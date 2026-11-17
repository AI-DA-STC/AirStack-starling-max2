"""Where a partner-game run may write (G3).

* Records and summaries written outside ``runs/`` name the local rule keys and the sha256 of the local files, never values:
  use :func:`write_record`. It refuses any number (float or int, in a string too for decimals) that equals a value of the
  rules file, the deploy file or a checkpoint's architecture and game settings. Write counts and rates as they are; a
  count that happens to equal a protected number is refused, and the writer then states it as text (the guard is not relaxed).
* Anything that holds values (fixtures, trajectories) goes only under ``runs/``: use :func:`require_under_runs`.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

from .deploy import DEPLOY_KEYS, load_deploy
from .deploy import numeric_values as deploy_numeric_values
from .rules import RULE_KEYS, RUNS_DIR, file_sha256, load_rules, numeric_values

# Structural numbers every file may hold (the same set the literal scan allows); they carry no partner information.
STRUCTURAL = frozenset({0, 1, -1, 2})
_DECIMAL = re.compile(r"-?\d+\.\d+(?:[eE][+-]?\d+)?|-?\d+[eE][+-]?\d+")
_SIGNIFICANT = ".6g"


def rules_stamp(rules_path: Path | str) -> dict[str, Any]:
    """Keys and hash of the local file; no values."""
    return {"rules_keys": list(RULE_KEYS), "rules_sha256": file_sha256(rules_path)}


def require_under_runs(path: Path | str) -> Path:
    """Return the resolved path, or raise if it is not under the project's ``runs/`` directory."""
    resolved = Path(path).resolve()
    if RUNS_DIR.resolve() not in (resolved, *resolved.parents):
        raise ValueError(f"{resolved} is outside {RUNS_DIR}: values may only be written under runs/")
    return resolved


def _numbers(obj: Any):
    """Every int and float in a nested payload (a bool is not a number here)."""
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _numbers(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _numbers(v)


def _strings(obj: Any):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _strings(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _strings(v)


def _rounded(value: float) -> float:
    return float(format(value, _SIGNIFICANT))


def architecture_numbers(config: dict[str, Any]) -> list[float]:
    """Numbers of a checkpoint's config that identify the partner's network and game: the policy block, the widths and the
    environment settings (the derived half width too)."""
    found = list(_numbers(config.get("trainer", {}).get("policy", {})))
    found += list(_numbers(config.get("environment", {}).get("env", {}).get("physics", {})))
    for key in ("obs_dim", "global_state_dim", "action_dim", "episode_length"):
        found += list(_numbers(config.get(key)))
    for key in ("num_defenders", "num_attackers", "max_episode_steps"):
        found += list(_numbers(config.get("environment", {}).get(key)))
    hidden = config.get("trainer", {}).get("policy", {}).get("hidden_dim")
    if isinstance(hidden, int):
        found.append(hidden // 2)
    return [float(v) for v in found]


def protected_numbers(rules_path: Path | str, deploy_path: Path | str | None = None,
                      checkpoints: tuple[Path | str, ...] | list[Path | str] = ()) -> set[float]:
    """Every number a record must not hold: the rules file (floats and ints), the deploy file, the checkpoints' architecture."""
    rules = load_rules(rules_path)
    values = set(numeric_values(rules))
    values |= {float(getattr(rules, k)) for k in RULE_KEYS if isinstance(getattr(rules, k), int) and not isinstance(getattr(rules, k), bool)}
    if deploy_path is not None:
        values |= set(deploy_numeric_values(load_deploy(deploy_path)))
    for folder in checkpoints:
        values |= set(architecture_numbers(json.loads((Path(folder) / "config.json").read_text())))
    values = {v for v in values if v not in STRUCTURAL and not math.isnan(v)}
    return values | {_rounded(v) for v in values}


def check_payload(payload: dict[str, Any], protected: set[float]) -> None:
    """Raise ValueError if the payload holds a protected number (as a number, or as a decimal inside a string)."""
    for value in _numbers(payload):
        if value not in STRUCTURAL and not math.isnan(value) and (value in protected or _rounded(value) in protected):
            raise ValueError("payload holds a number equal to a local rules, deploy or checkpoint value; keep values out of records")
    for text in _strings(payload):
        for token in _DECIMAL.findall(text):
            if float(token) in protected or _rounded(float(token)) in protected:
                raise ValueError("payload text holds a number equal to a local rules, deploy or checkpoint value")


def write_record(path: Path | str, payload: dict[str, Any], rules_path: Path | str, *, deploy_path: Path | str | None = None,
                 checkpoints: tuple[Path | str, ...] | list[Path | str] = ()) -> Path:
    """Write a JSON record with the rules stamp (and the deploy and checkpoint stamps when given). Refuses a payload number
    (float or int) that equals a value of those files; see :func:`check_payload`."""
    check_payload(payload, protected_numbers(rules_path, deploy_path, checkpoints))
    stamp: dict[str, Any] = rules_stamp(rules_path)
    if deploy_path is not None:
        stamp |= {"deploy_keys": list(DEPLOY_KEYS), "deploy_sha256": file_sha256(deploy_path)}
    if checkpoints:
        stamp["checkpoint_sha256"] = [file_sha256(Path(c) / "state.msgpack") if (Path(c) / "state.msgpack").exists()
                                      else file_sha256(Path(c) / "actor.msgpack") for c in checkpoints]
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({**payload, **stamp}, indent=2, sort_keys=True) + "\n")
    return out
