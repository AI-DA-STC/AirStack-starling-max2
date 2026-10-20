"""Landing completion: settle on the ground before the one-shot disarm.

Regression for "the drone does not disarm after landing" (sim, 2026-10-19):
the commander fired DISARM the instant z dropped below
land_complete_altitude_m, set IDLE and stopped publishing. PX4's land
detector had not tripped yet, so the disarm was DENIED ("not landed") and
the offboard timeout left the drone hovering, armed, props spinning.

The fix keeps the drone in LANDING (still commanding the descent) for
land_settle_s after touchdown, then disarms. Constructs the real node, as
test_runtime_params.py does.
"""

from __future__ import annotations

import numpy as np
import pytest

rclpy = pytest.importorskip("rclpy")

from rclpy.duration import Duration  # noqa: E402
from rclpy.parameter import Parameter  # noqa: E402

from svg_ground_control.swarm_commander import FlightState, SwarmCommander  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _rclpy_session():
    rclpy.init()
    yield
    rclpy.shutdown()


def make_commander(**params) -> SwarmCommander:
    overrides = [Parameter(k, value=v) for k, v in params.items()]
    return SwarmCommander(parameter_overrides=overrides)


def _landing_drone(node, z: float):
    d = node.drones[0]
    d.state = FlightState.LANDING
    d.position = np.array([0.0, 0.0, z])
    return d


def test_landing_is_not_done_until_the_settle_time_has_elapsed() -> None:
    node = make_commander(land_settle_s=1.5, land_complete_altitude_m=0.15)
    try:
        d = _landing_drone(node, 0.10)          # below the threshold: touchdown
        t0 = node.get_clock().now()
        assert node.landing_done(d, t0) is False
        assert d.state == FlightState.LANDING
        assert node.landing_done(d, t0 + Duration(seconds=1.0)) is False
        assert node.landing_done(d, t0 + Duration(seconds=1.6)) is True
    finally:
        node.destroy_node()


def test_landing_is_not_done_while_still_above_the_threshold() -> None:
    node = make_commander(land_settle_s=0.0, land_complete_altitude_m=0.15)
    try:
        d = _landing_drone(node, 0.50)
        t0 = node.get_clock().now()
        assert node.landing_done(d, t0) is False
        assert node.landing_done(d, t0 + Duration(seconds=10.0)) is False
    finally:
        node.destroy_node()


def test_a_bounce_above_the_threshold_restarts_the_settle_timer() -> None:
    node = make_commander(land_settle_s=1.5, land_complete_altitude_m=0.15)
    try:
        d = _landing_drone(node, 0.10)
        t0 = node.get_clock().now()
        assert node.landing_done(d, t0) is False
        d.position = np.array([0.0, 0.0, 0.30])          # bounced back up
        assert node.landing_done(d, t0 + Duration(seconds=1.0)) is False
        d.position = np.array([0.0, 0.0, 0.10])          # down again at t=1.2
        assert node.landing_done(d, t0 + Duration(seconds=1.2)) is False
        # 1.6 s after the first touchdown but only 0.4 s after the second.
        assert node.landing_done(d, t0 + Duration(seconds=1.6)) is False
        assert node.landing_done(d, t0 + Duration(seconds=2.8)) is True
    finally:
        node.destroy_node()


def test_land_settle_s_is_a_live_parameter() -> None:
    node = make_commander(land_settle_s=2.0)
    try:
        assert node.land_settle == 2.0
        res = node.set_parameters([Parameter("land_settle_s", value=0.5)])
        assert res[0].successful, res[0].reason
        assert node.land_settle == 0.5
    finally:
        node.destroy_node()


# ------------------------------------------------------------- disarm retry
#
# 2026-10-20, random_goals landing after the settle fix: drone_1 disarm ->
# success=True, drone_2 and drone_3 -> success=False (PX4's land detector had
# not tripped yet); the commander went IDLE anyway and PX4's own
# COM_DISARM_LAND finished the job seconds later. A denied disarm must be
# retried while the descent is still being commanded, not abandoned.

def _stub_disarm_replies(node, replies):
    """Replace send_robot_command: each call pops the next reply ('ok',
    'rejected', ...) into drone.last_robot_command, stamped 'now'."""
    calls = []

    def fake(drone, command, label):
        calls.append(label)
        drone.last_robot_command = {
            'label': label, 'result': replies.pop(0), 'message': '',
            'stamp': node._now_s()}
    node.send_robot_command = fake
    return calls


def _step(node, d, t):
    """Run land_disarm_step at commander time ``t`` (an rclpy Time): the
    stubbed reply stamps and the send times then share one timeline, as in
    the node where both come from ``_now_s``."""
    node._now_s = lambda: t.nanoseconds * 1e-9
    return node.land_disarm_step(d, t)


def test_landing_done_stays_true_once_settled() -> None:
    node = make_commander(land_settle_s=1.0)
    try:
        d = _landing_drone(node, 0.10)
        t0 = node.get_clock().now()
        assert node.landing_done(d, t0) is False
        assert node.landing_done(d, t0 + Duration(seconds=1.5)) is True
        # The settle is not restarted by asking again.
        assert node.landing_done(d, t0 + Duration(seconds=1.6)) is True
    finally:
        node.destroy_node()


def test_disarm_is_resent_until_the_interface_accepts_it() -> None:
    node = make_commander(land_settle_s=0.0, land_disarm_retry_s=1.0,
                          land_disarm_retries=5)
    try:
        d = _landing_drone(node, 0.10)
        calls = _stub_disarm_replies(node, ['rejected', 'rejected', 'ok'])
        t0 = node.get_clock().now()
        assert _step(node, d, t0) is False            # 1st send
        assert calls == ['disarm']
        assert _step(node, d, t0 + Duration(seconds=0.5)) is False
        assert calls == ['disarm']                               # too soon
        assert _step(node, d, t0 + Duration(seconds=1.1)) is False
        assert calls == ['disarm', 'disarm']                     # 2nd send
        assert _step(node, d, t0 + Duration(seconds=2.2)) is False
        assert calls == ['disarm'] * 3                           # 3rd: 'ok'
        assert _step(node, d, t0 + Duration(seconds=2.3)) is True
        assert d.state == FlightState.LANDING                    # loop flips IDLE
    finally:
        node.destroy_node()


def test_disarm_gives_up_after_the_retry_budget() -> None:
    node = make_commander(land_settle_s=0.0, land_disarm_retry_s=1.0,
                          land_disarm_retries=3)
    try:
        d = _landing_drone(node, 0.10)
        calls = _stub_disarm_replies(node, ['rejected'] * 3)
        t0 = node.get_clock().now()
        for k in range(3):
            assert _step(node, d, t0 + Duration(seconds=1.1 * k)) is False
        assert calls == ['disarm'] * 3
        assert _step(node, d, t0 + Duration(seconds=3.4)) is True
        assert calls == ['disarm'] * 3                           # no 4th send
    finally:
        node.destroy_node()


def test_a_stale_ok_from_an_earlier_landing_does_not_count() -> None:
    node = make_commander(land_settle_s=0.0, land_disarm_retry_s=1.0,
                          land_disarm_retries=5)
    try:
        d = _landing_drone(node, 0.10)
        d.last_robot_command = {'label': 'disarm', 'result': 'ok', 'message': '',
                                'stamp': node._now_s() - 30.0}
        calls = []
        node.send_robot_command = lambda drone, command, label: calls.append(label)
        t0 = node.get_clock().now()
        assert _step(node, d, t0) is False             # sends
        assert _step(node, d, t0 + Duration(seconds=0.2)) is False  # waits
        assert calls == ['disarm']
    finally:
        node.destroy_node()
