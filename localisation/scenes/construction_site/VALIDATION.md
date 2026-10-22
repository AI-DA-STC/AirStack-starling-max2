# Construction-site arena: step-by-step validation ladder

One change per step. Each step has a command, a pass test that needs no GUI, and a resource cap. Do not go to the
next step until the current one passes. Written 2026-10-22 after two "laptop hangs" that were in fact the Intel BE200
WiFi firmware crashing within 30 s of an Isaac start/stop (kernel log: `iwlwifi ... Error sending SYSTEM_STATISTICS_CMD`,
then `kworker blocked for more than 122 seconds`), which drops the remote-desktop session while Isaac keeps running.

## Results 2026-10-22
Steps 1–7 all passed on the laptop over WiFi, 9 Isaac starts/stops, 0 WiFi firmware alerts. Flight score in `results/sim_site_run1_record.md`.

## Step 0: network (blocks everything else)
- Work on the laptop directly, or plug in Ethernet and connect the remote desktop to the Ethernet IP. WiFi must not be
  the session's only link while Isaac starts.
- Optional trials if WiFi keeps crashing even unused: boot kernel `6.17.0-20` from GRUB, or `options iwlwifi disable_11be=1`
  in `/etc/modprobe.d/iwlwifi.conf` (ask before changing system config).
- In every later step keep `scripts/sim_resources_watch.sh results/res_stepN.log` running in a laptop terminal.
  It prints `WIFI-ALERT` the moment the firmware crashes, and VRAM/load alerts. It never kills anything.

## Common launch line (Isaac tab, inside the isaac-sim container)
```
DRONE_USD=/isaac-sim/AirStack/simulation/isaac-sim/assets/robots/starling2max.usd PX4_VEHICLE_MODEL=pegasus_starling2max \
NUM_ROBOTS=<N> SVG_DOMAIN_ID=1 PLAY_SIM_ON_START=true ISAAC_SIM_HEADLESS=true \
<extra env from the step> \
PYTHONPATH="$ISAAC_SIM_PYTHONPATH" /isaac-sim/python.sh /isaac-sim/AirStack/simulation/isaac-sim/launch_scripts/svg_multi_drone_single_domain.py \
  --ext-folder ~/.local/share/ov/data/documents/Kit/shared/exts
```
Pass checks run from the exploration container (`cd ~/AirStack-starling-max2/localisation && ./docker/run.sh`):
- real-time factor and image rate: `python3 scripts/sim_check.py` (prints RTF over 10 s, image Hz, saves a frame, ORB corners, sky mean)
- camera frame: `python3 scripts/grab_frame.py drone_1 results/frame_stepN.png`
Stop the sim: Ctrl-C in the Isaac tab (or `docker exec isaac-sim pkill -INT -f svg_multi_drone`), wait 10 s, check the watch log for a WIFI-ALERT.

| Step | Single change | Extra env | Pass | Cap |
|---|---|---|---|---|
| 1 | baseline, default world | `NUM_ROBOTS=1` | `Ready for takeoff!` x1 within 3 min; RTF >= 0.8 | note VRAM V0 |
| 2 | + cropped world | `ENV_USD=/isaac-sim/.local/share/ov/data/scenes/construction_site/construction_site_r40.usdc NUM_ROBOTS=1` | ready < 2 min; RTF >= 0.6; VRAM <= V0 + 2.5 GB; 10 min soak with no WIFI-ALERT | load1 < 16 after 2 min |
| 3 | + camera | step 2 + `ENABLE_CAMERA=true CAMERA_DRONES=drone_1` | image >= 15 Hz; frame ORB >= 500; sky rows mean > 40; VRAM <= step 2 + 1.5 GB | |
| 4 | + 3 drones | step 3 with `NUM_ROBOTS=3` | ready x3; RTF >= 0.5; image >= 15 Hz; 10 min soak | |
| 5 | + cuVSLAM node | `scripts/slam_up.sh` (exploration container) | status rate >= 10 Hz; at rest, odom drift < 0.05 m over 60 s | |
| 6 | + flight + scoring | Interfaces/Commander/Cockpit tabs, `random_goals` | no odom jump > 1 m between consecutive poses; `scripts/score_run.sh` runs | |
| 7 | full site (flattened, all objects) | `ENV_USD=/isaac-sim/.local/share/ov/data/scenes/construction_site/construction_site_full.usdc` | same as 4 | PASSED 2026-10-22 23:15: 1 drone RTF 2.2 / 4.9 GB; 3 drones + camera RTF 1.4 / 4.3 GB, 41 Hz, 1987 corners, 0 WiFi alerts. Now the default world. |

## Resource notes from the reviews (2026-10-22)
- The site's meshes arrive through payloads after `wait_for_stage` returns, so the launcher's `add_colliders` never
  touched them (9 colliders added, all from Added_Assets). The site meshes already carry PhysX collision attributes
  (4,964 convex hull, 645 triangle). Drones do collide with the site through those.
- Full scene: 125k prims, 5.6k meshes, 5.8 M faces, 12.3k material prims (137 unique). Cropped r40: see `crop_site.py` output.
- Kit flags can be appended to the launch line (the launcher forwards unknown args): e.g.
  `--/rtx/indirectDiffuse/enabled=false --/rtx/ambientOcclusion/enabled=false --/rtx/reflections/enabled=false`
  `--/rtx/translucency/enabled=false --/rtx/post/dof/enabled=false --/rtx/post/motionblur/enabled=false`.
  Use only if a step fails its cap; one flag group per retry.
- `PX4_RENDERING_HZ=15` (Pegasus env) halves render work if the RTF cap fails.
