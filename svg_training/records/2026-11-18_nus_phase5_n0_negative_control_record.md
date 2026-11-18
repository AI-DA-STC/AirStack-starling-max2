Simulator: training simulator, the replica of NUS's 2-D game (hangar geometry; no safety filter), scored on the home RTX 5090. Nothing here is a flight result.

# 2026-11-18 NUS port, Phase 5 N0: negative control (W16, PASS: the rule failed the untrained arm)

| Item | Value |
|---|---|
| Purpose | Plan section 4.3 (N0): three "lineages" of untrained actors (our initialisation, one fresh actor per generation slot, no training) scored as the "ours" arm by the frozen 5.1 rule. Required: verdict FAIL with **both** 5.1-d intervals excluding 0; otherwise the rule cannot catch a learner that learned nothing and 5.1 is not scored |
| Gates | `[gates.phase5_negative_control]` and `[gates.phase5_method_match]` (FROZEN 2026-11-18 16:20), with `phase3_converted_policy`, copied verbatim into `runs/nus_port/phase5/n0/score/gates.toml` before scoring (sha256 `0748a338ff12b44b7fdd4706c22437647e55811c11daa45d00b49161941464fc`) |
| Reference | R0 (W15, PASS): `runs/nus_port/phase5/reference/matrix_1000.json` (its 144 cells and APF columns reused unchanged); 5.1-c is a gate (R0's leave-one-out check passed) |
| Date, machine | 2026-11-18, 19:01:37-19:11:04 (+08:00); home RTX 5090, torch 2.7.0+cu128. A first scoring start at 19:00 stopped at once on a CUDA-only bug (the untrained actors were built on the CPU; fixed test-first, commit `352432b4`; 0.3 s of GPU, logged) |
| Concurrent jobs | C0 (NUS's trainer, 3 seeds), pilot P1b (`train_standin.py`), an Isaac clip job and the filter-graph check shared the GPU (`isaac_preflight.sh --allow-siblings` exit 0) |
| Code | branch `nus-phase5-method`, commit `352432b4` (`scripts/nus_phase5_score.py --arm n0`, `nus/crossplay.py`) |
| Arm | seeds 7001, 8001, 9001 (frozen table); generations 1-8, Guard in odd and Strike in even generations; our network at the method's shape (bfloat16 trunk); 5.1-a not applicable; 5.1-b pools: the selection rule over the earlier N0 entries of the other team plus APF |
| Scoring | 1,000 games per pairing on R0's start set (`starts_seed` 20261120), both teams deterministic: each N0 Guard against every reference Strike and its own lineage's Strikes, each reference Guard against every N0 Strike, both APF columns; 567 s of GPU wall clock (`runs/nus_port/phase5/n0/score/gpu_hours.log`) |
| Outputs | `runs/nus_port/phase5/n0/score/matrix_1000.json` (sha256 `9fc3223ed2c2576f18b833891cbbe9649df3da6f94662f4729086cd3d58ff51f`), `result.json` (sha256 `6844ac01e5ee1d800ef06e8256926bb4654a16665e826216fcf35cc127dec71a`) |

## Results (frozen rule, observed in the training simulator)

| Statistic | Rule | N0 | Verdict |
|---|---|---|---|
| 5.1-a completion | not applicable to N0 | - | - |
| 5.1-b learner works | no two consecutive failed same-team generations in 1-6 | every lineage fails (longest run 3) | fail |
| 5.1-c scripted columns | APF win rate inside the reference envelope (Guards 0.922-0.989, Strikes 0.996-1.000) | 24 of 24 entries outside | fail (gated) |
| 5.1-d Guard hold against the other lineages' Strikes | pooled t interval (t 2.776, SD floor 0.02) contains 0 | N0 0.0002, 0.0001, 0.0001 against reference 0.281, 0.377, 0.441: difference **-0.366, interval [-0.499, -0.234]** | excludes 0 |
| 5.1-d Strike reach against the other lineages' Guards | same | N0 0.047, 0.025, 0.047 against reference 0.455, 0.699, 0.747: difference **-0.594, interval [-0.848, -0.341]** | excludes 0 |
| Spread ratio (ours / reference, floored) | INFO for a FAIL | 0.249 and 0.128 | - |

The plan's expectation (lead's estimate from F5, INFO): about -0.37 against a half-width about 0.13 (Guards) and about -0.64 against about 0.25 (Strikes); observed -0.366 +- 0.133 and -0.594 +- 0.253.

INFO (5.1-e, margin 0.01 and band [0.2, 0.8] from `configs/nus_phase5_method.toml`): last-mover share 0.375 in each N0 lineage (reference 0.75, 1.0, 1.0); near-shutout share 0.06-0.31 (reference 0.88-1.0); generalist mean of the N0 arm 0.062.

## Verdict

The rule's verdict on N0 is **FAIL**, with both 5.1-d intervals excluding 0, as `[gates.phase5_negative_control]` requires: **N0 PASS** (the rule catches a learner that learned nothing). Its power against a partly broken learner is not measured; it cannot catch small differences (plan section 4.3). No videos: nothing was trained (the plan says so for N0).
