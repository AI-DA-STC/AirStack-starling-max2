"""Sim (velocity-output) teleop: release the sticks and the drone parks — patch 0006 (AirStack-starling-max2).

On a sim drone the commander publishes stick + kp * (reference - position) as a bare velocity. Before the
patch that full command fed back twice: the reference advanced by it (``drone.applied``) and the stick ramp
re-attached to it (``drone.published``), so after one stick push the drone kept swinging at 1-2 m/s inside
the teleop fence (Isaac sessions 2026-10-30, flat world and construction site). The trajectory output (real
drones) never had this: there the published velocity IS the stick, PX4 holds the reference itself.

The plant below is what the 2026-10-30 PX4 logs measured: velocity follows the setpoint with a ~0.45 s lag,
commands and odometry arrive a tick late, and Isaac's lockstep clock runs 1-2x wall time.
"""

from __future__ import annotations

import os

import numpy as np
import pytest

rclpy = pytest.importorskip("rclpy")
yaml = pytest.importorskip("yaml")

from rclpy.parameter import Parameter  # noqa: E402

from svg_ground_control.swarm_commander import FlightState, SwarmCommander  # noqa: E402

CONFIG = os.path.join(os.path.dirname(__file__), "..", "config", "teleop_single.yaml")
TAU_S = 0.45          # PX4 velocity response (PX4 seconds)


@pytest.fixture(scope="module", autouse=True)
def _rclpy_session():
    rclpy.init()
    yield
    rclpy.shutdown()


def make(mode: str) -> SwarmCommander:
    with open(CONFIG) as fh:
        params = yaml.safe_load(fh)["swarm_commander"]["ros__parameters"]
    params["drone_modes"] = mode
    return SwarmCommander(parameter_overrides=[Parameter(k, value=v) for k, v in params.items()])


def fly_push_release(mode: str, clock: float, push=(1.0, 0.0, 0.0), push_s=1.0, after_s=20.0):
    """One stick push, then hands off. Returns rows (t, x, y, speed) of the simulated vehicle."""
    node = make(mode)
    try:
        dt = node.control_dt
        d = node.drones[0]
        d.position, d.velocity = np.array([0.0, 0.0, 1.2]), np.zeros(3)
        d.state, d.hold_target = FlightState.ACTIVE, np.array([0.0, 0.0, 1.2])
        sent = []
        d.cmd_pub = type("Pub", (), {"publish": staticmethod(sent.append)})()
        node.mission_active = True
        p, v, pending, rows = d.position.copy(), np.zeros(3), np.zeros(3), []
        n_push, n = int(push_s / dt), int((push_s + after_s) / dt)
        for k in range(n):
            now = node.get_clock().now()
            d.position, d.velocity, d.last_odom_time = p.copy(), v.copy(), now      # odometry a tick old
            stick = push if k < n_push else ((0.0, 0.05, 0.0) if k == n_push else (0.0, 0.0, 0.0))
            d.teleop_twist, d.last_teleop_time = np.array(stick, dtype=float), now
            node.control_loop()
            m = sent[-1]
            if d.output == "trajectory":                                           # PX4 holds the setpoint
                pt = m.points[0]
                sp = np.array([pt.transforms[0].translation.x, pt.transforms[0].translation.y,
                               pt.transforms[0].translation.z])
                ff = pt.velocities[0].linear
                cmd = np.array([ff.x, ff.y, ff.z]) + (sp - p if np.all(np.isfinite(sp)) else 0.0)
            else:
                tw = m.twist.linear
                cmd = np.array([tw.x, tw.y, tw.z])
            apply, pending = pending, cmd                                           # a tick late at PX4
            h = dt * clock
            for _ in range(5):
                v = v + (apply - v) * min(1.0, (h / 5) / TAU_S)
                p = p + v * (h / 5)
            rows.append((k * dt, p[0], p[1], float(np.hypot(v[0], v[1]))))
        return np.array(rows), push_s + after_s
    finally:
        node.destroy_node()


@pytest.mark.parametrize("clock", [1.0, 1.9])
@pytest.mark.parametrize("mode", ["sim", "real"])
def test_released_sticks_park_the_drone(mode: str, clock: float) -> None:
    rows, end = fly_push_release(mode, clock)
    last = rows[rows[:, 0] >= end - 8.0]
    travel = float(np.sum(np.hypot(np.diff(last[:, 1]), np.diff(last[:, 2]))))
    assert last[:, 3].max() < 0.05, f"{mode} @ {clock}x still moving at {last[:, 3].max():.2f} m/s"
    assert travel < 0.1, f"{mode} @ {clock}x travelled {travel:.2f} m in the last 8 s"
    # Parked near where the push ended, not wandering off: within the ramp + lead distance.
    assert 0.5 < last[-1, 1] < 2.0 and abs(last[-1, 2]) < 0.2


def test_sim_reference_and_ramp_carry_the_stick_not_the_correction() -> None:
    node = make("sim")
    try:
        d = node.drones[0]
        assert d.output == "velocity"
        d.position, d.velocity = np.array([0.0, 0.0, 1.2]), np.zeros(3)
        d.state, d.hold_target = FlightState.ACTIVE, d.position.copy()
        d.cmd_pub = type("Pub", (), {"publish": staticmethod(lambda m: None)})()
        node.mission_active = True
        now = node.get_clock().now()
        d.last_odom_time = now
        node.control_loop()                                       # seeds the reference at the drone
        d.ref = d.position + np.array([0.4, 0.0, 0.0])            # drone 0.4 m short of its reference
        d.teleop_twist, d.last_teleop_time = np.zeros(3), now     # sticks centred
        node.control_loop()
        # The published command carries the correction toward the reference ...
        assert d.published[0] > 0.1
        # ... but neither the reference nor the stick ramp may inherit it.
        assert np.allclose(d.applied, 0.0)
        ref_before = d.ref.copy()
        node.control_loop()
        assert np.allclose(d.ref, ref_before)
    finally:
        node.destroy_node()


def test_trajectory_output_keeps_feeding_the_published_command_back() -> None:
    """The real-drone path is unchanged: there the published velocity is the stick itself."""
    node = make("real")
    try:
        d = node.drones[0]
        assert d.output == "trajectory"
        sent = []
        d.cmd_pub = type("Pub", (), {"publish": staticmethod(sent.append)})()
        d.position, d.ref = np.array([0.0, 0.0, 1.2]), np.array([0.3, 0.0, 1.2])
        now = node.get_clock().now()
        v = np.array([0.7, 0.1, 0.0])
        node.publish_command(d, v, np.zeros(3), now)
        assert np.allclose(d.applied, v) and np.allclose(d.published, v)
    finally:
        node.destroy_node()


def test_sim_ramp_reattaches_to_the_stick_part_not_the_measured_or_the_correction() -> None:
    """Velocity-output twin of test_teleop_ramp_reattaches_to_the_published_velocity_not_the_measured_one."""
    node = make("sim")
    try:
        d = node.drones[0]
        assert d.output == "velocity"
        now = node.get_clock().now()
        d.last_teleop_time, d.teleop_twist = now, np.zeros(3)      # sticks released
        d.teleop_stick_published = np.array([1.0, 0.0, 0.0])      # stick part last tick: 1 m/s forward
        d.published = np.array([1.4, 0.0, 0.0])                   # what went out: stick + correction
        d.applied = np.array([1.8, 0.0, -0.3])                    # measured velocity after a leash pull
        v, a = node.teleop_command(d, now)
        np.testing.assert_allclose(v, [1.0 - node.teleop_accel * node.control_dt, 0.0, 0.0])
        assert a[2] == 0.0
    finally:
        node.destroy_node()
