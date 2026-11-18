"""Phase 5 Task S5 (plan section 9): the stage 5.2 evaluation runner (scripts/nus_phase5_eval.py) and its metrics module
(nus/tier1_metrics.py), CPU, marker local files: the bars from Phase 4 row 5's counts (the plan's 0.460 / 0.055 / 0.004 / 0.601), the
per-seed gates and the 2-of-3 rule, the control C-1 stopping first, the separately capped INFO cross-play table, the refusals, and a
whole marker-world evaluation of a tiny trained run (gates file first, videos as data, NOT OF RECORD). No numeric literal (G2)."""
from __future__ import annotations

import importlib.util
import json
import shutil
import tomllib

import numpy as np
import pytest
import torch

import _nus_markers  # noqa: F401
from _nus_markers import ROOT
from _nus_tier1_fixture import (BAR_PLACES, EVAL_GAMES, HOLDS_FAILING, HOLDS_PASSING, MIN_SEEDS, PLAN_BARS, REACH_PASSING, REF_GAMES,
                                SEED_NAMES, T23_REACH, TRAIN_SEED, tier1_world_fixture, tiny_tier1_config)
from svg_training.nus import ladder, outputs, players
from svg_training.nus import tier1_metrics as M

_TRAINED: dict = {}
TABLE = tomllib.loads((ROOT / "configs" / "nus_port.toml").read_text())["gates"]["phase5_tier1_training"]


def _scores(counts: dict) -> dict:
    return {"pairs": [{"guard": g, "strike": s, "reach": M.rate(k, REF_GAMES)} for (g, s), k in counts.items()]}


def _bars():
    return M.reference_bars(_scores(T23_REACH), list(TABLE["guard_strikes"]), list(TABLE["strike_guards"]))


# ------------------------------------------------------------------------------------------------ metrics
def test_bars_reproduce_the_plan_values_from_the_t23_counts():
    bars = _bars()
    assert {g: round(b["bar"], BAR_PLACES) for g, b in bars.items()} == PLAN_BARS
    assert bars["G-1"]["from"] == ["ParkedGuard"] and bars["G-2"]["from"] == ["guard_mirror"]
    assert set(bars["G-3"]["from"]) == {"G19", "P3G", "ParkedGuard"} and bars["S-1"]["against"] == "ParkedGuard"


def test_bars_refuse_a_strike_nobody_was_scored_against():
    counts = {k: v for k, v in T23_REACH.items() if k[1] != "strike_flank"}
    with pytest.raises(ValueError, match="G-4"):
        M.reference_bars(_scores(counts), list(TABLE["guard_strikes"]), list(TABLE["strike_guards"]))


def _seed(holds: int, reach: int, nonfinite: int = 0) -> dict:
    out = {g: {"reach": M.rate(REF_GAMES - holds, REF_GAMES), "nonfinite": 0} for g in M.GUARD_GATES}
    out["S-1"] = {"reach": M.rate(reach, REF_GAMES), "nonfinite": nonfinite}
    return out


def test_seed_gates_and_the_two_of_three_rule():
    bars = _bars()
    good = M.seed_verdict(_seed(HOLDS_PASSING, REACH_PASSING), bars, TABLE["nonfinite_max"])
    weak = M.seed_verdict(_seed(HOLDS_FAILING, REACH_PASSING), bars, TABLE["nonfinite_max"])
    broken = M.seed_verdict(_seed(HOLDS_PASSING, REACH_PASSING, nonfinite=1), bars, TABLE["nonfinite_max"])
    assert good["pass"] and not weak["pass"] and not weak["gates"]["G-1"]["pass"] and weak["gates"]["G-3"]["pass"]
    assert not broken["pass"] and not broken["gates"]["F-2"]["pass"] and good["gates"]["F-1"]["pass"]
    assert TABLE["min_seeds_passing"] == MIN_SEEDS
    two = M.stage_verdict(dict(zip(SEED_NAMES, (good, good, weak))), 0, TABLE["min_seeds_passing"])
    assert two["verdict"] == "PASS" and two["claim"] == "in 2 of 3 seeds"
    three = M.stage_verdict(dict(zip(SEED_NAMES, (good, good, good))), 0, TABLE["min_seeds_passing"])
    assert three["claim"] == "in all 3 seeds"
    one = M.stage_verdict(dict(zip(SEED_NAMES, (good, weak, broken))), 0, TABLE["min_seeds_passing"])
    assert one["verdict"] == "FAIL"
    stopped = M.stage_verdict(dict(zip(SEED_NAMES, (good, good, good))), 1, TABLE["min_seeds_passing"])
    assert stopped["verdict"] == "STOPPED"


def test_control_differences_and_clamp_share():
    a = torch.tensor([1, 2, 1, 1], dtype=torch.int8)
    assert M.control_differences(a, a.clone()) == 0 and M.control_differences(a, a.flip(0)) == 2
    share = M.clamp_share(torch.tensor([1, 0]), torch.tensor([2, 2]))
    assert share["k"] == 1 and share["n"] == 2 + 2


# ------------------------------------------------------------------------------------------------ the runner on the marker world
@pytest.fixture()
def marker(tmp_path, monkeypatch):
    tw = tier1_world_fixture(tmp_path, monkeypatch, episode_steps=None)   # the synthetic S20 / G19 checkpoints' own game length
    tiny_tier1_config(tmp_path, monkeypatch)
    monkeypatch.setattr(outputs, "RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(players, "TRAINED", {})
    mods = {}
    for name in ("nus_tier1_train", "nus_phase5_eval"):
        spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
        mods[name] = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mods[name])
        monkeypatch.setattr(mods[name], "RUNS_ROOT", tmp_path / "runs")
        monkeypatch.setattr(mods[name], "STAGE_DIR", tmp_path / "runs" / "s52")
    run = tmp_path / "runs" / "s52" / "seed"
    if "run" in _TRAINED:   # one tiny training run per session (the marker files are the same in every test, so is the method's sha256)
        shutil.copytree(_TRAINED["run"], run)
    else:
        assert mods["nus_tier1_train"].main(["--seed", str(TRAIN_SEED), "--smoke", "--method", str(tw.method_path), "--out", str(run),
                                             "--probe-updates", "0"]) == 0
        _TRAINED["run"] = run
    # the Phase 4 marker starts as a starts file, and a reference row scored on them (so the control matches game by game)
    starts = tmp_path / "starts.npz"
    np.savez_compressed(starts, **{k: v.numpy() for k, v in tw.w.starts.items()})
    monkeypatch.setattr(ladder, "load_starts", lambda path=None: tw.w.starts)
    w = tw.world
    ref = tmp_path / "runs" / "reference"
    ref.mkdir(parents=True)
    pairs, per_game = [], {}
    for guard, strike in T23_REACH:
        if guard in ("guard_mirror", "P3G"):
            continue
        res, _, _, _ = ladder.play_game_pair(w.cfg, w.geo, w.row, tw.w.starts, guard, strike, w.guards, w.strikes, "cpu",
                                             tw.w.settings["ladder"]["seed"], 0, None, w.rules)
        pairs.append({"guard": guard, "strike": strike, "reach": M.rate(int((res.outcome == 1).sum()), int(res.outcome.numel()))})
        per_game[f"{guard}__{strike}__outcome"] = res.outcome.numpy()
    (ref / "scores.json").write_text(json.dumps({"pairs": pairs}))
    np.savez_compressed(ref / "per_game.npz", **per_game)
    gates = tmp_path / "nus_port.toml"
    source = (ROOT / "configs" / "nus_port.toml").read_text()
    gates.write_text(source.replace(f'starts_file = "{TABLE["starts_file"]}"', f'starts_file = "{starts}"', 1))
    monkeypatch.setattr(mods["nus_phase5_eval"], "GATES", gates)
    return tw, mods["nus_phase5_eval"], run, ref, tmp_path


def _eval_args(tw, run, ref, out, *extra):
    return ["--stage", "5.2", "--not-of-record", "--reference-dir", str(ref), "--games", str(EVAL_GAMES), "--runs", str(run),
            "--method", str(tw.method_path), "--out", str(out), *extra]


def test_marker_world_evaluation_end_to_end(marker):
    tw, ev, run, ref, tmp_path = marker
    out = tmp_path / "runs" / "s52" / "eval"
    assert ev.main(_eval_args(tw, run, ref, out, "--info", "--crossplay")) == 0
    gates = (out / "gates.toml").read_text()
    assert "NOT OF RECORD" in gates and "[gates.phase5_tier1_training]" in gates and "reference scores: sha256" in gates
    result = json.loads((out / "result.json").read_text())
    assert result["not_of_record"] and result["control"]["games_differ"] == 0
    assert set(result["seeds"]) == {f"seed{TRAIN_SEED}"}
    seed = result["seeds"][f"seed{TRAIN_SEED}"]
    assert set(seed["gates"]) == {*M.GUARD_GATES, *M.STRIKE_GATES, "F-1", "F-2"}
    assert result["verdict"]["verdict"] in ("PASS", "FAIL") and result["verdict"]["note"].startswith("NOT OF RECORD")
    rows = json.loads((out / "scores.json").read_text())["pairs"]
    labels = [r["label"] for r in rows]
    assert labels[0] == "control" and labels.count(f"seed{TRAIN_SEED}") == len(M.GUARD_GATES) + len(M.STRIKE_GATES)
    assert all(r["clamp_share"]["n"] > 0 and r["nonfinite"] == 0 and r["unfinished_games"] == 0 for r in rows)
    assert result["info"] and all(i.get("played") for i in result["info"])
    assert result["crossplay"]["played"] and not result["crossplay"]["dropped"]
    assert list((out / "videos" / "pending").glob("*.npz")) and "NOT OF RECORD" in (out / "record_draft.md").read_text()
    assert ev.main(_eval_args(tw, run, ref, out)) == ev.EXIT_REFUSED            # never overwritten


def test_control_c1_stops_before_any_gated_pairing(marker):
    tw, ev, run, ref, tmp_path = marker
    data = dict(np.load(ref / "per_game.npz"))
    key = "ParkedGuard__S20__outcome"
    data[key] = np.where(data[key] == 1, 2, 1).astype(data[key].dtype)      # every game flipped
    bad = tmp_path / "runs" / "bad_reference"
    bad.mkdir()
    (bad / "scores.json").write_text((ref / "scores.json").read_text())
    np.savez_compressed(bad / "per_game.npz", **data)
    out = tmp_path / "runs" / "s52" / "eval_bad"
    assert ev.main(_eval_args(tw, run, bad, out)) == ev.EXIT_STOPPED
    result = json.loads((out / "result.json").read_text())
    assert result["verdict"]["verdict"] == "STOPPED" and result["control"]["games_differ"] == EVAL_GAMES and not result["seeds"]
    assert [r["label"] for r in json.loads((out / "scores.json").read_text())["pairs"]] == ["control"]


def test_crossplay_has_its_own_cap(marker, monkeypatch):
    tw, ev, run, ref, tmp_path = marker
    original = ev.Cap.fits
    monkeypatch.setattr(ev.Cap, "fits", lambda self, s: False if self.group == "s52_crossplay" else original(self, s))
    out = tmp_path / "runs" / "s52" / "eval_cap"
    assert ev.main(_eval_args(tw, run, ref, out, "--crossplay")) == 0
    result = json.loads((out / "result.json").read_text())
    assert result["crossplay"]["dropped"] and not result["crossplay"]["played"] and "dropped" in result["crossplay"]["note"]
    assert result["verdict"]["verdict"] in ("PASS", "FAIL")                    # the gated pairings ran first and are intact


def test_refusals(marker, tmp_path):
    tw, ev, run, ref, _ = marker
    out = tmp_path / "runs" / "s52" / "eval_refused"
    assert ev.main(["--stage", "5.3"]) == ev.EXIT_REFUSED
    assert ev.main(["--stage", "5.2", "--runs", str(run), "--method", str(tw.method_path), "--out", str(out)]) == ev.EXIT_REFUSED  # PROPOSED
    assert ev.main(["--stage", "5.2", "--games", str(EVAL_GAMES), "--runs", str(run), "--out", str(out)]) == ev.EXIT_REFUSED
    other = tmp_path / "other_method.toml"
    other.write_text(tw.method_path.read_text() + "\n")
    assert ev.main(_eval_args(tw, run, ref, out)[:-2] + ["--method", str(other), "--out", str(out)]) == ev.EXIT_REFUSED
    assert not (out / "result.json").exists()
