Simulator: training simulator, tier 1 (fast engine; Starling layer: commander copy, safety filter on every pair, fitted PX4 response, exploratory); study tag on (P1, PROPOSED). Observed in the training simulator; not a flight result.

# 2026-11-21_ste_l012b_tag_1p15_strike record

## Gates

Verdict: **ABORTED**. Nothing below is a result: no side status or category is read from a run whose controls did not all pass or that did not finish (gate [controls]).

| Run | Variant / side | What ran | Why it ended |
|---|---|---|---|
| runs/2026-11-21_ste_l012b_tag_1p15_strike | tag_1p15 / strike | controls batch played; 86 training updates, 541,065,216 game-steps; final batch played | controls PASS (exit 0, results.json complete); training stopped before its game-step budget (cap reserve: 649 s left < final reserve 664 s at update 86) |

## Run notes

- **Never suspend the machine during a GPU job** (no closed lid, no sleep): the cap clock and the GPU-hour ledger are wall clock less the owner's gpu_pause.sh pauses only (tooling task L07-SUSPEND). Say here whether the machine was suspended during the runs.
- **Asymmetries stated before the runs** (gate file header): one training seed per side; the learner decides every 0.6 s while the scripts decide every 0.05 s (finding L011-F1); one network per drone; about 1 GPU-h per run. A gain is evidence; no gain is weak evidence.
- **Decision-boundary restart** (LEAD CALL 21 Nov 2026): a game that ends inside a 0.6 s decision restarts at the next decision boundary; the ticks after its end are played, counted (stale-tick share) and never trained on (T41's hold let the new game play the old held action).
- **Strike recipe** (LEAD CALL 21 Nov 2026, pre-registered in [trainer] strike_fallback): the T41 recipe if its pilot probe against g* shows at least one reach; else the shaped Strike recipe (the game's distance shaping 1.0, training reward only), also when neither probe shows a reach (LEAD CALL 21 Nov 2026, QC N-1: 3-update probes no longer stop the Strike runs). The parked-Guard probes are information only. The recipe of each run is in the tables below.
- **Run 0, the learner positive control** (LEAD CALL 21 Nov 2026, QC N-1; gate [run0]): the Strike recipe trained against the parked Guard at the budget and cap of a run of record, read at pre-listed checkpoints (reach rate at least scripted strike_straight's on the same starts minus 0.05). Strike runs need run 0 = PASS; if it reads FAIL the Strike runs are not launched and the Strike side is INCONCLUSIVE (the trainer did not learn the easy Strike task at the run budget). Guard runs do not depend on it.
- **Hours** (LEAD CALL 21 Nov 2026, QC N-3): nothing kills a run at --gpu-h during its final phase; the GPU-hours below are the ledger's real hours.
- **Resume** (by design): networks, optimisers, scalers, counters and the torch random state are restored at the last update boundary, but the training games restart from the run seed's first starts (the game generator is not checkpointed), so a resumed run is not identical to an uninterrupted run. Each run's job launches say whether it was resumed.

## Run notes added by the lead

- **Why ABORTED** (QC N-2): training stopped at update 86 of 88 because the cap reserve ran short (649 s left, 664 s
  needed for the final batch, at `--cap-h 0.85`); the run then played its final batch and ended with exit 0. A run that
  did not reach its game-step budget gets no side status, so tag 1.15 m reads "incomplete: one side only"
  ([record T51](2026-11-21_ste_l012b_best_response_record.md)). Why the cap was short: T51, lead's note (c).
- **For information only (proves nothing):** the trained Strike drones mostly wait out the 120 s clock (771 of 1,000
  games ran to the clock; 1.05 Guards left on average in holds); 103 reaches of 1,000 against 355 for the best scripted
  Strike (guard_field v strike_straight). The training reach rate stayed at about 10–14 % from update 41.
- **Not re-run** (lead's recommendation; the owner asked): it could not change the category, since the scripts alone
  already sit above the 0.2 band on both sides.
- **GPU-hours** 0.770; one launch, not suspended (2,770 s effective against a 2,772 s span).
- **Clips** (2-D with the height panel, both games to the clock):
  [game 0](../docs/media/ste_l012b/tag_1p15_trained_strike_ABORTED_game0_hold.gif),
  [game 1](../docs/media/ste_l012b/tag_1p15_trained_strike_ABORTED_game1_hold.gif).

## Ledger row

Ledger row: | T52 | 2026-11-21T15:58:59+08:00 | training simulator, tier 1 (fast engine; Starling layer: commander copy, safety filter on every pair, fitted PX4 response, exploratory); study tag on (P1, PROPOSED); NVIDIA GeForce RTX 5070 Ti Laptop GPU | 2026-11-21_ste_l012b_tag_1p15_strike | STE L0.12b Best-response test: tag_1p15 / strike: controls PASS (exit 0, results.json complete); training stopped before its game-step budget (cap reserve: 649 s left < final reserve 664 s at update 86); 0.770 GPU-h | ABORTED | records/2026-11-21_ste_l012b_tag_1p15_strike_record.md |

