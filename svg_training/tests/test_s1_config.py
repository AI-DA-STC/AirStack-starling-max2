import pathlib
import tomllib

ROOT = pathlib.Path(__file__).resolve().parents[1]
CFG = tomllib.loads((ROOT / "configs/s1.toml").read_text())


def test_fit_gates():
    g = CFG["fit_gates"]
    assert g == {"vel_rms_max_mps": 0.10, "t63_err_max_s": 0.10, "delay_range_s": [0.0, 0.40], "min_held_out_steps": 8}


def test_filter_gates():
    g = CFG["filter_gates"]
    assert g == {"max_abs_dv_mps": 0.02, "constraint_residual_max": 2.0e-3, "emergency_agreement_min": 0.99,
                 "cross_team_corrections": 0, "scenes": 2000}


def test_steps_give_enough_held_out_steps():
    s = CFG["steps"]
    assert isinstance(s["hold_s"], float) and all(isinstance(v, float) for v in s["speeds_mps"])
    n = len(s["speeds_mps"]) * len(s["axes"]) * len(s["signs"]) * s["repeats"]
    assert n == 36 and n >= 2 * CFG["fit_gates"]["min_held_out_steps"]


def test_filter_bench():
    b = CFG["filter_bench"]
    assert b["cases"] == ["t1_5v3_open", "t1_5v3_full"] and b["num_games"] == [1024, 4096, 16384]
