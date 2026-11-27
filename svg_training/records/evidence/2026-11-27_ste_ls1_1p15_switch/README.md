Evidence for route 3's move to the 1.15 m tag (owner R51, 27 Nov 2026), steps C0, C, B and D of the switch plan; read with the record [2026-11-27_ste_ls1_1p15_switch_record.md](../../2026-11-27_ste_ls1_1p15_switch_record.md), the plan [LS1_1P15_SWITCH.md](../../../ste_learning/drafts/LS1_1P15_SWITCH.md) and the options page [LS1_1P15_LIMIT_OPTIONS.md](../../../ste_learning/drafts/LS1_1P15_LIMIT_OPTIONS.md); not of record

Training simulator, tier 1, CPU only; observed in the training simulator, not a flight result. Absolute paths were
replaced with placeholders when the files were copied here (`<svg_training>`, `<scratch>` for the session scratch folder,
`~/`). Run the scripts from `svg_training/` with `PYTHONPATH=source` (the conda env `env_isaaclab`, no GPU). Step E (the
pilot networks replayed at 1.15 m) is **not** here: its results are sealed until the owner rules the 1.15 m limits.

| Folder | Files | What | Reads (under `runs/`, not in git) |
|---|---|---|---|
| `c0/` | `c0.py`, `c0.json`, `c0.log` | step C0: T50's 30 fixed scripted cells replayed on the CPU against `configs/ste_l012b/screen_reference.npz`; 30 of 30 exact | none (plays) |
| `c/` | `c.py`, `c_guard.log`, `c_strike.log` | step C: the scripted stages of the copy check at 1.15 m (network check bypassed, R48's values filled in a scratch copy so 1,000 games a cell are read) | writes `2026-11-27_ste_ls12_1p15_scripts_{guard,strike}` |
| `b/` | `b_table.py`, `b_table.{json,md}`, `run0_ceiling_1p15_{results.md,cmd.txt}` | step B: every cell's wins at 1.6 m (T44, T94) and 1.15 m (T50, step C); the run 0 ceiling at 1.15 m (T97) | `2026-11-26_ste_ls12_read_*`, `2026-11-27_ste_ls12_1p15_scripts_*`, `2026-11-27_ste_l3_run0_ceiling_1p15` |
| `limits/` | `check.py`, `r48_at_1p6.json`, `r48_at_1p15.json`, `f31.json`, `f35.json` | R48's limits (and `flips_max_games` 31, 35) judged with the gate's own rule (`scripts/ste_ls1_equivalence.py`) on the calibration reads; on the 1.6 m runs it reproduces `LS1_LIMIT_OPTIONS.md` section 6 exactly | `2026-11-25_ste_ls15_calibration_*`, `2026-11-26_ste_ls15_topup_*`, `2026-11-27_ste_ls15_1p15_calibration_*`, `2026-11-27_ste_ls15_1p15_topup_*` |

Re-run the limits check: `python check.py runs/<calibration run with SIDE> runs/<top-up run with SIDE> <limits gate file>
<near-miss gate file> <out.json>` (SIDE is replaced by guard and strike). In cell labels, `a+b+c@x` means the line-up
a, b, c against opponent x. The scripts ran on commits `7d511274` (C0, ended 08:29), `20fbd511` (C, the ceiling) and `6aac9e9e` (the limits check,
read-only).
