#!/usr/bin/env python
"""Draft the record of the L0.12 Best-response test from its verdict and run folders (records/README.md; STANDARDS
section 8; the sections of T44's record, records/2026-11-21_ste_l011_screen_record.md).

    make_ste_l012_record.py --verdict <folder>/verdict.json --out records/<date>_ste_l012_best_response_record.md
                            [--name <date>_ste_l012_best_response] [--number T<n>] [--pilot <pilot run>/pilot.json]
    make_ste_l012_record.py --aborted --runs <run>,<run>,... --out records/<...>_record.md [--name ...] [--number ...]
    (both: [--task L0.12b] names the task in the record and the ledger row; default L0.12)

Refuses to overwrite (a record is never edited after it is written; additions go under "Run notes added by the lead").
With --verdict the word is INFO: ``verdict`` only accepts runs whose controls all passed (QC C-1), and this writer
refuses a verdict.json whose ``controls_pass`` is false. The record and its ledger row carry every side's status, gain,
Guards left in holds and game length next to the variant category (QC I-8: the category alone is set by T44's scripts).
With --aborted it writes an ABORTED record from the run folders alone: for each run what ran (phase, updates, game-steps)
and why it ended (controls not PASS, exit code, no complete results), with NO gain, status or category. GPU-hours: each
run's own ledger lines in the shared folder, if launched as a job. Prints the ledger row. Exit 0 written, 1 refused."""
from __future__ import annotations

import argparse
import datetime
import json
import math
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
             "shaping 1.0, training reward only), also when neither probe shows a reach (LEAD CALL 21 Nov 2026, QC N-1: "
             "3-update probes no longer stop the Strike runs). The parked-Guard probes are information only. The recipe "
             "of each run is in the tables below.",
             "- **Run 0, the learner positive control** (LEAD CALL 21 Nov 2026, QC N-1; gate [run0]): the Strike recipe "
             "trained against the parked Guard at the budget and cap of a run of record, read at pre-listed checkpoints "
             "(reach rate at least scripted strike_straight's on the same starts minus 0.05). Strike runs need run 0 = "
             "PASS; if it reads FAIL the Strike runs are not launched and the Strike side is INCONCLUSIVE (the trainer "
             "did not learn the easy Strike task at the run budget). Guard runs do not depend on it.",
             "- **Hours** (LEAD CALL 21 Nov 2026, QC N-3): nothing kills a run at --gpu-h during its final phase; the "
             "GPU-hours below are the ledger's real hours.",
             "- **Resume** (by design): networks, optimisers, scalers, counters and the torch random state are restored at "
             "the last update boundary, but the training games restart from the run seed's first starts (the game "
             "generator is not checkpointed), so a resumed run is not identical to an uninterrupted run. Each run's job "
             "launches say whether it was resumed.")


def num(x, fmt: str = "{:.2f}") -> str:
    """A rounded number, or "-" for a missing or nan value (never a raw float in a record)."""
    if x is None or x == "-" or (isinstance(x, float) and math.isnan(x)):
        return "-"
    return fmt.format(x) if isinstance(x, (int, float)) else str(x)


def first_launch(dirs) -> str:
    """The ledger's Date: the earliest launch in the runs' launches.jsonl (+08:00 here), else now."""
    times = []
    for d in dirs:
        f = Path(d) / "launches.jsonl"
        if f.is_file():
            times += [e["time"] for e in map(json.loads, filter(str.strip, f.read_text().splitlines()))
                      if e.get("event") == "launch"]
    t = datetime.datetime.fromtimestamp(min(times)) if times else datetime.datetime.now()
    return t.astimezone().isoformat(timespec="seconds")


def hours_cell(dirs) -> str:
    used = [h for h in (l011rec.gpu_hours(Path(d))[1] for d in dirs) if h is not None]
    return f"; {sum(used):.3f} GPU-h" if used else ""


def ledger_row(number, dirs, simulator, gpu, name, what, word, task: str = "L0.12") -> str:
    """LEDGER.md's seven columns: # | Date | Simulator | Run | What | Result | Record."""
    return (f"| {number or 'T?'} | {first_launch(dirs)} | {simulator}; {gpu or 'CPU'} | {name} | STE {task} "
            f"Best-response test: {what}{hours_cell(dirs)} | {word} | records/{name}_record.md |")


def ci(d: dict | None) -> str:
    if not d or not d.get("n"):
        return "n/a"
    return f"{d['k']}/{d['n']} = {d['rate']:.3f} ({d['ci'][0]:.3f}–{d['ci'][1]:.3f})"


Z_UP = ("strike_high", "strike_low")
Z_LABEL = "tier 1 vertical response not fitted (s2b.toml z_up_info)"


def lab(name: str) -> str:
    return f"{name} ({Z_LABEL})" if name in Z_UP else name


def purpose(verdict: dict, task: str, runs: dict | None = None) -> str:
    """The Purpose paragraph: L0.12's, or (a reference not made by T44, L0.12b) the same method on that reference; a run
    whose gate file named its training opponent (train_opponent, L1 side track) is said to train against it."""
    explicit = [f"{k} trained against its explicit opponent {r['opponent']} ({r['opponent_choice']})"
                for k, r in (runs or {}).items() if r.get("opponent_choice") == "explicit, not the maximin pick"]
    if explicit:
        return (f"STE task {task}: L0.12's best-response method, with the training opponent named in the gate file: "
                f"{'; '.join(explicit)}; the gain over the best script against that opponent on T44's own starts "
                f"(INFO).")
    label = verdict.get("reference_label", "T44")
    if label == "T44":
        return ("STE task L0.12 Best-response test (PLAN.md section 4): for each shortlisted variant of T44, an exploiter "
                "Strike team trained against the best scripted Guard g* and an exploiter Guard team trained against the "
                "best scripted Strike s*; the gain of each over the best script on T44's own starts, and the variant's "
                "category on the better of script and exploiter (LEAD CALL 21 Nov 2026).")
    return (f"STE task {task}: L0.12's best-response method on the variant(s) {', '.join(verdict['variants'])}: an "
            f"exploiter Strike team trained against the best scripted Guard g* and an exploiter Guard team trained "
            f"against the best scripted Strike s*, g* and s* and the script baselines from {label} (on T44's own "
            f"starts); the gain of each over the best script, the category on the better of script and exploiter, and "
            f"the unchosen-tag shares (INFO).")


def unchosen_lines(verdict: dict) -> list[str]:
    """L0.12b: the trained exploiter's unchosen-tag shares per side (INFO); nothing when no side has them."""
    rows = [(v, s, sr["tag_shares"]) for v, e in verdict["variants"].items() for s, sr in e["sides"].items()
            if sr.get("tag_shares") and sr["tag_shares"].get("tag_edge_m") is not None]
    if not rows:
        return []
    out = ["", "Unchosen tags of the trained exploiter (INFO; pushed together = on the tag's tick the safety filter's "
           "correction closed the pair faster than the players' commands; filter active = the filter corrected either "
           "drone of the pair on that tick, an upper bound; at the filter edge = pair distance at most the filter "
           f"distance plus the gate's margin, {num(rows[0][2]['tag_edge_m'], '{:.2f}')} m):", "",
           "| Variant | Side | Cell | Tags | Pushed together (share) | Filter active (share) | At the edge (share) |",
           "|---|---|---|---|---|---|---|"]
    for v, s, ts in rows:
        out.append(f"| {v} | {s} | {ts['cell']} | {ts['tags_counted']} | {ts['tags_pushed']} "
                   f"({num(ts.get('pushed_tag_share'), '{:.3f}')}) | {ts['tags_filtered']} "
                   f"({num(ts.get('filter_active_share'), '{:.3f}')}) | {ts['tags_at_edge']} "
                   f"({num(ts.get('edge_tag_share'), '{:.3f}')}) |")
    return out


def record_text(verdict: dict, runs: dict, name: str, number: str | None, task: str = "L0.12") -> tuple[str, str]:
    word = "INFO (every control PASS; the categories feed gate G0)" if verdict["controls_pass"] else \
        "ABORTED (a control is not PASS: read controls.json of each run)"
    lines = [f"Simulator: {verdict['simulator']}. Observed in the training simulator; not a flight result.", "",
             f"# {name} record", "", "## Run notes", "", *RUN_NOTES, "", "## Purpose", "", purpose(verdict, task, runs), "",
             "## Config", "", f"- Gate file sha256 `{verdict['gates_sha256']}` (copy in each run folder: `gates.toml`).",
             f"- Band {verdict['band']} (PROPOSED by the lead)."]
    first = next(iter(runs.values()))
    source = verdict.get("reference_label", "T44")
    lines += [f"- Reference `{first['reference']['file']}`, sha256 `{first['reference']['sha256']}`; T44's starts sha256 "
              f"`{first['reference']['start_sha256']}`; {source} gate sha256 `{first['reference']['t44_gates_sha256']}`."]
    games = {r["game_file"]["file"]: r["game_file"]["sha256"] for r in runs.values()}
    lines += [f"- Game `{f}`, sha256 `{h}`." for f, h in games.items()]
    lines += [f"- {k}: trainer settings {r['settings']}" for k, r in runs.items()]
    # STE L1 side track: a run whose opponent the gate file named (train_opponent) says so; its preflight skipped the
    # g*/s* maximin check for that side only. Also a training game other than the scoring game.
    lines += [f"- {k}: trained against {r['opponent']} ({r['opponent_choice']}; the g*/s* maximin check was skipped for "
              f"this side only); the Purpose's g*/s* wording does not apply to it." for k, r in runs.items()
              if r.get("opponent_choice") == "explicit, not the maximin pick"]
    lines += [f"- {k}: trained on `{r['train_game_file']['file']}` (sha256 `{r['train_game_file']['sha256']}`), scored on "
              f"`{r['game_file']['file']}`." for k, r in runs.items()
              if r.get("train_game_file") and r["train_game_file"] != r["game_file"]]
    lines += [f"- {k}: {r['clock_note']}." for k, r in runs.items() if r.get("clock_note")]
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
    r0 = verdict.get("run0")
    if r0:
        reads = ", ".join(f"update {x['update']}: {x['trained']['k']}/{x['trained']['n']}" for x in r0.get("reads") or [])
        lines += ["", "## Run 0 (learner positive control)", "",
                  f"Run 0: **{r0['status']}** ({r0.get('train_stop')}); scripted {ci(r0.get('script'))}; reads {reads or '-'} "
                  f"(`{r0['file']}`, sha256 {r0['sha256'][:12]})."]
    accepted = [f"{v} {s}: {sr['run0']['learner_control_accepted']}" for v, e in verdict["variants"].items()
                for s, sr in e["sides"].items() if (sr.get("run0") or {}).get("learner_control_accepted")]
    if accepted:
        lines += ["", "Lead's decisions on run 0 (--accept-learner-control): " + "; ".join(accepted) + "."]
    lines += ["", "## Gates", "", f"Verdict: **{word}**.", "", "| Variant | Role | Strike side | Guard side | Better Strike "
              "reach upper | Better Guard hold upper | Category |", "|---|---|---|---|---|---|---|"]
    for v, e in verdict["variants"].items():
        s, g = e["sides"].get("strike"), e["sides"].get("guard")
        lines.append(f"| {v} | {e['role']} | {s['status'] if s else '-'} | {g['status'] if g else '-'} | "
                     f"{num(e.get('strike_upper'), '{:.3f}')} | {num(e.get('guard_upper'), '{:.3f}')} | "
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
                         f"{num(comp.get('guards_left_mean_in_holds'), '{:.3f}')} | {num(comp.get('length_median_s'))} |")
    lines += unchosen_lines(verdict)
    extras = [(k, o, e) for k, r in runs.items() for o, e in r.get("extra_opponents", {}).items()]
    if extras:
        lines += ["", f"Evaluation-only opponents (INFO; script baseline from the {source} reference, same starts):", "",
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
                         f"{num(comp.get('guards_left_mean_in_holds'), '{:.3f}')}, "
                         f"{num(comp.get('length_median_s'))} s median")
        parts.append("; ".join(sides) + f" (category {e['category']}, set by {source}'s scripts)")
    dirs = [r["dir"] for r in runs.values()] + ([str(Path(r0["file"]).parent)] if r0 else [])
    row = ledger_row(number, dirs, verdict["simulator"], (verdict.get("machine") or {}).get("gpu"), name,
                     " / ".join(parts), word.split(" ")[0], task)
    lines += ["## Ledger row", "", "Ledger row: " + row, ""]
    return "\n".join(lines) + "\n", row


def aborted_text(runs: dict, name: str, number: str | None, task: str = "L0.12") -> tuple[str, str]:
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
    gpus = sorted({info["gpu"] for info in runs.values() if info.get("gpu")})
    row = ledger_row(number, list(runs), sim, ", ".join(gpus), name, "; ".join(whys), "ABORTED", task)
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
    code = (d / "exit_code").read_text().strip() if (d / "exit_code").is_file() else None
    if code is not None and code != "0":
        why.append(f"exit {l011rec.exit_word(d)}")
    res = json.loads((d / "results.json").read_text()) if (d / "results.json").is_file() else None
    if res is None or res.get("complete") is not True:
        why.append("no complete results.json")
    elif not why:                              # QC N-4 (LEAD CALL 21 Nov 2026): a cleanly finished run says so
        exit_text = "exit 0" if code == "0" else "no exit_code file"
        done = "finished, " if res.get("budget_reached") is True else ""     # a run cut before its budget did not finish
        why.append(f"{done}controls PASS ({exit_text}, results.json complete)")
    if res is not None and res.get("budget_reached") is not True:     # QC N-2: why no side status is read
        why.append(f"training stopped before its game-step budget ({res.get('train_stop')})")
    return {"what": what, "ran": ran, "why": "; ".join(why) or "unknown (read job.log)",
            "gpu": ((res or {}).get("machine") or {}).get("gpu")}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--verdict", type=Path)
    ap.add_argument("--aborted", action="store_true", help="an ABORTED record from --runs (no verdict)")
    ap.add_argument("--runs", help="comma list of run folders (--aborted)")
    ap.add_argument("--pilot", type=Path, help="the pilot's pilot.json: the Strike probes are printed with the recipe")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--name", default=None)
    ap.add_argument("--number", default=None)
    ap.add_argument("--task", default="L0.12", help="the task named in the record and the ledger row (L0.12b)")
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
        text, row = aborted_text(runs, name, a.number, a.task)
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
    text, row = record_text(verdict, runs, name, a.number, a.task)
    if a.pilot is not None:                  # QC M-5: the probe counts with their denominators next to the recipe
        pj = json.loads(a.pilot.read_text())
        probes = ["Strike probes of the pilot (reaches / ended training games per update):", ""]
        probes += [f"- {dict((k, v) for k, v in pr.items() if k not in ('updates', 'learner_control'))}: "
                   + ", ".join(f"{u['reaches']}/{u['ended']}" for u in pr["updates"]) for pr in pj.get("probes", [])]
        probes += [f"- recipe picked: {pj.get('strike_recipe')} (the learner positive control is run 0, above)"]
        text = text.replace("## Gates", "\n".join(probes) + "\n\n## Gates", 1)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(text)
    print(f"wrote {a.out}\nledger row:\n{row}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
