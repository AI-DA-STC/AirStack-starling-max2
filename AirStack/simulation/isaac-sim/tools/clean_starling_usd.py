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
