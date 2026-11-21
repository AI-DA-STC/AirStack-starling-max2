"""VID-1c: the L0.3 2-D clips re-drawn with the height panel from the run's kept video slots (CPU only)."""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("redraw", ROOT / "scripts" / "redraw_ste_l03_clips.py")
rd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rd)


def test_doc_names_match_the_published_gifs():
    """Same names as the GIFs already in docs/media/ste_l03/ (they are replaced, not added)."""
    assert rd.doc_name("t1_cpu_t41", "hold", 0) == "tier1_cpu_t41_v_s20_hold_slot0.gif"
    assert rd.doc_name("t2_t41", "strike_win", 5) == "tier2_t41_v_s20_reach_slot5.gif"
    assert rd.doc_name("t2_parked", "hold", 1) == "tier2_parked_v_s20_hold_slot1.gif"
    assert rd.doc_name("t1_cuda_t41", "strike_win", 6) == "tier1_cuda_t41_v_s20_reach_slot6.gif"
    published = {p.name for p in (ROOT / "docs" / "media" / "ste_l03").glob("*.gif")}
    assert len(published) == 8 and all(n.startswith(("tier1_", "tier2_")) for n in published)


def test_the_height_panel_is_on():
    src = (ROOT / "scripts" / "redraw_ste_l03_clips.py").read_text()
    assert "height_panel=True" in src and "height_panel=False" not in src
