"""Scratch CPU pilot (not of record): one skill alone, raw inputs or a hand-made frame; held-out RMSE (xy)."""
import argparse, time
from common import *
ap = argparse.ArgumentParser()
ap.add_argument("--code", type=int, default=1); ap.add_argument("--hidden", default="256,256,256")
ap.add_argument("--steps", type=int, default=60000); ap.add_argument("--batch", type=int, default=8192)
ap.add_argument("--lr", type=float, default=1e-3); ap.add_argument("--threads", type=int, default=2)
ap.add_argument("--feat", default="raw"); ap.add_argument("--minutes", type=float, default=45)
ap.add_argument("--every", type=int, default=2500); ap.add_argument("--tag", default="")
a = ap.parse_args(); torch.set_num_threads(a.threads); torch.manual_seed(0)
parts = [load_round("strike", r, n=750000, seed=100 + r) for r in (0, 3)]
tr = {k: torch.cat([p[k] for p in parts]) for k in ("obs", "slot", "label")}
te = load_round("strike", 0, n=200000, seed=999)   # round 0 (unweighted, scripts-flown); overlaps train by chance only
def feats(obs):
    if a.feat == "raw": return obs
    own = obs[:, 0:2]; dz = own.norm(dim=-1, keepdim=True); hd = -own / dz.clamp(min=1e-6)
    side = torch.stack((-hd[:, 1], hd[:, 0]), -1); st = V.SLOTS_FROM; out = [obs, dz]
    for k in range(5):
        g = obs[:, st + 7*k: st + 7*k + 2]; pres = obs[:, st + 7*k + 6:st + 7*k + 7]
        out += [(g * hd).sum(-1, keepdim=True) * pres, (g * side).sum(-1, keepdim=True) * pres]
    out += [hd, side]
    return torch.cat(out, -1)
Xtr, Xte = feats(tr["obs"]), feats(te["obs"])
keep = torch.ones(Xtr.shape[1]); keep[[6, 7, 10, 11]] = 0
mean, std = Xtr.mean(0), Xtr.std(0).clamp(min=0.01)
hidden = [int(h) for h in a.hidden.split(",")]; layers, w = [], Xtr.shape[1] + 3
for h in hidden: layers += [torch.nn.Linear(w, h), torch.nn.ELU()]; w = h
layers.append(torch.nn.Linear(w, 4)); mlp = torch.nn.Sequential(*layers)
fwd = lambda x, s: mlp(torch.cat(((x - mean) / std * keep, torch.nn.functional.one_hot(s.long(), 3).float()), -1))
ytr, yte = tr["label"][:, a.code], te["label"][:, a.code]
opt = torch.optim.Adam(mlp.parameters(), lr=a.lr); R = Xtr.shape[0]; gen = torch.Generator().manual_seed(1)
def ev():
    with torch.no_grad(): o = fwd(Xte, te["slot"]).clamp(-1, 1)
    return round(rmse(o[:, :2] - yte[:, :2]), 4)
t0 = time.time(); step = 0
print(f"[{a.tag}] code {STRIKES[a.code]} feat {a.feat} D={Xtr.shape[1]} hidden {hidden}", flush=True)
while step < a.steps and time.time() - t0 < a.minutes * 60:
    idx = torch.randint(R, (a.batch,), generator=gen)
    loss = torch.nn.functional.mse_loss(fwd(Xtr[idx], tr["slot"][idx]), ytr[idx])
    opt.zero_grad(); loss.backward(); opt.step(); step += 1
    if step % a.every == 0: print(f"[{a.tag}] step {step} t {time.time()-t0:.0f}s loss {loss.item():.5f} heldout xy RMSE {ev()}", flush=True)
print(f"[{a.tag}] END step {step} heldout {ev()}", flush=True)
