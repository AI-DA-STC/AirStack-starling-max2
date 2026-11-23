"""STE task L2.1: filter option B in the training copy (WORK_BREAKDOWN L2.1; ARCHITECTURE section 3, "Option B mathematics").

Part 1, written and committed BEFORE the change: ``"equal"`` (today's even split) stays bit for bit. Golden tensors of the
safety filter on the T2 parity scenes (``scripts/filter_parity.make_scenes``, seed 20261115, the first 500 scenes at
T2's 1,000 sweeps, check_every 0; the first 200 for the early-stop and graph variants), each with T2's team mask and with
an every-pair mask (the partner preset's pairs), saved from commit 743c1901 (branch ste-l2-1 before L2.1). Regenerate
them only from a commit whose filter is known good:

    cd svg_training && PYTHONPATH=source python tests/test_safety_filter_option_b.py --write-golden

CPU, float32, made-up scenes. Observed in the training simulator, not a flight result.
"""
import importlib.util
import pathlib
import sys

import pytest
import torch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
CMU_PKG = ROOT.parent / "AirStack/robot/ros_ws/src/svg_ground_control"
from svg_training.core.safety_filter import filter_velocities  # noqa: E402
from svg_training.core.safety_filter_graph import filter_velocities_graph  # noqa: E402

GOLDEN = ROOT / "tests" / "data" / "safety_filter_equal_golden.pt"
T2_SEED = 20261115            # scripts/filter_parity.DEFAULT_SEED, the T2 record's scene seed
R_M, ALPHA, TOL = 0.55, 2.5, 2e-3
KEYS = ("velocities", "corrected", "residual", "emergency", "converged")


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


if __name__ == "__main__" and "--write-golden" in sys.argv:
    GOLDEN.parent.mkdir(parents=True, exist_ok=True)
    torch.save({f"{v}/{m}": _golden_run(v, m) for v in VARIANTS for m in ("team", "every")}, GOLDEN)
    print(f"wrote {GOLDEN}")
