"""STE phase L3, slice 3, step 3: the absent-drone mask, as library pieces (design note
ste_learning/drafts/L3_SLICE3_DESIGN.md §1 and its "Revision after the review" B1, A1-A3, B-S). Step 4 wires them into
the learners behind ``[learner] mask_absent`` (default off; off runs none of this).

A slot is absent at a decision when its own-alive flag is 0 in its observation at the decision's first tick; tags are
permanent within a game, so an absent run lasts to its game's end. Every piece takes ``live`` / ``alive`` (bool) and,
with every row live, gives skrl 2.1.0's own result bit for bit (the stock expressions are used on that branch).

* :func:`masked_gae`: GAE with an absent tail passing its team's rewards through (an absent step's effective value is
  its reward-to-go, its advantage 0; a tail cut by the rollout's end ends on ``tail``), advantages normalised over the
  live rows (one live row: the mean only; none: nothing), then the absent rows set to 0 (A2).
* :func:`last_values_prepass` (B1): every agent's V(next observation) in raw units, before any update, in the update's
  own order and under its no_grad and autocast (``skrl/multi_agents/torch/ippo/ippo.py:380-388``).
* :func:`own_last_live`, :func:`team_bootstrap` (A1): a cut tail's bootstrap is the mean of the live mates' raw last
  values (each through its own value scaler); with no live mate, the slot's own value at its last live step discounted
  by gamma^gap; with neither, 0; the counts of each, for the train log.
* :func:`masked_scaler_update` (A2, B-S): a running scaler updated on the live rows only, through skrl's pinned
  ``RunningStandardScaler._parallel_variance``; fewer than two live rows: skipped.
* :func:`masked_optimizer_step` (A2): no optimiser step when the minibatch has no live sample.
* :func:`time_limit_rewards` (A3): the time-limit bootstrap for live slots only.
* :func:`masked_policy_terms`, :func:`masked_value_loss`: the single-head (velocity) PPO terms as means over the live
  rows. The two-level terms take ``live`` in ``two_level.two_level_policy_terms``.
* :func:`check_pins` (B-S): skrl 2.1.0, its ``IPPO.update`` and ``_parallel_variance`` sources as read.

Shapes: T decisions, N games (one agent: one drone slot); rows [T, N, 1] as skrl's memory, or [B, ...] minibatches."""
from __future__ import annotations

import hashlib
import inspect

import skrl
import torch
import torch.nn.functional as F
from skrl.multi_agents.torch.ippo.ippo import compute_gae
from skrl.resources.preprocessors.torch.running_standard_scaler import RunningStandardScaler
from torch import Tensor

# sha256 of inspect.getsource(RunningStandardScaler._parallel_variance) at skrl 2.1.0, read when masked_scaler_update
# was written (24 Nov 2026)
PARALLEL_VARIANCE_SHA256 = "cfcb79ce6dcf2049812f0e96584a22a764c46ea4ffeb5ac7768e60e8fab99608"
# the pre-pass depends on IPPO.record_transition (what it stores) and IPPO.post_interaction (when the updates run, in
# which order): their source sha256 at skrl 2.1.0 (QC of step 4)
RECORD_TRANSITION_SHA256 = "acbb624f46c4556339162af9529348443d156dee7dbc84ecabbd40db1d79d7aa"
POST_INTERACTION_SHA256 = "1c1b4113d893e670ad7cfb3becaa04eccc5bc9ee8a04029cbb6c628314925b5b"
ADV_EPS = 1e-8                     # skrl's compute_gae: (A - mean) / (std + 1e-8) (ippo.py:62)
MIN_SCALER_ROWS = 2                # an unbiased variance needs two rows; fewer live rows: no scaler update


def check_pins() -> None:
    """RuntimeError unless the installed skrl is the one the masked copies were made from (version 2.1.0, its
    ``IPPO.update`` source, ``RunningStandardScaler._parallel_variance``'s source)."""
    from skrl.multi_agents.torch.ippo import IPPO

    from . import two_level                     # here, not at import: two_level imports the mask's learner mixin

    def sha(f) -> str:
        return hashlib.sha256(inspect.getsource(f).encode()).hexdigest()
    if (skrl.__version__ != two_level.SKRL_VERSION or two_level.update_source_sha256() != two_level.IPPO_UPDATE_SHA256
            or sha(RunningStandardScaler._parallel_variance) != PARALLEL_VARIANCE_SHA256
            or sha(IPPO.record_transition) != RECORD_TRANSITION_SHA256
            or sha(IPPO.post_interaction) != POST_INTERACTION_SHA256):
        raise RuntimeError(f"the absent-drone mask copies skrl {two_level.SKRL_VERSION}'s IPPO.update and "
                           f"RunningStandardScaler._parallel_variance; installed skrl {skrl.__version__}: re-read the "
                           f"copies before training")


# ------------------------------------------------------------------------------------------------ GAE
def masked_gae(rewards: Tensor, terminated: Tensor, values: Tensor, last_values: Tensor, alive: Tensor,
               alive_next: Tensor, tail: Tensor, discount: float, lam: float) -> dict:
    """rewards, values [T, N, 1]; terminated, alive [T, N, 1] bool; last_values, tail [N, 1] (raw units);
    alive_next [N, 1] bool (the slot in the observation after the rollout) -> {"returns" [T, N, 1], "advantages"
    [T, N, 1], "live" (int)}. Live steps: skrl's GAE expression; next value of step i: 0 if its game ended, else the
    next step's value if live, its effective value if absent, ``last_values`` / ``tail`` after the last step. Absent
    steps: effective value r + discount * not_done * next, advantage 0, return = their value (not a target).
    Advantages normalised over the live rows, then the absent rows 0. Every row live: skrl's compute_gae itself."""
    if bool(alive.all()) and bool(alive_next.all()):
        returns, advantages = compute_gae(rewards=rewards, terminated=terminated,
                                          truncated=torch.zeros_like(terminated), values=values,
                                          last_values=last_values, discount_factor=discount, lambda_coefficient=lam)
        return {"returns": returns, "advantages": advantages, "live": int(alive.numel())}
    not_done = terminated.logical_not().to(rewards.dtype)        # in the rewards' dtype (float32: skrl's bits)
    t = rewards.shape[0]
    adv = torch.zeros_like(rewards)
    veff = torch.zeros_like(rewards)
    for i in reversed(range(t)):
        if i < t - 1:
            nxt = torch.where(alive[i + 1], values[i + 1], veff[i + 1])
            a_next = torch.where(alive[i + 1], adv[i + 1], torch.zeros_like(adv[i + 1]))
        else:
            nxt = torch.where(alive_next, last_values, tail)
            a_next = torch.zeros_like(last_values)
        live_adv = rewards[i] - values[i] + discount * not_done[i] * (nxt + lam * a_next)
        adv[i] = torch.where(alive[i], live_adv, torch.zeros_like(live_adv))
        veff[i] = torch.where(alive[i], torch.zeros_like(live_adv), rewards[i] + discount * not_done[i] * nxt)
    returns = torch.where(alive, adv + values, values)
    count = int(alive.sum())
    if count == 0:
        return {"returns": returns, "advantages": torch.zeros_like(adv), "live": 0}
    sel = adv[alive]
    mean = sel.mean()
    std = sel.std() if count > 1 else torch.ones((), dtype=adv.dtype, device=adv.device) - ADV_EPS
    norm = (adv - mean) / (std + ADV_EPS)
    return {"returns": returns, "advantages": torch.where(alive, norm, torch.zeros_like(norm)), "live": count}


# ------------------------------------------------------------------------------------------------ the bootstrap
def last_values_prepass(agent) -> dict:
    """B1: {agent name: V(next observation) [N, 1] in raw units} for every agent of an skrl IPPO ``agent``, before any
    update: the update's own last-value step (ippo.py:380-388), in ``possible_agents`` order, under the same
    ``torch.no_grad()`` and autocast."""
    out = {}
    for uid in agent.possible_agents:
        value = agent.values[uid]
        with torch.no_grad(), torch.autocast(device_type=agent._device_type, enabled=agent.cfg.mixed_precision):
            inputs = {
                "observations": agent._observation_preprocessor[uid](agent._current_next_observations[uid]),
                "states": agent._state_preprocessor[uid](agent._current_next_states[uid]),
            }
            value.enable_training_mode(False)
            last_values, _ = value.act(inputs, role="value")
            value.enable_training_mode(True)
            out[uid] = agent._value_preprocessor[uid](last_values, inverse=True)
    return out


def own_last_live(values: Tensor, alive: Tensor) -> tuple[Tensor, Tensor, Tensor]:
    """values [T, N, 1] (raw), alive [T, N, 1] -> (the value at each slot's last live step [N, 1] (0 if none), gap [N]
    long = T - that step's index (decisions to the rollout's end; 0 if none), has [N] bool)."""
    t = values.shape[0]
    idx = torch.arange(t, device=values.device)[:, None]
    a = alive[..., 0]
    last = torch.where(a, idx, -1).amax(0)                                       # [N]
    has = last >= 0
    val = torch.gather(values[..., 0], 0, last.clamp(min=0)[None])[0][:, None]
    return torch.where(has[:, None], val, torch.zeros_like(val)), torch.where(has, t - last, 0), has


def team_bootstrap(last_values: dict, alive_next: dict, own: dict, discount: float) -> dict:
    """A1: per agent of one team, the bootstrap of a tail cut by the rollout's end. last_values {agent: [N, 1] raw}
    (``last_values_prepass``), alive_next {agent: [N] bool}, own {agent: own_last_live(...)} -> {agent: (bootstrap
    [N, 1] raw, {"mates", "own", "none"}: the games, among those where the agent is absent after the rollout, that took
    each rule)}. Rule: the mean of the live mates' raw last values; else the own last live value * discount^gap; else 0.
    The own-value fallback is a heuristic: V(s_L) * discount^(T - L) values the state at the slot's last live step L,
    not the state at the rollout's end T (QC note of step 3); it fires only when no mate is live (Guard team only)."""
    names = list(last_values)
    out = {}
    for a in names:
        mates = [m for m in names if m != a]
        if mates:
            live = torch.stack([alive_next[m] for m in mates]).to(last_values[a].dtype)          # [M-1, N]
            vals = torch.stack([last_values[m][:, 0] for m in mates])
            cnt = live.sum(0)
            mean = (vals * live).sum(0) / cnt.clamp(min=1.0)
        else:
            cnt = torch.zeros_like(last_values[a][:, 0])
            mean = cnt
        val, gap, has = own[a]
        own_v = val[:, 0] * torch.pow(torch.full_like(val[:, 0], discount), gap.to(val.dtype))
        boot = torch.where(cnt > 0, mean, torch.where(has, own_v, torch.zeros_like(own_v)))
        need = ~alive_next[a]
        counts = {"mates": int((need & (cnt > 0)).sum()), "own": int((need & (cnt == 0) & has).sum()),
                  "none": int((need & (cnt == 0) & ~has).sum())}
        out[a] = (boot[:, None], counts)
    return out


# ------------------------------------------------------------------------------------------------ scalers, optimiser
def masked_scaler_update(scaler: RunningStandardScaler, x: Tensor, live: Tensor) -> None:
    """A2: update ``scaler``'s running statistics on the live rows of ``x`` ([B, D] with live [B], or [T, N, D] with
    live [T, N]) through skrl's ``_parallel_variance`` (the call of its ``train=True`` path); every row live: exactly
    that path; fewer than ``MIN_SCALER_ROWS`` live rows: no update."""
    flat = x.reshape(-1, x.shape[-1])
    keep = live.reshape(-1)
    count = int(keep.sum())
    if count < MIN_SCALER_ROWS:
        return
    with torch.no_grad():
        if count == keep.numel():                        # every row live: skrl's own train path, any shape
            scaler(x, train=True)
            return
        sel = flat[keep]
        scaler._parallel_variance(torch.mean(sel, dim=0), torch.var(sel, dim=0), sel.shape[0])


def masked_optimizer_step(grad_scaler, optimizer, live_count: int) -> bool:
    """A2: step (skrl's ``scaler.step`` and ``scaler.update``) only when the minibatch had a live sample; else clear the
    gradients and step nothing (no Adam step on a zero gradient, which would still move its moments). True if
    stepped."""
    if int(live_count) == 0:
        optimizer.zero_grad()
        return False
    grad_scaler.step(optimizer)
    grad_scaler.update()
    return True


def time_limit_rewards(rewards: Tensor, truncated: Tensor, next_values: Tensor, discount: float,
                       alive: Tensor) -> Tensor:
    """A3: skrl's time-limit bootstrap (``rewards += discount * next_values * truncated``, ippo.py:318-326) for the live
    slots only. rewards, truncated, next_values [N, 1]; alive [N] bool."""
    return rewards + discount * next_values * (truncated & alive[:, None])


# ------------------------------------------------------------------------------------------------ losses
def _live_weights(live: Tensor, like: Tensor) -> tuple[Tensor, Tensor]:
    w = live.reshape(-1, *([1] * (like.dim() - 1))).to(like.dtype)
    return w, live.sum().clamp(min=1).to(like.dtype)


def masked_policy_terms(log_prob: Tensor, old_log_prob: Tensor, entropy: Tensor, advantages: Tensor, live: Tensor,
                        ratio_clip: float, entropy_scale: float) -> dict:
    """The single-head PPO terms over the live rows: log_prob, old_log_prob, advantages [B, 1]; entropy [B, ...];
    live [B] bool -> {"policy_loss", "entropy_loss"}. An absent row's log-ratio is 0 (ratio 1) and its weight 0, so
    nothing it stores reaches the loss. Every row live: skrl's expressions (ippo.py:448-459)."""
    if bool(live.all()):
        ratio = torch.exp(log_prob - old_log_prob)
        surrogate = advantages * ratio
        clipped = advantages * torch.clip(ratio, 1.0 - ratio_clip, 1.0 + ratio_clip)
        return {"policy_loss": -torch.min(surrogate, clipped).mean(), "entropy_loss": -entropy_scale * entropy.mean()}
    w, count = _live_weights(live, log_prob)
    log_ratio = torch.where(w > 0, log_prob - old_log_prob, torch.zeros_like(log_prob))
    ratio = torch.exp(log_ratio)
    adv = torch.where(w > 0, advantages, torch.zeros_like(advantages))
    surrogate = adv * ratio
    clipped = adv * torch.clip(ratio, 1.0 - ratio_clip, 1.0 + ratio_clip)
    we, _ = _live_weights(live, entropy)
    per_row = entropy[0].numel()
    ent = torch.where(we > 0, entropy, torch.zeros_like(entropy))        # an absent row's entropy never reaches it
    return {"policy_loss": -(torch.min(surrogate, clipped) * w).sum() / count,
            "entropy_loss": -entropy_scale * (ent * we).sum() / (count * per_row)}


def masked_value_loss(returns: Tensor, predicted: Tensor, sampled_values: Tensor, live: Tensor, value_clip: float,
                      scale: float) -> Tensor:
    """skrl's value loss (ippo.py:463-470: the clipped prediction, ``scale * mse``) over the live rows. [B, 1] each;
    live [B] bool. Every row live: skrl's expression."""
    if value_clip > 0:
        predicted = sampled_values + torch.clip(predicted - sampled_values, min=-value_clip, max=value_clip)
    if bool(live.all()):
        return scale * F.mse_loss(returns, predicted)
    w, count = _live_weights(live, predicted)
    err = torch.where(w > 0, returns - predicted, torch.zeros_like(predicted))
    return scale * (err ** 2 * w).sum() / (count * predicted[0].numel())
