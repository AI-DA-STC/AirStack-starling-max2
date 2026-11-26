import io, sys, torch, json
from pathlib import Path
ROOT = Path.home() / "AirStack-starling-max2-dev/svg_training"
sys.path.insert(0, str(ROOT / "source"))
from svg_training.ste import skill_net
from svg_training.core.observations import ObsView, OBS_DIM
V = ObsView()
GUARDS = ["guard_parked_centre", "guard_parked_ring", "guard_mark_edge", "guard_mirror", "guard_field"]
STRIKES = ["strike_straight", "strike_flank", "strike_high", "strike_low", "strike_sacrifice", "strike_converge"]
def run(side): return ROOT / f"runs/2026-11-26_ste_ls11_distil_{side}"
def load_net(side):
    raw = (run(side) / f"skill_net_{side}.pt").read_bytes()
    p = torch.load(io.BytesIO(raw), map_location="cpu", weights_only=True)
    net = skill_net.SkillNet(p["team"], list(p["skills"]), p["team_size"], p["slot_width"], list(p["hidden"]), list(p["zeroed_inputs"]))
    net.load_state_dict(p["state_dict"]); net.eval().requires_grad_(False)
    return net, p
def load_round(side, r, n=None, seed=0):
    d = torch.load(run(side) / f"data/round_{r}.pt", map_location="cpu", weights_only=True)
    if n is not None:
        g = torch.Generator().manual_seed(seed)
        idx = torch.randperm(d["obs"].shape[0], generator=g)[:n].sort().values
        d = {k: (v[idx] if torch.is_tensor(v) and v.dim() > 0 and v.shape[0] == d["obs"].shape[0] else v) for k, v in d.items()}
    return d
def net_all(net, obs, slot, chunk=65536):
    out = []
    k = net.k
    with torch.no_grad():
        for s in range(0, obs.shape[0], chunk):
            o, sl = obs[s:s+chunk], slot[s:s+chunk].long()
            n = o.shape[0]
            rows = o.repeat_interleave(k, 0); ss = sl.repeat_interleave(k); z = torch.arange(k).repeat(n)
            out.append(net(rows, ss, z).reshape(n, k, 4))
    return torch.cat(out)
def rmse(e, mask=None):
    if mask is not None: e = e[mask]
    if e.numel() == 0: return float("nan")
    return float((e.double() ** 2).mean().sqrt())
