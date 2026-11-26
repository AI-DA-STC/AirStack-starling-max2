INTERNAL · the latest status of STE's own learning track and the NUS port, overwritten at every update by the `train-status` skill · [../README.md](../README.md); the history: [LOG.md](LOG.md)

**Status, 2026-11-27 03:52 (+08:00) (event: both teams PASS at seed 1; seed 2 running)** · RTX 5090 · GPU 2 % / 37 W / 0.8 of 32 GB · 0 training processes (0 paused)

**Main track:** route 3 (the learned-skills route), stage LS1 stopped on T94 (R49); redesign note done ([LS1_REDESIGN.md](../drafts/LS1_REDESIGN.md)); R50 pilot trials RUNNING (CPU only): Stage 0 done; Stage 2 seed 1 PASS on both teams (Guard S1 at R1 + R2; Strike S2 with sacrifice and converge at R3); seed 2 running · **Side track:** none

**Plain summary.** The redesigned copy (one small network per skill, seeing the world from its own drone's line to the zone) was trained on the CPU and replayed against the stored script games of T94, every test cell. **Guard team: PASS** (worst cell 25 changed games of the 30 allowed, median 3; T94: 64). **Strike team: PASS on its second try** (first try failed on sacrifice and converge; with the scripts' switch distances as inputs, R3, the worst cell is 16, median 3; T94: 122). Each team now repeats with a second training seed; the result is the worse of the two. Flank, the move that failed worst, passes with own-frame inputs alone. R3 for sacrifice and converge needs your ruling before any build (decision 2). Scratch trials, not of record.

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

| P1 | Stage 1: row-level fits (B, A3, A4, next rungs, control arms) | RUNNING: all B fits eligible; R3 cuts sacrifice 0.077 to 0.025 and converge 0.096 to 0.036; control arms: own-frame inputs matter on all four tested skills, the slow finish only on strike_high | tier 1 (CPU) | scratch |
| P2 | Stage 2: closed-loop replay of every gated cell | seed 1: Guard S1 PASS (max 25, median 3, 1 over 20); Strike S1 FAIL (sacrifice and converge command error, one cell 31), S2 PASS (max 16, median 3, 0 over 20); seed 2 running | tier 1 (CPU) | scratch |

GPU-h on route 3: 0.172 of 200 (`[budget_ls]`, R43).

## Other workstreams

| ID | Plain name | Status |
|---|---|---|
| — | Learner v2 note | NOT STARTED: after LS1 (R37) |
| NEAR-962 | Planned-pushes flight; the Crazyflie commanded gaps | unchanged from 24 Nov |

**Next.** The redesign note (inputs, network shape, fit schedule, the exact zero, and a scripts-plus-correction option), with pilot pass marks written before any trial; two reviewers; then CPU trials of every skill of both teams. One finding shapes it: moves that passed the command check (0.02 to 0.035) still changed up to 44 games in a cell, and the calibration puts the 30-game limit near a random error of 0.01 or a steady bias under 0.01, so the real target is near 0.01, not 0.05.

**Waiting on you.** Nothing tonight. The trials run on the CPU; a result that needs decisions 2, 3, 8, 9 or 10 waits for your morning read. Please leave the PC alone overnight (24 of 32 threads in use).

**Usage:** GPU 0.172 h on route 3 (LS1.1 and the probe). The redraw review: 2 Sonnet agents, 171k tokens, under 1 min. The diagnosis workflow: 5 agents, 859k tokens, 2.6 h (analyst, record writer, two reviewers, reviser). The M4 full suite took about 40 min of CPU. Advisor (Fable 5.2, advisor tool) once after the diagnosis. Checks: the docs check (13 PASS, 0 FAIL) and the document test set (151 passed, 2 skipped) for this docs-only commit.

**Ready to push.** 47 commits on `development` (up to this commit); mirror updated after the commit; push from GitHub Desktop. `main` unchanged.
