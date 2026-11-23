ARCHIVED 2026-11-23 · superseded by [S2B_RESULTS.md](../S2B_RESULTS.md); kept for the record. Start at [../README.md](../README.md).
INTERNAL · a build plan written for the lab's AI coding assistants; history, not instructions. Results: [../README.md](../README.md).

# S2b: the S2 Game on Isaac Lab Drones, Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task by task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run the S2 game, with its rules, observations, strategy contract, scoring tool and adapters unchanged, on rigid-body Starling drones in Isaac Lab 2.3.2, flown by a batched copy of PX4 1.14's control cascade (velocity → acceleration → attitude and thrust → body rates → rotor forces) with the real drone's gains. Then compare it with the PyTorch tier (tier 1, Starling layer, exploratory model) using step tests, the scripted reference games and a throughput measurement. Render a few games to MP4. Run the S2 stand-in trainer on both backends.

**Architecture:** A third motion backend, `physics`, sits next to "pure partner rules" and "Starling layer" inside `SvgGame` (`core/game.py`). It uses the same command chain as the Starling layer (the commander copy, then the safety filter on every pair), extracted into one shared class. The trajectory setpoint then goes to `PhysicsDrone`, which runs the PX4 cascade, the rotor model and a rigid-body world for 10 physics steps per 0.05 s game tick. The world sits behind one small protocol with two implementations: `IsaacWorld` (the only Isaac Lab code, in `compat/isaaclab_232.py`) and `TorchRigidBodyWorld` (a pure-PyTorch test oracle, so every CPU test runs without Isaac Sim). The scoring tool, the strategies and the S2 adapters see no difference except the backend name.

**Tech Stack:** Python 3.11, conda `env_isaaclab` (torch 2.7.0+cu128, Isaac Sim 5.1.0, Isaac Lab 2.3.2 at `~/IsaacLab`, skrl 2.1.0, gymnasium 1.2.1, imageio + imageio-ffmpeg, opencv-python-headless, all present on 16 November 2026), container image `svg-training:isaaclab-2.3.2` (`docker/run.sh`). PX4 source is read with `git -C ~/PX4-Autopilot show v1.14.0:<path>` (read-only). No `pip install`.

**Spec:** the S2 design [2026-11-15-s2-game-and-plug-in-design.md](2026-11-15-s2-game-and-plug-in-design.md) §4a, §5, §7, plus this plan's own [Design](#design) section below (the owner's decision of 16 November 2026 is the spec; no separate spec file). Rules: [../../STANDARDS.md](../../STANDARDS.md) §3, §5, §6 (rules 7 and 8), §7, §8, §9, §11.

**Status:** approved by the owner 16 November 2026 with the answers at the end of this file; starts after S2 closes.

## Facts this plan rests on (read 16 November 2026)

| Fact | Source |
|---|---|
| The drone's PX4 gains: `MPC_XY_P` 0.95, `MPC_Z_P` 5, `MPC_XY_VEL_P/I/D_ACC` 1.8 / 0.4 / 0.2, `MPC_Z_VEL_P/I/D_ACC` 8 / 2 / 0, `MPC_VELD_LP` 5 Hz, `MPC_XY_VEL_MAX` 3, `MPC_Z_VEL_MAX_UP/DN` 2 / 0.6, `MPC_TILTMAX_AIR` 45, `MPC_THR_HOVER` 0.165, `MPC_THR_MIN/MAX` 0.04 / 0.6, `MPC_THR_XY_MARG` 0.3, `MC_ROLL_P`/`MC_PITCH_P` 8, `MC_YAW_P` 2.8, `MC_YAW_WEIGHT` 0.4, `MC_ROLLRATE_P/I/D` 0.064 / 0.1 / 0.0013, `MC_PITCHRATE_P/I/D` 0.064 / 0.096 / 0.0011, `MC_YAWRATE_P/I/D` 0.07 / 0.5 / 0, all `_K` 1 and `_FF` 0, rate limits 130 / 130 / 150 °/s, integrator limits 0.3, `IMU_DGYRO_CUTOFF` 40 Hz, `IMU_GYRO_RATEMAX` 800 Hz, `MC_AIRMODE` 0, `CA_ROTOR0..3_PX/PY` ±0.085 / ±0.0625 m, `KM` +0.05, +0.05, −0.05, −0.05 | `../starling_1_indoor_params.params` (read-only) |
| The 13 November flight logs show 3.0 m/s, `MPC_ACC_HOR` 3 and tilt 30° (drone_1) / 45° (drone_2) | `../docs/CONFIG.md` "Sim airframe" table; STANDARDS §5 |
| Starling inertials (CMU system identification): mass 0.557 kg, inertia 0.002943 / 0.001857 / 0.004649 kg·m², k_f 3.964738e-6 N/(rad/s)², k_m 5.38697e-8 N·m/(rad/s)², ω_max 1,450 rad/s, motor time constant 55 ms rising / 85 ms falling, centre of mass about 1 mm forward and 7.4 mm up | `../docs/CONFIG.md` "Inertials", "Thrust / motors"; `../isaac_sim/Starling 2 Max Sys ID Results - Slite.pdf` |
| From these: full rotor thrust 8.33586 N, weight 5.46417 N, hover rotor command 0.16388 (the drone's `MPC_THR_HOVER` is 0.165), hover rotor speed 586.98 rad/s, yaw torque per newton of thrust k_m/k_f = 0.0135872 m (the sim airframe's `KM` 0.0136) | arithmetic on the row above |
| CAD rotor positions ±0.095 / ±0.13 m (sim airframe `10090_pegasus_starling2max`, same signs and order as the drone's `CA_ROTOR*`); the drone's own parameters say ±0.085 / ±0.0625 m. Ixx 0.002943 > Iyy 0.001857 fits the CAD layout, which is wider across (y) than long (x) | `AirStack/simulation/isaac-sim/px4/airframes/10090_pegasus_starling2max` (CHG-0003); inertials above |
| With the real rate gains the AirStack simulator's Starling showed a 9 Hz pitch limit cycle (instant motors, 250 Hz IMU, CAD arms), and CMU's 72 ms motor lag "tumbles" it; the real drone flies the real gains | `../docs/CONFIG.md` rate-loop and motor rows (ledger #10) |
| PX4 1.14 cascade at tag v1.14.0: `PositionControl.cpp` (`_positionControl`, `_velocityControl`, `_accelerationControl`), `ControlMath.cpp` (`constrainXY` :122, `limitTilt` :53, `bodyzToAttitude` :70, `thrustToAttitude` :47), `AttitudeControl.cpp` (`update`), `lib/rate_control/rate_control.cpp` (`update`, `updateIntegral`), `ControlAllocationPseudoInverse.cpp` (`updateControlAllocationMatrixScale`, `normalizeControlAllocationMatrix`), `ControlAllocationSequentialDesaturation.cpp` (`mixAirmodeDisabled` :173, `mixYaw` :206) | `~/PX4-Autopilot`, tag `v1.14.0` |
| The S2 tier 1 Starling layer (exploratory `real_exploratory_v0`) settles slowly: t63 about 0.6 / 0.9 s at start / stop (the real drone about 0.2 s after its setpoint), a mode with a period of about 9 s, head-on closest approach 1.050 m | `runs/sdd/s2/progress.md` (Task 4 re-review); [S1 exploratory record](../../records/2026-11-15_s1_real_px4_exploratory.md) |
| log103 has 12 legs: legs 1, 3, …, 11 are the six held-out legs; held-out RMS of the fitted model 0.058 m/s | S1 exploratory record §3–4; `scripts/fit_real_px4.py` `load_flight`, `make_windows` |
| Tier 2 in S0: 455,300 drone-steps/s at 4,096 games × 3 drones, 100 Hz physics, ARL Robot 1, random thrust, no controller, one full state write per policy step | [S0_RESULTS](../S0_RESULTS.md) |
| Isaac Lab 2.3.2 (+25 commits): `RigidObject.permanent_wrench_composer.set_forces_and_torques(...)` (the old `set_external_force_and_torque` warns "will be deprecated"); `root_physx_view.set_inertias(...)` (as `envs/mdp/events.py:397`); `MassPropertiesCfg` has mass and density, no inertia; headless rendering needs `--enable_cameras` and reads frames with `omni.replicator.core` `render_product` + `"rgb"` annotator (`envs/direct_marl_env.py:501-530`); `DirectMARLEnv.step` resets through `reset_buf.nonzero()` (a host sync) | `~/IsaacLab/source/isaaclab/isaaclab/assets/rigid_object/rigid_object.py:402-450`, `envs/direct_marl_env.py`, `isaaclab_tasks/direct/quadcopter/quadcopter_env.py:154-158` |
| The container mounts only `svg_training/`; the Starling USD (`AirStack/simulation/isaac-sim/assets/robots/starling2max.usd`, 8 MB, body + four 20 g rotor bodies) and `~/flight_logs` are visible only on the host | `docker/run.sh`; `../docs/CONFIG.md` |

## Design

### Intent

The owner, 16 November 2026: "we should just wrap the s2 game as an isaac lab environment and do the rest of the stuff". S2 built the game on two motion paths in PyTorch. S2b adds the rigid-body Starling of DESIGN §4 (tier 2) under the same game, so a strategy can be scored and trained on a drone that tilts, saturates and lags like a Starling under PX4. It also brings forward the part of the S4 cross-check that needs no world: the same commands and games on both tiers, with gates. The lead added two items the same day: the S2 stand-in trainer (S2 Task 10) moves here and runs on both backends, and a short MP4 of the game on Isaac Lab drones.

### Approaches considered

| | A: an Isaac Lab `DirectMARLEnv` task that calls the game's rules from its hooks | **B: physics as a third motion backend inside `SvgGame` (chosen)** | C: a pure-PyTorch rigid body, Isaac only for spot checks |
|---|---|---|---|
| Idea | Isaac Lab owns the loop, resets and episode counters; the rules are split over `_get_dones`, `_get_rewards`, `_reset_idx` | the game owns the loop as in S2; Isaac Lab only integrates the bodies, behind one adapter module | rigid-body equations in torch, no PhysX |
| For | a registered Isaac Lab task; Isaac Lab's own train scripts work | one code path for rules, observations, strategies, scoring, adapters; CPU tests need no Isaac; meets STANDARDS §6 rule 7 directly | fastest, simplest |
| Against | a second reset path (`nonzero` host sync every step); the scoring tool and the S2 adapters would need a second wrapper; rules forked | not a registered Isaac Lab task (a thin shell can be added later) | not what the owner asked for; no contacts, cameras or worlds later |

### Decisions

| # | Decision | Why |
|---|---|---|
| D1 | Approach B. "Isaac Lab environment" means the S2 game running on Isaac Lab physics behind the existing adapters. No `DirectMARLEnv` subclass in S2b. | One code path (owner's part 1); no per-step host sync; the scoring tool and the S2 adapters work unchanged. Open question 1. |
| D2 | Each drone is one `RigidObject` per drone slot (as S0), with no collider, mass and diagonal inertia set from the CMU numbers, and the centre of mass at the body origin. Rotor forces and torques are summed in our own torch rotor model and applied as one body wrench. Not `isaaclab_contrib` `Multirotor` + `Thruster` (STANDARDS §5 named those). | `Multirotor` needs an articulation USD with named thruster joints, and the Starling USD is not one. Our rotor model is testable on CPU and carries the 55 / 85 ms lag on rotor speed, as identified. STANDARDS §5 rule 9's unit trap does not arise. The 7.4 mm offset of the centre of mass is left out and noted. |
| D3 | The cascade runs in PX4's frames (NED world, FRD body) and is ported line by line from v1.14.0. The game, the worlds and Isaac stay in ENU / FLU. The only crossing is `models/frames.py`, with quaternions in **WXYZ** (Isaac Lab 2.3.2) under the name `quat_wxyz` (STANDARDS §6 rule 8). | Copying PX4's equations in their own frames removes a whole class of sign errors; one tested crossing. |
| D4 | The plant uses the **CAD rotor positions** (±0.095 / ±0.13 m). PX4's allocation uses the **drone's `CA_ROTOR*` parameters** (±0.085 / ±0.0625 m, `KM` 0.05), as PX4 on the drone does. Switch `rotor_geometry = "cad" \| "params"` (plant side only). | Closes STANDARDS §5's OPEN row with a reason: CAD and inertia come from the same system identification, and Ixx > Iyy fits the CAD layout. The drone's PX4 really does allocate with its own parameters. Open question 2. |
| D5 | Motor lag **on** (55 ms rising, 85 ms falling, first order on rotor speed). The gains are **never retuned**. If the Task 3 design check finds the default plant unstable (hover tilt spread over 1°), the task stops with BLOCKED and the lead takes the four-variant table to the owner. | Gains come from the drone (STANDARDS §5 rule 2; iron rule 9 forbids the sim airframe's halved gains). The AirStack simulator's tumbling with lag on is a known risk. Open question 3. |
| D6 | Physics at 200 Hz (dt 0.005 s), 10 steps per game tick. The whole cascade runs once per physics step; the gyro low-pass (80 Hz, near the 100 Hz Nyquist limit) is left out; the D-term low-pass (40 Hz, second order) is kept. Fallback fixed now: if the Task 3 convergence test fails at 200 Hz, use 400 Hz (dt 0.0025). | The drone's rate loop runs at up to 800 Hz; 200 Hz keeps Isaac Lab cheap (S0's best point ran at 100 Hz). The convergence test checks that the coarser loop changes no result. |
| D7 | No transport delay and no estimator: the cascade reads the true state; `setpoint_delay_s = 0.0`. Task 7 reports, as information, the extra delay that would best match the real log, and applies none. | The fitted 0.148 s delay was measured on PX4's own logged setpoint, so it lies inside the drone (attitude response, estimator), and the physics drone should produce its own share. Fitting a delay here would be stage 1 work on one log. |
| D8 | Yaw: the cascade's yaw setpoint is the game's own integrated yaw, plus the commanded yaw rate as feed-forward. The game's observation keeps the game's yaw. | The commander copy leaves yaw out (`commander.py` docstring); this keeps one yaw source for every backend. |
| D9 | The game's wall and height-band clamp (`keep_in`), the parking of drones that are out, and resets are done in the physics backend by **at most two batched state writes per tick** (all drones, `torch.where`), never by gathering indices. Isaac sees a small teleport at a wall. | The same contract as the Starling layer; no host sync (S0 wrote the full state every policy step at 455,300 drone-steps/s). |
| D10 | A drone that tips past 60° or turns non-finite is an **upset**. It is reported per game in `info["upset"]`; the game rules do not change. Wrenches pass through `torch.nan_to_num` before PhysX, and the count is kept. Gates require 0. | One NaN body can break a whole PhysX scene. |
| D11 | Tilt limit 45° (`MPC_TILTMAX_AIR` in the drone's file and on drone_2, the airframe the tier 1 model was fitted on). drone_1's 30° is an INFO variant in Task 7's step tests. | One value per run; the other is shown. |
| D12 | Isaac tests run a script in a subprocess with `--headless`, are marked `isaac`, and are **skipped unless `SVG_ISAAC_TESTS=1`**. The default suite never starts Isaac Sim. | Avoids an Isaac launch by accident over WiFi (the firmware crash); keeps `pytest -q` CPU-only. |
| D13 | Every Isaac launch is preceded by `scripts/isaac_preflight.sh`: exit 10 = BLOCKED (WiFi-only with a remote-desktop session), exit 11 = the GPU is in use (the lead checks that it is not the AirStack simulator). Isaac runs go in the container; the video and the log-window extraction run on the host, because they read files outside `svg_training/`. | CLAUDE.md environment trap; the container mounts only this folder. |
| D14 | Stand-in (lead's ruling, 16 November): S2 Task 10 is built here and run twice with **`configs/s2.toml [standin]` and `[standin_gates]` unchanged**. First the control run: exactly `[standin]` (preset `pure`, PyTorch). Then the Isaac run: the same settings with the motion backend switched to `physics` (commander, filter on every pair, physics drone), `--no-local`. One ledger row each. If the Isaac run fails and the control passes, the record says the fault is in the Isaac Lab path. It also cites Task 5's agreement result and Task 7's step tests, which separate "the wrapping" from "the drone model". | Owner via lead. Open questions 5 and 6. |
| D15 | Scripted games are compared **paired**: one batch per Guard × Strike pair (`score.py --batch-per-pair`, new, default off), with the same seed on both backends. Each slot then plays the same arena, zone and starts on each backend, because no backend draws from the game's generator. | Differences then come from the drone, not from chance. |
| D16 | Video: a fixed oblique camera over one game, one frame per game tick (20 fps, real time), 1280 × 720, H.264, at most 10 MB, with the caption burnt in. The clip rule is fixed now (Task 6). The Starling USD is referenced read-only as a visual-only child; if that cannot be made to work, a primitive drone is used and the caption says "simplified drone shape". | Owner via lead. Showable and honest; not cherry-picked by eye. |

### Open questions for the owner

1. D1: is the S2 game on Isaac Lab physics behind the existing adapters what you meant by "Isaac Lab environment", or do you also want a registered Isaac Lab task (a thin `DirectMARLEnv` shell, about one more task)?
2. D4: which rotor layout is the real Starling 2 Max: CAD ±0.095 / ±0.13 m (CMU) or ±0.085 / ±0.0625 m (the drone's parameters)? The plan flies CAD for the body and the parameters for PX4's allocation.
3. D5: if the real gains with the measured 55 / 85 ms motor lag are unstable on the physics drone, what do you want: motor lag off (as the AirStack simulator does), the other rotor layout, or stop?
4. Approve `configs/s2b.toml` (Task 1) before any run.
5. D14: the Isaac stand-in run keeps `wall_clock_cap_min = 45`. At under about 18,500 game-steps/s it stops before 50 M game-steps (the record then states how many it reached). Keep the cap, or allow a longer cap for the Isaac run as a new, separately approved value?
6. D14: the PyTorch control run is the pure partner rules, as committed. Should a third run on the tier 1 Starling layer (the closest PyTorch twin of the physics drone) be added?
7. D16: may the MP4 files (each under 10 MB) be committed under `docs/media/`? They are not for the website or partner material without your say-so.

## Global Constraints

- **Write only inside `svg_training/`.** Nothing changes AirStack, `tools/`, `~/IsaacLab`, `~/PX4-Autopilot`, the drone parameters, the sim airframe or the website. `../starling_1_indoor_params.params`, `../docs/CONFIG.md`, the Starling USD and `~/flight_logs` are read, never written. Never push. Builder agents make no git writes; **the lead commits** with explicit paths (`git add <path> …`; never `-A`, `-a` or `--no-verify`). A change under `docker/` needs a `docs/record/CHANGES.md` line; this plan needs none.
- **Confidentiality.** The partner's numbers never appear in a committed file (code, tests, configs, records, figures, videos, video sidecars, commit messages). Every S2b run and every video uses the committed neutral values (`--no-local`). `test_local_values_not_in_tracked_files` must stay green with the local file present.
- **Numbers flow from the drone, never back.** Gains are copied from the drone's file by a script that records the source path, its sha256 and commit. They are never tuned. No sim-only airframe value (halved rate gains, yaw-rate 0.25 / 0.2, 20 m/s limits, `LNDMC_ROT_MAX` 300) appears in any S2b file (iron rule 9).
- **Isaac Sim safety.** Every Isaac run is **headless**, in the container (`docker/run.sh`) except where D13 says host. Before any launch, the builder runs `scripts/isaac_preflight.sh`. On exit 10 it stops and reports **BLOCKED (WiFi-only with remote desktop)**, and the lead asks the owner. On exit 11 it stops and reports the process list. `nvidia-smi` comes first, always. No run while the AirStack simulator or a flight session holds the GPU.
- **Isaac code lives in one adapter.** Every `isaaclab` / `isaacsim` / `omni` / `pxr` import is in `source/svg_training/compat/isaaclab_232.py`. The one exception is `scripts/_isaac_app.py`, which starts `AppLauncher`, as `benchmark_tier2.py` did in S0. `core/`, `models/`, `opponents/` and `envs/` import nothing from Isaac. CPU tests never need Isaac Sim; Isaac tests are marked `isaac` and skipped unless `SVG_ISAAC_TESTS=1` (D12).
- **Batched only.** No per-game Python loop, and no `.item()`, `.cpu()`, `.numpy()`, `.tolist()`, `nonzero(` or NumPy in any step path (the game, the layers, the cascade, the rotor model, the worlds). Fixed loops over physics sub-steps, the filter's sweeps, rotors (4) and drone slots (in the adapter only) are allowed. The host syncs allowed in S2 stay as they are (the filter's `check_every`, one host check per 100 steps in `play_match`).
- **Runs.** Gates in `configs/s2b.toml` (owner-approved before the first run, never edited afterwards) are copied to `runs/<name>/gates.toml` before each run. Each run gets a record from `records/_template_record.md` whose first line names the simulator ("observed in the training simulator (tier 2, Isaac Lab)" for Isaac runs). Each run gets a ledger row with the **next free T number at run time**. Never "validated". A FAIL is recorded as a FAIL; an interrupted run writes an ABORTED record.
- **Writing.** Plain words for a newcomer, the term second. Every results page shows a figure made by a committed script from the run's own data. Captions are 2–4 sentences and at most 400 characters. Use Strike team / Guard team / reach the zone / drone team (STANDARDS §2). Name the simulator every time.
- **After every task** the lead updates the S2b progress table in `docs/claude/HANDOFF.md` §0 and refreshes `~/Downloads/claude-handoff-svg-training.md`.
- Python: type hints on public functions, shapes in docstrings, SI units in names (`_m`, `_mps`, `_rad_s`, `_n`). Tests: `cd svg_training && PYTHONPATH=source ~/miniconda3/envs/env_isaaclab/bin/python -m pytest -q`. Isaac tests: `docker/run.sh 'SVG_ISAAC_TESTS=1 $SVG_PY -m pytest -q -m isaac'`, after the preflight.

## Review Focus

1. **A frame or quaternion error** (ENU/FLU against NED/FRD, WXYZ against XYZW): the drone flies the wrong way or flips. Tests `test_frames_known_rotations`, `test_rotor_torque_signs` (Task 2), `test_x_command_moves_east_nose_down` (Task 3, closed loop on the torch world).
2. **Isaac's body differs from the one we specified**: PhysX defaults (angular damping 0.05, sleeping, mass from a collider, inertia not applied, wrench in the world frame). Tests `test_isaac_world_mass_inertia_readback` and the agreement gates of Task 5 (Isaac world against the torch oracle under the same forces and the same cascade).
3. **The backends drift apart**: the physics path gets its own commander or filter call, or draws from the game's generator so starts differ. Tests `test_command_chain_bit_identical` (S1/S2 suites green after the extraction), `test_physics_and_starling_same_first_setpoint`, `test_backends_draw_identical_starts` (Task 4).
4. **A host sync, a per-game loop or a stray Isaac import** in the step, or the default suite launching Isaac. Tests `test_game_modules_have_no_host_calls` (scan extended), `test_step_runs_under_sync_debug_error[physics-torch]` (CUDA), `test_core_imports_no_isaac` (Task 4).
5. **Real gains changed, or sim-only values leaking in** (iron rule 9). Tests `test_physics_params_match_drone_file` and `test_no_sim_only_values` (Task 1); the BLOCKED rule of D5.

## Task overview and order

| Task | What | Needs | Isaac? |
|---|---|---|---|
| 1 | Config, gates, physics parameter file (owner approval) | S2 done | no |
| 2 | Frames, airframe and rotor model, torch reference world | 1 | no |
| 3 | PX4 1.14 cascade + design check (stability, convergence) | 2 | no |
| 4 | Shared command chain, physics backend in the game | 3 | no |
| 5 | Isaac Lab world adapter + agreement run | 4 | yes |
| 6 | Video of scripted games (MP4) | 5 | yes (host) |
| 7 | Step tests (physics vs tier 1 vs the real log) + throughput runs | 5 | yes |
| 8 | Scripted reference games, paired, physics vs Starling layer | 5, 7 | yes |
| 9 | Stand-in trainer (S2 Task 10) on both backends | 4 (torch run), 8 (Isaac run) | yes |
| 10 | Documents and final review | all | no |

Tasks 6 and 7 may run in parallel after Task 5 (disjoint files, but one GPU: never two Isaac runs at once). The torch control run of Task 9 may run after Task 4.

---

### Task 1: S2b config, gates and the physics parameter file (owner approval)

**Files:** Create `configs/s2b.toml`, `scripts/make_physics_params.py`, `params/starling_physics_v0.toml` (generated, committed), `source/svg_training/models/physics_params.py`; Modify `source/svg_training/core/game_config.py` (two fields, one loader), `configs/s2_game.toml` (two keys, defaults leave S2 unchanged); Test `tests/test_s2b_config.py`, `tests/test_physics_params.py`.

**Interfaces — Consumes:** `StarlingLayerCfg`, `load_game_cfg`, `CONFIGS` (S2). **Produces:**
```python
# core/game_config.py
@dataclass(frozen=True) class StarlingLayerCfg:          # S2 fields unchanged, plus:
    backend: str = "fitted"                               # "fitted" (S2 Starling layer) | "physics"
    physics_params: str = "params/starling_physics_v0.toml"
def load_s2b_gates(path: str | Path = CONFIGS / "s2b.toml") -> dict
# models/physics_params.py   (PyTorch-free dataclasses; SI units)
@dataclass(frozen=True) class AirframeParams:
    mass_kg: float; inertia_kgm2: tuple[float, float, float]           # roll, pitch, yaw (FRD axes)
    k_f: float; k_m: float; omega_max_rad_s: float; tau_up_s: float; tau_down_s: float
    rotor_xy_cad_m: tuple[tuple[float, float], ...]                    # 4 × (x, y) FRD, PX4 rotor order 0..3
    rotor_xy_params_m: tuple[tuple[float, float], ...]
    rotor_km: tuple[float, float, float, float]                        # the drone's CA_ROTOR*_KM (sign = spin)
    def f_max_n(self) -> float                                          # k_f · ω_max²
    def hover_u(self) -> float                                          # m·9.81 / 4 / f_max
@dataclass(frozen=True) class Px4Gains:      # field = PX4 parameter name in lower case, value as in the drone's file
    mpc_xy_p: float; mpc_z_p: float; mpc_xy_vel_p_acc: float; ...       # every name in the first Facts row
@dataclass(frozen=True) class PhysicsParams:
    airframe: AirframeParams; gains: Px4Gains
    physics_dt_s: float; rotor_geometry: str; motor_lag: bool; setpoint_delay_s: float
    upset_tilt_deg: float = 60.0; source: dict = field(default_factory=dict)
def load_physics_params(path: str | Path, overrides: dict | None = None) -> PhysicsParams
    # [physics] of configs/s2b.toml overrides physics_dt_s / rotor_geometry / motor_lag / setpoint_delay_s
```

`scripts/make_physics_params.py --params-file ../starling_1_indoor_params.params --out params/starling_physics_v0.toml` writes `[source]` (path, sha256, `git log -1 --format=%h` of that file, date), `[gains]` (every name in the first Facts row, copied, each line commented `MEASURED <file>`), `[airframe]` (typed in the script, each commented `MEASURED ../docs/CONFIG.md "Inertials" / CMU sys-ID PDF`), and the header `# Tier 2 rigid-body Starling, version 0. Gains copied from the drone, never tuned.` It refuses (exit 2) if any listed name is missing from the file.

`configs/s2b.toml`, PROPOSED values for the owner to approve before any run:

```toml
# S2b settings and gates. PROPOSED 16 Nov 2026 (S2b plan). Never edited after a result exists; a new gate = a new run.
[physics]                                  # backend settings (not gates)
params = "params/starling_physics_v0.toml"
physics_dt_s = 0.005                       # D6: 200 Hz, 10 physics steps per game tick
fallback_physics_dt_s = 0.0025             # D6: used only if Task 3's convergence test fails at 0.005
rotor_geometry = "cad"                     # D4
motor_lag = true                           # D5
setpoint_delay_s = 0.0                     # D7

[agreement]                                # Task 5
games = 64
drones_per_game = 3
seed = 20261116

[agreement_gates]                          # Isaac Lab world vs the torch reference world
open_loop_pos_max_m = 1.0e-3               # 1 s, the same constant wrench: only integrator rounding should differ
open_loop_angle_max_deg = 0.1              # same, attitude
closed_loop_vel_rms_max_mps = 0.01         # step set under the cascade: a tenth of the S1 model allowance (0.10)
closed_loop_pos_max_m = 0.02               # end of each step: a tenth of the commander's 0.2 m hold leash
mass_inertia_rel_err_max = 1.0e-4          # read back from PhysX: the body is the one specified
nan_max = 0

[step_tests]                               # Task 7
steps = [
  { name = "x_strike",  cmd_mps = [0.5, 0.0, 0.0],      push_s = 4.0, release_s = 4.0 },
  { name = "y_guard",   cmd_mps = [0.0, -0.3333, 0.0],  push_s = 4.0, release_s = 4.0 },
  { name = "diagonal",  cmd_mps = [0.3536, 0.3536, 0.0], push_s = 4.0, release_s = 4.0 },
  { name = "reverse",   cmd_mps = [0.5, 0.0, 0.0],      push_s = 3.0, release_s = 3.0, then_mps = [-0.5, 0.0, 0.0] },
  { name = "z_up_info", cmd_mps = [0.0, 0.0, 0.3],      push_s = 2.0, release_s = 3.0 },   # INFO: tier 1 z not fitted
]
hover_s = 10.0
real_log = "~/flight_logs/2026-11-13/ulog_drone_2/log103.ulg"
real_log_sha256_prefix = "4db5b1fcf33e69c6"
tilt_info_deg = 30.0                       # D11: drone_1's limit, INFO variant

[step_gates]
hover_drift_max_m = 0.05                   # 10 s from rest: a tenth of the 0.5 m stick leash
hover_tilt_std_max_deg = 1.0               # last 5 s of hover; a limit cycle like the AirStack sim's 9 Hz one is far larger
peak_tilt_max_deg = 45.5                   # MPC_TILTMAX_AIR 45: the tilt limiter works
upsets_max = 0                             # D10
real_min_windows = 6                       # log103's six held-out legs (S1 split); fewer found = INFO
real_vel_rms_max_mps = 0.10                # physics drone fed the logged setpoints: S1 [fit_gates] value
real_t63_err_max_s = 0.10                  # S1 [fit_gates] value
tier1_vel_rms_max_mps = 0.10               # physics vs tier 1 Starling layer, same commands, gated steps only
tier1_t63_gap_max_s = 0.10

[throughput]                               # Task 7: INFO, no gate
sizes = ["2v1", "5v3"]
num_games = [1024, 2048, 4096]
actions = "random"
repeats = 2
trainable_drone_steps_per_s_min = 20000    # S0's decision rule for tier 2, read off, not a gate

[compare_games]                            # Task 8
guards = ["guard_mark_edge", "guard_mark_inside", "guard_field", "guard_mirror", "random"]
strikes = ["strike_straight", "strike_flank"]
sizes = ["2v1", "5v3"]
games_per_band = 1000
seed = 0
batch_per_pair = true                      # D15: paired games

[compare_games_gates]
max_cell_hold_gap = 0.10                   # per Guard × Strike × size × band, 1,000 paired games; ~2× the 0.044
                                           # 95 % spread of two unpaired rates at 0.5, so a larger gap is the drone
closest_cross_3d_gap_max_m = 0.10          # AMENDED by the owner 16 Nov (decision A): per matchup cell, games without a start miss, 3-D closest Guard–Strike approach: physics minimum and 5th percentile no more than 0.10 m below tier 1 Starling layer's (paired games). Replaces physics_closest_cross_min_m = 1.0, which failed by construction (T9: walled drones + teammate squeeze reach 0.75–0.80 m on tier 1)
upsets_max = 0
nan_max = 0

[video]                                    # Task 6
clips = [
  { name = "s2b_2v1_lab",    size = "2v1", band = "lab",    guard = "guard_mark_edge", strike = "strike_flank", seed = 1 },
  { name = "s2b_2v1_large",  size = "2v1", band = "large",  guard = "guard_field",     strike = "strike_straight", seed = 2 },
  { name = "s2b_5v3_lab",    size = "5v3", band = "lab",    guard = "guard_mark_edge", strike = "strike_flank", seed = 3 },
  { name = "s2b_5v3_middle", size = "5v3", band = "middle", guard = "guard_mirror",    strike = "strike_flank", seed = 4 },
]
candidate_games = 4                        # clip rule: first game slot (index order) whose first game lasts 20-40 s, else the longest
seconds_min = 20.0
seconds_max = 40.0
fps = 20
resolution = [1280, 720]
max_mb = 10.0
caption = "Training simulator (Isaac Lab), scripted strategies, not a real flight"
```

- [ ] **Failing tests** `tests/test_physics_params.py`:
```python
def test_airframe_derived_values():
    a = load_physics_params(ROOT / "params/starling_physics_v0.toml").airframe
    assert a.f_max_n() == pytest.approx(8.33586, abs=1e-4)
    assert a.hover_u() == pytest.approx(0.16388, abs=1e-4)
    assert a.k_m / a.k_f == pytest.approx(0.0135872, abs=1e-6)
def test_physics_params_match_drone_file():               # Review Focus 5
    src = ROOT.parent / "starling_1_indoor_params.params"
    if not src.exists(): pytest.skip("drone parameter file not on this machine (container)")
    drone = _read_params(src)                              # "1 1 NAME value type" lines -> {NAME: float}
    g = load_physics_params(ROOT / "params/starling_physics_v0.toml").gains
    for f in dataclasses.fields(g): assert getattr(g, f.name) == pytest.approx(drone[f.name.upper()], rel=1e-9), f.name
def test_no_sim_only_values():                             # iron rule 9
    text = (ROOT / "params/starling_physics_v0.toml").read_text()
    for bad in ("0.032", "0.00065", "0.00055", "= 0.25", "= 20.0", "= 300"): assert bad not in text
def test_generator_refuses_missing_name(tmp_path): ...     # a file without MPC_XY_P -> exit 2
```
`tests/test_s2b_config.py`: `load_s2b_gates()` has every table listed above; `StarlingLayerCfg().backend == "fitted"`; `load_game_cfg(...)` with `starling_layer.backend = "physics"` loads; an unknown backend raises in `SvgGame` (Task 4); `"starling_layer.backend"` is NOT in `LOCAL_ALLOWED` (a local file cannot switch backend); `[standin]` and `[standin_gates]` of `configs/s2.toml` are byte-identical to the S2 commit (sha256 of the two table texts pinned in the test).
- [ ] Run `pytest -q tests/test_physics_params.py tests/test_s2b_config.py` → fail. Implement; run the generator on the host; run → pass; full suite green.
- [ ] The lead takes `configs/s2b.toml` and the Design section to the owner. **No run in Tasks 5–9 starts before approval.**
- [ ] Lead commits the files under **Files**: `git commit -m "svg_training S2b: physics parameters from the drone file, S2b gates"`.

### Task 2: Frames, airframe and rotor model, torch reference world

**Files:** Create `source/svg_training/models/frames.py`, `source/svg_training/models/starling_airframe.py`, `source/svg_training/models/rigid_body.py`; Test `tests/test_frames.py`, `tests/test_starling_airframe.py`, `tests/test_rigid_body.py`.

**Interfaces — Consumes:** `AirframeParams`, `PhysicsParams` (Task 1). **Produces:**
```python
# models/frames.py: the one crossing between ENU/FLU (game, worlds, Isaac) and NED/FRD (cascade); quaternions WXYZ
P_ENU_NED: Tensor              # [[0,1,0],[1,0,0],[0,0,-1]]  (v_ned = P @ v_enu, its own inverse)
B_FLU_FRD: Tensor              # diag(1, -1, -1)
def quat_wxyz_to_rotmat(q: Tensor) -> Tensor                    # [..., 4] -> [..., 3, 3], body -> world
def rotmat_to_quat_wxyz(r: Tensor) -> Tensor                    # w >= 0
def rot_enu_flu_to_ned_frd(r_enu_flu: Tensor) -> Tensor         # P @ R @ B
def vec_enu_to_ned(v: Tensor) -> Tensor; def vec_ned_to_enu(v: Tensor) -> Tensor
def yaw_enu_to_ned(yaw_enu: Tensor) -> Tensor                   # pi/2 - yaw, wrapped to (-pi, pi]
def quat_from_yaw_enu(yaw: Tensor) -> Tensor                    # level attitude, WXYZ
def tilt_rad(q_wxyz: Tensor) -> Tensor                          # angle between body z and world z
# models/starling_airframe.py
class RotorModel:
    def __init__(self, n: int, m: int, a: AirframeParams, motor_lag: bool, dt_s: float, device)
    omega_rad_s: Tensor                                          # [N, M, 4]
    def reset(self, mask: Tensor) -> None                        # [N, M] bool: rotors at hover speed
    def step(self, u: Tensor) -> Tensor                          # u [N, M, 4] in [0, 1] -> thrust [N, M, 4] N
def body_wrench_flu(thrust_n: Tensor, a: AirframeParams, geometry: str) -> tuple[Tensor, Tensor]
    # -> force_b [N, M, 3], torque_b [N, M, 3] in FLU (computed in FRD, converted with B_FLU_FRD)
# models/rigid_body.py
class RigidBodyWorld(Protocol):
    num_games: int; drones: int; dt_s: float; label: str; device
    def reset(self, mask: Tensor, pos_m: Tensor, quat_wxyz: Tensor) -> None    # [N,M], [N,M,3], [N,M,4]; at rest
    def write_state(self, mask: Tensor, pos_m: Tensor, quat_wxyz: Tensor, lin_vel_mps: Tensor,
                    ang_vel_b_rad_s: Tensor) -> None             # where mask, else unchanged; one batched write
    def apply_wrench_b(self, force_b: Tensor, torque_b: Tensor) -> None          # FLU body frame, held until next call
    def step(self) -> None                                       # one physics step of dt_s
    def state(self) -> tuple[Tensor, Tensor, Tensor, Tensor]     # pos_m, quat_wxyz, lin_vel_w (ENU), ang_vel_b (FLU)
class TorchRigidBodyWorld:                                       # label = "torch-reference (test oracle)"
    def __init__(self, num_games: int, drones: int, a: AirframeParams, dt_s: float, device)
```
Rotor model per physics step: `ω_cmd = sqrt(u · f_max / k_f)`; `τ = tau_up_s if ω_cmd > ω else tau_down_s`; `ω += (ω_cmd − ω)(1 − exp(−dt/τ))` (lag on), `ω = ω_cmd` (lag off); thrust `F_i = k_f ω_i²`. Wrench in FRD: force `(0, 0, −ΣF_i)`; torque `Σ r_i × (0, 0, −F_i) + (0, 0, sign(KM_i) · (k_m/k_f) · F_i)`, `r_i = (x_i, y_i, 0)` from the chosen geometry. Torch world, semi-implicit Euler (PhysX's order): `v += (R f_b / m + (0, 0, −9.81)) dt`; `ω_b += I⁻¹(τ_b − ω_b × I ω_b) dt`; `p += v dt`; `q ← normalise(q ⊗ [cos(|ω|dt/2), sin(|ω|dt/2) ω/|ω|])`.

- [ ] **Failing tests:**
```python
def test_frames_known_rotations():                        # Review Focus 1
    assert yaw_enu_to_ned(torch.tensor(0.0)) == pytest.approx(math.pi / 2)        # nose east
    r = rot_enu_flu_to_ned_frd(quat_wxyz_to_rotmat(quat_from_yaw_enu(torch.tensor(0.0))))
    assert torch.allclose(r @ torch.tensor([1.0, 0, 0]), torch.tensor([0.0, 1, 0]), atol=1e-6)   # body x -> NED east
    assert torch.allclose(r @ torch.tensor([0.0, 0, 1]), torch.tensor([0.0, 0, 1]), atol=1e-6)   # body down -> NED down
    q = torch.randn(100, 4); q = q / q.norm(dim=-1, keepdim=True)
    assert torch.allclose(rotmat_to_quat_wxyz(quat_wxyz_to_rotmat(q)).abs(), q.abs(), atol=1e-5)
def test_hover_wrench():
    t = torch.full((1, 1, 4), 1.3660425)
    f, tau = body_wrench_flu(t, A, "cad")
    assert f[0, 0, 2] == pytest.approx(5.46417, abs=1e-4) and tau.abs().max() < 1e-7
def test_rotor_torque_signs():                            # Review Focus 1
    # rotors 0 and 3 (right side, y_FRD > 0) +0.1 N: roll left -> torque x < 0 (same sign in FRD and FLU)
    # rotors 0 and 1 (KM > 0) +0.1 N: yaw right seen from above -> torque_FLU z < 0
    # rotors 0 and 2 (front) +0.1 N: nose up -> torque_FLU y < 0 (FRD y > 0)
def test_rotor_lag_63pct():                               # from hover speed, u stepped to 1: 63.2 % of the gap after 55 ms (±1 dt)
def test_rotor_lag_off_is_instant(): ...
def test_torch_world_free_fall():                         # no wrench, 1 s at 0.005: z drop = 9.81·(1·1.005)/2 within 1e-4 (semi-implicit Euler)
def test_torch_world_hover_holds(): ...                   # hover wrench 2 s: |Δp| < 1e-6, |ω| < 1e-9
def test_torch_world_spin_conserves_energy(): ...         # free tumbling 2 s at dt 1e-4: rotational energy within 1e-3 relative
```
- [ ] Run → fail; implement; run → pass. Static scan list of `test_game_modules_have_no_host_calls` gains `models/frames.py`, `models/starling_airframe.py`, `models/rigid_body.py`.
- [ ] Lead commits the six files.

### Task 3: PX4 1.14 cascade and the design check

**Files:** Create `source/svg_training/models/px4_cascade.py`, `scripts/physics_design_check.py`; Test `tests/test_px4_cascade.py`.

**Interfaces — Consumes:** Tasks 1–2. **Produces:**
```python
def constrain_xy(v0: Tensor, v1: Tensor, max_mps: float) -> Tensor        # ControlMath.cpp:122-184, batched
def limit_tilt(body_z: Tensor, max_rad: float) -> Tensor                  # ControlMath.cpp:53-68, world unit (0, 0, 1) as PX4 passes it
def bodyz_to_rotmat(body_z: Tensor, yaw_ned: Tensor) -> Tensor            # ControlMath.cpp:70-120 -> R_sp [..., 3, 3]
def allocation_matrix(g: Px4Gains) -> Tensor                              # [4, 6] normalised pseudo-inverse mix of v1.14
def allocate(torque_n: Tensor, thrust_n: Tensor, mix: Tensor) -> Tensor   # mixAirmodeDisabled + mixYaw -> u [N, M, 4] in [0, 1]
class Px4Cascade:
    def __init__(self, n: int, m: int, g: Px4Gains, dt_s: float, device, tilt_max_deg: float | None = None)
    def reset(self, mask: Tensor) -> None                 # integrators 0; derivative filters at rest
    def step(self, p_sp: Tensor, v_ff: Tensor, a_ff: Tensor, yaw_sp: Tensor, yawspeed_ff: Tensor,
             pos: Tensor, vel: Tensor, r_ned_frd: Tensor, omega_frd: Tensor) -> Tensor   # all NED/FRD; -> u [N, M, 4]
    # after a step, for logging and tests: acc_sp, thr_sp, r_sp, rates_sp, torque_n, collective [N, M]
```
The cascade, one physics step, NED / FRD, every vector [N, M, 3] (port each line from v1.14.0; equations here so the reviewer can check):
1. **Position** (`_positionControl`): `v_pos = K_p ⊙ (p_sp − p)`, `K_p = (mpc_xy_p, mpc_xy_p, mpc_z_p)`; `v_sp.xy = constrain_xy(v_pos.xy, v_ff.xy, mpc_xy_vel_max)`; `v_sp.z = clamp(v_ff.z + v_pos.z, −mpc_z_vel_max_up, mpc_z_vel_max_dn)`.
2. **Velocity** (`_velocityControl`): `v̇` = derivative of `vel` through a first-order low-pass at `mpc_veld_lp` Hz (`_vel_*_deriv`); `i.z = clamp(i.z, −g, g)`; `e = v_sp − v`; `a_sp = a_ff + K_vp ⊙ e + i − K_vd ⊙ v̇`.
3. **Acceleration → thrust** (`_accelerationControl`): `body_z = normalise(−a_sp.x, −a_sp.y, g)`; `body_z = limit_tilt(body_z, tilt_max)`; `T = (a_sp.z · h / g − h) / body_z.z`, `h = mpc_thr_hover`; `T = min(T, −mpc_thr_min)`; `thr_sp = body_z · T`.
4. **Saturation and anti-windup** (rest of `_velocityControl`): zero `e.z` if (`thr_sp.z ≥ −thr_min` and `e.z ≥ 0`) or (`thr_sp.z ≤ −thr_max` and `e.z ≤ 0`); vertical priority with the horizontal margin `mpc_thr_xy_marg` and the cap `mpc_thr_max`; `a_prod = thr_sp.xy · g / h`; `e.xy −= (2 / K_vp.x) · (a_sp.xy − (a_prod if |a_sp.xy|² > |a_prod|² else a_sp.xy))`; `i += e ⊙ K_vi · dt`.
5. **Attitude setpoint** (`thrustToAttitude`): `R_sp = bodyz_to_rotmat(−thr_sp, yaw_sp)`, collective `c = |thr_sp|`.
6. **Attitude** (`AttitudeControl::update`): the reduced-attitude quaternion law with `yaw_weight = mc_yaw_weight`; `ω_sp = 2 · sign(q_e.w) · q_e.xyz ⊙ (mc_roll_p, mc_pitch_p, mc_yaw_p)`; `+ R^T (0,0,1) · yawspeed_ff`; clamp to the rate limits (deg → rad).
7. **Rates** (`RateControl::update`): `e_ω = ω_sp − ω`; `τ_n = K ⊙ (P ⊙ e_ω + I_int − D ⊙ ω̇_f) + FF ⊙ ω_sp`, `ω̇_f` = derivative of `ω` through a second-order Butterworth low-pass at `imu_dgyro_cutoff` Hz; `I_int += max(0, 1 − (e_ω/400°/s)²) · I ⊙ e_ω · dt`, clamped to ±(`mc_rr_int_lim`, `mc_pr_int_lim`, `mc_yr_int_lim`). The allocator's saturation flags are taken as never set (noted in the docstring).
8. **Allocation:** `u = allocate(τ_n, c, mix)` from the drone's `CA_ROTOR*` (`PX`, `PY`, `CT` 6.5, `KM`), normalised as in `updateControlAllocationMatrixScale` / `normalizeControlAllocationMatrix`, desaturated as `mixAirmodeDisabled` (`MC_AIRMODE` 0); u clipped to [0, 1]. `THR_MDL_FAC` linearises the motor exactly, so `u` is a share of full thrust (stated).

`scripts/physics_design_check.py --out runs/<date>_s2b_design_check/` (CPU, torch world, one drone; development check, no ledger row, results in the task report). Table for plant geometry {cad, params} × motor lag {on, off} at dt {0.005, 0.001}: hover tilt spread (last 5 s of 10 s), hover drift, setpoint-level +x 0.5 m/s step (t63, overshoot, peak tilt). Plus the `ω_sp` → `ω` closed-loop check at 1 rad/s roll-rate steps. **Decision rules (fixed now):** (a) default (cad, lag on, 0.005) hover tilt spread > 1.0° → BLOCKED (D5); (b) default at 0.005 against default at 0.001, +x step speed RMS difference > 0.02 m/s → use `fallback_physics_dt_s` and record it.

- [ ] **Failing tests:**
```python
def test_constrain_xy_cases():
    assert torch.allclose(constrain_xy(t(1, 0), t(0, 1), math.sqrt(2)), t(1, 1), atol=1e-6)    # fits: sum
    assert torch.allclose(constrain_xy(t(1, 0), t(0, 1), 0.5), t(0.5, 0), atol=1e-6)          # v0 alone too big
    v = constrain_xy(t(0.6, 0), t(0, 3), 1.0); assert v.norm() == pytest.approx(1.0) and v[0] == pytest.approx(0.6)
def test_limit_tilt_45(): ...                              # body_z 60° off vertical -> exactly 45°, same azimuth
def test_hover_allocation():
    u = allocate(torch.zeros(1, 1, 3), torch.full((1, 1), 0.165), allocation_matrix(G))
    assert torch.allclose(u, torch.full((1, 1, 4), 0.165), atol=1e-6)
def test_hover_at_rest_outputs_hover_thrust(): ...        # setpoint = state, level: u = 0.165 ± 1e-6, τ_n = 0
def test_x_command_moves_east_nose_down():                # Review Focus 1; torch world, 1 drone, default plant
    # setpoint p_sp moving +x ENU at 0.5 m/s with v_ff (+0.5, 0, 0) for 3 s: x > 1.0 m, |y| < 0.02 m,
    # z within 0.05 m of start, pitch (FRD) negative while accelerating, final yaw within 1° of start
def test_hover_stable_default_plant(): ...                # 10 s: tilt spread <= 1.0°, drift <= 0.05 m (the D5 check as a test)
def test_tilt_limited_45(): ...                           # a_ff = (20, 0, 0) m/s²: peak tilt <= 45.5°
def test_vertical_step_and_thrust_cap(): ...              # v_ff z = -2 m/s (up): u <= 0.6 + 1e-6 throughout (MPC_THR_MAX)
def test_cascade_dt_convergence(): ...                    # +x step at 0.005 vs 0.001 s: speed RMS diff <= 0.02 m/s (rule b)
def test_cascade_reset_clears_integrators(): ...
```
- [ ] Run → fail; implement; run → pass. Run the design check; put its table in the task report. If rule (a) fires: **stop, BLOCKED**, the lead takes the table to the owner (open question 3). If rule (b) fires: the lead notes the fallback in HANDOFF (the value is already approved in `[physics]`).
- [ ] Lead commits `models/px4_cascade.py`, `scripts/physics_design_check.py`, `tests/test_px4_cascade.py`.

### Task 4: Shared command chain and the physics backend in the game (CPU)

**Files:** Create `source/svg_training/models/command_chain.py`, `source/svg_training/models/physics_drone.py`, `source/svg_training/core/physics_layer.py`; Modify `source/svg_training/models/fitted.py` (delegate to `CommandChain`, behaviour bit-identical), `source/svg_training/core/starling_layer.py` (accept and ignore `yaw` / `yaw_rate_rad_s`), `source/svg_training/core/game.py` (backend switch, `world=`, `info["upset"]`, `motion` label); Test `tests/test_physics_layer.py`, `tests/test_command_chain.py`, `tests/test_game_core.py` (scan list, sync test).

**Interfaces — Consumes:** `TeleopCommander`, `filter_velocities`, `load_params` (S1/S2), Tasks 1–3. **Produces:**
```python
# models/command_chain.py: the commander copy + the safety filter, moved out of FittedResponse unchanged
class CommandChain:
    def __init__(self, n: int, m: int, params: dict, device, dtype=torch.float32, safety_filter: bool = False,
                 pair_mask: Tensor | None = None, filter_iterations: int = 1000, filter_kwargs: dict | None = None)
    commander: TeleopCommander; corrected: Tensor                 # [N, M] bool
    def set_pair_mask(self, mask: Tensor) -> None
    def reset(self, mask: Tensor) -> None
    def step(self, cmd_mps: Tensor, pos_m: Tensor) -> tuple[Tensor, Tensor, Tensor]   # ENU (p_sp, v_ff, a_ff)
# models/physics_drone.py
class PhysicsDrone:
    def __init__(self, world: RigidBodyWorld, p: PhysicsParams, device)
    pos_m, vel_mps, quat_wxyz: Tensor; tilt_rad, max_tilt_rad: Tensor   # [N, M]
    upset: Tensor; nonfinite_count: Tensor                               # [N, M] bool since reset; scalar long
    def reset(self, mask: Tensor, pos_m: Tensor, yaw_rad: Tensor) -> None    # level, at rest, rotors at hover, cascade fresh
    def step_setpoint(self, p_sp_m: Tensor, v_ff_mps: Tensor, a_ff_mps2: Tensor, yaw_sp_rad: Tensor,
                      yaw_rate_rad_s: Tensor) -> None                    # ENU in; round(0.05 / dt) physics steps
    def write_clamped(self, mask: Tensor, pos_m: Tensor, vel_mps: Tensor) -> None   # keep attitude and body rates
# core/physics_layer.py: the StarlingLayer contract (S2 Task 4) on the physics drone
class PhysicsLayer:
    status = "physics"
    def __init__(self, cfg: GameCfg, num_games: int, guards: int, strikes: int, device, world: RigidBodyWorld)
        # same stick-cap checks and pair masks as StarlingLayer; command chain from cfg.starling.params
        # ([commander], [filter] tables); physics from cfg.starling.physics_params + configs/s2b.toml [physics]
    def reset(self, mask: Tensor, pos_m: Tensor, yaw: Tensor | None = None) -> None
    def step(self, cmd_mps: Tensor, pos_m: Tensor, alive: Tensor, yaw: Tensor | None = None,
             yaw_rate_rad_s: Tensor | None = None) -> tuple[Tensor, Tensor, Tensor]   # (pos, vel, corrected)
    def keep_in(self, lo_m: Tensor, hi_m: Tensor) -> Tensor
# core/game.py
SvgGame(..., world: RigidBodyWorld | None = None)
    # backend "physics" without a world -> ValueError("the physics backend needs a world: IsaacWorld or
    # TorchRigidBodyWorld"); world sizes must equal (num_games, guards + strikes); unknown backend -> ValueError
    motion: str      # "pure" | "starling" | "physics/<world.label>"; written into every record and score file
    # info["upset"] [N] bool (any live drone upset this game; all False on the other backends)
```
`PhysicsLayer.step` order: pair mask = live pairs (as Starling layer); drones that are out are reset at their (parked) positions, commanded zero; `CommandChain.step(cmd · alive, pos)`; `PhysicsDrone.step_setpoint(p_sp, v_ff, a_ff, yaw, yaw_rate)`; return the drone's position and velocity and `corrected & alive`. `keep_in` clamps position, zeroes the clamped axes of velocity, clamps the commander's reference (as `StarlingLayer.keep_in`), and makes one `write_clamped` call. Nothing here draws from the game's generator.

- [ ] **Failing tests:**
```python
def test_command_chain_bit_identical():                   # Review Focus 3: S1/S2 unchanged
    # FittedResponse before/after the extraction on 200 random ticks, filter on, team and every-pair masks:
    # torch.equal on vel_mps, pos_m, setpoint, corrected (golden tensors saved from the pre-change commit in the test's fixture)
def test_physics_and_starling_same_first_setpoint(): ... # same cfg, same commands: CommandChain outputs equal on tick 1
def test_backends_draw_identical_starts():               # D15
    a = SvgGame(cfg_starling, 32, 2, 1, device="cpu", seed=5)
    b = SvgGame(cfg_physics, 32, 2, 1, device="cpu", seed=5, world=TorchRigidBodyWorld(32, 3, A, 0.005, "cpu"))
    for _ in range(3): (re-reset with the same seed) assert torch.equal(a.pos_m, b.pos_m) and arenas equal
def test_physics_keeps_opposite_teams_apart():           # 1v1 head-on from (-1, 0) and (1, 0), team caps, 10 s
    assert min_horizontal_distance(backend="physics", preset="partner") >= 1.0
def test_physics_speed_ratio(): ...                       # full stick +x 6 s, 16 m arena: last-second speeds 0.5 ± 0.03, 0.333 ± 0.03
def test_physics_walls_and_height_band(): ...             # driven into a wall and down: inside margin + 0.01, z >= 0.5 - 0.01
def test_physics_dropout_parked_and_excluded(): ...       # an out drone never sets another's corrected; it is parked, no NaN
def test_physics_needs_world(): ...                       # ValueError names both worlds
def test_physics_partner_speed_above_stick_cap_raises(tmp_path): ...   # made-up local value 0.7 m/s
def test_upset_flag(): ...                                # a forced 90° attitude write -> info["upset"] True for that game only
def test_core_imports_no_isaac():                         # Review Focus 4
    code = ("import svg_training.core.game, svg_training.core.physics_layer, svg_training.models.px4_cascade, sys; "
            "assert not {m for m in sys.modules if m.split('.')[0] in ('isaaclab', 'isaacsim', 'omni', 'pxr')}")
    assert subprocess.run([sys.executable, "-c", code], env=ENV).returncode == 0
```
`tests/test_game_core.py`: static scan adds `physics_layer`, `command_chain`, `physics_drone`, `px4_cascade`; `test_step_runs_under_sync_debug_error` gains the parameter `physics-torch` (CUDA, 64 games 2v1, torch world, 130 steps, every game auto-resets once).
- [ ] Run → fail; implement; run → pass. The full suite is green, including `tests/test_fitted.py`, `tests/test_starling_layer.py` and `tests/test_score.py`, all unedited.
- [ ] Lead commits the files under **Files**.

### Task 5: Isaac Lab world adapter and the agreement run

**Files:** Modify `source/svg_training/compat/isaaclab_232.py` (new section; S0 functions unchanged); Create `scripts/_isaac_app.py`, `scripts/isaac_preflight.sh`, `scripts/physics_agreement.py`; Modify `pyproject.toml` (register the `isaac` marker), `tests/conftest.py` (or create it: skip `isaac` unless `SVG_ISAAC_TESTS=1`); Test `tests/test_isaac_world.py` (marked `isaac`), `tests/test_isaac_preflight.py` (CPU, fake commands); run record `records/<date>_s2b_agreement_record.md`; Modify `records/LEDGER.md`.

**Interfaces — Consumes:** `RigidBodyWorld`, `TorchRigidBodyWorld`, `AirframeParams`, `PhysicsDrone` (Tasks 2–4). **Produces:**
```python
# compat/isaaclab_232.py, new section (import only after AppLauncher)
def make_physics_sim(physics_dt_s: float, device: str)          # SimulationContext; gravity (0, 0, -9.81); render_interval = substeps
class IsaacWorld:                                               # implements RigidBodyWorld; label = "isaaclab-2.3.2"
    def __init__(self, sim, num_games: int, drones: int, a: AirframeParams, physics_dt_s: float,
                 spacing_m: float = 40.0, visual: str | None = None)   # visual: None | "starling" | "primitive" (Task 6)
    # one RigidObject per drone slot, no collider; mass_props mass = a.mass_kg; inertia diag set with
    # root_physx_view.set_inertias after play(); rigid_props: linear/angular damping 0, sleeping off,
    # gyroscopic forces on, max angular velocity >= 1e4 deg/s; positions are game-relative (env origins added inside)
    def mass_inertia_readback(self) -> tuple[Tensor, Tensor]    # [N, M], [N, M, 3]: what PhysX holds
def physics_play(sim, world: IsaacWorld) -> None                # play(sim) + inertia write + read-back check
# scripts/_isaac_app.py
def start_headless(parser: argparse.ArgumentParser, cameras: bool = False) -> tuple[argparse.Namespace, object]
    # AppLauncher.add_app_launcher_args; refuses without --headless (exit 2); returns (args, simulation_app)
```
Wrench: `permanent_wrench_composer.set_forces_and_torques(forces=…, torques=…, body_ids=…)` in the body frame, once per physics step, after `torch.nan_to_num`. The step loop is `write_data_to_sim → sim.step(render=False) → update(dt)`, as S0's `step_scene`. All Isaac reads are `data.root_link_pose_w`, `root_com_lin_vel_w`, `root_ang_vel_b` (or the 2.3.2 names the builder finds), converted to WXYZ game-relative tensors.

`scripts/isaac_preflight.sh` prints `nvidia-smi` and the network state. It exits 10 when no Ethernet device is `connected` (`nmcli -t -f TYPE,STATE device`) **and** a remote-desktop process is running (`pgrep -a -f 'gnome-remote-desktop|xrdp|x11vnc|vino|rustdesk|anydesk|teamviewer'`). It exits 11 when any compute process other than this shell's holds more than 500 MiB, 0 otherwise.

`scripts/physics_agreement.py --headless --gates configs/s2b.toml --name <date>_s2b_agreement`: 64 games × 3 drones, Isaac world and torch world side by side in one process. (1) The mass / inertia read-back. (2) Open loop: 1 s of a constant wrench (thrust 1.1 × weight, torque (2e-4, −1e-4, 5e-5) N·m) from hover. (3) Closed loop: the `[step_tests]` steps through `PhysicsDrone` (CommandChain-free setpoints: p_sp ramps at the step speed with `v_ff`) on both worlds. Writes `results.json`, the figure `docs/figures/s2b_agreement.png` (per-step speed, Isaac against torch), the record (first line: "Observed in the training simulator (tier 2, Isaac Lab) against its PyTorch reference world; no real drone"), and a ledger row.

- [ ] **Failing tests** (`tests/test_isaac_world.py`, each runs `scripts/physics_agreement.py --headless --smoke` in a subprocess and reads its JSON):
```python
pytestmark = pytest.mark.isaac
def test_isaac_world_mass_inertia_readback(smoke):        # Review Focus 2
    assert smoke["mass_rel_err"] <= 1e-4 and smoke["inertia_rel_err"] <= 1e-4
def test_isaac_hover_holds(smoke): ...                    # hover wrench 2 s: |Δp| < 1e-3 m
def test_isaac_wrench_is_body_frame(smoke): ...           # body yawed 90°, +x body force -> +y world acceleration
def test_isaac_open_loop_matches_torch(smoke): ...        # smoke version of gate (2)
```
`tests/test_isaac_preflight.py` (CPU, `PATH` with fake `nmcli`, `pgrep` and `nvidia-smi` scripts): WiFi-only + xrdp → 10; Ethernet + xrdp → 0; WiFi-only, no remote desktop → 0; a 3,600 MiB foreign process → 11.
- [ ] Run → fail (CPU tests); implement. **Before the first Isaac launch:** `scripts/isaac_preflight.sh`; on 10 or 11 stop and report. Then `docker/run.sh 'SVG_ISAAC_TESTS=1 $SVG_PY -m pytest -q -m isaac'` → pass.
- [ ] **Run (gates `[agreement_gates]`):** preflight, then `docker/run.sh 'svg-isaaclab -p scripts/physics_agreement.py --headless --gates configs/s2b.toml --name <date>_s2b_agreement'`. PASS when every gate holds. Record, ledger row, figure. On a FAIL, Tasks 6–9 wait for the lead's ruling.
- [ ] Lead commits code, tests, scripts, record, figure, ledger, `pyproject.toml`.

### Task 6: Video of scripted games on Isaac Lab drones

**Files:** Create `scripts/make_s2b_video.py`, `source/svg_training/bench/overlay.py` (pure NumPy/OpenCV, called only by the video script, never in a step), `docs/media/<clip>.mp4` and `docs/media/<clip>.toml` (sidecar) for each `[video] clips` entry; Modify `compat/isaaclab_232.py` (two functions); Test `tests/test_video.py` (CPU).

**Interfaces — Produces:**
```python
# compat/isaaclab_232.py
def make_recorder(sim, eye_m: tuple, lookat_m: tuple, resolution: tuple[int, int]) -> Callable[[], "np.ndarray"]
    # sim.set_camera_view + replicator render_product + "rgb" annotator (as direct_marl_env.py:510-530);
    # returns frame() -> [H, W, 3] uint8 after sim.render(); empty frames during warm-up are retried, not written
def spawn_arena_visuals(env_index: int, half_m: float, zone_xy_m: tuple, zone_radius_m: float) -> None
    # visual-only prims (no physics): translucent zone disc 0.02 m thick, four low wall bars at ±(half - 0.25) m
# bench/overlay.py
def draw_overlay(frame: "np.ndarray", caption: str, legend: dict[str, tuple[int, int, int]], time_left_s: float,
                 outcome: str | None) -> "np.ndarray"
def pick_clip_slot(first_game_s: "np.ndarray", seconds_min: float, seconds_max: float) -> int
```
`scripts/make_s2b_video.py --headless --enable_cameras --clip <name> --config configs/s2b.toml` (host conda env, D13). Steps: the preflight; `--no-local` game config with `starling_layer.enabled = true, backend = "physics"`; `IsaacWorld(..., num_games = candidate_games, visual = "starling")` (team marker spheres above each drone: Guard blue, Strike orange); play the first games headless without recording to pick the slot (rule `pick_clip_slot`, fixed in `[video]`); reset with the same seed (the same starts, D15); place the arena visuals for that slot; record one frame per game tick until that game ends or `seconds_max`; overlay (caption, legend "Guard team" / "Strike team", time left, the outcome at the end); encode H.264 (`imageio` with `imageio-ffmpeg`, `crf` raised in steps of 4 until the file is ≤ `max_mb`). Sidecar: clip name, commit, game config sha256, `local_file = "none"`, size, band, strategies, seed, slot, game length, outcome, `motion`, the visual used ("starling" or "primitive").

Starling visual: the USD at `../AirStack/simulation/isaac-sim/assets/robots/starling2max.usd`, referenced read-only as a child of each drone body with rigid bodies and colliders disabled by the spawn config. If that fails after one hour of trying, use `visual="primitive"` (a 0.19 × 0.26 × 0.05 m body and four 0.1 m rotor discs, the CAD layout) with the caption suffix " (simplified drone shape)", and report which in the task report.

- [ ] **Failing tests** (`tests/test_video.py`, CPU):
```python
def test_overlay_draws_caption():
    f = draw_overlay(np.zeros((720, 1280, 3), np.uint8), CAPTION, LEGEND, 12.3, None)
    assert f[-60:, :, :].max() > 0 and f.shape == (720, 1280, 3)        # caption band is drawn
def test_pick_clip_slot_rule():
    assert pick_clip_slot(np.array([12.0, 25.0, 33.0, 50.0]), 20, 40) == 1
    assert pick_clip_slot(np.array([5.0, 8.0, 12.0, 15.0]), 20, 40) == 3   # none in range: the longest
def test_video_config_caption_and_no_local():
    v = load_s2b_gates()["video"]; assert "not a real flight" in v["caption"] and v["max_mb"] <= 10
    # make_s2b_video.py source passes use_local=False and has no --local-dir option
```
- [ ] Run → fail; implement; run → pass. Preflight (BLOCKED on exit 10). Make the four clips on the host: `~/IsaacLab/isaaclab.sh -p scripts/make_s2b_video.py --headless --enable_cameras --clip <name>`. Watch each file once (frames are not blank, the drones are visible, the caption is readable). Check every file is ≤ 10 MB (`ls -l`).
- [ ] No ledger row (a clip is not a measurement). The lead shows the clips to the owner before committing (open question 7). Lead commits the script, overlay, tests and, on the owner's yes, `docs/media/*.mp4` and `*.toml`.

### Task 7: Step tests (physics vs tier 1 vs the real log) and throughput

**Files:** Create `scripts/physics_step_tests.py`, `scripts/physics_throughput.py`, `scripts/make_s2b_figures.py` (one function per figure; extended by Tasks 8, 9); Test `tests/test_step_tests.py`; run records `records/<date>_s2b_step_tests_record.md`, `records/<date>_s2b_throughput_record.md`; Modify `records/LEDGER.md`.

**Interfaces — Consumes:** `PhysicsLayer`, `StarlingLayer`, `PhysicsDrone`, `fit_real_px4.load_flight` / `make_windows`, `px4_trajectory.time_to_63pct`, `bench/timing.measure`. **Produces:**
```python
def step_metrics(t_s: "np.ndarray", v_a: "np.ndarray", v_b: "np.ndarray", t_change_s: list[float]) -> dict
    # speed RMS of a against b over the window; t63 of each at every change (px4_trajectory.time_to_63pct); peak
def step_verdict(results: dict, gates: dict) -> str       # "PASS" | "FAIL" | "INFO" (fewer windows than real_min_windows)
```
`scripts/physics_step_tests.py --phase windows --name <n>` (host, CPU): read log103 (check the sha256 prefix), rebuild S1's windows with `fit_real_px4.load_flight` + `make_windows`, keep the six held-out legs (odd indices, as S1's `split.json`), and save `runs/<n>/windows.npz`. `--phase run --headless --gates configs/s2b.toml --name <n>` (container): (1) hover 10 s; (2) the `[step_tests]` steps, one drone (a 1v1 game layout with the other drone 10 m away and still), full layers: physics (Isaac) and tier 1 Starling layer, the same commands; tier 1 is run in the same process on the GPU; the torch reference world is reported as INFO; (3) setpoint-level replay of the six windows through `PhysicsDrone` (start from each window's measured position and speed, level; setpoint sampled at the 0.05 s tick, as the commander sends it), scored against the logged speed with S1's definitions; the extra delay in [−0.10, 0.30] s that minimises RMS is INFO only (D7); (4) the 30° tilt variant (INFO). Gates `[step_gates]`. Reading rule, written in the record: if the physics drone passes against the real log and fails against tier 1, the record says the exploratory tier 1 model is the one that differs from the real drone (its t63 is 0.6 / 0.9 s); if it fails against the real log, the physics drone differs from the real drone, and the gates say by how much.

`scripts/physics_throughput.py --headless --size <2v1|5v3> --num-games <n> --gates configs/s2b.toml --out runs/<name>/results.jsonl` (one process per point, resume as S0): `SvgGame` with the physics backend, random actions on the GPU, filter setting from `configs/s2_game.toml` at launch (recorded), S0's warm-up and 2 repeats. Rows: game-steps/s, drone-steps/s, share of time in the filter, the cascade and PhysX, state writes per tick, GPU memory, NaN count; OOM is a row, not a crash. INFO; the record reads off `trainable_drone_steps_per_s_min`.

- [ ] **Failing tests:**
```python
def test_step_metrics_identical_traces(): ...            # a == b: rms 0, t63 gap 0
def test_step_metrics_known_delay():
    t = np.arange(0, 8, 0.01); a = np.clip((t - 1.0) / 0.3, 0, 1) * 0.5; b = np.clip((t - 1.1) / 0.3, 0, 1) * 0.5
    assert step_metrics(t, a, b, [1.0])["t63_gap_s"][0] == pytest.approx(0.10, abs=0.011)
def test_step_verdict_rules(): ...                        # fake results: one window short -> INFO; tier1 RMS 0.11 -> FAIL; all in -> PASS
def test_windows_phase_refuses_wrong_log(tmp_path): ...  # sha256 prefix mismatch -> exit 2
def test_throughput_row_fields(): ...                     # a CPU torch-world row has every field the record needs
```
- [ ] Run → fail; implement; run → pass.
- [ ] **Runs:** preflight; `--phase windows` on the host; `--phase run` in the container. Record (first line: "Observed in the training simulator (tier 2, Isaac Lab) and tier 1, against real flight logs (13 November 2026, drone_2)"), ledger row, figures `s2b_steps.png` (speed per step: physics, tier 1, command) and `s2b_real_replay.png` (six held-out legs: logged, physics, tier 1). Then throughput: 6 points (2 sizes × 3 game counts), one process each; record (first line: "Observed in the training simulator (tier 2, Isaac Lab), random actions, safety filter on every pair"), ledger row, figure `s2b_throughput.png` (drone-steps/s against games, the S0 tier 2 line and the 20,000 decision line drawn).
- [ ] Lead commits code, tests, figures, records, ledger.

### Task 8: Scripted reference games, paired, physics vs Starling layer

**Files:** Modify `scripts/score.py` (`--presets` accepts `physics`; `--batch-per-pair`; Isaac app started before torch is imported when `physics` is asked; one size per process with `physics`), `core/play.py` only if `MatchResult` needs `upset` (add the field; S2 tests unchanged); Create `scripts/compare_backends.py`; Test `tests/test_score.py` (new tests only), `tests/test_compare_backends.py`; run record `records/<date>_s2b_scripted_compare_record.md`; Modify `records/LEDGER.md`, `scripts/make_s2b_figures.py`.

**Interfaces — Produces:**
```python
# score.py: --presets pure,starling,physics  --batch-per-pair  (default off: S2 behaviour and S2 results unchanged)
#   physics: refuses more than one size per process, --device other than cuda, or a missing --headless (exit 2);
#   builds one IsaacWorld of games_per_band games x M drones and reuses it for every band and pair (new SvgGame each)
# compare_backends.py
def compare(a: dict, b: dict, gates: dict) -> dict        # two scores.json (+ per_game.npz) -> per-cell gaps, verdict
```
`compare_backends.py --a runs/<n>_starling --b runs/<n>_physics_2v1,runs/<n>_physics_5v3 --gates configs/s2b.toml --name <n>`: per cell (Guard × Strike × size × band) the hold-rate gap with both Wilson intervals; outcome agreement on paired games (INFO); mean end-step gap (INFO); closest opposite approach on physics; upsets; NaN. PASS when every cell's |gap| ≤ 0.10, physics closest approach ≥ 1.0 m in every game, upsets 0 and NaN 0.

- [ ] **Failing tests:**
```python
def test_batch_per_pair_pairs_starts(tmp_path): ...       # pure preset, 2 pairs, CPU: slot k of pair j has the same arena and starts in two runs
def test_batch_per_pair_off_is_s2_unchanged(tmp_path): ... # scores.json rows equal to a run without the flag
def test_score_physics_refuses_two_sizes(): ...           # --presets physics --sizes 2v1,5v3 -> exit 2, no app started
def test_compare_gate_rule(): ...                         # fake tables: one cell gap 0.11 -> FAIL; closest 0.99 -> FAIL; else PASS
def test_compare_reports_local_file_none(): ...           # both inputs used --no-local, else refuse
```
- [ ] Run → fail; implement; run → pass.
- [ ] **Runs:** preflight. Starling side: `score.py --presets starling --sizes 2v1,5v3 --batch-per-pair --games-per-band 1000 --seed 0 --no-local` (GPU, no Isaac). Physics side: the same with `--presets physics`, once per size, in the container, headless. Then `compare_backends.py`. Record (first line: "Observed in the training simulator: tier 2 (Isaac Lab) against tier 1 (Starling layer, exploratory), paired scripted games, committed neutral values"), ledger row, figure `s2b_scripted_compare.png` (hold rate with intervals per band, both backends side by side, one panel per size × Strike behaviour).
- [ ] Lead commits code, tests, figure, record, ledger.

### Task 9: Stand-in trainer on both backends (S2 Task 10, moved)

**Files:** as S2 plan Task 10 (`scripts/train_standin.py`, `source/svg_training/opponents/learned.py`, `tests/test_train_standin.py`, `docs/PLUG_IN.md` worked example, `scripts/make_s2_figures.py`), plus `--motion {pure,physics}` and the Isaac start; run records `records/<date>_s2b_standin_torch_record.md`, `records/<date>_s2b_standin_isaac_record.md`; Modify `records/LEDGER.md`.

**Interfaces — Consumes:** `SvgSkrlEnv`, `SvgTeamVectorEnv` (S2 Task 9), `score.py` (Task 8), `configs/s2.toml [standin]` / `[standin_gates]` **unchanged**. **Produces:** exactly the S2 plan Task 10 interfaces (`SkrlPolicyStrategy`, `make_strategy` accepting a run folder), and:
```python
# train_standin.py --config configs/s2.toml --seed <s> --name <n> [--motion pure|physics] [--timesteps-override n] [--device cuda]
#   pure (default): [standin] as committed (preset "pure", PyTorch). physics: the same settings with
#   starling_layer.enabled = true, backend = "physics", IsaacWorld(num_games, 3) (needs --headless; Isaac started first).
#   interface.toml gains: motion, physics_params file + sha256 (physics only), world label
```
Evaluation as S2 Task 10. Each seed is scored with `score.py` on the backend it trained on (`--presets pure` or `--presets physics`), 2v1, 1,000 games per band, evaluation seed = seed + 1000, trained against random Guard. PASS per `[standin_gates]`. The record states the game-steps reached against 50 M, and whether the 45-min wall-clock cap stopped the run.

- [ ] **Failing tests:** the S2 plan Task 10 tests (`test_standin_smoke`, `test_learned_refuses_other_team_size`, `test_make_strategy_loads_run_folder`, `test_standin_ignores_local_file`, `test_standin_gate_rule`), plus:
```python
def test_standin_physics_smoke_torch_world(tmp_path): ... # --motion physics with a TorchRigidBodyWorld injected (test hook), CPU, 16 games,
                                                          # --timesteps-override 100: agent.pt and interface.toml (motion = "physics/torch-reference ...")
def test_standin_physics_refuses_torch_world_for_runs(): ... # without the test hook, --motion physics builds IsaacWorld or exits 2
def test_standin_config_unchanged(): ...                  # [standin], [standin_gates] sha256 as pinned in Task 1
```
- [ ] Run → fail; implement; run → pass.
- [ ] **Run 1, control (PyTorch):** `nvidia-smi`; gates `[standin_gates]` copied to `runs/<date>_s2b_standin_torch/gates.toml`; seeds 1, 2, 3 one after another in the background; evaluation; record (first line: "Observed in the training simulator, tier 1, pure partner rules (committed neutral values); stand-in pipe test, not a strategy of record"), ledger row, figures.
- [ ] **Run 2, Isaac Lab:** preflight; the same gates copied to `runs/<date>_s2b_standin_isaac/gates.toml`; `--motion physics`, seeds 1, 2, 3 in the container, headless; evaluation on physics; record (first line: "Observed in the training simulator (tier 2, Isaac Lab), physics drone with the safety filter on every pair (committed neutral values); stand-in pipe test, not a strategy of record"), ledger row, figures. **If run 2 fails and run 1 passes, the record says the fault is in the Isaac Lab path,** citing Task 5 (wrapping agreement) and Task 7 (drone model) to say which part. Wording everywhere: "stand-in" and "pipe test".
- [ ] Add the worked example to `docs/PLUG_IN.md` (load the stand-in as a `Strategy`, score it, retrain it, with `--motion physics` shown). Lead commits code, tests, guide, figures, records, ledger.

### Task 10: Documents and final review

**Files:** Create `docs/S2B_RESULTS.md`; Modify `docs/claude/HANDOFF.md`, `README.md`, `CLAUDE.md` (status lines), `docs/WHAT_WE_DID.md` (chapter "S2b: the game on Isaac Lab drones"), `docs/GLOSSARY.md`, `docs/DESIGN.md` §4 (tier 2 today) and §8 (an S2b row; S4 keeps the cross-check in the construction-site world), `STANDARDS.md` §5 (tier 2 row: own rotor model, rotor positions D4; status labels change only with the owner's word).

- [ ] `docs/S2B_RESULTS.md` for a newcomer: what was built (a generated flowchart: game → command chain → physics drone → Isaac world, and the two other backends beside it), a still frame and a link to each clip with its caption, then one short section per run (agreement, step tests, throughput, scripted compare, stand-in × 2), each with its figure, a caption of at most 400 characters and a 2–3 sentence reading; the gate table with PASS / FAIL / INFO and the record links; what S2b does not do (below); what waits on the owner.
- [ ] GLOSSARY: physics backend, physics drone, PX4 cascade, rotor model, torch reference world (test oracle), agreement, upset, paired games, preflight.
- [ ] Docs check: no partner number anywhere (`test_local_values_not_in_tracked_files` with the local file present); STANDARDS §2 wording; every number traced to a record; simulator named; `git -C .. status --short -- AirStack tools patches mocap mocap.sh starling_1_indoor_params.params localisation` prints nothing.
- [ ] Final review: `train-gatekeeper` reads each S2b record with its `gates.toml` and ledger row; `train-drone-dynamics` reviews `px4_cascade.py` against PX4 v1.14.0 line by line; `train-isaaclab-engineer` reviews the adapter; a code review of the whole S2b diff (superpowers:requesting-code-review) against this plan; `panel-newcomer-reader` reads `S2B_RESULTS.md`. Fix rounds until no Critical or Important finding is open. Quote the full test-suite output (CPU and `-m isaac`) in HANDOFF; tick the STANDARDS §11 checklist.
- [ ] Lead commits the documents with explicit paths; refresh the HANDOFF copy in `~/Downloads/`.

## What S2b does not do

- No `DirectMARLEnv` task (D1, open question 1); no world, obstacles or PhysX contact tags. Drones have no colliders; contact stays the core 0.50 m rule. The construction-site world and the full cross-check stay in S4.
- No estimator, no sensor noise, no transport delay, no drag (not identified), no centre-of-mass offset, no battery sag, no allocator saturation feedback to the rate integrator; the gyro low-pass is left out (D6).
- No gain tuning of any kind, and no refit of the tier 1 model. A gap between the backends is recorded, not closed.
- No flight-control (thrust and body-rate) policy (use 3), no camera policy (use 4); the video camera is for people only.
- No change to the S2 gates, the S2 tasks or their results; `--batch-per-pair` and the `physics` preset are additions with S2 behaviour unchanged by default.
- Nothing here is a flight result or authorises a flight.

## Owner's answers (16 November 2026, "go with ur picks")

| # | Question | Answer |
|---|---|---|
| 1 | Also register the game as a standard Isaac Lab task? | **Yes**: a thin registration wrapper over the same environment, so partners can use Isaac Lab's usual tools and trainers. |
| 2 | Which rotor layout? | **As planned**: the body from CMU's CAD rotor positions (the owner's 19 October decision for the AirStack sim); PX4-style motor mixing from the drone's own parameters. |
| 3 | Real gains unstable with motor lag? | **One pre-written fallback allowed**: the AirStack sim's sim-only rate gains × 0.5 (ledger #10), labelled sim-only. Anything beyond it: BLOCKED, ask the owner. |
| 4 | `configs/s2b.toml` gates | **Approved as proposed**; written before any run, never moved. |
| 5 | Wall-clock cap for the Isaac stand-in | **Keep the 50 million game-step budget; cap 3 hours for the Isaac run only**; the PyTorch runs keep 45 minutes. |
| 6 | Stand-in control runs | **Both PyTorch variants**: pure partner rules and the Starling layer (the fair twin of the Isaac physics), each its own ledger row. |
| 7 | Isaac MP4s in git? | **Yes**, each under 10 MB, in `docs/media/`. |

## Addition (owner, 16 November 2026): TensorBoard for every training run

The stand-in task (both backends) and every later training run log to TensorBoard:

- skrl's own curves (rewards, losses, learning rate) in the run folder `runs/<run name>/` — skrl writes them by default;
- the game's own numbers, every evaluation interval, as extra scalars under `game/`: hold rate (trained Guard against each scripted Strike behaviour), share of games won by time-out, closest Guard–Strike approach (3-D, minimum and 5th percentile), filter share, game-steps per second;
- the run's settings (game config hash, seed, backend, preset) as TensorBoard text, so two runs can be told apart.

Test: a 1-minute CPU smoke run writes an event file whose tags include `game/hold_rate`. `docs/TRAINING.md` gets the exact command (`tensorboard --logdir runs/`, host side, then `http://localhost:6006`; safe over the remote desktop because it is only a web page). No cloud logging service (the partner's numbers must not leave the laptop).

## Owner's answers, second round (16 November 2026, "yes")

| # | Question | Answer |
|---|---|---|
| A | The games gate "physics closest Guard–Strike approach ≥ 1.0 m in every game" fails by construction (S2's T9: on tier 1 a drone held at a wall plus a team-mate squeeze already reaches 0.75–0.80 m; some games start closer than 1.0 m) | **Replaced, before any S2b run:** per matchup cell, in games without a start miss, the 3-D closest Guard–Strike approach under physics (minimum and 5th percentile) may be at most **0.10 m** below the tier 1 Starling layer's on the same paired games (`closest_cross_3d_gap_max_m` in `configs/s2b.toml`, Task 1). Wherever the plan's text still names `physics_closest_cross_min_m`, the builder uses this rule instead. |
| B | Make the training copy's safety filter wall-aware (it would no longer match CMU's)? | **No: keep the filter faithful to CMU's.** The wall effect is recorded as a real-drone hazard hypothesis (the commander runs the filter before the keep-in fence); a fix belongs in CMU's commander, the owner's call. |

## Corrections during the build (checked against PX4 v1.14.0 source, `git show v1.14.0:<path>`)

- **Yaw attitude gain** (D6 / Task 3 step 7): PX4 v1.14 `AttitudeControl::setProportionalGain` divides the yaw gain by the yaw weight, so the yaw P is `MC_YAW_P / MC_YAW_WEIGHT` (7.0 with the drone's values), not `MC_YAW_P`.
- **D-term filter** (D6 / Task 3 step 7): first-order `AlphaFilter` on the raw angular rate (`VehicleAngularVelocity.hpp:172`, alpha 0.557 at 200 Hz), not a second-order Butterworth.
- **Rate gains**: K multiplies P, I and D; feed-forward stands alone (`rate_control.cpp`). Identical here because every K is 1 on the drone.
- **Known differences for Task 7**: `THR_MDL_FAC` 0.9 and `MPC_USE_HTE` 1 (hover-thrust estimator) are on the drone but not modelled (fixed hover thrust 0.165, linear motor).

## Amendment (lead, 16 November 2026): the registered Isaac Lab task

The owner's answer 1 (register the game as a standard Isaac Lab task) has no owning task in the list above, and "What S2b does not do" says "No DirectMARLEnv task", which contradicts it. Resolution: **Task 8b, after Task 8** — a thin `DirectMARLEnv` wrapper over the same `SvgGame` with `backend = "physics"` and `IsaacWorld` (no second game code path), registered with `gymnasium.register` under the name `Isaac-SvG-StrikeGuard-v0`; its test runs one short headless episode through Isaac Lab's own environment loop and checks the observations and rewards equal the game's for the same seed. Task 10 documents it in `docs/PLUG_IN.md`. The "No DirectMARLEnv task" line is superseded.

Note for Task 7 (gatekeeper, T10 review): T10 ran 64 games (~320 m extent); at training scale (4,096 games at 40 m spacing, ~2.5 km) float32 positions step ~2.4e-4 m — measure precision at that extent.

## Owner's ruling, 16 November 2026 (night): sim-only yaw gains

The Global Constraint and Review Focus 5 ("no yaw-rate 0.25 / 0.2 in any S2b file") are **superseded for these three values**: the owner ruled that the physics drone uses the AirStack simulator's SIM-ONLY yaw-rate gains `MC_YAWRATE_P/I/D` = 0.25 / 0.2 / 0 (precedent CHG-0024), because with the drone's own gains, ModalAI's 15 Hz yaw filter and motor lag the modelled yaw does not settle (likely the missing rotor-inertia torque). They live only in `params/sim_only_yaw_v0.toml` (labelled SIM-ONLY, default for `backend = "physics"`); every other value stays the drone's own, and records name the yaw setting used. T10's FAIL is accepted (same ruling).

## Owner's answer, third round (17 November 2026, "the game-design should follow (a)")

Task 8 found that on the physics drone the Strike drone passes over or under a Guard drone: CMU's 3-D collision
filter, which the game copies faithfully, escapes vertically once millimetre height differences break tier 1's
exact equal-height symmetry (observed in the training simulator; not flown). Options put to the owner: (a) keep it,
Guards must learn to cover height; (b) pin every drone's height in the game; (c) a narrower height band.

**Answer: (a).** Vertical passing stays part of the game on the Starling layer and the physics drone. Consequences,
for later stages, not S2b: the Guard team's policy uses its vertical-speed output (the stand-in's `[standin_v2]`
proposal already leaves vz trained for `starling` and `physics`); scripted Guards that only move sideways are
expected to lose to a straight Strike on the physics drone, which is recorded, not fixed; the pure partner-rules
preset stays 2-D as NUS's game is. No S2b gate, task or result changes.
