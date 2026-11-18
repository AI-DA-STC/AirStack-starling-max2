# PROVISIONAL: the lab's NUS-port files (weights, local settings, recordings)

**PROVISIONAL.** Trained by the lab with NUS's code (commit `2d2b904`), 8 generations of self-play (seed 2 continued to 20),
on the lab's hangar set-up. Kept so anyone can repeat our numbers exactly. **Not final: NUS will retrain.** Nothing here
was trained by NUS, and nothing here has flown. Owner decision 6, 18 November 2026 (NUS agreed that its settings and our
results on its code may be published; NUS's source code is not in this folder or anywhere in this repository).

## What it is for

The NUS-port code reads its settings from the git-ignored `configs/local/` and its data from the git-ignored
`runs/nus_port/`. A fresh clone has neither, so the NUS tests skip and the ladder rows cannot run. Installing this folder
fills both with the lab's own files, byte for byte, so that:

- the NUS tests that compare our PyTorch copy with NUS's own code run (replica recordings, reference actions);
- every Phase 4 ladder row runs with the same weights, settings and starts as our records (`records/2026-11-18_nus_phase4_*`).

Install (from `svg_training/`; checks every sha256 first, never overwrites a different file unless `--force`):

```bash
scripts/nus_install_provisional.sh            # --dry-run to see what it would copy
```

It copies `configs/*` to `configs/local/` and `nus_port/*` to `runs/nus_port/`. The code keeps reading only those two
places; nothing reads this folder directly.

## Contents (44 MB; sha256 of every file in [SHA256SUMS](SHA256SUMS))

| Path here | Installed to | What | How it was made |
|---|---|---|---|
| `configs/nus_rules.toml`, `nus_rules_5v3.toml` | `configs/local/` | NUS's game rules, 3 v 3 and 5 v 3 | `scripts/nus_make_local_rules.py` from NUS's config (T15, `records/2026-11-17_nus_phase2_parity_record.md`) |
| `configs/nus_deploy.toml` | `configs/local/` | scale 0.40 m per unit, 0.60 s per step, hold 12 ticks; names the Phase 3 weights | `scripts/nus_make_local_deploy.py` (T16, `records/2026-11-18_nus_phase3_conversion_record.md`) |
| `configs/nus_deploy_ref.toml` | `configs/local/` | the same, naming the G19/S20 weights | `nus_make_local_deploy.py --same-as configs/local/nus_deploy.toml` (T17, `records/2026-11-18_nus_phase4_w3_reference_gates_record.md`) |
| `configs/nus_hangar.toml` | `configs/local/` | the hangar side, 7.5 m | `configs/nus_hangar.template.toml` with the owner's value |
| `configs/nus_method.toml` | `configs/local/` | NUS's training-method settings (Phase 5 port) | `scripts/nus_make_local_method.py` from NUS's run config (nus-method worktree) |
| `nus_port/weights/ref_s2_g19_guard/`, `ref_s2_g20_strike/` | `runs/nus_port/weights/` | **G19 and S20**: self-play seed 2, Guard generation 19 and Strike generation 20 | NUS's training code on the lab's 5090, then `scripts/nus_convert_checkpoint.py` (T17) |
| `nus_port/weights/hangar_guard_fixed_apf/`, `hangar_strike_fixed_apf/` | `runs/nus_port/weights/` | **P3G and P3S**: each team trained against NUS's scripted controller | NUS's code, then `nus_convert_checkpoint.py` (T16) |
| `nus_port/phase4/starts.npz` | `runs/nus_port/phase4/` | the 1,000 paired starts every ladder row plays | `scripts/nus_phase4.py --make-starts` |
| `nus_port/reference/` | `runs/nus_port/reference/` | NUS's own JAX actor's actions on recorded observations, its scripted controller's states, shared starts | `scripts/nus_export_reference.py` in NUS's environment (T16) |
| `nus_port/phase3_outcome_parity.json` | `runs/nus_port/` | T16's outcome counts (row 1's exact replay reads them) | `scripts/nus_outcome_parity.py` (T16) |
| `nus_port/fixtures/` | `runs/nus_port/fixtures/` | step-by-step recordings of NUS's own game (3 v 3, 5 v 3, gate sets, a training-field set) | `scripts/nus_record_fixtures.py` in NUS's environment (T15; `train_hangar_3v3` for the Phase 5 port) |

The sha256 values match the records: rules `dd22cc28…`, deploy `c248c6be…`, deploy_ref `6d71c111…`, hangar `b7f2870e…`,
starts `40c8cc59…`, G19 `ac3dde1e…`, S20 `210165db…`, gate recordings `b43dc8a0…` and `84dc274f…`.

## Read before relying on it

- **Byte-identical copies.** Nothing was edited, so the hashes in the records still match. Two consequences: the
  settings files keep their old first line ("never copy into a tracked file", written before decision 6), and
  `config.json`, `metadata.json` and `interface.toml` keep the lab's absolute paths (`/home/…`) and the name of NUS's
  logging account from NUS's default config (logging was switched off for every run).
- **Not in this folder:** NUS's source code; the motion-capture camera survey; `runs/nus_port/w3/reference/` (5.7 MB,
  used only by the INFO check `nus_phase4.py --cuda-parity`); the Phase 5 one-update exports (223 MB, regenerate with
  `scripts/nus_jax_export_update.py`; their 3 tests skip and say so); `configs/local/partner_rules.toml` (exists in no
  lab worktree; its 2 privacy scans skip and say so).
- **Rows 1–3 settings.** Rows 1, 2, 2.1, 2.2, 3a and 3 ran with earlier versions of `configs/nus_phase4.toml` (recorded
  sha256 `298a08b9…` and `0732011e…`); rows 4, 5a, 5 and 6 with the current file (`64ae48cf…`). The weights, local
  files and starts are the same for all rows.
- Repeating a row on another GPU gives the same counts within the Wilson intervals, not game by game (GPU arithmetic
  and bfloat16).
- Privacy tests let this folder, and only this folder, hold NUS's values and checkpoint files (STANDARDS §2);
  everywhere else code still reads them from `configs/local/`.
