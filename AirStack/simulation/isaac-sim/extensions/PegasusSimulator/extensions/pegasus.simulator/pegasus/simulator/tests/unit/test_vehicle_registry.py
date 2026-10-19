import importlib.util
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REG = os.path.join(HERE, "..", "..", "logic", "vehicles", "multirotors", "registry.py")
spec = importlib.util.spec_from_file_location("registry", REG)
registry = importlib.util.module_from_spec(spec); spec.loader.exec_module(registry)


class VehicleRegistryTest(unittest.TestCase):
    def test_iris_paths_select_iris(self):
        for p in ("~/.local/share/ov/.../Robots/Iris/iris.usd", "/x/iris.usd", "", None):
            self.assertEqual(registry.vehicle_key_from_usd(p), "iris")

    def test_starling_stem_any_case_and_suffix(self):
        for p in ("/isaac-sim/AirStack/simulation/isaac-sim/assets/robots/starling2max.usd",
                  "/tmp/Starling2Max.usdc", "C:/x/STARLING2MAX.usda", "/tmp/starling2max_v2.usd",
                  "/tmp/starlingmax2.usd"):
            self.assertEqual(registry.vehicle_key_from_usd(p), "starling2max", p)

    def test_unknown_stem_falls_back_to_iris(self):
        self.assertEqual(registry.vehicle_key_from_usd("/tmp/x500.usd"), "iris")


if __name__ == "__main__":
    unittest.main()
