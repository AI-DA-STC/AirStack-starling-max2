from common import *
import os, math
os.chdir(ROOT)
torch.set_num_threads(6)
from svg_training.ste import distil, exploit
from svg_training.opponents import scripted as S
g = distil.load_distil_gates("configs/ste_ls1/distil_gates.toml")
cfg = exploit.variant_cfg(g.skills_gates, "base")
net, p = load_net("strike")
d = load_round("strike", 0, n=300000, seed=11)
obs, slot, lab = d["obs"], d["slot"].long(), d["label"]
R = obs.shape[0]; M = 3; ar = torch.arange(R)
out = net_all(net, obs, slot)
full = torch.zeros(R, M, OBS_DIM); full[ar, slot] = obs
def pick(t): return t[ar, slot]
# ---- sacrifice branches (recomputed with the script's own code path)
own_p = obs[:, 0:2]
mates, live = S._team_slots(full, cfg.pad_guards); mates, live = pick(mates), pick(live)
decoy_live = live[:, 0]; others_live = live.sum(-1) >= 2
gp, _, gpres = S._slots(full, 0, cfg.pad_guards); gp, gpres = pick(gp), pick(gpres)
any_guard = gpres.any(-1)
guard_p = own_p[:, None, :] + gp
to_decoy = (guard_p - mates[:, 0][:, None, :]).norm(dim=-1).masked_fill(~gpres, float("inf"))
drawn = guard_p[ar, to_decoy.argmin(-1)]
has_b = any_guard & (drawn.norm(dim=-1) > S.SACRIFICE_NO_BEARING_M)
away = torch.where(has_b[:, None], drawn, mates[:, 0])
far = torch.atan2(-away[:, 1], -away[:, 0])
diff = S._wrap(far - torch.atan2(own_p[:, 1], own_p[:, 0]))
go_in = diff.abs() <= S.ENTRY_HALF_ANGLE_RAD
team_ok = decoy_live & others_live
is_decoy = slot == 0
e = out[:, 4, :2] - lab[:, 4, :2]
br = {"fallback straight (decoy out or alone)": ~team_ok, "decoy (slot 0) at nearest guard": team_ok & is_decoy,
      "others: circling": team_ok & ~is_decoy & ~go_in, "others: straight in (gap)": team_ok & ~is_decoy & go_in}
print("SACRIFICE branches: share, RMSE, share of MSE")
tot = float((e**2).sum())
for k, m in br.items():
    print(f"  {k:42s} {float(m.float().mean()):.3f}  {rmse(e, m):.4f}  {float((e[m]**2).sum())/tot:.3f}")
m = team_ok & ~is_decoy
for lo, hi in ((0, 0.02), (0.02, 0.1), (0.1, 0.3), (0.3, 4)):
    mm = m & ((diff.abs() - S.ENTRY_HALF_ANGLE_RAD).abs() >= lo) & ((diff.abs() - S.ENTRY_HALF_ANGLE_RAD).abs() < hi)
    print(f"   others, |angle to entry edge| {lo}-{hi} rad: share {float(mm.float().mean()):.3f} RMSE {rmse(e, mm):.4f}")
mm = m & ((math.pi - diff.abs()) < 0.1)
print(f"   others, within 0.1 rad of the +-pi direction flip: share {float(mm.float().mean()):.3f} RMSE {rmse(e, mm):.4f}")
# decoy: nearest guard switches (gap between nearest two guard distances)
dist = gp.norm(dim=-1).masked_fill(~gpres, float("inf")); ds = dist.sort(-1).values
gap = ds[:, 1] - ds[:, 0]
for lo, hi in ((0, 0.05), (0.05, 0.2), (0.2, 99)):
    mm = team_ok & is_decoy & (gap >= lo) & (gap < hi)
    print(f"   decoy, gap between nearest two guards {lo}-{hi} m: share {float(mm.float().mean()):.3f} RMSE {rmse(e, mm):.4f}")
# drawn guard switches for the others (gap between nearest two guards to strike 0)
td = to_decoy.sort(-1).values; gap2 = td[:, 1] - td[:, 0]
for lo, hi in ((0, 0.05), (0.05, 0.2), (0.2, 99)):
    mm = m & (gap2 >= lo) & (gap2 < hi)
    print(f"   others, gap between two guards nearest Strike 0 {lo}-{hi} m: share {float(mm.float().mean()):.3f} RMSE {rmse(e, mm):.4f}")
# ---- converge branches
e = out[:, 5, :2] - lab[:, 5, :2]; tot = float((e**2).sum())
s = M
n_live = live.sum(-1)
idx = torch.arange(s)
ref = torch.where(live, idx, s).amin(-1).clamp(max=s - 1)
ref_p = mates[ar, ref]
rp = ref_p[:, None, :]
cross = rp[..., 0] * mates[..., 1] - rp[..., 1] * mates[..., 0]; dot = (rp * mates).sum(-1)
offset = torch.atan2(cross, dot); offset = torch.where(offset < 0, offset + 2 * math.pi, offset).masked_fill(~live, float("inf"))
rank = offset.argsort(-1).argsort(-1).float()
target = rank * 2 * math.pi / n_live.clamp(min=1)[:, None].float()
err = S._wrap(target - offset.masked_fill(~live, 0.0))
radius = S._stand_off_m(full, cfg.arena.wall_margin_m); radius = pick(radius)
rho = mates.norm(dim=-1)
committed = (live & (rho < radius - S.RUN_IN_COMMIT_M)).any(-1)
gathered = ((err.abs() <= S.GATHER_ANGLE_RAD) | ~live).all(-1)
go = gathered | committed
own = idx[None, :] == slot[:, None]
own_off = (offset.masked_fill(~live, 0.0) * own).sum(-1); own_t = (target * own).sum(-1)
dd = own_t - own_off
circ = S._wrap(dd).abs() > S.CIRCLE_UNTIL_RAD
br = {"alone (straight)": n_live < 2, "run-in, committed": (n_live >= 2) & committed,
      "run-in, gathered not committed": (n_live >= 2) & gathered & ~committed,
      "placing: circling": (n_live >= 2) & ~go & circ, "placing: steer to point": (n_live >= 2) & ~go & ~circ}
print("\nCONVERGE branches: share, RMSE, share of MSE")
for k, m in br.items():
    print(f"  {k:42s} {float(m.float().mean()):.3f}  {rmse(e, m):.4f}  {float((e[m]**2).sum())/tot:.3f}")
maxerr = err.abs().masked_fill(~live, 0).amax(-1)
for lo, hi in ((0, 0.08), (0.08, 0.12), (0.12, 0.3), (0.3, 9)):
    mm = (n_live >= 2) & ~committed & (maxerr >= lo) & (maxerr < hi)
    print(f"   not committed, worst mate bearing error {lo}-{hi} rad (gate at 0.1): share {float(mm.float().mean()):.3f} RMSE {rmse(e, mm):.4f}")
for k in (2, 3):
    for name, m in br.items():
        mm = m & (n_live == k)
        if mm.any(): print(f"   n_live {k} {name:40s} share {float(mm.float().mean()):.3f} RMSE {rmse(e, mm):.4f}")
# near rank ties (a mate's offset near 0 / 2pi relative to reference)
o2 = offset.masked_fill(~live, 1.0).masked_fill(idx[None, :] == ref[:, None], 1.0)
near_wrap = (n_live >= 2) & ((o2 < 0.1) | (o2 > 2 * math.pi - 0.1)).any(-1)
print(f"   a mate within 0.1 rad of the reference bearing (rank wrap): share {float(near_wrap.float().mean()):.3f} RMSE {rmse(e, near_wrap):.4f}")
