"""The stage 5.2 training environment (NUS port Phase 5, Tasks S1 and S3): the hangar game of Phase 4 row 5 with fresh starts, run to the
time-out, one decision per ``hold_ticks`` ticks, with the partner's reward and a critic state, behind the interface of
:class:`svg_training.nus.replica_train.NusTrainEnv`, so ``nus/mappo.py`` and ``nus/selfplay.py`` run on it unchanged.

What one environment step is (plan section 5, P5-5, P5-6, P5-11):

* **Game.** ``NusHangarTrainGame`` (Phase 4 row 5: the fitted Starling layer with the EXPLORATORY drone model, the all-pairs safety
  filter, 3-D, height free in the band, the start-height jitter), fresh starts for every game from the generator the caller passes
  (``reset(n, generator)``), ``run_to_timeout`` on: a game ends only at its time limit; the sticky reached flag is set at the first tick
  a live Strike drone is inside the zone (the programme's first-reach rule, so the outcome equals the evaluation's) and stays set.
* **Decision and hold.** Each team gives one command per drone, ``(N, team, 3)`` inside the unit ball (vx, vy, vz; yaw rate 0); the
  game repeats it on each of the ``hold_ticks`` ticks of the step (the game scales it by the team speed; the filter acts every tick).
  One game is ``episode_steps`` decisions (= its ticks / ``hold_ticks``).
* **Observation.** Interface v0.2 (``core.observations.obs_v02``: v0.1 plus the height band), at the decision tick.
* **Reward** (S3), the Guard team's per decision; the Strike team gets the exact negative. The partner's reward
  (``replica_train.guard_reward``) in metres: the shaping scale is the method's divided by the deploy file's metres per unit, on the
  summed horizontal distance of the Strike drones to the zone centre at the start and at the end of the decision; the inside penalty
  uses the share of Strike drones inside the zone at the decision's end (the partner checks at its step's end); the first-reach
  penalty falls on the decision during which the first reach tick lies; the clean time-out reward on the last decision of a game that
  was never reached.
* **Critic state** (S3): ``SvgGame.state()`` (``build_state``, 61 numbers) then, only with ``critic_reached_flag``, the sticky reached
  flag, then the one-hot of the game's opponent slot padded to the method's slot count (plan section 5).
* **Scripted slot**: the partner's APF of either team (``nus/apf.py``) on the positions in partner units, the same command as
  ``players.ApfGuard`` / ``ApfStrike`` (displacement over the team's speed per step, clamped, vz 0), once per decision.
* **Training-curve metrics** (STANDARDS section 7.2, formatted by ``nus/tier1_metrics.py``): per game since the last reset, as device
  tensors (read once per update by the caller): live and filter-corrected drone-ticks, correction size, the change of the command
  between decisions, the same-team closest approach in 3-D, non-finite actions, the clamp share (``NusHangarGame.safety``).
* **Recording for videos**: ``begin_recording(slots, per, keep)`` keeps the per-tick positions of the first ``keep`` games of each of
  ``slots`` blocks of ``per`` games, and the tick of each one's first reach; ``end_recording`` hands them over (one host copy, after the
  games). ``SelfPlay.evaluate`` calls both when its ``record_games`` is set, so videos come from the evaluation's own games.

The state object is a view of the live game (the game is stepped in place): only the latest state may be stepped or observed. A game
of each size is kept, at most ``MAX_GAMES`` sizes (least recently used dropped), so a training size and a selection-evaluation size
live side by side. Everything is a batched tensor operation: the Python loops are over the ticks of a hold only (no loop over games,
no host read in a step). No numeric literal other than 0, 1, -1, 2 (G2).
"""
from __future__ import annotations

import tomllib
from collections import OrderedDict
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import torch
from torch import Tensor

from ..core.game_config import GameCfg, load_game_cfg
from ..core.observations import OBS_DIM_V02, STATE_DIM, obs_v02
from ..core.starling_layer import resolve_params
from . import hangar as H
from . import strategy as strategy_module
from .apf import NusApf
from .deploy import NusDeploy, apply_overrides, load_deploy
from .hangar import Geometry
from .method_cfg import NusMethod
from .replica_train import StepOut, guard_reward
from .rules import ROOT, NusRules, file_sha256, load_rules
from .train_game import NusHangarTrainGame

TIER1_CONFIG = ROOT / "configs" / "nus_phase5_tier1.toml"
ACTION_DIM = 2 + 1          # vx, vy, vz (P5-11)
MAX_GAMES = 2               # game sizes kept at once (training and selection evaluation)


def load_tier1(path: Path | str = TIER1_CONFIG) -> dict[str, Any]:
    return tomllib.loads(Path(path).read_text())


# ------------------------------------------------------------------------------------------------ world
@dataclass
class Tier1World:
    """Everything the 5.2 game needs from the local files and the committed settings (values in memory only)."""
    cfg: GameCfg
    geo: Geometry
    row: dict
    rules: NusRules
    deploy: NusDeploy
    guards: int
    strikes: int
    jitter_m: float
    clamp_tol_m: float
    filter_path: str
    game_file: Path
    local_sha256: dict = field(default_factory=dict)


def filter_path_name(cfg: GameCfg) -> str:
    """Which safety filter path a game runs (recorded by every 5.2 run)."""
    if cfg.starling.filter_cuda_graph:
        return "cuda_graph (core/safety_filter_graph.py, fixed shape: the fixed loop's answer bit for bit)"
    k = int(cfg.starling.filter_check_every)
    return f"existing (core/safety_filter.py, early stop every {k} sweeps)" if k > 0 else "existing (core/safety_filter.py, fixed loop)"


def tier1_world(row_id: str | None = None, filter_cuda_graph: bool = False) -> Tier1World:
    """Row ``row_id`` (default ``[world] row``) of ``configs/nus_phase4.toml`` built from the local files, the reward weight of the game
    config left at the hangar file's (unused: the reward is the partner's); ``filter_cuda_graph`` turns on the opt-in filter path."""
    settings, tier1 = H.load_phase4(), load_tier1()
    row_id = row_id or tier1["world"]["row"]
    base, _ = load_game_cfg(H.HANGAR_GAME, use_local=False)
    deploy = load_deploy(strategy_module.DEPLOY_PATH)
    rules = apply_overrides(load_rules(strategy_module.RULES_PATH), deploy)
    hangar = H.load_hangar(H.LOCAL_HANGAR)
    row = {r["id"]: r for r in settings["row"]}[row_id]
    H.check_row(row)
    cfg = H.hangar_cfg(base, rules, deploy, hangar, row)
    if filter_cuda_graph:
        cfg = cfg.replace(**{"starling.filter_cuda_graph": True})
    sha = {"rules": file_sha256(strategy_module.RULES_PATH), "deploy": file_sha256(strategy_module.DEPLOY_PATH),
           "hangar": file_sha256(H.LOCAL_HANGAR), "game_config": file_sha256(H.HANGAR_GAME), "phase4_settings": file_sha256(H.PHASE4_CONFIG),
           "drone_model_params": file_sha256(resolve_params(cfg.starling.params))}
    return Tier1World(cfg, H.geometry(rules, deploy, hangar, base), row, rules, deploy, rules.guard_count, rules.strike_count,
                      float(settings["ladder"]["jitter_m"]), float(tier1["world"]["clamp_tolerance_m"]), filter_path_name(cfg),
                      Path(H.HANGAR_GAME), sha)


# ------------------------------------------------------------------------------------------------ reward (S3)
def tier1_guard_reward(prev_xy_m: Tensor, xy_m: Tensor, inside_count: Tensor, time_limit: Tensor, reached_after: Tensor,
                       first_reach: Tensor, *, guard_count: int, method: NusMethod, shaping_gamma: float, metres_per_unit: float) -> Tensor:
    """The Guard team's reward of one decision, (N,), in metres: ``replica_train.guard_reward`` with the shaping scale converted from
    partner units by the deploy file's scale. ``prev_xy_m``, ``xy_m``: (N, M, 2) horizontal positions relative to the zone centre at
    the decision's start and end; the rest as ``guard_reward``."""
    in_metres = replace(method, shaping_scale=method.shaping_scale / metres_per_unit)
    return guard_reward(prev_xy_m, xy_m, inside_count, time_limit, reached_after, first_reach, guard_count=guard_count,
                        method=in_metres, shaping_gamma=shaping_gamma)


# ------------------------------------------------------------------------------------------------ state
@dataclass
class Tier1Game:
    """What the learner reads (``state.game``): ``pos`` (N, M, 3) m at the end of the last tick played; ``reached`` (N,) float 0/1,
    sticky; ``step`` (N,) long, decisions played."""
    pos: Tensor
    reached: Tensor
    step: Tensor


@dataclass
class Tier1State:
    """``game``: see :class:`Tier1Game`; ``handle``: the live game; ``first_tick`` (N,) long: the tick of the first reach, -1 if none."""
    game: Tier1Game
    handle: NusHangarTrainGame
    first_tick: Tensor


class NusTier1Env:
    """See the module docstring. ``seed``: the games' own start seed (used only when ``reset`` gets no generator)."""

    def __init__(self, world: Tier1World, method: NusMethod, device: torch.device | str = "cpu", seed: int = 0,
                 critic_reached_flag: bool | None = None):
        self.world, self.method, self.device = world, method, torch.device(device)
        self.rules, self.deploy, self.cfg = world.rules, world.deploy, world.cfg
        self.dtype = torch.float32
        self.guard_count, self.strike_count = world.guards, world.strikes
        self.num_actors = world.guards + world.strikes
        self.hold = int(world.geo.hold_ticks)
        self.episode_steps = int(world.rules.episode_steps)
        self.obs_dim, self.action_dim = OBS_DIM_V02, ACTION_DIM
        flag = load_tier1()["world"]["critic_reached_flag"] if critic_reached_flag is None else critic_reached_flag
        self.critic_reached_flag = bool(flag)
        self.slots = method.max_pool_slots
        self.base_state_dim = STATE_DIM + int(self.critic_reached_flag)
        self.state_dim = self.base_state_dim + self.slots
        self.apf = NusApf(world.rules, world.deploy)
        self.seed = int(seed)
        self._games: OrderedDict[int, NusHangarTrainGame] = OrderedDict()
        self._recording: dict[str, Any] | None = None
        self.stats: dict[str, Tensor] = {}

    # ------------------------------------------------------------------ teams
    def team_size(self, team: str) -> int:
        return self.guard_count if team == "guard" else self.strike_count

    def team_speed(self, team: str) -> float:
        """The command is normalised (the unit ball); the game scales it by the team's speed in m/s."""
        return 1.0

    # ------------------------------------------------------------------ games
    def _game(self, n: int) -> NusHangarTrainGame:
        game = self._games.pop(n, None)
        if game is None:
            while len(self._games) >= MAX_GAMES:
                self._games.popitem(last=False)
            w = self.world
            game = NusHangarTrainGame(w.cfg, w.geo, w.row, w.rules, w.guards, w.strikes, n, device=str(self.device), seed=self.seed,
                                      jitter_m=w.jitter_m, run_to_timeout=True, clamp_tol_m=w.clamp_tol_m)
            if game.ticks != self.episode_steps * self.hold:
                raise ValueError("the game's ticks are not the partner's steps times the hold: the decision schedule would drift")
        self._games[n] = game
        return game

    def reset(self, n_games: int, generator: torch.Generator | None = None) -> Tier1State:
        """Fresh games from the replica's start rule; starts drawn from ``generator`` when given (reproducible, resumable)."""
        game = self._game(int(n_games))
        if generator is not None:
            game.set_start_generator(generator)
        game.reset()
        n, dev, m = game.num_games, self.device, self.num_actors
        self._recording = None
        big = float("inf")
        self.stats = {"live_ticks": torch.zeros(n, device=dev), "corrected_ticks": torch.zeros(n, device=dev),
                      "correction_sum_mps": torch.zeros(n, device=dev), "smooth_sum_mps": torch.zeros(n, device=dev),
                      "smooth_n": torch.zeros(n, device=dev), "team_min_3d_m": torch.full((n,), big, device=dev),
                      "nonfinite_actions": torch.zeros(n, dtype=torch.long, device=dev),
                      "last_cmd_mps": torch.zeros(n, m, ACTION_DIM, device=dev), "decisions": torch.zeros((), dtype=torch.long, device=dev)}
        state = Tier1Game(game.pos_m.clone(), torch.zeros(n, device=dev), torch.zeros(n, dtype=torch.long, device=dev))
        return Tier1State(state, game, torch.full((n,), -1, dtype=torch.long, device=dev))

    # ------------------------------------------------------------------ views
    def observe(self, state: Tier1State) -> tuple[Tensor, Tensor]:
        """(Guard observations (N, G, 73), Strike observations (N, S, 73)): interface v0.2 at the decision tick."""
        obs = state.handle._obs()
        return obs_v02(obs["guard"], self.cfg), obs_v02(obs["strike"], self.cfg)

    def central_state(self, state: Tier1State, slot_ids: Tensor) -> Tensor:
        """(N, state_dim): ``build_state``, the reached flag when ``critic_reached_flag``, the opponent slot's one-hot."""
        parts = [state.handle.state()]
        if self.critic_reached_flag:
            parts.append(state.game.reached[:, None])
        parts.append(torch.nn.functional.one_hot(slot_ids.long(), self.slots).to(self.dtype))
        return torch.cat(parts, dim=-1)

    def _xy(self, game: NusHangarTrainGame, pos_m: Tensor) -> Tensor:
        return pos_m[..., :2] - game.arenas.zone_centre_m[:, None, :]

    def apf_actions(self, state: Tier1State, team: str) -> Tensor:
        """The partner's scripted controller of ``team`` as a normalised command (N, team size, 3), vz 0."""
        game = state.handle
        units = self.apf.actions(team, self._xy(game, state.game.pos) / self.deploy.metres_per_unit)
        speed = self.rules.guard_max_speed if team == "guard" else self.rules.strike_max_speed
        xy = (units / speed).clamp(-1, 1)
        return torch.cat((xy, torch.zeros_like(xy[..., :1])), dim=-1)

    # ------------------------------------------------------------------ step
    def step(self, state: Tier1State, guard_actions: Tensor, strike_actions: Tensor, shaping_gamma: float) -> tuple[Tier1State, StepOut]:
        """One decision: ``guard_actions`` (N, G, 3), ``strike_actions`` (N, S, 3) inside the unit ball, held for ``hold_ticks`` ticks.
        ``shaping_gamma``: the learner team's discount (per decision)."""
        game, st = state.handle, self.stats
        yaw = torch.zeros_like(guard_actions[..., :1])
        actions = {"guard": torch.cat((guard_actions, yaw), dim=-1), "strike": torch.cat((strike_actions, yaw[:, :1].expand_as(strike_actions[..., :1])), dim=-1)}
        cmd = torch.cat((guard_actions, strike_actions), dim=1)
        cmd = cmd / cmd.norm(dim=-1, keepdim=True).clamp(min=1.0) * game._speed_mps
        live = game.alive
        seen = (state.game.step > 0).to(cmd.dtype)     # the first decision of a game has no previous command
        st["smooth_sum_mps"] += seen * ((cmd - st["last_cmd_mps"]).norm(dim=-1) * live).sum(dim=1)
        st["smooth_n"] += seen * live.sum(dim=1)
        st["last_cmd_mps"] = cmd
        start_xy = self._xy(game, state.game.pos)
        reached = state.game.reached > 0
        first_tick = state.first_tick
        tick0 = state.game.step * self.hold
        rec = self._recording
        same = game._same
        for k in range(self.hold):
            out = game.step(actions)
            now = out.info["reached_now"]
            first_tick = torch.where(~reached & now, tick0 + k + 1, first_tick)
            reached = reached | now
            alive = out.info["final_alive"]
            pos = game._last_pos
            st["live_ticks"] += alive.sum(dim=1)
            hit = out.info["filter_corrected"] & alive
            st["corrected_ticks"] += hit.sum(dim=1)
            if game._corr_size is not None:
                st["correction_sum_mps"] += (game._corr_size * hit).sum(dim=1)
            dist3 = (pos[:, :, None, :] - pos[:, None, :, :]).norm(dim=-1)
            live2 = alive[:, :, None] & alive[:, None, :]
            st["team_min_3d_m"] = torch.minimum(st["team_min_3d_m"], torch.where(live2 & same, dist3, torch.full_like(dist3, float("inf"))).amin(dim=(1, 2)))
            st["nonfinite_actions"] += out.info["nonfinite_actions"]
            if rec is not None:
                rec["frames"].append(pos[rec["index"]].clone())
        end_pos = game._last_pos
        end_xy = self._xy(game, end_pos)
        inside = ((end_xy[:, self.guard_count:].norm(dim=-1) <= game.arenas.zone_radius_m[:, None]) & game.alive[:, self.guard_count:]).sum(dim=1)
        step = state.game.step + 1
        time_limit = step >= self.episode_steps
        first = reached & ~(state.game.reached > 0)
        reward = tier1_guard_reward(start_xy, end_xy, inside, time_limit, reached, first, guard_count=self.guard_count, method=self.method,
                                    shaping_gamma=shaping_gamma, metres_per_unit=self.deploy.metres_per_unit)
        st["decisions"] += 1
        if rec is not None:
            rec["first_tick"] = first_tick[rec["index"]]
        nxt = Tier1State(Tier1Game(end_pos.clone(), reached.to(self.dtype), step), game, first_tick)
        return nxt, StepOut(guard_reward=reward, inside_count=inside, first_reach=first, time_limit=time_limit, reached=reached)

    # ------------------------------------------------------------------ recording (videos from the evaluation's own games)
    def begin_recording(self, slots: int, per: int, keep: int, state: Tier1State) -> None:
        """Keep the per-tick positions of the first ``keep`` games of each of ``slots`` blocks of ``per`` games of ``state``."""
        keep = min(int(keep), int(per))
        index = (torch.arange(slots, device=self.device)[:, None] * per + torch.arange(keep, device=self.device)[None, :]).reshape(-1)
        self._recording = {"index": index, "slots": int(slots), "keep": keep, "frames": [state.game.pos[index].clone()],
                           "first_tick": state.first_tick[index]}

    def end_recording(self) -> dict[str, Any] | None:
        """{"frames": (ticks + 1, slots, keep, M, 3) host, "first_tick": (slots, keep) host long (-1 = never reached)} or None."""
        rec, self._recording = self._recording, None
        if rec is None:
            return None
        frames = torch.stack(rec["frames"]).reshape(len(rec["frames"]), rec["slots"], rec["keep"], self.num_actors, -1).cpu()
        return {"frames": frames, "first_tick": rec["first_tick"].reshape(rec["slots"], rec["keep"]).cpu()}

    def safety(self, state: Tier1State) -> dict[str, Tensor]:
        """The game's clamp counters since the last reset (``NusHangarGame.safety``), device tensors."""
        return state.handle.safety()
