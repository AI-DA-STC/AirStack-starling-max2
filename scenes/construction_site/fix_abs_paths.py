"""Rewrite absolute /home/... asset paths inside a USD layer to paths relative to the layer (installed copy only)."""
import sys, os
from pxr import Sdf
ABS_PREFIX = "/home/jeremychia/Documents/Meerkat_robot_JAZZY/Simulation Files/environments/construction_site/Assets/"
for path in sys.argv[1:]:
    layer = Sdf.Layer.FindOrOpen(path); n = 0
    def fix(p):
        global n
        if p.startswith(ABS_PREFIX): n += 1; return "./" + p[len(ABS_PREFIX):]
        return p
    def visit(prim):
        for kind in ("referenceList", "payloadList"):
            lst = getattr(prim, kind)
            for field in ("prependedItems", "appendedItems", "explicitItems", "addedItems"):
                items = list(getattr(lst, field))
                if not items: continue
                new = [type(i)(fix(i.assetPath), i.primPath, i.layerOffset) if hasattr(i, "primPath") else i for i in items]
                if any(a.assetPath != b.assetPath for a, b in zip(items, new)): setattr(lst, field, new)
        for attr in prim.attributes:
            v = attr.default
            if isinstance(v, Sdf.AssetPath) and v.path.startswith(ABS_PREFIX): attr.default = Sdf.AssetPath(fix(v.path))
        for c in prim.nameChildren: visit(c)
    for root in layer.rootPrims: visit(root)
    layer.subLayerPaths = [fix(p) for p in layer.subLayerPaths]
    if n: layer.Save()
    print(f"{os.path.basename(path)}: rewrote {n} absolute path(s)")
