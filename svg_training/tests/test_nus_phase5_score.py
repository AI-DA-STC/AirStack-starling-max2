"""Phase 5 task M8: scoring an arm against the R0 reference (scripts/nus_phase5_score.py) on synthetic entries, made-up rule values and
tiny game counts (not of record): the arm's gates copied verbatim, the reference cells reused unchanged, N0's untrained arm with its
selection-rule pools, C0's conversion and gate (a), our archives with completion from the state and status files, the verdict and the
INFO statistics written to result_not_of_record.json, nothing outside runs/."""
import importlib.util
import json
import tomllib

import pytest

from _nus_markers import ROOT
from _nus_phase5_method_fixture import (C0_RUN, R0_CHUNK, R0_GAMES, SYNTHETIC_HIDDEN, marker_method, write_fake_ours, write_fake_reference,
                                        write_method_toml)


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def world(tmp_path, monkeypatch):
    """A synthetic R0 under tmp runs/ and the scorer pointed at it."""
    r0, score = _load("nus_phase5_reference"), _load("nus_phase5_score")
    runs = tmp_path / "runs"
    for mod in (r0, score):
        monkeypatch.setattr(mod, "RUNS_ROOT", runs)
    monkeypatch.setattr(score, "PHASE5", runs / "phase5")
    import nus_convert_checkpoint as convert
    import nus_phase5_reference
    monkeypatch.setattr(convert, "require_under_runs", lambda p: r0._under_runs(p))
    monkeypatch.setattr(nus_phase5_reference, "RUNS_ROOT", runs)
    gates = tomllib.loads((ROOT / "configs" / "nus_port.toml").read_text())["gates"]
    ref = gates["phase5_reference_rebuild"]
    lo, hi = ref["generations"]
    outputs, actions, rules, deploy = write_fake_reference(tmp_path, list(ref["reference_runs"]), range(lo, hi + 1))
    method_path = tmp_path / "inputs" / "nus_method.toml"
    write_method_toml(method_path, marker_method(hidden_dim=SYNTHETIC_HIDDEN, compute_dtype="bfloat16"))
    common = ["--rules", str(rules), "--deploy", str(deploy), "--method", str(method_path), "--games-override", str(R0_GAMES),
              "--chunk", str(R0_CHUNK)]
    refdir = runs / "phase5" / "reference"
    assert r0.main(["--write-gates", "--out-dir", str(refdir)]) == 0
    assert r0.main(["--run", "--outputs-dir", str(outputs), "--out-dir", str(refdir), "--actions-dir", str(actions), *common]) == 0
    return {"score": score, "gates": gates, "common": common, "refdir": refdir, "tmp": tmp_path, "rules": rules, "deploy": deploy,
            "method": method_path, "generations": hi}


def _score(world, arm, *extra):
    s, out = world["score"], world["tmp"] / "runs" / "phase5" / arm / "score"
    assert s.main(["--arm", arm, "--write-gates", "--out-dir", str(out)]) == 0
    copied = tomllib.loads((out / "gates.toml").read_text())["gates"]
    assert copied[s.ARM_TABLE[arm]] == world["gates"][s.ARM_TABLE[arm]] and copied["phase5_method_match"] == world["gates"]["phase5_method_match"]
    return out, ["--arm", arm, "--out-dir", str(out), "--reference-dir", str(world["refdir"]), *world["common"], *extra]


def _result(out):
    return json.loads((out / "result_not_of_record.json").read_text())


def test_n0_is_scored_against_the_reference(world):
    out, args = _score(world, "n0")
    assert world["score"].main([*args, "--score"]) == 0
    result = _result(out)
    assert result["statistics"]["a"] is None and "negative_control_failed_as_required" in result
    assert result["verdict"]["verdict"] in ("PASS", "FAIL", "INCONCLUSIVE") and len(result["statistics"]["d"]) == 2
    matrix = json.loads((out / f"matrix_{R0_GAMES}_not_of_record.json").read_text())
    ref = json.loads((world["refdir"] / f"matrix_{R0_GAMES}_not_of_record.json").read_text())
    n_ref = len(ref["guards"])
    assert [row[: len(ref["strikes"])] for row in matrix["reached"][:n_ref]] == ref["reached"]          # reference cells reused
    assert all(v is not None for v in matrix["apf_strike_reached"]) and all(v is not None for v in matrix["apf_guard_reached"])
    assert set(result["info_5_1_e"]) >= {"last_mover_share", "near_shutout_share", "generalist_mean_ours"}


def test_c0_converts_checks_and_scores(world):
    seeds = world["gates"]["phase5_positive_control"]["seeds"]
    runs = [C0_RUN.format(seed=s) for s in seeds]
    tmp2 = world["tmp"] / "c0_inputs"
    tmp2.mkdir()
    outputs, actions, _, _ = write_fake_reference(tmp2, runs, range(1, world["generations"] + 1))
    out, args = _score(world, "c0")
    extra = ["--outputs-dir", str(outputs), "--runs", *runs, "--actions-dir", str(actions)]
    assert world["score"].main([*args, "--check", *extra]) == 0
    assert world["score"].main([*args, "--score", *extra]) == 0
    result = _result(out)
    assert result["lineages_ours"] == runs and result["statistics"]["a"]["pass"]


def test_our_archives_are_scored_with_completion(world):
    from svg_training.nus.deploy import apply_overrides, load_deploy
    from svg_training.nus.method_cfg import load_method
    from svg_training.nus.replica_train import NusTrainEnv
    from svg_training.nus.rules import load_rules
    seeds = world["gates"]["phase5_method_match"]["seeds"]
    deploy = load_deploy(world["deploy"])
    method = load_method(world["method"])
    env = NusTrainEnv(apply_overrides(load_rules(world["rules"]), deploy), deploy, method)
    write_fake_ours(world["tmp"] / "runs" / "phase5", "s51", seeds, env, method, world["generations"])
    out, args = _score(world, "s51")
    assert world["score"].main([*args, "--score"]) == 0
    result = _result(out)
    assert result["statistics"]["a"]["pass"] and result["lineages_ours"] == [f"o{s}" for s in seeds]
    assert all(p.is_relative_to(world["tmp"]) for p in world["tmp"].rglob("*"))
