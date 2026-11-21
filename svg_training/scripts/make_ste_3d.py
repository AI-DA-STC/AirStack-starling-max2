#!/usr/bin/env python3
"""STE tasks L0.4 / L0.5 stills and VID-1 part 2 (3-D replay of tier-1 games), drawn in Isaac Lab, headless.

    unset PYTHONPATH
    # Isaac (preflight first; headless, cameras on): stills of the Starling looks, and/or the replay of trajectories
    PYTHONPATH=source ~/miniconda3/envs/env_isaaclab/bin/python scripts/make_ste_3d.py --headless \\
        --work runs/<date>_ste_vid1 [--stills] [--replay runs/<date>_ste_vid1/trajectories/*.npz] [--arena-frame <npz>]
    # encode from the saved raw frames (overlay, MP4, GIF, README tables), no Isaac
    PYTHONPATH=source ~/miniconda3/envs/env_isaaclab/bin/python scripts/make_ste_3d.py --encode --work <same>

**What is drawn.** Display-only Starlings (``compat/isaaclab_232.spawn_display_drone``): the AirStack simulator's own
asset ``AirStack/simulation/isaac-sim/assets/robots/starling2max.usd`` (read only; referenced with its physics schemas
removed in our stage, never in the file) placed by writing its transform. No physics body and no PhysX: in the replay
every position comes from a trajectory file played and checked in tier 1 (``scripts/ste_vid1_capture.py``), so nothing
here can change a game. Tier 1 has no roll or pitch: drones are drawn level, turned by the game's yaw. A drone tagged
out disappears from the frame it is out.

**Stills** (``--stills``; L0.4 and L0.5): two rows of drones on a plain floor, each from a close 3-D view and from above,
and the six drones of one replayed game frame (``--arena-frame``, its middle tick) in the arena from both clip cameras
with each look. Row L0.4: the Starling as the file draws it (no paint), today's clip paint without the ball, today's
clip look (paint and ball) for each team. Row L0.5: the file's look, then the two proposed looks (``own_ring``,
``own_dot``) for each team. Labels and a caption are burnt in on ``--encode``.

**Replay** (``--replay``): per trajectory, one pass per camera (top view, then 3-D view; the renderer's temporal filter
settles ``settle_frames`` renders per tick), one frame per 0.05 s tick, raw H.264 (crf 10) under ``<work>/render/``.

Outputs of ``--encode``: ``docs/media/ste_l011/3d/<variant>_<outcome>_{top,3d}.{mp4,gif}`` and README.md there;
stills in ``docs/media/ste_l04/`` (L0.4) and ``docs/media/ste_l05/`` (L0.5) with README.md each.
Not a measurement: no gates, no record, no ledger row. Exit 0 done, 1 crash, 2 bad arguments, 11 GPU busy.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
sys.path.insert(0, str(ROOT / "scripts"))

from svg_training.viz import replay3d as r3  # noqa: E402
from svg_training.viz.starling_look import SETTINGS_FILE, load_video_settings, look_plan  # noqa: E402

STARLING_USD = (ROOT / ".." / "AirStack" / "simulation" / "isaac-sim" / "assets" / "robots" / "starling2max.usd")
GUARD_RGB = (0, 114, 178)          # Okabe-Ito blue (as scripts/make_s2b_video.py)
STRIKE_RGB = (230, 159, 0)         # Okabe-Ito orange (legend)
STRIKE_RENDER_RGB = (240, 95, 0)   # deeper on the drones: the renderer's tone curve turns Okabe-Ito orange yellow
ZONE_RGB = (0, 158, 115)
LEGEND = {"Guard team": GUARD_RGB, "Strike team": STRIKE_RGB, "Zone": ZONE_RGB}
LEGEND_3D = {**LEGEND, "x tagged out": (190, 190, 190)}      # replay clips: a cross where a drone was tagged out
GIF_WIDTHS = (800, 720, 640, 560, 480)                          # narrower first, before fewer frames per second
CAMERAS = ("top", "3d")
CAMERA_NAMES = {"top": "top view", "3d": "3-D view"}
MEDIA = ROOT / "docs" / "media"   # <media>/ste_l011/3d (replays), <media>/ste_l04 and <media>/ste_l05 (stills)
CLIP_SIDE_M = 6.5                  # the S2b painted ball's radius follows the arena: 0.03 + 0.0094 x side (S2b Task 6)
ROW_Z_M = 1.0                      # stills: drones in the air at this height
ROW_GAP_M = 0.75
ROW_Y_M = (30.0, 40.0)             # the two still rows stand far from the arena (out of every arena view)
STILLS_CAPTION = ("Render in Isaac Lab of the Starling 2 Max asset of the AirStack simulator (same file, our renderer, "
                  "our lights); not a photo, not the AirStack simulator's own window")


def team_rgb(team: str) -> tuple:
    return tuple(c / 255 for c in (GUARD_RGB if team == "guard" else STRIKE_RENDER_RGB))


def painted_marker_radius_m(side_m: float = CLIP_SIDE_M) -> float:
    return 0.03 + 0.0094 * side_m


def row_specs() -> dict:
    """The two still rows: [(label, look or None = the file as it is, team, ball)]."""
    return {
        "l04": [("AirStack asset, no paint", None, "guard", False),
                ("today's paint, no ball", "painted", "guard", False),
                ("today's clip look, Guard", "painted", "guard", True),
                ("today's clip look, Strike", "painted", "strike", True)],
        "l05": [("AirStack asset, no paint", None, "guard", False),
                ("proposed ring, Guard", "own_ring", "guard", True),
                ("proposed ring, Strike", "own_ring", "strike", True),
                ("proposed dot, Guard", "own_dot", "guard", True),
                ("proposed dot, Strike", "own_dot", "strike", True)],
    }


def plan_for(look: str | None, team: str, settings: dict, ball: bool = True):
    """The look plan of one drone; look None = the USD untouched, no marker."""
    from svg_training.viz.starling_look import LookPlan

    if look is None:
        return LookPlan("file", {}, ())
    p = look_plan(look, team_rgb(team), marker_radius_m=painted_marker_radius_m(), settings=settings)
    return p if ball else LookPlan(p.look, p.paint, ())


def row_positions(n: int, y_m: float) -> np.ndarray:
    """[n, 3] drone positions of a still row, centred on x = 0."""
    x = (np.arange(n) - (n - 1) / 2) * ROW_GAP_M
    return np.stack((x, np.full(n, y_m), np.full(n, ROW_Z_M)), axis=-1)


def row_views(n: int, y_m: float) -> dict:
    """Close 3-D view (front-left, above) and a top view of a still row: {name: (eye, lookat)}."""
    half_w = (n - 1) / 2 * ROW_GAP_M + 0.45
    d = half_w / np.tan(np.radians(30.0)) * 0.95
    look = np.array([0.0, y_m, ROW_Z_M])
    el, az = np.radians(28.0), np.radians(-90.0)
    eye = look + d * np.array([np.cos(az) * np.cos(el), np.sin(az) * np.cos(el), np.sin(el)])
    top_eye = look + np.array([0.0, -d * np.sin(np.radians(2.0)), d * np.cos(np.radians(2.0))])
    return {"close": (tuple(eye), tuple(look)), "top": (tuple(top_eye), tuple(look))}


def label_anchor(xyz_m, view, view_name: str, res: tuple[int, int]) -> list:
    """Pixel (x, y) where a drone's label goes: under the drone (0.22 m lower) in the close view; in the top view
    (where lower is the same pixel) a fixed 0.3 m south of it."""
    off = np.array([0.0, -0.3, 0.0]) if view_name == "top" else np.array([0.0, 0.0, -0.22])
    return r3.to_pixels(np.asarray(xyz_m, float)[None] + off, view[0], view[1], res)[0].tolist()


def frame_poses(t: r3.Trajectory, k: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    return t.pos_m[k], t.yaw_rad[k], t.alive[k]


def drone_teams(t: r3.Trajectory) -> list[str]:
    return ["guard"] * t.guards + ["strike"] * t.strikes


# ============================================================================================ Isaac part
def make_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--work", required=True, help="working folder (runs/..., git-ignored): raw frames and meta")
    ap.add_argument("--settings", default=str(SETTINGS_FILE))
    ap.add_argument("--stills", action="store_true")
    ap.add_argument("--replay", nargs="*", default=[], help="trajectory files (.npz) to replay")
    ap.add_argument("--arena-frame", default=None, help="a trajectory whose middle tick the arena stills show")
    ap.add_argument("--encode", action="store_true", help="encode from <work> only, no Isaac")
    ap.add_argument("--smoke", action="store_true", help="render a few frames only (PNG checks)")
    ap.add_argument("--media", default=str(MEDIA), help="media root (tests point it at a temporary folder)")
    ap.add_argument("--clip-drone-dir", default=None,
                    help="encode: folder with before_fix.png / after_fix.png of scripts/ste_l04_clip_drone_still.py")
    ap.add_argument("--record-run-dir", default=None,
                    help="encode: the recorded run folder, for each cell's hold and reach counts in the README")
    return ap


def render(args, isaac, frame_factory=None) -> int:
    """Isaac mode (after the app started; ``isaac`` = compat/isaaclab_232 or a stand-in in tests)."""
    import imageio.v2 as imageio

    settings = load_video_settings(args.settings)
    work = Path(args.work)
    work.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    usd = str(STARLING_USD.resolve())
    res = tuple(int(v) for v in settings["cameras"]["resolution"])
    pb = settings["playback"]
    sim = isaac.make_display_sim(getattr(args, "device", "cuda:0") or "cuda:0")
    isaac.spawn_world_lights(sun=True)
    isaac.spawn_floor()
    trajs = [r3.load_trajectory(p) for p in args.replay]
    arena_t = r3.load_trajectory(args.arena_frame) if args.arena_frame else (trajs[0] if trajs else None)
    # the arena (one for every trajectory: refused if they differ)
    ref = arena_t if arena_t is not None else None
    for t in trajs:
        if (t.half_m, t.zone_radius_m, tuple(t.zone_centre_m), t.guards, t.strikes) != (
                ref.half_m, ref.zone_radius_m, tuple(ref.zone_centre_m), ref.guards, ref.strikes):
            raise ValueError("the trajectories play in different arenas; replay them in separate launches")
    if ref is not None:
        isaac.spawn_display_arena("/World/Arena", ref.half_m, tuple(float(v) for v in ref.zone_centre_m),
                                  ref.zone_radius_m, ref.wall_margin_m, float(ref.height_band_m[1]))
    # drones: one set per look in the arena (replay look first), and the still rows
    sets = {}
    arena_looks = [settings["look"]["replay_look"]]
    if args.stills:
        arena_looks += [lk for lk in ("painted", "own_ring", "own_dot") if lk not in arena_looks]
    seg = (int(settings["look"]["own_ring"]["segments"]), int(settings["look"]["own_ring"]["tube_segments"]))
    if ref is not None:
        for lk in arena_looks:
            paths = []
            for m, team in enumerate(drone_teams(ref)):
                p = f"/World/Drones_{lk}/Drone_{m}"
                isaac.spawn_display_drone(p, usd, plan_for(lk, team, settings), seg)
                paths.append(p)
            sets[lk] = paths
    rows = {}
    if args.stills:
        for (name, spec), y in zip(row_specs().items(), ROW_Y_M):
            pos = row_positions(len(spec), y)
            paths = []
            for i, (label, lk, team, ball) in enumerate(spec):
                p = f"/World/Row_{name}/Drone_{i}"
                isaac.spawn_display_drone(p, usd, plan_for(lk, team, settings, ball), seg)
                isaac.set_display_pose(p, pos[i], 0.0, True)
                paths.append(p)
            rows[name] = (spec, pos, paths)
    isaac.display_play(sim)
    cams = (r3.camera_poses(ref.half_m, float(ref.height_band_m[1]), float(settings["cameras"]["top_tilt_deg"]),
                            settings["cameras"]["perspective_view"], wall_margin_m=ref.wall_margin_m)
            if ref is not None else None)
    first_view = cams[0] if cams else row_views(4, ROW_Y_M[0])["close"]
    frame = (frame_factory or isaac.make_recorder)(sim, first_view[0], first_view[1], res)

    def show_set(look: str | None) -> None:
        for lk, paths in sets.items():
            for p in paths:
                isaac.set_visible(p, lk == look)

    def settle(view, n: int) -> np.ndarray:
        frame.set_view(view[0], view[1])
        img = None
        for _ in range(max(n, 1)):
            img = frame()
        return img

    def place(paths, t: r3.Trajectory, k: int) -> None:
        pos, yaw, alive = frame_poses(t, k)
        for m, p in enumerate(paths):
            isaac.set_display_pose(p, pos[m], float(yaw[m]), bool(alive[m]))

    meta = {"date": datetime.date.today().isoformat(), "commit": _git_commit(), "working_tree": _working_tree_state(),
            "starling_usd": STARLING_USD.name,
            "starling_usd_sha256": _sha256(STARLING_USD), "resolution": list(res), "isaac": getattr(
                isaac, "ISAAC_WORLD_LABEL", "stand-in"), "settings_file": Path(args.settings).name,
            "settings_sha256": _sha256(Path(args.settings)), "stills": [], "replays": []}
    stills_dir = work / "stills_raw"
    if args.stills:
        stills_dir.mkdir(exist_ok=True)
        show_set(None)
        for name, (spec, pos, _) in rows.items():
            for vname, view in row_views(len(spec), pos[0, 1]).items():
                img = settle(view, int(pb["warm_frames"]))
                f = stills_dir / f"row_{name}_{vname}.png"
                imageio.imwrite(str(f), img)
                labels = [(spec[i][0], label_anchor(pos[i], view, vname, res)) for i in range(len(spec))]
                meta["stills"].append({"file": f.name, "row": name, "view": vname, "eye": list(view[0]),
                                       "lookat": list(view[1]), "labels": labels})
        if ref is not None:
            k = ref.end_step // 2
            for lk in arena_looks:
                show_set(lk)
                place(sets[lk], ref, k)
                for cam, view in zip(CAMERAS, cams):
                    img = settle(view, int(pb["warm_frames"]))
                    f = stills_dir / f"arena_{lk}_{cam}.png"
                    imageio.imwrite(str(f), img)
                    meta["stills"].append({"file": f.name, "row": "arena", "look": lk, "view": cam,
                                           "tick": int(k), "trajectory": Path(args.arena_frame or args.replay[0]).name,
                                           "eye": list(view[0]), "lookat": list(view[1])})
    look = settings["look"]["replay_look"]
    for path, t in zip(args.replay, trajs):
        show_set(look)
        stem = Path(path).stem
        rec = {"trajectory": Path(path).name, "trajectory_path": str(Path(path).resolve()), "stem": stem, "frames": int(t.end_step + 1), "cameras": {}}
        last = 3 if args.smoke else t.end_step
        for cam, view in zip(CAMERAS, cams):
            out = work / "render" / stem
            out.mkdir(parents=True, exist_ok=True)
            place(sets[look], t, 0)
            settle(view, int(pb["warm_frames"]))
            writer = imageio.get_writer(str(out / f"raw_{cam}.mp4"), format="FFMPEG", fps=20, codec="libx264",
                                        quality=None, pixelformat="yuv420p", macro_block_size=2,
                                        ffmpeg_params=["-crf", "10", "-preset", "fast"], ffmpeg_log_level="error")
            for k in range(last + 1):
                place(sets[look], t, k)
                img = None
                # the last frame is held with the result: let the renderer settle fully (no ghost of a drone just out)
                for _ in range(int(pb["warm_frames"] if k == last else pb["settle_frames"])):
                    img = frame()
                writer.append_data(img)
                if k in (0, last // 2, last):
                    imageio.imwrite(str(out / f"check_{cam}_{k:04d}.png"), img)
            writer.close()
            rec["cameras"][cam] = {"eye": list(view[0]), "lookat": list(view[1]), "frames": last + 1}
        meta["replays"].append(rec)
        print(f"replayed {stem}: {last + 1} frames x {len(CAMERAS)} cameras", flush=True)
    meta["wall_s"] = time.time() - t0
    meta["smoke"] = bool(args.smoke)
    (work / "render_meta.json").write_text(json.dumps(meta, indent=1))
    print(f"render done in {meta['wall_s']:.0f} s", flush=True)
    return 0


def _git_commit() -> str:
    r = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short=12", "HEAD"], capture_output=True, text=True)
    return r.stdout.strip() or "unknown"


def _working_tree_state() -> str:
    """'clean', or the pipeline files that differ from the commit (the render was made from a working tree)."""
    r = subprocess.run(["git", "-C", str(ROOT), "--no-optional-locks", "status", "--porcelain", "--", "scripts",
                        "source", "configs"],
                       capture_output=True, text=True)
    files = sorted({ln[3:].strip() for ln in r.stdout.splitlines() if ln.strip()})
    return "clean" if not files else "uncommitted changes: " + ", ".join(files)


def _sha256(path: Path) -> str:
    import hashlib

    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


# ============================================================================================ encode part
def label_still(img: np.ndarray, labels: list, caption: str) -> np.ndarray:
    """Burn the drone labels (centred under each drone) and a caption band into a copy of a still."""
    import cv2

    from svg_training.bench.overlay import _ascii, _dark_box, _text, wrap_caption

    out = np.ascontiguousarray(img[..., :3].copy())
    h, w = out.shape[:2]
    k = h / 720.0
    for text, (x, y) in labels:
        text = _ascii(text)
        tw, th = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.55 * k, 1)[0]
        x0, y0 = int(x - tw / 2) - 6, int(y) + 6
        _dark_box(out, x0, y0, x0 + tw + 12, y0 + th + 12)
        _text(out, text, x0 + 6, y0 + th + 6, 0.55 * k, (255, 255, 255), 1)
    lines = wrap_caption(_ascii(caption), w, 0.62 * k, 1)
    band = int(30 * k) * len(lines) + int(16 * k)
    _dark_box(out, 0, h - band, w, h)
    for i, line in enumerate(lines):
        _text(out, line, int(20 * k), h - band + int(30 * k) * (i + 1), 0.62 * k, (255, 255, 255), 1)
    return out


def encode(args) -> int:
    import imageio.v2 as imageio

    from svg_training.bench.overlay import draw_overlay, encode_gif, encode_mp4

    settings = load_video_settings(args.settings)
    pb = settings["playback"]
    work = Path(args.work)
    meta = json.loads((work / "render_meta.json").read_text())
    if meta.get("smoke"):
        print("smoke render: PNG checks only, nothing encoded", flush=True)
        return 0
    media = Path(args.media)
    rec_dir = getattr(args, "record_run_dir", None)
    if rec_dir:                                     # counts only from the record the settings pin
        have = _sha256(Path(rec_dir) / "gates.toml")
        if have != settings["key_games"]["gates_sha256"]:
            raise ValueError(f"{rec_dir}: gate file sha256 {have}, the settings pin {settings['key_games']['gates_sha256']}")
    res = tuple(meta["resolution"])
    rows_out = []
    fps = r3.playback_fps(float(pb["speed_x"]))
    for rec in meta["replays"]:
        t = r3.load_trajectory(rec["trajectory_path"])
        m = t.meta
        result = r3.outcome_text(t.outcome, t.end_step, int(m["tags"]), int(t.alive[-1, :t.guards].sum()))
        cap = r3.caption(m["variant"], float(pb["speed_x"]))
        files = {}
        for cam in CAMERAS:
            info = r3.info_line(m["variant"], t.guards, t.strikes, m["guard"], m["strike"], int(m["game_index"]),
                                2 * t.half_m) + f" | {CAMERA_NAMES[cam]}"
            view = rec["cameras"][cam]
            reader = imageio.get_reader(str(work / "render" / rec["stem"] / f"raw_{cam}.mp4"))
            frames = []
            raw = [img for img in reader]          # list(reader) asks len(): inf for a video
            reader.close()
            if len(raw) != rec["frames"]:
                raise RuntimeError(f"{rec['stem']} {cam}: {len(raw)} raw frames, expected {rec['frames']}")
            for k, img in enumerate(raw):
                end = k == len(raw) - 1
                img = draw_tag_crosses(img, t, k, view["eye"], view["lookat"], res)
                frames.append(draw_overlay(img, cap, LEGEND_3D, 0.0, result if end else None, info,
                                           clock=f"t = {k * 0.05:4.2f} s"))
            frames += [frames[-1]] * r3.hold_frames(float(pb["hold_s"]), fps)
            stem = f"{rec['stem']}_{cam}"
            d3 = media / "ste_l011" / "3d"
            mp4, crf = encode_mp4(frames, d3 / f"{stem}.mp4", fps=fps, max_mb=float(pb["mp4_max_mb"]))
            gif, gi = gif_full_rate(frames, d3 / f"{stem}.gif", fps, float(pb["gif_max_mb"]))
            out = work / "render" / rec["stem"]
            imageio.imwrite(str(out / f"overlay_{cam}_first.png"), frames[0])
            imageio.imwrite(str(out / f"overlay_{cam}_mid.png"), frames[len(raw) // 2])
            imageio.imwrite(str(out / f"overlay_{cam}_last.png"), frames[len(raw) - 1])
            files[cam] = {"mp4": mp4.name, "mp4_mb": round(mp4.stat().st_size / 1e6, 2), "crf": crf,
                          "gif": gi | {"file": gif.name, "mb": round(gif.stat().st_size / 1e6, 2)}}
        counts = None
        if rec_dir:
            with np.load(Path(rec_dir) / "cells" / (m["batch"].replace("/", "__") + ".npz")) as d:
                out_all = d["outcome"]
            n = games_per_cell(m)
            counts = r3.cell_counts(out_all[int(m["cell_index"]) * n:(int(m["cell_index"]) + 1) * n])
        rows_out.append({"rec": rec, "traj": t, "files": files, "result": result, "counts": counts})
    if rows_out:
        write_3d_readme(rows_out, meta, settings, media / "ste_l011" / "3d")
    if meta["stills"]:
        write_stills(work, meta, settings, media, getattr(args, "clip_drone_dir", None))
    print("encode done", flush=True)
    return 0


def games_per_cell(meta: dict) -> int:
    """Games per cell of the trajectory's batch: stored by the capture, else from its global and cell indices."""
    if "games_per_cell" in meta:
        return int(meta["games_per_cell"])
    ci = int(meta["cell_index"])
    if ci == 0:
        raise ValueError("games per cell unknown for cell 0 without meta games_per_cell")
    return (int(meta["global_index"]) - int(meta["game_index"])) // ci


def draw_tag_crosses(img: np.ndarray, t: r3.Trajectory, k: int, eye, lookat, res: tuple) -> np.ndarray:
    """A team-coloured cross (dark outline) at the last place of every drone out of the game at tick k."""
    import cv2

    marks = r3.tagged_marks(t.pos_m, t.alive, k)
    if not marks:
        return img
    out = np.ascontiguousarray(img[..., :3].copy())
    h = out.shape[0]
    r = max(int(round(9 * h / 720)), 3)
    px = r3.to_pixels(np.array([p for _, p in marks]), eye, lookat, res)
    for (m, _), (x, y) in zip(marks, px):
        if not np.isfinite([x, y]).all():
            continue
        col = GUARD_RGB if m < t.guards else STRIKE_RGB
        x, y = int(round(x)), int(round(y))
        for colour, width in (((20, 20, 24), 6), (col, 3)):
            cv2.line(out, (x - r, y - r), (x + r, y + r), colour, width, cv2.LINE_AA)
            cv2.line(out, (x - r, y + r), (x + r, y - r), colour, width, cv2.LINE_AA)
    return out


def gif_full_rate(frames: list, path: Path, fps: int, max_mb: float) -> tuple[Path, dict]:
    """A GIF that keeps every frame (fps = the playback fps) at the widest width that fits max_mb; only if no width
    fits, the encoder's own fallback (fewer frames per second, same playback speed)."""
    from svg_training.bench.overlay import encode_gif

    gi = None
    for w in GIF_WIDTHS:
        gif, gi = encode_gif(frames, path, fps=fps, max_mb=max_mb, src_fps=fps, speed=1.0, widths=(w,))
        if gi["fps"] == fps:
            return gif, gi
    return gif, gi


def replay_caption_md(t: r3.Trajectory, result: str) -> str:
    """The README caption of one game (2-4 sentences, <= 400 characters)."""
    m = t.meta
    result = result.replace("holds:", f"holds at {t.end_time_s:.1f} s:")     # the banner leaves the time to the clock
    return (f"{r3._short(m['guard']).capitalize()} Guards v {r3._short(m['strike'])} Strikes, game {m['game_index']} of "
            f"the {m['variant']} cell in record {m['record']}: {result}. Training simulator tier 1, replayed in Isaac "
            f"Lab for drawing only (drones drawn level); not a flight.")


def write_3d_readme(rows: list, meta: dict, settings: dict, dest: Path) -> None:
    kg = settings["key_games"]
    lines = [
        "# 3-D replays of the L0.11 key games (VID-1)",
        "",
        f"Training simulator. Each game is a tier-1 game of the L0.11 screen (record {kg['record']}) played again on "
        "the record's device with the same starts, seeds and batch, checked equal to the record (outcome, end step, "
        "tags, Strike drones left, start positions) and then drawn in Isaac Lab with the Starling asset of the "
        "AirStack simulator. Visual replay only: no physics runs in the drawing, nothing changes the game. Tier 1 has "
        "no roll or pitch, so the drones are drawn level; a tagged drone disappears. Look: "
        f"`{settings['look']['replay_look']}` (PROPOSED, pending the owner's check of the L0.5 stills, D9). "
        f"Played at {settings['playback']['speed_x']:g}x real time. Not a flight.",
        "",
        "Rule for the games (fixed before the replay): in each shortlisted variant, the best scripted Guard against "
        "the best scripted Strike (g* v s*), the lowest game index that ended in a hold and the lowest that ended in a "
        "reach.",
        "",
        "One hold and one reach per variant are shown; the column \"In the record\" gives how often each outcome "
        "happened in that cell, so the pair is not a 50/50 split. A cross marks where a drone was "
        "tagged out; in these 3v3 holds every Strike drone was traded for a Guard drone (T44). The zone is drawn as a "
        "10-sided disc inside the true circle, so a Strike drone that reaches the circle's edge can sit just outside "
        "the drawn edge.",
        "",
        "| Variant | Game | In the record | Top view | 3-D view | Caption |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        t, f, c = r["traj"], r["files"], r["counts"]
        cap = replay_caption_md(t, r["result"])
        if len(cap) > 400:
            raise ValueError(f"caption over 400 characters: {cap}")
        rec_txt = (f"{c['holds']} holds and {c['reaches']} reaches of {c['games']}" if c else "not read")
        lines.append(f"| {t.meta['variant']} | {t.meta['outcome_name']}, game {t.meta['game_index']} | {rec_txt} | "
                     f"![]({f['top']['gif']['file']}) [MP4]({f['top']['mp4']}) | "
                     f"![]({f['3d']['gif']['file']}) [MP4]({f['3d']['mp4']}) | {cap} |")
    g = rows[0]["files"]["top"]["gif"]
    lines += ["", f"GIF {g['width']} px wide, {g['fps']} frames/s (every tick kept) unless a row says otherwise; MP4 "
              f"1280 x 720 at the same rate."]
    for r in rows:
        for cam in CAMERAS:
            gi = r["files"][cam]["gif"]
            if (gi["width"], gi["fps"]) != (g["width"], g["fps"]):
                lines.append(f"`{gi['file']}`: {gi['width']} px wide, {gi['fps']} frames/s.")
    tree = meta.get("working_tree", "unknown (not recorded at render time)")
    lines += ["", f"Made by `scripts/make_ste_3d.py` from `scripts/ste_vid1_capture.py` trajectories; commit "
              f"{meta['commit']} (working tree: {tree}), {meta['date']}, {meta['isaac']}, asset "
              f"`{meta['starling_usd']}` (sha256 {meta['starling_usd_sha256'][:12]}...).", ""]
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "README.md").write_text("\n".join(lines))


STILL_CAPTIONS = {
    "row_l04_close": "L0.4: the Starling asset of the AirStack simulator as the file draws it (left) beside today's "
                     "clip paint and the clip look with its team ball. Same file and renderer; only paint and ball "
                     "differ. Until the fix below, the clips also drew a grey box over the drone.",
    "row_l04_top": "L0.4 from above: the same four drones. Today's clip paint turns the body dark and the rotors to the "
                   "team colour; the ball hides the drone from above.",
    "clip_drone_before_fix": "L0.4 finding: the S2b and NUS Isaac clips drew this. Their own code path (IsaacWorld) "
                             "left the grey physics box (0.19 x 0.26 x 0.05 m) visible over the Starling: the hide "
                             "call hit a prim that cannot be hidden. Box, rotor paint and ball made it unlike the "
                             "Starling.",
    "clip_drone_after_fix": "The same code path after the one-line fix (the box's own mesh is hidden): the Starling "
                            "with today's paint and ball, as in the row above. Visual only; the box never had a "
                            "collider.",
    "row_l05_close": "L0.5: the file's own look (left), then the two proposed team markers: a thin ring around the "
                     "drone and a small dot on its top. The drone itself is not painted.",
    "row_l05_top": "L0.5 from above: the ring stays visible around the drone; the dot sits on the top plate.",
}


def write_stills(work: Path, meta: dict, settings: dict, media: Path, clip_drone_dir: str | None = None) -> None:
    import imageio.v2 as imageio

    media_l04, media_l05 = media / "ste_l04", media / "ste_l05"
    media_l04.mkdir(parents=True, exist_ok=True)
    media_l05.mkdir(parents=True, exist_ok=True)
    done = {"l04": [], "l05": []}
    for s in meta["stills"]:
        img = imageio.imread(str(work / "stills_raw" / s["file"]))
        stem = Path(s["file"]).stem
        if s["row"] == "arena":
            lk, cam = s["look"], s["view"]
            dest = media_l05
            cap = (f"Look `{lk}` at clip scale, {CAMERA_NAMES[cam]}: the six drones of a replayed L0.11 game frame "
                   f"(tick {s['tick']}). Training simulator, drawing only.")
            out = label_still(img, [], STILLS_CAPTION)
            done["l05"].append((stem, cap))
        else:
            dest = media_l04 if s["row"] == "l04" else media_l05
            out = label_still(img, s["labels"], STILLS_CAPTION)
            done[s["row"]].append((stem, STILL_CAPTIONS[stem]))
        imageio.imwrite(str(dest / f"{stem}.png"), out, compress_level=9)
    for which in ("before_fix", "after_fix"):
        src = Path(clip_drone_dir) / f"{which}.png" if clip_drone_dir else None
        if src is not None and src.is_file():
            stem = f"clip_drone_{which}"
            out = label_still(imageio.imread(str(src)), [], STILLS_CAPTION)
            imageio.imwrite(str(media_l04 / f"{stem}.png"), out, compress_level=9)
            done["l04"].append((stem, STILL_CAPTIONS[stem]))
    for name, dest, title in (("l04", media_l04, "L0.4 Side-by-side Starling render"),
                              ("l05", media_l05, "L0.5 Starling video look fix: stills for the owner's check (D9)")):
        lines = [f"# {title}", "", "Renders in Isaac Lab (Isaac Sim 5.1, the same version as the AirStack simulator) "
                 "of the AirStack simulator's own Starling file, `AirStack/simulation/isaac-sim/assets/robots/"
                 "starling2max.usd` (read only). The file carries no material and no colour, and the AirStack simulator "
                 "adds none when it spawns it (Pegasus `vehicle.py` and `starling2max.py`, read), so the AirStack "
                 "simulator should draw the renderer's default surface too (read from the files and code; not "
                 "verified in its window). Not compared: the AirStack simulator's own lights, world, "
                 "camera and spinning rotors (Pegasus turns the rotor joints); no AirStack window was opened (rule: "
                 "the AirStack simulator is not run for this task).", ""]
        for stem, cap in done[name]:
            if len(cap) > 400:
                raise ValueError(f"caption over 400 characters: {cap}")
            lines += [f"**{stem}.** {cap}", "", f"![{stem}]({stem}.png)", ""]
        (dest / "README.md").write_text("\n".join(lines))


# ============================================================================================ main
def main() -> int:
    ap = make_parser()
    if "--encode" in sys.argv[1:]:
        a, _ = ap.parse_known_args()
        return encode(a)
    a0, _ = ap.parse_known_args()
    if not a0.stills and not a0.replay:
        print("nothing to do: give --stills and/or --replay", file=sys.stderr)
        return 2
    pre = subprocess.run(["bash", str(ROOT / "scripts" / "isaac_preflight.sh"), "--approved-headless"],
                         capture_output=True, text=True)
    print(pre.stdout[-1500:], flush=True)
    Path(a0.work).mkdir(parents=True, exist_ok=True)
    (Path(a0.work) / "preflight.txt").write_text(pre.stdout + pre.stderr)
    if pre.returncode != 0:
        print(f"preflight exit {pre.returncode}: stop", file=sys.stderr)
        return 11 if pre.returncode == 11 else 1
    from _isaac_app import start_headless
    args, _app = start_headless(ap, cameras=True)
    code = 1
    try:
        from svg_training.compat import isaaclab_232 as isaac
        code = render(args, isaac)
    except BaseException:
        traceback.print_exc()
    finally:
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(code)


if __name__ == "__main__":
    sys.exit(main())
