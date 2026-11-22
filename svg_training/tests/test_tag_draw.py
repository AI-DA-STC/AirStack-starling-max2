"""STE task L1.10: the tag radius drawn per game (``[tag] radius_m_range = [lo, hi]``, optional; absent = off).

With the range set, every game draws its own tag radius uniformly in [lo, hi] when it starts (the first games, every
auto-reset and every ``TrainGame.restart``), from a generator of its own seeded from the game seed (so the arenas, the
starts, the drop-outs and the survive draw are the same as with the range off), and the study tag of every game uses its
own radius (``SvgGame``, ``sweep.SweepGame``, ``exploit_train.TrainGame``). Off (absent) is today's game bit for bit: no
draw, and the matcher gets the same Python float. The learner does not observe the radius. Made-up positions; CPU.
"""
import math
import pathlib
import sys

import pytest
import torch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
from svg_training.core import game as core_game  # noqa: E402
from svg_training.core.game import Scenario, SvgGame  # noqa: E402
from svg_training.core.game_config import TagCfg, load_game_cfg  # noqa: E402
from svg_training.core.pair_rules import proximity_tags  # noqa: E402
from svg_training.ste import sweep  # noqa: E402
from svg_training.ste.exploit_train import TrainGame  # noqa: E402

CFG = load_game_cfg(use_local=False)[0]
ON = "nearest_pair_1for1"
TAG = CFG.replace(**{"tag.mode": ON})
DRAW = TAG.replace(**{"tag.radius_m_range": (1.5, 1.7)})
SHORT = {"dropout_fraction": 0.5, "rules.game_steps": 40}
L1 = ROOT / "configs" / "ste_l1"


# ------------------------------------------------------------------------------------------------ settings
def test_absent_is_off_and_the_default():
    assert TagCfg().radius_m_range is None and CFG.tag.radius_m_range is None
    assert load_game_cfg(ROOT / "configs" / "ste_l011" / "base.toml", use_local=False)[0].tag.radius_m_range is None


def test_a_game_file_sets_the_range(tmp_path):
    text = (ROOT / "configs" / "s2_game.toml").read_text()
    path = tmp_path / "game.toml"
    path.write_text(text + f'\n[tag]\nmode = "{ON}"\nradius_m = 1.6\nradius_m_range = [1.5, 1.7]\n')
    assert load_game_cfg(path, use_local=False)[0].tag == TagCfg(mode=ON, radius_m=1.6, radius_m_range=(1.5, 1.7))


@pytest.mark.parametrize("bad, text", [
    ({"radius_m_range": (1.5, 1.7)}, "needs the tag on"),                       # mode off: it would do nothing
    ({"mode": ON, "radius_m_range": (1.7, 1.5)}, "lo <= hi"),
    ({"mode": ON, "radius_m_range": (0.0, 1.7)}, "above 0"),
    ({"mode": ON, "radius_m_range": (1.5, math.inf)}, "finite"),
    ({"mode": ON, "radius_m_range": (1.5, math.nan)}, "finite"),
    ({"mode": ON, "radius_m_range": (1.5,)}, "two numbers"),
    ({"mode": ON, "radius_m_range": (1.5, 1.6, 1.7)}, "two numbers"),
    ({"mode": ON, "radius_m_range": (True, 1.7)}, "two numbers"),
    ({"mode": ON, "radius_m_range": "1.5-1.7"}, "two numbers"),
    ({"mode": ON, "radius_m": 1.4, "radius_m_range": (1.5, 1.7)}, "inside"),   # radius_m: the range's nominal value
])
def test_bad_ranges_raise(bad, text):
    with pytest.raises(ValueError, match=text):
        TagCfg(**bad)


# ------------------------------------------------------------------------------------------------ the matcher
def test_the_matcher_takes_one_radius_per_game():
    pos = torch.tensor([[(0.0, 0.0, 1.2), (1.6, 0.0, 1.2)]] * 3)                   # every game: the pair 1.6 m apart
    alive, surv = torch.ones(3, 2, dtype=torch.bool), torch.zeros(3, dtype=torch.bool)
    tagged, _, _ = proximity_tags(pos, alive, 1, torch.tensor([1.55, 1.65, 1.6]), surv)
    assert tagged.tolist() == [[False, False], [True, True], [False, False]]      # strictly closer than the radius
    as_float = proximity_tags(pos, alive, 1, 1.65, surv)
    as_tensor = proximity_tags(pos, alive, 1, torch.full((3,), 1.65), surv)
    assert all(torch.equal(a, b) for a, b in zip(as_float, as_tensor))


# ------------------------------------------------------------------------------------------------ the draw
def _radii(cfg, seed, n=20000, device="cpu"):
    return SvgGame(cfg, n, 1, 1, device=device, seed=seed)._study_radius()


def test_off_uses_the_float_radius_and_draws_nothing():
    g = SvgGame(TAG, 8, 1, 1, device="cpu", seed=1)
    assert g._study_radius() == 1.6 and isinstance(g._study_radius(), float) and g._tag_radius_m is None


def test_the_draw_is_uniform_in_the_range():
    r = _radii(DRAW, 7)
    assert r.shape == (20000,) and r.dtype == torch.float32
    assert float(r.min()) >= 1.5 and float(r.max()) <= 1.7
    # uniform on [1.5, 1.7]: mean 1.6, sd 0.2 / sqrt(12) = 0.0577; mean within 4 standard errors
    assert abs(float(r.mean()) - 1.6) < 4 * 0.0577 / math.sqrt(20000)
    assert abs(float(r.std()) - 0.2 / math.sqrt(12)) < 0.002
    tenths = torch.histc(r, bins=10, min=1.5, max=1.7)                             # 2,000 expected per bin
    assert float(tenths.min()) > 2000 - 4 * math.sqrt(2000 * 0.9) and float(tenths.max()) < 2000 + 4 * math.sqrt(1800)


def test_the_draw_follows_the_seed_and_reset_reseeds_it():
    a = _radii(DRAW, 3, n=500)
    assert torch.equal(a, _radii(DRAW, 3, n=500)) and not torch.equal(a, _radii(DRAW, 4, n=500))
    g = SvgGame(DRAW, 500, 1, 1, device="cpu", seed=3)
    g.reset()                                                      # no seed: the stream goes on, new radii
    assert not torch.equal(g._study_radius(), a)
    g.reset(seed=3)
    assert torch.equal(g._study_radius(), a)


def test_a_range_of_one_value_plays_the_fixed_radius_game_bit_for_bit():
    """lo = hi = 1.6: every drawn radius is 1.6 exactly, so the game equals the fixed 1.6 m game in every output over
    many auto-resets, which also shows that the draw takes nothing from the game's own streams (arenas, starts,
    drop-outs) nor from the survive draw."""
    from test_tag_rule import run                                 # the tag tests' scripted random-start runner
    fixed = TAG.replace(**SHORT, **{"tag.guard_survives_tag_prob": 0.5})
    one = fixed.replace(**{"tag.radius_m_range": (1.6, 1.6)})
    for seed in (0, 5):
        a, b = run(fixed, seed), run(one, seed)
        assert a["info_tagged"].any() and (a["end_step"] > 0).sum() >= 12
        assert all(torch.equal(a[k], b[k]) for k in a), seed


def test_the_range_does_not_change_arenas_starts_or_the_survive_draw():
    fixed = TAG.replace(**{"tag.guard_survives_tag_prob": 0.5})
    off, on = (SvgGame(c, 64, 3, 3, device="cpu", seed=4) for c in (fixed, fixed.replace(**{"tag.radius_m_range":
                                                                                              (1.5, 1.7)})))
    for x, y in ((off.pos_m, on.pos_m), (off.arenas.zone_centre_m, on.arenas.zone_centre_m),
                 (off._tag_survives, on._tag_survives), (off.dropout_step, on.dropout_step)):
        assert torch.equal(x, y)


def test_auto_reset_redraws_only_the_ended_games():
    g = SvgGame(DRAW, 6, 1, 1, device="cpu", seed=2)
    before = g._study_radius().clone()
    mask = torch.tensor([True, False, True, False, False, False])
    g._new_games(mask)
    after = g._study_radius()
    assert torch.equal(after[~mask], before[~mask]) and not torch.equal(after[mask], before[mask])
    assert float(after.min()) >= 1.5 and float(after.max()) <= 1.7


# ------------------------------------------------------------------------------------------------ tags use it
def _pair_game(cls, cfg, radii, **kw):
    """Two games, one Guard 1.6 m from one Strike drone, both still; the drawn radii replaced by ``radii``."""
    sc = Scenario("t", 6.0, (0.0, 0.0), 0.4, ((0.0, 2.0), (1.6, 2.0)))
    g = cls(cfg, 2, 1, 1, device="cpu", scenario=sc, seed=0, **kw)
    if radii is not None:
        g._tag_radius_m = torch.tensor(radii)
    return g


@pytest.mark.parametrize("cls", [SvgGame, TrainGame])
def test_the_game_tags_on_each_games_own_radius(cls):
    zero = torch.zeros(2, 1, 4)
    out = _pair_game(cls, DRAW, [1.55, 1.65]).step({"guard": zero, "strike": zero})
    assert out.info["tagged"].tolist() == [[False, False], [True, True]]
    fixed = _pair_game(cls, TAG, None).step({"guard": zero, "strike": zero})     # 1.6 m apart, radius 1.6: strict
    assert not fixed.info["tagged"].any()


def test_the_sweep_game_tags_on_each_games_own_radius():
    g = sweep.SweepGame(load_game_cfg(L1 / "base_err_tagdraw.toml", use_local=False)[0], 1, 2, 1, 1, "cpu", 0)
    g.pos_m[:, 0] = torch.tensor([0.0, 2.0, 1.2])
    g.pos_m[:, 1] = torch.tensor([1.6, 2.0, 1.2])
    g._tag_radius_m = torch.tensor([1.55, 1.65])
    tagged, _ = g._study_tags(g.pos_m, g.alive, torch.zeros_like(g.alive))
    assert tagged.tolist() == [[False, False], [True, True]]
    assert torch.isinf(g._tick_tag[1][0, 0]) or not bool(g._tick_tag[0][0, 0])
    assert bool(g._tick_tag[0][1, 0]) and abs(float(g._tick_tag[1][1, 0]) - 1.6) < 1e-5


def test_the_study_file_draws_in_1p5_to_1p7_and_the_learner_never_sees_it():
    cfg = load_game_cfg(L1 / "base_err_tagdraw.toml", use_local=False)[0]
    assert cfg.tag.radius_m_range == (1.5, 1.7) and cfg.tag.radius_m == 1.6
    g = SvgGame(cfg, 64, 3, 3, device="cpu", seed=11)
    r = g._study_radius()
    assert r.shape == (64,) and float(r.min()) >= 1.5 and float(r.max()) <= 1.7
    fixed = SvgGame(load_game_cfg(L1 / "base_err_nominal.toml", use_local=False)[0], 64, 3, 3, device="cpu", seed=11)
    obs_a, obs_b = g._obs(), fixed._obs()                           # same starts: the observations are equal
    assert all(torch.equal(obs_a[k], obs_b[k]) for k in obs_a)
    assert torch.equal(g.state(), fixed.state())


def test_the_seed_mix_is_its_own():
    assert core_game._tag_radius_seed(0) != core_game._tag_seed(0)
    assert core_game._tag_radius_seed(5) == core_game._tag_radius_seed(5) < (1 << 63)
