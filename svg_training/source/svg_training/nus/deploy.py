"""The deploy values of the partner policy: read from one git-ignored local file, never written in committed text (G1).

Template: ``configs/nus_deploy.template.toml`` (every value the string "LOCAL"). Real file: ``configs/local/nus_deploy.toml``,
written by ``scripts/nus_make_local_deploy.py``. The loader refuses a missing key, an unknown key, a key still "LOCAL" and
a wrong type.

The file holds three kinds of value, all private to the partner or the owner:

* the scale and the hold length (owner's decisions): metres per unit, seconds per step, hold length in simulator ticks,
  flying height;
* the geometry overrides of the checkpoint's game (they replace two keys of the rules file, which stays unchanged);
* constants that sit in the partner's code, not in a config: the LayerNorm epsilon, the disk-projection floor, the APF
  gains and floor.

Two more keys name the converted-weight folders under ``runs/nus_port/weights/``.
"""
from __future__ import annotations

import math
import tomllib
from dataclasses import dataclass, fields, replace
from pathlib import Path
from typing import Any

from ..core.game_config import TICK_S
from .rules import PLACEHOLDER, ROOT, NusRules

LOCAL_DEPLOY = ROOT / "configs" / "local" / "nus_deploy.toml"
DEPLOY_TEMPLATE = ROOT / "configs" / "nus_deploy.template.toml"
WEIGHTS_DIR = ROOT / "runs" / "nus_port" / "weights"
REFERENCE_DIR = ROOT / "runs" / "nus_port" / "reference"


@dataclass(frozen=True)
class NusDeploy:
    """Field names are the TOML keys; comments say what each one is, not its value."""

    metres_per_unit: float  # metres in one partner length unit (owner's decision)
    seconds_per_step: float  # seconds of one partner game step (owner's decision)
    hold_ticks: int  # simulator ticks one policy action is held (owner's decision)
    flying_height_m: float  # fixed flying height of the 2-D game in the simulator (owner's decision)
    spawn_distance: float  # replaces the rules file's Strike start distance for this checkpoint's game
    guard_boundary_radius: float  # replaces the rules file's Guard boundary radius for this checkpoint's game
    layernorm_epsilon: float  # partner code constant: epsilon of the residual blocks' LayerNorm
    disk_floor: float  # partner code constant: floor of the norm in the disk projection of an action
    apf_attraction_gain: float  # partner code constant: attraction of the scripted Strike controller to the zone
    apf_repulsion_gain: float  # partner code constant: repulsion of the scripted Strike controller from Guards
    apf_floor: float  # partner code constant: floor of the lengths in the scripted controllers
    guard_weights: str  # folder name under runs/nus_port/weights/ of the Guard team's converted actor
    strike_weights: str  # folder name under runs/nus_port/weights/ of the Strike team's converted actor


DEPLOY_KEYS: tuple[str, ...] = tuple(f.name for f in fields(NusDeploy))
_TYPES = {f.name: f.type for f in fields(NusDeploy)}
STRING_KEYS = tuple(k for k, t in _TYPES.items() if t in ("str", str))


def _coerce(key: str, value: Any, path: Path) -> Any:
    kind = _TYPES[key]
    if kind in ("str", str):
        if not isinstance(value, str) or value == PLACEHOLDER or not value:
            raise ValueError(f"{path}: key '{key}' must be a folder name (still {PLACEHOLDER}?)")
        return value
    if isinstance(value, str):
        raise ValueError(f"{path}: key '{key}' is a string (still {PLACEHOLDER}?); fill it with scripts/nus_make_local_deploy.py")
    if isinstance(value, bool):
        raise ValueError(f"{path}: key '{key}' must be a number")
    if kind in ("int", int):
        if not isinstance(value, int):
            raise ValueError(f"{path}: key '{key}' must be an integer")
        return int(value)
    return float(value)


def load_deploy(path: Path | str = LOCAL_DEPLOY) -> NusDeploy:
    """Read the local deploy file. Refuses a missing file, missing, unknown or placeholder keys, and a hold length that does
    not match the seconds per step (the policy's action is a velocity held for one game step)."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"{path} not found: run scripts/nus_make_local_deploy.py (it is git-ignored)")
    raw = tomllib.loads(path.read_text())
    missing = [k for k in DEPLOY_KEYS if k not in raw]
    if missing:
        raise ValueError(f"{path}: missing keys {missing}")
    unknown = [k for k in raw if k not in DEPLOY_KEYS]
    if unknown:
        raise ValueError(f"{path}: unknown keys {unknown}")
    deploy = NusDeploy(**{k: _coerce(k, raw[k], path) for k in DEPLOY_KEYS})
    if deploy.hold_ticks < 1:
        raise ValueError(f"{path}: key 'hold_ticks' must be at least 1")
    if not math.isclose(deploy.hold_ticks * TICK_S, deploy.seconds_per_step):
        raise ValueError(f"{path}: 'hold_ticks' x the simulator tick must equal 'seconds_per_step'")
    return deploy


def numeric_values(deploy: NusDeploy) -> list[float]:
    """Every numeric value of the file (used to refuse them in a record)."""
    return [float(getattr(deploy, f.name)) for f in fields(NusDeploy) if _TYPES[f.name] not in ("str", str)]


def apply_overrides(rules: NusRules, deploy: NusDeploy) -> NusRules:
    """The rules of the checkpoint's game: the Phase 2 rules with the deploy file's two geometry overrides."""
    return replace(rules, spawn_distance=deploy.spawn_distance, guard_boundary_radius=deploy.guard_boundary_radius)


def weights_folder(deploy: NusDeploy, team: str) -> Path:
    if team not in ("guard", "strike"):
        raise ValueError(f"team must be 'guard' or 'strike', got {team!r}")
    return WEIGHTS_DIR / (deploy.guard_weights if team == "guard" else deploy.strike_weights)


