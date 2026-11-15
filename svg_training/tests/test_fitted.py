"""FittedResponse (models/fitted.py): the commander's teleop law, the safety filter per team, then PX4's response.

Checked against the NumPy reference ``px4_trajectory.simulate`` fed by the commander's own outputs; the placeholder
path of the tier 1 environment is checked bit for bit against a hash taken before this change. CPU only.
"""
import hashlib
import pathlib
import tomllib

import numpy as np
import pytest
import torch

from svg_training.core.safety_filter import team_pair_mask
from svg_training.envs.tier1_bench import Tier1BenchCfg, Tier1BenchEnv
from svg_training.models import px4_trajectory as px4
from svg_training.models.fitted import FittedResponse
from svg_training.models.placeholder import PlaceholderResponse

ROOT = pathlib.Path(__file__).resolve().parents[1]
PARAMS = ROOT / "params/real_exploratory_v0.toml"
CFG = tomllib.loads(PARAMS.read_text())
KEEP_OUT_M = 2.0 * CFG["filter"]["safety_radius_m"]          # 1.10 m centre to centre


def _sticks(seed, t_n, n, m):
    rng = np.random.default_rng(seed)
    out = np.zeros((t_n, n, m, 3))
    for g in range(n):
        for j in range(m):
            t = 0
            while t < t_n:
                span = int(rng.integers(3, 40))
                out[t:t + span, g, j] = 0.0 if rng.random() < 0.25 else rng.normal(0.0, 0.4, 3) * [1.0, 1.0, 0.3]
                t += span
    return out


@pytest.mark.parametrize("dtype", [torch.float64, torch.float32])
def test_matches_px4_trajectory_simulate_fed_by_the_commander(dtype):
    t_n, n, m = 160, 3, 2
    sticks = _sticks(7, t_n, n, m)
    start = np.random.default_rng(8).uniform(-2.0, 2.0, (n, m, 3))
    fr = FittedResponse(n, m, PARAMS, device="cpu", dtype=dtype, pos_m=torch.tensor(start, dtype=dtype))
    sp = np.zeros((3, t_n, n, m, 3))
    vel = np.zeros((t_n, n, m, 3))
    for t in range(t_n):
        vel[t] = fr.step(torch.tensor(sticks[t], dtype=dtype)).double().numpy()
        for k in range(3):
            sp[k, t] = fr.setpoint[k].double().numpy()
    sub = round(CFG["commander"]["tick_s"] / CFG["px4"]["model_dt_s"])
    params = px4.TrajectoryParams.from_dict({k: v for k, v in CFG["px4"].items() if k != "model_dt_s"})
    # the setpoint is held over the tick: repeat each one `sub` times on the fit's grid, plus one closing sample
    up = [np.concatenate([np.repeat(x, sub, axis=0), x[-1:]], axis=0)[..., :2] for x in sp]
    up = [np.moveaxis(x, 0, 2) for x in up]                                        # (n, m, T*sub+1, 2)
    v_ref, _p = px4.simulate(*up, CFG["px4"]["model_dt_s"], params, p0=start[..., :2], v0=np.zeros((n, m, 2)))
    v_ref_ticks = np.moveaxis(v_ref[:, :, sub::sub], 2, 0)                         # (T, n, m, 2): after each tick
    assert np.abs(vel[..., :2] - v_ref_ticks).max() <= 1e-5
    assert np.abs(vel[..., :2]).max() > 0.2                                        # the drones really moved


def test_vertical_channel_holds_height_and_respects_its_limits():
    fr = FittedResponse(1, 1, PARAMS, device="cpu", dtype=torch.float64, pos_m=torch.tensor([[[0.0, 0.0, 1.0]]]))
    for _ in range(40):
        v = fr.step(torch.zeros(1, 1, 3, dtype=torch.float64))
    assert v.abs().max() < 1e-12 and abs(fr.pos_m[0, 0, 2].item() - 1.0) < 1e-12
    vz = [fr.step(torch.tensor([[[0.0, 0.0, -0.5]]], dtype=torch.float64))[0, 0, 2].item() for _ in range(60)]
    assert min(vz) >= -CFG["px4_vertical"]["vel_max_down_mps"] - 1e-9
    assert abs(vz[-1] + 0.5) < 0.02                                                 # follows the 0.5 m/s descent


def _head_on(filter_on, iterations=1000, params=PARAMS, ticks=200):
    """Game 0: two Guard drones fly at each other. Game 1: a Guard and a Strike drone fly at each other."""
    pos = torch.tensor([[[-1.5, 0.0, 1.5], [1.5, 0.0, 1.5], [-1.5, 6.0, 1.5], [1.5, 6.0, 1.5]],
                        [[-1.5, 0.0, 1.5], [-1.5, -6.0, 1.5], [1.5, 0.0, 1.5], [1.5, 6.0, 1.5]]], dtype=torch.float64)
    stick = torch.zeros(2, 4, 3, dtype=torch.float64)
    stick[0, 0, 0], stick[0, 1, 0] = 0.5, -0.5
    stick[1, 0, 0], stick[1, 2, 0] = 0.5, -0.5
    fr = FittedResponse(2, 4, params, device="cpu", dtype=torch.float64, pos_m=pos, safety_filter=filter_on,
                        pair_mask=team_pair_mask(2, 2), filter_iterations=iterations)
    track, corrected = [], []
    for _ in range(ticks):                                                          # 0.05 s each
        fr.step(stick)
        track.append(fr.pos_m.clone())
        corrected.append(fr.corrected.clone())
    return torch.stack(track), torch.stack(corrected)


# The filter changes only the SPEED the commander sends. The position setpoint it also sends PX4 (the commander's
# reference point) is not filtered: after a correction it is held up to 0.2 m ahead of the drone (hold_lead_m), and
# PX4 keeps flying toward it at about Kp x 0.2 = 0.19 m/s. The commander says so itself (swarm_commander.py:2221-2228,
# "PX4's onboard pull toward the reference is not filtered"). So two Guard drones flown head-on come to 1.083 m,
# inside the 1.10 m keep-out (observed in the training simulator, 15 Nov 2026, v0 parameters, tick 88), then settle
# at 1.100 m. The drone's response only sets how far the reference runs ahead: no delay -> 1.037 m, no acceleration
# limit -> 0.90 m; with PX4's position gain 0 the pair keeps 1.1001 m (next test). This is observed behaviour of the
# copied commander, not a filter fault. 1.05 m is a regression bound for the v0 parameters only; a new parameter
# set may move the dip for physical reasons (task-8b-review.md I1).
FITTED_MIN_M = 1.05


def test_filter_keeps_same_team_apart_and_never_touches_a_cross_team_pair():
    track, corrected = _head_on(True)
    guards = (track[:, 0, 0] - track[:, 0, 1]).norm(dim=-1)
    assert guards.min() >= FITTED_MIN_M                                             # same team: kept apart
    assert guards[-1] >= KEEP_OUT_M - 2e-3                                          # and settles at the keep-out
    assert corrected[:, 0, :2].any()                                                # ... by the filter
    assert not corrected[:, 1].any()                                                # Guard-Strike: never corrected
    cross = (track[:, 1, 0] - track[:, 1, 2]).norm(dim=-1)
    assert cross.min() < 0.5                                                        # they really meet (contact)
    free, _ = _head_on(False)
    assert torch.equal(track[:, 1], free[:, 1])                                     # identical to the filter off
    assert (free[:, 0, 0] - free[:, 0, 1]).norm(dim=-1).min() < 0.5                 # without it the Guards meet


def test_without_the_pull_to_the_position_setpoint_the_keep_out_holds():
    """The same head-on run with PX4's position gain set to 0: the drone flies only the filtered speed, and the pair
    stays outside the keep-out to the filter's tolerance. This isolates the cause of the dip above."""
    no_pull = tomllib.loads(PARAMS.read_text())
    no_pull["px4"]["kp_xy"] = 0.0
    track, _c = _head_on(True, params=no_pull)
    assert (track[:, 0, 0] - track[:, 0, 1]).norm(dim=-1).min() >= 1.0999


def test_nan_in_one_game_leaves_the_others_unchanged():
    n, m = 4, 4
    sticks = torch.tensor(_sticks(3, 60, n, m))
    start = torch.tensor(np.random.default_rng(4).uniform(-1.5, 1.5, (n, m, 3)))

    def run(poison):
        fr = FittedResponse(n, m, PARAMS, device="cpu", dtype=torch.float64, pos_m=start.clone(), safety_filter=True,
                            pair_mask=team_pair_mask(2, 2), filter_iterations=200)
        out = []
        for t in range(60):
            s = sticks[t].clone()
            if poison and t == 10:
                s[1, 0] = float("nan")
            out.append(torch.cat([fr.step(s), fr.pos_m], dim=-1).clone())
        return torch.stack(out)

    clean, bad = run(False), run(True)
    keep = [0, 2, 3]
    assert torch.equal(clean[:, keep], bad[:, keep])
    assert not torch.equal(clean[:, 1], bad[:, 1])                                  # game 1 did change


def test_reset_seeds_the_drone_at_its_new_position():
    fr = FittedResponse(2, 1, PARAMS, device="cpu", dtype=torch.float64)
    for _ in range(20):
        fr.step(torch.tensor([[[0.5, 0.0, 0.0]], [[0.5, 0.0, 0.0]]], dtype=torch.float64))
    new = torch.tensor([[[5.0, 5.0, 2.0]], [[9.0, 9.0, 9.0]]], dtype=torch.float64)
    fr.reset(torch.tensor([[True], [False]]), new)
    assert torch.equal(fr.pos_m[0, 0], new[0, 0]) and fr.vel_mps[0, 0].abs().max() == 0.0
    assert fr.vel_mps[1, 0, 0] > 0.1 and fr.pos_m[1, 0, 0] < 9.0                    # game 1 kept its state
    v = fr.step(torch.zeros(2, 1, 3, dtype=torch.float64))
    assert v[0, 0].abs().max() == 0.0 and torch.equal(fr.setpoint[0][0, 0], new[0, 0])   # holds where it was put


# ------------------------------------------------------------------------------------------- tier 1 environment
# Hash of 40 steps of the placeholder environment, taken with the code BEFORE this change (CPU, torch 2.7.0,
# env_isaaclab, 15 November 2026). The placeholder path must stay bit-identical.
PLACEHOLDER_SHA = "be8c01de04849c7a13662369178c768358eefd770a37e5cafb5e7cddfba94617"


def _placeholder_hash(**extra):
    e = Tier1BenchEnv(Tier1BenchCfg(num_games=32, guards=2, strikes=2, world="primitives", n_obstacles=12, n_rays=8,
                                    line_of_sight=True, seed=5, device="cpu", **extra))
    g = torch.Generator().manual_seed(11)
    h = hashlib.sha256()
    for _ in range(40):
        o = e.step(torch.rand(32, 4, 4, generator=g) * 2 - 1)
        for k in ("pos_m", "vel_mps", "ranges_m", "visible", "tagged", "touched"):
            h.update(o[k].contiguous().numpy().tobytes())
    return e, h.hexdigest()


def test_placeholder_path_is_bit_identical():
    e, digest = _placeholder_hash()
    assert isinstance(e.response, PlaceholderResponse) and digest == PLACEHOLDER_SHA
    _e, digest = _placeholder_hash(response="placeholder", safety_filter=False)
    assert digest == PLACEHOLDER_SHA


def _env(**kw):
    base = dict(num_games=16, guards=2, strikes=1, world="primitives", n_obstacles=6, n_rays=8, line_of_sight=True,
                device="cpu", response=str(PARAMS))
    return Tier1BenchEnv(Tier1BenchCfg(**{**base, **kw}))


@pytest.mark.parametrize("filter_on", [False, True])
def test_env_runs_with_the_fitted_response(filter_on):
    e = _env(safety_filter=filter_on, filter_iterations=50)
    assert isinstance(e.response, FittedResponse)
    for _ in range(30):
        o = e.step(torch.rand(16, 3, 4) * 2 - 1)
    assert all(torch.isfinite(o[k]).all() for k in ("pos_m", "vel_mps", "ranges_m"))
    assert o["vel_mps"].norm(dim=-1).max() < 1.0                                    # real-config speeds


def test_env_fitted_path_follows_positions_written_by_the_caller():
    e = _env(num_games=2, world="open", n_obstacles=0, n_rays=0, line_of_sight=False)
    e.pos_m[:] = torch.tensor([[0.0, 0, 2], [5.0, 0, 2], [0.49, 0, 2]])
    assert e.step(torch.zeros(2, 3, 4))["tagged"].tolist() == [[True, False, True]] * 2


def test_env_caps_each_teams_command_norm_before_the_commander():
    """STANDARDS §4: Strike drones at strike_speed_mps, Guard drones at it / 1.5, on the command's NORM."""
    e = _env(num_games=2, guards=1, strikes=1, world="open", n_obstacles=0, n_rays=0, line_of_sight=False)
    far = torch.tensor([[-10.0, 0, 4], [10.0, 0, 4]])
    for _ in range(30):
        e.pos_m[:] = far                                     # hold them apart: no contact, no wall
        e.step(torch.tensor([1.0, 1.0, 1.0, 0.0]).expand(2, 2, 4))   # full diagonal command
    v_ff = e.response.setpoint[1].norm(dim=-1)               # the speed the commander sends PX4
    assert (v_ff[:, 0] <= 0.5 / 1.5 + 1e-6).all() and (v_ff[:, 0] > 0.5 / 1.5 - 1e-4).all()
    assert (v_ff[:, 1] <= 0.5 + 1e-6).all() and (v_ff[:, 1] > 0.5 - 1e-4).all()


def test_env_refuses_a_strike_speed_above_the_commanders_cap():
    with pytest.raises(ValueError):
        _env(strike_speed_mps=0.6)


def test_env_filter_needs_the_fitted_response():
    with pytest.raises(ValueError):
        _env(response="placeholder", safety_filter=True)
