REFERENCE · every training script and flag, our own and the NUS jobs. To try things first: [how to run it yourself](RUN_IT_YOURSELF.md).

# Training a policy: headless and with the Isaac Sim window

> **What trains today.** The stand-in trainer (`scripts/train_standin.py`, a pipe test: [S2B_RESULTS §5](S2B_RESULTS.md#5-the-stand-in-trainer)); NUS's own JAX
> trainer ([NUS jobs](#nus-jobs)); and, in progress, our PyTorch copy of NUS's method (Phase 5,
> [what we did, day by day, §12](WHAT_WE_DID_DAY_BY_DAY.md#12-phase-5-training-in-ste-conditions-in-progress)). Our own `scripts/train.py` and
> `scripts/evaluate.py` are not built: commands marked `# planned` do not exist. Terms: [glossary](GLOSSARY.md).

*Headless* means running with no window on screen. It is faster, and it is the normal way to train. A *policy* is
the trained strategy. A *container* is a sealed copy of the software that runs the same way on every machine.

Every command runs from the `svg_training/` folder of your clone.

## 1. What exists today

The table shows what works now and which build step brings the rest.

| Item | Where it stands | Arrives with |
|---|---|---|
| Container image, shell in it, tests | works: [GETTING_STARTED](GETTING_STARTED.md) steps 4 and 6, `docker/run.sh` opens a shell | S0 |
| Training libraries in the image | present: `skrl`, `rsl_rl`, `isaaclab_tasks`, `isaaclab_rl`, `tensorboard` (checked 15 Nov) | already there |
| S0 benchmark, headless | works: [GETTING_STARTED, the S0 benchmark](GETTING_STARTED.md#the-s0-benchmark) | S0 |
| Isaac Sim with a window, on the host | available: Isaac Lab's own commands (§5) on NVIDIA's example tasks, not our game; not yet run on the laptop or the 5090 | already there |
| Our game and rewards | built ([plug in your code](PLUG_IN_YOUR_CODE.md)) | S2 |
| `scripts/train.py`, `scripts/evaluate.py` | **not built** | S3 or later |
| Our game on tier 2 (the only tier with an Isaac Sim window) | **planned** | S4 (S2 if the fallback of [DESIGN §7](DESIGN.md#7-environments-and-contact-tags) is taken) |
| A window from the container (X11 option in `docker/run.sh`) | **planned**, not scheduled | not scheduled |
| Export: policy file and `interface.toml` | **planned** | S5 |

## 2. Two ways to watch training

The table compares training without a window (headless) and with the Isaac Sim window.

| | Headless (normal) | With the Isaac Sim window |
|---|---|---|
| Games at once | as many as the GPU holds (thousands) | few (16–64): drawing them costs time and memory |
| Speed | fastest | much slower |
| You see | the terminal, TensorBoard curves, videos recorded headless | the drones flying, live |
| Use it for | all real training; every run of record | checking that the scene, starts and drones look right |
| Tier 1 (plain PyTorch, no Isaac) | always: tier 1 has no window | not possible; replay the policy on tier 2 instead (planned, S4) |
| Tier 2 (Isaac Lab) | yes: `--headless` | yes: leave out `--headless` |

Training runs headless ([STANDARDS §6](../STANDARDS.md#6-training-rules) rule 6). A run with the window is only for
looking. It never counts as a *run of record* (the official run whose numbers we keep). Most training uses *tier 1*,
the fast, simple drone model ([DESIGN §4](DESIGN.md#4-two-tiers-one-game)). You watch it through curves and replays.

## 3. Before you train

Check each row before a training run. A *gate* is a pass/fail check written before the run and never changed. A
*seed* is the starting number for the random draws: the same seed gives the same run. A sha256 *hash* is a
fingerprint of a file that changes if the file changes.

| Check | How |
|---|---|
| The GPU is free: no AirStack simulator, flight session, benchmark or other Isaac process | `nvidia-smi` and `docker ps` on the host (the container sees only its own processes) |
| The config is the approved one | `sha256sum configs/<config>.toml` matches the hash the owner approved; the start command refuses another (planned, S2; as `run_s0.sh` exit 65 today) |
| Gates are written | the step's `gates.toml` exists before the first run and is never edited ([STANDARDS §7](../STANDARDS.md#7-evaluation-and-gates)) |
| Seeds | every run fixes and records its seed; a claim that a method is better needs at least 3 seeds |
| Name and place | name `YYYY-MM-DD_s2_<label>`; output in `runs/<name>/` (not in git), record in `records/` ([STANDARDS §8](../STANDARDS.md#8-runs-and-records)) |
| Where you sit | anything that opens a window: at the machine or on Ethernet. Opening Isaac Sim over the remote desktop has crashed the laptop's (RTX 5070 Ti) WiFi firmware ([CLAUDE.md](../CLAUDE.md)) |

## 4. Headless training

**In the container** (the repository's way; image from [GETTING_STARTED](GETTING_STARTED.md) step 4):

```bash
nvidia-smi                                                       # on the host: GPU free
docker/run.sh '$SVG_PY scripts/train.py 2026-12-01_s2_guard_seed0 <approved sha256> --tier 1 --num-games 4096 --seed 0 --max-iterations 2000'   # planned (S2)
docker/run.sh svg-isaaclab -p scripts/train.py 2026-12-01_s2_t2_seed0 <approved sha256> --tier 2 --headless --num-games 1024 --seed 0   # planned (S4)
```

**On the host** (conda `env_isaaclab` and `~/IsaacLab`, as in [GETTING_STARTED](GETTING_STARTED.md) step 5). On a shell
that sources ROS (the 5090's does), run `unset PYTHONPATH` first in every terminal below
([GETTING_STARTED, hand fix 6](GETTING_STARTED.md#hand-fixes-after-the-setup-script)).

```bash
conda activate env_isaaclab
python scripts/train.py 2026-12-01_s2_guard_seed0 <approved sha256> --tier 1 --num-games 4096 --seed 0   # planned (S2)
~/IsaacLab/isaaclab.sh -p scripts/train.py <name> <approved sha256> --tier 2 --headless --num-games 1024 --seed 0   # planned (S4)
```

`scripts/train.py`, `--tier`, `--num-games` and `--max-iterations` are **planned** (fixed by the S2 plan); `--headless`
is Isaac Lab's own flag. The first training library we use is skrl ([DESIGN §6](DESIGN.md#6-training-recipe-for-use-1-starting-point-the-builder-may-change-it-with-evidence)).
A *checkpoint* is the policy saved part-way through training. TensorBoard is a web page that draws training curves.

The table lists what you see while training runs.

| While it runs | What you get |
|---|---|
| Terminal | skrl prints a progress bar over the training steps; Isaac Lab prints the log folder (`Logging experiment in directory: …`) |
| Curves | skrl writes TensorBoard files into its run folder (planned: `runs/<name>/`); open them with the block below, then `http://localhost:6006` |
| Checkpoints | with skrl's default (`auto`): `checkpoints/agent_<step>.pt` 10 times a run, plus `checkpoints/best_agent.pt` |
| Stop | Ctrl-C; the start command writes an `ABORTED` record (planned, as `run_s0.sh` does today) |
| Resume | `--checkpoint <file>` (planned for ours; exists in Isaac Lab's script). skrl loads the weights only; the step count starts again from 0 |

```bash
conda activate env_isaaclab && tensorboard --logdir runs/<name>   # on the host: the container publishes no port
```

TensorBoard is a web page, so viewing it over the remote desktop is safe; `runs/` is the same folder on both sides.
To compare runs side by side, point it at the whole folder: `tensorboard --logdir runs/`.

### What TensorBoard shows (planned for every training run, from S2b)

Every training run writes TensorBoard files into `runs/<run name>/` (owner, 16 November 2026; the S2b plan holds
the details). Version 2.20 is installed in `env_isaaclab`.

| Group | What it draws |
|---|---|
| skrl's own curves | reward, losses, learning rate, over training steps |
| `game/` | the game's numbers at each evaluation: how often the trained Guard team holds the zone against each scripted Strike behaviour, the share of games won by time-out, the closest Guard–Strike approach (3-D: minimum and 5th percentile), how often the collision filter changes a command, game-steps per second |
| text | the run's settings: game config hash, seed, simulator (PyTorch or Isaac Lab), rules preset |

Runs are logged to TensorBoard on the lab's own machines only; no cloud dashboard (Weights & Biases or similar) is
used, because NUS's source code stays off third-party services. NUS's settings and our results on NUS's code may be
published ([STANDARDS §2](../STANDARDS.md#2-wording)). The first run with these curves was the stand-in trainer in S2b.

**Practise the controls today** on NVIDIA's quadcopter example. It trains one drone to fly to a point. It is not
our game, and it has not yet been run this way on the laptop or the 5090. Isaac Lab writes `logs/` into the current folder, so
start in `runs/practice/`:

```bash
conda activate env_isaaclab
mkdir -p runs/practice && cd runs/practice
~/IsaacLab/isaaclab.sh -p ~/IsaacLab/scripts/reinforcement_learning/skrl/train.py \
    --task Isaac-Quadcopter-Direct-v0 --headless --num_envs 1024 --seed 0 --max_iterations 50
tensorboard --logdir logs          # curves; logs/skrl/quadcopter_direct/<date-time>_ppo_torch/
```

`--num_envs` is Isaac Lab's word for games. Other flags of that script: `--algorithm` (default `PPO`; `IPPO` or
`MAPPO` where a task ships a config for them), `--checkpoint`, `--ml_framework`, `--distributed` (several GPUs, through
`python -m torch.distributed.run`), and Hydra overrides such as `agent.seed=2024` or `env.<field>=<value>`.

## 5. Training with the Isaac Sim window

The table shows where the window works today.

| Where | Works today? | How |
|---|---|---|
| Host | yes, for Isaac Lab tasks; ours when tier 2 exists | the same command **without** `--headless`, with few games |
| Container | no: `docker/run.sh` passes no display (headless only, [docker/README](../docker/README.md)) | **planned** option, below |
| Another computer | to be tried | Isaac Sim livestreaming, below |

**Host, at the machine** (WiFi caution, §3):

```bash
conda activate env_isaaclab && mkdir -p runs/practice && cd runs/practice
~/IsaacLab/isaaclab.sh -s                                        # Isaac Sim alone, with a window
~/IsaacLab/isaaclab.sh -p ~/IsaacLab/scripts/reinforcement_learning/skrl/train.py \
    --task Isaac-Quadcopter-Direct-v0 --num_envs 32 --seed 0 --max_iterations 50
~/IsaacLab/isaaclab.sh -p scripts/train.py <name> <approved sha256> --tier 2 --num-games 32 --seed 0   # planned (S4)
```

Close the window or press Ctrl-C to stop. `--rendering_mode` picks a preset: `performance`, `balanced` (default), `quality`.

**Container with a window (planned option).** NVIDIA's own container does it with `docker/x11.yaml`: it passes
`DISPLAY`, `TERM` and `QT_X11_NO_MITSHM=1`, mounts `/tmp/.X11-unix`, and points `XAUTHORITY` at a temporary
`.xauth` file holding the display's cookie (copied with `xauth nlist` and `xauth nmerge`). A window option for
`docker/run.sh` would add the same. NVIDIA's guide calls its prebuilt image (ours is built on it) headless only,
yet shows an X11 command for it: untried until someone tests it.

**Livestreaming to another computer (not yet tried here).** Add `--livestream 2` (WebRTC on the local network;
`1` = public network, port 49100, address from `PUBLIC_IP`). It turns headless on by itself; you watch with
NVIDIA's *Isaac Sim WebRTC Streaming Client* on the other computer. From the container it also needs the network
option `docker/run.sh` does not set (planned, with the window option).

## 6. Watching a trained policy

```bash
python scripts/evaluate.py <name> --tier 1                     # planned (S2): scores against the gates
~/IsaacLab/isaaclab.sh -p scripts/evaluate.py <name> --tier 2 --num-games 16   # planned (S4): with the window
# works today, from runs/practice/ (host):
~/IsaacLab/isaaclab.sh -p ~/IsaacLab/scripts/reinforcement_learning/skrl/play.py --task Isaac-Quadcopter-Direct-v0 --num_envs 16
~/IsaacLab/isaaclab.sh -p ~/IsaacLab/scripts/reinforcement_learning/skrl/play.py --task Isaac-Quadcopter-Direct-v0 \
    --num_envs 16 --headless --video --video_length 200
```

The table gives the details of scoring and replay.

| Item | Detail |
|---|---|
| Scoring | at least 1,000 games per condition, rate with its 95 % interval, always headless ([STANDARDS §7](../STANDARDS.md#7-evaluation-and-gates)) |
| Which checkpoint `play.py` loads | from the newest run folder under `logs/skrl/<task folder>/`, the last file by name (`best_agent.pt` or the highest `agent_<step>.pt`); give `--checkpoint <file>` to be sure. `--real-time` plays at real speed |
| Video | `--video` turns on `--enable_cameras` by itself; `play.py` writes one clip to `<run folder>/videos/play/`; `train.py --video` writes one every `--video_interval` steps (default 2000) to `videos/train/`. Isaac Lab's guide says recording needs `ffmpeg` |
| Tier 1 policies | no Isaac window: rendered replays from our own code (planned, S2), or replay on tier 2 (planned, S4) |

## 7. After training

The table lists what follows a training run. The *record* is the written summary of a run. The *ledger* is the
list of all runs.

| Step | What |
|---|---|
| Record | `scripts/make_record.py` writes `records/<name>_record.md` with commit, config hash, seeds, games at once, steps per second and every gate PASS or FAIL; never edited (planned for training, works for S0) |
| Ledger | one row in [records/LEDGER.md](../records/LEDGER.md): T2, T3, …; a FAIL stays a FAIL |
| Wording | results are "observed in the training simulator", never "validated" ([STANDARDS §2](../STANDARDS.md#2-wording)) |
| Next stages | evaluate (S2), cross-check on tier 2 (S4), export the policy file and `interface.toml` (planned, S5) |

## NUS jobs

**Needs `your NUS clone`.** Set `C=<your clone of area-denial-continuous-space-self-play at 2d2b904>`. NUS's
outputs, the converted weights (`runs/nus_port/`) and the local settings files (`configs/local/nus_*.toml`) are not in
git; `scripts/nus_install_provisional.sh` installs the lab's own from the committed PROVISIONAL bundle
([how to run it yourself, level D](RUN_IT_YOURSELF.md#d-repeat-the-six-tests)). Every command runs from `svg_training/`, after `unset PYTHONPATH` if
your shell sources ROS 2. Long jobs go inside `tmux`. Results are "observed in the training simulator".

**1. The env, once** ([GETTING_STARTED](GETTING_STARTED.md#nus-jax-env-with-your-nus-clone)):

```bash
unset PYTHONPATH
C=<your clone>
scripts/workstation/setup_nus_jax.sh --dry-run --skip-gpu-check $C     # read what it will do
scripts/workstation/setup_nus_jax.sh --skip-gpu-check $C               # conda env nus_jax, Python 3.12; NUS's CPU tests (exit 5 = some failed)
scripts/workstation/setup_nus_jax.sh --cpu --skip-gpu-check $C         # no NVIDIA GPU: CPU JAX (no cuda13 extra)
```

**2. NUS's trainer, through the job runner.** `run_nus_job.sh` switches cloud logging off, keeps `~/.local` packages
out, caps JAX's share of GPU memory (`--mem-fraction`, default 0.60) and refuses to start when another process holds
more than 1024 MiB of GPU memory (owner, 18 November 2026; the same limit as `isaac_preflight.sh`, so the 5090's
remote-desktop daemon, 546–589 MiB, does not block it). Two rules from the first evening: give every job its own
`hydra.run.dir` (two jobs started in the same second otherwise share one folder), and turn videos on
(`save_eval_gif=True`, STANDARDS §8). Logs: `~/nus_jax_runs/<job>.log`, `.pid`, `.cmd.txt`.

```bash
H="+environment.env.physics.spawn_distance=8.0 environment.env.physics.defender_boundary=8.0"   # the hangar geometry (WHAT_WE_DID_DAY_BY_DAY §3)
D=$(date +%F)          # new names every time: run_nus_job.sh refuses an existing log (exit 6), and NUS overwrites an output folder
scripts/workstation/run_nus_job.sh --foreground $C ${D}_benchmark_2048 ma_skills/scripts/benchmark.py --config-name=benchmark_self_play_2048
scripts/workstation/run_nus_job.sh $C ${D}_hangar_fixed_apf_3v3_defender ma_skills/scripts/train.py --config-name=train_mappo_self_play_mpe \
    train_team=defender total_environment_steps=76800000 save_eval_gif=True $H hydra.run.dir=outputs/hangar/${D}_fixed_apf_3v3_defender
scripts/workstation/run_nus_job.sh --mem-fraction 0.25 $C ${D}_hangar_selfplay_3v3_seed1 ma_skills/scripts/train.py --config-name=train_self_play \
    seed=1 self_play.generations=8 save_eval_gif=True $H hydra.run.dir=outputs/hangar/${D}_selfplay_3v3_seed1
scripts/workstation/run_nus_job.sh $C ${D}_hangar_selfplay_3v3_seed1_to20 ma_skills/scripts/train.py --config-name=train_self_play \
    checkpoint_path=$C/outputs/hangar/${D}_selfplay_3v3_seed1 self_play.generations=20 save_eval_gif=True $H \
    hydra.run.dir=outputs/hangar/${D}_selfplay_seed1_to20_launcher
# G19 and S20 come from seed 2 continued to 20 generations: use seed=2 and its folder to repeat them
tail -f ~/nus_jax_runs/${D}_hangar_selfplay_3v3_seed1.log      # watch; stop: kill $(cat ~/nus_jax_runs/<job>.pid)
```

On the lab's workstation the exact commands of the 17–18 November runs are kept beside their logs (lab only). Never
reuse a job name or an `outputs/` folder: NUS's code overwrites it. Use `train_team=attacker` for the Strike team. Three self-play seeds share the GPU at `--mem-fraction 0.25` each.
`--dry-run` prints the exact command and starts nothing.

**3. Videos of self-play policies.** NUS's self-play runner writes no GIFs, even with `save_eval_gif=True`. Render
them afterwards with NUS's evaluator, from an archive entry (`archive/`) or `generations/*/checkpoints/best`:

```bash
scripts/workstation/run_nus_job.sh --foreground $C ${D}_eval_gif_<name> ma_skills/scripts/eval.py --config-name=eval_self_play \
    checkpoint_path=<checkpoint folder> deployment_eval_episodes=200 save_eval_gif=True hydra.run.dir=outputs/hangar/${D}_eval_gif_<name>
```

`eval.py` takes its opponent pool from the checkpoint's own `config.json`; to pick one opponent, point it at a folder
holding a link to the checkpoint's `state.msgpack` and an edited copy of that config (how the self-play clips in
[media/nus](media/nus/README.md) were made).

**4. Our side, Phases 2 to 4** (scripts `scripts/nus_*.py`; each prints paths, key names and sha256 values). These are
the commands as they were run for T15 to T21. Most of them write fixed places under `runs/nus_port/` and `configs/local/`
and **overwrite the evidence of those runs**: on a machine that holds earlier results, repeat them only in a fresh worktree (its `runs/` and
`configs/local/` start empty), with new `--tag`, `--name` and `--out-dir` values. The T17 gate script refuses an existing
gates file; `nus_phase4.py` refuses a finished row. `J` runs in NUS's env (CPU), `P` in the pipeline env:

```bash
J="env PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 JAX_PLATFORMS=cpu WANDB_MODE=disabled PYTHONPATH=source <env of your code>/bin/python"
P="env PYTHONPATH=source <pipeline env>/bin/python"     # env_isaaclab, or RUN_IT_YOURSELF B1's venv
# Phase 2: the local rules file, recordings of NUS's game, the replica gate (T15)
$J scripts/nus_make_local_rules.py --clone $C --config $C/ma_skills/config/train_self_play.yaml --out configs/local/nus_rules.toml
$J scripts/nus_record_fixtures.py --clone $C --config $C/ma_skills/config/train_self_play.yaml --tag gate_3v3 --episodes 100 --seed 2026
CUDA_VISIBLE_DEVICES= $P -m pytest -q -s tests/test_nus_replica.py -k gate
# Phase 3: the deploy file (our hangar scale; the converter reads it), convert, reference data, outcome parity (T16)
$P scripts/nus_make_local_deploy.py --clone $C --geometry-from <NUS checkpoint folder> --metres-per-unit 0.4 --seconds-per-step 0.6 \
    --hold-ticks 12 --flying-height-m 1.2 --guard-weights hangar_guard_fixed_apf --strike-weights hangar_strike_fixed_apf --out configs/local/nus_deploy.toml
$P scripts/nus_convert_checkpoint.py --checkpoint <NUS checkpoint folder> --team guard --name hangar_guard_fixed_apf
$P scripts/nus_convert_checkpoint.py --checkpoint <NUS Strike checkpoint folder> --team strike --name hangar_strike_fixed_apf
# T17 onward: G19 and S20 (seed 2, archive entries 0019_defender and 0020_attacker) and their deploy file
$P scripts/nus_convert_checkpoint.py --checkpoint <seed 2 run>/archive/0019_defender --team guard  --name ref_s2_g19_guard
$P scripts/nus_convert_checkpoint.py --checkpoint <seed 2 run>/archive/0020_attacker --team strike --name ref_s2_g20_strike
$P scripts/nus_make_local_deploy.py --clone $C --geometry-from <seed 2 run>/archive/0019_defender --metres-per-unit 0.4 --seconds-per-step 0.6 \
    --hold-ticks 12 --flying-height-m 1.2 --guard-weights ref_s2_g19_guard --strike-weights ref_s2_g20_strike \
    --same-as configs/local/nus_deploy.toml --out configs/local/nus_deploy_ref.toml
$J scripts/nus_export_reference.py --clone $C --guard-checkpoint <folder> --strike-checkpoint <folder> --seed 20261118 --episodes-per-half <E> --starts <K>
CUDA_VISIBLE_DEVICES= $P scripts/nus_outcome_parity.py --clone $C --jax-python <env of your code>/bin/python --guard-checkpoint <folder> --strike-checkpoint <folder>
# Phase 4: the hangar file, T17, the ladder rows, the figure
cp configs/nus_hangar.template.toml configs/local/nus_hangar.toml      # then set arena_side_m = 7.5 (our hangar)
CUDA_VISIBLE_DEVICES= $P scripts/nus_phase4_w3.py --write-gates
CUDA_VISIBLE_DEVICES= $P scripts/nus_phase4_w3.py --run --clone $C --jax-python <env of your code>/bin/python --guard-checkpoint <archive entry> --strike-checkpoint <archive entry>
$P scripts/nus_phase4.py --make-starts
$P scripts/nus_phase4.py --row 1 --device cuda                         # rows 2.1, 2.2, 2, 3a, 3, 4, 5a, 5 the same way
scripts/isaac_preflight.sh --approved-headless && $P scripts/nus_phase4.py --row 6 --headless --device cuda   # Isaac Lab
$P scripts/make_nus_phase4_figures.py                                # refuses (exit 2) unless all ten rows have scores.json
$P scripts/make_nus_selfplay_figures.py                                # Figure 1 of WHAT_WE_DID_DAY_BY_DAY, from the lab's matrix file (lab only)
```

Every option is in each script's `--help` and docstring. A row estimated above 2 h stops with exit 4 until you add
`--accept-long`; rows 4, 5a, 5 and 6 took 2–6 h each on the lab's RTX 5090 (run them in the background). `--out` of the
deploy script is refused outside `configs/local/`. The record writers mark any number equal to a local value as "at
the local value" (the mechanism is kept; NUS's values themselves are stated in [what we did, day by day](WHAT_WE_DID_DAY_BY_DAY.md); how to read a record:
[records/README](../records/README.md)). Instead of rebuilding the local files, `scripts/nus_install_provisional.sh`
installs the lab's own ([how to run it yourself, level D](RUN_IT_YOURSELF.md#d-repeat-the-six-tests)).

**5. Phase 5 (in progress).** Our PyTorch copy of NUS's method: `scripts/nus_make_local_method.py`,
`scripts/nus_selfplay_train.py`, `scripts/nus_phase5_reference.py`, `scripts/nus_phase5_score.py`; plan and gates in
[the Phase 5 plan](plans/2026-11-18-nus-phase5-retraining.md). R0, N0 and C0 have passed; our own seeds FAIL stage 5.1 (T43;
[what we found, training method](WHAT_WE_FOUND.md#6-ste-port-of-nus-training-method-stage-51-fail)). Each script's
`--help` holds its options.

## 8. Troubleshooting

The table lists common problems and what to do.

| Symptom | What to do |
|---|---|
| GPU busy (S0: exit 66 or 68) | stop the AirStack simulator, the benchmark or the other Isaac process; `nvidia-smi` on the host |
| Out of memory | fewer games (halve `--num-games` / `--num_envs`); the window costs memory too; the laptop has 12 GB, the 5090 32 GB |
| No window from the container | expected: headless only today. Use the host, or wait for the planned window option |
| Black window, or the remote desktop drops | do not open Isaac's window over the remote desktop: sit at the machine or use Ethernet; watch TensorBoard remotely instead |
| WiFi drops when Isaac starts | known on the laptop (RTX 5070 Ti): Isaac keeps running, the WiFi firmware crashed; reconnect over Ethernet |
| Isaac crashes at start-up | the S0 benchmark retries such a point once (`retried_points.txt`); the training start command will too (planned, S2) |
| Training slow | sensing costs most: tier 1 5 v 3 ran 98.3 million drone-steps / s in the open arena, 382,206 with full sensing ([S0_RESULTS](S0_RESULTS.md)) |
| No video written | add `--video` (it turns cameras on); check `videos/` in the run folder. The image and the host env have `moviepy` and `imageio_ffmpeg` (checked 15 Nov), so no system `ffmpeg` is needed |

**Updated when S2 lands:** check every `# planned` command and flag against the real `scripts/train.py` and
`scripts/evaluate.py`, the log and checkpoint folders, and run the window, livestream and video paths once.
