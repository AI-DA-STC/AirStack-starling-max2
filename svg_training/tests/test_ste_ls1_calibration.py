"""Route 3, stage LS1, task LS1-M1-T7: the paired statistics (``ste/cells.py``, C7) and the calibration read (job LS1.5,
``scripts/ste_ls1_calibration.py``; plan ste_learning/drafts/LS1_TASK_PLAN.md).

* The statistics on synthetic games: b, c and n match ``scoring.paired_wins``; the worked example (B-5); the interval
  contains the difference and narrows with n; ``adjusted_z`` (Bonferroni); the pooled difference is the mean of the cell
  differences and its interval uses the z given; end-step differences; the per-skill command-error table and the
  active rule of M2-T3; no NaN anywhere (empty strata are None).
* The committed files: ``cells.toml`` (20 distinct mixed combinations per side, equal to ``draw_mixed`` with its seed;
  each ``[permutation]`` a derangement; the info opponent), ``calibration.toml`` (its pins hold, no game count: one
  ruler); every arm x cell of both sides builds from them with a unique player name (no play).
* Tiny runs (CPU, ``tmp_path``, 8 games, one opponent, 2 mixed combinations, the identity arm and one noise arm): the
  documented keys, controls PASS, the identity arm with b = c = 0, ``complete`` last; the permuted scripts read from
  T44 without play; both intervals; a finished folder exits 2; a forced control failure exits 6 with controls.json
  only; chunking does not change a game, and a run stopped on request (exit 4) or at its cap (exit 3) resumes to the
  same results.json; the info opponent's cells never ask T44 for a cell."""
import json
import math
import os
import signal
import sys
import tomllib
from statistics import NormalDist

import numpy as np
import pytest
import torch

from svg_training.core.rewards import GUARD_WIN, RUNNING, STRIKE_WIN
from svg_training.opponents.scripted import make_strategy
from svg_training.ste import cells, compare, exploit, scoring, skills
from svg_training.ste.run_contract import (EXIT_CAP, EXIT_CONTROL_FAILED, EXIT_DONE, EXIT_INTERRUPTED,
                                           EXIT_REFUSED)

import _ste_ls1 as h
from _ste_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import ste_ls1_calibration as cal  # noqa: E402

ROOT = exploit.ROOT
CALIBRATION = ROOT / "configs" / "ste_ls1" / "calibration.toml"
CELLS = ROOT / "configs" / "ste_ls1" / "cells.toml"
SCRIPTED = ROOT / "source" / "svg_training" / "opponents" / "scripted.py"
SIDES = ("guard", "strike")
MIXED = 20
GATED_M = {"guard": 150, "strike": 130}          # (K + 20 mixed) x the other team's [players]: 5 + 20 by 6, 6 + 20 by 5
TINY_GAMES = 8
TINY_MIXED = 2
FAST_OPPONENT = "strike_straight"               # the shortest games against the Guard team (measured, LS1.5 header)
NOISE_ARM = "noise=0.05"
Z95 = 1.959964
TOL = 1e-5


def _pg(outcomes, end_steps=None):
    outcome = np.asarray(outcomes, dtype=np.int8)
    end = np.arange(len(outcome), dtype=np.int16) + 1 if end_steps is None else np.asarray(end_steps, dtype=np.int16)
    return {"outcome": outcome, "end_step": end}


def _win(side):
    return GUARD_WIN if side == "guard" else STRIKE_WIN


def _lose(side):
    return STRIKE_WIN if side == "guard" else GUARD_WIN


def _pair(side, both, b, c, neither):
    """(arm, reference) outcomes: ``both`` won by both, ``b`` won by the reference only (the arm lost), ``c`` won by the
    arm only, ``neither`` won by neither, in that order."""
    w, lo = _win(side), _lose(side)
    arm = [w] * both + [lo] * b + [w] * c + [lo] * neither
    ref = [w] * both + [w] * b + [lo] * c + [lo] * neither
    return _pg(arm), _pg(ref)


# ================================================================================================ the statistics
@pytest.mark.parametrize("side", SIDES)
def test_paired_cell_counts_match_paired_wins(side):
    rng = np.random.default_rng(11)
    w, lo = _win(side), _lose(side)
    arm = _pg(rng.choice([w, lo], size=300))
    ref = _pg(rng.choice([w, lo], size=300))
    got = cells.paired_cell(arm, ref, side, Z95)
    want = scoring.paired_wins(arm["outcome"], ref["outcome"], side)
    assert got["b"] == want["script_only"] and got["c"] == want["trained_only"]
    assert got["n"] == want["games"] == 300 and got["flips"] == got["b"] + got["c"]
    assert got["diff"] == pytest.approx((got["c"] - got["b"]) / got["n"], abs=1e-12)
    assert got["sign_test_p"] == pytest.approx(want["sign_test_p"], abs=1e-12)
    assert set(got) == {"b", "c", "flips", "n", "diff", "ci", "sign_test_p", "method"}
    with pytest.raises(ValueError):
        cells.paired_cell(_pg([RUNNING] + [w] * 3), _pg([w] * 4), side, Z95)       # an unfinished game


def test_a_worked_paired_example():
    """B-5. n = 1,000: both won 500, b = 30 (the reference won, the arm lost), c = 20 (the reverse), both lost 450; z =
    1.959964 (= adjusted_z(0.05, 1)). diff = (c - b) / n = -0.010; flips = 50; sign test p = 2 P(X <= 20 | 50, 1/2) =
    0.20264 (exact, two-sided, method-independent).

    Newcombe's paired hybrid score interval (Newcombe 1998, method 10, no continuity correction): the Wilson intervals
    at z of the two win shares, p_arm = (500 + 20) / n = 0.52 -> (l_a, u_a) and p_ref = (500 + 30) / n = 0.53 ->
    (l_r, u_r); phi = (500 x 450 - 30 x 20) / sqrt(530 x 470 x 520 x 480) = 0.89994;
    lower = diff - sqrt((p_arm - l_a)^2 - 2 phi (p_arm - l_a)(u_r - p_ref) + (u_r - p_ref)^2) = -0.02381,
    upper = diff + sqrt((u_a - p_arm)^2 - 2 phi (u_a - p_arm)(p_ref - l_r) + (p_ref - l_r)^2) = 0.00383."""
    arm, ref = _pair("guard", 500, 30, 20, 450)
    got = cells.paired_cell(arm, ref, "guard", Z95)
    assert (got["b"], got["c"], got["flips"], got["n"]) == (30, 20, 50, 1000)
    assert got["diff"] == pytest.approx(-0.010, abs=TOL)
    assert got["sign_test_p"] == pytest.approx(0.20264, abs=TOL)
    assert got["ci"][0] == pytest.approx(-0.02381, abs=TOL) and got["ci"][1] == pytest.approx(0.00383, abs=TOL)
    assert got["method"].startswith(cells.NEWCOMBE)
    assert cells.newcombe_phi(500, 30, 20, 450) == pytest.approx(0.89994, abs=TOL)
    arm_s, ref_s = _pair("strike", 500, 30, 20, 450)                # the same counts for the Strike team
    assert cells.paired_cell(arm_s, ref_s, "strike", Z95) == got


def test_interval_contains_the_difference_and_narrows_with_n():
    widths = []
    for scale in (1, 4, 16):
        arm, ref = _pair("strike", 50 * scale, 8 * scale, 3 * scale, 39 * scale)
        got = cells.paired_cell(arm, ref, "strike", Z95)
        assert got["ci"][0] < got["diff"] < got["ci"][1]
        widths.append(got["ci"][1] - got["ci"][0])
    assert widths[0] > widths[1] > widths[2]
    wide = cells.paired_cell(*_pair("strike", 50, 8, 3, 39), "strike", cells.adjusted_z(0.05, 150))
    narrow =cells.paired_cell(*_pair("strike", 50, 8, 3, 39), "strike", Z95)
    assert wide["ci"][0] < narrow["ci"][0] and wide["ci"][1] > narrow["ci"][1]


def test_a_degenerate_cell_is_said_and_finite():
    """No flips and every game won by both: phi has a zero denominator, set to 0 and said in ``method``."""
    arm, ref = _pair("guard", 20, 0, 0, 0)
    got = cells.paired_cell(arm, ref, "guard", Z95)
    assert (got["b"], got["c"], got["diff"]) == (0, 0, 0.0)
    assert "phi = 0" in got["method"] and got["ci"][0] <= 0.0 <= got["ci"][1]
    json.dumps(got, allow_nan=False)
    empty = cells.paired_cell(_pg([]), _pg([]), "guard", Z95)
    assert empty["n"] == 0 and empty["diff"] is None and empty["ci"] is None and empty["sign_test_p"] is None
    json.dumps(empty, allow_nan=False)


def test_adjusted_z():
    assert cells.adjusted_z(0.05, 1) == pytest.approx(Z95, abs=1e-6)
    zs = [cells.adjusted_z(0.05, m) for m in (1, 2, 30, 130, 150)]
    assert all(a < b for a, b in zip(zs, zs[1:]))
    assert cells.adjusted_z(0.05, 150) == pytest.approx(NormalDist().inv_cdf(1 - 0.05 / 300), abs=1e-12)
    for alpha, m in ((0.0, 1), (1.0, 1), (0.05, 0), (float("nan"), 1)):
        with pytest.raises(ValueError):
            cells.adjusted_z(alpha, m)


def _wins_sets(seed=3, n=200, k=5):
    rng = np.random.default_rng(seed)
    arm = {f"c{i}": rng.random(n) < 0.4 + 0.05 * i for i in range(k)}
    ref = {f"c{i}": rng.random(n) < 0.45 for i in range(k)}
    return arm, ref


def test_pooled_difference_is_the_mean_of_cell_differences():
    arm, ref = _wins_sets()
    got = cells.pooled_difference(arm, ref, Z95)
    cell_diffs = [arm[k].mean() - ref[k].mean() for k in arm]
    assert got["diff"] == pytest.approx(float(np.mean(cell_diffs)), abs=1e-12)
    assert got["cells"] == len(arm) and got["n"] == 200
    want = compare.paired_difference(compare.per_start_mean(arm, list(arm)), compare.per_start_mean(ref, list(arm)))
    assert got["se"] == pytest.approx(want["se"], abs=1e-15)
    assert cells.pooled_difference({}, {}, Z95) is None                          # an empty stratum
    with pytest.raises(ValueError):
        cells.pooled_difference(arm, {k: v for k, v in list(ref.items())[1:]}, Z95)


def test_the_pooled_ci_uses_the_given_z():
    """compare.paired_difference and scoring.pooled_row hard-wire z = 1.96; the pooled ci is recomputed at the z given."""
    arm, ref = _wins_sets()
    for z in (Z95, cells.adjusted_z(0.05, 7), 1.0):
        got = cells.pooled_difference(arm, ref, z)
        assert got["ci"][0] == pytest.approx(got["diff"] - z * got["se"], abs=1e-15)
        assert got["ci"][1] == pytest.approx(got["diff"] + z * got["se"], abs=1e-15)
    one = cells.pooled_difference({"a": np.array([True])}, {"a": np.array([False])}, Z95)
    assert one["se"] is None and one["ci"] is None and one["diff"] == 1.0                  # one start: no se, no NaN
    json.dumps(one, allow_nan=False)


def test_end_time():
    arm = _pg([GUARD_WIN] * 10, [100, 100, 100, 100, 100, 100, 100, 100, 110, 140])
    ref = _pg([GUARD_WIN] * 10, [100] * 10)
    got = cells.end_time(arm, ref)
    assert set(got) == {"differ_games", "mean_ticks", "median_ticks", "mean_abs_ticks", "p90_abs_ticks"}
    assert got["differ_games"] == 2 and got["mean_ticks"] == pytest.approx(5.0) and got["median_ticks"] == 0.0
    assert got["mean_abs_ticks"] == pytest.approx(5.0)
    assert got["p90_abs_ticks"] == pytest.approx(float(np.percentile([0] * 8 + [10, 40], cells.END_TIME_PCT)))
    early = cells.end_time(_pg([GUARD_WIN] * 2, [90, 100]), _pg([GUARD_WIN] * 2, [100, 100]))
    assert early["mean_ticks"] == pytest.approx(-5.0) and early["mean_abs_ticks"] == pytest.approx(5.0)
    empty = cells.end_time(_pg([]), _pg([]))
    assert empty["differ_games"] == 0 and all(empty[k] is None for k in empty if k != "differ_games")


def test_the_active_rule_and_the_command_error_table():
    """M2-T3's rule (one function M2 reuses): a channel is active where any label on it is not 0.0 on the same rows; a
    skill whose labels are all exactly 0 is the zero-command skill. The table has M2's shape (rmse [4], max_abs [4],
    active [4], rows; zero_skill)."""
    assert cells.active_rule([0.3, 0.0, 1e-9, 0.0]) == [True, False, True, False]
    acc = {"a": {"sum_sq": [4.0, 9.0, 0.0, 0.0], "max_abs": [0.5, 0.5, 0.0, 0.01], "count": 4,
                 "label_max_abs": [1.0, 0.7, 0.0, 0.0]},
           "z": {"sum_sq": [0.0, 0.0, 0.0, 0.0], "max_abs": [0.02, 0.0, 0.0, 0.0], "count": 9,
                 "label_max_abs": [0.0, 0.0, 0.0, 0.0]},
           "unseen": {"sum_sq": [0.0] * 4, "max_abs": [0.0] * 4, "count": 0, "label_max_abs": [0.0] * 4}}
    got = cells.command_errors(acc)
    assert got["zero_skill"] == "z"
    a = got["skills"]["a"]
    assert a["rmse"] == pytest.approx([1.0, 1.5, 0.0, 0.0]) and a["max_abs"] == pytest.approx([0.5, 0.5, 0.0, 0.01])
    assert a["active"] == [True, True, False, False] and a["rows"] == 4
    assert got["skills"]["unseen"] == {"rmse": None, "max_abs": None, "active": [False] * 4, "rows": 0}
    summary = cells.error_summary(got)
    assert summary == {"rmse_active_max": pytest.approx(1.5), "unused_max_abs": pytest.approx(0.01),
                       "zero_skill_max_abs": pytest.approx(0.02)}
    json.dumps(got, allow_nan=False)


@pytest.mark.parametrize("side", SIDES)
def test_the_rule_finds_the_zero_command_skill_of_the_scripts(side):
    """On real observations (``_ste_ls1.team_obs``, live rows), each script's labels through ``active_rule``: the Guard
    team's zero-command skill is guard_parked_centre (scripted.py, 3v3); strike_high and strike_low use vz too."""
    gates = exploit.load_gates(h.SKILLS_GATES)
    cfg, obs = h.team_obs(gates, side)
    live = obs[..., skills._V.alive] > skills.ALIVE_FLAG_MIN
    acc = {}
    for name in skills.team_skills(gates.players, side):
        a = make_strategy(name, side, cfg, obs.shape[0], "cpu", 0).act(obs)[live]
        acc[name] = {"sum_sq": [0.0] * 4, "max_abs": [0.0] * 4, "count": int(live.sum()),
                     "label_max_abs": a.abs().amax(0).tolist()}
    got = cells.command_errors(acc)
    if side == "guard":
        assert got["zero_skill"] == "guard_parked_centre"
    else:
        assert got["zero_skill"] is None
        for name in ("strike_high", "strike_low"):
            assert got["skills"][name]["active"][2]


# ================================================================================================ the committed files
@pytest.fixture(scope="module")
def gates():
    return exploit.load_gates(h.SKILLS_GATES)


@pytest.fixture(scope="module")
def specs(gates):
    return {side: cells.cell_spec(gates, side) for side in SIDES}


@pytest.fixture(scope="module")
def cells_cfg():
    return cal.load_cells(CELLS)


@pytest.fixture(scope="module")
def calcfg():
    return cal.load_calibration(CALIBRATION)


@pytest.mark.parametrize("side", SIDES)
def test_the_mixed_combinations_are_the_draw(specs, cells_cfg, side):
    combos = [tuple(c) for c in cells_cfg["mixed"][side]]
    assert len(combos) == MIXED and len(set(combos)) == MIXED
    assert set(combos) <= set(cells.mixed_pool(specs[side]))
    assert combos == cells.draw_mixed(specs[side], MIXED, int(cells_cfg["mixed"]["seed"]))


@pytest.mark.parametrize("side", SIDES)
def test_the_permutation_is_a_derangement(specs, cells_cfg, side):
    perm = list(cells_cfg["permutation"][side])
    k = len(specs[side].players)
    assert sorted(perm) == list(range(k)) and all(p != i for i, p in enumerate(perm))


def test_the_committed_pins_hold(calcfg):
    src = calcfg["source"]
    assert exploit.sha256_file(ROOT / src["skills_gates"]) == src["skills_gates_sha256"]
    assert exploit.sha256_file(ROOT / src["cells"]) == src["cells_sha256"]
    assert exploit.sha256_file(SCRIPTED) == src["scripted_sha256"] and src["scripted_sha256"].startswith("b7ccafdeaa4b01c7")
    assert ROOT / src["skills_gates"] == h.SKILLS_GATES and ROOT / src["cells"] == CELLS


def test_one_ruler(calcfg, cells_cfg):
    """B-6: the cell size is written once, in cells.toml [read]; calibration.toml holds no game count."""
    assert int(cells_cfg["read"]["games_per_cell"]) == 1000
    text = CALIBRATION.read_text()
    assert "games" not in json.dumps(calcfg) and "games_per_cell =" not in text
    assert calcfg["run"]["device"] == "cpu" and 0 < calcfg["intervals"]["alpha"] < 1


def test_the_calibration_loader_refuses_a_missing_or_unknown_key(tmp_path):
    text = CALIBRATION.read_text()
    bad = tmp_path / "c.toml"
    bad.write_text(text.replace("\nseed = 150101", "\n"))
    with pytest.raises(ValueError, match="seed"):
        cal.load_calibration(bad)
    bad.write_text(text.replace("[scale]\n", "[scale]\nextra = 1\n"))
    with pytest.raises(ValueError, match="extra"):
        cal.load_calibration(bad)
    bad.write_text(text.replace("channels = [0, 1, 2]", "channels = [0, 4]"))
    with pytest.raises(ValueError):
        cal.load_calibration(bad)


@pytest.mark.parametrize("side", SIDES)
def test_the_gated_cells_are_counted_not_typed(gates, specs, cells_cfg, side):
    """m = (K + the mixed combinations) x the other team's [players] (the info opponents are not gated)."""
    assert cal.gated_m(specs[side], cells_cfg, gates) == GATED_M[side]
    every = cal.side_cells(specs[side], cells_cfg, gates)
    gated = [c for c in every if c.kind != cal.INFO]
    assert len(gated) == GATED_M[side]
    assert [c.index for c in every] == list(range(len(every)))
    info = [c for c in every if c.kind == cal.INFO]
    assert {c.opponent for c in info} == set(cells_cfg["info_opponents"][side])
    assert len(info) == (len(specs[side].players) + MIXED) * len(cells_cfg["info_opponents"][side])


def _labels_from_scripts(gates, side):
    cfg, obs = h.team_obs(gates, side)
    live = obs[..., skills._V.alive] > skills.ALIVE_FLAG_MIN
    acc = {name: {"sum_sq": [0.0] * 4, "max_abs": [0.0] * 4, "count": int(live.sum()),
                  "label_max_abs": make_strategy(name, side, cfg, obs.shape[0], "cpu", 0).act(obs)[live].abs().amax(0).tolist()}
           for name in skills.team_skills(gates.players, side)}
    return cal.labels_of(acc)


@pytest.mark.parametrize("side", SIDES)
def test_every_arm_and_cell_builds_with_a_unique_name(gates, specs, cells_cfg, calcfg, side):
    """No play: every arm of the committed calibration x every cell it plays, from the committed files; each player
    name is unique and carries a C6 prefix, each player one object (correction: ``exploit._team_split`` wraps
    players[name] once per cell slice)."""
    cfg = exploit.variant_cfg(gates, "base")
    labels = _labels_from_scripts(gates, side)
    every = cal.side_cells(specs[side], cells_cfg, gates)
    names, objects, kept = set(), set(), []             # kept: alive, so no id is reused
    arms = [cal.REFERENCE_ARM] + cal.arms_of(calcfg, side)
    assert [a.name for a in arms[:2]] == [cal.REFERENCE, cal.IDENTITY]
    assert len({a.name for a in arms}) == len(arms)
    for arm in arms:
        mine = cal.arm_cells(arm, every, labels)
        if arm.kind == cal.ZERO_BIAS:
            assert {c.choice["script"] for c in mine} == ({"guard_parked_centre"} if side == "guard" else set())
            assert {c.kind for c in mine} <= {cal.FIXED}
        if arm.kind == cal.SWITCH:
            assert mine and all(cal.SWITCHES[arm.switch][1] in c.choice["flies"] for c in mine)
        players, cell_list, _ = cal.batch_players(arm, mine, specs[side], cfg, 2, "cpu", 110000, labels, calcfg)
        assert len(cell_list) == len(mine) == len(players)
        for name, p in players.items():
            assert name.startswith(cells.PREFIXES) and p.name == name and name not in names and id(p) not in objects
            names.add(name)
            objects.add(id(p))
            kept.append(p)
    reference = cal.arm_cells(cal.REFERENCE_ARM, every, labels)
    assert all(c.kind != cal.FIXED for c in reference)                      # fixed cells: T44 is the reference


# ================================================================================================ tiny runs
def _argv(out, side="guard", opponents=(FAST_OPPONENT,), arms=(NOISE_ARM,), mixed=TINY_MIXED, extra=()):
    argv = ["--calibration", str(CALIBRATION), "--side", side, "--out", str(out),
            "--expect-sha256", exploit.sha256_file(CALIBRATION), "--games", str(TINY_GAMES),
            "--mixed", str(mixed), "--opponents", *opponents, "--arms", *arms]
    return argv + list(extra)


class _PlayLog:
    """Counts ``exploit.play_cells`` calls and the player names each one flew."""

    def __init__(self, real):
        self.real, self.calls = real, []

    def __call__(self, *args, **kw):
        self.calls.append(sorted((kw.get("players") or {}).keys()))
        return self.real(*args, **kw)


@pytest.fixture(scope="module")
def tiny(tmp_path_factory):
    """The Guard team's tiny run: one opponent, 5 fixed + 2 mixed cells, the reference, identity and one noise arm, at
    the committed chunk size (6: two chunks). Returns (out folder, exit code, the play log)."""
    out = tmp_path_factory.mktemp("cal") / "guard"
    with pytest.MonkeyPatch.context() as mp:
        log = _PlayLog(exploit.play_cells)
        mp.setattr(exploit, "play_cells", log)
        code = cal.main(_argv(out))
    return out, code, log


def _results(out):
    return json.loads((out / cal.RESULTS).read_text())


def test_the_tiny_run_writes_the_documented_keys(tiny, gates):
    out, code, _ = tiny
    assert code == EXIT_DONE
    res = _results(out)
    assert list(res)[-1] == "complete" and res["complete"] is True
    assert set(res) == cal.RESULT_KEYS
    assert res["of_record"] is False and res["side"] == "guard" and res["games_per_cell"] == TINY_GAMES
    assert res["ticks_cap"] == int(gates.run["ticks_cap"]) and res["seed"] == 110000 and res["hold_ticks"] == 1
    assert {v["status"] for v in res["controls"].values()} == {scoring.PASS}
    assert res["controls"] == json.loads((out / cal.CONTROLS_FILE).read_text())
    assert set(res["arms"]) == {cal.IDENTITY, NOISE_ARM}
    for entry in res["cells"]:
        assert set(entry) == cal.CELL_KEYS
    for arm in res["arms"].values():
        assert set(arm) == cal.ARM_KEYS
        assert set(arm["pooled"]) == {"all", "fixed", "mixed", "info"} and arm["pooled"]["info"] is None
        assert set(arm["errors"]) == {"skills", "zero_skill"}
    assert (out / cal.RESULTS_MD).is_file() and "No pass or fail" in (out / cal.RESULTS_MD).read_text()
    assert res["labels"]["zero_skills"] == ["guard_parked_centre"]
    assert len(list(out.glob("batch_*.npz"))) == len(res["batches"])


def test_no_nan_in_results(tiny):
    """results.json and every statistic on a degenerate or empty stratum are JSON without NaN (None instead)."""
    json.dumps(_results(tiny[0]), allow_nan=False)
    degenerate = [cells.paired_cell(*_pair("guard", 5, 0, 0, 0), "guard", Z95), cells.paired_cell(_pg([]), _pg([]), "guard", Z95),
                  cells.pooled_difference({}, {}, Z95),
                  cells.pooled_difference({"a": np.array([True])}, {"a": np.array([True])}, Z95),
                  cells.end_time(_pg([]), _pg([])), cells.command_errors({"s": {"sum_sq": [0.0] * 4, "max_abs": [0.0] * 4,
                                                                               "count": 0, "label_max_abs": [0.0] * 4}})]
    json.dumps(degenerate, allow_nan=False)
    json.dumps(cells.error_summary(degenerate[-1]), allow_nan=False)


def test_the_identity_arm_has_no_flip_and_the_noise_arm_errs(tiny):
    res = _results(tiny[0])
    ident = [c for c in res["cells"] if c["arm"] == cal.IDENTITY]
    assert len(ident) == 5 + TINY_MIXED and all(c["b"] == c["c"] == 0 and c["diff"] == 0.0 for c in ident)
    assert res["arms"][cal.IDENTITY]["error_summary"]["rmse_active_max"] == 0.0
    noise = res["arms"][NOISE_ARM]["errors"]["skills"]
    assert all(s["rows"] > 0 for s in noise.values())
    assert max(max(s["max_abs"]) for s in noise.values()) <= 0.05 + 1e-6
    assert noise["guard_mark_edge"]["rmse"][0] > 0


def test_both_intervals_are_written(tiny):
    res = _results(tiny[0])
    iv = res["intervals"]
    assert {"alpha", "m", "z_cell", "z_pooled", "interval", "correction"} <= set(iv)
    assert iv["m"] == {"guard": GATED_M["guard"]}                          # the committed layout's m, not the tiny run's
    assert iv["z_pooled"] == pytest.approx(cells.adjusted_z(iv["alpha"], 1))
    assert iv["z_cell"] == pytest.approx(cells.adjusted_z(iv["alpha"], GATED_M["guard"]))
    for c in res["cells"] + res["permuted"]["cells"]:
        assert c["ci_adjusted"][0] <= c["ci_plain"][0] and c["ci_adjusted"][1] >= c["ci_plain"][1]


def test_the_permuted_scripts_are_read_without_play(tiny, gates, specs, cells_cfg):
    out, _, log = tiny
    res = _results(out)
    assert len(log.calls) == len(res["batches"])                            # one play_cells call per played batch
    assert not [n for call in log.calls for n in call if n.startswith(cells.PERM_PREFIX)]
    ref = exploit.load_reference(ROOT / gates.reference["file"])
    players = specs["guard"].players
    perm = cells_cfg["permutation"]["guard"]
    got = res["permuted"]["cells"]
    assert len(got) == len(players) and res["permuted"]["permutation"] == perm
    z_plain, z_cell = res["intervals"]["z_pooled"], res["intervals"]["z_cell"]
    for k, entry in enumerate(got):
        arm = {f: v[:TINY_GAMES] for f, v in ref.cell("base", players[perm[k]], FAST_OPPONENT).items()}
        t44 = {f: v[:TINY_GAMES] for f, v in ref.cell("base", players[k], FAST_OPPONENT).items()}
        want = cells.paired_cell(arm, t44, "guard", z_plain)
        assert (entry["code"], entry["flies"], entry["opponent"]) == (players[k], players[perm[k]], FAST_OPPONENT)
        assert (entry["b"], entry["c"], entry["n"]) == (want["b"], want["c"], want["n"])
        assert entry["ci_plain"] == pytest.approx(want["ci"])
        assert entry["ci_adjusted"] == pytest.approx(cells.paired_cell(arm, t44, "guard", z_cell)["ci"])


def test_a_finished_folder_exits_2(tiny):
    out = tiny[0]
    before = (out / cal.RESULTS).read_bytes()
    assert cal.main(_argv(out)) == EXIT_REFUSED
    assert (out / cal.RESULTS).read_bytes() == before


def test_a_pin_off_is_refused(tmp_path):
    argv = _argv(tmp_path / "a")
    argv[argv.index("--expect-sha256") + 1] = "0" * 64
    assert cal.main(argv) == EXIT_REFUSED
    moved = tmp_path / "calibration.toml"
    moved.write_text(CALIBRATION.read_text().replace('cells_sha256 = "', 'cells_sha256 = "0'))
    argv = _argv(tmp_path / "b")
    argv[argv.index("--calibration") + 1] = str(moved)
    argv[argv.index("--expect-sha256") + 1] = exploit.sha256_file(moved)
    assert cal.main(argv) == EXIT_REFUSED
    assert cal.main(_argv(tmp_path / "c", arms=("noise=0.07",))) == EXIT_REFUSED        # no such arm
    assert cal.main(_argv(tmp_path / "d", opponents=("guard_field",))) == EXIT_REFUSED  # not an opponent of the Guard team
    assert not (tmp_path / "a" / cal.RESULTS).exists()


def test_a_forced_control_failure_writes_controls_only_and_exits_6(tmp_path, monkeypatch):
    out = tmp_path / "fail"
    monkeypatch.setattr(exploit, "replay_ok", lambda *a, **k: (False, "forced"))
    argv = _argv(out, mixed=0, arms=())
    assert cal.main(argv) == EXIT_CONTROL_FAILED
    controls = json.loads((out / cal.CONTROLS_FILE).read_text())
    assert scoring.FAIL in {v["status"] for v in controls.values()}
    assert not (out / cal.RESULTS).exists() and not (out / cal.RESULTS_MD).exists()
    monkeypatch.undo()
    assert cal.main(argv) == EXIT_CONTROL_FAILED                            # terminal: a new run needs a new folder


def _per_game(out):
    """{(arm, choice, opponent): {key: per-game array}} of a finished folder, from its batch files."""
    res = _results(out)
    got = {}
    for c in res["cells"]:
        g = c["games"]
        with np.load(out / g["file"]) as z:
            got[(c["arm"], c["choice"], c["opponent"])] = {k: z[k][g["start"]:g["stop"]] for k in exploit.EXACT}
    return got


def _cell_rows(res):
    return [{k: v for k, v in c.items() if k != "games"} for c in res["cells"]]


def test_chunking_does_not_change_a_game_and_a_stopped_run_resumes_to_the_same_results(tiny, tmp_path, monkeypatch):
    """The committed chunk (6) against chunks of 2 give the same games, cell for cell. A chunk-2 run stopped on request
    (SIGINT to this process during its third batch: exit 4, the partial batch dropped) resumes with the same command to
    the very results.json of an uninterrupted chunk-2 run."""
    whole = tmp_path / "whole"
    assert cal.main(_argv(whole, extra=("--chunk", "2"))) == EXIT_DONE
    a, b = _per_game(tiny[0]), _per_game(whole)
    assert a.keys() == b.keys() and len(a) == 2 * (5 + TINY_MIXED)
    for key in a:
        for f in exploit.EXACT:
            assert (a[key][f] == b[key][f]).all(), (key, f)
    assert _cell_rows(_results(tiny[0])) == _cell_rows(_results(whole))
    assert _results(tiny[0])["arms"] == _results(whole)["arms"]

    stopped = tmp_path / "stopped"
    real, seen = exploit.play_cells, [0]

    def interrupting(*args, **kw):
        seen[0] += 1
        if seen[0] == 3:
            os.kill(os.getpid(), signal.SIGINT)
        return real(*args, **kw)

    monkeypatch.setattr(exploit, "play_cells", interrupting)
    assert cal.main(_argv(stopped, extra=("--chunk", "2"))) == EXIT_INTERRUPTED
    assert not (stopped / cal.RESULTS).exists() and len(list(stopped.glob("batch_*.npz"))) == 2
    monkeypatch.setattr(exploit, "play_cells", real)
    assert cal.main(_argv(stopped, extra=("--chunk", "2"))) == EXIT_DONE
    assert (stopped / cal.RESULTS).read_bytes() == (whole / cal.RESULTS).read_bytes()


def test_a_run_at_its_cap_exits_3_and_resumes(tmp_path):
    out = tmp_path / "cap"
    argv = _argv(out, mixed=0, arms=())
    assert cal.main(argv + ["--cap-h", "1e-12"]) == EXIT_CAP
    assert not (out / cal.RESULTS).exists()
    changed = list(argv)
    changed[changed.index("--games") + 1] = str(TINY_GAMES + 1)
    assert cal.main(changed) == EXIT_REFUSED                                # another layout in the same folder
    assert cal.main(argv) == EXIT_DONE
    assert _results(out)["complete"] is True


def test_the_info_cells_never_ask_t44_for_a_cell(tmp_path, monkeypatch):
    """The Strike team against guard_mark_inside (no T44 cell): the scripts' reference arm is played; ``ref.cell`` is
    never asked for it; the cells are INFO (out of control (a), of m and of the permuted read)."""
    asked = []
    real = exploit.Reference.cell

    def spy(self, variant, guard, strike):
        asked.append((variant, guard, strike))
        return real(self, variant, guard, strike)

    monkeypatch.setattr(exploit.Reference, "cell", spy)
    out = tmp_path / "info"
    assert cal.main(_argv(out, side="strike", opponents=("guard_mark_inside",), mixed=1, arms=())) == EXIT_DONE
    assert not [a for a in asked if "guard_mark_inside" in a]
    res = _results(out)
    assert {c["kind"] for c in res["cells"]} == {cal.INFO} and res["permuted"]["cells"] == []
    assert res["intervals"]["m"] == {"strike": GATED_M["strike"]}
    assert all(c["b"] == c["c"] == 0 for c in res["cells"])
    assert res["arms"][cal.IDENTITY]["pooled"]["all"] is None and res["arms"][cal.IDENTITY]["pooled"]["info"]["diff"] == 0.0
    assert {v["status"] for v in res["controls"].values()} == {scoring.PASS}


def test_the_reference_is_read_under_the_variants_reference_name():
    """R51 (route 3 at the 1.15 m tag, ste_learning/drafts/LS1_1P15_SWITCH.md step A): the 1.15 m skills gate file keeps
    the variant name ``base`` (``distil.VARIANT``) with ``reference_variant = "tag_1p15"`` (T50's reference file). The
    calibration reads its reference cells under that name, as the copy check does (``exploit.ref_variant``)."""
    from types import SimpleNamespace as NS
    pg = {"outcome": np.arange(6), "end_step": np.arange(6)}
    ref = exploit.Reference(np.zeros((6, 6, 3), np.float32), np.zeros(6, bool),
                            {("tag_1p15", "guard_field", "strike_straight"): pg}, {})
    gates = NS(variants={"base": {"game": "tag_1p15", "reference_variant": "tag_1p15"}})
    ctx = NS(ref=ref, variant="base", gates=gates, spec=NS(side="guard"), n=4)
    cell = NS(choice={"script": "guard_field"}, opponent="strike_straight")
    got = cal.t44_of(ctx, cell)
    assert got["outcome"].tolist() == [0, 1, 2, 3]
    # without a reference_variant the variant's own name is read, as before
    ref_base = exploit.Reference(ref.starts_m, ref.start_miss, {("base", "guard_field", "strike_straight"): pg}, {})
    ctx_base = NS(ref=ref_base, variant="base", gates=NS(variants={"base": {"game": "base"}}), spec=NS(side="guard"), n=4)
    assert cal.t44_of(ctx_base, cell)["end_step"].tolist() == [0, 1, 2, 3]
