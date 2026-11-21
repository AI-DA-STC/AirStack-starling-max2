Simulator: training simulator: tier 1 (fast engine; Starling layer: commander copy, safety filter on every pair, fitted PX4 response, exploratory) and tier 2 (the same command chain driving the Isaac Lab 2.3.2 rigid-body Starling in PhysX); study tag on (P1, PROPOSED). Observed in the training simulator; not a flight result.

# 2026-11-21_ste_l013_tier2_trains record

## Run notes

- **Never suspend the machine during a GPU job**: the cap clock and the GPU-hour ledger are wall clock less the owner's gpu_pause.sh pauses only. Say here whether the machine was suspended during the runs.
- **The game** (LEAD CALL 21 Nov 2026): PLAN.md row L0.13 named pilot P1b's recipe in the hangar game; the lead moved the task to the STE game: the L0.12 Guard run's recipe (T41's, one decision per 0.6 s, terminal reward only) on the L0.11 base game (tag 1.6 m, 3v3), exploiter Guard team against strike_straight. The PLAN's gate is kept in substance.
- **One procedure in both arms**: same games at once, game-step budget, seed and evaluation starts; one Isaac world per process, so tier 2 evaluations play on a view of the training world, and after every evaluation the training games restart afresh in both arms.
- **Resume** (by design): networks, optimisers, scalers, counters and the torch random state are restored at the last update boundary; the training games restart afresh, so a resumed arm is not identical to an unbroken one.
- **3-D clips** of the key games: pending (task VID-1b); the 2-D clips with the height panel are listed below.

## Purpose

STE task L0.13 Does tier 2 train at all? (PLAN.md section 4): the L0.12 Guard recipe trained on tier 2 (the Isaac Lab rigid-body Starling) beside a fresh tier 1 control with the same games at once and the same game-steps; tier 2 trains if its final Guard's hold rate on tier 2 has a Wilson lower bound above the parked Guard's upper bound in the same batch.

## Config

- Gate file sha256 `db4f9bf34aa815358f052de41109a2bf9c88bd237d1c0c6fbb8cef3eccf98871` (copy in each arm folder: `gates.toml`).
- Game `configs/ste_l011/base.toml`, sha256 `96e0e7f61a49999da54eee81a544bf64c519cd80833f0dcdfa2a07edfc10cc4d` (tier 2 sets starling.backend = "physics" in code; the file is never edited).
- 16,384 games at once in both arms; 48 updates = 301,989,888 game-steps planned; training seed 130102 in both arms; T44's first 1000 starts for every scoring batch.

## Model parameter set

- t1 (tier 1): `params/real_exploratory_v0.toml`, sha256 `4c93543f51ab41ea5bb0f81e6d1b0512f662a3e10126ec2d85fc3bb008cecaa2`; safety filter on every pair, 1000 sweeps, check every 8
- t2 (tier 2): `params/starling_physics_v0.toml`, sha256 `888f4aea1b5a8440c9685744df62459e9f09cb9907eb8b6a1006c89350a90eb2`; safety filter on every pair, 1000 sweeps, check every 8; sim-only gains 'params/sim_only_yaw_v0.toml'

## Commit

- t1: `fa3281ba445b35e62679ed3de5c6f7c252844ef8` (diff sha256 e3b0c44298fc)
- t2: `fa3281ba445b35e62679ed3de5c6f7c252844ef8` (diff sha256 e3b0c44298fc)

## Machine

- t1: jeremychia-Legion-Pro-7-16IAX10H, NVIDIA GeForce RTX 5070 Ti Laptop GPU, torch 2.7.0+cu128; exit 0 (DONE); effective 849 s of 0.75 h; 1 launch(es); job l013_t1 (task L0.13), asked 0.75 GPU-h, used 0.237 GPU-h (shared ledger)
- t2: jeremychia-Legion-Pro-7-16IAX10H, NVIDIA GeForce RTX 5070 Ti Laptop GPU, torch 2.7.0+cu128; exit 0 (DONE); effective 4627 s of 2.5 h; 1 launch(es); job l013_t2 (task L0.13), asked 2.5 GPU-h, used 1.289 GPU-h (shared ledger)

## Games at once and steps per second

- t1: 16,384 training games, 6 drones per game, tier 1, NVIDIA GeForce RTX 5070 Ti Laptop GPU: median 360,226 game-steps/s; 48 updates, 301,989,888 game-steps (budget: 301,989,888 game-steps in 48 updates (301,989,888 planned))
- t2: 16,384 training games, 6 drones per game, tier 2, NVIDIA GeForce RTX 5070 Ti Laptop GPU: median 70,468 game-steps/s; 48 updates, 301,989,888 game-steps (budget: 301,989,888 game-steps in 48 updates (301,989,888 planned))

## Gates

Verdict: **PASS**.

| Arm | Tier | Trained Guard holds | Parked Guard holds (same batch) | Bar cleared | Budget reached | Upset games, trained / parked (INFO) |
|---|---|---|---|---|---|---|
| t2 | 2 | 832/1000 = 0.832 (0.808–0.854) | 538/1000 = 0.538 (0.507–0.569) | **True** | True | 0 / 0 |
| t1 (control, INFO) | 1 | 836/1000 = 0.836 (0.812–0.858) | 534/1000 = 0.534 (0.503–0.565) | True | True | 0 / 0 |

Networks x tiers at update 48 (T44's starts, INFO):

| Networks | Tier 1 holds | Tier 2 holds |
|---|---|---|
| t2 networks | 846/1000 | 832/1000 |
| t1 networks | 836/1000 | 814/1000 |

Paired by start (t2 networks on tier 2 v t1 networks on tier 1): held in both 820, t2 only 12, t1 only 16, neither 152.

Scale (INFO): L0.12's base Guard held 913/1000 on tier 1 at 553,648,128 game-steps (records/2026-11-21_ste_l012_best_response_record.md).

## Figures and videos

- learning curves: `runs/2026-11-21_ste_l013_verdict/learning_curves.png` (each arm's networks on its own tier and the other tier; the parked Guard's interval as a band).
- t1: videos/l013_t1_tier1_game1_reach.gif: tier 1, game 1, reach at 3.1 s (0.05 MB)
- t1: videos/l013_t1_tier1_game0_hold.gif: tier 1, game 0, hold at 2.5 s (0.05 MB)
- t2: videos/l013_t2_tier2_game2_reach.gif: tier 2, game 2, reach at 2.4 s (0.05 MB)
- t2: videos/l013_t2_tier2_game0_hold.gif: tier 2, game 0, hold at 1.5 s (0.04 MB)

## Run notes added by the lead

- **Figure and clips.** Learning curves of both arms, each arm's networks on its own tier and on the other tier, with the
  parked Guard's interval as a band: [learning_curves.png](../docs/figures/ste_l013/learning_curves.png) (a copy of the
  verdict's figure, made by `scripts/ste_tier2_l013.py verdict`). The curves are read on 256 curve starts (seed
  130900), not T44's 1,000 scoring starts, so their end points (about 0.79–0.81) differ from the 832 and 836 above. The four 2-D clips, with the height panel:
  [docs/media/ste_l013](../docs/media/ste_l013/README.md).
- **(a) The game** (LEAD CALL 21 Nov 2026): the lead moved L0.13 from the PLAN's pilot P1b hangar game to the L0.12 base
  game and Guard recipe, so the result is comparable with T46's base Guard (913 of 1,000 at 553,648,128 game-steps).
- **(b) PASS = tier 2 learns.** At the same 301,989,888 game-steps tier 2 and tier 1 reach about the same hold rate (832
  against 836 of 1,000, each far above its parked Guard: 538 and 534), and each arm's networks move to the other tier with
  at most 22 games' difference (t2 networks 846 on tier 1, 832 on tier 2; t1 networks 836 on tier 1, 814 on tier 2).
  Lead's reading; one training seed, one opponent.
- **(c) Speed.** Tier 2 is about 5× slower per game-step (median 70,468 against 360,226 game-steps per second), so the
  same 302 M game-steps took 1.29 GPU-h on tier 2 against 0.24 on tier 1 (whole arms; tier 2 also plays 24 curve reads
  to tier 1's 8). Training time alone: 4,292 s against 826 s (5.2×).
- **(d) Physics check.** The tier 2 physics agreement control (C-1a) read 0.0166 m at 16,384 games (limit 0.02 m, PASS);
  the 3,000-game view of the same world read 0.0164 m; T48 read 0.0036 m at 1,024 games and T49 0.0028 m at 1,000.
  The cause of the larger reading here is not separated (world size, the recorded inputs, or the number of games
  compared); the lead's reading is that it grows with the games compared. The margin is 0.0034 m: a larger world (for
  example on the 5090) may fail this gate.
- **(e) Upsets and non-finite values** (evaluation batches and curve reads; the training log does not count them).
  Upset (tumbled) games: 0 in every evaluation batch and curve read of both arms, trained and parked, on both tiers.
  Non-finite physics values (physics_nonfinite): 0 on tier 1 and 0 on tier 2. Non-finite actions: 0, also in training.
- **(f) QC before the run:** 40 of 44 deliberate breakages caught; the 4 survivors (N03, N04, N08, N13) are test gaps whose
  effect would show in the run's own files. The lead checked those files: physics_nonfinite is 0 in results.json and in
  every one of the 32 curve reads (8 in t1, 24 in t2); tier_ran equals the tier asked in every curve read; every game in
  the evaluation files carries the tier of its file (eval_*_t1.npz all tier 1, eval_*_t2.npz all tier 2).
- **(g) 3-D clips** of the key games: pending task VID-1b.
- **Smokes** (SMOKE, every control PASS): runs/2026-11-21_ste_l013_smoke_t1 (0.008 GPU-h) and _smoke_t2 (0.055 GPU-h;
  physics check 0.0166 m at 16,384 games; projected time margin for the run of record +2,811 s).
- **Suspend.** Not suspended: one launch per arm, one boot; t1 853 s effective (progress.json) against an 855 s span,
  t2 4,638 s against 4,642 s (the 849 s and 4,627 s above come from results.json, written before the final write). GPU-hours: t1 0.237, t2 1.289 (the 1.527 in the ledger row); with the smokes 1.590.
- **Commit.** The arms name `fa3281ba`, which became `1ba631e8` when the branch was rebased on development.
- Edited after the first write (same session, before any merge; no number changed): the physics-check reading, the
  curve starts, whole-arm hours, the scope of the upset counts and the effective-time sources stated.

## Ledger row

Ledger row: | T53 | 2026-11-21T17:22:50+08:00 | training simulator: tier 1 (fast engine; Starling layer: commander copy, safety filter on every pair, fitted PX4 response, exploratory) and tier 2 (the same command chain driving the Isaac Lab 2.3.2 rigid-body Starling in PhysX); study tag on (P1, PROPOSED); NVIDIA GeForce RTX 5070 Ti Laptop GPU | 2026-11-21_ste_l013_tier2_trains | STE L0.13 Does tier 2 train at all? t2 832/1000 = 0.832 (0.808–0.854) v parked 538/1000 = 0.538 (0.507–0.569) on tier 2; t1 836/1000 = 0.836 (0.812–0.858) on tier 1; 301,989,888 game-steps; 1.527 GPU-h | PASS | records/2026-11-21_ste_l013_tier2_trains_record.md |

