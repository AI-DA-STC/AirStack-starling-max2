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

    def test_analyze_step_is_identical_copy(self):
        ours = (TOOLS / "analyze_step.py").read_bytes()
        theirs = (TOOLS.parent / "AirStack/simulation/isaac-sim/tools/analyze_step.py").read_bytes()
        self.assertEqual(ours, theirs)
