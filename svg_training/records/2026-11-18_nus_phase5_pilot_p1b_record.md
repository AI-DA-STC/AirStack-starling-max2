Simulator: training simulator, tier 1 (the hangar game of Phase 4 row 5: the all-pairs safety filter, the commander copy, delay and lag of the EXPLORATORY fitted drone model, drones free in height with the start-height jitter). Not a flight result.

# 2026-11-18 NUS port, Phase 5 pilot P1b (W15): ABORTED by the lead, GPU starved (pilot, not gated, INFO record)

**Pilot, not gated, INFO record. ABORTED by the lead (20:23, clean SIGINT) because the shared GPU starved it: 3 PPO updates
in about 1.5 h, about 2.4 s per simulator tick against 0.37 s solo.** No evaluation finished; there is no result for the
promotion signal (final mean-action hold v S20 Wilson lower bound > 0.460). The lead will rerun P1b on a near-solo GPU.

| Item | Value |
|---|---|
| Purpose | P1 plus the two fixes of the P1 diagnosis (`runs/nus_port/phase5/pilots/p1_diagnosis.md`, 5090 only): (1) zero-mean start (the last layer of each Guard policy's mean head zeroed: the start policy is the standing-still Guard, log std −1.6 kept); (2) one decision per 12 ticks (the deploy file's hold, the action held in between), γ = 0.99 per decision, shaping weight 0 (terminal +1 hold / −1 reach only) |
| Settings | `configs/nus_phase5.toml [pilot_p1b]` (table sha256 `bc0ea91905c5c29f`); opponent S20 (100 %), 32,768 training games, seed 101, evaluations on the Phase 4 paired starts (half-way 256, final 1,000; start evaluation skipped with `--no-eval-at-start`: the standing-still start is already measured, zero-action arm 27/64, and a CPU test shows P1b's start evaluation equals the zero-action arm) |
| Caps | 1.5 GPU-h as first set (FIXED by the lead); raised to **3.0 GPU-h** by the lead (18 Nov ~19:00, "shared GPU, ticks ~4x slower than solo; pilots' total stays 6.0 h"; commit `12a3e411`) |
| Code | branch `nus-phase5`: P1b code `ecad1389`, run from `12a3e411` (clean tree) |
| Command | `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True scripts/train_standin.py --game nus_hangar --settings pilot_p1b --seed 101 --no-eval-at-start --name 2026-11-18_nus_phase5_pilot_p1b --runs-dir runs/nus_port/phase5/pilots --device cuda` (own process session) |
| Machine | home RTX 5090, **shared** (owner, 18 Nov: run in parallel): `scripts/isaac_preflight.sh --approved-headless --allow-siblings` exit 0 |

## Attempts and timeline (18 Nov 2026, +08:00)

| Time | Event |
|---|---|
| 18:49:45 – 18:50:14 | first start, 1.5 h cap: **refused by the pilot's own cap rule** before anything was written: one evaluation estimated at 3,025 s side by side with C0 ×3 + R0, so the start and final evaluations (about 6,050 s) exceeded 5,400 s. Logged 0.008 h (`..._pilot_p1b_refused`) |
| about 18:51 | a waiting launcher (wait for a free GPU) ran for about one minute and was stopped by the lead's decision; it never launched |
| 18:51:57 | P1b started, 3.0 h cap, `--no-eval-at-start`; one evaluation estimated at 2,982 s |
| by 19:52 | 125 decisions (1,500 ticks per game), 3 PPO updates |
| about 19:55 | the half-way evaluation (256 games) started (update 4) |
| 20:23:27 | **stopped by the lead** (SIGINT) inside the half-way evaluation |

## Other jobs on the GPU at the same time (timings are not comparable to solo runs)

From the preflight (`preflight_p1b_2.txt`) and two snapshots (`p1b_gpu_neighbours.txt`, 19:22 and 19:52; 5090 only):
NUS's JAX trainer for C0 (three processes, 1,732 MiB each, all along); R0 (`nus_phase5_reference.py --run`, 1,456 MiB, at the
start); from about 19:20 the stage 5.1 self-play seeds 1001, 2001 and 3001 (`nus_selfplay_train.py`, 1,942 MiB each), Isaac
camera clips (`nus_isaac_clips.py`, about 4.7 GB) and a filter-graph test run from another worktree (772 MiB). P1b itself held
4,890 MiB.

## What was measured (training only; no evaluation finished)

| Quantity | Value |
|---|---|
| Decisions (skrl timesteps) | 125 logged by 19:52 (128 at the evaluation start) = 1,536 ticks per game; 4 updates begun, 3 logged |
| Speed | about 2.4 s per simulator tick (solo P1: 0.37 s); PPO update 6.1–8.1 s (P1 solo: about 0.7 s) |
| Training game length (decisions, mean) | 13.7, 26.0, 35.8, 46.6, 57.4 at decisions 25 … 125; the longest equals the decisions played (games still running since the start) |
| Reward (sum over the 3 Guards, per decision) | max 0.0, min −3.0 (a reach), mean −0.053 → −0.026; no hold could happen yet: a hold needs 200 decisions (2,400 ticks) and the run reached 128 |
| Value loss (per Guard) | about 4.3 → 2.3 over updates 2 to 3 |
| Policy standard deviation | 0.201 → 0.200 (the policy had barely moved from the standing-still start) |

The pilot's crash path wrote the GPU-hours line ("CRASHED: KeyboardInterrupt", 1.525 h; kept as written). No `agent.pt`,
`curve.json` or videos exist: the networks are saved and the clips rendered only when an evaluation finishes. The run folder
keeps `interface.toml` and the TensorBoard files.

## GPU hours

P1b 1.525 h + the refused start 0.008 h. The pilots' ledger (`runs/nus_port/phase5/pilots/gpu_hours.log`) stands at **3.073
of 6.0 GPU-h**.

## Lessons for the rerun

- Side by side with five to eight other jobs, P1b's ticks were about 6.5 times slower than solo: at 12 ticks per decision and
  32 decisions per update, an update took about 15 min, so 3 GPU-hours buy about 10 updates and fewer than one game length of
  training per update cycle. A near-solo GPU (the lead's plan: after C0 ends, other jobs paused) or the CUDA-graph filter path
  is needed for P1b to say anything.
- The cap rule's evaluation estimate is taken once at the start; on a GPU whose load changes it can be far off (here the GPU got
  busier after the start), so the rule reserved too little for the final evaluation (reported to the lead at 20:22).

## Output

`runs/nus_port/phase5/pilots/2026-11-18_nus_phase5_pilot_p1b/` (interface.toml, TensorBoard files), the log
`…_pilot_p1b.log`, `preflight_p1b.txt`, `preflight_p1b_2.txt`, `p1b_gpu_neighbours.txt`, `p1b_report.md` (5090 only,
git-ignored). Ledger row T32 (run on the home RTX 5090 as workstation row W15 of branch `nus-phase5` and renumbered at the merge into `main`).
