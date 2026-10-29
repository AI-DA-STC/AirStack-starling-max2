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


def run_stub(body, timeout=60):
    pre = ENV + "; source " + str(LIB) + '; OUT=$(mktemp -d); say(){ echo "SAY: $*"; }; note(){ :; }; '
    return subprocess.run(["bash", "-c", pre + body], capture_output=True, text=True, timeout=timeout)

class AbortPath(unittest.TestCase):
    def test_land_returns_0_when_all_disarmed(self):
        r = run_stub('rx(){ case "$*" in *mavros/state*) echo "armed: false";; esac; }; land_all_and_wait 10; echo rc=$?')
        self.assertIn("rc=0", r.stdout, r.stderr)

    def test_land_bound_is_real(self):
        r = run_stub('rx(){ case "$*" in *mavros/state*) sleep 3; echo "armed: true";; esac; }; t0=$SECONDS; land_all_and_wait 4; echo rc=$? el=$((SECONDS-t0))')
        self.assertIn("rc=1", r.stdout, r.stderr)
        el = int(r.stdout.split("el=")[1].split()[0])
        self.assertLessEqual(el, 4 + 10 + 1, r.stdout)

    def test_no_mavros_goes_to_down_and_exits_3(self):
        r = run_stub('rx(){ case "$*" in *"topic list"*) echo "/rosout";; esac; }; copy_ulogs(){ echo CALLED copy_ulogs; }; down(){ echo CALLED down; }; arm_abort_trap; kill -INT $$; sleep 1; echo NOT_REACHED')
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        self.assertIn("aborted before flight", r.stdout)
        self.assertIn("CALLED copy_ulogs", r.stdout); self.assertIn("CALLED down", r.stdout)
        self.assertNotIn("DRONES STILL ARMED", r.stdout); self.assertNotIn("NOT_REACHED", r.stdout)

    def test_second_ctrl_c_in_handler_is_ignored(self):
        r = run_stub('rx(){ case "$*" in *mavros/state*) kill -INT $$; echo "armed: false";; esac; }; copy_ulogs(){ :; }; down(){ trap -p INT; echo DOWN_RAN; }; arm_abort_trap; kill -INT $$; sleep 1; echo NOT_REACHED')
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        self.assertIn("DOWN_RAN", r.stdout); self.assertNotIn("NOT_REACHED", r.stdout)
        self.assertEqual(r.stdout.count("ABORT: Ctrl-C"), 1, r.stdout)

    def test_timeout_with_a_publisher_means_flying_and_lands(self):
        r = run_stub('rx(){ case "$*" in *"topic list"*) echo "/drone_1/interface/mavros/state";; *) return 1;; esac; }; land_all_and_wait(){ echo CALLED land; return 1; }; copy_ulogs(){ echo CALLED copy_ulogs; }; down(){ echo CALLED down; }; arm_abort_trap; kill -INT $$; sleep 1')
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        self.assertIn("CALLED land", r.stdout); self.assertNotIn("aborted before flight", r.stdout)
        self.assertIn("DRONES STILL ARMED", r.stdout); self.assertNotIn("CALLED down", r.stdout)

    def test_unreadable_topic_info_also_means_flying(self):
        r = run_stub('rx(){ return 1; }; land_all_and_wait(){ echo CALLED land; return 0; }; copy_ulogs(){ :; }; down(){ echo CALLED down; }; arm_abort_trap; kill -INT $$; sleep 1')
        self.assertIn("CALLED land", r.stdout); self.assertNotIn("aborted before flight", r.stdout)

    def test_no_publisher_means_aborted_before_flight(self):
        r = run_stub('rx(){ printf "/rosout\\n/parameter_events\\n"; }; land_all_and_wait(){ echo CALLED land; }; copy_ulogs(){ :; }; down(){ echo CALLED down; }; arm_abort_trap; kill -INT $$; sleep 1')
        self.assertIn("aborted before flight", r.stdout); self.assertNotIn("CALLED land", r.stdout); self.assertIn("CALLED down", r.stdout)

    def test_commander_phase_polls_status_and_topic_check_bypasses_the_daemon(self):
        src = LIB.read_text()
        c = src[src.index("commander() {"):src.index("params() {")]
        self.assertIn("-ge 30", c); self.assertIn("sleep 2", c); self.assertIn("odom_fresh", c); self.assertIn("status_pre.json", c)
        self.assertNotIn("json1 /svg/commander_status", c)
        n = src[src.index("no_flight_established() {"):src.index("land_all_and_wait() {")]
        self.assertIn("ros2 topic list --no-daemon --spin-time 5", n); self.assertIn("/drone_1/interface/mavros/state", n)
