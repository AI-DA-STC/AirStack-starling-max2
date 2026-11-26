INTERNAL · the results of the LS1 redesign's CPU pilots (owner R50, 27 Nov 2026): Stage 0 checks, Stage 1 row-level fits, Stage 2 closed-loop replays of every gated cell at two seeds, and what they ask of the owner; scratch, INFO, not of record · reviewed by two reviewers (numbers, completeness), 27 Nov 2026, findings folded in · links: [LS1_REDESIGN.md](LS1_REDESIGN.md) (the plan and its marks, section 4), [README.md](README.md), [DISCUSSION R49, R50](../DISCUSSION_2026-11-19_20.md), evidence [records/evidence/2026-11-27_ste_ls1_redesign_pilots/](../../records/evidence/2026-11-27_ste_ls1_redesign_pilots/README.md)

# LS1 redesign: pilot results (27 Nov 2026)

Training simulator, tier 1 (fast engine, Starling layer), CPU only, 0 GPU-hours. Everything here is observed in the
training simulator; nothing was flown, and nothing here bears on flight. These are scratch pilots: not runs of record,
no ledger row. Every number comes from the scratch scripts, logs and JSON files saved in the evidence folder (linked
above); the marks are those of [LS1_REDESIGN.md](LS1_REDESIGN.md) section 4, fixed before the first trial and not
moved.

## 0. In plain words (for the owner)

- **Both teams pass the deciding read, at both training seeds** (observed in the training simulator, on LS1.1's
  data). The new student is one small network per skill that sees the world from its own drone's line to the zone. It
  played every gated test cell (Guard team 150, Strike team 130) against the stored script games of T94, 1,000 games
  each.
  - **Guard team: PASS.** At most 25 changed games in any cell (limit 30), median 3 to 4, one cell over 20. The old
    student (T94): 12 cells over 30, worst 64.
  - **Strike team: PASS on the second rung.** With own-frame inputs alone, flank, the move that failed worst in T94
    (the fixed flank × 3 cell changed 122 games; the worst Strike cell, a flank mix, 130), now passes. But sacrifice
    and converge were still too far off: one cell at 31 changed games, and command error 0.060 and 0.076 against
    0.05. With the scripts' switch distances added as inputs for those two moves (rung R3), the worst cell is 16 and 15
    at the two seeds, median 2 to 3, no cell over 20. The old student: 64 cells over 30.
- **What seems to matter, at row level.** Single-seed control arms that change one idea at a time suggest the own-frame
  inputs matter most: with raw inputs, flank's row error is 6 times worse and field's 7 times; strike_high copies well
  either way. The slow learning-rate finish helps strike_high and guard_field's state-dependent error, not flank or
  mirror. These are row-level reads, not closed-loop ones, and the raw-input arm changes the input and output frame
  together. Neither shared shape (a shared trunk with one head per skill, or today's one network with the skill code)
  fitted as well as a network per skill at row level, so neither qualifies and neither was replayed: the build stays
  one network per skill.
- **Two rulings are yours before any build (section 5):**
  - **decision 2**: sacrifice and converge need the scripts' switch distances (R3) as inputs. They are distances, not
    the scripts' decisions; the thresholds stay learnable.
  - **decision 8**: guard_field passes at R2, where the nearest-first list of Strike drones equals the script's own
    choice of which Strike drone to field against.
- **What a pass means.** It is a go for the build, not a prediction of the copy check of record: the pilot reused
  LS1.1's rows and seed; the build re-distils on its own data, and the read of record (LS1.2, with its controls C1 to
  C7) decides. **No limit moved.**

## 1. Stage 0: checks with no training

| Check | Result | What it shows |
|---|---|---|
| 0a harness | **PASS**: the saved LS1.1 networks reproduce T94 cell for cell in T94's own batches (44 on high,straight,high v mark_edge; 122 on flank × 3 v mirror; Guard 64 on mark_edge,mirror,parked_centre v converge; all 14 cells of those batches equal); the script oracle gives 0 changed games | the replay harness is trusted; every later replay uses it |
| 0b old network, slow finish + mask (INFO) | Guard: cells over 30 from 12 to 7, median 16 to 11; Strike: 64 to 59, median 29 to 27 | the schedule and the mask alone do not rescue the old shape |
| 0c blended switches | every switch skill passes at 3 cm or wider: flank passes 1 and 3 cm (worst 10, 16), fails 10 cm (47); field, sacrifice and converge pass up to 10 cm (worst 6, 12, 19; converge's 19 at 10 cm is one below the 20 of the width rule); every driver check at w = 0 gives 0 changed games | R3 is eligible for all four switch skills; R4 is not forecast for any |
| 0d script logic | closed forms rebuilt from the feature code equal the stored labels within 5e-5 on every held-out row of all 11 skills, about 800,000 rows per team (worst 4.9e-5, parked_ring, just under the mark); yaw, unused vz and parked_centre exactly 0 | the features compute the scripts' geometry exactly |
| 0d ONNX parity | **PASS** on all 33 (skill, rung) pairs: unfitted pilot networks with their features exported at opset 17; onnxruntime equals torch within 4.4e-7 on 100,000 rows per team; flags identical; masked channels 0 | the features survive export |
| 0e all allowed row errors at once (INFO) | Guard: 0 cells over 30 (worst 22, median 6); Strike: 6 cells over 30 (worst 39, median 13) | the Strike row marks are not jointly budgeted, as the redesign note foresaw; they decide nothing |

**How 0c's blend was built** (blend.py): each hard switch of the closed forms becomes a linear blend of the branch
commands over the margin width w; an angular margin is turned into an arc at the drone's radius; a "nearest drone"
choice becomes a soft choice with weights from the pairwise distance gaps; converge's rank order is blended between
the two orderings of its two non-reference drones. It reduces exactly to the scripts as w → 0 (checked on up to
100,000 own held-out rows per skill). The r6 tail marks it sets (round-0 own held-out rows, the widest passing width):
flank 3.07 %, field 1.57 %, sacrifice 2.09 %, converge 3.19 %.

**0e as run.** Four wrappers nested per slot as the plan's table sets (noise on active channels, bias, turn 0.5°, scale
0.99; parked_centre unwrapped), noise seed 150101 + cell index × 3 + slot. The realised RMSE, bias, turn and scale of
the flown commands were not computed; the configured sizes are what is reported.

**Code faults found and fixed in 0d before any fit** (a fault is not a design result, 4.5): a boolean `Where` with no
onnxruntime kernel; exact ties in the nearest-first order (a ring of Guard drones seen from one of them puts two
team-mates at the same distance, broken by roundoff, differently in onnxruntime; distances are now ranked at 1 mm
resolution, ties by slot); onnxruntime's atan2 giving −π where torch gives +π (sacrifice's bearing flags now come
from the signs of float64 cross and dot products). Before the first fit the common features also gained the slot
one-hot, which the design keeps (3.4) and the first draft of the scratch code had left out. The Guard C4 analogue (an
unfitted network) played before the tie fix; the tie order changes nothing its mark reads.

## 2. Stage 1: row-level fits

Every fit: 3x128 per skill, 40,000 steps, batch 8,192, Adam with 2 % warm-up and cosine 1e-3 to 1e-5, own-row weight
2, mask from the labels, fit seed 150003 (seed 2: 151003), 1,000,000 training rows from round 0 and 1,000,000 from
round 3 of games with `game % 5 != 0`. Marks read on the skill's own held-out rows (`game % 5 == 0`), rounds 0 / 3.
r7 is the total RMSE per active channel (largest shown); the eligibility screen is r7 on pooled rounds 0 and 3
(eligible at ≤ 0.10).

| Skill | Old network (LS1.1, own rows r0 / r3) | B: R1 + R2 | R3 | R4 (reported) |
|---|---|---|---|---|
| strike_straight | 0.014 | 0.0000 | — | — |
| strike_flank | 0.21 / 0.25 | 0.028 / 0.023 | 0.0248 (screen; no gain) | 0.0001 |
| strike_high | 0.025 | 0.0009 / 0.0009 | 0.0002 (screen) | — |
| strike_low | 0.023 / 0.024 | 0.0019 / 0.0028 | 0.0002 (screen) | — |
| strike_sacrifice | 0.17 / 0.22 | 0.070 / 0.087 | **0.021 / 0.029** | 0.0004 |
| strike_converge | 0.14 / 0.15 | 0.086 / 0.104 | **0.032 / 0.040** | 0.0011 |
| guard_parked_ring | 0.038 / 0.043 | 0.010 / 0.011 | — | 0.0016 (screen) |
| guard_mark_edge | 0.024 / 0.025 | 0.007 / 0.010 | — | 0.0007 (screen) |
| guard_mirror | 0.037 / 0.038 | 0.023 / 0.025 | — | 0.0013 (screen) |
| guard_field | 0.074 / 0.107 | 0.011 / 0.025 | 0.0194 (screen; no gain) | 0.0003 (screen) |
| guard_parked_centre | 0.0068 | exactly 0 (mask) | — | — |

The old network's column is 0b's "saved" own-row RMSE over 4 channels. Every B fit is eligible, so no Retry was
triggered. Seed 2 repeats seed 1 closely on every refitted skill (screens within 0.004). R4 fits copy almost exactly,
as expected when the network is handed the scripts' decisions; no passing assembly uses them.

**Row marks of the deciding fits** (reported; they decide nothing, 4.3): met in full by guard_parked_ring,
guard_mark_edge, guard_field, strike_straight, strike_high, strike_low and strike_sacrifice (R3). Missed: guard_mirror
r5 0.023 / 0.025 (mark 0.015) and r6 0.9 % / 1.2 % (mark 0.2 %); strike_flank r5 0.013 / 0.014 (mark 0.010);
strike_converge (R3) r5 0.017 / 0.021 (mark 0.010) and r7 0.032 / 0.040 (mark 0.030). Seed 2's mark_edge r5 is
0.016 in round 3 (mark 0.015). At R2, sacrifice and converge also missed r4 (scale 0.988 and 0.982). All of these
skills pass closed loop: the row marks are stricter than the read, as the note expected for the Guard team.

**Control arms** (one idea at a time, single seed, row-level evidence that decides nothing). The 4.3 rule: an arm
matches B on a skill if its pooled R5 and R7 are each at most max(1.2 × B's, B's + 0.002) and it meets r2 and r3
wherever B does; counted only where B's R7 ≤ 0.030 (it is on all four skills).

| Skill | B (R5 / R7) | C-in: raw inputs, world frame | C-lr: constant lr | C-head: shared trunk, head per skill | C-one: one network, skill code |
|---|---|---|---|---|---|
| strike_high | 0.0009 / 0.0009 | 0.0025 / 0.0025: **matches** (inside the 0.002 floor) | 0.0048 / 0.0049: misses | 0.0084 / 0.0084: misses | 0.0115 / 0.0116: misses |
| strike_flank | 0.013 / 0.024 | 0.139 / 0.152: misses (not eligible) | 0.014 / 0.024: matches | 0.017 / 0.032: misses (ratio 1.3, marginal) | 0.021 / 0.041: misses (ratio 1.6 to 1.7) |
| guard_mirror | 0.024 / 0.024 | 0.046 / 0.046: misses | 0.019 / 0.019: matches | 0.022 / 0.022: matches | 0.033 / 0.033: misses (ratio 1.3) |
| guard_field | 0.0021 / 0.019 | 0.121 / 0.138: misses (not eligible) | 0.0048 / 0.020: misses (R5 about 2 times) | 0.0069 / 0.020: misses (R5 about 3 times) | 0.0096 / 0.022: misses (R5 about 5 times) |

Pre-declared consequences (4.3):
- C-in matches B on both skills of neither team (Strike: matches on high, misses on flank), so the own-frame inputs are
  not reported as unneeded; the frames are confounded in this arm (input and output change together).
- C-lr matches B on both skills of neither team (Strike: misses on high; Guard: misses on field), so the decaying
  schedule is not reported as unneeded; its misses on high and field are support for it.
- C-head misses on both Strike skills and on guard_field: it qualifies on neither team.
- C-one (one shared network with the skill code, today's shape) misses on all four skills: it qualifies on neither
  team. On the skills outside the comparison its screens are also worse than C-head's (sacrifice 0.094, converge 0.118
  at R1 + R2, against 0.083 and 0.103).
- **S-shared does not play on either team: the build's shape is one network per skill**, as the pilot flew it.

**Forward time** (the plan's Stage 1 measurement): the passing assemblies, features included, every code for every
drone row, 6 threads, measured while 4 to 5 other pilot jobs shared the CPU: Guard 83 ms per 3,000 rows and 889 ms per
49,152 rows; Strike 83 ms and 1,090 ms. Head training (LS1.4) runs on the GPU, where the build's smoke measures it
(5.2 of the redesign note).

## 3. Stage 2: the deciding read

Full replay of every gated cell, 1,000 games a cell on T44's starts, paired with T94's stored script games, command
errors from the read's own labeller, R48's limits from the gate file, headroom marks median ≤ 9 and at most 5 cells
over 20. Screen first: `cells_screen.json`, written before any Stage 2 play, holds the union of T94's 10 worst network
cells and the T90 bias 0.01 (Guard) or noise 0.05 (Strike) arm's 10 worst: 14 Guard and 19 Strike cells (the two lists
overlap). The batches holding a screen cell were played first, whole, in T94's batch layout; no screen stop happened.

| Replay | Assembly | Result | Over 30 | Worst | Median | Over 20 | Pooled interval | Failures |
|---|---|---|---|---|---|---|---|---|
| Guard S1, seed 1 | every skill R1 + R2 | **PASS** | 0 | 25 | 3 | 1 | [−0.0005, +0.0003] | 0 |
| Guard S1, seed 2 | same, fit seed 151003 | **PASS** | 0 | 24 | 4 | 1 | [−0.0006, +0.0002] | 0 |
| Strike S1, seed 1 | every skill R1 + R2 | FAIL | 1 | 31 | 3 | 3 | [+0.0008, +0.0018] | sacrifice vx, vy RMSE 0.060, 0.060; converge vx, vy 0.076, 0.075; converge × 3 v mirror 31 games |
| Strike S2, seed 1 | sacrifice, converge at R3; others R1 + R2 | **PASS** | 0 | 16 | 3 | 0 | [+0.0005, +0.0015] | 0 |
| Strike S2, seed 2 | same, fit seed 151003 | **PASS** | 0 | 15 | 2 | 0 | [+0.0004, +0.0013] | 0 |

Strike S1's trigger set (4.4) was {sacrifice, converge}; S2 moved each to its lowest eligible fitted rung above R2,
which is R3. Command error in the passing replays (largest active channel): Guard mirror 0.025 to 0.026, field 0.010,
mark_edge 0.007, parked_ring 0.002, parked_centre exactly 0; Strike converge 0.031 to 0.032, flank 0.027 to 0.028,
sacrifice 0.021, low 0.002, high 0.0007, straight 0.0000. The worst Guard cell is mirror,mirror,parked_centre v
converge (25, 24; the same cell was 54 in T94, whose worst Guard cell, 64, is now 18 or less); the worst Strike cells
are converge × 3 (16, 15). The 26 Strike INFO cells (guard_mark_inside): worst 24 and 23.

**C4 analogue** (an unfitted R2 pilot network, all-ones mask, the 30 fixed gated cells): Guard 30 of 30 miss, Strike
28 of 30 miss (mark: at least 15 each): **PASS** on both teams. As 4.4 sets, it is the only one of the read's controls
the pilot runs; C3, C5, C6 and C7 for per-skill networks are deferred to the build's read of record.

**onnxruntime-flown arm (INFO):** the exported Guard assembly flew its 14 screen cells with 0 games different from the
torch-flown assembly in every cell; the Strike assembly flew its 19 screen cells with 0 games different too. No
investigation is due (the mark is more than 3 in any cell).

**Team results (4.4, the worse of two seeds):** Guard **PASS**, deciding assembly S1. Strike **PASS**, deciding
assembly S2. **The pilot's result: PASS** (both teams).

## 4. Finished after the first draft

- The pre-declared Stage 1 fits the ladder did not need, reported only, are in the section 2 table: R3 for flank and
  field gives no gain over R1 + R2; R4 for mark_edge, mirror and parked_ring copies almost exactly, 0.0007 to 0.0016.
- C-one (one shared network per team, today's shape) finished: Strike 9,990 s, Guard 8,666 s (2.8 h and 2.4 h against
  the note's 40 to 80 min; likely because it labels every row with every code, on average 0.22 to 0.25 s a step with other jobs on the CPU).
  It misses B on all four counted skills (section 2), so it qualifies on neither team and S-shared does not play.
  Nothing is still running; the pilot is complete.

## 5. What this asks of the owner (4.5 and section 7 of the redesign note)

| # | Decision | Why it is asked now | Lead's recommendation |
|---|---|---|---|
| 2 | R3 for strike_sacrifice and strike_converge: the scripts' switch distances (bearing margins, gather and commit margins, the pace terms) as network inputs | Strike passes only with them (S1 FAIL at R1 + R2, S2 PASS at both seeds) | accept: they are distances, the thresholds stay learnable, and LS2 can move them |
| 8 | guard_field at R2: its nearest-first list of Strike drones equals the script's own choice of whom to field | Guard passes at R2 with it | accept, reported as a script choice for that one skill; if declined, the R1-only refit of 4.5 |
| — | the build (section 5 of the redesign note) | the pilot passed on both teams | approve after 2 and 8; the build re-distils on its own DAgger rows and the read of record decides |

Decisions 3 (R4), 6 (MARGINAL), 7 (residual), 9 (one team) and 10 (second round) are not triggered.

## 6. Cost

CPU only, 0 GPU-hours, on the RTX 5090 machine's CPU. Stage 0 to the last deciding replay ran from about 01:50 to
04:40 on 27 Nov 2026, up to 4 jobs at 6 threads side by side; after 04:40 the dispatcher's job count missed two jobs
(the onnxruntime arms), so up to 6 ran at once until it was fixed at about 05:30. Fits that ran before 04:40 took 7 to
12 min each (55 to 97 steps per second); fits that overlapped more jobs ran slower (21 to 23 min). A full replay took
21 to 25 min per team (screen 9 to 13 min). The two C-one fits started at 04:36 and 04:37 and ended at 07:22
(Strike) and 07:02 (Guard). The scratch code was written while the jobs ran.

## 7. Method notes and limits

- Rows are LS1.1's (rounds 0 and 3) and the replays use T94's stored games; the build collects its own rows. Headroom is
  the buffer for that shift; both teams meet it with room (median 2 to 4 against 9; at most 1 cell over 20 against 5).
- The match calls pool rounds 0 and 3 per channel by row count. The C-head miss on flank (ratio 1.3) is marginal; its
  misses on strike_high (9 times) and guard_field's R5 (3 times) are wide.
- The control arms ran at one seed; the seed spread on the refitted skills (screens within 0.004) is the only guide to
  how much of a ratio is noise.
- The pilots read only LS1.1's data and T94's stored games; nothing in the repository or in T94's folders was written
  while they ran. The scratch code and outputs are copied to the evidence folder afterwards; the networks themselves
  (9.6 MB) stay in `runs/2026-11-27_ste_ls1r_pilots_scratch/` (not in git).
