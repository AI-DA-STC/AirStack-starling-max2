"""Starling layer for the S2 game: drones move as a real Starling would (S2 Task 4).

With ``[starling_layer] enabled = true`` each drone's command (already capped to its team's speed) goes through
``models/fitted.FittedResponse``: the copy of CMU's commander teleop law, the safety filter inside it, and the
PX4 response fitted to real flight logs. The parameter file (``params/real_exploratory_v0.toml``) is
EXPLORATORY: fitted on one flight at <= 0.5 m/s, no gates; results with this layer are labelled so.

Which pairs the safety filter sees, per step and per game:

* preset "partner": every pair of live drones, both teams, as on the real drones (the commander filters all the
  drones it flies). The partner push-apart is off in the game (decision D3); a breach of the partner keep-out
  is reported by the game, not prevented.
* preset "contact" (side quest): live team-mates only, so opposite drones can meet and tag.

A drone that is out of the game takes part in no pair (an isolated drone is its own filter group), is commanded
zero, and is restarted fresh (at rest, new commander reference) every step it is out.

Every (re)start seeds the PX4 model's delay history with a hover setpoint at the drone's position
(``FittedResponse(hover_seed=True)``): a real drone hovering at its start has been sent "hold here", so the first
command reaches PX4 after the fitted delay like every later one.

Everything is a batched tensor operation: no loop over games, no host reads (the filter's own fixed sweep loop
and the PX4 model's fixed sub-steps are the only loops). One exception, by choice: ``[starling_layer]
filter_check_every = k > 0`` turns on the filter's early stop, which reads one number back from the GPU every k
sweeps (one host sync per check, S2 plan decision D10; counted in the Task 7 filter-speed record). With k = 0 the
step makes no host sync. Shapes: N games, M drones (Guard drones first).
"""
from __future__ import annotations

from pathlib import Path

import torch
from torch import Tensor

from svg_training.models.commander import CommanderParams
from svg_training.models.fitted import FittedResponse, load_params

from .game_config import CONFIGS, TICK_S, GameCfg

ROOT = CONFIGS.parent          # svg_training/: relative parameter paths are read from here


def resolve_params(path: str) -> Path:
    """The parameter TOML path: absolute as given, else relative to svg_training/."""
    p = Path(path)
    return p if p.is_absolute() else ROOT / p


def check_commander(cfg: GameCfg, params: dict) -> float:
    """The checks every Starling-layer backend makes on its parameter file (``params`` = ``load_params`` dict):
    the commander's tick is the game's, and neither team's speed exceeds the commander's stick cap.
    Returns the stick cap (m/s)."""
    commander = CommanderParams.from_dict(params["commander"])
    if abs(commander.tick_s - TICK_S) > 1e-12:
        raise ValueError(f"the parameter file's commander tick {commander.tick_s} s is not the game's tick "
                         f"{TICK_S} s")
    stick_cap_mps = commander.teleop_max_speed_mps
    for team in ("strike", "guard"):
        # the commander would clip a faster command to its cap, losing the Strike/Guard speed ratio silently.
        # The speed itself is not printed: it may be a partner value from the local file.
        if cfg.team_speed_mps(team) > stick_cap_mps + 1e-6:
            raise ValueError(f"the {team} team's speed exceeds the commander's stick cap "
                             f"({stick_cap_mps} m/s): the Strike/Guard speed ratio would be lost")
    if cfg.preset not in ("partner", "contact"):
        raise ValueError(f"preset must be 'partner' or 'contact', got {cfg.preset!r}")
    return stick_cap_mps


def filter_pairs(cfg: GameCfg, guards: int, strikes: int, device: str | torch.device) -> Tensor:
    """[M, M] bool: the pairs the safety filter sees (module docstring): every pair (preset "partner") or
    team-mates only (preset "contact")."""
    m = guards + strikes
    off_diag = ~torch.eye(m, dtype=torch.bool, device=device)
    if cfg.preset == "partner":
        return off_diag                                                        # every pair
    team = torch.arange(m, device=device) >= guards
    return (team[:, None] == team[None, :]) & off_diag                         # team-mates only


def filter_fn(cfg: GameCfg):
    """The filter function from ``[starling_layer] filter_cuda_graph``: None (the command chain's default,
    ``core.safety_filter.filter_velocities``) when off, ``core.safety_filter_graph.filter_velocities_graph`` when on."""
    if not cfg.starling.filter_cuda_graph:
        return None
    from .safety_filter_graph import filter_velocities_graph
    return filter_velocities_graph


def filter_kwargs(cfg: GameCfg) -> dict | None:
    """The filter's early stop from ``[starling_layer] filter_check_every`` (0 = off: no host sync)."""
    k = int(cfg.starling.filter_check_every)
    return {"check_every": k} if k > 0 else None


class StarlingLayer:
    """Commander + safety filter (pairs as in the module docstring) + fitted PX4 response for N games of M drones.

    ``status`` is "exploratory" (the parameter file's label); ``stick_cap_mps`` is the commander's stick cap.
    """

    status = "exploratory"

    def __init__(self, cfg: GameCfg, num_games: int, guards: int, strikes: int, device: str | torch.device):
        params = load_params(resolve_params(cfg.starling.params))
        self.stick_cap_mps = check_commander(cfg, params)
        pairs = filter_pairs(cfg, guards, strikes, device)
        self._pairs = pairs[None]                                              # [1, M, M]
        m = guards + strikes
        self.model = FittedResponse(num_games, m, params, device=device, safety_filter=True, pair_mask=pairs,
                                    filter_iterations=cfg.starling.filter_iterations,
                                    filter_kwargs=filter_kwargs(cfg), hover_seed=True, filter_fn=filter_fn(cfg))

    def reset(self, mask: Tensor, pos_m: Tensor, yaw: Tensor | None = None) -> None:
        """Restart the drones where mask [N, M] bool is True: at rest at pos_m [N, M, 3], fresh commander.
        ``yaw`` [N, M] is accepted and ignored (the physics backend uses it)."""
        self.model.reset(mask, pos_m)

    def step(self, cmd_mps: Tensor, pos_m: Tensor, alive: Tensor, yaw: Tensor | None = None,
             yaw_rate_rad_s: Tensor | None = None) -> tuple[Tensor, Tensor, Tensor]:
        """One 0.05 s tick. cmd_mps [N, M, 3] world ENU m/s (already capped to each team's speed), pos_m [N, M, 3]
        (the game's positions; the model adopts them first), alive [N, M] bool. ``yaw`` / ``yaw_rate_rad_s`` [N, M]
        are accepted and ignored (the fitted model has no yaw; the physics backend uses them).

        Returns (pos_m [N, M, 3], vel_mps [N, M, 3], corrected [N, M] bool: live drones the filter changed)."""
        self.model.set_pair_mask(self._pairs & alive[:, :, None] & alive[:, None, :])
        self.model.reset(~alive)                       # out drones: at rest, fresh; they are in no pair
        vel = self.model.step(cmd_mps * alive[..., None], pos_m)
        return self.model.pos_m, vel, self.model.corrected & alive

    def keep_in(self, lo_m: Tensor, hi_m: Tensor) -> Tensor:
        """Walls (keep_in) and height band: clamp the positions to [lo_m, hi_m] (each broadcastable to [N, M, 3]),
        stop the model's speed on every clamped axis, and clamp the commander's reference point into the same box
        (as the real commander clamps its reference to its fence). Returns the clamped positions [N, M, 3].

        On every axis the wall clamped, the outward part of the commander's published speed and of its ramp is
        zeroed too, as the real commander's keep_in fence publishes the clipped speed at the wall
        (``swarm_commander.py`` :2208-2219, :2307-2308); the real fence's slow-down before the wall (``fence.py``
        ``keep_in_velocity``) is not copied. Without it the commander copy remembers a speed the drone never had: the next ramp
        starts from it, and the safety filter believes a drone pinned at a wall is still moving away, so it lets an
        opposite drone close to ~0.77 m of a 1.10 m keep-out (S2 Task 7b fix)."""
        p = self.model.pos_m
        q = torch.maximum(torch.minimum(p, hi_m), lo_m)
        hit = q != p
        out_hi, out_lo = p > hi_m, p < lo_m                        # [N, M, 3] which side each clamped axis was on
        self.model.pos_m = q
        self.model.vel_mps = torch.where(hit, torch.zeros_like(self.model.vel_mps), self.model.vel_mps)
        self.model.chain.keep_in(lo_m, hi_m, out_hi, out_lo)        # the commander's side (shared code)
        return q
