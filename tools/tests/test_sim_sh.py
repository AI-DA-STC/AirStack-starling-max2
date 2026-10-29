# tools/tests/test_sim_sh.py
import pathlib, subprocess, unittest
SIM = pathlib.Path(__file__).resolve().parents[1] / "sim.sh"

def run(*args):
    return subprocess.run(["bash", str(SIM), *args], capture_output=True, text=True, timeout=20)

class SimSh(unittest.TestCase):
    def test_parses(self):
        self.assertEqual(subprocess.run(["bash", "-n", str(SIM)]).returncode, 0)

    def test_no_args_prints_usage_exit_2(self):
        r = run(); self.assertEqual(r.returncode, 2); self.assertIn("usage:", r.stdout)
        for sub in ("setup", "doctor", "up", "down", "status", "tabs", "test", "figures", "check"): self.assertIn(sub, r.stdout)

    def test_unknown_subcommand_exit_2(self):
        self.assertEqual(run("fly").returncode, 2)

    def test_sim_sh_rejects_bad_flags(self):                      # Review Focus 3
        for args in (["test", "crossing", "--ledger", "x", "--issue", "NEAR-787", "r1"],
                     ["test", "crossing", "--ledger", "20", "--issue", "NEAR787", "r1"],
                     ["test", "crossing", "--ledger", "20", "r1"],
                     ["test", "_template", "--ledger", "20", "--issue", "NEAR-787", "r1"],
                     ["test", "no_such_test", "--ledger", "20", "--issue", "NEAR-787", "r1"],
                     ["test", "crossing", "--ledger", "20", "--issue", "NEAR-787", "bad run"]):
            r = run(*args); self.assertEqual(r.returncode, 2, args); self.assertIn("error:", r.stderr, args)
            self.assertNotIn("docker", (r.stdout + r.stderr).lower(), args)   # failed before any container call; the usage text never says "docker"
            self.assertNotRegex(r.stdout, r"^\[\d\d:\d\d:\d\d")                # no `say` line: no phase ran
