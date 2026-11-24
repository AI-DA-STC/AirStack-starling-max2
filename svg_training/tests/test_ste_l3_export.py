"""STE L3-L6 pipeline check, task L6.2: the export and reload check of both routes (``ste/export.py``; spec
ste_learning/drafts/L3_L6_PIPELINE_SPEC.md section 5; schemas ``ste-check-velocity-0`` and ``ste-check-skills-0``).

A tiny learner of each route (CPU, one update) is exported (one ONNX file per drone slot, the observation scaler
folded in, and ``interface.toml``); the reload check runs in a FRESH Python process with onnxruntime (the primary
runtime) and onnx's ReferenceEvaluator (an independent second check): outputs within 1e-6 of the golden rows, each
head's argmax, the leader's choice, the flown skill and the skill lists exactly, the final commands within 1e-6 from
the pinned scripted.py. The reload refuses a missing or changed status ("pipeline check, not for flight"), a changed
file (sha256), an unknown schema. This does not settle the AirStack container's runtime (ARCHITECTURE section 3)."""
import json
import subprocess
import tomllib

import pytest
import torch

pytest.importorskip("onnxruntime")
import onnx  # noqa: E402

from _proc import child_env, child_python  # noqa: E402
from svg_training.opponents.scripted import make_strategy  # noqa: E402
from svg_training.ste import exploit, exploit_train, export  # noqa: E402

HOLD = 12
GATES = {"velocity": exploit.ROOT / "configs" / "ste_l3" / "velocity_gates.toml",
         "skills": exploit.ROOT / "configs" / "ste_l3" / "skills_gates.toml"}


def tiny_learner(route: str, side: str):
    gates = exploit.load_gates(GATES[route])
    cfg = exploit.variant_cfg(gates, "base")
    game = exploit_train.TrainGame(cfg, 6, 3, 3, device="cpu", seed=7)
    opp = make_strategy(exploit.opponent_of(gates, "base", side), "strike" if side == "guard" else "guard", cfg, 6,
                        "cpu", 8)
    env = exploit_train.decision_env(game, HOLD, side, opp, gates.learner, gates.players, 7)
    settings = {**gates.trainer, "num_games": 6, "rollouts": 2, "learning_epochs": 1, "mini_batches": 1}
    learner = exploit_train.Learner(settings, env, "cpu", seed=11)
    learner.update()
    return gates, learner


def reload_in_a_fresh_process(folder):
    code = ("import json, sys\nfrom svg_training.ste import export\n"
            "print(json.dumps(export.reload_check(sys.argv[1])))")
    r = subprocess.run([child_python(), "-c", code, str(folder)], env={**child_env(), "CUDA_VISIBLE_DEVICES": ""},
                       capture_output=True, text=True, timeout=300)
    return r


@pytest.fixture(scope="module", params=[("velocity", "guard"), ("skills", "strike")], ids=["velocity", "skills"])
def exported(request, tmp_path_factory):
    route, side = request.param
    gates, learner = tiny_learner(route, side)
    out = tmp_path_factory.mktemp(f"export_{route}")
    obs = export.golden_observations(gates, side, games=8, seed=5)
    folder = export.export_policy(learner.saved(), gates, side, out / "policy", obs)
    return route, side, gates, learner, folder, obs


def test_the_folder_holds_one_onnx_per_slot_and_the_interface(exported):
    route, side, gates, learner, folder, obs = exported
    meta = tomllib.loads((folder / "interface.toml").read_text())
    assert meta["policy_schema"] == f"ste-check-{route}-0" and meta["status"] == export.STATUS
    assert meta["team"] == side and meta["hold_ticks"] == HOLD and meta["interface_version"] == "0.1"
    assert len(meta["files"]) == 3 and all((folder / f["file"]).is_file() for f in meta["files"])
    for f in meta["files"]:
        m = onnx.load(str(folder / f["file"]))
        props = {p.key: p.value for p in m.metadata_props}
        assert props["status"] == export.STATUS and props["policy_schema"] == meta["policy_schema"]
    assert len(meta["golden"]) == 8
    if route == "skills":
        assert meta["skills"]["team_strategies"] == list(gates.learner.team_strategies[side])
        assert meta["skills"]["free_index"] == 0 and meta["scripted_sha256"]


def test_the_onnx_files_compute_the_trained_policy(exported):
    """The exported graph (scaler folded in) against the learner's own team on the golden observations."""
    import numpy as np
    import onnxruntime as ort
    route, side, gates, learner, folder, obs = exported
    team = learner.team()
    meta = tomllib.loads((folder / "interface.toml").read_text())
    want = team.logits(obs) if route == "skills" else team.act(obs)
    for i, f in enumerate(meta["files"]):
        sess = ort.InferenceSession(str(folder / f["file"]), providers=["CPUExecutionProvider"])
        got = sess.run(None, {"obs": obs[:, i].numpy().astype(np.float32)})[0]
        assert np.allclose(got, want[:, i].numpy(), rtol=0, atol=1e-6), i


def test_the_reload_check_passes_in_a_fresh_process_with_both_runtimes(exported):
    route, side, gates, learner, folder, obs = exported
    r = reload_in_a_fresh_process(folder)
    assert r.returncode == 0, r.stderr[-2000:]
    out = json.loads(r.stdout.strip().splitlines()[-1])
    assert out["ok"] and out["runtimes"] == ["onnxruntime", "onnx.reference"]
    assert out["max_abs_diff"] <= 1e-6 and out["golden_rows"] == 8 * 3
    if route == "skills":
        assert out["choices_equal"] and out["skill_lists_equal"] and out["commands_max_abs_diff"] <= 1e-6


@pytest.mark.parametrize("damage,why", [
    ("status", "status"), ("schema", "schema"), ("onnx_bytes", "sha256"), ("onnx_status", "status")])
def test_the_reload_refuses_a_damaged_export(exported, tmp_path, damage, why):
    import shutil
    route, side, gates, learner, folder, obs = exported
    copy = tmp_path / "copy"
    shutil.copytree(folder, copy)
    meta_path = copy / "interface.toml"
    text = meta_path.read_text()
    if damage == "status":
        meta_path.write_text(text.replace(f'status = "{export.STATUS}"', 'status = "ready to fly"'))
    elif damage == "schema":
        meta_path.write_text(text.replace(f'policy_schema = "ste-check-{route}-0"', 'policy_schema = "ste-policy-1"'))
    else:
        first = copy / tomllib.loads(text)["files"][0]["file"]
        m = onnx.load(str(first))
        if damage == "onnx_bytes":
            m.doc_string = "changed"
        else:
            keep = [p for p in m.metadata_props if p.key != "status"]
            del m.metadata_props[:]
            m.metadata_props.extend(keep)
        onnx.save(m, str(first))
        if damage == "onnx_status":                       # the sha256 rewritten too: only the status is missing
            meta_path.write_text(text.replace(tomllib.loads(text)["files"][0]["sha256"], export.sha256_file(first)))
    with pytest.raises(ValueError, match=why):
        export.reload_check(copy)


def test_onnxruntime_is_listed_as_the_export_extra():
    data = tomllib.loads((exploit.ROOT / "pyproject.toml").read_text())
    extra = {r.split(">")[0].split("=")[0].strip() for r in data["project"]["optional-dependencies"]["export"]}
    assert {"onnx", "onnxruntime"} <= extra
