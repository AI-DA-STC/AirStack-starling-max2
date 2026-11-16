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


# ---------------------------------------------------------------------------------------------------------------------
# S2b Task 8: --batch-per-pair (paired games) and the physics preset. S2 behaviour with the flag off is pinned by a
# golden made with the S2 score.py before Task 8 (tests/data/score_s2_flag_off_golden.json, its "_how" says how).
# ---------------------------------------------------------------------------------------------------------------------
GOLDEN = ROOT / "tests" / "data" / "score_s2_flag_off_golden.json"
TIMING_KEYS = {"batch_seconds", "batch_game_steps_per_s"}


def _tiny_game_file(tmp_path):
    """configs/s2_game.toml with 20 filter sweeps and 200-step games (test speed only; the golden used the same)."""
    text = (ROOT / "configs" / "s2_game.toml").read_text()
    assert "filter_iterations = 1000" in text and "game_steps = 1200" in text
    game_file = tmp_path / "tiny_game.toml"
    game_file.write_text(text.replace("filter_iterations = 1000", "filter_iterations = 20")
                         .replace("game_steps = 1200", "game_steps = 200"))
    return game_file


def _rows_and_games(out):
    import numpy as np

    rows = [{k: v for k, v in r.items() if k not in TIMING_KEYS}
            for r in json.loads((out / "scores.json").read_text())["rows"]]
    return rows, dict(np.load(out / "per_game.npz"))


def _same_value(a, b):
    if isinstance(a, float) or isinstance(b, float):
        return a is not None and b is not None and abs(a - b) <= 1e-9 * max(1.0, abs(a), abs(b))
    return a == b


def test_batch_per_pair_off_is_s2_unchanged(tmp_path):
    """Flag off: the S2 golden's command gives the same rows (timing left out; counts and steps exact, floats to
    1e-9) and the same per-game arrays, key for key: no new key appears without the flag."""
    import numpy as np

    gold = json.loads(GOLDEN.read_text())
    out = tmp_path / "s"
    p = run_score("--guard", "guard_mark_edge,random", "--strike", "strike_straight,strike_flank", "--sizes", "2v1",
                  "--presets", "pure,starling", "--bands", "lab,large", "--games-per-band", "6", "--seed", "3",
                  "--no-local", "--device", "cpu", "--game-config", str(_tiny_game_file(tmp_path)), "--out", str(out))
    assert p.returncode == 0, p.stderr
    rows, games = _rows_and_games(out)
    assert len(rows) == len(gold["rows"]) == 16
    for r, g in zip(rows, gold["rows"]):
        assert set(r) == set(g)
        for k in g:
            assert _same_value(r[k], g[k]), (k, r[k], g[k])
    assert set(games) == set(gold["per_game"])
    for k, enc in gold["per_game"].items():
        want = np.array([np.inf if v is None else v for v in enc["values"]], dtype=enc["dtype"])
        assert str(games[k].dtype) == enc["dtype"], k
        np.testing.assert_allclose(games[k].astype(float), want.astype(float), rtol=1e-9, atol=0, err_msg=k)


def test_batch_per_pair_pairs_starts(tmp_path):
    """D15. Pure preset, 2 pairs, CPU, --batch-per-pair: within a run every pair's slot k plays the same arena and
    starts; a second run (other Guard strategies, the Starling layer on) gives slot k the same arena and starts."""
    import numpy as np

    game_file = _tiny_game_file(tmp_path)
    common = ("--sizes", "2v1", "--bands", "lab,middle", "--games-per-band", "5", "--seed", "4", "--no-local",
              "--device", "cpu", "--game-config", str(game_file), "--batch-per-pair")
    a, b = tmp_path / "a", tmp_path / "b"
    pa = run_score("--guard", "guard_mark_edge,random", "--strike", "strike_straight", "--presets", "pure",
                   *common, "--out", str(a))
    pb = run_score("--guard", "zero,guard_field", "--strike", "strike_flank", "--presets", "starling",
                   *common, "--out", str(b))
    assert pa.returncode == 0, pa.stderr
    assert pb.returncode == 0, pb.stderr
    meta = json.loads((a / "scores.json").read_text())["meta"]
    assert meta["batch_per_pair"] is True
    rows, ga = _rows_and_games(a)
    assert all(r["batch_games"] == 5 for r in rows)
    _, gb = _rows_and_games(b)
    for band in ("lab", "middle"):
        keys = [f"pure|2v1|{gs}|strike_straight|{band}" for gs in ("guard_mark_edge", "random")]
        keys += [f"starling|2v1|{gs}|strike_flank|{band}" for gs in ("zero", "guard_field")]
        for field in ("start_pos_m", "arena_m", "start_miss"):
            arrays = [(ga if k.startswith("pure") else gb)[f"{k}|{field}"] for k in keys]
            for arr in arrays[1:]:
                np.testing.assert_array_equal(arr, arrays[0], err_msg=f"{band} {field}")
        assert ga[keys[0] + "|start_pos_m"].shape == (5, 3, 3) and ga[keys[0] + "|arena_m"].shape == (5, 4)
    # the two bands draw different arenas (seed + band index)
    assert not np.array_equal(ga["pure|2v1|random|strike_straight|lab|arena_m"],
                              ga["pure|2v1|random|strike_straight|middle|arena_m"])


def test_batch_per_pair_one_pair_equals_flag_off(tmp_path):
    """With one Guard x Strike pair the packed batch is already one pair: flag on = flag off, row for row; the flag
    only adds the start and arena arrays."""
    import numpy as np

    game_file = _tiny_game_file(tmp_path)
    common = ("--guard", "guard_mirror", "--strike", "strike_flank", "--sizes", "2v1", "--presets", "pure,starling",
              "--bands", "lab", "--games-per-band", "6", "--seed", "2", "--no-local", "--device", "cpu",
              "--game-config", str(game_file))
    off, on = tmp_path / "off", tmp_path / "on"
    assert run_score(*common, "--out", str(off)).returncode == 0
    assert run_score(*common, "--batch-per-pair", "--out", str(on)).returncode == 0
    r_off, g_off = _rows_and_games(off)
    r_on, g_on = _rows_and_games(on)
    assert r_off == r_on
    assert set(g_on) - set(g_off) == {k for k in g_on if k.endswith(("|start_pos_m", "|arena_m"))}
    for k in g_off:
        np.testing.assert_array_equal(g_off[k], g_on[k], err_msg=k)


@pytest.mark.parametrize("extra, why", [
    (("--sizes", "2v1,5v3", "--headless", "--batch-per-pair"), "one size"),
    (("--headless", "--batch-per-pair"), "one size"),                       # defaulted sizes: two
    (("--sizes", "2v1", "--batch-per-pair"), "--headless"),
    (("--sizes", "2v1", "--headless", "--batch-per-pair", "--device", "cpu"), "cuda"),
    (("--sizes", "2v1", "--headless"), "--batch-per-pair"),
])
def test_score_physics_refuses_two_sizes(extra, why, tmp_path):
    """--presets physics: more than one size per process, a missing --headless, a device other than cuda or a missing
    --batch-per-pair -> exit 2 with one line naming the problem, before Isaac Sim (or even torch) is imported."""
    import time

    t0 = time.time()
    p = run_score("--guard", "guard_field", "--strike", "strike_flank", "--presets", "physics", "--no-local",
                  *extra, "--out", str(tmp_path / "o"))
    assert p.returncode == 2, (p.returncode, p.stderr[-2000:])
    assert why in p.stderr and "refus" in p.stderr
    assert time.time() - t0 < 20 and p.stdout == "" and len(p.stderr.strip().splitlines()) == 1   # nothing started
    assert not (tmp_path / "o").exists()


def _torch_world(n, m, params, device):
    from svg_training.models.rigid_body import TorchRigidBodyWorld
    return TorchRigidBodyWorld(n, m, params.airframe, params.physics_dt_s, device)


def test_score_physics_preset_in_process(tmp_path):
    """The physics preset through the in-process hook (a PyTorch rigid-body world instead of IsaacWorld; tests
    only): one world of games_per_band games reused for every band and pair; rows and meta carry the motion, the
    upset count and the physics drone's settings (SIM-ONLY yaw-rate gains named)."""
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    import score

    built = []

    def factory(n, m, params, device):
        built.append((n, m))
        return _torch_world(n, m, params, device)

    out = tmp_path / "p"
    rc = score.main(["--guard", "guard_mark_edge,zero", "--strike", "strike_straight", "--sizes", "1v1",
                     "--presets", "physics", "--bands", "lab,large", "--games-per-band", "3", "--seed", "1",
                     "--no-local", "--device", "cpu", "--game-config", str(_tiny_game_file(tmp_path)),
                     "--batch-per-pair", "--out", str(out)], world_factory=factory)
    assert rc == 0
    assert built == [(3, 2)]                                    # one world for 2 bands x 2 pairs
    data = json.loads((out / "scores.json").read_text())
    meta, rows = data["meta"], data["rows"]
    from svg_training.models.rigid_body import TORCH_WORLD_LABEL
    assert meta["motion"] == {"physics": f"physics/{TORCH_WORLD_LABEL}"} and meta["batch_per_pair"] is True
    ph = meta["physics"]
    assert "SIM-ONLY" in ph["yaw_rate_gains"] and ph["nonfinite_count"] == 0 and ph["physics_dt_s"] == 0.005
    assert len(ph["physics_params_sha256"]) == 64 and meta["code_sha"]
    assert len(rows) == 4 and all(r["preset"] == "physics" and r["upset_games"] == 0 for r in rows)
    _, games = _rows_and_games(out)
    assert games["physics|1v1|zero|strike_straight|lab|upset"].dtype == bool
    assert "tier 2" in (out / "scores.md").read_text()


def test_physics_world_reuse_equals_fresh_world():
    """score.py reuses one world for every band and pair: a match on a world that already played another match
    gives exactly what it gives on a fresh world (PyTorch rigid-body world, CPU, made-up short game)."""
    import sys

    import torch

    sys.path.insert(0, str(ROOT / "source"))
    from svg_training.core.game import SvgGame
    from svg_training.core.game_config import load_game_cfg
    from svg_training.core.physics_layer import load_game_physics_params
    from svg_training.core.play import play_match
    from svg_training.opponents.scripted import make_strategy

    cfg, _ = load_game_cfg(local_dir=None, use_local=False)
    cfg = cfg.replace(**{"starling.enabled": True, "starling.backend": "physics", "starling.filter_iterations": 20,
                         "rules.game_steps": 60})
    params = load_game_physics_params(cfg)

    def match(world, guard, seed):
        game = SvgGame(cfg, 3, 1, 1, device="cpu", seed=seed, band=0, world=world)
        return play_match(game, make_strategy(guard, "guard", cfg, 3, "cpu", 101),
                          make_strategy("strike_straight", "strike", cfg, 3, "cpu", 202))

    used = _torch_world(3, 2, params, "cpu")
    match(used, "guard_field", 7)
    a = match(used, "guard_mark_edge", 5)
    b = match(_torch_world(3, 2, params, "cpu"), "guard_mark_edge", 5)
    for f in ("outcome", "end_step", "closest_cross_3d_m", "filter_corrected_rate", "upset", "start_pos_m"):
        assert torch.equal(getattr(a, f), getattr(b, f)), f
