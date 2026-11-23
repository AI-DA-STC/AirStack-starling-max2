Simulator: training simulator — replica of the partner's 2-D game (Phase 2, T15); the converted PyTorch policy against the partner's own JAX policy, CPU. Not a flight result.

# NUS port, Phase 3: the partner's policy, converted to PyTorch (run of record)

| Item | Value |
|---|---|
| Purpose | Run a policy trained by the partner's JAX code inside `svg_training` without the partner's code: same actions, and the same game outcomes observed in the training simulator. Shows that the actor converts and that our wrapper feeds it the observation it expects; says nothing about Starling-like drones (Phase 4) |
| Plan | `docs/archive/2026-11-18-nus-phase3-converted-policy.md` (v2, after the gatekeeper read; owner approved the `msgpack` dependency and layout id `nus_area_denial_v1`) |
| Date, machine | 2026-11-18T00:30:00+08:00, home RTX 5090 workstation (CPU only; the GPU was running other jobs). Pipeline env `env_isaaclab`; partner env `nus_jax` |
| Code | branch `nus-port-phase2` on `f3ea6ac1` plus this phase's files, committed with this record |
| Partner code | NUS `area-denial-continuous-space-self-play` @ `2d2b904` (private clone on the 5090) |
| Gates | `configs/nus_port.toml` `[gates.phase3_converted_policy]`, written and approved before the run (17 Nov 2026), unchanged; the pass rule for gate (b) was coded before any number was seen |
| Checkpoints converted | hangar-geometry fixed-opponent runs (private): Guard team `state.msgpack` sha256 `cd16bca68e9abbfe…`, Strike team `938b6e6c1f126a0f…`; converted actor-only entries `actor.msgpack` `c5d310ffbe4853e7…` (Guard), `0eeb938f0dea13f7…` (Strike), in `runs/nus_port/weights/` (git-ignored) |
| Partner values | git-ignored `configs/local/nus_rules.toml` (sha256 `dd22cc28ce2042f3…`, unchanged since T15) and `configs/local/nus_deploy.toml` (`c248c6be…`: hangar overrides, scale, hold length, flying height, and partner-code constants read from the partner source); no partner value is written here |
| Reference data | `runs/nus_port/reference/` (git-ignored): actions Guard `280a90a81dc8abe7…`, Strike `6d231234e357f333…`; scripted-opponent states `26c3fdc030a25b63…`; shared starts `386cccde0aa270e4…` |
| Seeds | outcome parity: the partner environment's own starts, seed 20261118; reference rollouts as recorded in the reference files |
| Games | 1,000 shared starts per team; 24,000 observation rows per team; 16,000 states for the scripted-opponent port |
| Compute dtype | the partner's actor runs its trunk in bfloat16; the converted actor copies the partner's bfloat16 cast points (per-operation rounding for the Mish activation, chosen by measurement). A plain float32 forward would miss gate (a) (max error 0.022 Guard, 0.030 Strike) |

## Results

| Gate / check | Limit | Guard team | Strike team | Result |
|---|---|---|---|---|
| (a) Action parity: max action error per step, converted vs JAX, 24,000 observation rows (8,000 states, half on-policy, half random) | ≤ 0.02 units | 0.00737 | 0.01045 | PASS |
| (b) Outcome parity: reach rate of the Strike team, 1,000 shared starts against the ported scripted opponent, Wilson 95 % | converted inside the JAX arm's interval | JAX 48/1000 = 0.048 [0.036, 0.063]; converted 46/1000 = 0.046 [0.035, 0.061]; 6 games differ | JAX 1000/1000 = 1.000 [0.996, 1.000]; converted 1000/1000; 0 differ | PASS |
| Wrapper test: rebuilt observation vs `NusReplica.observe` at every sample, action held between samples, a mid-hold reset restarts only that game, reached flag latches | ≤ 1e-4 units | pass | pass | PASS |
| Scripted-opponent port vs the partner's scripted actions, 16,000 states | ≤ 1e-4 units | Guard controller 1.3e-5 | Strike controller 4.2e-7 | PASS |

**Gate result: PASS** (both gates; wrapper and scripted-opponent checks pass).

Notes on the results:
- The Strike arm of gate (b) is saturated (the Strike policy reaches the zone in every game against the scripted
  Guards), so that comparison has little power; the Guard arm is the informative one.
- The ported Guard controller targets the nearest Strike drone. In 241 of the 16,000 states two Strike drones are
  equally near within float32 resolution; the two implementations chose differently in 11 of them. The test caps the
  share of such states at 1 %.

## Full suite

`cd svg_training; unset PYTHONPATH; PYTHONPATH=source ~/miniconda3/envs/env_isaaclab/bin/python -m pytest -q -p no:cacheprovider`
(CPU): **851 passed, 34 skipped, 0 failed** (lead's run, 18 Nov ~00:30).

## Videos

Four replica games rendered from the converted policy through `viz/replay.py`, positions interpolated between policy
steps: `runs/nus_port/videos/guard_game0.mp4`, `guard_game1.mp4`, `strike_game0.mp4`, `strike_game1.mp4`
(git-ignored; partner geometry).

## What was built

Source `source/svg_training/nus/`: `deploy.py` (local deploy-file loader), `apf.py` (both scripted controllers,
batched), `actor.py` (msgpack loader, no JAX/Flax import; torch actor), `strategy.py` (`NusPolicy`, reachable through
`make_strategy("svg_training.nus.strategy:NusPolicy")`), `outcome.py`, `interface.py` (layout `nus_area_denial_v1`).
Scripts `scripts/nus_*.py` for local files, conversion, reference export, the JAX policy server, outcome parity,
interface writing and videos. Templates `configs/nus_deploy.template.toml`, `configs/nus_interface.template.toml`
(keys and `"LOCAL"` only). Tests `tests/test_nus_{phase3_privacy,apf,actor,strategy,outcome,interface}.py`; privacy
rails widened (G2 now also scans `tests/test_nus_*.py`; the record writer refuses any rules, deploy or architecture
value; G4 covers the loader, wrapper and interface writer through a synthetic checkpoint). New dependency
`msgpack` in `pyproject.toml` (owner approval; the container image does not have it yet).

## Limits

- Parity is with the partner's 2-D game and policy. Nothing here says how the policy behaves with Starling lag and
  delay, our safety filter, 3-D, or Isaac Lab drones (Phase 4), or in flight.
- First checkpoints only: short fixed-opponent runs on the hangar geometry, not the self-play archives (running).
- Read from the partner's code, not proven: the checkpoint layout (`ma_skills/runner/fixed_opponent_runner.py:451-455`),
  where the disk-projection floor is applied (`ma_skills/jax/policy.py`), and XLA's CPU bfloat16 fusion (the cast
  points were matched by measurement).
- The wrapper refuses other team sizes and a scale or speed mismatch; a drone removed from the game is not modelled
  (the partner's method needs a fixed team size).
- The partner value scans in `tests/test_partner_privacy.py` skip on the 5090: rerun on the laptop before merging.
  Two generic test tolerances in `tests/_nus_markers.py` happen to coincide with two small partner settings; they
  were chosen independently and are not partner values (the laptop reviewer may rename them to avoid confusion).

## Ledger

Row `T16` in `records/LEDGER.md` (run on the home RTX 5090 as a workstation row and renumbered at the merge into `main`). The owner reads this record before Phase 4.

Watch the clips: [Copy of NUS 2-D game videos](../docs/media/nus/README.md#copy-of-nus-2-d-game).
