"""STE task L2.5: the reading script (scripts/ste_l25_read.py) on a tiny synthetic run folder (CPU, seconds).

The script applies the frozen spec ste_learning/drafts/L2_5_SPEC.md to the screen's run folder: plumbing checks P-b and
P-c from the per-game arrays, readings 1-4 with the spec's words (Wilson 95 % intervals that do not overlap), the paired
discordant-game readout, and the withholding table when a plumbing check fails. Here every number is made up so that
each word has a known answer."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

from svg_training.core.rewards import GUARD_WIN, STRIKE_WIN
from svg_training.ste import sweep

sys.path.insert(0, str(sweep.ROOT / "scripts"))
import ste_l25_read as read  # noqa: E402

GUARDS = ["guard_parked_centre", "guard_parked_ring", "guard_mark_edge", "guard_mirror", "guard_field"]
STRIKES = ["strike_straight", "strike_flank", "strike_high", "strike_low", "strike_sacrifice", "strike_converge"]
N = 200                                                   # games per cell in the fixture


def _cell_games(holds: int, end: int = 50, closest: float = 1.6) -> dict:
    outcome = np.full(N, STRIKE_WIN, dtype=np.int8)
    outcome[:holds] = GUARD_WIN
    return {"outcome": outcome, "end_step": np.full(N, end, dtype=np.int64),
            "closest_3d_m": np.full(N, closest, dtype=np.float32)}


def _write_group(run: Path, name: str, cells: list, games: list[dict], extra_row: dict | None = None) -> None:
    pg = {k: np.concatenate([g[k] for g in games]) for k in games[0]}
    (run / "cells").mkdir(parents=True, exist_ok=True)
    np.savez_compressed(run / "cells" / f"{name}__b00.npz", **pg)
    rows = []
    for (g, s), x in zip(cells, games):
        wins = int((x["outcome"] == GUARD_WIN).sum())
        rows.append({"guard": g, "strike": s, "games": N, "unfinished": 0, "guard_wins": wins,
                     "closest_cross_3d_m": 1.6, "rule_breach_rate": 0.0, "filter_rate": 0.02,
                     "filter_active_share": 0.05, "pushed_tag_share": 0.02, **(extra_row or {})})
    (run / "cells" / f"{name}__b00.json").write_text(json.dumps({"cells": [list(c) for c in cells], "rows": rows}))


def _holds(still: int, ring: int, mark: int, other: int) -> dict:
    return {"guard_parked_centre": still, "guard_parked_ring": ring, "guard_mark_edge": mark, "guard_mirror": other,
            "guard_field": other}


def make_run(tmp_path: Path, *, gy_changes_tag_off: bool = True, landing_changes: bool = True,
             still_with_tag: int = 100, still_without_tag: int = 10, mark: int = 160) -> Path:
    """A run folder: every tag-on group 5 x 6 cells, the tag-off groups 2 x 6, N games per cell."""
    run = tmp_path / "run"
    full = [(g, s) for g in GUARDS for s in STRIKES]
    parked = [(g, s) for g in GUARDS[:2] for s in STRIKES]
    base = _holds(still_with_tag, still_with_tag, mark, 170)

    def group(name, holds, end=50, closest=1.6, shift_one=None):
        games = []
        for g, s in full:
            x = _cell_games(holds[g], end, closest)
            if shift_one is not None and (g, s) == ("guard_mark_edge", "strike_straight"):
                x["outcome"][holds[g]] = shift_one     # one paired game flips
            games.append(x)
        _write_group(run, name, full, games)

    group("ctl_reference_replay", base)
    group("landing", base, end=50 if not landing_changes else 51, shift_one=GUARD_WIN if landing_changes else None)
    group("gy", base, closest=1.61)
    group("landing_gy", base, end=50 if not landing_changes else 51, closest=1.61)
    off = [_cell_games(still_without_tag) for _ in parked]
    _write_group(run, "ctl_tag_off_landing", parked, off)
    off_gy = [_cell_games(still_without_tag, end=60 if gy_changes_tag_off else 50) for _ in parked]
    _write_group(run, "ctl_tag_off_landing_gy", parked, off_gy)
    variants = [{"variant": v, "H": 0.8, "R": 0.2, "g_star": "guard_mark_edge", "s_star": "strike_straight"}
                for v in ("landing", "gy", "landing_gy")]
    info = [{"variant": "ctl_reference_replay", "H": 0.8, "R": 0.2, "g_star": "guard_mark_edge",
             "s_star": "strike_straight"}]
    (run / "results.json").write_text(json.dumps({"controls_all_pass": True,
                                                  "shortlist": {"variants": variants, "info_reference": info}}))
    return run


def test_the_words_follow_wilson_intervals_that_do_not_overlap():
    assert read.compare(600, 400, 1000, 1000) == "above"
    assert read.compare(400, 600, 1000, 1000) == "below"
    assert read.compare(500, 520, 1000, 1000) == "not distinguishable"


def test_plumbing_passes_when_the_rules_change_games(tmp_path):
    out = read.read_run(make_run(tmp_path))
    assert out["plumbing"]["P-b"]["holds"] and out["plumbing"]["P-c"]["holds"]
    assert out["plumbing"]["P-b"]["games_differ"] == 12 * N                    # every tag-off game's end step moved
    assert not out["withheld"]


def test_a_failed_p_b_withholds_the_option_b_words(tmp_path):
    out = read.read_run(make_run(tmp_path, gy_changes_tag_off=False))
    assert not out["plumbing"]["P-b"]["holds"]
    assert out["plumbing"]["P-b"]["words"] == "option B not shown to reach the game"
    assert out["reading3"]["withheld"] and all(p["withheld"] for p in out["reading3"]["pairs"])
    assert out["reading1"]["landing_gy"]["words_withheld"] and out["reading1"]["gy"]["words_withheld"]
    assert not out["reading1"]["landing"]["words_withheld"]
    r4 = {p["name"]: p for p in out["reading4"]["pairs"]}
    assert r4["landing_gy v gy"]["withheld"] and not r4["landing v base"]["withheld"]
    r2 = {r["rule_set"]: r for r in out["reading2"]["rule_sets"]}
    assert r2["landing_gy"]["withheld"] and not r2["landing"]["withheld"]


def test_a_failed_p_c_withholds_reading_4_and_the_landing_pair_of_reading_3(tmp_path):
    out = read.read_run(make_run(tmp_path, landing_changes=False))
    assert not out["plumbing"]["P-c"]["holds"]
    assert out["plumbing"]["P-c"]["words"] == ("landing not shown to reach the game; no landing word (reading 4) is "
                                               "written")
    assert out["reading4"]["withheld"]
    r3 = {p["name"]: p for p in out["reading3"]["pairs"]}
    assert r3["landing_gy v landing"]["withheld"] and not r3["gy v base"]["withheld"]


def test_reading_1_compares_the_still_guard_with_each_moving_script_by_name(tmp_path):
    out = read.read_run(make_run(tmp_path, still_with_tag=100, mark=160))
    r1 = out["reading1"]["landing"]
    assert r1["still"]["v"]["guard_mark_edge"]["word"] == "still Guard below mark_edge"
    assert r1["still"]["v"]["guard_mirror"]["word"] == "still Guard below mirror"
    assert r1["still"]["worst"] == {"holds": 100, "games": N, "strike": "strike_straight"}
    out = read.read_run(make_run(tmp_path / "b", still_with_tag=160, mark=160))
    assert out["reading1"]["landing"]["still"]["v"]["guard_mark_edge"]["word"] == \
        "still Guard not distinguishable from mark_edge"


def test_the_risk_word_needs_both_readings(tmp_path):
    favours = read.read_run(make_run(tmp_path, still_with_tag=160, still_without_tag=10, mark=160))
    for rs in ("landing", "landing_gy"):
        assert favours["risk"][rs]["word"] == ("the 1.6 m tag favours a Guard team that stands still, against "
                                               "scripted Strikes, in this rule set")
    below = read.read_run(make_run(tmp_path / "b", still_with_tag=100, still_without_tag=10, mark=160))
    assert below["risk"]["landing"]["word"] == "not seen with scripted Strikes in this rule set"
    neither = read.read_run(make_run(tmp_path / "c", still_with_tag=12, still_without_tag=10, mark=14))
    assert neither["risk"]["landing"]["word"] is None                            # stated side by side, no risk word
    assert "gy" not in favours["risk"] and "base" not in favours["risk"]         # only the arms with a tag-off twin


def test_reading_2_reads_the_tag_on_against_the_tag_off_twin(tmp_path):
    out = read.read_run(make_run(tmp_path, still_with_tag=100, still_without_tag=10))
    r2 = {r["rule_set"]: r for r in out["reading2"]["rule_sets"]}
    assert r2["landing"]["worst"]["still"]["word"] == "the tag raises the parked Guard's hold"
    assert r2["landing"]["cells"][0]["word"] == "the tag raises the parked Guard's hold"


def test_the_paired_readout_counts_discordant_games_and_their_direction(tmp_path):
    out = read.read_run(make_run(tmp_path))
    r4 = {p["name"]: p for p in out["reading4"]["pairs"]}
    cell = next(c for c in r4["landing v base"]["cells"] if (c["guard"], c["strike"]) == ("guard_mark_edge",
                                                                                          "strike_straight"))
    assert cell["paired"] == {"hold_to_reach": 0, "reach_to_hold": 1, "other_outcome": 0,
                              "same_outcome_end_step_changed": N - 1}
    assert r4["landing v base"]["paired_by_guard"]["guard_mark_edge"]["reach_to_hold"] == 1
    assert r4["landing v base"]["paired_total"]["reach_to_hold"] == 1
    assert cell["word"] == "no change detected"                                  # one game: below what Wilson sees


def test_main_writes_markdown_and_json_into_the_run_folder(tmp_path):
    run = make_run(tmp_path)
    assert read.main(["--run-dir", str(run)]) == 0
    md = (run / "l25_readings.md").read_text()
    data = json.loads((run / "l25_readings.json").read_text())
    assert data["plumbing"]["P-c"]["holds"]
    for text in ("P-b", "P-c", "Reading 1", "Reading 2", "Reading 3", "Reading 4", "hold → reach",
                 "not shown (not recorded by the driver)", "no change larger than this test can see"):
        assert text in md, text
