"""changes_log — the ONE format of a live parameter-change line (owner rule 2026-11-02). Sim-only tooling.

    <time> · <name> · <old> → <new> · <who> · readback <value>

time = ISO-8601 local time with its UTC offset (a unix float is converted); old / new / readback are numbers printed
with %g (unknown = "?", no read-back = "readback n/a"). One line per change, appended to `changes.log` in the run
folder. Used by tools/sim_tests/yaw_step/fly.sh (copied into the robot container next to it by `tools/sim.sh test`)
and by gates.py to compare the log with the ulog's changed_parameters. Stdlib only: it runs on the host and in the
robot container.
"""
import datetime

SEP = " · "
ARROW = " → "


def _t(t):
    if isinstance(t, (int, float)):
        return datetime.datetime.fromtimestamp(float(t)).astimezone().isoformat(timespec="seconds")
    if isinstance(t, datetime.datetime):
        return t.astimezone().isoformat(timespec="seconds")
    return str(t)


def _v(x):
    if x is None:
        return "?"
    if isinstance(x, (int, float)):
        return "%g" % x
    return str(x)


def _one_line(s):
    return " ".join(str(s).split())


def format_change(t, name, old, new, who, readback=None):
    """One change-log line (no trailing newline)."""
    rb = "readback n/a" if readback is None else "readback " + _v(readback)
    return SEP.join((_t(t), _one_line(name), _v(old) + ARROW + _v(new), _one_line(who), rb))


def _num(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def parse_change(line):
    """dict(time, name, old, new, who, readback) of one line; None when it is not a change line."""
    parts = line.rstrip("\n").split(SEP)
    if len(parts) != 5 or ARROW not in parts[2] or not parts[4].startswith("readback "):
        return None
    old, _, new = parts[2].partition(ARROW)
    return dict(time=parts[0], name=parts[1], old=_num(old), new=_num(new), who=parts[3],
                readback=_num(parts[4][len("readback "):]))


def append_change(path, t, name, old, new, who, readback=None):
    """Append one line to `path` (created if missing); returns the line."""
    line = format_change(t, name, old, new, who, readback)
    with open(path, "a") as fh:
        fh.write(line + "\n")
    return line
