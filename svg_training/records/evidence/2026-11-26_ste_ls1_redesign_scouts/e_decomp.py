# Scratch: split the saved nets' xy error into calibration-like kinds: steady bias, speed scale, turn (angle), rest.
import sys, torch, math
sys.path.insert(0, "<svg_training>/records/evidence/2026-11-26_ste_ls1_fix_diagnosis")
from common import *
torch.set_num_threads(6)
for side, SK in (("guard", GUARDS), ("strike", STRIKES)):
    net, _ = load_net(side)
    d = load_round(side, 3, n=300000, seed=77)  # net-flown rows (round 3)
    a = d["obs"][:, V.alive] > 0.5
    out = net_all(net, d["obs"][a], d["slot"][a].long()); lab = d["label"][a]
    print("==", side, "rows", int(a.sum()))
    for i, s in enumerate(SK):
        o, l = out[:, i, :2].double(), lab[:, i, :2].double(); e = o - l
        bias = e.mean(0)
        ln = l.norm(dim=-1); m = ln > 0.3
        on = o.norm(dim=-1)
        ang = torch.atan2(l[:, 0] * o[:, 1] - l[:, 1] * o[:, 0], (l * o).sum(-1))  # signed angle label->out
        ratio = (on[m] / ln[m])
        # per-skill shares of the MSE: bias part, along-label part, across-label part
        uhat = l / ln.clamp(min=1e-9)[:, None]
        along = (e * uhat).sum(-1); across = e[:, 0] * (-uhat[:, 1]) + e[:, 1] * uhat[:, 0]
        mse = float((e ** 2).sum(-1).mean())
        if not m.any(): print(f"  {s:20s} rmse/ch {math.sqrt(mse/2):.4f} bias {float(bias.norm()):.4f} (no moving labels)"); continue
        print(f"  {s:20s} rmse/ch {math.sqrt(mse/2):.4f}  bias ({float(bias[0]):+.4f},{float(bias[1]):+.4f}) |b| {float(bias.norm()):.4f} share {float((bias**2).sum())/mse:.3f} | "
              f"rows |label|>0.3 {float(m.float().mean()):.2f}: speed ratio mean {float(ratio.mean()):.4f} median {float(ratio.median()):.4f} | "
              f"angle deg mean {math.degrees(float(ang[m].mean())):+.2f} rms {math.degrees(float(ang[m].pow(2).mean().sqrt())):.2f} p50|.| {math.degrees(float(ang[m].abs().median())):.2f} p99|.| {math.degrees(float(ang[m].abs().quantile(.99))):.1f} | "
              f"along-rms {float(along[m].pow(2).mean().sqrt()):.4f} across-rms {float(across[m].pow(2).mean().sqrt()):.4f}")
