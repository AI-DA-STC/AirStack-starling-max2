"""Stage 1 joint control arms (LS1_REDESIGN.md 4.3): C-head (one 3x256 trunk on R1 + R2 with the slot one-hot, one
small output head per skill) and C-one (one 3x256 network on R1 + R2 plus the skill-code one-hot), outputs in the
zone-line frame, the [K, 4] mask, the loss and schedule of 3.7, every row labelled with every code.
usage: s1joint.py <tag> <side> head|one [--steps 40000] [--seed 150003]
Writes nets/<tag>.pt (a JointAssembly that flies in the harness) and s1/<tag>.json (row marks per skill)."""
import argparse
import json
import math
import time
from pathlib import Path

import torch
from torch import nn

import lsr

ap = argparse.ArgumentParser()
ap.add_argument("tag"); ap.add_argument("side"); ap.add_argument("shape", choices=["head", "one"])
ap.add_argument("--steps", type=int, default=40000); ap.add_argument("--seed", type=int, default=150003)
a = ap.parse_args()
torch.set_num_threads(6)
HERE = Path(__file__).parent
SK = lsr.SKILLS[a.side]; K = len(SK)


class JointAssembly(nn.Module):
    def __init__(self, side, shape, n_in, mean, std, raw, mask):
        super().__init__()
        self.side, self.shape = side, shape
        self.team, self.skills, self.k, self.team_size = side, tuple(lsr.SKILLS[side]), len(lsr.SKILLS[side]), lsr.M
        self.register_buffer("mean", mean); self.register_buffer("std", std); self.register_buffer("raw", raw)
        self.register_buffer("mask", mask)                                  # [K, 4]
        w = n_in + (self.k if shape == "one" else 0)
        layers = []
        for h in (256, 256, 256):
            layers += [nn.Linear(w, h), nn.ELU()]; w = h
        self.trunk = nn.Sequential(*layers)
        self.head = nn.Linear(256, 3 * (self.k if shape == "head" else 1))

    def every(self, obs, slot):
        """[B, K, 4] raw (unclipped, masked) commands for every code."""
        x, (e1, e2), _ = lsr.features(obs, slot.long(), self.side, self.skills[1], "R2")
        xn = torch.where(self.raw, x, (x - self.mean) / self.std)
        B = x.shape[0]
        if self.shape == "head":
            y = self.head(self.trunk(xn)).reshape(B, self.k, 3)
        else:
            rows = xn.repeat_interleave(self.k, 0)
            code = lsr.onehot(torch.arange(self.k).repeat(B), self.k)
            y = self.head(self.trunk(torch.cat((rows, code), -1))).reshape(B, self.k, 3)
        xy = y[..., 0:1] * e1[:, None] + y[..., 1:2] * e2[:, None]
        out = torch.cat((xy, y[..., 2:3], torch.zeros_like(y[..., 2:3])), -1)
        return out * self.mask[None]

    def forward(self, obs, slot, z, clip=True):
        e = self.every(obs, slot)
        if clip:
            e = e.clamp(-1, 1)
        return (lsr.onehot(z, self.k)[..., None] * e).sum(1) * obs[:, 12:13]

    def all_flat(self, obs):
        n, m = obs.shape[:2]
        rows = obs.reshape(n * m, -1); slot = torch.arange(m).repeat(n)
        with torch.no_grad():
            e = self.every(rows, slot).clamp(-1, 1) * rows[:, 12:13, None]
        return e.reshape(n, m, self.k, 4)


t0 = time.time()
train, held = lsr.load_rows(a.side)
x, _, _ = lsr.feats_chunked(train["obs"], train["slot"], a.side, SK[1], "R2")
mask = torch.stack([lsr.active_mask(train, k) for k in range(K)]).float()
torch.manual_seed(a.seed)
net = JointAssembly(a.side, a.shape, x.shape[1], x.mean(0), x.std(0).clamp(min=0.01), ((x == 0) | (x == 1)).all(0), mask)
del x
opt = torch.optim.Adam(net.parameters(), lr=1e-3)
g = torch.Generator().manual_seed(a.seed)
R = train["obs"].shape[0]; warm = max(1, int(0.02 * a.steps)); n_act = mask.sum(-1).clamp(min=1)
w_row = 1 + (train["flown"][:, None] == torch.arange(K)[None]).float()           # [R, K], own weight 2
print(f"[{a.tag}] C-{a.shape} {a.side}: {R} rows, steps {a.steps}, seed {a.seed}", flush=True)
for st in range(a.steps):
    cur = 1e-3 * (st + 1) / warm if st < warm else 1e-5 + 0.5 * (1e-3 - 1e-5) * (1 + math.cos(math.pi * (st - warm) / max(1, a.steps - warm)))
    for gr in opt.param_groups:
        gr["lr"] = cur
    idx = torch.randint(0, R, (8192,), generator=g)
    out = net.every(train["obs"][idx], train["slot"][idx])
    err = out - train["label"][idx] * mask[None]
    loss = ((w_row[idx] * (err ** 2).sum(-1)) / n_act[None]).mean(0).sum()
    opt.zero_grad(); loss.backward(); opt.step()
    if (st + 1) % 5000 == 0:
        print(f"[{a.tag}] step {st + 1}: loss {float(loss):.3e} ({time.time() - t0:.0f} s)", flush=True)
net.eval().requires_grad_(False)
del train
marks, screens = {}, {}
for k, sk in enumerate(SK):
    if a.side == "guard" and sk == "guard_parked_centre":
        continue
    outs = {}
    for r in (0, 3):
        with torch.no_grad():
            outs[r] = torch.cat([net.every(held[r]["obs"][i:i + 100000], held[r]["slot"][i:i + 100000])[:, k]
                                 for i in range(0, held[r]["obs"].shape[0], 100000)])
    marks[sk] = {str(r): lsr.row_marks(outs[r], held[r], k, sk, mask[k]) for r in (0, 3)}
    screens[sk] = lsr.screen_value(outs[0], outs[3], held, k, mask[k])
    m0 = marks[sk]["0"]
    print(f"[{a.tag}] {sk}: screen {screens[sk]:.4f}; round 0 r5 {[round(v, 4) for v in m0['r5_rmse_debiased']]} "
          f"r7 {[round(v, 4) for v in m0['r7_rmse']]}", flush=True)
torch.save(net, HERE / "nets" / f"{a.tag}.pt")
json.dump({"tag": a.tag, "side": a.side, "shape": a.shape, "seed": a.seed, "steps": a.steps, "marks": marks,
           "screen": screens, "seconds": time.time() - t0}, open(HERE / "s1" / f"{a.tag}.json", "w"), indent=1)
print(f"[{a.tag}] done in {time.time() - t0:.0f} s", flush=True)
