Simulator: NUS's own JAX trainer on the home RTX 5090 (training), then the training simulator's replica of NUS's 2-D game (hangar geometry; no safety filter) for scoring. Nothing here is a flight result.

# 2026-11-18/19 NUS port, Phase 5 C0: positive control (W17, PASS)

| Item | Value |
|---|---|
| Purpose | Plan section 4.3 (C0): NUS's own code, three new run seeds, scored by the frozen 5.1 rule as if it were ours. It must PASS before any of our seeds is scored: it shows the rule does not fail a correct copy by seed chance |
| Gates | `[gates.phase5_positive_control]` and `[gates.phase5_method_match]` (FROZEN 2026-11-18 16:20), with `phase3_converted_policy`, copied verbatim into `runs/nus_port/phase5/c0/score/gates.toml` before scoring (sha256 `c31e9268e5359e0c95932fd99870c7448261166a92fcaf01c0f502bfd14f0dc0`) |
| Training | NUS's `ma_skills/scripts/train.py --config-name=train_self_play`: the reference command of `~/nus_jax_runs/2026-11-17_hangar_selfplay_3v3_seed1.cmd.txt` with `seed` = 101, 201, 301 and `hydra.run.dir=outputs/hangar/2026-11-18_c0_selfplay_3v3_seed<seed>` changed, through `scripts/workstation/run_nus_job.sh --allow-shared-gpu --mem-fraction 0.25` (jobs `2026-11-18_hangar_c0_selfplay_3v3_seed{101,201,301}`, logs and commands in `~/nus_jax_runs/`); 8 generations each; 18:46:11 to 00:12:09 (+08:00), 5.4 h of wall clock, side by side |
| Concurrent jobs | R0 (18:49-18:52), N0 (19:01-19:11), our 5.1 seeds (from 19:14), pilot P1b, Isaac clip jobs and the filter-graph check shared the GPU (owner, 18 Nov: "parallelize"); NUS's update time rose from about 0.15-0.23 s (with C0 alone and R0) to about 0.48 s with everything running (F6: 0.071 s alone) |
| Reference observations | `scripts/nus_export_reference.py --archive-entry` x 24 (seed 20261122, 9 + 9 episodes per entry): 10,800 rows per entry (`runs/nus_port/phase5/c0/score/export_command.txt`) |
| Scoring | `scripts/nus_phase5_score.py --arm c0 --check` then `--score --device cuda`, commit `3220561b`: R0's reference cells reused unchanged; each C0 Guard against every reference Strike and its own lineage's Strikes, each reference Guard against every C0 Strike, both APF columns; 1,000 games per pairing on R0's start set (`starts_seed` 20261120), deterministic; 530 s of GPU wall clock. Outputs `matrix_1000.json` (sha256 `2f315fd1352514067b2f9c351e26b860105a42d875078025c9790a05f78870c1`), `result.json` (sha256 `6462e3afd7d0a4d0e51759b60048c877799089b254585a8e6e537fcdaf4da557`) |
| Videos | NUS's `eval.py`, two games per archived entry against its strongest opponent in its own archive evaluation (`scripts/nus_c0_videos.py`, CPU): 48 GIFs in `runs/nus_port/phase5/c0/videos/` (list in `videos.json`) |

## Results (frozen rule, observed in the training simulator)

| Statistic | Rule | C0 | Verdict |
|---|---|---|---|
| Gate (a) per entry | largest action error <= 0.02 units on >= 10,000 rows | 24 of 24; largest 0.0117 | pass |
| 5.1-a completion | every seed archives 8 generations; non-finite aborts 0 | 8, 8, 8; 0 aborts | pass |
| 5.1-b learner works | no two consecutive failed same-team generations in 1-6 | no failed generation in any lineage | pass |
| 5.1-c scripted columns (gated, R0's leave-one-out passed) | APF win rate inside the reference envelope (Guards 0.922-0.989, Strikes 0.996-1.000) | 24 of 24 inside | pass |
| 5.1-d Guard hold against the other lineages' Strikes | pooled t interval (t 2.776, SD floor 0.02) contains 0 | C0 0.295, 0.347, 0.375 against reference 0.281, 0.377, 0.441: difference **-0.027, interval [-0.171, +0.117]** | contains 0 |
| 5.1-d Strike reach against the other lineages' Guards | same | C0 0.701, 0.768, 0.756 against reference 0.455, 0.699, 0.747: difference **+0.108, interval [-0.150, +0.366]** | contains 0 |
| Spread ratio (ours / reference, floored) | INCONCLUSIVE above 4.36 | 0.506 and 0.230 | below |

INFO (5.1-e): last-mover share 1.0 in each C0 lineage (reference 0.75, 1.0, 1.0); near-shutout share 0.875-0.938 (reference 0.875-1.0); generalist mean of C0's generation 7 Guards against its generation 8 Strikes 1.0 (outside the band [0.2, 0.8]; the reference value was 0.668 at 256 games, F5 criterion (b)).

## Verdict

**PASS**: the frozen 5.1 rule does not tell NUS's own code with new seeds apart from NUS's reference lineages. Stage 5.1 may be scored once N0 has failed as required (W16, done). Limits stated in the plan apply: three seeds a side catch only large differences; the reference lineages share initial weights among themselves (F16), C0's do not.

## Ledger

Row `T33` in `records/LEDGER.md` (run on the home RTX 5090 as workstation row W17 and renumbered at the merge into `main`).
