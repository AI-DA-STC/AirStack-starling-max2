"""Follow-up checks on T44 (scripts/ste_l011_followups.py): the replay machinery (fixed starts, the held command, the
pass-through tag recorder) and every check, on a tiny CPU run made with the real driver and the smoke gate (the tests
never read the real T44 run folder)."""
import json
import sys

import numpy as np
import pytest
import torch

from _l011_smoke import GF, GP, SS, smoke_gates
from _ste_tools import SCRIPTS
from svg_training.core.game_config import TICK_S
from svg_training.ste import shared, sweep
from svg_training.ste.game_spec import load_game_spec

sys.path.insert(0, str(SCRIPTS))
import ste_l011_followups as fu  # noqa: E402
import ste_sweep_l011 as driver  # noqa: E402


@pytest.fixture(scope="module")
def tiny_run(tmp_path_factory):
    """A real driver run on the CPU: 1 cell per batch, 12 games, 120 ticks (games finish), no clips."""
    tmp = tmp_path_factory.mktemp("l011_followups")
    mp = pytest.MonkeyPatch()
    mp.setenv(shared.SHARED_ENV, str(tmp / "shared"))
    mp.setenv(shared.LEGACY_LOGS_ENV, "")
    gates = smoke_gates(tmp / "gates.toml", run={"games_per_cell": 12, "ticks_cap": 120})
    run = tmp / "run"
    assert driver.main(["--gates", str(gates), "--run-dir", str(run), "--cap-h", "1", "--no-clips"]) == 0
    mp.undo()
    return run


def test_the_decision_period_comes_from_the_sheet():
    assert fu.decision_ticks() * TICK_S == pytest.approx(load_game_spec()[0].value("timing.decision_s"))
    assert fu.decision_ticks() == 12


class Counter:
    team, name = "guard", "counter"

    def __init__(self):
        self.k = 0

    def reset(self, games):
        pass

    def act(self, obs):
        self.k += 1
        return torch.full((obs.shape[0], 1, 4), float(self.k))


def test_a_held_command_changes_only_on_decision_ticks_phased_per_game():
    p = fu.HoldPlayer(Counter(), 3)
    p.reset(torch.ones(2, dtype=torch.bool))
    seen = [p.act(torch.zeros(2, 1, 1))[:, 0, 0].tolist() for _ in range(4)]
    assert seen == [[1, 1], [1, 1], [1, 1], [4, 4]]
    p.reset(torch.tensor([False, True]))                 # game 1 restarts: it decides at once, game 0 keeps its phase
    assert p.act(torch.zeros(2, 1, 1))[:, 0, 0].tolist() == [4, 5]


def test_hold_1_is_the_player_itself_bit_for_bit():
    inner, wrapped = Counter(), fu.HoldPlayer(Counter(), 1)
    wrapped.reset(torch.ones(3, dtype=torch.bool))
    for _ in range(5):
        assert torch.equal(wrapped.act(torch.zeros(3, 1, 1)), inner.act(torch.zeros(3, 1, 1)))


def test_the_replay_starts_from_the_given_positions_and_the_recorder_changes_nothing(tiny_run):
    gates = sweep.load_gates(tiny_run / "gates.toml")
    index = fu.cell_index(tiny_run)
    t44 = fu.cell_games(index, ("base", GF, SS))
    cfg = sweep.variant_cfg(gates, "base")
    g = fu.FixedStartsGame(cfg, torch.as_tensor(t44["start_pos_m"]), torch.as_tensor(t44["start_miss"]), 3, 3, 0)
    assert np.array_equal(g.pos_m.numpy(), t44["start_pos_m"])
    args = (cfg, "3v3", (GF, SS), t44["start_pos_m"], t44["start_miss"], int(gates.run["seed"]), int(gates.run["ticks_cap"]))
    plain, recorded = fu.replay(*args), fu.replay(*args, record_tags=True)
    for key in fu.EXACT + ("closest_3d_m", "guards_removed"):
        assert np.array_equal(plain[key], recorded[key]), key
    # the CPU replay of a CPU run, one cell per batch as there: game for game the run's own result
    assert fu.agreement(plain, t44)["differ"] == 0


def test_every_check_runs_on_a_tiny_run_with_its_known_answers(tiny_run, tmp_path, monkeypatch):
    monkeypatch.setattr(fu, "TIE_PAIRS", [("base", GF, SS), ("tag_1p2", GF, SS)])
    monkeypatch.setattr(fu, "DECISION_PAIRS", [("base", GP, SS)])
    monkeypatch.setattr(fu, "IDENTICAL", [("base", [(GP, SS), (GF, SS)])])
    monkeypatch.setattr(fu, "HEIGHT_PAIRS", [("base", GF, SS)])
    tie = fu.check_tie(tiny_run)
    for row in tie:
        assert row["agreement_with_t44"]["differ"] == 0
        assert row["inside_tags_already_inside_a_step_earlier"] == 0          # known answer
        assert row["holds_any_tag_inside_zone"] <= row["holds"] and row["holds_last_tag_inside_zone"] <= row["holds"]
    dec = fu.check_decision(tiny_run)[0]
    assert dec["hold_ticks"] == 12 and dec["every_tick_agreement_with_t44"]["differ"] == 0
    assert dec["flips"]["hold_to_reach"] <= dec["every_tick"]["holds"]
    ident = fu.check_identical(tiny_run)
    assert ident["heights"][0]["strike_dz_max_m_max"] >= 0
    assert ident["cell_files"][0]["games"] == 12
    comp = fu.check_composition(tiny_run, tmp_path / "figs")
    assert comp["old_columns_unchanged"]["found_as_prefix"] == comp["old_columns_unchanged"]["old_rows"] > 0
    assert (tmp_path / "figs" / "hold_composition.png").is_file()
    before = (tiny_run / "results.md").read_text()
    fu.check_composition(tiny_run, tmp_path / "figs2")
    assert (tiny_run / "results.md").read_text() == before                                # the run folder is untouched


def test_wilson_matches_core_metrics():
    lo, hi = fu.wilson_interval(192, 1000)
    assert 0.2 < hi < 0.22 and 0.16 < lo < 0.17
