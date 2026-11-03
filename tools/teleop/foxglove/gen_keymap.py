#!/usr/bin/env python3
"""Write keymap.py's tables into the Foxglove extension and build the test fixtures (NEAR-789, sim only).

    python3 tools/teleop/foxglove/gen_keymap.py          rewrite the KEYMAP block and test/fixtures.json
    python3 tools/teleop/foxglove/gen_keymap.py --check  exit 1 if either differs from what keymap.py makes

Only the text between `// KEYMAP:BEGIN` and `// KEYMAP:END` is replaced; the rest of extension.js is hand-written.
The fixtures come from the real KeyState / header_lines / footer_line / flip_target, so the JS can be proved equal.
"""
import argparse
import itertools
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import keymap as K  # noqa: E402

EXT = HERE / "svg-teleop" / "dist" / "extension.js"
FIX = HERE / "svg-teleop" / "test" / "fixtures.json"
BEGIN, END = "// KEYMAP:BEGIN", "// KEYMAP:END"
T_PRESS, T_READ = 1.0, 1.01       # well inside DEBOUNCE_S and HOLD_SILENCE_S: Python's timing plays no part


def block():
    return "%s\nconst TABLES = %s;\n%s" % (BEGIN, json.dumps(K.export_tables(), sort_keys=True, ensure_ascii=False), END)


def axes_case(held, scale, profile, deadzone, space=False):
    st = K.KeyState(profile=profile, scale=scale, deadzone=deadzone)
    for k in held:
        st.press(k, T_PRESS)
    if space:
        st.press("space", T_PRESS)
    case = {"held": list(held), "scale": scale, "profile": profile, "deadzone": deadzone}
    if space:
        case["space"] = True
    case["axes"] = st.axes(T_READ)
    return case


def axes_cases():
    keys = list(K.KEYS)
    sets = [[]] + [[k] for k in keys] + [list(c) for c in itertools.combinations(keys, 2)]
    sets += [["up", "right", "w"], ["up", "left", "a", "w"], ["up", "down", "left", "right", "w", "s", "a", "d"],
             ["up", "right", "left"], ["W"], ["Up", "D"]]
    out = []
    for profile in K.PROFILES:
        for scale in sorted(K.SCALES.values()):
            for held in sets:
                out.append(axes_case(held, scale, profile, K.DEADZONE))
        for held in ([["up"], ["up", "right"], ["w", "a"]]):
            out.append(axes_case(held, K.DEFAULT_SCALE, profile, 0.3))
        out.append(axes_case(["up", "w"], K.DEFAULT_SCALE, profile, 0.0))
        for held in (["up"], ["up", "right", "w", "a"]):
            out.append(axes_case(held, K.DEFAULT_SCALE, profile, K.DEADZONE, space=True))
    return out


def status_lines():
    out = [None, "", "garbage", "frame=", "frame=up input=ok", "=body", "frame=body input=ok extra",
           "frame=body input=ok heading_deg=abc", "frame=body input=ok heading_deg=nan heading_age_s=nan",
           "frame=world input=ok heading_deg=12.5 heading_age_s=0.1"]
    for frame, inp, guard, pending in itertools.product(("body", "world"), ("ok", "none"), ("ok", "lost"),
                                                         ("none", "body", "world")):
        out.append("frame=%s input=%s guard=%s pending=%s heading_deg=nan" % (frame, inp, guard, pending))
        out.append("frame=%s input=%s guard=%s pending=%s heading_deg=90.0 heading_age_s=0.2"
                   % (frame, inp, guard, pending))
    out += ["frame=body", "frame=world", "frame=world input=none", "frame=body guard=lost",
            "frame=body pending=world", "frame=world pending=body", "frame=body pending=body",
            "frame=body pending=bogus", "frame=body input=weird guard=weird"]
    return out


def status_cases():
    out = []
    for line in status_lines():
        for seen in (True, False):
            st = K.parse_status(line) if line is not None else None
            out.append({"line": line, "seen": seen, "header": list(K.header_lines(st, seen)),
                        "footer": K.footer_line(st), "flip": K.flip_target(st)})
    return out


def fixtures_text():
    return json.dumps({"axes": axes_cases(), "status": status_cases()}, indent=1, ensure_ascii=False) + "\n"


def replaced(text):
    a, b = text.index(BEGIN), text.index(END) + len(END)
    return text[:a] + block() + text[b:]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--extension", type=pathlib.Path, default=EXT)
    ap.add_argument("--fixtures", type=pathlib.Path, default=FIX)
    a = ap.parse_args(argv)
    want = {a.extension: replaced(a.extension.read_text(encoding="utf-8")), a.fixtures: fixtures_text()}
    stale = [p for p, t in want.items() if not p.exists() or p.read_text(encoding="utf-8") != t]
    if a.check:
        for p in stale:
            print("out of date: %s (run python3 tools/teleop/foxglove/gen_keymap.py)" % p)
        return 1 if stale else 0
    for p in stale:
        p.write_text(want[p], encoding="utf-8")
        print("wrote", p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
