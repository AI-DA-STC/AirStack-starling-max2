Simulator: training simulator, tier 1 (the hangar game of Phase 4 row 5: the all-pairs safety filter, the commander copy, the EXPLORATORY fitted drone model). Not a flight result.

# 2026-11-18 filter_cuda_graph record (INFO, no ledger number yet; CUDA equivalence gate: FAIL)

**INFO record. The CUDA equivalence gate FAILS as written (T2 scenes); its hangar-state part passes (1,000 games).** The safety filter gets an opt-in
fixed-shape path whose sweeps run as CUDA graphs: `[starling_layer] filter_cuda_graph = true` (default false; every existing config,
record and test is unchanged). Observed in the training simulator; nothing here is a flight result.

## Two findings first

1. **On CUDA the existing filter's answer for a game depends on how many other games are still sweeping.** cuBLAS picks the kernel of
   each sweep's `einsum` by the batch size, so a row is rounded differently in a working batch of a different size, and the early stop
   (`check_every = 8`) changes the batch size at every check. On T2's 2,000 scenes at 1,000 sweeps, the existing path with
   `check_every` 0 and 8 differs by up to **2.6e-6 m/s in converged games and 1.65 m/s in unconverged ones** on CUDA (all flags equal).
   T8's "the early stop gave exactly the fixed loop's velocities, 0 m/s" holds on the CPU only (where it was measured).
2. **About 40 % of hangar games never converge in 1,000 sweeps** (ParkedGuard v S20 at 1,000 and 32,768 games, ticks 30–33: the
   working batch falls to 35–43 % of the games by sweep 40 and stays there to sweep 1,000). In those games a one-ulp difference grows
   to m/s over the sweeps.

## Purpose

P0 (`records/2026-11-18_nus_phase5_pilot_p0_record.md`) found the filter takes 89–99 % of each tick, launch-bound (about 82 kernels per
sweep, 125 host syncs per tick). Owner: "parallelize as much as possible to speed things up". Lead's brief: a faster, opt-in path that
does not change the filter's results.

## What was built (commit: see git log of branch `filter-cuda-graph`)

- `source/svg_training/core/safety_filter_graph.py`: `filter_velocities_graph`, same signature as `filter_velocities` plus `block`,
  `use_graph`, `compact`. Converged groups stay in the batch (they are frozen by the sweep itself); blocks of 8 sweeps are captured once
  per batch size as CUDA graphs and replayed. Early stop: the live count is copied to pinned memory once every 128 sweeps
  (`READ_EVERY_SWEEPS`, PROPOSED) and read one read late (`LAG_BLOCKS` 1, PROPOSED). `compact=True` (kwargs only, not in any config)
  adds a capacity ladder (N, N/2, N/4, … when the live games fit); it was not timed in the game. CPU: the same blocks run eagerly.
- `core/safety_filter.py`: `FilterResult.converged` [N] bool (every group met the stopping test, or no active pair); velocities and
  every other output unchanged (`tests/test_safety_filter.py` passes unchanged).
- `core/game_config.py` `StarlingLayerCfg.filter_cuda_graph` (default False); `core/starling_layer.filter_fn(cfg)`;
  `models/fitted.FittedResponse(filter_fn=)`; `core/physics_layer.py` passes it too.
- `scripts/nus_phase5_probe.py --filter-cuda-graph`; `scripts/filter_graph_check.py` (`record`, `equiv`, `calls`, `endtoend`).
- `tests/test_safety_filter_graph.py`: the gate (written before any measurement) and the tests added after the T2 CUDA result.

## Equivalence (gate fixed before measuring: velocities within 1e-6 m/s max abs, float32; converged, emergency, corrected flags equal; reference = existing path, same `check_every`, same device)

| Case | Device | Max abs difference (m/s) | Converged games / unconverged games | Flags | Gate |
|---|---|---|---|---|---|
| T2's 2,000 scenes, T8 setting (1,000 sweeps, check_every 8) | CPU | **0** (bit-identical) | 0 / 0 | equal | PASS |
| same | CUDA | **1.65** (94 of 2,000 games differ) | 2.56e-6 / 1.65 (228 unconverged) | equal | **FAIL** |
| reference's own spread on CUDA: existing check_every 0 vs 8 | CUDA | 1.65 (94 games) | 2.56e-6 / 1.65 | equal | (not a gate) |
| graph path vs existing **fixed loop** (check_every 0) | CPU and CUDA | **0** (bit-identical, all five outputs) | — | equal | (added after, labelled) |
| hand-made / early-stop cases (dropouts, no-pair games, coincident pair, NaN, float64, per-drone cap, blocks 1/3/8/32) | CPU | ≤ 1e-6 | — | equal | PASS |
| 200 recorded hangar states, 1,000 games (random + ParkedGuard v S20, ticks 0, 2, …, 198) | CUDA | **1.49e-8** (not bit-identical) | — | equal | **PASS, at 1,000 games only** |

- The hangar-state PASS holds for those states at 1,000 games. The rounding depends on the batch size, so nothing here shows it holds at
  16,384 or 32,768 games (not measured).
- The CUDA FAIL is the reference's own spread, exactly: the graph path (default) **is** the existing fixed loop bit for bit, so its
  distance from the early-stop path is the early stop's distance from its own fixed loop. No fixed-shape path can reproduce the early
  stop's CUDA bits (they depend on the batch-size trajectory). The tolerance was not changed.
- The recorded-state run used the code with a host read every block; the read cadence was changed afterwards. The cadence does not
  change the default path's answer (frozen sweeps are no-ops; `test_bit_identical_to_fixed_loop_cuda[8]` re-run after the change:
  passed), so the 1.49e-8 stands, but that test was not re-run on the final code (GPU-hour cap).
- With the flag ON, a game run on CUDA therefore matches the **fixed loop** (`check_every = 0`), not the `check_every = 8` early stop that
  `configs/nus_hangar_game.toml` uses; the two already differ by the amounts above.

## Speed (parked_s20 arm of the P0 probe, row 5, 6 drones per game, tier 1, NVIDIA GeForce RTX 5090)

**Taken with other jobs running on the GPU** (three NUS self-play jobs, a pilot P1b training run, GPU utilisation 92–98 % before any of
our runs; `scripts/isaac_preflight.sh --approved-headless --allow-siblings` exit 0). The same tick cost P0 measured as 0.31 s on an idle
GPU was 2.10 s here. 5 warm-up + 20 timed ticks per point (cut from 50 + 100 to stay under the 0.5 GPU-hour cap),
`PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`, seed 20261120. OFF and ON ran from the same working tree (commit `e8dc4f65` plus this
change, uncommitted). OFF and the first ON point (host read every block, since replaced) ran back to back; the final ON points are
single 20-tick runs 7–8 minutes after their OFF points, not back to back, with the same jobs on the GPU. A last OFF/ON pair at 1,000
games was run back to back on the committed code (row marked below).

| Games | OFF s/tick | ON s/tick | Speed-up | OFF game-steps/s | ON game-steps/s | Filter share OFF / ON | Peak reserved OFF / ON |
|---|---|---|---|---|---|---|---|
| 1,000 | 2.100 | 0.947 | **2.22×** | 476 | 1,056 | 0.985 / 0.967 | 70 / 118 MB |
| 1,000, back to back (committed code `9cb2ee85`, OFF then ON) | 2.042 | 0.933 | **2.19×** | 490 | 1,072 | 0.985 / 0.966 | — |
| 16,384 | 2.458 | 1.286 | **1.91×** | 6,666 | 12,741 | 0.959 / 0.923 | 862 / 956 MB |
| 32,768 | not run | not run | — | — | — | — | — |

At 32,768 games, from the filter-call bench instead of the game (five recorded parked_s20 states tiled to 32,768 games, one call each):
existing path 2.50 s per call, graphs with no host read 1.68 s (about **1.5×** at best), graphs with a read every 8 sweeps 2.06 s. The
gain falls with the game count (2.22×, 1.91×, about 1.5×): the graph path sweeps the whole batch every sweep, while the existing early
stop sweeps only the 35–43 % of games still live.

- First ON attempt (host read every block, as the existing path): 2.02 s/tick at 1,000 games, no gain. On a shared GPU each host
  sync or device-to-host copy costs about one turn of the GPU's time-slicing, so 125 of them per call cost what the launches saved.
  Filter-call scan, five recorded states at 1,000 games: existing 2.03 s, graphs with a read every 8 sweeps 1.92, every 64 1.03,
  every 256 0.87, no read 0.85 s per call. 128 was chosen (PROPOSED).
- Not measured: an idle GPU, where the speed-up is unknown either way (at 32,768 games P0's idle OFF tick was 0.34–0.43 s, and the
  full-batch path does about 2.5 times the arithmetic of the early stop's shrinking batch, so ON could be no faster there); 32,768 and
  49,152 games in the game; `compact=True` in the game.
- Early-stop floor: with a read every 128 sweeps, read one late, ON cannot stop before 256 full-batch sweeps. Where the existing early
  stop ends in tens of sweeps (P0's random arm late in a game, 0.063 s/tick), ON may be slower. Not measured.

## End-to-end game check (64 Phase 4 paired starts, ParkedGuard v S20, row 5): **on the CPU only**, outcomes identical

`scripts/filter_graph_check.py endtoend --device cpu` (`runs/nus_port/filter_graph/endtoend_cpu.json`, 5090 only): the first 64 games of
`runs/nus_port/phase4/starts.npz`, seed 20261120, played with `nus/ladder.play_game_pair` three times: OFF (existing early stop,
check_every 8; 373 s), OFF with check_every 0 (existing fixed loop; 597 s) and ON (the new path run eagerly, the CPU has no graphs; 613 s),
2,400 ticks each. **0 of 64 games differ in outcome, and every per-game field of the three `MatchResult`s is identical** (outcome
36 Strike / 28 Guard in all three). On the CPU the three filter paths agree (T2 table above), so this checks the masking and the config
wiring through a whole game, not CUDA replay. **The same check on CUDA was not run** (GPU-hour cap): there, finding 1 says ON equals the
fixed loop, not the early stop, and some games with unconverged groups may end differently.

## Tests

- `tests/test_safety_filter_graph.py`, CPU: 22 passed, 10 skipped (CUDA). On the GPU: the CUDA tests pass except
  `test_t2_scenes_t8_setting_cuda` (the gate FAIL above, kept unchanged); `test_recorded_hangar_states_cuda` passed (before the cadence change).
- Filter, speed, privacy and probe tests (CPU): 100 passed, 15 skipped. Re-run on the committed tree, every `tests/test_nus_*.py` plus
  the privacy and filter files: 205 passed, 15 skipped (13 need CUDA, 2 in `test_partner_privacy.py` find no local partner file; no NUS
  test skipped). `test_toml_key_turns_the_switch_on` added after the first commit. Full CPU suite (`CUDA_VISIBLE_DEVICES=""`): **946 passed, 44
  skipped**. `tests/test_safety_filter.py -k cuda` on the GPU (existing path with the new `converged` field, no host sync): 3 passed.

## GPU hours

`runs/nus_port/filter_graph/gpu_hours.log` (5090 only): **0.486 h** of the 0.5 h cap (wall clock holding the GPU, shared). Largest
items: the recorded-state gate test 0.128 h, recording the states 0.092 h.

## Limits

- `test_t2_scenes_t8_setting_cuda` fails on any CUDA machine by design (it is the gate, kept as written).
- HANDOFF (`docs/claude/HANDOFF.md`) was not updated (lead's call).
- One seed, 20 timed ticks per point, a GPU shared with four other jobs whose load changes; read the speed-up as indicative.
- The gate's reference (the early stop on CUDA) is not reproducible across batch shapes; any decision to accept the ON path rests on
  "equal to the fixed loop, bit for bit", which is a different claim from the one the gate was written for. That call is the lead's.
- Files on the 5090 only: `runs/nus_port/filter_graph/` (states, probe outputs, `equiv.json`, logs).
