"""Batched torch copy of the commander's real-mode teleop law (models/commander.py) against NumPy.

The NumPy side is CMU's own ``position_hold.py`` (imported read-only from AirStack: ``advance_reference``,
``ramp_velocity``, ``leash``) plus a line-by-line transcription of the parts that live inside ``swarm_commander.py``
(which needs ROS to import): the stick cap (``teleop_stick``, :1879-1894), ``command_feedforward`` (:193-224) and
the leash after a filter correction (:2229-2234). No ROS, no GPU.
"""
import pathlib
import sys
import tomllib

import numpy as np
import pytest
import torch

ROOT = pathlib.Path(__file__).resolve().parents[1]
CMU_PKG = ROOT.parent / "AirStack/robot/ros_ws/src/svg_ground_control"
if not (CMU_PKG / "svg_ground_control").is_dir():   # the container mounts only svg_training/
    pytest.skip(f"CMU's svg_ground_control is not on this machine ({CMU_PKG}); run on the host",
                allow_module_level=True)
sys.path.insert(0, str(CMU_PKG))
from svg_ground_control import position_hold as ph  # noqa: E402

from svg_training.models.commander import CommanderParams, TeleopCommander  # noqa: E402

PARAMS_TOML = ROOT / "params/real_exploratory_v0.toml"
P = CommanderParams.from_dict(tomllib.loads(PARAMS_TOML.read_text())["commander"])
DT = P.tick_s


# ------------------------------------------------------------------------------------------- NumPy transcription
def _np_stick(stick):
    """swarm_commander.py:1886-1889 (stale branch not modelled: a policy commands every tick)."""
    cmd = np.array(stick, dtype=float)
    speed = np.linalg.norm(cmd)
    if speed > P.teleop_max_speed_mps + 1e-3:
        cmd *= P.teleop_max_speed_mps / speed
    return cmd


def _np_feedforward(profile_accel, nominal, velocity, published, dt, limit):
    """swarm_commander.py:193-224, with no fence (clipped == velocity, so no axis is 'limited')."""
    accel = np.array(profile_accel, dtype=float)
    velocity = np.asarray(velocity, dtype=float)
    if np.linalg.norm(velocity - np.asarray(nominal, dtype=float)) > 1e-6:
        accel = (velocity - np.asarray(published, dtype=float)) / max(dt, 1e-3)
        norm = float(np.linalg.norm(accel))
        if limit > 0.0 and norm > limit:
            accel *= limit / norm
    return accel


class _NpDrone:
    """One teleop drone on the trajectory output, ACTIVE, mission running (the training case)."""

    def __init__(self):
        self.ref = None
        self.profile = None
        self.published = np.zeros(3)
        self.applied = np.zeros(3)

    def advance(self, pos):                                   # swarm_commander.py:1951-1979 (no fence box)
        seeded = self.ref is None
        self.ref, self.applied = ph.advance_reference(self.ref, pos, self.applied, np.zeros(3), DT, P.teleop_lead_m)
        if seeded:
            self.profile = None

    def shape(self, stick):                                   # :1896-1927, trajectory output
        s = _np_stick(stick)
        vel, acc, self.profile = ph.ramp_velocity(self.profile, self.published, s, P.teleop_accel_mps2, DT,
                                                  P.ramp_reattach_mps)
        return vel, acc

    def finish(self, nominal, accel_ff, safe, corrected, pos):   # :2202-2235, then publish_command :2306-2309
        accel = _np_feedforward(accel_ff, nominal, safe, self.published, DT, P.goal_accel_mps2)
        if corrected and self.ref is not None:
            lead, pulled = ph.leash(self.ref - pos, P.hold_lead_m)
            if pulled:
                self.ref = pos + lead
        p_sp = self.ref.copy()
        self.applied = np.array(safe, dtype=float)
        self.published = np.array(safe, dtype=float)
        return p_sp, np.array(safe, dtype=float), accel


def _np_run(sticks, positions, safety=None):
    """sticks, positions (T, N, M, 3) -> p_sp, v_ff, a_ff (T, N, M, 3). safety(nominal (M,3), pos) -> (safe, corr)."""
    t_n, n, m, _ = sticks.shape
    drones = [[_NpDrone() for _ in range(m)] for _ in range(n)]
    out = np.zeros((3, t_n, n, m, 3))
    for t in range(t_n):
        for g in range(n):
            nominal = np.zeros((m, 3))
            acc_ff = np.zeros((m, 3))
            for j in range(m):
                drones[g][j].advance(positions[t, g, j])
                nominal[j], acc_ff[j] = drones[g][j].shape(sticks[t, g, j])
            safe, corr = (nominal.copy(), np.zeros(m, dtype=bool)) if safety is None else safety(nominal,
                                                                                               positions[t, g])
            for j in range(m):
                res = drones[g][j].finish(nominal[j], acc_ff[j], safe[j], bool(corr[j]), positions[t, g, j])
                for k in range(3):
                    out[k, t, g, j] = res[k]
    return out


def _torch_run(sticks, positions, safety=None, cmdr=None):
    t_n, n, m, _ = sticks.shape
    cmdr = cmdr or TeleopCommander(n, m, P, device="cpu", dtype=torch.float64)
    out = np.zeros((3, t_n, n, m, 3))
    for t in range(t_n):
        res = cmdr.step(torch.from_numpy(sticks[t]), torch.from_numpy(positions[t]), safety=safety)
        for k in range(3):
            out[k, t] = res[k].numpy()
    return out


def _inputs(seed, t_n=240, n=3, m=3):
    """Random stick sequences: held for random spans, some above the cap, some zero; positions lag a little."""
    rng = np.random.default_rng(seed)
    sticks = np.zeros((t_n, n, m, 3))
    for g in range(n):
        for j in range(m):
            t = 0
            while t < t_n:
                span = int(rng.integers(1, 30))
                kind = rng.random()
                val = np.zeros(3) if kind < 0.2 else rng.normal(0.0, 0.5, 3) * (2.0 if kind > 0.8 else 1.0)
                sticks[t:t + span, g, j] = val
                t += span
    start = rng.uniform(-3.0, 3.0, (n, m, 3))
    walk = np.cumsum(rng.normal(0.0, 0.01, (t_n, n, m, 3)), axis=0)
    return sticks, start[None] + walk


# ------------------------------------------------------------------------------------------- tests
@pytest.mark.parametrize("seed", [0, 1, 2])
def test_matches_numpy_transcription(seed):
    sticks, positions = _inputs(seed)
    ref = _np_run(sticks, positions)
    got = _torch_run(sticks, positions)
    assert np.abs(got - ref).max() <= 1e-6


def _scripted_filter_np(nominal, pos):
    """A stand-in filter with known output: drone 0 slowed to 30 %, drone 1 turned, the rest untouched."""
    safe = nominal.copy()
    safe[0] = 0.3 * nominal[0]
    safe[1] = nominal[1][[1, 0, 2]]
    corr = np.linalg.norm(safe - nominal, axis=-1) > 1e-3
    return safe, corr


def _scripted_filter_torch(nominal, pos):
    safe = nominal.clone()
    safe[:, 0] = 0.3 * nominal[:, 0]
    safe[:, 1] = nominal[:, 1][:, [1, 0, 2]]
    return safe, (safe - nominal).norm(dim=-1) > 1e-3


@pytest.mark.parametrize("seed", [3, 4])
def test_matches_numpy_with_a_filter_in_the_loop(seed):
    """Post-filter path: feed-forward from the published rate (capped at goal_accel), hold leash, ramp re-attach."""
    sticks, positions = _inputs(seed)
    ref = _np_run(sticks, positions, safety=_scripted_filter_np)
    got = _torch_run(sticks, positions, safety=_scripted_filter_torch)
    assert np.abs(got - ref).max() <= 1e-6


def _hold(stick, ticks, pos=(0.0, 0.0, 1.0)):
    cmdr = TeleopCommander(1, 1, P, device="cpu", dtype=torch.float64)
    p = torch.tensor(pos, dtype=torch.float64).view(1, 1, 3)
    s = torch.tensor(stick, dtype=torch.float64).view(1, 1, 3)
    return [tuple(x[0, 0].clone() for x in cmdr.step(s, p)) for _ in range(ticks)]


def test_leash_clamps_the_reference_horizontally_and_vertically_apart():
    out = _hold((0.5, 0.0, 0.5), 60)                         # drone pinned at (0, 0, 1): the reference runs ahead
    leads = torch.stack([o[0] for o in out]) - torch.tensor([0.0, 0.0, 1.0], dtype=torch.float64)
    assert leads[:, :2].norm(dim=-1).max() <= P.teleop_lead_m + 1e-12
    assert leads[:, 2].abs().max() <= P.teleop_lead_m + 1e-12
    assert abs(leads[-1, 0].item() - P.teleop_lead_m) < 1e-12     # reaches the leash and stays on it
    assert abs(leads[-1, 2].item() - P.teleop_lead_m) < 1e-12     # z leashed on its own, not scaled with x


def test_ramp_limits_the_speed_change_per_tick():
    out = _hold((0.3, -0.3, 0.1), 20)
    v = torch.stack([o[1] for o in out])
    steps = (v[1:] - v[:-1]).norm(dim=-1)
    assert steps.max() <= P.teleop_accel_mps2 * DT + 1e-12
    assert abs(v[0].norm().item() - P.teleop_accel_mps2 * DT) < 1e-12          # first tick: one ramp step from 0
    a0 = out[0][2]
    assert abs(a0.norm().item() - P.teleop_accel_mps2) < 1e-9                  # feed-forward = the ramp's accel
    assert torch.allclose(v[-1], torch.tensor([0.3, -0.3, 0.1], dtype=torch.float64), atol=1e-12)
    assert out[-1][2].abs().max() < 1e-12                                     # ramp done: no feed-forward


def test_stick_speed_cap_with_the_commanders_slack():
    v = _hold((3.0, 4.0, 0.0), 30)[-1][1]
    assert abs(v.norm().item() - P.teleop_max_speed_mps) < 1e-12
    assert torch.allclose(v / v.norm(), torch.tensor([0.6, 0.8, 0.0], dtype=torch.float64))
    v = _hold((P.teleop_max_speed_mps + 0.0009, 0.0, 0.0), 30)[-1][1]         # inside the 1e-3 slack: not capped
    assert abs(v[0].item() - (P.teleop_max_speed_mps + 0.0009)) < 1e-12


def test_reset_reseeds_the_reference_and_restarts_the_ramp():
    cmdr = TeleopCommander(2, 1, P, device="cpu", dtype=torch.float64)
    s = torch.tensor([0.5, 0.0, 0.0], dtype=torch.float64).expand(2, 1, 3)
    p = torch.zeros(2, 1, 3, dtype=torch.float64)
    for _ in range(10):
        cmdr.step(s, p)
    cmdr.reset(torch.tensor([[True], [False]]))
    p2 = torch.tensor([[[1.0, 2.0, 3.0]], [[0.0, 0.0, 0.0]]], dtype=torch.float64)
    p_sp, v_ff, _a = cmdr.step(s, p2)
    assert torch.equal(p_sp[0, 0], p2[0, 0])                                  # seeded at the drone, not advanced
    assert abs(v_ff[0, 0, 0].item() - P.teleop_accel_mps2 * DT) < 1e-12       # ramp from 0 again
    assert abs(v_ff[1, 0, 0].item() - 0.5) < 1e-12                            # the other game untouched


def test_params_from_toml_and_unknown_keys_refused():
    assert P.tick_s == 0.05 and P.teleop_accel_mps2 == 5.0 and P.teleop_lead_m == 0.5
    assert P.teleop_max_speed_mps == 0.5 and P.hold_lead_m == 0.2 and P.goal_accel_mps2 == 3.0
    with pytest.raises(ValueError):
        CommanderParams.from_dict({**P.to_dict(), "bogus": 1.0})


def test_no_python_loop_in_the_module():
    """STANDARDS §6: the per-tick code (leash, TeleopCommander) has no for/while at all, so none over games.

    (CommanderParams loops over its own fields when it is built; that is not on the training path.)"""
    import ast
    tree = ast.parse((ROOT / "source/svg_training/models/commander.py").read_text())
    hot = [n for n in tree.body if getattr(n, "name", None) in ("leash", "TeleopCommander")]
    assert len(hot) == 2
    loops = [n for h in hot for n in ast.walk(h) if isinstance(n, (ast.For, ast.While, ast.comprehension))]
    assert not loops
