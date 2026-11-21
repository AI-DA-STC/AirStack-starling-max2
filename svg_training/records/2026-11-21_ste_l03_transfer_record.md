Simulator: training simulator, the hangar game of Phase 4 row 6 (tier 2: Isaac Lab rigid-body Starling; safety filter on every pair, drones free in height with the start jitter) beside row 5 (tier 1, fitted response, exploratory). Observed in the training simulator; not a flight result.

# 2026-11-21_ste_l03_transfer record

## Run notes

- Say here whether the machine was suspended during the run.

## Purpose

STE task L0.3 (INFO, PLAN.md section 4; DISCUSSION P3): does the STE Guard policy (T41, trained on tier 1, 829 of 1000 holds against S20) keep its hold rate on the Isaac Lab physics drone, on the same 1,000 paired starts, without retraining? Parked Guard as the control.

## Commit

023d193dcf78a715591baae1442d3220df420c97

## Config

- Gate file copy `gates.toml`, sha256 `cdbaffb01b6a3f0cb1d0892993edf03b3aa2e22fa6761431fc25d275c98a799c` (both run folders).
- T41's game (Phase 4 row 5) and its tier 2 game (row 6, the drone only: control C-0); T41 as a held strategy (one decision per 12 ticks, mean actions) against S20, T41's evaluation and opponent seeds; the parked control through T24's path (ParkedGuard, the ladder seed).

## Model parameter set

Row 5: `params/real_exploratory_v0.toml` (EXPLORATORY). Row 6: `params/starling_physics_v0.toml` with the SIM-ONLY yaw gains.

## Seeds

Evaluation seed 1101, opponent seed 1303 (T41's own); ladder seed for the parked control. One policy, one opponent, 1,000 fixed starts.

## Machine

CPU part: jeremychia-Legion-Pro-7-16IAX10H, 4 threads. GPU part: NVIDIA GeForce RTX 5070 Ti Laptop GPU, torch 2.7.0+cu128. Exit code 0 (DONE). job ste_l03_isaac (task L0.3), asked 1.4 GPU-h, used 1.240 GPU-h (shared ledger).

## Games at once and steps per second

1,000 games x 6 drones in one Isaac world; tier 2 rates t2_parked 1,462, t2_t41 1,686 game-steps/s.

## Results

| Arm | Tier, row | Device | Players | Counted | Result | Closest 3-D min / median (m) | Filter share | Rule breach share | Upset games | Mean end tick |
|---|---|---|---|---|---|---|---|---|---|---|
| t1_cpu_t41 | 1, row 5 | cpu | T41 v S20 | holds | 831 / 1000 (0.831, Wilson [0.807, 0.853]) | 0.85 / 1.51 | 0.335 | 0.007 | 0 | 2035 |
| t1_cuda_t41 | 1, row 5 | NVIDIA GeForce RTX 5070 Ti Laptop GPU | T41 v S20 | holds | 829 / 1000 (0.829, Wilson [0.804, 0.851]) | 0.87 / 1.50 | 0.335 | 0.005 | 0 | 2030 |
| t2_parked | 2, row 6 | NVIDIA GeForce RTX 5070 Ti Laptop GPU | ParkedGuard v S20 | reaches | 525 / 1000 (0.525, Wilson [0.494, 0.556]) | 0.99 / 1.14 | 0.156 | 0.001 | 0 | 1342 |
| t2_t41 | 2, row 6 | NVIDIA GeForce RTX 5070 Ti Laptop GPU | T41 v S20 | holds | 856 / 1000 (0.856, Wilson [0.833, 0.876]) | 1.04 / 1.48 | 0.309 | 0.000 | 0 | 2093 |

Paired by start, tier 2 against tier 1 (CPU): held in both 780, lost on tier 2 51, gained on tier 2 76, lost in both 93; sign test p = 0.03278956169303341. References: T41 829 holds (tier 1, RTX 5090 CUDA); T45 831 (tier 1, CPU); T24 parked 524 reaches (row 6, RTX 5090); T23 parked 429 holds (row 5). Tier 1 on this GPU: 829 / 1000 (0.829, Wilson [0.804, 0.851]); 10 games differ from the CPU.

## Gates

Verdict: **INFO**. No gate on the hold rate (INFO). Controls:

| Control | Result | Detail |
|---|---|---|
| C-0 | PASS | {"differences": ["starling.backend", "row.drone"], "expected": ["starling.backend", "row.drone"]} |
| C-1 | PASS | {"expected_holds": 831, "games_differing_from_t45": 0, "holds": 831} |
| C-2 | PASS | {"band": [493, 555], "reaches": 525, "t24_reaches": 524} |
| C-3 | PASS | {"drones": 6, "games": 1000, "limit_m": 0.02, "max_gap_m": 0.0027672238647937775, "ops": 81, "reference_world": "TorchRigidBodyWorld", "ticks": 20, "world": "IsaacWorld"} |

## Videos

2-D clips (STANDARDS section 8): videos/t1_cpu_t41_strike_win_slot5.mp4; videos/t1_cpu_t41_hold_slot0.mp4; videos/t2_t41_strike_win_slot5.mp4; videos/t2_t41_hold_slot0.mp4; videos/t2_parked_strike_win_slot0.mp4; videos/t2_parked_hold_slot1.mp4; videos/t1_cuda_t41_strike_win_slot6.mp4; videos/t1_cuda_t41_hold_slot0.mp4. 3-D Isaac Lab clips (VID-1) pending; key games (paired starts lost / gained on tier 2): [16, 18, 23, 22, 28, 41].

## Limits

- One policy, one opponent, one seed of starts: no method claim (STANDARDS 6.5).
- Tier 2 is the training simulator's physics drone, not a flight.

## Run notes added by the lead

- **Figure and clips.** Holds of each arm with Wilson 95 % intervals and the parked control's reaches:
  [transfer.png](../docs/figures/ste_l03/transfer.png) (made by `scripts/make_ste_l02_l03_figures.py` from the run's
  results.json). The eight 2-D clips, converted from MP4 to GIF: [docs/media/ste_l03](../docs/media/ste_l03/README.md).
- **Cap 1.5 → 1.4 GPU-h before the run of record** (LEAD CALL; the smokes `runs/scratch_l03_cpu`, 0 GPU-h, and
  `runs/scratch_l03_gpu`, 0.041 GPU-h, both exit 0). The change was committed as 023d193d at 13:36:17 (f6c7e815 after the
  branch was rebased), before the CPU part launched at 13:36:36; every arm records 023d193d with no uncommitted change.
- **C-3b (information only) shows a 0.26 m gap within 20 ticks** between the Isaac world and the reference world when T41
  plays S20 on row 6, while the counts agree (no game ended, no tag, no reach in either world; filter corrections 69,544
  against 69,504). Likely closed-loop amplification (lead's reading, no control run): small physics differences
  feed back through the players and the filter and grow. The physics alone agree: C-3 (C-3a), the replay of the same inputs on bare worlds, 0.0028 m, PASS.
- **T41 on tier 2: 856 of 1,000 holds against 831 on tier 1 (CPU).** Paired by start: lost on tier 2 51, gained 76;
  sign test p = 0.033. Tier 2 is slightly better, not worse. One policy, one opponent, one set of starts.
- **The tier 1 CUDA arm (829) is information only**: 10 of 1,000 games differ from the CPU arm.
- **Suspend.** The machine was not suspended: one launch per part, one boot; CPU part 683 s effective against a 684 s
  span; Isaac part 4,391 s effective against a 4,465 s span: progress.json was last written at 15:01:20, 71 s before the
  run ended at 15:02:31 (the final write), a recording-stage difference, not a suspend.
- Edited after the first write (same session, before any push; no number changed): the commit times of the cap change corrected (it was committed before the run, not after), and a mechanism marked as the lead's reading.
