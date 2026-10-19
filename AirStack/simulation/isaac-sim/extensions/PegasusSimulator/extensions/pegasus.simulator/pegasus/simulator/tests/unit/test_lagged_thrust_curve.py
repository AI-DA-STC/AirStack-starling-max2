"""Unit tests for the lagged thrust curve. Pure numpy — runs without Isaac Sim:
   AirStack/simulation/isaac-sim/tools/isaac_python.sh -m unittest discover -s \
     AirStack/simulation/isaac-sim/extensions/PegasusSimulator/extensions/pegasus.simulator/pegasus/simulator/tests/unit -v
Importing pegasus.simulator normally boots the Omniverse extension, so the package
modules are stubbed and only leaf modules are loaded from their files.
"""
import os
import sys
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SIM = os.path.abspath(os.path.join(HERE, "..", ".."))          # …/pegasus/simulator
ROOT = os.path.abspath(os.path.join(SIM, "..", ".."))          # …/pegasus.simulator


def _stub(name, path):
    if name not in sys.modules:
        m = types.ModuleType(name)
        m.__path__ = [path]
        sys.modules[name] = m


for name, path in (("pegasus", os.path.join(ROOT, "pegasus")),
                   ("pegasus.simulator", SIM),
                   ("pegasus.simulator.logic", os.path.join(SIM, "logic"))):
    _stub(name, path)
sys.path.insert(0, ROOT)

from pegasus.simulator.logic.thrusters.quadratic_thrust_curve import QuadraticThrustCurve  # noqa: E402
from pegasus.simulator.logic.thrusters.lagged_quadratic_thrust_curve import LaggedQuadraticThrustCurve  # noqa: E402

KF = 3.964738e-6


class LaggedThrustCurveTest(unittest.TestCase):
    def test_zero_time_constant_matches_parent(self):
        cfg = {"rotor_constant": [KF] * 4, "max_rotor_velocity": [1450] * 4}
        a, b = QuadraticThrustCurve(cfg), LaggedQuadraticThrustCurve(dict(cfg, time_constant=0.0))
        for ref in ([600] * 4, [0, 1450, 2000, 300]):
            a.set_input_reference(ref); b.set_input_reference(ref)
            fa, va, ma = a.update(None, 0.004); fb, vb, mb = b.update(None, 0.004)
            self.assertEqual(list(va), list(vb)); self.assertEqual(list(fa), list(fb)); self.assertEqual(ma, mb)

    def test_first_tick_starts_from_reference_not_zero(self):
        c = LaggedQuadraticThrustCurve({"rotor_constant": [KF] * 4, "time_constant": 0.072})
        c.set_input_reference([587.0] * 4)
        _, v, _ = c.update(None, 0.004)
        self.assertAlmostEqual(v[0], 587.0, places=6)   # no spin-up spike from 0 on the first tick

    def test_step_reaches_63_percent_after_one_tau(self):
        tau, dt = 0.072, 0.001
        c = LaggedQuadraticThrustCurve({"rotor_constant": [KF] * 4, "max_rotor_velocity": [1450] * 4, "time_constant": tau})
        c.set_input_reference([500.0] * 4); c.update(None, dt)           # settle at 500
        c.set_input_reference([1000.0] * 4)
        v = None
        for _ in range(int(round(tau / dt))):
            _, v, _ = c.update(None, dt)
        self.assertAlmostEqual((v[0] - 500.0) / 500.0, 1 - 2.718281828 ** -1, delta=0.02)

    def test_force_is_kf_omega_squared_of_lagged_velocity(self):
        c = LaggedQuadraticThrustCurve({"rotor_constant": [KF] * 4, "time_constant": 0.072})
        c.set_input_reference([600.0] * 4); c.update(None, 0.004)
        c.set_input_reference([900.0] * 4)
        f, v, _ = c.update(None, 0.004)
        self.assertLess(v[0], 900.0)                      # lagging
        self.assertAlmostEqual(f[0], KF * v[0] ** 2, places=9)

    def test_clamps_to_max_rotor_velocity(self):
        c = LaggedQuadraticThrustCurve({"rotor_constant": [KF] * 4, "max_rotor_velocity": [1450] * 4, "time_constant": 0.072})
        c.set_input_reference([5000.0] * 4)
        for _ in range(500):
            _, v, _ = c.update(None, 0.004)
        self.assertLessEqual(v[0], 1450.0 + 1e-9)


if __name__ == "__main__":
    unittest.main()
