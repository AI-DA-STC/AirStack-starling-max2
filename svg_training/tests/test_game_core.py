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


@pytest.mark.parametrize("change, key", [({"rules.teammates_pass": False}, "teammates_pass"),
                                         ({"obs_view": "limited"}, "obs_view"),
                                         ({"obs_view": "FULL"}, "obs_view")])
def test_unbuilt_rule_options_raise_naming_the_key(change, key):
    """Only teammates_pass = true and obs_view = "full" are built; anything else (e.g. from the local file) raises,
    and the message names the key, not the value given."""
    with pytest.raises(ValueError, match=key) as e:
        SvgGame(CFG.replace(**change), 2, 1, 1, device="cpu")
    assert "limited" not in str(e.value) and "FULL" not in str(e.value) and "False" not in str(e.value)


def test_built_rule_options_accepted():
    assert CFG.rules.teammates_pass is True and CFG.obs_view == "full"
    SvgGame(CFG, 2, 1, 1, device="cpu")


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


def test_dropout_is_one_drone_in_a_fraction_of_games():
    f = 0.3
    g = SvgGame(CFG.replace(dropout_fraction=f), 20000, 3, 2, device="cpu", seed=9)
    per_game = (g.dropout_step >= 0).sum(dim=1)
    assert per_game.max() <= 1
    assert abs(float((per_game == 1).float().mean()) - f) < 0.02
    who = (g.dropout_step >= 0).float().argmax(dim=1)[per_game == 1]
    assert set(who.tolist()) == {0, 1, 2, 3, 4}                      # any team, any drone
    steps = g.dropout_step[g.dropout_step >= 0]
    assert steps.min() >= 1 and steps.max() <= 1200


def test_start_miss_reported():
    big = CFG.replace(**{"starts.spacing_m": 50.0})                  # made-up: impossible to meet
    g = SvgGame(big, 32, 5, 3, device="cpu", seed=2, band=0)
    assert g.start_miss.all()                                        # from reset() itself
    a = {"guard": torch.zeros(32, 5, 4), "strike": torch.zeros(32, 3, 4)}
    out = g.step(a)
    assert out.info["start_miss"].all()                              # same flag, every step of the game
    for _ in range(1199):
        out = g.step(a)
    assert out.done.all() and out.info["start_miss"].all()           # read on the done step
    assert g.start_miss.all()                                        # the new game also misses
    ok = SvgGame(CFG, 32, 2, 1, device="cpu", seed=2, band=2)
    assert not ok.start_miss.any() and not ok.step({"guard": torch.zeros(32, 2, 4),
                                                    "strike": torch.zeros(32, 1, 4)}).info["start_miss"].any()


def test_scenarios_exist_and_fit():
    assert set(SCENARIOS) == {"lab4_open", "lab4_block", "large16_open", "large16_block"}
    for sc in SCENARIOS.values():
        SvgGame(CFG, 2, 1, 1, device="cpu", scenario=sc)


# Host reads that would stall the GPU step: .item() .cpu() .numpy() .tolist(), NumPy, nonzero(), and the builtins
# bool( float( int( on a tensor. A literal like float("inf") is not a host read. Static scan: a builtin call on a
# Python number looks the same, so each one outside the step is allow-listed below by its exact line, with why.
_HOST = re.compile(r"\.(item|cpu|numpy|tolist)\(|import numpy|nonzero\(|(?<![\w.])(bool|float|int)\((?![\"'])")
SRC = ROOT / "source" / "svg_training"
_STEP_FILES = ["core/arena.py", "core/observations.py", "core/rewards.py", "core/game.py", "core/pair_rules.py",
               "core/starling_layer.py", "core/safety_filter.py", "core/play.py", "opponents/scripted.py",
               "models/commander.py", "models/fitted.py", "models/placeholder.py", "models/_filters.py"]
# Offline fitting modules: run on flight logs with NumPy/SciPy, never in the step (the step imports only the frozen
# TrajectoryParams dataclass from px4_trajectory). Listed so a new models/*.py file must be placed on one list.
_OFFLINE_MODELS = {"models/fit.py", "models/px4_trajectory.py", "models/response.py", "models/__init__.py"}
_ALLOWED = {
    ("core/arena.py", "tot = float(sum(w))"): "config band weights (Python floats), before any tensor",
    ("core/starling_layer.py", "k = int(cfg.starling.filter_check_every)"): "config value, in __init__",
    ("core/safety_filter.py", "check_every = int(check_every)"): "keyword argument (Python int)",
    ("core/safety_filter.py", "live = (has_pair[work] & ~converged.all(dim=-1)).nonzero().squeeze(1)"):
        "the early stop's one host sync every check_every sweeps (D10); check_every 0 never reaches it",
    ("core/play.py", "max_steps = game.ticks if max_steps is None else int(max_steps)"): "argument, before the loop",
    ("core/play.py", "if steps % CHECK_EVERY_STEPS == 0 and bool(finished.all()):"):
        "the match loop's end check every CHECK_EVERY_STEPS steps, outside game.step (scoring, not training)",
    ("models/commander.py", "value = float(getattr(self, f.name))"): "dataclass __post_init__ on config numbers",
    ("models/fitted.py", 'model_dt_s = float(px4.pop("model_dt_s"))'): "parameter file, in __init__",
    ("models/fitted.py", 'self.vertical = {k: float(v) for k, v in cfg["px4_vertical"].items()}'): "parameter file",
    ("models/fitted.py", "self.delay_n = int(math.floor(d))"): "parameter file, in __init__",
    ("models/fitted.py", "self.safety_filter = bool(safety_filter)"): "argument, in __init__",
    ("models/fitted.py", "self.filter_iterations = int(filter_iterations)"): "argument, in __init__",
    ("models/fitted.py", "self.hover_seed = bool(hover_seed)"): "argument, in __init__",
    ("models/fitted.py", 'self._filter_cap_mps = torch.tensor(float(self.filter_cfg["max_speed_mps"]), '
                         'device=device, dtype=dtype)'): "parameter file, in __init__ (made a device tensor once)",
}


def test_game_modules_have_no_host_calls():
    models = {f"models/{p.name}" for p in (SRC / "models").glob("*.py")}
    assert models <= set(_STEP_FILES) | _OFFLINE_MODELS, f"new model module(s) to classify: {models - set(_STEP_FILES)}"
    used = set()
    for f in _STEP_FILES:
        for line in (SRC / f).read_text().splitlines():
            code = line.split("#", 1)[0].strip()
            if not _HOST.search(code):
                continue
            key = (f, code)
            assert key in _ALLOWED, f"host read in {f}: {code!r} (move it out of the step, or allow-list it with why)"
            used.add(key)
    assert used == set(_ALLOWED), f"allow-list entries no longer in the code: {set(_ALLOWED) - used}"


def test_host_scan_pattern():
    for bad in ["x.item()", "t.cpu()", "import numpy as np", "i = m.nonzero()", "if bool(done.any()):", "float(t.max())",
                "int(k.sum())"]:
        assert _HOST.search(bad), bad
    for ok in ['float("inf")', "x.float()", "(a == b).int()", "torch.full_like(d, float('nan'))", "a.bool()"]:
        assert not _HOST.search(ok), ok


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA only")
@pytest.mark.parametrize("starling", [False, True])
def test_step_runs_under_sync_debug_error(starling):
    cfg, steps = CFG.replace(dropout_fraction=0.2), 1300
    if starling:   # Starling layer, filter without early stop (check_every 0); short games so auto-reset runs often
        cfg = cfg.replace(**{"starling.enabled": True, "starling.filter_iterations": 20,
                             "starling.filter_check_every": 0, "rules.game_steps": 40})
        steps = 130
    g = SvgGame(cfg, 256, 3, 2, device="cuda", seed=1)
    a = {"guard": torch.rand(256, 3, 4, device="cuda") * 2 - 1, "strike": torch.rand(256, 2, 4, device="cuda") * 2 - 1}
    g.step(a)
    torch.cuda.set_sync_debug_mode("error")
    try:
        done = torch.zeros(256, dtype=torch.bool, device="cuda")
        for _ in range(steps):
            done |= g.step(a).done
    finally:
        torch.cuda.set_sync_debug_mode(0)
    assert bool(done.all())                                          # every game auto-reset at least once


def test_contact_tag_beats_zone_on_the_same_step():
    """Tie rule: tags come before the zone test. The Strike drone enters the zone (radius 0.4) and comes within
    contact (0.5 m) of the Guard drone on the same step (step 1): Guard win. Without the Guard drone near, the
    same move scores."""
    cfg = CFG.replace(preset="contact")

    def first_step(guard_xy):
        sc = Scenario("tie", 4.0, (0.0, 0.0), 0.4, (guard_xy, (-0.41, 0.0)))
        return SvgGame(cfg, N, 1, 1, device="cpu", scenario=sc).step({"guard": z(1), "strike": act_x(1, 1.0)})

    out = first_step((0.1, 0.0))            # strike to x = -0.385: 0.385 m from the zone centre, 0.485 m from the guard
    assert out.info["tagged"].all() and (out.outcome == GUARD_WIN).all() and (out.end_step == 1).all()
    out = first_step((1.5, 1.5))
    assert not out.info["tagged"].any() and (out.outcome == STRIKE_WIN).all() and (out.end_step == 1).all()
