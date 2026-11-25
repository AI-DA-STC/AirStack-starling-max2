"""Route 3, stage LS1, task LS1-M1-T4: the ``skill_source`` setting, the net-backed dispatch and the meta rules
(``ste/skills.py``; plan ste_learning/drafts/LS1_TASK_PLAN.md, contracts C4 and C5).

1. The scripts route is byte for byte as before (the committed evidence copies are the "saved before" fixtures).
2. The new keys are refused where they do not belong.
3. ``learner_spec`` keeps the new fields (through ``exploit.load_gates``).
4. The factory builds the net dispatch: it flies the network's one code and all codes; every refusal.
5. The checkpoint meta and the learner table differ only for a net; a reload across the two routes is refused.
6. ``FILL_PREFIX`` is the gate files' mark.
7. The tier-2 loader refuses a net (not wired).
8. The training driver refuses a net until LS1-M4-T2 (deleted there).

Every net gate file is written by ``tests/_ste_ls1.net_gates_text``. CPU only; the networks are tiny and untrained."""
import dataclasses
import json
import os
import sys
import tomllib

import pytest
import torch

import _ste_ls1 as H
from _ste_ls1 import ROOT, SKILLS_GATES, net_gates_text, save_tiny_net, team_obs, tiny_learner_saved
from _torch_threads import default_torch_threads  # noqa: F401  (autouse: CPU numerics at the default thread count)
from svg_training.core.observations import ObsView
from svg_training.ste import exploit, exploit_train, skill_net, skills, tier2_train

sys.path.insert(0, str(ROOT / "scripts"))
import ste_exploit_l012 as l012  # noqa: E402

V = ObsView()
SIDES = ("guard", "strike")
EVIDENCE = ROOT / "records" / "evidence" / "2026-11-25_ste_l3_l6_pipeline"
SIX_KEYS = {"team", "players", "choice", "team_strategies", "drone_skills", "free_index"}
WRONG_SHA = "0" * 64
FILL_SHA = "FILL_after_LS1.1"
OUT_GAMES = 8                 # the first games' drone 1 is made out (its row zero but the team flag)


@pytest.fixture(scope="module")
def gates():
    return exploit.load_gates(SKILLS_GATES)


@pytest.fixture(scope="module")
def cfg(gates):
    return exploit.variant_cfg(gates, "base")


@pytest.fixture(scope="module")
def nets(gates, cfg, tmp_path_factory):
    """{side: (absolute path, sha256)}: a tiny net of each side, team size 3, saved under a temporary folder."""
    folder = tmp_path_factory.mktemp("nets")
    return {side: save_tiny_net(folder / side, side, cfg, gates=gates, team_size=3) for side in SIDES}


def write(tmp_path, text, name="gates.toml"):
    p = tmp_path / name
    p.write_text(text)
    return p


def net_gates(tmp_path, nets_by_side, name="net_gates.toml"):
    return exploit.load_gates(write(tmp_path, net_gates_text(SKILLS_GATES.read_text(), nets_by_side), name))


def two_level_table(**extra) -> dict:
    """The skills gate file's [learner] table as a dict, plus ``extra``."""
    with open(SKILLS_GATES, "rb") as f:
        return {**tomllib.load(f)["learner"], **extra}


def entries(file="a.pt", sha=WRONG_SHA) -> dict:
    return {side: {"file": file, "sha256": sha} for side in SIDES}


# ================================================================================================ 1. off = as before
def test_scripts_route_is_byte_for_byte_as_before(gates, cfg, tmp_path):
    table = skills.learner_table(gates.learner)
    evidence = json.loads((EVIDENCE / "l3_run0_skills_learner_control.json").read_text())["learner"]
    assert table == evidence
    assert json.dumps(table) == json.dumps(evidence)
    for side in SIDES:
        d = skills.two_level_dispatch(gates.learner, gates.players, side, cfg, 4, "cpu", 0)
        assert type(d) is skills.TwoLevelDispatch
        meta = skills.skills_meta(d)
        assert set(meta) == SIX_KEYS
        s = tomllib.loads((EVIDENCE / "exports" / f"skills_{side}_interface.toml").read_text())["skills"]
        assert meta == {"team": side, "players": s["players"], "choice": "two_level",
                        "team_strategies": s["team_strategies"], "drone_skills": s["drone_skills"],
                        "free_index": s["free_index"]}
    explicit = exploit.load_gates(write(tmp_path, H.after_choice_line(SKILLS_GATES.read_text(),
                                                                       'skill_source = "scripts"')))
    assert explicit.learner == gates.learner
    assert skills.learner_table(explicit.learner) == table
    for side in SIDES:
        d = skills.two_level_dispatch(explicit.learner, explicit.players, side, cfg, 4, "cpu", 0)
        assert type(d) is skills.TwoLevelDispatch
        assert skills.skills_meta(d) == skills.skills_meta(
            skills.two_level_dispatch(gates.learner, gates.players, side, cfg, 4, "cpu", 0))


# ================================================================================================ 2. refusals
BELONG = "skill_source and skill_net belong to choice"
REFUSED = [
    ({"action": "velocity", "skill_source": "net"}, BELONG),
    ({"action": "velocity", "skill_net": entries()}, BELONG),
    ({"action": "velocity", "skill_source": "scripts"}, BELONG),
    ({"action": "skills", "choice": "team", "skill_source": "net", "skill_net": entries()}, BELONG),
    ({"action": "skills", "choice": "drone", "skill_source": "net"}, BELONG),
    (two_level_table(skill_source="onnx"), "skill_source must be one of"),
    (two_level_table(skill_source="net"), r'skill_source = "net" needs \[learner.skill_net\]'),
    (two_level_table(skill_source="scripts", skill_net=entries()), r'skill_net\] belongs to skill_source = "net"'),
    (two_level_table(skill_net=entries()), r'skill_net\] belongs to skill_source = "net"'),
    (two_level_table(skill_source="net", skill_net={"guard": entries()["guard"]}), "must have exactly the keys"),
    (two_level_table(skill_source="net", skill_net={**entries(), "both": entries()["guard"]}),
     "must have exactly the keys"),
    (two_level_table(skill_source="net", skill_net={**entries(), "guard": {"file": "a.pt", "sha256": WRONG_SHA,
                                                                           "size": 3}}), "file and sha256"),
    (two_level_table(skill_source="net", skill_net={**entries(), "guard": {"file": "a.pt"}}), "file and sha256"),
    (two_level_table(skill_source="net", skill_net=entries(sha="abc")), "64 lowercase hex"),
    (two_level_table(skill_source="net", skill_net=entries(sha="A" * 64)), "64 lowercase hex"),
    (two_level_table(skill_source="net", skill_net=entries(file="")), "file must be a non-empty string"),
    (two_level_table(skill_source="net", skill_net=entries(file=3)), "file must be a non-empty string"),
]


@pytest.mark.parametrize("table,why", REFUSED)
def test_new_keys_are_refused_where_they_do_not_belong(table, why):
    with pytest.raises(ValueError, match=why):
        skills.learner_spec(table)


def test_the_good_tables_load():
    spec = skills.learner_spec(two_level_table(skill_source="net", skill_net=entries(sha=FILL_SHA)))
    assert spec.skill_source == skills.NET_SOURCE and spec.skill_net == entries(sha=FILL_SHA)
    assert skills.SKILL_SOURCES == (skills.SCRIPTS_SOURCE, skills.NET_SOURCE) == ("scripts", "net")
    assert skills.learner_spec(two_level_table(skill_source="scripts")) == skills.learner_spec(two_level_table())


# ============================================================================================ 3. the spec keeps them
def test_learner_spec_keeps_the_new_fields(gates, tmp_path):
    nets = {"strike": ("ste_provisional/skill_nets/x/skill_net_strike.pt", WRONG_SHA),
            "guard": (str(tmp_path / "skill_net_guard.pt"), FILL_SHA)}
    text = net_gates_text(SKILLS_GATES.read_text(), nets)
    assert ("[reading]" in text) is H.READING_IN_NET_FILES          # LS1-M4-T1: True (a net file needs [reading])
    g = exploit.load_gates(write(tmp_path, text))
    assert g.learner.skill_source == "net"
    assert g.learner.skill_net == {side: {"file": f, "sha256": s} for side, (f, s) in nets.items()}
    assert g.learner.mask_absent is True
    assert dataclasses.replace(g.learner, skill_source="scripts", skill_net=None) == gates.learner
    with pytest.raises(AssertionError, match="occurs 0 times"):
        net_gates_text("[learner]\n", nets)


# ================================================================================================ 4. the factory
def test_net_dispatch_from_the_factory(gates, cfg, nets, tmp_path):
    g = net_gates(tmp_path, nets)
    for side in SIDES:
        d = skills.two_level_dispatch(g.learner, g.players, side, cfg, 64, "cpu", 0)
        assert type(d) is skills.NetTwoLevelDispatch and isinstance(d, skills.TwoLevelDispatch)
        assert d.skill_source == "net" and d.skill_net_sha256 == nets[side][1]
        assert d.names == skills.team_skills(gates.players, side) and list(d.net.skills) == d.names
        _, obs = team_obs(gates, side)
        obs = obs.clone()
        team_flag = obs[:OUT_GAMES, 1, V.team].clone()
        obs[:OUT_GAMES, 1] = 0.0
        obs[:OUT_GAMES, 1, V.team] = team_flag
        assert bool((obs[:, :, V.alive] > 0.5).any()) and bool((obs[:, :, V.alive] < 0.5).any())
        choice = torch.randint(0, d.k, obs.shape[:2], generator=torch.Generator().manual_seed(3))
        act = d.act(obs, choice)
        assert torch.equal(act, skill_net.one_code(d.net, obs, choice))
        every = d.commands(obs)
        assert torch.equal(every, skill_net.all_codes(d.net, obs))
        out = obs[..., V.alive] < 0.5
        assert bool((act[out] == 0).all()) and bool((every[out] == 0).all())
        assert bool((act[~out] != 0).any())
        with pytest.raises(ValueError, match="team size"):
            d.act(obs[:, :2], choice[:, :2])
        with pytest.raises(ValueError, match="team size"):
            d.commands(obs[:, :2])
    rel = os.path.relpath(nets["guard"][0], ROOT)                    # a relative file resolves from svg_training/
    g_rel = net_gates(tmp_path, {**nets, "guard": (rel, nets["guard"][1])}, "rel.toml")
    assert type(skills.two_level_dispatch(g_rel.learner, g_rel.players, "guard", cfg, 4, "cpu", 0)) is \
        skills.NetTwoLevelDispatch
    bad = {"file sha256": {**nets, "strike": (nets["strike"][0], WRONG_SHA)},
           "team: the file is 'guard'": {**nets, "strike": nets["guard"]},
           "not filled yet": {**nets, "strike": (nets["strike"][0], FILL_SHA)}}
    for why, by_side in bad.items():
        g_bad = net_gates(tmp_path, by_side, "bad.toml")
        with pytest.raises(ValueError, match=why):
            skills.two_level_dispatch(g_bad.learner, g_bad.players, "strike", cfg, 4, "cpu", 0)
    changed = dataclasses.replace(cfg, rules=dataclasses.replace(cfg.rules, keepout_strike_m=1.5))
    assert changed.rules.keepout_strike_m != cfg.rules.keepout_strike_m
    with pytest.raises(ValueError, match="game constants"):
        skills.two_level_dispatch(g.learner, g.players, "strike", changed, 4, "cpu", 0)


# ================================================================================================ 5. meta and table
@pytest.mark.parametrize("side", SIDES)
def test_meta_and_table_differ_only_for_a_net(gates, cfg, nets, tmp_path, side):
    g = net_gates(tmp_path, nets)
    scripts_saved, net_saved = tiny_learner_saved(gates, side), tiny_learner_saved(g, side)
    assert net_saved["skills"] == {**scripts_saved["skills"], "skill_source": "net",
                                   "skill_net_sha256": nets[side][1]}
    assert skills.learner_table(g.learner) == {**skills.learner_table(gates.learner), "skill_source": "net",
                                               "skill_net_sha256": {"guard": nets["guard"][1],
                                                                    "strike": nets["strike"][1]}}
    hidden = list(gates.trainer["hidden"])
    scripts_d = skills.two_level_dispatch(gates.learner, gates.players, side, cfg, 4, "cpu", 0)
    net_d = skills.two_level_dispatch(g.learner, g.players, side, cfg, 4, "cpu", 0)
    with pytest.raises(ValueError, match="skill lists"):
        exploit_train.skill_team_from_modules(side, scripts_saved, hidden, net_d, "cpu")
    with pytest.raises(ValueError, match="skill lists"):
        exploit_train.skill_team_from_modules(side, net_saved, hidden, scripts_d, "cpu")
    exploit_train.skill_team_from_modules(side, scripts_saved, hidden, scripts_d, "cpu")     # each its own: loads
    exploit_train.skill_team_from_modules(side, net_saved, hidden, net_d, "cpu")


# ================================================================================================ 6. the mark
def test_fill_prefix_is_the_gate_files_mark():
    assert skills.FILL_PREFIX == exploit.FILL_MARK == skill_net.FILL_MARK


# ================================================================================================ 7. tier 2
def test_tier2_loader_refuses_a_net(tmp_path):
    base = tier2_train.GATES_FILE.read_text() + H.TIER2_PLAYERS + H.TIER2_TWO_LEVEL
    assert tier2_train.load_gates(write(tmp_path, base, "base.toml")).learner.choice == "two_level"
    text = net_gates_text(base, {side: ("a.pt", WRONG_SHA) for side in SIDES}, reading=False)   # tier 2 has no [reading]
    with pytest.raises(ValueError, match="not wired"):
        tier2_train.load_gates(write(tmp_path, text))


# ================================================================================================ 8. the driver (M4-T2)
@pytest.mark.parametrize("mode", ["run", "--pilot", "--run0"])
def test_the_training_driver_refuses_a_net_until_m4(tmp_path, capsys, mode):
    g = write(tmp_path, net_gates_text(SKILLS_GATES.read_text(), {side: ("a.pt", WRONG_SHA) for side in SIDES}))
    run_dir = tmp_path / "run"
    head = ["--variant", "base", "--side", "guard"] if mode == "run" else [mode]
    code = l012.main(head + ["--gates", str(g), "--run-dir", str(run_dir), "--cap-h", "1"])
    assert code == 2
    assert "wired in M4" in capsys.readouterr().err
    assert not run_dir.exists()
