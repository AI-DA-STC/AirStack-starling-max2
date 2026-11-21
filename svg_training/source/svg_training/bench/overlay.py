"""Pure helpers of the S2b video script (scripts/make_s2b_video.py): the burnt-in overlay, the clip rule, the props
layout, the camera pose and the H.264 / GIF encoders under a size cap.

NumPy and OpenCV only, called by the video script on frames already copied to the host. Never imported by the game,
the layers or the worlds (nothing here runs in a training step). Frames are [H, W, 3] uint8 RGB."""
from __future__ import annotations

import subprocess
from pathlib import Path

import cv2
import numpy as np

FONT = cv2.FONT_HERSHEY_SIMPLEX
WHITE = (255, 255, 255)
BAND_ALPHA = 0.62            # how dark the caption band and the boxes are (0 = clear, 1 = black)


# --------------------------------------------------------------------------------------------- overlay
def _scale(h: int) -> float:
    return h / 720.0


def wrap_caption(caption: str, width_px: int, font_scale: float = 0.72, thickness: int = 2,
                 margin_px: int = 24) -> list[str]:
    """Split caption into lines that fit width_px at the overlay's font (words are never broken)."""
    words, lines, cur = caption.split(), [], ""
    for w in words:
        trial = w if not cur else cur + " " + w
        if cv2.getTextSize(trial, FONT, font_scale, thickness)[0][0] <= width_px - 2 * margin_px or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _ascii(s: str | None) -> str | None:
    """OpenCV's Hershey fonts draw ASCII only: dashes become " - ", anything else non-ASCII becomes "?"."""
    if s is None:
        return None
    s = s.replace(" \u2014 ", " - ").replace("\u2014", " - ").replace("\u2013", "-").replace("\u00d7", "x")
    return s.encode("ascii", "replace").decode()


def _dark_box(img: np.ndarray, x0: int, y0: int, x1: int, y1: int) -> None:
    x0, y0 = max(x0, 0), max(y0, 0)
    x1, y1 = min(x1, img.shape[1]), min(y1, img.shape[0])
    if x1 > x0 and y1 > y0:
        img[y0:y1, x0:x1] = (img[y0:y1, x0:x1].astype(np.float32) * (1.0 - BAND_ALPHA)).astype(np.uint8)


def _text(img: np.ndarray, s: str, x: int, y: int, scale: float, colour=WHITE, thickness: int = 2) -> None:
    cv2.putText(img, s, (x, y), FONT, scale, colour, thickness, cv2.LINE_AA)


def draw_overlay(frame: np.ndarray, caption: str, legend: dict[str, tuple[int, int, int]], time_left_s: float,
                 outcome: str | None, info: str | None = None, clock: str | None = None) -> np.ndarray:
    """Burn the overlay into a copy of frame [H, W, 3] uint8 RGB and return it.

    caption: bottom band (wrapped to the width, one or more lines); legend: label -> RGB colour, top left;
    time_left_s: top right ("time left 12.3 s"); outcome: a banner at the top centre (None = the game is still running or
    the clip stops before the end); info: one small grey line above the caption (matchup, arena), optional;
    clock: if given, this text replaces "time left ..." in the top-right box (VID-1: the game clock "t = 1.35 s").
    """
    img = np.ascontiguousarray(frame.copy())
    caption, info, outcome = _ascii(caption), _ascii(info), _ascii(outcome)
    h, w = img.shape[:2]
    k = _scale(h)
    pad = int(round(12 * k))
    # caption band (bottom): the info line (small, grey) above the caption lines
    cs, ct = 0.72 * k, max(1, int(round(2 * k)))
    lines = wrap_caption(caption, w, cs, ct, int(round(24 * k)))
    line_h = int(round(34 * k))
    info_h = int(round(28 * k)) if info else 0
    band_h = line_h * len(lines) + info_h + 2 * pad
    _dark_box(img, 0, h - band_h, w, h)
    if info:
        _text(img, info, int(round(24 * k)), h - band_h + pad + info_h - int(round(6 * k)), 0.56 * k,
              (215, 215, 215), max(1, ct - 1))
    for i, line in enumerate(lines):
        _text(img, line, int(round(24 * k)), h - band_h + pad + info_h + line_h * (i + 1) - int(round(9 * k)), cs,
              WHITE, ct)
    # legend (top left)
    ls = 0.66 * k
    rows = list(legend.items())
    lw = max([cv2.getTextSize(s_, FONT, ls, ct)[0][0] for s_, _ in rows] + [0]) + int(round(56 * k))
    row_h = int(round(32 * k))
    _dark_box(img, pad, pad, pad + lw, pad + row_h * len(rows) + pad)
    for i, (label, rgb) in enumerate(rows):
        cy = pad + int(round(8 * k)) + row_h * i + row_h // 2
        cv2.circle(img, (pad + int(round(22 * k)), cy), int(round(9 * k)), tuple(int(c) for c in rgb), -1,
                   cv2.LINE_AA)
        cv2.circle(img, (pad + int(round(22 * k)), cy), int(round(9 * k)), WHITE, max(1, ct - 1), cv2.LINE_AA)
        _text(img, label, pad + int(round(42 * k)), cy + int(round(8 * k)), ls, WHITE, ct)
    # time left (top right)
    t = _ascii(clock) if clock is not None else f"time left {max(time_left_s, 0.0):4.1f} s"
    tw, th = cv2.getTextSize(t, FONT, 0.72 * k, ct)[0]
    _dark_box(img, w - tw - 3 * pad, pad, w - pad, pad + th + 2 * pad)
    _text(img, t, w - tw - 2 * pad, pad + th + pad, 0.72 * k, WHITE, ct)
    # outcome banner (top centre, between the legend and the clock, clear of the arena's middle)
    if outcome:
        os_, ot = 0.95 * k, max(2, int(round(2.5 * k)))
        ow, oh = cv2.getTextSize(outcome, FONT, os_, ot)[0]
        x0, y0 = (w - ow) // 2 - 2 * pad, pad + int(round(70 * k))
        _dark_box(img, x0, y0, x0 + ow + 4 * pad, y0 + oh + 4 * pad)
        _text(img, outcome, x0 + 2 * pad, y0 + oh + 2 * pad, os_, WHITE, ot)
    return img


# --------------------------------------------------------------------------------------------- clip rule
def pick_clip_slot(first_game_s: np.ndarray, seconds_min: float, seconds_max: float) -> int:
    """The clip rule (configs/s2b.toml [video]): the first game slot, in index order, whose first game lasts
    seconds_min..seconds_max (inclusive); if none does, the slot whose first game lasts longest (the first on ties).
    first_game_s [K] seconds."""
    t = np.asarray(first_game_s, dtype=float)
    ok = np.flatnonzero((t >= seconds_min) & (t <= seconds_max))
    return int(ok[0]) if ok.size else int(np.argmax(t))


# --------------------------------------------------------------------------------------------- scene layout
def place_props(seed: int, half_m: float, zone_centre_m, zone_radius_m: float, count: int = 10,
                keep_clear_m: float = 0.5) -> list[dict]:
    """Visual props for the "props" clip: alternately a block and a column, at random places inside the arena
    ([-half_m, half_m]^2), at least keep_clear_m from the zone's edge and from one another. Their own random
    generator (seed), never the game's (the game's starts stay the same, D15).

    Returns [{"kind": "block" | "column", "xy_m": (x, y), "size_m": (dx, dy, height), "yaw_rad": float}]; a column's
    dx = dy = its diameter. Positions are relative to the game's origin."""
    rng = np.random.default_rng(seed)
    centre = np.asarray(zone_centre_m, dtype=float)
    out: list[dict] = []
    tries = 0
    while len(out) < count and tries < 10000:
        tries += 1
        kind = "block" if len(out) % 2 == 0 else "column"
        if kind == "block":
            size = (rng.uniform(0.4, 1.0), rng.uniform(0.4, 1.0), rng.uniform(0.4, 1.6))
        else:
            d = rng.uniform(0.25, 0.45)
            size = (d, d, rng.uniform(2.4, 3.2))
        r = 0.5 * float(np.hypot(size[0], size[1]))
        lim = half_m - r
        if lim <= 0:
            continue
        xy = rng.uniform(-lim, lim, size=2)
        if np.linalg.norm(xy - centre) < zone_radius_m + keep_clear_m + r:
            continue
        if any(np.linalg.norm(xy - np.asarray(p["xy_m"])) < r + p["_r"] + keep_clear_m for p in out):
            continue
        out.append({"kind": kind, "xy_m": (float(xy[0]), float(xy[1])), "size_m": tuple(float(s) for s in size),
                    "yaw_rad": float(rng.uniform(0.0, np.pi)) if kind == "block" else 0.0, "_r": r})
    for p in out:
        p.pop("_r")
    return out


HFOV_DEG = 60.0          # the video camera's horizontal field of view (compat/isaaclab_232.make_recorder sets it)


def project(points_m, eye_m, lookat_m, aspect: float = 16 / 9, hfov_deg: float = HFOV_DEG) -> np.ndarray:
    """Pinhole projection of points [P, 3] (world, z up) to normalised image coordinates [P, 2]: x right, y up, the
    frame edge at +-1; points behind the camera get inf."""
    eye, look = np.asarray(eye_m, float), np.asarray(lookat_m, float)
    f = look - eye
    f /= np.linalg.norm(f)
    r = np.cross(f, [0.0, 0.0, 1.0])
    r /= np.linalg.norm(r)
    u = np.cross(r, f)
    d = np.asarray(points_m, float) - eye
    z = d @ f
    tx = np.tan(np.radians(hfov_deg) / 2)
    ty = tx / aspect
    with np.errstate(divide="ignore", invalid="ignore"):
        out = np.stack(((d @ r) / (z * tx), (d @ u) / (z * ty)), axis=-1)
    out[z <= 0] = np.inf
    return out


# where the arena may appear in the image: clear of the caption band (bottom), the legend and the clock (top)
FRAME_BOX = {"x": (-0.93, 0.93), "y": (-0.66, 0.80)}


def camera_pose(half_m: float, origin_m=(0.0, 0.0, 0.0), view: str = "wide", top_m: float = 1.8,
                elevation_deg: float | None = None, azimuth_deg: float = -100.0,
                distance_scale: float = 1.0, lookat_lift_m: float = 0.0) -> tuple[tuple, tuple]:
    """Oblique camera over one game's square arena (half side half_m): (eye, lookat) in world metres. The camera
    looks at the arena from azimuth_deg (from +x, counter-clockwise; -100 = from the south, a little west) and
    elevation_deg above the horizon, as close as it can while the arena's corners on the floor and at top_m (the
    height band's top) stay inside FRAME_BOX. view "wide" (32 deg up) is the clip camera; "high" (55 deg up) is for
    stills. distance_scale > 1 steps back from the closest fit (more of the surroundings, for a backdrop);
    lookat_lift_m then raises the aim point, which lowers the arena in the image and shows more of what lies behind."""
    if view not in ("wide", "high"):
        raise ValueError(f"view must be 'wide' or 'high', got {view!r}")
    el = np.radians(elevation_deg if elevation_deg is not None else (32.0 if view == "wide" else 55.0))
    az = np.radians(azimuth_deg)
    o = np.asarray(origin_m, dtype=float)
    h = float(half_m)
    back = np.array([np.cos(az) * np.cos(el), np.sin(az) * np.cos(el), np.sin(el)])
    ground_back = np.array([np.cos(az), np.sin(az), 0.0])
    corners = np.array([[sx * h, sy * h, z] for sx in (-1, 1) for sy in (-1, 1) for z in (0.0, top_m)]) + o

    def closest(look: np.ndarray) -> float:
        lo, hi = 0.5, 400.0
        for _ in range(50):
            dist = 0.5 * (lo + hi)
            p = project(corners, look + dist * back, look)
            ok = (np.isfinite(p).all() and FRAME_BOX["x"][0] <= p[:, 0].min() and p[:, 0].max() <= FRAME_BOX["x"][1]
                  and FRAME_BOX["y"][0] <= p[:, 1].min() and p[:, 1].max() <= FRAME_BOX["y"][1])
            lo, hi = (lo, dist) if ok else (dist, hi)
        return hi

    # aim a little towards the camera (the far half of the arena looks shorter): the shift that lets it come closest
    looks = [o + np.array([0.0, 0.0, 0.5]) + k * h * ground_back for k in np.linspace(0.0, 0.8, 33)]
    dists = [closest(lk) for lk in looks]
    i = int(np.argmin(dists))
    look, eye = looks[i], looks[i] + distance_scale * dists[i] * back
    look = look + np.array([0.0, 0.0, lookat_lift_m])
    return tuple(float(v) for v in eye), tuple(float(v) for v in look)


# --------------------------------------------------------------------------------------------- encoders
def encode_mp4(frames: list[np.ndarray], path: Path, fps: int = 20, max_mb: float = 10.0, crf0: int = 23,
               crf_step: int = 4) -> tuple[Path, int]:
    """H.264 (libx264, yuv420p, imageio-ffmpeg) at crf0, then crf raised in steps of crf_step until the file is at
    most max_mb (10^6 bytes) or crf reaches 51. Returns (path, crf used). Raises if even crf 51 is too big."""
    import imageio.v2 as imageio

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    crf = crf0
    while True:
        w = imageio.get_writer(str(path), format="FFMPEG", fps=fps, codec="libx264", quality=None,
                               pixelformat="yuv420p", macro_block_size=2,
                               ffmpeg_params=["-crf", str(crf), "-preset", "slow", "-movflags", "+faststart"],
                               ffmpeg_log_level="error")
        for f in frames:
            w.append_data(np.ascontiguousarray(f))
        w.close()
        if path.stat().st_size <= max_mb * 1e6:
            return path, crf
        if crf >= 51:
            raise RuntimeError(f"{path.name}: {path.stat().st_size / 1e6:.2f} MB at crf 51, cap {max_mb} MB")
        crf = min(crf + crf_step, 51)


def encode_gif(frames: list[np.ndarray], path: Path, fps: int = 10, max_mb: float = 5.0, src_fps: int = 20,
               speed: float = 1.0,
               widths: tuple[int, ...] = (800, 720, 640, 560, 480, 400, 320, 240, 160)) -> tuple[Path, dict]:
    """Looping GIF through ffmpeg (palettegen + paletteuse), at most max_mb. The GIF plays at speed x real time
    with fps frames per second (every round(src_fps * speed / fps)-th frame is kept). Tries the widest width first
    (never wider than the frames), at fps, 0.7 fps and 0.5 fps, with 128 then 64 colours, before a narrower width.
    Returns (path, {"width", "fps", "colours", "speed"})."""
    import imageio_ffmpeg

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    h0, w0 = frames[0].shape[:2]
    exe = imageio_ffmpeg.get_ffmpeg_exe()
    for width in [w for w in widths if w <= w0] or [w0]:          # width first: the caption must stay readable
        for out_fps in sorted({fps, max(fps * 7 // 10, 1), max(fps // 2, 1)}, reverse=True):
            step = max(int(round(src_fps * speed / out_fps)), 1)
            raw = b"".join(np.ascontiguousarray(f).tobytes() for f in frames[::step])
            for colours in (128, 64):
                vf = (f"scale={width}:-2:flags=lanczos,split[a][b];"
                      f"[a]palettegen=max_colors={colours}:stats_mode=full[p];"
                      f"[b][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle")
                cmd = [exe, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w0}x{h0}",
                       "-r", str(out_fps), "-i", "-", "-vf", vf, "-loop", "0", str(path)]
                subprocess.run(cmd, input=raw, check=True)
                if path.stat().st_size <= max_mb * 1e6:
                    return path, {"width": width, "fps": out_fps, "colours": colours,
                                  "speed": step * out_fps / src_fps}
    raise RuntimeError(f"{path.name}: no GIF setting fits {max_mb} MB")
