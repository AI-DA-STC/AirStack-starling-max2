"""Scratch CPU pilot (not of record): fit a skill net on kept rows, log held-out RMSE per skill."""
import argparse, time, math
from common import *
ap = argparse.ArgumentParser()
ap.add_argument("--side", default="strike"); ap.add_argument("--hidden", default="256,256,256")
ap.add_argument("--steps", type=int, default=4000); ap.add_argument("--batch", type=int, default=8192)
ap.add_argument("--lr", type=float, default=1e-3); ap.add_argument("--threads", type=int, default=2)
ap.add_argument("--feat", default="raw"); ap.add_argument("--train", type=int, default=1500000)
ap.add_argument("--zero", default="6,7,10,11"); ap.add_argument("--every", type=int, default=500)
ap.add_argument("--minutes", type=float, default=60); ap.add_argument("--tag", default="")
a = ap.parse_args()
torch.set_num_threads(a.threads); torch.manual_seed(0)
skills = STRIKES if a.side == "strike" else GUARDS
parts = [load_round(a.side, r, n=a.train // 2, seed=100 + r) for r in (0, 3)]
tr = {k: torch.cat([p[k] for p in parts]) for k in ("obs", "slot", "label")}
te = load_round(a.side, 2, n=200000, seed=7)
def feats(obs, slot):
    if a.feat == "raw": return obs
    # R47-like added inputs: own and team-mates' bearing (sin, cos) and distance from the zone centre; guards' too
    own = obs[:, 0:2]; out = [obs]
    def bd(p, present):
        r = p.norm(dim=-1, keepdim=True); u = p / r.clamp(min=1e-6)
        return torch.cat((u, r), -1) * present[:, None]
    out.append(bd(own, torch.ones(obs.shape[0])))
    st = V.SLOTS_FROM
    for k in range(8):
        pres = obs[:, st + 7*k + 6]
        out.append(bd(own + obs[:, st + 7*k: st + 7*k + 2], pres))
    return torch.cat(out, -1)
Xtr, Xte = feats(tr["obs"], tr["slot"]), feats(te["obs"], te["slot"])
D = Xtr.shape[1]
zero = [int(i) for i in a.zero.split(",") if i]
keep = torch.ones(D); keep[zero] = 0
mean, std = Xtr.mean(0), Xtr.std(0).clamp(min=0.01)
M, K = 3, len(skills)
hidden = [int(h) for h in a.hidden.split(",")]
layers, w = [], D + M + K
for h in hidden: layers += [torch.nn.Linear(w, h), torch.nn.ELU()]; w = h
layers.append(torch.nn.Linear(w, 4)); mlp = torch.nn.Sequential(*layers)
def fwd(x, slot, z):
    x = (x - mean) / std * keep
    return mlp(torch.cat((x, torch.nn.functional.one_hot(slot.long(), M).float(), torch.nn.functional.one_hot(z, K).float()), -1))
def expand(x, slot):
    n = x.shape[0]
    return x.repeat_interleave(K, 0), slot.repeat_interleave(K), torch.arange(K).repeat(n)
opt = torch.optim.Adam(mlp.parameters(), lr=a.lr)
R = Xtr.shape[0]; gen = torch.Generator().manual_seed(1)
def evaluate():
    mlp.eval(); errs = []
    with torch.no_grad():
        for s in range(0, Xte.shape[0], 20000):
            x, sl, z = expand(Xte[s:s+20000], te["slot"][s:s+20000])
            o = fwd(x, sl, z).clamp(-1, 1) * Xte[s:s+20000, V.alive].repeat_interleave(K)[:, None]
            errs.append(o.reshape(-1, K, 4) - te["label"][s:s+20000])
    mlp.train(); e = torch.cat(errs)
    return {s[s.index('_')+1:]: round(rmse(e[:, i, :2]), 4) for i, s in enumerate(skills)}
t0 = time.time(); step = 0; order = torch.randperm(R, generator=gen); pos = 0
print(f"[{a.tag}] D={D} hidden={hidden} rows={R} params={sum(p.numel() for p in mlp.parameters())}", flush=True)
while step < a.steps and (time.time() - t0) < a.minutes * 60:
    if pos + a.batch > R: order = torch.randperm(R, generator=gen); pos = 0
    idx = order[pos:pos + a.batch]; pos += a.batch
    x, sl, z = expand(Xtr[idx], tr["slot"][idx])
    loss = torch.nn.functional.mse_loss(fwd(x, sl, z), tr["label"][idx].reshape(-1, 4))
    opt.zero_grad(); loss.backward(); opt.step(); step += 1
    if step % a.every == 0 or step == 1:
        print(f"[{a.tag}] step {step} t {time.time()-t0:.0f}s loss {loss.item():.5f} heldout {evaluate()}", flush=True)
print(f"[{a.tag}] END step {step} t {time.time()-t0:.0f}s heldout {evaluate()}", flush=True)
