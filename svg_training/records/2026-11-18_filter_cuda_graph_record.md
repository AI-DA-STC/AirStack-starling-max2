Simulator: training simulator, tier 1 (the hangar game of Phase 4 row 5: the all-pairs safety filter, the commander copy, the EXPLORATORY fitted drone model). Not a flight result.

# 2026-11-18 filter_cuda_graph record (INFO, no ledger number yet; CUDA equivalence gate: FAIL)

**INFO record. The CUDA equivalence gate FAILS as written; the hangar-state part of it passes.** The safety filter gets an opt-in
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
| 200 recorded hangar states, 1,000 games (random + ParkedGuard v S20, ticks 0, 2, …, 198) | CUDA | **1.49e-8** | — | equal | **PASS** |

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
change, uncommitted); OFF and the first ON point back to back, the final ON points about 7 minutes later with the same jobs on the GPU.

| Games | OFF s/tick | ON s/tick | Speed-up | OFF game-steps/s | ON game-steps/s | Filter share OFF / ON | Peak reserved OFF / ON |
|---|---|---|---|---|---|---|---|
| 1,000 | 2.100 | 0.947 | **2.22×** | 476 | 1,056 | 0.985 / 0.967 | 70 / 118 MB |
| 16,384 | 2.458 | 1.286 | **1.91×** | 6,666 | 12,741 | 0.959 / 0.923 | 862 / 956 MB |
| 32,768 | not run | not run | — | — | — | — | — |

- First ON attempt (host read every block, as the existing path): 2.02 s/tick at 1,000 games, no gain. On a shared GPU each host
  sync or device-to-host copy costs about one turn of the GPU's time-slicing, so 125 of them per call cost what the launches saved.
  Filter-call scan, five recorded states at 1,000 games: existing 2.03 s, graphs with a read every 8 sweeps 1.92, every 64 1.03,
  every 256 0.87, no read 0.85 s per call. 128 was chosen (PROPOSED).
- Not measured: an idle GPU (the speed-up there is unknown; P0's profile suggests more, since the existing path was launch-bound
  at 0.31 s/tick); 32,768 and 49,152 games; `compact=True` in the game.

## End-to-end game check (64 Phase 4 paired starts, ParkedGuard v S20, row 5, ON vs OFF): not run

Not run: the GPU-hour cap was reached first (0.464 of 0.5 GPU-h). The script is ready (`scripts/filter_graph_check.py endtoend`;
`--max-steps 10` for a cost estimate first). Expected from finding 2: ON matches OFF's fixed loop, not OFF's early stop, so some of the
games with unconverged groups may end differently; the report to make is the number of the 64 games whose outcome differs.

## Tests

- `tests/test_safety_filter_graph.py`, CPU: 22 passed, 10 skipped (CUDA). On the GPU: the CUDA tests pass except
  `test_t2_scenes_t8_setting_cuda` (the gate FAIL above, kept unchanged); `test_recorded_hangar_states_cuda` passed (before the cadence change).
- Filter, speed, privacy and probe tests (CPU): 100 passed, 15 skipped. Full CPU suite (`CUDA_VISIBLE_DEVICES=""`): **946 passed, 44
  skipped**. `tests/test_safety_filter.py -k cuda` on the GPU (existing path with the new `converged` field, no host sync): 3 passed.

## GPU hours

`runs/nus_port/filter_graph/gpu_hours.log` (5090 only): **0.464 h** of the 0.5 h cap (wall clock holding the GPU, shared). Largest
items: the recorded-state gate test 0.128 h, recording the states 0.092 h.

## Limits

- One seed, 20 timed ticks per point, a GPU shared with four other jobs whose load changes; read the speed-up as indicative.
- The gate's reference (the early stop on CUDA) is not reproducible across batch shapes; any decision to accept the ON path rests on
  "equal to the fixed loop, bit for bit", which is a different claim from the one the gate was written for. That call is the lead's.
- Files on the 5090 only: `runs/nus_port/filter_graph/` (states, probe outputs, `equiv.json`, logs).
