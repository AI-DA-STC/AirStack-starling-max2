"""STE task L1.1b: the shape of the estimator model. What PX4's cascade sees is the true state plus a slowly varying,
correlated estimate ERROR (first-order Gauss-Markov per quantity), with at most a small residual delay on position and
velocity; attitude is never delayed (EKF2's output predictor hands the controllers current-time states; the L1.1 code
review found the z loop unstable at about 0.117 s of feedback delay); the noise is seeded by the game seed.

Tests (WORK_BREAKDOWN L1.1b): off = today bit for bit; stationary mean, spread and lag-1 autocorrelation exp(-dt/tau)
within sampling tolerance with fixed seeds; reset draws from the stationary distribution; an attitude delay is refused;
the residual-delay guard; the game seed reaches the noise (game, both replay paths, ``SvgGame.reset(seed)``); a CPU
hover with made-up exploratory error values stays close.

CPU, float32 unless said, made-up sigmas and correlation times (none is a drone value). Observed in the training
simulator (PyTorch reference world), not a flight result.
"""
import dataclasses
import math
import sys
import pathlib

import pytest
import torch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))
from _physics_drone_today import TodayPhysicsDrone  # noqa: E402
from test_estimator_effect import scripted_flight, states, _rotvec_between  # noqa: E402
from svg_training.models.estimator_effect import ERROR_QUANTITIES, EstimatorEffect  # noqa: E402
from svg_training.models.physics_drone import PhysicsDrone  # noqa: E402
from svg_training.models.physics_params import (EFFECT_KEYS, ERROR_KEYS, STATE_DELAY_MAX_S,  # noqa: E402
                                                load_physics_drone_params, load_physics_params)
from svg_training.models.rigid_body import TorchRigidBodyWorld  # noqa: E402

import l1_model_check as check  # noqa: E402

V0 = ROOT / "params/starling_physics_v0.toml"
V1 = ROOT / "params/starling_physics_v1.toml"
P0 = load_physics_drone_params(V0)
P1 = load_physics_drone_params(V1)
DT = P0.physics_dt_s


def world(n, m, p=P0):
    return TorchRigidBodyWorld(n, m, p.airframe, p.physics_dt_s, "cpu")


def make_error(n, m, err, seed=0, delay=0, dtype=torch.float32, **white):
    """An EstimatorEffect with Gauss-Markov errors ``err`` = {quantity: (sigma, tau_s)}, reset at states(0)."""
    e = EstimatorEffect(n, m, delay, white.get("pos", 0.0), white.get("vel", 0.0), white.get("att", 0.0),
                        white.get("rate", 0.0), "cpu", seed=seed, error=err, dt_s=DT)
    e.reset(torch.ones(n, m, dtype=torch.bool), *[x.to(dtype) for x in states(0, n, m)])
    return e


def errors_of(est, truth):
    """Per quantity: estimate - truth [.., 3] (attitude: the small body rotation vector)."""
    return {"pos": est[0] - truth[0], "vel": est[2] - truth[2], "att": _rotvec_between(truth[1], est[1])}


# ------------------------------------------------------------------------------------- the keys
def test_error_keys_are_effect_keys_open_at_zero_in_v1():
    assert ERROR_KEYS == ("state_error_pos_m", "state_error_pos_tau_s", "state_error_vel_mps", "state_error_vel_tau_s",
                          "state_error_att_rad", "state_error_att_tau_s")
    assert set(ERROR_KEYS) <= set(EFFECT_KEYS) and ERROR_QUANTITIES == ("pos", "att", "vel")
    p0, p1 = load_physics_params(V0), load_physics_params(V1)
    assert all(getattr(p0, k) == 0.0 and getattr(p1, k) == 0.0 for k in ERROR_KEYS)
    lines = {ln.split("=", 1)[0].strip(): ln for ln in V1.read_text().splitlines() if "=" in ln}
    for k in ERROR_KEYS:
        assert "OPEN" in lines[k] and "L1.3" in lines[k], k
    assert "FIXED" in lines["state_delay_att_s"] and "0.117" in lines["state_delay_s"] and "0.05" in lines["state_delay_s"]
    assert "state_delay_max_s" not in lines                                 # FIXED in code, not a parameter-file line
    assert p1.state_delay_att_s == 0.0 and p0.state_delay_att_s == 0.0     # v0 has no such line: the default


def test_sigma_without_a_correlation_time_is_refused():
    for q, unit in (("pos", "m"), ("vel", "mps"), ("att", "rad")):
        with pytest.raises(ValueError, match=f"state_error_{q}_tau_s"):
            dataclasses.replace(P0, **{f"state_error_{q}_{unit}": 0.01})
        p = dataclasses.replace(P0, **{f"state_error_{q}_tau_s": 0.5})     # tau alone: allowed, still off
        assert getattr(p, f"state_error_{q}_tau_s") == 0.5
    with pytest.raises(ValueError, match="tau"):
        EstimatorEffect(1, 1, 0, 0.0, 0.0, 0.0, 0.0, "cpu", error={"pos": (0.01, 0.0)}, dt_s=DT)
    with pytest.raises(ValueError, match="dt_s"):
        EstimatorEffect(1, 1, 0, 0.0, 0.0, 0.0, 0.0, "cpu", error={"pos": (0.01, 0.5)})
    with pytest.raises(ValueError, match="quantit"):
        EstimatorEffect(1, 1, 0, 0.0, 0.0, 0.0, 0.0, "cpu", error={"rate": (0.01, 0.5)}, dt_s=DT)


# ------------------------------------------------------------------------------------- off = today
@pytest.mark.parametrize("extra", [{"state_error_pos_tau_s": 0.5, "state_error_vel_tau_s": 0.2,
                                    "state_error_att_tau_s": 1.0},           # correlation times alone: still off
                                   {"state_delay_s": 0.0, "state_delay_att_s": 0.0}],
                         ids=["tau_only", "guards_at_zero"])
def test_error_off_is_today_bit_for_bit(extra):
    n, m = 2, 3
    today = TodayPhysicsDrone(world(n, m), P0, "cpu")
    now = PhysicsDrone(world(n, m), dataclasses.replace(P1, **extra), "cpu", noise_seed=123)
    a = scripted_flight(today, n, m, torch.Generator().manual_seed(7))
    b = scripted_flight(now, n, m, torch.Generator().manual_seed(7))
    for i, (ra, rb) in enumerate(zip(a, b)):
        for j, (x, y) in enumerate(zip(ra, rb)):
            assert torch.equal(x, y), f"call {i}, output {j} differs from today's physics drone"
    assert now.estimator.off and not now.estimator.correlated


# ------------------------------------------------------------------------------------- Gauss-Markov statistics
@pytest.mark.parametrize("tau", [0.02, 0.5])
def test_gauss_markov_stationary_mean_spread_and_lag1_autocorrelation(tau):
    """x_{k+1} = a x_k + sigma sqrt(1 - a^2) w_k, a = exp(-dt / tau): stationary N(0, sigma^2), lag-1 autocorrelation a.
    Tolerances: 5 standard errors with the effective sample size n (1 - a) / (1 + a) of a correlated chain."""
    n, m, steps = 64, 4, 1500
    sig = {"pos": 0.02, "vel": 0.05, "att": 0.008}                          # made-up sigmas
    e = make_error(n, m, {k: (s, tau) for k, s in sig.items()}, seed=21)
    truth = states(0, n, m)
    xs = {k: [] for k in sig}
    for _ in range(steps):
        out = errors_of(e.push(*truth), truth)
        for k in sig:
            xs[k].append(out[k])
    a = math.exp(-DT / tau)
    for k, sd in sig.items():
        x = torch.stack(xs[k]).double()                                       # [T, N, M, 3]
        count = x.numel()
        n_eff = count * (1 - a) / (1 + a)
        assert abs(float(x.mean())) < 5.0 * sd / math.sqrt(n_eff), k
        std = float(x.std())
        assert std == pytest.approx(sd, rel=5.0 / math.sqrt(2.0 * n_eff) + 0.002), (k, std)
        x0, x1 = x[:-1].flatten(), x[1:].flatten()
        rho = float((x0 * x1).mean() / (x0 * x0).mean())
        assert rho == pytest.approx(a, abs=5.0 * math.sqrt((1 - a * a) / x0.numel()) + 1e-3), (k, rho, a)


def test_reset_draws_from_the_stationary_distribution():
    """At a reset the error of the restarted drones is a fresh draw of N(0, sigma^2) (no warm-up, no carry-over); the
    other drones keep theirs."""
    n, m, sd, tau = 4096, 4, 0.03, 2.0                                       # tau >> the steps: carry-over would show
    e = make_error(n, m, {"pos": (sd, tau)}, seed=3)
    truth = states(0, n, m)
    first = errors_of(e.reset(torch.ones(n, m, dtype=torch.bool), *truth), truth)["pos"].double()
    assert float(first.std()) == pytest.approx(sd, rel=0.02)              # 49,152 draws: about 3.1 % at 5 SE ...
    assert abs(float(first.mean())) < 5.0 * sd / math.sqrt(first.numel())
    for _ in range(5):
        before = errors_of(e.push(*truth), truth)["pos"].double()
    mask = torch.zeros(n, m, dtype=torch.bool)
    mask[: n // 2] = True
    after = errors_of(e.reset(mask, *truth), truth)["pos"].double()
    kept, fresh = ~mask, mask
    assert torch.equal(after[kept], before[kept])                          # a reset is not a step
    assert float(after[fresh].std()) == pytest.approx(sd, rel=0.03)
    corr = float((after[fresh] * before[fresh]).mean() / (sd * sd))         # carry-over would give about 0.99
    assert abs(corr) < 0.03


def test_error_is_seeded_per_quantity_and_apart_from_the_white_noise():
    err = {"pos": (0.02, 0.5)}
    a = make_error(2, 3, err, seed=5)
    b = make_error(2, 3, err, seed=5)
    c = make_error(2, 3, err, seed=6)
    d = make_error(2, 3, {**err, "vel": (0.05, 0.2), "att": (0.01, 1.0)}, seed=5, pos=0.01, rate=0.1)
    w = make_error(2, 3, {}, seed=5, pos=0.01)                              # white position noise alone
    w2 = make_error(2, 3, err, seed=5, pos=0.01)
    for t in range(1, 6):
        s = states(t)
        pa, pb, pc = (x.push(*s)[0] - s[0] for x in (a, b, c))
        pd = d.push(*s)[0] - s[0]
        pw, pw2 = w.push(*s)[0] - s[0], w2.push(*s)[0] - s[0]
        assert torch.equal(pa, pb) and not torch.equal(pa, pc)
        assert torch.allclose(pd, pw2, atol=0, rtol=0)    # switching other quantities on leaves position as it was
        assert torch.allclose(pw2 - pw, pa, atol=1e-5)    # adds to the white noise, own stream (float32 rounding)


def test_white_noise_streams_keep_their_l11_seeds():
    """Appending the correlated-error streams left L1.1's white-noise draws for a seed unchanged: stream i of seed s is
    seeded ((s + 1) x 4 + i) x 0x9E3779B97F4A7C15 mod 2^63, as at L1.1 (commit ff2c912e)."""
    mix = 0x9E3779B97F4A7C15
    sig = {"pos": 0.02, "att": 0.01, "vel": 0.05, "rate": 0.2}
    for seed in (0, 5, 1100):
        e = EstimatorEffect(2, 3, 0, sig["pos"], sig["vel"], sig["att"], sig["rate"], "cpu", seed=seed,
                            error={"pos": (0.02, 0.5), "att": (0.01, 0.5), "vel": (0.05, 0.2)}, dt_s=DT)
        for i, k in enumerate(("pos", "att", "vel", "rate")):
            g = torch.Generator().manual_seed((((seed + 1) * 4 + i) * mix) % (1 << 63))
            assert torch.equal(e._noise[k], torch.randn(2, 3, 3, generator=g) * sig[k]), (seed, k)
    seeds = {(s, i): __import__("svg_training.models.estimator_effect", fromlist=["x"]).stream_seed(s, i)
             for s in range(50) for i in range(7)}
    assert len(set(seeds.values())) == len(seeds)                           # no two (seed, stream) pairs collide


def test_float64_error_stays_float64():
    e = make_error(2, 3, {"pos": (0.02, 0.5), "att": (0.01, 0.5)}, dtype=torch.float64)
    out = e.push(*[x.double() for x in states(1)])
    assert out[0].dtype == out[1].dtype == torch.float64


def test_replace_latest_keeps_the_error():
    e = make_error(2, 3, {"pos": (0.02, 0.5)}, seed=1)
    s = states(1)
    p1 = e.push(*s)[0] - s[0]
    clamped = states(9)
    p2 = e.replace_latest(*clamped)[0] - clamped[0]
    assert torch.allclose(p1, p2, atol=1e-5)              # float32 rounding of positions up to ~30 m


# ------------------------------------------------------------------------------------- delay: attitude never
@pytest.mark.parametrize("k", [1, 4])
def test_attitude_and_body_rates_are_never_delayed(k):
    e = make_error(2, 3, {}, delay=k)
    for t in range(1, 3 * k + 3):
        pos, quat, vel, ang = e.push(*states(t))
        want = states(max(t - k, 0))
        assert torch.equal(pos, want[0]) and torch.equal(vel, want[2]), t     # residual delay: position, velocity
        assert torch.equal(quat, states(t)[1]) and torch.equal(ang, states(t)[3]), t   # current time


def test_a_config_that_delays_attitude_is_refused():
    for bad in (0.005, 0.02):
        with pytest.raises(ValueError, match="attitude"):
            load_physics_params(V1, overrides={"state_delay_att_s": bad})
        with pytest.raises(ValueError, match="attitude"):
            dataclasses.replace(P0, state_delay_att_s=bad)
    assert load_physics_params(V1, overrides={"state_delay_att_s": 0.0}).state_delay_att_s == 0.0


def test_residual_delay_guard():
    """The limit is FIXED in code (STATE_DELAY_MAX_S, 0.05 s; lead's call, fix round 1): no config may raise it."""
    assert STATE_DELAY_MAX_S == 0.05
    assert load_physics_params(V0, overrides={"state_delay_s": 0.05}).state_delay_steps() == 10
    for bad in (0.06, 0.1, 0.1482):
        with pytest.raises(ValueError, match="0.117"):                       # the message names the z-loop limit
            load_physics_params(V0, overrides={"state_delay_s": bad})
        with pytest.raises(ValueError, match="0.117"):
            dataclasses.replace(P0, state_delay_s=bad)
    with pytest.raises(ValueError, match="state_delay_max_s"):               # a config that sets the limit is refused
        load_physics_params(V0, overrides={"state_delay_s": 0.1482, "state_delay_max_s": 0.2})
    text = V1.read_text().replace("state_delay_s = 0.0 ", "state_delay_max_s = 0.2\nstate_delay_s = 0.0 ")
    f = ROOT / "runs" / "pytest_l11b_limit.toml"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text)
    try:
        with pytest.raises(ValueError, match="state_delay_max_s"):           # also in a parameter file's [model]
            load_physics_params(f)
    finally:
        f.unlink()
    assert not hasattr(P0, "state_delay_max_s")


# ------------------------------------------------------------------------------------- the game seed reaches the noise
ERR_ON = {"state_error_pos_m": 0.02, "state_error_pos_tau_s": 0.5, "state_error_vel_mps": 0.02,
          "state_error_vel_tau_s": 0.2, "state_error_att_rad": 0.005, "state_error_att_tau_s": 0.5}


def _game(tmp_path, seed, n=2):
    """The L0.2 speed game on the physics backend with ERR_ON written into a copy of v1, 1v1, torch world (CPU)."""
    from svg_training.core.game import SvgGame
    from svg_training.core.game_config import load_game_cfg
    settings = {"run": {"params_base": "params/starling_physics_v1.toml"}, "effects_on": ERR_ON}
    path = check.params_on_file(tmp_path, settings)
    base, _ = load_game_cfg(ROOT / "configs/ste_l011/base.toml", use_local=False)
    cfg = base.replace(**{"starling.backend": "physics", "starling.physics_params": str(path)})
    p = load_physics_params(path)
    return SvgGame(cfg, n, 1, 1, device="cpu", seed=seed, world=TorchRigidBodyWorld(n, 2, p.airframe,
                                                                                    p.physics_dt_s, "cpu"))


def _error_trace(game, ticks=4):
    zero = {"guard": torch.zeros(game.num_games, 1, 4), "strike": torch.zeros(game.num_games, 1, 4)}
    out = []
    for _ in range(ticks):
        game.step(zero)
        d = game._starling.drone
        out.append(d.est_pos_m - d.pos_m)
    return torch.stack(out)


def test_game_seed_reaches_the_noise(tmp_path):
    g5a, g5b, g6 = _game(tmp_path, 5), _game(tmp_path, 5), _game(tmp_path, 6)
    assert g5a._starling.drone.noise_seed == 5 and g6._starling.drone.noise_seed == 6
    assert g5a._starling.drone.estimator.correlated == ("pos", "att", "vel")
    a, b, c = _error_trace(g5a), _error_trace(g5b), _error_trace(g6)
    assert torch.equal(a, b) and not torch.allclose(a, c)
    # reset(seed) restarts the noise as it restarts the game's generator
    g5a.reset(seed=9)
    g6.reset(seed=9)
    assert torch.equal(_error_trace(g5a), _error_trace(g6))


class Jiggle:
    """A made-up player: seeded random commands (its own generator), so the drones move and leave the zone."""
    def __init__(self, n, k, seed):
        self.n, self.k, self.gen = n, k, torch.Generator().manual_seed(seed)

    def reset(self, mask):
        pass

    def act(self, obs):
        return torch.rand(self.n, self.k, 4, generator=self.gen) * 2 - 1


def _game_off(tmp_path, seed, n=2):
    """As _game, with every effect off (v1 as shipped)."""
    from svg_training.core.game import SvgGame
    from svg_training.core.game_config import load_game_cfg
    base, _ = load_game_cfg(ROOT / "configs/ste_l011/base.toml", use_local=False)
    cfg = base.replace(**{"starling.backend": "physics", "starling.physics_params": str(V1)})
    return SvgGame(cfg, n, 1, 1, device="cpu", seed=seed, world=world(n, 2, P1))


@pytest.mark.parametrize("effects", ["error_on", "off"])
def test_replay_reproduces_the_recorded_game_exactly(tmp_path, effects):
    """Fix round 1 (MEDIUM): the game's drone was built and reset before the recording starts, so its estimator has
    drawn more than a fresh replay drone's; record_inputs keeps the estimator's state at the start of the recording and
    the replays restore it: replay == game, every drone, every tick (as tests/test_ste_l02.py's C-1a, effects off)."""
    from svg_training.ste import speed, tier2_train
    make = _game if effects == "error_on" else _game_off
    n, ticks = 2, 40
    recs = {}
    for name, mod in (("speed", speed), ("tier2_train", tier2_train)):
        game = make(tmp_path, 5, n)
        recs[name] = mod.record_inputs(game, Jiggle(n, 1, 1), Jiggle(n, 1, 2), ticks)
        params = game._starling.params
    assert ("estimator" in recs["speed"]) and ("estimator" in recs["tier2_train"])
    want = recs["speed"]["drone_pos"]                                        # the game's own positions, every tick
    for name, mod in (("speed", speed), ("tier2_train", tier2_train)):
        got = mod.replay_positions(world(n, 2, params), params, "cpu", recs[name])
        assert torch.equal(got, want), (name, effects, float((got - want).norm(dim=-1).max()))
    if effects == "error_on":                                                # without the restore it would differ
        bare = {k: v for k, v in recs["speed"].items() if k != "estimator"}
        assert not torch.equal(speed.replay_positions(world(n, 2, params), params, "cpu", bare), want)


@pytest.mark.parametrize("module", ["speed", "tier2_train"])
def test_replays_use_the_recorded_game_seed(tmp_path, module):
    import importlib
    mod = importlib.import_module(f"svg_training.ste.{module}")
    game = _game(tmp_path, 5)

    class Still:                       # a made-up player: zero command
        def __init__(self, k):
            self.k = k

        def reset(self, mask):
            pass

        def act(self, obs):
            return torch.zeros(game.num_games, self.k, 4)
    rec = mod.record_inputs(game, Still(1), Still(1), 3)
    assert rec["noise_seed"] == 5
    params = game._starling.params

    def replay(r):
        return mod.replay_positions(TorchRigidBodyWorld(2, 2, params.airframe, params.physics_dt_s, "cpu"), params,
                                    "cpu", r)
    a, b = replay(rec), replay(rec)
    c = replay({k: v for k, v in {**rec, "noise_seed": 6}.items() if k != "estimator"})
    assert torch.equal(a, b) and not torch.equal(a, c)


# ------------------------------------------------------------------------------------- hover with the error on (CPU)
def test_hover_with_exploratory_error_stays_close():
    """configs/ste_l1/model_check.toml [hover]: MADE-UP exploratory error values (position 0.02 m / 0.5 s, velocity
    0.02 m/s / 0.2 s, attitude 0.005 rad / 0.5 s; not drone values, L1.3 fits them) and bounds written before the first
    run: 20 s of hover, 64 drones, on the torch world."""
    h = check.load_settings()["hover"]
    p = check.hover_params(P1)
    assert (p.state_error_pos_m, p.state_error_pos_tau_s, p.state_delay_s, p.state_noise_pos_m) == (0.02, 0.5, 0.0, 0.0)
    res = check.hover_check(world(32, 2, p), p, ticks=400, device="cpu", seed=17)
    print("hover with error:", res)
    assert res["error_on"] == ["pos", "att", "vel"]
    assert res["rms_m"] <= h["rms_max_m"] and res["max_m"] <= h["max_m"], res
    assert res["max_tilt_rad"] <= h["tilt_max_rad"] and res["upsets"] == 0 and res["nonfinite"] == 0, res
