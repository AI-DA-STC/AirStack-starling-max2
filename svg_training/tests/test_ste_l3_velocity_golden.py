"""STE phase L3, first slice (B8), test 4: the velocity route (today's learner) is unchanged by the mixed route's code.

The record (``tests/data/ste_l3_velocity_golden.json``) was made from the commit BEFORE the L3 slice (850d4967,
``development``) with ``--write-golden``: per side, a tiny CPU learner (``Learner`` on ``DecisionEnv``, the L0.12 gate
file's trainer settings cut to 6 games, 2 decisions per update, 1 epoch), two PPO updates, then the update statistics,
the losses, sums of every agent's policy, value and observation-scaler tensors and the mean actions of
``Learner.team()`` on fixed observations. This file imports only names that existed at 850d4967, so the same code records
from the old tree and checks the new one.

Whole numbers (games ended, reaches, stale ticks) are compared exactly. Decimal numbers are compared exactly on the
recording's CPU capability (``_capability``, AVX512: repeated equal there) and within ``RTOL``/``ATOL`` on any other:
PyTorch CPU kernels differ in the last bits by CPU capability (tests/test_game_tag_off_golden.py, measured 21 and 23 Nov
2026), and two PPO updates carry such bits forward (passes under ATEN_CPU_CAPABILITY avx2 and default, 24 Nov 2026). The bit-for-bit check of the switch itself (no ``[learner]`` table against
``action = "velocity"``) is in tests/test_ste_l3_skills.py.

Record (from a tree of the commit before the slice; the archive goes outside the repository):

    git -C ~/AirStack-starling-max2 archive 850d4967 svg_training/source svg_training/configs | tar -x -C /tmp/l3_old
    cd svg_training && PYTHONPATH=/tmp/l3_old/svg_training/source python tests/test_ste_l3_velocity_golden.py --write-golden
"""
import json
import os
import pathlib
import sys

import pytest
import torch

from _torch_threads import default_torch_threads  # noqa: F401  (autouse: goldens at the default thread count)

ROOT = pathlib.Path(__file__).resolve().parents[1]
if "--write-golden" not in sys.argv:
    sys.path.insert(0, str(ROOT / "source"))
from svg_training.core.observations import OBS_DIM  # noqa: E402
from svg_training.opponents.scripted import make_strategy  # noqa: E402
from svg_training.ste import exploit, exploit_train  # noqa: E402

GOLDEN = ROOT / "tests" / "data" / "ste_l3_velocity_golden.json"
RTOL, ATOL = 1e-4, 1e-5
WHOLE = ("games_ended", "reaches", "nonfinite_actions")


def tiny(gates) -> dict:
    return dict(gates.trainer, num_games=6, rollouts=2, learning_epochs=1, mini_batches=1)


def golden_values(side: str) -> dict:
    """Two updates of a tiny learner of ``side``; the numbers the record keeps."""
    gates = exploit.load_gates()
    cfg = exploit.variant_cfg(gates, "base")
    game = exploit_train.TrainGame(cfg, 6, 3, 3, device="cpu", seed=7)
    other = "guard" if side == "strike" else "strike"
    opp = make_strategy(exploit.opponent_of(gates, "base", side), other, cfg, 6, "cpu", 8)
    env = exploit_train.DecisionEnv(game, gates.trainer["decision_ticks"], side, opp)
    learner = exploit_train.Learner(tiny(gates), env, "cpu", seed=11)
    stats = [learner.update() for _ in range(2)]
    out: dict = {"whole": {f"u{i}_{k}": int(s[k]) for i, s in enumerate(stats) for k in WHOLE},
                 "decimal": {}}
    out["whole"].update({f"u{i}_stale_ticks": round(s["stale_tick_share"] * s["game_steps"])
                         for i, s in enumerate(stats)})
    dec = out["decimal"]
    for i, s in enumerate(stats):
        dec.update({f"u{i}_{k}": float(v) for k, v in s["losses"].items()})
        dec.update({f"u{i}_{k}": float(v) for k, v in s["std"].items()})
    for a in learner.names:
        for nm, mod in (("policy", learner.agent.policies[a]), ("value", learner.agent.values[a]),
                        ("obs_scaler", learner.agent._observation_preprocessor[a])):
            ts = [t for t in list(mod.parameters()) + list(mod.buffers()) if t.is_floating_point()]
            dec[f"{a}_{nm}_sum"] = float(sum(t.double().sum() for t in ts))
            dec[f"{a}_{nm}_abs"] = float(sum(t.double().abs().sum() for t in ts))
    obs = torch.randn(5, 3, OBS_DIM, generator=torch.Generator().manual_seed(3))
    act = learner.team().act(obs)
    dec["team_act_sum"] = float(act.double().sum())
    dec["team_act_abs"] = float(act.double().abs().sum())
    return out


SIDES = ("guard", "strike")


def fresh_process_values(side: str) -> dict:
    """``golden_values`` computed in a fresh Python process (24 Nov 2026): in the full suite an earlier module leaves
    global torch state behind (threads, and more than threads: a thread pin alone did not make the decimals equal), so
    the bit-for-bit comparison runs where nothing else has run."""
    import subprocess

    from _proc import child_env, child_python
    env = {**child_env("source" + os.pathsep + "tests"), "CUDA_VISIBLE_DEVICES": ""}
    r = subprocess.run([child_python(), str(pathlib.Path(__file__)), "--print-values", side], cwd=ROOT, env=env,
                       capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stderr[-2000:]
    return json.loads(r.stdout.strip().splitlines()[-1])


@pytest.mark.parametrize("side", SIDES)
def test_the_velocity_route_trains_as_before_the_l3_slice(side):
    data = json.loads(GOLDEN.read_text())
    record = data[side]
    now = fresh_process_values(side)
    assert now["whole"] == record["whole"]
    assert set(now["decimal"]) == set(record["decimal"])
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
    data["_how"] = ("recorded from 850d4967 (development, before the L3 slice) on CPU capability "
                    f"{torch.backends.cpu.get_cpu_capability()}")
    GOLDEN.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n")
    print(f"wrote {GOLDEN}")
