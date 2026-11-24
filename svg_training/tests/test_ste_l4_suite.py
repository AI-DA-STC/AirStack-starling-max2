"""STE L3-L6 pipeline check, task L4.2: the scoring suite on known players (``scripts/ste_l4_suite.py``; spec
ste_learning/drafts/L3_L6_PIPELINE_SPEC.md section 3). CPU, small: each route's untrained team (velocity: the
zero-mean still team; skills: free + the first drone skill) and a script team go through the final-scoring path
(cells against every script of the other team, the pooled row, the best single fixed choice, the choice share) and
the known answers hold; suite_check.json is written with complete and status. A wrong known answer is FAIL, exit 6;
the refusals exit 2. No training."""
import json
import sys

import pytest

from svg_training.ste import exploit, scoring

from _ste_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import ste_l4_suite as suite  # noqa: E402

GAMES = 3
CFG = exploit.ROOT / "configs" / "ste_l3"


@pytest.fixture(scope="module")
def done(tmp_path_factory):
    out = tmp_path_factory.mktemp("l4_suite") / "suite"
    assert suite.main(["--out", str(out), "--games", str(GAMES)]) == 0
    return out


def test_every_known_answer_holds_on_both_routes_and_sides(done):
    res = json.loads((done / "suite_check.json").read_text())
    assert res["complete"] is True and res["status"] == "PASS" and res["games"] == GAMES
    want_sha = {r: exploit.load_gates(CFG / f"{r}_gates.toml").sha256 for r in ("velocity", "skills")}
    assert res["gates_sha256"] == want_sha
    want = {"ctl_untrained_is_known", "ctl_script_cells_are_reference", "ctl_pooled_row_of_the_script_team",
            "ctl_pooled_row_of_the_untrained_team", "ctl_best_single_choice", "ctl_choice_share"}
    for route in ("velocity", "skills"):
        for side in ("guard", "strike"):
            checks = res["checks"][route][side]
            assert want <= set(checks), (route, side)
            assert all(v["status"] == "PASS" for v in checks.values()), (route, side, checks)
    assert "skills" in res["checks"]["skills"]["strike"]["ctl_choice_share"]["detail"]
    assert res["status_note"] == "pipeline check, not for flight"
    assert (done / "suite_check.md").read_text().startswith("Simulator:")


def test_the_same_command_on_a_finished_folder_is_refused_and_bad_arguments_too(done, tmp_path):
    assert suite.main(["--out", str(done), "--games", str(GAMES)]) == 2
    assert suite.main(["--out", str(tmp_path / "a"), "--games", "0"]) == 2
    assert suite.main(["--out", str(tmp_path / "b"), "--games", "100000"]) == 2
    (tmp_path / "c").mkdir()
    (tmp_path / "c" / "job.json").write_text("{}")                 # scripts/ste_job.py's own files: not a refusal
    assert suite.main(["--out", str(tmp_path / "c"), "--games", "1", "--routes", "velocity",
                       "--sides", "strike"]) == 0


def test_a_wrong_known_answer_is_fail_exit_6_and_still_written(tmp_path, monkeypatch):
    real = scoring.best_single_choice

    def wrong(*a, **k):
        out = real(*a, **k)
        others = [s for s in out["per_choice"] if s != out["best"]]
        return {**out, "best": others[0]}
    monkeypatch.setattr(scoring, "best_single_choice", wrong)
    out = tmp_path / "s"
    assert suite.main(["--out", str(out), "--games", "1", "--routes", "velocity", "--sides", "guard"]) == 6
    res = json.loads((out / "suite_check.json").read_text())
    assert res["complete"] is True and res["status"] == "FAIL"
    assert res["checks"]["velocity"]["guard"]["ctl_best_single_choice"]["status"] == "FAIL"
