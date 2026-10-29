"""metrics_core — the one place every formula of the live test driver lives.

Pure Python (stdlib + numpy). Never import rclpy or anything container-only here: the
rclpy metrics node, the offline bag recompute, gates.py and the plots all import this file.
Runs on Python 3.12 (container) and 3.13 (host). Sim-only: nothing here has seen a real flight.

Definitions
  world frame   world = odometry position + per-drone offset (offsets recorded once, in the
                CSV header as "offsets", flat x,y,z per drone in drone order).
  t_s           header stamp of the trigger drone's odometry message minus t0 (t0_unix in the
                CSV header). One row per trigger message, using the latest pose of the others.
  phase         0 idle, 1 takeoff, 2 test, 3 land; derived from /svg/commander_status
                (phase_from_status). Start positions are captured when phase becomes 2.
  stale rule    a drone whose last odometry is older than STALE_S (or never seen) is stale;
                every series that uses it is NaN for that row.
  speed         norm of odometry twist.twist.linear (same as the commander's speed_mps).
  goal distance |pos - antipode(start_pos)|, antipode = 2*arena_center - start; NaN before phase 2.
  running min   minimum over the phase-2 rows only (NaN ignored): NaN before phase 2, frozen at the last phase-2 value after it.
  cross-check   live rows are paired to bag rows by mutual-nearest t_s within t_tol.
                Continuous column: ok = max abs diff <= tol. Flag column (0/1): compared by
                sample count, ok = |sum_live - sum_bag| <= max(2, 1 % of paired rows).
                More than 5 % unpaired live rows, or more than 5 % unpaired bag rows, or no pair at all:
                ok is False for every row (UNVERIFIED).
  coverage      rows exist only when the trigger drone's odometry arrives, so a trigger-drone gap or a dead node
                leaves no NaN row behind. coverage() reports the largest t_s step over the phase-2 rows plus the
                row on each side (a hole across the start or end of the window counts) and the phase-2/3 row counts.
"""
import itertools
import math
import re
from dataclasses import dataclass
from typing import Callable

import numpy as np

STALE_S = 0.5
UNPAIRED_MAX = 0.05


class MetricsCsvError(ValueError):
    pass


@dataclass(frozen=True)
class Series:
    name: str
    fn: Callable[["Frame"], float]
    tol: float
    unit: str = ""
    kind: str = "continuous"  # "continuous" | "flag"
    running_min: bool = False


@dataclass
class Frame:
    t_s: float
    pos: dict
    vel: dict
    stale: frozenset
    cbf_active: frozenset
    emergency: bool
    fence_breached: bool
    phase: int
    start_pos: dict
    params: dict


@dataclass
class CrossRow:
    name: str
    tol: float
    kind: str
    max_abs_diff: float
    sum_live: float
    sum_bag: float
    paired: int
    unpaired_frac: float
    ok: bool
    unpaired_bag_frac: float = 0.0


# ---------------------------------------------------------------- geometry

def world_position(xyz, offset):
    return np.asarray(xyz, dtype=float) + np.asarray(offset, dtype=float)


def _num(name):
    return name.rsplit("_", 1)[-1]


def pair_key(a, b):
    a, b = sorted((a, b))
    return "d_" + _num(a) + _num(b)


def pairwise_distances(pos, stale=frozenset()):
    out = {}
    for a, b in itertools.combinations(sorted(pos), 2):
        if a in stale or b in stale:
            out[pair_key(a, b)] = math.nan
        else:
            out[pair_key(a, b)] = float(np.linalg.norm(np.asarray(pos[a]) - np.asarray(pos[b])))
    return out


def pair_distance(frame, a, b):
    if a in frame.stale or b in frame.stale or a not in frame.pos or b not in frame.pos:
        return math.nan
    return float(np.linalg.norm(np.asarray(frame.pos[a]) - np.asarray(frame.pos[b])))


def min_pair_distance(frame):
    # A stale (or never seen) drone makes the whole row NaN, not a minimum over the remaining pairs.
    if frame.stale:
        return math.nan
    vals = list(pairwise_distances(frame.pos).values())
    return min(vals) if vals else math.nan


def speed_of(frame, drone):
    if drone in frame.stale or drone not in frame.vel:
        return math.nan
    return float(np.linalg.norm(np.asarray(frame.vel[drone])))


def fence_margin(frame):
    lo = np.asarray(frame.params["fence_min"], dtype=float)
    hi = np.asarray(frame.params["fence_max"], dtype=float)
    best = math.nan
    for d, p in frame.pos.items():
        if d in frame.stale:
            continue
        p = np.asarray(p, dtype=float)
        m = float(min(np.min(p - lo), np.min(hi - p)))
        best = m if math.isnan(best) else min(best, m)
    return best


def arena_center(params):
    return (np.asarray(params["arena_low"], dtype=float) + np.asarray(params["arena_high"], dtype=float)) / 2.0


def antipode(p_start, center):
    return 2.0 * np.asarray(center, dtype=float) - np.asarray(p_start, dtype=float)


def goal_distance(frame, drone):
    if frame.phase < 2 or drone in frame.stale or drone not in frame.start_pos or drone not in frame.pos:
        return math.nan
    goal = antipode(frame.start_pos[drone], arena_center(frame.params))
    return float(np.linalg.norm(np.asarray(frame.pos[drone]) - goal))


# ---------------------------------------------------------------- phase / params

def phase_from_status(states, mission_active, prev):
    states = [str(s).upper() for s in states]
    if mission_active:
        return 2
    if any(s == "LANDING" for s in states):
        return 3
    if any(s in ("ARMING", "ASCEND") for s in states):
        return 1
    if states and all(s == "IDLE" for s in states):
        return 0
    return prev


_NUM = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")


def parse_param_array(text):
    m = re.search(r"\[([^\]]*)\]", text)
    if not m:
        raise ValueError("no array in %r" % text)
    return [float(x) for x in _NUM.findall(m.group(1))]


def parse_param_scalar(text):
    tail = text.split(":", 1)[1] if ":" in text else text
    found = _NUM.findall(tail)
    if not found:
        raise ValueError("no number in %r" % text)
    return float(found[-1])


def offsets_by_drone(flat, drones):
    if len(flat) != 3 * len(drones):
        raise ValueError("expected %d offset values for %d drones, got %d" % (3 * len(drones), len(drones), len(flat)))
    return {d: np.array(flat[3 * i:3 * i + 3], dtype=float) for i, d in enumerate(drones)}


def offset_sanity(status_pos, odom_pos, offsets, tol=0.05):
    errs = []
    for d, off in offsets.items():
        if d not in status_pos or d not in odom_pos:
            errs.append("%s: missing status or odometry position" % d)
            continue
        w = world_position(odom_pos[d], off)
        diff = float(np.linalg.norm(w - np.asarray(status_pos[d], dtype=float)))
        if diff > tol:
            errs.append("%s: odometry+offset differs from commander position by %.3f m (> %.2f)" % (d, diff, tol))
    return errs


# ---------------------------------------------------------------- series / tracker

def evaluate(frame, series):
    return {s.name: float(s.fn(frame)) for s in series}


def _running_names(series):
    return [s.name + "_running" for s in series if s.running_min]


def csv_columns(series):
    return ["t_s", "phase"] + [s.name for s in series] + _running_names(series)


class Tracker:
    def __init__(self, drones, offsets, params, series, stale_s=STALE_S):
        self.drones = list(drones)
        self.offsets = offsets
        self.params = params
        self.series = list(series)
        self.stale_s = stale_s
        self._pos, self._vel, self._seen = {}, {}, {}
        self._cbf = frozenset()
        self._states, self._active = [], False
        self._emergency = False
        self._fence = False
        self._phase = 0
        self._start = {}
        self._runmin = {s.name: math.inf for s in self.series if s.running_min}

    def update_odom(self, drone, t, xyz, vxyz):
        self._pos[drone] = world_position(xyz, self.offsets[drone])
        self._vel[drone] = np.asarray(vxyz, dtype=float)
        self._seen[drone] = float(t)

    def update_cbf(self, names_csv):
        self._cbf = frozenset(n.strip() for n in (names_csv or "").split(",") if n.strip())

    def update_status(self, status):
        self._states = [str(d.get("state", "")) for d in status.get("drones", [])]
        self._active = bool(status.get("mission_active", False))
        self._emergency = bool((status.get("cbf") or {}).get("emergency", False))
        self._fence = bool(status.get("fence_breached", False))

    def frame(self, t):
        stale = frozenset(d for d in self.drones if d not in self._seen or t - self._seen[d] > self.stale_s)
        new = phase_from_status(self._states, self._active, self._phase)
        if new == 2 and self._phase != 2:
            self._start = {d: p.copy() for d, p in self._pos.items()}
        self._phase = new
        return Frame(t_s=float(t), pos=dict(self._pos), vel=dict(self._vel), stale=stale, cbf_active=self._cbf,
                     emergency=self._emergency, fence_breached=self._fence, phase=new,
                     start_pos=dict(self._start), params=self.params)

    def row(self, t):
        f = self.frame(t)
        vals = evaluate(f, self.series)
        out = {"phase": float(f.phase)}
        out.update(vals)
        for s in self.series:
            if s.running_min:
                v = vals[s.name]
                if f.phase == 2 and not math.isnan(v):
                    self._runmin[s.name] = min(self._runmin[s.name], v)
                r = self._runmin[s.name]
                if math.isinf(r) or (f.phase == 2 and math.isnan(v)):
                    out[s.name + "_running"] = math.nan      # before phase 2 starts, or a stale row inside it
                else:
                    out[s.name + "_running"] = r             # phase 2 so far; frozen at the last phase-2 value afterwards
        return out


# ---------------------------------------------------------------- CSV

def _meta_value(v):
    if isinstance(v, (list, tuple, np.ndarray)):
        return ",".join(repr(float(x)) if not float(x).is_integer() else str(int(x)) for x in np.ravel(v))
    return str(v)


def csv_header(series, meta):
    lines = ["# %s=%s" % (k, _meta_value(meta[k])) for k in sorted(meta)]
    lines.append(",".join(csv_columns(series)))
    return "\n".join(lines) + "\n"


def format_row(t_s, phase, values, columns):
    cells = []
    for c in columns:
        if c == "t_s":
            cells.append("%.6f" % t_s)
        elif c == "phase":
            cells.append("%d" % int(phase))
        else:
            v = values.get(c, math.nan)
            cells.append("nan" if math.isnan(v) else "%.6f" % v)
    return ",".join(cells)


def read_metrics_csv(path):
    meta, columns, data = {}, None, []
    with open(path) as fh:
        for raw in fh:
            line = raw.strip()
            if not line:
                continue
            if line.startswith("#"):
                k, _, v = line[1:].strip().partition("=")
                meta[k.strip()] = v.strip()
            elif columns is None:
                columns = line.split(",")
            else:
                cells = line.split(",")
                if len(cells) != len(columns):
                    raise MetricsCsvError("%s: ragged row (%d cells, %d columns)" % (path, len(cells), len(columns)))
                try:
                    data.append([float(c) for c in cells])
                except ValueError as e:
                    raise MetricsCsvError("%s: bad cell: %s" % (path, e))
    if columns is None:
        raise MetricsCsvError("%s: no column line" % path)
    if "offsets" not in meta:
        raise MetricsCsvError("%s: no 'offsets' meta line (world frame cannot be reproduced)" % path)
    return meta, columns, np.array(data, dtype=float).reshape(len(data), len(columns))


def meta_refs(meta):
    """The header's `refs=ref_2r:1.1;ref_r:0.55` string as {name: float}; the one parser (plot_metrics uses it)."""
    out = {}
    for part in str(meta.get("refs", "")).split(";"):
        k, _, v = part.partition(":")
        try:
            out[k.strip()] = float(v)
        except ValueError:
            continue
    return out


def meta_offsets(meta, drones):
    return offsets_by_drone([float(x) for x in meta["offsets"].split(",")], drones)


# ---------------------------------------------------------------- cross-check

def _pair_rows(t_live, t_bag, t_tol):
    """Mutual-nearest pairing; returns (live_idx, bag_idx)."""
    if len(t_live) == 0 or len(t_bag) == 0:
        return np.array([], dtype=int), np.array([], dtype=int)
    order = np.argsort(t_bag)
    tb = t_bag[order]

    def nearest(src, dst):
        i = np.clip(np.searchsorted(dst, src), 1, len(dst) - 1) if len(dst) > 1 else np.zeros(len(src), dtype=int)
        if len(dst) > 1:
            left = np.abs(src - dst[i - 1]) <= np.abs(src - dst[i])
            i = np.where(left, i - 1, i)
        return i

    j = nearest(t_live, tb)
    lo = np.argsort(t_live)
    back = lo[nearest(tb, t_live[lo])]
    idx = np.arange(len(t_live))
    ok = (np.abs(t_live - tb[j]) <= t_tol) & (back[j] == idx)
    return idx[ok], order[j[ok]]


def crosscheck(live_cols, live, bag_cols, bag, series, t_tol=0.05):
    li, bi = _pair_rows(live[:, live_cols.index("t_s")], bag[:, bag_cols.index("t_s")], t_tol)
    n_live, n_bag = len(live), len(bag)
    unpaired = 1.0 - (len(li) / n_live if n_live else 0.0)
    unpaired_bag = 1.0 - (len(bi) / n_bag if n_bag else 0.0)
    fail_all = (len(li) == 0 or (n_live - len(li)) > UNPAIRED_MAX * n_live
                or (n_bag - len(bi)) > UNPAIRED_MAX * n_bag)
    specs = [(s.name, s.tol, s.kind) for s in series] + [(s.name + "_running", s.tol, "continuous") for s in series if s.running_min]
    out = []
    for name, tol, kind in specs:
        a = live[li, live_cols.index(name)]
        b = bag[bi, bag_cols.index(name)]
        both = ~(np.isnan(a) | np.isnan(b))
        mismatch_nan = np.isnan(a) != np.isnan(b)
        diff = float(np.max(np.abs(a[both] - b[both]))) if both.any() else 0.0
        if mismatch_nan.any():
            diff = math.inf
        sl, sb = float(np.nansum(a)), float(np.nansum(b))
        if kind == "flag":
            ok = abs(sl - sb) <= max(2.0, 0.01 * len(li))
        else:
            ok = diff <= tol
        out.append(CrossRow(name, tol, kind, diff, sl, sb, int(len(li)), float(unpaired), bool(ok and not fail_all), float(unpaired_bag)))
    return out


def coverage(cols, rows):
    """Row coverage of the test window: {max_gap_s, gap_at_s, phase2_rows, phase3_rows}.

    max_gap_s = largest t_s step between consecutive rows from the row before the first phase-2 row to the row after
    the last one (inf with fewer than two such rows); gap_at_s = t_s where that step starts (nan if none)."""
    ph = rows[:, cols.index("phase")] if len(rows) else np.array([])
    t = rows[:, cols.index("t_s")] if len(rows) else np.array([])
    idx = np.flatnonzero(ph == 2)
    out = {"phase2_rows": int(len(idx)), "phase3_rows": int(np.sum(ph == 3)), "max_gap_s": math.inf, "gap_at_s": math.nan}
    if len(idx):
        span = t[max(0, idx[0] - 1):min(len(t), idx[-1] + 2)]
        if len(span) > 1:
            d = np.diff(span)
            k = int(np.argmax(d))
            out["max_gap_s"], out["gap_at_s"] = float(d[k]), float(span[k])
    return out


def nan_fraction(rows, cols, name, phase=2):
    sel = rows[rows[:, cols.index("phase")] == phase]
    if len(sel) == 0:
        return 1.0  # fail closed: no phase rows at all
    return float(np.mean(np.isnan(sel[:, cols.index(name)])))
