"""STE task L0.9: the study's tag rule, 1-for-1, nearest pair first (PLAN.md section 4, row L0.9).

A live Guard drone and a live Strike drone whose 3-D centres are closer than ``[tag] radius_m`` tag each other; each drone
takes part in at most one tag per step; the closest pair goes first (ties: lower Guard index, then lower Strike index).
Both drones leave the game on that step unless the game drew "Guard survives" (``guard_survives_tag_prob``, D2: 0).
Tags come before the zone test. ``[tag] mode = "off"`` (the default) is today's game: the bit-for-bit check against the
pre-L0.9 record is ``tests/test_game_tag_off_golden.py``; here, an absent ``[tag]`` equals an explicit off, and a tag
switched on that cannot fire plays the same game bit for bit. The radius 1.6 m is PROPOSED (P1): study runs only.
Made-up positions; CPU.
"""
import math
import pathlib
import sys

import pytest
import torch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
from svg_training.core.game import GUARD_WIN, PARK_M, RUNNING, STRIKE_WIN, Scenario, SvgGame  # noqa: E402
from svg_training.core.game_config import TAG_MODES, TagCfg, load_game_cfg  # noqa: E402
from svg_training.core.pair_rules import proximity_tags  # noqa: E402

CFG = load_game_cfg(use_local=False)[0]
ON = "nearest_pair_1for1"
TAG = CFG.replace(**{"tag.mode": ON})
N = 2


def match(points, guards, radius_m=1.6, alive=None, survives=False):
    """proximity_tags on one game given as a list of (x, y, z), Guard drones first; returns (tagged, alive_after,
    partner) of game 0."""
    pos = torch.tensor([points], dtype=torch.float32)
    alive = torch.ones(1, len(points), dtype=torch.bool) if alive is None else torch.tensor([alive])
    tagged, after, partner = proximity_tags(pos, alive, guards, radius_m, torch.tensor([survives]))
    return tagged[0].tolist(), after[0].tolist(), partner[0].tolist()


# ------------------------------------------------------------------------------------------------ the matcher
def test_tag_at_1p59_m_not_at_1p61_m():
    assert match([(0.0, 0.0, 1.2), (1.59, 0.0, 1.2)], 1)[0] == [True, True]
    assert match([(0.0, 0.0, 1.2), (1.61, 0.0, 1.2)], 1)[0] == [False, False]


def test_distance_is_3d_between_centres():
    """1.0 m apart across, 1.25 m apart in height: 1.601 m in 3-D, no tag, though the horizontal distance is 1.0 m."""
    assert match([(0.0, 0.0, 0.5), (1.0, 0.0, 1.75)], 1)[0] == [False, False]
    assert match([(0.0, 0.0, 0.5), (1.0, 0.0, 1.7)], 1)[0] == [True, True]          # 1.562 m


def test_the_radius_comes_from_the_argument():
    assert match([(0.0, 0.0, 1.2), (1.4, 0.0, 1.2)], 1, radius_m=1.2)[0] == [False, False]
    assert match([(0.0, 0.0, 1.2), (1.4, 0.0, 1.2)], 1, radius_m=1.6)[0] == [True, True]


def test_one_guard_takes_one_strike_the_nearer():
    tagged, after, partner = match([(0.0, 0.0, 1.2), (1.0, 0.0, 1.2), (0.0, 0.7, 1.2)], 1)
    assert tagged == [True, False, True] and after == [False, True, False] and partner == [2, -1, 0]


def test_one_strike_is_taken_by_one_guard_the_nearer():
    tagged, after, partner = match([(1.0, 0.0, 1.2), (0.0, -0.6, 1.2), (0.0, 0.0, 1.2)], 2)
    assert tagged == [False, True, True] and after == [True, False, False] and partner == [-1, 2, 1]


def test_separate_pairs_tag_on_the_same_step():
    tagged, _, partner = match([(0.0, 0.0, 1.2), (3.0, 0.0, 1.2), (0.5, 0.0, 1.2), (3.0, 1.0, 1.2)], 2)
    assert tagged == [True, True, True, True] and partner == [2, 3, 0, 1]


def test_nearest_pair_first_not_the_most_pairs():
    """On a line: S1 at -1, G0 at 0, S0 at 0.5, G1 at 1.5. G0-S0 (0.5 m) goes first; G1-S1 is 2.5 m, so one tag, although
    pairing G0-S1 and G1-S0 (1.0 m each) would have made two. Greedy nearest-first, as PLAN row L0.9 says."""
    tagged, _, partner = match([(0.0, 0.0, 1.2), (1.5, 0.0, 1.2), (0.5, 0.0, 1.2), (-1.0, 0.0, 1.2)], 2)
    assert tagged == [True, False, True, False] and partner == [2, -1, 0, -1]


def test_ties_go_to_the_lower_guard_then_the_lower_strike():
    """Equal distances (1.0 m, exact in float32): the lower Strike index for one Guard, the lower Guard index for one
    Strike, and between two cross pairs the pair with the lower Guard index first."""
    assert match([(0.0, 0.0, 1.0), (1.0, 0.0, 1.0), (-1.0, 0.0, 1.0)], 1)[2] == [1, 0, -1]
    assert match([(1.0, 0.0, 1.0), (-1.0, 0.0, 1.0), (0.0, 0.0, 1.0)], 2)[2] == [2, -1, 0]
    # G0 and G1 each 1.0 m from S0; S1 only near G1 (1.0 m): G0 takes S0 first, then G1 takes S1
    assert match([(-1.0, 0.0, 1.0), (1.0, 0.0, 1.0), (0.0, 0.0, 1.0), (1.0, 1.0, 1.0)], 2)[2] == [2, 3, 0, 1]


def test_drones_that_are_out_never_tag():
    """Drones that are out are parked at the same point (PARK_M), 0 m apart: they must not match."""
    park = (PARK_M, PARK_M, 1.2)
    assert match([park, park], 1, alive=[False, False])[0] == [False, False]
    assert match([(0.0, 0.0, 1.2), (0.5, 0.0, 1.2)], 1, alive=[False, True]) == ([False, False], [False, True], [-1, -1])
    # the nearest Strike is out: the live one further away is taken
    tagged, _, partner = match([(0.0, 0.0, 1.2), (0.3, 0.0, 1.2), (1.2, 0.0, 1.2)], 1, alive=[True, False, True])
    assert tagged == [True, False, True] and partner == [2, -1, 0]


def test_a_guard_that_survives_stays_in():
    tagged, after, _ = match([(0.0, 0.0, 1.2), (1.0, 0.0, 1.2), (0.0, 0.7, 1.2)], 1, survives=True)
    assert tagged == [True, False, True] and after == [True, True, False]


def test_games_are_matched_independently():
    """Three games in one call give what each gives alone (no mixing across games)."""
    games = [[(0.0, 0.0, 1.2), (1.0, 0.0, 1.2), (5.0, 0.0, 1.2), (1.0, 0.5, 1.2)],
             [(0.0, 0.0, 1.2), (0.0, 0.0, 1.2), (0.4, 0.0, 1.2), (3.0, 0.0, 1.2)],
             [(2.0, 2.0, 1.2), (-2.0, -2.0, 1.2), (0.0, 0.0, 1.2), (0.0, 0.0, 0.5)]]
    alive = torch.ones(3, 4, dtype=torch.bool)
    survives = torch.tensor([False, True, False])
    tagged, after, partner = proximity_tags(torch.tensor(games), alive, 2, 1.6, survives)
    for i, game in enumerate(games):
        one = proximity_tags(torch.tensor([game]), alive[i:i + 1], 2, 1.6, survives[i:i + 1])
        assert torch.equal(tagged[i], one[0][0]) and torch.equal(after[i], one[1][0]) and torch.equal(partner[i], one[2][0])


def test_shapes_and_dtypes():
    n, g, s = 4, 3, 2
    tagged, after, partner = proximity_tags(torch.rand(n, g + s, 3), torch.ones(n, g + s, dtype=torch.bool), g, 1.6,
                                            torch.zeros(n, dtype=torch.bool))
    assert tagged.shape == after.shape == partner.shape == (n, g + s)
    assert tagged.dtype == after.dtype == torch.bool and partner.dtype == torch.long


# ------------------------------------------------------------------------------------------------ in the game
def z(n_drones):
    return torch.zeros(N, n_drones, 4)


def act_x(n_drones, v):
    a = z(n_drones)
    a[..., 0] = v
    return a


def game(starts, guards=1, strikes=1, cfg=TAG, zone=((0.0, 0.0), 0.4), side=6.0, seed=0):
    sc = Scenario("t", side, zone[0], zone[1], tuple(starts))
    return SvgGame(cfg, N, guards, strikes, device="cpu", scenario=sc, seed=seed)


def test_in_the_game_1p59_m_tags_1p61_m_does_not():
    out = game([(0.0, 2.0), (1.59, 2.0)]).step({"guard": z(1), "strike": z(1)})
    assert out.info["tagged"].all() and (out.outcome == GUARD_WIN).all() and (out.end_step == 1).all()
    assert not out.info["final_alive"].any()                       # both out on the step of the tag
    g = game([(0.0, 2.0), (1.61, 2.0)])
    out = g.step({"guard": z(1), "strike": z(1)})
    assert not out.info["tagged"].any() and (out.outcome == RUNNING).all() and g.alive.all()


def test_tagged_drones_leave_on_the_same_step_and_are_parked():
    g = game([(0.0, 2.0), (2.0, 2.0), (1.3, 2.0)], strikes=2)       # S0 2.0 m, S1 1.3 m from G0 (both > 1.10 m)
    out = g.step({"guard": z(1), "strike": z(2)})
    assert out.info["tagged"].tolist() == [[True, False, True]] * N
    assert out.info["final_alive"].tolist() == [[False, True, False]] * N
    assert (out.outcome == RUNNING).all()                          # a Strike drone is left: the game goes on
    assert (g.pos_m[:, [0, 2], :2] == PARK_M).all() and (g.pos_m[:, 1, :2] != PARK_M).all()


def test_one_guard_takes_one_strike_per_pass():
    """One Guard drone, two Strike drones in range. The Guard drone takes the nearer one and leaves with it; the other
    Strike drone plays on. If the Guard survives tags (probability 1), it takes the second one on the next step.
    Every start is more than 1.10 m from the Guard drone, so the push-apart rule moves nothing."""
    starts = [(0.0, 2.0), (1.5, 2.0), (0.0, 3.2)]                   # S0 1.5 m, S1 1.2 m from G0
    out = game(starts, strikes=2).step({"guard": z(1), "strike": z(2)})
    assert out.info["tagged"].tolist() == [[True, False, True]] * N and (out.outcome == RUNNING).all()
    g = game(starts, strikes=2, cfg=TAG.replace(**{"tag.guard_survives_tag_prob": 1.0}))
    first = g.step({"guard": z(1), "strike": z(2)})
    assert first.info["tagged"].tolist() == [[True, False, True]] * N
    assert first.info["final_alive"].tolist() == [[True, True, False]] * N
    second = g.step({"guard": z(1), "strike": z(2)})
    assert second.info["tagged"].tolist() == [[True, True, False]] * N
    assert (second.outcome == GUARD_WIN).all() and (second.end_step == 2).all()


def test_tags_come_before_the_zone_test():
    """The Strike drone enters the zone (radius 0.4 m) on step 1 and is 1.385 m from the Guard drone: tagged, no score.
    With the Guard drone far away the same move scores."""
    out = game([(1.0, 0.0), (-0.41, 0.0)]).step({"guard": z(1), "strike": act_x(1, 1.0)})
    assert out.info["tagged"].all() and (out.outcome == GUARD_WIN).all() and (out.end_step == 1).all()
    out = game([(2.5, 2.5), (-0.41, 0.0)]).step({"guard": z(1), "strike": act_x(1, 1.0)})
    assert not out.info["tagged"].any() and (out.outcome == STRIKE_WIN).all() and (out.end_step == 1).all()


def test_a_drone_that_left_through_a_wall_cannot_tag():
    cfg = TAG.replace(**{"arena.walls": "leave"})
    g = game([(1.5, 0.0), (2.74, 0.0)], cfg=cfg)                     # side 6: the keep-in limit is 2.75 m
    out = g.step({"guard": z(1), "strike": act_x(1, 1.0)})          # the Strike drone crosses it, 1.265 m from G0
    assert not out.info["tagged"].any() and (out.outcome == GUARD_WIN).all()
    assert out.info["final_alive"].tolist() == [[True, False]] * N


def test_tags_with_the_starling_layer():
    cfg = TAG.replace(**{"starling.enabled": True, "starling.filter_iterations": 20})
    out = game([(0.0, 2.0), (1.5, 2.0)], cfg=cfg).step({"guard": z(1), "strike": z(1)})
    assert out.info["tagged"].all() and (out.outcome == GUARD_WIN).all()
    out = game([(0.0, 2.0), (1.7, 2.0)], cfg=cfg).step({"guard": z(1), "strike": z(1)})
    assert not out.info["tagged"].any() and (out.outcome == RUNNING).all()


# ------------------------------------------------------------------------------------------------ random streams
def run(cfg, seed, steps=100, games=6, guards=3, strikes=3):
    """``steps`` steps of random-start games with scripted commands (Strike drones to the zone, Guard drones to the
    nearest Strike drone, noise from a fixed generator); every output stacked [T, ...]."""
    g = SvgGame(cfg, games, guards, strikes, device="cpu", seed=seed)
    gen = torch.Generator().manual_seed(1000 + seed)
    log = []
    for _ in range(steps):
        pos = g.pos_m
        to_zone = g.arenas.zone_centre_m[:, None, :] - pos[:, guards:, :2]
        rel = pos[:, None, guards:, :2] - pos[:, :guards, None, :2]
        d = rel.norm(dim=-1).masked_fill(~g.alive[:, None, guards:], float("inf"))
        to_strike = torch.gather(rel, 2, d.argmin(dim=2)[:, :, None, None].expand(-1, -1, 1, 2))[:, :, 0]
        xy = torch.cat((to_strike, to_zone), dim=1)
        xy = xy / xy.norm(dim=-1, keepdim=True).clamp(min=1e-6) + 0.6 * (torch.rand(*xy.shape, generator=gen) * 2 - 1)
        a = torch.cat((xy, torch.rand(games, guards + strikes, 2, generator=gen) * 2 - 1), dim=-1).clamp(-1.0, 1.0)
        out = g.step({"guard": a[:, :guards], "strike": a[:, guards:]})
        log.append({"pos_m": g.pos_m.clone(), "vel_mps": g.vel_mps.clone(), "alive": g.alive.clone(),
                    "outcome": out.outcome, "end_step": out.end_step, **{f"reward_{k}": v for k, v in out.reward.items()},
                    **{f"obs_{k}": v for k, v in out.obs.items()}, **{f"info_{k}": v for k, v in out.info.items()}})
    return {k: torch.stack([row[k] for row in log]) for k in log[0]}


SHORT = {"dropout_fraction": 0.5, "rules.game_steps": 40}


@pytest.mark.parametrize("starling", [False, True])
def test_a_tag_that_cannot_fire_plays_the_game_with_the_tag_off(starling):
    """Tag on at 0.5 m, with a Guard that survives in about half the games: the push-apart rule (pure) or the safety
    filter (Starling layer) keeps opposite drones about 1.10 m apart, so no tag fires, and every output equals the
    tag-off game bit for bit over 100 steps and many resets (no extra draw from the game's generator)."""
    base = CFG.replace(**SHORT)
    if starling:
        base = base.replace(**{"starling.enabled": True, "starling.filter_iterations": 20})
    on = base.replace(**{"tag.mode": ON, "tag.radius_m": 0.5, "tag.guard_survives_tag_prob": 0.5})
    for seed in (0, 5):
        off_run, on_run = run(base, seed), run(on, seed)
        assert not on_run["info_tagged"].any() and (on_run["end_step"] > 0).sum() >= 12
        assert off_run.keys() == on_run.keys()
        for k in off_run:
            assert torch.equal(off_run[k], on_run[k]), (seed, k)


def test_the_tag_on_does_not_change_the_starts():
    """The survive draw has its own generator: the same seed gives the same arenas and starts with the tag on or off,
    so study cells with and without the tag start from the same games."""
    off = SvgGame(CFG, 64, 3, 3, device="cpu", seed=4)
    on = SvgGame(TAG.replace(**{"tag.guard_survives_tag_prob": 0.5}), 64, 3, 3, device="cpu", seed=4)
    assert torch.equal(off.pos_m, on.pos_m) and torch.equal(off.arenas.zone_centre_m, on.arenas.zone_centre_m)
    off.reset(seed=9)
    on.reset(seed=9)
    assert torch.equal(off.pos_m, on.pos_m)


def test_the_survive_draw_follows_the_probability_and_the_seed():
    def survives(prob, seed):
        return SvgGame(TAG.replace(**{"tag.guard_survives_tag_prob": prob}), 4000, 1, 1, device="cpu",
                       seed=seed)._tag_survives
    assert not survives(0.0, 1).any() and survives(1.0, 1).all()
    half = survives(0.5, 1)
    assert 0.45 < half.float().mean() < 0.55
    assert torch.equal(half, survives(0.5, 1)) and not torch.equal(half, survives(0.5, 2))
    g = SvgGame(TAG.replace(**{"tag.guard_survives_tag_prob": 0.5}), 4000, 1, 1, device="cpu", seed=1)
    g.reset(seed=1)
    assert torch.equal(g._tag_survives, half)                       # reset(seed) reseeds the tag's stream too


def test_cpu_determinism_with_the_tag_on():
    cfg = TAG.replace(**SHORT, **{"tag.guard_survives_tag_prob": 0.5})
    first, again = run(cfg, 3), run(cfg, 3)
    assert first["info_tagged"].any()
    assert all(torch.equal(first[k], again[k]) for k in first)


# ------------------------------------------------------------------------------------------------ settings
def test_off_by_default_and_an_absent_section_is_off(tmp_path):
    assert TagCfg() == CFG.tag and CFG.tag.mode == "off"
    assert TAG_MODES == ("off", ON)
    text = (ROOT / "configs" / "s2_game.toml").read_text()
    assert "[tag]" not in text                                     # the committed game files stay as they were
    path = tmp_path / "game.toml"
    path.write_text(text + '\n[tag]\nmode = "off"\n')
    assert load_game_cfg(path, use_local=False)[0] == CFG
    path.write_text(text + f'\n[tag]\nmode = "{ON}"\nradius_m = 1.4\nguard_survives_tag_prob = 1.0\n')
    assert load_game_cfg(path, use_local=False)[0].tag == TagCfg(mode=ON, radius_m=1.4, guard_survives_tag_prob=1.0)


@pytest.mark.parametrize("bad, match_text", [
    ({"mode": "any_in_range"}, "tag.mode"),
    ({"radius_m": 0.0}, "tag.radius_m"),
    ({"radius_m": -1.0}, "tag.radius_m"),
    ({"radius_m": math.nan}, "tag.radius_m"),
    ({"radius_m": math.inf}, "tag.radius_m"),
    ({"guard_survives_tag_prob": -0.1}, "tag.guard_survives_tag_prob"),
    ({"guard_survives_tag_prob": 1.5}, "tag.guard_survives_tag_prob"),
    ({"guard_survives_tag_prob": math.nan}, "tag.guard_survives_tag_prob"),
])
def test_bad_settings_raise(bad, match_text):
    with pytest.raises(ValueError, match=match_text):
        TagCfg(**bad)


def test_unknown_key_and_local_file_refused(tmp_path):
    text = (ROOT / "configs" / "s2_game.toml").read_text()
    path = tmp_path / "game.toml"
    path.write_text(text + "\n[tag]\nradius = 1.6\n")
    with pytest.raises(ValueError, match=r"unknown key.*\[tag\].*radius"):
        load_game_cfg(path, use_local=False)
    local = tmp_path / "local"
    local.mkdir()
    (local / "partner_rules.toml").write_text(f'[tag]\nmode = "{ON}"\n')
    with pytest.raises(ValueError, match="tag.mode"):              # the partner's file may not switch the tag on
        load_game_cfg(ROOT / "configs" / "s2_game.toml", local_dir=local)


def test_the_tag_and_the_contact_preset_do_not_mix():
    with pytest.raises(ValueError, match=r"preset.*contact.*tag\.mode"):
        SvgGame(TAG.replace(preset="contact"), N, 1, 1, device="cpu")
    SvgGame(CFG.replace(preset="contact"), N, 1, 1, device="cpu")   # the contact preset alone is unchanged


def test_replace_reaches_the_tag_section():
    cfg = CFG.replace(**{"tag.mode": ON, "tag.radius_m": 1.2})
    assert cfg.tag == TagCfg(mode=ON, radius_m=1.2) and CFG.tag == TagCfg()
    with pytest.raises(KeyError, match="tag.land_speed_mps"):        # landing is L2.3, not here
        CFG.replace(**{"tag.land_speed_mps": 0.6})
