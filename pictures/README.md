# pictures/ — what each image shows, and whether it is still current

> **RECORD.** Nothing here is deleted; this index says what each picture proves, which docs use
> it, and whether it needs re-shooting. Last reviewed 2026-10-21.

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

## Pictures this branch still needs

1. **Now, in sim:** the four-tab Terminator session (`tools/sim_terminals.sh`), Isaac with the Starling 2 Max model, the panel in its healthy sim state (`0 sim · 3 real` is the known cosmetic mis-detection).
2. **M2 hand-carry:** panel `EKF EV FUSED`, QGC local position following the carried drone, the `px4_interface … target_system=N` startup line with the matching `MAV_SYS_ID`, the new topic list — these replace the four previous-branch evidence shots above.
3. **After the camera upgrade:** Motive streaming pane + IP, replacing the three Motive shots.
4. **After M3:** the redrawn control-flow diagram as an SVG next to the PNG.

GIFs used by the README gallery live in `../assets/` and are all current (one per video in `../videos/`).
