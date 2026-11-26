"""Open-loop check of blend.py on held-out rows: w -> 0 equals the exact closed form (and the labels); per w the RMSE
and the tail share (max-channel |blend - label| > 0.1) on the skill's own held-out rows (r6 input)."""
import torch

import blend
import geo

torch.manual_seed(0)
for side, skills in (("strike", ("strike_flank", "strike_sacrifice", "strike_converge")), ("guard", ("guard_field",))):
    d = torch.load(geo.ROOT / f"runs/2026-11-26_ste_ls11_distil_{side}/data/round_0.pt", weights_only=True)
    held = d["game"] % 5 == 0
    names = list((geo.GUARD if side == "guard" else geo.STRIKE).keys())
    for sk in skills:
        k = names.index(sk)
        rows = torch.nonzero(held & (d["flown"] == k)).squeeze(1)
        rows = rows[torch.randperm(rows.numel())[:200000]]
        obs, sl, lab = d["obs"][rows], d["slot"][rows], d["label"][rows, k]
        exact = blend.FUNCS[sk](obs, sl, 0.0)
        tiny = blend.FUNCS[sk](obs, sl, 1e-7)
        print(f"{sk}: {rows.numel()} own held-out rows; exact vs label max {float((exact - lab).abs().max()):.2e}; "
              f"w=1e-7 vs exact max {float((tiny - exact).abs().max()):.2e} "
              f"(rows > 1e-3: {int(((tiny - exact).abs().amax(-1) > 1e-3).sum())})", flush=True)
        for w in (0.01, 0.03, 0.10):
            b = blend.FUNCS[sk](obs, sl, w)
            e = (b - lab)
            print(f"   w {w*100:.0f} cm: RMSE xy {float(e[:, :2].pow(2).mean().sqrt()):.4f}; "
                  f"tail share >0.1 {float((e.abs().amax(-1) > 0.1).float().mean()):.5f}; "
                  f"rows changed >1e-3 {float((e.abs().amax(-1) > 1e-3).float().mean()):.4f}", flush=True)
