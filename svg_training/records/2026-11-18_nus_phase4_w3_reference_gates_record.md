Simulator: training simulator, tier 1 (replica of the partner's 2-D game, CPU): the self-play archive pair (seed 2, Guard generation 19 = G19, Strike generation 20 = S20) converted to PyTorch against the partner's own JAX policy. Not a flight result.

# 2026-11-18 NUS port, Phase 4 T17: Phase 3's gates on the archive pair (run of record)

| Item | Value |
|---|---|
| Purpose | Finish the archive arm of Phase 3's frozen gate (b), deferred at T16 (plan D2, F13), before the transfer ladder uses G19 and S20. Owner's answer 2 (18 Nov 2026): T17 first |
| Plan | `docs/plans/2026-11-18-nus-phase4-transfer-ladder.md` v2 with the owner's answers |
| Date, machine | 2026-11-18, home RTX 5090 workstation (CPU only for this run; JAX workers in `nus_jax`, CPU) |
| Code | branch `nus-port-phase2` over `afe6b993`, working copy NOT committed (the lead commits); files in HANDOFF section 0. Rows 1, 2, 3a and 3 ran before the jump-row fix of the partner push (it touches rows 2.1 and 2.2 only); rows 2.1 and 2.2 ran after it. |
| Gates | `runs/nus_port/w3/gates.toml` (sha256 `ca2a2e6a07ec9d08`): a verbatim copy of `configs/nus_port.toml` `[gates.phase3_converted_policy]` (sha256 of the file `6bf80e5a31e19553`, unchanged since T16), written before the run, together with the archive-arm pass rule. Nothing moved |
| Checkpoints | archive entries `0019_defender` (Guard) and `0020_attacker` (Strike) of the partner's self-play seed 2 (private): source `actor.msgpack` sha256 `ea318b3f8736be66` and `009a9fdc28fe3dad`; converted actor-only entries `ac3dde1e49cc1ce0` (Guard) and `210165dbd88688cc` (Strike) in `runs/nus_port/weights/` (git-ignored) |
| Partner values | git-ignored `configs/local/nus_rules.toml` (`dd22cc28ce2042f3`, unchanged), `nus_deploy.toml` (`c248c6bef3f6e17b`, T16's, unchanged) and the new `nus_deploy_ref.toml` (`6d71c111959fd9b2`: every key equals T16's file except the two weights folders; `nus_make_local_deploy.py --same-as` checks it) |
| Reference data | `runs/nus_port/w3/reference/` (git-ignored): actions Guard `fe04e023a3e9a510`, Strike `df807e80101677325`, scripted-opponent states `d3aa6b64bed15ce1`, shared starts `386cccde0aa270e4` (the same starts as T16: same partner environment and seed) |
| Seeds | reference export seed 20261118 (as T16); outcome runs: the partner environment's own starts, all actions deterministic |
| Games | 1,000 shared starts per arm; 24,000 observation rows per team |

## Results

| Gate / check | Limit | Guard team (G19) | Strike team (S20) | Result |
|---|---|---|---|---|
| (a) Action parity: max action error per step, converted vs JAX, 24,000 observation rows per team | <= 0.02 units | 0.00792 | 0.00946 | PASS |
| (b) Scripted arm: Strike reach rate against the ported scripted controller of the other team, converted inside the JAX arm's Wilson 95 % interval | inside | JAX 166/1000 = 0.166 [0.144, 0.190]; converted 172/1000 = 0.172 [0.150, 0.197]; 20 games differ | JAX 1000/1000 [0.996, 1.000]; converted 1000/1000; 0 differ | PASS |
| (b) Archive arm: G19 against S20, both teams converted and both teams JAX (two action workers); converted pair's reach rate inside the JAX pair's interval | inside | JAX pair 17/1000 = 0.017 [0.011, 0.027]; converted pair 15/1000 = 0.015 [0.009, 0.025]; **8 games differ** | | PASS |

**Gate result: PASS** (gate (a) both teams; gate (b) both arms; result file `runs/nus_port/w3/w3_result.json` sha256 `d4f772b92501535c`).

Notes: the Strike arm of the scripted comparison is saturated (S20 reaches the zone in every game against the scripted Guards), so it has little power; the Guard arm and the archive arm are the informative ones. The archive-arm pass rule was written in `gates.toml` before the run: the converted pair's rate inside the Wilson 95 % interval of the JAX pair's rate on the same 1,000 starts, all actions deterministic; the record also gives the count of games that differ.

## Videos

Two replica games per arm from the converted policies, positions interpolated to simulator ticks (`runs/nus_port/videos/w3/`, git-ignored): `scripted_arm_G19_game0.mp4`, `scripted_arm_S20_game0.mp4` (the scripted arm: one game per team), `archive_arm_G19_vs_S20_game0.mp4`, `archive_arm_G19_vs_S20_game1.mp4`.

## What was built for T17

`scripts/nus_phase4_w3.py` (gates file, both gates, videos); `scripts/nus_jax_common.py` now loads archive entries (`actor.msgpack`) as well as runner checkpoints; `scripts/nus_export_reference.py --out-dir` (under `runs/` only, so T16's files are untouched); `scripts/nus_make_local_deploy.py --same-as` and `--out` restricted to `configs/local/`; `nus/outcome.py:play_pair`; `nus/players.py` (the reference binding `RefGuard`, `RefStrike`).

## Limits

- Parity with the partner's 2-D game and policy only; nothing here says how G19 and S20 behave with Starling lag, delay, our safety filter, 3-D or Isaac Lab drones (the ladder rows).
- One pair (seed 2 generations 19 and 20), one reference observation set, one set of starts.

## Ledger

Row `T17` in `records/LEDGER.md` (run on the home RTX 5090 as a workstation row and renumbered at the merge into `main`).

Watch the clips: [Copy of NUS 2-D game videos](../docs/media/nus/README.md#copy-of-nus-2-d-game).
