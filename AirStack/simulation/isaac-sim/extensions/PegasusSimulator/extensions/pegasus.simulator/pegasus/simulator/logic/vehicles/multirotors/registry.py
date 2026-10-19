"""Pick a MultirotorConfig subclass from the vehicle USD file name.

The OGN PX4 node has no input for dynamics, so the USD file is the only handle the
launch script controls. `vehicle_key_from_usd` is pure (unit-tested without Omniverse);
`select_vehicle_config` imports the config class lazily because those modules pull in
Isaac/Omniverse.
"""
import os

# stem substring -> key. Order matters: first match wins. Add new airframes here.
_KEYS = (
    ("starling", "starling2max"),
)
DEFAULT_KEY = "iris"


def vehicle_key_from_usd(usd_file) -> str:
    if not usd_file:
        return DEFAULT_KEY
    stem = os.path.splitext(os.path.basename(str(usd_file)))[0].lower()
    for needle, key in _KEYS:
        if needle in stem:
            return key
    return DEFAULT_KEY


def select_vehicle_config(usd_file):
    """Return the config CLASS (not instance) for this USD. Falls back to MultirotorConfig."""
    key = vehicle_key_from_usd(usd_file)
    if key == "starling2max":
        from pegasus.simulator.logic.vehicles.multirotors.starling2max import Starling2MaxConfig
        return Starling2MaxConfig
    from pegasus.simulator.logic.vehicles.multirotor import MultirotorConfig
    return MultirotorConfig
