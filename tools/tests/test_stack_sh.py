import pathlib, subprocess, unittest
TOOLS = pathlib.Path(__file__).resolve().parents[1]
LIB = TOOLS / "lib" / "stack.sh"
ENV = "RUN=x OUT=/tmp/o HEAVY=/tmp/h S=/tmp/s SCENARIO=goal BAG_PREFIX=hover_step CONFIG=cbf_sim.yaml HEADLESS=true"

class StackSh(unittest.TestCase):
    def test_parses(self):
        self.assertEqual(subprocess.run(["bash", "-n", str(LIB)]).returncode, 0)

    def test_source_without_vars_returns_2(self):
        r = subprocess.run(["bash", "-c", f"source {LIB}"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 2); self.assertIn("unset", r.stderr)

    def test_source_defines_phases_and_runs_nothing(self):
        r = subprocess.run(["bash", "-c", f"{ENV}; source {LIB}; declare -F | sed 's/declare -f //'"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr); self.assertEqual(r.stderr, "")
        for fn in ("precheck", "up", "watch", "isaac", "interfaces", "ifgates", "odom_gates", "commander", "params", "copy_ulogs",
                   "down", "status", "ulog_header_params", "px4_arm_times_of", "land_all_and_wait", "arm_abort_trap", "abort_trap"):
            self.assertIn(fn, r.stdout.split(), fn)

    def test_studio_arg_only_when_asked(self):
        for use, want in (("false", False), ("true", True)):
            r = subprocess.run(["bash", "-c", f"{ENV} USE_STUDIO={use}; source {LIB}; echo \"$CMD_CMD\""], capture_output=True, text=True)
            self.assertEqual("use_foxglove_studio:=true" in r.stdout, want, r.stdout)
            self.assertIn("scenario:=goal record_bag:=true bag_prefix:=hover_step", r.stdout)
