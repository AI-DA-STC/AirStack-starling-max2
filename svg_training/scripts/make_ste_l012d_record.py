#!/usr/bin/env python
"""Write the record of STE task L0.12d Cross-tag check (INFO) from its run folder, and its ledger row
(records/README.md; the record sections of records/_template_record.md).

    make_ste_l012d_record.py --run-dir runs/<date>_ste_l012d_cross_tag --number T<n>
                             [--name <date>_ste_l012d_cross_tag] [--out-dir records] [--append-ledger]

Refuses (exit 1) unless the run folder's results.json is complete and its controls C1, C2 and C3 all PASS (the driver
reports no cross-tag number otherwise), and never overwrites a record. The word is INFO: no pass/fail gate, no
category. The reading words are the spec's (ste_learning/drafts/L0_12d_CROSS_TAG_SPEC.md), written before any scoring.
Prints the ledger row; --append-ledger appends it to records/LEDGER.md (the lead's step after reading the record)."""
from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
sys.path.insert(0, str(ROOT / "scripts"))

import make_ste_l011_record as l011rec  # noqa: E402  (GPU-hours and exit words)
from make_ste_l012_record import num  # noqa: E402

CONTROLS = ("C1", "C2", "C3", "C4")
CONTROL_WHAT = {"C1": "T46's base Guard evaluation batch replayed whole (base game): equal to its eval_final.npz game "
                      "for game, trained Guard holds as recorded",
                "C2": "T46's base Strike evaluation batch replayed whole (base game): equal to its eval_final.npz game "
                      "for game, trained Strike reaches as recorded",
                "C3": "every script cell of the 1.15 m batch equal to the L0.12b screen reference game for game, "
                      "g* v s* holds as the screen",
                "C4": "every script cell of X4's own base-game batch equal to T44's reference game for game, "
                      "guard_field v strike_straight holds as T44 (716)"}
X_WHAT = {"X1": "T46 base trained Guard team v s* at 1.15 m", "X2": "g* at 1.15 m v T46 base trained Strike team",
          "X3": "the base g* (the opponent it trained against) v T46 base trained Strike team (INFO)",
          "X4": "guard_field v T46 base trained Strike team in the base game (tag 1.6 m); the T46 Strike team never "
                "trained against guard_field (INFO)"}


def ci(x: dict) -> str:
    return f"{x['k']:,} of {x['n']:,} ({num(x['ci'][0], '{:.3f}')}–{num(x['ci'][1], '{:.3f}')})"


def clip_starts(res: dict) -> str:
    return (f"Clips: the clip seed's own starts (clip_seed {res['clip_seed']}), CPU, not the {res['eval_games']:,} "
            f"scoring starts")


def record_text(run_dir: Path, res: dict, name: str, number: str) -> tuple[str, str]:
    cells, c = res["cells"], res["controls"]
    pins, cmp_ = res["pins"], res["compare"]
    hours, used = l011rec.gpu_hours(run_dir)
    lines = [f"Simulator: {res['simulator']}. Observed in the training simulator; not a flight result.", "",
             f"# {name} record", "", "## Purpose", "",
             "STE task L0.12d Cross-tag check (INFO; spec ste_learning/drafts/L0_12d_CROSS_TAG_SPEC.md, written by the "
             "lead before any scoring): how well do the strategies trained at tag 1.6 m (T46, base variant) play when "
             "the tag is 1.15 m (the safety filter's 1.10 m keep-out + 0.05 m)? Scoring only, no training, on T44's "
             "1,000 scoring starts. Feeds G0 row 1 (tag distance). X4 (guard_field at 1.6 m) separates the opponent from "
             "the tag: with C2, X2 and X3 it completes tag x opponent.", "",
             "## Commit", "", f"`{res['code']['first']['commit']}` (diff sha256 {res['code']['first']['diff_sha256'][:12]})",
             "", "## Config", "",
             f"- Settings `configs/ste_l012d/cross_tag.toml`, sha256 `{res['settings_sha256']}` (copy in the run folder).",
             f"- T46 runs (read only, `{res['t46_runs_dir']}`): Guard `{pins['t46']['guard_run']}` (agent_final.pt "
             f"`{pins['t46']['guard_agent_sha256']}`), Strike `{pins['t46']['strike_run']}` (agent_final.pt "
             f"`{pins['t46']['strike_agent_sha256']}`); their gate file `{pins['t46']['gates_sha256']}`.",
             f"- Games: controls C1, C2 `{res['games']['controls']['file']}` (`{res['games']['controls']['sha256']}`); "
             f"cross-tag cells and C3 `{res['games']['x']['file']}` (`{res['games']['x']['sha256']}`).",
             f"- L0.12b gate file `{pins['screen']['gates']}` (`{pins['screen']['gates_sha256']}`); references "
             f"`{res['references']['t46']['file']}` (`{res['references']['t46']['sha256']}`) and "
             f"`{res['references']['screen']['file']}` (`{res['references']['screen']['sha256']}`), one start set "
             f"`{res['references']['start_sha256']}`.",
             f"- Trained players held {res['networks']['guard']['decision_ticks']} ticks (0.6 s) as trained, mean "
             f"actions; {res['eval_games']:,} games per cell; {res['ticks_cap']} ticks (the game length).", "",
             "## Model parameter set", "",
             f"Tier 1 Starling layer: `{res['parameter_set']['file']}` (fitted PX4 response, exploratory), sha256 "
             f"`{res['parameter_set']['sha256']}`; safety filter on {res['parameter_set']['filter']}.", "",
             "## Seeds", "", f"Scoring starts T44's (seed {res['references']['seed']}, loaded); scripted players seed + 101 "
                              f"(Guard) / + 202 (Strike); one training seed per side (T46's); no training here. "
                              f"{clip_starts(res)}.", "",
             "## Machine", "", f"{res['machine']['host']}, {res['machine']['gpu']}, torch {res['machine']['torch']}, "
                               f"device {res['device']}; exit {l011rec.exit_word(run_dir)}; effective "
                               f"{res['effective_s']:.0f} s of {res['cap_h']} h; {hours}", "",
             "## Games at once and steps per second", "",
             "; ".join(f"{k} batch {num(v, '{:.1f}')} s" for k, v in res["batch_seconds"].items())
             + " (tier 1, 6 drones per game).", "",
             "## Gates", "", "Verdict: **INFO** (no pass/fail gate; the controls are gated: any control not PASS and no "
                             "cross-tag number is reported).", "", "| Control | What | Status |", "|---|---|---|"]
    lines += [f"| {k} | {CONTROL_WHAT[k]} | **{c[k]['status']}** |" for k in CONTROLS]
    lines += ["", f"Closest-approach tolerance {res['closest_tol']['tol_m']} m ({res['closest_tol']['rule']}; "
              f"`{res['closest_tol']['source']}`, sha256 `{res['closest_tol']['sha256']}`)."]
    lines += ["", "| Cell | What | Trained side's wins (Wilson 95 %) | Script cell, same starts | Paired: trained only / "
              "script only | Trained at 1.15 m | Guards left in holds | Length median (s) | Pushed together (share) | "
              "Filter active (share) |", "|---|---|---|---|---|---|---|---|---|---|"]
    for key, x in cells.items():
        ts, p = x["tag_shares"], x.get("paired") or {}
        script = f"{' v '.join(x['script']['cell'])}: {ci(x['script'])}" if "script" in x else "-"
        trained = ci(x["trained_at_1p15"]) if "trained_at_1p15" in x else "-"
        lines.append(f"| {key} | {X_WHAT[key]}; game {x['game']} | {ci(x)} | {script} | {p.get('trained_only', '-')} / "
                     f"{p.get('script_only', '-')} | {trained} | {num(x['guards_left_mean_in_holds'], '{:.3f}')} | "
                     f"{num(x['length_median_s'])} | {ts.get('tags_pushed', '-')} "
                     f"({num(ts.get('pushed_tag_share'), '{:.3f}')}) | {ts.get('tags_filtered', '-')} "
                     f"({num(ts.get('filter_active_share'), '{:.3f}')}) |")
    lines += ["", f"Trained at 1.15 m: {cmp_['trained_source']}.", "", "## Figures and videos", "",
              f"{clip_starts(res)}.", ""]
    clips = res.get("clips") or {}
    if "missing" in clips:
        lines.append(f"- no clips: {clips['missing']}")
    for key, clip in clips.items():
        if key != "missing":
            lines += [f"- {key}: {f}" for f in clip["files"]] + ([f"- {key}: {clip['note']}"] if clip.get("note") else [])
    if not clips:
        lines.append("- no clips in this run folder")
    lines += ["", "## Reading", ""]
    lines += [f"- {key} ({X_WHAT[key]}): {x['reading']}." for key, x in cells.items()]
    lines += [f"- {res['limits'].capitalize()}.", ""]
    what = "; ".join(f"{k} {x['k']}/{x['n']}" + (f" (1.15 m-trained {x['trained_at_1p15']['k']}, script "
                                                    f"{x['script']['k']})" if "trained_at_1p15" in x else
                                                    f" (script {x['script']['k']})" if "script" in x else "")
                     for k, x in cells.items())
    row = (f"| {number} | {first_launch(run_dir)} | {res['simulator']}; {res['machine']['gpu']} | {name} | STE L0.12d "
           f"Cross-tag check (1.6 m-trained T46 base players at tag 1.15 m; X4 = guard_field at 1.6 m): {what}; controls "
           f"C1–C4 PASS"
           f"{f'; {used:.3f} GPU-h' if used is not None else ''} | INFO | records/{name}_record.md |")
    lines += ["## Ledger row", "", "Ledger row: " + row, ""]
    return "\n".join(lines), row


def first_launch(run_dir: Path) -> str:
    f = run_dir / "launches.jsonl"
    times = [e["time"] for e in map(json.loads, filter(str.strip, f.read_text().splitlines()))
             if e.get("event") == "launch"] if f.is_file() else []
    t = datetime.datetime.fromtimestamp(min(times)) if times else datetime.datetime.now()
    return t.astimezone().isoformat(timespec="seconds")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--run-dir", type=Path, required=True)
    ap.add_argument("--number", required=True, help="the ledger number (T56)")
    ap.add_argument("--name")
    ap.add_argument("--out-dir", type=Path, default=ROOT / "records")
    ap.add_argument("--ledger", type=Path, default=ROOT / "records" / "LEDGER.md")
    ap.add_argument("--append-ledger", action="store_true")
    a = ap.parse_args(argv)
    f = a.run_dir / "results.json"
    if not f.is_file():
        print(f"refused: {f} does not exist (no record without complete results)", file=sys.stderr)
        return 1
    res = json.loads(f.read_text())
    statuses = {k: (res.get("controls") or {}).get(k, {}).get("status") for k in CONTROLS}
    if res.get("complete") is not True or res.get("controls_pass") is not True or set(statuses.values()) != {"PASS"}:
        print(f"refused: results.json is not complete with every control PASS ({statuses})", file=sys.stderr)
        return 1
    name = a.name or a.run_dir.name
    out = a.out_dir / f"{name}_record.md"
    if out.exists():
        print(f"refused: {out} exists (a record is never overwritten)", file=sys.stderr)
        return 1
    text, row = record_text(a.run_dir, res, name, a.number)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text)
    print(f"wrote {out}")
    print(row)
    if a.append_ledger:
        with open(a.ledger, "a") as ledger:
            ledger.write(row + "\n")
        print(f"appended the row to {a.ledger}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
