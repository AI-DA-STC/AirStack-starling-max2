"""STE task L1.1: the PX4 cascade of the physics drone sees a delayed, noisy state, as PX4 1.14 sees EKF2's estimate.

``models/estimator_effect.EstimatorEffect`` (ring buffer of past states in physics steps, seeded Gaussian noise per
quantity, batched) sits after the world read of ``models/physics_drone.PhysicsDrone``; the game keeps the true state.
Tests (WORK_BREAKDOWN L1.1): default 0 = today bit for bit (against the frozen copy ``tests/_physics_drone_today.py``);
a delay of k physics steps returns the state of k steps earlier exactly; noise mean and spread within sampling tolerance
with a fixed seed; reset fills the buffer with the reset state; same results on ``TorchRigidBodyWorld`` and (marked
``isaac``, run by ``scripts/l1_model_check.py``) ``IsaacWorld``.

CPU, float32, made-up delays, noise levels and setpoints (none is a drone value). Observed in the training simulator
(PyTorch reference world), not a flight result.
"""
import dataclasses
import json
import math
import os
import pathlib
import subprocess
import sys
import tomllib

import pytest
import torch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))
from _physics_drone_today import TodayPhysicsDrone  # noqa: E402
from svg_training.core.game_config import load_s2b_gates  # noqa: E402
from svg_training.models.estimator_effect import EstimatorEffect  # noqa: E402
from svg_training.models.frames import quat_from_yaw_enu, quat_mul_wxyz  # noqa: E402
from svg_training.models.physics_drone import PhysicsDrone  # noqa: E402
from svg_training.models.physics_params import (EFFECT_KEYS, load_physics_drone_params,  # noqa: E402
                                                load_physics_params)
from svg_training.models.rigid_body import TorchRigidBodyWorld  # noqa: E402

import l1_model_check as check  # noqa: E402

V0 = ROOT / "params/starling_physics_v0.toml"
V1 = ROOT / "params/starling_physics_v1.toml"
P0 = load_physics_drone_params(V0)                  # the game's physics drone: SIM-ONLY yaw-rate gains (16 Nov ruling)
P1 = load_physics_drone_params(V1)
DT = P0.physics_dt_s


def world(n, m, p=P0):
    return TorchRigidBodyWorld(n, m, p.airframe, p.physics_dt_s, "cpu")


def with_effects(p, **kw):
    return dataclasses.replace(p, **kw)


# ------------------------------------------------------------------------------------- default 0 = today, bit for bit
def scripted_flight(drone, n, m, gen):
    """Made-up flight: starts, 6 ticks of random setpoints, a wall clamp, a partial restart, 4 more ticks. Returns
    every state output of the drone after every call, in order."""
    out = []

    def snap():
        out.append([drone.pos_m.clone(), drone.vel_mps.clone(), drone.quat_wxyz.clone(), drone._ang_vel_b.clone(),
                    drone.tilt_rad.clone(), drone.max_tilt_rad.clone(), drone.upset.clone(),
                    drone.nonfinite_count.clone()])

    start = torch.rand(n, m, 3, generator=gen) * 4.0 + torch.tensor([0.0, 0.0, 1.0])
    drone.reset(torch.ones(n, m, dtype=torch.bool), start, torch.rand(n, m, generator=gen) * 6.0 - 3.0)
    snap()
    for tick in range(10):
        if tick == 6:
            mask = torch.rand(n, m, generator=gen) > 0.5
            drone.write_clamped(mask, drone.pos_m * 0.9, torch.zeros_like(drone.vel_mps))
            snap()
            again = torch.rand(n, m, generator=gen) > 0.6
            drone.reset(again, start + 0.5, torch.zeros(n, m))
            snap()
        p_sp = drone.pos_m + torch.rand(n, m, 3, generator=gen) - 0.5
        v_ff = torch.rand(n, m, 3, generator=gen) - 0.5
        a_ff = torch.rand(n, m, 3, generator=gen) - 0.5
        drone.step_setpoint(p_sp, v_ff, a_ff, torch.rand(n, m, generator=gen) - 0.5, torch.zeros(n, m))
        snap()
    return out


@pytest.mark.parametrize("params", [P0, P1, with_effects(P0, **{k: 0.0 for k in EFFECT_KEYS})],
                         ids=["v0", "v1", "explicit_zeros"])
def test_default_off_is_today_bit_for_bit(params):
    n, m = 2, 3
    today = TodayPhysicsDrone(world(n, m), P0, "cpu")
    now = PhysicsDrone(world(n, m), params, "cpu")
    a = scripted_flight(today, n, m, torch.Generator().manual_seed(7))
    b = scripted_flight(now, n, m, torch.Generator().manual_seed(7))
    assert len(a) == len(b)
    for i, (ra, rb) in enumerate(zip(a, b)):
        for j, (x, y) in enumerate(zip(ra, rb)):
            assert torch.equal(x, y), f"call {i}, output {j} differs from today's physics drone"
    assert now.estimator.off and now.estimator.buffer is None       # off: no ring buffer, no generator draws


def test_off_passes_the_true_state_to_the_cascade():
    d = PhysicsDrone(world(1, 2), P0, "cpu")
    assert d.est_pos_m is d.pos_m and d.est_vel_mps is d.vel_mps and d.est_quat_wxyz is d.quat_wxyz
    assert d.est_ang_vel_b is d._ang_vel_b


# ------------------------------------------------------------------------------------- the effect on its own
def states(t, n=2, m=3):
    """A made-up state that differs at every step t: pos, quat (unit), vel, body rates."""
    base = torch.arange(n * m, dtype=torch.float32).reshape(n, m, 1)
    pos = base + t * torch.tensor([1.0, 2.0, 3.0])
    vel = -base + t * torch.tensor([0.5, -0.25, 0.125])
    quat = quat_from_yaw_enu(0.01 * t + 0.1 * base[..., 0])
    ang = base + t * torch.tensor([0.1, 0.2, 0.3])
    return pos, quat, vel, ang


def make_effect(k=0, n=2, m=3, seed=0, **noise):
    e = EstimatorEffect(n, m, delay_steps=k, noise_pos_m=noise.get("pos", 0.0), noise_vel_mps=noise.get("vel", 0.0),
                        noise_att_rad=noise.get("att", 0.0), noise_rate_rad_s=noise.get("rate", 0.0), device="cpu",
                        seed=seed)
    e.reset(torch.ones(n, m, dtype=torch.bool), *states(0, n, m))
    return e


@pytest.mark.parametrize("k", [1, 3, 30])
def test_delay_of_k_steps_returns_the_state_of_k_steps_earlier_exactly(k):
    e = make_effect(k)
    for t in range(1, 3 * k + 5):
        pos, quat, vel, ang = e.push(*states(t))
        want = states(max(t - k, 0))                 # before k steps have passed: the reset state (buffer filled)
        assert torch.equal(pos, want[0]) and torch.equal(quat, want[1]) and torch.equal(vel, want[2]), t
        assert torch.equal(ang, states(t)[3]), t     # body rates come from the gyro: never delayed


def test_float64_states_stay_float64():
    """The buffer and the noise take the state's dtype: a float64 world is never rounded through float32."""
    e = EstimatorEffect(2, 3, 2, 0.01, 0.0, 0.0, 0.0, "cpu")
    s64 = [x.double() for x in states(0)]
    e.reset(torch.ones(2, 3, dtype=torch.bool), *s64)
    for t in range(1, 5):
        pos, quat, vel, ang = e.push(*[x.double() for x in states(t)])
        assert pos.dtype == quat.dtype == vel.dtype == torch.float64
        assert torch.equal(vel, states(max(t - 2, 0))[2].double())


def test_estimate_is_a_copy_not_a_view_of_the_ring():
    e = make_effect(2)
    first = e.push(*states(1))
    kept = [x.clone() for x in first]
    for t in range(2, 8):
        e.push(*states(t))
    assert all(torch.equal(a, b) for a, b in zip(first, kept))


def test_reset_fills_the_buffer_with_the_reset_state():
    k = 4
    e = make_effect(k)
    for t in range(1, 10):
        e.push(*states(t))
    mask = torch.zeros(2, 3, dtype=torch.bool)
    mask[1, 2] = True
    fresh = states(100)
    est = e.reset(mask, *fresh)
    assert torch.equal(est[0][1, 2], fresh[0][1, 2])                         # at once: the reset state
    for t in range(10, 10 + k):
        pos, quat, vel, _ = e.push(*states(t))
        assert torch.equal(pos[1, 2], fresh[0][1, 2]) and torch.equal(quat[1, 2], fresh[1][1, 2])
        assert torch.equal(vel[1, 2], fresh[2][1, 2])
        assert torch.equal(pos[0, 0], states(t - k)[0][0, 0])                 # the others keep their history
    pos, _, _, _ = e.push(*states(10 + k))
    assert torch.equal(pos[1, 2], states(10)[0][1, 2])                       # then the new history


def test_replace_latest_overwrites_the_current_instant_only():
    """write_clamped moves the drone without a physics step: the newest buffer entry is replaced, not added."""
    k = 3
    e = make_effect(k)
    for t in range(1, 6):
        e.push(*states(t))
    clamped = states(50)
    e.replace_latest(*clamped)
    outs = [e.push(*states(t)) for t in range(6, 6 + k)]
    assert torch.equal(outs[-1][0], clamped[0])                              # k steps later the clamp shows
    assert torch.equal(outs[-2][0], states(4)[0])                            # and the step count did not change


def _rotvec_between(q_true, q_est):
    """Small-angle rotation vector of q_true^-1 q_est (2 vec / w; exact for q_true (x) [1, d / 2] normalised)."""
    conj = q_true * torch.tensor([1.0, -1.0, -1.0, -1.0])
    d = quat_mul_wxyz(conj, q_est)
    return 2.0 * d[..., 1:] / d[..., :1]


def test_noise_mean_and_spread_with_a_fixed_seed():
    n, m, steps = 32, 4, 200
    sig = {"pos": 0.02, "vel": 0.05, "att": 0.01, "rate": 0.2}              # made-up noise levels
    e = make_effect(0, n, m, seed=11, **sig)
    s = states(3, n, m)
    err = {k: [] for k in sig}
    for _ in range(steps):
        pos, quat, vel, ang = e.push(*s)
        err["pos"].append(pos - s[0])
        err["vel"].append(vel - s[2])
        err["att"].append(_rotvec_between(s[1], quat))
        err["rate"].append(ang - s[3])
        assert torch.allclose(quat.norm(dim=-1), torch.ones(n, m))           # still a unit quaternion
    for key, sd in sig.items():
        x = torch.stack(err[key]).reshape(-1, 3).double()                  # 25,600 draws per component
        se = sd / math.sqrt(x.shape[0])
        assert x.mean(0).abs().max() < 5.0 * se, key                       # mean 0 within 5 standard errors
        assert torch.allclose(x.std(0), torch.full((3,), sd, dtype=torch.float64), rtol=0.03), key   # ~ 4.4 sigma


def test_noise_is_seeded_and_each_quantity_has_its_own_stream():
    a = make_effect(0, seed=5, pos=0.1)
    b = make_effect(0, seed=5, pos=0.1)
    c = make_effect(0, seed=6, pos=0.1)
    d = make_effect(0, seed=5, pos=0.1, vel=0.3)
    for t in range(1, 5):
        pa, pb, pc, pd = (x.push(*states(t))[0] for x in (a, b, c, d))
        assert torch.equal(pa, pb) and not torch.equal(pa, pc)
        assert torch.equal(pa, pd)              # switching velocity noise on leaves position noise as it was


def test_noise_off_quantities_pass_unchanged():
    e = make_effect(0, pos=0.1)
    pos, quat, vel, ang = e.push(*states(1))
    s = states(1)
    assert not torch.equal(pos, s[0])
    assert torch.equal(quat, s[1]) and torch.equal(vel, s[2]) and torch.equal(ang, s[3])


def test_bad_settings_raise():
    with pytest.raises(ValueError, match="delay_steps"):
        EstimatorEffect(1, 1, -1, 0.0, 0.0, 0.0, 0.0, "cpu")
    with pytest.raises(ValueError, match="noise"):
        EstimatorEffect(1, 1, 0, -0.1, 0.0, 0.0, 0.0, "cpu")
    with pytest.raises(ValueError, match="noise"):
        EstimatorEffect(1, 1, 0, float("nan"), 0.0, 0.0, 0.0, "cpu")


# ------------------------------------------------------------------------------------- parameters (v0 untouched, v1)
def test_v0_loads_with_every_effect_off():
    p = load_physics_params(V0)
    assert all(getattr(p, k) == 0.0 for k in EFFECT_KEYS)
    assert p.state_delay_steps() == 0
    assert set(EFFECT_KEYS) == {"state_delay_s", "state_noise_pos_m", "state_noise_vel_mps", "state_noise_att_rad",
                                "state_noise_rate_rad_s", "drag_x_n_per_mps", "drag_y_n_per_mps", "drag_z_n_per_mps"}


def test_v1_is_v0_plus_effect_keys_all_open_at_zero():
    p0, p1 = load_physics_params(V0), load_physics_params(V1)
    assert p1.gains == p0.gains and p1.airframe == p0.airframe
    assert (p1.physics_dt_s, p1.rotor_geometry, p1.motor_lag, p1.setpoint_delay_s, p1.upset_tilt_deg) == \
        (p0.physics_dt_s, p0.rotor_geometry, p0.motor_lag, p0.setpoint_delay_s, p0.upset_tilt_deg)
    assert all(getattr(p1, k) == 0.0 for k in EFFECT_KEYS)
    text = V1.read_text()
    assert text.startswith("# Tier 2 rigid-body Starling, version 1.")
    lines = {ln.split("=", 1)[0].strip(): ln for ln in text.splitlines() if "=" in ln}
    for k in EFFECT_KEYS:
        assert "OPEN" in lines[k] and "L1.3" in lines[k], k
    assert "0.1482" in lines["state_delay_s"]          # the tier 1 setpoint delay is named and NOT used (no double count)
    t0, t1 = tomllib.loads(V0.read_text()), tomllib.loads(text)
    assert t1["gains"] == t0["gains"] and t1["airframe"] == t0["airframe"]


def test_effect_keys_can_be_overridden_and_are_checked():
    p = load_physics_params(V0, overrides={"state_delay_s": 0.1482, "state_noise_pos_m": 0.01,
                                           "drag_x_n_per_mps": 0.2})
    assert p.state_delay_s == 0.1482 and p.state_noise_pos_m == 0.01 and p.drag_x_n_per_mps == 0.2
    assert p.state_delay_steps() == 30                 # 29.64 physics steps of 5 ms, rounded to the nearest
    for key in EFFECT_KEYS:
        with pytest.raises(ValueError, match=key):
            load_physics_params(V0, overrides={key: -0.01})
        with pytest.raises(ValueError, match=key):
            load_physics_params(V0, overrides={key: float("inf")})


# ------------------------------------------------------------------------------------- through the physics drone
def test_physics_drone_delay_on_the_torch_world():
    res = check.delay_check(world(2, 3), P0, delay_steps=3, ticks=6, device="cpu")
    assert res["delay_steps"] == 3 and res["substeps_checked"] == 60
    assert res["max_err"] == 0.0                       # cascade input = the world's state 3 physics steps earlier


def test_physics_drone_noise_on_the_torch_world():
    res = check.noise_check(world(16, 4), P0, ticks=10, device="cpu")
    for key, row in res.items():
        assert abs(row["mean"]) < 5.0 * row["sigma"] / math.sqrt(row["count"]), key
        assert row["std"] == pytest.approx(row["sigma"], rel=0.05), key


def test_game_keeps_the_true_state():
    p = with_effects(P0, state_delay_s=0.02, state_noise_pos_m=0.05)
    d = PhysicsDrone(world(1, 2, p), p, "cpu")
    d.step_setpoint(d.pos_m.clone(), torch.zeros(1, 2, 3), torch.zeros(1, 2, 3), torch.zeros(1, 2), torch.zeros(1, 2))
    pos, quat, vel, _ = d.world.state()
    assert torch.equal(d.pos_m, pos) and torch.equal(d.vel_mps, vel) and torch.equal(d.quat_wxyz, quat)
    assert not torch.equal(d.est_pos_m, d.pos_m)


def test_same_seed_same_flight_on_cpu():
    p = with_effects(P0, state_delay_s=0.01, state_noise_pos_m=0.01, state_noise_vel_mps=0.02,
                     state_noise_att_rad=0.002, state_noise_rate_rad_s=0.01)
    runs = []
    for _ in range(2):
        d = PhysicsDrone(world(2, 2, p), p, "cpu", noise_seed=3)
        runs.append(scripted_flight(d, 2, 2, torch.Generator().manual_seed(1)))
    for ra, rb in zip(*runs):
        assert all(torch.equal(x, y) for x, y in zip(ra, rb))


# ------------------------------------------------------------------------------------- scripts/l1_model_check.py (CPU)
@pytest.fixture
def run_dir(tmp_path):
    """A run folder under runs/ (the script refuses any other place), removed after the test."""
    import shutil
    d = ROOT / "runs" / "pytest_l1_model" / tmp_path.name
    d.parent.mkdir(parents=True, exist_ok=True)
    yield d
    shutil.rmtree(d, ignore_errors=True)
    if d.parent.is_dir() and not any(d.parent.iterdir()):
        d.parent.rmdir()


def test_model_check_refuses_bad_arguments(tmp_path, run_dir):
    assert check.main(["--run-dir", str(tmp_path / "x"), "--cap-h", "0.1", "--dry-cpu"]) == 2      # not under runs/
    assert check.main(["--run-dir", str(run_dir), "--cap-h", "0", "--dry-cpu"]) == 2
    assert check.main(["--run-dir", str(run_dir), "--cap-h", "0.1"]) == 2                          # no --headless


def test_model_check_dry_cpu_end_to_end(run_dir):
    """The whole parent / child path on the CPU torch world (tiny): every part written, both arms measured, the
    effects really on in the "on" arm, tier 1 without an "on" arm; the same command then resumes and does nothing."""
    env = dict(os.environ, PYTHONPATH=str(ROOT / "source"), CUDA_VISIBLE_DEVICES="")
    cmd = [sys.executable, "scripts/l1_model_check.py", "--run-dir", str(run_dir), "--cap-h", "0.1", "--dry-cpu"]
    r = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, (r.stdout[-3000:], r.stderr[-3000:])
    res = json.loads((run_dir / "results.json").read_text())
    parts = res["parts"]
    assert set(parts) == {"isaac_tests", "tier2_isaac", "tier2_torch", "tier1"}
    assert parts["isaac_tests"]["last_line"] == "skipped: --dry-cpu"
    for name in ("tier2_isaac", "tier2_torch"):          # --dry-cpu: both on the torch world
        row = parts[name]
        assert row["mean_game_steps_per_s"]["off"] > 0 and row["mean_game_steps_per_s"]["on"] > 0
        assert row["on_arm"]["delay_steps"] == 10 and row["on_arm"]["drag"] is True
        assert row["on_arm"]["noise"] == ["pos", "att", "vel", "rate"]
        assert row["cost_fraction"] is not None and row["dry_cpu"] is True
    assert "on" not in parts["tier1"]["mean_game_steps_per_s"] and "L1.7" in parts["tier1"]["on_arm"]
    assert "MADE UP" in (run_dir / "params_on.toml").read_text()
    on = load_physics_params(run_dir / "params_on.toml")
    assert on.state_delay_steps() == 10 and on.gains == load_physics_params(V1).gains
    assert "# L1.1 / L1.2 model check" in (run_dir / "results.md").read_text()
    stamp = (run_dir / "results.json").stat().st_mtime_ns
    r = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0 and "tier2_torch ..." not in r.stdout
    assert (run_dir / "results.json").stat().st_mtime_ns >= stamp


# ------------------------------------------------------------------------------------- the Isaac Lab world
@pytest.mark.isaac
def test_isaac_world_same_results_as_torch(tmp_path):
    """scripts/l1_model_check.py --smoke runs the same checks on IsaacWorld and flies one effects-on step set on
    both worlds. Marked isaac: run by scripts/l1_model_check.py (or SVG_ISAAC_TESTS=1) on a free GPU."""
    out = tmp_path / "smoke.json"
    python = os.environ.get("SVG_ISAACLAB") or sys.executable
    env = dict(os.environ, PYTHONPATH=str(ROOT / "source"))
    r = subprocess.run([python, "scripts/l1_model_check.py", "--smoke", "--headless", "--out", str(out)],
                       cwd=ROOT, env=env, capture_output=True, text=True, timeout=1800)
    assert r.returncode == 0 and out.exists(), (r.stdout[-3000:], r.stderr[-3000:])
    res = json.loads(out.read_text())
    assert res["world"].lower().startswith("isaac")             # IsaacWorld.label is "isaaclab-<version>" (first GPU run, 22 Nov)
    assert res["delay"]["max_err"] == 0.0 and res["delay"]["substeps_checked"] > 0
    for key, row in res["noise"].items():
        assert abs(row["mean"]) < 5.0 * row["sigma"] / math.sqrt(row["count"]), key
        assert row["std"] == pytest.approx(row["sigma"], rel=0.05), key
    gates = load_s2b_gates()["agreement_gates"]
    assert res["agreement"]["pos_max_m"] <= gates["closed_loop_pos_max_m"]
    assert res["agreement"]["vel_rms_mps"] <= gates["closed_loop_vel_rms_max_mps"]
    assert res["agreement"]["nonfinite"] == 0
