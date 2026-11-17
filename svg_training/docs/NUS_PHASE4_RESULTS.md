# NUS port, Phase 4: the transfer ladder (results so far: rungs 1 to 3 of 6)

Observed in the training simulator (the replica of the partner's 2-D game, then our game with point drones and with the exploratory fitted drone
model). Nothing is flown. The partner's converted policies stay frozen; each row changes one behaviour (rung 2 changes two, owner answer 3). INFO runs
without gates; T17 (the archive pair through Phase 3's gates) PASSED. Every number is a Strike reach rate with its Wilson 95 % interval from 1,000 paired
games per pair on one starts file and one seed: no method claim. The records mark values that equal a local (partner or hangar) value as "at the local value"; since 18 Nov 2026 NUS agreed that its settings may be stated, and they are in [NUS_PORT §3](NUS_PORT.md#3-phase-0-answers-and-the-hangar-geometry).

**Rows 4, 5a, 5 and 6** (the all-pairs safety filter, 3-D at one height, the physics drone in Isaac Lab): results pending (running since 18 Nov 05:52), one after another in the background with `--accept-long` (the first foreground attempt at row 4
is T21 ABORTED: `records/2026-11-18_nus_phase4_rung4_record.md`). The whole NUS port, with NUS's own runs, the self-play matrix
and the videos: [NUS_PORT](NUS_PORT.md).

![Strike reach rate by ladder row](figures/nus_phase4_ladder.png)

*Figure 1. Strike reach rate (95 % Wilson interval) for the twelve core pairs, one panel per Strike player, one line per Guard player; the parked
Guard (the baseline) is dashed black. Rows: 1 replica, 2.1 our engine with the partner's rules, 2.2 square walls, 2 our push with hold, 3a identity drone
(equals row 2), 3 drone response. Made by `scripts/make_nus_phase4_figures.py` from `nus/ladder.py`'s outputs. Observed in the training simulator.*

## Reading, rung by rung

- **Rung 1 (T18), replica baseline.** The parked Guard lets every Strike policy through, so the geometry does not close the zone on its own. G19 holds S20
  (9 of 1,000 reach); the Phase 3 pair (P3G, P3S) is dominated by P3S; against the partner's scripted Strike controller P3G holds best. The T16 replay is equal
  game by game.
- **Rung 2 (T19), our engine and rules.** The split fired: five core pairs moved outside rung 1's interval. Row 2.1 (our engine, the partner's rules) matches
  row 1 up to the float32 noise floor of an independent implementation (one step equals one step; game-by-game equality cannot hold, diagnosed in the
  record). Square walls (2.2) already lower P3G against S20; our push with hold (2) moves the rest.
- **Rung 3 (T20), drone response.** An identity drone equals row 2 in every game. The commander copy, delay and lag (exploratory model, which answers more
  slowly than the real drone) raise the Strike reach rate for most pairs against the policy Guards and break our scripted `guard_mark_edge` against S20.

## Records

`records/2026-11-18_nus_phase4_w3_reference_gates_record.md`, `..._rung1_record.md`, `..._rung2_record.md`, `..._rung3_record.md`, `..._rung4_record.md`
(ABORTED, with the estimates). Ledger rows T17 to T21. Videos: `runs/nus_port/phase4/row_*/videos/` and `runs/nus_port/videos/w3/` (git-ignored).
