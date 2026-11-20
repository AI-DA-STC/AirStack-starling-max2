"""STE task L0.10, start ring (finding L08-F1): starts round the zone, Guard drones in a disc, Strike drones on a ring.

``[starts] mode = "zone_disc_ring"`` (core/arena.py ``draw_starts``): Guard drones uniform in radius inside
``guard_disc_m`` round the zone centre, Strike drones on the circle ``strike_ring_m`` round it, every bearing drawn
uniformly per drone (the hangar game's starts, sheet rows ``starts.*``). The default mode stays "rings" and plays today's
game bit for bit (STANDARDS section 3 rule 1); the L0.9 golden test (``test_game_tag_off_golden.py``) checks the default
against a record from before the tag existed, and the first test here checks that the new keys are not read while the
mode is off.

The ring value 2.75 m is a LEAD CALL (21 Nov 2026, L08-F1), PROPOSED: the hangar's 3.2 m scaled by the arena half-side.
Every number below comes from the sheet (``configs/ste_game.toml``) or the game file, none is typed here.
"""
import math

import pytest
import torch

from svg_training.core.arena import draw_arenas, draw_starts
from svg_training.core.game import SvgGame
from svg_training.core.game_config import load_game_cfg
from svg_training.ste.game_spec import load_game_spec

SPEC = load_game_spec()[0]
BASE = load_game_cfg(use_local=False)[0]
MODE = "zone_disc_ring"
TOL_M = 1e-5            # float32 rounding of a position of a few metres


def lab_cfg(**changes):
    """The game file with the sheet's lab arena fixed (side, zone radius, zone at the arena centre) and the sheet's starts.
    The arena is fixed through today's settings: a band of one width, one zone-radius fraction, and a zone-to-wall margin
    of half the side, so the zone centre can only be the arena centre."""
    side, radius = SPEC.value("arena.side_m"), SPEC.value("zone.radius_m")
    frac = radius / side
    cfg = BASE.replace(**{
        "arena.bands_m": {"lab": (side, side), "middle": (side, side), "large": (side, side)},
        "arena.zone_radius_frac": (frac, frac), "arena.zone_wall_margin_m": side / 2,
        "arena.wall_margin_m": SPEC.value("arena.wall_margin_m"), "arena.start_height_m": SPEC.value("height.start_m"),
        "starts.mode": MODE, "starts.strike_ring_m": SPEC.value("starts.strike_ring_m"),
        "starts.guard_disc_m": SPEC.value("starts.guard_disc_m")})
    return cfg.replace(**changes) if changes else cfg


def limit_m() -> float:
    return SPEC.value("arena.side_m") / 2 - SPEC.value("arena.wall_margin_m")


def check_starts(g: SvgGame, games: torch.Tensor, ring_m: float, disc_m: float) -> None:
    """The starts of ``games`` [N] bool: Strike drones on the ring and inside the keep-in box, Guard drones in the disc."""
    p = g.pos_m[games]
    centre = g.arenas.zone_centre_m[games][:, None, :]
    rho = (p[..., :2] - centre).norm(dim=-1)
    guards, strikes = rho[:, :g.guards], rho[:, g.guards:]
    assert torch.allclose(strikes, torch.full_like(strikes, ring_m), atol=TOL_M)     # the wall clamp changed nothing
    assert guards.max() <= disc_m + TOL_M
    assert p[..., :2].abs().max() <= limit_m() + TOL_M
    assert torch.all(p[..., 2] == SPEC.value("height.start_m"))
    cross = (p[:, :g.guards, None, :] - p[:, None, g.guards:, :]).norm(dim=-1)     # 3-D, Guard x Strike
    assert cross.min() >= ring_m - disc_m - TOL_M


# ------------------------------------------------------------------------------------------------ off = today
def test_the_new_keys_are_not_read_while_the_mode_is_off():
    """Mode "rings" (the default) with the new keys set to other values plays the same game, every output equal."""
    other = BASE.replace(**{"starts.strike_ring_m": 9.5, "starts.guard_disc_m": 0.1})       # made up: must not be read
    assert BASE.starts.mode == other.starts.mode == "rings"
    runs = []
    for cfg in (BASE, other):
        g = SvgGame(cfg, 8, 3, 3, device="cpu", seed=4)
        gen = torch.Generator().manual_seed(9)
        record = [g.reset(seed=4)["strike"].clone(), g.pos_m.clone()]
        for _ in range(40):
            a = {"guard": torch.rand(8, 3, 4, generator=gen) * 2 - 1, "strike": torch.rand(8, 3, 4, generator=gen) * 2 - 1}
            out = g.step(a)
            record += [g.pos_m.clone(), out.outcome.clone(), out.done.clone(), out.obs["guard"].clone(),
                       out.info["start_miss"].clone()]
        runs.append(record)
    assert all(torch.equal(a, b) for a, b in zip(*runs))


def test_an_unknown_mode_still_raises():
    with pytest.raises(ValueError, match="zone_disc_ring"):
        SvgGame(BASE.replace(**{"starts.mode": "nope"}), 2, 1, 1, device="cpu")
    ar = draw_arenas(BASE.arena, 2, torch.Generator().manual_seed(0), "cpu", 0)
    with pytest.raises(ValueError, match="zone_disc_ring"):
        draw_starts(BASE.replace(**{"starts.mode": "nope"}), ar, 1, 1, torch.Generator())


# ------------------------------------------------------------------------------------------------ the ring fits
def test_the_ring_fits_the_keep_in_box_on_every_bearing():
    """The worst bearing is along an axis: the ring's x or y equals its radius there. 0.1 degree steps."""
    ring_m = SPEC.value("starts.strike_ring_m")
    bearings = torch.arange(0, 3600, dtype=torch.float64) * (math.pi / 1800)
    reach = ring_m * torch.maximum(bearings.cos().abs(), bearings.sin().abs())
    assert reach.max() <= limit_m()
    assert math.isclose(limit_m() - reach.max().item(), limit_m() - ring_m)                 # 0.25 m on the axes


@pytest.mark.parametrize("guards,strikes", [(1, 1), (2, 1), (3, 3), (5, 3)])
def test_every_start_lies_on_the_ring_inside_the_keep_in_box(guards, strikes):
    """At reset and after auto-resets (games of 2 ticks, so most steps start new games), pure path."""
    cfg = lab_cfg(**{"rules.game_steps": 2})
    ring_m, disc_m = SPEC.value("starts.strike_ring_m"), SPEC.value("starts.guard_disc_m")
    g = SvgGame(cfg, 2048, guards, strikes, device="cpu", seed=1, band=0)
    assert torch.allclose(g.arenas.side_m, torch.full_like(g.arenas.side_m, SPEC.value("arena.side_m")))
    assert torch.all(g.arenas.zone_centre_m == 0)
    assert torch.allclose(g.arenas.zone_radius_m, torch.full_like(g.arenas.zone_radius_m, SPEC.value("zone.radius_m")))
    every = torch.ones(2048, dtype=torch.bool)
    check_starts(g, every, ring_m, disc_m)
    assert not g.start_miss.any()
    still = {"guard": torch.zeros(2048, guards, 4), "strike": torch.zeros(2048, strikes, 4)}
    renewed = 0
    for _ in range(4):
        out = g.step(still)
        if out.done.any():
            check_starts(g, out.done, ring_m, disc_m)
            renewed += int(out.done.sum())
        assert not out.info["start_miss"].any()
    assert renewed >= 2048


def test_the_starling_layer_starts_on_the_same_ring():
    cfg = lab_cfg(**{"starling.enabled": True, "starling.filter_iterations": 20})
    g = SvgGame(cfg, 64, 3, 3, device="cpu", seed=2, band=0)
    check_starts(g, torch.ones(64, dtype=torch.bool), SPEC.value("starts.strike_ring_m"), SPEC.value("starts.guard_disc_m"))


def test_the_hangar_ring_would_not_fit_negative_control():
    """The check above bites: a ring past the keep-in limit (the hangar's case, L08-F1) is clamped on some bearings."""
    cfg = lab_cfg(**{"starts.strike_ring_m": limit_m() + SPEC.value("arena.wall_margin_m")})
    g = SvgGame(cfg, 512, 3, 3, device="cpu", seed=1, band=0)
    with pytest.raises(AssertionError):
        check_starts(g, torch.ones(512, dtype=torch.bool), cfg.starts.strike_ring_m, cfg.starts.guard_disc_m)


def test_no_tag_on_the_first_step():
    """With the study tag on, every Strike start is farther from every Guard start than the tag radius."""
    cfg = lab_cfg(**{"tag.mode": SPEC.value("tag_rule.pairing"), "tag.radius_m": SPEC.value("tag.radius_m")})
    g = SvgGame(cfg, 4096, 5, 3, device="cpu", seed=3, band=0)
    out = g.step({"guard": torch.zeros(4096, 5, 4), "strike": torch.zeros(4096, 3, 4)})
    assert not out.info["tagged"].any()


def test_the_draw_is_uniform_in_radius_and_bearing_and_seeded():
    cfg = lab_cfg()
    disc_m = SPEC.value("starts.guard_disc_m")
    g = SvgGame(cfg, 8192, 3, 3, device="cpu", seed=5, band=0)
    p = g.pos_m[..., :2]
    rho = p[:, :3].norm(dim=-1)
    assert abs(rho.mean().item() - disc_m / 2) < 0.02 * disc_m                     # uniform in radius: mean = disc / 2
    bearing = torch.atan2(p[..., 1], p[..., 0])
    assert bearing.cos().mean().abs() < 0.03 and bearing.sin().mean().abs() < 0.03
    again = SvgGame(cfg, 8192, 3, 3, device="cpu", seed=5, band=0)
    assert torch.equal(again.pos_m, g.pos_m)
    assert not torch.equal(SvgGame(cfg, 8192, 3, 3, device="cpu", seed=6, band=0).pos_m, g.pos_m)


# ------------------------------------------------------------------------------------------------ team-mates close at the start
def test_team_mates_closer_than_the_filter_distance_are_counted_as_info():
    """LEAD CALL 21 Nov 2026: the miss stays a Guard-Strike pair inside the keep-out or a Strike drone inside the zone;
    team-mate pairs whose starts are closer than the filter distance are counted apart, in info["start_team_close"] [N]
    long (the game that played the step; constant over a game), and in SvgGame.start_team_close for the current game.
    Outcomes do not depend on it."""
    cfg = lab_cfg(**{"rules.game_steps": 3})
    g = SvgGame(cfg, 512, 3, 3, device="cpu", seed=8, band=0)
    keep = min(cfg.rules.keepout_guard_m, cfg.rules.keepout_strike_m)

    def count(pos):
        d = (pos[:, :, None, :2] - pos[:, None, :, :2]).norm(dim=-1)
        team = torch.zeros(6, 6, dtype=torch.bool)
        team[:3, :3] = team[3:, 3:] = True
        pair = team & torch.ones(6, 6, dtype=torch.bool).triu(1)
        return ((d < keep) & pair).sum(dim=(1, 2))

    expect = count(g.pos_m)
    assert torch.equal(g.start_team_close, expect) and expect.dtype == torch.long
    assert (expect > 0).float().mean() > 0.5                                      # three Guards in a 0.8 m disc
    assert not g.start_miss.any()
    still = {"guard": torch.zeros(512, 3, 4), "strike": torch.zeros(512, 3, 4)}
    for _ in range(5):
        out = g.step(still)
        assert torch.equal(out.info["start_team_close"], expect)                 # the game that played this step
        new = count(g.pos_m)
        expect = torch.where(out.done, new, expect)
        assert torch.equal(g.start_team_close, expect)


def test_the_team_close_count_is_absent_in_the_other_modes():
    """The default mode's outputs are unchanged (the L0.9 golden record fingerprints every info key)."""
    g = SvgGame(BASE, 4, 3, 3, device="cpu", seed=1)
    out = g.step({"guard": torch.zeros(4, 3, 4), "strike": torch.zeros(4, 3, 4)})
    assert "start_team_close" not in out.info
