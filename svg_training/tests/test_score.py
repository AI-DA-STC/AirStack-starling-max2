"""Scoring tool scripts/score.py (S2 Task 6): hand-worked fixed scenarios, outputs, local file by sha only."""
import hashlib
import json
import pathlib
import subprocess

import pytest

from _proc import child_env, child_python

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCORE = ROOT / "scripts" / "score.py"


def run_score(*args, cwd=ROOT):
    return subprocess.run([child_python(), str(SCORE), *args], cwd=cwd, env=child_env(str(ROOT / "source")),
                          capture_output=True, text=True, timeout=600)


@pytest.mark.parametrize("scenario, hold, end", [("lab4_open", 0.0, 37), ("large16_open", 0.0, 205),
                                                  ("lab4_block", 1.0, 1200), ("large16_block", 1.0, 1200)])
def test_score_fixed_scenarios_hand_worked(scenario, hold, end, tmp_path):
    """Design §7 condition 2. Open: the Strike drone flies straight at 0.025 m per step; lab4: 1.51 - 0.6 = 0.91 m
    -> 36.4 -> step 37; large16: 7.51 - 2.4 = 5.11 m -> 204.4 -> step 205. Block: the push-apart holds it out of
    the zone until the time-out at step 1200."""
    out = tmp_path / "s"
    p = run_score("--guard", "zero", "--strike", "strike_straight", "--scenario", scenario, "--presets", "pure",
                  "--no-local", "--device", "cpu", "--games-per-band", "4", "--out", str(out))
    assert p.returncode == 0, p.stderr
    rows = json.loads((out / "scores.json").read_text())["rows"]
    assert len(rows) == 1 and rows[0]["games"] == 4
    assert rows[0]["hold_rate"] == hold and rows[0]["mean_end_step"] == end
    assert (out / "gates.toml").read_text().strip().endswith("gates = []")
    md = (out / "scores.md").read_text()
    assert "s2_game.toml" in md and "not used" in md


def test_score_bands_sizes_and_refuses_overwrite(tmp_path):
    out = tmp_path / "s"
    p = run_score("--guard", "guard_mark_edge,random", "--strike", "strike_straight", "--sizes", "2v1",
                  "--presets", "pure", "--bands", "lab,large", "--no-local", "--device", "cpu",
                  "--games-per-band", "8", "--out", str(out))
    assert p.returncode == 0, p.stderr
    data = json.loads((out / "scores.json").read_text())
    rows = data["rows"]
    assert [(r["guard"], r["band"]) for r in rows] == [("guard_mark_edge", "lab"), ("random", "lab"),
                                                       ("guard_mark_edge", "large"), ("random", "large")]
    for r in rows:
        assert r["games"] == 8 and 0.0 <= r["ci_low"] <= r["hold_rate"] <= r["ci_high"] <= 1.0
        assert r["size"] == "2v1" and r["preset"] == "pure"
    md = (out / "scores.md").read_text()
    assert "## pure partner rules, 2v1" in md and md.count("| guard_mark_edge |") == 2
    again = run_score("--guard", "zero", "--strike", "strike_straight", "--scenario", "lab4_open", "--presets",
                      "pure", "--no-local", "--device", "cpu", "--out", str(out))
    assert again.returncode == 1 and "refusing" in again.stderr


def test_score_starling_preset_runs(tmp_path):
    """With the Starling layer: one small batch, filter rate and closest approach reported. A copy of the game file
    with 20 filter sweeps and 200-step games keeps the test short (made-up test values)."""
    text = (ROOT / "configs" / "s2_game.toml").read_text()
    assert "filter_iterations = 1000" in text and "game_steps = 1200" in text
    game_file = tmp_path / "s2_game.toml"
    game_file.write_text(text.replace("filter_iterations = 1000", "filter_iterations = 20")
                         .replace("game_steps = 1200", "game_steps = 200"))
    out = tmp_path / "s"
    p = run_score("--guard", "guard_mark_edge", "--strike", "strike_straight", "--sizes", "1v1", "--presets",
                  "starling", "--bands", "lab", "--no-local", "--device", "cpu", "--games-per-band", "4",
                  "--game-config", str(game_file), "--out", str(out))
    assert p.returncode == 0, p.stderr
    r = json.loads((out / "scores.json").read_text())["rows"][0]
    assert r["preset"] == "starling" and r["games"] == 4 and r["filter_rate"] is not None
    md = (out / "scores.md").read_text()
    assert "with Starling layer" in md and "filter 20 sweeps" in md and "3-D min / p5 / p50" in md
    assert r["closest_cross_3d_m"] is None or r["closest_cross_3d_m"] >= r["closest_cross_m"] - 1e-6


def test_score_reports_local_file_by_sha_only(tmp_path):
    """A made-up local file: scores.md and scores.json carry its file name and sha256, none of its values."""
    local = tmp_path / "local"
    local.mkdir()
    text = ("[partner_rules]\nkeepout_guard_m = 0.987654\nkeepout_strike_m = 0.876543\n"
            "strike_units_per_step = 0.0234567\n")
    (local / "partner_rules.toml").write_text(text)
    sha = hashlib.sha256(text.encode()).hexdigest()
    out = tmp_path / "s"
    p = run_score("--guard", "zero", "--strike", "strike_straight", "--scenario", "lab4_open", "--presets", "pure",
                  "--local-dir", str(local), "--device", "cpu", "--games-per-band", "2", "--out", str(out))
    assert p.returncode == 0, p.stderr
    md = (out / "scores.md").read_text()
    js = (out / "scores.json").read_text()
    assert sha in md and "partner_rules.toml" in md and sha in js
    for value in ("0.987654", "0.876543", "0.0234567"):
        assert value not in md and value not in js and value not in p.stdout
    assert str(local) not in md


def test_score_packs_pairs_on_their_own_slices(tmp_path):
    """Two Guard strategies in one batch: the standing Guard slice still holds lab4_block exactly (hand-worked:
    time-out at step 1200), whatever the random Guard slice beside it does."""
    out = tmp_path / "s"
    p = run_score("--guard", "random,zero", "--strike", "strike_straight", "--scenario", "lab4_block", "--presets",
                  "pure", "--no-local", "--device", "cpu", "--games-per-band", "6", "--out", str(out))
    assert p.returncode == 0, p.stderr
    rows = {r["guard"]: r for r in json.loads((out / "scores.json").read_text())["rows"]}
    assert rows["zero"]["hold_rate"] == 1.0 and rows["zero"]["mean_end_step"] == 1200
    assert rows["zero"]["games"] == rows["random"]["games"] == 6 and rows["zero"]["batch_games"] == 12


def test_score_refuses_nonfinite_actions(tmp_path):        # S2b Task 9 fix round 1: a NaN strategy is never scored
    (tmp_path / "nan_guard.py").write_text(
        "import torch\n\nclass NanGuard:\n    def __init__(self, team, cfg, num_games, device, seed=0):\n"
        "        self.team, self.name = 'guard', 'nan_guard'\n    def reset(self, games):\n        pass\n"
        "    def act(self, obs):\n        return torch.full((*obs.shape[:2], 4), float('nan'), device=obs.device)\n")
    env = child_env(str(ROOT / "source") + ":" + str(tmp_path))
    r = subprocess.run([child_python(), str(SCORE), "--guard", "nan_guard:NanGuard", "--strike", "strike_straight",
                        "--sizes", "2v1", "--presets", "pure", "--games-per-band", "4", "--bands", "lab", "--no-local",
                        "--device", "cpu", "--out", str(tmp_path / "out")], cwd=ROOT, env=env, capture_output=True,
                       text=True)
    assert r.returncode == 1 and "non-finite" in r.stderr, r.stderr[-2000:]
    assert not (tmp_path / "out" / "scores.json").exists()
