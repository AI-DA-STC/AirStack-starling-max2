"""STE phase L3, slice 3, step 4: the absent-drone mask in the learners (design note
ste_learning/drafts/L3_SLICE3_DESIGN.md §1 and its "Revision after the review"), behind ``[learner] mask_absent``
(default off; off builds none of this).

* :class:`MaskMixin`: what both routes share. ``post_interaction`` runs the pre-pass (B1) before the per-agent updates
  of a rollout (``masking.last_values_prepass``: every agent's raw last value; then each agent's live rows, its own last
  live value and the team bootstrap of a cut absent tail, ``masking.team_bootstrap``); ``_mask_returns`` writes the
  masked GAE and the live-row value-scaler updates into an agent's memory; ``_mask_inputs`` updates the observation
  scaler on a minibatch's live rows (epoch 0) and gives the inputs and the live rows. ``mask_stats``: the live share
  and the bootstrap counts of the last rollout (the train log). The time-limit bootstrap is refused with the mask on
  (A3: every gate keeps it off; refusing is simpler than a fourth copy of skrl's ``record_transition``).
* :class:`MaskedIPPO`: the velocity route. skrl 2.1.0's ``IPPO.update`` (ippo.py:368-540), a third copy, with the
  mask's pieces (``ste/masking.py``); with every row live it computes what stock IPPO does, bit for bit (tested).
  ``two_level.TwoLevelIPPO`` takes the same mixin for the two-level route.

A row is live when the slot's own-alive flag (``ObsView.alive``) is set in the raw observation the memory stores."""
from __future__ import annotations

import itertools
from typing import Any

import torch
import torch.nn as nn
from skrl import config
from skrl.multi_agents.torch.ippo import IPPO
from skrl.resources.schedulers.torch import KLAdaptiveLR

from ..core.observations import ObsView
from . import masking

ALIVE = ObsView.alive
ALIVE_FLAG_MIN = 0.5


def alive_rows(obs: torch.Tensor) -> torch.Tensor:
    """Raw observations [..., D] -> the live flag [...] bool."""
    return obs[..., ALIVE] > ALIVE_FLAG_MIN


class MaskMixin:
    """The absent-drone mask's shared parts (module docstring). Call :meth:`_mask_init` after ``IPPO.__init__``."""

    mask_absent = False

    def _mask_init(self, mask_absent: bool) -> None:
        self.mask_absent = bool(mask_absent)
        self.mask_stats: dict | None = None
        if not self.mask_absent:
            return
        masking.check_pins()
        MaskedIPPO.refuse_time_limit(self.cfg.time_limit_bootstrap)
        discounts = {float(self.cfg.discount_factor[u]) for u in self.possible_agents}
        if len(discounts) != 1:
            raise ValueError(f"the team bootstrap needs one discount factor for the team's agents, got {discounts}")

    @staticmethod
    def refuse_time_limit(setting: Any) -> None:
        values = setting.values() if isinstance(setting, dict) else [setting]
        if any(bool(v) for v in values):
            raise ValueError("time_limit_bootstrap is refused with the absent-drone mask (A3: every gate keeps it off)")

    def post_interaction(self, *, timestep: int, timesteps: int) -> None:
        if (self.mask_absent and self.training and not (self._rollout + 1) % self.cfg.rollouts
                and timestep >= self.cfg.learning_starts):
            self._mask_prepass()
        super().post_interaction(timestep=timestep, timesteps=timesteps)

    def _mask_prepass(self) -> None:
        """B1, A1: before any agent's update: every agent's raw last value, its live rows, its own last live value,
        and the team bootstrap of a tail cut by the rollout's end."""
        last = masking.last_values_prepass(self)
        alive, alive_next, own = {}, {}, {}
        for uid in self.possible_agents:
            mem = self.memories[uid]
            alive[uid] = alive_rows(mem.get_tensor_by_name("observations"))[..., None]          # [T, N, 1]
            alive_next[uid] = alive_rows(self._current_next_observations[uid])                    # [N]
            own[uid] = masking.own_last_live(mem.get_tensor_by_name("values"), alive[uid])
        gamma = float(self.cfg.discount_factor[self.possible_agents[0]])
        boot = masking.team_bootstrap(last, alive_next, own, gamma)
        self._mask = {"last": last, "alive": alive, "alive_next": alive_next,
                      "tail": {uid: boot[uid][0] for uid in self.possible_agents}}
        counts = {k: sum(boot[uid][1][k] for uid in self.possible_agents) for k in ("mates", "own", "none")}
        rows = sum(int(a.numel()) for a in alive.values())
        live = sum(int(a.sum()) for a in alive.values())
        self.mask_stats = {"live_share": live / max(rows, 1), "live_rows": live, "rows": rows, "bootstrap": counts,
                           "time_limit_bootstrap": False}

    def _mask_returns(self, uid: str) -> None:
        """The masked GAE and the live-row value-scaler updates written into the agent's memory (as skrl writes its
        own, ippo.py:393-404)."""
        memory = self.memories[uid]
        m = self._mask
        values = memory.get_tensor_by_name("values")
        out = masking.masked_gae(memory.get_tensor_by_name("rewards"), memory.get_tensor_by_name("terminated"), values,
                                 m["last"][uid], m["alive"][uid], m["alive_next"][uid][:, None], m["tail"][uid],
                                 float(self.cfg.discount_factor[uid]), float(self.cfg.gae_lambda[uid]))
        vp = self._value_preprocessor[uid]
        live = m["alive"][uid][..., 0]
        masking.masked_scaler_update(vp, values, live)
        memory.set_tensor_by_name("values", vp(values))
        masking.masked_scaler_update(vp, out["returns"], live)
        memory.set_tensor_by_name("returns", vp(out["returns"]))
        memory.set_tensor_by_name("advantages", out["advantages"])

    def _mask_inputs(self, uid: str, sampled_observations, sampled_states, epoch: int):
        """(inputs, live [B] bool) of a minibatch: the observation scaler updated on its live rows in epoch 0."""
        live = alive_rows(sampled_observations)
        op = self._observation_preprocessor[uid]
        if not epoch:
            masking.masked_scaler_update(op, sampled_observations, live)
        return {"observations": op(sampled_observations),
                "states": self._state_preprocessor[uid](sampled_states, train=not epoch)}, live


class MaskedIPPO(MaskMixin, IPPO):
    """The velocity route with the absent-drone mask (module docstring): built only when ``[learner] mask_absent`` is
    on. ``update`` is skrl 2.1.0's with the mask's pieces; skrl's tracking keys."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._mask_init(True)

    def update(self, *, timestep: int, timesteps: int, uid: str) -> None:
        policy = self.policies[uid]
        value = self.values[uid]
        memory = self.memories[uid]
        self._mask_returns(uid)                            # replaces skrl's last values, compute_gae and scalers

        cumulative_policy_loss = 0
        cumulative_entropy_loss = 0
        cumulative_value_loss = 0

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
            ) in memory.sample(
                names=self._tensors_names, batch_size=len(memory), mini_batches=self.cfg.mini_batches[uid]
            ):
                with torch.autocast(device_type=self._device_type, enabled=self.cfg.mixed_precision):
                    inputs, live = self._mask_inputs(uid, sampled_observations, sampled_states, epoch)
                    n_live = int(live.sum())
                    _, outputs = policy.act({**inputs, "taken_actions": sampled_actions}, role="policy")
                    next_log_prob = outputs["log_prob"]

                    # approx KL over the live rows (all rows live: skrl's expression)
                    with torch.no_grad():
                        if n_live == live.numel():
                            ratio = next_log_prob - sampled_log_prob
                            kl_divergence = ((torch.exp(ratio) - 1) - ratio).mean()
                        else:
                            ratio = torch.where(live[:, None], next_log_prob - sampled_log_prob,
                                                torch.zeros_like(next_log_prob))
                            kl_divergence = (((torch.exp(ratio) - 1) - ratio) * live[:, None]).sum() / max(n_live, 1)
                        kl_divergences.append(kl_divergence)

                    if self.cfg.kl_threshold[uid] and kl_divergence > self.cfg.kl_threshold[uid]:
                        break

                    scale = self.cfg.entropy_loss_scale[uid]
                    entropy = policy.get_entropy(role="policy") if scale else torch.zeros_like(next_log_prob)
                    terms = masking.masked_policy_terms(next_log_prob, sampled_log_prob, entropy, sampled_advantages,
                                                        live, self.cfg.ratio_clip[uid], scale)
                    entropy_loss = terms["entropy_loss"] if scale else 0
                    policy_loss = terms["policy_loss"]

                    predicted_values, _ = value.act(inputs, role="value")
                    value_loss = masking.masked_value_loss(sampled_returns, predicted_values, sampled_values, live,
                                                           self.cfg.value_clip[uid], self.cfg.value_loss_scale[uid])

                if n_live == 0:                            # A2: no step on a minibatch with no live row
                    self.optimizers[uid].zero_grad()
                    continue
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

                masking.masked_optimizer_step(self.scaler, self.optimizers[uid], n_live)

                cumulative_policy_loss += policy_loss.item()
                cumulative_value_loss += value_loss.item()
                if self.cfg.entropy_loss_scale[uid]:
                    cumulative_entropy_loss += entropy_loss.item()

            if self.schedulers[uid]:
                if isinstance(self.schedulers[uid], KLAdaptiveLR):
                    kl = torch.tensor(kl_divergences, device=self.device).mean()
                    if config.torch.is_distributed:
                        torch.distributed.all_reduce(kl, op=torch.distributed.ReduceOp.SUM)
                        kl /= config.torch.world_size
                    self.schedulers[uid].step(kl.item())
                else:
                    self.schedulers[uid].step()

        steps = self.cfg.learning_epochs[uid] * self.cfg.mini_batches[uid]
        self.track_data(f"Loss / Policy loss ({uid})", cumulative_policy_loss / steps)
        self.track_data(f"Loss / Value loss ({uid})", cumulative_value_loss / steps)
        if self.cfg.entropy_loss_scale[uid]:
            self.track_data(f"Loss / Entropy loss ({uid})", cumulative_entropy_loss / steps)
        self.track_data(f"Policy / Standard deviation ({uid})", policy.distribution(role="policy").stddev.mean().item())
        if self.schedulers[uid]:
            self.track_data(f"Learning / Learning rate ({uid})", self.schedulers[uid].get_last_lr()[0])
