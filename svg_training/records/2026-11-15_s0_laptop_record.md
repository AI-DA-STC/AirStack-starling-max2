Simulator: training simulator, tiers 1 and 2 (stand-in drone models, no safety filter)

# 2026-11-14T16:55:40 2026-11-15_s0_laptop record

## Purpose

Measure how fast the training simulator runs, in tier 1 (batched game model) and tier 2 (Isaac Lab physics), over the cases and numbers of games in the config. Overall result: **FAIL**.

## Commit

Parent repository HEAD (does not contain this folder while it is untracked): `unknown`

## Code version

code_sha (first 12 hex of a sha256 over the files under source/, scripts/ and configs/): `13bebe8bb138`

## Config

`configs/s0_benchmark.toml`, sha256 `2d3114864a8f335ce8456e40af9c50c63700d59d821d53b9b0f3e7abac2accf0`
Timing: 50 warm-up steps and at least 2 s; timed window at least 200 steps and at least 2.0 s; 2 repeats.

## Model parameter set

placeholder

## Seeds

0 for every case and repeat, both tiers (Tier1BenchCfg.seed default; torch.manual_seed(0) in tier 2)

## Machine

- Machine: laptop
- GPU: NVIDIA GeForce RTX 5070 Ti Laptop GPU

## Throughput

Mean of the repeats. Environment steps per second = games x policy steps per second.

### Tier 1

| Case | Games | Drones per game | Environment steps per second | Drone-steps per second | Peak memory (MB) | Resets per step (%) | Status |
|---|---|---|---|---|---|---|---|
| t1_1v1_open | 256 | 2 | 543,593 | 1,087,186 | 6 | 0.1 | ok (2 of 2) |
| t1_1v1_open | 1,024 | 2 | 2,134,176 | 4,268,353 | 7 | 0.1 | ok (2 of 2) |
| t1_1v1_open | 4,096 | 2 | 8,668,397 | 17,336,795 | 10 | 0.1 | ok (2 of 2) |
| t1_1v1_open | 16,384 | 2 | 34,770,313 | 69,540,625 | 22 | 0.1 | ok (2 of 2) |
| t1_1v1_open | 65,536 | 2 | 96,195,329 | 192,390,657 | 70 | 0.1 | ok (2 of 2) |
| t1_2v1_open | 256 | 3 | 540,521 | 1,621,564 | 6 | 0.1 | ok (2 of 2) |
| t1_2v1_open | 1,024 | 3 | 2,144,612 | 6,433,837 | 8 | 0.1 | ok (2 of 2) |
| t1_2v1_open | 4,096 | 3 | 8,591,485 | 25,774,456 | 13 | 0.1 | ok (2 of 2) |
| t1_2v1_open | 16,384 | 3 | 34,112,563 | 102,337,689 | 36 | 0.1 | ok (2 of 2) |
| t1_2v1_open | 65,536 | 3 | 57,976,811 | 173,930,433 | 124 | 0.1 | ok (2 of 2) |
| t1_5v3_open | 256 | 8 | 537,544 | 4,300,350 | 8 | 0.1 | ok (2 of 2) |
| t1_5v3_open | 1,024 | 8 | 2,153,729 | 17,229,832 | 16 | 0.1 | ok (2 of 2) |
| t1_5v3_open | 4,096 | 8 | 8,352,312 | 66,818,495 | 45 | 0.1 | ok (2 of 2) |
| t1_5v3_open | 16,384 | 8 | 12,033,441 | 96,267,529 | 165 | 0.1 | ok (2 of 2) |
| t1_5v3_open | 65,536 | 8 | 12,287,243 | 98,297,944 | 644 | 0.1 | ok (2 of 2) |
| t1_5v3_prim10 | 256 | 8 | 351,874 | 2,814,994 | 7 | 0.1 | ok (2 of 2) |
| t1_5v3_prim10 | 1,024 | 8 | 1,395,786 | 11,166,289 | 17 | 0.1 | ok (2 of 2) |
| t1_5v3_prim10 | 4,096 | 8 | 3,525,016 | 28,200,126 | 57 | 0.1 | ok (2 of 2) |
| t1_5v3_prim10 | 16,384 | 8 | 3,200,211 | 25,601,685 | 221 | 0.1 | ok (2 of 2) |
| t1_5v3_prim10 | 65,536 | 8 | 3,040,205 | 24,321,640 | 880 | 0.1 | ok (2 of 2) |
| t1_5v3_prim50 | 256 | 8 | 351,640 | 2,813,118 | 18 | 0.1 | ok (2 of 2) |
| t1_5v3_prim50 | 1,024 | 8 | 919,627 | 7,357,013 | 62 | 0.1 | ok (2 of 2) |
| t1_5v3_prim50 | 4,096 | 8 | 781,383 | 6,251,066 | 240 | 0.1 | ok (2 of 2) |
| t1_5v3_prim50 | 16,384 | 8 | 756,864 | 6,054,908 | 957 | 0.1 | ok (2 of 2) |
| t1_5v3_prim50 | 65,536 | 8 | 746,605 | 5,972,841 | 3,820 | 0.2 | ok (2 of 2) |
| t1_5v3_prim10_rays32 | 256 | 8 | 49,525 | 396,199 | 16 | 0.1 | ok (2 of 2) |
| t1_5v3_prim10_rays32 | 1,024 | 8 | 65,367 | 522,937 | 64 | 0.1 | ok (2 of 2) |
| t1_5v3_prim10_rays32 | 4,096 | 8 | 45,102 | 360,818 | 246 | 0.1 | ok (2 of 2) |
| t1_5v3_prim10_rays32 | 16,384 | 8 | 41,109 | 328,870 | 987 | 0.1 | ok (2 of 2) |
| t1_5v3_prim10_rays32 | 65,536 | 8 | 40,565 | 324,516 | 3,936 | 0.1 | ok (2 of 2) |
| t1_5v3_prim10_rays64 | 256 | 8 | 29,423 | 235,381 | 31 | 0.1 | ok (2 of 2) |
| t1_5v3_prim10_rays64 | 1,024 | 8 | 25,727 | 205,813 | 122 | 0.1 | ok (2 of 2) |
| t1_5v3_prim10_rays64 | 4,096 | 8 | 21,016 | 168,131 | 488 | 0.1 | ok (2 of 2) |
| t1_5v3_prim10_rays64 | 16,384 | 8 | 20,467 | 163,736 | 1,950 | 0.1 | ok (2 of 2) |
| t1_5v3_prim10_rays64 | 65,536 | 8 | - | - | - | - | oom |
| t1_5v3_prim10_los | 256 | 8 | 49,301 | 394,405 | 4 | 0.1 | ok (2 of 2) |
| t1_5v3_prim10_los | 1,024 | 8 | 198,656 | 1,589,245 | 14 | 0.1 | ok (2 of 2) |
| t1_5v3_prim10_los | 4,096 | 8 | 499,497 | 3,995,977 | 55 | 0.1 | ok (2 of 2) |
| t1_5v3_prim10_los | 16,384 | 8 | 438,348 | 3,506,786 | 220 | 0.1 | ok (2 of 2) |
| t1_5v3_prim10_los | 65,536 | 8 | 342,909 | 2,743,270 | 880 | 0.1 | ok (2 of 2) |
| t1_5v3_prim50_full | 256 | 8 | 11,658 | 93,264 | 61 | 0.2 | ok (2 of 2) |
| t1_5v3_prim50_full | 1,024 | 8 | 8,621 | 68,966 | 244 | 0.2 | ok (2 of 2) |
| t1_5v3_prim50_full | 4,096 | 8 | 8,247 | 65,979 | 971 | 0.2 | ok (2 of 2) |
| t1_5v3_prim50_full | 16,384 | 8 | 8,059 | 64,472 | 3,881 | 0.2 | ok (2 of 2) |
| t1_5v3_prim50_full | 65,536 | 8 | - | - | - | - | oom |
| t1_5v3_field | 256 | 8 | 452,307 | 3,618,456 | 99 | 0.1 | ok (2 of 2) |
| t1_5v3_field | 1,024 | 8 | 1,832,177 | 14,657,415 | 106 | 0.1 | ok (2 of 2) |
| t1_5v3_field | 4,096 | 8 | 6,768,391 | 54,147,125 | 136 | 0.1 | ok (2 of 2) |
| t1_5v3_field | 16,384 | 8 | 9,114,613 | 72,916,906 | 256 | 0.1 | ok (2 of 2) |
| t1_5v3_field | 65,536 | 8 | 9,038,361 | 72,306,889 | 737 | 0.1 | ok (2 of 2) |
| t1_5v3_field_rays32 | 256 | 8 | 89,968 | 719,747 | 99 | 0.1 | ok (2 of 2) |
| t1_5v3_field_rays32 | 1,024 | 8 | 275,817 | 2,206,533 | 117 | 0.1 | ok (2 of 2) |
| t1_5v3_field_rays32 | 4,096 | 8 | 327,002 | 2,616,016 | 193 | 0.1 | ok (2 of 2) |
| t1_5v3_field_rays32 | 16,384 | 8 | 237,594 | 1,900,756 | 499 | 0.1 | ok (2 of 2) |
| t1_5v3_field_rays32 | 65,536 | 8 | 221,827 | 1,774,614 | 1,708 | 0.1 | ok (2 of 2) |
| t1_5v3_full | 256 | 8 | 21,961 | 175,691 | 107 | 0.1 | ok (2 of 2) |
| t1_5v3_full | 1,024 | 8 | 47,776 | 382,206 | 154 | 0.1 | ok (2 of 2) |
| t1_5v3_full | 4,096 | 8 | 38,567 | 308,533 | 338 | 0.2 | ok (2 of 2) |
| t1_5v3_full | 16,384 | 8 | 34,477 | 275,819 | 1,078 | 0.2 | ok (2 of 2) |
| t1_5v3_full | 65,536 | 8 | 33,512 | 268,098 | 4,028 | 0.2 | ok (2 of 2) |
| t1_2v1_full | 256 | 3 | 21,572 | 64,716 | 98 | 0.1 | ok (2 of 2) |
| t1_2v1_full | 1,024 | 3 | 87,567 | 262,700 | 115 | 0.1 | ok (2 of 2) |
| t1_2v1_full | 4,096 | 3 | 129,575 | 388,726 | 185 | 0.1 | ok (2 of 2) |
| t1_2v1_full | 16,384 | 3 | 103,295 | 309,884 | 464 | 0.1 | ok (2 of 2) |
| t1_2v1_full | 65,536 | 3 | 98,621 | 295,864 | 1,580 | 0.1 | ok (2 of 2) |

### Tier 2 (ARL Robot 1 airframe)

| Case | Games | Drones per game | Environment steps per second | Drone-steps per second | GPU memory used (device-wide) (MB) | Resets per step (%) | Status |
|---|---|---|---|---|---|---|---|
| t2_k2 | 64 | 2 | 2,235 | 4,470 | 5,326 | 2.5 | ok (2 of 2) |
| t2_k2 | 256 | 2 | 8,610 | 17,220 | 5,320 | 2.5 | ok (2 of 2) |
| t2_k2 | 1,024 | 2 | 32,350 | 64,699 | 5,595 | 2.5 | ok (2 of 2) |
| t2_k2 | 4,096 | 2 | 111,513 | 223,027 | 6,396 | 2.6 | ok (2 of 2) |
| t2_k3 | 64 | 3 | 1,764 | 5,291 | 5,322 | 2.6 | ok (2 of 2) |
| t2_k3 | 256 | 3 | 6,891 | 20,672 | 5,389 | 2.6 | ok (2 of 2) |
| t2_k3 | 1,024 | 3 | 25,494 | 76,481 | 5,702 | 2.5 | ok (2 of 2) |
| t2_k3 | 4,096 | 3 | 79,471 | 238,413 | 6,932 | 2.5 | ok (2 of 2) |
| t2_k8 | 64 | 8 | 950 | 7,600 | 5,339 | 2.5 | ok (2 of 2) |
| t2_k8 | 256 | 8 | 3,481 | 27,852 | 5,578 | 2.5 | ok (2 of 2) |
| t2_k8 | 1,024 | 8 | 12,425 | 99,398 | 6,428 | 2.5 | ok (2 of 2) |
| t2_k8 | 2,048 | 8 | 22,045 | 176,361 | 7,582 | 2.5 | ok (2 of 2) |
| t2_k2_100hz | 64 | 2 | 4,228 | 8,457 | 5,315 | 2.5 | ok (2 of 2) |
| t2_k2_100hz | 256 | 2 | 17,067 | 34,134 | 5,318 | 2.5 | ok (2 of 2) |
| t2_k2_100hz | 1,024 | 2 | 62,223 | 124,445 | 5,585 | 2.5 | ok (2 of 2) |
| t2_k2_100hz | 4,096 | 2 | 210,423 | 420,846 | 6,403 | 2.5 | ok (2 of 2) |
| t2_k3_100hz | 64 | 3 | 3,340 | 10,021 | 5,329 | 2.5 | ok (2 of 2) |
| t2_k3_100hz | 256 | 3 | 12,913 | 38,740 | 5,174 | 2.5 | ok (2 of 2) |
| t2_k3_100hz | 1,024 | 3 | 49,085 | 147,256 | 5,528 | 2.6 | ok (2 of 2) |
| t2_k3_100hz | 4,096 | 3 | 151,767 | 455,300 | 6,758 | 2.5 | ok (2 of 2) |
| t2_k8_100hz | 64 | 8 | 1,842 | 14,735 | 5,140 | 2.5 | ok (2 of 2) |
| t2_k8_100hz | 256 | 8 | 6,787 | 54,296 | 5,402 | 2.6 | ok (2 of 2) |
| t2_k8_100hz | 1,024 | 8 | 23,834 | 190,669 | 6,218 | 2.6 | ok (2 of 2) |
| t2_k8_100hz | 2,048 | 8 | 39,787 | 318,294 | 7,533 | 2.5 | ok (2 of 2) |
| t2_k8_250hz | 64 | 8 | 823 | 6,588 | 5,324 | 2.4 | ok (2 of 2) |
| t2_k8_250hz | 256 | 8 | 2,872 | 22,974 | 5,593 | 2.4 | ok (2 of 2) |
| t2_k8_250hz | 1,024 | 8 | 10,561 | 84,489 | 6,372 | 2.4 | ok (2 of 2) |
| t2_k1 | 64 | 1 | - | - | - | - | crash |
| t2_k1 | 256 | 1 | 12,762 | 12,762 | 5,357 | 2.5 | ok (2 of 2) |
| t2_k1 | 1,024 | 1 | 50,492 | 50,492 | 5,381 | 2.5 | ok (2 of 2) |
| t2_k1 | 4,096 | 1 | 178,346 | 178,346 | 5,837 | 2.5 | ok (2 of 2) |

## Gates

| Gate | Limit | Observed | Result |
|---|---|---|---|
| tests_pass | true | true | PASS |
| sweep_complete | true | 1 missing, 0 invalid, 0 duplicate | FAIL |
| repeat_spread_max | 0.1 | 0.0562 (worst: t2_k8_100hz at 1,024 games) | PASS |
| nan_count_max | 0 | 0 | PASS |

Missing points (no complete measurement): t2_k1 at 64 games

## Decision rules

Proposed rules read off the numbers; not pass or fail.

- Tier 1 bulk training (case t1_5v3_full): best 382,206 drone-steps per second at 1024 games, rule is at least 50,000: meets.
- Tier 2 training (best tier 2 case t2_k3_100hz): best 455,300 drone-steps per second at 4096 games, rule is at least 20,000: meets.

## Compute budget

2,000,000,000 drone-steps / 382,206 drone-steps per second (case t1_5v3_full at 1,024 games) = 1.5 GPU-hours.

## Limits of this record

- Stand-in drone models: tier 1 uses a placeholder lag and delay, tier 2 uses Isaac Lab's ARL Robot 1 airframe.
- no safety filter in either tier (its port is S1).
- Ray march fixed at 24 steps.
- Throughput includes a per-step finiteness check of every floating-point output.
- Warm-up is at least 50 steps and at least 2 s per repeat.
- No policy network and no learning update are inside the timed step: the compute budget covers simulator stepping only and is a lower bound on training time.
- The budget assumes the published 2 billion samples are drone-steps; if they are environment steps, multiply it by the number of drones per game (8 for 5 against 3).
- Tier 2 rewrites every drone's root state on every policy step and has no flight controller.
- Case t2_k8_250hz runs a 20.8 Hz policy (12 steps of 4 ms), not 20 Hz.
- Tier 1 computes respawn candidates for every drone on every step, whether or not a drone is respawned.
- Numbers were observed in the training simulator; nothing here is a flight result.
