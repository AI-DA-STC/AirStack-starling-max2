"""STE task L0.13 Does tier 2 train at all? The driver scripts/ste_tier2_l013.py on the CPU (--dry-cpu: the PyTorch
reference rigid-body world stands in for Isaac Lab) with a tiny copy of the smoke gate file: arm t1 then arm t2 end to
end (controls, training, curve reads, final batches, results), the run contract (the same command resumes or does
nothing new; SIGINT stops with a checkpoint, exit 4; a failed control is terminal, exit 6, again on relaunch; a
non-finite value exits 5; refusals exit 2), TOO_SLOW when the cap reserve stops training, the verdict over the two arms
and the record writer."""
import json
import os
import signal
import subprocess
import sys

import pytest

from _proc import child_env, child_python
from _ste_tools import SCRIPTS, wait_for
from svg_training.ste import exploit, exploit_train, shared, tier2_train as T

sys.path.insert(0, str(SCRIPTS))
import make_ste_l013_record as record  # noqa: E402
import ste_tier2_l013 as driver  # noqa: E402

TINY = {"num_games = 16384 ": "num_games = 16 ", "eval_games = 1000 ": "eval_games = 4 ",
        "curve_games = 256 ": "curve_games = 4 ", "ticks_cap = 2400 ": "ticks_cap = 120 ", "rollouts = 32": "rollouts = 2",
        "learning_epochs = 5": "learning_epochs = 1", "mini_batches = 4": "mini_batches = 1",
        "game_steps_per_run = 6_291_456 ": "game_steps_per_run = 576 ", "games = 4\n": "games = 2\n",
        "max_ticks = 600 ": "max_ticks = 120 "}


def tiny_gates(tmp_path, **more):
    text = T.SMOKE_GATES_FILE.read_text()
    for old, new in {**TINY, **more}.items():
        assert old in text, old
        text = text.replace(old, new, 1)
    path = tmp_path / "tiny_gates.toml"
    path.write_text(text)
    return path


def arm(gates, run_dir, which, t1_run=None, *extra, videos=False):
    cap = str(T.load_gates(gates).arms[which]["cap_h"])
    args = ["--arm", which, "--gates", str(gates), "--run-dir", str(run_dir), "--cap-h", cap, "--dry-cpu"]
    args += [] if videos else ["--no-videos"]
    if t1_run is not None:
        args += ["--t1-run", str(t1_run)]
    return driver.main(args + list(extra))


@pytest.fixture(autouse=True)
def scratch_shared(tmp_path, monkeypatch):
    monkeypatch.setenv(shared.SHARED_ENV, str(tmp_path / "shared"))
    monkeypatch.setenv(shared.LEGACY_LOGS_ENV, "")


@pytest.fixture(scope="module")
def two_arms(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("l013_driver")
    mp = pytest.MonkeyPatch()
    mp.setenv(shared.SHARED_ENV, str(tmp / "shared"))
    mp.setenv(shared.LEGACY_LOGS_ENV, "")
    g = tiny_gates(tmp)
    assert arm(g, tmp / "t1", "t1") == 0
    assert arm(g, tmp / "t2", "t2", tmp / "t1") == 0
    mp.undo()
    return {"gates": g, "t1": tmp / "t1", "t2": tmp / "t2", "tmp": tmp}


def test_both_arms_write_every_file_and_every_control_passes(two_arms):
    for which in ("t1", "t2"):
        r = two_arms[which]
        for name in ("gates.toml", "gates.sha256", "code.json", "run.json", "controls.json", "curve.json",
                     "train_log.jsonl", "results.json", "results.md", "agent_final.pt", "checkpoint.latest",
                     "snapshots/u0001.pt", "snapshots/u0002.pt", "eval_before_t1.npz", "eval_final_t1.npz"):
            assert (r / name).is_file(), (which, name)
        controls = json.loads((r / "controls.json").read_text())
        assert controls and all(c["status"] == "PASS" for c in controls.values()), controls
        res = json.loads((r / "results.json").read_text())
        assert res["complete"] and res["arm"] == which and res["tier"] == T.TIERS[which] and res["dry_cpu"]
        assert res["trained_updates"] == 2 and res["budget_reached"]
        assert res["game_steps"] == T.load_gates(two_arms["gates"]).planned_game_steps == 2 * 2 * 12 * 16
        assert res["trained"]["tier_ran"] == res["parked"]["tier_ran"] == T.TIERS[which]          # QC T2
        assert set(res["upsets"]) == set(res["batches"]) and res["physics_nonfinite"]["tier 1"] == 0      # QC F1
        assert res["projection_for_run_of_record"]["updates"] == 48                              # QC C1
        assert res["trained"]["n"] == res["parked"]["n"] == 4
        log = [json.loads(x) for x in (r / "train_log.jsonl").read_text().splitlines()]
        assert [x["update"] for x in log] == [1, 2] and all(x["tier"] == T.TIERS[which] for x in log)
    t2c = json.loads((two_arms["t2"] / "controls.json").read_text())
    for name in ("ctl_physics_agreement_launch1", "ctl_physics_agreement_view_launch1", "ctl_untrained_is_still_t2",
                 "ctl_negative_bar_t2", "ctl_reference_replay", "ctl_reference_replay_final", "ctl_tier_difference",
                 "tags_one_for_one_t2_final", "no_nonfinite_actions_curve"):
        assert name in t2c, name
    t1c = json.loads((two_arms["t1"] / "controls.json").read_text())
    assert "ctl_physics_agreement_launch1" not in t1c and "ctl_untrained_is_still_t1" in t1c
    log2 = [json.loads(x) for x in (two_arms["t2"] / "train_log.jsonl").read_text().splitlines()]
    assert all(x["motion"].startswith("physics/") for x in log2)


def test_the_t2_arm_reads_both_tiers_and_the_t1_networks(two_arms):
    curve = json.loads((two_arms["t2"] / "curve.json").read_text())
    assert {(p["update"], p["tier"], p["networks"]) for p in curve} == {
        (u, t, w) for u in (1, 2) for t, w in ((2, "t2"), (1, "t2"), (2, "t1"))}
    res = json.loads((two_arms["t2"] / "results.json").read_text())
    assert res["peer_update"] == 2 and set(res["batches"]) == {"tier 1", "tier 2"}
    assert f"{T.PEER} v strike_straight" in res["batches"]["tier 2"]
    assert sum(res["paired_t2_on_t2_v_t1_on_t1"].values()) == 4
    assert "parked_t2_before_v_final" in res["info"]
    c1 = json.loads((two_arms["t1"] / "curve.json").read_text())
    assert {(p["tier"], p["networks"]) for p in c1} == {(1, "t1")}


def test_both_arms_start_from_the_same_networks_and_part_through_the_drone(two_arms):
    import torch
    load = lambda arm, u: torch.load(two_arms[arm] / "snapshots" / f"u{u:04d}.pt", weights_only=False)  # noqa: E731
    a0, b0 = load("t1", 0), load("t2", 0)
    assert set(a0) == set(b0)
    for k in a0:                                                  # one seed: the same start networks bit for bit
        for part in a0[k]:
            assert all(torch.equal(a0[k][part][p], b0[k][part][p]) for p in a0[k][part]), (k, part)
    a1, b1 = load("t1", 1), load("t2", 1)                         # the first update differs through the drone model
    assert any(not torch.equal(a1[k]["policy"][p], b1[k]["policy"][p]) for k in a1 for p in a1[k]["policy"])


def test_a_curve_read_stopped_by_sigint_is_done_on_resume(tmp_path, monkeypatch):
    g = tiny_gates(tmp_path)
    real = driver.Arm.curve_read

    def interrupted(self, curve):
        return self.stop("interrupted")                          # as a SIGINT during the read: the update is saved
    monkeypatch.setattr(driver.Arm, "curve_read", interrupted)
    r = tmp_path / "t1"
    assert arm(g, r, "t1") == 4
    monkeypatch.setattr(driver.Arm, "curve_read", real)
    assert arm(g, r, "t1") == 0
    curve = json.loads((r / "curve.json").read_text())
    assert sorted({p["update"] for p in curve}) == [1, 2]


def test_the_same_command_on_a_finished_arm_does_nothing_new(two_arms):
    r = two_arms["t1"]
    before = (r / "results.json").read_text()
    assert arm(two_arms["gates"], r, "t1") == 0
    assert (r / "results.json").read_text() == before


def test_the_verdict_and_the_record(two_arms, tmp_path):
    out = tmp_path / "verdict"
    args = ["verdict", "--t1-run", str(two_arms["t1"]), "--t2-run", str(two_arms["t2"]), "--out", str(out)]
    assert driver.main(args) == 2                                  # QC D2: not gates.toml's sha: refused without --smoke
    assert driver.main(args + ["--smoke"]) == 0
    v = json.loads((out / "verdict.json").read_text())
    assert v["verdict"] == "SMOKE" and v["smoke_reading"] in (T.PASS_WORD, T.FAIL_WORD)
    assert v["same_game_steps"] and v["controls_pass"] and "SMOKE" in (out / "verdict.md").read_text()
    assert (out / "learning_curves.png").is_file() and "DRY CPU RUN" in (out / "verdict.md").read_text()
    assert v["matrix_same_update"]["t1 networks"]["tier 2"]["games"] == 4
    rec = tmp_path / "rec.md"
    assert record.main(["--verdict", str(out / "verdict.json"), "--out", str(rec), "--name", "smoke"]) == 1   # QC D2
    assert record.main(["--verdict", str(out / "verdict.json"), "--out", str(rec), "--name", "smoke", "--smoke"]) == 0
    text = rec.read_text()
    assert "observed in the training simulator" in text.lower() and v["gates_sha256"] in text
    assert "Verdict: **SMOKE**" in text and "Upset games" in text
    assert record.main(["--verdict", str(out / "verdict.json"), "--out", str(rec), "--name", "smoke",
                        "--smoke"]) == 1   # no overwrite
    # the arms swapped or one missing: refused
    assert driver.main(["verdict", "--t1-run", str(two_arms["t2"]), "--t2-run", str(two_arms["t1"]),
                        "--out", str(tmp_path / "v2"), "--smoke"]) == 2


def test_the_aborted_record(two_arms, tmp_path):
    rec = tmp_path / "aborted.md"
    assert record.main(["--aborted", "--runs", f"{two_arms['t1']},{two_arms['t2']}", "--out", str(rec),
                        "--name", "smoke", "--why", "test"]) == 0
    text = rec.read_text()
    assert "Verdict: **ABORTED**" in text and "Bar cleared" not in text and "The lead: test." in text


# ------------------------------------------------------------------------------------------------ the run contract
def test_t2_refuses_without_a_finished_t1_and_with_another_cap(tmp_path):
    g = tiny_gates(tmp_path)
    assert arm(g, tmp_path / "t2", "t2", None) == 2
    assert arm(g, tmp_path / "t2b", "t2", tmp_path / "nothing") == 2
    assert driver.main(["--arm", "t1", "--gates", str(g), "--run-dir", str(tmp_path / "t1"), "--cap-h", "0.3",
                        "--dry-cpu", "--no-videos"]) == 2
    assert driver.pre_isaac_problem(["--arm", "t2", "--run-dir", "x"])[1].startswith("arm t2 starts Isaac Lab")
    assert "run arm t1 first" in driver.pre_isaac_problem(["--arm", "t2", "--headless", "--t1-run", str(tmp_path)])[1]


def test_a_changed_gate_file_is_refused_on_relaunch(tmp_path, monkeypatch):
    g = tiny_gates(tmp_path)
    monkeypatch.setattr(exploit, "replay_ok", lambda *a, **k: (False, "forced by the test"))
    r = tmp_path / "t1"
    assert arm(g, r, "t1") == 6
    sub = tmp_path / "other"
    sub.mkdir()
    other = tiny_gates(sub, **{"agree_ticks = 20 ": "agree_ticks = 21 "})
    assert arm(other, r, "t1") == 2


def test_a_failed_control_is_terminal_exit_6_again_on_relaunch(tmp_path, monkeypatch):
    g = tiny_gates(tmp_path)
    monkeypatch.setattr(exploit, "replay_ok", lambda *a, **k: (False, "forced by the test"))
    r = tmp_path / "t1"
    assert arm(g, r, "t1") == 6
    assert json.loads((r / "controls.json").read_text())["ctl_reference_replay"]["status"] == "FAIL"
    monkeypatch.undo()
    assert arm(g, r, "t1") == 6
    assert not (r / "train_log.jsonl").exists()
    assert "No result" in (r / "results.md").read_text()


def test_a_failed_physics_agreement_stops_t2_before_training(two_arms, tmp_path, monkeypatch):
    monkeypatch.setattr(T, "physics_agreement", lambda *a, **k: {"pass": False, "games": 1, "drones": 6, "ticks": 1,
                                                                  "world": "w", "max_gap_m": 1.0, "limit_m": 0.02})
    r = tmp_path / "t2"
    assert arm(two_arms["gates"], r, "t2", two_arms["t1"]) == 6
    assert json.loads((r / "controls.json").read_text())["ctl_physics_agreement_launch1"]["status"] == "FAIL"
    assert not (r / "train_log.jsonl").exists()


def test_a_non_finite_update_exits_5_and_stays_5(tmp_path, monkeypatch):
    g = tiny_gates(tmp_path)

    def boom(self):
        raise exploit_train.NonFinite("forced by the test")
    monkeypatch.setattr(exploit_train.Learner, "update", boom)
    r = tmp_path / "t1"
    assert arm(g, r, "t1") == 5
    monkeypatch.undo()
    assert arm(g, r, "t1") == 5


def test_the_cap_reserve_before_the_budget_is_too_slow_and_still_finishes(two_arms, tmp_path, monkeypatch):
    calls = []

    def room(gates, reserve, update_s, curve_s, due):
        calls.append(update_s)
        return 0.0 if update_s is None else 1.0e9            # room for the first update only
    monkeypatch.setattr(T, "room_needed_s", room)
    r = tmp_path / "t2"
    assert arm(two_arms["gates"], r, "t2", two_arms["t1"], videos=True) == 0          # the tier 2 clips too
    res = json.loads((r / "results.json").read_text())
    assert res["trained_updates"] == 1 and not res["budget_reached"] and res["train_stop"].startswith("cap reserve")
    gifs = sorted((r / "videos").glob("l013_t2_tier2_game*.gif"))
    assert gifs and len(res["videos"]) == len(gifs), res["videos"]
    assert res["peer_update"] == 1
    out = tmp_path / "verdict"
    assert driver.main(["verdict", "--t1-run", str(two_arms["t1"]), "--t2-run", str(r), "--out", str(out),
                        "--smoke"]) == 0
    v = json.loads((out / "verdict.json").read_text())
    assert v["smoke_reading"] == T.TOO_SLOW and not v["same_game_steps"]


def test_sigint_stops_with_a_checkpoint_and_the_same_command_resumes(tmp_path):
    g = tiny_gates(tmp_path, **{"game_steps_per_run = 6_291_456 ": "game_steps_per_run = 1440 "})
    r = tmp_path / "t1"
    cmd = [child_python(), str(SCRIPTS / "ste_tier2_l013.py"), "--arm", "t1", "--gates", str(g), "--run-dir", str(r),
           "--cap-h", "0.25", "--dry-cpu", "--no-videos"]
    env = child_env(str(T.ROOT / "source"))
    env.update({shared.SHARED_ENV: str(tmp_path / "shared"), shared.LEGACY_LOGS_ENV: "", "CUDA_VISIBLE_DEVICES": ""})
    p = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    log = r / "train_log.jsonl"
    wait_for(lambda: log.is_file() and len(log.read_text().splitlines()) >= 1, what="one update")
    os.kill(p.pid, signal.SIGINT)
    out, _ = p.communicate(timeout=300)
    assert p.returncode == 4, out
    p = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=600)
    assert p.returncode == 0 and "resumed at update" in p.stdout, p.stdout + p.stderr
    res = json.loads((r / "results.json").read_text())
    assert res["trained_updates"] == T.load_gates(g).planned_updates == 4 and res["launches"] == 2


# ------------------------------------------------------------------------------------------------ fix round (QC 21 Nov)
def copy_arms(two_arms, tmp_path):
    """Copies of the two finished arms (t2 pointing at the copied t1), for verdicts on edited results."""
    import shutil
    out = {}
    for which in ("t1", "t2"):
        out[which] = tmp_path / f"copy_{which}"
        shutil.copytree(two_arms[which], out[which], ignore=shutil.ignore_patterns("run.lock", "videos", "snapshots"))
    res = json.loads((out["t2"] / "results.json").read_text())
    res["t1_run"] = str(out["t1"])
    (out["t2"] / "results.json").write_text(json.dumps(res))
    return out


def edit_results(folder, **changes):
    res = json.loads((folder / "results.json").read_text())
    for who, (k, n) in changes.items():
        res[who] = {**res[who], **T.rate(k, n)}
    (folder / "results.json").write_text(json.dumps(res))


def verdict(c, out, *extra):
    return driver.main(["verdict", "--t1-run", str(c["t1"]), "--t2-run", str(c["t2"]), "--out", str(out), "--smoke",
                        *extra])


def test_the_verdict_reads_the_t2_arms_tier_2_numbers(two_arms, tmp_path):            # QC T2 (M04)
    c = copy_arms(two_arms, tmp_path)
    edit_results(c["t1"], trained=(0, 4), parked=(4, 4))
    edit_results(c["t2"], trained=(4, 4), parked=(0, 4))
    assert verdict(c, tmp_path / "v") == 0
    v = json.loads((tmp_path / "v" / "verdict.json").read_text())
    assert v["smoke_reading"] == T.PASS_WORD and v["detail"]["bar"]["trained"]["k"] == 4


@pytest.mark.parametrize("who", ["trained", "parked"])
def test_the_verdict_refuses_tier_2_numbers_that_ran_on_tier_1(two_arms, tmp_path, who):   # QC T2 (M01, M02)
    c = copy_arms(two_arms, tmp_path)
    res = json.loads((c["t2"] / "results.json").read_text())
    res[who]["tier_ran"] = 1
    (c["t2"] / "results.json").write_text(json.dumps(res))
    assert verdict(c, tmp_path / "v") == 2


def test_the_verdict_refuses_a_failed_control_or_a_bad_exit(two_arms, tmp_path):      # M17, M29
    c = copy_arms(two_arms, tmp_path)
    controls = json.loads((c["t2"] / "controls.json").read_text())
    good = json.dumps(controls)
    controls["ctl_reference_replay"]["status"] = "FAIL"
    (c["t2"] / "controls.json").write_text(json.dumps(controls))
    assert verdict(c, tmp_path / "v1") == 2
    (c["t2"] / "controls.json").write_text(good)
    (c["t2"] / "exit_code").write_text("3\n")
    assert verdict(c, tmp_path / "v2") == 2
    (c["t2"] / "exit_code").write_text("0\n")
    assert verdict(c, tmp_path / "v3") == 0


def test_t1_must_be_finished_with_every_control_passed_under_the_same_gate(tmp_path):    # M15, M16
    t1 = tmp_path / "t1"
    t1.mkdir()
    good = {"complete": True, "arm": "t1", "controls_all_pass": True, "gates_sha256": "abc"}
    (t1 / "results.json").write_text(json.dumps(good))
    assert driver.t1_problem(t1, "abc") is None
    (t1 / "results.json").write_text(json.dumps({**good, "controls_all_pass": False}))
    assert "not PASS" in driver.t1_problem(t1, "abc")
    (t1 / "results.json").write_text(json.dumps(good))
    assert "gate sha256" in driver.t1_problem(t1, "other")


def test_the_whole_isaac_world_and_the_view_are_both_checked(two_arms):           # M07, T5 (16 games > 12)
    controls = json.loads((two_arms["t2"] / "controls.json").read_text())
    whole, view = controls["ctl_physics_agreement_launch1"], controls["ctl_physics_agreement_view_launch1"]
    g = T.load_gates(two_arms["gates"])
    assert whole["games"] == g.trainer["num_games"] == 16 and not whole["world"].endswith("]")
    assert view["games"] == 3 * g.run["eval_games"] == 12 and view["world"].endswith("[:12]")


def test_every_tier_2_number_came_from_a_physics_batch(two_arms):                     # QC T2 (M03)
    import numpy as np
    controls = json.loads((two_arms["t2"] / "controls.json").read_text())
    for name in ("ctl_batch_tier_t2_before", "ctl_batch_tier_t2_final", "ctl_batch_tier_t1_final", "ctl_batch_tier_curve",
                 "ctl_no_nonfinite_wrench_t2_final", "ctl_no_nonfinite_wrench_curve"):
        assert controls[name]["status"] == "PASS", name
    assert set(np.load(two_arms["t2"] / "eval_final_t2.npz")["tier"]) == {2}
    assert set(np.load(two_arms["t2"] / "eval_final_t1.npz")["tier"]) == {1}
    res = json.loads((two_arms["t2"] / "results.json").read_text())
    assert res["motion"]["tier 2"].startswith("physics/") and res["motion"]["tier 1"] == "starling"
    curve = json.loads((two_arms["t2"] / "curve.json").read_text())
    assert all(p["tier_ran"] == p["tier"] for p in curve)
    assert {p["seed"] for p in curve} == {T.load_gates(two_arms["gates"]).run["curve_seed"]}      # M22


def test_a_tier_2_batch_played_on_the_fitted_drone_fails(two_arms, tmp_path, monkeypatch):   # QC T2
    real = exploit.play_cells

    def on_tier_1(cfg, *a, world=None, **k):
        out = real(T.tier_cfg(T.load_gates(two_arms["gates"]), 1), *a, **k)
        return out
    monkeypatch.setattr(exploit, "play_cells", on_tier_1)
    r = tmp_path / "t2"
    assert arm(two_arms["gates"], r, "t2", two_arms["t1"]) == 6
    assert json.loads((r / "controls.json").read_text())["ctl_batch_tier_t2_before"]["status"] == "FAIL"


def test_a_non_finite_wrench_in_a_tier_2_batch_fails(two_arms, tmp_path, monkeypatch):   # QC F1
    real = exploit.play_cells

    def bad_wrench(*a, **k):
        out = real(*a, **k)
        if str(out["motion"]).startswith("physics/"):
            out["physics_nonfinite"] = 1
        return out
    monkeypatch.setattr(exploit, "play_cells", bad_wrench)
    r = tmp_path / "t2"
    assert arm(two_arms["gates"], r, "t2", two_arms["t1"]) == 6
    c = json.loads((r / "controls.json").read_text())
    assert c["ctl_no_nonfinite_wrench_t2_before"]["status"] == "FAIL"
    assert c["ctl_no_nonfinite_wrench_t1_before"]["status"] == "PASS"


def test_the_training_world_is_restored_after_every_evaluation(two_arms, tmp_path, monkeypatch):   # QC T1 (M06)
    real = exploit_train.Learner.update
    seen = []

    def checked(self):
        drone = getattr(self.env.game._starling, "drone", None)
        if drone is not None:
            world_pos = drone.world.state()[0]
            seen.append(float((world_pos - drone.pos_m).abs().max()))
        return real(self)
    monkeypatch.setattr(exploit_train.Learner, "update", checked)
    assert arm(two_arms["gates"], tmp_path / "t2", "t2", two_arms["t1"]) == 0
    assert len(seen) == 2 and max(seen) < 1e-5, seen        # the training drones' state is the world's at every update


def test_a_terminal_folder_never_starts_a_world(two_arms, tmp_path, monkeypatch):      # M11
    monkeypatch.setattr(T, "physics_agreement", lambda *a, **k: {"pass": False, "games": 1, "drones": 6, "ticks": 1,
                                                                  "world": "w", "max_gap_m": 1.0, "limit_m": 0.02})
    r = tmp_path / "t2"
    assert arm(two_arms["gates"], r, "t2", two_arms["t1"]) == 6
    built = []

    def factory(*a, **k):
        built.append(a)
        return T.torch_world_factory(*a, **k)
    cap = str(T.load_gates(two_arms["gates"]).arms["t2"]["cap_h"])
    assert driver.main(["--arm", "t2", "--gates", str(two_arms["gates"]), "--run-dir", str(r), "--cap-h", cap,
                        "--dry-cpu", "--no-videos", "--t1-run", str(two_arms["t1"])], world_factory=factory) == 6
    assert built == []


def test_the_negative_bar_check_fails_when_the_untrained_guard_clears_it(two_arms, tmp_path, monkeypatch):   # M20
    real = T.trains_bar
    monkeypatch.setattr(T, "trains_bar", lambda t, p: {**real(t, p), "cleared": True})
    r = tmp_path / "t2"
    assert arm(two_arms["gates"], r, "t2", two_arms["t1"]) == 6
    assert json.loads((r / "controls.json").read_text())["ctl_negative_bar_t2"]["status"] == "FAIL"


def test_a_tier_difference_beyond_the_backend_fails(tmp_path, monkeypatch):          # M21
    monkeypatch.setattr(T, "cfg_differences", lambda a, b, prefix="": ["starling.backend", "tag.radius_m"])
    r = tmp_path / "t1"
    assert arm(tiny_gates(tmp_path), r, "t1") == 6
    assert json.loads((r / "controls.json").read_text())["ctl_tier_difference"]["status"] == "FAIL"


def test_the_untrained_guard_must_play_as_the_parked_guard(tmp_path, monkeypatch):    # M25
    real = exploit.replay_ok
    monkeypatch.setattr(exploit, "replay_ok", lambda *a, **k: real(*a, **k) if "ticks_cap" in k else (False, "forced"))
    r = tmp_path / "t1"
    assert arm(tiny_gates(tmp_path), r, "t1") == 6
    c = json.loads((r / "controls.json").read_text())
    assert c["ctl_untrained_is_still_t1"]["status"] == "FAIL" and c["ctl_reference_replay"]["status"] == "PASS"


def test_the_final_reference_replay_is_gated(tmp_path, monkeypatch):               # M26
    real = exploit.replay_ok
    calls = []

    def second_replay_fails(*a, **k):
        if "ticks_cap" in k:
            calls.append(1)
            if len(calls) > 1:
                return False, "forced"
        return real(*a, **k)
    monkeypatch.setattr(exploit, "replay_ok", second_replay_fails)
    r = tmp_path / "t1"
    assert arm(tiny_gates(tmp_path), r, "t1") == 6
    c = json.loads((r / "controls.json").read_text())
    assert c["ctl_reference_replay_final"]["status"] == "FAIL" and not (r / "results.json").exists()


def test_the_plumbing_checks_fail_on_bad_batches():                                  # M27
    import numpy as np
    ref = exploit.load_reference(T.ROOT / T.load_gates().reference["file"])
    n = 2
    pg = {"start_sha256": [exploit.starts_sha(ref.starts_m[:n])], "tags": np.array([1, 0]),
          "guards_removed": np.array([1, 0]), "guards_tagged": np.array([1, 0]), "nonfinite_actions": np.array([0, 0])}
    ok = driver.plumbing(exploit, pg, ref, n, "x", "_s")
    assert all(v["status"] == "PASS" for v in ok.values())
    bad = driver.plumbing(exploit, {**pg, "guards_removed": np.array([0, 0])}, ref, n, "x", "_s")
    assert bad["tags_one_for_one_s"]["status"] == "FAIL"
    assert driver.plumbing(exploit, {**pg, "nonfinite_actions": np.array([0, 3])}, ref, n, "x", "_s")[
        "no_nonfinite_actions_s"]["status"] == "NONFINITE"
    assert driver.plumbing(exploit, {**pg, "start_sha256": ["x"]}, ref, n, "x", "_s")[
        "ctl_paired_starts_s"]["status"] == "FAIL"


def test_sigint_during_the_clips_exits_4_and_the_same_command_finishes(tmp_path, monkeypatch):   # QC D4
    import svg_training.viz.replay as replay
    real = replay.record_games
    monkeypatch.setattr(replay, "record_games", lambda *a, **k: real(*a, **{**k, "should_stop": lambda: True}))
    g = tiny_gates(tmp_path)
    r = tmp_path / "t1"
    assert arm(g, r, "t1", videos=True) == 4
    assert not (r / "results.json").exists()
    monkeypatch.setattr(replay, "record_games", real)
    assert arm(g, r, "t1", videos=True) == 0
    assert list((r / "videos").glob("l013_t1_tier1_game*.gif"))


def test_the_tier2_clips_play_the_cpu_drawn_clip_starts(two_arms, tmp_path, monkeypatch):
    """CLIP-T2 QC: the t2 arm's clips run on the arm's device, whose generator draws other starts than tier 1's CPU draw
    from the same clip seed; both arms must get the clip starts drawn once on the CPU (``viz.replay.cpu_starts`` on the
    tier-1 game file)."""
    import svg_training.viz.replay as replay
    real, seen = replay.record_games, []

    def spy(cfg, *a, **k):
        seen.append(k.get("starts"))
        return real(cfg, *a, **k)
    monkeypatch.setattr(replay, "record_games", spy)
    r = tmp_path / "t2"
    assert arm(two_arms["gates"], r, "t2", two_arms["t1"], videos=True) == 0
    gates = T.load_gates(two_arms["gates"])
    from svg_training.ste import sweep
    guards, strikes = sweep.parse_size(gates.run["size"])
    want = replay.cpu_starts(T.tier_cfg(gates, 1), int(gates.videos["games"]), guards, strikes,
                             int(gates.run["clip_seed"]), band=0)
    assert len(seen) == 1 and seen[0] is not None, "the tier-2 clips drew their own starts on the arm's device"
    assert seen[0][0].device.type == "cpu"
    assert bool((seen[0][0] == want[0]).all()) and bool((seen[0][1] == want[1]).all())
