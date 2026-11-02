"""Series, parameters and references of the one-drone teleop-frame test (NEAR-789). Sim-only (iron rule 9).

Loaded by tools/live/metrics_node.py (live, 40 Hz odometry) and tools/live/bag_recompute.py (offline): one definition.
Tolerances are the live-vs-bag agreement per column (metrics_core.crosscheck). gates.py reads x_m / y_m at fly.sh's
push stamps. heading_deg is ENU yaw (counter-clockwise positive, metrics_core); fly.sh's stamps carry the operator
heading (clockwise positive, = -ENU yaw).
"""
import math

import metrics_core as M

DRONES = ("drone_1",)
TRIGGER = "drone_1"
# Read once from /swarm_commander at node start; recorded in the CSV header.
PARAMS = ["teleop_max_speed_mps", "teleop_fence_min", "teleop_fence_max"]
REFERENCES = {}


def _pos(i):
    return lambda f: float(f.pos["drone_1"][i]) if "drone_1" in f.pos and "drone_1" not in f.stale else math.nan


SERIES = [
    M.Series("heading_deg", lambda f: M.heading_deg(f, "drone_1"), 0.5, "deg"),
    M.Series("x_m", _pos(0), 0.02, "m"),
    M.Series("y_m", _pos(1), 0.02, "m"),
    M.Series("xy_drift_m", lambda f: M.xy_drift(f, "drone_1"), 0.02, "m"),
    M.Series("speed_drone_1", lambda f: M.speed_of(f, "drone_1"), 0.10, "m/s"),
    M.Series("fence_breached", lambda f: 1.0 if f.fence_breached else 0.0, 0.0, "", "flag"),
    M.Series("emergency", lambda f: 1.0 if f.emergency else 0.0, 0.0, "", "flag"),
]
