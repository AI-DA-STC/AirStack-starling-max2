"""The L1 side-track figure reads its numbers from the score-matrix runs' results.json and refuses runs whose controls
did not all pass."""
import json
import sys

import pytest

from _ste_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import make_ste_l1_side_figure as fig  # noqa: E402


def row(opponent, k, script_k, script_name="strike_straight", tag_m=1.149, script_tag_m=1.142):
    ci = lambda x: [x / 1000 - 0.02, x / 1000 + 0.03]  # noqa: E731
    script = {"name": script_name, "cell": ["guard_field", script_name], "k": script_k, "n": 1000, "ci": ci(script_k),
              "tag_stats": {"tag_distance_median_m": script_tag_m}}
    return {"opponent": opponent, "k": k, "n": 1000, "ci": ci(k), "tag_stats": {"tag_distance_median_m": tag_m},
            "best_script": script, "script_cells": [script]}


def score_run(tmp_path, name, games, complete=True, controls_pass=True):
    d = tmp_path / name
    d.mkdir()
    (d / "results.json").write_text(json.dumps({"complete": complete, "controls_pass": controls_pass,
                                                "games": {g: {"rows": r} for g, r in games.items()}}))
    return d


def l113_run(tmp_path, name, k30, k120):
    return score_run(tmp_path, name, {"tag_1p15_30s": [row("guard_mirror", 1, 604), row("guard_field", k30, 355)],
                                      "tag_1p15_120s": [row("guard_field", k120, 355)]})


def l111_run(tmp_path):
    return score_run(tmp_path, "l111", {"base_120s": [row(g, 100 + i, 200 + i, "strike_low")
                                                      for i, g in enumerate(fig.GUARDS)]})


def runs(tmp_path):
    return {"t52": l113_run(tmp_path, "t52", 145, 103), "arm_a": l113_run(tmp_path, "a", 199, 76),
            "arm_b": l113_run(tmp_path, "b", 94, 99), "l111": l111_run(tmp_path)}


def test_values_come_from_the_files(tmp_path):
    d = fig.panel_data(runs(tmp_path))
    assert d["l113"]["tag_1p15_30s"]["arm_a"] == pytest.approx((199, 179.0, 229.0))
    assert d["l113"]["tag_1p15_120s"]["t52"][0] == 103 and d["l113"]["tag_1p15_120s"]["arm_b"][0] == 99
    assert d["script"]["tag_1p15_30s"][0] == 355
    assert d["l111"]["guard_field"]["team"][0] == 102 and d["l111"]["guard_field"]["script"][0] == 202
    assert d["l111"]["guard_parked_ring"]["script_name"] == "strike_low"


def test_refuses_a_run_with_a_failed_control(tmp_path):
    r = runs(tmp_path)
    r["arm_b"] = score_run(tmp_path, "bad", {"tag_1p15_30s": [], "tag_1p15_120s": []}, controls_pass=False)
    with pytest.raises(SystemExit):
        fig.panel_data(r)


def test_main_writes_the_png(tmp_path):
    r, out = runs(tmp_path), tmp_path / "f.png"
    assert fig.main(["--t52", str(r["t52"]), "--arm-a", str(r["arm_a"]), "--arm-b", str(r["arm_b"]),
                     "--l111", str(r["l111"]), "--out", str(out), "--figure", "l113"]) == 0
    assert out.stat().st_size > 10_000


def delay_runs(tmp_path):
    r = runs(tmp_path)
    r["t52_clamp"] = score_run(tmp_path, "tc", {"tag_1p15_120s": [row("guard_field", 152, 355)]})
    r["arm_a_clamp"] = score_run(tmp_path, "ac", {"tag_1p15_120s": [row("guard_field", 172, 355)]})
    games = ("tag_1p15_delay0", "tag_1p15_120s", "tag_1p15_delay0p30")
    r["l115_t55"] = score_run(tmp_path, "t55", {g: [row("guard_field", k, 355, script_tag_m=m)] for g, k, m in
                                                zip(games, (133, 134, 148), (1.1452, 1.1422, 1.1323))})
    r["l115_t54"] = score_run(tmp_path, "t54", {g: [row("strike_straight", k, 645, "guard_field", tag_m=m)] for g, k, m in
                                                zip(games, (551, 572, 583), (1.1453, 1.1418, 1.1345))})
    return r


def test_delay_values_come_from_the_files(tmp_path):
    d = fig.delay_data(delay_runs(tmp_path))
    assert d["t52"]["clamped 120 s"][0] == 152 and d["t52"]["plain 120 s"][0] == 103 and d["t52"]["30 s game"][0] == 145
    assert d["arm_a"]["clamped 120 s"][0] == 172 and d["arm_a"]["plain 120 s"][0] == 76
    assert [w[0] for w in d["wins"]["T55"]] == [133, 134, 148]          # delay 0, 0.1482, 0.30 s in that order
    assert [w[0] for w in d["wins"]["T54"]] == [551, 572, 583]
    assert d["tag"]["script"] == [1.1452, 1.1422, 1.1323] and d["tag"]["T54"][2] == 1.1345
    assert d["script"][0] == 355


def test_main_writes_the_second_png(tmp_path):
    r, out = delay_runs(tmp_path), tmp_path / "g.png"
    args = ["--t52", str(r["t52"]), "--arm-a", str(r["arm_a"]), "--t52-clamp", str(r["t52_clamp"]),
            "--arm-a-clamp", str(r["arm_a_clamp"]), "--l115-t55", str(r["l115_t55"]), "--l115-t54", str(r["l115_t54"]),
            "--out2", str(out), "--figure", "l114_l115"]
    assert fig.main(args) == 0 and out.stat().st_size > 10_000
