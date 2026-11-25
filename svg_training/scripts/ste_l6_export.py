#!/usr/bin/env python
"""STE L3-L6 pipeline check, task L6.2: export one trained run (spec ste_learning/drafts/L3_L6_PIPELINE_SPEC.md
section 5). CPU; launched through ``scripts/ste_job.py`` (--task L6.2, --run-dir <out>) so that <out>/exit_code is
written, as the reader (``scripts/ste_l6_read.py``) requires.

    ste_l6_export.py --run-dir <trained run folder> --out <export folder> [--games 8]
    ste_l6_export.py --skill-net <skill network file> --side guard|strike --out <export folder> [--games 8]

Reads the run's own gate file copy (``gates.toml``, its sha256 equal to the run's pin ``gates.sha256`` and to its
``results.json``), its ``results.json`` (complete; the side) and ``agent_final.pt`` through the route's loader
(velocity: ``exploit_train.team_from_modules``; skills: ``skill_team_from_modules`` with the gate file's dispatch,
which refuses other skill lists). Exports with ``ste/export.py`` (``golden_observations`` + ``export_policy``):
one ONNX file per drone slot and ``interface.toml``, which records ``source_run``, ``source_checkpoint``,
``source_checkpoint_sha256`` and the run's ``gates_sha256``. The variant is the run's own (``results.json``
``variant``, "base" when absent; route 3, task LS1-M3-T1): its game gives the golden observations and the dispatch, and
``interface.toml`` records its game and ``train_seed`` (and names it when it is not "base"). Control ``ctl_team_equals_export`` (controls.json): the
loaded team's own outputs (velocity: mean actions; skills: logits) on the golden observations equal the exported
golden rows within ``export.within`` (absolute + relative).

``--skill-net`` (route 3, task LS1-M3-T4, job LS1.3; ``--run-dir`` and ``--skill-net`` are mutually exclusive, one is
required): a stand-alone skill network folder (``export.export_skill_net``, schema ``ste-check-skillnet-0``). The game
file and the team sizes are the network's own (its meta, OP-26): the game file's sha256 on disk must equal the meta's,
and the network must pass ``skill_net.net_problems`` against that game (team = ``--side``, its own skill list and team
size, the scripts' sha256 today, the game constants). Golden observations: ``export.golden_observations_cfg`` on that
game. Controls (controls.json): ``ctl_net_equals_export`` (the torch network loaded from the file, every code for every
drone, against the exported golden rows within ``export.within``) and ``ctl_reload_fresh_process``
(``ste_l6_read.reload_in_a_fresh_process``: ``export.reload_check`` in a new process, OP-25).

Exit codes: 0 done; 2 refused (a finished export folder, an unfinished run, a gate file copy that is not the pin,
a checkpoint the route's loader refuses, a variant the gate file copy does not hold; for ``--skill-net``: no ``--side``
or the network's team is not it, a missing or unreadable network file, its game file changed, a network
``net_problems`` refuses, the reload check cannot run in this environment); 6 a control failed. For ``--run-dir`` the
reload check in a fresh process is the reader's (``export.reload_check``). Pipeline check, not for flight; observed in
the training simulator."""
from __future__ import annotations

import argparse
import json
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))

import torch  # noqa: E402

from svg_training.ste import exploit, exploit_train, export, skill_net, skills  # noqa: E402

EXIT_DONE, EXIT_REFUSED, EXIT_CONTROL_FAILED = 0, 2, 6
PASS, FAIL = "PASS", "FAIL"
AGENT, RESULTS, GATES_COPY, PINNED_SHA = "agent_final.pt", "results.json", "gates.toml", "gates.sha256"


def refuse(why: str) -> int:
    print(f"refused: {why}", file=sys.stderr)
    return EXIT_REFUSED


def team_outputs(saved: dict, gates, side: str, obs: torch.Tensor, variant: str = "base") -> torch.Tensor:
    """The run's team through the route's loader, its outputs on ``obs`` [G, M, 71] (ValueError: the loader refuses,
    or ``variant`` is not in the gate file)."""
    hidden = list(gates.trainer["hidden"])
    export.check_variant(gates, variant)
    if gates.learner.skills:
        d = skills.two_level_dispatch(gates.learner, gates.players, side, exploit.variant_cfg(gates, variant),
                                      obs.shape[0], "cpu", 0)
        team = exploit_train.skill_team_from_modules(side, saved, hidden, d, "cpu")
        return team.logits(obs)
    return exploit_train.team_from_modules(side, saved, hidden, "cpu").act(obs)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="ste_l6_export.py", description=__doc__.split("\n\n")[0])
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--run-dir", type=Path, help="the trained run folder (scripts/ste_exploit_l012.py)")
    mode.add_argument("--skill-net", type=Path, help="a skill network file (route 3, job LS1.3): a stand-alone export")
    ap.add_argument("--side", choices=skill_net.TEAMS, help="the skill network's team (with --skill-net only)")
    ap.add_argument("--out", type=Path, required=True, help="the export folder (ste_job.py's --run-dir)")
    ap.add_argument("--games", type=int, default=export.GOLDEN_GAMES, help="golden observation games")
    a = ap.parse_args(argv)
    out = a.out
    if (out / "interface.toml").exists() or (out / "controls.json").exists():
        return refuse(f"{out} holds an export already: a new export needs a new folder")
    if a.games < 1:
        return refuse(f"--games {a.games}: at least 1")
    if a.skill_net is not None:
        return export_skill_net(a.skill_net.resolve(), a.side, out, a.games)
    if a.side is not None:
        return refuse("--side is for --skill-net only (a run's side is its results.json's)")
    run = a.run_dir.resolve()
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
    variant = res.get("variant", "base")
    if variant not in gates.variants:
        return refuse(f"{run}/{RESULTS}: variant {variant!r} not in the gate file copy (its variants: "
                      f"{sorted(gates.variants)})")
    saved = torch.load(run / AGENT, map_location="cpu", weights_only=False)
    obs = export.golden_observations(gates, side, games=a.games, variant=variant)
    try:
        want = team_outputs(saved, gates, side, obs, variant=variant)
    except ValueError as err:
        return refuse(f"{run}/{AGENT}: the route's loader refuses it: {err}")
    source = {"run": str(run), "checkpoint": str(run / AGENT), "checkpoint_sha256": exploit.sha256_file(run / AGENT)}
    folder = export.export_policy(saved, gates, side, out, obs, source=source, variant=variant)
    meta = tomllib.loads((folder / "interface.toml").read_text())
    got = torch.tensor([row["outputs"] for row in meta["golden"]], dtype=want.dtype)
    ok, diff, scale = export.within(got.numpy(), want.detach().numpy())
    controls = {"ctl_team_equals_export": {
        "status": PASS if ok else FAIL, "phase": "export",
        "detail": f"the run's team (route loader) against the exported golden rows: max abs diff {diff:.2e} "
                  f"(tolerance {export.tolerance_text()}, outputs up to {scale:.3g}), {got.shape[0]} games x "
                  f"{got.shape[1]} drones"}}
    (out / "controls.json").write_text(json.dumps(controls, indent=1))
    print(f"export {'done' if ok else 'CONTROL FAILED'}: {folder} ({meta['policy_schema']}, {side}; {export.STATUS})")
    return EXIT_DONE if ok else EXIT_CONTROL_FAILED


def export_skill_net(path: Path, side: str | None, out: Path, games: int) -> int:
    """The ``--skill-net`` branch (module docstring): preflight, export, the two controls. Returns the exit code."""
    if side is None:
        return refuse("--skill-net needs --side guard|strike (the network's team)")
    if not path.is_file():
        return refuse(f"{path}: no skill network file")
    try:
        meta = skill_net.read_skill_net_meta(path)
    except Exception as err:            # noqa: BLE001 (any unreadable file is one refusal, as skill_net.net_problems)
        return refuse(f"{path}: cannot be read as a skill network ({type(err).__name__}: {err})")
    if not isinstance(meta, dict) or meta.get("format") != skill_net.FORMAT:
        return refuse(f"{path}: format {meta.get('format') if isinstance(meta, dict) else None!r}, expected "
                      f"{skill_net.FORMAT!r}")
    if meta["team"] != side:
        return refuse(f"{path}: the network is the {meta['team']} team's, not --side {side}")
    game_path = ROOT / meta["game_file"]
    if not game_path.is_file():
        return refuse(f"{path}: its game file {meta['game_file']} is missing")
    game_sha = exploit.sha256_file(game_path)
    cfg = exploit.load_game_cfg_file(game_path)
    team_size = int(meta["guards"] if side == "guard" else meta["strikes"])
    sha = exploit.sha256_file(path)
    problems = skill_net.net_problems(path, sha256=sha, team=side, skills=list(meta["skills"]), team_size=team_size,
                                      cfg=cfg, game_file=meta["game_file"], game_sha256=game_sha)
    if problems:
        return refuse("; ".join(problems) + f" (the game file {meta['game_file']} on disk has sha256 {game_sha})")
    try:
        net, meta = skill_net.load_skill_net(path, team=side, skills=list(meta["skills"]), cfg=cfg, device="cpu",
                                             team_size=team_size, file_sha256=sha, game_sha256=game_sha)
        obs = export.golden_observations_cfg(cfg, int(meta["guards"]), int(meta["strikes"]), side, games,
                                             export.GOLDEN_SEED)
        source = {"checkpoint": export.repo_relative(path), "checkpoint_sha256": sha}
        folder = export.export_skill_net(net, meta, side, out, obs, source=source, net_file=path)
    except ValueError as err:
        return refuse(f"{path}: {err}")
    data = tomllib.loads((folder / "interface.toml").read_text())
    got = torch.tensor([row["commands"] for row in data["skill_net_golden"]], dtype=torch.float32)  # [G, M, K, 4]
    want = skill_net.all_codes(net, obs)
    ok_net, diff, scale = export.within(got.numpy(), want.detach().numpy())
    import ste_l6_read as reader        # imported here (this script's folder): --run-dir imports what it did before
    try:
        reload = reader.reload_in_a_fresh_process(folder)
    except reader.Refused as err:       # the export extra is missing in the new process: the environment, exit 2
        return refuse(f"{folder}: {err}")
    ok_reload = bool(reload.get("ok"))
    controls = {
        "ctl_net_equals_export": {
            "status": PASS if ok_net else FAIL, "phase": "export",
            "detail": f"the skill network loaded from {export.repo_relative(path)} (torch, every code for every drone) "
                      f"against the exported golden rows: max abs diff {diff:.2e} (tolerance "
                      f"{export.tolerance_text()}, commands up to {scale:.3g}), {got.shape[0]} games x "
                      f"{got.shape[1]} drones x {got.shape[2]} codes"},
        "ctl_reload_fresh_process": {
            "status": PASS if ok_reload else FAIL, "phase": "export",
            "detail": (f"export.reload_check in a new process: {reload.get('skill_net_golden_rows')} rows on "
                       f"{reload.get('runtimes')}, max abs diff {reload.get('skill_net_max_abs_diff')}" if ok_reload
                       else f"export.reload_check in a new process refused the folder: {reload.get('error')}")}}
    (out / "controls.json").write_text(json.dumps(controls, indent=1))
    ok = ok_net and ok_reload
    print(f"skill network export {'done' if ok else 'CONTROL FAILED'}: {folder} ({export.SKILL_NET_SCHEMA}, {side}; "
          f"{export.STATUS})")
    return EXIT_DONE if ok else EXIT_CONTROL_FAILED


if __name__ == "__main__":
    sys.exit(main())
