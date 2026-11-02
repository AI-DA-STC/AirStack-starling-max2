# tools/tests/test_yaw_step_gates.py
"""tools/sim_tests/yaw_step: gates on a synthetic run folder (ulog CSV in vehicle time + live metrics.csv in wall time +
fly.sh's stamp lines), fly.sh static checks, the five-file contract. Sim-only (iron rule 9). No docker, no ROS: fly.sh's
ROS side is checked statically only."""
import importlib.util
import math
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
TOOLS = HERE.parent
for p in (HERE, TOOLS, TOOLS / "live", TOOLS / "lib"):
    sys.path.insert(0, str(p))
import changes_log as C  # noqa: E402
import contract_check  # noqa: E402
import report as R  # noqa: E402
import synth_yaw as S  # noqa: E402

YAW = TOOLS / "sim_tests" / "yaw_step"
AIRFRAME = TOOLS.parent / "AirStack/simulation/isaac-sim/px4/airframes/10090_pegasus_starling2max"
FIX = HERE / "fixtures" / "run1"
SCALE = 1.32            # vehicle s per wall s (flat world, ledger #17-#19)
GAP_V = 26.0            # 20 s wall gap x 1.32
TURN_RATE = 28.6479     # 0.5 rad/s in deg/s: above yaw_core's 20 deg/s plateau, so the ulog shows it as a pulse


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def airframe_gains():
    """The airframe file's yaw gains, parsed independently of gates.py."""
    return {m.group(1): float(m.group(2)) for m in re.finditer(r"^param set-default (MC_YAW_P|MC_YAWRATE_[PIDK]) ([0-9.eE+-]+)",
                                                                 AIRFRAME.read_text(), re.M)}


def flight(n=3, sets=1, zeta=0.9, f_hz=1.5, ring_sets=(), turn=True):
    """(pulses, groups, extra stamp lines, tap moves): n pulses per direction per set, alternating +/-, GAP_V apart,
    then the patch-0007 turn (+90 deg at 0.5 rad/s) and the forward tap (0.75 m east)."""
    pulses, groups, t = [], [], 20.0
    for k in range(sets):
        for i in range(2 * n):
            z, f = (0.1, 0.8) if k in ring_sets else (zeta, f_hz)
            pulses.append(dict(onset=t, dur=1.0, sign=+1 if i % 2 == 0 else -1, zeta=z, f_hz=f))
            groups.append(k)
            t += GAP_V
        t += 10.0                                      # the sweep's param pulls between sets
    extra, moves = [], []
    if turn:
        pulses.append(dict(onset=t, dur=3.14 * SCALE, sign=+1, rate=TURN_RATE, zeta=0.9, f_hz=1.5, kind="turn"))
        groups.append(None)
        t_tap = t + 3.14 * SCALE + 5.0 * SCALE
        extra = [(t_tap, "tap onset vx=0.500"), (t_tap + 1.5 * SCALE, "tap release")]
        moves = [(t_tap, t_tap + 1.5 * SCALE, 0.75 / (1.5 * SCALE), 0.0)]
    return pulses, groups, extra, moves


def make_run(tmp, n=3, sets=1, sweep="", pulses=None, groups=None, extra=None, moves=None, px4=True, sign_flip=False,
             live_gain=1.0, yaw_rate=True, header=None, changes=(), log_changes=True, ring_sets=(), zeta=0.9, f_hz=1.5,
             nan_window=None, ff_zero=False, turn=True):
    tmp = pathlib.Path(tmp)
    out, heavy = tmp / "run", tmp / "heavy"
    out.mkdir()
    (heavy / "yaw_step_2026_11_02-12_00_00").mkdir(parents=True)
    (heavy / "yaw_step_2026_11_02-12_00_00" / "metadata.yaml").write_text("rosbag2_bagfile_information: {}\n")
    if pulses is None:
        pulses, groups, extra, moves = flight(n, sets, zeta, f_hz, ring_sets, turn)
    hdr = dict(airframe_gains(), **(header or {}))
    if px4:
        S.px4_csv(heavy / "px4_drone_1.csv", pulses, sign_flip=sign_flip, header=hdr, xy_moves=moves or (), tail_s=15.0,
                  nan_window=nan_window, ff_zero=ff_zero)
    pc = ["# MC_YAW* parameter changes of x.ulg, t_s = PX4 vehicle time (s since boot); sim only"]
    pc += ["%.6f %s %s" % (t + 100.0, name, v) for t, name, v in changes]
    (out / "px4_param_changes.txt").write_text("\n".join(pc) + "\n")
    if log_changes and changes:
        for t, name, v in changes:
            C.append_change(out / "changes.log", 1_800_000_000.0 + (t + 100.0) / SCALE, "drone_1/" + name, 2.8, v,
                            "yaw_step-sweep-set-1 (via ros2 param set)", readback=v)
    YM = _load("yaw_metrics_t", YAW / "metrics.py")
    S.metrics_csv(out / "metrics.csv", YM.SERIES, pulses, scale=SCALE, heading_gain=live_gain, yaw_rate=yaw_rate)
    shutil.copy(out / "metrics.csv", out / "metrics_bag.csv")
    S.stdout_log(out / "test_stdout.log", pulses, scale=SCALE, groups=[g if g is not None else 0 for g in groups], extra=extra or ())
    shutil.copy(FIX / "res_watch.log", out / "res_watch.log")
    (out / "armed_post.txt").write_text("drone_1 armed: false\n")
    (out / "landing_evidence.txt").write_text("[swarm_commander-2] drone_1: landed, disarmed (attempt 1)\n")
    (out / "isaac_evidence.txt").write_text("model_line=1 starling_cfg=1 autostart=1 unknown_model=0 cooking=0 ready=1\n")
    (out / "ulog_sysid_map.txt").write_text("2 /x.ulg 100\n")
    fly_args = ("%d 1.0 1.0" % n) + ((" " + sweep) if sweep else "")
    (out / "run_meta.txt").write_text("head_short=abc1234\ndirty_tools=0\nstarted=2026-11-02T12:00:00\ntz=+08\nnum_robots=1\nfly_args=%s\n" % fly_args)
    env = R.parse_env(YAW / "test.env")
    return out, heavy, env


def rows_of(out, heavy, env):
    G = _load("yaw_gates_t", YAW / "gates.py")
    return G, G.build_rows(out, heavy, env)


def v(rows, prefix):
    return next(r.verdict for r in rows if r.check.startswith(prefix))


def m(rows, prefix):
    return next(r.measured for r in rows if r.check.startswith(prefix))


GATES = ("heading overshoot", "settle", "ring", "swing back", "xy drift")


class YawStepGates(unittest.TestCase):
    def test_well_damped_run_passes(self):
        with tempfile.TemporaryDirectory() as d:
            out, heavy, env = make_run(d)
            _, (rows, ctx) = rows_of(out, heavy, env)
        self.assertEqual(R.overall_verdict(rows), "PASS", [(r.check, r.verdict, r.measured) for r in rows if r.gate and r.verdict != "PASS"])
        for g in GATES + ("yaw sign", "booted gains", "live vs ulog overshoot", "set-0 pulses", "live vs bag"):
            self.assertEqual(v(rows, g), "PASS", g)
        self.assertEqual(R.headline_text(rows, ctx), m(rows, "heading overshoot"))
        self.assertEqual(sum(1 for r in rows if re.match(r"pulse (\d+/\d+|turn)", r.check) and not r.gate), 6 + 1)   # 6 pulses + the turn

    def test_ring_fails_overshoot_settle_ring_and_swing(self):
        with tempfile.TemporaryDirectory() as d:
            out, heavy, env = make_run(d, zeta=0.1, f_hz=0.8)
            _, (rows, _) = rows_of(out, heavy, env)
        for g in ("heading overshoot", "settle", "ring", "swing back"):
            self.assertEqual(v(rows, g), "FAIL", g)
        self.assertEqual(R.overall_verdict(rows), "FAIL")

    def test_swing_gate_reads_peak_rate_dps_and_abs_is_info(self):          # reviewer change 1
        with tempfile.TemporaryDirectory() as d:
            out, heavy, env = make_run(d)
            _, (rows, _) = rows_of(out, heavy, env)
        self.assertIn("`peak_rate_dps`", m(rows, "swing back"))
        r = next(r for r in rows if r.check.startswith("pulse 0/1"))
        self.assertFalse(r.gate); self.assertIn("abs", r.measured)
        self.assertEqual(v(rows, "swing back"), "PASS")                        # abs ~57 deg/s at release never gates

    def test_unreleased_pulse_fails_the_flown_row_and_never_passes_a_gate(self):   # Review Focus 3 + reviewer change 2
        pulses, groups, _, _ = flight(n=3, turn=False)
        pulses[-1] = dict(pulses[-1], dur=None)
        with tempfile.TemporaryDirectory() as d:
            out, heavy, env = make_run(d, pulses=pulses, groups=groups, extra=(), moves=())
            _, (rows, _) = rows_of(out, heavy, env)
        self.assertEqual(v(rows, "set-0 pulses"), "FAIL")
        self.assertIn("unreleased", m(rows, "set-0 pulses"))
        for g in GATES:
            self.assertEqual(v(rows, g), "UNVERIFIED", g)
        self.assertIn("unreleased", next(r.measured for r in rows if r.check.startswith("pulse 0/6")))

    def test_nan_window_makes_the_gates_unverified_and_the_run_incomplete(self):
        with tempfile.TemporaryDirectory() as d:
            out, heavy, env = make_run(d, nan_window=(20.0 + GAP_V + 2.0, 20.0 + GAP_V + 3.0))   # after pulse 2's release
            _, (rows, _) = rows_of(out, heavy, env)
        self.assertEqual(v(rows, "set-0 pulses"), "UNVERIFIED")
        for g in GATES:
            self.assertEqual(v(rows, g), "UNVERIFIED", g)
        self.assertEqual(R.overall_verdict(rows), "INCOMPLETE")

    def test_missing_px4_csv_is_incomplete(self):                          # Review Focus 4
        with tempfile.TemporaryDirectory() as d:
            out, heavy, env = make_run(d, px4=False)
            _, (rows, _) = rows_of(out, heavy, env)
        for g in GATES + ("yaw sign", "booted gains", "live vs ulog overshoot", "set-0 pulses"):
            self.assertEqual(v(rows, g), "UNVERIFIED", g)
            self.assertIn("px4_drone_1.csv missing", m(rows, g), g)
        self.assertEqual(R.overall_verdict(rows), "INCOMPLETE")

    def test_yaw_sign_mismatch_fails(self):                                # Review Focus 5
        with tempfile.TemporaryDirectory() as d:
            out, heavy, env = make_run(d, sign_flip=True)
            _, (rows, _) = rows_of(out, heavy, env)
        self.assertEqual(v(rows, "yaw sign"), "FAIL")
        self.assertNotEqual(R.overall_verdict(rows), "PASS")

    def test_only_group_0_is_gated(self):
        changes = [(20.0 + 2 * GAP_V + 3.0, "MC_YAW_P", 1.0),               # between set 0 and set 1
                   (20.0 + 4 * GAP_V + 10.0 - 2.0, "MC_YAW_P", 2.8)]        # fly.sh restores before the 0007 turn
        with tempfile.TemporaryDirectory() as d:
            out, heavy, env = make_run(d, n=1, sets=2, sweep="MC_YAW_P=1.0", ring_sets=(1,), changes=changes)
            _, (rows, _) = rows_of(out, heavy, env)
        self.assertEqual(R.overall_verdict(rows), "PASS", [(r.check, r.verdict, r.measured) for r in rows if r.gate and r.verdict != "PASS"])
        s1 = next(r for r in rows if r.check.startswith("set 1"))
        self.assertFalse(s1.gate); self.assertIn("MC_YAW_P 1", s1.measured)
        self.assertEqual(v(rows, "live parameter changes logged"), "PASS")
        self.assertEqual(v(rows, "booted gains restored"), "PASS")
        self.assertEqual(v(rows, "sweep completed"), "PASS")
        self.assertIn("booted gains", m(rows, "pulse turn"))                 # the record says which gains the turn flew

    def test_a_sweep_that_never_restores_fails(self):                      # review Important 2
        changes = [(20.0 + 2 * GAP_V + 3.0, "MC_YAW_P", 1.0)]
        with tempfile.TemporaryDirectory() as d:
            out, heavy, env = make_run(d, n=1, sets=2, sweep="MC_YAW_P=1.0", changes=changes)
            _, (rows, _) = rows_of(out, heavy, env)
        self.assertEqual(v(rows, "booted gains restored"), "FAIL")
        self.assertIn("MC_YAW_P 1", m(rows, "booted gains restored"))
        self.assertIn("NOT booted", m(rows, "pulse turn"))

    def test_a_short_sweep_is_visible(self):                               # review Important 3
        changes = [(20.0 + 2 * GAP_V + 3.0, "MC_YAW_P", 1.0), (20.0 + 4 * GAP_V + 8.0, "MC_YAW_P", 2.8)]
        with tempfile.TemporaryDirectory() as d:          # 3 sets asked (2 sweep sets), 2 flown
            out, heavy, env = make_run(d, n=1, sets=2, sweep="MC_YAW_P=1.0;MC_YAW_P=1.4", changes=changes)
            G, (rows, ctx) = rows_of(out, heavy, env)
            self.assertEqual(v(rows, "sweep completed"), "UNVERIFIED")
            self.assertIn("2 of 3", m(rows, "sweep completed"))
            self.assertIn("sweep 1 of 2 set(s) flown", G.ledger_sentence(rows, ctx, "INCOMPLETE"))
            with open(out / "test_stdout.log", "a") as fh:
                fh.write("PARAM MISMATCH: MC_YAW_P set 1.4, read back 1.0 (mechanism None) -- sweep stopped\n")
            _, (rows, _) = rows_of(out, heavy, env)
        self.assertEqual(v(rows, "sweep completed"), "FAIL")

    def test_no_sweep_has_no_sweep_gate(self):
        with tempfile.TemporaryDirectory() as d:
            out, heavy, env = make_run(d)
            _, (rows, _) = rows_of(out, heavy, env)
        for c in ("sweep completed", "booted gains restored"):
            self.assertFalse(next(r for r in rows if r.check.startswith(c)).gate, c)

    def test_a_nan_swing_rate_is_unverified_not_fail(self):                # review minor
        with tempfile.TemporaryDirectory() as d:
            out, heavy, env = make_run(d)
            G = _load("yaw_gates_nan", YAW / "gates.py")
            real = G.Y.analyse
            def patched(*a, **k):
                res = real(*a, **k); res["pulses"][1]["peak_rate_dps"] = float("nan"); return res
            G.Y.analyse = patched
            try:
                rows, _ = G.build_rows(out, heavy, env)
            finally:
                G.Y.analyse = real
        self.assertEqual(v(rows, "swing back"), "UNVERIFIED")

    def test_the_same_value_set_twice_needs_two_log_lines(self):           # review minor
        t1, t2, t3 = 20.0 + 2 * GAP_V + 3.0, 20.0 + 4 * GAP_V + 13.0, 20.0 + 6 * GAP_V + 23.0
        changes = [(t1, "MC_YAW_P", 1.0), (t2, "MC_YAW_P", 1.4), (t3, "MC_YAW_P", 1.0), (t3 + 50.0, "MC_YAW_P", 2.8)]
        with tempfile.TemporaryDirectory() as d:
            out, heavy, env = make_run(d, n=1, sets=4, sweep="MC_YAW_P=1.0;MC_YAW_P=1.4;MC_YAW_P=1.0", changes=changes)
            lines = (out / "changes.log").read_text().splitlines()
            (out / "changes.log").write_text("\n".join(lines[:2] + lines[3:]) + "\n")     # the second 1.0 line lost
            _, (rows, _) = rows_of(out, heavy, env)
        self.assertEqual(v(rows, "live parameter changes logged"), "FAIL")
        self.assertIn("MC_YAW_P=1", m(rows, "live parameter changes logged"))

    def test_a_ulog_change_missing_from_changes_log_fails(self):           # owner rule 2026-11-02
        changes = [(20.0 + 2 * GAP_V + 3.0, "MC_YAW_P", 1.0)]
        with tempfile.TemporaryDirectory() as d:
            out, heavy, env = make_run(d, n=1, sets=2, sweep="MC_YAW_P=1.0", changes=changes, log_changes=False)
            _, (rows, _) = rows_of(out, heavy, env)
        self.assertEqual(v(rows, "live parameter changes logged"), "FAIL")

    def test_a_log_line_for_another_drone_does_not_count(self):            # CHG-0018: match drone_N/, not the bare name
        changes = [(20.0 + 2 * GAP_V + 3.0, "MC_YAW_P", 1.0)]
        # CHG-0020: fly.sh's sweep writes drone_1/ through px4_param_set.sh, so a bare name no longer counts either
        for prefix, verdict in (("drone_2/", "FAIL"), ("", "FAIL"), ("drone_1/", "PASS")):
            with tempfile.TemporaryDirectory() as d:
                out, heavy, env = make_run(d, n=1, sets=2, sweep="MC_YAW_P=1.0", changes=changes)
                log = (out / "changes.log").read_text().replace(" · drone_1/MC_YAW_P · ", " · %sMC_YAW_P · " % prefix)
                (out / "changes.log").write_text(log)
                _, (rows, _) = rows_of(out, heavy, env)
            self.assertEqual(v(rows, "live parameter changes logged"), verdict, prefix)

    def test_a_refused_log_line_does_not_count(self):                      # CHG-0018: a REFUSED set never reached PX4
        changes = [(20.0 + 2 * GAP_V + 3.0, "MC_YAW_P", 1.0)]
        with tempfile.TemporaryDirectory() as d:
            out, heavy, env = make_run(d, n=1, sets=2, sweep="MC_YAW_P=1.0", changes=changes)
            log = (out / "changes.log").read_text().rstrip("\n") + " · REFUSED fcu_url is not the sim PX4\n"
            (out / "changes.log").write_text(log)
            _, (rows, _) = rows_of(out, heavy, env)
        self.assertEqual(v(rows, "live parameter changes logged"), "FAIL")

    def test_a_stopped_sweep_set_names_why(self):                          # CHG-0020: REFUSED = FAIL, UNVERIFIED = UNVERIFIED
        changes = [(20.0 + 2 * GAP_V + 3.0, "MC_YAW_P", 1.0)]
        for line, verdict in (("PARAM UNVERIFIED: drone_1/MC_YAW_P set 1.4: param pull did not succeed -- sweep stopped", "UNVERIFIED"),
                              ("PARAM REFUSED: drone_1/MC_YAW_P set 1.4: fcu_url is not the sim PX4 -- sweep stopped", "FAIL"),
                              ("PARAM MISMATCH: drone_1/MC_YAW_P set 1.4, read back 1.0 -- sweep stopped", "FAIL")):
            with tempfile.TemporaryDirectory() as d:          # 3 sets asked, 2 flown, set 2 stopped by the helper
                out, heavy, env = make_run(d, n=1, sets=2, sweep="MC_YAW_P=1.0;MC_YAW_P=1.4", changes=changes)
                with open(out / "test_stdout.log", "a") as fh:
                    fh.write("  helper: PARAM MISMATCH: an indented helper line is not fly.sh's verdict\n" + line + "\n")
                _, (rows, _) = rows_of(out, heavy, env)
            self.assertEqual(v(rows, "sweep completed"), verdict, line)
            self.assertIn(line.split(":")[0], m(rows, "sweep completed"))
            self.assertIn("2 of 3", m(rows, "sweep completed"))

    def test_an_unverified_set_is_never_a_completed_sweep(self):          # every set flown, one set not confirmed
        changes = [(20.0 + 2 * GAP_V + 3.0, "MC_YAW_P", 1.0)]
        with tempfile.TemporaryDirectory() as d:
            out, heavy, env = make_run(d, n=1, sets=2, sweep="MC_YAW_P=1.0", changes=changes)
            with open(out / "test_stdout.log", "a") as fh:
                fh.write("PARAM UNVERIFIED: drone_1/MC_YAW_P set 1: no read-back -- sweep stopped\n")
            _, (rows, _) = rows_of(out, heavy, env)
        self.assertEqual(v(rows, "sweep completed"), "UNVERIFIED")

    def test_no_sweep_has_no_change_gate(self):
        with tempfile.TemporaryDirectory() as d:
            out, heavy, env = make_run(d)
            _, (rows, _) = rows_of(out, heavy, env)
        r = next(r for r in rows if r.check.startswith("live parameter changes"))
        self.assertFalse(r.gate); self.assertIn("none", r.measured)

    def test_live_vs_ulog_overshoot_mismatch_makes_overshoot_unverified(self):
        with tempfile.TemporaryDirectory() as d:
            out, heavy, env = make_run(d, live_gain=2.0)
            _, (rows, _) = rows_of(out, heavy, env)
        self.assertEqual(v(rows, "live vs ulog overshoot"), "UNVERIFIED")
        self.assertEqual(v(rows, "heading overshoot"), "UNVERIFIED")
        self.assertEqual(R.overall_verdict(rows), "INCOMPLETE")

    def test_booted_gains_gate_reads_the_airframe_file(self):
        with tempfile.TemporaryDirectory() as d:
            out, heavy, env = make_run(d, header={"MC_YAW_P": 9.9})
            _, (rows, _) = rows_of(out, heavy, env)
        self.assertEqual(v(rows, "booted gains"), "FAIL")
        self.assertIn("9.9", m(rows, "booted gains"))

    def test_patch_0007_turn_is_not_gated_and_the_tap_is_info(self):      # reviewer change 4
        with tempfile.TemporaryDirectory() as d:
            out, heavy, env = make_run(d)
            _, (rows, _) = rows_of(out, heavy, env)
        self.assertEqual(v(rows, "xy drift"), "PASS")                       # the 0.75 m tap sits in the turn's window only
        tap = next(r for r in rows if r.check.startswith("patch-0007 tap"))
        self.assertFalse(tap.gate)
        self.assertRegex(tap.measured, r"direction error [0-4]\.\d°")
        turn = next(r for r in rows if r.check.startswith("pulse turn"))
        self.assertFalse(turn.gate); self.assertIn("not gated", turn.measured)

    def test_an_unstamped_ulog_pulse_makes_the_match_unverified(self):
        pulses, groups, extra, moves = flight(n=3)
        stamped = list(pulses)
        with tempfile.TemporaryDirectory() as d:
            out, heavy, env = make_run(d, pulses=pulses, groups=groups, extra=extra, moves=moves)
            S.stdout_log(out / "test_stdout.log", stamped[1:], scale=SCALE, groups=[0] * 5 + [0], extra=extra)   # fly.sh's first stamp lost
            _, (rows, _) = rows_of(out, heavy, env)
        self.assertEqual(v(rows, "set-0 pulses"), "UNVERIFIED")
        for g in GATES:
            self.assertEqual(v(rows, g), "UNVERIFIED", g)

    def test_odometry_without_yaw_rate_gets_an_info_row(self):             # reviewer change 3 (U5)
        with tempfile.TemporaryDirectory() as d:
            out, heavy, env = make_run(d, yaw_rate=False)
            _, (rows, _) = rows_of(out, heavy, env)
        r = next(r for r in rows if r.check.startswith("odometry yaw rate"))
        self.assertFalse(r.gate); self.assertIn("odometry carries no yaw rate, U5", r.measured)
        self.assertEqual(R.overall_verdict(rows), "PASS")
        with tempfile.TemporaryDirectory() as d:
            out, heavy, env = make_run(d)
            _, (rows, _) = rows_of(out, heavy, env)
        self.assertNotIn("carries no yaw rate", m(rows, "odometry yaw rate"))

    def test_the_pulse_marker_source_is_named(self):                       # reviewer change 5 (U3)
        with tempfile.TemporaryDirectory() as d:
            out, heavy, env = make_run(d)
            _, (rows, _) = rows_of(out, heavy, env)
        self.assertIn("vehicle_attitude_setpoint.yaw_sp_move_rate", m(rows, "pulse marker"))
        with tempfile.TemporaryDirectory() as d:
            out, heavy, env = make_run(d, ff_zero=True)
            _, (rows, ctx) = rows_of(out, heavy, env)
        self.assertIn("trajectory_setpoint.yawspeed", m(rows, "pulse marker"))
        self.assertTrue(any("trajectory_setpoint.yawspeed" in c for c in ctx["caveats"]))

    def test_caption_and_ledger_sentence(self):
        with tempfile.TemporaryDirectory() as d:
            out, heavy, env = make_run(d)
            G, (rows, ctx) = rows_of(out, heavy, env)
        cap = G.figure_caption(ctx)
        self.assertLessEqual(len(cap), 380); self.assertIn("wall-clock", cap); self.assertIn("vehicle time", cap)
        s = G.ledger_sentence(rows, ctx, "PASS")
        self.assertIn("PASS", s); self.assertIn("vehicle time", s); self.assertIn("landed + DISARMED yes", s)
        self.assertIn("[Figure 1](#fig-1)", ctx["reading"])
        self.assertTrue(all(len(r.measured) <= 120 for r in rows if r.check.startswith("pulse ")))

    def test_report_renders_a_record(self):
        with tempfile.TemporaryDirectory() as d:
            out, heavy, env = make_run(d)
            rc = R.main([str(YAW), str(out), "--heavy", str(heavy), "--no-verdict-log", "--ledger", "24", "--issue", "NEAR-789"])
            text = (out.parent / "run_record.md").read_text()
        self.assertEqual(rc, 0)
        self.assertIn("| pulse 0/1", text); self.assertIn("NEAR-789", text)
        self.assertIn("| Sim | Isaac Sim, 1 Starling 2 Max", text)          # the drone count of THIS run (run_meta num_robots)


class FlyScript(unittest.TestCase):
    def test_fly_publishes_zeros_on_exit(self):                            # static: no ROS on the host
        src = (YAW / "fly.sh").read_text()
        for n in ("/svg/drone_1/teleop_command", "TwistStamped", "finally", "SIGTERM", "px4_param_set.sh",
                  "yaw_step-sweep-set-", "changes.log", "pulse", "release", "landed:", "ros2 param get",
                  "PARAM MISMATCH", "turn onset", "tap onset", "SignalHandlerOptions.NO", 'frame_id = "map"'):
            self.assertIn(n, src, n)
        for n in ("ParamSetV2", "ros2 param set", "param/pull", "force_pull"):     # every set goes through the helper (CHG-0020)
            self.assertNotIn(n, src, n)
        self.assertNotIn('rm -f "$HERE/changes.log"', src)    # sim.sh empties the run's log after `up` (CHG-0017)
        self.assertEqual(subprocess.run(["bash", "-n", str(YAW / "fly.sh")]).returncode, 0)

    def test_the_embedded_pulse_program_compiles(self):
        src = (YAW / "fly.sh").read_text()
        py = src.split("<<'PY'\n", 1)[1].split("\nPY\n", 1)[0]
        compile(py, "fly.sh<<PY", "exec")
        cut = py.split("def helper_set", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("except BaseException:", cut); self.assertIn("raise", cut)      # an interrupted set is still logged

    def test_the_pulse_program_dies_with_the_flight_script(self):
        # sim.sh's stop_fly runs `pkill -f "fly\\.sh"`: the embedded python must carry "fly.sh" in its argv or it would
        # keep commanding yaw after an abort landing.
        src = (YAW / "fly.sh").read_text()
        self.assertRegex(src, r'python3 - [^\n]*fly\.sh')

    def test_every_change_goes_through_changes_log(self):                  # owner rule 2026-11-02
        src = (YAW / "fly.sh").read_text()
        self.assertIn("import changes_log", src); self.assertIn("changes_log.append_change", src)
        self.assertIn("changes.log", src)
        self.assertNotIn(" → ", src)                                       # the format lives in tools/lib/changes_log.py only

    def test_fly_args_defaults_match_test_env(self):
        env = R.parse_env(YAW / "test.env")
        self.assertEqual(env["NUM_ROBOTS"], "1"); self.assertEqual(env["USE_STUDIO"], "false")
        self.assertEqual(env["FLY_ARGS"], "3 1.0 1.0"); self.assertEqual(env["CONFIG"], "teleop_single.yaml")
        self.assertTrue(env["DURATION_S"].isdigit(), env["DURATION_S"])   # report.py parses it: no inline comment
        self.assertTrue(env["FLY_TIMEOUT_S"].isdigit())
        self.assertIn("iron rule 9", (YAW / "test.env").read_text())


# ------------------------------------------------------------------ fly.sh's pulse program, run with stubs (no ROS, no docker)
RUNNER = r"""
import os, sys, time, types
time.sleep = lambda s: None
os.environ["FAKE_PYPID"] = str(os.getpid())
import threading
_EV = os.environ.get("FAKE_EVENTS")
def ev(name):
    if _EV:
        open(_EV, "a").write(name + "\n")
class _Clock:
    def now(self): return self
    def to_msg(self): return None
class _Node:
    def create_publisher(self, *a): return types.SimpleNamespace(publish=lambda m: None)
    def create_timer(self, *a): return None
    def get_clock(self): return _Clock()
    def destroy_node(self): ev("node.destroy")
class TwistStamped:
    def __init__(self):
        self.header = types.SimpleNamespace(stamp=None, frame_id="")
        self.twist = types.SimpleNamespace(angular=types.SimpleNamespace(z=0.0), linear=types.SimpleNamespace(x=0.0))
rclpy = types.ModuleType("rclpy"); rclpy.init = lambda **k: None; rclpy.create_node = lambda n: _Node()
def _spin_forever(n):          # a real spin never returns by itself: only executor.shutdown() ends it
    threading.Event().wait()
rclpy.spin = _spin_forever
def _shutdown():
    ev("rclpy.shutdown")
    if os.environ.get("FAKE_ABORT_AT_SHUTDOWN"): os.abort()      # the C++ runtime's `terminate called without an active exception`
rclpy.shutdown = _shutdown
def _try_shutdown():
    ev("rclpy.try_shutdown")
    if os.environ.get("FAKE_ABORT_AT_SHUTDOWN"): os.abort()
rclpy.try_shutdown = _try_shutdown
class SingleThreadedExecutor:
    def __init__(self): self._stop = threading.Event()
    def add_node(self, n): ev("executor.add_node")
    def spin(self):
        ev("spin.start"); self._stop.wait(); ev("spin.exit")
    def shutdown(self, *a, **k):
        ev("executor.shutdown"); self._stop.set()
exe = types.ModuleType("rclpy.executors"); exe.SingleThreadedExecutor = SingleThreadedExecutor
sig = types.ModuleType("rclpy.signals"); sig.SignalHandlerOptions = types.SimpleNamespace(NO=0)
gmm = types.ModuleType("geometry_msgs.msg"); gmm.TwistStamped = TwistStamped
sys.modules.update({"rclpy": rclpy, "rclpy.signals": sig, "rclpy.executors": exe, "geometry_msgs": types.ModuleType("geometry_msgs"), "geometry_msgs.msg": gmm})
code = open(sys.argv[1]).read()
sys.argv = ["-", "yaw_step/fly.sh"] + sys.argv[2:]
exec(compile(code, "fly.sh<<PY", "exec"), {"__name__": "__main__"})
"""
# fake ros2: the MAVROS param node as files in $FAKE_STATE (booted gains), PX4 applies a set at once
FAKE_ROS2 = r"""#!/bin/bash
st=$FAKE_STATE; a="$*"
echo "${ROS_AUTOMATIC_DISCOVERY_RANGE:-unset} ${ROS_STATIC_PEERS:-} $a" >> "$st/calls"
case "$a" in
  *param/pull*) [ -n "${FAKE_PULL_FAIL:-}" ] && { echo "success=False"; exit 0; }; echo "success=True" ;;
  "param get "*mavros_node*fcu_url*) echo "String value is: ${FAKE_FCU:-udp://:14541@172.31.0.200:14581}" ;;
  "param get "*) p=$4; echo "Double value is: $(cat "$st/$p")" ;;
  *param/set*ParamSetV2*)
    [[ "$a" =~ param_id:\ ([A-Z_]+),.*double_value:\ ([-0-9.eE+]+) ]] || exit 1
    p=${BASH_REMATCH[1]}; v=${BASH_REMATCH[2]}
    [ -e "$st/stuck_$p" ] && { echo "success=True"; exit 0; }           # PX4 ignores further sets of this one
    [ "${FAKE_REJECT:-}" = "$p" ] && { echo "success=True"; exit 0; }   # reports success, value unchanged
    echo "$v" > "$st/$p"
    [ "${FAKE_STUCK:-}" = "$p" ] && touch "$st/stuck_$p"
    [ "${FAKE_KILL_ON_SET:-}" = "$p=$v" ] && { kill -TERM "$FAKE_PYPID"; sleep 1; }   # Ctrl-C while the call is under way
    echo "response: success=True" ;;
  "param set "*) echo "Setting parameter failed" ;;
esac
"""
BOOTED = {"MC_YAW_P": "2.8", "MC_YAWRATE_P": "0.07", "MC_YAWRATE_I": "0.5", "MC_YAWRATE_D": "0.0", "MC_YAWRATE_K": "1.0"}


def run_program(tmp, sweep, **fake):
    tmp = pathlib.Path(tmp)
    (tmp / "bin").mkdir(); (tmp / "state").mkdir()
    (tmp / "bin" / "ros2").write_text(FAKE_ROS2); (tmp / "bin" / "ros2").chmod(0o755)
    for k, val in BOOTED.items():
        (tmp / "state" / k).write_text(val + "\n")
    src = (YAW / "fly.sh").read_text()
    (tmp / "prog.py").write_text(src.split("<<'PY'\n", 1)[1].split("\nPY\n", 1)[0])
    (tmp / "runner.py").write_text(RUNNER)
    env = dict(os.environ, PATH=str(tmp / "bin") + ":" + os.environ["PATH"], FAKE_STATE=str(tmp / "state"),
               CHANGES_LOG=str(tmp / "changes.log"), PYTHONPATH=str(TOOLS / "lib"),
               PARAM_HELPER=str(TOOLS / "lib" / "px4_param_set.sh"), ROS_STATIC_PEERS="10.40.2.11", **fake)
    r = subprocess.run([sys.executable, str(tmp / "runner.py"), str(tmp / "prog.py"), "0", "1", "1.0", "0", sweep],
                       capture_output=True, text=True, timeout=60, env=env)
    log = (tmp / "changes.log").read_text().splitlines() if (tmp / "changes.log").exists() else []
    state = {k: float((tmp / "state" / k).read_text()) for k in BOOTED}
    calls = (tmp / "state" / "calls").read_text().splitlines() if (tmp / "state" / "calls").exists() else []
    run_program.calls = calls          # every ros2 call: "<discovery range> <static peers> <argv>"
    return r, [C.parse_change(l) for l in log], state


FAKE_PY3 = """#!/bin/bash
# stands in for `python3 - yaw_step/fly.sh GAP N RATE PULSE SWEEP <<PY`: program on stdin, stubbed rclpy
cat > "$FAKE_DIR/prog.py"; shift 2
exec "$REAL_PY" "$FAKE_DIR/runner.py" "$FAKE_DIR/prog.py" "$@"
"""
FAKE_ROS2_SVC = "#!/bin/bash\ncase \"$*\" in *service*call*) echo \"success=True, message='ok'\";; esac\nexit 0\n"


def run_flysh(tmp, **fake):
    """The whole fly.sh (bash + embedded program) with a fake ros2, python3 and sleep: no ROS, no docker."""
    tmp = pathlib.Path(tmp); (tmp / "bin").mkdir(parents=True); (tmp / "home/AirStack/robot/ros_ws/install").mkdir(parents=True)
    (tmp / "home/AirStack/robot/ros_ws/install/setup.bash").write_text("")
    for name, body in (("ros2", FAKE_ROS2_SVC), ("python3", FAKE_PY3), ("sleep", "#!/bin/bash\nexit 0\n")):
        (tmp / "bin" / name).write_text(body); (tmp / "bin" / name).chmod(0o755)
    (tmp / "runner.py").write_text(RUNNER)
    for f in ("changes_log.py", "px4_param_set.sh"):
        shutil.copy(TOOLS / "lib" / f, tmp / f)
    shutil.copy(YAW / "fly.sh", tmp / "fly.sh")
    env = dict(os.environ, HOME=str(tmp / "home"), PATH=str(tmp / "bin") + ":" + os.environ["PATH"], FAKE_DIR=str(tmp),
               REAL_PY=sys.executable, **fake)
    return subprocess.run(["bash", str(tmp / "fly.sh"), "0", "1", "1.0", "0"], capture_output=True, text=True, timeout=60, env=env)


class FlyShExit(unittest.TestCase):                                              # CHG-0022
    def test_the_spin_thread_is_stopped_and_joined_before_the_node_and_rclpy_go(self):
        with tempfile.TemporaryDirectory() as d:
            ev = pathlib.Path(d) / "events"
            r = run_flysh(pathlib.Path(d) / "run", FAKE_EVENTS=str(ev))
            events = ev.read_text().split()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(events[-4:], ["executor.shutdown", "spin.exit", "node.destroy", "rclpy.try_shutdown"], events)
        self.assertIn("spin.start", events); self.assertNotIn("rclpy.shutdown", events)

    def test_a_clean_python_exit_adds_no_caveat(self):
        with tempfile.TemporaryDirectory() as d:
            r = run_flysh(d)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("CAVEAT", r.stdout); self.assertIn("landed:", r.stdout)

    def test_an_aborted_python_is_flagged_and_the_landing_still_runs(self):
        with tempfile.TemporaryDirectory() as d:
            r = run_flysh(d, FAKE_ABORT_AT_SHUTDOWN="1")
        self.assertNotEqual(r.returncode, 0, r.stdout)
        cav = [l for l in r.stdout.splitlines() if l.startswith("CAVEAT: ")]
        self.assertEqual(len(cav), 1, r.stdout)
        self.assertIn("pulse program", cav[0]); self.assertIn("134", cav[0]); self.assertIn("signal 6", cav[0])
        self.assertIn("landed:", r.stdout)


class FlyProgram(unittest.TestCase):
    def test_a_sweep_restores_the_booted_gains_before_the_0007_check(self):        # review Important 2
        with tempfile.TemporaryDirectory() as d:
            r, log, state = run_program(d, "MC_YAW_P=2.0;MC_YAW_P=1.4,MC_YAWRATE_D=0.002")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(state, {k: float(x) for k, x in BOOTED.items()})
        rest = [c for c in log if "restore" in c["who"]]
        self.assertEqual(sorted((c["name"], c["new"], c["readback"]) for c in rest), [("MC_YAWRATE_D", 0.0, 0.0), ("MC_YAW_P", 2.8, 2.8)])
        self.assertEqual(next(c for c in rest if c["name"] == "MC_YAW_P")["old"], 1.4)     # old = the sweep value it replaced
        self.assertEqual(len(log), 3 + 2)
        self.assertLess(r.stdout.index("booted gains restored"), r.stdout.index("turn onset"))
        # CHG-0020: every line through px4_param_set.sh: drone_1/, the read-back, the helper's who
        self.assertEqual({c["target"] for c in log}, {"drone_1"})
        self.assertEqual([c["who"].split(" ")[0] for c in log[:3]], ["yaw_step-sweep-set-1", "yaw_step-sweep-set-2", "yaw_step-sweep-set-2"])
        self.assertTrue(all(c["who"].startswith("restore-") for c in rest), rest)
        self.assertTrue(all(c["readback"] == c["new"] and not c["unverified"] for c in log), log)
        self.assertTrue(any(" · drone_1/MC_YAW_P · 2.8 → 2 · yaw_step-sweep-set-1" in l for l in r.stdout.splitlines()),
                        r.stdout)                                                        # the helper's line is echoed
        calls = run_program.calls
        self.assertTrue(calls and all(c.startswith("LOCALHOST  ") for c in calls), calls)  # never the lab subnet
        self.assertTrue(any("fcu_url" in c for c in calls), calls)                          # the sim-PX4 check ran

    def test_an_interrupted_set_is_still_logged_and_restored(self):                 # review Important 1
        with tempfile.TemporaryDirectory() as d:
            r, log, state = run_program(d, "MC_YAW_P=2.0;MC_YAW_P=1.4", FAKE_KILL_ON_SET="MC_YAW_P=1.4")
        self.assertNotEqual(r.returncode, 0)
        cut = [c for c in log if c["new"] == 1.4]
        self.assertEqual(len(cut), 1, log); self.assertIn("interrupted", cut[0]["who"]); self.assertIsNone(cut[0]["readback"])
        self.assertEqual(cut[0]["target"], "drone_1"); self.assertTrue(cut[0]["unverified"]); self.assertEqual(cut[0]["old"], 2.0)
        self.assertEqual(state["MC_YAW_P"], 2.8)                                         # restored on the way out
        self.assertTrue(any("restore" in c["who"] and c["new"] == 2.8 for c in log))
        self.assertNotIn("turn onset", r.stdout)

    def test_a_mismatch_stops_the_sweep_and_still_restores(self):
        with tempfile.TemporaryDirectory() as d:
            r, log, state = run_program(d, "MC_YAW_P=2.0,MC_YAWRATE_D=0.002", FAKE_REJECT="MC_YAWRATE_D")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("PARAM MISMATCH", r.stdout)
        self.assertEqual(state["MC_YAW_P"], 2.8)
        self.assertNotIn("pulse 1/1 onset", r.stdout)
        self.assertTrue(any(c["mismatch"] and c["name"] == "MC_YAWRATE_D" for c in log), log)

    def test_an_interrupted_first_set_restores_the_value_read_before_it(self):     # booted value read before any set
        with tempfile.TemporaryDirectory() as d:
            r, log, state = run_program(d, "MC_YAW_P=2.0", FAKE_KILL_ON_SET="MC_YAW_P=2.0")
        self.assertNotEqual(r.returncode, 0)
        cut = [c for c in log if c["new"] == 2.0]
        self.assertEqual(len(cut), 1, log); self.assertIn("interrupted", cut[0]["who"]); self.assertEqual(cut[0]["old"], 2.8)
        self.assertEqual(state["MC_YAW_P"], 2.8, r.stdout)
        self.assertNotIn("CAVEAT", r.stdout)

    def test_a_restore_cut_short_runs_again_on_exit(self):
        with tempfile.TemporaryDirectory() as d:
            r, log, state = run_program(d, "MC_YAW_P=2.0", FAKE_KILL_ON_SET="MC_YAW_P=2.8")
        self.assertNotEqual(r.returncode, 0)
        rest = [c for c in log if c["who"].startswith("restore-")]
        self.assertEqual(len(rest), 2, log); self.assertIn("interrupted", rest[0]["who"])
        self.assertIn("on-exit", rest[1]["who"]); self.assertEqual(rest[1]["readback"], 2.8)
        self.assertNotIn("turn onset", r.stdout)

    def test_an_unknown_parameter_is_logged_refused_and_stops_the_sweep(self):      # helper exit 3 writes no line itself
        with tempfile.TemporaryDirectory() as d:
            r, log, state = run_program(d, "MC_YAW_FOO=1.0")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertEqual(len(log), 1, log); self.assertTrue(log[0]["refused"]); self.assertIn("exit 3", log[0]["refused"])
        self.assertEqual(log[0]["target"], "drone_1")
        self.assertIn("PARAM REFUSED: drone_1/MC_YAW_FOO", r.stdout); self.assertNotIn("CAVEAT", r.stdout)

    def test_an_unverified_set_stops_the_sweep(self):                                # CHG-0020: helper exit 1 UNVERIFIED
        with tempfile.TemporaryDirectory() as d:
            r, log, state = run_program(d, "MC_YAW_P=2.0;MC_YAW_P=1.4", FAKE_PULL_FAIL="1")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        stops = [l for l in r.stdout.splitlines() if l.startswith("PARAM ")]
        self.assertEqual(len(stops), 1, r.stdout); self.assertTrue(stops[0].startswith("PARAM UNVERIFIED: drone_1/MC_YAW_P"), stops)
        self.assertNotIn("pulse 1/1 onset", r.stdout); self.assertNotIn("turn onset", r.stdout)
        self.assertEqual([c["new"] for c in log if c["who"].startswith("yaw_step-sweep-set-")], [2.0])   # set 2 never sent
        self.assertTrue(log[0]["unverified"])
        self.assertTrue(any(c["who"].startswith("restore-") for c in log), log)                  # the restore is still tried
        self.assertEqual(len([l for l in r.stdout.splitlines() if l.startswith("CAVEAT: ")]), 1, r.stdout)  # and not confirmed

    def test_a_refused_set_stops_the_sweep_and_touches_nothing(self):               # CHG-0020: helper exit 2 REFUSED
        with tempfile.TemporaryDirectory() as d:
            r, log, state = run_program(d, "MC_YAW_P=2.0,MC_YAWRATE_D=0.002", FAKE_FCU="udp://:14540@10.40.2.11:14580")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("PARAM REFUSED: drone_1/MC_YAW_P", r.stdout)
        self.assertEqual(len(log), 1, log); self.assertTrue(log[0]["refused"])    # set stopped at its first parameter; no restore
        self.assertEqual(state, {k: float(x) for k, x in BOOTED.items()})
        self.assertNotIn("pulse 1/1 onset", r.stdout); self.assertNotIn("CAVEAT", r.stdout)
        self.assertFalse([c for c in run_program.calls if "param/set" in c or c.split()[1:3] == ["param", "set"]])

    def test_a_failed_restore_says_which_gains_are_left(self):
        with tempfile.TemporaryDirectory() as d:
            r, log, state = run_program(d, "MC_YAW_P=2.0,MC_YAWRATE_D=0.002", FAKE_STUCK="MC_YAW_P")
        self.assertEqual(state["MC_YAW_P"], 2.0)
        self.assertEqual(state["MC_YAWRATE_D"], 0.0)          # one failed restore does not stop the others (CHG-0020)
        cav = [l for l in r.stdout.splitlines() if l.startswith("CAVEAT: ")]
        self.assertEqual(len(cav), 1, r.stdout); self.assertIn("non-booted gains", cav[0]); self.assertIn("MC_YAW_P=2", cav[0])
        self.assertNotIn("MC_YAWRATE_D", cav[0])

    def test_no_sweep_touches_no_parameter(self):
        with tempfile.TemporaryDirectory() as d:
            r, log, state = run_program(d, "")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr); self.assertEqual(log, [])
        self.assertIn("turn onset", r.stdout); self.assertIn("tap release", r.stdout)


class FlyArgsCheck(unittest.TestCase):
    """fly.sh --check validates the arguments on the host (sim.sh runs it before Isaac starts); no ROS needed."""
    def check(self, *args):
        return subprocess.run(["bash", str(YAW / "fly.sh"), "--check", *args], capture_output=True, text=True, timeout=20)

    def test_good_arguments_pass(self):
        for a in (("20",), ("20", "3", "1.0", "1.0"), ("20", "2", "1.0", "1.0", "MC_YAW_P=2.0;MC_YAW_P=1.4,MC_YAWRATE_D=0.002")):
            r = self.check(*a); self.assertEqual(r.returncode, 0, (a, r.stdout + r.stderr))

    def test_bad_arguments_are_refused(self):
        for a in (("20", "2", "1.0", "1.0", "MC_YAW_P=2.0;", "MC_YAW_P=1.4"),        # a space inside SWEEP -> 6 arguments
                  ("20", "2", "1.0", "1.0", "MC_ROLL_P=2.0"),                         # only MC_YAW* may be swept
                  ("20", "2", "1.0", "1.0", "MC_YAW_P=two"), ("20", "x"), ("20", "0"), ("abc",)):
            r = self.check(*a); self.assertEqual(r.returncode, 2, a); self.assertIn("fly.sh:", r.stdout + r.stderr, a)


class Contract(unittest.TestCase):
    def test_five_files_and_fresh_layout(self):
        self.assertEqual(contract_check.check(YAW), [])

    def test_metrics_series(self):
        YM = _load("yaw_metrics_t2", YAW / "metrics.py")
        self.assertEqual(YM.DRONES, ("drone_1",))
        self.assertEqual([s.name for s in YM.SERIES][:4], ["heading_rel_deg", "heading_deg", "yaw_rate_dps", "xy_drift_m"])
        self.assertFalse(any(s.running_min for s in YM.SERIES))
        self.assertEqual(YM.REFERENCES["ref_band_plus"], 2.0)


if __name__ == "__main__":
    unittest.main()
