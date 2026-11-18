"""scripts/workstation/*.sh (docs/WORKSTATION_SETUP.md): syntax, --help, --dry-run without side effects, argument
checks, the pinned requirements, and no partner-specific text in the scripts. CPU only.

Owner, 18 Nov 2026 (STANDARDS section 2): NUS agreed that its game settings, names and our results may be published, so the
workstation page (docs/WORKSTATION_SETUP.md) may now name NUS's code and state its settings. The scripts stay generic: they take
every partner setting as an argument, so the word and value scans below still cover the scripts.

The dry runs use a fake HOME and fake conda, git, pip, docker, rsync, ssh, tmux, nohup and nvidia-smi on PATH. Each
fake writes a sentinel file if it is ever called, so "no side effects" means: exit 0, no sentinel, and the fake HOME
holds nothing new. None of the real tools has to be installed (the suite also runs in the container).
"""
import os
import pathlib
import re
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
WS = ROOT / "scripts" / "workstation"
SCRIPTS = ["check_machine.sh", "setup_isaaclab_host.sh", "setup_nus_jax.sh", "run_nus_job.sh", "sync_results.sh"]
FAKES = ["conda", "git", "pip", "pip3", "docker", "rsync", "ssh", "scp", "tmux", "nohup", "nvidia-smi", "tailscale"]
SYNC_NAME = "zz_test_dry_sync_must_not_exist"

# Partner-specific words that must not appear in the generic workstation scripts (case-insensitive regexes). The
# partner's override values are checked separately, read at test time from the laptop's private reference folder.
# Documents may use these words since 18 Nov 2026 (owner; STANDARDS section 2).
DENY = [r"area[-_ ]?denial", r"marmot", r"\bapf\b", r"fixed_apf", r"ma_skills", r"self_play", r"mappo", r"\bmpe\b"]
NUS_REFERENCE_LAUNCH = pathlib.Path.home() / "nus_jax_reference" / "launch_job.sh"


def _nus_config_dir() -> pathlib.Path | None:
    """The partner's config folder, found through the `cd <repo>` line of the private launch script (so its name is
    never written in this repository); None when either is missing."""
    if not NUS_REFERENCE_LAUNCH.is_file():
        return None
    m = re.search(r"^cd (\S+)", NUS_REFERENCE_LAUNCH.read_text(), flags=re.M)
    if not m:
        return None
    found = [p for p in pathlib.Path(m.group(1)).glob("*/config") if p.is_dir()]
    return found[0] if found else None


def _fake_bin(tmp: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path]:
    b = tmp / "fakebin"
    b.mkdir()
    sentinel = tmp / "SENTINEL"
    for name in FAKES:
        p = b / name
        body = f'echo "{name} $*" >> "{sentinel}"\nexit 0\n'
        if name == "conda":   # read-only queries answer without the sentinel; anything else is a side effect
            body = ('case "$*" in "info --base") echo "$HOME/miniconda3"; exit 0;; '
                    '"env list") echo "base  $HOME/miniconda3"; exit 0;; esac\n' + body)
        p.write_text("#!/bin/bash\n" + body)
        p.chmod(0o755)
    return b, sentinel


def _run(tmp_path: pathlib.Path, script: str, *args: str) -> tuple[subprocess.CompletedProcess, pathlib.Path]:
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    fakebin, sentinel = _fake_bin(tmp_path) if not (tmp_path / "fakebin").exists() else (tmp_path / "fakebin",
                                                                                       tmp_path / "SENTINEL")
    env = {"PATH": f"{fakebin}:/usr/bin:/bin", "HOME": str(home), "LANG": "C.UTF-8"}
    r = subprocess.run(["bash", str(WS / script), *args], env=env, capture_output=True, text=True, timeout=60)
    return r, sentinel


DRY_ARGS = {
    "check_machine.sh": ["--dry-run"],
    "setup_isaaclab_host.sh": ["--dry-run"],
    "setup_nus_jax.sh": ["--dry-run", "PARTNER_REPO"],
    "run_nus_job.sh": ["--dry-run", "PARTNER_REPO", "job1", "pkg/train.py", "team=one", "steps=10"],
    "sync_results.sh": ["--dry-run", "workstation", SYNC_NAME],
}
DRY_EXPECT = {
    "check_machine.sh": ["nvidia-smi", "docker run --rm --gpus all", "lsb_release", "conda env list"],
    "setup_isaaclab_host.sh": ["python=3.11", "torch==2.7.0+cu128", "download.pytorch.org/whl/cu128", "5.1.0",
                               "isaac-sim/IsaacLab.git", "v2.3.2", "isaaclab.sh", "env_isaaclab_requirements.txt",
                               "pytest -q"],
    "setup_nus_jax.sh": ["python=3.12", "PYTHONNOUSERSITE=1", "cuda13", "matplotlib", "JAX_PLATFORMS=cpu",
                         "pytest -q"],
    "run_nus_job.sh": ["PYTHONNOUSERSITE=1", "WANDB_MODE=disabled", "XLA_PYTHON_CLIENT_PREALLOCATE=false",
                       "XLA_PYTHON_CLIENT_MEM_FRACTION=0.60", "use_wandb=False", "jax.memory_fraction=0.60",
                       "pkg/train.py team=one steps=10", "nus_jax_runs/job1.log"],
    "sync_results.sh": ["rsync", f"workstation:AirStack-starling-max2/svg_training/runs/{SYNC_NAME}/",
                        "records/LEDGER.md"],
}


@pytest.mark.parametrize("script", SCRIPTS)
def test_syntax_header_and_executable(script):
    path = WS / script
    assert subprocess.run(["bash", "-n", str(path)], capture_output=True).returncode == 0
    head = path.read_text().splitlines()[:4]
    assert head[0] == "#!/usr/bin/env bash"
    assert any("UNTESTED ON THE 5090" in line for line in head), "header must say UNTESTED ON THE 5090"
    assert os.access(path, os.X_OK), f"{script} is not executable"


@pytest.mark.parametrize("script", SCRIPTS)
def test_help(script, tmp_path):
    r, sentinel = _run(tmp_path, script, "--help")
    assert r.returncode == 0, r.stderr
    assert "Exit codes" in r.stdout and script in r.stdout
    assert not sentinel.exists()


@pytest.mark.parametrize("script", SCRIPTS)
def test_dry_run_prints_and_touches_nothing(script, tmp_path):
    args = [str(tmp_path / "partner") if a == "PARTNER_REPO" else a for a in DRY_ARGS[script]]
    r, sentinel = _run(tmp_path, script, *args)
    assert r.returncode == 0, r.stdout + r.stderr
    plain = r.stdout.replace("\\", "")                      # printed commands are shell-quoted (printf %q)
    for want in DRY_EXPECT[script]:
        assert want in plain, f"{script} --dry-run does not show {want!r}"
    assert not sentinel.exists(), f"{script} --dry-run called: {sentinel.read_text()}"
    assert list((tmp_path / "home").iterdir()) == [], "a dry run wrote into HOME"
    assert not (ROOT / "runs" / SYNC_NAME).exists()


@pytest.mark.parametrize("script", SCRIPTS)
def test_unknown_option_is_refused(script, tmp_path):
    r, sentinel = _run(tmp_path, script, "--no-such-option")
    assert r.returncode == 2
    assert not sentinel.exists()


def test_run_nus_job_argument_checks(tmp_path):
    repo = str(tmp_path / "partner")
    assert _run(tmp_path, "run_nus_job.sh", "--dry-run", repo, "job1")[0].returncode == 2            # no trainer
    assert _run(tmp_path, "run_nus_job.sh", "--dry-run", repo, "../x", "t.py")[0].returncode == 2     # bad name
    assert _run(tmp_path, "run_nus_job.sh", "--dry-run", "--mem-fraction", "1.5", repo, "j", "t.py")[0].returncode == 2
    r, _ = _run(tmp_path, "run_nus_job.sh", "--dry-run", "--mem-fraction", "0.3", "--no-jax-overrides",
                repo, "j", "t.py", "--config-name=c")
    assert r.returncode == 0
    assert "XLA_PYTHON_CLIENT_MEM_FRACTION=0.3" in r.stdout and "--config-name=c" in r.stdout
    assert "jax.memory_fraction" not in r.stdout and "use_wandb=False" in r.stdout


def test_run_nus_job_refuses_existing_log(tmp_path):
    repo = tmp_path / "partner"
    repo.mkdir()
    (repo / "t.py").write_text("")
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "j.log").write_text("earlier run\n")
    py = tmp_path / "home" / "miniconda3" / "envs" / "nus_jax" / "bin" / "python"
    py.parent.mkdir(parents=True)
    py.write_text(f'#!/bin/bash\necho "python $*" >> "{tmp_path / "SENTINEL"}"\n')
    py.chmod(0o755)
    r, sentinel = _run(tmp_path, "run_nus_job.sh", "--log-dir", str(logs), str(repo), "j", "t.py")
    assert r.returncode == 6, r.stdout + r.stderr
    assert (logs / "j.log").read_text() == "earlier run\n"
    assert not sentinel.exists()


def test_sync_results_argument_checks(tmp_path):
    assert _run(tmp_path, "sync_results.sh", "--dry-run", "ws", "../etc")[0].returncode == 2
    assert _run(tmp_path, "sync_results.sh", "--dry-run", "ws", "a/b")[0].returncode == 2
    assert _run(tmp_path, "sync_results.sh", "--dry-run", "ws;rm", "name")[0].returncode == 2
    assert _run(tmp_path, "sync_results.sh", "--dry-run", "ws")[0].returncode == 2
    r, _ = _run(tmp_path, "sync_results.sh", "--dry-run", "--remote-runs", "other_runs", "--local-runs",
                str(tmp_path / "local"), "ws", "job.1")
    assert r.returncode == 0
    assert "ws:other_runs/job.1/" in r.stdout and "LEDGER" not in r.stdout
    assert not (tmp_path / "local").exists()


def test_isaaclab_ref_override(tmp_path):
    r, _ = _run(tmp_path, "setup_isaaclab_host.sh", "--dry-run", "--isaaclab-ref", "f73c331738", "--skip-tests")
    assert r.returncode == 0
    assert "checkout --detach f73c331738" in r.stdout and "skipped (--skip-tests)" in r.stdout


def test_requirements_pins():
    lines = [ln.strip() for ln in (WS / "env_isaaclab_requirements.txt").read_text().splitlines()]
    pins = {ln.split("==")[0].lower(): ln.split("==")[1] for ln in lines if "==" in ln and not ln.startswith("#")}
    assert pins["torch"] == "2.7.0+cu128" and pins["torchvision"] == "0.22.0+cu128"
    assert pins["isaacsim"].startswith("5.1.0") and pins["skrl"] == "2.1.0"
    assert "--extra-index-url https://download.pytorch.org/whl/cu128" in lines
    assert not any(ln.startswith("-e ") for ln in lines), "Isaac Lab is installed from its clone, not from here"


def _committed_workstation_files() -> list[pathlib.Path]:
    """The generic workstation scripts (not the page: owner, 18 Nov 2026)."""
    return sorted(p for p in WS.rglob("*") if p.is_file() and "__pycache__" not in p.parts)


def test_no_partner_words():
    hits = []
    for p in _committed_workstation_files():
        text = p.read_text(errors="replace")
        for pat in DENY:
            for m in re.finditer(pat, text, flags=re.IGNORECASE):
                hits.append(f"{p.relative_to(ROOT)}: {m.group(0)!r}")
    assert not hits, "partner-specific text in a committed file:\n" + "\n".join(hits)


def _distinctive_numbers(text: str) -> set[str]:
    """Number tokens with 3+ significant digits, minus years (20xx) and powers of two (too common to mean anything)."""
    out = set()
    for tok in re.findall(r"(?<![\w.])\d+(?:\.\d+)?(?![\w.])", text):
        if len(tok.replace(".", "").strip("0")) < 3 or re.fullmatch(r"20\d\d", tok):
            continue
        if tok.isdigit() and int(tok) & (int(tok) - 1) == 0:
            continue
        out.add(tok)
    return out


def test_no_partner_override_values():
    """Override values from the laptop's private launch script, and distinctive numbers from the partner's config
    folder, must not appear here. Read at test time; skipped (not passed) on a machine without them. Limit: numbers
    with one or two significant digits (0.3, 500, 8000) cannot be told apart from ordinary ones and are not searched."""
    texts = [p.read_text() for p in [NUS_REFERENCE_LAUNCH] if p.is_file()]
    cfg_dir = _nus_config_dir()
    if cfg_dir is not None:
        texts += [p.read_text(errors="replace") for p in sorted(cfg_dir.rglob("*.yaml"))]
    if not texts:
        pytest.skip("no private reference files on this machine: the value scan cannot run (a skip is not a pass)")
    tokens = set().union(*(_distinctive_numbers(t) for t in texts))
    if not tokens:
        pytest.skip("no distinctive numbers in the private reference files")
    hits = []
    for p in _committed_workstation_files():
        text = p.read_text(errors="replace")
        for tok in tokens:
            if re.search(rf"(?<![\w.]){re.escape(tok)}(?![\w.])", text):
                hits.append(f"{p.relative_to(ROOT)}: {tok}")
    assert not hits, "partner override values in a committed file:\n" + "\n".join(hits)


@pytest.mark.parametrize("driver, want", [("570.86.10", 1), ("580.178.04", 0)])
def test_check_machine_driver_gate(tmp_path, driver, want):
    """A real (not dry) run with a fake nvidia-smi: a driver older than 580 is a FAIL (exit 1). Every other check is
    read-only; the Docker check is skipped; the fake disk check sees the real disk, so the test only asserts the
    exit code when that disk has room."""
    _fake_bin(tmp_path)
    smi = tmp_path / "fakebin" / "nvidia-smi"
    smi.write_text('#!/bin/bash\ncase "$*" in *query-gpu*) echo "NVIDIA GeForce RTX 5090, ' + driver
                   + ', 32607 MiB";; esac\nexit 0\n')
    smi.chmod(0o755)
    r, sentinel = _run(tmp_path, "check_machine.sh", "--skip-docker")
    assert ("FAIL  driver" in r.stdout) == (want == 1), r.stdout
    if "FAIL  " not in r.stdout.replace("FAIL  driver", ""):
        assert r.returncode == want, r.stdout
    assert not sentinel.exists()


def test_gpu_limit_matches_preflight_and_clears_remote_desktop():
    """Owner, 18 Nov 2026: run_nus_job.sh uses the same per-process GPU limit as isaac_preflight.sh, above the home
    RTX 5090's gnome-remote-desktop-daemon (up to 589 MiB measured) so it does not need --allow-shared-gpu."""
    def limit(path):
        m = re.search(r"^GPU_MIB_MAX=(\d+)", (ROOT / path).read_text(), flags=re.M)
        assert m, path
        return int(m.group(1))
    runner, preflight = limit("scripts/workstation/run_nus_job.sh"), limit("scripts/isaac_preflight.sh")
    assert runner == preflight
    assert runner > 589


def test_setup_nus_jax_cpu_option(tmp_path):
    """--cpu (docs panel C9, owner 18 Nov 2026): a CPU-only env for NUS's code, no CUDA JAX: installs the [test] extra only and lists
    the JAX devices on the CPU."""
    r, sentinel = _run(tmp_path, "setup_nus_jax.sh", "--dry-run", "--cpu", "PARTNER_REPO")
    assert r.returncode == 0, r.stderr
    install = [ln for ln in r.stdout.splitlines() if "pip install -e" in ln]
    assert len(install) == 1 and "PARTNER_REPO\\[test\\]" in install[0] and "cuda13" not in install[0]
    assert "JAX_PLATFORMS=cpu" in [ln for ln in r.stdout.splitlines() if "jax.devices" in ln][0]
    assert not sentinel.exists()
    assert "--cpu" in _run(tmp_path, "setup_nus_jax.sh", "--help")[0].stdout
