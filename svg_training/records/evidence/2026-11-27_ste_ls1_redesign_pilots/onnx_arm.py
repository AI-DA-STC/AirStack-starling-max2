"""Stage 2 onnxruntime-flown arm (INFO; LS1_REDESIGN.md 4.4): the exported pilot assembly (opset 17) flies the screen
cells of <side>; reported: games that differ from the torch-flown assembly, per cell (> 3 in any cell: investigate).
usage: onnx_arm.py <name> <side> <skill>=<fit tag> [...]"""
import io
import json
import sys
import warnings
from pathlib import Path

import numpy as np
import onnxruntime as ort
import torch

import lsr
import stage2
from harness import ctx_of, net_batches, cells, eq

torch.set_num_threads(6)
HERE = Path(__file__).parent
name, side, specs = sys.argv[1], sys.argv[2], sys.argv[3:]
parts = {}
for spec in specs:
    sk, tag = spec.split("=")
    parts[sk] = (torch.load(HERE / "nets" / f"{tag}.pt", weights_only=False), json.loads((HERE / "s1" / f"{tag}.json").read_text())["rung"])
asm = lsr.Assembly(side, parts).eval()
ctx = ctx_of(side)
_, held = lsr.load_rows(side, n_train=1)
obs = held[0]["obs"][:64].contiguous(); sl = held[0]["slot"][:64].long(); z = torch.zeros(64, dtype=torch.long)
buf = io.BytesIO()
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    torch.onnx.export(asm, (obs, sl, z), buf, input_names=["obs", "slot", "z"], output_names=["command"],
                      dynamic_axes={"obs": {0: "B"}, "slot": {0: "B"}, "z": {0: "B"}, "command": {0: "B"}},
                      opset_version=17)
sess = ort.InferenceSession(buf.getvalue(), providers=["CPUExecutionProvider"])


class OrtNet(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.team, self.skills, self.k, self.team_size = asm.team, asm.skills, asm.k, asm.team_size

    def forward(self, o, s, zz, clip=True):
        out = sess.run(None, {"obs": o.float().numpy(), "slot": s.long().numpy(), "z": zz.long().numpy()})[0]
        return torch.from_numpy(out)


scr = set(stage2.screen_cells(side))
bs = [b for b in net_batches(ctx, info=False) if any(stage2.key(c.choice["flies"], c.opponent) in scr for c in b.cells)]
reader = eq.Reader(ctx, eq.plan_batches(ctx))
res = []
for b in bs:
    pgs = {}
    for label, net in (("torch", asm), ("ort", OrtNet())):
        ctx.net, ctx.net_sha = net, "pilot"
        pgs[label] = eq.play_batch(ctx, b, reader, None, lambda: False)
    for i, c in enumerate(b.cells):
        if stage2.key(c.choice["flies"], c.opponent) not in scr:
            continue
        a = eq.exploit.slice_cell(pgs["torch"], i, ctx.n); o = eq.exploit.slice_cell(pgs["ort"], i, ctx.n)
        differ = int(np.sum(np.asarray(a["outcome"]) != np.asarray(o["outcome"])))
        res.append({"codes": list(c.choice["flies"]), "opponent": c.opponent, "outcome_differs": differ})
        print(f"  {','.join(c.choice['flies'])} v {c.opponent}: outcomes differ in {differ} games", flush=True)
worst = max(r["outcome_differs"] for r in res)
print(f"[{name}] onnxruntime arm {side}: {len(res)} screen cells; largest {worst} games differ -> "
      f"{'investigate (> 3)' if worst > 3 else 'ok'}", flush=True)
json.dump(res, open(HERE / "s2" / f"{name}.json", "w"), indent=1)
print("done")
