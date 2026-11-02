"""changes_log — the ONE format of a live parameter-change line (owner rule 2026-11-02). Sim-only tooling.

    <time> · <name> · <old> → <new> · <who> · readback <value>[ · MISMATCH][ · UNVERIFIED <why>][ · REFUSED <why>]

time = ISO-8601 local time with its UTC offset (a unix float is converted); old / new / readback are numbers printed
with %g, integers in full (unknown = "?", no read-back = "readback n/a"). name is a PX4 parameter, optionally with
its drone: `drone_2/MC_YAW_P` (parse_change splits it into target + name). ` · MISMATCH` is added when the read-back
differs from the value set (same()); ` · UNVERIFIED <why>` when nothing confirmed the value PX4 holds (no read-back, a
failed pull, no set mechanism reported success); ` · REFUSED <why>` when the set was never sent (CHG-0018). One line per change, appended to `changes.log`. Writers: the yaw_step sweep in
tools/sim_tests/yaw_step/fly.sh and tools/lib/px4_param_set.sh (`tools/sim.sh param set`), which calls the CLI:

    python3 changes_log.py append --log L --name drone_N/NAME --old O --new V --who W [--readback R] [--time T]
                                  [--unverified WHY] [--refused WHY]

prints the line it appended; exit 1 when it is a MISMATCH, UNVERIFIED or REFUSED. Readers: yaw_step gates.py (log vs the ulog's
changed_parameters) and report.py's "Changes in this run" block (changes_block, below). The append path is stdlib only:
it runs on the host and in the robot container. Run capture (host only, CHG-0017; docs/CODING_STANDARD.md §3):

    python3 changes_log.py diff <heavy_dir> -o <out>    # params_start_<target>.yaml vs params_end_<target>.yaml
    python3 changes_log.py ulog <ulog>... -o <out>      # every drone's ULog.changed_parameters, boot-time included

diff needs PyYAML, ulog needs pyulog (exit 4 without). A missing source is printed as "unknown (<why>)", never empty.
"""
import argparse
import datetime
import json
import os
import re
import sys
from pathlib import Path

SEP = " · "
ARROW = " → "
MISMATCH = "MISMATCH"
UNVERIFIED = "UNVERIFIED "
REFUSED = "REFUSED "


def _t(t):
    if isinstance(t, (int, float)):
        return datetime.datetime.fromtimestamp(float(t)).astimezone().isoformat(timespec="seconds")
    if isinstance(t, datetime.datetime):
        return t.astimezone().isoformat(timespec="seconds")
    return str(t)


def _v(x):
    if x is None:
        return "?"
    if isinstance(x, bool):
        return str(x)
    if isinstance(x, int):
        return str(x)
    if isinstance(x, float):
        return "%g" % x
    return str(x)


def _one_line(s):
    return " ".join(str(s).split())


def _num(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def same(a, b):
    """True when a and b are the same value: numbers within float32 rounding (rel 1e-6), other strings identical."""
    if a is None or b is None:
        return False
    fa, fb = _num(a), _num(b)
    if fa is None or fb is None:
        return str(a) == str(b)
    return abs(fa - fb) <= 1e-6 * max(1.0, abs(fa), abs(fb))


def _field(s):
    """One field: one line, and never the separator."""
    return _one_line(s).replace(SEP.strip(), ",").replace(" ,", ",")


def format_change(t, name, old, new, who, readback=None, unverified=None, refused=None):
    """One change-log line (no trailing newline). unverified / refused: the reason, appended as a marker."""
    rb = "readback n/a" if readback is None else "readback " + _v(readback)
    parts = [_t(t), _field(name), _v(old) + ARROW + _v(new), _field(who), rb]
    if readback is not None and not same(new, readback):
        parts.append(MISMATCH)
    if unverified:
        parts.append(UNVERIFIED + _field(unverified))
    if refused:
        parts.append(REFUSED + _field(refused))
    return SEP.join(parts)



def parse_change(line):
    """dict(time, target, name, old, new, who, readback, mismatch, unverified, refused) of one line; None when it is not
    a change line. target = the `drone_N` before a `/` in the name field (None without one); name = the bare parameter
    name; unverified / refused = the reason (None without the marker)."""
    parts = line.rstrip("\n").split(SEP)
    if len(parts) < 5 or ARROW not in parts[2] or not parts[4].startswith("readback "):
        return None
    mark = {"mismatch": False, "unverified": None, "refused": None}
    for extra in parts[5:]:
        if extra == MISMATCH:
            mark["mismatch"] = True
        elif extra.startswith(UNVERIFIED):
            mark["unverified"] = extra[len(UNVERIFIED):]
        elif extra.startswith(REFUSED):
            mark["refused"] = extra[len(REFUSED):]
        else:
            return None
    old, _, new = parts[2].partition(ARROW)
    target, _, name = parts[1].rpartition("/")
    return dict(time=parts[0], target=target or None, name=name, old=_num(old), new=_num(new), who=parts[3],
                readback=_num(parts[4][len("readback "):]), **mark)


def append_change(path, t, name, old, new, who, readback=None, unverified=None, refused=None):
    """Append one line to `path` (created if missing); returns the line."""
    line = format_change(t, name, old, new, who, readback, unverified=unverified, refused=refused)
    with open(path, "a") as fh:
        fh.write(line + "\n")
    return line


# ----------------------------------------------------------------------------------------------- run capture (CHG-0017)
BOOT_S = 2.0              # PX4 SITL logs ~46 boot-time settings (CAL_*, MAV_*, SENS_*, SYS_*, UXRCE_*) at 0.9-1.0 s
MIN_PX4_PARAMS = 500      # a MAVROS dump with fewer PX4 parameters is partial (a PX4 drone has ~900)
PX4_BOOKKEEPING = ("LND_FLIGHT_T_HI", "LND_FLIGHT_T_LO", "COM_FLIGHT_UUID")    # PX4 writes these itself (at disarm)
_PX4_NAME = re.compile(r"^[A-Z][A-Z0-9_]*$")


def _flatten(d, prefix, out):
    for k, v in d.items():
        key = prefix + str(k)
        if isinstance(v, dict):
            _flatten(v, key + ".", out)
        elif isinstance(v, list):
            out[key] = json.dumps(v)
        else:
            out[key] = str(v)


def read_dump(text):
    """{name: value-string} of a `ros2 param dump` (lines before the first `/node:` line are shell noise). Nested keys
    joined with `.`, lists as JSON. Needs PyYAML (ImportError otherwise)."""
    import yaml
    lines = text.splitlines()
    k = next((i for i, l in enumerate(lines) if l.startswith("/")), len(lines))
    doc = yaml.safe_load("\n".join(lines[k:])) or {}
    out = {}
    for node in (doc.values() if isinstance(doc, dict) else []):
        if isinstance(node, dict) and isinstance(node.get("ros__parameters"), dict):
            _flatten(node["ros__parameters"], "", out)
    return out


def diff_dumps(a, b):
    """[(name, old, new)] where the two dumps differ; numbers compare with same(); one side only -> "(absent)"."""
    return [(k, a.get(k, "(absent)"), b.get(k, "(absent)")) for k in sorted(set(a) | set(b))
            if not (k in a and k in b and same(a[k], b[k]))]


def ulog_changes(text):
    """[(t_s, target, name, value)] of px4_param_changes_all.txt (`t_s drone_N NAME value`; `#` lines skipped)."""
    rows = []
    for l in text.splitlines():
        f = l.split()
        if len(f) == 4 and not l.startswith("#") and _num(f[0]) is not None:
            rows.append((float(f[0]), f[1], f[2], f[3]))
    return rows


def ulog_targets(text):
    """The drones whose ulog the list covers (`# ulog drone_N <file>` header lines)."""
    return {f[2] for f in (l.split() for l in text.splitlines()) if len(f) >= 3 and f[:2] == ["#", "ulog"]}


def _snap_rows(text):
    """params_diff.txt -> ([(target, name, old, new)], [notes from `#` lines])."""
    rows, notes = [], []
    for l in text.splitlines():
        if not l.strip():
            continue
        if l.startswith("#"):
            notes.append(l.lstrip("# ").strip())
            continue
        left, _, new = l.partition(" -> ")
        key, _, old = left.partition(" ")
        target, _, name = key.partition("/")
        rows.append((target, name, old, new))
    return rows, notes


def _why_no_diff(heavy):
    h = Path(heavy) if heavy is not None else None
    if h is None or not h.is_dir() or not list(h.glob("params_start_*.yaml")):
        return "no start snapshot: the run stopped before its snapshot phase, or it predates CHG-0017"
    if not list(h.glob("params_end_*.yaml")):
        return "no end snapshot: the run aborted or failed before the post-flight evidence"
    return "params_diff.txt not written: host PyYAML missing? see run.log"


def _drones(out, heavy, covered):
    """The run's drones: run_meta.txt num_robots, else the start snapshots in heavy, else the drones the ulog list covers."""
    m = re.search(r"^num_robots=(\d+)\s*$", (out / "run_meta.txt").read_text() if (out / "run_meta.txt").is_file() else "", re.M)
    if m:
        return ["drone_%d" % i for i in range(1, int(m.group(1)) + 1)]
    h = Path(heavy) if heavy is not None else None
    found = {p.name[len("params_start_"):-len(".yaml")] for p in h.glob("params_start_drone_*.yaml")} if h is not None and h.is_dir() else set()
    return sorted(found | set(covered), key=lambda t: int(t.split("_")[1]) if t.split("_")[1].isdigit() else 0)


def block_caveat(lines):
    """ONE record caveat when the block flags anything (UNLOGGED CHANGE, CONFLICT) or a source is unknown; None if clean.
    Print-only: it never changes the verdict."""
    n_unl = sum(1 for l in lines if l.startswith("- UNLOGGED CHANGE"))
    n_con = sum(1 for l in lines if l.startswith("- CONFLICT"))
    n_unk = sum(1 for l in lines if "unknown (" in l)
    if not (n_unl or n_con or n_unk):
        return None
    what = ", ".join(s for s in (f"{n_unl} UNLOGGED CHANGE" if n_unl else "", f"{n_con} CONFLICT" if n_con else "",
                                 f"{n_unk} unknown source(s)" if n_unk else "") if s)
    return (f"Changes in this run: {what} — read that block before trusting which parameters this run flew "
            "(print-only; the verdict is unchanged).")


def _fence(lines):
    return ["```", *lines, "```"]


def changes_block(out, heavy, airframe_text=None):
    """The record's "Changes in this run" block (markdown lines). Sources: out/changes.log (the tools),
    out/px4_param_changes_all.txt (PX4's own list from the ulogs; it wins a conflict), out/params_diff.txt (start/end
    snapshots), heavy/params_start_drone_1.yaml vs the sim airframe. A source that is missing reads "unknown (<why>)"."""
    out = Path(out)
    L = ["## Changes in this run", "",
         "What changed while this run flew (docs/CODING_STANDARD.md §3), from three sources. PX4's own list (the ulog) "
         "is the ground truth and wins a conflict.", ""]

    # 1  the tools' log
    L += ["**Logged by the tools (`changes.log`):**", ""]
    logp = out / "changes.log"
    logged = []
    if not logp.is_file():
        L += ["unknown (changes.log was not copied out of the robot container: the run stopped before the stack was up, "
              "or it predates CHG-0017)"]
    else:
        raw = [l for l in logp.read_text().splitlines() if l.strip()]
        logged = [c for c in (parse_change(l) for l in raw) if c and not c["refused"]]      # REFUSED never reached PX4
        L += _fence(raw) if raw else ["none logged"]

    # 2  the ulog
    ulp = out / "px4_param_changes_all.txt"
    ul = ulog_changes(ulp.read_text()) if ulp.is_file() else None
    covered = ulog_targets(ulp.read_text()) if ulp.is_file() else set()
    after = [r for r in (ul or []) if r[0] > BOOT_S]
    nboot = len(ul or []) - len(after)
    L += ["", f"**PX4 ulog, parameters changed after boot (vehicle time, t > {BOOT_S:g} s; {nboot} boot-time settings not listed):**", ""]
    drones = _drones(out, heavy, covered)
    no_ulog = [d for d in drones if d not in covered] if ul is not None else []
    if ul is None:
        L += ["unknown (px4_param_changes_all.txt missing: no ulog was copied, or host pyulog failed; see the caveats)"]
    elif after:
        L += _fence(["%.3f %s %s %s" % r for r in after])
    else:
        L += ["none after boot" + ("" if covered else " (the list names no drone's ulog)")]
    if no_ulog:
        L += ["- unknown (no ulog for " + ", ".join(no_ulog) + ")"]

    # 3  the snapshots
    L += ["", "**Parameter snapshot, start → end of the flight (MAVROS for PX4, `ros2 param dump /swarm_commander`; "
          "catches Foxglove, QGC, `ros2 param set`):**", ""]
    dp = out / "params_diff.txt"
    snap, notes = _snap_rows(dp.read_text()) if dp.is_file() else ([], [])
    if not dp.is_file():
        L += ["unknown (" + _why_no_diff(heavy) + ")"]
    else:
        if snap:
            L += _fence(["%s/%s %s -> %s" % r for r in snap])
        elif not notes:
            L += ["no differences"]
        L += ["- unknown (" + n + ")" for n in notes]

    # 4  drone_1 at the start vs the airframe file
    L += ["", "**PX4 at the start vs the airframe file (drone_1):**", ""]
    sp = Path(heavy) / "params_start_drone_1.yaml" if heavy is not None else None
    try:
        start = read_dump(sp.read_text()) if sp is not None and sp.is_file() else None
        why = "no start snapshot of drone_1"
    except ImportError:
        start, why = None, "host PyYAML missing"
    except Exception as e:               # an unreadable dump must not cost the record
        start, why = None, f"start snapshot unreadable: {type(e).__name__}"
    if start is None:
        L += [f"unknown ({why})"]
    else:
        try:
            import airframe_params as AP
            text = airframe_text if airframe_text is not None else (AP.REPO / AP.AIRFRAME).read_text()
            want = {l.name: l.value for l in AP.parse_airframe(text)}
        except Exception as e:           # a missing or unparseable airframe must not cost the record
            want, why = None, f"airframe file unreadable: {type(e).__name__}: {e}"
        if want is None:
            L += [f"unknown ({why})"]
        else:
            bad = []
            for n, v in want.items():
                have = start.get(n)
                if have is None:
                    bad.append(f"- {n}: airframe {v:g}, not in the snapshot")
                elif not same(v, have):
                    bad.append(f"- {n}: airframe {v:g}, in force {have}")
            L += bad or [f"all {len(want)} airframe values in force"]

    # 5  conflicts and unlogged changes
    L += ["", "**Conflicts and unlogged changes:**", ""]
    probs = []

    def logs_for(target, name):
        return [c for c in logged if c["name"] == name and c["target"] in (target, None)]

    for t, target, name, v in after:
        if name in PX4_BOOKKEEPING:
            probs.append(f"- PX4 bookkeeping (not a tuning change): {target}/{name} → {v} at {t:.3f} s")
        elif not any(same(c["new"], v) or same(c["readback"], v) for c in logs_for(target, name)):
            probs.append(f"- UNLOGGED CHANGE (ulog): {target}/{name} → {v} at {t:.3f} s — not in this run's changes.log "
                         "(set before the run? see ~/flight_logs/sim/changes.log)")
    seen = set()
    for c in reversed(logged):                                  # the last logged value per parameter
        targets = [c["target"]] if c["target"] else sorted({r[1] for r in after if r[2] == c["name"]} or covered or {"drone_1"})
        for target in targets:
            if (target, c["name"]) in seen or not target.startswith("drone_"):
                continue
            seen.add((target, c["name"]))
            last = [r for r in after if r[1] == target and r[2] == c["name"]]
            if last and not same(c["new"], last[-1][3]):
                probs.append(f"- CONFLICT: changes.log has {target}/{c['name']} → {_v(c['new'])}, the ulog shows {last[-1][3]} "
                             f"at {last[-1][0]:.3f} s — the ulog wins")
            elif not last and ul is not None and target in covered:
                probs.append(f"- CONFLICT: {target}/{c['name']} logged but absent from the ulog list — did PX4 receive it?")
    for target, name, old, new in snap:
        lg = logs_for(target, name)
        if name in PX4_BOOKKEEPING:
            probs.append(f"- PX4 bookkeeping (not a tuning change): {target}/{name} {old} → {new} (snapshot)")
        elif not lg:
            probs.append(f"- UNLOGGED CHANGE: {target}/{name} {old} → {new} (snapshot; no tool logged it: Foxglove, QGC "
                         "or ros2 param set?)")
        elif not same(lg[-1]["new"], new):
            probs.append(f"- CONFLICT: changes.log last has {target}/{name} → {_v(lg[-1]['new'])}, the end snapshot shows {new} "
                         "(a later set nobody logged, or a set PX4 did not keep)")
    noted = [n.split(":", 1)[0] for n in notes if re.match(r"^[A-Za-z0-9_]+:", n)]
    unknown = ([n for n, gone in (("changes.log", not logp.is_file()), ("the ulog list", ul is None), ("the snapshot diff", not dp.is_file())) if gone]
               + ["the ulog of " + d for d in no_ulog] + ["the snapshot of " + t for t in noted])
    tail = "not checked against " + ", ".join(unknown) + " (unknown above)" if unknown else ""
    if probs:
        L += probs + (["- " + tail] if tail else [])
    else:
        L += ["- none" + (" found; " + tail if tail else "")]
    return L


def _write_diff(heavy, out):
    h = Path(heavy)
    starts = sorted(h.glob("params_start_*.yaml"))
    lines = []
    if not starts:
        lines.append(f"# no start snapshot in {h}")
    for sp in starts:
        target = sp.name[len("params_start_"):-len(".yaml")]
        ep = h / f"params_end_{target}.yaml"
        if not ep.is_file():
            lines.append(f"# {target}: no end snapshot")
            continue
        try:
            a, b = read_dump(sp.read_text()), read_dump(ep.read_text())
        except ImportError:
            raise
        except Exception as e:
            lines.append(f"# {target}: snapshot unreadable ({type(e).__name__})")
            continue
        if not a or not b:
            lines.append(f"# {target}: empty {'start' if not a else 'end'} snapshot")
            continue
        if target.startswith("drone_"):
            na, nb = (sum(1 for k in d if _PX4_NAME.match(k)) for d in (a, b))
            if min(na, nb) < MIN_PX4_PARAMS:
                lines.append(f"# {target}: partial snapshot (start {na}, end {nb} PX4 parameters, < {MIN_PX4_PARAMS}); its rows are skipped")
                continue
        lines += [f"{target}/{n} {o} -> {v}" for n, o, v in diff_dumps(a, b)]
    Path(out).write_text("".join(l + "\n" for l in lines))
    return 0 if starts else 1


def _ulog_value(v):
    if isinstance(v, float):
        return "%.7g" % v                    # PX4 floats are float32
    return str(v)


def _write_ulog(paths, out):
    from pyulog import ULog
    lines = []
    for p in paths:
        m = re.search(r"drone_(\d+)_sysid", os.path.basename(p))
        target = f"drone_{m.group(1)}" if m else os.path.basename(p)
        u = ULog(p, message_name_filter_list=["vehicle_status"])
        lines.append(f"# ulog {target} {os.path.basename(p)}")
        lines += ["%.3f %s %s %s" % (ts / 1e6, target, name, _ulog_value(v)) for ts, name, v in u.changed_parameters]
    Path(out).write_text("".join(l + "\n" for l in lines))
    return 0


def _cli_value(s):
    """A CLI string as the formatter wants it: int, float, None (empty or "?") or the string itself."""
    if s is None or s in ("", "?"):
        return None
    try:
        return int(s)
    except ValueError:
        pass
    f = _num(s)
    return s if f is None else f


def main(argv=None):
    ap = argparse.ArgumentParser(prog="changes_log.py", description="the one live parameter-change line, and the run capture (sim only)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("append", help="append one line to --log and print it; exit 1 on MISMATCH, UNVERIFIED or REFUSED")
    a.add_argument("--log", required=True)
    a.add_argument("--time", default=None, help="default: now")
    a.add_argument("--name", required=True, help="drone_N/NAME or NAME")
    a.add_argument("--old", default=None)
    a.add_argument("--new", required=True)
    a.add_argument("--who", required=True)
    a.add_argument("--readback", default=None)
    a.add_argument("--unverified", default=None, help="why nothing confirmed the value (marks the line UNVERIFIED)")
    a.add_argument("--refused", default=None, help="why the set was never sent (marks the line REFUSED)")
    d = sub.add_parser("diff", help="start/end snapshot diff of a run's heavy dir (needs PyYAML; exit 4 without)")
    d.add_argument("heavy"); d.add_argument("-o", "--out", required=True)
    u = sub.add_parser("ulog", help="every changed_parameters entry of the ulogs (needs pyulog; exit 4 without)")
    u.add_argument("ulogs", nargs="+"); u.add_argument("-o", "--out", required=True)
    o = ap.parse_args(argv)
    if o.cmd in ("diff", "ulog"):
        try:
            return _write_diff(o.heavy, o.out) if o.cmd == "diff" else _write_ulog(o.ulogs, o.out)
        except ImportError as e:
            print(f"changes_log.py {o.cmd}: {e} (pip install {'pyyaml' if o.cmd == 'diff' else 'pyulog'})", file=sys.stderr)
            return 4
    d = os.path.dirname(o.log)
    if d:
        os.makedirs(d, exist_ok=True)
    t = o.time if o.time else datetime.datetime.now()
    new, rb = _cli_value(o.new), _cli_value(o.readback)
    print(append_change(o.log, t, o.name, _cli_value(o.old), new, o.who, readback=rb, unverified=o.unverified, refused=o.refused))
    return 1 if (rb is not None and not same(new, rb)) or o.unverified or o.refused else 0


if __name__ == "__main__":
    sys.exit(main())
