"""The L1 side-track figure reads its numbers from the score-matrix runs' results.json and refuses runs whose controls
did not all pass."""
import json
import sys

import pytest

from _ste_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import make_ste_l1_side_figure as fig  # noqa: E402


def row(opponent, k, script_k, script_name="strike_straight"):
    ci = lambda x: [x / 1000 - 0.02, x / 1000 + 0.03]  # noqa: E731
    return {"opponent": opponent, "k": k, "n": 1000, "ci": ci(k),
            "best_script": {"name": script_name, "k": script_k, "n": 1000, "ci": ci(script_k)}}


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
                     "--l111", str(r["l111"]), "--out", str(out)]) == 0
    assert out.stat().st_size > 10_000
