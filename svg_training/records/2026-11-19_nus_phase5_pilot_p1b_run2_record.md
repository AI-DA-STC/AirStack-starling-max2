Simulator: training simulator, tier 1 (the hangar game of Phase 4 row 5: the all-pairs safety filter, the commander copy, delay and lag of the EXPLORATORY fitted drone model, drones free in height with the start-height jitter). Not a flight result.

# 2026-11-19 NUS port, Phase 5 pilot P1b, run 2 (T39, provisional): ABORTED by the starvation guard (pilot, not gated, INFO record)

**Pilot, not gated, INFO record. ABORTED by the lead's starvation guard** (rule set by the lead on 19 Nov 2026 ~00:10: if
fewer than 15 PPO updates have completed 45 min after launch, stop cleanly). At launch + 45 min the run had logged decision
175, about 5 completed updates, so it was stopped (SIGINT, 00:59:10). No evaluation ran; there is no result for the
promotion signal. Run 1 (`records/2026-11-18_nus_phase5_pilot_p1b_record.md`, W15) was stopped for the same reason.

| Item | Value |
|---|---|
| Purpose | P1b rerun on a freer GPU (the lead, after C0's three JAX jobs exited): P1 + zero-mean start + one decision per 12 ticks (the deploy file's hold), γ = 0.99 per decision, shaping weight 0; S20, 32,768 games, seed 101, `--no-eval-at-start` |
| Settings | `configs/nus_phase5.toml [pilot_p1b]` as committed in `12a3e411` (cap 3.0 GPU-h, lead); effective cap min(3.0, 6.0 − 3.073) = 2.927 h (10,537 s); one evaluation estimated at 2,457 s at the start |
| Code | branch `nus-phase5`, `af3b0346` (P1b code `ecad1389`, table `12a3e411`; the later commit adds records only), clean tree |
| Command | `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True scripts/train_standin.py --game nus_hangar --settings pilot_p1b --seed 101 --no-eval-at-start --name 2026-11-19_nus_phase5_pilot_p1b_run2 --runs-dir runs/nus_port/phase5/pilots --device cuda` (own process session) |
| Machine | home RTX 5090, **shared**: `scripts/isaac_preflight.sh --approved-headless --allow-siblings` exit 0 (`preflight_p1b_run2.txt`); at launch the three stage 5.1 trainers (`nus_selfplay_train.py` seeds 1001, 2001, 3001; 1,948 MiB each) kept the GPU 94 % busy; an Isaac clip job (about 4.7 GB) was on the GPU at the stop. Timings are not comparable to solo runs |
| Guards | `runs/nus_port/phase5/pilots/p1b_run2_guard.sh` (5090 only): the lead's starvation check at launch + 45 min (completed updates = latest logged decision // 32 decisions per update), and a stop at cap + 30 min (the lead's allowance for the final evaluation; not reached) |
| Time | 00:14:02 to 00:59:10 (+08:00), 19 Nov 2026 |

## What was measured (training only)

| Quantity | Value |
|---|---|
| Decisions | 175 logged (2,100 ticks per game), about 5 completed updates (15 needed) |
| Speed | about 1.2 s per simulator tick including the updates (P1 solo: 0.37 s per tick; run 1 on a busier GPU: about 2.4 s); PPO update 5.4–6.8 s |
| Training game length (decisions, mean) | 13.7, 26.0, 35.8, 46.6, 57.4, 69.2, 83.4 at decisions 25 … 175 (identical to run 1 up to decision 125: same seed and code) |
| Reward (sum over the 3 Guards, per decision) | max 0.0 (no hold yet: a hold needs 200 decisions, 2,400 ticks), mean −0.053 → −0.023 |
| Value loss (Guard 0) | 4.22 → 1.95 |
| Policy standard deviation | 0.201 → 0.199 |

No evaluation, so no `agent.pt`, `curve.json` or videos (they are written when an evaluation finishes). The pilot's crash
path wrote the GPU-hours line (0.752 h, "CRASHED: KeyboardInterrupt"; kept). Pilots' ledger: **3.825 of 6.0 GPU-h**.

## Reading

Even with C0 gone, the three stage 5.1 trainers on the same GPU held P1b to about 1.2 s per tick, about 3 times slower than
solo, so the decision-hold schedule (384 ticks per update) gives about 7 updates an hour. At that rate P1b's 2.9 h cap would
buy about 15–20 updates in all, and the first training games that can be held (200 decisions) would only just be reached:
P1b cannot say anything useful unless the GPU is near-solo or the filter is faster (the CUDA-graph filter path).

## Output

`runs/nus_port/phase5/pilots/2026-11-19_nus_phase5_pilot_p1b_run2/` (interface.toml, TensorBoard files), the log
`…_p1b_run2.log`, `preflight_p1b_run2.txt`, `p1b_run2_guard.sh`, `p1b_report.md` (5090 only, git-ignored). Ledger row T39
(provisional: the final number is set when the branch merges).
