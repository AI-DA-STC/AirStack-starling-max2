"""The Phase 4 ladder figure (plan D8). Reads the rows' ``scores.json`` under ``runs/nus_port/phase4/`` (git-ignored) and draws, from
``svg_training.nus.ladder``'s outputs only, the Strike reach rate with its Wilson 95 % interval for the core pairs: one panel per Strike
player, one line per Guard player, the parked Guard (the baseline) dashed black. Rates only: no geometry is drawn and no length is written.

    cd <svg_training>; unset PYTHONPATH; PYTHONPATH=source ~/miniconda3/envs/env_isaaclab/bin/python scripts/make_nus_phase4_figures.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from svg_training.nus import hangar as H  # noqa: E402
from svg_training.nus import ladder as L  # noqa: E402

OUT = ROOT / "docs" / "figures" / "nus_phase4_ladder.png"
STYLE = {"G19": ("tab:blue", "-"), "P3G": ("tab:green", "-"), "ApfGuard": ("tab:orange", "-"), "ParkedGuard": ("black", "--")}


def main() -> int:
    settings = H.load_phase4()
    fig_cfg = settings["figure"]
    rows = {}
    for row_id in fig_cfg["row_order"]:
        path = L.PHASE4_DIR / f"row_{row_id}" / "scores.json"
        if path.exists():
            rows[row_id] = {(p["guard"], p["strike"]): p for p in json.loads(path.read_text())["pairs"]}
    strikes, guards = settings["pairs"]["core_strikes"], settings["pairs"]["core_guards"]
    fig, axes = plt.subplots(1, len(strikes), figsize=tuple(fig_cfg["size_in"]), sharey=True)
    ids = [r for r in fig_cfg["row_order"] if r in rows]
    for ax, strike in zip(axes, strikes):
        for shift, guard in enumerate(guards):
            xs, ys, low, high = [], [], [], []
            for slot, row_id in enumerate(ids):
                pair = rows[row_id].get((guard, strike))
                if pair is None:
                    continue
                r = pair["reach"]
                xs.append(slot + (shift - len(guards) / 2) * fig_cfg["offset"])
                ys.append(r["rate"])
                low.append(r["rate"] - r["ci_low"])
                high.append(r["ci_high"] - r["rate"])
            colour, line = STYLE[guard]
            ax.errorbar(xs, ys, yerr=[low, high], color=colour, linestyle=line, marker="o", capsize=2, label=guard)
        ax.set_title(f"Strike: {strike}")
        ax.set_xticks(range(len(ids)), ids)
        ax.set_xlabel("ladder row")
        ax.grid(True)
    axes[0].set_ylabel("Strike reach rate (95 % Wilson interval)")
    axes[0].legend(title="Guard", loc="best")
    fig.tight_layout()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=fig_cfg["dpi"])
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
