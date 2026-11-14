import os
"""Docker packaging: static checks only. No docker daemon, no GPU, no build."""
import pathlib
import re
import shutil
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
DOCKER = ROOT / "docker"


@pytest.mark.parametrize("name", ["build.sh", "run.sh"])
def test_scripts_parse(name):
    assert subprocess.run(["bash", "-n", str(DOCKER / name)]).returncode == 0


def test_dockerfile_starts_with_arg_and_from():
    lines = [ln.strip() for ln in (DOCKER / "Dockerfile").read_text().splitlines()]
    instructions = [ln for ln in lines if ln and not ln.startswith("#")]
    assert instructions[0] == "ARG ISAACLAB_IMAGE=nvcr.io/nvidia/isaac-lab:2.3.2"
    assert instructions[1] == "FROM ${ISAACLAB_IMAGE}"


def test_dockerfile_never_imports_isaaclab():
    for ln in (DOCKER / "Dockerfile").read_text().splitlines():
        assert not re.search(r"import isaaclab", ln), ln
    assert "find_spec('isaaclab')" in (DOCKER / "Dockerfile").read_text()


def test_run_print_line():
    if shutil.which("docker") is None:
        pytest.skip("no docker binary")
    r = subprocess.run(["bash", str(DOCKER / "run.sh"), "--print", "echo", "hi"], capture_output=True, text=True,
                       cwd=ROOT, timeout=60)
    assert r.returncode == 0, r.stderr
    out = r.stdout
    for part in ("--gpus all", "--entrypoint bash", ":/workspace/svg_training", "ACCEPT_EULA=Y"):
        assert part in out, part
    assert "--network host" not in out
    assert "SVG_COMMIT=" in out and "TZ=" in out
    if os.path.exists("/etc/localtime"):
        assert "/etc/localtime:/etc/localtime:ro" in out
    assert "svg-training-isaac-cache-kit" in out


def test_no_yaml_or_compose_in_docker_folder():
    bad = [p.name for p in DOCKER.rglob("*") if p.suffix in (".yaml", ".yml") or p.name.startswith("docker-compose")]
    assert bad == []
