"""S2b Task 7: step tests (physics drone vs tier 1 vs the real flight log) and the throughput rows.

CPU only, made-up numbers, committed neutral game values (no local file). Nothing here starts Isaac Sim: the scripts'
Isaac paths are exercised by the runs of record, not by this file.
"""
import json
import math
import pathlib
import sys

import numpy as np
import pytest
import torch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
sys.path.insert(0, str(ROOT / "scripts"))
import physics_step_tests as pst  # noqa: E402
import physics_throughput as ptp  # noqa: E402

from svg_training.core.game_config import load_s2b_gates  # noqa: E402

GATES = load_s2b_gates()["step_gates"]


# ------------------------------------------------------------------------------------------- step_metrics
def test_step_metrics_identical_traces():
    t = np.arange(0, 8, 0.01)
    a = np.clip((t - 1.0) / 0.3, 0, 1) * 0.5 - np.clip((t - 5.0) / 0.3, 0, 1) * 0.5
    r = pst.step_metrics(t, a, a.copy(), [1.0, 5.0])
    assert r["rms_mps"] == 0.0
    assert r["t63_gap_s"] == [0.0, 0.0]
    assert r["peak_a_mps"] == pytest.approx(0.5) and r["peak_b_mps"] == pytest.approx(0.5)


def test_step_metrics_known_delay():
    t = np.arange(0, 8, 0.01)
    a = np.clip((t - 1.0) / 0.3, 0, 1) * 0.5
    b = np.clip((t - 1.1) / 0.3, 0, 1) * 0.5
    assert pst.step_metrics(t, a, b, [1.0])["t63_gap_s"][0] == pytest.approx(0.10, abs=0.011)


def test_step_metrics_shared_levels_and_reverse():
    """One level pair per change for both traces (here the command's): +0.5 -> -0.5 at the reverse."""
    t = np.arange(0, 7, 0.01)
    a = np.clip((t - 0.5) / 0.2, 0, 1) * 0.5 - np.clip((t - 3.5) / 0.2, 0, 1) * 1.0
    b = np.clip((t - 0.6) / 0.2, 0, 1) * 0.5 - np.clip((t - 3.7) / 0.2, 0, 1) * 1.0
    r = pst.step_metrics(t, a, b, [0.5, 3.5], levels_mps=[(0.0, 0.5), (0.5, -0.5)])
    assert r["t63_gap_s"][0] == pytest.approx(0.10, abs=0.011)
    assert r["t63_gap_s"][1] == pytest.approx(0.20, abs=0.011)
    # a trace that never gets there inside its segment gives NaN, never a number from the next segment
    flat = np.zeros_like(t)
    r2 = pst.step_metrics(t, flat, b, [0.5, 3.5], levels_mps=[(0.0, 0.5), (0.5, -0.5)])
    assert math.isnan(r2["t63_a_s"][0]) and math.isnan(r2["t63_gap_s"][0])


# ------------------------------------------------------------------------------------------- verdict
def _passing() -> dict:
    return {"measured": {"hover_drift_max_m": 0.01, "hover_tilt_std_max_deg": 0.1, "peak_tilt_max_deg": 10.0,
                         "upsets_max": 0, "real_min_windows": 6, "real_vel_rms_max_mps": 0.05,
                         "real_t63_err_max_s": 0.05, "tier1_vel_rms_max_mps": 0.05, "tier1_t63_gap_max_s": 0.05}}


def test_step_verdict_rules():
    assert pst.step_verdict(_passing(), GATES) == "PASS"
    short = _passing()
    short["measured"]["real_min_windows"] = 5                     # one window short: the real-log gates are not judged
    short["measured"]["real_vel_rms_max_mps"] = 0.5
    assert pst.step_verdict(short, GATES) == "INFO"
    bad = _passing()
    bad["measured"]["tier1_vel_rms_max_mps"] = 0.11
    assert pst.step_verdict(bad, GATES) == "FAIL"
    both = _passing()                                              # FAIL beats INFO
    both["measured"]["real_min_windows"] = 5
    both["measured"]["upsets_max"] = 1
    assert pst.step_verdict(both, GATES) == "FAIL"


@pytest.mark.parametrize("key", ["real_t63_err_max_s", "tier1_t63_gap_max_s", "hover_drift_max_m"])
def test_step_verdict_nan_or_missing_fails(key):
    r = _passing()
    r["measured"][key] = float("nan")
    assert pst.step_verdict(r, GATES) == "FAIL"
    r["measured"][key] = float("inf")
    assert pst.step_verdict(r, GATES) == "FAIL"
    del r["measured"][key]
    assert pst.step_verdict(r, GATES) == "FAIL"


def test_gate_rows_cover_every_gate():
    rows = pst.gate_rows(_passing()["measured"], GATES)
    assert [r["gate"] for r in rows] == list(GATES)
    assert all(r["result"] == "PASS" for r in rows)


# ------------------------------------------------------------------------------------------- windows phase
def test_windows_phase_refuses_wrong_log(tmp_path):
    fake = tmp_path / "log103.ulg"
    fake.write_bytes(b"not the flight log")
    runs = tmp_path / "runs"
    code = pst.main(["--phase", "windows", "--name", "t", "--log", str(fake), "--runs-dir", str(runs)])
    assert code == 2
    assert not runs.exists()                                       # refused before writing anything


def test_windows_phase_refuses_a_missing_log(tmp_path):
    code = pst.main(["--phase", "windows", "--name", "t", "--log", str(tmp_path / "none.ulg"),
                     "--runs-dir", str(tmp_path / "runs")])
    assert code == 2


# ------------------------------------------------------------------------------------------- replay timing
class _StubDrone:
    """Records the setpoints it is given; speed = the held v_ff, so the trace shows the timing exactly."""

    def __init__(self, n, m):
        self.pos_m = torch.zeros(n, m, 3)
        self.vel_mps = torch.zeros(n, m, 3)
        self.max_tilt_rad = torch.zeros(n, m)
        self.upset = torch.zeros(n, m, dtype=torch.bool)
        self.nonfinite_count = torch.zeros((), dtype=torch.long)
        self.calls = []

    def reset(self, mask, pos_m, yaw_rad):
        self.pos_m = pos_m.clone()
        self.vel_mps = torch.zeros_like(pos_m)

    def write_clamped(self, mask, pos_m, vel_mps):
        self.pos_m, self.vel_mps = pos_m.clone(), vel_mps.clone()

    def step_setpoint(self, p_sp, v_ff, a_ff, yaw_sp, yaw_rate):
        self.calls.append(v_ff.clone())
        self.vel_mps = v_ff.clone()


def _window(t0: float, n: int, v_of_t) -> dict:
    t = t0 + np.arange(n) * 0.01
    v = np.stack([v_of_t(t - t0), np.zeros(n), np.zeros(n)], axis=-1)
    return {"t_s": t, "p_sp": np.zeros((n, 3)), "v_ff": v, "a_ff": np.zeros((n, 3)), "yaw_sp": np.zeros(n),
            "yaw_rate": np.zeros(n), "p0": np.array([1.0, 2.0, 1.0]), "v0": np.array([0.1, 0.0, 0.0]),
            "heading0": 0.0}


def test_replay_tick_timing():
    """The setpoint held during tick k is the window's setpoint at t0 + k * 0.05; the state after tick k is stamped
    t0 + (k + 1) * 0.05; sample 0 is the start state at t0. A one-tick slip would move every t63 by 0.05 s."""
    ramp = lambda s: s.copy()                                                       # noqa: E731  v_ff = time since t0
    wins = [_window(10.0, 101, ramp), _window(50.0, 61, ramp)]
    d = _StubDrone(2, 2)
    out = pst.replay(d, wins, "cpu")
    for k, v in enumerate(d.calls[:12]):
        assert float(v[0, 0, 0]) == pytest.approx(0.05 * k, abs=1e-6)            # sampled at tick start
        assert float(v[0, 1, 0]) == 0.0                                            # the far drone holds still
    t_rel, vel = out["t_rel_s"], out["vel_mps"]
    assert t_rel[0] == 0.0 and t_rel[1] == pytest.approx(0.05)
    assert vel[0, 0, 0, 0] == pytest.approx(0.1)                                   # the window's start speed
    assert vel[1, 0, 0, 0] == pytest.approx(0.0)                                   # after tick 0: setpoint of t0
    assert vel[3, 0, 0, 0] == pytest.approx(0.10, abs=1e-6)                        # after tick 2: setpoint of t0+0.10
    # past a short window's end the setpoint holds its last sample
    assert float(d.calls[-1][1, 0, 0]) == pytest.approx(0.60, abs=1e-6)
    assert out["ticks"] == [20, 12]


def test_model_on_grid_and_score_against_identity():
    """A model that flies exactly the logged speed scores 0; shifted by one tick it does not."""
    t = 3.0 + np.arange(301) * 0.01
    v_meas = np.stack([np.clip((t - 4.0) / 0.3, 0, 1) * 0.4, np.zeros_like(t)], axis=-1)
    meas_idx = np.arange(0, 301, 10)
    t_tick = 3.0 + np.arange(61) * 0.05
    v_tick = np.stack([np.clip((t_tick - 4.0) / 0.3, 0, 1) * 0.4, np.zeros_like(t_tick)], axis=-1)
    on_grid = pst.model_on_grid(t, t_tick, v_tick)
    assert pst.window_rms_mps(on_grid, meas_idx, v_meas[meas_idx]) == pytest.approx(0.0, abs=1e-9)
    late = pst.model_on_grid(t, t_tick + 0.05, v_tick)
    assert pst.window_rms_mps(late, meas_idx, v_meas[meas_idx]) > 0.01


# ------------------------------------------------------------------------------------------- throughput rows
def test_throughput_row_fields():
    from svg_training.core.game_config import load_game_cfg
    from svg_training.core.physics_layer import load_game_physics_params
    from svg_training.models.rigid_body import TorchRigidBodyWorld

    cfg = ptp.physics_cfg(load_game_cfg(use_local=False)[0])
    p = load_game_physics_params(cfg)
    world = TorchRigidBodyWorld(2, 3, p.airframe, p.physics_dt_s, "cpu")
    timing = {"warmup_steps": 1, "timed_steps": 2, "min_timed_s": 0.0, "repeats": 1}
    rows = ptp.measure_point(world, cfg, "2v1", 2, "cpu", timing, min_warmup_s=0.0, profile_ticks=2)
    assert len(rows) == 1
    r = rows[0]
    for key in ptp.ROW_FIELDS:
        assert key in r, key
    assert r["status"] == "ok" and r["size"] == "2v1" and r["drones_per_game"] == 3 and r["num_games"] == 2
    assert r["drone_steps_per_s"] == pytest.approx(r["game_steps_per_s"] * 3)
    assert r["nan_count"] == 0 and r["upsets"] == 0
    assert 0.0 < r["share_filter"] < 1.0 and 0.0 < r["share_cascade"] < 1.0 and 0.0 < r["share_physics"] < 1.0
    assert r["share_filter"] + r["share_cascade"] + r["share_physics"] <= 1.0 + 1e-9
    assert 1 <= r["state_writes_per_tick_max"] <= 2                                 # D9
    assert r["filter_iterations"] == cfg.starling.filter_iterations
    assert r["filter_check_every"] == cfg.starling.filter_check_every
    assert r["preset"] == "partner" and r["filter_pairs"] == "every pair"
    assert "SIM-ONLY" in r["yaw_rate_gains"]
    json.dumps(r)                                                                   # one JSON line


def test_throughput_oom_is_a_row():
    from svg_training.core.game_config import load_game_cfg

    cfg = ptp.physics_cfg(load_game_cfg(use_local=False)[0])

    class _OomWorld:
        num_games, drones, dt_s, label = 2, 3, 0.005, "oom"

        def state(self):
            raise torch.OutOfMemoryError("CUDA out of memory (test)")

    rows = ptp.measure_point(_OomWorld(), cfg, "2v1", 2, "cpu", {"warmup_steps": 1, "timed_steps": 1,
                                                                 "min_timed_s": 0.0, "repeats": 2})
    assert len(rows) == 1 and rows[0]["status"] == "oom" and rows[0]["game_steps_per_s"] is None


# ------------------------------------------------------------------------------------------- flight log inside the folder
def test_real_log_relative_path_resolves_inside_svg_training():
    p = pst.resolve_real_log("data/flight_logs/2026-11-13/ulog_drone_2/log103.ulg")
    assert p == pst.ROOT / "data/flight_logs/2026-11-13/ulog_drone_2/log103.ulg"
    assert pst.resolve_real_log("/abs/x.ulg") == pathlib.Path("/abs/x.ulg")


def test_config_real_log_is_inside_svg_training():
    import tomllib
    st = tomllib.loads((pst.ROOT / "configs/s2b.toml").read_text())["step_tests"]
    assert not st["real_log"].startswith(("~", "/")), "flight log must live inside svg_training/ (owner, 17 Nov)"
    assert pst.resolve_real_log(st["real_log"]).is_relative_to(pst.ROOT)
