"""Where a partner-game run may write (G3).

* Records and summaries written outside ``runs/`` name the local rule keys and the sha256 of the local file, never values:
  use :func:`write_record`.
* Anything that holds values (fixtures, trajectories) goes only under ``runs/``: use :func:`require_under_runs`.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from .rules import RULE_KEYS, RUNS_DIR, file_sha256, load_rules, numeric_values


def rules_stamp(rules_path: Path | str) -> dict[str, Any]:
    """Keys and hash of the local file; no values."""
    return {"rules_keys": list(RULE_KEYS), "rules_sha256": file_sha256(rules_path)}


def require_under_runs(path: Path | str) -> Path:
    """Return the resolved path, or raise if it is not under the project's ``runs/`` directory."""
    resolved = Path(path).resolve()
    if RUNS_DIR.resolve() not in (resolved, *resolved.parents):
        raise ValueError(f"{resolved} is outside {RUNS_DIR}: values may only be written under runs/")
    return resolved


def _floats(obj: Any):
    if isinstance(obj, float):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _floats(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _floats(v)


def write_record(path: Path | str, payload: dict[str, Any], rules_path: Path | str) -> Path:
    """Write a JSON record with the rules stamp. Refuses a payload float that equals a rule value."""
    leaked = set(numeric_values(load_rules(rules_path)))
    for value in _floats(payload):
        if value in leaked and not math.isnan(value):
            raise ValueError("payload holds a float equal to a local rule value; keep values out of records")
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({**payload, **rules_stamp(rules_path)}, indent=2, sort_keys=True) + "\n")
    return out
