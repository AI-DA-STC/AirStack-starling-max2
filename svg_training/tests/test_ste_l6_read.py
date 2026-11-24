"""STE L3-L6 pipeline check, task L6.1: the per-route reads and the route comparison (``scripts/ste_l6_read.py``,
``ste/compare.py``; spec ste_learning/drafts/L3_L6_PIPELINE_SPEC.md section 3).

Synthetic run folders with known answers (no training): the route words (PIPELINE WORKS / RUN 0 FAILED / RUN 0
INCONCLUSIVE / DOES NOT WORK at <stage> naming the first failing control), the separate reads (ATTRIBUTION NOT READ,
HELD ARM NOT READ, COMPARISON NOT READ without a passing L4.2), the comparison's numbers (the worst cell without the
z_up_info cells, paired same-cell differences, the pooled row, the best single fixed choice, the choice shares), the
refusals (states section 3 does not word, contradictions, folders not on the same starts) and the fixed wording."""
import json
import sys

import numpy as np
import pytest

from svg_training.core.rewards import GUARD_WIN, RUNNING, STRIKE_WIN
from svg_training.ste import compare, exploit, jobs, pool, scoring

from _ste_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import ste_l6_read as reader  # noqa: E402

N = 60
CFG = exploit.ROOT / "configs" / "ste_l3"
GATES = {name: exploit.load_gates(CFG / f"{name}_gates.toml")
         for name in ("velocity", "skills", "velocity_poolonly", "skills_poolonly")}


# ------------------------------------------------------------------------------------------- the numbers (compare.py)
def test_paired_difference_reads_above_where_the_two_wilson_intervals_overlap():
    """The same 200 starts: B wins on 100, A on those 100 and 20 more (0.6 v 0.5). The two Wilson intervals overlap
    (the worst-cell rule reads "not distinguishable"); the paired interval excludes 0."""
    n = 200
    b = np.zeros(n, dtype=bool)
    b[:100] = True
    a = b.copy()
    a[100:120] = True
    assert compare.intervals_word(scoring.rate(a.sum(), n)["ci"], scoring.rate(b.sum(), n)["ci"]) == \
        "not distinguishable"
    d = compare.paired_difference(a, b)
    assert d["diff"] == pytest.approx(0.1) and d["ci"][0] > 0 and d["word"] == "above"
    assert compare.paired_difference(b, a)["word"] == "below"


def test_a_zero_width_interval_at_zero_is_not_distinguishable():
    a = np.array([True, False] * 10)
    d = compare.paired_difference(a, a.copy())
    assert d["se"] == 0.0 and d["ci"] == [0.0, 0.0] and d["word"] == "not distinguishable"


def test_the_headline_worst_cell_leaves_out_the_z_up_info_cells():
    wins = {"strike_straight": np.ones(N, bool), "strike_high": np.zeros(N, bool), "strike_flank": np.ones(N, bool)}
    wins["strike_flank"][:10] = False
    h = compare.headline(wins, ["strike_high", "strike_low"])
    assert h["worst"]["opponent"] == "strike_flank" and h["worst"]["k"] == N - 10
    assert list(h["z_up_info_cells"]) == ["strike_high"] and h["z_up_info_cells"]["strike_high"]["k"] == 0


def test_an_unfinished_game_is_no_win():
    out = np.array([GUARD_WIN, RUNNING, STRIKE_WIN, GUARD_WIN])
    w = compare.wins_by_cell(out, ["a", "b"], 2, "guard")
    assert w["a"].tolist() == [True, False] and w["b"].tolist() == [False, True]
    assert compare.wins_by_cell(out, ["a", "b"], 2, "strike")["b"].tolist() == [True, False]


def test_the_overall_choice_share_weights_each_bin_by_its_decisions():
    entry = {"bins": ["0", "1"], "counts": [10, 30], "share": {"x": [1.0, 0.0], "y": [0.0, 1.0]}}
    assert compare.overall_share(entry) == {"x": 0.25, "y": 0.75}
    assert compare.overall_share({"bins": ["0"], "counts": [0], "share": {"x": [None]}}) == {"x": None}


# ----------------------------------------------------------------------------------------------- synthetic run folders
def opponents(side):
    return list(GATES["velocity"].players["strikes" if side == "guard" else "guards"])


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj))


def wins_rows(side, rates, seed):
    """A win indicator per opponent cell, ``rates`` {opponent: rate} (default 0.5), deterministic."""
    rng = np.random.default_rng(seed)
    return {o: rng.random(N) < rates.get(o, 0.5) for o in opponents(side)}


def make_main(folder, gates_name, side, wins, exit_code=0, controls=None, choice=None, pooled_off=0.0, **extra):
    gates = GATES[gates_name]
    won, lost = (GUARD_WIN, STRIKE_WIN) if side == "guard" else (STRIKE_WIN, GUARD_WIN)
    opps = opponents(side)
    outcome = np.concatenate([np.where(wins[o], won, lost) for o in opps]).astype(np.int64)
    folder.mkdir(parents=True)
    np.savez_compressed(folder / "eval_info.npz", outcome=outcome)
    (folder / "agent_final.pt").write_bytes(f"networks of {folder.name}".encode())
    (folder / jobs.EXIT_FILE).write_text(f"{exit_code}\n")
    ctl = {"ctl_reference_replay_final": {"status": "PASS"}, "ctl_paired_starts_info": {"status": "PASS"}}
    ctl.update(controls or {})
    write(folder / "controls.json", ctl)
    if exit_code != 0:
        return folder
    key = (lambda o: f"{o} v {exploit.EXPLOITER}") if side == "strike" else (lambda o: f"{exploit.EXPLOITER} v {o}")
    members = pool.pool_members(gates.players, "strike" if side == "guard" else "guard")
    res = {"complete": True, "side": side, "gates_sha256": gates.sha256, "eval_games": N, "budget_reached": True,
           "reference": {k: gates.reference[k] for k in ("file", "sha256", "start_sha256", "t44_gates_sha256")},
           "game_file": {"file": "configs/ste_l011/base.toml", "sha256": "g" * 8},
           "info": {key(o): {"games": N} for o in opps},
           "pooled": {"rate": float(np.mean([wins[o].mean() for o in members])) + pooled_off},
           "best_single_choice": {"best": "x"}}
    if choice is not None:
        res["choice_by_decision"] = choice
    res.update(extra)
    write(folder / "results.json", res)
    return folder


def make_pilot(folder, gates_name, exit_code=0, control="PASS"):
    ctl = {"ctl_reference_replay_pilot": {"status": control}}
    write(folder / "pilot.json", {"gates_sha256": GATES[gates_name].sha256,
                                  "eval": {"per_side": {"guard": {"controls": ctl}, "strike": {"controls": ctl}}}})
    (folder / "pilot.md").write_text("pilot\n")
    (folder / jobs.EXIT_FILE).write_text(f"{exit_code}\n")
    return folder


def make_run0(folder, gates_name, status, exit_code=0):
    write(folder / "learner_control.json",
          {"complete": True, "status": status, "gates_sha256": GATES[gates_name].sha256})
    write(folder / "controls.json", {"ctl_reference_replay": {"status": "PASS"}})
    (folder / jobs.EXIT_FILE).write_text(f"{exit_code}\n")
    return folder


def make_export(folder, route, side, run=None, exit_code=0):
    """An export folder stand-in (the reload itself is ``fake_reload``): schema, team, gate sha, the checkpoint's
    sha256 (of ``run``'s agent_final.pt), exit_code as scripts/ste_job.py writes it."""
    folder.mkdir(parents=True)
    sha = exploit.sha256_file(run / "agent_final.pt") if run is not None else "0" * 64
    (folder / "interface.toml").write_text(f'policy_schema = "ste-check-{route}-0"\nteam = "{side}"\n'
                                           f'gates_sha256 = "{GATES[route].sha256}"\n'
                                           f'source_checkpoint_sha256 = "{sha}"\n')
    (folder / jobs.EXIT_FILE).write_text(f"{exit_code}\n")
    return folder


def skill_choice(side):
    """A choice share per opponent cell: the first two skills of ``side``, 0.7 / 0.3 over all decisions."""
    a, b = GATES["skills"].players["strikes" if side == "strike" else "guards"][:2]
    return {o: {"bins": ["0", "1"], "counts": [6, 4], "share": {a: [0.5, 1.0], b: [0.5, 0.0]}} for o in opponents(side)}


@pytest.fixture
def fake_reload(monkeypatch):
    """The fresh-process reload check stands in: ok unless the folder holds a file named BROKEN."""
    def reload(folder):
        if (folder / "BROKEN").exists():
            return {"ok": False, "error": "golden rows: onnxruntime differs by 1.0e-02 (> 1e-06)"}
        return {"ok": True, "runtimes": ["onnxruntime", "onnx.reference"], "max_abs_diff": 0.0}
    monkeypatch.setattr(reader, "reload_in_a_fresh_process", reload)


def build(tmp, run0=("PASS", "PASS"), strike=(True, True), suite="PASS", poolonly=True, held="PASS", **over):
    """A whole pipeline-check folder set; ``over`` replaces manifest entries (route.key -> path or None)."""
    m = {}
    for i, route in enumerate(("velocity", "skills")):
        r = tmp / route
        e = {"pilot": make_pilot(r / "pilot", route), "run0": make_run0(r / "run0", route, run0[i]),
             "guard": make_main(r / "guard", route, "guard", wins_rows("guard", {}, 10 + i),
                                choice=skill_choice("guard") if route == "skills" else None),
             "export_guard": make_export(r / "export_guard", route, "guard", r / "guard")}
        if strike[i]:
            e["strike"] = make_main(r / "strike", route, "strike", wins_rows("strike", {}, 20 + i),
                                    choice=skill_choice("strike") if route == "skills" else None)
            e["export_strike"] = make_export(r / "export_strike", route, "strike", r / "strike")
        if poolonly:
            e["poolonly_guard"] = make_main(r / "poolonly", f"{route}_poolonly", "guard",
                                            wins_rows("guard", {}, 30 + i),
                                            choice=skill_choice("guard") if route == "skills" else None)
            if route == "skills":
                e["poolonly_pilot"] = make_pilot(r / "poolonly_pilot", "skills_poolonly")
        m[route] = {k: str(v) for k, v in e.items()}
    if suite is not None:                       # scripts/ste_l4_suite.py's file and ste_job.py's exit_code
        checks = {r: {s: {"ctl_best_single_choice": {"status": suite}} for s in ("guard", "strike")}
                  for r in ("velocity", "skills")}
        write(tmp / "suite" / "suite_check.json",
              {"complete": True, "status": suite, "games": GATES["velocity"].run["eval_games"], "checks": checks,
               "gates_sha256": {r: GATES[r].sha256 for r in ("velocity", "skills")}})
        (tmp / "suite" / jobs.EXIT_FILE).write_text("0\n" if suite == "PASS" else "6\n")
        m["suite_check"] = str(tmp / "suite" / "suite_check.json")
    if held is not None:                        # scripts/ste_l3_held_arm.py: exit 6 when its control failed
        write(tmp / "held" / "controls.json", {"ctl_hold_one_is_reference": {"status": held}})
        if held == "PASS":
            write(tmp / "held" / "results.json", {"complete": True})
        (tmp / "held" / jobs.EXIT_FILE).write_text("0\n" if held == "PASS" else "6\n")
        m["held_arm"] = str(tmp / "held")
    for key, value in over.items():
        route, k = key.split("__")
        if value is None:
            m[route].pop(k, None)
        else:
            m[route][k] = str(value)
    lines = []
    for k in ("suite_check", "held_arm"):
        if k in m:
            lines.append(f'{k} = "{m[k]}"')
    for route in ("velocity", "skills"):
        lines.append(f"[{route}]")
        lines += [f'{k} = "{v}"' for k, v in m[route].items()]
    path = tmp / "read.toml"
    path.write_text("\n".join(lines) + "\n")
    return path


def read(tmp, manifest):
    code = reader.main(["--manifest", str(manifest), "--out", str(tmp / "out")])
    out = json.loads((tmp / "out" / "read.json").read_text()) if code == 0 else None
    return code, out


# ---------------------------------------------------------------------------------------------- the words
def test_every_task_done_reads_pipeline_works_and_the_comparison_is_written(tmp_path, fake_reload):
    code, out = read(tmp_path, build(tmp_path))
    assert code == 0
    assert out["routes"]["velocity"]["word"] == "PIPELINE WORKS"
    assert out["routes"]["skills"]["word"] == "PIPELINE WORKS"
    assert out["status"] == "pipeline check, not for flight" and out["label"] == "INFO"
    for side, k in (("guard", 6), ("strike", 5)):
        c = out["comparison"][side]
        assert c["k"] == k and len(c["paired_cells"]) == k
        assert set(c["policies"]) == {"velocity", "skills"}
        assert c["paired_cells"][0]["opponent"] == c["policies"]["velocity"]["headline"]["worst"]["opponent"]
        for p in c["policies"].values():
            assert {"pooled", "against_best_single_choice", "headline"} <= set(p)
            assert p["against_best_single_choice"]["word"] in ("above", "below", "not distinguishable")
        assert c["pooled_difference"]["word"] in ("above", "below", "not distinguishable")
    assert out["comparison"]["strike"]["policies"]["skills"]["choice_share"]["guard_mirror"]["overall"] == \
        {"strike_straight": 0.7, "strike_flank": 0.3}
    assert out["attribution"]["velocity"]["word"] == "read" and out["held_arm"]["word"] == "read"
    text = (tmp_path / "out" / "read.md").read_text() + json.dumps(out)
    assert "these two trained policies" in text and "no held-out opponent" in text
    assert "the route" not in text.lower()
    z = {c["opponent"]: c for c in out["comparison"]["guard"]["paired_cells"]}
    assert z["strike_high"]["label"] == z["strike_low"]["label"] == "vertical response not fitted in tier 1"
    assert "label" not in z["strike_straight"]
    zc = out["comparison"]["guard"]["policies"]["velocity"]["headline"]["z_up_info_cells"]
    assert zc["strike_high"]["label"] == "vertical response not fitted in tier 1"
    assert "strike_high (vertical response not fitted in tier 1)" in (tmp_path / "out" / "read.md").read_text()
    assert "observed in the training simulator" in text


def test_run_0_failed_without_a_strike_run_reads_run_0_failed(tmp_path, fake_reload):
    code, out = read(tmp_path, build(tmp_path, run0=("FAIL", "PASS"), strike=(False, True)))
    assert code == 0 and out["routes"]["velocity"]["word"] == "PIPELINE WORKS, RUN 0 FAILED"
    assert out["comparison"]["strike"]["compared"] is False and "velocity" in out["comparison"]["strike"]["why"]
    assert out["comparison"]["guard"]["compared"] is True


def test_run_0_inconclusive_reads_its_word_and_the_contradictions_are_refused(tmp_path, fake_reload):
    code, out = read(tmp_path / "a", build(_mk(tmp_path / "a"), run0=("INCONCLUSIVE", "INCONCLUSIVE"),
                                           strike=(True, False)))
    assert code == 0
    assert out["routes"]["velocity"]["word"] == out["routes"]["skills"]["word"] == "PIPELINE WORKS, RUN 0 INCONCLUSIVE"
    assert reader.main(["--manifest", str(build(_mk(tmp_path / "b"), run0=("FAIL", "PASS"))),
                        "--out", str(tmp_path / "b" / "out")]) == 2               # run 0 FAIL, a Strike run present
    assert reader.main(["--manifest", str(build(_mk(tmp_path / "c"), run0=("PASS", "INCONCLUSIVE"))),
                        "--out", str(tmp_path / "c" / "out")]) == 2               # skills INCONCLUSIVE, a Strike run
    assert reader.main(["--manifest", str(build(_mk(tmp_path / "d"), strike=(True, False))),
                        "--out", str(tmp_path / "d" / "out")]) == 2               # run 0 PASS, no Strike run


def _mk(p):
    p.mkdir(parents=True, exist_ok=True)
    return p


def test_a_failed_control_reads_does_not_work_and_names_the_first_failing_control(tmp_path, fake_reload):
    bad = make_main(tmp_path / "bad", "skills", "guard", wins_rows("guard", {}, 3), exit_code=6,
                    controls={"ctl_untrained_is_first_skill_before": {"status": "FAIL"},
                              "ctl_trained_against": {"status": "FAIL"}})
    code, out = read(tmp_path, build(tmp_path, skills__guard=bad))
    assert code == 0
    assert out["routes"]["skills"]["word"] == "PIPELINE DOES NOT WORK at L5.2 skills Guard run"
    assert "ctl_untrained_is_first_skill_before" in out["routes"]["skills"]["why"]
    assert out["comparison"]["guard"]["compared"] is False
    assert out["attribution"]["skills"]["word"].startswith("ATTRIBUTION NOT READ at L5.2 skills Guard run")


def test_a_non_finite_stop_and_a_crash_read_does_not_work(tmp_path, fake_reload):
    nf = make_main(tmp_path / "nf", "velocity", "strike", wins_rows("strike", {}, 3), exit_code=5)
    crash = make_pilot(tmp_path / "crash", "skills", exit_code=1)
    code, out = read(tmp_path, build(tmp_path, velocity__strike=nf, skills__pilot=crash))
    assert out["routes"]["velocity"]["word"] == "PIPELINE DOES NOT WORK at L5.1 velocity Strike run"
    assert "exit 5" in out["routes"]["velocity"]["why"]
    assert out["routes"]["skills"]["word"] == "PIPELINE DOES NOT WORK at L3.3 skills pilot"
    assert "crashed (exit 1)" in out["routes"]["skills"]["why"]


def test_an_export_that_does_not_reload_reads_does_not_work_at_the_export(tmp_path, fake_reload):
    m = build(tmp_path)
    (tmp_path / "skills" / "export_strike" / "BROKEN").write_text("")
    code, out = read(tmp_path, m)
    assert out["routes"]["skills"]["word"] == "PIPELINE DOES NOT WORK at L6.2 skills Strike export"
    assert "golden rows" in out["routes"]["skills"]["why"]


def test_an_export_of_another_side_or_route_is_refused(tmp_path, fake_reload):
    wrong = make_export(tmp_path / "wrong", "velocity", "guard")
    assert reader.main(["--manifest", str(build(tmp_path, skills__export_guard=wrong)),
                        "--out", str(tmp_path / "out")]) == 2


def test_the_comparison_is_not_read_without_a_passing_scoring_suite_check(tmp_path, fake_reload):
    code, out = read(tmp_path / "a", build(_mk(tmp_path / "a"), suite=None))
    assert code == 0 and out["comparison"]["word"] == "COMPARISON NOT READ" and "L4.2" in out["comparison"]["why"]
    assert "guard" not in out["comparison"]
    code, out = read(tmp_path / "b", build(_mk(tmp_path / "b"), suite="FAIL"))
    assert code == 0 and out["comparison"]["word"] == "COMPARISON NOT READ"


@pytest.mark.parametrize("key,value", [("games", 3), ("gates_sha256", {"velocity": "0" * 64, "skills": "0" * 64})])
def test_a_suite_check_on_fewer_games_or_other_gate_files_is_refused(tmp_path, fake_reload, key, value):
    m = build(tmp_path)
    s = json.loads((tmp_path / "suite" / "suite_check.json").read_text())
    s[key] = value
    (tmp_path / "suite" / "suite_check.json").write_text(json.dumps(s))
    assert reader.main(["--manifest", str(m), "--out", str(tmp_path / "out")]) == 2


def test_an_export_of_another_checkpoint_is_refused_and_a_crashed_export_does_not_work(tmp_path, fake_reload):
    m = build(_mk(tmp_path / "a"))
    (tmp_path / "a" / "velocity" / "guard" / "agent_final.pt").write_bytes(b"retrained")
    assert reader.main(["--manifest", str(m), "--out", str(tmp_path / "a" / "out")]) == 2
    crashed = make_export(tmp_path / "crashed", "velocity", "guard", exit_code=1)     # read before its sha
    code, out = read(tmp_path / "b", build(_mk(tmp_path / "b"), velocity__export_guard=crashed))
    assert out["routes"]["velocity"]["word"] == "PIPELINE DOES NOT WORK at L6.2 velocity Guard export"
    assert "crashed (exit 1)" in out["routes"]["velocity"]["why"]


def test_attribution_and_held_arm_not_read_words(tmp_path, fake_reload):
    po = make_main(tmp_path / "po", "velocity_poolonly", "guard", wins_rows("guard", {}, 4), exit_code=6,
                   controls={"ctl_reference_replay_final": {"status": "FAIL"}})
    code, out = read(tmp_path, build(tmp_path, held="FAIL", velocity__poolonly_guard=po, skills__poolonly_guard=None))
    assert out["attribution"]["velocity"]["word"] == "ATTRIBUTION NOT READ at L5.3 velocity pool-only Guard run"
    assert out["attribution"]["skills"]["word"] == "not given"
    assert out["held_arm"]["word"] == "HELD ARM NOT READ" and "ctl_hold_one_is_reference" in out["held_arm"]["why"]
    assert out["routes"]["velocity"]["word"] == "PIPELINE WORKS"                   # the route word does not change


def test_attribution_is_paired_pool_and_mask_against_pool_only(tmp_path, fake_reload):
    po = make_main(tmp_path / "po", "velocity_poolonly", "guard", wins_rows("guard", {}, 10))   # the same wins
    code, out = read(tmp_path, build(tmp_path, velocity__poolonly_guard=po))
    a = out["attribution"]["velocity"]
    assert a["pooled_difference"]["diff"] == 0.0 and a["pooled_difference"]["word"] == "not distinguishable"
    assert all(c["word"] == "not distinguishable" for c in a["paired_cells"])


def test_folders_not_on_the_same_starts_or_another_gate_file_are_refused(tmp_path, fake_reload):
    m = build(tmp_path)
    res_path = tmp_path / "skills" / "guard" / "results.json"
    res = json.loads(res_path.read_text())
    res["reference"]["start_sha256"] = "0" * 64
    res_path.write_text(json.dumps(res))
    assert reader.main(["--manifest", str(m), "--out", str(tmp_path / "out")]) == 2
    other = make_pilot(tmp_path / "other", "velocity")                            # a velocity pilot as the skills one
    assert reader.main(["--manifest", str(build(_mk(tmp_path / "x"), skills__pilot=other)),
                        "--out", str(tmp_path / "x" / "out")]) == 2


def test_a_pooled_rate_unlike_the_runs_own_results_is_refused(tmp_path, fake_reload):
    off = make_main(tmp_path / "off", "velocity", "guard", wins_rows("guard", {}, 10), pooled_off=0.01)
    assert reader.main(["--manifest", str(build(tmp_path, velocity__guard=off)), "--out", str(tmp_path / "out")]) == 2


def test_unworded_states_are_refused(tmp_path, fake_reload):
    cap = make_main(tmp_path / "cap", "velocity", "guard", wins_rows("guard", {}, 3), exit_code=3)
    assert reader.main(["--manifest", str(build(_mk(tmp_path / "a"), velocity__guard=cap)),
                        "--out", str(tmp_path / "a" / "out")]) == 2               # stopped at its cap: no word
    short = make_main(tmp_path / "short", "velocity", "guard", wins_rows("guard", {}, 10), budget_reached=False)
    assert reader.main(["--manifest", str(build(_mk(tmp_path / "b"), velocity__guard=short)),
                        "--out", str(tmp_path / "b" / "out")]) == 2               # trained short of the budget
    assert reader.main(["--manifest", str(build(_mk(tmp_path / "c"), velocity__run0=None)),
                        "--out", str(tmp_path / "c" / "out")]) == 2               # a required task not given
    nox = make_pilot(tmp_path / "nox", "velocity")
    (nox / jobs.EXIT_FILE).unlink()
    assert reader.main(["--manifest", str(build(_mk(tmp_path / "d"), velocity__pilot=nox)),
                        "--out", str(tmp_path / "d" / "out")]) == 2               # no exit_code: not through ste_job


def test_the_best_single_choice_is_the_reference_cells_best_script(tmp_path, fake_reload):
    code, out = read(tmp_path, build(tmp_path))
    gates = GATES["velocity"]
    ref = exploit.load_reference(exploit.ROOT / gates.reference["file"])
    members = pool.pool_members(gates.players, "strike")
    want = scoring.best_single_choice(ref, exploit.ref_variant(gates, "base"), "guard",
                                      list(gates.players["guards"]), members, N)
    got = out["comparison"]["guard"]["best_single_choice"]
    assert got["best"] == want["best"] and got["rate"] == pytest.approx(want["per_choice"][want["best"]]["rate"])


def test_the_reload_runs_in_a_fresh_process_on_a_real_export(tmp_path):
    """No stand-in: a real tiny export (tests/test_ste_l3_export.py's learner) read back by the reader's own call."""
    pytest.importorskip("onnxruntime")
    import test_ste_l3_export as tx
    from svg_training.ste import export
    gates, learner = tx.tiny_learner("velocity", "guard")
    folder = export.export_policy(learner.saved(), gates, "guard", tmp_path / "e",
                                  export.golden_observations(gates, "guard", games=4))
    r = reader.reload_in_a_fresh_process(folder)
    assert r["ok"] and r["runtimes"] == ["onnxruntime", "onnx.reference"]
    (folder / "interface.toml").write_text((folder / "interface.toml").read_text().replace(export.STATUS, "x"))
    r = reader.reload_in_a_fresh_process(folder)
    assert not r["ok"] and "status" in r["error"]


def test_a_pilot_control_that_failed_reads_does_not_work_at_the_pilot(tmp_path, fake_reload):
    """The pilot records its controls in pilot.json and exits 0 (it never exits 6): a FAIL there is read."""
    bad = make_pilot(tmp_path / "bad", "velocity", control="FAIL")
    code, out = read(tmp_path, build(tmp_path, velocity__pilot=bad))
    assert out["routes"]["velocity"]["word"] == "PIPELINE DOES NOT WORK at L3.2 velocity pilot"
    assert "ctl_reference_replay_pilot" in out["routes"]["velocity"]["why"]


def test_a_main_run_without_its_final_scoring_blocks_is_refused(tmp_path, fake_reload):
    """Section 3: the final phase writes the pooled row, the best single fixed choice and (skills) the choice share."""
    for name, drop in (("a", "best_single_choice"), ("b", "pooled"), ("c", "choice_by_decision")):
        m = build(_mk(tmp_path / name))
        path = tmp_path / name / "skills" / "strike" / "results.json"
        res = json.loads(path.read_text())
        res.pop(drop)
        path.write_text(json.dumps(res))
        assert reader.main(["--manifest", str(m), "--out", str(tmp_path / name / "out")]) == 2, drop


# ------------------------------------------------------------------- folders the real drivers wrote (the file contract)
from test_ste_l3_pool import pooled_runs  # noqa: E402,F401  (module fixture: a velocity Guard and a skills Strike run)
from test_ste_l3_run0 import tiny_run0  # noqa: E402,F401   (module fixture: the skills pilot and run 0, CPU)
from test_ste_l3_held_arm import done as held_done  # noqa: E402,F401


def test_the_reader_reads_folders_the_drivers_wrote(pooled_runs, tiny_run0, held_done, monkeypatch):  # noqa: F811
    for side, (g, r) in pooled_runs.items():
        gates = exploit.load_gates(g)
        (r / jobs.EXIT_FILE).write_text("0\n")                      # as scripts/ste_job.py writes it
        why, run = reader.read_main(r, gates, side, f"{side} run")
        assert why is None and run["n"] == run["results"]["eval_games"]
        assert set(run["wins"]) == set(reader.opponents_of(gates, side))
        if side == "strike":
            assert all(compare.overall_share(e) for e in run["results"]["choice_by_decision"].values())
    monkeypatch.setattr(exploit, "SKILLS_RUN0_EVAL_GAMES", 8)       # tiny_run0's test-only evaluation size
    code, g, r0, pilot = tiny_run0
    gates = exploit.load_gates(g)
    pilot_gates = exploit.load_gates(pilot.parent.parent / "a" / "gates.toml")
    for folder in (r0, pilot.parent):
        (folder / jobs.EXIT_FILE).write_text(f"{code if folder == r0 else 0}\n")
    assert reader.read_pilot(pilot.parent, pilot_gates, "pilot") is None
    why, status = reader.read_run0(r0, gates, "run 0")
    assert why is None and status in ("PASS", "FAIL", "INCONCLUSIVE")
    (held_done / jobs.EXIT_FILE).write_text("0\n")
    assert reader.held_arm({"held_arm": str(held_done)})["word"] == "read"


# ------------------------------------------------------------------------------------- QC round (S2, NITs)
def test_a_partial_suite_or_one_without_its_exit_code_is_refused(tmp_path, fake_reload):
    m = build(_mk(tmp_path / "a"))
    path = tmp_path / "a" / "suite" / "suite_check.json"
    s = json.loads(path.read_text())
    del s["checks"]["skills"]["strike"]                                  # three of the 2 x 2 entries
    path.write_text(json.dumps(s))
    assert reader.main(["--manifest", str(m), "--out", str(tmp_path / "a" / "out")]) == 2
    m = build(_mk(tmp_path / "b"))
    (tmp_path / "b" / "suite" / jobs.EXIT_FILE).unlink()
    assert reader.main(["--manifest", str(m), "--out", str(tmp_path / "b" / "out")]) == 2
    m = build(_mk(tmp_path / "c"))
    (tmp_path / "c" / "suite" / jobs.EXIT_FILE).write_text("6\n")       # exit 6 with a PASS file: inconsistent
    assert reader.main(["--manifest", str(m), "--out", str(tmp_path / "c" / "out")]) == 2


def test_the_held_arm_reads_its_exit_code(tmp_path, fake_reload):
    m = build(_mk(tmp_path / "a"))
    (tmp_path / "a" / "held" / jobs.EXIT_FILE).unlink()
    assert reader.main(["--manifest", str(m), "--out", str(tmp_path / "a" / "out")]) == 2
    m = build(_mk(tmp_path / "b"))
    (tmp_path / "b" / "held" / jobs.EXIT_FILE).write_text("1\n")       # crashed: no word for it
    assert reader.main(["--manifest", str(m), "--out", str(tmp_path / "b" / "out")]) == 2


def test_a_missing_runtime_is_an_environment_refusal_not_a_failed_export(tmp_path, monkeypatch):
    fake = tmp_path / "fake"
    (fake / "onnxruntime").mkdir(parents=True)
    (fake / "onnxruntime" / "__init__.py").write_text("raise ImportError('No module named onnxruntime (test)')\n")
    monkeypatch.setenv("PYTHONPATH", str(fake))
    with pytest.raises(reader.Refused, match="environment"):
        reader.reload_in_a_fresh_process(tmp_path)


def test_unparseable_reload_output_is_caught(tmp_path, monkeypatch):
    import subprocess
    monkeypatch.setattr(reader.subprocess, "run",
                        lambda *a, **k: subprocess.CompletedProcess(a, 0, stdout="garbage\n", stderr=""))
    r = reader.reload_in_a_fresh_process(tmp_path)
    assert r["ok"] is False and "unparseable" in r["error"]
