import sys, pathlib; sys.path.insert(0, str(pathlib.Path.home() / "AirStack-starling-max2-dev/svg_training/records/evidence/2026-11-26_ste_ls1_redesign_scouts"))
import torch, geo
from geo import *
d = torch.load(geo.ROOT / "runs/2026-11-26_ste_ls11_distil_strike/data/round_0.pt", weights_only=True)
rows = torch.nonzero((d["game"] % 5 == 0) & (d["flown"] == 1)).squeeze(1)[:200000]
obs = d["obs"][rows]; opp = d["opponent"][rows] if "opponent" in d else None
own = obs[:, 0:2]; tz = -own; dz = tz.norm(dim=-1, keepdim=True); hd = unit(tz); sd = perp(hd)
rp, _, pres = slots(obs, 0, PG)
along = (rp * hd[:, None]).sum(-1); off = (rp * sd[:, None]).sum(-1)
gz = (own[:, None] + rp).norm(dim=-1)
for name, m in (("along>0", along), ("along<dz", dz - along), ("|off|<clear", CLEAR - off.abs()), ("off sign", off)):
    near = (m.abs() < 0.005) & pres
    print(f"{name:12s}: rows with a present Guard within 5 mm of it {float(near.any(-1).float().mean()):.4f}")
cz = pres & (gz < 1e-3)
print("rows with a Guard within 1 mm of the zone centre", float(cz.any(-1).float().mean()))
print("of those, guard along - dz:", (along - dz)[cz][:10].tolist())
if opp is not None: print("opponent ids among centre rows", opp[cz.any(-1)].unique(return_counts=True))
