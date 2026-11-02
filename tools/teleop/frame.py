"""BODY/WORLD velocity frame for the sim teleop relay (NEAR-789, sim only — iron rule 9).

Pure logic, no ROS and no Tk: the relay node feeds it the drone heading and the operator's velocity
command and publishes what it returns, so the keyboard flies relative to the drone's nose.

Rotation (BODY -> WORLD), psi = ENU yaw:
    vx_w = vx*cos(psi) - vy*sin(psi)
    vy_w = vx*sin(psi) + vy*cos(psi)        vz and yaw rate pass through.

Guard (BODY mode only; WORLD never trips): the horizontal command is zeroed (vz and yaw rate still pass)
when the latest heading is older than stale_s, or when two consecutive headings differ by more than
jump_rad (wrapped to +-pi). A jump stays latched until the input is centred (|v_xy| < CENTRED_MPS) AND the
heading is fresh and steady again.

A mode flip is applied only when the input is centred; until then it is `pending`. Requesting the current
mode cancels a pending flip.

Status line: frame=<body|world> pending=<body|world|none> heading_deg=<%.1f|nan> heading_age_s=<%.2f|nan>
guard=<ok|stale|jump> input=<ok|none>, heading_deg = 0 at +X, clockwise positive, in [0, 360).
"""
from __future__ import annotations

import math

MODES = ("body", "world")
CENTRED_MPS = 0.05           # |v_xy| below this counts as a centred stick
STALE_S = 0.2                # heading older than this is not trusted
JUMP_RAD = 0.5               # heading change between consecutive samples above this is a glitch
INPUT_SILENT_S = 1.0         # no command for this long reads as input=none


def wrap_pi(a: float) -> float:
    return (a + math.pi) % (2.0 * math.pi) - math.pi


def rotate_body_to_world(vx: float, vy: float, yaw: float) -> tuple[float, float]:
    c, s = math.cos(yaw), math.sin(yaw)
    return vx * c - vy * s, vx * s + vy * c


def yaw_from_quat(x: float, y: float, z: float, w: float) -> float:
    if x * x + y * y + z * z + w * w < 0.5:
        return math.nan
    return math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))


def heading_deg_from_yaw(yaw: float) -> float:
    if math.isnan(yaw):
        return math.nan
    return (-math.degrees(yaw)) % 360.0


class FrameState:
    def __init__(self, mode: str = "body", stale_s: float = STALE_S, jump_rad: float = JUMP_RAD,
                 input_silent_s: float = INPUT_SILENT_S):
        if mode not in MODES:
            raise ValueError(f"unknown mode {mode!r}; expected one of {MODES}")
        self.mode = mode
        self.pending: str | None = None
        self.stale_s = stale_s
        self.jump_rad = jump_rad
        self.input_silent_s = input_silent_s
        self.yaw = math.nan
        self.yaw_t = math.nan
        self.prev_yaw = math.nan
        self.tripped: str | None = None
        self.last_input_t = math.nan
        self.last_input_centred = False

    def _steady(self) -> bool:
        return math.isnan(self.prev_yaw) or abs(wrap_pi(self.yaw - self.prev_yaw)) <= self.jump_rad

    def _fresh(self, t: float) -> bool:
        return not math.isnan(self.yaw_t) and (t - self.yaw_t) <= self.stale_s

    def _try_rearm(self, t: float) -> None:
        if self.tripped == "jump" and self.last_input_centred and self._fresh(t) and self._steady():
            self.tripped = None

    def update_heading(self, yaw: float, t: float) -> None:
        if math.isnan(yaw):
            return
        self.prev_yaw, self.yaw, self.yaw_t = self.yaw, yaw, t
        if not math.isnan(self.prev_yaw) and not self._steady():
            self.tripped = "jump"
        self._try_rearm(t)

    def request_mode(self, mode: str) -> None:
        if mode not in MODES:
            raise ValueError(f"unknown mode {mode!r}; expected one of {MODES}")
        self.pending = None if mode == self.mode else mode

    def command(self, vx: float, vy: float, vz: float, yaw_rate: float,
                t: float) -> tuple[float, float, float, float]:
        self.last_input_t = t
        self.last_input_centred = math.hypot(vx, vy) < CENTRED_MPS
        if self.pending is not None and self.last_input_centred:
            self.mode, self.pending = self.pending, None
        if self.mode == "world":
            return vx, vy, vz, yaw_rate
        self._try_rearm(t)
        if self.tripped is not None or not self._fresh(t):
            return 0.0, 0.0, vz, yaw_rate
        wx, wy = rotate_body_to_world(vx, vy, self.yaw)
        return wx, wy, vz, yaw_rate

    def _guard(self, t: float) -> str:
        if self.mode == "world":
            return "ok"
        if self.tripped is not None:
            return self.tripped
        return "ok" if self._fresh(t) else "stale"

    def status(self, t: float) -> dict:
        age = t - self.yaw_t if not math.isnan(self.yaw_t) else math.nan
        have_input = not math.isnan(self.last_input_t) and (t - self.last_input_t) <= self.input_silent_s
        return {
            "frame": self.mode,
            "pending": self.pending or "none",
            "heading_deg": heading_deg_from_yaw(self.yaw),
            "heading_age_s": age,
            "guard": self._guard(t),
            "input": "ok" if have_input else "none",
        }

    def status_line(self, t: float) -> str:
        s = self.status(t)
        hd = "nan" if math.isnan(s["heading_deg"]) else "%.1f" % s["heading_deg"]
        ag = "nan" if math.isnan(s["heading_age_s"]) else "%.2f" % s["heading_age_s"]
        return (f"frame={s['frame']} pending={s['pending']} heading_deg={hd} heading_age_s={ag} "
                f"guard={s['guard']} input={s['input']}")
