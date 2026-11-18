"""Record episodes of the partner's environment for the replica parity test. Run in the partner's JAX environment:

    cd <svg_training>; unset PYTHONPATH; PYTHONNOUSERSITE=1 JAX_PLATFORMS=cpu ~/miniconda3/envs/nus_jax/bin/python \
        scripts/nus_record_fixtures.py --clone <partner clone> --config <partner root config yaml> --tag <name> \
        --episodes <K> --seed <S> [--start-mode random|static]

Writes ``runs/nus_port/fixtures/<tag>.npz`` (states, actions, observations, per-step rule flags) and ``<tag>.json`` (coverage
counts and the commit of the clone). Values live only in the npz under runs/ (git-ignored). The JSON names no rule value.

Episodes alternate between random actions and scripted ones that make each rule fire: Strikes driven into Guards (push),
Guards driven outward past their boundary, oversized requests (caps), Strikes sent to the zone (reached flag).

``--train-fields`` (Phase 5, task M2; ``--config`` must then be a self-play run's resolved ``config.json``): also records, per step,
the partner's own critic state of the pre-step state (``JAXMPEAdapter.critic_state``, one random opponent slot per episode), the
Guard team's reward from the partner's ``defender_task_rewards`` with the run's reward settings and the Guard team's discount as the
shaping discount, the Strike drones inside the zone and the first-reach flag. The default recording is unchanged.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

os.environ.setdefault("JAX_PLATFORMS", "cpu")
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "source"))

import numpy as np  # noqa: E402

from nus_cfg import load_environment_cfg  # noqa: E402

OVERSIZE = 2 * 2 * 2  # requested step as a multiple of the team's speed limit in the oversized modes
MODES = ("random", "strike_into_guard", "guard_outward", "oversized", "strike_to_zone", "full_game", "guard_outward_chased")


def _unit(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.maximum(n, np.finfo(np.float32).eps)


def _nearest(frm: np.ndarray, to: np.ndarray) -> np.ndarray:
    """Vectors from each `frm` point to the nearest `to` point."""
    off = to[None, :, :] - frm[:, None, :]
    idx = np.argmin(np.linalg.norm(off, axis=-1), axis=1)
    return off[np.arange(len(frm)), idx]


def scripted_actions(mode: str, env, pos: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """(M, 2) requested displacements for the given mode."""
    g = env.num_good_agents
    limit = np.array([env.defender_max_speed] * g + [env.attacker_max_speed] * env.num_adversaries)[:, None]
    random_in_box = rng.uniform(-limit, limit, size=pos.shape)  # the partner's action box is the team speed limit per axis
    big = OVERSIZE * limit
    guards, strikes = pos[:g], pos[g:]
    act = random_in_box.copy()
    if mode == "random":
        return act
    if mode == "oversized":
        return big * _unit(rng.normal(size=pos.shape))
    if mode in ("strike_into_guard", "full_game"):
        act[g:] = big[g:] * _unit(_nearest(strikes, guards))
        act[:g] = 0 if mode == "strike_into_guard" else big[:g] * _unit(_nearest(guards, strikes))
        return act
    if mode == "strike_to_zone":
        act[g:] = big[g:] * _unit(-strikes)
        act[:g] = 0
        return act
    if mode in ("guard_outward", "guard_outward_chased"):
        act[:g] = big[:g] * _unit(guards + np.finfo(np.float32).eps)
        if mode == "guard_outward_chased":
            act[g:] = big[g:] * _unit(_nearest(strikes, guards))
        return act
    raise ValueError(mode)


def rule_flags(env, pos: np.ndarray, actions: np.ndarray, breach_before: float, breach_after: float) -> dict[str, bool]:
    """Which rules were active in this step, from geometry on the partner's own attributes."""
    g = env.num_good_agents
    limit = np.array([env.defender_max_speed] * g + [env.attacker_max_speed] * env.num_adversaries)[:, None]
    norms = np.linalg.norm(actions, axis=-1, keepdims=True)
    intended = np.asarray(env.intended_displacements({a: actions[i] for i, a in enumerate(env.agents)}))
    tentative = pos + intended
    dist = np.linalg.norm(tentative[:, None] - tentative[None], axis=-1)
    safety = np.array([env.defender_safety_distance] * g + [env.attacker_safety_distance] * env.num_adversaries)
    radius = 2 * env.agent_size + safety
    cross = np.arange(env.num_actors)[:, None] < g
    cross = cross != cross.T
    push = bool(np.any(cross & (dist < radius[None, :])))
    radial = np.linalg.norm(tentative[:g], axis=-1)
    boundary = bool(np.any(radial > env.defender_boundary - env.boundary_margin))
    return {
        "push": push,
        "team_cap": bool(np.any(norms > limit)),
        "boundary": boundary,
        "flag_flip": bool(breach_after > breach_before),
    }


def _train_recorder(args: argparse.Namespace, env_cfg: dict, env_id: str) -> dict:
    """The partner's adapter and reward function, set up from the run's config.json (Phase 5 M2 fixtures)."""
    import jax
    import jax.numpy as jnp
    from ma_skills.jax.mpe import JAXMPEAdapter
    import ma_skills.jax.rewards as nus_rewards

    run_cfg = json.loads(args.config.read_text())
    trainer = run_cfg["trainer"]
    adapter = JAXMPEAdapter(env_id=env_id, global_state_fields=env_cfg["env"]["global_state_fields"],
                            max_episode_steps=env_cfg["env"]["max_episode_steps"], env_kwargs=env_cfg["env"].get("physics", {}),
                            max_pool_slots=int(trainer["max_pool_slots"]))
    reward_cfg = trainer["rewards"]["defender"]
    kwargs = {"distance_scale": float(reward_cfg["attacker_distance_scale"]), "breach_penalty": float(reward_cfg["breach_penalty"]),
              "clean_timeout_reward": float(reward_cfg["clean_timeout_reward"]),
              "first_breach_penalty": float(reward_cfg.get("first_breach_penalty", 0)),
              "shaping_gamma": float(trainer["defender"]["task_gamma"])}
    length = int(env_cfg["env"]["max_episode_steps"])

    def record(state, new_state, info, t: int, slot: int):
        batched = jax.tree.map(lambda x: jnp.asarray(x)[None], state)
        critic = np.asarray(adapter.critic_state(batched, jnp.asarray([slot], jnp.int32)))[0]
        before, after = bool(state.breach), bool(new_state.breach)
        clean = jnp.asarray(t + 1 >= length) & ~jnp.asarray(after)
        count = info["attacker_inside_count"]
        value = nus_rewards.defender_task_rewards(state.p_pos, new_state.p_pos, new_state.area_pos, count / float(adapter.n_attackers), clean,
                                      n_defenders=adapter.n_agents, first_breach=jnp.asarray(after and not before), **kwargs)
        return critic, float(np.asarray(value).reshape(-1)[0]), int(count), bool(after and not before)

    return {"record": record, "state_dim": int(adapter.state_dim), "slots": int(trainer["max_pool_slots"])}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clone", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--episodes", required=True, type=int)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--start-mode", choices=("random", "static"), default="random")
    parser.add_argument("--train-fields", action="store_true", help="also record critic states and rewards (needs a run config.json)")
    parser.add_argument("--out-dir", type=Path, default=Path(__file__).resolve().parents[1] / "runs" / "nus_port" / "fixtures")
    args = parser.parse_args(argv)
    if "runs" not in args.out_dir.resolve().parts:
        raise SystemExit("fixtures hold partner values: --out-dir must be under runs/")

    sys.path.insert(0, str(args.clone))
    sys.path.insert(0, str(args.clone / "third_party" / "skill_learning_mpe" / "src"))
    import jax
    from skill_learning_mpe.env import make_env

    env_cfg = load_environment_cfg(args.config)
    *head, _mode, version = str(env_cfg["env"]["env_id"]).split("_")
    env_id = "_".join([*head, args.start_mode, version])
    env = make_env(env_id, **dict(env_cfg["env"].get("physics", {})))
    train = _train_recorder(args, env_cfg, env_id) if args.train_fields else None
    rng = np.random.default_rng(args.seed)
    steps = int(env.max_steps)
    m = env.num_actors

    pos = np.zeros((args.episodes, steps + 1, m, 2), np.float32)
    prev = np.zeros_like(pos)
    breach = np.zeros((args.episodes, steps + 1), np.float32)
    step_no = np.zeros((args.episodes, steps + 1), np.int32)
    obs = np.zeros((args.episodes, steps + 1, m, env.observation_spaces[env.agents[0]].shape[0]), np.float32)
    act = np.zeros((args.episodes, steps, m, 2), np.float32)
    names = ("push", "team_cap", "boundary", "flag_flip")
    flags = {k: np.zeros((args.episodes, steps), bool) for k in names}
    total_cap = np.zeros((args.episodes, steps), bool)
    if train is not None:
        central = np.zeros((args.episodes, steps, train["state_dim"]), np.float32)
        reward = np.zeros((args.episodes, steps), np.float32)
        inside = np.zeros((args.episodes, steps), np.int32)
        first_reach = np.zeros((args.episodes, steps), bool)
        slot = rng.integers(0, train["slots"], size=args.episodes)
    modes = [MODES[e % len(MODES)] for e in range(args.episodes)]

    def record(e, t, state, observation):
        pos[e, t] = np.asarray(state.p_pos)
        prev[e, t] = np.asarray(state.prev_p_pos)
        breach[e, t] = float(state.breach)
        step_no[e, t] = int(state.step)
        obs[e, t] = np.stack([np.asarray(observation[a]) for a in env.agents])

    for e in range(args.episodes):
        key = jax.random.PRNGKey(args.seed * (args.episodes + 1) + e)
        key, sub = jax.random.split(key)
        observation, state = env.reset(sub)
        record(e, 0, state, observation)
        for t in range(steps):
            actions = scripted_actions(modes[e], env, pos[e, t], rng).astype(np.float32)
            act[e, t] = actions
            actions_dict = {a: actions[i] for i, a in enumerate(env.agents)}
            intended = env.intended_displacements(actions_dict)
            corrections = env.displacement_corrections(state, intended)
            total_cap[e, t] = bool(np.any(np.linalg.norm(np.asarray(intended + corrections), axis=-1) > env.max_total_displacement))
            key, sub = jax.random.split(key)
            observation, new_state, _r, _d, info = env.step_env(sub, state, actions_dict)
            if train is not None:
                central[e, t], reward[e, t], inside[e, t], first_reach[e, t] = train["record"](state, new_state, info, t, int(slot[e]))
            f = rule_flags(env, pos[e, t], actions, float(state.breach), float(new_state.breach))
            for k in names:
                flags[k][e, t] = f[k]
            state = new_state
            record(e, t + 1, state, observation)

    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        out / f"{args.tag}.npz", pos=pos, prev_pos=prev, breach=breach, step=step_no, obs=obs, actions=act,
        total_cap=total_cap, modes=np.array(modes), **{f"flag_{k}": v for k, v in flags.items()},
        **({"central": central, "guard_reward": reward, "inside_count": inside, "first_reach": first_reach, "slot": slot}
           if train is not None else {}),
    )
    commit = subprocess.run(["git", "-C", str(args.clone), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    coverage = {
        "tag": args.tag, "start_mode": args.start_mode, "episodes": args.episodes, "steps_per_episode": steps,
        "seed": args.seed, "partner_commit": commit, "modes": sorted(set(modes)),
        "steps_with_push": int(flags["push"].sum()), "steps_with_team_cap": int(flags["team_cap"].sum()),
        "steps_with_total_cap": int(total_cap.sum()), "steps_with_boundary": int(flags["boundary"].sum()),
        "steps_with_flag_flip": int(flags["flag_flip"].sum()),
        "episodes_with_flag_flip": int(flags["flag_flip"].any(axis=1).sum()),
        **({"train_fields": True} if train is not None else {}),
    }
    (out / f"{args.tag}.json").write_text(json.dumps(coverage, indent=2) + "\n")
    print(json.dumps(coverage))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
