"""Test constants for the stage 5.2 tasks S1-S5 (the numeric-literal scan G2 covers tests/test_nus_*.py, so numbers live here), and the
marker world of the 5.2 environment (the Phase 4 marker files plus the Phase 5 marker method)."""
from __future__ import annotations

import types

from _nus_phase4_fixture import build
from _nus_phase5_method_fixture import marker_method, write_method_toml

FIRST_REACH_GAMES = 1000     # plan Task S1: the outcome test plays 1,000 CPU games with scripted players
TIER1_GAMES = 6              # games of a small environment test
REACH_SEED = 11              # start generator seed of the outcome test
OTHER_SEED = 12
OUTSIDE_COUNTED_M = 0.02     # plan Task S5: a drone 0.02 m outside the box counts one clamped drone-tick
OUTSIDE_NOT_M = 0.005        # ... 0.005 m outside counts none
REWARD_REL = 1e-5            # reward in metres v the replica's in units, relative
POS_ABS_M = 1e-5             # positions the env reports v the game's
SLOT = 2                     # an opponent slot id in the critic-state test
UNITS_SPAN = 3.0             # random positions in partner units: [-span, span]
CLAMP_STEPS = 6              # real steps checked for "every drone inside the box"
HALF = 0.5
AWAY = (1.0, 0.0, 0.0)       # a Strike command straight along +x (away from the zone once past it)


REACH_EPISODE_STEPS = 20     # partner steps of the 5.2 marker world: long enough for a marker Strike drone to reach the zone (the
                             # Phase 4 marker world's 7 steps of 2 s cannot: its start ring is about 3.7 m outside the zone at 0.1 m/s)
STICKY_EPISODE_STEPS = 30    # long enough to reach the zone (about step 18 against a still Guard team) and then leave it


def tier1_world_fixture(tmp_path, monkeypatch, games: int | None = None, episode_steps: int | None = REACH_EPISODE_STEPS):
    """The Phase 4 marker world with ``episode_steps`` partner steps (None: the marker rules' own, which the synthetic NUS checkpoints
    were written for) and the hangar file pointed at, the Phase 5 marker method, and its ``Tier1World``."""
    from _nus_markers import marker_rules, write_toml
    from svg_training.nus import hangar as hangar_mod
    from svg_training.nus.method_cfg import load_method
    from svg_training.nus.tier1_env import tier1_world
    w = build(tmp_path, monkeypatch) if games is None else build(tmp_path, monkeypatch, games=games)
    if episode_steps is not None:
        write_toml(w.folder / "nus_rules.toml", {**marker_rules(), "episode_steps": episode_steps})
    monkeypatch.setattr(hangar_mod, "LOCAL_HANGAR", w.folder / "nus_hangar.toml")
    method_path = tmp_path / "local" / "nus_method.toml"
    write_method_toml(method_path, marker_method())
    return types.SimpleNamespace(w=w, world=tier1_world(), method=load_method(method_path), method_path=method_path)


# ------------------------------------------------------------------------------------------------ S4: the trainer on the marker world
TRAIN_EPISODE_STEPS = 3      # partner steps of a trainer test game (tiny: the CPU smoke counts below)
TRAIN_SEED = 1001
TINY_TIER1 = """
[world]
row = "5"
clamp_tolerance_m = 0.01
critic_reached_flag = false

[caps]
training_gpu_hours = 1.0
probe_updates = 1

[videos]
format = "deferred"
games_searched = 2
eval_video_slots = 2

[evaluation]
control_guard = "ParkedGuard"
control_strike = "S20"
info_guard_strikes = ["P3S"]
info_strike_guards = ["G19", "ApfGuard"]
gpu_hours_groups = { gated = "s52_eval", crossplay = "s52_crossplay" }

[smoke]
generations = 2
updates_per_generation = 2
games_per_update = 4
selection_games_per_opponent = 2
eval_games = 4
"""


def tiny_tier1_config(tmp_path, monkeypatch):
    from svg_training.nus import tier1_env
    path = tmp_path / "nus_phase5_tier1.toml"
    path.write_text(TINY_TIER1)
    monkeypatch.setattr(tier1_env, "TIER1_CONFIG", path)
    return path


# ------------------------------------------------------------------------------------------------ S5: the evaluation runner
REF_GAMES = 1000
# Phase 4 row 5 (T23) counts the plan's bars come from (plan section 5): reach counts out of 1,000
T23_REACH = {("ParkedGuard", "S20"): 571, ("G19", "S20"): 983, ("guard_mirror", "ApfStrike"): 959, ("ParkedGuard", "ApfStrike"): 1000,
             ("G19", "strike_straight"): 1000, ("P3G", "strike_straight"): 1000, ("ParkedGuard", "strike_straight"): 1000,
             ("G19", "strike_flank"): 1000, ("P3G", "strike_flank"): 1000, ("ParkedGuard", "strike_flank"): 1000}
PLAN_BARS = {"G-1": 0.460, "G-2": 0.055, "G-3": 0.004, "G-4": 0.004, "S-1": 0.601}   # plan section 5, to three decimals
BAR_PLACES = 3
HOLDS_PASSING = 600          # a synthetic seed's holds out of 1,000 above every Guard bar
HOLDS_FAILING = 400          # ... below G-1's
REACH_PASSING = 700          # a synthetic Strike's reach above S-1's bar
MIN_SEEDS = 2
SEED_NAMES = ("seed1001", "seed2001", "seed3001")
EVAL_GAMES = 4               # games per pairing of the marker-world evaluation (the Phase 4 marker starts)
