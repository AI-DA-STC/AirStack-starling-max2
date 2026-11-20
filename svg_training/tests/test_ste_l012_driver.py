"""STE task L0.12 Best-response test, the driver scripts/ste_exploit_l012.py on the CPU with a tiny copy of the smoke
gate file: a whole run on each side (controls first, training, final evaluation, results), the run contract (the same
command resumes; SIGINT stops with a checkpoint, exit 4; a failed control is terminal, exit 6, again on relaunch;
refusals exit 2), the verdict over a variant's two runs, the pilot and the record writer."""
import json
import os
import signal
import subprocess
import sys

import pytest

from _proc import child_env, child_python
from _ste_tools import SCRIPTS, wait_for
from svg_training.ste import exploit, shared, sweep

sys.path.insert(0, str(SCRIPTS))
import make_ste_l012_record as record  # noqa: E402
import ste_exploit_l012 as driver  # noqa: E402

SMOKE = exploit.ROOT / "configs" / "ste_l012" / "smoke_gates.toml"


def tiny_gates(tmp_path, **replace):
    """The committed smoke gate file with lines replaced (key = "new value line")."""
    text = SMOKE.read_text()
    for old, new in replace.items():
        assert old in text, old
        text = text.replace(old, new, 1)
    path = tmp_path / "gates.toml"
    path.write_text(text)
    return path


@pytest.fixture(autouse=True)
def scratch_shared(tmp_path, monkeypatch):
    monkeypatch.setenv(shared.SHARED_ENV, str(tmp_path / "shared"))
    monkeypatch.setenv(shared.LEGACY_LOGS_ENV, "")


def run(gates, run_dir, variant="base", side="strike", *extra):
    return driver.main(["--gates", str(gates), "--variant", variant, "--side", side, "--run-dir", str(run_dir),
                        "--cap-h", "1", "--no-videos", *extra])


@pytest.fixture(scope="module")
def two_runs(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("l012_driver")
    mp = pytest.MonkeyPatch()
    mp.setenv(shared.SHARED_ENV, str(tmp / "shared"))
    mp.setenv(shared.LEGACY_LOGS_ENV, "")
    out = {}
    for side in ("strike", "guard"):
        r = tmp / side
        assert run(SMOKE, r, "base", side) == 0, side
        out[side] = r
    mp.undo()
    return out


def test_a_tiny_run_on_each_side_writes_every_file(two_runs):
    for side, r in two_runs.items():
        for name in ("gates.toml", "gates.sha256", "code.json", "controls.json", "curve.json", "train_log.jsonl",
                     "results.json", "results.md", "agent_final.pt", "checkpoint.latest"):
            assert (r / name).is_file(), (side, name)
        controls = json.loads((r / "controls.json").read_text())
        assert controls and all(c["status"] == "PASS" for c in controls.values()), controls
        res = json.loads((r / "results.json").read_text())
        assert res["side"] == side and res["variant"] == "base"
        for key in ("exploiter", "untrained", "script"):
            assert res[key]["n"] == res["eval_games"], key
        assert res["trained_updates"] >= 1 and res["game_steps"] > 0
        assert "guards_left_mean_in_holds" in res["exploiter"]["composition"]
        log = [json.loads(x) for x in (r / "train_log.jsonl").read_text().splitlines()]
        assert log and all("losses" in x for x in log)
        assert (r / "results.md").read_text().startswith("Simulator: training simulator, tier 1")


def test_the_same_command_on_a_finished_run_does_nothing_new(two_runs):
    r = two_runs["guard"]
    before = (r / "results.json").read_text()
    assert run(SMOKE, r, "base", "guard") == 0
    assert (r / "results.json").read_text() == before


def test_a_failed_control_is_terminal_exit_6_again_on_relaunch(tmp_path, monkeypatch):
    monkeypatch.setattr(exploit, "replay_ok", lambda *a, **k: (False, "forced by the test"))
    r = tmp_path / "run"
    assert run(SMOKE, r) == 6
    controls = json.loads((r / "controls.json").read_text())
    assert controls["ctl_reference_replay"]["status"] == "FAIL"
    monkeypatch.undo()
    assert run(SMOKE, r) == 6
    assert not (r / "train_log.jsonl").exists()                     # no training after a failed control


def test_refusals_exit_2(tmp_path):
    assert run(SMOKE, tmp_path / "a", "tag_1p8") == 2                  # not a shortlisted variant
    assert run(SMOKE, tmp_path / "b", "base", "both") == 2
    assert driver.main(["--gates", str(SMOKE), "--variant", "base", "--side", "guard", "--run-dir", str(tmp_path / "c"),
                        "--cap-h", "1", "--expect-gates-sha256", "0" * 64]) == 2
    r = tmp_path / "d"
    r.mkdir()
    (r / "job.json").write_text(json.dumps({"gpu_h": 2.0}))
    assert run(SMOKE, r) == 2                                        # the launcher asked for other hours


def test_a_run_with_an_unfilled_step_budget_is_refused(tmp_path):
    g = tiny_gates(tmp_path, **{"game_steps_per_run = 1440": "game_steps_per_run = 0"})
    assert run(g, tmp_path / "r") == 2


def test_sigint_stops_with_a_checkpoint_and_the_same_command_resumes(tmp_path):
    g = tiny_gates(tmp_path, **{"game_steps_per_run = 1440": "game_steps_per_run = 1000000000"})
    r = tmp_path / "run"
    cmd = [child_python(), str(SCRIPTS / "ste_exploit_l012.py"), "--gates", str(g), "--variant", "base", "--side",
           "guard", "--run-dir", str(r), "--cap-h", "1", "--no-videos"]
    env = child_env(str(exploit.ROOT / "source"))
    env.update({shared.SHARED_ENV: str(tmp_path / "shared"), shared.LEGACY_LOGS_ENV: ""})
    p = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    log = r / "train_log.jsonl"
    wait_for(lambda: log.is_file() and len(log.read_text().splitlines()) >= 2, what="two updates")
    os.kill(p.pid, signal.SIGINT)
    out, _ = p.communicate(timeout=120)
    assert p.returncode == 4, out
    done = len(log.read_text().splitlines())
    state = json.loads((r / "progress.json").read_text())
    assert state["step"] >= 2
    p = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    wait_for(lambda: len(log.read_text().splitlines()) >= done + 1, what="one more update after the resume")
    os.kill(p.pid, signal.SIGINT)
    out, _ = p.communicate(timeout=120)
    assert p.returncode == 4 and "resumed at update" in out, out


def test_the_verdict_over_a_variants_two_runs(two_runs, tmp_path):
    out = tmp_path / "verdict"
    assert driver.main(["verdict", "--gates", str(SMOKE), "--runs", f"{two_runs['strike']},{two_runs['guard']}",
                        "--out", str(out)]) == 0
    v = json.loads((out / "verdict.json").read_text())
    base = v["variants"]["base"]
    assert base["category"] in (exploit.GUARD_TRIVIAL, exploit.STRIKE_TRIVIAL, exploit.WORTH_LEARNING,
                                exploit.BOTH_BELOW_BAND)
    assert set(base["sides"]) == {"strike", "guard"}
    assert v["controls_pass"] is True
    md = record.main(["--verdict", str(out / "verdict.json"), "--out", str(tmp_path / "rec.md"), "--name", "smoke"])
    assert md == 0
    text = (tmp_path / "rec.md").read_text()
    assert text.startswith("Simulator: training simulator, tier 1")
    assert v["gates_sha256"] in text


def test_the_verdict_refuses_runs_of_another_gate_file(two_runs, tmp_path):
    g = tiny_gates(tmp_path, **{"band = 0.2": "band = 0.25"})
    assert driver.main(["verdict", "--gates", str(g), "--runs", f"{two_runs['strike']},{two_runs['guard']}",
                        "--out", str(tmp_path / "v")]) == 2


def test_the_pilot_measures_rates_for_both_sides(tmp_path):
    r = tmp_path / "pilot"
    assert driver.main(["--pilot", "--gates", str(SMOKE), "--run-dir", str(r), "--cap-h", "1"]) == 0
    p = json.loads((r / "pilot.json").read_text())
    sides = {pt["side"] for pt in p["points"]}
    assert sides == {"strike", "guard"}
    assert all(pt["game_steps_per_s"] > 0 for pt in p["points"])
    assert p["eval"]["seconds"] > 0
    assert (r / "pilot.md").is_file()
    for side in ("strike", "guard"):                          # the controls on the pilot's device, before any run
        assert p["eval"]["per_side"][side]["controls"]["ctl_reference_replay"]["status"] == "PASS"
    assert [len(pr["updates"]) for pr in p["probes"]] == [2, 2]


def test_the_video_pick_takes_one_of_each_outcome_by_identity():
    import numpy as np
    from svg_training.viz.replay import Recording
    def rec(i, outcome):
        return Recording(np.zeros((2, 6, 3)), np.ones((2, 6), dtype=bool), np.zeros(2), 1.6, 3.25, outcome, 1, 3, 3,
                         "lab", "x", "g", "s", 0, i, 1.0)
    recs = [rec(0, exploit.GUARD_WIN), rec(1, exploit.GUARD_WIN), rec(2, exploit.STRIKE_WIN)]
    assert [r.game_index for r in driver.pick_videos(recs, 2)] == [2, 0]
    assert [r.game_index for r in driver.pick_videos(recs, 5)] == [2, 0, 1]


def test_a_shaping_override_changes_the_training_game_only():
    g = exploit.load_gates(SMOKE)
    plain = driver.build_learner(g, "base", "strike", 4, 1)
    assert plain.env.game.cfg.rewards.shaping_weight == 0.0
    shaped = driver.build_learner(g, "base", "strike", 4, 1, overrides={"shaping_weight": 1.0, "init_log_std": 0.0})
    assert shaped.env.game.cfg.rewards.shaping_weight == 1.0
    assert float(shaped.agent.policies["strike_0"].log_std[0]) == 0.0
    assert exploit.variant_cfg(g, "base").rewards.shaping_weight == 0.0     # the evaluation game is untouched


def test_a_stop_inside_a_curve_evaluation_checkpoints_and_resumes_without_a_double_log(tmp_path, monkeypatch):
    def stopped(*a, **k):
        raise sweep.SweepStopped("forced by the test")
    monkeypatch.setattr(exploit, "play_fresh", stopped)
    r = tmp_path / "run"
    assert run(SMOKE, r, "base", "guard") == 3                       # no signal asked: the cap clock's stop
    logged = [json.loads(x)["update"] for x in (r / "train_log.jsonl").read_text().splitlines()]
    assert json.loads((r / "progress.json").read_text())["step"] == logged[-1]
    monkeypatch.undo()
    assert run(SMOKE, r, "base", "guard") == 0
    logged = [json.loads(x)["update"] for x in (r / "train_log.jsonl").read_text().splitlines()]
    assert logged == sorted(set(logged))                             # every update logged once


def test_the_train_log_carries_the_filter_share(two_runs):
    log = [json.loads(x) for x in (two_runs["strike"] / "train_log.jsonl").read_text().splitlines()]
    assert all(0.0 <= x["filter_share"] <= 1.0 for x in log)


def test_a_pilot_probe_may_name_another_opponent():
    g = exploit.load_gates(SMOKE)
    lr = driver.build_learner(g, "base", "strike", 4, 1, opponent="guard_parked_centre")
    assert type(lr.env.opponents["guard"]).__name__ == "GuardParkedCentre"


def test_a_tag_1p4_guard_run_scores_strike_straight_evaluation_only(tmp_path):
    r = tmp_path / "run"
    assert run(SMOKE, r, "tag_1p4", "guard") == 0
    res = json.loads((r / "results.json").read_text())
    extra = res["extra_opponents"]["strike_straight"]
    assert extra["exploiter"]["n"] == res["eval_games"] and extra["script"]["cell"][1] == "strike_straight"
    assert "tier 1 vertical response not fitted" in (r / "results.md").read_text()      # strike_low is labelled


def test_a_strike_side_not_launched_is_inconclusive_with_the_pre_registered_text(two_runs, tmp_path):
    out = tmp_path / "v"
    assert driver.main(["verdict", "--gates", str(SMOKE), "--runs", str(two_runs["guard"]), "--strike-not-launched",
                        "--out", str(out)]) == 0
    base = json.loads((out / "verdict.json").read_text())["variants"]["base"]
    strike = base["sides"]["strike"]
    assert strike["status"].startswith("INCONCLUSIVE") and "no learning signal" in strike["status"]
    assert strike["better"]["who"] == "script" and strike["run"] is None
    assert base["category"] in (exploit.GUARD_TRIVIAL, exploit.WORTH_LEARNING)
