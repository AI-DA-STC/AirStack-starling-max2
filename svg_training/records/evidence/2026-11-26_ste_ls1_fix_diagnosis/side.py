from common import *
import os
os.chdir(ROOT); torch.set_num_threads(2)
from svg_training.opponents.scripted import steer, _unit
net, p = load_net("strike")
d = load_round("strike", 0, n=300000, seed=11)
obs, slot, lab = d["obs"], d["slot"].long(), d["label"]; R = obs.shape[0]; ar = torch.arange(R)
out = net_all(net, obs, slot)
own = obs[:, 0:2]; dz = own.norm(dim=-1, keepdim=True); hd = _unit(-own); side = torch.stack((-hd[:, 1], hd[:, 0]), -1)
st = V.SLOTS_FROM
rp = torch.stack([obs[:, st + 7*k: st + 7*k + 2] for k in range(5)], 1); pres = torch.stack([obs[:, st + 7*k + 6] > 0.5 for k in range(5)], 1)
clear = 1.1 + 0.3
along = (rp * hd[:, None]).sum(-1); off_all = (rp * side[:, None]).sum(-1)
in_way = pres & (along > 0) & (along < dz) & (off_all.abs() < clear); blocked = in_way.any(-1)
near = rp.norm(dim=-1).masked_fill(~in_way, float("inf")).argmin(-1); gsel = rp[ar, near]
off = (gsel * side).sum(-1, keepdim=True); sign = torch.where(off >= 0, 1.0, -1.0)
mirror = steer(gsel - side * sign * clear)
true = lab[:, 1, :2]
assert float((steer(gsel + side * sign * clear)[blocked] - true[blocked]).abs().max()) < 1e-5
dl = (out[:, 1, :2] - true).norm(dim=-1); dm = (out[:, 1, :2] - mirror).norm(dim=-1)
ao = off.abs()[:, 0]
print("blocked rows: share where the net is closer to the MIRRORED side's command than to the label:")
for lo, hi in ((0, 0.01), (0.01, 0.05), (0.05, 0.2), (0.2, 0.5), (0.5, 9)):
    m = blocked & (ao >= lo) & (ao < hi)
    print(f"  |off| [{lo},{hi}) rows {float(m.sum())/float(blocked.sum()):.3f}  closer-to-mirror {float((dm[m] < dl[m]).float().mean()):.3f}  flank RMSE {rmse(out[m,1,:2]-true[m]):.4f}")
m = blocked
print(f"  all blocked: closer-to-mirror {float((dm[m] < dl[m]).float().mean()):.3f}; RMSE(label, mirrored label) {rmse(true[m]-mirror[m]):.4f}")
# angle error of net vs label on blocked rows
ang = torch.atan2(out[:,1,1], out[:,1,0]) - torch.atan2(true[:,1], true[:,0]); ang = torch.atan2(ang.sin(), ang.cos()).abs()
print("  blocked: median |angle error| deg %.1f, p90 %.1f" % (float(ang[m].median())*57.3, float(ang[m].quantile(0.9))*57.3))
