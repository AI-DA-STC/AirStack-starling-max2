"""Reference data for the converted-policy gates. Run in the partner's JAX environment (``nus_jax``), CPU only:

    cd <svg_training>; unset PYTHONPATH; PYTHONNOUSERSITE=1 JAX_PLATFORMS=cpu WANDB_MODE=disabled \
        ~/miniconda3/envs/nus_jax/bin/python scripts/nus_export_reference.py --clone <partner clone> \
        --guard-checkpoint <folder> --strike-checkpoint <folder> --seed <S> --episodes-per-half <E> --starts <K>

For each team writes ``runs/nus_port/reference/actions_<team>.npz``: team observations and the partner's JAX deterministic actions on
them in the checkpoint's own compute dtype (``actions``; the float32 forward is stored as ``actions_f32``, information only), plus
the game state each observation came from. Observations come from two kinds of 3 v 3 rollout in the partner's environment, built
before any number was measured: ON-POLICY (the checkpoint's team plays deterministically against the scripted opponent, the
opponent team being the partner's scripted controller) and RANDOM (both teams draw each action uniformly from their own action box,
so every observation is a valid game state). Half of the rows come from each kind (``kind``: 0 on-policy, 1 random).

Also writes ``apf_states.npz`` (all the states with both scripted controllers' actions, for the scripted-controller parity test)
and ``starts.npz`` (the partner's own random starts, replayed in both arms of the outcome run).

Everything is written under runs/ (it holds partner values and is git-ignored); the script prints counts and file hashes only.
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
REFERENCE_DIR = ROOT_RUNS / "nus_port" / "reference"
ROLLOUT_KEYS = ("guard actions", "strike actions", "step")  # one random key for each


def rollout(adapter, bundle, team: str, kind: str, episodes: int, key):
    """Play ``episodes`` games; return per-step team observations (E, T, size, D), states' positions and flags, and both teams' APF actions."""
    import jax
    import jax.numpy as jnp

    env = adapter.env
    steps = int(env.max_steps)
    keys = jax.random.split(key, episodes + 1)
    obs, state = adapter.reset_many(keys[1:])
    mine = adapter.defender_obs if team == "guard" else adapter.attacker_obs
    out = {k: [] for k in ("obs", "pos", "prev", "breach", "step", "strike_apf", "guard_apf")}
    box = {"guard": float(env.defender_max_speed), "strike": float(env.attacker_max_speed)}
    size = {"guard": adapter.n_agents, "strike": adapter.n_attackers}
    for t in range(steps):
        team_obs = mine(obs)
        out["obs"].append(np.asarray(team_obs))
        out["pos"].append(np.asarray(state.p_pos))
        out["prev"].append(np.asarray(state.prev_p_pos))
        out["breach"].append(np.asarray(state.breach))
        out["step"].append(np.asarray(state.step))
        out["strike_apf"].append(np.asarray(adapter.apf_actions(state, team="attacker")))
        out["guard_apf"].append(np.asarray(adapter.apf_actions(state, team="defender")))
        k_g, k_s, k_step = jax.random.split(jax.random.fold_in(keys[0], t), len(ROLLOUT_KEYS))
        if kind == "on_policy":
            own = deterministic_actions(bundle, team_obs)
            other = adapter.apf_actions(state, team="attacker" if team == "guard" else "defender")
            guard_act, strike_act = (own, other) if team == "guard" else (other, own)
        else:
            guard_act = jax.random.uniform(k_g, (episodes, size["guard"], 2), minval=-box["guard"], maxval=box["guard"])
            strike_act = jax.random.uniform(k_s, (episodes, size["strike"], 2), minval=-box["strike"], maxval=box["strike"])
        step_keys = jax.random.split(k_step, episodes)
        obs, state, _r, _d, _i = adapter.step_many_joint(step_keys, state, guard_act, strike_act)
    # (T, E, ...) -> (E*T, ...) keeping episode order
    return {k: np.concatenate([np.swapaxes(np.stack(v), 0, 1).reshape(episodes * steps, *np.stack(v).shape[2:])], axis=0) for k, v in out.items()}


def export_team(clone: Path, team: str, checkpoint: Path, episodes: int, seed: int, out_dir: Path = REFERENCE_DIR) -> dict:
    import jax

    bundle = load_actor(clone, checkpoint, team)
    bundle32 = load_actor(clone, checkpoint, team, dtype_name="float32")
    adapter = make_adapter(bundle["config"])
    parts, kinds = [], []
    for index, kind in enumerate(("on_policy", "random")):
        part = rollout(adapter, bundle, team, kind, episodes, jax.random.key(seed + index))
        parts.append(part)
        kinds.append(np.full(part["obs"].shape[0], index, np.int8))
    cat = {k: np.concatenate([p[k] for p in parts], axis=0) for k in parts[0]}
    actions = np.asarray(deterministic_actions(bundle, cat["obs"]), np.float32)
    actions32 = np.asarray(deterministic_actions(bundle32, cat["obs"]), np.float32)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"actions_{team}.npz"
    np.savez_compressed(path, obs=cat["obs"].astype(np.float32), actions=actions, actions_f32=actions32, pos=cat["pos"], prev_pos=cat["prev"],
                        breach=cat["breach"], step=cat["step"], kind=np.concatenate(kinds))
    return {"team": team, "path": path, "states": cat["obs"].shape[0], "rows": cat["obs"].shape[0] * cat["obs"].shape[1],
            "f32_vs_compute_dtype_max_diff": float(np.abs(actions - actions32).max()), "apf": cat}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clone", required=True, type=Path)
    parser.add_argument("--guard-checkpoint", required=True, type=Path)
    parser.add_argument("--strike-checkpoint", required=True, type=Path)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--episodes-per-half", required=True, type=int)
    parser.add_argument("--starts", required=True, type=int)
    parser.add_argument("--out-dir", type=Path, default=REFERENCE_DIR, help="default: the Phase 3 folder; Phase 4's W3 uses runs/nus_port/w3/reference")
    args = parser.parse_args(argv)
    out_dir = args.out_dir.resolve()
    if (ROOT_RUNS.resolve() not in (out_dir, *out_dir.parents)):
        raise SystemExit("refusing: --out-dir must lie under runs/ (the files hold partner values)")
    add_partner_paths(args.clone)
    import jax

    results = [export_team(args.clone, team, folder, args.episodes_per_half, args.seed + offset, out_dir)
               for offset, (team, folder) in enumerate((("guard", args.guard_checkpoint), ("strike", args.strike_checkpoint)))]
    apf_pos = np.concatenate([r["apf"]["pos"] for r in results])
    np.savez_compressed(out_dir / "apf_states.npz", pos=apf_pos,
                        strike_actions=np.concatenate([r["apf"]["strike_apf"] for r in results]).astype(np.float32),
                        guard_actions=np.concatenate([r["apf"]["guard_apf"] for r in results]).astype(np.float32))
    bundle = load_actor(args.clone, args.guard_checkpoint, "guard")
    adapter = make_adapter(bundle["config"])
    _, starts = adapter.reset_many(jax.random.split(jax.random.fold_in(jax.random.key(args.seed), 2), args.starts))
    np.savez_compressed(out_dir / "starts.npz", pos=np.asarray(starts.p_pos, np.float32))
    for path in sorted(out_dir.glob("*.npz")):
        print(f"{path.name}: sha256 {hashlib.sha256(path.read_bytes()).hexdigest()}")
    for r in results:
        print(f"{r['team']}: states {r['states']}, observation rows {r['rows']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
