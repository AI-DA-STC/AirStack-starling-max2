"""scripts/compare_backends.py (S2b Task 8): paired scripted games, physics drone against the tier 1 Starling layer.

Fake tables only (made-up numbers): the gate rule of configs/s2b.toml [compare_games_gates] as the owner amended it on
16 November (decision A): per cell (Guard x Strike x size x band) the hold-rate gap at most max_cell_hold_gap; the
physics minimum and 5th percentile of the 3-D closest Guard-Strike approach (games without a start miss) at most
closest_cross_3d_gap_max_m below tier 1's; upsets 0; NaN 0."""
import json
import pathlib
import subprocess
import sys
import tomllib

import numpy as np
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "source"))
sys.path.insert(0, str(ROOT / "tests"))

import compare_backends as cb  # noqa: E402
from _proc import child_env, child_python  # noqa: E402

GATES = tomllib.loads((ROOT / "configs" / "s2b.toml").read_text())["compare_games_gates"]
N = 100
CELLS = [("2v1", "guard_field", "strike_flank", "lab"), ("2v1", "guard_field", "strike_flank", "large")]


def _side(preset, holds=(0.50, 0.70), closest=(1.00, 1.00), upset=0, nan=False, local=None, starts_shift=0.0,
          motion=None):
    """A fake score.py output: per cell, N first games; hold rate holds[i] (Guard wins first), closest 3-D approach
    spread evenly from closest[i] to closest[i] + 0.5 m, the first 10 games start with a miss (closer, left out)."""
    pg = {}
    for (size, gs, ss, band), hold, c in zip(CELLS, holds, closest):
        key = f"{preset}|{size}|{gs}|{ss}|{band}"
        k = round(hold * N)
        pg[key + "|outcome"] = np.array([2] * k + [1] * (N - k), dtype=np.int8)
        pg[key + "|end_step"] = np.full(N, 600, dtype=np.int64)
        pg[key + "|band"] = np.zeros(N, dtype=np.int64)
        miss = np.zeros(N, dtype=bool)
        miss[:10] = True
        pg[key + "|start_miss"] = miss
        c3 = np.concatenate([np.full(10, 0.2), np.linspace(c, c + 0.5, N - 10)])
        if nan:
            c3[50] = np.nan
        pg[key + "|closest_cross_3d_m"] = c3
        pg[key + "|closest_cross_m"] = c3.copy()
        pg[key + "|rule_breach"] = c3 < 1.1
        pg[key + "|filter_corrected_rate"] = np.full(N, 0.3)
        pg[key + "|start_pos_m"] = np.arange(N * 3 * 3, dtype=np.float32).reshape(N, 3, 3) + starts_shift
        pg[key + "|arena_m"] = np.ones((N, 4), dtype=np.float32)
        if preset == "physics":
            up = np.zeros(N, dtype=bool)
            up[:upset] = True
            pg[key + "|upset"] = up
    meta = {"seed": 0, "games_per_band": N, "game_sha256": "ab" * 32, "local_file": local,
            "local_sha256": None if local is None else "cd" * 32, "batch_per_pair": True, "presets": [preset],
            "device": "cuda", "motion": {preset: motion or ("physics/isaaclab" if preset == "physics" else preset)},
            "code_sha": "0123456789ab", "commit": "f" * 40}
    if preset == "physics":
        meta["physics"] = {"nonfinite_count": 0, "yaw_rate_gains": "SIM-ONLY yaw-rate gains (test)"}
    return {"metas": [meta], "per_game": pg}


def test_compare_gate_rule():
    a = _side("starling")
    ok = cb.compare(a, _side("physics"), GATES)
    assert ok["verdict"] == "PASS" and len(ok["cells"]) == 2
    assert ok["cells"][0]["hold_gap"] == pytest.approx(0.0) and ok["cells"][0]["closest_3d_min_gap_m"] == 0.0
    # one cell 0.11 below / above on hold rate -> FAIL; exactly 0.10 -> PASS
    assert cb.compare(a, _side("physics", holds=(0.39, 0.70)), GATES)["verdict"] == "FAIL"
    assert cb.compare(a, _side("physics", holds=(0.50, 0.81)), GATES)["verdict"] == "FAIL"
    assert cb.compare(a, _side("physics", holds=(0.60, 0.60)), GATES)["verdict"] == "PASS"
    # physics closest approach 0.11 m below tier 1's (minimum and 5th percentile both move) -> FAIL; 0.09 -> PASS
    bad = cb.compare(a, _side("physics", closest=(1.00, 0.89)), GATES)
    assert bad["verdict"] == "FAIL" and not bad["cells"][1]["closest_ok"] and bad["cells"][0]["closest_ok"]
    assert cb.compare(a, _side("physics", closest=(0.91, 0.91)), GATES)["verdict"] == "PASS"
    # farther apart under physics is never a failure (the rule is one-sided)
    assert cb.compare(a, _side("physics", closest=(1.60, 1.60)), GATES)["verdict"] == "PASS"
    # the start-miss games (0.2 m) are left out of the closest rule
    assert ok["cells"][0]["physics_closest_3d_min_m"] == pytest.approx(1.0)
    # upsets and NaN
    up = cb.compare(a, _side("physics", upset=1), GATES)
    assert up["verdict"] == "FAIL" and up["upsets"] == 2
    nan = cb.compare(a, _side("physics", nan=True), GATES)
    assert nan["verdict"] == "FAIL" and nan["nan"] == 4          # 2 cells x (3-D and horizontal closest)


def test_compare_min_and_p05_judged_separately():
    """Only the minimum 0.11 m below (one deep game) -> FAIL; only the 5th percentile 0.11 m below -> FAIL."""
    a = _side("starling")
    b = _side("physics")
    key = "physics|2v1|guard_field|strike_flank|lab|closest_cross_3d_m"
    b["per_game"][key] = b["per_game"][key].copy()
    b["per_game"][key][-1] = 0.89                      # one game: the minimum drops by 0.11 m, the p05 hardly
    r = cb.compare(a, b, GATES)
    assert r["verdict"] == "FAIL" and r["cells"][0]["closest_3d_min_gap_m"] == pytest.approx(0.11)
    assert r["cells"][0]["closest_3d_p05_gap_m"] < 0.10
    b = _side("physics")
    c3 = b["per_game"][key].copy()
    c3[10:20] = 0.89 + np.linspace(0.0, 0.001, 10)     # the lowest tenth drops: p05 down 0.11, minimum too
    a2 = _side("starling")
    a2["per_game"][key.replace("physics", "starling")][10:20] = 1.0
    b["per_game"][key] = c3
    a2["per_game"][key.replace("physics", "starling")][10] = 0.89   # tier 1's minimum as low: min gap 0
    r = cb.compare(a2, b, GATES)
    assert r["cells"][0]["closest_3d_min_gap_m"] == pytest.approx(0.0)
    assert r["cells"][0]["closest_3d_p05_gap_m"] > 0.10 and r["verdict"] == "FAIL"


def test_compare_reports_local_file_none():
    r = cb.compare(_side("starling"), _side("physics"), GATES)
    assert r["local_file"] == "none"
    with pytest.raises(ValueError, match="local"):
        cb.compare(_side("starling"), _side("physics", local="partner_rules.toml"), GATES)
    with pytest.raises(ValueError, match="local"):
        cb.compare(_side("starling", local="partner_rules.toml"), _side("physics"), GATES)


def test_compare_refuses_unpaired_or_mismatched():
    with pytest.raises(ValueError, match="paired"):
        cb.compare(_side("starling"), _side("physics", starts_shift=0.5), GATES)
    b = _side("physics")
    b["metas"][0]["seed"] = 1
    with pytest.raises(ValueError, match="seed"):
        cb.compare(_side("starling"), b, GATES)
    b = _side("physics")
    b["metas"][0]["batch_per_pair"] = False
    with pytest.raises(ValueError, match="batch_per_pair"):
        cb.compare(_side("starling"), b, GATES)
    b = _side("physics")
    del b["per_game"]["physics|2v1|guard_field|strike_flank|large|outcome"]
    with pytest.raises(ValueError, match="cell"):
        cb.compare(_side("starling"), b, GATES)


def _write_run(d: pathlib.Path, side: dict) -> None:
    d.mkdir(parents=True)
    rows = []
    (d / "scores.json").write_text(json.dumps({"meta": side["metas"][0], "rows": rows}))
    np.savez_compressed(d / "per_game.npz", **side["per_game"])


def test_compare_cli_writes_outputs(tmp_path):
    """CLI: score folders in, compare.json / compare.md / gates.toml out under runs/<name>/, exit 0 with the verdict in
    the files; a second call into the same folder refuses; --b may list one folder per size."""
    _write_run(tmp_path / "a", _side("starling"))
    _write_run(tmp_path / "b", _side("physics"))
    cmd = [child_python(), str(ROOT / "scripts" / "compare_backends.py"), "--a", str(tmp_path / "a"), "--b",
           str(tmp_path / "b"), "--gates", str(ROOT / "configs" / "s2b.toml"), "--name", "cmp",
           "--runs-dir", str(tmp_path / "runs"), "--no-config-check"]
    p = subprocess.run(cmd, cwd=ROOT, env=child_env(str(ROOT / "source")), capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    out = tmp_path / "runs" / "cmp"
    res = json.loads((out / "compare.json").read_text())
    assert res["verdict"] == "PASS" and res["local_file"] == "none"
    assert res["meta"]["config_check"].startswith("skipped")          # a bypassed [compare_games] check is on record
    assert tomllib.loads((out / "gates.toml").read_text())["compare_games_gates"] == GATES
    md = (out / "compare.md").read_text()
    assert "PASS" in md and "guard_field" in md
    again = subprocess.run(cmd, cwd=ROOT, env=child_env(str(ROOT / "source")), capture_output=True, text=True)
    assert again.returncode == 2 and "exists" in again.stderr


def test_compare_config_check():
    """The run of record must be the [compare_games] matchups: other strategies, sizes, games or seed refuse."""
    cfg = tomllib.loads((ROOT / "configs" / "s2b.toml").read_text())["compare_games"]
    meta = {"guards": cfg["guards"], "strikes": cfg["strikes"], "sizes": cfg["sizes"],
            "games_per_band": cfg["games_per_band"], "seed": cfg["seed"], "batch_per_pair": True,
            "bands": ["lab", "middle", "large"]}
    assert cb.config_problems([meta], cfg) == []
    assert cb.config_problems([{**meta, "games_per_band": 500}], cfg)
    assert cb.config_problems([{**meta, "guards": ["guard_field"]}], cfg)
    # the physics side runs one size per process: the union over its folders is checked
    assert cb.config_problems([{**meta, "sizes": ["2v1"]}, {**meta, "sizes": ["5v3"]}], cfg) == []
    assert cb.config_problems([{**meta, "sizes": ["2v1"]}], cfg)


def test_scripted_compare_figure(tmp_path, capsys):
    """make_s2b_figures.py scripted_compare draws from compare.json (fake data)."""
    import make_s2b_figures

    res = cb.compare(_side("starling"), _side("physics", holds=(0.55, 0.62)), GATES)
    d = tmp_path / "cmp"
    d.mkdir()
    (d / "compare.json").write_text(json.dumps(res))
    out = tmp_path / "f.png"
    make_s2b_figures.scripted_compare(str(out), str(d))
    assert out.stat().st_size > 10_000
    printed = capsys.readouterr().out                       # the table each figure function prints is what it plotted
    assert "| 2v1 | strike_flank | guard_field | lab | 50.0 | 55.0 | +5.0 |" in printed
    assert "| 2v1 | strike_flank | guard_field | large | 70.0 | 62.0 | -8.0 |" in printed
    # a cell with no finished game (no hold rate) is skipped in the plot and printed as n/a, never a crash
    res["cells"][0]["tier1"]["hold_rate"] = None
    res["cells"][0]["hold_gap"] = None
    (d / "compare.json").write_text(json.dumps(res))
    make_s2b_figures.scripted_compare(str(tmp_path / "g.png"), str(d))
    assert "| 2v1 | strike_flank | guard_field | lab | n/a | 55.0 | n/a |" in capsys.readouterr().out


def test_vertical_pass_figure(tmp_path, capsys):
    """make_s2b_figures.py vertical_pass reads the score folders compare.json names (fake data)."""
    import make_s2b_figures

    b = _side("physics")
    key = "physics|2v1|guard_field|strike_flank|lab"
    b["per_game"][key + "|closest_cross_m"] = b["per_game"][key + "|closest_cross_m"].copy()
    b["per_game"][key + "|closest_cross_m"][10:30] = 0.1     # 20 of 100 games: horizontal 0.1 m, 3-D >= 1.0 m: a pass
    b["per_game"]["physics|2v1|guard_field|strike_flank|large|outcome"] = np.zeros(N, dtype=np.int8)   # none finished
    _write_run(tmp_path / "a", _side("starling"))
    _write_run(tmp_path / "b", b)
    d = tmp_path / "cmp"
    d.mkdir()
    res = {"preset_a": "starling", "preset_b": "physics",
           "cells": [{"size": "2v1", "guard": "guard_field", "strike": "strike_flank", "band": band}
                     for band in ("lab", "large")],
           "meta": {"a": [str(tmp_path / "a")], "b": [str(tmp_path / "b")]}}
    (d / "compare.json").write_text(json.dumps(res))
    out = tmp_path / "v.png"
    make_s2b_figures.vertical_pass(str(out), str(d))
    assert out.stat().st_size > 10_000
    printed = capsys.readouterr().out
    assert "| 2v1 | strike_flank | guard_field | lab | 0.000 | 0.200 |" in printed
    assert "| 2v1 | strike_flank | guard_field | large | 0.000 | n/a |" in printed      # no finished game: n/a


def test_compare_refuses_missing_physics_safety_data():
    """Fix round 1 (review Important 1): the upset and NaN gates fail closed. Side b must be the physics preset with
    its per-cell upset arrays and its physics meta (non-finite wrench count); anything missing is refused, never
    counted as zero."""
    a = _side("starling")
    b = _side("physics")
    for k in [k for k in b["per_game"] if k.endswith("|upset")]:
        del b["per_game"][k]
    with pytest.raises(ValueError, match="upset"):
        cb.compare(a, b, GATES)
    b = _side("physics")
    del b["metas"][0]["physics"]
    with pytest.raises(ValueError, match="physics meta"):
        cb.compare(a, b, GATES)
    b = _side("physics")
    b["metas"][0]["physics"]["nonfinite_count"] = None
    with pytest.raises(ValueError, match="nonfinite_count"):
        cb.compare(a, b, GATES)


def test_compare_refuses_starling_as_b():
    """Side b given a tier 1 (starling) score folder: refused (its upset and NaN gates would have nothing to judge)."""
    a = _side("starling")
    b = _side("starling")
    with pytest.raises(ValueError, match="physics"):
        cb.compare(a, b, GATES)


def test_compare_cli_refuses_missing_upset(tmp_path):
    """The same refusal through the CLI: exit 2 with one clear line, no compare.json."""
    b = _side("physics")
    for k in [k for k in b["per_game"] if k.endswith("|upset")]:
        del b["per_game"][k]
    _write_run(tmp_path / "a", _side("starling"))
    _write_run(tmp_path / "b", b)
    p = subprocess.run([child_python(), str(ROOT / "scripts" / "compare_backends.py"), "--a", str(tmp_path / "a"),
                        "--b", str(tmp_path / "b"), "--name", "cmp", "--runs-dir", str(tmp_path / "runs"),
                        "--no-config-check"], cwd=ROOT, env=child_env(str(ROOT / "source")), capture_output=True,
                       text=True)
    assert p.returncode == 2 and "upset" in p.stderr, p.stderr
    assert not (tmp_path / "runs" / "cmp" / "compare.json").exists()
