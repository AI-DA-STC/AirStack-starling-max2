Simulator: NUS's own 2-D game (JAX, CPU), hangar geometry and NUS's default geometry. Not a flight result.

# 2026-11-17 NUS port, Run 0: scripted balance check of the hangar geometry (INFO, after the fact)

**INFO record, written 18 November 2026 from the outputs listed below; no ledger number at the time of the run.**

| Item | Value |
|---|---|
| Purpose | Before any training: check that the hangar geometry (spawn distance 8 units, Guard boundary 8 units, zone 4 units) is neither too easy nor too hard for scripted players, with limits set before the run |
| Limits set before the run | too easy if a parked Guard holds at least 0.90 (Strike win ≤ 0.10); too hard if NUS's scripted APF Strike controller beats the mirror Guards on the zone rim more than 0.30 of the time, or reaches the zone before step 15 in the median game |
| Date, machine | 2026-11-17, 22:32 (+08:00); the lab's RTX 5090 workstation, CPU |
| Code | a probe script (`run0.py`) in the lab's private port folder, outside every git repository: NUS's environment and NUS's scripted players called through NUS's code; no game loop of ours |
| Games, seed | 1,000 games per cell, 200 steps each; seed 12345; runtime 4.5 s |
| Strike team | NUS's scripted APF Strike controller in every cell |
| Outputs | `results.md`, `results.json` beside the script (`results.json` sha256 prefix `2288f9faad3c88ff`); not in git |

## Results (observed in the training simulator)

| Geometry | Guard team | Strike win [Wilson 95 %] | Median reach step | Reach before step 15 |
|---|---|---|---|---|
| hangar | mirror Guards on the zone rim | 0.067 [0.053, 0.084] | 24 | 0.000 |
| hangar | mirror Guards inside the zone | 0.000 [0.000, 0.004] | — | 0.000 |
| hangar | NUS's APF Guard controller | 1.000 [0.996, 1.000] | 7 | 0.728 |
| hangar | one Guard parked at the centre | 1.000 [0.996, 1.000] | 6 | 1.000 |
| hangar | static Guards | 1.000 [0.996, 1.000] | 6 | 1.000 |
| NUS default | mirror Guards on the rim | 0.000 [0.000, 0.004] | — | 0.000 |
| NUS default | mirror Guards inside | 0.000 [0.000, 0.004] | — | 0.000 |
| NUS default | APF Guard, parked, static | 1.000 [0.996, 1.000] each | 22 | 0.000 |

## Verdict

INFO. Neither limit fired: the hangar geometry passed Run 0.

## Limits

- NUS has one scripted Strike behaviour (APF), so only the Guard side was varied.
- One seed. No videos (scripted players only; nothing trained).

## Ledger

Row `T36` in `records/LEDGER.md` (INFO, after the fact).
