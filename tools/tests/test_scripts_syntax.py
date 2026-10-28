# tools/tests/test_scripts_syntax.py
import pathlib, subprocess, unittest
TOOLS = pathlib.Path(__file__).resolve().parents[1]

class ScriptSyntax(unittest.TestCase):
    def test_test_script_parses_and_sleeps(self):
        p = TOOLS / "sim_hover_step_test.sh"
        self.assertTrue(p.exists(), p)
        self.assertEqual(subprocess.run(["bash", "-n", str(p)]).returncode, 0)
        src = p.read_text()
        self.assertIn('wait_s(){ sleep "$1"; }', src)
        self.assertNotIn("ros2 topic echo /clock", src)
        self.assertIn("STEPS_PER_AXIS", src)

    def test_make_figures_names_the_runs_and_the_fixed_output(self):
        p = TOOLS / "make_figures.sh"
        self.assertEqual(subprocess.run(["bash", "-n", str(p)]).returncode, 0)
        src = p.read_text()
        for needle in ("set -euo pipefail", "--overlay", "docs/record/sim_hover_step_run1", "docs/record/sim_hover_step_run2",
                       "docs/record/sim_hover_step_run3", "sim_hover_step_run1=1.336", "docs/record/figures/s5_hover_step_overlay.png"):
            self.assertIn(needle, src, needle)

    def test_analyze_step_is_identical_copy(self):
        ours = (TOOLS / "analyze_step.py").read_bytes()
        theirs = (TOOLS.parent / "AirStack/simulation/isaac-sim/tools/analyze_step.py").read_bytes()
        self.assertEqual(ours, theirs)

    def test_wrapper_parses_and_usage(self):
        p = TOOLS / "sim_hover_step_run.sh"
        self.assertEqual(subprocess.run(["bash", "-n", str(p)]).returncode, 0)
        r = subprocess.run(["bash", str(p), "no_such_phase"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)
        for ph in ("analyse", "status", "report", "collect", "down"): self.assertIn(ph, r.stdout + r.stderr)
        src = p.read_text()
        self.assertNotIn("sed -i", src)                       # no in-container patching
        self.assertNotIn("isaac-sim/tools", src)              # copies come from tools/
        self.assertIn("set -o pipefail", src); self.assertNotIn("set -eo pipefail", src)
        for needle in ("ulogs_copied.ok", "run_meta.txt", "clock_check.txt", "hover_step_timescale.py", "hover_step_analysis.py", "connected: true", "^armed: (true|false)"):
            self.assertIn(needle, src, needle)

    def test_shellcheck_if_present(self):
        import shutil
        if not shutil.which("shellcheck"): self.skipTest("shellcheck not installed")
        r = subprocess.run(["shellcheck", "-S", "warning", str(TOOLS / "sim_hover_step_run.sh"), str(TOOLS / "sim_hover_step_test.sh")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout)
