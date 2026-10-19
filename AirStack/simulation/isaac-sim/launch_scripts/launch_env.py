"""Vehicle selection for the SVG launch script from environment variables (no Isaac imports).

DRONE_USD          vehicle USD path as seen INSIDE the Isaac container. Unset/empty = Pegasus Iris.
PX4_VEHICLE_MODEL  PX4 SITL model name (rcS matches airframes/NNNNN_<name>). Unset/empty = gazebo-classic_iris.
"""
import os

IRIS_USD = "~/.local/share/ov/data/documents/Kit/shared/exts/pegasus.simulator/pegasus/simulator/assets/Robots/Iris/iris.usd"
IRIS_MODEL = "gazebo-classic_iris"
ZED_OFFSET_IRIS = [0.2, 0.0, -0.05]
ZED_OFFSET_STARLING = [0.12, 0.0, -0.03]   # half-size frame
# PX4 actuator (0..1) -> rotor speed: omega = INPUT_SCALING * u + 100 (zero_position_armed).
INPUT_SCALING_IRIS = 1000.0       # Pegasus default: omega_max 1100 rad/s
INPUT_SCALING_STARLING = 1350.0   # omega_max 1450 rad/s; hover 587 rad/s lands at u ~ 0.36 (airframe MPC_THR_HOVER)


def resolve_vehicle(env=None):
    """Return (drone_usd, px4_vehicle_model, zed_camera_offset, input_scaling)."""
    env = os.environ if env is None else env
    usd = (env.get("DRONE_USD") or "").strip() or IRIS_USD
    model = (env.get("PX4_VEHICLE_MODEL") or "").strip() or IRIS_MODEL
    is_starling = "starling" in os.path.basename(usd).lower()
    if is_starling and model == IRIS_MODEL:
        print("[svg_multi_drone] WARNING: DRONE_USD is a Starling but PX4_VEHICLE_MODEL is unset — "
              "PX4 will run the Iris airframe (set PX4_VEHICLE_MODEL=pegasus_starling2max)")
    return (usd, model,
            ZED_OFFSET_STARLING if is_starling else ZED_OFFSET_IRIS,
            INPUT_SCALING_STARLING if is_starling else INPUT_SCALING_IRIS)
