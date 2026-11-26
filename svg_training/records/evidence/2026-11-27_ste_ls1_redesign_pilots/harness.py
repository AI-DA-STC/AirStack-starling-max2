"""R50 pilot harness (scratch, INFO, not of record): replay a stand-in skill network in T94's own batches.

Reads only: the T94 read folders (layout, stored script games), the gate file, the saved LS1.1 networks.
Writes nothing in the repository or in runs/. Usage from svg_training/ with PYTHONPATH=source.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[0]
SVG = Path.home() / "AirStack-starling-max2-dev" / "svg_training"
sys.path.insert(0, str(SVG / "scripts"))
sys.path.insert(0, str(SVG / "source"))

import ste_ls1_equivalence as eq  # noqa: E402
from svg_training.ste import cells, skill_net  # noqa: E402

_all_codes = skill_net.all_codes


def _patched_all_codes(net, obs):
    """Pilot assemblies run each skill once per row (all_flat); every other network the stock path."""
    if hasattr(net, "all_flat"):
        return net.all_flat(obs)
    return _all_codes(net, obs)


skill_net.all_codes = _patched_all_codes

GATES = "configs/ste_ls1/distil_gates.toml"
SHA = "5cce1245052f2e9ef87d6a3c83d2301f1161100ed818224b932b0248735ee6bb"


def ctx_of(side: str) -> eq.Ctx:
    args = eq.parse(["--gates", GATES, "--side", side,
                     "--skill-net", f"runs/2026-11-26_ste_ls11_distil_{side}/skill_net_{side}.pt",
                     "--run-dir", f"runs/2026-11-26_ste_ls12_read_{side}", "--cap-h", "12",
                     "--expect-gates-sha256", SHA])
    ctx, why = eq.prepare(args)
    if why:
        raise SystemExit(f"prepare refused: {why}")
    return ctx


def net_batches(ctx: eq.Ctx, info: bool = True) -> list[eq.Batch]:
    """T94's network batches (R1 gated; R2 info if ``info``), cells and chunks as T94 played them."""
    stages = (eq.STAGE_R1, eq.STAGE_R2N) if info else (eq.STAGE_R1,)
    return [b for b in eq.plan_batches(ctx) if b.stage in stages]


def check_layout(ctx: eq.Ctx, batches: list[eq.Batch]) -> None:
    """Every network batch matches T94's layout.json entry (cells, codes, order): same batch shape -> exact replay."""
    have = {b["name"]: b for b in json.loads((ctx.run_dir / eq.LAYOUT_FILE).read_text())["batches"]}
    for b in batches:
        want = eq.layout_entry(ctx, b)
        got = have.get(b.name)
        if got is None:
            raise SystemExit(f"layout: {b.name} not in T94's layout.json")
        strip = lambda e: [(c["index"], c["codes"], c["opponent"]) for c in e["cells"]]
        if strip(got) != strip(want):
            raise SystemExit(f"layout: {b.name} differs from T94's")


def cell_label(c: cells.Cell) -> str:
    return f"{','.join(c.choice['flies'])} v {c.opponent}"


def replay(ctx: eq.Ctx, net, batches: list[eq.Batch], *, labels: bool = False, log=print) -> list[dict]:
    """Play ``batches`` with ``net`` as the network arm; pair each cell with T94's stored scripted games.
    Returns one row per cell: index, kind, codes, opponent, b, c, flips, ci. ``labels``: keep the labeller (command
    error against the scripts, slower)."""
    reader = eq.Reader(ctx, eq.plan_batches(ctx))
    ctx.net, ctx.net_sha = net, "pilot"
    rows = []
    for b in batches:
        t0 = time.perf_counter()
        pg = eq.play_batch(ctx, b, reader, None, lambda: False)
        for i, c in enumerate(b.cells):
            mine = eq.exploit.slice_cell(pg, i, ctx.n)
            e = eq.cell_entry(mine, reader.reference(c), ctx.side, ctx.z_cell)
            rows.append({"index": c.index, "kind": c.kind, "codes": list(c.choice["flies"]), "opponent": c.opponent,
                         "b": int(e["b"]), "c": int(e["c"]), "flips": int(e["flips"]), "ci": e["ci"],
                         "batch": b.name})
        log(f"  {b.name}: {len(b.cells)} cells, {time.perf_counter() - t0:.1f} s, "
            f"max flips {max(r['flips'] for r in rows[-len(b.cells):])}")
    return rows


def t94_rows(side: str) -> dict:
    """T94's network-arm cells {index: row} (r1_net and r2_net)."""
    res = json.loads((SVG / f"runs/2026-11-26_ste_ls12_read_{side}/results.json").read_text())
    out = {}
    for r in res["cells"]:
        if r["arm"] == "net":
            out[(r["kind"], tuple(r["codes"]), r["opponent"])] = r
    return out


def gated_ok(rows: list[dict], limit_flips: int = 30, margin: float = 0.045) -> tuple[int, int]:
    """(cells over the flip limit, cells with the interval outside +-margin) among gated cells."""
    g = [r for r in rows if r["kind"] != cells.INFO]
    over = sum(r["flips"] > limit_flips for r in g)
    wide = sum(not (-margin <= r["ci"][0] and r["ci"][1] <= margin) for r in g)
    return over, wide
