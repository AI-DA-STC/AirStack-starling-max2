# tools/tests/test_sim_sh.py
import os, pathlib, subprocess, tempfile, unittest
SIM = pathlib.Path(__file__).resolve().parents[1] / "sim.sh"

def run(*args, env=None):
    return subprocess.run(["bash", str(SIM), *args], capture_output=True, text=True, timeout=20, env=env)

class SimSh(unittest.TestCase):
    def test_parses(self):
        self.assertEqual(subprocess.run(["bash", "-n", str(SIM)]).returncode, 0)

    def test_no_args_prints_usage_exit_2(self):
        r = run(); self.assertEqual(r.returncode, 2); self.assertIn("usage:", r.stdout)
        for sub in ("setup", "doctor", "up", "down", "status", "tabs", "test", "figures", "check"): self.assertIn(sub, r.stdout)

    def test_unknown_subcommand_exit_2(self):
        self.assertEqual(run("fly").returncode, 2)

    def test_sim_sh_rejects_bad_flags(self):                      # Review Focus 3
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "foo")); os.makedirs(os.path.join(tmp, "_template"))
            env = dict(os.environ, SIM_TESTS_DIR=tmp)
            ok = ["--ledger", "20", "--issue", "NEAR-787", "r1"]
            cases = [(["test", "foo", "--ledger", "x", "--issue", "NEAR-787", "r1"], "--ledger must be an integer"),
                     (["test", "foo", "--ledger", "20", "--issue", "786", "r1"], "--issue must look like"),
                     (["test", "foo", "--ledger", "20", "--issue", "near-786", "r1"], "--issue must look like"),
                     (["test", "foo", "--ledger", "20", "--issue", "NEAR-786x", "r1"], "--issue must look like"),
                     (["test", "foo", "--ledger", "20", "r1"], "--issue must look like"),
                     (["test", "foo", "--ledger", "20", "r1", "--issue"], "--issue needs a value"),
                     (["test", "foo", "--ledger", "--issue", "NEAR-787", "r1"], "--ledger needs a value"),
                     (["test", "foo", "--ledger", "20", "--issue", "NEAR-787", "bad run"], "<run> must match"),
                     (["test", "foo", "--bogus"] + ok, "unknown flag"),
                     (["test", "foo"] + ok + ["extra"], "unexpected argument"),
                     (["test", "_template"] + ok, "no such test"),
                     (["test", "no_such_test"] + ok, "no such test"),
                     (["up", "--bad"], "unknown flag"),
                     (["down", "x"], "takes no arguments"), (["status", "x"], "takes no arguments"),
                     (["tabs", "x"], "takes no arguments")]
            for args, msg in cases:
                r = run(*args, env=env); self.assertEqual(r.returncode, 2, args); self.assertIn("error:", r.stderr, args)
                self.assertIn(msg, r.stderr, args)
                self.assertNotIn("docker", (r.stdout + r.stderr).lower(), args)   # failed before any container call; the usage text never says "docker"
                self.assertNotRegex(r.stdout, r"^\[\d\d:\d\d:\d\d")             # no `say` line: no phase ran
            # everything valid is NOT run here: it would start the real stack (the flow is covered statically below)

    def test_test_flow_wires_the_pieces(self):
        src = SIM.read_text()
        for n in ("source", "lib/stack.sh", "arm_abort_trap", "ABORT_HOOK=metrics_stop", "metrics_node.py", "bag_recompute.py", "metrics_node: ready", "ros2 topic hz /svg/test/",
                  "tail -n0 -f", "fly.sh", "armed_post.txt", "video.txt", "copy_ulogs", "bag_dump_hook", "report.py", "plot_metrics.py", "VERDICT:", "read -r"):
            self.assertIn(n, src, n)
        self.assertNotIn("sed -i", src); self.assertNotIn("AirStack/simulation/isaac-sim/tools", src)
        self.assertLess(src.index("commander"), src.index("arm_abort_trap"))        # trap armed only from the commander phase on
        self.assertLess(src.index('cmd_figures "$NAME" "$RUN"'), src.rindex("render_report"))   # figure exists before the record is rendered

    def test_failure_and_abort_paths_clean_up(self):
        src = SIM.read_text()
        for n in ("FAIL_HOOK=metrics_stop", "FAIL_RC=4", "REPORT_HOOK=finish_report", "pkill -f 'python3 metrics_node.py'", 'pkill -f "fly', "REPORT ERROR", "HEADLINE: "):
            self.assertIn(n, src, n)
        self.assertNotIn("min pairwise distance", src)                                   # the banner headline comes from report.py (ctx headline_row)
        self.assertNotIn('"$OUT/.metrics_stopped"', src); self.assertNotIn('"$OUT/.report_out"', src)
        self.assertLess(src.index("pkill -f 'python3 metrics_node.py' >/dev/null"), src.index("METRICS_STARTED=1"))   # old node killed before a new one starts
        self.assertLess(src.index("OBS file name (Enter to skip)"), src.index("PHASE=metrics_stop"))                # node stops AFTER the second pause
        self.assertIn("tail -n0 -f $S/metrics_node.log", src)

    def test_lock_present_refuses_before_any_phase(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "flight_logs", "sim")); os.makedirs(os.path.join(tmp, "tests", "foo"))
            lock = os.path.join(tmp, "flight_logs", "sim", ".sim_test.lock")
            holder = subprocess.Popen(["sleep", "30"])
            try:
                open(lock, "w").write(str(holder.pid))
                env = dict(os.environ, HOME=tmp, SIM_TESTS_DIR=os.path.join(tmp, "tests"))
                r = run("test", "foo", "--headless", "--ledger", "20", "--issue", "NEAR-787", "r1", env=env)
                self.assertEqual(r.returncode, 2, r.stdout + r.stderr); self.assertIn("another sim.sh test is already running", r.stderr)
                self.assertNotRegex(r.stdout, r"^\[\d\d:\d\d:\d\d"); self.assertEqual(open(lock).read(), str(holder.pid))   # lock untouched, no phase ran
            finally:
                holder.kill(); holder.wait()

    def test_metrics_stop_without_a_started_node_touches_nothing(self):
        src = SIM.read_text()
        fn = src[src.index("metrics_stop() {"):src.index("metrics_collect() {")]
        body = 'docker(){ echo DOCKER "$@"; }; alive(){ return 0; }; stop_tail(){ :; }; nx(){ echo NX "$@"; }; say(){ :; }; ' + fn + "\nunset METRICS_STARTED; HEAVY=/nonexistent; metrics_stop; echo rc=$?"
        r = subprocess.run(["bash", "-c", body], capture_output=True, text=True, timeout=20)
        self.assertIn("rc=0", r.stdout, r.stderr); self.assertNotIn("DOCKER", r.stdout); self.assertNotIn("NX", r.stdout)
        # the scratch dir is only removed when this run copied files in
        self.assertIn('[ "${OWN_SCRATCH:-0}" = 1 ] && docker exec', src)

    def test_figures_needs_two_args(self):
        self.assertEqual(run("figures", "crossing").returncode, 2)
        self.assertEqual(run("figures").returncode, 2)
