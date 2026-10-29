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
            r = run("test", "foo", "--headless", "--no-pause", *ok, env=env)       # everything valid: parsing passes, stub answers
            self.assertEqual(r.returncode, 2); self.assertIn("not implemented yet", r.stderr); self.assertNotIn("usage:", r.stderr)
