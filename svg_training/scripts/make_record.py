#!/usr/bin/env python
"""Write records/<name>_record.md and append T<n> to the training ledger.

Exit 0 when the record was written (whatever the verdict); 1 on refusal to
overwrite or unreadable input.
"""

import argparse
import hashlib
import os
import json
import re
import sys
import tomllib
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))

from svg_training.bench import record  # noqa: E402


def _earliest_date(rows):
    """Earliest row date (ISO date-time; a date without an offset is read as local time), else None."""
    best = None
    for r in rows:
        d = r.get("date")
        if not isinstance(d, str) or not d:
            continue
        try:
            t = datetime.fromisoformat(d)
            t = t if t.tzinfo else t.astimezone()
        except ValueError:
            continue
        if best is None or t < best[0]:
            best = (t, d)
    return best[1] if best else None


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--results", required=True)
    p.add_argument("--config", required=True)
    p.add_argument("--tests-passed", required=True, choices=["yes", "no"])
    p.add_argument("--name", required=True)
    p.add_argument("--seeds", required=True, help="free text: the seeds used, recorded verbatim")
    p.add_argument("--note", default="", help="free text printed at the top of the Gates section")
    p.add_argument("--flags-file", default=None,
                   help="file with one 'case num_games' line per point whose log showed a PhysX buffer overflow")
    p.add_argument("--retried-file", default=None,
                   help="file with one '<case> <num_games>: start-up crash (exit N), retried once' line per retried point")
    p.add_argument("--out-dir", default=str(ROOT / "records"))
    p.add_argument("--ledger", default=str(ROOT / "records" / "LEDGER.md"))
    a = p.parse_args(argv)
    if not a.seeds.strip():
        p.error("--seeds must not be empty")

    out = Path(a.out_dir) / f"{a.name}_record.md"
    ledger = Path(a.ledger)
    try:
        cfg_bytes = Path(a.config).read_bytes()
        cfg = tomllib.loads(cfg_bytes.decode())
        raw = Path(a.results).read_text().splitlines()
        ledger_text = ledger.read_text()
    except (OSError, ValueError) as e:  # tomllib.TOMLDecodeError is a ValueError
        print(f"unreadable input: {e}", file=sys.stderr)
        return 1
    if not os.access(ledger, os.W_OK):
        print(f"ledger not writable: {ledger}", file=sys.stderr)
        return 1
    overflow = []
    if a.flags_file and Path(a.flags_file).exists():
        try:
            for ln in Path(a.flags_file).read_text().splitlines():
                if ln.strip():
                    case, n = ln.split()
                    pt = (case, int(n))
                    if pt not in overflow:
                        overflow.append(pt)
        except (OSError, ValueError) as e:
            print(f"unreadable flags file {a.flags_file}: {e}", file=sys.stderr)
            return 1
    retried = []
    if a.retried_file and Path(a.retried_file).exists():
        try:
            for ln in Path(a.retried_file).read_text().splitlines():
                if ln.strip():
                    case, n = ln.split(":")[0].split()
                    pt = (case, int(n))
                    if pt not in retried:
                        retried.append(pt)
        except (OSError, ValueError) as e:
            print(f"unreadable retried file {a.retried_file}: {e}", file=sys.stderr)
            return 1
    rows = []
    for i, line in enumerate(raw, 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError as e:
            print(f"{a.results} line {i}: not valid JSON ({e})", file=sys.stderr)
            return 1
        if not isinstance(row, dict):
            print(f"{a.results} line {i}: not a JSON object", file=sys.stderr)
            return 1
        absent = [k for k in ("tier", "case", "num_games", "status") if k not in row]
        problem = f"missing key(s) {', '.join(absent)}" if absent else None
        if not problem:
            if not isinstance(row["case"], str):
                problem = "case must be a string"
            elif isinstance(row["num_games"], bool) or not isinstance(row["num_games"], int):
                problem = "num_games must be an integer"
            elif isinstance(row["tier"], bool) or row["tier"] not in (1, 2):
                problem = "tier must be 1 or 2"
            elif row["status"] not in ("ok", "oom", "crash"):
                problem = "status must be ok, oom or crash"
            elif row["status"] == "ok" and (isinstance(row.get("repeat"), bool)
                                            or not isinstance(row.get("repeat"), int)):
                problem = "repeat must be an integer for ok rows"
        if problem:
            print(f"{a.results} line {i}: {problem}", file=sys.stderr)
            return 1
        rows.append(row)
    if out.exists():
        print(f"refusing to overwrite {out}", file=sys.stderr)
        return 1

    first = rows[0] if rows else {}
    meta = {"name": a.name, "seeds": a.seeds, "config_path": a.config, "config_sha256": hashlib.sha256(cfg_bytes).hexdigest(),
            "machine": a.name.split("_s0_")[-1] if "_s0_" in a.name else "unknown",
            "gpu": first.get("gpu_name") or "unknown", "commit": first.get("commit") or "unknown",
            "date": _earliest_date(rows) or a.name.split("_")[0], "retried_points": retried,
            "note": a.note.strip(), "overflow_points": overflow}
    verdict = record.evaluate(rows, cfg, a.tests_passed == "yes")
    n = 1 + len(re.findall(r"^\| T\d+ \|", ledger_text, flags=re.M))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(record.render_record(rows, cfg, verdict, meta))
    if not ledger_text.endswith("\n"):
        ledger_text += "\n"
    ledger.write_text(ledger_text + record.ledger_row(n, meta, verdict) + "\n")
    print(f"wrote {out}; ledger T{n}; overall {verdict['overall']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
