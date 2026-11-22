INTERNAL · record of task L1.0 (RTX 5090 machine checks) of STE's learning track. Not a training result.

# L1.0 on the RTX 5090: machine checks (23 November 2026, ~02:00–02:45 +08:00)

**Machine:** home RTX 5090 workstation (AMD Ryzen 9 9950X3D, PyTorch CPU capability AVX512, Python 3.13.5 for
`gpu_pause.sh`). **Tree:** worktree `~/AirStack-starling-max2-l10`, branch `ste-l1-0` cut from `development` at
`8fff7628`. **GPU-hours used:** 0 (no training or measurement run; the GPU-only tests ran for about 3 minutes and log
no hours). **Status:** the machine-check part of L1.0 is DONE; its **speed re-measure is deferred** (the laptop lead,
23 Nov: the drone model changes with L1.1b; it runs after L1.1b/L1.7), and with it assumption A8's second half
("three tier 2 seeds side by side fit its 32 GB", costed plan) and the tier-2 physics check at 16,384 games that
HANDOFF warned might fail on a larger world. Two independent reviewers checked the evidence (numbers; completeness).

| Check | Result |
|---|---|
| Owner pauses | none open (`scripts/ste_job.py owner-pauses`) |
| Carry of the laptop's L1 hours | `carry --gpu-h 2.81 --note "laptop 2026-11-22"`: ledger `budget_l1_l2` used 2.810 of 13.0 (own rows 0.000, carried 2.810). 2.81 = L1.1 0.20 + L1.11 0.46 + L1.12 0.02 + L1.13 1.83 + L1.14 0.15 + L1.15 0.15. **Done once; do not repeat.** |
| Bundles | `nus_install_provisional.sh` 46 files; `ste_provisional` sha256 list all OK |
| TEST-F2b (training fingerprint on this CPU) | `test_default_path_bit_identical_after_the_nus_hooks`: 1 passed, not skipped; the 18 Nov hash filed under the AVX512 key is confirmed |
| L09-5090 (tag-off game on this CPU) | AVX512 record added to `tests/data/game_tag_off_golden.json` from `5ebac526` (parent of the L0.9 commit `50d8f8f2`; `dec9d276` is not in the shared history). That tree reproduced the AVX2 and NO AVX records exactly here first. AVX512's decimal fingerprints equal AVX2's. The current game now checks natively under AVX512: `checked capability AVX512: equal to the pre-L0.9 record`; `test_game_tag_off_golden.py` + `test_tag_rule.py` 46 passed |
| Closed phase L0 | `launch --task L0.7` refused, exit 2 ("which is closed (phases L0)") |
| Wake-up drill (`--task L1.0`) | `L1.0 l10_wakeup DONE exit=0 duration=120.2s`, waiter exit 0 |
| Resume drill (`--task L1.0`) | alive, then dead after `kill -KILL` of the group at 45 s; `DIED exit=none`, waiter exit 21; relaunch with `bash …/cmd.txt` printed `launch=2`; `resumed from step 40 of 120`; `DONE exit=0 … run_effective=120.1s`; `{"steps": 120, "total": 7260.0}` |
| Full CPU suite (GPU hidden) | **2,213 passed, 54 skipped, 0 failed**, pytest exit 0, 26.6 min. Skips: 41 need the GPU or Isaac Sim (expected with the GPU hidden); 6 `test_ste_l03` (T45's per-game file, see below); 3 NUS parity exports and 1 `states.pt` (in other worktrees of this machine); 2 partner file and 1 `~/nus_jax_reference` (not on the machine) |
| GPU-only tests, GPU visible | the 8 test files with "CUDA only" / "no CUDA device" skips: 203 passed, 1 skipped (`states.pt`), 1 xfailed; with `states.pt` copied from `~/AirStack-starling-max2-filter-graph`: `test_safety_filter_graph.py` 32 passed, 1 xfailed |
| L0.3 tests | T45's per-game file copied from `ste_provisional/players/2026-11-21_ste_l014/response/per_game.npz` to `runs/2026-11-21_ste_l014/response/per_game.npz` (sha256 `3959d594…`, equal to the pin in `configs/ste_l03/gates.toml`): `test_ste_l03.py` 21 passed (6 had skipped) |
| `gpu_pause.sh` | `status` runs on this machine; `python3` is 3.13.5, so `GPU_PAUSE_PYTHON` is not needed. No live pause was made |

**Found, for the laptop lead and the owner:**
1. The L0.3 gates read T45's per-game file under `runs/`, but `ste_provisional/README.md` says "nothing needs
   installing": on a fresh clone the six L0.3 tests skip until the file is copied (as above). The fix belongs on the
   install side (the gates file is sha-locked).
2. The main clone `~/AirStack-starling-max2` is on `main` and its `scripts/gpu_pause.sh` is the older copy (no
   `scripts/ste_*.py` pattern, no shared pause log). If the owner pauses jobs from that copy before gaming, an STE job
   would not be paused and the pause would not reach the shared log. The owner should pause from the `development`
   worktree's copy (`~/AirStack-starling-max2-dev/svg_training/scripts/gpu_pause.sh`).
3. The drill lines in `ste_learning/AUTOMATION.md` §7 use `--task L0.7`, refused since L0 closed; a note there now says to
   use the current phase's machine-check task.

Evidence: the raw outputs are in [evidence/2026-11-23_ste_l10_5090/](evidence/2026-11-23_ste_l10_5090/) (commands and
outputs, the full suite's summary, the drill logs, the GPU-visible and L0.3 runs).
Run folders: `runs/ste_l10_drills/` of the `-l10` worktree (git-ignored).
