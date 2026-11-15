Simulator: training simulator, tier 1 (safety-filter port vs CMU cbf_filter.py on T2's scenes; S2 game with the Starling layer for speed)

# 2026-11-16T01:25:30+08:00 2026-11-16_s2_filter_speed record

Result: **ABORTED**. Ledger row T7. Stopped by hand at 01:29:18 (Ctrl-C), after 4 minutes, before any speed number of a filter setting existed. No verdict. The run of record is [T8](2026-11-16_s2_filter_speed_2_record.md).

## Purpose

To measure how accurate and how fast each candidate setting of the safety filter is, and pick the fastest accurate one (S2 plan, Task 7). See the T8 record for the full description.

## Why it was stopped

While this run was in its speed phase, a reviewer found a bug in the Starling layer, the code being timed. At a wall, the commander copy kept the speed the wall had taken away from a drone, so the safety filter let a Guard drone and a Strike drone come to about 0.77 m apart, against a keep-out of 1.10 m. The lead asked for the fix before the speed run. The fix changes the step being timed, so the run was stopped. It was then restarted under a new name on the fixed code (T8).

## What had finished

- **Accuracy phase**, on the CPU, complete: all 15 candidates on T2's 2,000 scenes. The numbers are the same as in T8, which ran the same phase again. They are in `runs/2026-11-16_s2_filter_speed/accuracy.md`.
- **Speed phase**: only the baseline, the S2 game with the filter replaced by a pass-through: 808,631 game-steps/s. It was measured on the old code, so T8 measured it again.

## Commit

Repository HEAD `bcae60bf3982` at launch, with the Task 7b files uncommitted (`launch_commit.txt` in the run folder). Code fingerprint `791376efa903`.

## Config

`configs/s2.toml` `[filter_speed]` and `[filter_speed_gates]`, copied to `runs/2026-11-16_s2_filter_speed/gates.toml` before the run. Command in `run.sh` there.

## Machine

This laptop, RTX 5070 Ti Laptop GPU. `nvidia-smi` before launch (`preflight.txt`): only the remote-desktop daemon as a compute process.

## Gates

Not evaluated (ABORTED).
