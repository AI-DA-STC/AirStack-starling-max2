INTERNAL · spec of the L1 side track (tasks L1.11, L1.12, L1.13), written before any of its runs under the owner's G0 rulings R1 and R15; version 2 after two spec reviews · [../README.md](../README.md); the rulings: [DISCUSSION §14](../DISCUSSION_2026-11-19_20.md#14-gate-g0-rulings-owner-22-nov-2026)

Written by the lead 22 Nov 2026, before any of its runs. Version 2 (same day, before any run): after two spec reviews
(facts/driver fit; method), L1.13 split into two arms, T52 as comparator, 30 s scoring as the main read, margins and
run-0 costs added.

# L1 side track: L1.11, L1.12, L1.13 (INFO)

**Why.** The owner ruled 1.6 m first, 1.15 m after the game-rules phase, with a small 1.15 m side track in L1 (R1). Open
from L0 (G0_REPORT §2.1): (Q1) at 1.15 m the trained Strike team stayed below the script, but its opponent changed with
the tag (mark_edge at 1.6 m, field at 1.15 m); (Q2) at 1.15 m the Strike learner sees about 13–15× fewer finished
training games per game-step, and a clock loss 200 decisions away weighs only 0.99^200 ≈ 0.13: neither tested as a
cause; (Q3) the 1.6 m Guard team's 913 was scored against strike_straight only. All tier 1 (fast engine; ruling A12:
quick experiments and checks), laptop RTX 5070 Ti, one seed per arm, T44's 1,000 scoring starts, observed in the training
simulator; INFO (no pass/fail gate).

| Task | Question | What runs | Compared with |
|---|---|---|---|
| **L1.12** | Q3 | scoring only: T46's base Guard team (`ste_provisional/players/2026-11-21_ste_l012_base_guard`) against each of the 6 Strike scripts, base game (tag 1.6 m) | per Strike script, the best Guard script's holds on the same starts (T44 reference cells); worst cell first |
| **L1.11** | Q1 | Strike team trained against guard_field at tag 1.6 m (explicit training opponent; base g* is mark_edge), T46's base Strike recipe (shaped, weight 1.0), 0.55 B game-steps, new seed | strike_straight's 284 against field at 1.6 m (T44); T46's base Strike against field 85 (T56 X4) |
| **L1.13 arm A** | Q2, clock | Strike team trained against guard_field at tag 1.15 m on a **30 s training clock** (600 ticks), discount 0.99, 0.30 B game-steps, new seed | T52 (below), both clocks |
| **L1.13 arm B** | Q2, loss weight | the same at the real **120 s clock** with discount **0.997** per decision (a clock loss 200 decisions away weighs 0.997^200 ≈ 0.55, close to arm A's 0.99^50 ≈ 0.61), 0.30 B, new seed | T52 (below), both clocks |

**Comparator for L1.13: T52** (record T51/T52 of L0.12b, ABORTED at 0.54 B, information only): the 1.15 m Strike team
trained against guard_field, 120 s clock, discount 0.99; it reaches 103 of 1,000 (86–123) on T44's starts. Its saved
network is re-scored at both clocks on the same starts (paired), and its curve is read at the same update number as each
arm. T55 (5×) is shown for context only. Both 1.15 m curves level off by about 0.19 B (reviewer read), so 0.30 B per arm
is enough to compare.

**Clocks in scoring.** The time left is a network input in raw seconds, so a team trained on a 30 s clock has never seen
values above 30 s. Arm A's main read is therefore at a **30 s scoring clock** (a game file identical to tag_1p15 except
600 ticks); its 120 s score is INFO. Arm B's main read is at 120 s; its 30 s score is INFO. T52 and the scripts are scored
at both (scripts finish by about 12 s, so their 355 holds at 30 s; 42 of T52's 103 reaches come after 30 s).

**Reading words, fixed now (no category, no "validated"; one seed per arm, one start set):**
- A gain counts only if the arm's Wilson 95 % lower bound clears T52's upper bound at the same clock; otherwise "level
  with T52". A null is weak evidence (arm A raises finished games about 3.3× against a 13× gap).
- Arm A gain, arm B none: "with a shorter training clock the 1.15 m Strike team reaches N at 30 s (T52: M); the higher
  weight of a clock loss alone (arm B) did not do it". Not read as proof of the finished-games lead: the shorter clock
  also changes what the learner sees.
- Arm B gain: "weighting a clock loss more (discount 0.997) helps at 1.15 m: N against T52's M at 120 s".
- Both or neither: said as such.
- L1.11: if its interval lies above 284: "against field Guards at 1.6 m, training beat the script (N v 284): with this
  recipe field Guards are learnable at 1.6 m, so the 1.15 m Strike shortfall is not explained by the opponent alone".
  Overlap: "level with the script". Below: "below the script: field Guards are hard for this recipe at 1.6 m too, so the
  1.15 m shortfall may come from the opponent". Report finished training games per update; if they also run to the clock
  against field Guards at 1.6 m, the "below" reading carries Q2's caveat.
- L1.12: "The 1.6 m-trained Guard team holds N of 1,000 against <script> (best Guard script M)", one line per script,
  worst cell first.

**Every trained team is scored against every script of the other team** (G0 recommendation 1): L1.11 against all 5 Guard
scripts at 1.6 m; both L1.13 arms against all 5 at 1.15 m (at their main-read clock); worst cell first, Wilson intervals,
paired counts against the best script.

**Controls (any not PASS: no number reported, exit non-zero).** L1.12: the T46 Guard v strike_straight cell equals
T46's own evaluation game for game (913). L1.13: T52 re-scored at 120 s equals its own evaluation game for game (103).
Training runs: the driver's existing controls (run 0 PASS before each Strike run; script cells equal the references game
for game).

**Budget** (owner's 13 GPU-h for L1 + L2; config caps): L1.12 0.1 (expected minutes); L1.11 **0.9** (T46 base Strike
0.594 h of training + run 0 about 0.07 + the 720 s final reserve; T52 aborted on a tight cap); L1.13 **1.0** for both arms
(each about 0.30 B ≈ 0.33 h at T46's rate × 1.1–1.3 at 1.15 m, + run 0 each). Config caps change from 0.7/0.8 to 0.9/1.0
(L1 sum 8.1; L1 + L2 still within 13 with L2's high 3.9 and one confirming seed). Laptop, alone or side by side if
memory allows (12 GB).

**Outputs.** Run folders `runs/<date>_ste_l1{11,12,13}_*`; results.json/md; per-game npz; 2-D clips with the height
panel (one win, one loss per trained run, clip seed's own starts); records **T57 (L1.12), T58 (L1.11), T59 (L1.13)** with
ledger rows; one figure (bars with intervals: each arm and T52 at both clocks; L1.11 against the scripts); a plain
write-up for the owner; two reviewers + the results-and-plan discussion before reporting.

**Build needed (L1 tooling, test first, independent QC):**
1. A variant may name its **training opponent** (`train_opponent`, labelled "explicit, not the maximin pick"): used by
   training, the curve, the final cells, the script baseline and the result's opponent field
   (`exploit.opponent_of` and its callers, `ste_exploit_l012.py` curve_point/result); preflight's maximin check is skipped
   for that side only and the record says so; `_VARIANT_KEYS` accepts it.
2. A variant may name a **training game** (`train_game`, a pinned [games] entry): training builds its learner on it; curve
   and final scoring use `game` (the variant's scoring game); preflight checks both files' sha256. New game files
   `configs/ste_l1/tag_1p15_clock30.toml` (tag_1p15 with game_steps 600) — used as arm A's training game AND as the
   30 s scoring game.
3. `discount_factor` joins the per-side/variant override keys (arm B), recorded in results.
4. Pilot / run-0 inputs per variant as the driver requires (`--pilot-json`, `--run0-json`, `[run0]`), budgeted above.
5. A **scoring tool** (`scripts/ste_score_matrix.py`): scores saved players against every script of the other team on a
   given game file and clock, with the controls above; used by L1.12, T52's re-score, and every cross-play table.
6. T52's network (`runs/ste_archive/l12b/runs/2026-11-21_ste_l012b_tag_1p15_strike/`) added to `ste_provisional/`.
7. The driver launches L1 tasks against the L1+L2 caps (done in the config change, check).

**Addendum (22 Nov 2026, before any run).** The build measured the driver's time rule: L1.11's run asks 1.07 h of
allowance (run 0 + training + the 720 s final reserve) and L1.13 needs about 1.6 h for two run 0s, two arms and the
re-scores at the other clock (T52 and both arms). The lead raised the task caps to **L1.11 1.2** and **L1.13 1.7** GPU-h
(L1 caps sum 9.1; with L2's high 3.9 that is 13.0, the owner's cap). Caps are ceilings: expected use stays about 0.85
(L1.11) and 1.2 (L1.13). Nothing else in this spec changes. Arm A is trained and scored on the 30 s game file
(`configs/ste_l1/tag_1p15_clock30.toml`); the variant key `reference_variant` and a per-variant run 0 were added by the
build so each arm has its own run 0 and its own screen reference cells.

**Addendum 2 (22 Nov 2026 ~20:45, after L1.12 and T52's re-score, before this test runs): L1.14, the time-left test
(INFO, scoring only).** T52 (trained at 120 s) reaches more against guard_field when the game is 30 s long (145) than
it does in the first 30 s of a 120 s game (61, paired 17 v 59); at 120 s its late attacks mostly fail (in 99 of 126 games
where every Strike drone was tagged, the last fell after 90 s). Hypothesis (a reviewer's reading, not tested): the
network holds back while its time-left input is large. Test, by changing only the time-left value the policy sees (all
other inputs and the game untouched; out-of-game drones keep their zeroed inputs), against guard_field, T44's starts:
- **Control C-offset:** T52 in the 30 s game with time-left + 90 s. It must reproduce the first 600 ticks of T52's own
  120 s games game for game (every reach before tick 600 at the same tick; 61 reaches). Not PASS: no number reported.
- **Test T-clamp:** T52 in the 120 s game with time-left clamped to at most 30 s. Reading words: if its reaches' Wilson
  interval lies above T52's 120 s interval (103: 0.086–0.123): "the 1.15 m Strike team attacks earlier and reaches more
  when its time-left input says time is short: N against 103"; overlap: "clamping the time-left input did not change
  its reaches"; below: said as such. One network, one start set.
- **Arm A at 120 s, clamped to at most 30 s** (INFO): arm A never saw a time-left above 30 s; this is the fair 120 s read
  of arm A, beside its plain 120 s score.
Budget: new task **L1.14** (cap 0.3 GPU-h; expected about 0.2) taken from L1.9 (1.9 → 1.6, its estimate is 0.5–1.9);
the L1 caps still sum to 9.1. Tooling: a per-player time-left override in `scripts/ste_score_matrix.py`
(`offset_s` or `clamp_max_s`), recorded in results; test first; two code reviews.

**Addendum 3 (22 Nov 2026 ~22:30, owner approved the plan after two reviewers; before these run).**
- **L1.14 run order (both code reviews):** C-offset runs first; the T-clamp and arm-A-clamp runs start only after it
  PASSES (the run chain stops otherwise).
- **L1.15 delay check (INFO, scoring only, new task, cap 0.3 GPU-h taken from L1.10: 1.2 → 0.9).** Why: the tier-1
  game already carries the fitted Starling response delay (`params/real_exploratory_v0.toml` `delay_s` 0.1482: a delay
  from command to motion, not a late position; tags are judged on true positions, as motion capture would). Whether the
  1.15 m picture depends on that delay is unmeasured; L0.14 found more delay lets drones come closer than the filter's
  1.10 m. Re-score at `delay_s` **0** and **0.30 s** (0.148 s = the existing results; nothing else changed: two
  study parameter files, copies of v0 with only `delay_s` changed, labelled study-only, never a drone value), tag 1.15 m,
  120 s, T44's 1,000 starts: the 1.15 m-trained Strike team T55 (5×) and Guard team T54 (3×) against their training
  opponents (guard_field; strike_straight), and the script cell guard_field v strike_straight. Report wins with Wilson
  95 % intervals, paired counts, how games end, and the distance at each tag (minimum, median) and the closest approach.
  Reading words, fixed now: "the 1.15 m picture **depends on the response delay**" if, at 0 or 0.30 s, any of the three
  cells' wins move outside both its own interval at 0.148 s and the new one (non-overlap), or the median tag distance
  moves by more than 1 cm; then the 1.15 m training side track pauses until L1.7 (realistic drone in tier 1).
  Otherwise "the 1.15 m results hold across response delays 0–0.30 s" and the side track continues. One start set; no
  training.
