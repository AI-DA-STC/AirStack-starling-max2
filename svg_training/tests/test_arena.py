"""Arena and start draws (S2 Task 2)."""
import pathlib
import sys

import pytest
import torch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
from svg_training.core.arena import BANDS, draw_arenas, draw_starts  # noqa: E402
from svg_training.core.game_config import load_game_cfg  # noqa: E402

CFG = load_game_cfg(use_local=False)[0]
N = 20000


def _gen(seed=1):
    return torch.Generator().manual_seed(seed)


def test_sides_zones_and_bands():
    ar = draw_arenas(CFG.arena, N, _gen(), "cpu")
    assert ((ar.side_m >= 4.0) & (ar.side_m <= 16.0)).all()
    for i, name in enumerate(BANDS):
        lo, hi = CFG.arena.bands_m[name]
        s = ar.side_m[ar.band == i]
        assert ((s >= lo) & (s <= hi)).all()
        assert abs(float((ar.band == i).float().mean()) - 1 / 3) < 0.02
    frac = ar.zone_radius_m / ar.side_m
    assert (frac >= 0.10 - 1e-6).all() and (frac <= 0.25 + 1e-6).all()
    need = ar.zone_centre_m.abs() + ar.zone_radius_m[:, None] + 0.5
    assert (need <= ar.half_m[:, None] + 1e-5).all()


def test_band_zero_gives_only_lab():
    ar = draw_arenas(CFG.arena, 2000, _gen(), "cpu", band=0)
    assert (ar.band == 0).all() and (ar.side_m <= 6.0).all() and (ar.side_m >= 4.0).all()


def test_bad_band_raises():
    with pytest.raises(ValueError):
        draw_arenas(CFG.arena, 4, _gen(), "cpu", band=3)


@pytest.mark.parametrize("mode", ["rings", "anywhere"])
def test_starts_are_legal(mode):
    cfg = CFG.replace(**{"starts.mode": mode})
    g = _gen(2)
    ar = draw_arenas(cfg.arena, N, g, "cpu")
    pos = draw_starts(cfg, ar, 3, 2, g)
    assert pos.shape == (N, 5, 3) and (pos[..., 2] == cfg.arena.start_height_m).all()
    assert (pos[..., :2].abs() <= ar.half_m[:, None, None] + 1e-6).all()
    d = (pos[:, 3:, :2] - ar.zone_centre_m[:, None]).norm(dim=-1)
    assert (d > ar.zone_radius_m[:, None]).all()
    ok = torch.ones(N, dtype=torch.bool)
    for a, b in [(0, 1), (0, 2), (1, 2), (3, 4)]:
        ok &= (pos[:, a, :2] - pos[:, b, :2]).norm(dim=-1) >= cfg.starts.spacing_m - 1e-6
    if mode == "anywhere":
        assert float(ok.float().mean()) >= 0.99


def test_rings_geometry():
    g = _gen(3)
    ar = draw_arenas(CFG.arena, 500, g, "cpu", band=2)
    pos = draw_starts(CFG, ar, 4, 2, g)
    inset = ar.half_m[:, None] - CFG.starts.strike_inset_m
    s = pos[:, 4:, :2].abs().amax(dim=-1)
    assert torch.allclose(s, inset.expand_as(s), atol=1e-5)
    r = (pos[:, :4, :2] - ar.zone_centre_m[:, None]).norm(dim=-1)
    assert torch.allclose(r, (ar.zone_radius_m + CFG.starts.guard_ring_gap_m)[:, None].expand_as(r), atol=0.1)   # a wall clamp can move a drone by up to 0.05 m


def test_unknown_start_mode_raises():
    g = _gen()
    ar = draw_arenas(CFG.arena, 4, g, "cpu")
    with pytest.raises(ValueError):
        draw_starts(CFG.replace(**{"starts.mode": "nowhere"}), ar, 1, 1, g)
