"""Tests of the interface.toml draft for the partner policy (layout id nus_area_denial_v1). Values go only under runs/; the committed
template lists keys. Marker values and a synthetic checkpoint only."""
import tomllib

import pytest

from _nus_markers import FAKE_COMMIT as COMMIT, load_marker_files, write_synthetic_checkpoint
from svg_training.core.observations import INTERFACE_VERSION
from svg_training.nus import deploy as deploy_mod, interface as interface_mod
from svg_training.nus.actor import NusActor

TEAMS = ("guard", "strike")


@pytest.fixture(scope="module")
def parts(tmp_path_factory):
    folder = tmp_path_factory.mktemp("interface")
    rules, deploy, rules_path, deploy_path = load_marker_files(folder)
    actors = {}
    for team in TEAMS:
        checkpoint = write_synthetic_checkpoint(folder / team, team)
        actors[team] = NusActor.load(checkpoint, team=team, rules=rules, deploy=deploy)
    return rules, deploy, actors


def test_template_lists_exactly_the_keys_and_holds_only_the_layout_id_and_placeholders():
    template = tomllib.loads(interface_mod.INTERFACE_TEMPLATE.read_text())
    assert tuple(template) == interface_mod.INTERFACE_KEYS
    assert template["layout_id"] == interface_mod.LAYOUT_ID == "nus_area_denial_v1"
    assert all(v == "LOCAL" for k, v in template.items() if k != "layout_id")


@pytest.mark.parametrize("team", TEAMS)
def test_built_interface_has_the_template_keys_and_the_documented_content(parts, team):
    rules, deploy, actors = parts
    data = interface_mod.build_interface(team, rules, deploy, actors[team].meta, COMMIT)
    assert tuple(data) == interface_mod.INTERFACE_KEYS
    assert data["layout_id"] == "nus_area_denial_v1" and data["serves_interface_version"] == INTERFACE_VERSION
    assert data["team"] == team and data["guard_count"] == rules.guard_count and data["strike_count"] == rules.strike_count
    assert data["opponents_seen"] == (rules.strike_count if team == "guard" else rules.guard_count)
    assert data["metres_per_unit"] == deploy.metres_per_unit and data["hold_ticks"] == deploy.hold_ticks
    assert data["seconds_per_step"] == deploy.seconds_per_step
    assert data["vertical_speed"] == 0 and data["yaw_rate"] == 0 and data["prior_weight"] == 0
    assert data["compute_dtype"] == actors[team].meta["compute_dtype"] and data["checkpoint_sha256"] == actors[team].meta["sha256"]
    assert data["source_commit"] == COMMIT
    for key in ("field_order", "latch_rule", "previous_step_sampling", "action_form"):
        assert isinstance(data[key], str) and data[key]


def test_written_file_round_trips_and_lives_only_under_runs(parts, tmp_path):
    rules, deploy, actors = parts
    data = interface_mod.build_interface("guard", rules, deploy, actors["guard"].meta, COMMIT)
    with pytest.raises(ValueError, match="runs"):
        interface_mod.write_interface(tmp_path / "interface.toml", data)
    inside = deploy_mod.ROOT / "runs" / "nus_port" / "weights" / "_test_interface_folder" / "interface.toml"
    try:
        written = interface_mod.write_interface(inside, data)
        assert tomllib.loads(written.read_text()) == data
    finally:
        inside.unlink(missing_ok=True)
        inside.parent.rmdir()


def test_refuses_a_commit_that_is_not_a_hash_and_a_team_that_is_not_a_team(parts):
    rules, deploy, actors = parts
    with pytest.raises(ValueError, match="commit"):
        interface_mod.build_interface("guard", rules, deploy, actors["guard"].meta, "main")
    with pytest.raises(ValueError, match="team"):
        interface_mod.build_interface("referee", rules, deploy, actors["guard"].meta, COMMIT)
