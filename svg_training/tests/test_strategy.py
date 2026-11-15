"""Strategy contract: reset mask, check_strategy, split, no training library (S2 Task 5)."""
import os
import pathlib
import subprocess
import sys

import pytest
import torch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
from svg_training.core.game import SCENARIOS, SvgGame  # noqa: E402
from svg_training.core.game_config import load_game_cfg  # noqa: E402
from svg_training.core.observations import OBS_DIM  # noqa: E402
from svg_training.core.strategy import SplitStrategy, check_strategy  # noqa: E402

CFG = load_game_cfg(use_local=False)[0]
ENV = {**os.environ, "PYTHONPATH": str(ROOT / "source")}
N = 3


class RecordingStrategy:
    name = "recording"

    def __init__(self, team, out=0.0):
        self.team, self.resets, self.out = team, [], out

    def reset(self, games):
        self.resets.append(games.clone())

    def act(self, obs):
        return torch.full((*obs.shape[:2], 4), self.out)


def lab4():
    return SvgGame(CFG, N, 1, 1, device="cpu", scenario=SCENARIOS["lab4_open"])


def test_strategy_reset_mask_equals_done():
    g = lab4()
    rec = RecordingStrategy("guard")
    obs = g.reset()
    rec.reset(torch.ones(N, dtype=torch.bool))
    outs = []
    for _ in range(80):
        a = torch.zeros(N, 1, 4)
        a[..., 0] = 1.0
        out = g.step({"guard": rec.act(obs["guard"]), "strike": a})
        rec.reset(out.done)
        outs.append(out)
        obs = out.obs
    assert bool(outs[36].done.all()) and not bool(outs[35].done.any())      # Strike wins at step 37
    assert torch.equal(rec.resets[37], outs[36].done) and rec.resets[0].all()
    assert all(torch.equal(rec.resets[k + 1], outs[k].done) for k in range(80))


class Bad:
    team, name = "guard", "bad"

    def __init__(self, kind):
        self.kind = kind

    def reset(self, games):
        pass

    def act(self, obs):
        a = torch.zeros(*obs.shape[:2], 4)
        if self.kind == "range":
            a += 2.0
        elif self.kind == "nan":
            a += float("nan")
        elif self.kind == "shape":
            a = a[:, :, :3]
        elif self.kind == "grad":
            a = (a + torch.zeros(1, requires_grad=True)) * 1.0
        return a


@pytest.mark.parametrize("kind, word", [("range", "range"), ("nan", "finite"), ("shape", "shape"),
                                        ("grad", "autograd")])
def test_check_strategy_catches_bad_output(kind, word):
    with pytest.raises(AssertionError, match=word):
        check_strategy(Bad(kind), lab4(), steps=3)


def test_check_strategy_accepts_good():
    check_strategy(RecordingStrategy("guard", 0.5), lab4(), steps=5)
    check_strategy(RecordingStrategy("strike", -1.0), lab4(), steps=5)


def test_split_strategy_routes_slices_and_resets():
    a, b = RecordingStrategy("guard", 0.25), RecordingStrategy("guard", -0.5)
    s = SplitStrategy("guard", [(a, slice(0, 1)), (b, slice(1, 3))])
    act = s.act(torch.zeros(3, 2, OBS_DIM))
    assert (act[0] == 0.25).all() and (act[1:] == -0.5).all()
    s.reset(torch.tensor([True, False, True]))
    assert a.resets[0].tolist() == [True] and b.resets[0].tolist() == [False, True]
    with pytest.raises(ValueError):
        SplitStrategy("strike", [(a, slice(0, 1))])
    check_strategy(SplitStrategy("guard", [(a, slice(0, 1)), (b, slice(1, 3))]), lab4(), steps=3)


def test_core_imports_no_training_library():
    code = ("import svg_training.core.game, svg_training.core.strategy, svg_training.opponents, sys; "
            "assert not {'skrl', 'gymnasium', 'isaaclab'} & set(sys.modules)")
    r = subprocess.run([sys.executable, "-c", code], env=ENV, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
