"""STE L1 side track tooling (spec ste_learning/drafts/L1_SIDE_TRACK_SPEC.md v2): an explicit training opponent per
variant and side (``train_opponent``), a training game (``train_game``), per-variant trainer settings with
``discount_factor``, a per-variant run 0, the 30 s clock game file, the L1.11 / L1.13 gate files (equal to their sources
but for the listed keys; seeds new; caps by the driver's time rule), the pilot bundled in ste_provisional, and the shared
scoring module. The scoring tool itself is in tests/test_ste_score_matrix.py. CPU only."""
from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

import numpy as np
import pytest

from svg_training.core.rewards import GUARD_WIN, RUNNING, STRIKE_WIN
from svg_training.opponents.scripted import REGISTRY
from svg_training.ste import exploit, scoring, shared
from svg_training.ste.config import load_ste_learning
from svg_training.ste.exploit_train import effective_cfg

ROOT = exploit.ROOT
sys.path.insert(0, str(ROOT / "scripts"))
import ste_exploit_l012 as driver  # noqa: E402

L1 = ROOT / "configs" / "ste_l1"
L111, L113 = L1 / "l111_strike_gates.toml", L1 / "l113_gates.toml"
L012, L012C = ROOT / "configs" / "ste_l012" / "gates.toml", ROOT / "configs" / "ste_l012c" / "strike_gates.toml"
TAG115, CLOCK30 = ROOT / "configs" / "ste_l011" / "tag_1p15.toml", L1 / "tag_1p15_clock30.toml"
PILOT = ROOT / "ste_provisional" / "pilots" / "2026-11-21_ste_l012_pilot" / "pilot.json"
PILOT_SHA = "b029a9013098260679159a97a27471a0f6c15ae6239d367fc35f2f0c694a9d12"   # what T46, T52 and T55 named
EARLIER = [ROOT / "configs" / "ste_l012" / "gates.toml", ROOT / "configs" / "ste_l012" / "smoke_gates.toml",
           ROOT / "configs" / "ste_l012b" / "gates.toml", L012C, ROOT / "configs" / "ste_l012c" / "guard_gates.toml",
           *sorted((ROOT / "ste_provisional" / "players").glob("*/gates.toml"))]


@pytest.fixture(autouse=True)
def scratch_shared(tmp_path, monkeypatch):
    monkeypatch.setenv(shared.SHARED_ENV, str(tmp_path / "shared"))
    monkeypatch.setenv(shared.LEGACY_LOGS_ENV, "")


def text_with(path: Path, tmp_path: Path, name: str = "gates.toml", **replace) -> Path:
    """``path``'s text with lines replaced (old = new), written to ``tmp_path / name``."""
    text = path.read_text()
    for old, new in replace.items():
        assert text.count(old) >= 1, old
        text = text.replace(old, new, 1)
    out = tmp_path / name
    out.write_text(text)
    return out


SMALL = {"device": '"cpu"', "eval_games": "4", "ticks_cap": "160", "curve_games": "4", "num_games": "4", "rollouts": "2",
         "learning_epochs": "1", "mini_batches": "1", "curve_every_updates": "1", "final_reserve_s": "60",
         "game_steps_per_run": "96"}


def small(path: Path, tmp_path: Path, name: str = "gates.toml", **more) -> Path:
    """A CPU copy of a gate file at a test size (one update = 2 x 12 x 4 = 96 game-steps): the first line of each SMALL
    key replaced (``[trainer] num_games`` comes before ``[pilot]``'s), then ``more`` (old = new text)."""
    text = path.read_text()
    for key, value in SMALL.items():
        text, k = re.subn(rf"(?m)^{key} = .*$", f"{key} = {value}", text, count=1)
        assert k == 1, key
    for old, new in more.items():
        assert old in text, old
        text = text.replace(old, new, 1)
    out = tmp_path / name
    out.write_text(text)
    return out


# ================================================================================================ off means identical
@pytest.mark.parametrize("path", EARLIER, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_every_earlier_gate_file_loads_and_behaves_as_before(path):
    g = exploit.load_gates(path)
    for name, v in g.variants.items():
        assert not set(v) & exploit._VARIANT_OPTIONAL
        assert exploit.ref_variant(g, name) == name
        assert exploit.train_game(g, name) == v["game"]
        assert exploit.opponent_of(g, name, "strike") == v["g_star"] and exploit.opponent_of(g, name, "guard") == v["s_star"]
        for side in exploit.SIDES:
            assert exploit.side_settings(g, side, variant=name) == exploit.side_settings(g, side)
            assert exploit.recipe_label(g, side, name) == exploit.recipe_label(g, side)
            assert exploit.opponent_choice(g, name, side) == exploit.MAXIMIN_OPPONENT
    assert "per_variant" not in g.run0


def test_a_learner_without_the_new_keys_is_built_as_before():
    g = exploit.load_gates(ROOT / "configs" / "ste_l012" / "smoke_gates.toml")
    a = driver.build_learner(g, "base", "strike", 4, 1)
    assert a.env.game.cfg == exploit.variant_cfg(g, "base")
    assert type(next(iter(a.env.opponents.values()))) is REGISTRY["guard_mark_edge"]
    assert a.settings == exploit.side_settings(g, "strike")


# ================================================================================================ the new keys
def test_train_opponent_is_used_by_training_cells_baseline_and_labels(tmp_path):
    g = exploit.load_gates(L111)
    assert exploit.opponent_of(g, "base", "strike") == "guard_field"
    assert exploit.opponent_of(g, "base", "guard") == "strike_straight"           # the other side keeps s*
    assert exploit.opponent_choice(g, "base", "strike") == exploit.EXPLICIT_OPPONENT == "explicit, not the maximin pick"
    assert exploit.opponent_choice(g, "base", "guard") == exploit.MAXIMIN_OPPONENT
    cells = exploit.eval_cells(g, "base", "strike")
    assert {c[0] for c in cells} == {"guard_field"} and cells[0] == ("guard_field", exploit.EXPLOITER)
    ref = exploit.load_reference(ROOT / g.reference["file"])
    base = exploit.script_baseline(g, ref, "base", "strike")
    assert base["cell"] == ("guard_field", "strike_straight") and base["k"] == 284      # T44: 284 of 1,000 (spec)
    learner = driver.build_learner(exploit.load_gates(small(L111, tmp_path)), "base", "strike", 4, 1)
    assert driver.trained_against(learner) == REGISTRY["guard_field"].__name__


def test_the_loader_refuses_bad_new_keys(tmp_path):
    line = 'train_opponent = { strike = "guard_field" } }'
    for bad, why in (('train_opponent = { strike = "strike_low" } }', "not a script of the other team"),
                     ('train_opponent = { both = "guard_field" } }', "train_opponent"),
                     ('train_opponent = { strike = "guard_field" }, train_game = "nope" }', "train_game"),
                     ('train_opponent = { strike = "guard_field" }, side_overrides = { strike = { gamma = 0.9 } } }',
                      "unknown key"),
                     ('train_opponent = { strike = "guard_field" }, typo = 1 }', "unknown key")):
        with pytest.raises(ValueError, match=why):
            exploit.load_gates(text_with(L111, tmp_path, **{line: bad}))
    with pytest.raises(ValueError, match="per_variant"):
        exploit.load_gates(text_with(L113, tmp_path, **{"\nper_variant = true": '\nper_variant = "yes"'}))


def test_discount_factor_is_an_override_key_and_reaches_the_learner(tmp_path):
    assert "discount_factor" in exploit.OVERRIDE_KEYS
    g = exploit.load_gates(small(L113, tmp_path))
    assert exploit.side_settings(g, "strike", variant="arm_b_discount")["discount_factor"] == 0.997
    assert exploit.side_settings(g, "strike", variant="arm_a_clock30")["discount_factor"] == 0.99
    assert exploit.side_settings(g, "strike")["discount_factor"] == 0.99           # [trainer] untouched
    assert exploit.side_settings(g, "strike", variant="arm_b_discount")["shaping_weight"] == 1.0   # the recipe kept
    b = driver.build_learner(g, "arm_b_discount", "strike", 4, 1)
    assert b.settings["discount_factor"] == 0.997          # Learner checks skrl's effective value against it
    assert effective_cfg(b.agent.cfg, b.names[0])["discount_factor"] == 0.997       # what skrl itself uses
    a = driver.build_learner(g, "arm_a_clock30", "strike", 4, 1)
    assert effective_cfg(a.agent.cfg, a.names[0])["discount_factor"] == 0.99
    assert a.env.game.cfg.rules.game_steps == 600 and b.env.game.cfg.rules.game_steps == 2400


def test_train_game_trains_on_its_game_and_scores_on_game(tmp_path):
    p = text_with(ROOT / "configs" / "ste_l012" / "smoke_gates.toml", tmp_path, **{
        'extra_eval_opponents = { strike = [], guard = [] } }\ntag_1p2':
        'extra_eval_opponents = { strike = [], guard = [] }, train_game = "tag_1p2" }\ntag_1p2'})
    g = exploit.load_gates(p)
    assert exploit.train_game(g, "base") == "tag_1p2"
    learner = driver.build_learner(g, "base", "guard", 4, 1)
    assert learner.env.game.cfg.tag.radius_m == 1.2                                 # trains on tag_1p2
    assert exploit.variant_cfg(g, "base").tag.radius_m == 1.6                      # scores on base
    assert exploit.train_cfg(g, "base") == exploit.variant_cfg(g, "tag_1p2")


def test_recipe_label_names_the_variant_settings():
    g = exploit.load_gates(L113)
    assert exploit.recipe_label(g, "strike", "arm_b_discount") == \
        "shaped Strike recipe, variant settings {'discount_factor': 0.997}"


def test_reference_variant_maps_both_arms_onto_the_screen_cells():
    g = exploit.load_gates(L113)
    ref = exploit.load_reference(ROOT / g.reference["file"])
    for arm in g.variants:
        assert exploit.ref_variant(g, arm) == "tag_1p15"
        b = exploit.script_baseline(g, ref, arm, "strike")
        assert b["cell"] == ("guard_field", "strike_straight") and b["k"] == 355    # the screen's 355 reaches (spec)


# ================================================================================================ per-variant run 0
def test_a_run_0_per_variant_is_tied_to_its_arm():
    g = exploit.load_gates(L113)
    pilot = {"strike_recipe": {"side_overrides_strike": {"shaping_weight": 1.0}}}
    r0 = {"status": "PASS", "complete": True, "cap_h": 0.68, "gates_sha256": g.sha256, "variant": "arm_b_discount"}
    assert exploit.pilot_problem(g, pilot, "strike", None, r0, 0.68, "arm_b_discount") is None
    assert "per_variant" in exploit.pilot_problem(g, pilot, "strike", None, r0, 0.68, "arm_a_clock30")
    assert exploit.pilot_problem(g, pilot, "guard", None, None, 0.68, "arm_a_clock30") is None
    g11 = exploit.load_gates(L111)                       # without per_variant, any run 0 of the file serves (as L0.12)
    assert exploit.pilot_problem(g11, pilot, "strike", None, {**r0, "gates_sha256": g11.sha256, "variant": "x"}, 0.68,
                                 "base") is None


def test_run_0_needs_its_variant_with_per_variant_and_trains_that_arm(tmp_path):
    g = small(L113, tmp_path)
    pj = tmp_path / "pilot.json"
    pj.write_text(json.dumps({"strike_recipe": {"side_overrides_strike": {"shaping_weight": 1.0}}}))
    base = ["--run0", "--gates", str(g), "--cap-h", "1", "--no-videos", "--pilot-json", str(pj)]
    assert driver.main([*base, "--run-dir", str(tmp_path / "r0_none")]) == 2
    assert driver.main([*base, "--run-dir", str(tmp_path / "r0_typo"), "--variant", "arm_c"]) == 2
    rd = tmp_path / "r0_b"
    assert driver.main([*base, "--run-dir", str(rd), "--variant", "arm_b_discount"]) == 0
    out = json.loads((rd / driver.RUN0_FILE).read_text())
    assert out["variant"] == "arm_b_discount" and out["settings"]["discount_factor"] == 0.997 and out["per_variant"]
    assert json.loads((rd / driver.CONTROLS_FILE).read_text())["ctl_reference_replay"]["status"] == "PASS"


def test_run_0_without_per_variant_refuses_another_variant(tmp_path):
    g = small(L111, tmp_path)
    pj = tmp_path / "pilot.json"
    pj.write_text(json.dumps({"strike_recipe": {"side_overrides_strike": {"shaping_weight": 1.0}}}))
    assert driver.main(["--run0", "--gates", str(g), "--cap-h", "1", "--no-videos", "--pilot-json", str(pj),
                        "--run-dir", str(tmp_path / "r"), "--variant", "tag_1p2"]) == 2


def test_a_tiny_l111_strike_run_trains_and_scores_against_guard_field(tmp_path):
    g = small(L111, tmp_path)
    gates = exploit.load_gates(g)
    pj = tmp_path / "pilot.json"
    pj.write_text(json.dumps({"strike_recipe": {"side_overrides_strike": {"shaping_weight": 1.0}}}))
    r0 = tmp_path / "run0.json"
    r0.write_text(json.dumps({"status": "PASS", "complete": True, "cap_h": 1.0, "gates_sha256": gates.sha256}))
    rd = tmp_path / "run"
    assert driver.main(["--gates", str(g), "--variant", "base", "--side", "strike", "--run-dir", str(rd), "--cap-h", "1",
                        "--no-videos", "--pilot-json", str(pj), "--run0-json", str(r0)]) == 0
    res = json.loads((rd / "results.json").read_text())
    assert res["opponent"] == "guard_field" and res["opponent_choice"] == "explicit, not the maximin pick"
    assert res["trained_against"] == REGISTRY["guard_field"].__name__
    assert res["script"]["cell"] == ["guard_field", res["script"]["cell"][1]]
    assert all(k.startswith("guard_field v ") for k in res["cells"])
    assert res["discount_factor"] == 0.99 and res["train_game_file"] == res["game_file"]
    log = [json.loads(x) for x in (rd / "train_log.jsonl").read_text().splitlines()]
    assert {x["opponent"] for x in log} == {REGISTRY["guard_field"].__name__}
    run = json.loads((rd / "run.json").read_text())
    assert run["opponent"] == "guard_field" and run["opponent_choice"] == exploit.EXPLICIT_OPPONENT
    assert "explicit, not the maximin pick" in (rd / "results.md").read_text()
    controls = json.loads((rd / "controls.json").read_text())
    assert all(v["status"] == "PASS" for v in controls.values())
    # the verdict and the record writer carry the explicit opponent (the Purpose's g*/s* wording does not apply)
    out = tmp_path / "verdict"
    assert driver.main(["verdict", "--gates", str(g), "--runs", str(rd), "--out", str(out)]) == 0
    import make_ste_l012_record as record
    assert record.main(["--verdict", str(out / "verdict.json"), "--out", str(tmp_path / "rec.md"), "--name", "t"]) == 0
    text = (tmp_path / "rec.md").read_text()
    assert "trained against guard_field (explicit, not the maximin pick; the g*/s* maximin check was skipped" in text


def test_a_tiny_arm_a_run_trains_and_scores_on_the_30_s_clock(tmp_path):
    """Arm A end to end: its own run 0 file, the clock30 game for training and scoring, the screen reference's tag_1p15
    cells through reference_variant (controls PASS before and after training), discount 0.99 recorded."""
    g = small(L113, tmp_path)
    gates = exploit.load_gates(g)
    pj = tmp_path / "pilot.json"
    pj.write_text(json.dumps({"strike_recipe": {"side_overrides_strike": {"shaping_weight": 1.0}}}))
    r0 = tmp_path / "run0.json"
    r0.write_text(json.dumps({"status": "PASS", "complete": True, "cap_h": 1.0, "gates_sha256": gates.sha256,
                              "variant": "arm_a_clock30"}))
    rd = tmp_path / "run"
    assert driver.main(["--gates", str(g), "--variant", "arm_a_clock30", "--side", "strike", "--run-dir", str(rd),
                        "--cap-h", "1", "--no-videos", "--pilot-json", str(pj), "--run0-json", str(r0)]) == 0
    res = json.loads((rd / "results.json").read_text())
    assert res["game_file"]["file"] == "configs/ste_l1/tag_1p15_clock30.toml" == res["train_game_file"]["file"]
    assert res["discount_factor"] == 0.99 and res["opponent"] == "guard_field"
    assert res["opponent_choice"] == exploit.MAXIMIN_OPPONENT
    assert res["script"]["cell"] == ["guard_field", "strike_straight"]
    controls = json.loads((rd / "controls.json").read_text())
    assert controls["ctl_reference_replay"]["status"] == "PASS" and controls["ctl_reference_replay_final"]["status"] == "PASS"
    assert all(v["status"] == "PASS" for v in controls.values())
    # arm B's run with arm A's run 0 is refused (per_variant)
    assert driver.main(["--gates", str(g), "--variant", "arm_b_discount", "--side", "strike", "--run-dir",
                        str(tmp_path / "b"), "--cap-h", "1", "--no-videos", "--pilot-json", str(pj),
                        "--run0-json", str(r0)]) == 2


def test_preflight_skips_the_maximin_check_for_the_explicit_side_only(tmp_path):
    pj = tmp_path / "pilot.json"
    pj.write_text(json.dumps({"strike_recipe": {"side_overrides_strike": {"shaping_weight": 1.0}}}))
    args = lambda g: ["--gates", str(g), "--variant", "base", "--side", "guard", "--run-dir",  # noqa: E731
                      str(tmp_path / f"r{len(list(tmp_path.iterdir()))}"), "--cap-h", "1", "--no-videos",
                      "--pilot-json", str(pj)]
    # a wrong g* passes (the Strike side trains against its explicit opponent) ...
    wrong_g = small(L111, tmp_path, "g.toml", **{'g_star = "guard_mark_edge"': 'g_star = "guard_mirror"'})
    reason = driver.preflight(driver.parse(args(wrong_g)), exploit.load_gates(wrong_g))
    assert reason is None
    # ... a wrong s* does not (the Guard side has no explicit opponent)
    wrong_s = small(L111, tmp_path, "s.toml", **{'s_star = "strike_straight"': 's_star = "strike_flank"'})
    assert "g*, s*" in driver.preflight(driver.parse(args(wrong_s)), exploit.load_gates(wrong_s))


# ================================================================================================ the 30 s game file
def test_the_clock30_file_is_tag_1p15_but_for_game_steps():
    a, b = TAG115.read_text().splitlines(), CLOCK30.read_text().splitlines()
    assert len(a) == len(b)
    differ = [(x, y) for x, y in zip(a, b) if x != y]
    assert len(differ) == 1
    old, new = differ[0]
    assert old.startswith("game_steps = 2400 ") and re.match(r"game_steps = 600\s+#", new)
    assert TAG115.read_bytes().replace(old.encode(), new.encode()) == CLOCK30.read_bytes()
    c30, c120 = exploit.load_game_cfg_file(CLOCK30), exploit.load_game_cfg_file(TAG115)
    assert c30.rules.game_steps == 600 and c30 == c120.replace(**{"rules.game_steps": 600})


def test_on_the_30_s_clock_the_script_cells_replay_the_screen_and_a_still_game_ends_at_600():
    g = exploit.load_gates(L113)
    ref = exploit.load_reference(ROOT / g.reference["file"])
    cfg = exploit.variant_cfg(g, "arm_a_clock30")
    n = 3
    cells = [("guard_field", s) for s in g.players["strikes"]] + [("guard_parked_centre", exploit.ZERO)]
    pg = exploit.play_cells(cfg, "3v3", ref, cells, n, "cpu", int(ref.meta["seed"]), 2400, hold_ticks=12)
    for i, cell in enumerate(cells[:-1]):
        ok, text = exploit.replay_ok(exploit.slice_cell(pg, i, n), {k: v[:n] for k, v in ref.cell("tag_1p15", *cell).items()},
                                     "cpu", {}, ticks_cap=2400)
        assert ok, (cell, text)
    still = exploit.slice_cell(pg, len(cells) - 1, n)
    assert (still["outcome"] == GUARD_WIN).all() and (still["end_step"] == 600).all()
    assert scoring.end_reasons(still, pg["game_ticks"])["clock"] == n


# ================================================================================================ the gate files
def _strip(d: dict, keys) -> dict:
    return {k: v for k, v in d.items() if k not in keys}


def test_l111_is_l012s_gate_file_but_for_the_listed_keys():
    new, old = exploit.load_gates(L111), exploit.load_gates(L012)
    assert new.run == {**old.run, "task": "L1.11"}
    assert new.games == {"base": old.games["base"]}
    for part in ("reference", "players", "trainer", "controls", "videos"):
        assert getattr(new, part) == getattr(old, part), part
    assert _strip(new.verdict, {"order"}) == _strip(old.verdict, {"order"}) and new.verdict["order"] == ["base"]
    assert _strip(new.pilot, {"timing_batches"}) == _strip(old.pilot, {"timing_batches"})
    assert new.pilot["timing_batches"] == [{"variant": "base", "side": "strike"}]
    assert _strip(new.run0, {"train_seed"}) == _strip(old.run0, {"train_seed"})
    v, w = new.variants["base"], old.variants["base"]
    assert set(new.variants) == {"base"}
    assert _strip(v, {"train_seed", "train_opponent", "role"}) == _strip(w, {"train_seed", "role"})
    assert v["train_opponent"] == {"strike": "guard_field"} and v["train_seed"]["strike"] == 130111
    assert int(new.trainer["game_steps_per_run"]) == 550_000_000 and new.trainer["side_overrides"]["strike"] == \
        {"shaping_weight": 1.0}                                                       # T46's base Strike recipe


def test_l113_is_l012cs_strike_file_but_for_the_listed_keys():
    new, old = exploit.load_gates(L113), exploit.load_gates(L012C)
    assert new.run == {**old.run, "task": "L1.13"}
    assert new.games["tag_1p15"] == old.games["tag_1p15"] and set(new.games) == {"tag_1p15", "tag_1p15_clock30"}
    assert new.games["tag_1p15_clock30"].sha256 == exploit.sha256_file(CLOCK30)
    for part in ("reference", "players", "controls", "videos"):
        assert getattr(new, part) == getattr(old, part), part
    assert _strip(new.trainer, {"game_steps_per_run"}) == _strip(old.trainer, {"game_steps_per_run"})
    assert int(new.trainer["game_steps_per_run"]) == 300_000_000
    assert _strip(new.verdict, {"order"}) == _strip(old.verdict, {"order"})
    assert _strip(new.pilot, {"variant", "timing_batches"}) == _strip(old.pilot, {"variant", "timing_batches"})
    assert _strip(new.run0, {"variant", "train_seed", "per_variant"}) == _strip(old.run0, {"variant", "train_seed"})
    assert new.run0["per_variant"] is True
    w = old.variants["tag_1p15"]
    arms = {"arm_a_clock30": ("tag_1p15_clock30", 0.99, 130131), "arm_b_discount": ("tag_1p15", 0.997, 130132)}
    assert set(new.variants) == set(arms)
    for name, (game, discount, seed) in arms.items():
        v = new.variants[name]
        assert _strip(v, {"game", "train_seed", "role", "reference_variant", "side_overrides"}) == \
            _strip(w, {"game", "train_seed", "role"})
        assert v["game"] == game and v["reference_variant"] == "tag_1p15" and v["train_seed"]["strike"] == seed
        assert v["side_overrides"] == {"strike": {"discount_factor": discount}}


def _seeds(text: str) -> set[int]:
    found = {int(s) for s in re.findall(r"(?:train_seed|seed)\D{0,30}?(\d{6})", text)}
    return found | {int(s) for s in re.findall(r"(?:strike|guard) = (\d{6})", text)}


def test_the_seeds_are_new():
    used = set()
    for path in (ROOT / "configs").glob("ste_*/*.toml"):
        if path.parent.name != "ste_l1":
            used |= _seeds(path.read_text())
    assert {120411, 120412, 120413, 110000, 120900, 120950} <= used
    mine = []
    for path in (L111, L113):
        g = exploit.load_gates(path)
        mine += [int(s) for v in g.variants.values() for s in v["train_seed"].values()] + [int(g.run0["train_seed"])]
        assert int(g.run["curve_seed"]) not in mine and int(g.run["clip_seed"]) not in mine
    assert not set(mine) & used and len(set(mine)) == len(mine) == 8


# ================================================================================================ caps (time rule)
UPDATE_STEPS = 32 * 12 * 16384           # rollouts x decision ticks x games: one update
SIZING = {"update": 25.0, "read": 100.0, "batch": 120.0, "start": 10.0}   # T52's own timings + margin (gate headers)
MEASURED = {"update": 23.8, "read": 78.6, "batch": 106.0}                 # T52 (and T46 base: update max 19.6 s)
CAP_H = {"L1.11": 1.07, "L1.13": 0.68}   # --cap-h of each run (and its run 0), by the rule below
RUN0_USED_H, ARM_USED_H = 0.10, 0.50     # run 0 PASS at its first read (L0.12b: 0.10 GPU-h); an arm's expected use


def updates_that_start(cap_s, reserve_s, every):
    """The highest update N the driver lets start (cap left >= reserve before it): test_ste_l012c's rule."""
    n = 0
    s = SIZING
    while s["start"] + s["batch"] + n * s["update"] + (n // every) * s["read"] <= cap_s - reserve_s:
        n += 1
    return n


@pytest.mark.parametrize("path,task", [(L111, "L1.11"), (L113, "L1.13")])
def test_every_planned_update_starts_inside_the_cap(path, task):
    g = exploit.load_gates(path)
    tr = g.trainer
    assert int(tr["rollouts"]) * int(tr["decision_ticks"]) * int(tr["num_games"]) == UPDATE_STEPS
    planned = math.ceil(int(tr["game_steps_per_run"]) / UPDATE_STEPS)
    assert planned == {"L1.11": 88, "L1.13": 48}[task]
    assert SIZING["update"] >= 1.05 * MEASURED["update"] and SIZING["read"] >= 1.2 * MEASURED["read"]
    assert SIZING["batch"] >= MEASURED["batch"]
    reserve = exploit.final_reserve_s(tr, SIZING["batch"])
    assert reserve == 720.0
    every = int(tr["curve_every_updates"])
    assert updates_that_start(CAP_H[task] * 3600, reserve, every) >= planned
    assert updates_that_start((CAP_H[task] - 0.02) * 3600, reserve, every) < planned        # the rule bites
    assert f"--cap-h {CAP_H[task]}" in path.read_text()


# The lead raised the task caps to 1.2 (L1.11) and 1.7 (L1.13) on 22 Nov 2026, before any run (spec v2 addendum).
def test_the_task_caps_hold_run0_and_the_runs_in_launch_order():
    cfg = load_ste_learning()[0]
    # L1.11: run 0 (asks the run's cap, uses ~0.1), then the Strike run asks its whole cap
    assert RUN0_USED_H + CAP_H["L1.11"] <= cfg.cap_gpu_h("L1.11")
    # L1.13: run 0 A, arm A, run 0 B, then arm B asks its whole cap
    assert RUN0_USED_H + ARM_USED_H + RUN0_USED_H + CAP_H["L1.13"] <= cfg.cap_gpu_h("L1.13")


def test_the_l1_tasks_launch_against_the_l1_l2_budget():
    cfg = load_ste_learning()[0]
    for task in ("L1.11", "L1.12", "L1.13"):
        section = cfg.budget_of(task)
        assert section.phases == ("L1", "L2") or list(section.phases) == ["L1", "L2"]
        assert not section.closed and cfg.cap_gpu_h(task) > 0
    assert [cfg.cap_gpu_h(t) for t in ("L1.11", "L1.12", "L1.13")] == [1.2, 0.1, 2.1]
    for path in (L111, L113):
        assert cfg.budget_of(exploit.load_gates(path).run["task"]).phases == cfg.budget_of("L1.12").phases


# ================================================================================================ inputs
def test_the_bundled_pilot_is_l012s_and_picks_both_files_recipe():
    assert exploit.sha256_file(PILOT) == PILOT_SHA
    sums = (ROOT / "ste_provisional" / "SHA256SUMS").read_text()
    assert f"{PILOT_SHA}  pilots/2026-11-21_ste_l012_pilot/pilot.json" in sums
    pilot = json.loads(PILOT.read_text())
    for path in (L111, L113):
        assert exploit.recipe_problem(exploit.load_gates(path), pilot) is None
    for d in ("2026-11-21_ste_l012_base_strike", "2026-11-21_ste_l012b_tag_1p15_strike"):
        run = json.loads((ROOT / "ste_provisional" / "players" / d / "run.json").read_text())
        assert run["pilot_json_sha256"] == PILOT_SHA


# ================================================================================================ the shared scoring module
def test_end_reasons_split_every_game_once():
    pg = {"outcome": np.array([STRIKE_WIN, GUARD_WIN, GUARD_WIN, GUARD_WIN, RUNNING]),
          "end_step": np.array([50, 70, 600, 300, 0]), "strikes_left": np.array([2, 0, 1, 1, 3])}
    r = scoring.end_reasons(pg, 600)
    assert r == {"reach": 1, "all_strikes_tagged": 1, "clock": 1, "other_hold": 1, "unfinished": 1}
    assert set(r) == set(scoring.END_REASONS) and sum(r.values()) == 5


def test_the_drivers_reexport_the_shared_parts():
    import ste_cross_tag_l012d as l012d
    assert driver.plumbing_controls is scoring.plumbing_controls and driver.win_count is scoring.win_count
    assert driver.ending is scoring.ending and l012d.paired_wins is scoring.paired_wins
    assert l012d.save_batch is scoring.save_batch and l012d.load_batch is scoring.load_batch


# ================================================================================================ fix round 1
def test_a_run_folder_refuses_another_variant_side_or_gate_file_on_resume(tmp_path):
    """A run folder's run.json is the run it was started as: a resume naming another variant (per-variant run 0
    folders), side or gate file is refused (exit 2) before anything plays."""
    g = small(L113, tmp_path)
    pj = tmp_path / "pilot.json"
    pj.write_text(json.dumps({"strike_recipe": {"side_overrides_strike": {"shaping_weight": 1.0}}}))
    base = ["--run0", "--gates", str(g), "--cap-h", "1", "--no-videos", "--pilot-json", str(pj)]
    rd = tmp_path / "r0"
    rd.mkdir()
    (rd / "run.json").write_text(json.dumps({"variant": "arm_a_clock30", "side": "strike", "run0": True,
                                             "gates_sha256": exploit.load_gates(g).sha256}))
    assert driver.main([*base, "--run-dir", str(rd), "--variant", "arm_b_discount"]) == 2
    assert not (rd / "controls.json").exists()
    (rd / "run.json").write_text(json.dumps({"variant": "arm_b_discount", "side": "strike", "run0": True,
                                             "gates_sha256": "0" * 64}))
    assert driver.main([*base, "--run-dir", str(rd), "--variant", "arm_b_discount"]) == 2
    (rd / "run.json").write_text(json.dumps({"variant": "arm_b_discount", "side": "guard", "run0": False}))
    assert driver.main([*base, "--run-dir", str(rd), "--variant", "arm_b_discount"]) == 2
    assert not (rd / "controls.json").exists()


def test_results_name_the_task_and_the_curve_clock(tmp_path):
    g = small(L113, tmp_path)
    gates = exploit.load_gates(g)
    pj = tmp_path / "pilot.json"
    pj.write_text(json.dumps({"strike_recipe": {"side_overrides_strike": {"shaping_weight": 1.0}}}))
    r0 = tmp_path / "run0.json"
    r0.write_text(json.dumps({"status": "PASS", "complete": True, "cap_h": 1.0, "gates_sha256": gates.sha256,
                              "variant": "arm_a_clock30"}))
    rd = tmp_path / "run"
    assert driver.main(["--gates", str(g), "--variant", "arm_a_clock30", "--side", "strike", "--run-dir", str(rd),
                        "--cap-h", "1", "--no-videos", "--pilot-json", str(pj), "--run0-json", str(r0)]) == 0
    res = json.loads((rd / "results.json").read_text())
    assert res["what"].startswith("STE L1.13 ") and "L0.12" not in res["what"].split(";")[0]
    assert res["clock_s"] == 30.0 and "not comparable update by update" in res["clock_note"]
    assert "30 s clock" in (rd / "results.md").read_text()
    run = json.loads((rd / "run.json").read_text())
    assert run["gates_sha256"] == gates.sha256


def test_the_record_purpose_names_an_explicit_opponent():
    import make_ste_l012_record as record
    runs = {"base strike": {"opponent": "guard_field", "opponent_choice": exploit.EXPLICIT_OPPONENT}}
    text = record.purpose({"reference_label": "T44", "variants": {"base": {}}}, "L1.11", runs)
    assert "trained against its explicit opponent" in text and "guard_field" in text
    plain = record.purpose({"reference_label": "T44", "variants": {"base": {}}}, "L0.12", {})
    assert "explicit" not in plain
