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

# The fake docker: logs every call; FAKE_PS = the running container names; FAKE_ISAAC=1 = Isaac runs in isaac-sim
# (FAKE_ISAAC_RC = pgrep's exit code, overrides it); FAKE_EXEC_RC = exit code of the pad check's `docker exec … bash -ic`
# (default 0); FAKE_NOISE=1 = the container's bash -ic noise lines first; FAKE_FAIL_MATCH = a glob of the call that
# exits FAKE_FAIL_RC (default 1).
FAKE = r'''#!/bin/bash
echo "$@" >> "$FAKE_LOG"
if [ -n "${FAKE_FAIL_MATCH:-}" ] && [[ "$*" == $FAKE_FAIL_MATCH ]]; then exit "${FAKE_FAIL_RC:-1}"; fi
case "$*" in
  "ps --format {{.Names}}") [ -n "${FAKE_PS_FAIL:-}" ] && exit 1; printf "%b" "${FAKE_PS:-}"; exit 0;;
  "exec isaac-sim pgrep"*) [ -n "${FAKE_ISAAC_RC:-}" ] && exit "$FAKE_ISAAC_RC"; [ "${FAKE_ISAAC:-0}" = 1 ] && exit 0; exit 1;;
  exec*bash\ -ic*)
    if [ "${FAKE_NOISE:-0}" = 1 ]; then
      echo "bash: cannot set terminal process group (-1): Inappropriate ioctl for device"
      echo "bash: no job control in this shell"
      echo "Sourcing /root/AirStack/robot/ros_ws/install/setup.bash"
    fi
    echo "FAKE pad check output"; exit "${FAKE_EXEC_RC:-0}";;
esac
exit 0
'''


def fake_env(tmp, **kw):
    os.makedirs(os.path.join(tmp, "bin"), exist_ok=True)
    f = os.path.join(tmp, "bin", "docker"); pathlib.Path(f).write_text(FAKE); os.chmod(f, 0o755)
    e = dict(os.environ, HOME=tmp, FAKE_LOG=os.path.join(tmp, "log"), FAKE_PS=R + "\\n")
    e["PATH"] = os.path.join(tmp, "bin") + ":" + _GUARD_BIN + ":" + os.environ["PATH"]
    e.update({k: str(v) for k, v in kw.items()})
    return e


def calls(tmp):
    f = os.path.join(tmp, "log"); return pathlib.Path(f).read_text() if os.path.exists(f) else ""


def run(*args, env=None, script=REAL, stdin=subprocess.DEVNULL):
    if env is None:
        env = dict(os.environ, PATH=_GUARD_BIN + ":" + os.environ["PATH"], HOME=os.path.join(_GUARD, "home"))
    return subprocess.run(["bash", str(script), *args], capture_output=True, text=True, timeout=30, env=env, stdin=stdin)


def copy_tree(tmp, source_text):
    """A throwaway repo: tools/real.sh + tools/teleop/* and a teleop_real_ours.yaml with the given text."""
    import shutil
    os.makedirs(os.path.join(tmp, "tools", "teleop"))
    shutil.copy2(REAL, os.path.join(tmp, "tools", "real.sh"))
    for f in ("real_teleop.sh", "real_config.py", "pad_core.py", "pad_check.py"):
        shutil.copy2(TOOLS / "teleop" / f, os.path.join(tmp, "tools", "teleop", f))
    cfg = os.path.join(tmp, "AirStack/robot/ros_ws/src/svg_ground_control/config")
    os.makedirs(cfg); pathlib.Path(os.path.join(cfg, "teleop_real_ours.yaml")).write_text(source_text)
    return pathlib.Path(tmp, "tools", "real.sh")


SOURCE = (TOOLS.parent / "AirStack/robot/ros_ws/src/svg_ground_control/config/teleop_real_ours.yaml").read_text()


class Shim(unittest.TestCase):
    def test_both_parse(self):
        for p in (REAL, FRONT):
            self.assertEqual(subprocess.run(["bash", "-n", str(p)]).returncode, 0, p)

    def test_real_sh_is_only_a_shim(self):
        src = REAL.read_text()
        self.assertIn('exec "$(dirname "$(readlink -f "$0")")/teleop/real_teleop.sh" "$@"', src)
        code = [l for l in src.splitlines() if l.strip() and not l.lstrip().startswith("#")]
        self.assertEqual(len(code), 1, code)

    def test_a_symlink_to_real_sh_works(self):
        with tempfile.TemporaryDirectory() as tmp:
            link = os.path.join(tmp, "real.sh"); os.symlink(REAL, link)
            r = run(script=link, env=fake_env(tmp))
            self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
            self.assertIn("tools/real.sh teleop drone_1", r.stdout); self.assertEqual(calls(tmp), "")

    def test_strict_shell_and_no_detached_exec(self):
        src = FRONT.read_text()
        self.assertIn("set -euo pipefail", src)
        self.assertNotIn("exec -d", src); self.assertNotIn("docker exec -d", src)


class Usage(unittest.TestCase):
    def test_no_args_prints_usage_with_literal_examples_exit_2(self):
        r = run()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        out = r.stdout + r.stderr
        for ex in ("tools/real.sh pad", "tools/real.sh pad --static", "tools/real.sh teleop drone_1", "tools/real.sh teleop drone_2"):
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

    def test_guided_check_under_the_test_hook_runs_without_t(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = run("pad", env=fake_env(tmp, REAL_TELEOP_NO_TTY_OK=1))              # unit tests only: no terminal, no -t
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("exec -i %s bash -ic python3 /tmp/svg_real/pad_check.py --pad f310\n" % R, calls(tmp))

    def test_guided_check_in_a_terminal_passes_t(self):
        import pty
        master, slave = pty.openpty()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                r = run("pad", env=fake_env(tmp), stdin=slave)                     # a real terminal on stdin, no hook
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertIn("exec -i -t %s bash -ic python3 /tmp/svg_real/pad_check.py --pad f310\n" % R, calls(tmp))
        finally:
            os.close(master); os.close(slave)

    def test_isaac_check_that_errors_is_cannot_check(self):          # fail closed: only pgrep's 1 means "not running"
        for rc in (126, 2, 125):
            with tempfile.TemporaryDirectory() as tmp:
                r = run("pad", "--static", env=fake_env(tmp, FAKE_PS="isaac-sim\\n%s\\n" % R, FAKE_ISAAC_RC=rc))
                self.assertEqual(r.returncode, 2, (rc, r.stdout, r.stderr))
                self.assertIn("PAD CHECK: FAIL — do not fly: cannot tell whether Isaac Sim is running (", r.stdout)
                self.assertNotIn("cp ", calls(tmp))

    def test_noise_lines_are_filtered_and_the_exit_code_kept(self):
        self.assertIn("NOISE='^(bash: cannot set terminal|bash: no job control|Sourcing|groups: cannot find name)'",
                      (TOOLS / "lib" / "stack.sh").read_text())
        self.assertIn("NOISE='^(bash: cannot set terminal|bash: no job control|Sourcing|groups: cannot find name)'", FRONT.read_text())
        for rc in (0, 1, 3):
            with tempfile.TemporaryDirectory() as tmp:
                r = run("pad", "--static", env=fake_env(tmp, FAKE_NOISE=1, FAKE_EXEC_RC=rc))
                self.assertEqual(r.returncode, rc, r.stdout + r.stderr)
                self.assertIn("FAKE pad check output", r.stdout)
                for n in ("cannot set terminal", "no job control", "Sourcing"):
                    self.assertNotIn(n, r.stdout + r.stderr)

    def test_every_failed_docker_step_prints_the_fail_line(self):
        for glob in ("exec %s mkdir*" % R, "cp *pad_core.py*", "cp *pad_check.py*"):
            with tempfile.TemporaryDirectory() as tmp:
                r = run("pad", "--static", env=fake_env(tmp, FAKE_FAIL_MATCH=glob))
                self.assertEqual(r.returncode, 2, (glob, r.stdout, r.stderr))
                self.assertIn("PAD CHECK: FAIL — do not fly:", r.stdout, glob)
                self.assertNotIn("bash -ic", calls(tmp), glob)

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


PANES_2 = ['laptop : cd ~/AirStack-starling-max2 && MOCAP_BODIES="drone_2" ./mocap.sh',
           'pane 1 : MicroXRCEAgent udp4 -p 8888 -v4',
           'pane 2 : ros2 launch svg_ground_control real_interfaces.launch.py drones:=drone_2 target_systems:=2',
           'pane 3 : ros2 launch svg_ground_control ground_control.launch.py config:=/tmp/svg_real/teleop_real_drone_2.yaml use_mocap:=true use_foxglove_studio:=true',
           'pane 5 : ros2 launch svg_ground_control teleop.launch.py config:=/tmp/svg_real/teleop_real_drone_2.yaml']


class TeleopCommand(unittest.TestCase):
    def test_unknown_drone_exit_2_before_any_docker_call(self):
        for args in (["teleop"], ["teleop", "drone_3"], ["teleop", "drone_N"], ["teleop", "2"], ["teleop", "drone_02"],
                     ["teleop", ""], ["teleop", "drone_1", "extra"], ["teleop", "--static"]):
            with tempfile.TemporaryDirectory() as tmp:
                r = run(*args, env=fake_env(tmp, REAL_TELEOP_NO_TTY_OK=1))
                self.assertEqual(r.returncode, 2, (args, r.stdout, r.stderr))
                self.assertIn("usage:", r.stderr, args)
                self.assertEqual(calls(tmp), "", args)

    def test_drone_3_names_the_two_drones(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = run("teleop", "drone_3", env=fake_env(tmp))
            self.assertIn("error: unknown drone 'drone_3' — use drone_1 or drone_2", r.stderr)

    def test_refuses_without_a_terminal_before_docker(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = run("teleop", "drone_2", env=fake_env(tmp))
            self.assertEqual(r.returncode, 2, r.stdout + r.stderr); self.assertIn("terminal", r.stdout)
            self.assertEqual(calls(tmp), "")

    def test_refuses_while_the_sim_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = run("teleop", "drone_2", env=fake_env(tmp, REAL_TELEOP_NO_TTY_OK=1, FAKE_PS="isaac-sim\\n%s\\n" % R, FAKE_ISAAC=1))
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("PAD CHECK: FAIL — do not fly: Isaac Sim running — real teleop refused", r.stdout)
            self.assertNotIn("cp ", calls(tmp))

    def test_container_down_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = run("teleop", "drone_1", env=fake_env(tmp, REAL_TELEOP_NO_TTY_OK=1, FAKE_PS=""))
            self.assertEqual(r.returncode, 2, r.stdout + r.stderr); self.assertNotIn("cp ", calls(tmp))

    def test_pass_runs_the_full_check_then_copies_the_config_and_prints_the_panes(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = run("teleop", "drone_2", env=fake_env(tmp, REAL_TELEOP_NO_TTY_OK=1))
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            c = calls(tmp); lines = c.splitlines()
            idx = lambda pat: next(i for i, l in enumerate(lines) if pat in l)
            check = idx("bash -ic python3 /tmp/svg_real/pad_check.py --pad f310")
            self.assertNotIn("--static", lines[check])                                      # the full check, sticks included
            cp = idx(":/tmp/svg_real/teleop_real_drone_2.yaml")
            self.assertLess(check, cp); self.assertTrue(lines[cp].startswith("cp "))
            self.assertNotIn("exec -d", c)
            out = r.stdout
            for p in PANES_2:
                self.assertIn(p + "\n", out)
            self.assertIn("Stand drone_2 on x -0.5, y 0.0, nose toward +x. Takeoff flies a straight line to that point.", out)
            self.assertIn('drone_names: ["drone_2"]', out); self.assertIn('teleop_controller: "xbox_usb"', out)
            self.assertTrue(out.rstrip().endswith("Do not press MODE. Re-run this command after any container restart or pad replug."))
            self.assertLess(out.index("FAKE pad check output"), out.index("Stand drone_2"))
            self.assertNotIn("drone_N", out); self.assertNotIn("<", out)

    def test_drone_1_uses_target_system_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = run("teleop", "drone_1", env=fake_env(tmp, REAL_TELEOP_NO_TTY_OK=1))
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("pane 2 : ros2 launch svg_ground_control real_interfaces.launch.py drones:=drone_1 target_systems:=1", r.stdout)
            self.assertIn(":/tmp/svg_real/teleop_real_drone_1.yaml", calls(tmp))

    def test_an_old_config_is_removed_before_the_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = run("teleop", "drone_2", env=fake_env(tmp, REAL_TELEOP_NO_TTY_OK=1))
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            lines = calls(tmp).splitlines()
            rm = lines.index("exec %s rm -f /tmp/svg_real/teleop_real_drone_2.yaml" % R)
            check = next(i for i, l in enumerate(lines) if "pad_check.py" in l and "bash -ic" in l)
            self.assertLess(rm, check)

    def test_a_failed_check_leaves_no_config(self):
        for rc in (1, 2, 3):
            with tempfile.TemporaryDirectory() as tmp:
                r = run("teleop", "drone_2", env=fake_env(tmp, REAL_TELEOP_NO_TTY_OK=1, FAKE_EXEC_RC=rc))
                self.assertEqual(r.returncode, rc)
                c = calls(tmp)
                self.assertIn("rm -f /tmp/svg_real/teleop_real_drone_2.yaml", c)
                self.assertNotRegex(c, r"(?m)^cp .*teleop_real_drone_2\.yaml")
                self.assertNotIn("pane 3", r.stdout)

    def test_a_failed_rm_or_config_copy_prints_the_fail_line(self):
        for glob in ("exec %s rm -f*" % R, "cp *teleop_real_drone_2.yaml"):
            with tempfile.TemporaryDirectory() as tmp:
                r = run("teleop", "drone_2", env=fake_env(tmp, REAL_TELEOP_NO_TTY_OK=1, FAKE_FAIL_MATCH=glob))
                self.assertEqual(r.returncode, 2, (glob, r.stdout, r.stderr))
                self.assertIn("PAD CHECK: FAIL — do not fly:", r.stdout, glob); self.assertNotIn("pane 3", r.stdout)

    def test_a_refused_render_exits_1_before_any_docker_call(self):
        bad = SOURCE.replace("    max_climb_speed_mps: 0.5", "    max_climb_speed_mps: 0.5\n    forward_sign: -1.0", 1)
        with tempfile.TemporaryDirectory() as tmp:
            script = copy_tree(tmp, bad)
            r = run("teleop", "drone_2", env=fake_env(tmp, REAL_TELEOP_NO_TTY_OK=1), script=script)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("PAD CHECK: FAIL — do not fly: the drone_2 config was not made:", r.stdout)
            self.assertIn("forward_sign", r.stdout); self.assertEqual(calls(tmp), "")

    def test_pyyaml_missing_is_cannot_check_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            shim = os.path.join(tmp, "shim"); os.makedirs(shim)
            pathlib.Path(shim, "yaml.py").write_text("raise ImportError('no PyYAML in this test')\n")
            r = run("teleop", "drone_2", env=fake_env(tmp, REAL_TELEOP_NO_TTY_OK=1, PYTHONPATH=shim))
            self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
            self.assertIn("PAD CHECK: FAIL — do not fly: cannot check:", r.stdout); self.assertIn("PyYAML", r.stdout)
            self.assertEqual(calls(tmp), "")

    def test_the_copied_file_is_the_checked_render(self):
        with tempfile.TemporaryDirectory() as tmp:
            keep = os.path.join(tmp, "copied.yaml")
            env = fake_env(tmp, REAL_TELEOP_NO_TTY_OK=1)
            fake = os.path.join(tmp, "bin", "docker")             # the fake keeps a copy of what `docker cp` gets for the yaml
            pathlib.Path(fake).write_text(FAKE.replace('echo "$@" >> "$FAKE_LOG"\n',
                                               'echo "$@" >> "$FAKE_LOG"\ncase "$*" in cp*teleop_real_*) cp "$2" %s;; esac\n' % keep))
            r = run("teleop", "drone_2", env=env)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            sys.path.insert(0, str(TOOLS / "teleop"))
            import pad_core, real_config
            src = (TOOLS.parent / "AirStack/robot/ros_ws/src/svg_ground_control/config/teleop_real_ours.yaml").read_text()
            real_config.verify_render(src, pathlib.Path(keep).read_text(), "drone_2", pad_core.F310)


class PadCheckShell(unittest.TestCase):
    """pad_check.py as a script: compile, refusals that come before ROS, and source pins. Its main() runs against a fake
    ROS in tools/tests/test_pad_check.py (the joy_node pin and the stop on every exit path are tested there)."""
    SRC = PAD_CHECK.read_text()

    def test_compiles(self):
        py_compile.compile(str(PAD_CHECK), doraise=True)

    def _run(self, *args, tty_ok=False):
        with tempfile.TemporaryDirectory() as shim:
            pathlib.Path(shim, "rclpy.py").write_text("raise ImportError('no ROS in this test')\n")
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

    def test_timeouts_match_the_spec(self):
        for n in ("DISCOVERY_S = 2.0", "FIRST_MSG_S = 5.0", "STEP_S = 15.0", "COLLECT_S = 0.5", "BACK_TO_REST_S = 10.0"):
            self.assertIn(n, self.SRC)

    def test_every_decision_is_in_pad_core(self):
        for fn in ("judge_usb", "judge_driver", "judge_environment", "judge_opened", "judge_shape", "judge_rest", "steps_for", "judge_step"):
            self.assertIn("P." + fn + "(", self.SRC, fn)


if __name__ == "__main__":
    unittest.main()
