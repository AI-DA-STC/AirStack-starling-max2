#!/usr/bin/env python
"""Draft the record of an L0.2 Tier 2 speed run and its ledger row, from the run folder alone (records/README.md;
STANDARDS section 8; the sections of records/_template_record.md; the pattern of make_ste_l011_record.py, T44).

    make_ste_l02_record.py --run-dir runs/<date>_ste_l02_speed --number T<n> [--name ...] [--out-dir records]
                           [--append-ledger]

Refuses to overwrite a record. Verdict word: INFO when the run finished (exit 0) and every control passed, ABORTED
otherwise; a dry CPU run (tests) is refused. GPU-hours from the shared ledger when launched as a job. Exit 0 written,
1 refused."""
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

SIMULATOR = ("training simulator: tier 1 (fast engine; Starling layer: commander copy, safety filter on every pair, fitted "
             "PX4 response, exploratory) and tier 2 (Isaac Lab rigid-body Starling under the PX4 1.14 cascade copy), the "
             "L0.11 base game")


def _f(v, fmt="{:,.0f}") -> str:
    return "n/a" if v is None else fmt.format(v)


def record_text(run_dir: Path, res: dict, name: str, number: str) -> tuple[str, str]:
    gates = (run_dir / "gates.toml").read_text()
    import tomllib
    g = tomllib.loads(gates)
    code = (run_dir / "exit_code").read_text().strip() if (run_dir / "exit_code").is_file() else None
    finished = res["stopped"] is None and code == "0"
    ok = finished and res["controls_all_pass"] and not res.get("terminal")      # QC L02-6: named controls inside
    verdict = "INFO" if ok else "ABORTED"
    reasons = ([f"controls failed or missing: {', '.join(res['controls_failed'])}"] * bool(res["controls_failed"])
               + [f"stopped: {res['stopped']}"] * bool(res["stopped"]) + [f"exit {code}"] * (code != "0")
               + ["non-finite (terminal)"] * bool(res.get("terminal")))
    why = "" if ok else f" ({'; '.join(reasons) or 'not finished'}; rates void)"
    hours_text, hours = gpu_hours(run_dir)
    code_json = json.loads((run_dir / "code.json").read_text()) if (run_dir / "code.json").is_file() else {}
    rows = res["rows"]
    fit = [r for r in rows if r["status"] == "fit"]
    gpu = next((r.get("gpu") for r in fit if r.get("gpu")), None)
    table = ["| Point | Tier | Size | Games | Status | Scripted reference game-steps/s | Learner rollout game-steps/s | "
             "Training game-steps/s | Training drone-steps/s | PPO update (s) | GPU MiB, process (nvidia-smi) | "
             "torch peak reserved MiB |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        if r["status"] != "fit":
            table.append(f"| {r['id']} | {r['tier']} | {r['size']} | {r['games']:,} | **{r['status'].replace('_', ' ')}** | | | "
                         "| | | | |")
            continue
        lr, nv = r["learner"], r.get("nvidia_smi") or {}
        tr = lr["train_game_steps_per_s"]
        table.append(f"| {r['id']} | {r['tier']} | {r['size']} | {r['games']:,} | fit | {_f(r['reference']['game_steps_per_s'])} "
                     f"| {_f(lr['rollout_game_steps_per_s'])} | {_f(tr)} | {_f(tr * r['drones'] if tr else None)} | "
                     f"{_f(lr['update_s_each'], '{:.1f}')} | {_f(nv.get('process_mib'))} | {_f(r.get('torch_peak_reserved_mib'))} |")
    ratio = []
    by = {(r["tier"], r["size"], r["games"]): r for r in fit}
    for (tier, size, games), r in sorted(by.items()):
        other = by.get((1, size, games))
        if tier == 2 and other:
            a, b = r["learner"]["train_game_steps_per_s"], other["learner"]["train_game_steps_per_s"]
            ratio.append(f"{size} x {games:,}: tier 1 / tier 2 = {b / a:.1f}" if a else f"{size} x {games:,}: n/a")
    agree = next((r["controls"]["physics_agreement"] for r in rows if "physics_agreement" in r.get("controls", {})), None)
    lines = [f"Simulator: {SIMULATOR}. Observed in the training simulator; not a flight result.", "",
             f"# {name} record", "",
             "## Run notes", "",
             "- Say here whether the machine was suspended during the run (a suspend counts against the cap).",
             "- One child process per point; Isaac Sim's start is in each tier 2 point's wall time, not in its rates.", "",
             "## Purpose", "",
             "STE task L0.2 Tier 2 speed in contested play (INFO, PLAN.md section 4; DISCUSSION P3): game-steps per second "
             "on tier 2 and tier 1 with a learner in the loop and both teams playing, per team size and games at once, and "
             "the largest games at once that fits this GPU. Feeds D3 (where to train) at gate G0.", "",
             "## Commit", "", f"`{code_json.get('first', {}).get('commit', 'unknown')}` (diff sha256 "
                             f"`{code_json.get('first', {}).get('diff_sha256', 'unknown')}`); later code changes: "
                             f"{len(code_json.get('changes', []))}.", "",
             "## Config", "", f"- Gate file copy `gates.toml`, sha256 `{res['gates_sha256']}`.",
             f"- Game `{res['game_file']}` (sha256 `{g['run']['game_sha256']}`), tier 2 = the same with "
             "`starling_layer.backend = \"physics\"` (set in code; the file is not edited).",
             f"- Learner: {g['run']['learner_team']} team, skrl IPPO, the T41 recipe ({g['trainer']['decision_ticks']}-tick "
             f"decisions, {g['trainer']['rollouts']} decisions per update, {g['trainer']['learning_epochs']} epochs x "
             f"{g['trainer']['mini_batches']} mini-batches, hidden {g['trainer']['hidden']}), against "
             f"{g['run']['strike_script'] if g['run']['learner_team'] == 'guard' else g['run']['guard_script']}; scripted "
             f"reference {g['run']['guard_script']} v {g['run']['strike_script']} ({g['timing']['reference_decisions']} x "
             f"{g['trainer']['decision_ticks']} ticks); {g['timing']['updates']} update(s) per point after "
             f"{g['timing']['warmup_decisions']} warm-up decisions.", "",
             "## Model parameter set", "", "Tier 1: `params/real_exploratory_v0.toml` (fitted PX4 response, exploratory). "
             "Tier 2: `params/starling_physics_v0.toml` with `params/sim_only_yaw_v0.toml` (SIM-ONLY yaw gains).", "",
             "## Seeds", "", f"Game seed {g['run']['seed']} at every point; scripted players + 101 / + 202; skrl seed = game seed.", "",
             "## Machine", "", f"{fit[0].get('machine') if fit else 'n/a'}; GPU {gpu or 'none'}; torch "
             f"{fit[0].get('torch') if fit else 'n/a'}. Exit code {exit_word(run_dir)}. {hours_text}.", "",
             "## Games at once and steps per second", "", *table, "",
             f"Largest 3v3 games at once that fitted: tier 1 {res['largest_fit']['1']}, tier 2 {res['largest_fit']['2']} "
             f"(on this GPU's memory; the 5090 may hold more). Tier 1 against tier 2, training rate: "
             f"{'; '.join(ratio) or 'n/a'}. Not run: {', '.join(res['not_run']) or 'none'}.", "",
             "## Gates", "", f"Verdict: **{verdict}**{why}. No gate on a speed (INFO). Controls:", "",
             f"- C-1a tier 2 against the PyTorch reference world, bare worlds with the same recorded inputs: "
             + (f"{agree.get('games')} games x {agree.get('drones')} drones x {agree.get('ticks')} ticks, largest gap "
                f"{_f(agree.get('max_gap_m'), '{:.5f}')} m (limit {agree.get('limit_m')} m): "
                f"{'PASS' if agree.get('pass') else 'FAIL'}." if agree else "not run (missing: a failure)."),
             f"- C-2 learner loop, C-3 protected points, required controls present: "
             f"{'PASS' if res['controls_all_pass'] else 'FAIL: ' + ', '.join(res['controls_failed'])}.",
             "- C-1b GAME (INFO, not gated): " + ("; ".join(
                 f"first in/out difference at tick {b.get('first_divergence_tick')}, {b.get('differing_alive_drone_ticks')} "
                 f"drone-ticks differ, largest gap while both in the game {_f(b.get('max_gap_alive_before_divergence_m'), '{:.5f}')} m"
                 for b in (r.get("info", {}).get("game_agreement") for r in rows) if b) or "not recorded") + ".", "",
             "## Videos", "", "2-D clips (STANDARDS section 8): " + ("; ".join(c for r in rows for c in r.get("clips", []))
                                                                     or "none recorded (say why)")
             + ". The height panel arrives with L0.12's replay change; 3-D Isaac Lab clips: VID-1, pending.", "",
             "## Limits", "",
             "- One update per point: the update time is one sample. The learner starts at the zero-mean policy (the "
             "standing-still Guard team); a trained team may change game length and filter work.",
             "- Rates on this machine only; the 5090 rates differ.", ""]
    best = max((r for r in fit if r["tier"] == 2 and r["size"] == "3v3"), key=lambda r: r["games"], default=None)
    if ok:
        what = (f"{len(fit)} points fit; tier 2 3v3 at {best['games']:,} games: "
                f"{_f(best['learner']['train_game_steps_per_s'])} game-steps/s training" if best else "no tier 2 point")
        what += f"; largest 3v3 fit tier 1 {res['largest_fit']['1']}, tier 2 {res['largest_fit']['2']}"
    else:                                         # LEAD CALL QC L02-7: an ABORTED row never leads with a rate
        what = f"ABORTED{why}"
    hours_cell = f"; {hours:.3f} GPU-h" if hours is not None else ""
    row = (f"| {number} | {datetime.datetime.now().astimezone().isoformat(timespec='seconds')} | {SIMULATOR}; {gpu or 'CPU'} "
           f"| {name} | STE L0.2 Tier 2 speed in contested play: {what}{hours_cell} | {verdict} | records/{name}_record.md |")
    return "\n".join(lines), row


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--run-dir", type=Path, required=True)
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
    if res.get("dry_cpu"):
        print("refused: a dry CPU run (tests) has no record", file=sys.stderr)
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
