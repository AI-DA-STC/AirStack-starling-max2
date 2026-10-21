# AirStack — Starling Max 2 lab snapshot (code folder)

**What this folder is:** a frozen, working copy of CMU AirStack with our lab's edits applied —
the exact code the docs in `../docs/` describe. **Who reads this file:** anyone who wonders why
this folder differs from a fresh CMU clone, or needs to know which files are ours and which are
CMU's before editing or re-vendoring.

**Where it comes from:** [castacks/AirStack](https://github.com/castacks/AirStack), branch
`yikuan/SVG_ground_control_dev` @ `b21d28c` (since **2026-10-20**, commit `b059686` of this repo).
The first snapshot (2026-10-07) was the release line `yikuan/SVG_ground_control` @ `cf719f0`; the
bump applied `git diff cf719f0 b21d28c` (26 files in `robot/ros_ws/src/svg_ground_control/` + one
agent skill) as a patch — [`../docs/MIGRATION.md`](../docs/MIGRATION.md) §11. Our own edits
(table below) were kept through the bump. Our one still-needed local bug fix is already applied
(camera-info init race in PegasusSimulator — patch file and explanation in
[`../patches/`](../patches/), one level up in this repo). The second patch from the previous
snapshot (swarm_commander logger-severity crash) is **already fixed upstream** on this branch and
is no longer applied.

**Why it exists:** insurance. Both `yikuan/SVG_ground_control_dev` and `yikuan/SVG_ground_control`
are personal branches on CMU's repo — either could be rebased, changed, or deleted at any time.
This snapshot is the exact code our documentation on this branch describes, so the lab can always
rebuild the same setup.

**Previous snapshot:** the earlier copy (branch `daniel/diffaero_ground_control`, commit
`f544c743`, taken 2026-07-20, flown 2026-09-01→03) is preserved on git tag
`airstack-starling-max2` and branch `archive/airstack-starling-max2` of this repo. The two
AirStack branches are **siblings** (common ancestor `a46f04b` "goal tracking verified"), not
parent and child — see [`../docs/MIGRATION.md`](../docs/MIGRATION.md) for what changed.

**Differences from a normal AirStack clone:**

- Git submodules are included as **plain folders** — no `git submodule update` needed, and
  no `.gitmodules` file. Fully self-contained. Submodule commits at snapshot time:
  `PegasusSimulator` `8e01d01`, `macvo` `8683b53`, `vdb_mapping` `07cfb7b`,
  `vdb_mapping_ros2` `2d6d171`, `xdot_cpp` `c3afaf8`, `rviz_polygon_selection_tool` `018c746`.
  **The Pegasus folder carries our edits** (table below) on top of `8e01d01` — it is not a
  pristine submodule checkout.
- Patch 0001 is already in the code — do **NOT** re-apply it on top of this snapshot.
- Two machine-specific config files are excluded (`simulation/isaac-sim/docker/omni_pass.env`
  and `user.config.json`) — `./airstack.sh setup` generates both automatically (press Enter at
  its "API Token" prompt to skip the CMU-only Nucleus login).
- `AGENTS.md` and `.agents/skills/svg-release-branches` describe **CMU's own** branch workflow
  (develop on `_dev`, squash-release to `yikuan/SVG_ground_control`). That is **not** how this
  repo works: we commit everything to `main` and the user pushes via GitHub Desktop.
- The OptiTrack NatNet SDK is **not** included (it is a binary download CMU's `.gitignore`
  excludes). Run `robot/ros_ws/src/perception/natnet_ros2/install_sdk.sh` once before the
  first build, or `natnet_ros2` will not compile. Our `./mocap.sh` bridge does not need it,
  but the workspace build does.

**Ours vs CMU — every file we changed inside this folder** (none of it is upstream; re-apply on
a fresh CMU clone). "Sim" = only the Isaac Sim path loads it; "real" = flown on the drone;
"shared" = code both paths run. Paths relative to this folder; `PEG` =
`simulation/isaac-sim/extensions/PegasusSimulator/extensions/pegasus.simulator/pegasus/simulator`.

| Path | What | Since | Sim / real |
|---|---|---|---|
| `simulation/isaac-sim/assets/robots/starling2max.usd` | Starling 2 Max asset — CMU sys-ID masses; body parts < 2 mm culled, no decimation | 10-19, rebuilt 10-20 | sim |
| `simulation/isaac-sim/px4/airframes/10090_pegasus_starling2max` | PX4 SITL airframe: real attitude/position gains; rate gains ×0.5 + gyro filters 80/40; `LNDMC_ROT_MAX` 300; MPC speed/accel limits = the real drone's | 10-19, 10-20 | sim |
| `simulation/isaac-sim/docker/docker-compose.yaml` | one volume line: airframe bind-mounted into PX4's ROMFS source dir | 10-19 | sim |
| `simulation/isaac-sim/launch_scripts/launch_env.py`, `svg_multi_drone_single_domain.py` | `DRONE_USD` / `PX4_VEHICLE_MODEL` env handling; lidar-import fix | 10-19 | sim |
| `simulation/isaac-sim/tools/*` | asset cleaner, hover/step and CBF-crossing test scripts, step analysis, `launch_env` tests | 10-19, 10-20 | sim |
| `PEG/logic/thrusters/lagged_quadratic_thrust_curve.py` | motor-lag thrust curve (default lag 0 = off) | 10-19 | sim |
| `PEG/logic/vehicles/multirotors/registry.py`, `starling2max.py` | `Starling2MaxConfig` + the name → config registry | 10-19 | sim |
| `PEG/ogn/python/nodes/OgnPegasusMultirotorNodeBase.py` | vehicle config chosen by the USD file name (`create_multirotor`) | 10-19 | sim |
| `PEG/tests/unit/*` | unit tests for the above | 10-19 | sim |
| `robot/ros_ws/src/interface/interface_bringup/launch/mavros_px4.launch.xml` | `mavros_node` declared with `respawn="true"`, 2 s delay | 10-20 | sim only — real drones use `px4_interface`, never this file |
| `robot/ros_ws/src/svg_ground_control/svg_ground_control/swarm_commander.py` | `land_settle_s` (settle on the ground before DISARM) + `land_disarm_step` (retry a denied DISARM) | 10-19, 10-20 | shared code — the real `_ours` configs set `land_settle_s` 0.0, so real landings are unchanged |
| `robot/ros_ws/src/svg_ground_control/test/test_landing_settle.py` | tests for the two landing changes | 10-19, 10-20 | — |
| `robot/ros_ws/src/svg_ground_control/config/cbf_sim.yaml` | our sim run config: speeds 2.0 / 4.0 / 6.0, settle 2.0 s + disarm retry | 10-19, 10-20 | sim |
| `robot/ros_ws/src/svg_ground_control/config/swarm_real_ours.yaml`, `goal_single_ours.yaml` | our real-drone configs: `drone_1`, hover 0.5 m, `land_speed_mps` 0.6, ±2 m fence, `land_settle_s` 0.0 | 10-07, 10-20 | real |
| `README.md` (this file) | snapshot README | 10-07 | — |
| `PEG/ogn/api/spawn_zed_camera.py` (patch 0001) | ZED camera-info init race fix (`../patches/0001-*.patch`) | 2026-09 | sim |

Everything else in this folder is CMU's as of `b21d28c`. The values the sim airframe and the
configs carry are listed in [`../docs/CONFIG.md`](../docs/CONFIG.md); what each change fixed is
in [`../docs/MILESTONES.md`](../docs/MILESTONES.md) §3c (ledger #1–#13).

**How to use it:** follow "Setting up AirStack on a NEW machine" in the
[repo README](../README.md) one level up — this folder itself is your working folder
(`~/AirStack-starling-max2/AirStack`). No submodule or patch steps are needed.
