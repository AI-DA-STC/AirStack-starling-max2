"""Write interface.toml (layout id nus_area_denial_v1) into a converted-weights folder under runs/nus_port/weights/.

    python scripts/nus_write_interface.py --team guard|strike --weights-name <name> --clone <partner clone>

Loads the local rules and deploy files and the converted folder, takes the partner commit from the clone (``git rev-parse HEAD``) and
writes ``runs/nus_port/weights/<name>/interface.toml``. Prints the path and its sha256, never a value.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "source"))

from svg_training.nus.actor import NusActor  # noqa: E402
from svg_training.nus.deploy import LOCAL_DEPLOY, WEIGHTS_DIR, apply_overrides, load_deploy  # noqa: E402
from svg_training.nus.interface import build_interface, write_interface  # noqa: E402
from svg_training.nus.rules import LOCAL_RULES, file_sha256, load_rules  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--team", required=True, choices=("guard", "strike"))
    parser.add_argument("--weights-name", required=True)
    parser.add_argument("--clone", required=True, type=Path)
    args = parser.parse_args(argv)
    deploy = load_deploy(LOCAL_DEPLOY)
    rules = apply_overrides(load_rules(LOCAL_RULES), deploy)
    folder = WEIGHTS_DIR / args.weights_name
    actor = NusActor.load(folder, team=args.team, rules=rules, deploy=deploy)
    commit = subprocess.run(["git", "-C", str(args.clone), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    out = write_interface(folder / "interface.toml", build_interface(args.team, rules, deploy, actor.meta, commit))
    print(f"wrote {out}\nsha256: {file_sha256(out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
