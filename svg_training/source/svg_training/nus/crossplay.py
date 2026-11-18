"""Stage 5.1 statistics (NUS port Phase 5, task M5): the one module that serves the gate, the figures and the record (STANDARDS section 7.2).

Everything here follows the frozen table ``[gates.phase5_method_match]`` of ``configs/nus_port.toml`` (plan section 4.3) and is used the
same way by R0 (reference), C0 (positive control), N0 (negative control) and stage 5.1 itself. Every threshold comes from that table; this
file holds no numeric literal other than 0, 1, -1, 2 (G2).

Data. A :class:`CrossPlay` holds one scored matrix on the replica: every Guard entry against every Strike entry (Strike-team reach
counts; NaN where a pairing was not scored), plus each entry against the other team's scripted APF controller. An entry is
``(lineage, generation, team)``; a lineage is one seed of one arm (``"s1"`` for NUS seed 1, ``"o1001"`` for our seed 1001, ...). Entries
that failed conversion are listed in ``excluded`` and leave every panel (``d_failed_conversion``).

Statistics.

* 5.1-a completion: every lineage archives every generation and has no non-finite abort (not applicable to N0).
* 5.1-b learner works: in the window of generations, a generation fails when its archived entry's worst win rate against its own
  training pool (APF included) is at most ``b_failed_generation_max_worst_win``; a lineage fails when more than
  ``b_max_consecutive_failed_same_team`` consecutive same-team generations fail (same-team generations are two apart).
* 5.1-c scripted columns: each of our entries' win rate against the other team's APF lies inside [lowest Wilson lower bound, highest
  Wilson upper bound] of the reference entries of its team. Gated unless R0's leave-one-out check (:func:`loo_check`) fails.
* 5.1-d cross-lineage strength, two statistics: a lineage's Guards' mean hold rate against the reference Strike entries of other
  lineages, and its Strikes' mean reach rate against the reference Guard entries of other lineages, APF excluded. A reference lineage
  is scored against the other reference lineages; one of ours is the mean over the leave-one-out panels (each panel: the reference
  lineages but one). Arms are compared with a pooled two-sample t interval (frozen t quantile, four degrees of freedom), or, in the
  six-seed follow-up, a Welch interval (Welch-Satterthwaite degrees of freedom). Each arm's standard deviation (n - 1) is raised to the
  floor ``d_sd_floor`` before pooling, before the Welch terms and before the spread ratio (ours / reference).
* Verdict, in this order: FAIL if a (when applicable), b or c (when gated) fails, or either d interval excludes 0; otherwise
  INCONCLUSIVE if either spread ratio exceeds ``d_spread_ratio_max`` (FAIL instead in the follow-up); otherwise PASS.
* 5.1-e (INFO): last-mover share, near-shutout share, generalist mean, matrix differences.

Reading taken where the frozen text is silent (stated in the record, for the lead to confirm): the floor applies inside the Welch
interval too (it keeps the interval defined when an arm has no spread), and a reference lineage's own entries never enter its panel.
"""
from __future__ import annotations

import math
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, NamedTuple, Sequence

import numpy as np

from .outcome import wilson_interval
from .rules import ROOT

GATES_FILE = ROOT / "configs" / "nus_port.toml"
GATE_TABLE = "phase5_method_match"
TEAMS = ("guard", "strike")
STATISTIC_TEAM = {"guard_mean_hold_vs_other_lineage_strikes": "guard", "strike_mean_reach_vs_other_lineage_guards": "strike"}
POOLED_DEGREES_OF_FREEDOM = 2 * 2  # the frozen quantile is for 3 v 3 seeds (n1 + n2 - 2)
PASS, FAIL, INCONCLUSIVE, INFO = "PASS", "FAIL", "INCONCLUSIVE", "INFO"


class Entry(NamedTuple):
    lineage: str
    generation: int
    team: str


# ------------------------------------------------------------------------------------------------ gate
@dataclass(frozen=True)
class MethodMatchGate:
    """The frozen numbers of ``[gates.phase5_method_match]``."""

    generations: int
    games_per_pairing: int
    confidence: float
    b_window: tuple[int, int]
    b_max_worst_win: float
    b_max_consecutive: int
    t_quantile: float
    sd_floor: float
    spread_ratio_max: float
    d_statistics: tuple[str, ...]
    status: str


def load_gate(path: Path | str = GATES_FILE, table: str = GATE_TABLE, require_frozen: bool = True) -> MethodMatchGate:
    """Read the gate table; refuses a table that is not frozen (unless ``require_frozen`` is False, for tests)."""
    raw = tomllib.loads(Path(path).read_text())["gates"][table]
    if require_frozen and not str(raw.get("status", "")).startswith("FROZEN"):
        raise ValueError(f"[gates.{table}] is not frozen")
    lo, hi = raw["b_learner_window"]
    stats = tuple(raw["d_statistics"])
    if set(stats) != set(STATISTIC_TEAM):
        raise ValueError(f"[gates.{table}] d_statistics names statistics this module does not compute")
    return MethodMatchGate(generations=int(raw["generations"]), games_per_pairing=int(raw["games_per_pairing"]),
                           confidence=float(raw["confidence"]), b_window=(int(lo), int(hi)),
                           b_max_worst_win=float(raw["b_failed_generation_max_worst_win"]),
                           b_max_consecutive=int(raw["b_max_consecutive_failed_same_team"]), t_quantile=float(raw["d_t_quantile"]),
                           sd_floor=float(raw["d_sd_floor"]), spread_ratio_max=float(raw["d_spread_ratio_max"]), d_statistics=stats,
                           status=str(raw.get("status", "")))


# ------------------------------------------------------------------------------------------------ the scored matrix
@dataclass
class CrossPlay:
    """One scored matrix. ``reached`` (G, S): Strike-team reach counts of Guard entry i against Strike entry j, NaN where not scored;
    ``apf_strike_reached`` (G,): reach counts of the APF Strike team against each Guard entry; ``apf_guard_reached`` (S,): reach counts
    of each Strike entry against the APF Guard team. Every pairing plays ``games`` games."""

    guards: tuple[Entry, ...]
    strikes: tuple[Entry, ...]
    reached: np.ndarray
    games: int
    apf_strike_reached: np.ndarray
    apf_guard_reached: np.ndarray
    excluded: frozenset[Entry] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        self.guards, self.strikes = tuple(Entry(*e) for e in self.guards), tuple(Entry(*e) for e in self.strikes)
        self.reached = np.asarray(self.reached, dtype=float)
        self.apf_strike_reached = np.asarray(self.apf_strike_reached, dtype=float)
        self.apf_guard_reached = np.asarray(self.apf_guard_reached, dtype=float)
        self.excluded = frozenset(Entry(*e) for e in self.excluded)
        if self.reached.shape != (len(self.guards), len(self.strikes)):
            raise ValueError("reached must be (Guard entries, Strike entries)")
        if self.apf_strike_reached.shape != (len(self.guards),) or self.apf_guard_reached.shape != (len(self.strikes),):
            raise ValueError("the APF columns must have one count per entry")
        if any(e.team != TEAMS[0] for e in self.guards) or any(e.team != TEAMS[1] for e in self.strikes):
            raise ValueError("Guard rows and Strike columns must carry their team")
        if self.games < 1:
            raise ValueError("games must be positive")
        self._row = {e: i for i, e in enumerate(self.guards)}
        self._col = {e: j for j, e in enumerate(self.strikes)}

    def entries(self, lineage: str, team: str) -> list[Entry]:
        """The entries of one lineage and team that did not fail conversion, in generation order."""
        pool = self.guards if team == TEAMS[0] else self.strikes
        return sorted((e for e in pool if e.lineage == lineage and e not in self.excluded), key=lambda e: e.generation)

    def win_rate(self, entry: Entry, opponent: Entry) -> float:
        """The win rate of ``entry`` against ``opponent`` (a Guard wins when the Strike team never reaches); NaN if not scored."""
        if entry.team == TEAMS[0]:
            return 1 - self.reached[self._row[entry], self._col[opponent]] / self.games
        return self.reached[self._row[opponent], self._col[entry]] / self.games

    def apf_win_rate(self, entry: Entry) -> float:
        """The win rate of ``entry`` against the other team's APF controller."""
        if entry.team == TEAMS[0]:
            return 1 - self.apf_strike_reached[self._row[entry]] / self.games
        return self.apf_guard_reached[self._col[entry]] / self.games

    def apf_wins(self, entry: Entry) -> int:
        rate = self.apf_win_rate(entry)
        return int(round(rate * self.games))


def other_team(team: str) -> str:
    return TEAMS[1] if team == TEAMS[0] else TEAMS[0]


# ------------------------------------------------------------------------------------------------ 5.1-a
def stat_a(completion: dict[str, tuple[int, int]], generations: int) -> dict[str, Any]:
    """``completion``: lineage -> (archived generations, non-finite aborts). Passes when every lineage archived every generation and
    no lineage aborted on a non-finite value."""
    per = {k: bool(archived == generations and aborts == 0) for k, (archived, aborts) in completion.items()}
    return {"per_lineage": per, "pass": bool(per) and all(per.values())}


# ------------------------------------------------------------------------------------------------ 5.1-b
def worst_win(xp: CrossPlay, entry: Entry, pool: Sequence[Entry], include_apf: bool = True) -> float:
    """The entry's worst win rate against its training pool (learned entries of the other team, plus APF)."""
    rates = [xp.win_rate(entry, o) for o in pool if o not in xp.excluded]
    if include_apf:
        rates.append(xp.apf_win_rate(entry))
    rates = [r for r in rates if not math.isnan(r)]
    if not rates:
        raise ValueError(f"{entry}: no scored opponent in its pool")
    return float(min(rates))


def lineage_b(worst: dict[int, float], gate: MethodMatchGate) -> dict[str, Any]:
    """One lineage's 5.1-b: ``worst`` maps a generation to its archived entry's worst win rate. Every generation of the window is
    required."""
    lo, hi = gate.b_window
    window = range(lo, hi + 1)
    missing = [g for g in window if g not in worst]
    if missing:
        raise ValueError(f"5.1-b needs every generation of the window; missing {missing}")
    failed = {g: bool(worst[g] <= gate.b_max_worst_win) for g in window}
    longest = 0
    for start in (lo, lo + 1):  # the two teams' generation sequences inside the window
        run = 0
        for g in range(start, hi + 1, 2):
            run = run + 1 if failed[g] else 0
            longest = max(longest, run)
    return {"failed": failed, "longest_same_team_run": longest, "pass": longest <= gate.b_max_consecutive}


def stat_b(worst_by_lineage: dict[str, dict[int, float]], gate: MethodMatchGate) -> dict[str, Any]:
    per = {k: lineage_b(v, gate) for k, v in worst_by_lineage.items()}
    return {"per_lineage": per, "pass": bool(per) and all(p["pass"] for p in per.values())}


# ------------------------------------------------------------------------------------------------ 5.1-c
def envelope(xp: CrossPlay, entries: Sequence[Entry], confidence: float) -> tuple[float, float]:
    """[lowest Wilson lower bound, highest Wilson upper bound] of the entries' APF win rates."""
    bounds = [wilson_interval(xp.apf_wins(e), xp.games, confidence) for e in entries]
    return min(b[0] for b in bounds), max(b[1] for b in bounds)


def loo_check(xp: CrossPlay, reference: Sequence[str], confidence: float) -> dict[str, Any]:
    """R0's leave-one-out calibration of 5.1-c: each reference entry's APF win rate inside the envelope of the other reference entries
    of its team. Any miss makes 5.1-c INFO."""
    per = {}
    for team in TEAMS:
        entries = [e for k in reference for e in xp.entries(k, team)]
        for e in entries:
            lo, hi = envelope(xp, [o for o in entries if o != e], confidence)
            per[e] = bool(lo <= xp.apf_win_rate(e) <= hi)
    return {"per_entry": per, "pass": all(per.values())}


def stat_c(xp: CrossPlay, ours: Sequence[str], reference: Sequence[str], confidence: float, gated: bool) -> dict[str, Any]:
    out: dict[str, Any] = {"per_entry": {}, "envelope": {}, "kind": "gate" if gated else INFO}
    for team in TEAMS:
        lo, hi = envelope(xp, [e for k in reference for e in xp.entries(k, team)], confidence)
        out["envelope"][team] = (lo, hi)
        for k in ours:
            for e in xp.entries(k, team):
                out["per_entry"][e] = bool(lo <= xp.apf_win_rate(e) <= hi)
    out["pass"] = all(out["per_entry"].values())
    return out


# ------------------------------------------------------------------------------------------------ 5.1-d
def panel_value(xp: CrossPlay, lineage: str, team: str, panel: Sequence[str]) -> float:
    """Mean win rate of the lineage's entries of ``team`` against the entries of the other team in the panel's lineages, over every
    scored cell (entries that failed conversion are left out on both sides)."""
    own = xp.entries(lineage, team)
    opponents = [o for k in panel for o in xp.entries(k, other_team(team))]
    cells = [xp.win_rate(e, o) for e in own for o in opponents]
    cells = [c for c in cells if not math.isnan(c)]
    if not cells:
        raise ValueError(f"lineage {lineage} ({team}) has no scored cell against panel {list(panel)}")
    return float(np.mean(cells))


def reference_value(xp: CrossPlay, lineage: str, team: str, reference: Sequence[str]) -> float:
    """A reference lineage against the entries of the other reference lineages."""
    return panel_value(xp, lineage, team, [k for k in reference if k != lineage])


def our_value(xp: CrossPlay, lineage: str, team: str, reference: Sequence[str]) -> float:
    """One of our lineages: the mean over the leave-one-out panels (each panel: every reference lineage but one)."""
    panels = [[k for k in reference if k != left_out] for left_out in reference]
    return float(np.mean([panel_value(xp, lineage, team, p) for p in panels]))


def _floored_sd(values: Sequence[float], floor: float) -> float:
    return max(float(np.std(values, ddof=1)), floor)


def pooled_t_interval(ours: Sequence[float], reference: Sequence[float], t_quantile: float, sd_floor: float) -> dict[str, Any]:
    """The pooled two-sample t interval of (mean of ours - mean of reference), each arm's standard deviation floored first. The frozen
    quantile holds for four degrees of freedom only; another seed count is refused."""
    n1, n2 = len(ours), len(reference)
    if n1 + n2 - 2 != POOLED_DEGREES_OF_FREEDOM:
        raise ValueError("the frozen t quantile is for 3 v 3 seeds; use welch_interval for the six-seed follow-up")
    s1, s2 = _floored_sd(ours, sd_floor), _floored_sd(reference, sd_floor)
    pooled = math.sqrt(((n1 - 1) * s1 ** 2 + (n2 - 1) * s2 ** 2) / (n1 + n2 - 2))
    half = t_quantile * pooled * math.sqrt(1 / n1 + 1 / n2)
    diff = float(np.mean(ours) - np.mean(reference))
    return {"test": "pooled_t", "diff": diff, "low": diff - half, "high": diff + half, "df": float(n1 + n2 - 2),
            "t_quantile": t_quantile, "sd_ours": s1, "sd_reference": s2, "spread_ratio": s1 / s2,
            "contains_zero": bool(diff - half <= 0 <= diff + half), "ours": list(map(float, ours)),
            "reference": list(map(float, reference))}


def welch_interval(ours: Sequence[float], reference: Sequence[float], confidence: float, sd_floor: float) -> dict[str, Any]:
    """The Welch interval of the difference of means with Welch-Satterthwaite degrees of freedom; the floor is applied to each arm's
    standard deviation first."""
    from scipy.stats import t as student_t

    n1, n2 = len(ours), len(reference)
    s1, s2 = _floored_sd(ours, sd_floor), _floored_sd(reference, sd_floor)
    a, b = s1 ** 2 / n1, s2 ** 2 / n2
    df = (a + b) ** 2 / (a ** 2 / (n1 - 1) + b ** 2 / (n2 - 1))
    quantile = float(student_t.ppf(1 - (1 - confidence) / 2, df))
    half = quantile * math.sqrt(a + b)
    diff = float(np.mean(ours) - np.mean(reference))
    return {"test": "welch", "diff": diff, "low": diff - half, "high": diff + half, "df": float(df), "t_quantile": quantile,
            "sd_ours": s1, "sd_reference": s2, "spread_ratio": s1 / s2, "contains_zero": bool(diff - half <= 0 <= diff + half),
            "ours": list(map(float, ours)), "reference": list(map(float, reference))}


def stat_d(xp: CrossPlay, ours: Sequence[str], reference: Sequence[str], gate: MethodMatchGate, followup: bool = False) -> dict[str, Any]:
    out = {}
    for name in gate.d_statistics:
        team = STATISTIC_TEAM[name]
        our_values = [our_value(xp, k, team, reference) for k in ours]
        ref_values = [reference_value(xp, k, team, reference) for k in reference]
        interval = (welch_interval(our_values, ref_values, gate.confidence, gate.sd_floor) if followup
                    else pooled_t_interval(our_values, ref_values, gate.t_quantile, gate.sd_floor))
        out[name] = interval | {"team": team, "lineages_ours": list(ours), "lineages_reference": list(reference)}
    return out


# ------------------------------------------------------------------------------------------------ verdict
def verdict(a: dict | None, b: dict, c: dict, d: dict[str, dict], gate: MethodMatchGate, followup: bool = False) -> dict[str, Any]:
    """FAIL, then INCONCLUSIVE, then PASS (``verdict_order``). ``a`` is None where completion does not apply (N0). 5.1-c counts only
    when gated. In the follow-up the spread rule gives FAIL, not INCONCLUSIVE."""
    reasons = []
    if a is not None and not a["pass"]:
        reasons.append("5.1-a")
    if not b["pass"]:
        reasons.append("5.1-b")
    if c["kind"] != INFO and not c["pass"]:
        reasons.append("5.1-c")
    reasons += [f"5.1-d {name}: interval excludes 0" for name, r in d.items() if not r["contains_zero"]]
    spread = [f"5.1-d {name}: spread ratio above the limit" for name, r in d.items() if r["spread_ratio"] > gate.spread_ratio_max]
    if reasons:
        result = FAIL
    elif spread:
        result = FAIL if followup else INCONCLUSIVE
        reasons = spread
    else:
        result = PASS
    return {"verdict": result, "reasons": reasons, "followup": followup}


def negative_control_ok(result: dict[str, Any]) -> bool:
    """N0's requirement: verdict FAIL and both 5.1-d intervals exclude 0."""
    d = result["statistics"]["d"]
    return result["verdict"]["verdict"] == FAIL and all(not r["contains_zero"] for r in d.values())


def method_match(xp: CrossPlay, ours: Sequence[str], reference: Sequence[str], gate: MethodMatchGate, *,
                 completion: dict[str, tuple[int, int]] | None, pools: dict[Entry, Sequence[Entry]],
                 c_gated: bool = True, followup: bool = False) -> dict[str, Any]:
    """Every statistic a to d and the verdict for the ``ours`` arm against the ``reference`` arm. ``pools`` maps each of our entries in
    the 5.1-b window to its training pool (learned entries; APF is always added); ``completion`` is None for N0."""
    lo, hi = gate.b_window
    worst = {k: {e.generation: worst_win(xp, e, pools[e]) for team in TEAMS for e in xp.entries(k, team) if lo <= e.generation <= hi}
             for k in ours}
    a = stat_a(completion, gate.generations) if completion is not None else None
    b = stat_b(worst, gate)
    c = stat_c(xp, ours, reference, gate.confidence, c_gated)
    d = stat_d(xp, ours, reference, gate, followup)
    return {"statistics": {"a": a, "b": b, "c": c, "d": d}, "verdict": verdict(a, b, c, d, gate, followup)}


# ------------------------------------------------------------------------------------------------ 5.1-e (INFO)
def last_mover_share(xp: CrossPlay, lineage: str) -> float:
    """Own-lineage cells (its Guards x its Strikes) in which the later-trained policy wins (win rate above one half)."""
    wins = cells = 0
    for g in xp.entries(lineage, TEAMS[0]):
        for s in xp.entries(lineage, TEAMS[1]):
            later = g if g.generation > s.generation else s
            rate = xp.win_rate(later, s if later is g else g)
            if math.isnan(rate):
                continue
            cells += 1
            wins += int(rate > 1 / 2)
    return wins / cells if cells else float("nan")


def near_shutout_share(xp: CrossPlay, lineage: str, margin: float) -> float:
    """Own-lineage cells whose reach rate is within ``margin`` of 0 or 1 (``margin`` is the caller's, INFO only)."""
    rates = [xp.win_rate(s, g) for g in xp.entries(lineage, TEAMS[0]) for s in xp.entries(lineage, TEAMS[1])]
    rates = [r for r in rates if not math.isnan(r)]
    return float(np.mean([r <= margin or r >= 1 - margin for r in rates])) if rates else float("nan")


def generalist_mean(xp: CrossPlay, lineages: Sequence[str], guard_generation: int, strike_generation: int) -> float:
    """Mean reach rate of the given Strike generation of every lineage against the given Guard generation of every lineage (NUS's
    criterion (b) of the hangar probe; the band is the caller's, INFO only)."""
    guards = [e for k in lineages for e in xp.entries(k, TEAMS[0]) if e.generation == guard_generation]
    strikes = [e for k in lineages for e in xp.entries(k, TEAMS[1]) if e.generation == strike_generation]
    rates = [xp.win_rate(s, g) for g in guards for s in strikes]
    return float(np.nanmean(rates))


def cell_differences(first: CrossPlay, second: CrossPlay) -> np.ndarray:
    """Per-cell reach-rate differences (first - second) of two matrices over the same entries (e.g. JAX evaluator - replica)."""
    if first.guards != second.guards or first.strikes != second.strikes:
        raise ValueError("the two matrices must list the same entries in the same order")
    return first.reached / first.games - second.reached / second.games


# ------------------------------------------------------------------------------------------------ scoring on the replica
# A player is a parameter tree (``mappo.Trunk.tree`` layout, float32; a learned entry acting with its mean) or None (the APF controller
# of its team). Every pairing plays the same shared starts; pairings are stacked into one batch (a Python loop over chunks of pairings
# only, never over games).
def shared_starts(env, games: int, seed: int):
    """One start set drawn once by the replica's random start rule (``starts_seed`` of the reference gate)."""
    import torch
    return env.reset(games, torch.Generator(device=env.device).manual_seed(int(seed)), random_start=True)


def _repeat_state(starts, times: int):
    from .replica import ReplicaState
    from .replica_train import TrainState
    g = starts.game

    def rep(t):  # pairing p holds games p x G .. (p + 1) x G, each the same start set
        return t.repeat((times,) + (1,) * (t.dim() - 1))
    return TrainState(ReplicaState(rep(g.pos), rep(g.prev_pos), rep(g.reached), rep(g.step)), rep(starts.guard_spawn),
                      rep(starts.strike_spawn))


def _team_actions(env, state, team: str, players: list, games: int, forward: dict):
    """Actions (P x games, team size, 2) of one team for P stacked pairings; pairing p's games are rows p x games .. (p + 1) x games."""
    import torch
    from .mappo import squash, stack_trees, trunk_forward
    guard_obs, strike_obs = env.observe(state)
    obs = guard_obs if team == TEAMS[0] else strike_obs
    out = env.apf_actions(state, team)
    learned = [p for p, player in enumerate(players) if player is not None]
    if learned:
        a, d = obs.shape[1], obs.shape[2]
        stacked = obs.reshape(len(players), games * a, d)[learned]
        mean = trunk_forward(stack_trees([players[p] for p in learned]), stacked, **forward)
        acts = squash(mean, env.team_speed(team), env.deploy.disk_floor).reshape(len(learned), games, a, -1)
        out = out.reshape(len(players), games, a, -1).clone()
        out[torch.tensor(learned, device=out.device)] = acts
        out = out.reshape(len(players) * games, a, -1)
    return out


def score_pairings(env, pairs: Sequence[tuple[Any, Any]], starts, forward: dict, chunk: int) -> np.ndarray:
    """Strike-team reach counts of each (Guard player, Strike player) pairing on the shared ``starts``, both teams deterministic.
    ``forward``: the trunk settings (``bf16``, ``activation``, ``eps``, ``use_norm``); ``chunk``: pairings per batch."""
    import torch
    games = starts.game.pos.shape[0]
    counts = []
    for begin in range(0, len(pairs), chunk):
        part = pairs[begin:begin + chunk]
        state = _repeat_state(starts, len(part))
        with torch.no_grad():
            for _ in range(env.episode_steps):
                guard = _team_actions(env, state, TEAMS[0], [g for g, _ in part], games, forward)
                strike = _team_actions(env, state, TEAMS[1], [s for _, s in part], games, forward)
                state, _ = env.step(state, guard, strike, shaping_gamma=1)
            if not bool(torch.isfinite(state.game.pos).all()):
                raise RuntimeError("non-finite replica state while scoring")
            counts.append((state.game.reached > 0).reshape(len(part), games).sum(dim=1))
    return torch.cat(counts).cpu().numpy().astype(float)


def score_matrix(env, guards: dict[Entry, Any], strikes: dict[Entry, Any], starts, forward: dict, chunk: int,
                 excluded: frozenset[Entry] = frozenset()) -> CrossPlay:
    """Every Guard entry against every Strike entry and both APF columns, on one shared start set (plan R0 step 2)."""
    g_list, s_list = list(guards), list(strikes)
    pairs = [(guards[g], strikes[s]) for g in g_list for s in s_list]
    pairs += [(guards[g], None) for g in g_list] + [(None, strikes[s]) for s in s_list]
    counts = score_pairings(env, pairs, starts, forward, chunk)
    n_cells = len(g_list) * len(s_list)
    reached = counts[:n_cells].reshape(len(g_list), len(s_list))
    return CrossPlay(tuple(g_list), tuple(s_list), reached, int(starts.game.pos.shape[0]), counts[n_cells:n_cells + len(g_list)],
                     counts[n_cells + len(g_list):], frozenset(excluded))


def untrained_trees(env, method, seed: int, generations: int) -> dict[Entry, dict]:
    """N0: one fresh actor per generation slot, our initialisation from the stage seed (seed + generation - 1) and team, no training."""
    from .mappo import MappoActor, stage_generator
    from .method_cfg import team_of_generation
    from .selection import stage_seed
    out = {}
    for generation in range(1, generations + 1):
        team = team_of_generation(method, generation)
        actor = MappoActor(env.obs_dim, method, env.deploy.layernorm_epsilon, stage_generator(stage_seed(seed, generation), team, 0))
        out[Entry(f"n{seed}", generation, team)] = {k: v for k, v in _detach_tree(actor.trunk.tree()).items()}
    return out


def _detach_tree(tree: dict) -> dict:
    def d(pair):
        return tuple(t.detach().clone() for t in pair)
    return {"proj": d(tree["proj"]), "input": d(tree["input"]), "output": d(tree["output"]),
            "blocks": [{k: d(v) for k, v in b.items()} for b in tree["blocks"]]}


# ------------------------------------------------------------------------------------------------ files
def crossplay_to_dict(xp: CrossPlay) -> dict[str, Any]:
    """A JSON-ready form (counts and entry names only)."""
    def nums(a):
        return [None if math.isnan(v) else v for v in np.asarray(a, float).ravel().tolist()]
    return {"guards": [list(e) for e in xp.guards], "strikes": [list(e) for e in xp.strikes], "games": xp.games,
            "reached": [nums(row) for row in xp.reached], "apf_strike_reached": nums(xp.apf_strike_reached),
            "apf_guard_reached": nums(xp.apf_guard_reached), "excluded": sorted(list(e) for e in xp.excluded)}


def crossplay_from_dict(data: dict[str, Any]) -> CrossPlay:
    def arr(a):
        return np.asarray([np.nan if v is None else v for v in a], float)
    return CrossPlay(tuple(Entry(*e) for e in data["guards"]), tuple(Entry(*e) for e in data["strikes"]),
                     np.vstack([arr(row) for row in data["reached"]]) if data["reached"] else np.zeros((0, len(data["strikes"]))),
                     int(data["games"]), arr(data["apf_strike_reached"]), arr(data["apf_guard_reached"]),
                     frozenset(Entry(*e) for e in data["excluded"]))


def merge(first: CrossPlay, second: CrossPlay) -> CrossPlay:
    """One matrix over the entries of both (cells scored in neither stay NaN); both must share the game count."""
    if first.games != second.games:
        raise ValueError("the two matrices must use the same game count")
    guards = tuple(dict.fromkeys(first.guards + second.guards))
    strikes = tuple(dict.fromkeys(first.strikes + second.strikes))
    reached = np.full((len(guards), len(strikes)), np.nan)
    apf_s, apf_g = np.full(len(guards), np.nan), np.full(len(strikes), np.nan)
    for xp in (first, second):
        rows = [guards.index(g) for g in xp.guards]
        cols = [strikes.index(s) for s in xp.strikes]
        for i, r in enumerate(rows):
            for j, c in enumerate(cols):
                if not math.isnan(xp.reached[i, j]):
                    reached[r, c] = xp.reached[i, j]
            apf_s[r] = xp.apf_strike_reached[i]
        for j, c in enumerate(cols):
            apf_g[c] = xp.apf_guard_reached[j]
    return CrossPlay(guards, strikes, reached, first.games, apf_s, apf_g, first.excluded | second.excluded)


# ------------------------------------------------------------------------------------------------ 5.1-b pools
def selection_pools(entries: Sequence[Entry], seed: int, maximum: int, recent: int) -> dict[Entry, list[Entry]]:
    """Each entry's learned training pool, as the selection rule builds it from the earlier entries of the other team of the same
    lineage (``selection.select_opponents`` with the lineage's run seed). Serves our arm (the run's own archive) and N0 (the earlier N0
    entries); APF is added by :func:`worst_win`."""
    from .selection import select_opponents
    ordered = sorted(entries, key=lambda e: e.generation)
    if len({e.lineage for e in ordered}) > 1:
        raise ValueError("selection_pools takes the entries of one lineage")
    out = {}
    for e in ordered:
        archive = [{"generation": o.generation, "team": o.team, "entry": o} for o in ordered if o.generation < e.generation]
        chosen = select_opponents(archive, team=e.team, generation=e.generation, seed=seed, maximum=maximum, recent=recent)
        out[e] = [c["entry"] for c in chosen]
    return out
