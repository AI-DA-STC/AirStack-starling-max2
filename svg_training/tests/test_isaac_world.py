"""The Isaac Lab world (compat/isaaclab_232.IsaacWorld) against what we specified and against the torch reference
world (S2b plan Task 5, Review Focus 2). Every test reads one smoke run of ``scripts/physics_agreement.py --headless
--smoke`` started in a subprocess. Marked ``isaac``: skipped unless SVG_ISAAC_TESTS=1 (tests/conftest.py, D12).

    scripts/isaac_preflight.sh && docker/run.sh 'SVG_ISAAC_TESTS=1 $SVG_PY -m pytest -q -m isaac'
"""
import json
import os
import pathlib
import subprocess
import sys

import pytest

from svg_training.core.game_config import load_s2b_gates

pytestmark = pytest.mark.isaac
ROOT = pathlib.Path(__file__).resolve().parents[1]
GATES = load_s2b_gates()["agreement_gates"]


@pytest.fixture(scope="module")
def smoke(tmp_path_factory):
    out = tmp_path_factory.mktemp("isaac_smoke") / "smoke.json"
    python = os.environ.get("SVG_ISAACLAB") or sys.executable     # container: Isaac Lab's launcher; host: conda
    env = dict(os.environ, PYTHONPATH=str(ROOT / "source"))
    r = subprocess.run([python, "scripts/physics_agreement.py", "--headless", "--smoke", "--out", str(out)],
                       cwd=ROOT, env=env, capture_output=True, text=True, timeout=1200)
    assert r.returncode == 0 and out.exists(), (r.stdout[-3000:], r.stderr[-3000:])
    return json.loads(out.read_text())


def test_isaac_world_mass_inertia_readback(smoke):        # Review Focus 2
    assert smoke["mass_rel_err"] <= 1e-4 and smoke["inertia_rel_err"] <= 1e-4
    assert smoke["com_offset_max_m"] <= 1e-6                # centre of mass at the body origin (D2)
    s = smoke["body_settings"]                              # what the USD holds for PhysX, read back
    assert s["enable_gyroscopic_forces"] is True
    assert s["linear_damping"] == 0.0 and s["angular_damping"] == 0.0
    assert s["sleep_threshold"] == 0.0 and s["max_angular_velocity_deg_s"] >= 1e4
    assert s["has_collider"] is False


def test_isaac_hover_holds(smoke):                        # hover wrench 2 s
    assert smoke["hover_drift_max_m"] < 1e-3
    assert smoke["hover_rate_max_rad_s"] < 1e-3


def test_isaac_wrench_is_body_frame(smoke):               # body yawed 90 deg, +x body force -> +y world acceleration
    ax, ay, az = smoke["body_frame_acc_mps2"]
    want = smoke["body_frame_acc_want_mps2"]
    assert ay == pytest.approx(want, rel=0.02) and abs(ax) < 0.01 * want and abs(az) < 0.01 * want


# Known gap, accepted: ledger T10 (records/2026-11-16_s2b_agreement_record.md) FAILED this gate, 1.15 mm against
# 1.0 mm (this smoke: 1.067 mm). Owner's ruling, 16 November 2026: the FAIL stands in the ledger and is accepted,
# because the gap comes from PhysX's GPU attitude integration (PhysX on the CPU: 0.021 mm) and the closed-loop gates
# pass about 30 times inside. Strict: if the gap ever closes, this XPASSes, the run fails, and the mark must go.
@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason="T10 FAIL accepted by the owner 16 Nov 2026: PhysX GPU attitude integration, ~1.07-1.15 mm "
                          "against the 1.0 mm open-loop gate; closed loop ~30x inside its gates")
def test_isaac_open_loop_matches_torch(smoke):            # smoke version of gate (2), position part
    assert smoke["open_loop_pos_max_m"] <= GATES["open_loop_pos_max_m"]


def test_isaac_open_loop_angle_and_nan(smoke):            # smoke version of gate (2), the parts that pass
    assert smoke["open_loop_angle_max_deg"] <= GATES["open_loop_angle_max_deg"]
    assert smoke["nan"] <= GATES["nan_max"]


def test_isaac_state_write_reaches_physx(smoke):          # a written state (with body rates) carried into PhysX:
    assert smoke["write_readback_max_err"] < 1e-4         # one free step later Isaac agrees with the torch world


def test_isaac_first_step_after_play_is_right(smoke):    # the settling step in IsaacWorld._after_play
    assert smoke["first_step_ratio_err"] < 1e-4
