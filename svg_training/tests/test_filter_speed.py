"""Tests for scripts/filter_speed.py (S2 Task 7): selection rule, accuracy phase (7a), T2 path untouched."""
import importlib.util
import json
import pathlib
import tomllib

import numpy as np
import pytest
import torch

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"scripts/{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _acc(it, k, ok):
    return {"iterations": it, "check_every": k, "all_pass": ok}


def _spd(it, k, rate):
    return {"iterations": it, "check_every": k, "game_steps_per_s": rate}


def test_filter_speed_selection_rule():
    fs = _load("filter_speed")
    # made-up measurements: 100 sweeps is fastest but inaccurate; 200 sweeps accurate at every check_every
    acc = [_acc(1000, 0, True), _acc(1000, 8, True), _acc(200, 0, True), _acc(200, 8, True),
           _acc(100, 0, False), _acc(100, 8, False)]
    spd = [_spd(1000, 0, 10_000.0), _spd(1000, 8, 60_000.0), _spd(200, 0, 50_000.0), _spd(200, 8, 140_000.0),
           _spd(100, 0, 90_000.0), _spd(100, 8, 300_000.0)]
    sel = fs.select_candidate(acc, spd, 100_000)
    assert sel["verdict"] == "PASS" and sel["chosen"] == (200, 8)
    assert sel["fastest"] == (100, 8) and sel["fastest_accurate"] == (200, 8)

    # nothing accurate reaches the target: FAIL, the record lists the fastest accurate and the fastest
    slow = [dict(r, game_steps_per_s=r["game_steps_per_s"] / 3) for r in spd]
    sel = fs.select_candidate(acc, slow, 100_000)
    assert sel["verdict"] == "FAIL" and sel["chosen"] is None
    assert sel["fastest_accurate"] == (200, 8) and sel["fastest"] == (100, 8)

    # an iterations count passes only when every check_every measured with it passes
    acc2 = [_acc(200, 0, True), _acc(200, 8, False), _acc(1000, 0, True), _acc(1000, 8, True)]
    sel = fs.select_candidate(acc2, spd[:4], 100_000)
    assert sel["verdict"] == "FAIL" and sel["fastest_accurate"] == (1000, 8)

    # nothing accurate at all
    sel = fs.select_candidate([_acc(100, 0, False)], [_spd(100, 0, 500_000.0)], 100_000)
    assert sel["verdict"] == "FAIL" and sel["fastest_accurate"] is None and sel["fastest"] == (100, 0)

    # a speed row without an accuracy row is never chosen
    sel = fs.select_candidate([_acc(200, 0, True)], [_spd(50, 0, 900_000.0), _spd(200, 0, 120_000.0)], 100_000)
    assert sel["chosen"] == (200, 0)


def test_filter_parity_defaults_unchanged():
    """run_port without filter_kw is T2's call: bit-identical to filter_velocities with T2's arguments."""
    fp = _load("filter_parity")
    scenes = fp.make_scenes(60, 3)
    nom, pos, mask, cap = fp._batch(scenes)
    direct = fp.filter_velocities(nom, pos, mask, fp.RADIUS_M, cap, alpha=fp.ALPHA, iterations=200,
                                  tolerance=fp.TOL)
    for port in (fp.run_port(scenes, 200), fp.run_port(scenes, 200, check_every=0)):
        v = direct.velocities.double().numpy()
        assert all(np.array_equal(port["vel"][k], v[k, : len(s.pos_m)]) for k, s in enumerate(scenes))
        assert np.array_equal(port["emergency"], direct.emergency.numpy())
    a = fp.cross_team_check(scenes, fp.run_port(scenes, 200), 200, torch.float32)
    b = fp.cross_team_check(scenes, fp.run_port(scenes, 200), 200, torch.float32, check_every=0)
    assert a == b


def _small_gates(tmp_path):
    text = (ROOT / "configs/s2.toml").read_text()
    text = text.replace("iterations = [1000, 500, 300, 200, 100]", "iterations = [60, 20]")
    text = text.replace("check_every = [0, 8, 32]", "check_every = [0, 8]")
    text = text.replace("scenes = 2000", "scenes = 40")
    path = tmp_path / "s2.toml"
    path.write_text(text)
    g = tomllib.loads(text)
    assert g["filter_speed"]["iterations"] == [60, 20] and g["filter_speed_gates"]["scenes"] == 40
    return path


def test_accuracy_phase_writes_run_folder_and_refuses_overwrite(tmp_path):
    fs = _load("filter_speed")
    gates = _small_gates(tmp_path)
    runs = tmp_path / "runs"
    args = ["--gates", str(gates), "--name", "x_s2_filter_speed", "--phase", "accuracy", "--runs-dir", str(runs)]
    assert fs.main(args) == 0
    out = runs / "x_s2_filter_speed"
    assert (out / "gates.toml").read_text() == gates.read_text()
    rows = json.loads((out / "accuracy.json").read_text())["rows"]
    assert [(r["iterations"], r["check_every"]) for r in rows] == [(60, 0), (60, 8), (20, 0), (20, 8)]
    five = ["max_abs_dv_mps", "constraint_residual_max", "emergency_agreement_min", "cross_team_corrections",
            "max_abs_dv_first_phase_mps"]
    for r in rows:
        assert set(five) <= set(r["measured"]) and set(r["passed"]) == set(five)
        assert r["all_pass"] == all(r["passed"].values())
        assert r["max_dv_vs_fixed_loop_mps"] <= 1e-5  # check_every changes the answer by rounding only
    table = (out / "accuracy.md").read_text()
    assert table.splitlines()[0].startswith("Simulator: training simulator")
    for name in five:
        assert name in table
    assert fs.main(args) == 1  # refuses to overwrite
    assert not (ROOT / "records" / "x_s2_filter_speed_record.md").exists()  # 7a writes no record


def test_speed_phase_cpu_smoke_writes_tables_and_selection(tmp_path):
    """Both phases end to end on the CPU with a tiny case: speed rows for every candidate, the pass-through
    baseline, the selection, and refusal to overwrite. (The run of record is on the GPU.)"""
    fs = _load("filter_speed")
    gates = _small_gates(tmp_path)
    gates.write_text(gates.read_text().replace("num_games = 4096", "num_games = 4"))
    runs = tmp_path / "runs"
    args = ["--gates", str(gates), "--name", "z", "--phase", "both", "--runs-dir", str(runs), "--device", "cpu",
            "--sync-steps", "0", "--timing-override",
            json.dumps({"warmup_steps": 1, "timed_steps": 2, "min_timed_s": 0.0, "min_warmup_s": 0.0})]
    assert fs.main(args) == 0
    out = runs / "z"
    speed = json.loads((out / "speed.json").read_text())
    assert [(r["iterations"], r["check_every"]) for r in speed["rows"]] == [(60, 0), (60, 8), (20, 0), (20, 8)]
    for r in speed["rows"] + [speed["baseline"]]:
        assert r["status"] == "ok" and r["game_steps_per_s"] > 0 and len(r["repeats_game_steps_per_s"]) == 2
        assert r["nan_count"] == 0
    assert all(r["filter_share"] is not None for r in speed["rows"])
    assert speed["context"]["local_file"] is None and speed["context"]["case"]["num_games"] == 4
    sel = json.loads((out / "selection.json").read_text())
    assert sel["verdict"] in ("PASS", "FAIL") and "accurate_iterations" in sel
    table = (out / "speed.md").read_text()
    assert table.splitlines()[0].startswith("Simulator: training simulator, tier 1 (S2 game with the Starling layer")
    full_args = ["--gates", str(gates), "--name", "z", "--phase", "fullgame", "--runs-dir", str(runs), "--device",
                 "cpu", "--sync-steps", "0"]
    assert fs.main(full_args) == 0                            # INFO: early-stop candidates over one whole game
    full = json.loads((out / "fullgame.json").read_text())
    assert [(r["iterations"], r["check_every"]) for r in full["rows"]] == [(60, 8), (20, 8)]
    for r in full["rows"]:
        assert r["steps"] == 1200 and r["game_steps_per_s"] > 0 and len(r["segment_game_steps_per_s"]) == 12
    assert fs.main(full_args) == 1                            # refuses to overwrite
    assert fs.main(["--gates", str(gates), "--name", "nofolder", "--phase", "fullgame", "--runs-dir", str(runs),
                    "--device", "cpu"]) == 1                  # only into an existing run folder
    figs = _load("make_s2_figures")
    figs.filter_speed(str(out), str(tmp_path / "fig.png"))  # the record's figure script reads these files
    assert (tmp_path / "fig.png").stat().st_size > 10_000
    assert fs.main(args) == 1  # refuses to overwrite
    speed_only = ["--gates", str(gates), "--name", "z", "--phase", "speed", "--runs-dir", str(runs), "--device", "cpu"]
    assert fs.main(speed_only) == 1


def test_gate_passes_rounds_max_abs_dv_to_four_decimals():
    """Owner's ruling (16 November 2026): max_abs_dv_mps is compared at its written precision, 4 decimals."""
    fs = _load("filter_speed")
    assert fs.gate_passes("max_abs_dv_mps", 1.6666038415522255, 1.6666)  # T2's raw value passes
    assert fs.gate_passes("max_abs_dv_mps", 1.66664, 1.6666)
    assert not fs.gate_passes("max_abs_dv_mps", 1.66671, 1.6666)
    # every other gate compares as written
    assert not fs.gate_passes("constraint_residual_max", 2.0897301, 2.08973)
    assert not fs.gate_passes("max_abs_dv_first_phase_mps", 0.02000001, 0.02)
    assert fs.gate_passes("emergency_agreement_min", 0.999, 0.999)
    assert not fs.gate_passes("emergency_agreement_min", 0.9989999, 0.999)
    assert fs.gate_passes("cross_team_corrections", 0, 0) and not fs.gate_passes("cross_team_corrections", 1, 0)


def test_selection_applies_the_rounding_to_raw_rows():
    """select_candidate judges rows that carry raw values with gate_passes: T2's 1.6666038 counts as accurate."""
    fs = _load("filter_speed")
    limits = tomllib.loads((ROOT / "configs/s2.toml").read_text())["filter_speed_gates"]
    limits = {n: limits[n] for n in fs.GATE_ORDER}

    def row(it, k, dv):
        measured = {"max_abs_dv_mps": dv, "constraint_residual_max": 2.089727015421041,
                    "emergency_agreement_min": 0.999, "cross_team_corrections": 0,
                    "max_abs_dv_first_phase_mps": 6.18e-05}
        return {"iterations": it, "check_every": k, "measured": measured, "limits": limits, "all_pass": False}

    acc = [row(1000, 0, 1.6666038415522255), row(1000, 8, 1.6666038415522255), row(500, 0, 2.83), row(500, 8, 2.83)]
    spd = [_spd(1000, 0, 10_000.0), _spd(1000, 8, 120_000.0), _spd(500, 8, 400_000.0)]
    sel = fs.select_candidate(acc, spd, 100_000)
    assert sel["accurate_iterations"] == [1000]
    assert sel["verdict"] == "PASS" and sel["chosen"] == (1000, 8) and sel["fastest"] == (500, 8)
    acc_bad = [row(1000, 0, 1.66671), row(1000, 8, 1.66671)]
    assert fs.select_candidate(acc_bad, spd, 100_000)["verdict"] == "FAIL"
    # a failed speed point (None) is never chosen
    sel = fs.select_candidate(acc, [{"iterations": 1000, "check_every": 8, "game_steps_per_s": None}], 100_000)
    assert sel["verdict"] == "FAIL" and sel["fastest"] is None


def test_accuracy_rows_use_t2_measures():
    """The fifth gate is evaluate()'s first-phase |dv| (D6); the gate names are the [filter_speed_gates] keys."""
    fs = _load("filter_speed")
    gates = tomllib.loads((ROOT / "configs/s2.toml").read_text())["filter_speed_gates"]
    ev = {"max_abs_dv_mps": 1.0, "constraint_residual_max": 2.0, "emergency_agreement_min": 0.9995,
          "max_dv_subset_no_gs": 0.03}
    rows = fs.accuracy_verdicts(gates, ev, {"cross_team_corrections": 0})
    by = {r[0]: r for r in rows}
    assert list(by) == ["max_abs_dv_mps", "constraint_residual_max", "emergency_agreement_min",
                        "cross_team_corrections", "max_abs_dv_first_phase_mps"]
    assert by["max_abs_dv_first_phase_mps"][1] == 0.03 and by["max_abs_dv_first_phase_mps"][3] is False
    assert all(by[n][3] for n in list(by)[:4])
    with pytest.raises(KeyError):
        fs.accuracy_verdicts({k: v for k, v in gates.items() if k != "max_abs_dv_first_phase_mps"}, ev,
                             {"cross_team_corrections": 0})
