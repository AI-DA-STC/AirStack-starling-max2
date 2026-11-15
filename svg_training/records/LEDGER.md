# Training ledger

Training ledger; separate from the flight ledger `docs/record/LEDGER.md`

| # | Date | Simulator | Run | What | Result | Record |
|---|---|---|---|---|---|---|
| T1 | 2026-11-14T16:55:40 | training simulator, tiers 1 and 2 | 2026-11-15_s0_laptop | S0 throughput sweep | FAIL | records/2026-11-15_s0_laptop_record.md |
| T2 | 2026-11-15T04:45:54+08:00 | training simulator (safety-filter port vs CMU cbf_filter.py, CPU) | 2026-11-15_s1_filter_parity | S1 safety-filter parity, 2000 scenes, 1000 sweeps | FAIL | records/2026-11-15_s1_filter_parity_record.md |
| T3 | 2026-11-15T13:50:14+08:00 | AirStack simulator, one drone | 2026-11-15_s1_fit_v0 | S1 response fit v0 (lag2, 2 held-out steps) | FAIL | records/2026-11-15_s1_fit_v0_record.md |
