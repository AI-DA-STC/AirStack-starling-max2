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
