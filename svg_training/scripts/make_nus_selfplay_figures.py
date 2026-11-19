"""The NUS self-play cross-play figure for docs/WHAT_WE_DID_DAY_BY_DAY.md (Figure 1).

Reads the cross-play matrix written on the home RTX 5090 by the evaluation of NUS's self-play runs on the hangar geometry (NUS's own
evaluator, 256 games per pair, deterministic actions; the matrix file is 5090 only, outside every git repository) and draws the Strike
win rate for every Guard policy (rows) against every Strike policy (columns), grouped by seed. Rates only. Training simulator (NUS's
2-D JAX game); not a flight result.

    cd <svg_training>; unset PYTHONPATH; PYTHONPATH=source ~/miniconda3/envs/env_isaaclab/bin/python scripts/make_nus_selfplay_figures.py \
        [--matrix ~/ma_skills-self-play/_probes/selfplay_eval/matrix20_raw.json] [--out docs/figures/nus_selfplay_matrix.png]
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MATRIX = Path.home() / "ma_skills-self-play" / "_probes" / "selfplay_eval" / "matrix20_raw.json"
DEFAULT_OUT = ROOT / "docs" / "figures" / "nus_selfplay_matrix.png"


def _key(name: str) -> tuple[int, int]:
    """'s2g19' -> (2, 19)."""
    m = re.fullmatch(r"s(\d+)g(\d+)", name)
    if not m:
        raise ValueError(f"unexpected policy name {name!r}")
    return int(m.group(1)), int(m.group(2))


def _label(name: str, team: str) -> str:
    seed, gen = _key(name)
    return f"s{seed} {team}{gen}"


def draw(matrix_path: Path, out: Path) -> Path:
    data = json.loads(matrix_path.read_text())
    guards, strikes = data["guards"], data["strikes"]
    rates = data["strike_win_matrix_guard_active"]
    row_order = sorted(range(len(guards)), key=lambda i: _key(guards[i]))
    col_order = sorted(range(len(strikes)), key=lambda j: _key(strikes[j]))
    grid = [[rates[i][j] for j in col_order] for i in row_order]

    fig, ax = plt.subplots(figsize=(10.5, 8.5))
    im = ax.imshow(grid, cmap="RdBu_r", vmin=0.0, vmax=1.0, aspect="equal")
    ax.set_xticks(range(len(col_order)), [_label(strikes[j], "S") for j in col_order], rotation=90, fontsize=8)
    ax.set_yticks(range(len(row_order)), [_label(guards[i], "G") for i in row_order], fontsize=8)
    ax.set_xlabel("Strike team policy (seed, generation)")
    ax.set_ylabel("Guard team policy (seed, generation)")
    for idx, names, axis in ((row_order, guards, "y"), (col_order, strikes, "x")):
        seeds = [_key(names[k])[0] for k in idx]
        for pos in range(1, len(seeds)):
            if seeds[pos] != seeds[pos - 1]:
                (ax.axhline if axis == "y" else ax.axvline)(pos - 0.5, color="black", linewidth=1.2)
    for r, row in enumerate(grid):
        for c, v in enumerate(row):
            ax.text(c, r, "1" if v >= 0.995 else f"{v:.2f}".lstrip("0"), ha="center", va="center", fontsize=6,
                    color="white" if abs(v - 0.5) > 0.35 else "black")
    cbar = fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02)
    cbar.set_label("Strike win rate (red: Strike team wins; blue: Guard team holds)")
    n = data.get("episodes_per_pair")
    ax.set_title(f"NUS self-play on the hangar geometry: Strike win rate, {n} games per pair\n"
                 "seeds 1 and 3 to generation 8, seed 2 to generation 20 (training simulator, NUS's 2-D game)", fontsize=10)
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=110)
    plt.close(fig)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX, help="cross-play matrix JSON (5090 only)")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args(argv)
    if not args.matrix.is_file():
        print(f"no matrix file at {args.matrix} (it exists on the home RTX 5090 only)")
        return 2
    print(draw(args.matrix, args.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
