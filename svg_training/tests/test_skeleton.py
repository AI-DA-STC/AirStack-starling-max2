import tomllib, pathlib, importlib
ROOT = pathlib.Path(__file__).resolve().parents[1]

def test_package_imports_without_isaac():
    import sys
    importlib.import_module("svg_training")
    assert not any(m.split(".")[0] in {"isaaclab", "isaacsim", "omni", "pxr"} for m in sys.modules)

def test_sweep_config_is_complete():
    cfg = tomllib.loads((ROOT / "configs/s0_benchmark.toml").read_text())
    assert cfg["gates"] == {"tests_pass": True, "sweep_complete": True, "repeat_spread_max": 0.10, "nan_count_max": 0}
    assert cfg["timing"] == {"warmup_steps": 50, "timed_steps": 200, "repeats": 2}
    assert len(cfg["tier1"]) == 13 and len(cfg["tier2"]) == 8
    for case in cfg["tier1"]:
        assert set(case) == {"name", "guards", "strikes", "world", "n_obstacles", "n_rays", "line_of_sight", "num_games"}

def test_no_yaml_or_launch_paths():
    # The one allowed exception is docker/Dockerfile (STANDARDS §9 rule 2: it carries a change-log line).
    bad = [p for p in ROOT.rglob("*") if "runs" not in p.parts and (p.suffix in {".yaml", ".yml"} or p.name.startswith(("Dockerfile", "docker-compose")) or p.name == "launch")]
    assert [p.relative_to(ROOT).as_posix() for p in bad] == ["docker/Dockerfile"]
