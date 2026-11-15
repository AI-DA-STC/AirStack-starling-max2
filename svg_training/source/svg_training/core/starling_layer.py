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


class StarlingLayer:
    """Commander + safety filter (pairs as in the module docstring) + fitted PX4 response for N games of M drones.

    ``status`` is "exploratory" (the parameter file's label); ``stick_cap_mps`` is the commander's stick cap.
    """

    status = "exploratory"

    def __init__(self, cfg: GameCfg, num_games: int, guards: int, strikes: int, device: str | torch.device):
        params = load_params(resolve_params(cfg.starling.params))
        commander = CommanderParams.from_dict(params["commander"])
        if abs(commander.tick_s - TICK_S) > 1e-12:
            raise ValueError(f"the parameter file's commander tick {commander.tick_s} s is not the game's tick "
                             f"{TICK_S} s")
        self.stick_cap_mps = commander.teleop_max_speed_mps
        for team in ("strike", "guard"):
            # the commander would clip a faster command to its cap, losing the Strike/Guard speed ratio silently.
            # The speed itself is not printed: it may be a partner value from the local file.
            if cfg.team_speed_mps(team) > self.stick_cap_mps + 1e-6:
                raise ValueError(f"the {team} team's speed exceeds the commander's stick cap "
                                 f"({self.stick_cap_mps} m/s): the Strike/Guard speed ratio would be lost")
        if cfg.preset not in ("partner", "contact"):
            raise ValueError(f"preset must be 'partner' or 'contact', got {cfg.preset!r}")
        m = guards + strikes
        off_diag = ~torch.eye(m, dtype=torch.bool, device=device)
        if cfg.preset == "partner":
            pairs = off_diag                                                   # every pair
        else:
            team = torch.arange(m, device=device) >= guards
            pairs = (team[:, None] == team[None, :]) & off_diag               # team-mates only
        self._pairs = pairs[None]                                              # [1, M, M]
        k = int(cfg.starling.filter_check_every)
        self.model = FittedResponse(num_games, m, params, device=device, safety_filter=True, pair_mask=pairs,
                                    filter_iterations=cfg.starling.filter_iterations,
                                    filter_kwargs={"check_every": k} if k > 0 else None, hover_seed=True)

    def reset(self, mask: Tensor, pos_m: Tensor) -> None:
        """Restart the drones where mask [N, M] bool is True: at rest at pos_m [N, M, 3], fresh commander."""
        self.model.reset(mask, pos_m)

    def step(self, cmd_mps: Tensor, pos_m: Tensor, alive: Tensor) -> tuple[Tensor, Tensor, Tensor]:
        """One 0.05 s tick. cmd_mps [N, M, 3] world ENU m/s (already capped to each team's speed), pos_m [N, M, 3]
        (the game's positions; the model adopts them first), alive [N, M] bool.

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
        zeroed too, as the real commander's keep_in fence publishes the clipped speed (``swarm_commander.py``
        :2208-2219, :2307-2308). Without it the commander copy remembers a speed the drone never had: the next ramp
        starts from it, and the safety filter believes a drone pinned at a wall is still moving away, so it lets an
        opposite drone close to ~0.77 m of a 1.10 m keep-out (S2 Task 7b fix)."""
        p = self.model.pos_m
        q = torch.maximum(torch.minimum(p, hi_m), lo_m)
        hit = q != p
        out_hi, out_lo = p > hi_m, p < lo_m                        # [N, M, 3] which side each clamped axis was on
        self.model.pos_m = q
        self.model.vel_mps = torch.where(hit, torch.zeros_like(self.model.vel_mps), self.model.vel_mps)
        c = self.model.commander
        c.ref = torch.maximum(torch.minimum(c.ref, hi_m), lo_m)
        c.published = torch.where((out_hi & (c.published > 0)) | (out_lo & (c.published < 0)),
                                  torch.zeros_like(c.published), c.published)
        c.profile = torch.where((out_hi & (c.profile > 0)) | (out_lo & (c.profile < 0)),
                                torch.zeros_like(c.profile), c.profile)
        return q
