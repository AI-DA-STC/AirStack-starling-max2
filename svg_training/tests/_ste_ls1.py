"""Helpers of the route 3 (stage LS1) tests: the one home of the test helpers and of ``STAND_IN`` (plan
ste_learning/drafts/LS1_TASK_PLAN.md, section 0 constraint 5; created in task LS1-M1-T3).

* ``tiny_net``: a small skill network on the skills gate file's ``[players]`` lists, weights from a fixed seed.
* ``save_tiny_net``: that network saved with a complete C3 meta (the base variant's game file, its sha256, the game
  constants of the given config, the scripts' sha256, synthetic provenance).
* ``team_obs``: real observations of one team after some ticks of scripted play.
* ``STAND_IN``: synthetic limits, control sizes and margins, by section, for the tests of the verdict arithmetic. Every
  float lies off the 0.001 grid and is written with two significant digits, so no round number (PROPOSED or the
  owner's) can coincide with one, and the partner-privacy value scan (three or more significant digits) never matches.
* ``reading_block``: a ``[reading]`` TOML block filled from ``STAND_IN``.

CPU only."""
import hashlib
from pathlib import Path

import torch

from svg_training.opponents.scripted import make_strategy
from svg_training.ste import exploit, exploit_train, skill_net, skills

ROOT = Path(__file__).resolve().parents[1]
SKILLS_GATES = ROOT / "configs" / "ste_l3" / "skills_gates.toml"
STD_FLOOR = 0.0029                       # synthetic meta value (the real one is distil_gates.toml [net] std_floor)

STAND_IN = {
    "limits": {                          # distil_gates.toml [limits] (LS1-M2-T1)
        "cmd_rmse_max": 0.0047,
        "cmd_unused_max_abs": 0.0063,
        "cmd_zero_skill_max_abs": 0.00071,
        "flips_max_games": 37,
        "cell_margin": 0.0083,
        "pooled_margin": 0.0059,
        "end_time_gated": True,
        "end_time_max_ticks": 23,
    },
    "controls": {                        # distil_gates.toml [controls], the owner's keys (LS1-M2-T1)
        "permuted_min_miss_cells": 7,
        "unfitted_min_miss_cells": 5,
        "near_miss": {
            "bias": 0.0017,
            "rotate_deg": 0.0026,
            "noise": 0.0034,
            "switch": {
                "sacrifice_entry_rad": 0.0041,
                "converge_gather_rad": 0.0052,
                "flank_margin_m": 0.0068,
                "field_range_m": 0.0077,
            },
        },
    },
    "reading": {                         # heads_gates.toml [reading] (LS1-M4-T1)
        "margin_pooled": 0.0091,
        "margin_cell": 0.0097,
        "last_reads": 3,
        "strike_read": "run0",
    },
}


def _gates(gates):
    return gates if gates is not None else exploit.load_gates(SKILLS_GATES)


def slot_width(cfg, side: str) -> int:
    """The team's pad: the skill network's slot width (OP-6)."""
    return cfg.pad_guards if side == "guard" else cfg.pad_strikes


def tiny_net(side, gates=None, team_size=3, hidden=(16,), zeroed_inputs=(6, 7, 10, 11), seed=5) -> skill_net.SkillNet:
    """A small skill network of ``side``: skills = the gate file's ``[players]`` list of the side (default the skills
    gate file), slot width = the pad of its base variant's game, weights and biases from ``torch.manual_seed(seed)``
    (the global generator is restored afterwards)."""
    gates = _gates(gates)
    cfg = exploit.variant_cfg(gates, "base")
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(seed)
        return skill_net.SkillNet(side, skills.team_skills(gates.players, side), team_size, slot_width(cfg, side),
                                  list(hidden), list(zeroed_inputs))


def save_tiny_net(tmp_path, side, cfg, gates=None, **tiny_kw) -> tuple[Path, str]:
    """``tiny_net(side, gates, **tiny_kw)`` saved under ``tmp_path`` with a complete C3 meta: the base variant's game
    file (repository-relative) and its sha256, ``game_constants(cfg)``, the scripts' sha256 today, synthetic
    provenance. Returns (absolute path, the sha256 ``save_skill_net`` returned)."""
    gates = _gates(gates)
    net = tiny_net(side, gates=gates, **tiny_kw)
    game_file = gates.games[gates.variants["base"]["game"]].file
    meta = {"guards": net.team_size, "strikes": net.team_size, "std_floor": STD_FLOOR,
            "scripted_sha256": skill_net.scripted_sha256(), "game_file": str(game_file),
            "game_sha256": hashlib.sha256((ROOT / game_file).read_bytes()).hexdigest(),
            "game_constants": skill_net.game_constants(cfg),
            "provenance": {"distil_gates_file": "synthetic (tests/_ste_ls1.py)", "distil_gates_sha256": "synthetic",
                           "rounds": 0, "seed": int(tiny_kw.get("seed", 5)), "git_commit": "synthetic"}}
    path = (Path(tmp_path) / f"skill_net_{side}.pt").resolve()
    return path, skill_net.save_skill_net(path, net, meta)


def team_obs(gates, side, n=64, ticks=40, seed=5):
    """(cfg, obs [n, 3, OBS_DIM]): real observations of ``side`` in the base variant's 3v3 game after ``ticks`` ticks
    of scripted play (guard_mark_edge against strike_straight; the recipe of tests/test_ste_l3_two_level.py
    ``_team_obs``)."""
    cfg = exploit.variant_cfg(gates, "base")
    game = exploit_train.TrainGame(cfg, n, 3, 3, device="cpu", seed=seed)
    obs = game.reset()
    g = make_strategy("guard_mark_edge", "guard", cfg, n, "cpu", 0)
    s = make_strategy("strike_straight", "strike", cfg, n, "cpu", 0)
    for _ in range(ticks):
        obs = game.step({"guard": g.act(obs["guard"]), "strike": s.act(obs["strike"])}).obs
    return cfg, obs[side]


def _toml_value(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, str):
        return f'"{v}"'
    return repr(v)


def reading_block() -> str:
    """A ``[reading]`` TOML block (LS1-M4-T1's keys) filled from ``STAND_IN``."""
    lines = ["[reading]"] + [f"{k} = {_toml_value(v)}" for k, v in STAND_IN["reading"].items()]
    return "\n".join(lines) + "\n"
