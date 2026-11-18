"""Phase 5 task M5: the 5.1 statistics on synthetic numbers (nus/crossplay.py): the frozen gate, the intervals and the SD floor, the
spread ratio, 5.1-b's same-team runs, 5.1-c and its leave-one-out check, 5.1-d's leave-one-out panels with a failed conversion, and the
verdict order. Every number lives in tests/_nus_phase5_method_fixture.py (G2)."""
import math

import pytest

from _nus_phase5_method_fixture import (APF_OUTSIDE, B_PATTERNS, FLOOR_CASE, FLOOR_FAIL_CASE, FOUR_SEEDS, FROZEN_GATE, GAMES,
                                        GUARD_STRENGTH, LAST_MOVER_ALL, LAST_MOVER_NONE, OURS, PANEL_FAILED, PANEL_HOLD, PANEL_MEANS,
                                        PANEL_VALUE, POOLED_CASE, POOLED_OVER_ENTRIES, REF, SHUTOUT_MARGIN, SIX, STRIKE_STRENGTH, TOL,
                                        WELCH_CASE, WIDE_CASE, WORST_FAIL, WORST_PASS, copy_strengths, own_pools, synthetic_crossplay)
from svg_training.nus import crossplay as X


@pytest.fixture(scope="module")
def gate():
    return X.load_gate()


def test_gate_is_the_frozen_table(gate):
    for key, value in FROZEN_GATE.items():
        assert getattr(gate, key) == value, key
    assert gate.status.startswith("FROZEN") and set(gate.d_statistics) == set(X.STATISTIC_TEAM)


def test_pooled_t_interval_hand_values(gate):
    r = X.pooled_t_interval(POOLED_CASE["ours"], POOLED_CASE["reference"], gate.t_quantile, gate.sd_floor)
    for key in ("diff", "low", "high", "spread_ratio"):
        assert r[key] == pytest.approx(POOLED_CASE[key], abs=TOL), key
    assert r["contains_zero"] and r["df"] == len(POOLED_CASE["ours"]) * 2 - 2


def test_pooled_refuses_another_seed_count(gate):
    with pytest.raises(ValueError, match="3 v 3"):
        X.pooled_t_interval(FOUR_SEEDS, POOLED_CASE["reference"], gate.t_quantile, gate.sd_floor)


def test_sd_floor_on_zero_variance(gate):
    r = X.pooled_t_interval(FLOOR_CASE["ours"], FLOOR_CASE["reference"], gate.t_quantile, gate.sd_floor)
    assert r["sd_ours"] == r["sd_reference"] == gate.sd_floor
    assert r["high"] == pytest.approx(FLOOR_CASE["half"], abs=TOL) and r["low"] == pytest.approx(-FLOOR_CASE["half"], abs=TOL)
    assert r["spread_ratio"] == FLOOR_CASE["spread_ratio"] and r["contains_zero"]
    r = X.pooled_t_interval(FLOOR_FAIL_CASE["ours"], FLOOR_FAIL_CASE["reference"], gate.t_quantile, gate.sd_floor)
    assert not r["contains_zero"]  # without the floor the interval would have no width at all


def test_spread_ratio_uses_floored_sds_ours_over_reference(gate):
    r = X.pooled_t_interval(WIDE_CASE["ours"], WIDE_CASE["reference"], gate.t_quantile, gate.sd_floor)
    assert r["spread_ratio"] == pytest.approx(WIDE_CASE["spread_ratio"], abs=TOL) and r["contains_zero"]
    assert r["high"] == pytest.approx(WIDE_CASE["half"], abs=TOL)
    flipped = X.pooled_t_interval(WIDE_CASE["reference"], WIDE_CASE["ours"], gate.t_quantile, gate.sd_floor)
    assert flipped["spread_ratio"] == pytest.approx(1 / WIDE_CASE["spread_ratio"], abs=TOL)


def test_welch_interval_hand_values(gate):
    r = X.welch_interval(WELCH_CASE["ours"], WELCH_CASE["reference"], gate.confidence, gate.sd_floor)
    for key in ("diff", "low", "high", "df", "spread_ratio"):
        assert r[key] == pytest.approx(WELCH_CASE[key], abs=TOL), key
    zero = X.welch_interval(FLOOR_CASE["ours"] * 2, FLOOR_CASE["reference"], gate.confidence, gate.sd_floor)
    assert math.isfinite(zero["low"]) and zero["contains_zero"]


@pytest.mark.parametrize("failed, passes", B_PATTERNS)
def test_b_same_team_runs(gate, failed, passes):
    worst = {g: (WORST_FAIL if g in failed else WORST_PASS) for g in range(gate.b_window[0], gate.b_window[1] + 1)}
    assert X.lineage_b(worst, gate)["pass"] is passes


def test_b_needs_the_whole_window(gate):
    with pytest.raises(ValueError, match="window"):
        X.lineage_b({gate.b_window[0]: WORST_PASS}, gate)


def test_a_completion(gate):
    full = (gate.generations, 0)
    assert X.stat_a({"o1": full, "o2": full}, gate.generations)["pass"]
    assert not X.stat_a({"o1": full, "o2": (gate.generations - 1, 0)}, gate.generations)["pass"]
    assert not X.stat_a({"o1": full, "o2": (gate.generations, 1)}, gate.generations)["pass"]


def test_d_panels_with_a_failed_conversion():
    lineages = REF + ("o1",)
    strength = {k: GUARD_STRENGTH.get(k, GUARD_STRENGTH["s1"]) for k in lineages}
    xp = synthetic_crossplay(lineages, strength, copy_strengths(STRIKE_STRENGTH) | {"o1": STRIKE_STRENGTH["s1"]},
                             games=GAMES, excluded=[X.Entry(PANEL_FAILED[0], PANEL_FAILED[1], "strike")])
    # overwrite o1's Guard rows: its hold depends only on the Strike lineage
    for i, g in enumerate(xp.guards):
        if g.lineage == "o1":
            for j, s in enumerate(xp.strikes):
                if s.lineage in PANEL_HOLD:
                    xp.reached[i, j] = round((1 - PANEL_HOLD[s.lineage]) * GAMES)
    panels = [[k for k in REF if k != out] for out in REF]
    assert [X.panel_value(xp, "o1", "guard", p) for p in panels] == pytest.approx(list(PANEL_MEANS), abs=TOL)
    assert X.our_value(xp, "o1", "guard", REF) == pytest.approx(PANEL_VALUE, abs=TOL)
    assert X.our_value(xp, "o1", "guard", REF) != pytest.approx(POOLED_OVER_ENTRIES, abs=TOL)
    # the failed entry also leaves the reference lineage's own Strike value
    assert len(xp.entries(PANEL_FAILED[0], "strike")) == len(xp.entries("s2", "strike")) - 1


def test_c_envelope_and_loo(gate):
    xp = synthetic_crossplay(REF + OURS, copy_strengths(GUARD_STRENGTH), copy_strengths(STRIKE_STRENGTH))
    assert X.loo_check(xp, REF, gate.confidence)["pass"]
    assert X.stat_c(xp, OURS, REF, gate.confidence, gated=True)["pass"]
    odd = X.Entry("o1", 1, "guard")
    xp_out = synthetic_crossplay(REF + OURS, copy_strengths(GUARD_STRENGTH), copy_strengths(STRIKE_STRENGTH), apf_hold={odd: APF_OUTSIDE})
    c = X.stat_c(xp_out, OURS, REF, gate.confidence, gated=True)
    assert not c["pass"] and c["per_entry"][odd] is False
    ref_odd = X.Entry("s1", 1, "guard")
    xp_ref = synthetic_crossplay(REF + OURS, copy_strengths(GUARD_STRENGTH), copy_strengths(STRIKE_STRENGTH), apf_hold={ref_odd: APF_OUTSIDE})
    assert not X.loo_check(xp_ref, REF, gate.confidence)["pass"]


def _d(contains_zero, spread_ratio):
    return {"contains_zero": contains_zero, "spread_ratio": spread_ratio}


def test_verdict_order(gate):
    ok, bad = {"pass": True, "kind": "gate"}, {"pass": False, "kind": "gate"}
    low, high = gate.spread_ratio_max / 2, gate.spread_ratio_max * 2
    good_d = {name: _d(True, low) for name in gate.d_statistics}
    wide_d = {name: _d(True, high) for name in gate.d_statistics}
    excl_wide = {name: _d(i == 0, high) for i, name in enumerate(gate.d_statistics)}
    assert X.verdict(ok, ok, ok, good_d, gate)["verdict"] == X.PASS
    assert X.verdict(ok, ok, ok, wide_d, gate)["verdict"] == X.INCONCLUSIVE
    assert X.verdict(ok, ok, ok, wide_d, gate, followup=True)["verdict"] == X.FAIL      # six seeds: spread gives FAIL
    assert X.verdict(ok, ok, ok, excl_wide, gate)["verdict"] == X.FAIL                  # FAIL stays FAIL with a high spread
    assert X.verdict(bad, ok, ok, wide_d, gate)["verdict"] == X.FAIL
    assert X.verdict(ok, bad, ok, good_d, gate)["verdict"] == X.FAIL
    assert X.verdict(ok, ok, bad, good_d, gate)["verdict"] == X.FAIL
    assert X.verdict(ok, ok, {"pass": False, "kind": X.INFO}, good_d, gate)["verdict"] == X.PASS   # c as INFO never fails
    assert X.verdict(None, ok, ok, good_d, gate)["verdict"] == X.PASS                    # a not applicable (N0)
    at_limit = {name: _d(True, gate.spread_ratio_max) for name in gate.d_statistics}
    assert X.verdict(ok, ok, ok, at_limit, gate)["verdict"] == X.PASS                    # INCONCLUSIVE only above the limit


def test_method_match_copy_passes_and_untrained_fails(gate):
    lineages = REF + OURS
    xp = synthetic_crossplay(lineages, copy_strengths(GUARD_STRENGTH), copy_strengths(STRIKE_STRENGTH), games=GAMES)
    full = {k: (gate.generations, 0) for k in OURS}
    result = X.method_match(xp, OURS, REF, gate, completion=full, pools=own_pools(xp, OURS))
    assert result["verdict"]["verdict"] == X.PASS, result["verdict"]
    # an untrained arm: its Guards never hold and its Strikes never reach
    untrained = synthetic_crossplay(lineages, GUARD_STRENGTH | {k: 0 for k in OURS}, STRIKE_STRENGTH | {k: -1 for k in OURS},
                                    games=GAMES, own_rule="first_mover")
    n0 = X.method_match(untrained, OURS, REF, gate, completion=None, pools=own_pools(untrained, OURS))
    assert n0["verdict"]["verdict"] == X.FAIL and X.negative_control_ok(n0)
    assert not X.negative_control_ok(result)


def test_six_seed_followup_uses_welch(gate):
    lineages = REF + SIX
    xp = synthetic_crossplay(lineages, GUARD_STRENGTH | {k: GUARD_STRENGTH["s2"] for k in SIX},
                             STRIKE_STRENGTH | {k: STRIKE_STRENGTH["s2"] for k in SIX})
    d = X.stat_d(xp, SIX, REF, gate, followup=True)
    assert all(r["test"] == "welch" for r in d.values())
    with pytest.raises(ValueError):
        X.stat_d(xp, SIX, REF, gate, followup=False)


def test_info_statistics():
    xp = synthetic_crossplay(REF, GUARD_STRENGTH, STRIKE_STRENGTH)
    assert X.last_mover_share(xp, "s1") == LAST_MOVER_ALL
    flipped = synthetic_crossplay(REF, GUARD_STRENGTH, STRIKE_STRENGTH, own_rule="first_mover")
    assert X.last_mover_share(flipped, "s1") == LAST_MOVER_NONE
    assert X.near_shutout_share(xp, "s1", SHUTOUT_MARGIN) == 1
    assert X.cell_differences(xp, xp).max() == 0
    last_strike = max(e.generation for e in xp.strikes)
    assert 0 <= X.generalist_mean(xp, REF, last_strike - 1, last_strike) <= 1


# ---------------------------------------------------------------- batched scoring on the replica (marker files, CPU)
def _players(env, team, seeds):
    import torch
    from svg_training.nus.mappo import MappoActor
    from svg_training.nus.crossplay import _detach_tree
    actors = [MappoActor(env.obs_dim, env.method, env.deploy.layernorm_epsilon, torch.Generator().manual_seed(s)) for s in seeds]
    return actors, [_detach_tree(a.trunk.tree()) for a in actors]


def _one_pairing(env, starts, guard_actor, strike_actor):
    """Reference: one pairing on its own, actors called one by one (no stacking)."""
    import torch
    from svg_training.nus.mappo import squash
    state = starts
    with torch.no_grad():
        for _ in range(env.episode_steps):
            go, so = env.observe(state)
            g = env.apf_actions(state, "guard") if guard_actor is None else squash(guard_actor(go)[0], env.team_speed("guard"), env.deploy.disk_floor)
            s = env.apf_actions(state, "strike") if strike_actor is None else squash(strike_actor(so)[0], env.team_speed("strike"), env.deploy.disk_floor)
            state, _ = env.step(state, g, s, shaping_gamma=1)
    return int((state.game.reached > 0).sum())


def test_stacked_scoring_equals_pairings_one_by_one(tmp_path):
    from _nus_phase5_method_fixture import SCORE_CHUNK, SCORE_GAMES, SEEDS, STARTS_SEED, marker_env
    env = marker_env(tmp_path)
    m = env.method
    forward = dict(bf16=m.compute_dtype == "bfloat16", activation=m.activation, eps=env.deploy.layernorm_epsilon, use_norm=m.use_layernorm)
    g_actors, g_trees = _players(env, "guard", SEEDS[:2])
    s_actors, s_trees = _players(env, "strike", SEEDS[2:])
    starts = X.shared_starts(env, SCORE_GAMES, STARTS_SEED)
    guards = {X.Entry("a", 2 * i + 1, "guard"): t for i, t in enumerate(g_trees)}
    strikes = {X.Entry("a", 2 * i + 2, "strike"): t for i, t in enumerate(s_trees)}
    xp = X.score_matrix(env, guards, strikes, starts, forward, SCORE_CHUNK)
    for i, ga in enumerate(g_actors):
        for j, sa in enumerate(s_actors):
            assert xp.reached[i, j] == _one_pairing(env, starts, ga, sa)
        assert xp.apf_strike_reached[i] == _one_pairing(env, starts, ga, None)
    for j, sa in enumerate(s_actors):
        assert xp.apf_guard_reached[j] == _one_pairing(env, starts, None, sa)
    again = X.score_matrix(env, guards, strikes, X.shared_starts(env, SCORE_GAMES, STARTS_SEED), forward, len(guards) * len(strikes))
    assert (again.reached == xp.reached).all()                                       # shared starts and determinism


def test_untrained_arm_of_n0(tmp_path):
    from _nus_phase5_method_fixture import marker_env
    env = marker_env(tmp_path)
    n0 = X.untrained_trees(env, env.method, seed=FROZEN_GATE["generations"], generations=FROZEN_GATE["generations"])
    assert [e.team for e in n0] == ["guard", "strike"] * (FROZEN_GATE["generations"] // 2)
    again = X.untrained_trees(env, env.method, seed=FROZEN_GATE["generations"], generations=FROZEN_GATE["generations"])
    first = next(iter(n0))
    assert all(a.equal(b) for a, b in zip(n0[first]["proj"], again[first]["proj"]))
