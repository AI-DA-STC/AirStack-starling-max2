"""Step C (LS1_1P15_SWITCH.md): the scripted arms of the read at 1.15 m (stages c1, c1m, r2 scripts) in the read's own
batch layout, stored as games/<batch>.npz + layout.json + controls.json in runs/2026-11-27_ste_ls12_1p15_scripts_<side>.
The network check is bypassed (no network flies); --smoke --games 1000 so the FILL_ limits load and 1,000 games a cell
are read (asserted). Scratch, INFO, not of record. usage: c.py <side>"""
import json, sys, time
from pathlib import Path
import numpy as np, torch

SVG = Path.home() / "AirStack-starling-max2-dev" / "svg_training"
sys.path.insert(0, str(SVG / "scripts")); sys.path.insert(0, str(SVG / "source"))
import ste_ls1_equivalence as eq  # noqa: E402
from svg_training.ste import scoring  # noqa: E402

torch.set_num_threads(8)
side = sys.argv[1]
GATES = "configs/ste_ls1/distil_gates_1p15.toml"
RUN = SVG / f"runs/2026-11-27_ste_ls12_1p15_scripts_{side}"
eq.net_check = lambda args, g, cfg: ((None, None), None)
args = eq.parse(["--gates", GATES, "--side", side, "--skill-net", "none", "--run-dir", str(RUN), "--cap-h", "12",
                 "--smoke", "--games", "1000"])
ctx, why = eq.prepare(args)
if why:
    raise SystemExit(f"prepare refused: {why}")
assert ctx.n == 1000, ctx.n
assert ctx.variant == "tag_1p15", ctx.variant
assert abs(float(ctx.cfg.tag.radius_m) - 1.15) < 1e-9, ctx.cfg.tag.radius_m
batches = eq.plan_batches(ctx)
ref_batches = [b for b in batches if b.stage in eq.REFERENCE_STAGES]
print(f"[{side}] game tag {ctx.cfg.tag.radius_m} m; n {ctx.n}; {len(ref_batches)} scripted batches of {len(batches)}",
      flush=True)
(RUN / eq.GAMES_DIR).mkdir(parents=True, exist_ok=True)
reader = eq.Reader(ctx, batches)
layout = {"batches": [], "note": "step C scratch driver (LS1_1P15_SWITCH.md): scripted stages only"}
controls = {}
for b in ref_batches:
    path = reader.path(b)
    e = eq.layout_entry(ctx, b)
    t0 = time.perf_counter()
    pg = eq.play_batch(ctx, b, reader, None, lambda: False)
    e["seconds"] = time.perf_counter() - t0
    scoring.save_batch(path.with_name(f"{b.name}.part.npz"), pg)
    path.with_name(f"{b.name}.part.npz").replace(path)
    layout["batches"].append(e)
    ctl = eq.batch_control(ctx, b, pg, reader)
    controls[b.name] = ctl
    (RUN / eq.LAYOUT_FILE).write_text(json.dumps(layout, indent=1))
    (RUN / eq.CONTROLS_FILE).write_text(json.dumps(controls, indent=1, default=str))
    print(f"  {b.name}: {len(b.cells)} cells, {e['seconds']:.0f} s, {ctl['status']} ({ctl['detail']})", flush=True)
bad = [k for k, v in controls.items() if v["status"] != "PASS"]
print(f"[{side}] step C: {'PASS' if not bad else 'FAIL ' + ', '.join(bad)}; done", flush=True)
