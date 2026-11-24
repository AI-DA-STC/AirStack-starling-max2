#!/usr/bin/env python3
"""Summarise Crazyflie guard_show flight reports (STE track, Crazyflie route, task L0.14 / P13).

Reads ``<folder>/<date>_guard_show/report.json`` (plus ``meta.json``, and ``config/crazyflies.yaml`` for the firmware
settings, when present) and prints a Markdown summary: one row per flight, then statistics per drone role across the
flights that flew. Standard library and numpy only. It only reads: nothing is written into the folder.

    python scripts/cf_reports_summary.py <folder with the <date>_guard_show/ subfolders>

Every column is named after the report.json field it comes from (see ``FIELDS`` below). Nothing here states why a drone
behaved as it did; the "plan or aircraft" label is a numeric rule (``classify_pair``), not a finding about a mechanism.
"""
import argparse
import json
import pathlib
import re
import sys

import numpy as np

# Flights where no drone was airborne for this long are listed but left out of the statistics (the show aborted or
# failed before flying; the per-drone numbers then describe a drone on the floor).
FLOWN_MIN_AIRBORNE_S = 5.0

# Best-fit lags in the logs fall in two groups; this splits them for the count (a description of the numbers only).
LAG_SPLIT_S = 0.3

FIELDS = {
    "tracking": "drones.<cf>.tracking.error.{mean,p95,max} (commanded position vs mocap at the same instant)",
    "lag": "drones.<cf>.tracking.lag_s (delay that best lines commanded position up with mocap)",
    "resid": "drones.<cf>.tracking.residual.p95 (error left after that lag)",
    "cmd_hz": "drones.<cf>.commands.hz",
    "mocap_hz": "drones.<cf>.mocap.hz; drops = drones.<cf>.mocap.dropouts",
    "battery": "drones.<cf>.status.battery_{start,min,end} (V)",
    "pair": "fleet.closest_pair.{gap,cmd_gap,dz} and fleet.close_pairs[] (same keys)",
}


def parse_cmdline(cmdline):
    """The ``-p name:=value`` parameters of the ros2 run line, as a dict of strings."""
    return dict(re.findall(r"(\w+):=(\S+)", cmdline or ""))


def role_of(drone, params):
    """'guard' for a name in ``defenders``, 'strike' for one in ``attackers`` (the show's own parameter names); when the
    parameter is absent, ids below 10 are taken as Guard and 10 and above as Strike (the naming in these logs)."""
    d = [x for x in params.get("defenders", "").split(",") if x]
    a = [x for x in params.get("attackers", "").split(",") if x]
    if drone in d:
        return "guard"
    if drone in a:
        return "strike"
    m = re.search(r"(\d+)$", drone)
    return "guard" if m and int(m.group(1)) < 10 else "strike"


def read_config(path):
    """Uncommented ``stabilizer.controller`` / ``estimator`` / ``extPosStdDev`` values of config/crazyflies.yaml (None if
    absent). Plain-text scan; the file is not parsed as YAML so no extra library is needed."""
    f = pathlib.Path(path) / "config" / "crazyflies.yaml"
    if not f.is_file():
        return None
    out = {}
    for line in f.read_text(errors="replace").splitlines():
        body = line.split("#", 1)[0].strip()
        m = re.match(r"(controller|estimator|extPosStdDev|extQuatStdDev|enHighLevel):\s*(\S+)", body)
        if m:
            out[m.group(1)] = m.group(2)
    return out or None


def read_show_header(path):
    """The show's own start-up lines from output.log: ``controller`` (pid / mellinger) and the ``speeds`` line. Only the
    first 60 lines are read. Returns {} when output.log is absent; 'controller' is then None (not logged)."""
    f = pathlib.Path(path) / "output.log"
    out = {"controller": None, "speeds": None}
    if not f.is_file():
        return out
    with f.open(errors="replace") as fh:
        for _, line in zip(range(60), fh):
            body = re.sub(r"^\S+\s+", "", line.rstrip("\n")).strip()
            m = re.match(r"controller\s+(\w+)", body)
            if m and out["controller"] is None:
                out["controller"] = m.group(1)
            m = re.match(r"speeds\s+defence ([\d.]+), attack ([\d.]+)", body)
            if m and out["speeds"] is None:
                out["speeds"] = f"{m.group(1)}/{m.group(2)}"
    return out


def load_flights(folder):
    """List of flight dicts for every subfolder with a report.json, sorted by name, and the names of subfolders that
    have none."""
    root = pathlib.Path(folder)
    flights, missing = [], []
    for d in sorted(p for p in root.iterdir() if p.is_dir()):
        rj = d / "report.json"
        if not rj.is_file():
            missing.append(d.name)
            continue
        rep = json.loads(rj.read_text())
        mj = d / "meta.json"
        meta = json.loads(mj.read_text()) if mj.is_file() else {}
        params = parse_cmdline(meta.get("cmdline", ""))
        flights.append({"name": d.name, "report": rep, "meta": meta, "params": params, "config": read_config(d),
                        "header": read_show_header(d)})
    return flights, missing


def airborne(rep):
    vals = [(d.get("envelope") or {}).get("airborne_s") or 0.0 for d in rep["drones"].values()]
    return max(vals) if vals else 0.0


def flown(fl):
    return airborne(fl["report"]) >= FLOWN_MIN_AIRBORNE_S


def _num(x):
    """True for a finite number (report.json holds NaN where a commanded gap was not logged)."""
    return isinstance(x, (int, float)) and np.isfinite(x)


def classify_pair(pair, drones, tol=None):
    """'plan' when the commanded gap was within ``tol`` of the measured gap (the commands themselves put the two that
    close); 'aircraft' when the commands were farther apart than that. ``tol`` defaults to the sum of the two drones'
    ``tracking.error.p95`` in the same flight. A numeric rule on two reported fields, nothing more."""
    if not _num(pair.get("cmd_gap")) or not _num(pair.get("gap")):
        return "unknown"
    if tol is None:
        a, b = pair["pair"].split("/")
        tol = sum(((drones.get(x) or {}).get("tracking") or {}).get("error", {}).get("p95", 0.0) for x in (a, b))
    return "plan" if pair["cmd_gap"] - pair["gap"] <= tol else "aircraft"


def controller_of(fl):
    """Controller the show ran: output.log's 'controller' line, else the ``controller`` parameter, else 'unlogged'."""
    return fl["header"]["controller"] or fl["params"].get("controller") or "unlogged"


def flight_row(fl):
    rep, meta, p = fl["report"], fl["meta"], fl["params"]
    fleet = rep["fleet"]
    flags = {k: d["status"]["flags"] for k, d in rep["drones"].items() if (d.get("status") or {}).get("flags")}
    alarms = [a.split("  ", 1)[-1].strip() for a in fleet.get("show_alarms", []) if "ABORT" in a or "Traceback" in a]
    wins = [a for a in fleet.get("show_alarms", []) if "WINS" in a and "FINALE" not in a]
    cp = fleet.get("closest_pair") or {}
    return {
        "name": fl["name"],
        "date": (meta.get("started_iso") or fl["name"])[:16].replace("T", " "),
        "rules": p.get("rules"), "defense": p.get("defense"), "attack": p.get("attack"),
        "n_guard": len([x for x in p.get("defenders", "").split(",") if x]),
        "n_strike": len([x for x in p.get("attackers", "").split(",") if x]),
        "strike_block": p.get("strike_block"), "seed": p.get("seed"), "paced": p.get("paced"),
        "exit": meta.get("returncode"), "state": meta.get("state"),
        "airborne_s": airborne(rep), "flown": flown(fl), "flags": flags,
        "abort": alarms[0] if alarms else "", "result": wins[0].split("  ")[-1].strip() if wins else "",
        "closest_gap": cp.get("gap"), "closest_cmd_gap": cp.get("cmd_gap"),
        "n_close": len(fleet.get("close_pairs", [])), "n_downwash": len((fleet.get("downwash") or {}).get("events", [])),
        "git": (meta.get("git") or {}).get("head"), "config": fl["config"],
        "controller": controller_of(fl), "speeds": fl["header"]["speeds"],
    }


def _stat(vals):
    a = np.asarray([v for v in vals if v is not None], float)
    if a.size == 0:
        return None
    return {"n": int(a.size), "min": float(a.min()), "median": float(np.median(a)), "p95": float(np.percentile(a, 95)),
            "max": float(a.max()), "mean": float(a.mean())}


def role_stats(flights, skip_flagged=False):
    """Per role over drone-flights that flew (airborne >= FLOWN_MIN_AIRBORNE_S): lists of the report values, then
    summarised. The p95 of a tracking error is a per-drone-flight number; here its median and max over drone-flights are
    shown, and the mean error is weighted by ``tracking.samples``."""
    acc = {}
    for fl in flights:
        if not flown(fl):
            continue
        for k, d in fl["report"]["drones"].items():
            env, tr = d.get("envelope") or {}, d.get("tracking")
            if (env.get("airborne_s") or 0) < FLOWN_MIN_AIRBORNE_S or not tr:
                continue
            if skip_flagged and (d.get("status") or {}).get("flags"):
                continue
            r = acc.setdefault((role_of(k, fl["params"]), controller_of(fl)), {m: [] for m in
                               ("mean", "p95", "max", "lag", "resid", "cmd_hz", "mocap_hz", "drops", "b0", "bmin", "bend",
                                "w", "air", "speed")})
            e = tr["error"]
            r["mean"].append(e["mean"]); r["p95"].append(e["p95"]); r["max"].append(e["max"])
            r["w"].append(tr.get("samples") or 1)
            r["lag"].append(tr["lag_s"]); r["resid"].append(tr["residual"]["p95"])
            r["cmd_hz"].append((d.get("commands") or {}).get("hz"))
            r["mocap_hz"].append((d.get("mocap") or {}).get("hz")); r["drops"].append((d.get("mocap") or {}).get("dropouts"))
            st = d.get("status") or {}
            r["b0"].append(st.get("battery_start")); r["bmin"].append(st.get("battery_min")); r["bend"].append(st.get("battery_end"))
            r["air"].append(env.get("airborne_s")); r["speed"].append(env.get("top_speed"))
    out = {}
    for role, r in acc.items():
        w = np.asarray(r["w"], float)
        lag = np.asarray(r["lag"], float)
        out[role] = {
            "n_drone_flights": len(r["mean"]),
            "err_mean_weighted": float(np.average(r["mean"], weights=w)),
            "err_mean": _stat(r["mean"]), "err_p95": _stat(r["p95"]), "err_max": _stat(r["max"]),
            "lag": _stat(r["lag"]), "lag_low": int((lag < LAG_SPLIT_S).sum()), "lag_high": int((lag >= LAG_SPLIT_S).sum()),
            "resid_p95": _stat(r["resid"]), "cmd_hz": _stat(r["cmd_hz"]), "mocap_hz": _stat(r["mocap_hz"]),
            "drops": _stat(r["drops"]), "battery_start": _stat(r["b0"]), "battery_min": _stat(r["bmin"]),
            "battery_end": _stat(r["bend"]), "airborne_s": _stat(r["air"]), "top_speed": _stat(r["speed"]),
        }
    return out


def pair_events(flights):
    """Every closest/close pair event from flown flights, de-duplicated, with the plan/aircraft label."""
    ev = []
    for fl in flights:
        if not flown(fl):
            continue
        fleet = fl["report"]["fleet"]
        seen = set()
        for p in ([fleet.get("closest_pair")] if fleet.get("closest_pair") else []) + list(fleet.get("close_pairs", [])):
            key = (p["pair"], round(p["t"], 2))
            if key in seen:
                continue
            seen.add(key)
            a, b = p["pair"].split("/")
            ra, rb = role_of(a, fl["params"]), role_of(b, fl["params"])
            ev.append({"flight": fl["name"], "pair": p["pair"], "kind": "-".join(sorted((ra, rb))), "gap": p["gap"],
                       "cmd_gap": p.get("cmd_gap") if _num(p.get("cmd_gap")) else None, "dz": p.get("dz"), "jump": p.get("mocap_jump_nearby"),
                       "label": classify_pair(p, fl["report"]["drones"])})
    return ev


def _f(x, n=2):
    return "-" if not _num(x) else f"{x:.{n}f}"


def _role_table(stats, title):
    out = [f"## Per role: {title}\n"]
    out.append("| role / controller | drone-flights | err mean (weighted) m | err p95 median / max m | err max, max m | lag s median [min-max] | "
               "lag < 0.3 / >= 0.3 | resid p95 median / max m | cmd Hz median [min-max] | mocap Hz median | mocap drops median / max | "
               "battery start median V | battery min, lowest V | battery end median V |")
    out.append("|" + "---|" * 14)
    for role, ctrl in sorted(stats, key=lambda k: (k[1], k[0])):
        s = stats[(role, ctrl)]
        out.append(f"| {role} / {ctrl} | {s['n_drone_flights']} | {s['err_mean_weighted']:.3f} | {s['err_p95']['median']:.3f} / {s['err_p95']['max']:.3f} | "
                   f"{s['err_max']['max']:.3f} | {s['lag']['median']:.2f} [{s['lag']['min']:.2f}-{s['lag']['max']:.2f}] | "
                   f"{s['lag_low']} / {s['lag_high']} | {s['resid_p95']['median']:.3f} / {s['resid_p95']['max']:.3f} | "
                   f"{s['cmd_hz']['median']:.1f} [{s['cmd_hz']['min']:.1f}-{s['cmd_hz']['max']:.1f}] | {s['mocap_hz']['median']:.1f} | "
                   f"{s['drops']['median']:.0f} / {s['drops']['max']:.0f} | {s['battery_start']['median']:.2f} | "
                   f"{s['battery_min']['min']:.2f} | {s['battery_end']['median']:.2f} |")
    out.append("")
    return out


def render(flights, missing):
    rows = [flight_row(f) for f in flights]
    out = []
    flew = [r for r in rows if r["flown"]]
    out.append(f"{len(flights)} report.json read; {len(missing)} folders without report.json: {', '.join(missing) or 'none'}; "
               f"{len(flew)} flights with a drone airborne >= {FLOWN_MIN_AIRBORNE_S:g} s (the statistics use these only).\n")
    out.append("## Per flight\n")
    out.append("| start (local) | code | rules | defense | attack | G/S | strike_block | seed | paced | controller | speeds def/atk m/s | exit (state) | airborne s | "
               "crashes / flags | first ABORT or error | result line | closest pair m | close-pair events | downwash events |")
    out.append("|" + "---|" * 19)
    for r in rows:
        fl = "; ".join(f"{k}: {','.join(v)}" for k, v in r["flags"].items()) or "-"
        out.append(f"| {r['date']} | {r['git']} | {r['rules']} | {r['defense']} | {r['attack']} | {r['n_guard']}/{r['n_strike']} | "
                   f"{r['strike_block'] or '-'} | {r['seed']} | {r['paced']} | {r['controller']} | {r['speeds'] or '-'} | {r['exit']} ({r['state']}) | {r['airborne_s']:.0f} | "
                   f"{fl} | {r['abort'][:70] or '-'} | {r['result'][:50] or '-'} | {_f(r['closest_gap'])} | {r['n_close']} | {r['n_downwash']} |")
    out.append("\nG/S = number of names in `defenders` / `attackers` (the show's own parameter names; Guard / Strike here). "
               "airborne s = the largest `drones.*.envelope.airborne_s`. controller and speeds = the show's start-up lines in output.log ('unlogged' = no such line, 6 Nov flights) or the `controller` parameter; they are the show's settings, read from the log, not from report.json.\n")
    cfgs = {}
    for r in rows:
        cfgs.setdefault(json.dumps(r["config"], sort_keys=True), []).append(r["date"][:10])
    out.append("## config/crazyflies.yaml firmware settings (uncommented lines)\n")
    for k, v in cfgs.items():
        out.append(f"- {k}: {len(v)} flights, folders dated {', '.join(sorted(set(v)))}")
    out.append("")
    for title, skip in (("all drone-flights airborne >= 5 s", False),
                        ("same, leaving out drone-flights with a `status.flags` entry (crashed, tumbled)", True)):
        out.extend(_role_table(role_stats(flights, skip), title))
    out.append("\nField sources: " + "; ".join(f"{k}: {v}" for k, v in FIELDS.items()) + "\n")
    ev = pair_events(flights)
    out.append("## Closest pairs (fleet.closest_pair and fleet.close_pairs of flown flights)\n")
    out.append("| pair kind | events | gap m min / median / p95 | cmd_gap m min / median | cmd_gap - gap, median / p95 m | label plan | label aircraft | label unknown (no cmd_gap) |")
    out.append("|---|---|---|---|---|---|---|---|")
    for kind in ("guard-guard", "guard-strike", "strike-strike", "ALL"):
        e = [x for x in ev if kind == "ALL" or x["kind"] == kind]
        if not e:
            continue
        g = np.array([x["gap"] for x in e]); c = np.array([x["cmd_gap"] for x in e if x["cmd_gap"] is not None])
        sh = np.array([x["cmd_gap"] - x["gap"] for x in e if x["cmd_gap"] is not None])
        out.append(f"| {kind} | {len(e)} | {g.min():.2f} / {np.median(g):.2f} / {np.percentile(g, 95):.2f} | "
                   f"{(c.min() if c.size else float('nan')):.2f} / {(np.median(c) if c.size else float('nan')):.2f} | "
                   f"{(np.median(sh) if sh.size else float('nan')):.2f} / {(np.percentile(sh, 95) if sh.size else float('nan')):.2f} | "
                   f"{sum(x['label'] == 'plan' for x in e)} | {sum(x['label'] == 'aircraft' for x in e)} | "
                   f"{sum(x['label'] == 'unknown' for x in e)} |")
    out.append("\nLabel rule (`classify_pair`): 'plan' if cmd_gap - gap <= the sum of the two drones' tracking.error.p95 in that "
               "flight, else 'aircraft'. It compares two reported numbers; it does not say why they differ.")
    out.append("\n### Closest pair of each flown flight\n")
    out.append("| start | pair | gap m | cmd_gap m | dz m | label |")
    out.append("|---|---|---|---|---|---|")
    for fl in flights:
        cp = (fl["report"]["fleet"].get("closest_pair") or {})
        if flown(fl) and cp:
            out.append(f"| {(fl['meta'].get('started_iso') or fl['name'])[:16]} | {cp['pair']} | {cp['gap']:.2f} | "
                       f"{_f(cp.get('cmd_gap'))} | {cp.get('dz', float('nan')):+.2f} | "
                       f"{classify_pair(cp, fl['report']['drones'])} |")
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("folder", help="folder holding the <date>_guard_show/ subfolders (read only)")
    a = ap.parse_args(argv)
    flights, missing = load_flights(a.folder)
    if not flights:
        print(f"no report.json under {a.folder}", file=sys.stderr)
        return 1
    print(render(flights, missing))
    return 0


if __name__ == "__main__":
    sys.exit(main())
