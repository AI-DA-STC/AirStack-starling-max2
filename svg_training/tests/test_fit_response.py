"""Task 4 (S1): scripts/fit_response.py on a small synthetic session (known parameters, body-frame odometry).

No ROS, no GPU. The CLI runs in-process (main(argv)) on CSVs written to tmp_path; the time scale is injected with
--time-scale (the ulog path is tested on its own with a hand-built ULog file).
"""
import importlib.util
import json
import math
import pathlib
import re
import struct
import subprocess
import tomllib

import numpy as np
import pytest
from _proc import child_env, child_python

from svg_training.models.response import ResponseParams, body_to_world, simulate

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "fit_response.py"
GATES = ROOT / "configs" / "s1.toml"
NAME = "2026-11-15_s1_fit_v0"
SCALE = 1.5
YAW_DEG = 40.0
TRUE = ResponseParams(delay_s=0.12, tau_xy_s=0.5, tau_z_s=0.4, acc_max_xy_mps2=3.0, acc_max_z_mps2=2.5,
                      speed_cap_mps=2.0, family="lag1")
# 16 steps (axis, signed speed): even (train) and odd (held out) both cover x, y, z, both signs, 1 and 2 m/s.
PLAN16 = [(0, 2.0), (0, -1.0), (1, -2.0), (1, 1.0), (2, 1.0), (2, -2.0), (0, -1.0), (0, 2.0),
          (1, 1.0), (1, -2.0), (2, -2.0), (2, 1.0), (1, -1.0), (0, 1.0), (2, 2.0), (1, 2.0)]
PLAN6 = PLAN16[:6]


def _load():
    spec = importlib.util.spec_from_file_location("fit_response", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


fr = _load()


# ---------------------------------------------------------------- synthetic session

def _write_session(d: pathlib.Path, plan, scale=SCALE, noise_mps=0.01, seed=0, rest_wall=1.5, hold_wall=2.0):
    """teleop_command.csv (20 Hz wall), odometry.csv (50 Hz wall, BODY-frame velocity, yaw YAW_DEG), manifest.json."""
    d.mkdir(parents=True, exist_ok=True)
    n_cmd = int(round((len(plan) * (rest_wall + hold_wall) + rest_wall) * 20))
    t0 = 1.0e9
    t_cmd = np.arange(n_cmd) / 20.0
    cmd = np.zeros((n_cmd, 3))
    for i, (axis, speed) in enumerate(plan):
        s = rest_wall + i * (rest_wall + hold_wall)
        cmd[(t_cmd >= s - 1e-9) & (t_cmd < s + hold_wall - 1e-9), axis] = speed
    dt_f = 0.001
    t_f = np.arange(int(t_cmd[-1] * scale / dt_f)) * dt_f
    idx = np.searchsorted(t_cmd * scale, t_f + 1e-12, side="right") - 1
    v_f = simulate(cmd[idx], dt_f, TRUE)
    p_f = np.array([0.0, 0.0, 1.5]) + np.concatenate([np.zeros((1, 3)), np.cumsum(v_f[:-1] * dt_f, axis=0)])
    t_od = np.arange(0.0, t_cmd[-1] - 0.05, 1 / 50.0)
    v_w = np.stack([np.interp(t_od * scale, t_f, v_f[:, a]) for a in range(3)], axis=1)
    pos = np.stack([np.interp(t_od * scale, t_f, p_f[:, a]) for a in range(3)], axis=1)
    h = math.radians(YAW_DEG) / 2
    q = np.tile([math.cos(h), 0.0, 0.0, math.sin(h)], (len(t_od), 1))
    q_conj = q * np.array([1.0, -1.0, -1.0, -1.0])
    v_b = body_to_world(v_w, q_conj) + np.random.default_rng(seed).normal(0.0, noise_mps, v_w.shape)
    with open(d / "teleop_command.csv", "w") as f:
        f.write("t_wall_s,vx,vy,vz,yaw_rate\n")
        for t, c in zip(t_cmd, cmd):
            f.write(f"{t0 + t:.6f},{c[0]!r},{c[1]!r},{c[2]!r},0.0\n")
    with open(d / "odometry.csv", "w") as f:
        f.write("t_wall_s,x,y,z,vx,vy,vz,qw,qx,qy,qz\n")
        for t, p, v, qq in zip(t_od, pos, v_b, q):
            f.write(f"{t0 + t:.6f}," + ",".join(repr(float(x)) for x in (*p, *v, *qq)) + "\n")
    (d / "manifest.json").write_text(json.dumps({"bag": "/synthetic/bag", "drone": "drone_1"}))
    return d


def _steps_json(path: pathlib.Path, plan):
    steps = [{"index": i + 1, "repeat": 1, "axis": "xyz"[a], "sign": 1 if s > 0 else -1, "speed_mps": abs(s)}
             for i, (a, s) in enumerate(plan)]
    path.write_text(json.dumps({"steps": steps}))
    return path


def _root(tmp: pathlib.Path) -> pathlib.Path:
    (tmp / "records").mkdir(parents=True)
    (tmp / "records" / "LEDGER.md").write_text(
        "# Training ledger\n\n| # | Date | Simulator | Run | What | Result | Record |\n|---|---|---|---|---|---|---|\n"
        "| T1 | 2026-11-14T16:55:40 | training simulator | x | S0 | FAIL | records/x_record.md |\n")
    return tmp


def _args(csv_dir, root, *extra, scale=SCALE):
    return ["--csv-dir", str(csv_dir), "--time-scale", str(scale), "--name", NAME, "--gates", str(GATES),
            "--out-root", str(root), "--dt-s", "0.02", *extra]


@pytest.fixture(scope="module")
def passed(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("pass")
    csv = _write_session(tmp / "csv", PLAN16)
    root = _root(tmp / "root")
    sj = _steps_json(tmp / "steps.json", PLAN16)
    rc = fr.main(_args(csv, root, "--steps-json", str(sj), "--family", "best"))
    return rc, root, csv, sj


@pytest.fixture(scope="module")
def failed(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("fail")
    csv = _write_session(tmp / "csv", PLAN6)
    root = _root(tmp / "root")
    rc = fr.main(_args(csv, root, "--family", "lag1"))
    return rc, root


# ---------------------------------------------------------------- outputs and gates

def test_pass_run_writes_every_output(passed):
    rc, root, _, _ = passed
    assert rc == 0
    assert (root / "params" / "airstack_sim_v0.toml").is_file()
    assert (root / "records" / f"{NAME}_record.md").is_file()
    pngs = sorted((root / "docs" / "figures").glob("s1_t2_held_out_step_*.png"))
    assert len(pngs) == 8 and all(p.stat().st_size > 1000 for p in pngs)


def test_params_file_has_units_provenance_and_round_trips(passed):
    _, root, _, _ = passed
    d = tomllib.loads((root / "params" / "airstack_sim_v0.toml").read_text())
    p = ResponseParams.from_dict(d["params"])
    assert p.family in ("lag1", "lag2") and d["fit"]["family"] == p.family
    assert all(k.endswith(("_s", "_mps", "_mps2")) for k in d["params"] if k != "family")
    assert p.delay_s == pytest.approx(TRUE.delay_s, abs=0.03)
    assert p.tau_xy_s == pytest.approx(TRUE.tau_xy_s, rel=0.1)
    ts = d["time_scale"]
    assert ts["value"] == SCALE and "injected" in ts["source"]
    assert ts["derivative_gain"] == pytest.approx(SCALE, rel=0.02)
    f = d["fit"]
    assert f["train_steps"] == 8 and f["held_out_steps"] == 8 and f["verdict"] == "PASS"
    assert len(f["code_sha"]) == 12 and f["date"][-6] in "+-"
    assert d["source"]["bag"] == "/synthetic/bag"


def test_pass_record_and_ledger(passed):
    _, root, _, _ = passed
    text = (root / "records" / f"{NAME}_record.md").read_text()
    assert text.splitlines()[0].startswith("Simulator: AirStack simulator")
    assert "Overall result: **PASS**" in text
    for gate in ("vel_rms_max_mps", "t63_err_max_s", "delay_range_s", "min_held_out_steps"):
        assert any(line.startswith(f"| {gate}: ") and line.rstrip().endswith("| PASS |") for line in text.splitlines())
    assert "body frame" in text and "observed in the AirStack simulator" in text
    _plain_language(text)
    figs = re.findall(r"^!\[Figure (\d+)\]\((\.\./docs/figures/s1_t2_[^)]+\.png)\)$", text, flags=re.M)
    assert len(figs) == 9 and figs[-1][1].endswith("/s1_t2_all_steps.png")
    for _, link in figs:
        assert (root / "records" / link).resolve().is_file()
    captions = re.findall(r"^\*Figure \d+\.\* (.+)$", text, flags=re.M)
    assert len(captions) == 9
    for c in captions:
        assert len(c) <= 400 and 2 <= len(re.findall(r"[.!?](?:\s|$)", c)) <= 4, c
    segments = text[text.index("## Segments"):text.index("## Fit, both")]
    assert segments.count("| held out |") == 8 and segments.count("| train |") == 8
    ledger = (root / "records" / "LEDGER.md").read_text().splitlines()
    assert ledger[-1].startswith("| T2 | ") and f"| {NAME} |" in ledger[-1] and "| PASS |" in ledger[-1]


def _plain_language(text):
    """No unmeasured claim; every term explained once; split and reading generated from the run's own data."""
    assert "better than the placeholder" not in text
    assert "## Terms used here" in text and "**t63**: the time to reach 63 % of the change" in text
    assert text.index("## Terms used here") < text.index("## Fit, both")
    assert "## Reading" in text and "| Measured peak | At release | Lowest after release |" in text
    assert "held-out steps on" in text


def test_too_few_held_out_steps_is_a_fail_with_outputs(failed):
    rc, root = failed
    assert rc == 0
    text = (root / "records" / f"{NAME}_record.md").read_text()
    assert "Overall result: **FAIL**" in text
    _plain_language(text)
    row = next(line for line in text.splitlines() if line.startswith("| min_held_out_steps: "))
    assert "| 3 |" in row and row.rstrip().endswith("| FAIL |")
    d = tomllib.loads((root / "params" / "airstack_sim_v0.toml").read_text())
    assert d["fit"]["verdict"] == "FAIL" and d["fit"]["held_out_steps"] == 3
    assert ResponseParams.from_dict(d["params"]).family == "lag1"
    figs = root / "docs" / "figures"
    assert len(list(figs.glob("s1_t2_held_out_step_*.png"))) == 3
    assert (figs / "s1_t2_all_steps.png").is_file() and text.count("![Figure ") == 4
    assert (root / "records" / "LEDGER.md").read_text().splitlines()[-1].split("|")[6].strip() == "FAIL"


def test_refuses_to_overwrite(passed):
    _, root, csv, sj = passed
    params = root / "params" / "airstack_sim_v0.toml"
    before = (params.read_bytes(), (root / "records" / "LEDGER.md").read_bytes())
    assert fr.main(_args(csv, root, "--steps-json", str(sj))) == 1
    assert before == (params.read_bytes(), (root / "records" / "LEDGER.md").read_bytes())


def test_refuses_to_overwrite_figures_of_the_next_ledger_number(tmp_path):
    csv = _write_session(tmp_path / "csv", PLAN6)
    root = _root(tmp_path / "root")
    (root / "docs" / "figures").mkdir(parents=True)
    (root / "docs" / "figures" / "s1_t2_all_steps.png").write_bytes(b"x")
    assert fr.main(_args(csv, root)) == 1
    assert (root / "docs" / "figures" / "s1_t2_all_steps.png").read_bytes() == b"x"
    assert not (root / "params").exists() and not (root / "records" / f"{NAME}_record.md").exists()


def _nothing_written(root):
    assert not (root / "params").exists() and not (root / "docs").exists() and not (root / "runs").exists()
    assert not (root / "records" / f"{NAME}_record.md").exists()
    assert (root / "records" / "LEDGER.md").read_text().count("| T") == 1


def test_time_scale_disagreeing_with_position_derivative_stops(tmp_path):
    csv = _write_session(tmp_path / "csv", PLAN6)
    root = _root(tmp_path / "root")
    assert fr.main(_args(csv, root, scale=1.0)) == 3
    _nothing_written(root)


def test_steps_json_count_mismatch_stops(tmp_path):
    csv = _write_session(tmp_path / "csv", PLAN6)
    root = _root(tmp_path / "root")
    sj = _steps_json(tmp_path / "steps.json", PLAN16)
    assert fr.main(_args(csv, root, "--steps-json", str(sj))) == 2
    _nothing_written(root)


def test_cli_help_runs_as_a_script():
    out = subprocess.run([child_python(), str(SCRIPT), "--help"], capture_output=True, text=True, timeout=60,
                         env=child_env(str(ROOT / "source")))
    assert out.returncode == 0 and "--time-scale" in out.stdout and "--ulog" in out.stdout


# ---------------------------------------------------------------- ULog reader and ulog time scale

def _msg(kind: bytes, body: bytes) -> bytes:
    return struct.pack("<HB", len(body), kind[0]) + body


def _fake_ulog(path: pathlib.Path, arm_s, disarm_s, t_lpos_s, height_m):
    """Minimal ULog: a nested type before arming_state (offset check), a multi-instance copy that must be ignored."""
    out = bytearray(b"ULog\x01\x12\x35" + b"\x01" + struct.pack("<Q", 0))
    out += _msg(b"B", bytes(40))
    out += _msg(b"F", b"nested_t:uint32_t a;float[2] b;")
    out += _msg(b"F", b"vehicle_status:uint64_t timestamp;nested_t n;uint8_t arming_state;uint8_t[3] _padding0;")
    out += _msg(b"F", b"vehicle_local_position:uint64_t timestamp;float x;float y;float z;")
    out += _msg(b"A", struct.pack("<BH", 0, 7) + b"vehicle_status")
    out += _msg(b"A", struct.pack("<BH", 0, 9) + b"vehicle_local_position")
    out += _msg(b"A", struct.pack("<BH", 1, 11) + b"vehicle_local_position")
    out += _msg(b"I", b"\x0cchar[3] junkabc")
    states = [(1.0, 1), (arm_s, 2), (disarm_s, 1), (disarm_s + 1.0, 1)]
    for t, s in states:
        out += _msg(b"D", struct.pack("<HQIffB3x", 7, int(t * 1e6), 0, 0.0, 0.0, s))
    for t, h in zip(t_lpos_s, height_m):
        out += _msg(b"D", struct.pack("<HQfff", 9, int(round(t * 1e6)), 0.0, 0.0, -h))
        out += _msg(b"D", struct.pack("<HQfff", 11, int(round(t * 1e6)), 9.0, 9.0, -50.0))
    path.write_bytes(bytes(out))
    return path


def _flight(t):
    """Height (m): ground 0, climb at 0.5 m/s from t=10 to 1 m, hold, descend from 60 to ground at 0.5 m/s."""
    return np.clip(np.minimum(0.5 * (t - 10.0), 0.5 * (62.0 - t)), 0.0, 1.0)


def test_ulog_reader_fields_offsets_and_multi_instance(tmp_path):
    t = np.arange(0.0, 80.0, 0.01)
    u = _fake_ulog(tmp_path / "f.ulg", 5.0, 70.0, t, _flight(t))
    d = fr.read_ulog(u, ["vehicle_status", "vehicle_local_position"])
    st = d["vehicle_status"]
    assert st["arming_state"].tolist() == [1, 2, 1, 1]
    assert fr.arming_transitions(st["timestamp"], st["arming_state"]) == (5.0, 70.0)
    lp = d["vehicle_local_position"]
    assert len(lp["timestamp"]) == t.size and np.allclose(-lp["z"], _flight(t), atol=1e-6)


def test_ulog_time_scale_from_flight_span(tmp_path):
    scale, t0_v = 1.7, 3.0
    t_v = np.arange(0.0, 80.0, 0.004)
    u = _fake_ulog(tmp_path / "f.ulg", 5.0, 70.0, t_v, _flight(t_v))
    t_wall = 1.0e9 + np.arange(0.0, (80.0 - t0_v) / scale, 1 / 60.0)
    z = _flight(t0_v + (t_wall - 1.0e9) * scale) + 0.01
    r = fr.ulog_time_scale(u, t_wall, z)
    assert r["scale"] == pytest.approx(scale, rel=0.005)
    assert r["arm_s"] == 5.0 and r["disarm_s"] == 70.0
    with pytest.raises(ValueError):
        fr.ulog_time_scale(u, t_wall, np.zeros_like(z))
