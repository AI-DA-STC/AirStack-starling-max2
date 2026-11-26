"""Stage 0b (LS1_REDESIGN.md 4.2, INFO, calibration, no mark): the saved LS1.1 network of <side> gets a 300-step
fresh-Adam tail at lr 1e-4 (batch 8192, all codes, rows from every round of the training games, game % 5 != 0) and a
post-hoc [K, 4] output mask (channels whose labels are ever non-zero), then plays every T94 network batch (gated and
info cells). Reports row RMSE per skill (held-out games, rounds 0 and 3) and changed games per cell beside T94's.
usage: s0b.py <side>"""
import copy
import json
import sys
import time
from pathlib import Path

import torch

sys.path.insert(0, str(Path.home() / "AirStack-starling-max2-dev/svg_training/records/evidence/2026-11-26_ste_ls1_fix_diagnosis"))
from common import load_net, run, net_all, rmse, V  # noqa: E402
from harness import ctx_of, net_batches, check_layout, replay, t94_rows, cells  # noqa: E402

torch.set_num_threads(6)
side = sys.argv[1]
net0, _ = load_net(side)
K = net0.k
data = [torch.load(run(side) / f"data/round_{r}.pt", map_location="cpu", weights_only=True) for r in range(4)]
train = {k: torch.cat([d[k][d["game"] % 5 != 0] for d in data]) for k in ("obs", "slot", "label")}
held = {r: {k: data[r][k][data[r]["game"] % 5 == 0] for k in ("obs", "slot", "label", "flown")} for r in (0, 3)}
mask = torch.stack([d["label"].abs().amax(0) for d in data]).amax(0) > 0          # [K, 4]
print(f"{side}: {train['obs'].shape[0]} training rows; mask {mask.int().tolist()}", flush=True)
del data


class Masked(torch.nn.Module):
    def __init__(self, net, mask):
        super().__init__()
        self.net, self.mask = net, mask.float()
        self.team, self.skills, self.k, self.team_size = net.team, net.skills, net.k, net.team_size

    def forward(self, obs, slot, z, clip=True):
        return self.net(obs, slot, z, clip=clip) * self.mask[z]


def row_report(net, tag):
    for r in (0, 3):
        h = held[r]; out = net_all(net, h["obs"], h["slot"]); err = out - h["label"]
        alive = h["obs"][:, V.alive] > 0.5
        parts = []
        for k in range(K):
            own = alive & (h["flown"] == k)
            parts.append(f"{net.skills[k].split('_', 1)[1][:9]} {rmse(err[own, k]):.4f}")
        print(f"  {tag} round {r} own-row RMSE (4 ch): " + ", ".join(parts), flush=True)


row_report(net0, "saved")
net = copy.deepcopy(net0); net.train(); net.requires_grad_(True)
opt = torch.optim.Adam(net.parameters(), lr=1e-4)
g = torch.Generator().manual_seed(150001); R = train["obs"].shape[0]; t0 = time.time()
for st in range(300):
    idx = torch.randint(0, R, (8192,), generator=g)
    o, sl = train["obs"][idx], train["slot"][idx].long()
    out = net(o.repeat_interleave(K, 0), sl.repeat_interleave(K), torch.arange(K).repeat(8192), clip=False)
    loss = torch.nn.functional.mse_loss(out.reshape(8192, K, 4), train["label"][idx])
    opt.zero_grad(); loss.backward(); opt.step()
net.eval().requires_grad_(False)
print(f"  tail: 300 steps in {time.time() - t0:.0f} s, last loss {float(loss):.3e}", flush=True)
masked = Masked(net, mask)
row_report(masked, "tail+mask")
del train

ctx = ctx_of(side)
bs = net_batches(ctx)
check_layout(ctx, bs)
rows = replay(ctx, masked, bs)
t94 = t94_rows(side)
for r in rows:
    r["t94_flips"] = t94[(r["kind"], tuple(r["codes"]), r["opponent"])]["flips"]
gated = [r for r in rows if r["kind"] != cells.INFO]
over = lambda rs, key: sum(x[key] > 30 for x in rs)
wide = sum(not (-0.045 <= x["ci"][0] and x["ci"][1] <= 0.045) for x in gated)
print(f"== {side}: {len(gated)} gated cells: over 30 now {over(gated, 'flips')} (T94 {over(gated, 't94_flips')}); "
      f"interval outside +-0.045: {wide}; median {sorted(x['flips'] for x in gated)[len(gated) // 2]} "
      f"(T94 {sorted(x['t94_flips'] for x in gated)[len(gated) // 2]}); max {max(x['flips'] for x in gated)}", flush=True)
for r in sorted(gated, key=lambda x: -x["flips"])[:15]:
    print(f"   {r['flips']:4d} (T94 {r['t94_flips']:4d})  {','.join(r['codes'])} v {r['opponent']}", flush=True)
json.dump({"mask": mask.int().tolist(), "rows": rows}, open(Path(__file__).parent / f"s0b_{side}.json", "w"), indent=1)
print("done")
