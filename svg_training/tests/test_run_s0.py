"""run_s0.sh front door: argument checks, config-hash gate and --dry-run output. Never runs a real sweep."""
import hashlib
import os
import pathlib
import re
import subprocess
import tomllib

import pytest
from _proc import child_python

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_s0.sh"
CONFIG = ROOT / "configs" / "s0_benchmark.toml"
NAME = "2099-01-01_s0_pytest"


def run(*args):
    return subprocess.run(["bash", str(SCRIPT), *args], capture_output=True, text=True, cwd=ROOT, timeout=60)


def real_hash():
    return hashlib.sha256(CONFIG.read_bytes()).hexdigest()


def assert_nothing_created():
    assert not (ROOT / "runs" / NAME).exists()
    assert not list((ROOT / "records").glob(f"{NAME}*"))


def isaac_running():
    try:
        out = subprocess.run(["docker", "ps", "--format", "{{.Names}}"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return out.returncode == 0 and re.search(r"isaac|airstack", out.stdout, re.I) is not None


def tier2_points():
    cfg = tomllib.loads(CONFIG.read_text())
    return sum(len(c["num_games"]) for c in cfg["tier2"])


def test_syntax():
    assert subprocess.run(["bash", "-n", str(SCRIPT)]).returncode == 0


def test_bad_name():
    r = run("not-a-name", real_hash())
    assert r.returncode == 64
    assert "Usage" in r.stdout + r.stderr


def test_bad_hash_format():
    assert run(NAME, "abc123").returncode == 64
    assert run(NAME, "Z" * 64).returncode == 64
    assert_nothing_created()


def test_wrong_hash():
    r = run(NAME, "0" * 64)
    assert r.returncode == 65
    assert "config differs from the approved one" in r.stdout + r.stderr
    assert_nothing_created()


def test_dry_run():
    if isaac_running():
        pytest.skip("an isaac/airstack container is running")
    r = run("--dry-run", NAME, real_hash())
    assert r.returncode == 0, r.stdout + r.stderr
    dry = [ln for ln in r.stdout.splitlines() if ln.startswith("DRY: ")]
    t2 = [ln for ln in dry if "benchmark_tier2.py" in ln]
    assert len(t2) == tier2_points()
    assert len([ln for ln in dry if "timeout -k 60 1800" in ln]) == tier2_points()
    assert any("benchmark_tier1.py" in ln for ln in dry)
    mk = [ln for ln in dry if "make_record.py" in ln]
    assert len(mk) == 1 and "--seeds" in mk[0]
    cfg = tomllib.loads(CONFIG.read_text())
    first = cfg["tier2"][0]
    assert f"--case {first['name']} --num-games {min(first['num_games'])} " in t2[0]
    # new elements: TERM for isaaclab.sh, per-point log, seeds text, GPU check, --note and --flags-file
    assert all("env TERM=xterm PYTHONPATH=source" in ln for ln in t2)
    assert all(f"tier2_logs/{ln.split('--case ')[1].split()[0]}_{ln.split('--num-games ')[1].split()[0]}.log" in ln
               for ln in t2)
    assert ("--seeds 0 for every case and repeat, both tiers (Tier1BenchCfg.seed default; "
            "torch.manual_seed(0) in tier 2)") in mk[0]
    assert "--note" in mk[0] and "--flags-file" in mk[0] and "overflow_points.txt" in mk[0]
    assert any("exit 68" in ln and "python|kit|isaac|omni" in ln for ln in dry)
    assert any("code_sha" in ln and "preflight.txt" in ln for ln in dry)
    assert_nothing_created()


def test_dry_run_tier1_only():
    if isaac_running():
        pytest.skip("an isaac/airstack container is running")
    r = run("--dry-run", "--tier1-only", NAME, real_hash())
    assert r.returncode == 0, r.stdout + r.stderr
    assert "benchmark_tier2.py" not in r.stdout
    assert "make_record.py" not in r.stdout
    assert "benchmark_tier1.py" in r.stdout
    assert_nothing_created()


def bash(snippet: str, stdin: str = "") -> subprocess.CompletedProcess:
    """Source the script (functions only: main does not run when sourced) and run a snippet."""
    env = dict(os.environ)
    return subprocess.run(["bash", "-c", f"source {SCRIPT}\n{snippet}"], input=stdin, capture_output=True,
                          text=True, cwd=ROOT, timeout=120, env=env)


def test_busy_gpu_procs_filter():
    apps = ("3905, /usr/libexec/gnome-remote-desktop-daemon\n"
            "4100, /home/x/miniconda3/envs/env_isaaclab/bin/python\n"
            "4200, /home/x/.local/share/ov/pkg/isaac-sim/kit/kit\n"
            "4300, /usr/lib/xorg/Xorg\n"
            "4400, /opt/OMNIverse/omni.launcher\n"
            "4500, /usr/bin/Python3.11\n")
    r = bash("busy_gpu_procs", apps)
    assert r.returncode == 0
    got = [ln.split(",")[0] for ln in r.stdout.splitlines()]
    assert got == ["4100", "4200", "4400", "4500"]
    r = bash("busy_gpu_procs", "3905, /usr/libexec/gnome-remote-desktop-daemon\n")
    assert r.returncode == 0 and r.stdout == ""
    assert bash("busy_gpu_procs", "").returncode == 0


def test_stop_child_ends_the_process_group():
    r = bash("setsid bash -c 'sleep 300 & sleep 300' &\nCHILD=$!\nsleep 0.5\n"
             "group_alive $CHILD && echo alive-before\nstop_child\n"
             "group_alive $CHILD && echo alive-after || echo gone")
    assert r.returncode == 0, r.stderr
    assert r.stdout.split() == ["alive-before", "gone"]


def tier2_loop(tmp_path, fake_body: str, first_ok: bool = False):
    """Run run_tier2 with a stub standing in for the Isaac command; returns (result, run dir)."""
    run_dir = tmp_path / "run"
    (run_dir / "tier2_logs").mkdir(parents=True)
    snippet = f"""
RUN_DIR={run_dir}; RESULTS={run_dir}/results.jsonl; GPU_NAME=g; COMMIT=c; CODE_SHA=abc123abc123
wait_gpu_idle() {{ return 0; }}
tier2_cmd() {{ CMD=(bash -c '{fake_body}'); }}
run_tier2
echo "STOPPED=[$TIER2_STOPPED]"
"""
    return bash(snippet), run_dir


def test_tier2_first_point_oom_stops_loop_and_writes_oom_row(tmp_path):
    import json
    r, run_dir = tier2_loop(tmp_path, "echo PxgCudaDeviceMemoryAllocator fail to allocate; exit 1")
    assert r.returncode == 0, r.stderr + r.stdout
    rows = [json.loads(ln) for ln in (run_dir / "results.jsonl").read_text().splitlines()]
    assert len(rows) == 1  # the loop stopped at the first point
    assert rows[0]["status"] == "oom" and rows[0]["tier"] == 2 and rows[0]["code_sha"] == "abc123abc123"
    assert "STOPPED=[tier 2 stopped after its first point" in r.stdout and "t2_k2 at 64 games" in r.stdout
    assert (run_dir / "tier2_logs" / "t2_k2_64.log").exists()
    assert len((run_dir / "tier2.log").read_text().splitlines()) == 1  # one summary line per point


def test_tier2_crash_and_overflow_flag(tmp_path):
    import json
    r, run_dir = tier2_loop(tmp_path, "echo GPU buffer overflow in PhysX; exit 3")
    rows = [json.loads(ln) for ln in (run_dir / "results.jsonl").read_text().splitlines()]
    assert rows[0]["status"] == "crash" and rows[0]["note"] == "exit code 3"
    assert (run_dir / "overflow_points.txt").read_text() == "t2_k2 64\n"


def test_tier2_exit_2_first_point_stops_without_row(tmp_path):
    r, run_dir = tier2_loop(tmp_path, "echo cannot load; exit 2")
    assert not (run_dir / "results.jsonl").exists()
    assert "STOPPED=[tier 2 stopped after its first point" in r.stdout


def test_tier2_gpu_busy_gives_crash_row(tmp_path):
    import json
    run_dir = tmp_path / "run"
    (run_dir / "tier2_logs").mkdir(parents=True)
    r = bash(f"""
RUN_DIR={run_dir}; RESULTS={run_dir}/results.jsonl; GPU_NAME=g; COMMIT=c; CODE_SHA=abc123abc123
wait_gpu_idle() {{ GPU_BUSY="4100, python"; return 1; }}
run_tier2
""")
    rows = [json.loads(ln) for ln in (run_dir / "results.jsonl").read_text().splitlines()]
    assert len(rows) == 1 and rows[0]["status"] == "crash" and rows[0]["note"] == "gpu busy"


def test_tier2_continues_after_ok_first_point(tmp_path):
    run_dir = tmp_path / "run"
    (run_dir / "tier2_logs").mkdir(parents=True)
    stub = tmp_path / "stub.sh"  # stands in for the Isaac command: writes an ok row for its point
    stub.write_text(f"#!/usr/bin/env bash\nprintf '{{\"case\": \"%s\", \"num_games\": %s, \"status\": \"ok\"}}\\n' "
                    f"\"$1\" \"$2\" >> {run_dir}/results.jsonl\n")
    r = bash(f"""
RUN_DIR={run_dir}; RESULTS={run_dir}/results.jsonl; GPU_NAME=g; COMMIT=c; CODE_SHA=abc123abc123
wait_gpu_idle() {{ return 0; }}
tier2_cmd() {{ CMD=(bash {stub} "$1" "$2"); }}
run_tier2
echo "STOPPED=[$TIER2_STOPPED]"
""")
    assert "STOPPED=[]" in r.stdout, r.stdout + r.stderr
    assert len((run_dir / "results.jsonl").read_text().splitlines()) == tier2_points()


def test_exit_handler_writes_aborted_only_on_error(tmp_path):
    aborted = ROOT / "records" / "2099-01-02_s0_exitcheck_ABORTED_record.md"
    snippet = ("NAME=2099-01-02_s0_exitcheck; RUN_DIR=runs/none; RESULTS=/nonexistent; STEP='[7/9] tier 1 sweep'\n"
               "set +e; FINISHED={f}; INTERRUPTED={i}\n(exit {rc}); on_exit\n")
    try:
        for f, i, rc in ((1, 0, 3), (0, 0, 0), (0, 1, 3)):  # finished, normal end, interrupt handled elsewhere
            assert bash(snippet.format(f=f, i=i, rc=rc)).returncode == 0
            assert not aborted.exists()
        r = bash(snippet.format(f=0, i=0, rc=3))
        assert r.returncode == 0 and aborted.exists()
        text = aborted.read_text()
        assert text.startswith("Simulator: training simulator") and "ABORTED" in text
        assert "left through an error (exit 3)" in text and "[7/9] tier 1 sweep" in text
    finally:
        aborted.unlink(missing_ok=True)
    assert "trap on_exit EXIT" in SCRIPT.read_text() and "trap on_interrupt INT TERM HUP" in SCRIPT.read_text()


def run_env(env_extra, *args):
    import os
    env = {k: v for k, v in os.environ.items() if not k.startswith("SVG_")}
    env.update(env_extra)
    return subprocess.run(["bash", str(SCRIPT), *args], capture_output=True, text=True, cwd=ROOT, timeout=60, env=env)


def tier2_lines(r):
    return [ln for ln in r.stdout.splitlines() if ln.startswith("DRY: ") and "benchmark_tier2.py" in ln]


@pytest.mark.skipif(os.environ.get("SVG_IN_CONTAINER") == "1", reason="host form only")
def test_dry_run_host_form_uses_conda_and_home():
    if isaac_running():
        pytest.skip("an isaac/airstack container is running")
    r = run_env({}, "--dry-run", NAME, real_hash())
    assert r.returncode == 0, r.stdout + r.stderr
    t2 = tier2_lines(r)
    assert len(t2) == tier2_points()
    home = os.environ["HOME"]
    assert all("conda run -n env_isaaclab" in ln and f"{home}/IsaacLab/isaaclab.sh -p scripts/benchmark_tier2.py" in ln
               for ln in t2)


def test_dry_run_container_form_has_no_conda():
    if isaac_running():
        pytest.skip("an isaac/airstack container is running")
    # --dry-run runs $PY for the tier 2 point list, so SVG_PY must be a working interpreter here
    r = run_env({"SVG_IN_CONTAINER": "1", "SVG_PY": child_python(), "SVG_ISAACLAB": "/y/isaaclab.sh"},
                "--dry-run", NAME, real_hash())
    assert r.returncode == 0, r.stdout + r.stderr
    t2 = tier2_lines(r)
    assert len(t2) == tier2_points()
    assert all("/y/isaaclab.sh -p scripts/benchmark_tier2.py" in ln and "conda run" not in ln for ln in t2)
    assert all("timeout -k 60 1800 env TERM=xterm PYTHONPATH=source /y/isaaclab.sh" in ln for ln in t2)
    assert_nothing_created()


def retry_loop(tmp_path, kind):
    """Run run_tier2 over the first point with a stateful stub. kind: startup_then_ok, mass_then_139, startup_twice."""
    run_dir = tmp_path / "run"
    (run_dir / "tier2_logs").mkdir(parents=True)
    stub = tmp_path / "stub.sh"
    stub.write_text(f"""#!/usr/bin/env bash
case="$1"; n="$2"; kind={kind}
cnt={tmp_path}/cnt_${{case}}_${{n}}
c=$(cat $cnt 2>/dev/null || echo 0); echo $((c+1)) > $cnt
ok() {{ printf '{{"case": "%s", "num_games": %s, "status": "ok"}}\\n' "$case" "$n" >> {run_dir}/results.jsonl; }}
if [ "$kind" = mass_then_139 ]; then echo "mass_kg=0.03"; exit 139; fi
if [ "$kind" = startup_twice ]; then echo "Segmentation fault"; exit 139; fi
if [ "$c" -eq 0 ] && [ "$n" = 64 ] && [ "$case" = t2_k2 ]; then echo "Segmentation fault"; exit 139; fi
echo "mass_kg=0.03"; ok
""")
    r = bash(f"""
RUN_DIR={run_dir}; RESULTS={run_dir}/results.jsonl; GPU_NAME=g; COMMIT=c; CODE_SHA=abc123abc123
wait_gpu_idle() {{ return 0; }}
tier2_cmd() {{ CMD=(bash {stub} "$1" "$2"); }}
run_tier2
echo "STOPPED=[$TIER2_STOPPED]"
""")
    return r, run_dir, tmp_path


def read_rows(run_dir):
    import json
    p = run_dir / "results.jsonl"
    return [json.loads(ln) for ln in p.read_text().splitlines()] if p.exists() else []


def test_tier2_startup_crash_retried_once_then_ok(tmp_path):
    r, run_dir, _ = retry_loop(tmp_path, "startup_then_ok")
    assert r.returncode == 0, r.stderr + r.stdout
    rows = read_rows(run_dir)
    assert len(rows) == tier2_points() and all(x["status"] == "ok" for x in rows)
    lines = (run_dir / "retried_points.txt").read_text().splitlines()
    assert lines == ["t2_k2 64: start-up crash (exit 139), retried once"]
    assert (run_dir / "tier2_logs" / "t2_k2_64.startup_crash1.log").read_text().startswith("Segmentation")
    assert "mass_kg=" in (run_dir / "tier2_logs" / "t2_k2_64.log").read_text()
    assert "STOPPED=[]" in r.stdout


def test_tier2_crash_after_mass_line_is_not_retried(tmp_path):
    r, run_dir, _ = retry_loop(tmp_path, "mass_then_139")
    rows = read_rows(run_dir)
    assert len(rows) == 1 and rows[0]["status"] == "crash" and rows[0]["note"] == "exit code 139"
    assert not (run_dir / "retried_points.txt").exists()
    assert not list((run_dir / "tier2_logs").glob("*startup_crash*"))
    assert (tmp_path / "cnt_t2_k2_64").read_text().strip() == "1"


def test_tier2_startup_crash_twice_gives_crash_row(tmp_path):
    r, run_dir, _ = retry_loop(tmp_path, "startup_twice")
    rows = read_rows(run_dir)
    assert len(rows) == 1 and rows[0]["status"] == "crash" and rows[0]["note"] == "exit code 139"
    assert (tmp_path / "cnt_t2_k2_64").read_text().strip() == "2"
    assert len((run_dir / "retried_points.txt").read_text().splitlines()) == 1
    assert "STOPPED=[tier 2 stopped after its first point" in r.stdout


def test_record_cmd_passes_retried_file_only_when_it_exists(tmp_path):
    r = bash(f"RUN_DIR={tmp_path}; RESULTS=x; NAME=n; TESTS_PASSED=yes\nrecord_cmd\nprintf '%s ' \"${{CMD[@]}}\"")
    assert "--retried-file" not in r.stdout
    (tmp_path / "retried_points.txt").write_text("t2_k2 64: start-up crash (exit 139), retried once\n")
    r = bash(f"RUN_DIR={tmp_path}; RESULTS=x; NAME=n; TESTS_PASSED=yes\nrecord_cmd\nprintf '%s ' \"${{CMD[@]}}\"")
    assert f"--retried-file {tmp_path}/retried_points.txt" in r.stdout
