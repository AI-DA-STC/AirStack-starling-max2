"""STE task L2.6 follow-up clips (scripts/ste_l26_clips.py): 2-D replays with the height panel of the same games on tier 1
and tier 2 (spec ste_learning/drafts/L2_6_SPEC.md, "Clips"). CPU only: the choice rule, and the script end to end with
--dry-cpu (tier 2 on the PyTorch reference world)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

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
