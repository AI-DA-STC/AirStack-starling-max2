Simulator: training simulator, tier 1 (fast engine; Starling layer: commander copy, safety filter on every pair, fitted PX4 response, exploratory); study tag on (P1, PROPOSED). Observed in the training simulator; not a flight result.

# 2026-11-21_ste_l012_tag_1p2_strike record

## Gates

Verdict: **ABORTED**. Nothing below is a result: no side status or category is read from a run whose controls did not all pass or that did not finish (gate [controls]).

| Run | Variant / side | What ran | Why it ended |
|---|---|---|---|
| runs/2026-11-21_ste_l012_tag_1p2_strike | tag_1p2 / strike | controls batch played; 87 training updates, 547,356,672 game-steps; final batch played | controls PASS (exit 0, results.json complete); training stopped before its game-step budget (cap reserve: 602 s left < final reserve 620 s at update 87) |

## Run notes

- **Never suspend the machine during a GPU job** (no closed lid, no sleep): the cap clock and the GPU-hour ledger are wall clock less the owner's gpu_pause.sh pauses only (tooling task L07-SUSPEND). Say here whether the machine was suspended during the runs.
- **Asymmetries stated before the runs** (gate file header): one training seed per side; the learner decides every 0.6 s while the scripts decide every 0.05 s (finding L011-F1); one network per drone; about 1 GPU-h per run. A gain is evidence; no gain is weak evidence.
- **Decision-boundary restart** (LEAD CALL 21 Nov 2026): a game that ends inside a 0.6 s decision restarts at the next decision boundary; the ticks after its end are played, counted (stale-tick share) and never trained on (T41's hold let the new game play the old held action).
- **Strike recipe** (LEAD CALL 21 Nov 2026, pre-registered in [trainer] strike_fallback): the T41 recipe if its pilot probe against g* shows at least one reach; else the shaped Strike recipe (the game's distance shaping 1.0, training reward only), also when neither probe shows a reach (LEAD CALL 21 Nov 2026, QC N-1: 3-update probes no longer stop the Strike runs). The parked-Guard probes are information only. The recipe of each run is in the tables below.
- **Run 0, the learner positive control** (LEAD CALL 21 Nov 2026, QC N-1; gate [run0]): the Strike recipe trained against the parked Guard at the budget and cap of a run of record, read at pre-listed checkpoints (reach rate at least scripted strike_straight's on the same starts minus 0.05). Strike runs need run 0 = PASS; if it reads FAIL the Strike runs are not launched and the Strike side is INCONCLUSIVE (the trainer did not learn the easy Strike task at the run budget). Guard runs do not depend on it.
- **Hours** (LEAD CALL 21 Nov 2026, QC N-3): nothing kills a run at --gpu-h during its final phase; the GPU-hours below are the ledger's real hours.
- **Resume** (by design): networks, optimisers, scalers, counters and the torch random state are restored at the last update boundary, but the training games restart from the run seed's first starts (the game generator is not checkpointed), so a resumed run is not identical to an uninterrupted run. Each run's job launches say whether it was resumed.

## Run notes added by the lead

- **Why ABORTED** (QC N-2): training stopped at update 87 of 88 because the cap reserve ran short (602 s left, 620 s
  needed for the final batch); the run then played its final batch and ended with exit 0. A run that did not reach its
  game-step budget gets no side status, so the tag 1.2 m variant reads "incomplete: one side only" in
  [record T46](2026-11-21_ste_l012_best_response_record.md).
- **For information only (proves nothing):** the trained Strike drones mostly wait out the 120 s clock (786 of 1,000
  games ran to the clock); they reached the zone in 114 of 1,000 games against 355 for the best scripted Strike
  (guard_field v strike_straight, T44's starts). The training reach rate stayed flat at about 11 % from update 41.
- **Not re-run** (lead): about 1 GPU-h on top of L0.12's 6, and the category of tag 1.2 m could not change: its scripts
  already sit above the 0.2 band on both sides (T46, lead's notes).
- **GPU-hours** 0.659 (shared ledger); one launch, not suspended (2,322 s effective against a 2,372 s span; the gap was
  not looked into).
- **Clips** (2-D with the height panel, both games to the clock):
  [tag_1p2_trained_strike_ABORTED_game0_hold](../docs/media/ste_l012/tag_1p2_trained_strike_ABORTED_game0_hold.gif),
  [tag_1p2_trained_strike_ABORTED_game1_hold](../docs/media/ste_l012/tag_1p2_trained_strike_ABORTED_game1_hold.gif).

- **QC note (21 Nov 2026, after independent QC):** the effective-time gap above is a recording-stage difference, not a
  suspend: results.json's effective_s 2,321.8 s was written before the run's final write; progress.json ends at
  2,370.8 s, which matches the 2,372 s wall-clock span.

## Ledger row

Ledger row: | T47 | 2026-11-21T11:25:59+08:00 | training simulator, tier 1 (fast engine; Starling layer: commander copy, safety filter on every pair, fitted PX4 response, exploratory); study tag on (P1, PROPOSED); NVIDIA GeForce RTX 5070 Ti Laptop GPU | 2026-11-21_ste_l012_tag_1p2_strike | STE L0.12 Best-response test: tag_1p2 / strike: controls PASS (exit 0, results.json complete); training stopped before its game-step budget (cap reserve: 602 s left < final reserve 620 s at update 87); 0.659 GPU-h | ABORTED | records/2026-11-21_ste_l012_tag_1p2_strike_record.md |

