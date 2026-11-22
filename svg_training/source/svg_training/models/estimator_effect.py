"""What PX4's cascade sees of the drone (STE tasks L1.1 and L1.1b): the true state plus EKF2's estimate error.

The physics drone reads the true state from the world after every physics step; this effect turns it into the state the
cascade flies on. The game, the commander, the upset check and the drag keep the true state.

Shape of the model (L1.1b, from the L1.1 code review). EKF2's output predictor hands the controllers CURRENT-time states:
its error is a slowly varying offset, not a transport delay. A pure delay on the whole state is the wrong shape: in a
CPU check of 22 Nov 2026 the z loop (MPC_Z_P 5 x MPC_Z_VEL_P_ACC 8) went unstable at about 0.117 s of feedback delay.
So:

- **Correlated error (the main term).** Per quantity (position, velocity, attitude as a small body rotation) and per
  axis, a first-order Gauss-Markov process (exponentially correlated noise) with stationary standard deviation sigma
  and correlation time tau: x_{k+1} = a x_k + sigma sqrt(1 - a^2) w_k, a = exp(-dt / tau), w_k ~ N(0, 1) (the exact
  discretisation: stationary N(0, sigma^2), lag-1 autocorrelation a). At a reset the restarted drones draw x from the
  stationary distribution N(0, sigma^2) (no warm-up). ``replace_latest`` keeps x (no time passes).
- **White noise.** Independent Gaussian noise per axis and per physics step (L1.1): position, velocity, attitude and
  body rates. Body rates get only this: PX4's rate loop reads the gyro (``vehicle_angular_velocity``), not EKF2.
- **Residual delay (position and velocity only).** ``delay_steps`` physics steps of a ring buffer of past true
  positions and velocities. WARNING: kept only as a small residual (the code constant ``STATE_DELAY_MAX_S`` = 0.05 s,
  fixed; more is refused); attitude and body rates are never delayed.
- **Off.** With no delay, no white noise and no correlated error nothing is built or drawn and the true tensors are
  returned as they are.
- **Streams.** Each white quantity and each correlated quantity draws from its own ``torch.Generator``
  (``stream_seed(seed, i)``, i = its index in ``NOISE_STREAMS``), so switching one on never changes another's draws.
  ``seed`` is the game seed (``PhysicsLayer`` passes it): different runs draw different noise, the same seed the same.
  ``reseed(seed)`` restarts every stream (``SvgGame.reset(seed)``).
- **dtype.** The ring buffer, the noise and the error take the dtype of the first state they see (``reset``), so a
  float64 world is not rounded to float32.

Calls, made by ``PhysicsDrone``: ``reset(mask, ...)`` (call it first, with every drone: ``PhysicsDrone`` does) fills every
buffer entry of the drones in ``mask`` with their reset state and draws their error afresh; ``push(...)`` after each
physics step; ``replace_latest(...)`` when the game writes the state without a physics step (``write_clamped``: the entry
of the current instant is replaced, not added). Each returns the estimate (pos_m, quat_wxyz, vel_mps, ang_vel_b).

Tier 1 (STE L1.7, ``models/fitted.FittedResponse``) reuses this class for position and velocity errors only, with no
delay and no white noise; it has no attitude state and passes ``quat`` and ``ang`` as None, which pass through as None
while no attitude error and no attitude or rate noise is set.

Shapes: N games x M drones; pos, vel, body rates [N, M, 3], quaternions WXYZ [N, M, 4], masks [N, M] bool. Batched;
no host reads; the ring index is a Python integer advanced once per physics step (no loop over games or drones).
"""
from __future__ import annotations

import math

import torch
from torch import Tensor

from .frames import quat_mul_wxyz

_POS, _VEL = slice(0, 3), slice(3, 6)              # the delayed quantities, packed [.., 6] (never the attitude)
ERROR_QUANTITIES: tuple[str, ...] = ("pos", "att", "vel")          # the correlated (Gauss-Markov) estimate errors
# stream i of a seed: stream_seed(seed, i). White noise first (L1.1), then the correlated errors (L1.1b), appended.
WHITE_STREAMS: tuple[str, ...] = ("pos", "att", "vel", "rate")
NOISE_STREAMS: tuple[str, ...] = WHITE_STREAMS + tuple(f"{q}_error" for q in ERROR_QUANTITIES)
_STREAM_MIX = 0x9E3779B97F4A7C15     # odd 64-bit constant (as core/game.py's tag seed): spreads (seed, stream) pairs
_ERROR_MIX = 0xD1B54A32D192ED03      # another odd 64-bit constant, for the correlated-error streams (L1.1b)


def stream_seed(seed: int, stream: int) -> int:
    """The generator seed of noise stream ``stream`` for run seed ``seed``. White streams (0..3): ((seed + 1) x 4 +
    stream) x an odd 64-bit constant, mod 2^63, exactly as at L1.1 (their draws for a seed are unchanged); error streams
    (4..6): ((seed + 1) x 3 + stream - 4) x another odd constant, mod 2^63. One seed's streams never equal another
    seed's within a family (unlike seed + stream)."""
    w = len(WHITE_STREAMS)
    if stream < w:
        return (((seed + 1) * w + stream) * _STREAM_MIX) % (1 << 63)
    return (((seed + 1) * len(ERROR_QUANTITIES) + stream - w) * _ERROR_MIX) % (1 << 63)


class EstimatorEffect:
    """Correlated error, white noise and a small residual delay between the true state and PX4's cascade, N x M drones.

    ``error``: {quantity: (sigma, tau_s)} for quantities in ``ERROR_QUANTITIES`` (units: m, m/s, rad; s); a quantity
    with sigma 0 is off; sigma above 0 needs tau above 0 and ``dt_s`` (the physics step)."""

    def __init__(self, n: int, m: int, delay_steps: int, noise_pos_m: float, noise_vel_mps: float,
                 noise_att_rad: float, noise_rate_rad_s: float, device, dtype: torch.dtype = torch.float32,
                 seed: int = 0, error: dict[str, tuple[float, float]] | None = None,
                 dt_s: float | None = None) -> None:
        if isinstance(delay_steps, bool) or not isinstance(delay_steps, int) or delay_steps < 0:
            raise ValueError(f"delay_steps must be a whole number >= 0, got {delay_steps!r}")
        sig = {"pos": noise_pos_m, "att": noise_att_rad, "vel": noise_vel_mps, "rate": noise_rate_rad_s}
        for k, v in sig.items():
            if not math.isfinite(v) or v < 0:
                raise ValueError(f"noise of {k} must be a finite standard deviation >= 0, got {v!r}")
        error = dict(error or {})
        bad = sorted(set(error) - set(ERROR_QUANTITIES))
        if bad:
            raise ValueError(f"correlated error is built for the quantities {ERROR_QUANTITIES} only, got {bad}")
        self.error_a: dict[str, float] = {}                       # a = exp(-dt / tau) per correlated quantity
        self.error_sigma: dict[str, float] = {}
        for q in ERROR_QUANTITIES:
            s, tau = error.get(q, (0.0, 0.0))
            if not (math.isfinite(s) and s >= 0 and math.isfinite(tau) and tau >= 0):
                raise ValueError(f"error of {q}: sigma and tau must be finite and >= 0, got {(s, tau)!r}")
            if s == 0.0:
                continue
            if tau == 0.0:
                raise ValueError(f"error of {q}: sigma {s} needs a correlation time tau above 0 (white noise: noise_*)")
            if dt_s is None or not (math.isfinite(dt_s) and dt_s > 0):
                raise ValueError(f"a correlated error needs dt_s, the physics step in seconds, got {dt_s!r}")
            self.error_sigma[q] = s
            self.error_a[q] = math.exp(-dt_s / tau)
        self.correlated = tuple(q for q in ERROR_QUANTITIES if q in self.error_sigma)
        self.n, self.m = n, m
        self.device = torch.device(device)
        self.dtype = dtype
        self.delay_steps = delay_steps
        self.sigma = dict(sig)                                    # Python numbers (the parameter file)
        self.noisy = tuple(k for k in WHITE_STREAMS if self.sigma[k] > 0.0)
        self.off = delay_steps == 0 and not self.noisy and not self.correlated
        self.buffer: Tensor | None = None                         # [delay_steps + 1, N, M, 6], only with a delay
        self._newest = 0                                          # slot of the newest entry (Python int, no sync)
        self._gen: dict[str, torch.Generator] = {}
        self._noise: dict[str, Tensor] = {}                       # this physics step's white draws
        self._err: dict[str, Tensor] = {}                         # the correlated errors' state [N, M, 3]
        for k in self.noisy + tuple(f"{q}_error" for q in self.correlated):
            self._gen[k] = torch.Generator(device=self.device)
        self.reseed(seed)

    # ------------------------------------------------------------------------------------------- internals
    def _randn(self, key: str) -> Tensor:
        return torch.randn(self.n, self.m, 3, generator=self._gen[key], device=self.device, dtype=self.dtype)

    def _draw(self) -> None:
        for k in self.noisy:
            self._noise[k] = self._randn(k) * self.sigma[k]

    def _step_error(self) -> None:
        """One physics step of every correlated error: x = a x + sigma sqrt(1 - a^2) w."""
        for q in self.correlated:
            a = self.error_a[q]
            self._err[q] = a * self._err[q] + (self.error_sigma[q] * math.sqrt(1.0 - a * a)) * self._randn(f"{q}_error")

    def _restart_error(self, mask: Tensor) -> None:
        """Where mask: a fresh draw from the stationary distribution N(0, sigma^2). A full [N, M, 3] draw every time
        (no host read of the mask; the streams stay aligned whichever drones restart)."""
        for q in self.correlated:
            fresh = self._randn(f"{q}_error") * self.error_sigma[q]
            old = self._err.get(q)
            self._err[q] = fresh if old is None else torch.where(mask[..., None], fresh, old.to(fresh.dtype))

    def _delayed(self, pos: Tensor, vel: Tensor) -> tuple[Tensor, Tensor]:
        if self.buffer is None:
            return pos, vel
        old = self.buffer[(self._newest + 1) % (self.delay_steps + 1)].clone()   # a copy: the slot is reused
        return old[..., _POS], old[..., _VEL]

    def _estimate(self, pos: Tensor, quat: Tensor, vel: Tensor, ang: Tensor) -> tuple[Tensor, Tensor, Tensor, Tensor]:
        pos, vel = self._delayed(pos, vel)                       # attitude and body rates: current time, always
        if "pos" in self._noise:
            pos = pos + self._noise["pos"]
        if "pos" in self._err:
            pos = pos + self._err["pos"]
        if "vel" in self._noise:
            vel = vel + self._noise["vel"]
        if "vel" in self._err:
            vel = vel + self._err["vel"]
        if "rate" in self._noise:
            ang = ang + self._noise["rate"]
        rot = None                                               # small body rotation: white + correlated
        if "att" in self._noise:
            rot = self._noise["att"]
        if "att" in self._err:
            rot = self._err["att"] if rot is None else rot + self._err["att"]
        if rot is not None:
            half = 0.5 * rot
            dq = torch.cat((torch.ones_like(half[..., :1]), half), dim=-1)
            q = quat_mul_wxyz(quat, dq)
            quat = q / q.norm(dim=-1, keepdim=True)
        return pos, quat, vel, ang

    @staticmethod
    def _pack(pos: Tensor, vel: Tensor) -> Tensor:
        return torch.cat((pos, vel), dim=-1)

    # ------------------------------------------------------------------------------------------- interface
    def reseed(self, seed: int) -> None:
        """Restart every stream from ``seed`` (the game seed) and draw this physics step's white noise afresh. The
        correlated errors are drawn afresh at the next ``reset`` (SvgGame.reset(seed) restarts every drone)."""
        self.seed = seed
        for i, k in enumerate(NOISE_STREAMS):
            if k in self._gen:
                self._gen[k].manual_seed(stream_seed(self.seed, i))
        self._draw()

    def state_dict(self) -> dict:
        """Everything the next draws and estimates depend on (generator states, the white draws of this step, the
        correlated errors, the ring buffer): a replay restores it with ``load_state_dict`` so that it draws exactly what
        the recorded game drew (``ste/speed.py``, ``ste/tier2_train.py`` record_inputs / replay_positions)."""
        return {"seed": self.seed, "dtype": self.dtype, "newest": self._newest,
                "gen": {k: g.get_state() for k, g in self._gen.items()},
                "noise": {k: v.clone() for k, v in self._noise.items()},
                "err": {k: v.clone() for k, v in self._err.items()},
                "buffer": None if self.buffer is None else self.buffer.clone()}

    def load_state_dict(self, state: dict) -> None:
        """Restore ``state_dict()`` of an estimator with the same settings and shape (the replay's own drone)."""
        if set(state["gen"]) != set(self._gen):
            raise ValueError(f"estimator state has streams {sorted(state['gen'])}, this one {sorted(self._gen)}")
        self.seed, self.dtype, self._newest = state["seed"], state["dtype"], state["newest"]
        for k, g in self._gen.items():
            g.set_state(state["gen"][k])
        self._noise = {k: v.clone().to(self.device) for k, v in state["noise"].items()}
        self._err = {k: v.clone().to(self.device) for k, v in state["err"].items()}
        self.buffer = None if state["buffer"] is None else state["buffer"].clone().to(self.device)

    def reset(self, mask: Tensor, pos: Tensor, quat: Tensor, vel: Tensor, ang: Tensor) -> tuple[Tensor, ...]:
        """Where mask [N, M]: every buffer entry becomes this state (the drone has always been here) and the correlated
        error is drawn from its stationary distribution. Returns the estimate. No new white draw (the white noise of
        this physics step is kept)."""
        if self.off:
            return pos, quat, vel, ang
        packed = self._pack(pos, vel)
        if self.delay_steps > 0 and self.buffer is None:          # first reset: every slot of every drone
            self.buffer = packed[None].repeat(self.delay_steps + 1, 1, 1, 1)
        if packed.dtype != self.dtype:
            self.dtype = packed.dtype
            self._draw()
        if self.buffer is not None:
            self.buffer = torch.where(mask[None, ..., None], packed[None], self.buffer.to(packed.dtype))
        self._restart_error(mask)
        return self._estimate(pos, quat, vel, ang)

    def push(self, pos: Tensor, quat: Tensor, vel: Tensor, ang: Tensor) -> tuple[Tensor, ...]:
        """One physics step has passed: store the new true state, step the correlated errors, draw this step's white
        noise, return the estimate."""
        if self.off:
            return pos, quat, vel, ang
        if self.buffer is not None:
            self._newest = (self._newest + 1) % (self.delay_steps + 1)
            self.buffer[self._newest] = self._pack(pos, vel)
        self._step_error()
        self._draw()
        return self._estimate(pos, quat, vel, ang)

    def replace_latest(self, pos: Tensor, quat: Tensor, vel: Tensor, ang: Tensor) -> tuple[Tensor, ...]:
        """The state was written without a physics step: replace the newest entry (same instant); no new draw."""
        if self.off:
            return pos, quat, vel, ang
        if self.buffer is not None:
            self.buffer[self._newest] = self._pack(pos, vel)
        return self._estimate(pos, quat, vel, ang)
