"""STE task L0.3 STE Guard policy in tier 2 without retraining (INFO; PLAN.md section 4, DISCUSSION P3): the parts
``scripts/ste_transfer_l03.py`` plays and tests.

T41 (the STE Guard policy, ``runs/nus_port/phase5/pilots/2026-11-19_nus_phase5_pilot_p1b_run4``) was trained and scored
in the hangar game of Phase 4 row 5 (fitted Starling response, tier 1). Its tier 2 game is Phase 4 row 6: the same row
with ``drone = "physics"`` (configs/nus_phase4.toml: ``changed = ["drone"]``), the game T24 played. Both games are built
here the way ``nus/pilot.py`` builds T41's evaluation game (``pilot_world``, ``pilot_games``: the first Phase 4 paired
starts, the evaluation seed, the kept video slots), the second with the physics backend and a world. T41 plays as
``HeldStrategy(SkrlPolicyStrategy(run, mean actions), decision_ticks)`` (one decision per 12 ticks) against S20 with
T41's opponent seed. The parked control plays through T24's own path (``nus/ladder.play_game_pair``, ParkedGuard v S20,
the ladder seed).

Shapes: N games (the paired starts), M = 6 drones (3 Guard, then 3 Strike); per-game arrays [N]. No numeric literal other
than 0, 1, -1, 2 outside UPPER_CASE module constants: every count, seed and limit comes from ``configs/ste_l03/gates.toml``.
Observed in the training simulator; nothing here is a flight result."""
from __future__ import annotations

import dataclasses
import hashlib
import math
import tomllib
from pathlib import Path
from typing import Any, Callable

import numpy as np
import torch

from ..core.metrics import wilson_interval
from ..core.rewards import GUARD_WIN, RUNNING, STRIKE_WIN
from . import shared
from .speed import cfg_differences

ROOT = shared.PACKAGE_DIR.parents[2]
GATES_FILE = ROOT / "configs" / "ste_l03" / "gates.toml"
HALF = 0.5                                   # the sign test's null probability
PER_GAME = ("outcome", "end_step", "closest_cross_m", "closest_cross_3d_m", "rule_breach", "filter_corrected_rate",
            "nonfinite_actions", "upset", "start_miss")
_SECTIONS = {
    "run": {"task", "verdict", "guard_run", "guard_agent_sha256", "opponent", "decision_ticks", "eval_seed",
            "opponent_seed_offset", "games", "fitted_row", "physics_row", "threads", "cap_h", "cpu_cap_h", "device"},
    "pins": {"starts_sha256", "rules_sha256", "deploy_sha256", "hangar_sha256", "hangar_game_sha256"},
    "controls": {"t45_per_game", "t45_per_game_sha256", "t45_key", "t45_holds", "row_difference", "parked_guard",
                 "parked_reach_min", "parked_reach_max", "agree_games", "agree_ticks", "agree_max_m"},
    "references": {"t41_holds", "t41_games", "t24_parked_reaches", "t23_parked_holds", "row5_parked_reaches"},
    "clips": {"per_arm", "key_games"},
}


class Stopped(RuntimeError):
    """A stop or the cap arrived between two ticks: the arm is discarded."""


def sha256_file(path: Path | str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_gates(path: Path | str = GATES_FILE) -> dict:
    """The gate file with exact keys per section (ValueError on a missing or unknown key) plus ``path`` and
    ``sha256``; the parked band must be a band (min <= max)."""
    path = Path(path)
    data = tomllib.loads(path.read_text())
    if set(data) != set(_SECTIONS):
        raise ValueError(f"{path}: sections must be {sorted(_SECTIONS)}, got {sorted(data)}")
    for name, keys in _SECTIONS.items():
        have = set(data[name])
        if have != keys:
            raise ValueError(f"{path}: [{name}] unknown {sorted(have - keys)}, missing {sorted(keys - have)}")
    c = data["controls"]
    if not int(c["parked_reach_min"]) <= int(c["parked_reach_max"]):
        raise ValueError(f"{path}: [controls] parked_reach_min must not exceed parked_reach_max")
    if int(data["run"]["games"]) < int(c["agree_games"]):
        raise ValueError(f"{path}: [controls] agree_games must not exceed [run] games")
    return {**data, "path": path, "sha256": sha256_file(path)}


def pin_problems(gates: dict, root: Path = ROOT) -> list[str]:
    """Files whose sha256 differs from the gate file's pins (the T41 agent, the paired starts, the local NUS files, the
    hangar game file: the games would not be T41's and T24's; T45's per-game file: control C-1 could not be checked)."""
    from ..nus import hangar as H
    from ..nus import ladder
    from ..nus import strategy as strategy_module
    files = {"guard_agent_sha256": root / gates["run"]["guard_run"] / "agent.pt",
             "starts_sha256": ladder.STARTS_FILE, "rules_sha256": strategy_module.RULES_PATH,
             "deploy_sha256": strategy_module.DEPLOY_PATH, "hangar_sha256": H.LOCAL_HANGAR,
             "hangar_game_sha256": H.HANGAR_GAME}
    files["t45_per_game_sha256"] = root / gates["controls"]["t45_per_game"]    # C-1's answer (LEAD CALL QC L02-8)
    out = []
    for key, f in files.items():
        want = gates["run"].get(key) or gates["pins"].get(key) or gates["controls"][key]
        if not Path(f).is_file():
            out.append(f"{key}: {f} is missing")
        elif sha256_file(f) != want:
            out.append(f"{key}: {f} has sha256 {sha256_file(f)}, the gate file pins {want}")
    return out


# ================================================================================================ the two games
def worlds(gates: dict) -> tuple[Any, Any]:
    """(row 5 world, row 6 world): ``nus/pilot.PilotWorld`` of T41's game (``pilot_world(0.0)``, the shaping weight
    T41 trained with) and the same with the physics row's settings (its row dict and its game config)."""
    from ..core.game_config import load_game_cfg
    from ..nus import hangar as H
    from ..nus import pilot as P
    from ..nus import strategy as strategy_module
    from ..nus.deploy import apply_overrides, load_deploy
    from ..nus.rules import load_rules
    w5 = P.pilot_world(0.0)
    if str(w5.row["id"]) != str(gates["run"]["fitted_row"]):
        raise ValueError(f"pilot_world plays row {w5.row['id']}, the gate file's fitted_row is {gates['run']['fitted_row']}")
    settings = H.load_phase4()
    row6 = {r["id"]: r for r in settings["row"]}[str(gates["run"]["physics_row"])]
    H.check_row(row6)
    base, _ = load_game_cfg(H.HANGAR_GAME, use_local=False)
    deploy = load_deploy(strategy_module.DEPLOY_PATH)
    rules = apply_overrides(load_rules(strategy_module.RULES_PATH), deploy)
    cfg6 = H.hangar_cfg(base, rules, deploy, H.load_hangar(H.LOCAL_HANGAR), row6).replace(
        **{"rewards.shaping_weight": float(w5.cfg.rewards.shaping_weight)})
    return w5, dataclasses.replace(w5, cfg=cfg6, row=row6)


def row_difference(w5: Any, w6: Any) -> list[str]:
    """Settings that differ between the two games (the control expects the backend only)."""
    return cfg_differences(w5.cfg, w6.cfg) + [f"row.{k}" for k in sorted(set(w5.row) | set(w6.row))
                                              if k not in ("id", "rung", "changed") and w5.row.get(k) != w6.row.get(k)]


def t41_game(world: Any, games: int, device: str, seed: int, physics: Any = None):
    """T41's evaluation game (``nus/pilot.pilot_games``' arguments: the first ``games`` paired starts, the evaluation
    seed, the kept video slots), on ``physics`` (a rigid-body world) when given."""
    from ..nus import ladder
    from ..nus import pilot as P
    from ..nus.hangar_game import NusHangarGame
    starts = ladder.load_starts()
    if int(starts["starts_units"].shape[0]) < games:
        raise ValueError(f"{games} games need that many paired starts; the file holds {starts['starts_units'].shape[0]}")
    slots = int(P.load_pilots()["video_slots"])
    return NusHangarGame(world.cfg, world.geo, world.row, starts["starts_units"][:games], starts["jitter_m"][:games],
                         world.guards, world.strikes, device=device, seed=seed, video_slots=min(slots, games),
                         rules=world.rules, world=physics)


def t41_players(gates: dict, world: Any, games: int, device: str) -> tuple[Any, Any]:
    """(T41 as a held strategy, mean actions; the opponent with T41's opponent seed)."""
    from ..nus import pilot as P
    from ..opponents.learned import SkrlPolicyStrategy
    r = gates["run"]
    seed = int(r["eval_seed"])
    guard = P.HeldStrategy(SkrlPolicyStrategy(ROOT / r["guard_run"], games, device),
                           P.decision_ticks(r["decision_ticks"], world))
    opp = P.mix_strategy([(r["opponent"], slice(0, games))], "strike", world.cfg, device, seed + int(r["opponent_seed_offset"]))
    return guard, opp


def stoppable(game: Any, should_stop: Callable[[], bool] | None) -> Any:
    """Make ``game.step`` raise :class:`Stopped` when ``should_stop()`` is true before a tick (SIGINT, the cap)."""
    if should_stop is None:
        return game
    inner = game.step

    def step(actions):
        if should_stop():
            raise Stopped("stop requested before a tick")
        return inner(actions)
    game.step = step
    return game


def play_t41(gates: dict, world: Any, device: str, physics: Any = None, games: int | None = None,
             max_steps: int | None = None, should_stop: Callable | None = None) -> tuple[Any, dict]:
    """T41 v the opponent on T41's evaluation game: (MatchResult on the host, the game's extras)."""
    from ..core.play import play_match
    from ..nus.ladder import to_cpu
    n = int(games or gates["run"]["games"])
    seed = int(gates["run"]["eval_seed"])
    game = stoppable(t41_game(world, n, device, seed, physics), should_stop)
    guard, opp = t41_players(gates, world, n, device)
    game.gen.manual_seed(seed)
    res = play_match(game, guard, opp, max_steps=max_steps)
    return to_cpu(res), game.extras()


def play_parked(gates: dict, world: Any, device: str, physics: Any = None, games: int | None = None,
                should_stop: Callable | None = None, max_steps: int | None = None) -> tuple[Any, dict]:
    """The parked control through T24's own path (``ladder.play_game_pair``: the parked Guard player, the ladder
    seed, the Phase 4 starts). ``max_steps`` (smoke runs only) plays the same game and players through
    ``core.play.play_match`` with that many ticks."""
    from ..nus import hangar as H
    from ..nus import ladder as L
    n = int(games or gates["run"]["games"])
    settings = H.load_phase4()
    starts = {k: v[:n] for k, v in L.load_starts().items()}
    if max_steps is not None:
        from ..core.play import play_match
        from ..nus.hangar_game import NusHangarGame
        from ..nus.players import make_player, parks_guard0
        seed = int(settings["ladder"]["seed"])
        guard = make_player(gates["controls"]["parked_guard"], "guard", world.cfg, n, device, seed, 0)
        strike = make_player(gates["run"]["opponent"], "strike", world.cfg, n, device, seed, 0)
        game = stoppable(NusHangarGame(world.cfg, world.geo, world.row, starts["starts_units"], starts["jitter_m"], world.guards,
                                       world.strikes, device=device, seed=seed, parked=parks_guard0(guard),
                                       video_slots=int(settings["ladder"]["video_slots"]), world=physics, rules=world.rules),
                         should_stop)
        return L.to_cpu(play_match(game, guard, strike, max_steps=max_steps)), game.extras()
    if should_stop is not None:                   # play_game_pair builds its own game: stop between ticks via the class
        from ..nus.hangar_game import NusHangarGame
        inner = NusHangarGame.step

        def step(self, actions):
            if should_stop():
                raise Stopped("stop requested before a tick")
            return inner(self, actions)
        NusHangarGame.step = step
    try:
        res, extras, _game, _s = L.play_game_pair(world.cfg, world.geo, world.row, starts, gates["controls"]["parked_guard"],
                                                  gates["run"]["opponent"], world.guards, world.strikes, device,
                                                  int(settings["ladder"]["seed"]), int(settings["ladder"]["video_slots"]),
                                                  physics, world.rules)
    finally:
        if should_stop is not None:
            NusHangarGame.step = inner
    return res, extras


# ================================================================================================ numbers
def per_game(res: Any) -> dict[str, np.ndarray]:
    out = {}
    for k in PER_GAME:
        v = getattr(res, k, None)
        if v is not None:
            out[k] = v.detach().cpu().numpy()
    return out


def summary(pg: dict[str, np.ndarray], team: str) -> dict:
    """Finished games, holds (or reaches for team "strike") with Wilson 95 %, and the safety numbers of the arm."""
    oc = pg["outcome"]
    fin = oc != RUNNING
    n = int(fin.sum())
    k = int((oc == (GUARD_WIN if team == "guard" else STRIKE_WIN)).sum())
    c3 = pg["closest_cross_3d_m"][fin]
    c3 = c3[np.isfinite(c3)]
    lo, hi = wilson_interval(k, n) if n else (None, None)
    return {"games": n, "unfinished": int((~fin).sum()), "count": k, "rate": k / n if n else None, "ci": [lo, hi],
            "counted": "holds" if team == "guard" else "reaches",
            "closest_3d_min_m": float(c3.min()) if c3.size else None,
            "closest_3d_median_m": float(np.median(c3)) if c3.size else None,
            "rule_breach_share": float(pg["rule_breach"][fin].mean()) if n else None,
            "filter_share": float(pg["filter_corrected_rate"][fin].mean()) if n else None,
            "mean_end_step": float(pg["end_step"][fin].mean()) if n else None,
            "nonfinite_actions": int(pg["nonfinite_actions"].sum()),
            "upset_games": int(pg["upset"].sum()) if "upset" in pg else None}


def sign_test_p(a: int, b: int) -> float:
    """Two-sided exact sign test of a against b discordant pairs (binomial, p = 1/2)."""
    n = a + b
    if n == 0:
        return 1.0
    k = min(a, b)
    tail = sum(math.comb(n, i) for i in range(k + 1)) * HALF ** n
    return min(1.0, 2 * tail)


def paired(ref: np.ndarray, cell: np.ndarray) -> dict:
    """Paired by start: holds in both, lost here only, gained here only, lost in both; sign test p."""
    ref, cell = np.asarray(ref), np.asarray(cell)
    if ref.shape != cell.shape:
        raise ValueError(f"paired games differ in number: {ref.shape} v {cell.shape}")
    r, c = ref == GUARD_WIN, cell == GUARD_WIN
    lost, gained = int((r & ~c).sum()), int((~r & c).sum())
    return {"both_hold": int((r & c).sum()), "lost_here": lost, "gained_here": gained, "both_lost": int((~r & ~c).sum()),
            "outcomes_differ": int((ref != cell).sum()), "sign_test_p": sign_test_p(lost, gained),
            "lost_slots": [int(i) for i in np.flatnonzero(r & ~c)], "gained_slots": [int(i) for i in np.flatnonzero(~r & c)]}


# ================================================================================================ controls
def check_t45(gates: dict, pg: dict, root: Path = ROOT) -> dict:
    """C-1 (CPU, exact): T41's tier 1 game on the CPU gives T45's holds and T45's outcome in every game (T45 =
    records/2026-11-21_ste_l014_crazyflie_route_record.md, the 0.1482 s cell = the default path)."""
    c = gates["controls"]
    f = root / c["t45_per_game"]
    if not f.is_file() or sha256_file(f) != c["t45_per_game_sha256"]:
        return {"pass": False, "why": f"T45's per-game file {f} is missing or not the pinned one"}
    ref = np.load(f)[c["t45_key"]]
    holds = int((pg["outcome"] == GUARD_WIN).sum())
    differ = int((ref != pg["outcome"]).sum()) if ref.shape == pg["outcome"].shape else -1
    return {"holds": holds, "expected_holds": int(c["t45_holds"]), "games_differing_from_t45": differ,
            "pass": holds == int(c["t45_holds"]) and differ == 0}


def check_parked(gates: dict, pg: dict) -> dict:
    """C-2 (tier 2, a band): the parked Guard's Strike reaches lie in the pre-stated band (T24's Wilson 95 % interval;
    row 5's 571 is outside it, so a game that is not the physics drone's shows)."""
    c = gates["controls"]
    reaches = int((pg["outcome"] == STRIKE_WIN).sum())
    return {"reaches": reaches, "band": [int(c["parked_reach_min"]), int(c["parked_reach_max"])],
            "t24_reaches": int(gates["references"]["t24_parked_reaches"]),
            "pass": int(c["parked_reach_min"]) <= reaches <= int(c["parked_reach_max"])}


def check_rows(gates: dict, w5: Any, w6: Any) -> dict:
    """C-0: the two games differ only where the gate file says (Phase 4 row 6: the drone only)."""
    diff = row_difference(w5, w6)
    want = list(gates["controls"]["row_difference"])
    return {"differences": diff, "expected": want, "pass": sorted(diff) == sorted(want)}


def agreement(gates: dict, world: Any, device: str, physics: Any, reference_factory: Callable,
              games: int | None = None) -> tuple[dict, dict]:
    """(C-3, C-3b), LEAD CALL 21 Nov 2026 (QC L02-2), as L0.2's C-1a / C-1b (``ste/speed.py``, agreement section).
    C-3 PHYSICS (gated): T41 v the opponent in T41's row 6 game on a PyTorch reference world for ``agree_ticks`` ticks,
    every call the game made to its PhysicsDrone recorded (per-drone world writes and setpoints, in order; QC L02-R1),
    then replayed bare on ``physics`` and on a fresh reference world; the largest 3-D
    gap over every game, drone and tick at most ``agree_max_m``. C-3b GAME (INFO): the game on ``physics`` and on a
    reference world, positions compared only for drones in the game in both, up to the first in/out difference."""
    from ..core.physics_layer import load_game_physics_params
    from .speed import compare_game_traces, game_traces, record_inputs, replay_gap
    c = gates["controls"]
    n, ticks = int(games or gates["run"]["games"]), int(c["agree_ticks"])
    seed = int(gates["run"]["eval_seed"])
    m = world.guards + world.strikes
    params = load_game_physics_params(world.cfg)

    def game_on(phys):
        game = t41_game(world, n, device, seed, phys)
        game.gen.manual_seed(seed)
        guard, opp = t41_players(gates, world, n, device)
        return game, guard, opp
    rec = record_inputs(*game_on(reference_factory(n, m, params, device)), ticks)
    c3 = replay_gap(rec, physics, reference_factory(n, m, params, device), params, device, float(c["agree_max_m"]))
    del rec
    a = game_traces(*game_on(physics), ticks)
    b = game_traces(*game_on(reference_factory(n, m, params, device)), ticks)
    c3b = compare_game_traces(a["pos"], a["alive"], b["pos"], b["alive"])
    c3b.update(world=a["counters"], reference=b["counters"], games=n, info="INFO, not gated (LEAD CALL QC L02-2)")
    return c3, c3b
