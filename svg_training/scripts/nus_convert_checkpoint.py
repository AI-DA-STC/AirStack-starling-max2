"""Convert a partner checkpoint (runner checkpoint or archive entry) into an actor-only archive entry under runs/nus_port/weights/<name>/.

    python scripts/nus_convert_checkpoint.py --checkpoint <folder> --team guard|strike --name <name> \
        [--config-path <config.json>] [--rules configs/local/nus_rules.toml] [--deploy configs/local/nus_deploy.toml]

Writes actor.msgpack (the partner's array encoding, actor parameters only), config.json (verbatim copy) and metadata.json (team,
update, sha256 of the source weights file). The loader accepts the result as an archive entry, and the script reloads it and checks
that both folders give identical actions on a fixed set of random observations. Prints paths and sha256 values, never a value.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "source"))

import msgpack  # noqa: E402
import numpy as np  # noqa: E402
import torch  # noqa: E402

from svg_training.nus.actor import EXT_NDARRAY, NusActor, read_msgpack  # noqa: E402
from svg_training.nus.deploy import LOCAL_DEPLOY, WEIGHTS_DIR, apply_overrides, load_deploy  # noqa: E402
from svg_training.nus.outputs import require_under_runs  # noqa: E402
from svg_training.nus.rules import LOCAL_RULES, file_sha256, load_rules  # noqa: E402

CHECK_ROWS = 2 * 2 * 2 * 2 * 2 * 2  # fixed random observations of the reload check
CHECK_SEED = 0


def pack_tree(node):
    """Re-encode decoded arrays in the partner library's layout (ext type holding shape, dtype name, C-order bytes)."""
    if isinstance(node, dict):
        return {k: pack_tree(v) for k, v in node.items()}
    array = np.asarray(node)  # not ascontiguousarray: it would turn a scalar into a vector
    return msgpack.ExtType(EXT_NDARRAY, msgpack.packb((list(array.shape), array.dtype.name, array.tobytes("C")), use_bin_type=True))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument("--team", required=True, choices=("guard", "strike"))
    parser.add_argument("--name", required=True)
    parser.add_argument("--config-path", type=Path)
    parser.add_argument("--rules", type=Path, default=LOCAL_RULES)
    parser.add_argument("--deploy", type=Path, default=LOCAL_DEPLOY)
    args = parser.parse_args(argv)
    deploy = load_deploy(args.deploy)
    rules = apply_overrides(load_rules(args.rules), deploy)
    source = NusActor.load(args.checkpoint, team=args.team, rules=rules, deploy=deploy, config_path=args.config_path)
    out = require_under_runs(WEIGHTS_DIR / args.name)
    out.mkdir(parents=True, exist_ok=True)
    weights_file = args.checkpoint / ("state.msgpack" if source.meta["format"] == "runner" else "actor.msgpack")
    raw = read_msgpack(weights_file)
    params = raw["runner"]["policy"]["actor_params"] if source.meta["format"] == "runner" else raw["actor_params"]
    tree = {"actor_params": pack_tree(params), "update": pack_tree(np.asarray(source.meta["update"], np.int32)),
            "action_mode": "deterministic"}
    (out / "actor.msgpack").write_bytes(msgpack.packb(tree, use_bin_type=True))
    shutil.copyfile(args.config_path or args.checkpoint / "config.json", out / "config.json")
    (out / "metadata.json").write_text(json.dumps({"team": args.team, "update": source.meta["update"], "source_format": source.meta["format"],
                                                    "source_sha256": source.meta["sha256"], "source_path": str(args.checkpoint)}, indent=2) + "\n")
    converted = NusActor.load(out, team=args.team, rules=rules, deploy=deploy)
    gen = torch.Generator().manual_seed(CHECK_SEED)
    obs = torch.randn(CHECK_ROWS, source.team_size, source.obs_dim, generator=gen)
    if not torch.equal(source.act_units(obs), converted.act_units(obs)):
        raise SystemExit("converted folder does not reproduce the source actor")
    print(f"wrote {out}")
    print(f"source sha256: {source.meta['sha256']}")
    print(f"actor.msgpack sha256: {file_sha256(out / 'actor.msgpack')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
