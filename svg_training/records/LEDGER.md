# Training ledger

Training ledger; separate from the flight ledger `docs/record/LEDGER.md`

| # | Date | Simulator | Run | What | Result | Record |
|---|---|---|---|---|---|---|
| T1 | 2026-11-14T16:55:40 | training simulator, tiers 1 and 2 | 2026-11-15_s0_laptop | S0 throughput sweep | FAIL | records/2026-11-15_s0_laptop_record.md |
| T2 | 2026-11-15T04:45:54+08:00 | training simulator (safety-filter port vs CMU cbf_filter.py, CPU) | 2026-11-15_s1_filter_parity | S1 safety-filter parity, 2000 scenes, 1000 sweeps | FAIL | records/2026-11-15_s1_filter_parity_record.md |
| T3 | 2026-11-15T13:50:14+08:00 | AirStack simulator, one drone | 2026-11-15_s1_fit_v0 | S1 response fit v0 (lag2, 2 held-out steps) | FAIL | records/2026-11-15_s1_fit_v0_record.md |
| T4 | 2026-11-15T15:18:31+08:00 | training simulator, tier 1 (real-drone response model, exploratory; safety filter per team) | 2026-11-15_s1_tier1_fitted_filter | S1 tier 1 throughput with the fitted response, filter off / 1000 / 200 sweeps, 5v3 open and full, 1024–16384 games | INFO (no gates) | records/2026-11-15_s1_tier1_fitted_filter_record.md |
