# Getting started: from a clone to a benchmark run

Three goals, in order: the tests pass, a dry run prints its plan, the S0 benchmark runs and writes a record.
Use the container (part A) unless you already have Isaac Lab installed on the host (part B).
Terms are in the [glossary](GLOSSARY.md).

## What you need

| Item | Detail |
|---|---|
| NVIDIA GPU and driver | T1 ran on an RTX 5070 Ti Laptop GPU, driver 580.178.04 |
| GPU memory | at least 12 GB: T1 used up to 7.6 GB device-wide on 12 GB; Isaac Sim states a 16 GB minimum |
| Docker + NVIDIA Container Toolkit | the container starts with `--gpus all` |
| Disk | about 26 GB for NVIDIA's Isaac Lab image, downloaded once by `docker/build.sh` |
| Internet, first tier 2 run | Isaac Lab downloads its drone asset the first time |
| A free GPU | no AirStack simulator, flight session or other Isaac process running; check with `nvidia-smi` on the host |

Every command below runs from the folder: `cd ~/AirStack-starling-max2/svg_training`.

## A. In the container (the repository's way)

**A1 · Build the image, once.**

```bash
docker/build.sh
```

Must see: `built svg-training:isaaclab-2.3.2`. Code is mounted at run time, so code changes need no rebuild.
What the image holds and where it stores things: [docker/README](../docker/README.md).

**A2 · Run the tests.**

```bash
docker/run.sh '$SVG_PY -m pytest -q'
```

Passed when the last line has no `failed`. Two skips in the container are normal (host-only tests).

**A3 · Dry run.** Prints every command the benchmark would run; starts nothing.

```bash
docker/run.sh bash scripts/run_s0.sh --dry-run 2026-11-20_s0_trial <approved sha256> | head -40
```

<a id="approved-sha256"></a>**The approved sha256** (the config T1 ran, [record](../records/2026-11-15_s0_laptop_record.md#config)):
`2d3114864a8f335ce8456e40af9c50c63700d59d821d53b9b0f3e7abac2accf0`.
`sha256sum configs/s0_benchmark.toml` must print exactly this; if it differs, `run_s0.sh` stops with exit 65 and
the config needs the owner's approval (gates are never moved).
The dry run prints the plan for where it runs (host paths on the host, container paths inside `docker/run.sh`);
`head -40` keeps it short, as tier 2 adds one long line per point.

**A4 · The benchmark.** Pick a new name, `YYYY-MM-DD_s0_<label>` (lowercase letters, digits, `_`).

```bash
docker/run.sh bash scripts/run_s0.sh 2026-11-20_s0_workstation <approved sha256>
```

Must see at the end: `record: records/<name>_record.md` and the verdict line. Run headless; do not use the GPU
for anything else meanwhile.

## B. On the host

For a machine that already has Isaac Lab 2.3.2 in `~/IsaacLab` and conda `env_isaaclab` (this laptop has both).

```bash
~/miniconda3/envs/env_isaaclab/bin/python -m pytest -q          # tests
bash scripts/run_s0.sh --dry-run <name> <approved sha256>         # dry run
bash scripts/run_s0.sh <name> <approved sha256>                   # the benchmark
```

The script finds Python and Isaac Lab by itself; tier 2 starts through `conda run -n env_isaaclab`.
Never edit `~/IsaacLab`. Versions of both set-ups: [GLOSSARY, Versions](GLOSSARY.md#versions).

## Which to use

| Situation | Use |
|---|---|
| A new machine, a training workstation, a run of record | the container: one known image, same as T1 |
| Quick tests on this laptop | either; the host skips the container start |
| The host's Isaac Lab differs from 2.3.2 | the container |

## Reading the output

| Where | What |
|---|---|
| `runs/<name>/preflight.txt` | start time, code hash, config hash, GPU state before the run |
| `runs/<name>/tests.txt` | the test step's output |
| `runs/<name>/results.jsonl` | one line per repeat of every point: speeds, memory, status (`ok`, `oom`, `crash`) |
| `runs/<name>/tier1.log`, `tier2.log`, `tier2_logs/` | progress; one log per tier 2 point |
| `runs/<name>/retried_points.txt` | tier 2 points retried after an Isaac start-up crash (only if any) |
| `records/<name>_record.md` | the record: tables, gates with PASS or FAIL, decision rules, limits; never edited |
| `records/LEDGER.md` | one row per run, T1, T2, … |

`runs/` is not in git; `records/` is. How to read T1: [S0_RESULTS](S0_RESULTS.md).

## How long it takes

T1 took 1 h 47 min on the laptop: preflight at 00:54 Singapore time on 15 November 2026, last row at 02:41.
Tier 1 took most of it. Its slowest points step about once every 2 s (`t1_5v3_prim50_full` at 16,384 games), so
the 200-step timed window lasts up to about 7 minutes per repeat. Tier 2 took about a quarter of an hour.
T1's own files show these times in container UTC (8 h behind).

## When it fails

| Exit code | Meaning | What to do |
|---|---|---|
| 0 | the record was written, whatever its verdict | read the record |
| 1 | the record could not be written | read the last lines of the output |
| 64 | bad arguments | check the name pattern and the 64-hex hash |
| 65 | config differs from the [approved one](#approved-sha256) | do not edit the config; ask the owner |
| 66 | an Isaac or AirStack container is running | stop it (`docker ps`), then retry |
| 67 | `records/<name>_record.md` already exists | choose a new name; a record is never overwritten |
| 68 | another process uses the GPU (python, kit, isaac or omni) | stop it; `nvidia-smi` on the host |
| 130 | interrupted (Ctrl-C) | an `ABORTED` record is written in `records/` |

- A crashed or out-of-memory point does not stop the run: it gets a `crash` or `oom` row and the record says why.
- An Isaac Sim start-up crash (no row, the log stops before the scene is built) is retried once and listed in
  `retried_points.txt`.
- Run again with the same name before a record exists and the run resumes: finished points are skipped.
- In the container, the GPU check sees only the container's processes. Run `nvidia-smi` on the host first.

Next: training, headless and with the Isaac Sim window → [TRAINING](TRAINING.md) (planned workflow until S2).
