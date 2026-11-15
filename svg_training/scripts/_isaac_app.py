"""Start Isaac Sim headless for an S2b script (the one place outside compat/ that touches Isaac, as S0's
``benchmark_tier2.py``; S2b plan Global Constraints).

    from _isaac_app import start_headless
    args, simulation_app = start_headless(parser)              # parser holds the script's own arguments
    from svg_training.compat import isaaclab_232 as isaac       # only after this point

``start_headless`` adds Isaac Lab's launcher arguments, parses the command line, refuses (exit 2, one line on stderr)
when ``--headless`` is missing, and starts the app. Run the network and GPU check first:
``scripts/isaac_preflight.sh``. Leave a script with ``os._exit`` after flushing, never ``simulation_app.close()``
(Kit's shutdown spins in the container and swallows exit codes; S0, the S2b spike).
"""
from __future__ import annotations

import argparse
import sys


def start_headless(parser: argparse.ArgumentParser, cameras: bool = False) -> tuple[argparse.Namespace, object]:
    """Parse the command line with Isaac Lab's launcher arguments and start Isaac Sim headless.

    cameras: also turn on off-screen rendering (``--enable_cameras``), for videos (Task 6).
    Returns (args, simulation_app). Exits 2 without starting anything when ``--headless`` is missing.
    """
    from isaaclab.app import AppLauncher   # importing the launcher starts nothing

    AppLauncher.add_app_launcher_args(parser)
    args = parser.parse_args()
    if not args.headless:
        print("refused: run with --headless (S2b plan: every Isaac launch is headless)", file=sys.stderr)
        sys.stderr.flush()
        raise SystemExit(2)
    if cameras:
        args.enable_cameras = True
    simulation_app = AppLauncher(args).app
    return args, simulation_app
