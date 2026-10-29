"""Synthetic crossing world for metrics_core tests (no real data). Stand-in metrics.py for Task 4's smoke test."""
import math
import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "live"))
import metrics_core as M  # noqa: E402

DRONES = ["drone_1", "drone_2", "drone_3"]
TRIGGER = "drone_1"
OFFSETS_FLAT = [-2, 0, 0, 0, 0, 0, 2, 0, 0]
PARAMS = {"arena_low": [-3.0, -3.0, 0.5], "arena_high": [3.0, 3.0, 2.5],
          "fence_min": [-3.0, -6.0, 0.0], "fence_max": [5.0, 5.0, 3.0],
          "drone_radius": 0.55, "speed_cap": 4.0}
REFERENCES = {"ref_2r": 1.1, "ref_speed_cap": 4.0, "ref_r": 0.55}
T_START, T_END, R_START = 1.0, 9.0, 0.9


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
_CENTER = M.arena_center(PARAMS)
_ANG = {d: math.radians(90 + 120 * i) for i, d in enumerate(DRONES)}


def _s(t):  # progress 0..1 over the test window
    return min(1.0, max(0.0, (t - T_START) / (T_END - T_START)))


def _world_pos(d, t, closest_m, far_goal_miss_m):
    # The triangle of drones rotates by half a turn while its radius dips to closest_m / sqrt(3) at
    # mid-window: start at R_START, antipode at the end, every pair distance = sqrt(3) * radius.
    s = _s(t)
    rho = closest_m / math.sqrt(3.0)
    r = rho + (R_START - rho) * math.cos(math.pi * s) ** 2
    th = _ANG[d] + math.pi * s
    p = _CENTER + r * np.array([math.cos(th), math.sin(th), 0.0])
    if far_goal_miss_m is not None and d == "drone_1":
        # Miss the antipode radially (perpendicular to the final approach): closest approach = far_goal_miss_m.
        u = (p - _CENTER) * np.array([1.0, 1.0, 0.0])
        p = p + u / np.linalg.norm(u) * far_goal_miss_m * min(1.0, 2.0 * s)
    return p


def _world_vel(d, t, closest_m, peak_speed):
    # Synthetic twist: direction of travel, bell-shaped speed peaking at peak_speed at t = 5 s.
    h = 1e-3
    dp = _world_pos(d, t + h, closest_m, None) - _world_pos(d, t - h, closest_m, None)
    n = np.linalg.norm(dp)
    s = _s(t)
    mag = peak_speed * math.sin(math.pi * s) if 0.0 < s < 1.0 else 0.0
    return dp / n * mag if n > 0 else np.zeros(3)


def _phase(t):
    return 2 if t >= T_START else (1 if t >= 0.2 else 0)


def _states(t):
    return ["ACTIVE"] * 3 if t >= T_START else (["ASCEND"] * 3 if t >= 0.2 else ["IDLE"] * 3)


def _cbf(t, cbf=True):
    return frozenset({"drone_1", "drone_3"}) if cbf and 4.0 <= t <= 6.0 else frozenset()


def frame_at(t, closest_m=1.25, peak_speed=2.0, cbf=True, far_goal_miss_m=None):
    pos = {d: _world_pos(d, t, closest_m, far_goal_miss_m) for d in DRONES}
    vel = {d: _world_vel(d, t, closest_m, peak_speed) for d in DRONES}
    start = {d: _world_pos(d, T_START, closest_m, None) for d in DRONES}
    return M.Frame(t_s=t, pos=pos, vel=vel, stale=frozenset(), cbf_active=_cbf(t, cbf), emergency=False,
                   fence_breached=False, phase=_phase(t), start_pos=start, params=PARAMS)


def make_tracker(series=SERIES):
    offs = M.offsets_by_drone(OFFSETS_FLAT, DRONES)
    return M.Tracker(DRONES, offs, PARAMS, series)


def frames(n=400, dt=0.025, closest_m=1.25, emergency_at=None, peak_speed=2.0, cbf=True, far_goal_miss_m=None):
    tr = make_tracker()
    cols = M.csv_columns(SERIES)
    rows = []
    for i in range(n):
        t = i * dt
        status = {"drones": [{"state": s} for s in _states(t)], "mission_active": t >= T_START,
                  "cbf": {"emergency": emergency_at is not None and abs(t - emergency_at) < dt / 2},
                  "fence_breached": False}
        tr.update_status(status)
        tr.update_cbf(",".join(sorted(_cbf(t, cbf))))
        for d in reversed(DRONES):  # trigger drone last, as the node would
            p = _world_pos(d, t, closest_m, far_goal_miss_m)
            tr.update_odom(d, t, p - tr.offsets[d], _world_vel(d, t, closest_m, peak_speed))
        r = tr.row(t)
        rows.append([t] + [r[c] for c in cols[1:]])
    return cols, np.array(rows, dtype=float)


def default_meta():
    return {"offsets": ",".join(str(x) for x in OFFSETS_FLAT), "t0_unix": "1.5",
            "arena_low": PARAMS["arena_low"], "arena_high": PARAMS["arena_high"],
            "fence_min": PARAMS["fence_min"], "fence_max": PARAMS["fence_max"],
            "r": PARAMS["drone_radius"], "speed_cap": PARAMS["speed_cap"], **REFERENCES}


def write_csv(path, columns, rows, meta=None):
    meta = default_meta() if meta is None else meta
    series_cols = columns
    with open(path, "w") as fh:
        lines = ["# %s=%s" % (k, M._meta_value(meta[k])) for k in sorted(meta)]
        fh.write("\n".join(lines) + "\n" + ",".join(series_cols) + "\n")
        for row in rows:
            vals = dict(zip(columns, row))
            fh.write(M.format_row(vals["t_s"], vals["phase"], vals, columns) + "\n")


# ---- asymmetric world: three straight lines through the arena centre (breaks the triangle's symmetry)
_STRAIGHT = {  # start (world), unit direction of travel, progress warp
    "drone_1": (np.array([-0.9, 0.0, 1.5]), np.array([1.0, 0.0, 0.0]), lambda s: s),
    "drone_2": (np.array([0.0, -0.9, 1.5]), np.array([0.0, 1.0, 0.0]), lambda s: s * s),
    "drone_3": (np.array([0.0, 0.0, 2.4]), np.array([0.0, 0.0, -1.0]), lambda s: 1.0 - (1.0 - s) ** 3),
}


def straight_world(t):
    """(pos, vel) per drone in the world frame; every drone starts at T_START and ends on its antipode."""
    s = _s(t)
    pos, vel = {}, {}
    for d, (p0, u, warp) in _STRAIGHT.items():
        span = 2.0 * np.linalg.norm(p0 - _CENTER)
        pos[d] = p0 + u * span * warp(s)
        ds = 1.0 / (T_END - T_START) if 0.0 < s < 1.0 else 0.0
        h = 1e-6
        dw = (warp(min(1.0, s + h)) - warp(max(0.0, s - h))) / (min(1.0, s + h) - max(0.0, s - h))
        vel[d] = u * span * dw * ds
    return pos, vel


def straight_status(t):
    return {"drones": [{"state": x} for x in _states(t)], "mission_active": t >= T_START,
            "cbf": {"emergency": False}, "fence_breached": False}


def straight_frames(n=400, dt=0.025):
    tr = make_tracker()
    cols = M.csv_columns(SERIES)
    rows = []
    for i in range(n):
        t = i * dt
        tr.update_status(straight_status(t))
        pos, vel = straight_world(t)
        for d in reversed(DRONES):
            tr.update_odom(d, t, pos[d] - tr.offsets[d], vel[d])
        r = tr.row(t)
        rows.append([t] + [r[c] for c in cols[1:]])
    return cols, np.array(rows, dtype=float)
