"""Write the git-ignored local rules file from the partner's own configuration (G1).

    python scripts/nus_make_local_rules.py --clone <partner clone> --config <partner config yaml> --out configs/local/nus_rules.toml

The partner's configuration is read at run time; values go only into the local file. The script prints the output path,
the key names and the sha256 of the file, never a value.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "source"))

from nus_cfg import load_environment_cfg, read_code_constants  # noqa: E402
from svg_training.nus.rules import RULE_KEYS, file_sha256  # noqa: E402


def build_rules(env_cfg: dict, consts: dict) -> dict:
    """Map the partner's configuration (their names) to the rule keys (ours). Their yaml wins over constructor defaults."""
    physics = {**consts["constructor_defaults"], **dict(env_cfg.get("env", {}).get("physics", {}))}
    factory = consts["factory"]
    legacy = physics["max_speed"]
    guard_speed = legacy if physics.get("defender_max_speed") is None else physics["defender_max_speed"]
    strike_speed = legacy if physics.get("attacker_max_speed") is None else physics["attacker_max_speed"]
    cap = physics.get("max_total_displacement")
    if cap is None:
        cap = 2 * max(guard_speed, strike_speed)
    steps = physics.get("max_steps", env_cfg.get("max_episode_steps"))
    values = {
        "guard_count": int(env_cfg["num_defenders"]),
        "strike_count": int(env_cfg["num_attackers"]),
        "area_radius": float(physics["area_radius"]),
        "agent_size": float(factory["agent_size"]),
        "spawn_distance": float(physics.get("spawn_distance", factory["spawn_distance"])),
        "spawn_cluster_radius": float(factory["spawn_cluster_radius"]),
        "random_start": str(env_cfg.get("start_mode", "random")) != "static",
        "start_guard_disc_fraction": float(consts["start_guard_disc_fraction"]),
        "start_static_guard_ring_fraction": float(consts["start_static_guard_ring_fraction"]),
        "start_static_strike_cluster_fraction": float(consts["start_static_strike_cluster_fraction"]),
        "guard_max_speed": float(guard_speed),
        "strike_max_speed": float(strike_speed),
        "guard_safety_distance": float(physics["defender_safety_distance"]),
        "strike_safety_distance": float(physics["attacker_safety_distance"]),
        "push_gain": float(physics["repulsion_k"]),
        "push_smoothing_margin": float(physics["repulsion_margin"]),
        "total_displacement_cap": float(cap),
        "guard_boundary_radius": float(physics["defender_boundary"]),
        "boundary_margin": float(physics["boundary_margin"]),
        "episode_steps": int(steps),
        "norm_floor": float(consts["norm_floor"]),
        "obs_direction_floor": float(consts["obs_direction_floor"]),
    }
    missing = [k for k in RULE_KEYS if k not in values]
    if missing:
        raise KeyError(f"rule keys without a source: {missing}")
    return values


def write_rules_file(path: Path, values: dict) -> None:
    lines = ["# Local partner-game rules. Git-ignored. Written by scripts/nus_make_local_rules.py; never copy into a tracked file."]
    for key in RULE_KEYS:
        v = values[key]
        lines.append(f"{key} = {str(v).lower() if isinstance(v, bool) else repr(v)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clone", required=True, type=Path, help="path of the partner clone (read only)")
    parser.add_argument("--config", required=True, type=Path, help="partner config yaml (root config or environment group file)")
    parser.add_argument("--out", required=True, type=Path, help="local rules file to write (under configs/local/)")
    args = parser.parse_args(argv)
    values = build_rules(load_environment_cfg(args.config), read_code_constants(args.clone))
    write_rules_file(args.out, values)
    print(f"wrote {args.out}")
    print(f"keys: {', '.join(RULE_KEYS)}")
    print(f"sha256: {file_sha256(args.out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
