# L1.0 on the RTX 5090, 23 Nov 2026 ~02:00-02:35 (+08:00); worktree ~/AirStack-starling-max2-l10 (branch ste-l1-0 = development 8fff7628, no edits)

## carry
$ scripts/ste_job.py carry --gpu-h 2.81 --note "laptop 2026-11-22"
carried 2.81 GPU-h to [budget_l1_l2] (laptop 2026-11-22); budget_l1_l2 (phases L1 + L2): used 2.810 of 13.0 GPU-h (own rows 0.000, carried 2.810)
(2.81 = laptop status Usage line: L1.1 0.20, L1.11 0.46, L1.12 0.02, L1.13 1.83, L1.14 0.15, L1.15 0.15)
Before the carry: status said "used 0.000 of 13.0 (own rows 0.000, carried 0.000)"; owner-pauses: "no owner pause is open".

## CPU capability
torch.backends.cpu.get_cpu_capability() -> AVX512; lscpu: AMD Ryzen 9 9950X3D 16-Core Processor

## TEST-F2b
pytest tests/test_train_standin.py -k bit_identical -rs  ->  "1 passed, 43 deselected in 4.70s", exit 0

## L09-5090
pytest -v -rs tests/test_game_tag_off_golden.py tests/test_tag_rule.py  ->  "46 passed in 10.56s", exit 0
tests/data/game_tag_off_golden.json keys: decimal = ['AVX2', 'NO AVX'] (no AVX512 entry); whole = 10 runs.
git cat-file -t dec9d276 -> "fatal: Not a valid object name dec9d276" (the pre-L0.9 commit the record must be made from is not in this clone, also not on any origin branch after fetch).

## closed-L0 path
$ ste_job.py launch --task L0.7 ... -> "refused: task L0.7 is in [budget] of ste_learning.toml, which is closed (phases L0): nothing is launched; the phase in work is L1", exit 2

## drills: see wakeup_wait.txt, resume_kill_and_wait.txt, resume_relaunch.txt, *_job.log (dummy job: 120 steps, 1 s each, checkpoint every 10)

## full suite (GPU hidden), see full_suite_5090.txt: "2213 passed, 54 skipped, 4 warnings in 1595.88s", pytest exit 0 (from the background task's own exit code).
Laptop's last recorded full suites for comparison: 20 Nov 1,333 passed / 2 failed / 48 skipped; 21 Nov 1,420 passed.
Five skips in tests/test_ste_l03.py ("the bundle or T45's per-game file is missing"): gates expect runs/2026-11-21_ste_l014/response/per_game.npz (sha 3959d594...), the file is in git at ste_provisional/players/2026-11-21_ste_l014/response/per_game.npz but not installed to runs/. Lead copied it (sha matches) and is re-running tests/test_ste_l03.py.
