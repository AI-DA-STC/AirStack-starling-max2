Simulator: training simulator, tier 1 (the hangar game of Phase 4 row 5: the all-pairs safety filter, the commander copy, delay and lag of the EXPLORATORY fitted drone model, drones free in height with the start-height jitter); home RTX 5090, alone on the GPU. Not a flight result.

# 2026-11-19 NUS port, Phase 5 pilot 5.P1b "Guard learner, fixed", run 4 (T41): promotion signal MET (pilot, not gated, INFO record)

**Pilot, not gated, INFO record.** Our own Guard learner (the skrl IPPO stand-in) trained on tier 1 against NUS's
converted Strike policy S20 holds the zone in **829 of 1,000** games of the Phase 4 paired starts (hold rate 0.829,
Wilson 95 % [0.804, 0.851]). The promotion signal fixed in the plan (Wilson lower bound above 0.460, the parked Guard's
upper bound on row 5) is **met**. The parked Guard holds 429 of 1,000 on the same starts (T23); standing still from the
starts held 27 of 64 (P1 diagnosis). Run 1 of P1 held 0 of 1,000 (T26).

| Item | Value |
|---|---|
| Purpose | Can a simple learner find a defence against S20 on our drone model (plan D-P5-7)? P1 + both fixes from P1's diagnosis: a zero-mean start (the untrained Guards stand still) and one decision per 12 ticks (the deploy file's hold), γ = 0.99 per decision, no shaping reward |
| Settings | `configs/nus_phase5.toml [pilot_p1b]` (cap 3.0 GPU-h, table sha256 `bc0ea919…`); effective cap min(3.0, 6.0 − 3.828) = 2.172 h; 32,768 training games; seed 101; `--no-eval-at-start` |
| Code | branch `nus-phase5`, `39a4b4e6` (P1b code `ecad1389`, table `12a3e411`), clean tree |
| Command | `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True scripts/train_standin.py --game nus_hangar --settings pilot_p1b --seed 101 --no-eval-at-start --name 2026-11-19_nus_phase5_pilot_p1b_run4 --runs-dir runs/nus_port/phase5/pilots --device cuda`, launched by `p1b_run4_orchestrate.sh` (starvation check: at least 10 updates by launch + 45 min, set for a solo GPU) |
| Machine | home RTX 5090, **alone** (after the owner's reboot; preflight exit 0, no other GPU job) |
| Time | 04:59:25 to 07:07:54 (+08:00), 19 Nov 2026; stopped by the wall-clock cap (2.142 GPU-h); pilots' ledger 5.970 of 6.0 GPU-h |

## Results

| Evaluation | Games (Phase 4 paired starts) | Guard holds | Hold rate | Wilson 95 % |
|---|---|---|---|---|
| half-way (decision 768, 302 M game-steps) | 256 | 194 | 0.758 | [0.702, 0.806] |
| **final** (decision 1,472, 579 M game-steps, 46 updates) | **1,000** | **829** | **0.829** | **[0.804, 0.851]** |

| Reference on the same starts | Holds of 1,000 | Record |
|---|---|---|
| parked Guard v S20 (row 5) | 429 | T23 |
| NUS's Guard G19 v S20 (row 5) | 17 | T23 |
| P1 (first try, per-tick decisions, shaping) | 0 | T26 |

Final evaluation, other measures: closest Guard–Strike approach 0.55 m in the horizontal plane (0.87 m in 3-D; median
1.50 m); safety-filter active in 33 % of ticks; "rule breach" share 0.005; mean game end step 2,030 of 2,400. Training speed
about 93,600 game-steps/s (solo).

## Videos (recorded in the run, from the evaluation games)

`docs/media/nus/pilots/`: `p1b_run4_final_t1472_best_hold_slot0.mp4` (a hold, best checkpoint),
`p1b_run4_final_t1472_best_strike_win_slot6.mp4` (an S20 win, best checkpoint), `p1b_run4_mid_t768_strike_win_slot2.mp4`
(half-way). What the Guards do (frames checked by the lead): they spread out inside the zone in a triangle covering it;
S20's drones end pressed against the arena walls, held off by the safety filter, which acts as a wall around each Guard.

## Limits

- **One seed, one opponent.** Trained and scored only against S20; nothing says how it does against other Strike
  behaviours (pilot P2, not run) or in self-play (P3, not built). A pilot: not gated, not of record.
- Tier 1 uses the EXPLORATORY fitted drone model; Isaac Lab (tier 2) was not run.
- The mechanism ("the filter as a wall") is read from the videos and the filter share, not tested by a control.
- Observed in the training simulator; nothing here authorises a flight.

## Ledger

Row `T41` in `records/LEDGER.md`. Run 3 (stopped by the lead at 01:19 for the owner's reboot, before any update) is `T40`.
