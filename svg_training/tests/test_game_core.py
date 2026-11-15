"""Game core: hand-worked scenarios, reset bookkeeping, walls, rewards (S2 Task 2)."""
import pathlib
import re
import sys

import pytest
import torch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
from svg_training.core.game import (GUARD_WIN, RUNNING, SCENARIOS, STRIKE_WIN, Scenario, SvgGame)  # noqa: E402
from svg_training.core.game_config import load_game_cfg  # noqa: E402
from svg_training.core.observations import ObsView  # noqa: E402
from svg_training.core.rewards import team_rewards  # noqa: E402

CFG = load_game_cfg(use_local=False)[0]
CORE = ROOT / "source" / "svg_training" / "core"
N = 4


def z(g, s=None):
    return torch.zeros(N, g, 4)


def act_x(g, v):
    a = torch.zeros(N, g, 4)
    a[..., 0] = v
    return a


def scen(side, start_x, zone_r):
    return Scenario("t", side, (0.0, 0.0), zone_r, ((side / 2 - 0.5, side / 2 - 0.5), (start_x, 0.0)))


def game(side=4.0, start_x=-1.51, zone_r=0.6, cfg=CFG):
    return SvgGame(cfg, N, 1, 1, device="cpu", scenario=scen(side, start_x, zone_r))


@pytest.mark.parametrize("side, start_x, zone_r, win_step", [(4.0, -1.51, 0.6, 37), (16.0, -7.51, 2.4, 205)])
def test_strike_scores_hand_worked(side, start_x, zone_r, win_step):
    g = game(side, start_x, zone_r)
    for k in range(1, win_step + 1):
        out = g.step({"guard": z(1), "strike": act_x(1, 1.0)})
        assert bool(out.done.any()) == (k == win_step)
    assert (out.outcome == STRIKE_WIN).all() and (out.end_step == win_step).all()


@pytest.mark.parametrize("side", [4.0, 16.0])
def test_time_out_is_guard_win_at_exact_tick(side):
    g = game(side)
    for k in range(1, 1201):
        out = g.step({"guard": z(1), "strike": z(1)})
        assert bool(out.done.any()) == (k == 1200)
    assert (out.outcome == GUARD_WIN).all() and (out.end_step == 1200).all()


def test_win_on_last_step_is_strike():
    g = game(cfg=CFG.replace(**{"rules.game_steps": 37}))
    for _ in range(37):
        out = g.step({"guard": z(1), "strike": act_x(1, 1.0)})
    assert (out.outcome == STRIKE_WIN).all()


@pytest.mark.parametrize("side", [4.0, 16.0])
def test_dropout_of_last_strike_is_guard_win(side):
    g = game(side, -side / 2 + 0.5)
    g.schedule_dropout(drone=torch.full((N,), 1), at_step=torch.full((N,), 10))
    for k in range(1, 11):
        out = g.step({"guard": z(1), "strike": z(1)})
        assert bool(out.done.any()) == (k == 10)
    assert (out.outcome == GUARD_WIN).all() and (out.end_step == 10).all()
    assert not out.info["final_alive"][:, 1].any()
    assert out.obs["guard"][:, 0, ObsView().alive].min() == 1       # new game: back to full strength


def test_dropout_of_guard_game_continues():
    g = game()
    g.schedule_dropout(drone=torch.zeros(N, dtype=torch.long), at_step=torch.full((N,), 5))
    for k in range(1, 38):
        out = g.step({"guard": z(1), "strike": act_x(1, 1.0)})
        if k == 6:
            assert g.alive[:, 0].eq(False).all()
    assert (out.outcome == STRIKE_WIN).all() and (out.end_step == 37).all()
    assert not out.info["final_alive"][:, 0].any()


def test_guard_dropout_shows_absent_to_strike():
    g = game()
    g.schedule_dropout(drone=torch.zeros(N, dtype=torch.long), at_step=torch.full((N,), 3))
    for _ in range(3):
        out = g.step({"guard": z(1), "strike": act_x(1, 1.0)})
    v = ObsView()
    assert (out.obs["strike"][:, 0, v.slot(0)] == 0).all()           # Guard slot absent (drone 0 out)
    assert (out.obs["guard"][:, 0, v.alive] == 0).all()


def test_outcome_reported_on_done_step_then_new_game():
    g = game()
    for _ in range(36):
        g.step({"guard": z(1), "strike": act_x(1, 1.0)})
    out = g.step({"guard": z(1), "strike": act_x(1, 1.0)})
    v = ObsView()
    assert (out.outcome == STRIKE_WIN).all() and out.done.all()
    assert torch.allclose(out.obs["guard"][:, 0, v.time_left], torch.full((N,), CFG.game_ticks() * 0.05))
    assert (g.steps == 0).all()
    nxt = g.step({"guard": z(1), "strike": z(1)})
    assert (nxt.outcome == RUNNING).all() and not nxt.done.any() and (nxt.end_step == 0).all()
    assert (g.steps == 1).all()


def test_walls_keep_in():
    g = game()
    for _ in range(30):
        g.step({"guard": act_x(1, 1.0), "strike": z(1)})
    assert (g.pos_m[:, 0, 0] <= 4.0 / 2 - 0.25 + 1e-6).all() and (g.vel_mps[:, 0, 0] == 0).all()


def test_walls_keep_in_long_run_single_game():
    sc = Scenario("w", 4.0, (0.0, 0.0), 0.6, ((0.0, 1.5), (-1.5, -1.5)))
    g = SvgGame(CFG, 2, 1, 1, device="cpu", scenario=sc)
    for _ in range(400):
        out = g.step({"guard": torch.tensor([[[1.0, 0, 0, 0]]] * 2), "strike": torch.tensor([[[-1.0, 0, 0, 0]]] * 2)})
        if out.done.any():
            break
        assert g.pos_m[:, 0, 0].max() <= 1.75 + 1e-6 and g.pos_m[:, 1, 0].min() >= -1.75 - 1e-6


def test_walls_leave():
    sc = Scenario("w", 4.0, (0.0, 0.0), 0.6, ((1.5, 1.5), (-1.5, -1.0)))
    g = SvgGame(CFG.replace(**{"arena.walls": "leave"}), 2, 1, 1, device="cpu", scenario=sc)
    a = torch.zeros(2, 1, 4)
    a[..., 0] = 1.0
    for _ in range(16):                                              # Guard 1.5 + 0.0167 per step passes 1.75
        out = g.step({"guard": a, "strike": torch.zeros(2, 1, 4)})
    assert not g.alive[:, 0].any() and g.alive[:, 1].all()
    assert not out.info["final_alive"][:, 0].any() and (g.pos_m[:, 0] > 100).all()


def test_unknown_options_raise():
    with pytest.raises(ValueError):
        SvgGame(CFG.replace(**{"arena.walls": "bounce"}), 2, 1, 1, device="cpu")
    with pytest.raises(ValueError):
        SvgGame(CFG.replace(preset="chess"), 2, 1, 1, device="cpu")
    with pytest.raises(ValueError):
        SvgGame(CFG.replace(**{"starts.mode": "x"}), 2, 1, 1, device="cpu")


def test_rewards_terminal_signs():
    cfg = CFG.rewards
    out = torch.tensor([0, 1, 2], dtype=torch.int8)
    phi = torch.zeros(3)
    r = team_rewards(cfg, out, phi, phi, 2, 1)
    assert r["guard"].shape == (3, 2) and r["strike"].shape == (3, 1)
    assert r["guard"][:, 0].tolist() == [0.0, -1.0, 1.0] and r["strike"][:, 0].tolist() == [0.0, 1.0, -1.0]


def test_shaping_reward():
    cfg = CFG.replace(**{"rewards.shaping_weight": 2.0}).rewards
    r = team_rewards(cfg, torch.zeros(1, dtype=torch.int8), torch.tensor([0.5]), torch.tensor([0.25]), 1, 1)
    assert r["guard"].item() == pytest.approx(-0.5) and r["strike"].item() == pytest.approx(0.5)


def test_random_games_run_and_reset():
    g = SvgGame(CFG.replace(dropout_fraction=0.3), 64, 3, 2, device="cpu", seed=5)
    torch.manual_seed(0)
    done_seen = torch.zeros(64, dtype=torch.bool)
    for _ in range(1300):
        out = g.step({"guard": torch.rand(64, 3, 4) * 2 - 1, "strike": torch.rand(64, 2, 4) * 2 - 1})
        done_seen |= out.done
        assert torch.isfinite(out.obs["guard"]).all()
    assert done_seen.all()                                           # everyone ended within 1200 steps


def test_scenarios_exist_and_fit():
    assert set(SCENARIOS) == {"lab4_open", "lab4_block", "large16_open", "large16_block"}
    for sc in SCENARIOS.values():
        SvgGame(CFG, 2, 1, 1, device="cpu", scenario=sc)


def test_game_modules_have_no_host_calls():
    for f in ["arena", "observations", "rewards", "game"]:
        src = (CORE / f"{f}.py").read_text()
        assert not re.search(r"\.(item|cpu|numpy|tolist)\(|import numpy|nonzero\(", src), f


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA only")
def test_step_runs_under_sync_debug_error():
    g = SvgGame(CFG.replace(dropout_fraction=0.2), 256, 3, 2, device="cuda", seed=1)
    a = {"guard": torch.rand(256, 3, 4, device="cuda") * 2 - 1, "strike": torch.rand(256, 2, 4, device="cuda") * 2 - 1}
    g.step(a)
    torch.cuda.set_sync_debug_mode("error")
    try:
        for _ in range(1300):
            g.step(a)
    finally:
        torch.cuda.set_sync_debug_mode(0)
