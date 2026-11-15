"""Batched torch copy of CMU's commander teleop law, real mode, trajectory output (one tick = 0.05 s).

What it stands for
------------------
On the real drone (``drone_modes: real``, ``real_command_mode: trajectory``) a velocity command entering on
``/svg/<drone>/teleop_command`` does not reach PX4 as a bare speed. Each 20 Hz tick the commander
(``AirStack/robot/ros_ws/src/svg_ground_control/svg_ground_control/swarm_commander.py``) sends ONE setpoint with a
position, a speed and an acceleration. This module copies that law for N games of M drones, world ENU, metres
and seconds. The policy's command takes the place of the stick.

One tick, in the commander's order (file:line in swarm_commander.py unless said otherwise)
--------------------------------------------------------------------------------------
1. ``advance_reference`` (:1951-1979 -> position_hold.py:85-113). A fresh drone's reference point is seeded at
   its measured position (no move that tick) and its ramp restarts. Otherwise the reference moves by the speed
   published last tick x 0.05 s, then is leashed to ``teleop_lead_m``: the horizontal part on its norm, the
   vertical part on its own (position_hold.py:62-82). Where the leash pulls, reference = position + lead.
2. ``teleop_stick`` (:1879-1894): the command, scaled down to ``teleop_max_speed_mps`` when its norm is above
   the cap + 1e-3.
3. ``teleop_command`` (:1896-1910 -> position_hold.py:116-147): the ramp. It starts from the speed published last
   tick (``drone.published``; also when the ramp is fresh), or from its own last value when that is within
   ``ramp_reattach_mps`` of the published speed; moves toward the stick by at most ``teleop_accel_mps2 x dt``; the
   ramp's acceleration is (step / dt).
4. ``teleop_position_mode`` (:1912-1927): on the trajectory output the ramped stick is returned as is (no P term;
   ``teleop_kp`` unused). It is the filter's nominal command; the ramp's acceleration is ``accel_ff``.
5. The collision filter (:2140-2146) acts HERE, on the ramped stick, after the cap and the ramp and before the
   fence and the feed-forward. ``step(..., safety=fn)`` calls ``fn(nominal, pos) -> (safe, corrected)``; the
   training game passes ``core/safety_filter.py`` per team (models/fitted.py).
6. ``command_feedforward`` (:193-224, called at :2217-2220): the ramp's acceleration while the filter left the
   command alone (|safe - nominal| <= 1e-6); otherwise (safe - published) / dt, its norm capped at
   ``goal_accel_mps2`` (the scenario tracker's acceleration, default 3.0 at :374, :715).
7. If the filter corrected this drone (:2229-2234, ``result.corrected``, |safe - nominal| > 1e-3), its reference
   is leashed to ``hold_lead_m`` (0.2 m), on the same two-part leash.
8. ``publish_command`` (:2251-2313): position setpoint = the reference (:2260), speed = safe, acceleration = step 6;
   ``published`` = ``applied`` = safe (:2308-2309).

Left out, on purpose (each is listed in params/real_exploratory_v0.toml and the task report)
-------------------------------------------------------------------------------------------
* the stale-stick timeout (``teleop_timeout_s`` 0.5 s, :1881-1884): a policy commands every tick;
* the keep-in fences (teleop fence and geofence, :1966-1968 reference clamp, :2209-2210 speed clip and its
  braking feed-forward): the game's arena boundary is a game rule (a drone leaving it leaves the game). Since S2
  Task 7b the Starling layer (``core/starling_layer.StarlingLayer.keep_in``) copies the fence's effect AT the wall:
  the reference is clamped and the outward published speed and ramp are clipped to zero. The real fence's
  slow-down before the wall (``fence.py`` ``keep_in_velocity``, its margin and braking) is not copied;
* yaw (the teleop yaw rate, :2271-2283): it does not change the translation law;
* the takeoff, landing and hold states, and stale-odometry zero commands: a training drone is always ACTIVE;
* the emergency flag's re-leash of a filter group's drones whose command was NOT changed (:2229-2230,
  ``used_emergency_stop``): ``core/safety_filter.py`` reports emergency per game, not per team, so only
  ``corrected`` drones are re-leashed (every drone the push-apart moves is ``corrected``).

Shapes: N games, M drones; every vector tensor is [N, M, 3]; masks are [N, M] bool. No loops.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, fields
from typing import Callable

import torch
from torch import Tensor


@dataclass(frozen=True)
class CommanderParams:
    """Commander teleop parameters (SI, plain floats), from the ``[commander]`` table of a parameter TOML."""

    tick_s: float = 0.05
    teleop_max_speed_mps: float = 0.5
    teleop_accel_mps2: float = 5.0
    ramp_reattach_mps: float = 0.05
    teleop_lead_m: float = 0.5
    hold_lead_m: float = 0.2
    goal_accel_mps2: float = 3.0
    teleop_kp: float = 1.0           # recorded only: unused on the trajectory output
    teleop_timeout_s: float = 0.5    # recorded only: not modelled

    def __post_init__(self):
        for f in fields(self):
            value = float(getattr(self, f.name))
            object.__setattr__(self, f.name, value)
            if math.isnan(value) or value < 0.0:
                raise ValueError(f"{f.name} must be >= 0, got {value}")
        if self.tick_s <= 0.0:
            raise ValueError("tick_s must be > 0")

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "CommanderParams":
        unknown = set(d) - {f.name for f in fields(cls)}
        if unknown:
            raise ValueError(f"unknown CommanderParams keys: {sorted(unknown)}")
        return cls(**d)


def leash(lead: Tensor, max_xy: float, max_z: float | None = None) -> tuple[Tensor, Tensor]:
    """position_hold.leash, batched: lead [..., 3] -> (shortened lead [..., 3], pulled [...] bool).

    The horizontal part is scaled to norm <= max_xy and the vertical part clipped to |z| <= max_z, each on its
    own; 0 = no limit on that part.
    """
    if max_z is None:
        max_z = max_xy
    horizontal = torch.hypot(lead[..., 0], lead[..., 1])
    pull_xy = (horizontal > max_xy) if max_xy > 0.0 else torch.zeros_like(horizontal, dtype=torch.bool)
    pull_z = (lead[..., 2].abs() > max_z) if max_z > 0.0 else torch.zeros_like(horizontal, dtype=torch.bool)
    scale = torch.where(pull_xy, max_xy / torch.where(pull_xy, horizontal, torch.ones_like(horizontal)),
                        torch.ones_like(horizontal))
    xy = torch.where(pull_xy[..., None], lead[..., :2] * scale[..., None], lead[..., :2])
    z = torch.where(pull_z, torch.sign(lead[..., 2]) * max_z, lead[..., 2])
    return torch.cat([xy, z[..., None]], dim=-1), pull_xy | pull_z


SafetyFn = Callable[[Tensor, Tensor], tuple[Tensor, Tensor]]


class TeleopCommander:
    """The commander's real-mode teleop law for N games x M drones; see the module docstring.

    State per drone: reference point ``ref`` [N, M, 3] (``seeded`` [N, M] bool says it exists), the ramp's last
    velocity ``profile`` [N, M, 3] (``has_profile`` [N, M] bool), and ``published`` [N, M, 3], the speed sent
    last tick. A new commander, and ``reset``, leave every drone fresh: no reference, no ramp, published 0.
    """

    def __init__(self, n_games: int, n_drones: int, params: CommanderParams, device="cuda",
                 dtype: torch.dtype = torch.float32):
        self.p = params
        self.dt = params.tick_s
        shape = (n_games, n_drones, 3)
        self.ref = torch.zeros(shape, device=device, dtype=dtype)
        self.seeded = torch.zeros(shape[:2], device=device, dtype=torch.bool)
        self.profile = torch.zeros(shape, device=device, dtype=dtype)
        self.has_profile = torch.zeros(shape[:2], device=device, dtype=torch.bool)
        self.published = torch.zeros(shape, device=device, dtype=dtype)

    # ------------------------------------------------------------------------------------- the three stages
    def advance_reference(self, pos_m: Tensor) -> None:
        """Step 1: move each reference by what was published, leash it; seed fresh drones at pos_m [N, M, 3]."""
        r = self.ref + self.published * self.dt
        lead, pulled = leash(r - pos_m, self.p.teleop_lead_m)
        r = torch.where(pulled[..., None], pos_m + lead, r)
        fresh = ~self.seeded
        self.ref = torch.where(fresh[..., None], pos_m, r)
        self.has_profile = self.has_profile & self.seeded          # seeding restarts the ramp
        self.seeded = torch.ones_like(self.seeded)

    def shape(self, stick_mps: Tensor) -> tuple[Tensor, Tensor]:
        """Steps 2-4: the capped, ramped stick. stick [N, M, 3] -> (nominal [N, M, 3], accel_ff [N, M, 3])."""
        cap = self.p.teleop_max_speed_mps
        speed = stick_mps.norm(dim=-1, keepdim=True)
        over = speed > cap + 1e-3
        stick = torch.where(over, stick_mps * (cap / torch.where(over, speed, torch.ones_like(speed))), stick_mps)
        accel = self.p.teleop_accel_mps2
        if accel <= 0.0:                                            # ramp disabled: target passed through
            self.has_profile = torch.zeros_like(self.has_profile)
            return stick, torch.zeros_like(stick)
        base = self.published
        p = torch.where(self.has_profile[..., None], self.profile, base)
        p = torch.where(((base - p).norm(dim=-1) > self.p.ramp_reattach_mps)[..., None], base, p)
        dv = stick - p
        norm = dv.norm(dim=-1, keepdim=True)
        dv = dv * torch.clamp(accel * self.dt / norm.clamp(min=1e-9), max=1.0)
        p = p + dv
        self.profile = p
        self.has_profile = torch.ones_like(self.has_profile)
        return p.clone(), dv / max(self.dt, 1e-9)

    def finish(self, nominal: Tensor, accel_ff: Tensor, safe: Tensor, corrected: Tensor,
               pos_m: Tensor) -> tuple[Tensor, Tensor, Tensor]:
        """Steps 6-8 after the filter: -> (p_sp, v_ff, a_ff), each [N, M, 3], and remember what was published."""
        changed = (safe - nominal).norm(dim=-1, keepdim=True) > 1e-6
        acc = (safe - self.published) / max(self.dt, 1e-3)
        limit = self.p.goal_accel_mps2
        if limit > 0.0:
            n = acc.norm(dim=-1, keepdim=True)
            acc = torch.where(n > limit, acc * (limit / torch.where(n > limit, n, torch.ones_like(n))), acc)
        a_ff = torch.where(changed, acc, accel_ff)
        lead, pulled = leash(self.ref - pos_m, self.p.hold_lead_m)
        self.ref = torch.where((corrected & pulled)[..., None], pos_m + lead, self.ref)
        self.published = safe.clone()
        return self.ref.clone(), safe.clone(), a_ff

    # ------------------------------------------------------------------------------------- one tick
    def step(self, stick_mps: Tensor, pos_m: Tensor, safety: SafetyFn | None = None) -> tuple[Tensor, Tensor, Tensor]:
        """One 0.05 s tick. stick [N, M, 3] (world ENU, m/s), pos_m [N, M, 3] measured -> (p_sp, v_ff, a_ff)."""
        self.advance_reference(pos_m)
        nominal, accel_ff = self.shape(stick_mps)
        if safety is None:
            safe, corrected = nominal, torch.zeros(nominal.shape[:2], dtype=torch.bool, device=nominal.device)
        else:
            safe, corrected = safety(nominal, pos_m)
        return self.finish(nominal, accel_ff, safe, corrected, pos_m)

    def reset(self, mask: Tensor) -> None:
        """Make the drones where mask [N, M] bool is True fresh: no reference, no ramp, published 0."""
        keep = ~mask
        self.seeded = self.seeded & keep
        self.has_profile = self.has_profile & keep
        self.published = torch.where(mask[..., None], torch.zeros_like(self.published), self.published)
