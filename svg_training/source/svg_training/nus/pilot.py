"""Phase 5 pilots (plan docs/plans/2026-11-18-nus-phase5-retraining.md section 7; Tasks P-T3 to P-T5): the NUS hangar game for the
stand-in trainer (``scripts/train_standin.py --game nus_hangar --settings pilot_p1 ...``), the hard wall-clock cap, the pilots' GPU-hours
ledger, and the pilot videos. Not gated: every pilot is an INFO record.

* World: Phase 4 row 5 (``[pilots] row``; fitted Starling layer, all-pairs safety filter, 3-D, start-height jitter) from the local files
  through the ``nus/`` loaders; the pilot table's ``shaping_weight``; team sizes from the rules file.
* Training game: ``NusHangarTrainGame`` (fresh starts per game, run seed). Evaluation games: ``NusHangarGame`` on the first games of the
  Phase 4 paired starts file (row 5 scoring starts), one per evaluation size, keeping ``[pilots] video_slots`` games for videos.
* Opponents: the table's ``opponent_mix`` (``nus/players.py`` names, ``opponents.scripted`` names or ``module:Class``), in equal game blocks.
* Cap: ``effective_cap_s`` = the table's ``gpu_cap_hours``, but never more than what the pilots' total (``[pilots] total_gpu_hours``) leaves
  after the hours already in the ledger; a run that cannot fit one evaluation is refused; during training it stops at the first update after
  which the time so far plus the reserve (the evaluations still due and one more update) would pass the cap (``must_stop``). There is no
  ``--accept-long`` for a pilot.
* Ledger: one line per run appended to ``[pilots] gpu_hours_log`` (name, start, end, hours of the process holding the GPU).
* Videos (STANDARDS section 8): one game per evaluation, two for the final and the best evaluation, top-down, through the Phase 4 clip path
  (``ladder.video_clips``, ``ladder.clip_recording``, ``viz.replay.render_replay``), into the run folder's ``videos/``.

No numeric literal (G2): counts and hours come from ``configs/nus_phase5.toml``, lengths and speeds from the local files.
"""
from __future__ import annotations

import datetime
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import torch

from ..core.game_config import TICK_S, GameCfg, load_game_cfg
from ..core.strategy import SplitStrategy
from . import hangar as H
from . import ladder
from . import players
from . import strategy as strategy_module
from .deploy import apply_overrides, load_deploy
from .hangar import Geometry
from .hangar_game import NusHangarGame
from .players import make_player
from .rules import ROOT, NusRules, file_sha256, load_rules
from .train_game import NusHangarTrainGame

PHASE5_CONFIG = ROOT / "configs" / "nus_phase5.toml"
PILOT_TABLES = ("pilot_p1", "pilot_p2", "pilot_p3_guard", "pilot_p3_strike")
TEAMS = ("guard", "strike")
HOUR_S = datetime.timedelta(hours=1).total_seconds()
LOG_HEADER = ("# Phase 5 pilots P0-P3: wall-clock hours holding the RTX 5090 (plan section 7). One line per run.\n"
              "# name  start  end  hours\n")


def load_pilots(path: Path | str = PHASE5_CONFIG) -> dict[str, Any]:
    """The ``[pilots]`` table of ``configs/nus_phase5.toml``."""
    return tomllib.loads(Path(path).read_text())["pilots"]


GPU_HOURS_LOG = ROOT / load_pilots()["gpu_hours_log"]


# ------------------------------------------------------------------------------------------------ the ledger and the cap
def logged_hours(path: Path | str) -> float:
    """Sum of the hours column (the last field before any ``#`` note) of every non-comment line; 0 when the file does not exist."""
    p = Path(path)
    if not p.exists():
        return 0.0
    rows = [ln.split("#")[0].split() for ln in p.read_text().splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
    return sum(float(r[-1]) for r in rows if r)


def _iso(ts: float) -> str:
    return datetime.datetime.fromtimestamp(ts).astimezone().isoformat(timespec="seconds")


def append_gpu_hours(path: Path | str, name: str, start_ts: float, end_ts: float, note: str = "") -> None:
    """Append one line ``name start end hours [# note]`` (start and end are Unix times; ISO 8601 local time in the file)."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        p.write_text(LOG_HEADER)
    line = f"{name}  {_iso(start_ts)}  {_iso(end_ts)}  {(end_ts - start_ts) / HOUR_S:.3f}" + (f"   # {note}" if note else "")
    with p.open("a") as f:
        f.write(line + "\n")


def effective_cap_s(table_cap_h: float, total_h: float, logged_h: float) -> float:
    """The run's hard cap in seconds: its table cap, never more than the pilots' total minus the hours already logged."""
    return min(float(table_cap_h), float(total_h) - float(logged_h)) * HOUR_S


def mid_point_s(cap_s: float, eval_s: float, planned_evaluations: int) -> float:
    """Training time (s) at which the half-way evaluation runs: half of what the cap leaves after the planned evaluations."""
    return max(cap_s - eval_s * planned_evaluations, 0.0) / 2


def must_stop(elapsed_s: float, reserve_s: float, cap_s: float) -> bool:
    """True when the time so far plus the reserve (evaluations still due, one more update) would pass the cap."""
    return elapsed_s + reserve_s > cap_s


# ------------------------------------------------------------------------------------------------ the world and the games
@dataclass
class PilotWorld:
    """Everything a pilot needs from the local files and the committed settings."""
    cfg: GameCfg
    geo: Geometry
    row: dict
    rules: NusRules
    guards: int
    strikes: int
    jitter_m: float
    video: dict
    game_file: Path
    game_sha256: str
    local_sha256: dict = field(default_factory=dict)


def pilot_world(shaping_weight: float) -> PilotWorld:
    """Row ``[pilots] row`` of ``configs/nus_phase4.toml`` with the pilot table's shaping weight. Local files read at call time."""
    settings, pilots = H.load_phase4(), load_pilots()
    base, _ = load_game_cfg(H.HANGAR_GAME, use_local=False)
    deploy = load_deploy(strategy_module.DEPLOY_PATH)
    rules = apply_overrides(load_rules(strategy_module.RULES_PATH), deploy)
    hangar = H.load_hangar(H.LOCAL_HANGAR)
    row = {r["id"]: r for r in settings["row"]}[pilots["row"]]
    H.check_row(row)
    cfg = H.hangar_cfg(base, rules, deploy, hangar, row).replace(**{"rewards.shaping_weight": float(shaping_weight)})
    sha = {"rules": file_sha256(strategy_module.RULES_PATH), "deploy_w2": file_sha256(strategy_module.DEPLOY_PATH),
           "hangar": file_sha256(H.LOCAL_HANGAR)}
    if players.DEPLOY_REF.exists():
        sha["deploy_ref"] = file_sha256(players.DEPLOY_REF)
    if ladder.STARTS_FILE.exists():
        sha["starts"] = file_sha256(ladder.STARTS_FILE)
    return PilotWorld(cfg, H.geometry(rules, deploy, hangar, base), row, rules, rules.guard_count, rules.strike_count,
                      float(settings["ladder"]["jitter_m"]), dict(settings["video"]), Path(H.HANGAR_GAME), file_sha256(H.HANGAR_GAME), sha)


def pilot_games(world: PilotWorld, num_games: int, eval_sizes: list[int], device: str, seed: int, eval_seed: int
                ) -> tuple[NusHangarTrainGame, dict[int, NusHangarGame]]:
    """The training game (fresh starts, run seed) and one evaluation game per size (the first games of the Phase 4 paired starts file;
    the first ``[pilots] video_slots`` games keep their positions for videos)."""
    starts = ladder.load_starts()
    have = int(starts["starts_units"].shape[0])
    if max(eval_sizes) > have:
        raise ValueError(f"an evaluation of {max(eval_sizes)} games needs that many paired starts; the starts file holds {have}")
    slots = int(load_pilots()["video_slots"])
    evals = {size: NusHangarGame(world.cfg, world.geo, world.row, starts["starts_units"][:size], starts["jitter_m"][:size], world.guards,
                                 world.strikes, device=device, seed=eval_seed, video_slots=min(slots, size), rules=world.rules)
             for size in sorted(set(eval_sizes))}
    train = NusHangarTrainGame(world.cfg, world.geo, world.row, world.rules, world.guards, world.strikes, num_games, device=device, seed=seed,
                               jitter_m=world.jitter_m)
    return train, evals


def mix_strategy(parts: list[tuple[str, slice]], team: str, cfg: GameCfg, device: str, seed: int) -> SplitStrategy:
    """The opponent team as equal game blocks: ``parts`` = [(player name, game slice)] (``mix_slices``); one player per block, seeded
    ``seed + block index``."""
    return SplitStrategy(team, [(make_player(name, team, cfg, s.stop - s.start, device, seed + j), s) for j, (name, s) in enumerate(parts)])


# ------------------------------------------------------------------------------------------------ videos
def eval_clips(res, extras: dict, world: PilotWorld) -> list[dict[str, Any]]:
    """The kept slots' clips of one evaluation, host tensors: the first Strike win and the first hold (``ladder.video_clips``), then, when
    fewer than ``[pilots] videos_final_best`` games finished (an evaluation cut short by its step limit), the first unused slots as
    "unfinished" clips up to the steps played."""
    if "video" not in extras:
        return []
    pilots = load_pilots()
    slots = min(int(pilots["video_slots"]), int(extras["video"].shape[1]))
    clips = ladder.video_clips(res, extras, world.geo, slots, False, world.geo.height_m)
    used = {c["slot"] for c in clips}
    spare = [k for k in range(slots) if k not in used][:max(int(pilots["videos_final_best"]) - len(clips), 0)]
    steps = int(res.steps_played)
    clips += [{"slot": k, "kind": "unfinished", "outcome": int(res.outcome[k]), "end_step": steps,
               "closest_cross_m": float(res.closest_cross_m[k]), "pos_m": extras["video"][: steps + 1, k].clone()} for k in spare]
    return clips


def render_clips(clips: list[dict[str, Any]], folder: Path, label: str, count: int, world: PilotWorld, guard_name: str, strike_name: str,
                 seed: int) -> list[Path]:
    """Render the first ``count`` clips to ``folder / <label>_<kind>_slot<k>.mp4`` (top-down, Phase 4's video settings)."""
    from ..viz.replay import render_replay
    v = world.video
    out = []
    for clip in clips[:count]:
        rec = ladder.clip_recording(clip, world.geo, world.guards, world.strikes, guard_name, strike_name, label, seed)
        path = Path(folder) / f"{label}_{clip['kind']}_slot{clip['slot']}.mp4"
        out.append(render_replay(rec, path, speed=v["speed"], fps=v["fps"], dpi=v["dpi"],
                                 playback_label=f"{v['speed'] * v['fps'] * TICK_S:g}x real time"))
    return out


def free_gpu_cache() -> None:
    """Return the caching allocator's free blocks before the CPU-only video rendering."""
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
