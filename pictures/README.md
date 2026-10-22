# pictures/ — what each image shows, and whether it is still current

> **RECORD.** Nothing here is deleted; this index says what each picture proves, which docs use
> it, and whether it needs re-shooting. Last reviewed 2026-10-23.

**Size policy (2026-10-23):** ≤ 1600 px wide and ≤ 500 KB. JPG q85 for renders and desktop screenshots, PNG for small UI or
plot crops. Full-size originals live outside git in `~/Pictures/airstack-originals/`. GIFs ≤ 3 MB go in `../assets/`.
**No new mp4 in git** (the six in `../videos/` stay); a screen recording becomes a GIF plus a contact sheet.

| File | What it shows | Used by | Status |
|---|---|---|---|
| `Starling_Airstack_architecture.png` | Control-flow diagram: mocap → laptop (commander, CBF, agent) → PX4 | README, ARCHITECTURE, CLAUDE.md | **Stale in four places** (drawn for the previous branch): `./mocap.sh` not `./mocap.sh bridge`, `px4_interface` box missing, trajectory setpoint not bare velocity, Foxglove panel as operator view. Corrections listed in ARCHITECTURE.md; redraw as SVG after the first real flight on this branch |
| `Flight_lab_architecture.png` | Lab network topology (mocap LAN 192.168.9.x, drone segment 10.40.2.x) | ARCHITECTURE, CONFIG, CLAUDE.md | Current |
| `check_motive_ip_address.jpg` | Where Motive shows the PC's IP | MOCAP, CONFIG, DRONE_SETUP | Current; **re-shoot after the OptiTrack camera upgrade** (new Motive version / IP) |
| `mocap_axis_1.png`, `mocap_axis_2.png` | Motive axis convention and ground-plane set-up for the frame hand-check | MOCAP, CONFIG | Current; **re-shoot after the camera upgrade** |
| `successful_airstack_connected_to_drone_microuxre.png` | MicroXRCEAgent "session established" with the real drone (previous branch) | — (unreferenced since the 2026-10-21 README split) | Still valid as evidence: the uXRCE path is unchanged on this branch. Replace at M2 (hand-carry) with this branch's screenshot |
| `successful_read_of_drone_1_vehicle_odom.png` | `/drone_1/fmu/out/vehicle_odometry` echo on the real drone (previous branch) | — | Same as above; replace at M2 |
| `drone_topics.png` | `ros2 topic list` with the drone connected (previous branch) | — | Topic list changed with the branch bump; replace at M2 |
| `computer_detects_drone_and_awb_shell_working.png` | adb sees the drone + `voxl` shell (previous branch) | — | Still valid (adb path unchanged); replace at M2 if convenient |
| `airstack_natnet_working_1.png`, `airstack_natnet_working_2.png`, `awbshell_with_airstack_natnet_working.png` | CMU's `natnet_ros2` receiver streaming (August 2026) | — | **Obsolete**: replaced by the `./mocap.sh` bridge on 2026-08-27 (MOCAP.md §3). Kept for the archive; do not use as a reference |
| `voxel_setup_px4_restart_and_client_status.png` | `systemctl restart voxl-px4` output (August 2026) | — | **Obsolete and misleading**: that restart is forbidden by iron rule 7 (reboot instead). Kept for the archive only |
| `full_sim_run.jpg` | The whole camera-world sim session after landing, numbered ①–⑤: SLAM Studio `:8766`, the cuVSLAM debug image, the `slam_up.sh` status line, the bag recorder, Basestation Studio `:8765` | `localisation/README.md` | Current (sim, construction site, 2026-10-23) |
| `construction_site.jpg` | The construction-site world from above, numbered ①–③: cranes and building frames, the excavation, containers and plant | `localisation/scenes/construction_site/README.md` | Current (sim, 2026-10-23) |
| `drones_in_construction_site.jpg` | The three simulated Starling 2 Max drones over the sand patch beside the containers | `localisation/README.md` | Current (sim, 2026-10-23) |
| `vo_flat_frame.png`, `vo_site_frame.png` | drone_1's left camera at 640×480: the flat default world (sky, horizon, grid) vs the construction site | `localisation/README.md` (flat vs site figure) | Current (sim, 2026-10-22) |
| `vo_flat_xy_cam_run3.png`, `vo_site_xy_site_run1.png` | Top-down x-y, PX4 reference (blue) vs cuVSLAM (orange): `sim_cam_run3` jumps away; `sim_site_run1` stays on the reference | `localisation/README.md` (flat vs site figure) | Frozen copies of the runs named in the file |
| `sim_two_networks.svg` | Diagram: the isaac docker network vs the host network; DDS stays inside, MAVLink crosses; the two Foxglove Studios (8766, 8765) | ARCHITECTURE "Sim session anatomy" | Current 2026-10-23; hand-written SVG, the comment inside names what to redraw it from |
| `vo_scoring_flow.svg` | Diagram: bag + PX4 ulog → `score_vs_ulog.py` (convert, clock offset, SE(3) align, APE/RPE) → json + plot | `localisation/README.md` "How a run is scored" | Current 2026-10-23; hand-written SVG |
| `randompos_construction_sheet.jpg` | Six frames, 8 s apart, of the 2026-10-23 random-goals flight in the site (both Studio windows, Isaac, terminals) | `localisation/README.md` | Current (sim, unscored flight; source video `~/Videos/randompos_construction.mp4`, not in git) |

## Pictures this branch still needs

1. **Now, in sim:** the four-tab Terminator session (`tools/sim_terminals.sh`), Isaac with the Starling 2 Max model, the panel in its healthy sim state (`0 sim · 3 real` is the known cosmetic mis-detection). *Partly done 2026-10-23: `full_sim_run.jpg` shows Isaac, the panel and SLAM Studio after landing; a clean shot of the four tabs is still open.*
2. **M2 hand-carry:** panel `EKF EV FUSED`, QGC local position following the carried drone, the `px4_interface … target_system=N` startup line with the matching `MAV_SYS_ID`, the new topic list — these replace the four previous-branch evidence shots above.
3. **After the camera upgrade:** Motive streaming pane + IP, replacing the three Motive shots.
4. **After M3:** the redrawn control-flow diagram as an SVG next to the PNG.

GIFs used by the README gallery live in `../assets/` and are all current (one per video in `../videos/`, except
`randompos_construction_10fps.gif`: cuVSLAM debug image + Basestation 3D side by side, from a screen recording kept outside git).
