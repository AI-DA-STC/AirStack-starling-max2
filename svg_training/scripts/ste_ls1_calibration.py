#!/usr/bin/env python
"""STE route 3, stage LS1, job LS1.5: the calibration read (task LS1-M1-T7; plan ste_learning/drafts/LS1_TASK_PLAN.md).

    ste_ls1_calibration.py --calibration configs/ste_ls1/calibration.toml --side guard|strike
                           --out runs/<date>_ste_ls1_calibration_<side> --expect-sha256 <sha256 of the calibration file>
                           [--chunk K] [--cap-h H]
                           [--games N] [--opponents NAME ...] [--arms NAME ...] [--mixed N]     (test-only)

Launch: ``scripts/ste_job.py launch --task LS1.5 --gpu-h 0 ... -- <this command>`` (a CPU job; no --cap-h: no cap).
The scripts against changed scripts (``opponents/perturbed.py``; ``scripted.py`` untouched), no network, on the gate
read's cells (``configs/ste_ls1/cells.toml``) and T44's starts (seed ``ref.meta["seed"]``, hold 1, the skills gate
file's ``[run] ticks_cap``), at ``cells.toml [read] games_per_cell`` games per cell: which sizes of command error change
which games, on the gate's own ruler (C7, ``ste/cells.py``). Tier 1; observed in the training simulator. No pass or
fail: the owner sets the LS1 limits from this read (R38).

The cells of a side (``side_cells``): every choice (the K fixed ones, then the 20 mixed combinations of cells.toml)
against every script of the other team's ``[players]`` (gated: m = (K + 20) x that list, Guard 150, Strike 130), then
against cells.toml ``[info_opponents]`` (INFO: not gated, not in m). Ordered opponent by opponent; a game batch (one
``exploit.play_cells`` call) holds at most ``chunk_cells`` cells of ONE opponent (a batch runs to its longest game).

The arms (``arms_of``), each a player per cell named ``cal:<arm>:<choice>@<opponent>`` (C6; one object per cell):
* reference: the scripts (``orc:<choice>@<opponent>``, a ``cells.Composite`` of the script names). On the gated fixed
  cells the reference is T44 itself (no play); it is played on the mixed and the info cells (no T44 cell there);
* identity: every member wrapped at scale 1 on all four channels (the wrapper's exact identity: x 1 keeps every bit,
  the sign of a zero included; a noise or bias of 0 adds +-0.0 and could flip a zero's sign);
* ``noise=<s>`` on ``[noise] channels``; ``noise_active=<s>`` on each skill's active channels only (a skill with none
  flies the identity); ``bias=<s>`` on ``[bias] channels``; ``zero_bias=<s>`` only on the gated fixed cells of the
  zero-command skill; ``scale=<s>``; ``turn=<degrees>``; one arm per moved-switch value (``<switch key>=<value>``),
  played only on the cells where its code flies (team strategies: their fixed cells; flank: its fixed cells and the
  combinations that hold it), the moved player through ``perturbed.SwitchRecorder``.
A uniform choice (every drone the same code) is one changed player, as T44 played the script; a mixed one a
``Composite`` of one changed member per drone slot. Noise seeds: ``[noise] seed`` + the cell's index in the side's FULL
cell list x the team size + the drone slot (common to every noise arm; independent of chunking and of the test-only
options). The active channels and the zero-command skill come from the identity arm's labels (M2-T3's rule,
``cells.active_rule``: a channel is active where any script label on it is not 0.0), so the ladders play after it.

Order and controls (``controls.json``, written as each batch is checked): phase 1, chunk by chunk, the reference batch
then the identity batch; phase 2, chunk by chunk, every other arm. Every batch: paired starts, tags one for one, no
non-finite action (``scoring.plumbing_controls``) and every game finished. Identity batches also: (a) every gated fixed
cell equals T44 game for game (``exploit.replay_ok``, CPU); (b) b = c = 0 against the reference on every cell. A control
not PASS stops the run: exit 6 (5 for a non-finite action), terminal.

Per arm (``results.json``): per cell b, c, flips, diff with ``ci_plain`` (plain alpha) and ``ci_adjusted``
(``adjusted_z(alpha, m)``), sign-test p, end-step statistics and its games' place in its batch file; across cells the
median and largest flips, the largest |b - c|, the pooled difference (all gated, fixed, mixed, info; at plain alpha),
the cells with p < alpha and those whose adjusted interval excludes 0; the command error per skill on the gated fixed
cells (M2's table: rmse, max_abs, active, rows; zero_skill) and the three numbers the limits read. The permuted
scripts (R2 OA-6), no play: code k flies T44's cell of code ``perm[k]`` (cells.toml ``[permutation]``) against T44's
cell of code k, on the gated fixed cells. ``results.md`` sorts them by flips and by |diff|.

Files in ``--out``: ``layout.json`` (the run's layout, pinned at the first launch), ``batch_<arm>__<opponent>_<chunk>.npz``
(``scoring.save_batch`` plus the batch's command-error accumulators per cell and drone slot, written before the batch
counts as done), ``controls.json``, ``timing.json`` (seconds per batch, the lead's cost read), ``results.json``
(``complete`` last, built from the batch files only, so a resumed run gives the uninterrupted run's file) and
``results.md``. The run contract (``ste/run_contract.py``): the same command resumes at the next batch not yet done;
SIGINT or SIGTERM stops before the next tick (exit 4, the partial batch dropped); ``--cap-h`` (optional) caps effective
hours (exit 3).

Test-only options (each writes ``of_record: false``): ``--games N`` (the first N starts), ``--opponents`` (a subset of the
side's opponents), ``--arms`` (a subset of the ladder arms; the reference and identity arms always play), ``--mixed N``
(the first N combinations). ``m`` stays the committed layout's.

Exit codes: 0 done; 2 refused (bad arguments, a pin off, a finished folder, another layout in the folder); 3 cap; 4
stopped on request; 5 a non-finite value; 6 a control failed (terminal: the same command on the folder ends with 6
again)."""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import time
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
sys.path.insert(0, str(ROOT / "scripts"))

import numpy as np  # noqa: E402

import ste_l3_held_arm as held  # noqa: E402  (the input checks of the skills gate file)
import ste_sweep_l011 as l011  # noqa: E402  (the simulator words, JSON writing)
from svg_training.core.rewards import GUARD_WIN, RUNNING, STRIKE_WIN  # noqa: E402
from svg_training.opponents import perturbed  # noqa: E402
from svg_training.opponents.scripted import REGISTRY, make_strategy  # noqa: E402
from svg_training.ste import atomic, cells, exploit, scoring, skills, sweep  # noqa: E402
from svg_training.ste.run_contract import (EXIT_CONTROL_FAILED, EXIT_DONE, EXIT_FOR_STOP, EXIT_NONFINITE,  # noqa: E402
                                           EXIT_REFUSED, STOP_INTERRUPTED, NonFiniteError, RunBusyError, RunGuard)

FORMAT = "ste-ls1-calibration-1"
CONTROLS_FILE, RESULTS, RESULTS_MD = "controls.json", "results.json", "results.md"
LAYOUT_FILE, TIMING_FILE = "layout.json", "timing.json"
BATCH_PREFIX = "batch_"
HOUR_S = 3600.0
PASS, FAIL = scoring.PASS, scoring.FAIL
SCRIPTED = ROOT / "source" / "svg_training" / "opponents" / "scripted.py"
FIXED, MIXED, INFO = "fixed", "mixed", "info"
REFERENCE, IDENTITY = "reference", "identity"
NOISE, NOISE_ACTIVE, BIAS, ZERO_BIAS, SCALE, TURN, SWITCH = ("noise", "noise_active", "bias", "zero_bias", "scale",
                                                             "turn", "switch")
ALL_CHANNELS = tuple(range(perturbed.COMMAND_DIM))
HOLD_TICKS = 1                     # C6: every read plays hold 1
# the moved switches: key -> (team, the code it moves, the moved player, its keyword) (R2 OA-3)
SWITCHES = {
    "sacrifice_entry_rad": ("strike", "strike_sacrifice", perturbed.SacrificeMovedEntry, "entry_half_angle_rad"),
    "converge_gather_rad": ("strike", "strike_converge", perturbed.ConvergeMovedGather, "gather_angle_rad"),
    "flank_margin_m": ("strike", "strike_flank", perturbed.FlankMoved, "margin_m"),
    "field_range_m": ("guard", "guard_field", perturbed.FieldMovedRange, "range_m"),
}
CAL_KEYS = {
    "noise": {"sizes", "channels", "active_only_arm", "seed"},
    "bias": {"sizes", "channels", "zero_skill_sizes"},
    "scale": {"size", "channels"},
    "turn": {"degrees"},
    "switch": set(SWITCHES),
    "run": {"chunk_cells", "device"},
    "intervals": {"alpha"},
    "source": {"skills_gates", "skills_gates_sha256", "cells", "cells_sha256", "scripted_sha256"},
}
CELLS_KEYS = {"mixed": {"seed", "guard", "strike"}, "permutation": {"guard", "strike"},
              "info_opponents": {"guard", "strike"}, "read": {"games_per_cell"}}
RESULT_KEYS = {"format", "side", "of_record", "overrides", "simulator", "calibration_file", "calibration_sha256",
               "cells_file", "cells_sha256", "skills_gates", "skills_gates_sha256", "scripted_sha256", "reference_file",
               "reference_sha256", "variant", "device", "seed", "ticks_cap", "hold_ticks", "games_per_cell",
               "chunk_cells", "opponents", "info_opponents", "intervals", "controls", "labels", "batches", "arms",
               "cells", "permuted", "complete"}
CELL_KEYS = {"arm", "kind", "choice", "codes", "opponent", "index", "n", "b", "c", "flips", "diff", "ci_plain",
             "ci_adjusted", "sign_test_p", "method", "end_time", "games"}
ARM_KEYS = {"kind", "size", "channels", "switch", "cells", "flips_median", "flips_max", "max_abs_b_minus_c", "pooled",
            "p_below_alpha", "adjusted_excludes_zero", "errors", "error_summary"}
LABEL_RULE = ("M2-T3's rule (ste/cells.active_rule) on the identity arm's labels (the scripts' own commands on the "
              "states played, live drones of each slot's first game, every cell): a channel is active where any label "
              "is not 0.0; a skill with no active channel is the zero-command skill")
OBSERVED = "observed in the training simulator"


def say(text: str) -> None:
    print(f"[ls1.5] {text}", flush=True)


def refuse(why: str) -> int:
    print(f"[ls1.5] REFUSED: {why}", file=sys.stderr, flush=True)
    return EXIT_REFUSED


def _label(value) -> str:
    return repr(float(value))


# ================================================================================================ the two files
def _exact(data: dict, keys: dict, what: str) -> None:
    extra = set(data) - set(keys)
    if extra:
        raise ValueError(f"{what}: unknown section(s) {sorted(extra)}")
    for section, want in keys.items():
        if section not in data or not isinstance(data[section], dict):
            raise ValueError(f"{what}: missing section [{section}]")
        got = set(data[section])
        if want - got:
            raise ValueError(f"{what}: [{section}] misses {sorted(want - got)}")
        if got - want:
            raise ValueError(f"{what}: [{section}] has unknown key(s) {sorted(got - want)}")


def _number(v, what: str, positive: bool = True) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or (positive and v <= 0):
        raise ValueError(f"{what} must be a finite number{' above 0' if positive else ''}, got {v!r}")
    return float(v)


def _numbers(v, what: str) -> list[float]:
    if not isinstance(v, list) or not v:
        raise ValueError(f"{what} must be a non-empty list of numbers, got {v!r}")
    out = [_number(x, what) for x in v]
    if len(set(out)) != len(out):
        raise ValueError(f"{what}: repeated values {v!r}")
    return out


def _channels(v, what: str) -> tuple[int, ...]:
    if (not isinstance(v, list) or not v or any(isinstance(c, bool) or not isinstance(c, int) for c in v)
            or len(set(v)) != len(v) or not all(c in ALL_CHANNELS for c in v)):
        raise ValueError(f"{what} must be distinct channel indices in {list(ALL_CHANNELS)}, got {v!r}")
    return tuple(v)


def load_calibration(path: Path) -> dict:
    """calibration.toml: every key required, none unknown, each checked (ValueError)."""
    data = tomllib.loads(Path(path).read_text())
    _exact(data, CAL_KEYS, str(path))
    n, b, s, t, w, r = (data[k] for k in ("noise", "bias", "scale", "turn", "switch", "run"))
    _numbers(n["sizes"], "[noise] sizes")
    _channels(n["channels"], "[noise] channels")
    _number(n["active_only_arm"], "[noise] active_only_arm")
    if isinstance(n["seed"], bool) or not isinstance(n["seed"], int) or n["seed"] < 0:
        raise ValueError(f"[noise] seed must be a whole number, got {n['seed']!r}")
    _numbers(b["sizes"], "[bias] sizes")
    _channels(b["channels"], "[bias] channels")
    _numbers(b["zero_skill_sizes"], "[bias] zero_skill_sizes")
    _number(s["size"], "[scale] size")
    _channels(s["channels"], "[scale] channels")
    _numbers(t["degrees"], "[turn] degrees")
    for key in SWITCHES:
        _numbers(w[key], f"[switch] {key}")
    if isinstance(r["chunk_cells"], bool) or not isinstance(r["chunk_cells"], int) or r["chunk_cells"] < 1:
        raise ValueError(f"[run] chunk_cells must be a whole number >= 1, got {r['chunk_cells']!r}")
    if not isinstance(r["device"], str):
        raise ValueError(f"[run] device must be a string, got {r['device']!r}")
    alpha = _number(data["intervals"]["alpha"], "[intervals] alpha")
    if not alpha < 1:
        raise ValueError(f"[intervals] alpha must be below 1, got {alpha!r}")
    for key in ("skills_gates", "cells"):
        if not isinstance(data["source"][key], str):
            raise ValueError(f"[source] {key} must be a repository-relative path")
    for key in ("skills_gates_sha256", "cells_sha256", "scripted_sha256"):
        if not re.fullmatch(r"[0-9a-f]{64}", str(data["source"][key])):
            raise ValueError(f"[source] {key} must be a sha256 (64 hex digits), got {data['source'][key]!r}")
    return data


def load_cells(path: Path) -> dict:
    """cells.toml: every key required, none unknown (ValueError); the members are checked against a side's spec by
    :func:`check_cells`."""
    data = tomllib.loads(Path(path).read_text())
    _exact(data, CELLS_KEYS, str(path))
    games = data["read"]["games_per_cell"]
    if isinstance(games, bool) or not isinstance(games, int) or games < 1:
        raise ValueError(f"[read] games_per_cell must be a whole number >= 1, got {games!r}")
    return data


def check_cells(spec: cells.CellSpec, cells_cfg: dict, gates) -> str | None:
    """Why cells.toml does not fit ``spec``'s side of the skills gate file, or None."""
    side = spec.side
    try:
        cells.mixed_choices(spec, [tuple(c) for c in cells_cfg["mixed"][side]])
    except ValueError as err:
        return f"cells.toml [mixed] {side}: {err}"
    combos = [tuple(c) for c in cells_cfg["mixed"][side]]
    if len(set(combos)) != len(combos):
        return f"cells.toml [mixed] {side}: a combination is repeated"
    perm = list(cells_cfg["permutation"][side])
    if sorted(perm) != list(range(len(spec.players))) or any(p == i for i, p in enumerate(perm)):
        return f"cells.toml [permutation] {side} = {perm} is not a derangement of the {len(spec.players)} codes"
    gated = skills.team_skills(gates.players, cells.other(side))
    for name in cells_cfg["info_opponents"][side]:
        team = getattr(REGISTRY.get(name), "TEAM", "unknown")
        if name in gated or team not in (None, cells.other(side)):
            return f"cells.toml [info_opponents] {side}: {name!r} is not an ungated script of the {cells.other(side)} team"
    return None


# ================================================================================================ cells and arms
@dataclass(frozen=True)
class Cell:
    """One cell of a side: ``index`` in the side's full list (opponent by opponent; per opponent the K fixed choices,
    then the mixed combinations), the ``choice`` (``cells.fixed_choices`` / ``mixed_choices``), the ``opponent``, and
    the ``kind`` (fixed, mixed: gated; info)."""
    index: int
    choice: dict = field(compare=False)
    opponent: str
    kind: str


@dataclass(frozen=True)
class Arm:
    """An arm: its ``name`` (``<kind>=<value>``), ``kind``, ``size`` (the noise half-width, bias, scale, degrees or the
    moved value), ``channels``, and for a moved switch its ``switch`` key."""
    name: str
    kind: str
    size: float | None = None
    channels: tuple = ()
    switch: str | None = None

    @property
    def phase(self) -> int:
        return 1 if self.kind in (REFERENCE, IDENTITY) else 2


REFERENCE_ARM = Arm(REFERENCE, REFERENCE)
IDENTITY_ARM = Arm(IDENTITY, IDENTITY, 1.0, ALL_CHANNELS)


def gated_opponents(gates, side: str) -> list[str]:
    return skills.team_skills(gates.players, cells.other(side))


def side_cells(spec: cells.CellSpec, cells_cfg: dict, gates) -> list[Cell]:
    """Every cell of ``spec.side``, gated then info opponents (see :class:`Cell`)."""
    info = list(cells_cfg["info_opponents"][spec.side])
    choices = cells.fixed_choices(spec) + cells.mixed_choices(spec, [tuple(c) for c in cells_cfg["mixed"][spec.side]])
    out = []
    for opp in gated_opponents(gates, spec.side) + info:
        for j, choice in enumerate(choices):
            kind = INFO if opp in info else FIXED if j < len(spec.players) else MIXED
            out.append(Cell(len(out), choice, opp, kind))
    return out


def gated_m(spec: cells.CellSpec, cells_cfg: dict, gates) -> int:
    """m of C7: the side's gated cells, (K + the mixed combinations) x the other team's [players]."""
    return (len(spec.players) + len(cells_cfg["mixed"][spec.side])) * len(gated_opponents(gates, spec.side))


def arms_of(calcfg: dict, side: str) -> list[Arm]:
    """The identity arm, then the ladder arms of ``side`` in calibration.toml order."""
    n, b, s = calcfg["noise"], calcfg["bias"], calcfg["scale"]
    out = [IDENTITY_ARM]
    out += [Arm(f"{NOISE}={_label(v)}", NOISE, float(v), tuple(n["channels"])) for v in n["sizes"]]
    out.append(Arm(f"{NOISE_ACTIVE}={_label(n['active_only_arm'])}", NOISE_ACTIVE, float(n["active_only_arm"])))
    out += [Arm(f"{BIAS}={_label(v)}", BIAS, float(v), tuple(b["channels"])) for v in b["sizes"]]
    out += [Arm(f"{ZERO_BIAS}={_label(v)}", ZERO_BIAS, float(v), tuple(b["channels"])) for v in b["zero_skill_sizes"]]
    out.append(Arm(f"{SCALE}={_label(s['size'])}", SCALE, float(s["size"]), tuple(s["channels"])))
    out += [Arm(f"{TURN}={_label(v)}", TURN, float(v), perturbed.XY) for v in calcfg["turn"]["degrees"]]
    for key, (team, _, _, _) in SWITCHES.items():
        if team == side:
            out += [Arm(f"{key}={_label(v)}", SWITCH, float(v), (), key) for v in calcfg["switch"][key]]
    return out


def labels_of(acc: dict) -> dict:
    """The identity arm's labels per skill -> {"active": {skill: [4] bool}, "zero_skills": [...], "rows": {skill}}."""
    active = {s: cells.active_rule(a["label_max_abs"]) for s, a in acc.items() if int(a["count"])}
    return {"active": active, "zero_skills": [s for s in active if not any(active[s])],
            "rows": {s: int(a["count"]) for s, a in acc.items()}}


def arm_cells(arm: Arm, among: list[Cell], labels: dict | None) -> list[Cell]:
    """The cells of ``among`` that ``arm`` plays."""
    if arm.kind == REFERENCE:
        return [c for c in among if c.kind != FIXED]
    if arm.kind == ZERO_BIAS:
        return [c for c in among if c.kind == FIXED and c.choice["script"] in labels["zero_skills"]]
    if arm.kind == SWITCH:
        code = SWITCHES[arm.switch][1]
        return [c for c in among if code in c.choice["flies"]]
    return list(among)


def player_name(arm: Arm, cell: Cell) -> str:
    """C6: one name per (arm, choice, opponent), prefixed so it never shadows a script."""
    tail = f"{cell.choice['name']}@{cell.opponent}"
    return cells.ORC_PREFIX + tail if arm.kind == REFERENCE else f"{cells.CAL_PREFIX}{arm.name}:{tail}"


def _member(arm: Arm, skill: str, slot: int, cell: Cell, spec: cells.CellSpec, script, noise_seed: int, labels: dict,
            cfg, n: int, device: str, seed: int, name: str | None):
    """The changed player of one drone slot (or of every slot, for a uniform choice)."""
    s_seed = noise_seed + cell.index * spec.drones + slot
    if arm.kind == IDENTITY:
        return perturbed.CommandPerturbation(script(skill), SCALE, 1.0, s_seed, ALL_CHANNELS, name=name)
    if arm.kind == NOISE_ACTIVE:
        ch = tuple(i for i, a in enumerate(labels["active"][skill]) if a)
        if not ch:                                  # a skill with no active channel: the identity, still recorded
            return perturbed.CommandPerturbation(script(skill), SCALE, 1.0, s_seed, ALL_CHANNELS, name=name)
        return perturbed.CommandPerturbation(script(skill), NOISE, arm.size, s_seed, ch, name=name)
    if arm.kind in (NOISE, BIAS, ZERO_BIAS, SCALE, TURN):
        kind = BIAS if arm.kind == ZERO_BIAS else arm.kind
        return perturbed.CommandPerturbation(script(skill), kind, arm.size, s_seed, arm.channels, name=name)
    if arm.kind == SWITCH:
        _, code, moved, keyword = SWITCHES[arm.switch]
        if skill != code:
            return skill                             # an unmoved slot of a mixed cell flies its script
        return perturbed.SwitchRecorder(moved(spec.side, cfg, n, device, seed, **{keyword: arm.size}), script(skill),
                                        name=name)
    raise ValueError(f"unknown arm kind {arm.kind!r}")


def batch_players(arm: Arm, among: list[Cell], spec: cells.CellSpec, cfg, n: int, device: str, seed: int,
                  labels: dict | None, calcfg: dict) -> tuple[dict, list, list]:
    """The players of one game batch: ({name: player}, the play_cells cells [(guard, strike)], per cell the recorders
    [(slot, recorder)]). Scripts are seeded as ``exploit.play_cells`` seeds a named script (seed + the team offset)."""
    side = spec.side
    off = exploit.GUARD_SEED_OFFSET if side == cells.SIDES[0] else exploit.STRIKE_SEED_OFFSET
    noise_seed = int(calcfg["noise"]["seed"])

    def script(name):
        return make_strategy(name, side, cfg, n, device, seed + off)

    players, pairs, recorders = {}, [], []
    for cell in among:
        flies, name = cell.choice["flies"], player_name(arm, cell)
        if arm.kind == REFERENCE:
            player, rec = cells.Composite(side, list(flies), cfg, n, device, seed + off, name=name), []
        elif len(set(flies)) == 1:
            player = _member(arm, flies[0], 0, cell, spec, script, noise_seed, labels, cfg, n, device, seed + off, name)
            rec = [(m, player) for m in range(spec.drones)]
        else:
            members = [_member(arm, s, m, cell, spec, script, noise_seed, labels, cfg, n, device, seed + off, None)
                       for m, s in enumerate(flies)]
            player = cells.Composite(side, members, cfg, n, device, seed + off, name=name)
            rec = [(m, p) for m, p in enumerate(members) if hasattr(p, "errors")]
        if name in players:
            raise ValueError(f"two cells of one batch share the player name {name!r} (C6: one object per cell)")
        players[name] = player
        pairs.append(cells.cell_of(side, name, cell.opponent))
        recorders.append(rec)
    return players, pairs, recorders


def error_arrays(recorders: list, drones: int) -> dict:
    """The batch's command-error accumulators per cell and drone slot (host arrays, read once after the batch):
    err_sum_sq [C, M, 4] float64, err_max_abs and err_label_max_abs [C, M, 4] float32, err_count [C, M] int64; zero
    where no recorder flies the slot."""
    c, dim = len(recorders), perturbed.COMMAND_DIM
    out = {"err_sum_sq": np.zeros((c, drones, dim)), "err_max_abs": np.zeros((c, drones, dim), dtype=np.float32),
           "err_label_max_abs": np.zeros((c, drones, dim), dtype=np.float32),
           "err_count": np.zeros((c, drones), dtype=np.int64)}
    for i, rec in enumerate(recorders):
        for slot, obj in rec:
            e = obj.errors()
            if e is None:
                continue
            out["err_sum_sq"][i, slot] = e["sum_sq"][slot].cpu().numpy()
            out["err_max_abs"][i, slot] = e["max_abs"][slot].cpu().numpy()
            out["err_label_max_abs"][i, slot] = e["ref_max_abs"][slot].cpu().numpy()
            out["err_count"][i, slot] = int(e["count"][slot])
    return out


def chunks_of(among: list[Cell], size: int) -> list[tuple[str, list[Cell]]]:
    """Consecutive groups of at most ``size`` cells, never two opponents in one group: [(chunk id, cells)]."""
    out, by_opp = [], {}
    for cell in among:
        by_opp.setdefault(cell.opponent, []).append(cell)
    for opp, group in by_opp.items():
        for j in range(0, len(group), size):
            out.append((f"{opp}_{j // size:02d}", group[j:j + size]))
    return out


@dataclass
class Batch:
    name: str
    arm: Arm
    chunk: str
    cells: list


def batch_name(arm: Arm, chunk: str) -> str:
    return BATCH_PREFIX + re.sub(r"[^A-Za-z0-9_.-]", "_", arm.name) + "__" + chunk


def phase_batches(arms: list[Arm], chunks: list, labels: dict | None) -> list[Batch]:
    out = []
    for chunk, among in chunks:
        for arm in arms:
            mine = arm_cells(arm, among, labels)
            if mine:
                out.append(Batch(batch_name(arm, chunk), arm, chunk, mine))
    return out


# ================================================================================================ the run
@dataclass
class Ctx:
    a: argparse.Namespace
    calcfg: dict
    cal_sha: str
    cells_cfg: dict
    gates: object
    spec: cells.CellSpec
    variant: str
    ref: object
    cfg: object
    n: int
    chunk: int
    device: str
    seed: int
    ticks: int
    cells: list
    arms: list
    m: int
    alpha: float
    z_plain: float
    z_cell: float
    of_record: bool
    overrides: dict
    out: Path


def t44_of(ctx: Ctx, cell: Cell, code: str | None = None) -> dict:
    """T44's per-game record of a gated fixed cell (``code`` instead of the cell's own script: the permuted read)."""
    pg = ctx.ref.cell(ctx.variant, *cells.cell_of(ctx.spec.side, code or cell.choice["script"], cell.opponent))
    return {k: np.asarray(v)[:ctx.n] for k, v in pg.items()}


def _path(ctx: Ctx, batch: Batch) -> Path:
    return ctx.out / f"{batch.name}.npz"


def _load(ctx: Ctx, batch: Batch, cache: dict) -> dict:
    if batch.name not in cache:
        cache[batch.name] = scoring.load_batch(_path(ctx, batch))
    return cache[batch.name]


def _where(batches: list[Batch]) -> dict:
    """(arm name, cell index) -> (batch, place in the batch)."""
    return {(b.arm.name, c.index): (b, i) for b in batches for i, c in enumerate(b.cells)}


def reference_of(ctx: Ctx, cell: Cell, where: dict, cache: dict) -> dict:
    """The reference's per-game record of a cell: T44 on the gated fixed cells, the played scripts elsewhere."""
    if cell.kind == FIXED:
        return t44_of(ctx, cell)
    b, i = where[(REFERENCE, cell.index)]
    return exploit.slice_cell(_load(ctx, b, cache), i, ctx.n)


def check_batch(ctx: Ctx, batch: Batch, pg: dict, where: dict, cache: dict) -> dict:
    """The batch's controls (module docstring): {"status", "phase", "detail", "parts"}."""
    phase = "controls" if batch.arm.phase == 1 else "ladder"
    parts = scoring.plumbing_controls(pg, ctx.ref, ctx.n, phase)
    unfinished = int(np.sum(np.asarray(pg["outcome"]) == RUNNING))
    parts["all_games_finished"] = {"status": PASS if unfinished == 0 else FAIL, "phase": phase,
                                   "detail": f"{unfinished} unfinished games of {len(pg['outcome'])}"}
    if batch.arm.kind == IDENTITY:
        replay_bad, flips, fixed = [], [], 0
        for i, cell in enumerate(batch.cells):
            mine = exploit.slice_cell(pg, i, ctx.n)
            if cell.kind == FIXED:
                fixed += 1
                good, text = exploit.replay_ok(mine, t44_of(ctx, cell), ctx.device, ctx.gates.controls,
                                               ticks_cap=ctx.ticks)
                if not good:
                    replay_bad.append(f"{cell.choice['name']}@{cell.opponent}: {text}")
            if unfinished == 0:
                pc = cells.paired_cell(mine, reference_of(ctx, cell, where, cache), ctx.spec.side, ctx.z_plain)
                if pc["flips"]:
                    flips.append(f"{cell.choice['name']}@{cell.opponent}: b {pc['b']}, c {pc['c']}")
        if fixed:
            parts["replay_t44"] = {"status": PASS if not replay_bad else FAIL, "phase": phase,
                                   "detail": (f"{fixed} gated fixed cells equal T44 game for game" if not replay_bad
                                              else "; ".join(replay_bad))}
        parts["identity_no_flip"] = {"status": PASS if not flips and unfinished == 0 else FAIL, "phase": phase,
                                     "detail": (f"b = c = 0 on {len(batch.cells)} cells against the reference"
                                                if not flips and unfinished == 0 else "; ".join(flips) or "unfinished")}
    status = scoring.control_status(parts, True)
    return {"status": status, "phase": phase, "arm": batch.arm.name, "cells": len(batch.cells),
            "detail": "; ".join(f"{k} {v['status']}" for k, v in parts.items()), "parts": parts}


def _labels_acc(ctx: Ctx, batches: list[Batch], cache: dict, gated_fixed_only: bool) -> dict:
    """Per skill (in the team's [players] order) the summed accumulators of ``batches``' cells (each slot to the skill
    it flies): {skill: {"sum_sq" [4], "max_abs" [4], "count", "label_max_abs" [4]}}."""
    dim = perturbed.COMMAND_DIM
    acc = {s: {"sum_sq": np.zeros(dim), "max_abs": np.zeros(dim), "count": 0, "label_max_abs": np.zeros(dim)}
           for s in ctx.spec.players}
    for b in batches:
        pg = _load(ctx, b, cache)
        for i, cell in enumerate(b.cells):
            if gated_fixed_only and cell.kind != FIXED:
                continue
            for slot, skill in enumerate(cell.choice["flies"]):
                a = acc[skill]
                a["sum_sq"] = a["sum_sq"] + pg["err_sum_sq"][i, slot]
                a["max_abs"] = np.maximum(a["max_abs"], pg["err_max_abs"][i, slot])
                a["label_max_abs"] = np.maximum(a["label_max_abs"], pg["err_label_max_abs"][i, slot])
                a["count"] += int(pg["err_count"][i, slot])
    return {s: {"sum_sq": a["sum_sq"].tolist(), "max_abs": a["max_abs"].tolist(), "count": a["count"],
                "label_max_abs": a["label_max_abs"].tolist()} for s, a in acc.items()}


def run(ctx: Ctx, guard: RunGuard) -> int:
    out = ctx.out
    controls = json.loads((out / CONTROLS_FILE).read_text()) if (out / CONTROLS_FILE).is_file() else {}
    timing = json.loads((out / TIMING_FILE).read_text()) if (out / TIMING_FILE).is_file() else {}
    latest = guard.load_latest()
    done = set(latest.state["done"]) if latest is not None else set()
    every, seen = int(ctx.gates.run["cap_check_every_ticks"]), [0]

    def should_stop() -> bool:
        if guard.stop_requested:
            return True
        seen[0] += 1
        return seen[0] % every == 0 and guard.cap_reached()

    def stopped() -> int:
        guard.save(len(done), {"done": sorted(done)})
        reason = guard.stop_reason() or STOP_INTERRUPTED
        say(f"stopped ({reason}); the same command resumes at the next batch not yet done")
        return EXIT_FOR_STOP[reason]

    def play(batches: list[Batch], labels: dict | None, where: dict, cache: dict) -> int | None:
        for batch in batches:
            path = _path(ctx, batch)
            if batch.name in done and path.is_file():
                continue
            if guard.stop_reason():
                return stopped()
            players, pairs, recorders = batch_players(batch.arm, batch.cells, ctx.spec, ctx.cfg, ctx.n, ctx.device,
                                                      ctx.seed, labels, ctx.calcfg)
            started = time.perf_counter()
            try:
                pg = exploit.play_cells(ctx.cfg, ctx.gates.run["size"], ctx.ref, pairs, ctx.n, ctx.device, ctx.seed,
                                        ctx.ticks, hold_ticks=HOLD_TICKS, should_stop=should_stop, players=players)
            except sweep.SweepStopped:
                return stopped()
            took = time.perf_counter() - started
            if batch.arm.kind != REFERENCE:
                pg.update(error_arrays(recorders, ctx.spec.drones))
            temporary = path.with_name(f"{batch.name}.part.npz")
            scoring.save_batch(temporary, pg)
            os.replace(temporary, path)
            cache.pop(batch.name, None)
            timing[batch.name] = {"seconds": took, "cells": len(batch.cells), "games_per_cell": ctx.n}
            l011.write_json(out / TIMING_FILE, timing)
            ctl = check_batch(ctx, batch, pg, where, cache)
            controls[batch.name] = ctl
            l011.write_json(out / CONTROLS_FILE, controls)
            done.add(batch.name)
            guard.save(len(done), {"done": sorted(done)})
            say(f"{batch.name}: {len(batch.cells)} cells x {ctx.n} games, {took:.1f} s, {ctl['status']}")
            code = scoring.ending({batch.name: ctl})
            if code is not None:
                say(f"{'NON-FINITE' if code == EXIT_NONFINITE else 'CONTROL FAILED'} in {batch.name}: {ctl['detail']}; "
                    f"no number is reported (exit {code}); the batch file is kept for diagnosis")
                return code
        return None

    chunks = chunks_of(ctx.cells, ctx.chunk)
    first = phase_batches([REFERENCE_ARM, IDENTITY_ARM], chunks, None)
    cache: dict = {}
    code = play(first, None, _where(first), cache)
    if code is not None:
        return code
    labels = labels_of(_labels_acc(ctx, [b for b in first if b.arm.kind == IDENTITY], cache, False))
    second = phase_batches([a for a in ctx.arms if a.phase == 2], chunks, labels)
    code = play(second, labels, _where(first), cache)
    if code is not None:
        return code
    if {controls.get(b.name, {}).get("status") for b in first + second} != {PASS}:
        return scoring.ending(controls) or EXIT_CONTROL_FAILED
    result = results_of(ctx, first, second, labels, controls, cache)
    try:
        json.dumps(result, allow_nan=False)
    except ValueError as err:
        say(f"NON-FINITE value in the results ({err}); nothing written (exit {EXIT_NONFINITE})")
        return EXIT_NONFINITE
    l011.write_json(out / RESULTS, result)
    atomic.write_text(out / RESULTS_MD, results_md(result))
    guard.save(len(done), {"done": sorted(done), "phase": "done"})
    say(f"done: {out / RESULTS_MD}")
    return EXIT_DONE


# ================================================================================================ the results
def _cell_entry(ctx: Ctx, arm: Arm, cell: Cell, mine: dict, ref_pg: dict, batch: Batch, i: int) -> dict:
    p = cells.paired_cell(mine, ref_pg, ctx.spec.side, ctx.z_plain)
    a = cells.paired_cell(mine, ref_pg, ctx.spec.side, ctx.z_cell)
    return {"arm": arm.name, "kind": cell.kind, "choice": cell.choice["name"], "codes": list(cell.choice["flies"]),
            "opponent": cell.opponent, "index": cell.index, "n": p["n"], "b": p["b"], "c": p["c"],
            "flips": p["flips"], "diff": p["diff"], "ci_plain": p["ci"], "ci_adjusted": a["ci"],
            "sign_test_p": p["sign_test_p"], "method": p["method"], "end_time": cells.end_time(mine, ref_pg),
            "games": {"file": f"{batch.name}.npz", "start": i * ctx.n, "stop": (i + 1) * ctx.n}}


def _excludes_zero(ci) -> bool:
    return ci is not None and (ci[0] > 0 or ci[1] < 0)


def _wins(ctx: Ctx, pg: dict) -> np.ndarray:
    win = GUARD_WIN if ctx.spec.side == cells.SIDES[0] else STRIKE_WIN
    return np.asarray(pg["outcome"]) == win


def arm_summary(ctx: Ctx, arm: Arm, rows: list[dict], wins: dict, errors: dict) -> dict:
    """Across one arm's cells: flips (median, largest), the largest |b - c|, the pooled differences (all gated, fixed,
    mixed, info; z_pooled), the cells with p < alpha and those whose adjusted interval excludes 0, the error table."""
    flips = [r["flips"] for r in rows]
    pooled = {}
    for group, kinds in (("all", (FIXED, MIXED)), ("fixed", (FIXED,)), ("mixed", (MIXED,)), ("info", (INFO,))):
        keys = [k for k, (kind, _, _) in wins.items() if kind in kinds]
        pooled[group] = cells.pooled_difference({k: wins[k][1] for k in keys}, {k: wins[k][2] for k in keys},
                                                ctx.z_plain)
    return {"kind": arm.kind, "size": arm.size, "channels": list(arm.channels), "switch": arm.switch,
            "cells": len(rows), "flips_median": float(np.median(flips)) if flips else None,
            "flips_max": max(flips) if flips else None,
            "max_abs_b_minus_c": max(abs(r["b"] - r["c"]) for r in rows) if rows else None, "pooled": pooled,
            "p_below_alpha": sum(1 for r in rows if r["sign_test_p"] is not None and r["sign_test_p"] < ctx.alpha),
            "adjusted_excludes_zero": sum(1 for r in rows if _excludes_zero(r["ci_adjusted"])),
            "errors": errors, "error_summary": cells.error_summary(errors)}


def permuted_read(ctx: Ctx) -> dict:
    """The permuted scripts from T44 alone (R2 OA-6), on the run's gated fixed cells: code k flies T44's cell of code
    perm[k] against T44's cell of code k. No play."""
    perm = list(ctx.cells_cfg["permutation"][ctx.spec.side])
    rows = []
    for cell in ctx.cells:
        if cell.kind != FIXED:
            continue
        k = ctx.spec.players.index(cell.choice["script"])
        flies = ctx.spec.players[perm[k]]
        mine, t44 = t44_of(ctx, cell, flies), t44_of(ctx, cell)
        p = cells.paired_cell(mine, t44, ctx.spec.side, ctx.z_plain)
        a = cells.paired_cell(mine, t44, ctx.spec.side, ctx.z_cell)
        rows.append({"code": cell.choice["script"], "flies": flies, "opponent": cell.opponent,
                     "name": f"{cells.PERM_PREFIX}{cell.choice['name']}@{cell.opponent}", "n": p["n"], "b": p["b"],
                     "c": p["c"], "flips": p["flips"], "diff": p["diff"], "ci_plain": p["ci"], "ci_adjusted": a["ci"],
                     "sign_test_p": p["sign_test_p"], "method": p["method"]})
    return {"permutation": perm, "cells": rows,
            "plain_excludes_zero": sum(1 for r in rows if _excludes_zero(r["ci_plain"])),
            "adjusted_excludes_zero": sum(1 for r in rows if _excludes_zero(r["ci_adjusted"]))}


def results_of(ctx: Ctx, first: list[Batch], second: list[Batch], labels: dict, controls: dict, cache: dict) -> dict:
    """results.json, from the batch files (and T44) only."""
    where = _where(first)
    played = [b for b in first + second if b.arm.kind != REFERENCE]
    rows, arms = [], {}
    for arm in [IDENTITY_ARM] + [a for a in ctx.arms if a.phase == 2]:
        mine_batches = [b for b in played if b.arm.name == arm.name]
        arm_rows, wins = [], {}
        for b in mine_batches:
            pg = _load(ctx, b, cache)
            for i, cell in enumerate(b.cells):
                mine, ref_pg = exploit.slice_cell(pg, i, ctx.n), reference_of(ctx, cell, where, cache)
                arm_rows.append(_cell_entry(ctx, arm, cell, mine, ref_pg, b, i))
                wins[(cell.choice["name"], cell.opponent)] = (cell.kind, _wins(ctx, mine), _wins(ctx, ref_pg))
        errors = cells.command_errors(_labels_acc(ctx, mine_batches, cache, True))
        arms[arm.name] = arm_summary(ctx, arm, arm_rows, wins, errors)
        rows += arm_rows
    src = ctx.calcfg["source"]
    return {"format": FORMAT, "side": ctx.spec.side, "of_record": ctx.of_record, "overrides": ctx.overrides,
            "simulator": l011.SIMULATOR + "; " + OBSERVED,
            "calibration_file": _rel(ctx.a.calibration), "calibration_sha256": ctx.cal_sha,
            "cells_file": src["cells"], "cells_sha256": src["cells_sha256"], "skills_gates": src["skills_gates"],
            "skills_gates_sha256": src["skills_gates_sha256"], "scripted_sha256": src["scripted_sha256"],
            "reference_file": ctx.gates.reference["file"], "reference_sha256": ctx.gates.reference["sha256"],
            "variant": ctx.variant, "device": ctx.device, "seed": ctx.seed, "ticks_cap": ctx.ticks,
            "hold_ticks": HOLD_TICKS, "games_per_cell": ctx.n, "chunk_cells": ctx.chunk,
            "opponents": sorted({c.opponent for c in ctx.cells if c.kind != INFO},
                                key=gated_opponents(ctx.gates, ctx.spec.side).index),
            "info_opponents": [o for o in ctx.cells_cfg["info_opponents"][ctx.spec.side]
                               if o in {c.opponent for c in ctx.cells}],
            "intervals": {"alpha": ctx.alpha, "interval": cells.NEWCOMBE, "correction": cells.BONFERRONI,
                          "m": {ctx.spec.side: ctx.m}, "z_cell": ctx.z_cell, "z_pooled": ctx.z_plain,
                          "note": "ci_plain at z_pooled = adjusted_z(alpha, 1); ci_adjusted at z_cell = "
                                  "adjusted_z(alpha, m), m the side's gated cells of the committed layout; pooled ci "
                                  "at z_pooled; b, c and n are stored, so any other alpha is recomputed without a replay"},
            "controls": controls, "labels": {"rule": LABEL_RULE, **labels},
            "batches": [b.name for b in first + second], "arms": arms, "cells": rows,
            "permuted": permuted_read(ctx), "complete": True}


def _rel(path: Path) -> str:
    p = Path(path).resolve()
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return p.name


def _f(v, digits: int = 4) -> str:
    return "-" if v is None else f"{v:.{digits}f}" if isinstance(v, float) else str(v)


def _ci(ci) -> str:
    return "-" if ci is None else f"[{ci[0]:+.4f}, {ci[1]:+.4f}]"


def results_md(res: dict) -> str:
    iv = res["intervals"]
    side, m = res["side"], iv["m"][res["side"]]
    lines = [f"# LS1.5 calibration read, {side} team ({'of record' if res['of_record'] else 'NOT of record: ' + json.dumps(res['overrides'])})",
             "",
             f"{res['simulator']}. Cells: {res['games_per_cell']} games each on T44's starts (seed {res['seed']}), hold "
             f"{res['hold_ticks']}, tick cap {res['ticks_cap']}, device {res['device']}; opponents {res['opponents']}, "
             f"info {res['info_opponents']}. Intervals: {iv['interval']}, {iv['correction']}, alpha {iv['alpha']}, "
             f"m = {m} gated cells, z_cell {iv['z_cell']:.4f}, z_pooled {iv['z_pooled']:.4f}.",
             "",
             "No pass or fail: the owner sets the LS1 limits from this read (R38). Differences are the arm's win share "
             "less the reference's (the scripts; T44 on the gated fixed cells).",
             "",
             f"Labels ({res['labels']['rule']}): zero-command skill(s) {res['labels']['zero_skills']}; active channels "
             + "; ".join(f"{s} {[i for i, a in enumerate(v) if a]}" for s, v in res["labels"]["active"].items()) + ".",
             "",
             "## Arms",
             "",
             "| Arm | Cells | Flips median | Flips max | max abs(b-c) | Pooled all [ci] | Pooled fixed | Pooled mixed "
             "| p < alpha | Adjusted ci excludes 0 | RMSE active max | Unused max abs | Zero-skill max abs |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for name, a in res["arms"].items():
        p, e = a["pooled"], a["error_summary"]
        pool = {g: "-" if p[g] is None else f"{p[g]['diff']:+.4f} {_ci(p[g]['ci'])}" for g in ("all", "fixed", "mixed")}
        lines.append(f"| {name} | {a['cells']} | {_f(a['flips_median'], 1)} | {_f(a['flips_max'])} | "
                     f"{_f(a['max_abs_b_minus_c'])} | {pool['all']} | {pool['fixed']} | {pool['mixed']} | "
                     f"{a['p_below_alpha']} | {a['adjusted_excludes_zero']} | {_f(e['rmse_active_max'])} | "
                     f"{_f(e['unused_max_abs'])} | {_f(e['zero_skill_max_abs'])} |")
    perm = res["permuted"]
    lines += ["", "## The permuted scripts (from T44, no play)", "",
              f"Permutation {perm['permutation']} (code k flies code perm[k]); {len(perm['cells'])} gated fixed cells; "
              f"{perm['adjusted_excludes_zero']} with the adjusted interval excluding 0 "
              f"({perm['plain_excludes_zero']} at plain alpha).", ""]
    for title, key in (("By flips", lambda r: -r["flips"]), ("By |diff|", lambda r: -abs(r["diff"] or 0.0))):
        lines += [f"### {title}", "", "| Code | Flies | Opponent | b | c | Flips | Diff | ci_plain | ci_adjusted |",
                  "|---|---|---|---|---|---|---|---|---|"]
        lines += [f"| {r['code']} | {r['flies']} | {r['opponent']} | {r['b']} | {r['c']} | {r['flips']} | "
                  f"{_f(r['diff'])} | {_ci(r['ci_plain'])} | {_ci(r['ci_adjusted'])} |"
                  for r in sorted(perm["cells"], key=key)]
        lines.append("")
    lines += ["Per cell (b, c, flips, both intervals, sign-test p, end steps) and the command-error table per skill: "
              "results.json.", ""]
    return "\n".join(lines)


# ================================================================================================ the command line
def parse(argv: list[str] | None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--calibration", type=Path, required=True)
    ap.add_argument("--side", choices=cells.SIDES, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--expect-sha256", required=True)
    ap.add_argument("--chunk", type=int, default=None, help="cells per game batch (default [run] chunk_cells)")
    ap.add_argument("--cap-h", type=float, default=None, help="effective-hour cap (default: none, a CPU job)")
    ap.add_argument("--games", type=int, default=None, help="test-only: the first N starts (of_record false)")
    ap.add_argument("--opponents", nargs="+", default=None, help="test-only: these opponents (of_record false)")
    ap.add_argument("--arms", nargs="*", default=None, help="test-only: these ladder arms (of_record false)")
    ap.add_argument("--mixed", type=int, default=None, help="test-only: the first N combinations (of_record false)")
    return ap.parse_args(argv)


def prepare(a: argparse.Namespace) -> tuple[Ctx | None, str | None]:
    """Every check before anything plays: (the run's context, None) or (None, why it is refused)."""
    if not a.calibration.is_file():
        return None, f"the calibration file {a.calibration} is missing"
    sha = exploit.sha256_file(a.calibration)
    if sha != a.expect_sha256:
        return None, f"the calibration file {a.calibration} has sha256 {sha}, --expect-sha256 says {a.expect_sha256}"
    try:
        calcfg = load_calibration(a.calibration)
    except (OSError, ValueError) as err:
        return None, f"calibration file: {err}"
    src = calcfg["source"]
    for what, path, want in (("skills gate file", ROOT / src["skills_gates"], src["skills_gates_sha256"]),
                             ("cells file", ROOT / src["cells"], src["cells_sha256"]),
                             ("scripted.py", SCRIPTED, src["scripted_sha256"])):
        problem = scoring.sha_problem(path, want, what)
        if problem:
            return None, problem
    try:
        gates = exploit.load_gates(ROOT / src["skills_gates"])
        cells_cfg = load_cells(ROOT / src["cells"])
        spec = cells.cell_spec(gates, a.side)
    except (OSError, ValueError) as err:
        return None, str(err)
    problem = held.input_problems(gates) or check_cells(spec, cells_cfg, gates)
    if problem:
        return None, problem
    if len(gates.variants) != 1:
        return None, f"the skills gate file has variants {sorted(gates.variants)}: the calibration reads one"
    variant = next(iter(gates.variants))
    ref = exploit.load_reference(ROOT / gates.reference["file"])
    full_n = int(cells_cfg["read"]["games_per_cell"])
    n = full_n if a.games is None else int(a.games)
    if not 1 <= n <= ref.games:
        return None, f"games per cell {n} outside 1..{ref.games} (T44's starts)"
    chunk = int(calcfg["run"]["chunk_cells"]) if a.chunk is None else int(a.chunk)
    if chunk < 1:
        return None, f"--chunk must be at least 1, got {chunk}"
    if a.cap_h is not None and not (math.isfinite(a.cap_h) and a.cap_h > 0):
        return None, f"--cap-h must be a finite number above 0, got {a.cap_h}"
    every = side_cells(spec, cells_cfg, gates)
    among = list(every)
    if a.opponents is not None:
        known = list(dict.fromkeys(c.opponent for c in every))
        unknown = [o for o in a.opponents if o not in known]
        if unknown or len(set(a.opponents)) != len(a.opponents):
            return None, f"--opponents {a.opponents}: the {a.side} team's opponents are {known}"
        among = [c for c in among if c.opponent in a.opponents]
    if a.mixed is not None:
        if not 0 <= a.mixed <= len(cells_cfg["mixed"][a.side]):
            return None, f"--mixed {a.mixed} outside 0..{len(cells_cfg['mixed'][a.side])}"
        names = {c["name"] for c in cells.mixed_choices(spec, [tuple(x) for x in cells_cfg["mixed"][a.side][:a.mixed]])}
        fixed_names = {c["name"] for c in cells.fixed_choices(spec)}
        among = [c for c in among if c.choice["name"] in fixed_names | names]
    arms = arms_of(calcfg, a.side)
    if a.arms is not None:
        ladder = [x.name for x in arms if x.phase == 2]
        unknown = [x for x in a.arms if x not in ladder]
        if unknown or len(set(a.arms)) != len(a.arms):
            return None, f"--arms {a.arms}: the {a.side} team's ladder arms are {ladder}"
        arms = [x for x in arms if x.phase == 1 or x.name in a.arms]
    overrides = {k: v for k, v in (("games", a.games), ("opponents", a.opponents), ("arms", a.arms),
                                   ("mixed", a.mixed)) if v is not None}
    alpha = float(calcfg["intervals"]["alpha"])
    m = gated_m(spec, cells_cfg, gates)
    ctx = Ctx(a=a, calcfg=calcfg, cal_sha=sha, cells_cfg=cells_cfg, gates=gates, spec=spec, variant=variant, ref=ref,
              cfg=exploit.variant_cfg(gates, variant), n=n, chunk=chunk, device=str(calcfg["run"]["device"]),
              seed=int(ref.meta["seed"]), ticks=int(gates.run["ticks_cap"]), cells=among, arms=arms, m=m, alpha=alpha,
              z_plain=cells.adjusted_z(alpha, 1), z_cell=cells.adjusted_z(alpha, m), of_record=not overrides,
              overrides=overrides, out=a.out)
    return ctx, None


def layout_of(ctx: Ctx) -> dict:
    return {"format": FORMAT, "side": ctx.spec.side, "calibration_sha256": ctx.cal_sha, "games_per_cell": ctx.n,
            "chunk_cells": ctx.chunk, "device": ctx.device, "cells": [c.index for c in ctx.cells],
            "arms": [x.name for x in ctx.arms], "of_record": ctx.of_record, "overrides": ctx.overrides}


def main(argv: list[str] | None = None) -> int:
    a = parse(list(sys.argv[1:] if argv is None else argv))
    res = a.out / RESULTS
    if res.is_file() and json.loads(res.read_text()).get("complete") is True:
        return refuse(f"this folder is finished ({res}): a new run needs a new folder")
    controls_file = a.out / CONTROLS_FILE
    if controls_file.is_file():
        code = scoring.ending(json.loads(controls_file.read_text()))
        if code is not None:
            print(f"[ls1.5] a control is not PASS in this folder ({controls_file}): read it; a new run needs a new "
                  f"folder (exit {code})", file=sys.stderr, flush=True)
            return code
    ctx, why = prepare(a)
    if why:
        return refuse(why)
    layout = layout_of(ctx)
    pinned = a.out / LAYOUT_FILE
    if pinned.is_file() and json.loads(pinned.read_text()) != json.loads(json.dumps(layout)):
        return refuse(f"{pinned} holds another layout (calibration, side, games, chunk, cells or arms): a changed "
                      f"layout needs a new folder")
    a.out.mkdir(parents=True, exist_ok=True)
    try:
        with RunGuard(a.out, cap_s=a.cap_h * HOUR_S if a.cap_h is not None else math.inf) as guard:
            if not pinned.is_file():
                l011.write_json(pinned, layout)
            return run(ctx, guard)
    except RunBusyError as err:
        return refuse(str(err))
    except NonFiniteError as err:
        say(f"NON-FINITE: {err} (exit {EXIT_NONFINITE})")
        return EXIT_NONFINITE


if __name__ == "__main__":
    sys.exit(main())
