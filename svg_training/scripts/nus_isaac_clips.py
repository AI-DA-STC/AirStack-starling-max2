#!/usr/bin/env python3
"""Isaac Lab camera clips of the Phase 4 players (training simulator, tier 2), for people. Presentation only: no gates, no record, no ledger row.

    # one matchup of configs/nus_isaac_clips.toml per launch; host, headless, cameras on (scripts/isaac_preflight.sh --approved-headless first)
    cd <svg_training>; unset PYTHONPATH; PYTHONPATH=source ~/miniconda3/envs/env_isaaclab/bin/python scripts/nus_isaac_clips.py \\
        --headless --enable_cameras --clip g19_vs_s20
    ... scripts/nus_isaac_clips.py --list                       # the clips and their players (CPU, no Isaac; checks the player names)
    ... scripts/nus_isaac_clips.py --from-frames --clip <name>   # encode again from the saved raw frames (CPU, no Isaac)
    ... --headless --enable_cameras --clip props_g19_vs_s20 --allow-siblings --out runs/nus_port/isaac_clips_more   # second set, GPU shared

A thin layer over ``scripts/make_s2b_video.py`` (same world, camera, overlay and encoders; its colours and USD path are imported). The games are the
ladder's row 6 (``nus/hangar_game.NusHangarGame``: physics drones, all-pairs filter, free height with jitter, the hangar geometry from the git-ignored
local files) played by the Phase 4 players of ``nus/players.py`` on the first paired starts, not scripted strategies. Steps: a dry run plays every
candidate game once without the camera; the first Strike win and the first hold are chosen (a missing kind is made up by a further game of the other
kind); each chosen game is reset with the same seed and played again with the camera on its slot, one frame per tick, until it ends. The recorded game is
compared with the dry run (position difference) and the result is written to the sidecar. Output under ``runs/nus_port/isaac_clips/`` (git-ignored):
``<clip>_<kind>_<k>.mp4`` and ``.gif`` (sizes capped by the settings), a sidecar ``.toml``, and the raw frames and per-frame data in ``_raw/<clip>_<kind>_<k>/``.

Second set (owner, 18 Nov 2026 evening: "more Isaac Lab clips of NUS's policy, including in the props and construction-site worlds"): optional
per-clip keys, the first set's clips and defaults unchanged. ``scene`` = "plain" (default), "props" (blocks and columns for show, ``props_seed``,
``props_count``) or "construction_site" (the site world as a backdrop, ``[construction_site]`` of configs/s2b_video_scenes.toml); the scene is
built by ``make_s2b_video``'s scene layer exactly as the S2b clips build it, around the hangar game's own arena (its geometry is not changed;
it fits the site's clear patch). Visual only: nothing the game or the drones can sense. ``caption`` replaces ``[video] caption``;
``candidate_games`` replaces the ladder's ``video_slots`` and ``first_start`` (0-based index into the paired starts, default 0) moves the
candidates along the starts file; ``kinds`` (["hold"], ["strike_win", "hold"], ...) replaces the
``games_per_clip`` choice: the first unused candidate of each kind, a missing kind is reported and skipped. A site clip stops with exit 2
before Isaac starts when the world file is missing (it is on the laptop only). ``--allow-siblings`` is passed to the preflight.

No overlay or sidecar states the arena size (written when the hangar size was kept local; since 18 Nov ~14:10 the owner allows it in documents,
see docs/NUS_PORT_REPORT.md §3, but the clips keep the plain overlay); the overlay shows the two players and the drone counts only.
Exit 0 done, 1 crash, 2 bad arguments; the preflight's own code (11 = GPU busy) when it stops the launch.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import subprocess
import sys
import time
import tomllib
import traceback
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

CONFIG = ROOT / "configs" / "nus_isaac_clips.toml"
SCENES = ROOT / "configs" / "s2b_video_scenes.toml"      # [construction_site]: the site world, its spot, camera and lights (S2b)
KINDS = ("strike_win", "hold")
OUT_DIR = ROOT / "runs" / "nus_port" / "isaac_clips"
EXIT_BAD_ARGS, EXIT_CRASH = 2, 1


# ------------------------------------------------------------------------------------------------ settings and pure helpers
def load_settings(path: Path = CONFIG) -> dict:
    return tomllib.loads(Path(path).read_text())


def find_clip(settings: dict, name: str) -> dict:
    for clip in settings["clip"]:
        if clip["name"] == name:
            return dict(clip)
    raise KeyError(f"unknown clip {name!r}; known: {[c['name'] for c in settings['clip']]}")


def scene_of(clip: dict) -> str:
    return clip.get("scene", "plain")


def caption_of(settings: dict, clip: dict) -> str:
    return clip.get("caption", settings["video"]["caption"])


def load_site(path: Path | None = None) -> dict:
    """The construction-site settings of the S2b scenes file (the same world, spot, camera and lights as the S2b clips)."""
    return tomllib.loads(Path(path or SCENES).read_text())["construction_site"]


def team_of(name: str) -> str | None:
    """The team a player plays: the ladder's players (``nus/players.py``), then our scripted strategies by their prefix (``guard_mirror``)."""
    from svg_training.nus import players
    from svg_training.opponents.scripted import REGISTRY
    if name in players.TEAM_OF:
        return players.TEAM_OF[name]
    prefix = name.split("_")[0]
    return prefix if name in REGISTRY and prefix in ("guard", "strike") else None


def check_clips(settings: dict) -> None:
    """Every clip names a Guard-team player as its Guard and a Strike-team player as its Strike (``nus/players.py`` or a scripted strategy), a
    known scene (props with their seed and count) and known kinds."""
    import make_s2b_video as s2b
    for clip in settings["clip"]:
        for team in ("guard", "strike"):
            name = clip[team]
            if team_of(name) != team:
                raise ValueError(f"clip {clip['name']!r}: {name!r} is not a {team} player of the ladder")
        if scene_of(clip) not in s2b.SCENES:
            raise ValueError(f"clip {clip['name']!r}: scene {scene_of(clip)!r} is not one of {s2b.SCENES}")
        if scene_of(clip) == "props" and not {"props_seed", "props_count"} <= set(clip):
            raise ValueError(f"clip {clip['name']!r}: a props scene needs props_seed and props_count")
        if not set(clip.get("kinds", [])) <= set(KINDS):
            raise ValueError(f"clip {clip['name']!r}: kinds must be among {KINDS}")


def pick_slots(outcomes: list[int], want: int, strike_win: int, guard_win: int) -> list[tuple[int, str]]:
    """Games to record, from the first-game outcomes of the candidates: the first Strike win, then the first hold, then further games of either kind
    (Strike wins first) up to ``want``. Fewer when the candidates hold fewer. Sorted by slot."""
    wins = [i for i, o in enumerate(outcomes) if o == strike_win]
    holds = [i for i, o in enumerate(outcomes) if o == guard_win]
    order = [(i, "strike_win") for i in wins[:1]] + [(i, "hold") for i in holds[:1]]
    order += [(i, "strike_win") for i in wins[1:]] + [(i, "hold") for i in holds[1:]]
    return sorted(order[:want])


def pick_kinds(outcomes: list[int], kinds: list[str], strike_win: int, guard_win: int) -> list[tuple[int, str]]:
    """Games to record for a clip's ``kinds``: for each kind in order, the first candidate of that outcome not taken yet. A kind with no
    candidate left is skipped. Sorted by slot."""
    code = {"strike_win": strike_win, "hold": guard_win}
    taken: list[tuple[int, str]] = []
    for kind in kinds:
        slot = next((i for i, o in enumerate(outcomes) if o == code[kind] and i not in {t[0] for t in taken}), None)
        if slot is not None:
            taken.append((slot, kind))
    return sorted(taken)


WORLD_NAMES = {"props": "props world (backdrop only)", "construction_site": "construction-site world (backdrop only)"}


def info_line(clip: dict, guards: int, strikes: int) -> str:
    """The small line above the caption. Players, drone counts and, outside the plain arena, the world: never the arena size."""
    line = f"{guards} Guard v {strikes} Strike drones | Guard: {clip['guard']}, Strike: {clip['strike']}"
    return line if scene_of(clip) == "plain" else f"{line} | {WORLD_NAMES[scene_of(clip)]}"


def result_text(outcome: int, end_step: int, ticks: int, tick_s: float, strike_win: int, guard_win: int) -> str | None:
    if outcome == strike_win:
        return f"Strike team reaches the zone at {end_step * tick_s:.1f} s"
    if outcome == guard_win:
        return "Guard team holds the zone to the end" if end_step >= ticks else f"Guard team wins at {end_step * tick_s:.1f} s: no Strike drone left"
    return None


def take_name(clip: dict, kind: str, index: int) -> str:
    return f"{clip['name']}_{kind}_{index}"


def sidecar_rows(clip: dict, meta: dict, mp4_bytes: int, crf: int, gif_info: dict | None, gif_bytes: int | None, caption: str) -> dict:
    """Settings and provenance of one clip. No arena size, no hangar value, no partner value. Outside the plain arena also the scene, the number
    of props and the backdrop file."""
    rows = {"clip": meta["name"], "caption": caption, "commit": meta["commit"], "working_tree": meta["working_tree"], "date": meta["date"],
            "guard": clip["guard"], "strike": clip["strike"], "kind": meta["kind"], "slot": meta["slot"], "candidate_games": meta["candidate_games"],
            "row": meta["row"], "seed": meta["seed"], "outcome": meta["result_text"] or "the clip ends before the game does", "upset": meta["upset"],
            "game_length_s": meta["game_length_s"], "recorded_s": meta["recorded_s"], "replay_max_pos_diff_m": meta["replay_max_pos_diff_m"],
            "dry_run_differs": meta["dry_run_differs"], "fps": meta["fps"], "resolution": meta["resolution"], "hold_last_frame_s": meta["hold_s"],
            "mp4_bytes": mp4_bytes, "mp4_crf": crf, "gif_bytes": gif_bytes, "gif_width": (gif_info or {}).get("width"), "gif_fps": (gif_info or {}).get("fps"),
            "gif_speed_x_real_time": (gif_info or {}).get("speed"), "vram_used_mib_while_recording": meta["vram_mib"], "isaac": meta["isaac"],
            "record_wall_s": meta["wall_s"]}
    if "first_start" in meta:                     # the candidates start at this paired start: the game's own index in the starts file
        rows["paired_start_index"] = meta["first_start"] + meta["slot"]
    if meta.get("scene", "plain") != "plain":
        detail = meta.get("scene_detail") or {}
        rows.update({"scene": meta["scene"], "props_seed": clip.get("props_seed"), "props_count": detail.get("props_count"),
                     "backdrop_file": detail.get("backdrop_file"), "backdrop_sha256": detail.get("backdrop_sha256")})
    return rows


# ------------------------------------------------------------------------------------------------ the games (Isaac-free given a world and a stage)
def _git(args: list[str]) -> str:
    r = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True)
    return r.stdout.strip()


def working_tree_state() -> str:
    files = sorted({ln.split(maxsplit=1)[-1] for ln in _git(["status", "--porcelain", "--", "scripts", "source", "configs"]).splitlines() if ln.strip()})
    return "clean" if not files else "uncommitted changes: " + ", ".join(files)


def make_context(settings: dict, device: str, make_world, games: int | None = None, first: int = 0) -> SimpleNamespace:
    """Everything the games need: the row-6 configuration, the geometry, the paired starts of the candidates (``games`` of them from paired start
    index ``first``; the game draws no random numbers, so a game depends only on its own start) and the physics world.
    ``make_world(n, drones, params, device)`` builds the world (Isaac Lab, or a PyTorch rigid-body world in tests)."""
    from svg_training.core.physics_layer import load_game_physics_params
    from svg_training.nus import hangar as H
    from svg_training.nus import ladder as L
    from svg_training.core.game_config import load_game_cfg
    from svg_training.nus import strategy as strategy_module
    from svg_training.nus.deploy import apply_overrides, load_deploy
    from svg_training.nus.rules import load_rules
    phase4 = H.load_phase4()
    row = next(r for r in phase4["row"] if r["id"] == settings["video"]["row"])
    if row["drone"] != "physics":
        raise ValueError(f"row {row['id']!r} has no physics drone: the Isaac clips play the physics row")
    base, _ = load_game_cfg(H.HANGAR_GAME, use_local=False)
    deploy = load_deploy(strategy_module.DEPLOY_PATH)
    rules = apply_overrides(load_rules(strategy_module.RULES_PATH), deploy)
    hangar = H.load_hangar(H.LOCAL_HANGAR)
    geo = H.geometry(rules, deploy, hangar, base)
    cfg = H.hangar_cfg(base, rules, deploy, hangar, row)
    available = L.load_starts(L.STARTS_FILE)
    n = min(games or phase4["ladder"]["video_slots"], available["starts_units"].shape[0] - first)
    starts = {k: v[first:first + n] for k, v in available.items()}
    params = load_game_physics_params(cfg)
    world = make_world(n, rules.guard_count + rules.strike_count, params, device, geo, rules.guard_count)
    return SimpleNamespace(settings=settings, phase4=phase4, row=row, cfg=cfg, geo=geo, rules=rules, starts=starts, world=world, n=n, device=device, first=first,
                           guards=rules.guard_count, strikes=rules.strike_count, seed=phase4["ladder"]["seed"])


def new_game(ctx, clip: dict):
    """The hangar game of the row for this matchup (a parked Guard when the Guard player parks Guard 0)."""
    from svg_training.nus.hangar_game import NusHangarGame
    from svg_training.nus.players import make_player, parks_guard0
    guard = make_player(clip["guard"], "guard", ctx.cfg, ctx.n, ctx.device, ctx.seed)
    return NusHangarGame(ctx.cfg, ctx.geo, ctx.row, ctx.starts["starts_units"], ctx.starts["jitter_m"], ctx.guards, ctx.strikes, device=ctx.device,
                         seed=ctx.seed, parked=parks_guard0(guard), world=ctx.world, rules=ctx.rules)


def new_players(ctx, clip: dict):
    import torch
    from svg_training.nus.players import make_player
    guard = make_player(clip["guard"], "guard", ctx.cfg, ctx.n, ctx.device, ctx.seed)
    strike = make_player(clip["strike"], "strike", ctx.cfg, ctx.n, ctx.device, ctx.seed)
    everyone = torch.ones(ctx.n, dtype=torch.bool, device=ctx.device)
    guard.reset(everyone)
    strike.reset(everyone)
    return guard, strike


def dry_run(ctx, game, clip: dict) -> dict:
    """Play every candidate's first game without the camera. Returns first end tick, first outcome and the positions per tick [ticks + 1][N, M, 3]."""
    import torch
    obs = game.reset(seed=ctx.seed)
    guard, strike = new_players(ctx, clip)
    first_end = torch.zeros(ctx.n, dtype=torch.long, device=ctx.device)
    first_out = torch.zeros(ctx.n, dtype=torch.int8, device=ctx.device)
    positions = [game.pos_m.cpu().numpy()]
    for _ in range(game.ticks):
        out = game.step({"guard": guard.act(obs["guard"]), "strike": strike.act(obs["strike"])})
        new = out.done & (first_end == 0)
        first_end = torch.where(new, out.end_step, first_end)
        first_out = torch.where(new, out.outcome, first_out)
        guard.reset(out.done)
        strike.reset(out.done)
        obs = out.obs
        positions.append(game.pos_m.cpu().numpy())
        if bool((first_end > 0).all()):
            break
    return {"end_step": first_end.cpu().numpy(), "outcome": first_out.cpu().numpy(), "positions": positions}


def record_take(ctx, game, clip: dict, slot: int, kind: str, index: int, stage, dry: dict, work: Path, name: str) -> dict:
    """Replay the game of ``slot`` (same seed, same starts) with the camera on it: raw frames to ``work/raw.mp4`` and ``work/meta.json``."""
    import numpy as np
    import imageio.v2 as imageio
    from svg_training.core.game_config import TICK_S
    from svg_training.core.rewards import GUARD_WIN, STRIKE_WIN
    v = ctx.settings["video"]
    t_start = time.time()
    work.mkdir(parents=True, exist_ok=True)
    obs = game.reset(seed=ctx.seed)
    guard, strike = new_players(ctx, clip)
    stage.prepare(slot)
    writer = imageio.get_writer(str(work / "raw.mp4"), format="FFMPEG", fps=int(v["fps"]), codec="libx264", quality=None, pixelformat="yuv420p",
                                macro_block_size=2, ffmpeg_params=["-crf", "10", "-preset", "fast"], ffmpeg_log_level="error")
    per_frame, pos_log = [{"tick": 0, "time_left_s": float(game.ticks * TICK_S)}], [game.pos_m[slot].cpu().numpy().tolist()]
    first = stage.frame()
    writer.append_data(first)
    end_step, outcome, upset = 0, 0, False
    for k in range(1, game.ticks + 1):
        out = game.step({"guard": guard.act(obs["guard"]), "strike": strike.act(obs["strike"])})
        done = bool(out.done[slot])
        upset = upset or bool(out.info["upset"][slot])
        if done:
            end_step, outcome = int(out.end_step[slot]), int(out.outcome[slot])
            pos = game._starling.world.state()[0][slot].cpu().numpy()          # the world still holds the end pose
        else:
            pos = game.pos_m[slot].cpu().numpy()
        writer.append_data(stage.frame())
        per_frame.append({"tick": k, "time_left_s": float((game.ticks - k) * TICK_S)})
        pos_log.append(pos.tolist())
        guard.reset(out.done)
        strike.reset(out.done)
        obs = out.obs
        if done:
            break
    writer.close()
    dry_end = int(dry["end_step"][slot])
    k_max = min(len(pos_log), len(dry["positions"]), dry_end) - 1
    mine = np.asarray(pos_log[: k_max + 1])
    theirs = np.stack([p[slot] for p in dry["positions"][: k_max + 1]])
    diff = float(np.abs(mine - theirs).max()) if k_max >= 0 else 0.0
    same_end = end_step == dry_end and outcome == int(dry["outcome"][slot])
    meta = {"name": name, "kind": kind, "slot": slot, "index": index, "candidate_games": ctx.n, "row": ctx.row["id"], "seed": ctx.seed,
            "frames": len(per_frame), "per_frame": per_frame, "end_step": end_step, "outcome": outcome, "upset": upset,
            "result_text": result_text(outcome, end_step, game.ticks, TICK_S, STRIKE_WIN, GUARD_WIN),
            "game_length_s": end_step * TICK_S if end_step else None, "recorded_s": (len(per_frame) - 1) * TICK_S,
            "replay_max_pos_diff_m": diff, "dry_run_differs": bool(diff > float(v["replay_tolerance_m"]) or not same_end),
            "fps": int(v["fps"]), "resolution": list(v["resolution"]), "commit": _git(["rev-parse", "--short=12", "HEAD"]) or "unknown",
            "working_tree": working_tree_state(), "date": datetime.date.today().isoformat(), "vram_mib": stage.vram_mib(),
            "isaac": stage.label, "guards": ctx.guards, "strikes": ctx.strikes, "wall_s": time.time() - t_start, "guard": clip["guard"], "strike": clip["strike"]}
    if "first_start" in clip:
        meta["first_start"] = int(clip["first_start"])
    if scene_of(clip) != "plain":
        meta.update({"scene": scene_of(clip), "scene_detail": getattr(stage, "scene_detail", None) or {}})
    (work / "meta.json").write_text(json.dumps(meta, indent=1))
    return meta


def _now() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def record_clip(ctx, clip: dict, stage_factory, work_root: Path) -> list[str]:
    """Dry run, choose the games, record each. Returns the names of the takes (their folders are under ``work_root``)."""
    from svg_training.core.rewards import GUARD_WIN, STRIKE_WIN
    game = new_game(ctx, clip)
    print(f"{_now()} {clip['name']}: dry run of {ctx.n} candidate games", flush=True)
    dry = dry_run(ctx, game, clip)
    outcomes = [int(o) for o in dry["outcome"]]
    if "kinds" in clip:
        chosen = pick_kinds(outcomes, list(clip["kinds"]), STRIKE_WIN, GUARD_WIN)
        for kind in KINDS:
            missing = list(clip["kinds"]).count(kind) - [k for _, k in chosen].count(kind)
            if missing > 0:
                print(f"{clip['name']}: {missing} {kind} wanted, none left among the {ctx.n} candidates", flush=True)
    else:
        chosen = pick_slots(outcomes, int(ctx.settings["video"]["games_per_clip"]), STRIKE_WIN, GUARD_WIN)
    print(f"{_now()} {clip['name']}: first-game outcomes {dry['outcome'].tolist()}; recording {chosen}", flush=True)
    if not chosen:
        raise RuntimeError("no candidate game ended: nothing to record")
    stage = stage_factory(ctx)
    names = []
    counts: dict[str, int] = {}
    for slot, kind in chosen:
        counts[kind] = counts.get(kind, 0) + 1
        name = take_name(clip, kind, counts[kind])
        meta = record_take(ctx, game, clip, slot, kind, counts[kind], stage, dry, work_root / name, name)
        print(f"{_now()} recorded {name}: {meta['frames']} frames, result {meta['result_text']!r}, upset {meta['upset']}, replay diff {meta['replay_max_pos_diff_m']:.2e} m", flush=True)
        names.append(name)
    return names


# ------------------------------------------------------------------------------------------------ Isaac Lab stage
class IsaacStage:
    """The Isaac Lab scene of the clip: arena visuals of the recorded slot, camera, frames. Needs the app started with cameras on."""

    def __init__(self, ctx, sim, label: str, clip: dict | None = None):
        import numpy as np
        import make_s2b_video as s2b
        from svg_training.bench.overlay import camera_pose
        from svg_training.compat import isaaclab_232 as isaac
        self.ctx, self.sim, self.label, self.isaac, self.np, self.camera_pose, self.s2b = ctx, sim, label, isaac, np, camera_pose, s2b
        self.clip = clip or {}
        self.scene = scene_of(self.clip)
        self.site = load_site() if self.scene == "construction_site" else None
        self.backdrop = getattr(ctx.world, "_clip_backdrop", None)
        self.scene_detail: dict = {}
        self.origins = ctx.world.scene.env_origins.detach().cpu().numpy().astype(float)
        v = ctx.settings["video"]
        self._frame = isaac.make_recorder(sim, tuple(self.origins[0] + np.array([0.0, 0.0, 1.0])), tuple(self.origins[0]), tuple(int(x) for x in v["resolution"]))

    def prepare(self, slot: int) -> None:
        ctx, np = self.ctx, self.np
        half = ctx.geo.side_m / 2
        top = float(ctx.cfg.arena.height_band_m[1])
        # the hangar game's own arena (zone at the centre); the S2b scene layer adds the props or moves the site under it
        props = self.s2b.place_scene(self.isaac, self.scene, slot, self.origins[slot], half, (0.0, 0.0), ctx.geo.zone_radius_m,
                                     ctx.cfg.arena.wall_margin_m, top, site=self.site, backdrop=self.backdrop,
                                     props_seed=self.clip.get("props_seed"), props_count=self.clip.get("props_count"))
        self.scene_detail = {"props_count": len(props), "backdrop_file": (self.backdrop or {}).get("file"),
                             "backdrop_sha256": (self.backdrop or {}).get("sha256")}
        self.isaac.show_only_game(ctx.n, slot)
        eye, look = self.camera_pose(half, self.origins[slot], top_m=top, **self.s2b.site_camera_kw(self.site))
        self._frame.set_view(tuple(float(x) for x in eye), tuple(float(x) for x in look))
        if self.site is not None:                                      # the site's textures stream in over many frames (as S2b)
            self.s2b.warm_up(self._frame, self.isaac, self.site)
            return
        for _ in range(int(ctx.settings["video"]["warm_frames"])):      # the renderer's textures and filters settle
            self._frame()
            if self.isaac.stage_loading_done():
                break

    def frame(self):
        return self._frame()

    def vram_mib(self):
        r = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"], capture_output=True, text=True)
        try:
            return int(r.stdout.split()[0])
        except (IndexError, ValueError):
            return None


def make_isaac_world(settings: dict, clip: dict | None = None):
    """A ``make_world`` for ``make_context`` that builds the Starling-visual IsaacWorld (after the app started); for a site clip the world has
    the site's lights and no floor, and the site is referenced before physics starts (``make_s2b_video``'s scene layer)."""
    import make_s2b_video as s2b
    from svg_training.compat import isaaclab_232 as isaac
    site = load_site() if scene_of(clip or {}) == "construction_site" else None

    def make(n, drones, params, device, geo, guards):
        sim = isaac.make_physics_sim(params.physics_dt_s, device)
        s2b.spawn_scene_world(isaac, site)
        v = settings["video"]
        rgb = [tuple(c / v["rgb_full"] for c in s2b.GUARD_RGB)] * guards + [tuple(c / v["rgb_full"] for c in s2b.STRIKE_RENDER_RGB)] * (drones - guards)
        usd = str(s2b.STARLING_USD.resolve())
        marker = float(v["marker_base_m"]) + float(v["marker_per_side"]) * geo.side_m
        world = isaac.IsaacWorld(sim, n, drones, params.airframe, params.physics_dt_s, visual="starling", slot_rgb=rgb, starling_usd=usd, marker_radius_m=marker)
        if site is not None:
            world._clip_backdrop = s2b.spawn_site_backdrop(isaac, site, world.scene.env_origins[0].detach().cpu().numpy())
        isaac.physics_play(sim, world)
        world._clip_sim = sim
        return world
    return make


# ------------------------------------------------------------------------------------------------ encode (no Isaac)
def encode(settings: dict, clip: dict, work_root: Path, out: Path, no_gif: bool = False) -> list[Path]:
    import imageio.v2 as imageio
    import make_s2b_video as s2b
    from svg_training.bench.overlay import draw_overlay, encode_gif, encode_mp4
    v = settings["video"]
    legend = {"Guard team": s2b.GUARD_RGB, "Strike team": s2b.STRIKE_RGB, "Zone": s2b.ZONE_RGB}
    written = []
    for folder in sorted(p for p in work_root.iterdir() if p.is_dir() and p.name.startswith(clip["name"] + "_")):
        meta = json.loads((folder / "meta.json").read_text())
        info = info_line(clip, meta["guards"], meta["strikes"])
        reader = imageio.get_reader(str(folder / "raw.mp4"))
        pf = meta["per_frame"]
        caption = caption_of(settings, clip)
        frames = [draw_overlay(img, caption, legend, pf[i]["time_left_s"], meta["result_text"] if i == len(pf) - 1 else None, info)
                  for i, img in enumerate(reader)]
        reader.close()
        if len(frames) != len(pf):
            raise RuntimeError(f"{folder.name}: raw.mp4 has {len(frames)} frames, meta.json {len(pf)}")
        hold_s = float(v["hold_s"]) if meta["result_text"] else 0.0
        hold_s = max(hold_s, float(v["hold_min_s"])) if meta["result_text"] else 0.0
        frames += [frames[-1]] * int(round(hold_s * meta["fps"]))
        meta["hold_s"] = hold_s
        mp4, crf = encode_mp4(frames, out / f"{meta['name']}.mp4", fps=meta["fps"], max_mb=float(v["max_mb"]))
        gif_info = gif_bytes = None
        if not no_gif:
            gif, gif_info = encode_gif(frames, out / f"{meta['name']}.gif", fps=int(v["gif_fps"]), max_mb=float(v["gif_max_mb"]), src_fps=meta["fps"],
                                       speed=float(v["gif_speed"]))
            gif_bytes = gif.stat().st_size
            written.append(gif)
        side = sidecar_rows(clip, meta, mp4.stat().st_size, crf, gif_info, gif_bytes, caption)
        head = "# Isaac Lab clip sidecar, written by scripts/nus_isaac_clips.py. Training simulator, frozen partner policies, not a real flight.\n# Not a measurement: no gates, no ledger row. No arena size.\n"
        (out / f"{meta['name']}.toml").write_text(head + "".join(f"{k} = {json.dumps(val)}\n" if val is not None else f"{k} = \"none\"\n" for k, val in side.items()))
        tomllib.loads((out / f"{meta['name']}.toml").read_text())
        written.append(mp4)
        print(f"{mp4.name}: {mp4.stat().st_size} bytes (crf {crf}); gif {gif_info} {gif_bytes} bytes", flush=True)
    return written


# ------------------------------------------------------------------------------------------------ main
def make_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--clip", help="a clip name of the settings file")
    ap.add_argument("--config", type=Path, default=CONFIG)
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    ap.add_argument("--list", action="store_true", help="print the clips and check the player names (CPU, no Isaac)")
    ap.add_argument("--from-frames", action="store_true", help="encode from the saved raw frames only (no Isaac)")
    ap.add_argument("--no-gif", action="store_true")
    ap.add_argument("--allow-siblings", action="store_true", help="passed to the preflight: this folder's own GPU jobs may share the GPU")
    return ap


def record(args) -> int:
    """Isaac mode, after the app started."""
    settings = load_settings(args.config)
    clip = find_clip(settings, args.clip)
    check_clips(settings)
    dev = args.device if str(args.device).startswith("cuda") else "cuda:0"
    ctx = make_context(settings, dev, make_isaac_world(settings, clip), games=clip.get("candidate_games"),
                       first=int(clip.get("first_start", 0)))
    sim = ctx.world._clip_sim
    from svg_training.compat import isaaclab_232 as isaac
    record_clip(ctx, clip, lambda c: IsaacStage(c, sim, isaac.ISAAC_WORLD_LABEL, clip), args.out / "_raw")
    return 0


def main() -> int:
    ap = make_parser()
    known = ap.parse_known_args()[0]
    settings = load_settings(known.config)
    if known.list:
        check_clips(settings)
        for clip in settings["clip"]:
            print(f"{clip['name']}: Guard {clip['guard']} v Strike {clip['strike']} ({scene_of(clip)})")
        return 0
    if not known.clip:
        print("refusing: give --clip <name> (or --list)", file=sys.stderr)
        return EXIT_BAD_ARGS
    try:
        clip = find_clip(settings, known.clip)
    except KeyError as e:
        print(e, file=sys.stderr)
        return EXIT_BAD_ARGS
    if known.from_frames:
        encode(settings, clip, known.out / "_raw", known.out, known.no_gif)
        return 0
    if scene_of(clip) == "construction_site":
        import make_s2b_video as s2b
        usd = s2b.site_usd_path(load_site())
        if not usd.is_file():
            print(f"refusing: clip {clip['name']!r} needs the construction-site world {usd} (laptop only, never in git); "
                  "copy the localisation/scenes/construction_site/build/ bundle first", file=sys.stderr)
            return EXIT_BAD_ARGS
    flags = ["--approved-headless"] + (["--allow-siblings"] if known.allow_siblings else [])
    pre = subprocess.run(["bash", str(ROOT / "scripts" / "isaac_preflight.sh"), *flags], capture_output=True, text=True)
    print(pre.stdout, flush=True)
    known.out.mkdir(parents=True, exist_ok=True)
    (known.out / f"preflight_{clip['name']}.txt").write_text(pre.stdout + pre.stderr)
    if pre.returncode != 0:
        print(f"preflight exit {pre.returncode}: stop", file=sys.stderr)
        return pre.returncode or EXIT_CRASH
    from _isaac_app import start_headless
    args, _app = start_headless(ap, cameras=True)
    code = EXIT_CRASH
    try:
        code = record(args)
        if code == 0:
            encode(settings, clip, args.out / "_raw", args.out, args.no_gif)
    except BaseException:  # noqa: BLE001
        traceback.print_exc()
    finally:
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(code)
    return code


if __name__ == "__main__":
    sys.exit(main())
