"""Route 3, stage LS1, task LS1-M4-T3: the run 0 mark for the network (``scripts/ste_l3_run0_ceiling.py``; plan
ste_learning/drafts/LS1_TASK_PLAN.md section 5, with the design check's corrections).

Under ``[learner] skill_source = "net"`` the ceiling plays every constant choice of the two-level Strike team flown by
the Strike skill network, and sets the network's own mark (best constant choice less the margin, above the untrained
net team's Wilson upper bound). The control that a one-script choice replays T44's scripted cell becomes INFO (the T44
numbers are kept): equivalence of the network and the scripts is LS1.2's gate, so both modes (the mark and
``--oracle-check``) take ``--equivalence <folder>`` once per side and refuse (exit 2) unless each read is complete, of
record, DISTILLED and names that side's ``[learner.skill_net]`` sha256 (mapped by ``net_sha256``, cross-checked with
``cells[].side``); a FILL_, missing or edited Strike network is refused (exit 2, ``skill_net.net_problems``) before a
game is played. ``--oracle-check`` flies the hold-1 oracle ``NetComposite`` (drone m flies its code through
``skill_net.one_code`` on the whole team tensor, no heads, no dispatch). The scripts route is untouched
(tests/test_ste_l3_run0_ceiling.py).

Gate files: the SMOKE file cut to variant base with the two-level table and tiny untrained networks
(``tests/_ste_ls1.net_gate_file``); the LS1.2 reads are fakes (``tests/_ste_ls1.distilled_read``). CPU only."""
import json
import shutil
import sys

import pytest
import torch

import _ste_ls1 as H
from _ste_ls1 import ROOT, distilled_read, net_gate_file
from _torch_threads import default_torch_threads  # noqa: F401  (autouse: CPU numerics at the default thread count)
from svg_training.ste import exploit, skill_net, skills

sys.path.insert(0, str(ROOT / "scripts"))
import ste_l3_run0_ceiling as ceiling  # noqa: E402

GAMES = 3
CHUNK = "33"
SIDES = ("guard", "strike")
T44 = "ctl_one_script_choices_are_reference"
LOG = "ctl_choice_log_is_the_fixed_choice"


def reads(folder, nets, **kw) -> dict:
    """A fake LS1.2 read of each side's network under ``folder``: {side: its folder}."""
    return {side: distilled_read(folder / f"eq_{side}", side, nets[side][1], **kw).parent for side in SIDES}


def eq_args(folders) -> list[str]:
    out = []
    for f in folders:
        out += ["--equivalence", str(f)]
    return out


@pytest.fixture(scope="module")
def net(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("net_ceiling")
    gates_file, nets = net_gate_file(tmp / "g")
    return {"tmp": tmp, "gates": gates_file, "nets": nets, "reads": reads(tmp, nets)}


@pytest.fixture(scope="module")
def done(net):
    out = net["tmp"] / "run"
    code = ceiling.main(["--gates", str(net["gates"]), "--games", str(GAMES), "--chunk", CHUNK, "--out", str(out),
                         *eq_args(net["reads"].values())])
    assert code == 0
    return out


def _res(folder):
    return json.loads((folder / "results.json").read_text())


# ================================================================================================ the mark
def test_net_ceiling_runs_and_sets_a_mark_from_the_nets_own_best(done, net):
    res = _res(done)
    g = exploit.load_gates(net["gates"])
    assert res["complete"] and res["games"] == GAMES and res["gates_sha256"] == g.sha256
    assert [c["name"] for c in res["choices"]] == [c["name"] for c in ceiling.choices(g)]
    learner = res["learner"]
    assert learner == skills.learner_table(g.learner)
    assert learner["skill_source"] == skills.NET_SOURCE
    assert learner["skill_net_sha256"] == {side: net["nets"][side][1] for side in SIDES}
    ctl = res["controls"]
    assert ctl[T44]["status"] == ceiling.INFO                    # LS1.2's gate, not this run's
    one_script = [c["name"] for c in res["choices"] if c["script"]]
    assert len(one_script) == 6 and all(name in ctl[T44]["detail"] for name in one_script)   # T44 numbers kept
    assert ctl[LOG]["status"] == "PASS"
    assert all(v["status"] == "PASS" for k, v in ctl.items() if k != T44)
    mark = res["mark"]
    assert mark["k_best"] == max(c["k"] for c in res["choices"]) == res["best"]["k"]
    assert res["untrained"]["name"] == ceiling.untrained_choice(ceiling.choices(g), g)["name"]
    assert mark == ceiling.mark_rule(res["best"]["k"], res["untrained"]["k"], GAMES, float(g.run0["margin"]),
                                     of_record=False)
    assert res["equivalence"] == {side: {"folder": str(net["reads"][side]), "net_sha256": net["nets"][side][1],
                                         "verdict": "DISTILLED"} for side in SIDES}
    assert (done / "results.md").read_text().startswith("Simulator: training simulator, tier 1")


def test_the_net_flies_the_choices_not_the_scripts(net):
    """The same choices under the scripts gate file (no network) play other games: the network, not the dispatch's
    scripts, flies the net ceiling (the tiny network is untrained)."""
    g = exploit.load_gates(net["gates"])
    scripts_file = net["tmp"] / "g" / "scripts_twin_gates.toml"
    gs = exploit.load_gates(scripts_file)
    ref = exploit.load_reference(exploit.ROOT / g.reference["file"])
    chs = [ceiling.untrained_choice(ceiling.choices(g), g)]
    mine = ceiling.play(g, ref, chs, GAMES, "cpu", chunk=1)["cells"][0]
    theirs = ceiling.play(gs, ref, chs, GAMES, "cpu", chunk=1)["cells"][0]
    assert exploit.agreement(mine, theirs)["differ"] > 0


def test_a_fill_mark_in_the_draft_gate_file_loads_runs_and_renders(net, tmp_path, monkeypatch):
    """The lead's draft copy of heads_gates.toml holds ``[run0] skills_reach_min = "FILL_..."`` while the ceiling runs:
    the run is not refused, and the current mark is shown as written."""
    monkeypatch.setattr(exploit, "SKILLS_RUN0_EVAL_GAMES", 8)     # the smoke's 8 evaluation games
    text = net["gates"].read_text().replace('script = "strike_straight"\n',
                                            'script = "strike_straight"\nskills_reach_min = "FILL_from_the_ceiling"\n',
                                            1)
    draft = tmp_path / "draft_gates.toml"
    draft.write_text(text)
    out = tmp_path / "run"
    assert ceiling.main(["--gates", str(draft), "--games", "2", "--out", str(out),
                         *eq_args(net["reads"].values())]) == 0
    res = _res(out)
    assert res["current_mark"] == "FILL_from_the_ceiling"
    assert "FILL_from_the_ceiling" in (out / "results.md").read_text()


# ================================================================================================ the oracle check
def test_net_oracle_check_passes_and_a_differing_oracle_fails_exit_6(done, net, tmp_path, monkeypatch):
    out = tmp_path / "check.json"
    assert ceiling.main(["--oracle-check", str(done), "--check-out", str(out), *eq_args(net["reads"].values())]) == 0
    chk = json.loads(out.read_text())
    res = _res(done)
    ranked = sorted(res["choices"], key=lambda c: -c["k"])
    want = list(dict.fromkeys([res["best"]["name"]] + [c["name"] for c in ranked[:ceiling.TOP]]))
    assert [c["name"] for c in chk["checked"]] == want
    assert chk["status"] == "PASS" and chk["complete"] and chk["games"] == GAMES
    for c in chk["checked"]:
        assert c["differ"] == 0 and c["k_replay"] == c["k_oracle"] == c["k_ceiling"]
    assert chk["equivalence"] == res["equivalence"]

    real = ceiling.NetComposite

    class Wrong(real):
        """Every drone flies the Strike team's last code (a team strategy no checked free choice flies)."""

        def __init__(self, net_, codes, side, name):
            super().__init__(net_, [len(net_.skills) - 1] * len(codes), side, name)
    monkeypatch.setattr(ceiling, "NetComposite", Wrong)
    bad = tmp_path / "bad.json"
    assert ceiling.main(["--oracle-check", str(done), "--check-out", str(bad), *eq_args(net["reads"].values())]) == 6
    chk = json.loads(bad.read_text())
    assert chk["status"] == "FAIL" and any(c["differ"] > 0 for c in chk["checked"])


# ================================================================================================ refusals
def _bad_reads(net, tmp) -> dict:
    """{case: the --equivalence folders}: each must be refused."""
    nets, good = net["nets"], net["reads"]
    cases = {"none": [], "one side only": [good["strike"]], "the same side twice": [good["strike"], good["strike"]],
             "three reads": [good["guard"], good["strike"], good["strike"]],
             "a folder with no read": [good["guard"], tmp / "empty"]}
    (tmp / "empty").mkdir(parents=True)
    for case, kw in {"NOT DISTILLED": {"verdict": "NOT DISTILLED"}, "INCONCLUSIVE": {"verdict": "INCONCLUSIVE"},
                     "a smoke's NOT_RUN": {"verdict": "NOT_RUN"}, "not complete": {"complete": False},
                     "not of record": {"of_record": False}}.items():
        bad = distilled_read(tmp / case.replace(" ", "_").replace("'", ""), "strike", nets["strike"][1], **kw).parent
        cases[case] = [good["guard"], bad]
    other = distilled_read(tmp / "other_sha", "strike", "0" * 64).parent
    cases["of another net sha"] = [good["guard"], other]
    swapped = distilled_read(tmp / "side_swapped", "guard", nets["strike"][1]).parent   # the Strike sha, a Guard cell
    cases["cells of the other side"] = [good["guard"], swapped]
    return cases


def test_the_net_ceiling_needs_a_distilled_read_of_each_net_exit_2(done, net, tmp_path, capsys):
    for case, folders in _bad_reads(net, tmp_path / "reads").items():
        out = tmp_path / "out" / case.replace(" ", "_")
        code = ceiling.main(["--gates", str(net["gates"]), "--games", "2", "--out", str(out), *eq_args(folders)])
        assert code == 2, case
        assert not out.exists(), case                                    # refused before the folder is made
        assert "LS1.2" in capsys.readouterr().err, case
        chk = tmp_path / "chk" / f"{case.replace(' ', '_')}.json"
        assert ceiling.main(["--oracle-check", str(done), "--check-out", str(chk), *eq_args(folders)]) == 2, case
        assert not chk.exists(), case
        assert "LS1.2" in capsys.readouterr().err, case


def _strike_net_cases(net, tmp) -> dict:
    """{case: a gate file whose Strike network is FILL_, missing or edited}; the Guard network and the reads stay good
    (the reads name the sha256 the file pins, so only the network check can refuse it)."""
    nets = net["nets"]
    strike_file, strike_sha = nets["strike"]
    edited = tmp / "edited" / "skill_net_strike.pt"
    edited.parent.mkdir(parents=True)
    edited.write_bytes(strike_file.read_bytes() + b"\0")
    missing = tmp / "missing" / "skill_net_strike.pt"
    out = {}
    for case, entry in {"FILL_": (strike_file, "FILL_after_LS1.1"), "missing": (missing, strike_sha),
                        "edited": (edited, strike_sha)}.items():
        out[case], _ = net_gate_file(tmp / f"g_{case}", nets={"guard": nets["guard"], "strike": entry})
    return out


def test_a_fill_missing_or_edited_strike_net_is_refused_exit_2_in_both_modes(done, net, tmp_path, capsys):
    for case, gfile in _strike_net_cases(net, tmp_path).items():
        out = tmp_path / "out" / case
        code = ceiling.main(["--gates", str(gfile), "--games", "2", "--out", str(out),
                             *eq_args(net["reads"].values())])
        assert code == 2, case                                            # not 1: no uncaught ValueError
        assert not out.exists(), case
        assert "skill network" in capsys.readouterr().err, case
        # the oracle check of a finished folder whose gate file now pins that network
        folder = tmp_path / "folders" / case
        shutil.copytree(done, folder)
        res = _res(folder)
        res.update(gates_file=str(gfile), gates_sha256=exploit.load_gates(gfile).sha256)
        (folder / "results.json").write_text(json.dumps(res))
        assert ceiling.main(["--oracle-check", str(folder), *eq_args(net["reads"].values())]) == 2, case
        assert not (folder / ceiling.ORACLE_FILE).exists(), case
        assert "skill network" in capsys.readouterr().err, case


def test_equivalence_reads_belong_to_the_net_route_only(net, tmp_path, capsys):
    """The scripts route takes no ``--equivalence`` (it plays the scripts themselves); refused, nothing written."""
    out = tmp_path / "run"
    assert ceiling.main(["--games", "2", "--out", str(out), *eq_args(net["reads"].values())]) == 2
    assert not out.exists()
    assert "--equivalence" in capsys.readouterr().err


def test_the_hold_1_oracle_flies_each_drone_its_own_code_through_one_code(net):
    """``NetComposite`` (no heads, no dispatch): drone m's command is ``one_code`` of code ``codes[m]`` on the whole
    team's observation, batch shape [n, M] (the dispatch path's, constraint 8)."""
    g = exploit.load_gates(net["gates"])
    cfg, obs = H.team_obs(g, "strike", n=5, ticks=20)
    snet, _ = skill_net.load_skill_net(net["nets"]["strike"][0], team="strike",
                                       skills=skills.team_skills(g.players, "strike"), cfg=cfg, device="cpu",
                                       file_sha256=net["nets"]["strike"][1])
    codes = [3, 0, 5]
    orc = ceiling.NetComposite(snet, codes, "strike", "oracle:x")
    got = orc.act(obs)
    want = skill_net.one_code(snet, obs, torch.tensor(codes).expand(5, 3))
    assert orc.team == "strike" and orc.name == "oracle:x"
    assert torch.equal(got, want)
