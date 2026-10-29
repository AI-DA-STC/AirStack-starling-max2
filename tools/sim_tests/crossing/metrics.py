"""Series, parameters and references of the three-drone CBF crossing (NEAR-787). Sim-only (iron rule 9).

Loaded by tools/live/metrics_node.py (live, 40 Hz) and tools/live/bag_recompute.py (offline) -- one definition,
so both produce the same columns. Tolerances are the live-vs-bag agreement per column (metrics_core.crosscheck).
Same list by name/kind/tolerance as tools/tests/synth_crossing.SERIES.
"""
import metrics_core as M

DRONES = ("drone_1", "drone_2", "drone_3")
TRIGGER = "drone_1"
# Read once from /swarm_commander at node start; recorded in the CSV header.
PARAMS = ["drone_position_offsets", "arena_low", "arena_high", "fence_min", "fence_max",
          "cbf_safety_radius_m", "cbf_max_speed_mps"]
REFERENCES = {"ref_2r": lambda p: 2 * p["cbf_safety_radius_m"],
              "ref_r": lambda p: p["cbf_safety_radius_m"],
              "ref_speed_cap": lambda p: p["cbf_max_speed_mps"]}


def _series():
    s = []
    for a, b in (("drone_1", "drone_2"), ("drone_1", "drone_3"), ("drone_2", "drone_3")):
        s.append(M.Series(M.pair_key(a, b), lambda f, a=a, b=b: M.pair_distance(f, a, b), 0.02, "m"))
    s.append(M.Series("min_pair_distance", M.min_pair_distance, 0.02, "m", running_min=True))
    for d in DRONES:
        s.append(M.Series("speed_" + d, lambda f, d=d: M.speed_of(f, d), 0.10, "m/s"))
    for d in DRONES:
        s.append(M.Series("cbf_" + d, lambda f, d=d: 1.0 if d in f.cbf_active else 0.0, 0.0, "", "flag"))
    s.append(M.Series("emergency", lambda f: 1.0 if f.emergency else 0.0, 0.0, "", "flag"))
    s.append(M.Series("fence_breached", lambda f: 1.0 if f.fence_breached else 0.0, 0.0, "", "flag"))
    s.append(M.Series("fence_margin", M.fence_margin, 0.02, "m"))
    for d in DRONES:
        s.append(M.Series("goal_dist_" + d, lambda f, d=d: M.goal_distance(f, d), 0.05, "m"))
    return s


SERIES = _series()
