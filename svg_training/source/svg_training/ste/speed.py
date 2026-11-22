"""STE task L0.2 Tier 2 speed in contested play (INFO; PLAN.md section 4, DISCUSSION P3): the parts
``scripts/ste_speed_l02.py`` times and tests.

What one *point* (tier, team size, games at once) measures, in this order, on the L0.11 base game file
(``configs/ste_l011/base.toml``: study tag on, zone_disc_ring starts), tier 1 = the fitted Starling response, tier 2 = the
same file with ``starling_layer.backend = "physics"`` (the Isaac Lab rigid-body Starling; the file itself is never
edited, L0.11's gate pins its sha256):

1. **warm-up** (not timed): ``warmup_decisions`` learner decisions, so buffers and kernels exist;
2. **scripted reference** ("both teams playing", no learner): the base case's best scripted Guard against its best
   scripted Strike (T44: g* and s*), ``reference_decisions x decision_ticks`` ticks of every game, timed;
3. **learner in the loop**: the T41 / L0.12 recipe (skrl IPPO, one Gaussian policy and one value network per drone,
   one learner decision per ``decision_ticks`` ticks, the action held in between: ``nus/pilot.DecisionHoldEnv``)
   on the learner team against the other team's best script, ``updates`` x (``rollouts`` decisions, then skrl's PPO
   update: ``learning_epochs`` x ``mini_batches``). Timed apart: the rollouts (policy forward pass, sampling, game
   ticks, memory) and the PPO updates.

Rates are game-steps per second (one game-step = one 0.05 s tick of one game; drone-steps = game-steps x drones per
game): the reference rate, the rollout rate (learner forward in the loop) and the training rate (rollout game-steps over
rollout + update seconds). A CUDA synchronisation brackets every timed part (no host read inside one).

Shapes: N games, G Guard and S Strike drones (M = G + S); actions [N, G or S, 4] in [-1, 1]. No numeric literal other
than 0, 1, -1, 2 outside UPPER_CASE module constants (tests/test_ste_literals.py): every count and limit comes from the
gate file ``configs/ste_l02/gates.toml``."""
from __future__ import annotations

import dataclasses
import hashlib
import math
import time
import tomllib
from pathlib import Path
from typing import Any, Callable

import torch
from torch import Tensor

from ..core.game import SvgGame
from ..core.game_config import GameCfg, load_game_cfg
from ..core.rewards import STRIKE_WIN
from . import shared
from .sweep import parse_size

ROOT = shared.PACKAGE_DIR.parents[2]          # svg_training/
GATES_FILE = ROOT / "configs" / "ste_l02" / "gates.toml"
TIERS = (1, 2)
TEAMS = ("guard", "strike")
ACTION_AXES = {"vx": 0, "vy": 1, "vz": 2, "yaw": 3}
SKRL_KEYS = ("discount_factor", "gae_lambda", "entropy_loss_scale", "value_loss_scale", "ratio_clip", "value_clip",
             "grad_norm_clip")
GUARD_SEED_OFFSET = 101                    # players' seeds: game seed + these (scripts/score.py, viz/replay.py)
STRIKE_SEED_OFFSET = 202
MIB = 1048576                               # bytes per MiB
FIT = "fit"                                 # a point that ran
DID_NOT_FIT = "did_not_fit"                 # out of GPU memory (torch's error, or the child died without a row)

_SECTIONS = {
    "run": {"task", "verdict", "game_file", "game_sha256", "guard_script", "strike_script", "learner_team", "seed",
            "threads", "cap_h", "device"},
    "timing": {"warmup_decisions", "reference_decisions", "updates", "isaac_start_s", "process_start_s"},
    "trainer": {"algorithm", "decision_ticks", "rollouts", "learning_epochs", "mini_batches", "learning_rate", "hidden",
                "init_log_std", "frozen_log_std_axes", "zero_mean_init", *SKRL_KEYS},
    "controls": {"agree_point", "agree_games", "agree_ticks", "agree_max_m", "learner_update_point"},
    "clips": {"points", "games", "max_ticks", "speed", "fps", "dpi"},
}
_POINT_KEYS = {"id", "tier", "size", "games", "protected"}
_POINT_OPTIONAL = {"only_if_did_not_fit", "only_if_fit"}


@dataclasses.dataclass(frozen=True)
class Point:
    """One measured point: ``id`` (unique), ``tier`` 1 or 2, ``size`` ("3v3": Guard v Strike), ``games`` (N),
    ``protected`` (never cut to fit the cap), and the optional conditions ``only_if_did_not_fit`` /
    ``only_if_fit`` (the id of an earlier point: run this one only if that one did not fit / fitted)."""
    id: str
    tier: int
    size: str
    games: int
    protected: bool
    only_if_did_not_fit: str | None
    only_if_fit: str | None

    @property
    def drones(self) -> int:
        g, s = parse_size(self.size)
        return g + s


@dataclasses.dataclass(frozen=True)
class Gates:
    """The gate file, checked: its sections as dicts, the points in run order, the file's path and sha256."""
    path: Path
    sha256: str
    run: dict
    timing: dict
    trainer: dict
    controls: dict
    clips: dict
    points: tuple[Point, ...]

    def point(self, pid: str) -> Point:
        for p in self.points:
            if p.id == pid:
                return p
        raise KeyError(f"no point {pid!r} in {self.path}")


def sha256_file(path: Path | str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_gates(path: Path | str = GATES_FILE) -> Gates:
    """Read and check the gate file: exact keys per section (ValueError on a missing or unknown key), the points'
    ids unique, tiers in TIERS, sizes parse, conditions name an earlier point, the decision schedule whole numbers,
    the learner team a team name, the scripted players' teams the other way round from the learner's."""
    path = Path(path)
    data = tomllib.loads(path.read_text())
    want = set(_SECTIONS) | {"point"}
    if set(data) != want:
        raise ValueError(f"{path}: sections must be {sorted(want)}, got {sorted(data)}")
    for name, keys in _SECTIONS.items():
        have = set(data[name])
        if have != keys:
            raise ValueError(f"{path}: [{name}] unknown {sorted(have - keys)}, missing {sorted(keys - have)}")
    points, seen = [], set()
    for row in data["point"]:
        have = set(row)
        if not _POINT_KEYS <= have or have - _POINT_KEYS - _POINT_OPTIONAL:
            raise ValueError(f"{path}: a [[point]] needs {sorted(_POINT_KEYS)} (optional {sorted(_POINT_OPTIONAL)}), "
                             f"got {sorted(have)}")
        p = Point(str(row["id"]), int(row["tier"]), str(row["size"]), int(row["games"]), bool(row["protected"]),
                  row.get("only_if_did_not_fit"), row.get("only_if_fit"))
        if p.id in seen:
            raise ValueError(f"{path}: point id {p.id!r} twice")
        if p.tier not in TIERS:
            raise ValueError(f"{path}: point {p.id}: tier must be one of {TIERS}")
        if p.games < 1:
            raise ValueError(f"{path}: point {p.id}: games must be >= 1")
        parse_size(p.size)
        for cond in (p.only_if_did_not_fit, p.only_if_fit):
            if cond is not None and cond not in seen:
                raise ValueError(f"{path}: point {p.id}: condition {cond!r} must name an earlier point")
        seen.add(p.id)
        points.append(p)
    if not points:
        raise ValueError(f"{path}: no [[point]]")
    if data["run"]["learner_team"] not in TEAMS:
        raise ValueError(f"{path}: [run] learner_team must be one of {TEAMS}")
    tr = data["trainer"]
    for k in ("decision_ticks", "rollouts", "learning_epochs", "mini_batches"):
        if isinstance(tr[k], bool) or not isinstance(tr[k], int) or tr[k] < 1:
            raise ValueError(f"{path}: [trainer] {k} must be a whole number >= 1")
    if tr["algorithm"] != "IPPO":
        raise ValueError(f"{path}: [trainer] algorithm must be 'IPPO' (the T41 recipe)")
    bad = [a for a in tr["frozen_log_std_axes"] if a not in ACTION_AXES]
    if bad:
        raise ValueError(f"{path}: [trainer] frozen_log_std_axes from {list(ACTION_AXES)}, got {bad}")
    ids = {p.id for p in points}
    for k in ("agree_point", "learner_update_point"):
        if data["controls"][k] not in ids:
            raise ValueError(f"{path}: [controls] {k} must name a point")
        named = next(p for p in points if p.id == data["controls"][k])
        smallest = min(p.games for p in points if p.tier == named.tier and p.protected) if named.protected else None
        if not named.protected or named.games != smallest:        # QC L02-9: the controls' points always run
            raise ValueError(f"{path}: [controls] {k} must be a protected point at its tier's smallest games")
    if data["controls"]["agree_point"] and data_point_tier(points, data["controls"]["agree_point"]) != max(TIERS):
        raise ValueError(f"{path}: [controls] agree_point must be a tier 2 point")
    for c in data["clips"]["points"]:
        if c not in ids:
            raise ValueError(f"{path}: [clips] points: {c!r} is not a point")
    return Gates(path, sha256_file(path), dict(data["run"]), dict(data["timing"]), dict(tr), dict(data["controls"]),
                 dict(data["clips"]), tuple(points))


def data_point_tier(points: list[Point], pid: str) -> int:
    return next(p.tier for p in points if p.id == pid)


def game_problem(gates: Gates, root: Path = ROOT) -> str | None:
    """None if the game file exists and has the sha256 the gate file pins, else the reason."""
    f = root / gates.run["game_file"]
    if not f.is_file():
        return f"the game file {f} is missing"
    have = sha256_file(f)
    if have != gates.run["game_sha256"]:
        return f"the game file {f} has sha256 {have}, the gate file pins {gates.run['game_sha256']}"
    return None


def tier_cfg(gates: Gates, tier: int, root: Path = ROOT) -> GameCfg:
    """The game of a tier: the base game file as committed (tier 1), or the same with the physics backend (tier 2).
    Loaded with use_local=False (a partner's local file never changes it)."""
    cfg, _ = load_game_cfg(root / gates.run["game_file"], use_local=False)
    if tier == max(TIERS):
        cfg = cfg.replace(**{"starling.backend": "physics"})
    return cfg


def cfg_differences(a: GameCfg, b: GameCfg, prefix: str = "") -> list[str]:
    """Dotted names of the settings that differ between two game configs (nested dataclasses walked)."""
    out = []
    for f in dataclasses.fields(a):
        va, vb = getattr(a, f.name), getattr(b, f.name)
        name = f"{prefix}{f.name}"
        if dataclasses.is_dataclass(va) and dataclasses.is_dataclass(vb):
            out += cfg_differences(va, vb, name + ".")
        elif va != vb:
            out.append(name)
    return out


# ================================================================================================ planning
def runnable(point: Point, rows: dict[str, dict]) -> bool | None:
    """Whether a point's condition lets it run, given the finished rows {id: row}: True, False, or None when the point
    it depends on has no row (not run yet, or cut). ``only_if_did_not_fit``: the named point's status is not FIT
    (did_not_fit, or crashed); ``only_if_fit``: it is FIT."""
    for cond, want_fit in ((point.only_if_did_not_fit, False), (point.only_if_fit, True)):
        if cond is None:
            continue
        if cond not in rows:
            return None
        if (rows[cond]["status"] == FIT) != want_fit:
            return False
    return True


def point_game_steps(gates: Gates, point: Point) -> int:
    """Game-steps a point plays: (warm-up + reference + updates x rollouts) decisions x decision ticks x games."""
    t, tr = gates.timing, gates.trainer
    decisions = int(t["warmup_decisions"]) + int(t["reference_decisions"]) + int(t["updates"]) * int(tr["rollouts"])
    return decisions * int(tr["decision_ticks"]) * point.games


def timed_s_per_tick(gates: Gates, row: dict) -> float | None:
    """A measured row's timed seconds per game tick (scripted reference, learner rollouts and updates; not the process
    start, the agreement control or the clips), or None for a row that did not run."""
    if row.get("status") != FIT:
        return None
    ticks = row["reference"]["ticks"] + row["learner"]["decisions"] * int(gates.trainer["decision_ticks"])
    seconds = row["reference"]["seconds"] + row["learner"]["rollout_s"] + row["learner"]["update_s"]
    return seconds / ticks if ticks else None


def projected_s(gates: Gates, point: Point, rows: dict[str, dict]) -> float:
    """Seconds a point is expected to take: its process start (Isaac start for tier 2) plus its ticks at the timed
    seconds per tick of the nearest measured row of its tier (same size first, then the nearest games), scaled up in
    proportion when the point has more games (T12: the tier 2 tick time was nearly flat up to 4,096 games, so this
    over-estimates; never scaled down). Without a measured row of its tier: the start time alone."""
    start = float(gates.timing["isaac_start_s"] if point.tier == max(TIERS) else gates.timing["process_start_s"])
    known = [r for r in rows.values() if r.get("tier") == point.tier and timed_s_per_tick(gates, r)]
    if not known:
        return start
    near = min(known, key=lambda r: (r["size"] != point.size, abs(r["games"] - point.games)))
    ticks = point_game_steps(gates, point) // point.games
    return start + timed_s_per_tick(gates, near) * ticks * max(point.games / near["games"], 1.0)


def plan_cuts(gates: Gates, todo: list[Point], rows: dict[str, dict], left_s: float) -> list[str]:
    """Ids of the unprotected points to cut, taken from the END of the run order, until the projected time of what is
    left fits ``left_s``. Protected points are never cut (the cap then stops the run)."""
    keep = list(todo)
    cut = []
    while sum(projected_s(gates, p, rows) for p in keep) > left_s:
        drop = next((p for p in reversed(keep) if not p.protected), None)
        if drop is None:
            break
        keep.remove(drop)
        cut.append(drop.id)
    return cut


# ================================================================================================ one point
def sync(device: str) -> None:
    if torch.device(device).type == "cuda":
        torch.cuda.synchronize()


def make_game(cfg: GameCfg, point: Point, device: str, seed: int, world: Any = None) -> SvgGame:
    g, s = parse_size(point.size)
    return SvgGame(cfg, point.games, g, s, device=device, seed=seed, band=0, world=world)


def scripted(gates: Gates, team: str, cfg: GameCfg, games: int, device: str, seed: int):
    from ..opponents.scripted import make_strategy
    spec = gates.run["guard_script"] if team == TEAMS[0] else gates.run["strike_script"]
    return make_strategy(spec, team, cfg, games, device, seed + (GUARD_SEED_OFFSET if team == TEAMS[0] else STRIKE_SEED_OFFSET))


def play_scripted(game: SvgGame, guard: Any, strike: Any, ticks: int, on_tick: Callable | None = None,
                  on_start: Callable | None = None) -> dict:
    """``ticks`` ticks of every game, both teams scripted, from a fresh reset. Returns device counters (no host read
    inside the loop): games ended, Strike reaches among them, tags, upset games, non-finite drone-steps, filter-changed
    live drone-steps and live drone-steps. ``on_tick(k, out)`` (clips, the agreement check) is called after each tick,
    ``on_start()`` once after the reset."""
    obs = game.reset()
    if on_start is not None:
        on_start()
    every = torch.ones(game.num_games, dtype=torch.bool, device=game.device)
    guard.reset(every)
    strike.reset(every)
    zero = torch.zeros((), dtype=torch.long, device=game.device)
    c = {k: zero.clone() for k in ("ended", "reaches", "tags", "upset", "nonfinite", "filtered", "live")}
    for k in range(ticks):
        out = game.step({TEAMS[0]: guard.act(obs[TEAMS[0]]), TEAMS[1]: strike.act(obs[TEAMS[1]])})
        c["ended"] += out.done.sum()
        c["reaches"] += (out.done & (out.outcome == STRIKE_WIN)).sum()
        c["tags"] += out.info["tagged"].sum()
        c["upset"] += (out.done & out.info["upset"]).sum()
        c["nonfinite"] += out.info["nonfinite_actions"].sum()
        c["filtered"] += (out.info["filter_corrected"] & out.info["final_alive"]).sum()
        c["live"] += out.info["final_alive"].sum()
        guard.reset(out.done)
        strike.reset(out.done)
        obs = out.obs
        if on_tick is not None:
            on_tick(k, out)
    return c


def build_learner(gates: Gates, env: Any, device: str, seed: int):
    """skrl IPPO on ``env`` with the gate file's [trainer] (the T41 recipe, as ``scripts/train_standin.py`` builds it):
    per-drone networks, initial log std, zero-mean head, frozen log-std axes (gradient hook), RunningStandardScaler on
    observations and values. Refuses (ValueError) when skrl's effective settings differ from the file."""
    import copy

    from skrl.memories.torch import RandomMemory
    from skrl.multi_agents.torch.ippo import IPPO, IPPO_CFG
    from skrl.resources.preprocessors.torch import RunningStandardScaler
    from skrl.utils import set_seed

    from ..envs.skrl_adapter import skrl_kwargs_defaults
    from ..nus.pilot import zero_mean_head
    from ..opponents.learned import OBS_SPACE, make_models
    tr = gates.trainer
    set_seed(int(seed))
    names = env.possible_agents
    n = env.game.num_games
    rollouts = int(tr["rollouts"])
    models = make_models(names, list(tr["hidden"]), device)
    with torch.no_grad():
        for a in names:
            models[a]["policy"].log_std.fill_(float(tr["init_log_std"]))
    if tr["zero_mean_init"]:
        for a in names:
            zero_mean_head(models[a]["policy"])
    keep = torch.ones(len(ACTION_AXES), device=device)
    for axis in tr["frozen_log_std_axes"]:
        keep[ACTION_AXES[axis]] = 0.0
    for a in names:
        models[a]["policy"].log_std.register_hook(lambda g, k=keep: g * k)
    kw = skrl_kwargs_defaults(names)
    kw["observation_preprocessor_kwargs"] = {a: {"size": OBS_SPACE, "device": device} for a in names}
    kw["value_preprocessor_kwargs"] = {a: {"size": 1, "device": device} for a in names}
    cfg = IPPO_CFG(rollouts=rollouts, learning_epochs=int(tr["learning_epochs"]), mini_batches=int(tr["mini_batches"]),
                   learning_rate=float(tr["learning_rate"]), **{k: float(tr[k]) for k in SKRL_KEYS},
                   observation_preprocessor={a: RunningStandardScaler for a in names},
                   value_preprocessor={a: RunningStandardScaler for a in names},
                   experiment={"write_interval": 0, "checkpoint_interval": 0}, **kw)
    probe = copy.deepcopy(cfg)
    probe.expand(possible_agents=list(names))
    for k in SKRL_KEYS:
        v = getattr(probe, k)
        v = v.get(names[0]) if isinstance(v, dict) else v
        if not math.isclose(float(v), float(tr[k])):
            raise ValueError(f"skrl's effective {k} = {v!r} differs from the gate file's {tr[k]}")
    memories = {a: RandomMemory(memory_size=rollouts, num_envs=n, device=device) for a in names}
    agent = IPPO(possible_agents=names, models=models, memories=memories, observation_spaces=env.observation_spaces,
                 state_spaces=env.state_spaces, action_spaces=env.action_spaces, device=device, cfg=cfg)
    agent.init()
    return agent


def policy_snapshot(agent: Any) -> list[torch.Tensor]:
    return [p.detach().clone() for a in agent.policies for p in agent.policies[a].parameters()]


def learner_phase(agent: Any, env: Any, decisions: int, rollouts: int, device: str, timestep0: int = 0,
                  planned: int = 1) -> dict:
    """``decisions`` learner decisions with skrl's interaction loop (pre_interaction, act, env.step,
    record_transition, post_interaction); skrl runs a PPO update inside the post_interaction that closes each block of
    ``rollouts`` decisions. Returns rollout seconds (everything but the update calls), update seconds, updates run, the
    decisions and the device counters (games ended, reaches, non-finite drone-steps, upset games)."""
    obs, _ = env.reset()
    states = env.state()
    rollout_s = update_s = 0.0
    updates = 0
    zero = torch.zeros((), dtype=torch.long, device=device)
    ended, reaches, nonfinite, upset = zero.clone(), zero.clone(), zero.clone(), zero.clone()
    agent.enable_training_mode(True)
    total = max(planned, timestep0 + decisions)
    for i in range(decisions):
        t = timestep0 + i
        sync(device)
        t0 = time.perf_counter()
        agent.pre_interaction(timestep=t, timesteps=total)
        with torch.no_grad():
            actions, _ = agent.act(obs, states, timestep=t, timesteps=total)
            nxt, rew, term, trunc, info = env.step(actions)
            nxt_states = env.state()
            agent.record_transition(observations=obs, states=states, actions=actions, rewards=rew,
                                    next_observations=nxt, next_states=nxt_states, terminated=term, truncated=trunc,
                                    infos=info, timestep=t, timesteps=total)
        done = next(iter(term.values()))[:, 0]
        ended += done.sum()
        reaches += (done & (info["outcome"] == STRIKE_WIN)).sum()
        nonfinite += info["nonfinite_actions"].sum()
        upset += (done & info["upset"]).sum()
        sync(device)
        t1 = time.perf_counter()
        agent.post_interaction(timestep=t, timesteps=total)
        sync(device)
        t2 = time.perf_counter()
        rollout_s += t1 - t0
        if (t + 1) % rollouts == 0:
            update_s += t2 - t1
            updates += 1
        else:
            rollout_s += t2 - t1
        obs, states = nxt, nxt_states
    agent.enable_training_mode(False)
    return {"rollout_s": rollout_s, "update_s": update_s, "updates": updates, "decisions": decisions,
            "ended": ended, "reaches": reaches, "nonfinite": nonfinite, "upset": upset}


def gpu_memory(device: str) -> dict:
    """torch's peak allocated and reserved MiB on ``device`` (None on the CPU). PhysX's own buffers are not in these:
    the driver adds the process's nvidia-smi figure."""
    if torch.device(device).type != "cuda":
        return {"torch_peak_allocated_mib": None, "torch_peak_reserved_mib": None}
    return {"torch_peak_allocated_mib": torch.cuda.max_memory_allocated(device) / MIB,
            "torch_peak_reserved_mib": torch.cuda.max_memory_reserved(device) / MIB}


def rate(steps: int, seconds: float) -> float | None:
    return steps / seconds if seconds > 0 else None


def run_point(gates: Gates, point: Point, device: str, world_factory: Callable | None = None,
              torch_world_factory: Callable | None = None, clip_hook: Callable | None = None) -> dict:
    """Measure one point (module docstring). ``world_factory(n, m, params, device)`` makes the tier 2 world (Isaac Lab
    in the driver; the PyTorch reference world in the CPU tests); ``torch_world_factory`` the reference world of the
    agreement control (tier 2 ``agree_point`` only). ``clip_hook(game, cfg, point)`` (the driver's clips) runs after the
    timing, untimed. Returns the point's row (plain numbers: one host read per counter at the end)."""
    from ..core.physics_layer import load_game_physics_params
    from ..envs.skrl_adapter import SvgSkrlEnv
    from ..nus.pilot import DecisionHoldEnv
    t_start = time.perf_counter()
    tier2 = point.tier == max(TIERS)
    cfg = tier_cfg(gates, point.tier)
    seed = int(gates.run["seed"])
    g, s = parse_size(point.size)
    world = None
    if tier2:
        if world_factory is None:
            raise ValueError("a tier 2 point needs a world factory")
        world = world_factory(point.games, g + s, load_game_physics_params(cfg), device)
    game = make_game(cfg, point, device, seed, world)
    row: dict = {"id": point.id, "tier": point.tier, "size": point.size, "games": point.games, "drones": g + s,
                 "device": device, "motion": game.motion, "status": FIT, "controls": {}}
    if torch.device(device).type == "cuda":
        torch.cuda.reset_peak_memory_stats(device)
        row["gpu"] = torch.cuda.get_device_name(device)
    tr, tm = gates.trainer, gates.timing
    hold = int(tr["decision_ticks"])

    # ---- the agreement checks (tier 2 agree point): C-1a physics (gated), C-1b game (INFO); module section above
    row["info"] = {}
    if tier2 and point.id == gates.controls["agree_point"]:
        rec = record_physics_inputs(gates, cfg, point, device, seed, torch_world_factory)
        row["controls"]["physics_agreement"] = physics_agreement(gates, rec, world, load_game_physics_params(cfg), device,
                                                                 torch_world_factory)
        del rec
        row["info"]["game_agreement"] = game_agreement(gates, cfg, point, game, device, seed, torch_world_factory)

    # ---- 2. the scripted reference: both teams scripted, timed
    ref_ticks = int(tm["reference_decisions"]) * hold
    gs, ss = scripted(gates, TEAMS[0], cfg, point.games, device, seed), scripted(gates, TEAMS[1], cfg, point.games, device, seed)
    play_scripted(game, gs, ss, hold)                               # warm-up of the scripted path (not timed)
    sync(device)
    t0 = time.perf_counter()
    ref = play_scripted(game, gs, ss, ref_ticks)
    sync(device)
    ref_s = time.perf_counter() - t0

    # ---- 1. + 3. the learner in the loop
    team = gates.run["learner_team"]
    other = TEAMS[1] if team == TEAMS[0] else TEAMS[0]
    opp = scripted(gates, other, cfg, point.games, device, seed)
    env = DecisionHoldEnv(SvgSkrlEnv(game, train_teams=(team,), opponents={other: opp}), hold)
    agent = build_learner(gates, env, device, seed)
    rollouts, updates = int(tr["rollouts"]), int(tm["updates"])
    before = policy_snapshot(agent)
    warm = learner_phase(agent, env, int(tm["warmup_decisions"]), rollouts, device, planned=rollouts * updates)
    learn = learner_phase(agent, env, rollouts * updates, rollouts, device, timestep0=int(tm["warmup_decisions"]),
                          planned=rollouts * updates + int(tm["warmup_decisions"]))
    if warm["updates"]:
        raise ValueError("the warm-up decisions closed an update block: warmup_decisions must be below rollouts")
    after = policy_snapshot(agent)
    moved = any(not torch.equal(a, b) for a, b in zip(before, after))
    roll_steps = learn["decisions"] * hold * point.games
    sync(device)
    row.update({
        "reference": {"ticks": ref_ticks, "game_steps": ref_ticks * point.games, "seconds": ref_s,
                      "game_steps_per_s": rate(ref_ticks * point.games, ref_s),
                      **{k: int(v) for k, v in ref.items()},
                      "guard": gates.run["guard_script"], "strike": gates.run["strike_script"]},
        "learner": {"team": team, "opponent": gates.run[f"{other}_script"], "decisions": learn["decisions"],
                    "updates": learn["updates"], "game_steps": roll_steps, "rollout_s": learn["rollout_s"],
                    "update_s": learn["update_s"], "rollout_game_steps_per_s": rate(roll_steps, learn["rollout_s"]),
                    "train_game_steps_per_s": rate(roll_steps, learn["rollout_s"] + learn["update_s"]),
                    "update_s_each": learn["update_s"] / learn["updates"] if learn["updates"] else None,
                    "ended": int(learn["ended"]),
                    "nonfinite": int(learn["nonfinite"]) + int(warm["nonfinite"]),
                    "upset": int(learn["upset"]) + int(warm["upset"]), "policy_moved": moved,
                    "warmup_decisions": warm["decisions"]},
    })
    agree_ticks = row["info"]["game_agreement"]["ticks"] if "game_agreement" in row["info"] else 0
    row["game_steps_total"] = (warm["decisions"] * hold + hold + ref_ticks + agree_ticks) * point.games + roll_steps
    if point.id == gates.controls["learner_update_point"]:
        ok = learn["updates"] == updates and moved
        row["controls"]["learner_update"] = {"updates": learn["updates"], "expected_updates": updates,
                                             "policy_moved": moved, "pass": ok}
    row.update(gpu_memory(device))
    row["wall_s"] = time.perf_counter() - t_start
    if clip_hook is not None:
        row["clips"] = clip_hook(game, cfg, point)
    return row


# ================================================================================================ agreement (LEAD CALL 21 Nov 2026, QC L02-1, L02-R1)
# C-1a PHYSICS (gated): bare worlds, no game logic. Everything the game's PhysicsDrone did to its world in a scripted game
# on the PyTorch reference world is recorded in order: the restarts and the parking of out drones (``reset``: one world
# write per tick, partial masks), the setpoints (``step_setpoint``: the physics sub-steps) and the wall and height-band
# clamps (``write_clamped``: a partial ``write_state``). The same operations, same masks, same states, same order, are
# replayed through a fresh PhysicsDrone on the world under test and on a fresh reference world (T10's closed loop with
# the game's own writes), and every drone's position is compared after every tick, parked drones included.
# C-1b GAME (INFO): the same scripted game on both worlds; positions compared only for drones in the game in both, and
# only up to the first tick at which a drone is in the game in one world and out in the other.
_OPS = ("reset", "step_setpoint", "write_clamped")


def record_inputs(game: SvgGame, guard: Any, strike: Any, ticks: int) -> dict:
    """Play ``ticks`` ticks of a physics-backend game from a fresh reset and record, in order, every call the game made
    to its PhysicsDrone: ops = [(kind, tensors...)] with kind "reset" (mask [N, M], pos_m [N, M, 3], yaw [N, M]),
    "setpoint" (p_sp, v_ff, a_ff [N, M, 3], yaw_sp, yaw_rate [N, M]) or "clamp" (mask [N, M], pos_m, vel_mps [N, M, 3]),
    and "tick" after each tick; drone_pos [T, N, M, 3] = the drone's world positions after each tick (parked drones at
    the parking spot); noise_seed and estimator (its ``state_dict`` at the start of the recording) let the
    replays draw exactly the game's estimator noise."""
    layer = game._starling
    drone = getattr(layer, "drone", None)
    if drone is None:
        raise ValueError("record_inputs needs a game on the physics backend")
    ops: list = []
    label = {"reset": "reset", "step_setpoint": "setpoint", "write_clamped": "clamp"}

    def spy(name):
        inner = getattr(drone, name)

        def call(*args):
            ops.append((label[name], *(a.clone() for a in args)))
            return inner(*args)
        return call
    for name in _OPS:
        setattr(drone, name, spy(name))
    est = drone.estimator.state_dict()               # before the recorded reset: the replay restores it (L1.1b)
    try:
        obs = game.reset()
        every = torch.ones(game.num_games, dtype=torch.bool, device=game.device)
        guard.reset(every)
        strike.reset(every)
        drone_pos = []
        for _ in range(ticks):
            out = game.step({TEAMS[0]: guard.act(obs[TEAMS[0]]), TEAMS[1]: strike.act(obs[TEAMS[1]])})
            ops.append(("tick",))                    # restarts queued this tick are applied by the next tick's reset
            drone_pos.append(drone.pos_m.clone())
            guard.reset(out.done)
            strike.reset(out.done)
            obs = out.obs
    finally:
        for name in _OPS:
            delattr(drone, name)                     # the instance attributes only: the class methods are back
    n_set = sum(op[0] == "setpoint" for op in ops)
    if n_set != ticks:
        raise ValueError(f"recorded {n_set} setpoints for {ticks} ticks")
    return {"ops": ops, "drone_pos": torch.stack(drone_pos), "noise_seed": drone.noise_seed, "estimator": est}


def replay_positions(world: Any, params: Any, device: str, rec: dict) -> Tensor:
    """The recorded operations, in order, through a fresh PhysicsDrone on ``world`` (bare: no game), its estimator noise
    seeded with the recorded game's seed (``rec["noise_seed"]``) and restored to its state at the start of the recording
    (``rec["estimator"]``), so it reproduces the game with the estimator effect on. Returns the drone positions after
    each tick [T, N, M, 3]."""
    from ..models.physics_drone import PhysicsDrone
    drone = PhysicsDrone(world, params, device, noise_seed=rec.get("noise_seed", 0))   # the recorded game's seed (L1.1b)
    if "estimator" in rec:            # the game's drone had drawn more before the recording: restore its estimator
        drone.estimator.load_state_dict(rec["estimator"])
    act = {"reset": drone.reset, "setpoint": drone.step_setpoint, "clamp": drone.write_clamped}
    out = []
    for op in rec["ops"]:
        if op[0] == "tick":
            out.append(drone.pos_m.clone())
        else:
            act[op[0]](*op[1:])
    return torch.stack(out)


def replay_gap(rec: dict, world: Any, reference_world: Any, params: Any, device: str, limit_m: float) -> dict:
    """C-1a / C-3a: the largest 3-D position gap between the two bare replays, every game, drone and tick."""
    a = replay_positions(world, params, device, rec)
    b = replay_positions(reference_world, params, device, rec)
    gap = (a - b).norm(dim=-1)
    finite = bool(torch.isfinite(gap).all())
    worst = float(gap.max()) if finite else math.inf
    return {"games": int(gap.shape[1]), "drones": int(gap.shape[2]), "ticks": int(gap.shape[0]), "max_gap_m": worst,
            "limit_m": float(limit_m), "world": type(world).__name__, "reference_world": type(reference_world).__name__,
            "ops": len(rec["ops"]), "pass": finite and worst <= float(limit_m)}


def game_traces(game: SvgGame, guard: Any, strike: Any, ticks: int) -> dict:
    """A game played from a fresh reset: pos [T, N, M, 3] and alive [T, N, M] after each tick, alive meaning "in the
    game and still in the slot's first game" (from the step's own final_alive, before the auto-restart), and the
    game's counters."""
    pos, alive = [], []
    live = torch.ones(game.num_games, game.M, dtype=torch.bool, device=game.device)

    def tick(_k, out):
        nonlocal live
        live = live & out.info["final_alive"] & ~out.done[:, None]
        pos.append(game.pos_m.clone())
        alive.append(live.clone())
    c = play_scripted(game, guard, strike, ticks, on_tick=tick)
    return {"pos": torch.stack(pos), "alive": torch.stack(alive), "counters": {k: int(v) for k, v in c.items()}}


def compare_game_traces(pos_a: Tensor, alive_a: Tensor, pos_b: Tensor, alive_b: Tensor) -> dict:
    """C-1b / C-3b (INFO): first tick (1-based) at which a drone is in the game in one world and out in the other (None
    if never), how many drone-ticks differ so, and the largest 3-D gap over drones in the game in both worlds before
    that tick."""
    differ = alive_a != alive_b                                         # [T, N, M]
    per_tick = differ.flatten(1).any(dim=1)
    first = int(per_tick.nonzero()[0, 0]) if bool(per_tick.any()) else None
    upto = differ.shape[0] if first is None else first
    both = (alive_a & alive_b)[:upto]
    gap = (pos_a[:upto] - pos_b[:upto]).norm(dim=-1)
    gap = torch.where(both, gap, torch.zeros_like(gap))
    return {"first_divergence_tick": None if first is None else first + 1, "differing_alive_drone_ticks": int(differ.sum()),
            "max_gap_alive_before_divergence_m": float(gap.max()) if gap.numel() else 0.0, "ticks": int(differ.shape[0])}


def _reference_factory(factory: Callable | None) -> Callable:
    if factory is not None:
        return factory
    from ..models.rigid_body import TorchRigidBodyWorld
    return lambda n, m, params, device: TorchRigidBodyWorld(n, m, params.airframe, params.physics_dt_s, device)


def record_physics_inputs(gates: Gates, cfg: GameCfg, point: Point, device: str, seed: int,
                          factory: Callable | None) -> dict:
    """C-1a step 1: g* v s* on the reference world, ``agree_ticks`` ticks, the PhysicsDrone inputs recorded."""
    from ..core.physics_layer import load_game_physics_params
    params = load_game_physics_params(cfg)
    game = make_game(cfg, point, device, seed, _reference_factory(factory)(point.games, point.drones, params, device))
    return record_inputs(game, scripted(gates, TEAMS[0], cfg, point.games, device, seed),
                         scripted(gates, TEAMS[1], cfg, point.games, device, seed), int(gates.controls["agree_ticks"]))


def physics_agreement(gates: Gates, rec: dict, world: Any, params: Any, device: str, factory: Callable | None) -> dict:
    """C-1a step 2: the recorded inputs on ``world`` and on a fresh reference world; PASS at most ``agree_max_m``."""
    n, m = rec["drone_pos"].shape[1], rec["drone_pos"].shape[2]
    ref = _reference_factory(factory)(n, m, params, device)
    return replay_gap(rec, world, ref, params, device, float(gates.controls["agree_max_m"]))


def game_agreement(gates: Gates, cfg: GameCfg, point: Point, game: SvgGame, device: str, seed: int,
                   factory: Callable | None) -> dict:
    """C-1b (INFO): g* v s* on the point's game and on the same game on a reference world, ``agree_ticks`` ticks."""
    from ..core.physics_layer import load_game_physics_params
    params = load_game_physics_params(cfg)
    ref_game = make_game(cfg, point, device, seed, _reference_factory(factory)(point.games, point.drones, params, device))
    ticks = int(gates.controls["agree_ticks"])
    a = game_traces(game, scripted(gates, TEAMS[0], cfg, point.games, device, seed),
                    scripted(gates, TEAMS[1], cfg, point.games, device, seed), ticks)
    b = game_traces(ref_game, scripted(gates, TEAMS[0], cfg, point.games, device, seed),
                    scripted(gates, TEAMS[1], cfg, point.games, device, seed), ticks)
    out = compare_game_traces(a["pos"], a["alive"], b["pos"], b["alive"])
    out.update(world=a["counters"], reference=b["counters"], games=point.games, info="INFO, not gated (LEAD CALL QC L02-1)")
    return out


def failed_controls(row: dict) -> list[str]:
    return [name for name, c in row.get("controls", {}).items() if not c.get("pass", False)]



# ================================================================================================ clips (untimed)
def record_clips(gates: Gates, game: SvgGame, cfg: GameCfg, point: Point, device: str, seed: int) -> list:
    """STANDARDS section 8: the first ``[clips] games`` slots of the point's own game (either tier), both teams
    scripted (g* v s*), up to ``max_ticks`` ticks, recorded to the host every tick (untimed: after the measurement).
    Returns ``viz.replay.Recording`` objects of the slots whose first game ended; the last frame of a game is the tick
    before its end (the game restarts an ended game inside its step)."""
    import numpy as np

    from ..core.arena import BANDS
    from ..viz.replay import Recording
    c = gates.clips
    k, ticks = min(int(c["games"]), point.games), int(c["max_ticks"])
    g, s = parse_size(point.size)
    pos, alive = [], []
    first_end = torch.full((k,), -1, dtype=torch.long)
    outcome = torch.zeros(k, dtype=torch.long)
    closest = torch.full((k,), math.inf)

    def tick(i: int, out: Any) -> None:
        done = out.done[:k].cpu()
        new = done & (first_end < 0)
        first_end[new] = i + 1
        outcome[new] = out.outcome[:k].cpu().long()[new]
        live = first_end < 0
        closest[live | new] = torch.minimum(closest, out.info["closest_cross_m"][:k].cpu())[live | new]
        pos.append(game.pos_m[:k].cpu().numpy().copy())
        alive.append(game.alive[:k].cpu().numpy().copy())

    start: dict = {}

    def at_start() -> None:
        start["pos"], start["alive"] = game.pos_m[:k].cpu().numpy().copy(), game.alive[:k].cpu().numpy().copy()

    play_scripted(game, scripted(gates, TEAMS[0], cfg, point.games, device, seed),
                  scripted(gates, TEAMS[1], cfg, point.games, device, seed), ticks, on_tick=tick, on_start=at_start)
    start_pos, start_alive = start["pos"], start["alive"]
    ar = game.arenas
    centre, rad, half = ar.zone_centre_m[:k].cpu().numpy(), ar.zone_radius_m[:k].cpu().numpy(), ar.half_m[:k].cpu().numpy()
    band = ar.band[:k].cpu().numpy()
    pos_a = np.concatenate([start_pos[None], np.stack(pos)]) if pos else start_pos[None]
    alive_a = np.concatenate([start_alive[None], np.stack(alive)]) if alive else start_alive[None]
    recs = []
    for i in range(k):                                   # k clip slots: a fixed count, not the games of the run
        t = int(first_end[i])
        if t < 0:
            continue
        pi, ai = pos_a[:t, i].copy(), alive_a[:t, i].copy()     # frames 0..t-1: the game's last tick is not shown
        for m in range(pi.shape[1]):
            last = pi[0, m]
            for f in range(pi.shape[0]):
                if ai[f, m]:
                    last = pi[f, m]
                else:
                    pi[f, m] = last
        recs.append(Recording(pi, ai, centre[i], float(rad[i]), float(half[i]), int(outcome[i]), pi.shape[0] - 1, g, s,
                              BANDS[int(band[i])], f"Starling layer, {game.motion}", gates.run["guard_script"],
                              gates.run["strike_script"], seed, i, float(closest[i])))
    return recs
