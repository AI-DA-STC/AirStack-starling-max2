from common import *
import os
os.chdir(ROOT)
torch.set_num_threads(6)
from svg_training.ste import distil, exploit
from svg_training.opponents.scripted import make_strategy, steer, _unit
g = distil.load_distil_gates("configs/ste_ls1/distil_gates.toml")
cfg = exploit.variant_cfg(g.skills_gates, "base")
net, p = load_net("strike")
d = load_round("strike", 0, n=300000, seed=11)
obs, slot, lab = d["obs"], d["slot"].long(), d["label"]
R = obs.shape[0]; M = 3
out = net_all(net, obs, slot)
def script_on_rows(name, o):
    s = make_strategy(name, "strike", cfg, R, "cpu", 0)
    full = torch.zeros(o.shape[0], M, OBS_DIM); full[torch.arange(o.shape[0]), slot] = o
    a = s.act(full)
    return a[torch.arange(o.shape[0]), slot]
# anchor: recompute labels
for i, s in enumerate(STRIKES):
    print(s, "max |label - recompute|", float((script_on_rows(s, obs) - lab[:, i]).abs().max()))
# flank internals
own = obs[:, 0:2]; to_zone = -own; dz = to_zone.norm(dim=-1, keepdim=True); hd = _unit(to_zone)
side = torch.stack((-hd[:, 1], hd[:, 0]), -1)
st = V.SLOTS_FROM
rp = torch.stack([obs[:, st + 7*k: st + 7*k + 2] for k in range(5)], 1)
pres = torch.stack([obs[:, st + 7*k + 6] > 0.5 for k in range(5)], 1)
clear = cfg.rules.keepout_strike_m + 0.3
along = (rp * hd[:, None]).sum(-1); off_all = (rp * side[:, None]).sum(-1)
cand = pres & (along > 0) & (along < dz)
in_way = cand & (off_all.abs() < clear)
blocked = in_way.any(-1)
dist = rp.norm(dim=-1).masked_fill(~in_way, float("inf")); near = dist.argmin(-1)
gsel = rp[torch.arange(R), near]; off = (gsel * side).sum(-1)
alive = obs[:, V.alive] > 0.5
e_fl = (out[:, 1, :2] - lab[:, 1, :2])
print(f"\nrows {R}, alive {int(alive.sum())}; flank blocked share {float(blocked.float().mean()):.3f}")
print("flank label != straight label share", float(((lab[:,1,:2]-lab[:,0,:2]).abs().amax(-1) > 1e-6).float().mean()))
print("RMSE net flank v flank label: all %.4f blocked %.4f unblocked %.4f" % (rmse(e_fl), rmse(e_fl, blocked), rmse(e_fl, ~blocked)))
print("share of flank MSE from blocked rows %.3f" % float((e_fl[blocked]**2).sum() / (e_fl**2).sum()))
print("RMSE net flank v STRAIGHT label: blocked %.4f unblocked %.4f" % (rmse(out[:,1,:2]-lab[:,0,:2], blocked), rmse(out[:,1,:2]-lab[:,0,:2], ~blocked)))
print("RMSE flank label v straight label (predict-straight baseline): all %.4f blocked %.4f" % (rmse(lab[:,1,:2]-lab[:,0,:2]), rmse(lab[:,1,:2]-lab[:,0,:2], blocked)))
print("RMSE net flank v net straight: blocked %.4f unblocked %.4f" % (rmse(out[:,1,:2]-out[:,0,:2], blocked), rmse(out[:,1,:2]-out[:,0,:2], ~blocked)))
# aim at guard (mean of two sides)
aim = steer(gsel)
print("RMSE flank label v aim-at-guard on blocked %.4f ; net flank v aim-at-guard %.4f" % (rmse(lab[blocked,1,:2]-aim[blocked]), rmse(out[blocked,1,:2]-aim[blocked])))
# cosine between net flank and label on blocked
def cos(a, b): return (a*b).sum(-1) / (a.norm(dim=-1)*b.norm(dim=-1)).clamp(min=1e-9)
c = cos(out[blocked,1,:2], lab[blocked,1,:2]); c0 = cos(out[blocked,1,:2], lab[blocked,0,:2])
print("blocked: mean cos(net flank, flank label) %.3f ; mean cos(net flank, straight label) %.3f; share cos<0 v flank label %.3f" % (float(c.mean()), float(c0.mean()), float((c<0).float().mean())))
# side choice: bins of |off|
ao = off.abs()
print("\nblocked rows by |off| (side choice); share of blocked rows; flank RMSE; share of wrong side (net cross sign)")
side_net = torch.sign(((out[:,1,:2] - steer(gsel)) * side).sum(-1)); side_lab = torch.sign(((lab[:,1,:2] - steer(gsel)) * side).sum(-1))
for lo, hi in ((0, 0.001), (0.001, 0.01), (0.01, 0.05), (0.05, 0.2), (0.2, 0.5), (0.5, 9)):
    m = blocked & (ao >= lo) & (ao < hi)
    print(f"  |off| [{lo},{hi}) share {float(m.sum())/max(1,int(blocked.sum())):.3f} rmse {rmse(e_fl, m):.4f} wrong-side {float((side_net[m]!=side_lab[m]).float().mean()) if m.any() else float('nan'):.3f}")
# boundary of the corridor: distance to |off_all| = clear for candidate guards
bd = (off_all.abs() - clear).abs().masked_fill(~cand, float("inf")).amin(-1)
print("\nrows by distance to the corridor edge (nearest candidate guard): share; flank RMSE")
for lo, hi in ((0, 0.01), (0.01, 0.05), (0.05, 0.2), (0.2, 0.5), (0.5, 99), (99, float('inf'))):
    m = (bd >= lo) & (bd < hi) if hi != float('inf') else torch.isinf(bd)
    print(f"  [{lo},{hi}) share {float(m.float().mean()):.3f} rmse {rmse(e_fl, m):.4f} blocked share in bin {float(blocked[m].float().mean()) if m.any() else 0:.3f}")
# by number of guards in the way and by along distance
nw = in_way.sum(-1)
print("\nby guards in the way:", {int(k): (round(float((nw==k).float().mean()),3), round(rmse(e_fl, nw==k),4)) for k in range(4)})
al = along[torch.arange(R), near]
for lo, hi in ((0, 0.5), (0.5, 1.0), (1.0, 2.0), (2.0, 4.0), (4.0, 99)):
    m = blocked & (al >= lo) & (al < hi)
    print(f"  blocked, guard ahead {lo}-{hi} m: share {float(m.sum())/max(1,int(blocked.sum())):.3f} rmse {rmse(e_fl, m):.4f}")
# opponent breakdown of blocked share
print("\nblocked share and |off|<1cm share by opponent:")
for j in range(5):
    m = d["opponent"] == j
    print(f"  {GUARDS[j]:20s} blocked {float(blocked[m].float().mean()):.3f}  |off|<1cm among blocked {float(((ao<0.01)&blocked)[m].sum()/max(1,int((blocked&m).sum()))):.3f}  flank rmse {rmse(e_fl, m):.4f}")
# label sensitivity: jitter positions
gen = torch.Generator().manual_seed(5)
pos_idx = [0, 1] + [st + 7*k + j for k in range(8) for j in (0, 1)]
for sig in (0.001, 0.01):
    o2 = obs.clone()
    noise = torch.randn(R, len(pos_idx), generator=gen) * sig
    o2[:, pos_idx] += noise * (o2[:, pos_idx] != 0)   # absent slots stay zero
    o2[:, 0:2] = obs[:, 0:2] + noise[:, 0:2]
    for i in (0, 1, 4, 5):
        l2 = script_on_rows(STRIKES[i], o2)
        print(f"jitter {sig} m: {STRIKES[i]} label RMSE(orig, jittered) {rmse(l2[:, :2]-lab[:, i, :2]):.4f}; share rows moved >0.2 {float(((l2[:, :2]-lab[:, i, :2]).abs().amax(-1)>0.2).float().mean()):.4f}")
