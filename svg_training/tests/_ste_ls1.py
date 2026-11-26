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
  (False until LS1-M4-T1, which set it True: ``exploit.load_gates`` requires ``[reading]`` in a net gate file);
  its keyword ``reading`` overrides the flag for one file (False: a net file without ``[reading]``).
* ``TIER2_PLAYERS``, ``TIER2_TWO_LEVEL``: what makes ``configs/ste_l013/gates.toml`` a two-level tier-2 gate file (the
  text of tests/test_ste_l3_tier2.py, copied: test modules are not imported).
* ``tiny_learner_saved``: a tiny learner's ``saved()`` dict for whatever route the gate file holds (the recipe of
  tests/test_ste_l3_export.py ``tiny_learner``, copied: that module skips itself without onnxruntime).
* ``toml_text``, ``filled_distil``, ``write_distil_gates`` (task LS1-M2-T5, moved here from
  tests/test_ste_ls1_distil_gates.py so the distillation gate file has one writer in every test): a gate file's text
  from its parsed dict, the committed ``distil_gates.toml`` with the owner's keys filled from ``STAND_IN``, and that
  text written under ``tmp_path`` (relative ``[source]`` paths still resolve from the ``svg_training/`` root).
* ``unfilled_distil``, ``write_unfilled_distil_gates`` (lead, 26 Nov 2026, after the owner filled the committed file,
  R48): the committed ``distil_gates.toml`` with every owner key (the keys of ``STAND_IN["limits"]`` and
  ``STAND_IN["controls"]``) set back to ``UNFILLED`` (``"FILL_OWNER_R38"``), written under ``tmp_path``: the one source of
  an unfilled gate file for the tests that need one (a refusal outside ``--smoke``, a ``FILL_`` value that never reaches
  a comparison).
* ``save_tiny_net(..., provenance=...)``, ``write_fit_report``, ``read_net`` (task LS1-M2-T6): the equivalence read
  takes a network only with a complete ``fit_report.json`` beside it whose shas name the network and the gate file,
  and whose provenance names the same gate file; ``read_net`` saves a tiny network distilled, by its meta, from a given
  gate file and writes that report (no fit is run: the read's checks, not the network's quality, are under test).
* ``tiny_skill_net`` (task LS1-M3-T2): ``save_tiny_net`` loaded back with ``skill_net.load_skill_net``, as the export of
  the skill network takes it: (net, meta, path, sha256).
* ``net_gates_file`` (task LS1-M3-T3): a net gate file (the skills gate file through ``net_gates_text``) written under
  ``tmp_path``, with a tiny network of each side saved beside it (OP-35: both sides), for a route 3 team's export.
* ``smoke_two_level_text``, ``net_gate_file``, ``distilled_read`` (task LS1-M4-T2; M4-T3 and M4-T7 use them again): the
  SMOKE gate file cut to variant base with the two-level table (optionally run 0's mark, a filled Strike recipe and
  the LS1.4 heads gate file's shape: pool on, a second variant on the base reference cells, a run 0 per variant);
  that text as a net gate file with tiny networks (``NET_SEED``) for the training driver; a fake LS1.2 read
  (``results.json`` of ``scripts/ste_ls1_equivalence.py``) of one side's network.

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
READING_IN_NET_FILES = True              # set by LS1-M4-T1 (a net gate file's [reading] section is required)
CHOICE_ANCHOR = re.compile(r'^choice = "two_level".*$', re.MULTILINE)   # the whole line, its comment included
HOLD = 12                                # the tiny learner's decision ticks (tests/test_ste_l3_export.py)
UNFILLED = "FILL_OWNER_R38"               # an owner key not set yet (R38; exploit.FILL_MARK convention)

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


def net_gates_text(base_text: str, nets: dict, reading: bool | None = None) -> str:
    """A net gate file's text (C4): ``base_text`` (a two-level gate file's text) with ``skill_source = "net"`` after
    its ``choice = "two_level"`` line and a ``[learner.skill_net]`` table of ``nets`` {side: (file, sha256)} appended
    at the end (a table header after the choice line would take the keys that follow it, ``mask_absent`` in
    skills_gates.toml); then ``reading_block()`` when ``reading`` (None: ``READING_IN_NET_FILES``; False writes a net
    file without ``[reading]``, which ``exploit.load_gates`` refuses from LS1-M4-T1 on, for the tests of refusals and
    of loaders that refuse a net before they see the section)."""
    text = after_choice_line(base_text, 'skill_source = "net"')
    table = ["", "[learner.skill_net]"] + [f"{side} = {{ file = {json.dumps(str(f))}, sha256 = {json.dumps(str(s))} }}"
                                           for side, (f, s) in nets.items()]
    text = text.rstrip("\n") + "\n" + "\n".join(table) + "\n"
    if (READING_IN_NET_FILES if reading is None else reading):
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


def _unfill(node: dict) -> dict:
    return {k: _unfill(v) if isinstance(v, dict) else UNFILLED for k, v in node.items()}


def unfilled_distil(data: dict | None = None) -> dict:
    """The committed distillation gate file's dict (or ``data``) with every owner key (the keys of ``STAND_IN``'s
    ``limits`` and ``controls``, nested tables included) set to ``UNFILLED``: the gate file as it stood before the owner
    set the limits (R38), whatever the committed file holds today."""
    data = copy.deepcopy(data if data is not None else committed_distil())
    data["limits"] = _unfill(STAND_IN["limits"])
    data["controls"] = _unfill(STAND_IN["controls"])
    return data


def write_unfilled_distil_gates(tmp_path, name: str = "distil_gates_unfilled.toml") -> Path:
    """``toml_text(unfilled_distil())`` written under ``tmp_path``."""
    return write_distil_gates(tmp_path, unfilled_distil(), name=name)


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


def tiny_skill_net(tmp_path, side, gates=None, **tiny_kw) -> tuple[skill_net.SkillNet, dict, Path, str]:
    """``save_tiny_net(tmp_path, side, cfg)`` (the base variant's game of ``gates``, default the skills gate file)
    loaded back as the export takes it (task LS1-M3-T2): (net in ``eval()``, its meta, absolute path, sha256)."""
    gates = _gates(gates)
    cfg = exploit.variant_cfg(gates, "base")
    path, sha = save_tiny_net(tmp_path, side, cfg, gates=gates, **tiny_kw)
    net, meta = skill_net.load_skill_net(path, team=side, skills=skills.team_skills(gates.players, side), cfg=cfg,
                                         device="cpu", file_sha256=sha)
    return net, meta, path, sha


def net_gates_file(tmp_path, nets: dict | None = None, base=SKILLS_GATES, name="net_gates.toml") -> tuple[Path, dict]:
    """A net gate file under ``tmp_path``: ``net_gates_text(base text, nets)`` (task LS1-M3-T3). ``nets`` {side: (file,
    sha256)}; when None, a tiny network of each side (``save_tiny_net`` on the base variant's game of ``base``) is saved
    under ``tmp_path`` first. Returns (the gate file's path, nets)."""
    tmp_path = Path(tmp_path)
    if nets is None:
        gates = exploit.load_gates(base)
        cfg = exploit.variant_cfg(gates, "base")
        nets = {side: save_tiny_net(tmp_path, side, cfg, gates=gates) for side in ("guard", "strike")}
    path = tmp_path / name
    path.write_text(net_gates_text(Path(base).read_text(), nets))
    return path, nets


# ================================================================================ LS1-M4-T2: the driver's net gate file
SMOKE_GATES = ROOT / "configs" / "ste_l012" / "smoke_gates.toml"
SMOKE_TWO_LEVEL = TIER2_TWO_LEVEL      # the same text as tests/test_ste_l3_driver.py TWO_LEVEL (its lines 24-40)
SMOKE_VARIANT_LINE = re.compile(r"(?m)^(tag_1p2|tag_1p4) = \{ game = .*\n")
SMOKE_BASE_LINE = re.compile(r"(?m)^base = \{ game = .*$")
SMOKE_ORDER = 'order = ["base", "tag_1p2", "tag_1p4"]'
SMOKE_TIMING = 'timing_batches = [{ variant = "tag_1p2", side = "strike" }]'
SMOKE_RUN0_SCRIPT = 'script = "strike_straight"'
SMOKE_OVERRIDES = "side_overrides = { strike = {}, guard = {} }"
NET_SEED = 6                           # the tiny networks' weights: picked (CPU probe, 26 Nov 2026) so that on both
                                       # sides the untrained team's cell differs from the scripts' first-skill cell
                                       # and from a twin of the second drone skill (seed 5: every Strike game unfinished)
SECOND_VARIANT = "base_s2"             # the heads gate file's shape (LS1-M4-T4): a second seed of base, its own run 0
SECOND_SEEDS = {"strike": 120401, "guard": 120402}   # not a seed of the smoke file (120001 to 120950)
SECOND_RUN0_SEED = 120403
POOL_SEED = 120404


def _once(text: str, old: str, new: str) -> str:
    assert text.count(old) == 1, f"{old!r} occurs {text.count(old)} times, not once"
    return text.replace(old, new, 1)


def smoke_two_level_text(reach_min: float | None = None, heads_shape: bool = False,
                         strike_recipe: dict | None = None) -> str:
    """The SMOKE gate file (configs/ste_l012/smoke_gates.toml) cut to variant base (``verdict.order`` and the pilot's
    timing batch on base: a tiny network pins the base game's file and constants) plus the two-level table, scripts
    route. ``reach_min``: ``[run0] skills_reach_min`` (a skills run 0 needs it; the loader then needs
    ``SKILLS_RUN0_EVAL_GAMES`` patched to the smoke's 8 evaluation games). ``heads_shape``: the LS1.4 heads gate file's
    shape (LS1-M4-T4): a second variant ``base_s2`` of the base game with ``reference_variant = "base"`` and its own
    ``run0_seed``, ``[run0] per_variant = true`` and ``[pool]`` on. ``strike_recipe``: ``[trainer]
    side_overrides.strike`` filled (from a pilot, as L0.12's FILL steps)."""
    text = SMOKE_VARIANT_LINE.sub("", SMOKE_GATES.read_text())
    assert not SMOKE_VARIANT_LINE.search(text) and len(SMOKE_BASE_LINE.findall(text)) == 1
    variants = ["base"]
    if heads_shape:
        second = (f'{SECOND_VARIANT} = {{ game = "base", g_star = "guard_mark_edge", s_star = "strike_straight", '
                  f'role = "second seed of base (test)", train_seed = {toml_value(SECOND_SEEDS)}, '
                  f'extra_eval_opponents = {{ strike = [], guard = [] }}, reference_variant = "base", '
                  f'run0_seed = {SECOND_RUN0_SEED} }}')
        text = SMOKE_BASE_LINE.sub(lambda m: m.group(0) + "\n" + second, text, count=1)
        text = _once(text, "[run0]\n", "[run0]\nper_variant = true\n")
        variants.append(SECOND_VARIANT)
    text = _once(text, SMOKE_ORDER, f"order = {toml_value(variants)}")
    text = _once(text, SMOKE_TIMING, 'timing_batches = [{ variant = "base", side = "strike" }]')
    if reach_min is not None:
        text = _once(text, SMOKE_RUN0_SCRIPT, f"{SMOKE_RUN0_SCRIPT}\nskills_reach_min = {reach_min!r}")
    if strike_recipe:
        text = _once(text, SMOKE_OVERRIDES, f"side_overrides = {{ strike = {toml_value(strike_recipe)}, guard = {{}} }}")
    text += SMOKE_TWO_LEVEL
    if heads_shape:
        text += f"\n[pool]\nenabled = true\nseed = {POOL_SEED}\n"
    return text


def net_gate_file(folder, *, nets: dict | None = None, net_seed: int = NET_SEED, reach_min: float | None = None,
                  heads_shape: bool = False, strike_recipe: dict | None = None,
                  name: str = "gates.toml") -> tuple[Path, dict]:
    """A net gate file for the training driver (task LS1-M4-T2): ``smoke_two_level_text(...)`` through
    ``net_gates_text`` (so it carries the ``[reading]`` block filled from ``STAND_IN``, ``unfilled()`` is empty and the
    preflight passes), written as ``folder/name``. ``nets`` {side: (file, sha256)}; when None, a tiny network of each
    side (``save_tiny_net``, weights from ``net_seed``, on the base game of the scripts version of the same text) is
    saved under ``folder/nets`` first. The twin's code is fixed by the driver (``choice(FREE, first drone skill)``),
    not by this file. Returns (the gate file's path, nets)."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    text = smoke_two_level_text(reach_min, heads_shape, strike_recipe)
    if nets is None:
        scripts = folder / "scripts_twin_gates.toml"
        scripts.write_text(smoke_two_level_text())
        gates = exploit.load_gates(scripts)
        cfg = exploit.variant_cfg(gates, "base")
        nets = {side: save_tiny_net(folder / "nets", side, cfg, gates=gates, seed=net_seed)
                for side in ("guard", "strike")}
    path = folder / name
    path.write_text(net_gates_text(text, nets))
    return path, nets


def distilled_read(folder, side: str, net_sha256: str, *, verdict: str = "DISTILLED", of_record: bool = True,
                   complete: bool = True) -> Path:
    """A fake LS1.2 read of one side's network (``scripts/ste_ls1_equivalence.py`` results.json: exactly its
    ``RESULT_KEYS``, ``complete`` last; one cell row of its ``CELL_KEYS`` carrying ``side``): ``verdict`` (default
    DISTILLED), ``of_record`` and ``net_sha256`` as given; ``complete`` False leaves the key out (a read still being
    written). Used by M4-T3 and M4-T7. Returns the results.json path."""
    import ste_ls1_equivalence as eq          # scripts/ (the caller puts it on sys.path, as for the training driver)
    cell = {k: None for k in eq.CELL_KEYS}
    cell.update(side=side, arm="net")
    res = {k: None for k in eq.RESULT_KEYS}
    res.update(controls={}, cells=[cell], intervals={}, pooled={}, errors={}, failures=[], verdict=verdict,
               reasons=[], of_record=bool(of_record), gates_sha256="synthetic (tests/_ste_ls1.py)",
               net_sha256=net_sha256, skill_net_file=f"skill_net_{side}.pt", complete=True)
    if not complete:
        del res["complete"]
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / eq.RESULTS
    path.write_text(json.dumps(res, indent=1) + "\n")
    return path
