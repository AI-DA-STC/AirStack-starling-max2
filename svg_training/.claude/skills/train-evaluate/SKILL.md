---
name: train-evaluate
description: Use when scoring a checkpoint against its gates with the fixed evaluation suite. Covers loading the gates, game counts, intervals, the tier 2 cross-check and the gatekeeper read.
---

# Score a checkpoint

Do these in order. The scoring tool is `scripts/score.py` (S2). A strategy plugs in as `package.module:Class`; a
converted NUS policy is `svg_training.nus.strategy:NusPolicy` (docs/PLUG_IN_YOUR_CODE.md), scored up the transfer ladder with
`scripts/nus_phase4.py --row <id>` (INFO rows, no gates) and against its gates with `scripts/nus_phase4_w3.py`.

## 1. Load the gates
Open the run's `gates.toml`. Check its date is before the run's first result. If it is not, or it was
edited afterwards, stop: the gates are void and a new run is needed (STANDARDS §7 rule 1).

## 2. Check the machine
```bash
nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv
docker ps --format '{{.Names}}'
```
GPU free, no AirStack simulator, headless.

## 3. Run the fixed suite (STANDARDS §7 rule 4)
| Group | Measure |
|---|---|
| Scripted opponents | hold rate against each scripted Strike behaviour and Guard assignment |
| Starts | hold rate from held-out start regions |
| Team sizes | every trained size, plus one outside the range |
| Drop-out | hold rate when one drone leaves mid-game |
| Earlier versions | win rate against every saved version (cross-play table) |
| Safety | closest approach, filter intervention rate and size, fence breaches (gate: 0) |
| Smoothness | change in command between steps |

- At least 1,000 games per condition.
- The safety filter is on, the same as in flight.
- Use the one metrics module that also drew the training curves: the numbers gated are the numbers plotted.

## 4. Report rates with intervals
Each rate with its 95 % interval, the number of games, and the seeds. A method claim needs at least
3 seeds. Do not round a result across a gate.

## 5. PASS or FAIL per gate
Write each gate, its value, the measured number with interval, and PASS or FAIL. A FAIL stays a FAIL.
Never change a gate to make a checkpoint pass.

## 6. Cross-check on tier 2 when the stage requires it
Run the same checkpoint on the tier 2 rigid-body Starling. Report the gap in hold rate between tiers
and the step-response error, against the limits set beforehand. A gap above its limit sends work back
to stage 1 (refit the drone model).

## 7. Have `train-gatekeeper` read the record
Give it the record, `gates.toml` and the ledger row, not your conclusion. Fix every FAIL it returns
in the record, not in the gates.

## 8. Wording
"Observed in the training simulator", never "validated". Name the simulator and tier in every result.
