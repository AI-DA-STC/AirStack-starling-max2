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
    path = Path(folder) / "pilot.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"strike_recipe": {"recipe": exploit.RECIPE_BARE, "side_overrides_strike": {}}}))
    return path


def run0_json(folder, gates):
    path = Path(folder) / "run0.json"
    path.write_text(json.dumps({"status": "PASS", "complete": True, "cap_h": 1.0,
                                "gates_sha256": exploit.load_gates(gates).sha256}))
    return path


def run(gates, run_dir, side, *extra):
    pj = pilot_json(Path(run_dir).parent)
    r0 = ["--run0-json", str(run0_json(Path(run_dir).parent, gates))] if side == "strike" else []
    return driver.main(["--gates", str(gates), "--variant", "base", "--side", side, "--run-dir", str(run_dir),
                        "--cap-h", "1", "--pilot-json", str(pj), *r0, *extra])


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
    g = gate_file(tmp / "g")
    out = {}
    for side in ("strike", "guard"):
        r = tmp / side
        extra = () if side == "guard" else ("--no-videos",)
        assert run(g, r, side, *extra) == 0, side
        out[side] = r
    mp.undo()
    return g, out


# ================================================================================================ test 9: the driver
def test_a_two_level_run_on_each_side_passes_its_controls_and_writes_every_file(two_runs):
    g, runs = two_runs
    for side, r in runs.items():
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
    for side, r in runs.items():
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
    for side, r in runs.items():
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
    assert run(g, runs["strike"], "strike", "--no-videos") == 0
    assert (runs["strike"] / "results.json").read_text() == before


# ================================================================================================ test 18: still refused
def test_run0_pilot_and_verdict_refuse_a_two_level_gate_file(two_runs, tmp_path, capsys):
    g, runs = two_runs
    code = driver.main(["--run0", "--gates", str(g), "--run-dir", str(tmp_path / "r0"), "--cap-h", "1", "--no-videos",
                        "--pilot-json", str(pilot_json(tmp_path))])
    assert code == 2 and WHY in capsys.readouterr().err
    code = driver.main(["--pilot", "--gates", str(g), "--run-dir", str(tmp_path / "p"), "--cap-h", "1"])
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
