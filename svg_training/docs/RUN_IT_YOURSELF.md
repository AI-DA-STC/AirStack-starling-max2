READ · TRAINING SIMULATOR ONLY: six levels of running it yourself, from watching clips to repeating the six tests and training the STE Guard policy.

# Run it yourself

**For** NUS researchers and anyone with a fresh clone. **STE**: the lab that wrote this repository. Start at level A
or B; each level adds one thing it needs. Every command has a *needs* badge, and the table says which commands were
run from a fresh clone. Nothing here flies a drone. NUS's `defender` is the defender (Guard team) here, NUS's `attacker`
the attacker (Strike team); from here on, Guard and Strike. Terms in *italics* are in the [glossary](GLOSSARY.md); the
policies (G19, S20, P3G, P3S, the APF defender and attacker, the Parked Guard) are defined in
[glossary, policies](GLOSSARY.md#policies), and Tests 1–6 in [glossary, the six tests](GLOSSARY.md#the-six-tests).
The scripts number the tests as rows (`--row 1` = Test 1).

| Badge | Means |
|---|---|
| `none` | the clone and Python only; any laptop, no GPU |
| `GPU` | an NVIDIA GPU (driver 580 or newer, 12 GB or more) |
| `Isaac` | NVIDIA Isaac Lab 2.3.2 on Isaac Sim 5.1.0 (a large install: [full install guide](GETTING_STARTED.md)) |
| `NUS clone` | a checkout of NUS's `area-denial-continuous-space-self-play` (commit `2d2b904`) and its checkpoints |
| `lab only` | files that exist only on STE's machines; the page says what is available instead |

| Level | What | Needs | Time (CPU) | Verified from a fresh clone |
|---|---|---|---|---|
| [A](#a-watch-the-games) | watch the games | `none` | 5 min | yes |
| [B](#b-a-cpu-laptop-install-run-the-game-score-a-strategy-run-the-tests) | install, run the tests, score a strategy, train for seconds | `none` | ~5 min + ~10 min of tests | yes, 19 Nov 2026: 1,069 passed, 52 skipped, 0 failed |
| [C](#c-one-nvidia-gpu-the-same-at-full-size) | the same at full size | `GPU` | ~1 h | not yet |
| [D](#d-repeat-the-six-tests) | repeat the six tests from the PROVISIONAL files | `none` | 30 s to 2 min per Test 1 run | yes, 19 Nov 2026 (Test 1) |
| [D′](#d-rebuild-the-files-from-a-nus-clone) | rebuild those files from a NUS clone | `NUS clone` | minutes | partly (18 Nov 2026, CPU) |
| [E](#e-isaac-lab-test-6-and-the-clips) | Test 6 (Isaac Lab physics drones) and its clips | `GPU` `Isaac` | hours | not yet |
| [F](TRAIN_A_GUARD.md) | train the STE Guard policy: [training recipe](TRAIN_A_GUARD.md) | `none` for the CPU check, `GPU` for the run | 2 min (CPU check); 2.1 h on an RTX 5090 | CPU check only |

What "verified" means: on 19 November 2026 the commands of B and D ran from a fresh clone of this branch, CPU only
(`CUDA_VISIBLE_DEVICES=""`), in a plain Python 3.11 environment, with an empty home folder (so none of STE's files
could help). The machine was STE's 32-thread workstation; a laptop will be slower than the times here.

## A. Watch the games

`none` · 5 min · verified. Open [videos of the NUS port](media/nus/README.md) in a browser (GitHub shows the GIFs
inline). Four to start with:

| Clip | What it shows |
|---|---|
| [G19 vs S20 · NUS 2-D game (JAX) · Guard holds](media/nus/nus_selfplay_s2_g19_vs_s2_s20.gif) | NUS's game and renderer: the Guard holds for 200 steps |
| [G19 vs S20 · Test 4 · Guard holds](media/nus/phase4/row_4/G19_vs_S20_hold.mp4) → [G19 vs S20 · Test 5 · Strike reaches the zone](media/nus/phase4/row_5/G19_vs_S20_strike_win.mp4) | the same start, before and after drones are free in height |
| [G19 vs S20 · Test 6: Isaac Lab physics drones · Strike reaches the zone](media/nus/isaac/g19_vs_s20_strike_win_1.gif) | rigid-body Starling models in Isaac Lab |
| [Parked Guard vs S20 · Test 6: Isaac Lab physics drones · Guard holds](media/nus/isaac/parked_vs_s20_hold_1.gif) | a Guard team that stands still holds S20 for 120 s |

## B. A CPU laptop: install, run the game, score a strategy, run the tests

`none` · verified 19 Nov 2026. Nothing here learns a strategy; it shows that the pipeline works on the machine.

**B1 · `none` · Get the code and make an environment beside it.** Keep the environment *outside* the clone: a folder
inside it is not git-ignored, and the privacy tests scan every file git would add.
```bash
mkdir svg-try && cd svg-try
git clone https://github.com/AI-DA-STC/AirStack-starling-max2.git repo     # 1.7 GB
unset PYTHONPATH                     # only if the shell sources ROS 2: its packages leak into pip otherwise
uv venv -p 3.11 venv
uv pip install -p venv/bin/python --extra-index-url https://download.pytorch.org/whl/cpu \
    --index-strategy unsafe-best-match -e "repo/svg_training[test]"
P=$PWD/venv/bin/python
cd repo/svg_training
```
With plain pip instead of [uv](https://docs.astral.sh/uv/): `python3.11 -m venv venv && venv/bin/python -m pip install
--extra-index-url https://download.pytorch.org/whl/cpu -e "repo/svg_training[test]"`. The extra index gives the CPU
build of PyTorch (the default is the much larger CUDA build). Must see: the install ends without an error (2 s with a
warm uv cache, 41 s with plain pip; a cold first install was not timed). Verified with a local clone of the same
commit.

**B2 · `none` · Install the PROVISIONAL NUS-port files** (0.1 s; needed for D and F, and it lets 10 more NUS tests run).
```bash
scripts/nus_install_provisional.sh             # --dry-run to preview
```
Must see: `installed: 38 file(s) copied`. It checks every sha256 in `nus_provisional/SHA256SUMS`, then copies the files
into the git-ignored `configs/local/` and `runs/nus_port/`; it refuses to overwrite a different file unless `--force`.
The *PROVISIONAL* files are the converted G19, S20, P3G and P3S (trained by STE with NUS's code) and STE's settings
and starts, committed only so the numbers can be repeated: [what the files are](../nus_provisional/README.md).

**B3 · `none` · Run the tests** (about 10 min).
```bash
OMP_NUM_THREADS=4 $P -m pytest -q -p no:cacheprovider -rs
```
Must see: no `failed` in the last line. Seen on 19 Nov 2026: **1,069 passed, 52 skipped, 0 failed**. A skip is not a
pass; each names its reason:

| Skipped | Why | To run them |
|---|---|---|
| 32 | no CUDA GPU | an NVIDIA GPU |
| 9 | Isaac Sim or Isaac Lab not switched on or not installed | Isaac Lab, then `SVG_ISAAC_TESTS=1` |
| 4 | NUS's code or STE's large Phase 5 exports absent | a NUS clone (`SVG_NUS_CLONE=<clone>`) and NUS's JAX environment |
| 6 | files that exist only on STE's machines (machine layout, private files, a recorded filter state) | `lab only` |
| 1 | a bit-level fingerprint recorded with torch 2.7.0 and skrl 2.1.0 | the exact versions (below) |

Without B2, 10 more NUS tests skip ("fixtures or local files absent"). These tests also run the code blocks of
[plug in your code](PLUG_IN_YOUR_CODE.md), so its examples work on the install. On a shared or busy machine keep
`OMP_NUM_THREADS=4`: PyTorch otherwise takes every core. Under heavy load one timing test in
`tests/test_record_steps.py` can fail; it passes when run on its own (`$P -m pytest -q tests/test_record_steps.py`: 71
passed in a re-test, 19 Nov).

**B4 · `none` · Score a strategy** (10 s).
```bash
$P scripts/score.py --guard guard_field --strike strike_straight,strike_flank --sizes 2v1 --presets pure \
    --games-per-band 100 --no-local --out runs/try_score
```
Must see: a note that no CUDA GPU is visible, so it runs on the CPU (`--device auto`, the default); then
`runs/try_score/scores.md`, one hold rate per arena size band (three bands; in the large band 0.8 against
`strike_straight` and 0.96 against `strike_flank` were seen; the other two bands read higher). `guard_field`,
`strike_straight` and `strike_flank` are *STE scripted Guards and Strikes* (hand-written, no training). Another
strategy goes in the same way: [plug in a strategy](PLUG_IN_YOUR_CODE.md#plug-a-strategy-in). Keep `--presets pure`
on a CPU: the `starling` preset (the STE drone model and the safety filter) is many times slower.

**B5 · `none` · Train for a few seconds** (7 s; a pipe test, never a result).
```bash
$P scripts/train_standin.py --seed 1 --name try_smoke --smoke
```
Must see: `runs/try_smoke/` with `agent.pt`, `interface.toml`, `curve.json`, `train_result.json` (`"smoke": true`,
`"device": "cpu"`) and TensorBoard files.

**Exact versions.** `requirements-exact.txt` gives the versions the records were made with (torch 2.7.0, skrl 2.1.0,
numpy 1.26.0, …); the floating install of B1 is newer (torch 2.15.0 and skrl 2.1.2 were installed), and one test,
which compares a training run bit for bit, skips there. Verified 19 Nov 2026 with plain pip (41 s, warm cache): that
test runs and passes; the full suite was not re-run on these versions.
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
$P scripts/train_standin.py --seed 1 --name <new name> --motion starling    # the STE drone model
$P -m tensorboard.main --logdir runs/
```
Expect 1,000 games per band. On the S2 game the stand-in trainer is a pipe test: on the Isaac Lab drones its Guards
learned almost nothing (T14, [stand-in trainer results](S2B_RESULTS.md#5-the-stand-in-trainer)); the STE Guard policy
of level F comes from the same trainer with other settings. On a GPU the test `test_t2_scenes_t8_setting_cuda` shows
as `xfailed`: an expected failure (the filter's GPU answer depends on the batch size;
[the filter caveat](WHAT_WE_FOUND.md#3-six-tests-towards-ste-drones)).

## D. Repeat the six tests

`none` · verified 19 Nov 2026 for Test 1, CPU. After B2 every core pair runs from the PROVISIONAL files: the converted
G19, S20, P3G and P3S (trained by STE with NUS's code, 8 generations, hangar set-up) and STE's settings and starts.
A retraining by NUS would give a different G19 and S20 (training on a GPU is not repeatable bit for bit), so a repeat
agrees within intervals, not game by game. The scripts call a test a row: `--row 1` = Test 1.

**D1 · `none` · The converted P3G and P3S against T16's starts: the one exact check** (27 s).
```bash
$P scripts/nus_phase4.py --w2-replay
```
Must see: `"games_differ_from_play_arm": 0` for both teams, `"reached": 46` (Guard arm) and `1000` (Strike arm),
`"equal": true`: the same counts as the conversion record (T16).

**D2 · `none` · Test 1, cut down, with clips** (23 s).
```bash
$P scripts/nus_phase4.py --row 1 --pairs G19:S20,P3G:ApfStrike --games 50 --device cpu --out runs/p4_try
```
Must see: `runs/p4_try/` with `scores.json`, `scores.md`, `per_game.npz` and top-down clips in `videos/`. A smoke
run, not a result. `ApfStrike` is the APF attacker. `--out` must lie under `runs/`. A test folder is never
overwritten: delete `runs/p4_try/` to run it again. The clips need no system `ffmpeg` (the `imageio-ffmpeg`
package's own copy is used); `--no-videos` skips them.

**D3 · `none` · Test 1 in full: 12 pairs × 1,000 games** (97 s on STE's CPU).
```bash
$P scripts/nus_phase4.py --row 1 --device cpu
```
Must see: `runs/nus_port/phase4/row_1/scores.json`. Against Test 1 of record (GPU, [T18 record](../records/2026-11-18_nus_phase4_rung1_record.md)):
7 of the 12 pairs gave the same count; 5 differed by 1–3 of 1,000 games, each inside the record's Wilson 95 % interval
(G19 v S20: 10 here, 9 in the record). The same 5 differences appear with torch 2.7.0; likely causes, not separated:
CPU against GPU, or an earlier version of `configs/nus_phase4.toml` that Tests 1–3 ran with. The script refuses a
finished test: delete `runs/nus_port/phase4/row_1/` to run it again.

**D4 · `none` / `GPU` · The other tests** (not yet verified from a fresh clone).
```bash
$P scripts/nus_phase4.py --row 2.1      # then 2.2, 2, 3a, 3, 4, 5a, 5; add --device cuda on a GPU
```
Sub-tests 2.1 to Test 3 take minutes on a GPU. Tests 4, 5a and 5 took 2–6 h each on STE's RTX 5090: do not run them
on a CPU. A test estimated above 2 h stops (exit 4) until `--accept-long` is added.
`scripts/make_nus_phase4_figures.py` redraws the figure only when all ten tests and sub-tests have `scores.json`;
otherwise it refuses (exit 2) and leaves the committed figure alone.

## D′. Rebuild the files from a NUS clone

`NUS clone` · partly verified (18 Nov 2026, CPU, a fresh clone of an earlier commit): D′2 to D′4 gave files
byte-identical to STE's. Use a clone where B2 has **not** run, or the scripts find the PROVISIONAL files in place.

**D′1 · Names.** `J` is the Python of an environment where NUS's code runs (D′2 needs `hydra` and `omegaconf` from it);
`scripts/workstation/setup_nus_jax.sh --cpu <clone>` builds a CPU one (checked by its `--dry-run` test only).
```bash
C=<NUS clone at 2d2b904>
J="env PYTHONNOUSERSITE=1 JAX_PLATFORMS=cpu WANDB_MODE=disabled PYTHONPATH=source <NUS env>/bin/python"
G=<fixed-opponent Guard checkpoint, hangar set-up>    S=<fixed-opponent Strike checkpoint, hangar set-up>
```
The hangar set-up is NUS's `train_mappo_self_play_mpe` config with `+environment.env.physics.spawn_distance=8.0
environment.env.physics.defender_boundary=8.0` ([training scripts, NUS jobs](TRAINING.md#nus-jobs)).

**D′2 · `NUS clone` · The rules file** (0.2 s; verified).
```bash
$J scripts/nus_make_local_rules.py --clone $C --config $C/ma_skills/config/train_self_play.yaml --out configs/local/nus_rules.toml
```
Must see: a sha256 starting `dd22cc28` (STE's).

**D′3 · `NUS clone` · The deploy file, then the converted policies** (verified; the converter reads the deploy file).
```bash
$P scripts/nus_make_local_deploy.py --clone $C --geometry-from $G --metres-per-unit 0.4 --seconds-per-step 0.6 \
    --hold-ticks 12 --flying-height-m 1.2 --guard-weights hangar_guard_fixed_apf --strike-weights hangar_strike_fixed_apf \
    --out configs/local/nus_deploy.toml
$P scripts/nus_convert_checkpoint.py --checkpoint $G --team guard  --name hangar_guard_fixed_apf
$P scripts/nus_convert_checkpoint.py --checkpoint $S --team strike --name hangar_strike_fixed_apf
```
Must see: `nus_deploy.toml` sha256 starting `c248c6be` (STE's); `runs/nus_port/weights/hangar_*_fixed_apf/` (P3G
and P3S).

**D′4 · `none` · The hangar file and the paired starts** (1.4 s; verified).
```bash
cp configs/nus_hangar.template.toml configs/local/nus_hangar.toml    # then set arena_side_m = 7.5 in it
$P scripts/nus_phase4.py --make-starts
```
Must see: `runs/nus_port/phase4/starts.npz`, sha256 starting `40c8cc59` (STE's).

**D′5 · `NUS clone` · G19 and S20** (not yet verified). From the seed-2 self-play run, convert archive entries
`0019_defender` and `0020_attacker`, then write their deploy file, which must equal `nus_deploy.toml` in every key but
the two weights folders:
```bash
$P scripts/nus_convert_checkpoint.py --checkpoint <seed 2 run>/archive/0019_defender --team guard  --name ref_s2_g19_guard
$P scripts/nus_convert_checkpoint.py --checkpoint <seed 2 run>/archive/0020_attacker --team strike --name ref_s2_g20_strike
$P scripts/nus_make_local_deploy.py --clone $C --geometry-from <seed 2 run>/archive/0019_defender --metres-per-unit 0.4 \
    --seconds-per-step 0.6 --hold-ticks 12 --flying-height-m 1.2 --guard-weights ref_s2_g19_guard \
    --strike-weights ref_s2_g20_strike --same-as configs/local/nus_deploy.toml --out configs/local/nus_deploy_ref.toml
```
STE's `nus_deploy_ref.toml` has a sha256 starting `6d71c111`. Then run the tests as in D2–D4.

## E. Isaac Lab: Test 6 and the clips

`GPU` `Isaac` · not yet verified from a fresh clone. Install Isaac Lab ([full install guide](GETTING_STARTED.md): a
container of about 26 GB, or a host install with hand fixes; expect 1–2 h). Then, with B2 done:
```bash
scripts/isaac_preflight.sh --approved-headless        # must exit 0: no other large GPU job, no window over remote desktop
$P scripts/nus_phase4.py --row 6 --headless --device cuda --accept-long
```
Test 6 of record took 2.1 h on an RTX 5090 (T24). The camera clips of [videos of the NUS port](media/nus/README.md)
come from `scripts/nus_isaac_clips.py`. Never open the Isaac Sim window over a remote desktop.

## F. Train the STE Guard policy

The recipe for the one training result, with a CPU check that runs in about 2 minutes:
[training recipe](TRAIN_A_GUARD.md).

## Not here yet

- The STE port of NUS's training method (PyTorch) ([training method](WHAT_WE_FOUND.md#6-ste-port-of-nus-training-method-no-result-yet)):
  its scripts are in the repository and its test is calibrated (C0 PASS), but its own seeds (stage 5.1) have no
  result yet. A level will be added when they do.
- STE's own trainer for the game (beyond the stand-in trainer of level F) and the export to the drones are not built.
