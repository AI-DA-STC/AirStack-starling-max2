# Starling 2 Max in the SVG Isaac Sim — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the SVG Isaac Sim spawn Starling 2 Max drones with CMU's sys-ID dynamics instead of the Iris, through the unchanged launch → Pegasus → PX4 SITL → MAVROS → swarm-commander path.

**Architecture:** The vehicle USD only carries physics (mass, inertia, rotors, joints); Pegasus builds the OmniGraph and applies rotor forces in code. We add a cleaned Starling USD, a Pegasus vehicle config with CMU's thrust constants and motor lag selected by USD file name, a PX4 SITL airframe file bind-mounted into the Isaac container, and two env-var overrides in the launch script. Iris behaviour is untouched when the env vars are unset.

**Tech Stack:** Isaac Sim 5.1 image `airlab-docker.andrew.cmu.edu/airstack/airstack:v0.18.0_isaac-sim` (Python 3.11, pxr, trimesh 4.5.1, numpy 1.26), Pegasus Simulator (vendored, AirStack fork), PX4 v1.16.1 SITL, docker compose, ROS 2 Jazzy robot container.

**Spec:** `docs/superpowers/specs/2026-10-19-starling2max-sim-design.md`

## Global Constraints

- Work and commit in the **live clone** `~/AirStack-starling-max2` (docker mounts it); the mirror `~/Documents/GitHub/AirStack-starling-max2` pulls from it in the last task. Never push (the user pushes via GitHub Desktop).
- `PEG` below = `AirStack/simulation/isaac-sim/extensions/PegasusSimulator/extensions/pegasus.simulator/pegasus/simulator` (repo-relative). `ISAAC` = `AirStack/simulation/isaac-sim`.
- Constants, verbatim from the spec: mass 0.557 kg (already in the USD); `rotor_constant` 3.964738e-6; `rolling_moment_coefficient` 5.38697e-8; motor time constant 0.072 s; `rot_dir` [-1, -1, 1, 1]; `max_rotor_velocity` 1450 rad/s; PX4 `KM` 0.0136; `MPC_THR_HOVER` 0.36; rotor positions FLU r0 (+0.095, −0.13), r1 (−0.095, +0.13), r2 (+0.095, +0.13), r3 (−0.095, −0.13).
- Default behaviour must not change: with `DRONE_USD` and `PX4_VEHICLE_MODEL` unset, the Iris spawns exactly as today.
- The 98 MB original `isaac_sim/starlingmax2.usd` is never committed; the cleaned asset is.
- Python inside the Isaac image is only reachable as `/isaac-sim/python.sh`; `pxr` is a namespace package assembled from `/isaac-sim/extscache/*/pxr` (the wrapper in Task 2 handles this).
- Importing any `pegasus.simulator.*` module normally triggers `pegasus/simulator/__init__.py` → `extension.py` → Omniverse. Unit tests therefore stub the three package modules in `sys.modules` before importing a leaf module (pattern given in Task 3).

## Review Focus

Inputs the spec implies but no task's tests exercise, most likely to bite first:

1. **USD stem with unexpected casing or suffix** (`StarlingMax2.usdc`, `starling2max_v2.usd`) → must still select the Starling config or fall back to Iris loudly, never crash. Pinned in Task 4's test.
2. **Env var set to an empty string** (`DRONE_USD=`) → launch must treat it as unset, not reference an empty path. Pinned in Task 6's test.
3. **Decimated mesh with stale per-vertex primvars** (`normals`, `primvars:st` sized for 1.2 M faces) → Isaac logs warnings or renders black; the cleaner must drop them and recompute `extent`. Pinned in Task 2's verification dump.
4. **Lag curve at the first tick** (no previous velocity) → must start from the clamped reference, not from zero producing a thrust spike. Pinned in Task 3's test.
5. **Airframe file not executable or missing from the mount** → PX4 prints `Unknown model pegasus_starling2max` and the drone never arms. Pinned in Task 5's container check.

---

### Task 1: Repo hygiene — ignore the raw USD, commit the sys-ID PDF

**Files:**
- Create: `isaac_sim/.gitignore`
- Commit: `isaac_sim/Starling 2 Max Sys ID Results - Slite.pdf` (already on disk)

**Interfaces:**
- Produces: `isaac_sim/starlingmax2.usd` stays local-only; the PDF is the citable source for every constant in later tasks.

- [ ] **Step 1: Write the ignore file**

```bash
cd ~/AirStack-starling-max2
printf '# CMU raw sys-ID asset (98 MB, body mesh 1.2 M faces) — the cleaned copy lives in\n# AirStack/simulation/isaac-sim/assets/robots/starling2max.usd\nstarlingmax2.usd\n' > isaac_sim/.gitignore
```

- [ ] **Step 2: Verify git sees the PDF and the ignore file but not the USD**

Run: `git -C ~/AirStack-starling-max2 status --short isaac_sim/`
Expected:
```
?? isaac_sim/.gitignore
?? "isaac_sim/Starling 2 Max Sys ID Results - Slite.pdf"
```
(no `starlingmax2.usd` line)

- [ ] **Step 3: Commit**

```bash
cd ~/AirStack-starling-max2
git add isaac_sim/.gitignore "isaac_sim/Starling 2 Max Sys ID Results - Slite.pdf"
git commit -m "sim: add CMU Starling 2 Max sys-ID results (PDF); ignore the raw 98 MB USD"
```

---

### Task 2: Cleaned Starling asset — `starling2max.usd`

**Files:**
- Create: `AirStack/simulation/isaac-sim/tools/isaac_python.sh` (runs a script with the image's Python + pxr + Pegasus on the path)
- Create: `AirStack/simulation/isaac-sim/tools/dump_usd.py` (prim-tree dump used as the acceptance check)
- Create: `AirStack/simulation/isaac-sim/tools/clean_starling_usd.py`
- Create: `AirStack/simulation/isaac-sim/assets/robots/starling2max.usd` (generated)

**Interfaces:**
- Produces: `tools/isaac_python.sh <script.py> [args…]` — later tasks run unit tests with it. Repo root is mounted at `/repo` inside the container; the Pegasus extension root (`…/extensions/pegasus.simulator`) is on `PYTHONPATH`.
- Produces: the asset at container path `/isaac-sim/AirStack/simulation/isaac-sim/assets/robots/starling2max.usd` (Task 6 and the RUNBOOK use this exact path).

- [ ] **Step 1: Write the Isaac-Python wrapper**

```bash
cat > ~/AirStack-starling-max2/AirStack/simulation/isaac-sim/tools/isaac_python.sh <<'EOF'
#!/usr/bin/env bash
# Run a Python script with the Isaac Sim image's interpreter, pxr (USD) and the
# vendored Pegasus extension importable — no GPU, no Kit app, no running container.
#   tools/isaac_python.sh path/to/script.py [args...]      (paths relative to the repo root)
# Set ISAAC_PIP="pkg1 pkg2" to pip-install extras into the throw-away container first.
set -euo pipefail
REPO=$(cd "$(dirname "$0")/../../../.." && pwd)          # AirStack-starling-max2 repo root
IMAGE=${ISAAC_IMAGE:-airlab-docker.andrew.cmu.edu/airstack/airstack:v0.18.0_isaac-sim}
docker run --rm --entrypoint "" -v "$REPO":/repo -w /repo -e ISAAC_PIP="${ISAAC_PIP:-}" "$IMAGE" bash -c '
  set -e
  PXR=$(find /isaac-sim -type d -name pxr 2>/dev/null | xargs -n1 dirname | sort -u | tr "\n" ":")
  LIBS=$(find /isaac-sim \( -name "libusd_*.so*" -o -name "libtf.so*" \) 2>/dev/null | xargs -n1 dirname | sort -u | tr "\n" ":")
  export PYTHONPATH="/repo/AirStack/simulation/isaac-sim/extensions/PegasusSimulator/extensions/pegasus.simulator:${PXR}${PYTHONPATH:-}"
  export LD_LIBRARY_PATH="${LIBS}${LD_LIBRARY_PATH:-}"
  if [ -n "$ISAAC_PIP" ]; then /isaac-sim/python.sh -m pip install -q $ISAAC_PIP; fi
  cd /isaac-sim && exec ./python.sh "$@"' _ "$@" 2>&1 | grep -v -E "^\[[0-9.]+s\]|^\[Warning\]|Warning: " || true
EOF
chmod +x ~/AirStack-starling-max2/AirStack/simulation/isaac-sim/tools/isaac_python.sh
```

- [ ] **Step 2: Write the dump script (acceptance tool)**

```bash
cat > ~/AirStack-starling-max2/AirStack/simulation/isaac-sim/tools/dump_usd.py <<'EOF'
"""Print a vehicle USD's physics-relevant prim tree so two files can be diffed.
Usage (host): AirStack/simulation/isaac-sim/tools/isaac_python.sh AirStack/simulation/isaac-sim/tools/dump_usd.py <file.usd>
"""
import sys
from pxr import Usd, UsdGeom, UsdPhysics

st = Usd.Stage.Open(sys.argv[1])
print("upAxis", UsdGeom.GetStageUpAxis(st), "metersPerUnit", UsdGeom.GetStageMetersPerUnit(st),
      "defaultPrim", st.GetDefaultPrim().GetPath() if st.GetDefaultPrim() else None)
for prim in st.Traverse():
    t = prim.GetTypeName()
    apis = ",".join(sorted(prim.GetAppliedSchemas()))
    line = f"{prim.GetPath()} [{t}] {{{apis}}}"
    if prim.HasAPI(UsdPhysics.MassAPI):
        m = UsdPhysics.MassAPI(prim)
        line += f" mass={m.GetMassAttr().Get()} I={m.GetDiagonalInertiaAttr().Get()} com={m.GetCenterOfMassAttr().Get()}"
    if t == "Xform" and prim.HasAPI(UsdPhysics.RigidBodyAPI):
        tr = UsdGeom.Xformable(prim).GetLocalTransformation().ExtractTranslation()
        line += f" T=({tr[0]:.4f},{tr[1]:.4f},{tr[2]:.4f})"
    if t == "PhysicsRevoluteJoint":
        j = UsdPhysics.RevoluteJoint(prim)
        line += f" axis={j.GetAxisAttr().Get()} body0={list(j.GetBody0Rel().GetTargets())} body1={list(j.GetBody1Rel().GetTargets())}"
    if t == "Mesh":
        mesh = UsdGeom.Mesh(prim)
        fvc = mesh.GetFaceVertexCountsAttr().Get() or []
        pts = mesh.GetPointsAttr().Get() or []
        approx = UsdPhysics.MeshCollisionAPI(prim).GetApproximationAttr().Get() if prim.HasAPI(UsdPhysics.MeshCollisionAPI) else "-"
        pvs = [p.GetName() for p in UsdGeom.PrimvarsAPI(prim).GetPrimvars()]
        line += f" faces={len(fvc)} points={len(pts)} collision={approx} normals={mesh.GetNormalsAttr().HasAuthoredValue()} primvars={pvs}"
    print(line)
EOF
```

- [ ] **Step 3: Record the baseline dump of the raw file**

Run:
```bash
cd ~/AirStack-starling-max2
AirStack/simulation/isaac-sim/tools/isaac_python.sh AirStack/simulation/isaac-sim/tools/dump_usd.py isaac_sim/starlingmax2.usd > /tmp/starling_raw.txt
grep -c . /tmp/starling_raw.txt; grep 'body/body' /tmp/starling_raw.txt
```
Expected: ~24 lines; the body line shows `faces=1200408 points=1127811 collision=convexHull normals=True primvars=['primvars:displayColor', 'primvars:displayOpacity', 'primvars:normals', 'primvars:st']`; a `/vehicle/defaultLight [DistantLight]` line is present.

- [ ] **Step 4: Write the cleaner**

```bash
cat > ~/AirStack-starling-max2/AirStack/simulation/isaac-sim/tools/clean_starling_usd.py <<'EOF'
"""Produce the committed Starling 2 Max vehicle asset from CMU's raw sys-ID USD.

Changes made (and nothing else):
  * /vehicle/body/body mesh decimated to TARGET_FACES triangles (quadric decimation,
    trimesh + fast_simplification); stale per-vertex data (normals, primvars:normals,
    primvars:st) dropped, extent recomputed; the convexHull collider and the material
    binding are untouched.
  * /vehicle/defaultLight removed (it would be instanced once per spawned drone).
Mass, inertia, centre of mass, rotors, joints and colliders are byte-identical.

Usage (host):
  ISAAC_PIP=fast_simplification AirStack/simulation/isaac-sim/tools/isaac_python.sh \
      AirStack/simulation/isaac-sim/tools/clean_starling_usd.py \
      isaac_sim/starlingmax2.usd AirStack/simulation/isaac-sim/assets/robots/starling2max.usd
"""
import sys
import numpy as np
import trimesh
from pxr import Usd, UsdGeom, Vt, Gf

TARGET_FACES = 50_000
BODY_MESH = "/vehicle/body/body"
LIGHT = "/vehicle/defaultLight"

src, dst = sys.argv[1], sys.argv[2]
stage = Usd.Stage.Open(src)

mesh_prim = stage.GetPrimAtPath(BODY_MESH)
assert mesh_prim and mesh_prim.GetTypeName() == "Mesh", f"{BODY_MESH} missing"
mesh = UsdGeom.Mesh(mesh_prim)
fvc = np.array(mesh.GetFaceVertexCountsAttr().Get())
assert (fvc == 3).all(), "body mesh is not pure triangles; triangulate first"
pts = np.array(mesh.GetPointsAttr().Get(), dtype=np.float64)
idx = np.array(mesh.GetFaceVertexIndicesAttr().Get()).reshape(-1, 3)
print(f"body mesh: {len(idx)} faces, {len(pts)} points")

tm = trimesh.Trimesh(vertices=pts, faces=idx, process=False)
dec = tm.simplify_quadric_decimation(face_count=TARGET_FACES)
print(f"decimated: {len(dec.faces)} faces, {len(dec.vertices)} points")

mesh.GetPointsAttr().Set(Vt.Vec3fArray.FromNumpy(dec.vertices.astype(np.float32)))
mesh.GetFaceVertexCountsAttr().Set(Vt.IntArray([3] * len(dec.faces)))
mesh.GetFaceVertexIndicesAttr().Set(Vt.IntArray.FromNumpy(dec.faces.astype(np.int32).ravel()))
# per-vertex / per-face data sized for the old topology must go
mesh.GetNormalsAttr().Clear()
pv = UsdGeom.PrimvarsAPI(mesh_prim)
for name in ("normals", "st"):
    if pv.HasPrimvar(name):
        pv.RemovePrimvar(name)
for name in ("displayColor", "displayOpacity"):   # keep only if constant (one value)
    if pv.HasPrimvar(name):
        vals = pv.GetPrimvar(name).Get()
        if vals is not None and len(vals) != 1:
            pv.RemovePrimvar(name)
lo, hi = dec.vertices.min(axis=0), dec.vertices.max(axis=0)
mesh.GetExtentAttr().Set(Vt.Vec3fArray([Gf.Vec3f(*lo), Gf.Vec3f(*hi)]))

if stage.GetPrimAtPath(LIGHT):
    stage.RemovePrim(LIGHT)
    print(f"removed {LIGHT}")

stage.GetRootLayer().Export(dst)
print(f"wrote {dst}")
EOF
```

- [ ] **Step 5: Run the cleaner**

Run:
```bash
cd ~/AirStack-starling-max2
ISAAC_PIP=fast_simplification AirStack/simulation/isaac-sim/tools/isaac_python.sh \
  AirStack/simulation/isaac-sim/tools/clean_starling_usd.py \
  isaac_sim/starlingmax2.usd AirStack/simulation/isaac-sim/assets/robots/starling2max.usd
ls -la AirStack/simulation/isaac-sim/assets/robots/starling2max.usd
```
Expected: `decimated: 50000 faces …`, `removed /vehicle/defaultLight`, `wrote …`; file size well under 10 MB.
If `pip install fast_simplification` fails for lack of network, run once with network and keep the produced file; the tool is not a runtime dependency.

- [ ] **Step 6: Verify the prim-tree diff is only the mesh and the light**

Run:
```bash
cd ~/AirStack-starling-max2
AirStack/simulation/isaac-sim/tools/isaac_python.sh AirStack/simulation/isaac-sim/tools/dump_usd.py \
  AirStack/simulation/isaac-sim/assets/robots/starling2max.usd > /tmp/starling_clean.txt
diff /tmp/starling_raw.txt /tmp/starling_clean.txt
```
Expected: exactly two differences — the `/vehicle/defaultLight` line gone, and the `body/body` line now reading `faces=50000 … collision=convexHull normals=False primvars=[…displayColor…]` (no `primvars:st`, no `primvars:normals`). Every mass / inertia / com / rotor T= / joint line identical.

- [ ] **Step 7: Commit**

```bash
cd ~/AirStack-starling-max2
git add AirStack/simulation/isaac-sim/tools/isaac_python.sh AirStack/simulation/isaac-sim/tools/dump_usd.py \
        AirStack/simulation/isaac-sim/tools/clean_starling_usd.py AirStack/simulation/isaac-sim/assets/robots/starling2max.usd
git commit -m "sim: cleaned Starling 2 Max vehicle USD (CMU sys-ID inertials, body mesh decimated to 50k faces) + USD tooling"
```

---

### Task 3: Lagged quadratic thrust curve (motor time constant)

**Files:**
- Create: `PEG/logic/thrusters/lagged_quadratic_thrust_curve.py`
- Modify: `PEG/logic/thrusters/__init__.py` (export)
- Test: `PEG/tests/unit/__init__.py` (empty), `PEG/tests/unit/test_lagged_thrust_curve.py`

**Interfaces:**
- Produces: `class LaggedQuadraticThrustCurve(QuadraticThrustCurve)`, `__init__(self, config={})` accepting every `QuadraticThrustCurve` key plus `"time_constant": float` (seconds, default `0.0` = no lag). `update(state, dt) -> (force_list, velocity_list, rolling_moment)` same return shape as the parent. Task 4 constructs it.

- [ ] **Step 1: Write the failing test**

```bash
mkdir -p ~/AirStack-starling-max2/AirStack/simulation/isaac-sim/extensions/PegasusSimulator/extensions/pegasus.simulator/pegasus/simulator/tests/unit
: > ~/AirStack-starling-max2/AirStack/simulation/isaac-sim/extensions/PegasusSimulator/extensions/pegasus.simulator/pegasus/simulator/tests/unit/__init__.py
cat > ~/AirStack-starling-max2/AirStack/simulation/isaac-sim/extensions/PegasusSimulator/extensions/pegasus.simulator/pegasus/simulator/tests/unit/test_lagged_thrust_curve.py <<'EOF'
"""Unit tests for the lagged thrust curve. Pure numpy — runs without Isaac Sim:
   AirStack/simulation/isaac-sim/tools/isaac_python.sh -m unittest discover -s \
     AirStack/simulation/isaac-sim/extensions/PegasusSimulator/extensions/pegasus.simulator/pegasus/simulator/tests/unit -v
Importing pegasus.simulator normally boots the Omniverse extension, so the package
modules are stubbed and only leaf modules are loaded from their files.
"""
import importlib.util
import os
import sys
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SIM = os.path.abspath(os.path.join(HERE, "..", ".."))          # …/pegasus/simulator
ROOT = os.path.abspath(os.path.join(SIM, "..", ".."))          # …/pegasus.simulator


def _stub(name, path):
    if name not in sys.modules:
        m = types.ModuleType(name)
        m.__path__ = [path]
        sys.modules[name] = m


for name, path in (("pegasus", os.path.join(ROOT, "pegasus")),
                   ("pegasus.simulator", SIM),
                   ("pegasus.simulator.logic", os.path.join(SIM, "logic"))):
    _stub(name, path)
sys.path.insert(0, ROOT)

from pegasus.simulator.logic.thrusters.quadratic_thrust_curve import QuadraticThrustCurve  # noqa: E402
from pegasus.simulator.logic.thrusters.lagged_quadratic_thrust_curve import LaggedQuadraticThrustCurve  # noqa: E402

KF = 3.964738e-6


class LaggedThrustCurveTest(unittest.TestCase):
    def test_zero_time_constant_matches_parent(self):
        cfg = {"rotor_constant": [KF] * 4, "max_rotor_velocity": [1450] * 4}
        a, b = QuadraticThrustCurve(cfg), LaggedQuadraticThrustCurve(dict(cfg, time_constant=0.0))
        for ref in ([600] * 4, [0, 1450, 2000, 300]):
            a.set_input_reference(ref); b.set_input_reference(ref)
            fa, va, ma = a.update(None, 0.004); fb, vb, mb = b.update(None, 0.004)
            self.assertEqual(list(va), list(vb)); self.assertEqual(list(fa), list(fb)); self.assertEqual(ma, mb)

    def test_first_tick_starts_from_reference_not_zero(self):
        c = LaggedQuadraticThrustCurve({"rotor_constant": [KF] * 4, "time_constant": 0.072})
        c.set_input_reference([587.0] * 4)
        _, v, _ = c.update(None, 0.004)
        self.assertAlmostEqual(v[0], 587.0, places=6)   # no spin-up spike from 0 on the first tick

    def test_step_reaches_63_percent_after_one_tau(self):
        tau, dt = 0.072, 0.001
        c = LaggedQuadraticThrustCurve({"rotor_constant": [KF] * 4, "max_rotor_velocity": [1450] * 4, "time_constant": tau})
        c.set_input_reference([500.0] * 4); c.update(None, dt)           # settle at 500
        c.set_input_reference([1000.0] * 4)
        v = None
        for _ in range(int(round(tau / dt))):
            _, v, _ = c.update(None, dt)
        self.assertAlmostEqual((v[0] - 500.0) / 500.0, 1 - 2.718281828 ** -1, delta=0.02)

    def test_force_is_kf_omega_squared_of_lagged_velocity(self):
        c = LaggedQuadraticThrustCurve({"rotor_constant": [KF] * 4, "time_constant": 0.072})
        c.set_input_reference([600.0] * 4); c.update(None, 0.004)
        c.set_input_reference([900.0] * 4)
        f, v, _ = c.update(None, 0.004)
        self.assertLess(v[0], 900.0)                      # lagging
        self.assertAlmostEqual(f[0], KF * v[0] ** 2, places=9)

    def test_clamps_to_max_rotor_velocity(self):
        c = LaggedQuadraticThrustCurve({"rotor_constant": [KF] * 4, "max_rotor_velocity": [1450] * 4, "time_constant": 0.072})
        c.set_input_reference([5000.0] * 4)
        for _ in range(500):
            _, v, _ = c.update(None, 0.004)
        self.assertLessEqual(v[0], 1450.0 + 1e-9)


if __name__ == "__main__":
    unittest.main()
EOF
```

- [ ] **Step 2: Run the test to verify it fails**

Run:
```bash
cd ~/AirStack-starling-max2
AirStack/simulation/isaac-sim/tools/isaac_python.sh -m unittest discover -s AirStack/simulation/isaac-sim/extensions/PegasusSimulator/extensions/pegasus.simulator/pegasus/simulator/tests/unit -v
```
Expected: `ModuleNotFoundError: No module named 'pegasus.simulator.logic.thrusters.lagged_quadratic_thrust_curve'`

- [ ] **Step 3: Implement the curve**

```bash
cat > ~/AirStack-starling-max2/AirStack/simulation/isaac-sim/extensions/PegasusSimulator/extensions/pegasus.simulator/pegasus/simulator/logic/thrusters/lagged_quadratic_thrust_curve.py <<'EOF'
"""
| File: lagged_quadratic_thrust_curve.py
| Description: Quadratic thrust curve with a first-order motor lag on the rotor speed.
|   Added for the Starling 2 Max (CMU sys-ID: tau ~72 ms). With time_constant = 0 it is
|   identical to QuadraticThrustCurve.
"""
import numpy as np
from pegasus.simulator.logic.state import State
from pegasus.simulator.logic.thrusters.quadratic_thrust_curve import QuadraticThrustCurve


class LaggedQuadraticThrustCurve(QuadraticThrustCurve):
    """QuadraticThrustCurve whose rotor speed follows the commanded speed through a
    first-order lag:  omega += dt / tau * (omega_cmd - omega).

    Extra config key:
        "time_constant": float seconds (default 0.0 = no lag)
    """

    def __init__(self, config={}):
        super().__init__(config)
        self._time_constant = float(config.get("time_constant", 0.0))
        self._lagged = None   # None until the first update: start exactly at the reference

    def update(self, state: State, dt: float):
        rolling_moment = 0.0
        for i in range(self._num_rotors):
            target = np.maximum(self.min_rotor_velocity[i],
                                np.minimum(self._input_reference[i], self.max_rotor_velocity[i]))
            if self._lagged is None:
                self._lagged = [float(np.maximum(self.min_rotor_velocity[k],
                                                 np.minimum(self._input_reference[k], self.max_rotor_velocity[k])))
                                for k in range(self._num_rotors)]
            if self._time_constant > 0.0 and dt > 0.0:
                alpha = min(1.0, dt / self._time_constant)
                self._lagged[i] += alpha * (target - self._lagged[i])
            else:
                self._lagged[i] = float(target)
            self._velocity[i] = self._lagged[i]
            self._force[i] = self._rotor_constant[i] * np.power(self._velocity[i], 2)
            rolling_moment += self._rolling_moment_coefficient[i] * np.power(self._velocity[i], 2.0) * self._rot_dir[i]
        self._rolling_moment = rolling_moment
        return self._force, self._velocity, self._rolling_moment
EOF
cat >> ~/AirStack-starling-max2/AirStack/simulation/isaac-sim/extensions/PegasusSimulator/extensions/pegasus.simulator/pegasus/simulator/logic/thrusters/__init__.py <<'EOF'

from .lagged_quadratic_thrust_curve import LaggedQuadraticThrustCurve
EOF
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: same command as Step 2.
Expected: `Ran 5 tests … OK`

- [ ] **Step 5: Commit**

```bash
cd ~/AirStack-starling-max2
git add AirStack/simulation/isaac-sim/extensions/PegasusSimulator/extensions/pegasus.simulator/pegasus/simulator/logic/thrusters/ \
        AirStack/simulation/isaac-sim/extensions/PegasusSimulator/extensions/pegasus.simulator/pegasus/simulator/tests/unit/
git commit -m "pegasus: LaggedQuadraticThrustCurve — first-order motor lag (time_constant), unit-tested"
```

---

### Task 4: Starling2MaxConfig + config selection by USD file name

**Files:**
- Create: `PEG/logic/vehicles/multirotors/registry.py`
- Create: `PEG/logic/vehicles/multirotors/starling2max.py`
- Modify: `PEG/ogn/python/nodes/OgnPegasusMultirotorNodeBase.py:203-235` (`create_multirotor`)
- Test: `PEG/tests/unit/test_vehicle_registry.py`

**Interfaces:**
- Consumes: `LaggedQuadraticThrustCurve` (Task 3).
- Produces: `vehicle_key_from_usd(usd_file: str) -> str` (pure; `"starling2max"` or `"iris"`), `select_vehicle_config(usd_file: str) -> type` (lazy import; returns `Starling2MaxConfig` or `MultirotorConfig`). The OGN node calls `select_vehicle_config(db.inputs.usdFile)()`.

- [ ] **Step 1: Write the failing test for the pure selector**

```bash
cat > ~/AirStack-starling-max2/AirStack/simulation/isaac-sim/extensions/PegasusSimulator/extensions/pegasus.simulator/pegasus/simulator/tests/unit/test_vehicle_registry.py <<'EOF'
import importlib.util
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REG = os.path.join(HERE, "..", "..", "logic", "vehicles", "multirotors", "registry.py")
spec = importlib.util.spec_from_file_location("registry", REG)
registry = importlib.util.module_from_spec(spec); spec.loader.exec_module(registry)


class VehicleRegistryTest(unittest.TestCase):
    def test_iris_paths_select_iris(self):
        for p in ("~/.local/share/ov/.../Robots/Iris/iris.usd", "/x/iris.usd", "", None):
            self.assertEqual(registry.vehicle_key_from_usd(p), "iris")

    def test_starling_stem_any_case_and_suffix(self):
        for p in ("/isaac-sim/AirStack/simulation/isaac-sim/assets/robots/starling2max.usd",
                  "/tmp/Starling2Max.usdc", "C:/x/STARLING2MAX.usda", "/tmp/starling2max_v2.usd",
                  "/tmp/starlingmax2.usd"):
            self.assertEqual(registry.vehicle_key_from_usd(p), "starling2max", p)

    def test_unknown_stem_falls_back_to_iris(self):
        self.assertEqual(registry.vehicle_key_from_usd("/tmp/x500.usd"), "iris")


if __name__ == "__main__":
    unittest.main()
EOF
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd ~/AirStack-starling-max2 && AirStack/simulation/isaac-sim/tools/isaac_python.sh -m unittest discover -s AirStack/simulation/isaac-sim/extensions/PegasusSimulator/extensions/pegasus.simulator/pegasus/simulator/tests/unit -v`
Expected: `FileNotFoundError … registry.py`

- [ ] **Step 3: Write the registry and the Starling config**

```bash
PEG=~/AirStack-starling-max2/AirStack/simulation/isaac-sim/extensions/PegasusSimulator/extensions/pegasus.simulator/pegasus/simulator
cat > $PEG/logic/vehicles/multirotors/registry.py <<'EOF'
"""Pick a MultirotorConfig subclass from the vehicle USD file name.

The OGN PX4 node has no input for dynamics, so the USD file is the only handle the
launch script controls. `vehicle_key_from_usd` is pure (unit-tested without Omniverse);
`select_vehicle_config` imports the config class lazily because those modules pull in
Isaac/Omniverse.
"""
import os

# stem substring -> key. Order matters: first match wins. Add new airframes here.
_KEYS = (
    ("starling", "starling2max"),
)
DEFAULT_KEY = "iris"


def vehicle_key_from_usd(usd_file) -> str:
    if not usd_file:
        return DEFAULT_KEY
    stem = os.path.splitext(os.path.basename(str(usd_file)))[0].lower()
    for needle, key in _KEYS:
        if needle in stem:
            return key
    return DEFAULT_KEY


def select_vehicle_config(usd_file):
    """Return the config CLASS (not instance) for this USD. Falls back to MultirotorConfig."""
    key = vehicle_key_from_usd(usd_file)
    if key == "starling2max":
        from pegasus.simulator.logic.vehicles.multirotors.starling2max import Starling2MaxConfig
        return Starling2MaxConfig
    from pegasus.simulator.logic.vehicles.multirotor import MultirotorConfig
    return MultirotorConfig
EOF
cat > $PEG/logic/vehicles/multirotors/starling2max.py <<'EOF'
"""ModalAI Starling 2 Max — dynamics from CMU AirLab's system-identification campaign
("Starling 2 Max Sys ID Results", repo file isaac_sim/Starling 2 Max Sys ID Results - Slite.pdf).

Mass 0.557 kg, inertia and centre of mass live in the USD (assets/robots/starling2max.usd).
Here: propeller constants, motor lag, rotor-speed ceiling.
"""
from pegasus.simulator.logic.vehicles.multirotor import MultirotorConfig
from pegasus.simulator.logic.dynamics import LinearDrag
from pegasus.simulator.logic.thrusters import LaggedQuadraticThrustCurve

ROTOR_CONSTANT = 3.964738e-6          # N / (rad/s)^2        (CMU sys-ID)
ROLLING_MOMENT_COEFFICIENT = 5.38697e-8   # N·m / (rad/s)^2  (CMU sys-ID)
MOTOR_TIME_CONSTANT_S = 0.072         # s                     (CMU sys-ID, 55 up / 85 down)
MAX_ROTOR_VELOCITY = 1450.0           # rad/s — chosen so hover (587 rad/s) sits near 36 % throttle
ROT_DIR = [-1, -1, 1, 1]              # PX4 quad-X order FR, BL, FL, BR — same as Iris


class Starling2MaxConfig(MultirotorConfig):
    def __init__(self):
        super().__init__()
        self.thrust_curve = LaggedQuadraticThrustCurve({
            "num_rotors": 4,
            "rotor_constant": [ROTOR_CONSTANT] * 4,
            "rolling_moment_coefficient": [ROLLING_MOMENT_COEFFICIENT] * 4,
            "rot_dir": ROT_DIR,
            "min_rotor_velocity": [0.0] * 4,
            "max_rotor_velocity": [MAX_ROTOR_VELOCITY] * 4,
            "time_constant": MOTOR_TIME_CONSTANT_S,
        })
        # Drag was not identified by CMU; keep the Pegasus default.
        self.drag = LinearDrag([0.50, 0.30, 0.0])
EOF
```

- [ ] **Step 4: Run the registry test to verify it passes**

Run: same command as Step 2.
Expected: all tests OK (3 registry + 5 thrust-curve).

- [ ] **Step 5: Wire the selector into the OGN node**

In `$PEG/ogn/python/nodes/OgnPegasusMultirotorNodeBase.py`, replace the first three lines of `create_multirotor`'s body:

```python
        # Create multirotor configuration
        multirotor_config = MultirotorConfig()
        multirotor_config.backends = [backend]

        # Get USD file from input parameter
        selected_usd_file = db.inputs.usdFile
```
with
```python
        # Get USD file from input parameter — it also selects the dynamics config
        selected_usd_file = db.inputs.usdFile
        from pegasus.simulator.logic.vehicles.multirotors.registry import select_vehicle_config
        config_class = select_vehicle_config(selected_usd_file)
        print(f"Vehicle config for {os.path.basename(str(selected_usd_file))}: {config_class.__name__}")
        multirotor_config = config_class()
        multirotor_config.backends = [backend]
```
(`os` is already imported at the top of the file.)

- [ ] **Step 6: Syntax-check the edited node and the new modules**

Run:
```bash
cd ~/AirStack-starling-max2
python3 -m py_compile AirStack/simulation/isaac-sim/extensions/PegasusSimulator/extensions/pegasus.simulator/pegasus/simulator/ogn/python/nodes/OgnPegasusMultirotorNodeBase.py \
  AirStack/simulation/isaac-sim/extensions/PegasusSimulator/extensions/pegasus.simulator/pegasus/simulator/logic/vehicles/multirotors/{registry,starling2max}.py && echo compiled
```
Expected: `compiled`

- [ ] **Step 7: Commit**

```bash
cd ~/AirStack-starling-max2
git add AirStack/simulation/isaac-sim/extensions/PegasusSimulator/extensions/pegasus.simulator/pegasus/simulator/logic/vehicles/multirotors/ \
        AirStack/simulation/isaac-sim/extensions/PegasusSimulator/extensions/pegasus.simulator/pegasus/simulator/ogn/python/nodes/OgnPegasusMultirotorNodeBase.py \
        AirStack/simulation/isaac-sim/extensions/PegasusSimulator/extensions/pegasus.simulator/pegasus/simulator/tests/unit/test_vehicle_registry.py
git commit -m "pegasus: Starling2MaxConfig (CMU sys-ID thrust constants + 72 ms motor lag), selected by USD file name"
```

---

### Task 5: PX4 SITL airframe, bind-mounted into the Isaac container

**Files:**
- Create: `AirStack/simulation/isaac-sim/px4/airframes/10090_pegasus_starling2max`
- Modify: `AirStack/simulation/isaac-sim/docker/docker-compose.yaml:70` (add one volume line under `# pegasus integration`)

**Interfaces:**
- Produces: PX4 model name `pegasus_starling2max` (what `PX4_VEHICLE_MODEL` must be set to in Task 6).

- [ ] **Step 1: Write the airframe file**

```bash
mkdir -p ~/AirStack-starling-max2/AirStack/simulation/isaac-sim/px4/airframes
cat > ~/AirStack-starling-max2/AirStack/simulation/isaac-sim/px4/airframes/10090_pegasus_starling2max <<'EOF'
#!/bin/sh
#
# @name ModalAI Starling 2 Max (Pegasus / Isaac Sim SITL)
#
# @type Quadrotor x
#
# Rotor geometry from CMU's sys-ID USD (body FLU: r0 +0.095,-0.13 | r1 -0.095,+0.13 |
# r2 +0.095,+0.13 | r3 -0.095,-0.13), written here in PX4 FRD (y negated).
# KM = k_m / k_f = 5.38697e-8 / 3.964738e-6 = 0.0136. Hover throttle 0.36 follows from the
# Pegasus rotor-speed ceiling (1450 rad/s) and k_f. Rate/position gains: rc.mc_defaults.
# Bind-mounted into the SITL airframes dir by simulation/isaac-sim/docker/docker-compose.yaml.
#

. ${R}etc/init.d/rc.mc_defaults

param set-default CA_AIRFRAME 0

param set-default CA_ROTOR_COUNT 4
param set-default CA_ROTOR0_PX 0.095
param set-default CA_ROTOR0_PY 0.13
param set-default CA_ROTOR0_KM 0.0136
param set-default CA_ROTOR1_PX -0.095
param set-default CA_ROTOR1_PY -0.13
param set-default CA_ROTOR1_KM 0.0136
param set-default CA_ROTOR2_PX 0.095
param set-default CA_ROTOR2_PY -0.13
param set-default CA_ROTOR2_KM -0.0136
param set-default CA_ROTOR3_PX -0.095
param set-default CA_ROTOR3_PY 0.13
param set-default CA_ROTOR3_KM -0.0136

param set-default MPC_THR_HOVER 0.36

param set-default PWM_MAIN_FUNC1 101
param set-default PWM_MAIN_FUNC2 102
param set-default PWM_MAIN_FUNC3 103
param set-default PWM_MAIN_FUNC4 104
EOF
chmod +x ~/AirStack-starling-max2/AirStack/simulation/isaac-sim/px4/airframes/10090_pegasus_starling2max
```

- [ ] **Step 2: Add the compose mount**

In `AirStack/simulation/isaac-sim/docker/docker-compose.yaml`, directly after the line
```
      - ../extensions/PegasusSimulator/extensions/pegasus.simulator:/isaac-sim/.local/share/ov/data/documents/Kit/shared/exts/pegasus.simulator/:rw
```
insert
```
      # our PX4 SITL airframes (read by rcS at SITL start; no image rebuild needed)
      - ../px4/airframes/10090_pegasus_starling2max:/isaac-sim/PX4-Autopilot/build/px4_sitl_default/etc/init.d-posix/airframes/10090_pegasus_starling2max:ro
```

- [ ] **Step 3: Validate the compose file and the mount**

Run:
```bash
cd ~/AirStack-starling-max2/AirStack
docker compose -f simulation/isaac-sim/docker/docker-compose.yaml config 2>/dev/null | grep -n '10090_pegasus_starling2max' | head -2
./airstack.sh up isaac-sim 2>&1 | tail -2
docker exec isaac-sim bash -c 'f=/isaac-sim/PX4-Autopilot/build/px4_sitl_default/etc/init.d-posix/airframes; ls -l $f/10090_pegasus_starling2max; ls "$f" | sed -n "s/^\([0-9][0-9]*\)_pegasus_starling2max$/\1/p"'
```
Expected: the config shows the mount (source and target), the file is listed inside the container with execute bits, and the `sed` (the same expression `rcS:56` uses) prints `10090`.
(`./airstack.sh up isaac-sim` starts Isaac in the background; leave it for Task 7 or `./airstack.sh down` now.)

- [ ] **Step 4: Commit**

```bash
cd ~/AirStack-starling-max2
git add AirStack/simulation/isaac-sim/px4/airframes/10090_pegasus_starling2max AirStack/simulation/isaac-sim/docker/docker-compose.yaml
git commit -m "sim: PX4 SITL airframe 10090_pegasus_starling2max, bind-mounted into the Isaac container"
```

---

### Task 6: Launch-script env overrides, ZED offset, lidar import fix

**Files:**
- Modify: `AirStack/simulation/isaac-sim/launch_scripts/svg_multi_drone_single_domain.py:62` (DRONE_USD), `:138-146` (spawn call), `:151-161` (ZED), `:163-175` (lidar)
- Test: `AirStack/simulation/isaac-sim/tools/test_launch_env.py`

**Interfaces:**
- Consumes: asset path from Task 2, model name `pegasus_starling2max` from Task 5.
- Produces: env vars `DRONE_USD` (container path of the vehicle USD; empty/unset = Iris) and `PX4_VEHICLE_MODEL` (PX4 SITL model; empty/unset = `gazebo-classic_iris`).

- [ ] **Step 1: Write the failing test for the env handling**

The launch script imports Isaac at module level, so the env logic is factored into a tiny importable helper tested on the host:

```bash
cat > ~/AirStack-starling-max2/AirStack/simulation/isaac-sim/tools/test_launch_env.py <<'EOF'
"""Host test (plain python3): env-var handling used by svg_multi_drone_single_domain.py.
   python3 AirStack/simulation/isaac-sim/tools/test_launch_env.py
"""
import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "launch_scripts"))
from launch_env import resolve_vehicle   # noqa: E402

IRIS = "~/.local/share/ov/data/documents/Kit/shared/exts/pegasus.simulator/pegasus/simulator/assets/Robots/Iris/iris.usd"
STARLING = "/isaac-sim/AirStack/simulation/isaac-sim/assets/robots/starling2max.usd"


class LaunchEnvTest(unittest.TestCase):
    def test_unset_is_iris(self):
        usd, model, zed = resolve_vehicle({})
        self.assertEqual((usd, model), (IRIS, "gazebo-classic_iris")); self.assertEqual(zed, [0.2, 0.0, -0.05])

    def test_empty_string_is_unset(self):
        usd, model, _ = resolve_vehicle({"DRONE_USD": "", "PX4_VEHICLE_MODEL": "  "})
        self.assertEqual((usd, model), (IRIS, "gazebo-classic_iris"))

    def test_starling_sets_model_and_zed_offset(self):
        usd, model, zed = resolve_vehicle({"DRONE_USD": STARLING, "PX4_VEHICLE_MODEL": "pegasus_starling2max"})
        self.assertEqual((usd, model), (STARLING, "pegasus_starling2max")); self.assertEqual(zed, [0.12, 0.0, -0.03])

    def test_starling_usd_without_model_warns_but_keeps_iris_model(self):
        usd, model, _ = resolve_vehicle({"DRONE_USD": STARLING})
        self.assertEqual(model, "gazebo-classic_iris")


if __name__ == "__main__":
    unittest.main()
EOF
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python3 ~/AirStack-starling-max2/AirStack/simulation/isaac-sim/tools/test_launch_env.py`
Expected: `ModuleNotFoundError: No module named 'launch_env'`

- [ ] **Step 3: Write the helper**

```bash
cat > ~/AirStack-starling-max2/AirStack/simulation/isaac-sim/launch_scripts/launch_env.py <<'EOF'
"""Vehicle selection for the SVG launch script from environment variables (no Isaac imports).

DRONE_USD          vehicle USD path as seen INSIDE the Isaac container. Unset/empty = Pegasus Iris.
PX4_VEHICLE_MODEL  PX4 SITL model name (rcS matches airframes/NNNNN_<name>). Unset/empty = gazebo-classic_iris.
"""
import os

IRIS_USD = "~/.local/share/ov/data/documents/Kit/shared/exts/pegasus.simulator/pegasus/simulator/assets/Robots/Iris/iris.usd"
IRIS_MODEL = "gazebo-classic_iris"
ZED_OFFSET_IRIS = [0.2, 0.0, -0.05]
ZED_OFFSET_STARLING = [0.12, 0.0, -0.03]   # half-size frame


def resolve_vehicle(env=None):
    """Return (drone_usd, px4_vehicle_model, zed_camera_offset)."""
    env = os.environ if env is None else env
    usd = (env.get("DRONE_USD") or "").strip() or IRIS_USD
    model = (env.get("PX4_VEHICLE_MODEL") or "").strip() or IRIS_MODEL
    is_starling = "starling" in os.path.basename(usd).lower()
    if is_starling and model == IRIS_MODEL:
        print("[svg_multi_drone] WARNING: DRONE_USD is a Starling but PX4_VEHICLE_MODEL is unset — "
              "PX4 will run the Iris airframe (set PX4_VEHICLE_MODEL=pegasus_starling2max)")
    return usd, model, (ZED_OFFSET_STARLING if is_starling else ZED_OFFSET_IRIS)
EOF
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 ~/AirStack-starling-max2/AirStack/simulation/isaac-sim/tools/test_launch_env.py`
Expected: `Ran 4 tests … OK`

- [ ] **Step 5: Wire the helper into the launch script**

In `svg_multi_drone_single_domain.py`:

(a) replace line 62
```python
DRONE_USD = "~/.local/share/ov/data/documents/Kit/shared/exts/pegasus.simulator/pegasus/simulator/assets/Robots/Iris/iris.usd"
```
with
```python
from launch_env import resolve_vehicle   # sibling module; sys.path already has this dir via __file__ handling below
DRONE_USD, PX4_VEHICLE_MODEL, ZED_CAMERA_OFFSET = resolve_vehicle()
print(f"[svg_multi_drone] vehicle USD: {DRONE_USD}  PX4 model: {PX4_VEHICLE_MODEL}")
```
and make sure the script's own directory is importable: the existing line 55 inserts `../utils`; add before it
```python
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
```

(b) in `spawn_drone`, add to the `spawn_px4_multirotor_node(...)` call, after `usd_file=DRONE_USD,`:
```python
        px4_vehicle_model=PX4_VEHICLE_MODEL,
```

(c) in the ZED block replace `camera_offset=[0.2, 0.0, -0.05],` with `camera_offset=ZED_CAMERA_OFFSET,`

(d) replace the lidar block
```python
        from pegasus.simulator.ogn.api.spawn_ouster_lidar import (
            add_ouster_lidar_subgraph)
        add_ouster_lidar_subgraph(
            parent_graph_handle=graph_handle,
            drone_prim=drone_prim,
            robot_name=robot_name,
            lidar_name="OS1_REV6_128_10hz___512_resolution",
            lidar_topic_name="point_cloud_raw",
            lidar_offset=[0.0, 0.0, 0.025],
            lidar_rotation_offset=[0.0, 0.0, 0.0],
            lidar_min_range=0.75,
        )
```
with
```python
        from pegasus.simulator.ogn.api.spawn_rtx_lidar import add_rtx_lidar_subgraph
        add_rtx_lidar_subgraph(
            parent_graph_handle=graph_handle,
            drone_prim=drone_prim,
            robot_name=robot_name,
            lidar_name="OS1_REV6_128_10hz___512_resolution",
            lidar_topic_name="point_cloud_raw",
            lidar_offset=[0.0, 0.0, 0.025],
            lidar_rotation_offset=[0.0, 0.0, 0.0],
            min_range=0.75,
        )
```

- [ ] **Step 6: Syntax-check and confirm the Iris default is unchanged**

Run:
```bash
cd ~/AirStack-starling-max2/AirStack/simulation/isaac-sim
python3 -m py_compile launch_scripts/svg_multi_drone_single_domain.py launch_scripts/launch_env.py && echo compiled
python3 -c "import sys; sys.path.insert(0,'launch_scripts'); from launch_env import resolve_vehicle; print(resolve_vehicle({}))"
```
Expected: `compiled` and `('~/.local/share/ov/data/documents/Kit/shared/exts/pegasus.simulator/pegasus/simulator/assets/Robots/Iris/iris.usd', 'gazebo-classic_iris', [0.2, 0.0, -0.05])`

- [ ] **Step 7: Commit**

```bash
cd ~/AirStack-starling-max2
git add AirStack/simulation/isaac-sim/launch_scripts/svg_multi_drone_single_domain.py AirStack/simulation/isaac-sim/launch_scripts/launch_env.py AirStack/simulation/isaac-sim/tools/test_launch_env.py
git commit -m "sim launch: DRONE_USD / PX4_VEHICLE_MODEL env overrides (Iris default unchanged), Starling ZED offset, fix lidar import"
```

---

### Task 7: Integration — Iris regression, Starling hover + step, Starling CBF run

**Files:**
- Modify: `docs/MILESTONES.md` §3c (ledger rows written as results come in)

**Interfaces:**
- Consumes: everything above. Needs the GPU laptop, the robot container, and about 90 minutes.

All sim sessions follow RUNBOOK §A. Shorthand used below: **T1** = Isaac spawn terminal (`./airstack.sh connect isaac-sim --command=bash`), **pane N** = tmux `bringup` panes in the robot container (`./airstack.sh connect robot`).

- [ ] **Step 1: Iris regression (env unset)**

T1:
```bash
cd ~/AirStack-starling-max2/AirStack && ./airstack.sh up && ./airstack.sh connect isaac-sim --command=bash
NUM_ROBOTS=3 SVG_DOMAIN_ID=1 PLAY_SIM_ON_START=true ISAAC_SIM_HEADLESS=true PYTHONPATH="$ISAAC_SIM_PYTHONPATH" \
/isaac-sim/python.sh /isaac-sim/AirStack/simulation/isaac-sim/launch_scripts/svg_multi_drone_single_domain.py --ext-folder ~/.local/share/ov/data/documents/Kit/shared/exts
```
Expected in the log: `vehicle USD: ~/.local/…/iris.usd  PX4 model: gazebo-classic_iris`, three `Vehicle config for iris.usd: MultirotorConfig`, three `Ready for takeoff!`. Pane 1: `./src/svg_ground_control/scripts/launch_sim_interfaces.sh 3`; pane 2: `ros2 launch svg_ground_control ground_control.launch.py`; pane 3: `takeoff` → `land` services. Pass: identical to pre-change behaviour. Ctrl-C everything.

- [ ] **Step 2: Starling spawn — airframe and config selected**

T1 (same command with the two env vars in front):
```bash
DRONE_USD=/isaac-sim/AirStack/simulation/isaac-sim/assets/robots/starling2max.usd PX4_VEHICLE_MODEL=pegasus_starling2max \
NUM_ROBOTS=3 SVG_DOMAIN_ID=1 PLAY_SIM_ON_START=true ISAAC_SIM_HEADLESS=true PYTHONPATH="$ISAAC_SIM_PYTHONPATH" \
/isaac-sim/python.sh /isaac-sim/AirStack/simulation/isaac-sim/launch_scripts/svg_multi_drone_single_domain.py --ext-folder ~/.local/share/ov/data/documents/Kit/shared/exts
```
Expected: `Vehicle config for starling2max.usd: Starling2MaxConfig` ×3; PX4 console lines `env SYS_AUTOSTART` absent and no `Unknown model`; `INFO  [init] … 10090` or the airframe name in the PX4 startup; three `Ready for takeoff!`; no PhysX cooking warnings for `/vehicle/body/body`.
If `Unknown model pegasus_starling2max`: the mount from Task 5 is missing — `./airstack.sh down && up`.

- [ ] **Step 3: Hover and step response (goal scenario)**

Pane 1: `./src/svg_ground_control/scripts/launch_sim_interfaces.sh 3`. Pane 2:
```bash
ros2 launch svg_ground_control ground_control.launch.py \
  config:=$(ros2 pkg prefix svg_ground_control)/share/svg_ground_control/config/cbf_sim.yaml scenario:=goal use_mocap:=false use_led:=false
```
Pane 3, hover throttle and steps:
```bash
ros2 service call /swarm_commander/takeoff std_srvs/srv/Trigger
ros2 service call /swarm_commander/start   std_srvs/srv/Trigger
# hover throttle (PX4 attitude-target thrust, 0..1) — sample 10 messages
timeout 5 ros2 topic echo /drone_1/interface/mavros/setpoint_raw/target_attitude --field thrust | head -10
# 1 m step in x, then 1 m step in z, watching position
ros2 topic pub --once /svg/drone_1/goal_command geometry_msgs/msg/PoseStamped "{header: {frame_id: map}, pose: {position: {x: -1.0, y: 0.0, z: 1.2}}}"
timeout 6 ros2 topic echo /drone_1/odometry_conversion/odometry --field pose.pose.position > /tmp/step_x.txt
ros2 topic pub --once /svg/drone_1/goal_command geometry_msgs/msg/PoseStamped "{header: {frame_id: map}, pose: {position: {x: -1.0, y: 0.0, z: 2.2}}}"
timeout 6 ros2 topic echo /drone_1/odometry_conversion/odometry --field pose.pose.position > /tmp/step_z.txt
ros2 service call /swarm_commander/land std_srvs/srv/Trigger
```
Pass: hover thrust samples within **0.30–0.45**; in `/tmp/step_x.txt` x reaches −1.0 ± 0.1 within 2 s and the max overshoot past −1.0 is < 0.15 m with no growing oscillation; same for z in `/tmp/step_z.txt`. (drone_1 spawns at x = −2 with offset −2, so its world frame starts at x = 0; adjust the goals if the config's offsets differ.)
Fail on ringing: in the airframe file add `param set-default MC_ROLLRATE_K 0.5`, `MC_PITCHRATE_K 0.5`, `MC_YAWRATE_K 0.5`, restart Isaac, repeat. Record whichever gains passed.

- [ ] **Step 4: CBF crossing on the Starling (MILESTONES M1 row)**

Pane 2: Ctrl-C, relaunch with `scenario:=antipodal` (the config default). Pane 3: `takeoff`, `start`; watch `/svg/commander_status` → `cbf.active` lists drones while they cross; minimum pairwise distance ≥ 1.1 m (2 × 0.55). Pass: the crossing completes, no `emergency`. `land`.

- [ ] **Step 5: Record results**

Append to `docs/MILESTONES.md` §3c "Tests passed" (numbering continues from the last row):

```
| N   | Sim: Starling 2 Max model spawns (CMU sys-ID config + 10090 airframe) | `DRONE_USD=… PX4_VEHICLE_MODEL=pegasus_starling2max`, 3 drones headless | `Starling2MaxConfig` selected, PX4 boots on 10090, 3× Ready for takeoff | 2026-MM-DD |
| N+1 | Sim: Starling hover throttle + 1 m steps | `cbf_sim.yaml scenario:=goal`, MAVROS target_attitude thrust, odometry trace | hover thrust <value>; x step overshoot <m>, z <m>; gains <default / K=0.5> | 2026-MM-DD |
| N+2 | **M1 CBF crossing on the Starling model** | `cbf_sim.yaml` antipodal | min pairwise distance <m>, no emergency | 2026-MM-DD |
```
Fill in the measured values. Commit: `git commit -am "milestones: Starling sim model validated in sim (ledger rows N–N+2)"`.

---

### Task 8: Docs and mirror sync

**Files:**
- Modify: `docs/RUNBOOK.md` §A T1, `docs/CONFIG.md` (new row in Protocol constants + Files & identities), `docs/MILESTONES.md` §3b, `docs/SCENARIOS.md` §11, `AirStack/README.md`

- [ ] **Step 1: RUNBOOK §A T1** — after the Isaac spawn block add:

```markdown
**Starling 2 Max model** (default is the Iris): put these two in front of the same command —
```bash
DRONE_USD=/isaac-sim/AirStack/simulation/isaac-sim/assets/robots/starling2max.usd PX4_VEHICLE_MODEL=pegasus_starling2max \
```
CMU's sys-ID dynamics (mass 0.557 kg, k_f 3.96e-6, 72 ms motor lag) and our bind-mounted PX4
airframe `10090_pegasus_starling2max`. Both vars unset = Iris, exactly as before. Values and
sources: [CONFIG.md](CONFIG.md) "Sim airframe".
```

- [ ] **Step 2: CONFIG rows** — in §Protocol constants add:

```markdown
| **Sim airframe — Starling 2 Max** (2026-10-19) | USD `AirStack/simulation/isaac-sim/assets/robots/starling2max.usd` (CMU sys-ID inertials: 0.557 kg, I = 0.00294/0.00186/0.00465) · Pegasus `Starling2MaxConfig`: k_f 3.964738e-6, k_m 5.38697e-8, τ 0.072 s, ω_max 1450 rad/s · PX4 airframe `10090_pegasus_starling2max`: rotors ±0.095/±0.13, KM 0.0136, `MPC_THR_HOVER` 0.36 | Source: `isaac_sim/Starling 2 Max Sys ID Results - Slite.pdf` (CMU AirLab). ⚠️ Rotor geometry follows CMU's CAD, not the real drone's `CA_ROTOR*` params (±0.085/±0.0625) — user decision 2026-10-19. Select with `DRONE_USD` + `PX4_VEHICLE_MODEL` ([RUNBOOK.md](RUNBOOK.md) §A) |
```

- [ ] **Step 3: MILESTONES §3b** — add rows:

```markdown
| Starling 2 Max sim model | `simulation/isaac-sim/assets/robots/starling2max.usd`; `PEG/logic/vehicles/multirotors/starling2max.py` + `registry.py`; `PEG/logic/thrusters/lagged_quadratic_thrust_curve.py`; `simulation/isaac-sim/px4/airframes/10090_pegasus_starling2max` (compose-mounted); `launch_scripts/launch_env.py` (`DRONE_USD`, `PX4_VEHICLE_MODEL`) |
```
and in M1's sub-test table add the row `| Starling model | env vars per RUNBOOK §A, then the rows above | hover 0.30–0.45, steps settle | CONFIG "Sim airframe" |`.

- [ ] **Step 4: SCENARIOS §11** — one line in the appendix table: `| Sim airframe | see CONFIG "Sim airframe — Starling 2 Max" | CMU sys-ID numbers, how to select the model |`.

- [ ] **Step 5: `AirStack/README.md`** — under "Differences from a normal AirStack clone" add:

```markdown
- **Our additions on top of CMU's branch (2026-10-19, Starling sim model):**
  `simulation/isaac-sim/assets/robots/starling2max.usd`, `simulation/isaac-sim/px4/airframes/`,
  `simulation/isaac-sim/tools/`, `launch_scripts/launch_env.py`, Pegasus
  `logic/thrusters/lagged_quadratic_thrust_curve.py`, `logic/vehicles/multirotors/{registry,starling2max}.py`,
  the config selector in `OgnPegasusMultirotorNodeBase.create_multirotor`, one compose volume line,
  and the `DRONE_USD` / `PX4_VEHICLE_MODEL` env handling in `svg_multi_drone_single_domain.py`.
  Not upstream; re-apply on a fresh CMU clone.
```

- [ ] **Step 6: Commit and sync the mirror**

```bash
cd ~/AirStack-starling-max2
git add docs/ AirStack/README.md
git commit -m "docs: Starling 2 Max sim model — RUNBOOK §A env vars, CONFIG sim-airframe row, MILESTONES audit + M1 rows"
cd ~/Documents/GitHub/AirStack-starling-max2 && git pull ~/AirStack-starling-max2 main && git log --oneline -1
```
Expected: both clones at the same commit; the user pushes from GitHub Desktop.
