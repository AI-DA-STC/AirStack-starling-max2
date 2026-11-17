"""The partner's rule values: read from one git-ignored local file, never written in committed text (G1).

The committed template ``configs/nus_rules.template.toml`` lists every key with the string "LOCAL". The real values
sit in ``configs/local/nus_rules.toml``, written at run time by ``scripts/nus_make_local_rules.py`` from the partner's
own configuration. The loader refuses a missing key, a key still "LOCAL", a wrong type and an unknown key.

Units are the partner's units (length units and steps), not metres or seconds.
"""
from __future__ import annotations

import hashlib
import tomllib
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

PLACEHOLDER = "LOCAL"


def _project_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "pyproject.toml").exists():
            return parent
    raise FileNotFoundError("svg_training project root (pyproject.toml) not found")


ROOT = _project_root()
LOCAL_RULES = ROOT / "configs" / "local" / "nus_rules.toml"
TEMPLATE = ROOT / "configs" / "nus_rules.template.toml"
RUNS_DIR = ROOT / "runs"
FIXTURE_DIR = RUNS_DIR / "nus_port" / "fixtures"


@dataclass(frozen=True)
class NusRules:
    """Every value the replica needs. Field names are the TOML keys; descriptions say what each one is, not its value."""

    guard_count: int  # drones in the Guard team (their defenders)
    strike_count: int  # drones in the Strike team (their attackers)
    area_radius: float  # radius of the zone (disc at the origin)
    agent_size: float  # body radius used in the push radius
    spawn_distance: float  # Strike start distance from the zone centre
    spawn_cluster_radius: float  # Strike cluster radius (fixed-layout start only)
    random_start: bool  # random starts (True) or the fixed layout
    start_guard_disc_fraction: float  # random start: Guard disc radius as a fraction of the zone radius
    start_static_guard_ring_fraction: float  # fixed layout: Guard ring radius as a fraction of the zone radius
    start_static_strike_cluster_fraction: float  # fixed layout: Strike ring as a fraction of the cluster radius
    guard_max_speed: float  # per-step displacement cap of one Guard
    strike_max_speed: float  # per-step displacement cap of one Strike
    guard_safety_distance: float  # added to the push radius around a Guard
    strike_safety_distance: float  # added to the push radius around a Strike
    push_gain: float  # gain of the one-pass push
    push_smoothing_margin: float  # softplus smoothing width of the push and of the boundary
    total_displacement_cap: float  # cap on the executed displacement (choice plus corrections)
    guard_boundary_radius: float  # Guard-only soft circular boundary
    boundary_margin: float  # the boundary push starts this far inside its radius
    episode_steps: int  # fixed episode length
    norm_floor: float  # below this a length counts as zero when normalising a step or a push
    obs_direction_floor: float  # below this the observation's unit direction is zero


RULE_KEYS: tuple[str, ...] = tuple(f.name for f in fields(NusRules))
_TYPES = {f.name: f.type for f in fields(NusRules)}


def file_sha256(path: Path | str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _coerce(key: str, value: Any, path: Path) -> Any:
    kind = _TYPES[key]
    if isinstance(value, str):
        raise ValueError(f"{path}: key '{key}' is a string (still {PLACEHOLDER}?); fill it with scripts/nus_make_local_rules.py")
    if kind in ("bool", bool):
        if not isinstance(value, bool):
            raise ValueError(f"{path}: key '{key}' must be true or false")
        return value
    if isinstance(value, bool):
        raise ValueError(f"{path}: key '{key}' must be a number")
    if kind in ("int", int):
        if not isinstance(value, int):
            raise ValueError(f"{path}: key '{key}' must be an integer")
        return int(value)
    return float(value)


def load_rules(path: Path | str = LOCAL_RULES) -> NusRules:
    """Read the local rules file. Refuses a missing file, missing, unknown or placeholder keys."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"{path} not found: run scripts/nus_make_local_rules.py (it is git-ignored)")
    raw = tomllib.loads(path.read_text())
    missing = [k for k in RULE_KEYS if k not in raw]
    if missing:
        raise ValueError(f"{path}: missing keys {missing}")
    unknown = [k for k in raw if k not in RULE_KEYS]
    if unknown:
        raise ValueError(f"{path}: unknown keys {unknown}")
    return NusRules(**{k: _coerce(k, raw[k], path) for k in RULE_KEYS})


def numeric_values(rules: NusRules) -> list[float]:
    """The rule values that are floats (used to refuse them in a record)."""
    return [float(getattr(rules, f.name)) for f in fields(NusRules) if _TYPES[f.name] in ("float", float)]
