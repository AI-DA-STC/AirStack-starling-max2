"""Template gates: one gate (min pairwise distance >= CHANGE_ME m) from metrics.csv via metrics_core. Sim-only.

Copy and extend (see crossing/gates.py for the full set). report.py calls build_rows / ledger_sentence / figure_caption.
"""
import pathlib
import sys

import numpy as np

_TOOLS = pathlib.Path(__file__).resolve().parents[2]
for _p in (_TOOLS / "live", _TOOLS / "lib"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
import metrics_core as M  # noqa: E402
import report as R  # noqa: E402

GATE_M = 1.10  # CHANGE_ME


def build_rows(out, heavy, env):
    out = pathlib.Path(out)
    rows, ctx = [], {"headline": "minimum pairwise distance", "crosscheck": None}
    R.isaac_rows(rows, out)
    try:
        _, cols, data = M.read_metrics_csv(out / "metrics.csv")
        p2 = data[data[:, cols.index("phase")] == 2]
        m = float(np.nanmin(p2[:, cols.index("min_pair_distance")]))
        R.row(rows, "min pairwise distance ≥ %.2f m" % GATE_M, "≥ %.2f m" % GATE_M, "%.2f m" % m, "-", m >= GATE_M)
    except (OSError, M.MetricsCsvError, ValueError) as e:
        R.row(rows, "min pairwise distance ≥ %.2f m" % GATE_M, "≥ %.2f m" % GATE_M, "n/a — metrics.csv: %s" % e, "-", None)
    R.landing_rows(rows, out)
    R.evidence_rows(rows, out, heavy, env["BAG_PREFIX"], extra_files=("metrics.csv",))
    return rows, ctx


def ledger_sentence(rows, ctx, verdict):
    return "CHANGE_ME test name, live metrics: %s" % verdict


def figure_caption(ctx):
    return "CHANGE_ME: what the plot shows, the gate line, the shaded phases; drawn from metrics.csv by `tools/sim.sh figures <name> <run>`."
