"""Tests of the partner-game replica. Unit tests use made-up marker rules from a temporary local file (no partner value is
needed). The parity test compares with recorded runs of the partner's environment and is skipped unless the fixtures and the
local rules files exist (scripts/nus_make_local_rules.py, scripts/nus_record_fixtures.py; both under git-ignored paths)."""
import json
import math

import numpy as np
import pytest
import torch

from _nus_markers import (obs_errors, OBS_PER_DRONE, OBS_TAIL, PHI_WIDTH, SEED_B, SEED_C, SHAPE_HEAD, BATCH, DIRECTION_MIN, FIXED_LAYOUT_ORDERS, GUARDS, OBS_GAMES, POS_TOL, REL_LOOSE, REL_MID, REL_WIDE,
                          SPREAD_FACTOR, START_GAMES, STEPS_AFTER_LATCH, STRIKES, TOL_LOOSE, TOL_TIGHT, ROOT, marker_rules, write_toml)
from svg_training.nus import rules as rules_mod
from svg_training.nus.replica import NusReplica, ReplicaState

F32 = torch.float32


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
    spread = SPREAD_FACTOR * rules.agent_size + rules.guard_safety_distance
    guards = [[0.0, k * spread] for k in range(sim.guard_count)]
    strikes = [[rules.spawn_distance, k * spread] for k in range(sim.strike_count)]
    return [guards + strikes]


def test_per_team_cap_scales_a_large_request_to_the_team_limit(sim, rules):
    s = state_of(sim, far_layout(sim, rules))
    big = torch.full((1, sim.num_actors, 2), 1 + 2 * (rules.guard_max_speed + rules.strike_max_speed))
    moved = (sim.step(s, big).pos - s.pos).norm(dim=-1)[0]
    assert torch.allclose(moved[: sim.guard_count], torch.tensor(rules.guard_max_speed), atol=TOL_TIGHT)
    assert torch.allclose(moved[sim.guard_count:], torch.tensor(rules.strike_max_speed), atol=TOL_TIGHT)


def test_a_small_request_is_not_scaled(sim, rules):
    s = state_of(sim, far_layout(sim, rules))
    small = torch.zeros(1, sim.num_actors, 2)
    small[0, 0, 0] = rules.guard_max_speed / 2
    assert sim.step(s, small).pos[0, 0, 0] - s.pos[0, 0, 0] == pytest.approx(rules.guard_max_speed / 2, abs=TOL_TIGHT)


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
    assert moved[0, 0, 0].item() == pytest.approx(-guard_push, rel=REL_LOOSE, abs=TOL_TIGHT)
    assert moved[0, sim.guard_count, 0].item() == pytest.approx(strike_push, rel=REL_LOOSE)
    assert moved[0, 0, 1].abs().item() < TOL_TIGHT and strike_push > guard_push
    # everybody else did not move
    others = [i for i in range(sim.num_actors) if i not in (0, sim.guard_count)]
    assert moved[0, others].abs().max() < TOL_TIGHT


def test_same_team_overlap_is_allowed(sim, rules):
    rows = far_layout(sim, rules)
    rows[0][1] = list(rows[0][0])
    s = state_of(sim, rows)
    moved = sim.step(s, torch.zeros(1, sim.num_actors, 2)).pos - s.pos
    assert moved.abs().max() < TOL_TIGHT


def test_total_displacement_cap_limits_choice_plus_push(sim, rules):
    rows = far_layout(sim, rules)
    rows[0][sim.guard_count] = [rules.agent_size / 2, 0.0]  # a Strike almost on top of Guard 0
    rows[0][0] = [0.0, 0.0]
    s = state_of(sim, rows)
    moved = (sim.step(s, torch.zeros(1, sim.num_actors, 2)).pos - s.pos).norm(dim=-1)[0]
    assert moved[0].item() == pytest.approx(rules.total_displacement_cap, rel=REL_MID)
    assert moved[sim.guard_count].item() == pytest.approx(rules.total_displacement_cap, rel=REL_MID)


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
    assert moved[0, 0].norm().item() == pytest.approx(rules.total_displacement_cap, rel=REL_MID)


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
    assert moved[0, 0, 0].item() == pytest.approx(-expect, rel=REL_LOOSE)
    assert moved[0, sim.guard_count].abs().max() < TOL_TIGHT  # a Strike is not held by the boundary
    inner = state_of(sim, far_layout(sim, rules))
    assert (sim.step(inner, torch.zeros(1, sim.num_actors, 2)).pos - inner.pos).abs().max() < TOL_TIGHT


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
    assert s2.step.tolist() == [STEPS_AFTER_LATCH] * 2 and torch.equal(s1.pos, sim.step(s, toward).pos)


def test_episode_is_done_after_the_fixed_length(sim, rules):
    s = state_of(sim, far_layout(sim, rules), step=rules.episode_steps - 1)
    assert not sim.done(s).any()
    assert sim.done(sim.step(s, torch.zeros(1, sim.num_actors, 2))).all()


def test_games_in_a_batch_do_not_affect_each_other(sim, rules):
    gen = torch.Generator().manual_seed(1)
    s = sim.reset(BATCH, generator=gen)
    s = sim.step(s, torch.randn(BATCH, sim.num_actors, 2, generator=gen))
    act = torch.randn(BATCH, sim.num_actors, 2, generator=gen)
    both = sim.step(s, act)
    for i in range(BATCH):
        one = sim.step(ReplicaState(s.pos[i:i + 1], s.prev_pos[i:i + 1], s.reached[i:i + 1], s.step[i:i + 1]), act[i:i + 1])
        assert torch.allclose(one.pos, both.pos[i:i + 1], atol=TOL_TIGHT)
        assert torch.allclose(sim.observe(one), sim.observe(both)[i:i + 1], atol=TOL_TIGHT)


def test_random_start_follows_the_start_rule(sim, rules):
    s = sim.reset(START_GAMES, generator=torch.Generator().manual_seed(SEED_B))
    guards, strikes = s.pos[:, : sim.guard_count], s.pos[:, sim.guard_count:]
    assert guards.norm(dim=-1).max() <= rules.start_guard_disc_fraction * rules.area_radius + TOL_LOOSE
    assert torch.allclose(strikes.norm(dim=-1), torch.tensor(rules.spawn_distance), atol=POS_TOL)
    # radius is uniform (not the area): the mean is half the maximum
    assert guards.norm(dim=-1).mean().item() == pytest.approx(rules.start_guard_disc_fraction * rules.area_radius / 2, rel=REL_WIDE)
    assert torch.equal(s.pos, s.prev_pos) and s.reached.sum() == 0 and s.step.sum() == 0
    assert not torch.allclose(s.pos[0], s.pos[1])


def test_fixed_layout_start(sim, rules):
    s = sim.reset(2, random_start=False)
    assert torch.equal(s.pos[0], s.pos[1])
    g, k = sim.guard_count, sim.strike_count
    ang = 2 * math.pi * torch.arange(g) / g
    want = rules.start_static_guard_ring_fraction * rules.area_radius * torch.stack((ang.cos(), ang.sin()), dim=-1)
    assert torch.allclose(s.pos[0, :g], want, atol=TOL_LOOSE)
    sang = 2 * math.pi * torch.arange(k) / k
    want_s = torch.tensor([rules.spawn_distance, 0.0]) + rules.start_static_strike_cluster_fraction * rules.spawn_cluster_radius * torch.stack((sang.cos(), sang.sin()), dim=-1)
    assert torch.allclose(s.pos[0, g:], want_s, atol=TOL_LOOSE)


def _phi(v, floor):
    n = np.linalg.norm(v)
    return [*(v / n if n > floor else np.zeros(2)), n]


def test_observation_layout(sim, rules):
    gen = torch.Generator().manual_seed(SEED_C)
    s = sim.reset(OBS_GAMES, generator=gen)
    s = sim.step(s, torch.randn(OBS_GAMES, sim.num_actors, 2, generator=gen))
    s.pos[2, 0] = 0.0  # a drone exactly at the zone centre, no step: unit direction must be zero
    s.prev_pos[2, 0] = 0.0
    s.reached[1] = 1.0
    obs = sim.observe(s).numpy()
    g, k, m = sim.guard_count, sim.strike_count, sim.num_actors
    assert obs.shape == (OBS_GAMES, m, OBS_PER_DRONE * m + OBS_TAIL)
    orders = FIXED_LAYOUT_ORDERS
    assert (g, k) == (GUARDS, STRIKES)
    floor = rules.obs_direction_floor
    pos, prev = s.pos.numpy(), s.prev_pos.numpy()
    for game in range(OBS_GAMES):
        feat = [[*_phi(pos[game, a], floor), *_phi(prev[game, a], floor), *_phi(pos[game, a] - prev[game, a], floor)] for a in range(m)]
        for actor, order in orders.items():
            want = np.concatenate([feat[a] for a in order] + [[rules.area_radius, s.reached[game].item()]])
            np.testing.assert_allclose(obs[game, actor], want, atol=TOL_LOOSE)
    assert obs[2, 0, :PHI_WIDTH].tolist() == [0.0, 0.0, 0.0]


# ---------------------------------------------------------------- parity with recordings of the partner's environment
FIX_DIR = rules_mod.FIXTURE_DIR
CASES = {"3v3": "nus_rules.toml", "3v3_static": "nus_rules.toml", "5v3": "nus_rules_5v3.toml",
         # Phase 2 gate of record (configs/nus_port.toml [gates.phase2_replica_parity]): 100 recorded episodes each
         "gate_3v3": "nus_rules.toml", "gate_5v3": "nus_rules_5v3.toml"}
MIN_COVERAGE = ("steps_with_push", "steps_with_team_cap", "steps_with_total_cap", "steps_with_boundary", "steps_with_flag_flip")


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
    e, t1, m = d["pos"].shape[:SHAPE_HEAD]
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
    obs_err, dir_err = obs_errors(obs, flat(d["obs"][:, 1:]), m)
    flag_ok = torch.equal(out.reached, flat(d["breach"][:, 1:])) and torch.equal(out.step, flat(d["step"][:, 1:]).long())
    print(f"\n[parity {tag}] per-step max |pos err|={pos_err:.3e}  |prev err|={prev_err:.3e}  |obs err|={obs_err:.3e} (direction where |v| is above the direction threshold: {dir_err:.3e})  "
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
