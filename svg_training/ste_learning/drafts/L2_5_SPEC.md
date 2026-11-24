INTERNAL · spec of task L2.5 (the parked-Guard control and the scripted screen under the new rules), written before any of its runs; DRAFT until the lead's review freezes it · [../README.md](../README.md); the task's row: [WORK_BREAKDOWN](../WORK_BREAKDOWN.md) L2.5

Written 24 Nov 2026 by the L2.5 builder, before any run of the screen. Run by the builder: a CPU speed probe and a
96-game scratch check (both below, neither a result), the tests, and the driver's preflight and projection (no play).

# L2.5: Parked-Guard control and scripted opponents under the new rules (INFO)

**Why.** The 1.6 m one-for-one tag is wider than the 1.10 m filter distance, so a Guard team may hold by standing near
the zone and trading drones, not by playing (DISCUSSION §2.14: "a large radius favours a parked Guard — gate against
it"; §2.15: three parked Guards on a 0.8 m ring cover the zone). T44 measured this on the old rules (parked Guards
43.0–98.6 % hold, the best moving script mark_edge 80.8 % at worst). L2.1 (filter option B), L2.3 (landing) and L2.4
(team sizes) were built on 24 Nov 2026, all off by default. This screen asks, with scripted players only: does the tag
favour a Guard team that stands still once the new rules are on, and what do landing and option B change? The owner's
P2 (option B) and P7 (drone loss) rulings read the record, so option B is shown on and off side by side.

All tier 1 (fast engine), CPU, scripted players only, one start set (T44's 1,000 3v3 starts), observed in the training
simulator; INFO (no pass mark; the controls are gated). 0 GPU-h (task cap 0.5 GPU-h untouched).

## The arms

Main game (configs/ste_l011/base.toml, T44's file): 3v3, tag 1.6 m one for one at 3-D centres, both drones out, zone
1.6 m at the centre of the 6.5 m lab arena, zone_disc_ring starts, Starling layer with the filter on every pair (1000
sweeps, check every 8), fitted PX4 response (exploratory). Each new game file is base.toml value for value but for the
keys its header marks (tests/test_ste_l25.py). Labels: `touchdown_z_m` 0.15 FIXED (owner R28); `land_speed_mps` 0.6
MEASURED in the `_ours` configs; option B PROPOSED (P2 open).

| Group (gate file) | Game file | Landing | Filter share | Tag | Guards × Strikes | Cells | Games |
|---|---|---|---|---|---|---|---|
| ctl_reference_replay (previous state; must replay T44) | `configs/ste_l011/base.toml` | off | equal | 1.6 m | 5 × 6 | 30 | 30,000 |
| landing | `configs/ste_l2/l25_landing.toml` | on | equal | 1.6 m | 5 × 6 | 30 | 30,000 |
| gy | `configs/ste_l2/l25_gy.toml` | off | guard_yields | 1.6 m | 5 × 6 | 30 | 30,000 |
| landing_gy (new rules, option B) | `configs/ste_l2/l25_landing_gy.toml` | on | guard_yields | 1.6 m | 5 × 6 | 30 | 30,000 |
| ctl_tag_off_landing (parked, no tag) | `configs/ste_l2/l25_landing_tag_off.toml` | on (inert) | equal | off | 2 parked × 6 | 12 | 12,000 |
| ctl_tag_off_landing_gy (parked, no tag) | `configs/ste_l2/l25_landing_gy_tag_off.toml` | on (inert) | guard_yields | off | 2 parked × 6 | 12 | 12,000 |

Guard scripts: guard_parked_centre (at 3v3: every Guard holds its start, zero command: **the Guard team that stands
still**), guard_parked_ring (flies to a ring station round the zone and stops: **parked**), and three moving scripts:
guard_mark_edge, guard_mirror, guard_field. Strike scripts: straight, flank, high, low, sacrifice, converge (high and
low: tier 1's vertical response is not fitted; read with care). With the tag off and no drop-outs no drone ever leaves,
so landing is inert there; the tag-off files keep it on so that each differs from its tag-on file by `tag.mode` only.

**Behaviours named in the task that do not exist.** The task row names Strike behaviours "straight, flank, feint,
dodge". `opponents/scripted.py` has no feint and no dodge script. They are **not built** for this screen (no scope
growth): the six existing Strike scripts all run with the tag on (they have since L0.11), and the screen says which
behaviours are missing. If the owner wants them, they are a later small task (a script each, plus a cell column). The
row's file `tests/test_scripted_tag.py` is not created; `tests/test_ste_l25.py` covers this screen.

**What P7 gets from this screen.** Drone loss through tags only (tagged pairs land as filter obstacles, L2.3). No
scheduled drop-out (`dropout_fraction` 0) and fixed 3v3: drawn team sizes (L2.4) are not screened (the sweep driver plays
fixed sizes; the learner's absent-slot masking is an L3 item). Other team sizes (1v1, 2v1, 5v3) are not screened here.

## Controls (gated by the driver; a failure stops the run, exit 6, before any reading)

As L1.9 and L0.12b, at 3v3, on the new-rules game (landing + option B) where they can be:

| Control | Game | Known answer |
|---|---|---|
| ctl_tag_fires_3v3 | l25_landing_gy_tag_10m (10 m tag), zero v zero, 100 ticks | every game 3 tags at step 1 |
| ctl_reach_fires_3v3 | T44's zone_2p4_tag_off, zero v straight, 200 ticks | every game a reach |
| ctl_reference_replay | base (T44's file and starts) | all 30 cells equal T44 game for game (CPU) |
| ctl_tag_off_landing, ctl_tag_off_landing_gy | the tag-off files | zero tags |
| ctl_same_seed | landing_gy batch 0 played twice | every game equal (CPU: exact) |
| ctl_stand_still | landing_gy, every Guard v zero Strikes, **600 ticks** | zero reaches |
| ctl_still_3v3 | landing_gy, zero v zero, 200 ticks | zero tags |
| ctl_tiny_tag | l25_landing_gy_tag_0p05 (0.05 m tag), every Guard v straight, **600 ticks** | zero tags |
| global | every group | tags one for one; one start set (T44's); no non-finite action |

Change from L1.9: ctl_stand_still and ctl_tiny_tag stop at 600 ticks (30 s), not 2,400, to keep the screen near 30
minutes. Why that does not weaken what they test: in ctl_stand_still every Strike drone commands zero, so it can reach
the zone only if the safety filter carries it 1.15 m inwards (ring 2.75 m, zone 1.6 m), and the filter only pushes drones
apart; within 30 s every moving Guard script has reached its post, after which nothing moves a still Strike drone. In
ctl_tiny_tag a tag needs two drones within 0.05 m of each other, far inside the 1.10 m distance the filter keeps every
pair apart; a breach of that size would be a filter failure, which the breach and closest-approach columns of the
main groups (full length) would show. Both answers are "never", which a longer game tests no better once play has
settled.

**Plumbing checks, read before any number (pre-registered; computed after the run from its own `cells/*.npz`, which
the driver already writes per game: outcome, end_step, tags, strikes_left, closest_3d_m, start_pos_m; no code change).**
The cells being compared are paired: same T44 start, same player seeds, CPU (exact replay: the same-seed control and the
T44 replay check it). So two cells differ in a game only if the rule that separates them changed that game; with no
effect at all they are equal bit for bit (the builder's scratch check: landing on with the tag off, where no drone ever
lands, played T44's tag-off game identically).

- **P-b option B reached the game.** ctl_tag_off_landing and ctl_tag_off_landing_gy (the filter acts on Guard–Strike
  pairs when no tag ends them) must differ, in at least one of their 12,000 paired games, in outcome, end_step or
  closest_3d_m. If not: "**option B not shown to reach the game**".
- **P-c landing reached the game.** landing and ctl_reference_replay (base), over their 30 paired cells (30,000 games),
  must differ in at least one game in end_step or closest_3d_m (only a drone landing as a filter obstacle can change a
  live drone's path; the closest-approach column itself counts live drones only). If not: "**landing not shown to reach
  the game; no landing word (reading 4) is written**". The tag-fires control (every pair tagged at step 1 with landing
  on) and `tests/test_ste_l25.py` (the screen's game lands a tagged pair) back it, but do not replace it.

**What a failed plumbing check withholds** (the numbers of every group are still reported, labelled):

| Fails | Withheld | Still reported as plain numbers, labelled |
|---|---|---|
| P-b | reading 3 entirely; the option B rows of reading 2; reading 1's words for gy and landing_gy; reading 4's landing_gy v gy pair | gy and landing_gy, labelled "option B not shown to reach the game" |
| P-c | reading 4 entirely; reading 3's landing_gy v landing pair (gy v base stays) | landing and landing_gy, labelled "landing not shown to reach the game"; readings 1 and 2 on them keep their words (tag on v off does not depend on landing) with that label |

When P-b holds, the tag-on gy arms are read with full words even if option B changed few games there (below).

- Builder's scratch check (24 Nov 2026, 32 of T44's starts × 3 cells, CPU, not a result): landing with the tag off
  played T44's tag-off game identically; option B with the tag off changed 13 of 96 outcomes; with the tag on,
  landing and option B each changed 0–1 of 96 outcomes and 4–10 end steps.
- The tag-on option B arms may change few games: at 1.6 m the tag usually fires before the Guard–Strike filter acts
  (it starts head-on at about 1.32–1.57 m, DISCUSSION §2.14). The number of changed games is reported per cell; a
  small number is a result for P2, not a fault, once P-b holds.

## Reading words (fixed now; INFO; no "validated")

Hold rate = Guard team wins of 1,000 games, with its Wilson 95 % interval. Two rates are "distinguishable" only when
their intervals do not overlap (stricter than a 5 % test; at 1,000 games it cannot see shifts under about 40–60 games:
prose guidance, as L1.9). **"No change detected" means no change larger than this test can see, not "no effect".** One
seed, one start set: the intervals cover scoring noise only. About 30 cells per comparison and no multiplicity
correction: a single "distinguishable" cell is read with care.

1. **Still Guard v the moving scripts.** Words fixed in advance for the three new-rule sets (landing, gy,
   landing_gy); base is T44's game, whose answer is already known (still Guard 43.0 % at worst against mark_edge
   80.8 %), and is shown beside them. For each rule set and each parked script (still = guard_parked_centre, ring =
   guard_parked_ring): its worst-cell hold H_p (lowest over the six Strike scripts) against **each** moving script's
   worst-cell hold H_m (mark_edge, mirror, field separately; none is picked after the run). The **named comparator is
   guard_mark_edge** (T44's g* at 1.6 m and the L0.12 opponent, named before this run). Words, per pair: "**still Guard
   above mark_edge**" if H_p's lower bound > H_m's upper bound; "**still Guard below mark_edge**" if H_p's upper bound <
   H_m's lower bound; else "**still Guard not distinguishable from mark_edge**" (and the same with "ring Guard", mirror,
   field). The same words per Strike script (cell by cell) in a table; the driver's g* is quoted, and a parked g* is
   said so. Reading 1 alone never says the tag favours anything.
2. **With and without the tag** (the task's "parked Guard hold rate with and without the tag"), even split (landing v
   ctl_tag_off_landing) and option B (landing_gy v ctl_tag_off_landing_gy), per parked script and Strike script and on
   the worst-cell holds: "**the tag raises the parked Guard's hold**" (with-tag lower > without-tag upper), "**the tag
   lowers it**", else "**no change detected**". **The risk word**, for landing and landing_gy only (the arms with a
   tag-off twin), needs both readings: "**the 1.6 m tag favours a Guard team that stands still, against scripted
   Strikes, in this rule set**" if the tag raises the still Guard's worst-cell hold (reading 2) **and** the still
   Guard is above or not distinguishable from mark_edge (reading 1); "**not seen with scripted Strikes in this rule
   set**" if the still Guard is below mark_edge; otherwise (the tag raises the hold but the still Guard stays below, or
   no tag effect is detected while it is not below) the two readings are stated side by side with no risk word.
3. **Option B on and off** (for P2), landing_gy v landing and gy v base, per cell: "**option B raises the Guard team's
   hold**", "**option B lowers it**", else "**no change detected**", counted per Guard script; H, R, g*, s* of each group
   side by side (the driver's shortlist rule, configs/ste_l011/gates.toml [shortlist]); the changed-game counts (INFO);
   the closest 3-D approach and breach rate per cell (L2.1 known shortfall: a Guard drone pinned at a wall lets a Strike
   drone close to 0.39 m in tier 1). Filter activity for P2, as the driver records it: the share of tags with the
   filter active on the tag's own tick (an upper bound) and with the pair pushed together (L0.12b's columns), and the
   filter rate (share of live drone-steps corrected, every pair). **Guard–Strike filter activations before a tag are not
   shown** (the driver does not record them; a later measurement if P2 needs it).
4. **Landing on and off** (for P7's landing part), landing v base and landing_gy v gy: the same words with "landing"
   for "option B".

**Paired readout for readings 3 and 4 (pre-registered, INFO, no verdict).** The Wilson words cannot see a paired effect
of about 1 % (10 games in 1,000). So for each compared pair of cells (same Guard and Strike script, same 1,000 T44
starts), from the per-game outcome arrays: the discordant games and their direction, **hold → reach** (the Guard team
held without the rule and lost with it) and **reach → hold**, and the games whose end step changed with the same
outcome; summed per Guard script and per rule set. Reported as counts beside the Wilson words, without a pass mark; the
record states that one seed and one start set make these counts the effect on these starts only.

## Limits, stated in the record

Scripts only, no trained team (L3.5 must beat the parked Guard); tier 1 only (tier 2 with the new rules is L2.6); one
start set; 3v3 only; vertical Strike scripts not fitted in tier 1; scripted players decide every tick (L011-F1); option
B is PROPOSED; the closest-approach and breach columns count live drones only, so they cannot show how close a drone
comes to a landing one (a clean breach column under landing does not say landing is safe; L2.3's own tests do);
landing's known shortfall (a drone landing onto one held at the height-band floor closes to 0.95–1.05 m);
feint and dodge not built; no drop-out, no drawn sizes.

## Time (projected; CPU only)

Speed probe (RTX 5090 workstation CPU, 24 Nov 2026, a session scratch script, not committed; nice 19; machine load
2–10): l25_landing_gy, 30 cells × 1,000 games, ticks 5–105: **0.610 s per batch tick on 2 threads, 0.355 s on 8
threads**; base.toml 0.531 s on 2 threads; 12,000 games 0.252 s on 2 threads. About 2.05 × 10⁻⁵ s per game-tick on 2
threads and 1.18 × 10⁻⁵ on 8. Expected ticks per batch from T44 (3v3 tag-on batches ended in 400–500 ticks; tag-off
batches ran 2,400: parked v flank holds by time-out).

| Group | Batches | Tick cap | Expected ticks | Expected CPU s, 8 threads | 2 threads | Driver's worst case (cap × 0.7 s) |
|---|---|---|---|---|---|---|
| ctl_tag_fires_3v3 | 1 | 100 | 1 | < 1 | < 1 | 70 |
| ctl_reach_fires_3v3 | 1 | 200 | ~100 | 1 | 2 | 140 |
| ctl_reference_replay | 1 | 2,400 | ~400 | 142 | 246 | 1,680 |
| landing | 1 | 2,400 | ~500 | 177 | 308 | 1,680 |
| gy | 1 | 2,400 | ~500 | 177 | 308 | 1,680 |
| landing_gy | 1 | 2,400 | ~500 | 177 | 308 | 1,680 |
| ctl_tag_off_landing | 1 | 2,400 | 2,400 | 340 | 590 | 1,680 |
| ctl_tag_off_landing_gy | 1 | 2,400 | 2,400 | 340 | 590 | 1,680 |
| ctl_same_seed | 1 | 2,400 | ~500 | 177 | 308 | 1,680 |
| ctl_stand_still | 1 | 600 | 600 | 35 | 62 | 420 |
| ctl_still_3v3 | 1 | 200 | 200 | 2 | 4 | 140 |
| ctl_tiny_tag | 1 | 600 | 600 | 35 | 62 | 420 |
| **total** | **12** | **18,500** | | **≈ 1,600 s ≈ 27 min** | **≈ 2,800 s ≈ 47 min** | 12,950 × 1.1 + 600 s clips = **14,845 s = 4.12 h** |

187 cells, 12 batches, about 140 M game-ticks. The driver refuses a launch whose protected groups' worst case does not
fit the cap (QC I3), so the job's cap is **4.5 effective hours**; it re-times from its own sweep batches as it goes.
Clips: three 2-D GIFs of landing_gy (still Guard v straight, mark_edge v straight, field v flank), a few seconds each
(the clip path was run once by the builder on l25_landing_gy: a GIF was written).
The probe ran on 2 and 8 threads only; a launch on more threads is likely faster but competes with the AirStack
simulator (the brief: it records real-time logs on this machine). **Recommended: launch with `OMP_NUM_THREADS=8`**
(inherited by the job), or when the simulator is not recording.

## Launch (the lead launches; not run by the builder)

Requires task L2.5 to have a cap in `configs/ste_learning.toml` (it had none on 24 Nov 2026: `ste_job.py launch --task
L2.5` refused; the builder's second commit adds `"L2.5" = 0.5` and the L2 ID, flagged for the lead). `<d>` the launch
date; `<sha>` the gate file's sha256 at launch (`sha256sum configs/ste_l2/l25_screen_gates.toml`).

```
cd ~/AirStack-starling-max2-dev/svg_training && unset PYTHONPATH && export OMP_NUM_THREADS=8
~/miniconda3/envs/env_isaaclab/bin/python scripts/ste_job.py launch --task L2.5 --name l25_screen \
  --run-dir runs/<d>_ste_l25_screen --min-s 600 --gpu-h 0 --settings configs/ste_learning.toml -- \
  ~/miniconda3/envs/env_isaaclab/bin/python scripts/ste_sweep_l011.py --gates configs/ste_l2/l25_screen_gates.toml \
  --run-dir runs/<d>_ste_l25_screen --cap-h 4.5 --expect-gates-sha256 <sha>
```

After the run: the plumbing checks P-b and P-c, then the four readings, into `records/<d>_ste_l25_screen_record.md`
(INFO) and a ledger row; evidence (results.md, controls.json, gates.toml, the clips) under `records/evidence/`.
