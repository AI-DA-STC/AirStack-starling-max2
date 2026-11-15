> 16 November 2026 · S2 final review fix wave · status: the probe behind the wall-limit diagnosis in the [T9 record](../../records/2026-11-16_s2_scripted_reference_2_record.md#limits), committed and run again. Training simulator only, exploratory drone model; not a flight result.

# Why scripted pairs still come 0.75–0.80 m apart next to walls (probe)

After the wall fix, scripted Guard and Strike drones under the Starling layer still came to 0.75–0.80 m in crowded
5 v 3 games (keep-out 1.10 m). The T9 review traced this to two causes that overlap: the safety filter does not know
the walls, and the fitted drone model responds slowly. `scripts/probe_wall_limit.py` is that review's probe, turned
into a committed script.

## What it does

It plays 300 games of `guard_mirror` against `strike_flank`, 5 v 3, lab-size arenas, with the Starling layer on, on
the CPU, using the committed neutral settings (never the partner's local file). The filter runs 1,000 sweeps with a
check every 8, as in T9. Each game slot counts its first game; games that began with a start miss are left out (204
of 300 remain). It reports the closest 3-D Guard–Strike distance per game under these variants:

| Variant | What changes |
|---|---|
| `baseline` | nothing: the committed layer, as T9 ran it |
| `wall_aware` | the filter also knows the walls: a drone held at a wall may not be told to move further out. Built inside the script from `core/safety_filter.py` plus a small patch; the core is unchanged |
| `ideal_model` | the drone does exactly what the commander asks: no lag, no delay, no acceleration limit, no position or feed-forward term |
| `wall_aware_ideal` | both changes |
| `sweeps5000` | the baseline with 5,000 filter sweeps |

For the baseline it also counts, among games under 0.95 m, how often one drone of the closest pair is held at a
wall at the deepest moment, and whether the filter ever hit an emergency.

## Command

From `svg_training/` (22 minutes for all five variants on this laptop's CPU; `--variants baseline` alone takes about 3):

```
PYTHONPATH=source ~/miniconda3/envs/env_isaaclab/bin/python scripts/probe_wall_limit.py \
    --variants baseline,wall_aware,ideal_model,wall_aware_ideal,sweeps5000
```

## Output, 16 November 2026

Closest 3-D Guard–Strike distance over the 204 games without a start miss (m), and the share of games under 0.9 m
and 1.0 m. Run time per variant on 6 CPU threads, with the test suite running alongside.

| Variant | min | 1st pct | 5th pct | median | under 0.9 m | under 1.0 m | time |
|---|---|---|---|---|---|---|---|
| `baseline` | 0.821 | 0.848 | 0.857 | 0.939 | 20.1 % | 93.1 % | 161 s |
| `wall_aware` | 0.909 | 0.916 | 0.962 | 1.028 | 0.0 % | 25.5 % | 263 s |
| `ideal_model` | 0.840 | 0.878 | 0.893 | 0.974 | 6.9 % | 71.1 % | 159 s |
| `wall_aware_ideal` | 1.084 | 1.084 | 1.087 | 1.093 | 0.0 % | 0.0 % | 580 s |
| `sweeps5000` | 0.821 | 0.848 | 0.857 | 0.939 | 20.1 % | 93.1 % | 161 s |

Baseline, games under 0.95 m: 116. In 114 of them (98 %) one drone of the closest pair was held at a wall at the
deepest moment; in 104 (90 %) a third drone was within 1.3 m. No game had a filter emergency; the largest filter
residual was 0.0029. Every number is identical to the review's scratch run of the same morning.

## Reading

The run gives again every number the T9 record quotes. With the committed layer the closest pair came to 0.821 m;
with a wall-aware filter, 0.909 m; with an ideal drone but a wall-blind filter, 0.840 m; with both, 1.084 m; with
5,000 sweeps, the same 0.821 m. In 114 of the
116 deep games (98 %) one drone of the pair was held at a wall, and the filter never hit an emergency. So the deep
approaches come from the walls and the slow model together, not from the filter failing to settle.
