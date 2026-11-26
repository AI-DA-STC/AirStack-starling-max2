from common import *
import os, math
os.chdir(ROOT)
torch.set_num_threads(int(os.environ.get("OMP_NUM_THREADS", "2")))
from svg_training.ste import distil, exploit
from svg_training.opponents import scripted as S
g = distil.load_distil_gates("configs/ste_ls1/distil_gates.toml")
cfg = exploit.variant_cfg(g.skills_gates, "base")
net, p = load_net("guard")
for r in (0, 3):
    d = load_round("guard", r, n=300000, seed=21 + r)
    obs, slot, lab = d["obs"], d["slot"].long(), d["label"]
    R = obs.shape[0]; M = 3; ar = torch.arange(R)
    out = net_all(net, obs, slot)
    err = out - lab
    print(f"\n=== guard round {r} (net_flown {float(d['net_flown'].float().mean()):.2f}); label |yaw|max {float(lab[..., 3].abs().max()):.2e} |vz|max {float(lab[..., 2].abs().max()):.2e}")
    print("flown share:", {GUARDS[i]: round(float((d['flown']==i).float().mean()),3) for i in range(5)})
    for i, s in enumerate(GUARDS):
        print(f"  {s:20s} rmse xy {rmse(err[:, i, :2]):.4f}  yaw out mean {float(out[:, i, 3].mean()):+.4f} sd {float(out[:, i, 3].std()):.4f}  max|xy err| {float(err[:, i, :2].abs().max()):.3f}")
    # parked centre: where is the output largest
    pc = out[:, 0, :2].norm(dim=-1)
    print("  parked_centre |xy out| quantiles p50 %.4f p90 %.4f p99 %.4f p99.9 %.4f max %.4f; share > 0.005: %.3f" % tuple(
        [float(pc.quantile(q)) for q in (0.5, 0.9, 0.99, 0.999)] + [float(pc.max()), float((pc > 0.005).float().mean())]))
    for k in (1, 2, 3):
        m = d["n_live"] == k
        print(f"   parked_centre n_live {k}: share {float(m.float().mean()):.3f} p99 |out| {float(pc[m].quantile(0.99)) if m.any() else float('nan'):.4f}")
    # field: decompose by push active and nearest-strike gap
    own_p = obs[:, 0:2]
    full = torch.zeros(R, M, OBS_DIM); full[ar, slot] = obs
    tp, _, tpres = S._slots(full, 0, cfg.pad_guards); tp, tpres = tp[ar, slot], tpres[ar, slot]
    dd = tp.norm(dim=-1).clamp(min=1e-6)
    push_on = (tpres & (dd < S.FIELD_RANGE_M)).any(-1)
    dmin = dd.masked_fill(~tpres, 99).amin(-1)
    rp, _, pres = S._slots(full, cfg.pad_guards, cfg.pad_strikes); rp, pres = rp[ar, slot], pres[ar, slot]
    dist = rp.norm(dim=-1).masked_fill(~pres, float("inf")); ds = dist.sort(-1).values; gap = ds[:, 1] - ds[:, 0]
    e = err[:, 4, :2]; tot = float((e ** 2).sum())
    print("  FIELD: push active share %.3f RMSE %.4f (MSE share %.3f); push off RMSE %.4f" % (float(push_on.float().mean()), rmse(e, push_on), float((e[push_on]**2).sum())/tot, rmse(e, ~push_on)))
    for lo, hi in ((0, 0.7), (0.7, 0.9), (0.9, 1.0), (1.0, 1.1), (1.1, 1.3), (1.3, 99)):
        m = (dmin >= lo) & (dmin < hi)
        print(f"    nearest mate {lo}-{hi} m: share {float(m.float().mean()):.3f} RMSE {rmse(e, m):.4f}")
    for lo, hi in ((0, 0.05), (0.05, 0.2), (0.2, 99)):
        m = (gap >= lo) & (gap < hi)
        print(f"    gap between two nearest Strikes {lo}-{hi} m: share {float(m.float().mean()):.3f} RMSE {rmse(e, m):.4f}")
    lab_norm = lab[:, 4, :2].norm(dim=-1)
    print(f"    label saturated (|a|=1) share {float((lab_norm > 0.999).float().mean()):.3f} RMSE {rmse(e, lab_norm > 0.999):.4f}; not {rmse(e, lab_norm <= 0.999):.4f}")
    # mirror
    e = err[:, 3, :2]
    print("  MIRROR: by n_live", {k: round(rmse(e, d['n_live']==k), 4) for k in (1,2,3)}, "near_switch", {b: round(rmse(e, d['near_switch']==b),4) for b in (True, False)})
    n_live_s = pres.sum(-1)
    print("    by live Strikes seen", {k: (round(float((n_live_s==k).float().mean()),3), round(rmse(e, n_live_s==k),4)) for k in range(4)})
    ln = lab[:, 3, :2].norm(dim=-1)
    print(f"    label saturated share {float((ln > 0.999).float().mean()):.3f} RMSE {rmse(e, ln > 0.999):.4f}; not {rmse(e, ln <= 0.999):.4f}")
# jitter sensitivity for guard scripts (round 0 rows)
d = load_round("guard", 0, n=200000, seed=5); obs, slot, lab = d["obs"], d["slot"].long(), d["label"]; R = obs.shape[0]; ar = torch.arange(R)
st = V.SLOTS_FROM; pos_idx = [0, 1] + [st + 7*k + j for k in range(8) for j in (0, 1)]
gen = torch.Generator().manual_seed(5)
for sig in (0.001, 0.01):
    o2 = obs.clone(); noise = torch.randn(R, len(pos_idx), generator=gen) * sig
    o2[:, pos_idx] += noise * (o2[:, pos_idx] != 0); o2[:, 0:2] = obs[:, 0:2] + noise[:, 0:2]
    for i, s in enumerate(GUARDS):
        sc = S.make_strategy(s, "guard", cfg, R, "cpu", 0)
        full = torch.zeros(R, 3, OBS_DIM); full[ar, slot] = o2
        l2 = sc.act(full)[ar, slot]
        print(f"jitter {sig}: {s} label RMSE {rmse(l2[:, :2] - lab[:, i, :2]):.4f}")
