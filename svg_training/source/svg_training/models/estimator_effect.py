"""What PX4's cascade sees of the drone (STE task L1.1): the true state, delayed and noisy, as EKF2's estimate is.

The physics drone reads the true state from the world after every physics step; this effect turns it into the state the
cascade flies on. The game, the commander, the upset check and the drag keep the true state.

- **Delay.** Position, velocity and attitude (EKF2's outputs) reach the cascade ``delay_steps`` physics steps late: a
  ring buffer of the last ``delay_steps + 1`` true states, one entry per physics step. Body rates are not delayed: PX4's
  rate loop reads the gyro (``vehicle_angular_velocity``), not EKF2.
- **Noise.** Independent Gaussian noise per axis and per physics step: position (m), velocity (m/s), attitude (a small
  rotation, rad, applied in the body frame: q (x) [1, d / 2], normalised) and body rates (rad/s). Each quantity draws from
  its own ``torch.Generator`` (``stream_seed(seed, i)``), so switching one on never changes another's draws.
  Noise is drawn once per physics step (``push``) and kept until the next one.
- **Off.** With no delay and no noise nothing is built or drawn and the true tensors are returned as they are.
- **dtype.** The ring buffer and the noise take the dtype of the first state they see (``reset``), so a float64
  world is not rounded to float32.

Calls, made by ``PhysicsDrone``: ``reset(mask, ...)`` (call it first, with every drone: ``PhysicsDrone`` does) fills every buffer entry of the drones in ``mask`` with their reset
state (all drones at construction); ``push(...)`` after each physics step; ``replace_latest(...)`` when the game writes
the state without a physics step (``write_clamped``: the entry of the current instant is replaced, not added, so the
delay stays a whole number of physics steps). Each returns the estimate (pos_m, quat_wxyz, vel_mps, ang_vel_b).

Shapes: N games x M drones; pos, vel, body rates [N, M, 3], quaternions WXYZ [N, M, 4], masks [N, M] bool. Batched;
no host reads; the ring index is a Python integer advanced once per physics step (no loop over games or drones).
"""
from __future__ import annotations

import math

import torch
from torch import Tensor

from .frames import quat_mul_wxyz

_POS, _QUAT, _VEL = slice(0, 3), slice(3, 7), slice(7, 10)     # the delayed quantities, packed [.., 10]
NOISE_STREAMS: tuple[str, ...] = ("pos", "att", "vel", "rate")  # stream i of a seed: stream_seed(seed, i)
_STREAM_MIX = 0x9E3779B97F4A7C15     # odd 64-bit constant (as core/game.py's tag seed): spreads (seed, stream) pairs


def stream_seed(seed: int, stream: int) -> int:
    """The generator seed of noise stream ``stream`` for run seed ``seed``: ((seed + 1) x 4 + stream) x an odd 64-bit
    constant, mod 2^63, so one seed's streams never equal another seed's (unlike seed + stream)."""
    return (((seed + 1) * len(NOISE_STREAMS) + stream) * _STREAM_MIX) % (1 << 63)


class EstimatorEffect:
    """Delay (whole physics steps) and Gaussian noise between the true state and PX4's cascade, for N x M drones."""

    def __init__(self, n: int, m: int, delay_steps: int, noise_pos_m: float, noise_vel_mps: float,
                 noise_att_rad: float, noise_rate_rad_s: float, device, dtype: torch.dtype = torch.float32,
                 seed: int = 0) -> None:
        if isinstance(delay_steps, bool) or not isinstance(delay_steps, int) or delay_steps < 0:
            raise ValueError(f"delay_steps must be a whole number >= 0, got {delay_steps!r}")
        sig = {"pos": noise_pos_m, "att": noise_att_rad, "vel": noise_vel_mps, "rate": noise_rate_rad_s}
        for k, v in sig.items():
            if not math.isfinite(v) or v < 0:
                raise ValueError(f"noise of {k} must be a finite standard deviation >= 0, got {v!r}")
        self.n, self.m = n, m
        self.device = torch.device(device)
        self.dtype = dtype
        self.delay_steps = delay_steps
        self.sigma = dict(sig)                                    # Python numbers (the parameter file)
        self.noisy = tuple(k for k in NOISE_STREAMS if self.sigma[k] > 0.0)
        self.off = delay_steps == 0 and not self.noisy
        self.buffer: Tensor | None = None                         # [delay_steps + 1, N, M, 10], only with a delay
        self._newest = 0                                          # slot of the newest entry (Python int, no sync)
        self._gen: dict[str, torch.Generator] = {}
        self._noise: dict[str, Tensor] = {}                       # this physics step's draws
        for i, k in enumerate(NOISE_STREAMS):
            if k in self.noisy:
                g = torch.Generator(device=self.device)
                g.manual_seed(stream_seed(seed, i))
                self._gen[k] = g
        self._draw()

    # ------------------------------------------------------------------------------------------- internals
    def _draw(self) -> None:
        for k in self.noisy:
            self._noise[k] = torch.randn(self.n, self.m, 3, generator=self._gen[k], device=self.device,
                                         dtype=self.dtype) * self.sigma[k]

    def _delayed(self, pos: Tensor, quat: Tensor, vel: Tensor) -> tuple[Tensor, Tensor, Tensor]:
        if self.buffer is None:
            return pos, quat, vel
        old = self.buffer[(self._newest + 1) % (self.delay_steps + 1)].clone()   # a copy: the slot is reused
        return old[..., _POS], old[..., _QUAT], old[..., _VEL]

    def _estimate(self, pos: Tensor, quat: Tensor, vel: Tensor, ang: Tensor) -> tuple[Tensor, Tensor, Tensor, Tensor]:
        pos, quat, vel = self._delayed(pos, quat, vel)
        if "pos" in self._noise:
            pos = pos + self._noise["pos"]
        if "vel" in self._noise:
            vel = vel + self._noise["vel"]
        if "rate" in self._noise:
            ang = ang + self._noise["rate"]
        if "att" in self._noise:
            half = 0.5 * self._noise["att"]
            dq = torch.cat((torch.ones_like(half[..., :1]), half), dim=-1)
            q = quat_mul_wxyz(quat, dq)
            quat = q / q.norm(dim=-1, keepdim=True)
        return pos, quat, vel, ang

    @staticmethod
    def _pack(pos: Tensor, quat: Tensor, vel: Tensor) -> Tensor:
        return torch.cat((pos, quat, vel), dim=-1)

    # ------------------------------------------------------------------------------------------- interface
    def reset(self, mask: Tensor, pos: Tensor, quat: Tensor, vel: Tensor, ang: Tensor) -> tuple[Tensor, ...]:
        """Where mask [N, M]: every buffer entry becomes this state (the drone has always been here). Returns the
        estimate. No new noise draw (the drawn noise of this physics step is kept)."""
        if self.off:
            return pos, quat, vel, ang
        packed = self._pack(pos, quat, vel)
        if self.delay_steps > 0 and self.buffer is None:          # first reset: every slot of every drone
            self.buffer = packed[None].repeat(self.delay_steps + 1, 1, 1, 1)
        if packed.dtype != self.dtype:
            self.dtype = packed.dtype
            self._draw()
        if self.buffer is not None:
            self.buffer = torch.where(mask[None, ..., None], packed[None], self.buffer.to(packed.dtype))
        return self._estimate(pos, quat, vel, ang)

    def push(self, pos: Tensor, quat: Tensor, vel: Tensor, ang: Tensor) -> tuple[Tensor, ...]:
        """One physics step has passed: store the new true state, draw this step's noise, return the estimate (the
        state of ``delay_steps`` steps earlier, plus noise)."""
        if self.off:
            return pos, quat, vel, ang
        if self.buffer is not None:
            self._newest = (self._newest + 1) % (self.delay_steps + 1)
            self.buffer[self._newest] = self._pack(pos, quat, vel)
        self._draw()
        return self._estimate(pos, quat, vel, ang)

    def replace_latest(self, pos: Tensor, quat: Tensor, vel: Tensor, ang: Tensor) -> tuple[Tensor, ...]:
        """The state was written without a physics step: replace the newest entry (same instant); no new draw."""
        if self.off:
            return pos, quat, vel, ang
        if self.buffer is not None:
            self.buffer[self._newest] = self._pack(pos, quat, vel)
        return self._estimate(pos, quat, vel, ang)
