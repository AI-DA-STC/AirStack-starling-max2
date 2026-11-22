"""STE L1 side track, task L1.15 (spec ste_learning/drafts/L1_SIDE_TRACK_SPEC.md, addendum 3): the delay check's study
files. Two parameter files equal to params/real_exploratory_v0.toml but for [px4] delay_s (0 and 0.30 s; study-only,
never a drone value) and two game files equal to configs/ste_l011/tag_1p15.toml but for [starling_layer] params."""
from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from svg_training.ste.exploit import load_game_cfg_file
from svg_training.ste import exploit

ROOT = exploit.ROOT
BASE_PARAMS = ROOT / "params" / "real_exploratory_v0.toml"
BASE_GAME = ROOT / "configs" / "ste_l011" / "tag_1p15.toml"
L1 = ROOT / "configs" / "ste_l1"
STUDY = {0.0: ("study_params_delay0.toml", "tag_1p15_delay0.toml"),
         0.30: ("study_params_delay0p30.toml", "tag_1p15_delay0p30.toml")}


def _lines_but(path: Path, skip) -> list[str]:
    """The file's lines that are not comments, blank, or ``skip(line)``."""
    return [x for x in path.read_text().splitlines() if x.strip() and not x.lstrip().startswith("#") and not skip(x)]


@pytest.mark.parametrize("delay", sorted(STUDY))
def test_a_study_parameter_file_differs_from_v0_in_delay_only(delay):
    path = L1 / STUDY[delay][0]
    base, new = tomllib.loads(BASE_PARAMS.read_text()), tomllib.loads(path.read_text())
    assert new["px4"]["delay_s"] == delay and base["px4"]["delay_s"] == 0.1482
    new["px4"]["delay_s"] = base["px4"]["delay_s"]
    assert new == base                                                    # every other value the same
    is_delay = lambda x: x.startswith("delay_s")                         # noqa: E731
    assert _lines_but(path, is_delay) == _lines_but(BASE_PARAMS, is_delay)   # and every value line, byte for byte
    head = path.read_text().split("\n[", 1)[0]
    assert "STUDY-ONLY" in head and "never a drone value" in head


@pytest.mark.parametrize("delay", sorted(STUDY))
def test_a_delay_game_file_differs_from_tag_1p15_in_its_parameter_file_only(delay):
    params, game = STUDY[delay]
    path = L1 / game
    base, new = tomllib.loads(BASE_GAME.read_text()), tomllib.loads(path.read_text())
    assert new["starling_layer"]["params"] == f"configs/ste_l1/{params}"
    new["starling_layer"]["params"] = base["starling_layer"]["params"]
    assert new == base
    is_params = lambda x: x.startswith("params = ")                      # noqa: E731
    assert _lines_but(path, is_params) == _lines_but(BASE_GAME, is_params)
    cfg, ref = load_game_cfg_file(path), load_game_cfg_file(BASE_GAME)
    assert cfg.game_ticks() == ref.game_ticks() == 2400


@pytest.mark.parametrize("delay", sorted(STUDY))
def test_the_delay_game_builds_with_its_delay(delay):
    """The tier 1 Starling layer of the game reads the study file: its pure delay is ``delay`` (in 0.01 s model steps)."""
    from svg_training.core.game import SvgGame
    game = SvgGame(load_game_cfg_file(L1 / STUDY[delay][1]), 2, 3, 3, "cpu", 7)
    drone = game._starling.model
    got = (drone.delay_n + drone.delay_f) * drone.model_dt_s
    assert got == pytest.approx(delay, abs=1e-9)
