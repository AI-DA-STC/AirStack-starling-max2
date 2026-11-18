INTERNAL · an investigation note that a record cites; kept as written.

> 17 November 2026 · S2b Task 8 fix round 1 · status: the diagnosis behind the "Why" bullets of the [T13 record](../../records/2026-11-17_s2b_scripted_compare_record.md), committed and run again. Training simulator only, CPU; not a flight result.

# Why scripted Guards stop holding on the physics drone (diagnosis)

In T13 the scripted Guard team held almost no games against the straight Strike on the physics drone, where tier 1
had held most of them. The run's per-game arrays showed Guard and Strike drones passing one over the other on the
physics drone and never on tier 1. This diagnosis asks two things. Does that happen in a small game we can watch
step by step? And is a height difference on its own enough to break the Guard's block?

## What was run

`scripts/diag_vertical_pass.py` (sha256 `72d1c673d55d`) plays 40 games of 2 Guard v 1 Strike in lab-size arenas. It
runs on the CPU with the committed neutral values (never the partner's local file), the Starling layer on, game seed
0 and strategy seeds 101 / 202 as `score.py`. The drone model is either tier 1 (`--backend fitted`) or the physics
drone in the PyTorch reference world (`--backend physics`); Isaac Lab agreed with that world to 0.001 m/s in T11.
`--strike-dz-m` raises every Strike drone's start by that many metres. Each game slot counts its first game.

It prints:
- the hold rate;
- one drone's largest height change from its start, at any step;
- how many Strike wins had a pass: at the closest horizontal Guard–Strike approach, under 0.55 m apart horizontally
  and more than 0.5 m apart in height. This is looser than figure 2 of the record, which asks for at least 0.84 m.

Commands (`svg_training/`, host conda `env_isaaclab` python, `CUDA_VISIBLE_DEVICES=` so nothing touches the GPU),
run on 17 November 2026 from the working tree at commit `c4d722d` plus this fix round's uncommitted files:

```
PYTHONPATH=source python scripts/diag_vertical_pass.py --backend fitted
PYTHONPATH=source python scripts/diag_vertical_pass.py --backend physics
PYTHONPATH=source python scripts/diag_vertical_pass.py --backend fitted --guard guard_field
PYTHONPATH=source python scripts/diag_vertical_pass.py --backend physics --guard guard_field
PYTHONPATH=source python scripts/diag_vertical_pass.py --backend fitted --strike-dz-m 0.001
PYTHONPATH=source python scripts/diag_vertical_pass.py --backend fitted --strike-dz-m 0.01
```

## Results

Every case is 40 games against the straight Strike.

| Drone model | Guard | Strike start | hold | mean end step | one drone's largest height change (m) | Strike wins | with a pass |
|---|---|---|---|---|---|---|---|
| tier 1 | mark edge | as drawn | 97.5 % | 1171 | 0.000000 | 1 | 0 |
| physics | mark edge | as drawn | 0.0 % | 335 | 0.645965 | 40 | 32 |
| tier 1 | field | as drawn | 97.5 % | 1171 | 0.000000 | 1 | 0 |
| physics | field | as drawn | 0.0 % | 333 | 0.691334 | 40 | 32 |
| tier 1 | mark edge | +1 mm | 0.0 % | 293 | 0.627086 | 40 | 25 |
| tier 1 | mark edge | +10 mm | 0.0 % | 223 | 0.623691 | 40 | 32 |

These are the same numbers as the first, uncommitted run of the night (`runs/sdd/s2b/task8/`), which the record
first quoted.

## What it shows

- **On tier 1 no drone ever leaves its start height.** The scripted strategies never command up or down, and with
  every drone at exactly 1.20 m the safety filter can only push sideways. The Guards hold 97.5 %.
- **On the physics drone drones climb and drop by up to 0.65–0.69 m and the Strike drone passes over or under.** The
  Guards hold 0 %, and 32 of the 40 Strike wins show a pass.
- **A 1 mm height difference is enough on tier 1 too.** With every Strike drone started 1 mm higher, tier 1's Guards
  also hold 0 %, with a slow drone model and no physics. So exactly equal heights are what made tier 1's Guards
  hold. The physics drone's real dynamics never keep heights exactly equal.

## Limits

- One size (2v1), one band (lab), one Strike behaviour (straight), 40 games.
- The offset test writes the game's positions and restarts the Starling layer's state through private fields
  (`game.pos_m`, `game._starling.reset`): a diagnosis, not an interface.
- The test does not measure how much the speed difference between the two drone models (T11) adds in other cells.
