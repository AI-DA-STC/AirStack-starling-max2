"""STE task L0.13 Does tier 2 train at all? (PLAN.md section 4 row L0.13; LEAD CALL 21 Nov 2026): the gate file, the
two tiers of the L0.11 base game, the view of an Isaac world used for evaluations, the physics agreement check, and the
verdict arithmetic. The driver is ``scripts/ste_tier2_l013.py``; the trainer is L0.12's (``ste/exploit_train.py``).

**What L0.13 measures.** The L0.12 Guard run's recipe (the T41 recipe, one decision per 0.6 s) trains an exploiter
Guard team against ``strike_straight`` in the L0.11 base game (tag 1.6 m, 3v3) twice, with the SAME games at once, the
SAME game-steps, the SAME training seed and the SAME procedure: arm ``t1`` on tier 1 (the fitted Starling response) and
arm ``t2`` on tier 2 (the same game file with ``starling_layer.backend = "physics"``: the Isaac Lab rigid-body Starling).
The gate (written before any run): tier 2 "trains" if the t2 Guard's final hold rate on tier 2 (T44's first 1,000 starts)
has a Wilson 95 % lower bound above the parked Guard's (``guard_parked_centre``, same batch, tier 2) upper bound
(:func:`trains_bar`); the verdict (:func:`tier2_verdict`) is PASS, FAIL or TOO_SLOW (the arm reached its cap reserve
before its game-step budget: a result, pre-registered).

**One world per process.** An Isaac world is n games x m drones for its whole process, and ``PhysicsLayer`` needs a
world of exactly its game's size. The t2 arm builds ONE world of the training size and plays every tier 2 evaluation
on :class:`SliceWorld`, a view of its first k games; the other games are parked level, at rest, holding a hover force,
and are not counted. An evaluation therefore overwrites the training games' physics state: after each evaluation the
training games restart afresh (``SvgSkrlEnv.reset``), and the t1 arm does the same after its own evaluations so that the
two arms run one procedure.

**Physics agreement (control C-1a, L0.2's check, copied here because ``ste/speed.py`` lives on another branch).** A
scripted game on the PyTorch reference world records, in order, every call the game made to its drone model (the
restarts and parking writes, the PX4 cascade copy's setpoints, the wall and height-band clamps); the same calls are
replayed on the world under test and on a fresh reference world, and the largest 3-D gap over every game, drone and tick
must stay within the gate's limit (T10's 0.02 m).

Shapes: N games, M = G + S drones (Guard drones first); vectors [N, M, 3], masks [N, M]. Standard library, NumPy and
PyTorch only (Isaac Lab stays in ``compat/``; the driver builds the Isaac world). No tuned number lives here
(tests/test_ste_literals.py): every count and limit comes from the gate file ``configs/ste_l013/gates.toml``.
Observed in the training simulator; nothing here is a flight result."""
from __future__ import annotations

import dataclasses
import hashlib
import math
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import torch
from torch import Tensor

from ..core.game_config import GameCfg, load_game_cfg
from ..core.metrics import wilson_interval
from ..opponents.scripted import REGISTRY
from . import exploit, sweep

ROOT = sweep.ROOT
GATES_FILE = ROOT / "configs" / "ste_l013" / "gates.toml"
SMOKE_GATES_FILE = ROOT / "configs" / "ste_l013" / "smoke_gates.toml"
ARMS = ("t1", "t2")                   # the run order: t2 scores t1's networks on tier 2, so t1 runs first
TIERS = {"t1": 1, "t2": 2}
TIER2_SETTING = "starling.backend"    # the one setting tier 2 changes (C-0)
PHYSICS_BACKEND = "physics"
EXPLOITER = exploit.EXPLOITER         # the arm's own networks in a cell
PEER = "t1_same_update"               # the t1 arm's networks at the t2 arm's update (t2 arm only, INFO)
PASS_WORD, FAIL_WORD, TOO_SLOW = "PASS", "FAIL", "TOO_SLOW"
QUAT_ONE = (1.0, 0.0, 0.0, 0.0)       # level, nose east (WXYZ)
SNAPSHOT_KEYS = ("policy", "observation_preprocessor")   # what a snapshot keeps of each agent (exploit_train)
HOUR_S = 3600.0
PEER_BATCH_CELLS = 3                  # the largest evaluation batch: the arm's Guard, the parked Guard, the t1 peer

_SECTIONS = {
    "run": {"task", "kind", "device", "size", "game_file", "game_sha256", "side", "opponent", "parked", "eval_games",
            "ticks_cap", "curve_seed", "curve_games", "clip_seed", "train_seed", "cap_check_every_ticks", "cap_h_total"},
    "reference": {"file", "sha256", "start_sha256", "t44_gates_sha256", "t44_record", "t44_run", "variant"},
    "l012": {"gates_sha256", "record", "base_guard_holds", "base_guard_games", "base_guard_game_steps", "run"},
    "arms": {"order", "t1", "t2"},
    "trainer": {"algorithm", "decision_ticks", "num_games", "game_steps_per_run", "rollouts", "learning_epochs",
                "mini_batches", "learning_rate", "hidden", "init_log_std", "frozen_log_std_axes", "zero_mean_init",
                "discount_factor", "gae_lambda", "entropy_loss_scale", "value_loss_scale", "ratio_clip", "value_clip",
                "grad_norm_clip", "shaping_weight", "checkpoint_every_updates", "curve_every_updates",
                "final_reserve_factor", "final_batch_units", "clip_reserve_s", "room_factor"},
    "controls": {"stop_on_fail", "replay_count_tol_cuda_games", "replay_differ_tol_cuda_games", "agree_guard",
                 "agree_strike", "agree_ticks", "agree_max_m", "tier_difference"},
    "verdict": {"rule", "budget_rule"},
    "videos": {"games", "keep", "max_ticks", "speed", "fps", "dpi"},
}
_ARM_KEYS = {"tier", "cap_h", "final_reserve_s"}
VERDICT_RULE = "trained_low_above_parked_high"
BUDGET_RULE = "cap_reserve_before_budget_is_too_slow"


@dataclass(frozen=True)
class Tier2Gates:
    """The gate file as loaded (``sha256`` of its bytes). ``arms``: {"t1": {tier, cap_h, final_reserve_s}, "t2": ...}."""
    path: str
    sha256: str
    run: dict
    reference: dict
    l012: dict
    arms: dict
    trainer: dict
    controls: dict
    verdict: dict
    videos: dict
    # STE L3 slice 3 (step 5): optional tables, absent in the L0.13 files of record (which load unchanged)
    players: dict | None = None
    learner: Any = dataclasses.field(default_factory=lambda: exploit.skills.learner_spec(None))
    pool: dict = dataclasses.field(default_factory=lambda: {"enabled": False})

    @property
    def per_update(self) -> int:
        """Game-steps of one update: rollouts decisions x decision ticks x games at once."""
        tr = self.trainer
        return int(tr["rollouts"]) * int(tr["decision_ticks"]) * int(tr["num_games"])

    @property
    def planned_updates(self) -> int:
        """Updates that reach the budget (the last one may pass it): the same count in both arms."""
        return max(1, math.ceil(int(self.trainer["game_steps_per_run"]) / self.per_update))

    @property
    def planned_game_steps(self) -> int:
        return self.planned_updates * self.per_update


def _exact(table: Any, keys: set[str], where: str) -> dict:
    if not isinstance(table, dict):
        raise ValueError(f"[{where}] must be a table")
    unknown, missing = sorted(set(table) - keys), sorted(keys - set(table))
    if unknown:
        raise ValueError(f"unknown key(s) in [{where}]: {unknown}")
    if missing:
        raise ValueError(f"missing key(s) in [{where}]: {missing}")
    return table


def load_gates(path: str | Path = GATES_FILE) -> Tier2Gates:
    """Load and check the gate file; ValueError names the first problem (an unknown or missing key, an arm order other
    than t1 then t2, a player that is not a script, an evaluation batch larger than the training world, the job cap
    below the arms' caps)."""
    path = Path(path)
    raw = path.read_bytes()
    data = tomllib.loads(raw.decode())
    unknown = sorted(set(data) - set(_SECTIONS) - {"learner", "players", "pool"})
    if unknown:
        raise ValueError(f"unknown section(s) in {path.name}: {unknown}")
    # STE L3: an optional [learner] table. Slice 3 (step 5) wires choice = "two_level" into the Guard-side L0.13 arms;
    # slice 1's flat modes are still refused here (velocity, or no table: as before)
    learner = exploit.skills.learner_spec(data.get("learner"))
    if learner.skills and learner.choice != exploit.skills.TWO_LEVEL:
        exploit.skills.require_velocity_learner(learner, "ste/tier2_train.py (scripts/ste_tier2_l013.py)")
    parts = {name: _exact(data.get(name), keys, name) for name, keys in _SECTIONS.items()}
    arms = parts["arms"]
    if list(arms["order"]) != list(ARMS):
        raise ValueError(f"arms.order must be {list(ARMS)} (t2 scores t1's networks on tier 2)")
    for arm in ARMS:
        _exact(arms[arm], _ARM_KEYS, f"arms.{arm}")
        if int(arms[arm]["tier"]) != TIERS[arm]:
            raise ValueError(f"arms.{arm}.tier must be {TIERS[arm]}")
        if not float(arms[arm]["cap_h"]) * HOUR_S > float(arms[arm]["final_reserve_s"]):
            raise ValueError(f"arms.{arm}: cap_h leaves no training time above final_reserve_s")
    run, tr, c, v = parts["run"], parts["trainer"], parts["controls"], parts["verdict"]
    if run["side"] != "guard":
        raise ValueError("run.side must be guard (L0.13 trains the Guard team; LEAD CALL 21 Nov 2026)")
    for name, team in ((run["opponent"], "strike"), (run["parked"], "guard"), (c["agree_guard"], "guard"),
                       (c["agree_strike"], "strike")):
        if name not in REGISTRY or not name.startswith(team):
            raise ValueError(f"{name!r} must be a scripted {team} player")
    n = int(tr["num_games"])
    for what, k in (("3 x run.eval_games (the final tier 2 batch)", PEER_BATCH_CELLS * int(run["eval_games"])),
                    ("run.curve_games", int(run["curve_games"])), ("videos.games", int(parts["videos"]["games"]))):
        if k > n:
            raise ValueError(f"{what} = {k} exceeds trainer.num_games {n}: an evaluation plays on a view of the "
                             "training world")
    if int(tr["game_steps_per_run"]) <= 0:
        raise ValueError("trainer.game_steps_per_run must be above 0")
    if float(run["cap_h_total"]) < sum(float(arms[a]["cap_h"]) for a in ARMS):
        raise ValueError("run.cap_h_total must cover both arms' caps")
    if v["rule"] != VERDICT_RULE or v["budget_rule"] != BUDGET_RULE:
        raise ValueError(f"verdict.rule must be {VERDICT_RULE!r} and verdict.budget_rule {BUDGET_RULE!r}")
    if list(c["tier_difference"]) != [TIER2_SETTING]:
        raise ValueError(f"controls.tier_difference must be [{TIER2_SETTING!r}]")
    sweep.parse_size(run["size"])
    if len({int(run["train_seed"]), int(run["curve_seed"]), int(run["clip_seed"])}) != len(("train", "curve", "clip")):
        raise ValueError("run.train_seed, curve_seed and clip_seed must differ")
    players, pool = _skills_tables(data, learner, parts)
    return Tier2Gates(path=str(path), sha256=hashlib.sha256(raw).hexdigest(), players=players, learner=learner,
                      pool=pool, **parts)


def _skills_tables(data: dict, learner, parts: dict) -> tuple[dict | None, dict]:
    """STE L3 slice 3 (step 5): the optional ``[players]`` and ``[pool]`` and the two-level route's checks. ValueError
    names the first problem: a two-level ``[learner]`` without ``[players]``; ``[players]`` other than the tier-1 gate
    file's (the L0.12 file this gate pins, ``[l012] gates_sha256``); the lists against ``[players]``
    (``skills.check_two_level``); ``[run] parked`` other than the first Guard drone skill (the untrained team's known
    answer: it plays free + that skill, the parked cell); an enabled ``[pool]`` (not wired into the L0.13 arms)."""
    players = data.get("players")
    if players is not None:
        _exact(players, {"guards", "strikes"}, "players")
        bad = [p for team in ("guards", "strikes") for p in players[team] if p not in REGISTRY]
        if bad:
            raise ValueError(f"players: unknown player(s) {bad}")
        tier1 = exploit.GATES_FILE
        if exploit.sha256_file(tier1) != parts["l012"]["gates_sha256"]:
            raise ValueError(f"players: the tier-1 gate file {tier1} is not the one [l012] gates_sha256 pins")
        want = exploit.load_gates(tier1).players
        if any(list(players[t]) != list(want[t]) for t in ("guards", "strikes")):
            raise ValueError("players: the lists must equal the tier 1 gate file's [players] (the same skills)")
    if learner.skills:
        if players is None:
            raise ValueError("a two-level [learner] needs [players] (the lists of the skills)")
        exploit.skills.check_two_level(learner, players)
        if learner.drone_skills["guard"][0] != parts["run"]["parked"]:
            raise ValueError(f"run.parked {parts['run']['parked']!r} must be the first Guard drone skill "
                             f"{learner.drone_skills['guard'][0]!r}: the untrained two-level team plays free + that "
                             f"skill, and the control compares it with the parked cell")
    table = data.get("pool")
    if table is None:
        return players, {"enabled": False}
    _exact(table, {"enabled", "seed"}, "pool")
    if not isinstance(table["enabled"], bool) or isinstance(table["seed"], bool) or not isinstance(table["seed"], int):
        raise ValueError("pool: enabled true or false, seed an int")
    if table["enabled"]:
        raise ValueError("pool.enabled: the opponent pool is not wired into the L0.13 arms (they train against "
                         "run.opponent)")
    return players, {"enabled": False, "seed": table["seed"]}


def sha256_file(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pin_problems(gates: Tier2Gates, root: Path = ROOT) -> list[str]:
    """One line per pinned file that is missing or changed: the game file and T44's reference file (and its starts)."""
    out = []
    for key, rel in (("game_sha256", gates.run["game_file"]), ("sha256", gates.reference["file"])):
        f = root / rel
        want = gates.run[key] if key == "game_sha256" else gates.reference[key]
        if not f.is_file():
            out.append(f"{rel} is missing")
        elif sha256_file(f) != want:
            out.append(f"{rel} has sha256 {sha256_file(f)}, the gate file pins {want}")
    if not out:
        ref = exploit.load_reference(root / gates.reference["file"])
        if ref.start_sha256 != gates.reference["start_sha256"]:
            out.append(f"the reference starts have sha256 {ref.start_sha256}, the gate file pins "
                       f"{gates.reference['start_sha256']}")
        if int(ref.meta["seed"]) in (int(gates.run["train_seed"]), int(gates.run["curve_seed"]), int(gates.run["clip_seed"])):
            out.append(f"a seed of the gate file is the scoring starts' seed {ref.meta['seed']}")
        if gates.reference["variant"] not in ref.meta["variants"]:
            out.append(f"the reference has no variant {gates.reference['variant']!r}")
    return out


# ================================================================================================ the two tiers
def tier_cfg(gates: Tier2Gates, tier: int, root: Path = ROOT) -> GameCfg:
    """The game of a tier: the base game file as committed (tier 1), or the same with the physics backend (tier 2).
    Loaded with use_local=False (a partner's local file never changes it); the file itself is never edited."""
    cfg, _ = load_game_cfg(root / gates.run["game_file"], local_dir=None, use_local=False)
    if tier == TIERS["t2"]:
        cfg = cfg.replace(**{TIER2_SETTING: PHYSICS_BACKEND})
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


def torch_world_factory(n: int, m: int, params, device: str):
    """The PyTorch reference rigid-body world (the agreement check's reference; tier 2 in the CPU tests)."""
    from ..models.rigid_body import TorchRigidBodyWorld
    return TorchRigidBodyWorld(n, m, params.airframe, params.physics_dt_s, device)


# ================================================================================================ the view of a world
class SliceWorld:
    """The first ``k`` games of a rigid-body world of N >= k games: the ``models/rigid_body.RigidBodyWorld`` protocol
    for k x M bodies, so a game of k games can play in a world built for N (one Isaac world per process).

    At construction the other N - k games' drones are written level (``QUAT_ONE``), at rest, where they are, and from
    then on hold a hover force (m g up, body frame = world frame for a level body) and no torque: parked, never
    counted. Every write is padded to N x M (masks False outside the view) and is ONE batched write of the full world,
    as the world's own contract asks; ``state()`` returns clones of the first k games. mass_kg: the airframe's mass."""

    def __init__(self, world: Any, k: int, mass_kg: float):
        if not 0 < int(k) <= int(world.num_games):
            raise ValueError(f"a view of {k} games of a world of {world.num_games}")
        self.world, self.num_games, self.drones = world, int(k), int(world.drones)
        self.dt_s, self.device = world.dt_s, world.device
        self.label = f"{world.label}[:{self.num_games}]"
        from ..models.physics_params import G_MPS2
        n, m = int(world.num_games), self.drones
        pos, _quat, lin, ang = world.state()
        self._idle = (torch.arange(n, device=pos.device) >= self.num_games)[:, None].expand(n, m)
        level = torch.tensor(QUAT_ONE, dtype=pos.dtype, device=pos.device).expand(n, m, len(QUAT_ONE))
        if bool(self._idle.any()):
            world.write_state(self._idle, pos.clone(), level.contiguous(), torch.zeros_like(lin), torch.zeros_like(ang))
        hover = torch.zeros(n, m, len(("x", "y", "z")), dtype=pos.dtype, device=pos.device)
        hover[..., -1] = float(mass_kg) * G_MPS2
        self._hover = torch.where(self._idle[..., None], hover, torch.zeros_like(hover))
        world.apply_wrench_b(self._hover, torch.zeros_like(self._hover))

    def _pad(self, x: Tensor, full: Tensor) -> Tensor:
        """x [k, M, ...] -> [N, M, ...]: x on the view, ``full`` (the world's own values) elsewhere."""
        return torch.cat((x.to(full.dtype), full[self.num_games:]), dim=0)

    def _mask(self, mask: Tensor) -> Tensor:
        return torch.cat((mask, torch.zeros_like(self._idle[self.num_games:])), dim=0)

    def reset(self, mask: Tensor, pos_m: Tensor, quat_wxyz: Tensor) -> None:
        pos, quat, _lin, _ang = self.world.state()
        self.world.reset(self._mask(mask), self._pad(pos_m, pos), self._pad(quat_wxyz, quat))

    def write_state(self, mask: Tensor, pos_m: Tensor, quat_wxyz: Tensor, lin_vel_mps: Tensor,
                    ang_vel_b_rad_s: Tensor) -> None:
        pos, quat, lin, ang = self.world.state()
        self.world.write_state(self._mask(mask), self._pad(pos_m, pos), self._pad(quat_wxyz, quat),
                               self._pad(lin_vel_mps, lin), self._pad(ang_vel_b_rad_s, ang))

    def apply_wrench_b(self, force_b: Tensor, torque_b: Tensor) -> None:
        self.world.apply_wrench_b(self._pad(force_b, self._hover), self._pad(torque_b, torch.zeros_like(self._hover)))

    def step(self) -> None:
        self.world.step()

    def state(self) -> tuple[Tensor, Tensor, Tensor, Tensor]:
        return tuple(t[:self.num_games].clone() for t in self.world.state())


def view(world: Any, k: int, params: Any) -> Any:
    """A world of exactly k games: ``world`` itself when it holds k games, else its :class:`SliceWorld`."""
    return world if int(world.num_games) == int(k) else SliceWorld(world, k, params.airframe.mass_kg)


# ================================================================================================ C-1a physics agreement
# Copied from L0.2 (branch ste-l0.2, ste/speed.py record_inputs / replay_positions / replay_gap; LEAD CALL 21 Nov 2026
# QC L02-1, L02-R1), kept under another name until that branch merges.
_OPS = ("reset", "step_setpoint", "write_clamped")


def record_inputs(game: Any, guard: Any, strike: Any, ticks: int) -> dict:
    """Play ``ticks`` ticks of a physics-backend game from a fresh reset and record, in order, every call the game made
    to its PhysicsDrone: ops = [(kind, tensors...)] with kind "reset" (mask [N, M], pos_m [N, M, 3], yaw [N, M]),
    "setpoint" (p_sp, v_ff, a_ff [N, M, 3], yaw_sp, yaw_rate [N, M]) or "clamp" (mask [N, M], pos_m, vel_mps [N, M, 3]),
    and "tick" after each tick; noise_seed and estimator (its ``state_dict`` at the start of the recording) let the
    replays draw exactly the game's estimator noise."""
    drone = getattr(game._starling, "drone", None)
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
        for _ in range(ticks):
            out = game.step({"guard": guard.act(obs["guard"]), "strike": strike.act(obs["strike"])})
            ops.append(("tick",))
            guard.reset(out.done)
            strike.reset(out.done)
            obs = out.obs
    finally:
        for name in _OPS:
            delattr(drone, name)                     # the instance attributes only: the class methods are back
    n_set = sum(op[0] == "setpoint" for op in ops)
    if n_set != ticks:
        raise ValueError(f"recorded {n_set} setpoints for {ticks} ticks")
    return {"ops": ops, "noise_seed": drone.noise_seed, "estimator": est}


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
    """The largest 3-D position gap between the two bare replays, every game, drone and tick; PASS within limit_m."""
    a = replay_positions(world, params, device, rec)
    b = replay_positions(reference_world, params, device, rec)
    gap = (a - b).norm(dim=-1)
    finite = bool(torch.isfinite(gap).all())
    worst = float(gap.max()) if finite else math.inf
    return {"games": int(gap.shape[1]), "drones": int(gap.shape[2]), "ticks": int(gap.shape[0]), "max_gap_m": worst,
            "limit_m": float(limit_m), "world": getattr(world, "label", type(world).__name__),
            "reference_world": type(reference_world).__name__, "ops": len(rec["ops"]),
            "pass": finite and worst <= float(limit_m)}


def physics_agreement(gates: Tier2Gates, cfg: GameCfg, world: Any, device: str,
                      factory: Callable = torch_world_factory) -> dict:
    """C-1a on ``world`` (k games, the training world or a view): the gate's agree_guard v agree_strike on a reference
    world of k games for agree_ticks ticks, recorded, then replayed bare on ``world`` and on a fresh reference world."""
    from ..core.game import SvgGame
    from ..core.physics_layer import load_game_physics_params
    from ..opponents.scripted import make_strategy
    c, k = gates.controls, int(world.num_games)
    params = load_game_physics_params(cfg)
    g, s = sweep.parse_size(gates.run["size"])
    seed = int(gates.run["train_seed"])
    game = SvgGame(cfg, k, g, s, device=device, seed=seed, band=0, world=factory(k, g + s, params, device))
    rec = record_inputs(game, make_strategy(c["agree_guard"], "guard", cfg, k, device, seed + sweep.GUARD_SEED_OFFSET),
                        make_strategy(c["agree_strike"], "strike", cfg, k, device, seed + sweep.STRIKE_SEED_OFFSET),
                        int(c["agree_ticks"]))
    del game
    out = replay_gap(rec, world, factory(k, g + s, params, device), params, device, float(c["agree_max_m"]))
    del rec
    return out


def batch_tier(pg: dict) -> int:
    """The tier a played batch ran on, from the drone model it reports (``exploit.play_cells`` "motion"): 2 for the
    physics drone, 1 otherwise (QC T2: a tier 2 number must come from a physics-backend batch)."""
    return TIERS["t2"] if str(pg["motion"]).startswith(PHYSICS_BACKEND + "/") else TIERS["t1"]


# ================================================================================================ budget and time
def final_reserve_s(gates: Tier2Gates, arm: str, batch_s: float) -> float:
    """Effective seconds kept back for an arm's final phase: final_reserve_factor x (final_batch_units x the arm's own
    controls batches' seconds + clip_reserve_s), never less than the arm's final_reserve_s (L0.12's rule, QC I-3; the
    floor covers a batch that runs long: L0.12 lesson)."""
    tr = gates.trainer
    measured = float(tr["final_reserve_factor"]) * (float(tr["final_batch_units"]) * float(batch_s)
                                                     + float(tr["clip_reserve_s"]))
    return max(float(gates.arms[arm]["final_reserve_s"]), measured)


def room_needed_s(gates: Tier2Gates, reserve_s: float, update_s: float | None, curve_s: float | None,
                  curve_due: bool) -> float:
    """Effective seconds that must be left before the next update starts: the reserve, plus room_factor x (the last
    update's seconds and, when the next update ends on a curve read, the last read's seconds). Before any update has
    been timed: the reserve alone."""
    f = float(gates.trainer["room_factor"])
    extra = (update_s or 0.0) + ((curve_s or 0.0) if curve_due else 0.0)
    return float(reserve_s) + f * extra


def projection(gates: Tier2Gates, arm: str, pre_s: float, update_s: float, curve_s: float, batch_s: float) -> dict:
    """Whether an arm of ``gates`` reaches its budget at the measured times (QC C1): training goes on while the cap left
    covers the reserve plus room_factor x (the next update and its read), so the last of P updates (with its read)
    starts only if pre + (P - 1) U + (R - 1) C + reserve + f (U + C) <= cap, i.e. with f = 1.5,
    pre + (P + 0.5) U + (R + 0.5) C <= cap - reserve (R reads; QC's pre + 48.5 U + 8.5 C <= 7,500 s for t2). pre: the
    effective seconds before the first update; U, C: seconds of one update and one curve read; batch_s: the controls
    batches (the reserve's unit). Also the break-even training rate (game-steps per second) at that pre and C."""
    f = float(gates.trainer["room_factor"])
    p = gates.planned_updates
    r = sum(1 for u in range(1, p + 1) if curve_due(gates, u))
    reserve = final_reserve_s(gates, arm, batch_s)
    available = float(gates.arms[arm]["cap_h"]) * HOUR_S - reserve
    need = float(pre_s) + (p - 1 + f) * float(update_s) + (r - 1 + f) * float(curve_s)
    room = available - float(pre_s) - (r - 1 + f) * float(curve_s)
    u_max = room / (p - 1 + f)
    return {"updates": p, "reads": r, "pre_s": float(pre_s), "update_s": float(update_s), "curve_s": float(curve_s),
            "reserve_s": reserve, "need_s": need, "available_s": available, "margin_s": available - need,
            "break_even_game_steps_per_s": gates.per_update / u_max if u_max > 0 else math.inf}


def curve_due(gates: Tier2Gates, update: int) -> bool:
    """A learning-curve read follows update ``update`` (every curve_every_updates, and the budget's last update)."""
    every = int(gates.trainer["curve_every_updates"])
    return update % every == 0 or update == gates.planned_updates


# ================================================================================================ the verdict
def rate(k: int, n: int) -> dict:
    lo, hi = wilson_interval(int(k), int(n))
    return {"k": int(k), "n": int(n), "rate": k / n if n else float("nan"), "ci": [lo, hi]}


def trains_bar(trained: tuple[int, int], parked: tuple[int, int]) -> dict:
    """The gate's bar (``VERDICT_RULE``): the trained Guard's hold Wilson lower bound above the parked Guard's upper."""
    t, p = rate(*trained), rate(*parked)
    return {"trained": t, "parked": p, "cleared": bool(t["n"] > 0 and p["n"] > 0 and t["ci"][0] > p["ci"][1])}


def tier2_verdict(trained: tuple[int, int], parked: tuple[int, int], budget_reached: bool, game_steps: int,
                  t1_bar_cleared: bool | None = None, t1_budget_reached: bool = True) -> dict:
    """PASS: the t2 arm reached its budget and its final Guard clears the bar on tier 2; FAIL: budget reached, bar not
    cleared; TOO_SLOW: the arm stopped at its cap reserve before its budget (``BUDGET_RULE``; the bar at the game-steps
    reached is reported, ``bar_at_steps_reached``). ``reading`` (wording, pre-registered): a FAIL whose tier 1 control
    did not clear its own bar either AT ITS FULL BUDGET says the budget, not the tier, is what was short (QC D3: a tier 1
    control that stopped early says nothing about the budget)."""
    bar = trains_bar(trained, parked)
    if not budget_reached:
        word = TOO_SLOW
    else:
        word = PASS_WORD if bar["cleared"] else FAIL_WORD
    reading = None
    if word == FAIL_WORD and t1_bar_cleared is False and not t1_budget_reached:
        reading = ("FAIL with the tier 1 control below its own bar but stopped before its budget: the control does not "
                   "say whether the budget or the tier was short")
    elif word == FAIL_WORD and t1_bar_cleared is False:
        reading = ("FAIL with the tier 1 control below its own bar too: the recipe did not learn at this budget on "
                   "either tier; this does not single out tier 2")
    elif word == FAIL_WORD and t1_bar_cleared:
        reading = "FAIL while the tier 1 control cleared its bar: tier 2 did not train at the budget tier 1 trained at"
    elif word == TOO_SLOW:
        reading = (f"TOO_SLOW: the arm stopped at its cap reserve at {game_steps:,} game-steps; the bar at the steps "
                   f"reached was {'cleared' if bar['cleared'] else 'not cleared'} (INFO)")
    return {"verdict": word, "bar": bar, "budget_reached": bool(budget_reached), "game_steps": int(game_steps),
            "bar_at_steps_reached": bar["cleared"], "reading": reading}


def snapshot(modules: dict) -> dict:
    """What a learning-curve snapshot keeps of ``Learner.modules()`` (or ``Learner.saved()``): each agent's policy and
    observation scaler (enough for ``exploit_train.team_from_modules``); the skills route (``{"skills", "modules"}``,
    L3 slice 3): the same, with the skill lists kept beside them (for ``skill_team_from_modules``)."""
    if set(modules) == {"skills", "modules"}:
        return {"skills": modules["skills"], "modules": snapshot(modules["modules"])}
    return {a: {k: v for k, v in m.items() if k in SNAPSHOT_KEYS} for a, m in modules.items()}
