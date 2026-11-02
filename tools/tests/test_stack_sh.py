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

    def test_land_writes_armed_post_for_the_record(self):
        r = run_stub('rx(){ case "$*" in *mavros/state*) echo "armed: false";; esac; }; land_all_and_wait 10; cat "$OUT/armed_post.txt"')
        self.assertEqual(r.stdout.split("\n")[:3], ["drone_1 armed: false", "drone_2 armed: false", "drone_3 armed: false"], r.stdout)

    def test_bound_inside_first_pass_writes_unknown_lines(self):
        r = run_stub('rx(){ case "$*" in *mavros/state*) sleep 3; echo "armed: false";; esac; }; land_all_and_wait 4; echo rc=$?; cat "$OUT/armed_post.txt"')
        self.assertIn("rc=1", r.stdout, r.stderr)
        self.assertIn("drone_3 armed: UNKNOWN", r.stdout, r.stdout)
        self.assertNotIn("armed: true", r.stdout)

    def test_later_complete_pass_overwrites_earlier_and_partial_never_does(self):
        body = ('C=$(mktemp); rx(){ case "$*" in *mavros/state*) echo x >> $C; n=$(wc -l < $C); [ $n -le 3 ] && echo "armed: true" || echo "armed: false";; esac; }; '
                'land_all_and_wait 10; echo rc=$?; cat "$OUT/armed_post.txt"')
        r = run_stub(body)
        self.assertIn("rc=0", r.stdout, r.stderr)
        self.assertEqual(r.stdout.count("armed: false"), 3, r.stdout); self.assertNotIn("armed: true", r.stdout)
        r = run_stub('C=$(mktemp); rx(){ case "$*" in *mavros/state*) echo x >> $C; n=$(wc -l < $C); [ $n -le 3 ] && echo "armed: true" || { sleep 3; echo "armed: true"; };; esac; }; land_all_and_wait 4; echo rc=$?; cat "$OUT/armed_post.txt"')
        self.assertIn("rc=1", r.stdout, r.stderr)
        self.assertNotIn("UNKNOWN", r.stdout, r.stdout)

    def test_land_bound_is_real(self):
        r = run_stub('rx(){ case "$*" in *mavros/state*) sleep 3; echo "armed: true";; esac; }; t0=$SECONDS; land_all_and_wait 4; echo rc=$? el=$((SECONDS-t0))')
        self.assertIn("rc=1", r.stdout, r.stderr)
        el = int(r.stdout.split("el=")[1].split()[0])
        self.assertLessEqual(el, 4 + 10 + 1, r.stdout)

    def test_no_mavros_goes_to_down_and_exits_3(self):
        r = run_stub('rx(){ case "$*" in *"topic list"*) printf "/rosout\\n/svg/commander_status\\n";; esac; }; copy_ulogs(){ echo CALLED copy_ulogs; }; down(){ echo CALLED down; }; arm_abort_trap; kill -INT $$; sleep 1; echo NOT_REACHED')
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
        r = run_stub('rx(){ printf "/rosout\\n/svg/commander_status\\n"; }; land_all_and_wait(){ echo CALLED land; }; copy_ulogs(){ :; }; down(){ echo CALLED down; }; arm_abort_trap; kill -INT $$; sleep 1')
        self.assertIn("aborted before flight", r.stdout); self.assertNotIn("CALLED land", r.stdout); self.assertIn("CALLED down", r.stdout)

    def test_commander_phase_polls_status_and_topic_check_bypasses_the_daemon(self):
        src = LIB.read_text()
        c = src[src.index("commander() {"):src.index("params() {")]
        self.assertIn("-ge 30", c); self.assertIn("sleep 2", c); self.assertIn("odom_fresh", c); self.assertIn("status_pre.json", c)
        self.assertNotIn("json1 /svg/commander_status", c)
        n = src[src.index("no_flight_established() {"):src.index("land_all_and_wait() {")]
        self.assertIn("ros2 topic list --no-daemon --spin-time 5", n); self.assertIn("/drone_1/interface/mavros/state", n)

    def test_error_text_or_partial_list_means_flying(self):
        for out in ('echo "The ros2 daemon may be unhealthy: error"', 'printf "/rosout\\n/parameter_events\\n"', 'echo "!! WARNING /svg/commander_status"'):
            r = run_stub('rx(){ %s; }; land_all_and_wait(){ echo CALLED land; return 0; }; copy_ulogs(){ :; }; down(){ :; }; arm_abort_trap; kill -INT $$; sleep 1' % out)
            self.assertIn("CALLED land", r.stdout, out); self.assertNotIn("aborted before flight", r.stdout, out)

    def test_pre_land_hook_runs_before_the_flight_check_and_the_land(self):
        body = ('L=$(mktemp); pre(){ echo PRE >> $L; }; PRE_LAND_HOOK=pre; '
                'rx(){ echo RX >> $L; case "$*" in *"topic list"*) echo "/drone_1/interface/mavros/state";; esac; }; '
                'land_all_and_wait(){ echo LAND >> $L; return 0; }; copy_ulogs(){ :; }; down(){ echo DOWN >> $L; }; '
                'trap "cat \\$L" EXIT; arm_abort_trap; kill -INT $$; sleep 1')
        r = run_stub(body)
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        seq = [l for l in r.stdout.splitlines() if l in ("PRE", "RX", "LAND", "DOWN")]
        self.assertEqual(seq[0], "PRE", seq); self.assertLess(seq.index("PRE"), seq.index("LAND"))
        self.assertEqual(seq.count("PRE"), 1, seq)
        self.assertIn("PRE_LAND_HOOK", LIB.read_text().split("set -o pipefail")[0])        # documented in the header

    def test_landing_timeout_still_writes_the_record_and_leaves_the_stack_up(self):
        body = ('rx(){ case "$*" in *"topic list"*) echo "/drone_1/interface/mavros/state";; esac; }; '
                'land_all_and_wait(){ echo CALLED land; return 1; }; copy_ulogs(){ echo CALLED copy_ulogs; }; down(){ echo CALLED down; }; '
                'rh(){ echo "REPORT_HOOK aborted=$([ -f $OUT/aborted.txt ] && echo yes) caveat=$(cat $OUT/caveats.txt)"; }; REPORT_HOOK=rh; '
                'arm_abort_trap; kill -INT $$; sleep 1')
        r = run_stub(body)
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        o = r.stdout
        self.assertIn("REPORT_HOOK aborted=yes", o)
        self.assertIn("caveat=landing timed out; stack left up; bag left in the container", o)
        self.assertNotIn("CALLED down", o); self.assertNotIn("CALLED copy_ulogs", o)
        self.assertLess(o.index("REPORT_HOOK"), o.index("DRONES STILL ARMED"))

    def test_fail_runs_hooks_in_order_and_exits_with_fail_rc(self):
        r = run_stub('fh(){ echo HOOK_FAIL; }; rh(){ echo HOOK_REPORT; }; down(){ echo CALLED down; }; FAIL_HOOK=fh; REPORT_HOOK=rh; FAIL_RC=4; ALL_MODE=1; STACK_UP=1; PHASE=fly; fail boom; echo NOT_REACHED')
        self.assertEqual(r.returncode, 4, r.stdout + r.stderr)
        o = r.stdout; self.assertLess(o.index("HOOK_FAIL"), o.index("CALLED down")); self.assertLess(o.index("CALLED down"), o.index("HOOK_REPORT"))
        self.assertNotIn("NOT_REACHED", o)
        self.assertEqual(run_stub('PHASE=x; fail boom').returncode, 1)                  # default stays 1 (hover driver)


class OneDrone(unittest.TestCase):
    def test_default_is_three_drones(self):
        r = subprocess.run(["bash", "-c", f"{ENV}; source {LIB}; echo \"$ISAAC_CMD\"; echo \"$IF_CMD\"; echo $DRONE_IDS; echo $SYSIDS"], capture_output=True, text=True)
        self.assertIn("NUM_ROBOTS=3 ", r.stdout); self.assertIn("launch_sim_interfaces.sh 3", r.stdout)
        self.assertIn("1 2 3", r.stdout); self.assertIn("2 3 4", r.stdout)

    def test_num_robots_1_everywhere(self):
        r = subprocess.run(["bash", "-c", f"{ENV} NUM_ROBOTS=1; source {LIB}; echo \"$ISAAC_CMD\"; echo \"$IF_CMD\"; echo \"ids=$DRONE_IDS\"; echo \"sys=$SYSIDS\""], capture_output=True, text=True)
        self.assertIn("NUM_ROBOTS=1 ", r.stdout); self.assertIn("launch_sim_interfaces.sh 1", r.stdout)
        self.assertIn("ids=1\n", r.stdout); self.assertIn("sys=2\n", r.stdout)

    def test_land_wait_polls_only_the_spawned_drones(self):
        pre = ENV + " NUM_ROBOTS=1; source " + str(LIB) + '; OUT=$(mktemp -d); say(){ :; }; note(){ :; }; '
        r = subprocess.run(["bash", "-c", pre + 'rx(){ case "$*" in *mavros/state*) echo "armed: false";; esac; }; land_all_and_wait 10; echo rc=$?; cat "$OUT/armed_post.txt"'], capture_output=True, text=True, timeout=60)
        self.assertIn("rc=0", r.stdout); self.assertEqual(r.stdout.strip().splitlines()[-1], "drone_1 armed: false"); self.assertNotIn("drone_2", r.stdout)

    def test_param_keys_carry_the_yaw_gains(self):
        r = subprocess.run(["bash", "-c", f"{ENV}; source {LIB}; echo \"$PARAM_KEYS\""], capture_output=True, text=True)
        for k in ("MC_YAW_P", "MC_YAWRATE_P", "MC_YAWRATE_I", "MC_YAWRATE_D", "MC_YAWRATE_K"): self.assertIn(k, r.stdout)


def run_n(n, body, timeout=60):
    """Source stack.sh with NUM_ROBOTS=n, throwaway OUT/HEAVY, say() echoed, note() silent; the body stubs what it needs."""
    pre = ENV + f"; NUM_ROBOTS={n}; source " + str(LIB) + '; OUT=$(mktemp -d); HEAVY=$(mktemp -d); say(){ echo "SAY: $*"; }; note(){ :; }; phase_begin(){ :; }; '
    return subprocess.run(["bash", "-c", pre + body], capture_output=True, text=True, timeout=timeout)


class OneDroneStages(unittest.TestCase):
    """Every stage that used to hard-code 3, run with one drone against stubs (no docker). A '3 put back' mutant of any of these fails here."""
    def test_isaac_waits_for_one_ready_and_one_config_print(self):
        r = run_n(1, 'alive(){ return 0; }; wait_for(){ echo "NEED=$NEED"; return 0; }; isaac_evidence(){ echo "unknown_model=0 starling_cfg=1" > "$OUT/isaac_evidence.txt"; }; isaac')
        self.assertIn("NEED=1", r.stdout, r.stdout + r.stderr)
        self.assertNotIn("Starling2MaxConfig printed", r.stdout)

    def test_interfaces_checks_only_the_spawned_drones(self):
        r = run_n(1, 'alive(){ return 0; }; count_log(){ echo 0; }; odom_gates(){ :; }; docker(){ :; }; mavros_connected(){ echo "mc $1"; return 0; }; interfaces')
        self.assertIn("mc 1", r.stdout, r.stdout + r.stderr); self.assertNotIn("mc 2", r.stdout); self.assertNotIn("mc 3", r.stdout)

    def test_odom_gates_reads_only_the_spawned_drones(self):
        r = run_n(1, 'rx(){ echo "$*" >> "$OUT/rx.log"; case "$*" in *pose.pose.position*) echo "x: 1";; esac; }; odom_gates; cat "$OUT/rx.log"')
        self.assertIn("/drone_1/odometry_conversion", r.stdout, r.stdout + r.stderr)
        self.assertNotIn("/drone_2/odometry_conversion", r.stdout); self.assertNotIn("/drone_3/odometry_conversion", r.stdout)
        self.assertIn("interfaces: 1 drones with odometry", r.stdout)

    def test_commander_accepts_one_idle_drone_and_gets_the_count(self):
        st = '{"scenario":"goal","drones":[{"state":"IDLE","odom_fresh":true}]}'
        r = run_n(1, "alive(){ return 0; }; count_log(){ echo 1; }; wait_for(){ return 0; }; docker(){ return 1; }; json1(){ :; }; fail(){ echo \"FAILED: $*\"; return 9; }; rx(){ echo '" + st + "'; }; commander; echo done")
        self.assertNotIn("FAILED", r.stdout, r.stdout + r.stderr); self.assertIn("done", r.stdout)

    def test_commander_refuses_two_drones_when_one_spawned(self):
        st = '{"scenario":"goal","drones":[{"state":"IDLE","odom_fresh":true},{"state":"IDLE","odom_fresh":true}]}'
        r = run_n(1, "alive(){ return 0; }; count_log(){ echo 1; }; wait_for(){ return 0; }; docker(){ return 1; }; json1(){ :; }; sleep(){ :; }; SECONDS=100; fail(){ echo \"FAILED: $*\"; return 9; }; rx(){ echo '" + st + "'; }; commander")
        self.assertIn("with 1 IDLE", r.stdout, r.stdout + r.stderr)

    def test_copy_ulogs_keeps_only_this_stacks_sysids(self):
        dk = ('docker(){ case "$1" in cp) touch "$3";; exec) shift; case "$*" in *"for f in"*) printf "/a.ulg\\n/b.ulg\\n";; '
              '*"python3 -c"*) case "$*" in *"/a.ulg"*) echo 2;; *) echo 3;; esac;; *stat*) echo 100;; esac;; esac; }; ')
        r = run_n(1, dk + 'copy_ulogs; ls "$OUT"; cat "$OUT/ulog_sysid_map.txt"')
        self.assertIn("ulogs_copied.ok", r.stdout, r.stdout + r.stderr)
        self.assertIn("2 /a.ulg", r.stdout); self.assertNotIn("3 /b.ulg", r.stdout)
        self.assertIn("not in 2", r.stdout)                                      # sysid 3 is another stack's drone: warned and skipped

    def test_copy_ulogs_three_drones_still_need_2_3_4(self):
        dk = 'docker(){ case "$1" in cp) touch "$3";; exec) shift; case "$*" in *"for f in"*) printf "/a.ulg\\n";; *"python3 -c"*) echo 2;; *stat*) echo 100;; esac;; esac; }; '
        r = run_n(3, dk + 'copy_ulogs; ls "$OUT"')
        self.assertNotIn("ulogs_copied.ok", r.stdout, r.stdout); self.assertIn("need 2 3 4", r.stdout)

    def test_land_wait_bound_hit_marks_only_the_spawned_drones_unknown(self):
        r = run_n(2, 'rx(){ case "$*" in *mavros/state*) sleep 2; echo "armed: true";; esac; }; land_all_and_wait 1; echo rc=$?; cat "$OUT/armed_post.txt"')
        self.assertIn("rc=1", r.stdout, r.stdout + r.stderr); self.assertIn("drone_2 armed: UNKNOWN", r.stdout); self.assertNotIn("drone_3", r.stdout)

    def test_status_lists_only_the_spawned_drones(self):
        r = run_n(1, 'docker(){ :; }; count_log(){ echo 0; }; alive(){ return 1; }; rx(){ :; }; mavros_connected(){ return 0; }; status')
        self.assertIn("drone_1 connected: yes", r.stdout, r.stdout + r.stderr); self.assertNotIn("drone_2", r.stdout)


class EnvLeak(unittest.TestCase):
    def test_stack_env_ignores_an_exported_num_robots(self):
        sim = TOOLS / "sim.sh"
        text = sim.read_text()
        i = text.index("stack_env() {"); j = text.index("source \"$REPO/tools/lib/stack.sh\"", i)
        self.assertIn("unset NUM_ROBOTS FLY_ARGS", text[i:j])
        k = text.index('source "$SIM_TESTS_DIR/$NAME/test.env"')
        self.assertIn("unset NUM_ROBOTS FLY_ARGS", text[k - 200:k])               # right before test.env, so only test.env can set them


class Snapshots(unittest.TestCase):
    """param_snapshot start|end (CHG-0017): one MAVROS dump per drone + the commander's dump, in $HEAVY; never a fail."""
    def test_one_dump_per_drone_and_the_commander(self):
        r = run_stub('HEAVY=$(mktemp -d); rx(){ case "$*" in *"param dump /drone_"*) printf "/d:\\n  ros__parameters:\\n"; for i in $(seq 1 600); do echo "    P$i: 1"; done;; '
                     '*"param dump /swarm_commander"*) printf "/swarm_commander:\\n  ros__parameters:\\n    cbf_alpha: 2.5\\n";; esac; }; param_snapshot start; echo rc=$?; ls "$HEAVY"')
        for n in ("params_start_drone_1.yaml", "params_start_drone_2.yaml", "params_start_drone_3.yaml", "params_start_swarm_commander.yaml"):
            self.assertIn(n, r.stdout, r.stdout + r.stderr)
        self.assertIn("600 PX4 parameters", r.stdout); self.assertIn("rc=0", r.stdout); self.assertNotIn("WARN", r.stdout)

    def _calls(self, tag):
        r = run_stub('HEAVY=$(mktemp -d); C=$(mktemp); rx(){ echo "$*" >> $C; }; param_snapshot ' + tag + '; echo ===; cat $C')
        return r.stdout.split("===", 1)[0], r.stdout.split("===", 1)[1]

    def test_start_pull_is_cached_and_comes_before_the_dump(self):                 # before takeoff: MAVROS's own pull is fresh
        _, calls = self._calls("start")
        lines = [l for l in calls.splitlines() if "drone_1" in l]
        self.assertIn("param/pull mavros_msgs/srv/ParamPull '{force_pull: false}'", lines[0]); self.assertIn("ros2 param dump /drone_1/interface/mavros/param", lines[1])
        self.assertNotIn("force_pull: true", calls)

    def test_end_pull_is_forced_after_landing(self):                               # U4: the end snapshot must not be MAVROS's cache
        said, calls = self._calls("end")
        lines = [l for l in calls.splitlines() if "drone_1" in l]
        self.assertIn("'{force_pull: true}'", lines[0]); self.assertIn("ros2 param dump /drone_1/interface/mavros/param", lines[1])
        self.assertNotIn("force_pull: false", calls)
        self.assertIn("WARN: snapshot end drone_1: the forced param pull did not report success", said)   # the fake answers nothing

    def test_a_short_or_empty_dump_warns(self):
        r = run_stub('HEAVY=$(mktemp -d); rx(){ case "$*" in *"param dump /drone_"*) printf "/d:\\n  ros__parameters:\\n    P1: 1\\n";; esac; }; param_snapshot end; echo rc=$?')
        self.assertIn("WARN: snapshot end drone_1 has 1 PX4 parameters", r.stdout)
        self.assertIn("WARN: snapshot end swarm_commander is empty", r.stdout); self.assertIn("rc=0", r.stdout)

    def test_param_diff_failure_is_a_caveat_not_a_fail(self):
        r = run_stub('HEAVY=$(mktemp -d); caveat(){ echo "CAVEAT: $*"; }; param_diff; echo rc=$?')
        self.assertIn("CAVEAT: params_diff.txt not written", r.stdout); self.assertIn("rc=0", r.stdout)
