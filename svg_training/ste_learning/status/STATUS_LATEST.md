INTERNAL · the latest status of STE's own learning track and the NUS port, overwritten at every update by the `train-status` skill · [../README.md](../README.md); the history: [LOG.md](LOG.md)

**Status, 2026-11-27 07:25 (+08:00) (event: last pilot job done, C-one does not qualify; the pilot is complete; owner decisions 2 and 8 needed)** · RTX 5090 · GPU 1 % / 32 W / 0.9 of 32 GB · 0 training processes (0 paused)

**Main track:** route 3 (the learned-skills route), stage LS1 stopped on T94 (R49); redesign note done ([LS1_REDESIGN.md](../drafts/LS1_REDESIGN.md)); R50 pilot trials: **PASS on both teams at two seeds** (Guard S1 at R1 + R2; Strike S2 with sacrifice and converge at R3); results note [LS1_REDESIGN_PILOT_RESULTS.md](../drafts/LS1_REDESIGN_PILOT_RESULTS.md), two reviewers; pilot complete (C-one, the last job, does not qualify: the build stays one network per skill) · **Side track:** none

**Plain summary.** The redesigned copy (one small network per skill, seeing the world from its own drone's line to the zone) was trained on the CPU and replayed against T94's stored script games in every test cell, 1,000 games each, at two training seeds. **Guard team: PASS** (worst cell 25 and 24 changed games of the 30 allowed, median 3 to 4; T94: worst 64, 12 cells over 30). **Strike team: PASS** with the scripts' switch distances (R3) as inputs for sacrifice and converge (worst 16 and 15, median 2 to 3; T94: worst 130, 64 cells over 30); with own-frame inputs alone it missed by one cell (31) and two command errors. Flank, the worst move in T94, passes with own-frame inputs alone. Observed in the training simulator, scratch pilots on LS1.1's data; a pass is a go for the build, and the build's own copy check decides. The last job, today's shape (one network for all skills), fitted worse than a network per skill on all four compared skills (row level, one seed, not replayed), so by the plan's rule the build keeps one network per skill.

## Watch

The route 3 flowchart, redrawn 26 Nov: LS1 stopped, the redesign's CPU trials below it (Stage 0 on hold).

![The five steps of route 3 with LS1 stopped and the LS1 redesign trials](../figures/ls_four_stages.png)

| The scripts fly flank | The LS1.1 network on the same start |
|---|---|
| ![Strike flank, scripts](../../records/evidence/2026-11-26_ste_ls1_fix_diagnosis/strike_strike_flank_g0_scripts.gif) | ![Strike flank, network](../../records/evidence/2026-11-26_ste_ls1_fix_diagnosis/strike_strike_flank_g0_net.gif) |

2-D top-down clips with the height panel, game 0 of LS1.1. Flank is the skill the network copies worst (0.33 command error against 0.05).

## Phases

| Phase | Status | Math library | Simulator | What |
|---|---|---|---|---|
| NUS port Phases 1–4 | DONE | JAX (NUS), PyTorch | NUS 2-D game (JAX); copy of NUS 2-D game (PyTorch); tier 1; tier 2 Isaac Lab | port, conversion, ladder rows |
| NUS port Phase 5 | PAUSED (5.1 FAIL T43) | PyTorch | tier 1 fast engine | route (b) stopped; STE Guard policy T41 kept |
| NUS port Phase 6 docs | DONE (passes 1, 2) | none | none | public docs |
| L0 Game definition | DONE (G0 ruled 22 Nov) | PyTorch | tier 1; tier 2 Isaac Lab | |
| L1 Drone model | DONE except L1.6 (waits on L1.3 + NEAR-962) | PyTorch | tier 1; tier 2; AirStack simulator (logs) | |
| L2 Game rules in training | DONE | PyTorch | tier 1; tier 2 Isaac Lab | |
| L3 Learner (two routes) | DONE | PyTorch | tier 1; tier 2 Isaac Lab (smoke) | |
| L4–L6 pipeline check | DONE, both routes PIPELINE WORKS (INFO) | PyTorch | tier 1 fast engine; tier 2 Isaac Lab (smoke) | 2.29 of 20 GPU-h |
| ▶ Route 3, LS1 Distil | STOPPED on T94 (NOT DISTILLED, both teams; R49); redesign being drafted | PyTorch | tier 1 fast engine | the scripts copied into a skill network per team |
| Route 3, LS1.4 Head training | BUILT (M4 merged), NOT STARTED: needs both teams DISTILLED | PyTorch | tier 1 fast engine | the heads trained on the skill network, both sides |
| Route 3, LS2, self-play, LS3 | NOT STARTED (each needs its design note) | PyTorch | tier 1 fast engine | order by R41 |
| L7–L9 | NOT STARTED | — | AirStack simulator; real flight | owner's gate |

## Route 3, stage LS1, task by task

| ID | Plain name | Status | Simulator | Result |
|---|---|---|---|---|
| M1–M4 | The build: skill network, calibration, distillation, copy check, export, head training | DONE, all four merged (full suite 3,425 passed at M4) | tier 1 (CPU tests) | `79a3e10c` |
| LS1.5 | Calibration read, then the top-up (owner R48) | DONE (T90, T91, INFO) | tier 1 (CPU) | limits set by the owner (R48) |
| LS1.0 | Smokes and the CUDA label probe | DONE (T92, INFO) | tier 1; GPU probe | labels bit-equal on CUDA |
| LS1.1 | Distillation, one skill network per team | DONE (T93, INFO) | tier 1 (GPU) | 0.172 of 0.8 GPU-h |
| LS1.2 | Copy check against the scripts | **NOT DISTILLED** both teams (T94); every control PASS | tier 1 (CPU) | Guard 18 limit failures, Strike 98 |
| — | Diagnosis and the fix-round proposal | DONE, two reviewers (numbers, reasoning) | CPU scratch pilots | [proposal](../drafts/LS1_FIX_ROUND_PROPOSAL.md), section 0b the lead's recommendation |
| LS1.1-fix, LS1.2-fix | The one fix round the stop rules allow (R47) | NOT SPENT (owner R49) | — | — |
| — | Redesign of the skill network: design note, pilot marks, two reviewers | DONE (`c1bebc9a`); rules fixed after the focused re-review (`6625cf82`) | none | [LS1_REDESIGN.md](../drafts/LS1_REDESIGN.md) |
| — | Route 3 flowcharts redrawn: LS1 stopped, the redesign trials (owner asked) | DONE, one review round (numbers: no finding; completeness: 1 blocker, 4 minor, all fixed) | none | [route page](../LEARNED_SKILLS_ROUTE.md) |
| P0 | Stage 0 of the pilots: harness check, de-bias and mask replay, blended-switch replay, ONNX check (no training) | DONE: 0a PASS (T94 reproduced cell for cell); 0c every switch skill passes at 3 cm or wider (flank widest 3 cm), R3 eligible for all four; 0d PASS after three code fixes (closed forms within 5e-5 on 0.8 M rows per team; ONNX parity on every skill and rung); 0b and 0e INFO (0e: Guard under 30, Strike 6 cells over 30) | tier 1 (CPU) | about 1.5 to 2 h one at a time, 0 GPU-h; decides whether a learnable copy can pass at all |

| P1 | Stage 1: row-level fits (B, A3, A4, next rungs, control arms) | DONE for the ladder (all B fits eligible; R3: sacrifice 0.077 to 0.025, converge 0.096 to 0.036); control arms by the 4.3 rule: own frame needed on flank, mirror, field; the slow finish on high and field; C-head and C-one qualify on neither team (C-one misses on all four skills), so S-shared does not play; reported-only fits done | tier 1 (CPU) | scratch |
| P2 | Stage 2: closed-loop replay of every gated cell | **PASS both teams, two seeds**: Guard S1 (25 / 24, median 3 / 4); Strike S1 FAIL (one cell 31, sacrifice and converge command error), S2 PASS (16 / 15, median 3 / 2); C4 analogue PASS both; onnxruntime arm 0 games different (both teams) | tier 1 (CPU) | [results](../drafts/LS1_REDESIGN_PILOT_RESULTS.md) |

GPU-h on route 3: 0.172 of 200 (`[budget_ls]`, R43).

## Other workstreams

| ID | Plain name | Status |
|---|---|---|
| — | Learner v2 note | NOT STARTED: after LS1 (R37) |
| NEAR-962 | Planned-pushes flight; the Crazyflie commanded gaps | unchanged from 24 Nov |

**Next.** Nothing runs; the scratch loops are stopped. On the owner's decisions 2 and 8: the build (redesign note section 5), which re-distils on its own DAgger rows; its copy check of record (LS1.2) decides.

**Waiting on you.** Decision 2 (R3 switch distances as inputs for strike_sacrifice and strike_converge; lead: accept) and decision 8 (guard_field at R2 gets its nearest Strike drone first, the script's own choice; lead: accept); then the build (redesign note section 5). The results note is [LS1_REDESIGN_PILOT_RESULTS.md](../drafts/LS1_REDESIGN_PILOT_RESULTS.md).

**Usage:** 0 GPU-h for the pilots (CPU only; route 3 still 0.172 GPU-h). Pilots 01:50 to 07:22: the deciding replays by 04:40, up to 4 jobs at 6 threads (6 at once after 04:40 until a dispatcher count bug was fixed at 05:30); the two C-one fits 04:36 to 07:02 and 07:22 (2.4 h and 2.8 h against 40 to 80 min estimated: every row labelled with every code). Reviews: two Sonnet agents for the results note (numbers 130k tokens, completeness 154k), findings folded in; one Sonnet agent for the C-one addition (a row-level read; matches never gate the build's shape). Checks: the docs check and the document test set for this docs-only commit.

**Ready to push.** 50 commits on `development` (up to this commit); mirror updated after the commit; push from GitHub Desktop. `main` unchanged.
