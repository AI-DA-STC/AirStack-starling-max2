"""Interface v0.2 (Phase 5 Task S2; owner approved 18 Nov 2026 ~18:20, plan section 12 item 1): v0.1 (71 numbers) with the height band's
floor and ceiling (m, world z) appended at indices 71-72. Opt-in: the default game and every v0.1 consumer keep the 71 numbers byte for
byte; only the 5.2 hangar games (training and evaluation) serve 73."""
import pathlib
import sys

import torch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
from svg_training.core.arena import Arenas  # noqa: E402
from svg_training.core.game_config import load_game_cfg  # noqa: E402
from svg_training.core.observations import (INTERFACE_LAYOUTS, INTERFACE_VERSION, INTERFACE_VERSION_V02, OBS_DIM, OBS_DIM_V02,  # noqa: E402
                                            ObsView, build_obs, obs_v02)

CFG = load_game_cfg(use_local=False)[0]


def _inputs():
    n = 3
    pos = torch.tensor([[[1.0, 0.0, 1.2], [0.0, 2.0, 0.9], [-1.0, -1.0, 1.5]]]).repeat(n, 1, 1)  # 2 Guard, 1 Strike
    vel = torch.tensor([[[0.1, 0.0, 0.0], [0.0, 0.2, 0.0], [0.3, 0.0, 0.1]]]).repeat(n, 1, 1)
    ar = Arenas(torch.full((n,), 8.0), torch.full((n,), 4.0), torch.zeros(n, 2), torch.full((n,), 1.0), torch.ones(n, dtype=torch.long))
    return pos, vel, torch.zeros(n, 3), torch.ones(n, 3, dtype=torch.bool), ar, torch.full((n,), 30.0)


def test_versions_and_widths():
    assert INTERFACE_VERSION == "0.1" and OBS_DIM == 71           # the default game still serves v0.1
    assert INTERFACE_VERSION_V02 == "0.2" and OBS_DIM_V02 == 73
    assert INTERFACE_LAYOUTS == {"0": 69, "0.1": 71, "0.2": 73}
    v = ObsView()
    assert v.height_band == slice(71, 73) and v.zone_centre.stop == 71


def test_v02_appends_floor_and_ceiling_and_moves_nothing():
    pos, vel, yaw, al, ar, tl = _inputs()
    v01 = build_obs(CFG, pos, vel, yaw, al, ar, tl, 2, 1)
    floor, ceiling = CFG.arena.height_band_m
    for team in ("guard", "strike"):
        v02 = obs_v02(v01[team], CFG)
        assert v02.shape[-1] == OBS_DIM_V02
        assert torch.equal(v02[..., :OBS_DIM], v01[team])          # indices 0-70 unchanged, bit for bit
        assert torch.equal(v02[..., 71], torch.full_like(v02[..., 71], floor))
        assert torch.equal(v02[..., 72], torch.full_like(v02[..., 72], ceiling))


def test_v02_out_drone_sees_zero_band():
    pos, vel, yaw, al, ar, tl = _inputs()
    al[:, 2] = False
    v02 = obs_v02(build_obs(CFG, pos, vel, yaw, al, ar, tl, 2, 1)["strike"], CFG)
    assert (v02[..., ObsView.height_band] == 0).all()             # out: zeros, as every other field but team


def test_default_build_obs_is_unchanged():
    """The v0.1 output is what it was before v0.2 existed: same width, the same numbers (fixed values below were read before the change)."""
    pos, vel, yaw, al, ar, tl = _inputs()
    o = build_obs(CFG, pos, vel, yaw, al, ar, tl, 2, 1)
    assert o["guard"].shape == (3, 2, 71) and o["strike"].shape == (3, 1, 71)
    g0 = o["guard"][0, 0]
    assert torch.equal(g0[:3], pos[0, 0]) and g0[ObsView.zone_radius] == 1.0 and g0[ObsView.arena_half] == 4.0


def test_v01_consumers_unaffected():
    """The stand-in loader still demands the default version; the adapters still serve 71."""
    from svg_training.opponents import learned
    assert learned.INTERFACE_VERSION == "0.1" and learned.OBS_DIM == 71
