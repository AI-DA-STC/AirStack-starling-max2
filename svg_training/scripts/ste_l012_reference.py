#!/usr/bin/env python
"""STE task L0.12 Best-response test: write the T44 reference file from T44's run folder (read only).

    ste_l012_reference.py --t44 <T44 run folder> --out configs/ste_l012/t44_reference.npz [--variants base,tag_1p2,tag_1p4]

T44 (the L0.11 Screening sweep, records/2026-11-21_ste_l011_screen_record.md) ran on CUDA. A CPU generator does not
reproduce its start draw, so L0.12 replays T44's OWN starts: this script copies them (``start_pos_m`` of the first cell of
the first variant, 1,000 games) and the per-game results of every cell of the named variants (``ste/exploit.PER_GAME``)
into one compressed file, with T44's gate sha256 and seed. It refuses (exit 2, nothing written) when a variant is missing
or when any cell of the named variants started from other positions (they must share one start set: T44's
``paired_starts`` control). The L0.12 gate file pins the file's sha256 and the start sha256."""
from __future__ import annotations

import argparse
import json
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))

import numpy as np  # noqa: E402

from svg_training.ste import exploit  # noqa: E402

DEFAULT_VARIANTS = "base,tag_1p2,tag_1p4"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--t44", type=Path, required=True, help="T44's run folder (cells/*.json and *.npz; read only)")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--variants", default=DEFAULT_VARIANTS)
    a = ap.parse_args(argv)
    variants = [v.strip() for v in a.variants.split(",") if v.strip()]
    starts = miss = None
    sha = None
    cells: dict = {}
    for v in variants:
        batches = sorted((a.t44 / "cells").glob(f"{v}__b*.json"))
        if not batches:
            print(f"refused: no cell file of variant {v!r} in {a.t44 / 'cells'}", file=sys.stderr)
            return 2
        for path in batches:
            data = json.loads(path.read_text())
            z = np.load(path.with_suffix(".npz"))
            n = data["games"] // len(data["cells"])
            for k, (g, s) in enumerate(data["cells"]):
                sl = slice(k * n, (k + 1) * n)
                here = exploit.starts_sha(z["start_pos_m"][sl])
                if here != data["start_sha256"][k]:
                    print(f"refused: {path.name} cell {g} v {s}: start sha256 {here} is not the recorded "
                          f"{data['start_sha256'][k]}", file=sys.stderr)
                    return 2
                if sha is None:
                    starts, miss, sha = z["start_pos_m"][sl].copy(), z["start_miss"][sl].copy(), here
                elif here != sha:
                    print(f"refused: {path.name} cell {g} v {s} started from other positions ({here[:12]} v "
                          f"{sha[:12]}): the variants must share one start set", file=sys.stderr)
                    return 2
                cells[(v, g, s)] = {f: z[f][sl] for f in exploit.PER_GAME}
    gates_sha = (a.t44 / "gates.sha256").read_text().strip() if (a.t44 / "gates.sha256").is_file() else "unknown"
    seed = None
    if (a.t44 / "gates.toml").is_file():
        seed = int(tomllib.loads((a.t44 / "gates.toml").read_text())["run"]["seed"])
    meta = {"source": "T44 (L0.11 Screening sweep) run folder", "t44_run": a.t44.name, "t44_gates_sha256": gates_sha,
            "seed": seed, "variants": variants, "games": int(starts.shape[0]), "start_sha256": sha}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    exploit.write_reference(a.out, starts, miss, cells, meta)
    print(f"wrote {a.out}: {len(cells)} cells of {variants}, {starts.shape[0]} starts (sha256 {sha[:16]}), "
          f"file sha256 {exploit.sha256_file(a.out)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
