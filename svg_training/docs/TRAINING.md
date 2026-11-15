# Training a policy: headless and with the Isaac Sim window

> **Nothing can be trained yet.** The training code arrives with build step S2 (one Guard drone against one Strike
> drone). S1 (drone model and safety filter) is built and run, with no drone-model gate passed yet ([S1 results](S1_RESULTS.md)). This page
> describes how training is **planned** to work. A command marked `# planned (S2)` (or S4) does not exist yet;
> commands without the mark work today. The page is checked and corrected when S2 arrives. Terms: [glossary](GLOSSARY.md).

*Headless* means running with no window on screen. It is faster, and it is the normal way to train. A *policy* is
the trained strategy. A *container* is a sealed copy of the software that runs the same way on every machine.

Every command runs from the folder: `cd ~/AirStack-starling-max2/svg_training`.

## 1. What exists today

The table shows what works now and which build step brings the rest.

| Item | Where it stands | Arrives with |
|---|---|---|
| Container image, shell in it, tests | works: [GETTING_STARTED](GETTING_STARTED.md) A1–A2, `docker/run.sh` opens a shell | S0 |
| Training libraries in the image | present: `skrl`, `rsl_rl`, `isaaclab_tasks`, `isaaclab_rl`, `tensorboard` (checked 15 Nov) | already there |
| S0 benchmark, headless | works: [GETTING_STARTED](GETTING_STARTED.md) A3–A4 or B | S0 |
| Isaac Sim with a window, on the host | available: Isaac Lab's own commands (§5) on NVIDIA's example tasks, not our game; not yet run on this laptop | already there |
| Our game, rewards, `scripts/train.py` and `scripts/evaluate.py` | **planned** | S2 |
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
| Where you sit | anything that opens a window: at the machine or on Ethernet. Opening Isaac Sim over the remote desktop has crashed this laptop's WiFi firmware ([CLAUDE.md](../CLAUDE.md)) |

## 4. Headless training

**In the container** (the repository's way; image from [GETTING_STARTED](GETTING_STARTED.md) A1):

```bash
nvidia-smi                                                       # on the host: GPU free
docker/run.sh '$SVG_PY scripts/train.py 2026-12-01_s2_guard_seed0 <approved sha256> --tier 1 --num-games 4096 --seed 0 --max-iterations 2000'   # planned (S2)
docker/run.sh svg-isaaclab -p scripts/train.py 2026-12-01_s2_t2_seed0 <approved sha256> --tier 2 --headless --num-games 1024 --seed 0   # planned (S4)
```

**On the host** (conda `env_isaaclab` and `~/IsaacLab`, as in [GETTING_STARTED](GETTING_STARTED.md) B):

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

**Practise the controls today** on NVIDIA's quadcopter example. It trains one drone to fly to a point. It is not
our game, and it has not yet been run this way on this laptop. Isaac Lab writes `logs/` into the current folder, so
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

## 8. Troubleshooting

The table lists common problems and what to do.

| Symptom | What to do |
|---|---|
| GPU busy (S0: exit 66 or 68) | stop the AirStack simulator, the benchmark or the other Isaac process; `nvidia-smi` on the host |
| Out of memory | fewer games (halve `--num-games` / `--num_envs`); the window costs memory too; the laptop has 12 GB |
| No window from the container | expected: headless only today. Use the host, or wait for the planned window option |
| Black window, or the remote desktop drops | do not open Isaac's window over the remote desktop: sit at the machine or use Ethernet; watch TensorBoard remotely instead |
| WiFi drops when Isaac starts | known on this laptop: Isaac keeps running, the WiFi firmware crashed; reconnect over Ethernet |
| Isaac crashes at start-up | the S0 benchmark retries such a point once (`retried_points.txt`); the training start command will too (planned, S2) |
| Training slow | sensing costs most: tier 1 5 v 3 ran 98.3 million drone-steps / s in the open arena, 382,206 with full sensing ([S0_RESULTS](S0_RESULTS.md)) |
| No video written | add `--video` (it turns cameras on); check `videos/` in the run folder. The image and the host env have `moviepy` and `imageio_ffmpeg` (checked 15 Nov), so no system `ffmpeg` is needed |

**Updated when S2 lands:** check every `# planned` command and flag against the real `scripts/train.py` and
`scripts/evaluate.py`, the log and checkpoint folders, and run the window, livestream and video paths once.
