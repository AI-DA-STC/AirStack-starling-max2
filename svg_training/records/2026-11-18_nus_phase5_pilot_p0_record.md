Simulator: training simulator, tier 1 (the hangar game of Phase 4 row 5: the all-pairs safety filter, the commander copy, delay and lag of the EXPLORATORY fitted drone model, drones free in height with the start-height jitter). Not a flight result.

# 2026-11-18 NUS port, Phase 5 pilot P0 (W11): throughput probe of the hangar game (pilot, not gated, INFO record)

**Pilot, not gated, INFO record.** P0 measures how the time per simulator tick grows with the number of games, so that the
pilots and stage 5.2 can be sized (plan `docs/plans/2026-11-18-nus-phase5-retraining.md` section 7, row P0; fact F17).
Nothing here is a training result, and no gate applies.

| Item | Value |
|---|---|
| Purpose | Seconds per tick (primary), game-steps/s, drone-steps/s, peak GPU memory and the share of time in the safety filter at 1,000 / 4,096 / 16,384 / 32,768 games; the pilots' game count by the plan's rule; and (gatekeeper, 18 Nov 2026) one 49,152-game point for the rule "three seeds side by side only if s/tick at 49,152 ≤ 1.5 × the 16,384 value" |
| Plan | `docs/plans/2026-11-18-nus-phase5-retraining.md` section 7 (P0) and section 9 (Task P-T1). INFO run: `runs/nus_port/phase5/p0/gates.toml` holds `gates = []`, written before the run |
| Date, machine | 2026-11-18; main run 15:53:51 to 16:12:01, 49,152-game point 16:14:06 to 16:16:52 (+08:00); home RTX 5090 workstation (NVIDIA GeForce RTX 5090, torch 2.7.0+cu128, Python 3.11.18); GPU otherwise idle (only the remote-desktop daemon, 585 MiB, and a 27 MiB desktop program; `scripts/isaac_preflight.sh --approved-headless` exit 0) |
| Code | branch `nus-phase5` at commit `e595bfd3` plus the then-untracked `scripts/nus_phase5_probe.py` (Task P-T1) and `configs/nus_phase5.toml` (its `[probe]` table; sha256 prefix at run time `f1c9e9cb92a41320`, since extended); the lead commits. The 49,152 point ran through the probe's `--extend` mode (same ticks, seed and device; earlier entries kept) |
| Config and local files | Phase 4 row 5 (`configs/nus_phase4.toml`, sha256 prefix `64ae48cf4f51be37`), `configs/nus_hangar_game.toml` (`3f771112bd3f0370`; filter 1,000 sweeps, early-stop check every 8), the Starling parameter file `params/real_exploratory_v0.toml` (EXPLORATORY drone model, T5 = FAIL), git-ignored `configs/local/` files (5090 only; no value is written here): rules `dd22cc28ce2042f3`, deploy_w2 `c248c6bef3f6e17b`, deploy_ref `6d71c111959fd9b2`, hangar `b7f2870ee17d2d70` |
| Players | arm `parked_s20`: ParkedGuard (Guard 0 at the zone centre, all Guards command zero) against S20 (the converted archive Strike policy, seed 2 generation 20); arm `random`: both teams uniform random actions in [−1, 1] on every axis, every tick |
| Starts | drawn in memory for each count with the Phase 4 starts rule (`NusReplica.reset(random_start=True)` plus the ±1 mm start-height jitter), seed 20261120 (PROPOSED); the Phase 4 starts file was not used. Games that end restart from their own start (`NusHangarGame`) |
| Timing | 50 untimed warm-up ticks, then 400 timed ticks per arm and count, `torch.cuda.synchronize` before and after; each tick: act once per team, step, reset the strategies of the games that ended (as `core/play.play_match`). Share in the filter: the command chain's filter call wrapped with `synchronize` + `perf_counter` on both sides during the same timed ticks (the filter syncs at its first sweep anyway) |
| Allocator | the 5090 shell's `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True,max_split_size_mb:128` (exported in `~/.bashrc`; found after the run, see the memory section) |
| Seeds | one seed: a throughput probe, no method claim (STANDARDS section 6.5) |
| Videos | none: a throughput probe plays no scored game and trains nothing (STANDARDS section 8 applies to training runs) |

## Results

Throughput: game-steps per second (ticks × games), with games, 6 drones per game, tier 1, NVIDIA GeForce RTX 5090.
"Ratio" is the seconds per tick divided by the same arm's 1,000-game value.

| Arm | Games | Seconds per tick | Ratio | Game-steps/s | Drone-steps/s | Share of time in the filter | Peak GPU memory allocated | Peak GPU memory reserved |
|---|---|---|---|---|---|---|---|---|
| ParkedGuard v S20 | 1,000 | 0.3141 | 1.00 | 3,184 | 19,105 | 0.989 | 53 MB | 73 MB |
| ParkedGuard v S20 | 4,096 | 0.4116 | 1.31 | 9,951 | 59,706 | 0.988 | 185 MB | 258 MB |
| ParkedGuard v S20 | 16,384 | 0.4274 | 1.36 | 38,330 | 229,980 | 0.970 | 706 MB | 23.5 GB |
| ParkedGuard v S20 | 32,768 | 0.4327 | 1.38 | 75,734 | 454,406 | 0.942 | 1.40 GB | 31.0 GB |
| ParkedGuard v S20 | 49,152 | 0.3609 | 1.15 | 136,184 | 817,103 | 0.892 | 2.10 GB | 31.1 GB |
| random (INFO) | 1,000 | 0.0630 | 1.00 | 15,877 | 95,260 | 0.950 | 25 MB | 50 MB |
| random (INFO) | 4,096 | 0.1609 | 2.55 | 25,463 | 152,780 | 0.980 | 74 MB | 109 MB |
| random (INFO) | 16,384 | 0.1936 | 3.07 | 84,639 | 507,833 | 0.983 | 272 MB | 22.8 GB |
| random (INFO) | 32,768 | 0.2696 | 4.28 | 121,558 | 729,349 | 0.983 | 535 MB | 31.1 GB |

No count ran out of memory; no count was shortened by the probe's own deadline. The 1,000-game ParkedGuard v S20 value
agrees with Phase 4 row 4 (T22, 3,084 game-steps/s over whole games).

- **The tick cost hardly grows with the game count** in the ParkedGuard v S20 arm: 32.8 times the games cost 1.38 times
  the time per tick (1,000 to 32,768). Throughput therefore grows nearly in proportion to the game count.
- **49,152 measured below 32,768** (0.3609 against 0.4327 s per tick). Each count draws its own starts, and the filter's
  work per tick depends on the scene (its share falls to 0.892); read the values above 4,096 games as flat at
  0.36–0.43 s per tick, not as a speed-up.
- **The random arm is cheap at 1,000 games** because the filter's early stop ends its sweeps once the random drones
  spread apart: each count's 50 warm-up ticks (crowded starts) cost about 0.41 s per tick at every count, then the
  timed ticks fall. Its ratios therefore overstate the growth with games.

### Side-by-side rule (gatekeeper, 18 Nov 2026)

| Arm | s/tick at 49,152 | s/tick at 16,384 | Ratio | Limit | Result |
|---|---|---|---|---|---|
| ParkedGuard v S20 | 0.3609 | 0.4274 | 0.84 | 1.5 (at most 0.641 s) | **passes**: three seeds may run side by side (plan section 8) |
| random | not measured | 0.1936 | — | — | not applicable (INFO arm) |

One 49,152-game process only approximates three 16,384-game processes (plan section 8); see the memory note below.

### Pilots' game count: 32,768

Rule (plan section 7, P0): the largest count whose seconds per tick is at most 1.5 × the 1,000-game value, at most
32,768. **Decision (lead, 18 Nov 2026):** the count is set by the ParkedGuard v S20 arm only, the arm closest to pilot P1
(a Guard learner against S20) and the one with the filter fully loaded; the random arm is INFO, because its 1,000-game
base is artificially cheap (the early stop above), so under the rule it would allow only 1,000 games although every
random-arm tick costs less than any ParkedGuard v S20 tick. ParkedGuard v S20 at 32,768: ratio 1.38 ≤ 1.5, so
**32,768** (the rule's maximum). The probe's `pilot` block records the rule per arm, the arm used and this decision.

### Memory: reserved memory grows far beyond what is allocated (and the fix)

From 16,384 games up, the peak memory **reserved** by PyTorch's caching allocator reached 23–31 GB of the 32 GB card, while
the memory **allocated** stayed at 0.7–2.1 GB. The run used the shell's allocator setting
`expandable_segments:True,max_split_size_mb:128` (`~/.bashrc` on the 5090, found after the run). A memory smoke the same
afternoon (16:39–16:41, `runs/nus_port/phase5/p0_alloc_smoke/`, 5090 only) re-ran the ParkedGuard v S20 arm at 16,384 and
32,768 games with `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` alone (50 warm-up ticks, 100 timed ticks):

| Games | Allocator setting | Seconds per tick | Peak allocated | Peak reserved |
|---|---|---|---|---|
| 16,384 | shell's (P0, 400 timed ticks) | 0.4274 | 706 MB | 23.5 GB |
| 16,384 | `expandable_segments:True` (100 timed ticks) | 0.3298 | 706 MB | 0.92 GB |
| 32,768 | shell's (P0, 400 timed ticks) | 0.4327 | 1.40 GB | 31.0 GB |
| 32,768 | `expandable_segments:True` (100 timed ticks) | 0.3422 | 1.40 GB | 1.88 GB |

The reserve then stays near what is allocated. The faster ticks are indicative only (100 timed ticks against 400, a
different window of the game); in the pilot process the same change left the time unchanged (two P1 smokes, 32,768 games:
training 23.7 s and 23.7 s, evaluation 66.8 s and 66.3 s; reserved 23.0 GB against 4.36 GB with 4.03 GB allocated in both).
The pilots therefore set `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` themselves (`configs/nus_phase5.toml [pilots]
alloc_conf`, replacing the shell's value). P0's seconds per tick above were measured with the shell's setting.

### Where the filter's time goes (INFO, one profiled tick)

One tick of ParkedGuard v S20 at 1,000 games, after the warm-up, under `torch.profiler` (CPU and CUDA activity); counts
from `runs/nus_port/phase5/p0/probe.json` key `profile` (5090 only), the operator table in `profile.txt`.

| Quantity | Value |
|---|---|
| Filter calls per tick | 1 |
| Sweeps (one `aten::einsum` per sweep; Python loop iterations) | **1,000**, the whole budget: the early stop never fires, because some game always has an unconverged group |
| Early-stop checks (`aten::nonzero`, one host sync each) | 125 (every 8 sweeps) |
| Host sync or copy calls (filter / whole tick) | 377 / 396 |
| CUDA kernel launches (filter / whole tick) | 81,813 / 82,566 (about 82 per sweep) |
| GPU kernel time in the filter (under the profiler) | 0.099 s of a 0.566 s filter call: the GPU is busy about 17–19 % of the time |

The filter's cost is kernel launches and Python overhead, not GPU arithmetic; that is why the tick cost barely grows with
the game count. Possible speed-ups (none tried; the filter was not changed): fewer sweeps (time roughly in proportion;
accuracy to be checked against T8's table), or CUDA-graph capture of the 8-sweep blocks between checks (it needs a
fixed-shape variant of the early-stop re-gather, which would also remove the reserved-memory growth).

### GPU hours

From `runs/nus_port/phase5/pilots/gpu_hours.log` (5090 only): CUDA checks of the probe 0.019 h (15:52:40 to 15:53:50),
the main run 0.303 h, the 49,152-game point 0.046 h, the memory smoke 0.029 h; **0.397 h in all**, under P0's cap of 0.5
GPU-hours.

## Limits

- One seed; one draw of starts per count; 400 ticks per point (about a sixth of one 2,400-tick game), taken after 50
  warm-up ticks from fresh starts: the mid-game and end-game cost of a tick is not measured. A whole Phase 4 row 4 game
  ran at about the same rate (T22).
- Tier 1 only, with the EXPLORATORY drone model (T5 = FAIL); tier 2 (Isaac Lab) is not measured here.
- No learner in the loop: a pilot's update adds the PPO step and the policy's own forward pass (not measured).
- 49,152 games in one process is not the same as three 16,384-game processes (separate allocators, Python threads and
  kernel queues).
- The probe ran under the shell's allocator setting (see the memory section); the pilots use another one.
- The share of time in the filter uses synchronized timers; the filter syncs at its first sweep anyway, so the extra cost
  is small, but the share is an upper bound.

## Output

`runs/nus_port/phase5/p0/` (5090 only, git-ignored): `gates.toml`, `probe.json` (per arm and count, the pilot block, the
side-by-side block, the profile, `meta` with the sha256 of every file read), `probe.log`, `probe_extend.log`,
`profile.txt`, `preflight.txt`, `gpu_before.txt`. Ledger row T25 (run on the home RTX 5090 as workstation row W11 and renumbered at the merge into `main`).
