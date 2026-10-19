import sys
from pxr import Usd, UsdGeom, Gf
for p in sys.argv[1:]:
    st = Usd.Stage.Open(p); print("####", p)
    for path in ("/vehicle", "/vehicle/body", "/vehicle/body/body", "/vehicle/rotor0", "/vehicle/rotor1", "/vehicle/rotor2", "/vehicle/rotor3"):
        prim = st.GetPrimAtPath(path)
        if not prim: continue
        x = UsdGeom.Xformable(prim)
        ops = {o.GetOpName(): o.Get() for o in x.GetOrderedXformOps()}
        m = x.GetLocalTransformation()
        zaxis = m.TransformDir(Gf.Vec3d(0, 0, 1))
        print(f"  {path}: ops={ops}\n      local +Z maps to {tuple(round(v,3) for v in zaxis)}")
    for path in ("/vehicle/rotor0/rotor0", "/vehicle/rotor0/iris_prop_ccw"):
        prim = st.GetPrimAtPath(path)
        if prim:
            x = UsdGeom.Xformable(prim); print(f"  {path} mesh ops=", {o.GetOpName(): o.Get() for o in x.GetOrderedXformOps()})
