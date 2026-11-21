#!/usr/bin/env python
"""Draft the record of an L0.3 run (STE Guard policy in tier 2 without retraining) and its ledger row, from the two run
folders alone (records/README.md; STANDARDS section 8; the pattern of make_ste_l011_record.py, T44).

    make_ste_l03_record.py --run-dir runs/<date>_ste_l03_transfer --cpu-run runs/<date>_ste_l03_cpu --number T<n>
                           [--name ...] [--out-dir records] [--append-ledger]

Refuses to overwrite a record and refuses a smoke run. Verdict word: INFO when the GPU part finished (exit 0) and every
control passed, ABORTED otherwise. Exit 0 written, 1 refused."""
from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
sys.path.insert(0, str(ROOT / "scripts"))

from make_ste_l011_record import exit_word, gpu_hours  # noqa: E402

SIMULATOR = ("training simulator, the hangar game of Phase 4 row 6 (tier 2: Isaac Lab rigid-body Starling; safety filter "
             "on every pair, drones free in height with the start jitter) beside row 5 (tier 1, fitted response, "
             "exploratory)")


def _r(s: dict) -> str:
    if s["rate"] is None:
        return f"{s['count']} / {s['games']}"
    return f"{s['count']} / {s['games']} ({s['rate']:.3f}, Wilson [{s['ci'][0]:.3f}, {s['ci'][1]:.3f}])"


def record_text(run_dir: Path, cpu_run: Path, res: dict, name: str, number: str) -> tuple[str, str]:
    code = (run_dir / "exit_code").read_text().strip() if (run_dir / "exit_code").is_file() else None
    missing = [c for c in ("C-0", "C-1", "C-2", "C-3") if c not in res["controls"]]          # LEAD CALL QC L02-6
    failed = [k for k, v in res["controls"].items() if not v.get("pass", False)]
    ok = (res["stopped"] is None and code == "0" and res["controls_all_pass"] and not missing and not failed
          and not res.get("terminal"))
    verdict = "INFO" if ok else "ABORTED"
    why = "; ".join([f"failed {', '.join(failed)}"] * bool(failed) + [f"missing {', '.join(missing)}"] * bool(missing)
                    + [f"stopped {res['stopped']}"] * bool(res["stopped"]) + [f"exit {code}"] * (code != "0")
                    + ["non-finite (terminal)"] * bool(res.get("terminal")))
    hours_text, hours = gpu_hours(run_dir)
    arms, ref = res["arms"], res["references"]
    t2, t1 = arms.get("t2_t41"), arms.get("t1_cpu_t41")
    parked, cuda = arms.get("t2_parked"), arms.get("t1_cuda_t41")
    p = res.get("t2_v_t1_cpu", {})
    rates = ", ".join("{} {:,.0f}".format(k, m.get("game_steps_per_s") or 0) for k, m in arms.items() if m["tier"] == 2)
    rows = ["| Arm | Tier, row | Device | Players | Counted | Result | Closest 3-D min / median (m) | Filter share | "
            "Rule breach share | Upset games | Mean end tick |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for k, m in arms.items():
        s = m["summary"]
        who = "ParkedGuard v S20" if k == "t2_parked" else "T41 v S20"
        rows.append(f"| {k} | {m['tier']}, row {m['row']} | {m.get('gpu') or m['device']} | {who} | {s['counted']} | {_r(s)} | "
                    f"{s['closest_3d_min_m']:.2f} / {s['closest_3d_median_m']:.2f} | {s['filter_share']:.3f} | "
                    f"{s['rule_breach_share']:.3f} | {s['upset_games']} | {s['mean_end_step']:.0f} |")
    ctl = ["| Control | Result | Detail |", "|---|---|---|"]
    for k, v in res["controls"].items():
        ctl.append(f"| {k} | {'PASS' if v['pass'] else 'FAIL'} | "
                   f"{json.dumps({a: b for a, b in v.items() if a != 'pass'}, default=str)[:400]} |")
    lines = [f"Simulator: {SIMULATOR}. Observed in the training simulator; not a flight result.", "",
             f"# {name} record", "",
             "## Run notes", "", "- Say here whether the machine was suspended during the run.", "",
             "## Purpose", "",
             "STE task L0.3 (INFO, PLAN.md section 4; DISCUSSION P3): does the STE Guard policy (T41, trained on tier 1, "
             f"{ref['t41_holds']} of {ref['t41_games']} holds against S20) keep its hold rate on the Isaac Lab physics drone, "
             "on the same 1,000 paired starts, without retraining? Parked Guard as the control.", "",
             "## Commit", "", f"{(t2 or t1 or {}).get('commit', 'unknown')}"
                              f"{' (working tree not clean)' if (t2 or t1 or {}).get('dirty') else ''}", "",
             "## Config", "", f"- Gate file copy `gates.toml`, sha256 `{res['gates_sha256']}` (both run folders).",
             "- T41's game (Phase 4 row 5) and its tier 2 game (row 6, the drone only: control C-0); T41 as a held "
             "strategy (one decision per 12 ticks, mean actions) against S20, T41's evaluation and opponent seeds; the "
             "parked control through T24's path (ParkedGuard, the ladder seed).", "",
             "## Model parameter set", "", "Row 5: `params/real_exploratory_v0.toml` (EXPLORATORY). Row 6: "
             "`params/starling_physics_v0.toml` with the SIM-ONLY yaw gains.", "",
             "## Seeds", "", "Evaluation seed 1101, opponent seed 1303 (T41's own); ladder seed for the parked control. "
             "One policy, one opponent, 1,000 fixed starts.", "",
             "## Machine", "", f"CPU part: {t1.get('machine') if t1 else 'n/a'}, {t1.get('threads') if t1 else 'n/a'} threads. "
             f"GPU part: {(t2 or {}).get('gpu') or 'n/a'}, torch {(t2 or {}).get('torch')}. Exit code {exit_word(run_dir)}. "
             f"{hours_text}.", "",
             "## Games at once and steps per second", "",
             f"1,000 games x 6 drones in one Isaac world; tier 2 rates {rates} game-steps/s.", "",
             "## Results", "", *rows, "",
             f"Paired by start, tier 2 against tier 1 (CPU): held in both {p.get('both_hold')}, lost on tier 2 "
             f"{p.get('lost_here')}, gained on tier 2 {p.get('gained_here')}, lost in both {p.get('both_lost')}; sign test "
             f"p = {p.get('sign_test_p')}. References: T41 {ref['t41_holds']} holds (tier 1, RTX 5090 CUDA); T45 831 "
             f"(tier 1, CPU); T24 parked {ref['t24_parked_reaches']} reaches (row 6, RTX 5090); T23 parked "
             f"{ref['t23_parked_holds']} holds (row 5)."
             + (f" Tier 1 on this GPU: {_r(cuda['summary'])}; {res.get('t1_cuda_v_t1_cpu', {}).get('outcomes_differ')} games "
                "differ from the CPU." if cuda else ""), "",
             "## Gates", "", f"Verdict: **{verdict}**{' (' + why + '; rates void)' if verdict == 'ABORTED' else ''}. No gate "
             "on the hold rate (INFO). Controls:", "", *ctl, "",
             "## Videos", "", "2-D clips (STANDARDS section 8): " + "; ".join(res.get("clips", ["none"])) + ". 3-D Isaac "
             f"Lab clips (VID-1) pending; key games (paired starts lost / gained on tier 2): "
             f"{res.get('vid1_key_games', {}).get('slots', [])}.", "",
             "## Limits", "", "- One policy, one opponent, one seed of starts: no method claim (STANDARDS 6.5).",
             "- Tier 2 is the training simulator's physics drone, not a flight.", ""]
    if verdict == "ABORTED":                     # LEAD CALL QC L02-7: an ABORTED row never leads with a number
        head = f"ABORTED ({why}); rates void"
    else:
        head = (f"T41 v S20 on tier 2 {_r(t2['summary'])}; tier 1 CPU {t1['summary']['count']}; lost {p.get('lost_here')} / "
                f"gained {p.get('gained_here')}; parked {parked['summary']['count']} reaches" if t2 and t1 and parked else "incomplete")
    hours_cell = f"; {hours:.3f} GPU-h" if hours is not None else ""
    row = (f"| {number} | {datetime.datetime.now().astimezone().isoformat(timespec='seconds')} | {SIMULATOR}; "
           f"{(t2 or {}).get('gpu') or 'n/a'} | {name} | STE L0.3 STE Guard policy in tier 2 without retraining: {head}"
           f"{hours_cell} | {verdict} | records/{name}_record.md |")
    return "\n".join(lines), row


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--run-dir", type=Path, required=True)
    ap.add_argument("--cpu-run", type=Path, required=True)
    ap.add_argument("--number", required=True)
    ap.add_argument("--name")
    ap.add_argument("--out-dir", type=Path, default=ROOT / "records")
    ap.add_argument("--ledger", type=Path, default=ROOT / "records" / "LEDGER.md")
    ap.add_argument("--append-ledger", action="store_true")
    a = ap.parse_args(argv)
    f = a.run_dir / "results.json"
    if not f.is_file():
        print(f"refused: {f} does not exist", file=sys.stderr)
        return 1
    res = json.loads(f.read_text())
    if res.get("smoke"):
        print("refused: a smoke run has no record", file=sys.stderr)
        return 1
    name = a.name or a.run_dir.name
    out = a.out_dir / f"{name}_record.md"
    if out.exists():
        print(f"refused: {out} exists (a record is never overwritten)", file=sys.stderr)
        return 1
    text, row = record_text(a.run_dir, a.cpu_run, res, name, a.number)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text)
    print(f"wrote {out}")
    print(row)
    if a.append_ledger:
        with open(a.ledger, "a") as ledger:
            ledger.write(row + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
