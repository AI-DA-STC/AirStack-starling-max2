"""Scratch (not of record): the 11 scripts re-written per row with their discrete choices exposed, so that a jitter can
be split into the jump part (a choice flips) and the smooth part (choices held). Rows from round_0.pt (script-flown)."""
import math, sys, json, torch
from pathlib import Path
ROOT = Path.home() / "AirStack-starling-max2-dev/svg_training"
sys.path.insert(0, str(ROOT / "source"))
from svg_training.ste import exploit
torch.set_num_threads(6)
CFG = exploit.load_game_cfg_file(ROOT / "configs/ste_l011/base.toml")
PG, PS, M = CFG.pad_guards, CFG.pad_strikes, 3
CLEAR = CFG.rules.keepout_strike_m + 0.3
GSPEED = CFG.team_speed_mps("guard")
LO, HI = CFG.arena.height_band_m
WALL = CFG.arena.wall_margin_m
PI = math.pi


def unit(v): return v / v.norm(dim=-1, keepdim=True).clamp(min=1e-9)
def steer(d):
    n = d.norm(dim=-1, keepdim=True); return d / n.clamp(min=1e-9) * (n / 0.25).clamp(max=1.0)
def wrap(a): return torch.atan2(a.sin(), a.cos())
def perp(v): return torch.stack((-v[..., 1], v[..., 0]), -1)
def slot(obs, k):
    s = obs[:, 13 + 7 * k: 20 + 7 * k]; return s[:, 0:2], s[:, 3:5], s[:, 6] > 0.5
def slots(obs, first, count):
    s = obs[:, 13 + 7 * first: 13 + 7 * (first + count)].reshape(-1, count, 7); return s[..., 0:2], s[..., 3:5], s[..., 6] > 0.5
def gat(x, idx): return torch.gather(x, 1, idx[:, None, None].expand(-1, 1, x.shape[-1]))[:, 0]
def z4(xy, obs, vz=None):
    vz = torch.zeros_like(xy[:, :1]) if vz is None else vz[:, None]
    return torch.cat((xy, vz, torch.zeros_like(xy[:, :1])), -1) * obs[:, 12:13]
def circle(own, R, d):
    rho = own.norm(dim=-1, keepdim=True); er = unit(own); et = perp(er)
    a = et * d[:, None] + er * ((R - rho) / 1.0).clamp(-1, 1); return a / a.norm(dim=-1, keepdim=True).clamp(min=1.0)
def stand_off(obs):
    return torch.minimum(obs[:, 8:9] + 1.0, obs[:, 9:10] - WALL - obs[:, 69:71].abs().amax(-1, keepdim=True))
def team(obs, sl, first):
    """[B,3,2] team positions rel zone, [B,3] live (self included)."""
    rp, _, pres = slots(obs, first, M); own = obs[:, 0:2]
    eye = torch.nn.functional.one_hot(sl, M).bool()
    pos = own[:, None] + rp * (~eye)[..., None]
    return pos, torch.where(eye, (obs[:, 12] > 0.5)[:, None].expand(-1, M), pres)


# ------------------------------------------------------------------ Guard
def marked(obs, sl):
    rp, rv, pres = slots(obs, PG, PS); own, ov = obs[:, 0:2], obs[:, 3:5]
    n = pres.sum(-1); rank = sl % n.clamp(min=1)
    pick = pres & ((pres.cumsum(-1) - 1) == rank[:, None]); w = pick.float()[..., None]
    return own + (rp * w).sum(1), ov + (rv * w).sum(1), n > 0, pick.float().argmax(-1)

def g_centre(obs, sl, ch=None): return torch.zeros(obs.shape[0], 4), {}
def g_mark(obs, sl, ch=None):
    sp, _, f, pk = marked(obs, sl); return z4(steer(unit(sp) * obs[:, 8:9] - obs[:, 0:2]) * f[:, None], obs), {"pick": pk}
def g_mirror(obs, sl, ch=None):
    sp, sv, f, pk = marked(obs, sl); er = unit(sp)
    vt = sv - (sv * er).sum(-1, keepdim=True) * er
    a = steer(er * obs[:, 8:9] * 1.2 - obs[:, 0:2]) + vt / GSPEED; a = a / a.norm(dim=-1, keepdim=True).clamp(min=1.0)
    return z4(a * f[:, None], obs), {"pick": pk}
def g_field(obs, sl, ch=None):
    own = obs[:, 0:2]; rp, _, pres = slots(obs, PG, PS)
    dist = rp.norm(dim=-1).masked_fill(~pres, float("inf")); near = dist.argmin(-1) if ch is None else ch["near"]
    found = pres.any(-1); rel = gat(rp, near)
    pull = steer(unit(own + rel) * obs[:, 8:9] - own) * found[:, None]
    tp, _, tpres = slots(obs, 0, PG); d = tp.norm(dim=-1).clamp(min=1e-6)
    mag = (1 / d ** 2 - 1 / 1.1 ** 2) * (tpres & (d < 1.1))
    a = pull - (tp / d[..., None] * mag[..., None]).sum(1); a = a / a.norm(dim=-1, keepdim=True).clamp(min=1.0)
    return z4(a, obs), {"near": near}
def g_ring(obs, sl, ch=None):
    own = obs[:, 0:2]; mates, live = team(obs, sl, 0); idx = torch.arange(M)
    n_live = live.sum(-1); step = 2 * PI / M
    ref = torch.where(live, idx, M).amin(-1).clamp(max=M - 1); refp = gat(mates, ref)
    rp = refp[:, None]
    off = torch.atan2(rp[..., 0] * mates[..., 1] - rp[..., 1] * mates[..., 0], (rp * mates).sum(-1))
    off = torch.where(off < 0, off + 2 * PI, off).masked_fill(~live, float("inf"))
    rank = off.argsort(dim=-1, stable=True).argsort(dim=-1)
    own_rank = gat(rank[..., None].float(), sl)[:, 0] if ch is None else ch["rank"]
    ordered = torch.atan2(refp[:, 1], refp[:, 0]) + own_rank * step
    th = torch.atan2(mates[..., 1], mates[..., 0]); w = live.float()
    phase = torch.atan2((w * (M * th).sin()).sum(-1), (w * (M * th).cos()).sum(-1)) / M
    oth = torch.atan2(own[:, 1], own[:, 0])
    mm = torch.round(wrap(oth - phase) / step) if ch is None else ch["m"]
    want = torch.where(n_live >= M, ordered, phase + mm * step)
    r = 0.8  # ring_radius_m(3) = max(0.8, 1.15 / (2 sin(pi/3)) = 0.664)
    return z4(steer(r * torch.stack((want.cos(), want.sin()), -1) - own), obs), {"rank": own_rank, "m": mm}

GUARD = {"guard_parked_centre": g_centre, "guard_parked_ring": g_ring, "guard_mark_edge": g_mark,
         "guard_mirror": g_mirror, "guard_field": g_field}


# ------------------------------------------------------------------ Strike
def s_straight(obs, sl, ch=None): return z4(steer(-obs[:, 0:2]), obs), {}
def s_height(top):
    tz = HI - 0.1 if top else LO + 0.1
    def f(obs, sl, ch=None):
        vz = ((tz - obs[:, 2]) / 0.25).clamp(-1, 1); xy = steer(-obs[:, 0:2]) * (1 - vz ** 2).clamp(min=0).sqrt()[:, None]
        return z4(xy, obs, vz), {}
    return f
def flank_parts(obs):
    own = obs[:, 0:2]; tz = -own; dz = tz.norm(dim=-1, keepdim=True); hd = unit(tz); sd = perp(hd)
    rp, _, pres = slots(obs, 0, PG)
    along = (rp * hd[:, None]).sum(-1); off = (rp * sd[:, None]).sum(-1)
    c_front, c_short, c_corr = along > 0, along < dz, off.abs() < CLEAR
    return own, tz, dz, hd, sd, rp, pres, along, off, c_front, c_short, c_corr
def s_flank(obs, sl, ch=None):
    own, tz, dz, hd, sd, rp, pres, along, off, cf, cs, cc = flank_parts(obs)
    inw = pres & cf & cs & cc
    near = rp.norm(dim=-1).masked_fill(~inw, float("inf")).argmin(-1) if ch is None else ch["near"]
    blocked = inw.any(-1) if ch is None else ch["blocked"]
    g = gat(rp, near); o = (g * sd).sum(-1)
    sign = torch.where(o >= 0, 1.0, -1.0) if ch is None else ch["sign"]
    wp = g + sd * sign[:, None] * CLEAR
    return z4(steer(torch.where(blocked[:, None], wp, tz)), obs), {"blocked": blocked, "near": near, "sign": sign}
def s_sacrifice(obs, sl, ch=None):
    own = obs[:, 0:2]; straight = steer(-own); mates, live = team(obs, sl, PG)
    dp, dl = mates[:, 0], live[:, 0]; others = live.sum(-1) >= 2
    gp, _, gpres = slots(obs, 0, PG)
    near = gp.norm(dim=-1).masked_fill(~gpres, float("inf")).argmin(-1) if ch is None else ch["near"]
    anyg = gpres.any(-1)
    decoy_a = torch.where(anyg[:, None], steer(gat(gp, near)), straight)
    guard_p = own[:, None] + gp
    td = (guard_p - dp[:, None]).norm(dim=-1).masked_fill(~gpres, float("inf"))
    dr = td.argmin(-1) if ch is None else ch["drawn"]
    drawn = gat(guard_p, dr)
    hb = anyg & (drawn.norm(dim=-1) > 0.05) if ch is None else ch["has_bearing"]
    away = torch.where(hb[:, None], drawn, dp)
    diff = wrap(torch.atan2(-away[:, 1], -away[:, 0]) - torch.atan2(own[:, 1], own[:, 0]))
    dirn = torch.where(diff >= 0, 1.0, -1.0) if ch is None else ch["direction"]
    go_in = diff.abs() <= PI / 6 if ch is None else ch["go_in"]
    rest = torch.where(go_in[:, None], straight, circle(own, stand_off(obs), dirn))
    a = torch.where((sl == 0)[:, None], decoy_a, rest)
    a = torch.where((dl & others)[:, None], a, straight)
    return z4(a, obs), {"near": near, "drawn": dr, "has_bearing": hb, "direction": dirn, "go_in": go_in, "diff": diff}
def s_converge(obs, sl, ch=None):
    own = obs[:, 0:2]; straight = steer(-own); mates, live = team(obs, sl, PG); idx = torch.arange(M)
    n_live = live.sum(-1); ref = torch.where(live, idx, M).amin(-1).clamp(max=M - 1); refp = gat(mates, ref)
    rp = refp[:, None]
    off = torch.atan2(rp[..., 0] * mates[..., 1] - rp[..., 1] * mates[..., 0], (rp * mates).sum(-1))
    off = torch.where(off < 0, off + 2 * PI, off).masked_fill(~live, float("inf"))
    rank = off.argsort(-1).argsort(-1).float() if ch is None else ch["rank"]
    target = rank * 2 * PI / n_live.clamp(min=1)[:, None].float()
    err = wrap(target - off.masked_fill(~live, 0.0))
    R = stand_off(obs); rho = mates.norm(dim=-1)
    committed = (live & (rho < R - 0.3)).any(-1) if ch is None else ch["committed"]
    gathered = ((err.abs() <= 0.1) | ~live).all(-1) if ch is None else ch["gathered"]
    go = gathered | committed
    te = (rho - obs[:, 8:9]).clamp(min=0) * live
    pace = (gat(te[..., None], sl)[:, 0] / te.amax(-1).clamp(min=1e-9)).clamp(max=1.0)
    own_off = gat(off.masked_fill(~live, 0.0)[..., None], sl)[:, 0]; own_t = gat(target[..., None], sl)[:, 0]
    want = torch.atan2(refp[:, 1], refp[:, 0]) + own_t; diff = own_t - own_off
    dirn = torch.where(diff >= 0, 1.0, -1.0) if ch is None else ch["direction"]
    circ = wrap(diff).abs() > 0.5 if ch is None else ch["circle"]
    point = R * torch.stack((want.cos(), want.sin()), -1)
    place = torch.where(circ[:, None], circle(own, R, dirn), steer(point - own))
    a = torch.where(go[:, None], unit(-own) * pace[:, None], place)
    a = torch.where((n_live >= 2)[:, None], a, straight)
    return z4(a, obs), {"rank": rank, "committed": committed, "gathered": gathered, "direction": dirn, "circle": circ,
                        "maxerr": torch.where(live, err.abs(), torch.zeros_like(err)).amax(-1), "minrho": rho.masked_fill(~live, 9).amin(-1),
                        "n_live": n_live, "pace": pace, "go": go}

STRIKE = {"strike_straight": s_straight, "strike_flank": s_flank, "strike_high": s_height(True),
          "strike_low": s_height(False), "strike_sacrifice": s_sacrifice, "strike_converge": s_converge}


def load(side, n, seed=0):
    d = torch.load(ROOT / f"runs/2026-11-26_ste_ls11_distil_{side}/data/round_0.pt", weights_only=True)
    g = torch.Generator().manual_seed(seed); idx = torch.randperm(d["obs"].shape[0], generator=g)[:n]
    return {k: d[k][idx] for k in ("obs", "slot", "label", "flown", "n_live", "opponent", "near_switch")}


def jitter(obs, delta, gen, z=True, vel=False):
    o = obs.clone(); n = obs.shape[0]
    o[:, 0:2] += torch.randn(n, 2, generator=gen) * delta
    if z: o[:, 2] += torch.randn(n, generator=gen) * delta
    if vel: o[:, 3:5] += torch.randn(n, 2, generator=gen) * delta
    for k in range(8):
        a = 13 + 7 * k; pres = (obs[:, a + 6] > 0.5).float()[:, None]
        o[:, a:a + 2] += torch.randn(n, 2, generator=gen) * delta * pres
        if vel: o[:, a + 3:a + 5] += torch.randn(n, 2, generator=gen) * delta * pres
    return o


def diffch(c0, c1, keys):
    out = {}
    for k in keys:
        a, b = c0[k], c1[k]
        out[k] = (a != b).any(-1) if a.dim() > 1 else (a != b)
    return out
