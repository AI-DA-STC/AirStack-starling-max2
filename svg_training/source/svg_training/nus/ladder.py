"""Every Phase 4 number (plan D5): the paired starts, the replica engine of rows 1 and 2.1, the pair loops, the metrics, and the text of the
records. The figure script imports this module and computes nothing itself. No numeric literal (G2): counts, tolerances and quantiles come
from ``configs/nus_phase4.toml`` (``settings``), lengths and speeds from the local files through ``hangar.py``.

Definitions (written in every record): a rate is ``k/n`` with its Wilson 95 % interval; "reach time" is in seconds, over Strike-win games;
correction size is the speed the safety filter changed, per corrected drone-step (mean over corrected drone-steps; the 95th percentile is
over games of the per-game mean); smoothness is the change of the command the game receives, per drone per tick (and per policy sample, the
tick value times ``hold_ticks``), mean over live drone-ticks per game, its 95th percentile over games; closest approaches are the minimum
and quantiles over games of each game's minimum over its steps.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch import Tensor

from ..core.game_config import TICK_S, GameCfg
from ..core.metrics import summarise, wilson_interval
from ..core.play import MatchResult, play_match
from ..core.rewards import GUARD_WIN, STRIKE_WIN
from .hangar import Geometry
from .outputs import check_payload, near_relative, require_under_runs
from .players import ReplicaPlayer, make_player, parks_guard0
from .replica import NusReplica, ReplicaState
from .rules import RUNS_DIR, NusRules, file_sha256

PHASE4_DIR = RUNS_DIR / "nus_port" / "phase4"
STARTS_FILE = PHASE4_DIR / "starts.npz"
LOCAL_VALUE = "at the local value"
PLACES = 2 + 1  # decimals of a rate or length in a record
ALL_BLOCKS = {"core": ("core_guards", "core_strikes"), "our_strike": ("our_strike_guards", "our_strikes"),
              "our_guard": ("our_guard_guards", "our_guard_strikes")}


# ------------------------------------------------------------------------------------------------ starts
def make_starts(rules: NusRules, games: int, seed: int, jitter_m: float, path: Path | None = None) -> Path:
    """The paired starts, drawn once with the replica's own start rule (random starts), seeded; the jitter per drone and game (uniform, +-
    ``jitter_m``); Guard 0's parked variant. Written only under runs/ (the file holds partner values)."""
    out = require_under_runs(path or STARTS_FILE)
    if out.exists():
        raise FileExistsError(f"{out} exists (the starts are drawn once)")
    gen = torch.Generator().manual_seed(seed)
    start = NusReplica(rules).reset(games, generator=gen, random_start=True).pos
    jitter = (torch.rand(games, start.shape[1], generator=gen) * 2 - 1) * jitter_m
    parked = start.clone()
    parked[:, 0] = 0
    out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out, starts_units=start.numpy(), jitter_m=jitter.numpy(), parked_starts_units=parked.numpy())
    return out


def load_starts(path: Path | None = None) -> dict[str, Tensor]:
    data = np.load(path or STARTS_FILE)
    return {k: torch.from_numpy(data[k]) for k in data.files}


# ------------------------------------------------------------------------------------------------ pairs
def pairs_of_row(settings: dict[str, Any], row: dict[str, Any]) -> list[tuple[str, str]]:
    """(Guard player, Strike player) of every pair of the row's blocks, in the order of the config."""
    pairs: list[tuple[str, str]] = []
    for block in row["blocks"]:
        guard_key, strike_key = ALL_BLOCKS[block]
        pairs += [(g, s) for g in settings["pairs"][guard_key] for s in settings["pairs"][strike_key]]
    return pairs


# ------------------------------------------------------------------------------------------------ replica engine (rows 1 and 2.1)
@dataclass
class ReplicaExtras:
    """What the replica records besides the MatchResult (host tensors, metres)."""
    team_min_3d_m: Tensor
    any_min_3d_m: Tensor
    guard0_drift_m: Tensor
    smooth_sample_mps: Tensor
    positions_units: Tensor | None  # [steps + 1, slots, M, 2] of the first slots, or None


@torch.no_grad()
def play_replica(sim: NusReplica, guard: ReplicaPlayer, strike: ReplicaPlayer, starts_units: Tensor, scale: float, seconds_per_step: float,
                 hold_ticks: int, filter_keepout_m: float, keepouts_m: tuple[float, float], slots: int = 0
                 ) -> tuple[MatchResult, ReplicaExtras]:
    """One pair in the replica from ``starts_units`` [N, M, 2] (Guard 0 parked when the Guard player parks it). Ends a game at the first
    step a Strike drone is inside the zone; metrics use the steps up to then. Ticks = steps x ``hold_ticks``; metres = units x ``scale``.
    Refuses non-finite actions."""
    games, dev = starts_units.shape[0], sim.device
    g = sim.guard_count
    pos0 = starts_units.clone().to(dev, sim.dtype)
    if parks_guard0(guard):
        pos0[:, 0] = 0
    state = ReplicaState(pos=pos0, prev_pos=pos0.clone(), reached=torch.zeros(games, dtype=sim.dtype, device=dev),
                         step=torch.zeros(games, dtype=torch.long, device=dev))
    big = float("inf")
    ended = torch.zeros(games, dtype=torch.bool, device=dev)
    first_reach = torch.zeros(games, dtype=torch.long, device=dev)
    cross_min = torch.full((games,), big, device=dev)
    team_min = torch.full((games,), big, device=dev)
    any_min = torch.full((games,), big, device=dev)
    drift = torch.zeros(games, device=dev)
    smooth_sum = torch.zeros(games, device=dev)
    prev_cmd = torch.zeros(games, sim.num_actors, 2, device=dev)
    frames = [state.pos[:slots].clone()] if slots else []
    cross = sim.cross_team[None]
    same = (~sim.cross_team & ~torch.eye(sim.num_actors, dtype=torch.bool, device=dev))[None]
    offdiag = ~torch.eye(sim.num_actors, dtype=torch.bool, device=dev)[None]
    for step in range(sim.rules.episode_steps):
        obs = sim.observe(state)
        mine = guard(obs[:, :g], state.pos)
        theirs = strike(obs[:, g:], state.pos)
        actions = torch.cat((mine, theirs), dim=1)
        if not bool(torch.isfinite(actions).all()):
            raise RuntimeError("non-finite action in the replica: the run refuses to score")
        state = sim.step(state, actions)
        active = ~ended
        pos_m = state.pos * scale
        dist = (pos_m[:, :, None] - pos_m[:, None]).norm(dim=-1)
        inf = torch.full_like(dist, big)
        cross_min = torch.where(active, torch.minimum(cross_min, torch.where(cross, dist, inf).amin(dim=(1, 2))), cross_min)
        team_min = torch.where(active, torch.minimum(team_min, torch.where(same, dist, inf).amin(dim=(1, 2))), team_min)
        any_min = torch.where(active, torch.minimum(any_min, torch.where(offdiag, dist, inf).amin(dim=(1, 2))), any_min)
        drift = torch.where(active, torch.maximum(drift, pos_m[:, 0].norm(dim=-1)), drift)
        cmd = sim.intended(actions) * scale / seconds_per_step
        if step > 0:
            smooth_sum = smooth_sum + active * (cmd - prev_cmd).norm(dim=-1).sum(dim=1)
        prev_cmd = cmd
        reached_now = state.reached > 0
        first_reach = torch.where(active & reached_now, torch.full_like(first_reach, step + 1), first_reach)
        ended = ended | reached_now
        if slots:
            frames.append(state.pos[:slots].clone())
    reached = first_reach > 0
    steps = torch.where(reached, first_reach, torch.full_like(first_reach, sim.rules.episode_steps))
    outcome = torch.where(reached, STRIKE_WIN, GUARD_WIN).to(torch.int8)
    start_m = pos0 * scale
    d0 = (start_m[:, :, None] - start_m[:, None]).norm(dim=-1)
    miss = ((d0 < filter_keepout_m) & offdiag).any(dim=(1, 2))
    rule_breach = cross_min < min(keepouts_m)
    zeros = torch.zeros(games, device=dev)
    result = MatchResult(outcome.cpu(), (steps * hold_ticks).cpu(), torch.zeros(games, dtype=torch.long), cross_min.cpu(), cross_min.cpu(),
                         rule_breach.cpu(), zeros.cpu(), miss.cpu(), int(sim.rules.episode_steps * hold_ticks),
                         torch.zeros(games, dtype=torch.long), torch.zeros(games, dtype=torch.bool))
    extras = ReplicaExtras(team_min.cpu(), any_min.cpu(), drift.cpu(), (smooth_sum / (sim.num_actors * (steps - 1).clamp(min=1))).cpu(),
                           torch.stack(frames).cpu() if slots else None)
    return result, extras


# ------------------------------------------------------------------------------------------------ the pair loop of the game rows
def play_game_pair(cfg: GameCfg, geo: Geometry, row: dict, starts: dict[str, Tensor], guard_name: str, strike_name: str, guards: int,
                   strikes: int, device: str, seed: int, video_slots: int, world=None, rules: NusRules | None = None):
    """Build a fresh ``NusHangarGame`` for the pair and play it with ``core.play.play_match``. Returns (MatchResult, extras, game, seconds)."""
    import time

    from .hangar_game import NusHangarGame
    n = starts["starts_units"].shape[0]
    jump = geo.hold_ticks if row["motion"] == "jump" else 0
    guard = make_player(guard_name, "guard", cfg, n, device, seed, jump)
    strike = make_player(strike_name, "strike", cfg, n, device, seed, jump)
    game = NusHangarGame(cfg, geo, row, starts["starts_units"], starts["jitter_m"], guards, strikes, device=device, seed=seed,
                         parked=parks_guard0(guard), video_slots=video_slots, world=world, rules=rules)
    if torch.device(device).type == "cuda":
        torch.cuda.synchronize()
    t0 = time.perf_counter()
    result = play_match(game, guard, strike)
    if torch.device(device).type == "cuda":
        torch.cuda.synchronize()
    seconds = time.perf_counter() - t0
    return to_cpu(result), game.extras(), game, seconds


def to_cpu(res: MatchResult) -> MatchResult:
    """The result with every tensor on the host."""
    return MatchResult(*(res.steps_played if k == "steps_played" else (None if getattr(res, k) is None else getattr(res, k).detach().cpu())
                         for k in res.__dataclass_fields__))


def warmup_estimate(cfg: GameCfg, geo: Geometry, row: dict, starts: dict[str, Tensor], pair: tuple[str, str], guards: int, strikes: int, device: str,
                    seed: int, ticks: int, world=None, rules: NusRules | None = None) -> float:
    """Seconds per pair, estimated from ``ticks`` simulator ticks of the first pair (the settings' warm-up): the time of those ticks scaled to the
    game length. The first tick is left out of the timing (it builds buffers)."""
    import time

    from .hangar_game import NusHangarGame
    n = starts["starts_units"].shape[0]
    jump = geo.hold_ticks if row["motion"] == "jump" else 0
    guard = make_player(pair[0], "guard", cfg, n, device, seed, jump)
    strike = make_player(pair[1], "strike", cfg, n, device, seed, jump)
    game = NusHangarGame(cfg, geo, row, starts["starts_units"], starts["jitter_m"], guards, strikes, device=device, seed=seed,
                         parked=parks_guard0(guard), world=world, rules=rules)
    obs = game.reset()
    guard.reset(torch.ones(n, dtype=torch.bool, device=device))
    strike.reset(torch.ones(n, dtype=torch.bool, device=device))
    cuda = torch.device(device).type == "cuda"
    for tick in range(ticks + 1):
        if tick == 1:
            if cuda:
                torch.cuda.synchronize()
            t0 = time.perf_counter()
        obs = game.step({"guard": guard.act(obs["guard"]), "strike": strike.act(obs["strike"])}).obs
    if cuda:
        torch.cuda.synchronize()
    return (time.perf_counter() - t0) / ticks * geo.game_ticks


# ------------------------------------------------------------------------------------------------ metrics of one pair
def _rate(k: int, n: int) -> dict[str, Any]:
    low, high = wilson_interval(k, n)
    return {"k": k, "n": n, "rate": k / n if n else None, "ci_low": low if n else None, "ci_high": high if n else None}


def _quantiles(values: Tensor, qs: list[float]) -> dict[str, float | None]:
    values = values[torch.isfinite(values)].double()
    out: dict[str, float | None] = {"min": float(values.min()) if values.numel() else None}
    for q in qs:
        out[f"q{q}"] = float(torch.quantile(values, q)) if values.numel() else None
    return out


def pair_row(res: MatchResult, extras: dict[str, Tensor] | ReplicaExtras, settings: dict[str, Any], geo: Geometry, filter_keepout_m: float,
             contact_m: float, guard: str, strike: str, previous_outcome: Tensor | None, tier_has_filter: bool, drones: int) -> dict[str, Any]:
    """The D5 metrics of one pair as a plain dict (floats, counts)."""
    ex = extras if isinstance(extras, dict) else {"team_min_3d_m": extras.team_min_3d_m, "any_min_3d_m": extras.any_min_3d_m,
                                                   "guard0_drift_m": extras.guard0_drift_m, "smooth_sample_mps": extras.smooth_sample_mps}
    qs, tail = list(settings["ladder"]["quantiles"]), settings["ladder"]["tail_quantile"]
    finished = res.outcome != 0
    n = int(finished.sum())
    reach = int((res.outcome == STRIKE_WIN).sum())
    summary = summarise(res, by=())[0]
    row: dict[str, Any] = {"guard": guard, "strike": strike, "games": n, "reach": _rate(reach, n),
                           "hold_rate": summary["hold_rate"], "mean_end_step": summary["mean_end_step"]}
    win = res.outcome == STRIKE_WIN
    seconds = res.end_step[win].double() * TICK_S
    row["reach_time_s"] = {"median": float(seconds.median()) if seconds.numel() else None, "games": int(seconds.numel())}
    row["closest_cross_h"] = _quantiles(res.closest_cross_m, qs)
    row["closest_cross_3d"] = _quantiles(res.closest_cross_3d_m, qs)
    row["closest_team_3d"] = _quantiles(ex["team_min_3d_m"], qs)
    row["rule_breach"] = _rate(int(res.rule_breach.sum()), n)
    any_min = ex["any_min_3d_m"]
    row["filter_breach"] = _rate(int((any_min < filter_keepout_m).sum()), n)
    row["contact"] = _rate(int((any_min < contact_m).sum()), n)
    row["start_miss"] = _rate(int(res.start_miss.sum()), n)
    if res.upset is not None:
        row["upsets"] = _rate(int(res.upset.sum()), n)
    if tier_has_filter and "corr_count" in ex:
        steps = int(res.end_step.sum()) * drones   # no drop-out: every drone is live for every tick of a game
        count = float(ex["corr_count"].sum())
        row["filter_corrections"] = _rate(int(count), steps)
        means = ex["corr_mean_mps"][ex["corr_count"] > 0]
        row["correction_size_mps"] = {"mean": float((ex["corr_mean_mps"] * ex["corr_count"]).sum() / max(count, 1.0)),
                                      f"q{tail}": float(torch.quantile(means.double(), tail)) if means.numel() else None, "games": int(means.numel())}
    if "smooth_tick_mps" in ex:
        tick = ex["smooth_tick_mps"].double()
        row["smoothness_tick_mps"] = {"mean": float(tick.mean()), f"q{tail}": float(torch.quantile(tick, tail))}
        row["smoothness_sample_mps"] = {"mean": float(tick.mean()) * geo.hold_ticks, f"q{tail}": float(torch.quantile(tick, tail)) * geo.hold_ticks}
    elif "smooth_sample_mps" in ex:
        sample = ex["smooth_sample_mps"].double()
        row["smoothness_sample_mps"] = {"mean": float(sample.mean()), f"q{tail}": float(torch.quantile(sample, tail))}
        row["smoothness_tick_mps"] = {"mean": float(sample.mean()) / geo.hold_ticks, f"q{tail}": float(torch.quantile(sample, tail)) / geo.hold_ticks}
    drift = ex["guard0_drift_m"]
    row["guard0_drift_m"] = {"min": float(drift.min()), "p50": float(drift.median()), "max": float(drift.max())}
    if previous_outcome is not None:
        row["paired_change"] = int((previous_outcome != res.outcome).sum())
    return row


# ------------------------------------------------------------------------------------------------ reading rules and reports
def parked_hold_reading(rows: list[dict[str, Any]], threshold: float) -> dict[str, Any]:
    """Reading rule 1: ParkedGuard holds at least ``threshold`` against ApfStrike on this row."""
    found = [r for r in rows if r["guard"] == "ParkedGuard" and r["strike"] == "ApfStrike"]
    holds = [r["hold_rate"] for r in found]
    return {"parked_apf_hold_rates": holds, "stop": any(h is not None and h >= threshold for h in holds)}


def split_trigger(rung1: list[dict[str, Any]], rung2: list[dict[str, Any]]) -> dict[str, Any]:
    """Split of rung 2 (D3): any core pair of rung 2 whose Strike reach rate lies outside rung 1's Wilson interval for the same pair."""
    first = {(r["guard"], r["strike"]): r for r in rung1}
    outside = []
    for r in rung2:
        base = first.get((r["guard"], r["strike"]))
        if base is not None and not (base["reach"]["ci_low"] <= r["reach"]["rate"] <= base["reach"]["ci_high"]):
            outside.append([r["guard"], r["strike"]])
    return {"fires": bool(outside), "pairs_outside": outside}


# ------------------------------------------------------------------------------------------------ record text (committed text)
def pinned_to_local(name: str, value: float | None, protected: set[float]) -> bool:
    return value is not None and (value in protected or float(format(value, ".6g")) in protected)


def fmt(value: float | None, protected: set[float], places: int = PLACES) -> str:
    """A number as record text: rounded, and "at the local value" when it equals or nearly equals a protected value."""
    if value is None:
        return "n/a"
    near = near_relative()
    for p in protected:
        if p and math.isclose(value, p, rel_tol=near):
            return LOCAL_VALUE
    text = f"{value:.{places}f}"
    for p in protected:
        if p and math.isclose(float(text), p, rel_tol=near):
            return LOCAL_VALUE
    return text


def fmt_rate(r: dict[str, Any], protected: set[float]) -> str:
    return f"{r['k']}/{r['n']} [{fmt(r['ci_low'], protected)}, {fmt(r['ci_high'], protected)}]"


def check_text(text: str, protected: set[float]) -> None:
    """Raise if committed text holds a decimal equal to a protected value (the ``check_payload`` rule on a string)."""
    check_payload({"text": text}, protected)


def sha_of(paths: list[Path]) -> dict[str, str]:
    return {Path(p).name: file_sha256(p) for p in paths}


# ------------------------------------------------------------------------------------------------ videos (plan D6)
def pick_video_slots(outcome: Tensor, slots: int) -> list[tuple[int, str]]:
    """Among the first ``slots`` games: the first Strike win and the first hold (kind "strike_win" / "hold"); a kind with no game is left out."""
    found = []
    head = outcome[:slots]
    for want, kind in ((STRIKE_WIN, "strike_win"), (GUARD_WIN, "hold")):
        hits = (head == want).nonzero()
        if hits.numel():
            found.append((int(hits[0, 0]), kind))
    return found


def interpolate_to_ticks(units: Tensor, hold_ticks: int) -> Tensor:
    """[steps + 1, M, 2] partner-step positions -> [steps x hold_ticks + 1, M, 2] with one frame per simulator tick (linear)."""
    frames = [units[0:1]]
    for k in range(units.shape[0] - 1):
        for sub in range(1, hold_ticks + 1):
            frames.append((units[k] + (units[k + 1] - units[k]) * (sub / hold_ticks))[None])
    return torch.cat(frames)


def video_clips(res: MatchResult, extras: dict[str, Tensor] | ReplicaExtras, geo: Geometry, slots: int, replica: bool, height_m: float
                ) -> list[dict[str, Any]]:
    """Clips of the pair: {slot, kind, outcome, end_step, closest_cross_m, pos_m [ticks + 1, M, 3]} (host tensors, metres, top-down)."""
    clips = []
    for slot, kind in pick_video_slots(res.outcome, slots):
        end = int(res.end_step[slot])
        if replica:
            units = extras.positions_units[: end // geo.hold_ticks + 1, slot]
            xy = interpolate_to_ticks(units, geo.hold_ticks) * geo.scale_m_per_unit
            pos = torch.cat((xy, torch.full((*xy.shape[:2], 1), height_m)), dim=-1)
        else:
            pos = extras["video"][: end + 1, slot]
        clips.append({"slot": slot, "kind": kind, "outcome": int(res.outcome[slot]), "end_step": end,
                      "closest_cross_m": float(res.closest_cross_m[slot]), "pos_m": pos.clone()})
    return clips


def clip_recording(clip: dict[str, Any], geo: Geometry, guards: int, strikes: int, guard: str, strike: str, label: str, seed: int):
    """A ``viz.replay.Recording`` of one clip (top-down; the zone at the arena centre, the arena the fixed hangar square)."""
    from ..viz.replay import Recording
    pos = clip["pos_m"].numpy()
    return Recording(pos, np.ones(pos.shape[:2], bool), np.zeros(2), geo.zone_radius_m, geo.side_m / 2, clip["outcome"], clip["end_step"],
                     guards, strikes, "hangar", label, guard, strike, seed, clip["slot"], clip["closest_cross_m"])


# ------------------------------------------------------------------------------------------------ committed tables
PINNED_NOTE = "Values that equal a local value read \"at the local value\" (the full value stays in the git-ignored scores.json)."


def paired_against(pairs: list[dict[str, Any]], previous: Any, current: Any) -> list[dict[str, Any]]:
    """Copies of ``pairs`` whose ``paired_change`` is the number of games whose outcome differs between two ``per_game.npz`` files (same pair, same slot)."""
    out = []
    for r in pairs:
        key = f"{r['guard']}__{r['strike']}__outcome"
        changed = int((previous[key] != current[key]).sum()) if key in previous.files else None
        out.append({**r, "paired_change": changed})
    return out


def paired_against_nearest(pairs: list[dict[str, Any]], previous: list[Any], current: Any) -> list[dict[str, Any]]:
    """Like :func:`paired_against`, but ``previous`` is a list of ``per_game.npz`` files, nearest row first: each pair is compared with the first
    file that holds it (a row that ran fewer pairs than its neighbour, e.g. control row 5a, leaves the rest to the row before it)."""
    out = []
    for r in pairs:
        key = f"{r['guard']}__{r['strike']}__outcome"
        source = next((p for p in previous if key in p.files), None)
        out.append({**r, "paired_change": int((source[key] != current[key]).sum()) if source is not None else None})
    return out


def rung_table_md(pairs: list[dict[str, Any]], protected: set[float], coarse_time: bool = False, vs_row: str | None = None) -> str:
    """The markdown table of one row for a committed record: rates as ``k/n`` with their Wilson 95 % interval, every number passed through
    :func:`fmt` (a protected value reads "at the local value"). Closest approaches and the reach time are lengths and seconds. ``coarse_time``:
    the reach time in whole seconds (rows whose games end only on partner-step boundaries: replica and jump rows, where finer values would show the
    step length). ``vs_row``: the row the last column compares with."""
    versus = f"Games whose outcome differs from row {vs_row}" if vs_row else "Games whose outcome differs from the row before"
    head = ("| Guard | Strike | Strike reach, k/n [95 % interval] | Reach time, median s | Closest approach Guard-Strike 3-D, min / p5 / p50 m | "
            f"Rule breach | Filter breach | Contact | Start miss | {versus} |")
    lines = [head, "|" + "---|" * (head.count("|") - 1)]
    for r in pairs:
        q = r["closest_cross_3d"]
        keys = sorted(k for k in q if k.startswith("q"))
        close = " / ".join(fmt(v, protected) for v in (q["min"], *(q[k] for k in keys)))
        seconds = r["reach_time_s"]["median"]
        if coarse_time:   # whole seconds: a bare integer cannot carry the step length, and check_text looks at decimals only
            time_text = "n/a" if seconds is None else str(round(seconds))
        else:
            time_text = fmt(seconds, protected)
        lines.append("| " + " | ".join([r["guard"], r["strike"], fmt_rate(r["reach"], protected), time_text, close,
                                          fmt_rate(r["rule_breach"], protected), fmt_rate(r["filter_breach"], protected), fmt_rate(r["contact"], protected),
                                          fmt_rate(r["start_miss"], protected), str(r.get("paired_change", "n/a"))]) + " |")
    return "\n".join(lines) + "\n"


def extras_table_md(pairs: list[dict[str, Any]], protected: set[float]) -> str:
    """Same-team approach, filter correction share and size, smoothness per tick, and the parked Guard's drift. (The per-sample smoothness differs from
    the per-tick one by the hold length, so it is kept out of committed tables; both are in scores.json.)"""
    head = ("| Guard | Strike | Same-team approach 3-D, min / p5 / p50 m | Filter corrections k/n [95 %] | Correction size mean / p95 m/s | "
            "Smoothness (change of the command per drone per tick) mean / p95 m/s | Guard 0 drift min / p50 / max m |")
    lines = [head, "|" + "---|" * (head.count("|") - 1)]
    for r in pairs:
        q = r["closest_team_3d"]
        keys = sorted(k for k in q if k.startswith("q"))
        team = " / ".join(fmt(v, protected) for v in (q["min"], *(q[k] for k in keys)))
        corr = fmt_rate(r["filter_corrections"], protected) if "filter_corrections" in r else "n/a"
        size = r.get("correction_size_mps")
        size_text = " / ".join(fmt(v, protected) for v in size.values() if not isinstance(v, int) or isinstance(v, bool)) if size else "n/a"
        tick = r["smoothness_tick_mps"]   # the per-sample value is the per-tick one times the hold length: it stays in scores.json
        d = r["guard0_drift_m"]
        lines.append("| " + " | ".join([r["guard"], r["strike"], team, corr, size_text,
                                          " / ".join(fmt(v, protected) for v in tick.values()),
                                          " / ".join(fmt(d[k], protected) for k in ("min", "p50", "max"))]) + " |")
    return "\n".join(lines) + "\n"
