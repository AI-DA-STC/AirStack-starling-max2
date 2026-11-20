"""STE task L0.11 Screening sweep (INFO): the gate file, the plan of cells and batches, the sweep's game, one batch played,
the controls with known answers, and the shortlist rule. The driver is ``scripts/ste_sweep_l011.py``.

**The gate file** (``configs/ste_l011/gates.toml``, :func:`load_gates`): every section and key is required, an unknown one
raises. It names the variant game files with their sha256 (:func:`game_file_problems` reports a file that changed), the
groups of cells in run order (the cut order read backwards), the controls, the shortlist rule, the clips and the pilot.

**A cell** is one scripted Guard against one scripted Strike in one variant at one team size: ``games_per_cell`` games.
**A batch** is up to ``cells_per_batch`` cells of one group played side by side in one game of
``cells x games_per_cell`` games (:func:`play_batch`): the safety filter costs about the same per tick for 1,000 or
10,000 games, so packing saves time (``scripts/score.py``). The batches of a group are fixed by the gate file
(:func:`build_plan`): the filter's early stop is batch-wide, so a cell's numbers may depend on its batch-mates in the
last float digits, and a batch is never re-packed.

**Paired starts.** :class:`SweepGame` is ``SvgGame`` with the starts hook replaced (``SvgGame._draw_starts``, the hook
the NUS port's hangar game uses): one draw of ``games_per_cell`` starts, from the start mode of the game file
(``core/arena.draw_starts``) and the game's own seed, tiled over the cells. So every cell of every batch of one start
setting meets the same 1,000 starts, whatever the batch size. The game itself is not changed: the step, the rules, the
filter and the tag are ``SvgGame``'s. It also counts, per game slot and for the slot's first game only (as
``core/play.play_match`` counts), the Strike drones tagged, the Strike drones left when the game ended, and the start's
team-mate pairs closer than the filter distance; and it asks ``should_stop`` before every tick (a Python call, no host
read), raising :class:`SweepStopped` so that a stop or the cap ends a batch at once (the batch is played again on resume).

Shapes: N games (= cells x games per cell), M drones (Guard drones first). Everything in the step is a batched tensor
operation; the host reads happen after a batch. Standard library, NumPy and PyTorch only. No tuned number lives here
(tests/test_ste_literals.py): every value comes from the gate file or a game file.
"""
from __future__ import annotations

import dataclasses
import hashlib
import math
import time
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import numpy as np
import torch
from torch import Tensor

from ..core.arena import Arenas, draw_starts
from ..core.game import SvgGame
from ..core.game_config import GameCfg, load_game_cfg
from ..core.metrics import summarise, wilson_interval
from ..core.play import play_match
from ..core.rewards import GUARD_WIN, RUNNING, STRIKE_WIN
from ..core.strategy import SplitStrategy
from ..opponents.scripted import REGISTRY, make_strategy
from . import shared

ROOT = shared.PACKAGE_DIR.parents[2]         # svg_training/ (PACKAGE_DIR is source/svg_training/ste)
GATES_FILE = ROOT / "configs" / "ste_l011" / "gates.toml"
GUARD_SEED_OFFSET = 101             # players' seeds: game seed + these, as scripts/score.py and viz/replay.py
STRIKE_SEED_OFFSET = 202
ROLE_SWEEP, ROLE_CONTROL, ROLE_SENSITIVITY = "sweep", "control", "sensitivity"
SAME_SEED, STAND_STILL, ZERO_TAGS = "same_seed_twice", "stand_still_never_reaches", "zero_tags"
STILL_ZERO_TAGS = "stand_still_zero_tags"     # both teams command zero, tag on: no tag in the group's first ``ticks``
CONTROL_KINDS = (SAME_SEED, STAND_STILL, ZERO_TAGS, STILL_ZERO_TAGS)
GLOBAL_CHECKS = ("tags_at_most_min_team", "paired_starts", "no_nonfinite_actions")
TIE_BREAKS = ("lab_arena_first", "larger_zone_tag_margin", "lower_guard_survives", "run_order")
ALL = "all"
SUMMARY_KEYS = ("guard_wins", "hold_rate", "ci_low", "ci_high", "mean_end_step", "closest_cross_m", "closest_cross_p05_m",
                "closest_cross_p25_m", "closest_cross_p50_m", "closest_cross_3d_m", "closest_cross_3d_p05_m",
                "closest_cross_3d_p25_m", "closest_cross_3d_p50_m", "rule_breach_rate", "filter_rate", "start_miss_rate")
PER_GAME_EXACT = ("outcome", "end_step", "tags", "strikes_left", "start_pos_m")   # equal in a same-seed replay

_SECTIONS = {
    "run": {"task", "kind", "seed", "games_per_cell", "cells_per_batch", "ticks_cap", "device", "cap_check_every_ticks"},
    "players": {"guards", "strikes", "one_strike_duplicates", "z_up_info", "z_up_label"},
    "confounds": {"ring_outside_zone_m", "zone_2p4", "arena_7p5", "height_offset_cell"},
    "cut": {"protected", "safety_factor"},
    "controls": {"stop_on_fail", "same_seed_closest_tol_m", "global_checks"},
    "shortlist": {"always", "candidates", "report_only", "max_variants", "trivial_at", "tie_window", "tie_breaks"},
    "clips": {"cells", "group", "games", "seed", "max_ticks", "speed", "fps", "dpi", "reserve_s"},
    "pilot": {"sizes", "cells_per_batch", "ticks", "warmup_ticks"},
}
_GROUP_KEYS = {
    ROLE_SWEEP: {"name", "role", "factor", "level", "game", "size", "guards", "strikes"},
    ROLE_CONTROL: {"name", "role", "control", "game", "size", "guards", "strikes"},
    ROLE_SENSITIVITY: {"name", "role", "factor", "level", "game", "size", "guards", "strikes", "strike_start_dz_m"},
    SAME_SEED: {"name", "role", "control", "of_group", "of_batch"},
    STILL_ZERO_TAGS: {"name", "role", "control", "game", "size", "guards", "strikes", "ticks"},
}


class SweepStopped(RuntimeError):
    """``should_stop`` said yes before a tick: the batch is abandoned (it is played again from its start on resume)."""


@dataclass(frozen=True)
class GameRef:
    """A variant game file: its path (relative to ``svg_training/``) and the sha256 the gate file pins."""
    file: str
    sha256: str


@dataclass(frozen=True)
class GroupSpec:
    """One ``[[groups]]`` entry. Fields a role does not use are None."""
    name: str
    role: str
    factor: str | None
    level: str | None
    game: str | None
    size: str | None
    guards: tuple[str, ...] | None
    strikes: tuple[str, ...] | None
    control: str | None
    of_group: str | None
    of_batch: int | None
    ticks: int | None                       # a group's own tick cap (stand_still_zero_tags), else None: the run's
    strike_start_dz_m: float | None         # sensitivity groups: every Strike drone starts this much higher (m)

    def ticks_cap(self, run: dict) -> int:
        return int(self.ticks if self.ticks is not None else run["ticks_cap"])


@dataclass(frozen=True)
class Gates:
    """The gate file as loaded. ``sha256``: of its bytes (the driver pins it in the run folder)."""
    path: str
    sha256: str
    run: dict
    players: dict
    confounds: dict
    games: dict
    groups: tuple[GroupSpec, ...]
    cut: dict
    projection: dict
    controls: dict
    shortlist: dict
    clips: dict
    pilot: dict

    def group(self, name: str) -> GroupSpec:
        for spec in self.groups:
            if spec.name == name:
                return spec
        raise KeyError(f"no group {name!r} in the gate file")

    def with_game(self, name: str, file: str) -> "Gates":
        """A copy whose game ``name`` points at ``file`` (same pinned sha256): tests of the sha check."""
        games = dict(self.games)
        games[name] = GameRef(file, self.games[name].sha256)
        return dataclasses.replace(self, games=games)

    @property
    def ring_margin_m(self) -> float:
        return float(self.confounds["ring_outside_zone_m"])


def parse_size(size: str) -> tuple[int, int]:
    """'3v3' -> (3 Guard drones, 3 Strike drones)."""
    guards, _, strikes = size.lower().partition("v")
    if not (guards.isdigit() and strikes.isdigit()):
        raise ValueError(f"a team size looks like '3v3' (Guard v Strike), got {size!r}")
    return int(guards), int(strikes)


def _exact_keys(table: Any, keys: set[str], where: str) -> dict:
    if not isinstance(table, dict):
        raise ValueError(f"[{where}] must be a table")
    unknown, missing = sorted(set(table) - keys), sorted(keys - set(table))
    if unknown:
        raise ValueError(f"unknown key(s) in [{where}]: {unknown}")
    if missing:
        raise ValueError(f"missing key(s) in [{where}]: {missing}")
    return table


def _names(value: Any, known: list[str], where: str) -> tuple[str, ...]:
    names = tuple(known) if value == ALL else tuple(value)
    bad = [n for n in names if n not in REGISTRY]
    if bad or not names:
        raise ValueError(f"{where}: unknown or empty player list {bad or names}")
    return names


def _group(table: dict, players: dict, games: dict) -> GroupSpec:
    role = table.get("role")
    kind = table.get("control") if role == ROLE_CONTROL else None
    key = kind if kind in (SAME_SEED, STILL_ZERO_TAGS) else role
    if key not in _GROUP_KEYS:
        raise ValueError(f"group {table.get('name')!r}: role must be one of {ROLE_SWEEP!r}, {ROLE_CONTROL!r}, "
                         f"{ROLE_SENSITIVITY!r}")
    _exact_keys(table, _GROUP_KEYS[key], f"groups {table.get('name')}")
    if kind is not None and kind not in CONTROL_KINDS:
        raise ValueError(f"group {table['name']}: unknown control {kind!r} (known: {CONTROL_KINDS})")
    has_game = "game" in table
    if has_game:
        if table["game"] not in games:
            raise ValueError(f"group {table['name']}: game {table['game']!r} is not in [games]")
        parse_size(table["size"])
    return GroupSpec(
        name=table["name"], role=role, factor=table.get("factor"), level=table.get("level"),
        game=table.get("game"), size=table.get("size"),
        guards=_names(table["guards"], players["guards"], table["name"]) if has_game else None,
        strikes=_names(table["strikes"], players["strikes"], table["name"]) if has_game else None,
        control=kind, of_group=table.get("of_group"), of_batch=table.get("of_batch"), ticks=table.get("ticks"),
        strike_start_dz_m=table.get("strike_start_dz_m"))


def load_gates(path: str | Path = GATES_FILE) -> Gates:
    """Load and check the gate file; ValueError names the first problem (unknown or missing key, unknown game, player,
    size, group, control or tie-break)."""
    path = Path(path)
    raw = path.read_bytes()
    data = tomllib.loads(raw.decode())
    top = set(_SECTIONS) | {"games", "groups", "projection"}
    unknown = sorted(set(data) - top)
    if unknown:
        raise ValueError(f"unknown section(s) in {path.name}: {unknown}")
    parts = {name: _exact_keys(data.get(name), keys, name) for name, keys in _SECTIONS.items()}
    games = {}
    for name, ref in data.get("games", {}).items():
        _exact_keys(ref, {"file", "sha256"}, f"games.{name}")
        games[name] = GameRef(ref["file"], ref["sha256"])
    players = parts["players"]
    for team in ("guards", "strikes"):
        _names(players[team], [], f"players.{team}")
    groups = tuple(_group(g, players, games) for g in data.get("groups", []))
    names = [g.name for g in groups]
    if len(set(names)) != len(names) or not groups:
        raise ValueError("group names must be unique, and there must be at least one group")
    for g in groups:
        if g.control == SAME_SEED and g.of_group not in names:
            raise ValueError(f"group {g.name}: of_group {g.of_group!r} is not a group")
    projection = data.get("projection", {})
    _exact_keys(projection, {"seconds_per_batch_tick"}, "projection")
    for size in projection["seconds_per_batch_tick"]:
        parse_size(size)
    sl = parts["shortlist"]
    for name in list(sl["candidates"]) + list(sl["report_only"]) + list(parts["cut"]["protected"]) + [parts["clips"]["group"]]:
        if name not in names:
            raise ValueError(f"{name!r} (shortlist, cut or clips) is not a group")
    if not set(sl["always"]) <= set(sl["candidates"]) or len(sl["always"]) > sl["max_variants"]:
        raise ValueError("shortlist.always must be candidates, at most max_variants of them")
    bad = [t for t in sl["tie_breaks"] if t not in TIE_BREAKS]
    if bad:
        raise ValueError(f"unknown tie-break(s) {bad} (known: {TIE_BREAKS})")
    bad = [c for c in parts["controls"]["global_checks"] if c not in GLOBAL_CHECKS]
    if bad:
        raise ValueError(f"unknown global check(s) {bad} (known: {GLOBAL_CHECKS})")
    return Gates(path=str(path), sha256=hashlib.sha256(raw).hexdigest(), games=games, groups=groups,
                 projection=projection, **parts)


def sha256_file(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def game_file_problems(gates: Gates, root: Path = ROOT) -> list[str]:
    """One line per game file that is missing or whose sha256 is not the one the gate file pins."""
    problems = []
    for name, ref in gates.games.items():
        path = root / ref.file
        if not path.is_file():
            problems.append(f"game {name}: {path} is missing")
        elif sha256_file(path) != ref.sha256:
            problems.append(f"game {name}: {path} has sha256 {sha256_file(path)}, the gate file pins {ref.sha256}")
    return problems


def variant_cfg(gates: Gates, name: str, root: Path = ROOT) -> GameCfg:
    """The game of variant ``name``, from its committed file only (never the partner's local file)."""
    return load_game_cfg(root / gates.games[name].file, local_dir=None, use_local=False)[0]


# ================================================================================================ the plan
@dataclass(frozen=True)
class PlannedGroup:
    """A group with its cells (Guard, Strike) in order, its fixed batches, and the cells left out as duplicates."""
    spec: GroupSpec
    cells: tuple[tuple[str, str], ...]
    batches: tuple[tuple[tuple[str, str], ...], ...]
    skipped: tuple[tuple[str, str], ...]

    def batch_id(self, index: int) -> str:
        return f"{self.spec.name}/b{index:02d}"


def _chunks(cells: tuple, size: int) -> tuple[tuple, ...]:
    return tuple(cells[i:i + size] for i in range(0, len(cells), size))


def build_plan(gates: Gates) -> list[PlannedGroup]:
    """The groups in run order with their cells and batches. At one Strike drone the ``one_strike_duplicates`` cells are
    left out (``skipped``). A same-seed control replays one batch of its group with the same cells."""
    per_batch = int(gates.run["cells_per_batch"])
    duplicates = set(gates.players["one_strike_duplicates"])
    plan: dict[str, PlannedGroup] = {}
    for spec in gates.groups:
        if spec.control == SAME_SEED:
            source = plan[spec.of_group]
            cells = source.batches[spec.of_batch]
            plan[spec.name] = PlannedGroup(spec, cells, (cells,), ())
            continue
        _, strikes = parse_size(spec.size)
        every = tuple((g, s) for g in spec.guards for s in spec.strikes)
        one = strikes == 1
        cells = tuple(c for c in every if not (one and c[1] in duplicates))
        skipped = tuple(c for c in every if c not in cells)
        plan[spec.name] = PlannedGroup(spec, cells, _chunks(cells, per_batch), skipped)
    return list(plan.values())


def group_game(gates: Gates, spec: GroupSpec) -> tuple[str, str]:
    """(game name, team size) a group plays; a same-seed control plays its source group's."""
    if spec.control == SAME_SEED:
        return group_game(gates, gates.group(spec.of_group))
    return spec.game, spec.size


# ================================================================================================ the sweep's game
class SweepGame(SvgGame):
    """``SvgGame`` of ``cells x games_per_cell`` games whose starts are one draw of ``games_per_cell`` games tiled over the
    cells (module docstring). Every game must have the same arena (a fixed-arena game file): checked at construction.
    After ``reset``: ``tags`` [N] long (Strike drones tagged in the slot's first game), ``strikes_left`` [N] long (Strike
    drones in the game when the slot's first game ended), ``team_close_first`` [N] long (start team-mate pairs closer
    than the filter distance in the first game; starts mode zone_disc_ring), ``first_done`` [N] bool."""

    def __init__(self, cfg: GameCfg, cells: int, games_per_cell: int, guards: int, strikes: int, device: str,
                 seed: int, strike_start_dz_m: float = 0):
        self.games_per_cell = games_per_cell
        self.strike_start_dz_m = strike_start_dz_m
        self._start_gen = torch.Generator(device=device)
        self._start_gen.manual_seed(seed)
        self.should_stop: Callable[[], bool] | None = None
        super().__init__(cfg, cells * games_per_cell, guards, strikes, device=device, seed=seed, band=0)
        ar = self.arenas
        for name, value in (("side", ar.side_m), ("zone radius", ar.zone_radius_m), ("zone centre", ar.zone_centre_m)):
            if not bool((value == value[:1]).all()):
                raise ValueError(f"SweepGame needs one fixed arena: the {name} differs between games")

    def _draw_starts(self, arenas: Arenas) -> tuple[Tensor, Tensor]:
        n = self.games_per_cell
        one = Arenas(arenas.side_m[:n], arenas.half_m[:n], arenas.zone_centre_m[:n], arenas.zone_radius_m[:n],
                     arenas.band[:n])
        starts, miss = draw_starts(self.cfg, one, self.guards, self.strikes, self._start_gen, return_miss=True)
        if self.strike_start_dz_m:            # sensitivity groups only; 0 (the default) leaves the draw untouched
            lift = torch.zeros_like(starts)
            lift[:, self.guards:, -1] = self.strike_start_dz_m
            starts = starts + lift
        tiles = self.num_games // n
        return starts.repeat(tiles, 1, 1), miss.repeat(tiles)

    def reset(self, seed: int | None = None) -> dict[str, Tensor]:
        obs = super().reset(seed)
        n, dev = self.num_games, self.device
        self.first_done = torch.zeros(n, dtype=torch.bool, device=dev)
        self.tags = torch.zeros(n, dtype=torch.long, device=dev)
        self.strikes_left = torch.zeros(n, dtype=torch.long, device=dev)
        self.team_close_first = self.start_team_close.clone()
        return obs

    def step(self, actions: dict[str, Tensor]):
        if self.should_stop is not None and self.should_stop():
            raise SweepStopped("stop requested before a tick")
        out = super().step(actions)
        g = self.guards
        first = ~self.first_done
        self.tags = self.tags + first * out.info["tagged"][:, g:].sum(dim=1)
        ended = first & out.done
        self.strikes_left = torch.where(ended, out.info["final_alive"][:, g:].sum(dim=1), self.strikes_left)
        self.first_done = self.first_done | out.done
        return out


def split_players(cells: tuple, team: str, cfg: GameCfg, games_per_cell: int, device: str, seed: int) -> SplitStrategy:
    """One player per cell on its slice of games; seeds as ``scripts/score.py`` (game seed + 101 Guard, + 202 Strike)."""
    column = 0 if team == "guard" else 1
    offset = GUARD_SEED_OFFSET if team == "guard" else STRIKE_SEED_OFFSET
    parts = [(make_strategy(cell[column], team, cfg, games_per_cell, device, seed + offset),
              slice(i * games_per_cell, (i + 1) * games_per_cell)) for i, cell in enumerate(cells)]
    return SplitStrategy(team, parts)


@dataclass
class BatchResult:
    """One batch played. ``per_game``: host arrays [N] (``start_pos_m`` [N, M, 3]); ``rows``: one summary per cell;
    ``start_sha256``: per cell, of its first games' start positions; timing and GPU memory (None on the CPU)."""
    per_game: dict
    rows: list
    start_sha256: list
    seconds: float
    steps_played: int
    games: int
    game_steps_per_s: float
    peak_allocated_bytes: int | None
    peak_reserved_bytes: int | None
    nonfinite_actions: int


def _rate(k: int, n: int) -> tuple[float | None, list | None]:
    if n == 0:
        return None, None
    low, high = wilson_interval(k, n)
    return k / n, [low, high]


def cell_row(per_game: dict, summary: list, cell: tuple, games_per_cell: int) -> dict:
    """The summary of one cell: ``summarise``'s row (hold rate, interval, closest approach, ...) plus reach and
    time-out rates with Wilson 95 % intervals, holds by tagging every Strike drone, tags per game and the start counts."""
    outcome, left = per_game["outcome"], per_game["strikes_left"]
    finished = outcome != RUNNING
    n = int(finished.sum())
    holds, reaches = int((outcome == GUARD_WIN).sum()), int((outcome == STRIKE_WIN).sum())
    timeouts = int(((outcome == GUARD_WIN) & (left > 0)).sum())
    row = dict(summary[0]) if summary else dict.fromkeys(SUMMARY_KEYS)      # no finished game: every summary None
    row.update(guard=cell[0], strike=cell[1], games=n, unfinished=games_per_cell - n, holds=holds, reaches=reaches,
               timeouts=timeouts, eliminations=holds - timeouts)
    for name, k in (("hold", holds), ("reach", reaches), ("timeout", timeouts), ("elimination", holds - timeouts)):
        row[f"{name}_rate"], row[f"{name}_ci"] = _rate(k, n)
    tags = per_game["tags"][finished]
    row["tags_mean"] = float(tags.mean()) if n else None
    row["tags_max"] = int(tags.max()) if n else None
    row["start_miss_games"] = int(per_game["start_miss"].sum())
    close = per_game["start_team_close"]
    row["start_team_close_games"] = int((close > 0).sum())
    row["start_team_close_pairs"] = int(close.sum())
    return row


def _sync(device: str) -> None:
    if str(device).startswith("cuda"):
        torch.cuda.synchronize()


def play_batch(cfg: GameCfg, size: str, cells: tuple, run: dict,
               should_stop: Callable[[], bool] | None = None, strike_start_dz_m: float = 0) -> BatchResult:
    """Play one batch: ``cells`` side by side, ``run["games_per_cell"]`` games each, at most ``run["ticks_cap"]`` ticks
    (``core/play.play_match``), on ``run["device"]`` from ``run["seed"]``. Raises :class:`SweepStopped` when
    ``should_stop`` says yes before a tick. ``strike_start_dz_m``: every Strike drone starts this much higher (sensitivity
    groups; 0 = the game's own starts)."""
    guards, strikes = parse_size(size)
    n, device, seed = int(run["games_per_cell"]), run["device"], int(run["seed"])
    game = SweepGame(cfg, len(cells), n, guards, strikes, device, seed, strike_start_dz_m)
    game.should_stop = should_stop
    guard = split_players(cells, "guard", cfg, n, device, seed)
    strike = split_players(cells, "strike", cfg, n, device, seed)
    cuda = str(device).startswith("cuda")
    if cuda:
        torch.cuda.reset_peak_memory_stats()
    _sync(device)
    started = time.perf_counter()
    res = play_match(game, guard, strike, max_steps=int(run["ticks_cap"]))
    _sync(device)
    seconds = time.perf_counter() - started
    alive_strikes = game.alive[:, guards:].sum(dim=1)
    host = {
        "outcome": res.outcome, "end_step": res.end_step, "tags": game.tags,
        "strikes_left": torch.where(game.first_done, game.strikes_left, alive_strikes),
        "closest_3d_m": res.closest_cross_3d_m, "closest_m": res.closest_cross_m, "start_miss": res.start_miss,
        "start_team_close": game.team_close_first, "nonfinite_actions": res.nonfinite_actions,
        "start_pos_m": res.start_pos_m}
    per_game = {k: v.detach().cpu().numpy() for k, v in host.items()}
    rows, shas = [], []
    for i, cell in enumerate(cells):
        sl = slice(i * n, (i + 1) * n)
        part = {k: v[sl] for k, v in per_game.items()}
        rows.append(cell_row(part, summarise(res.slice(sl), by=()), cell, n))
        shas.append(hashlib.sha256(np.ascontiguousarray(part["start_pos_m"]).tobytes()).hexdigest())
    games = len(cells) * n
    return BatchResult(per_game=per_game, rows=rows, start_sha256=shas, seconds=seconds, steps_played=res.steps_played,
                       games=games, game_steps_per_s=games * res.steps_played / seconds if seconds > 0 else math.inf,
                       peak_allocated_bytes=torch.cuda.max_memory_allocated() if cuda else None,
                       peak_reserved_bytes=torch.cuda.max_memory_reserved() if cuda else None,
                       nonfinite_actions=int(per_game["nonfinite_actions"].sum()))


# ================================================================================================ controls (known answers)
def check_same_seed(a: dict, b: dict, tol_m: float) -> tuple[bool, str]:
    """Same seed twice: every per-game count and the start positions equal; the closest 3-D approach within tol_m
    (an infinity must equal an infinity)."""
    for key in PER_GAME_EXACT:
        if not np.array_equal(a[key], b[key]):
            return False, f"{key} differs in {int(np.sum(np.asarray(a[key]) != np.asarray(b[key])))} entries"
    x, y = np.asarray(a["closest_3d_m"], dtype=float), np.asarray(b["closest_3d_m"], dtype=float)
    same = (x == y) | (np.abs(x - y) <= tol_m)
    if not same.all():
        return False, f"closest 3-D approach differs by up to {float(np.nanmax(np.abs(x - y)[~same])):.3g} m (tolerance {tol_m})"
    return True, f"{len(x)} games equal"


def check_zero_tags(per_game: dict) -> tuple[bool, str]:
    tags = int(np.sum(per_game["tags"]))
    return tags == 0, f"{tags} tags in {len(per_game['tags'])} games"


def check_never_reaches(per_game: dict) -> tuple[bool, str]:
    reaches = int(np.sum(np.asarray(per_game["outcome"]) == STRIKE_WIN))
    return reaches == 0, f"{reaches} reaches in {len(per_game['outcome'])} games"


def check_tags_bound(per_game: dict, guards: int, strikes: int, survive_prob: float) -> tuple[bool, str]:
    """Tags per game <= min(G, S) when a tagged Guard drone always leaves (probability 0), else <= S."""
    bound = min(guards, strikes) if survive_prob == 0 else strikes
    most = int(np.max(per_game["tags"])) if len(per_game["tags"]) else 0
    return most <= bound, f"most tags in a game {most}, bound {bound}"


def check_paired_starts(shas_by_setting: dict) -> tuple[bool, str]:
    """``shas_by_setting``: start setting -> the set of start sha256 its cells had. Paired: one per setting."""
    bad = {str(k): len(v) for k, v in shas_by_setting.items() if len(v) != 1}
    return not bad, (f"settings with more than one set of starts: {bad}" if bad
                     else f"{len(shas_by_setting)} start setting(s), one set of starts each")


# ================================================================================================ the shortlist rule
def _maximin(rows: list[dict], rate: str, ci: str, keep: str, over: str, order: list[str]) -> tuple[float, str]:
    """max over ``keep`` of min over ``over`` of rows[rate]; ties to the higher worst Wilson lower bound, then ``order``."""
    best = None
    for name in order:
        mine = [r for r in rows if r[keep] == name]
        if not mine:
            continue
        worst = min(r[rate] for r in mine)
        worst_low = min(r[ci][0] for r in mine)
        key = (worst, worst_low, -order.index(name))
        if best is None or key > best[0]:
            best = (key, name)
    return best[0][0], best[1]


def _variant(name: str, rows: list[dict], meta: dict, rule: dict, expected: int | None) -> dict:
    guards = list(dict.fromkeys(r["guard"] for r in rows))
    strikes = list(dict.fromkeys(r["strike"] for r in rows))
    out = {"variant": name, "cells": len(rows), **{k: meta[k] for k in meta if k != "name"}}
    complete = bool(rows) and all(r.get("hold_rate") is not None and r.get("reach_rate") is not None for r in rows)
    if expected is not None and len(rows) != expected:
        complete = False
    if not complete:
        return {**out, "H": None, "R": None, "d": None, "g_star": None, "s_star": None, "eligible": False,
                "reason": "not every cell was played"}
    h, g_star = _maximin(rows, "hold_rate", "hold_ci", "guard", "strike", guards)
    r, s_star = _maximin(rows, "reach_rate", "reach_ci", "strike", "guard", strikes)
    d = min(1 - h, 1 - r)
    trivial = rule["trivial_at"]
    reason = ("Guard-trivial looking: a scripted Guard holds against every scripted Strike" if h >= trivial else
              "Strike-trivial looking: a scripted Strike reaches against every scripted Guard" if r >= trivial else
              "eligible")
    return {**out, "H": h, "R": r, "d": d, "g_star": g_star, "s_star": s_star, "eligible": reason == "eligible",
            "reason": reason}


def _tie_key(v: dict, breaks: list[str], order: list[str]) -> tuple:
    key = []
    for name in breaks:
        if name == "lab_arena_first":
            key.append(v["arena_side_m"])
        elif name == "larger_zone_tag_margin":
            key.append(-abs(v["zone_radius_m"] - v["tag_radius_m"]))
        elif name == "lower_guard_survives":
            key.append(v["survive"])
        elif name == "run_order":
            key.append(order.index(v["variant"]))
        else:
            raise ValueError(f"unknown tie-break {name!r}")
    return tuple(key)


def shortlist(rows_by_group: dict, metas: dict, rule: dict, run_order: list[str],
              expected_cells: dict | None = None, exclude_strikes: tuple = ()) -> dict:
    """The gate file's shortlist rule (configs/ste_l011/gates.toml [shortlist]) on the cell rows of each group: the
    ``always`` variants first (references, flagged ``reference``), then at most ``max_variants - len(always)`` more.
    ``metas``: per group, its realised arena side, zone radius, tag radius and survive probability. Returns
    {"variants": [one dict per candidate], "shortlist": [names], "report_only": [one dict per report-only group]}."""
    def rows_of(name):
        return [r for r in rows_by_group.get(name, []) if r["strike"] not in exclude_strikes]

    def expected(name):
        """Cells the plan holds for ``name`` (a count, or the planned (Guard, Strike) cells, less excluded Strikes)."""
        if expected_cells is None or name not in expected_cells:
            return None
        planned = expected_cells[name]
        return planned if isinstance(planned, int) else len([c for c in planned if c[1] not in exclude_strikes])

    variants = [_variant(n, rows_of(n), metas[n], rule, expected(n)) for n in rule["candidates"] if n in metas]
    report = [_variant(n, rows_of(n), metas[n], rule, expected(n)) for n in rule["report_only"] if n in metas]
    always = [v for v in variants if v["variant"] in rule["always"]]
    for v in always:                       # the reference: carried whatever the rule says (LEAD CALL 21 Nov 2026)
        v["reference"] = True
        v["reason"] = "reference (eligible)" if v["eligible"] else f"reference, ruled out because {v['reason']}"
    eligible = sorted((v for v in variants if v["eligible"] and v["variant"] not in rule["always"]),
                      key=lambda v: -v["d"])
    ordered = []
    while eligible:
        top = eligible[0]["d"]
        cluster = [v for v in eligible if top - v["d"] < rule["tie_window"]]
        cluster.sort(key=lambda v: _tie_key(v, rule["tie_breaks"], run_order))
        ordered += cluster
        eligible = [v for v in eligible if v not in cluster]
    for rank, v in enumerate(ordered):
        v["rank"] = rank + 1
    added = ordered[:rule["max_variants"] - len(always)]
    return {"variants": variants, "shortlist": [v["variant"] for v in always + added],
            "report_only": report, "excluded_strikes": list(exclude_strikes)}
