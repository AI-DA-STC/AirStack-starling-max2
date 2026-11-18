Simulator: training simulator, tier 1 (the hangar game of Phase 4 row 5: the all-pairs safety filter, the commander copy, delay and lag of the EXPLORATORY fitted drone model, drones free in height with the start-height jitter). Not a flight result.

# 2026-11-18 NUS port, Phase 5 pilot P1 (W12): Guard learners against S20 (pilot, not gated, INFO record)

**Pilot, not gated, INFO record.** P1 asks whether a simple learner (the skrl IPPO stand-in) finds a Guard strategy against
NUS's Strike policy S20 on the hangar game with the safety filter in the loop ("use the filter as a wall", plan D-P5-7).
Nothing here is a strategy of record; no gate applies. Promotion signal (plan section 7): the final mean-action hold
against S20 on the 1,000 Phase 4 paired starts has a Wilson 95 % lower bound above 0.460. **Not met** (0/1000 holds).

| Item | Value |
|---|---|
| Purpose | Pilot P1 of `docs/plans/2026-11-18-nus-phase5-retraining.md` section 7: three Guard learners (one network per Guard drone) against the Strike team played 100 % by S20 |
| Date, machine | 2026-11-18, 17:02:59 to 18:03:37 (+08:00), home RTX 5090 workstation (NVIDIA GeForce RTX 5090, torch 2.7.0+cu128, skrl 2.1.0); GPU otherwise idle (`scripts/isaac_preflight.sh --approved-headless` exit 0, `runs/nus_port/phase5/pilots/preflight_p1.txt`; another session did CPU-only work in another worktree) |
| Code | branch `nus-phase5`, commit `c74cb5b2`, clean working tree |
| Command | `scripts/train_standin.py --game nus_hangar --settings pilot_p1 --seed 101 --name 2026-11-18_nus_phase5_pilot_p1 --runs-dir runs/nus_port/phase5/pilots --device cuda` |
| Settings | `configs/nus_phase5.toml [pilot_p1]` (PROPOSED; table sha256 `3514775d2c4a20c6`): `[standin_v2]`'s learner (hidden [128, 128], init log std −1.6, yaw log std frozen, vz trained, lr 3e-4, 32 rollouts, 5 epochs, 4 minibatches, γ 0.99, λ 0.95, skrl's other defaults), shaping weight 1.0, the policy acting every tick, observation interface v0.1, budget 236 M game-steps, hard cap 1.5 GPU-h including the evaluations |
| Game | Phase 4 row 5 (`configs/nus_phase4.toml`, `configs/nus_hangar_game.toml`, the EXPLORATORY Starling parameter file; T5 = FAIL) with git-ignored local files (5090 only; sha256 prefixes: rules `dd22cc28ce2042f3`, deploy_w2 `c248c6bef3f6e17b`, deploy_ref `6d71c111959fd9b2`, hangar `b7f2870ee17d2d70`, starts `40c8cc59297f58d5`) |
| Games | 32,768 training games at once (P0's pilots' count), 3 Guard v 3 Strike drones, tier 1; training starts drawn fresh for every game by the replica's start rule (`NusHangarTrainGame`, run seed) |
| Evaluation | mean actions, Strike team S20; at the start and half-way on the first 256 Phase 4 paired starts, at the end on all 1,000; every game played to its end (time-out 2,400 ticks); evaluation seed 1101 |
| Seeds | training seed 101 (one seed: a pilot, no method claim) |
| Allocator | `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` (set by the pilot, replacing the shell's value) |

## Run

| Quantity | Value |
|---|---|
| Ending | FINISHED: the game-step budget was reached (7,202 timesteps, 225 updates, 235,995,136 game-steps); not stopped by the cap |
| Time | training 2,700 s; evaluations 929 s (start 187 s, half-way 281 s, final 461 s); videos 15 s (CPU, after the GPU work); process 3,652 s |
| Throughput (training, PPO updates included) | 87,390 game-steps/s (524,340 drone-steps/s), 32,768 games, 6 drones per game, tier 1, NVIDIA GeForce RTX 5090; PPO update about 0.70 s |
| GPU memory | peak allocated 4.04 GB, peak reserved 4.47 GB |
| Non-finite values | none (the run's guard did not fire) |
| Cap | 5,400 s; one evaluation estimated at 792 s from 20 warm-up ticks (the real evaluations ended sooner because every game ended before its time-out) |

## Learning curve (mean actions against S20)

| Evaluation | Timestep | Game-steps | Games | Holds (k/n) | Wilson 95 % | Mean game length (ticks) | Closest Guard–Strike approach 3-D, min / p5 (m) | Filter share | Rule breach rate |
|---|---|---|---|---|---|---|---|---|---|
| start | 0 | 0 | 256 | 0/256 | [0.000, 0.015] | 221.8 | 0.888 / 1.038 | 0.356 | 0.012 |
| half-way | 4,064 | 133,169,152 | 256 | 0/256 | [0.000, 0.015] | 510.4 | 0.898 / 0.991 | 0.315 | 0.090 |
| final | 7,202 | 235,995,136 | 1,000 | **0/1000** | **[0.000, 0.004]** | 812.6 | 0.898 / 0.989 | 0.252 | 0.118 |

The largest mean action rose from 0.597 to 1.000 (the Tanh mean saturates on at least one axis); the policies' standard
deviation fell from 0.20 to 0.13; the last value losses were about 0.056.

**Promotion signal: NOT MET.** The final Wilson lower bound is 0.000, against the bar 0.460 (the parked Guard's upper
bound). For comparison on the same starts and settings (Phase 4 row 5, T23): ParkedGuard holds 429 of 1,000 against S20
(571 Strike reaches), NUS's own Guard G19 holds 17 of 1,000.

What did change: the games last longer. The mean game length grew from 222 to 813 ticks (11 s to 41 s), so the learned
Guards slow S20 down but never hold to the time-out (2,400 ticks, 120 s). The rule breach rate grew with it (0.012 to
0.118).

**What the Guards do (two frames of the final videos, looked at by eye):** the three Guards sit spread around the zone, one
inside it and two near its edge, and barely move; S20's Strike drones wait at the walls and in the corners and one slips in
through a gap. The learner did not find the parked Guard's answer (one Guard at the zone centre, letting the filter's keep-out
close the zone).

## Diagnosis after the run (CPU only, INFO; `runs/nus_port/phase5/pilots/p1_diagnosis.md`, 5090 only)

On the first 64 Phase 4 paired starts (row 5, S20, CPU): zero-action Guards from the normal starts hold 27/64, ParkedGuard
28/64, P1's start networks 0/64 and its final networks 0/64. The untrained policy's mean action is not zero (mean |a_xy|
0.28, |a_z| 0.13 at the start), so the Guards leave the start cluster and drift 0.18–0.22 m off the flying height (zero
action: 0.03 m). The +1 for a hold comes only at the 2,400-tick time-out, which no training game reached (longest 1,317
ticks), and with γ = 0.99 per tick it would be discounted by 3e-11 from the start; the learner saw the −1 at a reach and the
nearest-Strike shaping, and learned to delay the reach by chasing. Two pilot fixes are proposed there (zero-mean
initialisation; one decision every 12 ticks with the shaping off); neither is implemented.

## Videos (STANDARDS section 8)

`runs/nus_port/phase5/pilots/2026-11-18_nus_phase5_pilot_p1/videos/` (5090 only), top-down, 6× real time:

| File | Evaluation | Game |
|---|---|---|
| `start_t0_best_strike_win_slot0.mp4` | start (also the "best": every evaluation held 0, ties keep the first) | Strike win |
| `start_t0_best_unfinished_slot1.mp4` | start | a second game (labelled "unfinished"; see limits) |
| `mid_t4064_strike_win_slot0.mp4` | half-way | Strike win |
| `final_t7202_strike_win_slot0.mp4` | final | Strike win |
| `final_t7202_unfinished_slot1.mp4` | final | a second game (labelled "unfinished"; see limits) |

There is no hold to show: no evaluation game was held.

## GPU hours

1.010 h (`runs/nus_port/phase5/pilots/gpu_hours.log`, 17:03:00 to 18:03:37), under P1's cap of 1.5 h. The pilots' ledger
stood at 1.461 of 6.0 h after P1 (P0 0.397, two P1 smokes 0.054, P1 1.010).

## Limits

- One seed, one learner configuration (the stand-in's), 236 M game-steps; a pilot shows only whether this learner finds a
  strategy quickly, not whether one exists.
- The EXPLORATORY drone model (T5 = FAIL) and tier 1 only.
- `agent_best.pt` is the start networks (all three evaluations held 0; the first is kept on a tie).
- Two cosmetic defects of the pilot code, found in this run, no effect on the numbers: the progress line prints
  "finished k/1000" for the 256-game evaluations (the denominator is the final size); a second video clip is labelled
  "unfinished" when no hold exists among the kept games, although that game did finish (a Strike win).
- The evaluation estimate (792 s) assumes every game runs to its time-out; the real evaluations were shorter, so the cap
  kept more time in reserve than needed. It did not bind: the budget ended the run.

## Output

`runs/nus_port/phase5/pilots/2026-11-18_nus_phase5_pilot_p1/` (5090 only, git-ignored): `interface.toml`, `agent.pt`
(final networks), `agent_best.pt`, `curve.json`, `train_result.json`, TensorBoard event files, `videos/`; the log
`runs/nus_port/phase5/pilots/2026-11-18_nus_phase5_pilot_p1.log`. Ledger row T26 (run on the home RTX 5090 as workstation row W12 and renumbered at the merge into `main`).
