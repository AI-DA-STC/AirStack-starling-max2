"""STE task L0.12b Bubble tag check (owner decision 21 Nov 2026): tag radius 1.15 m (the safety filter's 1.10 m keep-out +
0.05 m). The game file, the unchosen-tag measurement (hand-made games where the filter makes a tag and where it does not),
the study-tag hook in core/game.py (it changes no game), the screen's gate file and a CPU run of the screen driver with
its reference replay, the best-response gate file (fill steps, pilot reuse, the step budget that cannot stop at the cap
reserve), and a CPU run of the L0.12 driver under it end to end. Everything on the CPU, tiny sizes."""
import json
import math
import re
import sys
from pathlib import Path

import numpy as np
import pytest
import torch

from _ste_tools import SCRIPTS
from svg_training.core.game import SvgGame
from svg_training.core.game_config import load_game_cfg
from svg_training.core.rewards import GUARD_WIN, RUNNING
from svg_training.ste import exploit, shared, sweep
from svg_training.ste.run_contract import EXIT_CONTROL_FAILED, EXIT_DONE, EXIT_REFUSED

sys.path.insert(0, str(SCRIPTS))
import make_ste_l011_record as screen_record  # noqa: E402
import make_ste_l012_record as record  # noqa: E402
import ste_exploit_l012 as driver  # noqa: E402
import ste_l012_reference as ref_script  # noqa: E402
import ste_sweep_l011 as screen  # noqa: E402

ROOT = sweep.ROOT
TAG_FILE = ROOT / "configs" / "ste_l011" / "tag_1p15.toml"
BASE_FILE = ROOT / "configs" / "ste_l011" / "base.toml"
SCREEN = ROOT / "configs" / "ste_l012b" / "screen_gates.toml"
GATES = ROOT / "configs" / "ste_l012b" / "gates.toml"
L011_GATES = ROOT / "configs" / "ste_l011" / "gates.toml"
L012_GATES = ROOT / "configs" / "ste_l012" / "gates.toml"
PARKED = "guard_parked_centre"


@pytest.fixture(autouse=True)
def private_shared(tmp_path, monkeypatch):
    monkeypatch.setenv(shared.SHARED_ENV, str(tmp_path / "shared"))
    monkeypatch.setenv(shared.LEGACY_LOGS_ENV, "")


def cfg_of(path):
    return load_game_cfg(path, local_dir=None, use_local=False)[0]


# ------------------------------------------------------------------------------------------------ the game file
def test_tag_1p15_is_the_base_game_with_the_tag_at_1p15_m():
    tag, base = cfg_of(TAG_FILE), cfg_of(BASE_FILE)
    assert tag.tag.radius_m == 1.15 and tag.tag.mode == "nearest_pair_1for1"
    assert tag.replace(**{"tag.radius_m": base.tag.radius_m}) == base          # one factor changed
    assert min(tag.rules.keepout_guard_m, tag.rules.keepout_strike_m) == 1.1   # the filter distance it sits 0.05 m over


def test_both_gate_files_pin_the_committed_game_files():
    for gates in (sweep.load_gates(SCREEN), exploit.load_gates(GATES)):
        assert sweep.game_file_problems(gates) == []
        assert gates.games["tag_1p15"].sha256 == sweep.sha256_file(TAG_FILE)


# ------------------------------------------------------------------------------------------------ unchosen tags
def play_still(starts, guards, strikes, ticks=60):
    """One game from hand-made starts, every drone commanding zero, until it ends: (game, per-game arrays)."""
    cfg = cfg_of(TAG_FILE)
    s = torch.tensor(starts, dtype=torch.float32)[None]
    game = sweep.SweepGame(cfg, 1, 1, guards, strikes, "cpu", 5, fixed_starts=(s, torch.zeros(1, dtype=torch.bool)))
    game.reset()
    still = {"guard": torch.zeros(1, guards, 4), "strike": torch.zeros(1, strikes, 4)}
    outcome = torch.zeros(1, dtype=torch.int8)
    for _ in range(ticks):
        out = game.step(still)
        outcome = torch.where(game.first_done & (outcome == RUNNING), out.outcome, outcome)
        if bool(game.first_done.all()):
            break
    pg = {"outcome": outcome.numpy(), "tags": game.tags.numpy(), "tag_pair_m": game.tag_pair_m.numpy(),
          "tag_filtered": game.tag_filtered.numpy()}
    return game, pg, sweep.tag_shares(pg, sweep.tag_edge_m(cfg, 0.01))


def test_the_filter_makes_a_tag_it_is_counted_as_unchosen():
    """Two Guard team-mates start 1.0 m apart (inside the 1.10 m keep-out): the filter pushes them apart, and the one
    pushed towards the Strike drone (1.16 m away, outside the 1.15 m tag) reaches it. Nobody chose that tag."""
    game, pg, s = play_still([[-1.5, 2.5, 1.2], [-0.5, 2.5, 1.2], [0.66, 2.5, 1.2]], guards=2, strikes=1)
    assert pg["tags"].tolist() == [1] and pg["outcome"].tolist() == [GUARD_WIN]
    assert 1.10 < float(pg["tag_pair_m"][0, 0]) < 1.15                       # tagged inside the bubble band
    assert bool(pg["tag_filtered"][0, 0])
    assert s["tags_counted"] == 1 and s["tags_filtered"] == 1 and s["unchosen_tag_share"] == 1.0


def test_a_tag_the_filter_did_not_make_is_not_unchosen_and_the_edge_count_reads_the_distance():
    """A still 1v1 pair 1.14 m apart: tagged on tick 1, no filter correction (nothing moves), not at the edge (> 1.11 m).
    The same at 1.105 m: still not filtered, but at the filter edge (<= 1.10 + 0.01 m)."""
    _, pg, s = play_still([[-0.5, 2.5, 1.2], [0.64, 2.5, 1.2]], guards=1, strikes=1)
    assert pg["tags"].tolist() == [1] and not bool(pg["tag_filtered"][0, 0])
    assert pg["tag_pair_m"][0, 0] == pytest.approx(1.14, abs=1e-5)
    assert (s["tags_filtered"], s["unchosen_tag_share"], s["tags_at_edge"], s["edge_tag_share"]) == (0, 0.0, 0, 0.0)
    _, pg, s = play_still([[-0.5, 2.5, 1.2], [0.605, 2.5, 1.2]], guards=1, strikes=1)
    assert (s["tags_counted"], s["tags_filtered"], s["tags_at_edge"], s["edge_tag_share"]) == (1, 0, 1, 1.0)
    assert s["tag_edge_m"] == pytest.approx(1.11)


def test_no_tag_records_nothing():
    _, pg, s = play_still([[-0.5, 2.5, 1.2], [0.7, 2.5, 1.2]], guards=1, strikes=1, ticks=20)
    assert pg["tags"].tolist() == [0] and math.isinf(pg["tag_pair_m"][0, 0]) and not pg["tag_filtered"].any()
    assert s["tags_counted"] == 0 and s["unchosen_tag_share"] is None and s["edge_tag_share"] is None


def test_tag_shares_counts_finished_first_games_only_and_needs_an_edge_limit():
    pg = {"outcome": np.array([GUARD_WIN, RUNNING, GUARD_WIN], dtype=np.int8),
          "tag_pair_m": np.array([[1.105, 1.13], [1.12, np.inf], [np.inf, np.inf]]),
          "tag_filtered": np.array([[True, False], [True, False], [False, False]])}
    s = sweep.tag_shares(pg, 1.11)
    assert (s["tags_counted"], s["tags_filtered"], s["tags_at_edge"]) == (2, 1, 1)   # the unfinished game is not counted
    assert s["unchosen_tag_share"] == 0.5 and s["edge_tag_share"] == 0.5 and s["tag_pair_min_m"] == pytest.approx(1.105)
    s = sweep.tag_shares(pg, None)
    assert s["tags_at_edge"] is None and s["edge_tag_share"] is None and s["unchosen_tag_share"] == 0.5
    assert sweep.tag_shares({"outcome": pg["outcome"]}, 1.11) == {}
    assert sweep.tag_edge_m(cfg_of(TAG_FILE), None) is None


def test_the_hook_changes_no_game_and_counts_every_tag():
    """SweepGame's _study_tags (it records the pairs) against SvgGame's own (it does not): the same games, tick for tick
    results; and every tag of a finished first game has a recorded pair."""
    cfg = cfg_of(TAG_FILE)
    cells = (("guard_field", "strike_straight"), ("guard_mirror", "strike_flank"))
    run = {"games_per_cell": 6, "device": "cpu", "seed": 110000, "ticks_cap": 160, "tag_edge_margin_m": 0.01}
    a = sweep.play_batch(cfg, "3v3", cells, run)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(sweep.SweepGame, "_study_tags", SvgGame._study_tags)
        mp.setattr(sweep.SweepGame, "_tick_tag", None, raising=False)
        b = sweep.play_batch(cfg, "3v3", cells, run)
    for key in sweep.PER_GAME_EXACT + ("closest_3d_m", "guards_removed"):
        assert np.array_equal(a.per_game[key], b.per_game[key]), key
    assert int(a.per_game["tags"].sum()) > 0                                    # the test exercises tags
    finished = a.per_game["outcome"] != RUNNING
    assert int(np.isfinite(a.per_game["tag_pair_m"][finished]).sum()) == int(a.per_game["tags"][finished].sum())
    for row in a.rows:
        assert {"tags_counted", "tags_filtered", "unchosen_tag_share", "tags_at_edge", "edge_tag_share"} <= set(row)


# ------------------------------------------------------------------------------------------------ old gate files
def test_the_pinned_l011_and_l012_gate_files_still_load_unchanged():
    old = sweep.load_gates(L011_GATES)
    assert old.reference is None and "tag_edge_margin_m" not in old.run
    l012 = exploit.load_gates(L012_GATES)
    assert exploit.reference_label(l012) == "T44" and exploit.unfilled(l012) == []
    assert exploit.edge_m(l012, cfg_of(BASE_FILE)) is None


# ------------------------------------------------------------------------------------------------ the screen
def test_the_screen_gate_file_plays_every_script_pair_at_tag_1p15_on_t44s_starts():
    g = sweep.load_gates(SCREEN)
    assert g.run["games_per_cell"] == 1000 and g.run["seed"] == 110000 and g.run["tag_edge_margin_m"] == 0.01
    plan = {p.spec.name: p for p in sweep.build_plan(g)}
    assert len(plan["tag_1p15"].cells) == 30 and plan["tag_1p15"].spec.game == "tag_1p15"
    assert len(plan["ctl_reference_replay"].cells) == 30 and plan["ctl_reference_replay"].spec.control == "reference_replay"
    assert g.reference["start_sha256"] == exploit.load_gates(L012_GATES).reference["start_sha256"]
    assert screen.reference_problem(g) is None                                  # the pinned file, T44's starts
    assert set(g.cut["protected"]) == set(plan)                                 # nothing is ever cut
    assert g.shortlist["candidates"] == ["tag_1p15"] == g.shortlist["always"]
    ticks = sum(p.spec.ticks_cap(g.run) * len(p.batches) for p in plan.values())
    projected = ticks * g.projection["seconds_per_batch_tick"]["3v3"] * g.cut["safety_factor"] + g.clips["reserve_s"]
    assert projected <= 0.75 * 3600                                             # the launch cap in the commands


def test_a_reference_replay_group_needs_a_reference_of_its_variant(tmp_path):
    text = SCREEN.read_text().replace('variant = "base"', 'variant = "tag_off"', 1)
    (tmp_path / "g.toml").write_text(text)
    with pytest.raises(ValueError, match="reference_replay"):
        sweep.load_gates(tmp_path / "g.toml")


def tiny_screen(tmp_path, **replace) -> Path:
    """The screen's gate file on the CPU: 4 games per cell, short games (a test of the code path, never a result)."""
    text = SCREEN.read_text()
    edits = {'device = "cuda"': 'device = "cpu"', "games_per_cell = 1000": "games_per_cell = 4",
             "ticks_cap = 2400                   # = the game": "ticks_cap = 300   # smoke",
             "\nticks = 100": "\nticks = 3", "cap_check_every_ticks = 100": "cap_check_every_ticks = 2", **replace}
    for old, new in edits.items():
        assert old in text, old
        text = text.replace(old, new)
    text = text.replace("\nticks = 200", "\nticks = 60", 1).replace("\nticks = 200", "\nticks = 3", 1)   # reach fires; still
    path = tmp_path / "screen_gates.toml"
    path.write_text(text)
    return path


def run_screen(gates, run_dir) -> int:
    return screen.main(["--gates", str(gates), "--run-dir", str(run_dir), "--cap-h", "1", "--no-clips"])


@pytest.fixture(scope="module")
def screen_run(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("l012b_screen")
    mp = pytest.MonkeyPatch()
    mp.setenv(shared.SHARED_ENV, str(tmp / "shared"))
    mp.setenv(shared.LEGACY_LOGS_ENV, "")
    out = tmp / "run"
    code = run_screen(tiny_screen(tmp), out)
    mp.undo()
    return code, out


def test_the_screen_runs_on_the_cpu_with_every_control_passing(screen_run):
    code, out = screen_run
    assert code == EXIT_DONE
    result = json.loads((out / "results.json").read_text())
    assert result["controls_all_pass"], result["controls"]
    assert result["controls"]["ctl_reference_replay"]["status"] == "PASS"
    groups = {g["name"]: g for g in result["groups"]}
    rows = groups["tag_1p15"]["rows"]
    assert len(rows) == 30 and all(r["tag_edge_m"] == pytest.approx(1.11) for r in rows)
    assert all("unchosen_tag_share" in r and "edge_tag_share" in r for r in rows)
    assert result["shortlist"]["shortlist"] == ["tag_1p15"]
    v = result["shortlist"]["variants"][0]
    assert v["variant"] == "tag_1p15" and v.get("reference")                    # carried; g* / s* when every cell ended
    assert v["g_star"] in sweep.load_gates(SCREEN).players["guards"] or "cell" in v["reason"]   # CPU smoke: games cut short
    md = (out / "results.md").read_text()
    assert "# L0.12b scripted screen (INFO): results" in md and "Unchosen tags (INFO, L0.12b)" in md
    assert "unchosen tags: filter on (share)" in md
    starts = exploit.load_reference(ROOT / sweep.load_gates(SCREEN).reference["file"]).starts_m[:4]
    z = np.load(out / "cells" / "tag_1p15__b00.npz")
    assert np.array_equal(z["start_pos_m"][:4], starts)                         # T44's starts, loaded


def test_the_screen_record_names_the_task_the_loaded_starts_and_the_unchosen_tags(screen_run, tmp_path, capsys):
    code, out = screen_run
    assert code == EXIT_DONE
    run = tmp_path / "run"                                                      # a copy: the fixture's folder is shared
    import shutil
    shutil.copytree(out, run)
    (run / "exit_code").write_text("0\n")
    assert screen_record.main(["--run-dir", str(run), "--number", "W0", "--out-dir", str(tmp_path / "rec")]) == 0
    text = (tmp_path / "rec" / "run_record.md").read_text()
    assert "STE task L0.12b scripted screen (INFO)" in text and "STE L0.12b scripted screen:" in capsys.readouterr().out
    assert "T44's first 4 starts, loaded from the reference file" in text and "## Unchosen tags (INFO, L0.12b)" in text
    assert "proposed 1.6 m rules" not in text and "L0.11 Screening sweep" not in text


def test_the_screen_stops_when_the_reference_replay_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(exploit, "replay_ok", lambda *a, **k: (False, "forced by the test"))
    gates = tiny_screen(tmp_path)
    assert run_screen(gates, tmp_path / "run") == EXIT_CONTROL_FAILED
    controls = json.loads((tmp_path / "run" / "controls.json").read_text())
    assert controls["ctl_reference_replay"]["status"] == "FAIL"
    assert not (tmp_path / "run" / "cells" / "tag_1p15__b00.json").exists()      # nothing after the failed replay


def test_the_screen_refuses_a_reference_file_that_is_not_the_pinned_one(tmp_path, capsys):
    gates = tiny_screen(tmp_path, **{'sha256 = "4bc5e011': 'sha256 = "0bc5e011'})
    assert run_screen(gates, tmp_path / "run") == EXIT_REFUSED
    assert "reference file" in capsys.readouterr().err


# ------------------------------------------------------------------------------------------------ the best-response gate
def set_line(text: str, key: str, value: str) -> str:
    """``key = "..."`` at the start of a line (the first one) set to ``value``: works before and after the lead's fill."""
    out, n = re.subn(rf'^{key} = "[^"]*"', f'{key} = "{value}"', text, count=1, flags=re.M)
    assert n == 1, key
    return out


def test_the_runs_gate_file_refuses_while_a_value_is_unfilled(tmp_path, capsys):
    g = exploit.load_gates(GATES)
    assert exploit.unfilled(g) in ([], ["[reference] sha256"])                  # committed unfilled; the lead fills it
    assert list(g.variants) == ["tag_1p15"] and g.run0["variant"] == "tag_1p15" and g.run["task"] == "L0.12"
    assert g.run["tag_edge_margin_m"] == 0.01 and exploit.reference_label(g) != "T44"
    assert g.reference["t44_gates_sha256"] == sweep.load_gates(SCREEN).sha256     # the screen's gate file
    unfilled = tmp_path / "gates.toml"
    unfilled.write_text(set_line(GATES.read_text(), "sha256", "FILL_AFTER_SCREEN"))
    assert exploit.unfilled(exploit.load_gates(unfilled)) == ["[reference] sha256"]
    pj = tmp_path / "pilot.json"
    pj.write_text(json.dumps({"strike_recipe": {"side_overrides_strike": {"shaping_weight": 1.0}}}))
    code = driver.main(["--gates", str(unfilled), "--variant", "tag_1p15", "--side", "guard", "--run-dir",
                        str(tmp_path / "r"), "--cap-h", "0.75", "--pilot-json", str(pj)])
    assert code == EXIT_REFUSED and "not filled yet" in capsys.readouterr().err


def test_the_runs_gate_file_keeps_l012s_trainer_but_the_step_budget():
    new, old = exploit.load_gates(GATES), exploit.load_gates(L012_GATES)
    assert {k: v for k, v in new.trainer.items() if k != "game_steps_per_run"} == \
           {k: v for k, v in old.trainer.items() if k != "game_steps_per_run"}
    assert (new.controls, new.verdict["band"], new.verdict["gain_rule"], new.verdict["learned_rule"]) == \
           (old.controls, old.verdict["band"], old.verdict["gain_rule"], old.verdict["learned_rule"])
    assert {k: v for k, v in new.run.items() if k != "tag_edge_margin_m"} == old.run
    assert new.run0["train_seed"] not in [s for v in new.variants.values() for s in v["train_seed"].values()]


def test_l012s_pilot_json_is_accepted_by_the_runs_gate_file_on_both_sides():
    """LEAD CALL 21 Nov 2026 (L0.12b): L0.12's pilot is reused. The driver reads only its Strike recipe."""
    g = exploit.load_gates(GATES)
    pilot = {"gates_sha256": "9220fd9f0eba545a18d6cc3779a35aaf97618eacf7a9e74b30f0c1efbc31f060",   # L0.12's pilot
             "strike_recipe": {"recipe": exploit.RECIPE_SHAPED, "side_overrides_strike": {"shaping_weight": 1.0}}}
    assert exploit.recipe_problem(g, pilot) is None
    assert exploit.pilot_problem(g, pilot, "guard") is None
    run0 = {"complete": True, "status": "PASS", "cap_h": 0.75, "gates_sha256": g.sha256}
    assert exploit.pilot_problem(g, pilot, "strike", run0=run0, cap_h=0.75) is None
    assert "run 0 ran under gate" in exploit.pilot_problem(g, pilot, "strike", run0={**run0, "gates_sha256": "x"},
                                                           cap_h=0.75)          # L0.12's run 0 is not reusable


# Measured on L0.12's runs (laptop RTX 5070 Ti, 21 Nov 2026; train_log.jsonl, curve.json, results.json of each run).
WORST_STRIKE_UPDATE_S = 20.0           # tag_1p4 Strike, max of every update (median 19.5)
WORST_CURVE_READ_S = 53.8              # tag_1p4 Strike, max of every curve read (256 games to the 120 s time-out)
WORST_CONTROLS_BATCH_S = 95.0          # tag_1p2 Strike: final reserve 620 s = 2 x (2 b + 120)
MARGIN = 1.05


def updates_that_start(cap_s, batch_s, update_s, read_s, every, start_s, reserve_s):
    """The highest update N whose start the driver allows (cap left >= reserve before it): run_exploit's loop."""
    n = 0
    while start_s + batch_s + n * update_s + (n // every) * read_s <= cap_s - reserve_s:
        n += 1
    return n


def test_the_step_budget_cannot_stop_at_the_cap_reserve_by_construction():
    g = exploit.load_gates(GATES)
    tr = g.trainer
    per_update = int(tr["rollouts"]) * int(tr["decision_ticks"]) * int(tr["num_games"])
    planned = math.ceil(int(tr["game_steps_per_run"]) / per_update)
    batch = 100.0                                                             # >= the worst measured, 95 s
    assert batch >= WORST_CONTROLS_BATCH_S
    reserve = exploit.final_reserve_s(tr, batch)
    fits = updates_that_start(0.75 * 3600, batch, WORST_STRIKE_UPDATE_S * MARGIN, WORST_CURVE_READ_S * MARGIN,
                              int(tr["curve_every_updates"]), 60.0, reserve)
    assert planned == 72 and fits >= planned                                  # every planned update starts
    assert planned * per_update >= int(tr["game_steps_per_run"])              # and meets the budget
    old = exploit.load_gates(L012_GATES).trainer                              # L0.12's 550 M did not fit (T47)
    assert math.ceil(int(old["game_steps_per_run"]) / per_update) > fits


# ------------------------------------------------------------------------------------------------ end to end (CPU)
def test_screen_to_reference_to_a_guard_run_and_its_record(screen_run, tmp_path, monkeypatch):
    """The screen's run folder -> the reference builder -> the runs' gate file filled (CPU sizes) -> a Guard run whose
    results carry the unchosen-tag shares -> verdict -> record."""
    code, out = screen_run
    assert code == EXIT_DONE
    ref_path = tmp_path / "screen_reference.npz"
    assert ref_script.main(["--t44", str(out), "--out", str(ref_path), "--variants", "tag_1p15"]) == 0
    ref = exploit.load_reference(ref_path)
    players = exploit.load_gates(GATES).players
    g_star, s_star = exploit.star_players(ref, "tag_1p15", players)
    text = GATES.read_text()                       # filled or not: the fill fields are set by pattern
    text = set_line(set_line(set_line(text, "file", str(ref_path)), "sha256", exploit.sha256_file(ref_path)),
                    "start_sha256", ref.start_sha256)
    text, n = re.subn(r'g_star = "[^"]*", s_star = "[^"]*"', f'g_star = "{g_star}", s_star = "{s_star}"', text, count=1)
    assert n == 1
    for old, new in {'device = "cuda"': 'device = "cpu"', "eval_games = 1000": "eval_games = 4",
                     "ticks_cap = 2400": "ticks_cap = 40", "curve_games = 256": "curve_games = 2",
                     "num_games = 16384": "num_games = 4", "game_steps_per_run = 450_000_000": "game_steps_per_run = 192",
                     "rollouts = 32": "rollouts = 2", "learning_epochs = 5": "learning_epochs = 1",
                     "mini_batches = 4": "mini_batches = 1", "final_reserve_s = 600": "final_reserve_s = 60",
                     "curve_every_updates = 10": "curve_every_updates = 2"}.items():
        assert old in text, old
        text = text.replace(old, new, 1)
    gates = tmp_path / "gates.toml"
    gates.write_text(text)
    pj = tmp_path / "pilot.json"
    pj.write_text(json.dumps({"strike_recipe": {"side_overrides_strike": {"shaping_weight": 1.0}}}))
    run_dir = tmp_path / "guard"
    assert driver.main(["--gates", str(gates), "--variant", "tag_1p15", "--side", "guard", "--run-dir", str(run_dir),
                        "--cap-h", "1", "--no-videos", "--pilot-json", str(pj)]) == EXIT_DONE
    controls = json.loads((run_dir / "controls.json").read_text())
    assert all(c["status"] == "PASS" for c in controls.values()), controls   # the screen's cells replayed
    res = json.loads((run_dir / "results.json").read_text())
    shares = res["tag_shares"]
    assert shares["edge_m"] == pytest.approx(1.11) and len(shares["cells"]) == 7 and len(shares["info"]) == 6
    assert res["reference_label"] == exploit.reference_label(exploit.load_gates(gates))
    md = (run_dir / "results.md").read_text()
    assert "## INFO: unchosen tags (L0.12b)" in md and "T44 reference" not in md
    assert driver.main(["verdict", "--gates", str(gates), "--runs", str(run_dir), "--out", str(tmp_path / "v")]) == 0
    verdict = json.loads((tmp_path / "v" / "verdict.json").read_text())
    assert verdict["variants"]["tag_1p15"]["sides"]["guard"]["tag_shares"]["cell"].startswith("exploiter v ")
    rec = tmp_path / "rec.md"
    assert record.main(["--verdict", str(tmp_path / "v" / "verdict.json"), "--out", str(rec), "--task", "L0.12b"]) == 0
    text = rec.read_text()
    assert "STE L0.12b" in text and "Unchosen tags of the trained exploiter" in text and "for each shortlisted" not in text
    # run 0 under this gate file: tag_1p15 against the parked Guard, its script cell replayed from the screen's reference
    r0 = tmp_path / "run0"
    assert driver.main(["--run0", "--gates", str(gates), "--run-dir", str(r0), "--cap-h", "1", "--no-videos",
                        "--pilot-json", str(pj)]) == EXIT_DONE
    lc = json.loads((r0 / "learner_control.json").read_text())
    assert lc["variant"] == "tag_1p15" and lc["opponent"] == PARKED and lc["status"] in ("PASS", "FAIL", "INCONCLUSIVE")
    assert all(c["status"] == "PASS" for c in json.loads((r0 / "controls.json").read_text()).values())
