"""The L0.13 learning-curve figure states what its curves and bands are read on, and draws both parked bands with an
outline so that two overlapping bands stay visible (QC of T53)."""
import sys

import matplotlib
matplotlib.use("Agg")
from matplotlib.figure import Figure  # noqa: E402

from _ste_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import ste_tier2_l013 as driver  # noqa: E402


def point(update, tier, networks, rate):
    return {"update": update, "game_steps": update * 1_000_000, "tier": tier, "networks": networks, "k": int(rate * 256),
            "n": 256, "rate": rate, "seed": 130900}


def test_the_curve_figure_names_its_starts_and_outlines_both_bands(tmp_path, monkeypatch):
    seen = {}

    def capture(fig, path, *a, **k):
        ax = fig.axes[0]
        seen["texts"] = [t.get_text() for t in fig.texts]
        seen["bands"] = [p for p in ax.patches if p.get_label().startswith("parked Guard")]
    monkeypatch.setattr(Figure, "savefig", capture)
    c1 = [point(6, 1, "t1", 0.56), point(12, 1, "t1", 0.62)]
    c2 = [point(6, 2, "t2", 0.55), point(6, 1, "t2", 0.57), point(6, 2, "t1", 0.55)]
    parked = {"k": 534, "n": 1000, "rate": 0.534, "ci": [0.503, 0.565]}
    driver.curve_figure(c1, c2, parked, parked, tmp_path / "f.png")
    note = " ".join(seen["texts"])
    assert "256 curve starts (seed 130900)" in note and "1,000-start interval" in note
    assert len(seen["bands"]) == 2
    for band in seen["bands"]:
        assert band.get_linewidth() >= 1.0 and band.get_edgecolor()[3] > 0.5     # an opaque outline
