"""Keyboard -> a gamepad's /joy stream, so CMU's safe_teleop flies the drone unchanged (NEAR-789, sim only).

Pure logic, no ROS and no Tk: key_teleop.py feeds it key events and publishes what it returns.

    Up / Down      forward / back = pitch   (right stick up / down)
    Left / Right   slide left / right = roll (right stick left / right)
    W / S          up / down                (left stick up / down = climb)
    A / D          turn left / right        (left stick left / right = yaw)
    Shift / Ctrl   up / down, Q / E  turn left / right (aliases of W/S and A/D)
    1 / 2 / 3      25 / 50 / 100 % of top speed (default 50 %; safe_teleop's dead zone is compensated)

A "mode 2" layout: arrows = right stick (move), WASD = left stick (height + heading). safe_teleop commands
velocities, so "roll" slides the drone sideways and "pitch" moves it forward/back; there is no attitude command.

Signs follow CMU's controllers.py: stick up = +forward, stick left = +left (ENU), yaw stick left = +yaw
(counter-clockwise), left stick up = +climb. Opposite keys cancel. A release only counts after DEBOUNCE_S
with no new press of the same key, because X11 key auto-repeat sends release+press pairs while a key is held.
"""
from __future__ import annotations

from dataclasses import dataclass

DEBOUNCE_S = 0.06            # X11 auto-repeat pairs arrive within a few ms; a real release is longer
HOLD_SILENCE_S = 1.0         # a held key auto-repeats (GNOME: first repeat 500 ms, then every 30 ms); a key with no
                             # event for this long is NOT held — its release was swallowed (Alt-Tab, a grab): drop it
DEADZONE = 0.15              # safe_teleop's default `deadzone` (velocity.py); key_teleop reads the live value
N_AXES, N_BUTTONS = 8, 15    # as wide as the widest pad layout CMU supports
SCALES = {"1": 0.25, "2": 0.5, "3": 1.0}
DEFAULT_SCALE = 0.5


@dataclass(frozen=True)
class Profile:
    """The axis numbers of one CMU controller profile (safe_teleop/controllers.py), copied by value and
    checked against that file by tools/tests/test_keymap.py."""
    name: str
    forward_axis: int
    left_axis: int
    climb_axis: int
    yaw_axis: int
    lock_button: int


PROFILES = {
    "dragonrise_usb": Profile("dragonrise_usb", forward_axis=3, left_axis=2, climb_axis=1, yaw_axis=0, lock_button=6),
    "xbox_usb": Profile("xbox_usb", forward_axis=4, left_axis=3, climb_axis=1, yaw_axis=0, lock_button=4),
}

# key -> (stick, direction). Stick names are the Profile fields without "_axis".
KEYS = {
    "up": ("forward", 1.0), "down": ("forward", -1.0),           # pitch
    "left": ("left", 1.0), "right": ("left", -1.0),              # roll
    "w": ("climb", 1.0), "s": ("climb", -1.0),
    "a": ("yaw", 1.0), "d": ("yaw", -1.0),
    "shift_l": ("climb", 1.0), "shift_r": ("climb", 1.0),        # aliases from the first layout
    "control_l": ("climb", -1.0), "control_r": ("climb", -1.0),
    "q": ("yaw", 1.0), "e": ("yaw", -1.0),
}
WORDS = {("forward", 1.0): "forward", ("forward", -1.0): "back", ("left", 1.0): "left", ("left", -1.0): "right",
         ("yaw", 1.0): "turn left", ("yaw", -1.0): "turn right", ("climb", 1.0): "up", ("climb", -1.0): "down"}


def stick_for(frac, width):
    """The stick value that safe_teleop's deadzone() turns into `frac` of top speed (its rescale, inverted)."""
    if frac == 0:
        return 0.0
    return (1.0 if frac > 0 else -1.0) * (width + abs(frac) * (1.0 - width))


def _norm(keysym):
    return str(keysym).lower()        # Shift held turns "w" into "W": still the same key


class KeyState:
    """Which flight keys are down, and the /joy axes they make."""

    def __init__(self, profile="dragonrise_usb", scale=DEFAULT_SCALE, deadzone=DEADZONE):
        self.profile = PROFILES[profile]
        self.scale = scale
        self.deadzone = deadzone
        self._down = set()
        self._released = {}            # key -> release time, cancelled by a press within DEBOUNCE_S
        self._last = {}                # key -> time of its last press or release event

    def press(self, keysym, t):
        k = _norm(keysym)
        if k in SCALES:
            self.scale = SCALES[k]
            return
        if k in KEYS:
            self._settle(t)
            self._down.add(k)
            self._released.pop(k, None)
            self._last[k] = t

    def release(self, keysym, t):
        k = _norm(keysym)
        if k in KEYS and k in self._down:
            self._released[k] = t
            self._last[k] = t

    def all_up(self):
        """Focus lost or window closing: every key counts as released, now."""
        self._down.clear()
        self._released.clear()
        self._last.clear()

    def _settle(self, t):
        for k, tr in list(self._released.items()):
            if t - tr >= DEBOUNCE_S:
                self._down.discard(k)
                del self._released[k]
        for k in list(self._down):
            if t - self._last.get(k, t) >= HOLD_SILENCE_S:
                self._down.discard(k)
                self._released.pop(k, None)

    def sticks(self, t):
        self._settle(t)
        out = {"forward": 0.0, "left": 0.0, "yaw": 0.0, "climb": 0.0}
        for k in self._down:
            stick, sign = KEYS[k]
            out[stick] += sign                       # opposite keys cancel to 0; a key and its alias clamp to 1
        out = {s: max(-1.0, min(1.0, v)) for s, v in out.items()}
        h = (out["forward"] ** 2 + out["left"] ** 2) ** 0.5
        if h > 1.0:                                  # diagonal: same speed as straight (safe_teleop does not cap it)
            out["forward"] /= h
            out["left"] /= h
        return {s: v * self.scale for s, v in out.items()}   # fractions of top speed

    def axes(self, t):
        a = [0.0] * N_AXES
        for stick, v in self.sticks(t).items():
            a[getattr(self.profile, stick + "_axis")] = float(stick_for(v, self.deadzone))
        return a

    def buttons(self):
        return [0] * N_BUTTONS

    def status(self, t):
        st = self.sticks(t)
        held = [WORDS[(s, 1.0 if v > 0 else -1.0)] for s, v in st.items() if v]
        return "%s  ·  %d %% of top speed" % (", ".join(held) or "hold (no key)", round(self.scale * 100))
