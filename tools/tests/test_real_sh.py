# tools/tests/test_real_sh.py — tools/real.sh, the real-drone gamepad front door (shim + tools/teleop/real_teleop.sh).
# Every call runs with a fake `docker` (it logs its arguments); a guard docker first on PATH refuses and leaves a marker,
# as in tools/tests/test_sim_sh.py, so no test can reach the real containers.
import os, pathlib, py_compile, subprocess, sys, tempfile, unittest
TOOLS = pathlib.Path(__file__).resolve().parents[1]
REAL = TOOLS / "real.sh"
FRONT = TOOLS / "teleop" / "real_teleop.sh"
PAD_CHECK = TOOLS / "teleop" / "pad_check.py"
R = "airstack-robot-desktop-1"

_GUARD = tempfile.mkdtemp(prefix="realsh_guard_")
_GUARD_BIN = os.path.join(_GUARD, "bin"); os.makedirs(_GUARD_BIN, exist_ok=True)
with open(os.path.join(_GUARD_BIN, "docker"), "w") as _fh:
    _fh.write("#!/bin/sh\necho \"$@\" >> %s/docker_called\necho 'test guard: real docker blocked' >&2\nexit 97\n" % _GUARD)
os.chmod(os.path.join(_GUARD_BIN, "docker"), 0o755)
GUARD_MARK = os.path.join(_GUARD, "docker_called")

# The fake docker: logs every call; FAKE_PS = the running container names; FAKE_ISAAC=1 = Isaac runs in isaac-sim;
# FAKE_EXEC_RC = exit code of the pad check's `docker exec … bash -ic` (default 0).
FAKE = r'''#!/bin/sh
echo "$@" >> "$FAKE_LOG"
case "$*" in
  "ps --format {{.Names}}") [ -n "${FAKE_PS_FAIL:-}" ] && exit 1; printf "%b" "${FAKE_PS:-}"; exit 0;;
  "exec isaac-sim pgrep"*) [ "${FAKE_ISAAC:-0}" = 1 ] && exit 0; exit 1;;
  exec*bash\ -ic*) echo "FAKE pad check output"; exit "${FAKE_EXEC_RC:-0}";;
esac
exit 0
'''


def fake_env(tmp, **kw):
    os.makedirs(os.path.join(tmp, "bin"), exist_ok=True)
    f = os.path.join(tmp, "bin", "docker"); open(f, "w").write(FAKE); os.chmod(f, 0o755)
    e = dict(os.environ, HOME=tmp, FAKE_LOG=os.path.join(tmp, "log"), FAKE_PS=R + "\\n")
    e["PATH"] = os.path.join(tmp, "bin") + ":" + _GUARD_BIN + ":" + os.environ["PATH"]
    e.update({k: str(v) for k, v in kw.items()})
    return e


def calls(tmp):
    f = os.path.join(tmp, "log"); return open(f).read() if os.path.exists(f) else ""


def run(*args, env=None):
    if env is None:
        env = dict(os.environ, PATH=_GUARD_BIN + ":" + os.environ["PATH"], HOME=os.path.join(_GUARD, "home"))
    return subprocess.run(["bash", str(REAL), *args], capture_output=True, text=True, timeout=30, env=env, stdin=subprocess.DEVNULL)


class Shim(unittest.TestCase):
    def test_both_parse(self):
        for p in (REAL, FRONT):
            self.assertEqual(subprocess.run(["bash", "-n", str(p)]).returncode, 0, p)

    def test_real_sh_is_only_a_shim(self):
        src = REAL.read_text()
        self.assertIn('exec "$(dirname "$0")/teleop/real_teleop.sh" "$@"', src)
        code = [l for l in src.splitlines() if l.strip() and not l.lstrip().startswith("#")]
        self.assertEqual(len(code), 1, code)

    def test_strict_shell_and_no_detached_exec(self):
        src = FRONT.read_text()
        self.assertIn("set -euo pipefail", src)
        self.assertNotIn("exec -d", src); self.assertNotIn("docker exec -d", src)


class Usage(unittest.TestCase):
    def test_no_args_prints_usage_with_literal_examples_exit_2(self):
        r = run()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        out = r.stdout + r.stderr
        for ex in ("tools/real.sh pad", "tools/real.sh pad --static"):
            self.assertIn(ex, out)
        for bad in ("drone_N", "<drone>", "<"):
            self.assertNotIn(bad, out)
        self.assertFalse(os.path.exists(GUARD_MARK))

    def test_bad_arguments_exit_2_before_any_docker_call(self):
        for args in (["fly"], ["pad", "--bogus"], ["pad", "x"], ["pad", "--static", "--static"], ["-h"]):
            with tempfile.TemporaryDirectory() as tmp:
                r = run(*args, env=fake_env(tmp))
                self.assertEqual(r.returncode, 2, (args, r.stdout, r.stderr))
                self.assertIn("usage:", r.stdout + r.stderr, args)
                self.assertEqual(calls(tmp), "", args)


class PadCommand(unittest.TestCase):
    def test_guided_check_refuses_without_a_terminal_before_docker(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = run("pad", env=fake_env(tmp))
            self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
            self.assertIn("terminal", r.stdout + r.stderr); self.assertIn("PAD CHECK: FAIL — do not fly:", r.stdout)
            self.assertEqual(calls(tmp), "")

    def test_container_down_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = run("pad", "--static", env=fake_env(tmp, FAKE_PS=""))
            self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
            self.assertIn("PAD CHECK: FAIL — do not fly: the robot container (%s) is not running" % R, r.stdout)
            self.assertNotIn("cp ", calls(tmp)); self.assertNotIn("bash -ic", calls(tmp))

    def test_docker_not_answering_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = run("pad", "--static", env=fake_env(tmp, FAKE_PS_FAIL=1))
            self.assertEqual(r.returncode, 2, r.stdout + r.stderr); self.assertIn("PAD CHECK: FAIL — do not fly:", r.stdout)

    def test_refuses_while_the_sim_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = run("pad", "--static", env=fake_env(tmp, FAKE_PS="isaac-sim\\n%s\\n" % R, FAKE_ISAAC=1))
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("PAD CHECK: FAIL — do not fly: Isaac Sim running — real teleop refused", r.stdout)
            self.assertNotIn("cp ", calls(tmp)); self.assertNotIn("bash -ic", calls(tmp))

    def test_an_idle_isaac_container_is_not_a_refusal(self):          # `sim.sh down` leaves the containers up
        with tempfile.TemporaryDirectory() as tmp:
            r = run("pad", "--static", env=fake_env(tmp, FAKE_PS="isaac-sim\\n%s\\n" % R, FAKE_ISAAC=0))
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_static_copies_both_files_and_runs_the_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = run("pad", "--static", env=fake_env(tmp))
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            c = calls(tmp); lines = c.splitlines()
            self.assertEqual(lines[0], "ps --format {{.Names}}")                       # the guard is the first call
            self.assertIn("exec %s mkdir -p /tmp/svg_real" % R, c)
            self.assertRegex(c, r"cp \S+/tools/teleop/pad_core\.py %s:/tmp/svg_real/" % R)
            self.assertRegex(c, r"cp \S+/tools/teleop/pad_check\.py %s:/tmp/svg_real/" % R)
            self.assertIn("exec -i %s bash -ic python3 /tmp/svg_real/pad_check.py --pad f310 --static" % R, c)
            self.assertNotIn("exec -d", c)
            self.assertIn("FAKE pad check output", r.stdout)

    def test_guided_check_uses_a_terminal_when_there_is_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = run("pad", env=fake_env(tmp, REAL_TELEOP_NO_TTY_OK=1))              # unit tests only: no -t here
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("bash -ic python3 /tmp/svg_real/pad_check.py --pad f310", calls(tmp))
            self.assertNotIn("--static", calls(tmp))
            self.assertIn("exec -i %s bash -ic" % R, calls(tmp))                     # no TTY in a test: -i only
            self.assertRegex(FRONT.read_text(), r"\[ -t 0 \] && flags\+=\(-t\)")       # a terminal adds -t (Ctrl-C reaches the check)

    def test_check_exit_codes_pass_through(self):
        for rc in (1, 2, 3):
            with tempfile.TemporaryDirectory() as tmp:
                r = run("pad", "--static", env=fake_env(tmp, FAKE_EXEC_RC=rc))
                self.assertEqual(r.returncode, rc, (rc, r.stdout, r.stderr))

    def test_an_unexpected_exit_code_is_cannot_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = run("pad", "--static", env=fake_env(tmp, FAKE_EXEC_RC=126))
            self.assertEqual(r.returncode, 2, r.stdout + r.stderr); self.assertIn("PAD CHECK: FAIL — do not fly:", r.stdout)

    def test_cleanup_stops_a_left_over_check_joy_node(self):
        with tempfile.TemporaryDirectory() as tmp:
            run("pad", "--static", env=fake_env(tmp, FAKE_EXEC_RC=3))
            self.assertIn("exec %s pkill -f __node:=svg_pad_check_joy" % R, calls(tmp).splitlines()[-1])


class PadCheckShell(unittest.TestCase):
    """pad_check.py needs rclpy + the pad (container only): compile, refusals that come before ROS, and source pins."""
    SRC = PAD_CHECK.read_text()

    def test_compiles(self):
        py_compile.compile(str(PAD_CHECK), doraise=True)

    def _run(self, *args, tty_ok=False):
        with tempfile.TemporaryDirectory() as shim:
            open(os.path.join(shim, "rclpy.py"), "w").write("raise ImportError('no ROS in this test')\n")
            env = dict(os.environ, PYTHONPATH=shim)
            return subprocess.run([sys.executable, str(PAD_CHECK), *args], capture_output=True, text=True, timeout=20,
                                  env=env, stdin=subprocess.DEVNULL)

    def test_guided_without_a_terminal_exits_2(self):
        r = self._run("--pad", "f310")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("PAD CHECK: FAIL — do not fly: the stick test needs a terminal", r.stdout)

    def test_ros_missing_exits_2(self):
        r = self._run("--pad", "f310", "--static")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("PAD CHECK: FAIL — do not fly: cannot check — ROS or the xbox_usb profile did not import", r.stdout)

    def test_only_f310(self):
        self.assertEqual(self._run("--pad", "dragonrise").returncode, 2)

    def test_private_joy_node_pinned_by_name(self):
        for n in ('NODE = "svg_pad_check_joy"', 'TOPIC = "/svg_pad_check/joy"', '"__node:=" + NODE', '"joy:=" + TOPIC',
                  '"device_name:=" + spec.sdl_name', "get_controller(spec.profile)", "profile.mapping_parameters()",
                  'drv.get("deadzone"', 'drv.get("autorepeat_rate"'):
            self.assertIn(n, self.SRC, n)
        self.assertNotIn("device_id", self.SRC)

    def test_joy_node_stopped_on_every_exit(self):
        fin = self.SRC[self.SRC.index("    finally:"):]
        self.assertIn("stop_joy(joy)", fin)
        for sig in ("signal.SIGTERM", "signal.SIGHUP"):
            self.assertIn(sig, self.SRC)
        self.assertIn("except KeyboardInterrupt", self.SRC); self.assertIn("return 3", self.SRC)
        self.assertIn("start_new_session=True", self.SRC); self.assertIn("os.killpg", self.SRC)

    def test_timeouts_match_the_spec(self):
        for n in ("DISCOVERY_S = 2.0", "FIRST_MSG_S = 5.0", "STEP_S = 15.0", "COLLECT_S = 0.5", "BACK_TO_REST_S = 10.0"):
            self.assertIn(n, self.SRC)

    def test_every_decision_is_in_pad_core(self):
        for fn in ("judge_usb", "judge_driver", "judge_environment", "judge_opened", "judge_shape", "judge_rest", "steps_for", "judge_step"):
            self.assertIn("P." + fn + "(", self.SRC, fn)


if __name__ == "__main__":
    unittest.main()
