#!/usr/bin/env python3
"""Figures for the S2b records: one function per figure (Task 9 now; other tasks add theirs).

  make_s2b_figures.py standin <out.png> runs/<seed 1 run> [runs/<seed 2 run> ...]
  make_s2b_figures.py standin_bars <out.png> runs/<group with verdict.json> runs/<seed 1 score> [...]

``standin``: the stand-in's learning curves, read from each run folder's TensorBoard event files with
TensorBoard's own ``EventAccumulator`` (the same numbers the TensorBoard web page shows; this is how the
documentation's "screenshots" of training are made, as PNGs from the data, without a browser). One line per seed;
x = game-steps (skrl timestep x the run's num_games from interface.toml).
``standin_bars``: the gate evaluation: hold rate with Wilson 95 % intervals per Strike behaviour for the trained
stand-in (each seed; the gate is per seed), random Guard moves and ``guard_mark_edge`` (if scored; these two summed over the seeds' evaluations), summed over the bands, read from
verdict.json (``train_standin.py verdict``) and the score.py outputs.

Every value plotted is read from the run's own files as written; nothing is smoothed or fitted. Style and palette:
``scripts/make_s0_figures.py``. Each function prints the table it plotted.
"""
from __future__ import annotations

import json
import pathlib
import sys
import tomllib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "source"))
import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from make_s0_figures import INK, INK2, SERIES, style  # noqa: E402

BEHAVIOUR_LABEL = {"strike_straight": "straight", "strike_flank": "flank"}
SKRL_REWARD = "Reward / Total reward (mean)"


def read_scalars(run_dir: str | pathlib.Path) -> dict[str, list[tuple[int, float]]]:
    """{tag: [(step, value), ...]} over every TensorBoard event file in run_dir (sorted by step)."""
    from tensorboard.backend.event_processing.event_accumulator import EventAccumulator

    out: dict[str, list[tuple[int, float]]] = {}
    files = sorted(pathlib.Path(run_dir).glob("events.out.tfevents.*"))
    if not files:
        raise FileNotFoundError(f"{run_dir}: no TensorBoard event file")
    for f in files:
        ea = EventAccumulator(str(f), size_guidance={"scalars": 0})
        ea.Reload()
        for tag in ea.Tags()["scalars"]:
            out.setdefault(tag, []).extend((e.step, e.value) for e in ea.Scalars(tag))
    return {k: sorted(v) for k, v in out.items()}


def _run_meta(run_dir: pathlib.Path) -> dict:
    return tomllib.loads((run_dir / "interface.toml").read_text())


def standin(out: str, *run_dirs: str) -> None:
    """Learning curves of the stand-in: hold rate per Strike behaviour, skrl's mean episode reward, the closest
    Guard-Strike approach (3-D), the filter share and the training speed; one line per seed."""
    runs = [pathlib.Path(r) for r in run_dirs]
    metas = [_run_meta(r) for r in runs]
    data = [read_scalars(r) for r in runs]
    behaviours = list(metas[0]["training"]["opponent_mix"])
    panels = ([(f"game/hold_rate/{b}", f"hold rate v {BEHAVIOUR_LABEL.get(b, b)} Strike", "share of games held",
                (0.0, 1.0)) for b in behaviours]
              + [(SKRL_REWARD, "game reward, both Guard drones summed (skrl)", "reward per game", None),
                 ("game/closest_cross_3d_p05_m", "closest Guard–Strike approach, 3-D", "m (solid p5, dashed min)",
                  None),
                 ("game/filter_share", "safety-filter share", "share of drone-steps", None),
                 ("game/game_steps_per_s", "training speed", "game-steps per second", None)])
    fig, axes = plt.subplots(2, 3, figsize=(15, 8.4), dpi=150, squeeze=False)
    print(f"| run | seed | tag | game-steps | value |\n|---|---|---|---|---|")
    for ax, (tag, title, ylabel, ylim) in zip(axes.flat, panels):
        for i, (r, m, d) in enumerate(zip(runs, metas, data)):
            n = int(m["training"]["num_games"])
            col = SERIES[i % len(SERIES)]
            pts = d.get(tag, [])
            if pts:
                xs = [s * n / 1e6 for s, _ in pts]
                ax.plot(xs, [v for _, v in pts], color=col, linewidth=2, marker="o", markersize=3,
                        label=f"seed {m['seed']}")
                for s, val in pts:
                    print(f"| {r.name} | {m['seed']} | {tag} | {s * n:,} | {val:.4g} |")
            if tag == "game/closest_cross_3d_p05_m":
                mins = d.get("game/closest_cross_3d_min_m", [])
                if mins:
                    ax.plot([s * n / 1e6 for s, _ in mins], [v for _, v in mins], color=col, linewidth=1.2,
                            linestyle="--")
        style(ax, title, "game-steps (millions)", ylabel)
        if ylim:
            ax.set_ylim(*ylim)
        if not any(d.get(tag) for d in data):
            ax.text(0.5, 0.5, "not logged", transform=ax.transAxes, ha="center", color=INK2)
    axes[0, 0].legend(frameon=False, fontsize=9, labelcolor=INK)
    fig.suptitle(f"Stand-in (pipe test), {metas[0]['motion']}: observed in the training simulator",
                 x=0.01, ha="left", fontsize=13, color=INK)
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)
    print(f"wrote {out}")


def standin_bars(out: str, group_dir: str, *score_dirs: str) -> None:
    """Gate evaluation: trained stand-in (per seed), random and guard_mark_edge, per Strike behaviour, Wilson 95 %."""
    from svg_training.core.metrics import wilson_interval

    ver = json.loads((pathlib.Path(group_dir) / "verdict.json").read_text())
    behaviours = list(dict.fromkeys(c["behaviour"] for c in ver["cells"]))
    edge: dict[str, tuple[int, int]] = {}
    for d in score_dirs:
        for r in json.loads((pathlib.Path(d) / "scores.json").read_text())["rows"]:
            if r["guard"] == "guard_mark_edge" and r.get("size") == "2v1":
                k, nn = edge.get(r["strike"], (0, 0))
                edge[r["strike"]] = (k + int(r["guard_wins"]), nn + int(r["games"]))
    fig, axes = plt.subplots(1, len(behaviours), figsize=(6.5 * len(behaviours), 4.8), dpi=150, sharey=True,
                             squeeze=False)
    print("| behaviour | who | hold rate | 95 % interval | games |\n|---|---|---|---|---|")
    for ax, b in zip(axes.flat, behaviours):
        bars = []
        for c in [c for c in ver["cells"] if c["behaviour"] == b]:
            bars.append((f"stand-in\nseed {c['seed']}", c["trained"], SERIES[0]))
        rk = sum(c["random"]["guard_wins"] for c in ver["cells"] if c["behaviour"] == b)
        rn = sum(c["random"]["games"] for c in ver["cells"] if c["behaviour"] == b)
        lo, hi = wilson_interval(rk, rn)
        bars.append(("random\n(all seeds)", {"hold_rate": rk / rn, "ci_low": lo, "ci_high": hi, "games": rn},
                     SERIES[1]))
        if b in edge:
            k, nn = edge[b]
            lo, hi = wilson_interval(k, nn)
            bars.append(("mark edge, scripted\n(all seeds)",
                         {"hold_rate": k / nn, "ci_low": lo, "ci_high": hi, "games": nn}, SERIES[2]))
        for j, (label, r, col) in enumerate(bars):
            ax.bar(j, r["hold_rate"], color=col, width=0.6)
            ax.errorbar(j, r["hold_rate"], yerr=[[r["hold_rate"] - r["ci_low"]], [r["ci_high"] - r["hold_rate"]]],
                        color=INK, capsize=4, linewidth=1.2)
            print(f"| {b} | {label.replace(chr(10), ' ')} | {r['hold_rate']:.3f} | {r['ci_low']:.3f}–"
                  f"{r['ci_high']:.3f} | {r['games']} |")
        ax.set_xticks(range(len(bars)), [x[0] for x in bars])
        ax.set_ylim(0, 1)
        style(ax, f"v {BEHAVIOUR_LABEL.get(b, b)} Strike (2v1, all bands)", "", "share of games held")
    fig.suptitle(f"Stand-in (pipe test) gate check: {ver['verdict']}, observed in the training simulator",
                 x=0.01, ha="left", fontsize=13, color=INK)
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)
    print(f"wrote {out}")


FIGURES = {"standin": standin, "standin_bars": standin_bars}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) < 3 or argv[0] not in FIGURES:
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        return 2
    FIGURES[argv[0]](*argv[1:])
    return 0


if __name__ == "__main__":
    sys.exit(main())
