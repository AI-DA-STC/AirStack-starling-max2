"""Phase 5 task M3: the learner (nus/mappo.py). Formula tests on marker files and hand values; the stacked forward against the converted
actor of Phase 3; the one-update parity test against the partner's own update, exported by scripts/nus_jax_export_update.py (float32
twin and the run's bfloat16; skipped where the export or the local files are absent: a skip is not a pass)."""
import json
import math

import numpy as np
import pytest
import torch

from _nus_markers import BATCH, ROOT, write_synthetic_checkpoint, load_marker_files
from _nus_phase5_method_fixture import (CLIP_SCALE, NOISE_FLOOR_FACTOR, NOISE_FLOOR_SEEDS, GAE_CASE, LATENT_BIG, NORMAL_SAMPLES, PARITY_DTYPES, PARITY_TOL,
                                        SEEDS, TRAIN_GAMES, UNIT_TOL,
                                        marker_env, marker_method_object)
from svg_training.nus import mappo as M


def test_log_prob_and_entropy_formulas():
    gen = torch.Generator().manual_seed(0)
    mean, log_std = torch.randn(NORMAL_SAMPLES, 2, generator=gen), torch.randn(NORMAL_SAMPLES, 2, generator=gen) / 2
    x = torch.randn(NORMAL_SAMPLES, 2, generator=gen)
    ref = torch.distributions.Normal(mean, log_std.exp())
    torch.testing.assert_close(M.gaussian_log_prob(x, mean, log_std), ref.log_prob(x).sum(-1))
    torch.testing.assert_close(M.gaussian_entropy(log_std), ref.entropy().sum(-1))
    naive = torch.log(1 - torch.tanh(x).square()).sum(-1)
    torch.testing.assert_close(M.tanh_log_jacobian(x), naive, atol=UNIT_TOL, rtol=UNIT_TOL)
    assert torch.isfinite(M.tanh_log_jacobian(torch.full((1, 2), LATENT_BIG))).all()
    zero = torch.zeros_like(mean)
    torch.testing.assert_close(M.transformed_entropy(mean, log_std, zero), M.gaussian_entropy(log_std) + M.tanh_log_jacobian(mean))


def test_gae_by_hand():
    c = GAE_CASE
    col = lambda v: torch.tensor(v)[:, None]  # noqa: E731
    returns, adv = M.gae(col(c["rewards"]), col(c["values"]), col(c["dones"]).bool(), c["gamma"], c["lam"])
    torch.testing.assert_close(adv[:, 0], torch.tensor(c["advantages"]))
    torch.testing.assert_close(returns[:, 0], torch.tensor(c["returns"]))


def test_normalisation_and_clip():
    method = marker_method_object()
    adv = torch.randn(NORMAL_SAMPLES, generator=torch.Generator().manual_seed(1))
    out = M.normalise_advantages(adv, method)
    assert abs(out.mean().item()) < UNIT_TOL and abs(out.std(unbiased=False).item() - 1) < UNIT_TOL * NORMAL_SAMPLES
    spike = torch.zeros(NORMAL_SAMPLES * NORMAL_SAMPLES)
    spike[0] = 1
    assert M.normalise_advantages(spike, method).max().item() == pytest.approx(method.advantage_clip)


def test_global_norm_clip_matches_the_rule():
    p = torch.nn.Parameter(torch.zeros(2))
    p.grad = torch.ones(2)
    M.clip_global_norm_([p], CLIP_SCALE)
    assert torch.equal(p.grad, torch.ones(2))                                     # below the limit: unchanged
    p.grad = torch.ones(2) * CLIP_SCALE
    norm = M.clip_global_norm_([p], CLIP_SCALE)
    assert norm.item() == pytest.approx(CLIP_SCALE * math.sqrt(2))
    assert torch.linalg.norm(p.grad).item() == pytest.approx(CLIP_SCALE)


def test_learner_initialisation(tmp_path):
    env = marker_env(tmp_path)
    m = env.method
    a, b = M.Learner(m, env, "guard", seed=BATCH), M.Learner(m, env, "guard", seed=BATCH)
    c = M.Learner(m, env, "strike", seed=BATCH)
    assert torch.equal(a.actor.trunk.proj.weight, b.actor.trunk.proj.weight)
    assert not torch.equal(a.actor.trunk.proj.weight, c.actor.trunk.proj.weight[:, : a.actor.trunk.proj.weight.shape[1]])
    assert torch.all(a.actor.log_std == m.initial_log_std)
    rows = torch.linalg.norm(a.actor.trunk.output.weight, dim=1)
    torch.testing.assert_close(rows, torch.full_like(rows, m.output_init_gain))   # orthogonal rows of length = the gain
    assert torch.count_nonzero(a.actor.trunk.proj.bias) == 0
    w = a.critic.trunk.input.weight
    std = m.init_std_scale / math.sqrt(w.shape[1])
    assert w.abs().max().item() <= m.init_truncation * std + UNIT_TOL
    zero = M.Learner(marker_method_object(zero_init_output=True), env, "guard", seed=BATCH)
    assert torch.count_nonzero(zero.actor.trunk.output.weight) == 0


def test_rollout_update_and_non_finite_abort(tmp_path):
    env = marker_env(tmp_path)
    learner = M.Learner(env.method, env, "strike", seed=1)
    gen = torch.Generator().manual_seed(2)
    rollout = learner.collect(env, env.reset(TRAIN_GAMES, gen), gen, steps=env.episode_steps,
                              opponent=lambda s, g: env.apf_actions(s, "guard"))
    assert rollout.obs.shape == (env.episode_steps, TRAIN_GAMES, env.strike_count, env.obs_dim)
    assert rollout.central.shape == (env.episode_steps, TRAIN_GAMES, env.state_dim) and bool(rollout.dones[-1].all())
    actions, _ = learner.act(rollout.obs[0], gen, deterministic=True)
    assert torch.all(torch.linalg.norm(actions, dim=-1) <= env.team_speed("strike") * (1 + UNIT_TOL))
    before = learner.actor.trunk.proj.weight.detach().clone()
    metrics = learner.update(rollout, gen)
    assert not torch.equal(before, learner.actor.trunk.proj.weight) and all(math.isfinite(v) for v in metrics.values())
    rollout.rewards[0, 0] = float("nan")
    with pytest.raises(M.NonFiniteError):
        learner.update(rollout, gen)


def test_stacked_forward_equals_the_converted_actor(tmp_path):
    from svg_training.nus.actor import NusActor
    rules, deploy, _, _ = load_marker_files(tmp_path / "inputs")
    actors, obs = [], torch.randn(2 + 1, BATCH, rules.guard_count, (rules.guard_count + rules.strike_count) * (2 * 2 * 2 + 1) + 2,
                                  generator=torch.Generator().manual_seed(SEEDS[0]))
    for seed in range(2 + 1):
        folder = write_synthetic_checkpoint(tmp_path / f"c{seed}", "guard", kind="archive", seed=seed)
        actors.append(NusActor.load(folder, team="guard", rules=rules, deploy=deploy))
    first = actors[0]
    stacked = M.stack_trees([M.tree_from_converted(a._params) for a in actors])
    flat = obs.reshape(len(actors), -1, obs.shape[-1])
    means = M.trunk_forward(stacked, flat, bf16=first.bf16, activation=first.activation_name, eps=first.eps, use_norm=first.use_norm)
    for i, actor in enumerate(actors):
        torch.testing.assert_close(means[i].reshape(BATCH, rules.guard_count, -1), actor.mean(obs[i]))


# ---------------------------------------------------------------- one-update parity with the partner's own update
def _flax_pair(d, prefix):
    return (torch.from_numpy(d[f"{prefix}/Dense_0/kernel"].T.copy()), torch.from_numpy(d[f"{prefix}/Dense_0/bias"].copy()))


def _load_trunk(trunk, d, prefix, proj):
    with torch.no_grad():
        pairs = {"proj": f"{prefix}/{proj}", "input": f"{prefix}/network/input", "output": f"{prefix}/network/output"}
        for name, key in pairs.items():
            w, b = _flax_pair(d, key)
            getattr(trunk, name).weight.copy_(w)
            getattr(trunk, name).bias.copy_(b)
        for k, block in enumerate(trunk.blocks):
            for name, layer in block.items():
                key = f"{prefix}/network/block_{k}/{name}"
                if name.startswith("dense"):
                    w, b = _flax_pair(d, key)
                else:
                    w, b = (torch.from_numpy(d[f"{key}/LayerNorm_0/{p}"].copy()) for p in ("scale", "bias"))
                layer.weight.copy_(w)
                layer.bias.copy_(b)


def _flat_like(learner, d, which, actor_prefix, critic_prefix):
    """(actor vector, critic vector) from the export in the learner's parameter order."""
    def collect(module, prefix, proj):
        clone = type(module.trunk)(module.trunk.proj.in_features, module.trunk.output.out_features, learner.method)
        _load_trunk(clone, d, prefix, proj)
        parts = [p.detach().flatten() for p in clone.parameters()]
        if which == "actor":
            parts = [torch.from_numpy(d[f"{prefix}/log_std"].copy())] + parts
        return torch.cat(parts)
    return collect(learner.actor, actor_prefix, "obs_proj") if which == "actor" else collect(learner.critic, critic_prefix, "state_proj")


def _vector(module, actor: bool):
    parts = [p.detach().flatten() for p in module.trunk.parameters()]
    return torch.cat(([module.log_std.detach().flatten()] if actor else []) + parts)


def _grad_vector(grads, actor: bool):
    # parameters() order: log_std first for the actor, then the trunk
    return torch.cat([g.flatten() for g in grads])


def _rel(a, b):
    return (torch.linalg.norm(a - b) / torch.linalg.norm(b)).item()


@pytest.mark.parametrize("dtype", PARITY_DTYPES)
def test_one_update_parity(dtype):
    from dataclasses import replace

    from svg_training.nus import deploy as deploy_mod, method_cfg, rules as rules_mod
    from svg_training.nus.replica_train import NusTrainEnv
    export = ROOT / f"runs/nus_port/phase5/method_port/update_guard_{dtype}.npz"
    paths = (rules_mod.LOCAL_RULES, deploy_mod.LOCAL_DEPLOY, method_cfg.LOCAL_METHOD, export)
    if not all(p.exists() for p in paths):
        pytest.skip("parity export or local files absent (scripts/nus_jax_export_update.py, nus_make_local_*.py): not a pass")
    tol = PARITY_TOL[dtype]
    d = np.load(export)
    deploy = deploy_mod.load_deploy()
    method = replace(method_cfg.load_method(), compute_dtype=dtype)
    env = NusTrainEnv(deploy_mod.apply_overrides(rules_mod.load_rules(), deploy), deploy, method)
    learner = M.Learner(method, env, "guard", seed=1)
    _load_trunk(learner.actor.trunk, d, "actor_before", "obs_proj")
    _load_trunk(learner.critic.trunk, d, "critic_before", "state_proj")
    with torch.no_grad():
        learner.actor.log_std.copy_(torch.from_numpy(d["actor_before/log_std"].copy()))
    actor0, critic0 = _vector(learner.actor, True), _vector(learner.critic, False)
    t = {k: torch.from_numpy(d[k].copy()) for k in ("obs", "central", "latents", "rewards", "dones", "values", "old_logp", "returns",
                                                     "advantages", "entropy_noise")}
    perm = torch.from_numpy(d["permutation"].astype(np.int64))
    # (1) the rollout evaluation and GAE
    with torch.no_grad():
        mean, log_std = learner.actor(t["obs"])
        values, old_logp = learner.critic(t["central"]), M.gaussian_log_prob(t["latents"], mean, log_std)
    returns, adv = M.gae(t["rewards"], t["values"], t["dones"].bool(), learner.gamma, learner.lam)
    res = {"dtype": dtype, "samples": int(perm.numel()), "values_max_abs_err": (values - t["values"]).abs().max().item(),
           "old_logp_max_abs_err": (old_logp - t["old_logp"]).abs().max().item(),
           "gae_returns_max_abs_err": (returns - t["returns"]).abs().max().item(),
           "gae_advantages_max_abs_err": (adv - t["advantages"]).abs().max().item()}
    # (2) one update, one epoch, one minibatch, the partner's permutation and entropy noise
    metrics = learner.update_from(t["obs"], t["central"], t["latents"], t["old_logp"], t["returns"], t["advantages"], None,
                                  minibatches=1, epochs=1, permutations=[perm], entropy_noise=[t["entropy_noise"]], keep_raw_grads=True)
    res["policy_loss_abs_err"] = abs(metrics["policy_loss"] - float(d["metric/policy_loss"]))
    for key in ("value_loss", "entropy"):
        theirs = float(d[f"metric/{key}"])
        res[f"{key}_rel_err"] = abs(metrics[key] - theirs) / abs(theirs)
    actor_grad_theirs = _flat_like(learner, d, "actor", "actor_grad", None)
    critic_grad_theirs = _flat_like(learner, d, "critic", None, "critic_grad")
    actor_grad_ours, critic_grad_ours = _grad_vector(learner.raw_grads["actor"], True), _grad_vector(learner.raw_grads["critic"], False)
    res["actor_grad_rel_err"], res["critic_grad_rel_err"] = _rel(actor_grad_ours, actor_grad_theirs), _rel(critic_grad_ours, critic_grad_theirs)
    res["actor_grad_cosine"] = torch.nn.functional.cosine_similarity(actor_grad_ours, actor_grad_theirs, dim=0).item()
    res["critic_grad_cosine"] = torch.nn.functional.cosine_similarity(critic_grad_ours, critic_grad_theirs, dim=0).item()
    for name, ours_g, theirs_g in (("actor", actor_grad_ours, actor_grad_theirs), ("critic", critic_grad_ours, critic_grad_theirs)):
        both = (ours_g != 0) & (theirs_g != 0)
        res[f"{name}_grad_sign_flip_share_info"] = ((torch.sign(ours_g) != torch.sign(theirs_g)) & both).float().mean().item()
    actor_after = _flat_like(learner, d, "actor", "actor_after", None)
    critic_after = _flat_like(learner, d, "critic", None, "critic_after")
    res["actor_delta_rel_err"] = _rel(_vector(learner.actor, True) - actor0, actor_after - actor0)
    res["critic_delta_rel_err"] = _rel(_vector(learner.critic, False) - critic0, critic_after - critic0)
    # (3) the clip and AdamW alone, on the partner's own gradients
    fresh = M.Learner(method, env, "guard", seed=1)
    for module, prefix, proj, grads, opt in ((fresh.actor, "actor_before", "obs_proj", "actor_grad", fresh.actor_opt),
                                             (fresh.critic, "critic_before", "state_proj", "critic_grad", fresh.critic_opt)):
        _load_trunk(module.trunk, d, prefix, proj)
        _load_trunk_grads(module, d, grads, proj)
        if module is fresh.actor:
            with torch.no_grad():
                module.log_std.copy_(torch.from_numpy(d["actor_before/log_std"].copy()))
        M.clip_global_norm_(list(module.parameters()), method.max_grad_norm)
        opt.step()
    res["adamw_actor_rel_err"] = _rel(_vector(fresh.actor, True) - actor0, actor_after - actor0)
    res["adamw_critic_rel_err"] = _rel(_vector(fresh.critic, False) - critic0, critic_after - critic0)
    out = ROOT / "runs/nus_port/phase5/method_port" / f"m3_parity_{dtype}.json"
    out.write_text(json.dumps(res, indent=2) + "\n")
    print(f"\n[M3 parity {dtype}] {json.dumps(res)}")
    assert res["gae_returns_max_abs_err"] <= tol["gae"] and res["gae_advantages_max_abs_err"] <= tol["gae"]
    assert max(res["adamw_actor_rel_err"], res["adamw_critic_rel_err"]) <= tol["adamw_rel"]
    assert max(res[f"{k}_rel_err"] for k in ("value_loss", "entropy")) <= tol["loss_rel"] and res["policy_loss_abs_err"] <= tol["loss_rel"]
    if tol["values"] is not None:
        assert res["values_max_abs_err"] <= tol["values"] and res["old_logp_max_abs_err"] <= tol["values"]
    if tol["grad_rel"] is not None:
        assert max(res["actor_grad_rel_err"], res["critic_grad_rel_err"]) <= tol["grad_rel"]
    if tol["delta_rel"] is not None:
        assert max(res["actor_delta_rel_err"], res["critic_delta_rel_err"]) <= tol["delta_rel"]


def _ours_on_export(dtype, export):
    """Our learner loaded with an export's initial parameters, after one update on its batch with its draws: (learner, actor delta,
    critic delta), in our parameter order."""
    from dataclasses import replace

    from svg_training.nus import deploy as deploy_mod, method_cfg, rules as rules_mod
    from svg_training.nus.replica_train import NusTrainEnv
    d = np.load(export)
    deploy = deploy_mod.load_deploy()
    method = replace(method_cfg.load_method(), compute_dtype=dtype)
    env = NusTrainEnv(deploy_mod.apply_overrides(rules_mod.load_rules(), deploy), deploy, method)
    learner = M.Learner(method, env, "guard", seed=1)
    _load_trunk(learner.actor.trunk, d, "actor_before", "obs_proj")
    _load_trunk(learner.critic.trunk, d, "critic_before", "state_proj")
    with torch.no_grad():
        learner.actor.log_std.copy_(torch.from_numpy(d["actor_before/log_std"].copy()))
    actor0, critic0 = _vector(learner.actor, True), _vector(learner.critic, False)
    t = {k: torch.from_numpy(d[k].copy()) for k in ("obs", "central", "latents", "old_logp", "returns", "advantages", "entropy_noise")}
    learner.update_from(t["obs"], t["central"], t["latents"], t["old_logp"], t["returns"], t["advantages"], None, minibatches=1, epochs=1,
                        permutations=[torch.from_numpy(d["permutation"].astype(np.int64))], entropy_noise=[t["entropy_noise"]])
    return learner, _vector(learner.actor, True) - actor0, _vector(learner.critic, False) - critic0


def test_bfloat16_update_within_twice_the_noise_floor():
    """Noise-floor rule **v2** (lead, 18 Nov 2026, fixed before any v2 measurement). Floor: K runs of the partner's own bfloat16 update on
    the parity export's batch with every observation and central-state number multiplied by (1 + u x 2^-8), u drawn i.i.d. uniform in
    [-1, 1] per element (about one bfloat16 ulp, relative), seeds 1 to K; floor = the largest relative parameter-update difference
    against the partner's unperturbed bfloat16 update, actor and critic separately. Pass: our bfloat16 update against the partner's
    bfloat16 update <= factor x floor, actor and critic each. K, the scale and the factor are not changed after seeing numbers. INFO:
    the partner's own float32 update against its bfloat16 update on the same batch.

    Rule v1 (same day) was degenerate: a one-float32-ulp nudge never crosses a bfloat16 rounding boundary, so the critic floor was 0 and
    any implementation not bit-identical failed; its numbers stay in m3_noise_floor.json as history. Exports:
    scripts/nus_jax_export_update.py --batch-from (and --perturb-relative-seed, or --perturb-ulp for v1)."""
    from svg_training.nus import deploy as deploy_mod, method_cfg, rules as rules_mod
    folder = ROOT / "runs/nus_port/phase5/method_port"
    names = ["update_guard_bfloat16", "floor_bf16_base", "floor_f32_base"] + [f"floor_bf16_rel{k}" for k in NOISE_FLOOR_SEEDS]
    exports = {k: folder / f"{k}.npz" for k in names}
    if not all(p.exists() for p in (*exports.values(), rules_mod.LOCAL_RULES, deploy_mod.LOCAL_DEPLOY, method_cfg.LOCAL_METHOD)):
        pytest.skip("noise-floor exports or local files absent (scripts/nus_jax_export_update.py --batch-from): not a pass")
    learner, ours_actor, ours_critic = _ours_on_export("bfloat16", exports["update_guard_bfloat16"])
    ours = {"actor": ours_actor, "critic": ours_critic}

    def nus_delta(name, which):
        d = np.load(exports[name])
        args = ("actor_after", None) if which == "actor" else (None, "critic_after")
        before = ("actor_before", None) if which == "actor" else (None, "critic_before")
        return _flat_like(learner, d, which, *args) - _flat_like(learner, d, which, *before)

    res = {"rule": "v2: ours_vs_nus_bf16 <= factor x max over seeds of nus_bf16_relative_perturbation_vs_nus_bf16, actor and critic",
           "factor": NOISE_FLOOR_FACTOR, "seeds": list(NOISE_FLOOR_SEEDS), "relative_scale": "2^-8 x u, u uniform in [-1, 1]"}
    for which in ("actor", "critic"):
        base = nus_delta("floor_bf16_base", which)
        res[f"{which}_base_vs_parity_export"] = _rel(base, nus_delta("update_guard_bfloat16", which))
        runs = [_rel(nus_delta(f"floor_bf16_rel{k}", which), base) for k in NOISE_FLOOR_SEEDS]
        res[f"{which}_floor_runs"] = runs
        res[f"{which}_floor"] = max(runs)
        res[f"{which}_info_nus_f32_vs_nus_bf16"] = _rel(nus_delta("floor_f32_base", which), base)
        res[f"{which}_ours_vs_nus_bf16"] = _rel(ours[which], base)
        res[f"{which}_limit"] = NOISE_FLOOR_FACTOR * res[f"{which}_floor"]
        res[f"{which}_pass"] = res[f"{which}_ours_vs_nus_bf16"] <= res[f"{which}_limit"]
    path = folder / "m3_noise_floor.json"
    old = json.loads(path.read_text()) if path.exists() else {}
    history = old.get("v1_degenerate_history", old if "rule" in old and not str(old["rule"]).startswith("v2") else None)
    path.write_text(json.dumps({"v2": res, "v1_degenerate_history": history}, indent=2) + "\n")
    print(f"\n[M3 noise floor v2] {json.dumps(res)}")
    assert res["actor_pass"] and res["critic_pass"], (
        f"bfloat16 update outside 2 x the partner's floor: actor {res['actor_ours_vs_nus_bf16']:.4g} vs limit {res['actor_limit']:.4g}, "
        f"critic {res['critic_ours_vs_nus_bf16']:.4g} vs limit {res['critic_limit']:.4g}")


def _load_trunk_grads(module, d, prefix, proj):
    shadow = type(module.trunk)(module.trunk.proj.in_features, module.trunk.output.out_features, module.method)
    _load_trunk(shadow, d, prefix, proj)
    for p, g in zip(module.trunk.parameters(), shadow.parameters()):
        p.grad = g.detach().clone()
    if hasattr(module, "log_std"):
        module.log_std.grad = torch.from_numpy(d[f"{prefix}/log_std"].copy())
