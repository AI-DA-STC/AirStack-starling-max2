#!/usr/bin/env python
"""Write the tier 2 physics drone's parameter file: PX4 gains copied from the drone's own file, never tuned.

  make_physics_params.py --params-file ../starling_1_indoor_params.params --out params/starling_physics_v0.toml

Reads a QGC parameter file ("vehicle component NAME value type" lines, read-only) and writes a TOML file with
  [source]    the drone file's path (relative to svg_training/), sha256, last git commit touching it, today's date;
  [gains]     every name in Px4Gains (models/physics_params.py), the value text copied verbatim from the drone file;
  [airframe]  CMU's system identification of the Starling 2 Max, typed in below (../docs/CONFIG.md "Inertials");
  [model]     the plan's backend defaults (D4-D7, D10); configs/s2b.toml [physics] overrides them at run time.
Exit 2, writing nothing, if any listed name is missing from the drone file. Numbers flow from the drone, never back:
this script never writes a drone file, and the result holds no sim-only airframe value (iron rule 9).
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
from svg_training.models.physics_params import GAIN_NAMES, load_physics_params  # noqa: E402

HEADER = "# Tier 2 rigid-body Starling, version 0. Gains copied from the drone, never tuned."
INERTIALS = 'MEASURED ../docs/CONFIG.md "Inertials" / CMU sys-ID PDF'
MOTORS = 'MEASURED ../docs/CONFIG.md "Thrust / motors" / CMU sys-ID PDF'
TIME_CONSTANT = ('MEASURED CMU sys-ID PDF "Time Constant" (../isaac_sim/, step response; '
                 '../docs/CONFIG.md quotes only their 72 ms mean)')
CAD = 'MEASURED ../docs/CONFIG.md "Rotor geometry" (CMU CAD; sim airframe 10090, same order and signs as CA_ROTOR*)'

# (key, TOML value text, comment). CMU system identification of the Starling 2 Max
# (../isaac_sim/Starling 2 Max Sys ID Results - Slite.pdf, as summarised in ../docs/CONFIG.md).
AIRFRAME: tuple[tuple[str, str, str], ...] = (
    ("mass_kg", "0.557", f"kg, body 477 g + 4 x 20 g rotors. {INERTIALS}"),
    ("inertia_kgm2", "[0.002943, 0.001857, 0.004649]", f"kg m^2, roll / pitch / yaw. {INERTIALS}"),
    ("k_f", "3.964738e-6", f"N/(rad/s)^2, rotor thrust. {MOTORS}"),
    ("k_m", "5.38697e-8", f"N m/(rad/s)^2, rotor drag torque. {MOTORS}"),
    ("omega_max_rad_s", "1450.0", f"rad/s, full rotor speed. {MOTORS}"),
    ("tau_up_s", "0.055", f"s, rotor-speed lag speeding up. {TIME_CONSTANT}"),
    ("tau_down_s", "0.085", f"s, rotor-speed lag slowing down. {TIME_CONSTANT}"),
    ("rotor_xy_cad_m", "[[0.095, 0.13], [-0.095, -0.13], [0.095, -0.13], [-0.095, 0.13]]",
     f"m, (x fwd, y right) FRD, rotors 0..3. {CAD}"),
)

MODEL = (
    "[model]                                   # backend defaults (S2b plan); configs/s2b.toml [physics] overrides them\n"
    "physics_dt_s = 0.005                      # D6: 200 Hz, 10 physics steps per 0.05 s game tick\n"
    "rotor_geometry = \"cad\"                    # D4: plant rotor positions; PX4's allocation always uses [gains] CA_ROTOR*\n"
    "motor_lag = true                          # D5: first-order rotor-speed lag (tau_up_s / tau_down_s)\n"
    "setpoint_delay_s = 0.0                    # D7: no transport delay, no estimator\n"
    "upset_tilt_deg = 60.0                     # D10: tilt past this (or a non-finite state) is an upset\n")


def read_qgc_params(path: Path) -> dict[str, str]:
    """QGC parameter file -> {NAME: value text as written}. Comment and malformed lines are skipped."""
    out: dict[str, str] = {}
    for line in path.read_text().splitlines():
        parts = line.split()
        if len(parts) == 5 and not line.lstrip().startswith("#"):
            out[parts[2]] = parts[3]
    return out


def git_commit(path: Path) -> str:
    """Short hash of the last commit touching `path`, with '+dirty' if it has uncommitted changes; 'none' if untracked."""
    try:
        h = subprocess.run(["git", "-C", str(path.parent), "log", "-1", "--format=%h", "--", path.name],
                           capture_output=True, text=True, timeout=30).stdout.strip()
        dirty = subprocess.run(["git", "-C", str(path.parent), "status", "--porcelain", "--", path.name],
                               capture_output=True, text=True, timeout=30).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "none"
    if not h:
        return "none"
    return h + ("+dirty" if dirty else "")


def toml_number(text: str) -> str:
    """The drone's value text if TOML reads it as a number, else its float repr (same value)."""
    import tomllib
    try:
        float(tomllib.loads(f"v = {text}")["v"])
        return text
    except (tomllib.TOMLDecodeError, TypeError, ValueError):
        return repr(float(text))


def render(params_file: Path, values: dict[str, str]) -> str:
    rel = os.path.relpath(params_file.resolve(), ROOT)
    sha = hashlib.sha256(params_file.read_bytes()).hexdigest()
    lines = [HEADER,
             "# Written by scripts/make_physics_params.py; do not edit by hand (re-run the script).",
             "# Read by source/svg_training/models/physics_params.py (load_physics_params).",
             "# Units: SI, except [gains], which keep PX4's own units (deg, deg/s, Hz) and names (lower case).",
             "",
             "[source]",
             f'path = "{rel}"',
             f'sha256 = "{sha}"',
             f'git_commit = "{git_commit(params_file.resolve())}"',
             f'date = "{datetime.date.today().isoformat()}"',
             "",
             "[gains]                                   # the drone's PX4 1.14 parameters, value text copied verbatim"]
    for name in GAIN_NAMES:
        key = f"{name.lower()} = {toml_number(values[name])}"
        lines.append(f"{key:<41} # MEASURED {rel} {name}")
    lines += ["", "[airframe]                                # CMU system identification of the Starling 2 Max"]
    for key, val, comment in AIRFRAME:
        lines.append(f"{key + ' = ' + val:<41} # {comment}")
    lines += ["", MODEL.rstrip("\n")]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--params-file", required=True, type=Path, help="the drone's QGC parameter file (read-only)")
    ap.add_argument("--out", required=True, type=Path, help="parameter TOML to write")
    a = ap.parse_args(argv)
    if not a.params_file.is_file():
        print(f"error: no such file {a.params_file}", file=sys.stderr)
        return 2
    values = read_qgc_params(a.params_file)
    missing = [n for n in GAIN_NAMES if n not in values]
    if missing:
        print(f"error: {a.params_file} lacks {len(missing)} listed name(s): {', '.join(missing)}; nothing written",
              file=sys.stderr)
        return 2
    text = render(a.params_file, values)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    tmp = a.out.with_suffix(a.out.suffix + ".tmp")
    tmp.write_text(text)
    try:
        p = load_physics_params(tmp.resolve())         # the written file must load as written
    except Exception:
        tmp.unlink()
        raise
    tmp.replace(a.out)
    print(f"wrote {a.out}: {len(GAIN_NAMES)} gains from {a.params_file} (sha256 {p.source['sha256'][:16]}), "
          f"f_max {p.airframe.f_max_n():.5f} N, hover command {p.airframe.hover_u():.5f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
