"""STE phase L3, slice 2, test 8a (design note ste_learning/drafts/L3_SLICE2_DESIGN.md): the velocity route's SCORING
path is unchanged by the L3 code (slice 1's ``HeldPlayer`` choice branch, slice 2's dispatch), against the tree before
slice 1.

The record (``tests/data/ste_l3_velocity_scoring_golden.json``) was made from ``8421efdd`` (development, the commit
before L3 slice 1) with ``--write-golden``: per side, a fixed velocity team (``LearnerTeam`` of ``StandinPolicy`` nets
drawn from a fixed seed, identity scalers), held 12 ticks, played by ``exploit.play_cells`` in the run's evaluation
cells (the team, the ``zero`` twin and every script of its team against g* / s*) on T44's first ``GAMES`` starts.
This file imports only names that existed at 8421efdd, so the same code records from the old tree and checks the new
one.

Per-game whole numbers (outcome, end step, tags, Guard drones tagged, Strike drones left) are compared exactly. The
closest approach (decimal) is compared exactly on the recording's CPU capability and within ``RTOL``/``ATOL`` on any
other (as tests/test_ste_l3_velocity_golden.py). Computed in a fresh child process at torch's default thread count
(OMP_NUM_THREADS and MKL_NUM_THREADS dropped).

Record (from a tree of the commit before slice 1; the archive goes outside the repository):

    git -C ~/AirStack-starling-max2 archive 8421efdd svg_training/source svg_training/configs svg_training/params \\
        | tar -x -C /tmp/l3_old
    cd svg_training && PYTHONPATH=/tmp/l3_old/svg_training/source python tests/test_ste_l3_velocity_scoring_golden.py \\
        --write-golden
"""
import json
import os
import pathlib
import sys

import pytest
import torch

ROOT = pathlib.Path(__file__).resolve().parents[1]
if "--write-golden" not in sys.argv:
    sys.path.insert(0, str(ROOT / "source"))
from svg_training.opponents.learned import StandinPolicy  # noqa: E402
from svg_training.ste import exploit  # noqa: E402

GOLDEN = ROOT / "tests" / "data" / "ste_l3_velocity_scoring_golden.json"
RTOL, ATOL = 1e-4, 1e-5
GAMES = 16
NET_SEED = 23
WHOLE = ("outcome", "end_step", "tags", "guards_tagged", "strikes_left")
SIDES = ("guard", "strike")


def golden_values(side: str) -> dict:
    """The fixed velocity team of ``side`` in its evaluation cells; the numbers the record keeps."""
    gates = exploit.load_gates()
    ref = exploit.load_reference(exploit.ROOT / gates.reference["file"])
    cfg = exploit.variant_cfg(gates, "base")
    torch.manual_seed(NET_SEED)
    nets = []
    for _ in range(3):
        pol = StandinPolicy(list(gates.trainer["hidden"]), "cpu")
        pol.eval()
        nets.append(pol.net)
    team = exploit.LearnerTeam(side, nets, [lambda o, train=False: o] * 3)
    cells = exploit.eval_cells(gates, "base", side)
    pg = exploit.play_cells(cfg, "3v3", ref, cells, GAMES, "cpu", ref.meta["seed"], gates.run["ticks_cap"],
                            learner=team, hold_ticks=int(gates.trainer["decision_ticks"]))
    out = {"cells": [list(c) for c in cells], "whole": {k: [int(x) for x in pg[k].reshape(-1)] for k in WHOLE},
           "decimal": {"closest_3d_m_sum": float(pg["closest_3d_m"].astype("float64").sum()),
                       "closest_3d_m_abs": float(abs(pg["closest_3d_m"].astype("float64")).sum())}}
    return out


def fresh_process_values(side: str) -> dict:
    import subprocess

    from _proc import child_env, child_python
    env = {**child_env("source" + os.pathsep + "tests"), "CUDA_VISIBLE_DEVICES": ""}
    for k in ("OMP_NUM_THREADS", "MKL_NUM_THREADS"):     # recorded at torch's default thread count
        env.pop(k, None)
    r = subprocess.run([child_python(), str(pathlib.Path(__file__)), "--print-values", side], cwd=ROOT, env=env,
                       capture_output=True, text=True, timeout=900)
    assert r.returncode == 0, r.stderr[-2000:]
    return json.loads(r.stdout.strip().splitlines()[-1])


@pytest.mark.parametrize("side", SIDES)
def test_the_velocity_scoring_path_plays_as_before_the_l3_slices(side):
    data = json.loads(GOLDEN.read_text())
    record = data[side]
    now = fresh_process_values(side)
    assert now["cells"] == record["cells"]
    assert now["whole"] == record["whole"]
    games = len(record["whole"]["outcome"])
    assert games == GAMES * len(record["cells"])
    end = record["whole"]["end_step"]           # power: the held velocity team (cell 0) plays other games than its
    assert end[:GAMES] != end[GAMES:2 * GAMES]  # zero twin (cell 1), so the held command path is exercised
    if torch.backends.cpu.get_cpu_capability() == data["_capability"]:
        assert now["decimal"] == record["decimal"]                      # bit for bit on the recording's capability
        return
    for k, v in record["decimal"].items():
        assert now["decimal"][k] == pytest.approx(v, rel=RTOL, abs=ATOL), k


if __name__ == "__main__" and "--print-values" in sys.argv:
    print(json.dumps(golden_values(sys.argv[sys.argv.index("--print-values") + 1])))

if __name__ == "__main__" and "--write-golden" in sys.argv:
    data = {side: golden_values(side) for side in SIDES}
    data["_capability"] = torch.backends.cpu.get_cpu_capability()
    data["_how"] = ("recorded from 8421efdd (development, before L3 slice 1) on CPU capability "
                    f"{torch.backends.cpu.get_cpu_capability()}")
    GOLDEN.write_text(json.dumps(data, sort_keys=True) + "\n")
    print(f"wrote {GOLDEN}")
