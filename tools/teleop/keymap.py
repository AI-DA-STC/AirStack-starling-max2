"""Keyboard -> a gamepad's /joy stream, so CMU's safe_teleop flies the drone unchanged (NEAR-789, sim only).

Pure logic, no ROS and no Tk: key_teleop.py feeds it key events and publishes what it returns.

    Up / Down      forward / back = pitch   (right stick up / down)
    Left / Right   slide left / right = roll (right stick left / right)
    W / S          climb / descend          (left stick up / down)
    A / D          turn (yaw) left / right  (left stick left / right)
    Space          STOP: every key let go
    F              ask the relay to flip Drive mode <-> Room mode, once per press (this module never changes the frame)
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
}
WORDS = {("forward", 1.0): "pitch: forward", ("forward", -1.0): "pitch: back",
         ("left", 1.0): "roll: slide left", ("left", -1.0): "roll: slide right",
         ("yaw", 1.0): "turn (yaw) left", ("yaw", -1.0): "turn (yaw) right",
         ("climb", 1.0): "climb", ("climb", -1.0): "descend"}
STOP_SHOWN_S = 1.0
GREY, GREEN, BLUE, AMBER, RED = "#6b7280", "#0a7a3c", "#1d4ed8", "#b45309", "#B00020"


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
        self.flip_requested = False    # F pressed; the window asks the relay, then clears this
        self._f_last = None            # time of the last F event (press or release); None = F is up
        self._f_rel = None             # time of the last F release, None after a press
        self.stop_at = None            # time of the last Space

    def press(self, keysym, t):
        k = _norm(keysym)
        if k in SCALES:
            self.scale = SCALES[k]
            return
        if k == "space":
            self.all_up()
            self.stop_at = t
            return
        if k == "f":                       # one request per real press: a held F auto-repeats (final review 1)
            if not self._f_held(t):
                self.flip_requested = True
            self._f_last, self._f_rel = t, None
            return
        if k in KEYS:
            self.stop_at = None            # a new flight key ends the STOP display
            self._settle(t)
            self._down.add(k)
            self._released.pop(k, None)
            self._last[k] = t

    def release(self, keysym, t):
        k = _norm(keysym)
        if k == "f" and self._f_last is not None:
            self._f_last = self._f_rel = t
            return
        if k in KEYS and k in self._down:
            self._released[k] = t
            self._last[k] = t

    def all_up(self):
        """Focus lost or window closing: every key counts as released, now."""
        self._down.clear()
        self._released.clear()
        self._last.clear()
        self._f_last = self._f_rel = None

    def _f_held(self, t):
        """F still down: released less than DEBOUNCE_S ago (an auto-repeat pair), or an event within HOLD_SILENCE_S."""
        if self._f_last is None:
            return False
        if self._f_rel is not None:
            return t - self._f_rel < DEBOUNCE_S
        return t - self._f_last < HOLD_SILENCE_S

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
            out[stick] += sign                       # opposite keys cancel to 0; a repeated key clamps to 1
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

    def status(self, t, max_speed_mps=None):
        if self.stop_at is not None and t - self.stop_at < STOP_SHOWN_S:
            words = "STOP"
        else:
            st = self.sticks(t)
            held = [WORDS[(s, 1.0 if v > 0 else -1.0)] for s, v in st.items() if v]
            words = ", ".join(held) or "hold (no key)"
        out = "%s  ·  %d %% of top speed" % (words, round(self.scale * 100))
        if max_speed_mps is not None:
            out += " = %.1f m/s" % (self.scale * max_speed_mps)
        return out


def parse_status(line):
    """The relay's `key=value ...` status line as a dict; numbers become floats (nan stays nan)."""
    out = {}
    for tok in str(line).split():
        if "=" in tok:
            k, v = tok.split("=", 1)
            if k in ("heading_deg", "heading_age_s"):
                try:
                    v = float(v)
                except ValueError:
                    v = float("nan")
            out[k] = v
    return out


_ROOM = ("Room mode — ↑ is always the far wall", "Like moving a chess piece: ↑ is the far wall no matter where the nose points.")
_DRIVE = ("Drive mode — ↑ is always where the nose points", "Like driving a car: turn with A / D, then ↑ goes that way.")


def header_lines(status, relay_seen):
    """(bold line, sentence, colour) for the window header; wording is spec 5.4 (words only)."""
    if status is None or not relay_seen or status.get("frame") not in ("body", "world"):
        return ("Keys not reaching the drone — close this window, then run tools/sim.sh keys", "", RED)
    if status.get("input") == "none":
        return _ROOM + (GREY,)
    if status.get("guard", "ok") != "ok":
        return ("Heading lost — let go of the keys", "The drone holds until the heading is back and every key is up.", RED)
    pending = status.get("pending", "none")
    if pending != "none":
        name = "room" if pending == "world" else "drive"
        return ("Switching to %s mode — let go of the keys first" % name,
                "Your ↑ still works the old way until every key is up.", AMBER)
    if status.get("frame") == "world":
        return _ROOM + (BLUE,)
    return _DRIVE + (GREEN,)


def flip_target(status):
    """The mode F asks for: the other one, measured from the pending target if a flip is waiting (so a second F
    cancels it). None when there is no usable status or the relay has no input (nothing to flip)."""
    if status is None or status.get("input") == "none" or status.get("frame") not in ("body", "world"):
        return None
    pending = status.get("pending", "none")
    effective = pending if pending in ("body", "world") else status["frame"]
    return "body" if effective == "world" else "world"


def footer_line(status):
    base = "A / D turn · W / S up / down · Space STOP"
    target = flip_target(status)
    if target is None:
        return base
    return base + (" · F → drive mode" if target == "body" else " · F → room mode")


def export_tables():
    """Every table the Foxglove strip needs, as plain JSON types (NEAR-789). Derived from the code above, so the
    wording and numbers exist once; tools/teleop/foxglove/gen_keymap.py writes this into the extension."""
    rooms = header_lines({"frame": "world", "input": "ok"}, True)
    lines = {
        "relay_lost": list(header_lines(None, False)),
        "room_idle": list(header_lines({"frame": "world", "input": "none"}, True)),
        "heading_lost": list(header_lines({"frame": "body", "guard": "lost"}, True)),
        "switch_room": list(header_lines({"frame": "body", "pending": "world"}, True)),
        "switch_drive": list(header_lines({"frame": "world", "pending": "body"}, True)),
        "room": list(rooms),
        "drive": list(header_lines({"frame": "body", "input": "ok"}, True)),
    }
    return {
        "keys": {k: [stick, d] for k, (stick, d) in KEYS.items()},
        "words": {"%s:%d" % (stick, int(d)): w for (stick, d), w in WORDS.items()},
        "scales": dict(SCALES),
        "default_scale": DEFAULT_SCALE,
        "deadzone": DEADZONE,
        "debounce_s": DEBOUNCE_S,
        "hold_silence_s": HOLD_SILENCE_S,
        "n_axes": N_AXES,
        "n_buttons": N_BUTTONS,
        "profiles": {n: {"forward_axis": p.forward_axis, "left_axis": p.left_axis, "climb_axis": p.climb_axis,
                         "yaw_axis": p.yaw_axis, "lock_button": p.lock_button} for n, p in PROFILES.items()},
        "lines": lines,
        "footer": {"base": footer_line(None),
                   "drive": footer_line({"frame": "world", "input": "ok"})[len(footer_line(None)):],
                   "room": footer_line({"frame": "body", "input": "ok"})[len(footer_line(None)):]},
        "stop_shown_s": STOP_SHOWN_S,
    }


if __name__ == "__main__":
    import json
    import sys
    if "--dump-json" in sys.argv[1:]:
        print(json.dumps(export_tables(), sort_keys=True, indent=2, ensure_ascii=False))
