Simulator: training simulator: tier 1 (fast engine; Starling layer: commander copy, safety filter on every pair, fitted PX4 response, exploratory) and tier 2 (Isaac Lab rigid-body Starling under the PX4 1.14 cascade copy), the L0.11 base game. Observed in the training simulator; not a flight result.

# 2026-11-21_ste_l02_speed record

## Run notes

- Say here whether the machine was suspended during the run (a suspend counts against the cap).
- One child process per point; Isaac Sim's start is in each tier 2 point's wall time, not in its rates.

## Purpose

STE task L0.2 Tier 2 speed in contested play (INFO, PLAN.md section 4; DISCUSSION P3): game-steps per second on tier 2 and tier 1 with a learner in the loop and both teams playing, per team size and games at once, and the largest games at once that fits this GPU. Feeds D3 (where to train) at gate G0.

## Commit

`ff579c7defd47306fcf5ddcbfedc6fb8a85ffb92` (diff sha256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`); later code changes: 0.

## Config

- Gate file copy `gates.toml`, sha256 `9475a9333990e3fdf867d349fa719a36e5b899ae505824319deaef46d2200877`.
- Game `configs/ste_l011/base.toml` (sha256 `96e0e7f61a49999da54eee81a544bf64c519cd80833f0dcdfa2a07edfc10cc4d`), tier 2 = the same with `starling_layer.backend = "physics"` (set in code; the file is not edited).
- Learner: guard team, skrl IPPO, the T41 recipe (12-tick decisions, 32 decisions per update, 5 epochs x 4 mini-batches, hidden [128, 128]), against strike_straight; scripted reference guard_mark_edge v strike_straight (16 x 12 ticks); 1 update(s) per point after 2 warm-up decisions.

## Model parameter set

Tier 1: `params/real_exploratory_v0.toml` (fitted PX4 response, exploratory). Tier 2: `params/starling_physics_v0.toml` with `params/sim_only_yaw_v0.toml` (SIM-ONLY yaw gains).

## Seeds

Game seed 120000 at every point; scripted players + 101 / + 202; skrl seed = game seed.

## Machine

jeremychia-Legion-Pro-7-16IAX10H; GPU NVIDIA GeForce RTX 5070 Ti Laptop GPU; torch 2.7.0+cu128. Exit code 0 (DONE). job ste_l02_speed_b (task L0.2), asked 1.4 GPU-h, used 0.294 GPU-h (shared ledger).

## Games at once and steps per second

| Point | Tier | Size | Games | Status | Scripted reference game-steps/s | Learner rollout game-steps/s | Training game-steps/s | Training drone-steps/s | PPO update (s) | GPU MiB, process (nvidia-smi) | torch peak reserved MiB |
|---|---|---|---|---|---|---|---|---|---|---|---|
| t2_3v3_1024 | 2 | 3v3 | 1,024 | fit | 9,505 | 9,838 | 9,764 | 58,584 | 0.3 | 2,491 | 166 |
| t1_3v3_1024 | 1 | 3v3 | 1,024 | fit | 44,114 | 52,895 | 50,807 | 304,842 | 0.3 | 374 | 174 |
| t2_3v3_2048 | 2 | 3v3 | 2,048 | fit | 15,944 | 14,664 | 14,514 | 87,083 | 0.6 | 2,655 | 330 |
| t1_3v3_2048 | 1 | 3v3 | 2,048 | fit | 71,362 | 76,960 | 71,417 | 428,503 | 0.8 | 520 | 320 |
| t2_3v3_4096 | 2 | 3v3 | 4,096 | fit | 25,246 | 25,499 | 25,161 | 150,964 | 0.8 | 2,945 | 618 |
| t1_3v3_4096 | 1 | 3v3 | 4,096 | fit | 135,717 | 143,266 | 133,673 | 802,041 | 0.8 | 828 | 628 |
| t2_3v3_8192 | 2 | 3v3 | 8,192 | fit | 40,985 | 42,053 | 41,369 | 248,215 | 1.2 | 3,523 | 1,128 |
| t1_3v3_8192 | 1 | 3v3 | 8,192 | fit | 234,370 | 229,083 | 207,992 | 1,247,955 | 1.4 | 1,306 | 1,106 |
| t2_5v3_4096 | 2 | 5v3 | 4,096 | fit | 18,470 | 24,810 | 24,428 | 195,424 | 1.0 | 3,095 | 766 |
| t1_5v3_4096 | 1 | 5v3 | 4,096 | fit | 77,164 | 106,199 | 99,627 | 797,018 | 1.0 | 966 | 766 |
| t2_2v1_4096 | 2 | 2v1 | 4,096 | fit | 38,914 | 38,671 | 38,228 | 114,684 | 0.5 | 2,819 | 496 |
| t1_2v1_4096 | 1 | 2v1 | 4,096 | fit | 285,043 | 299,699 | 275,101 | 825,304 | 0.5 | 710 | 510 |
| t2_1v1_4096 | 2 | 1v1 | 4,096 | fit | 41,549 | 40,643 | 40,230 | 80,460 | 0.4 | 2,747 | 422 |
| t1_1v1_4096 | 1 | 1v1 | 4,096 | fit | 382,562 | 427,463 | 393,614 | 787,228 | 0.3 | 638 | 438 |
| t2_3v3_16384 | 2 | 3v3 | 16,384 | fit | 61,187 | 68,814 | 67,368 | 404,206 | 2.0 | 4,703 | 2,234 |

Largest 3v3 games at once that fitted: tier 1 8192, tier 2 16384 (on this GPU's memory; the 5090 may hold more). Tier 1 against tier 2, training rate: 1v1 x 4,096: tier 1 / tier 2 = 9.8; 2v1 x 4,096: tier 1 / tier 2 = 7.2; 3v3 x 1,024: tier 1 / tier 2 = 5.2; 3v3 x 2,048: tier 1 / tier 2 = 4.9; 3v3 x 4,096: tier 1 / tier 2 = 5.3; 3v3 x 8,192: tier 1 / tier 2 = 5.0; 5v3 x 4,096: tier 1 / tier 2 = 4.1. Not run: t2_3v3_6144, t2_5v3_8192, t1_3v3_16384, t2_5v3_1024, t2_5v3_2048, t1_5v3_1024, t1_5v3_2048.

## Gates

Verdict: **INFO**. No gate on a speed (INFO). Controls:

- C-1a tier 2 against the PyTorch reference world, bare worlds with the same recorded inputs: 1024 games x 6 drones x 20 ticks, largest gap 0.00359 m (limit 0.02 m): PASS.
- C-2 learner loop, C-3 protected points, required controls present: PASS.
- C-1b GAME (INFO, not gated): first in/out difference at tick 14, 4 drone-ticks differ, largest gap while both in the game 0.00230 m.

## Videos

2-D clips (STANDARDS section 8): videos/t2_3v3_1024_hold_game0.gif: guard_mark_edge v strike_straight, hold at 1.8 s; videos/t2_3v3_1024_reach_game2.gif: guard_mark_edge v strike_straight, reach at 2.3 s; videos/t1_3v3_1024_hold_game0.gif: guard_mark_edge v strike_straight, hold at 2.1 s; videos/t1_3v3_1024_reach_game6.gif: guard_mark_edge v strike_straight, reach at 2.9 s. The height panel arrives with L0.12's replay change; 3-D Isaac Lab clips: VID-1, pending.

## Limits

- One update per point: the update time is one sample. The learner starts at the zero-mean policy (the standing-still Guard team); a trained team may change game length and filter work.
- Rates on this machine only; the 5090 rates differ.

## Run notes added by the lead

- **Figure and clips.** Training rate against games at once, 3v3, both tiers:
  [speed.png](../docs/figures/ste_l02/speed.png) (made by `scripts/make_ste_l02_l03_figures.py` from the run's
  results.json). The four 2-D clips as GIFs: [docs/media/ste_l02](../docs/media/ste_l02/README.md).
- **Smokes and why the check was split.** The first Isaac smoke (`runs/scratch_l02_smoke`, smoke gate file, cap 0.25 h)
  ended with exit 6: the tier 2 agreement control compared whole games against the PyTorch reference world and found a
  1,730 m gap (limit 0.02 m). The gap likely came from drones that were out of the game, which the game parks far away:
  a parked drone compared against one still flying counts as a huge gap (lead's reading; not tested on its own). QC L02-1 split the check: **C-1a**, gated,
  replays the recorded drone inputs on bare worlds (0.00359 m here, PASS); **C-1b**, information only, compares the game
  while drones are in it (0.00230 m here). QC L02-R1 then made the replay repeat every operation in order (restarts,
  parking of out drones, wall and height clamps), so parked drones are compared too. The second smoke
  (`runs/scratch_l02_smoke2`, a new folder) ended with exit 0, every control PASS. Smokes: 0.044 + 0.051 GPU-h.
- **Cap 1.5 → 1.4 GPU-h before the run of record** (LEAD CALL; the smokes had used about 0.096 of the task cap). A launch
  a minute before the run (`runs/2026-11-21_ste_l02_speed`) was refused with exit 2 because its `--cap-h 1.4` differed
  from the file's 1.5 (0 GPU-h). The change was committed as ff579c7d at 13:11:59 (e2b722fb after the
  branch was rebased), a second before the run launched at 13:12:00; the run's code.json names ff579c7d with no
  uncommitted change, and its `gates.toml` copy carries 1.4.
- **"Largest fit" for tier 1 is 8,192 only because 16,384 was not run** (the driver's point plan cut it:
  `cuts.json`). It is not a memory limit:
  tier 1 at 8,192 games used 1.3 GB (1,306 MiB for the process).
- **Out-of-memory detection is still unproven on Isaac:** no point ran out of memory (tier 2 fitted 16,384 games at
  4.7 GB), so the "did not fit" path was never exercised on the GPU.
- **Tier 2 (Isaac Lab) is slower than tier 1 per game-step:** 4.9–5.3× at 3v3, 4.1× at 5v3, 7.2× at 2v1 and 9.8× at 1v1
  (training rate, same games at once).
- **Suspend.** The machine was not suspended: one launch, effective time 1,059 s against a 1,060 s wall-clock span.
- Edited after the first write (same session, before any push; no number changed): the commit times of the cap change corrected (it was committed before the run, not after), and a mechanism marked as the lead's reading.
