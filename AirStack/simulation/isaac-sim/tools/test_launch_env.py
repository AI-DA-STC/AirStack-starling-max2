"""Host test (plain python3): env-var handling used by svg_multi_drone_single_domain.py.
   python3 AirStack/simulation/isaac-sim/tools/test_launch_env.py
"""
import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "launch_scripts"))
from launch_env import resolve_vehicle   # noqa: E402

IRIS = "~/.local/share/ov/data/documents/Kit/shared/exts/pegasus.simulator/pegasus/simulator/assets/Robots/Iris/iris.usd"
STARLING = "/isaac-sim/AirStack/simulation/isaac-sim/assets/robots/starling2max.usd"


class LaunchEnvTest(unittest.TestCase):
    def test_unset_is_iris(self):
        usd, model, zed = resolve_vehicle({})
        self.assertEqual((usd, model), (IRIS, "gazebo-classic_iris")); self.assertEqual(zed, [0.2, 0.0, -0.05])

    def test_empty_string_is_unset(self):
        usd, model, _ = resolve_vehicle({"DRONE_USD": "", "PX4_VEHICLE_MODEL": "  "})
        self.assertEqual((usd, model), (IRIS, "gazebo-classic_iris"))

    def test_starling_sets_model_and_zed_offset(self):
        usd, model, zed = resolve_vehicle({"DRONE_USD": STARLING, "PX4_VEHICLE_MODEL": "pegasus_starling2max"})
        self.assertEqual((usd, model), (STARLING, "pegasus_starling2max")); self.assertEqual(zed, [0.12, 0.0, -0.03])

    def test_starling_usd_without_model_warns_but_keeps_iris_model(self):
        usd, model, _ = resolve_vehicle({"DRONE_USD": STARLING})
        self.assertEqual(model, "gazebo-classic_iris")


if __name__ == "__main__":
    unittest.main()
