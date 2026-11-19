Simulator: NUS's own 2-D game (JAX, CPU) and the Copy of NUS 2-D game (PyTorch, CPU), hangar geometry, the same 1,000 starts; home RTX 5090 (CPU only). Not a flight result.

# 2026-11-19 NUS port: G19 against P3S and G19 against S20, NUS's JAX game against the PyTorch copy, same starts (T42, INFO)

**INFO record, not gated.** Two match-ups played three ways on the same 1,000 starts, every action deterministic:

1. **NUS's JAX game**: NUS's environment and NUS's JAX actors, end to end (no game rule or step of STE's);
2. **PyTorch copy, NUS's JAX actors**: the Copy of NUS 2-D game (PyTorch) with NUS's JAX actors queried step by step through
   action workers (the method of T16 and T17);
3. **PyTorch copy, converted actors**: the Copy of NUS 2-D game (PyTorch) with the converted PyTorch actors.

| Item | Value |
|---|---|
| Purpose | (a) G19 against P3S in NUS's JAX code, not run before (only in the PyTorch copy, on other starts: Test 1); (b) G19 against S20 in NUS's own JAX game (T17 ran NUS's JAX actors inside the PyTorch copy); (c) same-start videos, NUS's JAX game beside the PyTorch copy |
| Policies | G19 = self-play seed 2, Guard generation 19 (`2026-11-17_selfplay_3v3_seed2/archive/0019_defender`); S20 = the same run, Strike generation 20 (`archive/0020_attacker`); P3S = Strike trained against NUS's scripted Guard (`2026-11-17_fixed_apf_3v3_attacker/checkpoints/final`); all trained by STE with NUS's code. Converted weights: `ref_s2_g19_guard`, `ref_s2_g20_strike`, `hangar_strike_fixed_apf` (T16, T17) |
| Starts | the W3 starts file (T17, sha256 `386cccde…`), 1,000 starts; rebuilt in NUS's environment from seed 20261118 and checked equal before the run (largest gap 0) |
| Game | the G19 checkpoint's game settings; the P3S and G19 configs have no differing game setting |
| Code | `scripts/nus_pair_jax_game.py` (arm 1, `nus_jax`), `scripts/nus_pair_compare.py` (arms 2 and 3, videos), branch `nus-g19-p3s` |
| Time | 19 Nov 2026, about 16:35–16:50 (+08:00); about 13 s per match-up for arm 1, 35 s for arms 2 and 3 |

## Results (observed in the training simulator)

Strike team reaches the zone, of 1,000 games (Wilson 95 %):

| Match-up | 1. NUS's JAX game | 2. PyTorch copy, NUS's JAX actors | 3. PyTorch copy, converted actors | Games whose outcome differs from 1 (arm 2 / arm 3) |
|---|:-:|:-:|:-:|:-:|
| G19 v P3S | 991 [0.983, 0.995] | 991 | 991 | 2 / 2 |
| G19 v S20 | 17 [0.011, 0.027] | 17 | 15 [0.009, 0.025] | 0 / 8 |

- Arm 1 for G19 v S20 equals T17's JAX arm (17 of 1,000) on the same starts.
- Drone paths. G19 v P3S games are short (most end with a reach); 714 of 1,000 stay within 0.1 unit of arm 1 to their end
  (median of each game's largest gap 0.05 units). G19 v S20 games run the full 200 steps; the paths start equal and drift
  apart slowly (game 0: 0.04 units at step 100, 0.53 at step 200; median of each game's largest gap 0.68 units). Arm 2
  (NUS's own JAX actors in the copy) drifts as well, so the drift is not caused by the conversion; likely small number
  differences (the copy runs in float32) that grow over many steps of a closed loop. Not tested by a control.
- In arm 1, every one of the 983 G19 v S20 games the Guard team holds has a Strike drone more than 10 units from the zone
  centre at some point (median of each game's farthest point 33 units). S20's drones wandering away from the zone is
  therefore a behaviour of S20 in NUS's own game, not of the port.

## Videos (same start, NUS's JAX game left, PyTorch copy right; rendered from the recorded positions)

`docs/media/nus/pairs/`: `g19_vs_p3s_game0_same_start` (Strike reaches at step 26 in both), `g19_vs_p3s_game121_same_start`
(one of the 9 Guard holds), `g19_vs_s20_game0_same_start` (Guard holds in both), `g19_vs_s20_game139_same_start` (Guard
holds in both; the game with the farthest Strike excursion, one Strike drone near x = −15 m in both). MP4 and GIF each.

## Limits

- One start set, one evaluation seed; 1,000 games per match-up.
- P3S was trained for 3,000 updates in the hangar arena (start distance and Guard boundary 8 units), as in T16.
- The NUS JAX game runs every game to NUS's step limit; the reach step is the first step NUS's `breach` flag is set.

## Note, 20 November 2026

The two scripts broke the rule that NUS-facing code holds no numeric literals (`tests/test_nus_rules_privacy.py`, G2); the
full suite was not run before the first merge. They now read the confidence level from the Phase 3 gate text and the
video hold time from the renderer, and the step keys are derived by `fold_in`. A rerun on the same starts gives the same
counts, differing games, intervals and largest gaps as the table above.

## Ledger

Row `T42` in `records/LEDGER.md`.
