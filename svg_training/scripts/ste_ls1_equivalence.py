#!/usr/bin/env python
"""STE route 3, stage LS1, job LS1.2: the equivalence read of a skill network against the scripts it copies (plan
ste_learning/drafts/LS1_TASK_PLAN.md, merge M2; the design check of M2). This file holds the read's importable part
(task LS1-M2-T5): its players and its verdict functions; and the read itself (task LS1-M2-T6), at the end of the file:

    ste_ls1_equivalence.py --gates configs/ste_ls1/distil_gates.toml --side guard|strike
                           --skill-net runs/<date>_ste_ls1_<side>/skill_net_<side>.pt --run-dir runs/<date>_ste_ls1_read_<side>
                           --cap-h <H> [--expect-gates-sha256 <hex>] [--smoke] [--allow-code-change] [--chunk K]
                           [--games N] [--opponents NAME ...] [--mixed N]          (the last three test-only)

Launch: ``scripts/ste_job.py launch --task LS1.2 --gpu-h 0 ... -- <this command>`` (a CPU job: job.json ``gpu_h`` must
be 0; ``[read] device`` must not be cuda). Under ``--smoke`` (job LS1.0's read, not of record) the cells play ``[smoke]
read_games`` starts each (``distil.SMOKE_RULE``); otherwise cells.toml ``[read] games_per_cell`` (one ruler, B-6). Every
batch plays hold 1 on T44's starts: seed ``ref.meta["seed"]`` and ``[run] ticks_cap`` of the pinned skills gate file,
the cap checked every ``[run] cap_check_every_ticks`` ticks (CA-3).

The network (refused, exit 2, before anything is written; design check of M2): a ``fit_report.json`` must lie beside the
file, complete, naming the file's sha256 (``net_sha256``) and this gate file's (``gates_sha256``), and outside --smoke of
record; the network's provenance must name this gate file's sha256 (and outside --smoke be of record); that sha256 is
the one ``skill_net.net_problems`` (team, skills, team size, game constants, the scripts' and the game file's sha256)
and ``load_skill_net`` check. Also refused: a pin off (the skills gate file, cells.toml, opponents/scripted.py, the
game file, T44), the owner's FILL_ keys outside --smoke (R38), a GPU job, a changed gate file, network, side or option
set in a started folder, another layout.

The batches (``plan_batches``), in this order, each a game batch of at most ``chunk_cells`` cells of one opponent and
one kind (fixed, mixed, info), so every arm is played at its scripted arm's batch shape (plan constraint 8):
C1 the scripts through the dispatch on the fixed cells (each equals T44 game for game, ``exploit.replay_ok``; the
scripted arm of every fixed cell); C1m the scripts' ``Composite`` on the mixed cells (plumbing; the scripted arm of
every mixed cell); C2 the scripts as a network (``cells.ScriptOracle`` through ``NetTwoLevelDispatch``) on C1's and
C1m's cells (game for game equal to them, its command error within ``[data] label_check_atol``); C3 the permuted
scripts from T44 (no play); C4 the unfitted network and C5 the permuted network on the gated fixed cells (OP-20); C6
(bias, turn, each switch player of the side) and C7 (noise on each skill's active channels, from C2's labels) on
``[read] near_miss_cells``, played only outside --smoke; then R1, the network on the gated cells
(fixed and mixed) with its command error against the scripts' labels, and R2 (INFO, the Strike team against
cells.toml ``[info_opponents]``: the scripts, then the network, paired with each other, not gated). The scripted arms
hold the gated and the near-miss cells (under the test-only options the near-miss cells of the read's opponents are
played even when ``--mixed`` leaves their combination out).

Controls first (OP-19): every batch's own controls (paired starts, tags one for one, no non-finite action, every game
finished, and C1's and C2's checks) and the named controls (``control_names``: C1, C1m, C2, C3 to C5 at least the
owner's count of cells miss, C6 the near miss fails a limit, C7 it meets every limit) are written to ``controls.json``
as they are settled, all of them before the first R1 batch. A control not PASS: ``results.json`` with the verdict
INCONCLUSIVE and no result batch (exit 6, terminal: the same command on the folder exits 6 again); a non-finite
action: exit 5, no result. A smoke checks plumbing, never a verdict (F1; lead, 26 Nov 2026): under --smoke, the
owner's keys filled or FILL_, C4 and C5 are played but not judged, C6 and C7 are not played, and C3 to C7, the failures
and the verdict are NOT_RUN (``Ctx.plumbing_only``); the smoke ends exit 0 with NOT_RUN when every plumbing control
(C1, C1m, C2 and each batch's own) passes. Outside --smoke a FILL_ key is refused, so every step is judged.

Files in ``--run-dir``: ``gates.toml`` and ``gates.sha256`` (pinned at the first launch), ``run.json`` (side, smoke,
sizes, options, the network), ``code.json``; ``layout.json`` (``batches``, each appended before it is played, its
``seconds`` after); ``games/<batch>.npz`` (``scoring.save_batch``'s arrays plus ``pos_at`` [G, M, T, 3], ``alive_at`` [G,
M, T], on an arm batch ``pair_class`` [G], and the batch's command-error accumulators per cell and skill, ``err_*``:
what ``results.json`` needs, so a resumed read rebuilds the uninterrupted read's file from the batch files only);
``controls.json``; ``results.json`` (exactly ``RESULT_KEYS``, ``complete`` last; the per-cell intervals at ``z_cell =
adjusted_z(alpha, m)``, m the side's gated cells of the committed layout, the pooled rows at ``z_pooled``) and
``results.md``. The last line on stdout is the verdict word (DISTILLED, NOT DISTILLED, INCONCLUSIVE, or NOT_RUN for a
smoke).

The run contract (``ste/run_contract.py``): the same command resumes at the first batch not done (done batches are
not replayed); SIGINT or SIGTERM stops before the next tick (exit 4, the partial batch dropped); --cap-h caps effective
hours (exit 3). Test-only options (each writes ``of_record: false``): ``--games N``, ``--opponents`` (at least one gated
one), ``--mixed N``; m stays the committed layout's. Exit codes: 0 DISTILLED, NOT DISTILLED or a smoke's NOT_RUN (and
a done folder); 2 refused; 3 cap; 4 stopped; 5 a non-finite value; 6 a control failed (INCONCLUSIVE).

The players. Every read plays hold 1 on T44's starts (C6), one object per cell under a prefixed name
(``cells.PREFIXES``), each recording, for each slot's first game only, its drones' positions and alive flags at the
ticks ``round(t / TICK_S)`` of ``path_times_s`` (``[read] path_times_s``):

* :class:`RecordingSkillTeam`: a constant-heads ``exploit.SkillTeam`` (``cells.ConstHeads`` per choice, as
  ``cells.fixed_team`` builds it) over any two-level dispatch; with a ``labeller`` (the scripts' dispatch) it also
  records the flown code's command error against the scripts' label on the same observation, per code and channel
  (sums of squares, max |error|, rows, the label's max |.|) and per code by the number of live drones (batched);
* :class:`RecordingPlayer`: the same position record around any other player (a ``cells.Composite``, a changed
  script of ``opponents/perturbed.py``), and for the near-miss arms the per-slot recorders of the changed players;
* :class:`PermutedNet`: code k flies code ``perm[k]`` (C5; ``cells.toml [permutation]``); :func:`unfitted_net`: the
  distillation's fit start (C4: ``distil.initial_net`` from ``[fit] seed`` under ``fork_rng``, no new seed).

:func:`arms` builds an arm's players over a list of cells (``cells.Cell``): ``scripts`` (C1, C1m: fixed choices through
the scripts' dispatch, mixed ones a ``Composite`` of the scripts), ``oracle`` (C2: ``cells.ScriptOracle`` through
``NetTwoLevelDispatch``), ``unfitted`` (C4), ``permuted`` (C5), ``net`` (R1) and the near-miss arms: C6 (systematic,
one per kind and one per switch player of the side) ``bias`` (``CommandPerturbation(kind="bias")`` on xy),
``rotate_deg`` (``kind="turn"``) and each ``near_miss.switch`` key of the side (its own moved player at its own value,
``perturbed.SWITCHES``, only on the near-miss cells where its code flies); C7 (random) ``noise``
(``kind="noise"`` on each skill's active channels, the calibration's ``noise_active`` rule: none for the zero-command
skill, which flies the identity; drawn from ``[read] noise_seed`` + the cell's index in the side's full cell list x the
team size + the slot).

The verdict functions: :func:`interval_step` (per cell b, c, flips, the difference with its interval at
``z_cell = adjusted_z(alpha, m)``, m the side's gated cells of the committed layout, the end-step differences; the
pooled rows at ``z_pooled = adjusted_z(alpha, 1)``, C7 of the plan); :func:`limit_failures` (one string per miss,
naming the ``[limits]`` key); :func:`gross_control` (C3 to C5: at least the owner's count of cells miss),
:func:`near_miss_control` (C6 fails the limits, C7 meets them); :func:`verdict` (controls first);
:func:`path_distance`; :func:`permuted_from_t44` (C3 from T44 alone, no play). A ``FILL_`` value never reaches a
comparison: each function that reads a limit or a control size raises ValueError naming it (R38).

Tier 1; observed in the training simulator. Shapes: N games, M drones of the side, K codes, T marks, G games of a
batch. Loops run over cells, marks, codes and the M drones of a team only, never over games."""
from __future__ import annotations

import argparse
import json
import math
import os
import signal
import sys
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
sys.path.insert(0, str(ROOT / "scripts"))

import numpy as np  # noqa: E402
import torch  # noqa: E402
from torch import Tensor, nn  # noqa: E402

import ste_sweep_l011 as l011  # noqa: E402  (code pinning: the L0.11 driver's own helper)
from svg_training.core.game_config import TICK_S  # noqa: E402
from svg_training.core.observations import ObsView  # noqa: E402
from svg_training.core.rewards import GUARD_WIN, RUNNING, STRIKE_WIN  # noqa: E402
from svg_training.opponents import perturbed  # noqa: E402
from svg_training.opponents.scripted import make_strategy  # noqa: E402
from svg_training.ste import atomic, cells, distil, exploit, scoring, skill_net, skills, sweep  # noqa: E402
from svg_training.ste.run_contract import (EXIT_CONTROL_FAILED, EXIT_DONE, EXIT_FOR_STOP, EXIT_NONFINITE,  # noqa: E402
                                           EXIT_REFUSED, STOP_INTERRUPTED, NonFiniteError, RunBusyError, RunGuard)

PASS, FAIL, NONFINITE = scoring.PASS, scoring.FAIL, scoring.NONFINITE
NOT_RUN = "NOT_RUN"                              # a control or a verdict not run (a smoke, F1)
STATUSES = (PASS, FAIL, NONFINITE, NOT_RUN)
DISTILLED, NOT_DISTILLED, INCONCLUSIVE = "DISTILLED", "NOT DISTILLED", "INCONCLUSIVE"
HOLD_TICKS = 1                                   # C6: every read plays hold 1
_V = ObsView()
COMMAND_DIM = perturbed.COMMAND_DIM
ALL_CHANNELS = tuple(range(COMMAND_DIM))
PATH_PCT = 90                                    # path_distance's upper percentile over games
# the arms (kinds), each with its name prefix (C6)
SCRIPTS, ORACLE, UNFITTED, PERMUTED, NET = "scripts", "oracle", "unfitted", "permuted", "net"
BIAS, ROTATE, NOISE = "bias", "rotate_deg", "noise"         # the [controls] near_miss keys of C6 and C7
SWITCHES = perturbed.SWITCHES                                # one C6 arm per switch key of the side
NET_KINDS = (ORACLE, UNFITTED, PERMUTED, NET)
RANDOM_KINDS = [NOISE]                                       # C7
NEAR_MISS_KEYS = {BIAS: "near_miss.bias", ROTATE: "near_miss.rotate_deg", NOISE: "near_miss.noise",
                  **{k: f"near_miss.switch.{k}" for k in SWITCHES}}
PREFIX = {SCRIPTS: cells.SCR_PREFIX, ORACLE: cells.ORC_PREFIX, UNFITTED: cells.UNF_PREFIX, PERMUTED: cells.PERM_PREFIX,
          NET: cells.NET_PREFIX}
CHANNEL_NAMES = ("vx", "vy", "vz", "yaw rate")


def systematic_kinds(side: str) -> list[str]:
    """C6's arms of ``side``: bias, turn, then one per switch player of the side (``perturbed.SWITCHES`` order)."""
    cells.other(side)
    return [BIAS, ROTATE] + [k for k, v in SWITCHES.items() if v[0] == side]


def read_kinds(side: str) -> list[str]:
    """Every arm of the read of ``side``: the net-flown and scripted arms, then C6's and C7's."""
    return [SCRIPTS, ORACLE, UNFITTED, PERMUTED, NET] + systematic_kinds(side) + RANDOM_KINDS


# ================================================================================================ the recorders
class _PathRecord:
    """Positions ``obs[..., 0:3]`` (zone-relative in xy, world z) and alive flags of the side's drones at the mark ticks
    ``round(t / TICK_S)``, for each slot's first game only (``HeldPlayer._first``'s rule: a game that ended is not
    recorded after its end). One scalar tick: every slot's first game starts at tick 0 together
    (``core/play.play_match`` resets every game at once), and tick 0 is the reset observation (the starts)."""

    def _init_path(self, path_times_s) -> None:
        times = [float(t) for t in path_times_s]
        if not times or any(not math.isfinite(t) or t < 0 for t in times):
            raise ValueError(f"path_times_s must be finite times >= 0 s, got {list(path_times_s)!r}")
        self.path_times_s = tuple(times)
        self.mark_ticks = tuple(int(round(t / TICK_S)) for t in times)
        self._tick = 0
        self._first: Tensor | None = None
        self._pos: Tensor | None = None
        self._alive: Tensor | None = None

    def _path_reset(self, games: Tensor) -> None:
        """games [N] bool: the games that end now (all at the start); their slots' later games are not recorded."""
        if self._first is None:
            self._first = torch.ones_like(games, dtype=torch.bool)
        else:
            self._first = self._first & ~games

    def _first_live(self, obs: Tensor) -> Tensor:
        """[N, M] bool: live drones of games still in their slot's first game."""
        live = obs[..., _V.alive] > skills.ALIVE_FLAG_MIN
        return live if self._first is None else live & self._first[:, None]

    def _path_record(self, obs: Tensor) -> None:
        n, m = obs.shape[:2]
        if self._pos is None:
            self._pos = obs.new_zeros(n, m, len(self.mark_ticks), 3)
            self._alive = torch.zeros(n, m, len(self.mark_ticks), dtype=torch.bool, device=obs.device)
        for j, tick in enumerate(self.mark_ticks):
            if tick == self._tick:
                live = self._first_live(obs)
                self._pos[:, :, j] = obs[..., _V.own_pos] * live[..., None]
                self._alive[:, :, j] = live
        self._tick += 1

    def paths(self) -> tuple[np.ndarray, np.ndarray] | None:
        """(pos_at [N, M, T, 3] float32, alive_at [N, M, T] bool) on the host; None before the first tick."""
        if self._pos is None:
            return None
        return self._pos.detach().cpu().numpy().astype(np.float32), self._alive.cpu().numpy()


class RecordingSkillTeam(exploit.SkillTeam, _PathRecord):
    """A ``SkillTeam`` (``holds_choice``) that records its paths and, with a ``labeller`` (a two-level dispatch of the
    scripts), the flown code's command error against the scripts' label on the same observation: per code k and
    channel the sum of squares (float64), the max |error|, the label's max |.|, the rows (live drones of first games),
    and the same sums and rows by the number of live drones of the side (1..M). The command it returns is the
    dispatch's, untouched. ``errors()`` reads the accumulators once (host lists)."""

    def __init__(self, team: str, nets: list, scalers: list, dispatch: skills.SkillDispatch, name: str, *,
                 path_times_s, labeller: skills.SkillDispatch | None = None):
        super().__init__(team, nets, scalers, dispatch, name=name)
        if labeller is not None and (labeller.team != team or list(labeller.names) != list(dispatch.names)):
            raise ValueError(f"the labeller holds the {labeller.team} team's {labeller.names}, the dispatch the {team} "
                             f"team's {dispatch.names}")
        self.labeller = labeller
        self._init_path(path_times_s)
        self._acc: dict | None = None

    def reset(self, games: Tensor) -> None:
        super().reset(games)
        if self.labeller is not None:
            self.labeller.reset(games)
        self._path_reset(games)

    def command(self, obs: Tensor, choice: Tensor) -> Tensor:
        """obs [N, M, D], choice [N, M] (resolved: the flown code) -> the dispatch's command [N, M, 4]."""
        flown = super().command(obs, choice)
        if self.labeller is not None:
            self._record_error(obs, choice.to(torch.long), flown)
        self._path_record(obs)
        return flown

    def _record_error(self, obs: Tensor, choice: Tensor, flown: Tensor) -> None:
        n, m = obs.shape[:2]
        k = self.dispatch.k
        label = self.labeller.act(obs, choice).to(flown.dtype)
        rows = self._first_live(obs)                                                  # [N, M]
        w = rows[..., None].to(flown.dtype)
        d = (flown - label) * w
        if self._acc is None:
            f64 = dict(dtype=torch.float64, device=obs.device)
            self._acc = {"sum_sq": torch.zeros(k, COMMAND_DIM, **f64), "max_abs": flown.new_zeros(k, COMMAND_DIM),
                         "label_max_abs": flown.new_zeros(k, COMMAND_DIM),
                         "count": torch.zeros(k, dtype=torch.long, device=obs.device),
                         "sum_sq_by_n_live": torch.zeros(k * m, COMMAND_DIM, **f64),
                         "count_by_n_live": torch.zeros(k * m, dtype=torch.long, device=obs.device)}
        a = self._acc
        code = choice.reshape(-1)
        sq = d.double().pow(2).reshape(-1, COMMAND_DIM)
        one = rows.reshape(-1).long()
        n_live = (obs[..., _V.alive] > skills.ALIVE_FLAG_MIN).sum(1).clamp(min=1)    # [N]
        by_live = code * m + (n_live - 1)[:, None].expand(n, m).reshape(-1)
        idx = code[:, None].expand(-1, COMMAND_DIM)
        a["sum_sq"].index_add_(0, code, sq)
        a["count"].index_add_(0, code, one)
        a["max_abs"].scatter_reduce_(0, idx, d.abs().reshape(-1, COMMAND_DIM), "amax")
        a["label_max_abs"].scatter_reduce_(0, idx, (label * w).abs().reshape(-1, COMMAND_DIM), "amax")
        a["sum_sq_by_n_live"].index_add_(0, by_live, sq)
        a["count_by_n_live"].index_add_(0, by_live, one)

    def errors(self) -> dict | None:
        """{code name: {"sum_sq" [4], "max_abs" [4], "count", "label_max_abs" [4], "sum_sq_by_n_live" [M][4],
        "count_by_n_live" [M]}} in the dispatch's code order (host lists); None without a labeller or before a tick."""
        if self._acc is None:
            return None
        a = {key: v.cpu() for key, v in self._acc.items()}
        k = self.dispatch.k
        m = a["count_by_n_live"].shape[0] // k
        nl_sq, nl_n = a["sum_sq_by_n_live"].reshape(k, m, COMMAND_DIM), a["count_by_n_live"].reshape(k, m)
        return {name: {"sum_sq": a["sum_sq"][i].tolist(), "max_abs": a["max_abs"][i].double().tolist(),
                       "count": int(a["count"][i]), "label_max_abs": a["label_max_abs"][i].double().tolist(),
                       "sum_sq_by_n_live": nl_sq[i].tolist(), "count_by_n_live": nl_n[i].tolist()}
                for i, name in enumerate(self.dispatch.names)}


def recording_team(spec: cells.CellSpec, choice: dict, dispatch: skills.TwoLevelDispatch, name: str, *,
                   path_times_s, labeller: skills.TwoLevelDispatch | None = None) -> RecordingSkillTeam:
    """``cells.fixed_team``'s two lines (a constant network per drone slot, identity scalers) building a
    :class:`RecordingSkillTeam` instead (``fixed_team`` always builds ``exploit.SkillTeam``)."""
    nets = [cells.ConstHeads(t, d, dispatch.widths) for t, d in choice["heads"]]
    return RecordingSkillTeam(spec.side, nets, [lambda o, train=False: o] * len(nets), dispatch, name,
                              path_times_s=path_times_s, labeller=labeller)


class RecordingPlayer(_PathRecord):
    """Any player of the side (``team``, ``reset``, ``act``) with the path record (no ``holds_choice``: held as a
    command, hold 1). ``flies`` (the code of each drone slot) and ``recorders`` [(slot, changed player)] carry a
    near-miss arm's per-slot command-error accumulators (``perturbed`` ``errors()``) to
    :func:`player_accumulators`."""

    def __init__(self, inner, name: str, path_times_s, flies: list[str] | None = None, recorders=()):
        self.inner, self.name, self.team = inner, name, inner.team
        self.flies, self.recorders = list(flies or []), list(recorders)
        self._init_path(path_times_s)

    def reset(self, games: Tensor) -> None:
        self.inner.reset(games)
        self._path_reset(games)

    def act(self, obs: Tensor) -> Tensor:
        """obs [N, M, OBS_DIM] -> the inner player's command [N, M, 4]."""
        out = self.inner.act(obs)
        self._path_record(obs)
        return out


# ================================================================================================ the stand-in networks
class PermutedNet(nn.Module):
    """C5 (and C3's permutation, ``cells.toml [permutation]``): ``forward(obs, slot, z) = net(obs, slot, perm[z])``, code
    k flies code perm[k]; C2's attributes are the network's (``skills`` stays the unpermuted list, the dispatch checks it
    against ``[players]``), the alive rule is the network's own (applied once)."""

    def __init__(self, net, perm):
        super().__init__()
        perm = [int(p) for p in perm]
        if sorted(perm) != list(range(net.k)):
            raise ValueError(f"perm {perm} is not a permutation of the network's {net.k} codes")
        self.net = net
        self.register_buffer("perm", torch.tensor(perm, dtype=torch.long))
        self.team, self.skills, self.k, self.team_size = net.team, tuple(net.skills), net.k, net.team_size
        for attr in ("slot_width", "hidden", "zeroed_inputs"):
            if hasattr(net, attr):
                setattr(self, attr, getattr(net, attr))

    def forward(self, obs: Tensor, slot: Tensor, z: Tensor, clip: bool = True) -> Tensor:
        return self.net(obs, slot, self.perm.to(z.device)[z], clip=clip)


def unfitted_net(spec: cells.CellSpec, g: distil.DistilGates):
    """C4: a fresh skill network of the side with the gate file's ``[net]`` sizes, initialised as every fit starts
    (``distil.initial_net`` from ``[fit] seed`` under ``torch.random.fork_rng``): no new seed (design check of M2)."""
    return distil.initial_net(spec, exploit.variant_cfg(g.skills_gates, distil.VARIANT), g.net, g.fit["seed"])


# ================================================================================================ the arms
def near_miss_value(g: distil.DistilGates, kind: str) -> float:
    """The owner's ``[controls] near_miss`` value of ``kind`` (in its player's unit); ValueError while it is FILL_."""
    if kind not in NEAR_MISS_KEYS:
        raise ValueError(f"{kind!r} is not a near-miss arm; they are {list(NEAR_MISS_KEYS)}")
    node = g.controls
    for part in NEAR_MISS_KEYS[kind].split("."):
        node = node[part]
    if distil.is_fill(node):
        raise ValueError(f"controls.{NEAR_MISS_KEYS[kind]} is not filled yet ({node!r}): the owner sets it (R38)")
    return float(node)


def near_miss_cells(g: distil.DistilGates, side: str) -> list[cells.Cell]:
    """The ``[read] near_miss_cells`` of ``side`` as cells of the side's full list (``cells.side_cells``), in the file's
    order: a one-code entry is that code's fixed cell, a longer one its cells.toml combination."""
    spec = g.specs[side]
    every = [c for c in cells.side_cells(spec, g.cells, g.skills_gates) if c.kind != cells.INFO]
    out = []
    for e in g.read["near_miss_cells"][side]:
        flies = list(e["codes"]) * spec.drones if len(e["codes"]) == 1 else list(e["codes"])
        hit = [c for c in every if c.choice["flies"] == flies and c.opponent == e["opponent"]]
        if len(hit) != 1:
            raise ValueError(f"[read] near_miss_cells.{side} {e!r} is not one gated cell of the side")
        out.append(hit[0])
    return out


def arm_cells(kind: str, among: list[cells.Cell], side: str) -> list[cells.Cell]:
    """The cells of ``among`` that arm ``kind`` plays: a switch arm only those where its code flies, every other arm
    all of them."""
    if kind in SWITCHES:
        team, code, _, _ = SWITCHES[kind]
        if team != side:
            raise ValueError(f"the switch arm {kind!r} is the {team} team's, not the {side} team's")
        return [c for c in among if code in c.choice["flies"]]
    if kind not in (SCRIPTS,) + NET_KINDS + (BIAS, ROTATE, NOISE):
        raise ValueError(f"unknown arm {kind!r}")
    return list(among)


def _uniform(cell: cells.Cell) -> bool:
    return len(set(cell.choice["flies"])) == 1


def player_name(kind: str, cell: cells.Cell) -> str:
    """C6: one name per (arm, choice, opponent), prefixed so it never shadows a script; the scripted mixed arm (a
    ``Composite``) carries the oracle prefix."""
    if kind in PREFIX:
        prefix = cells.ORC_PREFIX if kind == SCRIPTS and not _uniform(cell) else PREFIX[kind]
    else:
        prefix = cells.CAL_PREFIX
    return f"{prefix}{kind}:{cell.choice['name']}@{cell.opponent}"


def arms(side: str, kind: str, *, g: distil.DistilGates, among: list[cells.Cell], cfg, n: int, device, seed: int,
         net=None, net_sha256: str | None = None, active: dict | None = None, path_times_s=None) -> dict:
    """The players of arm ``kind`` on ``arm_cells(kind, among, side)``: {name: player} in cell order, one object per
    cell (module docstring). ``seed``: the read's seed; scripts are seeded as ``exploit.play_cells`` seeds a named
    script (seed + the team offset). ``net``: the network of ``permuted`` and ``net`` (required), of ``oracle`` and
    ``unfitted`` (default: ``ScriptOracle``, :func:`unfitted_net`). ``active`` {skill: [4] bool} (the scripts' active
    channels, ``cells.active_rule``): required by ``noise``. ``path_times_s``: default ``[read] path_times_s``.
    The near-miss values come from ``g`` (ValueError while FILL_)."""
    spec = g.specs[side]
    times = g.read["path_times_s"] if path_times_s is None else path_times_s
    s = seed + (exploit.GUARD_SEED_OFFSET if side == cells.SIDES[0] else exploit.STRIKE_SEED_OFFSET)
    lists = (list(spec.players), list(spec.team_strategies), list(spec.drone_skills))
    mine = arm_cells(kind, among, side)

    def scripts_dispatch():
        return skills.TwoLevelDispatch(side, *lists, cfg, n, device, s)

    out = {}
    if kind == SCRIPTS:
        for cell in mine:
            name = player_name(kind, cell)
            if _uniform(cell):
                out[name] = recording_team(spec, cell.choice, scripts_dispatch(), name, path_times_s=times)
            else:
                comp = cells.Composite(side, list(cell.choice["flies"]), cfg, n, device, s, name=name)
                out[name] = RecordingPlayer(comp, name, times, cell.choice["flies"])
        return out
    if kind in NET_KINDS:
        if net is None and kind in (PERMUTED, NET):
            raise ValueError(f"the {kind} arm needs the network")
        if kind == ORACLE and net is None:
            net = cells.ScriptOracle(cfg, side, list(spec.players), spec.drones)
        elif kind == UNFITTED and net is None:
            net = unfitted_net(spec, g)
        elif kind == PERMUTED:
            net = PermutedNet(net, g.cells["permutation"][side])
        for cell in mine:
            name = player_name(kind, cell)
            dispatch = skills.NetTwoLevelDispatch(side, *lists, cfg, n, device, s, net, net_sha256)
            out[name] = recording_team(spec, cell.choice, dispatch, name, path_times_s=times,
                                       labeller=scripts_dispatch() if kind in (ORACLE, NET) else None)
        return out
    value = near_miss_value(g, kind)
    if kind == NOISE and active is None:
        raise ValueError("the noise arm needs the scripts' active channels per skill (active)")
    noise_seed = int(g.read["noise_seed"])

    def member(cell: cells.Cell, skill: str, slot: int, name: str | None):
        script = make_strategy(skill, side, cfg, n, device, s)
        s_seed = noise_seed + cell.index * spec.drones + slot
        if kind == BIAS:
            return perturbed.CommandPerturbation(script, "bias", value, s_seed, perturbed.XY, name=name)
        if kind == ROTATE:
            return perturbed.CommandPerturbation(script, "turn", value, s_seed, perturbed.XY, name=name)
        if kind == NOISE:
            ch = tuple(i for i, a in enumerate(active[skill]) if a)
            if not ch:                       # the zero-command skill: the identity, still recorded
                return perturbed.CommandPerturbation(script, "scale", 1.0, s_seed, ALL_CHANNELS, name=name)
            return perturbed.CommandPerturbation(script, "noise", value, s_seed, ch, name=name)
        _, code, moved, keyword = SWITCHES[kind]
        if skill != code:
            return skill                     # an unmoved slot of a mixed cell flies its script
        return perturbed.SwitchRecorder(moved(side, cfg, n, device, s, **{keyword: value}), script, name=name)

    for cell in mine:
        name, flies = player_name(kind, cell), list(cell.choice["flies"])
        if _uniform(cell):
            inner = member(cell, flies[0], 0, name)
            recorders = [(m, inner) for m in range(spec.drones)]
        else:
            members = [member(cell, skill, m, None) for m, skill in enumerate(flies)]
            inner = cells.Composite(side, members, cfg, n, device, s, name=name)
            recorders = [(m, p) for m, p in enumerate(members) if hasattr(p, "errors")]
        out[name] = RecordingPlayer(inner, name, times, flies, recorders)
    return out


# ================================================================================================ the command errors
def _zero_acc() -> dict:
    return {"sum_sq": [0.0] * COMMAND_DIM, "max_abs": [0.0] * COMMAND_DIM, "count": 0,
            "label_max_abs": [0.0] * COMMAND_DIM}


def slot_accumulators(flies: list[str], recorders, players) -> dict:
    """Per skill (``players`` order) the accumulators of a near-miss cell's changed players (``perturbed`` per-slot
    ``errors()``), each slot to the skill it flies: {skill: {"sum_sq", "max_abs", "count", "label_max_abs"}}."""
    acc = {s: _zero_acc() for s in players}
    for slot, obj in recorders:
        e = obj.errors()
        if e is None:
            continue
        a = acc[flies[slot]]
        a["sum_sq"] = [x + float(y) for x, y in zip(a["sum_sq"], e["sum_sq"][slot].cpu().tolist())]
        a["max_abs"] = [max(x, float(y)) for x, y in zip(a["max_abs"], e["max_abs"][slot].cpu().tolist())]
        a["label_max_abs"] = [max(x, float(y)) for x, y in zip(a["label_max_abs"],
                                                               e["ref_max_abs"][slot].cpu().tolist())]
        a["count"] += int(e["count"][slot])
    return acc


def player_accumulators(player, players) -> dict | None:
    """A recorded player's accumulators per skill: a :class:`RecordingSkillTeam`'s ``errors()``, a near-miss
    :class:`RecordingPlayer`'s :func:`slot_accumulators`; None if it records none."""
    if isinstance(player, RecordingSkillTeam):
        return player.errors()
    if isinstance(player, RecordingPlayer) and player.recorders:
        return slot_accumulators(player.flies, player.recorders, players)
    return None


def sum_accumulators(players, accs) -> dict:
    """The accumulators of several cells summed per skill (``players`` order; None entries skipped): sums and rows
    added, maxima taken; the by-live-drone bins kept only when every summed entry has them."""
    out = {s: _zero_acc() for s in players}
    given = [a for a in accs if a is not None]
    by_live = bool(given) and all("sum_sq_by_n_live" in a[s] for a in given for s in a)
    for a in given:
        for s, e in a.items():
            o = out[s]
            o["sum_sq"] = [x + y for x, y in zip(o["sum_sq"], e["sum_sq"])]
            o["max_abs"] = [max(x, y) for x, y in zip(o["max_abs"], e["max_abs"])]
            o["label_max_abs"] = [max(x, y) for x, y in zip(o["label_max_abs"], e["label_max_abs"])]
            o["count"] += int(e["count"])
            if by_live:
                if "sum_sq_by_n_live" not in o:
                    o["sum_sq_by_n_live"] = [[0.0] * COMMAND_DIM for _ in e["count_by_n_live"]]
                    o["count_by_n_live"] = [0] * len(e["count_by_n_live"])
                o["sum_sq_by_n_live"] = [[x + y for x, y in zip(r, q)]
                                         for r, q in zip(o["sum_sq_by_n_live"], e["sum_sq_by_n_live"])]
                o["count_by_n_live"] = [x + y for x, y in zip(o["count_by_n_live"], e["count_by_n_live"])]
    return out


def error_table(acc: dict) -> dict:
    """The command-error table (the M2 file table's ``errors``, and ``limit_failures``' argument): ``cells.command_errors``
    of ``acc``, plus per skill ``rmse_by_n_live`` {"1".."M": the RMSE over the skill's active channels on its rows with
    that many live drones of the side, None for none or for no active channel} when ``acc`` carries the bins (a
    :class:`RecordingSkillTeam`'s; a near-miss arm's table has none)."""
    keys = ("sum_sq", "max_abs", "count", "label_max_abs")
    table = cells.command_errors({s: {k: a[k] for k in keys} for s, a in acc.items()})
    for s, a in acc.items():
        if "sum_sq_by_n_live" not in a:
            continue
        on = table["skills"][s]["active"]
        width = sum(on)
        table["skills"][s]["rmse_by_n_live"] = {
            str(j): (math.sqrt(sum(v for v, act in zip(row, on) if act) / (count * width)) if count and width else None)
            for j, (row, count) in enumerate(zip(a["sum_sq_by_n_live"], a["count_by_n_live"]), start=1)}
    return table


def active_of(errors: dict) -> dict:
    """{skill: [4] bool}: the active channels of an error table (``cells.active_rule`` on the scripts' labels)."""
    return {s: list(e["active"]) for s, e in errors["skills"].items()}


# ================================================================================================ the statistics
def _wins(pg: dict, side: str) -> np.ndarray:
    return np.asarray(pg["outcome"]) == (GUARD_WIN if side == cells.SIDES[0] else STRIKE_WIN)


def cell_entry(arm_pg: dict, ref_pg: dict, side: str, z_cell: float) -> dict:
    """One cell's statistics: ``cells.paired_cell`` at ``z_cell`` (b, c, flips, n, diff, ci, sign_test_p, method) and
    ``end_time`` (``cells.end_time``)."""
    return {**cells.paired_cell(arm_pg, ref_pg, side, z_cell), "end_time": cells.end_time(arm_pg, ref_pg)}


def interval_step(arm_pgs: dict, ref_pgs: dict, kinds: dict, side: str, alpha: float, m: int) -> dict:
    """The read's interval step (R2 RC-1): ``arm_pgs`` and ``ref_pgs`` {cell key: per-game record} on the same starts,
    ``kinds`` {cell key: ``cells.FIXED`` | ``MIXED`` | ``INFO``}; m the side's gated cells of the committed layout
    (``cells.gated_m``). Returns {"cells": {key: :func:`cell_entry` at z_cell}, "pooled": {"all" (fixed and mixed),
    "fixed", "mixed": ``cells.pooled_difference`` at z_pooled or None}, "intervals": {"alpha", "interval",
    "correction", "m": {side: m}, "z_cell", "z_pooled"}}, z_cell = adjusted_z(alpha, m), z_pooled = adjusted_z(alpha,
    1)."""
    if set(arm_pgs) != set(ref_pgs) or not set(arm_pgs) <= set(kinds):
        raise ValueError("the interval step needs the same cells in both arms, each with its kind")
    z_cell, z_pooled = cells.adjusted_z(alpha, m), cells.adjusted_z(alpha, 1)
    entries = {key: cell_entry(arm_pgs[key], ref_pgs[key], side, z_cell) for key in arm_pgs}
    pooled = {}
    for group, members in (("all", (cells.FIXED, cells.MIXED)), ("fixed", (cells.FIXED,)), ("mixed", (cells.MIXED,))):
        keys = [k for k in arm_pgs if kinds[k] in members]
        pooled[group] = cells.pooled_difference({k: _wins(arm_pgs[k], side) for k in keys},
                                                {k: _wins(ref_pgs[k], side) for k in keys}, z_pooled)
    intervals = {"alpha": float(alpha), "interval": cells.NEWCOMBE, "correction": cells.BONFERRONI,
                 "m": {side: int(m)}, "z_cell": z_cell, "z_pooled": z_pooled}
    return {"cells": entries, "pooled": pooled, "intervals": intervals}


def permuted_from_t44(ref, variant: str, spec: cells.CellSpec, perm, n: int, opponents) -> list[dict]:
    """C3 from T44 alone (R2 OA-6), no play: per gated fixed cell (opponent by opponent, codes in ``players`` order)
    {"code", "flies" (code perm[k]), "opponent", "arm" (T44's cell of perm[k] against the opponent), "ref" (T44's cell
    of code k)}, the first ``n`` games of each."""
    out = []
    for opp in opponents:
        for k, code in enumerate(spec.players):
            flies = spec.players[int(perm[k])]
            arm = ref.cell(variant, *cells.cell_of(spec.side, flies, opp))
            base = ref.cell(variant, *cells.cell_of(spec.side, code, opp))
            out.append({"code": code, "flies": flies, "opponent": opp,
                        "arm": {key: np.asarray(v)[:n] for key, v in arm.items()},
                        "ref": {key: np.asarray(v)[:n] for key, v in base.items()}})
    return out


def _mark_key(t) -> str:
    return f"{float(t):g}"


def path_distance(pos_a: np.ndarray, pos_b: np.ndarray, alive_a: np.ndarray, alive_b: np.ndarray, *,
                  path_times_s) -> dict:
    """The distance between two arms' flight paths from the same starts: pos [G, M, T, 3], alive [G, M, T] (each
    slot's first game, the recorders'). Per mark t (key ``f"{t:g}"``): per game the largest distance over its drones
    live in both arms at that mark (an ended game or an absent drone is not compared), then over the games that have
    one: {"games", "median_m", "p90_m" (``PATH_PCT``-th percentile), "max_m"}; None where no game has one."""
    both = np.asarray(alive_a, dtype=bool) & np.asarray(alive_b, dtype=bool)
    dist = np.linalg.norm(np.asarray(pos_a, dtype=np.float64) - np.asarray(pos_b, dtype=np.float64), axis=-1)
    times = list(path_times_s)
    if both.shape[-1] != len(times) or dist.shape != both.shape:
        raise ValueError(f"path arrays {dist.shape} and {both.shape} do not fit {len(times)} marks")
    out = {}
    for j, t in enumerate(times):
        seen = both[:, :, j].any(axis=1)
        if not seen.any():
            out[_mark_key(t)] = None
            continue
        per_game = np.where(both[:, :, j], dist[:, :, j], -np.inf).max(axis=1)[seen]
        out[_mark_key(t)] = {"games": int(seen.sum()), "median_m": float(np.median(per_game)),
                             "p90_m": float(np.percentile(per_game, PATH_PCT)), "max_m": float(per_game.max())}
    return out


# ================================================================================================ the rule
def check_limits(limits: dict) -> None:
    """ValueError naming every ``[limits]`` key that is missing or still FILL_ (R38: a FILL_ never reaches a
    comparison), or ``end_time_gated`` not a bool."""
    bad = [k for k in distil.LIMIT_KEYS if k not in limits or distil.is_fill(limits[k])]
    if bad:
        raise ValueError(f"limits not filled (R38): {', '.join(bad)}")
    if not isinstance(limits[distil.LIMIT_BOOL], bool):
        raise ValueError(f"{distil.LIMIT_BOOL} must be true or false, got {limits[distil.LIMIT_BOOL]!r}")


def _cell_label(cell: dict) -> str:
    if "codes" in cell and "opponent" in cell:
        return f"{'+'.join(cell['codes'])}@{cell['opponent']}"
    return "cell"


def cell_failures(cell: dict, limits: dict) -> list[str]:
    """The per-cell rule (one function for ``limit_failures`` and the C3 to C5 miss counts): flips above
    ``flips_max_games``; the interval (at z_cell) missing or not inside +-``cell_margin``; with ``end_time_gated``, the
    mean |end-step difference| missing or above ``end_time_max_ticks``. A missing value is a failure."""
    out, what = [], _cell_label(cell)
    if cell["flips"] > limits["flips_max_games"]:
        out.append(f"flips_max_games: {what} changed {cell['flips']} games > {limits['flips_max_games']}")
    ci, margin = cell.get("ci"), limits["cell_margin"]
    if ci is None:
        out.append(f"cell_margin: {what} has no interval")
    elif ci[0] < -margin or ci[1] > margin:
        out.append(f"cell_margin: {what} interval [{ci[0]:+.6f}, {ci[1]:+.6f}] not inside +-{margin}")
    if limits["end_time_gated"]:
        et = cell.get("end_time")
        mean = None if et is None else et.get("mean_abs_ticks")
        if mean is None:
            out.append(f"end_time_max_ticks: {what} has no end-step difference")
        elif mean > limits["end_time_max_ticks"]:
            out.append(f"end_time_max_ticks: {what} mean |end-step difference| {mean:.6g} ticks > "
                       f"{limits['end_time_max_ticks']}")
    return out


def _error_failures(errors: dict, limits: dict) -> list[str]:
    out, zero = [], errors.get("zero_skill")
    for skill, e in errors["skills"].items():
        if not e["rows"]:
            continue                         # not flown on these cells (a near-miss arm's other skills)
        if e.get("rmse") is None or e.get("max_abs") is None:
            out.append(f"cmd_rmse_max: {skill} has rows but no command error")
            continue
        if skill == zero:
            top = max(e["max_abs"])
            if top > limits["cmd_zero_skill_max_abs"]:
                out.append(f"cmd_zero_skill_max_abs: {skill} (the zero-command skill) largest |error| {top:.6g} > "
                           f"{limits['cmd_zero_skill_max_abs']}")
            continue
        for ch, (rmse, top, on) in enumerate(zip(e["rmse"], e["max_abs"], e["active"])):
            if on and rmse > limits["cmd_rmse_max"]:
                out.append(f"cmd_rmse_max: {skill} {CHANNEL_NAMES[ch]} rmse {rmse:.6g} > {limits['cmd_rmse_max']}")
            if not on and top > limits["cmd_unused_max_abs"]:
                out.append(f"cmd_unused_max_abs: {skill} unused {CHANNEL_NAMES[ch]} largest |error| {top:.6g} > "
                           f"{limits['cmd_unused_max_abs']}")
    return out


def limit_failures(cells_: list[dict], pooled: dict | None, errors: dict, limits: dict) -> list[str]:
    """One string per miss, naming the ``[limits]`` key (the M2 file table's rule): an active channel's rmse above
    ``cmd_rmse_max``; an unused channel's largest |error| above ``cmd_unused_max_abs``; the zero-command skill's largest
    |error| above ``cmd_zero_skill_max_abs``; each cell by :func:`cell_failures`; the pooled interval (at z_pooled)
    missing or not inside +-``pooled_margin``. Reads the stored intervals, never recomputes one. ValueError if a limit is
    FILL_ (:func:`check_limits`), before any comparison."""
    check_limits(limits)
    out = _error_failures(errors, limits)
    for cell in cells_:
        out += cell_failures(cell, limits)
    ci, margin = (pooled or {}).get("ci"), limits["pooled_margin"]
    if ci is None:
        out.append("pooled_margin: the pooled row has no interval")
    elif ci[0] < -margin or ci[1] > margin:
        out.append(f"pooled_margin: pooled interval [{ci[0]:+.6f}, {ci[1]:+.6f}] not inside +-{margin}")
    return out


def miss_count(cells_: list[dict], limits: dict) -> int:
    """The cells that miss (fail :func:`cell_failures`); ValueError if a limit is FILL_."""
    check_limits(limits)
    return sum(1 for c in cells_ if cell_failures(c, limits))


def gross_control(cells_: list[dict], limits: dict, controls: dict, key: str) -> dict:
    """C3 to C5: PASS when at least ``[controls] key`` (``permuted_min_miss_cells`` or ``unfitted_min_miss_cells``)
    cells miss. ValueError while that count or a limit is FILL_. {"status", "detail"}."""
    if key not in distil.COUNT_KEYS:
        raise ValueError(f"{key!r} is not one of {distil.COUNT_KEYS}")
    need = controls[key]
    if distil.is_fill(need):
        raise ValueError(f"controls.{key} is not filled yet ({need!r}): the owner sets it (R38)")
    misses = miss_count(cells_, limits)
    return {"status": PASS if misses >= int(need) else FAIL,
            "detail": f"{misses} of {len(cells_)} cells miss, at least {int(need)} needed ({key})"}


def near_miss_control(kind: str, cells_: list[dict], pooled: dict | None, errors: dict, limits: dict) -> dict:
    """C6 (a systematic arm, :func:`systematic_kinds`): PASS when :func:`limit_failures` is not empty; C7 (``noise``):
    PASS when it is empty. ValueError while a limit is FILL_. {"status", "detail"}."""
    failures = limit_failures(cells_, pooled, errors, limits)
    random = kind in RANDOM_KINDS
    if not random and kind not in (BIAS, ROTATE) and kind not in SWITCHES:
        raise ValueError(f"{kind!r} is not a near-miss arm")
    ok = not failures if random else bool(failures)
    want = "meets every limit" if random else "fails at least one limit"
    return {"status": PASS if ok else FAIL,
            "detail": f"{kind}: must be read as {want}; {len(failures)} failure(s)" +
                      (": " + "; ".join(failures[:3]) if failures else "")}


def verdict(controls: dict, failures, unfilled: list[str]) -> str:
    """The read's word: ``NOT_RUN`` while any owner key is FILL_ (``unfilled = distil.unfilled_limits(g)``, a smoke;
    F1); else INCONCLUSIVE if any control is not PASS (controls first: FAIL, NONFINITE or NOT_RUN); else NOT DISTILLED
    on any failure, DISTILLED on none. ValueError for no control, an unknown status, or failures ``NOT_RUN`` in a
    run with every owner key filled. The read calls it only outside --smoke (a smoke's word is NOT_RUN,
    ``Ctx.plumbing_only``)."""
    if unfilled:
        return NOT_RUN
    if not controls:
        raise ValueError("a verdict needs the controls")
    unknown = {c["status"] for c in controls.values()} - set(STATUSES)
    if unknown:
        raise ValueError(f"unknown control status(es) {sorted(unknown)}; known {STATUSES}")
    if isinstance(failures, str):
        raise ValueError(f"failures {failures!r}: a run with every owner key filled runs limit_failures")
    if any(c["status"] != PASS for c in controls.values()):
        return INCONCLUSIVE
    return NOT_DISTILLED if failures else DISTILLED


# ================================================================================================ the read (task LS1-M2-T6)
GAMES_DIR = "games"
CONTROLS_FILE, RESULTS, RESULTS_MD, LAYOUT_FILE = "controls.json", "results.json", "results.md", "layout.json"
RUN_FILE, PINNED_SHA, GATES_COPY, JOB_FILE, FIT_REPORT = "run.json", "gates.sha256", "gates.toml", "job.json", \
    "fit_report.json"
HOUR_S = 3600.0
SCRIPTED_FILE = ROOT / "source" / "svg_training" / "opponents" / "scripted.py"
PAIR_SAME, PAIR_B, PAIR_C = 0, 1, 2          # pair_class: the same result, b (the arm lost a reference win), c (reverse)
FIXED, MIXED, INFO = cells.FIXED, cells.MIXED, cells.INFO
# the controls (controls.json names; C6 one per systematic arm, C7 one per random arm: "<name>:<kind>")
CTL_C1, CTL_C1M, CTL_C2 = "ctl_scripts_equal_t44", "ctl_scripts_mixed_play", "ctl_oracle_net_equals_scripts"
CTL_C3, CTL_C4, CTL_C5 = "ctl_permuted_scripts_miss", "ctl_unfitted_net_misses", "ctl_permuted_net_misses"
CTL_C6, CTL_C7 = "ctl_near_miss_systematic_fails", "ctl_near_miss_random_passes"
# the stages of play, in play order (a batch is "<stage>__<opponent>_<chunk>"); C3 has none (T44 alone)
STAGE_C1, STAGE_C1M, STAGE_C2 = "c1_scripts", "c1m_scripts", "c2_oracle"
STAGE_C4, STAGE_C5 = "c4_unfitted", "c5_permuted"
STAGE_R1, STAGE_R2S, STAGE_R2N = "r1_net", "r2_scripts", "r2_net"
STAGES = ((STAGE_C1, STAGE_C1M, STAGE_C2, STAGE_C4, STAGE_C5) + tuple(f"c6_{k}" for k in (BIAS, ROTATE, *SWITCHES))
          + (f"c7_{NOISE}", STAGE_R1, STAGE_R2S, STAGE_R2N))
STAGE_ARM = {STAGE_C1: SCRIPTS, STAGE_C1M: SCRIPTS, STAGE_C2: ORACLE, STAGE_C4: UNFITTED, STAGE_C5: PERMUTED,
             **{f"c6_{k}": k for k in (BIAS, ROTATE, *SWITCHES)}, f"c7_{NOISE}": NOISE, STAGE_R1: NET,
             STAGE_R2S: SCRIPTS, STAGE_R2N: NET}
REFERENCE_STAGES = (STAGE_C1, STAGE_C1M, STAGE_R2S)        # the scripted arms: every other arm is paired with them
STAGE_CONTROL = {STAGE_C1: CTL_C1, STAGE_C1M: CTL_C1M, STAGE_C2: CTL_C2, STAGE_C4: CTL_C4, STAGE_C5: CTL_C5,
                 **{f"c6_{k}": f"{CTL_C6}:{k}" for k in (BIAS, ROTATE, *SWITCHES)}, f"c7_{NOISE}": f"{CTL_C7}:{NOISE}"}
RESULT_KEYS = ("controls", "cells", "intervals", "pooled", "errors", "failures", "verdict", "reasons", "of_record",
               "gates_sha256", "net_sha256", "skill_net_file", "complete")
CELL_KEYS = ("batch", "arm", "side", "kind", "codes", "opponent", "n", "b", "c", "flips", "diff", "ci", "sign_test_p",
             "method", "end_time", "path_distance", "games")
LAYOUT_BATCH_KEYS = ("name", "arm", "side", "device", "seed", "ticks_cap", "hold_ticks", "n", "gates_sha256",
                     "net_sha256", "seconds", "cells")
LAYOUT_CELL_KEYS = ("index", "arm", "codes", "opponent", "player")
ERR_KEYS = ("sum_sq", "max_abs", "label_max_abs")          # per skill and channel: err_<key> [C, K, 4] in a batch file
OBSERVED = "observed in the training simulator"


def control_names(side: str) -> list[str]:
    """The named controls of a read of ``side``, in order (C1, C1m, C2 to C5, C6 per systematic arm, C7)."""
    return ([CTL_C1, CTL_C1M, CTL_C2, CTL_C3, CTL_C4, CTL_C5] + [f"{CTL_C6}:{k}" for k in systematic_kinds(side)]
            + [f"{CTL_C7}:{k}" for k in RANDOM_KINDS])


def batch_name(stage: str, chunk: str) -> str:
    return f"{stage}__{chunk}"


def stage_of(name: str) -> str:
    return name.split("__")[0]


def say(text: str) -> None:
    print(f"[ls1.2] {text}", flush=True)


def refuse(why: str) -> int:
    print(f"[ls1.2] REFUSED: {why}", file=sys.stderr, flush=True)
    return EXIT_REFUSED


def write_json(path: Path, obj) -> None:
    atomic.write_text(path, json.dumps(obj, indent=1, allow_nan=False) + "\n")


def _resolve(path: str) -> Path:
    p = Path(path)
    return p if p.is_absolute() else ROOT / p


def rel(path) -> str:
    """``path`` repository-relative; outside the repository its name only (no machine or user name in a file)."""
    p = Path(path).resolve()
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return f"(outside svg_training)/{p.name}"


@dataclass
class Batch:
    name: str
    stage: str
    arm: str
    cells: list


@dataclass
class Ctx:
    """What a read needs once every check has passed."""
    args: argparse.Namespace
    g: distil.DistilGates
    side: str
    spec: cells.CellSpec
    cfg: object
    variant: str
    ref: object
    n: int
    chunk: int
    device: str
    seed: int
    ticks: int
    every: int
    net: object
    net_sha: str
    unfilled: list
    of_record: bool
    overrides: dict
    m: int
    alpha: float
    z_cell: float
    z_pooled: float
    gated: list
    info: list
    near: list
    scripted: list

    @property
    def run_dir(self) -> Path:
        return self.args.run_dir

    @property
    def plumbing_only(self) -> bool:
        """A smoke checks plumbing, never a verdict (F1; lead, 26 Nov 2026): under --smoke the limit-dependent steps (C3
        to C7 judged, C6 and C7 played, ``limit_failures``, the verdict) are NOT_RUN, filled gate file or not. Outside
        --smoke an unfilled file never gets here (``prepare`` refuses it)."""
        return bool(self.args.smoke or self.unfilled)

    def not_judged(self) -> str:
        """Why the limit-dependent steps are NOT_RUN (``plumbing_only``)."""
        why = "a smoke checks plumbing, never a verdict (F1)"
        if self.unfilled:
            why += f"; the owner's keys are not filled ({', '.join(self.unfilled)}; R38)"
        return why


# ------------------------------------------------------------------------------------------------ the command line
def parse(argv: list[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="STE route 3, job LS1.2: the equivalence read of one team's skill network")
    ap.add_argument("--gates", type=Path, required=True, help="the distillation gate file (distil_gates.toml)")
    ap.add_argument("--side", choices=cells.SIDES, required=True)
    ap.add_argument("--skill-net", type=Path, required=True, help="the network file; its fit_report.json beside it")
    ap.add_argument("--run-dir", type=Path, required=True)
    ap.add_argument("--cap-h", type=float, required=True, help="cap in effective hours (a CPU job: the launcher's "
                                                               "--gpu-h is 0)")
    ap.add_argument("--expect-gates-sha256", help="refuse unless the gate file has this sha256")
    ap.add_argument("--smoke", action="store_true", help="job LS1.0's read: [smoke] read_games starts, not of record")
    ap.add_argument("--allow-code-change", action="store_true",
                    help="resume although the code differs from the first launch's (recorded in code.json)")
    ap.add_argument("--chunk", type=int, default=None, help="cells per game batch (default [read] chunk_cells)")
    ap.add_argument("--games", type=int, default=None, help="test-only: the first N starts (of_record false)")
    ap.add_argument("--opponents", nargs="+", default=None, help="test-only: these opponents (of_record false)")
    ap.add_argument("--mixed", type=int, default=None, help="test-only: the first N combinations (of_record false)")
    ap.add_argument("--stop-after-batch", default=None, help=argparse.SUPPRESS)          # tests only (CA-2)
    return ap.parse_args(argv)


# ------------------------------------------------------------------------------------------------ pre-flight
def _job_problem(args: argparse.Namespace) -> str | None:
    path = args.run_dir / JOB_FILE
    if path.is_file():
        gpu_h = json.loads(path.read_text()).get("gpu_h", 0)
        if gpu_h != 0:
            return f"the read (LS1.2) is a CPU job: launch it at --gpu-h 0, not {gpu_h}"
    return None


def net_check(args: argparse.Namespace, g: distil.DistilGates, cfg) -> tuple[tuple | None, str | None]:
    """The network and its report (design check of M2): ((net, sha256), None) or (None, why it is refused)."""
    side, spec, src = args.side, g.specs[args.side], g.source
    path = Path(args.skill_net)
    report_file = path.parent / FIT_REPORT
    if not path.is_file():
        return None, f"the skill network {path} is missing"
    if not report_file.is_file():
        return None, f"no {FIT_REPORT} beside the skill network ({report_file}): a network is read only from a run"
    report = json.loads(report_file.read_text())
    if report.get("complete") is not True:
        return None, f"{report_file} is not complete: its run has not finished"
    sha = exploit.sha256_file(path)
    if report.get("net_sha256") != sha:
        return None, f"{report_file} names the network {report.get('net_sha256')}, the file has sha256 {sha}"
    if report.get("gates_sha256") != g.sha256:
        return None, (f"{report_file} names the gate file {report.get('gates_sha256')}, this gate file has sha256 "
                      f"{g.sha256}: the network was distilled from another gate file")
    if not args.smoke and report.get("of_record") is not True:
        return None, f"{report_file} is not of record (a smoke or a test run): a read of record needs a network of record"
    problems = skill_net.net_problems(path, sha256=sha, team=side, skills=list(spec.players), team_size=spec.drones,
                                      cfg=cfg, game_file=src["game_file"], game_sha256=src["game_sha256"])
    if problems:
        return None, "; ".join(problems)
    net, meta = skill_net.load_skill_net(path, team=side, skills=list(spec.players), cfg=cfg, device=g.read["device"],
                                         team_size=spec.drones, file_sha256=sha, game_sha256=src["game_sha256"])
    prov = meta.get("provenance") or {}
    if prov.get("distil_gates_sha256") != g.sha256:
        return None, (f"the network's provenance names the gate file {prov.get('distil_gates_sha256')}, this gate file "
                      f"has sha256 {g.sha256}")
    if not args.smoke and prov.get("of_record") is not True:
        return None, "the network's provenance is not of record: a read of record needs a network of record"
    return (net, sha), None


def _subset(args: argparse.Namespace, g: distil.DistilGates, spec: cells.CellSpec) -> tuple[list | None, str | None]:
    """The side's cells after the test-only options (the calibration's rule): (cells, None) or (None, why)."""
    sg = g.skills_gates
    every = cells.side_cells(spec, g.cells, sg)
    among = list(every)
    if args.opponents is not None:
        known = list(dict.fromkeys(c.opponent for c in every))
        unknown = [o for o in args.opponents if o not in known]
        if unknown or len(set(args.opponents)) != len(args.opponents):
            return None, f"--opponents {args.opponents}: the {args.side} team's opponents are {known}"
        among = [c for c in among if c.opponent in args.opponents]
    if args.mixed is not None:
        if not 0 <= args.mixed <= len(g.cells["mixed"][args.side]):
            return None, f"--mixed {args.mixed} outside 0..{len(g.cells['mixed'][args.side])}"
        names = {c["name"] for c in cells.mixed_choices(spec, [tuple(x) for x in g.cells["mixed"][args.side][:args.mixed]])}
        fixed_names = {c["name"] for c in cells.fixed_choices(spec)}
        among = [c for c in among if c.choice["name"] in fixed_names | names]
    return among, None


def prepare(args: argparse.Namespace) -> tuple[Ctx | None, str | None]:
    """Every check before anything is written: (the read's context, None) or (None, why it is refused)."""
    try:
        g = distil.load_distil_gates(args.gates)
    except (OSError, ValueError) as err:
        return None, f"gate file {args.gates}: {err}"
    if args.expect_gates_sha256 and args.expect_gates_sha256 != g.sha256:
        return None, f"the gate file has sha256 {g.sha256}, expected {args.expect_gates_sha256}"
    src, sg = g.source, g.skills_gates
    for key, path, what in (("skills_gates_sha256", _resolve(src["skills_gates"]), "skills gate file"),
                            ("cells_sha256", _resolve(src["cells"]), "cells file"),
                            ("scripted_sha256", SCRIPTED_FILE, "opponents/scripted.py"),
                            ("game_sha256", _resolve(src["game_file"]), "game file")):
        problem = scoring.sha_problem(path, src[key], what)
        if problem:
            return None, f"[source] {key}: {problem}"
    problems = exploit.game_file_problems(sg)
    if problems:
        return None, "the skills gate file's game file(s) differ: " + "; ".join(problems)
    ref_file = ROOT / sg.reference["file"]
    problem = scoring.sha_problem(ref_file, sg.reference["sha256"], "the scoring starts' reference (T44)")
    if problem:
        return None, problem
    unfilled = distil.unfilled_limits(g)
    if unfilled and not args.smoke:
        return None, (f"the owner's keys are not filled yet ({', '.join(unfilled)}): a read of record needs them (R38); "
                      f"--smoke runs without them, not of record")
    if not (math.isfinite(args.cap_h) and args.cap_h > 0):
        return None, f"--cap-h must be a finite number of hours above 0, got {args.cap_h!r}"
    device = str(g.read["device"])
    if device.startswith("cuda"):
        return None, f"[read] device is {device!r}: the read (LS1.2) is a CPU job (exact replay against T44)"
    problem = _job_problem(args)
    if problem:
        return None, problem
    side, spec = args.side, g.specs[args.side]
    cfg = exploit.variant_cfg(sg, distil.VARIANT)
    got, why = net_check(args, g, cfg)
    if why:
        return None, why
    net, net_sha = got
    ref = exploit.load_reference(ref_file)
    n = int(g.smoke["read_games"]) if args.smoke else int(g.cells["read"]["games_per_cell"])
    if args.games is not None:
        n = int(args.games)
    if not 1 <= n <= ref.games:
        return None, f"games per cell {n} outside 1..{ref.games} (T44's starts)"
    chunk = int(g.read["chunk_cells"]) if args.chunk is None else int(args.chunk)
    if chunk < 1:
        return None, f"--chunk must be at least 1, got {chunk}"
    among, why = _subset(args, g, spec)
    if why:
        return None, why
    opponents = {c.opponent for c in among}
    gated = [c for c in among if c.kind != INFO]
    if not gated:
        return None, f"--opponents {args.opponents}: the read needs at least one gated opponent (R1)"
    near = [c for c in near_miss_cells(g, side) if c.opponent in opponents]
    scripted = sorted({c.index: c for c in gated + near}.values(), key=lambda c: c.index)
    overrides = {k: v for k, v in (("games", args.games), ("opponents", args.opponents), ("mixed", args.mixed))
                 if v is not None}
    alpha = float(g.read["alpha"])
    m = cells.gated_m(spec, g.cells, sg)
    return Ctx(args=args, g=g, side=side, spec=spec, cfg=cfg, variant=exploit.ref_variant(sg, distil.VARIANT), ref=ref,
               n=n, chunk=chunk, device=device, seed=int(ref.meta["seed"]), ticks=int(sg.run["ticks_cap"]),
               every=int(sg.run["cap_check_every_ticks"]), net=net, net_sha=net_sha, unfilled=unfilled,
               of_record=not (args.smoke or overrides), overrides=overrides, m=m, alpha=alpha,
               z_cell=cells.adjusted_z(alpha, m), z_pooled=cells.adjusted_z(alpha, 1), gated=gated,
               info=[c for c in among if c.kind == INFO], near=near, scripted=scripted), None


def run_record(ctx: Ctx) -> dict:
    return {"side": ctx.side, "smoke": bool(ctx.args.smoke), "games_per_cell": ctx.n, "chunk_cells": ctx.chunk,
            "overrides": ctx.overrides, "of_record": ctx.of_record, "gates_file": rel(ctx.args.gates),
            "gates_sha256": ctx.g.sha256, "skill_net_file": rel(ctx.args.skill_net), "net_sha256": ctx.net_sha}


# ------------------------------------------------------------------------------------------------ the batches
def chunks_of(among: list, size: int) -> list[tuple[str, list]]:
    """Groups of at most ``size`` cells: one opponent and one kind (fixed, mixed, info) per group, so an arm paired with
    the scripted arms is played at their batch shape (plan constraint 8); ids ``<opponent>_<j>``, j counted per
    opponent."""
    out, by_opp = [], {}
    for cell in among:
        by_opp.setdefault(cell.opponent, []).append(cell)
    for opp, group in by_opp.items():
        j = 0
        for kind in (FIXED, MIXED, INFO):
            part = [c for c in group if c.kind == kind]
            for lo in range(0, len(part), size):
                out.append((f"{opp}_{j:02d}", part[lo:lo + size]))
                j += 1
    return out


def stage_cells(ctx: Ctx) -> dict:
    """{stage: its cells} in play order. The scripted arms (C1 fixed, C1m mixed) hold the gated cells and the near-miss
    cells (under the test-only options the near-miss cells may lie outside the gated ones); C2 the same cells; C4 and C5
    the gated fixed cells (OP-20: C4 30, C5 30 cell-plays per side); C6 and C7 the near-miss cells (each switch arm only
    those where its code flies), played only outside --smoke (``Ctx.plumbing_only``); R1 the gated cells; R2 the info cells
    (the Strike team's guard_mark_inside), its scripted arm then the network."""
    side = ctx.side
    fixed = [c for c in ctx.scripted if c.kind == FIXED]
    mixed = [c for c in ctx.scripted if c.kind == MIXED]
    out = {STAGE_C1: fixed, STAGE_C1M: mixed, STAGE_C2: fixed + mixed,
           STAGE_C4: [c for c in ctx.gated if c.kind == FIXED], STAGE_C5: [c for c in ctx.gated if c.kind == FIXED]}
    if not ctx.plumbing_only:
        for kind in systematic_kinds(side) + RANDOM_KINDS:
            out[(f"c7_{kind}" if kind in RANDOM_KINDS else f"c6_{kind}")] = arm_cells(kind, ctx.near, side)
    out[STAGE_R1] = list(ctx.gated)
    out[STAGE_R2S] = list(ctx.info)
    out[STAGE_R2N] = list(ctx.info)
    return out


def plan_batches(ctx: Ctx) -> list[Batch]:
    out = []
    for stage, among in stage_cells(ctx).items():
        for chunk, part in chunks_of(among, ctx.chunk):
            out.append(Batch(batch_name(stage, chunk), stage, STAGE_ARM[stage], part))
    return out


def _uses_net(arm: str) -> bool:
    return arm in (NET, PERMUTED)


def layout_entry(ctx: Ctx, batch: Batch) -> dict:
    return {"name": batch.name, "arm": batch.arm, "side": ctx.side, "device": ctx.device, "seed": ctx.seed,
            "ticks_cap": ctx.ticks, "hold_ticks": HOLD_TICKS, "n": ctx.n, "gates_sha256": ctx.g.sha256,
            "net_sha256": ctx.net_sha if _uses_net(batch.arm) else None, "seconds": None,
            "cells": [{"index": c.index, "arm": batch.arm, "codes": list(c.choice["flies"]), "opponent": c.opponent,
                       "player": player_name(batch.arm, c)} for c in batch.cells]}


def _without_seconds(entry: dict) -> dict:
    return {k: v for k, v in entry.items() if k != "seconds"}


def layout_problem(ctx: Ctx, batches: list[Batch]) -> str | None:
    path = ctx.run_dir / LAYOUT_FILE
    if not path.is_file():
        return None
    have = json.loads(path.read_text())["batches"]
    want = [json.loads(json.dumps(layout_entry(ctx, b))) for b in batches]
    if len(have) > len(want) or any(_without_seconds(a) != _without_seconds(b) for a, b in zip(have, want)):
        return f"{path} holds another layout (cells, chunks, games, network or gate file): a changed read needs a new folder"
    return None


def acc_arrays(accs: list, players: list[str], drones: int) -> dict:
    """The batch's command-error accumulators per cell and skill (``players`` order; zero where a cell records none):
    err_sum_sq, err_max_abs, err_label_max_abs [C, K, 4] float64, err_count [C, K] int64, and with every recorder's
    bins (a labelled ``RecordingSkillTeam``) err_sum_sq_by_n_live [C, K, M, 4], err_count_by_n_live [C, K, M]. Empty
    when no cell records."""
    given = [a for a in accs if a is not None]
    if not given:
        return {}
    c, k, dim = len(accs), len(players), COMMAND_DIM
    out = {f"err_{key}": np.zeros((c, k, dim)) for key in ERR_KEYS}
    out["err_count"] = np.zeros((c, k), dtype=np.int64)
    by_live = all("sum_sq_by_n_live" in a[s] for a in given for s in a)
    if by_live:
        out["err_sum_sq_by_n_live"] = np.zeros((c, k, drones, dim))
        out["err_count_by_n_live"] = np.zeros((c, k, drones), dtype=np.int64)
    for i, a in enumerate(accs):
        if a is None:
            continue
        for j, skill in enumerate(players):
            e = a[skill]
            for key in ERR_KEYS:
                out[f"err_{key}"][i, j] = e[key]
            out["err_count"][i, j] = int(e["count"])
            if by_live:
                out["err_sum_sq_by_n_live"][i, j] = e["sum_sq_by_n_live"]
                out["err_count_by_n_live"][i, j] = e["count_by_n_live"]
    return out


def acc_of(pg: dict, i: int, players: list[str]) -> dict | None:
    """Cell i's accumulators per skill from a batch file (:func:`acc_arrays`' inverse); None if the batch has none."""
    if "err_count" not in pg:
        return None
    out = {}
    for j, skill in enumerate(players):
        e = {key: [float(x) for x in pg[f"err_{key}"][i, j]] for key in ERR_KEYS}
        e["count"] = int(pg["err_count"][i, j])
        if "err_count_by_n_live" in pg:
            e["sum_sq_by_n_live"] = pg["err_sum_sq_by_n_live"][i, j].tolist()
            e["count_by_n_live"] = [int(x) for x in pg["err_count_by_n_live"][i, j]]
        out[skill] = e
    return out


def pair_class(arm_pg: dict, ref_pg: dict, side: str) -> np.ndarray:
    """[n] int8 per game: PAIR_SAME (both won or both lost), PAIR_B (the reference won, the arm lost), PAIR_C."""
    a, r = _wins(arm_pg, side), _wins(ref_pg, side)
    return np.where(a == r, PAIR_SAME, np.where(r, PAIR_B, PAIR_C)).astype(np.int8)


class Reader:
    """The batch files of a read folder, loaded once, and where each cell's scripted (reference) games are."""

    def __init__(self, ctx: Ctx, batches: list[Batch]):
        self.ctx, self.cache = ctx, {}
        self.where = {}                       # (reference group, cell index) -> (batch, place)
        for b in batches:
            if b.stage in REFERENCE_STAGES:
                group = "info" if b.stage == STAGE_R2S else "gated"
                for i, c in enumerate(b.cells):
                    self.where[(group, c.index)] = (b, i)

    def path(self, batch: Batch) -> Path:
        return self.ctx.run_dir / GAMES_DIR / f"{batch.name}.npz"

    def load(self, batch: Batch) -> dict:
        if batch.name not in self.cache:
            self.cache[batch.name] = scoring.load_batch(self.path(batch))
        return self.cache[batch.name]

    def cell(self, batch: Batch, i: int) -> dict:
        return exploit.slice_cell(self.load(batch), i, self.ctx.n)

    def reference(self, cell: cells.Cell) -> dict:
        b, i = self.where[("info" if cell.kind == INFO else "gated", cell.index)]
        return self.cell(b, i)


def batch_control(ctx: Ctx, batch: Batch, pg: dict, reader: Reader) -> dict:
    """A batch's own controls: paired starts, tags one for one, no non-finite action (``scoring.plumbing_controls``) and
    every game finished; C1 batches: every fixed cell equals T44 game for game (``exploit.replay_ok``, CPU); C2
    batches: every cell equals the scripted arm game for game (``exploit.agreement``) and the oracle's command error
    against the scripts' labels is at most ``[data] label_check_atol`` (the scripts run on another batch layout in the
    oracle and in the labeller: equal to the last bits, not bit for bit, plan constraint 8; the game-for-game equality is
    the control). {"status", "phase", "detail", "parts"}."""
    phase = "result" if batch.stage == STAGE_R1 else "info" if batch.stage in (STAGE_R2S, STAGE_R2N) else "controls"
    parts = scoring.plumbing_controls(pg, ctx.ref, ctx.n, phase)
    unfinished = int(np.sum(np.asarray(pg["outcome"]) == RUNNING))
    parts["all_games_finished"] = {"status": PASS if unfinished == 0 else FAIL, "phase": phase,
                                   "detail": f"{unfinished} unfinished games of {len(pg['outcome'])}"}
    if batch.stage == STAGE_C1:
        bad = []
        for i, cell in enumerate(batch.cells):
            good, text = exploit.replay_ok(exploit.slice_cell(pg, i, ctx.n), t44_of(ctx, cell), ctx.device,
                                           ctx.g.skills_gates.controls, ticks_cap=ctx.ticks)
            if not good:
                bad.append(f"{cell.choice['name']}@{cell.opponent}: {text}")
        parts["replay_t44"] = {"status": PASS if not bad else FAIL, "phase": phase,
                               "detail": (f"{len(batch.cells)} fixed cells equal T44 game for game" if not bad
                                          else "; ".join(bad))}
    if batch.stage == STAGE_C2:
        bad = []
        for i, cell in enumerate(batch.cells):
            ag = exploit.agreement(exploit.slice_cell(pg, i, ctx.n), reader.reference(cell))
            if ag["differ"]:
                bad.append(f"{cell.choice['name']}@{cell.opponent}: {ag['differ']} of {ag['games']} games differ")
        parts["oracle_equals_scripts"] = {"status": PASS if not bad else FAIL, "phase": phase,
                                          "detail": (f"{len(batch.cells)} cells equal the scripted arm game for game"
                                                     if not bad else "; ".join(bad))}
        top = float(np.max(pg["err_max_abs"])) if "err_max_abs" in pg else None
        atol = float(ctx.g.data["label_check_atol"])
        parts["oracle_command_error"] = {"status": PASS if top is not None and top <= atol else FAIL, "phase": phase,
                                         "detail": f"largest |oracle - scripts' label| {top}, at most {atol} "
                                                   f"([data] label_check_atol: the batch layout moves the last bits, "
                                                   f"plan constraint 8)"}
    status = scoring.control_status(parts, True)
    return {"status": status, "phase": phase, "detail": "; ".join(f"{k} {v['status']}" for k, v in parts.items()),
            "parts": parts}


def t44_of(ctx: Ctx, cell: cells.Cell, code: str | None = None) -> dict:
    pg = ctx.ref.cell(ctx.variant, *cells.cell_of(ctx.side, code or cell.choice["script"], cell.opponent))
    return {k: np.asarray(v)[:ctx.n] for k, v in pg.items()}


def play_batch(ctx: Ctx, batch: Batch, reader: Reader, active: dict | None, should_stop) -> dict:
    """Play one batch (``exploit.play_cells``, hold 1, T44's starts) and add the recorders' arrays: pos_at, alive_at,
    the command-error accumulators, and on an arm batch pair_class against the scripted arm."""
    net = ctx.net if _uses_net(batch.arm) else None
    players = arms(ctx.side, batch.arm, g=ctx.g, among=batch.cells, cfg=ctx.cfg, n=ctx.n, device=ctx.device,
                   seed=ctx.seed, net=net, net_sha256=ctx.net_sha if net is not None else None, active=active)
    if len(players) != len(batch.cells):
        raise ValueError(f"{batch.name}: {len(players)} players for {len(batch.cells)} cells")
    pairs = [cells.cell_of(ctx.side, name, cell.opponent) for name, cell in zip(players, batch.cells)]
    pg = exploit.play_cells(ctx.cfg, ctx.g.skills_gates.run["size"], ctx.ref, pairs, ctx.n, ctx.device, ctx.seed,
                            ctx.ticks, hold_ticks=HOLD_TICKS, should_stop=should_stop, players=players)
    paths = [p.paths() for p in players.values()]
    pg["pos_at"] = np.concatenate([x[0] for x in paths])
    pg["alive_at"] = np.concatenate([x[1] for x in paths])
    pg.update(acc_arrays([player_accumulators(p, list(ctx.spec.players)) for p in players.values()],
                         list(ctx.spec.players), ctx.spec.drones))
    if batch.stage not in REFERENCE_STAGES:
        pg["pair_class"] = np.concatenate([pair_class(exploit.slice_cell(pg, i, ctx.n), reader.reference(c), ctx.side)
                                           for i, c in enumerate(batch.cells)])
    return pg


# ------------------------------------------------------------------------------------------------ the arms' reads
def arm_read(ctx: Ctx, batches: list[Batch], reader: Reader, arm: str) -> dict:
    """One arm's cells, paired with the scripted arm: {"rows": results' cell entries (CELL_KEYS), "pooled",
    "intervals" (:func:`interval_step` at z_cell and z_pooled), "accs": per cell its accumulators, "kinds"}."""
    arm_pgs, ref_pgs, kinds, where = {}, {}, {}, {}
    for b in batches:
        for i, c in enumerate(b.cells):
            arm_pgs[c.index], ref_pgs[c.index], kinds[c.index] = reader.cell(b, i), reader.reference(c), c.kind
            where[c.index] = (b, i, c)
    read = interval_step(arm_pgs, ref_pgs, kinds, ctx.side, ctx.alpha, ctx.m)
    rows, accs = [], {}
    times = ctx.g.read["path_times_s"]
    for key, (b, i, c) in where.items():
        e = read["cells"][key]
        mine, base = arm_pgs[key], ref_pgs[key]
        dist = path_distance(mine["pos_at"], base["pos_at"], mine["alive_at"], base["alive_at"], path_times_s=times)
        rows.append({"batch": b.name, "arm": arm, "side": ctx.side, "kind": c.kind, "codes": list(c.choice["flies"]),
                     "opponent": c.opponent, "n": e["n"], "b": e["b"], "c": e["c"], "flips": e["flips"],
                     "diff": e["diff"], "ci": e["ci"], "sign_test_p": e["sign_test_p"], "method": e["method"],
                     "end_time": e["end_time"], "path_distance": dist,
                     "games": {"file": f"{GAMES_DIR}/{b.name}.npz", "start": i * ctx.n, "stop": (i + 1) * ctx.n}})
        accs[key] = acc_of(reader.load(b), i, list(ctx.spec.players))
    return {"rows": rows, "pooled": read["pooled"], "intervals": read["intervals"], "accs": accs, "kinds": kinds}


def arm_errors(ctx: Ctx, accs: list) -> dict:
    """The command-error table (:func:`error_table`) of the summed accumulators ``accs``."""
    return error_table(sum_accumulators(list(ctx.spec.players), accs))


def _not_run(ctx: Ctx) -> dict:
    return {"status": NOT_RUN, "phase": "controls", "detail": f"not judged: {ctx.not_judged()}"}


def permuted_scripts_control(ctx: Ctx) -> dict:
    """C3 from T44 alone (no play): code k flies T44's cell of code perm[k] on the read's gated fixed cells; at least
    ``permuted_min_miss_cells`` cells miss."""
    if ctx.plumbing_only:
        return _not_run(ctx)
    opponents = list(dict.fromkeys(c.opponent for c in ctx.gated if c.kind == FIXED))
    rows = permuted_from_t44(ctx.ref, ctx.variant, ctx.spec, ctx.g.cells["permutation"][ctx.side], ctx.n, opponents)
    read = interval_step({i: r["arm"] for i, r in enumerate(rows)}, {i: r["ref"] for i, r in enumerate(rows)},
                         {i: FIXED for i in range(len(rows))}, ctx.side, ctx.alpha, ctx.m)
    entries = [{**read["cells"][i], "codes": [r["code"]] * ctx.spec.drones, "opponent": r["opponent"]}
               for i, r in enumerate(rows)]
    return {**gross_control(entries, ctx.g.limits, ctx.g.controls, "permuted_min_miss_cells"), "phase": "controls"}


def _aggregate(name: str, statuses: list[str], what: str) -> dict:
    if not statuses:
        return {"status": PASS, "phase": "controls", "detail": f"{what}: no cell in this read (a test-only subset)"}
    bad = [s for s in statuses if s != PASS]
    return {"status": PASS if not bad else FAIL, "phase": "controls",
            "detail": f"{what}: {len(statuses) - len(bad)} of {len(statuses)} batches PASS"}


def judge(ctx: Ctx, stage_batches: dict, controls: dict, reader: Reader, active: dict | None) -> dict:
    """The named controls of every stage played so far (recomputed from the batch files at each launch)."""
    out = {}
    if STAGE_C1 in stage_batches:
        out[CTL_C1] = _aggregate(CTL_C1, [controls[b.name]["status"] for b in stage_batches[STAGE_C1]],
                                 "the scripts through the dispatch equal T44 game for game on the fixed cells")
    if STAGE_C1M in stage_batches:
        out[CTL_C1M] = _aggregate(CTL_C1M, [controls[b.name]["status"] for b in stage_batches[STAGE_C1M]],
                                  "the scripted mixed cells (Composite) play cleanly")
    if STAGE_C2 in stage_batches:
        out[CTL_C2] = _aggregate(CTL_C2, [controls[b.name]["status"] for b in stage_batches[STAGE_C2]],
                                 "the oracle network path equals the scripted arm game for game")
    if CTL_C2 in out:
        out[CTL_C3] = permuted_scripts_control(ctx)
    for stage, name, key in ((STAGE_C4, CTL_C4, "unfitted_min_miss_cells"), (STAGE_C5, CTL_C5, "permuted_min_miss_cells")):
        if stage not in stage_batches:
            continue
        if ctx.plumbing_only:
            out[name] = _not_run(ctx)
            continue
        rows = arm_read(ctx, stage_batches[stage], reader, STAGE_ARM[stage])["rows"]
        out[name] = {**gross_control(rows, ctx.g.limits, ctx.g.controls, key), "phase": "controls"}
    if ctx.plumbing_only:
        if STAGE_C5 in stage_batches:               # C6 and C7 are not played (F1): written NOT_RUN with C5's judgment
            for name in control_names(ctx.side):
                if name.startswith((CTL_C6, CTL_C7)):
                    out[name] = _not_run(ctx)
        return out
    for kind in systematic_kinds(ctx.side) + RANDOM_KINDS:
        stage = f"c7_{kind}" if kind in RANDOM_KINDS else f"c6_{kind}"
        name = f"{CTL_C7 if kind in RANDOM_KINDS else CTL_C6}:{kind}"
        if stage not in stage_batches:
            continue
        if not stage_batches[stage]:
            out[name] = {"status": FAIL, "phase": "controls", "detail": f"{kind}: no near-miss cell in this read"}
            continue
        read = arm_read(ctx, stage_batches[stage], reader, kind)
        errors = arm_errors(ctx, list(read["accs"].values()))
        out[name] = {**near_miss_control(kind, read["rows"], read["pooled"]["all"], errors, ctx.g.limits),
                     "phase": "controls"}
    return out


# ------------------------------------------------------------------------------------------------ the results
def intervals_of(ctx: Ctx) -> dict:
    return {"alpha": ctx.alpha, "interval": cells.NEWCOMBE, "correction": cells.BONFERRONI, "m": {ctx.side: ctx.m},
            "z_cell": ctx.z_cell, "z_pooled": ctx.z_pooled}


def inconclusive(ctx: Ctx, controls: dict) -> dict:
    """results.json of a read whose controls are not all PASS (OP-19): no result batch is played."""
    reasons = [f"{name}: {v['status']}: {v['detail']}" for name, v in controls.items() if v["status"] != PASS]
    return {"controls": controls, "cells": [], "intervals": intervals_of(ctx),
            "pooled": {"all": None, "fixed": None, "mixed": None}, "errors": None, "failures": [],
            "verdict": INCONCLUSIVE, "reasons": reasons, "of_record": ctx.of_record, "gates_sha256": ctx.g.sha256,
            "net_sha256": ctx.net_sha, "skill_net_file": rel(ctx.args.skill_net), "complete": True}


def results_of(ctx: Ctx, stage_batches: dict, controls: dict, reader: Reader) -> dict:
    """results.json from the batch files only (a resumed read gives the uninterrupted read's file)."""
    rows = []
    for stage in STAGES:
        if stage in REFERENCE_STAGES or not stage_batches.get(stage):
            continue
        read = arm_read(ctx, stage_batches[stage], reader, STAGE_ARM[stage])
        rows += read["rows"]
        if stage == STAGE_R1:
            r1 = read
    pooled = r1["pooled"]
    errors = arm_errors(ctx, [a for key, a in r1["accs"].items() if r1["kinds"][key] == FIXED])
    gated = [r for r in rows if r["arm"] == NET and r["kind"] in (FIXED, MIXED)]
    if ctx.plumbing_only:
        failures, word = NOT_RUN, NOT_RUN
        reasons = [f"not judged: {ctx.not_judged()}"]
    else:
        failures = limit_failures(gated, pooled["all"], errors, ctx.g.limits)
        word = verdict(controls, failures, ctx.unfilled)
    if not ctx.plumbing_only:
        reasons = ([f"{n}: {v['status']}" for n, v in controls.items() if v["status"] != PASS] if word == INCONCLUSIVE
                   else list(failures))
    return {"controls": controls, "cells": rows, "intervals": r1["intervals"], "pooled": pooled, "errors": errors,
            "failures": failures, "verdict": word, "reasons": reasons, "of_record": ctx.of_record,
            "gates_sha256": ctx.g.sha256, "net_sha256": ctx.net_sha, "skill_net_file": rel(ctx.args.skill_net),
            "complete": True}


def _f(v, digits: int = 4) -> str:
    return "-" if v is None else f"{v:.{digits}f}" if isinstance(v, float) else str(v)


def _ci(ci) -> str:
    return "-" if ci is None else f"[{ci[0]:+.4f}, {ci[1]:+.4f}]"


def _pooled(row: dict | None) -> str:
    return "-" if row is None else f"{row['diff']:+.4f} {_ci(row['ci'])}"


def results_md(ctx: Ctx, res: dict) -> str:
    iv = res["intervals"]
    record = "of record" if res["of_record"] else f"NOT of record (smoke {bool(ctx.args.smoke)}, overrides " \
                                                  f"{json.dumps(ctx.overrides)})"
    lines = [f"# LS1.2 equivalence read, {ctx.side} team ({record})", "",
             f"Training simulator, tier 1; {OBSERVED}. Network {res['skill_net_file']} (sha256 {res['net_sha256']}); "
             f"gate file {rel(ctx.args.gates)} (sha256 {res['gates_sha256']}). {ctx.n} games per cell on T44's starts "
             f"(seed {ctx.seed}), hold {HOLD_TICKS}, tick cap {ctx.ticks}, device {ctx.device}. Intervals "
             f"{iv['interval']}, {iv['correction']}, alpha {iv['alpha']}, m = {iv['m'][ctx.side]}, z_cell "
             f"{iv['z_cell']:.4f}, z_pooled {iv['z_pooled']:.4f}.", "",
             f"**Verdict: {res['verdict']}**" + ("" if res["verdict"] != NOT_RUN else
                                                  f" (no verdict is read: {ctx.not_judged()})"), ""]
    lines += [f"- {r}" for r in res["reasons"]] + ["", "## Controls (read before any result)", "",
                                                    "| Control | Status | Detail |", "|---|---|---|"]
    lines += [f"| {name} | {v['status']} | {v['detail']} |" for name, v in res["controls"].items()
              if not name.startswith(STAGES)]
    if res["cells"]:
        p = res["pooled"]
        summary = cells.error_summary(res["errors"])
        lines += ["", "## R1: the network against the scripts", "",
                  "Pooled difference (network less scripts, win share of the side): "
                  + "; ".join(f"{k} {_pooled(p[k])}" for k in ("all", "fixed", "mixed")) + ".",
                  f"Command error on the fixed cells: largest active-channel RMSE {_f(summary['rmse_active_max'])}, "
                  f"largest unused-channel |error| {_f(summary['unused_max_abs'])}, zero-command skill "
                  f"{res['errors']['zero_skill']} largest |error| {_f(summary['zero_skill_max_abs'])}.", "",
                  "| Arm | Kind | Codes | Opponent | b | c | Flips | Diff | ci (z_cell) | Mean abs end-step diff |",
                  "|---|---|---|---|---|---|---|---|---|---|"]
        lines += [f"| {c['arm']} | {c['kind']} | {'+'.join(c['codes'])} | {c['opponent']} | {c['b']} | {c['c']} | "
                  f"{c['flips']} | {_f(c['diff'])} | {_ci(c['ci'])} | {_f(c['end_time']['mean_abs_ticks'], 1)} |"
                  for c in sorted(res["cells"], key=lambda c: (c["arm"] != NET, -c["flips"]))]
    lines += ["", "Per cell path distances at the marks, the per-game classes and the arrays: results.json, games/.", ""]
    return "\n".join(lines)


# ------------------------------------------------------------------------------------------------ the run
def run(ctx: Ctx, guard: RunGuard, batches: list[Batch]) -> int:
    run_dir = ctx.run_dir
    (run_dir / GAMES_DIR).mkdir(exist_ok=True)
    controls = json.loads((run_dir / CONTROLS_FILE).read_text()) if (run_dir / CONTROLS_FILE).is_file() else {}
    layout_path = run_dir / LAYOUT_FILE
    layout = json.loads(layout_path.read_text()) if layout_path.is_file() else {"batches": []}
    latest = guard.load_latest()
    done = set(latest.state["done"]) if latest is not None else set()
    reader = Reader(ctx, batches)
    seen = [0]

    def should_stop() -> bool:
        if guard.stop_requested:
            return True
        seen[0] += 1
        return seen[0] % ctx.every == 0 and guard.cap_reached()

    def stopped() -> int:
        guard.save(len(done), {"done": sorted(done)})
        reason = guard.stop_reason() or STOP_INTERRUPTED
        say(f"stopped ({reason}); the same command resumes at the next batch not yet done")
        return EXIT_FOR_STOP[reason]

    def failed(code: int, where: str) -> int:
        write_json(run_dir / CONTROLS_FILE, controls)
        if code == EXIT_NONFINITE:
            say(f"NON-FINITE in {where}: no number is reported (exit {code}); the batch files are kept for diagnosis")
            return code
        res = inconclusive(ctx, controls)
        write_json(run_dir / RESULTS, res)
        atomic.write_text(run_dir / RESULTS_MD, results_md(ctx, res))
        say(f"CONTROL FAILED in {where}: no result batch is played (exit {code})")
        print(INCONCLUSIVE, flush=True)
        return code

    def play(stage_list: list[Batch], active: dict | None) -> int | None:
        for batch in stage_list:
            path = reader.path(batch)
            if batch.name in done and path.is_file():
                continue
            if guard.stop_reason():
                return stopped()
            index = batches.index(batch)
            if index >= len(layout["batches"]):
                layout["batches"].append(layout_entry(ctx, batch))
                write_json(layout_path, layout)
            started = time.perf_counter()
            try:
                pg = play_batch(ctx, batch, reader, active, should_stop)
            except sweep.SweepStopped:
                return stopped()
            took = time.perf_counter() - started
            temporary = path.with_name(f"{batch.name}.part.npz")
            scoring.save_batch(temporary, pg)
            os.replace(temporary, path)
            reader.cache.pop(batch.name, None)
            layout["batches"][index]["seconds"] = took
            write_json(layout_path, layout)
            ctl = batch_control(ctx, batch, pg, reader)
            controls[batch.name] = ctl
            write_json(run_dir / CONTROLS_FILE, controls)
            done.add(batch.name)
            guard.save(len(done), {"done": sorted(done)})
            say(f"{batch.name}: {len(batch.cells)} cells x {ctx.n} games, {took:.1f} s, {ctl['status']}")
            if ctx.args.stop_after_batch == batch.name:
                os.kill(os.getpid(), signal.SIGTERM)          # the contract's own stop (CA-2): exit 4 at the next check
            code = scoring.ending({batch.name: ctl})
            if code is not None:
                if batch.stage in STAGE_CONTROL:             # the batch's control is its stage's named control too
                    controls[STAGE_CONTROL[batch.stage]] = {"status": ctl["status"], "phase": "controls",
                                                            "detail": f"batch {batch.name}: {ctl['detail']}"}
                return failed(code, f"{batch.name} ({ctl['detail']})")
        return None

    by_stage = {}
    for b in batches:
        by_stage.setdefault(b.stage, []).append(b)
    planned = stage_cells(ctx)
    stage_batches = {}
    active = None
    for stage in STAGES:
        if stage not in planned or stage in (STAGE_R1, STAGE_R2S, STAGE_R2N):
            continue
        if stage.startswith("c7_") and active is None:
            c2 = arm_read(ctx, by_stage.get(STAGE_C2, []), reader, ORACLE)
            active = active_of(arm_errors(ctx, list(c2["accs"].values())))
        code = play(by_stage.get(stage, []), active)
        if code is not None:
            return code
        stage_batches[stage] = by_stage.get(stage, [])
        named = judge(ctx, stage_batches, controls, reader, active)
        controls.update(named)
        write_json(run_dir / CONTROLS_FILE, controls)
        bad = {k: v for k, v in named.items() if v["status"] not in (PASS, NOT_RUN)}
        if bad:
            code = scoring.ending(bad) or EXIT_CONTROL_FAILED
            return failed(code, ", ".join(bad))
    say("controls settled: " + ", ".join(f"{k} {controls[k]['status']}" for k in control_names(ctx.side)))
    for stage in (STAGE_R1, STAGE_R2S, STAGE_R2N):
        code = play(by_stage.get(stage, []), active)
        if code is not None:
            return code
        stage_batches[stage] = by_stage.get(stage, [])
    if guard.stop_reason():
        return stopped()
    res = results_of(ctx, stage_batches, controls, reader)
    try:
        json.dumps(res, allow_nan=False)
    except ValueError as err:
        say(f"NON-FINITE value in the results ({err}); nothing written (exit {EXIT_NONFINITE})")
        return EXIT_NONFINITE
    atomic.write_text(run_dir / RESULTS_MD, results_md(ctx, res))
    write_json(run_dir / RESULTS, res)
    guard.save(len(done), {"done": sorted(done), "phase": "done"})
    say(f"done: {rel(run_dir / RESULTS_MD)} (of_record {ctx.of_record})")
    print(res["verdict"], flush=True)
    return EXIT_CONTROL_FAILED if res["verdict"] == INCONCLUSIVE else EXIT_DONE


def main(argv: list[str] | None = None) -> int:
    args = parse(list(sys.argv[1:] if argv is None else argv))
    ctx, why = prepare(args)
    if why:
        return refuse(why)
    run_dir = args.run_dir
    results_file = run_dir / RESULTS
    controls_file = run_dir / CONTROLS_FILE
    if controls_file.is_file():
        code = scoring.ending({k: v for k, v in json.loads(controls_file.read_text()).items()
                               if v["status"] != NOT_RUN})
        if code is not None:
            print(f"[ls1.2] a control is not PASS in this run folder ({controls_file}): read it; a new read needs a new "
                  f"run folder (exit {code})", file=sys.stderr, flush=True)
            return code
    if results_file.is_file() and json.loads(results_file.read_text()).get("complete") is True:
        word = json.loads(results_file.read_text())["verdict"]
        say(f"this run folder is done ({rel(results_file)}): nothing to do")
        print(word, flush=True)
        return EXIT_DONE
    pinned = run_dir / PINNED_SHA
    if pinned.is_file() and pinned.read_text().strip() != ctx.g.sha256:
        return refuse(f"the gate file changed since the first launch in {run_dir}: a changed file needs a new run folder")
    if (run_dir / RUN_FILE).is_file():
        was, now = json.loads((run_dir / RUN_FILE).read_text()), json.loads(json.dumps(run_record(ctx)))
        differ = [f"{k} {was.get(k)!r} (this command: {now[k]!r})" for k in now if was.get(k) != now[k]]
        if differ:
            return refuse(f"{run_dir / RUN_FILE} was started as another read: {'; '.join(differ)}")
    batches = plan_batches(ctx)
    problem = layout_problem(ctx, batches)
    if problem:
        return refuse(problem)
    run_dir.mkdir(parents=True, exist_ok=True)
    try:
        with RunGuard(run_dir, cap_s=args.cap_h * HOUR_S) as guard:
            changed = l011.pin_code(args)
            if changed:
                return refuse(changed)
            if not pinned.is_file():
                atomic.write_text(run_dir / GATES_COPY, Path(args.gates).read_text())
                atomic.write_text(pinned, ctx.g.sha256 + "\n")
            if not (run_dir / RUN_FILE).is_file():
                write_json(run_dir / RUN_FILE, run_record(ctx))
            return run(ctx, guard, batches)
    except RunBusyError as err:
        return refuse(str(err))
    except NonFiniteError as err:
        say(f"NON-FINITE: {err} (exit {EXIT_NONFINITE})")
        return EXIT_NONFINITE


if __name__ == "__main__":
    sys.exit(main())
