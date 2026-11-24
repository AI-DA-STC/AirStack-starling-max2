"""STE phase L3, slice 2: the two-level learner's PPO step (owner ruling R30; design
ste_learning/drafts/L3_SLICE2_DESIGN.md §2).

Per drone slot i and decision, two heads: the team head (index 0 = "free", then the team strategies) and the drone
head (the skills that do not read team-mates). ``ste/skills.TwoLevelDispatch.resolve_two_level`` gives each sample its
head mask: L_i = 1 for the leader only (its team sample flies), F = 1 for every slot when the leader chose "free" (its
drone sample flies). A masked-out sample does not change the game, so it is left out of the loss.

* :func:`two_level_policy_terms`: per-head ratios, each clipped on its own and weighted by its own mask; per-head
  entropy with its own scale; per-head approx KL (0 for a head with no sample in the minibatch). Means over all samples
  of the minibatch (masked samples add zero).
* :class:`TwoLevelIPPO`: skrl 2.1.0's IPPO with ``init`` (two more memory tensors, ``head_mask`` and ``head_log_prob``,
  size 2, float32), ``act`` (keeps the per-head log-probabilities), ``record_transition`` (stores the masks from
  ``infos["head_mask"]`` and the old per-head log-probabilities; skrl's own ``log_prob`` gets their masked sum) and
  ``update`` (a copy of skrl 2.1.0's ``IPPO.update`` with :func:`two_level_policy_terms` in place of its single ratio
  and single entropy; the KL early stop and ``KLAdaptiveLR`` use the summed per-head KL, the KL of the joint policy over
  the heads in play). QC S1: each per-head KL is a mean over that head's masked-in samples only, so the sum is larger
  than stock's one KL over all samples and the team head's term (few leaders per minibatch) is noisy: a
  ``kl_threshold`` (or ``KLAdaptiveLR``'s) is set for this sum and triggers earlier than the same number would in stock
  skrl; the pinned recipe sets neither. Tracking: skrl's keys and per-head additions (QC N3: left as built). skrl's
  ``entropy_loss_scale`` is not read: the two scales are the ``[learner.entropy_scale]``.
  The copy is pinned: constructing one refuses another skrl version or another ``IPPO.update`` source.
* :func:`free_start_bias`: the start (design choice): with the output layer zeroed, the "free" logit's bias = ln T, so
  p(free) = 0.5 and each team strategy (1 - 0.5) / T; the drone head uniform; the argmax (free, first drone skill).

Shapes: B samples; heads [B, 2] in the order (team, drone). Imports skrl (the training library stays out of core/)."""
from __future__ import annotations

import hashlib
import inspect
import itertools
import math
from typing import Any

import skrl
import torch
import torch.nn as nn
import torch.nn.functional as F
from skrl import config
from skrl.multi_agents.torch import MultiAgent
from skrl.multi_agents.torch.ippo import IPPO
from skrl.multi_agents.torch.ippo.ippo import compute_gae
from skrl.resources.schedulers.torch import KLAdaptiveLR
from torch import Tensor

from .skills import FREE

SKRL_VERSION = "2.1.0"
# sha256 of inspect.getsource(skrl.multi_agents.torch.ippo.IPPO.update) at 2.1.0, when TwoLevelIPPO.update was copied
IPPO_UPDATE_SHA256 = "4ca3138eb33b90e13b3cc94fe44781c8da73eaffd5e43a6a0c560d83dc611490"
SHA_SHOWN_CHARS = 12          # hex characters of a sha256 shown in an error message
HEAD_NAMES = ("team", "drone")


def update_source_sha256() -> str:
    """sha256 of the installed skrl ``IPPO.update`` source."""
    return hashlib.sha256(inspect.getsource(IPPO.update).encode()).hexdigest()


def two_level_policy_terms(head_lp: Tensor, old_head_lp: Tensor, head_entropy: Tensor, mask: Tensor,
                           advantages: Tensor, ratio_clip: float, scales: tuple[float, float]) -> dict[str, Tensor]:
    """head_lp, old_head_lp, head_entropy, mask [B, 2] (team, drone); advantages [B, 1] -> {"policy_loss" (scalar),
    "entropy_loss" (scalar), "entropy_loss_heads" [2], "kl" [2] (no grad), "entropy" [2] (no grad: mean entropy over
    the samples with that head's mask on, nats)}.

    policy loss = sum over heads of -mean_B[ m_h * min(A r_h, A clip(r_h, 1 +- eps)) ], r_h = exp(m_h (lp_h - old_h)):
    a masked sample has ratio exactly 1 and no gradient, whatever its stored action or old log-probability.
    entropy loss = sum over heads of -s_h * mean_B[ m_h * H_h ]. kl_h = mean over the samples with m_h on of
    ((r - 1) - log r), 0 when there is none."""
    m = mask.to(head_lp.dtype)
    log_ratio = (head_lp - old_head_lp) * m
    ratio = torch.exp(log_ratio)
    surrogate = advantages * ratio
    clipped = advantages * torch.clip(ratio, 1.0 - ratio_clip, 1.0 + ratio_clip)
    policy_heads = -(torch.min(surrogate, clipped) * m).mean(0)
    entropy_heads = -torch.as_tensor(scales, dtype=head_lp.dtype, device=head_lp.device) * (m * head_entropy).mean(0)
    with torch.no_grad():
        count = m.sum(0).clamp(min=1.0)
        kl = (((ratio - 1.0) - log_ratio) * m).sum(0) / count
        entropy = (m * head_entropy).sum(0) / count
    return {"policy_loss": policy_heads.sum(), "entropy_loss": entropy_heads.sum(), "entropy_loss_heads": entropy_heads,
            "kl": kl, "entropy": entropy}


def free_start_bias(policy: nn.Module, strategies: int) -> None:
    """Set the "free" logit's bias of ``policy.net``'s output layer to ln(strategies) (after ``zero_mean_head``: p(free)
    = 0.5). The argmax plays "free": the largest team logit for T >= 2, and for T = 1 (ln 1 = 0) tied with the one
    strategy, the tie broken to "free" by the argmax's first index (QC N1)."""
    if strategies < 1:
        raise ValueError("the team head needs at least one team strategy")
    last = [mod for mod in policy.net if isinstance(mod, nn.Linear)][-1]
    with torch.no_grad():
        last.bias[FREE] = math.log(strategies)


class TwoLevelIPPO(IPPO):
    """skrl 2.1.0 IPPO for ``opponents/learned.TwoLevelPolicy`` (module docstring). ``entropy_scale``: {"team": s_team,
    "drone": s_drone}, both > 0. The trained team's agents must be ``possible_agents`` in slot order (the order of
    ``infos["head_mask"]``'s drone axis)."""

    def __init__(self, *, entropy_scale: dict, **kwargs: Any) -> None:
        if skrl.__version__ != SKRL_VERSION or update_source_sha256() != IPPO_UPDATE_SHA256:
            raise RuntimeError(f"TwoLevelIPPO.update is a copy of skrl {SKRL_VERSION}'s IPPO.update; installed skrl "
                               f"{skrl.__version__} (update source sha256 {update_source_sha256()[:SHA_SHOWN_CHARS]}): re-read the "
                               f"copy before training")
        scales = tuple(float(entropy_scale[h]) for h in HEAD_NAMES)
        if not all(math.isfinite(s) and s > 0 for s in scales):
            raise ValueError(f"entropy scales must be > 0, got {entropy_scale}")
        super().__init__(**kwargs)
        self.entropy_scale = scales
        self._current_head_log_prob: dict[str, Tensor] = {}
        self.last_kls: list[Tensor] = []          # [2] per minibatch of the last update (team, drone)

    def init(self, *, trainer_cfg: dict[str, Any] | None = None) -> None:
        super().init(trainer_cfg=trainer_cfg)
        if self.memories:
            for uid in self.possible_agents:
                self.memories[uid].create_tensor(name="head_mask", size=2, dtype=torch.float32)
                self.memories[uid].create_tensor(name="head_log_prob", size=2, dtype=torch.float32)
            self._tensors_names = self._tensors_names + ["head_mask", "head_log_prob"]

    def act(self, observations, states, *, timestep: int, timesteps: int):
        actions, outputs = super().act(observations, states, timestep=timestep, timesteps=timesteps)
        self._current_head_log_prob = {uid: outputs[uid]["head_log_prob"] for uid in self.possible_agents}
        return actions, outputs

    def record_transition(self, *, observations, states, actions, rewards, next_observations, next_states, terminated,
                          truncated, infos, timestep: int, timesteps: int) -> None:
        """skrl's IPPO.record_transition, plus ``head_mask`` (``infos["head_mask"]`` [N, M, 2], slot i = the i-th of
        ``possible_agents``) and ``head_log_prob``; ``log_prob`` = the masked sum of the per-head log-probabilities."""
        MultiAgent.record_transition(self, observations=observations, states=states, actions=actions, rewards=rewards,
                                     next_observations=next_observations, next_states=next_states,
                                     terminated=terminated, truncated=truncated, infos=infos, timestep=timestep,
                                     timesteps=timesteps)
        if not self.training:
            return
        masks = infos["head_mask"]
        if masks.shape[1] != len(self.possible_agents):
            raise ValueError(f"head_mask has {masks.shape[1]} drone slots, the agent {len(self.possible_agents)}")
        slots = [int(uid.rsplit("_", 1)[1]) for uid in self.possible_agents]
        if slots != list(range(len(slots))):            # QC N2: head_mask's drone axis is in slot order
            raise ValueError(f"the trained agents {self.possible_agents} are not in slot order 0..{len(slots) - 1}; "
                             f"head_mask would be read for the wrong drones")
        self._current_next_observations = next_observations
        self._current_next_states = next_states
        for i, uid in enumerate(self.possible_agents):
            if self.cfg.rewards_shaper is not None:
                rewards[uid] = self.cfg.rewards_shaper(rewards[uid], timestep, timesteps)
            if self.cfg.time_limit_bootstrap[uid] and truncated[uid].any():
                with torch.no_grad():
                    inputs = {"observations": self._observation_preprocessor[uid](next_observations[uid]),
                              "states": self._state_preprocessor[uid](next_states[uid])}
                    next_values, _ = self.values[uid].act(inputs, role="value")
                    next_values = self._value_preprocessor[uid](next_values, inverse=True)
                rewards[uid] += self.cfg.discount_factor[uid] * next_values * truncated[uid]
            m = masks[:, i].to(torch.float32)
            hlp = self._current_head_log_prob[uid]
            self.memories[uid].add_samples(observations=observations[uid], states=states[uid], actions=actions[uid],
                                           rewards=rewards[uid], terminated=terminated[uid], truncated=truncated[uid],
                                           log_prob=(hlp * m).sum(-1, keepdim=True),
                                           values=self._current_values[uid], head_mask=m, head_log_prob=hlp)

    def update(self, *, timestep: int, timesteps: int, uid: str) -> None:
        """skrl 2.1.0's ``IPPO.update`` (ippo.py:368-540) with the two-level policy terms; tracking keys as skrl's
        (``Loss / Policy loss``, ``Loss / Value loss``, ``Loss / Entropy loss``, ``Learning / Learning rate``) plus
        ``Loss / Entropy team|drone``, ``Policy / KL team|drone`` and ``Policy / Entropy team|drone``; no
        ``Policy / Standard deviation`` (a categorical head has none)."""
        policy = self.policies[uid]
        value = self.values[uid]
        memory = self.memories[uid]

        # compute returns and advantages (as skrl)
        with torch.no_grad(), torch.autocast(device_type=self._device_type, enabled=self.cfg.mixed_precision):
            inputs = {
                "observations": self._observation_preprocessor[uid](self._current_next_observations[uid]),
                "states": self._state_preprocessor[uid](self._current_next_states[uid]),
            }
            value.enable_training_mode(False)
            last_values, _ = value.act(inputs, role="value")
            value.enable_training_mode(True)
            last_values = self._value_preprocessor[uid](last_values, inverse=True)

        values = memory.get_tensor_by_name("values")
        returns, advantages = compute_gae(
            rewards=memory.get_tensor_by_name("rewards"),
            terminated=memory.get_tensor_by_name("terminated"),
            truncated=memory.get_tensor_by_name("truncated"),
            values=values,
            last_values=last_values,
            discount_factor=self.cfg.discount_factor[uid],
            lambda_coefficient=self.cfg.gae_lambda[uid],
            time_limit_bootstrap=self.cfg.time_limit_bootstrap[uid],
        )

        memory.set_tensor_by_name("values", self._value_preprocessor[uid](values, train=True))
        memory.set_tensor_by_name("returns", self._value_preprocessor[uid](returns, train=True))
        memory.set_tensor_by_name("advantages", advantages)

        cumulative_policy_loss = 0
        cumulative_entropy_loss = 0
        cumulative_value_loss = 0
        cumulative_heads = {k: torch.zeros(2, device=self.device) for k in ("entropy_loss_heads", "kl", "entropy")}
        self.last_kls = []

        for epoch in range(self.cfg.learning_epochs[uid]):
            kl_divergences = []

            for (
                sampled_observations,
                sampled_states,
                sampled_actions,
                sampled_log_prob,
                sampled_values,
                sampled_returns,
                sampled_advantages,
                sampled_head_mask,
                sampled_head_log_prob,
            ) in memory.sample(
                names=self._tensors_names, batch_size=len(memory), mini_batches=self.cfg.mini_batches[uid]
            ):

                with torch.autocast(device_type=self._device_type, enabled=self.cfg.mixed_precision):
                    inputs = {
                        "observations": self._observation_preprocessor[uid](sampled_observations, train=not epoch),
                        "states": self._state_preprocessor[uid](sampled_states, train=not epoch),
                    }

                    _, outputs = policy.act({**inputs, "taken_actions": sampled_actions}, role="policy")
                    terms = two_level_policy_terms(outputs["head_log_prob"], sampled_head_log_prob,
                                                   policy.get_entropy(role="policy"), sampled_head_mask,
                                                   sampled_advantages, self.cfg.ratio_clip[uid], self.entropy_scale)

                    # approx KL: the sum of the per-head KLs (the KL of the joint policy over the heads in play)
                    kl_divergence = terms["kl"].sum()
                    kl_divergences.append(kl_divergence)
                    self.last_kls.append(terms["kl"].detach())

                    # early stopping with KL divergence
                    if self.cfg.kl_threshold[uid] and kl_divergence > self.cfg.kl_threshold[uid]:
                        break

                    entropy_loss = terms["entropy_loss"]
                    policy_loss = terms["policy_loss"]

                    # compute value loss (as skrl)
                    predicted_values, _ = value.act(inputs, role="value")

                    if self.cfg.value_clip[uid] > 0:
                        predicted_values = sampled_values + torch.clip(
                            predicted_values - sampled_values,
                            min=-self.cfg.value_clip[uid],
                            max=self.cfg.value_clip[uid],
                        )
                    value_loss = self.cfg.value_loss_scale[uid] * F.mse_loss(sampled_returns, predicted_values)

                # optimization step (as skrl)
                self.optimizers[uid].zero_grad()
                self.scaler.scale(policy_loss + entropy_loss + value_loss).backward()

                if config.torch.is_distributed:
                    policy.reduce_parameters()
                    if policy is not value:
                        value.reduce_parameters()

                if self.cfg.grad_norm_clip[uid] > 0:
                    self.scaler.unscale_(self.optimizers[uid])
                    if policy is value:
                        nn.utils.clip_grad_norm_(policy.parameters(), self.cfg.grad_norm_clip[uid])
                    else:
                        nn.utils.clip_grad_norm_(
                            itertools.chain(policy.parameters(), value.parameters()), self.cfg.grad_norm_clip[uid]
                        )

                self.scaler.step(self.optimizers[uid])
                self.scaler.update()

                cumulative_policy_loss += policy_loss.item()
                cumulative_value_loss += value_loss.item()
                cumulative_entropy_loss += entropy_loss.item()
                for k in cumulative_heads:
                    cumulative_heads[k] = cumulative_heads[k] + terms[k].detach()

            # update learning rate (as skrl)
            if self.schedulers[uid]:
                if isinstance(self.schedulers[uid], KLAdaptiveLR):
                    kl = torch.tensor(kl_divergences, device=self.device).mean()
                    if config.torch.is_distributed:
                        torch.distributed.all_reduce(kl, op=torch.distributed.ReduceOp.SUM)
                        kl /= config.torch.world_size
                    self.schedulers[uid].step(kl.item())
                else:
                    self.schedulers[uid].step()

        # record data (skrl's keys, and the heads')
        steps = self.cfg.learning_epochs[uid] * self.cfg.mini_batches[uid]
        self.track_data(f"Loss / Policy loss ({uid})", cumulative_policy_loss / steps)
        self.track_data(f"Loss / Value loss ({uid})", cumulative_value_loss / steps)
        self.track_data(f"Loss / Entropy loss ({uid})", cumulative_entropy_loss / steps)
        heads = {k: (v / steps).tolist() for k, v in cumulative_heads.items()}
        for h, name in enumerate(HEAD_NAMES):
            self.track_data(f"Loss / Entropy {name} ({uid})", heads["entropy_loss_heads"][h])
            self.track_data(f"Policy / KL {name} ({uid})", heads["kl"][h])
            self.track_data(f"Policy / Entropy {name} ({uid})", heads["entropy"][h])

        if self.schedulers[uid]:
            self.track_data(f"Learning / Learning rate ({uid})", self.schedulers[uid].get_last_lr()[0])
