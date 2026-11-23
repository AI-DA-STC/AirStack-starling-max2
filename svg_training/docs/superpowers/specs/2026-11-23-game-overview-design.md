INTERNAL · design for one overview page on the game rules and the main learnings; panel 23 Nov 2026; APPROVED by the owner 23 Nov 2026 (build today; page name docs/OVERVIEW.md).

# Design: one overview page for the lab lead (rules of the game, main learnings)

## Intent
The owner's lab lead wants to see the rules of the game and the higher-level learnings and findings, for both the NUS
port and STE's own learning track. Owner's words: "my boss wants to see how the game is rules of the game, and the
higher level learnings and findings from our work so far". Reader: the internal lab lead, who knows Starlings, AirStack,
the safety filter and motion capture, but not reinforcement learning. Wanted today.

## What is wrong today (measured by the panel's newcomer reader, starting at `README.md`)
| Question the lead asks | Today |
|---|---|
| What are the rules of the game STE trains now? | 540 lines over 3 files; README §3 describes the older NUS-port set-up with no tag, so the front page gives the wrong game |
| Why did STE stop using NUS's policies? | about 95 lines over 2 files; the pause of the NUS route (20 Nov) appears only in `ste_learning/README.md` |
| What has STE's own training shown? | not found in 4 files; results T57–T64 appear only as bare row ids in `STATUS_LATEST.md` |

Also: four pages claim to be the first page; `docs/THE_GAME.md` says contact tags are "a separate track" (superseded
by gate G0, 22 Nov); README §6–7, `docs/NUS_PORT_REPORT.md` §12 and `docs/WHAT_WE_FOUND.md` stop on 19–20 Nov.

## Goals
- One page answers all three questions, each within 60 lines and at most one click from `README.md`.
- The rules of both games side by side; the main learnings, each with one number and its ledger row.
- Pages that say something wrong are marked or fixed, so a lead who clicks on does not hit a contradiction.

## Non-goals (today)
- No rewrite of README, `NUS_PORT_REPORT.md`, `WHAT_WE_FOUND.md`, `G0_REPORT.md` bodies.
- No new figure. No change to the docs checker. No status page: status stays in Linear and `ste_learning/status/STATUS_LATEST.md`.

## Constraints
- Write only inside `svg_training/`; commits by explicit path; never push; the pre-commit docs check passes.
- Every number traces to a ledger row or record; each learning says "observed in the training simulator" (T63 is a
  flight-log analysis); never "validated"; nothing has flown.
- `ste_learning/GAME_SPEC.md` stays the only source of game values and their labels; the new page copies only values
  labelled FIXED and links each row to it.
- The page is linked from the NUS-facing README, so NUS may read it: the NUS story is told as facts and test results,
  neutrally (NUS agreed its game details and STE's results on its code may be published).
- It is a reader page (label Read in `docs/README.md`), so the folder's reader-page rules apply: neutral and factual,
  no "you", no owner quotes, no "the partner", no clock times or agent roles; every label defined where it first
  appears; ledger row ids (T numbers) only in an Evidence column, each linking its record; mechanisms say "likely" until
  a control test has run (the push-blocking reading stays "likely").
- Owner's writing rules: plain words, no walls of text, captions 2–4 sentences and at most 400 characters, numbers
  explained physically.

## Decisions (panel of four: technical writer TW, flight-test engineer FTE, engineering manager EM, newcomer reader NR)
| Point | Decision | Vote |
|---|---|---|
| Entry page | a NEW page, not a README rewrite; README stays NUS-facing | 4–0 |
| P1 Name | `docs/OVERVIEW.md` | 2–2 (TW, FTE for `OVERVIEW.md`, neutral because NUS sees the link; EM, NR for `LEAD_OVERVIEW.md`, says who it is for). **Lead's ruling: `OVERVIEW.md`**, since the content serves any reader and NUS can see it; owner to confirm |
| Rules | one side-by-side table, NUS port game and STE game | 4–0 |
| P2 Learnings | seven rows; the stage 5.1 FAIL, T58 and T64 each keep their own row (negative results at equal weight) | 4–0 |
| P3 Filter, tag and keep-out | one row in the rules table plus one caveat line: at the 1.15 m tag the band is 5 cm, smaller than the 3–10 cm tracking lag measured on a real hover, so a real tag there could be decided by lag; T61's closest tag 1.106 m | 3–1 (FTE wanted a full section) |
| P4 Automated number check | later, as its own change to the docs checker | 3–1 (EM: today if it passes review) |
| P5 Stale README sentences | dated banner today, bodies fixed later | 3–1 (FTE: fix the sentences too) |
| P6 Other "read first" claims | demote today: README gets one line "Lab lead: start at docs/OVERVIEW.md"; `ste_learning/README.md` says "working folder"; `docs/README.md` lists OVERVIEW first | 4–0 |
| P7 Status on the page | no status words ("in progress", "next", "blocked"); a short "What has not been done" list of limits (nothing flown, one seed, one opponent) and one line pointing to STATUS_LATEST and Linear for open work | 4–0 |
| P8 New figure | none today; reuse `docs/figures/g0_report/game_diagram.png` and `docs/figures/overview_tests.png` | 4–0 |

## The page, `docs/OVERVIEW.md` (about 70 lines)
1. **The answer in four lines**, then a box: "Training simulator only. Nothing here has flown. A tag is a game rule, not
   a contact."
2. **The two games** (table, one idea per cell). Rows: teams; space (2-D / 3-D, arena); zone; game length; how a Guard
   stops a Strike (NUS: soft push / STE: 1-for-1 tag); tag distance (none / 1.6 m first, 1.15 m later); safety filter
   (added in Test 4 / on every pair); speeds; decision rate; where the full values are. NUS cells copied from README §3
   and `NUS_PORT_REPORT.md` §3; STE cells from GAME_SPEC (FIXED only). Then the 1.15 m caveat line (P3).
3. **Figure 1** `game_diagram.png` (the STE game), **Figure 2** `overview_tests.png` (the six tests), captions naming
   the generating script.
4. **Seven learnings** (table: learning | number | record), in this order:
   1. The safety filter and free height break NUS's push-blocking: Strike reaches G19 v S20 per 1,000 go 9, 17, 43,
      740 (filter), 983 (3-D), 979 (Isaac Lab drones); under STE conditions Guards that park in the zone hold more
      games than NUS-trained Guards (rows T18–T20, T22–T24).
   2. STE's conditions are trainable: STE's simple trainer gave a Guard team holding 829 of 1,000 against S20 (parked
      Guards 429) (T41).
   3. STE's port of NUS's training method narrowly failed its pre-set check (one of three seeds by small margins)
      (T43); the NUS route was paused on 20 Nov and STE runs its own track.
   4. At the 1.6 m tag, trained teams beat the best hand-written tactic against the opponent they trained on (Guard
      913 v 808, Strike 636 v 192; record of T46, `records/2026-11-21_ste_l012_best_response_record.md`); against other opponents the Guard team is above the best tactic for four of
      six Strike tactics (T57).
   5. A Strike team trained against a different Guard tactic only draws level with the hand-written one (277 v 284; T58).
   6. At the 1.15 m tag both sides learn but stay below the hand-written tactics (Guard 572 v 645, Strike 134 v 355;
      Guard: T56, `records/2026-11-22_ste_l012c_tag_1p15_guard_record.md`; Strike: `records/2026-11-22_ste_l012c_tag_1p15_strike_record.md`).
   7. Isaac Lab trains as well at about 5× the GPU time (832 v 836; T53); the 1.6 m teams on Isaac Lab drones shift
      −33 to +47 of 1,000 per matchup (T64); the real hover position estimate differs from motion capture by about
      1 cm (T63, flight-log analysis).
5. **What has not been done**: nothing flown; one training seed per side; each trained team scored mainly against
   its own training opponent; no deployable strategy yet. Open work: STATUS_LATEST and Linear (one line).
6. **Where to read more** (links only): GAME_SPEC, G0_REPORT, NUS_PORT_REPORT, WHAT_WE_FOUND, glossary.

## Today's slice (three tasks, one reviewer each)
1. Write `docs/OVERVIEW.md` as above.
2. Dated banners ("Superseded 22 Nov 2026: the NUS route is paused and STE runs its own track with a tag; see
   docs/OVERVIEW.md") on README §6–7, `NUS_PORT_REPORT.md` §12 and the top of `WHAT_WE_FOUND.md`; fix the tag
   sentence in `THE_GAME.md`.
3. Entry claims (P6).
Then: final review (most capable model), one fix wave, the newcomer acceptance test, commit, mirror pull.

## Later (each its own change, owner asks first)
README §6–7 and `WHAT_WE_FOUND.md` brought up to date; the automated number check (P4); a rules figure from GAME_SPEC
values and the FTE's distance ruler; a 10-line summary on top of G0_REPORT §5.

## Builder check (23 Nov), answers
- **Evidence is the record, not the ledger row's short text:** 913/808 and 636/192 are in T46's record; 572 and 645 in
  T56's; 134 and 355 in the 1.15 m Strike record. Every number is checked against its record by a reviewer.
- **NUS column:** 3 v 3 (README §3: 3 Guards v 3 Strikes); no tag (a soft push keeps the teams apart); 2-D; Guards
  kept inside a 3.2 m circle, Strikes start 3.2 m out, no walls (hangar scale); 200 steps of 0.60 s = 120 s; zone radius
  1.6 m; speeds 0.20 and 0.30 m per step, the same 0.33 and 0.50 m/s as STE's Guard and Strike. Values from README §3
  and `NUS_PORT_REPORT.md` §3, which NUS agreed may be published.
- **STE column, FIXED only:** 3 v 3, 6.5 m arena, zone radius 1.6 m, 120 s, Strike start ring 2.75 m, tag 1.6 m
  (1.15 m is a later setting), filter on every pair. PROPOSED values (Guard start disc, win ticks) are left out with
  "see GAME_SPEC". A note says the programme's other sizes (2 v 1, 5 v 3) are not trained yet.
- **Decision rate:** one decision per 0.60 s in both games.
- **Figure 1** (`game_diagram.png`, from `scripts/make_g0_report_figures.py`) shows the STE game from above (6.5 m
  arena, tags 1.6 and 1.15 m, filter radius); the caption says it is a top view of a 3-D game.
- **Page name:** the owner confirms `docs/OVERVIEW.md` when approving this design; the build waits for that.

## Left to the builder
Exact wording within these rules; the caption text.

## Done when
- The newcomer reader answers the three questions from `README.md` in at most one click and 60 lines each.
- The docs check passes; two reviewers find no wrong number; every learning row has a record link.
