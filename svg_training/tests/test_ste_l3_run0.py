"""STE phase L3: run 0, the learner positive control, for the skills route (lead's call 24 Nov 2026, pre-registered in
ste_learning/drafts/L3_SLICE2_DESIGN.md "Run 0 for the skills route").

Run 0 = a two-level Strike learner trained against ``guard_parked_centre`` ([run0] opponent; 3v3, the base game,
T44's starts) at the run's step budget and cap. Known answer: the untrained skills team plays free + strike_straight
(about 466 reaches of 1,000 against the parked Guard, T70), a learner that picks high or low reaches near 1,000 (T44 /
T70: the parked Guard holds 0 against them). PASS = reaches >= [run0] skills_reach_min (0.90) of the evaluation games
(point estimate) at the FINAL checkpoint; FAIL at the full budget below that; INCONCLUSIVE at the cap. A FAIL is never
overridden; the skills Strike runs launch only on PASS.

The PASS mark is checked on synthetic results only; the tiny CPU run checks the plumbing (controls, reads, the
final-checkpoint rule, learner_control.json, and that a Strike run of record reads its verdict). No GPU."""
import json
import sys
from pathlib import Path

import pytest
import torch

from svg_training.ste import exploit, shared, skills

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
RUN0_LINE = 'script = "strike_straight"'


def gate_text(reach_min: str | None = "0.90", table: str = TWO_LEVEL) -> str:
    text = SMOKE.read_text()
    assert text.count(RUN0_LINE) == 1
    if reach_min is not None:
        text = text.replace(RUN0_LINE, f"{RUN0_LINE}\nskills_reach_min = {reach_min}", 1)
    return text + table


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


@pytest.fixture(autouse=True)
def scratch_shared(tmp_path, monkeypatch):
    monkeypatch.setenv(shared.SHARED_ENV, str(tmp_path / "shared"))
    monkeypatch.setenv(shared.LEGACY_LOGS_ENV, "")


# ================================================================================================ the mark (synthetic)
@pytest.mark.parametrize("k,ok", [(900, True), (1000, True), (899, False), (466, False)])
def test_the_mark_is_the_point_estimate_at_or_above_0_90(k, ok):
    rd = exploit.skills_learner_control((k, 1000), 0.90)
    assert rd["pass"] is ok and rd["threshold"] == 0.90 and rd["trained"]["k"] == k


def test_the_status_is_decided_at_the_final_checkpoint():
    passing, failing = {"update": 5, "pass": True}, {"update": 10, "pass": False}
    assert exploit.skills_run0_status([failing | {"update": 5}, passing | {"update": 10}], True, 10) == "PASS"
    assert exploit.skills_run0_status([passing, failing], True, 10) == "FAIL"      # an earlier pass does not count
    assert exploit.skills_run0_status([passing], False, 10) == "INCONCLUSIVE"     # stopped at the cap
    # QC S1: with the budget reached, the last read must be the final mark; otherwise no verdict
    assert exploit.skills_run0_status([], True, 10) == "INCONCLUSIVE"
    assert exploit.skills_run0_status([passing], True, 10) == "INCONCLUSIVE"     # the passing read is not the final


def test_skills_reach_min_is_checked_at_load(tmp_path, monkeypatch):
    monkeypatch.setattr(exploit, "SKILLS_RUN0_EVAL_GAMES", 8)                # the smoke file's 8 evaluation games
    g = exploit.load_gates(write(tmp_path / "a.toml", gate_text("0.90")))
    assert g.run0["skills_reach_min"] == 0.90
    for bad in ("0.0", "1.5", '"high"'):
        with pytest.raises(ValueError, match="skills_reach_min"):
            exploit.load_gates(write(tmp_path / "b.toml", gate_text(bad)))


def test_skills_reach_min_needs_the_1000_evaluation_games(tmp_path):
    """QC S3: the mark is pre-registered on 1,000 evaluation games (T44's / T70's counts); another count is refused."""
    assert exploit.SKILLS_RUN0_EVAL_GAMES == 1000
    with pytest.raises(ValueError, match="1000"):
        exploit.load_gates(write(tmp_path / "s.toml", gate_text("0.90")))          # smoke: eval_games = 8
    exploit.load_gates(write(tmp_path / "n.toml", gate_text(None)))               # without the mark: loads


# ================================================================================================ pilot_problem
def _pilot(gates):
    return {"strike_recipe": {"side_overrides_strike": gates.trainer["side_overrides"]["strike"]},
            "learner": skills.learner_table(gates.learner)}


def _run0(gates, status="PASS", **over):
    return {"complete": True, "gates_sha256": gates.sha256, "status": status, "cap_h": 1.0,
            "learner": skills.learner_table(gates.learner), **over}


def test_a_skills_strike_run_reads_the_skills_run_0s_verdict(tmp_path, monkeypatch):
    monkeypatch.setattr(exploit, "SKILLS_RUN0_EVAL_GAMES", 8)
    gates = exploit.load_gates(write(tmp_path / "g.toml", gate_text()))
    pilot = _pilot(gates)
    assert exploit.pilot_problem(gates, pilot, "strike", run0=_run0(gates), cap_h=1.0) is None
    assert "FAIL" in exploit.pilot_problem(gates, pilot, "strike", run0=_run0(gates, "FAIL"), cap_h=1.0)
    assert "FAIL" in exploit.pilot_problem(gates, pilot, "strike", "the lead says go", _run0(gates, "FAIL"), 1.0)
    assert "INCONCLUSIVE" in exploit.pilot_problem(gates, pilot, "strike", run0=_run0(gates, "INCONCLUSIVE"),
                                                   cap_h=1.0)
    # QC S2: the lead's flag does not launch a skills Strike run on an INCONCLUSIVE run 0 (launch only on PASS)
    assert "PASS" in exploit.pilot_problem(gates, pilot, "strike", "the lead says go", _run0(gates, "INCONCLUSIVE"),
                                           1.0)
    velocity_run0 = {k: v for k, v in _run0(gates).items() if k != "learner"}
    assert "skills" in exploit.pilot_problem(gates, pilot, "strike", run0=velocity_run0, cap_h=1.0)
    other = _run0(gates, learner={**skills.learner_table(gates.learner), "entropy_scale": {"team": 0.5, "drone": 0.5}})
    assert "skills" in exploit.pilot_problem(gates, pilot, "strike", run0=other, cap_h=1.0)
    assert exploit.pilot_problem(gates, pilot, "guard") is None                    # Guard runs need no run 0


def test_a_velocity_strike_run_still_reads_a_velocity_run_0():
    gates = exploit.load_gates(SMOKE)
    pilot = {"strike_recipe": {"side_overrides_strike": gates.trainer["side_overrides"]["strike"]}}
    run0 = {"complete": True, "gates_sha256": gates.sha256, "status": "PASS", "cap_h": 1.0}
    assert exploit.pilot_problem(gates, pilot, "strike", run0=run0, cap_h=1.0) is None
    inconclusive = {**run0, "status": "INCONCLUSIVE"}               # the velocity route's flag: unchanged (QC S2)
    assert exploit.pilot_problem(gates, pilot, "strike", run0=inconclusive, cap_h=1.0) is not None
    assert exploit.pilot_problem(gates, pilot, "strike", "the lead says go", inconclusive, 1.0) is None


# ================================================================================================ a tiny CPU run 0
@pytest.fixture(scope="module")
def tiny_run0(tmp_path_factory):
    """The real sequence on the CPU: the skills pilot on gate file A, A filled from it (B), run 0 on B."""
    tmp = tmp_path_factory.mktemp("l3_run0")
    mp = pytest.MonkeyPatch()
    mp.setattr(exploit, "SKILLS_RUN0_EVAL_GAMES", 8)        # test-only: the smoke file plays 8 evaluation games
    mp.setenv(shared.SHARED_ENV, str(tmp / "shared"))
    mp.setenv(shared.LEGACY_LOGS_ENV, "")
    a = write(tmp / "a" / "gates.toml", gate_text())
    assert driver.main(["--pilot", "--gates", str(a), "--run-dir", str(tmp / "pilot"), "--cap-h", "1"]) == 0
    pilot = tmp / "pilot" / "pilot.json"
    fill = json.loads(pilot.read_text())["strike_recipe"]["side_overrides_strike"]
    inline = "{ " + ", ".join(f"{k} = {v!r}" for k, v in fill.items()) + " }" if fill else "{}"
    g = write(tmp / "g" / "gates.toml", gate_text().replace("side_overrides = { strike = {}, guard = {} }",
                                                            f"side_overrides = {{ strike = {inline}, guard = {{}} }}",
                                                            1))
    r = tmp / "run0"
    code = driver.main(["--run0", "--gates", str(g), "--run-dir", str(r), "--cap-h", "1", "--no-videos",
                        "--pilot-json", str(pilot)])
    mp.undo()
    return code, g, r, pilot


@pytest.fixture
def smoke_mark(monkeypatch):
    monkeypatch.setattr(exploit, "SKILLS_RUN0_EVAL_GAMES", 8)


def test_the_tiny_skills_run_0_trains_its_budget_and_writes_a_status(tiny_run0, smoke_mark):
    code, g, r, _ = tiny_run0
    assert code == 0
    gates = exploit.load_gates(g)
    out = json.loads((r / "learner_control.json").read_text())
    assert out["complete"] and out["status"] in ("PASS", "FAIL")
    assert out["learner"] == skills.learner_table(gates.learner)
    assert out["route"] == "skills" and out["skills_reach_min"] == 0.90
    assert out["budget_reached"] and out["updates"] == out["planned_updates"]       # no stop at an earlier read
    assert [rd["update"] for rd in out["reads"]] == out["checkpoints"]
    final = out["reads"][-1]
    assert final["update"] == out["planned_updates"]
    assert out["status"] == ("PASS" if final["trained"]["rate"] >= 0.90 else "FAIL")
    assert out["opponent"] == "guard_parked_centre" and out["trained_against"] == "GuardParkedCentre"
    controls = json.loads((r / "controls.json").read_text())
    assert all(v["status"] == "PASS" for v in controls.values()), controls
    assert "ctl_untrained_is_first_skill" in controls and "ctl_untrained_below_mark" in controls
    saved = torch.load(r / "agent_final.pt", weights_only=False)
    assert set(saved) == {"skills", "modules"}


def test_a_strike_run_of_record_follows_the_skills_run_0s_verdict(tiny_run0, smoke_mark, tmp_path, capsys):
    code, g, r, pilot = tiny_run0
    status = json.loads((r / "learner_control.json").read_text())["status"]
    args = ["--gates", str(g), "--variant", "base", "--side", "strike", "--run-dir", str(tmp_path / "s"), "--cap-h",
            "1", "--no-videos", "--pilot-json", str(pilot), "--run0-json", str(r / "learner_control.json")]
    if status == "FAIL":
        assert driver.main(args) == 2
        assert "FAIL" in capsys.readouterr().err
        assert driver.main(args + ["--accept-learner-control", "the lead says go"]) == 2
    else:
        assert driver.main(args) == 0


def test_the_same_command_on_a_finished_run_0_does_nothing_new(tiny_run0, smoke_mark):
    code, g, r, pilot = tiny_run0
    before = (r / "learner_control.json").read_text()
    assert driver.main(["--run0", "--gates", str(g), "--run-dir", str(r), "--cap-h", "1", "--no-videos",
                        "--pilot-json", str(pilot)]) == 0
    assert (r / "learner_control.json").read_text() == before


def test_a_skills_run_0_without_its_mark_is_refused(tmp_path, capsys, smoke_mark):
    g = write(tmp_path / "g" / "gates.toml", gate_text(None))
    code = driver.main(["--run0", "--gates", str(g), "--run-dir", str(tmp_path / "r"), "--cap-h", "1", "--no-videos",
                        "--pilot-json", str(write(tmp_path / "p.json", json.dumps(_pilot(exploit.load_gates(g)))))])
    assert code == 2 and "skills_reach_min" in capsys.readouterr().err


def test_a_skills_run_0_whose_first_strike_drone_skill_is_not_strike_straight_is_refused(tmp_path, capsys,
                                                                                          smoke_mark):
    """QC minor: the untrained control's known answer (free + strike_straight, about 466 of 1,000) needs
    strike_straight first in the Strike drone list."""
    table = TWO_LEVEL.replace('strike = ["strike_straight", "strike_flank", "strike_high", "strike_low"]',
                              'strike = ["strike_flank", "strike_straight", "strike_high", "strike_low"]')
    table = table.replace("[learner.drone_skills]", "[learner.drone_skills]", 1)
    text = gate_text(table=table).replace('strikes = ["strike_straight", "strike_flank"',
                                          'strikes = ["strike_flank", "strike_straight"', 1)
    g = write(tmp_path / "g" / "gates.toml", text)
    gates = exploit.load_gates(g)
    assert gates.learner.drone_skills["strike"][0] == "strike_flank"
    code = driver.main(["--run0", "--gates", str(g), "--run-dir", str(tmp_path / "r"), "--cap-h", "1", "--no-videos",
                        "--pilot-json", str(write(tmp_path / "p.json", json.dumps(_pilot(gates))))])
    assert code == 2 and "strike_straight" in capsys.readouterr().err
