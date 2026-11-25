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
* ``net_gates_text`` (task LS1-M1-T4): the one writer of a net gate file's text in every route 3 test (C4's keys
  added to a two-level gate file's text); ``READING_IN_NET_FILES`` says whether it appends ``reading_block()``
  (False until LS1-M4-T1, which sets it True: until then the loaders refuse an unknown ``[reading]`` section).
* ``TIER2_PLAYERS``, ``TIER2_TWO_LEVEL``: what makes ``configs/ste_l013/gates.toml`` a two-level tier-2 gate file (the
  text of tests/test_ste_l3_tier2.py, copied: test modules are not imported).
* ``tiny_learner_saved``: a tiny learner's ``saved()`` dict for whatever route the gate file holds (the recipe of
  tests/test_ste_l3_export.py ``tiny_learner``, copied: that module skips itself without onnxruntime).
* ``toml_text``, ``filled_distil``, ``write_distil_gates`` (task LS1-M2-T5, moved here from
  tests/test_ste_ls1_distil_gates.py so the distillation gate file has one writer in every test): a gate file's text
  from its parsed dict, the committed ``distil_gates.toml`` with the owner's keys filled from ``STAND_IN``, and that
  text written under ``tmp_path`` (relative ``[source]`` paths still resolve from the ``svg_training/`` root).
* ``save_tiny_net(..., provenance=...)``, ``write_fit_report``, ``read_net`` (task LS1-M2-T6): the equivalence read
  takes a network only with a complete ``fit_report.json`` beside it whose shas name the network and the gate file,
  and whose provenance names the same gate file; ``read_net`` saves a tiny network distilled, by its meta, from a given
  gate file and writes that report (no fit is run: the read's checks, not the network's quality, are under test).

CPU only."""
import copy
import hashlib
import json
import math
import re
import tomllib
from pathlib import Path

import torch

from svg_training.opponents.scripted import make_strategy
from svg_training.ste import exploit, exploit_train, skill_net, skills

ROOT = Path(__file__).resolve().parents[1]
SKILLS_GATES = ROOT / "configs" / "ste_l3" / "skills_gates.toml"
DISTIL_GATES = ROOT / "configs" / "ste_ls1" / "distil_gates.toml"
STD_FLOOR = 0.0029                       # synthetic meta value (the real one is distil_gates.toml [net] std_floor)
READING_IN_NET_FILES = False             # LS1-M4-T1 sets this True (its [reading] section is then required)
CHOICE_ANCHOR = re.compile(r'^choice = "two_level".*$', re.MULTILINE)   # the whole line, its comment included
HOLD = 12                                # the tiny learner's decision ticks (tests/test_ste_l3_export.py)

TIER2_PLAYERS = """
[players]
guards = ["guard_parked_centre", "guard_parked_ring", "guard_mark_edge", "guard_mirror", "guard_field"]
strikes = ["strike_straight", "strike_flank", "strike_high", "strike_low", "strike_sacrifice", "strike_converge"]
"""
TIER2_TWO_LEVEL = """
[learner]
action = "skills"
choice = "two_level"

[learner.team_strategies]
strike = ["strike_sacrifice", "strike_converge"]
guard = ["guard_parked_ring", "guard_field"]

[learner.drone_skills]
strike = ["strike_straight", "strike_flank", "strike_high", "strike_low"]
guard = ["guard_parked_centre", "guard_mark_edge", "guard_mirror"]

[learner.entropy_scale]
team = 0.01
drone = 0.01
"""

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


def save_tiny_net(tmp_path, side, cfg, gates=None, provenance: dict | None = None, **tiny_kw) -> tuple[Path, str]:
    """``tiny_net(side, gates, **tiny_kw)`` saved under ``tmp_path`` with a complete C3 meta: the base variant's game
    file (repository-relative) and its sha256, ``game_constants(cfg)``, the scripts' sha256 today, synthetic
    provenance (or ``provenance``, as given). Returns (absolute path, the sha256 ``save_skill_net`` returned)."""
    gates = _gates(gates)
    net = tiny_net(side, gates=gates, **tiny_kw)
    game_file = gates.games[gates.variants["base"]["game"]].file
    meta = {"guards": net.team_size, "strikes": net.team_size, "std_floor": STD_FLOOR,
            "scripted_sha256": skill_net.scripted_sha256(), "game_file": str(game_file),
            "game_sha256": hashlib.sha256((ROOT / game_file).read_bytes()).hexdigest(),
            "game_constants": skill_net.game_constants(cfg),
            "provenance": provenance if provenance is not None else
            {"distil_gates_file": "synthetic (tests/_ste_ls1.py)", "distil_gates_sha256": "synthetic",
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


def after_choice_line(base_text: str, lines: str) -> str:
    """``base_text`` with ``lines`` inserted after the whole line ``choice = "two_level"`` (which must occur exactly
    once)."""
    found = list(CHOICE_ANCHOR.finditer(base_text))
    assert len(found) == 1, f'the line choice = "two_level" occurs {len(found)} times, not once'
    end = found[0].end()
    return base_text[:end] + "\n" + lines.rstrip("\n") + base_text[end:]


def net_gates_text(base_text: str, nets: dict) -> str:
    """A net gate file's text (C4): ``base_text`` (a two-level gate file's text) with ``skill_source = "net"`` after
    its ``choice = "two_level"`` line and a ``[learner.skill_net]`` table of ``nets`` {side: (file, sha256)} appended
    at the end (a table header after the choice line would take the keys that follow it, ``mask_absent`` in
    skills_gates.toml); then ``reading_block()`` when ``READING_IN_NET_FILES``."""
    text = after_choice_line(base_text, 'skill_source = "net"')
    table = ["", "[learner.skill_net]"] + [f"{side} = {{ file = {json.dumps(str(f))}, sha256 = {json.dumps(str(s))} }}"
                                           for side, (f, s) in nets.items()]
    text = text.rstrip("\n") + "\n" + "\n".join(table) + "\n"
    if READING_IN_NET_FILES:
        text += "\n" + reading_block()
    return text


def tiny_learner_saved(gates, side) -> dict:
    """``Learner.saved()`` of a tiny learner of ``side`` on ``gates`` (whatever route it holds: scripts or a net), after
    one update: base variant, 6 games of 3v3, CPU (the recipe of tests/test_ste_l3_export.py ``tiny_learner``)."""
    cfg = exploit.variant_cfg(gates, "base")
    game = exploit_train.TrainGame(cfg, 6, 3, 3, device="cpu", seed=7)
    opp = make_strategy(exploit.opponent_of(gates, "base", side), "strike" if side == "guard" else "guard", cfg, 6,
                        "cpu", 8)
    env = exploit_train.decision_env(game, HOLD, side, opp, gates.learner, gates.players, 7)
    settings = {**gates.trainer, "num_games": 6, "rollouts": 2, "learning_epochs": 1, "mini_batches": 1}
    learner = exploit_train.Learner(settings, env, "cpu", seed=11)
    learner.update()
    return learner.saved()


def toml_value(v) -> str:
    """A TOML value: strings as JSON strings (the escapes agree), dicts as inline tables, lists element by element."""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, str):
        return json.dumps(v)
    if isinstance(v, dict):
        return "{ " + ", ".join(f"{k} = {toml_value(x)}" for k, x in v.items()) + " }"
    if isinstance(v, list):
        return "[" + ", ".join(toml_value(x) for x in v) + "]"
    if isinstance(v, float) and math.isnan(v):
        return "nan"
    return repr(v)


def toml_text(data: dict) -> str:
    """A gate file's text from its parsed dict: one ``[section]`` per top-level table, nested tables inline."""
    out = []
    for section, table in data.items():
        out.append(f"[{section}]")
        out += [f"{k} = {toml_value(v)}" for k, v in table.items()]
        out.append("")
    return "\n".join(out)


def committed_distil() -> dict:
    """The committed ``distil_gates.toml``, parsed."""
    return tomllib.loads(DISTIL_GATES.read_text())


def filled_distil(data: dict | None = None) -> dict:
    """The committed distillation gate file's dict (or ``data``) with the owner's keys filled from ``STAND_IN``
    (synthetic, constraint 5)."""
    data = copy.deepcopy(data if data is not None else committed_distil())
    data["limits"] = dict(STAND_IN["limits"])
    data["controls"] = copy.deepcopy(STAND_IN["controls"])
    return data


def write_distil_gates(tmp_path, data: dict | None = None, name: str = "distil_gates.toml") -> Path:
    """``toml_text(data)`` (default: ``filled_distil()``, the ``STAND_IN`` gate file) written under ``tmp_path``."""
    path = Path(tmp_path) / name
    path.write_text(toml_text(filled_distil() if data is None else data))
    return path


def write_fit_report(net_path, net_sha256: str, gates_sha256: str, of_record: bool = False,
                     complete: bool = True) -> Path:
    """A ``fit_report.json`` beside the network file (the M2 file table's keys, synthetic: no round, an empty final
    read): ``gates_sha256``, ``net_sha256``, ``of_record`` and, last, ``complete`` (left out when ``complete`` is
    False, as a report still being written)."""
    report = {"rounds": [], "final": {}, "gates_sha256": gates_sha256, "net_sha256": net_sha256,
              "of_record": bool(of_record)}
    if complete:
        report["complete"] = True
    path = Path(net_path).parent / "fit_report.json"
    path.write_text(json.dumps(report, indent=1) + "\n")
    return path


def read_net(folder, side, gates_file, of_record: bool = False, gates=None, **tiny_kw) -> tuple[Path, str]:
    """A tiny network of ``side`` saved in ``folder`` as if distilled from ``gates_file``: its provenance names that file
    and its sha256 (``of_record`` as given), and a complete ``fit_report.json`` beside it names both shas. Returns
    (path, the network's sha256)."""
    gates = _gates(gates)
    cfg = exploit.variant_cfg(gates, "base")
    gates_sha = hashlib.sha256(Path(gates_file).read_bytes()).hexdigest()
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    provenance = {"distil_gates_file": Path(gates_file).name, "distil_gates_sha256": gates_sha, "rounds": 0,
                  "seed": int(tiny_kw.get("seed", 5)), "git_commit": "synthetic", "of_record": bool(of_record)}
    path, sha = save_tiny_net(folder, side, cfg, gates=gates, provenance=provenance, **tiny_kw)
    write_fit_report(path, sha, gates_sha, of_record=of_record)
    return path, sha
