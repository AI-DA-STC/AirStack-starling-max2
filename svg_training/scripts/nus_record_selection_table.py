"""Record a table of the partner's opponent selections for the M4 test (NUS port Phase 5). Run in the partner's JAX environment, CPU:

    cd <svg_training>; unset PYTHONPATH; PYTHONNOUSERSITE=1 JAX_PLATFORMS=cpu ~/miniconda3/envs/nus_jax/bin/python \
        scripts/nus_record_selection_table.py --clone <partner clone> --out tests/data/nus_select_opponents.json

Calls the partner's ``select_opponents`` on archives of alternating teams (generation 1 trains the Guard team), for every
(seed, generation, maximum, recent) case listed by ``--seeds``, ``--generations`` and ``--sizes`` (maximum:recent pairs), and writes the
selected generations only (indices of a synthetic archive; no partner value, no partner code).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("JAX_PLATFORMS", "cpu")
os.environ.setdefault("WANDB_MODE", "disabled")


def archive(last_generation: int) -> list[dict]:
    """Entries of generations 1 .. last_generation; odd generations are Guard entries ("defender"), even ones Strike ("attacker")."""
    return [{"generation": g, "team": "defender" if g % 2 else "attacker"} for g in range(1, last_generation + 1)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clone", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--seeds", required=True, help="comma-separated run seeds")
    parser.add_argument("--generations", required=True, help="comma-separated generations")
    parser.add_argument("--sizes", required=True, help="comma-separated maximum:recent pairs")
    args = parser.parse_args(argv)
    sys.path.insert(0, str(args.clone))
    from ma_skills.runner.ensemble_self_play_runner import select_opponents

    cases = []
    for seed in map(int, args.seeds.split(",")):
        for generation in map(int, args.generations.split(",")):
            team = "defender" if generation % 2 else "attacker"
            for pair in args.sizes.split(","):
                maximum, recent = map(int, pair.split(":"))
                chosen = select_opponents(archive(generation - 1), team=team, generation=generation, seed=seed, maximum=maximum,
                                          recent=recent)
                cases.append({"seed": seed, "generation": generation, "maximum": maximum, "recent": recent,
                              "selected_generations": [e["generation"] for e in chosen]})
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"source": "partner select_opponents (ensemble_self_play_runner.py)", "cases": cases}, indent=1) + "\n")
    print(f"wrote {args.out}: {len(cases)} cases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
