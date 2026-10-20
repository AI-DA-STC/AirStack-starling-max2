"""Make the committed Starling 2 Max sim asset from CMU's starlingmax2.usd (98 MB).

What it does (2026-10-20 rewrite — the first version quadric-decimated the body to 50 k
faces, which DELETED most of the drone: the body mesh is 48,981 separate parts merged
into one 1.2 M-face mesh, and decimation drops whole parts to meet the budget — only 21 %
of the surface and neither body plate survived):
  * /vehicle/body/body: parts (connected components) with a largest extent below CULL_MM
    are culled (sub-millimetre screw threads, pins — invisible at sim scale); every other
    part is kept UNTOUCHED, no decimation. 2 mm keeps 99.9 % of the surface, 564 k faces.
  * stale per-vertex data dropped: normals, primvars:normals, primvars:st (60 MB of the
    original; Hydra recomputes normals), extent recomputed. convexHull collider and the
    material bindings are untouched.
  * explicit masses: ROTOR_MASS_KG per rotor, body = total - 4 rotors (see below).
  * /vehicle/defaultLight removed.

Usage (host):
  AirStack/simulation/isaac-sim/tools/isaac_python.sh \
      AirStack/simulation/isaac-sim/tools/clean_starling_usd.py \
      /repo/isaac_sim/starlingmax2.usd \
      /repo/AirStack/simulation/isaac-sim/assets/robots/starling2max.usd
"""
import sys
import numpy as np
import trimesh
from pxr import Usd, UsdGeom, UsdPhysics, Vt, Gf

CULL_MM = 2.0                  # drop parts whose largest extent is below this (mesh units are mm)
BODY_MESH = "/vehicle/body/body"
BODY = "/vehicle/body"
ROTORS = [f"/vehicle/rotor{i}" for i in range(4)]
LIGHT = "/vehicle/defaultLight"
ROTOR_MASS_KG = 0.020          # motor + prop assembly (~20 g on a Starling 2 Max); CMU's 0.557 kg is the whole drone.
                               # 5 g made the PhysX articulation unstable (body:rotor 107:1 -> attitude tumbling at ~1.3 Hz);
                               # 20 g keeps the ratio near the Iris (1.5 kg : 32 g).

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
parts = tm.split(only_watertight=False)
kept = [c for c in parts if c.extents.max() >= CULL_MM]
dec = trimesh.util.concatenate(kept)
print(f"parts: {len(parts)} -> kept {len(kept)} (largest extent >= {CULL_MM} mm): "
      f"{len(dec.faces)} faces, {len(dec.vertices)} points, surface kept {dec.area / tm.area:.3f}")
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

body_mass = UsdPhysics.MassAPI(stage.GetPrimAtPath(BODY))
total = body_mass.GetMassAttr().Get()
for r in ROTORS:
    rp = stage.GetPrimAtPath(r)
    assert rp and rp.HasAPI(UsdPhysics.RigidBodyAPI), f"{r} missing"
    UsdPhysics.MassAPI.Apply(rp).CreateMassAttr().Set(ROTOR_MASS_KG)
body_mass.GetMassAttr().Set(total - ROTOR_MASS_KG * len(ROTORS))
print(f"masses: body {total - ROTOR_MASS_KG*len(ROTORS):.3f} kg + 4 x {ROTOR_MASS_KG} kg rotors = {total:.3f} kg")

if stage.GetPrimAtPath(LIGHT):
    stage.RemovePrim(LIGHT)
    print(f"removed {LIGHT}")

stage.GetRootLayer().Export(dst)
print(f"wrote {dst}")
