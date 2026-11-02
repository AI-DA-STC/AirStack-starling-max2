# tools/tests/test_yaw_step_gates.py
"""tools/sim_tests/yaw_step: gates on a synthetic run folder (ulog CSV in vehicle time + live metrics.csv in wall time +
fly.sh's stamp lines), fly.sh static checks, the five-file contract. Sim-only (iron rule 9). No docker, no ROS: fly.sh's
ROS side is checked statically only."""
import importlib.util
import math
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
            C.append_change(out / "changes.log", 1_800_000_000.0 + (t + 100.0) / SCALE, name, 2.8, v, "yaw_step fly.sh sweep", readback=v)
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
        changes = [(20.0 + 2 * GAP_V + 3.0, "MC_YAW_P", 1.0)]               # between set 0 and set 1
        with tempfile.TemporaryDirectory() as d:
            out, heavy, env = make_run(d, n=1, sets=2, sweep="MC_YAW_P=1.0", ring_sets=(1,), changes=changes)
            _, (rows, _) = rows_of(out, heavy, env)
        self.assertEqual(R.overall_verdict(rows), "PASS", [(r.check, r.verdict, r.measured) for r in rows if r.gate and r.verdict != "PASS"])
        s1 = next(r for r in rows if r.check.startswith("set 1"))
        self.assertFalse(s1.gate); self.assertIn("MC_YAW_P 1", s1.measured)
        self.assertEqual(v(rows, "live parameter changes logged"), "PASS")

    def test_a_ulog_change_missing_from_changes_log_fails(self):           # owner rule 2026-11-02
        changes = [(20.0 + 2 * GAP_V + 3.0, "MC_YAW_P", 1.0)]
        with tempfile.TemporaryDirectory() as d:
            out, heavy, env = make_run(d, n=1, sets=2, sweep="MC_YAW_P=1.0", changes=changes, log_changes=False)
            _, (rows, _) = rows_of(out, heavy, env)
        self.assertEqual(v(rows, "live parameter changes logged"), "FAIL")

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
        for n in ("/svg/drone_1/teleop_command", "TwistStamped", "finally", "SIGTERM", "param/set", "param/pull",
                  "force_pull: true", "pulse", "release", "landed:", "ParamSetV2", "ros2 param set", "ros2 param get",
                  "PARAM MISMATCH", "turn onset", "tap onset", "SignalHandlerOptions.NO", 'frame_id = "map"'):
            self.assertIn(n, src, n)
        self.assertEqual(subprocess.run(["bash", "-n", str(YAW / "fly.sh")]).returncode, 0)

    def test_the_embedded_pulse_program_compiles(self):
        src = (YAW / "fly.sh").read_text()
        py = src.split("<<'PY'\n", 1)[1].split("\nPY\n", 1)[0]
        compile(py, "fly.sh<<PY", "exec")
        self.assertIn("finally:", py.split("def apply_set", 1)[1].split("def hold", 1)[0])   # an interrupted set is still logged

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
