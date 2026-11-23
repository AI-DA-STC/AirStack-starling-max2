"""STE task L2.3: landing drones stay filter obstacles (WORK_BREAKDOWN L2.3; ARCHITECTURE section 2, rows Landing and
Physics layer).

With ``[landing] enabled = true`` (PROPOSED; off by default) a drone that is tagged (the study tag) or lost (a drop-out)
leaves the game but does not vanish: it descends at ``land_speed_mps`` (0.6 m/s, the real ``_ours`` configs'
``land_speed_mps``) as an ordinary row of every safety-filter pair until its height is at or below ``touchdown_z_m``
(0.15 m, the ``_ours`` configs' ``land_complete_altitude_m``), then it is parked as an out drone is today. It no longer
acts (its action is ignored), tags, is tagged or scores. The descent enters the commander copy as the flight
commander's LANDING nominal (``swarm_commander.py`` :2086-2087): no stick cap, no ramp, the hold leash, and no walls
(the fence does not act on a LANDING drone). With the setting off (absent, or present with ``enabled = false``) the game
is today's bit for bit (``tests/test_game_tag_off_golden.py``; here: absent = off, and "on with no drone landing" = off).

Tier 1 (fitted backend) and tier 2 (physics backend on the PyTorch reference world, CPU). Made-up positions; CPU.
Observed in the training simulator, not a flight result.
"""
import pathlib
import sys

import pytest
import torch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
from svg_training.core.game import GUARD_WIN, PARK_M, RUNNING, STRIKE_WIN, Scenario, SvgGame  # noqa: E402
from svg_training.core.game_config import LandingCfg, load_game_cfg  # noqa: E402
from svg_training.core.observations import ObsView  # noqa: E402
from svg_training.core.physics_layer import load_game_physics_params  # noqa: E402
from svg_training.models.rigid_body import TorchRigidBodyWorld  # noqa: E402

CFG = load_game_cfg(use_local=False)[0]
N = 2
TICK_S = 0.05
BACKENDS = ("fitted", "physics")
KEEPOUT_M = 1.10                 # the filter distance (2 x safety_radius_m 0.55, params/real_exploratory_v0.toml)
# The keep-out holds up to the position-setpoint leak of the commander copy (1.083 m in T4; the Starling-layer tests
# accept >= 1.0 m: tests/test_starling_layer.py, tests/test_physics_layer.py). This file's own limit, 1.05 m, sits under
# the values measured in test_a_landing_drone_keeps_other_drones_away (1.113 m fitted, 1.093 m physics).
KEEPOUT_TOL_M = 0.05


def cfg_of(backend="fitted", landing=True, iterations=50, **extra):
    """The committed s2 game, Starling layer on (50 filter sweeps keep the CPU tests fast), landing on or off."""
    kw = {"starling.enabled": True, "starling.filter_iterations": iterations, "landing.enabled": landing, **extra}
    if backend == "physics":
        kw["starling.backend"] = "physics"
    return CFG.replace(**kw)


def make(cfg, starts, guards=1, strikes=1, zone=((-2.5, 2.5), 0.4), side=8.0, n=N, seed=0):
    sc = Scenario("t", side, zone[0], zone[1], tuple(starts))
    world = None
    if cfg.starling.backend == "physics":
        p = load_game_physics_params(cfg)
        world = TorchRigidBodyWorld(n, guards + strikes, p.airframe, p.physics_dt_s, "cpu")
    return SvgGame(cfg, n, guards, strikes, device="cpu", scenario=sc, world=world, seed=seed)


def act(g_cmd, s_cmd, n=N):
    """g_cmd / s_cmd: list of (vx, vy, vz) per drone in [-1, 1]; the same in every game."""
    def team(cmds):
        a = torch.zeros(n, len(cmds), 4)
        a[..., :3] = torch.tensor(cmds, dtype=torch.float32)
        return a
    return {"guard": team(g_cmd), "strike": team(s_cmd)}


def drop(g, drone, at_step=1):
    g.schedule_dropout(torch.full((g.num_games,), drone, dtype=torch.long),
                       torch.full((g.num_games,), at_step, dtype=torch.long))


def toward(pos_m, target, gain=2.0):
    """A scripted command [N, 3] in [-1, 1] toward target (x, y, z): proportional, norm capped at 1."""
    d = (torch.tensor(target) - pos_m) * gain
    return d / d.norm(dim=-1, keepdim=True).clamp(min=1.0)


def pair_mask(g):
    chain = g._starling.chain if g.cfg.starling.backend == "physics" else g._starling.model.chain
    return chain.pair_mask


# ------------------------------------------------------------------------------------------------ the setting
def test_off_by_default_and_an_absent_section_is_off(tmp_path):
    assert LandingCfg() == CFG.landing and CFG.landing.enabled is False
    assert (CFG.landing.land_speed_mps, CFG.landing.touchdown_z_m) == (0.6, 0.15)
    path = tmp_path / "g.toml"
    text = (ROOT / "configs" / "s2_game.toml").read_text().replace("enabled = false", "enabled = true", 1)
    path.write_text(text + "\n[landing]\nenabled = true\nland_speed_mps = 0.5\ntouchdown_z_m = 0.1\n")
    cfg = load_game_cfg(path, use_local=False)[0]
    assert cfg.starling.enabled and cfg.landing == LandingCfg(enabled=True, land_speed_mps=0.5, touchdown_z_m=0.1)


@pytest.mark.parametrize("bad", [{"enabled": 1}, {"land_speed_mps": 0.0}, {"land_speed_mps": float("nan")},
                                 {"land_speed_mps": True}, {"touchdown_z_m": -0.1}, {"touchdown_z_m": "0.1"}])
def test_bad_settings_raise(bad):
    with pytest.raises(ValueError, match="landing"):
        LandingCfg(**bad)


def test_unknown_key_raises(tmp_path):
    path = tmp_path / "g.toml"
    path.write_text((ROOT / "configs" / "s2_game.toml").read_text() + "\n[landing]\nenabled = false\nspeed = 1.0\n")
    with pytest.raises(ValueError, match="unknown key"):
        load_game_cfg(path, use_local=False)


def test_landing_needs_the_starling_layer_and_the_partner_preset():
    with pytest.raises(ValueError, match="landing"):
        CFG.replace(**{"landing.enabled": True})                                   # pure rules: planar, no descent
    with pytest.raises(ValueError, match="landing"):
        cfg_of().replace(preset="contact")                                         # contact preset: its own tag
    with pytest.raises(ValueError, match="touchdown"):
        cfg_of(**{"landing.touchdown_z_m": 0.5})                                   # at or above the band's floor


@pytest.mark.parametrize("backend", BACKENDS)
def test_on_with_no_drone_landing_plays_the_game_off_bit_for_bit(backend):
    """No tag, no drop-out: the landing switch changes nothing (positions, velocities, observations, rewards, info),
    except that it adds info["landing"] (all False)."""
    starts = ((0.0, 0.0), (-1.2, 0.0))
    outs = {}
    for on in (False, True):
        g = make(cfg_of(backend, landing=on), starts)
        rows = []
        for _ in range(40):
            o = g.step(act([(0.3, 0.2, 0.0)], [(1.0, 0.0, -0.3)]))
            rows.append((g.pos_m.clone(), g.vel_mps.clone(), o.obs["guard"], o.obs["strike"], o.reward["guard"],
                         {k: v for k, v in o.info.items() if k != "landing"}))
            if on:
                assert not o.info["landing"].any()
            else:
                assert "landing" not in o.info
        outs[on] = rows
    for a, b in zip(outs[False], outs[True]):
        for x, y in zip(a[:5], b[:5]):
            assert torch.equal(x, y)
        assert a[5].keys() == b[5].keys() and all(torch.equal(a[5][k], b[5][k]) for k in a[5])


# ------------------------------------------------------------------------------------------------ the descent
@pytest.mark.parametrize("backend", BACKENDS)
def test_a_lost_drone_descends_at_the_land_speed_and_is_parked_on_touchdown(backend):
    """A drop-out at the end of step 1 at 1.2 m: it lands, descends at 0.6 m/s, and is parked once z <= 0.15 m. Ideal
    time 1.05 m / 0.6 m/s = 1.75 s = 35 ticks; allowed up to 8 ticks (0.4 s) more for the PX4 delay (0.148 s,
    exploratory fit; the physics cascade's own lag) and the vertical lag (tau_z 0.125 s)."""
    cfg = cfg_of(backend)
    g = make(cfg, ((0.0, 0.0), (2.5, -2.5)))
    drop(g, 0)
    out = g.step(act([(0.0, 0.0, 0.0)], [(0.0, 0.0, 0.0)]))
    assert out.info["landing"][:, 0].all() and not out.info["final_alive"][:, 0].any()
    assert torch.allclose(g.pos_m[:, 0, 2], torch.full((N,), 1.2), atol=0.02)      # not parked: where it was
    ideal = round((1.2 - cfg.landing.touchdown_z_m) / cfg.landing.land_speed_mps / TICK_S)
    vz, ticks = [], None
    for k in range(1, 80):
        out = g.step(act([(0.0, 0.0, 0.0)], [(0.0, 0.0, 0.0)]))
        assert (out.outcome == RUNNING).all()
        if out.info["landing"][:, 0].all():
            vz.append(g.vel_mps[:, 0, 2].clone())
            assert (pair_mask(g)[:, 0, 1] & pair_mask(g)[:, 1, 0]).all()           # still a filter row
        else:
            assert not out.info["landing"][:, 0].any()
            ticks = k
            break
    assert ticks is not None and ideal <= ticks <= ideal + 8, (ticks, ideal)
    assert (g.pos_m[:, 0] == PARK_M).all() and (g.vel_mps[:, 0] == 0).all()        # parked, as an out drone is
    g.step(act([(0.0, 0.0, 0.0)], [(0.0, 0.0, 0.0)]))
    assert not pair_mask(g)[:, 0, 1].any()                    # in no pair from the next step (masks are set per step)
    mid = torch.stack(vz[len(vz) // 3: 2 * len(vz) // 3])
    assert torch.allclose(mid, torch.full_like(mid, -cfg.landing.land_speed_mps), atol=0.03)


@pytest.mark.parametrize("backend", BACKENDS)
def test_a_landing_drone_no_longer_acts(backend):
    """After the drop step (zero action in both runs), a full-scale action on the landing drone, yaw rate included,
    gives the same trajectory and yaw, bit for bit, as a zero action."""
    paths = []
    for a in ((0.0, 0.0, 0.0), (1.0, -1.0, 1.0)):
        g = make(cfg_of(backend), ((0.0, 0.0), (2.5, -2.5)))
        drop(g, 0)
        g.step(act([(0.0, 0.0, 0.0)], [(0.0, 0.0, 0.0)]))
        assert g.landing[:, 0].all()
        rows = []
        for _ in range(20):
            cmd = act([a], [(0.0, 0.0, 0.0)])
            cmd["guard"][..., 3] = a[0]                                              # yaw rate too
            g.step(cmd)
            rows.append((g.pos_m.clone(), g.yaw.clone()))
        paths.append(rows)
    for (p0, y0), (p1, y1) in zip(paths[0], paths[1]):
        assert torch.equal(p0[:, 0], p1[:, 0]) and torch.equal(y0[:, 0], y1[:, 0])


@pytest.mark.parametrize("backend", BACKENDS)
def test_a_landing_drone_keeps_other_drones_away(backend):
    """A Guard drone is lost at 1.2 m over (0, 0); a Strike drone at (-1.2, 0, 1.2) flies to (0, 0, 0.5), the band's
    floor under it, through the landing drone's path. Landing on: while it lands, the two stay >= 1.10 m apart in 3-D,
    less the tolerance (measured 24 Nov 2026, CPU: 1.113 m fitted, 1.093 m physics). Control, landing off, the same
    commands: the lost drone is parked at once, and the Strike drone comes inside 1.10 m of where the landing drone was
    at the same tick in the run with landing on (measured: 1.004 m fitted, 0.909 m physics): nothing holds it off. (The
    Strike drone, 0.5 m/s, cannot catch a drone descending at 0.6 m/s; the next test is the harder case.)"""
    target = (0.0, 0.0, 0.5)
    closest, ghost = {}, []
    for on in (True, False):
        g = make(cfg_of(backend, landing=on), ((0.0, 0.0), (-1.2, 0.0)))
        drop(g, 0)
        g.step(act([(0.0, 0.0, 0.0)], [(0.0, 0.0, 0.0)]))
        lo, landed = 9.0, False
        for k in range(120):
            s = toward(g.pos_m[:, 1], target)
            out = g.step(act([(0.0, 0.0, 0.0)], [tuple(s[0].tolist())]))
            assert (out.outcome == RUNNING).all()
            if on and out.info["landing"][:, 0].all():
                ghost.append(g.pos_m[:, 0].clone())
                lo = min(lo, float((g.pos_m[:, 0] - g.pos_m[:, 1]).norm(dim=-1).min()))
            elif on:
                landed = True
            elif k < len(ghost):                       # off: the distance to where the landing drone was (run on)
                lo = min(lo, float((ghost[k] - g.pos_m[:, 1]).norm(dim=-1).min()))
        if on:
            assert landed and len(ghost) > 20                                      # it landed, over 1 s
        closest[on] = lo
    assert closest[True] >= KEEPOUT_M - KEEPOUT_TOL_M, closest
    assert closest[False] < KEEPOUT_M - KEEPOUT_TOL_M, closest


@pytest.mark.parametrize("backend", BACKENDS)
def test_a_landing_drone_descending_onto_a_drone_near_the_floor_is_held_off(backend):
    """The harder case: the Strike drone presses toward (0, 0, 0.5) under a live Guard drone hovering at (0, 0, 1.2);
    the Guard drone is lost at step 40 (2 s) and lands onto it. Landing on: the pair stays >= 1.0 m apart (measured 24
    Nov 2026, CPU: 1.039 m fitted, 1.048 m physics; the Strike drone is near the band's floor, where the filter's known
    wall leak (S2 Task 7b; the Starling-layer tests' limit is 1.0 m) also lets two live drones close in). Control,
    landing off: the Strike drone flies through where the landing drone was (measured 0.662 m fitted, 0.713 m physics)."""
    target, at = (0.0, 0.0, 0.5), 40
    closest, ghost = {}, {}
    for on in (True, False):
        g = make(cfg_of(backend, landing=on), ((0.0, 0.0), (-1.2, 0.0)))
        drop(g, 0, at)
        lo = 9.0
        for k in range(1, at + 80):
            s = toward(g.pos_m[:, 1], target)
            out = g.step(act([(0.0, 0.0, 0.0)], [tuple(s[0].tolist())]))
            assert (out.outcome == RUNNING).all()
            if on and out.info["landing"][:, 0].all():
                ghost[k] = g.pos_m[:, 0].clone()
                lo = min(lo, float((g.pos_m[:, 0] - g.pos_m[:, 1]).norm(dim=-1).min()))
            elif not on and k in ghost:
                lo = min(lo, float((ghost[k] - g.pos_m[:, 1]).norm(dim=-1).min()))
        closest[on] = lo
    assert len(ghost) > 20 and not g.landing.any()
    assert closest[True] >= 1.0 and closest[False] < 0.8, closest


# ------------------------------------------------------------------------------------------------ tags and scoring
@pytest.mark.parametrize("backend", BACKENDS)
def test_a_tagged_pair_lands_and_the_game_goes_on(backend):
    """Tag on: G0 and S0 1.5 m apart tag on step 1 and both land; S1, far away, keeps the game running."""
    cfg = cfg_of(backend, **{"tag.mode": "nearest_pair_1for1"})
    g = make(cfg, ((0.0, 0.0), (1.5, 0.0), (2.5, -2.5)), guards=1, strikes=2)
    out = g.step(act([(0.0, 0.0, 0.0)], [(0.0, 0.0, 0.0)] * 2))
    assert out.info["tagged"][:, :2].all() and out.info["landing"][:, :2].all() and not out.info["landing"][:, 2].any()
    assert (out.outcome == RUNNING).all() and (g.pos_m[:, :2, 2] > 1.0).all()
    for _ in range(60):
        out = g.step(act([(0.0, 0.0, 0.0)], [(0.0, 0.0, 0.0)] * 2))
        assert (out.outcome == RUNNING).all() and not out.info["tagged"].any()
    assert not out.info["landing"].any() and (g.pos_m[:, :2] == PARK_M).all()      # both down and parked


@pytest.mark.parametrize("backend", BACKENDS)
def test_a_landing_drone_neither_tags_nor_is_tagged(backend):
    """Tag on with a made-up 2.2 m radius (the fitted drone's horizontal lag, tau 1.65 s, is too slow to close to 1.6 m
    on a drone descending at 0.6 m/s). G0 is lost at step 1; S0 starts 2.3 m away and chases it while it lands, well
    inside the radius, but nothing is tagged and S0 stays in. Control: without the drop-out, the same chase tags."""
    cfg = cfg_of(backend, **{"tag.mode": "nearest_pair_1for1", "tag.radius_m": 2.2})
    for lost in (True, False):
        g = make(cfg, ((0.0, 0.0), (2.3, 0.0)))
        if lost:
            drop(g, 0)
        tags, closest = 0, 9.0
        for _ in range(45):                                    # the landing takes about 38 ticks
            s = toward(g.pos_m[:, 1], tuple(g.pos_m[0, 0].tolist()))
            out = g.step(act([(0.0, 0.0, 0.0)], [tuple(s[0].tolist())]))
            tags += int(out.info["tagged"].sum())
            if lost and out.info["landing"][:, 0].all():
                closest = min(closest, float((g.pos_m[:, 0] - g.pos_m[:, 1]).norm(dim=-1).max()))
            if (not lost and out.done.any()) or (lost and not g.landing[:, 0].any()):
                break
        if lost:
            assert tags == 0 and closest < 2.0 and g.alive[:, 1].all()           # 0.2 m inside the radius
        else:
            assert tags > 0


@pytest.mark.parametrize("backend", BACKENDS)
def test_a_landing_strike_drone_over_the_zone_does_not_score(backend):
    """S0 starts inside the zone and is lost at step 1 (drop-outs come before the zone test, as today), then lands over
    the zone; S1, far away, keeps the game running: no step is a Strike win. Control: without the drop-out S0 wins at
    once."""
    cfg = cfg_of(backend)
    starts = ((2.5, 2.5), (0.0, 0.0), (-2.5, -2.5))
    for lost in (True, False):
        g = make(cfg, starts, guards=1, strikes=2, zone=((0.0, 0.0), 0.6))
        if lost:
            drop(g, 1)
        for k in range(50):
            out = g.step(act([(0.0, 0.0, 0.0)], [(0.0, 0.0, 0.0)] * 2))
            if not lost:
                assert (out.outcome == STRIKE_WIN).all()
                break
            assert (out.outcome == RUNNING).all()
            if k < 20:
                assert out.info["landing"][:, 1].all()


def test_the_last_strike_drone_landing_ends_the_game_and_the_new_game_clears_landing():
    """1v1: the only Strike drone is lost: the Guard team wins on that step (a landing drone is out of the game);
    the game restarts, and no drone of the new game is landing."""
    g = make(cfg_of(), ((0.0, 0.0), (2.0, 0.0)))
    drop(g, 1)
    out = g.step(act([(0.0, 0.0, 0.0)], [(0.0, 0.0, 0.0)]))
    assert (out.outcome == GUARD_WIN).all() and out.info["landing"][:, 1].all()
    assert not g.landing.any() and g.alive.all()


def test_a_drone_that_leaves_through_a_wall_goes_out_at_once():
    """walls = "leave" (PROPOSED for landing): a drone that leaves the arena or the height band is out at once, as
    today; only tags and drop-outs land."""
    g = make(cfg_of(**{"arena.walls": "leave"}), ((0.0, 0.0), (2.5, -2.5)))
    for _ in range(60):
        out = g.step(act([(0.0, 0.0, -1.0)], [(0.0, 0.0, 0.0)]))
        assert not out.info["landing"].any()
    assert not g.alive[:, 0].any() and (g.pos_m[:, 0] == PARK_M).all()


# ------------------------------------------------------------------------------------------------ what the policy sees
def test_a_landing_drone_is_absent_in_the_observations_as_an_out_drone_is():
    """Interface v0.1 (v0.3's landing flags are not approved): a landing drone's own row is zeros but its team, its slot
    in the others' rows is zeros (present 0), and the critic state's slot is zeros."""
    g = make(cfg_of(), ((0.0, 0.0), (2.5, -2.5)))
    drop(g, 0)
    out = g.step(act([(0.0, 0.0, 0.0)], [(0.0, 0.0, 0.0)]))
    assert g.landing[:, 0].all()
    own = out.obs["guard"][:, 0]
    assert (own[:, ObsView.team] == -1.0).all() and (own[:, :ObsView.team] == 0).all() \
        and (own[:, ObsView.team + 1:] == 0).all()
    slot = out.obs["strike"][:, 0, ObsView().slot(0)]
    assert (slot == 0).all()
    assert (g.state()[:, 3:10] == 0).all()                                         # game 3, then Guard slot 0


def test_cpu_determinism_with_landing_on():
    def run():
        cfg = cfg_of(**{"tag.mode": "nearest_pair_1for1", "dropout_fraction": 1.0, "rules.game_steps": 40})
        g = SvgGame(cfg, 4, 3, 3, device="cpu", seed=7)
        gen = torch.Generator().manual_seed(1)
        rows = []
        for _ in range(60):
            a = {"guard": torch.rand(4, 3, 4, generator=gen) * 2 - 1, "strike": torch.rand(4, 3, 4, generator=gen) * 2 - 1}
            out = g.step(a)
            rows.append(torch.cat((g.pos_m.flatten(), out.info["landing"].flatten().float())))
        return torch.stack(rows)
    a, b = run(), run()
    assert torch.equal(a, b)
