---
name: train-debug
description: Use when something in the training pipeline is wrong - NaN values, a flat reward, a slow run, a policy that works in tier 1 but not tier 2, a win rate that cycles, or Isaac that will not start. Evidence first, cause before fix.
---

# Debug

Do these in order. Never change a gate to make a run pass; record the failure.

## 1. Capture the evidence
Exact error text or the numbers that look wrong, the run folder, the commit, the seed, the tier, the
machine. Keep the logs. Check the GPU:
```bash
nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv
docker ps --format '{{.Names}}'
```

## 2. Find the symptom, run its first check
| Symptom | First check |
|---|---|
| NaN or exploding values | time step; action scaling to `[-1, 1]`; quaternion normalisation; each reward term alone; divide-by-zero in the safety filter port |
| Reward flat | opponent too strong or too weak (play it against a scripted one); start distribution; safety filter blocking every move: read the intervention rate, and check that the filter runs per team only (a filter between the teams makes a contact tag impossible, STANDARDS §4) |
| Throughput dropped | a `.cpu()`, NumPy call or Python loop in the step; rendering on; GPU shared with the AirStack simulator; GPU memory full |
| Wins in tier 1, not in tier 2 | model fit, delay, limits: refit the drone model (stage 1); compare step responses between tiers |
| Win rate cycles between versions | pool mix; scripted share (never removed); the cross-play table |
| Isaac will not start, or the remote desktop drops | run headless; the WiFi firmware crash on this laptop happens when a window opens over remote desktop; use Ethernet or sit at the machine |
| Results differ between seeds | seeds actually fixed and recorded; fewer than 3 seeds; games per condition below 1,000; an interval wider than the difference |

## 3. One hypothesis at a time
State it in one sentence. Find the log line, number or code line that proves or disproves it. Discard
it and form the next. Do not stack speculative edits.

## 4. Smallest fix at the real cause
Use `train-change` for the fix: test first, then edit. Never loosen a gate, shrink the evaluation
suite, drop scripted opponents from the pool, or switch the safety filter off to get a number.

## 5. Verify the way the failure was seen
Re-run the same check that showed the symptom, with the same seed. A NaN is fixed when the run passes
the step where it appeared; a throughput drop is fixed when steps per second returns, reported with
games, drones per game, tier and GPU.

## 6. Record
A failed run keeps its FAIL or ABORTED record and its ledger row. Add what you learned to
`docs/claude/HANDOFF.md` §4 if it changes what the next session should know.
