#!/usr/bin/env python3
"""Sim-airframe marker check: every `param set-default` line is labelled = real / SIM-ONLY and the label is true.

The rule is docs/CODING_STANDARD.md section 4. Markers sit at the END of the line:
  # = real
  # SIM-ONLY (real <v>) CHG-nnnn
  # SIM-ONLY (no real value) CHG-nnnn
Values are compared as floats (relative tolerance 1e-6), so 3e+01 equals 30.
  python3 tools/lib/airframe_params.py --check   # errors, exit 1
  python3 tools/lib/airframe_params.py --table   # name, sim value, real value, marker
"""
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
AIRFRAME = "AirStack/simulation/isaac-sim/px4/airframes/10090_pegasus_starling2max"
REAL_PARAMS = "starling_1_indoor_params.params"

_LINE = re.compile(r"^\s*param set-default\s+(\S+)\s+(\S+)")
_REAL = re.compile(r"#\s*= real\s*$")
_SIM = re.compile(r"#\s*SIM-ONLY \(real (\S+)\) (CHG-\d{4})\s*$")
_NOREAL = re.compile(r"#\s*SIM-ONLY \(no real value\) (CHG-\d{4})\s*$")


@dataclass
class Line:
    no: int
    name: str
    value: float
    marker: "str | None"      # real | sim | sim-noreal | None
    real: "float | None"
    chg: "str | None"


def parse_real(text):
    out = {}
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        f = raw.split("\t")
        if len(f) >= 4:
            out[f[2]] = float(f[3])
    return out


def parse_airframe(text):
    lines = []
    for no, raw in enumerate(text.splitlines(), 1):
        m = _LINE.match(raw)
        if not m:
            continue
        marker = real = chg = None
        if _REAL.search(raw):
            marker = "real"
        elif (s := _SIM.search(raw)):
            marker, real, chg = "sim", float(s.group(1)), s.group(2)
        elif (s := _NOREAL.search(raw)):
            marker, chg = "sim-noreal", s.group(1)
        lines.append(Line(no, m.group(1), float(m.group(2)), marker, real, chg))
    return lines


def same(a, b):
    return abs(a - b) <= 1e-6 * max(abs(a), abs(b))


def changes_ids(text):
    return set(re.findall(r"^\| (CHG-\d{4}) \|", text, re.M))


def check_markers(airframe_text, real, known_ids):
    errs = []
    for l in parse_airframe(airframe_text):
        at = f"line {l.no} {l.name}"
        have = real.get(l.name)
        if l.marker is None:
            errs.append(f"{at}: no marker (value {l.value:g})")
        elif l.marker == "real":
            if have is None:
                errs.append(f"{at}: '= real' but the drone's file has no {l.name}")
            elif not same(l.value, have):
                errs.append(f"{at}: '= real' but sim {l.value:g} != drone {have:g}")
        elif l.marker == "sim":
            if have is None:
                errs.append(f"{at}: 'SIM-ONLY (real {l.real:g})' but the drone's file has no {l.name}")
            elif not same(l.real, have):
                errs.append(f"{at}: marker says real {l.real:g} but the drone's file has {have:g}")
            elif same(l.value, have):
                errs.append(f"{at}: value {l.value:g} equals the drone's; the marker must be '= real'")
        else:
            if have is not None:
                errs.append(f"{at}: 'no real value' but the drone's file has {have:g}")
        if l.chg and l.chg not in known_ids:
            errs.append(f"{at}: unknown change id {l.chg}")
    return errs


def main(argv):
    real = parse_real((REPO / REAL_PARAMS).read_text())
    text = (REPO / AIRFRAME).read_text()
    if "--table" in argv:
        for l in parse_airframe(text):
            r = real.get(l.name)
            print(f"{l.name}\t{l.value:g}\t{'-' if r is None else format(r, 'g')}\t{l.marker}")
        return 0
    errs = check_markers(text, real, changes_ids((REPO / "docs/record/CHANGES.md").read_text()))
    for e in errs:
        print(e)
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
