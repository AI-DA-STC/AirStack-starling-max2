Evidence for the LS1 redesign's CPU pilots (owner R50, 27 Nov 2026): the scratch scripts that ran, their logs and JSON outputs; read with [LS1_REDESIGN_PILOT_RESULTS.md](../../../ste_learning/drafts/LS1_REDESIGN_PILOT_RESULTS.md) (results) and [LS1_REDESIGN.md](../../../ste_learning/drafts/LS1_REDESIGN.md) section 4 (the plan and its marks); not of record

Training simulator, tier 1, CPU only. Absolute paths were replaced with placeholders when the files were copied here
(`<svg_training>`, `<scratch>` for the pilot scratch folder, `~/`); run the scripts from `svg_training/` with those
put back (`run.sh` sets the environment: 6 threads, no GPU, `PYTHONPATH=source:<scratch>`). The fitted networks
(about 10 MB) are not here: they stay in `runs/2026-11-27_ste_ls1r_pilots_scratch/nets/` (not in git).

| Files | What |
|---|---|
| `harness.py` | replays a stand-in network in T94's own network batches (reads T94's layout and stored script games; writes nothing) |
| `s0a.*` | Stage 0a: the saved LS1.1 networks and the script oracle in T94's batches |
| `s0b.py`, `s0b_*.json`, `logs/s0b_*.log` | Stage 0b: the old networks with a slow-finish tail and the output mask, every cell |
| `blend.py`, `blend_rows.py`, `s0c*.{py,log,json}`, `logs/s0c_strike_converge.log`, `s0c_summary.json`, `flank_diag.py` | Stage 0c: blended-switch closed forms and their replays per width |
| `s0d.py`, `s0d.json`, `logs/s0d*.log` | Stage 0d: closed forms from the feature code against the labels; ONNX parity (`s0d_v3.log` is the final run) |
| `s0e.py`, `s0e_*.json`, `logs/s0e_*.log` | Stage 0e: all allowed row errors at once |
| `lsr.py` | features by rung (R1 to R4, RAW), the per-skill network, the fit, the row marks, the assembly |
| `s1fit.py`, `s1joint.py`, `s1/*.json`, `logs/{B,B2,A3,A3s2,A4,N3,N4,Cin,Clr,Chead,Cone}_*.log` | Stage 1 fits (per skill; joint C-head and C-one) with their row marks |
| `stage2.py`, `s2run.py`, `cells_screen.json`, `s2/*.json`, `logs/{S1,S2,c4}_*.log` | Stage 2: screen-first full replays, the trigger set, the C4 analogue |
| `onnx_arm.py`, `s2/onnx_*.json`, `logs/onnx_*.log` | the onnxruntime-flown arm on the screen cells |
| `summarize.py`, `summary.{md,json}`, `matches.{py,json}`, `rowmarks.py`, `forward_time.log` | the tables of the results note: fits, replays, the 4.3 match rule, row marks, forward time |
| `run.sh`, `dispatch.sh`, `queue.sh`, `after.sh`, `backup.sh`, `jobs.txt`, `dispatch.log*` | how the jobs were run: up to 4 at once (6 until the count was fixed, see the results note section 6) |

Inputs (not in git): `runs/2026-11-26_ste_ls11_distil_{guard,strike}` (rows, saved networks),
`runs/2026-11-26_ste_ls12_read_{guard,strike}` (T94's layout and stored games),
`runs/2026-11-25_ste_ls15_calibration_{guard,strike}` read only for the screen cells (the T90 arm's worst cells).
