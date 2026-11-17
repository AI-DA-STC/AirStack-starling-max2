"""Rewrite absolute asset paths baked in by the UE4 export (any /.../environments/construction_site/Assets/...) inside a USD
layer to paths relative to the layer, so the site works from wherever its copy sits (source/ here, or the installed copy)."""
import sys, os
from pxr import Sdf
MARK = "/environments/construction_site/Assets/"
for path in sys.argv[1:]:
    layer = Sdf.Layer.FindOrOpen(path); n = 0
    here = os.path.dirname(os.path.abspath(path))
    top = os.path.abspath(path).split("/environments/construction_site/")[0]   # the copy's own top folder
    def fix(p):
        global n
        if p.startswith("/") and MARK in p:
            n += 1
            rel = os.path.relpath(os.path.join(top, "environments/construction_site/Assets", p.split(MARK, 1)[1]), here)
            return rel if rel.startswith(".") else "./" + rel
        return p
    def visit(prim):
        for kind in ("referenceList", "payloadList"):
            lst = getattr(prim, kind)
            for field in ("prependedItems", "appendedItems", "explicitItems", "addedItems"):
                items = list(getattr(lst, field))
                if not items: continue
                def rebuild(i):
                    if isinstance(i, Sdf.Reference): return Sdf.Reference(fix(i.assetPath), i.primPath, i.layerOffset, i.customData)
                    if isinstance(i, Sdf.Payload): return Sdf.Payload(fix(i.assetPath), i.primPath, i.layerOffset)
                    return i
                new = [rebuild(i) for i in items]
                if any(a.assetPath != b.assetPath for a, b in zip(items, new)): setattr(lst, field, new)
        for attr in prim.attributes:
            v = attr.default
            if isinstance(v, Sdf.AssetPath) and v.path.startswith("/") and MARK in v.path: attr.default = Sdf.AssetPath(fix(v.path))   # fix() counts it
        for c in prim.nameChildren: visit(c)
    for root in layer.rootPrims: visit(root)
    layer.subLayerPaths = [fix(p) for p in layer.subLayerPaths]
    if n: layer.Save()
    print(f"{os.path.basename(path)}: rewrote {n} absolute path(s)")
    # verify: nothing in the composed stage may still resolve into the user's home directory
    from pxr import Usd
    st = Usd.Stage.Open(path, Usd.Stage.LoadAll)
    bad = [l.identifier for l in st.GetUsedLayers() if "/home/" in l.identifier and not l.identifier.startswith(os.path.dirname(os.path.abspath(path)))]
    missing = [l.identifier for l in st.GetUsedLayers() if not (l.anonymous or os.path.exists(l.realPath or ""))]
    print(f"   verify: {len(st.GetUsedLayers())} layers, outside-home refs {len(bad)}, missing {len(missing)}")
    if bad or missing: sys.exit(1)
