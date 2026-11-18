Simulator: NUS's own 2-D game (JAX), trained with NUS's code; NUS's default geometry and the hangar geometry. Not a flight result.

# 2026-11-17 NUS port, Phase 2a: policies trained with NUS's code (INFO, after the fact)

**INFO record, written 18 November 2026 from the logs and outputs listed below; no ledger number at the time of the runs.**
No gates: these runs made the reference policies for Phases 3–5. The policies are trained by us with NUS's code on our
hangar set-up; they are not NUS's own policies.

| Item | Value |
|---|---|
| Purpose | Phase 2a of the NUS port: measure NUS's trainer's speed, train fixed-opponent policies, then self-play policies on the hangar geometry, as references for the replica, the conversion and the transfer ladder |
| Date, machine | 2026-11-17, 21:33, to 2026-11-18, 03:51 (+08:00); the lab's RTX 5090 workstation |
| NUS code | `area-denial-continuous-space-self-play`, commit `2d2b904`; conda `nus_jax` (Phase 1 record) |
| Runner | every job through `scripts/workstation/run_nus_job.sh` (cloud logging off, `PYTHONNOUSERSITE=1`, a JAX memory fraction); exact commands in TRAINING, NUS jobs |
| Hangar geometry | `+environment.env.physics.spawn_distance=8.0 environment.env.physics.defender_boundary=8.0` (0.40 m per unit, 0.60 s per step; NUS_PORT §3) |
| Logs | `~/nus_jax_runs/<job>.log` and `<job>.cmd.txt` on the workstation (not in git) |
| Outputs | NUS's git-ignored `outputs/` folder in the NUS clone: `fixed_apf/2026.11.17/…` (default geometry), `hangar/2026-11-17_fixed_apf_3v3_{defender,attacker}/`, `hangar/2026-11-17_selfplay_3v3_seed{1,2,3}/`; seed 2 continued in place (launcher folder `hangar/2026-11-18_selfplay_seed2_to20_launcher/`) |

## Runs and results (observed in the training simulator)

| Run | Setting | Result |
|---|---|---|
| Speed | NUS's `benchmark_self_play_2048`, 3 v 3 against fixed APF opponents | compile and warm-up 14.8 s; 0.0565 s per update (5 updates, sd 0.0004 s) of 25,600 game-steps: about 453,000 game-steps/s |
| Fixed opponent, NUS default geometry | `train_mappo_self_play_mpe`, 3,000 updates per team (`total_environment_steps=76800000`), about 6.5 min and 1.7 GB of GPU memory each | Guard team held 20 of 20 evaluation games against the APF Strike; Strike team reached the zone in 20 of 20 against the APF Guards |
| Fixed opponent, hangar geometry (**P3G**, **P3S**) | the same with the hangar overrides, `save_eval_gif=True` | Guard held 19 of 20; Strike reached in 20 of 20 (120 evaluation GIFs in each run's `replays/`) |
| Self-play, hangar | `train_self_play`, seeds 1, 2, 3, `self_play.generations=8` (NUS's default is 32), 6,000 updates per generation, three jobs sharing the GPU at memory fraction 0.25 (about 0.13 s per update); 22:42 to 01:27 | all 8 generations archived in each seed; cross-play in the self-play matrix record |
| Self-play, seed 2 continued | `checkpoint_path=<seed 2 run> self_play.generations=20`, alone on the GPU (about 0.07 s per update); 02:16 to 03:51 | 20 generations archived; archive entries `0019_defender` (**G19**) and `0020_attacker` (**S20**) became the reference pair |

## Faults and lessons

- The first two fixed-opponent jobs (default geometry) started in the same second and shared one output folder; the
  Strike run was repeated with its own `hydra.run.dir`. Every later job got a unique folder.
- NUS's self-play runner wrote no GIFs even with `save_eval_gif=True` (we observed that its ensemble runner does not
  call the evaluation logger); the clips were rendered afterwards with NUS's `ma_skills/scripts/eval.py`.

## Verdict

INFO. No gates.

## Limits

- One seed continued to 20 generations; 8 generations per seed, against NUS's default of 32.
- Evaluations of the fixed-opponent runs are 20 games each (NUS's evaluation setting), below our 1,000.
- NUS's training on a GPU is not repeatable bit for bit: a retrain gives different policies.

## Ledger

Row `T37` in `records/LEDGER.md` (INFO, after the fact).
