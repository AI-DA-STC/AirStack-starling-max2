"""Route 3, stage LS1, task LS1-M2-T1: the distillation gate file ``configs/ste_ls1/distil_gates.toml`` and its loader
(``ste/distil.py`` ``load_distil_gates``, ``unfilled_limits``; plan ste_learning/drafts/LS1_TASK_PLAN.md).

* The committed file loads; its pins (skills gate file, cells.toml, the scripts, the game file) hold today.
* Every key of every section is required and no unknown key or section is accepted (a ``tmp_path`` copy written from the
  parsed file, one key removed or one added; the unchanged copy loads, so a refusal is the loader's, not the writer's).
* The owner's keys (``[limits]``, the owner's ``[controls]`` keys) are a ``FILL_`` string or a number;
  ``unfilled_limits`` lists exactly the ``FILL_`` ones; ``end_time_max_ticks`` is required whatever
  ``end_time_gated`` says.
* The near-miss controls: one switch value per moved player, each side's switch players fly in a ``near_miss_cells``
  entry, every entry is a fixed cell or a cells.toml combination against a gated script of the other team.
* The read's alpha and method are the built ones (alpha read from calibration.toml), one ruler (no game count per cell),
  the data-mix rules, new seeds, the smoke on the CPU and inside the schedule, the stop rules of R47.
* The helpers moved out of the calibration script (``perturbed.SWITCHES``; ``cells.load_cells``, ``check_cells``,
  ``side_cells``, ``gated_m``) are the ones the script uses.

Synthetic owner values come from ``_ste_ls1.STAND_IN`` (constraint 5): no limit is typed here. CPU only, no play."""
import copy
import hashlib
import inspect
import json
import math
import sys
import tomllib
from pathlib import Path

import pytest

from svg_training.opponents import perturbed
from svg_training.opponents.scripted import REGISTRY
from svg_training.ste import cells, distil, exploit, skills

import _ste_ls1 as h
from _ste_tools import SCRIPTS
from test_ste_l1side import _seeds

sys.path.insert(0, str(SCRIPTS))
import ste_ls1_calibration as cal  # noqa: E402

ROOT = exploit.ROOT
GATES = ROOT / "configs" / "ste_ls1" / "distil_gates.toml"
CALIBRATION = ROOT / "configs" / "ste_ls1" / "calibration.toml"
SCRIPTED = ROOT / "source" / "svg_training" / "opponents" / "scripted.py"
SIDES = ("guard", "strike")


# ================================================================================================ helpers
def _value(v) -> str:
    """A TOML value: strings as JSON strings (the escapes agree), dicts as inline tables, lists element by element."""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, str):
        return json.dumps(v)
    if isinstance(v, dict):
        return "{ " + ", ".join(f"{k} = {_value(x)}" for k, x in v.items()) + " }"
    if isinstance(v, list):
        return "[" + ", ".join(_value(x) for x in v) + "]"
    if isinstance(v, float) and math.isnan(v):
        return "nan"
    return repr(v)


def toml_text(data: dict) -> str:
    """A gate file's text from its parsed dict: one ``[section]`` per top-level table, nested tables inline."""
    out = []
    for section, table in data.items():
        out.append(f"[{section}]")
        out += [f"{k} = {_value(v)}" for k, v in table.items()]
        out.append("")
    return "\n".join(out)


def committed() -> dict:
    return tomllib.loads(GATES.read_text())


def write(tmp_path: Path, data: dict, name: str = "distil_gates.toml") -> Path:
    path = tmp_path / name
    path.write_text(toml_text(data))
    return path


def filled(data: dict | None = None) -> dict:
    """The committed file's dict with the owner's keys filled from ``STAND_IN`` (synthetic, constraint 5)."""
    data = copy.deepcopy(data if data is not None else committed())
    data["limits"] = dict(h.STAND_IN["limits"])
    data["controls"] = copy.deepcopy(h.STAND_IN["controls"])
    return data


def key_paths(table: dict, prefix: tuple = ()) -> list[tuple]:
    """Every key path of a section that the loader requires: the keys, and inside the nested owner and read tables
    (``near_miss``, its ``switch``, ``near_miss_cells``, ``codes``) their keys too."""
    out = []
    for k, v in table.items():
        out.append(prefix + (k,))
        if isinstance(v, dict):
            out += key_paths(v, prefix + (k,))
    return out


def _drop(data: dict, path: tuple) -> dict:
    data = copy.deepcopy(data)
    node = data
    for k in path[:-1]:
        node = node[k]
    del node[path[-1]]
    return data


def _set(data: dict, path: tuple, value) -> dict:
    data = copy.deepcopy(data)
    node = data
    for k in path[:-1]:
        node = node[k]
    node[path[-1]] = value
    return data


# ================================================================================================ the committed file
def test_the_committed_file_loads_and_its_pins_hold():
    g = distil.load_distil_gates(GATES)
    assert g.sha256 == hashlib.sha256(GATES.read_bytes()).hexdigest() and g.path == str(GATES)
    src = g.source
    assert src["skills_gates_sha256"] == exploit.sha256_file(ROOT / src["skills_gates"])
    assert src["cells_sha256"] == exploit.sha256_file(ROOT / src["cells"])
    assert src["scripted_sha256"] == exploit.sha256_file(SCRIPTED)
    assert src["game_sha256"] == exploit.sha256_file(ROOT / src["game_file"])
    skills_gates = exploit.load_gates(ROOT / src["skills_gates"])
    base = skills_gates.games[skills_gates.variants[distil.VARIANT]["game"]]
    assert (src["game_file"], src["game_sha256"]) == (base.file, base.sha256)
    for side in SIDES:                        # the CellSpec is the pinned skills gate file's
        assert g.specs[side] == cells.cell_spec(skills_gates, side)
    assert g.skills_gates.sha256 == src["skills_gates_sha256"] and g.cells == cells.load_cells(ROOT / src["cells"])


def test_the_round_trip_copy_loads(tmp_path):
    """The writer the key tests use gives a file the loader accepts (so their refusals are the loader's)."""
    for data in (committed(), filled()):
        g = distil.load_distil_gates(write(tmp_path, data))
        assert {k: getattr(g, k) for k in distil.SECTIONS} == data


def test_every_key_is_required(tmp_path):
    data = committed()
    assert set(data) == set(distil.SECTIONS)
    for section, table in data.items():
        assert set(table) == set(distil.SECTIONS[section]), section
        with pytest.raises(ValueError, match=section):
            distil.load_distil_gates(write(tmp_path, _drop(data, (section,))))
        for path in key_paths(table):
            with pytest.raises(ValueError, match=path[-1]):
                distil.load_distil_gates(write(tmp_path, _drop(data, (section,) + path)))


def test_an_unknown_key_or_section_is_refused(tmp_path):
    data = committed()
    with pytest.raises(ValueError, match="extra_section"):
        distil.load_distil_gates(write(tmp_path, {**data, "extra_section": {"a": 1}}))
    for section, table in data.items():
        for path in [()] + [p for p in key_paths(table) if isinstance(_get(table, p), dict)]:
            with pytest.raises(ValueError, match="surplus_key"):
                distil.load_distil_gates(write(tmp_path, _set(data, (section,) + path + ("surplus_key",), "x")))


def _get(table: dict, path: tuple):
    for k in path:
        table = table[k]
    return table


# ================================================================================================ the owner's keys
def test_limits_are_numbers_or_fill(tmp_path):
    data = committed()
    g = distil.load_distil_gates(GATES)
    fill = [k for k in distil.LIMIT_KEYS if str(g.limits[k]).startswith(exploit.FILL_MARK)]
    fill += [k for k in distil.CONTROL_SIZE_KEYS if str(_get(g.controls, tuple(k.split(".")))).startswith(
        exploit.FILL_MARK)]
    names = [("limits." if k in distil.LIMIT_KEYS else "controls.") + k for k in fill]
    assert distil.unfilled_limits(g) == names
    assert set(distil.LIMIT_KEYS) == set(data["limits"])
    # filled from STAND_IN: nothing unfilled
    assert distil.unfilled_limits(distil.load_distil_gates(write(tmp_path, filled(data)))) == []
    # each owner key alone FILL_: listed by name, the rest filled
    full = filled(data)
    for k in distil.LIMIT_KEYS:
        one = _set(full, ("limits", k), exploit.FILL_MARK + "OWNER")
        assert distil.unfilled_limits(distil.load_distil_gates(write(tmp_path, one))) == [f"limits.{k}"]
    for k in distil.CONTROL_SIZE_KEYS:
        one = _set(full, ("controls",) + tuple(k.split(".")), exploit.FILL_MARK + "OWNER")
        assert distil.unfilled_limits(distil.load_distil_gates(write(tmp_path, one))) == [f"controls.{k}"]
    # numbers: finite and > 0; bool refused except end_time_gated, which takes a bool or FILL_ only
    for k in distil.LIMIT_KEYS:
        bad = [0, -abs(h.STAND_IN["limits"]["cmd_rmse_max"]), float("nan"), "other text"]
        bad += [1.5] if k == "end_time_gated" else [True]
        for v in bad:
            with pytest.raises(ValueError, match=k):
                distil.load_distil_gates(write(tmp_path, _set(full, ("limits", k), v)))
    for v in (True, False):
        distil.load_distil_gates(write(tmp_path, _set(full, ("limits", "end_time_gated"), v)))
    for k in distil.CONTROL_SIZE_KEYS:
        for v in (0, -h.STAND_IN["controls"]["near_miss"]["bias"], True, float("nan"), "other text"):
            with pytest.raises(ValueError, match=k.split(".")[-1]):
                distil.load_distil_gates(write(tmp_path, _set(full, ("controls",) + tuple(k.split(".")), v)))
    for k in ("permuted_min_miss_cells", "unfitted_min_miss_cells"):      # cell counts: whole numbers
        with pytest.raises(ValueError, match=k):
            distil.load_distil_gates(write(tmp_path, _set(full, ("controls", k), h.STAND_IN["controls"]["near_miss"][
                "bias"])))


def test_end_time_max_ticks_is_required_whatever_end_time_gated_says(tmp_path):
    """The rule (design check, R38): end_time_max_ticks is a number or FILL_ even when end_time_gated is false, so no
    FILL_ survives into a run of record and nothing is typed."""
    full = filled()
    off = _set(full, ("limits", "end_time_gated"), False)
    assert distil.load_distil_gates(write(tmp_path, off)).limits["end_time_gated"] is False
    with pytest.raises(ValueError, match="end_time_max_ticks"):
        distil.load_distil_gates(write(tmp_path, _drop(off, ("limits", "end_time_max_ticks"))))
    unfilled = _set(off, ("limits", "end_time_max_ticks"), exploit.FILL_MARK + "OWNER")
    assert distil.unfilled_limits(distil.load_distil_gates(write(tmp_path, unfilled))) == ["limits.end_time_max_ticks"]


def test_the_near_miss_switch_names_one_value_per_moved_player():
    g = distil.load_distil_gates(GATES)
    switch = g.controls["near_miss"]["switch"]
    assert set(switch) == set(perturbed.SWITCHES) and len(switch) == len(set(perturbed.SWITCHES))
    assert [k for k in distil.CONTROL_SIZE_KEYS if k.startswith("near_miss.switch.")] == \
        [f"near_miss.switch.{k}" for k in perturbed.SWITCHES]
    for key, (team, code, moved, keyword) in perturbed.SWITCHES.items():
        assert code in g.specs[team].players, key                      # a player of that side's [players]
        assert issubclass(moved, REGISTRY[code]), key                  # the moved copy of that very script
        assert inspect.signature(moved).parameters[keyword].kind is inspect.Parameter.KEYWORD_ONLY, key


def test_the_read_alpha_and_method_are_the_built_ones():
    g = distil.load_distil_gates(GATES)
    assert 0 < g.read["alpha"] < 1
    assert g.read["interval"] == cells.NEWCOMBE and g.read["correction"] == cells.BONFERRONI
    assert g.read["alpha"] == tomllib.loads(CALIBRATION.read_text())["intervals"]["alpha"]


def test_the_read_method_accepts_only_the_built_strings(tmp_path):
    data = committed()
    for key in ("interval", "correction"):
        with pytest.raises(ValueError, match=key):
            distil.load_distil_gates(write(tmp_path, _set(data, ("read", key), "holm")))
    for v in (0, 1, -data["read"]["alpha"], True, "0.05"):
        with pytest.raises(ValueError, match="alpha"):
            distil.load_distil_gates(write(tmp_path, _set(data, ("read", "alpha"), v)))


# ================================================================================================ the near-miss cells
def _flies(entry: dict) -> set:
    return set(entry["codes"])


def test_every_near_miss_arm_has_a_cell(tmp_path):
    g = distil.load_distil_gates(GATES)
    for key, (team, code, _, _) in perturbed.SWITCHES.items():
        assert any(code in _flies(e) for e in g.read["near_miss_cells"][team]), key
    data = committed()
    strike = data["read"]["near_miss_cells"]["strike"]
    no_flank = [e for e in strike if "strike_flank" not in _flies(e)]
    assert no_flank and len(no_flank) < len(strike)
    with pytest.raises(ValueError, match="flank_margin_m"):
        distil.load_distil_gates(write(tmp_path, _set(data, ("read", "near_miss_cells", "strike"), no_flank)))
    for side in SIDES:                          # an empty list: the bias, turn and noise arms have no cell either
        with pytest.raises(ValueError, match="rotate_deg"):
            distil.load_distil_gates(write(tmp_path, _set(data, ("read", "near_miss_cells", side), [])))


def test_a_near_miss_cell_is_a_gated_cell_of_its_side(tmp_path):
    data = committed()
    g = distil.load_distil_gates(GATES)
    for side in SIDES:
        entries = data["read"]["near_miss_cells"][side]
        spec = g.specs[side]
        combos = {tuple(c) for c in g.cells["mixed"][side]}
        gated = skills.team_skills(g.skills_gates.players, cells.other(side))
        for e in entries:                       # committed: one code of the side, or a cells.toml combination
            assert (len(e["codes"]) == 1 and e["codes"][0] in spec.players) or tuple(e["codes"]) in combos
            assert e["opponent"] in gated
        first = entries[0]
        wrong = [
            {**first, "codes": [cells.mixed_pool(spec)[0][0]] * (spec.drones - 1)},          # neither form
            {**first, "codes": list(next(c for c in cells.mixed_pool(spec) if c not in combos))},  # not in cells.toml
            {**first, "codes": [g.specs[cells.other(side)].players[0]]},                    # the other team's code
            {**first, "opponent": spec.players[0]},                                          # not the other team
            {**first, "opponent": "guard_mark_inside" if side == "strike" else "no_such_script"},  # info / unknown
            {"codes": first["codes"]},                                                       # a key missing
        ]
        for bad in wrong:
            with pytest.raises(ValueError, match="near_miss_cells"):
                distil.load_distil_gates(write(tmp_path, _set(data, ("read", "near_miss_cells", side),
                                                              entries + [bad])))
        with pytest.raises(ValueError, match="repeated"):
            distil.load_distil_gates(write(tmp_path, _set(data, ("read", "near_miss_cells", side), entries + [first])))


# ================================================================================================ data, seeds, smoke
def test_the_mix_rules(tmp_path):
    g = distil.load_distil_gates(GATES)
    d = g.data
    assert d["uniform_share"] >= d["mix_share"] + d["random_share"]
    assert math.isclose(d["uniform_share"] + d["mix_share"] + d["random_share"], 1.0)
    assert g.dagger["script_share"][0] == 1.0
    assert d["hold"] == g.skills_gates.trainer["decision_ticks"]
    data = committed()
    with pytest.raises(ValueError, match="share"):
        distil.load_distil_gates(write(tmp_path, _set(data, ("data", "mix_share"), d["mix_share"] + d["random_share"])))
    with pytest.raises(ValueError, match="script_share"):
        distil.load_distil_gates(write(tmp_path, _set(data, ("dagger", "script_share"), g.dagger["script_share"][1:])))
    with pytest.raises(ValueError, match="hold"):
        distil.load_distil_gates(write(tmp_path, _set(data, ("data", "hold"), d["hold"] + 1)))


def test_the_seeds_are_new():
    g = distil.load_distil_gates(GATES)
    mine = [g.data["seed"], g.data["pool_seed"], g.fit["seed"], g.report["seed"], g.clips["seed"]]
    assert len(set(mine)) == len(mine) and all(isinstance(s, int) and not isinstance(s, bool) for s in mine)
    assert _seeds(GATES.read_text()) == set(mine)          # the regex of the other tests sees exactly these
    used = set()
    for path in (ROOT / "configs").glob("ste_*/*.toml"):
        if path != GATES:
            used |= _seeds(path.read_text())
    t44_seed = int(exploit.load_reference(ROOT / g.skills_gates.reference["file"]).meta["seed"])   # the read's starts
    pool_seed = int(g.skills_gates.pool["seed"])                                               # the skills route's pool
    assert not set(mine) & (used | {t44_seed, pool_seed})


def test_the_smoke_device_is_the_cpu():
    assert distil.load_distil_gates(GATES).smoke["device"] == "cpu"


def test_the_smoke_fits_the_schedule(tmp_path):
    """The smoke rule (design check): ``[smoke] rounds`` are the first entries of ``[dagger] script_share``."""
    data = committed()
    g = distil.load_distil_gates(GATES)
    assert 1 <= g.smoke["rounds"] <= len(g.dagger["script_share"])
    assert "rounds" in distil.SMOKE_RULE and "min(keep_rows" in distil.SMOKE_RULE
    with pytest.raises(ValueError, match="rounds"):
        distil.load_distil_gates(write(tmp_path, _set(data, ("smoke", "rounds"), len(g.dagger["script_share"]) + 1)))


def test_one_ruler():
    """B-6: neither file holds a game count per cell (cells.toml [read] games_per_cell is the one), [read] has no
    control_games, and both pin the same cells.toml."""
    dist, calib = committed(), tomllib.loads(CALIBRATION.read_text())

    def keys(t):
        return {k for k, v in t.items()} | {x for v in t.values() if isinstance(v, dict) for x in keys(v)}
    for data in (dist, calib):
        assert not {"games_per_cell", "control_games"} & keys(data)
    assert "control_games" not in dist["read"]
    assert dist["source"]["cells_sha256"] == calib["source"]["cells_sha256"]
    assert dist["source"]["cells"] == calib["source"]["cells"]


def test_the_clip_codes_are_codes_of_their_side(tmp_path):
    data = committed()
    g = distil.load_distil_gates(GATES)
    for side in SIDES:
        assert g.clips["codes"][side] and set(g.clips["codes"][side]) <= set(g.specs[side].players)
        with pytest.raises(ValueError, match="codes"):
            distil.load_distil_gates(write(tmp_path, _set(data, ("clips", "codes", side),
                                                          [g.specs[cells.other(side)].players[0]])))


# ================================================================================================ the stop rules
def test_the_stop_rules_are_r47s():
    g = distil.load_distil_gates(GATES)
    assert set(g.stop) == set(distil.STOP_KEYS) == {"control_fails", "not_distilled", "fix_round", "one_side_only"}
    assert all(isinstance(v, str) and v.strip() for v in g.stop.values())
    assert "INCONCLUSIVE" in g.stop["control_fails"] and "once" in g.stop["control_fails"]
    assert "no limit is moved" in g.stop["not_distilled"]
    assert "R47" in g.stop["fix_round"] and "inputs" in g.stop["fix_round"]
    assert "R47" in g.stop["one_side_only"] and "DISTILLED on both sides" in g.stop["one_side_only"]
    assert "gate-file variant" not in " ".join(g.stop.values())


# ================================================================================================ the moved helpers
def test_the_calibration_uses_the_moved_helpers():
    """The switch map, the cells.toml reader, the side's cells and m moved out of the calibration script unchanged
    (design check): the script's names are the importable ones, and m is Guard 150, Strike 130 for both reads."""
    assert cal.SWITCHES is perturbed.SWITCHES
    for name in ("load_cells", "check_cells", "side_cells", "gated_m", "gated_opponents", "Cell", "CELLS_KEYS"):
        assert getattr(cal, name) is getattr(cells, name), name
    assert (cal.FIXED, cal.MIXED, cal.INFO) == (cells.FIXED, cells.MIXED, cells.INFO)
    g = distil.load_distil_gates(GATES)
    m = {side: cells.gated_m(g.specs[side], g.cells, g.skills_gates) for side in SIDES}
    assert m == {"guard": 150, "strike": 130}
    for side in SIDES:
        every = cells.side_cells(g.specs[side], g.cells, g.skills_gates)
        assert sum(c.kind != cells.INFO for c in every) == m[side]
