#!/usr/bin/env python
"""STE route 3, stage LS1, job LS1.2: the equivalence read of a skill network against the scripts it copies (plan
ste_learning/drafts/LS1_TASK_PLAN.md, merge M2; the design check of M2). This file holds the read's importable part
(task LS1-M2-T5): its players and its verdict functions. The read itself (the command line, the batches, the run
contract, ``results.json``) is task LS1-M2-T6 and is not built yet: run as a script, this file refuses (exit 2).

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

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))

import numpy as np  # noqa: E402
import torch  # noqa: E402
from torch import Tensor, nn  # noqa: E402

from svg_training.core.game_config import TICK_S  # noqa: E402
from svg_training.core.observations import ObsView  # noqa: E402
from svg_training.core.rewards import GUARD_WIN, STRIKE_WIN  # noqa: E402
from svg_training.opponents import perturbed  # noqa: E402
from svg_training.opponents.scripted import make_strategy  # noqa: E402
from svg_training.ste import cells, distil, exploit, scoring, skills  # noqa: E402
from svg_training.ste.run_contract import EXIT_REFUSED  # noqa: E402

PASS, FAIL, NONFINITE = scoring.PASS, scoring.FAIL, scoring.NONFINITE
NOT_RUN = "NOT_RUN"                              # a control or a verdict not run (a smoke with FILL_ values, F1)
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
    run with every owner key filled."""
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


def main() -> int:
    print("[ls1.2] the equivalence read (job LS1.2) is task LS1-M2-T6, not built yet: this file holds its players and "
          "verdict functions only", file=sys.stderr, flush=True)
    return EXIT_REFUSED


if __name__ == "__main__":
    sys.exit(main())
