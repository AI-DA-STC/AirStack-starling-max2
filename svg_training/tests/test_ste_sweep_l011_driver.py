"""STE task L0.11: the sweep driver ``scripts/ste_sweep_l011.py`` on the CPU with a tiny gate file (tests/_l011_smoke.py):
outputs, the gate-hash refusal, the game-file refusal, resume after SIGINT (results equal an uninterrupted run), the cap
stop, a failed control stops the run and blocks a relaunch, the launcher's hours must equal the cap, the pilot, and one
run through ``scripts/ste_job.py launch`` with a private shared folder (the real GPU-hour ledger is never touched)."""
import json
import os
import signal
import subprocess
import sys

import pytest

from _l011_smoke import smoke_gates
from _ste_tools import ROOT, SCRIPTS, reap, run_py, start_py, tool_env, wait_for
from svg_training.ste import run_contract as rc, shared, sweep

sys.path.insert(0, str(SCRIPTS))
import make_ste_l011_record as recorder  # noqa: E402
import ste_sweep_l011 as driver  # noqa: E402

TOOL = SCRIPTS / "ste_job.py"
DRIVER = SCRIPTS / "ste_sweep_l011.py"
CAP_H = "1.0"


@pytest.fixture(autouse=True)
def private_shared(tmp_path, monkeypatch):
    monkeypatch.setenv(shared.SHARED_ENV, str(tmp_path / "shared"))
    monkeypatch.setenv(shared.LEGACY_LOGS_ENV, "")
    monkeypatch.setenv("OMP_NUM_THREADS", "4")


def run(gates, run_dir, *extra) -> int:
    return driver.main(["--gates", str(gates), "--run-dir", str(run_dir), "--cap-h", CAP_H, "--no-clips", *extra])


def rows_of(run_dir) -> dict:
    result = json.loads((run_dir / "results.json").read_text())
    return {g["name"]: g["rows"] for g in result["groups"]}


def test_a_run_writes_cells_controls_results_and_figures(tmp_path):
    gates = smoke_gates(tmp_path / "gates.toml")
    out = tmp_path / "run"
    assert run(gates, out) == rc.EXIT_DONE
    result = json.loads((out / "results.json").read_text())
    assert result["controls_all_pass"], result["controls"]
    assert set(result["controls"]) == {"ctl_same_seed", "ctl_stand_still", "ctl_still_3v3", "ctl_tiny_tag", "ctl_tag_off",
                                       "tags_at_most_min_team", "paired_starts", "no_nonfinite_actions"}
    groups = {g["name"]: g for g in result["groups"]}
    assert len(groups["base"]["rows"]) == 2 and groups["size_1v1"]["skipped_duplicates"] == [["guard_field", "strike_sacrifice"]]
    row = groups["base"]["rows"][0]
    for key in ("hold_rate", "reach_rate", "timeout_rate", "tags_mean", "start_miss_games", "start_team_close_games",
                "closest_cross_3d_m", "unfinished"):
        assert key in row
    assert row["games"] + row["unfinished"] == 4                     # 6 ticks: no game finishes, none is counted
    assert (out / "gates.toml").read_bytes() == gates.read_bytes()
    assert (out / driver.PINNED_SHA).read_text().strip() == sweep.load_gates(gates).sha256
    assert len(list((out / "cells").glob("*.json"))) == 10
    assert groups["ctl_still_3v3"]["rows"][0]["unfinished"] == 4      # its own 3-tick cap
    md = (out / "results.md").read_text()
    assert "Controls (read these first)" in md and "Sensitivity: every Strike drone starts 1 mm higher" in md
    assert "L011-F1" in md and "Never suspend" in md
    assert result["shortlist"]["shortlist"][0] == "base"                # the reference, always carried
    assert "shortlist" in result and result["shortlist"]["variants"]
    # the record writer drafts the record from the run folder alone, and never overwrites one
    records = tmp_path / "records"
    argv = ["--run-dir", str(out), "--number", "W99", "--out-dir", str(records), "--ledger", str(tmp_path / "L.md")]
    assert recorder.main(argv) == 0
    text = (records / "run_record.md").read_text()
    assert text.startswith("Simulator: training simulator, tier 1")
    for section in ("## Purpose", "## Commit", "## Config", "## Seeds", "## Machine", "## Games at once",
                    "## Steps per second", "## Gates", "## Shortlist for L0.12"):
        assert section in text
    assert sweep.load_gates(gates).sha256 in text and "L011-F1" in text and "never suspend" in text.lower()
    assert recorder.main(argv) == 1
    assert not (tmp_path / "L.md").exists()                           # the ledger only with --append-ledger


def test_the_run_refuses_a_changed_gate_file(tmp_path, capsys):
    gates = smoke_gates(tmp_path / "gates.toml")
    out = tmp_path / "run"
    first = driver.main(["--gates", str(gates), "--run-dir", str(out), "--cap-h", "1e-9", "--no-clips"])
    assert first == rc.EXIT_CAP and (out / driver.PINNED_SHA).is_file()      # the first launch pinned the sha256
    gates.write_text(gates.read_text() + "# a limit moved after a result\n")
    assert run(gates, out) == rc.EXIT_REFUSED
    assert "changed since the first launch" in capsys.readouterr().err


def test_the_run_refuses_a_game_file_whose_sha256_is_not_the_pinned_one(tmp_path, capsys):
    edited = tmp_path / "base.toml"
    edited.write_text((ROOT / "configs/ste_l011/base.toml").read_text() + "# edited\n")
    pinned = sweep.load_gates().games["base"].sha256
    gates = smoke_gates(tmp_path / "gates.toml", games={"base": {"file": str(edited), "sha256": pinned}})
    assert run(gates, tmp_path / "run") == rc.EXIT_REFUSED
    assert "game file(s) differ" in capsys.readouterr().err


def test_the_expected_gate_sha256_is_checked(tmp_path, capsys):
    gates = smoke_gates(tmp_path / "gates.toml")
    assert run(gates, tmp_path / "run", "--expect-gates-sha256", "0" * 64) == rc.EXIT_REFUSED


def test_sigint_stops_and_the_same_command_resumes_to_the_same_results(tmp_path):
    gates = smoke_gates(tmp_path / "gates.toml")
    whole = tmp_path / "whole"
    assert run(gates, whole) == rc.EXIT_DONE
    out = tmp_path / "split"
    cmd = [DRIVER, "--gates", gates, "--run-dir", out, "--cap-h", CAP_H, "--no-clips", "--sleep-between-batches-s", "1"]
    env = tool_env(tmp_path / "shared")
    proc = start_py(cmd, env, log=tmp_path / "split.log")
    try:
        first = out / "cells" / "base__b00.json"
        wait_for(first.exists, what="the first batch")
        os.kill(proc.pid, signal.SIGINT)
        assert proc.wait(timeout=60) == rc.EXIT_INTERRUPTED
    finally:
        reap(proc)
    done_before = json.loads((out / rc.CHECKPOINT_NAME).read_text())["state"]["done"]
    assert 1 <= len(done_before) < 10
    stamp = first.stat().st_mtime_ns
    again = run_py([*cmd[:-2]], env)
    assert again.returncode == rc.EXIT_DONE, again.stderr
    assert "resumed" in again.stdout
    assert first.stat().st_mtime_ns == stamp                          # a finished batch is not played again
    assert rows_of(out) == rows_of(whole)                             # same numbers as the run that was never stopped


def test_the_cap_stops_the_run_with_exit_3_and_results_and_an_aborted_record(tmp_path, monkeypatch):
    gates = smoke_gates(tmp_path / "gates.toml")
    code = driver.main(["--gates", str(gates), "--run-dir", str(tmp_path / "first"), "--cap-h", "1e-9", "--no-clips"])
    assert code == rc.EXIT_CAP
    out = tmp_path / "run"                           # the cap reached once the first batch is written
    monkeypatch.setattr(rc.RunGuard, "cap_reached", lambda self: (out / "cells" / "base__b00.json").exists())
    assert run(gates, out) == rc.EXIT_CAP
    result = json.loads((out / "results.json").read_text())
    assert result["stopped"] == "cap" and len(rows_of(out)["base"]) == 1
    (out / "exit_code").write_text("3\n")         # as the launcher's wrapper records it
    records = tmp_path / "records"
    assert recorder.main(["--run-dir", str(out), "--number", "W98", "--out-dir", str(records)]) == 0
    text = (records / "run_record.md").read_text()
    assert "ABORTED" in text and "3 (CAP)" in text


def test_a_failed_control_ends_the_run_with_exit_6_and_a_relaunch_ends_with_6_again(tmp_path, monkeypatch, capsys):
    """LEAD CALL 21 Nov 2026: CONTROL_FAILED (6) is terminal, never retried: the same command on the same folder ends 6."""
    gates = smoke_gates(tmp_path / "gates.toml")
    monkeypatch.setattr(sweep, "check_paired_starts", lambda shas: (False, "forced failure (test)"))
    out = tmp_path / "run"
    assert run(gates, out) == rc.EXIT_CONTROL_FAILED == 6
    assert len(json.loads((out / rc.CHECKPOINT_NAME).read_text())["state"]["done"]) == 1
    assert "no result below may be read" in (out / "results.md").read_text()
    assert json.loads((out / "results.json").read_text())["stopped"] == "control failed"
    monkeypatch.undo()
    monkeypatch.setenv(shared.SHARED_ENV, str(tmp_path / "shared"))
    assert run(gates, out) == rc.EXIT_CONTROL_FAILED
    assert "failed in this run folder" in capsys.readouterr().err


@pytest.mark.parametrize("gpu_h,why", [(0.5, "keep the two equal"), (1.0, "with device 'cpu'")])
def test_the_launchers_hours_must_match_the_cap_and_the_device(tmp_path, capsys, gpu_h, why):
    gates = smoke_gates(tmp_path / "gates.toml")
    out = tmp_path / "run"
    out.mkdir()
    (out / "job.json").write_text(json.dumps({"gpu_h": gpu_h}))
    assert run(gates, out) == rc.EXIT_REFUSED
    assert why in capsys.readouterr().err


def test_the_pilot_measures_every_point_and_projects_each_batch_size(tmp_path):
    gates = smoke_gates(tmp_path / "gates.toml")
    out = tmp_path / "pilot"
    assert driver.main(["--gates", str(gates), "--run-dir", str(out), "--cap-h", CAP_H, "--pilot"]) == rc.EXIT_DONE
    pilot = json.loads((out / "pilot.json").read_text())
    assert [(p["size"], p["cells"]) for p in pilot["points"]] == [("1v1", 1), ("1v1", 2), ("3v3", 1), ("3v3", 2)]
    assert all(p["seconds_per_tick"] > 0 for p in pilot["points"])
    assert [p["cells_per_batch"] for p in pilot["projections"]] == [1, 2]
    assert all(p["projected_s"] is not None for p in pilot["projections"])
    assert "projected GPU-h" in (out / "pilot.md").read_text()


def test_end_to_end_through_the_launcher_with_figures_and_a_clip(tmp_path):
    gates = smoke_gates(tmp_path / "gates.toml", run={"ticks_cap": 4})
    env = tool_env(tmp_path / "shared", OMP_NUM_THREADS="4")
    out = tmp_path / "runs" / "e2e"
    launched = run_py([TOOL, "launch", "--task", "L0.11", "--name", "l011_e2e", "--run-dir", out, "--min-s", "0",
                       "--gpu-h", "0", "--", sys.executable, DRIVER, "--gates", gates, "--run-dir", out, "--cap-h", CAP_H],
                      env)
    assert launched.returncode == 0, launched.stderr
    waited = run_py([TOOL, "wait", "l011_e2e", "--poll-s", "0.2"], env, timeout_s=300)
    assert waited.returncode == 0, (waited.stdout, (out / "job.log").read_text())
    assert "DONE exit=0" in waited.stdout
    result = json.loads((out / "results.json").read_text())
    assert result["controls_all_pass"]
    assert (out / "figures" / "base_heatmap.png").is_file() and (out / "figures" / "factors.png").is_file()
    assert list((out / "videos").glob("*.gif")), result["clips"]
    assert not (tmp_path / "shared" / shared.GPU_HOURS_LOG_NAME).exists()      # a CPU job logs no GPU-hours


def test_a_laptop_suspend_counts_against_the_cap(tmp_path):
    """The finding for the lead: the cap clock is the wall clock (time.time) less the owner's pauses of this process.
    A suspend (closed lid) stops the process but writes no pause line, so the jump of the wall clock across it is
    counted as effective time: the cap is reached by sleeping. (The launcher's wrapper bills the GPU-hour ledger the
    same way: its next beat logs an interval from its last beat to after the resume.)"""
    now = [1_000_000.0]
    with rc.RunGuard(tmp_path / "run", cap_s=3600.0, clock=lambda: now[0]) as guard:
        assert not guard.cap_reached()
        now[0] += 2 * 3600.0                                          # two hours with the lid closed
        assert guard.effective_s() == 2 * 3600.0 and guard.cap_reached()
