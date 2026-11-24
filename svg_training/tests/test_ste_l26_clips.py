"""STE task L2.6 follow-up clips (scripts/ste_l26_clips.py): 2-D replays with the height panel of the same games on tier 1
and tier 2 (spec ste_learning/drafts/L2_6_SPEC.md, "Clips"). CPU only: the choice rule, and the script end to end with
--dry-cpu (tier 2 on the PyTorch reference world)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import ste_l26_clips as clips  # noqa: E402


def test_choice_rule_first_game_whose_outcome_differs_else_game_0():
    assert clips.choose([2, 2, 1, 1], [2, 1, 1, 2]) == (1, "first game whose outcome differs between the tiers")
    assert clips.choose([2, 1], [2, 1]) == (0, "no game differs between the tiers: game 0")
    assert clips.choose([2, 0, 1], [2, 1, 2]) == (2, "first game whose outcome differs between the tiers")   # unfinished skipped


def test_clip_cells_are_the_specs():
    assert clips.CELLS == (("landing_gy_1p15", "guard_mark_edge", "strike_low"),
                           ("landing_gy_1p15", "guard_mark_edge", "strike_straight"))


def test_dry_cpu_writes_both_tiers_of_the_same_game(tmp_path):
    out = tmp_path / "clips"
    code = clips.main(["--out-dir", str(out), "--games", "2", "--max-ticks", "600", "--dry-cpu"])
    assert code == 0
    meta = json.loads((out / "clips.json").read_text())
    assert meta["dry_cpu"] is True and meta["seed"] == clips.CLIP_SEED and len(meta["cells"]) == 2
    for cell in meta["cells"]:
        assert len(cell["gifs"]) == 2 and {g["tier"] for g in cell["gifs"]} == {1, 2}
        assert len({g["game"] for g in cell["gifs"]}) == 1                     # the same game on both tiers
        for g in cell["gifs"]:
            assert (out / g["file"]).is_file() and (out / g["file"]).stat().st_size > 0
            assert f"tier{g['tier']}" in g["file"]
        assert len(cell["outcomes"]["tier1"]) == len(cell["outcomes"]["tier2"]) == 2


def test_tier1_only_draws_a_reach_and_a_hold_without_isaac(tmp_path):
    out = tmp_path / "t1"
    code = clips.main(["--out-dir", str(out), "--games", "8", "--max-ticks", "600", "--tier1-only"])
    assert code == 0
    meta = json.loads((out / "clips.json").read_text())
    assert meta["tier1_only"] is True and "tier 2 pending" in meta["rule"]
    for cell in meta["cells"]:
        assert {g["tier"] for g in cell["gifs"]} == {1} and "tier2" not in cell["outcomes"]
        kinds = [g["outcome"] for g in cell["gifs"]]
        o = cell["outcomes"]["tier1"]
        assert kinds == [k for k, code in (("reach", 1), ("hold", 2)) if code in o]   # first reach, then first hold
        for g in cell["gifs"]:
            assert g["game"] == o.index(1 if g["outcome"] == "reach" else 2)
            assert (out / g["file"]).is_file()


def test_both_tiers_play_the_same_cpu_drawn_starts(tmp_path, monkeypatch):
    """CLIP-T2 (24 Nov 2026): tier 2 ran on CUDA, whose generator drew other starts than tier 1's CPU draw from the same
    clip seed (diagnostic runs/2026-11-24_clip_t2_diag: up to 5.5 m apart; every path gave a reach on the CUDA starts, a
    mix on the CPU ones). Both tiers must get the clip starts drawn once on the CPU, whatever the tier-2 device."""
    from svg_training.viz import replay
    real, seen = replay.record_games, []

    def spy(cfg, *args, **kw):
        seen.append((kw.get("device"), kw.get("starts")))
        return real(cfg, *args, **kw)

    monkeypatch.setattr(replay, "record_games", spy)
    code = clips.main(["--out-dir", str(tmp_path / "c"), "--games", "2", "--max-ticks", "200", "--dry-cpu"])
    assert code == 0 and len(seen) == 4                                         # 2 cells x 2 tiers
    import ste_tier12_l26 as drv
    s = drv.load_settings(clips.GATES)
    g = {x["name"]: x for x in s["groups"]}["landing_gy_1p15"]
    want = clips.clip_starts(drv.game_cfg(s, g["tier1_game"]), 2)
    for _dev, st in seen:
        assert st is not None, "a tier was recorded on its own device's start draw"
        assert st[0].device.type == "cpu" and torch_equal(st[0], want[0]) and torch_equal(st[1], want[1])


def test_clip_starts_leave_tier1_games_unchanged():
    """The fix leaves tier 1 as published: with the CPU clip starts given, every tier-1 game of both cells (every frame,
    outcome and end step) equals record_games' own CPU draw from the clip seed."""
    import ste_tier12_l26 as drv
    from svg_training.viz.replay import record_games
    s = drv.load_settings(clips.GATES)
    cfg1 = drv.game_cfg(s, {x["name"]: x for x in s["groups"]}["landing_gy_1p15"]["tier1_game"])
    n = 8
    starts = clips.clip_starts(cfg1, n)
    for _group, guard, strike in clips.CELLS:
        kw = dict(num_games=n, seed=clips.CLIP_SEED, band=0, max_steps=400)
        own = record_games(cfg1, 3, 3, guard, strike, **kw)
        given = record_games(cfg1, 3, 3, guard, strike, starts=starts, **kw)
        assert len(own) == n and [r.game_index for r in given] == [r.game_index for r in own]
        for a, b in zip(given, own):
            assert (a.outcome, a.end_step) == (b.outcome, b.end_step)
            assert np.array_equal(a.pos_m, b.pos_m) and np.array_equal(a.alive, b.alive)
            assert np.array_equal(a.pos_m[0], starts[0][a.game_index].numpy())


def torch_equal(a, b) -> bool:
    import torch
    return bool(torch.equal(a.cpu(), b.cpu()))
