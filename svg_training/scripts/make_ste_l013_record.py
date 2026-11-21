#!/usr/bin/env python
"""Draft the record of STE task L0.13 Does tier 2 train at all? from its verdict and the two arm folders
(records/README.md; STANDARDS section 8; the sections of the L0.12 record).

    make_ste_l013_record.py --verdict <folder>/verdict.json --out records/<date>_ste_l013_tier2_trains_record.md
                            [--name <date>_ste_l013_tier2_trains] [--number T<n>]
    make_ste_l013_record.py --aborted --runs <t1 run>,<t2 run> --out records/<...>_record.md [--why "<the lead's line>"]

Refuses to overwrite (a record is never edited after it is written; additions go under "Run notes added by the lead").
With --verdict the word is the gate's (PASS, FAIL or TOO_SLOW; ``ste_tier2_l013.py verdict`` only accepts arms whose
controls all passed and that finished). With --aborted it writes an ABORTED record from the run folders alone: what ran
and why it ended, no hold rate read as a result and no verdict word. GPU-hours: each arm's own ledger lines in the shared
folder, if launched as a job. Prints the ledger row. Exit 0 written, 1 refused."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
sys.path.insert(0, str(ROOT / "scripts"))

import make_ste_l011_record as l011rec  # noqa: E402  (GPU-hours and exit words)
import make_ste_l012_record as l012rec  # noqa: E402  (first launch, number formatting)

SIM = ("training simulator: tier 1 (fast engine; Starling layer: commander copy, safety filter on every pair, fitted PX4 "
       "response, exploratory) and tier 2 (the same command chain driving the Isaac Lab 2.3.2 rigid-body Starling in "
       "PhysX); study tag on (P1, PROPOSED)")
RUN_NOTES = (
    "- **Never suspend the machine during a GPU job**: the cap clock and the GPU-hour ledger are wall clock less the "
    "owner's gpu_pause.sh pauses only. Say here whether the machine was suspended during the runs.",
    "- **The game** (LEAD CALL 21 Nov 2026): PLAN.md row L0.13 named pilot P1b's recipe in the hangar game; the lead moved "
    "the task to the STE game: the L0.12 Guard run's recipe (T41's, one decision per 0.6 s, terminal reward only) on the "
    "L0.11 base game (tag 1.6 m, 3v3), exploiter Guard team against strike_straight. The PLAN's gate is kept in substance.",
    "- **One procedure in both arms**: same games at once, game-step budget, seed and evaluation starts; one Isaac world per "
    "process, so tier 2 evaluations play on a view of the training world, and after every evaluation the training games "
    "restart afresh in both arms.",
    "- **Resume** (by design): networks, optimisers, scalers, counters and the torch random state are restored at the last "
    "update boundary; the training games restart afresh, so a resumed arm is not identical to an unbroken one.",
    "- **3-D clips** of the key games: pending (task VID-1b); the 2-D clips with the height panel are listed below.")


def ci(d: dict | None) -> str:
    if not d or not d.get("n"):
        return "n/a"
    return f"{d['k']}/{d['n']} = {d['rate']:.3f} ({d['ci'][0]:.3f}–{d['ci'][1]:.3f})"


def ledger_row(number, dirs, gpu, name, what, word) -> str:
    """LEDGER.md's seven columns: # | Date | Simulator | Run | What | Result | Record."""
    return (f"| {number or 'T?'} | {l012rec.first_launch(dirs)} | {SIM}; {gpu or 'CPU'} | {name} | STE L0.13 Does tier 2 "
            f"train at all? {what}{l012rec.hours_cell(dirs)} | {word} | records/{name}_record.md |")


def record_text(v: dict, arms: dict, name: str, number: str | None) -> tuple[str, str]:
    d, t1, t2 = v["detail"], v["t1"], v["t2"]
    lines = [f"Simulator: {SIM}. Observed in the training simulator; not a flight result.", "", f"# {name} record", "",
             "## Run notes", "", *RUN_NOTES, "", "## Purpose", "",
             "STE task L0.13 Does tier 2 train at all? (PLAN.md section 4): the L0.12 Guard recipe trained on tier 2 (the "
             "Isaac Lab rigid-body Starling) beside a fresh tier 1 control with the same games at once and the same "
             "game-steps; tier 2 trains if its final Guard's hold rate on tier 2 has a Wilson lower bound above the parked "
             "Guard's upper bound in the same batch.", "", "## Config", "",
             f"- Gate file sha256 `{v['gates_sha256']}` (copy in each arm folder: `gates.toml`)."]
    a2 = arms["t2"]
    lines += [f"- Game `{a2['game_file']['file']}`, sha256 `{a2['game_file']['sha256']}` (tier 2 sets "
              f"starling.backend = \"physics\" in code; the file is never edited).",
              f"- {a2['num_games']:,} games at once in both arms; {a2['planned_updates']} updates = "
              f"{a2['planned_game_steps']:,} game-steps planned; training seed {a2['train_seed']} in both arms; T44's first "
              f"{a2['eval_games']} starts for every scoring batch.", "", "## Model parameter set", ""]
    for arm, r in arms.items():
        ps = r["parameter_set"]
        lines.append(f"- {arm} (tier {r['tier']}): `{ps['file']}`, sha256 `{ps.get('sha256')}`; safety filter on {ps['filter']}"
                     + (f"; sim-only gains {ps['sim_only_gains']!r}" if ps.get("sim_only_gains") is not None else ""))
    lines += ["", "## Commit", ""] + [f"- {arm}: `{r['code']['first']['commit']}` (diff sha256 "
                                      f"{r['code']['first']['diff_sha256'][:12]})" for arm, r in arms.items()]
    lines += ["", "## Machine", ""]
    for arm, r in arms.items():
        hours, _ = l011rec.gpu_hours(Path(r["dir"]))
        lines.append(f"- {arm}: {r['machine']['host']}, {r['machine']['gpu']}, torch {r['machine']['torch']}; exit "
                     f"{l011rec.exit_word(Path(r['dir']))}; effective {r['effective_s']:.0f} s of {r['cap_h']} h; "
                     f"{r['launches']} launch(es); {hours}")
    lines += ["", "## Games at once and steps per second", ""]
    lines += [f"- {arm}: {r['num_games']:,} training games, 6 drones per game, tier {r['tier']}, {r['machine']['gpu']}: "
              f"median {(r['game_steps_per_s_median'] or 0):,.0f} game-steps/s; {r['trained_updates']} updates, "
              f"{r['game_steps']:,} game-steps ({r['train_stop']})" for arm, r in arms.items()]
    lines += ["", "## Gates", "", f"Verdict: **{v['verdict']}**." + (f" Reading (pre-registered): {d['reading']}."
                                                                      if d.get("reading") else ""), "",
              "| Arm | Tier | Trained Guard holds | Parked Guard holds (same batch) | Bar cleared | Budget reached |",
              "|---|---|---|---|---|---|",
              f"| t2 | 2 | {ci(t2['trained'])} | {ci(t2['parked'])} | **{t2['bar']['cleared']}** | {t2['budget_reached']} |",
              f"| t1 (control, INFO) | 1 | {ci(t1['trained'])} | {ci(t1['parked'])} | {t1['bar']['cleared']} | "
              f"{t1['budget_reached']} |"]
    m = v["matrix_same_update"]
    cell = lambda c: "n/a" if not c else f"{c['holds']}/{c['games']}"  # noqa: E731
    lines += ["", f"Networks x tiers at update {m['update']} (T44's starts, INFO):", "",
              "| Networks | Tier 1 holds | Tier 2 holds |", "|---|---|---|"]
    lines += [f"| {w} | {cell(m[w]['tier 1'])} | {cell(m[w]['tier 2'])} |" for w in ("t2 networks", "t1 networks")]
    p = t2.get("paired_t2_on_t2_v_t1_on_t1")
    if p:
        lines += ["", f"Paired by start (t2 networks on tier 2 v t1 networks on tier 1): held in both {p['both']}, t2 only "
                      f"{p['t2_only']}, t1 only {p['t1_only']}, neither {p['neither']}."]
    s = v["l012_scale"]
    lines += ["", f"Scale (INFO): L0.12's base Guard held {s['holds']}/{s['games']} on tier 1 at {s['game_steps']:,} "
                  f"game-steps ({s['record']}).", "", "## Figures and videos", "",
              f"- learning curves: `{Path(v.get('dir', '.')) / v['figure']}` (each arm's networks on its own tier and the "
              "other tier; the parked Guard's interval as a band)."]
    for arm in ("t1", "t2"):
        lines += [f"- {arm}: {x}" for x in v[arm]["videos"]]
    lines += ["", "## Reading", "", "(The lead writes the reading after QC; numbers come from the tables above.)", ""]
    row = ledger_row(number, [t1["dir"], t2["dir"]], t2["machine"]["gpu"], name,
                     f"t2 {ci(t2['trained'])} v parked {ci(t2['parked'])} on tier 2; t1 {ci(t1['trained'])} on tier 1; "
                     f"{t2['game_steps']:,} game-steps", v["verdict"])
    lines += ["## Ledger row", "", "Ledger row: " + row, ""]
    return "\n".join(lines) + "\n", row


def run_summary(d: Path) -> dict:
    """What an arm folder shows: what ran and why it ended (never a result)."""
    meta = json.loads((d / "run.json").read_text()) if (d / "run.json").is_file() else {}
    log = (d / "train_log.jsonl").read_text().splitlines() if (d / "train_log.jsonl").is_file() else []
    updates = {json.loads(x)["update"] for x in log}
    steps = json.loads(log[-1])["game_steps_total"] if log else 0
    ran = (f"controls batch {'played' if (d / 'eval_before_t1.npz').is_file() else 'not finished'}; {len(updates)} "
           f"training updates, {steps:,} game-steps; final batch "
           f"{'played' if (d / 'eval_final_t1.npz').is_file() else 'not played'}")
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
    elif not why:
        why.append(f"finished, controls PASS ({'exit 0' if code == '0' else 'no exit_code file'}, results.json complete)")
    return {"what": f"arm {meta.get('arm', '?')} (tier {meta.get('tier', '?')})", "ran": ran,
            "why": "; ".join(why) or "unknown (read job.log)", "gpu": ((res or {}).get("machine") or {}).get("gpu")}


def aborted_text(runs: dict, name: str, number: str | None, why: str | None) -> tuple[str, str]:
    lines = [f"Simulator: {SIM}. Observed in the training simulator; not a flight result.", "", f"# {name} record", "",
             "## Gates", "", "Verdict: **ABORTED**. Nothing below is a result: no hold rate is read and no verdict word is "
             "given for arms whose controls did not all pass or that did not finish (gate [controls])."
             + (f" The lead: {why}." if why else ""), "", "| Run | Arm | What ran | Why it ended |", "|---|---|---|---|"]
    for d, info in runs.items():
        lines.append(f"| {d} | {info['what']} | {info['ran']} | {info['why']} |")
    lines += ["", "## Run notes", "", *RUN_NOTES, ""]
    gpus = sorted({info["gpu"] for info in runs.values() if info.get("gpu")})
    row = ledger_row(number, list(runs), ", ".join(gpus), name,
                     "; ".join(f"{i['what']}: {i['why']}" for i in runs.values()), "ABORTED")
    lines += ["## Ledger row", "", "Ledger row: " + row, ""]
    return "\n".join(lines) + "\n", row


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--verdict", type=Path)
    ap.add_argument("--aborted", action="store_true", help="an ABORTED record from --runs (no verdict)")
    ap.add_argument("--runs", help="comma list of arm folders (--aborted)")
    ap.add_argument("--why", help="the lead's one-line reason (--aborted)")
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
        text, row = aborted_text(runs, name, a.number, a.why)
    else:
        if a.verdict is None:
            print("refused: give --verdict, or --aborted with --runs", file=sys.stderr)
            return 1
        v = json.loads(a.verdict.read_text())
        if not v.get("controls_pass"):
            print("refused: the verdict's controls_pass is false: write an ABORTED record (--aborted)", file=sys.stderr)
            return 1
        v["dir"] = str(a.verdict.parent)
        arms = {arm: json.loads((Path(v[arm]["dir"]) / "results.json").read_text()) | {"dir": v[arm]["dir"]}
                for arm in ("t1", "t2")}
        text, row = record_text(v, arms, name, a.number)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(text)
    print(f"wrote {a.out}\nledger row:\n{row}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
