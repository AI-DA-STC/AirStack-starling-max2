"""scripts/isaac_preflight.sh (S2b plan D13) with fake nmcli, pgrep and nvidia-smi on PATH; and the headless guard of
scripts/_isaac_app.py. CPU only: no Isaac Sim is started."""
import importlib.util
import os
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "isaac_preflight.sh"

WIFI_ONLY = "wifi:connected\nethernet:unavailable\nloopback:connected (externally)\n"
WITH_ETHERNET = "wifi:connected\nethernet:connected\nloopback:connected (externally)\n"
XRDP = "4242 /usr/sbin/xrdp --nodaemon\n"
DESKTOP_APP = "3905, 380, /usr/libexec/gnome-remote-desktop-daemon\n"          # under the limit: allowed
BIG_FOREIGN = "777001, 3600, /isaac-sim/kit/python/bin/python3\n"               # a 3,600 MiB foreign process


def _fake_bin(tmp: pathlib.Path) -> pathlib.Path:
    """Fake nmcli / pgrep / nvidia-smi that print what the FAKE_* environment variables hold."""
    b = tmp / "bin"
    b.mkdir()
    fakes = {
        "nmcli": 'printf "%s" "${FAKE_NMCLI:-}"\n',
        "pgrep": 'if [ -n "${FAKE_PGREP:-}" ]; then printf "%s" "$FAKE_PGREP"; exit 0; fi\nexit 1\n',
        "nvidia-smi": ('case "$*" in *query-compute-apps*) printf "%s" "${FAKE_APPS:-}";;\n'
                       '  *query-gpu=memory.total,memory.used*) printf "%s\\n" "${FAKE_MEM:-32607, 2000}";;\n'
                       '  *) echo "fake nvidia-smi table";; esac\n'),
        "ps": 'for a in "$@"; do last="$a"; done\neval "printf \'%s\' \\"\\${FAKE_ARGS_$last:-}\\""\n',
    }
    for name, body in fakes.items():
        p = b / name
        p.write_text("#!/bin/bash\n" + body)
        p.chmod(0o755)
    return b


def _run(tmp_path, nmcli: str, pgrep: str = "", apps: str = DESKTOP_APP, *flags: str,
         extra_env: dict | None = None) -> subprocess.CompletedProcess:
    env = {"PATH": f"{_fake_bin(tmp_path)}:/usr/bin:/bin", "FAKE_NMCLI": nmcli, "FAKE_PGREP": pgrep,
           "FAKE_APPS": apps, "HOME": str(tmp_path), **(extra_env or {})}
    return subprocess.run(["bash", str(SCRIPT), *flags], env=env, capture_output=True, text=True, timeout=60)


def test_wifi_only_with_remote_desktop_is_blocked(tmp_path):
    r = _run(tmp_path, WIFI_ONLY, XRDP)
    assert r.returncode == 10, r.stdout + r.stderr
    assert "BLOCKED" in r.stdout and "xrdp" in r.stdout


def test_ethernet_with_remote_desktop_is_fine(tmp_path):
    r = _run(tmp_path, WITH_ETHERNET, XRDP)
    assert r.returncode == 0, r.stdout + r.stderr


def test_wifi_only_without_remote_desktop_is_fine(tmp_path):
    r = _run(tmp_path, WIFI_ONLY, "")
    assert r.returncode == 0, r.stdout + r.stderr


def test_big_foreign_gpu_process_is_busy(tmp_path):
    r = _run(tmp_path, WITH_ETHERNET, "", DESKTOP_APP + BIG_FOREIGN)
    assert r.returncode == 11, r.stdout + r.stderr
    assert "777001" in r.stdout and "3600" in r.stdout


def test_5090_remote_desktop_daemon_is_allowed(tmp_path):
    """On the home RTX 5090 gnome-remote-desktop-daemon holds 546-589 MiB (owner raised the limit, 18 Nov 2026)."""
    r = _run(tmp_path, WITH_ETHERNET, "", "4538, 589, /usr/libexec/gnome-remote-desktop-daemon\n")
    assert r.returncode == 0, r.stdout + r.stderr


def test_a_nus_jax_job_still_counts_as_busy(tmp_path):
    """A partner JAX training job (about 1,700 MiB) must still block an Isaac launch."""
    r = _run(tmp_path, WITH_ETHERNET, "", DESKTOP_APP + "736800, 1732, python3\n")
    assert r.returncode == 11, r.stdout + r.stderr


def test_gpu_check_runs_even_when_blocked(tmp_path):
    r = _run(tmp_path, WIFI_ONLY, XRDP, DESKTOP_APP + BIG_FOREIGN)
    assert r.returncode == 10 and "777001" in r.stdout and "BLOCKED" in r.stdout


@pytest.mark.parametrize("flag, words", [("--approved-headless", "headless"), ("--approved-windowed", "window")])
def test_approval_turns_block_into_warning(tmp_path, flag, words):
    r = _run(tmp_path, WIFI_ONLY, XRDP, DESKTOP_APP, flag)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "WARNING" in r.stdout and "16 November 2026" in r.stdout and words in r.stdout


def test_approval_does_not_hide_a_busy_gpu(tmp_path):
    r = _run(tmp_path, WIFI_ONLY, XRDP, DESKTOP_APP + BIG_FOREIGN, "--approved-headless")
    assert r.returncode == 11 and "WARNING" in r.stdout and "777001" in r.stdout


SIBLING = "880001, 4400, python\n"                                              # one of our own training jobs
SIBLING_ARGS = {"FAKE_ARGS_880001": "python scripts/train_standin.py --game nus_hangar --settings pilot_p1b"}


def test_sibling_job_blocks_without_the_flag(tmp_path):
    r = _run(tmp_path, WITH_ETHERNET, "", DESKTOP_APP + SIBLING, extra_env=SIBLING_ARGS)
    assert r.returncode == 11, r.stdout + r.stderr


def test_sibling_job_is_allowed_with_the_flag(tmp_path):
    """Owner, 18 Nov 2026 ("parallelize the training"): our own training jobs may share the GPU."""
    r = _run(tmp_path, WITH_ETHERNET, "", DESKTOP_APP + SIBLING, "--allow-siblings", extra_env=SIBLING_ARGS)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "sibling" in r.stdout and "880001" in r.stdout


@pytest.mark.parametrize("args", ["python3 /isaac-sim/kit/kit.py --airstack", "python3 tools/sim.sh up", ""])
def test_flag_does_not_allow_a_foreign_process(tmp_path, args):
    r = _run(tmp_path, WITH_ETHERNET, "", DESKTOP_APP + "777001, 3600, python3\n", "--allow-siblings",
             extra_env={"FAKE_ARGS_777001": args})
    assert r.returncode == 11, r.stdout + r.stderr


def test_flag_needs_free_memory(tmp_path):
    r = _run(tmp_path, WITH_ETHERNET, "", DESKTOP_APP + SIBLING, "--allow-siblings",
             extra_env={**SIBLING_ARGS, "FAKE_MEM": "32607, 26000"})
    assert r.returncode == 11 and "free" in r.stdout, r.stdout + r.stderr


def test_flag_combines_with_headless_approval(tmp_path):
    r = _run(tmp_path, WIFI_ONLY, XRDP, DESKTOP_APP + SIBLING, "--approved-headless", "--allow-siblings",
             extra_env=SIBLING_ARGS)
    assert r.returncode == 0 and "WARNING" in r.stdout, r.stdout + r.stderr


def test_unknown_argument_exits_2(tmp_path):
    assert _run(tmp_path, WITH_ETHERNET, "", DESKTOP_APP, "--yes").returncode == 2


def test_prints_nvidia_smi_and_network(tmp_path):
    r = _run(tmp_path, WITH_ETHERNET)
    assert "fake nvidia-smi table" in r.stdout and "ethernet:connected" in r.stdout


@pytest.mark.skipif(importlib.util.find_spec("isaaclab") is None, reason="Isaac Lab not installed here")
def test_start_headless_refuses_without_headless():
    """scripts/_isaac_app.start_headless exits 2 before launching anything when --headless is missing."""
    code = ("import argparse, sys; sys.path.insert(0, 'scripts'); import _isaac_app; "
            "_isaac_app.start_headless(argparse.ArgumentParser())")
    env = dict(os.environ, PYTHONPATH=str(ROOT / "source"))
    r = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
    assert r.returncode == 2, r.stderr
    assert "--headless" in r.stderr
