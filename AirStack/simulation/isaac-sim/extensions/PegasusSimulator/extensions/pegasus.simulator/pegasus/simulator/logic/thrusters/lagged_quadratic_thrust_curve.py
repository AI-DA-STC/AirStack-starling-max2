"""
| File: lagged_quadratic_thrust_curve.py
| Description: Quadratic thrust curve with a first-order motor lag on the rotor speed.
|   Added for the Starling 2 Max (CMU sys-ID: tau ~72 ms). With time_constant = 0 it is
|   identical to QuadraticThrustCurve.
"""
import numpy as np
from pegasus.simulator.logic.state import State
from pegasus.simulator.logic.thrusters.quadratic_thrust_curve import QuadraticThrustCurve


class LaggedQuadraticThrustCurve(QuadraticThrustCurve):
    """QuadraticThrustCurve whose rotor speed follows the commanded speed through a
    first-order lag:  omega += dt / tau * (omega_cmd - omega).

    Extra config key:
        "time_constant": float seconds (default 0.0 = no lag)
    """

    def __init__(self, config={}):
        super().__init__(config)
        self._time_constant = float(config.get("time_constant", 0.0))
        self._lagged = None   # None until the first update: start exactly at the reference

    def _clamped_reference(self, i):
        return float(np.maximum(self.min_rotor_velocity[i],
                                np.minimum(self._input_reference[i], self.max_rotor_velocity[i])))

    def update(self, state: State, dt: float):
        if self._lagged is None:
            self._lagged = [self._clamped_reference(k) for k in range(self._num_rotors)]
        rolling_moment = 0.0
        for i in range(self._num_rotors):
            target = self._clamped_reference(i)
            if self._time_constant > 0.0 and dt > 0.0:
                alpha = min(1.0, dt / self._time_constant)
                self._lagged[i] += alpha * (target - self._lagged[i])
            else:
                self._lagged[i] = target
            self._velocity[i] = self._lagged[i]
            self._force[i] = self._rotor_constant[i] * np.power(self._velocity[i], 2)
            rolling_moment += self._rolling_moment_coefficient[i] * np.power(self._velocity[i], 2.0) * self._rot_dir[i]
        self._rolling_moment = rolling_moment
        return self._force, self._velocity, self._rolling_moment
