#!/usr/bin/env python
"""STE L3-L6 pipeline check, task L6.2: export one trained run (spec ste_learning/drafts/L3_L6_PIPELINE_SPEC.md
section 5). CPU; launched through ``scripts/ste_job.py`` (--task L6.2, --run-dir <out>) so that <out>/exit_code is
written, as the reader (``scripts/ste_l6_read.py``) requires.

    ste_l6_export.py --run-dir <trained run folder> --out <export folder> [--games 8]

Reads the run's own gate file copy (``gates.toml``, its sha256 equal to the run's pin ``gates.sha256`` and to its
``results.json``), its ``results.json`` (complete; the side) and ``agent_final.pt`` through the route's loader
(velocity: ``exploit_train.team_from_modules``; skills: ``skill_team_from_modules`` with the gate file's dispatch,
which refuses other skill lists). Exports with ``ste/export.py`` (``golden_observations`` + ``export_policy``):
one ONNX file per drone slot and ``interface.toml``, which records ``source_run``, ``source_checkpoint``,
``source_checkpoint_sha256`` and the run's ``gates_sha256``. Control ``ctl_team_equals_export`` (controls.json): the
loaded team's own outputs (velocity: mean actions; skills: logits) on the golden observations equal the exported
golden rows within ``export.GOLDEN_TOL``.

Exit codes: 0 done; 2 refused (a finished export folder, an unfinished run, a gate file copy that is not the pin,
a checkpoint the route's loader refuses); 6 the control failed. The reload check in a fresh process is the
reader's (``export.reload_check``). Pipeline check, not for flight; observed in the training simulator."""
from __future__ import annotations

import argparse
import json
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))

import torch  # noqa: E402

from svg_training.ste import exploit, exploit_train, export, skills  # noqa: E402

EXIT_DONE, EXIT_REFUSED, EXIT_CONTROL_FAILED = 0, 2, 6
PASS, FAIL = "PASS", "FAIL"
AGENT, RESULTS, GATES_COPY, PINNED_SHA = "agent_final.pt", "results.json", "gates.toml", "gates.sha256"


def refuse(why: str) -> int:
    print(f"refused: {why}", file=sys.stderr)
    return EXIT_REFUSED


def team_outputs(saved: dict, gates, side: str, obs: torch.Tensor) -> torch.Tensor:
    """The run's team through the route's loader, its outputs on ``obs`` [G, M, 71] (ValueError: the loader refuses)."""
    hidden = list(gates.trainer["hidden"])
    if gates.learner.skills:
        d = skills.two_level_dispatch(gates.learner, gates.players, side, exploit.variant_cfg(gates, "base"),
                                      obs.shape[0], "cpu", 0)
        team = exploit_train.skill_team_from_modules(side, saved, hidden, d, "cpu")
        return team.logits(obs)
    return exploit_train.team_from_modules(side, saved, hidden, "cpu").act(obs)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="ste_l6_export.py", description=__doc__.split("\n\n")[0])
    ap.add_argument("--run-dir", type=Path, required=True, help="the trained run folder (scripts/ste_exploit_l012.py)")
    ap.add_argument("--out", type=Path, required=True, help="the export folder (ste_job.py's --run-dir)")
    ap.add_argument("--games", type=int, default=export.GOLDEN_GAMES, help="golden observation games")
    a = ap.parse_args(argv)
    run, out = a.run_dir.resolve(), a.out
    if (out / "interface.toml").exists() or (out / "controls.json").exists():
        return refuse(f"{out} holds an export already: a new export needs a new folder")
    if a.games < 1:
        return refuse(f"--games {a.games}: at least 1")
    for name in (AGENT, RESULTS, GATES_COPY, PINNED_SHA):
        if not (run / name).is_file():
            return refuse(f"{run} has no {name} (not a finished run folder)")
    res = json.loads((run / RESULTS).read_text())
    if res.get("complete") is not True:
        return refuse(f"{run}/{RESULTS} is not complete")
    try:
        gates = exploit.load_gates(run / GATES_COPY)
    except (OSError, ValueError) as err:
        return refuse(f"{run}/{GATES_COPY}: {err}")
    pinned = (run / PINNED_SHA).read_text().strip()
    if not (gates.sha256 == pinned == res.get("gates_sha256")):
        return refuse(f"{run}: the gate file copy {gates.sha256}, the pin {pinned} and results.json "
                      f"{res.get('gates_sha256')} are not one gate file")
    side = res.get("side")
    if side not in ("guard", "strike"):
        return refuse(f"{run}/{RESULTS}: side {side!r}")
    saved = torch.load(run / AGENT, map_location="cpu", weights_only=False)
    obs = export.golden_observations(gates, side, games=a.games)
    try:
        want = team_outputs(saved, gates, side, obs)
    except ValueError as err:
        return refuse(f"{run}/{AGENT}: the route's loader refuses it: {err}")
    source = {"run": str(run), "checkpoint": str(run / AGENT), "checkpoint_sha256": exploit.sha256_file(run / AGENT)}
    folder = export.export_policy(saved, gates, side, out, obs, source=source)
    meta = tomllib.loads((folder / "interface.toml").read_text())
    got = torch.tensor([row["outputs"] for row in meta["golden"]], dtype=want.dtype)
    diff = float((got - want.detach()).abs().max())
    ok = diff <= export.GOLDEN_TOL
    controls = {"ctl_team_equals_export": {
        "status": PASS if ok else FAIL, "phase": "export",
        "detail": f"the run's team (route loader) against the exported golden rows: max abs diff {diff:.2e} "
                  f"(tolerance {export.GOLDEN_TOL:g}), {got.shape[0]} games x {got.shape[1]} drones"}}
    (out / "controls.json").write_text(json.dumps(controls, indent=1))
    print(f"export {'done' if ok else 'CONTROL FAILED'}: {folder} ({meta['policy_schema']}, {side}; {export.STATUS})")
    return EXIT_DONE if ok else EXIT_CONTROL_FAILED


if __name__ == "__main__":
    sys.exit(main())
