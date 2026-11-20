"""Top-down replay of Strike vs Guard games from the training simulator (offline, for showing people).

``record_games`` plays N games on the CPU with two strategies and keeps, per game, every drone's position at every
step (frame 0 = the start, frame k = after k steps), who is still in the game, the arena, the zone and the result.
``render_replay`` draws one recorded game as a top-down animation (matplotlib) and writes a GIF or an MP4.

This is offline visualisation: it loops over steps and games on the host, which the batched game step itself never
does. Nothing here changes the game."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch

from ..core.arena import BANDS
from ..core.game import SvgGame
from ..core.game_config import TICK_S, GameCfg
from ..core.rewards import GUARD_WIN, RUNNING, STRIKE_WIN
from ..opponents.scripted import make_strategy

# Colour-blind-safe pair (Okabe-Ito): blue for the Guard team, orange for the Strike team
GUARD_COLOUR = "#0072B2"
STRIKE_COLOUR = "#E69F00"
ZONE_COLOUR = "#009E73"


@dataclass
class Recording:
    """One recorded game. T = steps played, M = drones (Guard drones first, then Strike drones).
    pos_m [T+1, M, 3] (a drone that is out keeps the place it was last in the game), alive [T+1, M] bool,
    zone_centre_m [2], zone_radius_m, half_m (the arena is the square [-half_m, half_m]^2), outcome (1 Strike team
    reached the zone, 2 Guard team held it), end_step (== T), plus the labels used in the title."""
    pos_m: np.ndarray
    alive: np.ndarray
    zone_centre_m: np.ndarray
    zone_radius_m: float
    half_m: float
    outcome: int
    end_step: int
    guards: int
    strikes: int
    band: str
    rules: str
    guard_name: str
    strike_name: str
    seed: int
    game_index: int
    closest_cross_m: float
    height_band_m: tuple | None = None       # (floor, ceiling) m, drawn in the height panel; None: not known


    @property
    def end_time_s(self) -> float:
        return self.end_step * TICK_S


class _RecordingGame(SvgGame):
    """SvgGame that remembers each game's last positions just before its auto-reset overwrites them."""

    def _new_games(self, mask):
        if getattr(self, "_keep", False):
            self._last_pos = self.pos_m.clone()
            self._last_alive = self.alive.clone()
        super()._new_games(mask)


def record_games(cfg: GameCfg, guards: int, strikes: int, guard_spec, strike_spec, num_games: int = 8,
                 seed: int = 0, band: int | None = 1, max_steps: int | None = None) -> list[Recording]:
    """Play num_games games on the CPU (each slot's first game) and return one Recording per slot. The game
    seed is ``seed``; strategy seeds are seed + 101 (Guard) and seed + 202 (Strike), as in scripts/score.py.
    ``guard_spec`` / ``strike_spec``: a strategy name (``make_strategy``) or a strategy object on the CPU for
    ``num_games`` games (STE L0.12: a trained team of either side); the recording carries the object's ``name``."""
    dev = "cpu"
    game = _RecordingGame(cfg, num_games, guards, strikes, device=dev, seed=seed, band=band)
    guard = make_strategy(guard_spec, "guard", cfg, num_games, dev, seed + 101) if isinstance(guard_spec, str) else guard_spec
    strike = (make_strategy(strike_spec, "strike", cfg, num_games, dev, seed + 202) if isinstance(strike_spec, str)
              else strike_spec)
    guard_spec = guard_spec if isinstance(guard_spec, str) else guard.name
    strike_spec = strike_spec if isinstance(strike_spec, str) else strike.name
    obs = game.reset()
    everyone = torch.ones(num_games, dtype=torch.bool)
    guard.reset(everyone)
    strike.reset(everyone)
    game._keep = True
    ar = game.arenas
    centre, rad, half = ar.zone_centre_m.clone().numpy(), ar.zone_radius_m.clone().numpy(), ar.half_m.numpy().copy()
    band_idx = ar.band.clone().numpy()
    pos = [game.pos_m.clone().numpy()]
    alive = [game.alive.clone().numpy()]
    finished = np.zeros(num_games, dtype=bool)
    outcome = np.zeros(num_games, dtype=int)
    end = np.zeros(num_games, dtype=int)
    closest = np.full(num_games, np.inf)
    max_steps = game.ticks if max_steps is None else int(max_steps)
    for k in range(1, max_steps + 1):
        out = game.step({"guard": guard.act(obs["guard"]), "strike": strike.act(obs["strike"])})
        done = out.done.numpy()
        active = ~finished
        closest = np.where(active, np.minimum(closest, out.info["closest_cross_m"].numpy()), closest)
        p = game.pos_m.clone().numpy()
        a = game.alive.clone().numpy()
        if done.any():                                   # the game already restarted: use the saved last state
            p[done] = game._last_pos.numpy()[done]
            a[done] = out.info["final_alive"].numpy()[done]
        pos.append(p)
        alive.append(a)
        first = active & done
        outcome[first] = out.outcome.numpy()[first]
        end[first] = k
        finished |= done
        guard.reset(out.done)
        strike.reset(out.done)
        obs = out.obs
        if finished.all():
            break
    pos_a, alive_a = np.stack(pos), np.stack(alive)       # [T+1, N, M, 3] / [T+1, N, M]
    rules = "Starling layer" if cfg.starling.enabled else "pure rules"
    recs = []
    for i in range(num_games):
        if not finished[i]:
            continue
        t = int(end[i])
        pi, ai = pos_a[: t + 1, i].copy(), alive_a[: t + 1, i].copy()
        # a drone that is out is parked far away by the game: show it where it was last in the game
        for m in range(pi.shape[1]):
            last = pi[0, m]
            for f in range(t + 1):
                if ai[f, m]:
                    last = pi[f, m]
                else:
                    pi[f, m] = last
        recs.append(Recording(pi, ai, centre[i], float(rad[i]), float(half[i]), int(outcome[i]), t, guards,
                              strikes, BANDS[int(band_idx[i])], rules, guard_spec, strike_spec, seed, i,
                              float(closest[i]), tuple(cfg.arena.height_band_m)))
    return recs


def _label(spec: str) -> str:
    return spec.replace("_", " ")


def result_text(rec: Recording) -> str:
    if rec.outcome == STRIKE_WIN:
        return f"Strike team reaches the zone at t = {rec.end_time_s:.1f} s"
    if rec.outcome == GUARD_WIN:
        return "Guard team holds the zone"
    return "game not finished"


def title_text(rec: Recording) -> str:
    return (f"{rec.guards} Guard v {rec.strikes} Strike drones, {rec.rules}\n"
            f"Guard: {_label(rec.guard_name)}   Strike: {_label(rec.strike_name)}\n"
            f"arena {2 * rec.half_m:.0f} m x {2 * rec.half_m:.0f} m ({rec.band} size)")


def frame_indices(rec: Recording, speed: int = 1, hold_s: float = 2.5, fps: int = 20) -> list[int]:
    """Game steps shown, in order: every ``speed``-th step, the last step, then the last step repeated so the
    result stays up for ``hold_s`` seconds."""
    idx = list(range(0, rec.end_step + 1, max(1, speed)))
    if idx[-1] != rec.end_step:
        idx.append(rec.end_step)
    return idx + [rec.end_step] * int(round(hold_s * fps))


class Scene:
    """The figure of one replay: build it, then ``update(j)`` draws frame j of ``frame_indices``.
    ``dots`` and ``crosses`` hold one artist per drone: a drone in the game has a dot, one that is out has a cross.
    ``height_panel`` (default on; svg_training/CLAUDE.md "Videos inside every run", VID-1 part 1): a strip under the map
    with every drone's height (m) against time up to the frame's step, the height band as dashed lines and a time
    cursor (``hax``, ``heights``, ``band_lines``); off draws today's layout unchanged."""

    def __init__(self, rec: Recording, speed: int, fps: int, trail_s: float, size_in: tuple[float, float],
                 dpi: int, hold_s: float, height_panel: bool = True):
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.lines import Line2D
        from matplotlib.patches import Circle, Rectangle

        self.rec, self.speed = rec, speed
        g, h = rec.guards, rec.half_m
        n = rec.guards + rec.strikes
        w, hgt = size_in
        self.fig = fig = plt.figure(figsize=size_in, dpi=dpi)
        if height_panel:
            ax = fig.add_axes([0.07, 0.34, 0.52 * hgt / w, 0.52])
        else:
            ax = fig.add_axes([0.07, 0.15, 0.70 * hgt / w, 0.70])
        self.ax = ax
        ax.set_aspect("equal")
        pad = 0.04 * h
        ax.set_xlim(-h - pad, h + pad)
        ax.set_ylim(-h - pad, h + pad)
        ax.set_xlabel("x (m)", fontsize=12)
        ax.set_ylabel("y (m)", fontsize=12)
        ax.tick_params(labelsize=11)
        ax.add_patch(Rectangle((-h, -h), 2 * h, 2 * h, fill=False, ec="#444444", lw=2))
        ax.add_patch(Circle(rec.zone_centre_m, rec.zone_radius_m, fc=ZONE_COLOUR, alpha=0.22, ec=ZONE_COLOUR, lw=2))
        ax.text(rec.zone_centre_m[0], rec.zone_centre_m[1] + rec.zone_radius_m * 1.12, "zone", ha="center",
                va="bottom", fontsize=11, color="#006B4F")
        colours = [GUARD_COLOUR if m < g else STRIKE_COLOUR for m in range(n)]
        marker = ["o" if m < g else "^" for m in range(n)]
        self.trails = [ax.plot([], [], "-", color=c, lw=3.0, alpha=0.5, solid_capstyle="round")[0] for c in colours]
        # Drones can sit exactly on top of each other (same-team drones are not pushed apart). Each drone has its own
        # marker size, bigger for lower index and drawn underneath, so stacked drones show as nested markers.
        self.dots = []
        for m, c in enumerate(colours):
            k = m if m < g else m - g
            self.dots.append(ax.plot([], [], marker[m], color=c, ms=max(6, (24 if m < g else 18) - 5 * k),
                                     mec="black", mew=1.2, zorder=3 + (k if m < g else 10 + k))[0])
        self.crosses = [ax.plot([], [], "x", color=c, ms=18, mew=3.0, alpha=0.45, zorder=2)[0] for c in colours]
        fig.legend(handles=[
            Line2D([], [], marker="o", ls="", color=GUARD_COLOUR, mec="black", ms=12, label="Guard drone"),
            Line2D([], [], marker="^", ls="", color=STRIKE_COLOUR, mec="black", ms=11, label="Strike drone"),
            Line2D([], [], marker="x", ls="", color="#777777", ms=11, mew=3, alpha=0.6, label="drone that is out"),
            Line2D([], [], marker="s", ls="", color=ZONE_COLOUR, alpha=0.4, ms=14, label="zone")],
            loc="center left", bbox_to_anchor=(0.74, 0.5), fontsize=13, frameon=False, labelspacing=1.0)
        fig.text(0.5, 0.975, title_text(rec), ha="center", va="top", fontsize=15)
        fig.text(0.74, 0.30, "Marker size only tells the\ndrones of a team apart.\nDrones on top of each other\nshow as nested markers.", fontsize=11, color="#444444",
                 va="top")
        self.clock = fig.text(0.74, 0.80, "", ha="left", va="center", fontsize=15, family="monospace",
                              linespacing=1.4)
        banner_at = (0.87, 0.10, 12) if height_panel else (0.5, 0.02, 17)
        self.banner = fig.text(banner_at[0], banner_at[1], "", ha="center", va="bottom", fontsize=banner_at[2],
                               weight="bold", bbox={"fc": "white", "ec": "#444444", "boxstyle": "round,pad=0.4"})
        self.wrap_banner = height_panel
        self.hax, self.heights, self.band_lines, self.cursor = None, [], [], None
        if height_panel:
            hax = fig.add_axes([0.08, 0.07, 0.60, 0.17])
            self.hax = hax
            z = rec.pos_m[..., 2][rec.alive]
            lo, hi = (float(z.min()), float(z.max())) if z.size else (0.0, 1.0)
            if rec.height_band_m is not None:
                lo, hi = min(lo, rec.height_band_m[0]), max(hi, rec.height_band_m[1])
                self.band_lines = [hax.axhline(b, ls="--", color="#777777", lw=1.2) for b in rec.height_band_m]
            span = max(hi - lo, 0.2)
            hax.set_ylim(lo - 0.1 * span, hi + 0.1 * span)
            hax.set_xlim(0.0, max(rec.end_step, 1) * TICK_S)
            hax.set_xlabel("time (s)", fontsize=11)
            hax.set_ylabel("height (m)", fontsize=11)
            hax.tick_params(labelsize=10)
            self.heights = [hax.plot([], [], "-", color=c, lw=2.0, alpha=0.8)[0] for c in colours]
            self.cursor = hax.axvline(0.0, color="#444444", lw=1.0)
        self.idx = frame_indices(rec, speed, hold_s, fps)
        self.trail_n = max(1, int(round(trail_s / TICK_S)))
        self.plt = plt

    def update(self, j: int):
        rec, k = self.rec, self.idx[j]
        for m in range(rec.guards + rec.strikes):
            lo = max(0, k - self.trail_n)
            seg = rec.pos_m[lo : k + 1, m, :2][rec.alive[lo : k + 1, m]]
            self.trails[m].set_data(seg[:, 0], seg[:, 1])
            x, y = rec.pos_m[k, m, :2]
            if rec.alive[k, m]:
                self.dots[m].set_data([x], [y])
                self.crosses[m].set_data([], [])
            else:
                self.dots[m].set_data([], [])
                self.crosses[m].set_data([x], [y])
        self.clock.set_text(f"t = {k * TICK_S:5.1f} s")
        text = result_text(rec) if k >= rec.end_step else ""
        if self.wrap_banner and text:
            import textwrap
            text = textwrap.fill(text, width=22)
        self.banner.set_text(text)
        extra = []
        if self.hax is not None:
            t = np.arange(k + 1) * TICK_S
            for m, line in enumerate(self.heights):
                line.set_data(t, np.where(rec.alive[: k + 1, m], rec.pos_m[: k + 1, m, 2], np.nan))
            self.cursor.set_xdata([k * TICK_S, k * TICK_S])
            extra = self.heights + [self.cursor]
        return self.trails + self.dots + self.crosses + [self.clock, self.banner] + extra


def _use_bundled_ffmpeg_if_missing() -> None:
    """matplotlib's FFMpegWriter runs ``ffmpeg`` from PATH. A plain machine often has none, but the ``imageio-ffmpeg``
    dependency ships a binary: point matplotlib at it when no ``ffmpeg`` is on PATH (an ffmpeg already on PATH, or an
    ``animation.ffmpeg_path`` set by the user, wins)."""
    import shutil

    import matplotlib

    if matplotlib.rcParams["animation.ffmpeg_path"] != "ffmpeg" or shutil.which("ffmpeg"):
        return
    try:
        import imageio_ffmpeg
    except ImportError:
        return
    matplotlib.rcParams["animation.ffmpeg_path"] = imageio_ffmpeg.get_ffmpeg_exe()


def render_replay(rec: Recording, path: str | Path, speed: int = 1, fps: int = 20, trail_s: float = 1.5,
                  size_in: tuple[float, float] = (10.667, 8.0), dpi: int = 120, hold_s: float = 2.5,
                  playback_label: str = "", height_panel: bool = True) -> Path:
    """Write the replay of one game to ``path`` (.gif via pillow, .mp4 via ffmpeg). One game step is TICK_S = 0.05 s,
    one drawn frame shows ``speed`` steps and plays for 1/fps s, so the playback is speed * fps * 0.05 times real
    time (speed 2 at 20 fps = 2x). ``playback_label`` (e.g. "2x real time") is shown next to the clock. Default
    size 10.667 x 8 in at 120 dpi = 1280 x 960 px (even sizes, as the MP4 codec needs). ``height_panel`` (default on):
    the height strip under the map (``Scene``)."""
    from matplotlib.animation import FFMpegWriter, FuncAnimation, PillowWriter

    path = Path(path)
    if path.suffix not in (".gif", ".mp4"):
        raise ValueError(f"path must end in .gif or .mp4, got {path.name!r}")
    sc = Scene(rec, speed, fps, trail_s, size_in, dpi, hold_s, height_panel)
    if playback_label:
        base = sc.update

        def update(j: int):
            art = base(j)
            sc.clock.set_text(sc.clock.get_text() + f"\n({playback_label})")
            return art
        sc.update = update
    anim = FuncAnimation(sc.fig, sc.update, frames=len(sc.idx), blit=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".gif":
        anim.save(path, writer=PillowWriter(fps=fps))
    else:
        _use_bundled_ffmpeg_if_missing()
        anim.save(path, writer=FFMpegWriter(fps=fps, codec="libx264", bitrate=3000,
                                            extra_args=["-pix_fmt", "yuv420p"]))
    sc.plt.close(sc.fig)
    return path
