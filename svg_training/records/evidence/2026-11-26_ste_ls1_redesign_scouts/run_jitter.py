"""Verify the re-written scripts against the stored labels; then jitter: full change vs choices-held change, per choice."""
import sys, torch
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from geo import *

N = int(sys.argv[1]) if len(sys.argv) > 1 else 300000
def rms(x): return float((x.double() ** 2).mean().sqrt()) if x.numel() else float("nan")
for side, fns in (("guard", GUARD), ("strike", STRIKE)):
    d = load(side, N, seed=7); obs, sl, lab = d["obs"], d["slot"], d["label"]
    print(f"=== {side}: {obs.shape[0]} rows of round_0; consts obs8 {obs[:,8].unique().tolist()} obs9 {obs[:,9].unique().tolist()} "
          f"obs69/70 max|.| {float(obs[:,69:71].abs().max())}; alive min {float(obs[:,12].min())}")
    for k, (name, f) in enumerate(fns.items()):
        l0, c0 = f(obs, sl)
        err = float((l0 - lab[:, k]).abs().max())
        vzmax, yawmax = float(lab[:, k, 2].abs().max()), float(lab[:, k, 3].abs().max())
        fl = d["flown"] == k
        print(f"--- {name}: verify max|mine-stored| {err:.2e}; label max|vz| {vzmax:.3g} max|yaw| {yawmax:.3g}; flown share {float(fl.float().mean()):.3f}")
        keys = [c for c in c0 if c not in ("diff", "maxerr", "minrho", "n_live", "pace", "go")]
        for delta in (0.001, 0.01):
            gen = torch.Generator().manual_seed(11)
            oj = jitter(obs, delta, gen, z=True, vel=(name == "guard_mirror"))
            l1, c1 = f(oj, sl)
            dfull = (l1 - l0)[:, :3].norm(dim=-1)
            line = f"  delta {delta*1000:.0f} mm: full RMS {rms((l1-l0)[:, :3]) :.4f} (per-channel RMS over 3 ch)"
            if keys:
                l2, _ = f(oj, sl, c0)
                line += f", choices held {rms((l2-l0)[:, :3]):.4f}"
                dc = diffch(c0, c1, keys)
                anyc = torch.zeros_like(dfull, dtype=torch.bool)
                for c in keys: anyc |= dc[c]
                line += f"; rows with any choice flipped {float(anyc.float().mean()):.4f}"
                print(line)
                jump = (l1 - l2)[:, :3].norm(dim=-1)
                tot = float((dfull.double() ** 2).sum())
                for c in keys:
                    only = dc[c] & (sum(dc[o].int() for o in keys) == 1)
                    jj = jump[only & (jump > 1e-6)]
                    share_sq = float((dfull[dc[c]].double() ** 2).sum()) / max(tot, 1e-30)
                    q = jj.quantile(torch.tensor([0.1, 0.5, 0.9])).tolist() if jj.numel() > 2 else []
                    print(f"     {c:12s} flipped {float(dc[c].float().mean()):.5f} of rows (flown rows {float(dc[c][fl].float().mean()):.5f}); "
                          f"share of sq change {share_sq:.3f}; jump |dlabel| p10/p50/p90 {[round(x,3) for x in q]} (n={jj.numel()})")
            else:
                print(line)
