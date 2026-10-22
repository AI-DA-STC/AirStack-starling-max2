# Effort log (exploration phase)

| Date | Item | Time | Outcome / blockers |
|---|---|---|---|
| 2026-10-22 | Literature review (4 research agents + report) | ~1 h wall | reports/Multi drone localisation methods review.md |
| 2026-10-22 | cuVSLAM v17.0.1 wheels + SDK source + evaluation tarball downloaded; SHA256 recorded | 10 min | EuRoC classic URL dead (dataset moved to ETH Research Collection, 12 GB archive, browser download) |
| 2026-10-22 | Exploration Docker image (CMU robot image + CUDA 12.6 libs + cuvslam cu12 + gtsam) | build ⏳ | |
| 2026-10-22 | cuvslam_stereo_node.py written (rig from camera_info, FLU conversion, status topic) | 30 min | not yet run |
| 2026-10-22 | Exploration image built (29.5 GB); smoke test: cuvslam 17.0.1 + RTX 5070 Ti, 68/68 SDK tests OK | 25 min | Blackwell works with the cu12 wheel |
| 2026-10-22 | DDS: Isaac bridge topics invisible to host-network containers; static peers failed; fixed by `--network container:isaac-sim` | 40 min | documented in sim_cam_run1_record.md |
| 2026-10-22 | **sim_cam_run1**: cuVSLAM on drone_1, 3-drone random_goals 180 s, scored vs PX4 ulog | 45 min | APE 0.25 m / 141 m, 0 losses — pipeline proven; first scorer used the takeoff edge for the clock offset (wrong by 2.4 s), replaced by an offset search |
