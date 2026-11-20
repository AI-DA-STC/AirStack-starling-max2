"""STE learning track, task L0.14 "Crazyflie route check" (PLAN.md section 4): the two drivers and their figures.

Part 1, scripts/ste_l014_response_check.py: the STE Guard policy (T41) in its own hangar game with a slower drone. The
slower drone is a derived parameter file that differs from params/real_exploratory_v0.toml in ``[px4] delay_s`` only;
no default and no core code changes. These tests check the derivation, the step probe, the paired comparison, and, on
game outputs, that the default path is untouched (bit for bit) and that the slower file does change the games.

Part 2, scripts/ste_l014_arena_fit.py: the Crazyflie repository's offline planner run from a copy outside that
repository. These tests check the hand-set marks, the square arena file, the refusal to work inside the repository,
the per-case summary, and (when the repository and its interpreter exist) one real match through the child.
"""
import json
import math
import os
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import numpy as np
import pytest
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import ste_l014_arena_fit as af  # noqa: E402
import ste_l014_response_check as rc  # noqa: E402

CONFIG = ROOT / "configs" / "ste_l014.toml"
BASE = ROOT / "params" / "real_exploratory_v0.toml"


# ------------------------------------------------------------------------------------------------ the settings file
def test_config_loads_and_names_the_fitted_delay():
    cfg = rc.load_config(CONFIG)
    from svg_training.models.fitted import load_params
    assert load_params(ROOT / cfg["response"]["base_params"])["px4"]["delay_s"] == cfg["response"]["fitted_delay_s"]
    assert cfg["response"]["fitted_delay_s"] in cfg["response"]["delays_s"]           # the reference cell is in the list
    assert max(cfg["response"]["delays_s"]) == pytest.approx(0.56)                     # the Crazyflie-like cell


def test_config_refuses_an_unknown_or_missing_key(tmp_path):
    text = CONFIG.read_text()
    bad = tmp_path / "unknown.toml"
    bad.write_text(text.replace("games = 1000", "games = 1000\ngamez = 3", 1))
    with pytest.raises(ValueError, match="gamez"):
        rc.load_config(bad)
    bad.write_text(text.replace("eval_seed = 1101", "", 1))
    with pytest.raises(ValueError, match="eval_seed"):
        rc.load_config(bad)


# ------------------------------------------------------------------------------------------------ the derived file
def test_derived_file_differs_from_the_base_in_delay_only(tmp_path):
    from svg_training.models.fitted import load_params
    out = rc.derive_params(BASE, 0.56, tmp_path / "d.toml")
    base, new = load_params(BASE), load_params(out)
    assert new["px4"]["delay_s"] == 0.56
    new["px4"]["delay_s"] = base["px4"]["delay_s"]
    assert new == base
    assert "SENSITIVITY" in out.read_text().splitlines()[0]         # labelled as what it is, on its first line
    assert "Crazyflie model" in out.read_text()                     # ... and says it is NOT a Crazyflie model


def test_derived_file_at_the_fitted_delay_loads_equal_to_the_base(tmp_path):
    from svg_training.models.fitted import load_params
    out = rc.derive_params(BASE, 0.1482, tmp_path / "same.toml")
    assert load_params(out) == load_params(BASE)


def test_derive_refuses_a_file_without_exactly_one_delay(tmp_path):
    two = tmp_path / "two.toml"
    two.write_text(BASE.read_text() + "\n[extra]\ndelay_s = 1.0\n")
    with pytest.raises(ValueError, match="delay_s"):
        rc.derive_params(two, 0.3, tmp_path / "o.toml")
    none = tmp_path / "none.toml"
    none.write_text(BASE.read_text().replace("delay_s = 0.1482", "", 1))
    with pytest.raises(ValueError, match="delay_s"):
        rc.derive_params(none, 0.3, tmp_path / "o2.toml")


# ------------------------------------------------------------------------------------------------ the step probe
def test_step_probe_trails_longer_with_the_longer_delay(tmp_path):
    fast = rc.trailing(rc.derive_params(BASE, 0.1482, tmp_path / "a.toml"), 0.5, 12.0, 9.0)
    slow = rc.trailing(rc.derive_params(BASE, 0.56, tmp_path / "b.toml"), 0.5, 12.0, 9.0)
    # the Starling cell trails by about its delay plus the PX4 loop's own lag (measured 21 Nov: about 0.22 s)
    assert 0.1482 < fast["trailing_s"] < 0.3
    # the longer delay trails by at least the added delay (measured: more, as the commander's leash then binds)
    assert slow["trailing_s"] - fast["trailing_s"] >= 0.56 - 0.1482 - 0.02
    assert len(fast["t_s"]) == len(fast["x_m"]) == len(fast["cmd_x_m"]) == round(12.0 / 0.05)


# ------------------------------------------------------------------------------------------------ the paired comparison
def test_paired_flips_count_each_direction():
    from svg_training.core.rewards import GUARD_WIN, STRIKE_WIN
    ref = np.array([GUARD_WIN, GUARD_WIN, STRIKE_WIN, STRIKE_WIN, GUARD_WIN])
    cell = np.array([GUARD_WIN, STRIKE_WIN, GUARD_WIN, STRIKE_WIN, STRIKE_WIN])
    assert rc.paired(ref, cell) == {"both_hold": 1, "lost_here": 2, "gained_here": 1, "both_lost": 1, "games": 5}


def test_paired_refuses_unfinished_or_unequal_games():
    from svg_training.core.rewards import GUARD_WIN, RUNNING
    with pytest.raises(ValueError):
        rc.paired(np.array([GUARD_WIN, RUNNING]), np.array([GUARD_WIN, GUARD_WIN]))
    with pytest.raises(ValueError):
        rc.paired(np.array([GUARD_WIN]), np.array([GUARD_WIN, GUARD_WIN]))


# ------------------------------------------------------------------------------------------------ on game outputs
def _game_files_present() -> bool:
    cfg = rc.load_config(CONFIG)["response"]
    return (ROOT / "configs" / "local" / "nus_rules.toml").exists() and (ROOT / cfg["guard_run"] / "agent.pt").exists()


needs_game = pytest.mark.skipif(not _game_files_present(), reason="configs/local or the T41 run folder not installed "
                                                                 "(scripts/nus_install_provisional.sh)")


@pytest.fixture(scope="module")
def short_games(tmp_path_factory):
    """Four paired starts, 120 ticks, three ways: the default path (no params change), a derived file at the fitted
    delay, and a derived file at 0.56 s."""
    tmp = tmp_path_factory.mktemp("l014")
    cfg = rc.load_config(CONFIG)["response"]
    torch.set_num_threads(2)
    out = {"default": rc.play(cfg, None, games=4, max_steps=120)}
    out["same"] = rc.play(cfg, rc.derive_params(BASE, cfg["fitted_delay_s"], tmp / "same.toml"), games=4, max_steps=120)
    out["slow"] = rc.play(cfg, rc.derive_params(BASE, 0.56, tmp / "slow.toml"), games=4, max_steps=120)
    return out


@needs_game
def test_default_path_is_bit_identical_through_a_derived_file_at_the_fitted_delay(short_games):
    a, b = short_games["default"], short_games["same"]
    assert rc.identical(a, b) == []                                  # every output tensor equal, bit for bit
    assert a["pos_m"].abs().sum() > 0                                 # the drones exist and moved somewhere


@needs_game
def test_default_path_equals_the_direct_pilot_path(short_games):
    """The driver's default path is T41's evaluation path (nus/pilot.py pilot_games + play_match, the Guard held 12 ticks)
    built here independently."""
    from svg_training.core.play import play_match
    from svg_training.nus import pilot as P
    from svg_training.opponents.learned import SkrlPolicyStrategy
    cfg = rc.load_config(CONFIG)["response"]
    w = P.pilot_world(0.0)
    _, ev = P.pilot_games(w, 1, [4], "cpu", cfg["eval_seed"], cfg["eval_seed"])
    g = ev[4]
    opp = P.mix_strategy([(cfg["opponent"], slice(0, 4))], "strike", w.cfg, "cpu", cfg["eval_seed"] + cfg["opponent_seed_offset"])
    guard = P.HeldStrategy(SkrlPolicyStrategy(ROOT / cfg["guard_run"], 4, "cpu"), P.decision_ticks("deploy", w))
    g.gen.manual_seed(cfg["eval_seed"])
    res = play_match(g, guard, opp, max_steps=120)
    assert torch.equal(res.closest_cross_3d_m, short_games["default"]["closest_cross_3d_m"])
    assert torch.equal(g.pos_m, short_games["default"]["pos_m"])


@needs_game
def test_the_slow_file_changes_the_games(short_games):
    assert rc.identical(short_games["default"], short_games["slow"]) != []
    assert not torch.equal(short_games["default"]["pos_m"], short_games["slow"]["pos_m"])


# ------------------------------------------------------------------------------------------------ part 2: the planner
def test_hand_marks_geometry_for_every_size():
    cfg = rc.load_config(CONFIG)["arena_fit"]
    for g, s in cfg["sizes"]:
        marks = af.hand_marks(g, s, cfg["defender_ring_m"], cfg["attacker_ring_m"], (0.0, 0.0), cfg["bearing0_deg"])
        d = [k for k in marks if k.startswith("D")]
        a = [k for k in marks if k.startswith("A")]
        assert len(d) == g and len(a) == s
        for k in d:
            assert math.hypot(*marks[k][:2]) == pytest.approx(cfg["defender_ring_m"])
        for k in a:
            assert math.hypot(*marks[k][:2]) == pytest.approx(cfg["attacker_ring_m"])
        names = list(marks)
        for i, p in enumerate(names):
            for q in names[i + 1:]:
                assert math.dist(marks[p][:2], marks[q][:2]) >= cfg["d_cc_m"]             # the planner's spacing check
        for k in a:                                                                      # outside the default reach + 0.5
            assert min(math.dist(marks[k][:2], marks[j][:2]) for j in d) >= 1.15 + 0.5
        assert all(marks[k][2] == 0.0 for k in names)                                     # floor marks


def test_hand_marks_refuse_more_attackers_than_gaps():
    with pytest.raises(ValueError):
        af.hand_marks(2, 3, 1.4, 2.75, (0.0, 0.0), 0.0)


def test_square_arena_keeps_the_file_and_replaces_the_room(tmp_path):
    import yaml
    base = Path(os.path.expanduser(rc.load_config(CONFIG)["arena_fit"]["cf_repo"])) / rc.load_config(CONFIG)["arena_fit"]["arena_yaml"]
    text = base.read_text() if base.exists() else (
        "arena:\n  measured: true\n  centre: [-0.2, -0.1]\n  radius_tested: 4.0\n  radius_lost: 4.3\n"
        "  ceiling_tested: 7.0\n  ceiling_centre_tested: 7.0\n  ceiling_pinch_radius: 4.0\n"
        "  polygon:\n    - [5, -5]\n    - [5, 5]\n    - [-5, 5]\nseparation:\n  minimum: 0.8\n  tracking_margin: 0.1\n")
    d0 = yaml.safe_load(text)
    out = af.square_arena(text, 6.5)
    d = yaml.safe_load(out)
    cx, cy = d0["arena"]["centre"]
    poly = np.array(d["arena"]["polygon"])
    assert poly.shape == (4, 2)
    assert poly[:, 0].max() - poly[:, 0].min() == pytest.approx(6.5)
    assert poly[:, 1].max() - poly[:, 1].min() == pytest.approx(6.5)
    assert poly.mean(axis=0) == pytest.approx([cx, cy])
    assert d["arena"]["radius_tested"] == pytest.approx(3.25)                            # the circle inside the square
    assert d["separation"] == d0["separation"] and d["arena"]["measured"] is True
    x, y = poly[:, 0], poly[:, 1]
    assert 0.5 * np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y) > 0                      # counter-clockwise


def test_work_dir_inside_the_crazyflie_repository_is_refused(tmp_path):
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    with pytest.raises(ValueError, match="inside"):
        af.check_work_dir(repo, repo / "scratch")
    with pytest.raises(ValueError, match="inside"):
        af.check_work_dir(repo, repo)
    af.check_work_dir(repo, tmp_path / "elsewhere")                                    # outside: fine


def test_case_summary_counts_matches_not_ticks():
    rows = [
        {"winner": "defense", "emergency": 0, "backstop": 0, "failures": [], "sep_m": 1.2},
        {"winner": "attack", "emergency": 7, "backstop": 0, "failures": ["solver emergency push-apart on 7 ticks"], "sep_m": 0.9},
        {"winner": "defense", "emergency": 0, "backstop": 2, "failures": ["backstop clamp fired 2 times"], "sep_m": 1.05},
        {"winner": "defense", "emergency": 1, "backstop": 0, "failures": ["solver emergency push-apart on 1 ticks"], "sep_m": 1.3},
    ]
    s = af.summarise_case(rows, d_cc_m=1.10)
    assert s["matches"] == 4 and s["defence_wins"] == 3
    assert s["emergency_matches"] == 2 and s["emergency_ticks"] == 8
    assert s["other_failure_matches"] == 1                       # the backstop match; emergencies counted apart
    assert s["closest_pair_m"] == pytest.approx(0.9)
    assert s["matches_closer_than_d_cc"] == 2


def test_follow_up_cases_change_one_thing_each():
    cfg = rc.load_config(CONFIG)["arena_fit"]
    base = {c["name"]: c for c in af.cases(cfg) if c["kind"] == "pairing"}
    follow = [c for c in af.cases(cfg) if c["kind"].startswith("followup")]
    assert len(follow) == len(cfg["followup_sizes"]) * len(cfg["followup_arenas"]) * len(cfg["followup_variants"])
    for c in follow:
        twin = base[f"{c['defenders']}v{c['attackers']}_{c['arena']}_tau{cfg['tau_s']}"]
        extra = {k for k in c if k not in twin or c[k] != twin[k]} - {"name", "kind"}
        assert extra in ({"finale"}, {"strike_radius_m"})                     # exactly one change from the sweep's case
    assert {c["name"] for c in follow}.isdisjoint(base)


def _planner_available() -> bool:
    cfg = rc.load_config(CONFIG)["arena_fit"]
    repo = Path(os.path.expanduser(cfg["cf_repo"]))
    if not (repo / cfg["package"]).is_dir() or not Path(cfg["python"]).exists():
        return False
    return subprocess.run([cfg["python"], "-c", "import numpy, scipy, yaml"], capture_output=True).returncode == 0


@pytest.mark.skipif(not _planner_available(), reason="the Crazyflie repository or its interpreter (numpy, scipy, yaml) is "
                                                     "not on this machine")
def test_one_real_match_through_the_copy_leaves_the_repository_untouched(tmp_path):
    cfg = rc.load_config(CONFIG)["arena_fit"]
    repo = Path(os.path.expanduser(cfg["cf_repo"]))
    before = subprocess.run(["git", "-C", str(repo), "status", "--porcelain", "--ignored"], capture_output=True, text=True).stdout
    work = tmp_path / "work"
    prov = af.prepare(cfg, work)
    case = {"name": "t_1v1_room", "defenders": 1, "attackers": 1, "arena": "room", "tau_s": cfg["tau_s"], "kind": "pairing",
            "pairings": [cfg["pairing"]], "seeds": [0]}
    out = af.run_case(cfg, prov, case, tmp_path / "out")
    data = json.loads(out.read_text())
    assert data["refused"] == [] and len(data["rows"]) == 1
    row = data["rows"][0]
    assert row["winner"] in ("defense", "attack") and row["sep_m"] > 0
    assert data["marks"]["D1"] and data["settings"]["d_cc"] == pytest.approx(1.10)
    assert data["rules"]["strike_radius"] == pytest.approx(cfg["strike_radius_m"])     # the STE zone radius, not 2.4 m
    after = subprocess.run(["git", "-C", str(repo), "status", "--porcelain", "--ignored"], capture_output=True, text=True).stdout
    assert after == before                                         # nothing written inside that repository
    assert prov["commit"] and len(prov["package_sha256"]) == 64


# ------------------------------------------------------------------------------------------------ figures
def test_figures_are_drawn_from_the_results(tmp_path):
    import make_ste_l014_figures as mf
    resp = {"cells": [{"delay_s": d, "hold": h, "holds": round(h * 256), "games": 256, "ci": [h - 0.05, h + 0.05], "trailing_s": t,
                       "paired": {"lost_here": 3, "gained_here": 1},
                       "rule_breach_share": h / 10, "closest_3d_min_m": t}
                      for d, h, t in ((0.1482, 0.8, 0.2), (0.3, 0.7, 0.35), (0.56, 0.6, 0.62))],
            "step": [{"delay_s": d, "t_s": [0.05, 0.1], "x_m": [0.0, 0.01], "cmd_x_m": [0.025, 0.05]} for d in (0.1482, 0.56)],
            "reference_cell": 0}
    arena = {"cases": [{"name": f"{g}v{s}_{a}", "defenders": g, "attackers": s, "arena": a, "tau_s": 0.6, "kind": "pairing",
                        "summary": {"matches": 100, "emergency_matches": e, "defence_wins": 50, "closest_pair_m": 0.9,
                                    "other_failure_matches": 0, "matches_closer_than_d_cc": 1, "emergency_ticks": e},
                        "refused": []}
                       for (g, s), e in (((1, 1), 0), ((2, 1), 0), ((3, 3), 5), ((5, 3), 5))
                       for a in ("square_6_5", "circle_3_25", "room")]}
    (tmp_path / "response.json").write_text(json.dumps(resp))
    np.savez(tmp_path / "per_game.npz", **{f"delay_{d:.4f}__closest_cross_3d_m": np.array([0.3, 0.8, 1.05, 2.0])
                                          for d in (0.1482, 0.3, 0.56)})
    assert mf.closest_counts({**resp, "per_game_path": str(tmp_path / "per_game.npz")})[0.3] == {1.10: 3, 1.0: 2, 0.50: 1}
    (tmp_path / "arena.json").write_text(json.dumps(arena))
    out = tmp_path / "fig"
    assert mf.main(["--response", str(tmp_path / "response.json"), "--arena", str(tmp_path / "arena.json"), "--out", str(out)]) == 0
    for name in ("l014_hold_by_delay.png", "l014_step.png", "l014_arena_fit.png"):
        assert (out / name).stat().st_size > 1000
