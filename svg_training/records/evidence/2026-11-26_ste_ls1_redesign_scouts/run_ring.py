import sys, torch
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from geo import *
d = load("guard", 300000, seed=7); obs, sl = d["obs"], d["slot"]; own = obs[:, 0:2]
l0, c0 = g_ring(obs, sl)
mates, live = team(obs, sl, 0); n_live = live.sum(-1); idx = torch.arange(M)
ref = torch.where(live, idx, M).amin(-1).clamp(max=M - 1); refp = gat(mates, ref)
th = torch.atan2(mates[..., 1], mates[..., 0]); w = live.float()
s = torch.stack(((w * (3 * th).cos()).sum(-1), (w * (3 * th).sin()).sum(-1)), -1).norm(dim=-1)
for delta in (0.001, 0.01):
    oj = jitter(obs, delta, torch.Generator().manual_seed(11)); l1, c1 = g_ring(oj, sl)
    j = (l1 - l0)[:, :2].norm(dim=-1); big = j > 0.2
    tot = float((j.double()**2).sum())
    print(f"delta {delta*1000:.0f} mm: rows with |dlabel|>0.2: {float(big.float().mean()):.5f}; share of sq change in them {float((j[big].double()**2).sum())/tot:.3f}")
    for name, m in (("whole team", n_live >= 3), ("after loss", n_live < 3)):
        bb = big & m
        print(f"   {name}: rows {float(m.float().mean()):.3f}, big jumps {int(bb.sum())}, |own| q {[round(x,3) for x in own.norm(dim=-1)[bb].quantile(torch.tensor([.1,.5,.9])).tolist()] if bb.sum()>2 else []}, "
              f"|Guard0| q {[round(x,3) for x in refp.norm(dim=-1)[bb].quantile(torch.tensor([.1,.5,.9])).tolist()] if bb.sum()>2 else []}, "
              f"|3-fold sum| q {[round(x,3) for x in s[bb].quantile(torch.tensor([.1,.5,.9])).tolist()] if bb.sum()>2 else []}, jump p50 {float(j[bb].median()) if bb.sum() else 0:.3f}")
    # smooth part: rows with jumps < 0.2 RMS
    print(f"   RMS of the rows without a big jump {float((j[~big].double()**2).mean().sqrt()):.4f}")
