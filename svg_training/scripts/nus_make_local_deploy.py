"""Write the git-ignored local deploy file (G1): the owner's scale and hold length, the checkpoint's geometry overrides, and the
constants that sit in the partner's actor and scripted-controller code.

    python scripts/nus_make_local_deploy.py --clone <partner clone> --geometry-from <checkpoint folder or config.json> \
        --metres-per-unit <m> --seconds-per-step <s> --hold-ticks <k> --flying-height-m <m> \
        --guard-weights <name> --strike-weights <name> --out configs/local/nus_deploy.toml [--same-as configs/local/nus_deploy.toml]

``--out`` must lie under configs/local/ (refused otherwise). ``--same-as`` (Phase 4: the reference deploy file) refuses a file whose keys, other
than the two weights folders, differ from the given one.

The script prints the output path, the key names and the sha256 of the file, never a value. The owner's numbers are command-line
arguments of this run only; they are written nowhere but the local file.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "source"))

from nus_cfg import read_policy_constants  # noqa: E402
from svg_training.nus.deploy import DEPLOY_KEYS, STRING_KEYS, load_deploy  # noqa: E402
from svg_training.nus.rules import ROOT, file_sha256  # noqa: E402

LOCAL_OUT_DIR = ROOT / "configs" / "local"  # the only folder a deploy file may be written to (it is git-ignored); tests patch it
WEIGHT_KEYS = ("guard_weights", "strike_weights")


def geometry_from(source: Path) -> dict[str, float]:
    """The checkpoint's two geometry settings (its config.json physics block)."""
    config = source / "config.json" if source.is_dir() else source
    physics = json.loads(config.read_text())["environment"]["env"]["physics"]
    return {"spawn_distance": float(physics["spawn_distance"]), "guard_boundary_radius": float(physics["defender_boundary"])}


def build_deploy(args: argparse.Namespace) -> dict:
    values = {"metres_per_unit": float(args.metres_per_unit), "seconds_per_step": float(args.seconds_per_step),
              "hold_ticks": int(args.hold_ticks), "flying_height_m": float(args.flying_height_m),
              **geometry_from(args.geometry_from), **read_policy_constants(args.clone),
              "guard_weights": args.guard_weights, "strike_weights": args.strike_weights}
    missing = [k for k in DEPLOY_KEYS if k not in values]
    if missing:
        raise KeyError(f"deploy keys without a source: {missing}")
    return values


def write_deploy_file(path: Path, values: dict) -> None:
    lines = ["# Local deploy values of the partner policy. Git-ignored. Written by scripts/nus_make_local_deploy.py; never copy into a tracked file."]
    for key in DEPLOY_KEYS:
        v = values[key]
        lines.append(f'{key} = "{v}"' if key in STRING_KEYS else f"{key} = {v!r}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clone", required=True, type=Path)
    parser.add_argument("--geometry-from", required=True, type=Path, help="checkpoint folder or its config.json")
    parser.add_argument("--metres-per-unit", required=True)
    parser.add_argument("--seconds-per-step", required=True)
    parser.add_argument("--hold-ticks", required=True)
    parser.add_argument("--flying-height-m", required=True)
    parser.add_argument("--guard-weights", required=True)
    parser.add_argument("--strike-weights", required=True)
    parser.add_argument("--out", required=True, type=Path, help="must lie under configs/local/")
    parser.add_argument("--same-as", type=Path, help="refuse unless every key but the two weights folders equals this deploy file's")
    args = parser.parse_args(argv)
    out_dir = LOCAL_OUT_DIR.resolve()
    if out_dir not in (args.out.resolve(), *args.out.resolve().parents):
        raise SystemExit(f"refusing: --out must lie under {out_dir} (the git-ignored local folder)")
    values = build_deploy(args)
    if args.same_as is not None:
        reference = load_deploy(args.same_as)
        differing = [k for k in DEPLOY_KEYS if k not in WEIGHT_KEYS and getattr(reference, k) != values[k]]
        if differing:
            raise SystemExit(f"refusing: keys differ from {args.same_as.name}: {differing}")
    write_deploy_file(args.out, values)
    load_deploy(args.out)  # refuses an inconsistent file
    print(f"wrote {args.out}")
    print(f"keys: {', '.join(DEPLOY_KEYS)}")
    print(f"sha256: {file_sha256(args.out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
