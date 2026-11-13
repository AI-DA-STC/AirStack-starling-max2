"""tools/teleop/pad_core.py — every decision of the real-drone pad check, pure Python (stdlib only, no ROS).

The shell `pad_check.py` (in the robot container) gathers the facts — /proc/bus/input/devices, the sysfs driver link,
joy_node's log, /joy samples, the ROS graph — and asks this module for a verdict. Fail closed: anything unknown,
unreadable or ambiguous is a FAIL with its reason. Only the Logitech F310 in X mode is known (profile xbox_usb).
"""
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

MOVE = 0.5          # an axis this far from rest = the operator moved something
FULL = 0.8          # a full push reads at least this, profile sign applied
STICK_REST = 0.15   # stick axes at rest
TRIGGER_REST = 0.95 # triggers rest at +1.0
HAT_REST = 0.01     # D-pad axes at rest
PASS_LINE = "PAD CHECK: PASS — do not press MODE from now on"
NUMBER_WORDS = {2: "two", 3: "three", 4: "four"}


@dataclass(frozen=True)
class PadSpec:
    name: str
    profile: str
    usb: Tuple[str, str]
    driver: str
    sdl_name: str
    n_axes: int
    n_buttons: int
    trigger_axes: Tuple[int, ...]
    hat_axes: Tuple[int, ...]
    wrong_modes: Dict[Tuple[str, str], str] = field(default_factory=dict)


F310 = PadSpec(
    name="f310", profile="xbox_usb", usb=("046d", "c21d"), driver="xpad", sdl_name="Logitech Gamepad F310",
    n_axes=8, n_buttons=11, trigger_axes=(2, 5), hat_axes=(6, 7),
    wrong_modes={("046d", "c216"): "046d:c216 = D mode — flip the switch on the back of the pad to X"})
PADS = {F310.name: F310}


@dataclass(frozen=True)
class Verdict:
    ok: bool
    text: str
    data: object = None

    def line(self) -> str:
        return ("PASS " if self.ok else "FAIL ") + self.text


@dataclass(frozen=True)
class Step:
    name: str                 # what the operator is asked to do, e.g. "right stick UP"
    kind: str                 # "axis" or "button"
    index: int
    sign: float = 1.0
    stick: Optional[str] = None   # "right" / "left" for axis steps
    same_stick: Tuple[int, ...] = ()   # both axes of that stick


def ok(text, data=None):
    return Verdict(True, text, data)


def bad(text, data=None):
    return Verdict(False, text, data)


def fail_line(reason: str) -> str:
    return "PAD CHECK: FAIL — do not fly: " + reason


def load_jsonl(text: str) -> List[dict]:
    """JSON lines; blank lines and lines starting with # are skipped (fixture comments)."""
    return [json.loads(l) for l in text.splitlines() if l.strip() and not l.lstrip().startswith("#")]


# ---------------------------------------------------------------------------------------------------- static: USB
def parse_input_devices(text: str) -> List[dict]:
    """/proc/bus/input/devices -> [{bus, vendor, product, version, name, handlers, sysfs}]; # lines ignored."""
    out, cur = [], None
    for raw in text.splitlines() + [""]:
        line = raw.rstrip()
        if line.startswith("#"):
            continue
        if not line:
            if cur is not None:
                out.append(cur)
            cur = None
            continue
        if line.startswith("I: "):
            cur = {"bus": "", "vendor": "", "product": "", "version": "", "name": "", "handlers": [], "sysfs": ""}
            for kv in line[3:].split():
                k, _, v = kv.partition("=")
                if k.lower() in cur:
                    cur[k.lower()] = v.lower()
        elif cur is None:
            continue
        elif line.startswith("N: Name="):
            cur["name"] = line[len("N: Name="):].strip().strip('"')
        elif line.startswith("H: Handlers="):
            cur["handlers"] = line[len("H: Handlers="):].split()
        elif line.startswith("S: Sysfs="):
            cur["sysfs"] = line[len("S: Sysfs="):].strip()
    return [d for d in out if d["vendor"] and d["product"]]


def js_of(dev: dict) -> Optional[str]:
    js = [h for h in dev.get("handlers", []) if h.startswith("js") and h[2:].isdigit()]
    return js[0] if len(js) == 1 else None


def judge_usb(devs: Sequence[dict], spec: PadSpec = F310):
    """-> ([Verdict], js or None). First verdict = the pad; then one line for the other joystick devices."""
    usb = tuple(spec.usb)
    pads = [d for d in devs if (d["vendor"], d["product"]) == usb]
    wrong = [d for d in devs if (d["vendor"], d["product"]) in spec.wrong_modes]
    n = len(pads) + len(wrong)
    if n > 1:
        return [bad("ambiguous — %s F310 pads, unplug one" % NUMBER_WORDS.get(n, str(n)))], None
    if wrong:
        return [bad(spec.wrong_modes[(wrong[0]["vendor"], wrong[0]["product"])])], None
    if not pads:
        return [bad("F310 not found — plug it in")], None
    pad = pads[0]
    js = js_of(pad)
    if js is None:
        return [bad("F310 %s:%s has no joystick device (handlers %s) — unplug it and plug it in again"
                    % (usb[0], usb[1], " ".join(pad["handlers"]) or "none"))], None
    v = [ok('usb %s:%s "%s" %s (X mode)' % (usb[0], usb[1], pad["name"], js))]
    others = [d for d in devs if d is not pad and js_of(d)]
    for d in others:
        if d["name"] == spec.sdl_name:
            return v + [bad('%s "%s" also carries the pinned name — unplug it' % (js_of(d), d["name"]))], None
    if others:
        v.append(ok("others " + ", ".join('%s "%s"' % (js_of(d), d["name"]) for d in others) + " ignored — not the pinned name"))
    else:
        v.append(ok("others none"))
    return v, js


def judge_driver(name: Optional[str], spec: PadSpec = F310) -> Verdict:
    if not name:
        return bad("driver unreadable — cannot confirm X mode")
    if name != spec.driver:
        return bad("driver %s — cannot confirm X mode" % name)
    return ok("driver " + name)


# ---------------------------------------------------------------------------------------------------- static: joy_node
def parse_opened_name(log: str) -> Optional[str]:
    """The name joy_node logs as `Opened joystick: <name>.  deadzone: …` (the string device_name must match)."""
    for line in log.splitlines():
        i = line.find("Opened joystick: ")
        if i < 0:
            continue
        rest = line[i + len("Opened joystick: "):]
        j = rest.find("deadzone")
        name = (rest[:j] if j >= 0 else rest).rstrip()
        if name.endswith("."):
            name = name[:-1]
        return name.strip() or None
    return None


def judge_opened(name: Optional[str], spec: PadSpec = F310) -> Verdict:
    if name is None:
        return bad('joy_node opened nothing within 5 s (name pin "%s")' % spec.sdl_name)
    if name != spec.sdl_name:
        return bad('joy_node opened "%s", not the pinned "%s"' % (name, spec.sdl_name))
    return ok('joy_node opened "%s"' % name)


def judge_shape(n_axes: int, n_buttons: int, spec: PadSpec = F310) -> Verdict:
    if (n_axes, n_buttons) != (spec.n_axes, spec.n_buttons):
        return bad("%d axes/%d buttons — not the X-mode layout (%d/%d)" % (n_axes, n_buttons, spec.n_axes, spec.n_buttons))
    return ok("%d axes %d buttons" % (n_axes, n_buttons))


def stick_axes(spec: PadSpec) -> List[int]:
    return [i for i in range(spec.n_axes) if i not in spec.trigger_axes and i not in spec.hat_axes]


def judge_rest(samples: Sequence[dict], spec: PadSpec = F310) -> Verdict:
    """Every sample at rest. data = the mean axes (the baseline the steps are judged against)."""
    if not samples:
        return bad("rest: no /joy sample to judge")
    for s in samples:
        a, b = s["axes"], s["buttons"]
        if len(a) != spec.n_axes or len(b) != spec.n_buttons:
            return bad(judge_shape(len(a), len(b), spec).text)
        for i in stick_axes(spec):
            if abs(a[i]) > STICK_REST:
                return bad("rest: stick axis %d at %+.2f — let go of the sticks" % (i, a[i]))
        for i in spec.trigger_axes:
            if a[i] < TRIGGER_REST:
                return bad("rest: trigger axis %d at %+.2f — let go of the triggers" % (i, a[i]))
        for i in spec.hat_axes:
            if abs(a[i]) > HAT_REST:
                return bad("rest: D-pad axis %d at %+.2f — let go of the D-pad" % (i, a[i]))
        for i, v in enumerate(b):
            if v:
                return bad("rest: button %d held — let go of every button" % i)
    n = len(samples)
    mean = [round(sum(s["axes"][i] for s in samples) / n, 6) for i in range(spec.n_axes)]
    return ok("rest sticks centred, triggers released, D-pad and buttons idle", mean)


# ---------------------------------------------------------------------------------------------------- guided steps
def steps_for(spec: PadSpec, mapping: dict) -> List[Step]:
    """The operator's five moves, from the installed profile's mapping (ControllerProfile.mapping_parameters())."""
    right = (int(mapping["forward_axis"]), int(mapping["left_axis"]))
    left = (int(mapping["climb_axis"]), int(mapping["yaw_axis"]))
    sign = lambda k: float(mapping.get(k, 1.0))
    return [Step("right stick UP", "axis", right[0], sign("forward_sign"), "right", right),
            Step("right stick LEFT", "axis", right[1], sign("left_sign"), "right", right),
            Step("left stick UP", "axis", left[0], sign("climb_sign"), "left", left),
            Step("left stick LEFT", "axis", left[1], sign("yaw_sign"), "left", left),
            Step("press LB", "button", int(mapping["lock_button"]))]


def _axis_dev(s: dict, rest: Sequence[float]) -> List[float]:
    a = s["axes"]
    return [abs(a[i] - rest[i]) if i < len(rest) else abs(a[i]) for i in range(len(a))]


def movement(s: dict, rest: Sequence[float]) -> bool:
    """Any axis more than MOVE from rest, or any button down."""
    return any(d > MOVE for d in _axis_dev(s, rest)) or any(s["buttons"])


def at_rest(s: dict, rest: Sequence[float]) -> bool:
    return all(d <= STICK_REST for d in _axis_dev(s, rest)) and not any(s["buttons"])


def judge_step(step: Step, samples: Sequence[dict], rest: Sequence[float], spec: PadSpec = F310) -> Verdict:
    """Judge one guided move on the peaks of its samples; the dominant axis is the one furthest from rest."""
    peak, at = {}, {}
    pressed = set()
    for s in samples:
        for i, d in enumerate(_axis_dev(s, rest)):
            if d > peak.get(i, -1.0):
                peak[i], at[i] = d, s["axes"][i]
        pressed |= {i for i, v in enumerate(s["buttons"]) if v}
    moved = {i: d for i, d in peak.items() if d > MOVE}
    if not moved and not pressed:
        return bad("NO MOVEMENT on " + step.name)
    if step.kind == "button":
        if pressed == {step.index}:
            return ok("%s: button %d" % (step.name, step.index))
        if pressed:
            return bad("WRONG BUTTON — %s pressed button %s, expected button %d"
                       % (step.name, " + ".join(str(i) for i in sorted(pressed)), step.index))
        dom = max(moved, key=moved.get)
        return bad("WRONG BUTTON — %s moved axis %d%s, expected button %d"
                   % (step.name, dom, " (a trigger)" if dom in spec.trigger_axes else "", step.index))
    if not moved:
        return bad("WRONG BUTTON — %s pressed button %s, expected a stick" % (step.name, " + ".join(str(i) for i in sorted(pressed))))
    dom = max(moved, key=moved.get)
    if dom in spec.hat_axes:
        if step.stick == "left" and not any(i in moved for i in step.same_stick):
            return bad("MODE ON — press MODE (light off) and run again")
        return bad("D-pad — %s moved the D-pad (axis %d); use the %s stick" % (step.name, dom, step.stick))
    if dom in spec.trigger_axes:
        return bad("TRIGGER — %s moved trigger axis %d; let go of the triggers" % (step.name, dom))
    if dom == step.index:
        v = at[dom] * step.sign
        if v >= FULL:
            return ok("%s: axis %d %+.2f" % (step.name, dom, at[dom]))
        if v <= -FULL:
            return bad("INVERTED — %s read axis %d at %+.2f (expected %s); do not fly this pad"
                       % (step.name, dom, at[dom], "+" if step.sign > 0 else "-"))
        return bad("NOT FULL — %s reached axis %d %+.2f (need %+.2f); push it all the way and run again"
                   % (step.name, dom, at[dom], FULL * step.sign))
    if dom in step.same_stick:
        return bad("WRONG AXIS — %s moved axis %d, expected axis %d" % (step.name, dom, step.index))
    if dom in stick_axes(spec):
        other = "left" if step.stick == "right" else "right"
        return bad("SWAPPED STICK — %s moved axis %d (the %s stick); use the %s stick" % (step.name, dom, other, step.stick))
    return bad("WRONG AXIS — %s moved axis %d, expected axis %d" % (step.name, dom, step.index))


def judge_environment(joy_pubs: Sequence[str], nodes: Sequence[str], procs: Sequence[str]) -> Verdict:
    """The ROS graph and the container's processes before the pad check starts its own joy_node."""
    if any("svg_multi_drone_single_domain" in p for p in procs):
        return bad("Isaac Sim running — real teleop refused")
    if joy_pubs:
        return bad("%d publisher(s) on /joy (%s) — stop the teleop pane / close the sim keyboard window (tools/sim.sh relay stop)"
                   % (len(joy_pubs), ", ".join(joy_pubs)))
    if any(n.rstrip("/").split("/")[-1] == "safe_teleop" for n in nodes) or any("safe_teleop" in p for p in procs):
        return bad("safe_teleop running — stick tests would reach the commander")
    return ok("environment nothing else on /joy, no safe_teleop")
