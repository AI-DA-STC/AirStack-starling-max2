INTERNAL · the options for the owner's ruling R38: the 17 owner keys of the LS1 copy check (`configs/ste_ls1/distil_gates.toml` on branch `ls1-m2`, all `FILL_OWNER_R38` today) and OQ-3 (alpha, interval, correction), read from the calibration LS1.5 (25 to 26 Nov 2026); written by the analyst (Opus 5.5), reviewed by two reviewers (numbers, completeness; Sonnet 5.5) on 26 Nov 2026 and revised; no value is set until the owner rules · [README.md](README.md); the run: [record](../../records/2026-11-26_ste_ls15_calibration_record.md); the rules the limits go into: [LS1_TASK_PLAN.md](LS1_TASK_PLAN.md) constraint 5, C7, M2-T1, M2-T5, M2-T6, OQ-3; [LS_EXECUTION_WORKFLOW.md](LS_EXECUTION_WORKFLOW.md) section 5

# LS1 pass limits: options for the owner (R38)

Training simulator, tier 1 (fast engine, Starling layer, exploratory PX4 model); every number here is observed in the
training simulator. Nothing here is a flight result.

**In short (the recommended values; details and alternatives below).** A "cell" is one line-up of the copied team
against one opposing script, played on the same 1,000 starts as the scripts. "Win share" is always that of the team being
copied (the Guard team's holds, or the Strike team's reaches of the zone).

- A cell may change at most **30** of its 1,000 games (`flips_max_games`).
- In each cell the copy's win share may differ from the scripts' by at most **0.045** (4.5 points), allowing for chance
  (`cell_margin`); over all cells together by at most **0.01** (1 point, `pooled_margin`).
- The copy's command may differ from the scripts' by at most **0.05** (RMSE, command units) on a channel the skill uses;
  at most **0.05** on a channel it never uses; at most **0.005** for the parked Guard skill, whose scripted command is 0.
- The end time of games is reported, not gated (threshold **3.0** ticks recorded for later).
- The gate's own checks: a wrong-skill copy, and an untrained one, must miss at least **15** of 30 cells; a steady error
  of **bias 0.05** or a **6°** turn, or a moved switch point (sacrifice **0.6109** rad, converge **0.15** rad), must fail;
  random noise **0.02** must pass. Flank and field switch sizes: a short CPU top-up read first (separate decision; if
  declined, flank **0.4** m and field **1.3** m, with the consequence in group E).
- Statistics: alpha **0.05**, Newcombe's paired interval, Bonferroni over each side's cells (the only ones built).

Glossary: **RMSE**, the root-mean-square difference between the copy's and the scripts' command on the same states;
**parked skill**, `guard_parked_centre`, which holds still (command exactly 0); **near-miss control**, the gate playing
the scripts with a small deliberate error on a few chosen cells, to show that it fails an error of that size (C6) and
passes random noise (C7); **switch**, a point inside a script where it changes what it does (for example the bearing at which
a Strike drone of `strike_sacrifice` turns in toward the zone); **pooled**, all of a side's gated cells taken together.

## 1. What the limits are for, and what the calibration measured

Route 3 copies each team's hand-written scripts (5 Guard team skills, 6 Strike team skills) into one network per team.
Before anything is trained on that network, the read LS1.2 asks one question: does the copy play like the scripts? It
plays the copy and the scripts on the same 1,000 starts per cell (150 Guard cells, 130 Strike cells) and counts the games
that came out differently. The 17 owner keys (`FILL_OWNER_R38` in the gate file; plus the three OQ-3 settings alpha,
interval and correction) decide how close is close enough: how large a command error is allowed, how many
games per cell may change, how far the copy's win share may drift from the scripts' in one cell and over all cells, and
how large the deliberate errors of the gate's own checks must be (an error the gate must catch, and a small random error it
must let through). The calibration LS1.5 measured these numbers without any network: the scripts played against
deliberately changed copies of themselves (random noise on the commands, a steady bias, the commands scaled by 0.95,
turned by a few degrees, and moved switch points inside four scripts), 1,000 games per cell on the gate's own cells and
starts, read with the gate's own statistics. It shows which sizes of error change which games. It does not pass or fail
anything.

How to read the numbers below:

- **Games changed (flips)**: in one cell, games the copy lost that the scripts won (b) plus games it won that the scripts
  lost (c), of 1,000.
- **Net difference**: c − b, as games of 1,000 or as a share (c − b) / 1,000. Negative: the changed copy wins less.
- **Margin needed**: the smallest `cell_margin` (or `pooled_margin`) that the cell's (or the pooled row's) interval fits
  inside. The gate passes a cell when its whole interval lies inside ± the margin, so this is the number to compare with a
  margin. Per cell at the corrected z (Guard 3.5879, Strike 3.5504, `results.json` `intervals`); pooled at 1.96.
- **Gated cells only.** The Strike team's `results.md` rows include 26 INFO cells against `guard_mark_inside` (not gated,
  not read by the gate). The medians and maxima in this page are over the gated cells (Guard 150, Strike 130; the switch
  arms only on the cells where their code flies), computed from `results.json`; some Strike rows therefore differ from
  `results.md` (for example `converge_gather_rad=0.2`: largest flips 30 on gated cells, 51 with the INFO cell).
- **Near-miss cells**: the 4 Guard and 5 Strike cells of `distil_gates.toml [read.near_miss_cells]`, on which the gate's
  near-miss controls C6 (must FAIL) and C7 (must PASS) play. The calibration played every one of them in every arm. Their
  per-cell numbers come from `results.json`; their pooled rows exist in no file: the analyst recomputed them from the batch
  files (`batch_*.npz`) and T44 with the calibration's own functions (`ste_ls1_calibration.reference_of`, `_wins`,
  `cells.pooled_difference` at z 1.96), read-only, after checking that b and c match `results.json` on every cell.

## 2. What each size of error did

Gated cells; "games changed" = flips per cell (median / largest); "largest net" = the largest |c − b| in one cell (games of
1,000); pooled = the mean difference over all gated cells with its 95 % interval; RMSE = the largest command RMSE of any
skill on a channel it uses (command units; the command is clipped to [−1, 1]). Source: `results.json` of each run.

**Guard team** (150 cells; zero-command and field arms on 6 cells)

| Error injected | Games changed median / largest | Largest net | Pooled difference [95 %] | RMSE |
|---|---|---|---|---|
| none (identity) | 0 / 0 | 0 | +0.0000 | 0 |
| noise 0.01 | 1 / 6 | 6 | −0.0003 [−0.0005, −0.0000] | 0.0058 |
| noise 0.02 | 3 / 11 | 6 | −0.0005 [−0.0009, −0.0002] | 0.0116 |
| noise 0.05 | 7.5 / 21 | 10 | −0.0015 [−0.0021, −0.0009] | 0.0289 |
| noise 0.1 | 15 / 37 | 16 | −0.0034 [−0.0044, −0.0024] | 0.0578 |
| noise 0.05, used channels only | 6 / 20 | 9 | −0.0016 [−0.0022, −0.0011] | 0.0289 |
| bias 0.01 (x, y) | 9 / 31 | 15 | −0.0001 [−0.0010, +0.0008] | 0.0100 |
| bias 0.02 | 17 / 63 | 21 | −0.0009 [−0.0023, +0.0004] | 0.0200 |
| bias 0.05 | 38 / 150 | 63 | −0.0044 [−0.0070, −0.0017] | 0.0500 |
| bias 0.0025 on the parked skill only | 2 / 9 | 5 | +0.0000 [−0.0015, +0.0015] | (largest output 0.0025) |
| bias 0.005 on the parked skill only | 5.5 / 15 | 9 | +0.0003 [−0.0017, +0.0024] | (0.005) |
| bias 0.01 on the parked skill only | 12.5 / 21 | 15 | −0.0017 [−0.0047, +0.0014] | (0.01) |
| scale 0.95 | 17 / 49 | 25 | −0.0066 [−0.0080, −0.0051] | 0.0354 |
| turn 1.5° | 9 / 34 | 13 | −0.0001 [−0.0010, +0.0009] | 0.0185 |
| turn 3° | 17 / 52 | 12 | −0.0005 [−0.0020, +0.0011] | 0.0371 |
| turn 6° | 30.5 / 94 | 23 | −0.0020 [−0.0043, +0.0002] | 0.0741 |
| field range 1.1 → 1.2 m | 1 / 3 | 1 | −0.0005 [−0.0014, +0.0004] | 0.0217 |
| field range 1.1 → 1.3 m | 7 / 9 | 8 | −0.0050 [−0.0075, −0.0025] | 0.0523 |

**Strike team** (130 cells; sacrifice and converge arms on 5 cells, flank arms on 65)

| Error injected | Games changed median / largest | Largest net | Pooled difference [95 %] | RMSE |
|---|---|---|---|---|
| none (identity) | 0 / 0 | 0 | +0.0000 | 0 |
| noise 0.01 | 5 / 18 | 14 | −0.0004 [−0.0009, +0.0001] | 0.0057 |
| noise 0.02 | 8 / 27 | 21 | −0.0029 [−0.0036, −0.0022] | 0.0114 |
| noise 0.05 | 13 / 37 | 25 | −0.0050 [−0.0061, −0.0039] | 0.0284 |
| noise 0.1 | 18 / 56 | 32 | −0.0062 [−0.0077, −0.0047] | 0.0564 |
| noise 0.05, used channels only | 13 / 37 | 25 | −0.0050 [−0.0061, −0.0039] | 0.0284 |
| bias 0.01 (x, y) | 9 / 20 | 13 | −0.0029 [−0.0040, −0.0018] | 0.0099 |
| bias 0.02 | 13 / 24 | 14 | −0.0042 [−0.0055, −0.0029] | 0.0198 |
| bias 0.05 | 31 / 58 | 20 | −0.0071 [−0.0095, −0.0046] | 0.0492 |
| scale 0.95 | 17 / 43 | 32 | −0.0096 [−0.0113, −0.0080] | 0.0355 |
| turn 1.5° | 10 / 21 | 10 | +0.0003 [−0.0008, +0.0015] | 0.0186 |
| turn 3° | 19.5 / 38 | 13 | +0.0009 [−0.0008, +0.0026] | 0.0371 |
| turn 6° | 38 / 75 | 23 | +0.0001 [−0.0027, +0.0028] | 0.0742 |
| sacrifice entry 30° → 35° | 7 / 12 | 12 | +0.0024 [−0.0001, +0.0049] | 0.1298 |
| sacrifice entry 30° → 40° | 17 / 22 | 12 | −0.0016 [−0.0056, +0.0024] | 0.1756 |
| converge gather 0.1 → 0.15 rad | 14 / 23 | 8 | −0.0004 [−0.0042, +0.0034] | 0.1329 |
| converge gather 0.1 → 0.2 rad | 29 / 30 | 6 | +0.0040 [−0.0011, +0.0091] | 0.2327 |
| flank margin 0.3 → 0.35 m | 4 / 15 | 7 | −0.0004 [−0.0010, +0.0001] | 0.0095 |
| flank margin 0.3 → 0.4 m | 5 / 20 | 12 | −0.0012 [−0.0019, −0.0005] | 0.0188 |

What stands out:

- **Random error hurts the Strike team more than the Guard team.** Noise 0.02 changes at most 11 games in a Guard cell and
  27 in a Strike cell, and costs the Strike team 0.29 points of win share over all cells (−0.0029). The most sensitive
  Strike cells fly `strike_low` against `guard_mark_edge` or `guard_mirror` (noise 0.02: 24 lost and 3 won in
  `[strike_low, strike_straight, strike_straight]` v `guard_mirror`).
- **A steady error hurts the Guard team more.** Bias 0.05 changes up to 150 games in one Guard cell. Even bias 0.01 changes
  up to 31 games in a Guard cell against `strike_converge`, all of them cells where the parked skill flies (for example
  `[guard_mark_edge, guard_parked_centre, guard_parked_centre]`: 13 lost, 18 won), and 21 in the fixed parked cell (18
  lost, 3 won): the parked skill drifting.
- **Turns change many games in both directions** (b close to c): their pooled difference stays near 0 while the games
  changed per cell grow fast. The games-changed limit sees them; the net-difference limits do not.
- **Moved switch points have a large command error and a small effect on play.** Converge 0.2 rad has the largest RMSE of
  any arm (0.2327) yet changes at most 30 games in a cell and moves the pooled share by +0.0040. On these starts the
  games are not sensitive to where those switches sit.
- **Random output on unused channels did not matter.** Noise 0.05 on all four channels and noise 0.05 on each skill's used
  channels only gave the same Strike numbers (largest 37, pooled −0.0050 both) and almost the same Guard numbers (21 v 20,
  −0.0015 v −0.0016).

## 3. The wrong-skill copy (code permutation)

The copy is checked to fly the right skill for each code: a copy that flies code k+1's skill when asked for code k must
miss. The calibration read this from T44 alone, with no play: in each of the 30 fixed cells per side, the games of the
skill actually flown were paired with the games of the skill asked for (permutation `cells.toml [permutation]`: Guard
`[1, 2, 3, 4, 0]`, Strike `[1, 2, 3, 4, 5, 0]`). `results.md` reports cells whose corrected interval excludes 0 (Guard 19
of 30, Strike 21 of 30); the gate counts a different thing, a cell that **fails the per-cell limits** (games changed above
`flips_max_games` or interval outside ± `cell_margin`). Counted that way (analyst, from `results.json` `permuted`):

| Per-cell limits (flips, margin) | Guard cells missed of 30 | Strike cells missed of 30 |
|---|---|---|
| 25, 0.035 | 24 | 29 |
| 30, 0.045 (recommended below) | 22 | 29 |
| 40, 0.045 | 22 | 29 |
| 40, 0.05 | 21 | 28 |
| 60, 0.05 | 19 | 25 |

The Guard cells that do not miss at 30 / 0.045 are the 8 where the swapped skills play alike: `guard_parked_centre`
flown as `guard_parked_ring` (5 cells, 3 to 22 games changed) and `guard_mark_edge` flown as `guard_mirror` against
`strike_straight`, `strike_high` and `strike_low` (20 to 26 games). The Strike side misses in all but one cell
(`strike_high` flown as `strike_low` v `guard_field`, 5 games). One key, `permuted_min_miss_cells`, serves both sides and
both controls: C3 (these permuted scripts, an exact count) and C5 (the permuted network, whose count moves with the
network's own error). It must sit under the Guard count with room to spare.

## 4. Five facts that shape every option

1. **Many cells against few.** The copy is judged on 150 (Guard) or 130 (Strike) cells, and a single cell over a limit
   fails it. The near-miss controls are judged on 4 or 5 cells. So the largest number a small acceptable error produces
   over 130 cells can exceed the largest number a large error produces over 5 cells. Example: Strike noise 0.02 changes up
   to 27 games over the 130 cells; Strike turn 3° changes at most 20 on its 5 near-miss cells. No games-changed limit can
   let the first through and stop the second. This is why the workflow's proposed 3° near miss does not work (section 5,
   group D).
2. **C6 and C7 are judged on every limit, command error included.** The read's importable part landed on branch `ls1-m2`
   while this page was written (`41eec3b1`, `df24386a`, 26 Nov 2026; `scripts/ste_ls1_equivalence.py`, task M2-T5; the
   read itself, M2-T6, is not built). Its `near_miss_control` passes the near-miss arm's cells, pooled row and
   command-error table to `limit_failures`, and the arm's changed players record their command error
   (`RecordingPlayer` with the per-slot recorders). So C6 fails when **any** limit is crossed (games changed, cell margin,
   pooled margin, end time if gated, or a command-error limit), and C7 passes only when **none** is. Its noise arm (C7)
   plays on each skill's used channels only, and the parked skill flies unchanged (the calibration's `noise_active`
   rule), so the C7 noise has no unused-channel or parked-skill output. The checks in sections 5 and 6 use this rule;
   the command errors on the near-miss cells were recomputed for this page from the batch files' accumulators
   (`err_sum_sq`, `err_max_abs`, `err_count`), the calibration's own per-cell record.
3. **The pooled row of a near-miss arm.** `interval_step` (the same file) pools over the cells it is given, at z 1.96;
   M2-T6 is expected to give it the arm's own near-miss cells. For a switch arm that is one or two cells, and the pooled
   interval at 1.96 is narrower than the per-cell interval at 3.55, so the pooled margin trips before the cell margin.
   No recommended near-miss value below relies on a pooled trip alone.
4. **Steady errors replay exactly; noise does not.** Bias, turn and switch arms draw nothing at random; on the CPU, on the
   same starts and cells, the gate should reproduce the calibration's games (the calibration's identity arm equalled T44
   game for game in every fixed cell, `controls.json` `replay_t44`). The near-miss check for them is therefore a
   prediction, an expectation the read itself confirms. The gate's noise arm draws from seed 150007 (`[read] noise_seed`),
   the calibration's from 150101: the C7 numbers are an estimate, not a replay.
5. **A perfect copy needs a margin.** With 0 games changed, a cell's corrected interval is still up to ±0.0124 (Guard) and
   ±0.0121 (Strike) wide (identity arm). Any `cell_margin` at or below these fails a copy identical to the scripts.

## 5. Key by key, in groups

Wording: "lets through" = a copy whose error is like that arm would pass that limit on the copy's own read (R1, all
gated cells); "stops" = would fail it. Each option is judged on the calibration's arms; a network's error is not one of
them (section 8).

### Group A: command error (`cmd_rmse_max`, `cmd_unused_max_abs`, `cmd_zero_skill_max_abs`)

Read on the copy's own fixed cells, on the states it reached, against the scripts' commands on those states (plan
OP-16). They also act on the near-miss controls (section 4, fact 2): a near-miss arm's command error is read on its own
near-miss cells.

**`cmd_rmse_max`**: the largest RMSE allowed for any skill on any channel it uses.
Evidence: section 2, RMSE column. Every evenly spread error with an RMSE of 0.05 or more (noise 0.1, turn 6°, bias 0.05)
already fails on play under the group B limits recommended below. The only calibrated errors that the play limits let
through and RMSE sees are the moved switches: Strike sacrifice and converge (RMSE 0.130 to 0.233) and Guard field range
1.3 m (0.0523).

| Option | Value | Lets through | Stops |
|---|---|---|---|
| strict | 0.03 | noise ≤ 0.05 (0.0289), bias ≤ 0.02, turn 1.5°, flank both, field 1.2 m | turn 3° (0.0371), scale 0.95 (0.035), bias 0.05, noise 0.1, turn 6°, field 1.3 m, every sacrifice and converge rung |
| **middle, RECOMMENDED** | **0.05** | the above plus turn 3°, scale 0.95, Strike bias 0.05 (0.0492) | noise 0.1 (0.058), turn 6° (0.074), Guard bias 0.05 (0.0500000005, on the line), field 1.3 m (0.0523), every sacrifice and converge rung (≥ 0.1298) |
| lenient | 0.10 | everything above, field 1.3 m | only the sacrifice and converge rungs |

Why 0.05: it is the workflow's starting point and the one limit that stops, in the copy's own read, the switch-type errors
the play limits let through. It is also what makes the switch near misses of C6 fail: on their near-miss cells the first
sacrifice and converge rungs have an RMSE of 0.1203 and 0.1198 (group E). The cost: a network whose error is concentrated at switch points may show an RMSE above 0.05
while playing like the scripts, and fail for a reason the games do not show. The fit report of LS1.1 (`final.per_skill`
RMSE, before the read) shows this coming.

**`cmd_unused_max_abs`**: the largest output allowed on a channel a skill never uses (Guard skills: vz and yaw rate;
`strike_high` and `strike_low`: yaw rate; the other Strike skills: vz and yaw rate; labels in `results.md`).
Evidence: noise on all channels and noise on used channels only gave the same play (section 2). No steady output on an
unused channel was calibrated.

| Option | Value | Lets through | Stops |
|---|---|---|---|
| strict | 0.02 | random output up to ±0.02 there (noise 0.02's largest: 0.0200) | noise 0.05 and above on those channels |
| **middle, RECOMMENDED** | **0.05** | random output up to ±0.05 (noise 0.05's largest: 0.0500), shown not to change the games | noise 0.1 (0.1000) |
| lenient | 0.10 | random output up to ±0.1 | nothing calibrated |

Why 0.05: the largest output on unused channels that the calibration shows has no effect on play. It is a largest value
over every row, so a network with a quiet output and a few rare spikes is judged by the spikes.

**`cmd_zero_skill_max_abs`**: the largest output allowed from the parked skill whose scripted command is exactly 0
(`guard_parked_centre`; the Strike team has none, labels in `results.md`).
Evidence: the parked-skill bias ladder on its 6 cells; under bias 0.01 on all Guard cells, the fixed parked cell against
`strike_converge` changed 21 games (18 lost, 3 won) and needs the largest margin of that arm (0.0375). Random output there did not matter (noise 0.05 against
noise 0.05 on used channels only, section 2).

| Option | Value | Lets through | Stops |
|---|---|---|---|
| strict | 0.0025 | a steady parked-skill drift of 0.0025 (9 games at most, pooled +0.0000) | drift 0.005 and above; random output above 0.0025 |
| **middle, RECOMMENDED** | **0.005** | drift 0.005 (15 games at most, pooled +0.0003 [−0.0017, +0.0024]) | drift 0.01 (21 games, pooled −0.0017); random output above 0.005 (so a Guard copy with noise 0.01 on every skill fails here alone) |
| lenient | 0.01 | drift 0.01 | random output above 0.01 |

Why 0.005: the workflow's starting point, and the largest rung at which the parked skill shows no net effect. It is
stricter than the play limits (which let a 0.01 drift through), because it is the only check on a parked drone's slow
drift. Note the clash it creates: it stops random output of 0.01 on the parked skill, which the calibration shows is
harmless to play. C7 is not affected: its noise leaves the parked skill unchanged (section 4, fact 2).

### Group B: games changed and net difference (`flips_max_games`, `cell_margin`, `pooled_margin`)

These three decide the copy's own read and, with group A, the near-miss controls too. They are best chosen together.

| Bundle | flips, cell, pooled | The copy: Guard lets through | The copy: Strike lets through | Near misses that fail on both sides (calibrated) |
|---|---|---|---|---|
| strict | 25, 0.035, 0.005 | noise ≤ 0.05, parked drift ≤ 0.005, field 1.2 m | noise 0.01, bias 0.01, turn 1.5°, sacrifice 35°, converge 0.15, flank both | bias 0.05, turn 6°; turn 3° (Guard by games, 33; Strike only by the pooled row, 0.0059). Bias 0.02 fails on both sides only by the pooled row (Strike 0.0059; Guard 0.005015, a hair over 0.005): not counted as failing |
| **middle, RECOMMENDED** | **30, 0.045, 0.01** | noise ≤ 0.05, parked drift ≤ 0.01, field both | noise ≤ 0.02, bias ≤ 0.02, turn 1.5°, every switch rung | bias 0.05, turn 6° |
| lenient | 40, 0.05, 0.015 | noise ≤ 0.1, bias 0.01, turn 1.5°, parked drift ≤ 0.01, field both | noise ≤ 0.05, bias ≤ 0.02, turn ≤ 3°, every switch rung | on play none: bias 0.05 (Strike 36 games) and turn 6° (Strike 38) pass; with `cmd_rmse_max` 0.05 turn 6° still fails on command error (0.0745), bias 0.05 does not (Strike 0.0491) |

(The last column counts the play limits only. Group A's limits act on top: under the recommended set the copy's read also stops Guard noise on
the parked skill above 0.005 and every sacrifice and converge rung, by command error. Full list in section 6.)

**`flips_max_games`**: the most games one cell may change. The sharpest of the play limits: it is the one that sees
turns.
Evidence: largest games changed per cell, section 2; on the near-miss cells (section 6): Guard bias 0.05 46, turn 3° 33,
turn 6° 48; Strike bias 0.05 36, turn 3° 20, turn 6° 38; noise 0.02 4 (Guard) and 12 (Strike).

| Option | Value | Lets through | Stops |
|---|---|---|---|
| strict | 25 | Guard noise ≤ 0.05 (21); Strike noise 0.01 (18), bias ≤ 0.02 (24), turn 1.5° (21) | Strike noise 0.02 (27); Guard bias 0.01 (31), turn 1.5° (34) |
| **middle, RECOMMENDED** | **30** | the above plus Strike noise 0.02 (27) and converge 0.2 (30) | Guard bias 0.01 (31) and turn 1.5° (34); Strike noise 0.05 (37), turn 3° (38) |
| lenient | 40 | the above plus Guard bias 0.01, turn 1.5°, noise 0.1 (37); Strike noise 0.05, turn 3° | Guard bias 0.02 (63), turn 3° (52); Strike bias 0.05 (58), turn 6° (75) |

Why 30: the largest round value that leaves at least 6 games of room on both calibrated steady near misses (bias 0.05,
turn 6°) on both teams' near-miss cells (Strike: 36 and 38 games, 6 and 8 above; Guard 46 and 48), while a Strike copy as good as noise 0.02 passes (27,
3 below; thin). At 35 the Strike bias near miss would fail by one game; at 40 it passes. The cost on the Guard side: bias
0.01 (31) and turn 1.5° (34) are stopped, both by their cells against `strike_converge`.

**`cell_margin`**: how far one cell's win share may differ from the scripts' (its whole corrected interval must lie
inside ± this). Floor: 0.0124 (a perfect copy, fact 5).
Evidence (margin needed, largest over the gated cells): Guard noise 0.02 0.0197, noise 0.05 0.0246, bias 0.01 0.0375,
bias 0.02 0.0459, turn 1.5° 0.0351, scale 0.0504; Strike noise 0.01 0.0317, noise 0.02 0.0419, noise 0.05 0.0490, bias
0.05 0.0484, turn 6° 0.0499. The workflow's starting point, 0.03, would stop a Strike copy with noise 0.01 (RMSE 0.006).
No calibrated near miss reaches 0.045 on its near-miss cells (largest: Guard bias 0.05, 0.0341).

| Option | Value | Lets through | Stops |
|---|---|---|---|
| strict | 0.035 | Guard noise ≤ 0.05; Strike noise 0.01, bias 0.01, turn 3° (0.0328) | Strike noise 0.02 (0.0419); Guard bias 0.01 (0.0375), turn 1.5° (0.0351) |
| **middle, RECOMMENDED** | **0.045** | the above plus Strike noise 0.02, bias 0.02 (0.0338); Guard bias 0.01, turn ≤ 3° | Strike noise 0.05 (0.0490), bias 0.05 (0.0484), turn 6°, scale; Guard bias 0.02 (0.0459), scale (0.0504), turn 6° (0.0544) |
| lenient | 0.05 | the above plus Strike noise 0.05, bias 0.05, turn 6° (0.0499) | Strike noise 0.1, scale (0.0562); Guard bias 0.05, scale, turn 6° |

Why 0.045: the smallest of the three that lets a Strike copy as good as noise 0.02 through (0.0419, 0.003 below; thin).
What it stops depends on the cell's win share: a cell whose change runs one way (b lost games, c = 0) needs more than
0.045 from about 23 to 27 lost games (2.3 to 2.7 points) upwards (estimate, the calibration's Newcombe function at the
corrected z, for win shares 0.1 to 0.97). So a cell can lose 2.5 points and pass: observed, Guard scale 0.95,
`[guard_field x3]` v `strike_straight`, b 25, c 0, margin needed 0.0436, 25 games changed (under 30). Any cell whose net
loss exceeds 30 games (3 points) fails the games-changed limit whatever its margin.

**`pooled_margin`**: how far the win share over all gated cells may differ from the scripts' (its interval at z 1.96 must
lie inside ± this; a copy that wins more also fails).
Evidence (margin needed): Guard largest 0.0080 (scale), bias 0.05 0.0070; Strike noise 0.02 0.0036, noise 0.05 0.0061,
bias 0.02 0.0055, bias 0.05 0.0095, scale 0.0113. On the near-miss cells: noise 0.02 0.0024 (Guard), 0.0037 (Strike).

| Option | Value | Lets through | Stops |
|---|---|---|---|
| strict | 0.005 | Guard everything but bias 0.05, scale and field 1.3 m (0.0075); Strike noise ≤ 0.02, bias 0.01, turns, sacrifice 35°, converge 0.15, flank both | Strike noise ≥ 0.05, bias 0.02 (0.0055), bias 0.05, scale, sacrifice 40° (0.0056), converge 0.2 (0.0091) |
| **middle, RECOMMENDED** | **0.01** | every calibrated arm but one | Strike scale 0.95 (0.0113) |
| lenient | 0.015 | every calibrated arm | nothing calibrated |

Why 0.01: within 10 wins per 1,000 games on average over all cells; it lets every Strike random-noise copy through with
room (noise 0.02 at 0.0036) and stops a copy that loses about 1 point everywhere. It rarely binds alone in the copy's read:
games changed and the cell margin bind first. This departs from the workflow (`LS_EXECUTION_WORKFLOW.md` section 5),
which illustrates the pooled row with "within 15 wins is 0.015 there": at 0.015 no calibrated arm is stopped, while 0.01
stops Strike scale 0.95 (0.0113), the only calibrated copy that loses about 1 point over all cells.

### Group C: end time (`end_time_gated`, `end_time_max_ticks`)

**What they control**: with `end_time_gated` true, a cell fails when the mean |difference of the tick each game ended| is
above `end_time_max_ticks` (a tick is 0.05 s, `core.game_config.TICK_S`, plan M2-T5). The number is required even when not gated.
Evidence (largest over the gated cells, ticks): Guard noise 0.02 1.59, noise 0.05 2.97, bias 0.01 2.83, turn 1.5° 3.90,
bias 0.05 28.35; Strike noise 0.02 1.13, noise 0.05 2.63, bias 0.02 4.28, converge 0.2 10.05. On the near-miss cells the
Guard team's largest is 0.75 ticks (turn 6°): against `strike_straight` the end time barely moves, so gating cannot make
a Guard near miss fail. On the Strike near-miss cells: bias 0.05 6.37, turn 3° 3.15, turn 6° 6.31, noise 0.02 0.84.

| Option | Value | Lets through | Stops |
|---|---|---|---|
| strict | gated, 2.0 | Guard and Strike noise ≤ 0.02 | Guard noise 0.05 (2.97), bias 0.01 (2.83); Strike noise 0.05 (2.63), bias 0.01 (2.04), sacrifice 40° (2.29) |
| middle | gated, 3.0 | the above plus Guard noise 0.05 (all channels 2.97, used channels only 2.96, by 0.03 and 0.04); Strike noise 0.05, bias 0.01, sacrifice | Guard turn 1.5° (3.90); Strike bias 0.02 (4.28), converge both (5.29, 10.05); near miss: Strike turn 3° (3.15, by 0.15) |
| **lenient, RECOMMENDED** | **not gated; 3.0 recorded** | (reported only) | (nothing) |

Why not gated: under the recommended groups A and B, gating at 3.0 would newly stop, in the copy's read, only Strike
bias 0.02 (4.28 ticks); the converge rungs it would also stop already fail on `cmd_rmse_max` 0.05 (RMSE 0.1329 and
0.2327), and Guard noise 0.05 on used channels (2.96) would still pass. Its one near-miss use would be a hair's margin
(Strike turn 3°, 3.15 v 3.0); and the number moves in games whose winner does not change, so a network that flies slightly
differently but wins and loses the same games would accumulate it. 3.0 is the value the middle option would gate, kept so
that switching it on later is a one-word change (a new hash).

### Group D: near-miss sizes that must FAIL (`bias`, `rotate_deg`) and must PASS (`noise`)

**What they control**: control C6 plays the scripts with a steady error of this size on the near-miss cells and must FAIL
the limits (proof that the gate can see a near miss); C7 plays them with random noise of this size and must PASS (proof
that it does not fail a near-perfect copy). One value serves both teams. They must sit just above what the limits let
through (`bias`, `rotate_deg`) and just below it (`noise`). Checked explicitly in section 6.

**`bias`** (steady, on x and y)

| Option | Value | What happens under the recommended limits |
|---|---|---|
| strict (smaller) | 0.02 | Guard fails, but only on the parked-skill output (0.02 > 0.005; 18 games); **Strike does not** (20 games, RMSE 0.0198): C6 would not FAIL, the read INCONCLUSIVE (exit 6) |
| **middle, RECOMMENDED** | **0.05** | FAILS on both: Guard 46 games (16 above), pooled 0.0148 > 0.01, parked-skill output 0.05 > 0.005; Strike 36 games (6 above; RMSE 0.0491, just under 0.05). The first calibrated rung the copy's read also stops on both teams (Guard 150 games, Strike 58) |
| lenient (larger) | 0.08 | not calibrated; expected to fail with more room (estimate, from the rise 0.02 → 0.05) |

**`rotate_deg`** (a turn of x and y)

| Option | Value | What happens under the recommended limits |
|---|---|---|
| strict (smaller) | 3.0 (the workflow's proposal) | Guard fails (33 games, 3 above); **Strike does not** (20 games, RMSE 0.0372): C6 would not FAIL, INCONCLUSIVE. The copy's read stops 3° on both teams (Guard 52, Strike 38): the near-miss cells are not where a 3° turn shows |
| **middle, RECOMMENDED** | **6.0** | FAILS on both, on two limits each: Guard 48 games (18 above), Strike 38 (8 above); RMSE 0.0745 and 0.0743 > 0.05 |
| lenient (larger) | 9.0 | not calibrated; expected to fail with more room (estimate) |

**`noise`** (random, must PASS; as built, on each skill's used channels only, the parked skill unchanged: fact 2)

| Option | Value | What happens under the recommended limits |
|---|---|---|
| strict (smaller) | 0.01 | passes with the most room (Guard 2 games, Strike 7) but proves less: the copy's read lets more than this through |
| **middle, RECOMMENDED** | **0.02** | passes: Guard 4 games, cell 0.0148, pooled 0.0024, RMSE about 0.0113; Strike 12 games, cell 0.0228, pooled 0.0037, RMSE about 0.0115 (limits 30, 0.045, 0.01, 0.05); no unused-channel or parked-skill output. The largest calibrated rung the play limits let through on both teams in the copy's read (Strike noise 0.05 is stopped there, 37 games), so "just below" in that nominal sense only: on the near-miss cells C7 would also pass noise 0.05 (next row). Estimate: the calibration played 0.02 on all four channels (with another seed); the used-channels-only rule was calibrated at 0.05, where it changed the same games as all-channel noise on the Strike team and almost the same on the Guard team |
| lenient (larger) | 0.05 | passes on the near-miss cells (used channels only: Guard 10 games; Strike 18 games, pooled 0.0079 v 0.01) but is above what the copy's read lets through on the Strike team (37 games): not "just below" |

What C7 shows, then: that the gate does not fail a small random error on the near-miss cells. It does not show where
the gate's sensitivity ends: on 4 or 5 cells, 12 games (Strike) of a limit of 30 is far from the limit, and noise 0.05
would pass C7 (Strike 18 games, pooled 0.0079) although the copy's read over all 130 Strike cells stops it (37 games;
section 4, fact 1).

In the copy's own read, a Guard copy with random output of 0.01 or more on the parked skill fails
`cmd_zero_skill_max_abs` 0.005 (section 6); C7 does not test that, because its noise leaves the parked skill unchanged.

### Group E: moved-switch near misses that must FAIL (`sacrifice_entry_rad`, `converge_gather_rad`, `flank_margin_m`, `field_range_m`)

**What they control**: one C6 arm per moved switch, each at its value in its player's unit, played on the near-miss cells
where its code flies (Guard: `guard_field` v `strike_straight`, 1 cell; Strike: sacrifice 1 cell, converge 1 cell, flank 2
cells). Each must FAIL.

On their near-miss cells the calibrated rungs change few games; what makes two of them fail is their command error
(RMSE on the near-miss cells, recomputed for this page from the batch files):

| Key (today's value) | Rung | Games changed | Cell margin needed | Pooled needed | RMSE | Under the recommended limits |
|---|---|---|---|---|---|---|
| `sacrifice_entry_rad` (0.5236 = 30°) | 0.6109 (35°) | 7 | 0.0159 | 0.0062 | 0.1203 | **FAILS** on command error (0.07 above 0.05) |
| | 0.6981 (40°) | 17 | 0.0196 | 0.0091 | 0.1666 | FAILS on command error |
| `converge_gather_rad` (0.1) | 0.15 | 23 | 0.0262 | 0.0144 | 0.1198 | **FAILS** on command error (0.07 above), and the one-cell pooled row |
| | 0.2 | 29 | 0.0279 | 0.0156 | 0.1951 | FAILS on command error and the pooled row |
| `flank_margin_m` (0.3) | 0.35 | 12, 6 (2 cells) | 0.0221 | 0.0059 | 0.0097 | passes: C6 not shown |
| | 0.4 | 12, 7 | 0.0221 | 0.0055 | 0.0192 | passes: C6 not shown (0.35 and 0.4 gave the same games on the fixed flank cell, 9 lost, 3 won) |
| `field_range_m` (1.1) | 1.2 | 0 | 0.0055 | 0 | 0.0181 | passes |
| | 1.3 | 8 | 0.0196 | 0.0135 | 0.0501 | fails on RMSE by a hair (0.0501 v 0.05) and on the one-cell pooled row by 0.0035 (0.0135 v 0.01); relied on neither |

So C6 for sacrifice and converge shows that the gate sees a moved switch by its command, not by the games (on these starts
the games barely notice those moves, section 2). Flank and field are **not demonstrable from LS1.5**: no calibrated rung
fails with room under any sensible limit, and lowering `pooled_margin` or gating end time to rescue them would be a
hair's margin (fact 3; group C).

| Key | Option | Value | Effect |
|---|---|---|---|
| `sacrifice_entry_rad` | smaller | 0.6109 (35°) **RECOMMENDED** | fails with room (RMSE 0.1203); the first calibrated rung, so "just above" |
| | larger | 0.6981 (40°) | fails with more room; a larger move than needed |
| | larger still | 0.8727 (50°) | not calibrated (estimate) |
| `converge_gather_rad` | smaller | 0.15 **RECOMMENDED** | fails with room (RMSE 0.1198) and on the pooled row; the first calibrated rung |
| | larger | 0.2 | fails with more room |
| | larger still | 0.3 | not calibrated (estimate) |
| `flank_margin_m`, `field_range_m` | **RECOMMENDED: a short top-up calibration first (a separate owner decision)** | larger rungs on their near-miss cells only (analyst's proposal: flank 0.6 and 0.9 m; field 1.5 and 1.8 m), then the smallest rung that fails with room | the rungs are accepted by the code: the loader takes any finite value above 0 (`ste/distil.py`) and neither `FlankMoved` nor `FieldMovedRange` (`opponents/perturbed.py`) sets a bound; flank 0.6 and 0.9 m make the flank clearance 1.7 and 2.0 m (keepout 1.1 m + margin, `scripted.StrikeFlank`), field 1.5 and 1.8 m widen the Guard team's push range from 1.1 m. Not calibrated: whether they fail is unknown until played. Needs a new calibration file (the committed `calibration.toml` is pinned by LS1.5's hash); CPU only, 0 GPU-h; 6 cell-plays (estimate: well under 30 minutes, from the 2 to 18 s per one-cell switch batch in `timing.json`); steady arms replay exactly, so the result predicts C6 |
| | **fallback if the top-up is declined** | flank 0.4; field 1.3 (the top calibrated rungs) | field 1.3 is predicted to FAIL (C6 passes), on small margins: RMSE by 0.0001, and the one-cell pooled row by 0.0035, which depends on M2-T6 giving `interval_step` the arm's own cells (fact 3). Flank 0.4 passes every limit on its near-miss cells and steady arms replay exactly, so its C6 is predicted not to fail: the read is predicted INCONCLUSIVE (exit 6). The stop rule then allows the cause to be fixed on the CPU and the read repeated once (`[stop] control_fails`), so this uses up that one repeat; whether a changed near-miss size counts as such a fix is the owner's call, since the values are hashed with the gate file. The arm cannot be removed: the loader requires all four switch keys and a near-miss cell where each switch player flies (`distil_gates.toml [read.near_miss_cells]`, `ste/distil.py`) |
| | set now at an extrapolated value | for example flank 0.6, field 1.5 (estimates: flank's RMSE rose 0.0097 → 0.0192 and field's 0.0181 → 0.0501 per rung) | may still not fail: INCONCLUSIVE at LS1.2 |

### Group F: control counts (`permuted_min_miss_cells`, `unfitted_min_miss_cells`)

**`permuted_min_miss_cells`**: at least this many of the 30 fixed cells must miss (fail a per-cell limit) for the
permuted scripts (C3) and the permuted network (C5).
Evidence: section 3: 22 Guard, 29 Strike under the recommended per-cell limits (one of the 22 Guard cells misses by
a hair: `guard_parked_centre` flown as `guard_parked_ring` v `strike_flank`, margin needed 0.0459 v 0.045, 29 games).
One key serves both sides: the Guard team has 7 cells of room (22 − 15), the Strike team 14 (29 − 15), so at 15 C3 and
C5 test the Strike side loosely.

| Option | Value | Effect |
|---|---|---|
| strict | 20 | C3 passes (22, 29); C5 passes only if the permuted network misses within 2 cells of the scripts on the Guard team |
| **middle, RECOMMENDED** | **15** | C3 passes; 7 cells of room for the network's own error on the Guard team |
| lenient | 10 | passes easily; proves less |

Why 15: half of the 30 cells, below the Guard team's 22 with room for C5, where the count depends on the network.

**`unfitted_min_miss_cells`**: at least this many of the 30 fixed cells must miss for an untrained network (C4).
Evidence: none from LS1.5 (no network played). In T44 only 2 of 30 fixed cells per side have a win share of at most 2 %
or at least 98 % (Guard: the two parked skills v `strike_converge`, 0.986 and 0.983; Strike: `strike_converge` v the two parked
Guards, 0.014 and 0.017), so most cells can move. An untrained network that happens to command little would play like a
parked Guard team and might not miss the 12 cells of the two parked skills (estimate, analyst).

| Option | Value | Effect |
|---|---|---|
| strict | 25 | strongest proof; risks INCONCLUSIVE if the untrained Guard copy plays like a parked team (estimate) |
| **middle, RECOMMENDED** | **15** | the same bar as the permuted control; room for the 12 parked-skill cells (estimate) |
| lenient | 10 | passes easily; proves little |

### Group G: OQ-3, the statistics (`[read] alpha`, `interval`, `correction`)

**`alpha`**: the error rate behind every interval. In this gate it works backwards from a usual test: a cell passes when
its interval lies inside the margin, so a smaller alpha (wider interval) makes the copy **harder** to pass, and a larger
alpha makes it easier. Every margin in this page was read at alpha 0.05; another alpha means re-reading them (b, c and n
are stored; the full paired tables can be rebuilt from the batch files without replaying a game).

| Option | Value | z per cell (Guard / Strike), pooled | Effect (estimate: intervals scale with z) |
|---|---|---|---|
| strict | 0.01 | 3.9879 / 3.9538, 2.5758 | per-cell intervals about 11 % wider, pooled 31 % wider; Strike noise 0.02 would need about 0.045 (0.0448, recomputed with `cells.newcombe_interval` at z 3.9538): it passes 0.045 by 0.0002, on the edge |
| **middle, RECOMMENDED** | **0.05** | 3.5879 / 3.5504, 1.9600 | as measured; the margins above |
| lenient | 0.10 | 3.4029 / 3.3636, 1.6449 | about 5 % narrower per cell, 16 % narrower pooled |

**`interval`**: **RECOMMENDED: `newcombe_hybrid`** (Newcombe's paired hybrid score interval, the only one built in
`ste/cells.py` and the one the calibration used). Alternatives (Wald with continuity correction, exact conditional) need a
build and a worked example in M1-T7 before M2 (plan OP-11), and a re-read of the margins.

**`correction`**: **RECOMMENDED: `bonferroni_per_side`** over the side's gated cells (m = 150 Guard, 130 Strike), the
pooled row at plain alpha, as the plan proposes and the calibration measured. It is the only correction built
(`distil_gates.toml [read]`: "the only correction built (ste/cells.py)"), so it is the only one selectable today. Not
built (each needs a build and a re-read of the margins): no correction (plain z 1.96 per cell: intervals about 45 %
narrower, estimate from 1.96 / 3.59; the near misses would fail less often on margins); Holm. Plain words: in this gate a
copy passes a cell only when the cell's whole interval fits inside the margin, so a wider interval makes passing harder.
The correction widens every cell's interval (it allows for 130 or 150 cells being read at once), so it makes the gate
stricter on the copy, not more lenient. The margins recommended here were read with it in place, so keeping it keeps
them valid.

## 6. The consistency check

Under the recommended set (`flips_max_games` 30, `cell_margin` 0.045, `pooled_margin` 0.01, end time not gated,
`cmd_rmse_max` 0.05, `cmd_unused_max_abs` 0.05, `cmd_zero_skill_max_abs` 0.005), judged as the built rule does (fact 2),
on each team's near-miss cells (largest over the arm's cells; pooled over them at z 1.96 and the command errors on them,
both recomputed for this page):

| Near miss | Team | Cells | Games changed (30) | Cell margin needed (0.045) | Pooled needed (0.01) | RMSE (0.05) | Parked-skill output (0.005) | Must | Outcome | Room |
|---|---|---|---|---|---|---|---|---|---|---|
| bias 0.05 | Guard | 4 | 46 | 0.0341 | 0.0148 | 0.0478 | 0.05 | FAIL | **FAIL** (games, pooled, parked output) | 16 games |
| bias 0.05 | Strike | 5 | 36 | 0.0329 | 0.0057 | 0.0491 | — | FAIL | **FAIL** (games) | 6 games |
| turn 6° | Guard | 4 | 48 | 0.0340 | 0.0080 | 0.0745 | 0 | FAIL | **FAIL** (games, RMSE) | 18 games |
| turn 6° | Strike | 5 | 38 | 0.0313 | 0.0060 | 0.0743 | — | FAIL | **FAIL** (games, RMSE) | 8 games |
| sacrifice 0.6109 rad | Strike | 1 | 7 | 0.0159 | 0.0062 | 0.1203 | — | FAIL | **FAIL** (RMSE) | 0.070 of RMSE |
| converge 0.15 rad | Strike | 1 | 23 | 0.0262 | 0.0144 | 0.1198 | — | FAIL | **FAIL** (RMSE, pooled) | 0.070 of RMSE |
| noise 0.02, used channels (estimate) | Guard | 4 | 4 | 0.0148 | 0.0024 | about 0.0113 | 0 | PASS | **PASS** | 26 games, 0.030, 0.0076 |
| noise 0.02, used channels (estimate) | Strike | 5 | 12 | 0.0228 | 0.0037 | about 0.0115 | — | PASS | **PASS** | 18 games, 0.022, 0.0063 |
| (rejected) bias 0.02 | Strike | 5 | 20 | 0.0242 | 0.0059 | 0.0198 | — | FAIL | pass: would not fail | — |
| (rejected) turn 3° | Strike | 5 | 20 | 0.0264 | 0.0059 | 0.0372 | — | FAIL | pass: would not fail | — |
| (fallback, top-up recommended) field 1.3 m | Guard | 1 | 8 | 0.0196 | 0.0135 | 0.0501 | 0 | FAIL | **FAIL** (RMSE, pooled) | RMSE by 0.0001; pooled by 0.0035 (depends on M2-T6, fact 3) |
| (fallback, top-up recommended) flank 0.4 m | Strike | 2 | 12 | 0.0221 | 0.0055 | 0.0192 | — | FAIL | pass: would not fail (INCONCLUSIVE) | — |

The steady rows are expected to replay exactly (fact 4). The noise rows are an estimate: the calibration played noise
0.02 on all four channels with seed 150101; the gate plays it on used channels only with seed 150007; the RMSE shown is
the calibration's on used channels.

And on the copy's own read (all gated cells, the full recommended set), the calibrated arms come out (computed for this
page; noise here is the calibration's, on all four channels):

| Team | Lets through | Stops |
|---|---|---|
| Guard | identity; noise 0.05 on used channels only; parked drift ≤ 0.005; field 1.2 m | noise ≥ 0.01 on every skill (on the parked-skill output alone); bias ≥ 0.01 (31 games, parked output); scale; every turn (turn 1.5°: 34 games); field 1.3 m (RMSE 0.0523) |
| Strike | identity; noise ≤ 0.02; bias ≤ 0.02; turn 1.5°; flank both | noise ≥ 0.05; bias 0.05; scale; turn ≥ 3°; every sacrifice and converge rung (RMSE) |

The two control counts at these per-cell limits: permuted scripts miss 22 (Guard; one of them, `guard_parked_centre`
flown as `guard_parked_ring` v `strike_flank`, by a hair: margin needed 0.0459 v 0.045) and 29 (Strike) cells, against
the recommended 15.

## 7. The recommended set

| Key | Value | Reason (one line) |
|---|---|---|
| `[limits] cmd_rmse_max` | 0.05 | stops the switch-type errors the play limits let through; every larger even error already fails on play |
| `[limits] cmd_unused_max_abs` | 0.05 | random output up to 0.05 on unused channels did not change the games |
| `[limits] cmd_zero_skill_max_abs` | 0.005 | largest parked-skill drift with no net effect (15 games at most) |
| `[limits] flips_max_games` | 30 | largest round value leaving at least 6 games of room on bias 0.05 and turn 6° on both teams; Strike noise 0.02 passes (27) |
| `[limits] cell_margin` | 0.045 | lets Strike noise 0.02 through (0.0419); stops a one-directional loss from about 2.3 to 2.7 points depending on the cell (estimate); a 2.5-point loss passed once (Guard scale 0.95, b 25, c 0) |
| `[limits] pooled_margin` | 0.01 | within 10 wins per 1,000 on average; stops only Strike scale 0.95 alone (stricter than the workflow's 0.015 illustration, which stops nothing calibrated) |
| `[limits] end_time_gated` | false | adds little the other limits miss; moves in games whose winner does not change |
| `[limits] end_time_max_ticks` | 3.0 | recorded, inactive; the middle option if gated later |
| `[controls] permuted_min_miss_cells` | 15 | Guard permuted scripts miss 22 (one by a hair), Strike 29; room for the network (7 Guard, 14 Strike) |
| `[controls] unfitted_min_miss_cells` | 15 | no data; same bar, room for a parked-like untrained Guard team (estimate) |
| `[controls.near_miss] bias` | 0.05 | fails on both teams (46 and 36 games v 30) |
| `[controls.near_miss] rotate_deg` | 6.0 | fails on both teams (48 and 38 games, RMSE 0.074); 3° does not fail on the Strike team |
| `[controls.near_miss] noise` | 0.02 | passes on both teams with room (estimate); the largest rung the play limits let through on both |
| `[controls.near_miss.switch] sacrifice_entry_rad` | 0.6109 | the first rung (35°) fails on command error with room (RMSE 0.1203 v 0.05) |
| `[controls.near_miss.switch] converge_gather_rad` | 0.15 | the first rung fails on command error with room (0.1198) and on the pooled row |
| `[controls.near_miss.switch] flank_margin_m` | top-up read first (0.6 and 0.9); fallback **0.4** if declined | 0.35 and 0.4 fail nothing: at 0.4 C6 is predicted not to fail, the read INCONCLUSIVE (exit 6), using the one repeat |
| `[controls.near_miss.switch] field_range_m` | top-up read first (1.5 and 1.8); fallback **1.3** if declined | 1.3 is predicted to fail on small margins: RMSE by 0.0001 (0.0501 v 0.05); the one-cell pooled row by 0.0035 (0.0135 v 0.01), which depends on M2-T6 (fact 3) |
| `[read] alpha` | 0.05 | the calibration's; every margin above was read at it |
| `[read] interval` | `newcombe_hybrid` | the only one built; the calibration's |
| `[read] correction` | `bonferroni_per_side`, pooled at plain alpha | the only one built; as proposed and measured; the margins assume it |

**If you only answer one thing:** accept the recommended set. A second, separate decision: allow a short top-up
calibration read (CPU, 0 GPU-h) of larger flank and field moves on their near-miss cells before those two switch keys
are set. If it is declined, write flank 0.4 and field 1.3; the read is then predicted INCONCLUSIVE on the flank control
(group E).

What accepting it costs, in plain words:
- **The Guard team copy must play closer than a 1.5° turn or a 0.01 bias** (they change 34 and 31 games in a cell
  against `strike_converge`), and its parked skill must stay under 0.005 everywhere: random output of 0.01 there fails,
  although the calibration shows such random output does not change the games. The alternative is
  `cmd_zero_skill_max_abs` 0.01 (group A, lenient).
- **The Strike team copy has little room**: a copy as good as noise 0.02 passes by 3 games (27 v 30) and 0.003 of
  margin (0.0419 v 0.045).
- If the copy fails, the stop rules allow one announced fix round (data mix, rounds, network size, zeroed inputs) and
  no limit is moved (`[stop]`).

One question goes to the lead, not the owner, before the file is hashed: M2-T6 must give `interval_step` each near-miss
arm's own near-miss cells, so that its pooled row is the one checked here (fact 3).

## 8. What the calibration cannot tell

- **A network's error is not these errors.** The calibration's errors are spread evenly: the same bias, turn or noise on
  every tick, drone and skill. A network's error is systematic and concentrated: largest where the scripts switch (a
  sharp change of command), in states the data covered least (review A F1 names the converge skill), and possibly
  different with one or two drones left. The numbers say how much each kind of evenly spread error changes the games; a
  network can change games with a smaller RMSE (if its error sits where games are decided) or a larger one (if it sits
  where they are not, as the moved switches show).
- **One set of starts.** Every number is one draw: T44's 1,000 starts (seed 110000) per cell. The noise arms are one
  realisation (seed 150101); the gate's noise near miss uses another (150007).
- **Few near-miss cells.** The near-miss controls see 4 or 5 cells; the copy is read on 130 or 150. The limits are
  chosen so the two agree on the calibrated arms only.
- **States.** The calibration measured command error on the scripts' own states; the gate reads it on states the
  network reached.
- **Not covered:** a steady output on an unused channel (vz, yaw rate); an error that depends on the number of live
  drones; the moved switches beyond their two rungs; any untrained network (C4 has no data); tier 2; flight.
- **The equivalence read (M2-T6) is not built yet**: the near-miss rule is read from its importable part (fact 2), and
  which cells its pooled row covers is expected, not built (fact 3).

## 9. Sources

- Run folders (not in git): `runs/2026-11-25_ste_ls15_calibration_guard/` and `..._strike/` in `~/AirStack-starling-max2-dev/svg_training/`:
  `results.json` (sha256 `d271dc75…` Guard, `868e8b41…` Strike), `results.md`, `controls.json`, `layout.json`,
  `timing.json`; the batch files for the near-miss pooled rows. The run's record:
  [2026-11-26_ste_ls15_calibration_record.md](../../records/2026-11-26_ste_ls15_calibration_record.md).
- Calibration files: `configs/ste_ls1/calibration.toml` (sha256 `b628fa0a…`), `configs/ste_ls1/cells.toml` (sha256
  `464fa2db…`); the script `scripts/ste_ls1_calibration.py`; statistics `source/svg_training/ste/cells.py`.
- The gate: `configs/ste_ls1/distil_gates.toml` on branch `ls1-m2` (at `df24386a`; since `155b7876` only `[read] noise_seed` was added, the owner keys are unchanged), sections `[limits]`, `[controls]`,
  `[read]`, `[read.near_miss_cells]`, `[stop]`; `scripts/ste_ls1_equivalence.py` at `df24386a` (the importable part, M2-T5:
  `arms`, `limit_failures`, `near_miss_control`, `interval_step`); the plan (LS1_TASK_PLAN.md, M2 file table, M2-T5, M2-T6).
- The analyst's derived numbers (margins needed, near-miss subsets, permuted miss counts under limits, near-miss pooled
  rows, near-miss command errors, T44 win shares) were computed read-only from the files above; nothing in the run folders was changed.
