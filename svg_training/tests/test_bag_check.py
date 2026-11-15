"""scripts/bag_check.py on a synthetic bag: the model's own output is read back exactly; an extra delay is found;
the script never fits and never writes under params/. Synthetic data only (never the real bag)."""
import importlib.util
import json
import pathlib
import struct

import numpy as np

from _mcap_writer import cdr_header, write_mcap
from svg_training.models import px4_trajectory as m

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "bag_check.py"
PARAMS = ROOT / "params" / "real_exploratory_v0.toml"
BASE_NS = 1_700_000_000_000_000_000
SP_SCHEMA = ("uint64 timestamp\nfloat32[3] position\nfloat32[3] velocity\nfloat32[3] acceleration\n"
             "float32[3] jerk\nfloat32 yaw\nfloat32 yawspeed\n")
LP_SCHEMA = ("uint64 timestamp\nuint64 timestamp_sample\nbool xy_valid\nfloat32 x\nfloat32 y\nfloat32 z\n"
             "uint8 FOO = 3\nfloat32 vx\nfloat32 vy\nfloat32 vz\n")
GATES_TOML = """[bag_check_gates]
drone = "drone_2"
vel_rms_max_mps = 0.10
t63_err_max_s = 0.10
min_legs = 3
accel_ff = "derived"
"""


def _load():
    spec = importlib.util.spec_from_file_location("bag_check", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _params(extra_delay_s=0.0):
    import tomllib
    px = {k: v for k, v in tomllib.loads(PARAMS.read_text())["px4"].items() if k != "model_dt_s"}
    p = m.TrajectoryParams.from_dict(px)
    return m.replace(p, delay_s=p.delay_s + extra_delay_s)


def _setpoint_messages(leg_starts, total_s=None):
    """19 Hz setpoint messages: each leg ramps to 0.5 m/s along (0.8, 0.6) at 5 m/s^2, holds 2 s, ramps back; the
    position setpoint is the integral of the speed. Returns message times (s), p_sp (N, 2), v_ff (N, 2) in ENU."""
    total_s = total_s or leg_starts[-1] + 9.0
    fine_t = np.arange(0.0, total_s, 0.001)
    speed = np.zeros_like(fine_t)
    for a in leg_starts:
        speed += np.clip(5.0 * (fine_t - a), 0, 0.5) - np.clip(5.0 * (fine_t - (a + 2.0)), 0, 0.5)
    u = np.array([0.8, 0.6])
    pos = np.cumsum(speed) * 0.001
    t_msg = np.arange(0.0, total_s - 0.01, 0.0527)                     # ~19 Hz, never on the 0.01 s grid
    p = np.stack([np.interp(t_msg, fine_t, pos)] * 2, axis=-1) * u
    v = np.stack([np.interp(t_msg, fine_t, speed)] * 2, axis=-1) * u
    return t_msg, p, v


def _measured(t_msg, p, v, params):
    """The model flown over the whole flight in one go on the 0.01 s grid, sampled every 0.02 s (50 Hz)."""
    grid = np.arange(0.0, t_msg[-1], 0.01)
    idx = np.clip(np.searchsorted(t_msg, grid, side="right") - 1, 0, len(t_msg) - 1)
    p_h, v_h = p[idx], v[idx]
    a_h = np.gradient(v_h, grid, axis=0)
    vel, pos = m.simulate(p_h, v_h, a_h, 0.01, params, p0=np.zeros(2), v0=np.zeros(2))
    return grid[::2], pos[::2], vel[::2]


def _build_bag(path, params, leg_starts=(3.0, 13.0, 23.0), drones=("drone_1", "drone_2"), z_ned=-1.5):
    t_msg, p, v = _setpoint_messages(leg_starts)
    t_m, pos, vel = _measured(t_msg, p, v, params)
    schemas = {1: ("px4_msgs/msg/TrajectorySetpoint", SP_SCHEMA), 2: ("px4_msgs/msg/VehicleLocalPosition", LP_SCHEMA)}
    channels, msgs, cid = {}, [], 0
    for d in drones:
        cid += 2
        channels[cid - 1] = (1, f"/{d}/fmu/in/trajectory_setpoint")
        channels[cid] = (2, f"/{d}/fmu/out/vehicle_local_position")
        for k, t in enumerate(t_msg):
            ned_p, ned_v = (p[k][1], p[k][0]), (v[k][1], v[k][0])                       # ENU -> NED
            body = (struct.pack("<Q", k) + struct.pack("<3f", ned_p[0], ned_p[1], 0.0)
                    + struct.pack("<3f", ned_v[0], ned_v[1], 0.0) + struct.pack("<3f", 0, 0, 0)
                    + struct.pack("<3f", 0, 0, 0) + struct.pack("<2f", 0, 0))
            msgs.append((cid - 1, BASE_NS + int(round(t * 1e9)), cdr_header() + body))
        for k, t in enumerate(t_m):
            body = (struct.pack("<QQ", k, k) + struct.pack("<?", True) + b"\0\0\0"
                    + struct.pack("<3f", pos[k][1], pos[k][0], z_ned) + struct.pack("<3f", vel[k][1], vel[k][0], 0.0))
            msgs.append((cid, BASE_NS + int(round(t * 1e9)), cdr_header() + body))
    msgs.sort(key=lambda r: r[1])
    bag = path / "bag"
    bag.mkdir()
    write_mcap(bag / "b_0.mcap", schemas, channels, msgs, per_chunk=500)
    return bag


def _run(tmp_path, bag, name="t"):
    gates = tmp_path / "gates.toml"
    gates.write_text(GATES_TOML)
    mod = _load()
    code = mod.main(["--bag", str(bag), "--params", str(PARAMS), "--gates", str(gates), "--name", name,
                     "--runs-dir", str(tmp_path / "runs"), "--fig", str(tmp_path / "fig.png"), "--no-record"])
    assert code == 0
    return json.loads((tmp_path / "runs" / name / "results.json").read_text())


def test_bag_check_reproduces_model_exactly(tmp_path):
    bag = _build_bag(tmp_path, _params())
    res = _run(tmp_path, bag)
    assert len(res["drone_2"]["legs"]) == 3
    assert max(leg["rms_mps"] for leg in res["drone_2"]["legs"]) < 1e-3
    assert res["result"] == "PASS"
    assert abs(res["drone_2"]["best_extra_shift_s"]) <= 0.01
    assert (tmp_path / "fig.png").exists() and (tmp_path / "runs" / "t" / "gates.toml").exists()
    # the setpoint speed itself is a clearly worse description than the model (a lagging drone)
    assert res["drone_2"]["pooled_rms_mps"]["sp"] > 0.05


def test_bag_check_finds_extra_delay(tmp_path):
    bag = _build_bag(tmp_path, _params(extra_delay_s=0.20))
    res = _run(tmp_path, bag)
    assert abs(res["drone_2"]["best_extra_shift_s"] - 0.20) <= 0.02
    assert res["result"] == "FAIL"                                  # 0.2 s late is far beyond the gates


def test_bag_check_never_fits():
    src = SCRIPT.read_text()
    assert "fit(" not in src
    for line in src.splitlines():                       # nothing is written to a path that mentions params
        assert not ("params" in line and ("write_text" in line or "write_bytes" in line or "copyfile(" in line
                                          and "params_used" not in line))


def test_bag_check_too_few_legs_is_info(tmp_path):
    bag = _build_bag(tmp_path, _params(), leg_starts=(3.0,))
    res = _run(tmp_path, bag)
    assert res["drone_2"]["n_legs"] == 1
    assert res["result"] == "INFO"


def test_bag_check_ground_legs_are_not_scored(tmp_path):
    bag = _build_bag(tmp_path, _params(), z_ned=0.0)            # the drone never leaves the floor
    res = _run(tmp_path, bag)
    assert res["drone_2"]["n_legs"] == 0 and res["result"] == "INFO"
    assert res["all_legs_sensitivity"]["drone_2"]["n_legs"] == 3
