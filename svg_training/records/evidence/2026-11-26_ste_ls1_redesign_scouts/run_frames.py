"""Frame checks, boundary densities (rows per metre of margin) and the smoothing width a smooth fit may use for a target."""
import sys, torch
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from geo import *

def q(x, ps=(0.01, 0.1, 0.5, 0.9, 0.99)):
    return [round(v, 4) for v in x.float().quantile(torch.tensor(ps)).tolist()] if x.numel() > 2 else []
def dens(margin, mask, J2, name, nrows):
    """margin [R] >= 0 metres (inf where the boundary does not apply); share within 1 and 5 mm and 1 cm; rows per metre;
    width w for per-channel RMSE 0.01 / 0.05 (2 used channels): MSE_xy = rho * E[J^2] * w / 12."""
    m = margin[mask]
    s1, s5, s10 = [float((m < t).sum()) / nrows for t in (0.001, 0.005, 0.01)]
    rho = s10 / 0.02
    w = lambda r: 12 * 2 * r * r / max(rho * J2, 1e-12)
    print(f"  {name:34s} within 1/5/10 mm: {s1:.5f} {s5:.5f} {s10:.5f}; rho {rho:.3f} /m; E[J^2] {J2:.2f}; "
          f"w for 0.05: {w(0.05)*1000:.1f} mm, for 0.01: {w(0.01)*1000:.2f} mm")

N = 300000
# ---------------------------------------------------------------- Strike
d = load("strike", N, seed=7); obs, sl, lab = d["obs"], d["slot"], d["label"]; R = obs.shape[0]
own = obs[:, 0:2]; eh = unit(-own); es = perp(eh)
rot = lambda v: torch.stack(((v * eh).sum(-1), (v * es).sum(-1)), -1)
print("=== strike: |own xy| quantiles", q(own.norm(dim=-1)))
for k, name in enumerate(STRIKE):
    f = rot(lab[:, k, :2])
    print(f"  {name:18s} label in zone-line frame: along mean {float(f[:,0].mean()):.4f} sd {float(f[:,0].std()):.4f}; side mean {float(f[:,1].mean()):.4f} sd {float(f[:,1].std()):.4f}")
for k, name in ((2, "strike_high"), (3, "strike_low")):
    f = rot(lab[:, k, :2]); vz = lab[:, k, 2]
    pred = (1 - vz ** 2).clamp(min=0).sqrt()
    print(f"  {name}: max|along - sqrt(1-vz^2)| {float((f[:,0]-pred).abs().max()):.2e}, max|side| {float(f[:,1].abs().max()):.2e}; "
          f"share of rows inside the 0.25 m height ramp {float((vz.abs() < 1).float().mean()):.3f}")
# flank margins
own_, tz, dz, hd, sd, rp, pres, along, off, cf, cs, cc = flank_parts(obs)
inw = pres & cf & cs & cc; blocked = inw.any(-1)
dist = rp.norm(dim=-1).masked_fill(~inw, float("inf")); srt = dist.sort(-1).values
near = dist.argmin(-1); off_sel = gat(off[..., None], near)[:, 0]
print(f"flank: blocked share {float(blocked.float().mean()):.3f}; in-way count dist {torch.bincount(inw.sum(-1)).tolist()}")
print("  selected Guard: along q", q(gat(along[..., None], near)[:, 0][blocked]), "|off| q", q(off_sel.abs()[blocked]))
# which in_way condition is nearest to flipping, per present guard
m_front = torch.where(pres & cs & cc, along.abs(), torch.full_like(along, float("inf"))).amin(-1)
m_short = torch.where(pres & cf & cc, (dz - along).abs(), torch.full_like(along, float("inf"))).amin(-1)
m_corr = torch.where(pres & cf & cs, (off.abs() - CLEAR).abs(), torch.full_like(along, float("inf"))).amin(-1)
gpos = own[:, None] + rp
print("  Guards present: |pos from zone centre| q", q(gpos.norm(dim=-1)[pres]), "; share of present Guards within 1.4 m of centre",
      round(float((gpos.norm(dim=-1)[pres] < 1.4).float().mean()), 3))
print("  absent Guard slot encodes along=0, off=0 (on two boundaries at once); present-but-absent rows: share of rows with <3 Guards",
      round(float((pres.sum(-1) < 3).float().mean()), 3))
dens(off_sel.abs(), blocked, 1.19 ** 2, "flank side (off_sel = 0)", R)
dens((srt[:, 1] - srt[:, 0]) / 2, blocked & torch.isfinite(srt[:, 1]), 1.19 ** 2, "flank nearest-in-way swap", R)
dens(m_corr, torch.ones(R, dtype=torch.bool), 0.72 ** 2, "flank corridor edge |off|=1.4 (any Guard)", R)
dens(m_front, torch.ones(R, dtype=torch.bool), 0.72 ** 2, "flank along=0 (any Guard)", R)
dens(m_short, torch.ones(R, dtype=torch.bool), 0.72 ** 2, "flank along=dist_zone (any Guard)", R)
# sacrifice
l, c = s_sacrifice(obs, sl); mates, live = team(obs, sl, PG); others = (live[:, 0] & (live.sum(-1) >= 2))
rest = others & (sl != 0); rho_own = own.norm(dim=-1); diff = c["diff"]
print(f"sacrifice: rows of a non-decoy with the decoy live {float(rest.float().mean()):.3f}; decoy rows with a Guard {float((others & (sl==0)).float().mean()):.3f}")
dens(rho_own * (diff.abs() - PI / 6).abs(), rest, 1.35 ** 2, "sacrifice go_in edge (arc, m)", R)
dens(rho_own * (PI - diff.abs()), rest & (diff.abs() > PI / 6), 1.98 ** 2, "sacrifice direction flip at pi (arc, m)", R)
gp, _, gpres = slots(obs, 0, PG); guard_p = own[:, None] + gp
td = (guard_p - mates[:, 0][:, None]).norm(dim=-1).masked_fill(~gpres, float("inf")).sort(-1).values
dens((td[:, 1] - td[:, 0]) / 2, rest & torch.isfinite(td[:, 1]), 1.0, "sacrifice drawn-Guard swap (J~1 assumed)", R)
gd = gp.norm(dim=-1).masked_fill(~gpres, float("inf")).sort(-1).values
dens((gd[:, 1] - gd[:, 0]) / 2, others & (sl == 0) & torch.isfinite(gd[:, 1]), 1.0, "sacrifice decoy nearest-Guard swap (J~1)", R)
# converge
l, c = s_converge(obs, sl); act = c["n_live"] >= 2
print(f"converge: rows n_live>=2 {float(act.float().mean()):.3f}; go {float((c['go']&act).float().mean()):.3f}; committed {float((c['committed']&act).float().mean()):.3f}; gathered-not-committed {float((c['gathered']&~c['committed']&act).float().mean()):.3f}")
dens((c["minrho"] - 2.3).abs(), act & ~c["gathered"], 1.55 ** 2, "converge committed (min live rho = 2.3)", R)
dens(2.6 * (c["maxerr"] - 0.1).abs(), act & ~c["committed"], 1.2 ** 2, "converge gathered (max err = 0.1 rad, arc)", R)
pc = c["pace"][act & c["go"]]
print("  run-in pace q", q(pc), "; team's max edge distance (m) q (run-in rows):")
mates, live = team(obs, sl, PG); te = (mates.norm(dim=-1) - 1.6).clamp(min=0) * live
print("   ", q(te.amax(-1)[act & c["go"]]))

# ---------------------------------------------------------------- Guard
d = load("guard", N, seed=7); obs, sl = d["obs"], d["slot"]; R = obs.shape[0]; own = obs[:, 0:2]
print("=== guard: |own xy| q", q(own.norm(dim=-1)), "; share < 0.1/0.25/0.5 m",
      [round(float((own.norm(dim=-1) < t).float().mean()), 4) for t in (0.1, 0.25, 0.5)])
sp, sv, found, pk = marked(obs, sl)
print("  marked Strike |pos| q", q(sp.norm(dim=-1)[found]), "; found share", round(float(found.float().mean()), 4))
rp, _, pres = slots(obs, PG, PS); dist = rp.norm(dim=-1).masked_fill(~pres, float("inf")).sort(-1).values
dens((dist[:, 1] - dist[:, 0]) / 2, torch.isfinite(dist[:, 1]), 1.6 ** 2, "field nearest-Strike swap", R)
tp, _, tpres = slots(obs, 0, PG)
print("  field push active (a mate within 1.1 m) share", round(float((tpres & (tp.norm(dim=-1) < 1.1)).any(-1).float().mean()), 4),
      "; mate distance q", q(tp.norm(dim=-1)[tpres]))
# ring: the conditioning of the bearings it reads
mates, live = team(obs, sl, 0); n_live = live.sum(-1); idx = torch.arange(M)
ref = torch.where(live, idx, M).amin(-1).clamp(max=M - 1); refp = gat(mates, ref)
print(f"  ring: whole team live {float((n_live>=3).float().mean()):.3f}; |Guard 0 pos| q (whole team)", q(refp.norm(dim=-1)[n_live >= 3]))
th = torch.atan2(mates[..., 1], mates[..., 0]); w = live.float()
cm = torch.stack(((w * (3 * th).cos()).sum(-1), (w * (3 * th).sin()).sum(-1)), -1).norm(dim=-1)
print("   after a loss: |sum of 3-fold unit vectors| q", q(cm[n_live < 3]), "(small = phase ill-defined)")
l, c = g_ring(obs, sl); oth = torch.atan2(own[:, 1], own[:, 0])
phase = torch.atan2((w * (3 * th).sin()).sum(-1), (w * (3 * th).cos()).sum(-1)) / 3
fr = wrap(oth - phase) / (2 * PI / 3); mm = (fr - fr.round()).abs()
dens((0.5 - mm) * (2 * PI / 3) * own.norm(dim=-1), n_live < 3, 1.5 ** 2, "ring after-loss station round() (arc, m)", R)
