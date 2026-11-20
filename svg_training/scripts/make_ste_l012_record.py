#!/usr/bin/env python
"""Draft the record of the L0.12 Best-response test from its verdict and run folders (records/README.md; STANDARDS
section 8; the sections of T44's record, records/2026-11-21_ste_l011_screen_record.md).

    make_ste_l012_record.py --verdict <folder>/verdict.json --out records/<date>_ste_l012_best_response_record.md
                            [--name <date>_ste_l012_best_response] [--number T<n>]

Refuses to overwrite (a record is never edited after it is written; additions go under "Run notes added by the lead").
The verdict word is INFO when every control of every run is PASS (the variant categories feed gate G0; the owner rules),
and ABORTED otherwise. GPU-hours: each run's own ledger lines in the shared folder, if launched as a job. Prints the
ledger row. Exit 0 written, 1 refused."""
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
             "and the Strike side is INCONCLUSIVE. The parked-Guard probes are information only. The recipe of each run is in the tables below.")


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
    row = (f"| {number or 'T?'} | {name} | L0.12 Best-response test | {word.split(' ')[0]} | "
           + "; ".join(f"{v}: {e['category']}" for v, e in verdict["variants"].items()) + " |")
    return "\n".join(lines) + "\n", row


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--verdict", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--name", default=None)
    ap.add_argument("--number", default=None)
    a = ap.parse_args(argv)
    if a.out.exists():
        print(f"refused: {a.out} exists (a record is never overwritten)", file=sys.stderr)
        return 1
    verdict = json.loads(a.verdict.read_text())
    runs = {}
    for key, d in verdict["runs"].items():
        runs[key] = {"dir": d, **json.loads((Path(d) / "results.json").read_text())}
    name = a.name or a.out.stem.replace("_record", "")
    text, row = record_text(verdict, runs, name, a.number)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(text)
    print(f"wrote {a.out}\nledger row:\n{row}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
