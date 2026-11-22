#!/usr/bin/env python
"""Figure of the L1 side track (records T58, T59): reaches of 1,000 against the Guard scripts, Wilson 95 % intervals,
read from the scoring runs' results.json (scripts/ste_score_matrix.py). Observed in the training simulator.

    make_ste_l1_side_figure.py [--figure l113|l114_l115|both] [--t52 <run>] [--arm-a <run>] [--arm-b <run>]
                               [--l111 <run>] [--out docs/figures/ste_l1_side/l113_arms.png]
                               [--t52-clamp <run>] [--arm-a-clamp <run>] [--l115-t55 <run>] [--l115-t54 <run>]
                               [--out2 docs/figures/ste_l1_side/l114_l115.png]

Panel 1 (L1.13, tag 1.15 m): T52, arm A and arm B against guard_field at the 30 s and the 120 s scoring clock, with the
best script (strike_straight) as a line and its interval as a band. Panel 2 (L1.11, tag 1.6 m): the L1.11 Strike team
against each of the 5 Guard scripts beside the best Strike script on the same starts. Second figure (records T60, T61):
L1.14, T52 and arm A at 120 s plain and with the time-left input clamped to at most 30 s (T52 at 30 s beside them);
L1.15, wins and median tag distance of T55, T54 and the script cell at response delay 0, 0.1482 and 0.30 s. Defaults:
the run folders of 22 Nov 2026 under runs/."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs"
DEFAULTS = {"t52": RUNS / "2026-11-22_ste_l113_t52_rescore", "arm_a": RUNS / "2026-11-22_ste_l113_arm_a_rescore",
            "arm_b": RUNS / "2026-11-22_ste_l113_arm_b_rescore", "l111": RUNS / "2026-11-22_ste_l111_score",
            "t52_clamp": RUNS / "2026-11-22_ste_l114_t52_clamp", "arm_a_clamp": RUNS / "2026-11-22_ste_l114_arm_a_clamp",
            "l115_t55": RUNS / "2026-11-22_ste_l115_t55", "l115_t54": RUNS / "2026-11-22_ste_l115_t54"}
DELAYS = (("tag_1p15_delay0", 0.0), ("tag_1p15_120s", 0.1482), ("tag_1p15_delay0p30", 0.30))
KEEP_OUT_M = 1.10                  # the safety filter's keep-out distance
CLOCKS = (("tag_1p15_30s", "30 s clock"), ("tag_1p15_120s", "120 s clock"))
TEAMS = (("t52", "T52 (comparator)"), ("arm_a", "arm A (30 s training clock)"), ("arm_b", "arm B (discount 0.997)"))
GUARDS = ("guard_mark_edge", "guard_mirror", "guard_field", "guard_parked_centre", "guard_parked_ring")
# Okabe-Ito blue and vermillion for the two arms (checked with the dataviz palette checker: CVD and normal-vision separation
# pass); a neutral grey for the comparator and the scripts, which are references, not series.
COLOUR = {"t52": "#8c8c8c", "arm_a": "#0072B2", "arm_b": "#D55E00", "l111": "#0072B2", "script": "#8c8c8c"}
INK, MUTED, GRID = "#1a1a1a", "#555555", "#e0e0e0"


def rows(run: Path, game: str) -> dict:
    """{opponent: row} of one scoring game in a score-matrix run's results.json (k, n, ci, best_script)."""
    res = json.loads((run / "results.json").read_text())
    if not res.get("complete") or not res.get("controls_pass"):
        raise SystemExit(f"{run}: results.json not complete or a control not PASS: no number is drawn")
    return {r["opponent"]: r for r in res["games"][game]["rows"]}


def cell(row: dict) -> tuple[int, float, float]:
    """(reaches, Wilson low, Wilson high) of a row or of its best_script entry, as counts of 1,000."""
    n = int(row["n"])
    return int(row["k"]), row["ci"][0] * n, row["ci"][1] * n


def panel_data(runs: dict) -> dict:
    l113 = {clock: {team: cell(rows(runs[team], clock)["guard_field"]) for team, _ in TEAMS} for clock, _ in CLOCKS}
    script = {clock: cell(rows(runs["t52"], clock)["guard_field"]["best_script"]) for clock, _ in CLOCKS}
    l111_rows = rows(runs["l111"], "base_120s")
    l111 = {g: {"team": cell(l111_rows[g]), "script": cell(l111_rows[g]["best_script"]),
                "script_name": l111_rows[g]["best_script"]["name"]} for g in GUARDS}
    return {"l113": l113, "script": script, "l111": l111}


def _bar(ax, x, value, colour, width):
    k, lo, hi = value
    ax.bar(x, k, width, color=colour, edgecolor="white", linewidth=2)
    ax.errorbar(x, k, yerr=[[k - lo], [hi - k]], fmt="none", ecolor=INK, elinewidth=1.2, capsize=3)
    ax.text(x, hi + 12, str(k), ha="center", va="bottom", fontsize=8, color=INK)


def _style(ax):
    ax.grid(axis="y", color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.tick_params(colors=MUTED)


def draw(data: dict, out: Path) -> None:
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 4.6), gridspec_kw={"width_ratios": [1, 1.4]})
    width = 0.26
    for i, (clock, clock_label) in enumerate(CLOCKS):
        for j, (team, label) in enumerate(TEAMS):
            _bar(a1, i + (j - 1) * width, data["l113"][clock][team], COLOUR[team], width)
        k, lo, hi = data["script"][clock]
        a1.fill_between([i - 1.6 * width, i + 1.6 * width], lo, hi, color=COLOUR["script"], alpha=0.18, lw=0)
        a1.plot([i - 1.6 * width, i + 1.6 * width], [k, k], color=INK, lw=1.2, ls=":")
    a1.text(1 + 1.6 * width, data["script"]["tag_1p15_120s"][0] + 8, "best script\n(strike_straight)", ha="right",
            va="bottom", fontsize=8, color=INK)
    a1.set_xticks(range(len(CLOCKS)), [lbl for _, lbl in CLOCKS], color=INK)
    a1.set_ylim(0, 450)
    a1.set_ylabel("reaches of 1,000 against guard_field", color=MUTED)
    a1.set_title("L1.13, tag 1.15 m: Strike teams v guard_field", color=INK, fontsize=10, loc="left")
    handles = [plt.Rectangle((0, 0), 1, 1, color=COLOUR[t]) for t, _ in TEAMS]
    a1.legend(handles, [lbl for _, lbl in TEAMS], fontsize=8, frameon=False, loc="upper left")
    _style(a1)

    width = 0.38
    for i, g in enumerate(GUARDS):
        _bar(a2, i - width / 2, data["l111"][g]["team"], COLOUR["l111"], width)
        _bar(a2, i + width / 2, data["l111"][g]["script"], COLOUR["script"], width)
        a2.text(i + width / 2, -18, data["l111"][g]["script_name"].replace("strike_", ""), ha="center", va="top",
                fontsize=7, color=MUTED)
    a2.set_xticks(range(len(GUARDS)), [g.replace("guard_", "") for g in GUARDS], color=INK)
    a2.tick_params(axis="x", pad=14)
    a2.set_ylim(0, 700)
    a2.set_ylabel("reaches of 1,000", color=MUTED)
    a2.set_title("L1.11, tag 1.6 m: Strike team trained v field, against each Guard script", color=INK, fontsize=10,
                 loc="left")
    a2.legend([plt.Rectangle((0, 0), 1, 1, color=COLOUR["l111"]), plt.Rectangle((0, 0), 1, 1, color=COLOUR["script"])],
              ["L1.11 Strike team", "best Strike script, same starts (name under the bar)"], fontsize=8, frameon=False,
              loc="upper left")
    _style(a2)
    fig.suptitle("STE L1 side track (training simulator, tier 1; one seed per team; T44's 1,000 starts)", fontsize=11,
                 color=INK, x=0.01, ha="left")
    fig.text(0.01, 0.005, "Bars: reaches of 1,000; whiskers: Wilson 95 %. Left: main reads arm A at 30 s, arm B at 120 s; "
             "arm A at 120 s plays outside its training clock.", fontsize=8, color=MUTED)
    fig.tight_layout(rect=(0, 0.03, 1, 0.95))
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150)
    plt.close(fig)


def delay_data(runs: dict) -> dict:
    """L1.14 and L1.15 numbers: (count, Wilson low, high) as counts of 1,000; median tag distances (m)."""
    t52 = {"plain 120 s": cell(rows(runs["t52"], "tag_1p15_120s")["guard_field"]),
           "clamped 120 s": cell(rows(runs["t52_clamp"], "tag_1p15_120s")["guard_field"]),
           "30 s game": cell(rows(runs["t52"], "tag_1p15_30s")["guard_field"])}
    arm_a = {"plain 120 s": cell(rows(runs["arm_a"], "tag_1p15_120s")["guard_field"]),
             "clamped 120 s": cell(rows(runs["arm_a_clamp"], "tag_1p15_120s")["guard_field"]),
             "30 s game": cell(rows(runs["arm_a"], "tag_1p15_30s")["guard_field"])}
    wins, tag = {"T55": [], "T54": [], "script": []}, {"T55": [], "T54": [], "script": []}
    for game, _ in DELAYS:
        r55 = rows(runs["l115_t55"], game)["guard_field"]
        r54 = rows(runs["l115_t54"], game)["strike_straight"]
        sc = next(c for c in r55["script_cells"] if c["cell"] == ["guard_field", "strike_straight"])
        for key, r in (("T55", r55), ("T54", r54), ("script", sc)):
            wins[key].append(cell(r))
            tag[key].append(float(r["tag_stats"]["tag_distance_median_m"]))
    return {"t52": t52, "arm_a": arm_a, "script": cell(rows(runs["t52"], "tag_1p15_120s")["guard_field"]["best_script"]),
            "wins": wins, "tag": tag}


def draw_delay(data: dict, out: Path) -> None:
    fig, (a1, a2, a3) = plt.subplots(1, 3, figsize=(14, 4.6), gridspec_kw={"width_ratios": [1.3, 1, 1]})
    width = 0.26
    shades = {"plain 120 s": "#8c8c8c", "clamped 120 s": "#0072B2", "30 s game": "#D55E00"}
    for i, team in enumerate(("t52", "arm_a")):
        for j, (label, colour) in enumerate(shades.items()):
            _bar(a1, i + (j - 1) * width, data[team][label], colour, width)
    k, lo, hi = data["script"]
    a1.axhspan(lo, hi, color=COLOUR["script"], alpha=0.18, lw=0)
    a1.axhline(k, color=INK, lw=1.2, ls=":")
    a1.text(1.45, k + 8, "best script (strike_straight)", ha="right", va="bottom", fontsize=8, color=INK)
    a1.set_xticks([0, 1], ["T52", "arm A"], color=INK)
    a1.set_ylim(0, 520)
    a1.set_ylabel("reaches of 1,000 against guard_field", color=MUTED)
    a1.set_title("L1.14: time-left input clamped to at most 30 s", color=INK, fontsize=10, loc="left")
    a1.legend([plt.Rectangle((0, 0), 1, 1, color=c) for c in shades.values()],
              ["120 s game, plain", "120 s game, time-left clamped", "30 s game"], fontsize=8, frameon=False,
              loc="upper left")
    _style(a1)

    xs = [d for _, d in DELAYS]
    styles = {"T55": ("#0072B2", "o", "T55 Strike v guard_field, reaches"),
              "T54": ("#D55E00", "s", "T54 Guard v strike_straight, holds"),
              "script": ("#8c8c8c", "^", "script field v straight, reaches")}
    for key, (colour, marker, label) in styles.items():
        ks = [w[0] for w in data["wins"][key]]
        err = [[w[0] - w[1] for w in data["wins"][key]], [w[2] - w[0] for w in data["wins"][key]]]
        a2.errorbar(xs, ks, yerr=err, color=colour, marker=marker, ms=8, mec="white", mew=2, lw=2, capsize=3,
                    label=label)
        a3.plot(xs, data["tag"][key], color=colour, marker=marker, ms=8, mec="white", mew=2, lw=2, label=label)
    a2.set_ylim(0, 900)
    a2.set_ylabel("wins of 1,000", color=MUTED)
    a2.set_title("L1.15: wins by response delay", color=INK, fontsize=10, loc="left")
    a2.legend(fontsize=8, frameon=False, loc="upper left")
    a3.axhline(KEEP_OUT_M, color=INK, lw=1.2, ls=":")
    a3.text(xs[0], KEEP_OUT_M + 0.001, "filter keep-out 1.10 m", fontsize=8, color=INK, va="bottom")
    a3.set_ylim(1.095, 1.155)
    a3.set_ylabel("median tag distance (m)", color=MUTED)
    a3.set_title("L1.15: median tag distance, same markers", color=INK, fontsize=10, loc="left")
    for ax in (a2, a3):
        ax.set_xticks(xs, ["0 s", "0.148 s\n(fitted)", "0.30 s"], color=INK)
        ax.set_xlabel("response delay, command to motion", color=MUTED)
        _style(ax)
    fig.suptitle("STE L1.14 and L1.15, tag 1.15 m (training simulator, tier 1; one network per team; T44's 1,000 "
                 "starts)", fontsize=11, color=INK, x=0.01, ha="left")
    fig.text(0.01, 0.005, "Whiskers: Wilson 95 %. 0 s and 0.30 s are study-only parameter files, not drone values.",
             fontsize=8, color=MUTED)
    fig.tight_layout(rect=(0, 0.03, 1, 0.95))
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150)
    plt.close(fig)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--t52", type=Path, default=DEFAULTS["t52"])
    ap.add_argument("--arm-a", type=Path, default=DEFAULTS["arm_a"])
    ap.add_argument("--arm-b", type=Path, default=DEFAULTS["arm_b"])
    ap.add_argument("--l111", type=Path, default=DEFAULTS["l111"])
    ap.add_argument("--out", type=Path, default=ROOT / "docs/figures/ste_l1_side/l113_arms.png")
    ap.add_argument("--t52-clamp", type=Path, default=DEFAULTS["t52_clamp"])
    ap.add_argument("--arm-a-clamp", type=Path, default=DEFAULTS["arm_a_clamp"])
    ap.add_argument("--l115-t55", type=Path, default=DEFAULTS["l115_t55"])
    ap.add_argument("--l115-t54", type=Path, default=DEFAULTS["l115_t54"])
    ap.add_argument("--out2", type=Path, default=ROOT / "docs/figures/ste_l1_side/l114_l115.png")
    ap.add_argument("--figure", choices=("l113", "l114_l115", "both"), default="both")
    a = ap.parse_args(argv)
    if a.figure in ("l113", "both"):
        draw(panel_data({"t52": a.t52, "arm_a": a.arm_a, "arm_b": a.arm_b, "l111": a.l111}), a.out)
        print(f"wrote {a.out}")
    if a.figure in ("l114_l115", "both"):
        draw_delay(delay_data({"t52": a.t52, "arm_a": a.arm_a, "t52_clamp": a.t52_clamp, "arm_a_clamp": a.arm_a_clamp,
                               "l115_t55": a.l115_t55, "l115_t54": a.l115_t54}), a.out2)
        print(f"wrote {a.out2}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
