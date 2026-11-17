# NUS port, Phase 3: the partner's policy, converted to PyTorch

**Status: PLAN v2 (17 November 2026, night), after the gatekeeper read of v1 (5 PASS, 8 FAIL; all 8 fixes applied).
Owner: "follow ur recommendation". Both owner approvals given (17 Nov, night): `msgpack` dependency; layout id
`nus_area_denial_v1`.** Phase 2 passed first (ledger W1). The private plan with partner values is
on the 5090 (`~/ma_skills-self-play/PORT_PLAN.md`); this file holds none. Gate numbers: `configs/nus_port.toml`
`[gates.phase3_converted_policy]`, frozen; this plan only specifies how they are measured.

## Goal (status: PROPOSED)

Run a policy trained by the partner's JAX code inside `svg_training` without the partner's code, with the same
actions and, observed in the training simulator (2-D replica), the same game outcomes. Phase 3 shows that the actor
converts and that our wrapper feeds it the observation it expects. It says nothing about Starling-like drones (Phase 4).

## Inputs

- **First checkpoints** (named; sha256 kept in the private notes): the hangar-geometry fixed-opponent runs,
  `…/outputs/hangar/2026-11-17_fixed_apf_3v3_defender/checkpoints/final` (Guard team) and
  `…_attacker/checkpoints/final` (Strike team). Later: hangar self-play `archive/` entries.
- **Formats accepted, nothing else:** a checkpoint folder `{config.json, state.msgpack}`, or an archive entry
  `{actor.msgpack, metadata.json}` plus its run's `config.json`. Anything else is refused.
- **Partner values:** Phase 2's `configs/local/nus_rules*.toml` unchanged (W1's hashes stay valid). New, separate
  git-ignored file `configs/local/nus_deploy.toml` for the hangar overrides, the scale (metres per unit, seconds per
  step) and the hold length, with its own committed template of `"LOCAL"` values and its own G1 loader tests.
- **Converted weights, reference data, any `interface.toml` with values:** `runs/nus_port/{weights,reference}/`
  (git-ignored).

## Tasks (test first; `train-change`; implementer writes, lead reviews)

1. **Privacy first.** Widen the G2 numeric-literal scan to `tests/test_nus_*.py`. Extend `write_record` to refuse any
   value (float or int) found in the rules, the deploy file or the checkpoint's architecture. Extend the G4 marker test
   to the actor loader, the wrapper and the interface writer, using a synthetic checkpoint with marker architecture
   sizes built in `tmp_path` (no partner checkpoint in tests).
2. **Scripted Strike opponent port** `source/svg_training/nus/apf.py`: the partner's APF Strike policy (Strike drones
   steered by attraction to the zone and repulsion from Guards), batched, values from local keys, G2. Its own per-step
   parity test against the partner's scripted actions on recorded states (tolerance as Phase 2's 1e-4 units).
3. **Weight loader** `source/svg_training/nus/actor.py`: read the msgpack with `msgpack` + `numpy` (no JAX/Flax in
   `source/`), rebuild the network from `config.json` (layer sizes, block count, activation, LayerNorm epsilon, output
   layer, log_std, compute dtype), transpose kernels, copy the partner's bfloat16 cast points when the config says
   bfloat16 (record states it), deterministic mean action (tanh, team speed, disk projection).
4. **Reference data** `scripts/nus_export_reference.py` (env `nus_jax`, CPU): new 3 v 3 hangar-geometry observations,
   half on-policy (the checkpoint playing APF opponents in the partner's env) and half random, ≥ 10,000 per team, and
   the partner's JAX actions on them in the checkpoint's own dtype → `runs/nus_port/reference/`.
5. **Action parity test** (gate a): converted vs JAX actions on the reference observations; max error per step.
6. **Wrapper** `source/svg_training/nus/strategy.py`, `svg_training.nus.strategy:NusPolicy` through
   `make_strategy("module:Class")` (`opponents/scripted.py:217-233`, constructor `(team, cfg, num_games, device, seed)`):
   the checkpoint comes from a `runs/nus_port/weights/<name>/` folder named in `configs/local/nus_deploy.toml`
   (no constructor change). Strategies read only the observation (`opponents/scripted.py:1-4`): the wrapper rebuilds
   the partner's observation from our observation fields plus its own memory (positions at the previous policy step,
   sticky reached flag), holds each action for K ticks, scales units per step to m/s. Batched torch only in `act`,
   per-game `reset(games)`, no per-game Python loops (STANDARDS §6). Fixed team sizes; refuses others.
   **Wrapper test:** on matched states, the rebuilt observation equals `NusReplica.observe` within 1e-4 units, across
   hold boundaries and resets.
7. **Outcome parity run** (gate b): both arms in the Phase 2 replica — the JAX policy (via its exported actions path in
   `nus_jax`) and the converted policy — each playing its own team against the ported APF opponent, on the same 1,000
   starts (the partner's recorded starts replayed in both), fixed seeds, Strike reach rate with Wilson 95 % intervals,
   gate as configured. (Independent samples of a faithful port miss each other's interval about one time in six;
   shared starts remove most of that noise. The gate is not moved.) The archive opponent waits for the self-play
   entries.
8. **`interface.toml` draft** (layout id `nus_area_denial_v1`): team sizes and k, field order, latch rule, scale keys,
   previous-step sampling, action form, vz = yaw rate = 0, prior weight 0, compute dtype, source commit, checkpoint
   sha256. Values in `runs/nus_port/`; a committed template lists keys only.
9. **Docs:** HANDOFF; correct HOW_IT_WORKS:79 and PLUG_IN (a partner JAX policy now has a scoring hook).

## Records (STANDARDS §8)

One record for the phase, `records/<date>_nus_phase3_conversion_record.md`, simulator named on its first line, with
both gates (a, b) and the wrapper test, the full §8 fields (purpose, commit, config, seeds, machine, games, gates),
the checkpoint, rules, deploy-file and reference-data sha256s, the dtype handling, and a video line (two replica
games per team rendered from the converted policy, or why not). Ledger row W2 (workstation number). Laptop privacy
scans before merge.

## Approvals (owner, 17 November 2026, night: both approved)

1. **New dependency:** `msgpack` (Python) in `pyproject.toml` (and the container image, with its `CHANGES.md` line).
2. **Interface layout id** for the partner policy (STANDARDS §3 rule 3): `nus_area_denial_v1`, plus its HANDOFF entry.

## Stop point

The owner reads the W2 record before Phase 4 (the first Isaac Lab rung also needs the 5090 preflight decision).

## Not in this phase

Starling layer, safety filter, 3-D, Isaac Lab (Phase 4); any ROS 2 node or flight (S5, outside this folder).
