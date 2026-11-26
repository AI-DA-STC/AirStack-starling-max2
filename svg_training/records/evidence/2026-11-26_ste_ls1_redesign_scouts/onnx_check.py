"""Scratch (not of record): can the residual's scripts and a routed per-skill net be traced to ONNX opset 17?"""
import io, sys, warnings
from pathlib import Path
import numpy as np, torch
from torch import nn
from torch.nn import functional as F
ROOT = Path.home() / "AirStack-starling-max2-dev/svg_training"
sys.path.insert(0, str(ROOT / "source"))
from svg_training.ste import cells, exploit
from svg_training.core.observations import ObsView, OBS_DIM
torch.set_num_threads(6)
V = ObsView()
TEAMS = {"strike": ["strike_straight", "strike_flank", "strike_high", "strike_low", "strike_sacrifice", "strike_converge"],
         "guard": ["guard_parked_centre", "guard_parked_ring", "guard_mark_edge", "guard_mirror", "guard_field"]}
cfg = exploit.load_game_cfg_file(ROOT / "configs/ste_l011/base.toml")
import onnxruntime as ort

def export(model, args, names):
    buf = io.BytesIO()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        torch.onnx.export(model.eval(), args, buf, input_names=names, output_names=["command"],
                          dynamic_axes={**{n: {0: "B"} for n in names}, "command": {0: "B"}}, opset_version=17)
    return buf.getvalue()

for side, names in TEAMS.items():
    d = torch.load(ROOT / f"runs/2026-11-26_ste_ls11_distil_{side}/data/round_0.pt", map_location="cpu", weights_only=True, mmap=True)
    g = torch.Generator().manual_seed(1)
    idx = torch.randperm(d["obs"].shape[0], generator=g)[:5000].sort().values
    obs, slot = d["obs"][idx].clone(), d["slot"][idx].clone().long()
    z = torch.randint(len(names), (obs.shape[0],), generator=g)
    label = d["label"][idx].clone()
    del d
    orc = cells.ScriptOracle(cfg, side, names, 3, 1)
    with torch.no_grad():
        want = orc(obs, slot, z)
    print("ORC", side, "oracle vs stored labels max", float((want - label[torch.arange(len(z)), z]).abs().max()))
    try:
        raw = export(orc, (obs[:1], slot[:1], z[:1]), ["obs", "slot", "z"])
        sess = ort.InferenceSession(raw, providers=["CPUExecutionProvider"])
        got = sess.run(None, {"obs": obs.numpy(), "slot": slot.numpy(), "z": z.numpy()})[0]
        print(side, "ScriptOracle ONNX export OK; ort vs torch max abs diff", float(np.abs(got - want.numpy()).max()))
    except Exception as e:
        print(side, "ScriptOracle ONNX export FAILED:", type(e).__name__, str(e)[:300])

# routed per-skill nets
class Routed(nn.Module):
    def __init__(self, k):
        super().__init__(); self.k = k
        self.nets = nn.ModuleList([nn.Sequential(nn.Linear(OBS_DIM + 3, 64), nn.ELU(), nn.Linear(64, 4)) for _ in range(k)])
    def forward(self, obs, slot, z):
        x = torch.cat((obs, F.one_hot(slot, 3).to(obs.dtype)), -1)
        out = obs.new_zeros(obs.shape[0], 4)
        for k, m in enumerate(self.nets):
            sel = (z == k).nonzero(as_tuple=True)[0]
            out = out.index_put((sel,), m(x[sel]))
        return out
class AllGather(Routed):
    def forward(self, obs, slot, z):
        x = torch.cat((obs, F.one_hot(slot, 3).to(obs.dtype)), -1)
        every = torch.stack([m(x) for m in self.nets], 1)
        return torch.gather(every, 1, z[:, None, None].expand(-1, 1, 4))[:, 0]
for cls in (Routed, AllGather):
    m = cls(6).eval()
    o = torch.randn(4000, OBS_DIM); s = torch.randint(3, (4000,)); zz = torch.randint(6, (4000,))
    try:
        raw = export(m, (o[:1], s[:1], zz[:1]), ["obs", "slot", "z"])
        sess = ort.InferenceSession(raw, providers=["CPUExecutionProvider"])
        got = sess.run(None, {"obs": o.numpy(), "slot": s.numpy(), "z": zz.numpy()})[0]
        with torch.no_grad(): ref = m(o, s, zz).numpy()
        print(cls.__name__, "ONNX OK; max abs diff", float(np.abs(got - ref).max()))
    except Exception as e:
        print(cls.__name__, "ONNX FAILED:", type(e).__name__, str(e)[:300])
