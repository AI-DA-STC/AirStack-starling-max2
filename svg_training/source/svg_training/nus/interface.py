"""The interface.toml draft for the partner policy (STANDARDS §3 rule 1), layout id ``nus_area_denial_v1``.

The file says what a consumer must do to feed the policy and read its action: the team sizes and how many opponents a drone sees, the
observation field order, the reached-flag rule, the scale and the hold length, the previous-step sampling, the action form, the vertical
speed and yaw rate (zero), the prior weight (zero), the compute dtype, the source commit and the checkpoint's sha256. It holds the
partner's and the owner's values, so it is written only under ``runs/`` (git-ignored); the committed template
``configs/nus_interface.template.toml`` lists the keys.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..core.observations import INTERFACE_VERSION
from .deploy import NusDeploy
from .outputs import require_under_runs
from .replica import FEATURES_PER_ACTOR
from .rules import ROOT, NusRules

LAYOUT_ID = "nus_area_denial_v1"
INTERFACE_TEMPLATE = ROOT / "configs" / "nus_interface.template.toml"
INTERFACE_KEYS: tuple[str, ...] = (
    "layout_id", "serves_interface_version", "team", "guard_count", "strike_count", "opponents_seen", "observation_width",
    "field_order", "latch_rule", "metres_per_unit", "seconds_per_step", "hold_ticks", "previous_step_sampling", "action_form",
    "vertical_speed", "yaw_rate", "prior_weight", "compute_dtype", "source_commit", "checkpoint_sha256")
FIELD_ORDER = ("one block per drone: the policy's own drone, then its team-mates in cyclic order starting after it, then the other team in "
               "index order (Guard drones first in each game); a block is the unit direction and the length of the drone's position, of its "
               "position at the previous sample and of its last displacement, all relative to the zone centre in units; then the zone radius "
               "in units and the reached flag")
LATCH_RULE = ("the reached flag is 0 at a game's start; at a sample it becomes 1 once any Strike drone is inside the zone, and stays 1 until "
              "the next game starts")
PREVIOUS_STEP = ("the previous positions are the positions at the previous sample, one hold earlier; at a game's start they equal the "
                 "current positions")
ACTION_FORM = ("deterministic mean of the policy; squashed with tanh, scaled by the team's speed in units per step and projected onto the "
               "speed disk; the command is that displacement over the team's speed in units per step, held for the hold length")
_COMMIT = re.compile(r"[0-9a-f]{40}")


def build_interface(team: str, rules: NusRules, deploy: NusDeploy, actor_meta: dict[str, Any], source_commit: str) -> dict[str, Any]:
    """The interface values for one team's converted actor (keys in :data:`INTERFACE_KEYS` order)."""
    if team not in ("guard", "strike"):
        raise ValueError(f"team must be 'guard' or 'strike', got {team!r}")
    if not _COMMIT.fullmatch(source_commit):
        raise ValueError("source commit must be a full 40-character git hash")
    drones = rules.guard_count + rules.strike_count
    data = {
        "layout_id": LAYOUT_ID, "serves_interface_version": INTERFACE_VERSION, "team": team,
        "guard_count": rules.guard_count, "strike_count": rules.strike_count,
        "opponents_seen": rules.strike_count if team == "guard" else rules.guard_count,
        "observation_width": FEATURES_PER_ACTOR * drones + 2, "field_order": FIELD_ORDER, "latch_rule": LATCH_RULE,
        "metres_per_unit": deploy.metres_per_unit, "seconds_per_step": deploy.seconds_per_step, "hold_ticks": deploy.hold_ticks,
        "previous_step_sampling": PREVIOUS_STEP, "action_form": ACTION_FORM, "vertical_speed": 0, "yaw_rate": 0, "prior_weight": 0,
        "compute_dtype": actor_meta["compute_dtype"], "source_commit": source_commit, "checkpoint_sha256": actor_meta["sha256"],
    }
    return {k: data[k] for k in INTERFACE_KEYS}


def write_interface(path: Path | str, data: dict[str, Any]) -> Path:
    """Write the interface file; refuses a path outside ``runs/`` (it holds values)."""
    out = require_under_runs(path)
    lines = ["# interface.toml for the partner policy. Holds partner and owner values: git-ignored, under runs/ only."]
    for key in INTERFACE_KEYS:
        value = data[key]
        lines.append(f'{key} = "{value}"' if isinstance(value, str) else f"{key} = {value!r}")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n")
    return out
