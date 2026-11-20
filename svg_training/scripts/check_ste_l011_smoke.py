#!/usr/bin/env python
"""Check a run folder of the L0.11 CUDA smoke (configs/ste_l011/cuda_smoke_gates.toml; pre-launch QC section 5 B, I6).

    check_ste_l011_smoke.py --run-dir runs/<date>_ste_l011_cuda_smoke [--expect-sigint] [--device-expected cuda]

One line per check, PASS / FAIL / WARN, then a summary. Exit 0 when no check FAILs (a WARN asks the lead to act but does
not fail), 1 otherwise, 2 when the folder cannot be read. Checks:
1. the job ended with exit 0 (the exit_code file of scripts/ste_job.py);
2. every control in results.json is PASS (the two known-non-zero ones, the same-seed replay at the full game length,
   every zero control and the global checks), and the run did not stop early;
3. the device was the expected one (cuda);
4. the same-seed replay covered one whole base batch (cells per batch x games per cell games, at the gate's ticks);
5. results.json, results.md, controls.json, figures/base_heatmap.png and at least one clip in videos/ exist;
6. with --expect-sigint (the B.8 drill): launches.jsonl shows a launch that ended with exit 4 and a later launch that
   ended with exit 0, and no batch file written before the relaunch was rewritten after it;
7. timing (WARN only): the base batch's seconds per tick against the gate's [projection.seconds_per_batch_tick] "3v3";
   more than 10 % slower means the 1.1 safety factor does not cover the error: put the full-batch figure in the sweep's
   gate file before its launch."""
from __future__ import annotations

import argparse
import json
import sys
import tomllib
from pathlib import Path

TIMING_TOLERANCE = 0.10


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--run-dir", type=Path, required=True)
    ap.add_argument("--expect-sigint", action="store_true")
    ap.add_argument("--device-expected", default="cuda")
    a = ap.parse_args(argv)
    run = a.run_dir
    try:
        result = json.loads((run / "results.json").read_text())
        gates = tomllib.loads((run / "gates.toml").read_text())
    except (OSError, ValueError) as err:
        print(f"FAIL cannot read the run folder: {err}")
        return 2
    lines: list[tuple[str, str]] = []

    def check(ok: bool, text: str, warn: bool = False) -> None:
        lines.append(("PASS" if ok else "WARN" if warn else "FAIL", text))

    code = (run / "exit_code").read_text().strip() if (run / "exit_code").is_file() else None
    check(code == "0", f"exit code {code} (want 0)")
    bad = {k: v["status"] for k, v in result["controls"].items() if v["status"] != "PASS"}
    check(not bad and result["controls_all_pass"], f"{len(result['controls'])} controls, not PASS: {bad or 'none'}")
    kinds = {v["control"] for v in result["controls"].values()}
    want_kinds = {"tag_fires", "reach_fires", "same_seed_twice", "stand_still_never_reaches", "stand_still_zero_tags",
                  "zero_tags", "global"}
    check(want_kinds <= kinds, f"control kinds present: {sorted(kinds)}")
    check(not result.get("stopped"), f"run stopped: {result.get('stopped')}")
    device = str(result["meta"]["device"])
    check(device.startswith(a.device_expected), f"device {device} ({result['meta'].get('gpu')}), want {a.device_expected}")
    r = gates["run"]
    batch = json.loads((run / "cells" / "ctl_same_seed__b00.json").read_text()) if (
        run / "cells" / "ctl_same_seed__b00.json").is_file() else None
    want_games = int(r["cells_per_batch"]) * int(r["games_per_cell"])
    check(batch is not None and batch["games"] == want_games,
          f"same-seed replay: {batch['games'] if batch else 'missing'} games (want one whole base batch, {want_games}), "
          f"{batch['steps_played'] if batch else '-'} ticks played of at most {r['ticks_cap']}")
    for rel in ("results.json", "results.md", "controls.json", "figures/base_heatmap.png"):
        check((run / rel).is_file(), f"{rel} written")
    clips = sorted((run / "videos").glob("*.gif")) if (run / "videos").is_dir() else []
    check(bool(clips), f"clips: {[c.name for c in clips]}")
    if a.expect_sigint:
        events = [json.loads(x) for x in (run / "launches.jsonl").read_text().splitlines() if x.strip()]
        ends = [e for e in events if e["event"] == "end"]
        starts = {e["launch"]: e["time"] for e in events if e["event"] == "launch"}
        interrupted = [e for e in ends if e["exit_code"] == 4]
        later = [e for e in ends if e["exit_code"] == 0 and interrupted and e["launch"] > interrupted[0]["launch"]]
        check(bool(interrupted) and bool(later), f"SIGINT drill: launch ends {[(e['launch'], e['exit_code']) for e in ends]}"
                                                 f" (want an exit 4, then a later exit 0)")
        resumes = json.loads((run / "checkpoint.latest").read_text())["state"].get("resumes", [])
        if interrupted and later:
            kept = [(bid, (run / "cells" / (bid.replace("/", "__") + ".json")).stat().st_mtime < r["time"])
                    for r in resumes for bid in r["done"]]
            check(bool(resumes) and bool(kept) and all(ok for _, ok in kept),
                  f"resumed {len(resumes)} time(s); {sum(ok for _, ok in kept)} of {len(kept)} batches finished before "
                  f"a resume were kept, not replayed")
    base = json.loads((run / "cells" / "base__b00.json").read_text()) if (run / "cells" / "base__b00.json").is_file() else None
    table = gates["projection"]["seconds_per_batch_tick"]
    if base and "3v3" in table:
        spt = base["seconds"] / max(base["steps_played"], 1)
        ratio = spt / float(table["3v3"])
        check(ratio <= 1 + TIMING_TOLERANCE,
              f"base batch {spt * 1e3:.1f} ms per tick over {base['steps_played']} ticks, {base['games']} games; the "
              f"gate's 3v3 figure {float(table['3v3']) * 1e3:.1f} ms (ratio {ratio:.2f}); over 1.10: put this figure in "
              f"the sweep's [projection]", warn=True)
    for status, text in lines:
        print(f"{status} {text}")
    failed = sum(1 for s, _ in lines if s == "FAIL")
    print(f"{'SMOKE PASS' if not failed else 'SMOKE FAIL'}: {failed} FAIL, "
          f"{sum(1 for s, _ in lines if s == 'WARN')} WARN of {len(lines)} checks")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
