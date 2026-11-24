"""STE task L2.6 Scripted games, tier 1 against tier 2, new rules (INFO): the game files, the gate file
(configs/ste_l2/l26_gates.toml) and the driver (scripts/ste_tier12_l26.py); spec ste_learning/drafts/L2_6_SPEC.md.

CPU only. Checked here: each L2.6 game file is its L2.5 parent value for value but for the keys its header marks; the gate
file pins every file it names and its groups' tier-2 games differ from their tier-1 games in the backend, the parameter
file and (error arm only) the tier-1 estimate error; the batch layout; the projection (protected groups fit the cap in
the worst case); the reading words, fixed before the run; and the driver end to end on the PyTorch reference world
(--dry-cpu) at a test size, every control passing and every reading written."""
from __future__ import annotations

import json
import sys
import tomllib
from pathlib import Path

import pytest

from svg_training.ste import exploit, shared, tier2_train as T

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import ste_tier12_l26 as tool  # noqa: E402

L2 = ROOT / "configs" / "ste_l2"
GATES = L2 / "l26_gates.toml"
ERR_FILE = ROOT / "configs" / "ste_l1" / "base_err_nominal.toml"


def _cfg(path: Path):
    return exploit.load_game_cfg_file(path)


# ================================================================================================ the game files
@pytest.mark.parametrize("name, parent, err", [
    ("l26_landing_tag_1p15", "l25_landing", False),
    ("l26_landing_gy_tag_1p15", "l25_landing_gy", False),
    ("l26_landing_tag_1p15_err", "l25_landing", True),
    ("l26_landing_gy_tag_1p15_err", "l25_landing_gy", True),
])
def test_each_file_is_its_l25_parent_but_for_the_tag_radius_and_the_tier1_error(name, parent, err):
    mine, theirs = _cfg(L2 / f"{name}.toml"), _cfg(L2 / f"{parent}.toml")
    diff = T.cfg_differences(theirs, mine)
    want = {"tag.radius_m"} | ({d for d in diff if d.startswith("estimate_error.")} if err else set())
    assert set(diff) == want and "tag.radius_m" in diff
    assert mine.tag.radius_m == 1.15 and theirs.tag.radius_m == 1.6
    if err:
        assert mine.estimate_error == _cfg(ERR_FILE).estimate_error and mine.estimate_error.enabled
        assert mine.estimate_error.commander_reads == "true"
    else:
        assert not mine.estimate_error.enabled
    head = (L2 / f"{name}.toml").read_text().splitlines()[0]
    assert head.startswith("# STE task L2.6") and name in head


def test_the_1p15_files_keep_landing_and_their_share():
    assert _cfg(L2 / "l26_landing_tag_1p15.toml").landing.enabled
    assert _cfg(L2 / "l26_landing_tag_1p15.toml").filter.share == "equal"
    assert _cfg(L2 / "l26_landing_gy_tag_1p15.toml").filter.share == "guard_yields"


# ================================================================================================ the gate file
def test_gate_file_loads_and_pins_the_real_files():
    s = tool.load_settings(GATES)
    assert tool.pin_problems(s) == []
    assert s["job"]["task"] == "L2.6" and s["job"]["games"] == 1000 and s["job"]["ticks_cap"] == 2400
    assert s["job"]["cap_h"] <= 1.5                                   # the task cap (WORK_BREAKDOWN L2.6)


def test_gate_file_refuses_an_unknown_key(tmp_path):
    bad = tmp_path / "g.toml"
    bad.write_text(GATES.read_text().replace("[job]\n", "[job]\nsurprise = 1\n", 1))
    with pytest.raises(ValueError, match="surprise"):
        tool.load_settings(bad)


def test_gate_file_refuses_a_rule_pair_naming_no_group(tmp_path):
    bad = tmp_path / "g.toml"
    bad.write_text(GATES.read_text().replace('to = "landing_1p6" }', 'to = "nowhere" }', 1))
    with pytest.raises(ValueError, match="nowhere"):
        tool.load_settings(bad)


def test_the_batch_layout():
    s = tool.load_settings(GATES)
    lay = tool.layout(s)
    assert len(lay.main) == 6 and len(lay.cells) == 7
    assert lay.cells[:6] == lay.main and lay.cells[6] == tuple(s["cells"]["repeat"])
    assert lay.repeat_pair == (6, lay.main.index(tuple(s["cells"]["repeat"])))
    assert ("guard_parked_centre", "strike_straight") in lay.main      # the tier-2 known-answer cell


def test_every_group_differs_between_tiers_only_in_backend_params_and_the_tier1_error():
    s = tool.load_settings(GATES)
    for g in s["groups"]:
        ctl = tool.condition_check(s, g)
        assert ctl["status"] == tool.PASS, (g["name"], ctl["detail"])
    names = [g["name"] for g in s["groups"]]
    assert names[0] == "base_1p6" and s["known"]["t2_group"] == "base_1p6"
    assert [g["protected"] for g in s["groups"]] == sorted((g["protected"] for g in s["groups"]), reverse=True)


def test_condition_check_fails_a_tier2_game_with_another_rule(tmp_path):
    s = tool.load_settings(GATES)
    g = dict(next(x for x in s["groups"] if x["name"] == "landing_1p6"), tier2_game="l25_landing_gy")
    assert tool.condition_check(s, g)["status"] == tool.FAIL


def test_counts_known_answers_are_t70s():
    s = tool.load_settings(GATES)
    by = {g["name"]: g for g in s["groups"]}
    assert by["landing_1p6"]["tier1_known_holds"] == [802, 534, 477, 807, 895, 716]
    assert by["landing_gy_1p6"]["tier1_known_holds"] == [803, 534, 477, 808, 902, 716]
    assert by["base_1p6"]["tier1_known"] == "t44"


# ================================================================================================ the projection
def test_protected_groups_fit_the_cap_in_the_worst_case_and_the_rest_may_drop():
    s = tool.load_settings(GATES)
    p = tool.launch_projection(s)
    assert p["protected_s"] * s["projection"]["safety_factor"] <= p["cap_s"] == s["job"]["cap_h"] * 3600
    assert p["fits"] is True
    assert p["total_s"] * s["projection"]["safety_factor"] > p["cap_s"]   # in the worst case some droppable group drops
    w = {g["name"]: tool.worst_seconds(s, g) for g in s["groups"]}
    assert w["landing_gy_1p15"]["tier2"] == pytest.approx(0.19 * 2400 * 2.5)
    assert w["landing_1p15"]["tier1"] == pytest.approx(0.05 * 2400)


def test_should_play_rule():
    assert tool.should_play(True, 5000.0, 4000.0, 5400.0, 1.1) is True            # protected: always (launch checked)
    assert tool.should_play(False, 1000.0, 3000.0, 5400.0, 1.1) is True           # 1000 + 3300 <= 5400
    assert tool.should_play(False, 2500.0, 3000.0, 5400.0, 1.1) is False          # 2500 + 3300 > 5400


def test_measured_rates_replace_the_table():
    s = tool.load_settings(GATES)
    g = next(x for x in s["groups"] if x["name"] == "landing_gy_1p6")
    w = tool.worst_seconds(s, g, measured={(1, "guard_yields"): 0.01, (2, "guard_yields"): 0.1})
    assert w == {"tier1": pytest.approx(24.0), "tier2": pytest.approx(240.0)}


# ================================================================================================ the reading words
def test_predict_words():
    assert tool.predict_word(800, 1000, 790, 1000, 0.10) == tool.PREDICTS
    assert tool.predict_word(800, 1000, 730, 1000, 0.10) == tool.INSIDE_T13      # separated, gap 0.07
    assert tool.predict_word(800, 1000, 650, 1000, 0.10) == tool.BEYOND_T13      # gap 0.15
    assert tool.predict_word(951, 1000, 1, 1000, 0.10) == tool.BEYOND_T13        # T13's mark edge v straight
    assert tool.predict_word(14, 16, 9, 16, 0.10) == tool.BEYOND_T13             # overlapping (small n) but gap 0.31: T13 first
    assert tool.predict_word(0, 0, 3, 3, 0.10) == tool.NO_GAMES                 # no finished game on a tier: no word
    assert tool.effect_word(2, 3, 0, 0) == tool.NO_GAMES
    assert tool.group_word([tool.PREDICTS] * 5 + [tool.NO_GAMES]) == tool.GROUP_NO_WORD
    assert tool.cross_word(tool.NO_GAMES, tool.RAISES) == tool.NO_GAMES


def test_group_words():
    P, I, B = tool.PREDICTS, tool.INSIDE_T13, tool.BEYOND_T13
    assert tool.group_word([P] * 6) == tool.GROUP_PREDICTS
    assert tool.group_word([P] * 5 + [I]) == tool.GROUP_INSIDE
    assert tool.group_word([P] * 5 + [B]) == tool.GROUP_NOT


def test_effect_and_cross_words():
    assert tool.effect_word(844, 1000, 895, 1000) == tool.RAISES                 # T70's landing cell, its own word
    assert tool.effect_word(808, 1000, 802, 1000) == tool.NO_CHANGE              # overlapping intervals
    assert tool.effect_word(752, 1000, 86, 1000) == tool.LOWERS
    assert tool.effect_word(500, 1000, 600, 1000) == tool.RAISES
    assert tool.cross_word(tool.LOWERS, tool.LOWERS) == tool.AGREE
    assert tool.cross_word(tool.NO_CHANGE, tool.NO_CHANGE) == tool.AGREE
    assert tool.cross_word(tool.RAISES, tool.LOWERS) == tool.DISAGREE
    assert tool.cross_word(tool.RAISES, tool.NO_CHANGE) == tool.ONLY_T1
    assert tool.cross_word(tool.NO_CHANGE, tool.LOWERS) == tool.ONLY_T2


def test_beyond_copy_noise():
    assert tool.beyond_noise(1, 0, 6) is True                     # an exact repeat: one changed game is enough
    assert tool.beyond_noise(0, 0, 6) is False
    assert tool.beyond_noise(30, 5, 6) is False                   # 30 <= 6 x 5
    assert tool.beyond_noise(31, 5, 6) is True


# ================================================================================================ the driver, end to end
N, TICKS = 3, 30


def _value(v) -> str:
    if isinstance(v, dict):
        return "{ " + ", ".join(f"{k} = {_value(x)}" for k, x in v.items()) + " }"
    if isinstance(v, list):
        return "[" + ", ".join(_value(x) for x in v) + "]"
    if isinstance(v, bool):
        return "true" if v else "false"
    return json.dumps(v) if isinstance(v, str) else repr(v)


def write_settings(path: Path, **job) -> Path:
    """The committed gate file at the test size (device cpu, N games, a short clock): known answers are NOT_CHECKED."""
    s = tomllib.loads(GATES.read_text())
    s["job"].update({"device": "cpu", "games": N, "ticks_cap": TICKS, **job})
    lines = []
    for sec in ("job", "reference", "cells", "params", "games", "known", "controls", "projection", "reading"):
        lines += [f"[{sec}]", *[f"{k} = {_value(v)}" for k, v in s[sec].items()], ""]
    for g in s["groups"]:
        lines += ["[[groups]]", *[f"{k} = {_value(v)}" for k, v in g.items()], ""]
    path.write_text("\n".join(lines))
    return path


@pytest.fixture(scope="module")
def dry_case(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("l26")
    mp = pytest.MonkeyPatch()
    mp.setenv(shared.SHARED_ENV, str(tmp / "shared"))
    mp.setenv(shared.LEGACY_LOGS_ENV, "")
    settings = write_settings(tmp / "s.toml")
    rd = tmp / "run"
    args = ["--settings", str(settings), "--run-dir", str(rd), "--cap-h", "1.5", "--dry-cpu"]
    code = tool.main(args)
    again = tool.main(args)                                        # a finished folder: nothing to do
    mp.undo()
    return code, again, rd


def test_dry_run_plays_every_group_on_both_tiers_with_every_control_passing(dry_case):
    code, again, rd = dry_case
    assert code == 0 and again == 0
    controls = json.loads((rd / "controls.json").read_text())
    assert {v["status"] for v in controls.values()} <= {"PASS", "INFO", "NOT_CHECKED"}
    assert controls["tag_fires_t2"]["status"] == "PASS"
    s = tool.load_settings(GATES)
    for g in s["groups"]:
        for key in ("condition", "tier1", "tier2", "repeat_t1", "repeat_t2"):
            assert f"{key}_{g['name']}" in controls, (key, g["name"])
        assert any(k.startswith(f"physics_agreement_{g['name']}_launch") for k in controls)
    assert controls["known_t2"]["status"] == "NOT_CHECKED"           # test size: the band is for 1,000 games
    assert controls["repeat_t2_landing_1p15_err"]["status"] == "INFO"   # each copy draws its own error


def test_dry_run_results_hold_every_reading(dry_case):
    _, _, rd = dry_case
    res = json.loads((rd / "results.json").read_text())
    assert res["complete"] is True and res["dry_cpu"] is True
    s = tool.load_settings(GATES)
    assert [g["name"] for g in res["groups"]] == [g["name"] for g in s["groups"]]
    for g in res["groups"]:
        assert g["played"] is True
        assert g["word"] in (tool.GROUP_PREDICTS, tool.GROUP_INSIDE, tool.GROUP_NOT, tool.GROUP_NO_WORD)
        assert len(g["cells"]) == 6
        for c in g["cells"]:
            assert c["word"] in (tool.PREDICTS, tool.INSIDE_T13, tool.BEYOND_T13, tool.NO_GAMES)   # short test clock
            assert c["tier1"]["n"] + c["tier1"]["unfinished"] == N and "agreement" in c
    assert {p["name"] for p in res["rule_pairs"]} == {p["name"] for p in s["reading"]["rule_pairs"]}
    for p in res["rule_pairs"]:
        assert p["read"] is True and len(p["cells"]) == 6
        for c in p["cells"]:
            assert set(c) >= {"cell", "tier1", "tier2", "cross"}
    md = (rd / "results.md").read_text()
    assert "observed in the training simulator" in md.lower() and "tier 2" in md


def test_tier2_batches_ran_the_physics_drone(dry_case):
    _, _, rd = dry_case
    games = sorted(p.name for p in (rd / "games").glob("*.npz"))
    assert "landing_gy_1p15_t2.npz" in games and "landing_gy_1p15_t1.npz" in games
    for tier in (1, 2):                                            # the batch's own record of the drone model it ran
        meta = json.loads((rd / "games" / f"landing_gy_1p15_t{tier}.json").read_text())
        assert T.batch_tier(meta) == tier and meta["physics_nonfinite"] == 0


def test_a_changed_pin_is_refused(tmp_path):
    settings = tmp_path / "s.toml"
    settings.write_text(GATES.read_text().replace("42d18251", "00000000", 1))
    code = tool.main(["--settings", str(settings), "--run-dir", str(tmp_path / "run"), "--cap-h", "1.5", "--dry-cpu"])
    assert code == 2


def test_cap_must_equal_the_settings(tmp_path):
    code = tool.main(["--settings", str(GATES), "--run-dir", str(ROOT / "runs" / "never_l26"), "--cap-h", "0.5",
                      "--dry-cpu"])
    assert code == 2 and not (ROOT / "runs" / "never_l26").exists()


def test_isaac_launch_needs_headless(tmp_path):
    assert tool.pre_isaac_problem(["--run-dir", str(tmp_path)])[0] == 2
    assert tool.pre_isaac_problem(["--headless", "--run-dir", str(tmp_path)]) is None
