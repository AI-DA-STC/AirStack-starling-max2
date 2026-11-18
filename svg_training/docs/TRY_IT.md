READ · TRAINING SIMULATOR ONLY: five levels of trying it yourself, from watching clips to repeating our ladder rows.

# Try it

**For** the NUS team and anyone with a fresh clone. Start at level A or B; each level adds one thing you need. Every
command has a *needs* badge, and the table says which commands we ran from a fresh clone. Nothing here flies a drone.
Words in *italics* are in the [glossary](GLOSSARY.md).

| Badge | Means |
|---|---|
| `none` | the clone and Python only; any laptop, no GPU |
| `GPU` | an NVIDIA GPU (driver 580 or newer, 12 GB or more) |
| `Isaac` | NVIDIA Isaac Lab 2.3.2 on Isaac Sim 5.1.0 (a large install: [GETTING_STARTED](GETTING_STARTED.md)) |
| `your NUS clone` | your `area-denial-continuous-space-self-play` checkout (commit `2d2b904`) and its checkpoints |
| `lab only` | files that exist only on the lab's machines; you cannot run it, and the page says what you get instead |

| Level | What you do | Needs | Time (CPU) | Verified from a fresh clone |
|---|---|---|---|---|
| [A](#a-watch-the-games) | watch the games | `none` | 5 min | yes |
| [B](#b-a-cpu-laptop-install-run-the-game-score-a-strategy-run-the-tests) | install, run the tests, score a strategy, train for seconds | `none` | ~5 min + ~10 min of tests | yes, 19 Nov 2026: 1,069 passed, 52 skipped, 0 failed |
| [C](#c-one-nvidia-gpu-the-same-at-full-size) | the same at full size | `GPU` | ~1 h | not yet |
| [D](#d-repeat-our-ladder-rows) | repeat our ladder rows from our PROVISIONAL files | `none` | 30 s to 2 min per row 1 run | yes, 19 Nov 2026 (row 1) |
| [D′](#d-rebuild-the-files-from-your-clone) | rebuild those files from your own clone | `your NUS clone` | minutes | partly (18 Nov 2026, CPU) |
| [E](#e-isaac-lab-row-6-and-the-clips) | the Isaac Lab row and its clips | `GPU` `Isaac` | hours | not yet |

What "verified" means: on 19 November 2026 the commands of B and D ran from a fresh clone of this branch, CPU only
(`CUDA_VISIBLE_DEVICES=""`), in a plain Python 3.11 environment, with an empty home folder (so none of the lab's
files could help). The machine was the lab's 32-thread workstation; a laptop will be slower than the times here.

## A. Watch the games

`none` · 5 min · verified. Open [media/nus/README.md](media/nus/README.md) in a browser (GitHub shows the GIFs inline).
Start with these four:

| Clip | What it shows |
|---|---|
| [G19 holds S20 in your game](media/nus/nus_selfplay_s2_g19_vs_s2_s20.gif) | your 2-D game, your renderer: the Guard holds for 200 steps |
| [row 4: hold](media/nus/phase4/row_4/G19_vs_S20_hold.mp4) → [row 5: Strike win](media/nus/phase4/row_5/G19_vs_S20_strike_win.mp4) | the same start, before and after drones are free in height |
| [Isaac Lab: a Strike drone reaches the zone](media/nus/isaac/g19_vs_s20_strike_win_1.gif) | G19 v S20 on rigid-body Starlings (row 6) |
| [Isaac Lab: a parked Guard team holds](media/nus/isaac/parked_vs_s20_hold_1.gif) | a Guard team that stands still holds S20 for 120 s (row 6) |

## B. A CPU laptop: install, run the game, score a strategy, run the tests

`none` · verified 19 Nov 2026. Nothing here learns a strategy; it proves the pipe works on your machine.

**B1 · `none` · Get the code and make an environment beside it.** Keep the environment *outside* the clone: a folder
inside it is not git-ignored, and the privacy tests scan every file git would add.
```bash
mkdir svg-try && cd svg-try
git clone https://github.com/AI-DA-STC/AirStack-starling-max2.git repo     # 1.7 GB
unset PYTHONPATH                     # only if your shell sources ROS 2: its packages leak into pip otherwise
uv venv -p 3.11 venv
uv pip install -p venv/bin/python --extra-index-url https://download.pytorch.org/whl/cpu \
    --index-strategy unsafe-best-match -e "repo/svg_training[test]"
P=$PWD/venv/bin/python
cd repo/svg_training
```
With plain pip instead of [uv](https://docs.astral.sh/uv/): `python3.11 -m venv venv && venv/bin/python -m pip install
--extra-index-url https://download.pytorch.org/whl/cpu -e "repo/svg_training[test]"`. The extra index gives the CPU
build of PyTorch (the default is the much larger CUDA build). Must see: the install ends without an error (2 s with a
warm uv cache, 41 s with plain pip; a cold first install was not timed). We verified with a local clone of the same
commit.

**B2 · `none` · Install our PROVISIONAL NUS files** (0.1 s; needed for D, and it lets 10 more NUS tests run).
```bash
scripts/nus_install_provisional.sh             # --dry-run to preview
```
Must see: `installed: 38 file(s) copied`. It checks every sha256 in `nus_provisional/SHA256SUMS`, then copies the files
into the git-ignored `configs/local/` and `runs/nus_port/`; it refuses to overwrite a different file unless `--force`.
What the files are: [nus_provisional/README.md](../nus_provisional/README.md).

**B3 · `none` · Run the tests** (about 10 min).
```bash
OMP_NUM_THREADS=4 $P -m pytest -q -p no:cacheprovider -rs
```
Must see: no `failed` in the last line. We saw **1,069 passed, 52 skipped, 0 failed**. A skip is not a pass; each names
its reason:

| Skipped | Why | To run them |
|---|---|---|
| 32 | no CUDA GPU | an NVIDIA GPU |
| 9 | Isaac Sim or Isaac Lab not switched on or not installed | Isaac Lab, then `SVG_ISAAC_TESTS=1` |
| 4 | NUS's code or our large Phase 5 exports absent | your NUS clone (`SVG_NUS_CLONE=<clone>`) and NUS's JAX environment |
| 6 | files that exist only on the lab's machines (machine layout, private files, a recorded filter state) | `lab only` |
| 1 | a bit-level fingerprint recorded with torch 2.7.0 and skrl 2.1.0 | the exact versions (below) |

Without B2, 10 more NUS tests skip ("fixtures or local files absent"). These tests also run the code blocks of
[PLUG_IN](PLUG_IN.md), so its examples work on your install. On a shared or busy machine keep `OMP_NUM_THREADS=4`:
PyTorch otherwise takes every core.

**B4 · `none` · Score a strategy** (10 s).
```bash
$P scripts/score.py --guard guard_field --strike strike_straight,strike_flank --sizes 2v1 --presets pure \
    --games-per-band 100 --no-local --out runs/try_score
```
Must see: a note that no CUDA GPU is visible, so it runs on the CPU (`--device auto`, the default); then
`runs/try_score/scores.md`, one hold rate per arena size band (three bands; in the large band we saw 0.8 against `strike_straight` and 0.96 against
`strike_flank`; the other two bands read higher). Your own strategy goes in the same way: [PLUG_IN](PLUG_IN.md#plug-a-strategy-in). Keep
`--presets pure` on a CPU: the `starling` preset (our drone model and safety filter) is many times slower.

**B5 · `none` · Train for a few seconds** (7 s; a pipe test, never a result).
```bash
$P scripts/train_standin.py --seed 1 --name try_smoke --smoke
```
Must see: `runs/try_smoke/` with `agent.pt`, `interface.toml`, `curve.json`, `train_result.json` (`"smoke": true`,
`"device": "cpu"`) and TensorBoard files.

**Exact versions.** Use `requirements-exact.txt` to get the versions our records were made with (torch 2.7.0, skrl
2.1.0, numpy 1.26.0, …); the floating install of B1 is newer (we got torch 2.15.0 and skrl 2.1.2), and one test, which
compares a training run bit for bit, skips there. Verified 19 Nov 2026 with plain pip (41 s, warm cache): that test runs
and passes; the full suite was not re-run on these versions.
```bash
python3.11 -m venv venv
venv/bin/python -m pip install --extra-index-url https://download.pytorch.org/whl/cpu -r repo/svg_training/requirements-exact.txt \
    -e "repo/svg_training[test]"
```

## C. One NVIDIA GPU: the same at full size

`GPU` · not yet verified from a fresh clone. Install as B1 with the CUDA build (`--extra-index-url
https://download.pytorch.org/whl/cu128`); `--device auto` then picks the GPU. Then:
```bash
$P scripts/score.py --guard guard_field --strike strike_straight,strike_flank --sizes 2v1 --presets pure,starling \
    --no-local --out runs/try_score_full
$P scripts/train_standin.py --seed 1 --name <new name>                      # pure rules, 45 min cap
$P scripts/train_standin.py --seed 1 --name <new name> --motion starling    # our drone model
$P -m tensorboard.main --logdir runs/
```
Expect 1,000 games per band. The stand-in trainer is a pipe test: on our Isaac Lab drones its Guards learned almost
nothing (T14, [S2B_RESULTS §5](S2B_RESULTS.md#5-the-stand-in-trainer)). On a GPU the test
`test_t2_scenes_t8_setting_cuda` shows as `xfailed`: it is an expected failure (the filter's GPU answer depends on the
batch size; [NUS_RESULTS Q3](NUS_RESULTS.md#q3-what-does-each-drone-limit-do)).

## D. Repeat our ladder rows

`none` · verified 19 Nov 2026 for row 1, CPU. After B2 every core pair runs from our PROVISIONAL files: the converted
G19, S20, P3G and P3S (trained by us with your code, 8 generations, hangar set-up) and our settings and starts. Your
own retraining would give a different G19 and S20 (training on a GPU is not repeatable bit for bit), so a repeat agrees
within intervals, not game by game.

**D1 · `none` · Our converted P3G and P3S against T16's starts: the one exact check** (27 s).
```bash
$P scripts/nus_phase4.py --w2-replay
```
Must see: `"games_differ_from_play_arm": 0` for both teams, `"reached": 46` (Guard arm) and `1000` (Strike arm),
`"equal": true`: the same counts as the conversion record (T16).

**D2 · `none` · Row 1, cut down, with clips** (23 s).
```bash
$P scripts/nus_phase4.py --row 1 --pairs G19:S20,P3G:ApfStrike --games 50 --device cpu --out runs/p4_try
```
Must see: `runs/p4_try/` with `scores.json`, `scores.md`, `per_game.npz` and top-down clips in `videos/`. A smoke
run, not a result. `--out` must lie under `runs/`. A row folder is never overwritten: delete `runs/p4_try/` to run it
again. The clips need no system `ffmpeg` (the `imageio-ffmpeg` package's own copy is used); `--no-videos` skips them.

**D3 · `none` · Row 1 in full: 12 pairs × 1,000 games** (97 s on our CPU).
```bash
$P scripts/nus_phase4.py --row 1 --device cpu
```
Must see: `runs/nus_port/phase4/row_1/scores.json`. Against our row 1 (GPU, [T18 record](../records/2026-11-18_nus_phase4_rung1_record.md)):
7 of the 12 pairs gave the same count; 5 differed by 1–3 of 1,000 games, each inside the record's Wilson 95 % interval
(G19 v S20: 10 here, 9 in the record). The same 5 differences appear with torch 2.7.0; likely causes, not separated:
CPU against GPU, or an earlier version of `configs/nus_phase4.toml` that rows 1–3 ran with. The script refuses a
finished row: delete `runs/nus_port/phase4/row_1/` to run it again.

**D4 · `none` / `GPU` · Other rows** (not yet verified from a fresh clone).
```bash
$P scripts/nus_phase4.py --row 2.1      # then 2.2, 2, 3a, 3, 4, 5a, 5; add --device cuda on a GPU
```
Rows 2.1–3 take minutes on a GPU. Rows 4, 5a and 5 took 2–6 h each on our RTX 5090: do not run them on a CPU. A row
estimated above 2 h stops (exit 4) until you add `--accept-long`. `scripts/make_nus_phase4_figures.py` redraws the
figure only when all ten rows have `scores.json`; otherwise it refuses (exit 2) and leaves the committed figure alone.

## D′. Rebuild the files from your clone

`your NUS clone` · partly verified (18 Nov 2026, CPU, a fresh clone of an earlier commit): D′2 to D′4 gave files
byte-identical to ours. Use a clone where B2 has **not** run, or the scripts find our files in place.

**D′1 · Names.** `J` is the Python of an environment where your code runs (D′2 needs `hydra` and `omegaconf` from it);
`scripts/workstation/setup_nus_jax.sh --cpu <clone>` builds a CPU one (checked by its `--dry-run` test only).
```bash
C=<your clone at 2d2b904>
J="env PYTHONNOUSERSITE=1 JAX_PLATFORMS=cpu WANDB_MODE=disabled PYTHONPATH=source <your env>/bin/python"
G=<fixed-opponent Guard checkpoint, hangar set-up>    S=<fixed-opponent Strike checkpoint, hangar set-up>
```
The hangar set-up is your `train_mappo_self_play_mpe` config with `+environment.env.physics.spawn_distance=8.0
environment.env.physics.defender_boundary=8.0` ([TRAINING, NUS jobs](TRAINING.md#nus-jobs)).

**D′2 · `your NUS clone` · The rules file** (0.2 s; verified).
```bash
$J scripts/nus_make_local_rules.py --clone $C --config $C/ma_skills/config/train_self_play.yaml --out configs/local/nus_rules.toml
```
Must see: a sha256 starting `dd22cc28` (ours).

**D′3 · `your NUS clone` · The deploy file, then the converted policies** (verified; the converter reads the deploy file).
```bash
$P scripts/nus_make_local_deploy.py --clone $C --geometry-from $G --metres-per-unit 0.4 --seconds-per-step 0.6 \
    --hold-ticks 12 --flying-height-m 1.2 --guard-weights hangar_guard_fixed_apf --strike-weights hangar_strike_fixed_apf \
    --out configs/local/nus_deploy.toml
$P scripts/nus_convert_checkpoint.py --checkpoint $G --team guard  --name hangar_guard_fixed_apf
$P scripts/nus_convert_checkpoint.py --checkpoint $S --team strike --name hangar_strike_fixed_apf
```
Must see: `nus_deploy.toml` sha256 starting `c248c6be` (ours); `runs/nus_port/weights/hangar_*_fixed_apf/`.

**D′4 · `none` · The hangar file and the paired starts** (1.4 s; verified).
```bash
cp configs/nus_hangar.template.toml configs/local/nus_hangar.toml    # then set arena_side_m = 7.5 in it
$P scripts/nus_phase4.py --make-starts
```
Must see: `runs/nus_port/phase4/starts.npz`, sha256 starting `40c8cc59` (ours).

**D′5 · `your NUS clone` · G19 and S20** (not yet verified). From your seed-2 self-play run, convert archive entries
`0019_defender` and `0020_attacker`, then write their deploy file, which must equal `nus_deploy.toml` in every key but
the two weights folders:
```bash
$P scripts/nus_convert_checkpoint.py --checkpoint <seed 2 run>/archive/0019_defender --team guard  --name ref_s2_g19_guard
$P scripts/nus_convert_checkpoint.py --checkpoint <seed 2 run>/archive/0020_attacker --team strike --name ref_s2_g20_strike
$P scripts/nus_make_local_deploy.py --clone $C --geometry-from <seed 2 run>/archive/0019_defender --metres-per-unit 0.4 \
    --seconds-per-step 0.6 --hold-ticks 12 --flying-height-m 1.2 --guard-weights ref_s2_g19_guard \
    --strike-weights ref_s2_g20_strike --same-as configs/local/nus_deploy.toml --out configs/local/nus_deploy_ref.toml
```
Ours: `nus_deploy_ref.toml` sha256 starting `6d71c111`. Then run the rows as in D2–D4.

## E. Isaac Lab: row 6 and the clips

`GPU` `Isaac` · not yet verified from a fresh clone. Install Isaac Lab ([GETTING_STARTED](GETTING_STARTED.md): a
container of about 26 GB, or a host install with hand fixes; expect 1–2 h). Then, with B2 done:
```bash
scripts/isaac_preflight.sh --approved-headless        # must exit 0: no other large GPU job, no window over remote desktop
$P scripts/nus_phase4.py --row 6 --headless --device cuda --accept-long
```
Our row 6 took 2.1 h on an RTX 5090 (T24). The camera clips of [media/nus](media/nus/README.md) come from
`scripts/nus_isaac_clips.py`. Never open the Isaac Sim window over a remote desktop.

## Not here yet

- Our copy of your training method (Phase 5, [NUS_RESULTS Q6](NUS_RESULTS.md#q6-does-our-copy-of-your-training-method-behave-like-yours)):
  its scripts are in the repository and its test is calibrated (C0 PASS), but our own seeds (5.1) have no result yet.
  We will add a level for it when they do.
- Our own trainer for the game and the export to the drones are not built. Today the trainers are the stand-in (a pipe
  test) and your code.
