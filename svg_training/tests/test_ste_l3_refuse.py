"""STE phase L3, first slice: every driver or loader that builds a ``DecisionEnv`` or a velocity team directly refuses a
gate file whose ``[learner] action = "skills"`` (``ste/skills.require_velocity_learner``), with a clear message and exit 2,
until it is wired to the skills route; it never trains or scores the velocity route silently. A gate file with
``action = "velocity"`` (or no table) still passes the check. CPU only, nothing is played."""
import hashlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from svg_training.ste import exploit, skills, tier2_train

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import ste_cross_tag_l012d as cross  # noqa: E402
import ste_exploit_l012 as l012  # noqa: E402
import ste_score_matrix as matrix  # noqa: E402
import ste_tier2_l013 as l013  # noqa: E402
import ste_tier2_score_l18 as l18  # noqa: E402
import ste_vid1_capture as vid1  # noqa: E402

SKILLS = '\n[learner]\naction = "skills"\nchoice = "team"\n'
VELOCITY = '\n[learner]\naction = "velocity"\n'
WHY = "not wired into"


def gate_copy(where: Path, table: str, src: Path = exploit.GATES_FILE) -> Path:
    where.mkdir(parents=True, exist_ok=True)
    p = where / "gates.toml"
    p.write_text(src.read_text() + table)
    return p


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def run_folder(where: Path, table: str) -> dict:
    """A made-up run folder: the L0.12 gate file plus ``table``, and stand-in network and result files (never loaded:
    the refusal comes first). Returns the sha256 of each."""
    g = gate_copy(where, table)
    for name in ("agent_final.pt", "eval_final.npz", "run.json", "eval_info.npz"):
        (where / name).write_bytes(b"not read")
    return {"gates": sha(g), "agent": sha(where / "agent_final.pt"), "eval": sha(where / "eval_final.npz")}


def test_the_helper_refuses_skills_and_passes_velocity():
    with pytest.raises(skills.LearnerNotWired, match=WHY):
        skills.require_velocity_learner(skills.learner_spec({"action": "skills", "choice": "drone"}), "x")
    for spec in (skills.learner_spec(None), skills.learner_spec({"action": "velocity"})):
        skills.require_velocity_learner(spec, "x")
    skills.require_velocity_learner(SimpleNamespace(), "x")          # a gate file without the field: velocity
    assert issubclass(skills.LearnerNotWired, ValueError)            # the drivers' refusal path (exit 2)


# ------------------------------------------------------------------------------------------------ L0.12 trainer
def test_exploit_l012_main_refuses_a_skills_gate_file(tmp_path, capsys):
    g = gate_copy(tmp_path, SKILLS)
    code = l012.main(["--gates", str(g), "--variant", "base", "--side", "guard", "--run-dir", str(tmp_path / "run"),
                      "--cap-h", "1"])
    assert code == 2
    assert WHY in capsys.readouterr().err


def test_exploit_l012_build_learner_refuses_a_skills_gate_file(tmp_path):
    gates = exploit.load_gates(gate_copy(tmp_path, SKILLS))
    with pytest.raises(skills.LearnerNotWired, match="ste_exploit_l012"):
        l012.build_learner(gates, "base", "guard", 2, 1)


# ------------------------------------------------------------------------------------------------ L0.13 tier 2 trainer
def test_the_tier2_gate_loader_refuses_skills_and_loads_velocity(tmp_path):
    src = tier2_train.GATES_FILE
    with pytest.raises(skills.LearnerNotWired, match="tier2_train"):
        tier2_train.load_gates(gate_copy(tmp_path / "s", SKILLS, src))
    assert tier2_train.load_gates(gate_copy(tmp_path / "v", VELOCITY, src)).run == tier2_train.load_gates(src).run


def test_tier2_l013_main_refuses_a_skills_gate_file(tmp_path, capsys):
    g = gate_copy(tmp_path, SKILLS, tier2_train.GATES_FILE)
    code = l013.main(["--arm", "t1", "--run-dir", str(tmp_path / "run"), "--cap-h", "1", "--gates", str(g), "--dry-cpu"])
    assert code == 2
    assert WHY in capsys.readouterr().err


# ------------------------------------------------------------------------------------------------ team_from_modules callers
def test_score_matrix_refuses_a_skills_player(tmp_path):
    h = run_folder(tmp_path / "player", SKILLS)
    s = {"player": {"dir": str(tmp_path / "player"), "gates_sha256": h["gates"], "agent_sha256": h["agent"],
                    "eval_sha256": h["eval"], "variant": "base", "side": "guard"}}
    loaded, why = matrix.check_inputs(SimpleNamespace(), s)
    assert loaded is None and WHY in why and "ste_score_matrix" in why


def test_vid1_capture_refuses_a_skills_player(tmp_path, capsys):
    h = run_folder(tmp_path / "runs" / "r1", SKILLS)
    a = SimpleNamespace(trained_runs_dir=str(tmp_path / "runs"), out=str(tmp_path / "out"), runs=None)
    settings = {"trained_games": {"record": "test", "runs": ["r1"], "gates_sha256": h["gates"]}}
    assert vid1.trained_main(a, settings) == 2
    assert WHY in capsys.readouterr().out


@pytest.mark.parametrize("skills_side", ["guard", "strike"])
def test_tier2_score_l18_refuses_a_skills_player_on_either_side(tmp_path, skills_side):
    s = {}
    for side in ("guard", "strike"):
        run_folder(tmp_path / side, SKILLS if side == skills_side else VELOCITY)
        s[f"{side}_player"] = {"dir": str(tmp_path / side)}
    s["job"] = {"games": 1, "ticks_cap": 1}
    with pytest.raises(skills.LearnerNotWired, match="ste_tier2_score_l18"):
        l18.Context(s, SimpleNamespace(games=None, max_ticks=None), "cpu", None)
    if skills_side == "guard":
        with pytest.raises(skills.LearnerNotWired):
            l18.layout(s)


def test_cross_tag_l012d_refuses_skills_networks(tmp_path):
    """The driver pins one gate file (sha256) for both T46 runs, so both hold the same skills gate file here."""
    t = {"guard_run": "g", "strike_run": "s"}
    for side, name in (("guard", "g"), ("strike", "s")):
        h = run_folder(tmp_path / name, SKILLS)
        t[f"{side}_agent_sha256"], t[f"{side}_eval_sha256"], t["gates_sha256"] = h["agent"], h["eval"], h["gates"]
    loaded, why = cross.check_inputs(SimpleNamespace(t46_runs_dir=tmp_path), {"t46": t})
    assert loaded is None and WHY in why and "ste_cross_tag_l012d" in why
