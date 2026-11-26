Simulator: training simulator, tier 1 (fast engine; Starling layer), played on the CPU of the RTX 5090 workstation for the smoke and the copy check; the label-tolerance probe ran on the GPU (CUDA). Observed in the training simulator; not a flight result.

# 2026-11-26 STE LS1.0 smoke and label-tolerance probe record

**reviewed by one reviewer, 26 Nov 2026**. Written by the technical writer (Sonnet 5.5) from the run folders; every
number below is copied from them unless marked "computed for this record".

## Purpose

Part (a): job LS1.0 of route 3, stage LS1, the CPU smoke of the distillation driver (`scripts/ste_ls1_distil.py
--smoke`) and of the copy check (`scripts/ste_ls1_equivalence.py --smoke`), run on code `38c917a9` before the owner's
limits (R48) were set: to show that the two drivers run end to end on both sides. Not of record; verdict NOT_RUN by
design. Part (b): the label-tolerance probe on the GPU, which measured on CUDA the largest label difference that the
gate file's `label_check_atol` (1e-05) bounds. Part (b) belongs to task LS1.1 and its GPU time is charged to it.

## Commit

Part (a): `38c917a970c3ab4655fe880bcc83ae6bffc69212`, `code.json` of every smoke folder (diff_sha256 `e3b0c442…b855`
= the hash of empty input: no uncommitted change; `changes` empty). Part (b): the folder holds no `code.json`; its
`cmd.txt` names the code path `~/AirStack-starling-max2-ls1fill/svg_training`, a worktree since removed, so the code of
the probe cannot be re-read from that path; the commit of that worktree is not recorded.

## Config

Part (a) ran `configs/ste_ls1/distil_gates.toml` as it was before the owner's limits: sha256
`ea5f2921d9fead72a943d47a97c60e16c17e5cee07f2e6121c5c024f8fc6dd39` (in each `results.md`, copy in the folders'
`gates.toml`), with every owner key a `FILL_` string. The committed file now is sha256
`5cce1245052f2e9ef87d6a3c83d2301f1161100ed818224b932b0248735ee6bb` (R48 values). Part (b) read the gate file from the
worktree named above.

## Model parameter set

The tier-1 drone model of the pinned skills gate file's game (`configs/ste_l011/base.toml`, the gate file's `[source]`).

## Seeds

Gate file `[data]` seed 150001, pool seed 150002, fit seed 150003, report seed 150004, clips seed 150005 (as in the
file; the smoke inherits them); the read's starts are T44's (seed 110000).

## Machine

The home RTX 5090 workstation; boot `2ff91543…`. Part (a) on the CPU (`CUDA_VISIBLE_DEVICES` empty, `cmd.txt`),
`--cap-h 1.0` (distil) and `--cap-h 2.0` (read), `--gpu-h 0.0`. Part (b) on the GPU (device `cuda`; `CUDA_VISIBLE_DEVICES`
not set).

## Games at once

Smoke sizes (gate file `[smoke]`): 16 games x 120 ticks per round, 2 rounds (`script_share` [1.0, 0.5]), report 16
games x 120 ticks; the copy check 24 games per cell. Probe: 2,048 games x 300 ticks, round 0 (script-flown), per side.

## Steps per second

Not recorded.

## Gates

None: NOT_RUN by design (part (a)); part (b) is a measurement.

## Commands

Part (a) (from `cmd.txt`, home paths written `~/`), launched with `scripts/ste_job.py launch --task LS1.0
--gpu-h 0.0`:

```
python scripts/ste_ls1_distil.py --gates configs/ste_ls1/distil_gates.toml --side <side> \
  --run-dir runs/2026-11-26_ste_ls10_smoke_<side> --cap-h 1.0 --smoke
python scripts/ste_ls1_equivalence.py --gates configs/ste_ls1/distil_gates.toml --side <side> \
  --skill-net runs/2026-11-26_ste_ls10_smoke_<side>/skill_net_<side>.pt \
  --run-dir runs/2026-11-26_ste_ls10_smoke_read_<side> --cap-h 2.0 --smoke
```

Part (b), `ste_job.py launch --task LS1.1 --name ls11_atol_probe --gpu-h 0.05 --min-s 5.0`, child: `python
runs/2026-11-26_ste_ls11_atol_probe/atol_probe.py ~/AirStack-starling-max2-ls1fill/svg_training
~/AirStack-starling-max2-dev/svg_training/runs/2026-11-26_ste_ls11_atol_probe`. The script (sha256
`f756d8768147fb1eddcb1ec68dcf25c2dbe8d0aa47905fa7d128a89ef11e0366`) loads `ste_ls1_distil.py` from the worktree, collects
round 0 per side on `cuda` and runs the driver's own `label_check` with a huge atol so the difference is reported, not judged.

## Launch errors and re-launches

Part (a): one launch each, exit 0. Part (b), `launches.jsonl` (times +08:00, computed for this record):

| Launch | Start | End | Exit | What |
|---|---|---|---|---|
| 1 | 26 Nov 09:05:08.8 | 09:05:09.7 (0.8 s) | 1 | crashed on loading `ste_ls1_distil.py` from the probe script: `AttributeError: 'NoneType' object has no attribute '__dict__'` inside `@dataclass` (the module was not entered in `sys.modules` before `exec_module`); a fault of the probe script, not of the driver |
| 2 | 09:05:16.3 | 09:05:29.2 (12.9 s) | 0 | finished; the script now has `sys.modules["dr"] = dr` before `exec_module` |

The cause of launch 1 is read from the traceback in `job.log`; that the line was the only change is the reading of the
script as it stands, not shown by a copy of the first version.

## Timing

Part (a), seconds from `launches.jsonl` (computed for this record):

| Folder | Start (26 Nov, +08:00) | Seconds |
|---|---|---|
| `ls10_smoke_guard` | 05:29:21 | 18.5 |
| `ls10_smoke_strike` | 05:29:21 | 20.8 |
| `ls10_smoke_read_guard` | 05:29:54 | 276.7 |
| `ls10_smoke_read_strike` | 05:29:54 | 513.6 |

## Controls

Part (a), distillation smoke (`controls.json`): `ctl_labels_are_the_scripts` PASS on both sides. Guard: round 0: 0 of 4,907
kept rows differ by more than `label_check_atol` (0 not bit-equal, largest difference 0); round 1: 0 of 4,885 (29 not
bit-equal, largest 8.34e-07). Strike: round 0: 0 of 4,717 (largest 0); round 1: 0 of 4,705 (largest 0).

Copy-check smoke (`controls.json`, computed for this record): Guard 112 controls, 105 PASS, 7 NOT_RUN; Strike 107
controls, 98 PASS, 9 NOT_RUN. Every NOT_RUN is "not judged: the owner's keys are not filled" (permuted, unfitted, permuted
net, the near-miss bias, rotate, switch and noise controls). No FAIL (`job.log`: no control failed).

## Results

Part (a), distillation smoke (`fit_report.json`, `job.log`; 40 epochs per round on a few thousand rows, a plumbing check only):

| Side | Round 0 rows (kept) | Round 0 last loss | Round 1 rows (kept) | Round 1 last loss | Network sha256 |
|---|---|---|---|---|---|
| Guard | 4,907 (4,907) | 0.109693 | 4,885 (4,885) | 0.0691975 | `1824a6f9efabf4b7d9358fca2fda064fa7fccb308b6abf404c3cb36f61a52f00` |
| Strike | 4,717 (4,717) | 0.100342 | 4,705 (4,705) | 0.0818805 | `e07b1254c0e80bc3d2ffdfe9d6254617e6536047b160f14d6657ea33f756b3db` |

Copy-check smoke: 24 games per cell on the smoke network; `results.json` `complete: true`, `of_record` false, verdict
**NOT_RUN** on both sides ("the owner's keys are FILL_: no verdict is read"; `results.md`). Its game results say nothing
about the network.

Part (b), label-tolerance probe (`atol_probe.json`, `job.log`), CUDA, round 0, 2,048 games x 300 ticks per side:

| Side | Labels checked | Differ by more than the huge atol | Not bit-equal | Largest abs difference | Seconds |
|---|---|---|---|---|---|
| Guard | 1,486,542 | 0 | 0 | 0.0 | 6.2 |
| Strike | 1,476,833 | 0 | 0 | 0.0 | 5.6 |

The labels the driver kept on CUDA equal the scripts' labels bit for bit on these rows: largest difference 0.0 against
the gate's `label_check_atol` of 1e-05. The gate file's comment "Not measured on CUDA" is left as written (editing it
changes the pinned hash); this record is the CUDA measurement. It covers round 0 only (script-flown), at this size.

## Verdict

**INFO.** Part (a) NOT_RUN by design (both drivers ran to the end, exit 0); part (b) a measurement with no gate.

## Videos

The smoke distillation folders hold a `videos/` folder (clips of the smoke network, e.g.
`guard_guard_parked_ring_g1_net.gif` beside `..._scripts.gif`); they are of a network fitted on a few thousand rows and
are not evidence of anything.

## GPU hours

Part (a): 0 GPU-h. Part (b): from `runs/shared/gpu_hours.log` (the shared folder
`~/AirStack-starling-max2/svg_training/runs/shared/`, lines with `ls11_atol_probe`, group LS1.1): two entries, 0.815 s and
12.833 s, 13.65 s in all = 0.0038 GPU-h (computed for this record), charged to LS1.1 (the job's `--gpu-h` was 0.05).

## What this does not show

- That the network copies the scripts: the smoke is a plumbing check on a few thousand rows.
- The label difference beyond round 0 or beyond this probe's size; the CPU maximum in the gate file's comment (7.2e-07,
  8.7 million rows) is a different measurement on a different device.
- Which commit the probe ran on (the removed worktree).
- Tier 2, or any flight.

## Evidence

Run folders (not in git), in `~/AirStack-starling-max2-dev/svg_training/runs/`: `2026-11-26_ste_ls10_smoke_{guard,strike}/`,
`2026-11-26_ste_ls10_smoke_read_{guard,strike}/`, `2026-11-26_ste_ls11_atol_probe/` (`atol_probe.py`, `atol_probe.json`,
`job.log`, `cmd.txt`, `launches.jsonl`). sha256: `atol_probe.json`
`a2afcc8dec39e1f76bdedb810b9b1c378452ddb541b053bc5057c9667d821875`; `ls10_smoke_read_guard/results.json`
`5f08dc9bf769c466a8ea2de127977315c4aec65b8adc1450ba64939a948ddb9e`; `ls10_smoke_read_strike/results.json`
`6b84c7d226fec675a312a9477634fbc8a21d895e928412b52d4594fc5e9c22d4`; `ls10_smoke_guard/fit_report.json`
`841869c1dad76e6f78d41f3c26f734f8ec9da6c03732e5157b3f59e89d831d6c`; `ls10_smoke_strike/fit_report.json`
`724dbd3260591f0da3d87107f2da8f419da41e6a91c620440c58c9f16fc443e2`.

## Ledger row (T92)

| # | Date | Simulator | Run | What | Result | Record |
|---|---|---|---|---|---|---|
| T92 | 2026-11-26T09:05:29+08:00 | training simulator, tier 1; CPU (smoke and copy check), GPU (probe) | 2026-11-26_ste_ls10_smoke_{guard,strike}, 2026-11-26_ste_ls10_smoke_read_{guard,strike}, 2026-11-26_ste_ls11_atol_probe | STE LS1.0 CPU smoke of the distillation (2 rounds, 4,907 / 4,885 Guard and 4,717 / 4,705 Strike rows, label control PASS) and of the copy check (24 games per cell; verdict NOT_RUN by design, owner keys FILL_) on code 38c917a9, exit 0, 18.5 to 513.6 s; and the LS1.1 label-tolerance probe on CUDA (first launch crashed in 0.8 s, a module-loading fault of the probe script; second: 1,486,542 Guard and 1,476,833 Strike labels, largest difference 0.0, bit-equal, against label_check_atol 1e-05; code path a removed worktree); 0.0038 GPU-h charged to LS1.1 | INFO | `records/2026-11-26_ste_ls10_smoke_record.md` |
