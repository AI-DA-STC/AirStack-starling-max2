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
import check_ste_l011_smoke as smoke_check  # noqa: E402
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
    assert set(result["controls"]) == {"ctl_tag_fires_2v1", "ctl_tag_fires_5v3", "ctl_reach_fires_1v1", "ctl_same_seed",
                                       "ctl_stand_still", "ctl_still_3v3", "ctl_tiny_tag", "ctl_tag_off",
                                       "tags_one_for_one", "paired_starts", "no_nonfinite_actions"}
    groups = {g["name"]: g for g in result["groups"]}
    assert len(groups["base"]["rows"]) == 2 and groups["size_1v1"]["skipped_duplicates"] == [["guard_field", "strike_sacrifice"]]
    row = groups["base"]["rows"][0]
    for key in ("hold_rate", "reach_rate", "timeout_rate", "tags_mean", "start_miss_games", "start_team_close_games",
                "closest_cross_3d_m", "unfinished"):
        assert key in row
    assert row["games"] + row["unfinished"] == 4                     # 6 ticks: no game finishes, none is counted
    assert (out / "gates.toml").read_bytes() == gates.read_bytes()
    assert (out / driver.PINNED_SHA).read_text().strip() == sweep.load_gates(gates).sha256
    assert len(list((out / "cells").glob("*.json"))) == 13
    timing = json.loads((out / rc.CHECKPOINT_NAME).read_text())["state"]["timing"]
    assert {k: len(v) for k, v in timing.items()} == {"3v3": 4, "1v1": 1}     # QC I2: sweep and sensitivity batches only
    assert groups["ctl_still_3v3"]["rows"][0]["unfinished"] == 4      # its own 3-tick cap
    md = (out / "results.md").read_text()
    assert "Controls (read these first)" in md and "Sensitivity: every Strike drone starts 1 mm higher" in md
    assert "L011-F1" in md and "Never suspend" in md
    assert result["shortlist"]["shortlist"][0] == "base"                # the reference, always carried
    assert "parked (holds starts; = still at 2+ Guards)" in md          # QC M-10 label, 3v3 base rows
    assert "among drones still in the game after the tag step" in md   # QC M-3 wording
    assert "no proximity tag (INFO" in md                                # M-8: the tag-off INFO reference row
    assert result["shortlist"]["info_reference"][0]["variant"] == "ctl_tag_off"
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
    assert "among drones still in the game after the tag step" in text
    assert "no proximity tag (INFO" not in text        # this record is not INFO (no exit code): no numbers, no reference
    assert recorder.main(argv) == 1
    assert not (tmp_path / "L.md").exists()                           # the ledger only with --append-ledger
    assert "ABORTED" in text and "no exit_code" in text                 # QC M-4: no exit code is never INFO
    (out / "exit_code").write_text("0\n")
    assert recorder.main(["--run-dir", str(out), "--number", "W99", "--out-dir", str(tmp_path / "r2")]) == 0
    assert "Verdict: **INFO" in (tmp_path / "r2" / "run_record.md").read_text()
    assert "no proximity tag (INFO" in (tmp_path / "r2" / "run_record.md").read_text()


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
    assert 1 <= len(done_before) < 13
    stamp = first.stat().st_mtime_ns
    again = run_py([*cmd[:-2]], env)
    assert again.returncode == rc.EXIT_DONE, again.stderr
    assert "resumed" in again.stdout
    assert first.stat().st_mtime_ns == stamp                          # a finished batch is not played again
    assert rows_of(out) == rows_of(whole)                             # same numbers as the run that was never stopped
    # the I6 check script's SIGINT drill line, on this folder (the launcher's files written as ste_job.py writes them)
    resumes = json.loads((out / rc.CHECKPOINT_NAME).read_text())["state"]["resumes"]
    assert resumes and set(resumes[0]["done"]) == set(done_before)
    (out / "launches.jsonl").write_text("\n".join(json.dumps(e) for e in (
        {"event": "launch", "launch": 1, "time": 0.0}, {"event": "end", "launch": 1, "time": 1.0, "exit_code": 4},
        {"event": "launch", "launch": 2, "time": resumes[0]["time"]},
        {"event": "end", "launch": 2, "time": resumes[0]["time"] + 1, "exit_code": 0})) + "\n")
    lines = []
    smoke_check.print = lambda text: lines.append(text)          # capture its lines (module-level print)
    try:
        smoke_check.main(["--run-dir", str(out), "--expect-sigint", "--device-expected", "cpu"])
    finally:
        del smoke_check.print
    assert any(x.startswith("PASS SIGINT drill") for x in lines), lines
    assert any(x.startswith("PASS resumed 1 time(s)") for x in lines), lines


def test_the_cap_stops_the_run_with_exit_3_and_results_and_an_aborted_record(tmp_path, monkeypatch):
    gates = smoke_gates(tmp_path / "gates.toml")
    code = driver.main(["--gates", str(gates), "--run-dir", str(tmp_path / "first"), "--cap-h", "1e-9", "--no-clips"])
    assert code == rc.EXIT_CAP
    out = tmp_path / "run"                           # the cap reached once the first base batch is written
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
    assert [(p["size"], p["cells"]) for p in pilot["points"]] == [(z, c) for z in ("1v1", "2v1", "3v3", "5v3") for c in (1, 2)]
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
    assert smoke_check.main(["--run-dir", str(out), "--device-expected", "cpu"]) == 0          # the I6 check script
    assert smoke_check.main(["--run-dir", str(out)]) == 1                                      # not a CUDA run


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


# ================================================================================================ QC fix round 1
def _proximity_tags():
    from svg_training.core import pair_rules
    return pair_rules.proximity_tags


def _hit_any(pos_m, alive, guards, radius_m, guard_survives):
    """QC M3: one Guard tags every Strike in range (the F5 'hit.any' rule), not one for one."""
    import torch
    d = (pos_m[:, :guards, None, :] - pos_m[:, None, guards:, :]).norm(dim=-1)
    near = alive[:, :guards, None] & alive[:, None, guards:] & (d < radius_m)
    tagged = torch.cat((near.any(dim=2), near.any(dim=1)), dim=1)
    leaves = torch.cat((tagged[:, :guards] & ~guard_survives[:, None], tagged[:, guards:]), dim=1)
    return tagged, alive & ~leaves, torch.full_like(alive, -1, dtype=torch.long)


def _mutate(monkeypatch, name):
    """QC's breakages (runs/ste_l11_qc.md section 3), applied in process to the real game and driver."""
    import torch
    from svg_training.core import game as game_module
    original = _proximity_tags()
    if name == "M1_tag_counter_dead":
        step = sweep.SweepGame.step

        def dead(self, actions):
            out = step(self, actions)
            self.tags = self.tags * 0
            return out
        monkeypatch.setattr(sweep.SweepGame, "step", dead)
    elif name == "M2_tag_never_fires":
        monkeypatch.setattr(game_module, "proximity_tags", lambda p, a, g, r, s: original(p, a, g, 0.0, s))
    elif name == "M3_one_guard_tags_all":
        monkeypatch.setattr(game_module, "proximity_tags", _hit_any)
    elif name == "M4_guards_always_survive":
        monkeypatch.setattr(game_module, "proximity_tags", lambda p, a, g, r, s: original(p, a, g, r, torch.ones_like(s)))
    elif name == "M11_zone_never_fires":
        draw = game_module.draw_arenas

        def no_zone(*args, **kwargs):
            ar = draw(*args, **kwargs)
            ar.zone_radius_m = ar.zone_radius_m * 0
            return ar
        monkeypatch.setattr(game_module, "draw_arenas", no_zone)
    else:
        raise KeyError(name)


@pytest.mark.parametrize("mutant,caught_by", [
    ("M1_tag_counter_dead", "ctl_tag_fires_2v1"), ("M2_tag_never_fires", "ctl_tag_fires_2v1"),
    ("M3_one_guard_tags_all", "ctl_tag_fires_2v1"), ("M4_guards_always_survive", "ctl_tag_fires_2v1"),
    ("M11_zone_never_fires", "ctl_reach_fires_1v1")])
def test_qcs_breakages_each_end_the_real_driver_with_exit_6(tmp_path, monkeypatch, mutant, caught_by):
    """QC C1: each of the breakages that passed every control before now ends in CONTROL_FAILED, before any sweep cell."""
    gates = smoke_gates(tmp_path / "gates.toml")
    _mutate(monkeypatch, mutant)
    out = tmp_path / "run"
    assert run(gates, out) == rc.EXIT_CONTROL_FAILED
    controls = json.loads((out / "controls.json").read_text())
    assert controls[caught_by]["status"] == "FAIL", controls
    assert not (out / "cells" / "base__b00.json").exists()


def test_the_clean_known_answer_controls_pass_exactly(tmp_path):
    gates = smoke_gates(tmp_path / "gates.toml")
    out = tmp_path / "run"
    assert run(gates, out) == rc.EXIT_DONE
    controls = json.loads((out / "controls.json").read_text())
    for name in ("ctl_tag_fires_2v1", "ctl_tag_fires_5v3", "ctl_reach_fires_1v1", "tags_one_for_one"):
        assert controls[name]["status"] == "PASS", controls[name]


def test_the_run_refuses_before_play_when_the_protected_groups_alone_cannot_fit_the_cap(tmp_path, capsys):
    """QC I3 (H6): projection x 1.1 + 600 s of base and the controls alone is over the cap: exit 2, nothing played."""
    slow = {"1v1": 100.0, "2v1": 100.0, "3v3": 100.0, "5v3": 100.0}
    gates = smoke_gates(tmp_path / "gates.toml", projection=slow)
    out = tmp_path / "run"
    assert run(gates, out) == rc.EXIT_REFUSED
    assert "protected" in capsys.readouterr().err and not list((out / "cells").glob("*.json"))


def test_a_gate_that_requires_the_projection_refuses_without_it(tmp_path, capsys):
    gates = smoke_gates(tmp_path / "gates.toml", run={"require_projection": True})
    assert run(gates, tmp_path / "run") == rc.EXIT_REFUSED
    assert "seconds_per_batch_tick" in capsys.readouterr().err


def test_a_failed_control_run_writes_no_shortlist_numbers_into_results_record_or_ledger_row(tmp_path, monkeypatch,
                                                                                           capsys):
    """QC I4: an ABORTED row carries only what ran and why."""
    gates = smoke_gates(tmp_path / "gates.toml")
    _mutate(monkeypatch, "M4_guards_always_survive")
    out = tmp_path / "run"
    assert run(gates, out) == rc.EXIT_CONTROL_FAILED
    md = (out / "results.md").read_text()
    assert "Shortlist: **" not in md and "not read" in md
    (out / "exit_code").write_text("6\n")
    capsys.readouterr()
    assert recorder.main(["--run-dir", str(out), "--number", "W97", "--out-dir", str(tmp_path / "rec")]) == 0
    text = (tmp_path / "rec" / "run_record.md").read_text()
    row = capsys.readouterr().out.strip().splitlines()[-1]
    assert "| Variant | H" not in text and "Not read: control" in text and "ABORTED" in text
    assert " H " not in row and "shortlist" not in row and "ABORTED" in row
    assert smoke_check.main(["--run-dir", str(out), "--device-expected", "cpu"]) == 1


def test_the_code_is_pinned_at_the_first_launch(tmp_path, monkeypatch, capsys):
    """QC M-2: a resume on other code is refused unless --allow-code-change, which is recorded."""
    gates = smoke_gates(tmp_path / "gates.toml")
    out = tmp_path / "run"
    stop = ["--gates", str(gates), "--run-dir", str(out), "--cap-h", "1e-9", "--no-clips"]
    assert driver.main(stop) == rc.EXIT_CAP
    pinned = json.loads((out / driver.CODE_FILE).read_text())
    monkeypatch.setattr(driver, "code_identity", lambda: {"commit": "0" * 40, "diff_sha256": "x"})
    assert driver.main(stop) == rc.EXIT_REFUSED
    assert "code changed" in capsys.readouterr().err
    assert driver.main(stop + ["--allow-code-change"]) == rc.EXIT_CAP
    after = json.loads((out / driver.CODE_FILE).read_text())
    assert after["first"] == pinned["first"] and after["changes"][0]["commit"] == "0" * 40


def test_a_non_finite_action_writes_results_before_exit_5(tmp_path, monkeypatch):
    """QC M-1."""
    gates = smoke_gates(tmp_path / "gates.toml")
    real = sweep.play_batch

    def nan_batch(*args, **kwargs):
        res = real(*args, **kwargs)
        res.nonfinite_actions = 1
        return res
    monkeypatch.setattr(sweep, "play_batch", nan_batch)
    out = tmp_path / "run"
    assert run(gates, out) == rc.EXIT_NONFINITE
    assert json.loads((out / "results.json").read_text())["stopped"] == "non-finite"


def test_a_pilot_stopped_at_its_cap_still_writes_its_table(tmp_path):
    """QC M-6."""
    gates = smoke_gates(tmp_path / "gates.toml")
    out = tmp_path / "pilot"
    assert driver.main(["--gates", str(gates), "--run-dir", str(out), "--cap-h", "1e-9", "--pilot"]) == rc.EXIT_CAP
    assert (out / "pilot.md").is_file() and "stopped" in (out / "pilot.md").read_text()


def test_the_pilot_times_moving_guards_first(tmp_path):
    """QC M-10: the 1-, 4- and 10-cell pilot points must not time guard_parked_centre (= still at 2+ Guards) alone."""
    g = sweep.load_gates()
    cells = driver.pilot_cells(g)
    assert cells[0][0] not in ("guard_parked_centre", "guard_parked_ring")
    assert "guard_parked_centre" not in {c[0] for c in cells[:4]}


def test_clips_stop_when_a_stop_is_asked(tmp_path):
    """QC M-5: the clip loop honours SIGINT."""
    gates = sweep.load_gates(smoke_gates(tmp_path / "gates.toml"))
    notes = driver.make_clips(gates, tmp_path, should_stop=lambda: True)
    assert notes and "stopped" in notes[0] and not (tmp_path / "videos").exists()
