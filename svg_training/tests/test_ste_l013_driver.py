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

TINY = {"num_games = 16384 ": "num_games = 12 ", "eval_games = 1000 ": "eval_games = 4 ",
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
        assert res["trained_updates"] == 2 and res["game_steps"] == 576 and res["budget_reached"]
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


def test_the_arms_train_the_same_networks_from_the_same_seed(two_arms):
    import torch
    a = torch.load(two_arms["t1"] / "snapshots" / "u0001.pt", weights_only=False)
    b = torch.load(two_arms["t2"] / "snapshots" / "u0001.pt", weights_only=False)
    assert set(a) == set(b)
    # same start, same seed: the first update differs only through the drone model (tier 1 v tier 2)
    assert any(not torch.equal(a[k]["policy"][p], b[k]["policy"][p]) for k in a for p in a[k]["policy"])


def test_the_same_command_on_a_finished_arm_does_nothing_new(two_arms):
    r = two_arms["t1"]
    before = (r / "results.json").read_text()
    assert arm(two_arms["gates"], r, "t1") == 0
    assert (r / "results.json").read_text() == before


def test_the_verdict_and_the_record(two_arms, tmp_path):
    out = tmp_path / "verdict"
    assert driver.main(["verdict", "--t1-run", str(two_arms["t1"]), "--t2-run", str(two_arms["t2"]),
                        "--out", str(out)]) == 0
    v = json.loads((out / "verdict.json").read_text())
    assert v["verdict"] in (T.PASS_WORD, T.FAIL_WORD) and v["same_game_steps"] and v["controls_pass"]
    assert (out / "learning_curves.png").is_file() and "DRY CPU RUN" in (out / "verdict.md").read_text()
    assert v["matrix_same_update"]["t1 networks"]["tier 2"]["games"] == 4
    rec = tmp_path / "rec.md"
    assert record.main(["--verdict", str(out / "verdict.json"), "--out", str(rec), "--name", "smoke"]) == 0
    text = rec.read_text()
    assert "observed in the training simulator" in text.lower() and v["gates_sha256"] in text
    assert record.main(["--verdict", str(out / "verdict.json"), "--out", str(rec), "--name", "smoke"]) == 1   # no overwrite
    # the arms swapped or one missing: refused
    assert driver.main(["verdict", "--t1-run", str(two_arms["t2"]), "--t2-run", str(two_arms["t1"]),
                        "--out", str(tmp_path / "v2")]) == 2


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
    assert driver.main(["verdict", "--t1-run", str(two_arms["t1"]), "--t2-run", str(r), "--out", str(out)]) == 0
    v = json.loads((out / "verdict.json").read_text())
    assert v["verdict"] == T.TOO_SLOW and not v["same_game_steps"]


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
    assert res["trained_updates"] == 5 and res["launches"] == 2
