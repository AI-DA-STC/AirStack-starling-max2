Observed in the training simulator (tier 2, Isaac Lab), physics drone with the safety filter on every pair (committed neutral values); stand-in pipe test, not a strategy of record

# 2026-11-17T03:36:29+08:00 2026-11-17_s2b_standin_isaac record

Result: **INCOMPLETE** against `[standin_gates]` of `configs/s2.toml` (unchanged): 2 of the 3 required seeds ran on this laptop; seed 3 was not started here and is queued for the home RTX 5090. Both seeds that ran fail their own gate cells (see Gates), so the gate cannot pass when seed 3 is added. Ledger row T14. Observed in the training simulator; nothing here is a flight result.

## What this run shows

- **The pipe works on the Isaac Lab drones.** Each seed trained the full 100 M game-steps of `[standin_v2]` (762 updates, 4,096 games), with no NaN, no upset drone and no non-finite wrench. Each run folder loaded in `score.py` as a Guard strategy and was scored on the physics drone.
- **Against the straight Strike drone nothing was learned.** Both seeds hold 0 of 3,000 games, the same as random Guards (0 of 3,000). The scripted reference `guard_mark_edge` holds only 1.1 % on the same games. In most of these games the stand-in Guard drones were not in the Strike drone's way: the median horizontal closest approach is 1.04–1.92 m, and the games end about as early as with random Guards (mean end step 96–217 against 84–217). In a few games a Guard drone did get in the way (5th percentile 0.41–0.67 m horizontally, 1.05–1.10 m in 3-D) and the Strike drone still got through, which is consistent with T13's over/under passing; this run did not test that.
- **Against the flank Strike drone a little was learned, far short of the gate.** Here the Guard drones do meet the Strike drone: the median horizontal closest approach is 0.02–0.14 m in the lab and middle bands while the 3-D one stays near 1.0 m, so the drones pass one above the other (as in T13). Seed 1 holds 7.2 % (215 of 3,000) and seed 2 13.3 % (400 of 3,000), against random 0 % and `guard_mark_edge` 96.3 % (both seeds' games). The gate asks for at least 20 points above random. Both seeds started holding only after 40–60 M game-steps (figure 1).
- **Closest approach (3-D, scoring games):** the stand-in Guard drones come to 0.95 m (seed 1) and 0.95 m (seed 2) from a Strike drone, under the 1.10 m keep-out, as the scripted Guards do on the physics drone (`guard_mark_edge` 0.92–0.95 m). Random Guards come closer, 0.63–0.77 m. No scoring game had an upset drone.
- **For the end goal:** the stand-in learner with `[standin_v2]` does not learn to hold on the physics drone in 100 M game-steps. On pure partner rules the same settings reached 0.06–0.32 v straight (Step B pilots). The likely difference is the game on the physics drone, where Strike drones can pass vertically (owner's option (a): this stays in the game; the Guard team must cover height); no tier 1 control run was made here, so this is not tested.

## Purpose

S2b Task 9, run 2: train the stand-in (2 Guard drones, skrl IPPO) against the scripted Strike mix on the physics drone in Isaac Lab, score each seed on the physics drone, and apply the stand-in gate. It is a pipe test: does training, saving, loading and scoring work end to end on the Isaac Lab drones? It is not a strategy of record.

## Settings

- Settings table **`[standin_v2]` of `configs/s2b.toml`** (sha256 `06e8804eeb75fef9035bb64f80655a235401b56f4b27d49bada82b9660563dee`), **approved by the owner on 17 November 2026** for these runs (the final proposal of the Task 9 diagnosis). It differs from the committed `[standin]` in: 100 M game-steps per seed (50 M), initial policy log std −1.6 (skrl's 0), and the log std of the yaw-rate axis frozen at −1.6 for `physics` (the motion ignores yaw). Discount 0.99, GAE lambda 0.95, entropy 0, value-loss scale 2.5, ratio and value clip 0.2, grad-norm clip 0.5 are skrl's defaults, now written down and checked against skrl's effective values. Everything else as `[standin]`.
- Owner's game-design ruling (17 Nov, option a): vertical over/under passing stays in the game, so for `physics` the vz axis is trained.
- Command per seed: `train_standin.py --headless --config configs/s2.toml --settings standin_v2 --seed <s> --name 2026-11-17_s2b_standin_isaac_seed<s> --motion physics --eval-every-updates 80 --stop-at 2026-11-17T07:58:00` (host conda `env_isaaclab`).
- **Deviation: learning-curve evaluation every 80 updates, not the default 20.** On the physics drone one evaluation flies the whole 4,096-game world for up to 1,200 steps (about 75–150 s). At 20 updates the evaluations alone would have cost about 90 min per seed and only one seed would have fitted before the laptop was packed. This is not expected to change training: the evaluation games use their own generator and the whole world state is written back after each one. That write-back was shown bit-exact on the PyTorch reference world only; on PhysX it is not verified (Task 9 report, concern 4). The curves have 11 points per seed instead of 40. The same value was used for both seeds.
- `--stop-at 07:58` was a safety stop for the 08:15 deadline (clean stop at an update boundary); it did not trigger.
- Wall-clock cap: `[standin_s2b] wall_clock_cap_min_isaac` = 180 min of training time; not reached.

## Gates

`[standin_gates]` copied before the runs to `runs/2026-11-17_s2b_standin_isaac/gates.toml`: for every seed and both Strike behaviours, trained hold rate minus random ≥ 0.20 and disjoint Wilson 95 % intervals, over 3 bands × 1,000 games, evaluation seed = training seed + 1000; all 3 seeds must pass.

| Seed | Strike | Stand-in hold (95 %) | Random hold (95 %) | Gain | Cell |
|---|---|---|---|---|---|
| 1 | straight | 0.000 (0.000–0.001) | 0.000 (0.000–0.001) | +0.000 | FAIL |
| 1 | flank | 0.072 (0.063–0.081) | 0.000 (0.000–0.001) | +0.072 | FAIL |
| 2 | straight | 0.000 (0.000–0.001) | 0.000 (0.000–0.001) | +0.000 | FAIL |
| 2 | flank | 0.133 (0.122–0.146) | 0.000 (0.000–0.001) | +0.133 | FAIL |
| 3 | both | not run on the laptop; queued for the 5090 | | | — |

Verdict: **INCOMPLETE** (2 of 3 seeds). `train_standin.py verdict` over the two seeds says FAIL because it needs 3 seeds; its output is kept in `runs/2026-11-17_s2b_standin_isaac/verdict_seeds_1_2/verdict.json`. No gate was moved.

![Learning curves, seeds 1 and 2](../docs/figures/s2b_standin_isaac_curves.png)

*Figure 1. Learning curves on the physics drone (256 evaluation games, mean actions; evaluation seed = gate seed, so not used to pick a checkpoint). Hold rate v straight stays 0; v flank rises after 40–60 M game-steps to about 0.1. Training speed rose once the other Isaac jobs left the GPU.*

![Gate bars](../docs/figures/s2b_standin_isaac_bars.png)

*Figure 2. Scoring games, 2v1, 3,000 per bar (Wilson 95 %): stand-in per seed, random and the scripted `guard_mark_edge` (information). Title says INCOMPLETE: seeds 1–2 of 3.*

## Per seed

| Seed | Status | Wall time (start → end) | Training / evaluation time | Game-steps | Hold v straight / v flank (scoring) | 3-D closest, min / p5 range over bands (m) | Upsets / NaN |
|---|---|---|---|---|---|---|---|
| 1 | FINISHED | 03:36 → 05:02 (86 min) | 3,667 s / 1,462 s | 99,999,744 of 100 M | 0.000 / 0.072 | 0.95 / 1.01–1.10 | 0 / 0 |
| 2 | FINISHED | 05:02 → 06:11 (69 min) | 2,934 s / 1,199 s | 99,999,744 of 100 M | 0.000 / 0.133 | 0.95 / 1.00–1.08 | 0 / 0 |
| 3 | NOT RUN here | — | — | — | — | — | — |

## GPU sharing

- Seed 1 shared the GPU with Task 8's two Isaac scoring runs of record (2 × 2.3 GB; they finished at about 04:02 and 05:01). The preflight returned 11 (GPU in use) because of them only; this was accepted by the lead's ruling. Training ran at 20–31 k game-steps/s.
- Seed 2 had the GPU to itself apart from this task's own scoring of seed 1 (05:02–05:46, about 2.3 GB). The preflight returned 0. Training ran at 23–46 k game-steps/s.
- A 640-timestep timing run before seed 1 (not of record, `runs/sdd/s2b/task9/isaac_timing_v2diag_seed1/`, diagnosis flags with the same values) gave 21.6 k game-steps/s and about 140 s per evaluation; it set the evaluation interval.

## Seeds done and left

- Done on this laptop: seeds 1 and 2 (trained and scored, with the `guard_mark_edge` reference).
- **Left for the RTX 5090: seed 3** (training and scoring). Lead's ruling at 05:52: seed 3 would have ended 08:07–08:15, too close to the 08:15 stop. The commands are in `runs/sdd/s2b/task-9-isaac-report.md`.

## Commit

- Training, seed 1: `997a5d2-dirty`; seed 2: `a288d69-dirty` (as each `interface.toml` says). The commits between them add only `scripts/workstation/` files. No file under `source/`, `configs/` or `params/`, and neither `scripts/train_standin.py` nor `scripts/score.py`, changed on disk after 03:36 (seed 1's start; checked by modification time at the end), so both seeds ran the same training and scoring code. The files that did change after 03:36: `scripts/workstation/*`, `scripts/make_s2b_flowchart.py`, `scripts/compare_backends.py`, `scripts/diag_vertical_pass.py` (other sessions) and `scripts/make_s2b_figures.py` (this task, the figure only).
- Scoring (`scores.json` meta): seed 1 commit `a288d69`, code fingerprint `0395a6ffb496`; seed 2 commit `a3e1039`, code fingerprint `7236b4691a3a` (the fingerprint hashes all of source/, scripts/ and configs/, so it moves with any edit there).

## Config

`configs/s2.toml` `[standin_gates]` (gates, unchanged, pinned); `configs/s2b.toml` `[standin_v2]` (settings), `[standin_s2b]` (caps), `[tensorboard]`; game `configs/s2_game.toml` (sha256 `da8dd28fab3b`), committed neutral values only (`--no-local`).

## Model parameter set

Physics drone `params/starling_physics_v0.toml` (sha256 `888f4aea1b5a`), with the SIM-ONLY yaw-rate gains of `params/sim_only_yaw_v0.toml` (owner's ruling 16 Nov 2026; never a drone value); commander and safety filter from `params/real_exploratory_v0.toml` (exploratory). Physics step 0.005 s, motor lag on.

## Seeds

Training seeds 1 and 2; scoring seeds 1001 and 1002 (training seed + 1000); Strike strategy seeds as `score.py` (seed + 202).

## Machine

NVIDIA GeForce RTX 5070 Ti Laptop GPU (12 GB); Isaac Sim 5.1.0 / Isaac Lab 2.3.2 on the host (conda `env_isaaclab`, skrl 2.1.0), headless; WiFi with a remote-desktop program running (owner's approval of 16 Nov for headless launches).

## Games at once

Training 4,096 games (2v1, 3 drones each); learning-curve evaluation 256 of them; scoring 1,000 games per pair and band (`--batch-per-pair`).

## Steps per second

Training game-steps per second (training time only): seed 1 19.8–31.1 k (shared with Task 8), seed 2 23.4–46.4 k (shared with this task's scoring until 05:46). Drone-steps per second = 3 × these.

## Files

- `runs/2026-11-17_s2b_standin_isaac/`: `gates.toml`, `preflight_seed1.txt` (exit 11), `preflight_seed2.txt` (exit 0), `launched.txt`, `verdict_seed1_only/`, `verdict_seeds_1_2/` (the tool output), `bars_input/verdict.json` (a copy whose verdict text reads INCOMPLETE, used only for the figure title), `curves_table.md`, `bars_table.md` (the numbers plotted).
- `runs/2026-11-17_s2b_standin_isaac_seed{1,2}/` (interface.toml, agent.pt, curve.json, train_result.json, TensorBoard files) and their `.log`.
- `runs/2026-11-17_s2b_standin_isaac_seed{1,2}_score/` (trained + random) and `..._score_mark_edge/` (information), with logs.
- Figures: `docs/figures/s2b_standin_isaac_curves.png`, `docs/figures/s2b_standin_isaac_bars.png`.
