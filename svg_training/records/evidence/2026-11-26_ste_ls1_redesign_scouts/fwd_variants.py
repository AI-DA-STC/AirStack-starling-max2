"""Scratch timing (not of record): CPU forward cost of skill-network variants, 6 threads."""
import io, statistics, sys, time
from pathlib import Path
import torch
from torch import nn
from torch.nn import functional as F
ROOT = Path.home() / "AirStack-starling-max2-dev/svg_training"
sys.path.insert(0, str(ROOT / "source"))
from svg_training.ste import skill_net, cells, exploit
from svg_training.core.observations import ObsView, OBS_DIM
torch.set_num_threads(6)
V = ObsView()
STRIKES = ["strike_straight", "strike_flank", "strike_high", "strike_low", "strike_sacrifice", "strike_converge"]
K = len(STRIKES)
d = torch.load(ROOT / "runs/2026-11-26_ste_ls11_distil_strike/data/round_0.pt", map_location="cpu", weights_only=True, mmap=True)
B = int(sys.argv[1]) if len(sys.argv) > 1 else 12288
g = torch.Generator().manual_seed(0)
idx = torch.randperm(d["obs"].shape[0], generator=g)[:B].sort().values
obs = d["obs"][idx].clone(); slot = d["slot"][idx].clone().long(); z = torch.randint(K, (B,), generator=g)
del d
cfg = exploit.load_game_cfg_file(ROOT / "configs/ste_l011/base.toml")

def timeit(fn, reps=30, warm=5):
    with torch.no_grad():
        for _ in range(warm): fn()
        ts = []
        for _ in range(reps):
            t = time.perf_counter(); fn(); ts.append(time.perf_counter() - t)
    return statistics.median(ts) * 1000

def mlp(inp, hidden, out):
    layers, w = [], inp
    for h in hidden: layers += [nn.Linear(w, h), nn.ELU()]; w = h
    layers.append(nn.Linear(w, out)); return nn.Sequential(*layers)

net = skill_net.SkillNet("strike", STRIKES, 3, 3, [256]*3, [6,7,10,11]).eval()
res = {}
res["a current 3x256, one code per row"] = timeit(lambda: net(obs, slot, z))
rows_k = obs.repeat_interleave(K, 0); slot_k = slot.repeat_interleave(K); z_k = torch.arange(K).repeat(B)
res["e current 3x256, all codes (B*K rows)"] = timeit(lambda: net(rows_k, slot_k, z_k))

# K separate 3x256 nets (input obs + slot one-hot; no code one-hot)
sep = nn.ModuleList([mlp(OBS_DIM + 3, [256]*3, 4) for _ in range(K)]).eval()
def x_of(o, s): return torch.cat(((o - net.in_mean) / net.in_std * net.keep, F.one_hot(s, 3).float()), -1)
def sep_all_gather():
    x = x_of(obs, slot)
    every = torch.stack([m(x) for m in sep], 1)                      # [B, K, 4]
    return every[torch.arange(B), z].clamp(-1, 1) * obs[:, V.alive:V.alive+1]
res["b K separate 3x256, run all then gather"] = timeit(sep_all_gather)
def sep_routed():
    x = x_of(obs, slot); out = x.new_zeros(B, 4)
    for k, m in enumerate(sep):
        sel = (z == k).nonzero(as_tuple=True)[0]
        if sel.numel(): out[sel] = m(x[sel])
    return out.clamp(-1, 1) * obs[:, V.alive:V.alive+1]
res["c K separate 3x256, rows routed by code"] = timeit(sep_routed)
def sep_all_codes():
    x = x_of(obs, slot); return torch.stack([m(x) for m in sep], 1)
res["e' K separate 3x256, all codes (each net on B rows)"] = timeit(sep_all_codes)
# batched separate nets via bmm on stacked weights, all codes
W = [torch.randn(K, OBS_DIM + 3, 256) * .05, torch.randn(K, 256, 256) * .05, torch.randn(K, 256, 256) * .05, torch.randn(K, 256, 4) * .05]
bs = [torch.zeros(K, 1, 256), torch.zeros(K, 1, 256), torch.zeros(K, 1, 256), torch.zeros(K, 1, 4)]
def sep_bmm_all():
    h = x_of(obs, slot)[None].expand(K, -1, -1)
    for i in range(3): h = F.elu(torch.baddbmm(bs[i], h, W[i]))
    return torch.baddbmm(bs[3], h, W[3])                               # [K, B, 4]
res["e'' K separate 3x256 as one bmm, all codes"] = timeit(sep_bmm_all)

# shared trunk 3x256 + K linear heads (Linear(256, 4K)), gather
trunk = mlp(OBS_DIM + 3, [256]*3, 4 * K).eval()
def trunk_heads():
    out = trunk(x_of(obs, slot)).reshape(B, K, 4)
    return out[torch.arange(B), z].clamp(-1, 1) * obs[:, V.alive:V.alive+1]
res["d shared trunk 3x256 + K linear heads, gather"] = timeit(trunk_heads)
# shared trunk 2x256 + per-skill 1x256 hidden head, all heads then gather
trunk2 = mlp(OBS_DIM + 3, [256]*2, 256).eval()
heads2 = nn.ModuleList([mlp(256, [256], 4) for _ in range(K)]).eval()
def trunk2_heads():
    h = F.elu(trunk2(x_of(obs, slot)))
    every = torch.stack([m(h) for m in heads2], 1)
    return every[torch.arange(B), z]
res["d' trunk 2x256 + K heads (256 hidden each), all then gather"] = timeit(trunk2_heads)

# own-frame features (pilot F2's: zone distance, per other slot along/side, heading, side vector)
def own_frame(o):
    own = o[:, 0:2]; dz = own.norm(dim=-1, keepdim=True); hd = -own / dz.clamp(min=1e-6)
    side = torch.stack((-hd[:, 1], hd[:, 0]), -1); st = V.SLOTS_FROM; out = [o, dz]
    for k in range(8):
        gg = o[:, st + 7*k: st + 7*k + 2]; pres = o[:, st + 7*k + 6:st + 7*k + 7]
        out += [(gg * hd).sum(-1, keepdim=True) * pres, (gg * side).sum(-1, keepdim=True) * pres]
    out += [hd, side]
    return torch.cat(out, -1)
res["f0 own-frame feature computation only (8 slots)"] = timeit(lambda: own_frame(obs))
D2 = own_frame(obs).shape[1]
netf = mlp(D2 + 3 + K, [256]*3, 4).eval()
res["f current 3x256 + own-frame inputs, one code"] = timeit(lambda: netf(torch.cat((own_frame(obs), F.one_hot(slot, 3).float(), F.one_hot(z, K).float()), -1)))

# residual: ScriptOracle forward (K scripts on a team tensor) + current net
orc = cells.ScriptOracle(cfg, "strike", STRIKES, 3, B)
res["g ScriptOracle forward (all K scripts, gather)"] = timeit(lambda: orc(obs, slot, z))
res["g' residual = ScriptOracle + current net"] = timeit(lambda: orc(obs, slot, z, clip=False) + net(obs, slot, z, clip=False))
# structural zero mask
mask = torch.ones(K, 4); mask[:, 3] = 0
res["h current + [K,4] channel mask"] = timeit(lambda: net(obs, slot, z, clip=False) * mask[z])
for k_, v in res.items(): print(f"{v:8.3f} ms  {k_}")
print("B", B, "D own-frame", D2, "threads", torch.get_num_threads())
