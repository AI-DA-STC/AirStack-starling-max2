"""STE task L0.10: the scripted players of the study (PLAN section 4, row L0.10).

New Guard players: ``guard_parked_centre``, ``guard_parked_ring``. New Strike players: ``strike_high``, ``strike_low``,
``strike_sacrifice``, ``strike_converge``. Each test pins the player's defining behaviour on hand-built observations or in
a short game; the smoke matrix plays every study Guard against every study Strike at 1v1, 2v1, 3v3 and 5v3, with the
study tag off and on, on the pure path and the Starling layer, all pairs batched in one game per case (each game is
driven by its own pair, so no Python loop runs over games). CPU, small game counts.
"""
import math
import re
from pathlib import Path

import pytest
import torch

from svg_training.core.game import STRIKE_WIN, SvgGame
from svg_training.core.game_config import load_game_cfg
from svg_training.core.observations import OBS_DIM, ObsView
from svg_training.core.scenarios import Scenario
from svg_training.opponents import scripted
from svg_training.opponents.scripted import REGISTRY, make_strategy
from svg_training.ste.game_spec import load_game_spec

ROOT = Path(__file__).resolve().parents[1]
SPEC = load_game_spec()[0]
CFG = load_game_cfg(use_local=False)[0]
STARLING = CFG.replace(**{"starling.enabled": True, "starling.filter_iterations": 20})
V = ObsView()
PG = CFG.pad_guards
STUDY_GUARDS = ("guard_parked_centre", "guard_parked_ring", "guard_mirror", "guard_mark_edge", "guard_field")
STUDY_STRIKES = ("strike_straight", "strike_flank", "strike_high", "strike_low", "strike_sacrifice", "strike_converge")
NEW = ("guard_parked_centre", "guard_parked_ring", "strike_high", "strike_low", "strike_sacrifice", "strike_converge")
SIZES = ((1, 1), (2, 1), (3, 3), (5, 3))


def drone(team, pos, vel=(0.0, 0.0), r=1.6, z=1.2, half=3.25):
    """One drone's observation: pos (x, y) relative to the zone centre, own height z (world)."""
    o = torch.zeros(OBS_DIM)
    o[0:2], o[2] = torch.tensor(pos), z
    o[3:5] = torch.tensor(vel)
    o[V.zone_radius], o[V.arena_half], o[V.time_left] = r, half, 30.0
    o[V.team] = -1.0 if team == "guard" else 1.0
    o[V.alive] = 1.0
    return o


def put(o, slot, rel_pos, rel_vel=(0.0, 0.0)):
    s = V.slot(slot)
    o[s.start:s.start + 2] = torch.tensor(rel_pos)
    o[s.start + 3:s.start + 5] = torch.tensor(rel_vel)
    o[s.start + 6] = 1.0


def team_obs(team, positions, others=(), z=None):
    """A whole team's observation [1, k, OBS_DIM]: each drone sees its team-mates and ``others`` (opposite team,
    positions relative to the zone centre) in the right slots. Guard slots 0.., Strike slots PG.."""
    k = len(positions)
    zs = z if z is not None else [1.2] * k
    rows = [drone(team, p, z=zs[i]) for i, p in enumerate(positions)]
    mate0, other0 = (0, PG) if team == "guard" else (PG, 0)
    for i, o in enumerate(rows):
        for j, q in enumerate(positions):
            if j != i:
                put(o, mate0 + j, (q[0] - positions[i][0], q[1] - positions[i][1]))
        for j, q in enumerate(others):
            put(o, other0 + j, (q[0] - positions[i][0], q[1] - positions[i][1]))
    return torch.stack(rows)[None]


def mk(name, team, cfg=CFG, n=1):
    return make_strategy(name, team, cfg, n, "cpu", 0)


def bearing(xy):
    return math.atan2(float(xy[1]), float(xy[0]))


# ------------------------------------------------------------------------------------------------ registry
def test_the_new_players_are_registered_for_their_team():
    for name in NEW:
        team = "guard" if name.startswith("guard") else "strike"
        assert make_strategy(name, team, CFG, 1, "cpu", 0).team == team
        with pytest.raises(ValueError):
            make_strategy(name, "strike" if team == "guard" else "guard", CFG, 1, "cpu", 0)
    assert set(STUDY_GUARDS + STUDY_STRIKES) <= set(REGISTRY)


# ------------------------------------------------------------------------------------------------ parked Guards
def test_parked_centre_ignores_strikes_and_is_zero_at_the_centre():
    """Guard 0 steers to the centre; every other Guard holds where it is (zero command), LEAD CALL 21 Nov 2026."""
    gen = torch.Generator().manual_seed(0)
    at_centre = team_obs("guard", [(0.0, 0.0)])
    assert torch.equal(mk("guard_parked_centre", "guard").act(at_centre), torch.zeros(1, 1, 4))
    off = team_obs("guard", [(0.5, -0.3), (-0.2, 0.6)])
    base = mk("guard_parked_centre", "guard").act(off)
    assert torch.equal(base[0, 1], torch.zeros(4))                                  # Guard 1 holds its start
    for _ in range(5):                                       # any Strike drones anywhere: the same command
        strikes = [tuple((torch.rand(2, generator=gen) * 6 - 3).tolist()) for _ in range(3)]
        assert torch.equal(mk("guard_parked_centre", "guard").act(team_obs("guard", [(0.5, -0.3), (-0.2, 0.6)], strikes)),
                           base)
    assert torch.allclose(base[0, 0, :2], -torch.tensor([0.5, -0.3]) / math.hypot(0.5, 0.3), atol=1e-5)
    assert torch.all(base[..., 2:] == 0)


def test_parked_ring_stations_are_fixed_by_index_and_zero_there():
    for g in (1, 2, 3, 5):
        ring_m = mk("guard_parked_ring", "guard").ring_radius_m(g)
        stations = [(ring_m * math.cos(2 * math.pi * i / g), ring_m * math.sin(2 * math.pi * i / g)) for i in range(g)]
        a = mk("guard_parked_ring", "guard").act(team_obs("guard", stations, [(2.75, 0.0)]))
        assert a.abs().max() < 1e-5, g
    # Guard 1 of three is out: Guards 0 and 2 keep their stations (no re-spacing after a loss)
    ring_m = scripted.PARK_RING_M
    stations = [(ring_m * math.cos(2 * math.pi * i / 3), ring_m * math.sin(2 * math.pi * i / 3)) for i in range(3)]
    obs = team_obs("guard", stations)
    obs[0, 1] = 0.0
    obs[0, 1, V.team] = -1.0
    for o in (obs[0, 0], obs[0, 2]):
        o[V.slot(1).start:V.slot(1).stop] = 0.0
    a = mk("guard_parked_ring", "guard").act(obs)
    assert a.abs().max() < 1e-5
    # off station: steers to it, at Guard speed, and ignores Strike drones
    obs = team_obs("guard", [(0.0, 0.0), (0.0, 0.0), (0.0, 0.0)], [(1.0, 1.0)])
    a = mk("guard_parked_ring", "guard").act(obs)[0, :, :2]
    for i in range(3):
        want = torch.tensor([math.cos(2 * math.pi * i / 3), math.sin(2 * math.pi * i / 3)])
        assert torch.allclose(a[i], want, atol=1e-5)


@pytest.mark.parametrize("name", ["guard_parked_centre", "guard_parked_ring"])
@pytest.mark.parametrize("starling", [False, True])
def test_parked_guards_stop_and_stay(name, starling):
    """In a game against Strike drones that stand still far away, a parked Guard team reaches its stations and its
    command stays zero from then on (one Guard: no team-mate for the filter to push against)."""
    sc = Scenario("park", 6.5, (0.0, 0.0), 1.6, ((0.3, -0.4), (-3.0, -3.0)))
    cfg = STARLING if starling else CFG
    g = SvgGame(cfg, 2, 1, 1, device="cpu", seed=0, scenario=sc)
    guard = make_strategy(name, "guard", cfg, 2, "cpu", 0)
    obs = g.reset()
    for _ in range(200):
        out = g.step({"guard": guard.act(obs["guard"]), "strike": torch.zeros(2, 1, 4)})
        obs = out.obs
    park = g.pos_m[:, 0, :2].clone()
    for _ in range(40):
        a = guard.act(obs["guard"])
        assert a.abs().max() < 0.05
        obs = g.step({"guard": a, "strike": torch.zeros(2, 1, 4)}).obs
    assert (g.pos_m[:, 0, :2] - park).norm(dim=-1).max() < 0.02
    target = torch.zeros(2) if name == "guard_parked_centre" else torch.tensor([scripted.GuardParkedRing.RING_M, 0.0])
    assert (park - target).norm(dim=-1).max() < 0.05


def disc_ring_cfg(starling: bool):
    """The lab arena of the sheet with the new start mode (Guards in the 0.8 m disc), as in the smoke matrix."""
    return matrix_cfg(starling, False).replace(**{"rules.game_steps": 2400})


@pytest.mark.parametrize("starling", [False, True])
def test_parked_centre_team_settles_and_never_moves(starling):
    """Three Guards from the start disc, Strike drones still on the ring: Guard 0 settles at the centre, the others hold
    their starts (their command is zero on every step). Once settled no Guard moves: no jostling on the Starling layer."""
    cfg = disc_ring_cfg(starling)
    g = SvgGame(cfg, 8, 3, 3, device="cpu", seed=3, band=0)
    guard = make_strategy("guard_parked_centre", "guard", cfg, 8, "cpu", 0)
    obs = g.reset()
    start = g.pos_m[:, :3, :2].clone()
    still = torch.zeros(8, 3, 4)
    for k in range(400):
        a = guard.act(obs["guard"])
        assert torch.all(a[:, 1:] == 0)
        obs = g.step({"guard": a, "strike": still}).obs
    park = g.pos_m[:, :3, :2].clone()
    for _ in range(60):
        obs = g.step({"guard": guard.act(obs["guard"]), "strike": still}).obs
    assert (g.pos_m[:, :3, :2] - park).norm(dim=-1).max() < 0.02                 # settled: nothing moves
    assert park[:, 0].norm(dim=-1).max() < 0.05                                   # Guard 0 at the centre
    if not starling:                                                              # pure path: team-mates pass, so the
        assert torch.equal(park[:, 1:], start[:, 1:])                             # others never left their starts


def test_parked_ring_radius_keeps_neighbours_apart():
    """Ring radius = max(0.8 m, chord rule): neighbours at least the filter distance + 0.05 m apart (LEAD CALL 21 Nov
    2026). Five Guards: neighbours >= 1.15 m apart; one to three Guards: 0.8 m."""
    p = mk("guard_parked_ring", "guard")
    need = CFG.rules.keepout_guard_m + scripted.PARK_RING_SPACING_MARGIN_M
    for g in (1, 2, 3):
        assert p.ring_radius_m(g) == scripted.PARK_RING_M
    r5 = p.ring_radius_m(5)
    assert 2 * r5 * math.sin(math.pi / 5) >= need - 1e-9 and r5 > scripted.PARK_RING_M
    stations = [(r5 * math.cos(2 * math.pi * i / 5), r5 * math.sin(2 * math.pi * i / 5)) for i in range(5)]
    assert mk("guard_parked_ring", "guard").act(team_obs("guard", stations)).abs().max() < 1e-5
    gaps = [math.dist(stations[i], stations[(i + 1) % 5]) for i in range(5)]
    assert min(gaps) >= 1.15 - 1e-6


# ------------------------------------------------------------------------------------------------ height Strikes
@pytest.mark.parametrize("name,sign", [("strike_high", 1.0), ("strike_low", -1.0)])
def test_height_strike_climbs_or_descends_first(name, sign):
    lo, hi = CFG.arena.height_band_m
    s = mk(name, "strike", STARLING)
    a = s.act(team_obs("strike", [(-2.75, 0.0)], z=[1.2]))[0, 0]
    assert a[2] == pytest.approx(sign) and a[:2].norm() < 1e-6                     # all vertical while far off the edge
    edge = (hi if sign > 0 else lo) - sign * scripted.BAND_INSET_M
    a = s.act(team_obs("strike", [(-2.75, 0.0)], z=[edge]))[0, 0]
    assert abs(a[2]) < 1e-5 and torch.allclose(a[:2], torch.tensor([1.0, 0.0]), atol=1e-5)
    assert a.norm() <= 1.0 + 1e-6


@pytest.mark.parametrize("name", ["strike_high", "strike_low"])
def test_height_strike_is_straight_on_the_pure_path(name):
    """The pure path holds every drone at the start height (vz is ignored), so these play as strike_straight there."""
    obs = team_obs("strike", [(-2.0, 1.0), (1.5, 2.0)], [(0.0, 0.5)])
    assert torch.equal(mk(name, "strike").act(obs), mk("strike_straight", "strike").act(obs))


@pytest.mark.parametrize("name,top", [("strike_high", True), ("strike_low", False)])
def test_height_strike_holds_the_band_edge_on_approach(name, top):
    """Starling layer, one Strike drone from the ring, the Guard far off in a corner: from 0.5 m outside the zone edge
    to the step it enters the zone, its height is within 0.1 m of its band-edge target."""
    lo, hi = CFG.arena.height_band_m
    target = hi - scripted.BAND_INSET_M if top else lo + scripted.BAND_INSET_M
    sc = Scenario("edge", 6.5, (0.0, 0.0), 1.6, ((3.0, 3.0), (-2.75, 0.0)))
    g = SvgGame(STARLING, 1, 1, 1, device="cpu", seed=0, scenario=sc)
    s = make_strategy(name, "strike", STARLING, 1, "cpu", 0)
    obs = g.reset()
    heights = []
    for _ in range(400):
        p = g.pos_m[0, 1]
        if p[:2].norm() <= 1.6 + 0.5:
            heights.append(float(p[2]))
        out = g.step({"guard": torch.zeros(1, 1, 4), "strike": s.act(obs["strike"])})
        obs = out.obs
        if out.done.any():
            break
    assert out.outcome[0] == STRIKE_WIN
    assert heights and max(abs(h - target) for h in heights) < 0.1


# ------------------------------------------------------------------------------------------------ sacrifice
def test_sacrifice_decoy_heads_for_the_nearest_guard_the_others_take_the_far_side():
    """The others enter opposite the bearing of the Guard drone that Strike 0 draws (LEAD CALL 21 Nov 2026), not
    opposite Strike 0's own bearing. Here the drawn Guard is at 66.8 degrees, so the entry bearing is 246.8 degrees."""
    guards = [(0.3, 0.7), (-0.5, -0.5)]                      # Guard 0 is the nearer to Strike 0
    entry = math.atan2(-0.7, -0.3)                           # opposite the drawn Guard's bearing
    strikes = [(2.75, 0.0), (2.75 * math.cos(entry), 2.75 * math.sin(entry)), (-2.75, 0.0)]
    a = mk("strike_sacrifice", "strike").act(team_obs("strike", strikes, guards))[0, :, :2]
    to_guard = torch.tensor([0.3 - 2.75, 0.7])
    assert torch.allclose(a[0], to_guard / to_guard.norm(), atol=1e-5)            # Strike 0: at the nearest Guard
    inward = -torch.tensor([math.cos(entry), math.sin(entry)])
    assert torch.allclose(a[1], inward, atol=1e-5)                                 # Strike 1 at the entry bearing: in
    # Strike 2 at -x (opposite Strike 0, but 66.8 degrees short of the entry bearing): circles anticlockwise, not in
    assert a[2, 1] < -0.9 and abs(float(a[2, 0])) < 0.3


def test_sacrifice_without_a_decoy_or_alone_goes_straight():
    strikes = [(2.75, 0.0), (0.0, 2.75), (-2.75, 0.0)]
    obs = team_obs("strike", strikes, [(0.5, 0.0)])
    obs[0, 0] = 0.0                                          # the decoy is out: the gap is open, everyone goes in
    obs[0, 0, V.team] = 1.0
    for o in (obs[0, 1], obs[0, 2]):
        o[V.slot(PG).start:V.slot(PG).stop] = 0.0
    a = mk("strike_sacrifice", "strike").act(obs)
    assert torch.equal(a[0, 1:], mk("strike_straight", "strike").act(obs)[0, 1:]) and torch.all(a[0, 0] == 0)
    lone = team_obs("strike", [(2.0, 1.0)], [(0.5, 0.0)])
    assert torch.equal(mk("strike_sacrifice", "strike").act(lone), mk("strike_straight", "strike").act(lone))
    no_guard = team_obs("strike", strikes)                  # no live Guard drone: the decoy goes for the zone too
    a = mk("strike_sacrifice", "strike").act(no_guard)
    assert torch.allclose(a[0, 0, :2], torch.tensor([-1.0, 0.0]), atol=1e-5) and torch.isfinite(a).all()


# ------------------------------------------------------------------------------------------------ converge
def test_converge_arrivals_are_together_from_spread_bearings():
    """Three Strike drones start bunched (bearings 90, 110 and 130 degrees on the ring), the one Guard sits in a corner.
    They spread to three bearings a third of a turn apart, then run in together: when the first enters the zone, every
    Strike drone is within 0.15 m of the zone edge (0.3 s at Strike speed, the stated window)."""
    ring = 2.75
    starts = tuple((ring * math.cos(math.radians(d)), ring * math.sin(math.radians(d))) for d in (90, 110, 130))
    sc = Scenario("converge", 6.5, (0.0, 0.0), 1.6, ((3.0, -3.0),) + starts)
    for cfg in (CFG, STARLING):
        g = SvgGame(cfg, 1, 1, 3, device="cpu", seed=0, scenario=sc)
        s = make_strategy("strike_converge", "strike", cfg, 1, "cpu", 0)
        obs = g.reset()
        for _ in range(1200):
            before = g.pos_m[0, 1:, :2].clone()
            out = g.step({"guard": torch.zeros(1, 1, 4), "strike": s.act(obs["strike"])})
            obs = out.obs
            if out.done.any():
                break
        assert out.outcome[0] == STRIKE_WIN, cfg.starling.enabled
        last = before                                               # positions at the start of the winning step
        edge = last.norm(dim=-1) - 1.6
        assert edge.max() < 0.15, (cfg.starling.enabled, edge)
        angles = sorted(bearing(p) % (2 * math.pi) for p in last)
        gaps = [b - a for a, b in zip(angles, angles[1:])] + [angles[0] + 2 * math.pi - angles[-1]]
        assert min(gaps) > 2 * math.pi / 3 - 0.3, (cfg.starling.enabled, gaps)


def test_converge_run_in_goes_on_after_a_loss():
    """Study tag on. Strike 0's run-in passes within the tag radius of a still Guard drone set off its line, so Strike 0
    and that Guard drone are tagged during the run-in. The two survivors keep flying in (their distance from the zone
    centre never grows again) and reach the zone; they do not fly back out to spread for two."""
    ring = 2.75
    starts = tuple((ring * math.cos(math.radians(d)), ring * math.sin(math.radians(d))) for d in (90, 110, 130))
    sc = Scenario("loss", 6.5, (0.0, 0.0), 1.6, ((1.5, 1.2),) + starts)
    cfg = CFG.replace(**{"tag.mode": SPEC.value("tag_rule.pairing"), "tag.radius_m": SPEC.value("tag.radius_m")})
    g = SvgGame(cfg, 1, 1, 3, device="cpu", seed=0, scenario=sc)
    s = make_strategy("strike_converge", "strike", cfg, 1, "cpu", 0)
    obs = g.reset()
    tagged_at, rho_after = None, []
    for k in range(1200):
        out = g.step({"guard": torch.zeros(1, 1, 4), "strike": s.act(obs["strike"])})
        obs = out.obs
        if out.done.any():
            break
        if tagged_at is None and out.info["tagged"][0, 1]:
            tagged_at = k
        if tagged_at is not None:
            rho_after.append(g.pos_m[0, 2:, :2].norm(dim=-1).clone())
    assert tagged_at is not None and out.outcome[0] == STRIKE_WIN
    rho = torch.stack(rho_after)
    assert (rho[1:] - rho[:-1]).max() < 1e-4, "a survivor flew back out after the loss"


def test_converge_holds_until_every_strike_is_in_place():
    """One Strike drone in place, the other not at its bearing yet: the placed one holds (zero command), it does not run in
    alone. Both at their bearings: both run in, each at the pace that brings them to the zone edge together."""
    s = mk("strike_converge", "strike")
    stage = s.stage_radius_m(team_obs("strike", [(1.0, 0.0)]))[0, 0].item()
    ready = (stage, 0.0)
    far = (-2.75 * math.cos(0.3), 2.75 * math.sin(0.3))       # not yet at its bearing
    a = s.act(team_obs("strike", [ready, far]))[0]
    assert a[0].abs().max() < 1e-5 and a[1, :2].norm() > 0.5
    there = (-stage, 0.0)
    a = s.act(team_obs("strike", [ready, there]))[0, :, :2]                     # both in place: both run in
    assert torch.allclose(a, torch.tensor([[-1.0, 0.0], [1.0, 0.0]]), atol=1e-5)
    # in place by bearing, at different distances: the nearer one flies slower, so both reach the zone edge together
    r = 1.6
    nearer = (-(r + 0.5 * (stage - r)), 0.0)
    a = s.act(team_obs("strike", [ready, nearer]))[0, :, :2]
    assert torch.allclose(a, torch.tensor([[-1.0, 0.0], [0.5, 0.0]]), atol=1e-5)


# ------------------------------------------------------------------------------------------------ the smoke matrix
class Mixed:
    """One team's players spread over the games: game k is played by ``players[index[k]]``. Every player acts on all
    games and the right one is selected per game (tensor ops; the loop runs over the few players, not the games)."""

    def __init__(self, players, index):
        self.players, self.index = players, index

    def act(self, obs):
        out = obs.new_zeros(*obs.shape[:2], 4)
        for k, p in enumerate(self.players):
            out = torch.where((self.index == k)[:, None, None], p.act(obs), out)
        return out


def matrix_cfg(starling: bool, tag: bool):
    side, radius = SPEC.value("arena.side_m"), SPEC.value("zone.radius_m")
    cfg = (STARLING if starling else CFG).replace(**{
        "arena.bands_m": {"lab": (side, side), "middle": (side, side), "large": (side, side)},
        "arena.zone_radius_frac": (radius / side, radius / side), "arena.zone_wall_margin_m": side / 2,
        "starts.mode": "zone_disc_ring", "rules.game_steps": 120})
    if tag:
        cfg = cfg.replace(**{"tag.mode": SPEC.value("tag_rule.pairing")})
    return cfg


def play_matrix(guards, strikes, starling, tag, steps, per_pair=2, seed=0):
    cfg = matrix_cfg(starling, tag)
    pairs = [(gn, sn) for gn in STUDY_GUARDS for sn in STUDY_STRIKES]
    n = len(pairs) * per_pair
    pair_of = torch.arange(n) // per_pair
    g_index = torch.tensor([STUDY_GUARDS.index(pairs[k][0]) for k in range(len(pairs))])[pair_of]
    s_index = torch.tensor([STUDY_STRIKES.index(pairs[k][1]) for k in range(len(pairs))])[pair_of]
    gp = Mixed([make_strategy(x, "guard", cfg, n, "cpu", seed) for x in STUDY_GUARDS], g_index)
    sp = Mixed([make_strategy(x, "strike", cfg, n, "cpu", seed) for x in STUDY_STRIKES], s_index)
    game = SvgGame(cfg, n, guards, strikes, device="cpu", seed=seed, band=0)
    obs = game.reset()
    ended = torch.zeros(n, dtype=torch.long)
    wins = torch.zeros(n, dtype=torch.long)
    trace = []
    for _ in range(steps):
        a = {"guard": gp.act(obs["guard"]), "strike": sp.act(obs["strike"])}
        for t in a.values():
            assert torch.isfinite(t).all() and t.abs().max() <= 1.0
        out = game.step(a)
        assert (out.info["nonfinite_actions"] == 0).all()
        assert torch.isfinite(game.pos_m).all() and torch.isfinite(out.obs["guard"]).all()
        ended += out.done.long()
        wins += (out.done & (out.outcome == STRIKE_WIN)).long()
        trace.append(out.outcome.clone())
        obs = out.obs
    return pairs, pair_of, ended, wins, torch.stack(trace)


@pytest.mark.parametrize("guards,strikes", SIZES)
@pytest.mark.parametrize("tag", [False, True])
def test_smoke_matrix_pure_path(guards, strikes, tag):
    """Every study Guard against every study Strike (30 pairs, 2 games each), games of 120 ticks, 125 steps: every game
    ends (an outcome is produced) and the auto-reset starts new ones; nothing is non-finite."""
    pairs, pair_of, ended, wins, _ = play_matrix(guards, strikes, False, tag, steps=125)
    assert (ended >= 1).all()


@pytest.mark.parametrize("guards,strikes", SIZES)
@pytest.mark.parametrize("tag", [False, True])
def test_smoke_matrix_starling_layer(guards, strikes, tag):
    """The same on the Starling layer (fitted drone, filter on every pair, 20 sweeps), 1 game per pair, 125 steps."""
    pairs, pair_of, ended, wins, _ = play_matrix(guards, strikes, True, tag, steps=125, per_pair=1)
    assert (ended >= 1).all()


def test_smoke_matrix_is_deterministic():
    a = play_matrix(3, 3, False, True, steps=60, seed=3)
    b = play_matrix(3, 3, False, True, steps=60, seed=3)
    assert torch.equal(a[4], b[4])


def test_a_pair_plays_the_same_alone_as_in_the_batch():
    """Players are per game: game k of the batched matrix equals the same pair played on its own game (seed-for-seed
    the starts differ, so this compares actions on the same observations)."""
    cfg = matrix_cfg(False, True)
    game = SvgGame(cfg, 4, 3, 3, device="cpu", seed=7, band=0)
    obs = game.reset()
    for gn in STUDY_GUARDS:
        whole = make_strategy(gn, "guard", cfg, 4, "cpu", 0).act(obs["guard"])
        part = make_strategy(gn, "guard", cfg, 1, "cpu", 0).act(obs["guard"][2:3])
        assert torch.equal(whole[2:3], part)
    for sn in STUDY_STRIKES:
        whole = make_strategy(sn, "strike", cfg, 4, "cpu", 0).act(obs["strike"])
        part = make_strategy(sn, "strike", cfg, 1, "cpu", 0).act(obs["strike"][2:3])
        assert torch.equal(whole[2:3], part)


# ------------------------------------------------------------------------------------------------ the page
SETTINGS = {"PARK_RING_M": "m", "PARK_RING_SPACING_MARGIN_M": "m", "BAND_INSET_M": "m", "STAND_OFF_M": "m",
            "ENTRY_HALF_ANGLE_DEG": "deg", "GATHER_ANGLE_RAD": "rad", "RADIAL_RAMP_M": "m", "CIRCLE_UNTIL_RAD": "rad",
            "RUN_IN_COMMIT_M": "m"}


def test_the_player_settings_table_equals_the_constants():
    """GAME_SPEC.md "Scripted player settings": one row per behaviour constant of opponents/scripted.py (L0.10), value
    equal to the constant, PROPOSED, source LEAD CALL 21 Nov 2026."""
    text = (ROOT / "ste_learning" / "GAME_SPEC.md").read_text()
    section = text[text.index("## Scripted player settings"):]
    section = section[:section.index("\n## ")] if "\n## " in section[3:] else section
    rows = {}
    for line in section.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")] if line.startswith("|") else []
        if len(cells) == 6 and re.fullmatch(r"`[A-Z_]+`", cells[1]):
            rows[cells[1].strip("`")] = cells
    assert set(rows) == set(SETTINGS)
    for name, cells in rows.items():
        assert float(cells[2].strip("`")) == getattr(scripted, name), name
        assert cells[3] == SETTINGS[name] and cells[4] == "PROPOSED" and "LEAD CALL 21 Nov 2026" in cells[5], name
    assert math.isclose(scripted.ENTRY_HALF_ANGLE_RAD, math.radians(scripted.ENTRY_HALF_ANGLE_DEG))


def test_the_players_are_listed_on_the_game_spec_sheet():
    text = (ROOT / "ste_learning" / "GAME_SPEC.md").read_text()
    section = text[text.index("## Scripted players"):]
    for name in STUDY_GUARDS + STUDY_STRIKES:
        assert re.search(rf"`{name}`", section), name
