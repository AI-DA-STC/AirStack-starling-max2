"""ModalAI Starling 2 Max — dynamics from CMU AirLab's system-identification campaign
("Starling 2 Max Sys ID Results", repo file isaac_sim/Starling 2 Max Sys ID Results - Slite.pdf).

Mass 0.557 kg, inertia and centre of mass live in the USD (assets/robots/starling2max.usd).
Here: propeller constants, motor lag, rotor-speed ceiling.
"""
from pegasus.simulator.logic.vehicles.multirotor import MultirotorConfig
from pegasus.simulator.logic.dynamics import LinearDrag
from pegasus.simulator.logic.thrusters import LaggedQuadraticThrustCurve

ROTOR_CONSTANT = 3.964738e-6              # N / (rad/s)^2      (CMU sys-ID)
ROLLING_MOMENT_COEFFICIENT = 5.38697e-8   # N·m / (rad/s)^2    (CMU sys-ID)
MOTOR_TIME_CONSTANT_S = 0.072             # s                  (CMU sys-ID, 55 up / 85 down)
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
            "time_constant": MOTOR_TIME_CONSTANT_S,
        })
        # Drag was not identified by CMU; keep the Pegasus default.
        self.drag = LinearDrag([0.50, 0.30, 0.0])
