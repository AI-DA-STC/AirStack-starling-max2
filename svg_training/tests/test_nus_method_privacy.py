"""Phase 5 task M1 guard rails for the partner's training-method values: the template (G1), the loader's refusals, the make-local script
(writes only under configs/local/, prints no value, refuses a method the port does not copy), records that refuse a method value (G3)
and the marker chain (G4): marker values go in, and no file outside the local file, no captured output and no file git would add holds
one. Marker values only; the real local file is read only by the last test, and only to check it loads."""
import contextlib
import importlib.util
import io
import json
import subprocess
import tomllib

import pytest

from _nus_markers import BATCH, ROOT, marker_deploy, marker_rules, write_deploy_toml, write_toml
from _nus_phase5_method_fixture import (NOT_INTEGER, TRAIN_GAMES, UNSUPPORTED_RUNS, marker_method, method_marker_strings, write_fake_learner_sources,
                                        write_fake_run, write_method_toml)
from svg_training.nus import method_cfg, outputs, rules as rules_mod


def _script():
    spec = importlib.util.spec_from_file_location("nus_make_local_method", ROOT / "scripts" / "nus_make_local_method.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run_script(tmp_path, monkeypatch, values=None, **changes):
    values = values or marker_method()
    clone = write_fake_learner_sources(tmp_path / "clone", values)
    run = write_fake_run(tmp_path / "run", values, **changes)
    make = _script()
    monkeypatch.setattr(make, "LOCAL_OUT_DIR", tmp_path / "local")
    out = tmp_path / "local" / "nus_method.toml"
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        make.main(["--run-config", str(run), "--clone", str(clone), "--out", str(out)])
    return out, buf.getvalue(), clone, run


def test_g1_method_template_has_every_key_with_local_placeholder():
    tpl = tomllib.loads(method_cfg.METHOD_TEMPLATE.read_text())
    assert tuple(tpl) == method_cfg.METHOD_KEYS
    assert all(v == "LOCAL" for v in tpl.values())


def test_g1_method_file_is_git_ignored():
    r = subprocess.run(["git", "check-ignore", "-q", "configs/local/nus_method.toml"], cwd=ROOT)
    if r.returncode not in (0, 1):
        pytest.skip("git not available")
    assert r.returncode == 0


def test_g1_method_loader_refuses_placeholder_missing_unknown_bad_type_and_inconsistency(tmp_path):
    good = marker_method()
    path = tmp_path / "m.toml"
    write_method_toml(path, good)
    loaded = method_cfg.load_method(path)
    assert loaded.ppo_clip == good["ppo_clip"] and loaded.hidden_dim == good["hidden_dim"] and loaded.first_team == good["first_team"]
    cases = [({**good, "ppo_clip": "LOCAL"}, "ppo_clip"), ({**good, "activation": "LOCAL"}, "activation"),
             ({**good, "compute_dtype": "float16"}, "compute_dtype"), ({**good, "use_layernorm": 1}, "use_layernorm"),
             ({**good, "ppo_epochs": NOT_INTEGER}, "ppo_epochs"), ({**good, "extra_key": 1.0}, "extra_key"),
             ({k: v for k, v in good.items() if k != "weight_decay"}, "weight_decay"),
             ({**good, "recent_opponents": good["max_learned_opponents"] + 1}, "recent_opponents"),
             ({**good, "max_pool_slots": good["max_learned_opponents"]}, "max_pool_slots"),
             ({**good, "hidden_dim": good["hidden_dim"] + 1}, "hidden_dim")]
    for values, key in cases:
        write_method_toml(path, values)
        with pytest.raises(ValueError, match=key):
            method_cfg.load_method(path)
    with pytest.raises(FileNotFoundError):
        method_cfg.load_method(tmp_path / "absent.toml")


def test_team_helpers():
    path_values = marker_method()
    method = method_cfg.NusMethod(**{k: path_values[k] for k in method_cfg.METHOD_KEYS})
    assert [method_cfg.team_of_generation(method, g) for g in (1, 2)] == ["guard", "strike"]
    assert method_cfg.team_value(method, "strike", "gamma") == path_values["strike_gamma"]
    with pytest.raises(ValueError):
        method_cfg.team_of_generation(method, 0)


def test_make_local_method_reads_config_and_code_constants(tmp_path, monkeypatch):
    values = marker_method()
    out, captured, _, _ = _run_script(tmp_path, monkeypatch, values)
    loaded = method_cfg.load_method(out)
    for key in method_cfg.METHOD_KEYS:
        assert getattr(loaded, key) == values[key], key
    assert not [m for m in method_marker_strings(values) if m in captured]
    assert "sha256" in captured and "ppo_clip" in captured


def test_make_local_method_refuses_out_outside_local_and_unsupported_runs(tmp_path, monkeypatch):
    values = marker_method()
    clone = write_fake_learner_sources(tmp_path / "clone", values)
    run = write_fake_run(tmp_path / "run", values)
    make = _script()
    monkeypatch.setattr(make, "LOCAL_OUT_DIR", tmp_path / "local")
    with pytest.raises(SystemExit, match="configs/local|local"):
        make.main(["--run-config", str(run), "--clone", str(clone), "--out", str(tmp_path / "elsewhere.toml")])
    for dotted, value in UNSUPPORTED_RUNS.items():
        bad = write_fake_run(tmp_path / f"bad_{dotted}", values, **{dotted: value})
        with pytest.raises(SystemExit, match=dotted.split(".")[-1]):
            make.main(["--run-config", str(bad), "--clone", str(clone), "--out", str(tmp_path / "local" / "m.toml")])
    assert not (tmp_path / "local" / "m.toml").exists() and not (tmp_path / "elsewhere.toml").exists()


def test_make_local_method_refuses_ambiguous_code(tmp_path, monkeypatch):
    values = marker_method()
    clone = write_fake_learner_sources(tmp_path / "clone", values)
    policy = clone / "ma_skills" / "jax" / "policy.py"
    policy.write_text(policy.read_text().replace("        return jnp.clip", "        other = nn.initializers.orthogonal(2.0)\n        return jnp.clip"))
    make = _script()
    with pytest.raises(LookupError, match="orthogonal"):
        make.read_learner_constants(clone)


def test_g3_record_refuses_method_values(tmp_path):
    write_toml(tmp_path / "r.toml", marker_rules())
    write_deploy_toml(tmp_path / "d.toml", marker_deploy())
    values = marker_method()
    write_method_toml(tmp_path / "m.toml", values)
    kw = {"deploy_path": tmp_path / "d.toml", "method_path": tmp_path / "m.toml"}
    for payload in ({"x": values["ppo_clip"]}, {"x": [values["guard_actor_lr"]]}, {"x": f"lr {values['strike_critic_lr']!r}"}):
        with pytest.raises(ValueError):
            outputs.write_record(tmp_path / "bad.json", payload, tmp_path / "r.toml", **kw)
    assert not (tmp_path / "bad.json").exists()
    ok = json.loads(outputs.write_record(tmp_path / "ok.json", {"note": "keys only"}, tmp_path / "r.toml", **kw).read_text())
    assert ok["method_sha256"] == rules_mod.file_sha256(tmp_path / "m.toml") and "ppo_clip" in ok["method_keys"]
    # without the opt-in the method values are not protected (Phase 3 and 4 records keep their behaviour)
    outputs.write_record(tmp_path / "phase4.json", {"x": values["ppo_clip"]}, tmp_path / "r.toml", deploy_path=tmp_path / "d.toml")


def test_g4_method_marker_chain_leaks_nothing(tmp_path, monkeypatch):
    """Markers through the make-local script, the loader, a training-environment step, a learner update, a self-play generation (state,
    checkpoints, archive), a scored matrix and a record; then every file written outside the local file and the inputs, the captured
    output and every file git would add are scanned."""
    import torch

    from _nus_markers import load_marker_files
    from svg_training.nus.mappo import Learner
    from svg_training.nus.replica_train import NusTrainEnv

    values = marker_method()
    local, captured, clone, run = _run_script(tmp_path, monkeypatch, values)
    method = method_cfg.load_method(local)
    rules, deploy, rules_path, deploy_path = load_marker_files(tmp_path / "inputs")
    env = NusTrainEnv(rules, deploy, method)
    gen = torch.Generator().manual_seed(0)
    state = env.reset(TRAIN_GAMES, gen)
    learner = Learner(method, env, "guard", seed=1)
    rollout = learner.collect(env, state, gen, steps=rules.episode_steps, opponent=lambda s, g: env.apf_actions(s, "strike"))
    metrics = learner.update(rollout, gen)
    assert all(torch.isfinite(torch.as_tensor(v)) for v in metrics.values())
    from svg_training.nus import crossplay
    from svg_training.nus.selfplay import SelfPlay
    archive = SelfPlay(method, env, seed=TRAIN_GAMES, run_dir=tmp_path / "runs" / "selfplay", generations=1).run()
    forward = dict(bf16=method.compute_dtype == "bfloat16", activation=method.activation, eps=deploy.layernorm_epsilon,
                   use_norm=method.use_layernorm)
    players = crossplay.untrained_trees(env, method, seed=TRAIN_GAMES, generations=2)
    guards = {e: t for e, t in players.items() if e.team == "guard"}
    strikes = {e: t for e, t in players.items() if e.team == "strike"}
    xp = crossplay.score_matrix(env, guards, strikes, crossplay.shared_starts(env, TRAIN_GAMES, TRAIN_GAMES), forward, TRAIN_GAMES)
    (tmp_path / "runs" / "matrix.json").write_text(json.dumps({"reached": xp.reached.tolist(), "archive": archive}))
    outputs.write_record(tmp_path / "out" / "summary.json", {"note": "marker chain", "updates": 1}, rules_path, deploy_path=deploy_path,
                         method_path=local)
    markers = method_marker_strings(values)
    inputs = {local, rules_path, deploy_path}
    hits = []
    for p in tmp_path.rglob("*"):
        if p.is_file() and p not in inputs and clone not in p.parents and run not in p.parents:
            text = p.read_text(errors="ignore")
            hits += [(str(p), m) for m in markers if m in text]
    hits += [("captured output", m) for m in markers if m in captured]
    listing = subprocess.run(["git", "ls-files", "-co", "--exclude-standard"], cwd=ROOT, capture_output=True, text=True)
    if listing.returncode == 0:
        for rel in listing.stdout.splitlines():
            p = ROOT / rel
            if p.is_file():
                hits += [(rel, m) for m in markers if m in p.read_text(errors="ignore")]
    assert not hits, f"method marker values found in: {sorted({w for w, _ in hits})}"


def test_real_local_method_file_loads_when_present():
    if not method_cfg.LOCAL_METHOD.exists():
        pytest.skip("no configs/local/nus_method.toml on this machine (run scripts/nus_make_local_method.py): a skip is not a pass")
    method = method_cfg.load_method()
    assert method.first_team in method_cfg.TEAMS and method.compute_dtype in method_cfg.COMPUTE_DTYPES
