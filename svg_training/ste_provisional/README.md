INTERNAL · the STE learning track's trained players, carried in git so the RTX 5090 desktop (or any fresh clone) can
run phase L1 from `development` alone. Bundled by the lead on 22 Nov 2026, before the laptop → 5090 switch.

# STE provisional bundle: trained players for phase L1

`runs/` is not in git, so the trained players of phase L0 would otherwise exist only on the laptop. This folder holds
the ones phase L1 reads, byte for byte (sha256 of every file in [SHA256SUMS](SHA256SUMS); check with
`cd ste_provisional && sha256sum -c SHA256SUMS`). All are observed in the training simulator only; nothing here has flown.

| Folder in `players/` | Record | What | Read by |
|---|---|---|---|
| `2026-11-21_ste_l012_base_guard` | [T46](../records/2026-11-21_ste_l012_best_response_record.md) | Guard team trained at tag 1.6 m against strike_straight (holds 913 of 1,000) | L1.8 re-score on the new drone model, L1.12 (scored against every Strike script), cross-play scoring |
| `2026-11-21_ste_l012_base_strike` | [T46](../records/2026-11-21_ste_l012_best_response_record.md) | Strike team trained at tag 1.6 m against guard_mark_edge (636; 85 against guard_field, [T56](../records/2026-11-22_ste_l012d_cross_tag_record.md)) | L1.8, cross-play scoring |
| `2026-11-22_ste_l012c_tag_1p15_guard` | [T54](../records/2026-11-22_ste_l012c_tag_1p15_guard_record.md) | Guard team trained at tag 1.15 m, 3× budget (572) | the 1.15 m side track, cross-play scoring |
| `2026-11-22_ste_l012c_tag_1p15_strike` | [T55](../records/2026-11-22_ste_l012c_tag_1p15_strike_record.md) | Strike team trained at tag 1.15 m, 5× budget (134) | the 1.15 m side track (L1.13), cross-play scoring |
| `2026-11-21_ste_l012b_tag_1p15_strike` | [T52](../records/2026-11-21_ste_l012b_best_response_record.md) | Strike team trained at tag 1.15 m against guard_field, standard budget, **ABORTED** at 0.54 B (information only; reaches 103) | L1.13 comparator (re-scored at 30 s and 120 s) |
| `../pilots/2026-11-21_ste_l012_pilot/` (`pilot.json`, `pilot.md`, its `gates.toml`) | L0.12 pilot (gate `9220fd9f…`) | the L0.12 pilot: picked the shaped Strike recipe (bare probe 0 reaches against g*, fallback 1); the file every L0.12, L0.12b and L0.12c run of record named (sha256 `b029a9…`) | `--pilot-json` of the L1.11 and L1.13 runs and run 0s (the driver checks the recipe only; added 22 Nov 2026 for the L1 side track) |
| `2026-11-21_ste_l014/response/per_game.npz` | [T45](../records/2026-11-21_ste_l014_crazyflie_route_record.md) | per-game results of the Crazyflie-response re-score | L6.5 method (T45) |

Each player folder keeps `agent_final.pt`, its `gates.toml`, the results (`results.json`, `results.md`), the evaluation
batches (`eval_*.npz`), `curve.json` where it exists and `train_log.jsonl`. Left out: `checkpoint.latest` (a resume
state) and the videos (they are in `docs/media/`).

**Use.** The drivers take the folder as an argument, so nothing needs installing: for example
`scripts/ste_cross_tag_l012d.py --t46-runs-dir ste_provisional/players …`. The pinned sha256 values in
`configs/ste_l012d/cross_tag.toml` match these files. The full run folders (videos, checkpoints, logs) stay on the laptop
in `~/AirStack-starling-max2/svg_training/runs/ste_archive/` (map in its README).
