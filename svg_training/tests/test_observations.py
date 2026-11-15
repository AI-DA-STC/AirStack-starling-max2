"""Observation layout (S2 Task 2)."""
import pathlib
import sys

import torch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
from svg_training.core.arena import Arenas  # noqa: E402
from svg_training.core.game_config import load_game_cfg  # noqa: E402
from svg_training.core.observations import OBS_DIM, STATE_DIM, ObsView, build_obs, build_state  # noqa: E402

CFG = load_game_cfg(use_local=False)[0]


def _inputs(alive=None):
    n = 3
    pos = torch.tensor([[[1.0, 0.0, 1.2], [0.0, 2.0, 1.2], [-1.0, -1.0, 1.2]]]).repeat(n, 1, 1)  # 2 Guard, 1 Strike
    vel = torch.tensor([[[0.1, 0.0, 0.0], [0.0, 0.2, 0.0], [0.3, 0.0, 0.0]]]).repeat(n, 1, 1)
    ar = Arenas(torch.full((n,), 8.0), torch.full((n,), 4.0), torch.zeros(n, 2), torch.full((n,), 1.0),
                torch.ones(n, dtype=torch.long))
    al = torch.ones(n, 3, dtype=torch.bool) if alive is None else alive
    return pos, vel, torch.zeros(n, 3), al, ar, torch.full((n,), 30.0)


def test_dims_and_slots():
    assert OBS_DIM == 71 and STATE_DIM == 61
    pos, vel, yaw, al, ar, tl = _inputs()
    o = build_obs(CFG, pos, vel, yaw, al, ar, tl, 2, 1)
    assert o["guard"].shape == (3, 2, OBS_DIM) and o["strike"].shape == (3, 1, OBS_DIM)
    v = ObsView()
    g0 = o["guard"][0, 0]
    assert g0[v.slot(0)][6] == 0                                   # own slot absent
    s = g0[v.slot(CFG.pad_guards + 0)]
    assert torch.allclose(s[:3], pos[0, 2] - pos[0, 0]) and s[6] == 1
    assert torch.allclose(s[3:6], vel[0, 2] - vel[0, 0])
    assert g0[v.slot(1)][6] == 1                                    # the other Guard
    for k in (2, 3, 4, CFG.pad_guards + 1, CFG.pad_guards + 2):     # padding
        assert (g0[v.slot(k)] == 0).all()
    assert o["guard"][0, 0, v.team] == -1 and o["strike"][0, 0, v.team] == 1
    assert g0[v.time_left] == 30.0 and g0[v.zone_radius] == 1.0 and g0[v.arena_half] == 4.0
    assert g0[v.alive] == 1
    assert torch.allclose(g0[v.own_pos], pos[0, 0])
    assert torch.allclose(g0[v.sin_cos_yaw], torch.tensor([0.0, 1.0]))


def test_absent_drone_is_zero_everywhere():
    pos, vel, yaw, al, ar, tl = _inputs()
    al[:, 2] = False
    pos[:, 2] = 1e3
    o = build_obs(CFG, pos, vel, yaw, al, ar, tl, 2, 1)
    v = ObsView()
    assert (o["guard"][0, 0][v.slot(CFG.pad_guards)] == 0).all()
    s = o["strike"][0, 0]
    assert s[v.alive] == 0 and s[v.team] == 1 and (s[:v.team] == 0).all()
    assert torch.isfinite(o["guard"]).all()


def test_state_shape():
    pos, vel, yaw, al, ar, tl = _inputs()
    st = build_state(CFG, pos, vel, al, ar, tl, 2, 1)
    assert st.shape == (3, STATE_DIM) and st.shape[-1] == STATE_DIM


def test_zone_centre_at_69_70():
    """Interface change (S2 Task 9 fix round 1): indices 69-70 of every drone's observation, and 59-60 of the
    central state, are the zone centre's x, y relative to the arena centre (m). Nothing before them moved."""
    pos, vel, yaw, al, ar, tl = _inputs()
    zc = torch.tensor([[0.7, -1.3], [0.0, 0.0], [-2.0, 0.5]])
    ar = Arenas(ar.side_m, ar.half_m, zc, ar.zone_radius_m, ar.band)
    v = ObsView()
    assert v.zone_centre == slice(69, 71) and v.slot(7).stop == 69
    o = build_obs(CFG, pos, vel, yaw, al, ar, tl, 2, 1)
    for team in ("guard", "strike"):
        assert torch.equal(o[team][..., 69:71], zc[:, None, :].expand_as(o[team][..., 69:71]))
        assert torch.equal(o[team][..., v.zone_centre], o[team][..., 69:71])
    # own position + zone centre = position in the arena (walls at +-arena_half)
    g0 = o["guard"][0, 0]
    assert torch.allclose(g0[v.own_pos][:2] + g0[v.zone_centre], pos[0, 0, :2])
    # a drone that is out sees zeros there too (all zeros except team)
    al2 = al.clone()
    al2[:, 2] = False
    s = build_obs(CFG, pos, vel, yaw, al2, ar, tl, 2, 1)["strike"][0, 0]
    assert (s[v.zone_centre] == 0).all()
    st = build_state(CFG, pos, vel, al, ar, tl, 2, 1)
    assert torch.equal(st[:, 59:61], zc) and st.shape[-1] == 61
