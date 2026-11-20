#!/usr/bin/env python
"""Draft the record of an L0.11 Screening sweep run and its ledger row, from the run folder alone (records/README.md;
STANDARDS section 8; the sections of records/_template_record.md).

    make_ste_l011_record.py --run-dir runs/<date>_ste_l011_screen --number T<n> [--name <date>_ste_l011_screen]
                            [--out-dir records] [--append-ledger]

Writes ``<out-dir>/<name>_record.md`` (refuses to overwrite: a record is never edited after it is written) and prints
the ledger row. With --append-ledger the row is appended to ``records/LEDGER.md`` (the lead's step after reading the
record; W numbers on the 5090, renumbered at the merge). The verdict word is INFO when every control is PASS, and
ABORTED when the run did not finish or a control failed (the screen has no pass mark; the controls gate the reading).
GPU-hours: the run's own ledger lines in the shared folder (``ste/budget.py``), if the run was launched as a job.
Exit 0 written, 1 refused."""
from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))

from svg_training.ste import budget  # noqa: E402
from svg_training.ste.run_contract import EXIT_NAMES  # noqa: E402


def gpu_hours(run_dir: Path) -> tuple[str, float | None]:
    job_file = run_dir / "job.json"
    if not job_file.is_file():
        return "not launched as a job (no job.json): GPU-hours not logged", None
    job = json.loads(job_file.read_text())
    used = budget.job_gpu_h(job["task"], job["name"], job["run_dir"])
    return f"job {job['name']} (task {job['task']}), asked {job['gpu_h']} GPU-h, used {used:.3f} GPU-h (shared ledger)", used


def exit_word(run_dir: Path) -> str:
    path = run_dir / "exit_code"
    if not path.is_file():
        return "no exit_code file (not launched through scripts/ste_job.py, or still running)"
    code = int(path.read_text().strip())
    return f"{code} ({EXIT_NAMES.get(code, 'other')})"


def record_text(run_dir: Path, result: dict, name: str, number: str) -> tuple[str, str]:
    meta = result["meta"]
    code = (run_dir / "exit_code").read_text().strip() if (run_dir / "exit_code").is_file() else None
    finished = not result.get("stopped") and code == "0"          # QC M-4: INFO needs a recorded exit code 0
    readable = result["controls_all_pass"] and finished              # QC I4: otherwise no shortlist numbers anywhere
    why = "; ".join(
        ([f"control(s) {', '.join(k for k, v in result['controls'].items() if v['status'] != 'PASS')} not PASS"]
         if not result["controls_all_pass"] else [])
        + ([f"the run stopped ({result['stopped']})"] if result.get("stopped") else [])
        + (["no exit_code (not launched through scripts/ste_job.py, or still running)"] if code is None else
           [f"exit {code}"] if code != "0" else []))
    verdict = "INFO (no gates on the screen; every control PASS)" if readable else f"ABORTED ({why})"
    hours_text, hours = gpu_hours(run_dir)
    sl = result["shortlist"]
    batches = result["batches"]
    games = sum(b["games"] * b["steps_played"] for b in batches)
    seconds = sum(b["seconds"] for b in batches) or float("nan")
    sizes = sorted({b["size"] for b in batches})
    if readable:
        shortlist_lines = [
            "## Shortlist for L0.12 (rule: gate file [shortlist])", "",
                 f"**{', '.join(sl['shortlist']) or 'no eligible variant'}**; without the z_up_info columns: "
                 f"{', '.join(result['shortlist_without_z_up']['shortlist']) or 'none'}. The lead picks the shortlist and "
                 f"records why before L0.12 (PLAN.md row L0.11).", "",
                 "The base case is always carried as the reference for the proposed 1.6 m rules (LEAD CALL 21 Nov 2026); "
                 "the rule adds at most two more.", "",
                 "| Variant | H | g* | R | s* | d | |", "|---|---|---|---|---|---|---|",
                 *[f"| {v['variant']} | {v['H'] if v['H'] is None else round(v['H'], 3)} | {v['g_star']} | "
                   f"{v['R'] if v['R'] is None else round(v['R'], 3)} | {v['s_star']} | "
                   f"{v['d'] if v['d'] is None else round(v['d'], 3)} | {v['reason']} |" for v in sl["variants"] + sl["report_only"]],
            *[f"| {v['label']} (INFO; {v['variant']}) | {v['H'] if v['H'] is None else round(v['H'], 3)} | {v['g_star']} | "
              f"{v['R'] if v['R'] is None else round(v['R'], 3)} | {v['s_star']} | "
              f"{v['d'] if v['d'] is None else round(v['d'], 3)} | INFO reference, never shortlisted (P1 is the owner's at "
              f"G0) |" for v in sl.get("info_reference", [])]
        ]
    else:
        shortlist_lines = ["## Shortlist for L0.12", "",
                           f"Not read: {why}. An ABORTED record carries only what ran and why: no shortlist, H, R or d."]
    lines = [f"Simulator: {meta['simulator']}. Observed in the training simulator; not a flight result.", "",
             f"# {name} record", "",
             "## Run notes", "",
             "- **Never suspend the machine during a GPU job** (no closed lid, no sleep): the cap clock and the GPU-hour "
             "ledger are wall clock less the owner's gpu_pause.sh pauses only, so a suspend counts in full against the cap "
             "and is billed as GPU-hours (tooling task L07-SUSPEND). Say here whether the machine was suspended during the "
             "run.",
             "- **Finding L011-F1**: the scripted players decide every tick (0.05 s), not at the sheet's 0.6 s decision "
             "period (timing.decision_s). This sweep measures scripted play at 0.05 s. L0.12's trainers must fix their "
             "decision period explicitly (T41's recipe used 12 ticks = 0.6 s).", "",
             "## Purpose", "",
             "STE task L0.11 Screening sweep (INFO, PLAN.md section 4): scripted Guards against scripted Strikes, the base "
             "case (3v3, tag 1.6 m, zone 1.6 m, Guard survives 0, 6.5 m lab arena) and one factor changed at a time; it "
             "shortlists at most 3 rule variants for L0.12 by the rule written in the gate file before the run.", "",
             "## Commit", "", f"`{meta['commit']}`{' (working tree not clean)' if meta['dirty'] else ''}", "",
             "## Config", "",
             f"- Gate file `{meta['gates_file']}`, sha256 `{meta['gates_sha256']}` (copy in the run folder: `gates.toml`).",
             *[f"- Game `{k}`: `{v['file']}`, sha256 `{v['sha256']}`." for k, v in meta["games"].items()],
             f"- {meta['games_per_cell']} games per cell, {meta['cells_per_batch']} cells per batch, at most "
             f"{meta['ticks_cap']} ticks per game; device {meta['device']}.", "",
             "- Closest 3-D approach (results.md): among drones still in the game after the tag step (a pair tagged on "
             "a step is out before the distance is taken: core/game.py; QC M-3).", "",
             "## Model parameter set", "",
             "Tier 1 Starling layer: `params/real_exploratory_v0.toml` (fitted PX4 response, exploratory); safety filter on "
             "every pair, 1000 sweeps, check every 8.", "",
             "## Seeds", "", f"Game seed {meta['seed']} for every batch (paired starts: one draw of "
             f"{meta['games_per_cell']} games tiled over the cells); Guard players seed + 101, Strike players seed + 202.", "",
             "## Machine", "", f"{meta['host']}; GPU {meta['gpu'] or 'none (CPU)'}; torch {meta['torch']}; Python "
             f"{meta['python']}. Exit code {exit_word(run_dir)}. Effective time {meta['effective_s']:.0f} s of a "
             f"{meta['cap_h']} h cap. {hours_text}.", "",
             "## Games at once", "", f"{meta['games_per_cell']} x up to {meta['cells_per_batch']} cells per batch; "
             f"{len(batches)} batches played; sizes {', '.join(sizes)}.", "",
             "## Steps per second", "",
             f"{games / seconds:,.0f} game-steps per second over all batches ({games:,} game-steps in {seconds:.0f} s, "
             f"tier 1, {meta['gpu'] or 'CPU'}); per batch, with games and drones per game, in `results.md` (Batches).", "",
             "## Gates", "", f"Verdict: **{verdict}**.", "",
             "The screen is INFO: no pass mark. The controls, written in the gate file before the run, gate the reading:", "",
             "| Control | Status | Detail |", "|---|---|---|",
             *[f"| {k} | {v['status']} | {v['detail']} |" for k, v in result["controls"].items()], "",
             f"Cut by the projection: {', '.join(result['cut']) or 'none'}.", "",
             *shortlist_lines,
             "", "## Figures and videos", "",
             "Figures from the run's own results.json by `scripts/make_ste_l011_figures.py`: `figures/`. Clips "
             "(STANDARDS section 8): " + ("; ".join(result.get("clips", [])) or "none recorded (say why here)") + ".", "",
             "## Confounds stated before the run", "",
             *[f"- {k}: {v}" for k, v in meta["confounds"].items() if isinstance(v, str)], ""]
    head = ", ".join(f"{v['variant']} H {v['H']:.2f} R {v['R']:.2f}" for v in sl["variants"] if v["H"] is not None)
    played = f"{sum(len(g['rows']) for g in result['groups'])} cells played"
    what = (f"{played} x {meta['games_per_cell']} games; shortlist {', '.join(sl['shortlist']) or 'none'}; {head}"
            if readable else f"{played}; not read: {why}")
    hours_cell = f"; {hours:.3f} GPU-h" if hours is not None else ""
    row = (f"| {number} | {datetime.datetime.now().astimezone().isoformat(timespec='seconds')} | {meta['simulator']}; "
           f"{meta['gpu'] or 'CPU'} | {name} | STE L0.11 Screening sweep: {what}{hours_cell} | {verdict.split(' ')[0]} | "
           f"records/{name}_record.md |")
    return "\n".join(lines), row


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--run-dir", type=Path, required=True)
    ap.add_argument("--number", required=True, help="the ledger number: T<n> (or W<n> on the workstation)")
    ap.add_argument("--name", help="record name (default: the run folder's name)")
    ap.add_argument("--out-dir", type=Path, default=ROOT / "records")
    ap.add_argument("--ledger", type=Path, default=ROOT / "records" / "LEDGER.md")
    ap.add_argument("--append-ledger", action="store_true")
    a = ap.parse_args(argv)
    results = a.run_dir / "results.json"
    if not results.is_file():
        print(f"refused: {results} does not exist", file=sys.stderr)
        return 1
    name = a.name or a.run_dir.name
    out = a.out_dir / f"{name}_record.md"
    if out.exists():
        print(f"refused: {out} exists (a record is never overwritten)", file=sys.stderr)
        return 1
    text, row = record_text(a.run_dir, json.loads(results.read_text()), name, a.number)
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
