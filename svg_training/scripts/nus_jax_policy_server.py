"""Action worker for the outcome run. Run in the partner's JAX environment (``nus_jax``), CPU only:

    unset PYTHONPATH; PYTHONNOUSERSITE=1 JAX_PLATFORMS=cpu WANDB_MODE=disabled ~/miniconda3/envs/nus_jax/bin/python \
        scripts/nus_jax_policy_server.py --clone <partner clone> --checkpoint <folder> --team guard|strike

Reads observation arrays [N, team size, obs width] from standard input (numpy's array format, one frame each) and answers each with the
partner's deterministic actions [N, team size, 2] (float32, in the checkpoint's own compute dtype) on standard output, until the input
ends. Everything else the process prints goes to standard error, so the answer stream stays clean. The outcome run
(scripts/nus_outcome_parity.py, a PyTorch process) starts it as a child process.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402

from nus_jax_common import deterministic_actions, load_actor, read_frame, write_frame  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clone", required=True, type=Path)
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument("--team", required=True, choices=("guard", "strike"))
    args = parser.parse_args(argv)
    stdin, stdout = sys.stdin.buffer, sys.stdout.buffer
    sys.stdout = sys.stderr  # nothing but frames may reach the answer stream
    import jax.numpy as jnp

    bundle = load_actor(args.clone, args.checkpoint, args.team)
    while (frame := read_frame(stdin)) is not None:
        write_frame(stdout, np.asarray(deterministic_actions(bundle, jnp.asarray(frame, jnp.float32)), np.float32))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
