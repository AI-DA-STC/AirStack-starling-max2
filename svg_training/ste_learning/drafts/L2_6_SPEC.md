INTERNAL · spec of task L2.6 (scripted games, tier 1 against tier 2, under the new rules), written before any of its runs; DRAFT until the lead's review freezes it · [../README.md](../README.md); the task's row: [WORK_BREAKDOWN](../WORK_BREAKDOWN.md) L2.6

Written 24 Nov 2026 by the L2.6 builder, before any run. Run by the builder: the tests, the driver's CPU smoke on the
PyTorch reference world (`--dry-cpu`, 16 games, 400 ticks; not a result) and a CPU timing probe (below; not a result).
No GPU run.

# L2.6: Scripted games, tier 1 against tier 2, new rules (INFO)

**Question.** WORK_BREAKDOWN L2.6: "the fast engine still predicts tier 2 (T13 repeated with tag, option B, delay and
drag)". With the new rules on (the one-for-one tag at 1.6 m and at 1.15 m, landing L2.3, filter option B L2.1), do
scripted 3v3 games on tier 1 (fast engine) give the hold counts that tier 2 (Isaac Lab rigid-body Starling) gives, cell
by cell, from the same starts? And do the two tiers give the same word for what each new rule does (P2: option B; P7:
landing)? L3–L6 train on tier 1 and check on tier 2; P2 and P7 read tier-1 screens (T70). Both rest on this answer.

**What is already known.**
- T13 (S2b, no tag, 2v1 and 5v3): 36 of 60 cells over the 0.10 hold gap. Strike drones passed over or under the Guards on
  tier 2 and never on tier 1, where heights stay exactly equal. The owner kept vertical passing in the game.
- T53 (L0.13, base game, tag 1.6 m): tier 2 parked Guard 538 of 1,000 against straight. T64 (L1.8): 541 with error off;
  tier-1 to tier-2 shifts of −33 to +47 per cell, no collapse. guard_mark_edge v straight 808 → 800 holds, same outcome
  on 912 of 1,000 starts. The estimate error changed no Wilson word.
- T70 (L2.5, tier 1 only): at 1.6 m option B is not testable with scripted play. Landing raised the hold in two cells
  only, both against strike_low (+51), where tier 1's vertical response is not fitted.
- L1.1b, T63, T69: the estimator is modelled as a correlated estimate error, not a delay. A residual delay of 0.05 s
  could not be seen at L1.5's 0.1 s resolution.

## The groups (rule set × arm), in run order

Every group plays the same 7 cells × 1,000 games. Tier 1 plays first, then tier 2. Both use T44's first 1,000 3v3 starts
(loaded from `configs/ste_l012/t44_reference.npz`, never re-drawn) and T44's seed 110000. Tier 2 plays the group's game
file with exactly two changes: `starling_layer.backend = "physics"` and the arm's parameter file. A group is
"protected" if it must fit the cap in the worst case (the driver refuses the launch otherwise). A droppable group plays
only if no earlier group was dropped and its worst case still fits what is left of the cap, using the Isaac smoke's
measured rates, raised by this run's own batches where they are slower. Otherwise it is recorded as "not played (projected over the cap)". Every later group is then recorded
"not played (an earlier group in the drop order was dropped)". The order below is the drop order, fixed now.

| # | Group | Tier-1 game | Tier-2 game, arm | Tag | Landing | Share | Tier-1 known answer | Worst case (s) | Kept |
|---|---|---|---|---|---|---|---|---|---|
| 1 | base_1p6 | `configs/ste_l011/base.toml` | same, off | 1.6 m | off | equal | T44 replay | 576 | protected |
| 2 | landing_1p15 | `configs/ste_l2/l26_landing_tag_1p15.toml` | same, off | 1.15 m | on | equal | none | 576 | protected |
| 3 | landing_gy_1p15 | `configs/ste_l2/l26_landing_gy_tag_1p15.toml` | same, off | 1.15 m | on | option B | none | 2,323 | protected |
| 4 | landing_1p6 | `configs/ste_l2/l25_landing.toml` | same, off | 1.6 m | on | equal | T70 counts ±10 | 576 | protected |
| 5 | base_1p6_copy | as group 1 | as group 1 | 1.6 m | off | equal | T44 replay | 576 | dropped first |
| 6 | landing_gy_1p15_err | `l26_landing_gy_tag_1p15_err.toml` (tier-1 error) | `l26_landing_gy_tag_1p15.toml`, nominal | 1.15 m | on | option B | none | 2,323 | dropped second |
| 7 | landing_1p15_err | `l26_landing_tag_1p15_err.toml` (tier-1 error) | `l26_landing_tag_1p15.toml`, nominal | 1.15 m | on | equal | none | 576 | dropped third |
| 8 | landing_gy_1p6 | `configs/ste_l2/l25_landing_gy.toml` | same, off | 1.6 m | on | option B | T70 counts ±10 | 2,323 | dropped fourth |

Worst cases here use the gate file's fallback rates. The run uses the smoke's measured rates (Time, below).

Why this order:
- base_1p6 anchors both tiers to known answers (T44, T53).
- The 1.15 m pair is the main-training radius after L2. It is also where the filter (1.10 m) acts before the tag, so it
  is the only place option B can show in scripted play (T70).
- landing_1p6 is P7's landing cell on tier 2. It is the only rule effect T70 saw, and tier 1's vertical response is not
  fitted there.
- base_1p6_copy (added after the lead's review) plays group 1 again as a later batch. Its outcome differences against
  group 1 measure the between-batch noise directly, which reading 5 uses.
- The error arms come next: T64 found the result holds with the error, so they are less likely to change a word (the
  lead kept this order, 24 Nov 2026).
- landing_gy_1p6 comes last: option B was not testable at 1.6 m (T70).

The new game files are their L2.5 parents value for value, except for the keys their headers mark: `tag.radius_m`
1.15 (ruled at G0), plus for `_err` the `[estimate_error]` table of `configs/ste_l1/base_err_nominal.toml` (L1.7, T63
values, EXPLORATORY). `tests/test_ste_l26.py` checks this. The `_err` files exist because the physics backend refuses
`[estimate_error]` (`core/game_config.py`). Tier 2's error comes from `params/starling_physics_v1_nominal.toml` (L1.1b,
the file L1.8 used).

## The cells (6 main + 1 repeat, the same in every batch)

| Cell (Guard v Strike) | Why |
|---|---|
| guard_mark_edge v strike_straight | T44's best Guard script against its best Strike script at 1.6 m, and L0.12's training opponents. It is T13's collapsing cell type. T64 known on tier 2 (800). |
| guard_parked_centre v strike_straight | The still Guard (L2.5's risk). Tier-2 known answer T53 538 (507–569). |
| guard_parked_ring v strike_flank | The filter-as-wall cell (P2): with the tag off, option B took its hold from 752 to 86 (T70). |
| guard_field v strike_flank | T13's 5v3 flank gaps; a T70 clip cell. |
| guard_mark_edge v strike_low | P7's landing cell (+51 at 1.6 m, T70) and a height script. The height band (0.5–1.8 m) allows a vertical gap of up to 1.3 m. That is inside a 1.6 m tag, so a pass over or under at 1.6 m is always tagged. It is outside a 1.15 m tag, so T13's failure mode can return at 1.15 m. |
| guard_field v strike_straight | The best Guard and Strike scripts at 1.15 m (L0.12b), and the Strike team's hardest Guard script (T64, T67): the L3 opponents at 1.15 m. |
| repeat: guard_mark_edge v strike_straight | Same seed, same starts. It is the same-seed control and gives each batch its own copy-noise floor. |

## The arms

Estimate error **off** (every group) and **nominal** (groups 6–7). Nominal uses T63's values, EXPLORATORY: position
0.0099 m / 1.2 s, velocity 0.022 m/s / 1.3 s, and in tier 2 only, attitude 0.0027 rad / 2.0 s. This is the L1 arm for
the estimator (L1.1b replaced the delay model with it).

**Delay and drag are not arms.** The task row names them, but `params/starling_physics_v1.toml` has `drag_*` = 0 and
`state_delay_s` = 0, both OPEN and not fitted. L1.3 fitted the estimate error only (T63). L1.5 (T69) could not see a
0.05 s residual delay at its 0.1 s resolution. An arm with a made-up value would only measure the made-up value.
**The lead accepted this as a gap against the task text** (24 Nov 2026): delay and drag are both 0 in
`params/starling_physics_v1.toml`; drag has been open since L1.3; L1.5 saw drag in the AirStack simulator. No
sensitivity arm now. L2.6 therefore repeats T13 "with tag, option B and the estimate error", not "with delay and drag".

## Controls (gated by the driver: exit 6, terminal, no number reported)

| Control | Where | Known answer |
|---|---|---|
| tag_fires_t2 | first, tier 2, `l25_landing_gy_tag_10m` (10 m tag), zero v zero, 100 ticks | every game 3 tags at step 1, a Guard win: the tag fires on the physics drone. It does **not** exercise landing or option B (every game ends at step 1, nothing descends, the filter never acts). Landing and option B have never run in Isaac Lab (no Isaac-marked test of either). Their first contact is the required Isaac smoke before launch (below) |
| condition_\<g\> | every group | tier-2 game = tier-1 game but for `starling.backend` and `starling.physics_params` (plus the tier-1 `[estimate_error]` in the error arm); the parameter file differs from the off file in `state_error_*` only and flies its own values |
| tier1_\<g\> | every tier-1 batch | ran tier 1; paired starts, tags one for one, no non-finite action; base_1p6: every cell replays T44 by `exploit.replay_ok`'s rule (game for game on the CPU; on CUDA holds within 10 of T44 and at most 20 games with another outcome, L0.13's tolerances: L1.8 matched exactly on the laptop's CUDA, but no 5090 CUDA run has replayed T44 exactly, and a miss is terminal); landing_1p6 and landing_gy_1p6: each main cell's holds within 10 of T70's (T70 ran on the CPU) |
| physics_agreement_\<g\>_launch\<k\> | before every tier-2 batch, every launch | L0.13's C-1a: Isaac Lab against the torch twin, 20 ticks, ≤ 0.02 m |
| tier2_\<g\> | every tier-2 batch | ran the physics drone; 0 non-finite wrench or setpoint; plumbing as tier 1; upsets counted (INFO) |
| repeat_t1_\<g\>, repeat_t2_\<g\> | every batch | the two copies' holds within 10 and ≤ 20 games ending otherwise (L0.13's CUDA tolerances) in the off arm; INFO in the error arm (each copy draws its own error) |
| known_t2 | base_1p6 tier 2 | guard_parked_centre v straight inside T53's 507–569 |

Known answers are read at 1,000 games × 2,400 ticks only. A smaller run records NOT_CHECKED. 1.15 m has no known answer
on either tier: no earlier run used these rules there.

## Reading words (fixed now; INFO; no "validated")

Holds are Guard-team wins of the 1,000 games, with Wilson 95 % intervals. Paired by start: same start, same seed.

1. **Per cell, tier 1 against tier 2** (same arm). The first word that applies:
   - "**tier 2 differs by more than T13's 0.10**" if |tier-2 rate − tier-1 rate| > 0.10 (T13's per-cell hold gap,
     `configs/s2b.toml`; a word here, not a gate);
   - "**tier 1 predicts tier 2**" if the two intervals overlap;
   - otherwise "**tier 2 differs, inside T13's 0.10**".

   "Predicts" means only that tier 1 **agrees with tier 2 within the test's resolution**: no difference larger than
   this test can see. At 1,000 games that is about 40–60 games, so it does not mean "equal". With up to 48 cell words
   (8 groups × 6 cells) and no multiplicity correction, a few separated cells are expected by chance. The intervals
   are unpaired Wilson intervals on paired data (same starts), so they are wider than a paired test would be: they miss
   paired shifts that the same-outcome share and paired counts show.
2. **Per group.**
   - "**the fast engine predicts tier 2 in every scripted cell of this rule set**" if all 6 cells predict;
   - "**… does not predict tier 2 in this rule set (a gap larger than T13's 0.10)**" if any cell has a gap over 0.10;
   - else "**… predicts tier 2 within T13's 0.10 in this rule set, not in every cell**".

   This answers the task's question: "still predicts" for a rule set means the first or third word, within the
   test's resolution. 6 cells, no multiplicity correction: a single separated cell is read with care.
3. **Same-outcome share** (per cell: the share of starts with the same outcome on both tiers). Reported beside tier
   2's own copy agreement in that batch (the repeat cell) and, for the two known cells, T64's 0.912 and 0.993.
   **No word:** T64's one comparable cell sits at 0.912, so any cut-off would fall where the data already are.
4. **Rule effects** (rule pairs, one rule changed between two groups; a pair is read only if both groups played):
   - the pairs: landing at 1.6 m (base_1p6 → landing_1p6, P7); option B at 1.15 m (landing_1p15 → landing_gy_1p15,
     P2), the same with the error (groups 7 → 6), and option B at 1.6 m (landing_1p6 → landing_gy_1p6);
   - the tag radius (landing_1p6 → landing_1p15);
   - the copy pair (base_1p6 → base_1p6_copy, no rule changed): its counts are the between-batch noise; its words
     are expected to be "no change detected" and "both tiers agree"; no plumbing word;
   - the estimate error at 1.15 m (2 → 7, 3 → 6). Tier 1's and tier 2's error are different models (above), so this
     pair says how each tier's own error moves its own games.

   Per cell and tier: "**raises the Guard team's hold**" or "**lowers the Guard team's hold**" (intervals do not overlap),
   else "**no change detected**". These are T70's words, and the hold → reach and reach → hold counts go with them. Across tiers:
   "**both tiers agree on the rule's effect**" (same word, "no change detected" included), "**the tiers disagree on its
   direction**", "**only tier 1 detects an effect**" or "**only tier 2 detects an effect**". Per pair, the record gives
   the count of cells where both tiers agree. For P2 the record states: "at 1.15 m, tier 1 and tier 2 agree on option
   B's effect in k of 6 scripted cells". For P7: the same with landing at 1.6 m.
5. **Plumbing, before any rule-effect word** (pre-registered, per pair and tier). Two noise measures:
   - **within-batch:** the repeat cell, which plays the first cell's starts again in another slot of the same batch.
     The floor is the tier's run-wide value: the largest repeat-cell count over the tier's off-arm batches.
   - **between-batch:** the copy pair's changed games over the 6 main cells (base_1p6 against base_1p6_copy, a later
     batch of the same launch); zero if the copy group was dropped.

   Error-arm groups share their error draws slot by slot (`models/estimator_effect.py` keeps the streams aligned), so
   only the device's jitter separates two paired groups, never the error's redraw. The rules:
   - **The same arm on both sides.**
     - If both measures are 0 games in outcome and in end step (exact copies, as tier 1 is expected to be), the rule
       reached the tier when at least one game of the 6 main cells changed outcome or end step (L2.5's rule).
     - Otherwise, outcomes only: the 6 main cells' changed outcomes must exceed both 6 × the within-batch floor's
       outcome count and 2 × the between-batch outcome count, and be at least 1. End-step jitter on CUDA is not
       measured, so end steps are not counted there.
   - **The arm changes** (error_1p15, error_gy_1p15). Adding the error cannot be told apart from redrawing it by
     counting changed games. So the error reached the tier when the error batch's repeat copies differ (outcome or end
     step) in more than 2 × the run's off-arm floor + 20 games. 20 is `reach_margin_games` = L0.13's CUDA differ
     tolerance, so a one-game excess never counts.
   - If a pair fails, that tier's words for the pair are withheld ("the rule not shown to reach this tier beyond copy
     noise: no word"), and so is the cross-tier word. The counts are still reported.
   - **Limits of these floors.** The within-batch floor is one repeat cell (a handful of games on CUDA, T64: 4–7).
     × 6 extrapolates it to six cells; it is not a bound. The between-batch copy is one pair of batches from one
     launch: batches from different launches (a resume after a stop) are not covered, and neither is noise that
     differs by rule set.

Every reading is "observed in the training simulator". Tier 2 is another drone model, not a correction of tier 1.
Also reported, INFO: closest approach of any opposite pair per cell on both tiers (minimum on the results page;
minimum, median and tag distances in `results.json`, `scoring.tag_stats`): T13's second quantity, and at 1.15 m the
place where option B's known wall shortfall could show. Also game length, end reasons and upsets. **No word is made
from the closest approach here:** T13's 0.10 m closest-approach gate is reported as numbers only (INFO).

## Time and GPU-hours (projected; run cap 1.3 GPU-h + Isaac smoke ≤ 0.2 = the task cap 1.5)

The world holds 7,000 games × 6 drones. A batch lasts as long as its longest game.

**The launch check uses measured rates.** The required Isaac smoke (Launch, step 1) plays every group at the run's 1,000
games per cell for 100 ticks. Its seconds per batch tick, by tier and filter share, go to the run with `--rates-from`.
The driver refuses a run of record without it, and refuses a smoke folder played at another games-per-cell count or on
the CPU. The launch check (protected worst case × 1.1 ≤ the 1.3 h run cap) and the drop decisions use those rates, raised
by the run's own slower batches. The gate file's rates are only the fallback for a kind the smoke did not measure:

| Fallback rate | Value | From |
|---|---|---|
| tier 2, even split | 0.19 s/tick | laptop RTX 5070 Ti, L0.2 (T48) scripted 3v3: 0.162 at 4,096 and 0.200 at 8,192 games; T64 0.257 at 15,000 |
| tier 1, even split | 0.05 s/tick | L0.2: 0.030 at 4,096, 0.035 at 8,192; T64's replay 0.082 at 15,000 (two learned players) |
| option B factor, tier 1 | × 5.3 | T70: the tag-off pair, 1,597 s against 301 s on the CPU |
| option B factor, tier 2 | × 3.7 | the builder's 16-game CPU probe gave 1.75 on the torch world and 2.5 on tier 1, where T70 measured 5.3 at scale; 1.75 × 5.3 / 2.5 = 3.7 (lead's review) |
| fixed | 300 s | Isaac start, the world, 8 C-1a checks, the tag-fires batch (T64's overhead was about 75 s) |

| At the fallback rates | Seconds | GPU-h |
|---|---|---|
| Worst case, protected groups 1–4 (every batch 2,400 ticks) + fixed | 4,351 | 1.21 (× 1.1 = **1.33, over the 1.3 h run cap**) |
| Worst case, all 8 groups + fixed | 10,150 | 2.82: groups 5–8 drop in their fixed order |
| **Expected**, all 8 groups at 500 ticks per batch | about 2,350 | **about 0.65** |

**Risk, stated before the run.** At the laptop-based fallback rates the protected set does not fit the 1.3 h run cap.
The 5090's tier-2 rate and option B's tier-2 cost at 7,000 games are not measured; the smoke measures both. If its
rates still make the protected set too large, the driver refuses the launch (exit 2) and nothing is played. The
remedy, decided now: before the first launch, the lead makes landing_1p6 droppable (it moves to the head of the drop
order) in the gate file and re-pins it. It must not be done after a launch.

Why 500 ticks is expected: T70's tag-on 1.6 m tier-1 batches (30,000 games) ended within 400 ticks. L0.12b's 1.15 m
screen had no hold by time-out and its largest cell p90 was 14 s (280 ticks). In the builder's smoke every tag-on batch
ended within 200 ticks. Tier 2 game lengths at 1.15 m are not measured. The worst case covers them.

**Builder's CPU probe** (24 Nov 2026, 5090 workstation CPU, 8 threads, the 1.15 m files, 7 cells × 16 games, a session
scratch script; not a result): landing_1p15 at 11 ms/tick on tier 1 and 31 ms/tick on tier 2 (torch world);
landing_gy_1p15 at 28 and 54 ms/tick. Option B factor 2.5 on tier 1 and 1.75 on tier 2. Landing and option B ran on the
physics path with 0 non-finite values and 0 upsets. At 16 games this probe understates option B's cost at scale (tier 1:
2.5 here, 5.3 in T70); the fallback above scales it.

Budget: task L2.6 has a cap of 1.5 GPU-h in `configs/ste_learning.toml` (kept by the lead, 24 Nov 2026; the L1 + L2
task caps sum to 11.1 of 13.0). The status of 24 Nov 13:30 shows 4.271 of 13 used.

## Launch (the lead launches after branch `l26-spec` is merged to `development`; not run by the builder)

On the 5090 (weekday), after `nvidia-smi` and `scripts/isaac_preflight.sh --approved-headless` exit 0, alone on the GPU.
`<d>` is the launch date. The driver pins its own copy of the gate file and its sha256 at the first launch. The record
quotes it: `7cf3fd28ced129f89982e44ebacd8568029fa33c0ba7bafd8a9789f033579a35` on this branch.

**1. Required Isaac smoke** (not of record, its own run folder; logged against the L2.6 cap). It asks 0.2 GPU-h and is
expected to use about 0.1–0.18. `ste_job.py` counts every launch of a task against its cap, so the run asks 1.3 and the
two stay inside 1.5. It plays every group at the run's 1,000 games per cell for 100 ticks. It is the first time this
driver starts Isaac Lab, the first time landing and option B run on the physics drone, and it measures the per-tick
rates the run's launch check needs:

```
cd ~/AirStack-starling-max2-dev/svg_training && unset PYTHONPATH
~/miniconda3/envs/env_isaaclab/bin/python scripts/ste_job.py launch --task L2.6 --name l26_isaac_smoke \
  --run-dir runs/<d>_ste_l26_isaac_smoke --min-s 60 --gpu-h 0.2 --settings configs/ste_learning.toml -- \
  ~/miniconda3/envs/env_isaaclab/bin/python scripts/ste_tier12_l26.py --settings configs/ste_l2/l26_gates.toml \
  --run-dir runs/<d>_ste_l26_isaac_smoke --cap-h 0.2 --headless --games 1000 --max-ticks 100
```

The lead reads, before the real launch:
- exit 0 and every control PASS, INFO or NOT_CHECKED;
- `tier2_*`: 0 non-finite wrench or setpoint and the upset counts, for landing_gy_1p15 especially;
- the repeat cells' outcome and end-step differ counts on tier 2: CUDA jitter, the floor of reading 5;
- tier1_base_1p6's T44 line;
- `games/*_t2.json`: seconds per tick for landing_1p15 against landing_gy_1p15, which is option B's tier-2 factor at
  7,000 games.

A FAIL here means no launch: report it. A cap stop (exit 3) is acceptable once groups 1–4 are in `games/`: they hold
every kind of rate the launch check needs.

**2. The run:**

```
~/miniconda3/envs/env_isaaclab/bin/python scripts/ste_job.py launch --task L2.6 --name l26_tier12 \
  --run-dir runs/<d>_ste_l26_tier12 --min-s 1200 --gpu-h 1.3 --settings configs/ste_learning.toml -- \
  ~/miniconda3/envs/env_isaaclab/bin/python scripts/ste_tier12_l26.py --settings configs/ste_l2/l26_gates.toml \
  --run-dir runs/<d>_ste_l26_tier12 --cap-h 1.3 --headless --rates-from runs/<d>_ste_l26_isaac_smoke
```

After the run: a record `records/<d>_ste_l26_tier12_record.md` (INFO) with the readings above, the plumbing lines first,
and a ledger row. Evidence (`results.md`, `results.json`, `controls.json`, `plan.json`, the gate file) goes under
`records/evidence/`. **Clips (lead's decision, 24 Nov 2026): a follow-up render after the run**, from the per-game
files, not a driver step. The driver writes none. The record needs 2-D clips with the height panel for at least
guard_mark_edge v strike_low at 1.15 m on both tiers, to show whether Strike drones pass under. Until the render lands,
the record says its clips are pending.

## What it cannot show

- **Trained teams.** Scripts only: they act every tick (L011-F1) and do not use the rules the way a trained team would.
  T70: "a trained team that learned to use the even split as a wall would lose more".
- **Delay and drag** (not fitted, above). **The estimate error is not the same on both tiers.** Tier 1 has position and
  velocity only, at 0.01 s sub-steps. Tier 2 adds attitude and acts inside the PX4 cascade copy. In tier 2 the game,
  commander and filter read the true state (L1.8's limit).
- **Passes over or under (T13's failure mode) are not counted.** The per-game arrays hold the closest 3-D approach,
  not the horizontal one. A pass shows only through the strike_low cell's holds and the 1.15 m clips.
- One start set (T44's), 3v3 only, 6 cells, one seed. The intervals cover scoring noise only.
- No drop-outs and no drawn team sizes (P7's other parts).
- Option B is PROPOSED. Its known wall shortfall (0.39 m tier 1 / 0.60 m tier 2) is not measured here.
- **The 1.15 m tier-1 numbers have no earlier run to anchor them.** L2.5 played 1.6 m only.
- Tier 2 is not the AirStack simulator (L1.5's confounds stand) and not flight. Nothing here is a flight result.
- CUDA tier 2 is not bit-exact (T64), so paired counts on tier 2 carry copy noise. The repeat cell and the copy pair
  measure it within one launch only (reading 5).
- **Tier 1 carries a lumped setpoint delay, tier 2 none.** Tier 1's fitted response has 0.1482 s
  (`params/real_exploratory_v0.toml`, setpoint to EKF2's estimate). Tier 2 has no transport delay (`state_delay_s` 0):
  it makes its lag with the cascade and rotor lag. Part of any tier gap may come from this.
- **Tier 1 on CUDA is not bit-exact against T70's CPU counts.** The ±10 tolerance was accepted by the lead
  (24 Nov 2026); landing_1p6's and landing_gy_1p6's tier-1 known answers are bands, not game-for-game replays.
- **Paired data scored with unpaired intervals** (reading 1): the Wilson words are conservative for these paired games.

## Decisions taken (lead, 24 Nov 2026) and what stays open

Decided: the 1.5 GPU-h cap line stays; the error arms rank below landing_1p6; clips are a follow-up render after the
run; the ±10 tolerance on T70's counts is accepted; delay and drag stay out (a gap against the task text, accepted).

Open: if the smoke's rates make the protected set too large for the 1.3 h run cap, the remedy above (landing_1p6
droppable, before the first launch, gate re-pinned) is the lead's to apply.
