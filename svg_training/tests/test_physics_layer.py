"""The physics backend in the S2 game (S2b Task 4): command chain + PX4 1.14 cascade on the torch reference world.

CPU, few games, made-up numbers, committed neutral game values (no local file). Observed in the training
simulator (PyTorch reference world), not a flight result.
"""
import dataclasses
import math
import os
import pathlib
import subprocess
import sys

import pytest
import torch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
from svg_training.core.game import Scenario, SvgGame  # noqa: E402
from svg_training.core.game_config import load_game_cfg  # noqa: E402
from svg_training.core.physics_layer import PhysicsLayer, load_game_physics_params  # noqa: E402
from svg_training.core.starling_layer import StarlingLayer  # noqa: E402
from svg_training.models.physics_drone import PhysicsDrone  # noqa: E402
from svg_training.models.rigid_body import TorchRigidBodyWorld  # noqa: E402

CFG = load_game_cfg(use_local=False)[0]
N = 2
STEPS_10_S = 200
ENV = {**os.environ, "PYTHONPATH": str(ROOT / "source")}


def starling(cfg=CFG, iterations=50, **extra):
    """Fitted backend (S2 Starling layer); 50 sweeps keep the CPU tests fast."""
    return cfg.replace(**{"starling.enabled": True, "starling.filter_iterations": iterations, **extra})


def physics(cfg=CFG, iterations=50, **extra):
    return starling(cfg, iterations, **{"starling.backend": "physics", **extra})


PARAMS = load_game_physics_params(physics())
A = PARAMS.airframe


def world(n, m):
    return TorchRigidBodyWorld(n, m, A, PARAMS.physics_dt_s, "cpu")


def make(cfg, side, starts, guards=1, strikes=1, zone=((0.0, 3.0), 0.4), n=N):
    sc = Scenario("t", side, zone[0], zone[1], tuple(starts))
    w = world(n, guards + strikes) if cfg.starling.backend == "physics" else None
    return SvgGame(cfg, n, guards, strikes, device="cpu", scenario=sc, world=w)


def act(g_cmd, s_cmd, n=N, yaw=0.0):
    """g_cmd / s_cmd: list of (vx, vy, vz) per drone in [-1, 1]; the same in every game."""
    def team(cmds):
        a = torch.zeros(n, len(cmds), 4)
        a[..., :3] = torch.tensor(cmds, dtype=torch.float32)
        a[..., 3] = yaw
        return a
    return {"guard": team(g_cmd), "strike": team(s_cmd)}


def hdist(g, i, j):
    return (g.pos_m[:, i, :2] - g.pos_m[:, j, :2]).norm(dim=-1)


# ------------------------------------------------------------------------------------- one chain, both backends
def test_physics_and_starling_same_first_setpoint():         # Review Focus 3
    starts = ((-0.6, 0.0), (0.6, 0.0), (0.0, 1.5))            # close enough for the filter to act on tick 1
    cmd = act([(1.0, 0.0, 0.0), (-1.0, 0.2, 0.0)], [(0.0, -1.0, 0.3)])
    fitted = make(starling(), 8.0, starts, guards=2)
    phys = make(physics(), 8.0, starts, guards=2)
    out_f, out_p = fitted.step(cmd), phys.step(cmd)
    for a, b in zip(fitted._starling.model.chain.setpoint, phys._starling.chain.setpoint):
        assert torch.equal(a, b)
    assert torch.equal(out_f.info["filter_corrected"], out_p.info["filter_corrected"])
    assert out_p.info["filter_corrected"].any()                # the filter really acted
    assert isinstance(fitted._starling, StarlingLayer) and isinstance(phys._starling, PhysicsLayer)


def test_backends_draw_identical_starts():                   # D15
    a = SvgGame(starling(), 32, 2, 1, device="cpu", seed=5)
    b = SvgGame(physics(), 32, 2, 1, device="cpu", seed=5, world=world(32, 3))
    for k in range(3):
        if k:
            a.reset(seed=5 + k)
            b.reset(seed=5 + k)
        assert torch.equal(a.pos_m, b.pos_m) and torch.equal(a.start_miss, b.start_miss)
        for f in ("half_m", "zone_centre_m", "zone_radius_m", "band"):
            assert torch.equal(getattr(a.arenas, f), getattr(b.arenas, f)), f
        assert torch.equal(a.gen.get_state(), b.gen.get_state())   # the backend drew nothing from the generator
    zero = {"guard": torch.zeros(32, 2, 4), "strike": torch.zeros(32, 1, 4)}
    a.step(zero)
    b.step(zero)
    assert torch.equal(a.gen.get_state(), b.gen.get_state())


def test_motion_label():
    assert SvgGame(CFG, 2, 1, 1, device="cpu").motion == "pure"
    assert SvgGame(starling(), 2, 1, 1, device="cpu").motion == "starling"
    assert SvgGame(physics(), 2, 1, 1, device="cpu", world=world(2, 2)).motion == \
        "physics/torch-reference (test oracle)"


# ------------------------------------------------------------------------------------- the StarlingLayer contract
def min_horizontal_distance(backend: str, preset: str) -> float:
    """1v1 head-on from (-1, 0) and (1, 0), each at its team cap, for 10 s; closest horizontal distance."""
    cfg = CFG.replace(preset=preset, **{"contact.contact_m": 0.0})      # contact preset: no tags in this test
    cfg = physics(cfg) if backend == "physics" else starling(cfg)
    g = make(cfg, 8.0, ((-1.0, 0.0), (1.0, 0.0)))
    lo = 9.0
    for _ in range(STEPS_10_S):
        out = g.step(act([(1.0, 0.0, 0.0)], [(-1.0, 0.0, 0.0)]))
        assert not out.done.any() and not out.info["upset"].any()
        lo = min(lo, float(hdist(g, 0, 1).min()))
    return lo


def test_physics_keeps_opposite_teams_apart():
    assert min_horizontal_distance(backend="physics", preset="partner") >= 1.0
    assert min_horizontal_distance(backend="physics", preset="contact") < 0.5     # team mask only: they meet


def test_physics_speed_ratio():
    # full stick +x for 6 s in a 16 m arena; speeds over the last second
    g = make(physics(), 16.0, ((-7.0, 3.0), (-7.0, -3.0)), zone=((6.0, 0.0), 1.0))
    xs = []
    for _ in range(120):
        out = g.step(act([(1.0, 0.0, 0.0)], [(1.0, 0.0, 0.0)]))
        assert not out.info["upset"].any()
        xs.append(g.pos_m[:, :, 0].clone())
    speed = (xs[-1] - xs[-21]) / 1.0                                     # [N, 2], 5-6 s
    assert float(speed[:, 1].mean()) == pytest.approx(0.5, abs=0.03)
    assert float(speed[:, 0].mean()) == pytest.approx(0.5 / 1.5, abs=0.03)


def test_physics_walls_and_height_band():
    g = make(physics(), 4.0, ((1.0, 1.0), (-1.5, -1.5)), zone=((-1.0, 1.0), 0.4))
    lim = 4.0 / 2 - CFG.arena.wall_margin_m
    z_lo = CFG.arena.height_band_m[0]
    for _ in range(STEPS_10_S):
        out = g.step(act([(1.0, 0.0, -1.0)], [(0.0, 0.0, 0.0)]))
        assert not out.done.any() and not out.info["upset"].any()
        assert (g.pos_m[:, 0, 0] <= lim + 0.01).all() and (g.pos_m[:, 0, 2] >= z_lo - 0.01).all()
    assert g.pos_m[:, 0, 0].min() > lim - 0.01 and g.pos_m[:, 0, 2].max() < z_lo + 0.01   # it got there
    drone = g._starling.drone                                            # the world holds the clamped state
    assert torch.equal(drone.pos_m, g.pos_m) and (drone.vel_mps[:, 0, 0] == 0).all()
    for _ in range(20):                                                   # back out
        g.step(act([(-1.0, 0.0, 0.0)], [(0.0, 0.0, 0.0)]))
    assert (g.pos_m[:, 0, 0] < lim - 0.01).all()


def test_physics_dropout_parked_and_excluded():
    g = make(physics(), 8.0, ((-1.0, 0.0), (1.0, 0.0), (0.0, -3.0)), guards=2, strikes=1)
    g.schedule_dropout(torch.zeros(N, dtype=torch.long), torch.ones(N, dtype=torch.long))
    for k in range(60):
        out = g.step(act([(1.0, 0.0, 0.0), (-1.0, 0.0, 0.0)], [(0.0, 0.0, 0.0)]))
        assert torch.isfinite(g.pos_m).all() and torch.isfinite(g._starling.drone.pos_m).all()
        assert not out.info["upset"].any()
        if k >= 1:
            assert not g.alive[:, 0].any()
            assert (g.pos_m[:, 0] == 1.0e3).all()                         # parked by the game
            assert not out.info["filter_corrected"][:, :2].any()          # drone 1 has nobody near it
    # the out drone is restarted at its parked position every step: at rest there in the world
    d = g._starling.drone
    assert torch.allclose(d.pos_m[:, 0], torch.full((N, 3), 1.0e3), atol=0.05)
    assert d.vel_mps[:, 0].abs().max() < 0.05


def test_physics_out_drone_never_corrects_another():
    # layer level: drone 0 is out but sits 0.3 m from drone 1, which flies at it; nothing is corrected
    cfg = physics()
    pos = torch.tensor([[[0.0, 0.0, 1.2], [0.3, 0.0, 1.2], [4.0, 4.0, 1.2]]])
    layer = PhysicsLayer(cfg, 1, 2, 1, "cpu", world(1, 3))
    layer.reset(torch.ones(1, 3, dtype=torch.bool), pos)
    alive = torch.tensor([[False, True, True]])
    cmd = torch.tensor([[[0.0, 0, 0], [-0.33, 0, 0], [0.0, 0, 0]]])
    for _ in range(20):
        p, _, c = layer.step(cmd, pos, alive)
        assert not c.any()
        pos = torch.cat((pos[:, :1], p[:, 1:]), dim=1)


def test_physics_needs_world():
    with pytest.raises(ValueError, match="IsaacWorld or TorchRigidBodyWorld"):
        SvgGame(physics(), 2, 1, 1, device="cpu")
    with pytest.raises(ValueError, match="world holds"):
        SvgGame(physics(), 2, 1, 1, device="cpu", world=world(2, 3))
    with pytest.raises(ValueError, match="only by the physics backend"):
        SvgGame(starling(), 2, 1, 1, device="cpu", world=world(2, 2))
    with pytest.raises(ValueError, match="enabled"):
        SvgGame(CFG.replace(**{"starling.backend": "physics"}), 2, 1, 1, device="cpu", world=world(2, 2))


def test_physics_partner_speed_above_stick_cap_raises(tmp_path):
    (tmp_path / "partner_rules.toml").write_text("[partner_rules]\nstrike_units_per_step = 0.035\n")  # made-up
    cfg = load_game_cfg(local_dir=tmp_path)[0]
    assert cfg.team_speed_mps("strike") == pytest.approx(0.7)
    with pytest.raises(ValueError, match="stick cap"):
        SvgGame(physics(cfg), 2, 1, 1, device="cpu", world=world(2, 2))


# ------------------------------------------------------------------------------------- upset, NaN, writes, yaw
def test_upset_flag():
    g = make(physics(), 8.0, ((-1.0, 0.0), (1.0, 0.0)), n=3)
    still = act([(0.0, 0.0, 0.0)], [(0.0, 0.0, 0.0)], n=3)
    out = g.step(still)
    assert not out.info["upset"].any()
    w = g._starling.world
    pos, quat, vel, ang = w.state()
    roll90 = torch.tensor([math.cos(math.pi / 4), math.sin(math.pi / 4), 0.0, 0.0])
    mask = torch.zeros(3, 2, dtype=torch.bool)
    mask[1, 0] = True                                                     # game 1, drone 0 only
    w.write_state(mask, pos, torch.where(mask[..., None], roll90, quat), vel, ang)
    out = g.step(still)
    assert out.info["upset"].tolist() == [False, True, False]
    for _ in range(5):                                                    # stays set for the rest of that game
        assert g.step(still).info["upset"].tolist() == [False, True, False]
    assert g._starling.drone.nonfinite_count == 0


def test_upset_clears_with_the_new_game():
    g = make(physics(**{"rules.game_steps": 4}), 8.0, ((-1.0, 0.0), (1.0, 0.0)), n=2)
    still = act([(0.0, 0.0, 0.0)], [(0.0, 0.0, 0.0)])
    g.step(still)
    w = g._starling.world
    pos, quat, vel, ang = w.state()
    w.write_state(torch.ones(2, 2, dtype=torch.bool), pos, quat, vel, torch.full_like(ang, float("nan")))
    for _ in range(3):
        out = g.step(still)
    assert out.done.all() and out.info["upset"].all()                     # the game that just ended
    assert g._starling.drone.nonfinite_count > 0
    out = g.step(still)                                                   # the new game: restarted, finite
    assert not out.info["upset"].any() and torch.isfinite(g.pos_m).all()


def test_nonfinite_setpoint_is_replaced_and_counted():
    """px4_cascade needs finite setpoints. At the crossing a NaN feed-forward acts as 0 (PX4's addIfNotNan), a
    NaN position setpoint as the drone's own position, a NaN yaw as its own heading; each one is counted."""
    def fly(p_sp, v_ff, a_ff, yaw):
        d = PhysicsDrone(world(1, 2), PARAMS, "cpu")
        start = torch.tensor([[[0.0, 0.0, 1.2], [2.0, 0.0, 1.2]]])
        d.reset(torch.ones(1, 2, dtype=torch.bool), start, torch.zeros(1, 2))
        for _ in range(5):
            d.step_setpoint(p_sp(d), v_ff, a_ff, yaw, torch.zeros(1, 2))
        return d
    nan = float("nan")
    hold = (lambda d: d.pos_m.clone())
    zero = torch.zeros(1, 2, 3)
    ref = fly(hold, zero, zero, torch.zeros(1, 2))
    bad_ff = torch.tensor([[[nan, 0.0, 0.0], [0.0, 0.0, 0.0]]])
    d = fly(hold, bad_ff, bad_ff, torch.zeros(1, 2))
    assert torch.equal(d.pos_m, ref.pos_m) and int(d.nonfinite_count) == 10       # 5 ticks x (v_ff, a_ff)
    d = fly(lambda d: torch.full((1, 2, 3), nan), zero, zero, torch.full((1, 2), nan))
    assert torch.equal(d.pos_m, ref.pos_m) and int(d.nonfinite_count) == 20       # 5 x 2 drones x (p_sp, yaw)
    assert torch.isfinite(d.pos_m).all() and not d.upset.any()


class _CountingWorld(TorchRigidBodyWorld):
    """Counts calls of the protocol's two write methods (reset writes through write_state: counted once)."""
    writes = 0
    _in_reset = False

    def reset(self, *a):
        type(self).writes += 1
        self._in_reset = True
        super().reset(*a)
        self._in_reset = False

    def write_state(self, *a):
        type(self).writes += 1 - self._in_reset
        super().write_state(*a)


def test_at_most_two_world_writes_per_tick():                # D9
    w = _CountingWorld(N, 3, A, PARAMS.physics_dt_s, "cpu")
    g = SvgGame(physics(**{"rules.game_steps": 3, "dropout_fraction": 1.0}), N, 2, 1, device="cpu", seed=3,
                world=w)
    cmd = act([(1.0, 0.0, 0.0), (0.0, 1.0, 0.0)], [(-1.0, 0.0, 0.0)])
    for _ in range(7):                                                    # games end and restart; drop-outs
        before = _CountingWorld.writes
        g.step(cmd)
        assert _CountingWorld.writes - before <= 2


def _heading(q):
    return torch.atan2(2 * (q[..., 0] * q[..., 3] + q[..., 1] * q[..., 2]), 1 - 2 * (q[..., 2] ** 2 + q[..., 3] ** 2))


def test_game_passes_its_yaw_to_the_drone(monkeypatch):      # D8: setpoint = game yaw, feed-forward = yaw command
    seen = []
    real = PhysicsDrone.step_setpoint

    def spy(self, p_sp, v_ff, a_ff, yaw_sp, yaw_rate):
        seen.append((yaw_sp.clone(), yaw_rate.clone()))
        return real(self, p_sp, v_ff, a_ff, yaw_sp, yaw_rate)

    monkeypatch.setattr(PhysicsDrone, "step_setpoint", spy)
    g = make(physics(), 8.0, ((-1.0, 0.0), (1.0, 0.0)))
    for _ in range(3):
        g.step(act([(0.0, 0.0, 0.0)], [(0.0, 0.0, 0.0)], yaw=0.5))
        assert torch.equal(seen[-1][0], g.yaw)
        assert torch.allclose(seen[-1][1], torch.full((N, 2), 0.5 * CFG.yaw_rate_max_rad_s))
    assert float(g.yaw.min()) == pytest.approx(3 * 0.5 * CFG.yaw_rate_max_rad_s * 0.05)


def _yaw_step(motor_lag: bool) -> list[float]:
    """One drone, hover, yaw setpoint stepped 0 -> 0.3 rad (ENU, counter-clockwise), 10 s; heading every tick."""
    p = dataclasses.replace(PARAMS, motor_lag=motor_lag)
    d = PhysicsDrone(world(1, 1), p, "cpu")
    d.reset(torch.ones(1, 1, dtype=torch.bool), torch.tensor([[[0.0, 0.0, 1.2]]]), torch.zeros(1, 1))
    out = []
    for _ in range(200):
        d.step_setpoint(d.pos_m.clone(), torch.zeros(1, 1, 3), torch.zeros(1, 1, 3), torch.tensor([[0.3]]),
                        torch.zeros(1, 1))
        out.append(float(_heading(d.quat_wxyz)[0, 0]))
    return out


def test_yaw_step_turns_the_right_way_motor_lag_off():
    h = _yaw_step(motor_lag=False)
    assert all(abs(x - 0.3) < 0.01 for x in h[40:])                     # settled within 2 s, ENU sign right


@pytest.mark.xfail(strict=False, reason="OPEN (Task 4 finding, for Task 3's cascade): with the drone's 55/85 ms "
                   "motor lag a 0.3 rad yaw step grows into a yaw limit cycle (rotors hit u = 0, yaw-rate "
                   "integrator pinned at MC_YR_INT_LIM; PX4's allocator-saturation feedback is not ported)")
def test_yaw_step_settles_with_motor_lag():
    h = _yaw_step(motor_lag=True)
    assert all(abs(x - 0.3) < 0.05 for x in h[100:])


def test_core_imports_no_isaac():                             # Review Focus 4
    code = ("import svg_training.core.game, svg_training.core.physics_layer, svg_training.models.px4_cascade, sys; "
            "assert not {m for m in sys.modules if m.split('.')[0] in ('isaaclab', 'isaacsim', 'omni', 'pxr')}")
    assert subprocess.run([sys.executable, "-c", code], env=ENV).returncode == 0
