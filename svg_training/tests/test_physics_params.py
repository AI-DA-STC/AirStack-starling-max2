"""S2b Task 1: the physics parameter file (gains copied from the drone, never tuned) and its generator."""
import dataclasses
import hashlib
import pathlib
import subprocess
import sys
import tomllib

import pytest

from _proc import child_env, child_python

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
from svg_training.models.physics_params import (  # noqa: E402
    GAIN_NAMES, Px4Gains, apply_rate_gain_fallback, load_physics_params)

PARAMS = ROOT / "params/starling_physics_v0.toml"
DRONE_FILE = ROOT.parent / "starling_1_indoor_params.params"
SCRIPT = ROOT / "scripts/make_physics_params.py"


def _read_params(path: pathlib.Path) -> dict[str, float]:
    """QGC parameter file: "vehicle component NAME value type" lines -> {NAME: float}."""
    out = {}
    for line in path.read_text().splitlines():
        parts = line.split()
        if len(parts) == 5 and not line.startswith("#"):
            out[parts[2]] = float(parts[3])
    return out


def _fake_params_file(path: pathlib.Path, skip: str | None = None) -> dict[str, float]:
    """A made-up drone file holding every listed name (value = 1 + index / 100), minus `skip`."""
    vals = {n: 1.0 + i / 100 for i, n in enumerate(GAIN_NAMES) if n != skip}
    lines = ["# made-up test file", "1\t1\tOTHER_PARAM\t3\t6"]
    lines += [f"1\t1\t{n}\t{v}\t9" for n, v in vals.items()]
    path.write_text("\n".join(lines) + "\n")
    return vals


def _run_generator(params_file: pathlib.Path, out: pathlib.Path) -> subprocess.CompletedProcess:
    return subprocess.run([child_python(), str(SCRIPT), "--params-file", str(params_file), "--out", str(out)],
                          cwd=ROOT, env=child_env(), capture_output=True, text=True, timeout=60)


def test_airframe_derived_values():
    a = load_physics_params(PARAMS).airframe
    assert a.f_max_n() == pytest.approx(8.33586, abs=1e-4)
    assert a.hover_u() == pytest.approx(0.16388, abs=1e-4)
    assert a.k_m / a.k_f == pytest.approx(0.0135872, abs=1e-6)
    assert a.mass_kg == 0.557 and a.inertia_kgm2 == (0.002943, 0.001857, 0.004649)
    assert (a.tau_up_s, a.tau_down_s, a.omega_max_rad_s) == (0.055, 0.085, 1450.0)


def test_rotor_layouts_same_order_and_signs():
    a = load_physics_params(PARAMS).airframe
    assert a.rotor_xy_cad_m == ((0.095, 0.13), (-0.095, -0.13), (0.095, -0.13), (-0.095, 0.13))
    assert a.rotor_xy_params_m == ((0.085, 0.0625), (-0.085, -0.0625), (0.085, -0.0625), (-0.085, 0.0625))
    assert a.rotor_km == (0.05, 0.05, -0.05, -0.05)
    for cad, par in zip(a.rotor_xy_cad_m, a.rotor_xy_params_m):   # same quadrant, rotor by rotor
        assert all((c > 0) == (p > 0) for c, p in zip(cad, par))


def test_physics_params_match_drone_file():               # Review Focus 5
    if not DRONE_FILE.exists():
        pytest.skip("drone parameter file not on this machine (container)")
    drone = _read_params(DRONE_FILE)
    g = load_physics_params(PARAMS).gains
    assert {f.name.upper() for f in dataclasses.fields(g)} == set(GAIN_NAMES)
    for f in dataclasses.fields(g):
        assert getattr(g, f.name) == pytest.approx(drone[f.name.upper()], rel=1e-9), f.name


def test_source_hash_matches_drone_file():
    src = load_physics_params(PARAMS).source
    assert src["path"] == "../starling_1_indoor_params.params" and len(src["sha256"]) == 64 and src["date"]
    if not DRONE_FILE.exists():
        pytest.skip("drone parameter file not on this machine (container)")
    assert src["sha256"] == hashlib.sha256(DRONE_FILE.read_bytes()).hexdigest()


def test_no_sim_only_values():                             # iron rule 9
    text = PARAMS.read_text()
    for bad in ("0.032", "0.00065", "0.00055", "= 0.25", "= 20.0", "= 300"):
        assert bad not in text, bad
    assert text.startswith("# Tier 2 rigid-body Starling, version 0. Gains copied from the drone, never tuned.\n")


def test_every_gain_line_says_measured():
    data = tomllib.loads(PARAMS.read_text())
    lines = {ln.split("=", 1)[0].strip(): ln for ln in PARAMS.read_text().splitlines() if "=" in ln}
    for key in data["gains"]:
        assert "MEASURED ../starling_1_indoor_params.params" in lines[key], key
    for key in data["airframe"]:
        assert "MEASURED ../docs/CONFIG.md" in lines[key] or "MEASURED CMU sys-ID PDF" in lines[key], key


def test_overrides_from_s2b_physics_table():
    phys = tomllib.loads((ROOT / "configs/s2b.toml").read_text())["physics"]
    p = load_physics_params(ROOT / phys["params"], overrides=phys)
    assert (p.physics_dt_s, p.rotor_geometry, p.motor_lag, p.setpoint_delay_s) == (0.005, "cad", True, 0.0)
    q = load_physics_params(PARAMS, overrides={"physics_dt_s": 0.0025, "rotor_geometry": "params",
                                               "motor_lag": False})
    assert (q.physics_dt_s, q.rotor_geometry, q.motor_lag) == (0.0025, "params", False)
    assert q.gains == p.gains and q.airframe == p.airframe and p.upset_tilt_deg == 60.0


def test_bad_overrides_raise():
    with pytest.raises(ValueError, match="unknown"):
        load_physics_params(PARAMS, overrides={"mc_rollrate_p": 0.1})       # gains are never overridden
    with pytest.raises(ValueError, match="rotor_geometry"):
        load_physics_params(PARAMS, overrides={"rotor_geometry": "mesh"})
    with pytest.raises(ValueError, match="physics_dt_s"):
        load_physics_params(PARAMS, overrides={"physics_dt_s": 0.003})       # not a whole number per 0.05 s tick


def test_rate_gain_fallback_is_labelled_and_roll_pitch_only():
    fb = tomllib.loads((ROOT / "configs/s2b.toml").read_text())["fallback_rate_gains"]
    p = load_physics_params(PARAMS)
    q = apply_rate_gain_fallback(p, fb)
    assert "SIM-ONLY" in q.source["fallback"] and "SIM-ONLY" not in str(p.source)
    for name in ("mc_rollrate_p", "mc_rollrate_i", "mc_rollrate_d", "mc_pitchrate_p", "mc_pitchrate_i",
                 "mc_pitchrate_d"):
        assert getattr(q.gains, name) == pytest.approx(0.5 * getattr(p.gains, name)), name
    for name in ("mc_yawrate_p", "mc_yawrate_i", "mpc_xy_p", "mc_roll_p"):
        assert getattr(q.gains, name) == getattr(p.gains, name), name


def test_generator_writes_loadable_file(tmp_path):        # made-up numbers
    vals = _fake_params_file(tmp_path / "fake.params")
    r = _run_generator(tmp_path / "fake.params", tmp_path / "out.toml")
    assert r.returncode == 0, r.stderr
    p = load_physics_params(tmp_path / "out.toml")
    for f in dataclasses.fields(Px4Gains):
        assert getattr(p.gains, f.name) == pytest.approx(vals[f.name.upper()], rel=1e-12), f.name
    assert p.source["sha256"] == hashlib.sha256((tmp_path / "fake.params").read_bytes()).hexdigest()
    assert p.airframe.f_max_n() == pytest.approx(8.33586, abs=1e-4)


def test_generator_refuses_missing_name(tmp_path):
    _fake_params_file(tmp_path / "fake.params", skip="MPC_XY_P")
    r = _run_generator(tmp_path / "fake.params", tmp_path / "out.toml")
    assert r.returncode == 2 and "MPC_XY_P" in r.stderr
    assert not (tmp_path / "out.toml").exists()
