"""STE L3-L6 pipeline check: its four gate files (configs/ste_l3/; spec ste_learning/drafts/L3_L6_PIPELINE_SPEC.md) and
their budget (configs/ste_learning.toml [budget_l3_l4_l5_l6]). Nothing is played: the files load, they are one template
(the two routes and their pool-only controls differ only where the spec says), the game is G0's (3v3, 1-for-1 tag at
1.6 m, landing off, the even filter split), the skills route's run 0 mark is pre-registered, and each file's task fits
the budget."""
import tomllib

import pytest

from svg_training.ste import exploit, skills
from svg_training.ste.config import load_ste_learning

FILES = {name: exploit.ROOT / "configs" / "ste_l3" / f"{name}_gates.toml"
         for name in ("velocity", "skills", "velocity_poolonly", "skills_poolonly")}
TASKS = {"velocity": "L5.1", "skills": "L5.2", "velocity_poolonly": "L5.3", "skills_poolonly": "L5.4"}


@pytest.fixture(scope="module")
def gates():
    return {name: exploit.load_gates(path) for name, path in FILES.items()}


def test_every_file_loads_with_its_route_mask_and_task(gates):
    for name, g in gates.items():
        assert g.run["task"] == TASKS[name]
        assert g.learner.skills == name.startswith("skills")
        assert g.learner.mask_absent == (not name.endswith("poolonly"))
        assert g.pool == {"enabled": True, "seed": 140001}
        assert exploit.game_file_problems(g) == [] and exploit.unfilled(g) == []
        assert list(g.variants) == ["base"] and g.run["eval_games"] == 1000


def test_the_four_files_are_one_template(gates):
    """Same game, recipe, step budget, seeds and pool draws: the files differ only in [run] task, [learner], the
    skills route's [run0] skills_reach_min and, after the fill step (spec 2b rule 1), the Strike recipe per route
    (`[trainer] side_overrides.strike`), which is the same within a route's main and pool-only files."""
    def core(path):
        d = tomllib.loads(path.read_text())
        d["run"].pop("task")
        d.pop("learner")
        d["run0"].pop("skills_reach_min", None)
        d["trainer"]["side_overrides"].pop("strike")
        return d
    first = core(FILES["velocity"])
    for name, path in FILES.items():
        assert core(path) == first, name
    strike = {name: tomllib.loads(path.read_text())["trainer"]["side_overrides"]["strike"] for name, path in FILES.items()}
    assert strike["velocity"] == strike["velocity_poolonly"] and strike["skills"] == strike["skills_poolonly"]
    tr = {g.trainer["game_steps_per_run"] for g in gates.values()}
    assert tr == {550_000_000}


def test_the_game_is_g0s_with_landing_off_and_the_even_split(gates):
    cfg = exploit.variant_cfg(gates["skills"], "base")
    assert cfg.tag.mode == "nearest_pair_1for1" and cfg.tag.radius_m == 1.6
    assert cfg.landing.enabled is False and cfg.filter.share == "equal"
    assert cfg.estimate_error.enabled is False                          # lead's answer 2 (24 Nov 2026)
    assert gates["skills"].run["size"] == "3v3"


def test_the_skills_route_is_r30s_with_its_run0_mark(gates):
    for name in ("skills", "skills_poolonly"):
        g = gates[name]
        assert g.learner.choice == skills.TWO_LEVEL and g.learner.entropy_scale == {"team": 0.01, "drone": 0.01}
        assert g.learner.drone_skills["strike"][0] == exploit.SKILLS_RUN0_FIRST_STRIKE_SKILL
        assert list(g.learner.drone_skills["guard"]) == ["guard_parked_centre", "guard_mark_edge", "guard_mirror"]
        assert g.run0["skills_reach_min"] == 0.554 and g.run0["opponent"] == "guard_parked_centre"
    assert "skills_reach_min" not in gates["velocity"].run0
    assert "SUM of the two per-head KLs" in FILES["skills"].read_text()


def test_each_files_task_is_in_the_pipeline_budget(gates):
    cfg, _ = load_ste_learning()
    for g in gates.values():
        assert cfg.budget_of(g.run["task"]).section == "budget_l3_l4_l5_l6"
        assert cfg.cap_gpu_h(g.run["task"]) > 0
