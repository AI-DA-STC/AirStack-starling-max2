"""Phase 4 (transfer ladder) tests, marker values only: the hangar file and configuration, the hangar game (starts, parked Guard, jump motion,
layer swap, control equalities), the players, the replica engine and its metrics, the record text rules, the runner. CPU; no Isaac."""
import json
import subprocess
import tomllib

import pytest
import torch

import _nus_markers  # noqa: F401  (puts source/ and scripts/ on the path)
from _nus_markers import ROOT, marker_strings, write_toml
from _nus_phase4_fixture import (ROUND_DPI, ACT, BAD_SIDE, INTERVAL_BASE, INTERVAL_INSIDE, INTERVAL_OUTSIDE, PARKED_HOLD, QUOTE, ROUND_HALF, ROW_TWO_INDEX, rate, EXACT, FAR, HAND, HAND_DISTANCE, NEAR_UNITS, FOUR, P4_GAMES, POS_TOL_UNITS, STEPS_SHORT, THREE, TICKS_FEW, WIDE, build, marker_hangar_value)
from svg_training.core.game import SvgGame
from svg_training.core.play import play_match
from svg_training.nus import hangar as hangar_mod, ladder, players, strategy as strategy_module
from svg_training.nus.hangar_game import NusHangarGame, NusIdentityLayer, NusPushLayer
from svg_training.nus.replica import ReplicaState


@pytest.fixture
def world(tmp_path, monkeypatch):
    return build(tmp_path, monkeypatch)


def _game(w, row_id, parked=False, **kw):
    row = w.rows[row_id]
    return NusHangarGame(w.cfg(row_id), w.geo, row, w.starts["starts_units"], w.starts["jitter_m"], w.guards, w.strikes, device="cpu",
                         parked=parked, rules=w.rules, **kw)


# ------------------------------------------------------------------------------------------------ hangar file and configuration
def test_hangar_template_and_loader(tmp_path):
    tpl = tomllib.loads(hangar_mod.HANGAR_TEMPLATE.read_text())
    assert tuple(tpl) == hangar_mod.HANGAR_KEYS and all(v == "LOCAL" for v in tpl.values())
    path = tmp_path / "h.toml"
    write_toml(path, {"arena_side_m": marker_hangar_value()})
    assert hangar_mod.load_hangar(path).arena_side_m == marker_hangar_value()
    for bad, key in (({"arena_side_m": "LOCAL"}, "arena_side_m"), ({}, "arena_side_m"), ({"arena_side_m": BAD_SIDE, "extra": BAD_SIDE}, "extra"),
                     ({"arena_side_m": True}, "arena_side_m")):
        path.write_text("\n".join(f"{k} = {str(v).lower() if isinstance(v, bool) else (repr(v) if not isinstance(v, str) else QUOTE + v + QUOTE)}"
                                  for k, v in bad.items()) + "\n")
        with pytest.raises(ValueError, match=key):
            hangar_mod.load_hangar(path)
    with pytest.raises(FileNotFoundError):
        hangar_mod.load_hangar(tmp_path / "absent.toml")


def test_hangar_file_is_git_ignored():
    r = subprocess.run(["git", "check-ignore", "-q", "configs/local/nus_hangar.toml"], cwd=ROOT)
    if r.returncode not in (0, 1):
        pytest.skip("git not available")
    assert r.returncode == 0


def test_every_d1_key_is_set_from_the_marker_files_and_the_keepouts_are_crossed(world):
    w, r, d = world, world.rules, world.deploy
    cfg = w.cfg("2")
    scale = d.metres_per_unit
    assert cfg.rules.metres_per_unit == scale and cfg.rules.seconds_per_step == d.seconds_per_step
    assert cfg.rules.strike_units_per_step == r.strike_max_speed and cfg.rules.guard_units_per_step == r.guard_max_speed
    assert cfg.rules.game_steps == r.episode_steps and cfg.game_ticks() == r.episode_steps * d.hold_ticks
    # crossed: the disc round a Guard that keeps Strike drones out takes the GUARD side's safety distance
    assert cfg.rules.keepout_strike_m == pytest.approx((2 * r.agent_size + r.guard_safety_distance) * scale)
    assert cfg.rules.keepout_guard_m == pytest.approx((2 * r.agent_size + r.strike_safety_distance) * scale)
    assert cfg.arena.start_height_m == d.flying_height_m and cfg.arena.height_band_m == (d.flying_height_m, d.flying_height_m)
    assert w.cfg("5").arena.height_band_m == w.base.arena.height_band_m
    assert cfg.rules.push_rule == "block" and cfg.arena.walls == "keep_in" and cfg.dropout_fraction == 0 and cfg.obs_view == "full"
    assert not cfg.starling.enabled and w.cfg("3").starling.enabled and w.cfg("6").starling.backend == "physics"
    geo = w.geo
    assert geo.side_m == w.hangar_value and geo.ring_m == pytest.approx(r.spawn_distance * scale)
    assert geo.zone_radius_m == pytest.approx(r.area_radius * scale) and geo.guard_disc_m == pytest.approx(r.start_guard_disc_fraction * r.area_radius * scale)
    assert geo.ring_m < geo.side_m / 2 - geo.wall_margin_m   # the start ring lies inside the walls


def test_config_passes_the_policy_checks_and_the_stick_cap(world):
    w = world
    for row_id in ("2", "3", "4"):
        strategy_module._check_cfg(w.cfg(row_id), w.rules, w.deploy, "guard")
    NusHangarGame(w.cfg("4"), w.geo, w.rows["4"], w.starts["starts_units"], w.starts["jitter_m"], w.guards, w.strikes, device="cpu", rules=w.rules)


def test_committed_rows_declare_one_key_each_and_valid_values():
    settings = hangar_mod.load_phase4()
    rows = settings["row"]
    hangar_mod.check_row_lint(rows)
    for row in rows:
        hangar_mod.check_row(row)
        assert set(row["blocks"]) <= set(ladder.ALL_BLOCKS)
    assert "3h" not in {r["id"] for r in rows}   # owner answer 3: the separate hold row is dropped
    two = next(r for r in rows if r["id"] == "2")
    assert two["motion"] == "hold" and sorted(two["changed"]) == ["motion", "separation"]
    broken = [dict(rows[0]), dict(rows[ROW_TWO_INDEX], changed=["separation"])]
    with pytest.raises(ValueError):
        hangar_mod.check_row_lint(broken)
    with pytest.raises(ValueError):
        hangar_mod.check_row({**rows[0], "drone": "unknown"})
    with pytest.raises(ValueError):
        hangar_mod.check_row({**two, "drone": "physics"})   # push layer with the physics drone


# ------------------------------------------------------------------------------------------------ the hangar game
def test_starts_equal_the_starts_file_and_the_parked_variant_moves_guard_zero(world):
    w = world
    game = _game(w, "2")
    scale = w.deploy.metres_per_unit
    assert torch.allclose(game.pos_m[..., :2], w.starts["starts_units"] * scale)
    assert torch.all(game.pos_m[..., 2] == w.geo.height_m)
    assert torch.all(game.arenas.side_m == w.geo.side_m) and torch.all(game.arenas.zone_centre_m == 0)
    parked = _game(w, "2", parked=True)
    assert torch.all(parked.pos_m[:, 0, :2] == 0) and torch.equal(parked.pos_m[:, 1:], game.pos_m[:, 1:])
    jittered = _game(w, "5")
    assert torch.allclose(jittered.pos_m[..., 2] - w.geo.height_m, w.starts["jitter_m"], atol=POS_TOL_UNITS / WIDE)
    assert torch.equal(game.start_miss, _game(w, "2").start_miss)   # a start inside the filter's keep-out is flagged, not repaired


def test_start_miss_flags_a_pair_inside_the_filter_keepout(world):
    w = world
    starts = {k: v.clone() for k, v in w.starts.items()}
    starts["starts_units"][0, 1] = starts["starts_units"][0, 0]       # two drones on one spot
    game = NusHangarGame(w.cfg("2"), w.geo, w.rows["2"], starts["starts_units"], starts["jitter_m"], w.guards, w.strikes, device="cpu", rules=w.rules)
    assert bool(game.start_miss[0])
    assert torch.allclose(game.pos_m[0, 1, :2], game.pos_m[0, 0, :2])   # never repaired


def test_jump_motion_moves_a_drone_by_the_full_partner_step_in_one_tick(world):
    w = world
    starts = {k: v.clone() for k, v in w.starts.items()}
    spacing = w.geo.side_m / (2 * (w.guards + w.strikes + 2)) / w.deploy.metres_per_unit             # drones far apart, outside the zone
    starts["starts_units"][:, :, 0] = (torch.arange(w.guards + w.strikes)[None] + 1) * spacing
    starts["starts_units"][:, :, 1] = 0
    action = torch.zeros(P4_GAMES, w.strikes, ACT)
    action[:, 0, 1] = 1.0                                              # the first Strike drone at full speed along y, away from every other
    still = torch.zeros(P4_GAMES, w.guards, ACT)

    def one_step(row_id):
        game = NusHangarGame(w.cfg(row_id), w.geo, w.rows[row_id], starts["starts_units"], starts["jitter_m"], w.guards, w.strikes, device="cpu",
                             rules=w.rules)
        before = game.pos_m.clone()
        game.step({"guard": still, "strike": action})
        return (game.pos_m[:, w.guards, 1] - before[:, w.guards, 1]) / w.deploy.metres_per_unit

    moved, hold_moved = one_step("2.1"), one_step("2")
    assert torch.allclose(moved, torch.full_like(moved, w.rules.strike_max_speed), atol=POS_TOL_UNITS)         # the whole partner step, one tick
    assert torch.allclose(hold_moved, moved / w.deploy.hold_ticks, atol=POS_TOL_UNITS)                         # hold: one tick's share


def test_jump_row_matches_one_replica_step_from_the_same_state(world):
    """Rows 2.1: the partner's push, cap and Guard circle in metres equal one replica step, on every partner step (state put back each step)."""
    w = world
    game = _game(w, "2.1")
    sim, scale = w.sim, w.deploy.metres_per_unit
    state = ReplicaState(pos=w.starts["starts_units"].clone(), prev_pos=w.starts["starts_units"].clone(), reached=torch.zeros(P4_GAMES),
                         step=torch.zeros(P4_GAMES, dtype=torch.long))
    spd = torch.tensor([w.rules.guard_max_speed] * w.guards + [w.rules.strike_max_speed] * w.strikes)[None, :, None]
    gen = torch.Generator().manual_seed(1)
    for _ in range(STEPS_SHORT):
        actions = (torch.rand(P4_GAMES, w.guards + w.strikes, 2, generator=gen) * 2 - 1) * spd
        for tick in range(w.deploy.hold_ticks):
            a = torch.zeros(P4_GAMES, w.guards + w.strikes, ACT)
            if tick == 0:
                a[..., :2] = actions / spd
            game.step({"guard": a[:, :w.guards], "strike": a[:, w.guards:]})
        state = sim.step(state, actions)
        assert float((game.pos_m[..., :2] / scale - state.pos).abs().max()) < POS_TOL_UNITS
        game.pos_m = torch.cat((state.pos * scale, game.pos_m[..., 2:]), dim=-1)


def test_layer_swap_replaces_the_layer_with_the_filter_off_and_refuses_physics(world):
    w = world
    fitted, identity = _game(w, "3"), _game(w, "3a")
    assert type(fitted._starling) is NusPushLayer and not fitted._starling.model.chain.safety_filter
    assert type(identity._starling) is NusIdentityLayer
    assert _game(w, "4")._starling.model.chain.safety_filter                                   # rung 4: the standard layer, filter on
    with pytest.raises(ValueError):
        NusHangarGame(w.cfg("4").replace(**{"starling.backend": "physics"}), w.geo, {**w.rows["3"], "drone": "physics"}, w.starts["starts_units"],
                      w.starts["jitter_m"], w.guards, w.strikes, device="cpu", rules=w.rules)


def test_push_apart_after_a_step_with_the_filter_off(world):
    w = world
    for row_id in ("3a", "3"):
        starts = {k: v.clone() for k, v in w.starts.items()}
        spacing = w.geo.side_m / (2 * (w.guards + w.strikes + 2)) / w.deploy.metres_per_unit             # drones far apart, outside the zone
        starts["starts_units"][:, :, 0] = (torch.arange(w.guards + w.strikes)[None] + 1) * spacing
        starts["starts_units"][:, :, 1] = 0
        starts["starts_units"][:, w.guards] = starts["starts_units"][:, 0] + NEAR_UNITS        # a Strike drone on top of Guard 0
        game = NusHangarGame(w.cfg(row_id), w.geo, w.rows[row_id], starts["starts_units"], starts["jitter_m"], w.guards, w.strikes, device="cpu",
                             rules=w.rules)
        game.step({"guard": torch.zeros(P4_GAMES, w.guards, ACT), "strike": torch.zeros(P4_GAMES, w.strikes, ACT)})
        gap = (game.pos_m[:, w.guards, :2] - game.pos_m[:, 0, :2]).norm(dim=-1)
        assert torch.all(gap >= game.cfg.rules.keepout_strike_m * (1 - POS_TOL_UNITS))


def _scripted_pair(w, row_id, guard, strike, **kw):
    cfg = w.cfg(row_id)
    game = _game(w, row_id, **kw)
    g = players.make_player(guard, "guard", cfg, P4_GAMES, "cpu")
    s = players.make_player(strike, "strike", cfg, P4_GAMES, "cpu")
    return play_match(game, g, s), game.extras()


def test_control_rows_equal_their_partner_rows_game_by_game(world):
    """3a = 2 (an identity drone changes nothing) and 5a = 4 (free height, no jitter changes nothing), on a small CPU batch."""
    w = world
    for first, second in (("2", "3a"), ("4", "5a")):
        for guard, strike in (("ApfGuard", "ApfStrike"), ("ParkedGuard", "strike_straight")):
            a, ax = _scripted_pair(w, first, guard, strike, parked=guard == "ParkedGuard")
            b, bx = _scripted_pair(w, second, guard, strike, parked=guard == "ParkedGuard")
            assert torch.equal(a.outcome, b.outcome) and torch.equal(a.end_step, b.end_step), (first, second, guard, strike)
            assert float((a.closest_cross_m - b.closest_cross_m).abs().max()) <= POS_TOL_UNITS


def test_extras_are_recorded_for_the_first_games_only(world):
    w = world
    res, ex = _scripted_pair(w, "4", "ApfGuard", "ApfStrike", video_slots=2)
    assert ex["video"].shape[:2] == (w.cfg("4").game_ticks() + 1, 2)
    assert torch.all(torch.isfinite(ex["any_min_3d_m"])) and torch.all(ex["team_min_3d_m"] >= ex["any_min_3d_m"])
    assert float(ex["corr_count"].sum()) >= EXACT and torch.all(ex["guard0_drift_m"] >= 0)


# ------------------------------------------------------------------------------------------------ players
def test_ported_controllers_equal_nusapf_at_every_sample_and_hold_between(world):
    from svg_training.nus.apf import NusApf
    w = world
    game = _game(w, "2")
    apf = NusApf(w.rules, w.deploy)
    for team, cls in (("guard", players.ApfGuard), ("strike", players.ApfStrike)):
        player = cls(team, w.cfg("2"), P4_GAMES, "cpu")
        obs = game.reset()
        player.reset(torch.ones(P4_GAMES, dtype=torch.bool))
        last = None
        for tick in range(w.deploy.hold_ticks + 1):
            action = player.act(obs[team])
            pos = player._positions(obs[team])
            if tick % w.deploy.hold_ticks == 0:
                want = apf.actions(team, pos) / player.speed_units
                assert float((action[..., :2] - want.clamp(-1, 1)).abs().max()) < POS_TOL_UNITS
                last = action
            else:
                assert torch.equal(action, last)
            out = game.step({"guard": torch.zeros(P4_GAMES, w.guards, ACT), "strike": torch.zeros(P4_GAMES, w.strikes, ACT)})
            obs = out.obs


def test_players_meet_the_strategy_contract_and_bindings_load_their_folders(world):
    from svg_training.core.strategy import check_strategy
    w = world
    game = _game(w, "2")
    for name, team in (("ApfGuard", "guard"), ("ApfStrike", "strike"), ("ParkedGuard", "guard"), ("G19", "guard"), ("S20", "strike"), ("P3G", "guard"),
                       ("P3S", "strike")):
        check_strategy(players.make_player(name, team, w.cfg("2"), P4_GAMES, "cpu"), game, steps=TICKS_FEW)
    assert players.deploy_path_of("G19") == w.folder / "nus_deploy_ref.toml" and players.deploy_path_of("P3G") == w.folder / "nus_deploy.toml"
    folders = {n: players.make_player(n, t, w.cfg("2"), P4_GAMES, "cpu").actor.meta["path"] for n, t in (("G19", "guard"), ("S20", "strike"), ("P3G", "guard"), ("P3S", "strike"))}
    assert {n: p.rsplit("/", 1)[1] for n, p in folders.items()} == {n: v for n, v in __import__("_nus_phase4_fixture").WEIGHT_NAMES.items()}
    with pytest.raises(ValueError):
        players.make_player("G19", "strike", w.cfg("2"), P4_GAMES, "cpu")
    with pytest.raises(ValueError):
        players.make_player("strike_flank", "strike", w.cfg("2"), P4_GAMES, "cpu", jump_hold_ticks=w.deploy.hold_ticks)


def test_each_name_means_the_same_player_in_the_replica_and_the_game(world):
    """The converted policy's first sample in the game equals its replica action on the same start (rows 1 and 2 play one player)."""
    w = world
    game = _game(w, "2")
    obs = game.reset()
    for name in ("G19", "P3S"):
        team = players.TEAM_OF[name]
        in_game = players.make_player(name, team, w.cfg("2"), P4_GAMES, "cpu")
        in_game.reset(torch.ones(P4_GAMES, dtype=torch.bool))
        command = in_game.act(obs[team])[..., :2] * in_game.speed_units
        replica = players.ReplicaPlayer(name)
        state = ReplicaState(pos=w.starts["starts_units"].clone(), prev_pos=w.starts["starts_units"].clone(), reached=torch.zeros(P4_GAMES),
                             step=torch.zeros(P4_GAMES, dtype=torch.long))
        observation = w.sim.observe(state)
        rows = slice(0, w.guards) if team == "guard" else slice(w.guards, w.guards + w.strikes)
        assert float((command - replica(observation[:, rows], state.pos)).abs().max()) < POS_TOL_UNITS


# ------------------------------------------------------------------------------------------------ the replica engine and the metrics
def test_replica_engine_equals_play_arm_exactly_on_the_same_starts(world):
    from svg_training.nus.apf import NusApf
    from svg_training.nus.outcome import play_arm
    w = world
    sim, apf = w.sim, NusApf(w.rules, w.deploy)
    guard, strike = players.ReplicaPlayer("P3G"), players.ReplicaPlayer("ApfStrike")
    arm = play_arm(sim, apf, "guard", w.starts["starts_units"], guard.actor.act_units)
    res, extras = ladder.play_replica(sim, guard, strike, w.starts["starts_units"], w.deploy.metres_per_unit, w.deploy.seconds_per_step,
                                      w.deploy.hold_ticks, EXACT, (EXACT, EXACT), slots=2)
    assert torch.equal(res.outcome == 1, arm.reached)
    steps = torch.where(arm.reached, arm.first_reach_step, torch.full_like(arm.first_reach_step, w.rules.episode_steps))
    assert torch.equal(res.end_step, steps * w.deploy.hold_ticks)
    assert extras.positions_units.shape[1] == 2


def test_replica_closest_approach_by_hand(world):
    """Guard 0 parked at the zone centre; one Strike drone placed on a known spot with a zero action: the closest approach is that distance."""
    w = world
    starts = w.starts["starts_units"].clone()
    starts[:, :] = starts[:, :1] + FAR * torch.arange(w.guards + w.strikes)[None, :, None]   # every drone far from every other
    starts[:, 0] = 0
    starts[:, w.guards] = torch.tensor(HAND)
    class Zero:
        parks_guard0 = False

        def __init__(self, team):
            self.team = team

        def __call__(self, obs, pos):
            return torch.zeros(obs.shape[0], obs.shape[1], 2)

    res, extras = ladder.play_replica(w.sim, Zero("guard"), Zero("strike"), starts, w.deploy.metres_per_unit, w.deploy.seconds_per_step,
                                      w.deploy.hold_ticks, EXACT, (EXACT, EXACT))
    assert float(res.closest_cross_m.min()) == pytest.approx(w.deploy.metres_per_unit * HAND_DISTANCE, rel=POS_TOL_UNITS)


def test_pair_row_rates_intervals_and_the_split_trigger(world):
    w = world
    res, ex = _scripted_pair(w, "2", "ApfGuard", "ApfStrike")
    row = ladder.pair_row(res, ex, w.settings, w.geo, EXACT, EXACT, "ApfGuard", "ApfStrike", None, False, w.guards + w.strikes)
    assert row["reach"]["k"] + int(row["hold_rate"] * row["games"] + ROUND_HALF) == row["games"]
    assert row["reach"]["ci_low"] <= row["reach"]["rate"] <= row["reach"]["ci_high"]
    base = {"guard": "ApfGuard", "strike": "ApfStrike", "reach": rate(*INTERVAL_BASE)}
    inside = {"guard": "ApfGuard", "strike": "ApfStrike", "reach": rate(*INTERVAL_INSIDE)}
    outside = {"guard": "ApfGuard", "strike": "ApfStrike", "reach": rate(*INTERVAL_OUTSIDE)}
    assert not ladder.split_trigger([base], [inside])["fires"] and ladder.split_trigger([base], [outside])["fires"]
    parked = [{"guard": "ParkedGuard", "strike": "ApfStrike", "hold_rate": PARKED_HOLD}]
    assert ladder.parked_hold_reading(parked, w.settings["ladder"]["parked_stop_hold"])["stop"]


# ------------------------------------------------------------------------------------------------ privacy: derived values, record text
def test_derived_values_are_protected_and_text_collisions_read_at_the_local_value(world):
    from svg_training.nus import outputs
    w = world
    protected = outputs.protected_numbers(w.folder / "nus_rules.toml", w.folder / "nus_deploy.toml", hangar_path=w.folder / "nus_hangar.toml")
    scale = w.deploy.metres_per_unit
    for value in (w.hangar_value, w.rules.area_radius * scale, w.geo.ring_m, w.geo.keepout_strike_m, w.geo.strike_mps, w.geo.game_seconds):
        assert value in protected or float(format(value, ".6g")) in protected
        with pytest.raises(ValueError):
            outputs.write_record(w.folder / "bad.json", {"x": value}, w.folder / "nus_rules.toml", deploy_path=w.folder / "nus_deploy.toml",
                                 hangar_path=w.folder / "nus_hangar.toml")
        with pytest.raises(ValueError):
            outputs.check_payload({"x": value * (1 + w.settings["ladder"]["near_equal_relative"] / WIDE)}, protected)   # near-equality
        assert ladder.fmt(value, protected) == ladder.LOCAL_VALUE
    ok = outputs.write_record(w.folder / "ok.json", {"rate": "9/10", "n": P4_GAMES}, w.folder / "nus_rules.toml", deploy_path=w.folder / "nus_deploy.toml",
                              hangar_path=w.folder / "nus_hangar.toml")
    assert json.loads(ok.read_text())["hangar_sha256"]
    assert ladder.fmt(None, protected) == "n/a"
    with pytest.raises(ValueError):
        ladder.check_text(f"the arena side is {w.hangar_value!r} m", protected)


def test_paired_against_nearest_falls_back_to_the_row_before(tmp_path):
    import numpy as np
    near, far, now = tmp_path / "near.npz", tmp_path / "far.npz", tmp_path / "now.npz"
    np.savez(near, A__B__outcome=np.array([0, 1, 1, 1]))
    np.savez(far, A__B__outcome=np.array([0, 0, 0, 0]), C__D__outcome=np.array([1, 1, 0, 0]))
    np.savez(now, A__B__outcome=np.array([0, 1, 1, 0]), C__D__outcome=np.array([1, 0, 0, 0]), E__F__outcome=np.array([0, 0, 0, 0]))
    pairs = [{"guard": "A", "strike": "B"}, {"guard": "C", "strike": "D"}, {"guard": "E", "strike": "F"}]
    out = ladder.paired_against_nearest(pairs, [np.load(near), np.load(far)], np.load(now))
    assert [r["paired_change"] for r in out] == [1, 1, None]    # A-B against the nearer row, C-D only in the farther row, E-F in neither


def test_tables_for_committed_records_leak_no_protected_value(world):
    from svg_training.nus import outputs
    w = world
    protected = outputs.protected_numbers(w.folder / "nus_rules.toml", w.folder / "nus_deploy.toml", hangar_path=w.folder / "nus_hangar.toml")
    res, ex = _scripted_pair(w, "4", "ApfGuard", "ApfStrike")
    row = ladder.pair_row(res, ex, w.settings, w.geo, EXACT, EXACT, "ApfGuard", "ApfStrike", None, True, w.guards + w.strikes)
    row["closest_cross_3d"]["min"] = w.geo.keepout_strike_m                      # a pinned value: must read "at the local value"
    text = ladder.rung_table_md([row], protected) + ladder.extras_table_md([row], protected)
    assert ladder.LOCAL_VALUE in text
    ladder.check_text(text, protected)


def test_runner_writes_gates_first_refuses_an_existing_row_and_keeps_markers_out_of_committed_files(world, tmp_path, monkeypatch, capsys):
    import importlib.util
    spec = importlib.util.spec_from_file_location("nus_phase4", ROOT / "scripts" / "nus_phase4.py")
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    w = world
    work = ladder.RUNS_DIR / "nus_port" / "_test_marker_chain"
    monkeypatch.setattr(ladder, "PHASE4_DIR", work)
    monkeypatch.setattr(ladder, "STARTS_FILE", work / "starts.npz")
    monkeypatch.setattr(hangar_mod, "LOCAL_HANGAR", w.folder / "nus_hangar.toml")
    import shutil
    try:
        assert runner.main(["--make-starts"]) == 0
        assert (work / "starts.npz").exists()
        for row_id in ("1", "2", "3a", "4", "5", "6"):
            args = ["--row", row_id, "--games", str(P4_GAMES), "--out", str(work / f"row_{row_id}"), "--no-videos", "--accept-long",
                    "--pairs", "ApfGuard:ApfStrike,ParkedGuard:ApfStrike,P3G:S20"]
            code = runner.main(args, _torch_world if row_id == "6" else None)      # rung 6: a PyTorch rigid-body world instead of IsaacWorld
            assert code in (0, runner.EXIT_STOP)
            scores = json.loads((work / f"row_{row_id}" / "scores.json").read_text())
            assert len(scores["pairs"]) == THREE and (work / f"row_{row_id}" / "gates.toml").read_text().startswith("#")
            assert "gates = []" in (work / f"row_{row_id}" / "gates.toml").read_text()
            assert runner.main(args) == runner.EXIT_REFUSED                  # a finished row is never overwritten
        videos = ladder.video_clips(*_scripted_pair_for_clips(w), w.geo, 2, False, w.geo.height_m)
        assert all(c["pos_m"].shape[1:] == (w.guards + w.strikes, THREE) for c in videos)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    text = capsys.readouterr().out
    markers = [m for m in marker_strings({**w.rules_values, **{k: v for k, v in w.deploy_values.items() if isinstance(v, float)},
                                          "arena_side_m": w.hangar_value}) if len(m.replace(".", "").replace("e-", "")) > FOUR]
    hits = [m for m in markers if m in text]
    listing = subprocess.run(["git", "ls-files", "-co", "--exclude-standard"], cwd=ROOT, capture_output=True, text=True)
    if listing.returncode == 0:
        for rel in listing.stdout.splitlines():
            path = ROOT / rel
            if path.is_file() and path.suffix in (".py", ".md", ".toml", ".sh", ".json"):
                content = path.read_text(errors="ignore")
                hits += [f"{rel}: {m}" for m in markers if m in content and not rel.startswith("svg_training/tests/_nus") and "tests/" not in rel]
    assert not hits, hits


def _torch_world(n, m, params, device):
    from svg_training.models.rigid_body import TorchRigidBodyWorld
    return TorchRigidBodyWorld(n, m, params.airframe, params.physics_dt_s, device)


def _scripted_pair_for_clips(w):
    res, ex = _scripted_pair(w, "2", "ApfGuard", "ApfStrike", video_slots=2)
    return res, ex


# ------------------------------------------------------------------------------------------------ committed text check (D8): retired
# Retired 18 Nov 2026 (owner: NUS agreed that its game settings and our results on its code may be published; STANDARDS section 2).
# The check scanned the Phase 4 records, ledger rows, the summary page and HANDOFF for local values; documents may now state them.
# What stays: the local files are the only place the code reads values from (G1), no literals in partner-facing code (G2), the
# record writer and the table formatter keep refusing or marking local values (G3, the two tests above), the marker chain (G4), and
# NUS's source code stays out of the repository (tests/test_partner_privacy.py).


# ------------------------------------------------------------------------------------------------ the reference deploy file (W3)
def test_reference_deploy_script_refuses_outside_local_and_a_differing_key(tmp_path, monkeypatch):
    import contextlib
    import importlib.util
    import io

    from _nus_markers import FAKE_COMMIT, write_fake_policy_sources, write_synthetic_checkpoint
    from _nus_phase4_fixture import p4_deploy_values, WEIGHT_NAMES
    from svg_training.nus import deploy as deploy_mod
    spec = importlib.util.spec_from_file_location("nus_make_local_deploy", ROOT / "scripts" / "nus_make_local_deploy.py")
    make = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(make)
    values = p4_deploy_values()
    clone = tmp_path / "clone"
    write_fake_policy_sources(clone, values)
    checkpoint = write_synthetic_checkpoint(tmp_path / "ckpt", "guard", deploy_values=values)
    local = tmp_path / "local"
    monkeypatch.setattr(make, "LOCAL_OUT_DIR", local)
    common = ["--clone", str(clone), "--geometry-from", str(checkpoint), "--metres-per-unit", repr(values["metres_per_unit"]),
              "--seconds-per-step", repr(values["seconds_per_step"]), "--hold-ticks", str(values["hold_ticks"]),
              "--flying-height-m", repr(values["flying_height_m"]), "--guard-weights", WEIGHT_NAMES["G19"], "--strike-weights", WEIGHT_NAMES["S20"]]
    with contextlib.redirect_stdout(io.StringIO()):
        assert make.main(common + ["--out", str(local / "ref.toml")]) == 0
        with pytest.raises(SystemExit, match="refusing"):
            make.main(common + ["--out", str(tmp_path / "elsewhere.toml")])
        first = local / "first.toml"
        make.main(["--clone", str(clone), "--geometry-from", str(checkpoint), "--metres-per-unit", repr(values["metres_per_unit"]),
                   "--seconds-per-step", repr(values["seconds_per_step"]), "--hold-ticks", str(values["hold_ticks"]),
                   "--flying-height-m", repr(values["flying_height_m"]), "--guard-weights", WEIGHT_NAMES["P3G"], "--strike-weights", WEIGHT_NAMES["P3S"],
                   "--out", str(first)])
        assert make.main(common + ["--out", str(local / "same.toml"), "--same-as", str(first)]) == 0      # only the weights folders differ
        changed = common[:common.index("--flying-height-m") + 1] + [repr(values["flying_height_m"] + values["metres_per_unit"])] + common[common.index("--flying-height-m") + 2:]
        with pytest.raises(SystemExit, match="differ"):
            make.main(changed + ["--out", str(local / "other.toml"), "--same-as", str(first)])
    a, b = deploy_mod.load_deploy(local / "same.toml"), deploy_mod.load_deploy(first)
    assert {k: getattr(a, k) for k in deploy_mod.DEPLOY_KEYS if not k.endswith("weights")} == {k: getattr(b, k) for k in deploy_mod.DEPLOY_KEYS if not k.endswith("weights")}


# ------------------------------------------------------------------------------------------------ videos (D6)
def test_slot_picker_and_two_clips_per_pair_are_rendered(world, tmp_path):
    from svg_training.core.rewards import GUARD_WIN, STRIKE_WIN
    from svg_training.viz.replay import render_replay
    w = world
    picks = ladder.pick_video_slots(torch.tensor([GUARD_WIN, STRIKE_WIN, GUARD_WIN, STRIKE_WIN]), P4_GAMES)
    assert picks == [(1, "strike_win"), (0, "hold")]                           # the first Strike win, then the first hold
    assert ladder.pick_video_slots(torch.tensor([GUARD_WIN, GUARD_WIN]), P4_GAMES) == [(0, "hold")]
    res, ex = _scripted_pair(w, "2", "ApfGuard", "ApfStrike", video_slots=P4_GAMES)
    clips = ladder.video_clips(res, ex, w.geo, P4_GAMES, False, w.geo.height_m)
    assert clips and all(c["pos_m"].shape[0] == c["end_step"] + 1 for c in clips)
    out = tmp_path / "runs" / "videos"
    for clip in clips:
        rec = ladder.clip_recording(clip, w.geo, w.guards, w.strikes, "ApfGuard", "ApfStrike", "marker", 0)
        path = render_replay(rec, out / f"{clip['kind']}.mp4", speed=w.deploy.hold_ticks, fps=THREE, dpi=ROUND_DPI)
        assert path.stat().st_size > EXACT
    assert len(list(out.glob("*.mp4"))) == len(clips)


def test_estimate_only_runs_nothing_on_a_replica_row(world, monkeypatch, capsys):
    """--estimate-only on a replica-engine row (1, 2.1, 2.2) used to run the whole row (found 19 Nov 2026 on a fresh clone): the
    estimate block is skipped for replica rows. It now stops before writing anything, with the same exit code as on the other rows."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("nus_phase4", ROOT / "scripts" / "nus_phase4.py")
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    work = ladder.RUNS_DIR / "nus_port" / "_test_estimate_only"
    monkeypatch.setattr(ladder, "PHASE4_DIR", work)
    monkeypatch.setattr(hangar_mod, "LOCAL_HANGAR", world.folder / "nus_hangar.toml")
    import shutil
    try:
        assert runner.main(["--row", "1", "--estimate-only", "--out", str(work / "row_1")]) == runner.EXIT_LONG
        assert not (work / "row_1").exists()
        assert "estimate only" in capsys.readouterr().err
    finally:
        shutil.rmtree(work, ignore_errors=True)
