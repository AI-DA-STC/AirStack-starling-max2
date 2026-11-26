Evidence for the LS1 fix-round diagnosis ([proposal](../../../ste_learning/drafts/LS1_FIX_ROUND_PROPOSAL.md), [record](../../2026-11-26_ste_ls1_distil_read_record.md)): CPU scratch work, not of record

| File | What |
|---|---|
| `pilot.py`, `pilot_one.py`, `common.py` | the CPU pilots: shared network (A, B 512x3, B6, C with added inputs) and one skill per network (F1 flank, F2 flank in each drone's own frame, S4 sacrifice, S5 converge) |
| `pilot_*.log` | the pilots' held-out RMSE by step |
| `strike1.py`–`strike3.py`, `guard1.py`, `side.py`, `saved_on_heldout.py`, `fwd_time.py` | the diagnosis scripts run on the LS1.1 networks and kept rows (`runs/2026-11-26_ste_ls11_distil_{guard,strike}`, not in git) |
| `out_*.log` | their outputs, re-run on the CPU (6 threads) on 26 Nov 2026 after review |
| `distil_gates_fix.toml` | the scratch gate file with the proposal's five changes (loads through `distil.load_distil_gates`); not the gate file of any run |
| `strike_strike_flank_g0_scripts.gif`, `strike_strike_flank_g0_net.gif` | one LS1.1 2-D clip pair (game 0, Strike flies flank): the scripts, then the LS1.1 network on the same start (`runs/2026-11-26_ste_ls11_distil_strike/videos/`) |
