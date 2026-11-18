"""The interface.toml of a policy trained in stage 5.2 (NUS port Phase 5, Task S2; STANDARDS section 3 rule 1): policy interface
**v0.2** (``core/observations.py``: v0.1's 71 numbers plus the height band's floor and ceiling at indices 71-72).

The file says what a consumer must do to feed the policy and read its action: the interface version and observation width and order, the
action form and scaling (3-D, the unit ball times the team speed, yaw rate 0), the decision period and the command repeat, the command
rate, the frames, the game configuration and the drone-model parameter set (paths and sha256), the local files by sha256, the git commit,
the seed, the generation and the checkpoint's sha256. The team speeds and the decision period come from the partner's and the owner's
local files, so the file is written only under ``runs/`` (git-ignored). This is the training record of a checkpoint, not an export for
AirStack (an export is stage S5's ``train-export``, not in Phase 5). No numeric literal other than 0, 1, -1, 2 (G2).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..core.game_config import TICK_S, GameCfg
from ..core.observations import INTERFACE_VERSION_V02, OBS_DIM_V02
from .outputs import require_under_runs

TIER1_INTERFACE_KEYS: tuple[str, ...] = (
    "interface_version", "observation_width", "observation_layout", "team", "guard_count", "strike_count", "action_form",
    "team_speed_mps", "yaw_rate", "decision_ticks", "command_repeat", "command_rate_hz", "frames", "game_config",
    "game_config_sha256", "drone_model_params", "drone_model_params_sha256", "drone_model_status", "local_files_sha256",
    "compute_dtype", "source_commit", "seed", "generation", "checkpoint_sha256", "simulator")
OBSERVATION_LAYOUT = ("interface v0.1 (core/observations.py ObsView: own position relative to the zone centre and height, own velocity, "
                      "sin and cos of yaw, zone radius, arena half-side, time left, team, alive, eight padded slots of relative position, "
                      "relative velocity and present flag, the zone centre relative to the arena centre) then the height band's floor and "
                      "ceiling in m, world z (indices 71-72); a drone that is out sees zeros except its team")
ACTION_FORM = ("deterministic mean of the policy, three numbers (vx, vy, vz); squashed with tanh and projected onto the unit ball; the "
               "game multiplies by the team speed in m/s (world ENU); the safety filter then acts on every pair of drones")
COMMAND_REPEAT = "one decision every decision_ticks simulator ticks; the command is held and sent again on every tick in between"
FRAMES = "world ENU (x east, y north, z up), m and m/s; the zone centre is the origin of the relative positions"
_COMMIT = re.compile(r"[0-9a-f]{40}")


def build_tier1_interface(*, team: str, cfg: GameCfg, guards: int, strikes: int, decision_ticks: int, game_config: Path,
                          game_config_sha256: str, params_sha256: str, local_sha256: dict[str, str], compute_dtype: str,
                          source_commit: str, seed: int, generation: int, checkpoint_sha256: str) -> dict[str, Any]:
    """The interface values of one archived 5.2 checkpoint (keys in :data:`TIER1_INTERFACE_KEYS` order)."""
    if team not in ("guard", "strike"):
        raise ValueError(f"team must be 'guard' or 'strike', got {team!r}")
    if not _COMMIT.fullmatch(source_commit):
        raise ValueError("source commit must be a full 40-character git hash")
    data = {
        "interface_version": INTERFACE_VERSION_V02, "observation_width": OBS_DIM_V02, "observation_layout": OBSERVATION_LAYOUT,
        "team": team, "guard_count": int(guards), "strike_count": int(strikes), "action_form": ACTION_FORM,
        "team_speed_mps": float(cfg.team_speed_mps(team)), "yaw_rate": 0, "decision_ticks": int(decision_ticks),
        "command_repeat": COMMAND_REPEAT, "command_rate_hz": float(round(1 / TICK_S)), "frames": FRAMES,
        "game_config": str(game_config), "game_config_sha256": game_config_sha256, "drone_model_params": str(cfg.starling.params),
        "drone_model_params_sha256": params_sha256, "drone_model_status": "EXPLORATORY (T5 = FAIL)",
        "local_files_sha256": " ".join(f"{k}={v}" for k, v in sorted(local_sha256.items())), "compute_dtype": compute_dtype,
        "source_commit": source_commit, "seed": int(seed), "generation": int(generation), "checkpoint_sha256": checkpoint_sha256,
        "simulator": "training simulator, tier 1 (fitted Starling layer); nothing here is a flight result"}
    return {k: data[k] for k in TIER1_INTERFACE_KEYS}


def write_tier1_interface(path: Path | str, data: dict[str, Any]) -> Path:
    """Write the interface file; refuses a path outside ``runs/`` (it holds values)."""
    out = require_under_runs(path)
    missing = [k for k in TIER1_INTERFACE_KEYS if k not in data]
    if missing:
        raise ValueError(f"interface data misses keys {missing}")
    lines = ["# interface.toml of a stage 5.2 checkpoint (policy interface v0.2). Holds partner and owner values: under runs/ only."]
    for key in TIER1_INTERFACE_KEYS:
        value = data[key]
        lines.append(f'{key} = "{value}"' if isinstance(value, str) else f"{key} = {value!r}")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n")
    return out
