"""STE phase L3, slice 2, test 10 (design note ste_learning/drafts/L3_SLICE2_DESIGN.md §4): the scoring-only
held-command arm, scripts/ste_l3_held_arm.py. Every script of both teams with its command frozen for 12 ticks
(``HeldPlayer``'s command path) against every script of the other team, on T44's starts, beside the same script closed
loop (the reference cell). The control: the same play at hold 1 equals the reference game for game. CPU, 4 games."""
import json
import sys

import pytest

from svg_training.ste import exploit, skills

from _ste_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import ste_l3_held_arm as arm  # noqa: E402

GAMES = 4


@pytest.fixture(scope="module")
def done(tmp_path_factory):
    out = tmp_path_factory.mktemp("held") / "arm"
    assert arm.main(["--variant", "base", "--games", str(GAMES), "--out", str(out)]) == 0
    return out


def test_every_script_of_both_teams_is_held_against_every_script_of_the_other(done):
    gates = exploit.load_gates()
    res = json.loads((done / "results.json").read_text())
    assert res["hold_ticks"] == 12 and res["games"] == GAMES and res["complete"]
    assert res["controls"]["hold1_replay"]["status"] == "PASS"
    want = {(side, s, o) for side in ("strike", "guard") for s in skills.team_skills(gates.players, side)
            for o in skills.team_skills(gates.players, "guard" if side == "strike" else "strike")}
    got = {(c["side"], c["script"], c["opponent"]) for c in res["cells"]}
    assert got == want and len(want) == 60
    for c in res["cells"]:
        assert c["held"]["n"] == c["closed"]["n"] == GAMES
        assert c["held_only"] + c["both"] + c["closed_only"] + c["neither"] == GAMES
    assert any(c["differ"] > 0 for c in res["cells"]), "holding the command changed no game: the arm has no power"
    assert (done / "results.md").read_text().startswith("Simulator: training simulator, tier 1")


def test_the_closed_loop_column_is_the_reference_cell(done):
    gates = exploit.load_gates()
    ref = exploit.load_reference(exploit.ROOT / gates.reference["file"])
    for c in json.loads((done / "results.json").read_text())["cells"]:
        cell = (c["opponent"], c["script"]) if c["side"] == "strike" else (c["script"], c["opponent"])
        won = exploit.STRIKE_WIN if c["side"] == "strike" else exploit.GUARD_WIN
        assert c["closed"]["k"] == int((ref.cell("base", *cell)["outcome"][:GAMES] == won).sum()), c


def test_a_finished_folder_and_bad_arguments_are_refused(done, tmp_path):
    assert arm.main(["--variant", "base", "--games", str(GAMES), "--out", str(done)]) == 2
    assert arm.main(["--variant", "nope", "--games", "4", "--out", str(tmp_path / "a")]) == 2
    assert arm.main(["--variant", "base", "--games", "0", "--out", str(tmp_path / "b")]) == 2
    assert arm.main(["--variant", "base", "--games", "100000", "--out", str(tmp_path / "c")]) == 2


def test_a_failed_hold_1_control_publishes_nothing_exit_6(tmp_path, monkeypatch):
    monkeypatch.setattr(exploit, "agreement", lambda a, b: {"differ": 1, "games": len(a["outcome"])})
    out = tmp_path / "arm"
    assert arm.main(["--variant", "base", "--games", "2", "--out", str(out)]) == 6
    assert not (out / "results.json").exists()
    assert json.loads((out / "controls.json").read_text())["hold1_replay"]["status"] == "FAIL"


def test_the_arm_checks_its_inputs_against_the_gate_file_pins(tmp_path, capsys):
    """QC S2: the same input checks as the L0.12 preflight: a missing reference file, a reference of another sha256 or
    a game file that differs from its pin exits 2 with a message (no traceback), nothing played."""
    text = exploit.GATES_FILE.read_text()
    ref_file = exploit.load_gates().reference["file"]
    cases = {"missing": text.replace(f'file = "{ref_file}"', 'file = "configs/ste_l012/no_such_reference.npz"', 1),
             "ref_sha": text.replace(exploit.load_gates().reference["sha256"], "0" * 64, 1)}
    game = next(iter(exploit.load_gates().games.values()))
    cases["game_sha"] = text.replace(game.sha256, "1" * 64, 1)
    for name, body in cases.items():
        assert body != text, name
        g = tmp_path / f"{name}.toml"
        g.write_text(body)
        assert arm.main(["--gates", str(g), "--variant", "base", "--games", "2", "--out", str(tmp_path / name)]) == 2
        err = capsys.readouterr().err
        assert err.startswith("refused:") and "Traceback" not in err, (name, err)
        assert not (tmp_path / name / "controls.json").exists()
