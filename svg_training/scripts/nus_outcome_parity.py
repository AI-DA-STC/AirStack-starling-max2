"""Outcome parity run (gate b of Phase 3). Run in the pipeline environment, CPU only:

    cd <svg_training>; unset PYTHONPATH; CUDA_VISIBLE_DEVICES= PYTHONPATH=source ~/miniconda3/envs/env_isaaclab/bin/python \
        scripts/nus_outcome_parity.py --clone <partner clone> --jax-python ~/miniconda3/envs/nus_jax/bin/python \
        --guard-checkpoint <folder> --strike-checkpoint <folder> [--tag <name>]

For each team, two arms play the same ``games_per_opponent`` starts (the partner's own random starts, exported by
scripts/nus_export_reference.py) in our replica, the team against the ported scripted controller of the other team, all actions
deterministic: the JAX arm (the partner's policy, queried step by step through scripts/nus_jax_policy_server.py in ``nus_jax``) and the
converted arm (our PyTorch actor). Score: the rate of games in which the Strike team reaches the zone, with Wilson intervals at the
confidence named by the gate text; the gate passes when the converted rate lies inside the JAX arm's interval. The gate itself is read
from configs/nus_port.toml and never changed here. Result file: runs/nus_port/<tag>.json (rates and counts, no rule value); exit 1 on FAIL.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402
import torch  # noqa: E402

from nus_jax_common import read_frame, write_frame  # noqa: E402
from svg_training.nus.actor import NusActor  # noqa: E402
from svg_training.nus.apf import NusApf  # noqa: E402
from svg_training.nus.deploy import LOCAL_DEPLOY, REFERENCE_DIR, apply_overrides, load_deploy  # noqa: E402
from svg_training.nus.outcome import parse_confidence, play_arm, verdict  # noqa: E402
from svg_training.nus.replica import NusReplica  # noqa: E402
from svg_training.nus.rules import LOCAL_RULES, file_sha256, load_rules  # noqa: E402

GATES = ROOT / "configs" / "nus_port.toml"


class JaxPolicy:
    """The partner's actor in a child process; ``__call__`` maps team observations to actions, one round trip per call."""

    def __init__(self, jax_python: Path, clone: Path, checkpoint: Path, team: str):
        env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
        env |= {"PYTHONNOUSERSITE": "1", "JAX_PLATFORMS": "cpu", "WANDB_MODE": "disabled", "CUDA_VISIBLE_DEVICES": ""}
        self.process = subprocess.Popen(
            [str(jax_python), str(Path(__file__).resolve().parent / "nus_jax_policy_server.py"), "--clone", str(clone),
             "--checkpoint", str(checkpoint), "--team", team], stdin=subprocess.PIPE, stdout=subprocess.PIPE, env=env)

    def __call__(self, obs: torch.Tensor) -> torch.Tensor:
        write_frame(self.process.stdin, obs.cpu().numpy().astype(np.float32))
        answer = read_frame(self.process.stdout)
        if answer is None:
            raise RuntimeError("the JAX action worker ended early")
        return torch.from_numpy(answer).to(obs.device)

    def close(self) -> None:
        self.process.stdin.close()
        self.process.wait()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clone", required=True, type=Path)
    parser.add_argument("--jax-python", required=True, type=Path)
    parser.add_argument("--guard-checkpoint", required=True, type=Path)
    parser.add_argument("--strike-checkpoint", required=True, type=Path)
    parser.add_argument("--tag", default="outcome_parity")
    args = parser.parse_args(argv)
    gate = tomllib.loads(GATES.read_text())["gates"]["phase3_converted_policy"]
    games, confidence = int(gate["games_per_opponent"]), parse_confidence(gate["outcome_parity"])
    deploy = load_deploy(LOCAL_DEPLOY)
    rules = apply_overrides(load_rules(LOCAL_RULES), deploy)
    sim, apf = NusReplica(rules), NusApf(rules, deploy)
    starts = torch.from_numpy(np.load(REFERENCE_DIR / "starts.npz")["pos"])
    if starts.shape[0] < games:
        raise SystemExit("the starts file holds fewer starts than the gate's games per opponent")
    starts = starts[:games]
    result: dict = {"games": games, "confidence": confidence, "starts_sha256": file_sha256(REFERENCE_DIR / "starts.npz"), "teams": {}}
    ok = True
    for team, checkpoint in (("guard", args.guard_checkpoint), ("strike", args.strike_checkpoint)):
        actor = NusActor.load(checkpoint, team=team, rules=rules, deploy=deploy)
        jax_policy = JaxPolicy(args.jax_python, args.clone, checkpoint, team)
        try:
            jax_arm = play_arm(sim, apf, team, starts, jax_policy)
        finally:
            jax_policy.close()
        converted_arm = play_arm(sim, apf, team, starts, actor.act_units)
        summary = verdict(int(jax_arm.reached.sum()), int(converted_arm.reached.sum()), games, confidence)
        summary["paired_games_with_different_outcome"] = int((jax_arm.reached != converted_arm.reached).sum())
        summary["max_final_position_gap_units"] = float((jax_arm.final_pos - converted_arm.final_pos).abs().max())
        summary["checkpoint_sha256"] = actor.meta["sha256"]
        result["teams"][team] = summary
        ok &= summary["converted_within_jax_interval"]
        print(f"[{team}] JAX arm {summary['jax_rate']:.4f} {summary['jax_interval']}  converted {summary['converted_rate']:.4f} "
              f"{summary['converted_interval']}  within JAX interval: {summary['converted_within_jax_interval']}  "
              f"differing games: {summary['paired_games_with_different_outcome']}")
    result["gate"] = "PASS" if ok else "FAIL"
    out = ROOT / "runs" / "nus_port" / f"{args.tag}.json"
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"gate b: {result['gate']}  (written to {out}, sha256 {file_sha256(out)})")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
