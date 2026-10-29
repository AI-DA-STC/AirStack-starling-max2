"""Gates of the three-drone CBF crossing (NEAR-787), judged from the live metrics.csv. Sim-only (iron rule 9).

report.py calls build_rows(out, heavy, env), ledger_sentence(rows, ctx, verdict), figure_caption(ctx).
All numbers come from out/metrics.csv (40 Hz, written by tools/live/metrics_node.py); out/metrics_bag.csv is the
offline recompute from the rosbag, compared through metrics_core.crosscheck. A missing or unreadable file makes
the gates that need it UNVERIFIED, never a crash.
"""
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

DRONES = ("drone_1", "drone_2", "drone_3")
PAIRS = ("d_12", "d_13", "d_23")
GATE_2R, GATE_SPEED, GATE_GOAL, LEDGER4 = 1.10, 4.2, 0.40, 1.02
NAN_MAX = 0.01


def _load(path):
    try:
        meta, cols, data = M.read_metrics_csv(path)
    except (OSError, M.MetricsCsvError) as e:
        return None, "%s %s" % (pathlib.Path(path).name, "missing" if isinstance(e, FileNotFoundError) else "unreadable: %s" % e)
    return (meta, cols, data), None


class _Run:
    def __init__(self, cols, data):
        self.cols, self.data = cols, data
        self.p2 = data[data[:, cols.index("phase")] == 2]

    def col(self, name, rows=None):
        return (self.data if rows is None else rows)[:, self.cols.index(name)]

    def nan_problem(self, names):
        """None when every column is NaN-free enough in phase 2, else the reason string."""
        if len(self.p2) == 0:
            return "no phase-2 rows in metrics.csv"
        bad = [(n, M.nan_fraction(self.data, self.cols, n)) for n in names]
        bad = [(n, f) for n, f in bad if f > NAN_MAX]
        if bad:
            return "stale odometry in %.1f %% of rows (%s)" % (100 * max(f for _, f in bad), ", ".join(n for n, _ in bad))
        return None

    def dt(self):
        t = self.col("t_s")
        return float(np.median(np.diff(t))) if len(t) > 1 else 0.0


def build_rows(out, heavy, env):
    out = pathlib.Path(out)
    rows, ctx = [], {"headline": "minimum pairwise distance", "headline_row": "min pairwise distance", "crosscheck": None, "values": {}}
    R.isaac_rows(rows, out)
    live, why = _load(out / "metrics.csv")
    bag, _ = _load(out / "metrics_bag.csv")
    run = _Run(live[1], live[2]) if live else None
    V = ctx["values"]

    def gate(check, crit, base, fn, needs):
        """fn(run) -> (measured, ok); needs = columns that must be NaN-free in phase 2."""
        if run is None:
            return R.row(rows, check, crit, "n/a — %s" % why, base, None)
        miss = [n for n in needs if n not in run.cols]
        if miss:
            return R.row(rows, check, crit, "n/a — metrics.csv lacks column(s) %s" % ", ".join(miss), base, None)
        prob = run.nan_problem(needs)
        if prob:
            return R.row(rows, check, crit, "n/a — " + prob, base, None)
        meas, ok = fn(run)
        return R.row(rows, check, crit, meas, base, ok)

    # ---- coverage: a trigger-drone gap or a dead node leaves no NaN row, so the gates below would judge partial data
    has_tp = run is not None and "t_s" in run.cols and "phase" in run.cols
    R.coverage_row(rows, out, M.coverage(run.cols, run.data) if has_tp else None, M.STALE_S, why or "metrics.csv lacks t_s/phase")

    # ---- minimum pairwise distance
    def f_min(r):
        mp = r.col("min_pair_distance", r.p2)
        i = int(np.nanargmin(mp))
        t = float(r.col("t_s", r.p2)[i])
        pair = PAIRS[int(np.argmin([r.col(p, r.p2)[i] for p in PAIRS]))]
        m = float(mp[i])
        V["min_d"], V["min_pair"], V["min_t"] = m, pair, t
        return "`min_pair_distance`: %.2f m (margin %+.2f m to the gate; pair `%s` at t=%.1f s)" % (m, m - GATE_2R, pair, t), m >= GATE_2R
    gate("min pairwise distance ≥ 1.10 m (2r)", "≥ 1.10 m, binary (live 40 Hz odometry, phase 2)",
         "#4: 1.02 m (0.08 m inside, 10-19 asset, 3 m/s cap, no bag)", f_min, ("min_pair_distance",) + PAIRS)
    if "min_d" in V:
        R.row(rows, "vs ledger #4", "informational (min distance − 1.02 m)", "`min_pair_distance` − 1.02 m: %+.2f m" % (V["min_d"] - LEDGER4), "#4: 1.02 m", None, gate=False)
    else:
        R.row(rows, "vs ledger #4", "informational (min distance − 1.02 m)", "n/a — no minimum distance", "#4: 1.02 m", None, gate=False)

    # ---- all-phase minimum (info only, F8 ruling: the owner decides whether to gate it)
    if run is not None and all(p in run.cols for p in PAIRS) and len(run.data):
        R.row(rows, "min pairwise distance, all phases", "informational (every row: takeoff, window, landing; not a gate)",
              _all_phase_min(run), "-", None, gate=False)
    else:
        R.row(rows, "min pairwise distance, all phases", "informational (every row: takeoff, window, landing; not a gate)",
              "n/a — %s" % (why or "metrics.csv lacks d_12/d_13/d_23"), "-", None, gate=False)

    # ---- flags: emergency, fence
    def f_flag(name, key):
        def fn(r):
            c = r.col(name)
            n = int(np.nansum(c))
            V[key] = n
            return "`%s`: %d CSV rows flagged (≈ 8 per 5 Hz status sample)" % (name, n), n == 0
        return fn
    gate("emergency samples", "0 (5 Hz status string)", "-", f_flag("emergency", "emerg"), ("emergency",))
    gate("fence-breach samples", "0 (5 Hz status string)", "-", f_flag("fence_breached", "breach"), ("fence_breached",))

    # ---- CBF active
    def f_cbf(r):
        cs = [d for d in DRONES if np.nansum(r.col("cbf_" + d)) > 0]
        anyc = np.zeros(len(r.data), dtype=bool)
        for d in DRONES:
            anyc |= np.nan_to_num(r.col("cbf_" + d)) > 0
        secs = float(anyc.sum() * r.dt())
        V["cbf_drones"], V["cbf_s"] = cs, secs
        return "`cbf_drone_1..3`: " + (("%s seen; %.1f s active (any drone)" % (", ".join(cs), secs)) if cs else "nobody seen; 0.0 s active"), bool(cs)
    gate("CBF active on ≥ 1 drone at least once", "/svg/cbf_active names ≥ 1 drone at least once (20 Hz)", "-", f_cbf,
         tuple("cbf_" + d for d in DRONES))

    # ---- far goal
    def f_goal(r):
        best = {d: float(np.nanmin(r.col("goal_dist_" + d, r.p2))) for d in DRONES}
        V["goal"] = best
        return "`goal_dist_drone_1..3`: " + "; ".join("%s %.2f m" % (d, best[d]) for d in DRONES), all(v <= GATE_GOAL for v in best.values())
    gate("far goal reached per drone", "closest approach ≤ 0.40 m (commander arrival radius; spec draft said 0.3 m)", "-", f_goal,
         tuple("goal_dist_" + d for d in DRONES))

    # ---- peak speed
    def f_speed(r):
        pk = {d: float(np.nanmax(r.col("speed_" + d))) for d in DRONES}
        m = max(pk.values())
        V["peak"] = m
        return "`speed_drone_1..3`: %.2f m/s (%s)" % (m, ", ".join("%s %.2f" % (d, pk[d]) for d in DRONES)), m <= GATE_SPEED
    gate("peak speed ≤ 4.2 m/s", "≤ 4.2 m/s (cap 4.0 + 5 %), over every row including takeoff and landing (conservative)", "-", f_speed, tuple("speed_" + d for d in DRONES))

    # ---- landing: commander ACKs, then MAVROS state
    land = R.read(out, "landing_evidence.txt")
    done = sorted(set(re.findall(r"(drone_\d): landed, disarmed", land)))
    # Iron rules 2 and 5: the commander's ACK log is not an arming display -> info only; the MAVROS row below is the gate.
    R.row(rows, "landed, disarmed ×3 (commander ACK)", "informational (ACK log, not an arming display)",
          ", ".join(done) if done else "none — no landed, disarmed line in landing_evidence.txt", "-", None, gate=False)
    R.landing_rows(rows, out)

    # ---- live vs bag cross-check
    cr = None
    if live and bag:
        try:
            cr = M.crosscheck(live[1], live[2], bag[1], bag[2], _series())
        except (ValueError, KeyError, IndexError):
            cr = None
    ctx["crosscheck"] = cr
    R.crosscheck_rows(rows, cr, "minimum distance")
    if rows[-1].verdict == "FAIL":   # spec: live/offline mismatch -> UNVERIFIED (the run cannot PASS, but nothing is proven wrong)
        rows[-1].verdict = "UNVERIFIED"
    # A missing metrics file is already UNVERIFIED in the gate rows above; listing it as extra evidence would make
    # report.evidence_rows FAIL the bag row instead (INCOMPLETE is the honest verdict for missing evidence).
    extra = tuple(f for f in ("metrics.csv", "metrics_bag.csv") if (out / f).is_file())
    R.evidence_rows(rows, out, heavy, env["BAG_PREFIX"], extra_files=extra)

    # ---- info rows from the CSV
    if live:
        R.row(rows, "metrics node offsets (read once at start)", "informational (CSV header)",
              "offsets %s; t0_unix %s" % (live[0].get("offsets", "n/a"), live[0].get("t0_unix", "n/a")), "-", None, gate=False)
        r = run
        dur = float(r.col("t_s", r.p2)[-1] - r.col("t_s", r.p2)[0]) if len(r.p2) > 1 else 0.0
        hz = (len(r.p2) - 1) / dur if dur > 0 else 0.0
        R.row(rows, "window / samples", "informational (phase 2)", "%.1f s, %d rows (%d total), %.1f Hz" % (dur, len(r.p2), len(r.data), hz), "-", None, gate=False)
    else:
        for c in ("metrics node offsets (read once at start)", "window / samples"):
            R.row(rows, c, "informational", "n/a — %s" % why, "-", None, gate=False)
    ctx["reading"] = _reading(V)
    ctx["caveats"] = ["The %s s window is wall-clock; PX4 lockstep runs about 1.3× faster than the wall clock, so it is about %.0f s of vehicle time (the duration is not a gate)."
                      % (env.get("DURATION_S", "45"), float(env.get("DURATION_S", "45")) / 1.32)]
    return rows, ctx


def _all_phase_min(r):
    """nanmin over d_12/d_13/d_23 across every row, with the pair, t and the phase it fell in."""
    d = np.column_stack([r.col(p) for p in PAIRS])
    if np.all(np.isnan(d)):
        return "n/a — every pair distance is NaN"
    i, j = np.unravel_index(int(np.nanargmin(d)), d.shape)
    ph = int(r.col("phase")[i])
    seen2 = bool(np.any(r.col("phase")[:i] == 2))
    where = {1: "takeoff", 2: "test window", 3: "landing"}.get(ph, "after landing" if seen2 else "before takeoff")
    return "`d_12`/`d_13`/`d_23`: %.2f m (%s at t=%.1f s, %s)" % (d[i, j], PAIRS[j], float(r.col("t_s")[i]), where)


def _series():
    import importlib.util
    spec = importlib.util.spec_from_file_location("crossing_metrics_for_gates", pathlib.Path(__file__).with_name("metrics.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.SERIES


def _reading(V):
    if "min_d" not in V:
        return "[Figure 1](#fig-1) plots the pairwise distances; the live metrics.csv could not be read, so no value is reported."
    s = ("[Figure 1](#fig-1) plots the three pairwise distances and their running minimum against the 1.10 m (2r) gate. "
         "The closest approach was %.2f m (%s at t=%.1f s), %+.2f m against the gate and %+.2f m against ledger #4's 1.02 m."
         % (V["min_d"], V["min_pair"], V["min_t"], V["min_d"] - GATE_2R, V["min_d"] - LEDGER4))
    if "peak" in V and "goal" in V:
        s += " Peak speed was %.2f m/s (gate 4.2) and the far goals were reached to within %.2f m." % (V["peak"], max(V["goal"].values()))
    return s


def _status(rows, prefix):
    return next((r.verdict for r in rows if r.check.startswith(prefix)), "UNVERIFIED")


def ledger_sentence(rows, ctx, verdict):
    V = ctx.get("values", {})
    x = lambda k, f: (f % V[k]) if k in V else "n/a"
    cbf = ",".join(d.replace("drone_", "") for d in V.get("cbf_drones", [])) or "nobody"
    landed = _status(rows, "post-flight armed") == "PASS"   # MAVROS state only, never the ACK log
    s = ("CBF crossing, 3 drones antipodal, cbf_sim.yaml 2.0 / 4.0 m/s, live metrics: %s — min pairwise distance %s m (2r 1.10), "
         "emergency %s, fence breach %s, peak %s m/s, CBF on %s, landed + DISARMED ×3 %s, bag cross-check %s"
         % (verdict, x("min_d", "%.2f"), x("emerg", "%d"), x("breach", "%d"), x("peak", "%.2f"), cbf,
            "yes" if landed else "NOT shown", _status(rows, "live vs bag")))
    for v in ("FAIL", "UNVERIFIED"):
        names = [r.check for r in rows if r.gate and r.verdict == v]
        if names:
            s += "; %s: %s" % (v, ", ".join(names))
    return s


def figure_caption(ctx):
    return ("Pairwise distances d_12, d_13 and d_23 and their running minimum against wall-clock time, with the 1.10 m (2r) gate line and the "
            "0.55 m (r) line; shaded bands mark the takeoff and land phases. Drawn from the run's metrics.csv by "
            "`tools/sim.sh figures crossing <run>`.")
