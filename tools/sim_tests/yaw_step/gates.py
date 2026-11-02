"""Gates of the one-drone yaw-step test (NEAR-789), sim-only (iron rule 9: no value here is ported to the drone).

report.py calls build_rows(out, heavy, env), ledger_sentence(rows, ctx, verdict), figure_caption(ctx).

Sources (TEST_STANDARD rule 4 deviation, stated in docs/superpowers/plans/2026-11-02-sim-yaw-step-test.md):
  heavy/px4_drone_1.csv     PX4 ulog of drone_1, VEHICLE time (tools/live/ulog_yaw_dump.py) -> tools/live/yaw_core.py:
                            every time gate (settle, ring, swing-back rate) and drift; overshoot too
  out/metrics.csv           live 40 Hz odometry (wall clock): the same overshoot recomputed per pulse (must agree within
                            1.0 deg, else the overshoot gate is UNVERIFIED), the live yaw sign; metrics_bag.csv cross-check
  out/test_stdout.log       fly.sh's wall stamps `[<unix s>] pulse k/i onset sign=+1 rate=1.000` / `pulse k/i release`,
                            `turn onset|release`, `tap onset|release`: ONLY stamped pulses are gated. The ulog's pulses
                            are matched to the stamps in order (sign + onset spacing); the patch-0007 turn (0.5 rad/s =
                            28.6 deg/s, above yaw_core's 20 deg/s plateau, with the 0.75 m tap in its window) is matched
                            to its own stamp and never gated.
  out/px4_param_changes.txt MC_YAW* changes PX4 applied (ulog), out/changes.log the owner-rule log of fly.sh's sweep
                            (`drone_1/NAME` lines, written by tools/lib/px4_param_set.sh, CHG-0020). fly.sh's stop
                            lines `PARAM MISMATCH|REFUSED|UNVERIFIED: …` in test_stdout.log judge "sweep completed".
Gates judge sweep set 0 (the booted airframe gains) only; every gate = the worst set-0 pulse. A set-0 pulse without
numbers (unreleased, short window, NaN, not in the ulog, or a stamp/ulog mismatch) never passes: the metric gates go
UNVERIFIED (FAIL wins when another pulse is measured over the limit) and the "set-0 pulses" row is FAIL for an
unreleased pulse, UNVERIFIED otherwise.

Gate values (owner decides; written before the run, never moved after). Baseline: keyboard sessions 2026-10-30,
±8–17° ring at ~0.8 Hz for >= 10 s, no ulog.
  overshoot <= 3.0 deg        at 57 deg/s a 3 deg overrun is ~50 ms of continued turning: the lag of a well-damped loop
  settle to ±2 deg <= 2.0 s   a turn in place has no outer position loop to wait for (hover-step bar 3 s for 1 m)
  ring crossings <= 1         one swing back is lag; a second crossing is the owner's limit cycle
  swing back <= 30 deg/s      yaw_core peak_rate_dps: the fastest rotation AGAINST the turn after release must stay below
                              half the commanded 57 deg/s; peak_rate_abs_dps (always ~57 at release) is info only
  xy drift <= 0.15 m          a turn in place must not move the drone more than a 1 m step may overshoot
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
import changes_log  # noqa: E402
import metrics_core as M  # noqa: E402
import report as R  # noqa: E402
import yaw_core as Y  # noqa: E402

AIRFRAME = _TOOLS.parent / "AirStack/simulation/isaac-sim/px4/airframes/10090_pegasus_starling2max"
GATE_OVERSHOOT_DEG, GATE_SETTLE_S, GATE_RING, GATE_SWING_DPS, GATE_DRIFT_M = 3.0, 2.0, 1, 30.0, 0.15
LIVE_ULOG_TOL_DEG = 1.0
GAIN_RTOL = 1e-3
SPACING_TOL = 0.25            # each onset spacing ratio (vehicle / wall) within 25 % of their median, else a mismatch
U5_RATE_MIN, U5_SPAN_DEG = 1e-6, 10.0
BASE = "keyboard 2026-10-30: ±8–17° ring ~0.8 Hz, no ulog"
STAMP = re.compile(r"^\[(\d+\.\d+)\] (?:pulse (\d+)/(\d+)|(turn)|(tap)) (onset|release)(?: sign=([+-]\d+) rate=([0-9.]+))?")
MARKERS = {"ff_dps": "vehicle_attitude_setpoint.yaw_sp_move_rate (20 Hz; U3: it carries the pulses in offboard)",
           "yawspeed_sp_dps": "trajectory_setpoint.yawspeed (5 Hz fallback: yaw_sp_move_rate showed no pulse, U3)"}


# ------------------------------------------------------------------------------------------------ inputs
def parse_stamps(text):
    """(pulses, tap): pulses = [dict(kind pulse|turn, k, i, sign, rate, w_on, w_rel)] in stamp order; tap = dict or None."""
    items, tap = [], None
    for line in text.splitlines():
        mm = STAMP.match(line.strip())
        if not mm:
            continue
        t, k, i, turn, tp, ev, sg, rate = mm.groups()
        t = float(t)
        if tp:
            tap = tap or {"w_on": None, "w_rel": None}
            tap["w_on" if ev == "onset" else "w_rel"] = t
            continue
        key = ("turn", None, None) if turn else ("pulse", int(k), int(i))
        if ev == "onset":
            items.append(dict(kind=key[0], k=key[1], i=key[2], sign=int(sg) if sg else 1, rate=float(rate) if rate else float("nan"),
                              w_on=t, w_rel=None))
        else:
            for e in reversed(items):
                if (e["kind"], e["k"], e["i"]) == key and e["w_rel"] is None:
                    e["w_rel"] = t
                    break
    return items, tap


def fly_args(out, env):
    """(n per direction, rate rad/s, sweep sets) from run_meta.txt's fly_args line (what ran), else test.env."""
    mm = re.search(r"^fly_args=(.*)$", R.read(out, "run_meta.txt"), re.M)
    toks = (mm.group(1) if mm else env.get("FLY_ARGS", "")).split()
    try:
        n = int(float(toks[0])) if toks else 3
        rate = float(toks[1]) if len(toks) > 1 else 1.0
    except ValueError:
        n, rate = 3, 1.0
    sweep = [s for s in (toks[3] if len(toks) > 3 else "").split(";") if s.strip()]
    return n, rate, sweep


def airframe_gains(path=AIRFRAME):
    try:
        txt = pathlib.Path(path).read_text()
    except OSError:
        return {}
    return {mm.group(1): float(mm.group(2)) for mm in re.finditer(r"^param set-default (MC_YAW_P|MC_YAWRATE_[PIDK]) ([0-9.eE+-]+)", txt, re.M)}


def _close(a, b, rtol=GAIN_RTOL):
    return a is not None and b is not None and abs(a - b) <= rtol * max(abs(a), abs(b)) + 1e-9


def match(ulog, stamps):
    """Pair ulog pulses with fly.sh's stamps in order. (pairs [(stamp, ulog pulse | None)], spacing scale, problem | None).
    Accepted: same count, or fewer ulog pulses when the last one never released (the rest of the flight merged into
    it); every pair the same sign; each onset spacing (vehicle s / wall s) within SPACING_TOL of the median."""
    if not stamps:
        return [], float("nan"), "no pulse stamps in test_stdout.log"
    pairs = [(e, ulog[j] if j < len(ulog) else None) for j, e in enumerate(stamps)]
    if not ulog:
        return pairs, float("nan"), "the ulog shows no yaw pulse"
    if len(ulog) > len(stamps):
        return pairs, float("nan"), "the ulog shows %d yaw pulses, fly.sh stamped %d" % (len(ulog), len(stamps))
    if len(ulog) < len(stamps) and ulog[-1]["released"]:
        return pairs, float("nan"), "the ulog shows %d yaw pulses, fly.sh stamped %d" % (len(ulog), len(stamps))
    bad = [j + 1 for j, u in enumerate(ulog) if u["sign"] != stamps[j]["sign"]]
    if bad:
        return pairs, float("nan"), "ulog pulse(s) %s have the other sign than the stamp" % ",".join(map(str, bad))
    ratios = []
    for j in range(len(ulog) - 1):
        dw = stamps[j + 1]["w_on"] - stamps[j]["w_on"]
        ratios.append((ulog[j + 1]["onset_s"] - ulog[j]["onset_s"]) / dw if dw > 0 else float("nan"))
    scale = float(np.median(ratios)) if ratios else float("nan")
    if ratios and (any(not r > 0 for r in ratios) or any(abs(r / scale - 1.0) > SPACING_TOL for r in ratios)):
        return pairs, scale, "onset spacing vehicle/wall %s does not follow the stamps" % ", ".join("%.2f" % r for r in ratios)
    return pairs, scale, None


def label(e):
    return "pulse turn (patch-0007)" if e["kind"] == "turn" else "pulse %d/%d (%s)" % (e["k"], e["i"], "+" if e["sign"] > 0 else "−")


def _g(x, f="%.1f"):
    return "n/a" if x is None or (isinstance(x, float) and math.isnan(x)) else f % x


def gains_text(g):
    return "MC_YAW_P %s, MC_YAWRATE_P/I/D/K %s" % (_g(g.get("MC_YAW_P"), "%g"),
                                                   "/".join(_g(g.get(k), "%g") for k in ("MC_YAWRATE_P", "MC_YAWRATE_I", "MC_YAWRATE_D", "MC_YAWRATE_K")))


# ------------------------------------------------------------------------------------------------ rows
def build_rows(out, heavy, env):
    out, heavy = pathlib.Path(out), pathlib.Path(heavy) if heavy is not None else None
    rows = []
    ctx = {"headline": "worst overshoot after release (set 0)", "headline_row": "heading overshoot", "crosscheck": None,
           "values": {}, "caveats": []}
    V = ctx["values"]
    R.isaac_rows(rows, out, n=1)

    # ---- live metrics.csv (coverage, live overshoot + sign, U5, cross-check)
    live = bag = None
    why_live = None
    try:
        live = M.read_metrics_csv(out / "metrics.csv")
    except (OSError, M.MetricsCsvError) as e:
        why_live = "metrics.csv %s" % ("missing" if isinstance(e, FileNotFoundError) else "unreadable: %s" % e)
    try:
        bag = M.read_metrics_csv(out / "metrics_bag.csv")
    except (OSError, M.MetricsCsvError):
        bag = None
    has_tp = live is not None and "t_s" in live[1] and "phase" in live[1]
    R.coverage_row(rows, out, M.coverage(live[1], live[2]) if has_tp else None, M.STALE_S, why_live or "metrics.csv lacks t_s/phase")

    # ---- the ulog, the stamps, the match
    n, rate, sweep = fly_args(out, env)
    V.update(n=n, rate=rate, sets=1 + len(sweep))
    stdout = R.read(out, "test_stdout.log")
    stamps, tap = parse_stamps(stdout)
    flown = 0                                  # sets whose 2N pulses were all stamped onset + release, counted from set 0
    while sum(1 for e in stamps if e["kind"] == "pulse" and e["k"] == flown and e["w_rel"] is not None) == 2 * n:
        flown += 1
    V["flown"] = flown
    csv = heavy / "px4_drone_1.csv" if heavy is not None else None
    res, why_px4 = None, None
    try:
        res = Y.analyse(csv, out / "px4_param_changes.txt", wall_stamps=[(e["w_on"], e["w_rel"]) for e in stamps])
    except FileNotFoundError:
        why_px4 = "px4_drone_1.csv missing (no drone_1 ulog dump)"
    except (OSError, ValueError, TypeError) as e:
        why_px4 = "px4_drone_1.csv unreadable: %s" % e
    pairs, scale, problem = match(res["pulses"], stamps) if res else ([(e, None) for e in stamps], float("nan"), None)
    if res and not (scale > 0):
        ts = [u["time_scale"] for e, u in pairs if u is not None and not math.isnan(u.get("time_scale", float("nan")))]
        scale = float(np.median(ts)) if ts else float("nan")
    V["scale"] = scale
    set0 = [(e, u) for e, u in pairs if e["kind"] == "pulse" and e["k"] == 0]

    def lacks(e, u):
        """Why a set-0 pulse has no numbers (None = it has them)."""
        if problem:
            return "match: " + problem
        if u is None:
            return "not in the ulog"
        if u["post_status"] != "ok":
            return "post_status " + u["post_status"]
        return None

    measured = [(e, u) for e, u in set0 if lacks(e, u) is None]
    missing = [(e, lacks(e, u)) for e, u in set0 if lacks(e, u) is not None]

    # ---- set-0 pulses flown and analysable
    crit0 = "fly.sh stamped 2N = %d set-0 pulses; the ulog shows the same (order, sign, onset spacing); each released with ≥ %.0f s of NaN-free data after it" % (2 * n, Y.MIN_POST_WINDOW_S)
    if res is None:
        R.row(rows, "set-0 pulses flown and analysable", crit0, "n/a — " + why_px4, BASE, None)
    elif problem:
        R.row(rows, "set-0 pulses flown and analysable", crit0, "n/a — " + problem, BASE, None)
    else:
        unrel = [label(e) for e, u in set0 if u is not None and not u["released"]]
        txt = "%d stamped, %d with numbers" % (len(set0), len(measured))
        if unrel:
            R.row(rows, "set-0 pulses flown and analysable", crit0, txt + "; unreleased (yaw setpoint never back to 0): " + ", ".join(unrel), BASE, False)
        elif len(set0) != 2 * n or missing:
            R.row(rows, "set-0 pulses flown and analysable", crit0, txt + ("; " + "; ".join("%s %s" % (label(e), w) for e, w in missing) if missing else "")
                  + ("" if len(set0) == 2 * n else "; expected %d" % (2 * n)), BASE, None)
        else:
            R.row(rows, "set-0 pulses flown and analysable", crit0, txt + " (sign + spacing match the stamps)", BASE, True)

    # ---- the per-pulse gates (worst set-0 pulse)
    def metric_gate(check, crit, key, value, ok, fmt):
        if res is None:
            return R.row(rows, check, crit, "n/a — " + why_px4, BASE, None)
        if problem:
            return R.row(rows, check, crit, "n/a — match: " + problem, BASE, None)
        vals = [(e, value(u)) for e, u in measured]
        nan = [(e, "`%s` NaN" % key) for e, x in vals if x is None or (isinstance(x, float) and math.isnan(x))]
        vals = [(e, x) for e, x in vals if not any(e is n for n, _ in nan)]
        fails = [(e, x) for e, x in vals if not ok(x)]
        worst = max(vals, key=lambda ex: math.inf if ex[1] is None else ex[1]) if vals else None
        txt = "`%s`: worst %s (%s); %d of %d set-0 pulses with numbers" % (key, fmt(worst[1]) if worst else "n/a",
                                                                            label(worst[0]) if worst else "-", len(vals), len(set0))
        if missing or nan:
            txt += "; no numbers: " + ", ".join("%s%s" % (label(e), " (%s)" % w if w.startswith("`") else "") for e, w in missing + nan)
        V[key] = worst[1] if worst else None
        return R.row(rows, check, crit, txt, BASE, False if fails else (None if (missing or nan or not vals) else True))

    inf = lambda x: math.inf if x is None else x
    ov = metric_gate("heading overshoot ≤ 3.0°", "max over set-0 pulses of the heading's overrun past its final value after release (PX4 ulog, unwrapped ENU)",
                     "overshoot_deg", lambda u: u["overshoot_deg"], lambda x: x <= GATE_OVERSHOOT_DEG, lambda x: "%.2f°" % x)
    metric_gate("settle to ±2° ≤ 2.0 s (vehicle)", "time from release until the heading stays within ±2° of its final value, PX4 vehicle time; not settled in the window = FAIL",
                "settle_s", lambda u: inf(u["settle_s"]), lambda x: x <= GATE_SETTLE_S, lambda x: "not settled" if math.isinf(x) else "%.2f s" % x)
    metric_gate("ring crossings ≤ 1", "zero crossings of (heading − final) after it first enters the band, 0.5° hysteresis",
                "ring_crossings", lambda u: u["ring_crossings"], lambda x: x <= GATE_RING, lambda x: "%d" % x)
    metric_gate("swing back ≤ 30 °/s", "yaw_core `peak_rate_dps`: fastest body yaw rate AGAINST the turn in [release, +3 s] (PX4 vehicle_angular_velocity); `peak_rate_abs_dps` is info",
                "peak_rate_dps", lambda u: u["peak_rate_dps"], lambda x: x <= GATE_SWING_DPS, lambda x: "%.1f °/s" % x)
    metric_gate("xy drift ≤ 0.15 m", "max horizontal distance from the onset position over pulse + window (PX4 vehicle_local_position)",
                "xy_drift_m", lambda u: u["xy_drift_m"], lambda x: x <= GATE_DRIFT_M, lambda x: "%.3f m" % x)

    # ---- yaw sign: ulog ENU turn and live heading change both along the commanded sign
    t_live = h_live = t0_unix = None
    if live is not None and "heading_rel_deg" in live[1]:
        t_live, h_live = live[2][:, live[1].index("t_s")], live[2][:, live[1].index("heading_rel_deg")]
        try:
            t0_unix = float(live[0]["t0_unix"])
        except (KeyError, ValueError):
            t0_unix = None

    def live_at(t):
        ok = ~np.isnan(h_live)
        return float(np.interp(t, t_live[ok], h_live[ok])) if ok.any() else float("nan")

    crit_sign = "+angular.z (ENU, CCW) raises the ENU heading: ulog `turn_deg` and live `heading_rel_deg` change over the pulse both along the command"
    if res is None:
        R.row(rows, "yaw sign", crit_sign, "n/a — " + why_px4, "-", None)
    elif problem:
        R.row(rows, "yaw sign", crit_sign, "n/a — match: " + problem, "-", None)
    else:
        ul = [(e, u["turn_deg"] * e["sign"] > 0) for e, u in measured]
        lv = []
        if t_live is not None and t0_unix is not None:
            for e, u in measured:
                if e["w_rel"] is not None:
                    dh = live_at(e["w_rel"] - t0_unix) - live_at(e["w_on"] - t0_unix)
                    lv.append((e, dh * e["sign"] > 0 if not math.isnan(dh) else None))
        bad = [label(e) for e, ok in ul + lv if ok is False]
        txt = "ulog `turn_deg` along the command %d/%d, live `heading_rel_deg` change %d/%d" % (
            sum(1 for _, ok in ul if ok), len(set0), sum(1 for _, ok in lv if ok), len(set0))
        if measured:
            e, u = measured[0]
            txt += " (%s: ulog %+.1f°" % (label(e), u["turn_deg"]) + (", live %+.1f°)" % (live_at(e["w_rel"] - t0_unix) - live_at(e["w_on"] - t0_unix))
                                                                    if lv and e["w_rel"] is not None else ")")
        if bad:
            txt += "; WRONG sign: " + ", ".join(sorted(set(bad)))
        complete = not missing and len(lv) == len(set0) and all(ok is not None for _, ok in lv) and measured
        R.row(rows, "yaw sign", crit_sign, txt, "-", False if bad else (True if complete else None))

    # ---- booted gains = airframe file; set 0 flew them
    af = airframe_gains()
    crit_g = "ulog header MC_YAW_P, MC_YAWRATE_P/I/D/K = the `param set-default` lines of 10090_pegasus_starling2max (rel 1e-3), and set 0 flew them"
    if res is None:
        R.row(rows, "booted gains = airframe file", crit_g, "n/a — " + why_px4, "-", None)
    else:
        hdr = res["header_gains"]
        diffs = ["%s ulog %s vs file %s" % (k, _g(hdr.get(k), "%g"), _g(af.get(k), "%g")) for k in Y.GAIN_KEYS if not _close(hdr.get(k), af.get(k))]
        moved = [label(e) for e, u in set0 if u is not None and any(not _close(u["gains"].get(k), hdr.get(k)) for k in Y.GAIN_KEYS)]
        V["gains0"] = gains_text(hdr)
        txt = "ulog header %s" % gains_text(hdr) + (" = airframe file" if not diffs else "; differs: " + "; ".join(diffs))
        if moved:
            txt += "; set 0 flew other gains: " + ", ".join(moved)
        unknown = [k for k in Y.GAIN_KEYS if hdr.get(k) is None or af.get(k) is None]
        R.row(rows, "booted gains = airframe file", crit_g, txt, "-", None if unknown else (not diffs and not moved))

    # ---- live vs ulog overshoot (per pulse, within 1.0 deg)
    crit_lu = "per set-0 pulse, overshoot from live `heading_rel_deg` (yaw_core.measure_pulse on metrics.csv, stamps via t0_unix) within %.1f° of the ulog's" % LIVE_ULOG_TOL_DEG
    if res is None:
        lu = R.row(rows, "live vs ulog overshoot", crit_lu, "n/a — " + why_px4, "-", None)
    elif problem:
        lu = R.row(rows, "live vs ulog overshoot", crit_lu, "n/a — match: " + problem, "-", None)
    elif t_live is None or t0_unix is None:
        lu = R.row(rows, "live vs ulog overshoot", crit_lu, "n/a — " + (why_live or "metrics.csv lacks heading_rel_deg or t0_unix"), "-", None)
    else:
        diffs, nolive = [], []
        zeros = np.zeros_like(t_live)
        for e, u in measured:
            if e["w_rel"] is None or not (scale > 0):
                nolive.append(label(e))
                continue
            on_l, rel_l = e["w_on"] - t0_unix, e["w_rel"] - t0_unix
            nxt = [x["w_on"] - t0_unix for x in stamps if x["w_on"] > e["w_on"]]
            t_end = min(rel_l + (u["t_end_s"] - u["release_s"]) / scale, (min(nxt) - 0.5 / scale) if nxt else math.inf, float(t_live[-1]))
            p = Y.Pulse(on_l, rel_l, e["sign"], float("nan"), True)
            lm = Y.measure_pulse(p, t_live, h_live, zeros, zeros, zeros, t_end)
            if lm["post_status"] != "ok":
                nolive.append("%s (%s)" % (label(e), lm["post_status"]))
                continue
            diffs.append((e, lm["overshoot_deg"], u["overshoot_deg"]))
        worst = max(diffs, key=lambda d: abs(d[1] - d[2])) if diffs else None
        txt = ("max |live − ulog| %.2f° (%s: live %.2f°, ulog %.2f°); %d of %d compared" % (abs(worst[1] - worst[2]), label(worst[0]), worst[1], worst[2], len(diffs), len(set0))
               if worst else "nothing compared")
        if nolive or missing:
            txt += "; not compared: " + ", ".join(nolive + [label(e) for e, _ in missing])
        agree = worst is not None and abs(worst[1] - worst[2]) <= LIVE_ULOG_TOL_DEG
        lu = R.row(rows, "live vs ulog overshoot", crit_lu, txt, "-", (True if not (nolive or missing) else None) if agree else (None if worst is None else False))
    if lu.verdict == "FAIL":          # nothing proven wrong, but what was watched is not what is gated: UNVERIFIED
        lu.verdict = "UNVERIFIED"
    if lu.verdict != "PASS":
        ovr = next(r for r in rows if r.check.startswith("heading overshoot"))
        if ovr.verdict != "UNVERIFIED":
            ovr.measured += " — UNVERIFIED: live vs ulog overshoot not PASS"
            ovr.verdict = "UNVERIFIED"

    # ---- live parameter changes: every MC_YAW* change PX4 applied has a changes.log line (owner rule 2026-11-02)
    # drone_1's lines only: fly.sh's sweep writes `drone_1/NAME` through px4_param_set.sh (CHG-0020), so a bare name
    # is not a line of this drone; a REFUSED line never reached PX4 (CHG-0018)
    log_lines = [c for c in (changes_log.parse_change(l) for l in R.read(out, "changes.log").splitlines())
                 if c and c["target"] == "drone_1" and not c["refused"]]
    ul_changes = res["changes"] if res else []
    crit_c = "every MC_YAW* change in the ulog (px4_param_changes.txt) has a changes.log line, same name and value (owner rule 2026-11-02)"
    if not ul_changes and not log_lines and not sweep:
        R.row(rows, "live parameter changes logged", "informational (no sweep in this run)", "none — ulog and changes.log list no change", "-", None, gate=False)
    elif res is None:
        R.row(rows, "live parameter changes logged", crit_c, "n/a — " + why_px4, "-", None)
    elif not (out / "px4_param_changes.txt").is_file():
        R.row(rows, "live parameter changes logged", crit_c, "n/a — px4_param_changes.txt missing", "-", None)
    else:
        free, unlogged = list(log_lines), []        # each changes.log line accounts for ONE ulog change (same value twice = two lines)
        for t, nm, val in ul_changes:
            hit = next((c for c in free if c["name"] == nm and _close(c["new"], val)), None)
            if hit is None:
                unlogged.append((t, nm, val))
            else:
                free.remove(hit)
        txt = "ulog %d change(s), changes.log %d line(s)" % (len(ul_changes), len(log_lines))
        if unlogged:
            txt += "; NOT logged: " + ", ".join("%s=%g at %.1f s" % (nm, val, t) for t, nm, val in unlogged)
        if not ul_changes:
            txt += " — the sweep changed nothing PX4 logged"
        R.row(rows, "live parameter changes logged", crit_c, txt, "-", False if unlogged else (True if ul_changes else None))

    # ---- sweep completed (a short sweep must be visible) + booted gains restored before the turn / landing
    K = 1 + len(sweep)
    # fly.sh's own stop lines (column 0; the helper's echoed lines are indented): MISMATCH / REFUSED = proven not flown
    # as asked -> FAIL; UNVERIFIED = nothing confirmed the value PX4 holds -> never PASS (CHG-0020)
    stops = [l.strip() for l in stdout.splitlines() if re.match(r"PARAM (MISMATCH|REFUSED|UNVERIFIED)\b", l)]
    mism = [l for l in stops if not l.startswith("PARAM UNVERIFIED")]
    crit_s = ("fly.sh flew every requested gain set (2N stamped pulses each) and printed no PARAM MISMATCH, "
              "REFUSED or UNVERIFIED (each set read back through px4_param_set.sh)")
    if K == 1:
        R.row(rows, "sweep completed", "informational (no sweep in this run)", "set 0 only; %d set(s) flown" % flown, "-", None, gate=False)
    else:
        txt = "%d of %d sets flown (set 0 + %d of %d sweep sets)" % (flown, K, max(flown - 1, 0), K - 1)
        if stops:
            txt += "; " + (mism or stops)[0][:90]
        R.row(rows, "sweep completed", crit_s, txt, "-", False if mism else (True if flown >= K and not stops else None))
    crit_r = "every MC_YAW* the sweep changed is back at its ulog-header (booted) value before the patch-0007 turn (ulog changed_parameters)"
    if not ul_changes and K == 1:
        R.row(rows, "booted gains restored", "informational (no sweep in this run)", "nothing to restore", "-", None, gate=False)
    elif res is None:
        R.row(rows, "booted gains restored", crit_r, "n/a — " + why_px4, "-", None)
    else:
        hdr, last = res["header_gains"], {}
        for t, nm, val in sorted(ul_changes):
            last[nm] = (t, val)
        left = ["%s %g (booted %s)" % (nm, val, _g(hdr.get(nm), "%g")) for nm, (t, val) in last.items() if not _close(val, hdr.get(nm))]
        turn_u = next((u for e, u in pairs if e["kind"] == "turn" and u is not None), None)
        late = [nm for nm, (t, val) in last.items() if turn_u is not None and t >= turn_u["onset_s"]]
        if not last:
            R.row(rows, "booted gains restored", crit_r, "n/a — the ulog shows no MC_YAW* change", "-", None)
        else:
            txt = ("all %d back at booted" % len(last)) if not left else "NOT restored: " + ", ".join(left)
            if late:
                txt += "; restored only after the turn onset: " + ", ".join(late)
            R.row(rows, "booted gains restored", crit_r, txt, "-", not left and not late)

    # ---- landing, evidence, cross-check
    land = R.read(out, "landing_evidence.txt")
    done = sorted(set(re.findall(r"(drone_\d): landed, disarmed", land)))
    R.row(rows, "landed, disarmed (commander ACK)", "informational (ACK log, not an arming display)",
          ", ".join(done) if done else "none — no landed, disarmed line in landing_evidence.txt", "-", None, gate=False)
    R.landing_rows(rows, out, n=1)
    cr = None
    if live and bag:
        try:
            cr = M.crosscheck(live[1], live[2], bag[1], bag[2], _series())
        except (ValueError, KeyError, IndexError):
            cr = None
    ctx["crosscheck"] = cr
    R.crosscheck_rows(rows, cr, "heading_rel_deg")
    if rows[-1].verdict == "FAIL":
        rows[-1].verdict = "UNVERIFIED"
    extra = tuple(f for f in ("metrics.csv", "metrics_bag.csv") if (out / f).is_file())
    R.evidence_rows(rows, out, heavy, env["BAG_PREFIX"], extra_files=extra, n=1)

    # ---- info: per pulse, per gain set, patch-0007, U3/U4/U5, time scale, param changes
    _info_rows(rows, ctx, res, why_px4, pairs, problem, set0, measured, n, rate, scale, stamps, tap, heavy, live)
    ctx["reading"] = _reading(V, res is not None and not problem)
    ctx["caveats"].insert(0, "The %s s gap between pulses is wall-clock; in vehicle time it is the gap × the time scale (%s here; ~1.3 on the flat world). "
                          "Every time gate is PX4 vehicle time from the ulog; the figure's axis is wall clock." % (env.get("DURATION_S", "20"), _g(scale, "%.2f")))
    return rows, ctx


def _info_rows(rows, ctx, res, why_px4, pairs, problem, set0, measured, n, rate, scale, stamps, tap, heavy, live):
    info = lambda check, crit, meas: R.row(rows, check, crit, meas, "-", None, gate=False)
    if res is None:
        info("pulse table", "informational (PX4 ulog, vehicle time)", "n/a — " + why_px4)
    elif problem:
        for j, u in enumerate(res["pulses"]):
            info("ulog pulse %d (%s)" % (j + 1, "+" if u["sign"] > 0 else "−"), "informational (match unverified: %s)" % problem, _pulse_text(u))
    else:
        for e, u in pairs:
            if e["kind"] == "turn":
                if u is None:
                    txt = "not in the ulog; not gated (patch-0007 check)"
                else:
                    hdr = res["header_gains"]
                    booted = all(_close(u["gains"].get(k), hdr.get(k)) for k in Y.GAIN_KEYS)
                    txt = "turn %s at %s °/s, not gated; flew %s" % (_g(u["turn_deg"], "%+.0f°"), _g(u["plateau_dps"], "%.0f"),
                                                                   "booted gains" if booted else "NOT booted: " + gains_text(u["gains"]))
                info(label(e), "informational (0.5 rad/s for 3.14 s wall = 90° × the time scale in vehicle time, then the tap)", txt[:120])
            else:
                info(label(e), "informational (set %d; PX4 ulog, vehicle time)" % e["k"], "not in the ulog" if u is None else _pulse_text(u))
        for k in sorted({e["k"] for e, _ in pairs if e["kind"] == "pulse"}):
            mem = [(e, u) for e, u in pairs if e["kind"] == "pulse" and e["k"] == k]
            ok = [u for _, u in mem if u is not None and u["post_status"] == "ok"]
            g = next((u["gains"] for _, u in mem if u is not None), {})
            mx = lambda key: max((math.inf if u[key] is None else u[key]) for u in ok) if ok else None
            info("set %d: %s" % (k, "booted gains (gated)" if k == 0 else "sweep (info)"), "informational (gains in force from the ulog's changed_parameters)",
                 "%s — overshoot max %s, settle max %s, ring max %s, swing max %s, drift max %s; %d of %d with numbers"
                 % (gains_text(g), _g(mx("overshoot_deg"), "%.1f°"), _g(mx("settle_s"), "%.2f s"), _g(mx("ring_crossings"), "%d"),
                    _g(mx("peak_rate_dps"), "%.0f °/s"), _g(mx("xy_drift_m"), "%.2f m"), len(ok), len(mem)))
    # patch-0007 tap
    crit_tap = "informational: room-frame +x tap after the turn; a direction error ≈ the turn angle = the body-frame orbit (before patch 0007)"
    turn = next(((e, u) for e, u in pairs if e["kind"] == "turn"), None)
    if res is None:
        info("patch-0007 tap", crit_tap, "n/a — " + why_px4)
    elif problem or turn is None or turn[1] is None or not turn[1]["released"] or tap is None or None in (tap["w_on"], tap["w_rel"]) or turn[0]["w_rel"] is None or not (scale > 0):
        info("patch-0007 tap", crit_tap, "n/a — " + (("match: " + problem) if problem else "turn/tap stamps or the turn's ulog release missing"))
    else:
        e, u = turn
        t0 = u["release_s"] + (tap["w_on"] - e["w_rel"]) * scale
        t1 = t0 + (tap["w_rel"] - tap["w_on"]) * scale
        _, cols, data = Y.read_px4_csv(heavy / "px4_drone_1.csv")
        c = lambda name: data[:, cols.index(name)]
        tc = Y.tap_check(c("t_s"), c("x_ned"), c("y_ned"), Y.ned_to_enu_deg(c("heading_ned_deg")), t0, t1)
        info("patch-0007 tap", crit_tap, "direction error %.1f°, heading change %+.1f°, displacement %.2f m (vehicle %.1f–%.1f s)"
             % (tc["direction_err_deg"], tc["heading_change_deg"], tc["displacement_m"], t0, t1))
    if res is not None:
        info("pulse marker (U3)", "informational: which PX4 topic marks onset/release", MARKERS.get(res["marker"], res["marker"]))
        if res["marker"] != "ff_dps":
            ctx["caveats"].append("Pulse onsets and releases come from trajectory_setpoint.yawspeed (5 Hz, 0.2 s resolution): "
                                  "vehicle_attitude_setpoint.yaw_sp_move_rate showed no pulse (U3), so settle times carry up to 0.2 s of marker lag.")
        pl = [u["plateau_meas_dps"] for _, u in measured if not math.isnan(u["plateau_meas_dps"])]
        sp = [u["plateau_dps"] for _, u in measured]
        info("plateau measured vs commanded (U4)", "informational: body yaw rate during set-0 pulses vs the %.1f °/s commanded" % math.degrees(rate),
             ("measured %.1f–%.1f °/s, setpoint %.1f °/s, commanded %.1f °/s" % (min(pl), max(pl), float(np.median(sp)), math.degrees(rate))) if pl else "n/a — no set-0 pulse with numbers")
        tsc = [u["time_scale"] for _, u in measured if not math.isnan(u.get("time_scale", float("nan")))]
        info("time scale (vehicle s per wall s)", "informational, never a gate",
             "onset spacing median %s; per pulse %s" % (_g(scale, "%.3f"), ", ".join("%.2f" % x for x in tsc) if tsc else "n/a"))
        ch = res["changes"]
        info("px4_param_changes.txt", "informational: MC_YAW* changes PX4 applied (vehicle time)",
             ("; ".join("%.1f s %s=%g" % c for c in ch[:6]) + (" …" if len(ch) > 6 else "")) if ch else "none")
    # U5: odometry yaw rate
    crit5 = "informational: odometry twist.angular.z (live `yaw_rate_dps`) is plotted only, never gated"
    if live is None or "yaw_rate_dps" not in live[1] or "heading_rel_deg" not in live[1]:
        info("odometry yaw rate (U5)", crit5, "n/a — metrics.csv unreadable")
    else:
        cols, data = live[1], live[2]
        p2 = data[data[:, cols.index("phase")] == 2]
        r = np.abs(p2[:, cols.index("yaw_rate_dps")]); h = p2[:, cols.index("heading_rel_deg")]
        rmax = float(np.nanmax(r)) if np.any(~np.isnan(r)) else float("nan")
        span = float(np.nanmax(h) - np.nanmin(h)) if np.any(~np.isnan(h)) else float("nan")
        if (math.isnan(rmax) or rmax < U5_RATE_MIN) and span > U5_SPAN_DEG:
            info("odometry yaw rate (U5)", crit5, "odometry carries no yaw rate, U5: max |`yaw_rate_dps`| %s while `heading_rel_deg` spans %.0f°" % (_g(rmax, "%g"), span))
        else:
            info("odometry yaw rate (U5)", crit5, "present: max |`yaw_rate_dps`| %s °/s, `heading_rel_deg` span %s°" % (_g(rmax, "%.1f"), _g(span, "%.0f")))


def _pulse_text(u):
    """One per-pulse INFO cell, <= 120 chars."""
    if u["post_status"] != "ok":
        return ("no numbers: post_status %s (onset %.1f s, drift %s)" % (u["post_status"], u["onset_s"], _g(u["xy_drift_m"], "%.2f m")))[:120]
    s = ("on %.1f s, os %.1f°, settle %s, ring %d, swing %.0f °/s (abs %.0f), drift %.2f m, plat %.0f °/s, scale %s"
         % (u["onset_s"], u["overshoot_deg"], "not settled" if u["settle_s"] is None else "%.2f s" % u["settle_s"], u["ring_crossings"],
            u["peak_rate_dps"], u["peak_rate_abs_dps"], u["xy_drift_m"], u["plateau_meas_dps"], _g(u.get("time_scale"), "%.2f")))
    return s[:120]


def _series():
    import importlib.util
    spec = importlib.util.spec_from_file_location("yaw_step_metrics_for_gates", pathlib.Path(__file__).with_name("metrics.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.SERIES


def _reading(V, ok):
    s = "[Figure 1](#fig-1) plots the heading relative to the test start (live odometry, wall clock) with the ±2° settle band. "
    if not ok or V.get("overshoot_deg") is None:
        return s + "The PX4 ulog could not be matched to the scripted pulses, so no vehicle-time value is reported."
    st = V.get("settle_s")
    return s + ("Worst set-0 pulse after release, PX4 vehicle time: overshoot %.2f° (gate 3.0), settle %s (gate 2.0 s), %s ring crossing(s) (gate 1), "
                "swing back %.1f °/s (gate 30), drift %.3f m (gate 0.15)."
                % (V["overshoot_deg"], "not reached" if st is None or math.isinf(st) else "%.2f s" % st, _g(V.get("ring_crossings"), "%d"),
                   V.get("peak_rate_dps") or 0.0, V.get("xy_drift_m") or 0.0))


def _status(rows, prefix):
    return next((r.verdict for r in rows if r.check.startswith(prefix)), "UNVERIFIED")


def ledger_sentence(rows, ctx, verdict):
    V = ctx.get("values", {})
    st = V.get("settle_s")
    landed = _status(rows, "post-flight armed") == "PASS"
    s = ("yaw step, 1 drone, teleop_single.yaml, %d pulses ±%g rad/s per set, vehicle time: %s — overshoot %s, settle %s, ring %s, swing back %s, drift %s "
         "(set 0: %s); sweep %d of %d set(s) flown; landed + DISARMED %s"
         % (2 * V.get("n", 3), V.get("rate", 1.0), verdict, _g(V.get("overshoot_deg"), "%.2f°"),
            "n/a" if st is None else ("not reached" if math.isinf(st) else "%.2f s" % st), _g(V.get("ring_crossings"), "%d"),
            _g(V.get("peak_rate_dps"), "%.1f °/s"), _g(V.get("xy_drift_m"), "%.3f m"), V.get("gains0", "gains n/a"),
            max(V.get("flown", 0) - 1, 0), V.get("sets", 1) - 1, "yes" if landed else "NOT shown"))
    for vv in ("FAIL", "UNVERIFIED"):
        names = [r.check for r in rows if r.gate and r.verdict == vv]
        if names:
            s += "; %s: %s" % (vv, ", ".join(names))
    return s


def figure_caption(ctx):
    return ("Heading relative to the test start (`heading_rel_deg`, unwrapped, 40 Hz odometry) against wall-clock time, with the ±2° settle band; "
            "shaded bands mark takeoff and land. The gates are measured from the PX4 ulog in vehicle time, not on this axis. "
            "Drawn from metrics.csv by `tools/sim.sh figures yaw_step <run>`.")
