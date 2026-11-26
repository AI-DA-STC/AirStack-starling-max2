"""Closed forms in the proposed frames, from obs-index features, rotated back; max |diff| against the stored labels.
Strike: zone-line frame h = -p/|p|, s = perp(h) (left). Guard: the marked (mark, mirror) or nearest (field) Strike's radial frame."""
import sys, torch
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from geo import *

def nz(x): return x / x.norm(dim=-1, keepdim=True).clamp(min=1.0)
def back(c, e1, e2): return c[:, 0:1] * e1 + c[:, 1:2] * e2
def rep(name, xy, lab, extra=""):
    print(f"  {name:20s} max|closed form - label| xy {float((xy - lab[:, :2]).abs().max()):.2e} {extra}")

N = 300000
d = load("strike", N, seed=7); obs, sl, lab = d["obs"], d["slot"], d["label"]
p = obs[:, 0:2]; rho = p.norm(dim=-1); h = -p / rho[:, None]; s = perp(h)
Rot = lambda x: torch.stack(((x * h[:, None] if x.dim() == 3 else x * h).sum(-1), (x * s[:, None] if x.dim() == 3 else x * s).sum(-1)), -1)
R0 = 2.6
one = torch.stack((torch.ones_like(rho), torch.zeros_like(rho)), -1) * (rho / 0.25).clamp(max=1)[:, None]   # steer((rho, 0))
print("=== strike (zone-line frame)")
rep("strike_straight", back(one, h, s), lab[:, 0])
# flank: per-Guard (a_k, o_k) in frame; in-way mask; masked nearest; side sign
q, _, pres = slots(obs, 0, PG); fr = Rot(q); a_k, o_k = fr[..., 0], fr[..., 1]
inw = pres & (a_k > 0) & (a_k < rho[:, None]) & (o_k.abs() < CLEAR)
sel = q.norm(dim=-1).masked_fill(~inw, float("inf")).argmin(-1)
a_s, o_s = gat(a_k[..., None], sel)[:, 0], gat(o_k[..., None], sel)[:, 0]
sg = torch.where(o_s >= 0, 1.0, -1.0)
cf = torch.where(inw.any(-1)[:, None], steer(torch.stack((a_s, o_s + CLEAR * sg), -1)), one)
rep("strike_flank", back(cf, h, s), lab[:, 1])
for k, tz in ((2, HI - 0.1), (3, LO + 0.1)):
    v = ((tz - obs[:, 2]) / 0.25).clamp(-1, 1)
    c = one * (1 - v ** 2).clamp(min=0).sqrt()[:, None]
    rep(STRIKE_NAMES[k] if False else ["", "", "strike_high", "strike_low"][k], back(c, h, s), lab[:, k],
        f"vz {float((v - lab[:, k, 2]).abs().max()):.2e}")
# sacrifice
mates, live = team(obs, sl, PG); others = live.sum(-1) >= 2; active = live[:, 0] & others
any_g = pres.any(-1)
nearest = q.norm(dim=-1).masked_fill(~pres, float("inf")).argmin(-1)
decoy = torch.where(any_g[:, None], steer(gat(fr, nearest)), one)
gpz = p[:, None] + q                                                    # Guards rel zone
dr = (gpz - mates[:, 0][:, None]).norm(dim=-1).masked_fill(~pres, float("inf")).argmin(-1)
drawn = gat(gpz, dr); hb = any_g & (drawn.norm(dim=-1) > 0.05)
away = torch.where(hb[:, None], drawn, mates[:, 0]); ra = Rot(-away)
diff = wrap(torch.atan2(ra[:, 1], ra[:, 0]) + PI)                     # bearing of -away minus own bearing
dirn = torch.where(diff >= 0, 1.0, -1.0); rad = (R0 - rho).clamp(-1, 1)
circ = nz(torch.stack((-rad, -dirn), -1))
rest = torch.where((diff.abs() <= PI / 6)[:, None], one, circ)
c = torch.where((sl == 0)[:, None], decoy, rest); c = torch.where(active[:, None], c, one)
rep("strike_sacrifice", back(c, h, s), lab[:, 4])
# converge: own bearing error D (unwrapped, as the script), go, circle bit, pace
_, cc = s_converge(obs, sl)
idx = torch.arange(M); n_live = live.sum(-1)
ref = torch.where(live, idx, M).amin(-1).clamp(max=M - 1); refp = gat(mates, ref)
rp = refp[:, None]
off = torch.atan2(rp[..., 0] * mates[..., 1] - rp[..., 1] * mates[..., 0], (rp * mates).sum(-1))
off = torch.where(off < 0, off + 2 * PI, off).masked_fill(~live, float("inf"))
rank = off.argsort(-1).argsort(-1).float(); target = rank * 2 * PI / n_live.clamp(min=1)[:, None].float()
D = gat(target[..., None], sl)[:, 0] - gat(off.masked_fill(~live, 0.0)[..., None], sl)[:, 0]
err = wrap(target - off.masked_fill(~live, 0.0)); rho_j = mates.norm(dim=-1)
go = ((err.abs() <= 0.1) | ~live).all(-1) | (live & (rho_j < R0 - 0.3)).any(-1)
te = (rho_j - 1.6).clamp(min=0) * live; pace = (gat(te[..., None], sl)[:, 0] / te.amax(-1).clamp(min=1e-9)).clamp(max=1)
cdir = torch.where(D >= 0, 1.0, -1.0); Dw = wrap(D)
place = torch.where((Dw.abs() > 0.5)[:, None], nz(torch.stack((-rad, -cdir), -1)),
                    steer(torch.stack((rho - R0 * Dw.cos(), -R0 * Dw.sin()), -1)))
c = torch.where(go[:, None], torch.stack((pace, torch.zeros_like(pace)), -1), place)
c = torch.where((n_live >= 2)[:, None], c, one)
rep("strike_converge", back(c, h, s), lab[:, 5])
print("  converge: rows where the unwrapped and wrapped direction differ (circle branch, n_live>=2, not go):",
      round(float(((torch.sign(D) != torch.sign(Dw)) & (Dw.abs() > 0.5) & ~go & (n_live >= 2)).float().mean()), 5))

d = load("guard", N, seed=7); obs, sl, lab = d["obs"], d["slot"], d["label"]
p, v = obs[:, 0:2], obs[:, 3:5]
print("=== guard (Strike-anchored radial frames)")
sp, sv, found, pk = marked(obs, sl); e = unit(sp); t = perp(e)
c = steer(torch.stack((1.6 - (p * e).sum(-1), -(p * t).sum(-1)), -1))
rep("guard_mark_edge", back(c, e, t), lab[:, 2])
c = nz(steer(torch.stack((1.92 - (p * e).sum(-1), -(p * t).sum(-1)), -1)) +
       torch.stack((torch.zeros_like(p[:, 0]), (sv * t).sum(-1) / GSPEED), -1))
rep("guard_mirror", back(c, e, t), lab[:, 3])
q, _, spres = slots(obs, PG, PS); n = q.norm(dim=-1).masked_fill(~spres, float("inf")).argmin(-1)
en = unit(p + gat(q, n)); tn = perp(en)
tp, _, tpres = slots(obs, 0, PG); dd = tp.norm(dim=-1).clamp(min=1e-6)
push = -(tp / dd[..., None] * ((1 / dd ** 2 - 1 / 1.21) * (tpres & (dd < 1.1)))[..., None]).sum(1)
c = nz(steer(torch.stack((1.6 - (p * en).sum(-1), -(p * tn).sum(-1)), -1)) + torch.stack(((push * en).sum(-1), (push * tn).sum(-1)), -1))
rep("guard_field", back(c, en, tn), lab[:, 4])
l, _ = g_ring(obs, sl); rep("guard_parked_ring", l[:, :2], lab[:, 1], "(station delta then steer; the script's own computation)")
rep("guard_parked_centre", torch.zeros_like(p), lab[:, 0], f"all 4 channels max {float(lab[:, 0].abs().max())}")
