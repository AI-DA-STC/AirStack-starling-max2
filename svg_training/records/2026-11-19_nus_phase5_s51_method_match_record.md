Simulator: training simulator, Copy of NUS 2-D game (PyTorch), hangar geometry, NUS's observation layout; home RTX 5090. Not a flight result.

# 2026-11-19 NUS port, Phase 5 stage 5.1 "Method match": FAIL on 5.1-b and 5.1-c (T43)

**Gated; verdict FAIL.** The STE port of NUS's training method (PyTorch copy of NUS's alternating best-response MAPPO with
the archive pool, no APEX), 3 seeds × 8 generations, scored by the frozen 5.1 test against NUS's 3 hangar lineages (R0,
T29). Seeds 1001 and 2001 pass every part of the test. Seed 3001 fails two parts by small margins. The strength test
(5.1-d) passes for both teams. Under the frozen verdict order a FAIL is final (the follow-up seeds apply only after an
INCONCLUSIVE), and under the plan (§ checkpoints) a 5.1 FAIL stops route (b): stage 5.2 does not start.

| Item | Value |
|---|---|
| Gates | `configs/nus_port.toml [gates.phase5_method_match]`, FROZEN 18 Nov 16:20; verbatim copy `runs/nus_port/phase5/s51/score/gates.toml` (sha256 `078bd2d7…`) written before scoring |
| Calibration | R0 PASS (T29), N0 PASS (T30: the test fails untrained actors), C0 PASS (T33: the test passes NUS's own code on 3 new seeds) |
| Code | branch `nus-phase5-method` (`scripts/nus_selfplay_train.py --variant nus`, `scripts/nus_phase5_score.py --arm s51`) |
| Seeds | 1001, 2001, 3001, side by side on the home RTX 5090 (`--memory-fraction 0.2` each), with pauses for the owner's use of the PC |
| Time | first launched 18 Nov 19:13, restarted from checkpoints after pauses and the owner's reboot (last start 19 Nov 07:31); all three complete 19 Nov 21:06; videos rendered by 21:12; scored 22:00–22:10 (+08:00) |
| Scoring | 1,000 games per pairing, our 24 entries against NUS's 24 and NUS's scripted (APF) opponents |

## Results (observed in the training simulator)

| Part | Rule | Result | Verdict |
|---|---|---|---|
| 5.1-a completion | every seed archives every generation, no non-finite aborts | 3 of 3 seeds, 8 of 8 generations | PASS |
| 5.1-b learner works | no seed has two consecutive failed same-team generations in generations 1–6 (failed: the archived best's worst win rate against its own training pool, APF included, ≤ 0.5) | seeds 1001, 2001: no failed generation. Seed 3001: Strike generations 4 and 6 failed (two in a row for the Strike team) | **FAIL** |
| 5.1-c scripted columns | each entry's win rate against the other team's APF inside NUS's range for its team | 23 of 24 inside. Seed 3001 Guard generation 7: APF Strike reaches 91 of 1,000 (hold 0.909); NUS's Guard range [0.922, 0.989] | **FAIL** |
| 5.1-d Guard strength | mean hold against the other lineages' Strikes, ours − NUS, 95 % interval contains 0 | +0.157 [−0.008, +0.323]; ours 0.475 / 0.597 / 0.499, NUS 0.281 / 0.377 / 0.441; spread ratio 0.81 | pass |
| 5.1-d Strike strength | mean reach against the other lineages' Guards | −0.020 [−0.464, +0.424]; ours 0.782 / 0.704 / 0.354, NUS 0.455 / 0.699 / 0.747; spread ratio 1.46 | pass |

Information only (5.1-e): last-mover share ours 1.00 / 0.81 / 0.63, NUS 0.75 / 1.00 / 1.00; near-shutout share ours
1.00 / 0.94 / 1.00, NUS 0.94 / 1.00 / 0.88; generalist mean ours 0.336 (band 0.2–0.8).

**Reading.** The port trains: every seed finishes, two of three seeds pass every part, and its policies are as strong as
NUS's against NUS's lineages (both strength intervals contain 0; the Guard difference leans towards ours). The failure
sits in one seed: two failed Strike generations in a row, and one Guard 0.013 below NUS's lowest bound against the APF
Strike. NUS's own seed 1 had one failed generation (Strike generation 4) under the same rule, scored at 256 games per pairing (T38), so single failures
occur in NUS's code too; whether the port fails more often than NUS's code is not settled by 3 seeds. The test was fixed in
advance and is not changed after the result.

## Videos (recorded in the run)

`docs/media/nus/s51/` (MP4 and GIF): `seed1001_archive_g07_guard_game00` (seed 1001, Guard generation 7, archived entry,
game 0), `seed3001_archive_g07_guard_game00` (the Guard entry outside NUS's APF range), `seed2001_archive_g08_strike_game00`
(seed 2001, Strike generation 8). All runs' clips: `runs/nus_port/phase5/s51/seed*/videos/` (not in git).

## Limits

- 3 seeds; the verdict is final under the frozen rule. More seeds would not change it.
- 2-D Copy of NUS 2-D game only; no STE drone condition is in this stage.
- The cause of seed 3001's failed generations is not tested.

## What follows

Under the plan, a 5.1 FAIL stops route (b) (stage 5.2, NUS's method in STE conditions, does not start) and the next step
is the owner's. The lead's recommendation, already open with the owner: carry on with the STE Guard policy route (T41).

## Ledger

Row `T43` in `records/LEDGER.md`.
