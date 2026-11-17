"""Render replica games of the converted policy (two per team by default) into runs/nus_port/videos/. Pipeline environment, CPU:

    cd <svg_training>; unset PYTHONPATH; CUDA_VISIBLE_DEVICES= PYTHONPATH=source ~/miniconda3/envs/env_isaaclab/bin/python \
        scripts/nus_make_videos.py [--games 2]

The converted policy plays its team against the ported scripted controller of the other team in our replica of the partner's 2-D game,
from the first starts of the partner's start file (scripts/nus_export_reference.py), all deterministic. Positions are in metres (the deploy
file's scale); the frames between two game steps are linear interpolations (one frame per simulator tick), so the picture shows the replica
game, not a drone model. Uses the existing renderer (``viz/replay.py``); output sizes and speed come from ``make_replay.FORMATS``.
The videos hold partner values (geometry) and stay under runs/ (git-ignored). Training simulator, replica, not a flight.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402
import torch  # noqa: E402

from make_replay import FORMATS  # noqa: E402
from svg_training.core.rewards import GUARD_WIN, STRIKE_WIN  # noqa: E402
from svg_training.nus.actor import NusActor  # noqa: E402
from svg_training.nus.apf import NusApf  # noqa: E402
from svg_training.nus.deploy import LOCAL_DEPLOY, REFERENCE_DIR, apply_overrides, load_deploy, weights_folder  # noqa: E402
from svg_training.nus.outputs import require_under_runs  # noqa: E402
from svg_training.nus.replica import NusReplica, ReplicaState  # noqa: E402
from svg_training.nus.rules import LOCAL_RULES, file_sha256, load_rules  # noqa: E402
from svg_training.viz.replay import Recording, render_replay  # noqa: E402

VIDEO_DIR = ROOT / "runs" / "nus_port" / "videos"
MARGIN = 1 + 1 / 2 / 2  # drawn arena half-side over the largest position, so nothing sits on the frame


@torch.no_grad()
def record_one(sim: NusReplica, apf: NusApf, actor: NusActor, team: str, start: torch.Tensor, deploy, game_index: int) -> Recording:
    guards = sim.guard_count
    other = "strike" if team == "guard" else "guard"
    state = ReplicaState(pos=start[None].clone(), prev_pos=start[None].clone(), reached=torch.zeros(1), step=torch.zeros(1, dtype=torch.long))
    frames = [state.pos[0].clone()]
    reached_at = -1
    for _ in range(sim.rules.episode_steps):
        observation = sim.observe(state)
        mine = actor.act_units(observation[:, :guards] if team == "guard" else observation[:, guards:])
        theirs = apf.actions(other, state.pos)
        new = sim.step(state, torch.cat((mine, theirs) if team == "guard" else (theirs, mine), dim=1))
        for sub in range(1, deploy.hold_ticks + 1):
            frames.append((state.pos + (new.pos - state.pos) * (sub / deploy.hold_ticks))[0].clone())
        state = new
        if state.reached[0] > 0:
            reached_at = len(frames) - 1
            break
    units = torch.stack(frames)  # [T+1, M, 2]
    height = torch.full((*units.shape[:2], 1), deploy.flying_height_m)
    pos_m = torch.cat((units * deploy.metres_per_unit, height), dim=-1).numpy()
    guards_m, strikes_m = pos_m[:, :guards, :2], pos_m[:, guards:, :2]
    closest = float(np.linalg.norm(guards_m[:, :, None] - strikes_m[:, None], axis=-1).min())
    end = reached_at if reached_at >= 0 else pos_m.shape[0] - 1
    half = float(np.abs(pos_m[:, :, :2]).max()) * MARGIN
    return Recording(pos_m[: end + 1], np.ones(pos_m[: end + 1].shape[:2], bool), np.zeros(2), sim.rules.area_radius * deploy.metres_per_unit,
                     half, STRIKE_WIN if reached_at >= 0 else GUARD_WIN, end, guards, sim.strike_count, "replica", "replica of the partner's 2-D game",
                     "converted policy" if team == "guard" else "scripted controller", "converted policy" if team == "strike" else "scripted controller",
                     0, game_index, closest)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", type=int, required=True, help="games per team")
    args = parser.parse_args(argv)
    deploy = load_deploy(LOCAL_DEPLOY)
    rules = apply_overrides(load_rules(LOCAL_RULES), deploy)
    sim, apf = NusReplica(rules), NusApf(rules, deploy)
    starts = torch.from_numpy(np.load(REFERENCE_DIR / "starts.npz")["pos"])
    out_dir = require_under_runs(VIDEO_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    kind = "mp4"
    for team in ("guard", "strike"):
        actor = NusActor.load(weights_folder(deploy, team), team=team, rules=rules, deploy=deploy)
        for index in range(args.games):
            recording = record_one(sim, apf, actor, team, starts[index], deploy, index)
            path = render_replay(recording, out_dir / f"{team}_game{index}.{kind}", playback_label="replica", **FORMATS[kind])
            print(f"wrote {path.name} ({'Strike team reached the zone' if recording.outcome == STRIKE_WIN else 'Guard team held the zone'}), sha256 {file_sha256(path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
