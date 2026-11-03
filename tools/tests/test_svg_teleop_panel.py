# tools/tests/test_svg_teleop_panel.py — the Foxglove strip's JS logic equals keymap.py on the fixtures (NEAR-789, sim)
import pathlib, shutil, subprocess, unittest

PANEL = pathlib.Path(__file__).resolve().parent.parent / "teleop/foxglove/svg-teleop"


def run(*cmd):
    return subprocess.run(cmd, cwd=PANEL, capture_output=True, text=True)


@unittest.skipUnless(shutil.which("node"), "node not installed")
class Panel(unittest.TestCase):
    def test_extension_parses(self):
        self.assertEqual(run("node", "--check", "dist/extension.js").returncode, 0)

    def test_core_matches_keymap_py(self):
        r = run("node", "test/core.test.js")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("core ok", r.stdout)


if __name__ == "__main__":
    unittest.main()
