"""LS1-R pilot library (LS1_REDESIGN.md 3.3 to 3.7, 4.3): features by rung, per-skill networks with outputs in the
skill's frame and an output mask, the cosine fit, the row marks, and a K-skill assembly that flies in the harness.
Scratch, INFO, not of record. ONNX-friendly feature ops (no sort, no eye; ranks by pairwise counts; masked min and
gather), so 0d can export them.

Rungs: "R1" own zone-line frame; "R2" adds nearest-first order; "R3" adds the skill's switch margins; "R4" adds the
skill's choices and flags (branch heads, reflection, chosen frames). "RAW" is arm C-in (raw inputs, world frame).
"""
from __future__ import annotations

import math
import time
from pathlib import Path

import torch
from torch import nn

SVG = Path.home() / "AirStack-starling-max2-dev/svg_training"
import sys  # noqa: E402
sys.path.insert(0, str(SVG / "source"))
from svg_training.ste import exploit  # noqa: E402
from svg_training.opponents import scripted as S  # noqa: E402

CFG = exploit.load_game_cfg_file(SVG / "configs/ste_l011/base.toml")
PG, PS, M = CFG.pad_guards, CFG.pad_strikes, 3
CLEAR = CFG.rules.keepout_strike_m + S.StrikeFlank.MARGIN_M
GSPEED = CFG.team_speed_mps("guard")
LO, HI = CFG.arena.height_band_m
WALL = CFG.arena.wall_margin_m
RAMP = S.STEER_RAMP_M
ABSENT_FAR = 10.0
EPS = 1e-6
PI = math.pi
ZEROED = (6, 7, 10, 11)
GUARDS = ["guard_parked_centre", "guard_parked_ring", "guard_mark_edge", "guard_mirror", "guard_field"]
STRIKES = ["strike_straight", "strike_flank", "strike_high", "strike_low", "strike_sacrifice", "strike_converge"]
SKILLS = {"guard": GUARDS, "strike": STRIKES}


# ------------------------------------------------------------------ small ops
def perp(v):
    return torch.stack((-v[..., 1], v[..., 0]), -1)


def unit(v):
    return v / v.norm(dim=-1, keepdim=True).clamp(min=1e-9)


def steer(d):
    n = d.norm(dim=-1, keepdim=True)
    return d / n.clamp(min=1e-9) * (n / RAMP).clamp(max=1.0)


def wrap(a):
    return torch.atan2(a.sin(), a.cos())


def onehot(i, n):
    return (i[:, None] == torch.arange(n, device=i.device)[None]).to(torch.float32)


def gat(x, idx):
    """x [B, G, F], idx [B] -> [B, F] (one-hot weighted sum: ONNX-friendly, exact for one-hot)."""
    w = onehot(idx, x.shape[1])
    return (w[..., None] * x).sum(1)


def masked_argmin(d, pres):
    """argmin of d over present entries (first on ties); ONNX-friendly."""
    big = torch.where(pres, d, torch.full_like(d, 1e9))
    m = big.amin(-1, keepdim=True)
    hit = big <= m
    idx = torch.arange(d.shape[1], device=d.device)[None].expand_as(d)
    return torch.where(hit, idx, torch.full_like(idx, d.shape[1])).amin(-1).clamp(max=d.shape[1] - 1)


ORDER_RES_M = 1e-3      # R2's nearest-first order ranks distances at 1 mm resolution, ties by slot: exact symmetric
                        # ties (a ring seen from one of its drones) otherwise break by roundoff, differently in onnxruntime


def ranks(d, pres, res=None):
    """Rank of each entry by d ascending, absent last, ties by index (pairwise counts); ``res``: quantise d first."""
    if res is not None:
        d = torch.round(d / res) * res
    big = torch.where(pres, d, torch.full_like(d, 1e9))
    g = big.shape[1]
    idx = torch.arange(g, device=d.device)
    before = (big[:, None, :] < big[:, :, None]) | ((big[:, None, :] == big[:, :, None]) & (idx[None, None, :] < idx[None, :, None]))
    return before.sum(-1)


def reorder(feat, rank):
    """feat [B, G, F], rank [B, G] -> [B, G, F] with entry r = the entity of rank r."""
    g = feat.shape[1]
    w = (rank[:, None, :] == torch.arange(g, device=feat.device)[None, :, None]).to(feat.dtype)   # [B, r, k]
    return torch.einsum("brk,bkf->brf", w, feat)


def slots(obs, first, count):
    s = obs[:, 13 + 7 * first: 13 + 7 * (first + count)].reshape(-1, count, 7)
    return s[..., 0:2], s[..., 3:5], s[..., 6] > 0.5


def stand_off(obs):
    return torch.minimum(obs[:, 8] + S.STAND_OFF_M, obs[:, 9] - WALL - obs[:, 69:71].abs().amax(-1))


def team_pos(obs, sl, first):
    """[B, M, 2] team positions from the zone centre, [B, M] live (self included); own slot from its own row."""
    rp, _, pres = slots(obs, first, M)
    own = obs[:, 0:2]
    me = onehot(sl, M) > 0.5
    pos = own[:, None] + rp * (~me)[..., None].to(rp.dtype)
    live = (me & (obs[:, 12] > 0.5)[:, None]) | (~me & pres)
    return pos, live


# ------------------------------------------------------------------ frames
def zone_frame(obs):
    p = obs[:, 0:2]
    rho = p.norm(dim=-1)
    h = -p / rho.clamp(min=EPS)[:, None]
    return h, perp(h)


def to_frame(x, e1, e2):
    if x.dim() == 3:
        return torch.stack(((x * e1[:, None]).sum(-1), (x * e2[:, None]).sum(-1)), -1)
    return torch.stack(((x * e1).sum(-1), (x * e2).sum(-1)), -1)


# ------------------------------------------------------------------ R1, R2 (common block)
def entity_block(obs, e1, e2):
    """[B, 8, 6] per slot (a, o, d, present, u_e1, u_e2) with the absent placeholder."""
    q, u, pres = slots(obs, 0, PG + PS)
    fq, fu = to_frame(q, e1, e2), to_frame(u, e1, e2)
    d = q.norm(dim=-1)
    pf = pres.to(obs.dtype)
    a = torch.where(pres, fq[..., 0], torch.full_like(d, -ABSENT_FAR))
    o = torch.where(pres, fq[..., 1], torch.zeros_like(d))
    dd = torch.where(pres, d, torch.full_like(d, ABSENT_FAR))
    return torch.stack((a, o, dd, pf, fu[..., 0] * pf, fu[..., 1] * pf), -1), d, pres


def common(obs, sl, side, rung):
    p = obs[:, 0:2]; rho = p.norm(dim=-1)
    h, s = zone_frame(obs)
    v = obs[:, 3:5]
    raw = obs.clone(); raw[:, list(ZEROED)] = 0.0
    ent, d, pres = entity_block(obs, h, s)
    first = 0 if side == "guard" else PG
    mates, live = team_pos(obs, sl, first)
    rj = mates.norm(dim=-1)
    um, up = unit(mates), unit(p)[:, None]
    cb = (um * up).sum(-1); sb = um[..., 0] * up[..., 1] * -1 + um[..., 1] * up[..., 0]      # cross(p, mate) / norms
    lf = live.to(obs.dtype)
    mate = torch.stack((torch.where(live, rj, torch.full_like(rj, ABSENT_FAR)), cb * lf, sb * lf, lf), -1)
    width = PG if side == "guard" else PS
    parts = [raw, torch.stack((rho, obs[:, 2], (v * h).sum(-1), (v * s).sum(-1), obs[:, 5]), -1),
             ent.reshape(obs.shape[0], -1), mate.reshape(obs.shape[0], -1), onehot(sl.long(), width)]
    if rung in ("R2", "R3", "R4"):
        rg = ranks(d[:, :PG], pres[:, :PG], ORDER_RES_M); rs = ranks(d[:, PG:], pres[:, PG:], ORDER_RES_M)
        parts += [reorder(ent[:, :PG], rg).reshape(obs.shape[0], -1), reorder(ent[:, PG:], rs).reshape(obs.shape[0], -1)]
    return torch.cat(parts, -1)


# ------------------------------------------------------------------ R3 blocks (switch margins), per skill
def r3_block(obs, sl, skill):
    p = obs[:, 0:2]; rho = p.norm(dim=-1); h, s = zone_frame(obs); B = obs.shape[0]
    if skill in ("strike_high", "strike_low"):
        t = HI - S.BAND_INSET_M if skill == "strike_high" else LO + S.BAND_INSET_M
        vt = ((t - obs[:, 2]) / RAMP).clamp(-1, 1)
        return torch.stack((vt, (1 - vt ** 2).clamp(min=0).sqrt()), -1)
    if skill == "strike_flank":
        q, _, pres = slots(obs, 0, PG); fq = to_frame(q, h, s)
        a, o = fq[..., 0], fq[..., 1]
        m = torch.minimum(torch.minimum(a, rho[:, None] - a), CLEAR - o.abs())
        m = torch.where(pres, m, torch.full_like(m, -ABSENT_FAR))
        return torch.cat((m, torch.where(pres, o, torch.zeros_like(o))), -1)
    if skill == "guard_field":
        q, _, pres = slots(obs, PG, PS); d = q.norm(dim=-1)
        big = torch.where(pres, d, torch.full_like(d, ABSENT_FAR))
        r = ranks(d, pres); od = reorder(big[..., None], r)[..., 0]
        gap = (od[:, 1] - od[:, 0]) / 2
        tp, _, tpres = slots(obs, 0, PG); dd = tp.norm(dim=-1).clamp(min=1e-6)
        mag = (1 / dd ** 2 - 1 / S.FIELD_RANGE_M ** 2) * (tpres & (dd < S.FIELD_RANGE_M))
        push = -(tp / dd[..., None] * mag[..., None]).sum(1)
        return torch.cat((to_frame(push, h, s), gap[:, None]), -1)
    if skill == "strike_sacrifice":
        return sacrifice_parts(obs, sl)["r3"]
    if skill == "strike_converge":
        return converge_parts(obs, sl)["r3"]
    return torch.zeros(B, 0)


def sacrifice_parts(obs, sl):
    p = obs[:, 0:2]; rho = p.norm(dim=-1); h, s = zone_frame(obs)
    mates, live = team_pos(obs, sl, PG)
    dp, dl = mates[:, 0], live[:, 0]; others = live.sum(-1) >= 2
    gq, _, gpres = slots(obs, 0, PG); anyg = gpres.any(-1)
    n = masked_argmin(gq.norm(dim=-1), gpres)
    nq = to_frame(gat(gq, n), h, s)
    guard_p = p[:, None] + gq
    g = masked_argmin((guard_p - dp[:, None]).norm(dim=-1), gpres)
    drawn = gat(guard_p, g)
    hb = anyg & (drawn.norm(dim=-1) > S.SACRIFICE_NO_BEARING_M)
    away = torch.where(hb[:, None], drawn, dp)
    pd, ad = p.double(), (-away).double()          # flags from float64 cross / dot signs (no angle): the switches
    cr = pd[:, 0] * ad[:, 1] - pd[:, 1] * ad[:, 0]  # at 0, +-pi and +-pi/6 then break alike in onnxruntime
    dt = (pd * ad).sum(-1)
    nrm = ((pd * pd).sum(-1) * (ad * ad).sum(-1)).sqrt()
    ads = torch.atan2(cr.abs().to(obs.dtype), dt.to(obs.dtype)).abs()    # |ds| in [0, pi]; .abs(): ort's atan2(0, -x) is -pi
    cs = (dt / nrm.clamp(min=1e-12)).to(obs.dtype); sn = (cr / nrm.clamp(min=1e-12)).to(obs.dtype)
    R = stand_off(obs)
    rad = ((R - rho) / S.RADIAL_RAMP_M).clamp(-1, 1)
    decoy = (sl == 0).to(obs.dtype)
    r3 = torch.stack((decoy, nq[:, 0], nq[:, 1], anyg.to(obs.dtype), cs, sn, ads - S.ENTRY_HALF_ANGLE_RAD,
                      PI - ads, rad), -1)
    r3 = torch.cat((r3, to_frame(dp - p, h, s)), -1)
    active = dl & others
    go_in = dt >= math.cos(S.ENTRY_HALF_ANGLE_RAD) * nrm
    dirn = torch.where(cr >= 0, 1.0, -1.0)
    return {"r3": r3, "active": active, "go_in": go_in, "dir": dirn, "decoy": sl == 0, "anyg": anyg, "nq": nq, "rad": rad}


def converge_parts(obs, sl):
    p = obs[:, 0:2]; rho = p.norm(dim=-1)
    mates, live = team_pos(obs, sl, PG); idx = torch.arange(M)
    n_live = live.sum(-1)
    ref = torch.where(live, idx[None].expand_as(live), torch.full_like(live, M, dtype=torch.long)).amin(-1).clamp(max=M - 1)
    refp = gat(mates, ref); rp = refp[:, None]
    off = torch.atan2(rp[..., 0] * mates[..., 1] - rp[..., 1] * mates[..., 0], (rp * mates).sum(-1))
    off = torch.where(off < 0, off + 2 * PI, off)
    offl = torch.where(live, off, torch.full_like(off, 1e9))
    rank = ranks(offl, live).to(obs.dtype)
    target = rank * 2 * PI / n_live.clamp(min=1)[:, None].to(obs.dtype)
    offz = torch.where(live, off, torch.zeros_like(off))
    err = wrap(target - offz)
    R = stand_off(obs); rj = mates.norm(dim=-1)
    committed = (live & (rj < (R - S.RUN_IN_COMMIT_M)[:, None])).any(-1)
    gathered = ((err.abs() <= S.GATHER_ANGLE_RAD) | ~live).all(-1)
    te = (rj - obs[:, 8:9]).clamp(min=0) * live
    num = gat(te[..., None], sl)[:, 0]; den = te.amax(-1)
    own_off = gat(offz[..., None], sl)[:, 0]; own_t = gat(target[..., None], sl)[:, 0]
    D = own_t - own_off; Dw = wrap(D)
    want = torch.atan2(refp[:, 1], refp[:, 0]) + own_t
    maxerr = torch.where(live, err.abs(), torch.zeros_like(err)).amax(-1)
    minr = torch.where(live, rj, torch.full_like(rj, 1e9)).amin(-1)
    r3 = torch.stack((D, Dw, maxerr - S.GATHER_ANGLE_RAD, minr - (R - S.RUN_IN_COMMIT_M), num, den,
                      n_live.to(obs.dtype), ((R - rho) / S.RADIAL_RAMP_M).clamp(-1, 1), R, want.cos(), want.sin()), -1)
    go = gathered | committed
    return {"r3": r3, "go": go, "gathered": gathered, "committed": committed, "circle": Dw.abs() > S.CIRCLE_UNTIL_RAD,
            "two": n_live >= 2, "dir": torch.where(D >= 0, 1.0, -1.0), "pace": (num / den.clamp(min=1e-9)).clamp(max=1.0),
            "want": want, "R": R}


# ------------------------------------------------------------------ features by rung
def features(obs, sl, side, skill, rung):
    """-> (x [B, F], frame (e1, e2), extra dict for R4 heads)."""
    obs = obs.to(torch.float32)
    if rung == "RAW":
        raw = obs.clone(); raw[:, list(ZEROED)] = 0.0
        e1 = torch.zeros_like(obs[:, 0:2]); e1[:, 0] = 1.0
        return torch.cat((raw, onehot(sl.long(), PG if side == "guard" else PS)), -1), (e1, perp(e1)), {}
    x = common(obs, sl, side, rung)
    e1, e2 = zone_frame(obs)
    extra = {}
    if rung in ("R3", "R4"):
        x = torch.cat((x, r3_block(obs, sl, skill)), -1)
    if rung == "R4":
        x, (e1, e2), extra = r4_block(obs, sl, skill, x, e1, e2)
    return x, (e1, e2), extra


def r4_block(obs, sl, skill, x, e1, e2):
    """R4: the script's choices and flags; heads (a [B, H] gate, one-hot per row) and reflection sigma [B]."""
    B = obs.shape[0]; p = obs[:, 0:2]; rho = p.norm(dim=-1)
    one = torch.ones(B); sig = one
    if skill == "strike_flank":
        q, _, pres = slots(obs, 0, PG); fq = to_frame(q, e1, e2)
        a, o = fq[..., 0], fq[..., 1]
        inw = pres & (a > 0) & (a < rho[:, None]) & (o.abs() < CLEAR)
        k = masked_argmin(q.norm(dim=-1), inw); blocked = inw.any(-1)
        ak, ok = gat(a[..., None], k)[:, 0], gat(o[..., None], k)[:, 0]
        sig = torch.where(ok >= 0, 1.0, -1.0)
        add = torch.stack((blocked.float(), ak * blocked, ok.abs() * blocked), -1)
        heads = torch.stack((~blocked, blocked), -1).float()
    elif skill == "strike_sacrifice":
        P = sacrifice_parts(obs, sl)
        sig = P["dir"]
        dec, act, gi = P["decoy"], P["active"], P["go_in"]
        heads = torch.stack((~act, act & dec, act & ~dec & gi, act & ~dec & ~gi), -1).float()
        add = torch.cat((heads, (P["r3"][:, 5:6] * sig[:, None])), -1)
    elif skill == "strike_converge":
        P = converge_parts(obs, sl)
        sig = P["dir"]
        two, go, circ = P["two"], P["go"], P["circle"]
        heads = torch.stack((~two, two & go, two & ~go & circ, two & ~go & ~circ), -1).float()
        add = torch.cat((heads, P["pace"][:, None], (P["r3"][:, 1:2] * sig[:, None])), -1)
    elif skill == "guard_field":
        q, _, pres = slots(obs, PG, PS); n = masked_argmin(q.norm(dim=-1), pres)
        en = unit(p + gat(q, n)); tn = perp(en)
        e1, e2 = en, tn
        tp, _, tpres = slots(obs, 0, PG); dd = tp.norm(dim=-1).clamp(min=1e-6)
        mag = (1 / dd ** 2 - 1 / S.FIELD_RANGE_M ** 2) * (tpres & (dd < S.FIELD_RANGE_M))
        push = to_frame(-(tp / dd[..., None] * mag[..., None]).sum(1), en, tn)
        add = torch.cat((torch.stack((obs[:, 8] - (p * en).sum(-1), -(p * tn).sum(-1), pres.any(-1).float()), -1), push), -1)
        heads = torch.ones(B, 1)
    elif skill in ("guard_mark_edge", "guard_mirror"):
        q, u, pres = slots(obs, PG, PS)
        nS = pres.sum(-1); rk = sl % nS.clamp(min=1)
        pick = pres & ((pres.long().cumsum(-1) - 1) == rk[:, None])
        w = pick.float()[..., None]
        sp = p + (q * w).sum(1); sv = obs[:, 3:5] + (u * w).sum(1); found = (nS > 0)
        e1 = unit(sp); e2 = perp(e1)
        ring = S.GuardMirror.RING if skill == "guard_mirror" else 1.0
        add = torch.stack((ring * obs[:, 8] - (p * e1).sum(-1), -(p * e2).sum(-1), (sv * e2).sum(-1) / GSPEED,
                           found.float()), -1)
        heads = torch.ones(B, 1)
    elif skill == "guard_parked_ring":
        mates, live = team_pos(obs, sl, 0)
        th = torch.atan2(mates[..., 1], mates[..., 0]); w = live.float()
        cs, sn = (w * (3 * th).cos()).sum(-1), (w * (3 * th).sin()).sum(-1)
        whole = live.sum(-1) >= M
        idx = torch.arange(M)
        ref = torch.where(live, idx[None].expand_as(live), torch.full_like(live, M, dtype=torch.long)).amin(-1).clamp(max=M - 1)
        refp = gat(mates, ref); rp = refp[:, None]
        off = torch.atan2(rp[..., 0] * mates[..., 1] - rp[..., 1] * mates[..., 0], (rp * mates).sum(-1))
        off = torch.where(off < 0, off + 2 * PI, off)
        rk = ranks(torch.where(live, off, torch.full_like(off, 1e9)), live).float()
        own_rank = gat(rk[..., None], sl)[:, 0]
        ordered = torch.atan2(refp[:, 1], refp[:, 0]) + own_rank * 2 * PI / M
        phase = torch.atan2(sn, cs) / M
        oth = torch.atan2(p[:, 1], p[:, 0]); step = 2 * PI / M
        mm = torch.round(wrap(oth - phase) / step)
        want = torch.where(whole, ordered, phase + mm * step)
        e1 = torch.zeros_like(p); e1[:, 0] = 1.0; e2 = perp(e1)
        add = torch.stack((want.cos(), want.sin(), (cs ** 2 + sn ** 2).sqrt(), whole.float()), -1)
        heads = torch.stack((whole, ~whole), -1).float()
    else:
        add = torch.zeros(B, 0); heads = torch.ones(B, 1)
    x = torch.cat((x, add, to_frame(p, e1, e2)), -1)
    return x, (e1, e2), {"heads": heads, "sigma": sig}


# ------------------------------------------------------------------ networks
class SkillMLP(nn.Module):
    """One skill: features -> (c1, c2[, vz]) per head in the skill's frame; xy rotated back (with reflection), vz
    passes through, yaw 0; output mask [4]."""

    def __init__(self, n_in, out_dim, heads, hidden, mean, std, rawcols):
        super().__init__()
        self.register_buffer("mean", mean); self.register_buffer("std", std)
        self.register_buffer("raw", rawcols)
        layers, w = [], n_in
        for hdim in hidden:
            layers += [nn.Linear(w, hdim), nn.ELU()]; w = hdim
        layers.append(nn.Linear(w, out_dim * heads))
        self.mlp = nn.Sequential(*layers)
        self.out_dim, self.heads = out_dim, heads

    def forward(self, x, frame, extra):
        xn = torch.where(self.raw, x, (x - self.mean) / self.std)
        y = self.mlp(xn).reshape(x.shape[0], self.heads, self.out_dim)
        if self.heads > 1:
            y = (extra["heads"][..., None] * y).sum(1)
        else:
            y = y[:, 0]
        sig = extra.get("sigma", None)
        c2 = y[:, 1] * (sig if sig is not None else 1.0)
        e1, e2 = frame
        xy = y[:, 0:1] * e1 + c2[:, None] * e2
        vz = y[:, 2:3] if self.out_dim == 3 else torch.zeros_like(xy[:, :1])
        return torch.cat((xy, vz, torch.zeros_like(vz)), -1)


def out_dim_of(skill):
    return 3 if skill in ("strike_high", "strike_low") else 2


def n_heads(skill, rung):
    if rung != "R4":
        return 1
    return {"strike_flank": 2, "strike_sacrifice": 4, "strike_converge": 4, "guard_parked_ring": 2}.get(skill, 1)


# ------------------------------------------------------------------ data
def load_rows(side, n_train=1_000_000, seed=150003):
    """Training: 1,000,000 rows of round 0 + 1,000,000 of round 3 from games with game % 5 != 0. Held-out: game % 5
    == 0, rounds 0 and 3 (all rows)."""
    g = torch.Generator().manual_seed(seed)
    tr, held = [], {}
    for r in (0, 3):
        d = torch.load(SVG / f"runs/2026-11-26_ste_ls11_distil_{side}/data/round_{r}.pt", map_location="cpu", weights_only=True)
        keep = {k: d[k] for k in ("obs", "slot", "label", "flown", "game")}
        ho = keep["game"] % 5 == 0
        held[r] = {k: v[ho] for k, v in keep.items()}
        idx = torch.nonzero(~ho).squeeze(1)
        idx = idx[torch.randperm(idx.numel(), generator=g)[:n_train]].sort().values
        tr.append({k: v[idx] for k, v in keep.items()})
        del d
    train = {k: torch.cat([t[k] for t in tr]) for k in tr[0]}
    return train, held


def feats_chunked(obs, slot, side, skill, rung, chunk=200_000):
    xs, f1, f2, heads, sig = [], [], [], [], []
    for i in range(0, obs.shape[0], chunk):
        x, (e1, e2), ex = features(obs[i:i + chunk], slot[i:i + chunk].long(), side, skill, rung)
        xs.append(x); f1.append(e1); f2.append(e2)
        heads.append(ex.get("heads", torch.ones(x.shape[0], 1))); sig.append(ex.get("sigma", torch.ones(x.shape[0])))
    return torch.cat(xs), (torch.cat(f1), torch.cat(f2)), {"heads": torch.cat(heads), "sigma": torch.cat(sig)}


def active_mask(train, k):
    return train["label"][:, k].abs().amax(0) > 0


# ------------------------------------------------------------------ fit
def fit_skill(train, side, skill, rung, *, hidden=(128, 128, 128), steps=40_000, seed=150003, lr=1e-3, lr_final=1e-5,
              schedule="cos", batch=8192, own_weight=2.0, log=print):
    k = SKILLS[side].index(skill)
    torch.manual_seed(seed)
    x, frame, extra = feats_chunked(train["obs"], train["slot"], side, skill, rung)
    y = train["label"][:, k]
    mask = active_mask(train, k).float()
    w_row = 1 + (own_weight - 1) * (train["flown"] == k).float()
    binary = ((x == 0) | (x == 1)).all(0)
    mean, std = x.mean(0), x.std(0).clamp(min=0.01)
    net = SkillMLP(x.shape[1], out_dim_of(skill), n_heads(skill, rung), list(hidden), mean, std, binary)
    net.register_buffer("out_mask", mask)
    opt = torch.optim.Adam(net.parameters(), lr=lr)
    g = torch.Generator().manual_seed(seed)
    R = x.shape[0]; warm = max(1, int(0.02 * steps)); n_act = mask.sum().clamp(min=1)
    t0 = time.time()
    for st in range(steps):
        if schedule == "cos":
            cur = lr * (st + 1) / warm if st < warm else lr_final + 0.5 * (lr - lr_final) * (1 + math.cos(math.pi * (st - warm) / max(1, steps - warm)))
        else:
            cur = lr
        for gr in opt.param_groups:
            gr["lr"] = cur
        idx = torch.randint(0, R, (batch,), generator=g)
        out = net(x[idx], (frame[0][idx], frame[1][idx]), {"heads": extra["heads"][idx], "sigma": extra["sigma"][idx]})
        err = (out - y[idx]) * mask
        loss = (w_row[idx] * (err ** 2).sum(-1)).mean() / n_act
        opt.zero_grad(); loss.backward(); opt.step()
        if (st + 1) % 10_000 == 0:
            log(f"    {skill} {rung} step {st + 1}: loss {float(loss):.3e} lr {cur:.2e} ({time.time() - t0:.0f} s)")
    net.eval().requires_grad_(False)
    return net, time.time() - t0


def skill_out(net, obs, slot, side, skill, rung, chunk=200_000):
    outs = []
    with torch.no_grad():
        for i in range(0, obs.shape[0], chunk):
            x, fr, ex = features(obs[i:i + chunk], slot[i:i + chunk].long(), side, skill, rung)
            outs.append(net(x, fr, ex) * net.out_mask)
    return torch.cat(outs)


# ------------------------------------------------------------------ row marks (4.3)
def switch_margin(obs, slot, skill):
    """Distance (m) to the skill's nearest switch margin, for r5's '> 2 cm from every margin' (inf: no switch)."""
    B = obs.shape[0]; p = obs[:, 0:2]; rho = p.norm(dim=-1)
    if skill == "strike_flank":
        r3 = r3_block(obs, slot, skill); m, o = r3[:, :PG], r3[:, PG:]
        _, _, pres = slots(obs, 0, PG)
        a = torch.where(pres, m.abs(), torch.full_like(m, 1e9)).amin(-1)
        b = torch.where(pres & (m > -0.05), o.abs(), torch.full_like(o, 1e9)).amin(-1)
        return torch.minimum(a, b)
    if skill == "guard_field":
        return r3_block(obs, slot, skill)[:, 2] * 2
    if skill == "strike_sacrifice":
        r3 = sacrifice_parts(obs, slot)["r3"]
        ads = r3[:, 6] + S.ENTRY_HALF_ANGLE_RAD
        return rho * torch.minimum(r3[:, 6].abs(), torch.minimum(ads, r3[:, 7].abs()))
    if skill == "strike_converge":
        r3 = converge_parts(obs, slot)["r3"]
        return torch.minimum(torch.minimum(rho * r3[:, 0].abs(), rho * (r3[:, 1].abs() - S.CIRCLE_UNTIL_RAD).abs()),
                             torch.minimum(rho * r3[:, 2].abs(), r3[:, 3].abs()))
    return torch.full((B,), float("inf"))


def row_marks(out, held_r, k, skill, mask):
    """Marks r1..r7 on the skill's own held-out rows of one round. out [B, 4] (masked), labels [B, K, 4]."""
    own = held_r["flown"] == k
    alive = held_r["obs"][:, 12] > 0.5
    sel = own & alive
    o, y = out[sel], held_r["label"][sel, k]
    e = o - y
    act = mask.bool()
    res = {"rows": int(sel.sum())}
    res["r1_masked_zero"] = bool((o[:, ~act] == 0).all()) if (~act).any() else True
    res["r2_bias"] = [float(e[:, c].mean()) for c in range(4) if act[c]]
    big = y[:, :2].norm(dim=-1) > 0.2
    ang = torch.atan2(o[big, 1], o[big, 0]) - torch.atan2(y[big, 1], y[big, 0])
    res["r3_turn_deg"] = float(wrap(ang).mean() * 180 / PI) if big.any() else float("nan")
    res["r4_scale"] = float((o[big, :2].norm(dim=-1) / y[big, :2].norm(dim=-1)).mean()) if big.any() else float("nan")
    far = switch_margin(held_r["obs"][sel], held_r["slot"][sel].long(), skill) > 0.02
    ef = e[far] - e[far].mean(0)
    res["r5_rmse_debiased"] = [float(ef[:, c].pow(2).mean().sqrt()) for c in range(4) if act[c]]
    res["r6_tail"] = float((e.abs().amax(-1) > 0.1).float().mean())
    res["r7_rmse"] = [float(e[:, c].pow(2).mean().sqrt()) for c in range(4) if act[c]]
    return res


def screen_value(out0, out3, held, k, mask):
    """Eligibility screen: max over active channels of total RMSE on pooled own held-out rows of rounds 0 and 3."""
    errs = []
    for out, r in ((out0, 0), (out3, 3)):
        h = held[r]; sel = (h["flown"] == k) & (h["obs"][:, 12] > 0.5)
        errs.append(out[sel] - h["label"][sel, k])
    e = torch.cat(errs)
    return max(float(e[:, c].pow(2).mean().sqrt()) for c in range(4) if mask[c] > 0)


# ------------------------------------------------------------------ the assembly that flies in the harness
class Assembly(nn.Module):
    """K skills of one team: {skill: (net, rung)}; parked_centre (no entry) gives exact 0 (mask all off).
    forward(obs, slot, z) runs every skill on every row, then picks the row's code (run-all-then-pick)."""

    def __init__(self, side, parts: dict):
        super().__init__()
        self.side, self.parts = side, parts
        self.team, self.skills, self.k, self.team_size = side, tuple(SKILLS[side]), len(SKILLS[side]), M
        for i, (sk, (net, _)) in enumerate(parts.items()):
            self.add_module(f"n{i}", net)

    def forward(self, obs, slot, z, clip=True):
        outs = []
        for sk in self.skills:
            if sk not in self.parts:
                outs.append(torch.zeros(obs.shape[0], 4))
                continue
            net, rung = self.parts[sk]
            x, fr, ex = features(obs, slot.long(), self.side, sk, rung)
            o = net(x, fr, ex)
            if clip:
                o = o.clamp(-1, 1)
            outs.append(o * net.out_mask)
        every = torch.stack(outs, 1)                                    # [B, K, 4]
        pick = onehot(z, self.k)
        return (pick[..., None] * every).sum(1) * obs[:, 12:13]


def _all_flat(self, obs):
    """obs [N, M, OBS] -> [N, M, K, 4]: every code for every drone, each skill once (no K-fold repeat)."""
    n, m = obs.shape[:2]
    rows = obs.reshape(n * m, -1)
    slot = torch.arange(m).repeat(n)
    outs = []
    with torch.no_grad():
        for sk in self.skills:
            if sk not in self.parts:
                outs.append(torch.zeros(rows.shape[0], 4)); continue
            net, rung = self.parts[sk]
            x, fr, ex = features(rows, slot, self.side, sk, rung)
            outs.append(net(x, fr, ex).clamp(-1, 1) * net.out_mask)
    return (torch.stack(outs, 1) * rows[:, 12:13, None]).reshape(n, m, self.k, 4)


Assembly.all_flat = _all_flat
