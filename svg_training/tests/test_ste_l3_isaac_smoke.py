"""STE L3-L6 pipeline check, task L3.1: the Isaac smoke of the tier-2 skills fixed-choice replay,
scripts/ste_l3_isaac_smoke.py (spec ste_learning/drafts/L3_L6_PIPELINE_SPEC.md section 4). On the CPU with --dry-cpu
(the PyTorch reference world stands in for Isaac Lab), small: the six checks run and pass, the files are written, the
run contract holds (a finished folder does nothing new; a failed control is terminal, exit 6), and the refusals exit 2.
No Isaac run."""
import json
import sys

import pytest

from svg_training.ste import exploit, shared

from _ste_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import ste_l3_isaac_smoke as smoke  # noqa: E402

GATES = exploit.ROOT / "configs" / "ste_l3" / "skills_gates.toml"
CHECKS = ("ctl_replay_guard", "ctl_replay_strike", "ctl_device_placement", "ctl_reload_across_devices",
          "ctl_clips", "ctl_nonfinite_stale")


def run(run_dir, *extra, gates=GATES):
    return smoke.main(["--gates", str(gates), "--run-dir", str(run_dir), "--cap-h", "0.3", "--dry-cpu", "--games", "4",
                       "--max-ticks", "90", *extra])


@pytest.fixture(autouse=True)
def scratch_shared(tmp_path, monkeypatch):
    monkeypatch.setenv(shared.SHARED_ENV, str(tmp_path / "shared"))
    monkeypatch.setenv(shared.LEGACY_LOGS_ENV, "")


@pytest.fixture(scope="module")
def done(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("l3_smoke")
    mp = pytest.MonkeyPatch()
    mp.setenv(shared.SHARED_ENV, str(tmp / "shared"))
    mp.setenv(shared.LEGACY_LOGS_ENV, "")
    assert run(tmp / "run") == 0
    mp.undo()
    return tmp / "run"


def test_the_six_checks_pass_and_the_files_are_written(done):
    controls = json.loads((done / "controls.json").read_text())
    for k in CHECKS:
        assert controls[k]["status"] == "PASS", (k, controls[k])
    res = json.loads((done / "results.json").read_text())
    assert res["complete"] and res["tier"] == "reference world (--dry-cpu, not of record)"
    assert res["status"] == "pipeline check, not for flight"
    th = res["throughput"]
    assert th["two_level_game_steps_per_s"] > 0 and th["one_script_game_steps_per_s"] > 0 and th["ratio"] > 0
    cells = res["replay"]
    assert {c["side"] for c in cells} == {"guard", "strike"}
    assert sum(1 for c in cells if c["kind"] == "mixed") == 6                     # 3 combinations per side
    assert all((done / v.split(":")[0]).is_file() for v in res["clips"])
    assert (done / "results.md").read_text().startswith("Simulator:")


def test_the_same_command_on_a_finished_folder_does_nothing_new(done):
    before = (done / "results.json").read_text()
    assert run(done) == 0
    assert (done / "results.json").read_text() == before


def test_a_failed_replay_is_terminal_exit_6(tmp_path, monkeypatch):
    monkeypatch.setattr(exploit, "replay_ok", lambda *a, **k: (False, "forced by the test"))
    r = tmp_path / "run"
    assert run(r) == 6
    assert json.loads((r / "controls.json").read_text())["ctl_replay_guard"]["status"] == "FAIL"
    assert not (r / "results.json").exists()
    monkeypatch.undo()
    assert run(r) == 6                                                         # terminal in its folder


def test_refusals_exit_2(tmp_path):
    velocity = exploit.ROOT / "configs" / "ste_l3" / "velocity_gates.toml"
    assert run(tmp_path / "a", gates=velocity) == 2                            # the skills route only
    assert smoke.main(["--gates", str(GATES), "--run-dir", str(tmp_path / "b"), "--cap-h", "0.3"]) == 2   # --headless
    assert run(tmp_path / "c", "--games", "0") == 2
    assert smoke.main(["--gates", str(GATES), "--run-dir", str(tmp_path / "d"), "--cap-h", "0", "--dry-cpu"]) == 2
