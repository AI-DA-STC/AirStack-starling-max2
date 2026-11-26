INTERNAL · the redesign note for route 3's skill network after LS1 stopped (owner R49, 26 Nov 2026): what failed and the real target, the designs considered, the chosen design, the CPU pilots with their pass marks fixed before any trial, the build that follows if they pass, and the owner's decisions; reviewed by two reviewers (numbers, completeness), 26 Nov 2026; written by the writer (Opus 5.5) from three scouts, three designs and a judge, revised after the review; nothing run of record · links: [README.md](README.md), [LS1_FIX_ROUND_PROPOSAL.md](LS1_FIX_ROUND_PROPOSAL.md) (the diagnosis), [LS1_TASK_PLAN.md](LS1_TASK_PLAN.md), [LS_EXECUTION_WORKFLOW.md](LS_EXECUTION_WORKFLOW.md), [LEARNED_SKILLS_BRIDGE_PLAN.md](LEARNED_SKILLS_BRIDGE_PLAN.md), [the route page](../LEARNED_SKILLS_ROUTE.md), [DISCUSSION R47 to R49](../DISCUSSION_2026-11-19_20.md), the gate file [distil_gates.toml](../../configs/ste_ls1/distil_gates.toml)

# LS1 redesign: a skill network that copies the scripts closely enough (reviewed, 26 Nov 2026)

Training simulator, tier 1 (fast engine, Starling layer); everything here is observed in the training simulator. Not
for flight. Numbers come from the run folders, records and scratch logs named beside them. Anything that is a projection
is labelled **estimate**. Numbers from the redesign scouts' scratch work carry the scratch file's name and the tag
"(scout scratch)": those files are saved in
[records/evidence/2026-11-26_ste_ls1_redesign_scouts/](../../records/evidence/2026-11-26_ste_ls1_redesign_scouts/README.md)
and were not re-run by the writer (section 8 says which numbers the writer re-checked).

**Review status (lead, 26 Nov 2026).** Sections 0 to 3, 4.1, 4.2 and 5 to 8 were reviewed by two reviewers. The rules
added by the reviser after that review (0e in 4.2, sections 4.3 to 4.6, decisions 8 to 10) were re-reviewed once by a
focused reviewer (26 Nov 2026) and fixed: the ladder, the second seeds, the DAgger rescue, every trigger and term, 0e
and the costs. A confirming check (26 Nov 2026) found 11 of the 12 findings resolved and one partly (the 1.2x match rule may sit inside seed noise): **the matches of 4.3 are evidence only and never gate the build's shape; only S-shared's closed-loop replay can choose a shared shape.** No blocker remains; the worst-case hours are a loose upper bound.

## 0. In plain words (for the owner)

- **Route 3's idea.** The hand-written scripts are the teacher; one network per team is the student. The student must
  copy every script so closely that a game it plays ends as the scripts' game ends. Training then goes on from it.
- **What went wrong (T94).** The student failed on both teams. Three Strike moves (flank, sacrifice, converge) are far
  off. Even the Strike moves that looked fine changed up to 44 games in a cell, against a limit of 30.
- **What that taught us.** The real bar is stricter than the 0.05 error limit: random error near 0.01 for the Strike
  team, and a steady lean below about 0.005 for the Guard team. The student's best Strike moves lean by about 0.02 and also wobble; together that broke the limit.
- **What changes (four ideas to test, not settled).** (1) Each drone sees the world from its own point of view, along
  its line to the zone. (2) Each move gets its own small network. (3) Study longer and slow down at the end. On a
  network that was already trained, a slow finish removed the steady lean; whether it does the same when training
  starts from scratch is not tested yet. (4) "Stay still" and unused controls are zero by design. That makes two of the
  five limits pass automatically, so those two then test the design, not the learning. (5) For the four moves with
  sudden switches, the student may also be told where the script's switch points are, or, last, which way the script
  decided.
- **What this changes on the route page.** The route's picture changes from one network per team that reads a skill
  code to one small network per skill, unless a trial shows that a shared network with one output head per skill does
  as well (that shape is tried too).
- **The trials (CPU only, no GPU).** 5 to 7 hours to write the trial code, then about 9 to 16.5 hours of runs one
  job at a time on 6 threads (up to about 29 in the worst case of the ladder and the rescue, a loose upper bound; the decision-8 fallback and a second redesign round would add to it); with up to 4 jobs side by side at 6 threads each
  while the owner is not using the PC, about 4 to 8.5 hours of wall clock (up to about 15) (all estimates). Every
  move of both teams is trained small. Separate small trials test the first three ideas one at a time (the fourth is
  true by design), on one smooth move and one switching move per team, so we learn which ideas actually help. Then
  the students play all 280 test cells against the stored script games, and that replay alone decides pass or fail.
- **What a trial pass means.** The trial reuses the earlier data, and a design counts as passing only if it passes
  with two training seeds. A pass is a go for the build, not a prediction: the real check is the copy check after the
  build.
- **After the trials (estimate).** 1.5 to 2.5 days of building, about 0.1 to 0.9 GPU-hours to distil again (as the
  ledger counts; 0.628 left under LS1.1's cap; the high end needs a higher cap, announced first), 40 to 85 minutes of
  CPU per team for the copy check.
- **You decide.** Before the trials: confirm the trial plan, its costs and its "headroom" marks. Headroom is the lead's
  own safety margin, stricter than your limit of 30 changed games, not one of your limits. After the trials: if the
  plain version passes, approve the build. If a move needs the script's switch points as inputs, that is more than
  "own point of view": accept or not. If a move needs the script's decisions as inputs, the network copies the script's
  motion but the decision logic is built into the exported network. For sacrifice and converge that makes this route
  close to the skills route for those two moves, and their switch points stay fixed until a later stage (LS2) can move
  them. If nothing passes, LS1 stays stopped and the other design (scripts plus a learned correction)
  comes to you. **No limit moves.**

## 1. What failed and the real target

### 1.1 The read of record

Copy check LS1.2, ledger row T94, runs `runs/2026-11-26_ste_ls12_read_{guard,strike}` (`results.json`); record
[2026-11-26_ste_ls1_distil_read_record.md](../../records/2026-11-26_ste_ls1_distil_read_record.md). Every control
passed; NOT DISTILLED on both teams. The diagnosis is [LS1_FIX_ROUND_PROPOSAL.md](LS1_FIX_ROUND_PROPOSAL.md) sections
1 to 4. The owner stopped LS1 and asked for a redesign (R49,
[DISCUSSION](../DISCUSSION_2026-11-19_20.md)): the fix round is not spent, the copy check, its limits and its controls
stay as R48 set them, and a new build gets new run folders and a new gate-file hash.

Counts below were tallied by the writer from the two `results.json` files (network arm, `flips` = b + c):

| Team | Gated cells | Median changed games | Largest | Cells over 30 | Cells over 20 |
|---|---|---|---|---|---|
| Guard team | 150 | 16 | 64 (mark_edge, mirror, parked_centre v strike_converge) | 12 | 50 |
| Strike team | 130 | 29 | 130 (flank, low, flank v guard_mirror) | 64 | 85 |

Controls in the same files: the oracle arm (the scripts written as a network) changed 0 games in all 150 and 130
cells; the unfitted network went over 30 in 30 of 30 Guard cells (largest 592) and 27 of 30 Strike cells (largest 569).

### 1.2 Lead finding (a), checked: the 30-game limit binds, not the 0.05 command limit

| Team | Cells made only of skills that passed the command check | Result (T94 `results.json`) |
|---|---|---|
| Strike team (straight 0.022/0.016, high 0.035/0.032, low 0.031/0.028) | 55 gated + 11 INFO | gated: median 18, largest 44, **4 over 30** (44 high,straight,high v guard_mark_edge; 41 high,straight,high v guard_mirror; 38 high,low,straight v guard_mirror; 34 high x3 v guard_mirror); INFO v guard_mark_inside: 2 over 30 (37, 35). Every cell over 30 holds strike_high. |
| Guard team (parked_ring, mark_edge) | 12 gated | median 17, largest 27 (parked_ring x3 v strike_flank), none over 30 |
| Guard team, with parked_centre added | 42 gated | largest 32 (parked_centre, parked_centre, mark_edge v strike_converge), 1 over 30 |

So finding (a) holds. The brief's "6 of 66" is confirmed, split as 4 gated plus 2 INFO cells (of 55 gated plus 11
INFO). The command check is not the binding limit: moves well inside 0.05 still break the 30-game limit.

### 1.3 The error budget per team and per kind of error

From the calibration read T90 (runs `runs/2026-11-25_ste_ls15_calibration_{guard,strike}`, record
[2026-11-26_ste_ls15_calibration_record.md](../../records/2026-11-26_ste_ls15_calibration_record.md), tables at its
lines 148 to 168), where the scripts played deliberately changed copies of themselves on the copy check's cells. Cell
counts over 20 were tallied by the writer from the two `results.json` files.

| Changed copy | Guard team: median / largest / cells over 20 / over 30 | Strike team: median / largest / over 20 / over 30 |
|---|---|---|
| identity | 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 |
| noise 0.01 (RMSE about 0.006) | 1 / 6 / 0 / 0 | 5 / 18 / 0 / 0 |
| noise 0.02 (RMSE about 0.011) | 3 / 11 / 0 / 0 | 8 / 27 / 3 / 0 |
| noise 0.05 (RMSE about 0.029) | 7.5 / 21 / 1 / 0 | 13 / 37 / 34 / 8 |
| bias 0.01 on x and y | 9 / **31** / 9 / 2 | 9 / 20 / 0 / 0 |
| bias 0.02 | 17 / 63 / 44 / 16 | 13 / 24 / 11 / 0 |
| parked-skill bias 0.005 (6 cells) | 5.5 / 15 / 0 / 0 | not applicable |
| turn 1.5° (RMSE about 0.019) | 9 / **34** / 17 / 2 | 10 / 21 / 2 / 0 |
| scale 0.95 | 17 / 49 / 57 / 19; 6 cells outside the cell margin | 17 / 43 / 58 / 31; pooled [−0.0113, −0.0080] fails ±0.01 |
| moved switches (sacrifice entry, converge gather, flank margin 0.35/0.4) | not applicable | largest 12 to 30 at RMSE 0.13 to 0.23; flank 15 / 20 |

What this says (rungs are tested; anything between rungs is an **estimate**):

| Team | Steady bias per xy channel | Steady turn | Speed scale | Random (state-dependent) error |
|---|---|---|---|---|
| Guard team | fails at 0.01 (31), 63 at 0.02: a straight line through the two rungs crosses 30 near 0.0097; budget about **0.003 to 0.005**, a 2x safety factor (the lead's choice, for mixed error) | fails at 1.5° (34): budget about **1°** | fails at 0.95: budget within about **2 to 3 %** | passes up to RMSE 0.029 (21) |
| Strike team | passes 0.02 (24): budget about **0.005 to 0.02** | passes 1.5° (21) | fails at 0.95 (pooled): within about **2 to 3 %** | fails at RMSE 0.028 (37), passes 0.011 (27): budget about **0.010** |

Three cautions, all from the targets scout (scout scratch `a_calib.out`, `c_predict.out`, `d_rank.out`):

- **The 30 is a sensitivity bound, not noise.** The identity arm changes 0 games; games are deterministic on T44's
  starts. The limit is the largest over 130 to 150 cells, so in practice a cell median of about 9 or less is needed
  (estimate from the rungs above).
- **Real network error is worse than any single kind.** On the same 55 Strike cells the network reached 44, more than
  noise at RMSE 0.028 (37) or bias 0.02 (24). Mixed error and opponent amplification (guard_mirror most) add up.
- **Row error predicts changed games poorly.** Within passing-only cells the rank correlation of open-loop RMSE with
  changed games is 0.19 (Strike team) and 0.29 (Guard team); the ten worst cells overlap only 1 to 7 of 10 between kinds
  of error. Only a closed-loop replay of every cell decides.

### 1.4 What the best moves' error is made of

Scout scratch `g_ownrows.out`, `e_decomp.out` (saved LS1.1 networks, each skill on its own flown rows of round 3):

| Skill | Steady bias (x, y) | Bias share of the squared error | RMSE per channel |
|---|---|---|---|
| strike_high | (+0.019, +0.015) | 0.28 | 0.032 |
| strike_straight | (+0.016, +0.004) | 0.37 | 0.0195 |
| strike_low | (+0.014, +0.003) | 0.10 | 0.032 |
| guard_parked_centre | (+0.0085, +0.0051) | 0.73 | 0.0082 |
| guard_mirror | (+0.004, −0.010) | 0.02 | 0.054 |
| guard_mark_edge | (+0.004, −0.002) | 0.006 | 0.035 |

strike_high's bias is almost exactly the calibration's bias-0.02 rung, and strike_high is in every passing-only Strike
cell over 30. Turn and scale on the passing skills are not steady (mean signed angle within ±0.1°, speed ratio 0.996 to
1.001).

### 1.5 Lead finding (b): the constant yaw offset

- **Checked in the code:** the fit's loss covers every code and every channel, unclipped
  ([distil.py](../../source/svg_training/ste/distil.py) `fit`, `mse_loss` over `_flat_codes`, constant-rate Adam). So
  guard_parked_centre is trained.
- **Experiment (scout scratch `b_lrtail.py`, `b_guard.log`, `b_strike.log`):** a copy of the saved network given a
  fresh Adam tail at lr 1e-4 loses the Guard yaw offset (+0.0070 → 0.0000) within 100 to 300 steps; constant lr 1e-3
  grows new offsets back by 1,000 to 2,000 steps (vz 0.0146 on parked_centre). After a 300-step tail, |bias| is 0.0008
  to 0.0044 on every skill except Guard field (0.0056) and Strike sacrifice (0.012).
- **Not enough on its own:** after every tail, parked_centre stays at p99 0.014, largest about 0.07, with 31 % of rows
  above 0.005; on each skill's own flown rows (`g_ownrows.out`), strike_high and strike_low stay at 0.026 and 0.028 per
  channel (from 0.032 and 0.032), the level of the failing Strike noise rung. Over all rows the same tail gives about
  0.016 (high 0.0229 → 0.0159, low 0.0242 → 0.0156; `f_tailbias.out`, `b_strike.log`). Own rows are the harder set,
  and the pilot's row marks are read on own rows.
- **Unexplained:** the offsets appear on all five Guard skills (+0.0071 ring, −0.0012 mark, −0.0033 mirror, +0.0060
  field) and not on the Strike team's (about 1e-5). Why only the Guard team is not known.
- **Untested:** whether a from-scratch fit with a decaying rate behaves like these tails on an already-trained network.

### 1.6 Why the switch moves are hard (geometry scout)

Scout scratch `geo.py`, `out_jitter.log`, `out_frames.log`, `out_closed.log`, on 300,000 rows of round 0, 3v3, zone at
the arena centre:

- The labels of flank, field, sacrifice and converge **jump** in the 71 inputs: flank's side choice by about 1.19,
  field's nearest Strike drone by about 1.6, sacrifice's go-in edge by about 1.35, converge's committed switch by about
  1.55 (medians). With every script choice held fixed, a jiggle of the inputs moves the labels by (RMS per channel
  over 3 channels, the zero yaw channel included, `out_jitter.log` "choices held"): at 10 mm, parked_ring 0.0525,
  mirror 0.0216, converge 0.0169, sacrifice 0.0045, field 0.0044, mark_edge 0.0032, flank 0.0024 (straight 0.0023,
  high 0.0123, low 0.0094 with no choices); at 1 mm, parked_ring 0.0106, mirror 0.0022, converge 0.0017, mark_edge
  0.0003. parked_ring and mirror have a steep gain (about 4 per metre, from the 0.25 m steer ramp); converge's comes
  from its pace ratio.
- For RMSE 0.01 a smooth network fed continuous inputs must make each switch within about 1.4 to 4.8 mm; for 0.05,
  36 to 120 mm (first-order estimate, one switch at a time).
- In the drone's own zone-line frame, strike_straight is `(min(1, ρ/STEER_RAMP_M), 0)` (the constant (1, 0) beyond
  0.25 m from the zone centre); high/low are that xy scaled by `sqrt(1 − v_t²)` plus the vertical command `v_t`, which
  depends on height alone.
- Every one of the 11 scripts is reproduced by short closed forms in a frame, given the script's own choices and flags,
  within 1.9e-5 (parked_ring) and at most 8.8e-6 for the others.
- Yaw is exactly 0 for all 11 skills; vz is 0 for 9 (used only by high and low with the Starling layer on);
  guard_parked_centre is all-zero at a team size of 2 or more.

## 2. Options considered

Three designs were written against the evidence in section 1 and scored by a judge (1 to 10, higher is better).

| Design | In one line | Chance to pass | Route 3 fit | Build cost and risk | Pilot as a go/no-go |
|---|---|---|---|---|---|
| **Faithful** | one small network per skill, own-frame and per-skill inputs on a ladder R1 → R4, outputs in each skill's frame, a built-in zero, a decaying fit | 6 | 7 at R1; toward 5 at R4 | 6 | 7 |
| **Fidelity** | one expert per skill on the script's frames, flags and chosen drones (R4), one head per script branch, sign reflection, EMA and a bias polish | 7 | 5 | 4 | 8 |
| **Residual** | the scripts plus a learned correction that starts at zero; nothing is distilled | 9, conditional | 3 | 6 | 5 |

**Why not the residual now.** With a zero correction the network equals the scripts, so it passes by construction (T94's
oracle arm: 0 changed games in every cell). But the unfitted-network control C4 is
[distil.py](../../source/svg_training/ste/distil.py) `initial_net`, which would then equal the scripts, cannot miss 15
cells, and makes the read INCONCLUSIVE as the gate stands; R49 keeps the controls. It also changes what route 3 is: the
route page has the scripts "only as teachers" and an export "with no port of the scripts into the flight software"
([route page](../LEARNED_SKILLS_ROUTE.md) lines 59 and 93), and the scripts do not export as written (Guard fails at
`Sort`, onnxruntime refuses the Strike graph's `EyeLike`; contract scout, scout scratch `onnx_check.py`). Head training
would reproduce route 2. It stays the documented fallback (section 6.5), with its own ruling.

**Why not Fidelity as written.** Its structure freezes every script decision into the inputs from the start, its
features duplicate about 350 lines of the scripts' logic, it reads one path on the CPU and another on the GPU, and two
of its claims do not hold: a constant per-branch offset does not remove turn or scale where the command is not constant,
and its "separate experts cost little" holds only for a routed CPU path (run-all-then-pick measured about 6 times
today's forward, 13.2 against 2.2 ms per 3,000 rows; scout scratch `fwd_variants.py`).

**The chosen design: the judge's combination.** Faithful's design and ladder, built and piloted with Fidelity's harness
and marks, and three of the residual's ideas (a sort-free rewrite of the script logic the features need, export-parity
marks at switch margins, an onnxruntime-flown INFO arm). The plain version (R1 + R2, inside R49's four directions) is
tried on every skill. Script margins (R3) and script choices (R4) are tried on the four switch skills, and the next
rung of each smooth skill that has one is fitted too (R3 for high and low; R4 for mark_edge, mirror and ring), so the
closed-loop ladder of 4.4 can move it. The build takes the rungs of the assembly that passes the closed-loop read,
lowest rungs first. R4 is
compared with the residual design on the same criteria in 6.4.

## 3. The chosen design: LS1-R, per-skill networks in each skill's frame

### 3.1 What stays the same

- **The contract** ([skill_net.py](../../source/svg_training/ste/skill_net.py) `SkillNet.forward`):
  `forward(obs[B,71], slot[B], z[B], clip=True) -> [B,4]`, clamped to [−1, 1] when `clip`, then multiplied by
  `obs[:,12]` (alive); attributes `team`, `skills`, `k`, `team_size`, `slot_width`, `zeroed_inputs`; `one_code` and
  `all_codes` keep their signatures. So [skills.py](../../source/svg_training/ste/skills.py), the exploit and head-training
  code, and the read, unseen, l012 and ceiling scripts do not change (contract scout).
- **The scripts** ([scripted.py](../../source/svg_training/opponents/scripted.py)) and their sha pin `b7ccafde…`.
- **The copy check LS1.2**: the cells (`configs/ste_ls1/cells.toml`), 1,000 games per cell on T44's starts, every R48
  limit and control number (C1 to C7), the interval, the correction, the pooled row.
- **Collection and DAgger**: 4 rounds at script share [1, 0.5, 0.25, 0], 4,096 games × 600 ticks, 2,000,000 kept rows
  a round, error-weighted, the absent quota and the switch floor; the label control at `label_check_atol` 1e-5.
- **The inputs the network never reads**: 6, 7, 10, 11 (yaw sine and cosine, time left, team flag).

### 3.2 Notation

`p = obs[0:2]` (own xy from the zone centre), `z = obs[2]`, `v = obs[3:5]`, `ρ = |p|`. Slot k (0 to 7) has base
`b_k = 13 + 7k`: `q_k = obs[b_k : b_k+2]` (relative xy), `u_k = obs[b_k+3 : b_k+5]` (relative velocity),
`π_k = obs[b_k+6] > 0.5` (present). Guard slots are k = 0 to 4, Strike slots 5 to 7. `perp(x) = (−x_y, x_x)`.
`steer(d) = unit(d)·min(1, |d|/STEER_RAMP_M)`.

### 3.3 Inputs: a ladder of rungs, computed inside the network

A new module `source/svg_training/ste/skill_features.py` computes the inputs from `obs` and `slot`, row by row. Rules:
pure tensor operations; no `torch.sort` and no `torch.eye` (both stop the ONNX export today); ranks by pairwise
comparison counts; "nearest" by masked minimum and gather; never reads 6, 7, 10 or 11 (a test perturbs them and asserts
bit-equal features); no script number is retyped. They come from three places: module constants of
[scripted.py](../../source/svg_training/opponents/scripted.py) (`STEER_RAMP_M`, `STAND_OFF_M`, `RUN_IN_COMMIT_M`,
`GATHER_ANGLE_RAD`, `CIRCLE_UNTIL_RAD`, `ENTRY_HALF_ANGLE_RAD`, `PARK_RING_M`, `FIELD_RANGE_M`, `BAND_INSET_M`, …);
class attributes of the script classes (flank's `MARGIN_M` 0.3, mirror's `RING` 1.2); and the game config the
scripts read through `cfg` (flank's corridor `rules.keepout_strike_m + MARGIN_M` = 1.4, the height band that sets
high/low's target heights, `team_speed_mps("guard")`, `rules.keepout_guard_m`), or obs 8, 9, 69, 70. The features take
`cfg` at construction, as `load_skill_net` and `initial_net` already receive it, and the network file already pins the
game file, its sha and the game constants (contract scout); a test asserts each feature constant is the script's own
object. New numbers are UPPER_CASE module constants (`tests/test_ste_literals.py`).

Each rung adds to the one below. **Which rungs carry a script's choice is marked**, because those go beyond "each
drone's own point of view" (R49) and need the owner's ruling before a build (section 7).

| Rung | Adds | Carries a script choice? |
|---|---|---|
| **R1** own frame | the zone-line frame `e1 = h = −p/max(ρ, EPS)`, `e2 = s = perp(h)`; `ρ`, `z`, own velocity in the frame `(v·h, v·s)`, own vz; for every other slot in **slot order**: `(a_k, o_k) = (q_k·h, q_k·s)`, `d_k = |q_k|`, `π_k`, velocity `(u_k·h, u_k·s)`; team-mates also as `ρ_j = |p + q_j|` and the relative bearing `β_j` as (cos, sin), taken from the dot and cross products of `unit(p + q_j)` with `unit(p)` (no atan2 at R1 and R2); an absent drone as `(a, o, d) = (−ABSENT_FAR, 0, ABSENT_FAR)`, `ABSENT_FAR = 10`, `π = 0` (today an absent drone reads as zeros, "sitting on top of me"; the script itself drops it by its present flag, but zeros put the entity on the in-way boundary of flank's corridor test, and the placeholder keeps the feature away from that margin); the raw 71 normalised inputs (zeroed 6, 7, 10, 11) are kept | no |
| **R2** order | the same entities also listed **nearest first** (Guard drones and Strike drones separately, absent last) | generic ordering; **for guard_field it equals the script's choice** (nearest Strike drone), so a field pass at R2 is reported as such |
| **R3** script margins | per skill, the script's continuous distances to each switch (below); thresholds stay learnable | uses the scripts' switch geometry; no decision |
| **R4** script choices | per skill, the script's on/off flags and chosen drone (below); one output head per script branch, gated by the flag; side reflection by the script's side sign | **yes: the network is handed the script's decisions** |

Per-skill blocks (R3, then R4; formulas from the geometry scout, verified by its closed forms):

| Skill | R3 (margins, continuous) | R4 (choices, flags, branch heads) |
|---|---|---|
| strike_straight | none | none |
| strike_high, strike_low | `v_t = clamp((t − z)/STEER_RAMP_M, −1, 1)` with t the script's target height, and `sqrt(1 − v_t²)` (removes the cusp) | none |
| strike_flank | per Guard `m_k = min(a_k, ρ − a_k, 1.4 − |o_k|)` if `π_k`, `m_k = −ABSENT_FAR` if not (in the way iff `m_k > 0`; an absent drone sits far from the margin, as the script's `pres` test intends) and signed `o_k` | `blocked`; `k* = argmin` over in-way Guards of `d_k`; `(a*, |o*|)`; `sign* = (o* ≥ 0 ? +1 : −1)`; heads: free, blocked; side output reflected by `sign*` |
| strike_sacrifice | decoy flag (slot 0); nearest Guard `n` in the frame; drawn Guard `g = argmin_k |p + q_k − P_0|`; `Δs = wrap(atan2(−away) − θ_own)`; margins `|Δs| − π/6` and `π − |Δs|`; `rad = clamp(R − ρ, −1, 1)` with stand-off `R = min(r + STAND_OFF_M, A − 0.25 − max|c|)` | `active`, `go_in`, `dir`; heads: inactive, decoy, go_in, circle; reflected by `dir` |
| strike_converge | unwrapped `D` and `wrap(D)`; `max_live|err_j| − GATHER_ANGLE_RAD`; `min_live ρ_j − (R − RUN_IN_COMMIT_M)`; pace numerator and denominator; `n_live` | `gathered`, `committed`, `go`, `circle = |wrap D| > CIRCLE_UNTIL_RAD`, `n_live ≥ 2`; heads: n_live < 2, go, circle, steer; reflected by `sign D` |
| guard_field | push vector over mates within `FIELD_RANGE_M`; nearest-pair margin `(d2 − d1)/2` over present Strike drones | nearest Strike drone `n`; its frame `e_n = unit(p + q_n)`; `(r − p·e_n, −p·t_n)`; output in the `e_n` frame |
| guard_mark_edge, guard_mirror | none beyond R1 + R2 | the marked Strike drone `m` = the `(i mod n_S)`-th present Strike slot; `SP = p + q_m`, `e = unit(SP)`, `t = perp(e)`; mark_edge `(r − p·e, −p·t)`; mirror `(RING·r − p·e, −p·t)` with mirror's `RING` = 1.2 (class attribute), plus `SV·t / guard_speed` with `SV = v + u_m`, and the script's final clamp `a / max(1, |a|)` on `steer(…) + SV_t / guard_speed`; output in the `(e, t)` frame |
| guard_parked_ring | none beyond R1 + R2 | whole-team flag; station angle φ as (cos, sin) (ranks by pairwise counts; after a loss the 3-fold circular mean) and `|Σ e^{3iθ}|`; heads: whole team, after a loss |
| guard_parked_centre | its network slot gets the common block only; the mask zeroes it after the fit (3.6) | — |

At R4 the closed forms rebuilt from these features must equal the labels within `features_check_atol` = 5e-5 on every
kept row (the new control C9, `ctl_features_are_the_scripts`; the ring was measured at 1.9e-5). Rows with an exact tie
are excluded and counted.

### 3.4 Network shape

- **K separate MLPs** (Linear + ELU), held as stacked weights `W_l [K, in_l, out_l]` so each layer is one `torch.bmm`.
  Each skill reads the common block (R1 + R2) plus its own R3/R4 block, zero-padded to a common width with a fixed
  `[K, D_max]` input mask.
- **One dispatch path everywhere**: run all K, then pick the row's code with `gather` on z. No `nonzero`, so no GPU wait
  in head training; the copy check reads the same path that training uses. ONNX traced at opset 17 with run-all-then-pick
  (contract scout, scout scratch `onnx_frame.py`; max difference 3.6e-7).
- The z one-hot is dropped (a network per skill); the slot one-hot is kept (roles in mark, mirror, ring, sacrifice,
  converge).
- Hidden width per skill: **[128, 128, 128]** first, **[256, 256, 256]** if the pilot needs it (section 4).
- If the pilot's S-shared assembly becomes the build's shape (4.4: a shared trunk with a head per skill, or one shared
  network), this section, 3.8, 5.1 and 5.3 are re-costed for that shape before the owner is asked to approve the build.
- Normaliser over the features (std floor 0.01; flags and one-hots raw).
- New method `all_codes_flat(obs, slot) -> [B, K, 4]` for `distil._flat_codes` and `skill_net.all_codes`; the generic
  path stays for `ScriptOracle` and `PermutedNet`.

### 3.5 Outputs in each skill's frame (a fixed rotation, nothing learned)

Each skill's network predicts `(c1, c2[, vz])` in its frame; world `xy = c1·e1 + σ·c2·e2` (σ = 1 except the R4
reflection); vz passes through; yaw is 0.

| Rung | Strike skills | Guard skills |
|---|---|---|
| R1 to R3 | zone-line frame `(h, s)` | zone-line frame `(h, s)`; poorly conditioned for ρ < 0.5 m (3.7 % of Guard rows, scout scratch `out_frames.log`), which is why the raw inputs are kept |
| R4 | zone-line frame, reflected | mark_edge, mirror: marked-Strike frame `(e, t)`; field: nearest-Strike frame `(e_n, t_n)`; ring: world frame (both chosen frames carry a script choice) |

Because the rotation is orthonormal, the squared error is the same in the frame and in the world.

### 3.6 The exact zero: a [K, 4] output mask

- A buffer `out_mask [K, 4]`, set at the start of the first fit from the labels with
  [cells.py](../../source/svg_training/ste/cells.py) `active_rule` over round 0's kept rows (a channel is active if any
  label on it is non-zero). On this game: yaw off for all 11 skills; vz on only for strike_high and strike_low;
  guard_parked_centre all off at team size 3. It is not keyed on skill names, and it is checked against the network
  file's pinned `team_size` and `starling_enabled`.
- Applied after the clamp (`clip=True`) and on the raw output (`clip=False`), before the alive flag, so masked channels
  get no gradient and are bit-exact 0, in ONNX too (contract scout).
- **`initial_net` leaves the mask all ones**, so C4 (the unfitted network) keeps its meaning: an unfitted parked_centre
  is not the script. This takes Faithful's choice over Fidelity's.
- **Said plainly:** with the mask, `cmd_zero_skill_max_abs` and `cmd_unused_max_abs` pass by construction. That is
  honest here because the scripts output exact zeros there, but those two limits then test the mask, not learning.

### 3.7 Distillation and fit

- **Fit, fresh each round as today (C8 determinism)**, all K networks in one batched module, one optimiser.
- **Loss**: `L = Σ_k mean_rows[ w_row,k · ||mask_k ⊙ (f_k(features) − y_k)||² ] / n_active_k`, unclipped; every kept row
  is labelled with every code (as today); row weight `w_row,k = 1 + (own_row_weight − 1)·[flown == k]` with
  `own_row_weight = 2.0`.
- **Schedule**: Adam; linear warm-up over 2 % of the round's steps; cosine decay from `lr` = 1e-3 to `lr_final` = 1e-5.
  Rounds 0 to 2 at 40 epochs as today; the final round at `final_epochs` = E, set from the pilot as
  E = 1.5 × (steps the pilot needed) × 8,192 / 8,000,000 rows, rounded up: about 60 if 40,000 steps suffice, about 120
  if a skill needs the 80,000-step retry (estimate). The network is read at the end of the schedule; no best
  checkpoint is picked.
- **Not taken**: EMA of weights and the per-branch bias polish (Fidelity). The schedule is the lever for bias that was
  tested, on a network already trained (section 1.5; from scratch it is arm C-lr's question, 4.3); the polish does not remove turn or scale where the command varies, and it fits on final-round rows. Also
  not taken: a per-skill normalisation of the keep weights (it changes collection, which the diagnosis cleared).
- **The fit report** adds, per skill on its own rows: bias per channel, mean signed turn, mean speed ratio, and RMSE with
  the bias removed (the row marks of section 4).
- **The driver** gains C9 when any skill uses R3 or R4.

### 3.8 Gate-file changes ([distil_gates.toml](../../configs/ste_ls1/distil_gates.toml))

| Section | Change |
|---|---|
| `[net]` | `hidden` = per skill (pilot value); add `arch = "per_skill_v1"`, `features = "frame_v1"`, `out_mask = "from_labels"` and `[net.rung]` with one entry per skill (pilot value, e.g. `strike_straight = "R1"`); `zeroed_inputs` and `std_floor` unchanged |
| `[fit]` | `epochs = 40`, `lr = 0.001`, `batch = 8192`, `seed = 150003` kept; add `final_epochs`, `lr_final = 1e-5`, `schedule = "cosine"`, `warmup_share = 0.02`, `own_row_weight = 2.0` (all PROPOSED) |
| `[data]` | add `features_check_atol = 5e-5` (PROPOSED; only if a rung R3/R4 is used) |
| `[stop]` | the `fix_round` text is replaced to record R49 (stop and redesign; the fix round not spent; this build named); the owner's wording |
| `[source]` | unchanged (`scripted_sha256` stays: the scripts are not edited) |
| `[limits]`, `[controls]`, `[controls.near_miss*]`, `[read]`, `[read.near_miss_cells]` | **unchanged** |

The file's sha changes and is re-pinned (`--expect-gates-sha256`, provenance, `fit_report`). Network files become
FORMAT `"ste-ls1-skill-net-2"` with payload keys `arch`, `features`, `rung`, `hidden`, `out_mask`; format-1 files are
refused (only the T93 files in `runs/` use it; `configs/ste_ls1/heads_gates.toml` `[learner.skill_net]` shas are still
FILL_; contract scout).

## 4. Pilot plan before any build

All pilots are **scratch, INFO, not of record**. CPU only: each job sets `OMP_NUM_THREADS=6 MKL_NUM_THREADS=6
CUDA_VISIBLE_DEVICES=""`, unsets `PYTHONPATH` and runs `env_isaaclab` python with `PYTHONPATH=source`. Every time
below is for **one job at a time on 6 threads**. The lead's parallelism (26 Nov 2026, 4.6) allows up to 4 such jobs
side by side (24 threads) while the owner is not using the PC, and one at a time when the owner is; 4.6 gives the wall
clock both ways. Scratch code lives in the session scratchpad; nothing is
written in the repository during the pilots. Afterwards the scripts, logs and a README are saved to
`records/evidence/<date>_ste_ls1_redesign_pilots/`.

**Step before the pilots start:** the scouts' scratch files (section 8) are copied to
`records/evidence/2026-11-26_ste_ls1_redesign_scouts/` with a README, by the lead. Until then the marks that rest on
them (the 0b timing, the 0c widths and margins, r2 to r4's error kinds, the 0d parity figures) are draft.

**Before the first run the owner confirms the plan** (decision 1): its marks, including the headroom marks of 4.4,
which are the lead's rule and not an R48 limit, and its cost (4.6). **The marks below are fixed once confirmed, before
any trial, and are not adjusted afterwards.**

### 4.1 Data

- Rows: `runs/2026-11-26_ste_ls11_distil_{guard,strike}/data/round_{0..3}.pt` (fields `obs`, `slot`, `label [R,K,4]`,
  `flown`, `net_flown`, `round`, `game`, `episode`, `near_switch`; checked by the writer).
- **Held-out set, game-disjoint**: every row whose `game % 5 == 0`, in every round (about 37 % of F2's held-out rows were also
  among its training rows, [LS1_FIX_ROUND_PROPOSAL.md](LS1_FIX_ROUND_PROPOSAL.md) section on one skill per network). Training: 1,000,000 rows from round 0 plus 1,000,000 from round 3, from the other games.
- Marks are read on held-out rows where `flown == k`, rounds 0 and 3 separately; all held-out rows are reported too.
- Features are computed once per rung and cached (about 1 to 1.5 GB per team per rung, estimate).

### 4.2 Stage 0: five checks with no training (about 1.5 to 2 h one job at a time; estimate)

**0a. Harness validation.** A scratch driver imports
[ste_ls1_equivalence.py](../../scripts/ste_ls1_equivalence.py), builds its context on T94's gate file, wraps a pilot
network in the contract of 3.1 (as `PermutedNet` does), plays only the network batches with the read's own cell
functions, and pairs outcomes with the stored script games `runs/2026-11-26_ste_ls12_read_{side}/games/c1_scripts*`
and `c1m_scripts*` (valid: scripts against scripts change 0 games). Marks (lead, 26 Nov 2026: replayed in T94's own batches from `layout.json`, so each cell is exact; if a batch layout
cannot be kept, each cell may differ by at most 2 games, an estimate, as in 0c):

- the saved LS1.1 Strike network reproduces T94: 44 on high,straight,high v guard_mark_edge and 122 on flank x3 v
  guard_mirror; the saved Guard network: 64 on mark_edge,mirror,parked_centre v strike_converge (all three checked by
  the writer in T94's `results.json`);
- `ScriptOracle` gives 0 changed games on those three cells.

A miss is a harness fault: stop, fix, rerun. No design result is read until 0a passes.

**0b. De-bias and mask replay (INFO, calibration, no mark).** The LS1.1 networks get a 300-step fresh-Adam tail at lr
1e-4 and a post-hoc [K, 4] mask, then play every gated cell of both teams. It tells whether the schedule and the mask
alone bring the passing-skill cells under 30, and it calibrates row error against changed games for real network error.
Cost about 1 min of tail plus 8 to 12 min of replay per team (T94 `layout.json`: network arm 3.3 s per Guard cell,
4.5 s per Strike cell; scout scratch).

**0c. Blended-switch replay.** The closed forms of flank, field, sacrifice and converge (geometry scout) fly in place
of the script, with each hard switch replaced by a linear blend of the two branch commands over a margin width w of
1, 3 and 10 cm (what a smooth network does at a switch). Cells: every gated and INFO cell holding that skill (flank 65 +
13, field 6, sacrifice 5 + 1, converge 5 + 1, so 96 cells; tallied by the writer from T94). In mixed cells the
scripts fly the other codes. That is 96 cells × 4 widths (0, 1, 3, 10 cm) = 384 cell-plays at about 4.5 s, about
30 min in one job (estimate).

- Driver check: at w = 0 every cell gives at most 2 changed games (**estimate**: the closed forms differ from the
  scripts by up to 8.8e-6 for converge and 2.4e-7 to 3.6e-7 for the other three, `out_closed.log`, which can flip a
  game whose state sits on a switch margin). More than 2 in a cell is a harness or closed-form fault, not a design
  result: stop, fix, rerun. The changed games at w = 0 are reported and subtracted from nothing.
- A width **passes** for a skill if every gated cell holding it has b + c ≤ 20 and its interval inside ±0.045 (20, not
  30: a blend is one error source among several).
- Reading: if w = 3 cm or wider passes, R3 is eligible for that skill. If only 1 cm passes, R3 is still fitted but R4 is
  expected. If none passes, only R4 is eligible.
- The widest passing width also sets that skill's tail mark r6 (below): the blend's tail share is measured open loop,
  the w-blended closed forms against the labels with all of the skill's switches blended together, on the skill's own
  held-out rows (4.1), as the share of rows with max-channel |difference| > 0.1.

**0d. Sort-free script logic and ONNX parity.** The features of every rung (R1 to R4; ranks by comparison counts and
`arange == arange` in place of `eye`) are written once; the R4 part is also the code C9 needs. Marks:

- the closed forms from the R4 features equal the stored labels within 5e-5 on every held-out row of all 11 skills
  (mirror checked explicitly, with its `RING` of 1.2 and its final norm clamp);
  guard_parked_centre labels, all yaw labels and vz on the 9 skills that do not use it are exactly 0;
- the features of each rung plus an unfitted pilot network export at opset 17 and run in onnxruntime: flags and selections identical
  on at least 99.999 % of 100,000 rows per team; continuous outputs within 1e-5 except rows within 1e-4 of a switch
  margin; rows that differ by more than 1e-3 are at most 10 per million and each lies within 1e-4 of a margin; masked
  channels exactly 0.
- atan2 (used at R3 and R4 only) has not been shown to match under onnxruntime near ±π; this mark is its first test.

A 0d miss on a rung makes that rung ineligible for the build until fixed; the other rungs go on.

**0e. Combined-error replay (INFO, calibration, no mark; it changes nothing).** The scripts fly with every allowed
kind of row error at once, at the row marks of 4.3, on every gated cell of both teams, paired with T94's stored script
games. It reuses T90's perturbation code unchanged:
[perturbed.py](../../source/svg_training/opponents/perturbed.py) `CommandPerturbation`, one wrapper per kind, built per
drone slot as [ste_ls1_calibration.py](../../scripts/ste_ls1_calibration.py) `_member` builds T90's. Each wrapper
clamps to [−1, 1] and multiplies by the alive flag, so 0e nests four of them around each slot's script, in this order
(innermost first):

| Wrapper | Strike team | Guard team | Channels | As T90's |
|---|---|---|---|---|
| 1 noise, i.i.d. uniform in [−h, h] per tick, drone and channel | h = 0.0173 (RMSE 0.010 = h/√3) | h = 0.0260 (RMSE 0.015) | the skill's active channels (the mask of 3.6: x and y; vz too for high and low) | T90's `active_only_arm` channel rule (active channels only); T90's main noise ladder noised all four channels |
| 2 bias, +b on every live drone and tick | b = +0.005 | b = +0.003 | x and y, same sign | T90's `[bias]` (+size on channels 0 and 1) |
| 3 turn of xy, anticlockwise | +0.5° | +0.5° | x and y | T90's `[turn]` direction |
| 4 scale | 0.99 | 0.99 | vx, vy, vz | T90's `[scale]` channels [0, 1, 2] |

- Noise seed per slot: T90's rule, `150101 + cell index in the side's full cell list × team size + slot` (calibration
  `[noise] seed`), so 0e uses the same uniform draws as T90's noise arms (common random numbers).
- guard_parked_centre is not wrapped: under the mask of 3.6 it is exactly 0, so the design gives it no error.
- Reported per cell: b + c, the interval, and per skill the realised RMSE, bias, turn and scale of the flown command
  against the bare script's command (each wrapper records only against its own inner, so this is computed by the
  scratch driver, not read from the wrappers). The clamp makes the realised noise a little smaller than h/√3 where the
  command is near ±1.

It answers whether the row marks, taken together, stay under 30 changed games. Whatever it shows, **0e changes no
mark, rung, trigger or decision**; it is reported, and if the sum goes over 30 the note says that the row marks are
not jointly budgeted. Cost about 8 min (Guard team) and 10 min (Strike team) (estimate, from T94's per-cell times).

### 4.3 Stage 1: row-level fits, every skill of both teams

Common settings: the network of 3.4 for one skill, outputs in its frame (3.5), the mask (3.6), the loss and schedule of
3.7 (Adam, 2 % warm-up, cosine 1e-3 → 1e-5, batch 8,192, own-row weight 2), read at the end of the schedule.

| Arm | Skills | Rung | Size, steps | Fits |
|---|---|---|---|---|
| **B** (the owner-told design) | the 10 skills other than parked_centre | R1 + R2 | 3x128, 40,000 | 10 |
| **A3** | flank, field, sacrifice, converge | R3 (if 0c allows R3 for that skill) | 3x128, 40,000 | up to 4 |
| **A4** | flank, field, sacrifice, converge | R4 with branch heads and reflection (if 0d passed) | 3x128, 40,000 | 4 |
| **Next rung**, pre-declared, fitted whatever B shows (so the Stage 2 ladder always has a rung to move a smooth skill to; strike_high is in every passing-only Strike cell over 30) | strike_high, strike_low; guard_mark_edge, guard_mirror, guard_parked_ring | R3 for high and low (if 0d passed for R3); R4 for mark_edge, mirror, ring (if 0d passed for R4) | 3x128, 40,000 | 5 |
| **Retry**, pre-declared, at most once per fitted rung | any fitted (skill, rung) of B, A3, A4 or Next rung that fails the eligibility screen (below) | same rung | 3x256, 80,000 | as needed (allowance 4) |

Seeds: every Stage 1 fit uses fit seed **150003** (the gate file's `[fit] seed`, as T93); this is "seed 1" in 4.4.
The second seed of 4.4 is **151003** (scratch; clear of the computed noise seeds, `[read] noise_seed` 150007 and the
calibration's 150101 plus cell index × 3 plus slot, which stay below about 150600).

**The eligibility screen (one criterion, used for retries and in 4.4).** For a fitted (skill, rung): the largest, over
the skill's active channels, of its total RMSE (r7's quantity) on the pooled held-out rows of rounds 0 and 3 where
`flown == k`. The rung is **eligible** if that is at most **0.10**: twice the gate's 0.05, because the read's and the
fit report's RMSE differed by up to 2 times, and T94's parked_ring passed closed loop at own-row 0.062. A rung that
fails the screen gets its one Retry; **the retry replaces that rung's fit, whatever its result** (it is not a new
rung), and the screen is read again on it. The screen only decides which fitted rungs may enter a Stage 2 assembly;
**it is never a pass criterion**, and a skill passing it says nothing about the closed loop.

**Control arms: one idea at a time.** Arm B bundles the four ideas the owner was told about (own-frame inputs, a
network per skill, the decaying schedule, the built-in zero). They are hypotheses, and only these arms test them one at
a time. Each is read on one smooth and one switch skill per team: Strike team strike_high (in every passing-only
Strike cell over 30) and strike_flank (F1 and F2 already exist); Guard team guard_mirror (steep gain, 1.6) and
guard_field (switch). Same rows, held-out set, steps and seed as B; read on the row marks only.

| Arm | Differs from B in | What it tests | Fits |
|---|---|---|---|
| **C-in** raw inputs | the 71 raw inputs (zeroed 6, 7, 10, 11) and the world-frame output, per-skill network, new fit | idea 1, own-frame inputs, together with the output frame of 3.5 (both change in this arm; a match says the pair is not needed) | 4 per-skill |
| **C-lr** old schedule (replaces the earlier arm D) | constant lr 1e-3, R1 + R2, per-skill network | idea 3, the decaying schedule from scratch | 4 per-skill |
| **C-head** shared trunk | one 3x256 trunk (today's width) on R1 + R2 (plus the slot one-hot) for all the team's skills, one small output head per skill, new fit, mask | idea 2, a network per skill against a head per skill | 2 joint (one per team, all skills) |
| **C-one** one shared network | one 3x256 network on R1 + R2 plus the skill-code one-hot, as today's shape, new fit, mask | idea 2, against one network per team | 2 joint (one per team, all skills) |

Idea 4 (the built-in zero) is true by construction and is not tested by an arm (3.6).

**Matches B, defined.** For an arm and a skill, read two numbers on the pooled held-out rows of rounds 0 and 3 where
`flown == k`: R5 = the largest r5 over the skill's active channels, R7 = the largest r7 over them. The comparison
**counts** on that skill only where B meets r7's mark (R7 ≤ 0.030); where B misses it, the arm's numbers are reported
and read neither as a match nor as a miss. Where it counts, the arm **matches B** on the skill if all of:

- its R5 ≤ max(1.2 × B's R5, B's R5 + 0.002) and its R7 ≤ max(1.2 × B's R7, B's R7 + 0.002) (the absolute floor of
  0.002 keeps a tiny difference on a very small B from reading as a miss);
- it meets r2 and r3 in each round (0 and 3, read separately as in 4.1) and on each channel where B meets them.

The 1.2 and the 0.002 are the lead's choice. Seed-to-seed spread is not known until Stage 2's second seeds; a ratio
near 1.2 may be seed noise, so a match or a miss is weak evidence and is reported beside that spread once it is
known. What each outcome changes (pre-declared; a team's two skills are those named above):

- C-in matches B on both skills of a team: the own-frame inputs are reported as not needed for that team's two
  skills; the build keeps R1 (it costs little) but the note drops the claim that it is what fixes them.
- C-lr matches B on both skills of a team: the decaying schedule is reported as not needed from scratch for that team;
  the build keeps it (it costs nothing). C-lr missing r2 or r3 on a skill where B meets them is reported as support
  for the schedule.
- C-head or C-one **qualifies for S-shared on a team** if it matches B on each of that team's two skills where the
  comparison counts, and the comparison counts on at least one of them. If both qualify on a team, **only C-head's
  shape** goes to that team's Stage 2 (it keeps a separate head per skill and a path between codes for LS3, section 6); C-one is reported. If it
  passes there (4.4), it is the build's recommended shape: C-head is closer to the route page's "one skill network per
  team"; with C-one the route page's picture is unchanged.
- Otherwise the build uses separate per-skill networks, and the note states which idea the arms showed to matter.

These are row-level reads. 1.3 shows that row error predicts changed games poorly (rank correlation 0.19 and 0.29), so
an arm's match is evidence about the fit, not about the copy check; only the Stage 2 replays of C-head or C-one say
whether a shared shape passes.

guard_parked_centre keeps its network slot (so the unfitted C4 network moves on its cells) but is not fitted in the
pilot: once the mask is set from the labels it gives exactly 0 on every row, which is checked.

Throughput: F2 ran 3x256 at about 23 steps per second on 2 threads (2,605 s for 60,000 steps,
[pilot_F2.log](../../records/evidence/2026-11-26_ste_ls1_fix_diagnosis/pilot_F2.log)); 3x128 on 6 threads is expected
at about 60 to 100 steps per second (estimate), so about 7 to 11 min per 40,000-step per-skill fit. The joint arms
label every row with every code: C-head runs one trunk and K small heads (about 10 to 20 min a fit), C-one runs its
network K = 5 or 6 times a row (about 40 to 80 min a fit) (estimates). A retry at 3x256 and 80,000 steps is about 25
to 35 min (estimate: F2's 23 steps per second on 2 threads, faster on 6). Fits, one at a time on 6 threads:

| Fits | Count | Time (estimate) |
|---|---|---|
| B, A3, A4, Next rung (per skill; 10 + up to 4 + 4 + 5) | up to 23 | 2.7 to 4.2 h (23 × 7 to 11 min) |
| C-in, C-lr (per skill) | 8 | 0.9 to 1.5 h |
| C-head, C-one (joint) | 4 | 1.7 to 3.3 h (2 × 10 to 20 min + 2 × 40 to 80 min) |
| Retries (each replaces a fit; costed at none to 4, the rule itself has no cap) | 0 to 4 | 0 to 2.3 h (4 × 25 to 35 min) |
| **Stage 1** | | **about 5.3 to 11.3 h** |

Stage 1 also measures CPU forward time per 3,000-row and 49,152-row call for the assembled networks, features
included.

**Row marks, per skill on its own held-out rows, both rounds.** They are reported, and the control arms' comparisons
(above) read them. They decide nothing in the ladder: the eligibility screen (above) sets the retries and which rungs
may enter an assembly, and 4.4's rules order the rungs. **A missed row mark never blocks a PASS; Stage 2 alone
decides.** They are not jointly
budgeted (0e tests that), and on the Guard team they are stricter than the closed-loop evidence: T94's 12 Guard cells
made only of parked_ring and mark_edge reached a largest of 27 changed games, at own-row RMSE 0.062 and 0.035
(`g_ownrows.out`), far above r5 and r7.

| Mark | Guard team | Strike team | Source of the number |
|---|---|---|---|
| r1 exact zeros | masked channels `torch.equal` 0 on every row; guard_parked_centre all 4 channels 0 | masked channels 0 on every row | gate `cmd_zero_skill_max_abs` 0.005 |
| r2 steady bias, \|mean error\| per active xy channel (world frame) | ≤ 0.003 (the low end of 1.3's budget, which carries a 2x safety factor) | ≤ 0.005; vz of high/low ≤ 0.005 | Guard bias 0.01 → 31 (fails), parked bias 0.005 → 15; Strike network mixed error 44 at bias about 0.02 |
| r3 steady turn, \|mean signed angle\| over rows with \|label_xy\| > 0.2 | ≤ 0.5° | ≤ 0.5° | Guard turn 1.5° → 34 (fails) |
| r4 speed scale, mean \|out_xy\| / \|label_xy\| over the same rows | in [0.99, 1.01] | in [0.99, 1.01] | scale 0.95 fails both teams (margins, Strike pooled) |
| r5 state-dependent RMSE per active channel, bias removed, rows more than 2 cm from every switch margin of the skill | ≤ 0.015 (**estimate**: half the passing 0.029 rung, for amplification) | ≤ 0.010 (**estimate**: noise 0.011 → 27 passes, 0.028 → 37 fails) | T90 noise rungs |
| r6 tail: share of all own rows with max-channel \|error\| > 0.1 | switch skills: at most the share produced by the widest blend that passed 0c; 0.2 % if none passed; other skills 0.2 % | same rule | 0c; Fidelity r6 |
| r7 total RMSE per active channel, all own rows | ≤ 0.030 | ≤ 0.030 | gate 0.05; the read's and the fit report's RMSE differed by up to 2 times (parked_ring 0.042 v 0.088) |

These marks are estimates between calibration rungs and are reported only (the eligibility screen above is a
separate, single criterion). Stage 2 decides. The Strike r5 of 0.010 on its
own uses most of the Strike margin (noise RMSE 0.011 → 27 of 30), and the same skill may also carry the r2, r3 and r4
allowances; nothing but 0e shows the sum stays under 30.

### 4.4 Stage 2: closed-loop deciding read (every gated cell, both teams)

Stage 2 alone decides. The row marks decide nothing here; the eligibility screen of 4.3 only says which fitted rungs
may enter an assembly.

**One full replay.** All gated cells (Guard team 150, Strike team 130) plus the 26 Strike INFO cells (reported, not
gated). N = 1,000 games per cell on T44's starts (seed 110000, the read's). Network arm only, paired with T94's stored
script games (0a's driver). Recomputed on every full replay: each cell's b + c and interval (the read's own
`newcombe_hybrid`, Bonferroni per team), the pooled row over all gated cells, the command-error table from the
labeller over every cell played, the median b + c and the count of cells over 20. **A PASS or a MARGINAL is read only
from a full replay**; nothing is carried over from an earlier replay or another seed.

**Screen first** (about 1.5 min per team): per team, the union of T94's 10 worst network cells and the 10 worst cells
of the T90 arm nearest the team's binding kind of error (Guard team: bias 0.01; Strike team: noise 0.05), written to
`cells_screen.json` from the `results.json` files before any pilot network plays. All screen cells are played first;
if any of them is over 30, the replay stops there and is a FAIL (its screen cells over 30 are all known). A screen stop
can only give FAIL, never a pass.

**Marks, per team (fixed once the owner confirms the plan, before any trial):**

| Class | Condition |
|---|---|
| gate limits (all must hold) | every gated cell b + c ≤ 30; every cell interval inside ±0.045; pooled interval inside ±0.01; the replay's own command-error table passes R48 (active-channel RMSE ≤ 0.05, unused ≤ 0.05, zero skill ≤ 0.005). `end_time_gated` is false in the gate file, so end time is reported, not gated |
| headroom (all must hold) | median b + c over gated cells ≤ 9; at most 5 gated cells over 20 |

Per full replay (and per assembly, below):

- **PASS**: the gate limits and the headroom marks hold.
- **MARGINAL**: the gate limits hold, the headroom marks do not. The pilot rows come from LS1.1's data and seed; the
  build refits on its own DAgger rows. Headroom is the only buffer for that shift.
- **FAIL**: any gate limit is missed, or the replay stopped at the screen.

Consistency of the headroom marks with the calibration (writer's tally, 1.3): Strike noise RMSE 0.011 meets them
(median 8, 3 cells over 20, largest 27); Guard noise RMSE 0.029 meets them (7.5, 1, 21); Strike bias 0.02 passes the
gate but misses headroom (median 13, 11 over 20). So headroom is stricter than the gate, on purpose.

**Assemblies, pre-declared, at most four per team, in this order.** An assembly is one network per fitted skill, each
at a named rung (guard_parked_centre: its masked slot).

1. **S1**: every skill at its lowest fitted rung that is eligible (4.3). A skill with no eligible rung goes in at the
   rung with the smallest screen value.
2. **S2**, only if S1's result is FAIL: each skill of S1's trigger set (below) moves to its lowest eligible fitted
   rung above its current one, if it has one; the others stay.
3. **S3**, only if S2's result is FAIL: the same rule once more, from S2.
4. **S-shared**, only on a team whose result is PASS or MARGINAL and on which C-head or C-one qualified (4.3); below.

No assembly outside S1, S2, S3 and S-shared is played. The second seeds, the DAgger rescue (below) and the decision-8
fallback (4.5) refit skills of a listed assembly; they are not new assemblies.

**Two seeds for every assembly that reaches PASS or MARGINAL.** Seed 1 is the Stage 1 fits (fit seed 150003). If the
seed-1 full replay gives PASS or MARGINAL, every per-skill fit of the assembly is made again with fit seed 151003, on
the same rows, size and steps (3x256 and 80,000 for a retried rung); a seed-2 fit already made for the same (skill,
rung) in an earlier assembly is reused (fits are deterministic, C8). The seed-2 networks get their own full replay
(screen first). The assembly's result is the **worse of its two seeds**: PASS only if both pass; PASS and MARGINAL
give MARGINAL; a FAIL at either seed gives FAIL (reported as seed-sensitive when seed 1 passed). A seed-1 FAIL ends
the assembly with FAIL; it has no seed 2.

**The ladder, per team.**

- An assembly whose result is PASS or MARGINAL **ends the ladder**: it is the team's deciding assembly and its result
  is the team's. A MARGINAL does not try higher rungs (they carry more of the scripts' logic); it goes to decision 6.
- An assembly whose result is FAIL, at seed 1 or at seed 2, **fails that assembly only**; the ladder goes on to the
  next assembly.
- The ladder is **exhausted** when S3 has failed, or when an assembly has failed and no skill of its trigger set has
  an eligible fitted rung above its current one.
- On an exhausted ladder the team goes to the own-state check and DAgger rescue (below). **The team's result is FAIL
  only when the ladder is exhausted and the rescue is not triggered or also gives FAIL.**
- If every assembly failed, the **best** one is reported (it decides nothing): the fewest gated cells over 30 in its
  failing replay, then the smaller largest cell, then the lower rungs. Assemblies stopped at the screen rank after
  those replayed in full, by their number of screen cells over 30.

**Trigger set of a failed assembly**, read from its failing replay (seed 1's, or seed 2's after a seed-1 pass), from
the read's own failure kinds (`limit_failures` in [ste_ls1_equivalence.py](../../scripts/ste_ls1_equivalence.py)).
One set per kind; the trigger set is their union:

- **Cell kind** (`flips_max_games`, `cell_margin`): the offending cells are the gated cells with b + c > 30 or an
  interval not inside ±0.045. Every skill flown in at least half of the offending cells is in the set; if none
  reaches half, the skill (or the tied skills) flown in the most offending cells. In a replay stopped at the screen,
  the offending cells are its screen cells over 30.
- **Command kind** (`cmd_rmse_max`, `cmd_unused_max_abs`, `cmd_zero_skill_max_abs`): every skill named in a command
  failure. guard_parked_centre is masked to exact 0 and cannot miss its limit; if it does, that is a harness fault:
  stop, fix, rerun.
- **Pooled kind** (`pooled_margin`): each skill's signed contribution `c_k = (1/m) Σ_cells diff_cell × n_k,cell / 3`,
  over the m gated cells, with `diff_cell` the read's signed per-cell difference and `n_k,cell` the drones of the cell
  flying skill k. The pooled difference is the mean of the gated cells' `diff` (checked on T94: Guard −0.00238,
  Strike −0.00887), so the c_k add up to it. The skill with the largest |c_k| among those with the pooled difference's
  sign is in the set (ties: all tied).
- Missed headroom alone is MARGINAL, not FAIL, and triggers nothing.

A skill of the set with no eligible fitted rung above its current one stays where it is.

**S-shared.** Only the qualifying shape (4.3: C-head if both qualify), only on a team whose result is PASS or
MARGINAL: it decides only the build's shape, and a FAIL team has no build to shape. One joint fit of that shape at the
rungs of the team's deciding assembly, each skill's head (or code) reading its rung's features. At R1 + R2 the seed-1
fit is the control arm's own fit, reused. With any skill at R3 or R4 it is a new joint fit that no arm has checked, so
the eligibility screen is read on each of its skills first, and it plays only if every skill passes. Then the two
seeds as above (seed 2 a joint fit at 151003). It becomes the build's recommended shape only if its two-seed result is
at least the team's (PASS when the team PASSes; PASS or MARGINAL when the team is MARGINAL); otherwise it is reported
and not used. **It never changes the team's result.** Cost per team (estimate): one or two joint fits (C-head about 10
to 20 min, C-one about 40 to 80 min a fit, more with R3 or R4 blocks) plus up to two full replays.

The pilot's result: PASS if both teams PASS; FAIL if both FAIL; MARGINAL if both meet the gate limits and one or both
are MARGINAL (decision 6); one team meeting the gate limits and the other failing is the one-team row of 4.5.

**Also in Stage 2:**

- **C4 analogue**: an unfitted pilot network (seed 150003, all-ones mask) plays the 30 fixed gated cells per team. Mark:
  at least 15 cells miss on each team (the gate's number, `miss_count` definition). Cost about 5 min Guard team, about
  15 min Strike team (unfitted Strike games run to the tick cap; T94's C4 arm took about 850 s, scout scratch).
  **Among the read's controls the pilot runs only this C4 analogue** (C1 and C2 only as far as 0a checks the stored
  script games and `ScriptOracle`). C3, C5, C6 and C7 for per-skill networks are deferred to the build's read of
  record (LS1.2), where they run as R48 set them.
- **onnxruntime-flown arm (INFO)**: the exported pilot graph flies the 20 screen cells per team. Reported: changed games
  against the torch-flown network. More than 3 in any cell sends the lead to investigate before a build.
- **Control arms** C-in, C-lr, C-head and C-one are read on their row marks only (4.3); only S-shared puts a shared
  shape through the closed loop.

**Own-state check and DAgger rescue (once per team, only on an exhausted ladder).** It works on the last assembly the
team played (the highest rungs) and on its **failing replay** (seed 1's, or seed 2's after a seed-1 pass). If that
replay stopped at the screen, it is first completed in full with the same networks (9 to 18 min), so that every rule
below reads a full replay.

1. **Failing skills**: that assembly's trigger set (above).
2. **Fresh rows, never the read's starts.** The scratch driver calls the build's collection code `distil.collect` with
   round index 4, `[data]` seed 150001 and pool_seed 150002, script share 0: the assembly's **seed-1** networks (in
   0a's contract wrapper) fly every drone of the side. LS1.1 played rounds 0 to 3; `round_seed` mixes seed, round and
   purpose, so round 4's starts are new, neither rounds 0 to 3's nor T44's (seed 110000); the driver asserts both.
   Sizes as `[data]`: 4,096 games × 600 ticks, hold 12, mode shares 0.5 / 0.25 / 0.25, switch_jump 0.2, switch
   window 12 ticks; every row labelled with every code's script (the label control at 1e-5). Kept with `distil.keep`:
   2,000,000 rows, error weights from the flying networks, absent quota 0.2, switch floor 1.0, keep generator seed
   `round_seed(150001, 4, "keep")`. The kept rows are fixed once; both seeds below train on the same rows.
3. **Held-out**: the new games with `game % 5 == 0` (4.1's rule); never trained on.
4. **Trigger**: per failing skill k, its total RMSE per active channel on **all** collected rows of the held-out games
   where `flown == k`, taken before the keep (unweighted: the keep weights rows by the flying network's own error,
   which would inflate the ratio), against its r7 per channel on LS1.1's round-3 held-out rows where `flown == k`
   (round 3 is network-flown, script share 0, like the new rows; script-flown rows would make the ratio near
   automatic). Those baseline rows were kept with error weights from LS1.1's round-2 network, which leans toward harder
   rows, so the ratio is if anything conservative. A skill is **triggered** if the ratio exceeds 1.5 on any active
   channel. No triggered skill: the failure is read as a design result and the team is FAIL.
5. **Diagnostic only** (never a trigger, never trained on): the read's labeller keeps only aggregate errors
   (`RecordingSkillTeam`), so a scratch wrapper keeps a 1 % sample of `(obs, slot, label)` rows from the failing
   replay's offending cells and another from all its gated cells; the failing skills' RMSE on both is reported.
6. **Refit**: the triggered skills only, each from scratch (a fresh fit, as every round of the build, 3.7) at its
   rung, size and steps (a retried rung's 3x256 and 80,000), fit seed 150003, on Stage 1's training rows (1,000,000
   from round 0 and 1,000,000 from round 3) plus the new rows of games with `game % 5 != 0` (about 1.6 million,
   estimate). Each refit replaces that skill's fit whatever its row marks (reported). The other skills keep theirs.
7. **Replay every gated cell**: a full replay (screen first) of the assembly with the refits, with the cells, the
   pooled row, the command table, the median and the over-20 count recomputed. If it gives PASS or MARGINAL, seed 2
   follows: the triggered skills refitted at 151003 on the same rows (the DAgger rows included), the other skills' seed-2
   fits made or reused as above, and a second full replay; the result is the worse of the two seeds.
8. That result **replaces the team's FAIL**. A FAIL that survives it is the team's design result.

Cost per team (estimate): collection 5 to 15 min (not measured on the CPU), the full replay before it if needed (9 to
18 min), refits of 1 to 6 skills at 7 to 11 min each at two seeds (up to 132 min; more for retried rungs), two full
replays (18 to 36 min): about 0.1 h (no skill triggered) to 3.4 h per team. The build itself does 4 DAgger rounds.

Cost of a full replay: Guard team about 9 to 12 min, Strike team about 13 to 18 min (T94 network arm 496 s and 703 s
with the labeller, plus the larger forward; estimate); a screen-cell stop cuts a failing replay to about 2 min.

### 4.5 What each outcome means (decision rule, fixed with the marks)

| Outcome | Next step |
|---|---|
| PASS with every skill at R1 + R2 | the build plan (section 5) goes to the owner for approval; inside R49's four directions, except that guard_field at R2 is handed the script's own choice (its nearest Strike drone): that is reported as such and goes to decision 8 |
| PASS needs R3 on some skills | owner decision 2 (script margins as inputs) before the build |
| PASS needs R4 on some skills | owner decision 3, with the scope stated plainly: "for these skills the network copies the scripts' motion given the scripts' decisions; the decision logic is in the exported graph"; for sacrifice or converge, also: "for this skill route 3 is close to route 2, and the skill's own switch points are fixed until LS2 replaces the flags" (6.4) |
| One team passes, the other fails | head training (LS1.4) needs both teams' skill networks (route page, "for both teams"), so the build does not start for one team alone; the passing team's result is recorded, the failing team follows the FAIL rows, and decision 9 asks the owner whether to build the passing team now |
| FAIL on an exhausted ladder with a triggered skill (4.4's own-state check: the failing skill's error on fresh rows flown by its own network is more than 1.5 times its round-3 held-out r7) | the pre-declared DAgger rescue of 4.4: fresh network-flown rows from round 4 of `[data]` seeds 150001 and 150002 (never T44's starts), the triggered skills refitted from scratch, then **every gated cell** replayed at both seeds with the pooled row, the command table, the median and the over-20 count recomputed; its result replaces the FAIL. Only a FAIL that survives it is read as a design result |
| MARGINAL | owner decision 6 |
| Team FAIL: the ladder is exhausted (4.4) and the DAgger rescue is not triggered or also gives FAIL | LS1 stays stopped; the note reports which skills and cells fail and why, and the best assembly (4.4). The ladder beyond R4: R4 is handed the script's decisions, so a failure there lies inside a branch (regression error or closed-loop amplification), not at the switches. (a) A second pilot round: R4 at 3x256 with Fourier features of the frame inputs (Tancik et al., section 8, against the spectral bias of plain networks) on the failing skills, the other skills as in the last assembly; its marks are 4.4's gate limits and headroom marks unchanged, on every gated cell, at two seeds (151003 the second), with its fit sizes and feature scales written in the note before it runs; (b) the residual design (6.5), with its own ruling. Whether (a) is run before (b), or (b) comes straight to the owner, is decision 10. No limit moves |
| R4 passes but the owner declines decision 3 for a skill | the next trial for that skill is a classify-then-regress head at R3 inputs: a branch classifier trained on the script's branch labels, then a regression head per branch (Behavior Transformers, section 8). It uses the script's decisions as training labels only, not as inputs. It is a second pilot round and counts against decision 10's limit (if a Fourier round is also due, the two run together as that one round). Its marks are 4.4's gate limits and headroom marks unchanged, on every gated cell, at two seeds; its fit sizes are written in the note before it runs |
| guard_field is in the deciding assembly at R2 and the owner declines decision 8 | guard_field is refitted at R1 alone (slot order, no nearest-first lists) at both seeds (150003, 151003) on the same rows as its fit in that assembly (the DAgger rows included if a rescue made it); the Guard team's deciding assembly is otherwise unchanged and is replayed in full at both seeds against 4.4's marks (about 0.5 to 0.8 h, estimate: two fits and two Guard replays). Its result replaces the Guard team's. A FAIL there follows the team-FAIL row |
| 0a or 0c driver check, or 0d, fails | harness or code fault: fixed and rerun; not a design result |

### 4.6 Wall clock and cost of the pilots

All estimates. The lead sets the parallelism (26 Nov 2026): up to 4 jobs side by side at 6 threads each (24 of the
RTX 5090 machine's 32 threads) while the owner is not using the PC; one job at a time when the owner is. The table is
one job at a time. "Typical" is both teams ending at S1 (PASS or MARGINAL at both seeds) with no S-shared; "worst" is
the bound when every fallback runs.

| Part | Time, one job at a time | How it is made up |
|---|---|---|
| Scratch-code writing (agent time) | 5 to 7 h | the harness, features of every rung, the closed forms, the arms of 4.3 (the control arms add about 1 h to the 4 to 6 h of the first draft) |
| Stage 0 | about 1.5 to 2 h | 0a about 10 min; 0b about 25 min; 0c about 30 min; 0d 10 to 20 min; 0e about 18 min; feature caching |
| Stage 1 | about 5.3 to 11.3 h | the fit table of 4.3: up to 23 per-skill fits 2.7 to 4.2 h, C-in and C-lr 0.9 to 1.5 h, joint fits 1.7 to 3.3 h, retries 0 to 2.3 h |
| Stage 2, typical | about 2.4 to 3.3 h | S1 seed 1 both teams 22 to 30 min, C4 analogue about 20 min, onnxruntime arm about 10 min, seed-2 fits 10 × 7 to 11 min (1.2 to 1.8 h), seed-2 replays 22 to 30 min |
| Stage 2, S-shared if it plays | adds about 1.1 to 3.7 h | per team one new seed-2 joint fit at R1 + R2 (C-head 10 to 20 min, C-one 40 to 80 min) and two full replays; more with R3 or R4 blocks |
| Stage 2, worst | up to about 16 h | C4 and onnxruntime 0.5 h; S1 to S3 each failing at seed 2 after a seed-1 pass, 6 full replays per team (2.2 to 3 h for both teams); seed-2 fits bounded by Stage 1's 23 per-skill fits, 4 of them retried at 3x256 (up to 5.8 h); the DAgger rescue refitting every skill at both seeds (Guard up to 2.3 h, Strike up to 3.4 h); or, on the S-shared path, two new joint fits per team at R3 or R4 (up to about 5.3 h with C-one) in place of the rescue |
| **Total compute, one job at a time** | **about 9 to 16.5 h typical; up to about 29 h worst** | 1.5 + 5.3 + 2.4 = 9.2; 2 + 11.3 + 3.3 = 16.6; 2 + 11.3 + 16 = 29.3 |

**Wall clock with 4 jobs side by side** (estimate). Stage 1's fits are independent: about a third to a half of the
one-at-a-time time (memory bandwidth limits the gain). Stage 0's five checks split into about two at once. Stage 2's
ladder is sequential per team, so only the two teams, and the seed-2 fits within an assembly, run side by side: about
a half. Typical: about 0.75 to 1 h + 1.8 to 5.7 h + 1.2 to 1.7 h = **about 4 to 8.5 h**; worst: 1 + 5.7 + 8 = **about
15 h**. When the owner uses the PC, the one-at-a-time figures apply.

The first draft gave 7 to 9 h one at a time and 3.5 to 4.5 h with 4 jobs side by side; the review's draft gave 8 to
15.5 h (up to 20). Both are replaced: the rise comes from the control arms, the joint fits, the pre-declared next
rungs, the retries at 3x256, 0e, the second seeds of every assembly that reaches PASS or MARGINAL, the full-replay
DAgger rescue and S-shared's own fits.

All estimates. 0 GPU-hours.

## 5. The build after the pilots (only with the owner's approval)

### 5.1 Code changes by file (sizes are estimates; they depend on the rungs used)

| File | Change | Lines (code / tests) |
|---|---|---|
| `source/svg_training/ste/skill_features.py` (new) | features per team and rung, frames, absent placeholders, sort-free ranks, closed forms for C9; UPPER_CASE constants only | 150 (R1 + R2 only) to 350 (with R4) / 120 to 250 |
| [skill_net.py](../../source/svg_training/ste/skill_net.py) | SkillNet v2: batched per-skill MLP, input mask, output frames, `out_mask`, `all_codes_flat`; FORMAT 2; payload keys; refuse format 1 | about 150 / 140 |
| [distil.py](../../source/svg_training/ste/distil.py) | `initial_net`, `_mean_std` over features, `_flat_codes` through `all_codes_flat`, `fit` (schedule, masked per-skill loss, own-row weight), `SECTIONS` keys, the fit report's error kinds | about 100 / 120 |
| [export.py](../../source/svg_training/ste/export.py) | `_skill_net_lines` (arch, features, rungs); the trace already covers the features | about 15 / 30 |
| [ste_ls1_distil.py](../../scripts/ste_ls1_distil.py) | `rebuild_net`; C9 when R3/R4 is used | about 30 / 20 |
| [ste_l6_export.py](../../scripts/ste_l6_export.py) | the FORMAT check | about 5 |
| [ste_ls1_equivalence.py](../../scripts/ste_ls1_equivalence.py) | none (C4 stays `initial_net`) | 0 |
| tests | `tests/_ste_ls1.py` `tiny_net`; [test_ste_ls1_skill_net.py](../../tests/test_ste_ls1_skill_net.py) tests 1, 3, 4, 6 (slot-changes-command moved to a non-zero Guard skill) and 8 (payload keys); `test_ste_ls1_distil.py` (`"mlp.0.weight"`, `hidden`); `test_ste_ls1_distil_gates.py` (exact keys); `test_ste_ls1_export.py`; `test_ste_ls1_equivalence.py` 298 to 300; `test_ste_literals.py`; new: features never read 6, 7, 10, 11; masked channels exactly 0 on every path; features trace to ONNX within 1e-5; features are row-wise | about 250 to 600 in all |

In all about 450 to 650 lines of code and 250 to 600 of tests, about 1.5 to 2.5 agent-days with review and QC
(estimate). Two merges into `development`, each with the full suite in the background (code changes): M5 (features
and network, with their tests), then M6 (distil, gate file, drivers). The gate file is filled and hashed by the lead
after QC, as in the LS1 task plan.

### 5.2 The runs of record after the build

- **LS1.0 smoke** on the CPU, then **LS1.1** (GPU) and **LS1.2** (CPU) in new run folders
  (`runs/<date>_ste_ls11r_distil_{guard,strike}`, `runs/<date>_ste_ls12r_read_{guard,strike}`) with the new gate hash
  (R49). New ledger rows and a new record.
- **Before LS1.1**: a GPU timing smoke of one round and of one `one_code` call at 49,152 rows, so the GPU ask and the
  LS1.4 effect rest on measurements. It is paid from the `LS1.1` key (LS1.0's cap is 0.0 GPU-h, CPU only), counted in
  the ledger, and it also measures the features' overhead (5.3).

### 5.3 GPU-hours (estimates; budget section `[budget_ls]` of [ste_learning.toml](../../configs/ste_learning.toml))

LS1.1's task cap is 0.8 GPU-h (the lead's safety stop under R39, not an R48 limit); 0.172 is used, 0.628 left. The
ledger counts the union of side-by-side jobs: T93's two jobs summed to 0.326 but count 0.168
([distil read record](../../records/2026-11-26_ste_ls1_distil_read_record.md), "GPU hours").

Basis (each case: per-team seconds = 0.575 × (480 + 8 × E) × the factor, plus about 110 s of collection, report and
clips): T93's fit took about 460 of 529 s per team for 40 epochs over 2 + 4 + 6 + 8 million rows, about 0.575 s per
million row-epochs. Per-skill networks in the all-codes fit ran 0.55 to 0.9 times today's forward at 3x256 (CPU,
contract scout); about 0.3 to 0.5 times is expected at 3x128.

| Case | Final epochs E, size | Per team | Both teams summed | Union if side by side |
|---|---|---|---|---|
| low | 60, 3x128 (factor 0.3) | about 5 min, 0.08 GPU-h | 0.15 | about 0.1 |
| central | 120, 3x128 (factor 0.5) | about 9 min, 0.15 | 0.3 | about 0.17 |
| high (guard case) | 300, 3x256 (factor 0.9) | about 27 min, 0.44 | 0.9 | about 0.5 |

**Features overhead (estimate, not measured).** The factors above are FLOP ratios of the networks alone. The build
computes the features inside the network on every call (the pilot caches them), adding an estimated 0.4 to 0.7 of
today's forward. With it the per-team figures become about 0.14 to 0.18 GPU-h (low), 0.24 to 0.31 (central) and 0.63
to 0.77 (high). The fit can avoid most of it by computing the features once per round on the kept rows (they are
row-wise, 3.3), at about 2 to 3 times the rows' memory (estimate); the builder chooses, and the 5.2 smoke measures it.

The low case fits the 0.628 left with no cap change. The central case fits only with the features cached (two asks
of about 0.2); without caching its two asks (about 0.3 each before any padding) reach the 0.628 left, and the cap is
raised as below. The high case does not fit: the task plan's rule is that
both jobs' asks fit under the cap less the hours used, and two asks of about 0.45 (features cached) to 0.8 (features
not cached) exceed 0.628. So **in the high case the cap raise is required, not optional**: the lead raises LS1.1's cap
to about 1.2 GPU-h (features cached) or about 2.0 (not cached) and announces it before launch. Counted as the ledger
counts (union), LS1.1 in all would then be 0.172 + about 0.1 to 0.9 = about 0.27 to 1.07 GPU-h. Up to about 0.65 that
is inside the route page's "asks 0.9" for LS1 Distil ([route page](../LEARNED_SKILLS_ROUTE.md) line 86); the high case
without caching goes past it, and the lead states that to the owner before launch.

### 5.4 CPU time of the copy check (estimates)

Today 37.5 min (Guard team) and 53.1 min (Strike team); the network forward was about 3 % and 10 % of that (contract
scout). With run-all-then-pick: at 3x128 about +2 to 3 min and +7 to 12 min; at 3x256 about +5 to 7 min and +26 min.
The features add an estimated 0.4 to 0.7 of today's forward (5.3): about +0.5 to 1 min (Guard team) and +2 to 4 min
(Strike team). So about 40 to 46 min and 60 to 85 min.

### 5.5 Effect on LS1.4 head training (estimate; not measured on the GPU)

One `one_code` call of about 49,152 rows per tick, about 33,600 ticks per run. On the CPU the network part is about 1.5
to 3 times today at 3x128 and about 6 times at 3x256. No data-dependent shapes, so no GPU wait. What share of a head-
training step the skill network takes has not been measured; the 5.2 smoke measures it before LS1.4 is costed. The
LS1.4 cap (4.0 GPU-h, owner R43) is unchanged.

## 6. Route 3 fit

| Stage | Fit | Why |
|---|---|---|
| LS1.4 head training | good | contract unchanged; heads cannot tell the new network from the old; each code is a faithful copy without cross-skill interference |
| LS2 fine-tuning skills | good at R1 to R3; medium at R4 | a network per skill can be fine-tuned alone, tied to its frozen copy; PPO differentiates the weights, not the inputs, so feature inputs do not block it; R3 keeps thresholds learnable; R4 flags freeze where switches happen (a hook for the LS2 note: replace each flag by `sigmoid((margin − θ)/τ)` with θ, τ at the script values); the mask must be relaxed for vz or yaw to be learnable; raw world inputs stay, so the walls' asymmetry stays visible |
| LS3 free codes | medium (separate networks); better with a shared trunk | separate networks share nothing, so there is no built-in path between codes; a free code would be a new network on the common R1 + R2 block, the skill-agnostic part. The shared-trunk shape (C-head, 4.3) keeps that path; it is the build's recommended shape only if its S-shared assembly meets 4.4's rule |
| Export | good, if 0d passes | features and networks are plain tensor ops; R4 features must stay sort-free and eye-free; the scripts are not in the graph at R1 to R3, and only their decision logic is at R4 |

**Team size and the mask.** The mask file is pinned to team size 3 (and the Starling setting). guard_parked_centre is
zero only because its script tests the observation's shape, that is the game's fixed team size (`obs.shape[1] == 1`
in `GuardParkedCentre.act`), not the number of live drones: losing drones in a game does not change it, but a game
drawn with a lone Guard flies to the centre. If later stages draw team sizes (the route page's "What a useful policy
still needs"), the mask is rebuilt from that game's labels, or removed for parked_centre and the skill fitted. This goes
into the LS1.4 and LS2 hand-off and into decision 4.

**What LS2 must show on an R4 skill before LS1.4 is paid for (plan, CPU).** For each skill built at R4, a pre-declared
CPU check: replace each R4 flag by `sigmoid((margin − θ)/τ)` with θ at the script's value and a small τ, then (i)
replay that skill's gated cells and meet the same gate limits (the soft-flag network still copies the script), and (ii)
show non-zero gradients of a fixed loss on θ (the switch can move under training). If (i) or (ii) fails, the R4 skill
is a frozen copy for LS2 and the owner is told before LS1.4's hours are spent. Marks written in the build's task plan
before the check runs.

### 6.4 R4 and the residual design on the same criteria

| Criterion | R4 on a skill | Residual design |
|---|---|---|
| Script logic in the exported graph | the decision logic of that skill (flags, chosen drones; part of about 350 lines of script logic) | all of every script |
| Control C4 keeps its meaning | yes (`initial_net` is unfitted) | no: C4 must be redefined (owner decision) |
| LS1 shows a network can carry the skill | the motion, given the decisions; not the decisions | no: passes by construction |
| LS1.4 differs from route 2 | for that skill, little; for sacrifice and converge, close to route 2 | not at all (zero correction = route 2) |
| LS2 can move a switch | only through the untested sigmoid hook above | as hard as in LS1 (the correction must learn the jump) |
| Export | sort-free and eye-free features; parity first tested in 0d | three scripts need a traceable copy; parity unshown |
| Route page's "only as teachers" | narrowed for that skill | contradicted |

On these criteria R4 for sacrifice and converge is close to the residual design for those two skills: both put the
decision logic in the graph and leave LS2 to move the switches. The difference is that R4 still distils the motion and
keeps C4. Decision 3 says so.

### 6.5 What the residual option would change

The scripts plus a correction that starts at zero
(`skill = clamp(script_z(obs, slot) + C(obs, slot, z)) × alive`):

- LS1 passes by construction and becomes a plumbing and export check; it no longer shows that a network can carry the
  skills. 0 GPU-h for LS1.1.
- C4 must be redefined (e.g. the correction's body alone), an owner decision against R49's "controls stay".
- The scripts go inside the ONNX graph: three need a traceable copy (`eye` at scripted.py line 261, `argsort` at 336 and
  451 to 452, checked by the writer), and onnxruntime parity near switches is unshown.
- LS1.4 reproduces route 2 (with a zero correction the network is route 2), so its 4.0 GPU-h would buy a plumbing check.
- LS2 fits best (the tie is ‖C‖²); moving a switch is as hard as in LS1. LS3 codes start from a zero base.
- It contradicts the route page's "only as teachers" and narrows "no port of the scripts".

## 7. Decisions for the owner, and open questions

| # | Decision | When | Lead's recommendation |
|---|---|---|---|
| 1 | The pilot plan, its marks and its cost (section 4): about 5 to 7 h of agent time to write, about 9 to 16.5 h of CPU (up to about 29) one job at a time, about 4 to 8.5 h of wall clock (up to about 15) with 4 jobs side by side (4.6); the headroom marks of 4.4 are the lead's rule, stricter than R48's 30, and decide MARGINAL against PASS | before the first run (R49 approved trials in principle, not this plan) | run as written |
| 2 | R3: the scripts' switch distances as network inputs, for the skills that need them | after the pilots, only if needed | accept: thresholds stay learnable for LS2 |
| 3 | R4: the scripts' choices and flags as inputs, with one head per branch, for the skills that need them. For these skills the network copies the scripts' motion given the scripts' decisions; the decision logic is in the exported graph. For sacrifice and converge this makes route 3 close to route 2 (6.4), and the skill's own switch points are fixed until LS2's sigmoid hook is shown to work (6, the pre-LS1.4 check) | after the pilots, only if needed | accept only for skills that fail R1 to R3, with the plain scope sentence added to the route page; if declined, the classify-then-regress trial (4.5) |
| 4 | The [K, 4] mask: exact zeros by design; the zero-skill and unused-channel limits then pass by construction and test the mask, not learning; vz and yaw locked until the LS2 note; pinned to team size 3 and the Starling setting, rebuilt (or removed for parked_centre) if team sizes are drawn (6) | with the build | accept |
| 5 | The gate file: the `[stop]` fix_round text rewritten to record R49; new sha; FORMAT 2; format-1 networks refused | with the build | accept; the owner words the `[stop]` text |
| 6 | A MARGINAL pilot (gate limits met, headroom missed) | after the pilots, only if it happens | build, because the read of record decides and the build costs about 0.1 to 0.9 GPU-h; with the risk stated |
| 7 | The residual design, if nothing passes | after the pilots, only then | bring it with its own costs (C4 redefinition, scripts in the graph, LS1.4 as a plumbing check) |
| 8 | guard_field at R2: the nearest-first order equals the script's own choice for field, so a field pass at R2 is not "own point of view" only | after the pilots, if guard_field passes at R2 | accept, reported as a script choice for that one skill (R2 is generic ordering for every other skill); if declined, the R1-only fallback of 4.5 (guard_field refitted at R1 alone, the Guard team replayed in full at both seeds) |
| 9 | One team passes, the other fails: build the passing team now, or wait | after the pilots, only if it happens | wait: head training needs both teams (route page); record the passing team's result |
| 10 | How many redesign rounds before the residual design: a second pilot round (R4 with Fourier features on a team FAIL, the classify-then-regress head for a skill whose R4 the owner declined, or both together as one round) or the residual design straight away. Each round's marks are 4.4's, unchanged, at two seeds (4.5) | after the pilots, only on a team FAIL or a declined decision 3 | at most one second round in all, the classify-then-regress trial included, then the residual design |

The LS1.1 cap (5.3) is the lead's call under R39 and is announced, not asked.

**Open questions**

1. **Task key.** The rebuilt LS1.1 is assumed to run under the existing key `LS1.1` (cap 0.8, 0.628 left). A new key
   (e.g. `LS1.1R`) would need `TASK_IDS["LS"]` in [config.py](../../source/svg_training/ste/config.py) line 51, a cap
   entry, and `tests/test_ste_config.py`; not checked.
2. A from-scratch decaying fit is untested; only tails on a trained network were (1.5).
3. Why the constant offsets appear on the Guard team only is unexplained; the mask makes yaw moot, not xy.
4. atan2 and the R4 flags under onnxruntime near ±π and at switch margins: first tested in 0d.
5. The GPU cost of the per-skill network in LS1.4: measured at the 5.2 smoke.
6. Closed-loop amplification of mixed error: single-kind rungs were optimistic (44 against 24 to 37); only Stage 2
   measures it, and only on LS1.1's data.
7. Scope: every geometric fact was checked at 3v3 with the zone at the arena centre (constant stand-off 2.6, ring radius
   0.8, parked_centre zero at team size ≥ 2). The features use the general formulas, but other sizes and zone positions
   are untested, and the mask is tied to the pinned team size and Starling setting (section 6, decision 4).
8. Residual hard spots: the steep gain of parked_ring and mirror (choices held, 0.0525 and 0.0216 at 10 mm, about 4
   per metre from the 0.25 m steer ramp), converge's pace ratio (0.0169 at 10 mm, 0.0017 at 1 mm, choices held),
   parked_ring's after-loss 3-fold mean (0.006 to 0.085 % of rows), mirror's velocity term, and the Guard zone-line
   frame at ρ < 0.5 m.
9. Whether R2's nearest-first order counts as "own point of view" for guard_field (it equals the script's choice
   there): decision 8.
10. Two seeds for every assembly that reaches PASS or MARGINAL, and LS1.1's rows (plus, only after a DAgger rescue,
    one fresh round from the pilot network): a pilot pass is a go for the build, not a prediction of the copy check.

## 8. Method and sources

**How the note was made.** Three scouts (the contract and cost of change; the scripts' geometry; the targets and
evidence) worked read-only on the CPU (6 threads, scratch only). Three designers (Faithful, Fidelity, Residual) wrote
designs from the scouts' reports; a judge scored them and recommended the combination taken in section 2. The writer
(Opus 5.5) wrote this note. Nothing was run of record; no GPU was used.

**Re-checked by the writer for this note** (read-only):

- Finding (a) and every T94 count in 1.1, 1.2, 4.2 and 4.4 (cells, medians, over 20, over 30, the 44, 122 and 64
  cells, the C4 and C5 counts, cells per skill): `runs/2026-11-26_ste_ls12_read_{guard,strike}/results.json`.
- The calibration table in 1.3: the record's lines 148 to 168, and the over-20 counts from
  `runs/2026-11-25_ste_ls15_calibration_{guard,strike}/results.json`.
- T93's round seconds, the GPU-hour accounting and the 0.172 used: the
  [distil read record](../../records/2026-11-26_ste_ls1_distil_read_record.md); the cap: `[budget_ls]` in
  [ste_learning.toml](../../configs/ste_learning.toml).
- F2's last readings (0.0532 at 57,500 steps, 0.0448 at 60,000; 2,605 s):
  [pilot_F2.log](../../records/evidence/2026-11-26_ste_ls1_fix_diagnosis/pilot_F2.log).
- The stored rows' fields: `runs/2026-11-26_ste_ls11_distil_strike/data/round_3.pt`.
- The scripts' constants and the `eye`/`argsort` lines: [scripted.py](../../source/svg_training/opponents/scripted.py)
  lines 17 to 18, 242 to 252, 261, 336, 451 to 452.
- The route page's wording (lines 59, 74, 86, 93) and R47, R49 in the
  [DISCUSSION](../DISCUSSION_2026-11-19_20.md).
- For the fixes of the focused re-review (26 Nov 2026): the pooled difference equals the mean of the gated cells'
  `diff` (T94 `results.json`: Guard −0.00238, Strike −0.00887); the read's starts are seed 110000 (T94 `layout.json`);
  `end_time_gated` is false and the failure kinds are those of `limit_failures`
  ([distil_gates.toml](../../configs/ste_ls1/distil_gates.toml), [ste_ls1_equivalence.py](../../scripts/ste_ls1_equivalence.py));
  `round_seed` mixes (seed, round, purpose), `collect` takes any round index, and `keep` weights rows by the flying
  network's error ([distil.py](../../source/svg_training/ste/distil.py)); `CommandPerturbation`'s kinds, uniform
  noise, +size bias, anticlockwise turn and per-wrapper clamp, and the calibration's seed rule
  ([perturbed.py](../../source/svg_training/opponents/perturbed.py), [ste_ls1_calibration.py](../../scripts/ste_ls1_calibration.py),
  [calibration.toml](../../configs/ste_ls1/calibration.toml)); seed 151003 appears nowhere in `configs`, `source` or
  `scripts`.

**Taken from the scouts, not re-run by the writer (scout scratch).** Contract scout: `fwd_variants.py`,
`onnx_check.py`, `onnx_frame.py` (timings, ONNX results, the contract map). Geometry scout (folder `redesign/`):
`geo.py`, `run_jitter.py` → `out_jitter.log`, `run_frames.py` → `out_frames.log`, `run_ring.py` → `out_ring.log`,
`run_closed.py` → `out_closed.log`. Targets scout (folder `redesign/`): `a_cells.py` / `a_cells.out`, `a_calib.py` /
`a_calib.out`, `b_lrtail.py` with `b_guard.log` and `b_strike.log`, `c_predict.py` / `c_predict.out`, `d_rank.py` /
`d_rank.out`, `e_decomp.py` / `e_decomp.out`, `f_tailbias.py` / `f_tailbias.out`, `g_ownrows.py` / `g_ownrows.out`. These
are in the session's scratch folder, outside the repository: the geometry and targets scouts' files in its
`redesign/` folder, the contract scout's three files at its top level. The contract scout saved scripts only, no
logs: its timings (13.2 against 2.2 ms, 0.55 to 0.9 times), the ONNX difference of 3.6e-7 and the `Sort`/`EyeLike`
refusals have no saved output and are re-run when the files are copied. **Copying them to
`records/evidence/2026-11-26_ste_ls1_redesign_scouts/` (with a README) is a step before the pilots start (section 4),
not a later task**; until then the numbers they carry, and the pilot marks that rest on them, are draft.

**Literature** (the targets scout; [S] confirmed in a web search on 26 Nov, [M] from memory): spectral bias of MLPs,
Rahaman et al. 2019 [S]; Fourier features, Tancik et al. 2020 [S]; implicit behavioural cloning, Florence et al. 2021
[S]; Behavior Transformers, Shafiullah et al. 2022 [S] (classify the branch, then regress the offset); agent-centred
views, the MAGICAL benchmark [S]; policy distillation, Rusu et al. 2015, and Actor-Mimic, Parisotto et al. 2015 [S];
Distral, Teh et al. 2017 [S]; PCGrad, Yu et al. 2020 [S] (gradient conflict between tasks); residual policy learning,
Silver et al. 2018 [S]; MCP, Peng et al. 2019 [S]; DAgger, Ross et al. 2011 [S]; cosine decay, Loshchilov and Hutter
2017 [M]. They support a per-skill network or head against interference, frame inputs, branch classification at
discontinuities, and a decaying rate for precision; none was tested on this game.

**Wording.** Strike team, Guard team, tag, reach the zone. Results are observed in the training simulator. Labels:
estimate = projected, not measured; scout scratch = measured by a scout, not re-run here; INFO = not of record.
