"""The shared command chain (S2b Task 4): the commander copy + the safety filter, moved out of FittedResponse.

``test_command_chain_bit_identical`` replays 200 random ticks through ``FittedResponse`` (filter on; a team mask
with hover seeding, and a per-game every-pair mask without it; masked resets on the way) and compares every
tick's speed, position, setpoint and ``corrected`` with golden tensors saved from the commit BEFORE the extraction
(a669df8). Regenerate them only from a commit whose FittedResponse is known good:

    cd svg_training && PYTHONPATH=source python tests/test_command_chain.py --write-golden

CPU, float32, made-up commands; the parameter file is real_exploratory_v0 (exploratory).
"""
import pathlib
import sys

import pytest
import torch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
from svg_training.core.safety_filter import team_pair_mask  # noqa: E402
from svg_training.models.fitted import FittedResponse, load_params  # noqa: E402

PARAMS = ROOT / "params" / "real_exploratory_v0.toml"
GOLDEN = ROOT / "tests" / "data" / "command_chain_golden.pt"
N, GUARDS, STRIKES, TICKS = 2, 2, 2, 200
M = GUARDS + STRIKES


def _golden_run(kind: str) -> dict[str, torch.Tensor]:
    """200 ticks of FittedResponse, made-up commands; returns per-tick tensors stacked [T, ...].

    kind "team": the team pair mask, hover seeding on (the Starling layer's setting).
    kind "every": every pair, set per game each tick from a random 'live' set (as the Starling layer does), hover
    seeding off (the S1 default). Both: a random masked reset with new positions every 50 ticks."""
    gen = torch.Generator().manual_seed(20261116 if kind == "team" else 7)

    def box(*shape: int) -> torch.Tensor:
        p = (torch.rand(*shape, 3, generator=gen) * 2.0 - 1.0) * torch.tensor([1.5, 1.5, 0.3])
        return p + torch.tensor([0.0, 0.0, 1.2])

    every = ~torch.eye(M, dtype=torch.bool)
    mask = team_pair_mask(GUARDS, STRIKES) if kind == "team" else every
    fr = FittedResponse(N, M, PARAMS, device="cpu", safety_filter=True, pair_mask=mask, filter_iterations=200,
                        pos_m=box(N, M), hover_seed=(kind == "team"))
    fr.reset(torch.ones(N, M, dtype=torch.bool), fr.pos_m)
    keys = ("vel_mps", "pos_m", "p_sp", "v_ff", "a_ff", "corrected")
    log: dict[str, list[torch.Tensor]] = {k: [] for k in keys}
    live = torch.ones(N, M, dtype=torch.bool)
    for t in range(TICKS):
        if t and t % 50 == 0:
            fr.reset(torch.rand(N, M, generator=gen) < 0.5, box(N, M))
        if kind == "every":
            if t % 20 == 0:
                live = torch.rand(N, M, generator=gen) < 0.8
            fr.set_pair_mask(every[None] & live[:, :, None] & live[:, None, :])
        cmd = (torch.rand(N, M, 3, generator=gen) * 2.0 - 1.0) * torch.tensor([0.6, 0.6, 0.2])
        pos = fr.pos_m if t % 3 else None                     # also the "adopt the caller's positions" path
        vel = fr.step(cmd, pos)
        for k, v in zip(keys, (vel, fr.pos_m, *fr.setpoint, fr.corrected)):
            log[k].append(v.clone())
    return {k: torch.stack(v) for k, v in log.items()}


def test_command_chain_bit_identical():                   # Review Focus 3: S1/S2 unchanged
    golden = torch.load(GOLDEN)
    for kind in ("team", "every"):
        now = _golden_run(kind)
        assert now["corrected"].any(), f"{kind}: the filter never acted, the test checks nothing"
        for k, v in now.items():
            assert torch.equal(v, golden[kind][k]), f"{kind}: {k} differs from the pre-extraction golden"


if __name__ == "__main__" and "--write-golden" in sys.argv:
    GOLDEN.parent.mkdir(parents=True, exist_ok=True)
    torch.save({kind: _golden_run(kind) for kind in ("team", "every")}, GOLDEN)
    print(f"wrote {GOLDEN}")
