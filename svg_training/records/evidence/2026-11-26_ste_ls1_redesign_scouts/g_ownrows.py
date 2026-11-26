# Scratch: after a 300-step Adam tail at lr 1e-4 (fresh Adam, training rows of rounds 0-3), how much steady bias is left?
import sys, torch, math, copy
sys.path.insert(0, "<svg_training>/records/evidence/2026-11-26_ste_ls1_fix_diagnosis")
from common import *
torch.set_num_threads(6)
for side, SK in (("guard", GUARDS), ("strike", STRIKES)):
    net, _ = load_net(side)
    tr = [load_round(side, r, n=250000, seed=100 + r) for r in range(4)]
    obs = torch.cat([d["obs"] for d in tr]); slot = torch.cat([d["slot"] for d in tr]).long(); lab = torch.cat([d["label"] for d in tr]); del tr
    d = load_round(side, 3, n=300000, seed=77); a = d["obs"][:, V.alive] > 0.5
    eo, es, el = d["obs"][a], d["slot"][a].long(), d["label"][a]; ef = d["flown"][a]
    def show(n, tag):
        out = net_all(n, eo, es)
        print(f"== {side} {tag}")
        for i, s in enumerate(SK):
            e = (out[:, i, :2] - el[:, i, :2]).double(); mse = float((e ** 2).sum(-1).mean()); b = e.mean(0)
            eu = (out[:, i, 2:] - el[:, i, 2:]).double()
            f = ef == i; eo_ = e[f]; mo = float((eo_ ** 2).sum(-1).mean()); bo = eo_.mean(0)
            print(f"  {s:20s} OWN ROWS n {int(f.sum())} xy rmse/ch {math.sqrt(mo/2):.4f} |bias| {float(bo.norm()):.4f} per-ch ({float(bo[0]):+.4f},{float(bo[1]):+.4f}) bias share {float((bo**2).sum())/mo:.3f}")
            print(f"  {s:20s} ALL ROWS xy rmse/ch {math.sqrt(mse/2):.4f} |bias| {float(b.norm()):.4f} bias share {float((b**2).sum())/mse:.3f} | max|out| ch z,yaw {float(out[:, i, 2].abs().max()):.4f},{float(out[:, i, 3].abs().max()):.4f} mean z {float(eu[:,0].mean()):+.4f}")
    show(net, "saved")
    n2 = copy.deepcopy(net); n2.train(); n2.requires_grad_(True); opt = torch.optim.Adam(n2.parameters(), lr=1e-4)
    g = torch.Generator().manual_seed(7); R = obs.shape[0]; k = n2.k
    for st in range(300):
        idx = torch.randint(0, R, (8192,), generator=g)
        out = n2(obs[idx].repeat_interleave(k, 0), slot[idx].repeat_interleave(k), torch.arange(k).repeat(8192), clip=False).reshape(8192, k, 4)
        loss = torch.nn.functional.mse_loss(out, lab[idx]); opt.zero_grad(); loss.backward(); opt.step()
    n2.eval(); n2.requires_grad_(False); show(n2, "after 300 steps Adam lr 1e-4")
