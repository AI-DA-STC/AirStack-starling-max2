"""Tests for the fixed-shape, CUDA-graph path of the safety filter (core/safety_filter_graph.py), opt-in.

Equivalence gate (written before any measurement, 18 Nov 2026, lead's brief): on (a) T2's 2,000 scenes (seed 20261115) at
the T8 setting (1,000 sweeps, check_every 8) and the hand-made / early-stop cases of tests/test_safety_filter.py, and (b) 200
recorded hangar-game states at 1,000 games from Phase 4 row 5 (``scripts/filter_graph_check.py record``: 100 filter calls of the
``random`` arm and 100 of ``parked_s20``, at ticks 0, 2, 4, ..., 198 of one game from fresh starts (the crowded opening, where the
filter works hardest; 200 ticks per arm to fit the 0.5 GPU-hour cap), the P0 probe's seed; file
``runs/nus_port/filter_graph/states.pt``, on the 5090 only), the new path's velocities equal the existing path's within
``GATE_MAX_ABS_MPS`` = 1e-6 m/s max abs (float32), with the same per-game converged flags (``FilterResult.converged``), the same
emergency and corrected flags. The reference is the existing path with the same ``check_every`` on the same device. The
tolerance is never loosened after a measurement; the measured max difference is reported by ``filter_graph_check.py``.

Measured on CUDA after the gate was written (18 Nov 2026, T2 scenes): the gate FAILS on CUDA, and no fixed-shape path can pass it, because
the reference itself depends on batch shapes there (cuBLAS picks its kernel by the batch size, so the ``einsum`` of a sweep rounds a row
differently in a different-sized working batch): the existing path's own check_every 0 and 8 differ by up to 1.65 m/s (unconverged games)
and 2.6e-6 m/s (converged games), with equal flags. The gate tests are kept unchanged. Added after that result, and labelled so: the
default graph path (``compact=False``: full batch, no re-gather) equals the existing FIXED loop (check_every 0) bit for bit
(``test_bit_identical_to_fixed_loop_*``), and ``scripts/filter_graph_check.py equiv`` reports, beside the gate's numbers, the reference's
own spread (existing check_every 0 vs 8) on the same scenes and recorded states.

CPU tests run the masked loop eagerly (no CUDA graph on the CPU); CUDA tests capture and replay graphs. The full suite runs with
CUDA hidden, so run this file once more on the GPU: ``PYTHONPATH=source python -m pytest -q tests/test_safety_filter_graph.py``.
"""
import ast
import importlib.util
import pathlib
import sys

import pytest
import torch

ROOT = pathlib.Path(__file__).resolve().parents[1]
CMU_PKG = ROOT.parent / "AirStack/robot/ros_ws/src/svg_ground_control"
STATES = ROOT / "runs" / "nus_port" / "filter_graph" / "states.pt"
GATE_MAX_ABS_MPS = 1e-6     # FIXED before measuring (lead's brief, 18 Nov 2026); never loosened
R_M = 0.55

from svg_training.core import safety_filter as sf  # noqa: E402
from svg_training.core import safety_filter_graph as sfg  # noqa: E402
from svg_training.core.safety_filter import filter_velocities, team_pair_mask  # noqa: E402
from svg_training.core.safety_filter_graph import filter_velocities_graph  # noqa: E402

CUDA = torch.cuda.is_available()
needs_cuda = pytest.mark.skipif(not CUDA, reason="no CUDA device")


def _parity():
    if not (CMU_PKG / "svg_ground_control").is_dir():
        pytest.skip(f"CMU's svg_ground_control is not on this machine ({CMU_PKG}); run on the host")
    spec = importlib.util.spec_from_file_location("filter_parity", ROOT / "scripts/filter_parity.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _same(a, b, tol=GATE_MAX_ABS_MPS):
    """The gate: velocities within tol (max abs, NaN-free), converged / emergency / corrected flags equal."""
    assert a.velocities.shape == b.velocities.shape
    assert torch.isfinite(a.velocities).all() and torch.isfinite(b.velocities).all()
    assert float((a.velocities - b.velocities).abs().max()) <= tol
    assert a.converged is not None and b.converged is not None
    assert torch.equal(a.converged, b.converged)
    assert torch.equal(a.emergency, b.emergency)
    assert torch.equal(a.corrected, b.corrected)


def _t2_batch(count=2000, seed=20261115, device="cpu"):
    fp = _parity()
    nom, pos, mask, cap = fp._batch(fp.make_scenes(count, seed))
    return nom.to(device), pos.to(device), mask.to(device), cap.to(device)


def _random_batch(n, m, seed, device="cpu", spread=3.0, drop=0.25):
    gen = torch.Generator().manual_seed(seed)
    pos = torch.rand(n, m, 3, generator=gen) * spread
    nom = (torch.rand(n, m, 3, generator=gen) - 0.5) * 4.0
    live = torch.rand(n, m, generator=gen) > drop
    mask = ~torch.eye(m, dtype=torch.bool).expand(n, m, m) & live[:, :, None] & live[:, None, :]
    return nom.to(device), pos.to(device), mask.to(device)


# --- the existing path is unchanged; FilterResult.converged ------------------------------------------

def test_existing_file_keeps_one_loop():
    """The graph path lives in its own module: core/safety_filter.py keeps `range(iterations)` as its only loop."""
    tree = ast.parse(pathlib.Path(sf.__file__).read_text())
    assert len([n for n in ast.walk(tree) if isinstance(n, (ast.For, ast.While, ast.comprehension))]) == 1


def test_converged_flag_existing_paths():
    """converged [N] bool: every group met the stopping test, or the game had no active pair. Equal for check_every 0 and 8."""
    nom, pos, mask = _random_batch(64, 6, 3)
    far = torch.arange(6, dtype=torch.float32)[:, None] * torch.tensor([10.0, 0.0, 0.0])
    pos[:4] = far                                         # 4 games with no active pair
    pos[4, 1] = pos[4, 0]                                 # a coincident pair: never converges
    mask[4] = ~torch.eye(6, dtype=torch.bool)
    a = filter_velocities(nom, pos, mask, R_M, 2.0, iterations=300)
    b = filter_velocities(nom, pos, mask, R_M, 2.0, iterations=300, check_every=8)
    assert a.converged.shape == (64,) and a.converged.dtype == torch.bool
    assert a.converged[:4].all() and not a.converged[4]
    assert torch.equal(a.converged, b.converged)


# --- (a) the CPU (eager masked loop): equal to the existing path -------------------------------------

def test_t2_scenes_t8_setting_cpu():
    """T2's 2,000 scenes at T8's setting (1,000 sweeps, check_every 8), float32, CPU."""
    nom, pos, mask, cap = _t2_batch()
    a = filter_velocities(nom, pos, mask, R_M, cap, iterations=1000, check_every=8)
    b = filter_velocities_graph(nom, pos, mask, R_M, cap, iterations=1000, check_every=8)
    _same(a, b)


@pytest.mark.parametrize("check_every", [0, 8])
def test_per_game_masks_with_dropouts_cpu(check_every):
    nom, pos, mask = _random_batch(64, 8, 19)
    a = filter_velocities(nom, pos, mask, R_M, 2.0, iterations=300, check_every=check_every)
    b = filter_velocities_graph(nom, pos, mask, R_M, 2.0, iterations=300, check_every=check_every)
    _same(a, b)


def test_inactive_games_and_coincident_and_non_finite_cpu():
    """Games with no active pair, a coincident pair (never converges, emergency), a non-finite command."""
    nom, pos, mask = _random_batch(32, 6, 5)
    pos[:5] = torch.arange(6, dtype=torch.float32)[:, None] * torch.tensor([10.0, 0.0, 0.0])
    pos[5, 1] = pos[5, 0]
    mask[5] = ~torch.eye(6, dtype=torch.bool)
    nom[6, 2, 0] = float("nan")
    a = filter_velocities(nom, pos, mask, R_M, 2.0, iterations=300, check_every=8)
    b = filter_velocities_graph(nom, pos, mask, R_M, 2.0, iterations=300, check_every=8)
    _same(a, b)
    assert a.emergency[5] and not a.converged[5]


@pytest.mark.parametrize("compact", [False, True])
@pytest.mark.parametrize("block", [1, 3, 8, 32])
def test_block_length_does_not_change_the_answer_cpu(block, compact):
    """Converged groups are frozen, so the check cadence (block length) changes only when the loop stops; 300 is not a multiple of
    3, 8 or 32 (the remainder block)."""
    nom, pos, mask = _random_batch(48, 6, 29)
    a = filter_velocities(nom, pos, mask, R_M, 2.0, iterations=300, check_every=8)
    b = filter_velocities_graph(nom, pos, mask, R_M, 2.0, iterations=300, check_every=8, block=block, compact=compact)
    _same(a, b)


def test_compact_ladder_matches_early_stop_cpu():
    """compact=True (pre-frozen games with no pair, capacity ladder) on 600 games of which most converge fast: equal to the existing
    early stop on the CPU."""
    nom, pos, mask = _random_batch(600, 6, 47, spread=6.0)
    a = filter_velocities(nom, pos, mask, R_M, 2.0, iterations=300, check_every=8)
    b = filter_velocities_graph(nom, pos, mask, R_M, 2.0, iterations=300, check_every=8, compact=True)
    _same(a, b)


# --- added after the T2 CUDA result (labelled): the default graph path is the FIXED loop bit for bit --------------------------

def _equal_all(a, b):
    for x, y in ((a.velocities, b.velocities), (a.corrected, b.corrected), (a.residual, b.residual), (a.emergency, b.emergency),
                 (a.converged, b.converged)):
        assert torch.equal(x, y)


@pytest.mark.parametrize("check_every", [0, 8])
def test_bit_identical_to_fixed_loop_cpu(check_every):
    nom, pos, mask, cap = _t2_batch(400, 20261115)
    a = filter_velocities(nom, pos, mask, R_M, cap, iterations=1000)
    b = filter_velocities_graph(nom, pos, mask, R_M, cap, iterations=1000, check_every=check_every)
    _equal_all(a, b)


def test_float64_and_per_drone_cap_cpu():
    nom, pos, mask = _random_batch(40, 6, 31)
    nom, pos = nom.double(), pos.double()
    cap = 1.0 + torch.rand(40, 6, 1, generator=torch.Generator().manual_seed(2), dtype=torch.float64)
    a = filter_velocities(nom, pos, mask, R_M, cap, iterations=200, check_every=8)
    b = filter_velocities_graph(nom, pos, mask, R_M, cap, iterations=200, check_every=8)
    _same(a, b)


def test_rejects_like_the_existing_path():
    nom, pos, mask = _random_batch(4, 3, 1)
    with pytest.raises(ValueError, match="fixed"):
        filter_velocities_graph(nom, pos, mask, R_M, 2.0, fixed=torch.tensor([True, False, False]))
    with pytest.raises(ValueError, match="check_every"):
        filter_velocities_graph(nom, pos, mask, R_M, 2.0, check_every=-1)
    with pytest.raises(ValueError, match="block"):
        filter_velocities_graph(nom, pos, mask, R_M, 2.0, block=-1)


def test_capacity_ladder():
    """Working capacities: the full batch, then halves down to the floor; the smallest rung that holds the live count."""
    assert sfg._rung(1000, 1000, 64) == 1000
    assert sfg._rung(1000, 501, 64) == 1000
    assert sfg._rung(1000, 500, 64) == 500
    assert sfg._rung(1000, 126, 64) == 250
    assert sfg._rung(1000, 3, 64) == 64
    assert sfg._rung(40, 3, 64) == 40


# --- the game's switch -------------------------------------------------------------------------------

def test_config_switch_is_off_by_default_and_selects_the_graph_path():
    from svg_training.core.game_config import StarlingLayerCfg, load_game_cfg
    from svg_training.core.starling_layer import filter_fn
    assert StarlingLayerCfg().filter_cuda_graph is False
    for name in ("s2_game.toml", "nus_hangar_game.toml"):
        cfg, _ = load_game_cfg(ROOT / "configs" / name, use_local=False)
        assert cfg.starling.filter_cuda_graph is False and filter_fn(cfg) is None
    on = cfg.replace(**{"starling.filter_cuda_graph": True})
    assert filter_fn(on) is filter_velocities_graph


def test_starling_layer_uses_the_switch():
    from svg_training.core.game_config import load_game_cfg
    from svg_training.core.starling_layer import StarlingLayer
    cfg, _ = load_game_cfg(ROOT / "configs" / "s2_game.toml", use_local=False)
    cfg = cfg.replace(**{"starling.enabled": True})
    off = StarlingLayer(cfg, 4, 2, 2, "cpu")
    on = StarlingLayer(cfg.replace(**{"starling.filter_cuda_graph": True}), 4, 2, 2, "cpu")
    assert off.model.chain._filter_fn is filter_velocities
    assert on.model.chain._filter_fn is filter_velocities_graph


# --- (a) on CUDA: graphs captured and replayed --------------------------------------------------------

@needs_cuda
def test_t2_scenes_t8_setting_cuda():
    nom, pos, mask, cap = _t2_batch(device="cuda")
    a = filter_velocities(nom, pos, mask, R_M, cap, iterations=1000, check_every=8)
    b = filter_velocities_graph(nom, pos, mask, R_M, cap, iterations=1000, check_every=8)
    _same(a, b)


@needs_cuda
@pytest.mark.parametrize("check_every", [0, 8])
def test_per_game_masks_cuda(check_every):
    nom, pos, mask = _random_batch(3000, 6, 37, device="cuda")
    cap = torch.tensor(1.0, device="cuda")
    a = filter_velocities(nom, pos, mask, R_M, cap, iterations=300, check_every=check_every)
    b = filter_velocities_graph(nom, pos, mask, R_M, cap, iterations=300, check_every=check_every)
    _same(a, b)
    c = filter_velocities_graph(nom, pos, mask, R_M, cap, iterations=300, check_every=check_every)   # replay of cached graphs
    _same(b, c, tol=0.0)


@needs_cuda
def test_inactive_coincident_non_finite_cuda():
    nom, pos, mask = _random_batch(32, 6, 5)
    pos[:5] = torch.arange(6, dtype=torch.float32)[:, None] * torch.tensor([10.0, 0.0, 0.0])
    pos[5, 1] = pos[5, 0]
    mask[5] = ~torch.eye(6, dtype=torch.bool)
    nom[6, 2, 0] = float("nan")
    nom, pos, mask = nom.cuda(), pos.cuda(), mask.cuda()
    a = filter_velocities(nom, pos, mask, R_M, 2.0, iterations=300, check_every=8)
    b = filter_velocities_graph(nom, pos, mask, R_M, 2.0, iterations=300, check_every=8)
    _same(a, b)


@needs_cuda
def test_graph_equals_eager_masked_loop_cuda():
    """Replaying a captured graph gives the eager masked loop's bits (same kernels)."""
    nom, pos, mask = _random_batch(2000, 6, 41, device="cuda")
    cap = torch.tensor(1.0, device="cuda")
    a = filter_velocities_graph(nom, pos, mask, R_M, cap, iterations=200, check_every=8, use_graph=False)
    b = filter_velocities_graph(nom, pos, mask, R_M, cap, iterations=200, check_every=8, use_graph=True)
    _same(a, b, tol=0.0)


@needs_cuda
@pytest.mark.parametrize("check_every", [0, 8])
def test_bit_identical_to_fixed_loop_cuda(check_every):
    nom, pos, mask, cap = _t2_batch(device="cuda")
    a = filter_velocities(nom, pos, mask, R_M, cap, iterations=1000)
    b = filter_velocities_graph(nom, pos, mask, R_M, cap, iterations=1000, check_every=check_every)
    _equal_all(a, b)


@needs_cuda
def test_capacities_replayed_out_of_capture_order_cuda():
    """Graphs of several capacities share one memory pool: replay them in another order than captured, compare with the eager loop."""
    cap = torch.tensor(1.0, device="cuda")
    for n, seed in ((3000, 51), (256, 52), (3000, 53), (1000, 54), (256, 55)):
        nom, pos, mask = _random_batch(n, 6, seed, device="cuda", spread=4.0)
        for compact in (False, True):
            a = filter_velocities_graph(nom, pos, mask, R_M, cap, iterations=120, check_every=8, compact=compact, use_graph=False)
            b = filter_velocities_graph(nom, pos, mask, R_M, cap, iterations=120, check_every=8, compact=compact, use_graph=True)
            _equal_all(a, b)


@needs_cuda
def test_host_syncs_cuda():
    """check_every 0: no host sync once the graphs exist; check_every k: no more than one flagged sync per block (the count is read
    late from pinned memory through an event, which sync-debug mode does not flag; changed after the pipelined read went in)."""
    import warnings
    nom, pos, mask = _random_batch(256, 6, 43, device="cuda")
    cap = torch.tensor(1.0, device="cuda")
    filter_velocities_graph(nom, pos, mask, R_M, cap, iterations=40, check_every=0)   # capture
    torch.cuda.synchronize()
    torch.cuda.set_sync_debug_mode("error")
    try:
        filter_velocities_graph(nom, pos, mask, R_M, cap, iterations=40, check_every=0)
    finally:
        torch.cuda.set_sync_debug_mode("default")
    filter_velocities_graph(nom, pos, mask, R_M, cap, iterations=40, check_every=8)   # capture
    torch.cuda.synchronize()
    torch.cuda.set_sync_debug_mode("warn")
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            filter_velocities_graph(nom, pos, mask, R_M, cap, iterations=40, check_every=8)
    finally:
        torch.cuda.set_sync_debug_mode("default")
    syncs = [w for w in caught if "synchroniz" in str(w.message)]
    assert len(syncs) <= 40 // 8 + 1


# --- (b) 200 recorded hangar-game states (5090 only) --------------------------------------------------

@needs_cuda
@pytest.mark.skipif(not STATES.exists(), reason=f"recorded states not on this machine ({STATES}; 5090 only)")
def test_recorded_hangar_states_cuda():
    data = torch.load(STATES, map_location="cuda", weights_only=False)
    states = data["states"]
    assert len(states) == 200 and {s["arm"] for s in states} == {"random", "parked_s20"}
    worst = 0.0
    for s in states:
        kw = dict(s["kwargs"])
        a = filter_velocities(s["nominal"], s["pos"], s["mask"], s["radius_m"], s["cap"], **kw)
        b = filter_velocities_graph(s["nominal"], s["pos"], s["mask"], s["radius_m"], s["cap"], **kw)
        _same(a, b)
        worst = max(worst, float((a.velocities - b.velocities).abs().max()))
    print(f"recorded states: worst max abs difference {worst!r} m/s over {len(states)} states")
