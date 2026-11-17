Simulator: training simulator, tier 1 (the hangar game with the all-pairs safety filter and the EXPLORATORY fitted drone model). **ABORTED: no result.** Not a flight result.

# 2026-11-18 NUS port, Phase 4 rung 4 (W7): the all-pairs safety filter instead of the push (ABORTED, no score)

| Item | Value |
|---|---|
| What was running | `scripts/nus_phase4.py --row 4 --device cuda`, queued behind rows 3a and 3 (1,000 games x 24 pairs, one GPU, nothing else on it: `runs/nus_port/phase4/gpu_before_row_4.txt`), `gates.toml` written first (`gates = []`, reading rules) |
| Why it stopped | The first pair had not finished after more than 7 minutes, so the row would run for hours. The implementer stopped it by hand (SIGTERM, no checkpoint is involved) and read the plan's rule: a run estimated above 2 h is reported first, and the cheaper rows are run. The runner then got the plan's warm-up estimate (50 simulator ticks of the first pair, scaled to the game length) |
| Estimate (INFO, warm-up) | row 4: about 5.1 h on this GPU; row 6 (Isaac Lab physics drone, after `scripts/isaac_preflight.sh --approved-headless` exited 0): about 4.4 h. Rows 5a and 5 share row 4's code path (filter on, fitted drone) and were not timed separately; expect about the row 4 time each. The warm-up measures the first ticks, where the filter is slowest, so the estimates are upper figures; the first pair's 7 minutes without finishing is consistent with them |
| Likely cause | The partner's starts put drones of one team close together in every game (start miss 1,000 of 1,000 on every row), so the filter has work to do from the first tick and keeps its sweep budget; the S2 filter-speed record shows the same effect (about 25,000 game-steps/s over the first 100 steps against about 130,000 mid-game, and about 10,000 with every sweep). Each tick also runs the policy forward |
| Last good step | none for this row; rows 1 to 3 are complete (records of rungs 1 to 3) |
| Output kept | `runs/nus_port/phase4/_aborted_row_4_first_attempt/` (only `gates.toml`; git-ignored) |
| Date, machine, code | 2026-11-18, home RTX 5090 workstation; branch `nus-port-phase2` over `afe6b993`, working copy NOT committed (the lead commits); files in HANDOFF section 0 |

## What waits on the lead or the owner

Rungs 4, 5 (rows 5a, 5) and 6 are not run. Options, none taken by the implementer: (a) run them in the background with `--accept-long` (about 5 h each for rows 4, 5a and 5, about 4.4 h for row 6, one at a time, a free GPU each, preflight exit 0 for row 6); (b) run the core block only first (12 pairs, half the time); (c) change the filter's `filter_check_every` or sweep budget (a change to the Starling layer's settings: an owner decision, the S2 gates apply); (d) fewer than 1,000 games per pair (not allowed by STANDARDS section 7.3 for a result). The runner, tests, videos and record tooling for these rows are built and tested on marker values with a PyTorch rigid-body world (the marker chain test runs rows 1 to 6).

## Ledger

Row `W7` (ABORTED).
