"""Stage 0c (LS1_REDESIGN.md 4.2): the closed forms of flank, field, sacrifice and converge with every hard switch
replaced by a linear blend of the branch commands over a margin width w (metres; angles become arcs at the drone's
radius). w = 0 gives the scouts' exact closed forms (geo.py). Scratch, INFO, not of record.

Soft "nearest member" choice: q_k = mu_k * prod_{j != k} (1 - mu_j * P(j nearer than k)), P = lin(d_k - d_j),
normalised; with hard mu and P it is the script's argmin among members. "Any member" blends over max_k margin_k.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import torch

SCOUTS = Path.home() / "AirStack-starling-max2-dev/svg_training/records/evidence/2026-11-26_ste_ls1_redesign_scouts"
sys.path.insert(0, str(SCOUTS))
import geo  # noqa: E402
from geo import (CLEAR, GSPEED, M, PG, PI, PS, circle, gat, perp, slots, stand_off, steer, team, unit, wrap,  # noqa
                 z4)

SWITCH_SKILLS = {"strike": ("strike_flank", "strike_sacrifice", "strike_converge"), "guard": ("guard_field",)}


def lin(m, w):
    """Weight of the 'true' branch for a margin m (positive = true side), over width w."""
    return (0.5 + m / w).clamp(0.0, 1.0)


def soft_nearest(dist, mu, w):
    """dist [B, G] (inf where absent), mu [B, G] membership weight in [0, 1] -> q [B, G] normalised choice weights
    (zeros where no member)."""
    d = torch.nan_to_num(dist, posinf=1e6)
    p = lin(d[:, :, None] - d[:, None, :], w)          # [B, k, j]: P(j nearer than k) = lin(d_k - d_j)
    eye = torch.eye(d.shape[1], dtype=torch.bool)
    f = (1 - mu[:, None, :] * p).masked_fill(eye, 1.0)
    q = mu * f.prod(-1)
    return q / q.sum(-1, keepdim=True).clamp(min=1e-12)


def mix(q, cmds):
    """q [B, G], cmds [B, G, 2] -> [B, 2]."""
    return (q[..., None] * cmds).sum(1)


# ------------------------------------------------------------------ flank
def flank(obs, sl, w):
    if w <= 0:
        return geo.s_flank(obs, sl)[0]
    own = obs[:, 0:2]; tz = -own; dz = tz.norm(dim=-1, keepdim=True); hd = unit(tz); sd = perp(hd)
    rp, _, pres = slots(obs, 0, PG)
    along = (rp * hd[:, None]).sum(-1); off = (rp * sd[:, None]).sum(-1)
    margin = torch.minimum(torch.minimum(along, dz - along), CLEAR - off.abs())       # > 0: in the way
    margin = margin.masked_fill(~pres, -1e6)
    mu = lin(margin, w) * pres
    q = soft_nearest(rp.norm(dim=-1).masked_fill(~pres, float("inf")), mu, w)
    ws = lin(off, w)[..., None]                                                        # side sign +1 weight
    plus = steer((rp + sd[:, None] * CLEAR).reshape(-1, 2)).reshape(rp.shape)
    minus = steer((rp - sd[:, None] * CLEAR).reshape(-1, 2)).reshape(rp.shape)
    blocked = mix(q, ws * plus + (1 - ws) * minus)
    wb = lin(margin.amax(-1), w)[:, None]
    return z4(wb * blocked + (1 - wb) * steer(tz), obs)


# ------------------------------------------------------------------ field (Guard)
def field(obs, sl, w):
    if w <= 0:
        return geo.g_field(obs, sl)[0]
    own = obs[:, 0:2]; rp, _, pres = slots(obs, PG, PS)
    q = soft_nearest(rp.norm(dim=-1).masked_fill(~pres, float("inf")), pres.float(), w)
    found = pres.any(-1)
    pulls = steer((unit(own[:, None] + rp) * obs[:, None, 8:9] - own[:, None]).reshape(-1, 2)).reshape(rp.shape)
    pull = mix(q, pulls) * found[:, None]
    tp, _, tpres = slots(obs, 0, PG); d = tp.norm(dim=-1).clamp(min=1e-6)
    mag = (1 / d ** 2 - 1 / 1.1 ** 2) * (tpres & (d < 1.1))
    a = pull - (tp / d[..., None] * mag[..., None]).sum(1); a = a / a.norm(dim=-1, keepdim=True).clamp(min=1.0)
    return z4(a, obs)


# ------------------------------------------------------------------ sacrifice
def _dir_margin(diff):
    """Signed angular distance to the nearest flip of sign(diff) (at 0 and at +-pi)."""
    return torch.sign(diff) * torch.minimum(diff.abs(), PI - diff.abs())


def sacrifice(obs, sl, w):
    if w <= 0:
        return geo.s_sacrifice(obs, sl)[0]
    own = obs[:, 0:2]; rho = own.norm(dim=-1).clamp(min=1e-6); straight = steer(-own)
    mates, live = team(obs, sl, PG); dp, dl = mates[:, 0], live[:, 0]; others = live.sum(-1) >= 2
    gp, _, gpres = slots(obs, 0, PG); anyg = gpres.any(-1)
    # decoy (slot 0): soft nearest Guard
    q = soft_nearest(gp.norm(dim=-1).masked_fill(~gpres, float("inf")), gpres.float(), w)
    decoy = torch.where(anyg[:, None], mix(q, steer(gp.reshape(-1, 2)).reshape(gp.shape)), straight)
    # others: soft drawn Guard (nearest to the decoy), each with its own bearing blends
    guard_p = own[:, None] + gp
    qd = soft_nearest((guard_p - dp[:, None]).norm(dim=-1).masked_fill(~gpres, float("inf")), gpres.float(), w)
    R = stand_off(obs)
    rest_k = []
    for k in range(PG):
        cand = guard_p[:, k]
        whb = lin(cand.norm(dim=-1) - 0.05, w)[:, None] * anyg[:, None]          # has bearing
        outs = []
        for away in (cand, dp):
            diff = wrap(torch.atan2(-away[:, 1], -away[:, 0]) - torch.atan2(own[:, 1], own[:, 0]))
            wd = lin(rho * _dir_margin(diff), w)[:, None]
            wg = lin(rho * (PI / 6 - diff.abs()), w)[:, None]
            circ = wd * circle(own, R, torch.ones_like(diff)) + (1 - wd) * circle(own, R, -torch.ones_like(diff))
            outs.append(wg * straight + (1 - wg) * circ)
        rest_k.append(whb * outs[0] + (1 - whb) * outs[1])
    rest_k = torch.stack(rest_k, 1)
    rest = torch.where(anyg[:, None], mix(qd, rest_k), rest_k[:, 0])    # no Guard: away = decoy (outs[1] of any k)
    a = torch.where((sl == 0)[:, None], decoy, rest)
    a = torch.where((dl & others)[:, None], a, straight)
    return z4(a, obs)


# ------------------------------------------------------------------ converge
def _converge_given_rank(obs, sl, rank, live, mates, off, refp, n_live, w):
    """Converge's command for one hard rank assignment, with the go / circle / direction switches blended."""
    own = obs[:, 0:2]; rho = own.norm(dim=-1).clamp(min=1e-6)
    target = rank * 2 * PI / n_live.clamp(min=1)[:, None].float()
    offz = off.masked_fill(~live, 0.0)
    err = wrap(target - offz)
    R = stand_off(obs); rho_j = mates.norm(dim=-1)
    m_comm = (R - 0.3 - rho_j).masked_fill(~live, -1e6).amax(-1)
    m_gath = (rho_j * (0.1 - err.abs())).masked_fill(~live, 1e6).amin(-1)
    wc, wgat = lin(m_comm, w), lin(m_gath, w)
    wgo = (1 - (1 - wc) * (1 - wgat))[:, None]
    te = (rho_j - obs[:, 8:9]).clamp(min=0) * live
    pace = (gat(te[..., None], sl)[:, 0] / te.amax(-1).clamp(min=1e-9)).clamp(max=1.0)
    own_off = gat(offz[..., None], sl)[:, 0]; own_t = gat(target[..., None], sl)[:, 0]
    want = torch.atan2(refp[:, 1], refp[:, 0]) + own_t; diff = own_t - own_off
    wd = lin(rho * diff, w)[:, None]
    wcirc = lin(rho * (wrap(diff).abs() - 0.5), w)[:, None]
    circ = wd * circle(own, R, torch.ones_like(diff)) + (1 - wd) * circle(own, R, -torch.ones_like(diff))
    point = R * torch.stack((want.cos(), want.sin()), -1)
    place = wcirc * circ + (1 - wcirc) * steer(point - own)
    return wgo * (unit(-own) * pace[:, None]) + (1 - wgo) * place


def converge(obs, sl, w):
    if w <= 0:
        return geo.s_converge(obs, sl)[0]
    own = obs[:, 0:2]; straight = steer(-own)
    mates, live = team(obs, sl, PG); idx = torch.arange(M)
    n_live = live.sum(-1); ref = torch.where(live, idx, M).amin(-1).clamp(max=M - 1); refp = gat(mates, ref)
    rp = refp[:, None]
    off = torch.atan2(rp[..., 0] * mates[..., 1] - rp[..., 1] * mates[..., 0], (rp * mates).sum(-1))
    off = torch.where(off < 0, off + 2 * PI, off).masked_fill(~live, float("inf"))
    rank = off.argsort(-1).argsort(-1).float()
    # the one pair of non-ref live drones (team size 3): blend their order over the margin
    nonref = live & (idx[None] != ref[:, None])
    both = nonref.sum(-1) == 2
    a_i = torch.where(nonref, idx[None], M).amin(-1).clamp(max=M - 1)
    b_i = torch.where(nonref, idx[None], -1).amax(-1).clamp(min=0)
    oa, ob = gat(off.masked_fill(~live, 0)[..., None], a_i)[:, 0], gat(off.masked_fill(~live, 0)[..., None], b_i)[:, 0]
    s = ob - oa
    edge = torch.minimum(torch.minimum(oa, 2 * PI - oa), torch.minimum(ob, 2 * PI - ob))
    m_ab = torch.sign(s) * torch.minimum(s.abs(), edge)                       # > 0: a before b
    r_ab = torch.minimum(gat(mates.norm(dim=-1)[..., None], a_i)[:, 0], gat(mates.norm(dim=-1)[..., None], b_i)[:, 0])
    wab = torch.where(both, lin(r_ab * m_ab, w), (s > 0).float())[:, None]
    rank_ab = rank.clone()
    hard_a_first = (s > 0)
    # the swapped assignment: exchange the ranks of a and b
    swapped = rank.clone()
    ra, rb = gat(rank[..., None], a_i)[:, 0], gat(rank[..., None], b_i)[:, 0]
    swapped.scatter_(1, a_i[:, None], rb[:, None]); swapped.scatter_(1, b_i[:, None], ra[:, None])
    c_hard = _converge_given_rank(obs, sl, rank_ab, live, mates, off, refp, n_live, w)
    c_swap = _converge_given_rank(obs, sl, swapped, live, mates, off, refp, n_live, w)
    # weight of the hard assignment: wab if a is first in it, else 1 - wab
    wh = torch.where(hard_a_first[:, None], wab, 1 - wab)
    wh = torch.where(both[:, None], wh, torch.ones_like(wh))
    a = wh * c_hard + (1 - wh) * c_swap
    a = torch.where((n_live >= 2)[:, None], a, straight)
    return z4(a, obs)


FUNCS = {"strike_flank": flank, "strike_sacrifice": sacrifice, "strike_converge": converge, "guard_field": field}


class BlendNet(torch.nn.Module):
    """The scripts (ScriptOracle) for every code except ``skill``, which flies its w-blended closed form."""

    def __init__(self, oracle, skill: str, w: float):
        super().__init__()
        self.oracle, self.fn, self.w = oracle, FUNCS[skill], float(w)
        self.code = list(oracle.skills).index(skill)
        self.team, self.skills, self.k, self.team_size = oracle.team, oracle.skills, oracle.k, oracle.team_size

    def forward(self, obs, slot, z, clip: bool = True):
        out = self.oracle(obs, slot, z, clip=clip)
        sel = z == self.code
        if sel.any():
            c = self.fn(obs[sel], slot[sel], self.w)
            if clip:
                c = c.clamp(-1, 1)
            out[sel] = c * obs[sel, 12:13]
        return out
