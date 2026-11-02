"""Gates of the one-drone teleop-frame test (NEAR-789), sim-only (iron rule 9: no value here is ported to the drone).

report.py calls build_rows(out, heavy, env), ledger_sentence(rows, ctx, verdict), figure_caption(ctx).

Sources:
  out/test_stdout.log  fly.sh's wall stamps `[<unix s>] push <0|90|180|270|world> onset|release heading=<deg>` and the
                       line `relay: stick_frame=<body|world>` (the relay's own start line, read from its log)
  out/metrics.csv      live 40 Hz odometry (x_m, y_m), wall clock: a stamp maps to t_s = stamp - t0_unix (CSV header),
                       the same mapping as yaw_step's live check
  out/odom_hz.txt      `ros2 topic hz` of drone_1's odometry before the flight (stack.sh)

Heading convention. fly.sh stamps the OPERATOR heading h: 0 = +X, clockwise positive, [0, 360) (the relay's status line,
frame.heading_deg_from_yaw). The ENU yaw is psi = -h, so the nose points along (cos psi, sin psi):
h 0 -> +X, h 90 -> -Y, h 180 -> -X, h 270 -> +Y. metrics.csv's heading_deg is ENU yaw (plotted, not gated).

Gate values (written before the first run, never moved after):
  direction <= 20 deg   angle between the xy move from onset to release and the nose at onset (Drive mode), or +X
                        (Room mode). A frame error is 90 deg or more; 20 deg leaves room for lag and wind-up.
  moved >= 0.15 m       a 0.25 x 2.0 m/s push for 2 s commands about 1 m; 0.15 m says the push reached the drone.
  parked <= 0.30 m      distance from the release point to the point 3 s later: the drone stops when the stick is let go.
  heading <= 10 deg     |wrap(onset heading - the push label)| (world: 180). It judges the driver, not the relay, so a
                        miss is UNVERIFIED, never FAIL: the record must not claim a heading that was not flown.
  odometry >= 10 Hz     below that the stamps cannot be placed on the track (INCOMPLETE, never FAIL).
A push without both stamps or without position data at its stamps never passes: its rows go UNVERIFIED.
"""
import math
import pathlib
import re
import sys

import numpy as np

_TOOLS = pathlib.Path(__file__).resolve().parents[2]
for _p in (_TOOLS / "live", _TOOLS / "lib"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
import metrics_core as M  # noqa: E402
import report as R  # noqa: E402

GATE_DIR_DEG, GATE_MOVED_M, GATE_PARK_M, GATE_ODOM_HZ = 20.0, 0.15, 0.30, 10.0
GATE_HEADING_DEG = 10.0      # onset heading vs the push label (the yaw loop stops within ±3°)
PARK_S = 3.0                  # parked point = release + 3 s
MIN_DIR_M = 0.10              # below this the move has no direction to judge
NEAR_S = 0.25                 # a stamp needs a valid position row within 0.25 s
LABELS = ("0", "90", "180", "270", "world")
STAMP = re.compile(r"^\[(\d+\.\d+)\] push (\d+|world) (onset|release) heading=(\S+)")
RELAY = re.compile(r"relay: stick_frame=(\w+)")
BASE = "none (first run sets it)"


# ------------------------------------------------------------------------------------------------ inputs
def parse_stamps(text):
    """{label: dict(w_on, h_on, w_rel, h_rel)} from fly.sh's stamp lines (first onset per label, its next release)."""
    out = {}
    for line in text.splitlines():
        mm = STAMP.match(line.strip())
        if not mm:
            continue
        t, lab, ev, h = mm.groups()
        try:
            h = float(h)
        except ValueError:
            h = math.nan
        e = out.setdefault(lab, {"w_on": None, "h_on": math.nan, "w_rel": None, "h_rel": math.nan})
        if ev == "onset" and e["w_on"] is None:
            e["w_on"], e["h_on"] = float(t), h
        elif ev == "release" and e["w_on"] is not None and e["w_rel"] is None:
            e["w_rel"], e["h_rel"] = float(t), h
    return out


def nose_enu(h_deg):
    """ENU unit vector of the nose at operator heading h (clockwise from +X): psi = -h."""
    psi = math.radians(-h_deg)
    return math.cos(psi), math.sin(psi)


def angle_deg(d, u):
    """Unsigned angle (deg) between xy vectors d and u."""
    return abs(math.degrees(math.atan2(d[0] * u[1] - d[1] * u[0], d[0] * u[0] + d[1] * u[1])))


class _Track:
    """x_m / y_m against t_s from metrics.csv; at(t) = interpolated position, None when no valid row within NEAR_S."""

    def __init__(self, meta, cols, data):
        self.t0 = float(meta["t0_unix"])
        t, x, y = (data[:, cols.index(c)] for c in ("t_s", "x_m", "y_m"))
        ok = ~(np.isnan(t) | np.isnan(x) | np.isnan(y))
        self.t, self.x, self.y = t[ok], x[ok], y[ok]

    def at(self, wall):
        if len(self.t) == 0:
            return None
        ts = wall - self.t0
        if np.min(np.abs(self.t - ts)) > NEAR_S:
            return None
        return float(np.interp(ts, self.t, self.x)), float(np.interp(ts, self.t, self.y))


def _track(out):
    try:
        meta, cols, data = M.read_metrics_csv(out / "metrics.csv")
    except (OSError, M.MetricsCsvError) as e:
        return None, None, "metrics.csv %s" % ("missing" if isinstance(e, FileNotFoundError) else "unreadable: %s" % e)
    miss = [c for c in ("t_s", "phase", "x_m", "y_m") if c not in cols]
    if miss:
        return None, (meta, cols, data), "metrics.csv lacks column(s) %s" % ", ".join(miss)
    try:
        return _Track(meta, cols, data), (meta, cols, data), None
    except (KeyError, ValueError):
        return None, (meta, cols, data), "metrics.csv has no usable t0_unix"


# ------------------------------------------------------------------------------------------------ rows
def build_rows(out, heavy, env):
    out = pathlib.Path(out)
    rows = []
    ctx = {"headline": "worst direction error", "headline_row": "worst direction error", "crosscheck": None,
           "values": {}, "caveats": []}
    V = ctx["values"]
    R.isaac_rows(rows, out, n=1)
    track, live, why = _track(out)
    has_tp = live is not None and "t_s" in live[1] and "phase" in live[1]
    R.coverage_row(rows, out, M.coverage(live[1], live[2]) if has_tp else None, M.STALE_S, why or "metrics.csv lacks t_s/phase")

    stdout = R.read(out, "test_stdout.log")
    stamps = parse_stamps(stdout)

    # ---- the relay's live mode at start
    rl = RELAY.search(stdout)
    crit_r = "fly.sh printed `relay: stick_frame=body` (the relay's own start line): the Drive-mode pushes ran through a BODY relay"
    if rl is None:
        R.row(rows, "relay stick_frame recorded", crit_r, "n/a — no `relay: stick_frame=` line in test_stdout.log", "-", None)
    else:
        R.row(rows, "relay stick_frame recorded", crit_r, "stick_frame=%s" % rl.group(1), "-", rl.group(1) == "body")
    V["relay"] = rl.group(1) if rl else None

    # ---- odometry rate
    hz_txt = R.read(out, "odom_hz.txt")
    mm = re.search(r"average rate:\s*([0-9.]+)", hz_txt)
    crit_o = "≥ %.0f Hz (`ros2 topic hz` of /drone_1/odometry_conversion/odometry before the flight); below = INCOMPLETE" % GATE_ODOM_HZ
    if mm is None:
        R.row(rows, "odometry rate ≥ 10 Hz", crit_o, "n/a — odom_hz.txt missing or without `average rate:`", "-", None)
    else:
        hz = float(mm.group(1))
        V["odom_hz"] = hz
        R.row(rows, "odometry rate ≥ 10 Hz", crit_o, "%.1f Hz" % hz + ("" if hz >= GATE_ODOM_HZ else " — too slow to place the stamps"),
              "-", True if hz >= GATE_ODOM_HZ else None)

    # ---- pushes flown
    done = [lab for lab in LABELS if lab in stamps and stamps[lab]["w_rel"] is not None]
    lost = [lab for lab in LABELS if lab not in done]
    R.row(rows, "pushes flown", "fly.sh stamped onset + release for pushes 0, 90, 180, 270 (Drive mode) and world (Room mode)",
          "%d of 5" % len(done) + ("; missing or unreleased: %s" % ", ".join(lost) if lost else ""), "-", True if not lost else None)

    # ---- per push
    errs = {}
    for lab in LABELS:
        _push_rows(rows, lab, stamps.get(lab), track, why, errs, V)
    if errs:
        worst = max(errs, key=errs.get)
        V["worst_dir"], V["worst_lab"] = errs[worst], worst
        R.row(rows, "worst direction error", "informational (largest direction error over the measured pushes)",
              "%.1f° (push %s; gate %.0f°)" % (errs[worst], worst, GATE_DIR_DEG), BASE, None, gate=False)
    else:
        R.row(rows, "worst direction error", "informational (largest direction error over the measured pushes)",
              "n/a — no push measured", BASE, None, gate=False)

    # ---- flags (info: the gates above judge the frame; a fence or emergency shows in the record)
    if live is not None:
        for name in ("emergency", "fence_breached"):
            if name in live[1]:
                n = int(np.nansum(live[2][:, live[1].index(name)]))
                R.row(rows, "%s samples" % name, "informational (5 Hz status string)", "`%s`: %d CSV rows flagged" % (name, n), "-", None, gate=False)

    # ---- landing, cross-check, evidence
    land = R.read(out, "landing_evidence.txt")
    landed = sorted(set(re.findall(r"(drone_\d): landed, disarmed", land)))
    R.row(rows, "landed, disarmed (commander ACK)", "informational (ACK log, not an arming display)",
          ", ".join(landed) if landed else "none — no landed, disarmed line in landing_evidence.txt", "-", None, gate=False)
    R.landing_rows(rows, out, n=1)
    cr = None
    try:
        bag = M.read_metrics_csv(out / "metrics_bag.csv")
    except (OSError, M.MetricsCsvError):
        bag = None
    if live is not None and bag is not None:
        try:
            cr = M.crosscheck(live[1], live[2], bag[1], bag[2], _series())
        except (ValueError, KeyError, IndexError):
            cr = None
    ctx["crosscheck"] = cr
    R.crosscheck_rows(rows, cr, "x_m / y_m")
    if rows[-1].verdict == "FAIL":     # nothing proven wrong, but what was watched is not what is gated: UNVERIFIED
        rows[-1].verdict = "UNVERIFIED"
    extra = tuple(f for f in ("metrics.csv", "metrics_bag.csv") if (out / f).is_file())
    R.evidence_rows(rows, out, heavy, env["BAG_PREFIX"], extra_files=extra, n=1)

    ctx["reading"] = _reading(V)
    ctx["caveats"].append("Stamps are wall clock; they are placed on metrics.csv through its t0_unix header (t_s = stamp − t0_unix), "
                          "the same mapping as yaw_step's live check. PX4 lockstep runs about 1.3× the wall clock, so a 2 s push is about 2.6 s of vehicle time.")
    return rows, ctx


def _push_rows(rows, lab, e, track, why, errs, V):
    world = lab == "world"
    name = "push %s" % lab
    c_dir = ("direction within %.0f° of +X (Room mode; the nose at about 180° points the other way, so Drive mode would fail)" % GATE_DIR_DEG
             if world else "direction within %.0f° of the nose at onset (Drive mode; nose = (cos ψ, sin ψ), ψ = −heading)" % GATE_DIR_DEG)
    c_mov = "|xy move| from onset to release ≥ %.2f m" % GATE_MOVED_M
    c_park = "|xy at release + %.0f s − xy at release| ≤ %.2f m" % (PARK_S, GATE_PARK_M)
    checks = ("%s: direction within %.0f° of %s" % (name, GATE_DIR_DEG, "+X" if world else "the nose"), "%s: moved ≥ %.2f m" % (name, GATE_MOVED_M), "%s: parked within %.2f m" % (name, GATE_PARK_M))

    target = 180.0 if world else float(lab)
    c_head = "|onset heading − %.0f°| ≤ %.0f° (wrapped; a miss judges the yaw loop, not the relay: UNVERIFIED)" % (target, GATE_HEADING_DEG)
    head_chk = "%s: heading reached" % name

    def all_na(reason):
        R.row(rows, head_chk, c_head, "n/a — " + reason, BASE, None)
        for chk, crit in zip(checks, (c_dir, c_mov, c_park)):
            R.row(rows, chk, crit, "n/a — " + reason, BASE, None)

    if e is None or e["w_on"] is None:
        return all_na("no onset stamp in test_stdout.log")
    if e["w_rel"] is None:
        return all_na("onset stamped, never released (fly.sh stopped mid-push)")
    if track is None:
        return all_na(why)
    p_on, p_rel, p_park = track.at(e["w_on"]), track.at(e["w_rel"]), track.at(e["w_rel"] + PARK_S)
    h = e["h_on"]
    if math.isnan(h):
        R.row(rows, head_chk, c_head, "n/a — no heading in the onset stamp", BASE, None)
    else:
        dh = abs((h - target + 180.0) % 360.0 - 180.0)
        R.row(rows, head_chk, c_head, "%.1f° at onset (%.1f° off)%s" % (h, dh, "" if dh <= GATE_HEADING_DEG else " — the push did not fly at its label's heading"), BASE, True if dh <= GATE_HEADING_DEG else None)
    if p_on is None or p_rel is None:
        for chk, crit in zip(checks, (c_dir, c_mov, c_park)):
            R.row(rows, chk, crit, "n/a — no valid metrics.csv row within %.2f s of the onset or release stamp" % NEAR_S, BASE, None)
        return
    d = (p_rel[0] - p_on[0], p_rel[1] - p_on[1])
    dist = math.hypot(*d)
    # direction
    if world:
        u, ref = (1.0, 0.0), "+X"
        far = not math.isnan(h) and angle_deg(nose_enu(h), u) >= 90.0
    else:
        u, ref, far = (nose_enu(h) if not math.isnan(h) else None), "nose", True
    move = "move (%+.2f, %+.2f) m, heading %s at onset" % (d[0], d[1], "nan" if math.isnan(h) else "%.1f°" % h)
    if u is None:
        R.row(rows, checks[0], c_dir, "n/a — no heading in the onset stamp; " + move, BASE, None)
    elif dist < MIN_DIR_M:
        R.row(rows, checks[0], c_dir, "n/a — moved only %.2f m, no direction to judge; %s" % (dist, move), BASE, None)
    elif not far:
        R.row(rows, checks[0], c_dir, "n/a — the nose was within 90° of +X, Room and Drive mode look alike; " + move, BASE, None)
    else:
        err = angle_deg(d, u)
        errs[lab] = err
        R.row(rows, checks[0], c_dir, "%.1f° from %s; %s" % (err, ref, move), BASE, err <= GATE_DIR_DEG)
    # moved
    V["moved_" + lab] = dist
    R.row(rows, checks[1], c_mov, "%.2f m" % dist, BASE, dist >= GATE_MOVED_M)
    # parked
    if p_park is None:
        R.row(rows, checks[2], c_park, "n/a — no valid metrics.csv row within %.2f s of release + %.0f s" % (NEAR_S, PARK_S), BASE, None)
    else:
        dp = math.hypot(p_park[0] - p_rel[0], p_park[1] - p_rel[1])
        V["park_" + lab] = dp
        R.row(rows, checks[2], c_park, "%.2f m" % dp, BASE, dp <= GATE_PARK_M)


def _series():
    import importlib.util
    spec = importlib.util.spec_from_file_location("teleop_frame_metrics_for_gates", pathlib.Path(__file__).with_name("metrics.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.SERIES


def _reading(V):
    s = "[Figure 1](#fig-1) plots the heading, the x and y position and the speed against wall-clock time. "
    if "worst_dir" not in V:
        return s + "No push could be measured from metrics.csv, so no direction is reported."
    moved = [V[k] for k in V if k.startswith("moved_")]
    parked = [V[k] for k in V if k.startswith("park_")]
    s += ("The worst direction error was %.1f° (push %s; gate 20°). Each push moved %.2f–%.2f m (gate ≥ 0.15 m)"
          % (V["worst_dir"], V["worst_lab"], min(moved), max(moved)))
    s += (" and the drone stayed within %.2f m of the release point 3 s later (gate 0.30 m)." % max(parked)) if parked else "."
    return s


def _status(rows, prefix):
    return next((r.verdict for r in rows if r.check.startswith(prefix)), "UNVERIFIED")


def ledger_sentence(rows, ctx, verdict):
    V = ctx.get("values", {})
    landed = _status(rows, "post-flight armed") == "PASS"
    wd = "%.1f°" % V["worst_dir"] if "worst_dir" in V else "n/a"
    s = ("teleop frame, 1 drone, teleop_single_ours.yaml, relay stick_frame=%s, forward pushes at 0/90/180/270 (Drive) + 180 (Room): %s — "
         "worst direction error %s (gate 20°), odometry %s; landed + DISARMED %s"
         % (V.get("relay") or "n/a", verdict, wd, "%.0f Hz" % V["odom_hz"] if "odom_hz" in V else "n/a", "yes" if landed else "NOT shown"))
    for vv in ("FAIL", "UNVERIFIED"):
        names = [r.check for r in rows if r.gate and r.verdict == vv]
        if names:
            s += "; %s: %s" % (vv, ", ".join(names))
    return s


def figure_caption(ctx):
    return ("Heading (ENU yaw), x and y position and speed of drone_1 against wall-clock time, from the 40 Hz odometry. "
            "Each step in heading is a yaw to the next push heading; each ramp in x or y is a 2 s forward push. "
            "Drawn from metrics.csv by `tools/sim.sh figures teleop_frame <run>`.")
