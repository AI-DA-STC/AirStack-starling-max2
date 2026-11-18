"""Export one PPO update of the partner's learner for the M3 parity test (NUS port Phase 5). Run in the partner's JAX environment, CPU:

    cd <svg_training>; unset PYTHONPATH; PYTHONNOUSERSITE=1 JAX_PLATFORMS=cpu ~/miniconda3/envs/nus_jax/bin/python \
        scripts/nus_jax_export_update.py --clone <partner clone> --run-config <run config.json> --team guard --dtype bfloat16 \
        --steps <T> --games <B> --seed <S> --out runs/nus_port/phase5/method_port/update_bfloat16.npz

What it does, with the partner's own functions only (this script holds none of their code): builds the partner's actor and critic with
the run's architecture (``--dtype`` overrides the compute dtype, so a float32 twin can prove the logic tightly), initialises them,
collects ``--games`` games of ``--steps`` steps against the scripted APF controller (``collect_fixed_matchups``), evaluates the rollout
(``evaluate_rollout``), computes returns and advantages (``returns_and_advantages``) and runs ``policy_update`` with one epoch and one
minibatch. The optimiser is the runner's own (``FixedOpponentRunner._optimizer``) behind a pass-through stage that keeps the raw
gradient in its state, so the gradients are exported as well. The permutation and the entropy noise the update draws are re-derived
from its key with ``jax.random`` (split into three; the second key permutes the samples, the third gives one key per minibatch) and
exported, so the PyTorch side can use the same draws.

Writes one npz under runs/ (values of the partner's network; git-ignored) and prints its path, the array names and the metrics' names.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("JAX_PLATFORMS", "cpu")
os.environ.setdefault("WANDB_MODE", "disabled")

import numpy as np  # noqa: E402

TEAM = {"guard": "defender", "strike": "attacker"}


def _flat(tree, prefix: str) -> dict[str, np.ndarray]:
    out = {}
    if isinstance(tree, dict) or hasattr(tree, "items"):
        for key, value in tree.items():
            out |= _flat(value, f"{prefix}/{key}")
        return out
    return {prefix: np.asarray(tree, dtype=np.float32)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clone", required=True, type=Path)
    parser.add_argument("--run-config", required=True, type=Path)
    parser.add_argument("--team", choices=tuple(TEAM), default="guard")
    parser.add_argument("--dtype", choices=("bfloat16", "float32"), required=True)
    parser.add_argument("--steps", required=True, type=int)
    parser.add_argument("--games", required=True, type=int)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    if "runs" not in args.out.resolve().parts:
        raise SystemExit("the export holds the partner's network values: --out must be under runs/")

    sys.path.insert(0, str(args.clone))
    sys.path.insert(0, str(args.clone / "third_party" / "skill_learning_mpe" / "src"))
    import jax
    import jax.numpy as jnp
    import optax
    from omegaconf import OmegaConf
    import ma_skills.jax.mpe as nus_mpe
    from ma_skills.jax.policy import TeamActor, TeamCritic
    from ma_skills.jax.training import PPOConfig, evaluate_rollout, policy_update, returns_and_advantages
    from ma_skills.jax.types import PolicyTrainState
    import ma_skills.runner.fixed_opponent_runner as nus_runner

    run = json.loads(args.run_config.read_text())
    cfg = OmegaConf.create(run)
    team, env_cfg, trainer = TEAM[args.team], run["environment"]["env"], run["trainer"]
    adapter = nus_mpe.JAXMPEAdapter(env_id=env_cfg["env_id"], global_state_fields=env_cfg["global_state_fields"],
                            max_episode_steps=env_cfg["max_episode_steps"], env_kwargs=env_cfg.get("physics", {}),
                            max_pool_slots=int(trainer["max_pool_slots"]))
    first_obs, _ = adapter.reset_many(jax.random.split(jax.random.key(0), 1))
    obs_dim = int(adapter.defender_obs(first_obs).shape[-1])
    policy = trainer["policy"]
    dtype = getattr(jnp, args.dtype)
    speed = adapter.env.team_max_speed(team)
    kw = dict(hidden_dim=int(policy["hidden_dim"]), num_blocks=int(policy["n_hidden_layers"]), activation_name=str(policy["activation_type"]),
              use_norm=bool(policy["use_layernorm"]), dtype=dtype)
    actor = TeamActor(obs_dim, 2, max_speed=speed, initial_log_std=float(policy["initial_log_std"]),
                      zero_init_output=bool(policy["zero_init_output"]), **kw)
    critic = TeamCritic(adapter.state_dim, **kw)

    def capture():
        """A pass-through optax stage that keeps the incoming (raw) gradient as its state."""
        return optax.GradientTransformation(lambda params: jax.tree.map(jnp.zeros_like, params),
                                            lambda updates, state, params=None: (updates, updates))

    runner_like = SimpleNamespace(cfg=cfg, _learning_rate=lambda rate: float(rate))
    actor_opt = optax.chain(capture(), nus_runner.FixedOpponentRunner._optimizer(runner_like, trainer[team]["actor_lr"]))
    critic_opt = optax.chain(capture(), nus_runner.FixedOpponentRunner._optimizer(runner_like, trainer[team]["critic_lr"]))

    key = jax.random.key(args.seed)
    key, actor_key, critic_key, rollout_key, update_key = jax.random.split(key, 2 + 2 + 1)
    sample_obs = jnp.zeros((1, adapter.n_agents if team == "defender" else adapter.n_attackers, obs_dim), jnp.float32)
    actor_params = actor.init(actor_key, sample_obs)["params"]
    critic_params = critic.init(critic_key, jnp.zeros((1, adapter.state_dim), jnp.float32))["params"]
    state = PolicyTrainState(actor_params=actor_params, critic_params=critic_params, actor_opt_state=actor_opt.init(actor_params),
                             critic_opt_state=critic_opt.init(critic_params))

    reward = trainer["rewards"]["defender"]
    out = nus_mpe.collect_fixed_matchups(actor_params, rollout_key, adapter=adapter, actor=actor, episode_length=args.steps, active_team=team,
                                 batch_size=args.games, distance_scale=float(reward["attacker_distance_scale"]),
                                 breach_penalty=float(reward["breach_penalty"]), clean_timeout_reward=float(reward["clean_timeout_reward"]),
                                 shaping_gamma=float(trainer[team]["task_gamma"]),
                                 first_breach_penalty=float(reward.get("first_breach_penalty", 0)), apf_slots=1)
    _, defender_episode, attacker_episode, defender_rewards, attacker_rewards, *_ = out
    episode = defender_episode if team == "defender" else attacker_episode
    rewards = defender_rewards if team == "defender" else attacker_rewards
    values, old_logp, _ = evaluate_rollout(state, episode.obs, episode.global_state, episode.latents, actor=actor, critic=critic)
    done_flags = episode.truncated[..., 0, :].astype(jnp.float32)
    returns, advantages = returns_and_advantages(rewards, values, done_flags, jnp.zeros_like(values[-1]),
                                                 gamma=float(trainer[team]["task_gamma"]), gae_lambda=float(trainer[team]["task_gae_lambda"]))
    config = PPOConfig(epochs=1, minibatches=1, clip=float(trainer["ppo_clip"]), entropy_coef=float(trainer["entropy_coef"]),
                       critic_loss_coef=float(trainer["critic_loss_coef"]), advantage_weight=float(trainer[team]["task_advantage_weight"]),
                       max_speed=speed)
    new_state, metrics = policy_update(state, episode.obs, episode.global_state, episode.latents, old_logp, returns, advantages,
                                       jnp.ones_like(rewards), update_key, actor=actor, critic=critic, actor_optimizer=actor_opt,
                                       critic_optimizer=critic_opt, config=config)
    # the draws inside the update: one epoch, one minibatch
    samples = args.steps * args.games
    agents = episode.obs.shape[2]
    _, permutation_key, entropy_key = jax.random.split(update_key, 2 + 1)
    order = jax.random.permutation(permutation_key, samples)
    noise = jax.random.normal(jax.random.split(entropy_key, 1)[0], (samples, agents, 2))

    arrays = {"obs": episode.obs, "central": episode.global_state, "latents": episode.latents, "rewards": rewards[..., 0],
              "dones": done_flags[..., 0], "values": values[..., 0], "old_logp": old_logp[..., 0], "returns": returns[..., 0],
              "advantages": advantages[..., 0], "permutation": order, "entropy_noise": noise}
    arrays = {k: np.asarray(v) for k, v in arrays.items()}
    arrays |= _flat(jax.device_get(actor_params), "actor_before") | _flat(jax.device_get(new_state.actor_params), "actor_after")
    arrays |= _flat(jax.device_get(critic_params), "critic_before") | _flat(jax.device_get(new_state.critic_params), "critic_after")
    arrays |= _flat(jax.device_get(new_state.actor_opt_state[0]), "actor_grad") | _flat(jax.device_get(new_state.critic_opt_state[0]), "critic_grad")
    arrays |= {f"metric/{k}": np.asarray(v, np.float32) for k, v in metrics.items()}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(args.out, **arrays)
    commit = os.popen(f"git -C {args.clone} rev-parse HEAD").read().strip()
    (args.out.with_suffix(".json")).write_text(json.dumps({"dtype": args.dtype, "team": args.team, "steps": args.steps, "games": args.games,
                                                            "seed": args.seed, "partner_commit": commit, "arrays": sorted(arrays)}, indent=2))
    print(f"wrote {args.out} ({len(arrays)} arrays); metrics: {sorted(metrics)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
