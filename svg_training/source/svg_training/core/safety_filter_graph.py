"""Fixed-shape, CUDA-graph path of the safety filter (opt-in; ``[starling_layer] filter_cuda_graph = true``).

Same mathematics, inputs and outputs as ``core/safety_filter.filter_velocities`` (read its docstring first); only the way the sweep
loop is run differs. Shapes: ``N`` games, ``M`` drones, ``P = M (M - 1) / 2`` pairs, ``C`` the working capacity.

Why: in the hangar game the filter is launch-bound (P0 record, 18 Nov 2026: about 82 small kernels per sweep, 1,000 sweeps per tick,
the GPU busy about a fifth of the time), and its early stop re-gathers a working batch of a new shape every check, which a CUDA graph
cannot hold.

How:

* **Masking instead of re-gathering.** A converged group is already frozen by the sweep itself (``keep`` below: its velocity, speed
  correction, pair multipliers and flag do not change), so a game can stay in the batch after it is done and every further sweep is a
  no-op for it. The loop can therefore stop as soon as every game has converged without changing any number.
* **Blocks of sweeps as CUDA graphs.** ``block`` sweeps (default: ``check_every``, or ``DEFAULT_BLOCK`` when it is 0) are captured once
  per working capacity, then replayed; the remainder of ``iterations`` gets its own graph. Inputs and state live in static buffers
  that are copied in and out; results are never the static buffers themselves. Graphs of all capacities share one memory pool per
  device (they are replayed one after another, and every state they hand on lives in the static buffers).
* **Early stop**, ``check_every > 0``: once every ``READ_EVERY_SWEEPS`` sweeps (whole blocks) the live game count is copied to pinned
  host memory without waiting, and the count copied ``LAG_BLOCKS`` reads earlier is read (a host wait on an event); the loop ends when a
  count is 0 (the sweeps run since then were no-ops) or ``iterations`` is reached. On a GPU shared with other jobs every host sync or
  device-to-host copy costs about a turn of the GPU's time-slicing (measured 18 Nov 2026, 1,000 games, five recorded states: graphs with
  a read every 8 sweeps 1.92 s per call, existing path 2.03, a read every 64 sweeps 1.03, every 256 sweeps 0.87, no read 0.85).
  ``check_every = 0``: every block is replayed with no host read. The cadence never changes the answer (frozen sweeps are no-ops),
  except through the ladder below when ``compact=True``.
* Default (``compact=False``): the whole batch every sweep, no game frozen in advance. The answer is then the existing FIXED loop's
  (``check_every = 0``, run T2's loop) bit for bit, on the CPU and on CUDA, whatever ``check_every`` and ``block`` are
  (``tests/test_safety_filter_graph.py``).
* ``compact=True`` (with ``check_every > 0``): games with no active pair start frozen (the existing early stop never sweeps them), and
  when the live games fit in half the capacity the batch is compacted (live rows first, padded with frozen rows of the same batch) into
  the smallest rung ``ceil(N / 2^j)`` that holds them, not below ``min(N, CAPACITY_FLOOR)`` (``_rung``). Only a few shapes ever occur,
  so their graphs are reused across calls (``MAX_CACHED`` capacities kept, least recently used dropped).

Rounding on CUDA (measured 18 Nov 2026, ``scripts/filter_graph_check.py equiv``): cuBLAS chooses the kernel of a sweep's ``einsum`` by
the batch size, so on CUDA a row is rounded differently in a working batch of a different size. The existing early stop changes the
batch size at every check, so on CUDA its answer for a game depends on how many other games are still live, and it differs from its
own fixed loop (T2's 2,000 scenes at 1,000 sweeps: up to 2.6e-6 m/s in converged games, up to 1.65 m/s in unconverged ones, all flags
equal). No fixed-shape path can reproduce those bits; this path reproduces the fixed loop's instead (default) or its own ladder's.
On the CPU all paths agree on T2's scenes.

On the CPU (or with ``use_graph=False``) the same blocks run eagerly, so the CPU tests cover the masking, the ladder and the
remainder block. The code before and after the sweep loop is a copy of ``filter_velocities``' own, and each sweep is that loop's
body; ``tests/test_safety_filter_graph.py`` holds the equivalence gate against the existing path (fixed before any measurement:
velocities within 1e-6 m/s max abs, converged / emergency / corrected flags equal). Results are observed in the training simulator.
"""
from __future__ import annotations

from collections import OrderedDict, deque

import torch
from torch import Tensor

from .safety_filter import FilterResult, _drone_residual, _group_max, _share_setup

DEFAULT_BLOCK = 8          # PROPOSED: sweeps per graph when check_every is 0 (the hangar game's check_every is 8)
CAPACITY_FLOOR = 128       # PROPOSED: the working capacity never goes below min(N, this)
READ_EVERY_SWEEPS = 128    # PROPOSED: on CUDA the live count is copied to the host once per this many sweeps (whole blocks)
LAG_BLOCKS = 1             # PROPOSED: the early-stop count is read this many blocks late, so the host never waits on an empty queue
MAX_CACHED = 16            # PROPOSED: working capacities (static buffers + graphs) kept per process

_RUNNERS: "OrderedDict[tuple, _GraphRunner]" = OrderedDict()
_POOLS: dict = {}
_RINGS: dict = {}


def _rung(n: int, live: int, floor: int = CAPACITY_FLOOR) -> int:
    """The working capacity for ``live`` live games of ``n``: the smallest of n, ceil(n/2), ceil(n/4), ... that holds them, at least
    min(n, floor)."""
    c = n
    while (c + 1) // 2 >= live and c > 1:
        c = (c + 1) // 2
    return max(c, min(n, floor))


def _sweep(state: tuple, inp: tuple, cst: tuple, tolerance: float) -> tuple:
    """One parallel Dykstra sweep, masked: ``filter_velocities``' loop body, unchanged. state = (v [C, M, 3], cap_corr [C, M, 3],
    s [C, P], converged [C, M]); inp = (g [C, P, 3], bias, active, pns [C, P], cap [C, M, 1], inv [C, M], weight [C, M, 1],
    same [C, M, M]) and, with a per-pair share (STE L2.1), a ninth entry: the weighted incidence [C, P, M];
    cst = (ii, jj [P], member [P, M] bool, inc [P, M])."""
    v, cap_corr, s, converged = state
    w_g, w_bias, w_active, w_pns, w_cap, w_inv, w_weight, w_same = inp[:8]
    ii, jj, member, inc = cst
    capped = v + cap_corr
    norms = capped.norm(dim=-1, keepdim=True)
    cap_proj = torch.where(norms > w_cap, capped * (w_cap / norms.clamp(min=1e-12)), capped)
    lhs = (w_g * (v[:, ii] - v[:, jj])).sum(-1) - s * w_pns + w_bias  # at y = v + corr
    s_new = torch.where(w_active, (-lhs).clamp(min=0.0) / w_pns, torch.zeros_like(s))
    step = (s_new - s)[..., None] * w_g  # [C, P, 3]
    bad_step = w_active & ~torch.isfinite(step).all(dim=-1)  # [C, P]
    step = torch.where((w_active & ~bad_step)[..., None], step, torch.zeros_like(step))
    if len(inp) == 8:
        acc = cap_proj + w_inv[..., None] * v + torch.einsum("npd,pm->nmd", step, inc)
    else:
        acc = cap_proj + w_inv[..., None] * v + torch.einsum("npd,npm->nmd", step, inp[8])
    spoilt = (bad_step[..., None] & member[None]).any(dim=1)  # [C, M]
    new_v = torch.where(spoilt[..., None], torch.full_like(acc, float("nan")), acc / w_weight)

    delta = _group_max((new_v - v).abs().amax(dim=-1), w_same)
    res = _group_max(_drone_residual(new_v, ii, jj, member, w_g, w_bias, w_active, w_cap), w_same)
    keep = converged[..., None]  # converged groups are frozen, as the original stops
    v = torch.where(keep, v, new_v)
    cap_corr = torch.where(keep, cap_corr, capped - cap_proj)
    s = torch.where(converged[:, ii], s, s_new)
    converged = converged | ((res <= tolerance) & (delta <= tolerance))
    return v, cap_corr, s, converged


class _EagerRunner:
    """Runs blocks of sweeps eagerly on tensors it holds (CPU, or ``use_graph=False``)."""

    def __init__(self, cst: tuple, tolerance: float):
        self.cst, self.tolerance = cst, tolerance
        self.state = self.inp = None

    def load(self, state: tuple, inp: tuple) -> None:
        self.state, self.inp = tuple(state), tuple(inp)

    def run(self, sweeps: int) -> None:
        for _ in range(sweeps):
            self.state = _sweep(self.state, self.inp, self.cst, self.tolerance)

    def live_count(self):
        """The number of rows still sweeping, as a pending read (``_read``)."""
        return int((~self.state[3].all(dim=-1)).sum())


class _GraphRunner:
    """Static buffers for one working capacity and one CUDA graph per block length, captured on first use."""

    def __init__(self, c: int, m: int, p: int, device: torch.device, dtype: torch.dtype, cst: tuple, tolerance: float,
                 shared: bool = False):
        with torch.inference_mode(False), torch.no_grad():
            z = lambda *shape, dt=dtype: torch.zeros(*shape, device=device, dtype=dt)  # noqa: E731
            self.state = (z(c, m, 3), z(c, m, 3), z(c, p), z(c, m, dt=torch.bool))
            self.inp = (z(c, p, 3), z(c, p), z(c, p, dt=torch.bool), torch.ones(c, p, device=device, dtype=dtype), z(c, m, 1),
                        z(c, m), torch.ones(c, m, 1, device=device, dtype=dtype), z(c, m, m, dt=torch.bool))
            if shared:                                        # STE L2.1: the per-pair share's weighted incidence
                self.inp = self.inp + (z(c, p, m),)
            self.cst = tuple(t.clone() for t in cst)
            self.live = torch.zeros((), dtype=torch.long, device=device)   # rows still sweeping, written by every graph
        self.tolerance, self.device = tolerance, device
        self.graphs: dict[int, torch.cuda.CUDAGraph] = {}

    def load(self, state: tuple, inp: tuple) -> None:
        with torch.no_grad():
            for dst, src in zip(self.state + self.inp, tuple(state) + tuple(inp)):
                dst.copy_(src)

    def _capture(self, sweeps: int) -> torch.cuda.CUDAGraph:
        side = torch.cuda.Stream(device=self.device)
        side.wait_stream(torch.cuda.current_stream(self.device))
        with torch.cuda.stream(side), torch.no_grad():      # warm-up off the capture (library handles, workspaces)
            st = self.state
            for _ in range(sweeps):
                st = _sweep(st, self.inp, self.cst, self.tolerance)
        torch.cuda.current_stream(self.device).wait_stream(side)
        pool = _POOLS.setdefault(self.device, torch.cuda.graph_pool_handle())
        graph = torch.cuda.CUDAGraph()
        with torch.cuda.graph(graph, pool=pool), torch.no_grad():
            st = self.state
            for _ in range(sweeps):
                st = _sweep(st, self.inp, self.cst, self.tolerance)
            for dst, src in zip(self.state, st):
                dst.copy_(src)
            self.live.copy_((~st[3].all(dim=-1)).sum())
        return graph                                          # capture records the work without running it: the state is as loaded

    def run(self, sweeps: int) -> None:
        graph = self.graphs.get(sweeps)
        if graph is None:
            graph = self.graphs[sweeps] = self._capture(sweeps)
        graph.replay()

    def live_count(self):
        """The number of rows still sweeping after the last replay, as a pending read: copied without waiting into a slot of a pinned
        host ring made once per device (allocating pinned memory on the fly can synchronize the device), with the slot's event
        (``_read``). At most LAG_BLOCKS + 1 reads are outstanding, so a ring of LAG_BLOCKS + 2 slots is never overwritten unread."""
        ring = _RINGS.get(self.device)
        if ring is None:
            with torch.inference_mode(False):
                ring = _RINGS[self.device] = {"host": torch.zeros(LAG_BLOCKS + 2, dtype=torch.long, pin_memory=True),
                                              "events": [torch.cuda.Event() for _ in range(LAG_BLOCKS + 2)], "next": 0}
        k = ring["next"]
        ring["next"] = (k + 1) % (LAG_BLOCKS + 2)
        ring["host"][k].copy_(self.live, non_blocking=True)
        ring["events"][k].record()
        return ring["host"], k, ring["events"][k]


def _read(pending) -> int:
    """Resolve a ``live_count``: an int (eager) or (pinned host scalar, event); waits for the event (a host wait)."""
    if isinstance(pending, int):
        return pending
    host, k, event = pending
    event.synchronize()
    return int(host[k])


def _runner(c: int, m: int, p: int, device: torch.device, dtype: torch.dtype, cst: tuple, tolerance: float, use_graph: bool,
            shared: bool = False):
    if not use_graph:
        return _EagerRunner(cst, tolerance)
    key = (str(device), dtype, c, m, float(tolerance), bool(shared))       # a shared graph reads one more buffer
    r = _RUNNERS.pop(key, None)
    if r is None:
        r = _GraphRunner(c, m, p, device, dtype, cst, tolerance, shared)
    _RUNNERS[key] = r
    while len(_RUNNERS) > MAX_CACHED:
        _RUNNERS.popitem(last=False)
    return r


def filter_velocities_graph(nominal_mps: Tensor, pos_m: Tensor, pair_mask: Tensor, safety_radius_m: float,
                            max_speed_mps: float | Tensor, alpha: float = 2.5, iterations: int = 1000,
                            tolerance: float = 2e-3, fixed: None = None, check_every: int = 0, block: int = 0,
                            use_graph: bool | None = None, compact: bool = False,
                            pair_share: Tensor | None = None) -> FilterResult:
    """``filter_velocities`` with its sweep loop run as fixed-shape blocks (module docstring). Arguments and result as there;
    nominal_mps, pos_m [N, M, 3], pair_mask [M, M] or [N, M, M] bool. ``block`` = sweeps per block (0: ``check_every``, or
    ``DEFAULT_BLOCK`` when that is 0); ``use_graph`` None = CUDA graphs on a CUDA device, eager elsewhere; ``compact`` (needs
    ``check_every > 0``) pre-freezes games with no active pair and moves the live games into smaller capacities (module docstring).
    ``pair_share`` [P, 2] or [N, P, 2] (STE L2.1, as ``filter_velocities``): its weighted incidence rides in the inputs (a ninth
    static buffer, graphs cached apart from the no-share ones); None = this path as before, bit for bit."""
    if fixed is not None:
        raise ValueError("fixed rows are not supported: the training game has no external drones")
    check_every, block, iterations = int(check_every), int(block), int(iterations)
    if check_every < 0:
        raise ValueError(f"check_every must be >= 0 (0 = no early stop); got {check_every}")
    if block < 0:
        raise ValueError(f"block must be >= 0 (0 = check_every, or {DEFAULT_BLOCK}); got {block}")
    block = block or check_every or DEFAULT_BLOCK
    if nominal_mps.dim() != 3 or nominal_mps.shape[-1] != 3 or nominal_mps.shape != pos_m.shape:
        raise ValueError(f"nominal_mps and pos_m must both be [N, M, 3]; got {tuple(nominal_mps.shape)}, "
                         f"{tuple(pos_m.shape)}")
    n, m, _ = nominal_mps.shape
    dev, dt = nominal_mps.device, nominal_mps.dtype
    use_graph = (dev.type == "cuda") if use_graph is None else bool(use_graph)
    if use_graph and dev.type != "cuda":
        raise ValueError("use_graph=True needs CUDA tensors")

    # ---- set-up: a copy of filter_velocities' own --------------------------------------------------------------------------
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
    inc = is_i.to(dt) - is_j.to(dt)  # [P, M]

    in_mask = mask[:, ii, jj] & ~bad[:, ii] & ~bad[:, jj]  # [N, P]
    rel = pos_m[:, ii] - pos_m[:, jj]  # [N, P, 3]
    barrier = (rel * rel).sum(-1) - (2.0 * safety_radius_m) ** 2  # h [N, P]
    g = 2.0 * rel
    bias = alpha * barrier
    g_norm = g.norm(dim=-1)
    pair_norm_sq = (2.0 * (g * g).sum(-1)).clamp(min=1e-12)

    infeasible_p = in_mask & (g_norm < 1e-5) & (bias < -tolerance)  # coincident drones
    cap_i, cap_j = cap[:, ii, 0], cap[:, jj, 0]
    active = in_mask & (bias < g_norm * (cap_i + cap_j))  # pruning, as the original
    if pair_share is None:
        involvement = active.to(dt) @ member.to(dt)  # [N, M] active pairs per drone
        sinc = None
    else:  # option B (STE L2.1), as filter_velocities
        active, involvement, sinc = _share_setup(pair_share, active, in_mask, g, g_norm, bias, nominal_ok, cap, ii, jj,
                                                 is_i, is_j, dt)
    weight = (involvement + 1.0)[..., None]  # +1 for the speed-cap set

    v = nominal_ok.clone()
    cap_corr = torch.zeros_like(v)
    s = torch.zeros_like(bias)
    has_pair = active.any(dim=1)  # [N]
    converged = torch.zeros(n, m, dtype=torch.bool, device=dev)
    compact = bool(compact) and check_every > 0
    if compact:          # the existing early stop never sweeps a game with no active pair: it starts frozen here
        converged = converged | ~has_pair[:, None]

    # ---- the sweeps: fixed-shape blocks on a working batch (rows `work` of the games), frozen rows kept ----------------------
    cst = (ii, jj, member, inc)
    inputs = (g, bias, active, pair_norm_sq, cap.contiguous(), involvement, weight, same.contiguous())
    if sinc is not None:
        inputs = inputs + (sinc.contiguous(),)
    state = (v, cap_corr, s, converged)
    p = ii.numel()
    work = torch.arange(n, device=dev)
    out_v, out_conv = v, converged.all(dim=-1)
    done, c, runner = 0, n, None
    if compact:
        live_n = int(has_pair.sum())                                          # host read (as the existing check at sweep 0)
        if live_n == 0:
            done = iterations
        else:
            c = _rung(n, live_n)
            if c < n:
                sel = torch.argsort((~has_pair).to(torch.int8), stable=True)[:c]     # live rows first, then frozen padding
                work = work[sel]
                state = tuple(t[sel] for t in state)
                inputs = tuple(t[sel] for t in inputs)
    if done < iterations:
        runner = _runner(c, m, p, dev, dt, cst, tolerance, use_graph, sinc is not None)
        runner.load(state, inputs)
    pending: deque = deque()
    blocks, read_every = 0, max(1, READ_EVERY_SWEEPS // block)    # the same cadence eager and on graphs: the same ladder
    while done < iterations:
        sweeps = min(block, iterations - done)
        runner.run(sweeps)
        done += sweeps
        blocks += 1
        if not check_every or done >= iterations or blocks % read_every:
            continue
        pending.append(runner.live_count())                                   # read later: the GPU keeps LAG_BLOCKS blocks queued
        if len(pending) <= LAG_BLOCKS:
            continue
        live_n = _read(pending.popleft())                                     # rows live LAG_BLOCKS blocks ago (>= live now)
        if live_n == 0:
            break                                                             # the blocks since were no-ops
        c_new = _rung(n, live_n) if compact else c
        if c_new < c:                                                         # compact into a smaller rung
            st = runner.state
            live = ~st[3].all(dim=-1)                                         # [C] rows still sweeping now
            out_v = out_v.index_copy(0, work, st[0])
            out_conv = out_conv.index_copy(0, work, st[3].all(dim=-1))
            sel = torch.argsort((~live).to(torch.int8), stable=True)[:c_new]
            work = work[sel]
            state = tuple(t[sel] for t in st)
            inputs = tuple(t[sel] for t in runner.inp)
            c = c_new
            runner = _runner(c, m, p, dev, dt, cst, tolerance, use_graph, sinc is not None)
            runner.load(state, inputs)
    if runner is not None:
        out_v = out_v.index_copy(0, work, runner.state[0])
        out_conv = out_conv.index_copy(0, work, runner.state[3].all(dim=-1))
    v = out_v
    game_converged = out_conv | ~has_pair  # [N]

    # ---- after the sweeps: a copy of filter_velocities' own ---------------------------------------------------------------
    finite = torch.isfinite(v).all(dim=-1) & ~bad  # [N, M]
    v = torch.where(finite[..., None], v, torch.zeros_like(v))
    non_finite = _group_max((~finite).to(dt), same) > 0
    norms = v.norm(dim=-1, keepdim=True)
    v = torch.where(norms > cap, v * (cap / norms.clamp(min=1e-12)), v)

    infeasible = (infeasible_p[..., None] & member[None]).any(dim=1).to(dt)  # [N, M]
    group_res = _group_max(_drone_residual(v, ii, jj, member, g, bias, active, cap), same)
    emergency_d = non_finite | (_group_max(infeasible, same) > 0) | (group_res > 5.0 * tolerance)  # [N, M]

    lhs = (g * (v[:, ii] - v[:, jj])).sum(-1) + bias
    violated = in_mask & (lhs < 0.0) & emergency_d[:, ii]  # [N, P]
    x_axis = torch.zeros_like(g)
    x_axis[..., 0] = 1.0
    unit = torch.where((g_norm >= 1e-9)[..., None], g / g_norm.clamp(min=1e-9)[..., None], x_axis)
    pen = (-barrier).clamp(min=0.0)
    speed_i = torch.minimum(cap_i, 0.5 * cap_i + 0.1 * pen)
    speed_j = torch.minimum(cap_j, 0.5 * cap_j + 0.1 * pen)
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
