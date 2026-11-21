#!/usr/bin/env python
"""Draft the record of the L0.12 Best-response test from its verdict and run folders (records/README.md; STANDARDS
section 8; the sections of T44's record, records/2026-11-21_ste_l011_screen_record.md).

    make_ste_l012_record.py --verdict <folder>/verdict.json --out records/<date>_ste_l012_best_response_record.md
                            [--name <date>_ste_l012_best_response] [--number T<n>] [--pilot <pilot run>/pilot.json]
    make_ste_l012_record.py --aborted --runs <run>,<run>,... --out records/<...>_record.md [--name ...] [--number ...]

Refuses to overwrite (a record is never edited after it is written; additions go under "Run notes added by the lead").
With --verdict the word is INFO: ``verdict`` only accepts runs whose controls all passed (QC C-1), and this writer
refuses a verdict.json whose ``controls_pass`` is false. The record and its ledger row carry every side's status, gain,
Guards left in holds and game length next to the variant category (QC I-8: the category alone is set by T44's scripts).
With --aborted it writes an ABORTED record from the run folders alone: for each run what ran (phase, updates, game-steps)
and why it ended (controls not PASS, exit code, no complete results), with NO gain, status or category. GPU-hours: each
run's own ledger lines in the shared folder, if launched as a job. Prints the ledger row. Exit 0 written, 1 refused."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
sys.path.insert(0, str(ROOT / "scripts"))

import make_ste_l011_record as l011rec  # noqa: E402  (GPU-hours and exit words: the L0.11 writer's helpers)

RUN_NOTES = ("- **Never suspend the machine during a GPU job** (no closed lid, no sleep): the cap clock and the GPU-hour "
             "ledger are wall clock less the owner's gpu_pause.sh pauses only (tooling task L07-SUSPEND). Say here "
             "whether the machine was suspended during the runs.",
             "- **Asymmetries stated before the runs** (gate file header): one training seed per side; the learner decides "
             "every 0.6 s while the scripts decide every 0.05 s (finding L011-F1); one network per drone; about 1 GPU-h "
             "per run. A gain is evidence; no gain is weak evidence.",
             "- **Decision-boundary restart** (LEAD CALL 21 Nov 2026): a game that ends inside a 0.6 s decision restarts "
             "at the next decision boundary; the ticks after its end are played, counted (stale-tick share) and never "
             "trained on (T41's hold let the new game play the old held action).",
             "- **Strike recipe** (LEAD CALL 21 Nov 2026, pre-registered in [trainer] strike_fallback): the T41 recipe "
             "if its pilot probe against g* shows at least one reach; else the shaped Strike recipe (the game's distance "
             "shaping 1.0, training reward only) if its probe against g* does; else the Strike runs are not launched "
             "and the Strike side is INCONCLUSIVE. The parked-Guard probes are information only. The recipe of each run is in the tables below.",
             "- **Resume** (by design): networks, optimisers, scalers, counters and the torch random state are restored at "
             "the last update boundary, but the training games restart from the run seed's first starts (the game "
             "generator is not checkpointed), so a resumed run is not identical to an uninterrupted run. Each run's job "
             "launches say whether it was resumed.")


def ci(d: dict | None) -> str:
    if not d or not d.get("n"):
        return "n/a"
    return f"{d['k']}/{d['n']} = {d['rate']:.3f} ({d['ci'][0]:.3f}–{d['ci'][1]:.3f})"


Z_UP = ("strike_high", "strike_low")
Z_LABEL = "tier 1 vertical response not fitted (s2b.toml z_up_info)"


def lab(name: str) -> str:
    return f"{name} ({Z_LABEL})" if name in Z_UP else name


def record_text(verdict: dict, runs: dict, name: str, number: str | None) -> tuple[str, str]:
    word = "INFO (every control PASS; the categories feed gate G0)" if verdict["controls_pass"] else \
        "ABORTED (a control is not PASS: read controls.json of each run)"
    lines = [f"Simulator: {verdict['simulator']}. Observed in the training simulator; not a flight result.", "",
             f"# {name} record", "", "## Run notes", "", *RUN_NOTES, "", "## Purpose", "",
             "STE task L0.12 Best-response test (PLAN.md section 4): for each shortlisted variant of T44, an exploiter "
             "Strike team trained against the best scripted Guard g* and an exploiter Guard team trained against the "
             "best scripted Strike s*; the gain of each over the best script on T44's own starts, and the variant's "
             "category on the better of script and exploiter (LEAD CALL 21 Nov 2026).", "",
             "## Config", "", f"- Gate file sha256 `{verdict['gates_sha256']}` (copy in each run folder: `gates.toml`).",
             f"- Band {verdict['band']} (PROPOSED by the lead)."]
    first = next(iter(runs.values()))
    lines += [f"- Reference `{first['reference']['file']}`, sha256 `{first['reference']['sha256']}`; T44's starts sha256 "
              f"`{first['reference']['start_sha256']}`; T44 gate sha256 `{first['reference']['t44_gates_sha256']}`."]
    games = {r["game_file"]["file"]: r["game_file"]["sha256"] for r in runs.values()}
    lines += [f"- Game `{f}`, sha256 `{h}`." for f, h in games.items()]
    lines += [f"- {k}: trainer settings {r['settings']}" for k, r in runs.items()]
    lines += ["", "## Model parameter set", ""]
    sets = {(r["parameter_set"]["file"], r["parameter_set"]["sha256"], r["parameter_set"]["filter"]) for r in runs.values()}
    lines += [f"Tier 1 Starling layer: `{f}` (fitted PX4 response, exploratory), sha256 `{h}`; safety filter on {flt}."
              for f, h, flt in sorted(sets)]
    lines += ["", "## Commit", ""]
    for key, r in runs.items():
        lines.append(f"- {key}: `{r['code']['first']['commit']}` (diff sha256 {r['code']['first']['diff_sha256'][:12]})")
    lines += ["", "## Seeds", ""] + [f"- {k}: training seed {r['train_seed']}; scoring starts T44's (seed 110000, loaded)"
                                       for k, r in runs.items()]
    lines += ["", "## Machine", ""]
    for key, r in runs.items():
        hours, _ = l011rec.gpu_hours(Path(r["dir"]))
        lines.append(f"- {key}: {r['machine']['host']}, {r['machine']['gpu']}, torch {r['machine']['torch']}; exit "
                     f"{l011rec.exit_word(Path(r['dir']))}; effective {r['effective_s']:.0f} s of {r['cap_h']} h; {hours}")
    lines += ["", "## Games at once and steps per second", ""]
    lines += [f"- {k}: {r['num_games']} training games, 6 drones per game, tier 1, {r['machine']['gpu']}: median "
              f"{(r['game_steps_per_s_median'] or 0):,.0f} game-steps/s; {r['trained_updates']} updates, "
              f"{r['game_steps']:,} game-steps ({r['train_stop']}); evaluation {r['eval_games']} games per cell"
              for k, r in runs.items()]
    lines += ["", "## Gates", "", f"Verdict: **{word}**.", "", "| Variant | Role | Strike side | Guard side | Better Strike "
              "reach upper | Better Guard hold upper | Category |", "|---|---|---|---|---|---|---|"]
    for v, e in verdict["variants"].items():
        s, g = e["sides"].get("strike"), e["sides"].get("guard")
        lines.append(f"| {v} | {e['role']} | {s['status'] if s else '-'} | {g['status'] if g else '-'} | "
                     f"{e.get('strike_upper', float('nan')):.3f} | {e.get('guard_upper', float('nan')):.3f} | "
                     f"**{e['category']}** |")
    lines += ["", "| Variant | Side | Recipe | Trained exploiter | Untrained | Best script (cell) | Gain | Real | Paired "
              "(exploiter only / script only) | Guards left in holds (exploiter) | Length median (s) |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
    for v, e in verdict["variants"].items():
        for side, sr in e["sides"].items():
            comp = sr["exploiter_composition"] or {}
            paired = sr["paired"] or {}
            g = sr["gain"]["gain"]
            lines.append(f"| {v} | {side} | {sr.get('recipe') or '-'} | {ci(sr['gain']['trained'])} | "
                         f"{ci(sr['untrained'])} | {ci(sr['gain']['script'])} ({' v '.join(lab(c) for c in sr['script_cell'])})"
                         f" | {'-' if g is None else f'{g:+.3f}'} | {sr['gain']['real']} | "
                         f"{paired.get('exploiter_only', '-')} / {paired.get('script_only', '-')} | "
                         f"{comp.get('guards_left_mean_in_holds', '-')} | {comp.get('length_median_s', '-')} |")
    extras = [(k, o, e) for k, r in runs.items() for o, e in r.get("extra_opponents", {}).items()]
    if extras:
        lines += ["", "Evaluation-only opponents (INFO; script baseline from the T44 reference, same starts):", "",
                  "| Run | Opponent | Trained exploiter | Best script | Gain | Real |", "|---|---|---|---|---|---|"]
        lines += [f"| {k} | {e['label']} | {ci(e['exploiter'])} | {ci(e['script'])} | {e['gain']:+.3f} | {e['real']} |"
                  for k, o, e in extras]
    lines += ["", "## Figures and videos", ""]
    for key, r in runs.items():
        lines += [f"- {key}: {x}" for x in r.get("videos", [])]
    lines += ["", "## Reading", "", "(The lead writes the reading after QC; numbers come from the tables above.)", ""]
    parts = []
    for v, e in verdict["variants"].items():
        sides = []
        for side, sr in e["sides"].items():
            comp = sr.get("exploiter_composition") or {}
            g = sr["gain"]["gain"]
            sides.append(f"{v} {side.capitalize()}: {sr['status']}, gain {'-' if g is None else f'{g:+.3f}'}, Guards left "
                         f"{comp.get('guards_left_mean_in_holds', '-')}, {comp.get('length_median_s', '-')} s median")
        parts.append("; ".join(sides) + f" (category {e['category']}, set by T44's scripts)")
    row = (f"| {number or 'T?'} | {name} | L0.12 Best-response test | {word.split(' ')[0]} | " + " / ".join(parts) + " |")
    lines += ["## Ledger row", "", "Ledger row: " + row, ""]
    return "\n".join(lines) + "\n", row


def aborted_text(runs: dict, name: str, number: str | None) -> tuple[str, str]:
    """An ABORTED record from run folders alone: what ran and why, no gain, no status, no category (QC C-1)."""
    sim = ("training simulator, tier 1 (fast engine; Starling layer: commander copy, safety filter on every pair, "
           "fitted PX4 response, exploratory); study tag on (P1, PROPOSED)")
    lines = [f"Simulator: {sim}. Observed in the training simulator; not a flight result.", "", f"# {name} record", "",
             "## Gates", "", "Verdict: **ABORTED**. Nothing below is a result: no side status or category is read "
             "from a run whose controls did not all pass or that did not finish (gate [controls]).", "",
             "| Run | Variant / side | What ran | Why it ended |", "|---|---|---|---|"]
    whys = []
    for d, info in runs.items():
        lines.append(f"| {d} | {info['what']} | {info['ran']} | {info['why']} |")
        whys.append(f"{info['what']}: {info['why']}")
    lines += ["", "## Run notes", "", *RUN_NOTES, ""]
    row = f"| {number or 'T?'} | {name} | L0.12 Best-response test | ABORTED | " + "; ".join(whys) + " |"
    lines += ["## Ledger row", "", "Ledger row: " + row, ""]
    return "\n".join(lines) + "\n", row


def run_summary(d: Path) -> dict:
    """What a run folder shows: its variant and side, what ran, and why it ended (never a result)."""
    meta = json.loads((d / "run.json").read_text()) if (d / "run.json").is_file() else {}
    what = f"{meta.get('variant', '?')} / {meta.get('side', '?')}"
    log = (d / "train_log.jsonl").read_text().splitlines() if (d / "train_log.jsonl").is_file() else []
    updates = {json.loads(x)["update"] for x in log}
    steps = json.loads(log[-1])["game_steps_total"] if log else 0
    ran = (f"controls batch {'played' if (d / 'eval_before.npz').is_file() else 'not finished'}; {len(updates)} "
           f"training updates, {steps:,} game-steps; final batch "
           f"{'played' if (d / 'eval_final.npz').is_file() else 'not played'}")
    why = []
    if (d / "controls.json").is_file():
        bad = {k: v["status"] for k, v in json.loads((d / "controls.json").read_text()).items() if v["status"] != "PASS"}
        if bad:
            why.append("controls not PASS: " + ", ".join(f"{k} {v}" for k, v in bad.items()))
    if (d / "exit_code").is_file():
        why.append(f"exit {l011rec.exit_word(d)}")
    if not (d / "results.json").is_file():
        why.append("no complete results.json")
    return {"what": what, "ran": ran, "why": "; ".join(why) or "unknown (read job.log)"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--verdict", type=Path)
    ap.add_argument("--aborted", action="store_true", help="an ABORTED record from --runs (no verdict)")
    ap.add_argument("--runs", help="comma list of run folders (--aborted)")
    ap.add_argument("--pilot", type=Path, help="the pilot's pilot.json: the Strike probes are printed with the recipe")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--name", default=None)
    ap.add_argument("--number", default=None)
    a = ap.parse_args(argv)
    if a.out.exists():
        print(f"refused: {a.out} exists (a record is never overwritten)", file=sys.stderr)
        return 1
    name = a.name or a.out.stem.replace("_record", "")
    if a.aborted:
        if not a.runs:
            print("refused: --aborted needs --runs", file=sys.stderr)
            return 1
        runs = {d: run_summary(Path(d)) for d in [x.strip() for x in a.runs.split(",") if x.strip()]}
        text, row = aborted_text(runs, name, a.number)
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(text)
        print(f"wrote {a.out}\nledger row:\n{row}")
        return 0
    if a.verdict is None:
        print("refused: give --verdict, or --aborted with --runs", file=sys.stderr)
        return 1
    verdict = json.loads(a.verdict.read_text())
    if not verdict.get("controls_pass"):
        print("refused: the verdict's controls_pass is false: write an ABORTED record (--aborted)", file=sys.stderr)
        return 1
    runs = {}
    for key, d in verdict["runs"].items():
        runs[key] = {"dir": d, **json.loads((Path(d) / "results.json").read_text())}
    text, row = record_text(verdict, runs, name, a.number)
    if a.pilot is not None:                  # QC M-5: the probe counts with their denominators next to the recipe
        pj = json.loads(a.pilot.read_text())
        probes = ["Strike probes of the pilot (reaches / ended training games per update):", ""]
        probes += [f"- {dict((k, v) for k, v in pr.items() if k not in ('updates', 'learner_control'))}: "
                   + ", ".join(f"{u['reaches']}/{u['ended']}" for u in pr["updates"]) for pr in pj.get("probes", [])]
        probes += [f"- recipe picked: {pj.get('strike_recipe')}; learner positive control: {pj.get('learner_control')}"]
        text = text.replace("## Gates", "\n".join(probes) + "\n\n## Gates", 1)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(text)
    print(f"wrote {a.out}\nledger row:\n{row}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
