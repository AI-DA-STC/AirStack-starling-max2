#!/usr/bin/env python3
"""Live window of a test's headline plot, opened and closed by `tools/sim.sh test` (design 2026-10-30).

    live_plot.py --plots <test>/plots.json --docker <robot container> --csv /tmp/svg_test/metrics.csv [--title T]
    live_plot.py --plots <test>/plots.json --file <metrics.csv> [--once --save out.png]      (tests, re-viewing a run)

It follows the run's metrics.csv as the metrics node writes it (the node flushes once a second) and draws the first
plot of plots.json: the same series, colours and reference lines as the record's Figure 1, with the latest closest
value and the running minimum in the title. It never affects a verdict. Host-only: numpy + matplotlib (TkAgg)."""
from __future__ import annotations

import argparse
import json
import math
import pathlib
import queue
import subprocess
import sys
import threading
import time

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import metrics_core as M  # noqa: E402
import plot_style as PS  # noqa: E402

REDRAW_S = 0.5


class LiveModel:
    """The growing CSV as arrays for one plot spec. Torn rows from a live tail are skipped and counted."""

    def __init__(self, spec):
        self.spec = spec
        self.series = list(spec.get("series", []))
        self._p = M.CsvLineParser(strict=False, source="live metrics.csv")
        self._arr, self._cols = None, None                # rows converted so far (appended, never rebuilt)

    def feed(self, line):
        self._p.feed(line)

    @property
    def skipped(self):
        return self._p.skipped

    @property
    def meta(self):
        return self._p.meta

    def arrays(self):
        cols, rows = self._p.columns or [], self._p.rows
        if self._arr is None or self._cols != cols:
            self._arr, self._cols = np.zeros((0, len(cols))), list(cols)
        if len(rows) > len(self._arr):
            new = np.asarray(rows[len(self._arr):], dtype=float).reshape(-1, len(cols))
            self._arr = np.vstack([self._arr, new])
        a = self._arr
        idx = {c: i for i, c in enumerate(cols)}

        def col(name):
            return a[:, idx[name]] if name in idx and len(a) else np.full(len(a), math.nan)
        return col("t_s"), {s: col(s) for s in self.series}, col("phase")

    def refs(self):
        out = []
        for name in self.spec.get("refs", []):
            v = PS.ref_value(self.meta, name)
            if v is not None:
                out.append((name, v))
        return out

    def headline(self):
        """Running-minimum plots: the lowest series now and the running minimum. Others: each series' latest value."""
        t, ys, _ = self.arrays()
        if not len(t):
            return "waiting for the metrics node…"
        unit = (" " + self.spec["unit"]) if self.spec.get("unit") else ""
        f = lambda v: "—" if v is None or math.isnan(v) else "%.2f%s" % (v, unit)
        plain = [s for s in self.series if not s.endswith("_running")]
        running = [s for s in self.series if s.endswith("_running")]
        if running:
            now = [ys[s][-1] for s in plain if not math.isnan(ys[s][-1])]
            return "now %s · running min %s" % (f(min(now)) if now else "—", f(ys[running[0]][-1]))
        return "latest " + ", ".join("%s %s" % (s, f(ys[s][-1])) for s in plain)


class Redraw:
    """Throttle: lines mark the plot dirty; it is drawn at most every `period` s, and a dirty plot is always drawn
    on a later pass even when no further line arrives (the last rows before the node stops are not lost)."""

    def __init__(self, period=0.5):
        self.period, self.dirty, self.last = period, False, -1e9

    def mark(self):
        self.dirty = True

    def due(self, now):
        return self.dirty and now - self.last >= self.period

    def drawn(self, now):
        self.dirty, self.last = False, now


class Window:
    """One matplotlib figure, updated in place (no flicker, the window keeps its position)."""

    def __init__(self, spec, title):
        import matplotlib.pyplot as plt                  # the caller has chosen the backend
        self.plt, self.spec, self.title = plt, spec, title
        self.fig, self.ax = plt.subplots(figsize=(7.0, 3.8), dpi=100, facecolor="white")
        try:
            self.fig.canvas.manager.set_window_title("Live: %s" % title)
        except AttributeError:
            pass
        ax = self.ax
        ax.set_facecolor("white"); ax.grid(True, color=PS.GRID, linewidth=0.8); ax.set_axisbelow(True)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        for sp in ("left", "bottom"):
            ax.spines[sp].set_color(PS.SPINE)
        ax.tick_params(colors=PS.MUTED, labelsize=8)
        ax.set_xlabel("t [s, wall]", color=PS.INK, fontsize=9)
        ax.set_ylabel(spec.get("title", spec.get("id", "")), color=PS.INK, fontsize=9)
        self.lines = {}
        for i, name in enumerate(spec.get("series", [])):
            self.lines[name], = ax.plot([], [], color=PS.series_colour(i, name), ls=PS.series_style(i), lw=1.6, label=name)
        self.ref_lines = {}
        yr = spec.get("y_range")
        if yr:
            ax.set_ylim(yr[0], yr[1])
        ax.legend(fontsize=7, frameon=False, loc="upper right", ncol=2)
        self.fig.text(0.01, 0.01, PS.FOOTER, fontsize=7, color=PS.MUTED)
        self.fig.tight_layout(rect=(0, 0.03, 1, 1))

    def update(self, model):
        t, ys, _ = model.arrays()
        for name, ln in self.lines.items():
            ln.set_data(t, ys.get(name, np.full(len(t), math.nan)))
        for name, v in model.refs():
            if name not in self.ref_lines:
                self.ref_lines[name] = self.ax.axhline(v, color=PS.INK, ls="--", lw=1.0, alpha=0.8, label="%s = %g" % (name, v))
                self.ax.legend(fontsize=7, frameon=False, loc="upper right", ncol=2)
        ok = t[np.isfinite(t)]
        if len(ok):
            self.ax.set_xlim(float(ok[0]), max(float(ok[-1]), float(ok[0]) + 10.0))
        if not self.spec.get("y_range"):
            self.ax.relim(); self.ax.autoscale_view(scalex=False)
        name = self.spec.get("title", self.spec.get("id", ""))
        self.ax.set_title("%s: %s" % (name, model.headline()), color=PS.INK, fontsize=10, loc="left")


def source_cmd(docker=None, path="/tmp/svg_test/metrics.csv"):
    """The command whose stdout is the CSV, line by line. In the container the tail ends when the metrics node does."""
    if docker:
        # anchored: matches the node's own argv only, never this bash -c or the node's bash -ic launcher; no node → exit
        script = ("p=$(pgrep -of '^python3 metrics_node\\.py'); [ -n \"$p\" ] || exit 3; "
                  "exec tail -n +1 -F --pid=$p %s 2>/dev/null" % path)
        return ["docker", "exec", docker, "bash", "-c", script]
    return ["tail", "-n", "+1", "-F", path]


def _reader(cmd, q):
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1)
    except OSError as e:
        q.put(("error", str(e))); return
    for line in proc.stdout:
        q.put(("line", line))
    q.put(("eof", proc.wait()))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--plots", required=True)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--docker", help="robot container name (follows --csv inside it)")
    src.add_argument("--file", help="a metrics.csv on this machine")
    ap.add_argument("--csv", default="/tmp/svg_test/metrics.csv")
    ap.add_argument("--title", default="live test")
    ap.add_argument("--once", action="store_true", help="read --file to its end, draw once, exit (tests, re-viewing)")
    ap.add_argument("--save", help="with --once: write the frame to this PNG")
    a = ap.parse_args(argv)
    try:
        spec = json.loads(pathlib.Path(a.plots).read_text())["plots"][0]
    except (OSError, ValueError, KeyError, IndexError) as e:
        print("live_plot: cannot read the first plot of %s: %s" % (a.plots, e), file=sys.stderr)
        return 2
    model = LiveModel(spec)
    if a.once:
        if not a.file:
            print("live_plot: --once needs --file", file=sys.stderr); return 2
        with open(a.file) as fh:
            for line in fh:
                model.feed(line)
        import matplotlib
        if a.save:
            matplotlib.use("Agg")
        w = Window(spec, a.title); w.update(model)
        if a.save:
            w.fig.savefig(a.save, facecolor="white")
        else:
            w.plt.show()
        return 0
    import matplotlib
    matplotlib.use("TkAgg")
    w = Window(spec, a.title)
    q = queue.Queue()
    threading.Thread(target=_reader, args=(source_cmd(a.docker, a.csv if a.docker else a.file), q), daemon=True).start()
    w.plt.show(block=False)
    redraw = Redraw(REDRAW_S)
    while w.plt.fignum_exists(w.fig.number):
        try:
            while True:
                kind, val = q.get_nowait()
                if kind == "line":
                    model.feed(val); redraw.mark()
                elif kind == "error":
                    print("live_plot: source failed: %s" % val, file=sys.stderr)
                elif kind == "eof":
                    print("live_plot: source ended (rc %s); the window keeps the last frame" % val, file=sys.stderr)
        except queue.Empty:
            pass
        now = time.monotonic()
        if redraw.due(now):
            w.update(model); w.fig.canvas.draw_idle(); redraw.drawn(now)
        w.plt.pause(0.1)
    print("live_plot: window closed by the user", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
