"""How tests start a child Python.

Host: SVG_PY is unset, so this is sys.executable. Container: SVG_PY is /usr/local/bin/svg-python (docker/Dockerfile),
Isaac Sim's python.sh environment without its exit-code flattening, so exit codes the tests check survive."""
import os
import sys


def child_python() -> str:
    return os.environ.get("SVG_PY") or sys.executable


def child_env(pythonpath: str = "source") -> dict:
    """A copy of the environment (CUDA needs it) with pythonpath put in front of any PYTHONPATH."""
    env = dict(os.environ)
    old = env.get("PYTHONPATH")
    env["PYTHONPATH"] = pythonpath + (os.pathsep + old if old else "")
    return env
