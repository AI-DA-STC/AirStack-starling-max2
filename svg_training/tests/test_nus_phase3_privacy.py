"""Phase 3 guard rails: the deploy file (G1), records that refuse any partner or owner value (G3), the numeric-literal scan over the
test files (G2). Marker values only; no partner checkpoint or value is used."""
import json
import tomllib

import pytest

from _nus_markers import (NOT_INTEGER, BATCH, ROOT, distinctive, marker_deploy, marker_rules, write_deploy_toml, write_toml)
from svg_training.nus import deploy as deploy_mod, outputs, rules as rules_mod


def test_g1_deploy_template_has_every_key_with_local_placeholder():
    tpl = tomllib.loads(deploy_mod.DEPLOY_TEMPLATE.read_text())
    assert tuple(tpl) == deploy_mod.DEPLOY_KEYS
    assert all(v == "LOCAL" for v in tpl.values())


def test_g1_deploy_loader_refuses_placeholder_missing_unknown_bad_type_and_inconsistent_hold(tmp_path):
    good = marker_deploy()
    path = tmp_path / "d.toml"
    write_deploy_toml(path, good)
    loaded = deploy_mod.load_deploy(path)
    assert loaded.hold_ticks == good["hold_ticks"] and loaded.guard_weights == good["guard_weights"]
    write_deploy_toml(path, {**good, "metres_per_unit": "LOCAL"})
    with pytest.raises(ValueError, match="metres_per_unit"):
        deploy_mod.load_deploy(path)
    write_deploy_toml(path, {**good, "guard_weights": "LOCAL"})
    with pytest.raises(ValueError, match="guard_weights"):
        deploy_mod.load_deploy(path)
    write_deploy_toml(path, {k: v for k, v in good.items() if k != "apf_floor"})
    with pytest.raises(ValueError, match="apf_floor"):
        deploy_mod.load_deploy(path)
    write_deploy_toml(path, {**good, "extra_key": 1.0})
    with pytest.raises(ValueError, match="extra_key"):
        deploy_mod.load_deploy(path)
    write_deploy_toml(path, {**good, "hold_ticks": good["hold_ticks"] + NOT_INTEGER})
    with pytest.raises(ValueError, match="hold_ticks"):
        deploy_mod.load_deploy(path)
    write_deploy_toml(path, {**good, "hold_ticks": good["hold_ticks"] + 1})
    with pytest.raises(ValueError, match="seconds_per_step"):
        deploy_mod.load_deploy(path)
    with pytest.raises(FileNotFoundError):
        deploy_mod.load_deploy(tmp_path / "absent.toml")


def test_g1_deploy_file_is_git_ignored():
    import subprocess
    r = subprocess.run(["git", "check-ignore", "-q", "configs/local/nus_deploy.toml"], cwd=ROOT)
    if r.returncode not in (0, 1):
        pytest.skip("git not available")
    assert r.returncode == 0


def test_overrides_replace_only_the_two_geometry_keys(tmp_path):
    values, deploy_values = marker_rules(), marker_deploy()
    write_toml(tmp_path / "r.toml", values)
    write_deploy_toml(tmp_path / "d.toml", deploy_values)
    rules, deploy = rules_mod.load_rules(tmp_path / "r.toml"), deploy_mod.load_deploy(tmp_path / "d.toml")
    merged = deploy_mod.apply_overrides(rules, deploy)
    assert merged.spawn_distance == deploy_values["spawn_distance"] and merged.guard_boundary_radius == deploy_values["guard_boundary_radius"]
    assert merged.area_radius == rules.area_radius and merged.guard_count == rules.guard_count


def _files(tmp_path):
    write_toml(tmp_path / "r.toml", marker_rules())
    write_deploy_toml(tmp_path / "d.toml", marker_deploy())
    return tmp_path / "r.toml", tmp_path / "d.toml"


def test_g3_record_refuses_any_rule_or_deploy_value_float_or_int(tmp_path):
    rules_path, deploy_path = _files(tmp_path)
    rules, deploy = marker_rules(), marker_deploy()
    for payload in ({"x": rules["area_radius"]}, {"x": {"y": [rules["push_gain"]]}}, {"x": rules["episode_steps"]},
                    {"x": deploy["metres_per_unit"]}, {"x": deploy["hold_ticks"]}, {"x": deploy["apf_repulsion_gain"]},
                    {"x": f"rate {deploy['layernorm_epsilon']!r} per step"}, {"x": f"{rules['push_gain']:.6g}"}):
        with pytest.raises(ValueError):
            outputs.write_record(tmp_path / "bad.json", payload, rules_path, deploy_path=deploy_path)
        assert not (tmp_path / "bad.json").exists()
    ok = outputs.write_record(tmp_path / "ok.json", {"rate": 0.0, "flag": True, "note": "keys only", "n": BATCH}, rules_path, deploy_path=deploy_path)
    stamp = json.loads(ok.read_text())
    assert stamp["deploy_sha256"] == rules_mod.file_sha256(deploy_path) and stamp["rules_sha256"] == rules_mod.file_sha256(rules_path)
    assert set(stamp["deploy_keys"]) == set(deploy_mod.DEPLOY_KEYS)


def test_g3_record_without_deploy_file_still_refuses_rule_ints(tmp_path):
    rules_path, _ = _files(tmp_path)
    with pytest.raises(ValueError):
        outputs.write_record(tmp_path / "bad.json", {"episodes": marker_rules()["episode_steps"]}, rules_path)


def test_g3_record_refuses_the_checkpoint_architecture_and_geometry(tmp_path):
    from _nus_markers import write_synthetic_checkpoint, MARKER_ARCH
    rules_path, deploy_path = _files(tmp_path)
    ckpt = write_synthetic_checkpoint(tmp_path / "ckpt", "guard")
    for value in (MARKER_ARCH["hidden_dim"], MARKER_ARCH["hidden_dim"] // 2, float(MARKER_ARCH["hidden_dim"])):
        with pytest.raises(ValueError):
            outputs.write_record(tmp_path / "bad.json", {"width": value}, rules_path, deploy_path=deploy_path, checkpoints=[ckpt])
    stamp = json.loads(outputs.write_record(tmp_path / "ok.json", {"note": "none"}, rules_path, deploy_path=deploy_path, checkpoints=[ckpt]).read_text())
    assert len(stamp["checkpoint_sha256"][0]) == len(rules_mod.file_sha256(rules_path))


def test_marker_strings_have_enough_digits_to_search_for():
    assert distinctive([repr(marker_deploy()["metres_per_unit"]), repr(marker_deploy()["seconds_per_step"])])


# ---------------------------------------------------------------- G4 for Phase 3: marker values never reach a committed or output file
def test_g4_deploy_actor_wrapper_and_interface_chain_leaks_no_marker(tmp_path, monkeypatch, capsys):
    import contextlib
    import io
    import re
    import subprocess

    import torch

    from _nus_markers import (FAKE_COMMIT, HOLDS, MARKER_ARCH, SEED_B, load_marker_files, marker_strings, mask_paths,
                              write_fake_policy_sources, write_synthetic_checkpoint)
    from svg_training.core.game_config import load_game_cfg
    from svg_training.core.observations import OBS_DIM
    from svg_training.nus import interface as interface_mod, strategy as strategy_mod
    from svg_training.nus.actor import NusActor
    from svg_training.opponents.scripted import make_strategy
    import importlib.util

    def load_script(name):
        spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    # The captured output names the folder the deploy file is written to ("wrote <path>"). The folder is this test's choice, not a
    # leak, so it is masked before the search below; it is named with both searched numbers here, as pytest's numbered temp folder
    # is on some runs (tests/test_nus_marker_paths.py).
    tmp_path = tmp_path / f"pytest-{MARKER_ARCH['hidden_dim']}-{MARKER_ARCH['hidden_dim'] // 2}"
    rules, deploy_marker, rules_path, _ = load_marker_files(tmp_path / "inputs")
    values = marker_deploy()
    clone = tmp_path / "clone"
    write_fake_policy_sources(clone, values)
    checkpoint = write_synthetic_checkpoint(tmp_path / "checkpoint", "guard")
    local_deploy = tmp_path / "local" / "nus_deploy.toml"
    captured = io.StringIO()

    # the deploy script (code constants read from the fake clone; scale and weights names given on the command line)
    make = load_script("nus_make_local_deploy")
    monkeypatch.setattr(make, "LOCAL_OUT_DIR", tmp_path / "local")   # Phase 4: --out is refused outside configs/local/; the test's own folder stands in
    with contextlib.redirect_stdout(captured):
        make.main(["--clone", str(clone), "--geometry-from", str(checkpoint), "--metres-per-unit", repr(values["metres_per_unit"]),
                   "--seconds-per-step", repr(values["seconds_per_step"]), "--hold-ticks", str(values["hold_ticks"]),
                   "--flying-height-m", repr(values["flying_height_m"]), "--guard-weights", values["guard_weights"],
                   "--strike-weights", values["strike_weights"], "--out", str(local_deploy)])
    loaded = deploy_mod.load_deploy(local_deploy)
    for key in ("layernorm_epsilon", "disk_floor", "apf_attraction_gain", "apf_repulsion_gain", "apf_floor", "metres_per_unit"):
        assert getattr(loaded, key) == values[key], key

    # the actor loader and the wrapper (weights folder named in the deploy file, rules and deploy paths patched in)
    weights = tmp_path / "weights"
    write_synthetic_checkpoint(weights / values["guard_weights"], "guard", kind="archive")
    monkeypatch.setattr(strategy_mod, "RULES_PATH", rules_path)
    monkeypatch.setattr(strategy_mod, "DEPLOY_PATH", local_deploy)
    monkeypatch.setattr(deploy_mod, "WEIGHTS_DIR", weights)
    cfg, _ = load_game_cfg(use_local=False)
    cfg = cfg.replace(**{"rules.metres_per_unit": loaded.metres_per_unit, "rules.seconds_per_step": loaded.seconds_per_step,
                         "rules.strike_units_per_step": rules.strike_max_speed, "rules.guard_units_per_step": rules.guard_max_speed})
    strategy = make_strategy("svg_training.nus.strategy:NusPolicy", "guard", cfg, BATCH, "cpu", SEED_B)
    obs = torch.zeros(BATCH, rules.guard_count, OBS_DIM)
    for _ in range(loaded.hold_ticks * HOLDS):
        captured.write(str(strategy.act(obs).shape))
    actor = NusActor.load(weights / values["guard_weights"], team="guard", rules=rules, deploy=loaded)
    captured.write(str(actor.act_units(torch.zeros(BATCH, actor.team_size, actor.obs_dim)).shape))

    # the interface writer (under runs/; removed afterwards) and the record writer
    data = interface_mod.build_interface("guard", rules, loaded, actor.meta, FAKE_COMMIT)
    inside = deploy_mod.ROOT / "runs" / "nus_port" / "weights" / "_test_marker_chain" / "interface.toml"
    out_dir = tmp_path / "out"
    try:
        interface_mod.write_interface(inside, data)
        assert tomllib.loads(inside.read_text())["layout_id"] == interface_mod.LAYOUT_ID
    finally:
        inside.unlink(missing_ok=True)
        inside.parent.rmdir()
    outputs.write_record(out_dir / "summary.json", {"games": BATCH, "reached_fraction": 0.0}, rules_path, deploy_path=local_deploy, checkpoints=[checkpoint])
    assert deploy_mod.numeric_values(loaded)[0] in {float(v) for v in values.values() if isinstance(v, float)}  # the values really were there

    # scan: every file written outside the local inputs and the fake clone, the captured output, every file git would add
    markers = distinctive(marker_strings({**values, **{k: v for k, v in marker_rules().items()}}))
    architecture = [re.compile(rf"\b{MARKER_ARCH['hidden_dim']}\b"), re.compile(rf"\b{MARKER_ARCH['hidden_dim'] // 2}\b")]
    skip = {local_deploy, rules_path, tmp_path / "inputs" / "nus_deploy.toml"}
    hits = []
    for path in tmp_path.rglob("*"):
        if path.is_file() and path not in skip and clone not in path.parents and checkpoint not in path.parents and weights not in path.parents:
            text = path.read_text(errors="ignore")
            hits += [(str(path), m) for m in markers if m in text]
            hits += [(str(path), p.pattern) for p in architecture if p.search(text)]
    text = mask_paths(captured.getvalue() + capsys.readouterr().out, tmp_path)
    assert "sha256" in text                                   # only the folder was taken out, the script's lines are still there
    hits += [("captured output", m) for m in markers if m in text]
    hits += [("captured output", p.pattern) for p in architecture if p.search(text)]
    listing = subprocess.run(["git", "ls-files", "-co", "--exclude-standard"], cwd=ROOT, capture_output=True, text=True)
    if listing.returncode == 0:
        for rel in listing.stdout.splitlines():
            path = ROOT / rel
            if path.is_file():
                content = path.read_text(errors="ignore")
                hits += [(rel, m) for m in markers if m in content]
    assert not hits, f"marker values found in: {sorted({where for where, _ in hits})}"
