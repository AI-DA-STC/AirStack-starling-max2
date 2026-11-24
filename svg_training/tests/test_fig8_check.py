"""scripts/fig8_check.py on a synthetic bag (never the owner's real bag): the mission window comes from the commander's
start and hold commands on bag_check's time base; the model's own output replays to zero error; an extra delay is found;
an error injected only while the safety filter lists a drone shows only in that drone's filter-on subset; nothing is fitted
and params/ is not touched."""
import hashlib
import importlib.util
import json
import pathlib
import struct

import numpy as np
import pytest

from _mcap_writer import cdr_header, write_mcap
from svg_training.models import px4_trajectory as m

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "fig8_check.py"
PARAMS = ROOT / "params" / "real_exploratory_v0.toml"
BASE_NS = 1_700_000_000_000_000_000
SP_SCHEMA = ("uint64 timestamp\nfloat32[3] position\nfloat32[3] velocity\nfloat32[3] acceleration\n"
             "float32[3] jerk\nfloat32 yaw\nfloat32 yawspeed\n")
LP_SCHEMA = ("uint64 timestamp\nuint64 timestamp_sample\nbool xy_valid\nfloat32 x\nfloat32 y\nfloat32 z\n"
             "uint8 FOO = 3\nfloat32 vx\nfloat32 vy\nfloat32 vz\n")
STR_SCHEMA = "string data\n"
START_S, HOLD_S, END_S = 4.0, 24.0, 27.0          # start and hold commands, end of the recording (bag_check seconds)
INJECT = (12.0, 16.0)                              # drone_2 listed by the filter here (with drone_1)
D1_ONLY = (18.0, 20.0)                             # only drone_1 listed here
OFFSET_MPS = 0.3                                   # east error injected into drone_2's measured speed in INJECT


def _load():
    spec = importlib.util.spec_from_file_location("fig8_check", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _params(extra_delay_s=0.0):
    import tomllib
    px = {k: v for k, v in tomllib.loads(PARAMS.read_text())["px4"].items() if k != "model_dt_s"}
    p = m.TrajectoryParams.from_dict(px)
    return m.replace(p, delay_s=p.delay_s + extra_delay_s)


def _setpoint(phase=0.0):
    """20 Hz setpoint messages (times never on the 0.01 s grid): hover until START_S, then a slow figure eight
    (peak about 0.6 m/s) that eases in over 2 s, until HOLD_S, then hover at the last point. ENU."""
    t_msg = np.arange(0.0, END_S, 0.0503)
    s = np.clip((t_msg - START_S) / 2.0, 0.0, 1.0) ** 2 * (t_msg < HOLD_S)            # eases in, stops at hold
    tau = np.cumsum(np.r_[0.0, np.diff(t_msg)] * s)                                     # slowed clock
    w = 2 * np.pi / 12.0
    p = np.stack([1.0 * np.sin(w * tau + phase) - np.sin(phase), 0.5 * np.sin(2 * w * tau)], axis=-1)
    v = np.gradient(p, t_msg, axis=0)
    return t_msg, p, v


def _measured(t_msg, p, v, params):
    """The model flown over the whole recording on the 0.01 s grid (setpoint held, acceleration the slope of the held
    speed, as bag_check), sampled every 0.01 s (100 Hz)."""
    grid = np.arange(0.0, END_S - 0.05, 0.01)
    idx = np.clip(np.searchsorted(t_msg, grid, side="right") - 1, 0, len(t_msg) - 1)
    p_h, v_h = p[idx], v[idx]
    a_h = np.gradient(v_h, grid, axis=0)
    vel, pos = m.simulate(p_h, v_h, a_h, 0.01, params, p0=p[0], v0=np.zeros(2))
    return grid, pos, vel


def _string(text):
    raw = text.encode() + b"\0"
    return cdr_header() + struct.pack("<I", len(raw)) + raw


def _cbf_at(t):
    if INJECT[0] <= t < INJECT[1]:
        return "drone_1,drone_2"
    if D1_ONLY[0] <= t < D1_ONLY[1]:
        return "drone_1"
    return ""


def _build_bag(path, params, inject=True, early_status_s=-0.4):
    schemas = {1: ("px4_msgs/msg/TrajectorySetpoint", SP_SCHEMA), 2: ("px4_msgs/msg/VehicleLocalPosition", LP_SCHEMA),
               3: ("std_msgs/msg/String", STR_SCHEMA)}
    channels, msgs = {1: (3, "/svg/commander_status"), 2: (3, "/svg/cbf_active")}, []
    ns = lambda t: BASE_NS + int(round(t * 1e9))                                        # noqa: E731
    # commander status at 5 Hz from before the drones' first message (the 24 Nov bag's zero trap)
    seq_name = [(0.0, 1, "takeoff"), (START_S, 2, "start"), (HOLD_S, 3, "hold")]
    for t in np.arange(early_status_s, END_S, 0.2):
        seq, name = [(q, n) for t0, q, n in seq_name if t >= t0 - 1e-9][-1] if t >= 0 else (None, None)
        lc = {"seq": seq, "name": name} if name else None
        msgs.append((1, ns(t), _string(json.dumps({"mission_active": bool(START_S <= t < HOLD_S), "last_command": lc}))))
    for t in np.round(np.arange(0.0, END_S, 0.05), 3):            # a message at each INJECT edge
        msgs.append((2, ns(t), _string(_cbf_at(t))))
    cid = 2
    for k_d, d in enumerate(("drone_1", "drone_2")):
        t_msg, p, v = _setpoint(phase=0.5 * k_d)
        t_m, pos, vel = _measured(t_msg, p, v, params)
        if inject and d == "drone_2":
            vel = vel.copy()
            vel[(t_m >= INJECT[0]) & (t_m < INJECT[1]), 0] += OFFSET_MPS
        channels[cid + 1] = (1, f"/{d}/fmu/in/trajectory_setpoint")
        channels[cid + 2] = (2, f"/{d}/fmu/out/vehicle_local_position")
        for k, t in enumerate(t_msg):
            body = (struct.pack("<Q", k) + struct.pack("<3f", p[k][1], p[k][0], -1.5)           # ENU -> NED
                    + struct.pack("<3f", v[k][1], v[k][0], 0.0) + struct.pack("<3f", 0, 0, 0)
                    + struct.pack("<3f", 0, 0, 0) + struct.pack("<2f", 0, 0))
            msgs.append((cid + 1, ns(t), cdr_header() + body))
        for k, t in enumerate(t_m):
            body = (struct.pack("<QQ", k, k) + struct.pack("<?", True) + b"\0\0\0"
                    + struct.pack("<3f", pos[k][1], pos[k][0], -1.5) + struct.pack("<3f", vel[k][1], vel[k][0], 0.0))
            msgs.append((cid + 2, ns(t), cdr_header() + body))
        cid += 2
    msgs.sort(key=lambda r: r[1])
    bag = path / "bag"
    bag.mkdir()
    write_mcap(bag / "b_0.mcap", schemas, channels, msgs, per_chunk=500)
    return bag


def _run(tmp_path, bag, extra=()):
    out = tmp_path / "evidence"
    code = _load().main(["--bag", str(bag), "--params", str(PARAMS), "--out", str(out), *extra])
    assert code == 0
    assert (out / "fig8_heldout.png").exists()
    return json.loads((out / "metrics.json").read_text())


def test_fixture_is_small(tmp_path):
    bag = _build_bag(tmp_path, _params())
    assert (bag / "b_0.mcap").stat().st_size < 1_000_000


def test_window_from_commands_on_bag_check_time_base(tmp_path):
    # the status topic starts 0.4 s before the drones' topics; bag_check zeroes on the drones' topics, so the start
    # and hold commands must land at START_S and HOLD_S (to one status period), not 0.4 s later
    res = _run(tmp_path, _build_bag(tmp_path, _params()))
    lo, hi = res["window_s"]
    assert abs(lo - START_S) <= 0.21 and abs(hi - HOLD_S) <= 0.21
    assert res["window_source"] == "commands start -> hold"


def test_window_override(tmp_path):
    res = _run(tmp_path, _build_bag(tmp_path, _params()), extra=("--window-s", "6.0", "22.0"))
    assert res["window_s"] == [6.0, 22.0] and res["window_source"] == "--window-s"
    d2 = res["drones"]["drone_2"]["primary"]["subsets"]["all"]
    assert d2["n_samples"] == pytest.approx(1600, abs=3)


def test_self_replay_is_near_zero(tmp_path):
    res = _run(tmp_path, _build_bag(tmp_path, _params(), inject=False))
    for d in ("drone_1", "drone_2"):
        a = res["drones"][d]["primary"]["subsets"]["all"]
        assert a["model"]["rms_both_mps"] < 2e-3
        assert a["model"]["rms_x_mps"] < 2e-3 and a["model"]["rms_y_mps"] < 2e-3
        assert abs(a["best_shift_s"]) <= 0.01
        assert a["sp"]["rms_both_mps"] > 0.02                   # the lagging drone is not the setpoint itself


def test_extra_delay_is_found(tmp_path):
    res = _run(tmp_path, _build_bag(tmp_path, _params(extra_delay_s=0.20), inject=False))
    a = res["drones"]["drone_2"]["primary"]["subsets"]["all"]
    assert abs(a["best_shift_s"] - 0.20) <= 0.02
    assert a["rms_after_shift_mps"] < 0.5 * a["model"]["rms_both_mps"]


def test_filter_split_is_per_drone(tmp_path):
    res = _run(tmp_path, _build_bag(tmp_path, _params(), inject=True))
    d2 = res["drones"]["drone_2"]["primary"]["subsets"]
    d1 = res["drones"]["drone_1"]["primary"]["subsets"]
    # drone_2 is listed only in INJECT (4 s); the D1_ONLY span is filter-off for drone_2
    assert d2["filter_on"]["n_samples"] == pytest.approx(400, abs=6)
    assert d1["filter_on"]["n_samples"] == pytest.approx(600, abs=8)
    assert d2["filter_on"]["model"]["rms_x_mps"] == pytest.approx(OFFSET_MPS, abs=0.01)
    assert d2["filter_on"]["model"]["rms_y_mps"] < 2e-3
    assert d2["filter_off"]["model"]["rms_both_mps"] < 2e-3
    assert d1["filter_on"]["model"]["rms_both_mps"] < 2e-3
    assert res["drones"]["drone_2"]["filter_runs"]["count"] == 1


def test_reading_words_and_fit_range(tmp_path):
    res = _run(tmp_path, _build_bag(tmp_path, _params(), inject=True))
    r = res["drones"]["drone_2"]["reading"]
    assert r["filter_on.model.rms_x_mps"]["word"] == "outside the 12 Nov check's range (above)"     # 0.3 v 0.029-0.120
    assert r["filter_on.model.rms_x_mps"]["range_12nov"] == [0.029, 0.120]
    assert r["filter_off.model.rms_both_mps"]["word"] == "outside the 12 Nov check's range (below)"
    mod = _load()
    assert mod.reading_word(0.05, (0.029, 0.120)) == "inside the 12 Nov check's range"
    assert mod.reading_word(0.120, (0.029, 0.120)) == "inside the 12 Nov check's range"
    sp = res["drones"]["drone_2"]["speeds"]
    assert sp["fit_range_mps"] == 0.5 and sp["measured_max_mps"] > 0.5 and sp["above_fit_range"]
    assert 0.3 < sp["model_max_mps"] <= sp["setpoint_max_mps"] + 0.05 and sp["model_median_mps"] > 0


def test_variants_present(tmp_path):
    res = _run(tmp_path, _build_bag(tmp_path, _params(), inject=False))
    v = res["drones"]["drone_1"]["variants"]
    assert set(v) == {"accel_logged", "setpoint_linear", "restarted_5s"}
    for k in ("accel_logged", "setpoint_linear"):                 # one-window variants carry the model's limits too
        assert 0.0 <= v[k]["model_limits"]["share_on_acc_limit"] <= 1.0
        assert v[k]["model_speed"]["median_mps"] > 0.0 and v[k]["model_speed"]["max_mps"] > 0.3
    assert v["restarted_5s"]["subsets"]["all"]["model"]["rms_both_mps"] < 5e-3
    # the restarted windows carry an already-delayed setpoint for the model; their baselines must still use the
    # setpoint as sent (same scored span as the primary window, so the same baseline to rounding)
    prim = res["drones"]["drone_1"]["primary"]["subsets"]["all"]
    for k in ("sp", "sp_delayed"):
        assert v["restarted_5s"]["subsets"]["all"][k]["rms_both_mps"] == pytest.approx(prim[k]["rms_both_mps"], rel=0.02)


def test_no_start_command_is_an_error(tmp_path):
    bag = _build_bag(tmp_path, _params())
    out = tmp_path / "ev"
    code = _load().main(["--bag", str(bag), "--params", str(PARAMS), "--out", str(out), "--start-command", "nope"])
    assert code == 1


def test_never_fits_and_leaves_params_alone(tmp_path):
    src = SCRIPT.read_text()
    assert "fit(" not in src and "least_squares" not in src
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT / "params").glob("*")}
    _run(tmp_path, _build_bag(tmp_path, _params()))
    after = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT / "params").glob("*")}
    assert before == after
