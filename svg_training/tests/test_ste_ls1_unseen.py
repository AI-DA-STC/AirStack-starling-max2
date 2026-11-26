"""LS1-M4-T6: ``scripts/ste_ls1_unseen.py``, the scores of the LS1.4 teams against players of no pool (INFO; plan
ste_learning/drafts/LS1_TASK_PLAN.md section 5, job LS1.4-H of workflow section 6).

Each route team (route 2: the scripts fly the chosen skill; route 3: the skill network flies it; two training pairs, two
sides) plays one cell against the other side's trained team of route 1 (the velocity route's L5.1 runs), both held
``[trainer] decision_ticks`` (12) in one ``exploit.play_cells`` call, on the CPU, on the reference's first
``eval_games`` starts.

SMOKE-sized fixtures (no training of record, nothing on the GPU): the route 1 gate file is the SMOKE file
(``configs/ste_l012/smoke_gates.toml``, velocity), route 2's the SMOKE file cut to base with the two-level table
(``_ste_ls1.smoke_two_level_text``), route 3's that text as a net gate file in the heads gate file's shape
(``_ste_ls1.net_gate_file``, variant ``base_s2`` for the second pair); each team a tiny learner after one update
(``_ste_ls1.tiny_learner_saved``) saved as a run folder's ``agent_final.pt`` beside a fake ``results.json`` and
``exit_code``. The fake-folder helpers live here: no other test uses them. CPU only."""
import json
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import torch

import _ste_ls1 as H
from _torch_threads import default_torch_threads  # noqa: F401  (autouse: CPU numerics at the default thread count)
from svg_training.core.rewards import GUARD_WIN, STRIKE_WIN
from svg_training.ste import exploit, exploit_train, jobs, scoring, skills

sys.path.insert(0, str(H.ROOT / "scripts"))
import ste_ls1_read as reader  # noqa: E402
import ste_ls1_unseen as unseen  # noqa: E402
import ste_score_matrix as matrix  # noqa: E402

ARMS, PAIRS, SIDES = ("route2", "route3"), ("s1", "s2"), ("guard", "strike")
VARIANT = {("route2", "s1"): "base", ("route2", "s2"): "base", ("route3", "s1"): "base", ("route3", "s2"): "base_s2"}
HOLD = 12                                      # the plan's hold: [trainer] decision_ticks of every gate file here
WHY_MATRIX = "not wired into"


def other(side: str) -> str:
    return "strike" if side == "guard" else "guard"


# ------------------------------------------------------------------------------------------------ the fake folders
def make_run(folder: Path, gates, variant: str, side: str, saved: dict) -> Path:
    """A finished run folder of the training driver as this scorer reads it: ``agent_final.pt`` (``saved``),
    ``results.json`` (complete, side, variant, gate sha256, train seed, budget reached, the scoring starts and, for the
    skills route, the ``[learner]`` table, as ``ste_exploit_l012.learner_block`` writes it) and ``exit_code`` 0."""
    folder.mkdir(parents=True, exist_ok=True)
    torch.save(saved, folder / "agent_final.pt")
    res = {"variant": variant, "side": side, "gates_sha256": gates.sha256,
           "reference": {"start_sha256": gates.reference["start_sha256"]},
           "train_seed": int(gates.variants[variant]["train_seed"][side]), "budget_reached": True}
    table = skills.learner_table(gates.learner)
    if table is not None:
        res["learner"] = table
    res["complete"] = True
    (folder / "results.json").write_text(json.dumps(res))
    (folder / jobs.EXIT_FILE).write_text("0\n")
    return folder


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    """The three gate files, a tiny learner per route and side, and the ten run folders of a full manifest."""
    tmp = tmp_path_factory.mktemp("unseen")
    files = {"route1": H.SMOKE_GATES, "route2": tmp / "scripts_gates.toml"}
    files["route2"].write_text(H.smoke_two_level_text())
    files["route3"], nets = H.net_gate_file(tmp / "net", heads_shape=True)
    gates = {route: exploit.load_gates(p) for route, p in files.items()}
    saved = {(route, side): H.tiny_learner_saved(gates[route], side) for route in gates for side in SIDES}
    folders = {("route1", side): make_run(tmp / "runs" / f"route1_{side}", gates["route1"], "base", side,
                                          saved[("route1", side)]) for side in SIDES}
    for (arm, pair), variant in VARIANT.items():
        for side in SIDES:
            folders[(arm, pair, side)] = make_run(tmp / "runs" / f"{arm}_{pair}_{side}", gates[arm], variant, side,
                                                  saved[(arm, side)])
    return SimpleNamespace(tmp=tmp, files=files, gates=gates, saved=saved, folders=folders, nets=nets)


@pytest.fixture
def use_world(world, monkeypatch):
    """The scorer reads the fixture's gate files in place of the committed ones (route 1 and both arms, both pairs)."""
    monkeypatch.setattr(unseen, "ROUTE1_GATES", world.files["route1"])
    for arm in ARMS:
        for pair in PAIRS:
            monkeypatch.setitem(reader.GATE_FILES[arm], pair, world.files[arm])
    return world


def manifest(path: Path, world, teams=None, replace: dict | None = None, extra: str = "") -> Path:
    """A manifest naming route 1's two folders and ``teams`` [(arm, pair, side)] (default all eight); ``replace``
    {key: folder} swaps a folder (key ("route1", side) or (arm, pair, side))."""
    replace = replace or {}
    teams = teams if teams is not None else [(a, p, s) for a in ARMS for p in PAIRS for s in SIDES]
    lines = ["[route1]"] + [f'{s} = "{replace.get(("route1", s), world.folders[("route1", s)])}"' for s in SIDES]
    for arm in ARMS:
        for pair in PAIRS:
            mine = [s for (a, p, s) in teams if (a, p) == (arm, pair)]
            if mine:
                lines.append(f"[{arm}.{pair}]")
                lines += [f'{s} = "{replace.get((arm, pair, s), world.folders[(arm, pair, s)])}"' for s in mine]
    path.write_text("\n".join(lines) + "\n" + extra)
    return path


# ------------------------------------------------------------------------------------------------ the scores
def test_route_team_v_velocity_team_plays_both_held_12(use_world, tmp_path, monkeypatch):
    """Every route team plays one cell against the other side's route 1 team in one ``play_cells`` call: the route team
    as the learner (a ``SkillTeam``), route 1's as a named player (a ``LearnerTeam``), both wrapped in ``HeldPlayer``
    with the gate files' hold (12), on the CPU; results.json holds one row per team, its counts equal to the saved
    per-game file and to a direct ``play_cells`` call on independently built teams, ``complete`` last."""
    w = use_world
    for g in w.gates.values():
        assert int(g.trainer["decision_ticks"]) == HOLD
    calls, held = [], []
    real_play, real_held = exploit.play_cells, exploit.HeldPlayer

    def spy(*args, **kw):
        calls.append((args, kw))
        held.append([])
        return real_play(*args, **kw)

    class Held(real_held):
        def __init__(self, inner, hold_ticks):
            held[-1].append((type(inner).__name__, int(hold_ticks)))
            super().__init__(inner, hold_ticks)

    monkeypatch.setattr(exploit, "play_cells", spy)
    monkeypatch.setattr(exploit, "HeldPlayer", Held)
    out = tmp_path / "out"
    assert unseen.main(["--manifest", str(manifest(tmp_path / "m.toml", w)), "--out", str(out)]) == 0

    assert len(calls) == len(ARMS) * len(PAIRS) * len(SIDES)
    for (args, kw), pair_held in zip(calls, held):
        cells = args[3]
        assert len(cells) == 1 and exploit.EXPLOITER in cells[0]
        side = "guard" if cells[0][0] == exploit.EXPLOITER else "strike"
        name = cells[0][1 if side == "guard" else 0]
        assert name == f"route1:{other(side)}"
        assert kw["hold_ticks"] == HOLD and args[5] == "cpu"
        assert isinstance(kw["learner"], exploit.SkillTeam) and kw["learner"].team == side
        assert list(kw["players"]) == [name] and isinstance(kw["players"][name], exploit.LearnerTeam)
        assert kw["players"][name].team == other(side)
        assert sorted(pair_held) == [("LearnerTeam", HOLD), ("SkillTeam", HOLD)]

    res = json.loads((out / "results.json").read_text())
    assert list(res)[-1] == "complete" and res["complete"] is True and res["label"] == "INFO"
    assert all(v["status"] == scoring.PASS for v in json.loads((out / "controls.json").read_text()).values())
    n = int(w.gates["route1"].run["eval_games"])
    rows = {(r["arm"], r["pair"], r["side"]): r for r in res["teams"]}
    assert set(rows) == {(a, p, s) for a in ARMS for p in PAIRS for s in SIDES}
    for (arm, pair, side), r in rows.items():
        with np.load(out / r["games_file"]) as z:
            won = z["outcome"] == (GUARD_WIN if side == "guard" else STRIKE_WIN)
        assert len(won) == n and r["n"] == n and r["k"] == int(won.sum())
        assert r["opponent"]["name"] == f"route1:{other(side)}" and r["variant"] == VARIANT[(arm, pair)]
        assert r["pooled"]["members"] == [r["opponent"]["name"]] and r["pooled"]["cells"][r["opponent"]["name"]]["k"] \
            == r["k"]
    for pair in PAIRS:
        for side in SIDES:
            assert res["paired"][pair][side]["n"] == n and res["paired"][pair][side]["label"] == "INFO"

    # the route 3 Guard team of pair s2 against route 1's Strike team, built here independently of the scorer
    g3, g1 = w.gates["route3"], w.gates["route1"]
    variant = VARIANT[("route3", "s2")]
    cfg = exploit.variant_cfg(g3, variant)
    d = skills.two_level_dispatch(g3.learner, g3.players, "guard", cfg, n, "cpu",
                                  int(g3.variants[variant]["train_seed"]["guard"]))
    mine = exploit_train.skill_team_from_modules("guard", w.saved[("route3", "guard")], list(g3.trainer["hidden"]),
                                                 d, "cpu")
    vel = exploit_train.team_from_modules("strike", w.saved[("route1", "strike")], list(g1.trainer["hidden"]), "cpu")
    ref = exploit.load_reference(exploit.ROOT / g3.reference["file"])
    def direct(hold):
        return real_play(cfg, g3.run["size"], ref, [(exploit.EXPLOITER, "route1:strike")], n, "cpu",
                         int(ref.meta["seed"]), int(g3.run["ticks_cap"]), learner=mine, hold_ticks=hold,
                         players={"route1:strike": vel})

    held_12, held_1 = direct(HOLD), direct(1)
    with np.load(out / rows[("route3", "s2", "guard")]["games_file"]) as z:
        for key in ("outcome", "end_step", "tags", "strikes_left", "closest_3d_m"):
            assert np.array_equal(z[key], held_12[key]), key
        assert not np.array_equal(z["closest_3d_m"], held_1["closest_3d_m"])     # the hold reaches the game


def test_a_failed_control_exits_6_and_publishes_no_score(use_world, tmp_path, monkeypatch):
    def failing(pg, ref, n, phase, suffix=""):
        return {f"ctl_paired_starts{suffix}": {"status": scoring.FAIL, "phase": phase, "detail": "test"}}

    monkeypatch.setattr(unseen.scoring, "plumbing_controls", failing)
    out = tmp_path / "out"
    m = manifest(tmp_path / "m.toml", use_world, teams=[("route3", "s1", "guard")])
    assert unseen.main(["--manifest", str(m), "--out", str(out)]) == 6
    assert (out / "controls.json").is_file() and not (out / "results.json").exists()


# ------------------------------------------------------------------------------------------------ the refusals
def _velocity_folder_holding(world, tmp: Path, route: str) -> Path:
    """A route 1 Guard folder whose results.json is the velocity run's and whose agent_final.pt is ``route``'s."""
    folder = tmp / "route1_guard_swapped"
    shutil.copytree(world.folders[("route1", "guard")], folder)
    torch.save(world.saved[(route, "guard")], folder / "agent_final.pt")
    return folder


def _arm_swapped(world, tmp: Path, arm: str, saved_of: str) -> Path:
    """A ``arm`` s1 Guard folder whose agent_final.pt is ``saved_of``'s Guard checkpoint."""
    folder = tmp / f"{arm}_s1_guard_swapped"
    shutil.copytree(world.folders[(arm, "s1", "guard")], folder)
    torch.save(world.saved[(saved_of, "guard")], folder / "agent_final.pt")
    return folder


@pytest.mark.parametrize("case", ["skills_folder_as_route1", "skills_checkpoint_in_route1", "route1_gates_skills",
                                  "net_checkpoint_in_route1", "velocity_checkpoint_in_route2",
                                  "route2_checkpoint_in_route3", "route3_checkpoint_in_route2"])
def test_a_velocity_checkpoint_from_a_skills_folder_is_refused(use_world, tmp_path, monkeypatch, capsys, case):
    """Route 1 is the velocity route, by its gate file, its results.json and its checkpoint; each route team's checkpoint
    is its own arm's (the skill lists and the network sha256 it carries): every mix exits 2 before a game is played,
    and nothing is written."""
    w = use_world
    replace, want = {}, None
    if case == "skills_folder_as_route1":
        replace[("route1", "guard")], want = w.folders[("route2", "s1", "guard")], "gate sha256"
    elif case == "skills_checkpoint_in_route1":
        replace[("route1", "guard")], want = _velocity_folder_holding(w, tmp_path, "route2"), "mixed-route"
    elif case == "net_checkpoint_in_route1":
        replace[("route1", "guard")], want = _velocity_folder_holding(w, tmp_path, "route3"), "mixed-route"
    elif case == "route1_gates_skills":
        monkeypatch.setattr(unseen, "ROUTE1_GATES", w.files["route2"])
        want = "velocity route"
    elif case == "velocity_checkpoint_in_route2":
        replace[("route2", "s1", "guard")], want = _arm_swapped(w, tmp_path, "route2", "route1"), "mixed-route"
    elif case == "route2_checkpoint_in_route3":
        replace[("route3", "s1", "guard")], want = _arm_swapped(w, tmp_path, "route3", "route2"), "skill lists"
    else:
        replace[("route2", "s1", "guard")], want = _arm_swapped(w, tmp_path, "route2", "route3"), "skill lists"
    played = []
    monkeypatch.setattr(exploit, "play_cells", lambda *a, **k: played.append(1))
    out = tmp_path / "out"
    assert unseen.main(["--manifest", str(manifest(tmp_path / "m.toml", w, replace=replace)), "--out", str(out)]) == 2
    err = capsys.readouterr().err
    assert want in err, err
    assert not played and not out.exists()


def test_an_edited_network_is_refused_before_a_game(use_world, tmp_path, monkeypatch, capsys):
    """A route 3 gate file whose network file was changed after it was hashed (C5, ``skill_net.net_problems`` through
    the driver's ``net_file_problems``): exit 2, nothing played or written."""
    w = use_world
    nets = {}
    for side, (path, sha) in w.nets.items():
        copy = tmp_path / "nets" / Path(path).name
        copy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, copy)
        nets[side] = (copy, sha)
    gates_file, _ = H.net_gate_file(tmp_path / "g", nets=nets, heads_shape=True)
    nets["guard"][0].write_bytes(nets["guard"][0].read_bytes() + b"edited")
    g = exploit.load_gates(gates_file)
    for pair in PAIRS:
        monkeypatch.setitem(reader.GATE_FILES["route3"], pair, gates_file)
    folder = make_run(tmp_path / "r3", g, "base", "guard", w.saved[("route3", "guard")])
    played = []
    monkeypatch.setattr(exploit, "play_cells", lambda *a, **k: played.append(1))
    m = manifest(tmp_path / "m.toml", w, teams=[("route3", "s1", "guard")], replace={("route3", "s1", "guard"): folder})
    out = tmp_path / "out"
    assert unseen.main(["--manifest", str(m), "--out", str(out)]) == 2
    assert "skill network" in capsys.readouterr().err
    assert not played and not out.exists()


@pytest.mark.parametrize("case", ["typo", "no_team", "used_out", "not_finished"])
def test_a_bad_manifest_or_folder_is_refused(use_world, tmp_path, monkeypatch, case):
    w = use_world
    out = tmp_path / "out"
    teams, extra, replace = [("route2", "s1", "guard")], "", {}
    if case == "typo":
        extra = '[route3.s1]\ngaurd = "x"\n'
    elif case == "no_team":
        teams = []
    elif case == "used_out":
        out.mkdir()
        (out / "results.json").write_text("{}")
    else:
        folder = tmp_path / "r2"
        shutil.copytree(w.folders[("route2", "s1", "guard")], folder)
        (folder / jobs.EXIT_FILE).write_text("6\n")
        replace[("route2", "s1", "guard")] = folder
    played = []
    monkeypatch.setattr(exploit, "play_cells", lambda *a, **k: played.append(1))
    m = manifest(tmp_path / "m.toml", w, teams=teams, replace=replace, extra=extra)
    assert unseen.main(["--manifest", str(m), "--out", str(out)]) == 2
    assert not played
    assert not (out / "controls.json").exists()


# ------------------------------------------------------------------------------------------------ the score matrix
@pytest.mark.parametrize("route", ["route2", "route3"])
def test_score_matrix_still_refuses_skills_gate_files(world, tmp_path, route):
    """``scripts/ste_score_matrix.py`` (``require_velocity_learner``, its line 215) still refuses a skills player, the
    scripts route's and the skill network's alike: the route teams are scored here, not there."""
    folder = tmp_path / "player"
    folder.mkdir()
    shutil.copyfile(world.files[route], folder / "gates.toml")
    for name in ("agent_final.pt", "eval_final.npz"):
        (folder / name).write_bytes(b"not read")
    sha = {name: exploit.sha256_file(folder / name) for name in ("gates.toml", "agent_final.pt", "eval_final.npz")}
    s = {"player": {"dir": str(folder), "gates_sha256": sha["gates.toml"], "agent_sha256": sha["agent_final.pt"],
                    "eval_sha256": sha["eval_final.npz"], "variant": "base", "side": "guard"}}
    loaded, why = matrix.check_inputs(SimpleNamespace(), s)
    assert loaded is None and WHY_MATRIX in why and "ste_score_matrix" in why
