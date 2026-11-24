"""STE phase L3: the constant-choice ceiling of the skills route's run 0 (scripts/ste_l3_run0_ceiling.py; addendum of
25 Nov 2026 to ste_learning/drafts/L3_SLICE2_DESIGN.md "Run 0 for the skills route").

Every constant choice of the two-level Strike team (each team strategy; each per-drone combination of the drone skills
under "free", K_d ** M of them) held for the whole game against [run0] opponent (guard_parked_centre), on T44's starts,
through the scoring path (``exploit.play_cells``, ``HeldPlayer`` holding the choice of a ``SkillTeam`` over the
``TwoLevelDispatch``). The mark rule: skills_reach_min = (best reaches - margin x n) / n, above the untrained team's
Wilson upper bound or the lead re-plans. CPU, a few games."""
import json
import sys

import pytest
import torch

from svg_training.core.metrics import wilson_interval
from svg_training.opponents.scripted import make_strategy
from svg_training.ste import exploit, skills

from _ste_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import ste_l3_run0_ceiling as ceiling  # noqa: E402

GAMES = 4
SKILLS_GATES = exploit.ROOT / "configs" / "ste_l3" / "skills_gates.toml"
VELOCITY_GATES = exploit.ROOT / "configs" / "ste_l3" / "velocity_gates.toml"


@pytest.fixture(scope="module")
def gates():
    return exploit.load_gates(SKILLS_GATES)


@pytest.fixture(scope="module")
def ref(gates):
    return exploit.load_reference(exploit.ROOT / gates.reference["file"])


@pytest.fixture(scope="module")
def done(tmp_path_factory):
    out = tmp_path_factory.mktemp("ceiling") / "run"
    assert ceiling.main(["--games", str(GAMES), "--out", str(out), "--chunk", "25"]) == 0
    return out


# ================================================================================================ the choices
def test_every_constant_choice_is_listed_once(gates):
    chs = ceiling.choices(gates)
    team, drone = gates.learner.team_strategies["strike"], gates.learner.drone_skills["strike"]
    m = 3
    assert len(chs) == len(team) + len(drone) ** m == 66
    assert len({c["name"] for c in chs}) == len(chs)
    assert all(not any(c["name"] == s for s in skills.team_skills(gates.players, "strike")) for c in chs)
    for t, name in enumerate(team, start=1):
        c = next(c for c in chs if c["kind"] == "team" and c["flies"] == [name] * m)
        assert c["heads"] == [(t, 0)] * m and c["script"] == name
    free = [c for c in chs if c["kind"] == "free"]
    assert {tuple(c["flies"]) for c in free} == {(a, b, d) for a in drone for b in drone for d in drone}
    for c in free:
        assert c["heads"] == [(skills.FREE, drone.index(s)) for s in c["flies"]]
        assert c["script"] == (c["flies"][0] if len(set(c["flies"])) == 1 else None)
    untrained = ceiling.untrained_choice(chs, gates)
    assert untrained["kind"] == "free" and untrained["flies"] == [drone[0]] * m


def test_a_fixed_team_resolves_to_its_choice_every_decision(gates):
    """The fixed-choice team goes through the two-level dispatch: its resolved flown players are the choice's."""
    cfg = exploit.variant_cfg(gates, "base")
    obs = torch.zeros(5, 3, 64)
    names = skills.team_skills(gates.players, "strike")
    for c in ceiling.choices(gates)[:3] + ceiling.choices(gates)[-3:]:
        team = ceiling.fixed_team(gates, c, cfg, 5, "cpu", 0)
        live = obs.clone()
        live[..., skills._V.alive] = 1.0
        flown = team.choose(live)
        assert flown.shape == (5, 3)
        assert [names[int(i)] for i in flown[0]] == c["flies"]
        assert bool((flown == flown[:1]).all())


# ================================================================================================ the mark rule
def test_the_mark_is_the_best_count_less_the_margin_on_the_1000_grid():
    r = ceiling.mark_rule(k_best=570, k_untrained=466, n=1000, margin=0.05)
    assert r["mark_count"] == 520 and r["skills_reach_min"] == 0.52
    hi = wilson_interval(466, 1000)[1]
    assert r["untrained_ci_high"] == hi and 0.496 < hi < 0.498
    assert r["mark_above_untrained_high"] is True and r["status"] == "MARK_SET"
    # the read compares rate >= mark: 520 / 1000 must meet 0.52 exactly (no float edge)
    assert exploit.skills_learner_control((520, 1000), r["skills_reach_min"])["pass"]
    assert not exploit.skills_learner_control((519, 1000), r["skills_reach_min"])["pass"]


def test_a_mark_not_above_the_untrained_teams_upper_bound_asks_the_lead_to_re_plan():
    r = ceiling.mark_rule(k_best=540, k_untrained=466, n=1000, margin=0.05)
    assert r["mark_count"] == 490 and r["mark_above_untrained_high"] is False
    assert r["status"] == "LEAD_RE_PLANS"
    edge = ceiling.mark_rule(k_best=547, k_untrained=466, n=1000, margin=0.05)    # 0.497 v the bound 0.49699
    assert edge["mark_above_untrained_high"] is True


# ================================================================================================ the small run
def test_every_choice_has_its_reaches_and_wilson_interval(done, gates):
    res = json.loads((done / "results.json").read_text())
    assert res["complete"] and res["games"] == GAMES and res["opponent"] == "guard_parked_centre"
    assert res["hold_ticks"] == 12 and res["size"] == "3v3" and res["gates_sha256"] == gates.sha256
    assert [c["name"] for c in res["choices"]] == [c["name"] for c in ceiling.choices(gates)]
    for c in res["choices"]:
        assert c["n"] == GAMES and 0 <= c["k"] <= GAMES
        assert c["ci"] == list(wilson_interval(c["k"], GAMES)) and c["rate"] == c["k"] / GAMES
        assert c["k"] + c["holds"] + c["unfinished"] == GAMES
    best = max(res["choices"], key=lambda c: c["k"])
    assert res["best"]["name"] == best["name"] and res["best"]["k"] == best["k"]
    assert res["untrained"]["name"] == ceiling.untrained_choice(ceiling.choices(gates), gates)["name"]
    assert res["mark"] == ceiling.mark_rule(best["k"], res["untrained"]["k"], GAMES, float(gates.run0["margin"]))
    assert res["of_record"] is False                         # 4 games, not the 1,000 the mark is set on
    assert all(v["status"] == "PASS" for v in res["controls"].values())
    assert (done / "results.md").read_text().startswith("Simulator: training simulator, tier 1")


def test_the_cells_that_are_one_script_replay_t44(done, gates, ref):
    """Control: a choice that flies one script on every drone (each team strategy, each free same-skill choice) equals
    T44's cell of that script game for game; its reaches are T44's."""
    res = json.loads((done / "results.json").read_text())
    known = [c for c in res["choices"] if c["script"]]
    assert len(known) == 6
    opp = gates.run0["opponent"]
    for c in known:
        want = int((ref.cell("base", opp, c["script"])["outcome"][:GAMES] == exploit.STRIKE_WIN).sum())
        assert c["k"] == want, c["name"]
    detail = res["controls"]["ctl_one_script_choices_are_reference"]["detail"]
    assert all(c["name"] in detail for c in known)
    assert res["controls"]["ctl_choice_log_is_the_fixed_choice"]["status"] == "PASS"


def test_chunking_does_not_change_a_game(gates, ref):
    chs = ceiling.choices(gates)[:2] + ceiling.choices(gates)[10:12]
    one = ceiling.play(gates, ref, chs, 2, "cpu", chunk=len(chs))
    many = ceiling.play(gates, ref, chs, 2, "cpu", chunk=1)
    for a, b in zip(one["cells"], many["cells"]):
        for key in exploit.EXACT:
            assert (a[key] == b[key]).all(), key


class Composite:
    """The oracle, written without the dispatch: drone m flies script ``names[m]`` closed loop (its own column of that
    script's command on the whole team's observation)."""

    def __init__(self, names, cfg, n):
        self.team, self.name = "strike", "composite(" + ",".join(names) + ")"
        self.scripts = [make_strategy(nm, "strike", cfg, n, "cpu", 0) for nm in names]

    def reset(self, games):
        for s in self.scripts:
            s.reset(games)

    def act(self, obs):
        return torch.stack([s.act(obs)[:, m] for m, s in enumerate(self.scripts)], dim=1)


def test_a_mixed_free_choice_equals_its_oracle_without_the_dispatch(gates, ref):
    n = 3
    c = next(c for c in ceiling.choices(gates) if c["kind"] == "free" and len(set(c["flies"])) == 3)
    mine = ceiling.play(gates, ref, [c], n, "cpu", chunk=1)["cells"][0]
    cfg = exploit.variant_cfg(gates, "base")
    opp = gates.run0["opponent"]
    pg = exploit.play_cells(cfg, gates.run["size"], ref, [(opp, "oracle")], n, "cpu", ref.meta["seed"],
                            int(gates.run["ticks_cap"]), hold_ticks=1,
                            players={"oracle": Composite(c["flies"], cfg, n)})
    for key in exploit.EXACT:
        assert (mine[key] == pg[key]).all(), key


# ================================================================================================ refusals, controls
def test_a_finished_folder_a_velocity_gate_file_and_bad_arguments_are_refused(done, tmp_path, capsys):
    assert ceiling.main(["--games", str(GAMES), "--out", str(done)]) == 2
    assert ceiling.main(["--gates", str(VELOCITY_GATES), "--games", "2", "--out", str(tmp_path / "v")]) == 2
    assert "two_level" in capsys.readouterr().err
    assert ceiling.main(["--games", "0", "--out", str(tmp_path / "a")]) == 2
    assert ceiling.main(["--games", "100000", "--out", str(tmp_path / "b")]) == 2
    assert ceiling.main(["--games", "2", "--chunk", "0", "--out", str(tmp_path / "c")]) == 2
    assert not any((tmp_path / x / "results.json").exists() for x in "vabc")


def test_a_failed_control_publishes_nothing_exit_6(tmp_path, monkeypatch, gates):
    few = ceiling.choices(gates)[:3]
    monkeypatch.setattr(ceiling, "choices", lambda g: few)
    monkeypatch.setattr(exploit, "replay_ok", lambda *a, **k: (False, "made to differ"))
    out = tmp_path / "run"
    assert ceiling.main(["--games", "2", "--out", str(out)]) == 6
    assert not (out / "results.json").exists()
    controls = json.loads((out / "controls.json").read_text())
    assert controls["ctl_one_script_choices_are_reference"]["status"] == "FAIL"


def test_only_a_cpu_run_on_the_1000_evaluation_games_is_of_record():
    """Addendum of 25 Nov 2026: the device of record is the CPU (it replays T44 exactly; CUDA only within tolerance)."""
    assert ceiling.of_record(1000, "cpu") is True
    assert ceiling.of_record(1000, "cuda") is False and ceiling.of_record(1000, "cuda:0") is False
    assert ceiling.of_record(999, "cpu") is False
