#!/usr/bin/env python3
"""Build a cropped, flattened, de-duplicated copy of the construction-site arena for Isaac.

Usage: crop_site.py <construction_site_arena.usda (installed copy)> <out_dir> [--radius 40]

Why: the full arena composes to 125k prims / 5.6k meshes / 12.3k materials; Isaac must compile every material.
Keeping only what is within R m of the flight origin (plus ground/backdrop) cuts that to ~1k meshes and ~60 unique
materials. Output: <out_dir>/construction_site_rNN.usdc + textures/ next to it. Default prim stays `stage` with the same
/stage/site translate, so the launcher path (ENV_USD=...usdc) is unchanged. CPU only (usd-core), ~1-2 min.

Flattening is done by hand (prim/attribute/relationship copy) because Usd.Stage.Flatten() aborts on ~12k shader colour
inputs (emissiveColor etc.) that this USD build cannot decode from the UE4-exported crate files; those are skipped.
"""
import argparse, hashlib, os, shutil, sys
from pxr import Usd, UsdGeom, UsdShade, UsdPhysics, Sdf, Gf

ap = argparse.ArgumentParser(); ap.add_argument("arena"); ap.add_argument("out_dir"); ap.add_argument("--radius", type=float, default=40.0)
a = ap.parse_args()
R = a.radius
KEEP = {"Landscape2", "Landscape", "Plane2", "Plane3", "Plane4", "Plane5", "Plane", "DistantLight"}   # ground, far planes, one sun
DROP = {"male_adult_construction_04", "SkyLight", "Light_Source", "PointLight", "PointLight2", "SpotLight",
        "ConcreteWall1456LookFollowCamera0"}            # S3-payload person, duplicate dome light, extra lights, a UE camera
ROOTS = ["/stage/site/construction_site_withrobot", "/stage/site/Added_Assets"]

def safe_get(attr):
    try: return attr.Get()
    except Exception: return None

def box_dist_2d(rg):
    mn, mx = rg.GetMin(), rg.GetMax()
    dx = max(mn[0], 0.0, -mx[0]); dy = max(mn[1], 0.0, -mx[1])
    return (dx * dx + dy * dy) ** 0.5

src = Usd.Stage.Open(a.arena, Usd.Stage.LoadAll)
src.SetEditTarget(src.GetSessionLayer())
bc = UsdGeom.BBoxCache(Usd.TimeCode.Default(), [UsdGeom.Tokens.default_, UsdGeom.Tokens.render])
kept = dropped = 0
for root in ROOTS:
    rp = src.GetPrimAtPath(root)
    if not rp: print("missing root", root); continue
    for c in rp.GetChildren():
        n = c.GetName()
        rg = bc.ComputeWorldBound(c).ComputeAlignedRange()
        keep = (n in KEEP) or (n not in DROP and not rg.IsEmpty() and box_dist_2d(rg) <= R)
        if n in DROP or n.startswith(("male_adult", "female_adult")) or c.GetTypeName() == "Camera": keep = False
        if c.GetTypeName().endswith("Light") and n != "DistantLight": keep = False
        if keep: kept += 1
        else: c.SetActive(False); dropped += 1
print(f"radius {R} m: kept {kept} objects, deactivated {dropped}")

# ---- manual flatten into a new crate layer
out_dir = os.path.abspath(a.out_dir); tex_dir = os.path.join(out_dir, "textures"); os.makedirs(tex_dir, exist_ok=True)
out_path = os.path.join(out_dir, f"construction_site_r{int(R)}.usdc")
if os.path.exists(out_path): os.remove(out_path)
out = Sdf.Layer.CreateNew(out_path)
dst = Usd.Stage.Open(out)
UsdGeom.SetStageUpAxis(dst, UsdGeom.GetStageUpAxis(src)); UsdGeom.SetStageMetersPerUnit(dst, UsdGeom.GetStageMetersPerUnit(src))
n_prims = n_attrs = n_skipped = n_tex = 0; tex_names = {}
for prim in Usd.PrimRange(src.GetPseudoRoot(), Usd.TraverseInstanceProxies(Usd.PrimIsActive & Usd.PrimIsDefined & ~Usd.PrimIsAbstract)):
    if prim.IsPseudoRoot(): continue
    spec = Sdf.CreatePrimInLayer(out, prim.GetPath()); n_prims += 1
    spec.specifier = Sdf.SpecifierDef
    try:
        if prim.GetTypeName(): spec.typeName = prim.GetTypeName()
    except Exception as e:
        print("typeName failed for", prim.GetPath(), repr(prim.GetTypeName()), e); raise
    schemas = prim.GetAppliedSchemas()
    if schemas: spec.SetInfo("apiSchemas", Sdf.TokenListOp.CreateExplicit(list(schemas)))
    for key in ("kind", "purpose"):
        if prim.HasAuthoredMetadata(key): spec.SetInfo(key, prim.GetMetadata(key))
    for attr in prim.GetAttributes():
        conns = attr.GetConnections()
        # shader outputs (outputs:surface, outputs:rgb, ...) carry neither a value nor a connection but must exist
        if not attr.HasAuthoredValue() and not conns and not attr.GetName().startswith("outputs:"): continue
        aspec = Sdf.AttributeSpec(spec, attr.GetName(), attr.GetTypeName(), attr.GetVariability()); aspec.custom = attr.IsCustom()
        if conns: aspec.connectionPathList.explicitItems = conns
        if attr.HasAuthoredValue():
            try: v = attr.Get()
            except Exception: n_skipped += 1; continue
            if v is None: continue
            if isinstance(v, Sdf.AssetPath):
                rp = str(v.resolvedPath)
                if attr.GetName() == "inputs:file" and rp and os.path.exists(rp):           # copy the texture next to the output
                    bn = os.path.basename(rp)
                    if bn in tex_names and tex_names[bn] != rp: bn = hashlib.md5(rp.encode()).hexdigest()[:8] + "_" + bn
                    tex_names[bn] = rp; dstf = os.path.join(tex_dir, bn)
                    if not os.path.exists(dstf): shutil.copy(rp, dstf); n_tex += 1
                    v = Sdf.AssetPath("./textures/" + bn)
                elif rp:
                    v = Sdf.AssetPath(rp)                                                  # e.g. MDL modules: keep absolute resolved path
            aspec.default = v; n_attrs += 1
        # authored attribute metadata: interpolation (primvars!), elementSize, colorSpace, displayName, ...
        for key, val in attr.GetAllAuthoredMetadata().items():
            if key in ("default", "typeName", "variability", "custom", "timeSamples", "connectionPaths"): continue
            try: aspec.SetInfo(key, val)
            except Exception: pass
    for rel in prim.GetRelationships():
        tg = rel.GetTargets()
        if tg:
            rspec = Sdf.RelationshipSpec(spec, rel.GetName(), rel.IsCustom()); rspec.targetPathList.explicitItems = tg
print(f"flattened: {n_prims} prims, {n_attrs} attributes ({n_skipped} undecodable skipped), {n_tex} textures copied")
dst.SetDefaultPrim(dst.GetPrimAtPath("/stage"))

# ---- material de-dup: signature over the material's shader network
def mat_signature(mat):
    parts = []
    for sh in Usd.PrimRange(mat.GetPrim()):
        if not sh.IsA(UsdShade.Shader): continue
        s = UsdShade.Shader(sh); parts.append(("shader", sh.GetName(), s.GetShaderId() or ""))
        for inp in s.GetInputs():
            if inp.HasConnectedSource():
                # connection described relative to the material (shader name + output), not by absolute prim path
                parts.append((inp.GetBaseName(), "->" + ";".join(f"{c.GetPrimPath().name}.{c.name}" for c in inp.GetAttr().GetConnections())))
            else:
                v = safe_get(inp.GetAttr())
                if isinstance(v, Sdf.AssetPath): v = v.path
                parts.append((inp.GetBaseName(), repr(v)))
    return hashlib.md5(repr(sorted(parts)).encode()).hexdigest()

dst.DefinePrim("/stage/Looks", "Scope")
canon = {}; rebound = 0; removed = 0
for p in list(dst.Traverse()):
    if not (p.IsA(UsdGeom.Mesh) or p.IsA(UsdGeom.Subset)): continue
    api = UsdShade.MaterialBindingAPI(p); mat, _ = api.ComputeBoundMaterial()
    if not mat: continue
    sig = mat_signature(mat)
    if sig not in canon:
        cpath = Sdf.Path(f"/stage/Looks/M_{len(canon):03d}")
        Sdf.CopySpec(out, mat.GetPath(), out, cpath); canon[sig] = cpath
    if mat.GetPath() != canon[sig]:
        api.UnbindDirectBinding(); api.Bind(UsdShade.Material(dst.GetPrimAtPath(canon[sig]))); rebound += 1
dup_paths = [p.GetPath() for p in dst.Traverse() if p.IsA(UsdShade.Material) and not p.GetPath().HasPrefix(Sdf.Path("/stage/Looks"))]
for path in dup_paths:
    if dst.GetPrimAtPath(path): dst.RemovePrim(path); removed += 1
print(f"materials: {len(canon)} unique under /stage/Looks, {rebound} bindings redirected, {removed} per-mesh copies removed")

# ---- physics: the excavation mesh was a convex hull (sealed solid) -> triangle mesh so the pit is a pit
pit = dst.GetPrimAtPath("/stage/site/construction_site_withrobot/Landscape")
if pit:
    for m in Usd.PrimRange(pit):
        if m.IsA(UsdGeom.Mesh) and m.HasAPI(UsdPhysics.MeshCollisionAPI):
            UsdPhysics.MeshCollisionAPI(m).GetApproximationAttr().Set("none")
out.Save()
print("wrote", out_path)

# ---- verify by reopening
v = Usd.Stage.Open(out_path, Usd.Stage.LoadAll)
meshes = sum(1 for p in v.Traverse() if p.IsA(UsdGeom.Mesh)); mats = sum(1 for p in v.Traverse() if p.IsA(UsdShade.Material))
prims = sum(1 for _ in v.Traverse()); lights = [str(p.GetPath()) for p in v.Traverse() if p.GetTypeName().endswith("Light")]
bad = []; nomat = 0
for p in v.Traverse():
    if p.IsA(UsdGeom.Mesh) and not UsdShade.MaterialBindingAPI(p).ComputeBoundMaterial()[0]: nomat += 1
    for at in p.GetAttributes():
        if at.GetTypeName() == Sdf.ValueTypeNames.Asset:
            val = safe_get(at)
            if isinstance(val, Sdf.AssetPath) and val.path and ("/home/" in val.path or val.path.startswith("http")): bad.append((str(p.GetPath()), val.path))
            if isinstance(val, Sdf.AssetPath) and val.path.startswith("./textures/") and not os.path.exists(os.path.join(out_dir, val.path)): bad.append((str(p.GetPath()), "missing " + val.path))
rg = UsdGeom.BBoxCache(Usd.TimeCode.Default(), [UsdGeom.Tokens.default_]).ComputeWorldBound(v.GetPrimAtPath("/stage")).ComputeAlignedRange()
print(f"verify: prims {prims}, meshes {meshes} ({nomat} without material), materials {mats}, lights {lights}, mpu {UsdGeom.GetStageMetersPerUnit(v)}, up {UsdGeom.GetStageUpAxis(v)}, defaultPrim {v.GetDefaultPrim().GetPath()}")
print(f"        bounds min {[round(x,1) for x in rg.GetMin()]} max {[round(x,1) for x in rg.GetMax()]}; bad asset paths: {len(bad)} {bad[:3]}")
print(f"        size {os.path.getsize(out_path)/1e6:.1f} MB + textures {sum(os.path.getsize(os.path.join(tex_dir,f)) for f in os.listdir(tex_dir))/1e6:.1f} MB")
sys.exit(1 if bad else 0)
