#!/usr/bin/env python3
"""Figures for the S2b records: one function per figure (Tasks 7 and 9; Task 8 adds its own).

  make_s2b_figures.py standin <out.png> runs/<seed 1 run> [runs/<seed 2 run> ...]
  make_s2b_figures.py standin_bars <out.png> runs/<group with verdict.json> runs/<seed 1 score> [...]
  make_s2b_figures.py steps <out.png> runs/<step-test run>                      (Task 7, s2b_steps.png)
  make_s2b_figures.py real_replay <out.png> runs/<step-test run>                (Task 7, s2b_real_replay.png)
  make_s2b_figures.py throughput <out.png> runs/<run>/results.jsonl [S0 results.jsonl]   (Task 7, s2b_throughput.png)
  make_s2b_figures.py scripted_compare <out.png> runs/<compare run>            (Task 8, s2b_scripted_compare.png)
  make_s2b_figures.py vertical_pass <out.png> runs/<compare run>               (Task 8, s2b_scripted_compare_vertical.png)

``standin``: the stand-in's learning curves, read from each run folder's TensorBoard event files with
TensorBoard's own ``EventAccumulator`` (the same numbers the TensorBoard web page shows; this is how the
documentation's "screenshots" of training are made, as PNGs from the data, without a browser). One line per seed;
x = game-steps (skrl timestep x the run's num_games from interface.toml).
``standin_bars``: the gate evaluation: hold rate with Wilson 95 % intervals per Strike behaviour for the trained
stand-in (each seed; the gate is per seed), random Guard moves and ``guard_mark_edge`` (if scored; these two summed over the seeds' evaluations), summed over the bands, read from
verdict.json (``train_standin.py verdict``) and the score.py outputs.

``scripted_compare``: paired scripted games, hold rate with Wilson 95 % intervals per band for the tier 1 Starling
layer and the physics drone side by side; one panel per size x Strike behaviour; colour = Guard strategy, open circle
= tier 1, filled square = physics drone. Read from ``compare_backends.py``'s compare.json.
``vertical_pass``: per cell, the share of games in which a Guard and a Strike drone passed one over the other
(closest horizontal approach under 0.55 m while the closest 3-D approach stayed at or above 1.0 m, so the two were at
least 0.84 m apart in height at that moment), tier 1 against the physics drone. Read from the score folders that
compare.json names (per_game.npz).

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
                seeds = [mm["seed"] for mm in metas]
                label = f"seed {m['seed']}" if len(set(seeds)) == len(seeds) else r.name   # same seed: name the runs
                ax.plot(xs, [v for _, v in pts], color=col, linewidth=2, marker="o", markersize=3, label=label)
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
            ax.errorbar(j, r["hold_rate"], yerr=[[max(0.0, r["hold_rate"] - r["ci_low"])], [max(0.0, r["ci_high"] - r["hold_rate"])]],
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


def _load_run(run_dir: str | pathlib.Path) -> tuple[dict, dict]:
    import numpy as np

    run = pathlib.Path(run_dir)
    return json.loads((run / "results.json").read_text()), dict(np.load(run / "arrays.npz"))


def steps(out: str, run_dir: str) -> None:
    """Task 7: speed along the stick command for each step (one panel per step): the physics drone in the world,
    tier 1's drone model and the command, from the step-test run's arrays.npz (game g = step g mod 5)."""
    import numpy as np

    res, arr = _load_run(run_dir)
    sched = json.loads(str(arr["schedule"]))
    seen, games = set(), []
    for g, info in enumerate(sched):
        if info["step"] not in seen:
            seen.add(info["step"])
            games.append(g)
    rows = {r["name"]: r for r in res["steps"]["steps"]}
    fig, axes = plt.subplots(1, len(games), figsize=(3.6 * len(games), 4.4), dpi=150, squeeze=False, sharey=True)
    print("| step | t (s) | command | physics | tier 1 |\n|---|---|---|---|---|")
    for ax, g in zip(axes.flat, games):
        info = sched[g]
        name = info["step"]
        r = rows[name]
        cmd = np.asarray(r["cmd_mps"], float)
        axis = cmd / np.linalg.norm(cmd)
        end = info["ticks"] + 1
        t = np.arange(end) * 0.05
        vp = arr["physics_step_vel"][:end, g, 0] @ axis
        v1 = arr["tier1_step_vel"][:end, g, 0] @ axis
        c = np.concatenate(([0.0], arr["physics_cmd"][:end - 1, g] @ axis))
        ax.step(t, c, where="pre", color=INK2, linewidth=1.4, linestyle="--", label="command")
        ax.plot(t, vp, color=SERIES[0], linewidth=2.0, label="physics drone (Isaac Lab)")
        ax.plot(t, v1, color=SERIES[1], linewidth=2.0, label="tier 1 (exploratory model)")
        axis_txt = "up" if abs(axis[2]) > 0.9 else ("x" if abs(axis[0]) > 0.9 else ("y" if abs(axis[1]) > 0.9
                                                                                    else "diagonal"))
        style(ax, f"{name}{'' if r['gated'] else ' (INFO)'}", "time from the step's start (s)",
              f"speed along the command, {axis_txt} (m/s)" if g == games[0] else "")
        ax.text(0.98, 0.04, f"RMS gap {r['rms_vs_tier1_mps']:.3f} m/s", transform=ax.transAxes, ha="right",
                color=INK2, fontsize=8)
        for k in range(0, end, 20):
            print(f"| {name} | {t[k]:.2f} | {c[k]:.3f} | {vp[k]:.3f} | {v1[k]:.3f} |")
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, frameon=False, fontsize=9, labelcolor=INK, loc="lower center", ncol=3)
    fig.suptitle(f"Step tests: physics drone against tier 1, the same stick commands through the same commander and "
                 f"filter ({res['verdict']}, observed in the training simulator)", x=0.01, ha="left", fontsize=12,
                 color=INK)
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    fig.savefig(out)
    plt.close(fig)
    print(f"wrote {out}")


def real_replay(out: str, run_dir: str) -> None:
    """Task 7: the six held-out legs of log103: the speed the drone logged, the physics drone and tier 1's drone
    model, each fed PX4's logged setpoints, along each leg's direction (the mean direction of its speed setpoint)."""
    import numpy as np

    res, arr = _load_run(run_dir)
    w = np.load(pathlib.Path(run_dir) / "windows.npz")
    legs = res["replay"]["legs"]
    t_rel = arr["physics_replay_t_rel_s"]
    fig, axes = plt.subplots(2, 3, figsize=(14.0, 7.4), dpi=150, squeeze=False)
    print("| leg | RMS physics (m/s) | RMS tier 1 (m/s) |\n|---|---|---|")
    for ax, leg in zip(axes.flat, legs):
        k = leg["game"]
        t = w[f"w{k}_t_s"]
        u = w[f"w{k}_v_ff"][:, :2].mean(axis=0)
        u = u / np.linalg.norm(u)
        t0 = t[0]
        meas_t = t[w[f"w{k}_meas_idx"]] - t0
        ax.plot(t - t0, w[f"w{k}_v_ff"][:, :2] @ u, color=INK2, linewidth=1.2, linestyle="--",
                label="setpoint speed (logged)")
        ax.plot(meas_t, w[f"w{k}_v_meas"] @ u, color=INK, linewidth=0, marker="o", markersize=3,
                label="drone, logged")
        ax.plot(t_rel, arr["physics_replay_vel"][:, k, 0, :2] @ u, color=SERIES[0], linewidth=2.0,
                label="physics drone (Isaac Lab)")
        ax.plot(t - t0, w[f"w{k}_v_tier1"] @ u, color=SERIES[1], linewidth=2.0, label="tier 1 (exploratory model)")
        ax.set_xlim(0, t[-1] - t0)
        style(ax, f"leg {leg['leg']}: RMS physics {leg['rms_physics_mps']:.3f}, tier 1 {leg['rms_tier1_mps']:.3f} m/s",
              "time in the leg's window (s)", "speed along the leg (m/s)")
        print(f"| {leg['leg']} | {leg['rms_physics_mps']:.4f} | {leg['rms_tier1_mps']:.4f} |")
    axes[0, 0].legend(frameon=False, fontsize=8, labelcolor=INK, loc="best")
    fig.suptitle("Real flight, 13 November 2026 (drone_2, log103): six held-out legs replayed at setpoint level "
                 "(observed in the training simulator)", x=0.01, ha="left", fontsize=12, color=INK)
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)
    print(f"wrote {out}")


def throughput(out: str, results_jsonl: str, s0_results: str | None = None, line: str = "20000") -> None:
    """Task 7: drone-steps per second against games for the game on the physics drone (2v1, 5v3; mean of the
    repeats, both repeats as dots), S0's tier 2 benchmark at the same drones per game (dashed, t2_k3 and t2_k8 at
    200 Hz: ARL Robot 1 stand-in drones, random thrust, no controller; from S0's own results file) and S0's decision
    line."""
    rows = [json.loads(x) for x in pathlib.Path(results_jsonl).read_text().splitlines() if x.strip()]
    s0 = []
    if s0_results and pathlib.Path(s0_results).exists():
        s0 = [json.loads(x) for x in pathlib.Path(s0_results).read_text().splitlines() if x.strip()]
    fig, ax = plt.subplots(figsize=(7.6, 4.8), dpi=150)
    print("| series | games | drone-steps/s (mean) |\n|---|---|---|")
    for i, (size, case) in enumerate((("2v1", "t2_k3"), ("5v3", "t2_k8"))):
        col = SERIES[i]
        ok = [r for r in rows if r.get("size") == size and r.get("status") == "ok"]
        games = sorted({r["num_games"] for r in ok})
        means = [sum(r["drone_steps_per_s"] for r in ok if r["num_games"] == n)
                 / sum(1 for r in ok if r["num_games"] == n) for n in games]
        if games:
            ax.plot(games, means, color=col, linewidth=2.0, marker="o", markersize=6,
                    label=f"{size}, physics drone + commander + filter")
            ax.scatter([r["num_games"] for r in ok], [r["drone_steps_per_s"] for r in ok], color=col, s=10, zorder=3)
        for n, v in zip(games, means):
            print(f"| {size} physics | {n} | {v:,.0f} |")
        bad = [r for r in rows if r.get("size") == size and r.get("status") != "ok"]
        for r in bad:
            ax.annotate(r["status"], (r["num_games"], float(line)), color=col, fontsize=8, ha="center")
        s0_ok = [r for r in s0 if r.get("case") == case and r.get("status") == "ok"]
        g0 = sorted({r["num_games"] for r in s0_ok})
        m0 = [sum(r["drone_steps_per_s"] for r in s0_ok if r["num_games"] == n)
              / sum(1 for r in s0_ok if r["num_games"] == n) for n in g0]
        if g0:
            ax.plot(g0, m0, color=col, linewidth=1.4, linestyle="--", marker="s", markersize=4,
                    label=f"S0 tier 2 {case} ({'3' if size == '2v1' else '8'} ARL stand-in drones, no controller)")
            for n, v in zip(g0, m0):
                print(f"| S0 {case} | {n} | {v:,.0f} |")
    ax.axhline(float(line), color=INK2, linewidth=1.2, linestyle=":")
    ax.text(0.01, float(line) * 1.08, f"S0 decision line {float(line):,.0f}", color=INK2, fontsize=8,
            transform=ax.get_yaxis_transform())
    ax.set_xscale("log", base=2)
    ax.set_yscale("log")
    ticks = sorted({r["num_games"] for r in rows} | {r["num_games"] for r in s0 if r.get("case") in ("t2_k3", "t2_k8")})
    ax.set_xticks(ticks, [f"{t:,}" for t in ticks])
    ax.minorticks_off()
    style(ax, "Game on the physics drone (Isaac Lab): throughput\nobserved in the training simulator",
          "games at once", "drone-steps per second")
    ax.legend(frameon=False, fontsize=8, labelcolor=INK, loc="lower right")
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)
    print(f"wrote {out}")


SC_BANDS = ("lab", "middle", "large")


def _num(v, scale: float, fmt: str) -> str:
    """A printed table value: "n/a" for a missing one (a cell with no finished game), else scale * v in fmt."""
    return "n/a" if v is None else format(scale * v, fmt)
SC_BAND_LABEL = {"lab": "lab\n4–6 m", "middle": "middle\n6–10 m", "large": "large\n10–16 m"}


def scripted_compare(out: str, compare_dir: str) -> None:
    """Task 8: hold rate (Wilson 95 %) per band, tier 1 against the physics drone, one panel per size x Strike."""
    from matplotlib.lines import Line2D

    res = json.loads((pathlib.Path(compare_dir) / "compare.json").read_text())
    cells = res["cells"]
    sizes = list(dict.fromkeys(c["size"] for c in cells))
    strikes = list(dict.fromkeys(c["strike"] for c in cells))
    guards = list(dict.fromkeys(c["guard"] for c in cells))
    fig, axes = plt.subplots(len(sizes), len(strikes), figsize=(13, 4.6 * len(sizes)), dpi=150, sharey=True,
                             squeeze=False)
    width = 0.84
    slot = width / len(guards)
    print("| size | Strike | Guard | band | tier 1 hold | physics hold | gap |\n|---|---|---|---|---|---|---|")
    for i, size in enumerate(sizes):
        for k, strike in enumerate(strikes):
            ax = axes[i, k]
            for gi, g in enumerate(guards):
                colour = SERIES[gi % len(SERIES)]
                for side, dx, marker, face in (("tier1", -0.22, "o", "white"), ("physics", 0.22, "s", colour)):
                    xs, ys, lo, hi = [], [], [], []
                    for bi, band in enumerate(SC_BANDS):
                        c = next((c for c in cells if (c["size"], c["strike"], c["guard"], c["band"])
                                  == (size, strike, g, band)), None)
                        if c is None or c[side]["hold_rate"] is None:
                            continue
                        r = c[side]
                        xs.append(bi - width / 2 + slot * (gi + 0.5) + dx * slot)
                        ys.append(100 * r["hold_rate"])
                        lo.append(100 * (r["hold_rate"] - r["ci_low"]))
                        hi.append(100 * (r["ci_high"] - r["hold_rate"]))
                        if side == "physics":
                            print(f"| {size} | {strike} | {g} | {band} | {_num(c['tier1']['hold_rate'], 100, '.1f')} | "
                                  f"{_num(r['hold_rate'], 100, '.1f')} | {_num(c['hold_gap'], 100, '+.1f')} |")
                    ax.errorbar(xs, ys, yerr=[lo, hi], fmt=marker, color=colour, markersize=5, capsize=1.5,
                                linewidth=1.0, markerfacecolor=face)
            for bi in range(1, len(SC_BANDS)):
                ax.axvline(bi - 0.5, color=INK2, linewidth=0.6, alpha=0.4)
            ax.set_xticks(range(len(SC_BANDS)), [SC_BAND_LABEL[b] for b in SC_BANDS])
            ax.set_ylim(-3, 103)
            style(ax, f"{size[0]} Guard v {size[-1]} Strike, {BEHAVIOUR_LABEL.get(strike, strike)} Strike",
                  "arena size band", "hold rate, % of games (95 % interval)" if k == 0 else "")
    handles = [Line2D([], [], color=SERIES[i % len(SERIES)], marker="s", linestyle="", label=f"Guard: {g}")
               for i, g in enumerate(guards)]
    handles += [Line2D([], [], color=INK2, marker="o", markerfacecolor="white", linestyle="",
                       label="tier 1 Starling layer"),
                Line2D([], [], color=INK2, marker="s", linestyle="", label="physics drone (Isaac Lab)")]
    fig.legend(handles=handles, loc="lower center", ncol=4, frameon=False, fontsize=9, labelcolor=INK)
    fig.suptitle(f"Paired scripted games, physics drone v tier 1: {res['verdict']}; observed in the training "
                 "simulator", x=0.01, ha="left", fontsize=13, color=INK)
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    fig.savefig(out)
    plt.close(fig)
    print(f"wrote {out}")


PASS_HORIZ_M, PASS_3D_M = 0.55, 1.0      # vertical_pass: horizontal < 0.55 m while 3-D >= 1.0 m -> >= 0.84 m apart in z


def vertical_pass(out: str, compare_dir: str) -> None:
    """Task 8: share of games with a Guard-Strike pair passing one over the other, tier 1 v physics, per cell."""
    import numpy as np
    from matplotlib.lines import Line2D

    res = json.loads((pathlib.Path(compare_dir) / "compare.json").read_text())
    root = pathlib.Path(__file__).resolve().parents[1]
    sides = {}
    for side, key in (("tier1", "a"), ("physics", "b")):
        pg = {}
        for d in res["meta"][key]:
            d = pathlib.Path(d)
            with np.load((d if d.is_absolute() else root / d) / "per_game.npz") as z:
                pg.update({k: z[k] for k in z.files})
        sides[side] = (res["preset_a"] if side == "tier1" else res["preset_b"], pg)
    cells = res["cells"]
    sizes = list(dict.fromkeys(c["size"] for c in cells))
    strikes = list(dict.fromkeys(c["strike"] for c in cells))
    guards = list(dict.fromkeys(c["guard"] for c in cells))
    fig, axes = plt.subplots(len(sizes), len(strikes), figsize=(13, 4.4 * len(sizes)), dpi=150, sharey=True,
                             squeeze=False)
    width = 0.84
    slot = width / len(guards)
    print("| size | Strike | Guard | band | tier 1 share | physics share |\n|---|---|---|---|---|---|")
    for i, size in enumerate(sizes):
        for k, strike in enumerate(strikes):
            ax = axes[i, k]
            for gi, g in enumerate(guards):
                colour = SERIES[gi % len(SERIES)]
                for bi, band in enumerate(SC_BANDS):
                    share = {}
                    for side, (preset, pg) in sides.items():
                        key = f"{preset}|{size}|{g}|{strike}|{band}"
                        if f"{key}|outcome" not in pg:
                            continue
                        fin = pg[f"{key}|outcome"] != 0
                        hz, c3 = pg[f"{key}|closest_cross_m"][fin], pg[f"{key}|closest_cross_3d_m"][fin]
                        share[side] = float(((hz < PASS_HORIZ_M) & (c3 >= PASS_3D_M)).mean()) if fin.any() else None
                    x = bi - width / 2 + slot * (gi + 0.5)
                    if share.get("physics") is not None:
                        ax.bar(x, 100 * share["physics"], width=slot * 0.8, color=colour)
                    if share.get("tier1") is not None:
                        ax.plot(x, 100 * share["tier1"], marker="o", color=INK, markerfacecolor="white",
                                markersize=5, linestyle="")
                    print(f"| {size} | {strike} | {g} | {band} | {_num(share.get('tier1'), 1, '.3f')} | "
                          f"{_num(share.get('physics'), 1, '.3f')} |")
            for bi in range(1, len(SC_BANDS)):
                ax.axvline(bi - 0.5, color=INK2, linewidth=0.6, alpha=0.4)
            ax.set_xticks(range(len(SC_BANDS)), [SC_BAND_LABEL[b] for b in SC_BANDS])
            ax.set_ylim(0, 102)
            style(ax, f"{size[0]} Guard v {size[-1]} Strike, {BEHAVIOUR_LABEL.get(strike, strike)} Strike",
                  "arena size band", "games with an over/under pass, %" if k == 0 else "")
    handles = [Line2D([], [], color=SERIES[i % len(SERIES)], marker="s", linestyle="", label=f"Guard: {g}")
               for i, g in enumerate(guards)]
    handles += [Line2D([], [], color=INK2, marker="s", linestyle="", label="bar: physics drone (Isaac Lab)"),
                Line2D([], [], color=INK, marker="o", markerfacecolor="white", linestyle="",
                       label="circle: tier 1 Starling layer")]
    fig.legend(handles=handles, loc="lower center", ncol=4, frameon=False, fontsize=9, labelcolor=INK)
    fig.suptitle("Guard and Strike drones passing one over the other (>= 0.84 m apart in height); observed in the "
                 "training simulator", x=0.01, ha="left", fontsize=13, color=INK)
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    fig.savefig(out)
    plt.close(fig)
    print(f"wrote {out}")


FIGURES = {"standin": standin, "standin_bars": standin_bars, "steps": steps, "real_replay": real_replay,
           "throughput": throughput, "scripted_compare": scripted_compare,
           "vertical_pass": vertical_pass}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) < 3 or argv[0] not in FIGURES:
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        return 2
    FIGURES[argv[0]](*argv[1:])
    return 0


if __name__ == "__main__":
    sys.exit(main())
