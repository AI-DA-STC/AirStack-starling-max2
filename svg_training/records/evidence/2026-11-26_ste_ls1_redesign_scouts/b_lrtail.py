# Scratch: does a short low-lr / decaying-lr Adam tail from the saved LS1.1 net shrink the constant offsets
# (Guard yaw +0.007, parked_centre xy) and the passing skills' RMSE? Copies the net in memory only; writes nothing in the repo.
import sys, os, time, copy, math, torch
sys.path.insert(0, "<svg_training>/records/evidence/2026-11-26_ste_ls1_fix_diagnosis")
from common import *
torch.set_num_threads(6)
side = sys.argv[1]; steps = int(sys.argv[2]); arms = sys.argv[3].split(",")
SK = GUARDS if side == "guard" else STRIKES
net0, p = load_net(side)
# training pool: 250k rows from each round; eval: 200k other rows (round 0 + round 3)
tr = [load_round(side, r, n=250000, seed=100 + r) for r in range(4)]
obs = torch.cat([d["obs"] for d in tr]); slot = torch.cat([d["slot"] for d in tr]).long(); lab = torch.cat([d["label"] for d in tr])
del tr
ev = [load_round(side, r, n=100000, seed=900 + r) for r in (0, 3)]
eobs = torch.cat([d["obs"] for d in ev]); eslot = torch.cat([d["slot"] for d in ev]).long(); elab = torch.cat([d["label"] for d in ev])
alive = eobs[:, V.alive] > 0.5
del ev
def report(net, tag):
    out = net_all(net, eobs, eslot); err = out - elab
    s = [f"{tag:22s}"]
    for i, k in enumerate(SK):
        a = alive
        s.append(f"{k.split('_',1)[1][:8]} xy {rmse(err[a, i, :2]):.4f} z {rmse(err[a, i, 2]):.4f} yaw m{float(out[a, i, 3].mean()):+.4f}")
    if side == "guard":
        pc = out[alive, 0, :3].abs().amax(-1)
        s.append(f"| parked_centre max|xyz| p50 {float(pc.quantile(.5)):.4f} p99 {float(pc.quantile(.99)):.4f} max {float(pc.max()):.4f} share>0.005 {float((pc>0.005).float().mean()):.3f}; |yaw| max {float(out[alive,0,3].abs().max()):.4f}")
    print(" ".join(s), flush=True)
report(net0, "saved net")
for arm in arms:
    net = copy.deepcopy(net0); net.train(); net.requires_grad_(True)
    kind, lr0 = arm.split(":"); lr0 = float(lr0)
    opt = torch.optim.Adam(net.parameters(), lr=lr0)
    g = torch.Generator().manual_seed(7); R = obs.shape[0]; t0 = time.time()
    for st in range(1, steps + 1):
        lr = lr0 if kind == "const" else lr0 * 0.5 * (1 + math.cos(math.pi * (st - 1) / steps)) if kind == "cos" else lr0 * (1 - (st - 1) / steps)
        for gr in opt.param_groups: gr["lr"] = lr
        idx = torch.randint(0, R, (8192,), generator=g)
        k = net.k; o = obs[idx]; sl = slot[idx]
        out = net(o.repeat_interleave(k, 0), sl.repeat_interleave(k), torch.arange(k).repeat(8192), clip=False).reshape(8192, k, 4)
        loss = torch.nn.functional.mse_loss(out, lab[idx])
        opt.zero_grad(); loss.backward(); opt.step()
        if st in (100, 300, steps) or st % 1000 == 0:
            net.eval(); report(net, f"{arm} step {st}"); net.train()
    print(f"  {arm}: {steps} steps in {time.time()-t0:.0f} s", flush=True)
