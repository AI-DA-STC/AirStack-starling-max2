"""Phase 5 Tasks S1 and S3 (plan docs/plans/2026-11-18-nus-phase5-retraining.md section 9): the stage 5.2 training game and environment
(``nus/train_game.py`` run to the time-out, ``nus/tier1_env.py``) and its reward and critic state, plus the clamp counter of Task S5
(``nus/hangar_game.py``). CPU, marker local files. No numeric literal (G2): constants live in the fixtures."""
from __future__ import annotations

import ast

import pytest
import torch

import _nus_markers  # noqa: F401  (puts source/ and scripts/ on the path)
from _nus_markers import ROOT
from _nus_phase4_fixture import P4_GAMES
from _nus_tier1_fixture import (AWAY, CLAMP_STEPS, FIRST_REACH_GAMES, OTHER_SEED, OUTSIDE_COUNTED_M, OUTSIDE_NOT_M, POS_ABS_M, REACH_SEED,
                                REWARD_REL, SLOT, HALF, STICKY_EPISODE_STEPS, TIER1_GAMES, UNITS_SPAN, tier1_world_fixture)
from svg_training.core.observations import OBS_DIM, OBS_DIM_V02, STATE_DIM
from svg_training.core.play import play_match
from svg_training.core.rewards import STRIKE_WIN
from svg_training.nus.hangar_game import NusHangarGame
from svg_training.nus.players import make_player
from svg_training.nus.replica_train import guard_reward
from svg_training.nus.tier1_env import NusTier1Env, tier1_guard_reward
from svg_training.nus.train_game import NusHangarTrainGame


@pytest.fixture
def tw(tmp_path, monkeypatch):
    return tier1_world_fixture(tmp_path, monkeypatch)


def _gen(seed):
    return torch.Generator().manual_seed(seed)


def _apf_both(env, state):
    return env.apf_actions(state, "guard"), env.apf_actions(state, "strike")


# ------------------------------------------------------------------------------------------------ S1: decision and hold
def test_one_decision_is_held_for_hold_ticks(tw, monkeypatch):
    env = NusTier1Env(tw.world, tw.method)
    state = env.reset(TIER1_GAMES, _gen(REACH_SEED))
    calls = []
    original = NusHangarTrainGame.step

    def spy(self, actions):
        calls.append({k: v.clone() for k, v in actions.items()})
        return original(self, actions)
    monkeypatch.setattr(NusHangarTrainGame, "step", spy)
    g, s = _apf_both(env, state)
    nxt, out = env.step(state, g, s, env.method.guard_gamma)
    assert len(calls) == env.hold == tw.w.geo.hold_ticks
    assert all(torch.equal(c["guard"], calls[0]["guard"]) and torch.equal(c["strike"], calls[0]["strike"]) for c in calls)
    assert torch.equal(calls[0]["guard"][..., :2 + 1], g) and (calls[0]["guard"][..., -1] == 0).all()   # yaw rate 0
    assert bool((state.handle.steps == env.hold).all()) and bool((nxt.game.step == 1).all())
    assert torch.allclose(nxt.game.pos, state.handle.pos_m, atol=POS_ABS_M)
    assert env.episode_steps * env.hold == state.handle.ticks


def test_observation_is_v02_and_the_command_is_3d(tw):
    env = NusTier1Env(tw.world, tw.method)
    state = env.reset(TIER1_GAMES, _gen(REACH_SEED))
    guard_obs, strike_obs = env.observe(state)
    assert guard_obs.shape == (TIER1_GAMES, env.guard_count, OBS_DIM_V02) and strike_obs.shape[-1] == OBS_DIM_V02
    floor, ceiling = tw.world.cfg.arena.height_band_m
    assert (guard_obs[..., OBS_DIM] == floor).all() and (guard_obs[..., OBS_DIM + 1] == ceiling).all()
    assert env.action_dim == 2 + 1 and env.team_speed("guard") == 1


def test_starts_come_from_the_passed_generator(tw):
    env = NusTier1Env(tw.world, tw.method)
    a = env.reset(TIER1_GAMES, _gen(REACH_SEED)).game.pos.clone()
    b = env.reset(TIER1_GAMES, _gen(REACH_SEED)).game.pos.clone()
    c = env.reset(TIER1_GAMES, _gen(OTHER_SEED)).game.pos.clone()
    assert torch.equal(a, b) and not torch.equal(a, c)


def test_reached_flag_stays_set_and_the_game_runs_to_the_time_out(tmp_path, monkeypatch):
    """Strike drones run to the zone (APF) against a still Guard team, then, once their game is reached, straight along +x; the flag
    stays 1 after they leave, the game is never restarted before the time limit, and the last decision is the time-out."""
    tw = tier1_world_fixture(tmp_path, monkeypatch, episode_steps=STICKY_EPISODE_STEPS)
    env = NusTier1Env(tw.world, tw.method)
    state = env.reset(TIER1_GAMES, _gen(REACH_SEED))
    still = torch.zeros(TIER1_GAMES, env.guard_count, env.action_dim)
    away = torch.tensor(AWAY).expand(TIER1_GAMES, env.strike_count, env.action_dim)
    seen_reach = torch.zeros(TIER1_GAMES, dtype=torch.bool)
    for k in range(env.episode_steps):
        strike = torch.where(seen_reach[:, None, None], away, env.apf_actions(state, "strike"))
        prev_reached = state.game.reached > 0
        state, out = env.step(state, still, strike, env.method.guard_gamma)
        assert bool((state.game.reached >= prev_reached.float()).all())                 # sticky
        assert bool(torch.equal(out.first_reach, out.reached & ~prev_reached))
        seen_reach |= out.reached
        assert bool(out.time_limit.all()) == (k == env.episode_steps - 1)
        if k < env.episode_steps - 1:
            assert bool((state.handle.steps == (k + 1) * env.hold).all())                # no restart at the reach
    assert bool(seen_reach.any()) and bool((state.game.reached[seen_reach] == 1).all())
    assert bool((seen_reach & (out.inside_count == 0)).any())       # reached, now outside the zone, and the flag is still set


def test_outcome_equals_the_first_reach_rule(tw):
    """Plan Task S1: on 1,000 CPU games with scripted players (APF Strike v APF or still Guards, decided once per hold, held), the sticky reached flag of the
    run-to-time-out game equals the outcome of the programme rule (the game ends at its first reach), and the flag's first tick is
    that game's end step."""
    env = NusTier1Env(tw.world, tw.method)
    n = FIRST_REACH_GAMES
    apf_guard = torch.arange(n) % 2 == 0          # half the games an APF Guard team, half a still one: both outcomes occur
    state = env.reset(n, _gen(REACH_SEED))
    for _ in range(env.episode_steps):
        g, s = _apf_both(env, state)
        state, _ = env.step(state, g * apf_guard[:, None, None], s, env.method.guard_gamma)
    w = tw.world
    plain = NusHangarTrainGame(w.cfg, w.geo, w.row, w.rules, w.guards, w.strikes, n, seed=OTHER_SEED, jitter_m=w.jitter_m)
    plain.set_start_generator(_gen(REACH_SEED))
    plain.reset()
    outcome = torch.zeros(n, dtype=torch.int8)
    end = torch.zeros(n, dtype=torch.long)
    finished = torch.zeros(n, dtype=torch.bool)
    held = None
    for tick in range(plain.ticks):
        if tick % env.hold == 0:   # the same decision schedule and arithmetic as the environment, on the programme game
            pos = plain.pos_m
            units = (pos[..., :2] - plain.arenas.zone_centre_m[:, None, :]) / w.deploy.metres_per_unit
            g = (env.apf.actions("guard", units) / w.rules.guard_max_speed).clamp(-1, 1) * apf_guard[:, None, None]
            s = (env.apf.actions("strike", units) / w.rules.strike_max_speed).clamp(-1, 1)
            zero = torch.zeros_like(g[..., :2])
            held = {"guard": torch.cat((g, zero), dim=-1), "strike": torch.cat((s, torch.zeros_like(s[..., :2])), dim=-1)}
        out = plain.step(held)
        first = out.done & ~finished
        outcome = torch.where(first, out.outcome, outcome)
        end = torch.where(first, out.end_step, end)
        finished |= out.done
        if bool(finished.all()):
            break
    assert bool(finished.all())
    reached = state.game.reached > 0
    assert torch.equal(reached, outcome == STRIKE_WIN)
    assert torch.equal(state.first_tick[reached], end[reached])
    assert bool(reached.any()) and not bool(reached.all())          # both kinds occur, so the comparison means something


def test_apf_command_equals_the_ported_players(tw):
    """The environment's scripted slot gives the command ``ApfGuard`` / ``ApfStrike`` give from the observation (rounding only)."""
    env = NusTier1Env(tw.world, tw.method)
    state = env.reset(TIER1_GAMES, _gen(REACH_SEED))
    obs = state.handle._obs()
    for team in ("guard", "strike"):
        player = make_player("ApfGuard" if team == "guard" else "ApfStrike", team, tw.world.cfg, TIER1_GAMES, "cpu")
        player.reset(torch.ones(TIER1_GAMES, dtype=torch.bool))
        ported = player.act(obs[team])
        ours = env.apf_actions(state, team)
        assert torch.allclose(ported[..., :2 + 1], ours, atol=POS_ABS_M)


def test_no_python_loop_over_games_in_the_environment():
    tree = ast.parse((ROOT / "source/svg_training/nus/tier1_env.py").read_text())
    for loop in [n for n in ast.walk(tree) if isinstance(n, (ast.For, ast.While, ast.comprehension))]:
        text = ast.unparse(loop.iter if not isinstance(loop, ast.While) else loop.test)
        assert "hold" in text or "items()" in text or "rows" in text or "settings" in text or "len(self._games)" in text, text
    tree = ast.parse((ROOT / "source/svg_training/nus/train_game.py").read_text())
    assert not [n for n in ast.walk(tree) if isinstance(n, (ast.For, ast.While, ast.comprehension))]


# ------------------------------------------------------------------------------------------------ S3: reward and critic state
def test_reward_in_metres_equals_the_replica_reward_in_units(tw):
    w, method = tw.world, tw.method
    gen = _gen(REACH_SEED)
    m = w.guards + w.strikes
    before = (torch.rand(TIER1_GAMES, m, 2, generator=gen) * 2 - 1) * UNITS_SPAN
    after = (torch.rand(TIER1_GAMES, m, 2, generator=gen) * 2 - 1) * UNITS_SPAN
    inside = torch.randint(0, w.strikes + 1, (TIER1_GAMES,), generator=gen)
    flags = torch.rand(2 + 1, TIER1_GAMES, generator=gen) > HALF
    scale = w.deploy.metres_per_unit
    units = guard_reward(before, after, inside, flags[0], flags[1], flags[2], guard_count=w.guards, method=method,
                         shaping_gamma=method.guard_gamma)
    metres = tier1_guard_reward(before * scale, after * scale, inside, flags[0], flags[1], flags[2], guard_count=w.guards, method=method,
                                shaping_gamma=method.guard_gamma, metres_per_unit=scale)
    assert torch.allclose(metres, units, rtol=REWARD_REL, atol=REWARD_REL)


def test_environment_reward_is_the_partner_reward_of_its_own_positions(tw):
    env = NusTier1Env(tw.world, tw.method)
    state = env.reset(TIER1_GAMES, _gen(REACH_SEED))
    for _ in range(env.episode_steps):
        prev = state
        start = prev.game.pos.clone()
        state, out = env.step(prev, *_apf_both(env, prev), env.method.strike_gamma)
        zone = state.handle.arenas.zone_centre_m[:, None, :]
        want = tier1_guard_reward(start[..., :2] - zone, state.game.pos[..., :2] - zone, out.inside_count, out.time_limit, out.reached,
                                  out.first_reach, guard_count=env.guard_count, method=env.method, shaping_gamma=env.method.strike_gamma,
                                  metres_per_unit=env.deploy.metres_per_unit)
        assert torch.equal(out.guard_reward, want)
        radius = state.handle.arenas.zone_radius_m[:, None]
        assert torch.equal(out.inside_count, ((state.game.pos[:, env.guard_count:, :2] - zone[:, :, :]).norm(dim=-1) <= radius).sum(dim=1))


@pytest.mark.parametrize("flag", [False, True])
def test_critic_state_is_build_state_then_the_flag_then_the_slot_one_hot(tw, flag):
    env = NusTier1Env(tw.world, tw.method, critic_reached_flag=flag)
    state = env.reset(TIER1_GAMES, _gen(REACH_SEED))
    slots = torch.full((TIER1_GAMES,), SLOT, dtype=torch.long)
    central = env.central_state(state, slots)
    assert central.shape == (TIER1_GAMES, env.state_dim) and env.state_dim == STATE_DIM + int(flag) + tw.method.max_pool_slots
    assert torch.equal(central[:, :STATE_DIM], state.handle.state())
    hot = central[:, STATE_DIM + int(flag):]
    assert bool((hot.argmax(dim=1) == SLOT).all()) and bool((hot.sum(dim=1) == 1).all())
    if flag:
        assert bool((central[:, STATE_DIM] == state.game.reached).all())


def test_default_critic_state_follows_the_plan(tw):
    """Plan section 5: build_state's 61 numbers plus the slot one-hot (the reached flag is a question for the gatekeeper, off by default)."""
    assert NusTier1Env(tw.world, tw.method).state_dim == STATE_DIM + tw.method.max_pool_slots


# ------------------------------------------------------------------------------------------------ S5: the clamp counter
def test_clamp_counter_counts_drones_outside_by_more_than_the_tolerance(tw):
    w = tw.world
    game = NusHangarTrainGame(w.cfg, w.geo, w.row, w.rules, w.guards, w.strikes, TIER1_GAMES, seed=OTHER_SEED, jitter_m=w.jitter_m,
                              clamp_tol_m=w.clamp_tol_m)
    layer = game._starling
    half = w.geo.side_m / 2 - w.cfg.arena.wall_margin_m
    floor, ceiling = w.cfg.arena.height_band_m
    lo, hi = torch.tensor([-half, -half, floor]), torch.tensor([half, half, ceiling])
    pos = game.pos_m.clone()
    pos[0, 0, 0] = hi[0] + OUTSIDE_COUNTED_M      # game 0: one drone 0.02 m outside in x
    pos[1, 0, 2] = lo[2] - OUTSIDE_NOT_M          # game 1: one drone 0.005 m under the floor
    layer.model.pos_m = pos
    clamped = layer.keep_in(lo, hi)
    acc = game.safety()
    assert acc["clamp_ticks"].tolist() == [1] + [0] * (TIER1_GAMES - 1)
    assert bool((acc["live_ticks"] == w.guards + w.strikes).all()) and not bool(acc["nonfinite_state"].any())
    assert bool(((clamped >= lo) & (clamped <= hi)).all())


def test_every_drone_is_inside_the_box_after_each_step_and_the_counter_changes_nothing(tw):
    """Real steps: after each, every drone is inside the keep-in box; outcomes with the counter on equal those with it off."""
    w = tw.world
    results = []
    for tol in (None, w.clamp_tol_m):
        game = NusHangarGame(w.cfg, w.geo, w.row, tw.w.starts["starts_units"], tw.w.starts["jitter_m"], w.guards, w.strikes,
                             seed=OTHER_SEED, rules=w.rules, clamp_tol_m=tol)
        lim = w.geo.side_m / 2 - w.cfg.arena.wall_margin_m
        floor, ceiling = w.cfg.arena.height_band_m
        guard = make_player("ParkedGuard", "guard", w.cfg, P4_GAMES, "cpu")
        strike = make_player("ApfStrike", "strike", w.cfg, P4_GAMES, "cpu")
        res = play_match(game, guard, strike)
        results.append((res.outcome.clone(), res.end_step.clone()))
        obs = game.reset()
        for _ in range(CLAMP_STEPS):
            obs = game.step({"guard": guard.act(obs["guard"]), "strike": strike.act(obs["strike"])}).obs
            p = game.pos_m
            assert bool((p[..., :2].abs() <= lim).all()) and bool(((p[..., 2] >= floor) & (p[..., 2] <= ceiling)).all())
    assert torch.equal(results[0][0], results[1][0]) and torch.equal(results[0][1], results[1][1])
