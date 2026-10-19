"""Estimate the implicit mass PhysX assigns to rotor rigid bodies that carry no MassAPI
(collider convex-hull volume x default density 1000 kg/m^3). Usage: isaac_python.sh ... <usd> [<usd>]"""
import sys
import numpy as np, trimesh
from pxr import Usd, UsdGeom, UsdPhysics, Gf
for p in sys.argv[1:]:
    st = Usd.Stage.Open(p); print("####", p); total = 0.0
    for prim in st.Traverse():
        if prim.GetTypeName() == "Mesh" and prim.HasAPI(UsdPhysics.CollisionAPI) and "rotor" in str(prim.GetPath()):
            m = UsdGeom.Mesh(prim); pts = np.array(m.GetPointsAttr().Get()); fvc = np.array(m.GetFaceVertexCountsAttr().Get())
            idx = np.array(m.GetFaceVertexIndicesAttr().Get())
            xf = UsdGeom.Xformable(prim).GetLocalTransformation()
            pts_w = np.array([xf.Transform(Gf.Vec3d(float(q[0]), float(q[1]), float(q[2]))) for q in pts])
            if (fvc == 3).all():
                tm = trimesh.Trimesh(pts_w, idx.reshape(-1, 3), process=False)
            else:
                tm = trimesh.PointCloud(pts_w).convex_hull
            hull = tm.convex_hull; vol = hull.volume; mass = vol * 1000.0; total += mass
            bb = hull.bounds; print(f"  {prim.GetPath()}: hull volume {vol*1e6:.1f} cm^3 -> implicit mass {mass*1000:.1f} g  bbox {np.round(bb[1]-bb[0],3)} m")
    print(f"  total implicit rotor mass: {total*1000:.1f} g")
    body = st.GetPrimAtPath("/vehicle/body"); print("  body MassAPI mass:", UsdPhysics.MassAPI(body).GetMassAttr().Get())
