"""STE phase L3, slice 2, step 4: the two-level route wired into scripts/ste_exploit_l012.py (design note
ste_learning/drafts/L3_SLICE2_DESIGN.md, test 9, the driver half of test 18 and the driver half of test 11).

On the CPU with the committed smoke gate file plus a two-level ``[learner]`` table: a whole run on each side (controls,
including the untrained twin = "free + first drone skill" equal to that script's cell game for game; training; the
final batch; ``agent_final.pt`` with the skill lists; one CPU clip on one side); the final networks reloaded on their
own replay the scored games; ``--run0``, ``--pilot``, ``verdict`` and the single-head modes still refuse."""
import json
import sys
from pathlib import Path

import numpy as np
import pytest
import torch

from svg_training.ste import exploit, exploit_train, shared, skills

from _ste_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import ste_exploit_l012 as driver  # noqa: E402

SMOKE = exploit.ROOT / "configs" / "ste_l012" / "smoke_gates.toml"
TWO_LEVEL = """
[learner]
action = "skills"
choice = "two_level"

[learner.team_strategies]
strike = ["strike_sacrifice", "strike_converge"]
guard = ["guard_parked_ring", "guard_field"]

[learner.drone_skills]
strike = ["strike_straight", "strike_flank", "strike_high", "strike_low"]
guard = ["guard_parked_centre", "guard_mark_edge", "guard_mirror"]

[learner.entropy_scale]
team = 0.01
drone = 0.01
"""
SINGLE = '\n[learner]\naction = "skills"\nchoice = "drone"\n'
WHY = "not wired into"


def gate_file(folder: Path, table: str = TWO_LEVEL) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    p = folder / "gates.toml"
    p.write_text(SMOKE.read_text() + table)
    return p


def pilot_json(folder):
    """A velocity-style pilot.json stand-in (no gate sha, no learner): a skills run of record must refuse it."""
    path = Path(folder) / "pilot.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"strike_recipe": {"recipe": exploit.RECIPE_BARE, "side_overrides_strike": {}}}))
    return path


def skills_pilot(folder, gates):
    """The real two-level pilot of ``gates`` (QC S1: a skills run of record follows a skills pilot of its gate file)."""
    r = Path(folder) / "pilot"
    assert driver.main(["--pilot", "--gates", str(gates), "--run-dir", str(r), "--cap-h", "1"]) == 0
    return r / "pilot.json"


def run0_json(folder, gates):
    path = Path(folder) / "run0.json"
    path.write_text(json.dumps({"status": "PASS", "complete": True, "cap_h": 1.0,
                                "gates_sha256": exploit.load_gates(gates).sha256}))
    return path


def run(gates, run_dir, side, *extra, pilot=None):
    pj = pilot or pilot_json(Path(run_dir).parent)
    r0 = ["--run0-json", str(run0_json(Path(run_dir).parent, gates))] if side == "strike" else []
    return driver.main(["--gates", str(gates), "--variant", "base", "--side", side, "--run-dir", str(run_dir),
                        "--cap-h", "1", "--pilot-json", str(pj), *r0, *extra])


def sides(runs):
    return [(s, runs[s]) for s in ("strike", "guard")]


@pytest.fixture(autouse=True)
def scratch_shared(tmp_path, monkeypatch):
    monkeypatch.setenv(shared.SHARED_ENV, str(tmp_path / "shared"))
    monkeypatch.setenv(shared.LEGACY_LOGS_ENV, "")


@pytest.fixture(scope="module")
def two_runs(tmp_path_factory):
    """A two-level run on each side; the Guard run makes its clip (STANDARDS section 8), the Strike run does not."""
    tmp = tmp_path_factory.mktemp("l3_driver")
    mp = pytest.MonkeyPatch()
    mp.setenv(shared.SHARED_ENV, str(tmp / "shared"))
    mp.setenv(shared.LEGACY_LOGS_ENV, "")
    a = gate_file(tmp / "a")                     # the pilot runs on gate file A ...
    pilot = skills_pilot(tmp, a)
    fill = json.loads(pilot.read_text())["strike_recipe"]["side_overrides_strike"]
    g = gate_file(tmp / "g")                     # ... and the gate file is filled from it (B), as in L0.12's FILL steps
    inline = "{ " + ", ".join(f"{k} = {v!r}" for k, v in fill.items()) + " }" if fill else "{}"
    g.write_text(g.read_text().replace("side_overrides = { strike = {}, guard = {} }",
                                       f"side_overrides = {{ strike = {inline}, guard = {{}} }}", 1))
    assert exploit.load_gates(g).trainer["side_overrides"]["strike"] == fill
    out = {"pilot": pilot.parent, "pilot_gates": a}
    for side in ("strike", "guard"):
        r = tmp / side
        extra = () if side == "guard" else ("--no-videos",)
        assert run(g, r, side, *extra, pilot=pilot) == 0, side
        out[side] = r
    mp.undo()
    return g, out


# ================================================================================================ test 9: the driver
def test_a_two_level_run_on_each_side_passes_its_controls_and_writes_every_file(two_runs):
    g, runs = two_runs
    for side, r in sides(runs):
        for name in ("controls.json", "curve.json", "train_log.jsonl", "results.json", "results.md", "agent_final.pt",
                     "eval_final.npz"):
            assert (r / name).is_file(), (side, name)
        controls = json.loads((r / "controls.json").read_text())
        assert all(c["status"] == "PASS" for c in controls.values()), controls
        assert "ctl_untrained_is_first_skill" in controls and "ctl_untrained_is_still" not in controls
        spec = exploit.load_gates(g).learner
        assert spec.drone_skills[side][0] in controls["ctl_untrained_is_first_skill"]["detail"]
        res = json.loads((r / "results.json").read_text())
        assert res["learner"]["choice"] == "two_level"
        assert res["learner"]["drone_skills"][side] == list(spec.drone_skills[side])
        log = [json.loads(x) for x in (r / "train_log.jsonl").read_text().splitlines()]
        assert log and all(any(k.startswith("Loss / Entropy team") for k in x["losses"]) for x in log)
        saved = torch.load(r / "agent_final.pt", weights_only=False)
        assert set(saved) == {"skills", "modules"}
        assert saved["skills"]["team_strategies"] == list(spec.team_strategies[side])
        assert saved["skills"]["players"] == skills.team_skills(exploit.load_gates(g).players, side)


def test_the_untrained_two_level_team_equals_its_first_drone_skill_cell_game_for_game(two_runs):
    g, runs = two_runs
    gates = exploit.load_gates(g)
    n = int(gates.run["eval_games"])
    for side, r in sides(runs):
        before = np.load(r / "eval_before.npz")
        cells = exploit.eval_cells(gates, "base", side)
        first = gates.learner.drone_skills[side][0]
        twin = [c for c in cells if first in c][0]
        k = cells.index(twin)
        for key in ("outcome", "end_step", "tags"):
            assert np.array_equal(before[key][:n], before[key][k * n:(k + 1) * n]), (side, key)


def test_the_final_networks_reloaded_on_their_own_replay_the_scored_games(two_runs):
    """Training = scoring at the driver (design test 11): agent_final.pt through skill_team_from_modules, held 12
    ticks, replays the scored exploiter cell game for game."""
    g, runs = two_runs
    gates = exploit.load_gates(g)
    ref = exploit.load_reference(exploit.ROOT / gates.reference["file"])
    cfg = exploit.variant_cfg(gates, "base")
    for side, r in sides(runs):
        n = json.loads((r / "results.json").read_text())["eval_games"]
        d = skills.two_level_dispatch(gates.learner, gates.players, side, cfg, n, "cpu", 0)
        team = exploit_train.skill_team_from_modules(side, torch.load(r / "agent_final.pt", weights_only=False),
                                                     list(gates.trainer["hidden"]), d, "cpu")
        cell = exploit.eval_cells(gates, "base", side)[0]
        pg = exploit.play_cells(cfg, "3v3", ref, [cell], n, "cpu", ref.meta["seed"], gates.run["ticks_cap"],
                                learner=team, hold_ticks=gates.trainer["decision_ticks"])
        final = np.load(r / "eval_final.npz")
        for key in ("outcome", "end_step", "tags", "closest_3d_m"):
            assert np.array_equal(pg[key], final[key][:n]), (side, key)


def test_the_guard_run_made_its_clip_with_the_skills_team(two_runs):
    _, runs = two_runs
    res = json.loads((runs["guard"] / "results.json").read_text())
    assert res["videos"] and res["videos"][0].startswith("videos/"), res["videos"]
    assert all((runs["guard"] / v.split(":")[0]).is_file() for v in res["videos"])


def test_the_same_command_on_a_finished_two_level_run_does_nothing_new(two_runs):
    g, runs = two_runs
    before = (runs["strike"] / "results.json").read_text()
    assert run(g, runs["strike"], "strike", "--no-videos", pilot=runs["pilot"] / "pilot.json") == 0
    assert (runs["strike"] / "results.json").read_text() == before


# ================================================================================================ test 18: still refused
def test_run0_and_verdict_refuse_a_two_level_gate_file(two_runs, tmp_path, capsys):
    g, runs = two_runs
    code = driver.main(["--run0", "--gates", str(g), "--run-dir", str(tmp_path / "r0"), "--cap-h", "1", "--no-videos",
                        "--pilot-json", str(pilot_json(tmp_path))])
    assert code == 2 and WHY in capsys.readouterr().err
    code = driver.main(["verdict", "--gates", str(g), "--runs", f"{runs['strike']},{runs['guard']}", "--out",
                        str(tmp_path / "v")])
    assert code == 2 and WHY in capsys.readouterr().err
    assert not (tmp_path / "v").exists()


def test_a_single_head_mode_is_still_refused_for_training(tmp_path, capsys):
    g = gate_file(tmp_path / "s", SINGLE)
    assert run(g, tmp_path / "run", "guard", "--no-videos") == 2
    assert WHY in capsys.readouterr().err
    with pytest.raises(skills.LearnerNotWired, match="ste_exploit_l012"):
        driver.build_learner(exploit.load_gates(g), "base", "guard", 2, 1)


def test_build_learner_builds_the_two_level_learner(tmp_path):
    from svg_training.ste.two_level import TwoLevelIPPO
    learner = driver.build_learner(exploit.load_gates(gate_file(tmp_path)), "base", "strike", 2, 1)
    assert isinstance(learner.agent, TwoLevelIPPO) and learner.env.skills.widths == (3, 4)


# ================================================================================================ QC of step 4
def test_the_skills_pilot_records_its_gate_file_and_route_and_its_controls_pass(two_runs):
    """--pilot is wired for the two-level route: pilot.json names the gate file it ran under (sha256) and the
    [learner] table; the untrained skills team's controls pass on both sides (free + first drone skill = that script's
    cell). The runs followed it on the gate file filled from it (another sha256, the same [learner] table)."""
    g, runs = two_runs
    p = json.loads((runs["pilot"] / "pilot.json").read_text())
    assert p["gates_sha256"] == exploit.load_gates(runs["pilot_gates"]).sha256 != exploit.load_gates(g).sha256
    assert p["learner"] == driver.learner_block(exploit.load_gates(g))["learner"]
    assert p["learner"]["choice"] == "two_level"
    for side in ("strike", "guard"):
        ctl = p["eval"]["per_side"][side]["controls"]
        assert ctl["ctl_untrained_is_first_skill"]["status"] == "PASS" and "ctl_untrained_is_still" not in ctl
    assert {pt["side"] for pt in p["points"]} == {"strike", "guard"}


def test_a_skills_run_of_record_refuses_a_pilot_of_another_gate_file_or_route(two_runs, tmp_path, capsys):
    """QC S1: a velocity pilot.json (no route), one without the skills route, of another route, or of other skill lists
    or entropy scales is refused (exit 2): the run's budget and final reserve would come from another learner's
    rates."""
    g, runs = two_runs
    real = json.loads((runs["pilot"] / "pilot.json").read_text())
    other_lists = {**real["learner"], "drone_skills": {**real["learner"]["drone_skills"],
                                                       "guard": ["guard_parked_centre", "guard_mark_edge"]}}
    for name, data in (("velocity", {"strike_recipe": real["strike_recipe"], "gates_sha256": real["gates_sha256"]}),
                       ("no_route", {k: v for k, v in real.items() if k != "learner"}),
                       ("other_route", {**real, "learner": {**real["learner"], "choice": "team"}}),
                       ("other_lists", {**real, "learner": other_lists}),
                       ("other_scales", {**real, "learner": {**real["learner"],
                                                             "entropy_scale": {"team": 0.02, "drone": 0.01}}})):
        pj = tmp_path / f"{name}.json"
        pj.write_text(json.dumps(data))
        for side in ("strike", "guard"):
            assert run(g, tmp_path / f"{name}_{side}", side, "--no-videos", pilot=pj) == 2, (name, side)
            assert "skills pilot" in capsys.readouterr().err, (name, side)


def test_a_velocity_run_still_follows_a_hand_made_pilot(tmp_path):
    """The velocity route's preflight is unchanged (the L0.12 driver tests' stand-in pilot.json still passes it)."""
    args = driver.parse(["--gates", str(SMOKE), "--variant", "base", "--side", "guard", "--run-dir",
                         str(tmp_path / "r"), "--cap-h", "1", "--pilot-json", str(pilot_json(tmp_path))])
    assert driver.preflight(args, exploit.load_gates(SMOKE)) is None


def test_make_videos_refuses_a_skills_gate_file_with_a_learner_without_skills(tmp_path):
    """QC N1: the clip path follows the gate file's route; a skills gate file with a velocity learner fails loudly."""
    from types import SimpleNamespace
    g = exploit.load_gates(gate_file(tmp_path))
    stand_in = SimpleNamespace(modules=lambda: {}, saved=lambda: {})
    with pytest.raises(ValueError, match="skills"):
        driver.make_videos(g, "base", "guard", exploit.variant_cfg(g, "base"), stand_in, tmp_path)
