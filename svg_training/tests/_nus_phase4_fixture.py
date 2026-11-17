"""Marker world for the Phase 4 tests (no partner value, none of the owner's hangar values): marker rules, deploy (a hold long enough that the
marker speeds stay under the commander's stick cap), reference deploy, hangar file, synthetic converted weights, and the paired starts."""
import types

import torch

from _nus_markers import (HOLD_TICKS, ROOT, _unit, load_marker_files, marker_deploy, marker_rules, write_deploy_toml, write_synthetic_checkpoint,
                          write_toml)

P4_HOLD_TICKS = 40          # marker hold: 2 s per step, so the marker team speeds are below the 0.5 m/s stick cap
P4_GAMES = 4
HANGAR_RANGE = (20.1, 24.9)  # the arena side contains the marker start ring
WEIGHT_NAMES = {"G19": "marker_ref_guard", "S20": "marker_ref_strike", "P3G": "marker_guard_weights", "P3S": "marker_strike_weights"}


def marker_hangar_value() -> float:
    lo, hi = HANGAR_RANGE
    return float(f"{lo + (hi - lo) * _unit('hangar/arena_side_m', 0):.6g}")


def p4_deploy_values() -> dict:
    values = marker_deploy()
    values["hold_ticks"] = P4_HOLD_TICKS
    values["seconds_per_step"] = P4_HOLD_TICKS * 0.05
    return values


def build(tmp_path, monkeypatch, games: int = P4_GAMES, checkpoints: bool = True):
    """Write the marker files in ``tmp_path`` and point the modules at them. Returns a namespace."""
    from svg_training.core.game_config import load_game_cfg
    from svg_training.nus import deploy as deploy_mod, hangar as hangar_mod, players, strategy as strategy_mod
    from svg_training.nus.replica import NusReplica

    folder = tmp_path / "local"
    folder.mkdir(parents=True, exist_ok=True)
    rules_values, deploy_values = marker_rules(), p4_deploy_values()
    write_toml(folder / "nus_rules.toml", rules_values)
    write_deploy_toml(folder / "nus_deploy.toml", deploy_values)
    ref_values = {**deploy_values, "guard_weights": WEIGHT_NAMES["G19"], "strike_weights": WEIGHT_NAMES["S20"]}
    write_deploy_toml(folder / "nus_deploy_ref.toml", ref_values)
    write_toml(folder / "nus_hangar.toml", {"arena_side_m": marker_hangar_value()})
    weights = tmp_path / "weights"
    if checkpoints:
        for team, names in (("guard", ("G19", "P3G")), ("strike", ("S20", "P3S"))):
            for index, name in enumerate(names):
                write_synthetic_checkpoint(weights / WEIGHT_NAMES[name], team, kind="archive", seed=index + (team == "strike") * 2,
                                           rules_values=rules_values, deploy_values=deploy_values)
    monkeypatch.setattr(strategy_mod, "RULES_PATH", folder / "nus_rules.toml")
    monkeypatch.setattr(strategy_mod, "DEPLOY_PATH", folder / "nus_deploy.toml")
    monkeypatch.setattr(deploy_mod, "WEIGHTS_DIR", weights)
    for cls in (players.RefGuard, players.RefStrike):
        monkeypatch.setattr(cls, "deploy_path", folder / "nus_deploy_ref.toml")
    monkeypatch.setattr(players, "DEPLOY_REF", folder / "nus_deploy_ref.toml")
    deploy = deploy_mod.load_deploy(folder / "nus_deploy.toml")
    rules = deploy_mod.apply_overrides(__import__("svg_training.nus.rules", fromlist=["load_rules"]).load_rules(folder / "nus_rules.toml"), deploy)
    hangar = hangar_mod.load_hangar(folder / "nus_hangar.toml")
    base, _ = load_game_cfg(hangar_mod.HANGAR_GAME, use_local=False)
    settings = hangar_mod.load_phase4()
    geo = hangar_mod.geometry(rules, deploy, hangar, base)
    gen = torch.Generator().manual_seed(7)
    sim = NusReplica(rules)
    start = sim.reset(games, generator=gen, random_start=True).pos
    starts = {"starts_units": start, "jitter_m": (torch.rand(games, rules.guard_count + rules.strike_count, generator=gen) * 2 - 1) * 0.001}
    rows = {r["id"]: r for r in settings["row"]}
    return types.SimpleNamespace(folder=folder, weights=weights, rules=rules, deploy=deploy, hangar=hangar, base=base, settings=settings, geo=geo,
                                 starts=starts, rows=rows, rules_values=rules_values, deploy_values=deploy_values, ref_values=ref_values,
                                 guards=rules.guard_count, strikes=rules.strike_count, sim=sim,
                                 cfg=lambda row_id: hangar_mod.hangar_cfg(base, rules, deploy, hangar, rows[row_id]),
                                 hangar_value=marker_hangar_value(), hold=P4_HOLD_TICKS)


# ---- test-only constants (the numeric-literal scan covers tests/test_nus_*.py, so numbers live here)
STEPS_SHORT = 3        # partner steps played in a short test
TICKS_FEW = 5
POS_TOL_UNITS = 1e-4   # the Phase 2 position tolerance
EXACT = 0
WIDE = 10              # a count of tolerance multiples
FOUR = 4
THREE = 3
SIX = 6
FAR = 100.0            # units: drones placed far from each other
HAND = (3.0, 4.0)      # a 3-4-5 triangle for the by-hand closest approach
HAND_DISTANCE = 5.0
NEAR_UNITS = 1e-3      # a Strike drone put this close to a Guard
ACT = 4                # vx, vy, vz, yaw rate
BAD_SIDE = 1.5
INTERVAL_BASE, INTERVAL_INSIDE, INTERVAL_OUTSIDE = (0.5, 0.4, 0.6), (0.55, 0.4, 0.6), (0.9, 0.8, 0.95)
PARKED_HOLD = 0.95
ROUND_HALF = 0.5
ROW_TWO_INDEX = 3      # rows[3] is row "2" in the committed order
QUOTE = chr(34)


def rate(point: float, low: float, high: float) -> dict:
    return {"rate": point, "ci_low": low, "ci_high": high}
ROUND_DPI = 40         # a small even frame size for the video test
