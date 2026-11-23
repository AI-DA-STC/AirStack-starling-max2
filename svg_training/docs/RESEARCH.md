REFERENCE · the state of the art as of 14 November 2026, with sources: the evidence behind the design; what changed since: gate G0 (22 November 2026) set the rules of STE's own game · start at [../README.md](../README.md); the current state: [overview](OVERVIEW.md)

# Research digest: vectorised drone-team training (as of 14 November 2026)

> **How to read this.** Start with the bullets below, then §1: each finding and what the design does about it.
> §2 is Isaac Lab, §8 published throughput (ours is measured in [S0_RESULTS.md](S0_RESULTS.md)), §9–10 environments and tags.
> Sources are web research of 14 November 2026; §11 lists what is not verified. Paper titles keep their wording;
> this folder's own wording rules are in [STANDARDS §2](../STANDARDS.md#2-wording).

- Realistic environments change training: opponents hide behind obstacles, samples needed rise by billions, and how the policy sees obstacles decides success (0.79 vs 0.10 in one study). One baked distance field can serve every game.
- Contact tags favour thrust-and-body-rate control: velocity-level pursuers caught 17.7% vs 88.4% for body-rate pursuers in one study, so the fast model must carry PX4's tracking lag or its contacts look too easy.
- Velocity-command policies transfer to real quadrotors and are the least sensitive to model mismatch, so team strategy can train on a fast model of PX4's velocity loop instead of rotor physics.
- That model must carry PX4's real behaviour: a PID velocity loop with a 45° tilt cap, no acceleration or jerk shaping on offboard setpoints, plus a fitted delay and lag. Without modelled delay, policies fail on hardware.
- The safety filter belongs in the training loop: penalise its correction, store the unfiltered action, switch it on part-way through training.
- Isaac Lab 2.3.2 offers drones at motor-thrust level only, multi-agent training only through skrl IPPO/MAPPO, and no self-play. Velocity controllers arrive in 3.0, and their velocity loop is P-only, not PX4's PID.
- No self-play scheme wins on every metric, and team-game policies overfit start positions and team sizes unless training randomises both. No measured throughput exists for Isaac Lab quadrotor teams.

This digest is the evidence for decisions the owner has already taken:

- **Two tiers, one game.** Tier 1 is a fast PX4-like velocity-response model in batched PyTorch for bulk training. Tier 2 is a rigid-body Starling 2 Max in Isaac Lab for the cross-check, for low-level flight-control training and, later, cameras.
- **Versions.** Isaac Lab 2.3.2 on Isaac Sim 5.1 now; Isaac Lab 3.0 later, on the RTX 5090 machine.
- **Uses, in priority order.** Team strategy; hosting partner strategies; low-level flight control; camera-based behaviour (future).
- **A tag is physical contact** between a Guard drone and a Strike drone; there is no tag radius. In the fast model, contact means centres closer than 0.50 m: twice the 0.248 m enclosing-sphere radius of the Starling 2 Max with propellers, measured from the drone's USD (decided 14 Nov 2026).
- **The safety filter acts only between drones of the same team**, never between a Guard drone and a Strike drone (14 Nov 2026).
- **Games are played in realistic 3D environments**, the lab's construction-site world first (14 Nov 2026).

The game: the Guard team holds a circular zone, the Strike team tries to reach the zone, and a Guard drone tags a Strike drone by contact. Policies output velocity commands to ModalAI Starling 2 Max drones on PX4, and a safety filter (a control barrier function, CBF) keeps drones of the same team apart. Statements marked "estimate" or "the researcher's suggestion" are judgements from the research, not published results.

> **Note, 18 November 2026.** The same-team-only filter on this page (here, the decisions table and §6 item 6) is now
> the contact-tag track's rule; the main game and the NUS port filter every pair, as in flight
> ([STANDARDS §4](../STANDARDS.md#4-game-specification-version-0)).

## 1. What the findings mean for this pipeline

| Finding | Design consequence | Source section |
|---|---|---|
| Velocity-level actions transfer and are the least sensitive to model mismatch; they lose agility only near the platform's limits ([Kaufmann 2022](https://arxiv.org/abs/2202.10796)). | Policies output velocity setpoints. Strategy training needs no rotor physics, so tier 1 carries the bulk of training. | §4 |
| PX4 tracks offboard velocity with a PID (default xy 1.8/0.4/0.2) and a 45° tilt cap; `MPC_ACC_HOR` and `MPC_JERK_*` do not shape offboard setpoints, so a raw step gives close to tilt-limited acceleration ([PositionControl.cpp](https://github.com/PX4/PX4-Autopilot/blob/main/src/modules/mc_pos_control/PositionControl/PositionControl.cpp)). | Tier 1 ports PX4's `_velocityControl` and `_accelerationControl`. Command rate limiting is the policy's or the safety filter's job, not PX4's. | §5 |
| Without simulated rotor delay, 0/10 real flights succeeded ([Learning to Fly in Seconds](https://arxiv.org/html/2311.13081v2)); published delays range 20–60 ms and up to 1/15 s. | Tier 1 has an explicit command delay and attitude lag, fitted from Starling flight logs. | §4, §5 |
| Sys-ID first, randomise selectively: ±30% mass randomisation made SimpleFlight worse; only the thrust coefficient helped ([SimpleFlight](https://arxiv.org/html/2412.11764v4)). | Fit delay, lag and drag from logs; randomise lag, delay and Kp by about ±20–30% rather than everything. | §4, §5 |
| A low-pass filter on actions failed on hardware; a smoothness reward worked, but only when added in a second training stage ([SimpleFlight](https://arxiv.org/html/2412.11764v4), [OPEN](https://arxiv.org/html/2409.15866v4)). | No action filter in the loop. Add an action-rate penalty (λ ≈ 0.4–2.0) in stage 2. | §4, §7 |
| Policies trained with the safety filter in the loop score about 20% higher on hardware than policies that meet it only at deployment ([Bejarano et al.](https://arxiv.org/html/2410.11671v2)). | The same safety filter runs in tier 1, tier 2 and flight. Penalise correction size, store the unfiltered action, switch the filter on part-way. | §6 |
| Owner's decision: the safety filter acts only within a team, and a tag is contact (centres closer than 0.50 m). No published work excludes the other team from a safety filter; the closest has "role-dependent engagement constraints" (abstract only, [2607.10986](https://arxiv.org/abs/2607.10986)). | The filter takes a same-team pair mask, so Guard–Strike pairs are never filtered and contact stays reachable. Tier 1 treats contact as a sphere-overlap event, not physics. | §6, §10 |
| Every two-team game in clutter hides opponents out of line of sight; win rates fell from 80% to 3% against an unexpected opponent type in an urban two-UAV study ([2511.05812](https://arxiv.org/html/2511.05812v1)). | Observations carry a line-of-sight mask, last-seen state and a GRU; the critic sees unmasked state. | §10 |
| Obstacles multiply sample cost: MAPPO needs over 2.0 B samples for about 90% capture with obstacles ([OPEN](https://arxiv.org/html/2409.15866v4)); hide-and-seek needed 31.7 B frames ([Baker et al.](https://arxiv.org/pdf/1909.07528)). | Clutter stages come after the open arena works; budget them on tier 1. | §10 |
| Plain MAPPO "fails entirely" in hard obstacle settings ([DualCL](https://arxiv.org/html/2312.12255v2)); policies overfit below about 4,000 levels ([Cobbe et al.](https://proceedings.mlr.press/v97/cobbe19a.html)). | A curriculum of environments: a layout generator, an archive of unsolved scenes, thousands of layouts, one held-out world. | §9, §10 |
| Swapping a distance-field patch for a nearest-obstacle list dropped success from 0.79 to 0.10 ([Huang et al.](https://arxiv.org/html/2309.13285v2)). | Obstacles enter as a distance-field patch or range rays, not a nearest-k list. | §10 |
| For policies without cameras, geometry (open space, clutter density, line-of-sight blockers) matters more than photorealism; this is the researcher's inference, not a tested result. | Match the construction site's scale and clutter; strip materials from the training copy. | §9 |
| One baked distance field (SDF) tensor serves every game; 100 × 100 × 30 m at 20 cm is 75 MB in fp16 (the researcher's arithmetic). | Tier 1 bakes the site once and varies games by transform and added clutter. | §9 |
| Sensing, not physics, sets throughput: 3.4 M physics steps/s vs 96 k depth images/s ([DiffAero](https://arxiv.org/html/2509.10247v1)). | S0 measures steps/s with range rays and line-of-sight queries, not physics alone. | §8, §10 |
| Velocity-level pursuers caught 17.7% vs 88.4% for body-rate pursuers ([Gavin & Bronz](https://arxiv.org/html/2607.05939)); 0.51 vs 0.95 in a second study ([Sanchez Roncero et al.](https://arxiv.org/html/2506.02849v2)). The velocity loop there was a fast inner loop, not PX4 at 20 Hz. | Velocity setpoints stay the strategy interface, but tier 1 models PX4's tracking lag explicitly; tier 2's body-rate layer is where contact tags can test lower-level control. | §5, §10 |
| Local Isaac Lab 2.3.2 has drones at motor-thrust level only; Lee controllers exist only in 3.0, and the Lee velocity loop is P-only ([#3895](https://github.com/isaac-sim/IsaacLab/pull/3895)). | Tier 2 on 2.3.2 needs its own PX4-style velocity cascade on top of the `Thruster` model. This same layer is where low-level flight-control training plugs in. | §2, §5 |
| Isaac Lab's only native multi-agent path is `DirectMARLEnv` + skrl IPPO/MAPPO; there is no self-play, league or opponent-pool support. | Opponent pool, snapshot buckets and ratings are our own code, outside the learner, and shared by both tiers. Partner strategies plug in as pool members. | §2, §7 |
| No self-play scheme dominates ([VolleyBots](https://arxiv.org/html/2502.01932)); rule-based agents beat deep RL in maritime capture-the-flag ([Pyquaticus](https://arxiv.org/pdf/2404.17038)). | Mix latest-vs-latest, past snapshots and scripted classical opponents. Scripted baselines and exploitability are part of evaluation. | §7 |
| Start-position overfitting is the known failure mode; archives of starts with success in [0.5, 0.9] fix it ([OPEN](https://arxiv.org/html/2409.15866v4)). | Starts are uniform over the arena from the first run, plus an archive of hard starts. | §7 |
| Team-size generalisation decays: about 56% completion at twice the trained count ([UZH racing](https://arxiv.org/html/2605.22748)). | One shared actor per team over padded, masked entity lists; train across the full team-size range with mid-episode drop-outs. | §7 |
| One shared critic's advantages cancel in zero-sum games ([HARL-A](https://arxiv.org/html/2510.01264v1)). | One critic per team. | §7 |
| Sparse win/lose rewards gave a 44.7% smaller sim-to-real speed gap than dense progress rewards ([Agile Flight Emerges](https://arxiv.org/html/2512.11781v1)). | Zero-sum terminal rewards; any shaping is potential-based and annealed to zero. | §4, §7 |
| No measured throughput exists for Isaac Lab quadrotor teams; PyTorch point-mass simulators reach millions of steps/s ([DiffAero](https://arxiv.org/html/2509.10247v1)). | Plan compute on tier 1. Measure tier 2 throughput on our own hardware before budgeting it. | §8 |
| PX4's neural modules need PX4 1.17/1.18; VOXL2 runs PX4 1.14 ([ModalAI notes](https://docs.modalai.com/sdk-1.7-release-notes/)). | The policy stays a velocity-setpoint source outside PX4. | §5 |
| Isaac Lab 3.0 switches quaternions from WXYZ to XYZW, and shape checks do not catch a wrong order ([release](https://github.com/isaac-sim/IsaacLab/releases/tag/v3.0.0)). | Keep Isaac Lab-specific code inside tier 2 so the 3.0 move touches one layer. | §2 |

## 2. Isaac Lab today

| | Isaac Lab 2.3.2 (installed here) | Isaac Lab 3.0.0 GA |
|---|---|---|
| Released | 2 Feb 2026, the "last release from main" ([pip docs](https://isaac-sim.github.io/IsaacLab/v2.3.2/source/setup/installation/pip_installation.html)) | 20 Oct 2026 ([release](https://github.com/isaac-sim/IsaacLab/releases/tag/v3.0.0)) |
| Isaac Sim | 5.1; its docs now carry a "no longer supported" banner | 6.2, GA 22 Oct 2026, "primarily a bug-fix release" for Lab 3.0 ([forum](https://forums.developer.nvidia.com/t/isaac-sim-6-2-general-availability/386512)) |
| Python / PyTorch | 3.11 / 2.7.0+cu128 (supports sm_120) | 3.12 / 2.11 with CUDA 13.0 |
| Linux driver | 580 series, 580.65.06 ([#3477](https://github.com/isaac-sim/IsaacLab/issues/3477)) | 595.58.03 ([requirements](https://docs.isaacsim.omniverse.nvidia.com/6.2.0/installation/requirements.html)) |
| Physics | PhysX | Newton 1.6.1 (Warp-native) and PhysX; the multirotor asset is PhysX-only ([#6141](https://github.com/isaac-sim/IsaacLab/issues/6141)) |
| Drone asset | `Multirotor`, `Thruster`, `ThrustAction` from NTNU ARL ([#3760](https://github.com/isaac-sim/IsaacLab/pull/3760)) | Same |
| Drone controllers | None: motor-thrust level only | `LeeAttitude`, `LeeVel`, `LeeAcceleration`, `LeePosition` ([#3895](https://github.com/isaac-sim/IsaacLab/pull/3895)); inertia fix [#8964](https://github.com/isaac-sim/IsaacLab/pull/8964) not merged |
| Drone tasks | `Isaac-TrackPositionNoObstacles-ARL-Robot-1-v0` (+ `-Play-v0`), `Isaac-Quadcopter-Direct-v0` | `IsaacContrib-TrackPositionNoObstacles-ARL-Robot-1`, `IsaacContrib-Navigation-3DObstacles-ARL-Robot-1`; Quadcopter-Direct removed ([CHANGELOG](https://github.com/isaac-sim/IsaacLab/blob/main/source/isaaclab_tasks/docs/CHANGELOG.rst)) |
| RL libraries | rsl_rl 5.0.1, skrl 2.1.0, rl_games 1.6.1, SB3 2.8.0 | RSL-RL 5.5.1; TorchRL's `IsaacLabWrapper` is tested on 3.0 only ([TorchRL](https://docs.pytorch.org/rl/stable/reference/isaaclab.html)) |

The 3.0 navigation task already matches the tier-2 architecture: the policy outputs velocity commands tracked by `LeeVelController`, with depth from a Warp `MultiMeshRayCasterCamera` at 480×270 encoded by a VAE ([navigation_env_cfg.py](https://github.com/isaac-sim/IsaacLab/blob/main/source/isaaclab_tasks/isaaclab_tasks/contrib/drone_arl/navigation/config/arl_robot_1/navigation_env_cfg.py)). Neither ARL task has published training results or throughput. NTNU's later depth-navigation work on Lab 3.0-EA reports real flights ([general-navigation-policy](https://github.com/ntnu-arl/general-navigation-policy), [arXiv 2610.08306](https://arxiv.org/abs/2610.08306)).

### What the local install offers

| Item | Value |
|---|---|
| Repository | `~/IsaacLab`, branch `main`, VERSION 2.3.2, HEAD `f73c331738` (1 Jun 2026), 25 commits past the v2.3.2 tag; the `v3.0.0-beta` tag is not reached |
| Environment | conda `env_isaaclab`, Python 3.11.15, isaacsim 5.1.0.0 wheels, editable `isaaclab` 0.54.4 and `isaaclab_contrib` 0.0.2 |
| Other libraries | torch 2.7.0+cu128, warp 1.14.0, gymnasium 1.2.1, onnx 1.21.0 |

- **Drones are motor-thrust level only.** `Multirotor(Articulation)` maps thrusts to a body wrench through a 6×4 `allocation_matrix`; `Thruster` is a first-order rotor model with an RK4 option. There is no attitude, velocity or position controller and no velocity-command action.
- **Thruster parameters** ([thruster_cfg.py](https://github.com/isaac-sim/IsaacLab/blob/main/source/isaaclab_contrib/isaaclab_contrib/actuators/thruster_cfg.py)): separate rise and fall time constants randomised per environment, thrust coefficient range, slew-rate limit. ARL Robot 1 uses tau_inc 0.05–0.08 s, tau_dec 0.005 s, 0.1–10 N per motor ([arl_robot_1.py](https://github.com/isaac-sim/IsaacLab/blob/main/source/isaaclab_assets/isaaclab_assets/robots/arl_robot_1.py)).
- **ARL position task:** 4096 envs, sim dt 0.01 s, decimation 10 (10 Hz policy), 5 s episodes, per-motor thrust actions, rewards include `action_rate_l2` (−0.05). Ships rsl_rl, skrl and rl_games PPO configs.
- **Crazyflie direct task:** collective thrust plus body moments applied as a wrench, with no actuator lag.
- **Multi-agent:** `DirectMARLEnv` (PettingZoo Parallel API) with per-agent spaces, dict `step`, `state()`, and hooks `_get_observations`, `_get_states`, `_get_rewards`, `_get_dones`. Only skrl trains natively multi-agent (`--algorithm IPPO|MAPPO`); RSL-RL, RL-Games and SB3 flatten to one agent ([#7360](https://github.com/isaac-sim/IsaacLab/pull/7360)). Shipped examples are cooperative only (cart–double-pendulum, Shadow-Hand-Over). Manager-based envs have no multi-agent support.
- **Self-play, league or adversarial support:** none.
- **N drones per environment:** give the scene N asset configs with different prim names, as Shadow-Hand-Over does with `replicate_physics=True`.
- **Sensors:** `TiledCamera`, `RayCaster` (single static mesh), and `MultiMeshRayCasterCamera`, whose per-target `track_mesh_transforms` may allow other drones as targets (not verified).
- **External project:** `./isaaclab.sh --new` generates a pip-installable extension outside the repo, with Direct single-agent, Direct multi-agent or Manager-based templates and skrl IPPO/MAPPO agent configs.
- **Export:** `rsl_rl/play.py` writes `exported/policy.pt` (JIT) and `policy.onnx`. Multi-GPU runs through torchrun with `--distributed`, Linux only ([docs](https://isaac-sim.github.io/IsaacLab/v2.3.2/source/features/multi_gpu.html)).
- **Assets** resolve from Nucleus, so first use needs network access or an asset cache.

### Migration traps 2.3 → 3.0

From the [release notes](https://github.com/isaac-sim/IsaacLab/releases/tag/v3.0.0) and [migration guide](https://docs.nvidia.com/isaaclab/isaac-lab/migrating-to-3-0); the researcher rates the cost as medium to high and easy to get subtly wrong.

| Change | Trap |
|---|---|
| Quaternions WXYZ → XYZW | Shape checks do not catch a wrong order |
| `.data.*` returns `ProxyArray` | Code needs `.torch` |
| Write methods split into index and mask variants | Every state write changes |
| `AppLauncher` → `launch_simulation`; per-library `train.py` → `isaaclab train`; `--headless` → `--viz none` | Launch scripts change |
| Scene builds one source env and applies a clone plan; `cfg.robot_cfg` → `cfg.scene.robot` ([#5770](https://github.com/isaac-sim/IsaacLab/pull/5770)) | Scene configs move |
| Actuator fields renamed; IMU becomes `Pva`; TiledCamera folded into Camera | Configs break |
| Fresh Python 3.12 environment, installed with `uv` | Lab 3.0 and Isaac Sim 5.1 (AirStack, Pegasus) can coexist in separate environments |
| Performance | beta2 lost about 20% Humanoid throughput and the wrench composer cost about 50% FPS on PhysX; maintainers say both are patched ([#7398](https://github.com/isaac-sim/IsaacLab/issues/7398)) |

A fallback for staying on 2.3.2: backport the pure-torch Lee controllers, converting quaternions back to WXYZ, dropping `.torch` and applying the #8964 fix.

### Driver and GPU notes

- Isaac Sim 5.1 needs the 580 driver; some users on 580.65.06 report a Warp `cuDeviceGetUuid` error ([#3477](https://github.com/isaac-sim/IsaacLab/issues/3477)).
- TiledCamera hangs on an RTX 5090 with Isaac Sim 5.1; the reporter's workaround was the standard Camera ([#4951](https://github.com/isaac-sim/IsaacLab/issues/4951)). Cameras on the Quadcopter env needed `clone_in_fabric=False` ([#4424](https://github.com/isaac-sim/IsaacLab/issues/4424)).
- Open 3.0 camera bugs: a headless depth-only camera blacks out RGB cameras ([#9002](https://github.com/isaac-sim/IsaacLab/issues/9002)); large camera atlases return black tiles ([#8412](https://github.com/isaac-sim/IsaacLab/issues/8412)).
- Isaac Sim lists 16 GB VRAM as the minimum ([5.1 requirements](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/installation/requirements.html)); 12 GB suits state-based training but is tight for RTX cameras. On 12 GB, prefer Warp ray-cast depth over TiledCamera.
- Train headless: the Isaac start/stop WiFi firmware crash on the laptop drops remote desktop sessions.

## 3. Simulators and frameworks compared

| Framework | Status (Nov 2026) | Physics and controllers | Multi-agent | Real-flight evidence | URL |
|---|---|---|---|---|---|
| Isaac Lab `isaaclab_contrib` | ★8.6k, 3.0 GA | PhysX rigid body + thruster model; Lee att/vel/acc/pos in 3.0 | `DirectMARLEnv` (task is ours to write) | NTNU depth navigation | [repo](https://github.com/isaac-sim/IsaacLab), [2610.08306](https://arxiv.org/abs/2610.08306) |
| Aerial Gym | ★781, Isaac Gym (deprecated); Isaac Lab support "under development" | Same motor model; Lee controllers; Warp depth | Limited | Yes, including a VOXL 2 Mini + PX4 motor-level policy | [repo](https://github.com/ntnu-arl/aerial_gym_simulator), [paper](https://arxiv.org/html/2503.01471v1) |
| OmniDrones | ★591; README says "hard to maintain"; Isaac Sim 4.1; last code Oct 2024 | Rotor model, controllers, MARL tasks | Yes (MAPPO) | Some (OPEN, VolleyBots, AgilePE trained on it) | [repo](https://github.com/btx0424/OmniDrones) |
| Pegasus | ★920; v5.1.0 for Isaac Sim 5.1 only | PX4/ArduPilot SITL, single scene | Several vehicles, not vectorised | Validation tool, not for training | [repo](https://github.com/PegasusSimulator/PegasusSimulator) |
| IsaacLab-HARL | ★167; fork on Isaac Sim 4.5 | Adds `happo_adv`, one critic per team | Adversarial, alternating ("leapfrog") training | No | [repo](https://github.com/DIRECTLab/IsaacLab-HARL), [paper](https://arxiv.org/html/2510.01264v1) |
| isaac_drone_racer | ★200; Isaac Sim 4.5 | Rotor, drag and power models; attitude/rate control | No | Not stated | [repo](https://github.com/kousheekc/isaac_drone_racer) |
| CrazyPlayGround | ★18; Lab 2.3.2 | Crazyflie tasks | Unknown | Deploy scripts for CF2.1 | [repo](https://github.com/JulienHansen/CrazyPlayGround) |
| DiffAero | ★103, last push Dec 2025; pure PyTorch, differentiable | Full quadrotor, continuous and discrete point mass; PPO, DreamerV3, BPTT, SHAC, SHA2C | Position and obstacle tasks are multi-agent capable | Point-mass policy flown through PX4 with OptiTrack | [repo](https://github.com/flyingbitac/diffaero), [paper](https://arxiv.org/html/2509.10247v1) |
| rlPx4Controller (AirGym) | C++ library, CPU-parallel | "Strict PX4-like" position, velocity, attitude and CTBR control | Not stated | Not stated | [repo](https://github.com/emNavi/rlPx4Controller), [AirGym](https://arxiv.org/html/2504.15129v1) |
| Crazyflow | JAX, differentiable | Crazyflie-centred | Not stated | Not stated | [2606.01478](https://arxiv.org/abs/2606.01478) |
| RLtools | Laptop-GPU training | Single-agent motor control | No | Crazyflie after 18 s of training | [2311.13081](https://arxiv.org/abs/2311.13081) |
| VMAS | PyTorch, BenchMARL-ready | 2D point mass | Yes | No | [repo](https://github.com/proroklab/VectorizedMultiAgentSimulator) |
| TimeChamber | Isaac Gym | Self-play framework | PFSP pool, vectorised Elo | No | [repo](https://github.com/floodsung/TimeChamber) |

Flightmare and Agilicious are inactive (last pushes 2024 and 2023). VisFly renders with Habitat-Sim for vision tasks ([2407.14783](https://arxiv.org/html/2407.14783v4)).

The researcher recommends Isaac Lab `isaaclab_contrib` as the rigid-body base: it is the only maintained Isaac framework with a batched velocity controller and per-environment motor and gain randomisation, from authors with a VOXL 2 + PX4 record. DiffAero is the closest match to a velocity-command + PX4 + motion-capture setup and the precedent for tier 1. VMAS or DiffAero's point mass is the fastest place to prototype the game logic and rewards.

## 4. What makes a policy transfer to a real quadrotor

| Paper (year) | Platform | Action (rate) | Sim | What made transfer work |
|---|---|---|---|---|
| Kaufmann benchmark, ICRA 2022 ([arXiv](https://arxiv.org/abs/2202.10796)) | Agile quad | Velocity vs CTBR vs per-rotor thrust | BEM simulator, 20 ms delay | CTBR and velocity transferred; per-rotor thrust could not fly with the real 60 ms latency. Velocity least sensitive to mismatch. |
| Swift, Nature 2023 ([PDF](https://rpg.ifi.uzh.ch/docs/Nature23_Kaufmann.pdf)) | Racing quad, Betaflight | CTBR; MLP 2×128 | Custom | No dynamics randomisation; residual models fitted on 800–1,000 real samples, then fine-tuning. |
| Learning to Fly in Seconds ([arXiv](https://arxiv.org/html/2311.13081v2)) | Crazyflie | RPM | RLtools | Without first-order rotor delay (0.15 s), 0/10 real flights; without action history the policy fails. |
| SimpleFlight 2024–25 ([arXiv](https://arxiv.org/html/2412.11764v4)) | Crazyflie; a PX4/Orin quad | CTBR, 100 Hz; 3×256 MLP | OmniDrones | Sys-ID of mass, inertia, thrust coefficient, motor time constant; action-difference reward (λ=0.4); action low-pass filter failed; 50 Hz clearly worse than 100 Hz. |
| RAPTOR 2025 ([arXiv](https://arxiv.org/abs/2509.11481)) | 10 quads, 32 g–2.4 kg | Motor commands | RLtools | 1,000 teachers distilled into one recurrent 2,084-parameter student that adapts in context. |
| PX4 neural mode, NTNU 2025 ([arXiv](https://arxiv.org/html/2505.00432v1)) | 1.2 kg quad, Pixracer Pro | Motor thrusts, 650 Hz; 64×32 MLP | Aerial Gym | Sim and real responses "largely consistent"; motor-command mismatch traced to the motor time constant. |
| Collision encoding, ICRA 2024 ([arXiv](https://arxiv.org/abs/2402.03947)) | ARL quad | Velocity + yaw rate to the autopilot | Aerial Gym | Depth encoder frozen before RL; policy runs on velocity references. |
| Back to Newton's Laws 2025 ([arXiv](https://arxiv.org/html/2407.10648v2)) | 365 g quad, Betaflight | Thrust-acceleration vector, 15 Hz | Differentiable point mass | Fixed delay 1/15 s plus moving-average lag (λ=12) fitted from step responses; drag fitted and randomised; six drones flew together. |
| DiffAero 2025 ([arXiv](https://arxiv.org/html/2509.10247v1)) | Quad + PX4 | Acceleration → attitude + thrust | Point mass with first-order lag | Lag factor fitted and randomised per episode. |
| OPEN 2024–25 ([arXiv](https://arxiv.org/html/2409.15866v4)) | 3 Crazyflies | CTBR, 100 Hz, MAPPO | OmniDrones + sys-ID | Smoothness term (coefficient 2.0) added in stage 2; without it the real drones crashed. |
| AgilePE 2026 ([arXiv](https://arxiv.org/html/2608.14135v1)) | PX4, Orin NX | CTBR, 60 Hz | OmniDrones | Thrust response 45 ms and rate response 30 ms modelled; gains randomised ±10% (thrust) and ±30% (rates); delay jitter ±20–30%. |
| Agile Flight Emerges 2025 ([arXiv](https://arxiv.org/html/2512.11781v1)) | Crazyflie Brushless | CTBR, 50 Hz in sim | Isaac Lab | Sparse win/lose multi-agent reward: 44.7% smaller sim-to-real speed gap than dense progress rewards. |
| Layered Safety, RSS 2025 ([arXiv](https://arxiv.org/html/2505.02293)) | 3 Crazyflies | Acceleration, 10 Hz, onboard PID | Double integrator | Safety filter switched on halfway through training; transferred to hardware. |

### Transfer checklist

| Item | What the sources give |
|---|---|
| Sys-ID before randomisation | Identify mass, thrust map, actuator lag; ±30% mass randomisation hurt SimpleFlight |
| Delay and lag, explicitly | 20 ms (benchmark sim) vs 60 ms (real); 45 ms thrust / 30 ms rate (AgilePE); 1/15 s (Back to Newton); delay up to 40 ms ([UZH](https://arxiv.org/html/2605.22748)) |
| Randomisation ranges | Gains ±10% thrust, ±30% rates, delay jitter ±20–30% (AgilePE); thrust, drag, inertia ±10%, mass ±5% (UZH) |
| Smoothness | Reward on ‖u_t − u_{t−1}‖, λ ≈ 0.4–2.0, added in stage 2; no low-pass filter |
| Memory | Action or state history (RLtools) or recurrence (RAPTOR; LSTM-256 in UZH) |
| Network size | 2×128, 3×256, 64×32, 2,084 parameters: small networks suffice |
| Policy rate | 100 Hz for CTBR; 10–15 Hz has transferred for velocity or acceleration policies |
| Rewards | Sparse or competitive rewards for adversarial tasks |
| Observation noise | A minor factor in the RLtools ablation |

Every deployed team-game result used motion capture, and most ran inference off-board. Exceptions: the single VolleyBots drone (Orin on board) and Crazyflie teams (MCU on board).

### Later: camera policies

1. Train a privileged-state teacher, distil into a depth student with DAgger, then fine-tune with RL; fine-tuning raised success from 40% to 100% ([2403.12203](https://arxiv.org/html/2403.12203v3)).
2. Use very low-resolution depth (16×12, 16×9) with a GRU; low resolution itself narrows the gap ([2407.10648](https://arxiv.org/html/2407.10648v2), [2509.10247](https://arxiv.org/html/2509.10247v1)).
3. Pre-train and freeze a depth encoder on sim and real depth, then run RL on the latent ([2402.03947](https://arxiv.org/abs/2402.03947)).
4. Randomise depth noise, blur, scale and offset ([2504.15129](https://arxiv.org/html/2504.15129v1)), with a noise curriculum from privileged input to depth ([2512.09571](https://arxiv.org/html/2512.09571v1)). Model camera latency at its frame rate (15–30 Hz).

## 5. Modelling PX4's velocity loop

**Offboard setpoint types** ([offboard docs](https://docs.px4.io/main/en/flight_modes/offboard)). A velocity setpoint bypasses the position P loop; acceleration bypasses position and velocity; attitude and rate setpoints skip the whole position controller; thrust/torque and actuator setpoints bypass all PX4 loops. PX4 needs at least a 2 Hz stream; `COM_OF_LOSS_T` sets the timeout.

**How PX4 tracks a velocity setpoint** ([PositionControl.cpp](https://github.com/PX4/PX4-Autopilot/blob/main/src/modules/mc_pos_control/PositionControl/PositionControl.cpp), [gain params](https://github.com/PX4/PX4-Autopilot/blob/main/src/modules/mc_pos_control/multicopter_position_control_gain_params.yaml)):

| Element | Behaviour | Default |
|---|---|---|
| Acceleration command | `Kp(v_sp − v) + ∫Ki·e − Kd·v̇`; D term on measured acceleration, low-pass `MPC_VELD_LP` | 5 Hz filter |
| Horizontal gains | `MPC_XY_VEL_P/I/D_ACC` | 1.8 / 0.4 / 0.2 |
| Vertical gains | `MPC_Z_VEL_P/I/D_ACC` | 4.0 / 2.0 / 0 |
| Tilt cap | `MPC_TILTMAX_AIR` | 45° |
| Thrust | Saturated with vertical priority; horizontal integrator has tracking anti-windup | – |
| Speed clamps | `MPC_XY_VEL_MAX`, `MPC_Z_VEL_MAX_UP`, `MPC_Z_VEL_MAX_DN` | 12 / 3 / 1.5 m/s |
| **Does not apply** | `MPC_ACC_HOR`, `MPC_JERK_*` feed only the goto controller and flight-task generators | – |

Researcher's estimate, not from a source: ignoring attitude lag, the horizontal loop behaves like a first-order lag with τ ≈ (1+Kd)/Kp ≈ 0.67 s at default gains, and the acceleration cap is about g·tan 45° ≈ 9.8 m/s². The Isaac Lab Lee velocity loop is `K_vel * velocity_error` with no integral term, so it is not a stand-in for this PID.

### Fidelity ladder

| Level | Model | Role here |
|---|---|---|
| L0 | Point mass, first-order velocity lag τ, pure delay d, acceleration cap, speed clamp | Game-logic exploration |
| L1 | Batched PyTorch double integrator driven by a line-by-line port of PX4 `_velocityControl` and `_accelerationControl`, plus fitted second-order tilt lag, command delay (and Wi-Fi if used), drag; gains from the drone's parameter dump; lag, delay and Kp randomised ±20–30%; same safety filter at 10–50 Hz | **Tier 1** (the researcher's recommended main model) |
| L2 | Isaac Lab rigid body + `Thruster` model + ported PX4 velocity PID | **Tier 2**: checks L1 near tilt and thrust saturation and in collisions |
| L3 | AirStack PX4 SITL: real PX4, EKF, uXRCE-DDS or MAVROS path, safety filter | Gate before flight |
| L4 | Hardware with motion capture | Final evidence |

Rigid-body plus PX4-like cascade (rlPx4Controller, Isaac Lab) and point mass with identified lag (Back to Newton, DiffAero, Layered Safety) are both published routes; a frozen learned low-level policy (VolleyBots) is a third. A sim-to-sim gate is standard in legged robotics ([Humanoid-Gym](https://arxiv.org/abs/2404.05695)).

### Fitting the model from flight logs

1. Fly offboard velocity steps and doublets (0.5–2 m/s, every axis) in SITL and on the real drone.
2. Parse the ulog with pyulog ([log analysis](https://docs.px4.io/main/en/log/flight_log_analysis.html)); fit τ, d, attitude lag and drag by least squares. [data-driven-dynamics](https://github.com/KonradRudin/data-driven-dynamics) fits parametric multirotor models from ulogs.
3. Read the Starling 2 Max's tuned `MPC_*` values from the drone; they are not published.
4. Compare at L3 and L4 (the researcher's suggestion; no source standardises these): step delay, rise time and overshoot; velocity RMSE on recorded strategy commands; open-loop position divergence at 1–3 s; closed-loop gaps in win rate, safety-filter intervention rate and minimum separation.

### PX4 neural modules and VOXL2

| Module | First release | What it does |
|---|---|---|
| `mc_nn_control` ([docs](https://docs.px4.io/main/en/neural_networks/mc_neural_network_control)) | v1.17.0, May 2026 | TFLite Micro; 15 inputs → 4 motor forces; replaces the controller cascade and allocator |
| `mc_raptor` ([docs](https://docs.px4.io/main/en/neural_networks/raptor)) | v1.18.0-rc1, Sep 2026 | External mode following `trajectory_setpoint`; holds position after 200 ms without one; docs call MAVLink/Wi-Fi setpoint feeding "unreliable" |

Neither runs on stock VOXL2: voxl-px4 is based on PX4 1.14.0, including the SDK 1.7 pre-releases ([notes](https://docs.modalai.com/sdk-1.7-release-notes/)), and runs on the sensors DSP ([forum](https://forum.modalai.com/post/4623)). voxl-tflite-server targets vision models and often falls back to CPU for custom models ([docs](https://docs.modalai.com/voxl-tflite-server/), [forum](https://forum.modalai.com/topic/2872/voxl-2-tflite-gpu-delegate-fails-on-custom-model)). The researcher's judgement: a strategy MLP runs on the VOXL2 CPU; a ground-station policy adds Wi-Fi latency and jitter.

## 6. Training with the safety filter in the loop

| Evidence | Result |
|---|---|
| Bejarano et al., RA-L 2025, Crazyflie ([2410.11671](https://arxiv.org/html/2410.11671v2)) | Unfiltered training loses return when the filter is added at deployment (200.2 vs 222.1 in sim); filtered training about 20% higher on hardware; smoothness up to 75% better in sim |
| Layered Safety, RSS 2025 ([2505.02293](https://arxiv.org/html/2505.02293)) | Filter switched on halfway, because early filtering hurts exploration; filtered-trained variants beat unfiltered on every metric; no correction penalty |
| CBF-RL ([2510.14959](https://arxiv.org/pdf/2510.14959v4)) | 100% success vs 55% for filter-only training |
| Taxonomy ([2511.17765](https://arxiv.org/pdf/2511.17765)) | Options: constant penalty when the filter acts, penalty scaled by correction size, or none |

**Recipe.**

1. Run the same safety filter in tier 1, tier 2 and flight, and keep it on at evaluation.
2. Penalise the correction α‖u_policy − u_filtered‖², α ≈ 1–10; this beat a constant penalty.
3. Store the unfiltered policy action in the PPO buffer.
4. Switch the filter on part-way through training (halfway in Layered Safety).
5. Reset episodes only from safe states, and log the intervention rate.
6. Filter only same-team pairs (owner's decision): a Strike drone cannot shelter behind the filter, and a contact tag (centres closer than 0.50 m) stays reachable. The AirStack filter keeps a 1.1 m keep-out between all drones (2 × 0.55 m `cbf_safety_radius_m` in `cbf_sim.yaml`), so a contact-tag policy needs a same-team pair mask there before it flies (§10).

## 7. Two-team games: theory, self-play, evaluation

The literature calls this a **multiplayer reach-avoid game**: "attackers" try to reach a target region and "defenders" try to stop them. Variants are "perimeter defense", "target guarding" / "target-attacker-defender (TAD)" and "border defense" ([Yan et al. review](https://www.frontiersin.org/journals/control-engineering/articles/10.3389/fcteg.2022.1093186/full), [Shishika et al.](https://www.frontiersin.org/articles/10.3389/fcteg.2023.1279454)). Here, the Strike team and the Guard team.

### Classical baselines (scripted opponents and yardsticks)

| Baseline | Use |
|---|---|
| Pairwise Hamilton–Jacobi (HJ) outcomes + maximum matching ([Chen, Zhou & Tomlin](https://arxiv.org/pdf/1611.00450)) | One HJ PDE covers every pair of identical players; the matching bounds how many Strike drones reach the zone |
| Exact 2-vs-1 HJ + mixed-integer assignment ([2309.13155](https://arxiv.org/html/2309.13155v1)) | Intractable past a 6-dimensional joint state |
| Team strategies, Shishika, Paulos & Kumar ([1912.04342](https://arxiv.org/pdf/1912.04342), [review](https://link.springer.com/chapter/10.1007/978-3-030-64793-3_26)); Garcia, Casbeer & Pachter ([2002.04054](https://arxiv.org/abs/2002.04054)); Bajaj & Bopardikar ([2007.04406](https://bohrium.dp.tech/paper/arxiv/2007.04406)) | Analytic team play |
| Apollonius-circle dominance regions ([Automatica 2023](https://www.flight.utias.utoronto.ca/fsc/wp-content/uploads/2023/05/automatica2023FF.pdf)) | Zero capture radius gives an Apollonius circle; a non-zero one, such as the 0.50 m contact distance, gives a Cartesian oval |
| Game-theory-assisted early termination ([2603.15907](https://arxiv.org/html/2603.15907v1)) | Episode ends once a Guard senses the Strike drone, with the analytic payoff as terminal reward; mean reward +10% (1v1), +19% (3v1) |

### Most relevant works

| Work (year) | Task | Algorithm and self-play | Sim | Team size | Real flight |
|---|---|---|---|---|---|
| [OPEN](https://arxiv.org/html/2409.15866v4) (RA-L 2025) | 3 pursuers vs 1 scripted faster evader | MAPPO, LSTM evader predictor, adaptive start generator | OmniDrones | 3v1 | Crazyflie, off-board, motion capture |
| [VolleyBots](https://arxiv.org/html/2502.01932) (NeurIPS 2025) | Drone volleyball | SP / FSP / PSRO; exploitability and Elo | OmniDrones | 1v1, 3v3, 6v6 (6v6 never converged) | One drone, Orin on board |
| [HCSP](https://arxiv.org/html/2505.04317v5) (CoRL 2025) | 3v3 volleyball | Skills → PSRO-Nash high level → joint fine-tune | OmniDrones | 3v3 | Preliminary |
| [UZH + GDM racing](https://arxiv.org/html/2605.22748) (2026) | Multi-drone racing | Recurrent PPO; league 75% past self (power-law) + 20 fixed policies; Perceiver over opponents | Flightmare | up to 4 | 4 drones, off-board |
| [AgileFlight](https://arxiv.org/html/2512.11781v1) (2025) | 1v1 racing | Sparse win-only self-play | Isaac Lab | 1v1 | Zero-shot |
| [AMSPBH](https://arxiv.org/abs/2506.02849) (2025) | 1v1 pursuit-evasion | PSRO-style, 13 generations, Hedge opponent sampling | Isaac Lab, 6144 envs | 1v1 | Crazyflie, up to 4.87 m/s |
| [AgilePE](https://arxiv.org/abs/2608.14135) (2026) | Pursuit-evasion | Prioritised fictitious self-play (PFSP) with opponent pool | OmniDrones | – | Zero-shot, PX4 |
| [HARL-A](https://arxiv.org/html/2510.01264v1) (2025) | Sumo, soccer, Crazyflie "Galaga" | HAPPO, one critic per team; alternating updates; no pool | Isaac Lab | 2v2 | No |
| [GT-assisted border defense](https://arxiv.org/html/2603.15907v1) (2026) | Guards vs 1 | MAPPO, BenchMARL | VMAS | 1v1, 3v1 | No |
| [GNN perimeter defense](https://arxiv.org/abs/2301.09689) (2023) | Perimeter game | GNN imitating a centralised expert | sim | Small → large | No |
| [STLGame](https://arxiv.org/html/2412.01656v1) (L4DC 2025) | STL reach-avoid | FSP with gradient best responses; exploitability ≈ 0 | sim | 1v1 | No |
| [HOLA-Drone](https://arxiv.org/abs/2409.08767) (2024) | Pursuit with unseen teammates | Open-ended hypergraph learning | Kinematic | multi | Crazyflie, no sim-to-real measures |

### Self-play schemes and pitfalls

- **No scheme dominates.** VolleyBots 1v1: SP exploitability 48.6 vs PSRO-Nash 10.7. In 3v3, PSRO-Nash has the best Elo (1268) but SP has lower exploitability (25.8 vs 35.8).
- **Scripted play can win.** At AAMAS 2024 maritime capture-the-flag, rule-based agents beat the deep-RL entries ([Pyquaticus](https://arxiv.org/pdf/2404.17038), [repo](https://github.com/mit-ll-trusted-autonomy/pyquaticus)).
- **Large teams may not converge** (6v6 volleyball never did).
- **Implementation (the researcher's suggestion):** keep K frozen snapshots outside the learner, split environment indices across them, run each in `torch.no_grad` on its slice, and sample with PFSP/Hedge weights from recent win rates. Suggested buckets: about 40% latest vs latest, 35% PFSP over past snapshots ([AlphaStar](https://deepmind.google/discover/blog/alphastar-grandmaster-level-in-starcraft-ii-using-multi-agent-reinforcement-learning/)-style), 25% scripted (matching or Apollonius Guards; rush, split, feint and plan-switch Strikers). Add exploiters that beat the main policy to the pool.
- **Code to borrow:** TimeChamber (PFSP pool, vectorised Elo) and HARL-A ([site](https://directlab.github.io/IsaacLab-HARL/)).

### Variable team size and drop-outs

| Pattern | Evidence |
|---|---|
| Entity encoders (deep sets, attention) | Deep-sets policy on board Crazyflies ([2109.07735](https://arxiv.org/pdf/2109.07735)); attention on board at about 1 kHz on a 168 MHz MCU ([2309.13285](https://arxiv.org/html/2309.13285v2)) |
| Limited size generalisation | Perceiver policy fell to about 56% completion at 8 agents, twice the training maximum (UZH) |
| Recurrence for partial observability | LSTM-256 (UZH); LSTM predictor (OPEN) |
| Drop-out and noise training | Measurement noise and opponent-observation dropout (UZH); agent-failure resilience ([RADAR](https://mlanthology.org/aaai/2021/phan2021aaai-resilient)) |
| One critic per team | Shared critic's advantages cancel in zero-sum games (HARL-A) |

The researcher's suggestion: MAPPO with one shared actor per team, ego state centred on the zone, padded entity lists (N_max = 10) with masks through attention or deep sets plus a GRU, and observation sharing with simulated delay and packet drops instead of learned communication. Use IPPO as a sanity baseline; HAPPO only if teams become heterogeneous. Go flat first and move to HCSP-style skills (tag, block, reach/feint) plus learned assignment if 5v3 stalls; hierarchy has evidence (HCSP 82.9% average win rate; an LLM skill selector at 46.4% vs a behaviour tree at 51.5%, both beating flat RL, [2606.20014](https://arxiv.org/pdf/2606.20014)).

### Start-position and team-size curricula

- OPEN archives start configurations with success in [0.5, 0.9], expanding locally (p 0.7) and exploring globally (p 0.3).
- PLR, Robust PLR and ACCEL ([accelagent](https://accelagent.github.io), [2110.02439](https://ar5iv.labs.arxiv.org/html/2110.02439)); MAESTRO builds a joint environment–opponent curriculum for zero-sum games ([2303.03376](https://arxiv.org/abs/2303.03376)).
- The researcher's suggestion: uniform starts over the arena from day one plus the archive; team sizes Guards 1–6 and Strikers 1–4; random speed ratios; mid-episode teammate removal and Strike plan switches; optional early termination for 1v1 endgames.

### Evaluation suite (the researcher's suggestion)

1. Win rate against scripted classical opponents.
2. Held-out start distributions and unseen team sizes.
3. Cross-play matrix over seeds; Elo or TrueSkill over the snapshot pool.
4. Exploitability: train a best response with a fixed budget.
5. Drop-out, plan-switch and comms-delay stress tests.
6. Safety-filter intervention rate and minimum separation.

### Rewards

- OPEN: +6 capture bonus per pursuer, −0.1 × distance, −10 per collision, smoothness added in stage 2.
- Border game: terminal payoff is the Strike drone's distance from the target at the tag (zero-sum).
- The researcher's suggestion: ±1 per zone reach or tag plus a team terminal reward; potential-based dominance-region shaping annealed to zero; smoothness in stage 2; a small penalty proportional to safety-filter correction.
- Hyperparameter starting points (the researcher's suggestion; no source gives them at this scale): 4096 envs, 32–64-step rollouts, 4–5 epochs, 4–8 minibatches, learning rate 3e-4 with adaptive KL, γ 0.99, GAE λ 0.95.

## 8. Throughput

**No measured env-steps/s exists for any Isaac Lab quadrotor task, single- or multi-agent, on any GPU.** Neither ARL task publishes results, and most Isaac papers omit wall-clock time.

| Source | Setup | Figure | Hardware |
|---|---|---|---|
| [Isaac Lab v2.1.1 benchmarks](https://isaac-sim.github.io/IsaacLab/v2.1.1/source/overview/reinforcement-learning/performance_benchmarks.html) | Cartpole-Direct, 4096 envs | 1.1M step FPS; 510k with training | RTX 4090 |
| same | G1 rough, 4096 envs | 94k | RTX 4090 |
| same | RGB camera 100×100, 1024 envs | 50k step FPS; 32k with training; 16.7 GB VRAM | RTX 4090 |
| [OmniDrones](https://arxiv.org/pdf/2309.12825) | 4-drone task, 4096 envs | about 310k FPS | RTX 4090 |
| [Aerial Gym](https://arxiv.org/html/2503.01471v1) | 65k envs | 4.43M samples/s | RTX 3090 |
| same | 270×480 depth, 2048 envs | 2,750 FPS | RTX 3090 |
| same, as read for clutter | Physics only, 4096 envs; 270×480 depth with 20 cubes | 1.43M samples/s; about 3.9k depth frames/s | not stated |
| [GaussGym](https://arxiv.org/abs/2510.15352v1) (legged) | Splats in a vectorised simulator, 2,500 scenes | over 100k steps/s | not stated |
| [DiffAero](https://arxiv.org/html/2509.10247v1) | 8192 envs | 3.4M physics steps/s; 96k depth frames/s at 64×64 | RTX 4090 |
| [Crazyflow](https://arxiv.org/abs/2606.01478) | Sampling-based obstacle avoidance | > 0.5 billion steps/s | not stated |
| [RLtools](https://arxiv.org/abs/2311.13081) | Single quadrotor | about "5 months of flight per second"; 18 s to real flight | laptop GPU |
| [VisFly](https://arxiv.org/html/2407.14783v4) | 64×64 rendering | about 10k FPS | not stated |
| [TimeChamber](https://github.com/floodsung/TimeChamber) | Self-play, 4096 envs | about 80k FPS | laptop GPU |
| [VMAS](https://arxiv.org/pdf/2207.03530) | 30k parallel simulations | under 10 s | not stated |

**Sensing sets throughput once obstacles arrive.** DiffAero simulates 3.4M physics steps/s but renders 96k depth images/s; Aerial Gym runs 1.43M physics samples/s but about 3.9k depth frames/s. The researcher rates sensing as a 10–40× slowdown of the point-mass simulator (estimate), so the benchmark measures steps/s at 0, 10 and 50 obstacles, including N·rays and N² line-of-sight queries.

**Compute reported for team games.** UZH racing: about 200M steps in 27 h on one RTX 4090 with 144 envs × 4 drones. OPEN: over 2B samples to reach a 90% capture rate. HCSP: 4096 envs for skills, 512 for the high level. AMSPBH: 6144 envs, 500 Hz sim, 50 Hz policy.

**Estimates (not measured).**

- State-based single quadrotor in Isaac Lab: roughly 0.3–1M env-steps/s on a 4090/5090 at 4–16k envs, about a third to half of that on an RTX 5070 Ti laptop. A 4v4 game has 8 articulations per env, so env-steps/s falls roughly in proportion. Policy steps = physics steps ÷ decimation.
- Point mass with PX4 velocity response and batched safety filter (tier 1): well above 10⁵ steps/s.
- Version effects: 3.0-beta2 lost about 20% Humanoid throughput versus 2.3.2; maintainers say it is patched, but full recovery in GA is unverified.

## 9. Realistic environments

Games are played in realistic 3D worlds, the lab's construction-site world first (owner's decision). This section covers what the lab already has, where other worlds come from, and how thousands of games share one world.

### The lab's construction-site world

| Item (measured from the repository's USD files) | Value |
|---|---|
| Origin | The lab's UE4 export `Scene02_nohumans.usd`, unmodified, kept inside this repository folder at `localisation/scenes/construction_site/source/AI_training/Construction_site/` (git-ignored; it never goes through GitHub, see `localisation/scenes/construction_site/README.md`). A separate UE 4.21 project in `localisation/ConstructionSite(UE4)/` (1.6 GB, gitignored as "not ours to version") looks like a Marketplace pack; the docs do not say Scene02 came from it |
| Licence | Bought by the owner from CGTrader (owner, 16 November 2026): rendered clips and stills may be committed; the asset files (`source/`, `build/`) never go in git |
| Size | 546 × 575 × 137 m (height = crane tops); Z up, 1 m per unit |
| Geometry, collision | 25,437 prims, 5,622 meshes, 5.79 M triangles, one distant light; 5,613 meshes already carry PhysX colliders (4,963 convex hull, 646 triangle mesh); drones collide with the site in the AirStack simulator |
| Files (from the repository root) | `localisation/scenes/construction_site/build/construction_site_full.usdc` (50.2 MB); `construction_site_r40.usdc` (34.1 MB: 40 m crop, 4.8k prims, 68 materials); wrapper `construction_site_arena.usda`; scripts `crop_site.py`, `build_arena_usda.py`, `fix_abs_paths.py`, `install.sh`; `README.md`, `VALIDATION.md`. Textures 128×128 px, except a 1024² landscape set |
| Install | `install.sh` copies to `~/docker/isaac-sim/data/scenes/construction_site`; the container mounts it under `/isaac-sim/.local/share/ov/data`; the launcher reads `ENV_USD` |
| Drone start | The wrapper shifts the site so drones start on a level, clear patch (4 m clear radius; 135 props within 12 m). README (+32.0, +12.5) and wrapper (+29, +12.5) disagree on the shift |
| Observed in the AirStack simulator (RTX 5070 Ti, 12 GB, headless) | Full site, 1 drone: real-time factor 2.2, 4.9 GB GPU. Full site, 3 drones + camera: 1.4, 4.3 GB, camera 41 Hz. 40 m crop, 3 drones + camera: 1.4, ≤ 4.0 GB. Two drones: not recorded |
| Known costs | Stage load about 90 s longer; absolute texture paths need `fix_abs_paths.py`; referencing Scene02 directly is too heavy, hence the flattened files |

### Sources compared

| Source | Realism | Scale | Licence | Effort into Isaac Sim 5.1 | Use |
|---|---|---|---|---|---|
| Isaac Sim bundled: grid rooms, Simple Room, 4 warehouses, hospital, office ([5.1 list](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/assets/usd_assets_environments.html)) | Medium | Indoor only; sizes not published | NVIDIA GPUs only, no redistribution ([licence](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/common/license-isaac-sim-additional.html)) | None | All tiers (bake for tier 1) |
| SimReady: over 2,000 assets ([Unite.ai](https://www.unite.ai/?p=491523)); SimReady-Warehouse-01, 753 assets, 14.4 GB ([HF](https://huggingface.co/datasets/nvidia/PhysicalAI-SimReady-Warehouse-01)) | High (props) | Industrial, residential, hospital; no construction category seen | Warehouse CC-BY-4.0; library not stated | Low | Clutter |
| The lab's Unreal construction site | Medium–high | Outdoor, site | Depends on the asset's Marketplace licence | Done; Unreal-to-USD pitfalls are lost materials, dropped physics, texture OOM ([forum](https://forums.developer.nvidia.com/t/ue5-3-export-to-omniverse-loses-a-lot-of-materials/316236)) | All tiers |
| Pegasus / OmniDrones / Aerial Gym | Mostly abstract | Procedural | Open source | Low; Aerial Gym ray-casts against one shared mesh ([arXiv](https://pdf.arxiv.org/pdf/2503.01471)) | Pattern for tier 1 |
| Infinigen Indoors | Procedural, photoreal | Indoor; outdoor not tested in Isaac Sim | Open source | Low: `usdc --omniverse` export, 5.1 tutorial ([docs](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/replicator_tutorials/tutorial_replicator_infinigen_sdg.html)) | Held-out indoor worlds |
| HM3D (Matterport scans) | Real scans | Indoor homes | Academic, non-commercial, revocable ([Habitat](https://aihabitat.org/terms-of-use)) | Medium | Indoor generalisation |
| World Labs Marble | Generated splat + collider mesh | Indoor example only | Paid plan to export ([NVIDIA blog](https://developer.nvidia.com/blog/simulate-robotic-environments-faster-with-nvidia-isaac-sim-and-world-labs-marble)) | Medium; scale set by hand | Cameras |
| Own scan: photogrammetry or LiDAR → mesh | Real geometry | Site-scale | RealityScan free under US$1M revenue; Epic may train on scans unless you opt out ([licence](https://www.realityscan.com/license)) | Medium | All tiers |
| Own scan: 3D Gaussian splats via 3DGUT → NuRec USDZ | Photoreal, visual only | Any; GPU memory grows with size | — | Isaac Sim ≥ 5.0; collider added by hand ([NuRec](https://docs.nvidia.com/nurec/robotics/neural_reconstruction_mono.html)) | Cameras only |
| OpenStreetMap via Blosm; Singapore HDB3D ([data](https://github.com/ualsg/hdb3d-data)) | Block buildings (LoD1) | City | OSM ODbL, share-alike ([OSM](https://www.openstreetmap.org/copyright)); HDB3D with attribution | Medium | Urban geometry |
| BIM/IFC files | Exact as-designed | Building or site | CAD Converter proprietary; most IFC properties dropped ([docs](https://docs.omniverse.nvidia.com/kit/docs/omni.kit.converter.cad/latest/Overview.html)) | Medium | All tiers |

No construction-site generator or ready-made construction USD scene turned up. Not usable:

- **Google Photorealistic 3D Tiles (via Cesium):** visualisation only, no caching or offline use, no derived 3D models ([policy](https://developers.google.com/maps/documentation/tile/policies)); tiles also go black or blurry at drone heights ([thread](https://community.cesium.com/t/cesium-isaac-sim-terrain-goes-black-at-drone-scale-10-500ft-google-photorealistic-3d-tiles-not-loading-close-up/45997)).
- **Singapore OneMap3D / SLA CityGML:** view-only; API access needs an NDA; CityGML covers Ang Mo Kio only ([SLA](https://sla.gov.sg/geoworks/programmes/programmes-geoworks-supports/onemap3d-developer-programme)).
- **TartanAir V2 / TartanGround** (CC-BY-4.0, [tartanair.org](https://tartanair.org/)) have no USD or environment release; **AirSim binaries** use proprietary assets that cannot be redistributed ([AirSim](https://microsoft.github.io/AirSim/unreal_custenv/)).

### One shared world for thousands of games

**Tier 1 (PyTorch).** Bake a distance field with Warp `mesh_query_point_sign_winding_number`, which handles meshes that are not watertight, as Unreal exports and scans usually are ([Warp](https://nvidia.github.io/warp/stable/language_reference/_generated/warp.mesh_query_point_sign_winding_number.html)). Store it as a torch grid, sample it with trilinear `grid_sample`, and use its gradient as the surface normal. Each game applies its own random transform to the query points and adds clutter as the minimum of primitive distance fields; several worlds fit in one `[W, X, Y, Z]` tensor.

| 100 × 100 × 30 m (the researcher's arithmetic) | Voxels | fp16 | fp32 |
|---|---|---|---|
| 20 cm | 37.5 M | 75 MB | 150 MB |
| 10 cm | 300 M | 600 MB | 1.2 GB |
| 10 cm, 1-bit occupancy | 300 M | about 38 MB | – |

| Tier 2 (Isaac Lab) | Fact |
|---|---|
| Shared prim, filtering | A prim outside the replicated envs "is instantiated once" ([cloning](https://isaac-sim.github.io/IsaacLab/develop/source/how-to/cloning.html)); `filter_collisions` (default on) stops envs colliding with each other but keeps collisions with global prims; drones in one game still collide ([config](https://isaac-sim.github.io/IsaacLab/v3.0.0-EA/_modules/isaaclab/scene/interactive_scene_cfg.html)) |
| Overlapping games | PhysX 5.5 filters by environment ID in the GPU broadphase ([PxActor](https://nvidia-omniverse.github.io/PhysX/physx/5.5.0/_api_build/classPxActor.html)), but Isaac Lab 3.0 warns that large overlapping layouts "can still exhaust broadphase pair capacity" ([OvPhysX](https://docs.nvidia.com/isaaclab/concepts/ov-phys-x)). Compromise: K copies of the world, each hosting N/K overlapping games; raise K until the broadphase stops overflowing (the researcher's suggestion) |
| Colliders | World as one static triangle mesh ([performance](https://isaac-sim.github.io/IsaacLab/v3.0.0-beta2/source/how-to/simulation_performance.html)); GPU convex hulls cap at 64 vertices ([limits](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/physics/physics_resources.html)); SDF meshes are expensive; drones as spheres or boxes |
| Ray casting (2.3.2) | `RayCaster`: "only a single static mesh", fine for one merged world ([cfg](https://raw.githubusercontent.com/isaac-sim/IsaacLab/v2.3.2/source/isaaclab/isaaclab/sensors/ray_caster/ray_caster_cfg.py)); `MultiMeshRayCaster`: `is_shared`/`reference_meshes` and `track_mesh_transforms=False` for static meshes ([cfg](https://raw.githubusercontent.com/isaac-sim/IsaacLab/v2.3.2/source/isaaclab/isaaclab/sensors/ray_caster/multi_mesh_ray_caster_cfg.py)); stale readings after teleport reported in 2.2.1 ([forum](https://forums.developer.nvidia.com/t/multimeshraycaster-data-pos-w-ray-hits-w-fails-to-update-after-dynamic-teleportation-in-apply-action/369856)) |
| Cameras | RTX partitions "must remain spatially separated" ([renderers](https://docs.nvidia.com/isaaclab/concepts/renderers)): overlapping games need Warp ray-cast depth or separate world copies |
| Limits | The 12 GB laptop is below the 16 GB minimum: fine for headless physics and ray casting, not camera training. Strip materials from the training copy. No official triangle budget; start at 100k–500k collision triangles (the researcher's suggestion) |

### Real places

- **Scan to mesh.** Photogrammetry or LiDAR of an actual site, with the owner's permission, feeds the same baking pipeline.
- **Gaussian splats are visual only.** NuRec splats have "no inherent collision properties"; collision comes from a hand-added ground plane or an imported mesh ([NuRec](https://docs.nvidia.com/nurec/robotics/neural_reconstruction_mono.html)).
- **Drone real-to-sim works**, all single-drone camera policies with splats for appearance and separate geometry for collision: SOUS VIDE / FiGS, 105 hardware flights zero-shot ([2412.16346](https://web3.arxiv.org/abs/2412.16346)); GRaD-Nav++, 67% on trained and 50% on unseen tasks on hardware ([MSL](https://msl.stanford.edu/bibliography/chen2025grad.html)); FalconGym 2.0, 69 of 70 gates on a Starling 2 ([2510.02248](https://arxiv.org/pdf/2510.02248)); Flying in Clutter, 1,024 envs, 90% in sim and 80% real, with downwash-moved foliage the main real failure ([2512.17349](https://arxiv.org/html/2512.17349v1)).

### Recommended ladder (the researcher's suggestion)

| Rung | Worlds | Tiers |
|---|---|---|
| 1 | Grid worlds plus procedural primitives (today) | Both |
| 2 | Procedural construction-site generator: column grids, half-built slabs, scaffolds, crane mast and jib, containers, material stacks | Analytic distance fields (tier 1); the same layout from USD primitives (tier 2) |
| 3 | The lab's construction site, worked through below | All |
| 4 | More worlds: NVIDIA warehouse, hospital, office; Infinigen interiors; OSM/HDB3D blocks; one held out for testing | All |
| 5 | A scanned real site, meshed and baked the same way | All |
| 6 | Cameras: a splat of the scanned site plus its scan mesh for collision, Isaac Sim ≥ 5.0 or Isaac Lab 3.0 ([notes](https://isaac-sim.github.io/IsaacLab/release/3.0.0-beta2/source/refs/release_notes.html)) | Tier 2 |

The construction site, step by step:

1. In Isaac Sim, merge all meshes, drop foliage and decals, check units (Unreal uses cm), decimate to a collision mesh and export it.
2. Crop to the flight volume and bake a distance field at 20 cm; 10 cm if gaps matter.
3. In Isaac Lab, load the site as one global static triangle-mesh prim with game origins inside it (K copies if the broadphase overflows), `filter_collisions` on, `RayCaster` on the merged mesh.
4. Randomise spawn points and add primitive clutter per game.
5. Check in the AirStack simulator (Pegasus + PX4) on the same USD.

## 10. Training in cluttered environments, and tags by contact

| Work (year) | Task | Environment | Obstacle and opponent observation | Action | Real flight |
|---|---|---|---|---|---|
| [OPEN](https://arxiv.org/html/2409.15866v4) (RA-L 2025) | 3 pursuers vs 1 evader | 4–5 analytic cylinders, adaptive generator | 3 nearest obstacles; evader masked unless in line of sight; predictor | CTBR | Crazyflie, motion capture, virtual evader |
| [DualCL](https://arxiv.org/html/2312.12255v2) (2023) | Pursuit-evasion | 0–3 cylinders; out-of-distribution test scenes | Obstacle position, height, radius | CTBR | Crazyflie, virtual evader |
| [PSTO](https://arxiv.org/html/2603.24238) (2026) | Multi-pursuer | 0–9 boxes, 1024 envs | 120×6 LiDAR grid + intent heatmap | Body-frame velocity, 10 Hz | Outdoor, Mid-360 + Swarm-LIO |
| [Hide-and-seek](https://arxiv.org/pdf/1909.07528) (2019) | Two-team game | Random walls and rooms, MuJoCo | 30 range sensors; line-of-sight and 135° cone masks | Forces | None |
| [Huang et al.](https://arxiv.org/html/2309.13285v2) (2023–24) | Multi-drone navigation | Columns, 20–80% density | 3×3 distance-field patch at 0.1 m | Motor thrusts | 8 Crazyflies, known obstacle list |
| [LEARN](https://arxiv.org/html/2511.17765v1) (2025) | Multi-drone navigation | Cylinders, density 0.1–1.0 | 32 ToF ranges (actor); 3×3 min-distance grid (critic) | Motor thrusts | 6 Crazyflies fully on board, up to 2 m/s |
| [Back to Newton's Laws](https://arxiv.org/html/2407.10648v2) (2025) | Multi-drone navigation | Procedural primitives, differentiable point mass | 16×12 depth; other drones rendered as spheres | Thrust acceleration | 6 drones, up to 20 m/s in a forest |
| [Aerial Gym](https://arxiv.org/html/2503.01471v1) (RA-L 2025) | Navigation | Per-env meshes, Warp BVH | 64-D VAE latent of depth | Velocity + yaw rate | Cluttered corridor, 2.83 m/s |
| [Gavin & Bronz](https://arxiv.org/html/2607.05939) (ICUAS 2026) | Net capture, competitive MARL | Open arena, JAX, 1024 envs | Full state | CTBR vs velocity ablation | None stated |
| [Sanchez Roncero et al.](https://arxiv.org/html/2506.02849v2) (2025; AMSPBH in §7) | 1v1 pursuit-evasion | Open arena | Full state | Rate vs velocity | Crazyflie, up to 4.87 m/s |

### What obstacles change

- **Occlusion is the core difficulty.** Hide-and-seek masks by line of sight and field of view, with an omniscient centralised critic; OPEN masks the evader and predicts its position.
- **Sample cost rises, and plain RL needs curricula.** OPEN's MAPPO baseline needs over 2.0 B samples for about 90% capture with obstacles, which OPEN cuts by over 50%; hide-and-seek needed 31.7 B frames, and batches of 16k or 8k never converged. Without curricula MAPPO "fails entirely" in DualCL's hard settings, and Huang et al. report interactions growing "exponentially" with obstacles.
- **Encoding decides success.** An SDF patch gave 0.79 success, a "nearest-L obstacles" list 0.10 (Huang et al.); the researcher judges a nearest-k list will not scale to a construction site.
- **Chokepoints reward geometry-aware tactics.** Scripted heuristics fall to about 0.01 capture at a wall and 0.2 at a narrow gap, where OPEN reaches 0.99–1.0.
- **Geometry generalises from primitives, given many layouts.** Primitive-trained policies transfer to forests (Back to Newton; [Lee et al.](https://arxiv.org/html/2509.08177v2), 11 out-of-distribution scenes); RL policies overfit below about 4,000 levels ([Cobbe et al.](https://proceedings.mlr.press/v97/cobbe19a.html)).
- **Photorealism matters little without cameras.** Depth policies trained in simulated forests flew in disaster zones and cities ([UZH](https://rpg.ifi.uzh.ch/AgileAutonomy.html)); for racing, randomised appearance sufficed, lighting mattered most ([1905.09727](https://arxiv.org/pdf/1905.09727)); 122 realistic scenes beat 10,000 procedural ones for camera navigation, with gains that "quickly saturate" ([HSSD](https://arxiv.org/abs/2306.11290)).

### Representing the world cheaply

| Need | Cheapest representation |
|---|---|
| Collision, point-mass drone | Analytic primitives (one test per obstacle) or a shared distance-field grid (one trilinear lookup per drone) |
| Range rays | Analytic ray–primitive intersection (DiffAero) or sphere tracing through the distance field |
| Line of sight between drones | Sphere-trace the segment through the distance field, or segment–box tests; drones as spheres in the same query (Back to Newton) |
| Rigid-body cross-check | Warp mesh BVH; Isaac Lab `MultiMeshRayCaster` tracks moving meshes, with the static-only caveat documented for the camera variants ([docs](https://isaac-sim.github.io/IsaacLab/main/source/api/lab/isaaclab.sensors.ray_caster.html)) |
| Memory (the researcher's arithmetic, recomputed) | A 60 × 60 × 20 m site at 0.1 m is 72 M voxels, about 144 MB in fp16, one grid for thousands of games; §9 gives the 100 × 100 × 30 m case |

### What the policy observes

| Observation | Examples | Real sensor |
|---|---|---|
| Range scan | 30 rays (hide-and-seek); 32 ToF ranges, flown (LEARN); 3,200 bins with CTBR via PX4 ([Flying on Point Clouds](https://arxiv.org/html/2503.00496v1)) | ToF array; LiDAR (Mid-360) |
| Distance-field patch | 3×3 grid, 9 values (Huang et al., real Crazyflies) | None: needs a known map and motion capture |
| Depth image or latent | VAE latent of stereo depth (Aerial Gym, flown); 16×12 or 16×9 raw depth (Back to Newton; DiffAero) | Stereo depth (RealSense) |
| Privileged, training only | Fast-marching time-of-arrival map (Lee et al.); ESDF-based CBF reward ([Zhang et al.](https://arxiv.org/html/2602.08653v1)) | None |

Motion capture plus a known map is the accepted first step (OPEN; Huang et al.). The researcher's suggestion for the first obstacle stage: about 32–64 range rays (a horizontal ring plus up and down), a line-of-sight mask, each opponent's last-seen state and a GRU; an archive of unsolved scenes sampled with p ≈ 0.7 and kept while success is 0.5–0.9; replay of states just before collisions (about 5% above PLR in Huang et al.).

### Line of sight and radio links

- Mask opponents by line of sight and give last-seen position and time since seen, a GRU or a predictor (OPEN; PSTO). Train the critic on unmasked state (hide-and-seek).
- Policies still worked at 75% message loss in one dropout study ([2609.14268](https://arxiv.org/pdf/2609.14268)). Radio blockage by buildings is studied mainly as communication loss ([TVT 2026](https://trid.trb.org/View/2731863)).

### Tags by contact

**How the literature defines capture: a radius.** 0.3 m (OPEN); 0.12 m with a 0.1 m drone (DualCL); 0.5 m (Sanchez Roncero et al.); 1.4 m (PSTO); multiplayer reach-avoid games with obstacles also use a capture radius ([Chen, Zhou & Tomlin](https://arxiv.org/pdf/1611.00450)). Here, contact is sphere overlap at r_a + r_b, with these Starling 2 Max sizes measured from `AirStack/simulation/isaac-sim/assets/robots/starling2max.usd`:

| Item | Value |
|---|---|
| Enclosing sphere, props included | radius 0.248 m, centre (0, 0, 0.023) m → contact below 0.50 m between centres |
| Body mesh; rotors | Body x ±0.108, y ±0.143, z −0.068 to +0.052 m; rotor origins (±0.095, ±0.13, 0.0195) m, prop radius about 0.09 m |
| Mass | 0.477 kg body + 4 × 0.02 kg rotors = 0.557 kg |
| Simulator collision | Convex hull on the body and each of 4 rotors; authored `extent` (±0.218 × ±0.225) is stale, ignore it |

| Study (velocity vs body-rate control) | Opponent | Velocity-level pursuer | Body-rate (CTBR) pursuer |
|---|---|---|---|
| [Gavin & Bronz](https://arxiv.org/html/2607.05939) | CTBR evader | 17.7% | 88.4% |
| same | APF evader | 59.0% | 88.1% |
| [Sanchez Roncero et al.](https://arxiv.org/html/2506.02849v2) | Rate-control evader | 0.51 | 0.95 |

Caveat: Gavin & Bronz's velocity interface is a fast INDI inner loop, not PX4 at 20 Hz, and no source shows that 20 Hz velocity commands with 0.2–0.7 s lag are too slow.

**The researcher's estimate, not a sourced result:** miss distance ≈ ½·a·τ², with a the evader's sideways acceleration and τ the pursuer's tracking lag. At a = 3 m/s², τ = 0.2 s gives about 0.06 m and τ = 0.7 s about 0.7 m, beyond the 0.50 m contact distance; §5's estimate of PX4's default lag is 0.67 s. Hence tier 1 models PX4's velocity tracking lag explicitly, randomised 0.2–0.7 s (the researcher's suggestion), or simulated contacts look too easy.

**Handling contact.**

- Tier 1: contact is a sphere-overlap event; the tagged Strike drone leaves the game. Also removing the Guard drone with probability p is a design choice to ablate (the researcher's suggestion).
- Rewards: terminal reward for the contact; shape with closing velocity, or use proportional navigation ([FRPN](https://arxiv.org/pdf/2405.13542)) as a scripted baseline. Gavin & Bronz softly penalise pursuer–evader body contact and end the episode on pursuer–pursuer collision.
- Tier 2: Isaac Lab `ContactSensor` force matrices log drone–drone contact ([docs](https://isaac-sim.github.io/IsaacLab/main/source/concepts/sensors/contact_sensor.html)). In the AirStack simulator, drone–drone contact is undocumented and untested.
- Real flights: published work uses a virtual contact distance (OPEN and DualCL fly a virtual evader), not impact. Physical contact damages drones and is a hazard.

### Safety filters that exclude some pairs

No published work exempts opponents from a CBF. Nearest works: "role-dependent engagement constraints" ([2607.10986](https://arxiv.org/abs/2607.10986), abstract only); SCOPE, which constrains separation among all UAVs and from obstacles ([IJCAI-26](https://www.ijcai.org/proceedings/2026/0007.pdf)); an ESDF-based CBF as a training reward with a depth point-cloud HOCBF at deployment (Zhang et al.). The researcher's risk: drones outside each other's filter can collide at high closing speeds, so the filter runs in training as well as flight.

### Scripted opponents in clutter

- **Guard drones (pursuit):** Angelani, Janosov, APF (OPEN); FRPN and APF (Gavin & Bronz); assignment by maximum matching (Chen, Zhou & Tomlin).
- **Strike drones (evade, reach the zone):** APF with tangential wall-following fields (PSTO); Dijkstra or fast-marching cost maps to the zone (Zhang et al.; Lee et al.).

## 11. Not verified

**Isaac Lab and frameworks**

- Any measured env-steps/s for Isaac Lab quadrotor tasks; §8 figures for them are estimates.
- Training curves or wall-clock times for the ARL tasks; whether they run under kit-less `physics=ovphysx` or need full Isaac Sim 6.2.
- Whether 3.0 GA fully recovers the beta2 throughput regression; whether Newton is the 3.0 default ([#8110](https://github.com/isaac-sim/IsaacLab/pull/8110) open).
- Whether skrl multi-agent works with `--distributed`; whether other train scripts support it.
- Isaac Sim 5.1 behaviour on the RTX 5070 Ti laptop GPU (no reports found).
- Whether `MultiMeshRayCasterCamera` can track other drones as moving targets.
- The exact tree generated by `./isaaclab.sh --new`.
- DiffAero's MAPPO (in the paper, not the README) and its "42% lower tracking error" (secondary summaries only).
- Single-author repos (Quadsim, a "PX4-calibrated" PPO repo).

**Sim-to-real and PX4**

- Swift's policy rate; the action space in "Reaching the Limit"; RLtools network size and history length.
- Which Aerial Gym tasks transferred to hardware.
- Whether PX4 PR #26768 (MAVLink offboard setpoints into external modes such as RAPTOR) is merged; how `mc_nn_control` is activated.
- Whether PX4 1.14 on VOXL2 has the attitude reference model (`MC_REF_W_N`).
- The Starling 2 Max's tuned `MPC_*` values; VOXL2 Wi-Fi offboard latency (none published; measure it).
- The Sim-to-(Multi)-Real sim-to-sim quote.

**Two-team games**

- The NUS MARMot "skills + plays + success-predicting planner" work and its ~20% 2v1 hold rate, proposed as the bar to beat; no NUS MARMot drone RL paper was found.
- Mangharam STL-guided MARL for capture-the-flag ([2306.06808](https://arxiv.org/abs/2306.06808) found, benchmark not confirmed); a Google DeepMind 2025 multi-robot soccer paper (only 2023 OP3 work, [2304.13653](https://arxiv.org/pdf/2304.13653)); no Vijay Kumar lab drone RL paper found.
- Tsinghua affiliation of OPEN and DualCL ([2312.12255](https://arxiv.org/abs/2312.12255)); that the GNN expert is maximum matching; Pyquaticus real-boat numbers ([PDF](https://calinbelta.com/wp-content/uploads/2026/03/pyquaticus-1.pdf)); HCSP's real-flight appendix; whether Yan, Shi & Zhong cover circular targets.
- Wall-clock training time for any Isaac-based team game.

**Realistic environments**

- "Rivermark" as an NVIDIA asset (found only in a community dataset, [HF](https://huggingface.co/datasets/aiozai/HierSceneDataset/blob/main/README.md), no licence); downloadable USD worlds for AirStack, TartanAir V2 or TartanGround; sizes of NVIDIA's bundled environments; licences of the SimReady Central Library, Infinigen and ScanNet++.
- An explicit machine-learning ban in the Google 3D Tiles terms (only "visualisation only" and "no derived 3D models" are verified); collision on Cesium tilesets.
- Whether Isaac Lab 2.3.2 / Isaac Sim 5.1 filter by PhysX environment ID; whether env spacing 0 works in 2.3.2; a "15–50% slowdown" for overlapping environments; PhysX and Warp triangle or memory limits; distance-field baking times; the 3DGRUT v1.1.0 mesh-injection tool and the `add_mesh_to_usdz.py` script.

**Cluttered training and contact tags**

- A source arguing that 20 Hz velocity commands with 0.2–0.7 s lag are too slow; a speed ratio that makes contact capture feasible against an evasive drone; UED (PLR, ACCEL) applied to quadrotor games beyond OPEN and DualCL; training samples and wall-clock time for PSTO and DualCL.
- Capture radius, speeds and indoor flight details of Gavin et al. 2026 ([2603.16279](https://arxiv.org/abs/2603.16279)); full FRPN details; exact DiffAero memory figures; the Isaac Lab release in which `MultiMeshRayCaster` gained moving meshes.
- Whether Zhou et al. (Science Robotics 2022) is ESDF-free ([news](https://techxplore.com/news/2022-05-drone-swarms-autonomously-thick-forest.html)); ViPER's named baselines ([PMLR](https://proceedings.mlr.press/v270/wang25k.html)); whether the 75% message-loss policies were trained with or without dropout.

**Local inspection (not found)**

- A licence for the construction-site asset; any real-time factor for one or two drones on the full site beyond §9's figures.
- Drone–drone contact in the AirStack simulator is undocumented and untested: no collision groups or filtered pairs exist under `AirStack/simulation/isaac-sim`, so PhysX would treat the convex hulls as colliding (an inference from the USD).

**Where the reports disagreed, and how this digest resolves it**

- **AgilePE's simulator.** The Isaac Lab ecosystem report could not find it; the sim-to-real report, which read the paper for transfer details, gives OmniDrones. This digest uses OmniDrones.
- **Agile Flight Emerges speed-gap figure.** The sim-to-real report gives 44.7% from the paper; the team-games report lists 47% and 3.2× from secondary summaries as unverified. This digest uses 44.7%.
- **v2.3.2 date.** The ecosystem report gives the release as 2 Feb 2026; the local inspection dates the tag 29 Jan 2026. Both are kept: tag and release differ.
- **Local checkout.** The ecosystem report warned the local copy might be a 3.0 `develop` build; the local inspection shows `main`, 25 commits past v2.3.2, without the Lee controllers. This digest follows the local inspection.
- **Base recommendation.** The ecosystem report recommends Isaac Lab 3.0 with `LeeVelController` as the training base now; the sim-to-real and team-games reports recommend a PyTorch PX4-response model for bulk training and Isaac Lab as a cross-check, noting the Lee loop is P-only. The owner's two-tier decision follows the latter, with 3.0 deferred to the RTX 5090 machine.
- **Distance-field memory.** The clutter report gives "about 14 MB" for 60 × 60 × 20 m at 0.1 m in fp16; 72 M voxels × 2 bytes is about 144 MB, consistent with the environments report's arithmetic. This digest uses 144 MB.
- **Site prim count.** `VALIDATION.md` says 125k prims; the local measurement gives 25,437 (meshes, triangles and colliders agree). This digest uses the measurement.
