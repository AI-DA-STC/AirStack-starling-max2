"""S2 game config and gates: neutral defaults, local overlay allow-list, unknown keys, gates file."""
import pathlib
import shutil
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
from svg_training.core.game_config import CONFIGS, load_game_cfg, load_s2_gates  # noqa: E402


def test_neutral_defaults_load_without_local(tmp_path):
    cfg, prov = load_game_cfg(local_dir=tmp_path / "absent")
    assert prov.local_file is None and cfg.preset == "partner"
    assert cfg.team_speed_mps("strike") == pytest.approx(0.5)
    assert cfg.team_speed_mps("guard") == pytest.approx(0.5 / 1.5)
    assert cfg.game_ticks() == 1200 and not cfg.starling.enabled
    assert cfg.arena.bands_m["lab"] == (4.0, 6.0)


def test_local_overlay_applies_allowed_keys(tmp_path):  # made-up numbers only
    (tmp_path / "partner_rules.toml").write_text(
        "[partner_rules]\nkeepout_guard_m = 0.77\nseconds_per_step = 0.1\ngame_steps = 30\n")
    cfg, prov = load_game_cfg(local_dir=tmp_path)
    assert cfg.rules.keepout_guard_m == 0.77 and cfg.game_ticks() == 60 and prov.local_sha256


def test_local_overlay_rejects_other_keys(tmp_path):
    (tmp_path / "partner_rules.toml").write_text("[starling_layer]\nenabled = true\n")
    with pytest.raises(ValueError, match="not allowed"):
        load_game_cfg(local_dir=tmp_path)


def test_unknown_key_raises(tmp_path):
    bad = tmp_path / "g.toml"
    bad.write_text(CONFIGS.joinpath("s2_game.toml").read_text().replace("game_steps", "game_stepz"))
    with pytest.raises(ValueError, match="unknown key"):
        load_game_cfg(bad, local_dir=None)


def test_use_local_false_ignores_file(tmp_path):
    (tmp_path / "partner_rules.toml").write_text("[partner_rules]\nkeepout_guard_m = 0.77\n")
    cfg, prov = load_game_cfg(local_dir=tmp_path, use_local=False)
    assert cfg.rules.keepout_guard_m == 1.10 and prov.local_file is None


def test_replace_dotted():
    cfg, _ = load_game_cfg(local_dir=None)
    assert cfg.replace(**{"starling.enabled": True}).starling.enabled and not cfg.starling.enabled
    with pytest.raises(KeyError):
        cfg.replace(**{"starling.nope": 1})


def test_example_file_matches_defaults(tmp_path):
    shutil.copy(CONFIGS / "partner_rules.example.toml", tmp_path / "partner_rules.toml")
    a, _ = load_game_cfg(local_dir=tmp_path)
    b, _ = load_game_cfg(local_dir=None)
    assert a == b


def test_s2_gates_complete():
    g = load_s2_gates()
    assert g["filter_speed_gates"]["game_steps_per_s_min"] == 100000
    assert g["standin_gates"]["seeds_required"] == len(g["standin"]["seeds"]) == 3
    assert set(g) >= {"filter_speed", "filter_speed_gates", "bag_check_gates", "scoring", "standin", "standin_gates"}
