"""Match loop and metrics (S2 Task 6): first game per slot, strategy resets, Wilson interval, summary rows."""
import math
import pathlib
import re
import sys

import pytest
import torch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
from svg_training.core.game import GUARD_WIN, SCENARIOS, STRIKE_WIN, SvgGame  # noqa: E402
from svg_training.core.game_config import load_game_cfg  # noqa: E402
from svg_training.core.metrics import hold_rate, summarise, wilson_interval  # noqa: E402
from svg_training.core.play import MatchResult, play_match  # noqa: E402
from svg_training.opponents.scripted import make_strategy  # noqa: E402

CFG = load_game_cfg(use_local=False)[0]
CORE = ROOT / "source" / "svg_training" / "core"


def mk(spec, team, n, dev="cpu", cfg=CFG):
    return make_strategy(spec, team, cfg, n, dev, 0)


def test_wilson_interval_known_values():
    assert wilson_interval(0, 1000) == pytest.approx((0.0, 0.00383), abs=1e-4)
    assert wilson_interval(500, 1000) == pytest.approx((0.4691, 0.5309), abs=1e-4)
    assert wilson_interval(1000, 1000) == pytest.approx((1 - 0.00383, 1.0), abs=1e-4)
    assert all(math.isnan(v) for v in wilson_interval(0, 0))


def test_hold_rate_counts_finished_games_only():
    out = torch.tensor([GUARD_WIN, STRIKE_WIN, 0, GUARD_WIN], dtype=torch.int8)
    assert hold_rate(out) == pytest.approx(2 / 3)
    assert math.isnan(hold_rate(torch.zeros(3, dtype=torch.int8)))


def test_play_counts_first_game_per_slot():
    """lab4_open: the Strike drone reaches the zone on step 37, the slot auto-resets and the same game ends again
    on step 74. Played to step 100, every slot counts once, with end step 37."""
    n = 6
    game = SvgGame(CFG, n, 1, 1, device="cpu", scenario=SCENARIOS["lab4_open"])
    res = play_match(game, mk("zero", "guard", n), mk("strike_straight", "strike", n), max_steps=200)
    assert res.steps_played == 100                     # stopped at the first host check (step 100), after step 74
    assert (res.outcome == STRIKE_WIN).all() and (res.end_step == 37).all()
    rows = summarise(res, by=())
    assert rows[0]["games"] == n and rows[0]["hold_rate"] == 0.0 and rows[0]["mean_end_step"] == 37
    # Guard at (1.5, 1.5), Strike on y = 0 from x = -1.51: closest at its last position x = -1.51 + 37 * 0.025
    assert rows[0]["closest_cross_m"] == pytest.approx(math.hypot(1.5 + 1.51 - 37 * 0.025, 1.5), abs=1e-4)
    assert rows[0]["rule_breach_rate"] == 0.0 and rows[0]["filter_rate"] == 0.0


def test_play_stops_at_first_check_after_all_finished():
    n = 4
    game = SvgGame(CFG, n, 1, 1, device="cpu", scenario=SCENARIOS["lab4_open"])
    res = play_match(game, mk("zero", "guard", n), mk("strike_straight", "strike", n), max_steps=1000)
    assert res.steps_played == 100


def test_unfinished_slots_are_left_out():
    n = 3
    game = SvgGame(CFG, n, 1, 1, device="cpu", scenario=SCENARIOS["lab4_open"])
    res = play_match(game, mk("zero", "guard", n), mk("strike_straight", "strike", n), max_steps=20)
    assert (res.outcome == 0).all()
    assert summarise(res, by=()) == []


class Recorder:
    """Stands still and records every reset mask."""
    name = "recorder"

    def __init__(self, team):
        self.team, self.resets = team, []

    def reset(self, games):
        self.resets.append(games.clone())

    def act(self, obs):
        return obs.new_zeros(*obs.shape[:2], 4)


def test_play_resets_strategies_with_done():
    n = 5
    game = SvgGame(CFG.replace(**{"rules.game_steps": 30}), n, 1, 1, device="cpu", seed=3)
    g, s = Recorder("guard"), Recorder("strike")
    res = play_match(game, g, s, max_steps=65)
    assert g.resets[0].all() and s.resets[0].all()                  # all True before the first step
    assert len(g.resets) == 1 + 65
    assert g.resets[30].all() and not g.resets[29].any()             # time-out on step 30 -> done
    assert (res.outcome == GUARD_WIN).all() and (res.end_step == 30).all()


def test_play_refuses_swapped_teams():
    game = SvgGame(CFG, 2, 1, 1, device="cpu")
    with pytest.raises(ValueError):
        play_match(game, mk("strike_straight", "strike", 2), mk("zero", "guard", 2))


def test_scenario_size_matches_band_reporting():
    """band=2 games all have a side in [10, 16] m and are reported as 'large'; a scenario reports its own band."""
    n = 64
    game = SvgGame(CFG, n, 2, 1, device="cpu", seed=5, band=2)
    sides = [game.arenas.side_m.clone()]
    res = play_match(game, mk("guard_mark_edge", "guard", n), mk("strike_straight", "strike", n))
    sides.append(game.arenas.side_m)
    for side in sides:
        assert ((side >= 10.0) & (side <= 16.0)).all()
    assert (res.band == 2).all()
    rows = summarise(res)
    assert [r["band"] for r in rows] == ["large"] and rows[0]["games"] == n
    game = SvgGame(CFG, 4, 1, 1, device="cpu", scenario=SCENARIOS["large16_open"])
    res = play_match(game, mk("zero", "guard", 4), mk("strike_straight", "strike", 4))
    assert [r["band"] for r in summarise(res)] == ["large"]


def test_summarise_groups_and_percentiles():
    t = torch.tensor
    res = MatchResult(outcome=t([2, 2, 1, 2, 0], dtype=torch.int8), end_step=t([10, 20, 30, 40, 0]),
                      band=t([0, 0, 0, 2, 2]), closest_cross_m=t([1.0, 2.0, 3.0, float("inf"), 0.1]),
                      rule_breach=t([True, False, False, False, True]),
                      filter_corrected_rate=t([0.5, 0.0, 0.25, 0.0, 1.0]),
                      start_miss=t([True, False, False, False, True]))
    rows = summarise(res)
    lab, large = rows
    assert lab["band"] == "lab" and lab["games"] == 3 and lab["hold_rate"] == pytest.approx(2 / 3)
    assert lab["closest_cross_m"] == 1.0 and lab["closest_cross_p50_m"] == pytest.approx(2.0)
    assert lab["rule_breach_rate"] == pytest.approx(1 / 3) and lab["start_miss_rate"] == pytest.approx(1 / 3)
    assert lab["filter_rate"] == pytest.approx(0.25) and lab["mean_end_step"] == pytest.approx(20.0)
    assert large["games"] == 1 and large["closest_cross_m"] is None     # unfinished slot left out; inf -> None
    both = summarise(res, by=("band", "start_miss"))
    assert {(r["band"], r["start_miss"]) for r in both} == {("lab", True), ("lab", False), ("large", False)}
    with pytest.raises(ValueError):
        summarise(res, by=("size",))


def test_play_module_has_one_host_check():
    src = (CORE / "play.py").read_text()
    assert not re.search(r"\.(item|cpu|numpy|tolist)\(|import numpy|nonzero\(", src)
    assert len(re.findall(r"\bbool\(", src)) == 1                     # the every-100-steps finished check


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA only")
@pytest.mark.parametrize("starling", [False, True])
@pytest.mark.parametrize("guard", ["guard_mark_edge", "guard_mark_inside", "guard_field", "guard_mirror", "random"])
def test_play_loop_runs_under_sync_debug_error(starling, guard):
    """99 steps (before the first host check): the match loop, the scripted strategies and the game make no
    host sync."""
    cfg = CFG
    if starling:
        cfg = cfg.replace(**{"starling.enabled": True, "starling.filter_iterations": 20,
                             "starling.filter_check_every": 0})
    n = 128
    game = SvgGame(cfg, n, 3, 2, device="cuda", seed=1)
    g, s = make_strategy(guard, "guard", cfg, n, "cuda", 0), make_strategy("strike_flank", "strike", cfg, n, "cuda", 0)
    play_match(game, g, s, max_steps=2)                                 # warm-up (allocations, lazy init)
    torch.cuda.set_sync_debug_mode("error")
    try:
        res = play_match(game, g, s, max_steps=99)
    finally:
        torch.cuda.set_sync_debug_mode(0)
    assert res.steps_played == 99
