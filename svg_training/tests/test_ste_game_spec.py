"""STE learning track, task L0.8: the game spec sheet (ste_learning/GAME_SPEC.md) and its settings file
(configs/ste_game.toml, loaded by ste/game_spec.py).

The sheet lists, it does not decide (PLAN.md section 4, row L0.8). These tests check four things:

1. the settings file loads, fails closed (unknown or missing section or key, wrong type), and every value carries one of
   the four status labels with a source;
2. the labels of the pending rulings (P1, P2, P9, P10, P12) are not upgraded without the owner (ste_learning/STANDARDS.md
   sections 1-2);
3. the values taken from NUS's hangar game equal what the hangar code computes from the local files (skipped, and saying
   so, when configs/local/ is not installed);
4. the sheet's table and the settings file agree value for value and label for label, so they cannot drift.
"""
import dataclasses
import hashlib
import math
import re
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from svg_training.ste.game_spec import (
    GAME_FILE, LABELS, SCHEMA, GameSpec, SpecEntry, load_game_spec)
from svg_training.ste.config import Provenance

ROOT = Path(__file__).resolve().parents[1]
SHEET = ROOT / "ste_learning" / "GAME_SPEC.md"
GOOD = GAME_FILE.read_text()


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "ste_game.toml"
    path.write_text(text)
    return path


def changed(tmp_path: Path, old: str, new: str) -> Path:
    """A copy of the committed file with one piece of text replaced (the piece must be there exactly once)."""
    assert GOOD.count(old) == 1, old
    return write(tmp_path, GOOD.replace(old, new))


def line_of(key: str) -> str:
    """The committed file's whole line that sets ``key`` ("section.name"), comment included."""
    section, name = key.split(".")
    current = None
    for line in GOOD.splitlines():
        header = re.match(r"\[(\w+)\]", line)
        if header:
            current = header.group(1)
        elif current == section and re.match(rf"{name}\s*=", line):
            return line
    raise AssertionError(f"{key} not found in {GAME_FILE.name}")


# ------------------------------------------------------------------------------------------------ the committed file
def test_committed_file_loads_with_a_label_and_a_source_on_every_value():
    spec, provenance = load_game_spec()
    assert isinstance(spec, GameSpec) and isinstance(provenance, Provenance)
    assert [entry.key for entry in spec.entries] == list(SCHEMA)                  # every key, in the schema's order
    assert all(entry.status in LABELS for entry in spec.entries)
    assert all(entry.source.strip() for entry in spec.entries)
    assert provenance.settings_sha256 == hashlib.sha256(GAME_FILE.read_bytes()).hexdigest()
    assert GAME_FILE == ROOT / "configs" / "ste_game.toml"
    assert load_game_spec(GAME_FILE) == (spec, provenance)
    assert LABELS == ("FIXED", "MEASURED", "PROPOSED", "OPEN")                    # ../STANDARDS.md, table under the title
    with pytest.raises(KeyError, match="zone.diameter_m"):
        spec.entry("zone.diameter_m")


def test_the_file_covers_every_item_plan_section_4_names():
    """PLAN.md section 4, row L0.8: zone radius and shape, height band, arena, starts, game length, speeds, team sizes, tag
    rule, filter mode."""
    keys = set(SCHEMA)
    for needed in ("zone.radius_m", "zone.shape", "height.band_m", "arena.side_m", "starts.guard_disc_m",
                   "starts.strike_ring_m", "timing.game_s", "speeds.strike_mps", "speeds.strike_to_guard_ratio",
                   "teams.target_sizes", "tag_rule.radius_m", "tag_rule.pairing", "filter.pairs", "filter.share"):
        assert needed in keys, needed


def test_no_tag_section_before_l09():
    """[tag] is task L0.9's off-by-default switch (WORK_BREAKDOWN L0.1 note); the sheet records the proposal as tag_rule."""
    assert "tag" not in tomllib.loads(GOOD)


# ------------------------------------------------------------------------------------------------ fails closed
def test_unknown_section_or_key_raises(tmp_path):
    with pytest.raises(ValueError, match=r"unknown section.*\btag\b"):
        load_game_spec(write(tmp_path, GOOD + "\n[tag]\nenabled = false   # PROPOSED (P1): off\n"))
    with pytest.raises(ValueError, match=r"unknown key.*\[zone\].*diameter_m"):
        load_game_spec(changed(tmp_path, line_of("zone.radius_m"),
                               line_of("zone.radius_m") + "\ndiameter_m = 3.2   # PROPOSED (made up): twice the radius"))


def test_missing_section_or_key_raises(tmp_path):
    with pytest.raises(ValueError, match=r"missing key.*\[zone\].*radius_m"):
        load_game_spec(changed(tmp_path, line_of("zone.radius_m"), "# radius removed"))
    without_filter = GOOD[:GOOD.index("[filter]")]
    with pytest.raises(ValueError, match=r"missing section.*filter"):
        load_game_spec(write(tmp_path, without_filter))
    with pytest.raises(FileNotFoundError):
        load_game_spec(tmp_path / "absent.toml")


def test_a_file_that_cannot_be_read_as_toml_raises_naming_the_file(tmp_path):
    path = write(tmp_path, GOOD.replace("[zone]", "[zone", 1))
    with pytest.raises(ValueError, match=r"not valid TOML") as err:
        load_game_spec(path)
    assert str(path) in str(err.value)


@pytest.mark.parametrize("key, new_value", [
    ("zone.radius_m", "2"),                     # a whole number where a decimal is expected
    ("zone.radius_m", '"1.6"'),
    ("zone.radius_m", "true"),                  # a TOML yes/no is not a number
    ("zone.radius_m", "nan"),                   # not finite
    ("zone.shape", "1.0"),
    ("zone.win_ticks_inside", "1.0"),           # a decimal where a whole number is expected
    ("height.band_m", "[0.5, 2]"),              # every element a decimal
    ("height.band_m", "0.5"),
    ("teams.target_sizes", '["1v1", 2]'),
    ("tag_rule.main_game_has_tag", "0"),
])
def test_wrong_type_raises(tmp_path, key, new_value):
    line = line_of(key)
    code, comment = line.split("#", 1)
    name = code.split("=")[0].strip()
    with pytest.raises(ValueError, match=re.escape(key)):
        load_game_spec(changed(tmp_path, line, f"{name} = {new_value}   #{comment}"))


@pytest.mark.parametrize("comment", [
    "",                                         # no comment
    "   # the zone's radius",                   # a comment without a label
    "   # OPEN",                                # a label without a source
    "   # FIXEDISH (owner): not one of the four labels",
    "   # see PROPOSED (lead) below",           # the label does not lead the comment
    "   # DECIDED (owner): not a label of the settings files",
])
def test_a_value_without_a_label_and_source_raises(tmp_path, comment):
    line = line_of("zone.radius_m")
    with pytest.raises(ValueError, match=r"zone\.radius_m.*label"):
        load_game_spec(changed(tmp_path, line, line.split("#", 1)[0].rstrip() + comment))


def test_one_value_per_line(tmp_path):
    """The labels are read line by line, so a value spread over lines (or a dotted key) is refused, not skipped."""
    line = line_of("height.band_m")
    comment = line.split("#", 1)[1]
    with pytest.raises(ValueError, match=r"one value per line"):
        load_game_spec(changed(tmp_path, line, f"band_m = [   #{comment}\n  0.5, 1.8]"))
    with pytest.raises(ValueError, match=r"one value per line"):
        load_game_spec(changed(tmp_path, "[speeds]\n", "[speeds]\nextra.x = 1.0   # PROPOSED (made up): dotted\n"))


def test_a_hash_inside_a_string_does_not_start_the_comment(tmp_path):
    line = line_of("zone.centre")
    spec, _ = load_game_spec(changed(tmp_path, line, 'centre = "arena#centre"   # PROPOSED (made up): a hash inside'))
    assert spec.value("zone.centre") == "arena#centre" and spec.status("zone.centre") == "PROPOSED"


def test_frozen_and_no_defaults():
    spec, provenance = load_game_spec()
    with pytest.raises(dataclasses.FrozenInstanceError):
        spec.entries = ()
    with pytest.raises(dataclasses.FrozenInstanceError):
        spec.entries[0].value = 0.0
    with pytest.raises(TypeError):
        spec.entries[0] = spec.entries[1]
    assert isinstance(spec.value("height.band_m"), tuple)                         # lists load as tuples
    assert hash(spec) == hash(load_game_spec()[0])                               # nothing mutable inside
    for cls in (GameSpec, SpecEntry):
        assert cls.__dataclass_params__.frozen
        assert all(f.default is dataclasses.MISSING and f.default_factory is dataclasses.MISSING
                   for f in dataclasses.fields(cls)), cls


def test_module_imports_on_the_cpu_without_torch_or_isaac():
    code = ("import sys; before = set(sys.modules); import svg_training.ste.game_spec as g; g.load_game_spec(); "
            "new = {m.split('.')[0] for m in set(sys.modules) - before}; "
            "print(sorted(new & {'torch', 'numpy', 'isaaclab', 'isaacsim', 'omni', 'pxr'}))")
    run = subprocess.run([sys.executable, "-B", "-c", code], capture_output=True, text=True,
                         env={"PYTHONPATH": str(ROOT / "source"), "CUDA_VISIBLE_DEVICES": ""})
    assert run.returncode == 0, run.stderr
    assert run.stdout.strip() == "[]"


# ------------------------------------------------------------------------------------------------ labels not upgraded
# ste_learning/STANDARDS.md section 1: "Never upgrade a label without the owner". Section 2 lists the pending rulings.
# A change to any line below needs the owner's ruling, written into DISCUSSION and the parent STANDARDS first.
PINNED_LABELS = {
    "tag_rule.main_game_has_tag": "FIXED",        # parent STANDARDS section 4 "Tag": the main game has no tag (P1 would overturn it)
    "tag_rule.radius_m": "PROPOSED",              # P1
    "tag_rule.pairing": "PROPOSED",               # PLAN section 4 L0.9
    "tag_rule.guard_survives_tag_prob": "PROPOSED",  # D2 provisional; P12 revisits what a tag costs
    "zone.radius_m": "PROPOSED",                  # P12; the parent row "Zone radius" is OPEN
    "teams.target_sizes": "OPEN",                 # P9
    "teams.of_interest": "FIXED",                 # parent STANDARDS section 4
    "arena.environment": "PROPOSED",              # P10
    "arena.side_m": "PROPOSED",                   # F8: PLAN section 4 L0.11 base case
    "speeds.strike_mps": "FIXED",                 # parent STANDARDS section 4
    "speeds.strike_to_guard_ratio": "FIXED",      # parent STANDARDS section 4
    "filter.pairs": "FIXED",                      # parent STANDARDS sections 4 and 5
    "filter.share": "MEASURED",                   # read from cbf_filter.py (lead, 20 Nov 2026: no FIXED without the owner); option B is P2
}


def test_pending_rulings_keep_their_labels():
    spec, _ = load_game_spec()
    found = {key: spec.status(key) for key in PINNED_LABELS}
    assert found == PINNED_LABELS
    assert spec.value("tag_rule.main_game_has_tag") is False


def test_the_sources_name_the_pending_rulings():
    spec, _ = load_game_spec()
    for key, ruling in (("tag_rule.radius_m", "P1"), ("teams.target_sizes", "P9"), ("arena.environment", "P10"),
                        ("zone.radius_m", "P12"), ("tag_rule.guard_survives_tag_prob", "P12"),
                        ("filter.share", "P2"), ("arena.side_m", "F8")):
        assert re.search(rf"\b{ruling}\b", spec.entry(key).source), (key, ruling)


def test_starts_that_do_not_fit_the_arena_are_open():
    """A start ring outside the arena's keep-in limit (half the side less the wall margin) cannot be the track's value."""
    spec, _ = load_game_spec()
    limit_m = spec.value("arena.side_m") / 2 - spec.value("arena.wall_margin_m")
    for key in ("starts.strike_ring_m", "starts.guard_disc_m"):
        if spec.value(key) > limit_m:
            assert spec.status(key) == "OPEN", (key, spec.value(key), limit_m)
    # as committed (20 Nov 2026): the hangar ring does not fit the lab arena; the Guard disc does
    assert spec.value("starts.strike_ring_m") > limit_m >= spec.value("starts.guard_disc_m")


# ------------------------------------------------------------------------------------------------ sources agree
def test_shared_game_values_equal_the_committed_game_files():
    spec, _ = load_game_spec()
    for name in ("s2_game.toml", "nus_hangar_game.toml"):
        game = tomllib.loads((ROOT / "configs" / name).read_text())
        assert spec.value("height.band_m") == tuple(game["arena"]["height_band_m"]), name
        assert spec.value("arena.wall_margin_m") == game["arena"]["wall_margin_m"], name
        assert spec.value("arena.walls") == game["arena"]["walls"], name
        assert spec.value("zone.win_ticks_inside") == game["partner_rules"]["win_steps_in_zone"], name
        assert math.isclose(spec.value("speeds.strike_mps"), game["partner_rules"]["strike_units_per_step"]
                            * game["partner_rules"]["metres_per_unit"] / game["partner_rules"]["seconds_per_step"])
    s2 = tomllib.loads((ROOT / "configs" / "s2_game.toml").read_text())
    assert spec.value("height.start_m") == s2["arena"]["start_height_m"]


def test_hangar_values_equal_the_hangar_geometry():
    """The values taken from NUS's hangar game equal what nus/hangar.py computes from the local files (no NUS number is
    typed in this test)."""
    local = ROOT / "configs" / "local"
    if not all((local / f).exists() for f in ("nus_rules.toml", "nus_deploy.toml", "nus_hangar.toml")):
        pytest.skip("configs/local/ not installed (scripts/nus_install_provisional.sh): the hangar check cannot run "
                    "(a skip is not a pass)")
    from svg_training.core.game_config import load_game_cfg
    from svg_training.nus import deploy as deploy_mod, hangar as hangar_mod, rules as rules_mod
    deploy = deploy_mod.load_deploy()
    rules = deploy_mod.apply_overrides(rules_mod.load_rules(), deploy)
    base, _ = load_game_cfg(hangar_mod.HANGAR_GAME, use_local=False)
    geo = hangar_mod.geometry(rules, deploy, hangar_mod.load_hangar(), base)
    spec, _ = load_game_spec()
    close = lambda key, value: math.isclose(spec.value(key), value, rel_tol=1e-9)  # noqa: E731
    assert close("zone.radius_m", geo.zone_radius_m)
    assert close("starts.guard_disc_m", geo.guard_disc_m)
    assert close("starts.strike_ring_m", geo.ring_m)
    assert close("height.start_m", geo.height_m)
    assert close("timing.game_s", geo.game_seconds)
    assert close("timing.decision_s", deploy.seconds_per_step)
    assert close("speeds.strike_mps", geo.strike_mps)
    assert close("speeds.strike_to_guard_ratio", geo.strike_mps / geo.guard_mps)
    assert close("arena.wall_margin_m", geo.wall_margin_m)
    assert spec.value("teams.base_case") == f"{rules.guard_count}v{rules.strike_count}"
    assert not close("arena.side_m", geo.side_m)    # F8: the track pins the lab arena, not the hangar's side
    assert close("tag_rule.radius_m", geo.zone_radius_m)   # F2: zone radius = proposed tag radius today


# ------------------------------------------------------------------------------------------------ sheet = file
SHEET_COLUMNS = ("Item", "Setting", "Value", "Status", "Source", "Today: hangar game · S2 game")


def sheet_rows(text: str) -> dict[str, tuple[object, str]]:
    """{setting: (value, status)} of every row of the sheet's table. A row is a table line whose 2nd cell is a setting
    in backticks (`section.name`); the 3rd cell is its value in backticks, written as in TOML."""
    header = "| " + " | ".join(SHEET_COLUMNS) + " |"
    assert header in text, f"GAME_SPEC.md: expected the table header line {header!r}"
    rows: dict[str, tuple[object, str]] = {}
    for line in text.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")] if line.startswith("|") else []
        if len(cells) < 2 or not re.fullmatch(r"`\w+\.\w+`", cells[1]):
            continue
        key = cells[1].strip("`")
        assert len(cells) == len(SHEET_COLUMNS), (
            f"GAME_SPEC.md, row {key}: expected {len(SHEET_COLUMNS)} cells {SHEET_COLUMNS}, found {len(cells)}")
        found = re.fullmatch(r"`([^`]+)`", cells[2])
        assert found, f"GAME_SPEC.md, row {key}: expected the value in backticks in the 3rd cell, found {cells[2]!r}"
        try:
            value = tomllib.loads(f"v = {found.group(1)}")["v"]
        except tomllib.TOMLDecodeError as err:
            raise AssertionError(f"GAME_SPEC.md, row {key}: the value {found.group(1)!r} is not a TOML value ({err})")
        assert key not in rows, f"GAME_SPEC.md: setting {key} has two rows"
        rows[key] = (tuple(value) if isinstance(value, list) else value, cells[3])
    return rows


def check_sheet(text: str, spec: GameSpec) -> None:
    """The sheet's table and the settings file hold the same settings, values and labels."""
    rows = sheet_rows(text)
    file_keys = [entry.key for entry in spec.entries]
    only_sheet, only_file = sorted(set(rows) - set(file_keys)), [k for k in file_keys if k not in rows]
    assert not only_sheet and not only_file, (
        f"GAME_SPEC.md and {GAME_FILE.name} list different settings: only in the sheet {only_sheet}, only in the "
        f"file {only_file}")
    values = {key: {"sheet": rows[key][0], "file": spec.value(key)} for key in file_keys
              if rows[key][0] != spec.value(key) or type(rows[key][0]) is not type(spec.value(key))}
    assert not values, f"GAME_SPEC.md and {GAME_FILE.name}: these values differ: {values}"
    labels = {key: {"sheet": rows[key][1], "file": spec.status(key)} for key in file_keys
              if rows[key][1] != spec.status(key)}
    assert not labels, f"GAME_SPEC.md and {GAME_FILE.name}: these status labels differ: {labels}"


def made_up_sheet(spec: GameSpec) -> str:
    """A sheet with the committed file's settings, values and labels, in the sheet's table layout."""
    def toml_value(value):
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, str):
            return f'"{value}"'
        if isinstance(value, tuple):
            return "[" + ", ".join(toml_value(v) for v in value) + "]"
        return repr(value)
    rows = [f"| an item | `{e.key}` | `{toml_value(e.value)}` | {e.status} | a source | — |" for e in spec.entries]
    return "\n".join(["# Game spec", "", "| " + " | ".join(SHEET_COLUMNS) + " |",
                      "|" + "---|" * len(SHEET_COLUMNS), *rows, ""])


def test_the_sheet_and_the_settings_file_agree():
    check_sheet(SHEET.read_text(), load_game_spec()[0])


def test_the_sheet_check_refuses_a_sheet_that_differs_and_says_where():
    spec, _ = load_game_spec()
    good = made_up_sheet(spec)
    check_sheet(good, spec)

    def refused(match, text):
        with pytest.raises(AssertionError, match=match):
            check_sheet(text, spec)

    radius = next(line for line in good.splitlines() if "`zone.radius_m`" in line)
    refused(r"values differ: \{'zone\.radius_m': \{'sheet': 2\.4",
            good.replace(radius, radius.replace(f"`{spec.value('zone.radius_m')!r}`", "`2.4`")))
    refused(r"status labels differ: \{'zone\.radius_m': \{'sheet': 'FIXED', 'file': 'PROPOSED'\}",
            good.replace(radius, radius.replace("| PROPOSED |", "| FIXED |")))
    refused(r"only in the file \['zone\.radius_m'\]", good.replace(radius + "\n", ""))
    refused(r"only in the sheet \['zone\.diameter_m'\]",
            good.replace(radius, radius + "\n| an item | `zone.diameter_m` | `3.2` | PROPOSED | a source | — |"))
    refused(r"setting zone\.radius_m has two rows", good.replace(radius, radius + "\n" + radius))
    refused(r"row zone\.radius_m: expected the value in backticks", good.replace(radius, radius.replace(f"`{spec.value('zone.radius_m')!r}`", f"{spec.value('zone.radius_m')!r}")))
    refused(r"row zone\.radius_m: expected 6 cells", good.replace(radius, radius.replace(" a source | — |", " — |")))
    refused(r"expected the table header line", good.replace("| Status |", "| Label |"))
    ring = next(line for line in good.splitlines() if "`starts.strike_ring_m`" in line)
    refused(r"values differ: \{'starts\.strike_ring_m'", good.replace(ring, ring.replace(
        f"`{spec.value('starts.strike_ring_m')!r}`", "`3`")))                                # 3 is not 3.0


def test_the_sheet_is_internal_and_names_the_open_rulings():
    text = SHEET.read_text()
    assert text.startswith("INTERNAL · ")
    for ruling in ("P1", "P2", "P9", "P10", "P12", "F8", "D2"):
        assert re.search(rf"\b{ruling}\b", text), ruling
