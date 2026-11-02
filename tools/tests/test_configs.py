# tools/tests/test_configs.py
import pathlib, unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
CFG = ROOT / "AirStack/robot/ros_ws/src/svg_ground_control/config"


def yaml_load(path):
    import yaml
    return yaml.safe_load(path.read_text())


class TeleopOurs(unittest.TestCase):
    def setUp(self):
        try:
            import yaml  # noqa: F401
        except ImportError:
            self.skipTest("PyYAML missing")

    def test_ours_diverts_safe_teleop_only(self):
        base = yaml_load(CFG / "teleop_single.yaml")
        ours = yaml_load(CFG / "teleop_single_ours.yaml")
        self.assertEqual(ours["swarm_commander"], base["swarm_commander"])
        self.assertEqual(ours["safe_teleop"]["ros__parameters"]["teleop_topic_template"],
                         "/svg/{name}/teleop_command_stick")
        b = dict(base["safe_teleop"]["ros__parameters"])
        o = dict(ours["safe_teleop"]["ros__parameters"])
        b.pop("teleop_topic_template", None)
        o.pop("teleop_topic_template", None)
        self.assertEqual(o, b)

    def test_cockpit_and_docs_name_the_ours_yaml_for_the_keyboard_session(self):
        for f in ("tools/sim_tab.sh", "docs/TELEOP.md"):
            self.assertIn("teleop_single_ours.yaml", (ROOT / f).read_text(), f)


if __name__ == "__main__":
    unittest.main()
