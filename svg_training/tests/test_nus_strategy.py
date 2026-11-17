"""Tests of the partner-policy strategy wrapper (NusPolicy). A synthetic checkpoint with marker sizes stands in for the partner's; no
partner value is used. The wrapper rebuilds the partner's observation from our observation and its own memory, holds each action for
the deploy file's number of ticks and converts units per step into the normalised command."""
import dataclasses

import pytest
import torch

from _nus_markers import (ACTION_WIDTH, HOLDS, SPACE_DIM, ARENA_SIDE_M, BATCH, POS_TOL, SEED_B, TOL_LOOSE, TOL_TIGHT, load_marker_files, obs_errors, write_synthetic_checkpoint)
from svg_training.core.arena import Arenas
from svg_training.core.game import SvgGame
from svg_training.core.game_config import load_game_cfg
from svg_training.core.observations import OBS_DIM, ObsView, build_obs
from svg_training.core.strategy import check_strategy
from svg_training.nus import deploy as deploy_mod, strategy as strategy_mod
from svg_training.nus.replica import NusReplica, ReplicaState
from svg_training.opponents.scripted import make_strategy

SPEC = "svg_training.nus.strategy:NusPolicy"
TEAMS = ("guard", "strike")
V = ObsView()


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    """Marker rules and deploy files plus converted-weight folders for both teams, wired into the strategy module."""
    folder = tmp_path_factory.mktemp("strategy")
    rules, deploy, rules_path, deploy_path = load_marker_files(folder)
    weights = folder / "weights"
    for team in TEAMS:
        write_synthetic_checkpoint(weights / getattr(deploy, f"{team}_weights"), team, kind="archive")
    return rules, deploy, rules_path, deploy_path, weights


@pytest.fixture()
def wired(world, monkeypatch):
    rules, deploy, rules_path, deploy_path, weights = world
    monkeypatch.setattr(strategy_mod, "RULES_PATH", rules_path)
    monkeypatch.setattr(strategy_mod, "DEPLOY_PATH", deploy_path)
    monkeypatch.setattr(deploy_mod, "WEIGHTS_DIR", weights)
    return rules, deploy


def game_cfg(rules, deploy, **extra):
    cfg, _ = load_game_cfg(use_local=False)
    return cfg.replace(**{"rules.metres_per_unit": deploy.metres_per_unit, "rules.seconds_per_step": deploy.seconds_per_step,
                          "rules.strike_units_per_step": rules.strike_max_speed, "rules.guard_units_per_step": rules.guard_max_speed,
                          "rules.game_steps": rules.episode_steps, **extra})


def our_obs(cfg, rules, deploy, pos_units, alive=None):
    """Our observation (metres) of the same positions; the zone centre is the arena centre and the zone has the rules' radius."""
    n, m = pos_units.shape[:2]
    height = torch.full((n, m, 1), deploy.flying_height_m)
    pos_m = torch.cat((pos_units * deploy.metres_per_unit, height), dim=-1)
    arena = Arenas(side_m=torch.full((n,), ARENA_SIDE_M), half_m=torch.full((n,), ARENA_SIDE_M / 2),
                   zone_centre_m=torch.zeros(n, 2), zone_radius_m=torch.full((n,), rules.area_radius * deploy.metres_per_unit),
                   band=torch.zeros(n, dtype=torch.long))
    alive = torch.ones(n, m, dtype=torch.bool) if alive is None else alive
    return build_obs(cfg, pos_m, torch.zeros(n, m, SPACE_DIM), torch.zeros(n, m), alive, arena, torch.zeros(n), rules.guard_count, rules.strike_count)


def team_slice(rules, team):
    return slice(0, rules.guard_count) if team == "guard" else slice(rules.guard_count, rules.guard_count + rules.strike_count)


def make(rules, deploy, team, n=BATCH, **cfg_extra):
    return make_strategy(SPEC, team, game_cfg(rules, deploy, **cfg_extra), n, "cpu", 0)


@pytest.mark.parametrize("team", TEAMS)
def test_plugs_in_through_make_strategy_and_passes_the_contract_check(wired, team):
    rules, deploy = wired
    cfg = game_cfg(rules, deploy)
    strategy = make_strategy(SPEC, team, cfg, BATCH, "cpu", 0)
    assert strategy.team == team and strategy.name == "NusPolicy"
    game = SvgGame(cfg, BATCH, rules.guard_count, rules.strike_count, device="cpu", seed=SEED_B)
    check_strategy(strategy, game, steps=deploy.hold_ticks * HOLDS)


def start_with_a_strike_at_the_zone_edge(sim, rules, generator):
    """Batch of random starts; in game 0 a Strike drone stands just outside the zone."""
    state = sim.reset(BATCH, generator=generator)
    pos = state.pos.clone()
    pos[0, rules.guard_count] = torch.tensor([rules.area_radius + rules.strike_max_speed / 2, 0.0])
    return ReplicaState(pos, pos.clone(), state.reached, state.step)


@pytest.mark.parametrize("team", TEAMS)
def test_rebuilt_observation_equals_the_replicas_at_every_sample_and_the_action_is_held_between(wired, team):
    rules, deploy = wired
    sim, cfg = NusReplica(rules), game_cfg(rules, deploy)
    strategy = make_strategy(SPEC, team, cfg, BATCH, "cpu", 0)
    rows = team_slice(rules, team)
    gen = torch.Generator().manual_seed(SEED_B)
    state = start_with_a_strike_at_the_zone_edge(sim, rules, gen)
    strategy.reset(torch.ones(BATCH, dtype=torch.bool))
    for step_index in range(HOLDS * 2):
        requests = torch.randn(BATCH, sim.num_actors, 2, generator=gen) * rules.guard_max_speed
        direction = -1 if step_index == 0 else 1  # game 0: a Strike walks into the zone, then out again: the flag must stay set
        requests[0, rules.guard_count] = torch.tensor([direction * rules.strike_max_speed, 0.0])
        nxt = sim.step(state, requests)
        first = None
        for sub in range(deploy.hold_ticks):
            current = state.pos + (nxt.pos - state.pos) * (sub / deploy.hold_ticks)  # the game's ticks between two samples
            action = strategy.act(our_obs(cfg, rules, deploy, current)[team])
            if sub == 0:
                err, direction_err = obs_errors(strategy.partner_obs, sim.observe(state)[:, rows], sim.num_actors)
                assert err <= POS_TOL and direction_err <= POS_TOL, f"step {step_index}: {err:.3e} {direction_err:.3e}"
                first = action
            else:
                assert torch.equal(action, first), "the action changes inside a hold"
        state = nxt
    assert state.reached[0] == 1 and strategy.reached[0] == 1  # the latch was set in game 0 and stayed


@pytest.mark.parametrize("team", TEAMS)
def test_a_reset_in_the_middle_of_a_hold_restarts_only_that_game(wired, team):
    rules, deploy = wired
    sim, cfg = NusReplica(rules), game_cfg(rules, deploy)
    strategy = make_strategy(SPEC, team, cfg, BATCH, "cpu", 0)
    rows = team_slice(rules, team)
    gen = torch.Generator().manual_seed(SEED_B)
    state = sim.reset(BATCH, generator=gen)
    strategy.reset(torch.ones(BATCH, dtype=torch.bool))
    strategy.act(our_obs(cfg, rules, deploy, state.pos)[team])  # the first sample of every game
    strategy.reached[:] = 1  # every game had latched
    before = strategy.partner_obs.clone()
    held = strategy.held.clone()
    moved = state.pos + torch.randn(state.pos.shape, generator=gen) * rules.guard_max_speed
    fresh = sim.reset(BATCH, generator=gen)
    game = 1
    moved[game] = fresh.pos[game]
    strategy.reset(torch.arange(BATCH) == game)
    action = strategy.act(our_obs(cfg, rules, deploy, moved)[team])
    err, direction = obs_errors(strategy.partner_obs[game:game + 1], sim.observe(fresh)[game:game + 1, rows], sim.num_actors)
    assert err <= POS_TOL and direction <= POS_TOL  # the new game's first sample: no previous positions, flag clear
    assert strategy.partner_obs[game, 0, -1] == 0
    keep = torch.arange(BATCH) != game
    assert torch.equal(strategy.partner_obs[keep], before[keep]) and torch.equal(action[keep], held[keep])
    for _ in range(deploy.hold_ticks - 1):
        strategy.act(our_obs(cfg, rules, deploy, moved)[team])
    strategy.act(our_obs(cfg, rules, deploy, moved)[team])  # the game's next sample: exactly one hold after its reset
    assert torch.allclose(strategy.memory_pos[game], moved[game], atol=TOL_LOOSE) and strategy.tick[game] == deploy.hold_ticks + 1


@pytest.mark.parametrize("team", TEAMS)
def test_action_is_the_actors_units_per_step_over_the_team_speed_with_vertical_and_yaw_zero_and_out_drones_silent(wired, team):
    from svg_training.nus.actor import NusActor
    rules, deploy = wired
    cfg = game_cfg(rules, deploy)
    strategy = make_strategy(SPEC, team, cfg, BATCH, "cpu", 0)
    sim = NusReplica(rules)
    state = sim.reset(BATCH, generator=torch.Generator().manual_seed(SEED_B))
    strategy.reset(torch.ones(BATCH, dtype=torch.bool))
    rows = team_slice(rules, team)
    alive = torch.ones(BATCH, sim.num_actors, dtype=torch.bool)
    alive[0, rows.start] = False
    out = strategy.act(our_obs(cfg, rules, deploy, state.pos, alive)[team])
    speed = rules.guard_max_speed if team == "guard" else rules.strike_max_speed
    actor = NusActor.load(deploy_mod.weights_folder(deploy, team), team=team, rules=rules, deploy=deploy)
    units = actor.act_units(strategy.partner_obs)
    assert out.shape == (BATCH, actor.team_size, ACTION_WIDTH)
    assert torch.allclose(out[..., :2][1:], (units / speed)[1:], atol=TOL_LOOSE)
    assert out[..., 2:].abs().max() == 0 and out.abs().max() <= 1
    assert out[0, 0].abs().max() == 0  # a drone that is out is commanded zero


def test_memory_moves_only_at_a_sample(wired):
    rules, deploy = wired
    cfg, sim = game_cfg(rules, deploy), NusReplica(rules)
    gen = torch.Generator().manual_seed(SEED_B)
    state = sim.reset(BATCH, generator=gen)
    strategy = make_strategy(SPEC, "guard", cfg, BATCH, "cpu", 0)
    strategy.reset(torch.ones(BATCH, dtype=torch.bool))
    strategy.act(our_obs(cfg, rules, deploy, state.pos)["guard"])
    moved = state.pos + torch.randn(state.pos.shape, generator=gen) * rules.guard_max_speed
    strategy.act(our_obs(cfg, rules, deploy, moved)["guard"])  # inside the hold: no new sample, the memory stays
    assert torch.allclose(strategy.memory_pos, state.pos, atol=TOL_LOOSE)


def test_refuses_what_it_cannot_play_naming_keys_only(wired):
    rules, deploy = wired
    for change, key in (({"rules.metres_per_unit": deploy.metres_per_unit * 2}, "metres_per_unit"),
                        ({"rules.seconds_per_step": deploy.seconds_per_step * 2}, "seconds_per_step"),
                        ({"rules.strike_units_per_step": rules.strike_max_speed * 2}, "strike_units_per_step"),
                        ({"rules.guard_units_per_step": rules.guard_max_speed * 2}, "guard_units_per_step"),
                        ({"dropout_fraction": 1.0 / 2}, "dropout_fraction")):
        cfg = game_cfg(rules, deploy).replace(**change)
        with pytest.raises(ValueError, match=key) as err:
            make_strategy(SPEC, "guard", cfg, BATCH, "cpu", 0)
        assert str(deploy.metres_per_unit) not in str(err.value) and str(rules.strike_max_speed) not in str(err.value)
    strategy = make(rules, deploy, "guard")
    wrong = torch.zeros(BATCH, rules.guard_count + 1, OBS_DIM)
    with pytest.raises(ValueError, match="team size"):
        strategy.act(wrong)
    with pytest.raises(ValueError):
        make(rules, deploy, "referee")


def test_missing_local_files_fail_with_a_clear_message(world, monkeypatch, tmp_path):
    rules, deploy, _, _, _ = world
    monkeypatch.setattr(strategy_mod, "DEPLOY_PATH", tmp_path / "absent.toml")
    with pytest.raises(FileNotFoundError, match="nus_make_local_deploy"):
        make(rules, deploy, "guard")
