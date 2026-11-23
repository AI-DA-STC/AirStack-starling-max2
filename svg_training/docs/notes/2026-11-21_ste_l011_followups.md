INTERNAL · an investigation note that a record cites, kept as written: what a scripted "hold" is made of (STE task L0.11 follow-ups) · start at [../../README.md](../../README.md); the record: [2026-11-21_ste_l011_screen_record.md](../../records/2026-11-21_ste_l011_screen_record.md)

> 21 November 2026 · STE task L0.11 follow-ups to T44, before L0.12 is designed · INFO, no gates · training simulator,
> tier 1 (Starling layer, safety filter on every pair), CPU. Observed in the training simulator; not a flight result.

# L0.11 follow-ups: what a scripted "hold" is made of

The screening sweep T44 ([record](../../records/2026-11-21_ste_l011_screen_record.md)) shortlisted base (reference),
tag 1.2 m and tag 1.4 m. The quality check of its results found that every hold at equal numbers is a full trade. These
five checks ask what else sits behind the shortlist numbers before L0.12 is designed.

## How it was run

- **Script:** `scripts/ste_l011_followups.py`, tested in `tests/test_ste_l011_followups.py`.
- **Machine:** CPU, 4 threads.
- **Input:** a copy of T44's run folder (cell files and `results.json`, read only).
- **Starts:** every replay starts from T44's own start positions, stored per game in its cell files. They are the same
  1,000 starts for every 3v3 group in the 6.5 m arena (start sha256 `5aeba7ab2b582f29…`). Game seed 110000; players
  seed + 101 (Guard team) and + 202 (Strike team), as in T44.
- **Agreement with T44:** each replayed cell was compared with T44's own per-game results. All 8 cells replayed from
  T44's starts with every-tick decisions (11 replays) agree in all 1,000 games: same outcome, end step, tags and Strike
  drones left. So the CPU replay reproduces the GPU run game for game.
- **Output:** all numbers are in [2026-11-21_ste_l011_followups.json](2026-11-21_ste_l011_followups.json).

## 1. How many holds the tie rule decides

A tag is applied before the zone test, and at the base rules the zone radius equals the tag radius (1.6 m). So a Strike
drone can be tagged on the step it is already inside the zone; it then does not score. A recorder kept the positions
each tag was decided on; it passes the game's own result through unchanged, tested bit for bit. We counted the holds in
which a tag hit a Strike drone already horizontally inside the zone. If the zone were tested first, those games would
have been reaches.

| Rules | Guard script v Strike script | Holds (of 1,000) | Holds with a tag inside the zone | Hold if the zone were tested first |
|---|---|---|---|---|
| base (tag 1.6 m, zone 1.6 m) | mark_edge v straight | 808 | 33 (last tag in every one) | 775 |
| base | field v converge | 871 | 14 | 857 |
| tag 1.2 m | field v straight | 645 | 0 | 645 |
| tag 1.4 m | mirror v low | 672 | 31 | 641 |

- **The tie rule decides a few percent of holds, not the bulk:** 33 of 808 in base's maximin cell.
- **Known answer held:** each Strike drone tagged inside the zone was outside it one step earlier. Otherwise it would
  have scored then, and none did.

## 2. What a hold is made of

The results table now has three more columns per cell: holds leaving no Guard drone, Guards left in holds (mean), and
game length (median and 90th percentile). Guards left = Guard drones less those removed by tags; drop-outs are off in
every L0.11 game. There is also a new figure, [hold_composition.png](../figures/ste_l011/hold_composition.png). T44's
table and figures were regenerated from its cell files into `docs/figures/ste_l011/`. All 428 rows of the old table
reappear unchanged, with the new columns added at the end. The record's numbers do not change, and the other figures are
byte-identical.

| Group | Holds | Ran to the 120 s time-out | Guards left in every hold | Cell medians of game length (s) |
|---|---|---|---|---|
| base, tag 1.2 / 1.4 / 1.8 m, zone 2.4 m, 7.5 m arena, 1v1 | 3,485 – 24,966 per group | 0 | 0 | 1.4 – 9.2 |
| 2v1 | 18,883 | 0 | 1 | 1.6 – 3.1 |
| 5v3 | 29,392 | 0 | 2 | 1.1 – 9.8 |
| Guard survives a tag | 29,948 | 0 | 3 | 1.7 – 8.1 |

- **Not one tag-on game ran to the time-out.** At equal numbers every hold traded every Guard drone for a Strike drone.
- **Holds keep Guard drones only by head-count:** they leave Guards only where the Guard team starts with more drones
  (1 at 2v1, 2 at 5v3) or where a Guard survives its tag.
- **The longest cells:** 90th percentiles up to 15.9 s.

## 3. Identical columns, and whether climbing plays any part on tier 1

These were compared game by game in T44's cell files (outcome, end step, tags, Strike drones left).

- **tag 1.2 m, field against straight, high and low.** All three hold 645 of 1,000 in exactly the same games. The
  games still differ: the end step differs in every game. The high Strike drones climbed 0.51 m and the low ones
  descended 0.61 m (replayed, largest height change from the start), so the height was flown and did not change who won.
- **tag 1.4 m, parked at the centre against parked on the ring.** Same outcome in every game against straight, flank and
  converge. Outcomes differ in 10 games (high), 14 (low) and 5 (sacrifice) of 1,000.
- **Across the sweep, high and low against straight, per Guard script.**
  - Outcomes differ in most cells: base 924 games over 10 cells, tag 1.4 m 924, tag 1.8 m 600, 1v1 1,449.
  - They do not differ at 5v3 (1 game) or with a surviving Guard (27 games).
  - So climbing and descending change outcomes on tier 1 in most groups. They do not for guard_field at tag 1.2 m, nor
    where head-count already decides.
  - Tier 1's vertical response is not fitted (`configs/s2b.toml`, step `z_up_info`), so this is a tier-1 result, not a
    property of the game.

## 4. Commands held for 0.6 s (finding L011-F1)

The scripted players decide every tick (0.05 s); the sheet's decision period is 0.6 s
(`timing.decision_s` / one tick = 12 ticks). We replayed the best scripted Guard against the best scripted Strike from
the same starts with every command of both teams held for 12 ticks, phased from each game's start. A hold of 1 tick
equals the plain player bit for bit (tested).

| Rules | Guard v Strike | Hold, every tick (95 %) | Hold, held 0.6 s (95 %) | Games that change |
|---|---|---|---|---|
| base | mark_edge v straight | 808 (0.782–0.831) | 793 (0.767–0.817) | 41 (28 to reach, 13 to hold) |
| tag 1.2 m | field v straight | 645 (0.615–0.674) | 645 (0.615–0.674) | 0 (identical games) |
| tag 1.4 m | mirror v low | 672 (0.642–0.700) | 738 (0.710–0.764) | 170 (52 to reach, 118 to hold) |
| tag 1.4 m | mirror v straight | 695 (0.666–0.723) | 693 (0.664–0.721) | 46 (24 to reach, 22 to hold) |

- **Little change for most pairs:** holding commands for 0.6 s barely moves the outcome against the straight Strike;
  both scripts steer at nearly fixed targets during a game of about 2.5 s.
- **The exception is the low Strike at tag 1.4 m:** 66 more holds when the commands are held (it is a z_up_info column,
  not fitted on tier 1).
- **For L0.12:** a learner deciding every 0.6 s faces about the same scripted opponents as the sweep measured, except
  for the height scripts.

## 5. The base reach and its Wilson interval

The base maximin cell, mark_edge against straight, is reached in **192 of 1,000** games (from the cell file). Its 95 %
Wilson interval is **0.169 – 0.218** (`core/metrics.wilson_interval`). The upper bound is above L0.12's 0.2 line, so on
the L0.12 rule this scripted Strike would not by itself make the base case Guard-trivial.

## Limits

- Scripted players only. Tier 1, with the safety filter on every pair and an exploratory fitted PX4 response. CPU
  replays of T44's starts, one cell at a time, agreeing game for game with T44 where compared.
- Check 1 covers four cells, not the whole sweep.
- Check 4 changes the decision period of the scripts, not of a learner.
