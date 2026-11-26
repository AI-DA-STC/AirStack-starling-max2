import io, sys, warnings
from pathlib import Path
import numpy as np, torch
from torch import nn
from torch.nn import functional as F
ROOT = Path.home() / "AirStack-starling-max2-dev/svg_training"
sys.path.insert(0, str(ROOT / "source"))
from svg_training.core.observations import ObsView, OBS_DIM
import onnxruntime as ort
V = ObsView()
class Framed(nn.Module):
    def __init__(self):
        super().__init__(); self.mlp = nn.Sequential(nn.Linear(92 + 3 + 6, 64), nn.ELU(), nn.Linear(64, 4))
        self.register_buffer("mask", torch.ones(6, 4)); self.mask[0] = 0; self.mask[:, 3] = 0
    def forward(self, o, slot, z):
        own = o[:, 0:2]; dz = own.norm(dim=-1, keepdim=True); hd = -own / dz.clamp(min=1e-6)
        side = torch.stack((-hd[:, 1], hd[:, 0]), -1); st = V.SLOTS_FROM; out = [o, dz]
        for k in range(8):
            gg = o[:, st + 7*k: st + 7*k + 2]; pres = o[:, st + 7*k + 6:st + 7*k + 7]
            out += [(gg * hd).sum(-1, keepdim=True) * pres, (gg * side).sum(-1, keepdim=True) * pres]
        out += [hd, side]
        x = torch.cat(out + [F.one_hot(slot, 3).to(o.dtype), F.one_hot(z, 6).to(o.dtype)], -1)
        return self.mlp(x).clamp(-1, 1) * self.mask[z] * o[:, V.alive:V.alive + 1]
m = Framed().eval()
o = torch.randn(4000, OBS_DIM); s = torch.randint(3, (4000,)); zz = torch.randint(6, (4000,))
buf = io.BytesIO()
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    torch.onnx.export(m, (o[:1], s[:1], zz[:1]), buf, input_names=["obs", "slot", "z"], output_names=["command"],
                      dynamic_axes={"obs": {0: "B"}, "slot": {0: "B"}, "z": {0: "B"}, "command": {0: "B"}}, opset_version=17)
sess = ort.InferenceSession(buf.getvalue(), providers=["CPUExecutionProvider"])
got = sess.run(None, {"obs": o.numpy(), "slot": s.numpy(), "z": zz.numpy()})[0]
with torch.no_grad(): ref = m(o, s, zz).numpy()
print("own-frame + mask ONNX OK; max abs diff", float(np.abs(got - ref).max()), "zero rows exact:", bool((got[zz.numpy() == 0] == 0).all()))
