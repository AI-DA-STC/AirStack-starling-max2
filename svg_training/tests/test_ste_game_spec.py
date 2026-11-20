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


def test_the_tag_section_lists_the_games_switch_and_its_defaults():
    """Task L0.9 changed this test on purpose: until L0.8 it asserted that no [tag] section exists. [tag] now lists the
    game's own switch for the study tag (core/game_config.py TagCfg, read from a game file's [tag]): the same keys, the
    code's defaults as values, off, and the proposal's radius, probability and pairing (tag_rule)."""
    from svg_training.core.game_config import TAG_MODES, TagCfg
    spec, _ = load_game_spec()
    table = tomllib.loads(GOOD)["tag"]
    assert list(table) == [f.name for f in dataclasses.fields(TagCfg)]
    assert TagCfg(**table) == TagCfg()                                            # the sheet holds the code's defaults
    assert spec.value("tag.mode") == TAG_MODES[0] == "off" and spec.value("tag_rule.main_game_has_tag") is False
    assert spec.value("tag.radius_m") == spec.value("tag_rule.radius_m")
    assert spec.value("tag.guard_survives_tag_prob") == spec.value("tag_rule.guard_survives_tag_prob")
    assert spec.value("tag_rule.pairing") in TAG_MODES[1:]                        # the pairing the switch turns on


# ------------------------------------------------------------------------------------------------ fails closed
def test_unknown_section_or_key_raises(tmp_path):
    with pytest.raises(ValueError, match=r"unknown section.*\blanding\b"):
        load_game_spec(write(tmp_path, GOOD + "\n[landing]\nland_speed_mps = 0.6   # PROPOSED (made up): L2.3\n"))
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
    "   # FIXED (): an empty source",
    "   # FIXED ( ): a source of blanks",
    "   # FIXED (OPEN) PROPOSED (P12): two labels",
    "   # PROPOSED (OPEN): a label in place of the source",
    "   # PROPOSED: P12; also OPEN (P12)",
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
# Every setting's label is pinned here. A change to any line needs a dated ruling (the owner's for FIXED rows and pending
# rulings, written into DISCUSSION and the parent STANDARDS first; the lead's for LEAD CALL rows), named in the comment.
PINNED_LABELS = {
    "zone.shape": "FIXED",                        # parent STANDARDS section 4 "Teams"
    "zone.scored_in": "PROPOSED",                 # parent STANDARDS section 4 "Height" (PROPOSED)
    "zone.radius_m": "OPEN",                      # P12, OPEN at G0; the parent row "Zone radius" is OPEN (QC I2, 21 Nov 2026)
    "zone.centre": "PROPOSED",                    # LEAD CALL, 20 Nov 2026
    "zone.win_ticks_inside": "PROPOSED",          # parent STANDARDS section 4 "Strike scores" (PROPOSED)
    "height.band_m": "PROPOSED",                  # parent STANDARDS section 4 "Height" (PROPOSED)
    "height.mode": "PROPOSED",                    # T41's game
    "height.start_m": "PROPOSED",                 # hangar and S2 game files
    "arena.side_m": "PROPOSED",                   # F8: PLAN section 4 L0.11 base case
    "arena.wall_margin_m": "PROPOSED",            # game files
    "arena.walls": "PROPOSED",                    # game files
    "arena.environment": "OPEN",                  # P10, OPEN at G0 (QC I2, 21 Nov 2026)
    "starts.guard_disc_m": "PROPOSED",            # hangar game
    "starts.strike_ring_m": "PROPOSED",           # LEAD CALL 21 Nov 2026, L08-F1 (L0.10): the hangar ring scaled to the 6.5 m arena
    "timing.game_s": "PROPOSED",                  # LEAD CALL, 20 Nov 2026
    "timing.decision_s": "PROPOSED",              # hangar game, T41
    "speeds.strike_mps": "FIXED",                 # parent STANDARDS section 4 "Speeds in metres per second"
    "speeds.strike_to_guard_ratio": "FIXED",      # parent STANDARDS section 4 "Speed ratio"
    "teams.of_interest": "FIXED",                 # parent STANDARDS section 4 "Team sizes of interest"
    "teams.target_sizes": "OPEN",                 # P9
    "teams.base_case": "PROPOSED",                # PLAN section 4 L0.11 base case
    "tag_rule.main_game_has_tag": "FIXED",        # parent STANDARDS section 4 "Tag": the main game has no tag (P1 would overturn it)
    "tag_rule.radius_m": "PROPOSED",              # P1 (PLAN section 2: "P1 and P2 PROPOSED")
    "tag_rule.pairing": "PROPOSED",               # PLAN section 4 L0.9
    "tag_rule.guard_survives_tag_prob": "PROPOSED",  # D2 provisional; P12 revisits what a tag costs (lead's ruling 3, 20 Nov 2026)
    "tag.mode": "FIXED",                          # parent STANDARDS section 4 "Tag": off until the owner rules P1 (L0.9)
    "tag.radius_m": "PROPOSED",                   # P1, as tag_rule.radius_m
    "tag.guard_survives_tag_prob": "PROPOSED",    # D2 provisional, P12, as tag_rule.guard_survives_tag_prob
    "filter.pairs": "FIXED",                      # parent STANDARDS sections 4 and 5
    "filter.share": "MEASURED",                   # read from cbf_filter.py (lead's ruling 4, 20 Nov 2026: no FIXED without the owner)
    "filter.keepout_m": "FIXED",                  # parent STANDARDS section 5 "Safety filter in flight today"
    "players.guard_park_ring_m": "PROPOSED",      # PLAN section 2 F1 (lead's geometry script, 20 Nov 2026), task L0.10
}


def test_pending_rulings_keep_their_labels():
    spec, _ = load_game_spec()
    assert list(PINNED_LABELS) == list(SCHEMA)                                    # every setting is pinned
    found = {key: spec.status(key) for key in PINNED_LABELS}
    assert found == PINNED_LABELS
    assert spec.value("tag_rule.main_game_has_tag") is False


def test_the_sources_name_the_pending_rulings():
    spec, _ = load_game_spec()
    for key, ruling in (("tag_rule.radius_m", "P1"), ("teams.target_sizes", "P9"), ("arena.environment", "P10"),
                        ("zone.radius_m", "P12"), ("tag_rule.guard_survives_tag_prob", "P12"),
                        ("filter.share", "P2"), ("arena.side_m", "F8"), ("tag.mode", "P1"), ("tag.radius_m", "P1"),
                        ("tag.guard_survives_tag_prob", "P12"),
                        ("starts.strike_ring_m", "L08-F1"), ("starts.strike_ring_m", "LEAD CALL"),
                        ("players.guard_park_ring_m", "F1")):
        assert re.search(rf"(?<![\w-]){ruling}(?![\w-])", spec.entry(key).source), (key, ruling)


def test_starts_that_do_not_fit_the_arena_are_open():
    """A start ring outside the arena's keep-in limit (half the side less the wall margin) cannot be the track's value."""
    spec, _ = load_game_spec()
    limit_m = spec.value("arena.side_m") / 2 - spec.value("arena.wall_margin_m")
    for key in ("starts.strike_ring_m", "starts.guard_disc_m"):
        if spec.value(key) > limit_m:
            assert spec.status(key) == "OPEN", (key, spec.value(key), limit_m)
    # L0.10 (LEAD CALL 21 Nov 2026, closes L08-F1): the ring fits the lab arena on every bearing (the hangar's 3.2 m did
    # not); it stays outside the zone, and every Strike start is farther than the proposed tag radius from the Guard disc
    ring_m, disc_m = spec.value("starts.strike_ring_m"), spec.value("starts.guard_disc_m")
    assert limit_m >= ring_m > spec.value("zone.radius_m") > disc_m
    assert ring_m - disc_m > spec.value("tag.radius_m") > spec.value("filter.keepout_m")


def test_the_game_defaults_equal_the_sheet():
    """The game's own start setting (core/game_config.py StartsCfg, mode "zone_disc_ring", task L0.10) and the parked-ring
    Guard (opponents/scripted.py) take their defaults from the sheet's values; this test keeps them equal."""
    from svg_training.core.game_config import StartsCfg
    from svg_training.opponents.scripted import GuardParkedRing
    spec, _ = load_game_spec()
    assert StartsCfg().strike_ring_m == spec.value("starts.strike_ring_m")
    assert StartsCfg().guard_disc_m == spec.value("starts.guard_disc_m")
    assert StartsCfg().mode == "rings"                                            # off by default: today's starts
    assert GuardParkedRing.RING_M == spec.value("players.guard_park_ring_m")


# ------------------------------------------------------------------------------------------------ sources agree
def test_shared_game_values_equal_the_committed_game_files():
    spec, _ = load_game_spec()
    for name in ("s2_game.toml", "nus_hangar_game.toml"):
        game = tomllib.loads((ROOT / "configs" / name).read_text())
        assert spec.value("height.band_m") == tuple(game["arena"]["height_band_m"]), name
        assert spec.value("arena.wall_margin_m") == game["arena"]["wall_margin_m"], name
        assert spec.value("arena.walls") == game["arena"]["walls"], name
        assert spec.value("zone.win_ticks_inside") == game["partner_rules"]["win_steps_in_zone"], name
    s2 = tomllib.loads((ROOT / "configs" / "s2_game.toml").read_text())
    assert spec.value("height.start_m") == s2["arena"]["start_height_m"]
    # speeds from S2's units (nus_hangar_game.toml carries neutral placeholders that hangar_cfg overrides, QC m5)
    rules = s2["partner_rules"]
    assert math.isclose(spec.value("speeds.strike_mps"),
                        rules["strike_units_per_step"] * rules["metres_per_unit"] / rules["seconds_per_step"])
    assert math.isclose(spec.value("speeds.strike_to_guard_ratio"),
                        rules["strike_units_per_step"] / rules["guard_units_per_step"])


PARENT = ROOT / "STANDARDS.md"
FENCE_FILE = ROOT.parent / "AirStack" / "robot" / "ros_ws" / "src" / "svg_ground_control" / "config" / "goal_two_ours.yaml"
FILTER_PARAMS = ROOT / "params" / "real_exploratory_v0.toml"


def parent_row(name: str) -> tuple[str, str]:
    """(value cell, status cell) of the row named ``name`` in the parent STANDARDS.md tables (first cell = name)."""
    for line in PARENT.read_text().splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")] if line.startswith("|") else []
        if len(cells) >= 3 and cells[0] == name:
            return cells[1], cells[2]
    raise AssertionError(f"../STANDARDS.md: no table row named {name!r}")


def test_fixed_values_follow_their_parent_rows():
    """Each FIXED value is computed from, or matched against, the parent STANDARDS row it cites; that row is FIXED too."""
    spec, _ = load_game_spec()
    # zone shape: "the Guard team holds a circular zone"
    teams, label = parent_row("Teams")
    assert label == "FIXED" and spec.value("zone.shape") == "circle" and "circular zone" in teams
    # team sizes of interest: "2 Guard against 1 Strike; 5 Guard against 3 Strike"
    sizes, label = parent_row("Team sizes of interest")
    assert label == "FIXED"
    assert spec.value("teams.of_interest") == tuple(f"{g}v{s}" for g, s in re.findall(r"(\d+) Guard against (\d+) Strike", sizes))
    assert set(spec.value("teams.of_interest")) <= set(spec.value("teams.target_sizes"))
    # speeds: "Strike 0.5 m/s, Guard 0.33 m/s"; ratio "1.5 times as fast"
    speeds, label = parent_row("Speeds in metres per second")
    assert label == "FIXED" and re.search(rf"Strike {spec.value('speeds.strike_mps')!r} m/s", speeds)
    ratio, label = parent_row("Speed ratio")
    assert label == "FIXED" and re.search(rf"\b{spec.value('speeds.strike_to_guard_ratio')!r} times as fast", ratio)
    # main game has no tag
    tag, label = parent_row("Tag")
    assert label == "FIXED" and spec.value("tag_rule.main_game_has_tag") is False and "The main game has no tag" in tag
    assert spec.value("tag.mode") == "off"                                        # the game's switch follows it (L0.9)
    # filter on every pair, in the game (section 4) and in flight (section 5)
    in_game, label_game = parent_row("Safety filter in the game")
    in_flight, label_flight = parent_row("Safety filter in flight today")
    assert label_game == label_flight == "FIXED" and spec.value("filter.pairs") == "every_pair"
    assert "every pair" in in_game and "every pair of drones" in in_flight
    # filter distance = 2 x the safety radius of the drone parameter set, and the parent row states both
    radius_m = tomllib.loads(FILTER_PARAMS.read_text())["filter"]["safety_radius_m"]
    assert math.isclose(spec.value("filter.keepout_m"), 2 * radius_m)
    assert f"keep-out radius {radius_m!r} m" in in_flight and f"({2 * radius_m:.2f} m centre to centre)" in in_flight
    s2 = tomllib.loads((ROOT / "configs" / "s2_game.toml").read_text())["partner_rules"]
    assert spec.value("filter.keepout_m") == s2["keepout_guard_m"] == s2["keepout_strike_m"]


def yaml_triple(text: str, key: str) -> tuple[float, float, float]:
    found = re.search(rf"^\s*{key}:\s*\[([^\]]+)\]", text, re.MULTILINE)
    assert found, f"{FENCE_FILE.name}: no line '{key}: [x, y, z]'"
    return tuple(float(v) for v in found.group(1).split(","))


def test_proposed_values_follow_the_files_they_cite():
    """The literals and the arena side, against what their sources say (read only)."""
    spec, _ = load_game_spec()
    # arena side: the lab fence, a square, as PLAN's L0.11 base case says
    text = FENCE_FILE.read_text()
    low, high = yaml_triple(text, "fence_min"), yaml_triple(text, "fence_max")
    assert high[0] - low[0] == high[1] - low[1] == spec.value("arena.side_m")
    assert f"the {spec.value('arena.side_m')!r} m lab arena" in (ROOT / "ste_learning" / "PLAN.md").read_text()
    assert re.search(r"^\s*fence_behavior:\s*\"keep_in\"", text, re.MULTILINE) and spec.value("arena.walls") == "keep_in"
    # height band: the lab's goal box heights
    assert (yaml_triple(text, "arena_low")[2], yaml_triple(text, "arena_high")[2]) == spec.value("height.band_m")
    # environment: E0 of the parent's environment ladder, the first build step
    ladder, _ = parent_row("Environment ladder")
    assert spec.value("arena.environment") == "open_arena" and ladder.startswith("E0 open arena")
    # height: free in the band, as in T41's game (Phase 4 row 5)
    rows = {row["id"]: row for row in tomllib.loads((ROOT / "configs" / "nus_phase4.toml").read_text())["row"]}
    assert spec.value("height.mode") == "free" and rows["5"]["height"].split("_")[0] == spec.value("height.mode")
    # zone counted in the horizontal plane: the zone test reads x and y only
    assert spec.value("zone.scored_in") == "horizontal_plane"
    assert "d = (pos[..., :2] - self.arenas.zone_centre_m[:, None, :]).norm(dim=-1)" in (
        ROOT / "source" / "svg_training" / "core" / "game.py").read_text()
    # zone at the arena centre in the hangar game
    draw = (ROOT / "source" / "svg_training" / "nus" / "hangar_game.py").read_text()
    assert spec.value("zone.centre") == "arena_centre" and "torch.zeros(n, 2, device=dev), full(geo.zone_radius_m)" in draw
    # base case and tag radius: PLAN's L0.11 base case
    plan = (ROOT / "ste_learning" / "PLAN.md").read_text()
    assert f"Base case: {spec.value('teams.base_case')}, tag radius {spec.value('tag_rule.radius_m')!r} m, zone radius " \
           f"{spec.value('zone.radius_m')!r} m" in plan


RING_STEP_M = 0.05     # the lead's rounding step for the lab ring (LEAD CALL 21 Nov 2026, L08-F1)


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
    # L0.10 (LEAD CALL 21 Nov 2026, L08-F1): the hangar ring scaled by the arena half-side, rounded down to 5 cm
    scaled_m = geo.ring_m * (spec.value("arena.side_m") / 2) / (geo.side_m / 2)
    assert close("starts.strike_ring_m", math.floor(scaled_m / RING_STEP_M + 1e-9) * RING_STEP_M)
    assert spec.value("starts.strike_ring_m") < geo.ring_m
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
    refused(rf"status labels differ: \{{'zone\.radius_m': \{{'sheet': 'FIXED', 'file': '{spec.status('zone.radius_m')}'\}}",
            good.replace(radius, radius.replace(f"| {spec.status('zone.radius_m')} |", "| FIXED |")))
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
    for ruling in ("P1", "P2", "P9", "P10", "P12", "F8", "D2", "L08-F1"):
        assert re.search(rf"(?<![\w-]){ruling}(?![\w-])", text), ruling
    open_items = text[text.index("## Open items"):]
    assert re.search(r"^\| L08-F1 \|", open_items, re.MULTILINE), "the start-ring finding is filed as L08-F1"
    assert re.search(r"^\| L08-F1 \|.*\bClosed\b.*LEAD CALL 21 Nov 2026", open_items, re.MULTILINE), "L0.10 closed it"
    assert not re.search(r"^\| F8 \|", open_items, re.MULTILINE), "F8 is PLAN's arena finding; the ring is L08-F1"
