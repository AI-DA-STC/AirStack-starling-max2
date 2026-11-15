"""Pair rules: push-apart (partner) and contact tags (side quest), hand-worked (S2 Task 3). Made-up numbers."""
import pathlib
import sys

import pytest
import torch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
from svg_training.core.game import GUARD_WIN, SCENARIOS, Scenario, SvgGame  # noqa: E402
from svg_training.core.game_config import load_game_cfg  # noqa: E402
from svg_training.core.pair_rules import contact_tags, push_apart  # noqa: E402

CFG = load_game_cfg(use_local=False)[0]
N = 2


def act(n_g, n_s, g_xy=(0.0, 0.0), s_xy=(0.0, 0.0)):
    g = torch.zeros(N, n_g, 4)
    s = torch.zeros(N, n_s, 4)
    g[..., 0], g[..., 1] = g_xy
    s[..., 0], s[..., 1] = s_xy
    return {"guard": g, "strike": s}


def make(side, starts, guards=1, strikes=1, zone=((0.0, 0.0), 0.4), cfg=CFG):
    sc = Scenario("t", side, zone[0], zone[1], tuple(starts))
    return SvgGame(cfg, N, guards, strikes, device="cpu", scenario=sc)


def dist01(g):
    return (g.pos_m[:, 0, :2] - g.pos_m[:, 1, :2]).norm(dim=-1)


def keep(cfg, kg, ks, **extra):
    return cfg.replace(**{"rules.keepout_guard_m": kg, "rules.keepout_strike_m": ks, **extra})


@pytest.mark.parametrize("side", [4.0, 16.0])
def test_block_strike_stops_at_its_keepout(side):
    cfg = keep(CFG, 1.0, 1.0)
    g = make(side, ((0.0, 0.0), (-1.51, 0.0)), zone=((0.0, side / 2 - 1.0), 0.4), cfg=cfg)
    lo = 9.0
    for _ in range(100):
        g.step(act(1, 1, s_xy=(1.0, 0.0)))
        lo = min(lo, float(dist01(g).min()))
    assert g.pos_m[0, 1, 0].item() == pytest.approx(-1.0, abs=1e-4)
    assert lo >= 1.0 - 1e-4


def test_block_both_closing_never_below_smaller_distance():
    cfg = keep(CFG, 0.9, 1.3)
    g = make(16.0, ((-1.6, 0.0), (1.6, 0.0)), zone=((0.0, 6.0), 0.4), cfg=cfg)
    lo = 9.0
    for _ in range(120):
        g.step(act(1, 1, g_xy=(1.0, 0.0), s_xy=(-1.0, 0.0)))
        lo = min(lo, float(dist01(g).min()))
    assert lo >= 0.9 - 1e-4


def test_shove_moves_still_guard():
    cfg = keep(CFG, 1.1, 1.1, **{"rules.push_rule": "shove"})
    g = make(16.0, ((0.0, 0.0), (-1.51, 0.0)), zone=((0.0, 6.0), 0.4), cfg=cfg)
    for _ in range(60):
        g.step(act(1, 1, s_xy=(1.0, 0.0)))
    assert g.pos_m[0, 0, 0].item() > 0.3
    assert dist01(g).min() >= 1.1 - 1e-4


def test_block_leaves_still_guard_in_place():
    g = make(16.0, ((0.0, 0.0), (-1.51, 0.0)), zone=((0.0, 6.0), 0.4))
    for _ in range(60):
        g.step(act(1, 1, s_xy=(1.0, 0.0)))
    assert g.pos_m[0, 0, 0].item() == pytest.approx(0.0, abs=1e-5)


def test_unknown_push_rule_raises():
    with pytest.raises(ValueError):
        make(4.0, ((0.0, 0.0), (-1.5, 0.0)), cfg=CFG.replace(**{"rules.push_rule": "bounce"}))


def test_teammates_pass_through():
    g = make(16.0, ((-1.0, 0.0), (1.0, 0.0), (7.0, 7.0)), guards=2, strikes=1, zone=((-6.0, -6.0), 0.4))
    lo = 9.0
    for _ in range(60):
        a = act(2, 1)
        a["guard"][:, 0, 0], a["guard"][:, 1, 0] = 1.0, -1.0
        g.step(a)
        lo = min(lo, float((g.pos_m[:, 0, :2] - g.pos_m[:, 1, :2]).norm(dim=-1).min()))
    assert lo < 0.1


def test_out_drone_does_not_push():
    g = make(16.0, ((0.0, 0.0), (-1.51, 0.0), (7.0, 7.0)), guards=1, strikes=2, zone=((0.0, 6.0), 0.4))
    g.schedule_dropout(torch.zeros(N, dtype=torch.long), torch.ones(N, dtype=torch.long))   # guard out after step 1
    for _ in range(80):
        g.step(act(1, 2, s_xy=(1.0, 0.0)))
    assert g.pos_m[0, 1, 0].item() > 0.0       # strike walked through where the guard was


def test_push_apart_function_skips_dead_and_teammates():
    prop = torch.tensor([[[0.0, 0.0], [0.1, 0.0], [0.2, 0.0]]])
    is_strike = torch.tensor([False, False, True])
    alive = torch.tensor([[True, True, False]])
    out = push_apart(prop, prop, is_strike, alive, 1.0, 1.0)
    assert torch.equal(out, prop)


@pytest.mark.parametrize("name, x", [("lab4_block", -1.40), ("large16_block", -3.10)])
def test_block_scenario_strike_never_scores(name, x):
    g = SvgGame(CFG, N, 1, 1, device="cpu", scenario=SCENARIOS[name])
    for k in range(1, 1201):
        out = g.step(act(1, 1, s_xy=(1.0, 0.0)))
        assert bool(out.done.any()) == (k == 1200)
        if k == 400:
            assert g.pos_m[0, 1, 0].item() == pytest.approx(x, abs=1e-4)
    assert (out.outcome == GUARD_WIN).all() and (out.end_step == 1200).all()
    assert not out.info["rule_breach"].any()


def contact_game(prob=0.0, preset="contact", side=4.0):
    cfg = CFG.replace(**{"preset": preset, "contact.guard_survives_tag_prob": prob})
    return make(side, ((0.3, 0.0), (-0.51, 0.0)), zone=((1.0, 1.0), 0.4), cfg=cfg)


@pytest.mark.parametrize("side", [4.0, 16.0])
def test_contact_tag_hand_worked(side):
    g = contact_game(side=side)
    for k in range(1, 14):
        out = g.step(act(1, 1, s_xy=(1.0, 0.0)))
        assert bool(out.done.any()) == (k == 13)
    assert (out.outcome == GUARD_WIN).all() and (out.end_step == 13).all()
    assert out.info["tagged"].all()
    assert not out.info["final_alive"].any()


def test_contact_guard_survives_when_prob_one():
    g = contact_game(prob=1.0)
    for _ in range(13):
        out = g.step(act(1, 1, s_xy=(1.0, 0.0)))
    assert out.info["final_alive"][:, 0].all() and not out.info["final_alive"][:, 1].any()
    assert (out.outcome == GUARD_WIN).all()


def test_contact_preset_has_no_push_apart():
    g = contact_game()
    for _ in range(10):
        g.step(act(1, 1, s_xy=(1.0, 0.0)))
    assert dist01(g)[0].item() == pytest.approx(0.81 - 0.25, abs=1e-4)


def test_contact_tags_function():
    pos = torch.tensor([[[0.0, 0.0, 1.2], [0.3, 0.0, 1.2], [5.0, 5.0, 1.2]]])
    alive = torch.ones(1, 3, dtype=torch.bool)
    tagged, after = contact_tags(pos, alive, 2, 0.5, torch.tensor([False]))
    # guards 0 and 1, strike 2 at (5, 5): nobody within 0.5 m of it
    assert not tagged.any() and after.all()
    pos[0, 2] = torch.tensor([0.1, 0.3, 1.2])         # 0.32 m from guard 0, 0.28 m from guard 1
    tagged, after = contact_tags(pos, alive, 2, 0.5, torch.tensor([True]))
    assert tagged.all() and after.tolist() == [[True, True, False]]
