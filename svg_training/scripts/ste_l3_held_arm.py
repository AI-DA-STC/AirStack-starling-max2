#!/usr/bin/env python
"""STE phase L3, slice 2: the held-command arm (design note ste_learning/drafts/L3_SLICE2_DESIGN.md §4; v2 hold rule).
Scoring only, no training.

    ste_l3_held_arm.py --variant <variant> --games <n> --out <folder> [--gates configs/ste_l012/gates.toml]
                       [--hold <ticks>] [--device cpu|cuda]

Why: the mixed route chooses a skill every 0.6 s (12 ticks) and the chosen skill then runs closed loop every tick, a
reaction-speed advantage that pure RL (one command held for 12 ticks) does not have. This arm measures that advantage
for the skills themselves: every script of both teams with its command FROZEN for ``--hold`` ticks (``HeldPlayer``'s
command path, phased from each game's start) against every script of the other team closed loop, on T44's first
``--games`` starts, beside the same script closed loop (the reference cell, T44).

Control (before anything is published): the same play at hold 1 equals the reference cell game for game, every cell
(``exploit.agreement``: outcome, end step, tags, Strike drones left). A failure: controls.json only, exit 6.

Writes <out>/controls.json, results.json (per cell: closed-loop and held wins, the paired counts both / held only /
closed only / neither, the games that differ) and results.md. Exit codes: 0 done; 2 refused (bad arguments, a finished
folder); 6 the control failed. Not under the run contract (no cap or resume): a CPU job, or a short GPU batch launched
by the lead. Training simulator, tier 1: results are "observed in the training simulator"."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
sys.path.insert(0, str(ROOT / "scripts"))

import numpy as np  # noqa: E402

import ste_sweep_l011 as l011  # noqa: E402  (the simulator label, JSON writing)
from svg_training.opponents.scripted import make_strategy  # noqa: E402
from svg_training.ste import atomic, exploit, skills  # noqa: E402

EXIT_DONE, EXIT_REFUSED, EXIT_CONTROL_FAILED = 0, 2, 6
PASS, FAIL = "PASS", "FAIL"
SIDES = ("strike", "guard")
HELD = "held:"                       # the cell name of a held script (so it never clashes with a script's own name)


def other(side: str) -> str:
    return "guard" if side == "strike" else "strike"


def cell_of(side: str, mine: str, opp: str) -> tuple[str, str]:
    return (opp, mine) if side == "strike" else (mine, opp)


def arm_cells(gates) -> list[tuple[str, str, str]]:
    """(side, script, opponent) for every script of both teams against every script of the other team."""
    return [(side, s, o) for side in SIDES for s in skills.team_skills(gates.players, side)
            for o in skills.team_skills(gates.players, other(side))]


def play(gates, variant: str, side: str, n: int, hold: int, device: str, ref) -> tuple[list, dict]:
    """One side's scripts (held ``hold`` ticks) against every script of the other team: (cells, per-game arrays)."""
    cfg = exploit.variant_cfg(gates, variant)
    seed = int(ref.meta["seed"])
    mine = skills.team_skills(gates.players, side)
    # One stateless script object per held script, shared by its cells (each cell wraps its own HeldPlayer, so the
    # hold counters are per cell); seeded without the team offset play_cells adds for named scripts: no script of
    # these lists draws random numbers, so the seed does not change a game (QC N2 of step 4).
    players = {HELD + s: make_strategy(s, side, cfg, n, device, seed) for s in mine}
    cells = [(s, o) for s in mine for o in skills.team_skills(gates.players, other(side))]
    pg = exploit.play_cells(cfg, gates.run["size"], ref, [cell_of(side, HELD + s, o) for s, o in cells], n, device,
                            seed, int(gates.run["ticks_cap"]), hold_ticks=hold, players=players)
    return cells, pg


def input_problems(gates) -> str | None:
    """The L0.12 preflight's input checks (QC S2 of step 4): the game files and the reference file against the gate
    file's pins. The reason to refuse, or None."""
    problems = exploit.game_file_problems(gates)
    if problems:
        return "game file(s) differ from the gate file: " + "; ".join(problems)
    ref_file = exploit.ROOT / gates.reference["file"]
    if not ref_file.is_file():
        return f"the reference file {ref_file} is missing"
    if exploit.sha256_file(ref_file) != gates.reference["sha256"]:
        return (f"the reference file {ref_file} has sha256 {exploit.sha256_file(ref_file)}, the gate file pins "
                f"{gates.reference['sha256']}")
    ref = exploit.load_reference(ref_file)
    if ref.start_sha256 != gates.reference["start_sha256"]:
        return (f"the reference starts have sha256 {ref.start_sha256}, the gate file pins "
                f"{gates.reference['start_sha256']}")
    return None


def wins(outcome, side: str) -> np.ndarray:
    return np.asarray(outcome) == (exploit.STRIKE_WIN if side == "strike" else exploit.GUARD_WIN)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--gates", type=Path, default=exploit.GATES_FILE)
    ap.add_argument("--variant", required=True)
    ap.add_argument("--games", type=int, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--hold", type=int, help="ticks the command is held (default: the gate file's decision_ticks)")
    ap.add_argument("--device", default="cpu")
    a = ap.parse_args(argv)
    try:
        gates = exploit.load_gates(a.gates)
    except (OSError, ValueError) as err:
        print(f"refused: gate file {a.gates}: {err}", file=sys.stderr)
        return EXIT_REFUSED
    problem = input_problems(gates)
    if problem:
        print(f"refused: {problem}", file=sys.stderr)
        return EXIT_REFUSED
    ref = exploit.load_reference(exploit.ROOT / gates.reference["file"])
    hold = int(a.hold if a.hold is not None else gates.trainer["decision_ticks"])
    if a.variant not in gates.variants:
        problem = f"--variant must be one of {list(gates.variants)}, got {a.variant!r}"
    elif not 1 <= a.games <= ref.games:
        problem = f"--games must be 1..{ref.games} (the reference's starts), got {a.games}"
    elif hold < 2:
        problem = f"--hold must be at least 2 ticks (1 is the closed loop), got {hold}"
    elif (a.out / "results.json").is_file():
        problem = f"{a.out} holds a finished arm (results.json): a new run needs a new folder"
    if problem:
        print(f"refused: {problem}", file=sys.stderr)
        return EXIT_REFUSED
    a.out.mkdir(parents=True, exist_ok=True)
    n, rv = a.games, exploit.ref_variant(gates, a.variant)

    def reference(side, s, o):
        return {k: v[:n] for k, v in ref.cell(rv, *cell_of(side, s, o)).items()}

    # the control: hold 1 = the reference, every cell, game for game
    bad = []
    for side in SIDES:
        cells, pg = play(gates, a.variant, side, n, 1, a.device, ref)
        for k, (s, o) in enumerate(cells):
            if exploit.agreement(exploit.slice_cell(pg, k, n), reference(side, s, o))["differ"]:
                bad.append(f"{s} v {o}")
    controls = {"hold1_replay": {"status": FAIL if bad else PASS,
                                 "detail": (f"cells off the reference at hold 1: {bad}" if bad else
                                            f"every cell ({len(arm_cells(gates))}) equals the reference game for game "
                                            f"at hold 1 ({n} games each)")}}
    l011.write_json(a.out / "controls.json", controls)
    if bad:
        print(f"CONTROL FAILED: {controls['hold1_replay']['detail']}; nothing published "
              f"(exit {EXIT_CONTROL_FAILED})", file=sys.stderr)
        return EXIT_CONTROL_FAILED
    # the arm: held `hold` ticks against the same script closed loop (the reference cell)
    rows = []
    for side in SIDES:
        cells, pg = play(gates, a.variant, side, n, hold, a.device, ref)
        for k, (s, o) in enumerate(cells):
            mine, base = exploit.slice_cell(pg, k, n), reference(side, s, o)
            h, c = wins(mine["outcome"], side), wins(base["outcome"], side)
            rows.append({"side": side, "script": s, "opponent": o,
                         "held": {"k": int(h.sum()), "n": n}, "closed": {"k": int(c.sum()), "n": n},
                         "both": int(np.sum(h & c)), "held_only": int(np.sum(h & ~c)),
                         "closed_only": int(np.sum(~h & c)), "neither": int(np.sum(~h & ~c)),
                         "differ": exploit.agreement(mine, base)["differ"]})
    what = ("STE L3 slice 2 held-command arm (scripts/ste_l3_held_arm.py): every script with its command held "
            f"{hold} ticks against the same script closed loop; observed in the training simulator")
    result = {"what": what, "simulator": l011.SIMULATOR, "variant": a.variant, "reference_variant": rv, "games": n,
              "hold_ticks": hold, "device": a.device, "gates_sha256": gates.sha256,
              "reference_sha256": gates.reference["sha256"],
              "controls": controls, "cells": rows, "complete": True}
    l011.write_json(a.out / "results.json", result)
    atomic.write_text(a.out / "results.md", render(result))
    print(f"[held arm] done: {a.out / 'results.md'}", flush=True)
    return EXIT_DONE


def render(result: dict) -> str:
    lines = [f"Simulator: {result['simulator']}", "",
             f"# Held-command arm, {result['variant']}: command held {result['hold_ticks']} ticks v closed loop",
             "", f"{result['games']} games per cell on T44's starts; control: "
                 f"{result['controls']['hold1_replay']['detail']}.",
             "", "| Team | Script | Opponent | Closed loop wins | Held wins | Held only | Closed only | Games that "
                 "differ |",
             "|---|---|---|---|---|---|---|---|"]
    for c in result["cells"]:
        lines.append(f"| {c['side']} | {c['script']} | {c['opponent']} | {c['closed']['k']}/{c['closed']['n']} | "
                     f"{c['held']['k']}/{c['held']['n']} | {c['held_only']} | {c['closed_only']} | {c['differ']} |")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    sys.exit(main())
