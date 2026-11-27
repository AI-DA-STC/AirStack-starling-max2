INTERNAL · the options for the owner's ruling on the LS1 copy limits at the 1.15 m tag (R51; decision 1 of [LS1_1P15_SWITCH.md](LS1_1P15_SWITCH.md) section 4): the 16 owner keys of `configs/ste_ls1/distil_gates_1p15.toml` (all `FILL_R51`), read from the 1.15 m calibration (step D) alone; step E stays sealed until the ruling · the 1.6 m page this one follows: [LS1_LIMIT_OPTIONS.md](LS1_LIMIT_OPTIONS.md) (R48) · [README.md](README.md)

# LS1 copy limits at the 1.15 m tag: options for the owner (R51)

**Ruled (R52, 27 Nov 2026): "31"**: option B, `flips_max_games` 31 and the other 15 keys as R48, written into
`configs/ste_ls1/distil_gates_1p15.toml`. Step E was then judged once: [the record](../../records/2026-11-27_ste_ls1_1p15_switch_record.md).

Training simulator, tier 1 (fast engine, Starling layer, exploratory PX4 model); every number here is observed in the
training simulator. Nothing here is a flight result. Reviewed by two reviewers (section 5).

**In short.** At 1.6 m you set 16 copy limits (R48) from the 1.6 m calibration. The same calibration has now been
played at 1.15 m: the same deliberate errors, the same 1,000 starts, the same cells, with the scripts' own games at
1.15 m as the yardstick. R48's limits were then applied with the gate's own rule.

- **The gate's own checks still work.** Every deliberate error the gate must catch is still caught. The scripted copy
  with a scrambled skill order still misses 24 Guard and 25 Strike cells, against the 15 required. The gate's
  small-random-error check (random noise 0.02 on the 4 or 5 check cells) still passes with room.
- **The same small errors change more games at 1.15 m.** Over all of the copy's cells, Strike noise 0.02 changes up to
  31 games in one cell (27 at 1.6 m). At 1.6 m it passed the 30-game limit with 3 games to spare. At 1.15 m it misses
  by 1 game, in one cell, `strike_sacrifice` against `guard_parked_ring`. The gate's small-error check plays only 5
  cells and does not include that one, which is why it still passes.
- **Recommended: R48's values, with `flips_max_games` 31 instead of 30.** R48 chose 30 by a rule: the most games
  that still leaves 6 games of room on the steady errors the gate must catch, and lets Strike noise 0.02 through.
  Applied to the 1.15 m numbers, the same rule gives exactly 31. The other 15 keys stay as R48 set them.
- **Alternatives:** keep 30 as ruled (A), or 35 for more room (C). Section 3.

**This key also decides step E and the build.** Step E (last night's networks replayed at 1.15 m, sealed) and the
LS1 copy check both fail a team if any one cell changes more games than this limit. A failure means NOT DISTILLED:
one announced fix round, then LS1 stops (the gate file's `[stop]`). The choice is made blind to E.

If you only answer one thing: **"31, rest as R48"** (or "30" or "35" for `flips_max_games`; the other 15 keys as R48
unless you name one).

Terms: a **cell** is one line-up of the copied team against one opposing script, 1,000 games. **Games changed** in a
cell: games the copy lost that the scripts won plus games it won that the scripts lost. **RMSE**: the root-mean-square
difference between the copy's command and the scripts' on the same states. **Room**: how far a number sits from its
limit. **Near miss**: a deliberate small error the gate plays on 4 (Guard) or 5 (Strike) check cells, either one it must
catch (C6: a steady bias, a 6° turn, a moved switch point) or one it must let through (C7: random noise 0.02).
**INCONCLUSIVE**: the read's word when one of its own checks comes out wrong; the read is then repeated once.
**Pooled needed**: how far apart copy and scripts may be over the check cells together, at the 95 % level.

## 1. What was measured

| Item | 1.6 m (R48's source) | 1.15 m (this page) |
|---|---|---|
| Calibration runs | T90, T91 (top-up) | T95 `runs/2026-11-27_ste_ls15_1p15_calibration_{guard,strike}`, T96 `..._1p15_topup_{guard,strike}` |
| Files | `calibration.toml`, `calibration_topup.toml` | `calibration_1p15.toml` (`ebee6586…`), `calibration_topup_1p15.toml` (`6f06cf39…`): the same arms and rungs, top-up rungs included (field 1.5 and 1.8 m, flank 0.6 and 0.9 m), on the 1.15 m skills gate file |
| Scripts' games (the yardstick) | T44 | T50's 1.15 m games (step C0: they replay exactly on the CPU, 30 of 30 cells) |
| Cells | Guard 150, Strike 130 gated (+26 INFO) | the same |
| Near-miss cells | Strike cells against `guard_mark_edge` | Strike cells against `guard_field`, the best Guard script at 1.15 m (plan section 5); Guard cells unchanged |
| Controls | all PASS | all PASS: Guard 450 batches, Strike 499, top-up 3 and 3; the identity arm equals the scripts' games game for game (fixed cells against T50, mixed cells against the played scripts) |
| Cost | about 2.1 CPU-h a team | about 4.4 CPU-h a team (CPU shared; launch 1 oversubscribed and restarted with 8 threads); top-up seconds |

How the numbers were made: `records/evidence/2026-11-27_ste_ls1_1p15_switch/limits/check.py` reads each run's
`results.json` and batch files and judges every arm with the gate's built rule (`scripts/ste_ls1_equivalence.py`:
`limit_failures`, `cell_failures`, `miss_count`). On the 1.6 m runs it reproduces the 1.6 m page's section 6 table, both
control counts (22, 29) and both "lets through / stops" lists exactly. Margins needed: per cell at the corrected z, pooled
over the arm's near-miss cells at 1.96. A reviewer recomputed four near-miss rows and two copy's-read rows from the
batch files without the script (section 5).

## 2. The check at 1.15 m beside 1.6 m

### 2.1 The gate's near-miss checks under R48 (C6 must FAIL, C7 must PASS)

| Near miss | Team | Games changed 1.6 → 1.15 (limit 30) | Pooled needed 1.6 → 1.15 (0.01) | RMSE 1.15 (0.05) | Outcome at 1.15 m | Fails on |
|---|---|---|---|---|---|---|
| bias 0.05 | Guard | 46 → 27 | 0.0148 → 0.0073 | 0.0478 | **FAIL** (as required) | parked-skill output only (0.05 v 0.005); at 1.6 m also games and pooled |
| bias 0.05 | Strike | 36 → 37 | 0.0057 → 0.0055 | 0.0490 | **FAIL** | games (room 7 at 30, 6 at 31) |
| turn 6° | Guard | 48 → 47 | 0.0080 → 0.0053 | 0.0743 | **FAIL** | games, RMSE |
| turn 6° | Strike | 38 → 56 | 0.0060 → 0.0047 | 0.0741 | **FAIL** | games, RMSE |
| sacrifice 0.6109 rad | Strike | 7 → 3 | 0.0062 → 0.0064 | 0.1321 | **FAIL** | RMSE |
| converge 0.15 rad | Strike | 23 → 2 | 0.0144 → 0.0048 | 0.0822 | **FAIL** | RMSE (at 1.6 m also pooled) |
| flank 0.9 m | Strike | 52 → 25 | 0.0381 → 0.0347 | 0.1029 | **FAIL** | RMSE, pooled |
| field 1.5 m | Guard | 42 → 0 | 0.0544 → 0 | 0.1147 | **FAIL** | RMSE |
| noise 0.02, used channels (estimate) | Guard | 4 → 4 | 0.0024 → 0.0020 | about 0.0113 | **PASS** (as required) | room 26 games |
| noise 0.02, used channels (estimate) | Strike | 12 → 4 | 0.0037 → 0.0016 | about 0.0114 | **PASS** | room 26 games |

Every check comes out the way it must. What moved: three of the four moved switches (sacrifice, converge, field) now
change 0 to 3 games on their cells and fail on command error alone, with room (RMSE 0.08 to 0.13 against 0.05). Flank
0.9 m still changes 25 games and also fails the pooled margin. Guard bias 0.05 now fails only because the parked skill
outputs 0.05 where the limit is 0.005. That failure is certain (the bias is applied to every drone, the parked one
included), but it no longer tests the play limits on the Guard team. Steady errors replay exactly, so these rows predict
the gate's own checks. The noise rows are estimates, because the gate draws its noise from another seed (fact 4 of the
1.6 m page).

### 2.2 What R48 lets through on the copy's read (all gated cells)

| Team | 1.6 m: lets through | 1.15 m: lets through | Newly stopped at 1.15 m (worst cell's games changed) |
|---|---|---|---|
| Guard | identity; noise 0.05 on used channels; parked drift ≤ 0.005; field 1.2 m | identity; parked drift ≤ 0.005; field 1.2 m | noise 0.05 on used channels (34: `guard_mirror` v `strike_converge`) |
| Strike | identity; noise ≤ 0.02; bias ≤ 0.02; turn 1.5°; flank 0.35, 0.4 m | identity; noise 0.01; flank 0.35 m | noise 0.02 (31: `strike_sacrifice` v `guard_parked_ring`; next worst cell 24); bias 0.01 (44), 0.02 (61); turn 1.5° (37); flank 0.4 m (31) |

The larger errors were stopped at 1.6 m and are still stopped. The reason for the tighter ruler is that the worst
cells are now contested ones. At 1.15 m the Strike team wins more, so more cells sit near even, and an even cell has
more games a small error can turn. Step B: every Guard cell lost wins (median −423 of 1,000 over the 150 gated cells);
every gated Strike cell gained (median +368 over 130).

### 2.3 Unchanged, or stronger

- A perfect copy needs a margin: the identity arm's widest interval is ±0.0123 (Guard) and ±0.0121 (Strike), inside the
  0.045 cell margin.
- **Parked-skill drift** (`cmd_zero_skill_max_abs`): 0.005 still passes (16 games, cell margin needed 0.0249). At
  1.15 m, 0.01 changes up to 34 games (21 at 1.6 m) and needs a cell margin of 0.051. That supports 0.005 more strongly
  than at 1.6 m.
- **Margins** (0.045, 0.01): on the copy's read no calibrated arm is stopped by a margin alone, on either team, at 1.6 m
  or 1.15 m. Every arm a margin stops is also over the games limit or a command limit, so the margins act as backstops.
- **End time** (`end_time_gated` false, 3.0 recorded): the largest mean end-tick difference rises at 1.15 m. Noise 0.02:
  Guard 2.13, Strike 2.32 ticks (1.59, 1.13 at 1.6 m). Noise 0.05: 4.46, 4.56 (2.97, 2.63). Bias 0.01: 3.62, 3.69. Gating at
  3.0 would now stop noise 0.05 and bias 0.01, which the games limit already stops on the Strike team, and Guard noise
  0.05 on used channels (4.45), which the games limit already stops at 30 or 31. The 1.6 m reason not to gate still holds:
  the end time moves in games whose winner does not change.
- **Statistics** (OQ-3: alpha 0.05, Newcombe's paired interval, Bonferroni per side): already fixed in the gate file; no
  reason to change them.

## 3. `flips_max_games`: the options

R48's rule at 1.6 m: "the largest round value leaving at least 6 games of room on bias 0.05 and turn 6° on both teams;
Strike noise 0.02 passes" (1.6 m page, section 7). At 1.15 m the two halves meet at exactly 31. Strike bias 0.05 changes
37 games, so 31 leaves room 6. Strike noise 0.02 changes 31, which passes at 31 with no room. The Guard half no longer
binds, because Guard bias 0.05 fails on the parked output whatever this key is. There are two ways to read "keep R48":
keep the number (30) or keep the rule (31).

| Option | Value | Copy's read lets through (beyond identity) | Gate checks | For | Against |
|---|---|---|---|---|---|
| A | 30 (R48's number) | Guard: parked drift ≤ 0.005, field 1.2 m; Strike: noise 0.01, flank 0.35 m | all as required; Strike bias 0.05 room 7 | the same number as the 1.6 m pilots were judged on; no change to explain | breaks R48's intent: a Strike copy as good as noise 0.02 (RMSE about 0.011, the level the network design's Strike error budget is built around: LS1_REDESIGN 4.4, row mark ≤ 0.010) fails by 1 game in one cell, and that one cell would make the team NOT DISTILLED |
| **B (recommended)** | **31** (R48's rule) | as A, plus Strike noise 0.02, flank 0.4 m | all as required; Strike bias 0.05 room 6 | both halves of R48's rule hold at 1.15 m | noise 0.02 passes with no room, on one random draw (seed 150101); another draw could change 32 |
| C | 35 | as B, plus Strike noise 0.05, Guard and Strike noise 0.05 on used channels | all as required; Strike bias 0.05 room **2** | the most room for a 1.15 m copy | lets through errors R48 stopped at 1.6 m; the Strike bias check fails by only 2 games, so a small change in the gate's play could leave it not failing, making the read INCONCLUSIVE |

What none of the options changes: the headroom marks of step E (median at most 9 games changed a cell, at most 5 cells
over 20) were fixed in the plan before any run and are not moved. Because noise changes more games at 1.15 m, those
marks are harder to meet than they were at 1.6 m.

The other 15 keys, R48's values under every option:

| Key | Value | At 1.15 m |
|---|---|---|
| `cmd_rmse_max` | 0.05 | catches every moved switch, three of them by RMSE alone (2.1) |
| `cmd_unused_max_abs` | 0.05 | no calibrated arm at 1.15 m is stopped by this key alone (as at 1.6 m); unchanged |
| `cmd_zero_skill_max_abs` | 0.005 | stronger case (2.3) |
| `cell_margin` | 0.045 | backstop; under B the largest needed by an arm let through is 0.0388 (Strike flank 0.4 m) |
| `pooled_margin` | 0.01 | backstop |
| `end_time_gated` (`end_time_max_ticks` 3.0 already set) | false | 2.3 |
| `permuted_min_miss_cells` | 15 | the scrambled-skill copy misses 24 (Guard) and 25 (Strike) |
| `unfitted_min_miss_cells` | 15 | **set blind**: there is no 1.15 m data outside E, whose untrained-network control (the C4 analogue) is sealed and voids E if it misses fewer. At 1.6 m the bar rested on an untrained Guard team playing like a parked one; at 1.15 m parked Guards hold only 101, 31 and 16 of 1,000 against straight, high and low Strike teams, so an untrained Guard team may differ from the scripts in more cells, not fewer (estimate) |
| near miss `bias`, `rotate_deg`, `noise` | 0.05, 6.0, 0.02 | 2.1 |
| switch `sacrifice_entry_rad`, `converge_gather_rad`, `flank_margin_m`, `field_range_m` | 0.6109, 0.15, 0.9, 1.5 | 2.1. Only the rungs above were measured; no larger rung that still changes games was played for sacrifice, converge or field. Field 1.3 m would also fail, by RMSE 0.0552 (room 0.005): keep 1.5 |

## 4. What this cannot tell

- **E is sealed.** No pilot-network number is on this page, and none was read for it. E is judged once, after the ruling,
  as a transfer test (plan section 3). Its read does not isolate the tag change: the ruler also tightened (2.2), and the
  Strike near-miss opponent changed.
- **A network's error is not these errors** (1.6 m page, section 8). This holds more at 1.15 m, because the pilots were
  fitted on 1.6 m rows.
- **One draw each.** One set of starts and one noise draw (seed 150101; the gate's C7 uses 150007). 31 against 30 is
  one game in one cell of one draw.
- **Three switch checks rest on command error.** At 1.15 m the sacrifice, converge and field moves change almost no games
  on their check cells. If the build changed how command error is read, those three checks would have no play limit behind them.
- **Not measured here:** the share of training rows with a team-mate absent at 1.15 m (plan step C). It moves to the
  build's CPU smoke (record of T95 to T97).

## 5. Reviews

27 Nov 2026, Sonnet 5.5, independent; neither opened E's sealed files.
- **Numbers and sources.** It checked every number against the run folders, the check script's outputs and the shas,
  and recomputed four near-miss rows (Strike bias 0.05 and turn 6°, Guard bias 0.05 and turn 6°) and the Strike noise
  0.01 and 0.02 copy's-read rows from the batch files without the script. It also reviewed the script: the gate rule is
  applied directly, the identity-as-yardstick step is valid, and the error mapping and C7 estimate are right. It found 2
  should-fix and 3 nits: the switch wording ("two" by RMSE alone was three; flank still changes 25 games) and the
  Strike median (over gated cells). All fixed.
- **Completeness.** It confirmed all 16 keys are covered, the plan's marks are respected (D alone, E sealed, the
  recommendation does not lean on E) and the internal-page rules are met. It found 11 should-fix and 4 nits: the
  `[stop]` consequence, the fact that this key also decides E's verdict, the two readings of "keep R48" (the
  recommendation moved from 30 to 31), C7 not seeing the 31-game cell, end time, the unfitted bar set blind, the
  unmeasured larger switch rungs, the headroom marks, a glossary, and E named before use. All fixed.

## 6. Sources

- Run folders (not in git): `runs/2026-11-27_ste_ls15_1p15_calibration_guard/` (`results.json` sha256 `310551ff…`),
  `..._strike/` (`d2839ddb…`), `runs/2026-11-27_ste_ls15_1p15_topup_guard/` (`355aa76d…`), `..._strike/` (`22419437…`);
  1.6 m: `runs/2026-11-25_ste_ls15_calibration_{guard,strike}/`, `runs/2026-11-26_ste_ls15_topup_{guard,strike}/`.
  Record: [2026-11-27_ste_ls1_1p15_switch_record.md](../../records/2026-11-27_ste_ls1_1p15_switch_record.md).
- The check: `records/evidence/2026-11-27_ste_ls1_1p15_switch/limits/check.py` and its outputs `r48_at_1p6.json`
  (the reproduction of the 1.6 m page), `r48_at_1p15.json` (option A), `f31.json` (B), `f35.json` (C). End-time maxima:
  each run's `results.json` (`cells[].end_time.mean_abs_ticks`, gated cells). Step B: `.../b/b_table.json`.
- Gate files: `configs/ste_ls1/distil_gates.toml` (R48's values, `5cce1245…`), `configs/ste_ls1/distil_gates_1p15.toml`
  (its near-miss cells and `[stop]`, `59d94d50…`); the rule: `scripts/ste_ls1_equivalence.py`.
- Plan and marks: [LS1_1P15_SWITCH.md](LS1_1P15_SWITCH.md); the 1.6 m options: [LS1_LIMIT_OPTIONS.md](LS1_LIMIT_OPTIONS.md).
