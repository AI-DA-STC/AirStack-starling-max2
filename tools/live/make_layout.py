#!/usr/bin/env python3
"""make_layout — build a test's Foxglove layout.json. Sim-only tooling: nothing here has seen a real flight.

    make_layout.py <test_dir> [--check] [--base PATH]

Reads CMU's read-only base layout (svg_basestation.json) and <test_dir>/plots.json, validates every series name
against <test_dir>/metrics.py (SERIES, "<name>_running" for running_min series, REFERENCES keys, "phase"), and writes
<test_dir>/layout.json with one Plot panel per plot plus a StateTransitions panel for the phase. Output is
deterministic. --check exits 0 when layout.json is current, 1 when stale or missing, 2 on error.
"""
import argparse
import copy
import importlib.util
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
BASE_LAYOUT = REPO / "AirStack/robot/ros_ws/src/svg_ground_control/foxglove/svg_basestation.json"
TOPIC = "/svg/test/"

if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))


class LayoutError(ValueError):
    pass


def load_series_names(test_dir):
    path = pathlib.Path(test_dir) / "metrics.py"
    if not path.is_file():
        raise LayoutError("no metrics.py in %s" % test_dir)
    spec = importlib.util.spec_from_file_location("svg_layout_metrics", str(path))
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
        names = set()
        for s in mod.SERIES:
            names.add(s.name)
            if getattr(s, "running_min", False):
                names.add(s.name + "_running")
        names |= set(getattr(mod, "REFERENCES", {}))
    except Exception as e:
        raise LayoutError("bad metrics.py in %s: %s: %s" % (test_dir, type(e).__name__, e))
    names.add("phase")
    return names


def plot_panel(plot):
    names = list(plot.get("series", [])) + list(plot.get("refs", []))
    cfg = {
        "paths": [{"value": TOPIC + n + ".data", "enabled": True, "timestampMethod": "receiveTime", "label": n}
                  for n in names],
        "title": plot.get("title", plot["id"]),
        "xAxisVal": "timestamp",
        "showLegend": True,
        "legendDisplay": "floating",
        "showPlotValuesInLegend": True,
        "isSynced": True,
        "followingViewWidth": 60,
        "showXAxisLabels": True,
        "showYAxisLabels": True,
    }
    yr = plot.get("y_range")
    if yr:
        cfg["minYValue"], cfg["maxYValue"] = yr[0], yr[1]
    return cfg


def phase_panel(name):
    return {"paths": [{"value": TOPIC + name + ".data", "timestampMethod": "receiveTime"}], "isSynced": True}


def _leaves(t):
    return 1 if isinstance(t, str) else _leaves(t["first"]) + _leaves(t["second"])


def column_tree(ids):
    if not ids:
        raise LayoutError("no panels to lay out")
    if len(ids) == 1:
        return ids[0]
    k = (len(ids) + 1) // 2
    return {"direction": "column", "first": column_tree(ids[:k]), "second": column_tree(ids[k:]),
            "splitPercentage": round(100 * k / len(ids))}


def render(base, plots, known):
    cfg = copy.deepcopy(base["configById"])
    ids = []
    seen = set()
    for p in plots["plots"]:
        pid = p["id"]
        if pid in seen:
            raise LayoutError("duplicate plot id '%s'" % pid)
        seen.add(pid)
        for n in list(p.get("series", [])) + list(p.get("refs", [])):
            if n not in known:
                raise LayoutError("plot '%s': unknown series '%s'" % (pid, n))
        cfg["Plot!svgtest_" + pid] = plot_panel(p)
        ids.append("Plot!svgtest_" + pid)
    phase = plots.get("phase_series", "phase")
    if phase not in known:
        raise LayoutError("phase_series '%s' is not a known series" % phase)
    cfg["StateTransitions!svgtest_phase"] = phase_panel(phase)
    pct = plots.get("panel_width_pct", 50)
    out = {k: copy.deepcopy(v) for k, v in base.items() if k not in ("configById", "layout")}
    out["configById"] = cfg
    out["layout"] = {"direction": "row", "first": copy.deepcopy(base["layout"]),
                     "second": column_tree(["StateTransitions!svgtest_phase"] + ids),
                     "splitPercentage": 100 - pct}
    return out


def dumps(layout):
    return json.dumps(layout, indent=2, sort_keys=True) + "\n"


def build(test_dir, base_path):
    td = pathlib.Path(test_dir)
    try:
        base = json.loads(pathlib.Path(base_path).read_text())
        plots = json.loads((td / "plots.json").read_text())
    except (OSError, ValueError) as e:
        raise LayoutError("cannot read inputs: %s" % e)
    return render(base, plots, load_series_names(td))


def main(argv=None):
    ap = argparse.ArgumentParser(description="plots.json + base layout -> layout.json")
    ap.add_argument("test_dir")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--base", default=str(BASE_LAYOUT))
    a = ap.parse_args(argv)
    try:
        layout = build(a.test_dir, a.base)
    except LayoutError as e:
        print("make_layout: %s" % e, file=sys.stderr)
        return 2
    text = dumps(layout)
    out = pathlib.Path(a.test_dir) / "layout.json"
    if a.check:
        if out.is_file() and out.read_text() == text:
            return 0
        print("stale: run python3 tools/live/make_layout.py %s" % a.test_dir)
        return 1
    out.write_text(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
