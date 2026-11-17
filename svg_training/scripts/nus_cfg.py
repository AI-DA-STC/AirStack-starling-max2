"""Read the partner's environment configuration and constants from their clone (read-only). Holds no partner value.

Used by ``nus_make_local_rules.py`` and ``nus_record_fixtures.py``. Needs PyYAML; composes a root config with Hydra when the
file has a ``defaults`` list (the partner's own environment, ``nus_jax``, has both).
"""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

SMALL_EXPONENT = 2 * 2 * 2 + 2  # constants below 2 ** -SMALL_EXPONENT are treated as numerical floors


def load_environment_cfg(path: Path | str) -> dict[str, Any]:
    """The partner's ``environment`` group as a plain dict, from a root config (with defaults) or the group file itself."""
    path = Path(path)
    import yaml

    raw = yaml.safe_load(path.read_text())
    if isinstance(raw, dict) and "defaults" in raw:
        from hydra import compose, initialize_config_dir
        from omegaconf import OmegaConf

        with initialize_config_dir(config_dir=str(path.parent.resolve()), version_base=None):
            cfg = compose(config_name=path.stem)
        container = OmegaConf.to_container(cfg, resolve=True)
        return dict(container["environment"])
    try:
        from omegaconf import OmegaConf

        container = OmegaConf.to_container(OmegaConf.load(path), resolve=True)
    except ImportError:
        container = raw
    return dict(container["environment"]) if "environment" in container else dict(container)


def _env_dir(clone: Path) -> Path:
    return clone / "third_party" / "skill_learning_mpe" / "src" / "skill_learning_mpe" / "env"


def env_source_path(clone: Path | str) -> Path:
    return _env_dir(Path(clone)) / "mpe" / "simple_area_denial.py"


def _function(tree: ast.AST, name: str) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise LookupError(f"function {name} not found in the partner source")


def _small_floors(func: ast.FunctionDef) -> set[float]:
    limit = 1 / 2**SMALL_EXPONENT
    return {n.value for n in ast.walk(func) if isinstance(n, ast.Constant) and isinstance(n.value, float) and 0 < n.value < limit}


def read_code_constants(clone: Path | str) -> dict[str, Any]:
    """Constants that sit in the partner's code, not in their yaml: constructor defaults, factory settings, start
    fractions and numerical floors. Read by parsing the source (nothing is imported)."""
    clone = Path(clone)
    out: dict[str, Any] = {}

    tree = ast.parse(env_source_path(clone).read_text())
    init = _function(tree, "__init__")
    kwonly = init.args.kwonlyargs
    defaults: dict[str, Any] = {}
    for arg, default in zip(kwonly, init.args.kw_defaults):
        if isinstance(default, ast.Constant):
            defaults[arg.arg] = default.value
    out["constructor_defaults"] = defaults

    reset = _function(tree, "reset")
    scaled = []  # (line, attribute, constant) for "self.<attr> * <constant>"
    for node in ast.walk(reset):
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult):
            for side, other in ((node.left, node.right), (node.right, node.left)):
                if isinstance(side, ast.Attribute) and isinstance(other, ast.Constant) and isinstance(other.value, float):
                    scaled.append((node.lineno, node.col_offset, side.attr, other.value))
    scaled.sort()
    area = [c for _, _, attr, c in scaled if attr == "area_radius"]
    cluster = [c for _, _, attr, c in scaled if attr == "spawn_cluster_radius"]
    if len(area) != 2 or len(cluster) != 1:
        raise LookupError("partner reset code has an unexpected shape; read it and update nus_cfg.py")
    out["start_guard_disc_fraction"], out["start_static_guard_ring_fraction"] = area
    (out["start_static_strike_cluster_fraction"],) = cluster

    floors = {}
    for func_name, key in (("displacement_corrections", "norm_floor"), ("obs_fn", "obs_direction_floor")):
        found = _small_floors(_function(tree, func_name))
        if len(found) != 1:
            raise LookupError(f"expected one numerical floor in {func_name}, found {len(found)}")
        floors[key] = found.pop()
    cap_floor = _small_floors(_function(tree, "_cap_vectors"))
    if cap_floor != {floors["norm_floor"]}:
        raise LookupError("the partner's cap floor differs from their push floor; the replica uses one floor")
    out.update(floors)

    factory = ast.parse((_env_dir(clone) / "__init__.py").read_text())
    config = None
    for node in ast.walk(_function(factory, "make_env")):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict):
            config = node.value
    if config is None:
        raise LookupError("make_env config dict not found")
    out["factory"] = {
        key.value: val.value
        for key, val in zip(config.keys, config.values)
        if isinstance(key, ast.Constant) and isinstance(val, ast.Constant)
    }
    return out
