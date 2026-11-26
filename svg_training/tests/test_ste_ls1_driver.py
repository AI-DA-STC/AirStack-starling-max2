"""Route 3, stage LS1, task LS1-M4-T2: the training driver's untrained-team control under a skill network
(``scripts/ste_exploit_l012.py``; plan ste_learning/drafts/LS1_TASK_PLAN.md section 5, with the design check's
corrections).

Under ``[learner] skill_source = "net"`` the untrained two-level team flies "free" + the first drone skill through the
skill network, so its known answer is no longer a scripted cell: the driver appends a NET TWIN cell (a constant-choice
``SkillTeam`` on the same network, ``driver.net_twin``) to every batch that carries the untrained control (a run's
controls and final batches, run 0's controls batch, the pilot's evaluation and timing batches), and the control compares
the untrained team with it game for game. The scripts and velocity routes are untouched (``net_twin`` gives nothing).

The preflight refuses a missing or edited network before the run folder is touched, and reads the pilot as a check
(``driver.net_pilot_problem``): the pinned Strike recipe must be the pilot's, for Guard runs too, and the pilot's
measured rate at ``[trainer] num_games`` and this launch's cap must reach ``game_steps_per_run`` (run 0: less its
checkpoint reads); a pilot of another route is refused either way.

The gate files are the SMOKE file cut to variant base with the two-level table and tiny untrained networks
(``tests/_ste_ls1.net_gate_file``); the pilot runs on file A and the runs follow file B, filled from it (L0.12's FILL
steps). One test plays the LS1.4 heads gate file's shape (pool on, a second variant ``base_s2`` on the base reference
cells, a run 0 per variant). CPU only; no GPU job."""
import json
import sys

import numpy as np
import pytest

import _ste_ls1 as H
from _ste_ls1 import ROOT, SKILLS_GATES, net_gate_file
from _torch_threads import default_torch_threads  # noqa: F401  (autouse: CPU numerics at the default thread count)
from svg_training.ste import exploit, shared, skill_net, skills

sys.path.insert(0, str(ROOT / "scripts"))
import ste_exploit_l012 as driver  # noqa: E402

SMOKE = H.SMOKE_GATES
VELOCITY_GATES = ROOT / "configs" / "ste_l3" / "velocity_gates.toml"
SIDES = ("strike", "guard")
REACH_MIN = 0.9                         # run 0's mark in the test files (the smoke's 8 games; the twin reaches far less)
NOT_LAUNCHED = "nothing is launched"


@pytest.fixture(autouse=True)
def scratch_shared(tmp_path, monkeypatch):
    monkeypatch.setenv(shared.SHARED_ENV, str(tmp_path / "shared"))
    monkeypatch.setenv(shared.LEGACY_LOGS_ENV, "")


@pytest.fixture
def smoke_mark(monkeypatch):
    """A gate file with [run0] skills_reach_min loads only on 1,000 evaluation games; the smoke plays 8."""
    monkeypatch.setattr(exploit, "SKILLS_RUN0_EVAL_GAMES", 8)


def run0_json(folder, gates_file, variant=None):
    """A skills run 0 stand-in (PASS, this gate file, its [learner] table): a Strike run of record reads it."""
    g = exploit.load_gates(gates_file)
    path = folder / "run0.json"
    path.write_text(json.dumps({"status": "PASS", "complete": True, "cap_h": 1.0, "gates_sha256": g.sha256,
                                "learner": skills.learner_table(g.learner), "variant": variant}))
    return path


def run(gates_file, run_dir, side, pilot, *extra, variant="base"):
    r0 = ["--run0-json", str(run0_json(run_dir.parent, gates_file, variant))] if side == "strike" else []
    return driver.main(["--gates", str(gates_file), "--variant", variant, "--side", side, "--run-dir", str(run_dir),
                        "--cap-h", "1", "--pilot-json", str(pilot), *r0, *extra])


def run0(gates_file, run_dir, pilot, *extra):
    return driver.main(["--run0", "--gates", str(gates_file), "--run-dir", str(run_dir), "--cap-h", "1", "--no-videos",
                        "--pilot-json", str(pilot), *extra])


@pytest.fixture(scope="module")
def net_runs(tmp_path_factory):
    """The real sequence on the CPU under a skill network: the pilot on gate file A, B filled from it, a run of record
    on each side (the Guard run makes its clip, the Strike run does not) and run 0 (on B with its mark)."""
    tmp = tmp_path_factory.mktemp("ls1_driver")
    mp = pytest.MonkeyPatch()
    mp.setenv(shared.SHARED_ENV, str(tmp / "shared"))
    mp.setenv(shared.LEGACY_LOGS_ENV, "")
    a, nets = net_gate_file(tmp / "a")
    batches, play_cells = [], exploit.play_cells

    def spy(cfg, size, ref, cells, *args, **kw):            # the pilot's batches: their cells and twin players
        batches.append((list(cells), dict(kw.get("players") or {})))
        return play_cells(cfg, size, ref, cells, *args, **kw)
    mp.setattr(exploit, "play_cells", spy)
    assert driver.main(["--pilot", "--gates", str(a), "--run-dir", str(tmp / "pilot"), "--cap-h", "1"]) == 0
    mp.setattr(exploit, "play_cells", play_cells)
    pilot = tmp / "pilot" / "pilot.json"
    fill = json.loads(pilot.read_text())["strike_recipe"]["side_overrides_strike"]
    b, _ = net_gate_file(tmp / "b", nets=nets, strike_recipe=fill)
    assert exploit.load_gates(b).trainer["side_overrides"]["strike"] == fill
    out = {"a": a, "b": b, "nets": nets, "pilot": pilot, "fill": fill, "codes": {}, "pilot_batches": batches}
    for side in SIDES:
        r = tmp / side
        out["codes"][side] = run(b, r, side, pilot, *(() if side == "guard" else ("--no-videos",)))
        out[side] = r
    mp.setattr(exploit, "SKILLS_RUN0_EVAL_GAMES", 8)
    r0_file, _ = net_gate_file(tmp / "r0", nets=nets, strike_recipe=fill, reach_min=REACH_MIN)
    out["run0_file"], out["run0"] = r0_file, tmp / "run0"
    out["codes"]["run0"] = run0(r0_file, out["run0"], pilot)
    mp.undo()
    return out


def twin_index(gates, side):
    """The net twin's cell is the last of the batch (appended after eval_cells)."""
    return len(exploit.eval_cells(gates, "base", side))


# ================================================================================================ the twin
def test_net_untrained_team_equals_its_net_twin_and_every_control_passes(net_runs):
    assert net_runs["codes"] == {"strike": 0, "guard": 0, "run0": 0}
    g = exploit.load_gates(net_runs["b"])
    n = int(g.run["eval_games"])
    for side in SIDES:
        r = net_runs[side]
        controls = json.loads((r / "controls.json").read_text())
        assert all(c["status"] == "PASS" for c in controls.values()), controls
        twin_ctl = controls["ctl_untrained_is_first_skill"]
        assert driver.NET_TWIN in twin_ctl["detail"] and g.learner.drone_skills[side][0] in twin_ctl["detail"]
        k = twin_index(g, side)
        for npz in ("eval_before.npz", "eval_final.npz"):
            assert len(np.load(r / npz)["outcome"]) == (k + 1) * n, (side, npz)     # the twin cell, appended last
        before = np.load(r / "eval_before.npz")
        for key in ("outcome", "end_step", "tags"):
            assert np.array_equal(before[key][:n], before[key][k * n:(k + 1) * n]), (side, key)
        res = json.loads((r / "results.json").read_text())
        assert res["learner"]["skill_source"] == "net" and res["complete"] is True
        twin = [c for c in res["cells"] if driver.NET_TWIN in c]
        assert len(twin) == 1, res["cells"]
    clips = json.loads((net_runs["guard"] / "results.json").read_text())["videos"]
    assert clips and clips[0].startswith("videos/"), clips                       # STANDARDS section 8, net-flown


def test_the_check_is_not_vacuous(net_runs):
    """The untrained net team's cell differs from the scripts' first-skill cell (same opponent, same starts) in at
    least one game on each side: equal to its twin is a statement about the network, not about the script."""
    g = exploit.load_gates(net_runs["b"])
    n = int(g.run["eval_games"])
    for side in SIDES:
        before = np.load(net_runs[side] / "eval_before.npz")
        cells = exploit.eval_cells(g, "base", side)
        first = g.learner.drone_skills[side][0]
        k = cells.index([c for c in cells if first in c][0])
        differ = np.zeros(n, dtype=bool)
        for key in ("outcome", "end_step", "tags"):
            differ |= before[key][:n] != before[key][k * n:(k + 1) * n]
        assert differ.sum() > 0, side


@pytest.mark.parametrize("side", SIDES)
def test_a_twin_of_another_code_fails_exit_6(net_runs, tmp_path, monkeypatch, side):
    """A twin flying the second drone skill is not the untrained team: the control fails, exit 6 (CONTROL_FAILED)
    before any training."""
    monkeypatch.setattr(driver, "NET_TWIN_DRONE_SKILL", 1)
    r = tmp_path / "run"
    assert run(net_runs["b"], r, side, net_runs["pilot"], "--no-videos") == 6
    ctl = json.loads((r / "controls.json").read_text())["ctl_untrained_is_first_skill"]
    second = exploit.load_gates(net_runs["b"]).learner.drone_skills[side][1]
    assert ctl["status"] == "FAIL" and second in ctl["detail"]
    assert not (r / "results.json").exists() and not (r / "train_log.jsonl").exists()


def test_net_run0_controls_pass_with_the_net_twin(net_runs, smoke_mark):
    r = net_runs["run0"]
    controls = json.loads((r / "controls.json").read_text())
    assert all(c["status"] == "PASS" for c in controls.values()), controls
    assert driver.NET_TWIN in controls["ctl_untrained_is_first_skill"]["detail"]
    assert controls["ctl_untrained_below_mark"]["status"] == "PASS"
    out = json.loads((r / driver.RUN0_FILE).read_text())
    g = exploit.load_gates(net_runs["run0_file"])
    assert out["complete"] is True and out["learner"] == skills.learner_table(g.learner)
    assert out["learner"]["skill_net_sha256"] == {s: net_runs["nets"][s][1] for s in ("guard", "strike")}


def test_net_pilot_records_the_net_learner(net_runs):
    p = json.loads(net_runs["pilot"].read_text())
    g = exploit.load_gates(net_runs["a"])
    assert p["learner"] == skills.learner_table(g.learner) and p["learner"]["skill_source"] == "net"
    for side in SIDES:
        ev = p["eval"]["per_side"][side]
        assert ev["cells"] == twin_index(g, side) + 1
        ctl = ev["controls"]["ctl_untrained_is_first_skill"]
        assert ctl["status"] == "PASS" and driver.NET_TWIN in ctl["detail"]
    assert driver.net_pilot_problem(exploit.load_gates(net_runs["b"]), p, "guard", 1.0) is None
    # the twin is in pilot step 1 (each side) and in every timing batch; never in an INFO batch or the run 0 read
    twinned = [(cells, players) for cells, players in net_runs["pilot_batches"]
               if any(driver.NET_TWIN in str(x) for c in cells for x in c)]
    assert len(twinned) == len(exploit.SIDES) + len(g.pilot["timing_batches"])
    assert all(set(players) == {x for c in cells for x in c if x.startswith(driver.NET_TWIN)}
               for cells, players in twinned)
    assert driver.net_pilot_problem(exploit.load_gates(net_runs["b"]), p, "strike", 1.0, run0=True) is None


def test_scripts_route_cells_and_players_unchanged():
    """``net_twin`` gives no cell and no player for the scripts route, the velocity route and the SMOKE file."""
    for path in (SKILLS_GATES, VELOCITY_GATES, SMOKE):
        g = exploit.load_gates(path)
        cfg = exploit.variant_cfg(g, "base")
        for side in SIDES:
            opp = exploit.opponent_of(g, "base", side)
            assert driver.net_twin(g, side, opp, cfg, 2, "cpu", 0) == ([], {}), (path.name, side)
    for path in (SKILLS_GATES, SMOKE):
        assert driver.net_pilot_problem(exploit.load_gates(path), {}, "strike", 1.0) is None


def test_net_pilot_problem_is_none_for_the_scripts_route_with_route_2s_pilot_shape():
    """Route 2's L3.3 pilot.json (its keys; the recipe deliberately not the gate's and no rate point) is never read
    by the net check: the scripts route keeps today's preflight."""
    g = exploit.load_gates(SKILLS_GATES)
    route2 = {"machine": {}, "device": "cuda", "gates_sha256": "0" * 64, "eval": {"per_side": {}}, "timing": [],
              "probes": [], "points": [], "learner": skills.learner_table(g.learner),
              "strike_recipe": {"recipe": "other", "side_overrides_strike": {"shaping_weight": 1.0}},
              "run0_read_s": 1.0, "projection": [], "plan_hours": []}
    for side in SIDES:
        assert driver.net_pilot_problem(g, route2, side, 1.0) is None
        assert driver.net_pilot_problem(g, route2, side, 1.0, run0=True) is None


# ================================================================================================ the preflight
@pytest.mark.parametrize("mode", ["run", "--pilot", "--run0"])
@pytest.mark.parametrize("fault", ["missing", "edited", "other_game"])
@pytest.mark.parametrize("side", ["strike", "guard"])
def test_preflight_refuses_a_missing_or_edited_net_exit_2(net_runs, tmp_path, capsys, mode, fault, side):
    """Either side's network: missing, edited after its sha256 was pinned, or made on another game file (its meta's
    game_sha256: the one check C5 leaves to the driver's preflight)."""
    nets = dict(net_runs["nets"])
    path, sha = nets[side]
    if fault == "missing":
        nets[side] = (str(tmp_path / "nowhere" / f"skill_net_{side}.pt"), sha)
        why = "missing file"
    elif fault == "edited":
        edited = tmp_path / "edited" / f"skill_net_{side}.pt"
        edited.parent.mkdir()
        edited.write_bytes(path.read_bytes() + b"\0")
        nets[side] = (str(edited), sha)
        why = "file sha256"
    else:
        scripts = tmp_path / "scripts_gates.toml"
        scripts.write_text(H.smoke_two_level_text())
        meta = skill_net.read_skill_net_meta(path)
        meta = {**{k: meta[k] for k in skill_net.META_KEYS}, "game_sha256": "0" * 64}
        other = tmp_path / "other_game" / f"skill_net_{side}.pt"
        net = H.tiny_net(side, gates=exploit.load_gates(scripts), seed=H.NET_SEED)
        nets[side] = (str(other), skill_net.save_skill_net(other, net, meta))
        why = "game_sha256"
    g, _ = net_gate_file(tmp_path / "g", nets=nets, strike_recipe=net_runs["fill"])
    r = tmp_path / "run"
    head = ["--variant", "base", "--side", "guard", "--pilot-json", str(net_runs["pilot"])] if mode == "run" else \
        [mode] + (["--pilot-json", str(net_runs["pilot"])] if mode == "--run0" else [])
    assert driver.main(head + ["--gates", str(g), "--run-dir", str(r), "--cap-h", "1"]) == 2
    err = capsys.readouterr().err
    assert why in err and "skill network" in err and f"skill_net_{side}.pt" in err, err
    assert not r.exists()


def hand_pilot(gates_file, *, recipe, eval_s=384.0, rate=1.0, per_update=96, run0_read_s=0.0, points=None):
    """A hand-made net pilot.json (the route's [learner] table; ``recipe`` as the Strike recipe it picked). With
    eval_s 384 the smoke trainer's final reserve is 2 x (2 x 384 + 120) = 1,776 s, so a 1 h cap leaves
    3,600 - 1,776 - 384 = 1,440 s of training: exactly the smoke's 1,440 game-steps at 1 game-step per second."""
    g = exploit.load_gates(gates_file)
    n = int(g.trainer["num_games"])
    if points is None:
        points = [{"side": s, "num_games": n, "updates": 2, "game_steps": 2 * per_update, "seconds": 2 * per_update / rate,
                   "game_steps_per_s": rate} for s in SIDES]
    data = {"learner": skills.learner_table(g.learner), "strike_recipe": {"side_overrides_strike": recipe},
            "eval": {"per_side": {s: {"seconds": eval_s} for s in SIDES}}, "points": points,
            "run0_read_s": run0_read_s}
    return data


def test_the_projection_arithmetic_at_the_boundary(net_runs):
    g = exploit.load_gates(net_runs["b"])
    fill = net_runs["fill"]
    assert exploit.final_reserve_s(g.trainer, 384.0) == 1776.0 and int(g.trainer["game_steps_per_run"]) == 1440
    for side in SIDES:
        assert driver.net_pilot_problem(g, hand_pilot(net_runs["b"], recipe=fill), side, 1.0) is None     # 1,440
        short = driver.net_pilot_problem(g, hand_pilot(net_runs["b"], recipe=fill, rate=1439 / 1440), side, 1.0)
        assert short is not None and NOT_LAUNCHED in short and "game-steps" in short
    # run 0 also spends time on its checkpoint reads: 15 updates of 96 s fit 1,440 s without reads, 14 with 1 s reads
    assert driver.net_pilot_problem(g, hand_pilot(net_runs["b"], recipe=fill), "strike", 1.0, run0=True) is None
    slow = driver.net_pilot_problem(g, hand_pilot(net_runs["b"], recipe=fill, run0_read_s=1.0), "strike", 1.0,
                                    run0=True)
    assert slow is not None and NOT_LAUNCHED in slow and "run 0" in slow
    assert driver.net_pilot_problem(g, hand_pilot(net_runs["b"], recipe=fill, run0_read_s=1.0), "strike", 1.0) is None


def test_a_pilot_with_another_recipe_or_too_few_game_steps_is_refused_exit_2(net_runs, tmp_path, capsys, monkeypatch):
    b, fill = net_runs["b"], net_runs["fill"]
    other = {"shaping_weight": 1.0} if not fill else {}
    n = int(exploit.load_gates(b).trainer["num_games"])
    cases = {
        "recipe": hand_pilot(b, recipe=other),
        "short": hand_pilot(b, recipe=fill, rate=1439 / 1440),
        "run0_reads": hand_pilot(b, recipe=fill, run0_read_s=1.0),
        "did_not_fit": hand_pilot(b, recipe=fill, points=[{"side": s, "num_games": n, "did_not_fit": "out of memory"}
                                                          for s in SIDES]),
        "no_point": hand_pilot(b, recipe=fill, points=[{"side": s, "num_games": 2 * n, "updates": 2,
                                                        "game_steps": 192, "seconds": 192.0, "game_steps_per_s": 1.0}
                                                       for s in SIDES]),
    }
    monkeypatch.setattr(exploit, "SKILLS_RUN0_EVAL_GAMES", 8)
    r0_file = net_runs["run0_file"]
    for name, data in cases.items():
        pj = tmp_path / f"{name}.json"
        pj.write_text(json.dumps(data))
        launches = [("run0", r0_file)] if name == "run0_reads" else [("guard", b), ("strike", b), ("run0", r0_file)]
        for kind, gates_file in launches:
            r = tmp_path / f"{name}_{kind}"
            code = run0(gates_file, r, pj) if kind == "run0" else run(gates_file, r, kind, pj, "--no-videos")
            err = capsys.readouterr().err
            assert code == 2 and NOT_LAUNCHED in err, (name, kind, err)
            assert not r.exists(), (name, kind)
        if name == "run0_reads":                     # the same pilot launches the runs of record (no reads there)
            assert driver.net_pilot_problem(exploit.load_gates(b), data, "guard", 1.0) is None


def test_a_scripts_pilot_is_refused_for_a_net_gate_file_exit_2(net_runs, tmp_path, capsys, monkeypatch):
    """A pilot of the scripts route is refused for a net gate file (a run of record and run 0), and the net pilot for
    the scripts gate file of the same text: the [learner] tables differ by the route's source and the networks' shas
    (``skills_pilot_problem``). Nothing is written in the run folder."""
    monkeypatch.setattr(exploit, "SKILLS_RUN0_EVAL_GAMES", 8)
    fill = net_runs["fill"]
    scripts_b = tmp_path / "scripts_gates.toml"
    scripts_b.write_text(H.smoke_two_level_text(strike_recipe=fill))
    scripts_r0 = tmp_path / "scripts_run0_gates.toml"
    scripts_r0.write_text(H.smoke_two_level_text(reach_min=REACH_MIN, strike_recipe=fill))
    scripts_pilot = tmp_path / "scripts_pilot.json"
    scripts_pilot.write_text(json.dumps({**json.loads(net_runs["pilot"].read_text()),
                                         "learner": skills.learner_table(exploit.load_gates(scripts_b).learner)}))
    for gates_file, r0_file, pilot in ((net_runs["b"], net_runs["run0_file"], scripts_pilot),
                                       (scripts_b, scripts_r0, net_runs["pilot"])):
        for kind in ("guard", "strike", "run0"):
            r = tmp_path / f"{gates_file.stem}_{kind}"
            code = run0(r0_file, r, pilot) if kind == "run0" else run(gates_file, r, kind, pilot, "--no-videos")
            err = capsys.readouterr().err
            assert code == 2 and "skills pilot with the same [learner] table" in err, (gates_file.name, kind, err)
            assert not r.exists()


# ================================================================================================ the heads shape
def test_the_heads_shape_runs_a_second_variant_and_its_run0(net_runs, tmp_path, smoke_mark):
    """LS1.4's heads gate file combines a net, [pool] on, a second variant on the base reference cells
    (reference_variant "base") and a run 0 per variant: a base_s2 Guard run and a base_s2 run 0 end with exit 0, their
    reference replays PASS against base's cells, and run 0 trains base_s2's own run0_seed."""
    g_file, _ = net_gate_file(tmp_path / "heads", nets=net_runs["nets"], strike_recipe=net_runs["fill"],
                              reach_min=REACH_MIN, heads_shape=True)
    g = exploit.load_gates(g_file)
    assert g.pool["enabled"] and exploit.ref_variant(g, H.SECOND_VARIANT) == "base" and g.run0["per_variant"]
    guard = tmp_path / "guard"
    assert run(g_file, guard, "guard", net_runs["pilot"], "--no-videos", variant=H.SECOND_VARIANT) == 0
    controls = json.loads((guard / "controls.json").read_text())
    assert all(c["status"] == "PASS" for c in controls.values()), controls
    res = json.loads((guard / "results.json").read_text())
    assert res["variant"] == H.SECOND_VARIANT and res["train_seed"] == H.SECOND_SEEDS["guard"]
    assert res["trained_against"].startswith("OpponentPool")
    r0 = tmp_path / "run0"
    assert run0(g_file, r0, net_runs["pilot"], "--variant", H.SECOND_VARIANT) == 0
    out = json.loads((r0 / driver.RUN0_FILE).read_text())
    assert out["variant"] == H.SECOND_VARIANT and out["train_seed"] == H.SECOND_RUN0_SEED and out["per_variant"]
    controls = json.loads((r0 / "controls.json").read_text())
    assert all(c["status"] == "PASS" for c in controls.values()), controls
    assert driver.NET_TWIN in controls["ctl_untrained_is_first_skill"]["detail"]
