#!/usr/bin/env python3
"""Pick a clear, level flight spot in the construction site and author the wrapper USDA.

Usage: build_arena_usda2.py <Scene02_nohumans.usd> <out.usda> [--spot X Y]
The wrapper's default prim is /stage (what Pegasus references to /World/stage). The launcher clears
/World/stage's xform ops (scale_stage_prim), so the translation lives on the child /stage/site.
"""
import os, argparse, numpy as np
from pxr import Usd, UsdGeom, Sdf, Gf
from scipy.ndimage import distance_transform_edt, maximum_filter, minimum_filter

ap = argparse.ArgumentParser(); ap.add_argument("scene"); ap.add_argument("out"); ap.add_argument("--spot", nargs=2, type=float)
a = ap.parse_args()
stage = Usd.Stage.Open(a.scene, Usd.Stage.LoadAll)
cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), [UsdGeom.Tokens.default_, UsdGeom.Tokens.render])
xcache = UsdGeom.XformCache(Usd.TimeCode.Default())
roots = ["/World/construction_site_withrobot", "/World/Added_Assets"]
boxes = []
for r in roots:
    for c in stage.GetPrimAtPath(r).GetChildren():
        rg = cache.ComputeWorldBound(c).ComputeAlignedRange()
        if rg.IsEmpty(): continue
        boxes.append((c.GetName(), np.array(rg.GetMin()), np.array(rg.GetMax()), r.split("/")[-1]))

# ---- terrain height map from the Landscape meshes (0.5 m cells, max z per cell)
def mesh_points(path):
    out = []
    for p in Usd.PrimRange(stage.GetPrimAtPath(path)):
        if p.IsA(UsdGeom.Mesh):
            P = UsdGeom.Mesh(p).GetPointsAttr().Get()
            if not P: continue
            M = np.array(xcache.GetLocalToWorldTransform(p)); out.append(np.array(P, dtype=float) @ M[:3, :3] + M[3, :3])
    return np.concatenate(out)
pts = mesh_points("/World/construction_site_withrobot/Landscape2")          # the ground terrain (z -0.1..2.4)
pit_pts = mesh_points("/World/construction_site_withrobot/Landscape")       # the excavation mesh (z down to -8.5)
pit_pts = pit_pts[pit_pts[:, 2] < -1.0]
print(f"terrain points: {len(pts)}  z {pts[:,2].min():.2f}..{pts[:,2].max():.2f};  pit-floor points: {len(pit_pts)}")
CELL = 0.5
tx0, ty0 = pts[:, 0].min(), pts[:, 1].min()
tnx, tny = int((pts[:, 0].max() - tx0) / CELL) + 2, int((pts[:, 1].max() - ty0) / CELL) + 2
H = np.full((tny, tnx), np.nan)
ix = ((pts[:, 0] - tx0) / CELL).astype(int); iy = ((pts[:, 1] - ty0) / CELL).astype(int)
np.fmax.at(H, (iy, ix), pts[:, 2])
def terrain(x, y):
    i, j = int((y - ty0) / CELL), int((x - tx0) / CELL)
    return Hfill[i, j] if 0 <= i < tny and 0 <= j < tnx else np.nan
# the terrain mesh is sparse (~3.6 points/m^2): fill empty cells from the nearest sampled cell, remember the gap distance
nan = np.isnan(H)
gap, (gi, gj) = distance_transform_edt(nan, return_distances=True, return_indices=True)
Hfill = H[gi, gj]
print(f"height map {tnx}x{tny} cells of {CELL} m, {nan.mean()*100:.0f}% filled from neighbours, max fill gap {gap.max()*CELL:.1f} m")
hmax = maximum_filter(Hfill, size=int(10 / CELL) + 1); hmin = minimum_filter(Hfill, size=int(10 / CELL) + 1)   # 10 m window (radius 5)
def level(x, y, tol=0.25):
    i, j = int((y - ty0) / CELL), int((x - tx0) / CELL)
    if not (0 <= i < tny and 0 <= j < tnx) or gap[i, j] * CELL > 3: return False, np.nan     # off the terrain or in a hole
    return (hmax[i, j] - hmin[i, j]) <= tol, hmax[i, j] - hmin[i, j]

# ---- occupancy (things a drone at 0-8 m could hit) and prop lists
B = np.array([[*mn, *mx] for _, mn, mx, _ in boxes])
x0, y0 = B[:, :2].min(0) - 1; x1, y1 = B[:, 3:5].max(0) + 1
nx, ny = int(x1 - x0) + 1, int(y1 - y0) + 1
occ = np.zeros((ny, nx), dtype=np.uint8)
for n, mn, mx, _ in boxes:
    if n.startswith("Landscape") or (mx[0] - mn[0]) > 80 or (mx[1] - mn[1]) > 80: continue
    if mx[2] < -0.5 or mn[2] > 8: continue
    occ[max(int(mn[1]-y0),0):min(int(mx[1]-y0)+1,ny), max(int(mn[0]-x0),0):min(int(mx[0]-x0)+1,nx)] = 1
dist = distance_transform_edt(1 - occ)
small = [(n, mn, mx, 0.5*(mn[:2]+mx[:2]), grp) for n, mn, mx, grp in boxes
         if max(mx[0]-mn[0], mx[1]-mn[1]) < 15 and mn[2] < 3 and mx[2] > -0.5]
cen = np.array([c for *_, c, _ in small]); names = [n for n, *_ in small]; added = np.array([g == "Added_Assets" for *_, g in small])
pits = np.array([[*mn[:2], *mx[:2]] for n, mn, mx, _ in boxes if mn[2] < -1.0 and mx[2] < 1.0 and max(mx[0]-mn[0], mx[1]-mn[1]) < 80])
def pit_near(x, y, r=8):
    dx = np.maximum(np.maximum(pits[:,0]-x, x-pits[:,2]), 0); dy = np.maximum(np.maximum(pits[:,1]-y, y-pits[:,3]), 0)
    if (np.hypot(dx, dy) < r).any(): return True
    return bool((np.hypot(pit_pts[:,0]-x, pit_pts[:,1]-y) < r).any())
def score(x, y, R=12):
    d = np.hypot(cen[:,0]-x, cen[:,1]-y); sel = np.where(d < R)[0]; q = [0,0,0,0]
    for i in sel: q[int(cen[i,0] >= x)*2 + int(cen[i,1] >= y)] += 1
    return len(sel), q, int(added[sel].sum())

if a.spot:
    sx, sy = a.spot
else:
    cands = []; rej = {"off_terrain": 0, "rough": 0, "pit": 0, "props": 0}; vars_ = []
    ys, xs = np.where(dist >= 3.0)
    for yy, xx in zip(ys, xs):
        x, y = xx + x0, yy + y0
        ok, var = level(x, y, tol=0.3)
        if np.isnan(var): rej["off_terrain"] += 1; continue
        vars_.append(var)
        if not ok: rej["rough"] += 1; continue
        if pit_near(x, y): rej["pit"] += 1; continue
        k, q, na = score(x, y)
        if min(q) < 1 or k < 8: rej["props"] += 1; continue
        cands.append((k, min(q), dist[yy, xx], x, y, q, na, var))
    print(f"free cells {len(ys)}: rejected {rej}, kept {len(cands)}; on-terrain variation percentiles 10/50/90 = {np.percentile(vars_,[10,50,90]).round(2) if vars_ else 'n/a'}")
    cands.sort(key=lambda c: (-c[6], -c[0], -c[1]))      # prefer the user's Added_Assets area, then prop count
    print("top candidate spots (free radius >=3 m, level terrain, no pit within 8 m, props within 12 m in all quadrants):")
    for k, m, d, x, y, q, na, var in cands[:10]:
        dd = np.hypot(cen[:,0]-x, cen[:,1]-y); near = [names[i] for i in np.argsort(dd)[:5]]
        print(f"   x={x:+7.1f} y={y:+7.1f} free {d:.1f} m  props {k:3d} {q} added {na:2d}  terrain z {terrain(x,y):+.2f} (var {var:.2f})  nearest {near}")
    _, _, _, sx, sy, *_ = cands[0]
hz = terrain(sx, sy)
print(f"chosen spot: x={sx:.1f} y={sy:.1f}  terrain z {hz:+.2f} m  free radius {dist[int(sy - y0), int(sx - x0)]:.1f} m")
near = []
for n, mn, mx, _ in boxes:
    if n.startswith("Landscape") or (mx[0] - mn[0]) > 80 or (mx[1] - mn[1]) > 80: continue
    dx = max(mn[0] - sx, 0, sx - mx[0]); dy = max(mn[1] - sy, 0, sy - mx[1]); d = np.hypot(dx, dy)
    if d < 15: near.append((d, n, (mn - [sx, sy, hz]).round(1), (mx - [sx, sy, hz]).round(1)))
near.sort(key=lambda r: r[0])
print(f"{len(near)} objects within 15 m of the new origin; nearest (coords relative to the new origin):")
for d, n, mn, mx in near[:14]: print(f"   {d:5.1f} m  {n:34s} min {mn} max {mx}")

# ---- author the wrapper
rel = os.path.relpath(a.scene, os.path.dirname(os.path.abspath(a.out)))
layer = Sdf.Layer.CreateNew(a.out)
w = Usd.Stage.Open(layer)
UsdGeom.SetStageUpAxis(w, UsdGeom.Tokens.z); UsdGeom.SetStageMetersPerUnit(w, 1.0)
root = UsdGeom.Xform.Define(w, "/stage"); w.SetDefaultPrim(root.GetPrim())
site = UsdGeom.Xform.Define(w, "/stage/site")
site.AddTranslateOp().Set(Gf.Vec3d(-sx, -sy, -float(hz)))
for r in roots:
    p = w.DefinePrim(f"/stage/site/{r.split('/')[-1]}", "Xform")
    p.GetReferences().AddReference(rel, r)
layer.comment = (f"Construction-site arena for the SVG swarm sim. References the site + props from {rel} "
                 f"(not the Meerkat robot, its OmniGraphs or its PhysicsScene). Site translated by ({-sx:.1f}, {-sy:.1f}, {-hz:.2f}) "
                 f"so the level clear patch at site ({sx:.1f}, {sy:.1f}) is the drones' origin at ground level. Generated by build_arena_usda2.py.")
layer.Save()
print("wrote", a.out)
v = Usd.Stage.Open(a.out, Usd.Stage.LoadAll)
n = sum(1 for _ in v.Traverse()); meshes = sum(1 for p in v.Traverse() if p.IsA(UsdGeom.Mesh))
bad = [str(p.GetPath()) for p in v.Traverse() if p.GetTypeName() in ("OmniGraph", "PhysicsScene", "RenderProduct") or "Assemmovablewheels" in p.GetName()]
print(f"wrapper composes: {n} prims, {meshes} meshes; unwanted prims carried over: {len(bad)}")
