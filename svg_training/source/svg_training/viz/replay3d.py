"""VID-1 part 2: the data path of the 3-D replay of tier-1 games (CPU or CUDA; no Isaac here).

A tier-1 game keeps no trajectory: the L0.11 run folder holds per-game numbers and the start positions only. So a key
game is **played again**: :func:`capture_batch` re-plays one L0.11 batch exactly as ``ste/sweep.play_batch`` plays it
(the same ``SweepGame``, the same paired starts, the same players and seeds, the same batch-mates, because the safety
filter's early stop is batch-wide) and keeps every step of the chosen games. :func:`check_against_record` then compares
the re-played per-game numbers (outcome, end step, tags, Strike drones left, start positions exactly; the closest 3-D
and horizontal approach within a tolerance, as the sweep's same-seed control) with the run's stored cell file; a game is
drawn only if they agree, so the game drawn is the game in the record.

A :class:`Trajectory` is what the renderer needs: positions, yaw and who is in the game at every 0.05 s tick, the arena
and the result. Tier 1 has no roll or pitch: the renderer draws the drones level. Then the cameras (top view, 3-D view),
the playback maths and the burnt-in texts.

Offline tooling: it reads the game state once per step on the device (an index, a clone), never inside the game's own
step; nothing here changes the game. Shapes: N games, M drones (Guard drones first), T ticks.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import torch

from ..bench.overlay import FRAME_BOX, HFOV_DEG, camera_pose, project
from ..core.game_config import TICK_S, GameCfg
from ..core.play import play_match
from ..core.rewards import GUARD_WIN, STRIKE_WIN
from ..ste import exploit, sweep

EXACT_KEYS = ("outcome", "end_step", "tags", "strikes_left", "start_pos_m")   # sweep.PER_GAME_EXACT
CLOSE_KEYS = ("closest_3d_m", "closest_m")    # equal within the gate file's same_seed_closest_tol_m (0 on the CPU)
OUTCOME_CODES = {"hold": GUARD_WIN, "reach": STRIKE_WIN}
PARK_LIMIT_M = 100.0          # a coordinate beyond this is a parked drone (the game parks drones that are out at 1 km)


@dataclass
class Trajectory:
    """One game, step by step. pos_m [T+1, M, 3] (frame 0 = the start, frame k = after k ticks; a drone that is out
    keeps the last place it was in the game), yaw_rad [T+1, M], alive [T+1, M] bool; the arena square is
    [-half_m, half_m]^2 around the origin (walls stop the drones at half_m - wall_margin_m); zone_centre_m [2];
    outcome 1 reach (Strike team) or 2 hold (Guard team); end_step = T; meta: where the game comes from."""
    pos_m: np.ndarray
    yaw_rad: np.ndarray
    alive: np.ndarray
    guards: int
    strikes: int
    half_m: float
    wall_margin_m: float
    height_band_m: tuple
    zone_centre_m: np.ndarray
    zone_radius_m: float
    tag_radius_m: float
    outcome: int
    end_step: int
    meta: dict = field(default_factory=dict)

    @property
    def end_time_s(self) -> float:
        return self.end_step * TICK_S


_SCALARS = ("guards", "strikes", "half_m", "wall_margin_m", "height_band_m", "zone_radius_m", "tag_radius_m", "outcome",
            "end_step")


def save_trajectory(stem: str | Path, t: Trajectory) -> Path:
    """Arrays to <stem>.npz, the rest to <stem>.json. Returns the .npz path."""
    stem = Path(stem)
    stem.parent.mkdir(parents=True, exist_ok=True)
    npz = stem.with_suffix(".npz")
    np.savez_compressed(npz, pos_m=t.pos_m, yaw_rad=t.yaw_rad, alive=t.alive, zone_centre_m=t.zone_centre_m)
    head = {k: getattr(t, k) for k in _SCALARS}
    head["height_band_m"] = list(t.height_band_m)
    stem.with_suffix(".json").write_text(json.dumps({**head, "meta": t.meta}, indent=1))
    return npz


def load_trajectory(path: str | Path) -> Trajectory:
    """Read a trajectory written by save_trajectory; ValueError names a field with a wrong shape."""
    path = Path(path).with_suffix(".npz")
    head = json.loads(path.with_suffix(".json").read_text())
    with np.load(path) as d:
        arrays = {k: d[k] for k in ("pos_m", "yaw_rad", "alive", "zone_centre_m")}
    m = head["guards"] + head["strikes"]
    frames = head["end_step"] + 1
    want = {"pos_m": (frames, m, 3), "yaw_rad": (frames, m), "alive": (frames, m), "zone_centre_m": (2,)}
    for k, shape in want.items():
        if arrays[k].shape != shape:
            raise ValueError(f"{path.name}: {k} has shape {arrays[k].shape}, expected {shape}")
    head["height_band_m"] = tuple(head["height_band_m"])
    return Trajectory(**arrays, **{k: head[k] for k in _SCALARS}, meta=head["meta"])


# ------------------------------------------------------------------------------------------------ capture
class _CaptureMixin:
    """Keeps, after every step and before the auto-reset, the positions, yaw and alive flags of the games ``keep``
    (global game indices). Frame 0 is taken right after reset. Mixed into a sweep or evaluation game class."""

    def __init__(self, *args, keep: list[int], **kw) -> None:
        self._cap = None
        self._keep_list = list(keep)          # SvgGame.__init__ may reset: the index tensor is made on first use
        self._keep = None
        super().__init__(*args, **kw)

    def reset(self, seed: int | None = None):
        obs = super().reset(seed)
        self._cap = [self._snap()]
        return obs

    def _snap(self):
        if self._keep is None:
            self._keep = torch.as_tensor(self._keep_list, dtype=torch.long, device=self.pos_m.device)
        k = self._keep
        return self.pos_m[k].clone(), self.yaw[k].clone(), self.alive[k].clone()

    def _new_games(self, mask) -> None:
        if self._cap is not None:
            self._cap.append(self._snap())
        super()._new_games(mask)


class _CaptureGame(_CaptureMixin, sweep.SweepGame):
    """The L0.11 sweep's game, capturing (``sweep.play_batch``)."""


class _CaptureFixedGame(_CaptureMixin, exploit.FixedStartsGame):
    """The L0.12 evaluation game on T44's starts, capturing (``exploit.play_cells``)."""


@dataclass
class Capture:
    """per_game: host arrays [N] of EXACT_KEYS and CLOSE_KEYS (start_pos_m [N, M, 3]); trajectories: one per kept game,
    in order."""
    per_game: dict
    trajectories: list


def _refuse_surviving_guard(cfg: GameCfg) -> None:
    if cfg.tag.guard_survives_tag_prob != 0:
        raise ValueError(f"tag.guard_survives_tag_prob is {cfg.tag.guard_survives_tag_prob}: the replay assumes "
                         f"one-for-one tags (0)")


def _collect(game, res, cfg: GameCfg, guards: int, strikes: int, keep: list[int], ticks_cap: int,
             batch_games: int) -> Capture:
    """Per-game numbers (as play_batch / play_cells report them) and one Trajectory per kept game."""
    alive_strikes = game.alive[:, guards:].sum(dim=1)
    host = {"outcome": res.outcome, "end_step": res.end_step, "tags": game.tags,
            "strikes_left": torch.where(game.first_done, game.strikes_left, alive_strikes),
            "start_pos_m": res.start_pos_m, "closest_3d_m": res.closest_cross_3d_m, "closest_m": res.closest_cross_m}
    per_game = {k: v.detach().cpu().numpy() for k, v in host.items()}
    pos = torch.stack([c[0] for c in game._cap]).cpu().numpy()          # [S+1, K, M, 3]
    yaw = torch.stack([c[1] for c in game._cap]).cpu().numpy()
    alive = torch.stack([c[2] for c in game._cap]).cpu().numpy()
    ar = game.arenas
    trajs = []
    for k, g in enumerate(keep):
        end = int(per_game["end_step"][g])
        if end == 0:
            raise RuntimeError(f"game {g} did not finish within {ticks_cap} ticks")
        p, a = pos[: end + 1, k].copy(), alive[: end + 1, k].copy()
        for m in range(p.shape[1]):                     # a drone that is out: shown where it was last in the game
            last = p[0, m].copy()
            for f in range(end + 1):
                if a[f, m] and np.abs(p[f, m, :2]).max() < PARK_LIMIT_M:
                    last = p[f, m].copy()
                else:
                    p[f, m] = last
        trajs.append(Trajectory(
            pos_m=p.astype(np.float32), yaw_rad=yaw[: end + 1, k].astype(np.float32), alive=a.astype(bool),
            guards=guards, strikes=strikes, half_m=float(ar.half_m[g]), wall_margin_m=float(cfg.arena.wall_margin_m),
            height_band_m=tuple(float(v) for v in cfg.arena.height_band_m),
            zone_centre_m=ar.zone_centre_m[g].detach().cpu().numpy().astype(np.float64),
            zone_radius_m=float(ar.zone_radius_m[g]), tag_radius_m=float(cfg.tag.radius_m),
            outcome=int(per_game["outcome"][g]), end_step=end,
            meta={"global_index": int(g), "batch_games": int(batch_games)}))
    return Capture(per_game, trajs)


def capture_batch(cfg: GameCfg, size: str, cells: tuple, run: dict, keep: list[int],
                  strike_start_dz_m: float = 0) -> Capture:
    """Play one batch as ``sweep.play_batch`` does (same game, players, seeds, step cap, Strike start offset) and keep
    every step of the games ``keep`` (global indices: cell index x games per cell + game index). Refuses a game where a
    tagged Guard may survive: the replay's banner and crosses assume one-for-one tags."""
    _refuse_surviving_guard(cfg)
    guards, strikes = sweep.parse_size(size)
    n, device, seed = int(run["games_per_cell"]), run["device"], int(run["seed"])
    game = _CaptureGame(cfg, len(cells), n, guards, strikes, device, seed, strike_start_dz_m, keep=list(keep))
    guard = sweep.split_players(cells, "guard", cfg, n, device, seed)
    strike = sweep.split_players(cells, "strike", cfg, n, device, seed)
    res = play_match(game, guard, strike, max_steps=int(run["ticks_cap"]))
    return _collect(game, res, cfg, guards, strikes, keep, int(run["ticks_cap"]), len(cells) * n)


def capture_trained(cfg: GameCfg, size: str, ref, cells: list, n: int, device: str, seed: int, ticks_cap: int,
                    learner, hold_ticks: int, keep: list[int]) -> Capture:
    """Play an L0.12 evaluation batch as ``exploit.play_cells`` does (T44's first ``n`` starts, the same cells, the
    learner behind every exploiter cell held ``hold_ticks`` ticks, mean actions) and keep every step of the games
    ``keep``. Refuses a game where a tagged Guard may survive."""
    _refuse_surviving_guard(cfg)
    guards, strikes = sweep.parse_size(size)
    starts = torch.as_tensor(ref.starts_m[:n])
    miss = torch.as_tensor(ref.start_miss[:n])
    game = _CaptureFixedGame(cfg, len(cells), starts, miss, guards, strikes, device, seed, keep=list(keep))
    g = exploit._team_split(cells, "guard", cfg, n, device, seed, learner, hold_ticks)
    s = exploit._team_split(cells, "strike", cfg, n, device, seed, learner, hold_ticks)
    res = play_match(game, g, s, max_steps=int(ticks_cap))
    return _collect(game, res, cfg, guards, strikes, keep, int(ticks_cap), len(cells) * n)


def check_against_record(per_game: dict, record: dict, keys: tuple = EXACT_KEYS, tol_m: float = 0.0) -> dict:
    """Every key of every game equal (start positions bit for bit), and the CLOSE_KEYS present in both within tol_m
    (an infinity must equal an infinity; sweep.check_same_seed's rule)? {"equal", "mismatches": {key: games differing}}."""
    mism = {}
    for k in keys:
        a, b = np.asarray(per_game[k]), np.asarray(record[k])
        if a.shape != b.shape:
            mism[k] = int(max(a.shape[0], b.shape[0]))
            continue
        diff = a != b
        mism[k] = int(diff.reshape(diff.shape[0], -1).any(axis=1).sum()) if diff.ndim > 1 else int(diff.sum())
    for k in CLOSE_KEYS:
        if k in per_game and k in record:
            x, y = np.asarray(per_game[k], float), np.asarray(record[k], float)
            if x.shape != y.shape:
                mism[k] = int(max(x.shape[0], y.shape[0]))
                continue
            with np.errstate(invalid="ignore"):
                same = (x == y) | (np.abs(x - y) <= tol_m)
            mism[k] = int((~same).sum())
    return {"equal": all(v == 0 for v in mism.values()), "mismatches": mism}


def pick_key_games(outcome_cell: np.ndarray, outcomes: list[str]) -> dict:
    """The rule fixed before the replay (configs/ste_video.toml [key_games]): per outcome name, the lowest game index of
    the cell that ended that way (None if none did)."""
    out = {}
    for name in outcomes:
        if name not in OUTCOME_CODES:
            raise ValueError(f"outcome must be one of {sorted(OUTCOME_CODES)}, got {name!r}")
        hit = np.flatnonzero(np.asarray(outcome_cell) == OUTCOME_CODES[name])
        out[name] = int(hit[0]) if hit.size else None
    return out


def find_cell(gates: sweep.Gates, plan: list, group: str, cell: tuple) -> tuple[str, tuple, int]:
    """(batch id, the batch's cells, the cell's index in it) of a cell of a group of the gate file's plan."""
    cell = tuple(cell)
    for pg in plan:
        if pg.spec.name != group:
            continue
        for b, cells in enumerate(pg.batches):
            cells = tuple(tuple(c) for c in cells)
            if cell in cells:
                return pg.batch_id(b), cells, cells.index(cell)
    raise KeyError(f"no cell {cell} in group {group!r}")


# ------------------------------------------------------------------------------------------------ cameras
def _fits(points: np.ndarray, eye, look) -> bool:
    p = project(points, eye, look)
    return bool(np.isfinite(p).all() and FRAME_BOX["x"][0] <= p[:, 0].min() and p[:, 0].max() <= FRAME_BOX["x"][1]
                and FRAME_BOX["y"][0] <= p[:, 1].min() and p[:, 1].max() <= FRAME_BOX["y"][1])


def arena_outline_m(half_m: float, top_m: float, wall_margin_m: float) -> np.ndarray:
    """[8, 3] points a camera must see: the arena floor's corners (+-half_m, z 0) and the top rails' corners
    (+-(half_m - wall_margin_m), z top_m; compat spawn_display_arena)."""
    lim = half_m - wall_margin_m
    return np.array([[sx * h, sy * h, z] for h, z in ((half_m, 0.0), (lim, top_m)) for sx in (-1, 1) for sy in (-1, 1)])


def top_view_pose(half_m: float, top_m: float, tilt_deg: float, origin_m=(0.0, 0.0, 0.0),
                  wall_margin_m: float = 0.0) -> tuple[tuple, tuple]:
    """Camera above the arena, leaning tilt_deg off vertical towards the south (so north, +y, is at the top of the
    image), as close as it can while the arena outline (arena_outline_m) stays inside FRAME_BOX; the aim point is
    moved north or south (up to 0.3 half sides) to the place that lets the camera come closest."""
    if tilt_deg <= 0:
        raise ValueError("tilt_deg must be > 0: a z-up look-at cannot point straight down")
    t = np.radians(tilt_deg)
    back = np.array([0.0, -np.sin(t), np.cos(t)])
    o = np.asarray(origin_m, float)
    pts = arena_outline_m(half_m, top_m, wall_margin_m) + o

    def closest(look: np.ndarray) -> float:
        lo, hi = 0.5, 400.0
        for _ in range(60):
            d = 0.5 * (lo + hi)
            lo, hi = (lo, d) if _fits(pts, look + d * back, look) else (d, hi)
        return hi

    looks = [o + np.array([0.0, k * half_m, 0.0]) for k in np.linspace(-0.3, 0.3, 25)]
    dists = [closest(lk) for lk in looks]
    i = int(np.argmin(dists))
    eye = looks[i] + dists[i] * back
    return tuple(float(v) for v in eye), tuple(float(v) for v in looks[i])


def camera_poses(half_m: float, top_m: float, tilt_deg: float, perspective_view: str,
                 origin_m=(0.0, 0.0, 0.0), wall_margin_m: float = 0.0) -> list[tuple[tuple, tuple]]:
    """[(eye, lookat) of the top view, (eye, lookat) of the 3-D view (bench/overlay.camera_pose, the S2b clip view)]."""
    return [top_view_pose(half_m, top_m, tilt_deg, origin_m, wall_margin_m),
            camera_pose(half_m, origin_m, view=perspective_view, top_m=top_m)]


def to_pixels(points_m: np.ndarray, eye, look, resolution: tuple[int, int], hfov_deg: float = HFOV_DEG) -> np.ndarray:
    """World points [P, 3] to pixel coordinates [P, 2] (x right, y down) in an image of resolution (width, height)."""
    w, h = resolution
    p = project(points_m, eye, look, aspect=w / h, hfov_deg=hfov_deg)
    return np.stack(((p[:, 0] + 1) * w / 2, (1 - p[:, 1]) * h / 2), axis=-1)


# ------------------------------------------------------------------------------------------------ playback, texts
def playback_fps(speed_x: float) -> int:
    """Frames per second when every 0.05 s tick is one frame, played at speed_x times real time."""
    fps = speed_x / TICK_S
    if abs(fps - round(fps)) > 1e-9 or round(fps) < 1:
        raise ValueError(f"speed {speed_x} x real time is not a whole number of frames per second ({fps})")
    return int(round(fps))


def hold_frames(hold_s: float, fps: int) -> int:
    return int(round(hold_s * fps))


def outcome_text(outcome: int, end_step: int, tags: int, guards_left: int) -> str:
    """The result banner (short: it sits between the legend and the clock). A hold in these games is a trade (T44): say
    how many tags each way and what is left."""
    t = end_step * TICK_S
    if outcome == STRIKE_WIN:
        return f"Strike team reaches the zone at {t:.1f} s"
    if outcome == GUARD_WIN:
        left = "no Guard left" if guards_left == 0 else f"{guards_left} Guard{'s' if guards_left != 1 else ''} left"
        return f"Guard team holds: {tags}-for-{tags} tags, {left}"     # the clock shows the time
    return "the game had not ended"


def tagged_marks(pos_m: np.ndarray, alive: np.ndarray, k: int) -> list[tuple[int, np.ndarray]]:
    """[(drone, place)] of every drone out of the game at frame k (pos_m [T+1, M, 3] holds its last in-game place)."""
    return [(m, pos_m[k, m]) for m in range(alive.shape[1]) if not alive[k, m]]


def cell_counts(outcome_cell: np.ndarray) -> dict:
    o = np.asarray(outcome_cell)
    return {"games": int(o.size), "holds": int((o == GUARD_WIN).sum()), "reaches": int((o == STRIKE_WIN).sum())}


def caption(variant: str, speed_x: float, source: str = "the L0.11 screen") -> str:
    """The burnt-in caption (<= 400 characters). source: where the game comes from ("the L0.11 screen", "the L0.12
    evaluation, trained Strike team")."""
    return (f"Training simulator: a tier-1 game of {source} ({variant}) replayed in Isaac Lab for drawing only, "
            f"drones drawn level; {speed_x:g}x real time; not a flight")


def _short(spec: str) -> str:
    return spec.replace("guard_", "").replace("strike_", "").replace("_", " ")


def info_line(variant: str, guards: int, strikes: int, guard_spec: str, strike_spec: str, game_index: int,
              side_m: float) -> str:
    return (f"{variant} | {guards} Guard v {strikes} Strike | Guard: {_short(guard_spec)}, Strike: {_short(strike_spec)}"
            f" | game {game_index} | arena {side_m:g} m")
