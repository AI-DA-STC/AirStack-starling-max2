import json, subprocess, sys, pathlib, torch
from _proc import child_env, child_python
import pytest
from svg_training.bench import timing
ROOT = pathlib.Path(__file__).resolve().parents[1]

def test_measure_counts_steps_and_nans():
    calls = []
    def step():
        calls.append(1); return {"pos_m": torch.tensor([float("nan")]), "reset_fraction": torch.tensor(0.25)}
    r = timing.measure(step, warmup_steps=3, timed_steps=10, device="cpu", min_warmup_s=0.0)
    assert len(calls) == 13 and r["steps_per_s"] > 0 and r["nan_count"] == 10 and abs(r["mean_reset_fraction"] - 0.25) < 1e-6

def test_measure_synchronises_on_cuda(monkeypatch):
    import types
    ev = []
    monkeypatch.setattr(torch.cuda, "synchronize", lambda *a, **k: ev.append("sync"))
    monkeypatch.setattr(torch.cuda, "reset_peak_memory_stats", lambda *a, **k: None)
    monkeypatch.setattr(torch.cuda, "max_memory_allocated", lambda *a, **k: 0)
    monkeypatch.setattr(timing, "time", types.SimpleNamespace(perf_counter=lambda: ev.append("clock") or float(len(ev))))
    timing.measure(lambda: ev.append("step"), warmup_steps=2, timed_steps=3, device="cuda", min_warmup_s=0.0)
    i = ev.index("sync")
    assert set(ev[:i]) == {"step"}
    assert ev[i:] == ["sync", "clock"] + ["step"] * 3 + ["sync", "clock"]

def test_out_of_memory_becomes_a_row():
    def boom(): raise torch.OutOfMemoryError("x")
    rows = timing.run_case(boom, lambda e: (lambda: None), {"name": "c", "guards": 1, "strikes": 1}, 64,
                           {"warmup_steps": 1, "timed_steps": 1, "repeats": 2}, "cpu", min_warmup_s=0.0)
    assert len(rows) == 1 and rows[0]["status"] == "oom" and rows[0]["num_games"] == 64

def test_cli_smoke(tmp_path):
    out = tmp_path / "r.jsonl"
    subprocess.run([child_python(), "scripts/benchmark_tier1.py", "--config", "configs/s0_benchmark.toml", "--out", str(out),
                    "--device", "cpu", "--only", "t1_2v1_open", "--max-games", "256", "--min-warmup-s", "0"], cwd=ROOT, check=True,
                   env=child_env())
    rows = [json.loads(l) for l in out.read_text().splitlines()]
    assert len(rows) == 2 and {r["status"] for r in rows} == {"ok"} and rows[0]["drones_per_game"] == 3
    assert rows[0]["drone_steps_per_s"] == rows[0]["env_steps_per_s"] * 3


CFG = ["--config", "configs/s0_benchmark.toml", "--device", "cpu", "--only", "t1_2v1_open", "--min-warmup-s", "0"]
ENV = child_env()

def _cli(*extra):
    return subprocess.run([child_python(), "scripts/benchmark_tier1.py", *CFG, *extra], cwd=ROOT, env=ENV,
                          capture_output=True, text=True)

def test_oom_in_second_repeat_gives_one_row():
    state = {"n": 0}
    def make(): state["n"] += 1; return state["n"]
    def step_of(e):
        def step():
            if e == 2: raise torch.OutOfMemoryError("x")
        return step
    rows = timing.run_case(make, step_of, {"name": "c", "guards": 1, "strikes": 1}, 8,
                           {"warmup_steps": 1, "timed_steps": 1, "repeats": 2}, "cpu", min_warmup_s=0.0)
    assert len(rows) == 1 and rows[0]["status"] == "oom" and rows[0]["repeat"] == 0
    assert rows[0]["env_steps_per_s"] is None

def test_infinity_counts_as_non_finite():
    r = timing.measure(lambda: {"pos_m": torch.tensor([float("inf")])}, warmup_steps=0, timed_steps=4, device="cpu", min_warmup_s=0.0)
    assert r["nan_count"] == 4

def test_drones_per_game_key():
    rows = timing.run_case(lambda: None, lambda e: (lambda: None), {"name": "t2", "tier": 2, "drones_per_game": 5}, 4,
                           {"warmup_steps": 1, "timed_steps": 1, "repeats": 1}, "cpu", min_warmup_s=0.0)
    assert rows[0]["drones_per_game"] == 5 and rows[0]["tier"] == 2

def test_cli_rerun_skips_and_other_exit_codes(tmp_path):
    out = tmp_path / "r.jsonl"
    p = _cli("--out", str(out), "--max-games", "256")
    assert p.returncode == 0
    n = len(out.read_text().splitlines())
    p = _cli("--out", str(out), "--max-games", "256")
    assert p.returncode == 0 and "skip t1_2v1_open 256: already in" in p.stdout
    assert len(out.read_text().splitlines()) == n
    assert _cli("--out", str(tmp_path / "x.jsonl"), "--max-games", "1").returncode == 3
    q = subprocess.run([child_python(), "scripts/benchmark_tier1.py", *CFG[:-3], "nope", "--min-warmup-s", "0", "--out", str(tmp_path / "y.jsonl")],
                       cwd=ROOT, env=ENV, capture_output=True, text=True)
    assert q.returncode == 3 and "t1_2v1_open" in q.stdout

def test_cli_broken_existing_line_exits_1(tmp_path):
    out = tmp_path / "r.jsonl"
    out.write_text('{"case": "a", "num_games": 1}\nnot json\n')
    p = _cli("--out", str(out), "--max-games", "256")
    assert p.returncode == 1 and "line 2" in p.stdout


def test_min_warmup_s_both_conditions(monkeypatch):
    import types
    clock = {"t": 0.0}
    monkeypatch.setattr(timing, "time", types.SimpleNamespace(perf_counter=lambda: clock["t"]))
    steps = []
    def step():
        steps.append(1); clock["t"] += 0.125  # each step takes 0.125 s of fake time (exact in binary)
    # time condition dominates: 5 minimum steps, but 1.0 s of warm-up needs 8 steps, then 4 timed
    timing.measure(step, warmup_steps=5, timed_steps=4, device="cpu", min_warmup_s=1.0)
    assert len(steps) == 8 + 4
    # step condition dominates: the time is already reached after 3 steps, yet 20 warm-up steps are run
    steps.clear(); clock["t"] = 0.0
    timing.measure(step, warmup_steps=20, timed_steps=4, device="cpu", min_warmup_s=0.2)
    assert len(steps) == 20 + 4


def test_min_warmup_s_not_timed(monkeypatch):
    import types
    clock = {"t": 0.0}
    monkeypatch.setattr(timing, "time", types.SimpleNamespace(perf_counter=lambda: clock["t"]))
    def step():
        clock["t"] += 0.125
    r = timing.measure(step, warmup_steps=1, timed_steps=10, device="cpu", min_warmup_s=3.0)
    assert r["steps_per_s"] == pytest.approx(8.0)  # only the 10 timed steps of 0.125 s count


def test_crash_becomes_a_row_and_sweep_continues():
    def make(): raise ValueError("bad point")
    rows = timing.run_case(make, lambda e: (lambda: None), {"name": "c", "guards": 1, "strikes": 1}, 32,
                           {"warmup_steps": 1, "timed_steps": 1, "repeats": 2}, "cpu", min_warmup_s=0.0)
    assert len(rows) == 1 and rows[0]["status"] == "crash" and rows[0]["repeat"] == 0
    assert rows[0]["env_steps_per_s"] is None and rows[0]["error"].startswith("ValueError: bad point")
    ok = timing.run_case(lambda: None, lambda e: (lambda: None), {"name": "c2", "guards": 1, "strikes": 1}, 32,
                         {"warmup_steps": 1, "timed_steps": 1, "repeats": 2}, "cpu", min_warmup_s=0.0)
    assert [r["status"] for r in ok] == ["ok", "ok"]  # the next point is unaffected


def test_rows_carry_code_sha():
    from svg_training.bench.rows import code_sha
    rows = timing.run_case(lambda: None, lambda e: (lambda: None), {"name": "c", "guards": 1, "strikes": 1}, 4,
                           {"warmup_steps": 1, "timed_steps": 1, "repeats": 1}, "cpu", min_warmup_s=0.0)
    assert rows[0]["code_sha"] == code_sha() and len(rows[0]["code_sha"]) == 12


def test_code_sha_stable_and_changes(tmp_path):
    from svg_training.bench.rows import code_sha
    for d in ("source", "scripts", "configs"):
        (tmp_path / d).mkdir()
    (tmp_path / "source" / "a.py").write_text("x = 1\n")
    (tmp_path / "configs" / "c.toml").write_text("a = 1\n")
    a = code_sha(tmp_path)
    assert a == code_sha(tmp_path) and len(a) == 12 and int(a, 16) >= 0
    (tmp_path / "source" / "__pycache__").mkdir()
    (tmp_path / "source" / "__pycache__" / "a.pyc").write_text("junk")
    assert code_sha(tmp_path) == a  # __pycache__ is skipped
    (tmp_path / "docs").mkdir(); (tmp_path / "docs" / "n.md").write_text("ignored")
    assert code_sha(tmp_path) == a  # other folders are not part of it
    (tmp_path / "scripts" / "run.sh").write_text("echo\n")
    b = code_sha(tmp_path)
    assert b != a  # a new file
    (tmp_path / "source" / "a.py").write_text("x = 2\n")
    assert code_sha(tmp_path) != b  # a changed file


def test_cli_exit_1_when_a_point_crashes(tmp_path, monkeypatch):
    # in-process run of main with one crashing point and one ok point
    import importlib.util, torch as _t
    spec = importlib.util.spec_from_file_location("bt1", ROOT / "scripts" / "benchmark_tier1.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    real = m.Tier1BenchEnv
    def flaky(cfg):
        if cfg.num_games == 256: raise RuntimeError("boom")
        return real(cfg)
    monkeypatch.setattr(m, "Tier1BenchEnv", flaky)
    out = tmp_path / "r.jsonl"
    monkeypatch.setattr(sys, "argv", ["x", "--config", str(ROOT / "configs/s0_benchmark.toml"), "--out", str(out),
                                      "--device", "cpu", "--only", "t1_1v1_open", "--max-games", "1024",
                                      "--min-warmup-s", "0"])
    with pytest.raises(SystemExit) as e:
        m.main()
    assert e.value.code == 1
    rows = [json.loads(l) for l in out.read_text().splitlines()]
    assert {(r["num_games"], r["status"]) for r in rows} == {(256, "crash"), (1024, "ok")}


def test_cuda_warmup_synchronises_before_clock_check(monkeypatch):
    import types
    ev, clock = [], {"t": 0.0}
    monkeypatch.setattr(torch.cuda, "synchronize", lambda *a, **k: ev.append("sync"))
    monkeypatch.setattr(torch.cuda, "reset_peak_memory_stats", lambda *a, **k: None)
    monkeypatch.setattr(torch.cuda, "max_memory_allocated", lambda *a, **k: 0)
    def now():
        ev.append("clock"); return clock["t"]
    monkeypatch.setattr(timing, "time", types.SimpleNamespace(perf_counter=now))
    def step():
        ev.append("step"); clock["t"] += 0.5
    timing.measure(step, warmup_steps=1, timed_steps=1, device="cuda", min_warmup_s=1.0)
    # the clock check inside the warm-up is always directly preceded by a synchronise
    checks = [i for i, e in enumerate(ev) if e == "clock"][1:3]
    assert all(ev[i - 1] == "sync" for i in checks)
