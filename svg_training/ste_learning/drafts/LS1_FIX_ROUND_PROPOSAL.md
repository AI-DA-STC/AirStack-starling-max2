INTERNAL · the analyst's diagnosis of the LS1 copy check (LS1.2, 26 Nov 2026: NOT DISTILLED on both sides) and the proposal for the one fix round the stop rules allow (R47, gate `[stop]`); written by the analyst (Opus 5.5) on 26 Nov 2026; reviewed by two reviewers (numbers, reasoning), 26 Nov 2026; nothing run of record (the CPU pilots below are scratch, not of record) · links: [README.md](README.md), [LS1_TASK_PLAN.md](LS1_TASK_PLAN.md), [LS_EXECUTION_WORKFLOW.md](LS_EXECUTION_WORKFLOW.md) sections 3 and 5, [LS1_LIMIT_OPTIONS.md](LS1_LIMIT_OPTIONS.md), [DISCUSSION R46 to R48](../DISCUSSION_2026-11-19_20.md), the gate file `configs/ste_ls1/distil_gates.toml` (sha256 5cce1245...)

# LS1 fix round: why the copy failed and the one fix round (26 Nov 2026)

Training simulator, tier 1; observed in the training simulator. Not for flight. Every number below comes from the run
folders named in each table or from a scratch evaluation on the CPU of the saved networks against the scripts, on
rows from those run folders. Anything that is a projection is labelled **estimate**. The scratch outputs are saved as
logs (`out_*.log`, `pilot_*.log`), with the scripts that wrote them, in
[records/evidence/2026-11-26_ste_ls1_fix_diagnosis/](../../records/evidence/2026-11-26_ste_ls1_fix_diagnosis/README.md); at review the diagnosis scripts (section 2, the saved-network row of section 3 and the CPU timing) were run again,
and their numbers match the new logs at the stated rounding, except one CPU timing (section 4); the pilot numbers of
section 3 come from the pilots' original logs (`pilot_*.log`), which a reviewer checked; the pilots were not re-run.

## 0. In plain words (for the owner)

**What was tested.** One network per team was trained to copy that team's hand-written skills. The copy check then
compared the network with the scripts. Strike's three hard skills (flank, sacrifice, converge) are far off: 0.19 to
0.34 command error against a limit of 0.05. Guard misses narrowly on mirror (0.051) and by about twice the limit on field (0.097). Guard misses the
"parked at the centre" skill, which must output exactly zero: its largest output is 0.035 (typical 0.011), about 7 times
the limit of 0.005.

**Why, in four points.**

1. **The network is under-trained. It is not misled.** Its error on the rows it was trained on is as large as on
   fresh games. Flank's error is 0.336 on the training rows and 0.343 on fresh games. So the cause is the fit, not
   data coverage or drift. The rounds' refits on 2, 4 and 6 million rows (about 10,000, 20,000 and 29,000 steps)
   barely moved Strike's error (0.186, 0.175, 0.172). Guard's fell (0.096, 0.078, 0.064), but rounds and steps grew
   together there, so that series cannot say which helped. The only clear Strike drop came in the last three epochs of
   the last fit, near 37,000 steps. So for Strike more rounds alone will not fix it, and more steps help only slowly,
   with plateaus.
2. **One shared network is too little for six skills in the steps it got.** In CPU trials a 256x3 network given one
   skill alone reached, at about the shared network's steps: flank 0.123 (40,000 steps), sacrifice 0.157 and converge
   0.158 (37,500 steps). The shared network after its 39,000 steps on the GPU is at 0.336, 0.280 and 0.197 on the same
   kind of rows. Alone is about 2.7 times better for flank, 1.8 times for sacrifice and 1.25 times for converge. Each
   skill alone keeps improving at the end of its trial (flank 0.112 at 60,000 steps). Sacrifice sat on a plateau near
   0.30 for 10,000 steps, then dropped to 0.18. This is the strongest pointer in the diagnosis, and a larger network is
   an allowed lever. The proposal still keeps the size, and that is **a cost choice, not an evidence result**: the only
   equal-step test of a wider network ran 5,000 steps, before any plateau escape, and a wider network would cost steps
   inside the GPU cap (section 5).
3. **None of the failing skills lacks information.** Each failing script reads only what is in the 71 numbers: the
   drone's own position, its team-mates' and the Guards' positions, and the zone. None of them reads the four zeroed
   inputs (yaw, time left, team flag). Flank's labels do jump: a 1 mm change of the positions moves them by 0.026 RMS,
   and 1 cm moves them by 0.083. So a copy has to place flank's switch points to within a few millimetres. A smooth
   network learns that slowly.
4. **The zero skill is a precision problem that no allowed lever is shown to fix.** The network's yaw output for that
   skill sits at +0.007 on every row, which alone is above the 0.005 limit. Its sideways output is above 0.005 on 95 %
   of rows.

**What the fix round can change.** It may change only the data (`[data]`), the relabelling rounds (`[dagger]`), the
network size and the zeroed inputs (`[net]`). It cannot change the fit settings (epochs, learning rate) and cannot add
inputs. The evidence says steps help most, so the proposal gives the final fit about 1.9 times the gradient steps.
It does this through more rows per round and one round fewer, not through more epochs. One round fewer gives up whatever
Guard gained from the rounds themselves; the data cannot separate that from the steps (section 5). It keeps the network
size (for cost), raises the share of rows with a team-mate out, and zeroes 17 more inputs that no script reads. It asks
0.62 GPU-h of the 0.628 left under LS1.1's cap of 0.8.

**What I expect (estimate).** Guard mirror probably passes. Guard field may pass. Strike flank, sacrifice and converge
very likely stay above 0.05, and Guard's zero skill very likely stays above 0.005. So LS1 is expected to stop after the
fix round, as the stop rules say.

**If the fix round fails.** LS1 stops and no limit is moved. Head training (LS1.4, its 4.0 GPU-h cap) does not start,
and route 3 waits for the owner to decide on a new build. If Guard alone passes, Guard is reported DISTILLED, but that
changes nothing for LS1.4: head training needs both sides (gate `[stop]` one_side_only).

**The owner decides** whether to spend the fix round as the cheap final record, or to
stop LS1 now on this diagnosis (the two choices side by side: section 7). If LS1 stops, the later build named in R47 (added bearing and distance inputs) may be
the wrong build. In a short trial those inputs did not help flank or sacrifice. Inputs in each drone's own frame did
help: flank alone reached 0.045 with them.

## 0b. The lead's recommendation (26 Nov 2026, after the review): stop LS1 now

The lead read the reviewed page against its own pilot numbers and **recommends stopping LS1 now, not spending the fix
round**. This changes recommendation 1 of section 7; the diagnosis and the costed round below are unchanged.

- **No allowed lever has a path to the limit on Strike.** The best case for more capacity and more steps is one skill
  alone in its own 256x3 network: flank 0.112 at 60,000 steps, sacrifice 0.157 and converge 0.158 at 37,500
  (`pilot_F1.log`, `pilot_S4.log`, `pilot_S5.log`), all two to three times the 0.05 limit. The fix round gives a shared
  network about 73,000 steps. The only pilot under 0.05 is flank with inputs in each drone's own frame (0.045,
  `pilot_F2.log`), and those inputs are a new build, not allowed in the fix round (R47).
- **Guard cannot pass either.** Every kept row carries the labels of all five Guard skills (`label` [rows, 5, 4] in
  `data/round_*.pt`, checked by the lead), so the error-weighted keep does not starve `guard_parked_centre` of rows.
  No `[data]` key reaches its constant +0.007 yaw offset. LS1.4 needs both sides (gate `[stop]` one_side_only), so it
  stays blocked whichever round is run.
- **The 512x3 round would not test what the next build needs.** Its pilot ran only 5,000 steps, and the one-skill
  pilots above already show that capacity alone does not reach the limit.
- **Cost of the round in full:** 0.62 GPU-h, about 1 h of CPU for the second read, and a record with two reviewers.
  This diagnosis alone took 2.6 h of agent time. It would buy a second NOT DISTILLED, expected on both sides.
- **What stopping buys:** the same record content (section 6), and the effort goes to the re-scoped build: inputs in
  each drone's own frame, a network or output head per skill, a fit schedule, and an exact zero for the parked skills.
  That build is the owner's decision (R47 named bearing and distance inputs; the pilot says those help converge only).

The fix round stays available until the owner rules. If the owner chooses to spend it, the proposal in section 5 is
ready, and the lead would ask for a small cap raise for headroom (the 0.62 asked leaves 0.008 of the 0.8 cap).

## 1. What failed (the read of record)

Runs `runs/2026-11-26_ste_ls12_read_{guard,strike}` (results.json, results.md); every control PASS (Guard 119, Strike
117, from the task brief), verdict NOT DISTILLED on both.

| Side | Failure | Read value | Limit |
|---|---|---|---|
| Guard | zero-command skill `guard_parked_centre`, largest error (max over channels; per channel 0.0351, 0.0345, 0.0002, 0.0077) | 0.0351 | 0.005 |
| Guard | `guard_mirror` RMSE vx, vy | 0.0509, 0.0523 | 0.05 |
| Guard | `guard_field` RMSE vx, vy | 0.0966, 0.0993 | 0.05 |
| Guard | games changed above 30: 12 cells (11 of them against `strike_converge`, 10 holding `guard_mirror`, 10 `guard_parked_centre`); one cell over the margin (`guard_field` x3 v `strike_sacrifice`, 41 games, [+0.0015, +0.0506]) | 31 to 64 games | 30 games, 0.045 |
| Strike | `strike_flank` RMSE vx, vy | 0.3352, 0.3342 | 0.05 |
| Strike | `strike_sacrifice` RMSE vx, vy | 0.2664, 0.2560 | 0.05 |
| Strike | `strike_converge` RMSE vx, vy | 0.2030, 0.1902 | 0.05 |
| Strike | 64 cells over 30 games, 27 over the cell margin, the pooled row ([-0.0111, -0.0066] v +-0.01); 52 of the 64 cells and 78 of the 91 cell failures hold `strike_flank` | | |

The Strike skills that pass the command limit (straight 0.022 and 0.016, high 0.035 and 0.032, low 0.031 and 0.028)
still flip more than 30 games in a few mixed cells against `guard_mirror`: that opponent amplifies small differences.
The rest of the Strike cell failures are the flank, sacrifice and converge cells.

The read's error by live drones (results.json `errors`): flank 0.149 / 0.216 / 0.371 with 1 / 2 / 3 live drones,
sacrifice 0.033 / 0.088 / 0.319, converge 0.062 / 0.335 / 0.178; Guard mirror 0.067 / 0.070 / 0.044, field 0.061 /
0.130 / 0.100.

## 2. Where the error lives

Scratch logs behind this section: 2.1 `out_strike1.log`, `out_guard1.log`; 2.2 `out_strike2.log`, `out_side.log`; 2.3
and 2.4 `out_strike3.log` (label sensitivities in `out_strike2.log`); 2.5 `out_guard1.log`.

### 2.1 The fit itself (both sides)

From `runs/2026-11-26_ste_ls11_distil_{guard,strike}/fit_report.json` and a scratch evaluation of the saved network
`skill_net_<side>.pt` on 300,000 to 400,000 rows sampled from `data/round_0.pt` (flown by the scripts, kept without
error weights) and `data/round_3.pt` (flown by the network, kept by error weight). The stored labels were recomputed
with the scripts row by row first: largest difference 5.1e-06 (converge), at most 3.6e-07 for the others.

| Skill | xy RMSE, training rows round 0 | round 3 | fit report (fresh, net-flown) | the read |
|---|---|---|---|---|
| strike_flank | 0.336 | 0.347 | 0.343, 0.349 | 0.335, 0.334 |
| strike_sacrifice | 0.280 | 0.328 | 0.290, 0.289 | 0.266, 0.256 |
| strike_converge | 0.197 | 0.216 | 0.202, 0.191 | 0.203, 0.190 |
| strike_straight | 0.021 | 0.021 | 0.023, 0.017 | 0.022, 0.016 |
| guard_mirror | 0.050 | 0.052 | 0.050, 0.051 | 0.051, 0.052 |
| guard_field | 0.133 | 0.188 | 0.136, 0.138 | 0.097, 0.099 |

The error on the training rows equals the error on fresh games: the network **underfits**. Coverage is not the
problem. The fit's own numbers agree. Strike's training loss sat near 0.03 for most of every round (round 3: 0.0578
falling to 0.0288 by epoch 37), then dropped in its last three epochs (0.0283, 0.0252, 0.0227). The fit was escaping a
plateau when it stopped. Guard's loss was still falling steadily at the end (0.00475, then 0.00464). The
previous-round network's RMSE over the rounds was 0.186, 0.175, 0.172 (Strike) and 0.096, 0.078, 0.064 (Guard).
Each refit is fitted on all rows so far (2, 4, 6 million), so this series is also a steps series (about 10,000,
20,000 and 29,000 steps). Guard improved with rounds and steps. Strike barely did until the late drop of the last fit.

By hold length (fit report): Strike 0.199 / 0.170 / 0.200 / 0.301 for 0-12 / 12-60 / 60-240 / 240-600 ticks held;
Guard 0.075 / 0.057 / 0.053 / 0.037. Strike's worst rows are the long holds, the states a skill reaches after
flying a long time (deep detours, circling). Guard's worst rows are just after a switch.

Near switch points (`near_switch` rows, round 0): flank 0.323 near v 0.342 away, sacrifice 0.281 v 0.280, converge
0.272 v 0.153. Only converge's error gathers near switches. Flank's and sacrifice's error is spread over all states.

By opponent (round 0): flank 0.326 to 0.340, sacrifice 0.267 to 0.286 against every Guard script. No opponent
explains it.

How much of the kept data had the skill flying (round 0, round 3): flank 0.139, 0.136; sacrifice 0.175, 0.170;
converge 0.254, 0.275; straight 0.122, 0.119. Every kept row carries every skill's label, so each skill is trained on
all rows. The flown share only sets which states appear.

### 2.2 strike_flank

The script (`opponents/scripted.py`, `StrikeFlank`): fly at the zone, unless a Guard drone ahead lies within keep-out
+ 0.3 m = 1.4 m of the line. Then aim at a waypoint 1.4 m to the far side of the nearest such Guard. Scratch
decomposition on 300,000 round-0 rows:

| Check | Result |
|---|---|
| Rows where the detour is on (a Guard in the 2.8 m wide corridor) | 0.948; one Guard in the way 0.512, two 0.436, none 0.052 |
| RMSE when the detour is on, and when it is off | 0.343 and 0.173; detour rows carry 0.986 of flank's squared error |
| "Just fly straight" against flank's labels | 0.496 overall (0.509 on detour rows) |
| Net's flank command against the straight label on detour rows; net flank against net straight | 0.366; 0.365 |
| Mean cosine of the net's flank command with flank's label and with the straight label (detour rows) | 0.873 and 0.876 |
| Median and p90 angle error on detour rows | 19.6 and 49.8 degrees |
| Net closer to the mirrored-side command than to the label (detour rows) | 0.284 overall; 0.51 within 1 cm of the side boundary, 0.20 at 0.2 to 0.5 m from it, 0.36 beyond 0.5 m |
| Rows within 1 cm of the side boundary, of detour rows | 0.012 (0.011 to 0.014 for every opponent) |
| Rows within 5 cm of the corridor edge | below 0.001 |
| Distance to the Guard in the way | 1 to 2 m 0.528, 2 to 4 m 0.472 |

So the network learned flank partly. It removes about half of the squared error of "fly straight"
((0.343/0.509)^2 = 0.45 left). It still turns the wrong way or too little on many detour rows, and the misses are
far from the side and corridor boundaries, not at them. The side choice is not noise: only 1.2 % of detour rows lie
within 1 cm of the side boundary.

Inputs. Flank reads the own xy position (relative to the zone), the Guard slots' relative xy and presence flags, and
the keep-out constant. All of these are in the 71 numbers, and none is zeroed. So flank needs no added input. But its
key quantity is each Guard's offset from the drone's own zone line, a product of two input vectors, followed by an
argmin and a sign. A small network builds that slowly from raw inputs. Section 3 has the pilots.

Label jumps (scratch: positions jittered with Gaussian noise, scripts recomputed). At 1 mm, flank's labels move by
0.026 RMS (0.0009 of rows by more than 0.2). At 1 cm they move by 0.083 (0.0095 of rows). The movement grows as
roughly the square root of the jitter, the mark of jumps: the side choice, which Guard is nearest in the way, and the
corridor edge. This is label sensitivity, not a proven floor: a copy that resolves the jumps to about 4 mm would sit
near 0.05 (estimate, from the square-root scaling).

### 2.3 strike_sacrifice

Strike 0 flies at the nearest Guard. The others circle the zone the shorter way to the bearing opposite the Guard
nearest Strike 0, then fly straight in within 30 degrees of it. Scratch decomposition, round-0 rows:

| Branch | Share of rows | RMSE | Share of squared error |
|---|---|---|---|
| straight (Strike 0 out, or a drone alone) | 0.173 | 0.045 | 0.004 |
| Strike 0 at the nearest Guard | 0.286 | 0.117 | 0.050 |
| others circling | 0.428 | 0.340 | 0.636 |
| others flying in through the gap | 0.113 | 0.462 | 0.310 |

The error does not gather at the switch points. Others more than 0.3 rad from the 30-degree edge: 0.413 of rows, RMSE
0.32. Within 0.02 rad of it: 0.009 of rows, RMSE 0.57. Within 0.1 rad of the +-pi direction flip: 0.010 of rows,
0.72. Where the two Guards nearest Strike 0 are within 5 cm of each other: 0.016 of rows, 0.58. The circling and
straight-in commands need the drawn Guard (an argmin of pairwise distances between Strike 0 and five Guard slots) and
an angle comparison. No zeroed input is read, and no information is missing. Label sensitivity: 0.028 RMS at 1 mm,
0.086 at 1 cm.

### 2.4 strike_converge

| Branch | Share of rows | RMSE | Share of squared error |
|---|---|---|---|
| alone (straight) | 0.097 | 0.058 | 0.008 |
| run-in, committed | 0.091 | 0.391 | 0.358 |
| run-in, gathered, not committed | 0.020 | 0.529 | 0.145 |
| placing, circling | 0.360 | 0.139 | 0.180 |
| placing, steering to the point | 0.432 | 0.166 | 0.308 |

The run-in (11 % of rows) carries half the squared error. Its pace is the drone's distance to the zone edge over the
farthest team-mate's, which needs team-mates' distances from the zone. The gather gate is "every live drone within
0.1 rad of its bearing": rows with the worst team-mate within 0 to 0.12 rad (not committed) have RMSE 0.50 to 0.51.
Two live drones are worst (read 0.335; round 0, two-live run-in 0.339, placing 0.26 to 0.31). Label sensitivity:
0.020 at 1 mm, 0.088 at 1 cm. Information is all present.

### 2.5 Guard

| Skill | What the scratch evaluation shows (round-0 rows; round 3 alike) | Label sensitivity, 1 mm / 1 cm |
|---|---|---|
| guard_parked_centre (zero in 3v3) | yaw output +0.0070 on every row (sd 0.0002), above 0.005 by itself; xy output median 0.011, p99 0.021, max 0.087, above 0.005 on 0.955 of rows; same with 1, 2 or 3 live drones (p99 0.024, 0.025, 0.020). A constant offset, not a tail. The yaw output of every Guard skill is off zero (+0.0071 ring, -0.0012 mark edge, -0.0033 mirror, +0.0060 field) although every Guard label has yaw 0 exactly. | 0 / 0 |
| guard_mirror | smooth labels; error 0.063 / 0.071 / 0.044 with 1 / 2 / 3 live, 0.063 near switches v 0.047 away | 0.0005 / 0.0054 |
| guard_field | the jump of the nearest Strike drone: where the two nearest Strikes are within 5 cm, 0.036 of rows, RMSE 0.47; 5 to 20 cm, 0.114, 0.21; beyond, 0.756, 0.075 (net-flown round 3: 0.079 of rows at 0.50). The team-mate push is on in 0.029 of rows (0.056 of the squared error). 0.993 of labels have length 1 (a direction only). | 0.022 / 0.073 |
| guard_parked_ring (passes in the read: 0.042, 0.037) | the station assignment jumps | 0.012 / 0.058 |

The Guard cell failures sit almost all against `strike_converge` (11 of 12). Those games are long (mean end-step
difference 2.4 to 7.6 ticks), so small command errors of mirror and parked_centre build up into changed outcomes.

### 2.6 Zeroed inputs (gate `[net]`, OP-5)

Zeroed now: 6, 7 (yaw sine and cosine), 10 (time left), 11 (team flag). No script reads them (checked in
`opponents/scripted.py`), so no failing skill depends on a zeroed input. Inputs no script of either team reads, and
so free to zero: own vz (5); every slot's relative z (15, 22, 29, 36, 43, 50, 57, 64) and relative vz (18, 25, 32,
39, 46, 53, 60, 67). Strike high and low read own z (2), so 2 stays. Guard mirror reads velocities in xy, so 3, 4 and
the slots' vx and vy stay. One gate file serves both teams, so the Strike-only unused inputs (every velocity) cannot be
zeroed for Strike alone.

The zeroing is stored in the saved skill network (`skill_net.py` writes `zeroed_inputs` into the network file and
rebuilds the network from it), so it carries over to the export (LS1.3) and to the skill network that head training
(LS1.4) uses. In the fix round it goes in with four other changes, so its own effect cannot be told apart from theirs.

## 3. CPU pilots (scratch, not of record)

CPU, 2 to 6 threads, no GPU. Each pilot fits a fresh network with the gate's fit recipe (Adam, lr 0.001, batch 8,192,
the same normaliser, inputs 6, 7, 10 and 11 zeroed). The training rows are 1.5 million: 750,000 each sampled from
Strike's `data/round_0.pt` and `data/round_3.pt`. The pilots are short against the GPU fit's 39,000 steps on 8
million rows, so they compare levers at equal steps; they do not predict the GPU result.

**Shared network, all six skills.** Held-out: 200,000 rows of `data/round_2.pt` (error-weighted, harder than
average). xy RMSE:

| Pilot | Steps | flank | sacrifice | converge | straight |
|---|---|---|---|---|---|
| A: 256x3 (as LS1.1) | 5,000 | 0.461 | 0.378 | 0.320 | 0.050 |
| A | 10,096 | 0.460 | 0.375 | 0.298 | 0.032 |
| B: 512x3 | 5,000 | 0.460 | 0.377 | 0.302 | 0.039 |
| C: 256x3 + R47-like inputs (the drone's own and every other drone's bearing and distance from the zone, Guards included) | 4,000 | 0.458 (A: 0.462) | 0.378 (A: 0.379) | 0.268 (A: 0.325) | 0.043 |
| the saved LS1.1 network (39,000 GPU steps), same rows (`out_saved_on_heldout.log`) | | 0.345 | 0.327 | 0.223 | 0.021 |

A at 10,000 steps tracks LS1.1's round 0, whose fit had about 9,800 steps: training loss 0.0325 here and 0.0288
there. The saved network (39,000 steps) is better than A at 10,000 on these rows (flank 0.46 v 0.345). The fit
report's rounds say how: almost flat from 10,000 to 29,000 steps, then the late drop in the last fit's final epochs
(section 2.1). At equal steps the wider network B helps a little (loss 0.0329 v 0.0349; converge 0.302 v 0.320) and not at
all on flank or sacrifice in this window. That window is short: 5,000 steps, before the plateau escapes seen at 10,000
to 20,000 steps (sacrifice alone) and near 37,000 (LS1.1's Strike fit), so it does not rule a wider network out. The R47-like inputs help converge, not flank or sacrifice, in 4,000 steps
(short).

**One skill per network, 256x3.** Held-out: 200,000 rows of `data/round_0.pt` (about 37 % of them also among the
training rows; the training loss equals the held-out error, so the overlap does not matter here). xy RMSE by steps:

| Pilot | 5k | 10k | 20k | 30k | 40k | 60k | saved shared network, same kind of rows |
|---|---|---|---|---|---|---|---|
| flank, raw inputs | 0.214 | 0.158 | 0.139 | 0.129 | 0.123 | 0.112 | 0.336 |
| flank, raw + each Guard's along and offset in the drone's zone-line frame | 0.119 | 0.101 | 0.080 | 0.067 | 0.057 | 0.045 | |
| sacrifice, raw inputs | 0.309 | 0.301 | 0.182 | 0.163 | 0.157 (37.5k) | | 0.280 |
| converge, raw inputs | 0.251 | 0.229 | 0.198 | 0.170 | 0.158 (37.5k) | | 0.197 |

Every failing Strike skill can be learnt from the 71 numbers. Each is still improving when its pilot ends, and
sacrifice shows a plateau escape between 10,000 and 20,000 steps. In the shared network the same skills get one sixth
of the loss each and share the trunk, and after 39,000 steps they are worse than alone at about the same steps (flank 40,000, the others 37,500): about 2.7 times
for flank (3.0 against flank's 60,000), 1.8 times for sacrifice and 1.25 times for converge. With raw inputs even
a whole network for flank alone is at 0.112 after 60,000 steps. With inputs in the drone's own frame it reaches 0.045.

## 4. Which lever fixes what

| Lever (allowed: gate `[stop]` fix_round) | Evidence | Expected to help |
|---|---|---|
| More gradient steps in the final fit (`[data] keep_rows`, `ticks_per_round`, `[dagger]` rows add up) | underfit (section 2.1); Guard's loss still falling at the end; for Strike, only the late drop in the last fit's final epochs (rounds at 10k to 29k steps were almost flat) and the alone pilots, still falling at 37.5k to 60k with a plateau escape for sacrifice | **the main lever**: every failing skill, most for Guard mirror and field and for sacrifice (plateau escape) |
| More relabelling rounds (`[dagger]`) | previous-round error flat for Strike; training rows' error equals fresh error | not shown by itself: Guard's previous-round error fell with the rounds (0.096, 0.078, 0.064), but rounds and steps moved together, so the data cannot say which helped. Fit time grows with the square of the rounds (each round refits from scratch on all rows so far), so fewer rounds give more steps per GPU-hour |
| Data mix: mode shares | error flat across uniform, mix and random (flank 0.342 / 0.327 / 0.332) and across opponents | no |
| Data mix: `absent_min_share` | the largest errors are with a team-mate out: converge two-live 0.335, mirror 1 to 2 live 0.067 to 0.070, field two-live 0.130; the kept absent share was its natural 0.226 to 0.238 | a little, for converge, mirror, field |
| Data mix: `switch_floor` | only converge's error gathers near switches; near-switch rows are already 0.30 to 0.35 of kept Strike rows | no |
| Larger network (`[net] hidden`) | at equal steps 512x3 gives a small gain (B v A); alone-v-shared shows the trunk is crowded, but that comparison also changes each skill's loss share | some, later in training (not ruled out: the equal-step test ran 5,000 steps only); it costs 2.7 to 3.7 times the CPU time per command (four logged runs: 2.2 to 2.5 ms v 6.3 to 6.7 ms for 3,000 rows, 6 threads, 2.7 to 2.9 times, `out_fwd_time*.log`; the top of the range from an earlier unlogged run, 1.9 v 7.1 ms) in the read and in every later use |
| Zeroed inputs (`[net] zeroed_inputs`) | no failing skill reads a zeroed input; 17 more inputs are read by no script | small: removes inputs that carry no label information |
| Fit settings (`[fit]` epochs, lr, batch) | Guard's constant output offsets (+0.007 yaw) and the plateaus point at the learning rate and the number of epochs | **not allowed** in the fix round (gate `[stop]` fix_round lists `[data]`, `[dagger]`, `[net]` hidden and zeroed_inputs only) |

What no allowed lever is shown to fix:

- **guard_parked_centre's 0.005 limit.** The output is a constant offset of about 0.007 (yaw) and about 0.011 (xy),
  not a tail. The loss gives a skill whose label is exactly zero almost no pull (its squared error is about 6e-05). A
  learning-rate decay (`[fit]`, not allowed) or a structural zero (the dispatch returning zero for a skill that is zero
  at this team size: a new build) would target it.
- **strike_flank at 0.05** with raw inputs. Even a whole 256x3 network for flank alone is at 0.112 after 60,000 steps.
  The shared network in the fix round will have far less than that per skill (estimate).
- No failing skill needs an added input in the sense of missing information. Flank does reach the limit far sooner
  with inputs in the drone's own frame. Those are not the R47 inputs (bearing and distance from the zone), and the
  fix round cannot add inputs.

## 5. The proposal: the one fix round

Changes to `configs/ste_ls1/distil_gates.toml` (one file for both teams). Every other key stays as it is, `[limits]`,
`[controls]`, `[read]` and `[stop]` included. The changed file has a new sha256 and is hashed before the launch.

| Key | Old | New | Reason |
|---|---|---|---|
| `[data] ticks_per_round` | 600 | 1200 | collect about 11.7 million rows per round (estimate: 5.86 million at 600), so the larger keep still leaves the error weighting a choice; also more long-hold rows, where Strike is worst (0.301 at 240 to 600 ticks held) |
| `[data] keep_rows` | 2,000,000 | 5,000,000 | the main lever: the final fit gets 15 million rows, 1,831 steps per epoch, about 73,200 steps in its 40 epochs (now 8 million rows, about 39,000 steps); the epochs cannot change. 5 million, not more, keeps the job inside its 0.31 GPU-h ask with a margin |
| `[dagger] script_share` | [1.0, 0.5, 0.25, 0.0] | [1.0, 0.5, 0.0] | three rounds, to give the final fit the most steps inside the ask (rows fitted over the run 5 million x (1 + 2 + 3) = 30 million, not 5 million x 10). **This trades away whatever Guard gained from the rounds themselves**: its previous-round error fell with them (0.096, 0.078, 0.064), and rounds and steps moved together. Guard's own numbers say coverage is not what limits it: mirror 0.050 on script-flown training rows, 0.050 and 0.051 on fresh net-flown games; field 0.133 on script-flown rows and 0.136, 0.138 on fresh unweighted net-flown games (its 0.188 on round-3 rows is likely the keep's error weighting, not the net-flown states). The last collecting network gets more steps than LS1.1's (round 1 fitted on 10 million rows, about 48,800 steps, against 29,300). The last round is still flown by the network alone. The four-round option at the same cost is in the table below |
| `[data] absent_min_share` | 0.2 | 0.3 | the largest errors are with a team-mate out (converge, mirror, field); the natural share was 0.226 to 0.238 |
| `[net] zeroed_inputs` | [6, 7, 10, 11] | [5, 6, 7, 10, 11, 15, 18, 22, 25, 29, 32, 36, 39, 43, 46, 50, 53, 57, 60, 64, 67] | add own vz and every slot's relative z and vz: no script of either team reads them (section 2.6); they carry no label information |
| `[net] hidden` | [256, 256, 256] | unchanged | **a cost choice, not an evidence result.** Capacity is the lever the alone-v-shared numbers point to most (2.7, 1.8 and 1.25 times at about equal steps), and it is allowed. The only equal-step test of 512x3 ran 5,000 steps and helped little. Inside the cap 512x3 would cut the steps by 2 to 3.7 times (estimate; its GPU cost per step is not measured), and it costs 2.7 to 3.7 times per command on the CPU in the read and in head training. The 512x3 option is costed below for the owner |

The extra steps come through rows (`keep_rows`, `ticks_per_round`) and the round count, not through epochs: `[fit]` is
untouched (40 epochs, lr 0.001, batch 8,192). The five changes go in as one bundle, so if the round moves a number the
record cannot say which change moved it.

Rounds against rows at about the same cost (estimate; 4,883 steps per million rows over 40 epochs at batch 8,192; fit at
4.6 to 5.3 ms per step, see Cost):

| Option | Rows fitted over the run | Steps over the run | Steps of the final fit | Fit time | Inside 0.31 GPU-h per job? |
|---|---|---|---|---|---|
| LS1.1 (4 rounds x 2 million) | 20 million | 97,700 | 39,100 | (measured) | |
| **proposed (3 x 5 million)** | 30 million | 146,500 | 73,200 | 674 to 776 s | yes, 0.24 to 0.28 h |
| 4 x 3 million | 30 million | 146,500 | 58,600 | 674 to 776 s, one more collection (about 40 s) | yes, 0.25 to 0.29 h |
| 4 x 3.75 million | 37.5 million | 183,100 | 73,200 | 842 to 970 s | no margin, 0.29 to 0.34 h |
| 4 x 5 million | 50 million | 244,100 | 97,700 | 1,123 to 1,294 s | no, 0.37 h or more |

The proposal keeps three rounds: at the same cost it gives the final fit 25 % more steps than four rounds of 3 million,
and steps are the lever both sides' evidence agrees on. Four rounds of 3 million is the alternative if the owner prefers
to keep the relabelling rounds.

Checked: the gate file with these five changes, written to a scratch copy, loads through `distil.load_distil_gates`
(no `FILL_` key; run sizes 4,096 games x 1,200 ticks, three rounds; the smoke takes the first two rounds, [1.0, 0.5]).

**Expected effect per failing item (estimate; the pilots do not predict the GPU fit, they rank levers).**

| Item | Read now | Expected after the fix round | Pass? |
|---|---|---|---|
| guard_mirror RMSE | 0.051, 0.052 | 0.035 to 0.048 (smooth labels; Guard's loss was still falling; more rows with a team-mate out) | likely |
| guard_field RMSE | 0.097, 0.099 | 0.06 to 0.09 (the nearest-Strike jump; sensitivity 0.022 at 1 mm) | possible, not likely |
| guard_parked_centre largest error | 0.035 | 0.011 to 0.035 (no lever aims at the constant offset: the lower end is today's typical output, the level the read would show if only the tail shrank; the upper end is today's read) | very unlikely |
| Guard cells v strike_converge | 12 over 30 games | fewer, as mirror's and parked_centre's errors fall | unclear |
| strike_flank RMSE | 0.335, 0.334 | 0.20 to 0.30 | very unlikely |
| strike_sacrifice RMSE | 0.266, 0.256 | 0.12 to 0.25 (if the plateau escape seen alone happens in the shared network) | very unlikely |
| strike_converge RMSE | 0.203, 0.190 | 0.10 to 0.17 | very unlikely |
| Strike cells (64 over 30, 27 over margin, pooled) | | fewer, as flank's error falls; the flank cells stay the bulk | no |

Items that pass narrowly now are refitted from scratch and could fail: Strike's largest unused-channel error 0.0428
(limit 0.05), `guard_parked_ring` 0.042 and 0.037 (limit 0.05), and the cells at 29 to 30 games changed (Guard: 4 cells
at 30 and 2 at 29; Strike: 5 at 29, network arm of the read).

Verdict expected (estimate): NOT DISTILLED on both sides: Strike on flank, sacrifice and converge, and Guard on
parked_centre.

**Cost.**

| Item | Estimate | Basis |
|---|---|---|
| GPU, per team (the two side by side on the RTX 5090) | about 0.26 h each (0.24 to 0.28) | LS1.1 measured (fit_report.json, round seconds, each one round's collection, keep and fit): each extra 2 million rows x 40 epochs (9,766 steps) added 45.6, 46.4 and 45.0 s (Guard: 4.6 to 4.75 ms per step) and 51.7, 50.3 and 37.6 s (Strike: 5.3, 5.2 and 3.9 ms), collection changes included; the means are 45.7 s (4.7 ms) and 46.5 s (4.8 ms). The estimate takes 4.6 to 5.3 ms: 146,500 steps is 674 to 776 s; plus three collections of 1,200 ticks (about 40 s each; about 18 s at 600 ticks now, round 0's seconds less its fit), start-up, report and clips (35 to 37 s measured, sizes unchanged) and an allowance of 20 to 60 s for the larger keep's error pass: 850 to 990 s |
| GPU-h to ask | 0.31 per job, 0.62 together | LS1.1 has used 0.172 of its 0.8 cap. That is the union of its ledger lines, side-by-side overlap counted once, the 0.004 probe included (`ste/budget.py`; `scripts/ste_job.py status`); summed per job the same lines are 0.329 (guard 0.158, strike 0.168, probe 0.004). The launcher's check (`budget.check_launch`) tests, for each launch, the union used so far plus that job's ask against the cap; each job stops at its own ask, which keeps the union under the cap. The task plan's stricter rule is that both asks fit under the cap less the hours used: 0.62 <= 0.628, a margin of 0.008. Under a per-job sum the ask would not fit (0.8 - 0.329 = 0.471 < 0.62) and would need a cap change announced to the owner first; neither the launcher nor the cap test counts that way. The union of the two jobs side by side is expected near 0.3 h. Each job's 0.31 is 1,116 s, above the 990 s top of the estimate. If the first minutes run slower than 5.3 ms per step, the lead stops and asks the owner before the cap is reached, not after |
| GPU memory and host memory, per job | rows on the GPU about 6 GB (15 million rows); host peak about 15 to 17 GB (the fit copies the kept rows of all rounds into one set); disk about 6 GB of data files per team | 398 (Guard) and 414 (Strike) bytes per kept row (`data/round_*.pt`: 796 MB and 828 MB for 2 million rows); 15 million rows is 6.0 GB (Guard) and 6.2 GB (Strike). It fits the RTX 5090 (32 GB) side by side. On the laptop (12 GB) one team at a time, or a smaller `keep_rows`, recorded as such |
| CPU, the second copy check LS1.2 | about 38 and 53 min again (the network size is unchanged; the two reads side by side, about 1 h wall); 75 to 110 min if run beside a GPU job | the first read: 37.5 min (Guard) and 53.1 min (Strike) of cell time from `job.log` |

The fix round is a new run of record. It gets its own run folders (for example `runs/<date>_ste_ls11fix_distil_{guard,strike}`
and `runs/<date>_ste_ls12fix_read_{guard,strike}`), a new gate-file hash, a record and a ledger row, and the two
reviewers before its verdict is reported. It is announced to the owner before launch, with its cost (gate `[stop]`).

**Alternative, if the owner prefers the strongest attempt over the cheap record.** Use the same keys, plus `[net]
hidden` = [512, 512, 512]. This is about 0.45 to 0.85 GPU-h per team (estimate: 2 to 3.7 times the per-step cost on
146,500 steps; the GPU cost per step of 512x3 is not measured, and the CPU forward ratio, 2.7 to 3.7, is taken as the
upper end), so it asks about 1.0 per job. That needs an owner change of LS1.1's cap (0.8 to about 2.2) and its test
(`task_caps_total_gpu_h`), as the task plan says. The second read could then take 56 to 66 min (Guard) and 104 to 135 min
(Strike): the network-flown arms (10.6 and 30.2 min of the first read) scaled by 2.7 to 3.7 (estimate). The pilots
cannot say whether it would change the verdict: the one equal-step test ran 5,000 steps, before any plateau escape.
It is left out for the cap and the read's cost, not because the evidence rules it out.

## 6. If it still fails

Per the stop rules (gate `[stop]` not_distilled, R47): no limit is moved, LS1 stops, and the record names the skills
that do not copy and why. Head training (LS1.4) does not start, and route 3 waits on an owner decision about a new build.
A side that passes alone (Guard is the likelier) is reported DISTILLED and waits; it does not start LS1.4 (gate `[stop]`
one_side_only). For the record, from this diagnosis:

- **strike_flank, strike_sacrifice, strike_converge**: one shared 3-layer network trained under the fixed fit settings
  does not learn them in the steps it gets. Each is learnable alone, slowly, from the 71 numbers. Their labels jump
  within millimetres of switch points.
- **guard_parked_centre**: the exact-zero limit asks for a precision that a squared-error fit at a fixed learning rate
  does not give.
- **guard_field** (if it fails): the nearest-Strike switch.

Route 3 would then need a new build, which is an owner decision. The evidence above points at three changes. The
first is per-skill capacity: a network or output head per skill, since alone pilots are 1.25 to 2.7 times better at about equal steps (flank most).
The second is inputs in each drone's own frame for flank: it reached 0.045 alone at 60,000 steps. The third is a fit
schedule (more epochs, a decaying learning rate) and a structural zero for a zero skill. The R47 inputs (bearing and
distance from the zone) helped converge in a short pilot, but not flank or sacrifice. Building only those may not be
enough (estimate, from a 4,000-step pilot).

## 7. For the lead and the owner

1. Spend the fix round as proposed (0.62 GPU-h asked inside the cap, about 0.26 h used per team side by side, about 1 h of CPU wall for the two reads)? Or stop LS1
   now on this diagnosis? My recommendation is to spend it. The CPU pilots are too short to rule out a late plateau
   escape in the GPU fit (LS1.1's Strike fit was escaping one when it stopped). The run then closes LS1 with a clean
   record. The two choices side by side (estimates):

   | Choice | Cost | Chance of DISTILLED (estimate) | What it buys |
   |---|---|---|---|
   | spend the fix round | 0.62 GPU-h asked, 0.008 of LS1.1's cap left unasked (about 0.3 h expected used, the two side by side); about 1 h of CPU wall for the two reads | Guard: low (mirror likely, field possible, the zero skill very unlikely); Strike: very low (flank, sacrifice, converge very unlikely) | the one allowed attempt, used; a record that says which skills do not copy after the strongest step-count the cap allows, and a test of the late plateau escape |
   | stop LS1 now | 0 GPU-h; about 1 h CPU saved | none (NOT DISTILLED on both sides stands) | the same record content from this diagnosis, without the fix round's evidence; LS1.4 does not start either way |
2. The stronger alternative (512x3, a cap change to about 2.2) is the owner's call. I do not recommend it, for cost:
   capacity is the lever the diagnosis points to most, but the pilots neither show nor rule out a gain from a wider
   shared network, and it needs the cap change.
3. Before the build that follows: the owner may want the later build re-scoped from "R47 inputs" to "per-skill
   capacity, own-frame inputs, fit schedule" (section 6).

## 8. Method

- Scratch code, saved with its logs in `records/evidence/2026-11-26_ste_ls1_fix_diagnosis/`: loads `skill_net_<side>.pt` into `ste/skill_net.SkillNet`, the rows from
  `data/round_<r>.pt`, and recomputes labels with `opponents/scripted.make_strategy` on each row alone at its slot of a
  zero team tensor (the rule of `ctl_labels_are_the_scripts`), with the game config from
  `distil.load_distil_gates("configs/ste_ls1/distil_gates.toml")`. Branch masks are recomputed from the script's own
  formulas and checked against the stored labels (flank's detour waypoint to within 1e-05).
- RMSE is over the x and y channels together unless a table gives vx and vy separately. The read's numbers are its
  own (results.json `errors`).
- CPU at most 6 threads, `CUDA_VISIBLE_DEVICES` empty; no GPU job, no git, no file written in the repository other
  than this page and the LS1.1/LS1.2 record.
- Reviewed by two reviewers (numbers, reasoning), 26 Nov 2026; their fixes applied by the analyst after a check
  against the source. The diagnosis scripts were run again at review and their outputs saved as logs (the page's head and section 2); the
  pilots keep their original logs.
