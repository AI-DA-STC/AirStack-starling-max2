# NUS port, Phase 4: the transfer ladder (results so far: rungs 1 to 3 of 6)

Observed in the training simulator (the replica of the partner's 2-D game, then our game with point drones and with the exploratory fitted drone
model). Nothing is flown. The partner's converted policies stay frozen; each row changes one behaviour (rung 2 changes two, owner answer 3). INFO runs
without gates; W3 (the archive pair through Phase 3's gates) PASSED. Every number is a Strike reach rate with its Wilson 95 % interval from 1,000 paired
games per pair on one starts file and one seed: no method claim. Values that equal a partner or hangar value are not written here.

**Not run:** rungs 4 (all-pairs safety filter), 5 (3-D at one height, 1 mm jitter) and 6 (the physics drone in Isaac Lab). Each was estimated above the 2 h
limit (about 5 h for rungs 4 and 5, about 4.4 h for rung 6); see `records/2026-11-18_nus_phase4_rung4_record.md`. The ladder stops here until the owner
or the lead chooses how to run them.

![Strike reach rate by ladder row](figures/nus_phase4_ladder.png)

*Figure 1. Strike reach rate (95 % Wilson interval) for the twelve core pairs, one panel per Strike player, one line per Guard player; the parked
Guard (the baseline) is dashed black. Rows: 1 replica, 2.1 our engine with the partner's rules, 2.2 square walls, 2 our push with hold, 3a identity drone
(equals row 2), 3 drone response. Made by `scripts/make_nus_phase4_figures.py` from `nus/ladder.py`'s outputs. Observed in the training simulator.*

## Reading, rung by rung

- **Rung 1 (W4), replica baseline.** The parked Guard lets every Strike policy through, so the geometry does not close the zone on its own. G19 holds S20
  (9 of 1,000 reach); the Phase 3 pair (P3G, P3S) is dominated by P3S; against the partner's scripted Strike controller P3G holds best. The W2 replay is equal
  game by game.
- **Rung 2 (W5), our engine and rules.** The split fired: five core pairs moved outside rung 1's interval. Row 2.1 (our engine, the partner's rules) matches
  row 1 up to the float32 noise floor of an independent implementation (one step equals one step; game-by-game equality cannot hold, diagnosed in the
  record). Square walls (2.2) already lower P3G against S20; our push with hold (2) moves the rest.
- **Rung 3 (W6), drone response.** An identity drone equals row 2 in every game. The commander copy, delay and lag (exploratory model, which answers more
  slowly than the real drone) raise the Strike reach rate for most pairs against the policy Guards and break our scripted `guard_mark_edge` against S20.

## Records

`records/2026-11-18_nus_phase4_w3_reference_gates_record.md`, `..._rung1_record.md`, `..._rung2_record.md`, `..._rung3_record.md`, `..._rung4_record.md`
(ABORTED, with the estimates). Ledger rows W3 to W7. Videos: `runs/nus_port/phase4/row_*/videos/` and `runs/nus_port/videos/w3/` (git-ignored).
