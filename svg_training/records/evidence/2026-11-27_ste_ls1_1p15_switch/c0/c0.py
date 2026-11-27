"""Step C0 (LS1_1P15_SWITCH.md): T50's 30 fixed scripted cells at 1.15 m replayed on the CPU, game for game
(exploit.replay_ok), in two batches of 15 cells. Mark: every cell exact. usage: c0.py"""
import json, sys, time
from pathlib import Path
import numpy as np, torch
sys.path.insert(0, "source")
from svg_training.ste import exploit
from svg_training.ste.exploit import load_reference, load_game_cfg_file, play_cells, slice_cell, replay_ok

torch.set_num_threads(12)
ref = load_reference("configs/ste_l012b/screen_reference.npz")
cfg = load_game_cfg_file("configs/ste_l011/tag_1p15.toml")
cells = sorted((g, s) for (v, g, s) in ref.cells if v == "tag_1p15")
print(f"{len(cells)} cells; meta seed {ref.meta.get('seed')}; start sha {ref.start_sha256[:12]}", flush=True)
assert len(cells) == 30
out, ok_all = [], True
for b in range(2):
    part = cells[b * 15:(b + 1) * 15]
    t0 = time.time()
    pg = play_cells(cfg, "3v3", ref, part, 1000, "cpu", 110000, 2400)
    for k, (g, s) in enumerate(part):
        mine = slice_cell(pg, k, 1000)
        good, text = replay_ok(mine, ref.cell("tag_1p15", g, s), "cpu", {})
        ok_all &= good
        out.append({"guard": g, "strike": s, "exact": bool(good), "text": text})
        print(f"  {g} v {s}: {'EXACT' if good else 'DIFFERS'}: {text}", flush=True)
    print(f"batch {b}: {time.time() - t0:.0f} s", flush=True)
json.dump(out, open(Path(__file__).parent / "c0.json", "w"), indent=1)
print(f"C0: {'PASS' if ok_all else 'FAIL'} ({sum(o['exact'] for o in out)} of 30 cells exact)")
