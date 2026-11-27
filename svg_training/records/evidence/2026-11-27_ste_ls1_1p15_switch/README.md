Evidence for route 3's move to the 1.15 m tag (owner R51, 27 Nov 2026), steps C0, C, B, D and E of the switch plan; read with the record [2026-11-27_ste_ls1_1p15_switch_record.md](../../2026-11-27_ste_ls1_1p15_switch_record.md), the plan [LS1_1P15_SWITCH.md](../../../ste_learning/drafts/LS1_1P15_SWITCH.md) and the options page [LS1_1P15_LIMIT_OPTIONS.md](../../../ste_learning/drafts/LS1_1P15_LIMIT_OPTIONS.md); not of record

Training simulator, tier 1, CPU only; observed in the training simulator, not a flight result. Absolute paths were
replaced with placeholders when the files were copied here (`<svg_training>`, `<scratch>` for the session scratch folder,
`~/`). Run the scripts from `svg_training/` with `PYTHONPATH=source` (the conda env `env_isaaclab`, no GPU). Step E (the
pilot networks replayed at 1.15 m) was sealed until the owner ruled the 1.15 m limits (R52, 27 Nov 2026) and is in `e/`.

| Folder | Files | What | Reads (under `runs/`, not in git) |
|---|---|---|---|
| `c0/` | `c0.py`, `c0.json`, `c0.log` | step C0: T50's 30 fixed scripted cells replayed on the CPU against `configs/ste_l012b/screen_reference.npz`; 30 of 30 exact | none (plays) |
| `c/` | `c.py`, `c_guard.log`, `c_strike.log` | step C: the scripted stages of the copy check at 1.15 m (network check bypassed, R48's values filled in a scratch copy so 1,000 games a cell are read) | writes `2026-11-27_ste_ls12_1p15_scripts_{guard,strike}` |
| `b/` | `b_table.py`, `b_table.{json,md}`, `run0_ceiling_1p15_{results.md,cmd.txt}` | step B: every cell's wins at 1.6 m (T44, T94) and 1.15 m (T50, step C); the run 0 ceiling at 1.15 m (T97) | `2026-11-26_ste_ls12_read_*`, `2026-11-27_ste_ls12_1p15_scripts_*`, `2026-11-27_ste_l3_run0_ceiling_1p15` |
| `e/` | `judge.py`, `e_judged.{json,md}`, `sealed/*.json`, `oracle_{guard,strike}.json`, `inputs.sha256`, `code/` (`e_run.py`, `harness.py`, `jobs.txt`, `run_all.sh`, `dispatch.log`), `logs/` | step E: the R50 pilot networks at 1.15 m (sealed per-assembly files, the script-oracle results), judged once with R52's gate file (`judge.py`, sha-pinned); `e_judged.md` has every cell. The jobs also used the pilot harness's `lsr.py`, `stage2.py`, `blend.py`, `s2run.py` (copies in `../../2026-11-27_ste_ls1_redesign_pilots/`) and the pilot networks (`nets/`, not in git) | the calibration `2026-11-27_ste_ls15_1p15_calibration_*` (noise 0.02 arm); step C's games when the jobs ran |
| `limits/` | `check.py`, `r48_at_1p6.json`, `r48_at_1p15.json`, `f31.json`, `f35.json` | R48's limits (and `flips_max_games` 31, 35) judged with the gate's own rule (`scripts/ste_ls1_equivalence.py`) on the calibration reads; on the 1.6 m runs it reproduces `LS1_LIMIT_OPTIONS.md` section 6 exactly | `2026-11-25_ste_ls15_calibration_*`, `2026-11-26_ste_ls15_topup_*`, `2026-11-27_ste_ls15_1p15_calibration_*`, `2026-11-27_ste_ls15_1p15_topup_*` |

Re-judge E from `svg_training/` (it reads `e/`, `b/b_table.json`, the 1.6 m pilot folder and step D's `results.json`):
`python records/evidence/2026-11-27_ste_ls1_1p15_switch/e/judge.py records/evidence/2026-11-27_ste_ls1_1p15_switch/e
runs/2026-11-27_ste_ls15_1p15_calibration_SIDE <out.json> <out.md>`.

Re-run the limits check: `python check.py runs/<calibration run with SIDE> runs/<top-up run with SIDE> <limits gate file>
<near-miss gate file> <out.json>` (SIDE is replaced by guard and strike). In cell labels, `a+b+c@x` means the line-up
a, b, c against opponent x. The scripts ran on commits `7d511274` (C0, ended 08:29), `20fbd511` (C, the ceiling) and `6aac9e9e` (the limits check,
read-only).
