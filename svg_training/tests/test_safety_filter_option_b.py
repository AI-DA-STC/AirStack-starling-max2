"""STE task L2.1: filter option B in the training copy (WORK_BREAKDOWN L2.1; ARCHITECTURE section 3, "Option B mathematics").

Part 1, written and committed BEFORE the change: ``"equal"`` (today's even split) stays bit for bit. Golden tensors of the
safety filter on the T2 parity scenes (``scripts/filter_parity.make_scenes``, seed 20261115, the first 500 scenes at
T2's 1,000 sweeps, check_every 0; the first 200 for the early-stop and graph variants), each with T2's team mask and with
an every-pair mask (the partner preset's pairs), saved from commit 743c1901 (branch ste-l2-1 before L2.1). Regenerate
them only from a commit whose filter is known good:

    cd svg_training && PYTHONPATH=source python tests/test_safety_filter_option_b.py --write-golden

Part 2: option B, ``"guard_yields"`` (PROPOSED, P2 open; owner rules at the L2 gate). Per pair a share (sigma_i, sigma_j),
sigma_i + sigma_j = 1, of the correction: drone i moves by sigma_i c g / |g|^2, drone j by -sigma_j c g / |g|^2 (ARCHITECTURE
section 3). In a Guard-Strike pair the Guard takes the whole correction (1, 0); team-mate pairs and pairs with a landing
drone (L2.3) keep (1/2, 1/2). Emergency rule (DISCUSSION section 2.9, "a fallback to 50/50 when the Guard truly cannot
escape"): a game whose option B answer would need the filter's emergency action (its residual after the speed clamp above
5 x tolerance, the original's own emergency residual; or a non-finite row or coincident drones) takes today's even-split
filter instead, push-apart included. The desk cases of DISCUSSION section 2.9 are fixtures (Strike 0.5 m/s into a still
Guard; Guard pushing back at 0.33 m/s; closest approach 1.10 m); a Guard pinned between two closing Strikes has an analytic
feasibility limit for the fallback. Both filter paths (``filter_velocities``, ``filter_velocities_graph`` eager on the CPU;
the CUDA-graph replay is not run here).

Part 3: the game setting ``[filter] share`` (``core/game_config.FilterCfg``; absent = "equal") through the Starling layer,
both backends (tier 1 fitted, tier 2 physics on the PyTorch reference world): absent and "equal" play the same game bit for
bit; the desk case in the game; pairs with a landing drone stay equal; a Guard drone pinned at a wall (KNOWN SHORTFALL,
pinned at its measured value: the Strike drone closes to 0.39-0.60 m). Through the Starling layer the keep-out holds to 1.10 m less the tracking tolerance (the
commander copy's position-setpoint leak and the PX4 lag; the Starling-layer tests accept >= 1.0 m).

CPU, float32 unless stated, made-up scenes. Observed in the training simulator, not a flight result.
"""
import importlib.util
import pathlib
import sys

import pytest
import torch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
CMU_PKG = ROOT.parent / "AirStack/robot/ros_ws/src/svg_ground_control"
from svg_training.core.safety_filter import (filter_velocities, filter_velocities_shared,  # noqa: E402
                                             guard_yields_share)
from svg_training.core.safety_filter_graph import filter_velocities_graph  # noqa: E402

GOLDEN = ROOT / "tests" / "data" / "safety_filter_equal_golden.pt"
T2_SEED = 20261115            # scripts/filter_parity.DEFAULT_SEED, the T2 record's scene seed
R_M, ALPHA, TOL = 0.55, 2.5, 2e-3
KEYS = ("velocities", "corrected", "residual", "emergency", "converged")
KEEPOUT_M = 2 * R_M           # 1.10 m centre to centre (params/real_exploratory_v0.toml safety_radius_m 0.55)
EMERGENCY_RES = 5 * TOL       # the filter's emergency residual (core/safety_filter.py), the fallback's threshold
TICK_S = 0.05                 # the commander's tick (20 Hz)
DISCRETE_TOL_M = 0.005        # kinematic closed loop (ideal tracking): the 20 Hz step's own shortfall below 1.10 m
PATHS = {"dense": filter_velocities, "graph": filter_velocities_graph}


def _parity():
    """scripts/filter_parity.py as a module (it imports CMU's filter read-only, so the host is needed)."""
    if not (CMU_PKG / "svg_ground_control").is_dir():
        pytest.skip(f"CMU's svg_ground_control is not on this machine ({CMU_PKG}); run on the host")
    spec = importlib.util.spec_from_file_location("filter_parity", ROOT / "scripts/filter_parity.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def t2_batch(count: int, masks: str):
    """The first ``count`` T2 scenes as one batch: nominal, pos [N, 8, 3], mask [N, 8, 8], cap [N, 1, 1].
    masks "team": T2's own (same-team pairs); "every": every pair of the scene's real drones (padding excluded)."""
    fp = _parity()
    scenes = fp.make_scenes(count, T2_SEED)
    nom, pos, mask, cap = fp._batch(scenes)
    if masks == "every":
        real = torch.zeros(count, fp.M_MAX, dtype=torch.bool)
        for k, s in enumerate(scenes):
            real[k, : len(s.pos_m)] = True
        mask = real[:, :, None] & real[:, None, :] & ~torch.eye(fp.M_MAX, dtype=torch.bool)
    return nom, pos, mask, cap, scenes


VARIANTS = {   # name: (scenes, filter function, keyword arguments)
    "dense_ce0": (500, filter_velocities, {}),
    "dense_ce8": (200, filter_velocities, {"check_every": 8}),
    "graph_ce0": (200, filter_velocities_graph, {}),
    "graph_ce8_compact": (200, filter_velocities_graph, {"check_every": 8, "compact": True}),
}


def _golden_run(variant: str, masks: str) -> dict[str, torch.Tensor]:
    count, fn, kw = VARIANTS[variant]
    nom, pos, mask, cap, _ = t2_batch(count, masks)
    res = fn(nom, pos, mask, R_M, cap, alpha=ALPHA, iterations=1000, tolerance=TOL, **kw)
    return {k: getattr(res, k).clone() for k in KEYS}


@pytest.mark.parametrize("masks", ["team", "every"])
@pytest.mark.parametrize("variant", sorted(VARIANTS))
def test_equal_is_todays_filter_bit_for_bit(variant, masks):
    """The default filter call (no share given) reproduces the pre-L2.1 tensors exactly, on both filter paths."""
    golden = torch.load(GOLDEN)[f"{variant}/{masks}"]
    now = _golden_run(variant, masks)
    assert now["corrected"].any() and now["emergency"].any(), "the scenes exercise nothing"
    for k in KEYS:
        assert torch.equal(now[k], golden[k]), f"{variant}/{masks}: {k} differs from the pre-L2.1 golden"


# --- part 2: option B -------------------------------------------------------------------------------------------------

def scene(pos, nom, dtype=torch.float32):
    """One game: pos, nom lists of (x, y, z) -> [1, M, 3] tensors and the every-pair mask [M, M]."""
    p, v = torch.tensor([pos], dtype=dtype), torch.tensor([nom], dtype=dtype)
    m = p.shape[1]
    return v, p, ~torch.eye(m, dtype=torch.bool)


def run(path, nom, pos, mask, share=None, cap=1.0, iterations=1000, **kw):
    """One filter call on ``path`` ("dense" / "graph"); share None = today's call (no keyword passed)."""
    extra = {} if share is None else {"pair_share": share}
    return PATHS[path](nom, pos, mask, R_M, cap, alpha=ALPHA, iterations=iterations, tolerance=TOL, **extra, **kw)


def gy(guards, strikes, n=1, landing=None):
    """guard_yields shares [N, P, 2] for Guard drones 0..guards-1, then Strike drones."""
    guard = torch.arange(guards + strikes) < guards
    return guard_yields_share(guard, n, landing=landing)


def test_share_table_guard_strike_pairs_only():
    """2 Guards + 2 Strikes, triu order (0,1) (0,2) (0,3) (1,2) (1,3) (2,3): only Guard-Strike pairs move off 1/2."""
    share = gy(2, 2)
    assert share.shape == (1, 6, 2)
    half, guard_i = [0.5, 0.5], [1.0, 0.0]
    assert share[0].tolist() == [half, guard_i, guard_i, guard_i, guard_i, half]
    # a Strike drone listed before a Guard drone: the Guard (drone j) takes the share
    guard = torch.tensor([False, True])
    assert guard_yields_share(guard, 1)[0].tolist() == [[0.0, 1.0]]


def test_share_table_landing_pairs_stay_equal():
    """A pair with a landing drone (L2.3: out of the game, still a filter obstacle) keeps the even split, per game."""
    landing = torch.tensor([[False, False, False, False], [False, False, True, False]])
    share = gy(2, 2, n=2, landing=landing)
    assert share[0].tolist() == gy(2, 2)[0].tolist()
    # game 1: Strike drone 2 lands -> pairs (0,2) and (1,2) back to 1/2; (0,3), (1,3) stay Guard-only
    assert share[1].tolist() == [[0.5, 0.5], [0.5, 0.5], [1.0, 0.0], [0.5, 0.5], [1.0, 0.0], [0.5, 0.5]]
    landing_guard = torch.tensor([[True, False, False, False]])
    assert gy(2, 2, landing=landing_guard)[0, :3].tolist() == [[0.5, 0.5]] * 3


@pytest.mark.parametrize("path", sorted(PATHS))
def test_explicit_even_shares_equal_todays_filter(path):
    """Shares (1/2, 1/2) everywhere are today's mathematics (not today's code path: within 1e-6 m/s)."""
    nom, pos, mask, cap, _ = t2_batch(200, "every")
    p = pos.shape[1] * (pos.shape[1] - 1) // 2
    half = torch.full((200, p, 2), 0.5)
    a = run(path, nom, pos, mask, cap=cap)
    b = run(path, nom, pos, mask, share=half, cap=cap)
    assert (a.velocities - b.velocities).abs().max() <= 1e-6
    assert torch.equal(a.emergency, b.emergency) and torch.equal(a.converged, b.converged)


# DISCUSSION section 2.9 desk case 1: Strike drone at 0.5 m/s into a still Guard drone, 1.2 m apart (inside the filter's
# reach: it acts below about 1.32 m at 0.5 m/s closing). Pair (Guard 0, Strike 1): g = 2 (p_G - p_S) = (-2.4, 0, 0),
# h = 1.2^2 - 1.1^2 = 0.23; constraint -2.4 (v_G + 0.5) + 2.5 x 0.23 >= 0, so the pair needs v_G - v_S <= -0.2604 + 0.5.
DESK_GAP_M = 1.2
NEED_MPS = (ALPHA * (DESK_GAP_M ** 2 - KEEPOUT_M ** 2)) / (2 * DESK_GAP_M)       # 0.2396: closing speed allowed


@pytest.mark.parametrize("path", sorted(PATHS))
def test_desk_strike_into_still_guard(path):
    """guard_yields: the Strike drone's command is untouched (bit for bit) and the Guard drone takes the whole
    correction (backs off at 0.5 - 0.2396 = 0.2604 m/s); equal: each takes half (0.1302 m/s)."""
    nom, pos, mask = scene([(0, 0, 1), (DESK_GAP_M, 0, 1)], [(0, 0, 0), (-0.5, 0, 0)])
    b = run(path, nom, pos, mask, share=gy(1, 1))
    assert torch.equal(b.velocities[0, 1], nom[0, 1])
    assert b.velocities[0, 0, 0].item() == pytest.approx(-(0.5 - NEED_MPS), abs=TOL)
    assert b.velocities[0, 0, 1:].abs().max() <= 1e-6 and not b.emergency.any()
    assert b.corrected[0].tolist() == [True, False]
    e = run(path, nom, pos, mask)
    half = (0.5 - NEED_MPS) / 2
    assert e.velocities[0, 0, 0].item() == pytest.approx(-half, abs=TOL)
    assert e.velocities[0, 1, 0].item() == pytest.approx(-0.5 + half, abs=TOL)


@pytest.mark.parametrize("path", sorted(PATHS))
def test_desk_guard_pushing_back(path):
    """Desk case 2: the Guard drone pushes back at 0.33 m/s. guard_yields: the Strike drone is still untouched and the
    Guard's command is replaced by the retreat the pair needs (0.2604 m/s away)."""
    nom, pos, mask = scene([(0, 0, 1), (DESK_GAP_M, 0, 1)], [(0.33, 0, 0), (-0.5, 0, 0)])
    b = run(path, nom, pos, mask, share=gy(1, 1))
    assert torch.equal(b.velocities[0, 1], nom[0, 1])
    assert b.velocities[0, 0, 0].item() == pytest.approx(-(0.5 - NEED_MPS), abs=TOL)


@pytest.mark.parametrize("path", sorted(PATHS))
@pytest.mark.parametrize("team", ["guard", "strike"])
def test_team_mate_pairs_keep_the_even_split(path, team):
    """Guard-Guard and Strike-Strike pairs under guard_yields: the even split, as with "equal" (within 1e-6 m/s)."""
    nom, pos, mask = scene([(0, 0, 1), (DESK_GAP_M, 0, 1)], [(0.3, 0, 0), (-0.5, 0, 0)])
    share = gy(2, 0) if team == "guard" else gy(0, 2)
    b, e = run(path, nom, pos, mask, share=share), run(path, nom, pos, mask)
    assert (b.velocities - e.velocities).abs().max() <= 1e-6
    dv = b.velocities - nom
    assert dv[0, 0, 0].item() == pytest.approx(-dv[0, 1, 0].item(), abs=1e-6)      # 50/50


def _kinematic_closest(share, ticks=200):
    """Ideal tracking, two games (Guard drone still / pushing back at 0.33 m/s; Strike drone at 0.5 m/s from 1.6 m): each
    tick the filter's output is flown exactly for 0.05 s. Returns (closest gap [2] m, last velocities [2, 2, 3])."""
    pos = torch.tensor([[[0.0, 0, 1], [1.6, 0, 1]]] * 2)
    nom = torch.tensor([[[0.0, 0, 0], [-0.5, 0, 0]], [[0.33, 0, 0], [-0.5, 0, 0]]])
    mask = ~torch.eye(2, dtype=torch.bool)
    closest = torch.full((2,), float("inf"))
    for _ in range(ticks):
        res = run("dense", nom, pos, mask, share=share, iterations=200, check_every=8)
        pos = pos + res.velocities * TICK_S
        closest = torch.minimum(closest, (pos[:, 0] - pos[:, 1]).norm(dim=-1))
    return closest, res.velocities


def test_desk_closest_approach_and_steady_state():
    """Closed loop, ideal tracking: closest approach >= 1.10 m - the 20 Hz step's shortfall, both settings, both desk
    cases. Steady state: equal moves the pair off together at 0.25 m/s (still Guard; DISCUSSION section 2.9); guard_yields
    keeps the Strike drone at its 0.5 m/s and the Guard drone retreats at 0.5 m/s."""
    gap_b, v_b = _kinematic_closest(gy(1, 1, n=2))
    gap_e, v_e = _kinematic_closest(None)
    assert gap_b.min() >= KEEPOUT_M - DISCRETE_TOL_M and gap_e.min() >= KEEPOUT_M - DISCRETE_TOL_M
    assert (v_b[:, 1, 0] == -0.5).all()
    assert v_b[:, 0, 0].tolist() == pytest.approx([-0.5, -0.5], abs=0.01)
    assert v_e[0, :, 0].tolist() == pytest.approx([-0.25, -0.25], abs=0.01)


def pinch(u_mps, d_m=1.3):
    """A Guard drone at the origin, Strike drones at -d and +d on x, each closing on it at u. Alone, the Guard can meet
    both pairs only if u <= alpha (d^2 - 1.1^2) / (2 d) (0.4615 m/s at d = 1.3 m): the Guard cannot escape above it."""
    return scene([(0, 0, 1), (-d_m, 0, 1), (d_m, 0, 1)], [(0, 0, 0), (u_mps, 0, 0), (-u_mps, 0, 0)])


U_STAR = ALPHA * (1.3 ** 2 - KEEPOUT_M ** 2) / (2 * 1.3)
# Beyond U_STAR the option B answer violates each Guard-Strike pair by 2 d (u - U_STAR) (the Guard stays put by symmetry);
# its residual passes 5 x tolerance at u = U_STAR + 0.01 / 2.6 = U_STAR + 0.0038 m/s.
U_SWITCH = U_STAR + EMERGENCY_RES / (2 * 1.3)


@pytest.mark.parametrize("path", sorted(PATHS))
def test_pinched_guard_below_the_limit_no_fallback(path):
    """u below the limit: option B holds; the Strike drones are untouched; no fallback, no emergency."""
    nom, pos, mask = pinch(U_STAR - 0.02)
    res = filter_velocities_shared(nom, pos, mask, R_M, 1.0, gy(1, 2), filter_fn=PATHS[path], alpha=ALPHA,
                                   iterations=1000, tolerance=TOL)
    assert not res.fallback.any() and not res.emergency.any()
    assert torch.equal(res.velocities[0, 1:], nom[0, 1:])
    assert res.residual.max() <= TOL


@pytest.mark.parametrize("path", sorted(PATHS))
def test_pinched_guard_above_the_limit_falls_back_to_the_even_split(path):
    """u = 0.5 m/s, above the limit: the Guard cannot escape; the game takes today's even-split filter, bit for bit."""
    nom, pos, mask = pinch(0.5)
    kw = dict(alpha=ALPHA, iterations=1000, tolerance=TOL)
    res = filter_velocities_shared(nom, pos, mask, R_M, 1.0, gy(1, 2), filter_fn=PATHS[path], **kw)
    today = PATHS[path](nom, pos, mask, R_M, 1.0, **kw)
    assert res.fallback.all()
    for k in KEYS:
        assert torch.equal(getattr(res, k), getattr(today, k)), k
    assert not torch.equal(res.velocities[0, 1:], nom[0, 1:])          # the Strike drones now give way too


def test_fallback_fires_only_above_its_residual():
    """Sweep u across the limit: the fallback is off up to U_SWITCH - 0.001 m/s (option B kept, with its residual at
    most 5 x tolerance) and on from U_SWITCH + 0.001 m/s; it never fires below the analytic limit U_STAR."""
    us = [U_STAR - 0.05, U_STAR - 0.001, U_STAR + 0.001, U_SWITCH - 0.001, U_SWITCH + 0.001, U_SWITCH + 0.01, 0.5]
    for u in us:
        nom, pos, mask = pinch(u)
        res = filter_velocities_shared(nom, pos, mask, R_M, 1.0, gy(1, 2), alpha=ALPHA, iterations=1000,
                                       tolerance=TOL)
        assert bool(res.fallback) == (u > U_SWITCH), u
        if u <= U_SWITCH:
            assert res.residual.item() <= EMERGENCY_RES and torch.equal(res.velocities[0, 1:], nom[0, 1:]), u


@pytest.mark.parametrize("path", sorted(PATHS))
def test_fallback_games_are_todays_filter_and_the_rest_meet_the_tolerance(path):
    """T2 scenes, every pair, scene team 0 = Guard team: the games that fall back carry today's answer bit for bit;
    every other game has no emergency, residual <= 5 x tolerance, and its Strike rows change only through
    Strike-Strike pairs or the speed cap (never more than an equal-only Strike-team solve, within 0.02 m/s)."""
    nom, pos, mask, cap, scenes = t2_batch(200, "every")
    guard = torch.zeros(200, 8, dtype=torch.bool)
    for k, s in enumerate(scenes):
        guard[k, : len(s.pos_m)] = torch.as_tensor(s.team == 0)
    share = guard_yields_share(guard, 200)
    kw = dict(alpha=ALPHA, iterations=1000, tolerance=TOL)
    res = filter_velocities_shared(nom, pos, mask, R_M, cap, share, filter_fn=PATHS[path], **kw)
    today = PATHS[path](nom, pos, mask, R_M, cap, **kw)
    fb = res.fallback
    assert fb.any() and (~fb).any()
    for k in KEYS:
        assert torch.equal(getattr(res, k)[fb], getattr(today, k)[fb]), k
    assert not res.emergency[~fb].any() and res.residual[~fb].max() <= EMERGENCY_RES
    # the Strike team alone (Strike-Strike pairs only), as the oracle of the Strike rows
    strike_only = mask & ~guard[:, :, None] & ~guard[:, None, :]
    alone = PATHS[path](nom, pos, strike_only, R_M, cap, **kw)
    keep = ~fb & ~alone.emergency
    srow = ~guard & keep[:, None]
    assert (res.velocities[srow] - alone.velocities[srow]).abs().max() <= 0.02


def _strikes_held(s, fp) -> bool:
    """Every Strike drone of the scene is held by option B: nominal within the cap, no active Strike-Strike pair (today's
    pruning bound), so the filter leaves it at its nominal and treats it as the original treats a ``fixed`` row."""
    import numpy as np
    st = np.flatnonzero(s.team == 1)
    for k in st:
        if np.linalg.norm(s.nominal_mps[k]) > s.max_speed_mps:
            return False
        for q in st[st != k]:
            rel = s.pos_m[k] - s.pos_m[q]
            if ALPHA * (rel @ rel - KEEPOUT_M ** 2) < np.linalg.norm(2 * rel) * 2 * s.max_speed_mps:
                return False
    return True


def test_two_stage_oracle_with_cmus_fixed_rows():
    """Option B against CMU's own filter used twice (read-only, float64, 1,000 sweeps): the Strike team alone, then every
    drone with the Strike rows held (``fixed``) at that answer. T2's two-team scenes where both answers need no emergency
    and no fallback: where every Strike drone is held (measured 24 Nov 2026: 43 of 80 such scenes in the first 240), the
    answers are the same (<= 1e-9 m/s). Elsewhere a Strike drone is itself corrected, the share's pruning keeps today's
    bound for its pairs, and the Guard rows reach another feasible point (up to 0.19 m/s off CMU's two-stage answer;
    today's even split is itself up to 0.21 m/s off the exact projection on these scenes, the averaging weights of the
    parallel sweeps): there the test asks only for feasibility (residual <= 5 x tolerance)."""
    fp = _parity()
    import numpy as np
    scenes = [s for s in fp.make_scenes(240, T2_SEED) if s.teams == 2]
    nom, pos, _, cap = fp._batch(scenes, dtype=torch.float64)
    n = len(scenes)
    real = torch.zeros(n, fp.M_MAX, dtype=torch.bool)
    guard = torch.zeros(n, fp.M_MAX, dtype=torch.bool)
    for k, s in enumerate(scenes):
        real[k, : len(s.pos_m)] = True
        guard[k, : len(s.pos_m)] = torch.as_tensor(s.team == 0)
    mask = real[:, :, None] & real[:, None, :] & ~torch.eye(fp.M_MAX, dtype=torch.bool)
    res = filter_velocities_shared(nom, pos, mask, R_M, cap, guard_yields_share(guard, n, dtype=torch.float64),
                                   alpha=ALPHA, iterations=1000, tolerance=TOL)
    held, other = [], []
    for k, s in enumerate(scenes):
        strike = s.team == 1
        idx = np.flatnonzero(strike)
        a = fp.cmu_filter(s.nominal_mps[idx], s.pos_m[idx], safety_radius=R_M, max_speed=s.max_speed_mps, alpha=ALPHA)
        cmd = s.nominal_mps.copy()
        cmd[idx] = a.velocities
        b = fp.cmu_filter(cmd, s.pos_m, safety_radius=R_M, max_speed=s.max_speed_mps, alpha=ALPHA, fixed=strike)
        if a.used_emergency_stop or b.used_emergency_stop or not (a.converged and b.converged) or res.fallback[k]:
            continue
        d = float(np.abs(res.velocities[k, : len(s.pos_m)].numpy() - b.velocities).max())
        (held if _strikes_held(s, fp) else other).append((d, k))
    assert len(held) >= 30 and other, (len(held), len(other))
    assert max(held)[0] <= 1e-9, max(held)
    assert max(res.residual[k].item() for _, k in other) <= EMERGENCY_RES


def test_graph_path_with_shares_matches_dense_early_stop_and_compaction():
    """The graph path's early stop and compaction ladder carry the share buffer: within 1e-5 m/s of the dense early stop
    on 200 T2 scenes (eager on the CPU; the CUDA-graph replay itself is not run in this file)."""
    nom, pos, mask, cap, scenes = t2_batch(200, "every")
    guard = torch.zeros(200, 8, dtype=torch.bool)
    for k, s in enumerate(scenes):
        guard[k, : len(s.pos_m)] = torch.as_tensor(s.team == 0)
    share = guard_yields_share(guard, 200)
    a = run("dense", nom, pos, mask, share=share, cap=cap, check_every=8)
    b = run("graph", nom, pos, mask, share=share, cap=cap, check_every=8, compact=True)
    assert (a.velocities - b.velocities).abs().max() <= 1e-5
    assert torch.equal(a.emergency, b.emergency) and torch.equal(a.corrected, b.corrected)


@pytest.mark.parametrize("path", sorted(PATHS))
def test_share_shape_is_checked(path):
    nom, pos, mask = scene([(0, 0, 1), (DESK_GAP_M, 0, 1)], [(0, 0, 0), (-0.5, 0, 0)])
    with pytest.raises(ValueError, match="pair_share"):
        run(path, nom, pos, mask, share=torch.full((1, 2, 2), 0.5))


# --- part 3: the game setting -----------------------------------------------------------------------------------------

from svg_training.core import safety_filter as sf  # noqa: E402
from svg_training.core.game import RUNNING, Scenario, SvgGame  # noqa: E402
from svg_training.core.game_config import FILTER_SHARES, FilterCfg, load_game_cfg  # noqa: E402
from svg_training.core.physics_layer import load_game_physics_params  # noqa: E402
from svg_training.models.rigid_body import TorchRigidBodyWorld  # noqa: E402

CFG = load_game_cfg(use_local=False)[0]
BACKENDS = ("fitted", "physics")
TRACKING_TOL_M = 0.10         # DISCUSSION section 2.9: tracking lag 0.03-0.10 m measured (HTX-R2); the Starling-layer tests' 1.0 m


def cfg_of(backend="fitted", share=None, landing=False, iterations=50):
    """The committed s2 game, Starling layer on (50 sweeps keep the CPU tests fast); share None = no [filter] change."""
    kw = {"starling.enabled": True, "starling.filter_iterations": iterations, "landing.enabled": landing}
    if share is not None:
        kw["filter.share"] = share
    if backend == "physics":
        kw["starling.backend"] = "physics"
    return CFG.replace(**kw)


def make(cfg, starts, guards=1, strikes=1, side=8.0, n=2):
    sc = Scenario("t", side, (-2.5, 2.5), 0.4, tuple(starts))
    world = None
    if cfg.starling.backend == "physics":
        p = load_game_physics_params(cfg)
        world = TorchRigidBodyWorld(n, guards + strikes, p.airframe, p.physics_dt_s, "cpu")
    return SvgGame(cfg, n, guards, strikes, device="cpu", scenario=sc, world=world, seed=0)


def act(g_cmd, s_cmd, n=2):
    def team(cmds):
        a = torch.zeros(n, len(cmds), 4)
        a[..., :3] = torch.tensor(cmds, dtype=torch.float32)
        return a
    return {"guard": team(g_cmd), "strike": team(s_cmd)}


def chain(g):
    return g._starling.chain if g.cfg.starling.backend == "physics" else g._starling.model.chain


def test_setting_absent_is_equal_and_values_are_checked(tmp_path):
    assert FilterCfg() == CFG.filter and CFG.filter.share == "equal"
    assert FILTER_SHARES == sf.SHARE_MODES
    path = tmp_path / "g.toml"
    text = (ROOT / "configs" / "s2_game.toml").read_text().replace("enabled = false", "enabled = true", 1)
    path.write_text(text + '\n[filter]\nshare = "guard_yields"\n')
    assert load_game_cfg(path, use_local=False)[0].filter == FilterCfg(share="guard_yields")
    path.write_text(text + '\n[filter]\nshare = "equal"\nemergency = "equal"\n')
    with pytest.raises(ValueError, match="unknown key"):
        load_game_cfg(path, use_local=False)
    with pytest.raises(ValueError, match="filter.share"):
        FilterCfg(share="strike_yields")


def test_guard_yields_needs_the_starling_layer_and_the_partner_preset():
    with pytest.raises(ValueError, match="filter.share"):
        CFG.replace(**{"filter.share": "guard_yields"})                         # no filter at all without the layer
    with pytest.raises(ValueError, match="filter.share"):
        cfg_of(share="guard_yields").replace(preset="contact")                   # contact: no Guard-Strike pairs


@pytest.mark.parametrize("backend", BACKENDS)
def test_equal_written_out_plays_the_absent_setting_bit_for_bit(backend):
    starts = ((0.0, 0.0), (-1.3, 0.0))
    rows = {}
    for share in (None, "equal"):
        g = make(cfg_of(backend, share), starts)
        rows[share] = []
        for _ in range(30):
            o = g.step(act([(0.3, 0.2, 0.0)], [(1.0, 0.0, -0.3)]))
            rows[share].append((g.pos_m.clone(), g.vel_mps.clone(), o.info["filter_corrected"].clone()))
        assert chain(g).pair_share is None
    assert any(r[2].any() for r in rows[None])
    for a, b in zip(rows[None], rows["equal"]):
        assert all(torch.equal(x, y) for x, y in zip(a, b))


def _desk_game(backend, share, ticks=60):
    """1v1: a still Guard drone at the origin, the Strike drone from 2.0 m flying at it at full speed (0.5 m/s).
    Returns (closest 3-D gap m, Strike filter corrections [T, N, 3], Guard corrected any tick)."""
    g = make(cfg_of(backend, share), ((0.0, 0.0), (-2.0, 0.0)))
    closest, s_corr, g_hit = 9.0, [], False
    for _ in range(ticks):
        o = g.step(act([(0.0, 0.0, 0.0)], [(1.0, 0.0, 0.0)]))
        assert (o.outcome == RUNNING).all()
        closest = min(closest, float((g.pos_m[:, 0] - g.pos_m[:, 1]).norm(dim=-1).min()))
        s_corr.append(chain(g).correction[:, 1].clone())
        g_hit = g_hit or bool(o.info["filter_corrected"][:, 0].any())
    return closest, torch.stack(s_corr), g_hit


# measured 24 Nov 2026, CPU, 60 ticks: closest approach (guard_yields / equal) fitted 1.058 / 1.072 m, physics 1.080 /
# 1.080 m; the Strike drone's largest correction with equal 0.260 m/s (fitted), 0.258 m/s (physics)
@pytest.mark.parametrize("backend", BACKENDS)
def test_desk_case_in_the_game(backend):
    """guard_yields: the filter never changes the Strike drone's command (bit for bit zero correction), the Guard drone
    gives way, and the pair stays >= 1.10 m - the tracking tolerance apart; equal: the Strike drone is corrected too."""
    gap_b, corr_b, hit_b = _desk_game(backend, "guard_yields")
    gap_e, corr_e, _ = _desk_game(backend, None)
    assert hit_b and (corr_b == 0).all() and corr_e.abs().max() > 0.05
    assert min(gap_b, gap_e) >= KEEPOUT_M - TRACKING_TOL_M, (gap_b, gap_e)


@pytest.mark.parametrize("backend", BACKENDS)
def test_pairs_with_a_landing_drone_stay_equal_in_the_game(backend):
    """[landing] on with guard_yields, 1 Guard + 2 Strike drones (pairs (0,1) (0,2) (1,2)): Guard-Strike pairs (1, 0)
    while all play; once Strike drone 1 is lost and lands (L2.3: an ordinary filter row), its pairs are (1/2, 1/2)."""
    g = make(cfg_of(backend, "guard_yields", landing=True), ((0.0, 0.0), (-1.3, 0.0), (2.5, -2.5)), strikes=2)
    g.schedule_dropout(torch.full((2,), 1, dtype=torch.long), torch.full((2,), 2, dtype=torch.long))
    g.step(act([(0.0, 0.0, 0.0)], [(0.0, 0.0, 0.0)] * 2))
    assert chain(g).pair_share.tolist() == [[[1.0, 0.0], [1.0, 0.0], [0.5, 0.5]]] * 2 and not g.landing.any()
    g.step(act([(0.0, 0.0, 0.0)], [(0.0, 0.0, 0.0)] * 2))           # lost at the end of step 2: landing from then
    assert g.landing[:, 1].all()
    o = g.step(act([(0.0, 0.0, 0.0)], [(0.0, 0.0, 0.0)] * 2))
    assert (o.outcome == RUNNING).all() and g.landing[:, 1].all()
    assert chain(g).pair_share.tolist() == [[[0.5, 0.5], [1.0, 0.0], [0.5, 0.5]]] * 2


# (backend: guard_yields closest band, equal minimum): measured 24 Nov 2026, CPU, 120 ticks: guard_yields 0.393 m fitted,
# 0.597 m physics (fallback on 98 / 46 game-ticks); equal 0.967 m fitted, 0.998 m physics (no fallback: share "equal")
WALL_CASES = {"fitted": ((0.35, 0.45), 0.95), "physics": ((0.55, 0.65), 0.95)}


@pytest.mark.parametrize("backend", BACKENDS)
def test_a_guard_pinned_at_a_wall_known_shortfall(backend):
    """KNOWN SHORTFALL of option B, pinned at its measured value (a regression guard, not an acceptance; for the owner's
    P2 ruling): a still Guard drone at x = 3.6 m, against the +x wall (keep-in edge 3.75 m), and the Strike drone from
    x = 1.6 m flying at it at full speed. The filter does not know the walls: with guard_yields it keeps the Strike drone's
    command and sends the Guard drone through the wall, where the walls clamp it, so the pair closes until the Guard drone
    would need more than the cap (1.0 m/s) and the emergency rule falls back to the even split, which then still gives
    half of every correction to the pinned drone. The pair closes to 0.39 m (fitted; physics 0.60 m, where the Guard drone
    also escapes down to the height band's floor); with equal it stops at 0.97 m (physics 1.00 m), as today."""
    band, eq_min = WALL_CASES[backend]
    closest, fell_back = {}, {}
    for share in ("guard_yields", None):
        g = make(cfg_of(backend, share), ((3.6, 0.0), (1.6, 0.0)))
        lo, fb = 9.0, 0
        for _ in range(120):
            o = g.step(act([(0.0, 0.0, 0.0)], [(1.0, 0.0, 0.0)]))
            assert (o.outcome == RUNNING).all()
            lo = min(lo, float((g.pos_m[:, 0] - g.pos_m[:, 1]).norm(dim=-1).min()))
            fb += int(chain(g).fallback.sum())
        closest[share], fell_back[share] = lo, fb
    assert band[0] <= closest["guard_yields"] <= band[1] and fell_back["guard_yields"] > 0, closest
    assert closest[None] >= eq_min and fell_back[None] == 0, closest


if __name__ == "__main__" and "--write-golden" in sys.argv:
    GOLDEN.parent.mkdir(parents=True, exist_ok=True)
    torch.save({f"{v}/{m}": _golden_run(v, m) for v in VARIANTS for m in ("team", "every")}, GOLDEN)
    print(f"wrote {GOLDEN}")
