"""Phase 5 task M6: the R0 reference rebuild (scripts/nus_phase5_reference.py) on synthetic archive entries in NUS's layout, made-up
rule values and tiny game counts (not of record): the gates copied verbatim before any result, conversion and gate (a) per entry, a
failed entry leaving the set, more failures than allowed stopping the stage, the matrix scored with nus/crossplay.py, the leave-one-out
check, and nothing written outside runs/."""
import importlib.util
import json
import sys
import tomllib

import pytest

from _nus_markers import ROOT
from _nus_phase5_method_fixture import R0_CHUNK, R0_GAMES, marker_method, write_fake_reference, write_method_toml


@pytest.fixture()
def r0(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("nus_phase5_reference", ROOT / "scripts" / "nus_phase5_reference.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "RUNS_ROOT", tmp_path / "runs")
    import nus_convert_checkpoint as convert
    monkeypatch.setattr(convert, "require_under_runs", lambda p: mod._under_runs(p))
    return mod


def _gates():
    return tomllib.loads((ROOT / "configs" / "nus_port.toml").read_text())["gates"]


def _args(tmp_path, outputs, actions, rules, deploy, *mode):
    method = tmp_path / "inputs" / "nus_method.toml"
    write_method_toml(method, marker_method())
    return [*mode, "--outputs-dir", str(outputs), "--out-dir", str(tmp_path / "runs" / "ref"), "--actions-dir", str(actions),
            "--rules", str(rules), "--deploy", str(deploy), "--method", str(method), "--games-override", str(R0_GAMES),
            "--chunk", str(R0_CHUNK)]


def test_gates_are_copied_verbatim_and_never_overwritten(tmp_path, r0):
    path = r0.write_gates(tmp_path / "runs" / "ref")
    copied = tomllib.loads(path.read_text())["gates"]
    for table in r0.TABLES:
        assert copied[table] == _gates()[table]
    with pytest.raises(SystemExit, match="exists"):
        r0.write_gates(tmp_path / "runs" / "ref")
    with pytest.raises(SystemExit, match="outside runs"):
        r0.write_gates(tmp_path / "elsewhere")


def _setup(tmp_path, r0, spoil=()):
    ref = _gates()["phase5_reference_rebuild"]
    lo, hi = ref["generations"]
    outputs, actions, rules, deploy = write_fake_reference(tmp_path, list(ref["reference_runs"]), range(lo, hi + 1), spoil)
    assert r0.main(["--write-gates", "--out-dir", str(tmp_path / "runs" / "ref")]) == 0
    return ref, outputs, actions, rules, deploy


def test_run_converts_checks_and_scores(tmp_path, r0):
    ref, outputs, actions, rules, deploy = _setup(tmp_path, r0)
    assert r0.main(_args(tmp_path, outputs, actions, rules, deploy, "--run")) == 0
    out = tmp_path / "runs" / "ref"
    conv = json.loads((out / "conversions.json").read_text())
    lo, hi = ref["generations"]
    assert len(conv["entries"]) == len(ref["reference_runs"]) * (hi - lo + 1) and not conv["failed"] and not conv["stop"]
    matrix = json.loads((out / f"matrix_{R0_GAMES}_not_of_record.json").read_text())
    assert not matrix["of_record"] and len(matrix["guards"]) * len(matrix["strikes"]) == sum(map(len, matrix["reached"]))
    assert all(0 <= v <= R0_GAMES for row in matrix["reached"] for v in row) and not (out / f"matrix_{ref['games_per_pairing']}.json").exists()
    loo = json.loads((out / "loo_not_of_record.json").read_text())
    assert loo["statistic_c"] in ("gate", "INFO") and len(loo["reference_seed_values_info"]) == 2
    written = [p for p in tmp_path.rglob("*") if p.is_file() and "runs" not in p.relative_to(tmp_path).parts]
    assert all(p.relative_to(tmp_path).parts[0] in ("inputs", "outputs") for p in written)       # outputs only under runs/


def test_a_failed_entry_leaves_the_set(tmp_path, r0):
    ref, *_ = _setup(tmp_path, r0)
    run = ref["reference_runs"][0]
    tmp2 = tmp_path / "second"
    tmp2.mkdir()
    outputs, actions, rules, deploy = write_fake_reference(tmp2, list(ref["reference_runs"]), range(ref["generations"][0], ref["generations"][1] + 1),
                                                           spoil={(run, ref["generations"][0])})
    r0.RUNS_ROOT = tmp2 / "runs"
    assert r0.main(["--write-gates", "--out-dir", str(tmp2 / "runs" / "ref")]) == 0
    assert r0.main(_args(tmp2, outputs, actions, rules, deploy, "--run")) == 0
    conv = json.loads((tmp2 / "runs" / "ref" / "conversions.json").read_text())
    assert len(conv["failed"]) == 1 and not conv["stop"]
    matrix = json.loads((tmp2 / "runs" / "ref" / f"matrix_{R0_GAMES}_not_of_record.json").read_text())
    assert matrix["excluded"] == [[run, ref["generations"][0], "guard"]]


def test_too_many_failures_stop_the_stage(tmp_path, r0):
    ref = _gates()["phase5_reference_rebuild"]
    run = ref["reference_runs"][0]
    lo, hi = ref["generations"]
    spoil = {(run, g) for g in range(lo, lo + ref["max_failed_conversions"] + 1)}
    outputs, actions, rules, deploy = write_fake_reference(tmp_path, list(ref["reference_runs"]), range(lo, hi + 1), spoil)
    assert r0.main(["--write-gates", "--out-dir", str(tmp_path / "runs" / "ref")]) == 0
    assert r0.main(_args(tmp_path, outputs, actions, rules, deploy, "--run")) == r0.EXIT_STOP
    assert json.loads((tmp_path / "runs" / "ref" / "conversions.json").read_text())["stop"]
    assert not list((tmp_path / "runs" / "ref").glob("matrix_*"))
    with pytest.raises(SystemExit):
        r0.main(_args(tmp_path, outputs, actions, rules, deploy, "--score"))


def test_export_reference_per_archive_entry_in_the_partners_environment():
    """scripts/nus_export_reference.py --archive-entry in the partner's JAX environment (CPU, one episode per half): one actions file per
    entry, its team read from the entry's config. Skipped without the nus_jax environment, the clone or the reference runs (not a pass)."""
    import os
    import shutil
    import subprocess
    import uuid
    from pathlib import Path
    clone = Path.home() / "ma_skills-self-play" / "area-denial-continuous-space-self-play"
    python = Path.home() / "miniconda3" / "envs" / "nus_jax" / "bin" / "python"
    run = _gates()["phase5_reference_rebuild"]["reference_runs"][0]
    archive = clone / "outputs" / "hangar" / run / "archive"
    entries = sorted(p for p in archive.glob("000*") if p.is_dir())[:2] if archive.is_dir() else []
    if not (python.exists() and len(entries) == 2):
        pytest.skip("no nus_jax environment or reference archive on this machine (a skip is not a pass)")
    out = ROOT / "runs" / "nus_port" / "phase5" / f"test_export_{uuid.uuid4().hex}"
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"} | {"PYTHONNOUSERSITE": "1", "JAX_PLATFORMS": "cpu",
                                                                        "CUDA_VISIBLE_DEVICES": "", "WANDB_MODE": "disabled"}
    try:
        cmd = [str(python), str(ROOT / "scripts" / "nus_export_reference.py"), "--clone", str(clone), "--seed", "1",
               "--episodes-per-half", "1", "--out-dir", str(out)]
        for e in entries:
            cmd += ["--archive-entry", str(e)]
        done = subprocess.run(cmd, env=env, capture_output=True, text=True)
        assert done.returncode == 0, done.stderr[-len(done.stderr) // 2:]
        teams = {"defender": "guard", "attacker": "strike"}
        for e in entries:
            assert (out / run / e.name / f"actions_{teams[e.name.split('_')[-1]]}.npz").exists()
        assert not (out / "starts.npz").exists()
    finally:
        shutil.rmtree(out, ignore_errors=True)
