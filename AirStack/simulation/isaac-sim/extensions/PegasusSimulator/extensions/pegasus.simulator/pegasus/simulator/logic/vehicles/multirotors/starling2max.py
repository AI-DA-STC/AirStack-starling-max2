"""ModalAI Starling 2 Max — dynamics from CMU AirLab's system-identification campaign
("Starling 2 Max Sys ID Results", repo file isaac_sim/Starling 2 Max Sys ID Results - Slite.pdf).

Mass 0.557 kg, inertia and centre of mass live in the USD (assets/robots/starling2max.usd).
Here: propeller constants, motor lag, rotor-speed ceiling.
"""
import os
from pegasus.simulator.logic.vehicles.multirotor import MultirotorConfig
from pegasus.simulator.logic.dynamics import LinearDrag
from pegasus.simulator.logic.thrusters import LaggedQuadraticThrustCurve

ROTOR_CONSTANT = 3.964738e-6              # N / (rad/s)^2      (CMU sys-ID)
ROLLING_MOMENT_COEFFICIENT = 5.38697e-8   # N·m / (rad/s)^2    (CMU sys-ID)
CMU_MEASURED_MOTOR_TAU_S = 0.072          # s  (CMU sys-ID thrust-step response, 55 up / 85 down)
MOTOR_TIME_CONSTANT_S = 0.0               # DEFAULT: no lag. 2026-10-19 sim bisection: with the real drone's
                                          # PX4 gains a plain first-order 72 ms lag makes the attitude loop
                                          # tumble (roll ±100°, ~0.8 s period); with tau=0 it hovers within
                                          # ±2° roll. The real actuator path evidently does not look like a
                                          # 72 ms lag to PX4's rate loop (RPM-controlled ESCs). Re-enable for
                                          # experiments with STARLING_MOTOR_TAU=<s>; see CONFIG "Sim airframe".
MAX_ROTOR_VELOCITY = 1450.0               # rad/s — chosen so hover (587 rad/s) sits near 36 % throttle
ROT_DIR = [-1, -1, 1, 1]                  # PX4 quad-X order FR, BL, FL, BR — same as Iris


class Starling2MaxConfig(MultirotorConfig):
    def __init__(self):
        super().__init__()
        self.thrust_curve = LaggedQuadraticThrustCurve({
            "num_rotors": 4,
            "rotor_constant": [ROTOR_CONSTANT] * 4,
            "rolling_moment_coefficient": [ROLLING_MOMENT_COEFFICIENT] * 4,
            "rot_dir": ROT_DIR,
            "min_rotor_velocity": [0.0] * 4,
            "max_rotor_velocity": [MAX_ROTOR_VELOCITY] * 4,
            # STARLING_MOTOR_TAU (seconds) overrides the lag for experiments; 0 = instantaneous like the Iris
            "time_constant": float(os.environ.get("STARLING_MOTOR_TAU", MOTOR_TIME_CONSTANT_S)),
        })
        print(f"Starling2MaxConfig: k_f={ROTOR_CONSTANT} k_m={ROLLING_MOMENT_COEFFICIENT} omega_max={MAX_ROTOR_VELOCITY} "
              f"tau={self.thrust_curve._time_constant}")
        # Drag was not identified by CMU; keep the Pegasus default.
        self.drag = LinearDrag([0.50, 0.30, 0.0])
