"""The hangar geometry as a game configuration (NUS port Phase 4, plan D1). Nothing partner-derived is written in a tracked file: this
module computes every value in memory from the three git-ignored local files (rules, deploy, hangar) and holds no numeric literal (G2).

* ``configs/local/nus_hangar.toml`` (template ``configs/nus_hangar.template.toml``): the owner's arena side, kept local. The loader refuses
  a missing file, a missing, unknown or "LOCAL" key and a wrong type.
* :func:`geometry`: the fixed arena, the zone, the start ring and disc, the keep-outs and the speeds, in metres and m/s.
* :func:`hangar_cfg`: the ``GameCfg`` of one ladder row. ``rules.keepout_strike_m`` is the disc round a GUARD that keeps STRIKE drones out
  (the Strike team's own disc in ``pair_rules.push_apart``), so it takes the Guard side's safety distance; ``keepout_guard_m`` the Strike
  side's. The crossing is deliberate (port plan F3) and a test pins it.
* :func:`protected_derived`: every value derived from the local files that a record must not state (lengths x scale, speeds in m/s,
  ticks and seconds, keep-outs, ring, disc, zone, arena).

``rules`` is the Phase 2 rules with the deploy file's two geometry overrides applied (``deploy.apply_overrides``), as ``NusPolicy`` uses.
"""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, fields, replace
from pathlib import Path
from typing import Any

from ..core.game_config import TICK_S, GameCfg
from .deploy import NusDeploy
from .rules import PLACEHOLDER, ROOT, NusRules

LOCAL_HANGAR = ROOT / "configs" / "local" / "nus_hangar.toml"
HANGAR_TEMPLATE = ROOT / "configs" / "nus_hangar.template.toml"
HANGAR_GAME = ROOT / "configs" / "nus_hangar_game.toml"
PHASE4_CONFIG = ROOT / "configs" / "nus_phase4.toml"

ROW_KEYS = ("engine", "boundary", "separation", "motion", "drone", "height")
ROW_VALUES = {"engine": ("replica", "game"), "boundary": ("guard_circle", "walls"),
              "separation": ("partner_push", "block", "filter"), "motion": ("jump", "hold"),
              "drone": ("points", "identity", "fitted", "physics"), "height": ("pinned", "free", "free_jitter")}


@dataclass(frozen=True)
class NusHangar:
    """Field names are the TOML keys."""
    arena_side_m: float  # side of the square hangar arena (owner's decision)


HANGAR_KEYS: tuple[str, ...] = tuple(f.name for f in fields(NusHangar))


def load_hangar(path: Path | str = LOCAL_HANGAR) -> NusHangar:
    """Read the local hangar file. Refuses a missing file, missing, unknown or placeholder keys and a wrong type."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"{path} not found (it is git-ignored; template configs/nus_hangar.template.toml)")
    raw = tomllib.loads(path.read_text())
    missing = [k for k in HANGAR_KEYS if k not in raw]
    if missing:
        raise ValueError(f"{path}: missing keys {missing}")
    unknown = [k for k in raw if k not in HANGAR_KEYS]
    if unknown:
        raise ValueError(f"{path}: unknown keys {unknown}")
    for key in HANGAR_KEYS:
        value = raw[key]
        if isinstance(value, str):
            raise ValueError(f"{path}: key '{key}' is a string (still {PLACEHOLDER}?)")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{path}: key '{key}' must be a number")
    return NusHangar(**{k: float(raw[k]) for k in HANGAR_KEYS})


def load_phase4(path: Path | str = PHASE4_CONFIG) -> dict[str, Any]:
    """The committed Phase 4 settings (counts, names, tolerances)."""
    return tomllib.loads(Path(path).read_text())


def check_row(row: dict[str, Any]) -> None:
    """Refuse a row with a missing key or a value outside the table of D3 (keys named)."""
    for key in ROW_KEYS:
        if key not in row:
            raise ValueError(f"row {row.get('id')!r}: missing key '{key}'")
        if row[key] not in ROW_VALUES[key]:
            raise ValueError(f"row {row.get('id')!r}: key '{key}' must be one of {ROW_VALUES[key]}")
    if row["drone"] == "points" and row["separation"] == "filter":
        raise ValueError(f"row {row.get('id')!r}: the safety filter needs a drone model (drone != points)")
    if row["separation"] == "partner_push" and row["drone"] != "points":
        raise ValueError(f"row {row.get('id')!r}: the partner's soft push is built for the point drone only")
    if row["drone"] == "physics" and row["separation"] == "block":
        raise ValueError(f"row {row.get('id')!r}: the push layer is not built for the physics drone")


def check_row_lint(rows: list[dict[str, Any]]) -> None:
    """Consecutive declared rows differ in exactly the keys their ``changed`` list names; every row but rung 2 (owner answer 3) changes at
    most one key."""
    for before, row in zip(rows, rows[1:]):
        differs = sorted(k for k in ROW_KEYS if before[k] != row[k])
        if differs != sorted(row["changed"]):
            raise ValueError(f"row {row['id']!r}: keys that differ from row {before['id']!r} are {differs}, declared {row['changed']}")
        if len(differs) > 1 and row["id"] != "2":
            raise ValueError(f"row {row['id']!r} changes more than one key")


@dataclass(frozen=True)
class Geometry:
    """The hangar game in metres and m/s (never written in a tracked file)."""
    scale_m_per_unit: float
    side_m: float
    zone_radius_m: float
    ring_m: float
    guard_disc_m: float
    height_m: float
    keepout_strike_m: float
    keepout_guard_m: float
    strike_mps: float
    guard_mps: float
    hold_ticks: int
    game_ticks: int
    game_seconds: float
    wall_margin_m: float


def geometry(rules: NusRules, deploy: NusDeploy, hangar: NusHangar, base: GameCfg) -> Geometry:
    scale = deploy.metres_per_unit
    ticks = rules.episode_steps * deploy.hold_ticks
    return Geometry(
        scale_m_per_unit=scale, side_m=hangar.arena_side_m, zone_radius_m=rules.area_radius * scale,
        ring_m=rules.spawn_distance * scale, guard_disc_m=rules.start_guard_disc_fraction * rules.area_radius * scale,
        height_m=deploy.flying_height_m,
        keepout_strike_m=(2 * rules.agent_size + rules.guard_safety_distance) * scale,
        keepout_guard_m=(2 * rules.agent_size + rules.strike_safety_distance) * scale,
        strike_mps=rules.strike_max_speed * scale / deploy.seconds_per_step,
        guard_mps=rules.guard_max_speed * scale / deploy.seconds_per_step,
        hold_ticks=deploy.hold_ticks, game_ticks=ticks, game_seconds=ticks * TICK_S, wall_margin_m=base.arena.wall_margin_m)


def with_wide_arena(geo: Geometry) -> Geometry:
    """Row 2.1: the walls moved out of reach: a side 2 ** 8 times the start ring (the partner's Strike drones are unbounded; a drone the push
    flings away still stays inside, because a step is capped)."""
    return replace(geo, side_m=geo.ring_m * 2 ** (2 * 2 * 2))


def hangar_cfg(base: GameCfg, rules: NusRules, deploy: NusDeploy, hangar: NusHangar, row: dict[str, Any]) -> GameCfg:
    """The game configuration of one ladder row (an ``engine = "game"`` row). Pure; no numeric literal."""
    check_row(row)
    if row["engine"] != "game":
        raise ValueError(f"row {row['id']!r} runs in the replica: it has no game configuration")
    geo = geometry(rules, deploy, hangar, base)
    pinned = row["height"] == "pinned"
    band = (geo.height_m, geo.height_m) if pinned else base.arena.height_band_m
    return base.replace(**{
        "rules.metres_per_unit": deploy.metres_per_unit, "rules.seconds_per_step": deploy.seconds_per_step,
        "rules.strike_units_per_step": rules.strike_max_speed, "rules.guard_units_per_step": rules.guard_max_speed,
        "rules.game_steps": rules.episode_steps,
        "rules.keepout_strike_m": geo.keepout_strike_m, "rules.keepout_guard_m": geo.keepout_guard_m,
        "rules.push_rule": "block",
        "arena.start_height_m": geo.height_m, "arena.height_band_m": band, "arena.walls": "keep_in",
        "starling.enabled": row["drone"] != "points",
        "starling.backend": "physics" if row["drone"] == "physics" else "fitted",
        "dropout_fraction": 0.0, "obs_view": "full"})


def protected_derived(rules: NusRules, deploy: NusDeploy, hangar: NusHangar, base: GameCfg) -> list[float]:
    """Every value derived from the local files that a record must not state (plan Task 1)."""
    geo = geometry(rules, deploy, hangar, base)
    scale = geo.scale_m_per_unit
    lengths = [rules.area_radius, rules.agent_size, rules.spawn_distance, rules.spawn_cluster_radius, rules.guard_safety_distance,
               rules.strike_safety_distance, rules.guard_boundary_radius, rules.boundary_margin, rules.guard_max_speed,
               rules.strike_max_speed, rules.total_displacement_cap, rules.push_smoothing_margin]
    values = [length * scale for length in lengths]
    values += [geo.side_m, geo.side_m / 2, geo.side_m / 2 - geo.wall_margin_m, geo.zone_radius_m, geo.ring_m, geo.guard_disc_m, geo.height_m,
               geo.keepout_strike_m, geo.keepout_guard_m, geo.strike_mps, geo.guard_mps, geo.game_seconds,
               float(geo.game_ticks), float(geo.hold_ticks), deploy.seconds_per_step, float(rules.episode_steps),
               2 * geo.keepout_strike_m, 2 * geo.keepout_guard_m, geo.ring_m / scale, geo.zone_radius_m * 2,
               rules.episode_steps * deploy.seconds_per_step, geo.game_seconds / deploy.seconds_per_step]
    return [float(v) for v in values]
