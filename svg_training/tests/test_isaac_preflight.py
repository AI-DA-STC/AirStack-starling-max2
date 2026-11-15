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
DESKTOP_APP = "3905, 380, /usr/libexec/gnome-remote-desktop-daemon\n"          # under 500 MiB: allowed
BIG_FOREIGN = "777001, 3600, /isaac-sim/kit/python/bin/python3\n"               # a 3,600 MiB foreign process


def _fake_bin(tmp: pathlib.Path) -> pathlib.Path:
    """Fake nmcli / pgrep / nvidia-smi that print what the FAKE_* environment variables hold."""
    b = tmp / "bin"
    b.mkdir()
    fakes = {
        "nmcli": 'printf "%s" "${FAKE_NMCLI:-}"\n',
        "pgrep": 'if [ -n "${FAKE_PGREP:-}" ]; then printf "%s" "$FAKE_PGREP"; exit 0; fi\nexit 1\n',
        "nvidia-smi": ('case "$*" in *query-compute-apps*) printf "%s" "${FAKE_APPS:-}";;\n'
                       '  *) echo "fake nvidia-smi table";; esac\n'),
    }
    for name, body in fakes.items():
        p = b / name
        p.write_text("#!/bin/bash\n" + body)
        p.chmod(0o755)
    return b


def _run(tmp_path, nmcli: str, pgrep: str = "", apps: str = DESKTOP_APP, *flags: str) -> subprocess.CompletedProcess:
    env = {"PATH": f"{_fake_bin(tmp_path)}:/usr/bin:/bin", "FAKE_NMCLI": nmcli, "FAKE_PGREP": pgrep,
           "FAKE_APPS": apps, "HOME": str(tmp_path)}
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
