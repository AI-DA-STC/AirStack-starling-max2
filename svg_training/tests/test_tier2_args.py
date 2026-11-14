import importlib.util
import pathlib
import re
import sys
import tomllib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def mod():
    spec = importlib.util.spec_from_file_location("benchmark_tier2", ROOT / "scripts" / "benchmark_tier2.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)  # must not start Isaac
    return m


@pytest.fixture(scope="module")
def cfg():
    with open(ROOT / "configs" / "s0_benchmark.toml", "rb") as f:
        return tomllib.load(f)


def test_parse_case(mod, cfg):
    c = mod.parse_case(cfg, "t2_k8", 1024)
    assert c["drones_per_game"] == 8 and c["physics_dt_s"] == 0.005 and c["substeps"] == 10
    with pytest.raises(KeyError):
        mod.parse_case(cfg, "nope", 64)
    with pytest.raises(ValueError):
        mod.parse_case(cfg, "t2_k8", 4096)


ISAAC = r"(isaaclab\w*|isaacsim\w*|omni\w*|pxr)"


def test_only_compat_imports_isaac():
    src = ROOT / "source" / "svg_training"
    offenders = [p for p in src.rglob("*.py")
                 if "compat" not in p.parts
                 and re.search(rf"^\s*(from|import) {ISAAC}", p.read_text(), re.M)]
    assert offenders == []
    # scripts: module-top-level imports only (column 0); benchmark_tier2.py imports inside functions
    top = [p for p in (ROOT / "scripts").glob("*.py")
           if re.search(rf"^(from|import) {ISAAC}", p.read_text(), re.M)]
    assert top == []


def test_script_import_loads_no_isaac(mod):
    bad = [m for m in sys.modules if m.split(".")[0] in ("isaaclab", "isaacsim", "omni", "pxr")]
    assert bad == []


def _run_py(code: str) -> str:
    import subprocess
    from _proc import child_env, child_python
    r = subprocess.run([child_python(), "-c", code], capture_output=True, text=True, cwd=ROOT,
                       env=child_env(str(ROOT / "source")))
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def test_prelaunch_part_loads_nothing_heavy(tmp_path):
    out = tmp_path / "r.jsonl"
    out.write_text('{"case": "t2_k2", "num_games": 64}\n')
    code = f"""
import importlib.util, sys, tomllib
spec = importlib.util.spec_from_file_location("b", "scripts/benchmark_tier2.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
cfg = tomllib.load(open("configs/s0_benchmark.toml", "rb"))
m.parse_case(cfg, "t2_k2", 64)
from svg_training.bench.rows import existing_points
assert ("t2_k2", 64) in existing_points({str(out)!r})
print(sorted(x for x in sys.modules if x.split(".")[0] in ("torch", "isaaclab", "isaacsim", "omni", "pxr")))
"""
    assert _run_py(code) == "[]"


def test_rows_module_imports_without_torch():
    code = "import sys; import svg_training.bench.rows; print('torch' in sys.modules)"
    assert _run_py(code) == "False"


def test_timing_reexports_rows():
    from svg_training.bench import rows, timing
    assert timing.existing_points is rows.existing_points and timing.ROW_KEYS is rows.ROW_KEYS


def test_tier2_script_compiles_seeds_and_cites_code_sha():
    import ast
    path = ROOT / "scripts" / "benchmark_tier2.py"
    src = path.read_text()
    compile(ast.parse(src), str(path), "exec")  # compiles; nothing is written
    run_src = src[src.index("def run("):]
    # seeded before the first random draw, after the launcher (run() is only called after AppLauncher(args))
    assert run_src.index("torch.manual_seed(0)") < run_src.index("torch.rand")
    assert src.index("AppLauncher(args)") < src.index("run(args, case")
    assert '"code_sha": code_sha()' in run_src and "from svg_training.bench.rows import code_sha" in run_src


def test_tier1_script_exit_codes_documented():
    src = (ROOT / "scripts" / "benchmark_tier1.py").read_text()
    assert "sys.exit(1)" in src and "crash" in src
