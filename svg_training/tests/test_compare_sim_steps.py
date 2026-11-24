"""STE L1.5: tier 2 against the AirStack simulator's velocity steps (scripts/compare_sim_steps.py). CPU only.

The fixture tests/data/l15_steps_fixture.npz is cut from the L1.4 session (bag + PX4 log of
runs/2026-11-24_ste_l14_steps_r3, three steps: 1 = +x 0.5, 17 = +z 2.0, 18 = -z 2.0) by
``compare_sim_steps.py fixture``. Tests that need the full session skip when it is absent (runs/ is not in git).
"""
from __future__ import annotations

import dataclasses
import math
import re
import sys
import tomllib
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "source"))

import compare_sim_steps as cs  # noqa: E402

SIM_PARAMS = ROOT / "params" / "airstack_sim_physics_v0.toml"
FIXTURE = ROOT / "tests" / "data" / "l15_steps_fixture.npz"
AIRFRAME = Path.home() / "AirStack-starling-max2/AirStack/simulation/isaac-sim/px4/airframes/10090_pegasus_starling2max"
L14_RUN = ROOT / "runs" / "2026-11-24_ste_l14_steps_r3"
for _cand in (L14_RUN, Path.home() / "AirStack-starling-max2-dev/svg_training/runs/2026-11-24_ste_l14_steps_r3"):
    if (_cand / "steps_flown.json").is_file():
        L14_RUN = _cand
        break

# Raw CDR bytes of two messages of the L1.4 bag (log time in the name), copied verbatim.
TELEOP_1795492211210182903 = bytes.fromhex(
    "000100007309056b931b860c040000006d617000000000000000e03f0000000000000000000000000000000000000000000000000000"
    "0000000000000000000000000000")
SETPOINT_1795492207686845119 = bytes.fromhex(
    "000100000000000000000000010000000001c705000000000000000000000000000000000000000000000000f7e86548cb8065bf8da3"
    "b062d63d5bbf50615b81d7ffdf3f0000000000000000000000000000000000000000000000000000000000000000")


# =========================================================================================== decoding and frames
def test_decode_twist_stamped_from_bag_bytes():
    stamp, lin, ang = cs.decode_twist_stamped(TELEOP_1795492211210182903)
    assert stamp == pytest.approx(1795492211.2101, abs=1e-3)
    assert lin == pytest.approx((0.5, 0.0, 0.0))
    assert ang == pytest.approx((0.0, 0.0, 0.0))


def test_decode_position_target_from_bag_bytes():
    m = cs.decode_position_target(SETPOINT_1795492207686845119)
    assert m["coordinate_frame"] == 1 and m["type_mask"] == 1479
    assert cs.is_velocity_only(m["type_mask"])
    assert m["position"] == pytest.approx((0.0, 0.0, 0.0))
    assert m["velocity"][2] == pytest.approx(0.5, abs=1e-4)          # the climb to the hover point: ENU z up
    assert abs(m["velocity"][0]) < 0.01 and abs(m["velocity"][1]) < 0.01
    assert not cs.is_velocity_only(1479 & ~0x7)                       # position used: not the speed-only route


def test_ned_to_enu_vectors_and_heading():
    assert cs.ned_to_enu(np.array([[1.0, 2.0, 3.0]])) == pytest.approx(np.array([[2.0, 1.0, -3.0]]))
    assert cs.heading_ned_to_enu(np.array([0.0]))[0] == pytest.approx(math.pi / 2)        # north = ENU +y
    assert cs.heading_ned_to_enu(np.array([math.pi / 2]))[0] == pytest.approx(0.0, abs=1e-12)   # east = ENU +x


# =========================================================================================== metrics
def _fopdt(t, dead_s, tau_s, level=1.0):
    return np.where(t < dead_s, 0.0, level * (1.0 - np.exp(-(t - dead_s) / tau_s)))


def test_metrics_recover_dead_time_rise_and_t63_of_a_first_order_response():
    t = np.arange(-2.0, 8.0, 0.01)
    sp = np.where(t >= 0.0, 1.0, 0.0)
    v = _fopdt(t, 0.2, 0.3)
    m = cs.response_metrics(t, v, sp, hold_end_s=7.0)
    assert m["delay_s"] == pytest.approx(0.2 + 0.3 * math.log(1 / 0.9), abs=0.01)
    assert m["rise_s"] == pytest.approx(0.3 * math.log(9.0), abs=0.01)
    assert m["rise_own_s"] == pytest.approx(0.3 * math.log(9.0), abs=0.01)     # its own extreme ~ the level here
    assert m["t63_s"] == pytest.approx(0.5, abs=0.01)
    assert m["overshoot_pct"] == pytest.approx(0.0, abs=0.5)
    assert m["ss_error_mps"] == pytest.approx(0.0, abs=1e-3)
    assert 0.2 <= m["lag_s"] <= 0.55


def test_metrics_of_the_input_itself_and_an_overshoot():
    t = np.arange(-2.0, 8.0, 0.01)
    sp = np.where(t >= 0.0, 1.0, 0.0)
    m = cs.response_metrics(t, sp, sp, hold_end_s=7.0)
    assert m["delay_s"] == pytest.approx(0.0, abs=1e-9) and m["ss_error_mps"] == pytest.approx(0.0)
    assert m["lag_s"] == pytest.approx(0.0, abs=1e-9)
    over = np.where(t < 0, 0.0, 1.0 + 0.2 * np.exp(-((t - 1.0) ** 2) / 0.05))
    assert cs.response_metrics(t, over, sp, hold_end_s=7.0)["overshoot_pct"] == pytest.approx(20.0, abs=0.5)
    slow = 0.5 * sp                                                     # never reaches 90 %: rise NaN, ss error -0.5
    ms = cs.response_metrics(t, slow, sp, hold_end_s=7.0)
    assert math.isnan(ms["rise_s"]) and ms["ss_error_mps"] == pytest.approx(-0.5)
    assert ms["rise_own_s"] == pytest.approx(0.0, abs=1e-9)                   # a step to its own level: at once


def test_metrics_use_the_input_peak_as_the_shared_level():
    """The setpoint PX4 got is not a step (it peaks, then sags): both traces are scored on the input's own levels."""
    t = np.arange(-2.0, 8.0, 0.01)
    sp = np.where(t < 0, 0.0, np.where(t < 1.0, 0.56, 0.2))
    m = cs.response_metrics(t, sp, sp, hold_end_s=7.0)
    assert m["level0_mps"] == pytest.approx(0.0) and m["level_peak_mps"] == pytest.approx(0.56)
    assert m["overshoot_pct"] == pytest.approx(0.0, abs=1e-9)


# =========================================================================================== alignment
def test_align_step_recovers_a_known_clock_map():
    """Bag setpoints at 20 Hz wall; PX4 samples its current setpoint at 10 Hz on its own clock, t_v = a + s (t_w - t_on)."""
    a_true, s_true, t_on = 100.0, 2.47, 5000.0
    t_w = t_on + np.arange(-3.0, 6.0, 0.05)
    lvl = np.where(t_w < t_on, 0.0, np.where(t_w < t_on + 3.0, np.minimum(0.5, 0.1 * np.round((t_w - t_on) / 0.05)), 0.0))
    v_bag = np.stack([lvl, 0 * lvl, 0 * lvl], 1)
    t_px4 = np.arange(a_true - 6.0, a_true + 3.0 * s_true + 6.0, 0.1) + 0.013
    t_w_of = t_on + (t_px4 - a_true) / s_true
    v_px4 = v_bag[np.clip(np.searchsorted(t_w, t_w_of, side="right") - 1, 0, len(t_w) - 1)]
    al = cs.align_step(t_w, v_bag, t_px4, v_px4, t_on, hold_wall_s=3.0, guess_offset_s=a_true + 1.3, guess_scale=2.5)
    assert al["offset_s"] == pytest.approx(a_true, abs=0.03)
    # a 10 Hz log pins the release edge (3 s wall later) to about +-0.1 s: the scale is known to about +-0.02 only,
    # and the reported spread says so (the onset, which the metrics use, is pinned much tighter)
    assert al["scale_spread"] < 0.06
    assert abs(al["scale"] - s_true) <= al["scale_spread"] / 2 + 0.005
    assert al["onset_spread_s"] <= 0.05
    assert al["residual_rms_mps"] < 0.02


# =========================================================================================== reading words
def test_reading_words_with_the_floor():
    assert cs.reading(0.30, [0.25, 0.35], floor=0.05) == "within"
    assert cs.reading(0.39, [0.25, 0.35], floor=0.05) == "within"          # inside the widened range
    assert cs.reading(0.41, [0.25, 0.35], floor=0.05) == "outside (above)"
    assert cs.reading(0.10, [0.25, 0.35], floor=0.05) == "outside (below)"
    assert cs.reading(math.nan, [0.25, 0.35], floor=0.05) == "not reached"
    assert cs.reading(math.nan, [math.nan, math.nan], floor=0.05) == "within"       # neither reaches it
    assert cs.reading(0.3, [math.nan, math.nan], floor=0.05) == "outside (AirStack not reached)"
    assert set(cs.FLOORS) == set(cs.METRICS)


def test_arm_change_words():
    assert cs.arm_change(0.10, 0.20, floor=0.05) == "closer"
    assert cs.arm_change(0.20, 0.10, floor=0.05) == "further"
    assert cs.arm_change(0.12, 0.10, floor=0.05) == "no change (within the floor)"


# =========================================================================================== the SIM-ONLY parameter file
def test_sim_only_file_is_refused_by_the_trainers_loader_and_read_by_the_script(tmp_path):
    from svg_training.models.physics_params import load_physics_params

    text = SIM_PARAMS.read_text()
    assert text.startswith("# SIM-ONLY")
    assert "SIM-ONLY" in tomllib.loads(text)["sim_only"]["label"]
    with pytest.raises(ValueError, match="unknown section"):
        load_physics_params(SIM_PARAMS)
    p, prov = cs.load_sim_only_params(SIM_PARAMS, tmp_path)
    assert p.motor_lag is False
    assert (p.drag_x_n_per_mps, p.drag_y_n_per_mps, p.drag_z_n_per_mps) == (0.5, 0.3, 0.0)
    assert p.gains.mc_rollrate_p == 0.032 and p.gains.mpc_z_vel_max_dn == 4.0 and p.gains.mc_yaw_cutoff == 15.0
    assert prov["sha256"] and "SIM-ONLY" in prov["label"]


def test_no_config_or_source_file_names_the_sim_only_file():
    """R21: the values stay a comparison file; no game file, trainer or model may load them."""
    hits = []
    for top in ("configs", "source"):
        for f in (ROOT / top).rglob("*"):
            if f.is_file() and f.suffix in (".py", ".toml") and "airstack_sim_physics" in f.read_text(errors="replace"):
                hits.append(str(f.relative_to(ROOT)))
    assert hits == []


@pytest.mark.skipif(not AIRFRAME.is_file(), reason="the AirStack live clone's sim airframe is not on this machine")
def test_every_cited_airframe_line_says_what_the_file_says():
    lines = AIRFRAME.read_text().splitlines()
    gains = tomllib.loads(SIM_PARAMS.read_text())["gains"]
    cited = 0
    for row in SIM_PARAMS.read_text().splitlines():
        m = re.match(r"^(\w+)\s*=\s*\S+\s+# A:(\d+) (\w+)", row)
        if not m:
            continue
        key, line_no, px4 = m.group(1), int(m.group(2)), m.group(3)
        src = lines[line_no - 1].split()
        assert src[:3] == ["param", "set-default", px4], (row, lines[line_no - 1])
        assert float(src[3]) == pytest.approx(float(gains[key]), rel=1e-6), row
        cited += 1
    assert cited >= 35


@pytest.mark.skipif(not (L14_RUN / "drone_1_sysid2_03_49_17.ulg").is_file(), reason="the L1.4 PX4 log is not here")
def test_every_gain_equals_the_simulators_ulog_parameter():
    from fit_real_px4 import read_ulog_full

    _, params, changes = read_ulog_full(L14_RUN / "drone_1_sysid2_03_49_17.ulg", [])
    assert changes == []
    gains = tomllib.loads(SIM_PARAMS.read_text())["gains"]
    for key, val in gains.items():
        name = "MC_YAW_TQ_CUTOFF" if key == "mc_yaw_cutoff" else key.upper()
        assert float(np.float32(params[name])) == pytest.approx(float(np.float32(val)), rel=1e-6), key


# =========================================================================================== the arms
def test_arms_differ_only_by_their_named_keys(tmp_path):
    base, _ = cs.load_sim_only_params(SIM_PARAMS, tmp_path)
    arms = cs.arm_params(base)
    assert list(arms) == list(cs.ARMS)
    off = arms["off"]
    assert (off.gains.mpc_xy_p, off.gains.mpc_z_p) == (0.0, 0.0)            # speed-only route (module docstring)
    assert dataclasses.replace(off.gains, mpc_xy_p=base.gains.mpc_xy_p, mpc_z_p=base.gains.mpc_z_p) == base.gains
    for name, keys in (("delay", {"state_delay_s"}), ("error", set(cs.ERROR_KEYS))):
        diff = {f.name for f in dataclasses.fields(off) if getattr(off, f.name) != getattr(arms[name], f.name)}
        assert diff == keys, name
    assert arms["delay"].state_delay_s == 0.05
    nominal = tomllib.loads((ROOT / "params/starling_physics_v1_nominal.toml").read_text())["model"]
    for k in cs.ERROR_KEYS:
        assert getattr(arms["error"], k) == nominal[k]


# =========================================================================================== tier 2 on the CPU
def _torch_world(p, n):
    from svg_training.models.rigid_body import TorchRigidBodyWorld
    return TorchRigidBodyWorld(n, 1, p.airframe, p.physics_dt_s, "cpu")


def test_zero_position_gains_fly_a_constant_climb_at_the_sent_speed(tmp_path):
    """The speed-only route: PX4 (position NaN) flies v_ff. Tier 2 holds a position setpoint over the tick, which pulls
    back about K_p v dt / 2; with the position gains at 0 the climb settles at the sent speed."""
    base, _ = cs.load_sim_only_params(SIM_PARAMS, tmp_path)
    ticks = 100
    sp = np.zeros((ticks, 1, 3))
    sp[:, 0, 2] = 1.5
    inputs = {"sp_mps": sp, "pos0_m": np.array([[0.0, 0.0, 3.0]]), "vel0_mps": np.zeros((1, 3)),
              "yaw0_rad": np.zeros(1)}
    vel = {}
    for name, p in (("route", cs.arm_params(base)["off"]), ("held", base)):
        out = cs.fly(_torch_world(p, 1), p, inputs, "cpu", seed=0)
        vel[name] = out["vel_mps"][-20:, 0, 2].mean()
    assert vel["route"] == pytest.approx(1.5, abs=0.03)
    assert vel["held"] < 1.4                                             # the held position setpoint's pull


def test_fly_arms_batch_shapes_determinism_and_noise(tmp_path):
    base, _ = cs.load_sim_only_params(SIM_PARAMS, tmp_path)
    arms = cs.arm_params(base)
    steps, reps, ticks = 2, 2, 40
    sp = np.zeros((ticks, steps * reps, 3))
    sp[10:, :, 0] = 0.5
    inputs = {"sp_mps": sp, "pos0_m": np.tile([0.0, 0.0, 2.0], (steps * reps, 1)),
              "vel0_mps": np.zeros((steps * reps, 3)), "yaw0_rad": np.zeros(steps * reps)}
    out = cs.fly_arms(lambda p: _torch_world(p, steps * reps), arms, inputs, "cpu", seed=3)
    assert set(out) == set(cs.ARMS)
    for name in cs.ARMS:
        assert out[name]["vel_mps"].shape == (ticks + 1, steps * reps, 3)
        assert out[name]["upsets"] == 0 and out[name]["nonfinite"] == 0
    off = out["off"]["vel_mps"]
    assert np.array_equal(off[:, 0], off[:, 1])                          # deterministic on the CPU
    assert not np.array_equal(out["error"]["vel_mps"][:, 0], out["error"]["vel_mps"][:, 1])   # noise per game
    assert not np.array_equal(out["delay"]["vel_mps"], off)


# =========================================================================================== the recorded fixture
@pytest.fixture(scope="module")
def fixture_steps():
    if not FIXTURE.is_file():
        pytest.skip("fixture missing")
    return cs.extract_from_streams(cs.load_fixture(FIXTURE))


def test_fixture_is_small():
    assert FIXTURE.stat().st_size < 1_000_000


def test_fixture_steps_parse_with_the_right_signs_and_clock(fixture_steps):
    steps = fixture_steps["steps"]
    assert [s["index"] for s in steps] == [1, 17, 18]
    for s in steps:
        assert 2.2 <= s["clock_scale"] <= 2.9                          # the simulator's PX4 clock against the wall
        assert s["align_residual_rms_mps"] < 0.05
        assert s["setpoint_velocity_only"]
        u = np.asarray(s["cmd_unit"])
        t = s["t_s"]
        hold = (t > 1.5) & (t < s["hold_end_s"])
        assert (s["response_mps"][hold] @ u).mean() > 0.15                # moves along the command (ENU signs)
        assert (s["setpoint_mps"][hold] @ u).mean() > 0.15
    z_up = steps[1]
    assert z_up["axis"] == "z" and z_up["sign"] == 1 and z_up["teleop_level_mps"] == pytest.approx(2.0)
    assert z_up["setpoint_settled_mps"] == pytest.approx(1.5, abs=0.05)    # the commander's sag on the sim clock
    assert z_up["pos0_m"][2] < z_up["pos_end_m"][2]                       # climbs (ENU z up)


def test_fixture_metrics_and_cells(fixture_steps):
    steps = fixture_steps["steps"]
    for s in steps:
        m = s["metrics"]["airstack"]
        assert set(cs.METRICS) <= set(m)
        assert 0.0 < m["delay_s"] < 1.0
    cells = cs.cell_table(steps, {"airstack": [s["metrics"]["airstack"] for s in steps]})
    assert ("z", 2.0) in cells and len(cells[("z", 2.0)]["steps"]) == 2


def test_fixture_end_to_end_on_the_cpu(fixture_steps, tmp_path):
    """extract -> tier 2 (torch world, CPU, 1 replica) -> per-step metrics and reading words; never of record."""
    base, prov = cs.load_sim_only_params(SIM_PARAMS, tmp_path)
    arms = cs.arm_params(base)
    inputs, layout = cs.batch_inputs(fixture_steps["steps"], replicas=1)
    out = cs.fly_arms(lambda p: _torch_world(p, layout["games"]), arms, inputs, "cpu", seed=0)
    res = cs.analyse(fixture_steps, out, layout)
    assert len(res["steps"]) == 3
    for row in res["steps"]:
        assert set(cs.ARMS) <= set(row["tier2"])
    for cell in res["cells"]:
        for arm in cs.ARMS:
            assert set(cell["reading"][arm]) == set(cs.METRICS)
    assert set(res["confounds"]) == {"px4_version", "route", "clock", "estimator_source", "plant"}


@pytest.mark.skipif(not (L14_RUN / "steps_flown.json").is_file(), reason="the L1.4 run folder is not here")
def test_real_session_parses_35_steps_and_skips_step_6():
    ext = cs.extract_from_streams(cs.load_streams(L14_RUN))
    idx = [s["index"] for s in ext["steps"]]
    assert len(idx) == 35 and 6 not in idx
    assert ext["skipped"] == [6]
