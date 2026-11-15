"""Starling layer: commander copy + safety filter on every pair + fitted PX4 model in the S2 game (S2 Task 4).

CPU, few games, made-up numbers. The parameter file is real_exploratory_v0 (exploratory)."""
import pathlib
import sys

import pytest
import torch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
from svg_training.core.game import GUARD_WIN, Scenario, SvgGame  # noqa: E402
from svg_training.core.game_config import load_game_cfg  # noqa: E402
from svg_training.core.safety_filter import team_pair_mask  # noqa: E402
from svg_training.core.starling_layer import StarlingLayer  # noqa: E402
from svg_training.models import fitted  # noqa: E402
from svg_training.models.fitted import FittedResponse  # noqa: E402

CFG = load_game_cfg(use_local=False)[0]
PARAMS = ROOT / "params" / "real_exploratory_v0.toml"
N = 2
STEPS_10_S = 200


def starling(cfg=CFG, iterations=50, **extra):
    """Starling layer on; 50 sweeps keep the CPU tests fast (test setting; one or two pairs converge in fewer)."""
    return cfg.replace(**{"starling.enabled": True, "starling.filter_iterations": iterations, **extra})


def make(cfg, side, starts, guards=1, strikes=1, zone=((0.0, 3.0), 0.4)):
    return SvgGame(cfg, N, guards, strikes, device="cpu", scenario=Scenario("t", side, zone[0], zone[1],
                                                                            tuple(starts)))


def act(g_cmd, s_cmd):
    """g_cmd / s_cmd: list of (vx, vy, vz) per drone in [-1, 1]; the same in every game."""
    def team(cmds):
        a = torch.zeros(N, len(cmds), 4)
        a[..., :3] = torch.tensor(cmds, dtype=torch.float32)
        return a
    return {"guard": team(g_cmd), "strike": team(s_cmd)}


def hdist(g, i, j):
    return (g.pos_m[:, i, :2] - g.pos_m[:, j, :2]).norm(dim=-1)


def min_horizontal_distance(starling_on: bool, preset: str) -> float:
    """1v1 head-on from (-1, 0) and (1, 0), each at its team cap, for 10 s; closest horizontal distance."""
    cfg = CFG.replace(preset=preset, **{"contact.contact_m": 0.0})      # contact preset: no tags in this test
    if starling_on:
        cfg = starling(cfg)
    g = make(cfg, 8.0, ((-1.0, 0.0), (1.0, 0.0)))
    lo = 9.0
    for _ in range(STEPS_10_S):
        out = g.step(act([(1.0, 0.0, 0.0)], [(-1.0, 0.0, 0.0)]))
        assert not out.done.any()
        lo = min(lo, float(hdist(g, 0, 1).min()))
    return lo


def test_starling_keeps_opposite_teams_apart():
    # every pair is filtered: the 1.10 m keep-out holds up to the position-setpoint leak (1.083 m in T4)
    assert min_horizontal_distance(starling_on=True, preset="partner") >= 1.0
    # contact preset: team mask only, so a Guard and a Strike drone meet
    assert min_horizontal_distance(starling_on=True, preset="contact") < 0.5


def test_starling_keeps_teammates_apart():
    starts = ((-1.0, 0.0), (1.0, 0.0), (3.5, -3.5))
    cmd = act([(1.0, 0.0, 0.0), (-1.0, 0.0, 0.0)], [(0.0, 0.0, 0.0)])
    lo = {}
    for name, cfg in (("starling", starling()), ("pure", CFG)):
        g = make(cfg, 8.0, starts, guards=2, strikes=1)
        lo[name] = 9.0
        for _ in range(120):
            g.step(cmd)
            lo[name] = min(lo[name], float(hdist(g, 0, 1).min()))
    assert lo["starling"] >= 1.0
    assert lo["pure"] < 0.1                                             # teammates pass through


def test_starling_speed_ratio():
    # full stick +x for 10 s in a 16 m arena; speed over the last second. Not 4 s as first planned: the fitted
    # PX4 model is underdamped (period about 9 s), so at 4 s the Guard drone is at 0.29 m/s and the Strike drone
    # at 0.52 m/s, the same as models/fitted.FittedResponse alone; by 10 s both are within 0.02 m/s.
    g = make(starling(), 16.0, ((-7.0, 3.0), (-7.0, -3.0)), zone=((6.0, 0.0), 1.0))
    xs = []
    for _ in range(STEPS_10_S):
        g.step(act([(1.0, 0.0, 0.0)], [(1.0, 0.0, 0.0)]))
        xs.append(g.pos_m[:, :, 0].clone())
    speed = (xs[-1] - xs[-21]) / 1.0                                     # [N, 2]
    guard_speed, strike_speed = float(speed[:, 0].mean()), float(speed[:, 1].mean())
    assert strike_speed == pytest.approx(0.5, abs=0.02) and guard_speed == pytest.approx(0.5 / 1.5, abs=0.02)


def _local_cfg(tmp_path, text):
    (tmp_path / "partner_rules.toml").write_text(text)
    return load_game_cfg(local_dir=tmp_path)[0]


def test_partner_speed_above_stick_cap_raises(tmp_path):
    cfg = _local_cfg(tmp_path, "[partner_rules]\nstrike_units_per_step = 0.035\n")   # made-up: 0.7 m/s
    assert cfg.team_speed_mps("strike") == pytest.approx(0.7)
    SvgGame(cfg, 2, 1, 1, device="cpu")                                  # pure rules: no stick, no cap
    with pytest.raises(ValueError, match="stick cap"):
        SvgGame(starling(cfg), 2, 1, 1, device="cpu")


def test_guard_speed_above_stick_cap_raises(tmp_path):
    cfg = _local_cfg(tmp_path, "[partner_rules]\nguard_units_per_step = 0.03\n")     # made-up: 0.6 m/s
    with pytest.raises(ValueError, match="stick cap"):
        SvgGame(starling(cfg), 2, 1, 1, device="cpu")


def test_starling_walls_and_height_band():
    g = make(starling(), 4.0, ((1.0, 1.0), (-1.5, -1.5)), zone=((-1.0, 1.0), 0.4))
    lim = 4.0 / 2 - CFG.arena.wall_margin_m
    z_lo = CFG.arena.height_band_m[0]
    for _ in range(STEPS_10_S):
        out = g.step(act([(1.0, 0.0, -1.0)], [(0.0, 0.0, 0.0)]))
        assert not out.done.any()
        assert (g.pos_m[:, 0, 0] <= lim + 0.01).all() and (g.pos_m[:, 0, 2] >= z_lo - 0.01).all()
    assert g.pos_m[:, 0, 0].min() > lim - 0.01 and g.pos_m[:, 0, 2].max() < z_lo + 0.01   # it got there
    assert (g.vel_mps[:, 0, 0].abs() < 1e-6).all() and (g.vel_mps[:, 0, 2].abs() < 1e-6).all()
    # back out: the model's speed was stopped at the wall, so the drone leaves it at once
    for _ in range(10):
        g.step(act([(-1.0, 0.0, 0.0)], [(0.0, 0.0, 0.0)]))
    assert (g.pos_m[:, 0, 0] < lim - 0.01).all()


def test_starling_height_band_leave():
    cfg = starling(**{"arena.walls": "leave"})
    g = make(cfg, 8.0, ((1.0, 1.0), (-3.0, -3.0)), zone=((-1.0, 1.0), 0.4))
    for _ in range(STEPS_10_S):
        g.step(act([(0.0, 0.0, -1.0)], [(0.0, 0.0, 0.0)]))
    assert not g.alive[:, 0].any() and g.alive[:, 1].all()               # left through the floor of the band


def test_rule_breach_flag():
    keep = {"rules.keepout_guard_m": 1.5, "rules.keepout_strike_m": 1.5}   # made-up test keep-outs
    breach = {}
    for name, cfg in (("starling", starling(CFG.replace(**keep))), ("pure", CFG.replace(**keep))):
        g = make(cfg, 8.0, ((-1.6, 0.0), (1.6, 0.0)))
        breach[name] = False
        for _ in range(STEPS_10_S):
            out = g.step(act([(1.0, 0.0, 0.0)], [(-1.0, 0.0, 0.0)]))
            breach[name] |= bool(out.info["rule_breach"].any())
    assert breach["starling"]            # push-apart off (D3): only the 1.10 m filter keeps them apart
    assert not breach["pure"]            # the push-apart holds 1.5 m


def test_starling_reports_filter_corrected():
    g = make(starling(), 8.0, ((-1.0, 0.0), (1.0, 0.0)))
    seen = torch.zeros(N, 2, dtype=torch.bool)
    for _ in range(60):
        seen |= g.step(act([(1.0, 0.0, 0.0)], [(-1.0, 0.0, 0.0)])).info["filter_corrected"]
    assert seen.all()
    pure = make(CFG, 8.0, ((-1.0, 0.0), (1.0, 0.0)))
    assert not pure.step(act([(1.0, 0.0, 0.0)], [(-1.0, 0.0, 0.0)])).info["filter_corrected"].any()


def test_fitted_filter_kwargs_passthrough(monkeypatch):
    seen = {}
    real = fitted.filter_velocities

    def spy(*args, **kwargs):
        seen.update(kwargs)
        return real(*args, **kwargs)

    monkeypatch.setattr(fitted, "filter_velocities", spy)
    r = FittedResponse(2, 2, PARAMS, device="cpu", safety_filter=True, pair_mask=team_pair_mask(2, 0),
                       filter_iterations=1000, filter_kwargs={"iterations": 7})
    r.reset(torch.ones(2, 2, dtype=torch.bool), torch.tensor([[[0.0, 0, 1.2], [1.0, 0, 1.2]]] * 2))
    r.step(torch.zeros(2, 2, 3))
    assert seen["iterations"] == 7


def test_fitted_set_pair_mask_per_game():
    pos = torch.tensor([[[0.0, 0, 1.2], [0.8, 0, 1.2]]] * 2)
    r = FittedResponse(2, 2, PARAMS, device="cpu", safety_filter=True, pair_mask=team_pair_mask(2, 0),
                       filter_iterations=200)
    r.reset(torch.ones(2, 2, dtype=torch.bool), pos)
    mask = team_pair_mask(2, 0).expand(2, 2, 2).clone()
    mask[1] = False                                                      # game 1: the pair is not filtered
    r.set_pair_mask(mask)
    r.step(torch.tensor([[[0.5, 0, 0], [-0.5, 0, 0]]] * 2), pos)
    assert r.corrected[0].all() and not r.corrected[1].any()


def test_dropout_excluded_from_filter():
    # layer level: drone 0 is out but sits 0.3 m from drone 1, which flies at it; nothing is corrected and
    # drone 1 moves exactly as if drone 0 were far away
    def run(pos0):
        layer = StarlingLayer(starling(), 1, 2, 1, "cpu")
        pos = torch.tensor([[pos0, [0.3, 0.0, 1.2], [4.0, 4.0, 1.2]]])
        layer.reset(torch.ones(1, 3, dtype=torch.bool), pos)
        alive = torch.tensor([[False, True, True]])
        cmd = torch.tensor([[[0.0, 0, 0], [-0.33, 0, 0], [0.0, 0, 0]]])
        corr = torch.zeros(1, 3, dtype=torch.bool)
        for _ in range(20):
            p, _, c = layer.step(cmd, pos, alive)
            corr |= c
            pos = torch.cat((torch.tensor([[pos0]]), p[:, 1:]), dim=1)
        return pos[0, 1], corr
    near, corr_near = run([0.0, 0.0, 1.2])
    far, _ = run([-50.0, -50.0, 1.2])
    assert not corr_near.any()
    assert torch.equal(near, far)
    # game level: an out drone is never reported corrected
    g = make(starling(), 8.0, ((-1.0, 0.0), (1.0, 0.0), (0.0, -3.0)), guards=2, strikes=1)
    g.schedule_dropout(torch.zeros(N, dtype=torch.long), torch.ones(N, dtype=torch.long))
    for k in range(60):
        out = g.step(act([(1.0, 0.0, 0.0), (-1.0, 0.0, 0.0)], [(0.0, 0.0, 0.0)]))
        if k >= 1:
            assert not out.info["filter_corrected"][:, 0].any()
            assert not out.info["filter_corrected"][:, 1].any()          # nobody left near drone 1


def test_starling_game_resets_layer_with_new_game():
    cfg = starling(**{"rules.game_steps": 20})
    g = make(cfg, 8.0, ((-1.0, 0.0), (1.0, 0.0)))
    for _ in range(20):
        out = g.step(act([(1.0, 0.0, 0.0)], [(0.0, 1.0, 0.0)]))
    assert out.done.all() and (out.outcome == GUARD_WIN).all()
    m = g._starling.model
    assert torch.allclose(m.vel_mps, torch.zeros_like(m.vel_mps)) and m._fresh.all()
    out = g.step(act([(0.0, 0.0, 0.0)], [(0.0, 0.0, 0.0)]))              # at rest at the starts: stays put
    assert torch.allclose(g.pos_m[:, 0, :2], torch.tensor([-1.0, 0.0]).expand(N, 2), atol=1e-5)
