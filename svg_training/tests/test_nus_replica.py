"""Tests of the partner-game replica. Unit tests use made-up marker rules from a temporary local file (no partner value is
needed). The parity test compares with recorded runs of the partner's environment and is skipped unless the fixtures and the
local rules files exist (scripts/nus_make_local_rules.py, scripts/nus_record_fixtures.py; both under git-ignored paths)."""
import json
import math

import numpy as np
import pytest
import torch

from _nus_markers import ROOT, marker_rules, write_toml
from svg_training.nus import rules as rules_mod
from svg_training.nus.replica import NusReplica, ReplicaState

F32 = torch.float32
POS_TOL = 1e-4  # test tolerance (not a partner value): units, float32


@pytest.fixture(scope="module")
def rules(tmp_path_factory):
    path = tmp_path_factory.mktemp("rules") / "nus_rules.toml"
    write_toml(path, marker_rules())
    return rules_mod.load_rules(path)


@pytest.fixture(scope="module")
def sim(rules):
    return NusReplica(rules)


def state_of(sim, pos_rows, prev_rows=None, reached=0.0, step=0):
    pos = torch.tensor(pos_rows, dtype=F32)
    n = pos.shape[0]
    prev = pos.clone() if prev_rows is None else torch.tensor(prev_rows, dtype=F32)
    return ReplicaState(pos, prev, torch.full((n,), float(reached)), torch.full((n,), step, dtype=torch.long))


def softplus(x):
    return math.log1p(math.exp(x))


def far_layout(sim, rules):
    """One game: Guards close to the zone centre on a short line, Strikes far away; nothing within any push radius."""
    spread = 3 * rules.agent_size + rules.guard_safety_distance
    guards = [[0.0, k * spread] for k in range(sim.guard_count)]
    strikes = [[rules.spawn_distance, k * spread] for k in range(sim.strike_count)]
    return [guards + strikes]


def test_per_team_cap_scales_a_large_request_to_the_team_limit(sim, rules):
    s = state_of(sim, far_layout(sim, rules))
    big = torch.full((1, sim.num_actors, 2), 1 + 2 * (rules.guard_max_speed + rules.strike_max_speed))
    moved = (sim.step(s, big).pos - s.pos).norm(dim=-1)[0]
    assert torch.allclose(moved[: sim.guard_count], torch.tensor(rules.guard_max_speed), atol=1e-6)
    assert torch.allclose(moved[sim.guard_count:], torch.tensor(rules.strike_max_speed), atol=1e-6)


def test_a_small_request_is_not_scaled(sim, rules):
    s = state_of(sim, far_layout(sim, rules))
    small = torch.zeros(1, sim.num_actors, 2)
    small[0, 0, 0] = rules.guard_max_speed / 2
    assert sim.step(s, small).pos[0, 0, 0] - s.pos[0, 0, 0] == pytest.approx(rules.guard_max_speed / 2, abs=1e-6)


def test_push_uses_the_opponent_teams_radius_and_pushes_both_ways(sim, rules):
    r_guard_team = 2 * rules.agent_size + rules.guard_safety_distance  # radius around a Guard
    r_strike_team = 2 * rules.agent_size + rules.strike_safety_distance  # radius around a Strike
    assert r_guard_team != r_strike_team
    d = (r_guard_team + r_strike_team) / 2
    rows = far_layout(sim, rules)
    rows[0][0] = [0.0, 0.0]
    rows[0][sim.guard_count] = [d, 0.0]
    s = state_of(sim, rows)
    zero = torch.zeros(1, sim.num_actors, 2)
    moved = sim.step(s, zero).pos - s.pos
    m, k = rules.push_smoothing_margin, rules.push_gain
    # the Guard is pushed by the Strike's radius; the Strike by the Guard's radius
    guard_push = k * m * softplus((r_strike_team - d) / m)
    strike_push = k * m * softplus((r_guard_team - d) / m)
    assert moved[0, 0, 0].item() == pytest.approx(-guard_push, rel=1e-3, abs=1e-6)
    assert moved[0, sim.guard_count, 0].item() == pytest.approx(strike_push, rel=1e-3)
    assert moved[0, 0, 1].abs().item() < 1e-6 and strike_push > guard_push
    # everybody else did not move
    others = [i for i in range(sim.num_actors) if i not in (0, sim.guard_count)]
    assert moved[0, others].abs().max() < 1e-6


def test_same_team_overlap_is_allowed(sim, rules):
    rows = far_layout(sim, rules)
    rows[0][1] = list(rows[0][0])
    s = state_of(sim, rows)
    moved = sim.step(s, torch.zeros(1, sim.num_actors, 2)).pos - s.pos
    assert moved.abs().max() < 1e-6


def test_total_displacement_cap_limits_choice_plus_push(sim, rules):
    rows = far_layout(sim, rules)
    rows[0][sim.guard_count] = [rules.agent_size / 2, 0.0]  # a Strike almost on top of Guard 0
    rows[0][0] = [0.0, 0.0]
    s = state_of(sim, rows)
    moved = (sim.step(s, torch.zeros(1, sim.num_actors, 2)).pos - s.pos).norm(dim=-1)[0]
    assert moved[0].item() == pytest.approx(rules.total_displacement_cap, rel=1e-5)
    assert moved[sim.guard_count].item() == pytest.approx(rules.total_displacement_cap, rel=1e-5)


def test_coincident_tentative_positions_fall_back_to_the_current_direction(sim, rules):
    rows = far_layout(sim, rules)
    gap = rules.guard_max_speed / 2
    rows[0][0] = [0.0, 0.0]
    rows[0][sim.guard_count] = [gap, 0.0]
    s = state_of(sim, rows)
    act = torch.zeros(1, sim.num_actors, 2)
    act[0, 0, 0] = gap  # the Guard walks onto the Strike's spot
    moved = sim.step(s, act).pos - s.pos
    assert moved[0, 0, 0] < 0 < moved[0, sim.guard_count, 0]  # pushed apart along the old line
    assert moved[0, 0].norm().item() == pytest.approx(rules.total_displacement_cap, rel=1e-5)


def test_guard_boundary_pushes_a_guard_inward_and_not_a_strike(sim, rules):
    r = rules.guard_boundary_radius
    rows = far_layout(sim, rules)
    rows[0][0] = [r, 0.0]
    rows[0][sim.guard_count] = [-r, 0.0]
    s = state_of(sim, rows)
    moved = sim.step(s, torch.zeros(1, sim.num_actors, 2)).pos - s.pos
    trigger = r - rules.boundary_margin
    m = rules.push_smoothing_margin
    expect = rules.push_gain * m * softplus((r - trigger) / m)
    assert moved[0, 0, 0].item() == pytest.approx(-expect, rel=1e-3)
    assert moved[0, sim.guard_count].abs().max() < 1e-6  # a Strike is not held by the boundary
    inner = state_of(sim, far_layout(sim, rules))
    assert (sim.step(inner, torch.zeros(1, sim.num_actors, 2)).pos - inner.pos).abs().max() < 1e-6


def test_reached_flag_latches_and_stays(sim, rules):
    safe_y = -2 * rules.area_radius
    guards = [[0.0, safe_y]] * sim.guard_count
    inside = [[rules.area_radius + rules.strike_max_speed / 2, 0.0]] + [[rules.spawn_distance, 0.0]] * (sim.strike_count - 1)
    outside = [[rules.spawn_distance, 0.0]] * sim.strike_count
    s = state_of(sim, [guards + inside, guards + outside])
    toward = torch.zeros(2, sim.num_actors, 2)
    toward[:, sim.guard_count, 0] = -rules.strike_max_speed
    s1 = sim.step(s, toward)
    assert s1.reached.tolist() == [1.0, 0.0]
    away = torch.zeros(2, sim.num_actors, 2)
    away[:, sim.guard_count, 0] = rules.strike_max_speed
    s2 = sim.step(sim.step(s1, away), away)
    assert s2.reached.tolist() == [1.0, 0.0]
    assert s2.step.tolist() == [3, 3] and torch.equal(s1.pos, sim.step(s, toward).pos)


def test_episode_is_done_after_the_fixed_length(sim, rules):
    s = state_of(sim, far_layout(sim, rules), step=rules.episode_steps - 1)
    assert not sim.done(s).any()
    assert sim.done(sim.step(s, torch.zeros(1, sim.num_actors, 2))).all()


def test_games_in_a_batch_do_not_affect_each_other(sim, rules):
    gen = torch.Generator().manual_seed(1)
    s = sim.reset(5, generator=gen)
    s = sim.step(s, torch.randn(5, sim.num_actors, 2, generator=gen))
    act = torch.randn(5, sim.num_actors, 2, generator=gen)
    both = sim.step(s, act)
    for i in range(5):
        one = sim.step(ReplicaState(s.pos[i:i + 1], s.prev_pos[i:i + 1], s.reached[i:i + 1], s.step[i:i + 1]), act[i:i + 1])
        assert torch.allclose(one.pos, both.pos[i:i + 1], atol=1e-6)
        assert torch.allclose(sim.observe(one), sim.observe(both)[i:i + 1], atol=1e-6)


def test_random_start_follows_the_start_rule(sim, rules):
    s = sim.reset(400, generator=torch.Generator().manual_seed(3))
    guards, strikes = s.pos[:, : sim.guard_count], s.pos[:, sim.guard_count:]
    assert guards.norm(dim=-1).max() <= rules.start_guard_disc_fraction * rules.area_radius + 1e-5
    assert torch.allclose(strikes.norm(dim=-1), torch.tensor(rules.spawn_distance), atol=1e-4)
    # radius is uniform (not the area): the mean is half the maximum
    assert guards.norm(dim=-1).mean().item() == pytest.approx(rules.start_guard_disc_fraction * rules.area_radius / 2, rel=0.1)
    assert torch.equal(s.pos, s.prev_pos) and s.reached.sum() == 0 and s.step.sum() == 0
    assert not torch.allclose(s.pos[0], s.pos[1])


def test_fixed_layout_start(sim, rules):
    s = sim.reset(2, random_start=False)
    assert torch.equal(s.pos[0], s.pos[1])
    g, k = sim.guard_count, sim.strike_count
    ang = 2 * math.pi * torch.arange(g) / g
    want = rules.start_static_guard_ring_fraction * rules.area_radius * torch.stack((ang.cos(), ang.sin()), dim=-1)
    assert torch.allclose(s.pos[0, :g], want, atol=1e-5)
    sang = 2 * math.pi * torch.arange(k) / k
    want_s = torch.tensor([rules.spawn_distance, 0.0]) + rules.start_static_strike_cluster_fraction * rules.spawn_cluster_radius * torch.stack((sang.cos(), sang.sin()), dim=-1)
    assert torch.allclose(s.pos[0, g:], want_s, atol=1e-5)


def _phi(v, floor):
    n = np.linalg.norm(v)
    return [*(v / n if n > floor else np.zeros(2)), n]


def test_observation_layout(sim, rules):
    gen = torch.Generator().manual_seed(5)
    s = sim.reset(3, generator=gen)
    s = sim.step(s, torch.randn(3, sim.num_actors, 2, generator=gen))
    s.pos[2, 0] = 0.0  # a drone exactly at the zone centre, no step: unit direction must be zero
    s.prev_pos[2, 0] = 0.0
    s.reached[1] = 1.0
    obs = sim.observe(s).numpy()
    g, k, m = sim.guard_count, sim.strike_count, sim.num_actors
    assert obs.shape == (3, m, 9 * m + 2)
    orders = {0: [0, 1, 2, 3, 4], 1: [1, 2, 0, 3, 4], 2: [2, 0, 1, 3, 4], 3: [3, 4, 0, 1, 2], 4: [4, 3, 0, 1, 2]}
    assert (g, k) == (3, 2)
    floor = rules.obs_direction_floor
    pos, prev = s.pos.numpy(), s.prev_pos.numpy()
    for game in range(3):
        feat = [[*_phi(pos[game, a], floor), *_phi(prev[game, a], floor), *_phi(pos[game, a] - prev[game, a], floor)] for a in range(m)]
        for actor, order in orders.items():
            want = np.concatenate([feat[a] for a in order] + [[rules.area_radius, s.reached[game].item()]])
            np.testing.assert_allclose(obs[game, actor], want, atol=1e-5)
    assert obs[2, 0, :3].tolist() == [0.0, 0.0, 0.0]


# ---------------------------------------------------------------- parity with recordings of the partner's environment
FIX_DIR = rules_mod.FIXTURE_DIR
CASES = {"3v3": "nus_rules.toml", "3v3_static": "nus_rules.toml", "5v3": "nus_rules_5v3.toml",
         # Phase 2 gate of record (configs/nus_port.toml [gates.phase2_replica_parity]): 100 recorded episodes each
         "gate_3v3": "nus_rules.toml", "gate_5v3": "nus_rules_5v3.toml"}
MIN_COVERAGE = ("steps_with_push", "steps_with_team_cap", "steps_with_total_cap", "steps_with_boundary", "steps_with_flag_flip")


def _obs_errors(ours, theirs, m, direction_check_above=0.1):
    """Largest observation error. The unit direction of a near-zero vector is ill-conditioned in float32 (a rounding step
    of a position turns into a large angle), so each [direction, magnitude] block is compared as the magnitude and as the
    vector direction x magnitude; the direction alone is compared where the vector is longer than `direction_check_above`
    units. The last two entries (zone radius, reached flag) are compared exactly in the same pass."""
    a, b = ours[..., :-2].reshape(*ours.shape[:-1], -1, 3), theirs[..., :-2].reshape(*theirs.shape[:-1], -1, 3)
    vec_a, vec_b = a[..., :2] * a[..., 2:], b[..., :2] * b[..., 2:]
    err = max((a[..., 2] - b[..., 2]).abs().max().item(), (vec_a - vec_b).abs().max().item(), (ours[..., -2:] - theirs[..., -2:]).abs().max().item())
    long = b[..., 2] > direction_check_above
    dir_err = (a[..., :2] - b[..., :2]).abs().amax(dim=-1)[long].max().item()
    return err, dir_err


@pytest.mark.parametrize("tag", list(CASES))
def test_per_step_parity_with_the_partner_environment(tag):
    npz, js, local = FIX_DIR / f"{tag}.npz", FIX_DIR / f"{tag}.json", rules_mod.ROOT / "configs/local" / CASES[tag]
    if not (npz.exists() and js.exists() and local.exists()):
        pytest.skip("fixtures or local rules file absent (scripts/nus_make_local_rules.py, scripts/nus_record_fixtures.py)")
    cov = json.loads(js.read_text())
    for key in MIN_COVERAGE:
        assert cov[key] > 0, f"fixture {tag} has no steps for {key}"
    rules = rules_mod.load_rules(local)
    sim = NusReplica(rules)
    d = np.load(npz)
    e, t1, m = d["pos"].shape[:3]
    steps = t1 - 1

    def flat(a):
        return torch.from_numpy(np.ascontiguousarray(a)).reshape(e * steps, *a.shape[2:])

    state = ReplicaState(
        pos=flat(d["pos"][:, :-1]), prev_pos=flat(d["prev_pos"][:, :-1]), reached=flat(d["breach"][:, :-1]),
        step=flat(d["step"][:, :-1]).long(),
    )
    out = sim.step(state, flat(d["actions"]))
    obs = sim.observe(out)
    pos_err = (out.pos - flat(d["pos"][:, 1:])).abs().max().item()
    prev_err = (out.prev_pos - flat(d["prev_pos"][:, 1:])).abs().max().item()
    obs_err, dir_err = _obs_errors(obs, flat(d["obs"][:, 1:]), m)
    flag_ok = torch.equal(out.reached, flat(d["breach"][:, 1:])) and torch.equal(out.step, flat(d["step"][:, 1:]).long())
    print(f"\n[parity {tag}] per-step max |pos err|={pos_err:.3e}  |prev err|={prev_err:.3e}  |obs err|={obs_err:.3e} (direction where |v|>0.1: {dir_err:.3e})  "
          f"flag/step equal={flag_ok}  coverage: push={cov['steps_with_push']} team_cap={cov['steps_with_team_cap']} "
          f"total_cap={cov['steps_with_total_cap']} boundary={cov['steps_with_boundary']} flip={cov['steps_with_flag_flip']}")

    # open loop: the replica's own state from the recorded start, recorded actions only (information, not asserted)
    cur = ReplicaState(torch.from_numpy(d["pos"][:, 0]), torch.from_numpy(d["prev_pos"][:, 0]), torch.from_numpy(d["breach"][:, 0]),
                       torch.from_numpy(d["step"][:, 0]).long())
    acts = torch.from_numpy(d["actions"])
    drift = []
    first_flag_replica = torch.full((e,), -1)
    for t in range(steps):
        cur = sim.step(cur, acts[:, t])
        drift.append((cur.pos - torch.from_numpy(d["pos"][:, t + 1])).abs().amax(dim=(1, 2)))
        newly = (cur.reached > 0) & (first_flag_replica < 0)
        first_flag_replica[newly] = t + 1
    drift = torch.stack(drift, dim=1)
    flag_steps = np.where(d["breach"].max(axis=1) > 0, d["breach"].argmax(axis=1), -1)
    print(f"[open-loop {tag}] max drift over episode={drift.max().item():.3e}  at last step={drift[:, -1].max().item():.3e}  "
          f"episodes within tolerance={int((drift.amax(dim=1) <= POS_TOL).sum())}/{e}  "
          f"first-reached step equal in {int((first_flag_replica.numpy() == flag_steps).sum())}/{e}")

    assert pos_err <= POS_TOL and prev_err <= POS_TOL and flag_ok
    assert obs_err <= POS_TOL and dir_err <= POS_TOL, f"observation error {obs_err:.3e}, direction {dir_err:.3e}"
    # starts: the fixed layout is deterministic; random starts must satisfy the start rule
    if tag.endswith("static"):
        torch.testing.assert_close(sim.reset(1, random_start=False).pos[0], torch.from_numpy(d["pos"][0, 0]), atol=POS_TOL, rtol=0)
    else:
        g = d["pos"][:, 0, : rules.guard_count]
        assert np.linalg.norm(g, axis=-1).max() <= rules.start_guard_disc_fraction * rules.area_radius + POS_TOL
        np.testing.assert_allclose(np.linalg.norm(d["pos"][:, 0, rules.guard_count:], axis=-1), rules.spawn_distance, atol=POS_TOL)
