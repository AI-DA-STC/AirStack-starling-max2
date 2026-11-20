#!/usr/bin/env python
"""Follow-up checks on the L0.11 Screening sweep (T44) before L0.12 is designed (QC results read, runs/ste_l11_qc.md;
lead's brief 21 Nov 2026). CPU only, INFO, observed in the training simulator.

    ste_l011_followups.py --run-dir <T44 run folder (read only)> --out <folder> [--check all|tie|composition|identical|
                          decision|wilson] [--games 1000] [--figures-out docs/figures/ste_l011]

Every replay starts from T44's OWN starts: the start positions stored per game in the run's cell files (never redrawn:
a CPU generator does not reproduce the CUDA draw), one cell at a time on the CPU. A replay is "a CPU replay of T44's
starts", not T44: the per-game agreement with T44's outcomes is reported beside every replayed number.

Checks (results in <out>/followups.json, one entry per check):
1. ``tie``: the tie rule's share of holds. Tags are applied before the zone test, and at the base rules the zone radius
   equals the tag radius (1.6 m). A pass-through recorder around the game's tag function (it returns the game's own
   result unchanged; tested bit for bit) keeps the positions each tag was decided on, so for every hold of a slot's first
   game we count whether ANY tag hit a Strike drone already horizontally inside the zone (a zone-first order would have
   made that game a reach), and whether the LAST tag step did. Known answer checked on every such tag: that Strike was
   outside the zone one step earlier (else it would have reached then).
2. ``composition``: holds leaving no Guard drone and game length per cell (``ste/sweep.hold_composition``), added to the
   run's rows from its cell files; the results table and the figures are regenerated with the new columns into
   --figures-out. Every number that was already in the table is unchanged (checked).
3. ``identical``: per-game equality (outcome, end step, tags, Strikes left, closest 3-D approach) of chosen columns from
   the cell files, and the height the high and low Strikes actually flew in a replay (does the climb or descent play any
   part on tier 1?).
4. ``decision``: the best scripted Guard against the best scripted Strike, every tick (0.05 s) and with every player's
   command held for the sheet's decision period (timing.decision_s / one tick = 12 ticks, 0.6 s, both teams, phased from
   each game's start), same starts; hold and reach with Wilson intervals, and the games that change outcome.
5. ``wilson``: the base reach count of the best scripted Strike against the best scripted Guard from the cell file, with
   its 95 % Wilson interval (core/metrics.wilson_interval)."""
from __future__ import annotations

import argparse
import contextlib
import json
import math
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
sys.path.insert(0, str(ROOT / "scripts"))

import numpy as np  # noqa: E402
import torch  # noqa: E402

from svg_training.core import game as game_module  # noqa: E402
from svg_training.core.game_config import TICK_S  # noqa: E402
from svg_training.core.metrics import wilson_interval  # noqa: E402
from svg_training.core.rewards import GUARD_WIN, RUNNING, STRIKE_WIN  # noqa: E402
from svg_training.ste import sweep  # noqa: E402
from svg_training.ste.game_spec import load_game_spec  # noqa: E402

CHECK_EVERY = 100
EXACT = ("outcome", "end_step", "tags", "strikes_left")
TIE_PAIRS = [("base", "guard_mark_edge", "strike_straight"), ("base", "guard_field", "strike_converge"),
             ("tag_1p2", "guard_field", "strike_straight"), ("tag_1p4", "guard_mirror", "strike_low")]
DECISION_PAIRS = [("base", "guard_mark_edge", "strike_straight"), ("tag_1p2", "guard_field", "strike_straight"),
                  ("tag_1p4", "guard_mirror", "strike_low"), ("tag_1p4", "guard_mirror", "strike_straight")]
IDENTICAL = [("tag_1p2", [("guard_field", s) for s in ("strike_straight", "strike_high", "strike_low")]),
             ("tag_1p4", [(g, s) for s in ("strike_straight", "strike_flank", "strike_high", "strike_low",
                                           "strike_sacrifice", "strike_converge")
                          for g in ("guard_parked_centre", "guard_parked_ring")])]
HEIGHT_PAIRS = [("tag_1p2", "guard_field", "strike_high"), ("tag_1p2", "guard_field", "strike_low"),
                ("size_1v1", "guard_parked_centre", "strike_high")]


def decision_ticks() -> int:
    """The sheet's decision period in ticks: timing.decision_s / TICK_S (0.6 / 0.05 = 12)."""
    return round(load_game_spec()[0].value("timing.decision_s") / TICK_S)


# ================================================================================================ the run's cell files
def cell_index(run_dir: Path) -> dict:
    """(group, guard, strike) -> {"npz", "slice", "game", "size", "batch"} from every batch json of the run."""
    out = {}
    for path in sorted((run_dir / "cells").glob("*.json")):
        data = json.loads(path.read_text())
        n = data["games"] // len(data["cells"])
        for k, (g, s) in enumerate(data["cells"]):
            out.setdefault((data["group"], g, s), {"npz": path.with_suffix(".npz"), "slice": slice(k * n, (k + 1) * n),
                                                   "game": data["game"], "size": data["size"], "batch": data["batch"],
                                                   "start_sha256": data["start_sha256"][k]})
    return out


def cell_games(index: dict, key: tuple) -> dict:
    ref = index[key]
    z = np.load(ref["npz"])
    return {k: z[k][ref["slice"]] for k in z.files}


# ================================================================================================ replay machinery
class FixedStartsGame(sweep.SweepGame):
    """``SweepGame`` of one cell whose first games start from given positions (T44's, from its cell files) through the
    starts hook; later games (after a slot's first) start there too, and are not counted."""

    def __init__(self, cfg, starts_m: torch.Tensor, miss: torch.Tensor, guards: int, strikes: int, seed: int):
        self._fixed = (starts_m, miss)
        super().__init__(cfg, 1, starts_m.shape[0], guards, strikes, "cpu", seed)

    def _draw_starts(self, arenas):
        return self._fixed[0].clone(), self._fixed[1].clone()


class HoldPlayer:
    """Holds a player's command for ``hold_ticks`` ticks, per game, phased from the game's start (its first tick decides).
    hold_ticks 1 = the player itself (tested bit for bit)."""

    def __init__(self, inner, hold_ticks: int):
        self.inner, self.hold, self.team, self.name = inner, int(hold_ticks), inner.team, inner.name
        self.tick = None
        self.held = None

    def reset(self, games: torch.Tensor) -> None:
        self.inner.reset(games)
        if self.tick is None:
            self.tick = torch.zeros(games.shape[0], dtype=torch.long)
        self.tick = torch.where(games, torch.zeros_like(self.tick), self.tick)

    def act(self, obs: torch.Tensor) -> torch.Tensor:
        a = self.inner.act(obs)
        decide = (self.tick % self.hold == 0)[:, None, None]
        self.held = a if self.held is None else torch.where(decide, a, self.held)
        self.tick = self.tick + 1
        return self.held


class TagRecorder:
    """Pass-through recorder around the game's tag function: returns the game's own result unchanged and keeps the
    positions and the tagged drones of the latest call."""

    def __init__(self):
        self.last = None

    @contextlib.contextmanager
    def installed(self):
        original = game_module.proximity_tags

        def recording(pos_m, alive, guards, radius_m, guard_survives):
            out = original(pos_m, alive, guards, radius_m, guard_survives)
            self.last = (pos_m.clone(), out[0].clone())
            return out
        game_module.proximity_tags = recording
        try:
            yield self
        finally:
            game_module.proximity_tags = original


def replay(cfg, size: str, cell: tuple, starts_m: np.ndarray, miss: np.ndarray, seed: int, ticks_cap: int,
           hold_ticks: int = 1, record_tags: bool = False) -> dict:
    """Play one cell from the given starts on the CPU; per first game: outcome, end_step, tags, guards_removed,
    strikes_left, closest_3d_m, and (record_tags) tie_any, tie_last, tie_prev_inside; strike_dz_max_m (largest height
    change of a live Strike drone from its start)."""
    guards, strikes = sweep.parse_size(size)
    n = starts_m.shape[0]
    game = FixedStartsGame(cfg, torch.as_tensor(starts_m, dtype=torch.float32), torch.as_tensor(miss, dtype=torch.bool),
                           guards, strikes, seed)
    gp = HoldPlayer(sweep.split_players((cell,), "guard", cfg, n, "cpu", seed), hold_ticks)
    sp = HoldPlayer(sweep.split_players((cell,), "strike", cfg, n, "cpu", seed), hold_ticks)
    recorder = TagRecorder()
    radius = None
    outcome = torch.full((n,), RUNNING, dtype=torch.int8)
    end_step = torch.zeros(n, dtype=torch.long)
    closest = torch.full((n,), math.inf)
    tie_any = torch.zeros(n, dtype=torch.bool)
    tie_last = torch.zeros(n, dtype=torch.bool)
    tie_prev_inside = torch.zeros(n, dtype=torch.long)
    dz_max = torch.zeros(n)
    with (recorder.installed() if record_tags else contextlib.nullcontext()):
        obs = game.reset()
        radius = game.arenas.zone_radius_m[:, None]
        z0 = game.pos_m[:, guards:, 2].clone()
        everyone = torch.ones(n, dtype=torch.bool)
        gp.reset(everyone)
        sp.reset(everyone)
        finished = torch.zeros(n, dtype=torch.bool)
        prev_xy = game.pos_m[:, guards:, :2].clone()
        for step in range(1, ticks_cap + 1):
            out = game.step({"guard": gp.act(obs["guard"]), "strike": sp.act(obs["strike"])})
            active = ~finished
            if record_tags:
                pos, tagged = recorder.last
                d = pos[:, guards:, :2].norm(dim=-1)
                hit = tagged[:, guards:]
                inside = hit & (d <= radius)
                any_tag = hit.any(dim=1) & active
                tie_any |= active & inside.any(dim=1)
                tie_last = torch.where(any_tag, inside.any(dim=1), tie_last)
                tie_prev_inside += (active[:, None] & inside & (prev_xy.norm(dim=-1) <= radius)).sum(dim=1)
            alive_s = out.info["final_alive"][:, guards:]
            z = game.pos_m[:, guards:, 2]
            dz = torch.where(alive_s, (z - z0).abs(), torch.zeros_like(z)).amax(dim=1)
            dz_max = torch.where(active, torch.maximum(dz_max, dz), dz_max)
            prev_xy = torch.where(alive_s[..., None], game.pos_m[:, guards:, :2], prev_xy)
            closest = torch.where(active, torch.minimum(closest, out.info["closest_cross_3d_m"]), closest)
            ended = active & out.done
            outcome = torch.where(ended, out.outcome, outcome)
            end_step = torch.where(ended, out.end_step, end_step)
            finished |= out.done
            gp.reset(out.done)
            sp.reset(out.done)
            obs = out.obs
            if step % CHECK_EVERY == 0 and bool(finished.all()):
                break
    result = {"outcome": outcome.numpy(), "end_step": end_step.numpy(), "tags": game.tags.numpy(),
              "guards_removed": game.guards_removed.numpy(),
              "strikes_left": torch.where(game.first_done, game.strikes_left,
                                          game.alive[:, guards:].sum(dim=1)).numpy(),
              "closest_3d_m": closest.numpy(), "strike_dz_max_m": dz_max.numpy()}
    if record_tags:
        result.update(tie_any=tie_any.numpy(), tie_last=tie_last.numpy(), tie_prev_inside=tie_prev_inside.numpy())
    return result


def agreement(a: dict, b: dict) -> dict:
    """Games whose outcome, end step, tags or Strikes left differ between two per-game records."""
    differ = np.zeros(len(a["outcome"]), dtype=bool)
    for key in EXACT:
        differ |= np.asarray(a[key]) != np.asarray(b[key])
    return {"games": int(len(differ)), "differ": int(differ.sum()),
            "outcome_differ": int(np.sum(np.asarray(a["outcome"]) != np.asarray(b["outcome"])))}


def rates(pg: dict) -> dict:
    outcome = np.asarray(pg["outcome"])
    n = int(np.sum(outcome != RUNNING))
    holds, reaches = int(np.sum(outcome == GUARD_WIN)), int(np.sum(outcome == STRIKE_WIN))
    return {"games": n, "unfinished": int(len(outcome) - n), "holds": holds, "reaches": reaches,
            "hold_ci": list(wilson_interval(holds, n)), "reach_ci": list(wilson_interval(reaches, n))}


# ================================================================================================ the checks
def _setup(run_dir: Path, games: int | None):
    gates = sweep.load_gates(run_dir / "gates.toml")
    return gates, cell_index(run_dir), games or int(gates.run["games_per_cell"])


def _replay_cell(gates, index, key, games, **kwargs):
    t44 = cell_games(index, key)
    ref = index[key]
    cfg = sweep.variant_cfg(gates, ref["game"])
    pg = replay(cfg, ref["size"], key[1:], t44["start_pos_m"][:games], t44["start_miss"][:games], int(gates.run["seed"]),
                int(gates.run["ticks_cap"]), **kwargs)
    return pg, {k: v[:games] for k, v in t44.items()}, ref


def check_tie(run_dir: Path, games: int | None = None) -> list[dict]:
    gates, index, games = _setup(run_dir, games)
    out = []
    for key in TIE_PAIRS:
        pg, t44, ref = _replay_cell(gates, index, key, games, record_tags=True)
        holds = pg["outcome"] == GUARD_WIN
        cfg = sweep.variant_cfg(gates, ref["game"])
        out.append({"group": key[0], "guard": key[1], "strike": key[2], "start_sha256": ref["start_sha256"],
                    "tag_radius_m": cfg.tag.radius_m, "zone_radius_m": cfg.arena.zone_radius_frac[0] * cfg.arena.bands_m["lab"][0],
                    **rates(pg), "t44": rates(t44), "agreement_with_t44": agreement(pg, t44),
                    "holds_any_tag_inside_zone": int(np.sum(holds & pg["tie_any"])),
                    "holds_last_tag_inside_zone": int(np.sum(holds & pg["tie_last"])),
                    "inside_tags_already_inside_a_step_earlier": int(np.sum(pg["tie_prev_inside"]))})
    return out


def check_identical(run_dir: Path, games: int | None = None) -> dict:
    gates, index, games = _setup(run_dir, games)
    out = {"cell_files": [], "heights": []}
    for group, cells in IDENTICAL:
        base = cell_games(index, (group, *cells[0]))
        for cell in cells[1:]:
            other = cell_games(index, (group, *cell))
            ag = agreement(base, other)
            close = np.isclose(base["closest_3d_m"], other["closest_3d_m"], rtol=0, atol=1e-9) | (
                np.isinf(base["closest_3d_m"]) & np.isinf(other["closest_3d_m"]))
            out["cell_files"].append({"group": group, "a": list(cells[0]), "b": list(cell), **ag,
                                      "closest_differ": int(np.sum(~close))})
    # parked_centre against parked_ring, Strike by Strike, in tag_1p4
    pairs = {}
    for s in gates.players["strikes"]:
        ka, kb = ("tag_1p4", "guard_parked_centre", s), ("tag_1p4", "guard_parked_ring", s)
        if ka in index and kb in index:
            pairs[s] = agreement(cell_games(index, ka), cell_games(index, kb))
    out["tag_1p4_parked_centre_v_ring"] = pairs
    # every group: is strike_high (or low) identical game for game to strike_straight, per Guard script?
    same = {}
    for (group, g, s), ref in index.items():
        if s in gates.players["z_up_info"] and (group, g, "strike_straight") in index:
            ag = agreement(cell_games(index, (group, g, s)), cell_games(index, (group, g, "strike_straight")))
            same.setdefault(group, {"cells": 0, "identical": 0, "outcome_identical": 0, "outcome_differ_games": 0})
            same[group]["cells"] += 1
            same[group]["identical"] += int(ag["differ"] == 0)
            same[group]["outcome_identical"] += int(ag["outcome_differ"] == 0)
            same[group]["outcome_differ_games"] += ag["outcome_differ"]
    out["height_scripts_identical_to_straight"] = same
    for key in HEIGHT_PAIRS:
        if key not in index:
            continue
        pg, t44, ref = _replay_cell(gates, index, key, games)
        dz = pg["strike_dz_max_m"]
        out["heights"].append({"group": key[0], "guard": key[1], "strike": key[2], "games": int(len(dz)),
                               "strike_dz_max_m_median": float(np.median(dz)), "strike_dz_max_m_max": float(dz.max()),
                               "agreement_with_t44": agreement(pg, t44)})
    return out


def check_decision(run_dir: Path, games: int | None = None) -> list[dict]:
    gates, index, games = _setup(run_dir, games)
    hold = decision_ticks()
    out = []
    for key in DECISION_PAIRS:
        every, t44, ref = _replay_cell(gates, index, key, games)
        held, _, _ = _replay_cell(gates, index, key, games, hold_ticks=hold)
        flips = {"hold_to_reach": int(np.sum((every["outcome"] == GUARD_WIN) & (held["outcome"] == STRIKE_WIN))),
                 "reach_to_hold": int(np.sum((every["outcome"] == STRIKE_WIN) & (held["outcome"] == GUARD_WIN)))}
        out.append({"group": key[0], "guard": key[1], "strike": key[2], "hold_ticks": hold,
                    "hold_s": hold * TICK_S, "every_tick": rates(every), "held": rates(held), "flips": flips,
                    "every_vs_held": agreement(every, held),
                    "median_end_step": [float(np.median(every["end_step"])), float(np.median(held["end_step"]))],
                    "t44": rates(t44), "every_tick_agreement_with_t44": agreement(every, t44),
                    "z_up_info": key[2] in gates.players["z_up_info"]})
    return out


def check_wilson(run_dir: Path) -> dict:
    gates, index, _ = _setup(run_dir, None)
    t44 = cell_games(index, ("base", "guard_mark_edge", "strike_straight"))
    r = rates(t44)
    return {"cell": ["base", "guard_mark_edge", "strike_straight"], **r,
            "reach_upper_above_0p2": r["reach_ci"][1] > 0.2}


def check_composition(run_dir: Path, figures_out: Path) -> dict:
    """Add the hold composition to a scratch copy of the run's results.json (from the cell files), regenerate the results
    table and the figures into ``figures_out``; return the per-group summary and whether every old column is unchanged."""
    import make_ste_l011_figures
    import ste_sweep_l011 as driver
    gates = sweep.load_gates(run_dir / "gates.toml")
    result = json.loads((run_dir / "results.json").read_text())
    index = cell_index(run_dir)
    summary = {}
    for group in result["groups"]:
        size = group["size"]
        guards = sweep.parse_size(size)[0]
        spec = gates.group(group["name"])
        ticks = spec.ticks_cap(gates.run)
        for row in group["rows"]:
            pg = cell_games(index, (group["name"], row["guard"], row["strike"]))
            row.update(sweep.hold_composition({**pg, "game_ticks": ticks}, guards))
        if group["rows"] and group["role"] != "control":
            holds = sum(r["holds"] for r in group["rows"])
            summary[group["name"]] = {"holds": holds, "holds_no_guard_left": sum(r["holds_no_guard_left"]
                                                                                for r in group["rows"]),
                                      "timeouts": sum(r["timeouts_by_length"] for r in group["rows"]),
                                      "guards_left_in_holds": sorted({round(r["guards_left_mean_in_holds"], 3)
                                                                      for r in group["rows"]
                                                                      if r["guards_left_mean_in_holds"] is not None}),
                                      "length_median_s_range": [min(r["length_median_s"] for r in group["rows"]),
                                                                max(r["length_median_s"] for r in group["rows"])],
                                      "length_p90_s_max": max(r["length_p90_s"] for r in group["rows"])}
    figures_out.mkdir(parents=True, exist_ok=True)
    new_md = driver.render_md(result, gates)
    name = f"results_{run_dir.name}.md"
    old_md = (figures_out / name).read_text() if (figures_out / name).is_file() else (run_dir / "results.md").read_text()
    unchanged = old_columns_unchanged(old_md, new_md)
    (figures_out / name).write_text(new_md)
    with tempfile.TemporaryDirectory() as tmp:
        shutil.copytree(run_dir / "cells", Path(tmp) / "cells")
        (Path(tmp) / "results.json").write_text(json.dumps(result))
        make_ste_l011_figures.main(["--run-dir", tmp, "--out", str(figures_out)])
    return {"groups": summary, "old_columns_unchanged": unchanged, "table": str(figures_out / name)}


def old_columns_unchanged(old_md: str, new_md: str) -> dict:
    """Every table row of the old results table is a prefix (its cells, in order) of the same row in the new one."""
    def rows(md):
        return [line for line in md.splitlines() if line.startswith("| ") and not line.startswith("| Guard |")]
    old, new = rows(old_md), rows(new_md)
    prefix = sum(1 for o in old if any(n.startswith(o.rstrip("|").rstrip()) for n in new))
    return {"old_rows": len(old), "found_as_prefix": prefix}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--run-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--check", default="all", choices=["all", "tie", "composition", "identical", "decision", "wilson"])
    ap.add_argument("--games", type=int)
    ap.add_argument("--figures-out", type=Path, default=ROOT / "docs" / "figures" / "ste_l011")
    a = ap.parse_args(argv)
    torch.set_grad_enabled(False)
    a.out.mkdir(parents=True, exist_ok=True)
    path = a.out / "followups.json"
    results = json.loads(path.read_text()) if path.is_file() else {}
    todo = ["wilson", "tie", "identical", "decision", "composition"] if a.check == "all" else [a.check]
    for check in todo:
        if check == "tie":
            results["tie"] = check_tie(a.run_dir, a.games)
        elif check == "identical":
            results["identical"] = check_identical(a.run_dir, a.games)
        elif check == "decision":
            results["decision"] = check_decision(a.run_dir, a.games)
        elif check == "wilson":
            results["wilson"] = check_wilson(a.run_dir)
        else:
            results["composition"] = check_composition(a.run_dir, a.figures_out)
        path.write_text(json.dumps(results, indent=1))
        print(f"{check}: written to {path}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
