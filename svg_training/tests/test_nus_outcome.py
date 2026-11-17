"""Tests of the outcome-parity machinery (Wilson interval, pass rule, the batched arm player, the wire format to the JAX action worker).
Marker rules only; the run of record is scripts/nus_outcome_parity.py."""
import io
import math

import numpy as np
import pytest
import torch

from _nus_markers import BATCH, SEED_B, TOL_LOOSE, TOL_TIGHT, WILSON_CONFIDENCE, WILSON_N_TEN, load_marker_files
from nus_jax_common import read_frame, write_frame
from svg_training.nus.apf import NusApf
from svg_training.nus.outcome import parse_confidence, play_arm, verdict, wilson_interval
from svg_training.nus.replica import NusReplica

TEAMS = ("guard", "strike")


@pytest.fixture(scope="module")
def files(tmp_path_factory):
    return load_marker_files(tmp_path_factory.mktemp("outcome"))


def test_wilson_interval_matches_the_closed_forms():
    z = WILSON_CONFIDENCE
    low, high = wilson_interval(0, WILSON_N_TEN, z)
    z2 = torch.distributions.Normal(0.0, 1.0).icdf(torch.tensor(1 - (1 - z) / 2)).item() ** 2
    assert low == pytest.approx(0, abs=TOL_TIGHT) and high == pytest.approx(z2 / (WILSON_N_TEN + z2), abs=TOL_LOOSE)  # k = 0: the upper end is z^2 / (n + z^2)
    low, high = wilson_interval(WILSON_N_TEN // 2, WILSON_N_TEN, z)
    assert low == pytest.approx(1 - high, abs=TOL_LOOSE) and 0 < low < 1 / 2 < high < 1  # symmetric about one half
    low, high = wilson_interval(WILSON_N_TEN, WILSON_N_TEN, z)
    assert high == pytest.approx(1, abs=TOL_TIGHT) and 0 < low < 1
    narrow, wide = wilson_interval(BATCH * BATCH, BATCH * BATCH * BATCH, z), wilson_interval(BATCH, BATCH * BATCH, z)
    assert narrow[1] - narrow[0] < wide[1] - wide[0]  # more games, narrower interval


def test_confidence_is_read_from_the_gate_text_and_other_forms_are_refused():
    assert parse_confidence("strike_reach_rate_within_95pct_interval_of_jax") == pytest.approx(WILSON_CONFIDENCE)
    for bad in ("strike_reach_rate_equal", "within_pct_interval", "within_195pct_interval"):
        with pytest.raises(ValueError):
            parse_confidence(bad)


def test_verdict_passes_only_inside_the_jax_interval():
    n = BATCH * BATCH * BATCH * BATCH
    same = verdict(n // 2, n // 2, n, WILSON_CONFIDENCE)
    assert same["converted_within_jax_interval"] is True
    far = verdict(n // 2, n // 2 + n // BATCH, n, WILSON_CONFIDENCE)
    assert far["converted_within_jax_interval"] is False
    assert set(("jax_rate", "converted_rate", "jax_interval", "converted_interval", "games")) <= set(far)


@pytest.mark.parametrize("team", TEAMS)
def test_play_arm_is_batched_deterministic_and_paired(files, team):
    rules, deploy, _, _ = files
    sim, apf = NusReplica(rules), NusApf(rules, deploy)
    starts = sim.reset(BATCH, generator=torch.Generator().manual_seed(SEED_B)).pos

    def toward_the_zone(obs):  # a stand-in policy of the right shape: every drone of the team steps the same way
        return torch.full(obs.shape[:-1] + (2,), -rules.strike_max_speed)

    first = play_arm(sim, apf, team, starts, toward_the_zone)
    again = play_arm(sim, apf, team, starts, toward_the_zone)
    assert torch.equal(first.reached, again.reached) and torch.equal(first.first_reach_step, again.first_reach_step)
    assert first.reached.shape == (BATCH,) and first.reached.dtype == torch.bool
    reached_somewhere = first.first_reach_step >= 0
    assert torch.equal(reached_somewhere, first.reached)
    assert first.first_reach_step.max() < rules.episode_steps
    with pytest.raises(ValueError):
        play_arm(sim, apf, "referee", starts, toward_the_zone)


def test_wire_format_round_trips_arrays_and_signals_the_end():
    stream = io.BytesIO()
    array = np.random.default_rng(0).normal(size=(BATCH, 2, BATCH)).astype(np.float32)
    write_frame(stream, array)
    write_frame(stream, array[:1])
    stream.seek(0)
    assert np.array_equal(read_frame(stream), array) and np.array_equal(read_frame(stream), array[:1])
    assert read_frame(stream) is None
    assert math.isfinite(float(array.sum()))
