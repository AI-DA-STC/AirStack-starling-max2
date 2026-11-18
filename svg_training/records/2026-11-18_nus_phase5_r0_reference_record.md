Simulator: training simulator, the replica of NUS's 2-D game (hangar geometry: spawn distance 8.0, Guard boundary 8.0; no safety filter), scored on the home RTX 5090; conversions and gate (a) on the CPU. Nothing here is a flight result.

# 2026-11-18 NUS port, Phase 5 R0: reference rebuild (W15, PASS)

| Item | Value |
|---|---|
| Purpose | Plan `docs/plans/2026-11-18-nus-phase5-retraining.md` section 4.2 (R0): NUS's own hangar self-play lineages (seeds 1, 2, 3, generations 1-8) converted, each checked against Phase 3 gate (a), and scored as a 12 x 12 Guard x Strike matrix plus both APF columns at 1,000 games per pairing on the replica, before any Phase 5 gate is used |
| Gates | `[gates.phase5_reference_rebuild]` (FROZEN 2026-11-18 16:20), with `phase5_method_match` and `phase3_converted_policy`, copied verbatim into `runs/nus_port/phase5/reference/gates.toml` before the run (sha256 `014b7152dd278fa4e1b3b2bbf5ff6f009c8dfd95e5a673922129ba0b1bcae069`; `configs/nus_port.toml` sha256 `77ad9626c59ce4980daed9a694dec4d220b4b30b2e930657c270d4d8f38e8dfb`) |
| Owner approval | route (b) runs R0 -> C0 -> N0 -> 5.1, owner, 18 Nov 2026 ~18:30 (through the lead) |
| Date, machine | 2026-11-18; reference export 18:37-18:40 (CPU, `nus_jax`); R0 run 18:49:04-18:52:34 (+08:00): conversions and gate (a) 18:49:04-18:49:07, scoring 18:49:07-18:52:34; home RTX 5090 workstation, NVIDIA GeForce RTX 5090, torch 2.7.0+cu128 |
| Concurrent jobs | the three C0 jobs (NUS's own trainer, seeds 101, 201, 301, started 18:46, about 1.7 GB of GPU memory each) ran on the GPU the whole time (owner, 18 Nov: "parallelize"; `isaac_preflight.sh --allow-siblings` exit 0, 25.4 GB free) |
| Code | branch `nus-phase5-method`, commit `b86acb94` (`scripts/nus_phase5_reference.py`, `nus/crossplay.py`); the preflight's sibling fix was committed afterwards as `054af3e0` |
| Local files (sha256) | `configs/local/nus_rules.toml` `dd22cc28ce2042f3947f8427c5b69885187bb0b362498a487b67a753168c5a19`; `configs/local/nus_deploy_ref.toml` `6d71c111959fd9b2dd6fe48f83a8d3f645c12eff64ecb1a136d854ed30a08158` (the hangar geometry); `configs/local/nus_method.toml` `ce0b3d282cbe29cffeb1ba5fe78ac8251826b438a63c9afca0940c8fd4ed6c0b` (only its pool width is used here) |
| Reference observations | `scripts/nus_export_reference.py --archive-entry` x 24 (NUS's JAX actor in its own bfloat16 on 9 on-policy + 9 random episodes per entry, seed 20261122): 10,800 rows per entry; command in `runs/nus_port/phase5/reference/export_command.txt` |
| Scoring | `nus_phase5_reference.py --run --device cuda`: 1,000 games per pairing on one start set (`starts_seed` 20261120, the replica's random start rule), both teams deterministic, 168 pairings (144 cells + 24 APF), stacked 16 pairings per batch; 207 s of GPU wall clock (`runs/nus_port/phase5/reference/gpu_hours.log`) |
| Seeds | the reference lineages are NUS's seeds 1, 2, 3; one start set |

## Results

| Check | Rule (frozen) | Result |
|---|---|---|
| Gate (a) per entry | largest action error <= 0.02 units on >= 10,000 observation rows | **24 of 24 PASS**; largest error over all entries 0.0092 units; 10,800 rows each |
| Failed conversions | at most 2 | 0 (no entry leaves the reference set) |
| Leave-one-out check of 5.1-c | each entry's win rate against the other team's APF inside the Wilson envelope of the other 11 entries of its team | **PASS** (no miss): statistic 5.1-c stays a **gate** |
| Matrix | 1,000 games per pairing | `runs/nus_port/phase5/reference/matrix_1000.json`, sha256 `0cef471d08dcd869a7d0bb7537fb760d20f24faa4ec754c13074877b2a411704` |

INFO, observed in the training simulator (5.1-d seed values of the reference arm; NUS seed 1, 2, 3):

| Statistic | Seed 1 | Seed 2 | Seed 3 | F5 at 256 games |
|---|---|---|---|---|
| Guards' mean hold rate against the other lineages' Strikes | 0.281 | 0.377 | 0.441 | 0.28, 0.37, 0.44 |
| Strikes' mean reach rate against the other lineages' Guards | 0.455 | 0.699 | 0.747 | 0.46, 0.70, 0.75 |

Every Guard entry holds the zone against the APF Strike team in 0.939-0.982 of games; every Strike entry reaches the zone against the APF Guard team in all 1,000 games.

## Verdict

**PASS** (gate (a) on every entry; no failed conversion). 5.1-c remains a gate. Not run: the JAX cross-check (`jax_crosscheck = "INFO"`; `scripts/nus_jax_crossplay.py` is not built). No videos: R0 trains nothing (it scores NUS's archived entries). Smoke runs before this one (16 games, not of record) are in `runs/nus_port/phase5/smoke/`.
