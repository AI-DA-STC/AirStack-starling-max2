"""S2b Task 1: the S2b settings and gates file, the motion backend switch, and S2's stand-in tables untouched."""
import hashlib
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
from svg_training.core.game_config import (  # noqa: E402
    CONFIGS, LOCAL_ALLOWED, StarlingLayerCfg, load_game_cfg, load_s2b_gates)

# sha256 of the [standin] and [standin_gates] table texts of configs/s2.toml at the S2 commit 96894cc
# (each table from its header line up to the next header). S2b may not change them (plan D14); Task 9 reuses this.
STANDIN_SHA256 = {"standin": "29d71984c226f88cf568d2fbe128b5e8a782ed21f48569002fbc1d8eae980495",
                  "standin_gates": "10e16a5be00ff3bb539351f7bd96d089741ce95d0c7d1a73cde9a598caa0eb77"}

S2B_TABLES = {"physics", "agreement", "agreement_gates", "step_tests", "step_gates", "throughput", "compare_games",
              "compare_games_gates", "video", "standin_s2b", "fallback_rate_gains", "tensorboard"}


def table_text(text: str, name: str) -> str:
    """The text of TOML table [name]: its header line up to (not including) the next line starting with '['."""
    out, on = [], False
    for line in text.splitlines(keepends=True):
        if line.startswith("["):
            on = line.startswith(f"[{name}]")
        if on:
            out.append(line)
    return "".join(out)


def test_s2b_gates_have_every_table():
    g = load_s2b_gates()
    assert set(g) == S2B_TABLES
    assert g["physics"]["params"] == "params/starling_physics_v0.toml"
    assert (g["physics"]["physics_dt_s"], g["physics"]["fallback_physics_dt_s"]) == (0.005, 0.0025)
    assert g["agreement_gates"]["nan_max"] == 0 and g["step_gates"]["upsets_max"] == 0
    assert [s["name"] for s in g["step_tests"]["steps"]] == ["x_strike", "y_guard", "diagonal", "reverse",
                                                              "z_up_info"]
    assert g["step_tests"]["real_log_sha256_prefix"] == "4db5b1fcf33e69c6"
    assert len(g["video"]["clips"]) == 4 and g["video"]["max_mb"] == 10.0


def test_games_gate_is_the_owners_amended_rule():          # owner's answers, second round, A
    cg = load_s2b_gates()["compare_games_gates"]
    assert cg["closest_cross_3d_gap_max_m"] == 0.10 and "physics_closest_cross_min_m" not in cg
    assert cg["max_cell_hold_gap"] == 0.10 and cg["upsets_max"] == 0 and cg["nan_max"] == 0


def test_owner_answers_written_down():                     # owner's answers 3, 5, 6 and the TensorBoard addition
    g = load_s2b_gates()
    s = g["standin_s2b"]
    assert s["motions"] == ["pure", "starling", "physics"]
    assert s["wall_clock_cap_min_isaac"] == 180 and s["wall_clock_cap_min_torch"] == 45
    fb = g["fallback_rate_gains"]
    assert fb["rate_gain_scale"] == 0.5 and "SIM-ONLY" in fb["label"]
    assert all(n.startswith(("mc_rollrate_", "mc_pitchrate_")) for n in fb["gains"])
    tb = g["tensorboard"]
    assert "game/hold_rate" in tb["game_scalars"] and tb["cloud_logging"] is False


def test_isaac_cap_matches_the_s2_budget():
    s2 = load_s2b_gates(CONFIGS / "s2.toml")["standin"]
    assert load_s2b_gates()["standin_s2b"]["wall_clock_cap_min_torch"] == s2["wall_clock_cap_min"]


def test_backend_defaults_leave_s2_unchanged():
    assert StarlingLayerCfg().backend == "fitted"
    assert StarlingLayerCfg().physics_params == "params/starling_physics_v0.toml"
    cfg, _ = load_game_cfg(use_local=False)
    assert cfg.starling.backend == "fitted" and not cfg.starling.enabled
    assert cfg.starling == StarlingLayerCfg(params=cfg.starling.params, filter_check_every=8)


def test_physics_backend_loads(tmp_path):
    text = (CONFIGS / "s2_game.toml").read_text()
    assert 'backend = "fitted"' in text
    f = tmp_path / "g.toml"
    f.write_text(text.replace('backend = "fitted"', 'backend = "physics"'))
    cfg, _ = load_game_cfg(f, use_local=False)
    assert cfg.starling.backend == "physics"
    assert cfg.replace(**{"starling.backend": "fitted"}).starling.backend == "fitted"


def test_unknown_backend_raises():
    # Raised when the config is built, so SvgGame (Task 4) can never receive an unknown backend.
    with pytest.raises(ValueError, match="backend"):
        StarlingLayerCfg(backend="isaac")
    cfg, _ = load_game_cfg(use_local=False)
    with pytest.raises(ValueError, match="backend"):
        cfg.replace(**{"starling.backend": "nope"})


def test_local_file_cannot_switch_backend(tmp_path):
    assert "starling_layer.backend" not in LOCAL_ALLOWED
    assert "starling_layer.physics_params" not in LOCAL_ALLOWED
    (tmp_path / "partner_rules.toml").write_text('[starling_layer]\nbackend = "physics"\n')
    with pytest.raises(ValueError, match="not allowed"):
        load_game_cfg(local_dir=tmp_path)


def test_s2_standin_tables_unchanged():                     # D14
    text = (CONFIGS / "s2.toml").read_text()
    for name, sha in STANDIN_SHA256.items():
        assert hashlib.sha256(table_text(text, name).encode()).hexdigest() == sha, name
