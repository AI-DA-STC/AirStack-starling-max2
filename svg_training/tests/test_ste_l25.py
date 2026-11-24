"""STE task L2.5 Parked-Guard control and scripted opponents under the new rules (INFO): the CPU screen's game files and
gate file (configs/ste_l2/l25_*.toml, configs/ste_l2/l25_screen_gates.toml; spec ste_learning/drafts/L2_5_SPEC.md).

What is checked here (CPU only): each game file is configs/ste_l011/base.toml value for value but for its marked keys,
with the labels the rulings give; the gate file pins every game file and T44's reference, plays every group at 3v3 on
the CPU from T44's starts, holds the planned cells, and its worst case fits the cap it states; the screen's driver
(scripts/ste_sweep_l011.py, ste/sweep.py) passes [landing] and [filter] share through to the game unchanged (a tagged
pair lands and stays counted one for one; option B moves drones); and the screen at test sizes runs with every control
passing. The rules themselves are tested in tests/test_landing.py and tests/test_safety_filter_option_b.py."""
from __future__ import annotations

import copy
import json
import sys
import tomllib
from pathlib import Path

import numpy as np
import pytest
import torch

from svg_training.ste import exploit, shared, sweep
from svg_training.ste.run_contract import EXIT_DONE

ROOT = sweep.ROOT
sys.path.insert(0, str(ROOT / "scripts"))
import ste_sweep_l011 as screen  # noqa: E402

L2 = ROOT / "configs" / "ste_l2"
GATES = L2 / "l25_screen_gates.toml"
BASE = ROOT / "configs" / "ste_l011" / "base.toml"
TAG_OFF_L011 = ROOT / "configs" / "ste_l011" / "tag_off.toml"
L012B = ROOT / "configs" / "ste_l012b" / "screen_gates.toml"
LANDING = {"enabled": True, "land_speed_mps": 0.6, "touchdown_z_m": 0.15}
OPTION_B = {"share": "guard_yields"}
# file -> (the tables it adds, the [tag] keys it changes)
FILES = {
    "l25_landing": ({"landing": LANDING}, {}),
    "l25_gy": ({"filter": OPTION_B}, {}),
    "l25_landing_gy": ({"landing": LANDING, "filter": OPTION_B}, {}),
    "l25_landing_tag_off": ({"landing": LANDING}, {"mode": "off"}),
    "l25_landing_gy_tag_off": ({"landing": LANDING, "filter": OPTION_B}, {"mode": "off"}),
    "l25_landing_gy_tag_10m": ({"landing": LANDING, "filter": OPTION_B}, {"radius_m": 10.0}),
    "l25_landing_gy_tag_0p05": ({"landing": LANDING, "filter": OPTION_B}, {"radius_m": 0.05}),
}
GUARDS = ["guard_parked_centre", "guard_parked_ring", "guard_mark_edge", "guard_mirror", "guard_field"]
STRIKES = ["strike_straight", "strike_flank", "strike_high", "strike_low", "strike_sacrifice", "strike_converge"]
PARKED = ["guard_parked_centre", "guard_parked_ring"]


def _cfg(path: Path):
    return sweep.load_game_cfg(path, local_dir=None, use_local=False)[0]


def _t44_starts(n: int):
    ref = exploit.load_reference(ROOT / sweep.load_gates(GATES).reference["file"])
    return torch.as_tensor(ref.starts_m[:n]), torch.as_tensor(ref.start_miss[:n])


# ================================================================================================ the game files
@pytest.mark.parametrize("name", list(FILES))
def test_each_game_file_is_base_but_for_its_marked_keys(name):
    tables, tag = FILES[name]
    want = copy.deepcopy(tomllib.loads(BASE.read_text()))
    want.update(copy.deepcopy(tables))
    want["tag"].update(tag)
    path = L2 / f"{name}.toml"
    assert tomllib.loads(path.read_text()) == want
    cfg = _cfg(path)                                                              # the loader accepts it
    assert cfg.landing.enabled is ("landing" in tables)
    assert cfg.filter.share == ("guard_yields" if "filter" in tables else "equal")
    assert cfg.team_size.mode == "fixed" and cfg.dropout_fraction == 0.0             # P7's drawn sizes are not here
    head = path.read_text().split("\n\n")[0].replace("\n# ", " ")              # the header comment, one line
    assert "Study file: no run of record uses it" in head
    marked = head.split("except the lines marked L2.5: ")[1].split(". Values")[0]
    assert marked == ", ".join([f"tag.{k}" for k in tag] + [f"[{k}]" for k in tables])


def test_the_labels_follow_the_rulings():
    for name, (tables, _) in FILES.items():
        text = (L2 / f"{name}.toml").read_text()
        if "landing" in tables:
            assert 'touchdown_z_m = 0.15               # L2.5: FIXED (owner ruling R28' in text, name
        if "filter" in tables:
            line = next(x for x in text.splitlines() if x.startswith("share = "))
            assert "PROPOSED, P2 OPEN" in line and "no run of record uses it" in line, name
    assert "[landing]" not in BASE.read_text() and "[filter]" not in BASE.read_text()     # T44's file untouched


# ================================================================================================ the gate file
def test_the_gate_file_pins_every_file_and_plays_3v3_on_the_cpu_from_t44s_starts():
    g = sweep.load_gates(GATES)
    assert not sweep.game_file_problems(g)
    for name in FILES:
        assert g.games[name].file == f"configs/ste_l2/{name}.toml"
        assert g.games[name].sha256 == exploit.sha256_file(L2 / f"{name}.toml")
    assert g.games["base"].file == "configs/ste_l011/base.toml"
    assert g.run["task"] == "L2.5" and g.run["kind"] == "INFO" and g.run["device"] == "cpu"
    assert g.run["games_per_cell"] == 1000 and g.run["ticks_cap"] == 2400 and g.run["seed"] == 110000
    assert g.reference == sweep.load_gates(L012B).reference                     # T44's starts and cells, as L0.12b
    assert screen.reference_problem(g) is None                                   # every group can play T44's starts
    assert g.players["guards"] == GUARDS and g.players["strikes"] == STRIKES
    plan = {p.spec.name: p for p in sweep.build_plan(g)}
    assert all(sweep.group_game(g, p.spec)[1] == "3v3" for p in plan.values())
    sweeps = {n: (p.spec.game, len(p.cells)) for n, p in plan.items() if p.spec.role == "sweep"}
    assert sweeps == {"landing": ("l25_landing", 30), "gy": ("l25_gy", 30), "landing_gy": ("l25_landing_gy", 30)}
    ctl = {n: (p.spec.control, p.spec.game, len(p.cells)) for n, p in plan.items() if p.spec.role == "control"}
    assert ctl == {"ctl_tag_fires_3v3": ("tag_fires", "l25_landing_gy_tag_10m", 1),
                   "ctl_reach_fires_3v3": ("reach_fires", "zone_2p4_tag_off", 1),
                   "ctl_reference_replay": ("reference_replay", "base", 30),
                   "ctl_same_seed": ("same_seed_twice", None, 30),
                   "ctl_tag_off_landing": ("zero_tags", "l25_landing_tag_off", 12),
                   "ctl_tag_off_landing_gy": ("zero_tags", "l25_landing_gy_tag_off", 12),
                   "ctl_stand_still": ("stand_still_never_reaches", "l25_landing_gy", 5),
                   "ctl_still_3v3": ("stand_still_zero_tags", "l25_landing_gy", 1),
                   "ctl_tiny_tag": ("zero_tags", "l25_landing_gy_tag_0p05", 5)}
    assert plan["ctl_same_seed"].spec.of_group == "landing_gy"
    for name in ("ctl_tag_off_landing", "ctl_tag_off_landing_gy"):                # the parked Guards without the tag
        assert {c[0] for c in plan[name].cells} == set(PARKED) and {c[1] for c in plan[name].cells} == set(STRIKES)
    assert sum(len(p.cells) for p in plan.values()) == 187 and sum(len(p.batches) for p in plan.values()) == 12
    assert sorted(g.cut["protected"]) == sorted(plan)                            # nothing is cut
    assert set(g.shortlist["candidates"]) == set(g.shortlist["always"]) == {"landing", "gy", "landing_gy"}
    assert set(g.shortlist["info_reference"]) == {"ctl_reference_replay", "ctl_tag_off_landing", "ctl_tag_off_landing_gy"}


def test_the_worst_case_fits_the_cap_the_header_states():
    g = sweep.load_gates(GATES)
    plan = sweep.build_plan(g)
    ticks = sum(p.spec.ticks_cap(g.run) * len(p.batches) for p in plan)
    assert ticks == 18_500
    projected = ticks * g.projection["seconds_per_batch_tick"]["3v3"] * g.cut["safety_factor"] + g.clips["reserve_s"]
    assert projected == pytest.approx(14_845)
    assert projected <= 4.5 * 3600 and "--cap-h is the effective-hour cap of the job (4.5)" in GATES.read_text()
    assert screen.project_cuts(g, plan, 0, {"done": [], "cut": [], "timing": {}}, 4.5 * 3600) == ([], pytest.approx(14_845))


# ================================================================================================ the driver passes the rules
def test_a_tagged_pair_lands_through_the_screens_game_and_stays_one_for_one():
    """The tag-fires game with landing on: every pair is tagged on the first tick; all six drones are then landing (they
    stay filter obstacles), and the screen's counters still read three tags and three Guard drones out."""
    game = sweep.SweepGame(_cfg(L2 / "l25_landing_gy_tag_10m.toml"), 1, 4, 3, 3, "cpu", 110000)
    game.reset()
    zero = torch.zeros(4, 3, 4)
    out = game.step({"guard": zero, "strike": zero})
    assert out.info["landing"].all() and not out.info["final_alive"].any() and out.done.all()
    assert game.tags.tolist() == [3] * 4 and game.guards_removed.tolist() == [3] * 4
    old = sweep.SweepGame(_cfg(ROOT / "configs" / "ste_l011" / "tag_10m.toml"), 1, 4, 3, 3, "cpu", 110000)
    old.reset()
    assert "landing" not in old.step({"guard": zero, "strike": zero}).info                # landing off: today's info


def _play(path: Path, cells, n: int, ticks: int):
    run = {"games_per_cell": n, "device": "cpu", "seed": 110000, "ticks_cap": ticks, "tag_edge_margin_m": 0.01}
    return sweep.play_batch(_cfg(path), "3v3", cells, run, fixed_starts=_t44_starts(n)).per_game


def test_option_b_reaches_the_screens_game():
    """Tag off, still Guards: the safety filter acts on Guard-Strike pairs, so option B must change the games played by
    the screen (the spec's plumbing check P-b on the full run reads the same per-game arrays)."""
    cells = (("guard_parked_centre", "strike_straight"),)
    equal = _play(L2 / "l25_landing_tag_off.toml", cells, 6, 120)
    option_b = _play(L2 / "l25_landing_gy_tag_off.toml", cells, 6, 120)
    assert np.array_equal(equal["start_pos_m"], option_b["start_pos_m"])          # same starts (T44's)
    assert not np.array_equal(equal["closest_3d_m"], option_b["closest_3d_m"])


# ================================================================================================ end to end (CPU)
def _tiny(tmp_path: Path) -> Path:
    """The gate file at test sizes (4 games per cell, short games): a test of the code path, never a result."""
    text = GATES.read_text()
    for old, new in {"games_per_cell = 1000": "games_per_cell = 4",
                     "ticks_cap = 2400                   # = the game": "ticks_cap = 300   # smoke",
                     "\nticks = 100": "\nticks = 3", "cap_check_every_ticks = 100": "cap_check_every_ticks = 2"}.items():
        assert old in text, old
        text = text.replace(old, new)
    text = text.replace("\nticks = 200", "\nticks = 60", 1).replace("\nticks = 200", "\nticks = 3", 1)   # reach fires; still
    text = text.replace("\nticks = 600", "\nticks = 40")                         # stand still; tiny tag
    out = tmp_path / "l25_gates.toml"
    out.write_text(text)
    return out


@pytest.fixture(scope="module")
def tiny_run(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("l25")
    mp = pytest.MonkeyPatch()
    mp.setenv(shared.SHARED_ENV, str(tmp / "shared"))
    mp.setenv(shared.LEGACY_LOGS_ENV, "")
    out = tmp / "run"
    code = screen.main(["--gates", str(_tiny(tmp)), "--run-dir", str(out), "--cap-h", "1", "--no-clips"])
    mp.undo()
    return code, out


def test_the_screen_runs_on_the_cpu_with_every_control_passing(tiny_run):
    code, out = tiny_run
    assert code == EXIT_DONE
    result = json.loads((out / "results.json").read_text())
    assert result["controls_all_pass"], result["controls"]
    assert result["controls"]["ctl_reference_replay"]["status"] == "PASS"
    groups = {g["name"]: g for g in result["groups"]}
    assert {n: len(groups[n]["rows"]) for n in ("landing", "gy", "landing_gy", "ctl_tag_off_landing")} == \
        {"landing": 30, "gy": 30, "landing_gy": 30, "ctl_tag_off_landing": 12}
    assert result["shortlist"]["shortlist"] == ["landing", "gy", "landing_gy"]
    assert len(result["shortlist"]["info_reference"]) == 3
    assert "# L2.5 scripted screen (INFO): results" in (out / "results.md").read_text()
    starts = _t44_starts(4)[0].numpy()
    for batch in ("landing__b00", "ctl_tag_off_landing_gy__b00"):
        assert np.array_equal(np.load(out / "cells" / f"{batch}.npz")["start_pos_m"][:4], starts)   # T44's, loaded
