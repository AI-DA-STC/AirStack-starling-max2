"""Batched port of CMU's collision filter (``svg_ground_control/cbf_filter.py``) with a team mask.

Shapes: ``N`` games, ``M`` drones per game, ``P = M (M - 1) / 2`` unordered pairs (``triu_indices``).

Same mathematics as the flight stack's ``filter_velocities``:

* barrier per pair ``h_ij = |p_i - p_j|^2 - (2 r)^2``;
* constraint ``2 (p_i - p_j) . (v_i - v_j) + alpha h_ij >= 0`` (gradient ``g = 2 (p_i - p_j)``,
  bias ``alpha h``) and the speed cap ``|v_i| <= v_max``;
* pairs that no capped velocities can violate (``bias >= |g| (v_max,i + v_max,j)``) are pruned;
* parallel (product-space) Dykstra: each sweep projects onto every active half-space and every speed
  ball at once and averages per drone, weighted by (active pairs + 1);
* a drone group stops updating at the first sweep where its residual and its largest per-sweep change
  are both <= ``tolerance`` (the original's stopping test, so up to the original's own sweep count the
  two run identical sequences);
* after the sweeps: non-finite rows -> 0, over-cap rows scaled back to the cap;
* emergency push-apart, per group, when a row was non-finite, or a pair is coincident
  (``|g| < 1e-5`` and ``bias < -tolerance``), or the residual after the clamp exceeds ``5 tolerance``.
  Each still-violated pair pushes its drones apart along ``g`` at ``min(v_max, 0.5 v_max + 0.1 max(0, -h))``.

Differences from the original, by design:

* A fixed number of parallel sweeps (``iterations``, the only loop), with converged groups frozen; no
  Gauss-Seidel polish phase. The original falls back to up to 200 sequential Gauss-Seidel sweeps when
  its 200 parallel sweeps do not converge; that phase cannot be batched without a loop over pairs. In
  those scenes the port keeps sweeping in parallel, towards the same projection by a different path.
* The original also takes the emergency action when its solver did not converge. With a fixed budget
  that clause would turn slow but feasible scenes into push-aparts, so the port leaves it out (measured
  on development seed 1, 2,000 scenes: emergency agreement 0.9990 with the clause, 1.0000 without, at
  1,000 sweeps). An unconverged group whose residual is at most ``5 tolerance`` keeps its sweep result.
* Pairs outside ``pair_mask`` are dropped entirely: no constraint, no weight, no push. A "group" is a
  drone plus every drone ``pair_mask`` pairs it with; with a team mask (``team_pair_mask``) a group is a
  team, so each team converges and takes its emergency action on its own, exactly as when the
  original is called once per team.
* The original's push-apart loops over pairs in order and evaluates each pair on commands already
  overwritten by earlier pairs. Here every pair is evaluated on the commands before the push and, when
  a drone sits in several violated pairs, the last such pair in ``triu`` order sets its command (the
  original's last-writer-wins order). Identical when no drone is in two violated pairs.
* No ``fixed`` rows: the game has no external drones. Passing ``fixed`` raises.
* ``max_speed_mps`` may be per drone; the pruning bound and the push speed then use each drone's own
  cap (identical to the original when the cap is one number).

Early stop (``check_every = k > 0``, S2 Task 7; ``k = 0``, the default, is the fixed loop of run T2, bit for
bit): games with no active pair skip the sweeps (their answer is the speed clamp after the loop); every ``k``
sweeps, starting at sweep 0, the games that still have an unconverged group are gathered into a smaller working
batch, and the loop ends when none is left or ``iterations`` is reached. Converged groups are frozen in the
fixed loop as well, so the answer equals the fixed loop's up to float rounding. Each check makes one host sync
(``nonzero``), the one the S2 plan allows (decision D10); nothing else in the call syncs when every tensor
argument, the speed cap included, is already on the inputs' device.
"""
from dataclasses import dataclass

import torch
from torch import Tensor


@dataclass(frozen=True)
class FilterResult:
    """Output of `filter_velocities`.

    velocities [N, M, 3] safe velocities (m/s); corrected [N, M] bool, ``|v - nominal| > 1e-3``;
    residual [N] worst violation of the active pair constraints and speed caps after the filter
    (emergency action included, as in the original); emergency [N] bool, push-apart used in any group;
    converged [N] bool, every group of the game met the stopping test within the sweeps, or the game had no active pair
    (None only where a caller builds a result itself, e.g. a pass-through in ``scripts/filter_speed.py``).
    """

    velocities: Tensor
    corrected: Tensor
    residual: Tensor
    emergency: Tensor
    converged: Tensor | None = None


def team_pair_mask(guards: int, strikes: int, device: torch.device | str | None = None) -> Tensor:
    """[M, M] bool, M = guards + strikes: True only between two different drones of the same team.

    Drones ``0 .. guards-1`` are the Guard team, ``guards .. M-1`` the Strike team.
    """
    team = torch.arange(guards + strikes, device=device) >= guards
    return (team[:, None] == team[None, :]) & ~torch.eye(guards + strikes, dtype=torch.bool, device=device)


def _group_max(x: Tensor, same: Tensor) -> Tensor:
    """x [N, M] >= 0, same [N, M, M] bool -> [N, M]: max of x over each drone's group."""
    return torch.where(same, x[:, None, :], torch.zeros_like(x)[:, None, :]).amax(dim=-1)


def _drone_residual(v: Tensor, ii: Tensor, jj: Tensor, member: Tensor, g: Tensor, bias: Tensor, active: Tensor,
                    cap: Tensor) -> Tensor:
    """Per-drone worst violation [N, M]: own speed cap and every active pair it belongs to.

    v [N, M, 3]; ii, jj [P] pair drones; member [P, M] bool; g [N, P, 3]; bias, active [N, P]; cap [N, M, 1].
    Only the two drones of a pair are read for it, so a non-finite drone cannot reach another pair.
    """
    lhs = (g * (v[:, ii] - v[:, jj])).sum(-1) + bias
    viol = torch.where(active, (-lhs).clamp(min=0.0), torch.zeros_like(lhs))  # [N, P]
    per_pair = torch.where(member[None], viol[..., None], torch.zeros_like(viol)[..., None])  # [N, P, M]
    speed = (v.norm(dim=-1) - cap[..., 0]).clamp(min=0.0)  # [N, M]
    return torch.cat([speed[:, None, :], per_pair], dim=1).amax(dim=1)


def filter_velocities(nominal_mps: Tensor, pos_m: Tensor, pair_mask: Tensor, safety_radius_m: float,
                      max_speed_mps: float | Tensor, alpha: float = 2.5, iterations: int = 1000,
                      tolerance: float = 2e-3, fixed: None = None, check_every: int = 0) -> FilterResult:
    """Project nominal velocities onto the safe set of every masked pair, all games at once.

    nominal_mps [N, M, 3], pos_m [N, M, 3]; pair_mask [M, M] or [N, M, M] bool, which must be symmetric,
    False on the diagonal and team (block) shaped, as `team_pair_mask` makes it (not checked: the per-team
    stopping assumes it); max_speed_mps a number or a tensor broadcastable to [N, M, 1].
    A drone whose command or position is not finite is commanded zero, takes part in no pair, and sets
    its team's emergency flag; every other drone, its own team mates included, is filtered as if it were
    absent, and the other team's output is bit-identical to the all-finite case.
    The result is on the inputs' device and dtype. ``fixed`` (the original's externally flown rows) is
    not supported: the game has no external drones. ``iterations`` defaults to the count of the parity
    record (1,000; see ``scripts/filter_parity.py``); fewer sweeps are cheaper and differ more from the
    original. ``check_every`` = k > 0 stops early (module docstring, "Early stop"): one host sync every k
    sweeps; 0 runs all ``iterations`` sweeps on every game with no host sync. A speed cap given as a Python
    number is copied to the device on every call (a host sync on CUDA); pass a device tensor in the step.
    """
    if fixed is not None:
        raise ValueError("fixed rows are not supported: the training game has no external drones")
    check_every = int(check_every)
    if check_every < 0:
        raise ValueError(f"check_every must be >= 0 (0 = no early stop); got {check_every}")
    if nominal_mps.dim() != 3 or nominal_mps.shape[-1] != 3 or nominal_mps.shape != pos_m.shape:
        raise ValueError(f"nominal_mps and pos_m must both be [N, M, 3]; got {tuple(nominal_mps.shape)}, "
                         f"{tuple(pos_m.shape)}")
    n, m, _ = nominal_mps.shape
    dev, dt = nominal_mps.device, nominal_mps.dtype
    pos_m = pos_m.to(device=dev, dtype=dt)
    bad = ~(torch.isfinite(nominal_mps).all(dim=-1) & torch.isfinite(pos_m).all(dim=-1))  # [N, M]
    nominal_ok = torch.where(bad[..., None], torch.zeros_like(nominal_mps), nominal_mps)
    pos_m = torch.where(bad[..., None], torch.zeros_like(pos_m), pos_m)
    cap = torch.broadcast_to(torch.as_tensor(max_speed_mps, dtype=dt, device=dev), (n, m, 1))
    mask = pair_mask.to(dev)
    if mask.dim() == 2:
        mask = mask.expand(n, m, m)
    same = mask | torch.eye(m, dtype=torch.bool, device=dev)  # [N, M, M] each drone's group

    ii, jj = torch.triu_indices(m, m, offset=1, device=dev)  # [P]
    drones = torch.arange(m, device=dev)
    is_i, is_j = ii[:, None] == drones, jj[:, None] == drones  # [P, M]
    member = is_i | is_j
    inc = is_i.to(dt) - is_j.to(dt)  # [P, M]: +1 drone i, -1 drone j; used only on finite, guarded values

    in_mask = mask[:, ii, jj] & ~bad[:, ii] & ~bad[:, jj]  # [N, P]; a non-finite drone is in no pair
    rel = pos_m[:, ii] - pos_m[:, jj]  # [N, P, 3]
    barrier = (rel * rel).sum(-1) - (2.0 * safety_radius_m) ** 2  # h [N, P]
    g = 2.0 * rel  # gradient w.r.t. v_i
    bias = alpha * barrier
    g_norm = g.norm(dim=-1)
    pair_norm_sq = (2.0 * (g * g).sum(-1)).clamp(min=1e-12)

    infeasible_p = in_mask & (g_norm < 1e-5) & (bias < -tolerance)  # coincident drones
    cap_i, cap_j = cap[:, ii, 0], cap[:, jj, 0]
    active = in_mask & (bias < g_norm * (cap_i + cap_j))  # pruning, as the original
    involvement = active.to(dt) @ member.to(dt)  # [N, M] active pairs per drone
    weight = (involvement + 1.0)[..., None]  # +1 for the speed-cap set

    # Dykstra state. The pair correction of the original is (-s g) on drone i and (+s g) on drone j, so one
    # scalar s per pair holds it; the speed-ball correction is a vector per drone.
    v = nominal_ok.clone()
    cap_corr = torch.zeros_like(v)
    s = torch.zeros_like(bias)
    converged = torch.zeros(n, m, dtype=torch.bool, device=dev)  # per drone, always equal within a group

    # The sweeps run on a working batch. With check_every = 0 it is every game, the tensors above themselves, so
    # the loop is T2's bit for bit. With check_every = k > 0 it is re-gathered every k sweeps: the games that still
    # have an active pair in an unconverged group; the others are written back to `out_v` first.
    has_pair = active.any(dim=1)  # [N] games with something to filter
    w_g, w_bias, w_active, w_pns, w_cap = g, bias, active, pair_norm_sq, cap
    w_inv, w_weight, w_same = involvement, weight, same
    work = torch.arange(n, device=dev)  # [W] game index of each working row
    out_v = v

    for it in range(iterations):
        if check_every and it % check_every == 0:
            out_v = out_v.index_copy(0, work, v)
            live = (has_pair[work] & ~converged.all(dim=-1)).nonzero().squeeze(1)  # the one host sync (D10)
            if live.numel() == 0:
                break
            work = work[live]
            v, cap_corr, s, converged = v[live], cap_corr[live], s[live], converged[live]
            w_g, w_bias, w_active, w_pns, w_cap = w_g[live], w_bias[live], w_active[live], w_pns[live], w_cap[live]
            w_inv, w_weight, w_same = w_inv[live], w_weight[live], w_same[live]
        capped = v + cap_corr
        norms = capped.norm(dim=-1, keepdim=True)
        cap_proj = torch.where(norms > w_cap, capped * (w_cap / norms.clamp(min=1e-12)), capped)
        lhs = (w_g * (v[:, ii] - v[:, jj])).sum(-1) - s * w_pns + w_bias  # at y = v + corr
        s_new = torch.where(w_active, (-lhs).clamp(min=0.0) / w_pns, torch.zeros_like(s))
        # consensus: sum over the speed ball and every active pair containing the drone, of its projection.
        # The pair sum is a matrix product with the +1/-1/0 incidence (it fixes the summation order, so results
        # are bit-identical to run T2); its operand is guarded first, so it is always finite and an inactive
        # pair is exactly 0: a drone outside a pair adds exactly nothing (0 x NaN never happens). A non-finite
        # step goes back as NaN to its own two drones only, by boolean indexing.
        step = (s_new - s)[..., None] * w_g  # [W, P, 3]
        bad_step = w_active & ~torch.isfinite(step).all(dim=-1)  # [W, P]
        step = torch.where((w_active & ~bad_step)[..., None], step, torch.zeros_like(step))
        acc = cap_proj + w_inv[..., None] * v + torch.einsum("npd,pm->nmd", step, inc)
        spoilt = (bad_step[..., None] & member[None]).any(dim=1)  # [W, M] drones of a non-finite pair step
        new_v = torch.where(spoilt[..., None], torch.full_like(acc, float("nan")), acc / w_weight)

        delta = _group_max((new_v - v).abs().amax(dim=-1), w_same)
        res = _group_max(_drone_residual(new_v, ii, jj, member, w_g, w_bias, w_active, w_cap), w_same)
        keep = converged[..., None]  # converged groups are frozen, as the original stops
        v = torch.where(keep, v, new_v)
        cap_corr = torch.where(keep, cap_corr, capped - cap_proj)
        s = torch.where(converged[:, ii], s, s_new)
        converged = converged | ((res <= tolerance) & (delta <= tolerance))

    if check_every:
        v = out_v.index_copy(0, work, v)
        # rows left out of the working batch had no active pair or every group converged
        game_converged = torch.ones(n, dtype=torch.bool, device=dev).index_copy(0, work, converged.all(dim=-1))
    else:
        game_converged = converged.all(dim=-1)
    game_converged = game_converged | ~has_pair  # [N]

    # Final safeguard, as the original: zero non-finite rows (group then not converged), clamp to the cap.
    finite = torch.isfinite(v).all(dim=-1) & ~bad  # [N, M]
    v = torch.where(finite[..., None], v, torch.zeros_like(v))
    non_finite = _group_max((~finite).to(dt), same) > 0
    norms = v.norm(dim=-1, keepdim=True)
    v = torch.where(norms > cap, v * (cap / norms.clamp(min=1e-12)), v)

    infeasible = (infeasible_p[..., None] & member[None]).any(dim=1).to(dt)  # [N, M]
    group_res = _group_max(_drone_residual(v, ii, jj, member, g, bias, active, cap), same)
    emergency_d = non_finite | (_group_max(infeasible, same) > 0) | (group_res > 5.0 * tolerance)  # [N, M]

    # Emergency push-apart: every masked pair still violated, in a group that takes the emergency action.
    lhs = (g * (v[:, ii] - v[:, jj])).sum(-1) + bias
    violated = in_mask & (lhs < 0.0) & emergency_d[:, ii]  # [N, P]
    x_axis = torch.zeros_like(g)
    x_axis[..., 0] = 1.0  # the original's direction for coincident drones, built on the device
    unit = torch.where((g_norm >= 1e-9)[..., None], g / g_norm.clamp(min=1e-9)[..., None], x_axis)
    pen = (-barrier).clamp(min=0.0)
    speed_i = torch.minimum(cap_i, 0.5 * cap_i + 0.1 * pen)
    speed_j = torch.minimum(cap_j, 0.5 * cap_j + 0.1 * pen)
    # slots: 0 = keep, 1..P = drone i of pair p, P+1..2P = drone j of pair p; the last violated pair wins
    push = torch.cat([v.new_zeros(n, 1, 3), unit * speed_i[..., None], -unit * speed_j[..., None]], dim=1)
    order = torch.arange(1, ii.numel() + 1, device=dev).repeat(2)  # [2P]
    owns = torch.cat([is_i, is_j])  # [2P, M]
    key = torch.where(violated.repeat(1, 2)[..., None] & owns[None], order[None, :, None], 0)  # [N, 2P, M]
    key = torch.cat([key.new_zeros(n, 1, m), key], dim=1)
    best_key, best_slot = key.max(dim=1)  # [N, M]
    chosen = torch.gather(push, 1, best_slot[..., None].expand(n, m, 3))
    v = torch.where((best_key > 0)[..., None], chosen, v)

    residual = _drone_residual(v, ii, jj, member, g, bias, active, cap).amax(dim=-1)
    corrected = ((v - nominal_ok).norm(dim=-1) > 1e-3) | bad
    return FilterResult(velocities=v, corrected=corrected, residual=residual, emergency=emergency_d.any(dim=-1),
                        converged=game_converged)
