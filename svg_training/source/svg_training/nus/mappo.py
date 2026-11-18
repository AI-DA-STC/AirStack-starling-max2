"""The partner's MAPPO learner in PyTorch (NUS port Phase 5, task M3), described from ``ma_skills/jax/policy.py``, ``nn.py``,
``training.py`` and ``runner/fixed_opponent_runner.py`` (plan section 4.1, items 8 to 14); no line of the partner's code is copied.

* **Network** (actor and critic share the shape): a projection to half the trunk width, an input layer, pre-norm residual blocks
  (LayerNorm, activation, dense, twice, plus the block input), an output layer. With ``compute_dtype = "bfloat16"`` the trunk is
  computed in bfloat16 with the cast points of the converted actor (``nus/actor.py``); parameters stay float32. Dense kernels start
  from a fan-in truncated normal, biases at zero, LayerNorm at one and zero; the actor's output layer is orthogonal with a small gain
  (or zero); the critic's output layer is a truncated normal like the rest.
* **Actor head**: the mean in float32 and a learned state-independent log standard deviation per axis, clipped to its bounds. A latent
  is drawn (mean + std x noise, or the mean when deterministic); the action is tanh(latent) x team speed, projected onto the speed disk.
  **The latent is stored**; the log probability is the Gaussian density at the stored latent, without the tanh Jacobian.
* **Entropy**: the squashed policy's entropy at fresh reparameterised samples (Gaussian entropy + the tanh log-Jacobian at the sample).
* **GAE** with the team's discount and lambda, bootstrap 0 at the time limit; one value per game; advantages normalised over the whole
  batch (population variance plus an epsilon), clipped, times the team's advantage weight; returns = advantages + values.
* **PPO**: epochs x minibatches over (time x games) samples, a fresh permutation per epoch; per minibatch the actor step (clipped
  surrogate with the log ratio clipped, minus the entropy bonus) then the critic step (coefficient x squared error, no value clip).
  Actor and critic each have an AdamW (decoupled weight decay; betas and epsilon at the library defaults, which equal the partner's)
  behind a global-norm clip that leaves a gradient below the limit unchanged and scales one above it to the limit.
* A non-finite metric aborts the update (``NonFiniteError``).

Shapes: N games, A drones of the learner's team, D observation width, S central-state width, T steps. Everything in a rollout and an
update is batched over games (a Python loop over steps, epochs and minibatches only). This file holds no partner value (G2).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

import numpy as np
import torch
from torch import nn

from .actor import ACTIVATIONS
from .method_cfg import NusMethod, team_value
from .replica_train import NusTrainEnv, TrainState

TEAM_CODE = {"guard": 1, "strike": 2}  # the partner seeds a fresh learner from the stage seed and this code
ACTION_DIM = 2


class NonFiniteError(RuntimeError):
    """A non-finite training metric: the partner's runner aborts the run here."""


# ------------------------------------------------------------------------------------------------ network
class Trunk(nn.Module):
    """Parameter store of the partner's network: ``proj`` (in -> hidden / 2), ``input`` (hidden / 2 -> hidden), ``blocks`` (norm_0,
    dense_0, norm_1, dense_1), ``output`` (hidden -> out). The forward pass is :func:`trunk_forward` on :meth:`tree`."""

    def __init__(self, in_dim: int, out_dim: int, method: NusMethod):
        super().__init__()
        hidden = method.hidden_dim
        self.proj = nn.Linear(in_dim, hidden // 2)
        self.input = nn.Linear(hidden // 2, hidden)
        self.blocks = nn.ModuleList()
        for _ in range(method.hidden_blocks):
            block = nn.ModuleDict({"dense_0": nn.Linear(hidden, hidden), "dense_1": nn.Linear(hidden, hidden)})
            if method.use_layernorm:
                block["norm_0"], block["norm_1"] = nn.LayerNorm(hidden), nn.LayerNorm(hidden)
            self.blocks.append(block)
        self.output = nn.Linear(hidden, out_dim)

    def tree(self) -> dict:
        """The functional layout: {"proj", "input", "output": (weight (out, in), bias), "blocks": [{name: (weight, bias)}]}."""
        return {"proj": (self.proj.weight, self.proj.bias), "input": (self.input.weight, self.input.bias),
                "output": (self.output.weight, self.output.bias),
                "blocks": [{name: (layer.weight, layer.bias) for name, layer in block.items()} for block in self.blocks]}


def _linear(x: torch.Tensor, layer: tuple[torch.Tensor, torch.Tensor], bf16: bool) -> torch.Tensor:
    weight, bias = layer
    if bf16:
        weight, bias = weight.to(torch.bfloat16), bias.to(torch.bfloat16)
    if weight.dim() == 2 + 1:  # stacked parameters (L, out, in) and inputs (L, B, in)
        return torch.matmul(x, weight.transpose(-1, -2)) + bias.unsqueeze(-2)
    return torch.matmul(x, weight.transpose(-1, -2)) + bias  # product and bias add are separate roundings, as in the partner's graph


def _layer_norm(x: torch.Tensor, layer: tuple[torch.Tensor, torch.Tensor], eps: float, bf16: bool) -> torch.Tensor:
    scale, bias = layer
    if scale.dim() == 2:  # stacked
        scale, bias = scale.unsqueeze(-2), bias.unsqueeze(-2)
    xf = x.float()
    mean = xf.mean(-1, keepdim=True)
    var = (xf - mean).square().mean(-1, keepdim=True)
    y = (xf - mean) * (torch.rsqrt(var + eps) * scale) + bias
    return y.to(torch.bfloat16) if bf16 else y


def trunk_forward(tree: dict, x: torch.Tensor, *, bf16: bool, activation: str, eps: float, use_norm: bool) -> torch.Tensor:
    """The network on inputs (..., in), or on stacked inputs (L, B, in) with stacked parameters; returns float32 (..., out)."""
    act = ACTIVATIONS[activation][1 if bf16 else 0]
    x = x.float()
    if bf16:
        x = x.to(torch.bfloat16)
    x = _linear(_linear(x, tree["proj"], bf16), tree["input"], bf16)
    for block in tree["blocks"]:
        h = act(_layer_norm(x, block["norm_0"], eps, bf16)) if use_norm else act(x)
        h = _linear(h, block["dense_0"], bf16)
        h = act(_layer_norm(h, block["norm_1"], eps, bf16)) if use_norm else act(h)
        h = _linear(h, block["dense_1"], bf16)
        x = x + h
    return _linear(x, tree["output"], bf16).float()


def _init_trunk(trunk: Trunk, method: NusMethod, generator: torch.Generator, output: str) -> None:
    """Fan-in truncated normal kernels, zero biases, LayerNorm one and zero; the output layer per ``output`` ("orthogonal", "zero" or
    "normal")."""
    def normal_(layer: nn.Linear) -> None:
        std = method.init_std_scale / math.sqrt(layer.weight.shape[1])
        bound = method.init_truncation * std
        nn.init.trunc_normal_(layer.weight, mean=0, std=std, a=-bound, b=bound, generator=generator)
        nn.init.zeros_(layer.bias)

    with torch.no_grad():
        for module in trunk.modules():
            if isinstance(module, nn.Linear):
                normal_(module)
            elif isinstance(module, nn.LayerNorm):
                nn.init.ones_(module.weight)
                nn.init.zeros_(module.bias)
        if output == "orthogonal":
            nn.init.orthogonal_(trunk.output.weight, gain=method.output_init_gain, generator=generator)
        elif output == "zero":
            nn.init.zeros_(trunk.output.weight)


class MappoActor(nn.Module):
    """The learner's actor: observations (..., D) -> (mean (..., 2) float32, clipped log std (..., 2))."""

    def __init__(self, obs_dim: int, method: NusMethod, layernorm_epsilon: float, generator: torch.Generator | None = None):
        super().__init__()
        self.method, self.eps = method, layernorm_epsilon
        self.trunk = Trunk(obs_dim, ACTION_DIM, method)
        self.log_std = nn.Parameter(torch.full((ACTION_DIM,), method.initial_log_std))
        _init_trunk(self.trunk, method, generator or torch.Generator().manual_seed(0),
                    "zero" if method.zero_init_output else "orthogonal")

    def forward(self, obs: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        m = self.method
        mean = trunk_forward(self.trunk.tree(), obs, bf16=m.compute_dtype == "bfloat16", activation=m.activation, eps=self.eps,
                             use_norm=m.use_layernorm)
        log_std = self.log_std.clamp(m.log_std_min, m.log_std_max)
        return mean, log_std.expand_as(mean)


class MappoCritic(nn.Module):
    """The team critic: central states (..., S) -> values (...,) float32."""

    def __init__(self, state_dim: int, method: NusMethod, layernorm_epsilon: float, generator: torch.Generator | None = None):
        super().__init__()
        self.method, self.eps = method, layernorm_epsilon
        self.trunk = Trunk(state_dim, 1, method)
        _init_trunk(self.trunk, method, generator or torch.Generator().manual_seed(0), "normal")

    def forward(self, state: torch.Tensor) -> torch.Tensor:
        m = self.method
        return trunk_forward(self.trunk.tree(), state, bf16=m.compute_dtype == "bfloat16", activation=m.activation, eps=self.eps,
                             use_norm=m.use_layernorm)[..., 0]


def tree_from_converted(params: dict) -> dict:
    """The functional layout from a converted actor's parameters (``NusActor._params``: ``obs_proj``, ``input``, ``blocks`` with
    ``dense_*`` and ``norm_*``, ``output``; weights possibly bfloat16, which converts back to float32 exactly)."""
    def f(pair):
        return tuple(t.float() for t in pair)
    return {"proj": f(params["obs_proj"]), "input": f(params["input"]), "output": f(params["output"]),
            "blocks": [{name: f(pair) for name, pair in block.items()} for block in params["blocks"]]}


def stack_trees(trees: list[dict]) -> dict:
    """Stack equal-shaped parameter trees along a new leading axis (one batched call serves every entry)."""
    def s(pairs):
        return tuple(torch.stack(t) for t in zip(*pairs))
    return {"proj": s([t["proj"] for t in trees]), "input": s([t["input"] for t in trees]), "output": s([t["output"] for t in trees]),
            "blocks": [{name: s([t["blocks"][k][name] for t in trees]) for name in trees[0]["blocks"][k]}
                       for k in range(len(trees[0]["blocks"]))]}


# ------------------------------------------------------------------------------------------------ distribution
def project_to_disk(actions: torch.Tensor, max_speed: float, floor: float) -> torch.Tensor:
    norm = torch.linalg.norm(actions, dim=-1, keepdim=True)
    return actions * torch.clamp(max_speed / norm.clamp_min(floor), max=1)


def squash(latent: torch.Tensor, max_speed: float, floor: float) -> torch.Tensor:
    """Executed action of a latent: tanh x speed, projected onto the speed disk."""
    return project_to_disk(torch.tanh(latent) * max_speed, max_speed, floor)


def gaussian_log_prob(latent: torch.Tensor, mean: torch.Tensor, log_std: torch.Tensor) -> torch.Tensor:
    """Log density of the pre-squash Gaussian at the stored latent, summed over the action axes: (..., 2) -> (...)."""
    z = (latent - mean) * torch.exp(-log_std)
    return (-(z.square() + 2 * log_std + math.log(2 * math.pi)) / 2).sum(-1)


def tanh_log_jacobian(latent: torch.Tensor) -> torch.Tensor:
    """sum log(1 - tanh(x)^2) in the saturation-safe form 2 (log 2 - x - softplus(-2 x)): (..., 2) -> (...)."""
    return (2 * (math.log(2) - latent - nn.functional.softplus(-2 * latent))).sum(-1)


def gaussian_entropy(log_std: torch.Tensor) -> torch.Tensor:
    return (log_std + (math.log(2 * math.pi) + 1) / 2).sum(-1)


def transformed_entropy(mean: torch.Tensor, log_std: torch.Tensor, noise: torch.Tensor) -> torch.Tensor:
    """Entropy of the squashed policy at the reparameterised sample mean + std x noise: (..., 2) -> (...)."""
    return gaussian_entropy(log_std) + tanh_log_jacobian(mean + torch.exp(log_std) * noise)


# ------------------------------------------------------------------------------------------------ advantages
def gae(rewards: torch.Tensor, values: torch.Tensor, dones: torch.Tensor, gamma: float, lam: float,
        last_values: torch.Tensor | None = None) -> tuple[torch.Tensor, torch.Tensor]:
    """(returns, advantages), both (T, N), from rewards, values and done flags (T, N); bootstrap ``last_values`` (N,) or 0."""
    nxt = torch.zeros_like(values[0]) if last_values is None else last_values
    running = torch.zeros_like(values[0])
    out = torch.empty_like(values)
    for t in range(values.shape[0] - 1, -1, -1):
        live = 1 - dones[t].float()
        delta = rewards[t] + gamma * nxt * live - values[t]
        running = delta + gamma * lam * live * running
        out[t] = running
        nxt = values[t]
    return out + values, out


def normalise_advantages(advantages: torch.Tensor, method: NusMethod) -> torch.Tensor:
    """Whole-batch normalisation (population variance plus the epsilon), clipped."""
    mean = advantages.mean()
    var = (advantages - mean).square().mean()
    return ((advantages - mean) / torch.sqrt(var + method.advantage_epsilon)).clamp(-method.advantage_clip, method.advantage_clip)


def clip_global_norm_(parameters: list[nn.Parameter], max_norm: float) -> torch.Tensor:
    """Leave the gradients unchanged when their global norm is below ``max_norm``; otherwise scale them to it. Returns the norm."""
    grads = [p.grad for p in parameters if p.grad is not None]
    norm = torch.sqrt(sum(g.float().square().sum() for g in grads))
    scale = torch.where(norm < max_norm, torch.ones_like(norm), max_norm / norm)
    for g in grads:
        g.mul_(scale)
    return norm


# ------------------------------------------------------------------------------------------------ rollout and learner
@dataclass
class Rollout:
    """Time-major batch: ``obs`` (T, N, A, D), ``central`` (T, N, S), ``latents`` (T, N, A, 2), ``rewards`` (T, N) of the learner's
    team, ``dones`` (T, N), ``reached`` (N,) the sticky reached flag at the end, ``slot_ids`` (N,)."""

    obs: torch.Tensor
    central: torch.Tensor
    latents: torch.Tensor
    rewards: torch.Tensor
    dones: torch.Tensor
    reached: torch.Tensor
    slot_ids: torch.Tensor


def stage_generator(seed: int, team: str, stream: int, device: torch.device | str = "cpu") -> torch.Generator:
    """A torch generator from (stage seed, team code, stream): our initialisation follows the partner's rule (stage seed and team code)
    with our own generator."""
    state = np.random.SeedSequence([int(seed), TEAM_CODE[team], int(stream)]).generate_state(1, dtype=np.uint64)[0]
    return torch.Generator(device=device).manual_seed(int(state) >> 1)


class Learner:
    """A fresh learner of one team: actor, critic and their optimisers (plan section 4.1, items 2, 8-14)."""

    def __init__(self, method: NusMethod, env: NusTrainEnv, team: str, seed: int, device: torch.device | str = "cpu"):
        if team not in TEAM_CODE:
            raise ValueError(f"team must be 'guard' or 'strike', got {team!r}")
        self.method, self.team, self.device = method, team, torch.device(device)
        eps, self.floor = env.deploy.layernorm_epsilon, env.deploy.disk_floor
        self.max_speed = env.team_speed(team)
        self.actor = MappoActor(env.obs_dim, method, eps, stage_generator(seed, team, 0)).to(self.device)
        self.critic = MappoCritic(env.state_dim, method, eps, stage_generator(seed, team, 1)).to(self.device)
        wd = method.weight_decay
        self.actor_opt = torch.optim.AdamW(self.actor.parameters(), lr=team_value(method, team, "actor_lr"), weight_decay=wd)
        self.critic_opt = torch.optim.AdamW(self.critic.parameters(), lr=team_value(method, team, "critic_lr"), weight_decay=wd)
        self.gamma = team_value(method, team, "gamma")
        self.lam = team_value(method, team, "gae_lambda")
        self.advantage_weight = team_value(method, team, "advantage_weight")
        # the batch shape: the copied method's minibatch count, or a variant's (5.1b/5.1c), which may drop the few samples a
        # permutation leaves over when (time x games) does not divide into the minibatches
        self.minibatches, self.drop_remainder = method.ppo_minibatches, False
        # most drone rows the rollout evaluation passes through the networks at once (bounded memory at 16,384 games x 200 steps)
        self.eval_rows = 2 ** (2 * 2 * 2 * 2)

    # ------------------------------------------------------------------ acting
    @torch.no_grad()
    def act(self, obs: torch.Tensor, generator: torch.Generator | None, deterministic: bool) -> tuple[torch.Tensor, torch.Tensor]:
        """Observations (N, A, D) -> (actions (N, A, 2), latents (N, A, 2))."""
        mean, log_std = self.actor(obs)
        if deterministic:
            latent = mean
        else:
            noise = torch.randn(mean.shape, generator=generator, device=mean.device, dtype=mean.dtype)
            latent = mean + torch.exp(log_std) * noise
        return squash(latent, self.max_speed, self.floor), latent

    @torch.no_grad()
    def collect(self, env: NusTrainEnv, state: TrainState, generator: torch.Generator, steps: int,
                opponent: Callable[[TrainState, torch.Generator], torch.Tensor], slot_ids: torch.Tensor | None = None,
                deterministic: bool = False) -> Rollout:
        """Play ``steps`` joint steps from ``state``; ``opponent(state, generator)`` gives the other team's actions (N, other size, 2).
        Stored per step: the learner's observations, the central state before the step, the latents, the learner team's reward."""
        n = state.game.pos.shape[0]
        slot_ids = torch.zeros(n, dtype=torch.long, device=self.device) if slot_ids is None else slot_ids
        obs_t, central_t, latents_t, rewards_t, dones_t = [], [], [], [], []
        sign = 1 if self.team == "guard" else -1
        for _ in range(steps):
            guard_obs, strike_obs = env.observe(state)
            own = guard_obs if self.team == "guard" else strike_obs
            actions, latents = self.act(own, generator, deterministic)
            other = opponent(state, generator)
            central_t.append(env.central_state(state, slot_ids))
            g_act, s_act = (actions, other) if self.team == "guard" else (other, actions)
            state, out = env.step(state, g_act, s_act, self.gamma)
            obs_t.append(own)
            latents_t.append(latents)
            rewards_t.append(sign * out.guard_reward)
            dones_t.append(out.time_limit)
        return Rollout(torch.stack(obs_t), torch.stack(central_t), torch.stack(latents_t), torch.stack(rewards_t),
                       torch.stack(dones_t), state.game.reached > 0, slot_ids)

    # ------------------------------------------------------------------ learning
    @torch.no_grad()
    def evaluate(self, rollout: Rollout) -> tuple[torch.Tensor, torch.Tensor]:
        """(values (T, N), log probabilities of the stored latents (T, N, A)) with the current parameters, in chunks of at most
        ``eval_rows`` drone rows (at least one sample per chunk)."""
        t, n, a = rollout.obs.shape[:2 + 1]
        obs, central = rollout.obs.reshape(t * n, a, -1), rollout.central.reshape(t * n, -1)
        latents = rollout.latents.reshape(t * n, a, -1)
        step = max(self.eval_rows // a, 1)
        values, logp = [], []
        for begin in range(0, t * n, step):
            part = slice(begin, begin + step)
            mean, log_std = self.actor(obs[part])
            values.append(self.critic(central[part]))
            logp.append(gaussian_log_prob(latents[part], mean, log_std))
        return torch.cat(values).reshape(t, n), torch.cat(logp).reshape(t, n, a)

    def update(self, rollout: Rollout, generator: torch.Generator | None = None, *, permutations: list[torch.Tensor] | None = None,
               entropy_noise: list[torch.Tensor] | None = None) -> dict[str, float]:
        """One PPO update on a rollout. ``permutations`` (one (T x N,) index per epoch) and ``entropy_noise`` (one (minibatch, A, 2) per
        minibatch, in order) replace the generator's draws in the parity test."""
        m = self.method
        values, old_logp = self.evaluate(rollout)
        returns, advantages = gae(rollout.rewards, values, rollout.dones, self.gamma, self.lam)
        return self.update_from(rollout.obs, rollout.central, rollout.latents, old_logp, returns, advantages, generator,
                                permutations=permutations, entropy_noise=entropy_noise, minibatches=self.minibatches, epochs=m.ppo_epochs,
                                drop_remainder=self.drop_remainder)

    def update_from(self, obs: torch.Tensor, central: torch.Tensor, latents: torch.Tensor, old_logp: torch.Tensor,
                    returns: torch.Tensor, advantages: torch.Tensor, generator: torch.Generator | None, *, minibatches: int, epochs: int,
                    permutations: list[torch.Tensor] | None = None, entropy_noise: list[torch.Tensor] | None = None,
                    keep_raw_grads: bool = False, drop_remainder: bool = False) -> dict[str, float]:
        """The PPO epochs on a prepared batch: ``obs`` (T, N, A, D), ``central`` (T, N, S), ``latents`` (T, N, A, 2), ``old_logp``
        (T, N, A), ``returns`` and ``advantages`` (T, N). ``keep_raw_grads`` keeps the last minibatch's gradients before the clip in
        ``self.raw_grads`` (parity test)."""
        m = self.method
        t, n, a = obs.shape[:2 + 1]
        samples = t * n
        if samples % minibatches and not drop_remainder:
            raise ValueError("time x games must divide into the minibatches")
        size = samples // minibatches
        obs, central = obs.reshape(samples, a, -1), central.reshape(samples, -1)
        latents, old_logp = latents.reshape(samples, a, ACTION_DIM).float(), old_logp.reshape(samples, a)
        returns = returns.reshape(samples)
        adv = self.advantage_weight * normalise_advantages(advantages.reshape(samples), m)
        actor_params, critic_params = list(self.actor.parameters()), list(self.critic.parameters())
        totals: dict[str, torch.Tensor] = {}
        k = 0
        for epoch in range(epochs):
            perm = permutations[epoch] if permutations is not None else torch.randperm(samples, generator=generator, device=obs.device)
            for b in range(minibatches):
                idx = perm[b * size:(b + 1) * size]
                mean, log_std = self.actor(obs[idx])
                logp = gaussian_log_prob(latents[idx], mean, log_std)
                noise = (entropy_noise[k] if entropy_noise is not None
                         else torch.randn(mean.shape, generator=generator, device=mean.device, dtype=mean.dtype))
                entropy = transformed_entropy(mean, log_std, noise).mean()
                log_ratio = (logp - old_logp[idx]).clamp(-m.log_ratio_clip, m.log_ratio_clip)
                ratio = torch.exp(log_ratio)
                a_b = adv[idx][:, None]
                surrogate = torch.minimum(ratio * a_b, ratio.clamp(1 - m.ppo_clip, 1 + m.ppo_clip) * a_b)
                policy_loss = -surrogate.mean()
                self.actor_opt.zero_grad(set_to_none=True)
                (policy_loss - m.entropy_coef * entropy).backward()
                if keep_raw_grads:
                    self.raw_grads = {"actor": [p.grad.detach().clone() for p in actor_params]}
                actor_norm = clip_global_norm_(actor_params, m.max_grad_norm)
                self.actor_opt.step()

                value_loss = (returns[idx] - self.critic(central[idx])).square().mean()
                self.critic_opt.zero_grad(set_to_none=True)
                (m.critic_loss_coef * value_loss).backward()
                if keep_raw_grads:
                    self.raw_grads["critic"] = [p.grad.detach().clone() for p in critic_params]
                critic_norm = clip_global_norm_(critic_params, m.max_grad_norm)
                self.critic_opt.step()
                with torch.no_grad():
                    step_metrics = {"policy_loss": policy_loss, "value_loss": value_loss, "entropy": entropy,
                                    "clip_frac": ((ratio - 1).abs() > m.ppo_clip).float().mean(), "ratio": ratio.mean(),
                                    "approx_kl": ((ratio - 1) - log_ratio).mean(), "policy_grad_norm": actor_norm,
                                    "value_grad_norm": critic_norm}
                for key, value in step_metrics.items():
                    totals[key] = totals.get(key, torch.zeros((), device=obs.device)) + value.detach().float()
                k += 1
        metrics = {key: float(value / k) for key, value in totals.items()}
        metrics["returns_mean"] = float(returns.mean())
        metrics["advantages_mean"] = float(advantages.mean())
        bad = sorted(key for key, value in metrics.items() if not math.isfinite(value))
        if bad:
            raise NonFiniteError(f"non-finite training metrics: {bad}")
        return metrics
