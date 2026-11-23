"""STE tasks L1.9 (1v1 best-response read, plus the scripted 1v1 screen at 1.6 m and 1.15 m) and L1.10 (tag drawn per
game in 1.5-1.7 m, 3v3), both trained with the nominal estimate error (L1.7). Spec: ste_learning/drafts/L1_9_10_SPEC.md.

What is checked here (CPU only): the game files equal their sources but for what they add; the gate files equal T46's
(configs/ste_l012/gates.toml) but for the listed keys; the screen gate file plays the two 1v1 groups on one start set;
training plays the with-error (and tag-draw) game while the driver scores on the no-error game; the seeds are new; the
driver's time rule fits each run's cap and the task caps in launch order (L1.10 does not fit its 0.9: the needed cap is
computed); the score-matrix settings load once filled. End to end at test sizes: the 1v1 screen, its reference, an L1.9
Guard run and run 0, and an L1.10 Guard run, every control PASS. The tag draw itself: tests/test_tag_draw.py."""
from __future__ import annotations

import hashlib
import json
import math
import re
import sys
import tomllib
from pathlib import Path

import numpy as np
import pytest
import torch

from svg_training.core.rewards import GUARD_WIN, STRIKE_WIN
from svg_training.opponents.scripted import REGISTRY
from svg_training.ste import exploit, shared, sweep
from svg_training.ste.config import load_ste_learning

ROOT = exploit.ROOT
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))
import ste_exploit_l012 as driver  # noqa: E402
import ste_l012_reference as ref_script  # noqa: E402
import ste_score_matrix as matrix  # noqa: E402
import ste_sweep_l011 as screen  # noqa: E402
from test_ste_l1side import PILOT, _seeds, _strip, small  # noqa: E402

L1 = ROOT / "configs" / "ste_l1"
L19, L110, SCREEN = L1 / "l19_gates.toml", L1 / "l110_gates.toml", L1 / "l19_screen_gates.toml"
L012 = ROOT / "configs" / "ste_l012" / "gates.toml"
BASE, TAG115 = ROOT / "configs" / "ste_l011" / "base.toml", ROOT / "configs" / "ste_l011" / "tag_1p15.toml"
NOMINAL = L1 / "base_err_nominal.toml"
ERR1V1, P115_1V1, TAGDRAW = L1 / "base_1v1_err.toml", L1 / "base_1v1_1p15.toml", L1 / "base_err_tagdraw.toml"
MATRICES = {(t, s): L1 / f"score_matrix_{t}_{s}.toml" for t in ("l19", "l110") for s in ("strike", "guard")}
STRIKES_1V1 = ["strike_straight", "strike_flank", "strike_high", "strike_low"]


def _values(path: Path, start: str) -> list[str]:
    """The value lines (no comment, no blank) of ``path`` from the first line equal to ``start`` on."""
    lines = path.read_text().splitlines()
    return [x for x in lines[lines.index(start):] if x.strip() and not x.lstrip().startswith("#")]


def _cfg(path: Path):
    return exploit.load_game_cfg_file(path)


# ================================================================================================ the game files
def test_the_1v1_error_game_is_base_err_nominal_value_for_value():
    assert _values(ERR1V1, "[game]") == _values(NOMINAL, "[game]")
    assert tomllib.loads(ERR1V1.read_text()) == tomllib.loads(NOMINAL.read_text())
    cfg = _cfg(ERR1V1)
    assert cfg == _cfg(NOMINAL) and cfg.estimate_error.enabled and cfg.estimate_error.commander_reads == "true"
    assert cfg.tag.radius_m == 1.6 and cfg.tag.radius_m_range is None
    assert (cfg.pad_guards, cfg.pad_strikes) == (5, 3)                 # team size is the gate file's [run] size


def test_the_1v1_1p15_game_is_tag_1p15_value_for_value_without_error():
    assert _values(P115_1V1, "[game]") == _values(TAG115, "[game]")
    cfg = _cfg(P115_1V1)
    assert cfg == _cfg(TAG115) and cfg.tag.radius_m == 1.15 and not cfg.estimate_error.enabled


def test_the_tag_draw_game_is_base_err_nominal_plus_one_line():
    a, b = _values(NOMINAL, "[game]"), _values(TAGDRAW, "[game]")
    assert len(b) == len(a) + 1
    extra = [x for x in b if x not in a]
    assert len(extra) == 1 and re.match(r"radius_m_range = \[1\.5, 1\.7\]\s+#", extra[0])
    assert [x for x in b if x != extra[0]] == a
    cfg = _cfg(TAGDRAW)
    assert cfg == _cfg(NOMINAL).replace(**{"tag.radius_m_range": (1.5, 1.7)})
    assert cfg.tag.radius_m == 1.6 and cfg.estimate_error.enabled


# ================================================================================================ the gate files
def _common(new, old, task: str, games: dict, variant: str) -> dict:
    """Assert everything L0.12 ([trainer], [controls], [videos], the verdict rule, run 0's rule) is T46's; return the
    variant table."""
    assert new.run == {**old.run, "task": task, **({"size": "1v1"} if task == "L1.9" else {})}
    assert {k: (v.file, v.sha256) for k, v in new.games.items()} == games
    for name, ref in new.games.items():
        assert ref.sha256 == exploit.sha256_file(ROOT / ref.file), name
    for part in ("trainer", "controls", "videos"):
        assert getattr(new, part) == getattr(old, part), part
    assert int(new.trainer["game_steps_per_run"]) == 550_000_000                  # 0.55 B each (the costed row)
    assert new.trainer["side_overrides"] == {"strike": {"shaping_weight": 1.0}, "guard": {}}   # T46's recipe
    assert _strip(new.verdict, {"order"}) == _strip(old.verdict, {"order"}) and new.verdict["order"] == [variant]
    assert _strip(new.pilot, {"variant", "timing_batches"}) == _strip(old.pilot, {"variant", "timing_batches"})
    assert new.pilot["variant"] == variant and new.pilot["timing_batches"] == [{"variant": variant, "side": "strike"}]
    assert _strip(new.run0, {"variant", "train_seed"}) == _strip(old.run0, {"variant", "train_seed"})
    assert new.run0["variant"] == variant and "per_variant" not in new.run0
    assert set(new.variants) == {variant}
    v, w = new.variants[variant], old.variants["base"]
    assert _strip(v, {"train_seed", "role", "train_game", "reference_variant"}) == _strip(w, {"train_seed", "role"})
    return v


def test_l19_is_t46s_gate_file_but_for_the_listed_keys():
    new, old = exploit.load_gates(L19), exploit.load_gates(L012)
    v = _common(new, old, "L1.9", {"base": (old.games["base"].file, old.games["base"].sha256),
                                   "base_1v1_err": ("configs/ste_l1/base_1v1_err.toml", exploit.sha256_file(ERR1V1))},
                "base_1v1")
    assert v["game"] == "base" and v["train_game"] == "base_1v1_err" and "reference_variant" not in v
    assert new.players == {**old.players, "strikes": STRIKES_1V1}                 # the 1v1 screen's four Strike scripts
    sl = tomllib.loads(SCREEN.read_text())["players"]
    assert [s for s in sl["strikes"] if s not in sl["one_strike_duplicates"]] == STRIKES_1V1
    assert new.reference["file"] == "configs/ste_l1/l19_reference.npz"
    assert exploit.unfilled(new) == ["[reference] sha256", "[reference] start_sha256", "[reference] t44_gates_sha256",
                                     "[reference] t44_record", "[reference] t44_run"]   # FILL after the screen


def test_l110_is_t46s_gate_file_but_for_the_listed_keys():
    new, old = exploit.load_gates(L110), exploit.load_gates(L012)
    v = _common(new, old, "L1.10", {"base": (old.games["base"].file, old.games["base"].sha256),
                                    "base_err_tagdraw": ("configs/ste_l1/base_err_tagdraw.toml",
                                                         exploit.sha256_file(TAGDRAW))}, "base_tagdraw")
    assert v["game"] == "base" and v["train_game"] == "base_err_tagdraw"
    assert new.players == old.players and new.reference == old.reference and not exploit.unfilled(new)   # T44's, T46's
    ref = exploit.load_reference(ROOT / new.reference["file"])
    assert exploit.star_players(ref, "base", new.players) == ("guard_mark_edge", "strike_straight")       # T46's opponents
    assert v["reference_variant"] == "base" and exploit.ref_variant(new, "base_tagdraw") == "base"   # T44's base cells


def test_both_runs_train_with_the_error_and_the_driver_scores_without_it(tmp_path):
    pilot = json.loads(PILOT.read_text())
    for path, variant, train in ((L19, "base_1v1", ERR1V1), (L110, "base_tagdraw", TAGDRAW)):
        g = exploit.load_gates(path)
        assert exploit.recipe_problem(g, pilot) is None                           # L0.12's pilot, the shaped recipe
        assert exploit.variant_cfg(g, variant) == _cfg(BASE) and not exploit.variant_cfg(g, variant).estimate_error.enabled
        assert exploit.train_cfg(g, variant) == _cfg(train)
        for side in ("strike", "guard"):
            learner = driver.build_learner(exploit.load_gates(small(path, tmp_path, name=f"{variant}_{side}.toml")),
                                           variant, side, 4, 1)
            game = learner.env.game
            assert game.cfg.estimate_error.enabled and game._starling.model.estimator is not None
            assert (game.guards, game.strikes) == ((1, 1) if variant == "base_1v1" else (3, 3))
            if variant == "base_tagdraw":
                r = game._study_radius()
                assert r.shape == (4,) and float(r.min()) >= 1.5 and float(r.max()) <= 1.7
            else:
                assert game._study_radius() == 1.6


def test_why_the_driver_scores_without_the_error_a_script_cell_does_not_replay_with_it():
    """The DESIGN note of both gate files: the estimate error is drawn per batch slot, so two identical script cells in
    one batch differ with it on (the driver's exact replay controls could not pass), and are equal with it off."""
    ref = exploit.load_reference(ROOT / exploit.load_gates(L110).reference["file"])
    cells, n = [("guard_mark_edge", "strike_straight")] * 2, 6
    for path, same in ((BASE, True), (NOMINAL, False)):
        pg = exploit.play_cells(_cfg(path), "3v3", ref, cells, n, "cpu", int(ref.meta["seed"]), 2400)
        agree = exploit.agreement(exploit.slice_cell(pg, 0, n), exploit.slice_cell(pg, 1, n))
        assert (agree["differ"] == 0) is same, (path.name, agree)


# ================================================================================================ the screen
def test_the_screen_plays_two_1v1_groups_on_the_cpu_from_one_start_set():
    g = sweep.load_gates(SCREEN)
    assert g.run["task"] == "L1.9" and g.run["device"] == "cpu" and g.run["games_per_cell"] == 1000
    assert not sweep.game_file_problems(g)
    assert g.games["base"].file == "configs/ste_l011/base.toml" and g.games["tag_1p15_1v1"].file == \
        "configs/ste_l1/base_1v1_1p15.toml"
    plan = {p.spec.name: p for p in sweep.build_plan(g)}
    assert {n: len(p.cells) for n, p in plan.items() if p.spec.role == "sweep"} == {"base_1v1": 20, "tag_1p15_1v1": 20}
    assert all(sweep.group_game(g, p.spec)[1] == "1v1" for p in plan.values())
    assert sorted(g.cut["protected"]) == sorted(plan)                            # nothing is cut
    # one start set: the two groups draw their starts from the same seed and start mode
    a, b = (sweep.SweepGame(_cfg(f), 1, 64, 1, 1, "cpu", int(g.run["seed"])) for f in (BASE, P115_1V1))
    assert torch.equal(a.pos_m, b.pos_m)
    # the worst case fits the CPU job's cap (the header's arithmetic)
    ticks = sum(p.spec.ticks_cap(g.run) * len(p.batches) for p in plan.values())
    assert ticks == 15_100
    projected = ticks * g.projection["seconds_per_batch_tick"]["1v1"] * g.cut["safety_factor"] + g.clips["reserve_s"]
    assert projected <= 1.5 * 3600 and "--cap-h is the effective-hour cap of the job (1.5)" in SCREEN.read_text()


# ================================================================================================ seeds
def test_the_seeds_are_new():
    used = set()
    for path in (ROOT / "configs").glob("ste_*/*.toml"):
        if path not in (L19, L110):
            used |= _seeds(path.read_text())
    for path in (ROOT / "ste_provisional" / "players").glob("*/gates.toml"):
        if not path.parent.name.startswith(("2026-11-24_ste_l110", "2026-11-24_ste_l19")):   # L1.9/L1.10's own runs (24 Nov 2026)
            used |= _seeds(path.read_text())
    assert {120001, 120101, 130111, 110000, 120900, 120950} <= used
    mine = []
    for path in (L19, L110):
        g = exploit.load_gates(path)
        mine += [int(s) for v in g.variants.values() for s in v["train_seed"].values()] + [int(g.run0["train_seed"])]
        assert int(g.run["curve_seed"]) not in mine and int(g.run["clip_seed"]) not in mine
    assert sorted(mine) == [130191, 130192, 130193, 130201, 130202, 130203]
    assert not set(mine) & used


# ================================================================================================ caps (time rule)
UPDATE_STEPS = 32 * 12 * 16384           # rollouts x decision ticks x games: one update
# U: T46's base Strike update maximum 19.6 s x 1.27 (the estimate error's training cost, unmeasured on a GPU); K, B:
# L0.12b's sizing (the evaluation plays the no-error game, as T46's: base Strike reads 52.5-53.2 s); O as L0.12b.
SIZING = {"update": 25.0, "read": 56.5, "batch": 100.0, "start": 10.0}
T46 = {"strike_update_max": 19.6, "strike_read_max": 53.2, "guard_used_h": 1450.5 / 3600, "strike_used_h": 2126.1 / 3600}
CAP_H = 0.94                              # --cap-h of run 0 and both runs, in both tasks
# Expected use: T46's (and L0.12b run 0's 0.10) times the same error factor the time rule allows on an update (U / T46's
# worst update = 25 / 19.6), so the launch totals and the time rule assume one error cost.
ERROR_FACTOR = SIZING["update"] / T46["strike_update_max"]
RUN0_USED_H = 0.10 * ERROR_FACTOR
GUARD_USED_H, STRIKE_USED_H = T46["guard_used_h"] * ERROR_FACTOR, T46["strike_used_h"] * ERROR_FACTOR
SCORE_ASK_H, SCORE_USED_H = {"L1.9": 0.15, "L1.10": 0.2}, {"L1.9": 0.05, "L1.10": 0.1}


def updates_that_start(cap_s: float, reserve_s: float, every: int) -> int:
    n, s = 0, SIZING
    while s["start"] + s["batch"] + n * s["update"] + (n // every) * s["read"] <= cap_s - reserve_s:
        n += 1
    return n


def test_the_sizing_comes_from_t46s_logs():
    for side, key in (("strike", "strike_update_max"), ("guard", None)):
        rows = [json.loads(x) for x in (ROOT / "ste_provisional" / "players" / f"2026-11-21_ste_l012_base_{side}" /
                                        "train_log.jsonl").read_text().splitlines() if x.strip()]
        worst = max(r["seconds"] for r in rows)
        assert len(rows) == 88 and SIZING["update"] >= 1.25 * worst
        if key:
            assert worst == pytest.approx(T46[key], abs=0.05)
    curve = json.loads((ROOT / "ste_provisional" / "players" / "2026-11-21_ste_l012_base_strike" / "curve.json").read_text())
    assert max(p["seconds"] for p in curve) == pytest.approx(T46["strike_read_max"], abs=0.05)
    assert SIZING["read"] >= 1.06 * T46["strike_read_max"]
    for side in ("guard", "strike"):
        res = json.loads((ROOT / "ste_provisional" / "players" / f"2026-11-21_ste_l012_base_{side}" /
                          "results.json").read_text())
        assert res["effective_s"] / 3600 == pytest.approx(T46[f"{side}_used_h"], abs=0.001)
    assert GUARD_USED_H >= 1.27 * T46["guard_used_h"] and STRIKE_USED_H >= 1.27 * T46["strike_used_h"]


@pytest.mark.parametrize("path", [L19, L110])
def test_every_planned_update_starts_inside_the_cap(path):
    g = exploit.load_gates(path)
    tr = g.trainer
    assert int(tr["rollouts"]) * int(tr["decision_ticks"]) * int(tr["num_games"]) == UPDATE_STEPS
    planned = math.ceil(int(tr["game_steps_per_run"]) / UPDATE_STEPS)
    assert planned == 88
    reserve = exploit.final_reserve_s(tr, SIZING["batch"])
    assert reserve == 640.0
    every = int(tr["curve_every_updates"])
    assert updates_that_start(CAP_H * 3600, reserve, every) >= planned
    assert updates_that_start((CAP_H - 0.02) * 3600, reserve, every) < planned        # the rule bites
    assert f"--cap-h {CAP_H} on run 0 and on both runs" in path.read_text()


def _launch_totals(task: str) -> list[float]:
    """Hours the launcher sees at each launch (used so far + this job's ask), in the spec's launch order: run 0, the
    Guard run, the Strike run, the Guard score matrix, the Strike score matrix."""
    used, out = 0.0, []
    for ask, use in ((CAP_H, RUN0_USED_H), (CAP_H, GUARD_USED_H), (CAP_H, STRIKE_USED_H),
                     (SCORE_ASK_H[task], SCORE_USED_H[task]), (SCORE_ASK_H[task], SCORE_USED_H[task])):
        out.append(used + ask)
        used += use
    return out


def test_l19_fits_its_task_cap_in_launch_order():
    cap = load_ste_learning()[0].cap_gpu_h("L1.9")
    assert cap == 1.6
    totals = _launch_totals("L1.9")
    assert max(totals) <= cap and max(totals) == pytest.approx(1.595, abs=0.001)      # tight: 0.005 to spare
    assert cap - (RUN0_USED_H + GUARD_USED_H + STRIKE_USED_H + 2 * SCORE_USED_H["L1.9"]) == pytest.approx(0.105, abs=0.001)


def test_l110_needs_1p7_and_its_cap_was_raised_to_it_from_three_tasks():
    """At 0.9 run 0 alone (asking 0.94) did not fit; in launch order the largest total the launcher sees is 1.69 GPU-h (the
    second score matrix, the main reading, launches last). 23 Nov 2026 (fix round 1, announced to the owner): 1.7, with
    0.6 from L1.8 (used 0.598, T64), 0.1 from L1.6 and 0.1 from L1.15 (used 0.154, T61); the L1 sum stays 9.1."""
    cfg = load_ste_learning()[0]
    needed = math.ceil(max(_launch_totals("L1.10")) * 10 - 1e-9) / 10
    assert needed == 1.7 == cfg.cap_gpu_h("L1.10") and max(_launch_totals("L1.10")) <= cfg.cap_gpu_h("L1.10")
    assert (cfg.cap_gpu_h("L1.8"), cfg.cap_gpu_h("L1.6"), cfg.cap_gpu_h("L1.15")) == (0.6, 0.0, 0.2)
    assert 0.598 <= cfg.cap_gpu_h("L1.8") and 0.154 <= cfg.cap_gpu_h("L1.15")            # their used hours still fit
    l1 = [t for t, _ in cfg.budget_of("L1.10").task_cap_gpu_h if t.startswith("L1.")]
    assert round(sum(cfg.cap_gpu_h(t) for t in l1), 6) == 9.1
    text = L110.read_text()
    assert "raised from 0.9 on 23 Nov 2026" in text and "at least 1.7 GPU-h" in text
    for task in ("L1.9", "L1.10"):
        assert cfg.budget_of(task).phases == cfg.budget_of("L1.11").phases


# ================================================================================================ score matrices
def _filled(path: Path, tmp_path: Path) -> Path:
    text = path.read_text().replace('own_wins = "FILL_FROM_RUN"', "own_wins = 1")
    text = re.sub(r'"FILL_[A-Z_]*"', '"x"', text)
    out = tmp_path / path.name
    out.write_text(text)
    return out


@pytest.mark.parametrize("key", list(MATRICES), ids=lambda k: f"{k[0]}_{k[1]}")
def test_the_score_matrices_load_once_filled_and_pin_their_games(key, tmp_path):
    path = MATRICES[key]
    if "FILL_" in path.read_text().split("[player]")[1].split("[[games]]")[0]:   # before its run: refused until filled
        with pytest.raises(ValueError, match="not filled yet"):
            matrix.load_settings(path)
        data = matrix.load_settings(_filled(path, tmp_path))
    else:                                                                       # filled from the finished run (L1.10, 24 Nov 2026)
        data = matrix.load_settings(path)
        assert isinstance(data["player"]["own_wins"], int) and data["player"]["own_wins"] > 0
    task, side = key
    assert data["job"]["task"] == {"l19": "L1.9", "l110": "L1.10"}[task] and data["player"]["side"] == side
    assert data["player"]["variant"] == {"l19": "base_1v1", "l110": "base_tagdraw"}[task]
    params = exploit.sha256_file(ROOT / "params" / "real_exploratory_v0.toml")
    for game in data["games"]:
        assert game["sha256"] == exploit.sha256_file(ROOT / game["file"]), game["name"]
        cfg = _cfg(ROOT / game["file"])
        if cfg.estimate_error.enabled:                     # with the error: no reference can be replayed (DESIGN)
            assert game["reference"] is False and game["params_sha256"] == params
        else:
            assert game["file"] == "configs/ste_l011/base.toml" and game["reference"] is not False
    names = [g["name"] for g in data["games"]]
    assert names == (["base_1v1_err", "base_1v1"] if task == "l19" else ["base_err", "base", "tagdraw_err"])
    main = data["games"][0]                    # the main read first; the rest INFO (L1.10: the lead's ruling, 23 Nov 2026)
    assert main["file"] == ("configs/ste_l1/base_1v1_err.toml" if task == "l19" else "configs/ste_l1/base_err_nominal.toml")
    assert _cfg(ROOT / main["file"]).estimate_error.enabled and _cfg(ROOT / main["file"]).tag.radius_m_range is None
    if task == "l110":
        assert "(main)" in main["clock_label"] and all("INFO" in g["clock_label"] for g in data["games"][1:])


# ================================================================================================ end to end (CPU)
def _tiny_screen(tmp_path: Path) -> Path:
    """The screen gate file at test sizes (4 games per cell, short games): a test of the code path, never a result."""
    text = SCREEN.read_text()
    for old, new in {"games_per_cell = 1000": "games_per_cell = 4",
                     "ticks_cap = 2400                   # = the game": "ticks_cap = 200   # smoke",
                     "\nticks = 100": "\nticks = 3", "cap_check_every_ticks = 100": "cap_check_every_ticks = 2"}.items():
        assert old in text, old
        text = text.replace(old, new)
    text = text.replace("\nticks = 200", "\nticks = 60", 1)                       # reach fires: enough to arrive
    text = text.replace("\nticks = 200", "\nticks = 3")                           # the two still controls
    out = tmp_path / "screen_gates.toml"
    out.write_text(text)
    return out


def _cpu_sizes(text: str) -> str:
    for old, new in {'device = "cuda"': 'device = "cpu"', "eval_games = 1000": "eval_games = 4",
                     "ticks_cap = 2400": "ticks_cap = 40", "curve_games = 256": "curve_games = 2",
                     "num_games = 16384": "num_games = 4", "game_steps_per_run = 550_000_000": "game_steps_per_run = 192",
                     "rollouts = 32": "rollouts = 2", "learning_epochs = 5": "learning_epochs = 1",
                     "mini_batches = 4": "mini_batches = 1", "final_reserve_s = 600": "final_reserve_s = 60",
                     "curve_every_updates = 10": "curve_every_updates = 2"}.items():
        assert old in text, old
        text = text.replace(old, new, 1)
    return text


def _set(text: str, key: str, value: str) -> str:
    out, n = re.subn(rf'^{key} = "[^"]*"', f'{key} = "{value}"', text, count=1, flags=re.M)
    assert n == 1, key
    return out


@pytest.fixture(scope="module")
def l19_chain(tmp_path_factory):
    """The L1.9 chain at test sizes: the 1v1 screen on the CPU, its reference (scripts/ste_l012_reference.py), and the
    runs' gate file filled as its FILL steps say."""
    tmp = tmp_path_factory.mktemp("l19")
    mp = pytest.MonkeyPatch()
    mp.setenv(shared.SHARED_ENV, str(tmp / "shared"))
    mp.setenv(shared.LEGACY_LOGS_ENV, "")
    out = tmp / "screen"
    code = screen.main(["--gates", str(_tiny_screen(tmp)), "--run-dir", str(out), "--cap-h", "1", "--no-clips"])
    (out / "exit_code").write_text(f"{code}\n")
    ref_path = tmp / "l19_reference.npz"
    ref_code = ref_script.main(["--t44", str(out), "--out", str(ref_path), "--variants", "base_1v1,tag_1p15_1v1"])
    gates = None
    if ref_code == 0:
        ref = exploit.load_reference(ref_path)
        g = exploit.load_gates(L19)
        g_star, s_star = exploit.star_players(ref, "base_1v1", g.players)
        text = _set(_set(_set(_set(_set(L19.read_text(), "file", str(ref_path)), "sha256", exploit.sha256_file(ref_path)),
                              "start_sha256", ref.start_sha256), "t44_gates_sha256", ref.meta["t44_gates_sha256"]),
                    "t44_run", out.name)
        text = _set(text, "t44_record", "records/test_l19_screen_record.md")
        text, n = re.subn(r'g_star = "[^"]*", s_star = "[^"]*"', f'g_star = "{g_star}", s_star = "{s_star}"', text, count=1)
        assert n == 1
        if s_star in g.players["z_up_info"]:
            text = text.replace("extra_eval_opponents = { strike = [], guard = [] }",
                                'extra_eval_opponents = { strike = [], guard = ["strike_straight"] }', 1)
        gates = tmp / "l19_gates.toml"
        gates.write_text(_cpu_sizes(text))
    yield {"code": code, "out": out, "ref_code": ref_code, "ref": ref_path, "gates": gates, "tmp": tmp}
    mp.undo()


def test_the_1v1_screen_runs_with_every_control_passing_and_one_start_set(l19_chain):
    assert l19_chain["code"] == 0 and l19_chain["ref_code"] == 0
    result = json.loads((l19_chain["out"] / "results.json").read_text())
    assert result["controls_all_pass"], result["controls"]
    ref = exploit.load_reference(l19_chain["ref"])
    assert ref.games == 4 and ref.starts_m.shape == (4, 2, 3)                     # 1v1 starts
    for v in ("base_1v1", "tag_1p15_1v1"):
        for gname in exploit.load_gates(L19).players["guards"]:
            for s in STRIKES_1V1:
                assert ref.cell(v, gname, s)["outcome"].shape == (4,)
    with pytest.raises(KeyError):
        ref.cell("base_1v1", "guard_field", "strike_converge")                   # duplicates not played at 1v1


def _pilot(tmp: Path) -> Path:
    pj = tmp / "pilot.json"
    pj.write_text(json.dumps({"strike_recipe": {"side_overrides_strike": {"shaping_weight": 1.0}}}))
    return pj


def test_a_tiny_l19_guard_run_and_run_0_train_on_the_error_game_and_score_at_1v1(l19_chain, monkeypatch):
    tmp = l19_chain["tmp"]
    monkeypatch.setenv(shared.SHARED_ENV, str(tmp / "shared"))
    monkeypatch.setenv(shared.LEGACY_LOGS_ENV, "")
    gates = l19_chain["gates"]
    rd = tmp / "guard"
    assert driver.main(["--gates", str(gates), "--variant", "base_1v1", "--side", "guard", "--run-dir", str(rd),
                        "--cap-h", "1", "--no-videos", "--pilot-json", str(_pilot(tmp))]) == 0
    controls = json.loads((rd / "controls.json").read_text())
    assert controls and all(v["status"] == "PASS" for v in controls.values()), controls
    res = json.loads((rd / "results.json").read_text())
    assert res["train_game_file"]["file"] == "configs/ste_l1/base_1v1_err.toml"
    assert res["game_file"]["file"] == "configs/ste_l011/base.toml"
    r0 = tmp / "run0"
    assert driver.main(["--gates", str(gates), "--run0", "--run-dir", str(r0), "--cap-h", "1", "--no-videos",
                        "--pilot-json", str(_pilot(tmp))]) == 0
    lc = json.loads((r0 / "learner_control.json").read_text())
    assert lc["variant"] == "base_1v1" and lc["train_game"] == "base_1v1_err" and lc["status"] in ("PASS", "FAIL")


def test_the_l19_driver_refuses_until_the_screen_fills_the_gate_file(tmp_path, capsys):
    rd = tmp_path / "run"
    code = driver.main(["--gates", str(L19), "--variant", "base_1v1", "--side", "guard", "--run-dir", str(rd),
                        "--cap-h", "0.94", "--no-videos", "--pilot-json", str(PILOT)])
    err = capsys.readouterr().err
    assert code == 2 and "not filled yet" in err and "[reference] t44_record" in err


@pytest.fixture(scope="module")
def l110_guard(tmp_path_factory):
    """A tiny L1.10 Guard run (CPU sizes) from the real gate file: trains on the tag-draw game, scored on T46's."""
    tmp = tmp_path_factory.mktemp("l110")
    mp = pytest.MonkeyPatch()
    mp.setenv(shared.SHARED_ENV, str(tmp / "shared"))
    mp.setenv(shared.LEGACY_LOGS_ENV, "")
    gates = tmp / "l110.toml"
    gates.write_text(_cpu_sizes(L110.read_text()))
    rd = tmp / "guard"
    code = driver.main(["--gates", str(gates), "--variant", "base_tagdraw", "--side", "guard", "--run-dir", str(rd),
                        "--cap-h", "1", "--no-videos", "--pilot-json", str(_pilot(tmp))])
    yield {"code": code, "rd": rd, "tmp": tmp}
    mp.undo()


def test_a_tiny_l110_guard_run_trains_on_the_tag_draw_game_and_scores_on_t46s_game(l110_guard):
    assert l110_guard["code"] == 0
    rd = l110_guard["rd"]
    controls = json.loads((rd / "controls.json").read_text())
    assert controls and all(v["status"] == "PASS" for v in controls.values()), controls   # T44's cells replayed
    res = json.loads((rd / "results.json").read_text())
    assert res["train_game_file"]["file"] == "configs/ste_l1/base_err_tagdraw.toml"
    assert res["game_file"]["file"] == "configs/ste_l011/base.toml" and res["opponent"] == "strike_straight"
    log = [json.loads(x) for x in (rd / "train_log.jsonl").read_text().splitlines()]
    assert log and {x["opponent"] for x in log} == {REGISTRY["strike_straight"].__name__}


# ------------------------------------------------------------------------------------------------ the main reading
def _player(rd: Path, side: str, variant: str) -> dict:
    """The [player] table pinning a finished tiny run folder (as the lead fills it from the run)."""
    gates = exploit.load_gates(rd / "gates.toml")
    n = int(gates.run["eval_games"])
    won = GUARD_WIN if side == "guard" else STRIKE_WIN
    outcome = np.load(rd / "eval_final.npz")["outcome"]
    return {"label": f"tiny {variant} {side}", "dir": str(rd), "side": side, "variant": variant,
            "gates_sha256": exploit.sha256_file(rd / "gates.toml"), "agent_sha256": exploit.sha256_file(rd / "agent_final.pt"),
            "eval_sha256": exploit.sha256_file(rd / "eval_final.npz"), "own_wins": int(np.sum(outcome[:n] == won)),
            "own_source": "made by the test"}


def _matrix(settings_path: Path, player: dict, tmp: Path, ref_path: Path | None = None) -> tuple[int, Path]:
    """The real settings file's [job] and [[games]], the tiny player, the L1.9 reference at its test path; run."""
    from test_ste_score_matrix import write_settings
    data = tomllib.loads(settings_path.read_text())
    games = []
    for g in data["games"]:
        g = dict(g)
        if ref_path is not None and g.get("reference") == "configs/ste_l1/l19_reference.npz":
            g["reference"], g["reference_sha256"] = str(ref_path), exploit.sha256_file(ref_path)
        games.append(g)
    s = write_settings(tmp / f"{settings_path.stem}.toml", data["job"], player, games)
    rd = tmp / f"{settings_path.stem}_run"
    return matrix.main(["--settings", str(s), "--run-dir", str(rd), "--cap-h", "1"]), rd


def _matrix_ok(code: int, rd: Path, names: list[str]) -> None:
    assert code == 0
    controls = json.loads((rd / "controls.json").read_text())
    assert controls and {v["status"] for v in controls.values()} == {"PASS"}, controls
    res = json.loads((rd / "results.json").read_text())
    assert res["complete"] is True and res["controls_pass"] is True and list(res["games"]) == names
    for name in names:
        rows = res["games"][name]["rows"]
        assert rows and all(r["best_script"]["name"] for r in rows)


def test_the_l19_score_matrix_plays_both_1v1_games(l19_chain, monkeypatch):
    monkeypatch.setenv(shared.SHARED_ENV, str(l19_chain["tmp"] / "shared"))
    monkeypatch.setenv(shared.LEGACY_LOGS_ENV, "")
    rd = l19_chain["tmp"] / "guard"
    if not (rd / "results.json").is_file():               # the tiny Guard run of the test above, else made here
        assert driver.main(["--gates", str(l19_chain["gates"]), "--variant", "base_1v1", "--side", "guard",
                            "--run-dir", str(rd), "--cap-h", "1", "--no-videos",
                            "--pilot-json", str(_pilot(l19_chain["tmp"]))]) == 0
    code, out = _matrix(MATRICES[("l19", "guard")], _player(rd, "guard", "base_1v1"), l19_chain["tmp"], l19_chain["ref"])
    _matrix_ok(code, out, ["base_1v1_err", "base_1v1"])
    rows = json.loads((out / "results.json").read_text())["games"]["base_1v1_err"]["rows"]
    assert sorted(r["opponent"] for r in rows) == sorted(STRIKES_1V1)


def test_the_l110_score_matrix_plays_its_three_games(l110_guard, monkeypatch):
    monkeypatch.setenv(shared.SHARED_ENV, str(l110_guard["tmp"] / "shared"))
    monkeypatch.setenv(shared.LEGACY_LOGS_ENV, "")
    code, out = _matrix(MATRICES[("l110", "guard")], _player(l110_guard["rd"], "guard", "base_tagdraw"),
                        l110_guard["tmp"])
    _matrix_ok(code, out, ["base_err", "base", "tagdraw_err"])
