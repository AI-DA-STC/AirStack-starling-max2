"""W3: the Phase 3 gates on the self-play archive pair (Phase 4 plan D2; owner answer 2). Gated, frozen text.

    cd <svg_training>; unset PYTHONPATH; CUDA_VISIBLE_DEVICES= PYTHONPATH=source ~/miniconda3/envs/env_isaaclab/bin/python \
        scripts/nus_phase4_w3.py --write-gates          # first: copies [gates.phase3_converted_policy] verbatim, before any run
        scripts/nus_phase4_w3.py --run --clone <partner clone> --jax-python ~/miniconda3/envs/nus_jax/bin/python \
            --guard-checkpoint <archive entry> --strike-checkpoint <archive entry>

The reference data (``scripts/nus_export_reference.py --out-dir runs/nus_port/w3/reference``) and the converted weights come first. Gate (a): action
parity of each converted actor on the reference observations. Gate (b), both arms named by the frozen text: the *scripted arm* (G19 against the
ported scripted Strike controller, S20 against the ported scripted Guard controller; each converted arm's Strike reach rate inside its JAX arm's
Wilson interval on the same starts) and the *archive arm* (G19 against S20, both converted against both JAX through two action workers; pass rule
written in ``gates.toml`` before the run: the converted pair's rate inside the JAX pair's Wilson interval, on the same starts, all actions
deterministic; the count of games whose outcome differs is recorded). Everything is written under ``runs/nus_port/w3/``; the gate text is read from
``runs/nus_port/w3/gates.toml`` (a verbatim copy) and never changed here. Exit 1 on FAIL. CPU only.
"""
from __future__ import annotations

import argparse
import json
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

W3_DIR = ROOT / "runs" / "nus_port" / "w3"
GATES = W3_DIR / "gates.toml"
SOURCE_GATES = ROOT / "configs" / "nus_port.toml"
SECTION = "[gates.phase3_converted_policy]"
ARCHIVE_RULE = ("# Archive arm pass rule, written before the run (Phase 4 plan D2): G19 (Guard) against S20 (Strike), both teams converted, and both teams JAX through\n"
                "# two action workers (one per team). PASS when the converted pair's Strike reach rate lies inside the Wilson interval (the gate's confidence) of the\n"
                "# JAX pair's rate, on the same shared starts, all actions deterministic. The record also gives the count of games whose outcome differs.\n")


def section_text() -> str:
    """The frozen gate section, line for line, from the committed file."""
    lines = SOURCE_GATES.read_text().splitlines()
    start = lines.index(SECTION)
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("[")), len(lines))
    return "\n".join(lines[start:end]).rstrip() + "\n"


def write_gates() -> int:
    from svg_training.nus.rules import file_sha256
    if GATES.exists():
        print(f"refusing: {GATES} exists (gates are written once, before the run)", file=sys.stderr)
        return 2
    W3_DIR.mkdir(parents=True, exist_ok=True)
    text = ("# W3 gates: a verbatim copy of configs/nus_port.toml [gates.phase3_converted_policy] (frozen, owner-approved 17 November 2026), written before the run.\n"
            f'source_sha256 = "{file_sha256(SOURCE_GATES)}"   # sha256 of configs/nus_port.toml\n'
            'source_note = "unchanged since W2"\n\n' + ARCHIVE_RULE + "\n" + section_text())
    GATES.write_text(text)
    print(f"wrote {GATES} (sha256 {file_sha256(GATES)})")
    return 0


def record_pair(sim, guard_fn, strike_fn, start, deploy, game_index, guard_label, strike_label):
    """One replica game of two policies (callables: team observations [1, T, obs] -> units), positions interpolated to simulator ticks."""
    import numpy as np
    import torch

    from svg_training.core.rewards import GUARD_WIN, STRIKE_WIN
    from svg_training.nus.ladder import interpolate_to_ticks
    from svg_training.nus.replica import ReplicaState
    from svg_training.viz.replay import Recording
    g = sim.guard_count
    state = ReplicaState(pos=start[None].clone(), prev_pos=start[None].clone(), reached=torch.zeros(1), step=torch.zeros(1, dtype=torch.long))
    frames, reached_at = [state.pos[0].clone()], -1
    for _ in range(sim.rules.episode_steps):
        obs = sim.observe(state)
        state = sim.step(state, torch.cat((guard_fn(obs[:, :g]), strike_fn(obs[:, g:])), dim=1))
        frames.append(state.pos[0].clone())
        if state.reached[0] > 0:
            reached_at = len(frames) - 1
            break
    units = torch.stack(frames)
    xy = interpolate_to_ticks(units, deploy.hold_ticks) * deploy.metres_per_unit
    pos_m = torch.cat((xy, torch.full((*xy.shape[:2], 1), deploy.flying_height_m)), dim=-1).numpy()
    closest = float(np.linalg.norm(pos_m[:, :g, None, :2] - pos_m[:, None, g:, :2], axis=-1).min())
    half = float(np.abs(pos_m[:, :, :2]).max()) * (1 + 1 / 2 / 2)
    return Recording(pos_m, np.ones(pos_m.shape[:2], bool), np.zeros(2), sim.rules.area_radius * deploy.metres_per_unit, half,
                     STRIKE_WIN if reached_at >= 0 else GUARD_WIN, pos_m.shape[0] - 1, g, sim.strike_count, "replica",
                     "replica of the partner's 2-D game", guard_label, strike_label, 0, game_index, closest)


def run(args) -> int:
    import numpy as np
    import torch

    from make_replay import FORMATS
    from nus_outcome_parity import JaxPolicy
    from svg_training.nus.actor import NusActor
    from svg_training.nus.apf import NusApf
    from svg_training.nus.deploy import apply_overrides, load_deploy, weights_folder
    from svg_training.nus.outcome import parse_confidence, play_arm, play_pair, verdict
    from svg_training.nus.players import DEPLOY_REF
    from svg_training.nus.replica import NusReplica
    from svg_training.nus.rules import LOCAL_RULES, file_sha256, load_rules
    from svg_training.viz.replay import render_replay

    gate = tomllib.loads(GATES.read_text())["gates"]["phase3_converted_policy"]
    games, confidence = int(gate["games_per_opponent"]), parse_confidence(gate["outcome_parity"])
    limit, rows_needed = float(gate["max_action_error_units_per_step"]), int(gate["observations_per_team"])
    deploy = load_deploy(DEPLOY_REF)
    rules = apply_overrides(load_rules(LOCAL_RULES), deploy)
    sim, apf = NusReplica(rules), NusApf(rules, deploy)
    ref = W3_DIR / "reference"
    starts = torch.from_numpy(np.load(ref / "starts.npz")["pos"])[:games]
    if starts.shape[0] < games:
        raise SystemExit("the W3 starts file holds fewer starts than the gate's games per opponent")
    result: dict = {"games": games, "confidence": confidence, "deploy_ref_sha256": file_sha256(DEPLOY_REF), "gates_sha256": file_sha256(GATES),
                    "starts_sha256": file_sha256(ref / "starts.npz"), "gate_a": {}, "gate_b_scripted": {}, "gate_b_archive": {}}
    actors, checkpoints = {}, {"guard": args.guard_checkpoint, "strike": args.strike_checkpoint}
    ok = True
    for team in ("guard", "strike"):
        actors[team] = NusActor.load(weights_folder(deploy, team), team=team, rules=rules, deploy=deploy)
        data = np.load(ref / f"actions_{team}.npz")
        obs, expected = torch.from_numpy(data["obs"]), torch.from_numpy(data["actions"])
        count = obs.shape[0] * obs.shape[1]
        if count < rows_needed:
            raise SystemExit("the W3 reference holds fewer observation rows than the gate asks for")
        error = float((actors[team].act_units(obs) - expected).abs().max())
        result["gate_a"][team] = {"rows": count, "max_action_error_units": error, "limit": limit, "pass": error <= limit,
                                  "converted_sha256": actors[team].meta["sha256"]}
        ok &= error <= limit
        print(f"[gate a {team}] rows={count} max error={error:.5f} limit={limit}", flush=True)
    jax_policies = {t: JaxPolicy(args.jax_python, args.clone, checkpoints[t], t) for t in ("guard", "strike")}
    try:
        for team in ("guard", "strike"):  # scripted arm
            jax_arm = play_arm(sim, apf, team, starts, jax_policies[team])
            conv_arm = play_arm(sim, apf, team, starts, actors[team].act_units)
            summary = verdict(int(jax_arm.reached.sum()), int(conv_arm.reached.sum()), games, confidence)
            summary["paired_games_with_different_outcome"] = int((jax_arm.reached != conv_arm.reached).sum())
            result["gate_b_scripted"][team] = summary
            ok &= summary["converted_within_jax_interval"]
            print(f"[gate b scripted {team}] JAX {summary['jax_reached']}/{games} converted {summary['converted_reached']}/{games} "
                  f"within={summary['converted_within_jax_interval']} differ={summary['paired_games_with_different_outcome']}", flush=True)
        jax_pair = play_pair(sim, jax_policies["guard"], jax_policies["strike"], starts)  # archive arm
    finally:
        for p in jax_policies.values():
            p.close()
    conv_pair = play_pair(sim, actors["guard"].act_units, actors["strike"].act_units, starts)
    summary = verdict(int(jax_pair.reached.sum()), int(conv_pair.reached.sum()), games, confidence)
    summary["paired_games_with_different_outcome"] = int((jax_pair.reached != conv_pair.reached).sum())
    result["gate_b_archive"] = summary
    ok &= summary["converted_within_jax_interval"]
    print(f"[gate b archive G19 v S20] JAX {summary['jax_reached']}/{games} converted {summary['converted_reached']}/{games} "
          f"within={summary['converted_within_jax_interval']} differ={summary['paired_games_with_different_outcome']}", flush=True)
    result["gate"] = "PASS" if ok else "FAIL"
    out = W3_DIR / "w3_result.json"
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"W3 gate: {result['gate']} (written to {out}, sha256 {file_sha256(out)})", flush=True)
    # videos: two replica games per arm from the converted policies
    video_dir = ROOT / "runs" / "nus_port" / "videos" / "w3"
    video_dir.mkdir(parents=True, exist_ok=True)
    labels = {"guard": "G19 (converted)", "strike": "S20 (converted)"}
    for team, name in (("guard", "G19"), ("strike", "S20")):  # scripted arm: two games (one per team)
        rec = _record_scripted(sim, apf, actors[team], team, starts[0], deploy, 0, labels[team])
        path = render_replay(rec, video_dir / f"scripted_arm_{name}_game0.mp4", playback_label="replica", **FORMATS["mp4"])
        print(f"wrote {path.name}", flush=True)
    for index in (0, 1):  # archive arm
        rec = record_pair(sim, actors["guard"].act_units, actors["strike"].act_units, starts[index], deploy, index, labels["guard"], labels["strike"])
        path = render_replay(rec, video_dir / f"archive_arm_G19_vs_S20_game{index}.mp4", playback_label="replica", **FORMATS["mp4"])
        print(f"wrote {path.name}", flush=True)
    return 0 if ok else 1


def _record_scripted(sim, apf, actor, team, start, deploy, index, label):
    """The scripted-arm clip: the converted policy of ``team`` against the ported scripted controller of the other team (as nus_make_videos does)."""
    from nus_make_videos import record_one
    rec = record_one(sim, apf, actor, team, start, deploy, index)
    rec.guard_name = label if team == "guard" else "scripted controller"
    rec.strike_name = label if team == "strike" else "scripted controller"
    return rec


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--write-gates", action="store_true")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--clone", type=Path)
    parser.add_argument("--jax-python", type=Path)
    parser.add_argument("--guard-checkpoint", type=Path)
    parser.add_argument("--strike-checkpoint", type=Path)
    args = parser.parse_args(argv)
    if args.write_gates:
        return write_gates()
    if args.run:
        if not (GATES.exists() and args.clone and args.jax_python and args.guard_checkpoint and args.strike_checkpoint):
            raise SystemExit("refusing: --run needs the gates file (run --write-gates first) and --clone --jax-python --guard-checkpoint --strike-checkpoint")
        return run(args)
    parser.error("give --write-gates or --run")


if __name__ == "__main__":
    raise SystemExit(main())
