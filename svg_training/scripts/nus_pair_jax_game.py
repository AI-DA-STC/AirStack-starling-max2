"""A Guard policy against a Strike policy in NUS's own 2-D game (JAX), on the shared starts. Run in ``nus_jax``, CPU only:

    cd <svg_training>; unset PYTHONPATH; PYTHONNOUSERSITE=1 JAX_PLATFORMS=cpu WANDB_MODE=disabled \
        ~/miniconda3/envs/nus_jax/bin/python scripts/nus_pair_jax_game.py --clone <NUS clone> \
        --guard-checkpoint <folder> --strike-checkpoint <folder> --starts runs/nus_port/w3/reference/starts.npz \
        --seed 20261118 --out runs/nus_port/pairs/<name>_jax_game.npz

The starts are rebuilt in NUS's environment from ``--seed`` exactly as ``nus_export_reference.py`` builds them, and must equal the
``--starts`` file (the starts the PyTorch copy plays); the script refuses otherwise. Both teams then act deterministically through NUS's
own actor (``deterministic_actions``) and NUS's own environment step, every game played to NUS's step limit. No game rule or step of
ours is used. Writes per-game positions (units, every step), the step at which the Strike team first reached the zone (-1: never) and
the count of reaches; prints counts and the file hash only (the file holds NUS values and stays under runs/).
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402

from nus_jax_common import add_partner_paths, deterministic_actions, load_actor, make_adapter  # noqa: E402

ROOT_RUNS = Path(__file__).resolve().parents[1] / "runs"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--clone", required=True, type=Path)
    parser.add_argument("--guard-checkpoint", required=True, type=Path)
    parser.add_argument("--strike-checkpoint", required=True, type=Path)
    parser.add_argument("--starts", required=True, type=Path)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    out = args.out.resolve()
    if ROOT_RUNS.resolve() not in out.parents:
        raise SystemExit("refusing: --out must lie under runs/ (the file holds NUS values)")
    add_partner_paths(args.clone)
    import jax

    guard = load_actor(args.clone, args.guard_checkpoint, "guard")
    strike = load_actor(args.clone, args.strike_checkpoint, "strike")
    g_phys, s_phys = guard["config"]["environment"]["env"]["physics"], strike["config"]["environment"]["env"]["physics"]
    differ = sorted(k for k in set(g_phys) | set(s_phys) if g_phys.get(k) != s_phys.get(k))
    print(f"game settings that differ between the two checkpoints' configs: {differ or 'none'} (the Guard checkpoint's game is played)")
    adapter = make_adapter(guard["config"])
    expected = np.load(args.starts)["pos"]
    games = expected.shape[0]
    obs, state = adapter.reset_many(jax.random.split(jax.random.fold_in(jax.random.key(args.seed), 2), games))
    rebuilt = np.asarray(state.p_pos, np.float32)
    gap = float(np.abs(rebuilt - expected).max())
    if gap > 0:
        raise SystemExit(f"refusing: starts rebuilt from seed {args.seed} differ from {args.starts} (max gap {gap})")
    print(f"starts: {games} games rebuilt in NUS's environment, equal to {args.starts.name}")
    steps = int(adapter.env.max_steps)
    pos, reached_at = [rebuilt], np.full(games, -1, np.int64)
    key = jax.random.fold_in(jax.random.key(args.seed), 1)  # the starts use fold 2 (as nus_export_reference.py)
    for t in range(steps):
        g_act = deterministic_actions(guard, adapter.defender_obs(obs))
        s_act = deterministic_actions(strike, adapter.attacker_obs(obs))
        obs, state, _r, _d, _i = adapter.step_many_joint(jax.random.split(jax.random.fold_in(key, t), games), state, g_act, s_act)
        pos.append(np.asarray(state.p_pos, np.float32))
        breach = np.asarray(state.breach).reshape(games, -1).any(axis=1)
        reached_at[(reached_at < 0) & breach] = t + 1
    reached = int((reached_at >= 0).sum())
    out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out, pos=np.stack(pos, axis=1), reached_at=reached_at, starts_gap=gap, steps=steps,
                        guard_checkpoint=str(args.guard_checkpoint), strike_checkpoint=str(args.strike_checkpoint))
    print(f"Strike reaches the zone: {reached} of {games} (NUS's JAX game, both teams NUS's JAX actors, deterministic)")
    print(f"wrote {out} sha256 {hashlib.sha256(out.read_bytes()).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
