"""Series, parameters and references of the one-drone yaw-step test (NEAR-789). Sim-only (iron rule 9).

Loaded by tools/live/metrics_node.py (live, 40 Hz odometry) and tools/live/bag_recompute.py (offline): one definition.
Tolerances are the live-vs-bag agreement per column (metrics_core.crosscheck). The live series are what the owner
watches; the time gates read the PX4 ulog in vehicle time (gates.py). yaw_rate_dps is odometry twist.angular.z: it is
plotted only and never gated (U5: odometry_conversion may not fill it).
"""
import metrics_core as M

DRONES = ("drone_1",)
TRIGGER = "drone_1"
# Read once from /swarm_commander at node start; recorded in the CSV header.
PARAMS = ["teleop_max_speed_mps", "teleop_fence_min", "teleop_fence_max"]
REFERENCES = {"ref_band_plus": 2.0, "ref_band_minus": -2.0, "ref_overshoot_gate": 3.0}

SERIES = [
    M.Series("heading_rel_deg", lambda f: M.heading_rel_deg(f, "drone_1"), 0.5, "deg"),
    M.Series("heading_deg", lambda f: M.heading_deg(f, "drone_1"), 0.5, "deg"),
    M.Series("yaw_rate_dps", lambda f: M.yaw_rate_dps(f, "drone_1"), 2.0, "deg/s"),
    M.Series("xy_drift_m", lambda f: M.xy_drift(f, "drone_1"), 0.02, "m"),
    M.Series("fence_breached", lambda f: 1.0 if f.fence_breached else 0.0, 0.0, "", "flag"),
    M.Series("emergency", lambda f: 1.0 if f.emergency else 0.0, 0.0, "", "flag"),
]
