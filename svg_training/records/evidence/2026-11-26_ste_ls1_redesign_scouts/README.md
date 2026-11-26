Evidence for the LS1 redesign note ([LS1_REDESIGN.md](../../../ste_learning/drafts/LS1_REDESIGN.md)): the scouts' CPU scratch scripts and outputs, 26 Nov 2026; not of record

| Files | What |
|---|---|
| `a_calib.*`, `a_cells.*` | the T90 calibration and T94 cells re-read: changed games against error kind and size; cells made only of passing skills |
| `b_lrtail.py`, `b_guard.log`, `b_strike.log`, `f_tailbias.*` | the low-learning-rate tail on the saved LS1.1 networks (the steady offsets) |
| `c_predict.*`, `d_rank.*`, `e_decomp.*`, `g_ownrows.*` | how well row-level error predicts changed games; error split into bias, turn, scale and the rest; error on each skill's own rows |
| `geo.py`, `run_closed.py`, `out_closed.log` | closed forms of the 11 scripts against the stored labels |
| `run_frames.py`, `out_frames.log`, `run_jitter.py`, `out_jitter.log`, `run_ring.py`, `out_ring.log` | frame features, label jumps at 1 mm and 1 cm, parked_ring's geometry |
| `fwd_variants.py`, `onnx_check.py`, `onnx_frame.py` | forward-time variants and ONNX export checks (the contract scout saved no output logs; its timings are in the note only) |

Inputs: `runs/2026-11-26_ste_ls11_distil_{guard,strike}`, `runs/2026-11-26_ste_ls12_read_{guard,strike}`, `runs/2026-11-25_ste_ls15_calibration_{guard,strike}` (not in git).

Absolute paths inside the scripts were replaced with placeholders (`<svg_training>`, `<scratch>`, `~/`) when they were saved here; run them from `svg_training/` with those paths put back.
