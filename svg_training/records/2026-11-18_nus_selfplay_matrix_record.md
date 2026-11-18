Simulator: NUS's own 2-D game (JAX, GPU), hangar geometry, NUS's own evaluator. Not a flight result.

# 2026-11-18 NUS port: self-play cross-play matrix, hangar geometry (INFO, after the fact)

**INFO record, written 18 November 2026 from the outputs listed below; no ledger number at the time of the runs.**

| Item | Value |
|---|---|
| Purpose | Who beats whom among the self-play policies of the Phase 2a record, and the go/no-go criteria set before the self-play runs (a: the learner works; b: the final policies' cross-play mean in 0.2–0.8) |
| Criteria, set before the runs | (a) no team's learner fails in 2 or more consecutive generations up to generation 6 (fail: the archived best's win rate ≤ 0.5 against any pool opponent, APF included); (b) mean Strike win of the final policies' cross-play (generation 7 Guards × generation 8 Strikes, 9 pairs) inside 0.2–0.8. Approved by the owner before the runs |
| Date, machine | 2026-11-18, 02:08 (8 generations) and 03:53 (seed 2 to 20) (+08:00); the lab's RTX 5090 workstation |
| Method | NUS's evaluator (`ma_skills.jax.ensemble_evaluation.evaluate_pool` on a `FixedOpponentRunner`), no game loop of ours; Guard side active, pool = the archived Strike policies plus the APF slot; deterministic actions on both sides; 256 games per pair; evaluation seed 20261118. Cross-checked from the Strike side |
| Loading check | NUS's own archive evaluation of seed 1 generation 7 re-run with NUS's seed formula: 198/200/199/193 wins, equal to its `metadata.json` |
| Code | probe scripts (`matrix.py`, `summarize.py`, `matrix20.py`, `summarize20.py`) in the lab's private port folder, outside every git repository |
| Outputs | beside the scripts (not in git): `matrix_raw.json` (sha256 prefix `71ac0dbf41d26afb`), `results.json` (`e265dc9dbe0f3801`), `matrix20_raw.json` (`e23ff1f60a39db90`), `results_seed2_20gens.json` (`a7fba9c177e19c96`); videos in `videos/` |
| Figure | `docs/figures/nus_selfplay_matrix.png`, made by `scripts/make_nus_selfplay_figures.py` from `matrix20_raw.json` (NUS_PORT Figure 1) |

## Results after 8 generations (observed in the training simulator)

| Criterion | Value | Verdict |
|---|---|---|
| (a) longest run of consecutive failed same-team generations, generations 1–6 | 1 (seed 1, Strike generation 4) | PASS |
| (b) final cross-play mean Strike win, 9 pairs | 0.668 (same seed 0.669, other seeds 0.667; Strike-side check 0.668) | PASS |

No single final pair is balanced: every cell of (b) is 0.008 or less, or 0.988 or more. Within a seed the later
generation mostly beats every earlier one. Every Strike policy beats NUS's APF Guard in every game; every Guard policy
holds the APF Strike to 0.016–0.078. Strike-side and Guard-side matrices differ by up to 0.094 (NUS's evaluator draws
different starts per opponent).

## Seed 2 continued to 20 generations

| Measure | Value |
|---|---|
| Last-mover cycle | generations 1–12; from generation 13 it stops in the Guard team's favour |
| Guards 13–19 against every earlier Strike policy | worst Strike win 0.06 |
| Guards 17–19 against every later Strike policy | 0.02 or less |
| Strike learners 16, 18, 20 against every earlier Guard | worst 0.34, 0.00, 0.00 |
| Near-shutout cells (≤ 0.05 or ≥ 0.95) | 0.95 of the 20-generation sub-matrix |
| G19 against the 8 Strike policies of seeds 1 and 3 | mean Strike win 0.042 (worst 0.13) |
| S20 against the 8 Guard policies of seeds 1 and 3 | mean Strike win 0.726 (seed 3 generation 5 holds it to 0.06) |
| G19 against S20 | Strike win 0.023 |
| G19 against NUS's APF Strike; S20 against NUS's APF Guard | 0.168; 1.00 |
| Criterion (b) with the newest finals (5 distinct pairs) | 0.333 (Strike side 0.327): PASS |

## Verdict

INFO. Criteria (a) and (b) both PASS after 8 generations; (b) PASS again with the newest finals.

## Limits

- 256 games per pair (our standard for a result is 1,000), one evaluation seed.
- One seed went to 20 generations; 8 generations per seed against NUS's default of 32.
- Re-running the 8-generation cells inside the 20-generation pool gave differences up to 0.047 (25 of 144 cells, 1–12
  games of 256); cause not tested.
- Under (a)'s definition, Strike generations 16, 18 and 20 of seed 2 fail three times in a row; (a)'s window ends at
  generation 6, so this is information only.

## Ledger

Row `T38` in `records/LEDGER.md` (INFO, after the fact).
