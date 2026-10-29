#!/usr/bin/env python3
"""Generic record renderer for `tools/sim.sh` tests (DOCS_STANDARD §4).

    report.py <test_dir> <run_dir> [--heavy D] [--record P] [--ledger N] [--issue NEAR-nnn] [--no-verdict-log]

<test_dir>/test.env gives the words (TITLE PURPOSE SCOPE SIM_ONLY_LINE ISSUE MILESTONE CONFIG SCENARIO BAG_PREFIX
DURATION_S BASELINE); <test_dir>/gates.py gives the rows:

    build_rows(out: Path, heavy: Path, env: dict) -> (list[Row], ctx dict)
    ledger_sentence(rows, ctx, verdict) -> str
    figure_caption(ctx) -> str            # 2-4 sentences, <= 380 chars, without the leading "Figure 1."

ctx keys read here: headline, crosscheck (list[CrossRow] | None), node_log_tail, test_stdout, caveats, tuning.
Every gate row is PASS / FAIL / UNVERIFIED; an info row never passes or fails the run; missing evidence is UNVERIFIED.
Exit: 0 PASS, 2 INCOMPLETE, 1 FAIL, 3 ABORTED (<run_dir>/aborted.txt exists). Writes <record>.md and one line in
<run_dir>/verdicts.log. Sim-only (CLAUDE.md iron rule 9)."""
from __future__ import annotations

import argparse
import dataclasses
import datetime
import importlib.util
import json
import pathlib
import re
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
EXIT = {"PASS": 0, "INCOMPLETE": 2, "FAIL": 1, "ABORTED": 3}
VERDICT_DEF = ("PASS = every gate PASS; INCOMPLETE = no FAIL but ≥ 1 gate UNVERIFIED; FAIL = any gate FAIL; "
               "ABORTED = Ctrl-C landing, never a result.")


# ----------------------------------------------------------------------------- rows
@dataclasses.dataclass
class Row:
    check: str
    criterion: str
    measured: str
    baseline: str
    verdict: str
    gate: bool


def row(rows: list, check: str, crit: str, meas: str, base: str, ok, gate: bool = True) -> Row:
    """gate rows: ok True/False/None -> PASS/FAIL/UNVERIFIED. info rows (gate=False) are always `info`."""
    v = ("UNVERIFIED" if ok is None else ("PASS" if ok else "FAIL")) if gate else "info"
    r = Row(check, crit, meas, base, v, gate)
    rows.append(r)
    return r


def overall_verdict(rows, aborted: bool = False) -> str:
    if aborted:
        return "ABORTED"
    gates = [r for r in rows if r.gate]
    if any(r.verdict == "FAIL" for r in gates):
        return "FAIL"
    if any(r.verdict == "UNVERIFIED" for r in gates):
        return "INCOMPLETE"
    return "PASS"


# ----------------------------------------------------------------------------- parsers
def parse_env(path) -> dict:
    """Shell `KEY=value` / `KEY="value"` lines (comments and blanks skipped)."""
    env = {}
    for line in pathlib.Path(path).read_text().splitlines():
        m = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_]*)=(.*?)\s*$", line)
        if not m:
            continue
        v = m.group(2)
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
            v = v[1:-1]
        env[m.group(1)] = v
    return env


def parse_kv(text: str) -> dict:
    """`key=value` tokens (run_meta.txt, isaac_evidence.txt)."""
    out = {}
    for k, v in re.findall(r"(\w+)=(\S+)", text):
        out.setdefault(k, v)
    return out


def parse_armed_post(text: str):
    """Exactly drone_1..3 each with `armed: true|false`; any garbage or missing drone -> None."""
    found = {}
    for line in text.splitlines():
        m = re.match(r"^\s*(drone_[123]) armed: (true|false)\s*$", line)
        if m:
            found[m.group(1)] = m.group(2) == "true"
    return found if set(found) == {"drone_1", "drone_2", "drone_3"} else None


def read(out, name: str) -> str:
    p = pathlib.Path(out) / name
    try:
        return p.read_text() if p.is_file() else ""
    except OSError:
        return ""


def _num(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def git_head_short() -> str:
    try:
        r = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=10)
        return r.stdout.strip() or "?"
    except Exception:
        return "?"


# ----------------------------------------------------------------------------- shared evidence rows
def isaac_rows(rows, out):
    ev = {k: _num(v) for k, v in parse_kv(read(out, "isaac_evidence.txt")).items()}
    for key, crit, want in [("autostart", "SYS_AUTOSTART=10090 x3", lambda n: n >= 3),
                            ("ready", "Ready for takeoff x3", lambda n: n == 3),
                            ("unknown_model", "no 'Unknown model'", lambda n: n == 0),
                            ("cooking", "no PhysX cooking warnings", lambda n: n == 0)]:
        n = ev.get(key)
        row(rows, "Isaac launch: " + crit, crit, "n/a" if n is None else str(int(n)), "-", None if n is None else want(n))
    sc = ev.get("starling_cfg")
    if not sc:   # 0 or missing: the launcher print was not captured, never PASS "indirectly"
        row(rows, "Isaac launch: Starling2MaxConfig x3", "Starling2MaxConfig x3 (launcher print)", "0 — launcher print not captured", "-", None)
    else:
        row(rows, "Isaac launch: Starling2MaxConfig x3", "Starling2MaxConfig x3 (launcher print)", str(int(sc)), "-", sc >= 3)


def landing_rows(rows, out):
    land = read(out, "landing_evidence.txt")
    n1 = len(re.findall(r"landed, disarmed \(attempt 1\)", land))
    nany = len(re.findall(r"landed, disarmed", land))
    row(rows, "landing: 'landed, disarmed' x3 (commander ACK log, not an arming display)", "informational",
        f"{nany} 'landed, disarmed' ({n1} on attempt 1)" + ("; 'disarm not accepted' seen" if "disarm not accepted" in land else "") if land else "n/a",
        "#13: attempt 1 x3", None, gate=False)
    armed = parse_armed_post(read(out, "armed_post.txt"))
    if armed is None:
        row(rows, "post-flight armed=false x3 (MAVROS state)", "armed: false for drone_1, drone_2, drone_3",
            "n/a — armed_post.txt does not hold three readable `drone_N armed: true|false` lines", "-", None)
    else:
        row(rows, "post-flight armed=false x3 (MAVROS state)", "armed: false for drone_1, drone_2, drone_3",
            ", ".join(f"{k} {'true' if v else 'false'}" for k, v in sorted(armed.items())), "-", not any(armed.values()))


def evidence_rows(rows, out, heavy, bag_prefix, extra_files=()):
    out = pathlib.Path(out)
    heavy = pathlib.Path(heavy) if heavy is not None else None
    crit = f"bag dir {bag_prefix}_* with metadata.yaml under the heavy folder" + (f", and {', '.join(extra_files)} in the run folder" if extra_files else "")
    bagdir = next((p for p in sorted(heavy.glob(bag_prefix + "_*")) if p.is_dir()), None) if heavy is not None and heavy.is_dir() else None
    if bagdir is None:
        row(rows, "rosbag copied + readable", crit, f"n/a — no {bag_prefix}_* dir under {heavy if heavy is not None else 'the heavy folder'}", "-", None)
    else:
        mb = sum(p.stat().st_size for p in bagdir.rglob("*") if p.is_file()) // 1_000_000
        has_meta = (bagdir / "metadata.yaml").is_file()
        absent = [f for f in extra_files if not (out / f).is_file()]
        row(rows, "rosbag copied + readable", crit,
            f"{bagdir.name}: {mb} MB, metadata.yaml {'present' if has_meta else 'MISSING'}"
            + (f"; MISSING in run folder: {', '.join(absent)}" if absent else ""), "-", has_meta and not absent)
    ulogs = [l.split() for l in read(out, "ulog_sysid_map.txt").splitlines() if l.strip()]
    sysids = sorted(u[0] for u in ulogs if u)
    row(rows, "PX4 ulogs one per sysid 2/3/4", "ulog_sysid_map.txt lists sysids 2, 3, 4 (drone_1/2/3)",
        f"{len(ulogs)} files, sysids {sysids}" if ulogs else "n/a — ulog_sysid_map.txt missing or empty", "-", (sysids == ["2", "3", "4"]) if ulogs else None)
    rw = read(out, "res_watch.log")
    wifi = rw.count("WIFI-ALERT")
    row(rows, "WiFi firmware alerts", "0 during the run", str(wifi) if rw else "n/a — no res_watch.log", "-", (wifi == 0) if rw else None)
    meta = parse_kv(read(out, "run_meta.txt"))
    now = git_head_short()
    ran = meta.get("head_short") or "?"
    code = f"ran at {ran}" if ran == now else f"ran at {ran}, report at {now}"
    if _num(meta.get("dirty_tools")):
        code += " (tools/ had uncommitted changes)"
    if not meta:
        code = f"n/a — no run_meta.txt; report at {now}"
    row(rows, "code that ran", "informational (run_meta.txt head vs git HEAD at report time)", code, "-", None, gate=False)
    history = [l for l in read(out, "verdicts.log").splitlines() if l.strip()]
    row(rows, "driver verdict history", "informational (every earlier generation of this record, newest last)",
        "<br>".join(f"`{l}`" for l in history) if history else "none — first generation", "-", None, gate=False)


def crosscheck_rows(rows, cr, headline: str):
    crit = f"live metrics.csv agrees with the rosbag recompute ({headline} within tolerance; flags by count)"
    if cr is None:
        row(rows, "live vs bag recompute", crit, "n/a — no bag recompute available", "-", None)
        return
    if not cr:
        row(rows, "live vs bag recompute", crit, "n/a — recompute compared no columns", "-", None)
        return
    parts = [f"{c.name} Σ {c.sum_live:g} vs {c.sum_bag:g}" if c.kind == "flag" else f"{c.name} Δmax {c.max_abs_diff:g} (tol {c.tol:g})" for c in cr]
    unp = max(c.unpaired_frac for c in cr)
    row(rows, "live vs bag recompute", crit, "; ".join(parts) + f"; unpaired {unp * 100:.1f} %", "-", all(c.ok for c in cr))


# ----------------------------------------------------------------------------- verdict log + record
def append_verdict(out, verdict: str, rows, head_short: str) -> str:
    n_fail = sum(1 for r in rows if r.gate and r.verdict == "FAIL")
    n_unv = sum(1 for r in rows if r.gate and r.verdict == "UNVERIFIED")
    stamp = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    line = f"{stamp} head={head_short} verdict={verdict} fail={n_fail} unverified={n_unv}"
    with open(pathlib.Path(out) / "verdicts.log", "a") as fh:
        fh.write(line + "\n")
    return line


def ledger_row(num, today, sentence, run, issue) -> str:
    return f"| {'?' if num is None else num} | {today} | SIM | {sentence} | [{run}_record.md]({run}_record.md) | {issue or '?'} |"


def _cell(s) -> str:
    return str(s).replace("|", "\\|").replace("\n", " ")


def _size_mb(p: pathlib.Path) -> int:
    return (sum(q.stat().st_size for q in p.rglob("*") if q.is_file()) if p.is_dir() else p.stat().st_size) // 1_000_000


def render(env, rows, ctx, out, heavy, verdict, history, ledger, issue) -> str:
    out = pathlib.Path(out)
    run = out.name
    meta = parse_kv(read(out, "run_meta.txt"))
    started, tz = meta.get("started", "n/a"), meta.get("tz", "")
    times = re.findall(r"^\[(\d\d:\d\d:\d\d)\]", ctx.get("test_stdout") or "", re.M)
    span = f"{times[0]}–{times[-1]}" if times else ""
    today = datetime.date.today().isoformat()
    title = env.get("TITLE", run)
    when = f"started {started} {tz}".rstrip() + (f"; flight {span} UTC" if span else "; flight span n/a")
    head = git_head_short()
    video = read(out, "video.txt").strip() or "none recorded"
    tuning = ctx.get("tuning") or {}
    ledger_sentence = ctx.get("ledger_sentence") or f"{title}: {verdict}"   # main() fills both from gates.py
    caption = ctx.get("figure_caption") or "Caption missing: the test's gates.py returned none."
    repo_files = sorted(p.name for p in out.iterdir() if p.is_file()) if out.is_dir() else []
    heavy_files = []
    if heavy is not None and pathlib.Path(heavy).is_dir():
        heavy_files = [f"`{p.name}` ({_size_mb(p)} MB)" for p in sorted(pathlib.Path(heavy).iterdir())]
    L = [f"RECORD · SIM — {run}. Sim-only (iron rule 9): {env.get('SIM_ONLY_LINE', 'none of these values is ported to the drone.')}", "",
         f"# {run} — {title} ({when})", "",
         f"**Verdict: {verdict}.** {env.get('PURPOSE', '')} For Linear {env.get('ISSUE', issue or '?')} (milestone {env.get('MILESTONE', '?')}). "
         f"{VERDICT_DEF} Report generated {today} at repo `{head}`.", "",
         f"**Scope:** {env.get('SCOPE', '')}", "",
         "## Setup", "", "| Item | Value |", "|---|---|",
         "| Sim | Isaac Sim, 3 Starling 2 Max (`DRONE_USD=starling2max.usd`, `PX4_VEHICLE_MODEL=pegasus_starling2max`), default flat world |",
         "| Airframe | `10090_pegasus_starling2max` (sim-only airframe gains, see the S5 hover records) |",
         f"| Commander | `{env.get('CONFIG', '?')} scenario:={env.get('SCENARIO', '?')}`, tuning {json.dumps(tuning) if tuning else 'n/a'} |",
         f"| Driver | `tools/sim.sh test {env.get('NAME', run)}`, repo commit `{meta.get('head', meta.get('head_short', 'n/a'))}` (tools/ uncommitted changes: {meta.get('dirty_tools', 'n/a')}) |",
         f"| Started | {started} {tz} (laptop clock, `run_meta.txt`); flight {span or 'n/a'} UTC (container clock) |",
         f"| Video | {video} |",
         "", "## Pass/fail", "",
         "| Check | Criterion | Measured | Baseline | Verdict |", "|---|---|---|---|---|"]
    for r in rows:
        v = f"**{r.verdict}**" if r.verdict in ("FAIL", "UNVERIFIED") else r.verdict
        L.append("| " + " | ".join(_cell(x) for x in (r.check, r.criterion, r.measured, r.baseline, v)) + " |")
    L += ["", "Rows marked info are informational and never pass or fail the run.", ""]
    if (out / "fig-1.png").exists():
        L += ['<a id="fig-1"></a>', f"![{title}]({run}/fig-1.png)", "", f"*Figure 1. {caption}*", ""]
    armed = parse_armed_post(read(out, "armed_post.txt"))
    L += ["## Driver verdict history", "",
          "Every generation of this record (`verdicts.log`, newest last; the last line is this one):", "", "```",
          "\n".join(history) if history else "none", "```", "",
          "## Evidence", "",
          "Flight script stdout (times are UTC, container clock):", "```", (ctx.get("test_stdout") or "n/a").strip(), "```", "",
          "Metrics node log (tail):", "```", (ctx.get("node_log_tail") or "n/a").strip(), "```", "",
          "Landing (commander ACK log) and post-flight MAVROS state:", "```",
          ((read(out, "landing_evidence.txt").strip() or "n/a") + "\n"
           + ("\n".join(f"{k} armed: {'true' if v else 'false'}" for k, v in sorted(armed.items())) if armed else "armed_post.txt: unreadable")).strip(),
          "```", ""]
    cr = ctx.get("crosscheck")
    L += ["Live vs bag recompute:", ""]
    if cr:
        L += ["| Column | Kind | Tolerance | Max diff | Σ live | Σ bag | Paired | Unpaired | OK |", "|---|---|---|---|---|---|---|---|---|"]
        L += [f"| {c.name} | {c.kind} | {c.tol:g} | {c.max_abs_diff:g} | {c.sum_live:g} | {c.sum_bag:g} | {c.paired} | {c.unpaired_frac * 100:.1f} % | {'yes' if c.ok else '**no**'} |" for c in cr]
    else:
        L += ["n/a — no recompute was available."]
    L += ["", "## Files", "",
          f"- Repo (this folder, `docs/record/{run}/`): " + (", ".join(f"`{f}`" for f in repo_files) if repo_files else "nothing") + ".",
          f"- Not in the repo (`{heavy if heavy is not None else '~/flight_logs/sim/' + run}/`): " + (", ".join(heavy_files) if heavy_files else "nothing copied") + ".",
          "", "## Caveats", ""]
    L += [f"- {c}" for c in (ctx.get("caveats") or [])] or ["- none recorded."]
    which = "next free number" if ledger is None else f"#{ledger}"
    L += ["", f"## Ledger row draft (docs/record/LEDGER.md table 1, {which}, {issue if issue else 'issue ?'})", "",
          ledger_row(ledger, today, ledger_sentence, run, issue), "", ""]
    return "\n".join(L)


def load_gates(test_dir):
    path = pathlib.Path(test_dir) / "gates.py"
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "live"))
    spec = importlib.util.spec_from_file_location("gates_" + pathlib.Path(test_dir).resolve().name.replace("-", "_"), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ----------------------------------------------------------------------------- CLI
def issue_id(s: str) -> str:
    if not re.fullmatch(r"NEAR-\d+", s):
        raise argparse.ArgumentTypeError(f"{s!r} is not a Linear issue id of the form NEAR-nnn")
    return s


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0], formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("test_dir")
    ap.add_argument("run_dir")
    ap.add_argument("--heavy", default=None, help="bag + ulog folder (default ~/flight_logs/sim/<run>)")
    ap.add_argument("--record", default=None, help="markdown path (default <run_dir>/../<run>_record.md)")
    ap.add_argument("--no-verdict-log", action="store_true")
    ap.add_argument("--ledger", type=int, default=None, help="number of the NEW LEDGER table-1 row (default: ?)")
    ap.add_argument("--issue", type=issue_id, default=None, help="Linear issue id NEAR-nnn (default: the test.env ISSUE)")
    a = ap.parse_args(argv)
    out = pathlib.Path(a.run_dir).resolve()
    if not out.is_dir():
        print(f"not a directory: {out}", file=sys.stderr)
        return 2
    test_dir = pathlib.Path(a.test_dir)
    env = parse_env(test_dir / "test.env")
    env.setdefault("NAME", test_dir.resolve().name)
    gates = load_gates(test_dir)
    heavy = pathlib.Path(a.heavy).expanduser() if a.heavy else pathlib.Path.home() / "flight_logs" / "sim" / out.name
    rec = pathlib.Path(a.record) if a.record else out.parent / f"{out.name}_record.md"
    rows, ctx = gates.build_rows(out, heavy, env)
    verdict = overall_verdict(rows, aborted=(out / "aborted.txt").exists())
    history = [l for l in read(out, "verdicts.log").splitlines() if l.strip()]
    if not a.no_verdict_log:
        history.append(append_verdict(out, verdict, rows, parse_kv(read(out, "run_meta.txt")).get("head_short", "?")))
    issue = a.issue or env.get("ISSUE")
    ctx["ledger_sentence"] = gates.ledger_sentence(rows, ctx, verdict)
    ctx["figure_caption"] = gates.figure_caption(ctx)
    rec.write_text(render(env, rows, ctx, out, heavy, verdict, history, a.ledger, issue))
    print(f"{verdict}: {rec}")
    for r in rows:
        if r.gate and r.verdict != "PASS":
            print(f"  {r.verdict:10s} {r.check}: {r.measured}")
    return EXIT[verdict]


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
