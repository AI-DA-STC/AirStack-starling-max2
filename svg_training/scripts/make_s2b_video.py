#!/usr/bin/env python3
"""S2b Task 6: videos of scripted games on rigid-body Starling drones in Isaac Lab (training simulator), for people.

    # on the host (the Starling USD and the construction-site world lie outside svg_training/), headless, cameras on
    PYTHONPATH=source ~/miniconda3/envs/env_isaaclab/bin/python scripts/make_s2b_video.py --headless --enable_cameras \\
        --clip s2b_2v1_lab [--config configs/s2b.toml] [--scenes configs/s2b_video_scenes.toml] [--visual starling]
    # encode again from the saved frames (overlay, size cap, GIF, stills), no Isaac
    PYTHONPATH=source ~/miniconda3/envs/env_isaaclab/bin/python scripts/make_s2b_video.py --from-frames --clip <name>

Clips: the four ``[video] clips`` of configs/s2b.toml (plain floor) and the ``[[clips]]`` of
configs/s2b_video_scenes.toml (visual props, or the construction-site world as a backdrop). Every clip uses the
committed neutral game settings (``use_local=False``; the partner's local file is never read) with
``starling_layer.enabled = true, backend = "physics"``: commander copy, safety filter, PX4 1.14 cascade, rotor model,
rigid bodies in PhysX, the SIM-ONLY yaw-rate gains (owner's ruling, 16 Nov 2026).

Steps (Isaac mode): preflight (``scripts/isaac_preflight.sh --approved-headless``; exit 11, a busy GPU, stops);
``IsaacWorld(candidate_games, drones, visual=...)``; the dry run plays every slot's first game without the camera;
the clip rule (``bench/overlay.pick_clip_slot``) picks the slot; the game is reset with the same seed and the same
strategy seeds (the same starts, D15) and played again with the camera on that slot, one frame per game tick, until
that game ends or ``seconds_max``. Raw frames (H.264, crf 10) and per-frame data go to ``runs/s2b_video/<clip>/``;
then the encode step burns in the overlay, holds the last frame 1-2 s if the game ended inside the clip (with the
result; the clip stays within seconds_max where it can), encodes H.264 (crf raised in steps of 4 until <= max_mb), a GIF (<= 5 MB) and a sidecar TOML into docs/media/,
and the still frames of configs/s2b_video_scenes.toml [[stills]] for this clip.

Not a measurement: no gates, no record, no ledger row. Exit 0 done, 1 crash, 2 bad arguments, 11 GPU busy.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import time
import tomllib
import traceback

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
sys.path.insert(0, str(ROOT / "scripts"))

STARLING_USD = (ROOT / ".." / "AirStack" / "simulation" / "isaac-sim" / "assets" / "robots" / "starling2max.usd")
GUARD_RGB = (0, 114, 178)          # Okabe-Ito blue, as the replay animations
STRIKE_RGB = (230, 159, 0)         # Okabe-Ito orange (legend)
STRIKE_RENDER_RGB = (240, 95, 0)    # deeper on the drones: the renderer's tone curve turns Okabe-Ito orange yellow
ZONE_RGB = (0, 158, 115)
HOLD_S = 2.0                       # the last frame (with the result) is held up to this long, within seconds_max
HOLD_MIN_S = 1.0                   # ... and at least this long, so the result can be read
GIF_MAX_MB = 5.0
GIF_FPS = 10
GIF_SPEED = 2.0                    # GIFs play at 2 x real time (as the replay animations), so they stay sharp under 5 MB
SIMPLIFIED = " (simplified drone shape)"


# --------------------------------------------------------------------------------------------- settings
def load_clip(name: str, config: pathlib.Path, scenes: pathlib.Path) -> tuple[dict, dict, dict]:
    """(clip, video settings, scenes file) for a clip name from either file; KeyError if unknown."""
    video = tomllib.loads(config.read_text())["video"]
    sc = tomllib.loads(scenes.read_text())
    for c in video["clips"]:
        if c["name"] == name:
            return {**c, "scene": "plain", "caption": video["caption"]}, video, sc
    for c in sc["clips"]:
        if c["name"] == name:
            return dict(c), video, sc
    names = [c["name"] for c in video["clips"]] + [c["name"] for c in sc["clips"]]
    raise KeyError(f"unknown clip {name!r}; known: {names}")


def label(spec: str) -> str:
    return spec.replace("guard_", "").replace("strike_", "").replace("_", " ")


def sha256(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def git_commit() -> str:
    r = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short=12", "HEAD"], capture_output=True, text=True)
    return r.stdout.strip() or "unknown"


def working_tree_state() -> str:
    """'clean', or which pipeline files differ from the commit (the clip was made from a working tree)."""
    r = subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain", "--", "scripts", "source", "configs"],
                       capture_output=True, text=True)
    files = sorted({ln[3:].strip() for ln in r.stdout.splitlines() if ln.strip()})
    return "clean" if not files else "uncommitted changes: " + ", ".join(files)


def gpu_used_mib() -> int | None:
    r = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                       capture_output=True, text=True)
    try:
        return int(r.stdout.split()[0])
    except (IndexError, ValueError):
        return None


def make_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--clip", required=True)
    ap.add_argument("--config", default="configs/s2b.toml")
    ap.add_argument("--scenes", default="configs/s2b_video_scenes.toml")
    ap.add_argument("--out", default="docs/media")
    ap.add_argument("--work", default="runs/s2b_video", help="raw frames and per-frame data (git-ignored)")
    ap.add_argument("--visual", default="starling", choices=["starling", "primitive"])
    ap.add_argument("--from-frames", action="store_true", help="encode from runs/s2b_video/<clip>/ only, no Isaac")
    ap.add_argument("--smoke-ticks", type=int, default=0,
                    help="> 0: no dry run (slot 0), record this many ticks, save PNGs only (a render check)")
    ap.add_argument("--stills-only", action="store_true",
                    help="replay the clip's game (slot from its meta.json) up to the last still, save the stills only")
    ap.add_argument("--no-gif", action="store_true")
    return ap


def _path(p: str) -> pathlib.Path:
    q = pathlib.Path(p)
    return q if q.is_absolute() else (ROOT / q)


# --------------------------------------------------------------------------------------------- Isaac part
def record(args) -> int:
    """Isaac mode (after the app started): dry run, clip rule, recorded pass. Writes raw.mp4 + meta.json."""
    import numpy as np
    import torch
    import imageio.v2 as imageio

    from svg_training.bench.overlay import camera_pose, pick_clip_slot, place_props
    from svg_training.compat import isaaclab_232 as isaac
    from svg_training.core.arena import BANDS
    from svg_training.core.game import SvgGame
    from svg_training.core.game_config import TICK_S, load_game_cfg
    from svg_training.core.physics_layer import load_game_physics_params
    from svg_training.core.rewards import GUARD_WIN, STRIKE_WIN
    from svg_training.models.physics_params import yaw_gains_text
    from svg_training.opponents.scripted import make_strategy

    t_start = time.time()
    clip, video, sc = load_clip(args.clip, _path(args.config), _path(args.scenes))
    work = _path(args.work) / clip["name"]
    work.mkdir(parents=True, exist_ok=True)
    g, s = (int(v) for v in clip["size"].split("v"))
    m = g + s
    band = BANDS.index(clip["band"])
    seed = int(clip["seed"])
    n = int(video["candidate_games"]) if args.smoke_ticks <= 0 else 1
    cfg, prov = load_game_cfg(use_local=False)                       # committed neutral values only
    cfg = cfg.replace(**{"starling.enabled": True, "starling.backend": "physics"})
    params = load_game_physics_params(cfg)
    dev = args.device if args.device.startswith("cuda") else "cuda:0"
    sim = isaac.make_physics_sim(params.physics_dt_s, dev)
    scene = clip["scene"]
    site = sc["construction_site"] if scene == "construction_site" else None
    isaac.spawn_world_lights(sun=site is None)
    if site is None:
        isaac.spawn_floor()
    side_max_m = cfg.arena.bands_m[clip["band"]][1]
    marker_r = 0.03 + 0.0094 * side_max_m
    slot_rgb = [tuple(c / 255 for c in GUARD_RGB)] * g + [tuple(c / 255 for c in STRIKE_RENDER_RGB)] * s
    usd = str(STARLING_USD.resolve()) if args.visual == "starling" else None
    world = isaac.IsaacWorld(sim, n, m, params.airframe, params.physics_dt_s, visual=args.visual, slot_rgb=slot_rgb,
                             starling_usd=usd, marker_radius_m=marker_r)
    origins = world.scene.env_origins.detach().cpu().numpy().astype(float)        # [N, 3] world
    backdrop = None
    if site is not None:
        site_usd = _path(site["usd"]).resolve()
        spot = (float(site["spot_m"][0]), float(site["spot_m"][1]), float(site["ground_z_m"]))
        removed = isaac.spawn_backdrop(str(site_usd), tuple(origins[0] - np.array(spot)))
        backdrop = {"file": site_usd.name, "sha256": sha256(site_usd), "physics_schemas_removed": removed,
                    "spot_m": list(spot)}
        backdrop["lights"] = isaac.scale_backdrop_lights(float(site["light_scale"]))
        print(f"backdrop {site_usd.name}: {removed} physics schemas removed (visual only); lights "
              f"{backdrop['lights']}", flush=True)
    isaac.physics_play(sim, world)                                   # raises if PhysX holds a different body
    readback = {"com_offset_max_m": world.com_offset_max_m(), "inertia_offdiag_max": world.inertia_offdiag_max(),
                **{k: v for k, v in world.body_settings().items() if k != "prim"}}
    mass, inertia = world.mass_inertia_readback()
    readback["mass_rel_err"] = float(((mass - params.airframe.mass_kg).abs() / params.airframe.mass_kg).max())
    readback["inertia_rel_err"] = float(((inertia - torch.tensor(params.airframe.inertia_kgm2)).abs()
                                         / torch.tensor(params.airframe.inertia_kgm2)).max())
    print("read-back:", json.dumps(readback), flush=True)
    if readback["has_collider"] or readback["com_offset_max_m"] > 1e-6:
        raise RuntimeError(f"the visual changed the physics body: {readback}")

    game = SvgGame(cfg, n, g, s, device=dev, seed=seed, band=band, world=world)

    def strategies():
        gs = make_strategy(clip["guard"], "guard", cfg, n, dev, seed + 101)
        ss = make_strategy(clip["strike"], "strike", cfg, n, dev, seed + 202)
        everyone = torch.ones(n, dtype=torch.bool, device=dev)
        gs.reset(everyone)
        ss.reset(everyone)
        return gs, ss

    # ---- dry run: every slot's first game, no camera
    dry = {}
    if args.stills_only:
        slot = int(json.loads((work / "meta.json").read_text())["slot"])
    elif args.smoke_ticks <= 0:
        obs = game.reset(seed=seed)
        gs, ss = strategies()
        first_end = torch.zeros(n, dtype=torch.long, device=dev)
        dry_pos = [game.pos_m.cpu().numpy()]                                          # [N, M, 3] per tick
        first_out = torch.zeros(n, dtype=torch.int8, device=dev)
        for k in range(1, game.ticks + 1):
            out = game.step({"guard": gs.act(obs["guard"]), "strike": ss.act(obs["strike"])})
            new = out.done & (first_end == 0)
            first_end = torch.where(new, out.end_step, first_end)
            first_out = torch.where(new, out.outcome, first_out)
            gs.reset(out.done)
            ss.reset(out.done)
            obs = out.obs
            dry_pos.append(game.pos_m.cpu().numpy())
            if k % 100 == 0 and bool((first_end > 0).all()):
                break
        end_s = first_end.cpu().numpy() * TICK_S
        slot = pick_clip_slot(end_s, float(video["seconds_min"]), float(video["seconds_max"]))
        dry = {"first_game_s": end_s.tolist(), "outcome": first_out.cpu().tolist(), "slot": slot}
        print(f"dry run: first games {end_s.tolist()} s, outcomes {dry['outcome']}, slot {slot}", flush=True)
    else:
        slot = 0

    # ---- recorded pass: same seed, same strategy seeds, the camera on the chosen slot
    obs = game.reset(seed=seed)
    gs, ss = strategies()
    ar = game.arenas
    half = float(ar.half_m[slot])
    zone_xy = tuple(float(v) for v in ar.zone_centre_m[slot].cpu())
    zone_r = float(ar.zone_radius_m[slot])
    isaac.spawn_arena_visuals(slot, half, zone_xy, zone_r, cfg.arena.wall_margin_m, floor=site is None,
                              top_m=float(cfg.arena.height_band_m[1]))
    props = []
    if scene == "props":
        props = place_props(int(clip["props_seed"]), half, np.array(zone_xy), zone_r, int(clip["props_count"]))
        isaac.spawn_props(slot, props)
    if site is not None:
        if half * 2 ** 0.5 > float(site["clear_radius_m"]):
            raise RuntimeError(f"arena half {half:.2f} m does not fit the clear patch ({site['clear_radius_m']} m)")
        isaac.move_backdrop(tuple(origins[slot] - np.array(backdrop["spot_m"])))
    isaac.show_only_game(n, slot)
    cam_kw = {}
    if site is not None:
        cam_kw = {"azimuth_deg": float(site["camera_azimuth_deg"]), "elevation_deg": float(site["camera_elevation_deg"]),
                  "distance_scale": float(site["camera_distance_scale"]),
                  "lookat_lift_m": float(site["camera_lookat_lift_m"])}
    eye, look = camera_pose(half, origins[slot], **cam_kw)
    res = tuple(int(v) for v in video["resolution"])
    frame = isaac.make_recorder(sim, eye, look, res)
    # warm-up: render until the stage has loaded and the image settles (textures stream in over many frames)
    warm_min = 150 if site is not None else 40
    for i in range(2000):
        frame()
        if i >= warm_min and isaac.stage_loading_done():
            break
    vram_mib = gpu_used_mib()
    stills = [st for st in sc.get("stills", []) if st["clip"] == clip["name"]]
    max_ticks = int(round(float(video["seconds_max"]) / TICK_S)) if args.smoke_ticks <= 0 else args.smoke_ticks
    if args.stills_only:
        max_ticks = int(round(max([float(st["at_s"]) for st in stills] + [0.0]) / TICK_S)) + 1
        work = work / "stills_only"
        work.mkdir(exist_ok=True)
    writer = imageio.get_writer(str(work / "raw.mp4"), format="FFMPEG", fps=int(video["fps"]), codec="libx264",
                                quality=None, pixelformat="yuv420p", macro_block_size=2,
                                ffmpeg_params=["-crf", "10", "-preset", "fast"], ffmpeg_log_level="error")
    per_frame, pos_log = [], []
    end_step, outcome, upset = 0, 0, False
    f0 = frame()
    writer.append_data(f0)
    imageio.imwrite(str(work / "frame_first.png"), f0)
    per_frame.append({"tick": 0, "time_left_s": float(game.ticks * TICK_S)})
    pos_log.append(game.pos_m[slot].cpu().numpy().tolist())
    alive_slot = game.alive[slot].cpu().numpy()
    for k in range(1, max_ticks + 1):
        out = game.step({"guard": gs.act(obs["guard"]), "strike": ss.act(obs["strike"])})
        done = bool(out.done[slot])
        upset = upset or bool(out.info["upset"][slot])
        if done:
            end_step, outcome = int(out.end_step[slot]), int(out.outcome[slot])
            alive_slot = out.info["final_alive"][slot].cpu().numpy()
            pos = game._starling.world.state()[0][slot].cpu().numpy()          # the world still holds the end pose
        else:
            alive_slot = game.alive[slot].cpu().numpy()
            pos = game.pos_m[slot].cpu().numpy()
        img = frame()
        writer.append_data(img)
        per_frame.append({"tick": k, "time_left_s": float((game.ticks - k) * TICK_S)})
        pos_log.append(pos.tolist())
        for st in stills:
            if abs(k * TICK_S - float(st["at_s"])) < TICK_S / 2:
                take_still(frame, st, half, origins[slot], pos, alive_slot, eye, look, work, cam_kw)
        gs.reset(out.done)
        ss.reset(out.done)
        obs = out.obs
        if done:
            break
    writer.close()
    if args.stills_only:
        for st in stills:                                   # next to the clip's own frames, for the encode step
            for ext in (".png", ".json"):
                os.replace(work / f"{st['name']}{ext}", work.parent / f"{st['name']}{ext}")
        print(f"stills only: {[st['name'] for st in stills]}", flush=True)
        return 0
    imageio.imwrite(str(work / "frame_last.png"), img)
    if outcome == STRIKE_WIN:
        result = f"Strike team reaches the zone at {end_step * TICK_S:.1f} s"
    elif outcome == GUARD_WIN:
        result = ("Guard team holds the zone to the end" if end_step >= game.ticks
                  else f"Guard team wins at {end_step * TICK_S:.1f} s: no Strike drone left")
    else:
        result = None                                              # the clip stops before the game ends
    meta = {
        "clip": clip, "slot": slot, "dry_run": dry, "frames": len(per_frame), "per_frame": per_frame,
        "pos_m": pos_log, "end_step": end_step, "outcome": outcome, "result_text": result, "upset": upset,
        "game_length_s": end_step * TICK_S if end_step else None, "recorded_s": (len(per_frame) - 1) * TICK_S,
        "arena_side_m": 2 * half, "zone_xy_m": zone_xy, "zone_radius_m": zone_r, "props": props,
        "motion": game.motion, "visual": args.visual, "yaw_gains": yaw_gains_text(params),
        "game_config": {"file": pathlib.Path(prov.game_file).name, "sha256": prov.game_sha256}, "local_file": "none",
        "physics_params_source": {k: (v if not isinstance(v, dict) else {kk: vv for kk, vv in v.items()
                                                                          if kk in ("file", "sha256")})
                                  for k, v in params.source.items()},
        "camera_rel_m": {"eye": (np.array(eye) - origins[slot]).tolist(), "lookat": (np.array(look) - origins[slot]).tolist()},
        "backdrop": backdrop, "readback": readback, "vram_used_mib_while_recording": vram_mib,
        "starling_usd": STARLING_USD.name if args.visual == "starling" else None,
        "candidate_games": n, "commit": git_commit(), "working_tree": working_tree_state(),
        "date": datetime.date.today().isoformat(),
        "isaac": isaac.ISAAC_WORLD_LABEL, "wall_s": time.time() - t_start, "fps": int(video["fps"]),
        "resolution": list(res), "smoke": args.smoke_ticks > 0,
    }
    if dry:
        # the same game twice? positions of the clip's slot on every tick both passes played it (the end tick
        # excluded: there the game has already restarted the slot), and the result if the clip shows the end
        dry_end = int(round(dry["first_game_s"][slot] / TICK_S))
        k_max = min(len(pos_log), len(dry_pos), dry_end) - 1
        a = np.asarray(pos_log[:k_max + 1])
        b = np.stack([p[slot] for p in dry_pos[:k_max + 1]])
        live = np.abs(b).max(axis=-1) < 500.0                       # drones that are out are parked far away
        meta["replay_max_pos_diff_m"] = float(np.abs(a - b)[live].max()) if live.any() else 0.0
        meta["replay_ticks_compared"] = k_max + 1
        same_end = (end_step == 0 and dry_end > len(pos_log) - 1) or (end_step == dry_end and
                                                                      outcome == dry["outcome"][slot])
        meta["dry_run_differs"] = bool(meta["replay_max_pos_diff_m"] > 1e-3 or not same_end)
        print(f"replay check: {k_max + 1} ticks, max position difference {meta['replay_max_pos_diff_m']:.2e} m, "
              f"same end {same_end}", flush=True)
    (work / "meta.json").write_text(json.dumps(meta, indent=1))
    print(f"recorded {len(per_frame)} frames, end step {end_step}, result {result!r}, upset {upset}, "
          f"VRAM {vram_mib} MiB, {meta['wall_s']:.0f} s", flush=True)
    return 0


def take_still(frame, st: dict, half: float, origin, pos, alive, eye, look, work: pathlib.Path, cam_kw: dict) -> None:
    """Render one still from the still's view, save it raw to work/<still>.png, put the clip camera back.
    cam_kw: the clip camera's camera_pose settings; the still's own elevation_deg, distance_scale, lookat_lift_m
    override them for its view ("wide", "high"); "close" looks at the live drones' centre."""
    import numpy as np
    import imageio.v2 as imageio

    from svg_training.bench.overlay import camera_pose

    if st["view"] == "close":
        live = np.asarray(pos)[np.asarray(alive, dtype=bool)]
        c = np.asarray(origin) + (live.mean(axis=0) if len(live) else np.array([0.0, 0.0, 1.2]))
        az = np.radians(cam_kw.get("azimuth_deg", -100.0) + 15.0)
        e, lk = c + np.array([2.8 * np.cos(az), 2.8 * np.sin(az), 1.1]), c + np.array([0.0, 0.0, -0.15])
    else:
        kw = {**cam_kw, **{k: float(st[k]) for k in ("elevation_deg", "distance_scale", "lookat_lift_m") if k in st}}
        if st["view"] == "high" and "elevation_deg" not in st:
            kw.pop("elevation_deg", None)
        e, lk = camera_pose(half, origin, view=st["view"], **kw)
    frame.set_view(tuple(float(v) for v in e), tuple(float(v) for v in lk))
    for _ in range(24):                                  # let the renderer's temporal filters settle
        img = frame()
    imageio.imwrite(str(work / f"{st['name']}.png"), img)
    (work / f"{st['name']}.json").write_text(json.dumps({"still": st, "tick_s": st["at_s"]}))
    frame.set_view(eye, look)
    for _ in range(24):
        frame()


# --------------------------------------------------------------------------------------------- encode part
def encode(args) -> int:
    """Overlay + H.264 under max_mb + GIF + sidecar + stills, from runs/s2b_video/<clip>/ (no Isaac)."""
    import numpy as np
    import imageio.v2 as imageio

    from svg_training.bench.overlay import draw_overlay, encode_gif, encode_mp4

    clip, video, sc = load_clip(args.clip, _path(args.config), _path(args.scenes))
    work = _path(args.work) / clip["name"]
    meta = json.loads((work / "meta.json").read_text())
    if meta.get("smoke"):
        print("smoke recording: PNGs only, nothing encoded", flush=True)
        return 0
    caption = clip["caption"] + (SIMPLIFIED if meta["visual"] == "primitive" else "")
    legend = {"Guard team": GUARD_RGB, "Strike team": STRIKE_RGB, "Zone": ZONE_RGB}
    g, s = clip["size"].split("v")
    info = (f"{g} Guard v {s} Strike drones | Guard: {label(clip['guard'])}, Strike: {label(clip['strike'])} | "
            f"{clip['band']} arena {meta['arena_side_m']:.1f} m")
    reader = imageio.get_reader(str(work / "raw.mp4"))
    frames = []
    pf = meta["per_frame"]
    for i, img in enumerate(reader):
        last = i == len(pf) - 1
        frames.append(draw_overlay(img, caption, legend, pf[i]["time_left_s"],
                                   meta["result_text"] if last else None, info))
    reader.close()
    if len(frames) != len(pf):
        raise RuntimeError(f"raw.mp4 has {len(frames)} frames, meta.json {len(pf)}")
    hold_s = 0.0                       # a clip cut before the game ends shows no result: nothing to hold
    if meta["result_text"]:
        hold_s = min(HOLD_S, max(HOLD_MIN_S, float(video["seconds_max"]) - meta["recorded_s"]))
    frames += [frames[-1]] * int(round(hold_s * meta["fps"]))
    meta["hold_s"] = hold_s
    out = _path(args.out)
    mp4, crf = encode_mp4(frames, out / f"{clip['name']}.mp4", fps=meta["fps"], max_mb=float(video["max_mb"]))
    gif_info = None
    if not args.no_gif:
        gif, gif_info = encode_gif(frames, out / f"{clip['name']}.gif", fps=GIF_FPS, max_mb=GIF_MAX_MB,
                                   src_fps=meta["fps"], speed=GIF_SPEED)
    imageio.imwrite(str(work / "check_first.png"), frames[0])
    imageio.imwrite(str(work / "check_middle.png"), frames[len(pf) // 2])
    imageio.imwrite(str(work / "check_last.png"), frames[len(pf) - 1])
    # stills (with the caption burnt in: a render must never pass for a photo)
    stills = []
    for st in [x for x in sc.get("stills", []) if x["clip"] == clip["name"]]:
        raw = work / f"{st['name']}.png"
        if raw.is_file():
            img = draw_overlay(imageio.imread(str(raw))[..., :3], caption, legend,
                               60.0 - float(st["at_s"]), None, info)
            p = out / f"{st['name']}.png"
            imageio.imwrite(str(p), img, compress_level=9)
            stills.append({"name": st["name"], "file": p.name, "bytes": p.stat().st_size, "view": st["view"],
                           "at_s": st["at_s"]})
    write_sidecar(out / f"{clip['name']}.toml", clip, meta, mp4, crf, gif_info, stills, caption)
    print(f"{mp4.name}: {mp4.stat().st_size / 1e6:.2f} MB (crf {crf}); gif {gif_info}; stills {stills}", flush=True)
    return 0


def _toml_value(v) -> str:
    if v is None:
        return '"none"'
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(round(v, 4) if isinstance(v, float) else v)
    if isinstance(v, (list, tuple)):
        return "[" + ", ".join(_toml_value(x) for x in v) + "]"
    return json.dumps(str(v), ensure_ascii=False)


UNKNOWN_TREE = "unknown (not recorded at recording time)"


def recorded_working_tree(meta: dict) -> str:
    """The working-tree state saved in meta.json when the clip was recorded; never the tree at encode time (clips
    recorded before the field existed say so)."""
    return meta.get("working_tree") or UNKNOWN_TREE


def write_sidecar(path: pathlib.Path, clip: dict, meta: dict, mp4: pathlib.Path, crf: int, gif_info, stills,
                  caption: str) -> None:
    """The clip's settings and provenance next to it (TOML). No partner value: committed neutral config only."""
    rows = {
        "clip": clip["name"], "caption": caption, "commit": meta["commit"],
        "working_tree": recorded_working_tree(meta), "date": meta["date"],
        "game_config_file": meta["game_config"]["file"], "game_config_sha256": meta["game_config"]["sha256"],
        "local_file": "none", "size": clip["size"], "band": clip["band"], "arena_side_m": meta["arena_side_m"],
        "zone_radius_m": meta["zone_radius_m"], "guard_strategy": clip["guard"], "strike_strategy": clip["strike"],
        "seed": clip["seed"], "strategy_seeds": [clip["seed"] + 101, clip["seed"] + 202],
        "candidate_games": meta["candidate_games"], "slot": meta["slot"],
        "dry_run_first_game_s": meta["dry_run"].get("first_game_s"),
        "game_length_s": meta["game_length_s"], "recorded_s": meta["recorded_s"],
        "outcome": meta["result_text"] or "the clip ends before the game does", "upset": meta["upset"],
        "motion": meta["motion"], "visual": meta["visual"], "starling_usd": meta["starling_usd"],
        "yaw_gains": meta["yaw_gains"], "scene": clip["scene"],
        "backdrop_file": (meta["backdrop"] or {}).get("file"), "backdrop_sha256": (meta["backdrop"] or {}).get("sha256"),
        "props_seed": clip.get("props_seed"), "props_count": len(meta["props"]),
        "camera_eye_rel_m": meta["camera_rel_m"]["eye"], "camera_lookat_rel_m": meta["camera_rel_m"]["lookat"],
        "fps": meta["fps"], "resolution": meta["resolution"], "hold_last_frame_s": meta["hold_s"],
        "mp4_bytes": mp4.stat().st_size, "mp4_crf": crf,
        "gif_bytes": (path.with_suffix(".gif").stat().st_size if gif_info else None),
        "gif_width": (gif_info or {}).get("width"), "gif_fps": (gif_info or {}).get("fps"),
        "gif_speed_x_real_time": (gif_info or {}).get("speed"),
        "stills": [s_["file"] for s_ in stills], "vram_used_mib_while_recording": meta["vram_used_mib_while_recording"],
        "readback_mass_rel_err": meta["readback"]["mass_rel_err"],
        "readback_inertia_rel_err": meta["readback"]["inertia_rel_err"],
        "readback_has_collider": meta["readback"]["has_collider"], "isaac": meta["isaac"],
        "record_wall_s": meta["wall_s"],
    }
    if "replay_max_pos_diff_m" in meta:     # the recorded game against the dry run (same seed, same strategy seeds)
        rows["replay_ticks_compared"] = meta["replay_ticks_compared"]
        rows["replay_max_pos_diff_m"] = meta["replay_max_pos_diff_m"]
        rows["dry_run_differs"] = meta["dry_run_differs"]
    head = ("# S2b Task 6 clip sidecar, written by scripts/make_s2b_video.py. Training simulator (Isaac Lab), scripted "
            "strategies, not a real flight.\n# Not a measurement: no gates, no ledger row.\n")
    path.write_text(head + "".join(f"{k} = {_toml_value(v)}\n" for k, v in rows.items()))
    tomllib.loads(path.read_text())                                  # it must parse


# --------------------------------------------------------------------------------------------- main
def main() -> int:
    ap = make_parser()
    if "--from-frames" in sys.argv:
        a, _ = ap.parse_known_args()
        return encode(a)
    try:
        load_clip(ap.parse_known_args()[0].clip, _path(ap.parse_known_args()[0].config),
                  _path(ap.parse_known_args()[0].scenes))
    except KeyError as e:
        print(e, file=sys.stderr)
        return 2
    pre = subprocess.run(["bash", str(ROOT / "scripts" / "isaac_preflight.sh"), "--approved-headless"],
                         capture_output=True, text=True)
    print(pre.stdout[-1500:], flush=True)
    work = _path(ap.parse_known_args()[0].work) / ap.parse_known_args()[0].clip
    work.mkdir(parents=True, exist_ok=True)
    (work / "preflight.txt").write_text(pre.stdout + pre.stderr)
    if pre.returncode != 0:
        print(f"preflight exit {pre.returncode}: stop", file=sys.stderr)
        return 11 if pre.returncode == 11 else 1
    from _isaac_app import start_headless
    args, _app = start_headless(ap, cameras=True)
    code = 1
    try:
        code = record(args)
        if code == 0 and args.smoke_ticks <= 0 and not args.stills_only:
            code = encode(args)
    except BaseException:
        traceback.print_exc()
    finally:
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(code)


if __name__ == "__main__":
    sys.exit(main())
