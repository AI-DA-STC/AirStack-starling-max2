"""STE task L0.12 Best-response test, the driver scripts/ste_exploit_l012.py on the CPU with a tiny copy of the smoke
gate file: a whole run on each side (controls first, training, final evaluation, results), the run contract (the same
command resumes; SIGINT stops with a checkpoint, exit 4; a failed control is terminal, exit 6, again on relaunch;
refusals exit 2), the verdict over a variant's two runs, the pilot and the record writer."""
import json
from pathlib import Path
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


def pilot_json(folder, recipe=exploit.RECIPE_BARE, overrides=None):
    """A pilot.json stand-in (the runs of record name the pilot they follow: M-4)."""
    path = Path(folder) / f"pilot_{len(recipe)}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"strike_recipe": {"recipe": recipe, "side_overrides_strike": {} if overrides is None
                                                  else overrides}}))
    return path


def run0_json(folder, status="PASS", gates=SMOKE, cap_h=1.0):
    """A run 0 learner_control.json stand-in (Strike runs of record name the run 0 they follow: QC N-1)."""
    path = Path(folder) / f"run0_{status}_{cap_h}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"status": status, "complete": True, "cap_h": cap_h,
                                "gates_sha256": exploit.load_gates(gates).sha256}))
    return path


def run(gates, run_dir, variant="base", side="strike", *extra):
    pj = pilot_json(Path(run_dir).parent)
    r0 = ["--run0-json", str(run0_json(Path(run_dir).parent, gates=gates))] if side == "strike" else []
    return driver.main(["--gates", str(gates), "--variant", variant, "--side", side, "--run-dir", str(run_dir),
                        "--cap-h", "1", "--no-videos", "--pilot-json", str(pj), *r0, *extra])


def run_0(gates, run_dir, *extra):
    return driver.main(["--run0", "--gates", str(gates), "--run-dir", str(run_dir), "--cap-h", "1", "--no-videos",
                        "--pilot-json", str(pilot_json(Path(run_dir).parent)), *extra])


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
                        "--cap-h", "1", "--expect-gates-sha256", "0" * 64, "--pilot-json",
                        str(pilot_json(tmp_path))]) == 2
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
           "guard", "--run-dir", str(r), "--cap-h", "1", "--no-videos", "--pilot-json", str(pilot_json(tmp_path))]
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
    assert base["sides"]["strike"]["run0"]["run0_json"] and base["sides"]["guard"]["run0"]["run0_json"] is None
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
    assert [len(pr["updates"]) for pr in p["probes"]] == [2, 2, 2]
    assert "learner_control" not in p                     # LEAD CALL 21 Nov 2026 (QC N-1): the control is run 0


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
    failed = run0_json(tmp_path / "r0", status="FAIL")
    assert driver.main(["verdict", "--gates", str(SMOKE), "--runs", str(two_runs["guard"]), "--strike-not-launched",
                        "--run0-json", str(failed), "--out", str(out)]) == 0
    v = json.loads((out / "verdict.json").read_text())
    base = v["variants"]["base"]
    strike = base["sides"]["strike"]
    assert strike["status"].startswith("INCONCLUSIVE") and "did not learn the easy Strike task" in strike["status"]
    assert v["run0"]["status"] == "FAIL"
    assert strike["better"]["who"] == "script" and strike["run"] is None
    assert base["category"] in (exploit.GUARD_TRIVIAL, exploit.WORTH_LEARNING)


# ------------------------------------------------------------------------------------------------ QC fix round 1
def _fail_final(real):
    def wrapped(*a, **k):
        out = real(*a, **k)
        if a[-1] == "final":
            out["ctl_reference_replay"] = {"status": "FAIL", "detail": "forced by the test", "phase": "final"}
        return out
    return wrapped


def test_a_control_failing_in_the_final_batch_publishes_nothing(tmp_path, monkeypatch):
    """QC C-1: no results.json, no side status in results.md, exit 6 again on relaunch, verdict refuses the run, and
    the record writer's ABORTED mode names what ran and why without any gain or category."""
    monkeypatch.setattr(driver, "evaluate_controls", _fail_final(driver.evaluate_controls))
    r = tmp_path / "run"
    assert run(SMOKE, r, "base", "guard") == 6
    monkeypatch.undo()
    assert not (r / "results.json").exists()
    md = (r / "results.md").read_text()
    assert "Side:" not in md and "## Result" not in md and "Learned:" not in md
    assert run(SMOKE, r, "base", "guard") == 6
    assert driver.main(["verdict", "--gates", str(SMOKE), "--runs", str(r), "--out", str(tmp_path / "v")]) == 2
    out = tmp_path / "rec.md"
    assert record.main(["--aborted", "--runs", str(r), "--out", str(out), "--name", "x"]) == 0
    text = out.read_text()
    assert "ABORTED" in text and "ctl_reference_replay" in text
    for word in ("worth learning", "Guard-trivial", "Strike-trivial", "weak (", "gain over"):
        assert word not in text


def test_a_crash_in_the_videos_does_not_make_the_run_look_complete(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("video writer broke (test)")
    monkeypatch.setattr(driver, "make_videos", boom)
    r = tmp_path / "run"
    with pytest.raises(RuntimeError):
        driver.main(["--gates", str(SMOKE), "--variant", "base", "--side", "guard", "--run-dir", str(r), "--cap-h", "1",
                     "--pilot-json", str(pilot_json(tmp_path))])
    assert not (r / "results.json").exists()
    assert driver.main(["verdict", "--gates", str(SMOKE), "--runs", str(r), "--out", str(tmp_path / "v")]) == 2
    monkeypatch.undo()
    monkeypatch.setattr(driver, "make_videos", lambda *a, **k: ["video stand-in (test)"])
    assert driver.main(["--gates", str(SMOKE), "--variant", "base", "--side", "guard", "--run-dir", str(r),
                        "--cap-h", "1", "--pilot-json", str(pilot_json(tmp_path))]) == 0
    assert json.loads((r / "results.json").read_text())["complete"] is True


def test_the_verdict_refuses_a_run_whose_recorded_exit_was_not_0(two_runs, tmp_path):
    import shutil
    r = tmp_path / "copy"
    shutil.copytree(two_runs["guard"], r)
    (r / "exit_code").write_text("3\n")
    assert driver.main(["verdict", "--gates", str(SMOKE), "--runs", str(r), "--out", str(tmp_path / "v")]) == 2


def test_results_are_the_batches_own_counts(two_runs):
    """QC I-1(c), mutations E4b and E8: the exploiter, untrained and script counts in results.json, and the side result
    built from them, are the counts of the evaluation batches on disk (eval_final.npz, eval_before.npz)."""
    import numpy as np
    g = exploit.load_gates(SMOKE)
    ref = exploit.load_reference(exploit.ROOT / g.reference["file"])
    for side, r in two_runs.items():
        res = json.loads((r / "results.json").read_text())
        cells = exploit.eval_cells(g, "base", side)
        n = res["eval_games"]
        final, before = np.load(r / "eval_final.npz"), np.load(r / "eval_before.npz")
        won = exploit.STRIKE_WIN if side == "strike" else exploit.GUARD_WIN
        k_e = int(np.sum(final["outcome"][:n] == won))
        k_u = int(np.sum(before["outcome"][:n] == won))
        assert (res["exploiter"]["k"], res["untrained"]["k"]) == (k_e, k_u)
        sr = res["side_result"]
        assert (sr["gain"]["trained"]["k"], sr["untrained"]["k"], sr["gain"]["script"]["k"]) == \
            (k_e, k_u, res["script"]["k"])
        assert sr == exploit.side_result(side, (k_e, n), (k_u, n), (res["script"]["k"], res["script"]["n"]))
        if side == "guard":                                 # untrained Guard = parked: T44's parked cell, first n games
            t44 = ref.cell("base", "guard_parked_centre", exploit.opponent_of(g, "base", side))["outcome"][:n]
            assert k_u == int(np.sum(t44 == exploit.GUARD_WIN)) > 0
        assert res["opponent"] == cells[0][0 if side == "strike" else 1]


def test_the_final_networks_replayed_independently_give_the_scored_games(two_runs):
    """QC I-1(c), mutations E3b and E6: agent_final.pt loaded on its own (team_from_modules, sorted agent names),
    held 12 ticks, replays the scored exploiter cell game for game, closest approach included."""
    import numpy as np
    import torch
    from svg_training.ste import exploit_train
    g = exploit.load_gates(SMOKE)
    ref = exploit.load_reference(exploit.ROOT / g.reference["file"])
    for side, r in two_runs.items():
        res = json.loads((r / "results.json").read_text())
        n = res["eval_games"]
        team = exploit_train.team_from_modules(side, torch.load(r / "agent_final.pt", weights_only=False),
                                               list(g.trainer["hidden"]), "cpu")
        cell = exploit.eval_cells(g, "base", side)[0]
        pg = exploit.play_cells(exploit.variant_cfg(g, "base"), "3v3", ref, [cell], n, "cpu", ref.meta["seed"],
                                g.run["ticks_cap"], learner=team, hold_ticks=g.trainer["decision_ticks"])
        final = np.load(r / "eval_final.npz")
        for key in ("outcome", "end_step", "tags", "closest_3d_m"):
            assert np.array_equal(pg[key], final[key][:n]), (side, key)


def test_the_train_log_names_the_opponent_actually_trained_against(two_runs):
    """QC I-1(c), mutation T2: every update line names the opponent strategy the training game played: g* for the
    Strike side, s* for the Guard side."""
    from svg_training.opponents.scripted import REGISTRY
    g = exploit.load_gates(SMOKE)
    for side, r in two_runs.items():
        want = REGISTRY[exploit.opponent_of(g, "base", side)].__name__
        log = [json.loads(x) for x in (r / "train_log.jsonl").read_text().splitlines()]
        assert {x["opponent"] for x in log} == {want}
        assert json.loads((r / "results.json").read_text())["trained_against"] == want


def test_the_final_phase_is_never_cut_by_the_cap(tmp_path, monkeypatch):
    """QC I-3: the cap reserve stops training up front; once the final phase starts the cap does not stop it (and a
    relaunch would not need a larger cap)."""
    from svg_training.ste.run_contract import RunGuard
    real_save = driver.evaluate_controls

    def after_controls(*a, **k):
        out = real_save(*a, **k)
        if a[-1] == "before":
            monkeypatch.setattr(RunGuard, "cap_reached", lambda self: True)
            monkeypatch.setattr(RunGuard, "effective_s", lambda self: self.cap_s)
        return out
    monkeypatch.setattr(driver, "evaluate_controls", after_controls)
    r = tmp_path / "run"
    assert run(SMOKE, r, "base", "guard") == 0
    res = json.loads((r / "results.json").read_text())
    assert "reserve" in res["train_stop"] and res["trained_updates"] == 0
    assert res["final_reserve_s"] >= exploit.load_gates(SMOKE).trainer["final_reserve_s"]
    assert res["controls_batch_s"] > 0
    # QC N-2 (LEAD CALL 21 Nov 2026): a run that stopped before its game-step budget publishes no side status
    assert res["budget_reached"] is False
    md = (r / "results.md").read_text()
    assert "Learned:" not in md and "before its game-step budget" in md
    assert driver.main(["verdict", "--gates", str(SMOKE), "--runs", str(r), "--out", str(tmp_path / "v")]) == 2
    assert not (tmp_path / "v" / "verdict.json").exists()
    out = tmp_path / "rec.md"
    assert record.main(["--aborted", "--runs", str(r), "--out", str(out), "--name", "x"]) == 0
    text = out.read_text()
    assert "before its game-step budget" in text and "unknown" not in text
    for word in (exploit.SIDE_INCONCLUSIVE, "INCONCLUSIVE:", "worth learning", "gain over"):
        assert word not in text, word


def test_info_batch_and_curve_are_checked_and_a_nonfinite_action_exits_5(two_runs, tmp_path, monkeypatch):
    """QC I-6: the INFO batch carries the plumbing controls; a non-finite action ends the run with exit 5 (the run
    contract's code), recorded as NONFINITE (not FAIL)."""
    import torch
    controls = json.loads((two_runs["strike"] / "controls.json").read_text())
    for k in ("ctl_paired_starts_info", "tags_one_for_one_info", "no_nonfinite_actions_info",
              "tags_one_for_one_curve", "no_nonfinite_actions_curve"):
        assert controls[k]["status"] == "PASS", k
    real = exploit.LearnerTeam.act
    monkeypatch.setattr(exploit.LearnerTeam, "act", lambda self, obs: real(self, obs) * float("nan"))
    r = tmp_path / "run"
    assert run(SMOKE, r, "base", "guard") == 5
    c = json.loads((r / "controls.json").read_text())
    assert c["no_nonfinite_actions"]["status"] == "NONFINITE"
    assert not (r / "results.json").exists()
    del torch


def test_the_pilot_writes_as_it_goes_and_records_a_point_that_did_not_fit(tmp_path, monkeypatch):
    """QC I-5: pilot.json after every step; an out-of-memory error at one rate point is recorded as "did not fit" and the
    pilot goes on; any other crash leaves the earlier steps on disk. QC I-1(b): the learner positive control is
    computed from the parked-Guard probe of the chosen recipe."""
    import torch
    from svg_training.ste import exploit_train
    real = exploit_train.Learner.update

    def oom(self):
        if self.env.game.num_games == 8 and self.updates >= 0 and getattr(self, "_rate_point", False):
            raise torch.cuda.OutOfMemoryError("test")
        return real(self)
    monkeypatch.setattr(driver, "RATE_POINT_HOOK", lambda learner: setattr(learner, "_rate_point", True))
    monkeypatch.setattr(exploit_train.Learner, "update", oom)
    r = tmp_path / "pilot"
    assert driver.main(["--pilot", "--gates", str(SMOKE), "--run-dir", str(r), "--cap-h", "1"]) == 0
    p = json.loads((r / "pilot.json").read_text())
    assert any(pt.get("did_not_fit") for pt in p["points"])
    assert any(pt.get("game_steps_per_s") for pt in p["points"])
    assert "learner_control" not in p
    monkeypatch.setattr(exploit_train.Learner, "update", lambda self: (_ for _ in ()).throw(RuntimeError("crash")))
    r2 = tmp_path / "pilot2"
    with pytest.raises(RuntimeError):
        driver.main(["--pilot", "--gates", str(SMOKE), "--run-dir", str(r2), "--cap-h", "1"])
    p2 = json.loads((r2 / "pilot.json").read_text())
    assert p2["eval"]["per_side"]                                   # the evaluation step was already on disk


def test_the_ledger_row_and_record_show_all_side_statuses(two_runs, tmp_path):
    """QC I-8 and M-1: the ledger row carries each side's status, gain, Guards left and game length; the record states
    that a resume is not identical to an uninterrupted run."""
    out = tmp_path / "v"
    assert driver.main(["verdict", "--gates", str(SMOKE), "--runs", f"{two_runs['strike']},{two_runs['guard']}",
                        "--out", str(out)]) == 0
    rec = tmp_path / "rec.md"
    assert record.main(["--verdict", str(out / "verdict.json"), "--out", str(rec), "--name", "x"]) == 0
    text = rec.read_text()
    row = text.split("Ledger row:")[1]
    for piece in ("base Strike:", "base Guard:", "Guards left", "s median"):
        assert piece in row, piece
    assert "not identical to an uninterrupted run" in text



# ------------------------------------------------------------------------------------------------ lead's items after round 1
def test_the_pilot_names_run_0_and_states_that_nothing_kills_the_final_phase(tmp_path):
    """LEAD CALL 21 Nov 2026 (QC N-1): no learner control in the pilot (run 0 is the control); (QC N-3) pilot.md says
    nothing kills a run at --gpu-h during its final phase and the ledger records the real hours, and projects the
    task's hours (pilot + run 0 + six runs) against the L0.12 cap."""
    r = tmp_path / "pilot"
    assert driver.main(["--pilot", "--gates", str(SMOKE), "--run-dir", str(r), "--cap-h", "1"]) == 0
    p = json.loads((r / "pilot.json").read_text())
    assert "learner_control" not in p and p["strike_recipe"]["recipe"] in (exploit.RECIPE_BARE, exploit.RECIPE_SHAPED)
    md = (r / "pilot.md").read_text()
    assert "run 0" in md and "the ledger records the real hours" in md
    plan = p["plan_hours"]
    assert plan and all(x["total_gpu_h"] == pytest.approx(x["pilot_gpu_h"] + 7 * x["run_cap_h"]) for x in plan)
    assert all(x["task_cap_gpu_h"] == 6.0 for x in plan)


def test_runs_refuse_a_missing_or_disagreeing_pilot_or_run_0(tmp_path):
    base = ["--gates", str(SMOKE), "--variant", "base", "--run-dir"]
    ok = str(pilot_json(tmp_path / "p"))
    assert driver.main([*base, str(tmp_path / "a"), "--side", "guard", "--cap-h", "1"]) == 2                 # no pilot
    assert driver.main([*base, str(tmp_path / "b"), "--side", "strike", "--cap-h", "1", "--pilot-json", ok]) == 2  # no run 0
    for i, r0 in enumerate([run0_json(tmp_path / "f", status="FAIL"), run0_json(tmp_path / "i", status="INCONCLUSIVE"),
                            run0_json(tmp_path / "c", cap_h=0.5)]):
        assert driver.main([*base, str(tmp_path / f"c{i}"), "--side", "strike", "--cap-h", "1", "--pilot-json", ok,
                            "--run0-json", str(r0)]) == 2
    other = tiny_gates(tmp_path, **{"band = 0.2": "band = 0.25"})
    assert driver.main([*base, str(tmp_path / "d"), "--side", "strike", "--cap-h", "1", "--pilot-json", ok,
                        "--run0-json", str(run0_json(tmp_path / "o", gates=other))]) == 2         # another gate file
    shaped = pilot_json(tmp_path / "s", recipe=exploit.RECIPE_SHAPED, overrides={"shaping_weight": 1.0})
    assert driver.main([*base, str(tmp_path / "e"), "--side", "strike", "--cap-h", "1", "--pilot-json", str(shaped),
                        "--run0-json", str(run0_json(tmp_path))]) == 2
    assert driver.main(["--run0", "--gates", str(SMOKE), "--run-dir", str(tmp_path / "f0"), "--cap-h", "1",
                        "--pilot-json", str(shaped)]) == 2                    # run 0 trains the gate's Strike recipe too


def test_a_lead_decision_on_run_0_is_recorded(tmp_path):
    r = tmp_path / "run"
    inc = run0_json(tmp_path / "i", status="INCONCLUSIVE")
    pj = pilot_json(tmp_path)
    assert driver.main(["--gates", str(SMOKE), "--variant", "base", "--side", "strike", "--run-dir", str(r), "--cap-h",
                        "1", "--no-videos", "--pilot-json", str(pj), "--run0-json", str(inc),
                        "--accept-learner-control", "lead, 21 Nov: go"]) == 0
    meta = json.loads((r / "run.json").read_text())
    assert meta["learner_control_accepted"] == "lead, 21 Nov: go" and meta["pilot_json"] == str(pj)
    assert meta["run0_json"] == str(inc) and meta["run0_json_sha256"] == exploit.sha256_file(inc)


def test_strike_not_launched_needs_run_0_fail(two_runs, tmp_path):
    for status in ("PASS", "INCONCLUSIVE"):
        r0 = run0_json(tmp_path / status, status=status)
        assert driver.main(["verdict", "--gates", str(SMOKE), "--runs", str(two_runs["guard"]), "--strike-not-launched",
                            "--run0-json", str(r0), "--out", str(tmp_path / f"v{status}")]) == 2
    assert driver.main(["verdict", "--gates", str(SMOKE), "--runs", str(two_runs["guard"]), "--strike-not-launched",
                        "--out", str(tmp_path / "v2")]) == 2
    other = run0_json(tmp_path / "o", gates=tiny_gates(tmp_path, **{"band = 0.2": "band = 0.25"}))
    assert driver.main(["verdict", "--gates", str(SMOKE), "--runs", str(two_runs["guard"]), "--run0-json", str(other),
                        "--out", str(tmp_path / "v3")]) == 2                 # any --run0-json is checked (gate sha)


def test_the_aborted_record_of_a_cleanly_finished_run_says_so(two_runs, tmp_path):
    """QC N-4 (LEAD CALL 21 Nov 2026): a run that finished (exit 0 or no exit file, results complete, controls PASS) is
    described as such, never "unknown (read job.log)", and still with no gain, status or category."""
    import shutil
    for code in ("0", None):
        r = tmp_path / f"copy{code}"
        shutil.copytree(two_runs["guard"], r)
        if code is not None:
            (r / "exit_code").write_text(code + "\n")
        out = tmp_path / f"rec{code}.md"
        assert record.main(["--aborted", "--runs", str(r), "--out", str(out), "--name", "x"]) == 0
        text = out.read_text()
        assert "finished, controls PASS" in text and "unknown" not in text, text
        for word in ("worth learning", "weak (", "gain over", "INCONCLUSIVE:"):
            assert word not in text, word


# ------------------------------------------------------------------------------------------------ run 0 (QC N-1)
def _straight_team(monkeypatch):
    """A known-good stand-in for the trained Strike: untrained (standing) before its first update, then the scripted
    strike_straight behind the learner's networks (held 0.6 s it reaches the parked Guard on the smoke starts exactly
    as the script does: 3 of 8)."""
    from svg_training.opponents.scripted import make_strategy
    from svg_training.ste import exploit_train
    g = exploit.load_gates(SMOKE)
    cfg = exploit.variant_cfg(g, "base")
    real = exploit_train.Learner.team
    monkeypatch.setattr(exploit_train.Learner, "team", lambda self: real(self) if self.updates == 0 else
                        make_strategy("strike_straight", "strike", cfg, int(g.run["eval_games"]), "cpu", 7))


def test_run_0_with_a_known_good_strike_passes_at_its_first_checkpoint_and_stops(tmp_path, monkeypatch):
    _straight_team(monkeypatch)
    r = tmp_path / "run0"
    assert run_0(SMOKE, r) == 0
    lc = json.loads((r / "learner_control.json").read_text())
    every = exploit.load_gates(SMOKE).trainer["curve_every_updates"]
    assert lc["status"] == "PASS" and lc["complete"] is True and len(lc["reads"]) == 1
    assert lc["reads"][0]["update"] == every and lc["updates"] == every < lc["planned_updates"]
    assert lc["reads"][0]["trained"]["k"] == lc["script"]["k"] == 3 and lc["reads"][0]["trained"]["n"] == 8
    assert lc["gates_sha256"] == exploit.load_gates(SMOKE).sha256 and lc["cap_h"] == 1.0
    assert lc["trained_against"] == "GuardParkedCentre"
    controls = json.loads((r / "controls.json").read_text())
    assert controls and all(v["status"] == "PASS" for v in controls.values()), controls
    assert run_0(SMOKE, r) == 0                                              # terminal: the same command changes nothing
    assert json.loads((r / "learner_control.json").read_text()) == lc


def test_run_0_with_a_strike_that_learned_nothing_fails_at_the_full_budget(tmp_path, monkeypatch):
    """The same harness with the untrained (standing) Strike: 0 of 8 reaches at every pre-listed checkpoint -> FAIL at
    the full budget (the criterion can fail)."""
    from svg_training.ste import exploit_train
    g = exploit.load_gates(SMOKE)
    monkeypatch.setattr(exploit_train.Learner, "team", lambda self: exploit.LearnerTeam.untrained(
        "strike", 3, list(g.trainer["hidden"]), "cpu"))
    r = tmp_path / "run0"
    assert run_0(SMOKE, r) == 0
    lc = json.loads((r / "learner_control.json").read_text())
    assert lc["status"] == "FAIL" and lc["budget_reached"] is True
    assert [x["update"] for x in lc["reads"]] == exploit.run0_checkpoints(lc["planned_updates"],
                                                                          g.trainer["curve_every_updates"])
    assert all(x["trained"]["k"] == 0 and not x["pass"] for x in lc["reads"])


def test_run_0_trained_against_the_wrong_opponent_never_passes(tmp_path, monkeypatch):
    """QC mutation T2 on run 0: the known-good stand-in, but the training game plays g* instead of the parked Guard ->
    a control FAIL (exit 6), never a PASS."""
    _straight_team(monkeypatch)
    real = driver.build_learner
    monkeypatch.setattr(driver, "build_learner", lambda *a, **k: real(*a, **{**k, "opponent": "guard_mark_edge"}))
    r = tmp_path / "run0"
    assert run_0(SMOKE, r) == 6
    controls = json.loads((r / "controls.json").read_text())
    assert controls["ctl_trained_against"]["status"] == "FAIL"
    lc = r / "learner_control.json"
    assert not lc.exists() or json.loads(lc.read_text())["status"] != "PASS"


def test_run_0_with_the_real_tiny_trainer_runs_to_a_status(tmp_path):
    """A healthy tiny run 0 (the real trainer, smoke sizes) does not crash and ends with a status; checkpoints are the
    pre-listed ones up to the status."""
    r = tmp_path / "run0"
    assert run_0(SMOKE, r) == 0
    lc = json.loads((r / "learner_control.json").read_text())
    assert lc["status"] in ("PASS", "FAIL") and lc["reads"] and (r / "agent_final.pt").is_file()
    assert (r / "train_log.jsonl").is_file() and json.loads((r / "run.json").read_text())["run0"] is True


def test_run_0_stopped_at_its_cap_reserve_is_inconclusive(tmp_path, monkeypatch):
    from svg_training.ste.run_contract import RunGuard
    real = driver.run0_controls

    def after_controls(*a, **k):
        out = real(*a, **k)
        monkeypatch.setattr(RunGuard, "effective_s", lambda self: self.cap_s)
        return out
    monkeypatch.setattr(driver, "run0_controls", after_controls)
    r = tmp_path / "run0"
    assert run_0(SMOKE, r) == 0
    lc = json.loads((r / "learner_control.json").read_text())
    assert lc["status"] == "INCONCLUSIVE" and lc["budget_reached"] is False and "reserve" in lc["train_stop"]
