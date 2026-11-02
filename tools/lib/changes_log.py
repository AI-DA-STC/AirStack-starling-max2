"""changes_log — the ONE format of a live parameter-change line (owner rule 2026-11-02). Sim-only tooling.

    <time> · <name> · <old> → <new> · <who> · readback <value>[ · MISMATCH]

time = ISO-8601 local time with its UTC offset (a unix float is converted); old / new / readback are numbers printed
with %g, integers in full (unknown = "?", no read-back = "readback n/a"). name is a PX4 parameter, optionally with
its drone: `drone_2/MC_YAW_P` (parse_change splits it into target + name). ` · MISMATCH` is added when the read-back
differs from the value set (same()). One line per change, appended to `changes.log`. Writers: the yaw_step sweep in
tools/sim_tests/yaw_step/fly.sh and tools/lib/px4_param_set.sh (`tools/sim.sh param set`), which calls the CLI:

    python3 changes_log.py append --log L --name drone_N/NAME --old O --new V --who W [--readback R] [--time T]

prints the line it appended; exit 1 when it is a MISMATCH. Readers: yaw_step gates.py (log vs the ulog's
changed_parameters). Stdlib only: it runs on the host and in the robot container.
"""
import argparse
import datetime
import os
import sys

SEP = " · "
ARROW = " → "
MISMATCH = "MISMATCH"


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


def format_change(t, name, old, new, who, readback=None):
    """One change-log line (no trailing newline)."""
    rb = "readback n/a" if readback is None else "readback " + _v(readback)
    parts = [_t(t), _one_line(name), _v(old) + ARROW + _v(new), _one_line(who), rb]
    if readback is not None and not same(new, readback):
        parts.append(MISMATCH)
    return SEP.join(parts)



def parse_change(line):
    """dict(time, target, name, old, new, who, readback, mismatch) of one line; None when it is not a change line.
    target = the `drone_N` before a `/` in the name field (None without one); name = the bare parameter name."""
    parts = line.rstrip("\n").split(SEP)
    mismatch = len(parts) == 6 and parts[5] == MISMATCH
    if mismatch:
        parts = parts[:5]
    if len(parts) != 5 or ARROW not in parts[2] or not parts[4].startswith("readback "):
        return None
    old, _, new = parts[2].partition(ARROW)
    target, _, name = parts[1].rpartition("/")
    return dict(time=parts[0], target=target or None, name=name, old=_num(old), new=_num(new), who=parts[3],
                readback=_num(parts[4][len("readback "):]), mismatch=mismatch)


def append_change(path, t, name, old, new, who, readback=None):
    """Append one line to `path` (created if missing); returns the line."""
    line = format_change(t, name, old, new, who, readback)
    with open(path, "a") as fh:
        fh.write(line + "\n")
    return line


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
    ap = argparse.ArgumentParser(prog="changes_log.py", description="append one live parameter-change line (sim only)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("append", help="append one line to --log and print it; exit 1 on a read-back MISMATCH")
    a.add_argument("--log", required=True)
    a.add_argument("--time", default=None, help="default: now")
    a.add_argument("--name", required=True, help="drone_N/NAME or NAME")
    a.add_argument("--old", default=None)
    a.add_argument("--new", required=True)
    a.add_argument("--who", required=True)
    a.add_argument("--readback", default=None)
    o = ap.parse_args(argv)
    d = os.path.dirname(o.log)
    if d:
        os.makedirs(d, exist_ok=True)
    t = o.time if o.time else datetime.datetime.now()
    new, rb = _cli_value(o.new), _cli_value(o.readback)
    print(append_change(o.log, t, o.name, _cli_value(o.old), new, o.who, readback=rb))
    return 1 if rb is not None and not same(new, rb) else 0


if __name__ == "__main__":
    sys.exit(main())
