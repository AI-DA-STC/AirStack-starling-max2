"""Template series: d_12, its running minimum, two drones' speeds. Copy and extend (see crossing/metrics.py). Sim-only."""
import metrics_core as M

DRONES = ("drone_1", "drone_2", "drone_3")
TRIGGER = "drone_1"
PARAMS = ["drone_position_offsets", "cbf_safety_radius_m"]     # CHANGE_ME: commander parameters your series need
REFERENCES = {"ref_2r": lambda p: 2 * p["cbf_safety_radius_m"]}

SERIES = [
    M.Series("d_12", lambda f: M.pair_distance(f, "drone_1", "drone_2"), 0.02, "m"),
    M.Series("min_pair_distance", M.min_pair_distance, 0.02, "m", running_min=True),
    M.Series("speed_drone_1", lambda f: M.speed_of(f, "drone_1"), 0.10, "m/s"),
    M.Series("speed_drone_2", lambda f: M.speed_of(f, "drone_2"), 0.10, "m/s"),
]
