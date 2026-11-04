# tools/tests/test_svg_teleop_install.py — the Foxglove strip is installed by slam_up.sh and ships in its own layout (NEAR-789, sim)
import json, pathlib, re, subprocess, tempfile, unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
FOX = ROOT / "tools/teleop/foxglove"
LAYOUT = FOX / "teleop-cuvslam.json"


def panel_ids(node):
    if isinstance(node, str):
        return [node]
    return panel_ids(node["first"]) + panel_ids(node["second"])


class Install(unittest.TestCase):
    def run_install(self, dest):
        return subprocess.run(["bash", str(FOX / "install.sh"), str(dest)], capture_output=True, text=True)

    def test_install_copies_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as t:
            for _ in range(2):
                r = self.run_install(t)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            d = pathlib.Path(t) / "nearlab.svg-teleop-1.0.0"
            self.assertTrue((d / "package.json").is_file())
            self.assertTrue((d / "dist/extension.js").is_file())
            self.assertFalse((d / "test").exists(), "tests must stay out of the installed copy")
            self.assertEqual(sorted(p.name for p in pathlib.Path(t).iterdir()), ["nearlab.svg-teleop-1.0.0"])

    def test_install_replaces_a_stale_copy(self):
        with tempfile.TemporaryDirectory() as t:
            d = pathlib.Path(t) / "nearlab.svg-teleop-1.0.0"
            (d / "dist").mkdir(parents=True)
            (d / "dist/old.js").write_text("x")
            self.assertEqual(self.run_install(t).returncode, 0)
            self.assertFalse((d / "dist/old.js").exists())

    def test_install_uses_no_python_or_rsync(self):
        src = (FOX / "install.sh").read_text()
        for word in ("python", "rsync"):
            self.assertNotIn(word, src)

    def test_slam_up_installs_before_studio(self):
        src = (ROOT / "localisation/scripts/slam_up.sh").read_text()
        self.assertLess(src.index("bash /teleop-foxglove/install.sh"), src.index("foxglove-studio --no-sandbox"))

    def test_slam_up_carries_on_without_the_mount(self):
        src = (ROOT / "localisation/scripts/slam_up.sh").read_text()
        self.assertIn("Teleop panel not installed: run scripts/slam_down.sh, then scripts/slam_up.sh", src)

    def test_exploration_container_mounts_the_panel_read_only(self):
        src = (ROOT / "localisation/docker/up.sh").read_text()
        self.assertIn('"$PWD/../tools/teleop/foxglove":/teleop-foxglove:ro', src)


class Layout(unittest.TestCase):
    def setUp(self):
        self.d = json.load(open(LAYOUT))

    def strip_id(self):
        # Studio builds the id as <package displayName>.<registerPanel name>!<instance>
        pkg = json.load(open(FOX / "svg-teleop/package.json"))
        name = re.search(r'registerPanel\(\{\s*name:\s*"([^"]+)"', (FOX / "svg-teleop/dist/extension.js").read_text()).group(1)
        return f"{pkg['displayName']}.{name}!teleop"

    def test_panel_id_follows_the_package_display_name(self):
        pkg = json.load(open(FOX / "svg-teleop/package.json"))
        self.assertEqual(pkg["displayName"], pkg["name"])
        self.assertIn(self.strip_id(), self.d["configById"])
        self.assertTrue(self.strip_id().startswith("svg-teleop.SVG Teleop!"))

    def three_d_id(self):
        return next(k for k in self.d["configById"] if k.startswith("3D!"))

    def test_three_panels_in_the_chosen_arrangement(self):
        lay = self.d["layout"]
        self.assertEqual(lay["direction"], "column")
        top, bottom = lay["first"], lay["second"]
        self.assertIsInstance(top, dict)
        self.assertEqual(top["direction"], "row")
        self.assertTrue(top["first"].startswith("Image!"))
        self.assertIn(self.three_d_id(), panel_ids(top["second"]))
        self.assertEqual(bottom, self.strip_id())
        self.assertGreaterEqual(lay["splitPercentage"], 70)
        self.assertLessEqual(lay["splitPercentage"], 85)
        self.assertTrue(any(i.startswith("Tab!") for i in panel_ids(lay)))

    def test_every_laid_out_panel_has_a_config(self):
        for pid in panel_ids(self.d["layout"]):
            self.assertIn(pid, self.d["configById"])

    def test_image_shows_the_cuvslam_debug_image(self):
        c = next(v for k, v in self.d["configById"].items() if k.startswith("Image!"))
        self.assertEqual(c["imageMode"]["imageTopic"], "/drone_1/cuvslam/debug_image")

    def test_chase_follows_the_moving_body_with_its_heading(self):
        c = self.d["configById"][self.three_d_id()]
        self.assertEqual(c["followTf"], "drone_1/cuvslam_base")
        self.assertEqual(c["followMode"], "follow-pose")
        self.assertTrue(c["cameraState"]["perspective"])
        self.assertEqual(c["cameraState"]["distance"], 4)
        self.assertEqual(c["cameraState"]["phi"], 65)

    def test_grid_topic_visible_and_builtin_grid_off(self):
        c = self.d["configById"][self.three_d_id()]
        self.assertTrue(c["topics"]["/drone_1/cuvslam/grid"]["visible"])
        self.assertFalse(c["layers"]["grid"]["visible"])

    def test_reserved_tab_untouched(self):
        t = self.d["configById"]["Tab!map"]
        self.assertEqual(t["tabs"], [{"title": "Map (reserved)", "layout": None}])

    def test_strip_config_keeps_template_defaults(self):
        c = self.d["configById"][self.strip_id()]
        self.assertEqual(c["drones"], ["drone_1"])
        self.assertFalse([k for k in c if k.endswith("Template")])


if __name__ == "__main__":
    unittest.main()
