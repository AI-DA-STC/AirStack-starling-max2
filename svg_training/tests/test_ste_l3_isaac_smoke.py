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


# ------------------------------------------------------------------------------------------- QC round (S5, S6)
def test_the_smoke_records_two_clips_upsets_syncs_and_is_not_of_record_on_the_cpu(done):
    res = json.loads((done / "results.json").read_text())
    assert len(res["clips"]) == 2 and all((done / v.split(":")[0]).is_file() for v in res["clips"])
    assert res["of_record"] is False
    assert set(res["upsets"]) == {"guard", "strike"}
    assert all(isinstance(v, int) for side in res["upsets"].values() for v in side.values())
    assert "not checked" in res["host_syncs_in_dispatch"] and "CPU" in res["host_syncs_in_dispatch"]
    assert "Isaac" in res["cuda_replay_tolerance"]
    controls = json.loads((done / "controls.json").read_text())
    assert "host syncs" in controls["ctl_device_placement"]["detail"]
    assert "2 clips" in controls["ctl_clips"]["detail"]


def test_of_record_only_on_isaac_at_the_full_size():
    g = exploit.load_gates(GATES)
    n, t = int(g.run["eval_games"]), int(g.run["ticks_cap"])
    assert smoke.of_record(g, dry_cpu=False, games=n, ticks=t)
    assert not smoke.of_record(g, dry_cpu=True, games=n, ticks=t)
    assert not smoke.of_record(g, dry_cpu=False, games=n - 1, ticks=t)
    assert not smoke.of_record(g, dry_cpu=False, games=n, ticks=t - 1)


def test_a_small_isaac_smoke_needs_its_test_flag(tmp_path, capsys):
    args = ["--gates", str(GATES), "--run-dir", str(tmp_path / "r"), "--cap-h", "0.3", "--headless", "--games", "4"]
    assert smoke.main(args) == 2
    assert "--small-test" in capsys.readouterr().err
    assert smoke.main(args + ["--small-test"]) == 2                            # then the run folder rule (not runs/)
    assert "--small-test" not in capsys.readouterr().err


def test_the_sync_counter_passes_the_dispatch_through():
    import torch

    class Inner:
        team, name, holds_choice, dispatch = "guard", "inner", True, "d"

        def choose(self, obs):
            return obs + 1

        def command(self, obs, held):
            return obs * held
    w = smoke.SyncCount(Inner(), "cpu")
    x = torch.ones(2)
    assert torch.equal(w.choose(x), x + 1) and torch.equal(w.command(x, x), x)
    assert w.holds_choice and w.dispatch == "d" and w.team == "guard" and w.syncs == 0 and w.checked is False
