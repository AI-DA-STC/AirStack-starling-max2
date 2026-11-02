# tools/tests/test_changes_log.py
"""The one change-log line format (owner rule 2026-11-02): `time · name · old → new · who · readback v`, and the
container-side PX4 parameter helper tools/lib/px4_param_set.sh that writes through it (sim only)."""
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import changes_log as C  # noqa: E402


class FormatChange(unittest.TestCase):
    def test_line_has_the_five_fields_in_order(self):
        s = C.format_change("2026-11-02T14:03:05+08:00", "MC_YAW_P", 2.8, 2.0, "yaw_step fly.sh sweep set 1", readback=2.0)
        self.assertEqual(s, "2026-11-02T14:03:05+08:00 · MC_YAW_P · 2.8 → 2 · yaw_step fly.sh sweep set 1 · readback 2")

    def test_unix_time_becomes_iso_with_offset(self):
        s = C.format_change(1_800_000_000.0, "MC_YAW_P", 2.8, 2.0, "x")
        self.assertRegex(s.split(" · ")[0], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d[+-]\d\d:\d\d$")

    def test_missing_values_are_explicit(self):
        s = C.format_change("t", "MC_YAW_P", None, 2.0, "x")
        self.assertIn("? → 2", s)
        self.assertTrue(s.endswith("readback n/a"), s)

    def test_one_line_even_with_a_newline_in_who(self):
        self.assertNotIn("\n", C.format_change("t", "P", 1, 2, "a\nb", readback=2))

    def test_parse_round_trips(self):
        s = C.format_change("2026-11-02T14:03:05+08:00", "MC_YAWRATE_D", 0.0, 0.002, "w", readback=0.002)
        d = C.parse_change(s)
        self.assertEqual((d["time"], d["name"], d["old"], d["new"], d["who"], d["readback"]),
                         ("2026-11-02T14:03:05+08:00", "MC_YAWRATE_D", 0.0, 0.002, "w", 0.002))
        self.assertIsNone(C.parse_change("not a change line"))
        self.assertIsNone(C.parse_change(C.format_change("t", "P", None, 2, "w"))["readback"])

    def test_append_writes_one_line_per_change(self):
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d) / "changes.log"
            C.append_change(p, "t1", "MC_YAW_P", 2.8, 2.0, "w", readback=2.0)
            C.append_change(p, "t2", "MC_YAW_P", 2.0, 1.4, "w", readback=1.4)
            lines = p.read_text().splitlines()
        self.assertEqual(len(lines), 2)
        self.assertEqual([C.parse_change(l)["new"] for l in lines], [2.0, 1.4])


class TargetAndMismatch(unittest.TestCase):
    """CODING_STANDARD §3: a live set names its drone (`drone_N/NAME`); a read-back that differs is marked on the line."""
    def test_a_drone_prefixed_name_parses_into_target_and_bare_name(self):
        d = C.parse_change(C.format_change("t", "drone_2/MC_YAW_P", 2.8, 2.0, "w", readback=2.0))
        self.assertEqual((d["target"], d["name"]), ("drone_2", "MC_YAW_P"))
        self.assertIsNone(C.parse_change(C.format_change("t", "MC_YAW_P", 2.8, 2.0, "w"))["target"])

    def test_a_differing_readback_is_marked_and_still_parses(self):
        s = C.format_change("t", "drone_1/MC_YAW_P", 2.8, 2.0, "w", readback=2.8)
        self.assertTrue(s.endswith(" · readback 2.8 · MISMATCH"), s)
        d = C.parse_change(s); self.assertTrue(d["mismatch"]); self.assertEqual(d["readback"], 2.8)
        self.assertFalse(C.parse_change(C.format_change("t", "P", 2.8, 2.0, "w", readback=2.0))["mismatch"])
        self.assertFalse(C.parse_change(C.format_change("t", "P", 2.8, 2.0, "w"))["mismatch"])     # no read-back: not a mismatch

    def test_same_is_float32_tolerant(self):
        self.assertTrue(C.same(0.07, 0.07000000029802322)); self.assertTrue(C.same(300, 300.0)); self.assertFalse(C.same(2.8, 2.0))
        self.assertTrue(C.same("abc", "abc")); self.assertFalse(C.same("abc", "abd")); self.assertFalse(C.same(None, 1.0))

    def test_large_integers_keep_every_digit(self):
        self.assertIn("2147483647 → 1", C.format_change("t", "P", 2147483647, 1, "w"))


class Cli(unittest.TestCase):
    """`python3 changes_log.py append …` — how the shell helper writes a line without its own formatter."""
    def _cli(self, *args):
        return subprocess.run([sys.executable, str(LIB / "changes_log.py"), *args], capture_output=True, text=True, timeout=30)

    def test_append_prints_and_appends_the_line(self):
        with tempfile.TemporaryDirectory() as d:
            log = os.path.join(d, "sub", "changes.log")
            r = self._cli("append", "--log", log, "--time", "T", "--name", "drone_1/MC_YAW_P", "--old", "2.8000000476837158",
                          "--new", "2.0", "--who", "w", "--readback", "2.0")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(r.stdout.strip(), "T · drone_1/MC_YAW_P · 2.8 → 2 · w · readback 2")
            self.assertEqual(open(log).read(), r.stdout)

    def test_a_mismatch_exits_1(self):
        with tempfile.TemporaryDirectory() as d:
            r = self._cli("append", "--log", os.path.join(d, "l"), "--name", "drone_1/P", "--old", "2.8", "--new", "2.0", "--who", "w", "--readback", "2.8")
            self.assertEqual(r.returncode, 1); self.assertIn("MISMATCH", r.stdout)


LIB = pathlib.Path(__file__).resolve().parents[1] / "lib"
HELPER = LIB / "px4_param_set.sh"
# fake ros2: `param get` prints the state file, `param set` stores "<KIND> value is: <value>" unless STUCK, and
# answers SET_REPLY; `service call` answers SVC_REPLY. Every call is appended to $CALLS.
FAKE_ROS2 = ('#!/bin/sh\necho "$*" >> "$CALLS"\ncase "$1 $2" in\n'
             '  "param get") cat "$STATE";;\n'
             '  "param set") [ -n "$STUCK" ] || echo "$KIND value is: $5" > "$STATE"; echo "${SET_REPLY:-Set parameter successful}";;\n'
             '  "service call") echo "${SVC_REPLY:-response: success=True}";;\nesac\n')


class Helper(unittest.TestCase):
    def _run(self, kind, old, val, name="MC_YAW_P", **fake):
        with tempfile.TemporaryDirectory() as d:
            open(os.path.join(d, "ros2"), "w").write(FAKE_ROS2); os.chmod(os.path.join(d, "ros2"), 0o755)
            state, log, calls = os.path.join(d, "state"), os.path.join(d, "changes.log"), os.path.join(d, "calls")
            open(state, "w").write(f"{kind} value is: {old}\n" if kind else "Parameter not set.\n")
            env = dict(os.environ, PATH=d + ":" + os.environ["PATH"], STATE=state, KIND=kind or "", CALLS=calls, **fake)
            r = subprocess.run(["bash", str(HELPER), "1", name, val, "who-1", log], capture_output=True, text=True, timeout=30, env=env)
            return r, (open(log).read() if os.path.exists(log) else ""), (open(calls).read() if os.path.exists(calls) else "")

    def test_sets_reads_back_and_logs_one_line(self):
        r, log, calls = self._run("Double", "2.8", "2.0")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertRegex(log, r"^\S+ · drone_1/MC_YAW_P · 2.8 → 2 · who-1 \(via ros2 param set\) · readback 2\n$")
        self.assertEqual(r.stdout.strip().splitlines()[-1], log.strip())
        self.assertIn("param set /drone_1/interface/mavros/param MC_YAW_P 2.0", calls)
        self.assertIn("service call /drone_1/interface/mavros/param/pull mavros_msgs/srv/ParamPull", calls)

    def test_a_double_gets_a_decimal_point(self):                                  # `ros2 param set … 2` would send an integer
        _, _, calls = self._run("Double", "2.8", "2"); self.assertIn("MC_YAW_P 2.0", calls)

    def test_readback_mismatch_exits_1_and_says_so(self):
        r, log, _ = self._run("Double", "2.8", "2.0", STUCK="1")
        self.assertEqual(r.returncode, 1); self.assertIn("· readback 2.8 · MISMATCH", log); self.assertIn("PARAM MISMATCH", r.stderr)

    def test_falls_back_to_param_set_v2_without_force(self):
        r, log, calls = self._run("Integer", "30", "300", name="LNDMC_ROT_MAX", SET_REPLY="Setting parameter failed", STUCK="1")
        self.assertIn("ParamSetV2", calls); self.assertIn("force_set: false", calls); self.assertIn("type: 2, integer_value: 300", calls)
        self.assertIn("via ParamSetV2", log); self.assertEqual(r.returncode, 1)       # the fake never changes the value: mismatch

    def test_unknown_name_exits_3_and_logs_nothing(self):
        r, log, _ = self._run(None, "", "2.0")
        self.assertEqual(r.returncode, 3); self.assertIn("has no MC_YAW_P", r.stderr); self.assertEqual(log, "")

    def test_integer_parameter_refuses_a_fraction(self):
        r, log, calls = self._run("Integer", "300", "2.5")
        self.assertEqual(r.returncode, 2); self.assertEqual(log, ""); self.assertNotIn("param set", calls)

    def test_bad_arguments_exit_2_before_ros(self):
        for args in (["1", "mc_yaw_p", "2.0"], ["0", "MC_YAW_P", "2.0"], ["1", "MC_YAW_P", "abc"], ["1", "MC_YAW_P", "2.0", "bad who"]):
            argv = (args + ["w"])[:4] + [os.devnull]
            r = subprocess.run(["bash", str(HELPER), *argv], capture_output=True, text=True, timeout=10, env=dict(os.environ, PATH="/nonexistent:/usr/bin:/bin"))
            self.assertEqual(r.returncode, 2, args)

    def test_never_force_sets(self):                                              # ledger #11: force_set aborted mavros_node
        self.assertNotIn("force_set: true", HELPER.read_text())

    def test_no_second_formatter(self):                                           # the format lives in changes_log.py only
        self.assertNotIn(" → ", HELPER.read_text())


# ----------------------------------------------------------------------------------------------- run capture (CHG-0017)
DUMP = "/drone_1/interface/mavros/param:\n  ros__parameters:\n    MC_YAW_P: 2.799999952316284\n    MC_YAWRATE_P: 0.07000000029802322\n    SYS_AUTOSTART: 10090\n"
CMD = ("bash: cannot set terminal process group\n/swarm_commander:\n  ros__parameters:\n    cbf_alpha: 2.5\n    fence_min:\n    - -4.0\n    - -2.0\n"
       "    qos_overrides:\n      /parameter_events:\n        publisher:\n          depth: 1000\n")
AF = "param set-default MC_YAW_P 2.8 # = real\nparam set-default MC_YAWRATE_P 0.07 # = real\n"
WHEN = "2026-11-02T14:03:05+08:00"
TOOLS = LIB.parent


def _has_yaml():
    try:
        import yaml  # noqa: F401
        return True
    except ImportError:
        return False


@unittest.skipUnless(_has_yaml(), "host PyYAML missing")
class Snapshot(unittest.TestCase):
    def test_dump_flattens_nested_keys_and_lists_after_noise(self):
        d = C.read_dump(CMD)
        self.assertEqual(d["cbf_alpha"], "2.5"); self.assertEqual(d["fence_min"], "[-4.0, -2.0]"); self.assertIn("qos_overrides./parameter_events.publisher.depth", d)

    def test_diff_is_float32_tolerant(self):
        a = C.read_dump(DUMP)
        self.assertEqual(C.diff_dumps(a, C.read_dump(DUMP.replace("0.07000000029802322", "0.07"))), [])
        self.assertEqual(C.diff_dumps(a, C.read_dump(DUMP.replace("2.799999952316284", "2.0"))), [("MC_YAW_P", "2.799999952316284", "2.0")])
        self.assertEqual(C.diff_dumps({"A": "1"}, {"B": "1"}), [("A", "1", "(absent)"), ("B", "(absent)", "1")])

    def test_diff_cli_names_a_missing_end(self):
        with tempfile.TemporaryDirectory() as d:
            h = pathlib.Path(d)
            (h / "params_start_drone_1.yaml").write_text(DUMP); (h / "params_end_drone_1.yaml").write_text(DUMP.replace("2.799999952316284", "2.0"))
            (h / "params_start_swarm_commander.yaml").write_text(CMD)
            subprocess.run([sys.executable, str(TOOLS / "lib/changes_log.py"), "diff", d, "-o", str(h / "diff.txt")], check=True)
            t = (h / "diff.txt").read_text()
            self.assertIn("drone_1/MC_YAW_P 2.799999952316284 -> 2.0", t); self.assertIn("# swarm_commander: no end snapshot", t)
            self.assertIn("# drone_1: partial snapshot", t)                      # 3 PX4 parameters < 500: the diff may miss some

    def test_diff_cli_without_any_start_snapshot_fails_and_says_so(self):
        with tempfile.TemporaryDirectory() as d:
            r = subprocess.run([sys.executable, str(TOOLS / "lib/changes_log.py"), "diff", d, "-o", os.path.join(d, "diff.txt")], capture_output=True, text=True)
            self.assertEqual(r.returncode, 1); self.assertIn("no start snapshot", open(os.path.join(d, "diff.txt")).read())


class UlogList(unittest.TestCase):
    def test_parses_rows_and_the_drones_covered(self):
        t = "# ulog drone_1 drone_1_sysid2_a.ulg\n0.950 drone_1 CAL_ACC0_ID 1310988\n35.100 drone_1 MC_YAW_P 2.0\n"
        self.assertEqual(C.ulog_changes(t), [(0.95, "drone_1", "CAL_ACC0_ID", "1310988"), (35.1, "drone_1", "MC_YAW_P", "2.0")])
        self.assertEqual(C.ulog_targets(t), {"drone_1"})

    def test_cli_on_a_non_ulog_fails(self):
        with tempfile.TemporaryDirectory() as d:
            bad = os.path.join(d, "drone_1_sysid2_x.ulg"); open(bad, "w").write("not a ulog")
            r = subprocess.run([sys.executable, str(TOOLS / "lib/changes_log.py"), "ulog", bad, "-o", os.path.join(d, "p.txt")], capture_output=True, text=True)
            self.assertNotEqual(r.returncode, 0)


@unittest.skipUnless(_has_yaml(), "host PyYAML missing")
class Block(unittest.TestCase):
    """The record's "Changes in this run" block: three sources, nothing silently empty, unlogged changes named."""
    LOG = WHEN + " · drone_1/MC_YAW_P · 2.8 → 2 · yaw_step-sweep-set-1 · readback 2\n"
    ULOG_HDR = "# ulog drone_1 drone_1_sysid2_a.ulg\n"

    def _block(self, files, start=None):
        with tempfile.TemporaryDirectory() as d:
            out = pathlib.Path(d, "out"); heavy = pathlib.Path(d, "heavy"); out.mkdir(); heavy.mkdir()
            for k, v in files.items():
                (out / k).write_text(v)
            if start:
                (heavy / "params_start_drone_1.yaml").write_text(start)
            return "\n".join(C.changes_block(out, heavy, airframe_text=AF))

    def test_all_sources_agree(self):
        t = self._block({"changes.log": self.LOG, "px4_param_changes_all.txt": self.ULOG_HDR + "0.950 drone_1 CAL_ACC0_ID 1310988\n35.100 drone_1 MC_YAW_P 2.0\n",
                         "params_diff.txt": "drone_1/MC_YAW_P 2.8 -> 2.0\n"})
        for s in ("## Changes in this run", "yaw_step-sweep-set-1", "35.100 drone_1 MC_YAW_P 2.0", "1 boot-time", "drone_1/MC_YAW_P 2.8 -> 2.0"):
            self.assertIn(s, t)
        self.assertNotIn("CAL_ACC0_ID", t); self.assertIn("Conflicts and unlogged changes:", t); self.assertIn("- none", t)
        self.assertNotIn("UNLOGGED", t); self.assertNotIn("CONFLICT", t)

    def test_a_bare_name_from_the_yaw_sweep_matches_its_drone(self):                # fly.sh logs `MC_YAW_P` without drone_N/
        t = self._block({"changes.log": WHEN + " · MC_YAW_P · 2.8 → 2 · yaw_step fly.sh sweep set 1 · readback 2\n",
                         "px4_param_changes_all.txt": self.ULOG_HDR + "35.100 drone_1 MC_YAW_P 2.0\n", "params_diff.txt": ""})
        self.assertNotIn("UNLOGGED", t); self.assertNotIn("CONFLICT", t)

    def test_conflict_names_the_ulog_as_the_winner(self):
        t = self._block({"changes.log": self.LOG, "px4_param_changes_all.txt": self.ULOG_HDR + "35.100 drone_1 MC_YAW_P 1.5\n"})
        self.assertIn("CONFLICT", t); self.assertIn("the ulog wins", t)

    def test_logged_but_not_in_the_ulog_is_a_conflict_only_for_a_drone_the_ulog_covers(self):
        t = self._block({"changes.log": self.LOG, "px4_param_changes_all.txt": self.ULOG_HDR})
        self.assertIn("did PX4 receive it?", t)
        t = self._block({"changes.log": self.LOG, "px4_param_changes_all.txt": "# ulog drone_2 drone_2_sysid3_a.ulg\n"})
        self.assertNotIn("did PX4 receive it?", t)

    def test_unlogged_snapshot_change_is_flagged(self):
        t = self._block({"changes.log": "", "params_diff.txt": "swarm_commander/cbf_alpha 2.5 -> 4.7\n"})
        self.assertIn("UNLOGGED CHANGE: swarm_commander/cbf_alpha 2.5 → 4.7", t)

    def test_unlogged_ulog_change_is_flagged_even_when_another_value_was_logged(self):
        t = self._block({"changes.log": self.LOG, "px4_param_changes_all.txt": self.ULOG_HDR + "35.100 drone_1 MC_YAW_P 2.0\n50.000 drone_1 MC_YAW_P 0.5\n60.000 drone_1 MPC_XY_VEL_MAX 9\n"})
        self.assertIn("UNLOGGED CHANGE (ulog): drone_1/MC_YAW_P → 0.5 at 50.000 s", t)
        self.assertIn("UNLOGGED CHANGE (ulog): drone_1/MPC_XY_VEL_MAX → 9 at 60.000 s", t)
        self.assertNotIn("→ 2.0 at 35.100", t)

    def test_empty_log_is_none_logged_but_a_missing_one_is_unknown(self):
        self.assertIn("none logged", self._block({"changes.log": ""}))
        self.assertIn("unknown (changes.log", self._block({}))

    def test_missing_sources_say_unknown_with_a_reason_and_never_crash(self):
        t = self._block({})
        self.assertEqual(t.count("unknown ("), 4, t)                               # tools log, ulog list, snapshot diff, start vs airframe
        self.assertNotIn("none logged", t); self.assertNotIn("no differences", t)
        self.assertIn("- none found; not checked against changes.log, the ulog list, the snapshot diff", t)   # never a bare "none"

    def test_a_partial_snapshot_says_unknown_for_that_target(self):
        t = self._block({"changes.log": "", "params_diff.txt": "# drone_2: no end snapshot\n"})
        self.assertIn("unknown (drone_2: no end snapshot)", t); self.assertNotIn("no differences", t)

    def test_no_differences_and_no_ulog_change_after_boot_are_said(self):
        t = self._block({"changes.log": "", "params_diff.txt": "", "px4_param_changes_all.txt": self.ULOG_HDR + "0.950 drone_1 CAL_ACC0_ID 1310988\n"})
        self.assertIn("no differences", t); self.assertIn("none after boot", t)

    def test_px4_bookkeeping_is_not_an_unlogged_change(self):                       # PX4 writes the flight-time counter itself at disarm
        t = self._block({"changes.log": "", "params_diff.txt": "drone_1/LND_FLIGHT_T_LO 0 -> 81000000\n"})
        self.assertNotIn("UNLOGGED", t); self.assertIn("PX4 bookkeeping", t)

    def test_start_vs_airframe(self):
        self.assertIn("MC_YAW_P: airframe 2.8, in force 2.0", self._block({}, start=DUMP.replace("2.799999952316284", "2.0")))
        self.assertIn("all 2 airframe values in force", self._block({}, start=DUMP))


if __name__ == "__main__":
    unittest.main()
