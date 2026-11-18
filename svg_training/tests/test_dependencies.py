"""pyproject.toml lists every package the code imports (docs panel C4, owner 18 Nov 2026).

Every top-level import in ``source/``, ``scripts/`` and ``tests/`` is the standard library, this folder's own code, a package
listed in ``[project] dependencies`` or the ``test`` extra, or one of the named groups below that ``pip install -e .[test]`` does not
give (Isaac Sim / Isaac Lab, ROS 2, NUS's JAX environment, the flight stack). A new import of anything else fails here until it is
listed: a plain CPU venv built from pyproject.toml alone must run the suite.
"""
import ast
import pathlib
import re
import sys
import tomllib

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCANNED = ("source", "scripts", "tests")

# import name -> distribution name, where they differ
DIST_OF = {"cv2": "opencv-python-headless", "yaml": "pyyaml", "imageio_ffmpeg": "imageio-ffmpeg", "PIL": "pillow"}

# imports that pip install -e .[test] never provides, by where they come from
NOT_FROM_PIP = {
    "Isaac Sim / Isaac Lab (conda env_isaaclab or the container; tests skip without it)":
        {"isaaclab", "isaaclab_assets", "isaaclab_contrib", "isaacsim", "omni", "pxr", "carb"},
    "ROS 2 (bag tools and the virtual stick, run on the flight laptop)":
        {"rclpy", "rosbag2_py", "rosidl_runtime_py", "geometry_msgs", "nav_msgs", "std_msgs", "std_srvs", "sensor_msgs"},
    "NUS's JAX code (conda nus_jax, scripts/workstation/setup_nus_jax.sh; never imported by the PyTorch pipeline)":
        {"jax", "jaxlib", "flax", "optax", "hydra", "omegaconf", "ma_skills", "skill_learning_mpe", "wandb"},
    "the flight stack in this repository (read from ../AirStack by path)": {"svg_ground_control"},
}


def _dist_name(requirement: str) -> str:
    return re.split(r"[\s<>=!~\[;]", requirement.strip(), maxsplit=1)[0].lower().replace("_", "-")


def _listed() -> set[str]:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    reqs = list(project["dependencies"]) + list(project.get("optional-dependencies", {}).get("test", []))
    return {_dist_name(r) for r in reqs}


def _local_modules() -> set[str]:
    names = {"svg_training"}
    for folder in SCANNED:
        names |= {p.stem for p in (ROOT / folder).rglob("*.py")}
    return names


def _imports(folders: list[pathlib.Path]) -> dict[str, set[str]]:
    """top-level module -> files importing it (absolute imports only)."""
    out: dict[str, set[str]] = {}
    for folder in folders:
        for path in folder.rglob("*.py"):
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node, ast.Import):
                    names = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    names = [node.module]
                else:
                    continue
                for name in names:
                    out.setdefault(name.split(".")[0], set()).add(path.name)
    return out


def unlisted_imports(folders: list[pathlib.Path] | None = None) -> dict[str, set[str]]:
    folders = folders if folders is not None else [ROOT / f for f in SCANNED]
    listed, local = _listed(), _local_modules()
    elsewhere = set().union(*NOT_FROM_PIP.values())
    return {m: files for m, files in _imports(folders).items()
            if m not in sys.stdlib_module_names and m not in local and m not in elsewhere
            and DIST_OF.get(m, m).lower().replace("_", "-") not in listed}


def test_every_import_is_listed_or_named():
    missing = unlisted_imports()
    assert not missing, ("imported but not in pyproject.toml (add it to [project] dependencies, or to NOT_FROM_PIP with where it "
                         f"comes from): { {m: sorted(f)[:3] for m, f in missing.items()} }")


def test_the_check_catches_a_new_import(tmp_path):
    """The scan is live: a made-up third-party import is reported; the standard library, our code and listed packages are not."""
    (tmp_path / "probe.py").write_text("import a_package_nobody_lists\nimport json\nimport torch\nfrom svg_training.core import game\n")
    assert set(unlisted_imports([tmp_path])) == {"a_package_nobody_lists"}


def test_core_runtime_set_is_listed():
    """The set a plain CPU venv needs for the suite (measured from a fresh clone, docs panel round 1)."""
    need = {"torch", "numpy", "scipy", "msgpack", "matplotlib", "imageio", "imageio-ffmpeg", "opencv-python-headless", "pyyaml",
            "skrl", "gymnasium", "tensorboard", "pytest"}
    assert need <= _listed()


def test_installable_layout():
    """pip install -e . needs a build backend and finds the package under source/ only."""
    data = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert data["build-system"]["build-backend"]
    assert data["tool"]["setuptools"]["packages"]["find"]["where"] == ["source"]
