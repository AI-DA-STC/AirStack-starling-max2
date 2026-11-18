"""Guard rails G1-G4 for the partner-game replica: partner values may never reach a committed file.

G4 (first test) fills a temporary local rules file with unusual marker values, runs the whole chain (make-local script on a
fake partner clone, loader, replica, record writer), then scans every file written outside the local file, the captured
output, and every file git would add, for the marker strings.
"""
import ast
import contextlib
import importlib.util
import io
import json
import subprocess
import textwrap

import pytest
import torch

from _nus_markers import MIN_SCANNED_FILES, BATCH, FEW_STEPS, NOT_INTEGER, ROOT, marker_rules, marker_strings, write_toml
from svg_training.nus import outputs, rules as rules_mod
from svg_training.nus.replica import NusReplica

SCRIPTS = ROOT / "scripts"


def _load_script(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _fake_clone(tmp_path, v):
    """A tiny stand-in for the partner clone with the same code shapes the script reads, filled with marker values."""
    env_dir = tmp_path / "clone/third_party/skill_learning_mpe/src/skill_learning_mpe/env"
    (env_dir / "mpe").mkdir(parents=True)
    (env_dir / "__init__.py").write_text(textwrap.dedent(f"""
        def make_env(env_id, **kwargs):
            config = {{"num_good_agents": int(1), "area_radius": 9.5, "spawn_distance": {v['spawn_distance']!r},
                      "spawn_cluster_radius": {v['spawn_cluster_radius']!r}, "agent_size": {v['agent_size']!r}}}
            return config
        """))
    (env_dir / "mpe/simple_area_denial.py").write_text(textwrap.dedent(f"""
        class SimpleAreaDenial:
            def __init__(self, *, num_good_agents: int = 3, num_adversaries: int = 3, area_radius: float = 9.5,
                         max_speed: float = 9.5, defender_max_speed: float | None = None,
                         attacker_max_speed: float | None = None, defender_safety_distance: float = 9.5,
                         attacker_safety_distance: float = 9.5, repulsion_k: float = {v['push_gain']!r},
                         repulsion_margin: float = {v['push_smoothing_margin']!r},
                         max_total_displacement: float | None = None, defender_boundary: float | None = 9.5,
                         boundary_margin: float = {v['boundary_margin']!r}, max_steps: int = 9):
                pass
            @staticmethod
            def _cap_vectors(vectors, limit):
                return vectors / max(limit, {v['norm_floor']!r})
            def displacement_corrections(self, state, intended):
                return where(distance > {v['norm_floor']!r}, a, b)
            def reset(self, key):
                a = self.area_radius * {v['start_guard_disc_fraction']!r}
                b = (self.area_radius * {v['start_static_guard_ring_fraction']!r}) * 2.0
                c = (self.spawn_cluster_radius * {v['start_static_strike_cluster_fraction']!r})
            def obs_fn(self, state):
                return where(magnitude > {v['obs_direction_floor']!r}, a, b)
        """))
    return tmp_path / "clone"


def test_g4_marker_values_never_reach_committed_or_output_files(tmp_path):
    values = marker_rules()
    markers = marker_strings(values)
    clone = _fake_clone(tmp_path, values)
    cfg = tmp_path / "environment.yaml"
    cfg.write_text(textwrap.dedent(f"""
        num_defenders: {values['guard_count']}
        num_attackers: {values['strike_count']}
        start_mode: random
        max_episode_steps: {values['episode_steps']}
        env:
          physics:
            area_radius: {values['area_radius']!r}
            defender_max_speed: {values['guard_max_speed']!r}
            attacker_max_speed: {values['strike_max_speed']!r}
            defender_safety_distance: {values['guard_safety_distance']!r}
            attacker_safety_distance: {values['strike_safety_distance']!r}
            repulsion_k: {values['push_gain']!r}
            repulsion_margin: {values['push_smoothing_margin']!r}
            max_total_displacement: {values['total_displacement_cap']!r}
            defender_boundary: {values['guard_boundary_radius']!r}
            boundary_margin: {values['boundary_margin']!r}
            max_steps: {values['episode_steps']}
        """))
    local = tmp_path / "local" / "nus_rules.toml"
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    # make-local script: writes only the local file, prints no value
    make = _load_script("nus_make_local_rules")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        make.main(["--clone", str(clone), "--config", str(cfg), "--out", str(local)])
    captured = buf.getvalue()
    assert local.exists()
    loaded = rules_mod.load_rules(local)
    assert loaded.guard_boundary_radius == pytest.approx(values["guard_boundary_radius"])
    assert loaded.start_static_guard_ring_fraction == pytest.approx(values["start_static_guard_ring_fraction"])

    # replica + record writer
    sim = NusReplica(loaded)
    gen = torch.Generator().manual_seed(0)
    state = sim.reset(BATCH, generator=gen)
    for _ in range(FEW_STEPS):
        state = sim.step(state, torch.randn(BATCH, sim.num_actors, 2, generator=gen))
        captured += str(sim.observe(state).shape)
    outputs.write_record(out_dir / "summary.json", {"games": BATCH, "reached_fraction": float(state.reached.mean())}, local)
    record = json.loads((out_dir / "summary.json").read_text())
    assert record["rules_sha256"] == rules_mod.file_sha256(local) and "area_radius" in record["rules_keys"]

    # scan: files written outside the local file (the fake clone and the yaml are inputs), captured output, files git would add
    hits = []
    for p in tmp_path.rglob("*"):
        if p.is_file() and p != local and clone not in p.parents and p != cfg:
            text = p.read_text(errors="ignore")
            hits += [(str(p), m) for m in markers if m in text]
    hits += [("captured output", m) for m in markers if m in captured]
    listing = subprocess.run(["git", "ls-files", "-co", "--exclude-standard"], cwd=ROOT, capture_output=True, text=True)
    if listing.returncode == 0:
        for rel in listing.stdout.splitlines():
            p = ROOT / rel
            if p.is_file():
                text = p.read_text(errors="ignore")
                hits += [(rel, m) for m in markers if m in text]
    assert not hits, f"marker values found in: {sorted({w for w, _ in hits})}"


def test_g1_template_has_every_key_with_local_placeholder():
    import tomllib
    tpl = tomllib.loads(rules_mod.TEMPLATE.read_text())
    assert tuple(tpl) == rules_mod.RULE_KEYS
    assert all(v == "LOCAL" for v in tpl.values())


def test_g1_loader_refuses_placeholder_missing_unknown_and_bad_type(tmp_path):
    good = marker_rules()
    path = tmp_path / "r.toml"
    write_toml(path, good)
    assert rules_mod.load_rules(path).guard_count == good["guard_count"]
    path.write_text(path.read_text().replace(f"area_radius = {good['area_radius']!r}", 'area_radius = "LOCAL"'))
    with pytest.raises(ValueError, match="area_radius"):
        rules_mod.load_rules(path)
    write_toml(path, {k: v for k, v in good.items() if k != "push_gain"})
    with pytest.raises(ValueError, match="push_gain"):
        rules_mod.load_rules(path)
    write_toml(path, {**good, "extra_key": 1.0})
    with pytest.raises(ValueError, match="extra_key"):
        rules_mod.load_rules(path)
    write_toml(path, {**good, "episode_steps": NOT_INTEGER})
    with pytest.raises(ValueError, match="episode_steps"):
        rules_mod.load_rules(path)
    with pytest.raises(FileNotFoundError):
        rules_mod.load_rules(tmp_path / "absent.toml")


def test_g1_local_file_is_git_ignored():
    r = subprocess.run(["git", "check-ignore", "-q", "configs/local/nus_rules.toml"], cwd=ROOT)
    if r.returncode not in (0, 1):
        pytest.skip("git not available")
    assert r.returncode == 0


_ALLOWED = {0, 1, -1, 2}


def test_g2_partner_facing_code_has_no_numeric_literals():
    files = (sorted((ROOT / "source/svg_training/nus").glob("*.py")) + sorted((ROOT / "scripts").glob("nus_*.py"))
             + sorted((ROOT / "tests").glob("test_nus_*.py")) + [ROOT / "scripts" / "make_nus_phase4_figures.py"])
    assert len(files) >= MIN_SCANNED_FILES
    # Phase 5 (Task P-T1): the throughput probe and its test are partner-facing; the globs above reach them, and this keeps it so
    assert {ROOT / "scripts" / "nus_phase5_probe.py", ROOT / "tests" / "test_nus_phase5_probe.py"} <= set(files)
    bad = []
    for path in files:
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Constant) and isinstance(node.value, (int, float, complex)) and not isinstance(node.value, bool):
                if node.value not in _ALLOWED:
                    bad.append(f"{path.name}:{node.lineno}")
    assert not bad, f"numeric literals other than 0, 1, -1, 2: {bad}"


def test_g3_record_refuses_rule_value_and_fixtures_only_under_runs(tmp_path):
    values = marker_rules()
    local = tmp_path / "nus_rules.toml"
    write_toml(local, values)
    with pytest.raises(ValueError):
        outputs.write_record(tmp_path / "bad.json", {"x": values["area_radius"]}, local)
    ok = outputs.write_record(tmp_path / "ok.json", {"episodes": BATCH, "note": "keys only"}, local)
    assert json.loads(ok.read_text())["rules_sha256"] == rules_mod.file_sha256(local)
    with pytest.raises(ValueError):
        outputs.require_under_runs(tmp_path / "fixtures.npz")
    assert outputs.require_under_runs(rules_mod.FIXTURE_DIR / "a.npz").name == "a.npz"
