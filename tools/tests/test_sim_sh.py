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
        self.assertLess(src.index("OBS video path, repo-relative, e.g. videos/<file>.mkv (Enter to skip)"), src.index("PHASE=metrics_stop"))   # node stops AFTER the second pause
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
        self.assertTrue('[ "${OWN_SCRATCH:-0}" = 1 ] && [ "${STACK_UP:-0}" != 1 ] && docker exec' in src)

    def _fn(self, name, nxt):
        src = SIM.read_text()
        return src[src.index(name + "() {"):src.index(nxt)]

    def test_metrics_stop_on_a_dead_node_writes_node_died_and_a_caveat(self):
        fn = self._fn("metrics_stop", "metrics_collect() {")
        with tempfile.TemporaryDirectory() as tmp:
            body = ('docker(){ case "$*" in *tail*) printf "l1\\nl2\\nl3\\nl4\\nTraceback boom\\n";; esac; }; alive(){ return 1; }; stop_tail(){ :; }; '
                    'nx(){ :; }; say(){ :; }; caveat(){ echo "$*" >> "$OUT/caveats.txt"; }; metrics_collect(){ echo COLLECTED; }; ' + fn +
                    f'\nOUT={tmp}; HEAVY={tmp}; R=r; S=/tmp/s; METRICS_STARTED=1; metrics_stop; echo rc=$?')
            r = subprocess.run(["bash", "-c", body], capture_output=True, text=True, timeout=20)
            self.assertIn("rc=0", r.stdout, r.stderr); self.assertIn("COLLECTED", r.stdout)
            died = pathlib.Path(tmp, "node_died.txt").read_text()
            self.assertRegex(died.splitlines()[0], r"^found_dead=\d{4}-\d\d-\d\dT"); self.assertIn("Traceback boom", died)
            self.assertIn("metrics node was not running at stop", pathlib.Path(tmp, "caveats.txt").read_text())

    def test_metrics_stop_on_a_live_node_writes_no_node_died(self):
        fn = self._fn("metrics_stop", "metrics_collect() {")
        with tempfile.TemporaryDirectory() as tmp:
            body = ('A=$(mktemp); docker(){ :; }; alive(){ [ ! -s $A ] && { echo x > $A; return 0; }; return 1; }; stop_tail(){ :; }; '
                    'nx(){ :; }; say(){ :; }; caveat(){ echo "$*" >> "$OUT/caveats.txt"; }; metrics_collect(){ echo COLLECTED; }; ' + fn +
                    f'\nOUT={tmp}; HEAVY={tmp}; R=r; S=/tmp/s; METRICS_STARTED=1; metrics_stop; echo rc=$?')
            r = subprocess.run(["bash", "-c", body], capture_output=True, text=True, timeout=30)
            self.assertIn("COLLECTED", r.stdout, r.stderr)
            self.assertFalse(pathlib.Path(tmp, "node_died.txt").exists()); self.assertFalse(pathlib.Path(tmp, "caveats.txt").exists())

    def test_fly_script_is_stopped_before_the_landing_not_by_metrics_stop(self):
        src = SIM.read_text()
        self.assertTrue("PRE_LAND_HOOK=stop_fly" in src, "sim.sh does not set PRE_LAND_HOOK=stop_fly")
        self.assertIn('pkill -f "fly\\\\.sh"', self._fn("stop_fly", "metrics_stop() {"))
        self.assertNotIn("fly", self._fn("metrics_stop", "metrics_collect() {").split("\n", 1)[1])
        fly = src[src.index("PHASE=fly"):src.index("PHASE=metrics_stop")]
        self.assertLess(fly.index("stop_fly"), fly.index("land_all_and_wait"))       # the overrun path stops fly.sh before landing

    def test_finish_report_keeps_the_scratch_dir_while_the_stack_is_up(self):
        fn = SIM.read_text().split("finish_report() {", 1)[1].split("\n", 1)[0]
        self.assertIn('"${STACK_UP:-0}" != 1', fn)

    def _render(self, report_py):
        fn = self._fn("render_report", "# finish_report")
        with tempfile.TemporaryDirectory() as tmp:
            lib = pathlib.Path(tmp, "tools", "lib"); lib.mkdir(parents=True)
            (lib / "report.py").write_text(report_py)
            body = ('say(){ echo "SAY: $*"; }; note(){ :; }; ' + fn +
                    f'\nREPO={tmp}; OUT={tmp}; HEAVY={tmp}; SIM_TESTS_DIR={tmp}; NAME=n; LEDGER=1; ISSUE=NEAR-1; render_report; echo REPORT_RC=$REPORT_RC')
            return subprocess.run(["bash", "-c", body], capture_output=True, text=True, timeout=20)

    def test_banner_skips_a_stderr_warning_printed_first(self):
        r = self._render("import sys\nprint('warning: figure caption is 420 chars (room 388); trimmed', file=sys.stderr, flush=True)\n"
                         "print('PASS: /x/r_record.md'); print('HEADLINE: 1.25 m (margin +0.15 m)')\n")
        self.assertIn("VERDICT: PASS — 1.25 m (margin +0.15 m)", r.stdout, r.stdout + r.stderr)
        self.assertIn("REPORT_RC=0", r.stdout)

    def test_banner_without_a_verdict_line_is_report_error(self):
        r = self._render("import sys\nprint('Traceback: boom', file=sys.stderr); sys.exit(1)\n")
        self.assertIn("REPORT ERROR", r.stdout); self.assertIn("REPORT_RC=4", r.stdout)

    def test_used_run_name_refuses_before_lock_and_docker(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "tests", "foo")); os.makedirs(os.path.join(tmp, "bin"))
            fake = os.path.join(tmp, "bin", "docker")
            open(fake, "w").write("#!/bin/sh\ntouch %s/docker_called\n" % tmp); os.chmod(fake, 0o755)
            env = dict(os.environ, HOME=tmp, SIM_TESTS_DIR=os.path.join(tmp, "tests"), PATH=os.path.join(tmp, "bin") + ":" + os.environ["PATH"])
            args = ("test", "foo", "--headless", "--ledger", "20", "--issue", "NEAR-787")
            self.assertTrue((SIM.parents[1] / "docs" / "record" / "sim_crossing_dry1_record.md").exists())
            r = run(*args, "sim_crossing_dry1", env=env)                                       # a record of that name exists
            self.assertEqual(r.returncode, 2, r.stdout + r.stderr); self.assertIn("run name already used — choose a new one", r.stderr)
            os.makedirs(os.path.join(tmp, "flight_logs", "sim", "r_new_x")); open(os.path.join(tmp, "flight_logs", "sim", "r_new_x", "a.ulg"), "w").write("x")
            r = run(*args, "r_new_x", env=env)                                                 # the heavy folder already holds files
            self.assertEqual(r.returncode, 2, r.stdout + r.stderr); self.assertIn("run name already used", r.stderr)
            self.assertFalse(os.path.exists(os.path.join(tmp, "docker_called")))
            self.assertFalse(os.path.exists(os.path.join(tmp, "flight_logs", "sim", ".sim_test.lock")))
            self.assertNotRegex(r.stdout, r"^\[\d\d:\d\d:\d\d")

    def test_figures_needs_two_args(self):
        self.assertEqual(run("figures", "crossing").returncode, 2)
        self.assertEqual(run("figures").returncode, 2)

    def test_check_passes_on_the_repo(self):
        r = subprocess.run(["bash", str(SIM), "check"], capture_output=True, text=True, timeout=120); self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_precommit_calls_check(self):
        self.assertIn("sim.sh\" check", (SIM.parent / "git-hooks" / "pre-commit").read_text())


class LivePlotWindow(unittest.TestCase):
    """The live plot window (design 2026-10-30): opened before pause 1 in window mode, closed by metrics_stop."""

    def _fn(self, name, nxt):
        src = SIM.read_text()
        return src[src.index(name + "() {"):src.index(nxt)]

    def _start(self, headless, display):
        fn = self._fn("start_live_plot", "stop_live_plot() {")
        with tempfile.TemporaryDirectory() as tmp:
            body = (f'python3(){{ echo "PY $*" > {tmp}/py; sleep 5; }}; say(){{ echo "SAY $*"; }}; ' + fn +
                    f'\nREPO=/repo; TD=/repo/tools/sim_tests/crossing; R=robot; S=/tmp/svg_test; OUT={tmp}; NAME=crossing; RUN=r9; '
                    f'HEADLESS={headless}; DISPLAY="{display}"; start_live_plot; echo "PID=$LIVE_PID"; sleep 0.5; '
                    f'[ -n "$LIVE_PID" ] && kill $LIVE_PID 2>/dev/null; cat {tmp}/py 2>/dev/null; true')
            return subprocess.run(["bash", "-c", body], capture_output=True, text=True, timeout=20).stdout

    def test_opens_in_window_mode_with_a_display(self):
        out = self._start("false", ":1")
        self.assertRegex(out, r"PID=\d+")
        self.assertIn("PY /repo/tools/live/live_plot.py --plots /repo/tools/sim_tests/crossing/plots.json --docker robot --csv /tmp/svg_test/metrics.csv", out)

    def test_headless_run_opens_no_window(self):
        out = self._start("true", ":1")
        self.assertIn("PID=\n", out + "\n"); self.assertNotIn("PY ", out)

    def test_no_display_opens_no_window_and_says_so(self):
        out = self._start("false", "")
        self.assertNotIn("PY ", out); self.assertIn("no DISPLAY", out)

    def test_stop_kills_only_its_own_window_and_the_container_tail(self):
        fn = self._fn("stop_live_plot", "# stop_fly")
        body = ('D=$(mktemp); docker(){ echo "DOCKER $*" >> $D; }; ' + fn +
                '\nsleep 30 & MINE=$!; sleep 30 & OTHER=$!; LIVE_PID=$MINE; R=robot; S=/tmp/svg_test; stop_live_plot; sleep 0.3; '
                'kill -0 $MINE 2>/dev/null && echo MINE_ALIVE; kill -0 $OTHER 2>/dev/null && echo OTHER_ALIVE; echo "LIVE=[$LIVE_PID]"; '
                'stop_live_plot; echo again=$?; kill $OTHER; cat $D; rm -f $D')
        out = subprocess.run(["bash", "-c", body], capture_output=True, text=True, timeout=20).stdout
        self.assertNotIn("MINE_ALIVE", out); self.assertIn("OTHER_ALIVE", out); self.assertIn("LIVE=[]", out)
        self.assertIn("DOCKER exec robot pkill -f", out); self.assertIn("/tmp/svg_test/metrics[.]csv", out)
        self.assertIn("again=0", out)

    def test_metrics_stop_closes_the_window_on_every_path(self):
        fn = self._fn("metrics_stop", "metrics_collect() {")
        self.assertLess(fn.index("stop_live_plot"), fn.index("METRICS_STARTED"))   # before any early return

    def test_window_opens_after_the_liveness_check_and_before_pause_1(self):
        src = SIM.read_text()
        a = src.index("metrics node is not publishing"); b = src.index("start_live_plot\n", a); c = src.index("Start OBS now")
        self.assertLess(a, b); self.assertLess(b, c)


class OptionalFoxgloveLayout(unittest.TestCase):
    """setup leaves the layout as an optional import file; it never claims Studio has it (Studio clears its local store)."""

    def _run(self, dry, present):
        src = SIM.read_text()
        fn = src[src.index("install_layout() {"):src.index("N_OK=0;")]
        body = ('D=$(mktemp); docker(){ echo "DOCKER $*" >> $D; case "$*" in *" test -f "*) return ' + ("0" if present else "1") + ';; esac; return 0; }; '
                'ok(){ echo "OK $*"; }; warn(){ echo "WARN $*"; }; bad(){ echo "BAD $*"; }; ' + fn +
                f'\nREPO=/repo; SIM_TESTS_DIR=/repo/tools/sim_tests; DRY={dry}; install_layout crossing; cat $D; rm -f $D')
        return subprocess.run(["bash", "-c", body], capture_output=True, text=True, timeout=20).stdout

    def test_setup_copies_the_plain_layout_as_an_import_file(self):
        out = self._run(0, False)
        self.assertIn("DOCKER cp /repo/tools/sim_tests/crossing/layout.json airstack-robot-desktop-1:/root/svg_test_crossing_layout.json", out)
        self.assertIn("optional", out); self.assertNotIn("studio-datastores", out); self.assertNotIn("installed in Studio", out)

    def test_doctor_reports_the_import_file_without_changing_anything(self):
        out = self._run(1, True)
        self.assertNotIn("DOCKER cp", out); self.assertIn("OK", out); self.assertIn("/root/svg_test_crossing_layout.json", out)
        self.assertIn("WARN", self._run(1, False))

    def test_exit_trap_also_closes_the_window(self):
        src = SIM.read_text()
        self.assertIn("trap 'stop_live_plot; rm -f \"$SIM_LOCK\"' EXIT", src)

    def test_pause_2_reminds_to_click_back_into_the_terminal(self):
        src = SIM.read_text()
        seg = src[src.index("Landed. Plots still live"):src.index("PHASE=metrics_stop")]
        self.assertIn("click back into this terminal", seg)
