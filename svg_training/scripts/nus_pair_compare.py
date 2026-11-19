"""One Guard policy against one Strike policy, three ways on the same starts, and same-start videos. Run in the pipeline environment, CPU only:

    cd <svg_training>; unset PYTHONPATH; CUDA_VISIBLE_DEVICES= PYTHONPATH=source ~/miniconda3/envs/env_isaaclab/bin/python \
        scripts/nus_pair_compare.py --name g19_vs_p3s --jax-game runs/nus_port/pairs/g19_vs_p3s_jax_game.npz \
        --guard-weights runs/nus_port/weights/ref_s2_g19_guard --strike-weights runs/nus_port/weights/hangar_strike_fixed_apf \
        --guard-label G19 --strike-label P3S [--clone <NUS clone> --jax-python ~/miniconda3/envs/nus_jax/bin/python \
        --guard-checkpoint <folder> --strike-checkpoint <folder>] [--videos 0 1]

The three arms, all deterministic, on the starts of ``--jax-game`` (written by ``scripts/nus_pair_jax_game.py``):
  1. NUS's JAX game: NUS's environment and NUS's JAX actors (read from the ``--jax-game`` file);
  2. the Copy of NUS 2-D game (PyTorch) with NUS's JAX actors, queried step by step through action workers (only with ``--clone``);
  3. the Copy of NUS 2-D game (PyTorch) with the converted PyTorch actors.
Counts of Strike reaches, Wilson intervals at the confidence the Phase 3 gate names, games whose outcome differs from arm 1, and the largest position gap to arm 1 (units,
over the steps both games are still running). Videos: for each ``--videos`` game index, the same start in arm 1 and arm 3, each to its
own end, then joined side by side (MP4 and a GIF that plays on GitHub). INFO only: no gate. Results under runs/nus_port/pairs/.
"""
from __future__ import annotations

import argparse
import json
import inspect
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402
import torch  # noqa: E402

OUT_DIR = ROOT / "runs" / "nus_port" / "pairs"


GATES = ROOT / "configs" / "nus_port.toml"


def gate_confidence() -> float:
    """The confidence level the Phase 3 gate text names (as scripts/nus_outcome_parity.py reads it); no level is written here."""
    from svg_training.nus.outcome import parse_confidence
    return parse_confidence(tomllib.loads(GATES.read_text())["gates"]["phase3_converted_policy"]["outcome_parity"])


def copy_trajectories(sim, guard_fn, strike_fn, starts):
    """Arm 3 (or 2) with every step's positions kept: [N, T+1, M, 2] units, and the first reach step (-1: never)."""
    from svg_training.nus.replica import ReplicaState
    g, n = sim.guard_count, starts.shape[0]
    state = ReplicaState(pos=starts.clone(), prev_pos=starts.clone(), reached=torch.zeros(n, dtype=sim.dtype),
                         step=torch.zeros(n, dtype=torch.long))
    frames, first = [starts.clone()], torch.full((n,), -1, dtype=torch.long)
    for step in range(sim.rules.episode_steps):
        obs = sim.observe(state)
        state = sim.step(state, torch.cat((guard_fn(obs[:, :g]), strike_fn(obs[:, g:])), dim=1))
        frames.append(state.pos.clone())
        first = torch.where((first < 0) & (state.reached > 0), torch.full_like(first, step + 1), first)
    return torch.stack(frames, dim=1).numpy(), first.numpy()


def recording(units: np.ndarray, reached_at: int, sim, deploy, index: int, guard_label: str, strike_label: str, game_label: str,
              half: float | None = None):
    """A replay of one game (units [T+1, M, 2]) cut at its own end, positions interpolated to simulator ticks (as nus_phase4_w3.record_pair)."""
    from svg_training.core.rewards import GUARD_WIN, STRIKE_WIN
    from svg_training.nus.ladder import interpolate_to_ticks
    from svg_training.viz.replay import Recording
    g = sim.guard_count
    end = reached_at if reached_at >= 0 else units.shape[0] - 1
    xy = interpolate_to_ticks(torch.from_numpy(units[: end + 1]).double(), deploy.hold_ticks) * deploy.metres_per_unit
    pos_m = torch.cat((xy, torch.full((*xy.shape[:2], 1), deploy.flying_height_m, dtype=xy.dtype)), dim=-1).numpy()
    closest = float(np.linalg.norm(pos_m[:, :g, None, :2] - pos_m[:, None, g:, :2], axis=-1).min())
    half = half or float(np.abs(pos_m[:, :, :2]).max()) * (1 + 1 / 2 / 2)
    return Recording(pos_m, np.ones(pos_m.shape[:2], bool), np.zeros(2), sim.rules.area_radius * deploy.metres_per_unit, half,
                     STRIKE_WIN if reached_at >= 0 else GUARD_WIN, pos_m.shape[0] - 1, g, sim.strike_count, "NUS hangar",
                     game_label, guard_label, strike_label, 0, index, closest)


def side_by_side(left: Path, right: Path, out_mp4: Path, out_gif: Path, d: float) -> None:
    """Join two MP4s left|right (the shorter one holds its last frame), then a 640-px-wide GIF of the joined clip."""
    import imageio_ffmpeg
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    joined = ("[0:v]tpad=stop_mode=clone:stop_duration=60[a];[1:v]tpad=stop_mode=clone:stop_duration=60[b];"
              "[a][b]hstack=inputs=2,trim=duration={d}[v]")
    subprocess.run([ff, "-y", "-loglevel", "error", "-i", str(left), "-i", str(right), "-filter_complex", joined.format(d=d), "-map", "[v]",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "23", str(out_mp4)], check=True)
    palette = "fps=10,scale=960:-2:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=96[p];[s1][p]paletteuse=dither=bayer"
    subprocess.run([ff, "-y", "-loglevel", "error", "-i", str(out_mp4), "-filter_complex", palette, "-loop", "0", str(out_gif)], check=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--name", required=True)
    parser.add_argument("--jax-game", required=True, type=Path)
    parser.add_argument("--guard-weights", required=True, type=Path)
    parser.add_argument("--strike-weights", required=True, type=Path)
    parser.add_argument("--guard-label", required=True)
    parser.add_argument("--strike-label", required=True)
    parser.add_argument("--clone", type=Path)
    parser.add_argument("--jax-python", type=Path)
    parser.add_argument("--guard-checkpoint", type=Path)
    parser.add_argument("--strike-checkpoint", type=Path)
    parser.add_argument("--videos", type=int, nargs="*", default=[0])
    args = parser.parse_args(argv)

    from make_replay import FORMATS
    from svg_training.nus.actor import NusActor
    from svg_training.nus.deploy import apply_overrides, load_deploy
    from svg_training.nus.players import DEPLOY_REF
    from svg_training.nus.replica import NusReplica
    from svg_training.nus.rules import LOCAL_RULES, file_sha256, load_rules
    from svg_training.viz.replay import render_replay

    deploy = load_deploy(DEPLOY_REF)
    rules = apply_overrides(load_rules(LOCAL_RULES), deploy)
    sim = NusReplica(rules)
    jax_game = np.load(args.jax_game)
    j_pos, j_at = jax_game["pos"], jax_game["reached_at"]
    starts = torch.from_numpy(j_pos[:, 0].astype(np.float32))
    games = starts.shape[0]
    guard = NusActor.load(args.guard_weights, team="guard", rules=rules, deploy=deploy)
    strike = NusActor.load(args.strike_weights, team="strike", rules=rules, deploy=deploy)
    arms = {"nus_jax_game": (j_pos, j_at)}
    if args.clone:
        from nus_outcome_parity import JaxPolicy
        workers = {t: JaxPolicy(args.jax_python, args.clone, c, t) for t, c in (("guard", args.guard_checkpoint), ("strike", args.strike_checkpoint))}
        try:
            arms["copy_jax_actors"] = copy_trajectories(sim, workers["guard"], workers["strike"], starts)
        finally:
            for w in workers.values():
                w.close()
    arms["copy_converted"] = copy_trajectories(sim, guard.act_units, strike.act_units, starts)
    ref_reached = j_at >= 0
    result = {"name": args.name, "games": games, "jax_game_file_sha256": file_sha256(args.jax_game),
              "guard_converted_sha256": guard.meta["sha256"], "strike_converted_sha256": strike.meta["sha256"], "arms": {}}
    from svg_training.nus.outcome import wilson_interval
    confidence = gate_confidence()
    result["confidence"] = confidence
    for arm, (pos, at) in arms.items():
        reached = at >= 0
        interval = list(wilson_interval(int(reached.sum()), games, confidence))
        steps = min(pos.shape[1], j_pos.shape[1])
        gap = np.abs(pos[:, :steps] - j_pos[:, :steps])
        live = np.arange(steps)[None, :] <= np.minimum(np.where(at >= 0, at, steps - 1), np.where(j_at >= 0, j_at, steps - 1))[:, None]
        result["arms"][arm] = {"strike_reaches": int(reached.sum()), "wilson_interval": interval,
                               "games_differing_from_nus_jax_game": int((reached != ref_reached).sum()),
                               "max_position_gap_units_while_both_run": float(gap.reshape(*gap.shape[:2], -1).max(axis=-1)[live].max())}
        print(f"[{arm}] Strike reaches {int(reached.sum())}/{games} [{interval[0]:.4f}, {interval[1]:.4f}]  differ from NUS JAX game: "
              f"{result['arms'][arm]['games_differing_from_nus_jax_game']}  max gap {result['arms'][arm]['max_position_gap_units_while_both_run']:.2e}",
              flush=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{args.name}_compare.json"
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"wrote {out} sha256 {file_sha256(out)}", flush=True)
    c_pos, c_at = arms["copy_converted"]
    video_dir = OUT_DIR / "videos"
    video_dir.mkdir(parents=True, exist_ok=True)
    for i in args.videos:
        left = recording(j_pos[i], int(j_at[i]), sim, deploy, i, f"{args.guard_label} (NUS JAX)", f"{args.strike_label} (NUS JAX)", "NUS 2-D game (JAX)")
        right = recording(c_pos[i], int(c_at[i]), sim, deploy, i, f"{args.guard_label} (converted)", f"{args.strike_label} (converted)",
                          "Copy of NUS 2-D game (PyTorch)")
        left.half_m = right.half_m = max(left.half_m, right.half_m)  # one scale for both panels
        paths = [render_replay(rec, video_dir / f"{args.name}_game{i}_{tag}.mp4", playback_label="NUS JAX game" if tag == "jax" else "PyTorch copy",
                               **FORMATS["mp4"]) for rec, tag in ((left, "jax"), (right, "pytorch"))]
        fmt = FORMATS["mp4"]
        hold_s = inspect.signature(render_replay).parameters["hold_s"].default  # the renderer's closing hold, not a second copy
        d = max(r.end_step for r in (left, right)) / fmt["speed"] / fmt["fps"] + hold_s
        side_by_side(*paths, video_dir / f"{args.name}_game{i}_same_start.mp4", video_dir / f"{args.name}_game{i}_same_start.gif", d)
        print(f"game {i}: NUS JAX game {'Strike reaches' if j_at[i] >= 0 else 'Guard holds'} (step {j_at[i]}), PyTorch copy "
              f"{'Strike reaches' if c_at[i] >= 0 else 'Guard holds'} (step {c_at[i]}); wrote {args.name}_game{i}_same_start.mp4/.gif", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
