# Public datasets for offline evaluation of multi-drone relative localisation (UWB + stereo/IMU, multi-agent with ground truth)

Research date: 2026-10-22. Link liveness checked with `curl -L` on that date unless stated otherwise. Target use: (a) per-drone VIO + UWB frame-alignment estimator, (b) collaborative SLAM, both scored as inter-agent relative error with evo. Lab sensors: RealSense D435i stereo+IMU, Nooploop LinkTrack UWB.

## Overview: which datasets to download this week

### Takeaway
Only one public dataset combines several drones flying simultaneously, inter-drone UWB ranging, stereo+IMU, and mocap ground truth: MILUV (McGill DECAR, 2025, three Uvify IFO-S with RealSense D435i and DW1000 UWB, Vicon, 173-186 GB, CC BY 4.0, open on figshare). Everything else is a compromise: NTU VIRAL (single drone, UWB to fixed anchors, Leica GT; NTU repository was down on 2026-10-22, SharePoint mirror exists), HKUST Omni-swarm/D²SLAM Dropbox bags (multi-drone, fisheye not stereo, mocap GT partly, documentation thin), EuRoC split into pseudo-agents (no UWB), S3E (3 ground robots, stereo+IMU+inter-robot UWB, ROS 2, 278 GB, CC BY 4.0), and the TIERS Turku UWB-mocap sets (ground robots, DWM1001, rosbags on SharePoint).

### Cited Findings
- MILUV: "three Uvify IFO-S quadcopters, each equipped with two custom-made UWB transceivers, a stereo camera, two IMUs, a magnetometer, a downward-facing camera, a barometer, and a downward-facing laser rangefinder", with 6 static UWB anchors, 48 AprilTags and a Vicon system; 173 GB, 217 min of flight; authors state that "to the authors' knowledge, there is no multi-UAV dataset with UWB transceivers prior to this work" — [MILUV arXiv 2504.14376](https://arxiv.org/abs/2504.14376); published in IJRR 2026 — [SAGE DOI 10.1177/02783649251405898](https://dx.doi.org/10.1177/02783649251405898)
- MILUV figshare record: licence CC BY 4.0, published 2025-02-25, not embargoed/confidential, 39 zip files totalling 185,736,682,062 bytes (~185.7 GB incl. calibration zips) — [figshare API article 28386041](https://api.figshare.com/v2/articles/28386041); DOI landing resolves (HTTP 202 → plus.figshare.com) — [doi.org/10.25452/figshare.plus.28386041.v1](https://doi.org/10.25452/figshare.plus.28386041.v1)
- NTU VIRAL: "two 3D lidars, two time-synchronized cameras, multiple IMUs, and four UWB nodes on the UAV ranging to three anchors", ROS bags, CC BY-NC-SA 4.0, 18 sequences of 4.0-9.4 GB each — [NTU VIRAL site](https://ntu-aris.github.io/ntu_viral_dataset/)
- Omni-swarm README: "to get the raw and preprocessed offical omni-directional and pinole dataset" at https://www.dropbox.com/sh/w5yagas06a9r14d/AACdKgMfCCg07M6jr6Ipmus1a?dl=0 (HTTP 200 on 2026-10-22); "Support NoopLoop UWB module only" — [Omni-swarm README](https://raw.githubusercontent.com/HKUST-Aerial-Robotics/Omni-swarm/master/README.md)
- S3E: three UGVs with 16-beam LiDAR, two colour cameras, 9-axis IMU, UWB and dual-antenna RTK; ROS 2 bags; 13 outdoor + 5 indoor sequences — [S3E project page](https://pengyu-team.github.io/S3E/); Hugging Face repo is cc-by-4.0, 278 GB — [HF PengYu-Team/S3E](https://huggingface.co/datasets/PengYu-Team/S3E)
- EuRoC MAV: stereo WVGA mono 2x20 FPS, MEMS IMU 200 Hz, Vicon 6D pose and Leica MS50 3D position; files hosted on ETH Research Collection — [EuRoC page](https://projects.asl.ethz.ch/datasets/euroc-mav/); record is open access, "In Copyright - Non-Commercial Use Permitted", four ZIPs totalling ~27.8 GB — [ETH Research Collection 690084](https://www.research-collection.ethz.ch/handle/20.500.11850/690084)

### Inferences
- For task (a) (VIO + UWB frame alignment between drones), MILUV is the only dataset where the estimator can be run exactly as designed (per-drone D435i VIO + tag-to-tag UWB ranges + Vicon truth for every drone). NTU VIRAL is a useful single-agent fallback where the "second agent" is replaced by fixed anchors.
- For task (b) (collaborative SLAM), the standard comparison sets in the literature are EuRoC pseudo-agents (COVINS/COVINS-G), TUM-VI room/corridor and HKUST Omni sequences (D²SLAM), S3E and GrAco (Swarm-SLAM), and Kimera-Multi campus sets (request-only). None of these except MILUV give UWB plus stereo on drones.
- Nooploop LinkTrack specifically appears only in HKUST Omni-swarm (module model not stated). No dataset was found that uses LinkTrack with published raw LinkTrack messages, so LinkTrack-specific bias/NLOS behaviour cannot be validated offline from public data.

### Gaps
- No 2026 multi-UAV UWB dataset was found; the newest is MILUV (Feb 2025 release, IJRR 2026). Searches for "multi-UAV dataset UWB", "swarm dataset UWB VIO", "relative localization dataset drones UWB" returned only MILUV, NTU VIRAL, TIERS and method papers — [search summary via arXiv listing](https://arxiv.org/abs/2504.14376).

## NTU VIRAL (Nanyang Technological University, 2022)

### Takeaway
Single-UAV, stereo (uEye 1221 LE, 10 Hz) + VN100 IMU (~385 Hz) + two Ouster OS1-16 + Humatics P440 UWB (4 UAV nodes to 3 anchors, ~68.6 Hz) with Leica MS60 position ground truth at 20 Hz; 18 rosbag sequences (181-583 s, 4-9.4 GB each); CC BY-NC-SA 4.0. Anchor positions are not surveyed; they are self-estimated from anchor-to-anchor ranges and published in the bag. NTU's Dataverse host returned HTTP 503 on 2026-10-22; a SharePoint mirror is linked from the site.

### Cited Findings
- Sensors: two uEye 1221 LE monochrome global-shutter cameras, externally triggered, 10 Hz, 752x480, stereo pair timestamps differ by < 3 ms; VectorNav VN100 configured at 400 Hz (effective ~385 Hz, topic /imu/imu); two Ouster OS1-16 Gen1 at 10 Hz each with internal 100 Hz IMU — [NTU VIRAL paper (ar5iv 2202.00379)](https://ar5iv.labs.arxiv.org/html/2202.00379)
- UWB: two Humatics P440 radios (IDs 200, 201), each with two antennas = four UAV ranging nodes; three anchors (IDs 100-102) → 12 UAV-to-anchor pairs; each ranging step 25 ms; UAV-to-anchor ranges at 68.571 Hz, anchor-to-anchor at 5.714 Hz; signal loss and multipath affect measurements — [NTU VIRAL paper](https://ar5iv.labs.arxiv.org/html/2202.00379)
- Anchor positions: anchors on tripods at nominal z = 1.5 m; anchor 100 is origin, anchor 101 on +x; remaining coordinates estimated from anchor-to-anchor ranges and published on /nodes_pos_sc; paper does not say anchors were surveyed with the Leica — [NTU VIRAL paper](https://ar5iv.labs.arxiv.org/html/2202.00379); a community note (Chinese) states the dataset does not provide the real UWB anchor positions — [gitcode.csdn.net summary](https://gitcode.csdn.net/6a292efb10ee7a33f27a760a.html)
- Ground truth: Leica Nova MS60 MultiStation tracking a prism on top of the UAV, 20 Hz, topic /leica/pose/relative (position only); prism ~0.4 m from body origin; payload flex shifts prism by up to ~2 cm; time alignment error estimated within 0.1 s — [NTU VIRAL paper](https://ar5iv.labs.arxiv.org/html/2202.00379); site warns users often miss the 0.4 m IMU-to-prism offset and links a compensation tutorial; CSV ground truth at https://github.com/ntu-aris/ntuviral_gt — [NTU VIRAL site](https://ntu-aris.github.io/ntu_viral_dataset/)
- Sync: messages timestamped by drivers at ROS publish time; Kalibr found a 20 ms camera-IMU offset (reported, not corrected); lidar stamps mark end of scan — [NTU VIRAL paper](https://ar5iv.labs.arxiv.org/html/2202.00379)
- Known issue: Ouster point cloud and IMU messages jitter due to sync problems (noted 12/07/2022); restamp script at utils/restamp.py — [NTU VIRAL site](https://ntu-aris.github.io/ntu_viral_dataset/)
- Sequences (zip of rosbag, size, duration): eee_01 8.7 GB 398.7 s; eee_02 7.0 GB 321.1 s; eee_03 4.3 GB 181.4 s; nya_01 8.6 GB 396.3 s; nya_02 9.4 GB 428.7 s; nya_03 9.0 GB 411.2 s; sbs_01 7.8 GB 354.2 s; sbs_02 8.2 GB 373.3 s; sbs_03 8.5 GB 389.3 s; rtp_01 5.0 GB 482 s; rtp_02 5.2 GB 439 s; rtp_03 4.0 GB 355 s; tnp_01 8.1 GB 583 s; tnp_02 6.2 GB 457 s; tnp_03 5.5 GB 407 s; spms_01 5.5 GB 446 s; spms_02 4.0 GB 398 s; spms_03 5.0 GB 386 s; download URLs of the form https://researchdata.ntu.edu.sg/api/access/datafile/68133; calib_stereo (49 MB) and calib_stereo_imu bag (0.96 GB, 131.7 s, Kalibr) — [NTU VIRAL site](https://ntu-aris.github.io/ntu_viral_dataset/)
- Licence: CC BY-NC-SA 4.0 for non-commercial academic use; contact authors for commercial use — [NTU VIRAL site](https://ntu-aris.github.io/ntu_viral_dataset/)
- Liveness: on 2026-10-22, https://researchdata.ntu.edu.sg/ and all datafile URLs returned HTTP 503 (whole Dataverse down, not just the files); the site's advertised fallback is a OneDrive/SharePoint folder https://entuedu-my.sharepoint.com/:f:/g/personal/shyuan_staff_main_ntu_edu_sg/EvyxXbi1l5tHonBWIQxueBoByr1-E-w7fgRyHNTsCmwFcg (extracted from the site HTML; not opened) — [NTU VIRAL site](https://ntu-aris.github.io/ntu_viral_dataset/)
- Published ATE (m) in dataset paper Table 4 (VINS-Fusion / LIO-SAM / MLOAM / VIRAL-SLAM): eee_01 0.608/0.075/0.249/0.060; eee_02 0.506/0.069/0.166/0.058; eee_03 0.494/0.101/0.232/0.037; nya_01 0.397/0.076/0.123/0.051; nya_02 0.424/0.090/0.191/0.043; nya_03 0.787/0.137/0.226/0.032; sbs_01 0.508/0.089/0.173/0.048; sbs_02 0.564/0.083/0.147/0.062; sbs_03 0.878/0.140/0.153/0.054 — [NTU VIRAL paper](https://ar5iv.labs.arxiv.org/html/2202.00379)
- Systems using it: VIRAL-SLAM (camera-IMU-UWB-lidar) — [arXiv 2105.03296](https://arxiv.org/pdf/2105.03296); MILIOM — [arXiv 2104.11888](https://arxiv.org/pdf/2104.11888); a 2026 CT-VIR continuous-time visual-inertial-ranging paper uses the same P440 two-radio/three-anchor hardware — [arXiv 2604.14545](https://arxiv.org/pdf/2604.14545); LXD-SLAM (2026) cites it — [arXiv 2606.27811](https://arxiv.org/pdf/2606.27811)

### Inferences
- With one drone, VIRAL can only test the UWB-to-fixed-frame alignment half of task (a) (treat the anchor frame as a "second agent"), not inter-drone ranging. Anchor coordinates must be taken from /nodes_pos_sc (self-surveyed) and treated as approximate.
- The 10 Hz camera rate is low relative to the D435i (typically 15-30 Hz) and the P440 is a different UWB class (ToF radar module) from LinkTrack; noise models will not transfer directly.
- Because the Dataverse was down at check time, plan to use the SharePoint mirror or retry; budget ~120 GB for all 18 sequences.

### Gaps
- Numeric Leica MS60 accuracy is not stated in the paper text (only a datasheet link) — [NTU VIRAL paper](https://ar5iv.labs.arxiv.org/html/2202.00379).
- Rosbag version not stated explicitly; topics are ROS 1 style (`/imu/imu`, `sensor_msgs`), so rosbag1 is implied but unconfirmed.
- Whether the SharePoint mirror is complete and currently accessible was not verified.

## MILUV (McGill University DECAR group, 2025; IJRR 2026)

### Takeaway
The only public multi-UAV dataset with inter-drone UWB ranging, stereo+IMU (RealSense D435i) and mocap ground truth: 3 Uvify IFO-S quadcopters, DW1000 (DWM1000) two-tag-per-drone DS-TWR ranging including tag-to-tag between robots and to 6 Vicon-surveyed anchors, 36 experiments, ~217 min, CSV + JPEG format, CC BY 4.0, open download from figshare (~186 GB incl. calibration), MIT-licensed Python devkit with ROS packages.

### Cited Findings
- Platform: three Uvify IFO-S quadcopters, Pixhawk 4 (PX4), Jetson Nano; sensors: Intel RealSense D435i front stereo camera, downward monochrome camera, two IMUs (D435i and Pixhawk), magnetometer, laser rangefinder, barometer — [MILUV arXiv HTML](https://arxiv.org/html/2504.14376)
- UWB: DW1000 (DWM1000 module) on custom boards; double-sided two-way ranging (not TDOA); non-participating tags passively listen; each robot carries two tags; tag-to-tag ranging between robots included (not between tags on the same robot); six static anchors (IDs 0-5) in three constellations; anchor positions measured by Vicon and provided in devkit config/uwb/anchors.yaml; low-level UWB data (raw timestamps, CIR, received power) included; up to 12 transceivers total — [MILUV arXiv HTML](https://arxiv.org/html/2504.14376); [MILUV arXiv abstract](https://arxiv.org/pdf/2504.14376)
- Scale/format: 36 experiments, ~217 min flight, 173 GB; sensor data as CSV (uwb_range, uwb_cir, imu_px4, mocap, ...), images as JPEG with timestamp filenames — [MILUV arXiv HTML](https://arxiv.org/html/2504.14376)
- Ground truth: 12-camera Vicon; paper gives no rate/accuracy figure; devkit computes "ground-truth" IMU from mocap poses to estimate IMU biases — [MILUV arXiv HTML](https://arxiv.org/html/2504.14376); [ResearchGate listing](https://www.researchgate.net/publication/399634965_MILUV_A_Multi-UAV_Indoor_Localization_dataset_with_UWB_and_Vision)
- Sync/calibration: computer clocks synced by NTP/Chrony; UWB clocks unsynced (handled by DS-TWR); Kalibr camera-IMU calibration, Allan variance IMU noise, UWB antenna-delay/bias calibration via uwb_calibration package — [MILUV arXiv HTML](https://arxiv.org/html/2504.14376)
- Baselines: VINS-Fusion VIO position RMSE ~0.10-0.97 m without loop closure, ~0.02-0.09 m with loop closure, some runs diverged; UWB-inertial EKF mostly 10-20 cm with failures; VIO+UWB EKF mostly 10-20 cm, struggles in high-pace flights — [MILUV arXiv HTML](https://arxiv.org/html/2504.14376)
- Limitations stated by authors: indoor only, small arena limiting to 3 UAVs and 4.418 m/s; rangefinder height biased; CIR at ~5 Hz vs ranging up to 200 Hz; no ground truth for UWB clock states — [MILUV arXiv HTML](https://arxiv.org/html/2504.14376)
- Download: figshare DOI 10.25452/figshare.plus.28386041.v1, CC BY 4.0, published 2025-02-25, open (not embargoed); 39 zips incl. three-drone runs (e.g. default_3_zigzag_0.zip 11.1 GB, default_3_random3_0b.zip 8.4 GB, cir_3_random3_0.zip 8.2 GB, cirObstacles_3_random_0.zip 3.2 GB) and single-drone runs (1.5-4.4 GB each), plus cam_calib.zip 6.1 GB, imu_calib.zip 5.1 GB, uwb_calib.zip 13.1 GB — [figshare API](https://api.figshare.com/v2/articles/28386041)
- Devkit: github.com/decargroup/miluv, MIT licence, v1.0.0 released 2024-07-03, Python ≥3.8 `pip3 install .`, DataLoader with `data_from_timestamps()`, ROS packages (`uwb_ros`, `launch`), Dockerfile, uwb_calibration submodule, 10 open issues (contents not read); docs redirect to http://www.decar.ca/miluv/ (HTTP 200) — [MILUV GitHub](https://github.com/decargroup/miluv)

### Inferences
- MILUV matches the lab's sensor stack almost exactly on the camera/IMU side (D435i) and provides exactly the inter-drone range + anchor range mix needed to validate a VIO+UWB frame-alignment estimator; three-drone "default_3_*" runs are the first thing to download (~3-11 GB each).
- Data is CSV/JPEG, not rosbag/MCAP, so a converter (or the devkit's ROS packages) is needed before feeding ROS-based C-SLAM systems; evo can consume CSV/TUM-format truth directly.
- DW1000 DS-TWR has different bias/NLOS behaviour from LinkTrack, but the raw-timestamp and CIR data allow re-deriving ranges with custom bias models.

### Gaps
- Vicon accuracy/rate, D435i frame rate, and IMU rates are not stated in the paper text extracted; check devkit docs.
- No published collaborative-SLAM or relative-localisation results on MILUV were found other than the authors' own EKF/VINS-Fusion baselines, so there is no external comparison number yet.
- The 10 open GitHub issues were not read; unknown whether they report sync/calibration faults.

## HKUST Aerial Robotics: Omni-swarm and D²SLAM datasets (2021-2023)

### Takeaway
Both repos link Dropbox folders (all returned HTTP 200 on 2026-10-22) with multi-drone rosbags: Omni-swarm offers "raw and preprocessed omni-directional and pinhole" data from 2-drone indoor flights (fisheye stereo 20 Hz, 400 Hz IMU, NoopLoop UWB 100 Hz, mocap GT indoors, none outdoors); D²SLAM offers quad-fisheye "Omni 2-5" sequences (mocap GT), TUM-VI-derived "tum_corr.7z", and no UWB. Documentation of contents, sizes, calibration and GT files on the download pages is essentially absent; these are the only public datasets using Nooploop UWB on drones.

### Cited Findings
- Omni-swarm README dataset link: https://www.dropbox.com/sh/w5yagas06a9r14d/AACdKgMfCCg07M6jr6Ipmus1a?dl=0 ("raw and preprocessed offical omni-directional and pinole dataset"); CNN models https://www.dropbox.com/s/skq1vgfeawiw151/models.zip?dl=0; "Support NoopLoop UWB module only"; `loop-5-drone.launch` exists; licence GPLv3 (repo); no ground-truth mention — [Omni-swarm README](https://raw.githubusercontent.com/HKUST-Aerial-Robotics/Omni-swarm/master/README.md)
- Omni-swarm paper hardware: DJI N3 flight controller, two Pointgrey cameras with 235° fisheye lenses, NoopLoop UWB module, DJI Manifold 2-G (TX2); IMU 400 Hz, camera 20 Hz (datasets) / 16 Hz (collision avoidance), UWB 100 Hz — [Omni-swarm paper (ar5iv 2103.04131)](https://ar5iv.labs.arxiv.org/html/2103.04131)
- Omni-swarm datasets: Table V lists five real-world 2-drone datasets Parallel1/2/3 (indoor), RandFlight (indoor), Outdoor1 (outdoor); indoor GT from "a motion capture system" (unnamed); Outdoor1 has no GT; plug-and-play test 4 drones; collision avoidance 3-4 drones — [Omni-swarm paper](https://ar5iv.labs.arxiv.org/html/2103.04131)
- Omni-swarm accuracy (Table VI, ATE pos m / ATE rot ° / RE pos m / RE rot °): Parallel1 0.127/2.2/0.062/2.3; Parallel2 0.086/3.0/0.063/4.3; Parallel3 0.119/1.8/0.072/1.8; RandFlight 0.088/2.7/0.069/1.3; 3-drone relative position error 0.076-0.083 m per axis; 4-drone 0.056-0.088 m per axis; outdoor ~235 m run drifted 1.9 m vs VIO 6.35 m — [Omni-swarm paper](https://ar5iv.labs.arxiv.org/html/2103.04131)
- D²SLAM README datasets: quad-camera omnidirectional datasets https://www.dropbox.com/scl/fo/jtiwfx98ms7cty946nmug/h?dl=0&rlkey=n03gf3jqmthzy655ku0ycbny0 ; aligned TUM Corr `tum_corr.7z` https://www.dropbox.com/s/ic0yuxr2xym1m0c/tum_corr.7z?dl=0 ; Baidu mirror https://pan.baidu.com/s/1qyRUHUeVCvORXM4CrIZCxg?pwd=D2SL ; "More datastes will be release very soon"; multi-robot config references drone1.bag/drone2.bag/drone3.bag replayed by `sync_bag_player`; quad-camera images concatenated into one 1280x800 frame; bag-player config excludes a `/uwb_node/...` topic; repo LGPL-3; 42 open issues — [D²SLAM GitHub](https://github.com/HKUST-Aerial-Robotics/D2SLAM)
- D²SLAM paper datasets (Table I): TUM ROOM 2-5 (stereo+IMU handheld, GT), TUM Corr 2-5 (built from TUM-VI corridor 1 and 2, GT only at start/end), HKUST RI 3 (3 robots, stereo + depth + IMU, no GT), Omni 2-5 (quad fisheye + IMU, flight, GT), OmniLongNoYaw 5 / OmniLongYaw 5 (5 robots, long flights); real-world UAV2 NoYaw / UAV2 Yaw with RealSense D435i stereo; GT "partly used a motion capture system"; drones: quad fisheye, PX4 IMU, Xavier NX, optional D435i; D²SLAM does not use UWB — [D²SLAM paper (arXiv 2211.01538v4)](https://arxiv.org/html/2211.01538v4)
- D²SLAM reported errors: TUM ROOM 3 D²VINS ATE_pos 0.128 m, RE_pos 0.119 m, RE_rot 2.95°; Omni 5 D²VINS ATE_pos 0.075 m, RE_pos 0.076 m, RE_rot 0.37°; D²SLAM vs DOOR-SLAM ATE_pos: OmniLongYaw 5 0.168 vs 0.149 m, TUM ROOM 5 0.032 vs 0.064 m, TUM Corr 5 0.275 vs 0.068 m; real-world D²PGO ATE ~0.090 m (NoYaw), 0.147 m (Yaw); baselines VINS-Mono, D²VINS single, DOOR-SLAM — [D²SLAM paper](https://arxiv.org/html/2211.01538v4)
- D²SLAM issues touching datasets: #46 "Process has died when i implement using my dataset" (open), #31 std::out_of_range in TUM dataset (open), #17 "How to evaluate multi-TUM dataset on single PC?" (open), #49 TUM launch failing (closed 2024-11-07), #27 "Kitti, Masala, EuRoC" (closed 2024-04-27), #6 mainland-China download link (closed 2023-06-11); none about ground truth, UWB or time sync — [D²SLAM issues](https://github.com/HKUST-Aerial-Robotics/D2SLAM/issues?q=dataset+OR+ground+truth+OR+calibration+OR+uwb)
- Liveness: all three Dropbox URLs returned HTTP 200 (Omni-swarm folder redirects to a new `scl/fo/...` share) on 2026-10-22 — curl check in this research session.
- Docker images hkustswarm/d2slam exist (x86, Jetson/OmniNxt) — [Docker Hub](https://hub.docker.com/r/hkustswarm/d2slam/tags)

### Inferences
- These are the only public drone bags containing Nooploop UWB messages, which makes the Omni-swarm Dropbox folder uniquely relevant for testing LinkTrack-style message handling; however the exact module (LinkTrack P/S/PB) is never named and the folder contents/sizes are undocumented, so budget time to inspect bags with `rosbag info`.
- D²SLAM's Omni sequences are quad-fisheye, not stereo pinhole; running a D435i-tuned VIO on them requires a fisheye-capable front end (the README's "pinhole" variant of the Omni-swarm set may be the stereo-rectified alternative, but this is unverified).
- Omni-swarm Table VI numbers (RE pos 0.06-0.07 m with 2 drones, mocap) are the directly comparable published figures for a UWB+VIO relative estimator on these bags.

### Gaps
- No manifest, file sizes, calibration YAMLs or GT file format for either Dropbox folder could be read (Dropbox folder listing is JavaScript-rendered); the Omni-swarm Dropbox share is the only evidence of what is released.
- Omni-swarm paper excerpt does not explicitly state public release of the mocap GT; the README does not mention GT at all.
- Whether the "HKUST RI 3" sequence (no GT) is in the public folder is unknown.

## EuRoC MAV (ETH Zurich ASL, 2016) and its reuse as pseudo-multi-agent

### Takeaway
Single AscTec-class MAV, stereo WVGA 20 Hz + 200 Hz IMU, Vicon 6-DoF (V1/V2 rooms) and Leica MS50 3-D position (Machine Hall); files moved in 2024 to the ETH Research Collection as four ZIPs (~27.8 GB), licence "In Copyright - Non-Commercial Use Permitted". No UWB. COVINS and COVINS-G establish the convention of running MH_01-05 and V1_01-03 as 3-5 simultaneous agents in a shared frame, which makes EuRoC the de-facto no-UWB C-SLAM benchmark.

### Cited Findings
- Sensors: stereo WVGA monochrome 2x20 FPS; MEMS IMU 200 Hz; ground truth from Vicon (6D pose), Leica MS50 laser tracker (3D position), Leica MS50 3D structure scan; calibration (intrinsics, cam-IMU extrinsics, aligned GT); known issues: per-camera auto-exposure causes brightness differences between the pair, very dynamic motion degrades laser-tracker accuracy, limited sensor-to-GT synchronisation and Vicon lacks device timestamps; "All dataset files are now hosted on the ETH Research Collection" DOI 10.3929/ethz-b-000690084; parser at github.com/ethz-asl/dataset_tools — [EuRoC page (HTTP 200)](https://projects.asl.ethz.ch/datasets/euroc-mav/)
- Research Collection record: "The EuRoC micro aerial vehicle datasets", open access, licence "In Copyright - Non-Commercial Use Permitted" (InC-NC/1.0), published 2024-09-27; files: Machine Hall Datasets ZIP 12,096 MB, Vicon Room 1 ZIP 5,762 MB, Vicon Room 2 ZIP 5,735 MB, Calibration ZIP 4,211 MB, euroc_mav_dataset.pdf — [ETH Research Collection](https://www.research-collection.ethz.ch/handle/20.500.11850/690084)
- Multi-agent reuse: COVINS-G "uses the Machine Hall (MH) and the Vicon Room 1 (V1) sequences to establish a collaborative estimation scenario with three to five participating agents", processing multi-session baselines sequentially and collaborative methods in parallel — [COVINS-G arXiv 2301.07147](https://arxiv.org/pdf/2301.07147); COVINS reports per-sequence network traffic over all EuRoC sequences — [COVINS arXiv 2108.05756](https://arxiv.org/pdf/2108.05756); COVINS repo scripts run a 3-agent session and a 5-agent MH1-MH5 variant — [COVINS GitHub mirror](https://github.com/kajo-kurisu/covins)
- D²SLAM users asked about EuRoC/KITTI support (issue #27, closed) — [D²SLAM issues](https://github.com/HKUST-Aerial-Robotics/D2SLAM/issues?q=dataset+OR+ground+truth+OR+calibration+OR+uwb)
- S3E paper positions itself as having 4x the average recording time of EuRoC — [S3E arXiv 2210.13723](https://arxiv.org/html/2210.13723v5)

### Inferences
- Because all MH sequences share the Leica frame and all V1 (resp. V2) sequences share one Vicon frame, inter-"agent" relative pose truth is available for free, so evo relative-error scoring between pseudo-agents is valid; but there is no inter-agent UWB, so task (a) cannot be tested on EuRoC without simulating ranges from GT.
- Per-sequence rosbag/ASL zips formerly on projects.asl.ethz.ch are no longer linked; expect to download the four large ZIPs (per-sequence files are inside).

### Gaps
- The individual sequence list with lengths/durations/difficulty is now only inside the archive PDF; not extracted here.
- Whether Swarm-SLAM used EuRoC could not be confirmed (its paper lists KITTI, KITTI-360, GrAco, M2DGR, S3E) — [Swarm-SLAM arXiv 2301.06230](https://arxiv.org/pdf/2301.06230).

## S3E (Sun Yat-sen University and collaborators, RA-L 2024)

### Takeaway
Three UGVs (Alpha, Blob, Carol) with 16-beam LiDAR, two colour cameras, 9-axis IMU, UWB inter-robot relative ranges and dual-antenna RTK; 13 outdoor + 5 indoor sequences, ROS 2 bags with all three robots merged per sequence; Hugging Face (cc-by-4.0, 278 GB) is the only download. Ground robots, not drones; indoor lab GT is Vicon at start/end only.

### Cited Findings
- Robots/sensors: three UGVs; S3Ev1.0 indoor and S3Ev2.0 outdoor platforms; per robot 16-beam 3D LiDAR, two high-resolution colour cameras, 9-axis IMU, UWB receiver (model unnamed), dual-antenna RTK; "UWB relative observations" / "relative distance measurements" (inter-robot; no fixed anchors mentioned) — [S3E project page](https://pengyu-team.github.io/S3E/)
- Sequences: 13 outdoor + 5 indoor across Concentric Circles, Intersecting Circles, Intersection Curve, Rays; scenes Dormitory, Teaching Building, Square/Playground, Laboratory, Campus Road, Tunnel; no per-sequence durations/sizes on the page; ROS 2 bags, GT provided separately, three robots merged in one bag, rosbag_extractor toolkit — [S3E project page](https://pengyu-team.github.io/S3E/)
- Author-listed issues: scalability (3 robots), single UGV type, environmental coverage, "small discrepancies may occur in highly dynamic scenes" in sync/calibration — [S3E project page](https://pengyu-team.github.io/S3E/)
- Hugging Face: licence cc-by-4.0, 278 GB, 806,343 rows in viewer; README says for lab sequences "we capture only the start and end points due to constraints in Vicon system availability" — [HF PengYu-Team/S3E (HTTP 200)](https://huggingface.co/datasets/PengYu-Team/S3E)
- IEEE DataPort entry exists (DOI 10.21227/rrcw-fv27) but files were not uploaded there — [IEEE DataPort](https://ieee-dataport.org/documents/s3e-multi-robot-multimodal-dataset-collaborative-slam)
- Paper: "existing collaborative SLAM methods perform poor inter-loop closures in at least one sequence"; "The addition of UWB measurements has significantly enhanced localization accuracy and reliability"; sequence counts differ between arXiv versions (7+5 early, 13+5 later) — [S3E arXiv 2210.13723](https://arxiv.org/html/2210.13723v5)
- Used by Swarm-SLAM (Lajoie & Beltrame) among its dataset experiments — [Swarm-SLAM arXiv 2301.06230](https://arxiv.org/pdf/2301.06230)

### Inferences
- S3E is the most relevant ground-robot set for task (b) with UWB, and its ROS 2 format fits a modern stack; outdoor sequences with RTK give full-trajectory inter-robot truth, indoor ones only endpoint truth, so relative-error scoring should use outdoor sequences.
- Camera is a colour pair at unstated rate (not a D435i-class IR stereo) and robots move at ground-vehicle dynamics; VIO behaviour will differ from drones.

### Gaps
- UWB module model, ranging rate, sensor rates, RTK accuracy and per-sequence sizes are only in images/paper tables not read here; the HF file listing (db3 vs mcap) was not visible.

## UTIAS Multi-Robot Cooperative Localization and Mapping (MR.CLAM) (University of Toronto, IJRR 2011)

### Takeaway
Five iRobot Create robots in a 15 m x 8 m room, odometry (~67 Hz) and camera barcode range-bearing to landmarks and other robots, 10-camera Vicon GT at 100 Hz with ~1 mm accuracy; nine plain-text datasets of 900-4400 s (4-17 MB compressed each, dataset 7 also has 22 GB of images); FTP download. No UWB, no IMU, 2-D only — useful only as a toy cooperative-localisation benchmark.

### Cited Findings
- 5 identical iRobot Create robots with laptops running Player; odometry ~67 Hz; 960x720 monocular camera detecting barcodes for range-bearing; 15 cylindrical landmarks; 15 m x 8 m indoor space — [MR.CLAM page (HTTP 200)](https://asrl.utias.utoronto.ca/datasets/mrclam/)
- GT: 10-camera Vicon, 100 Hz, accuracy "on the order of 1x10-3 m"; NTP clock sync ~1 ms — [MR.CLAM page](https://asrl.utias.utoronto.ca/datasets/mrclam/)
- Datasets 1-9: 1500 s/6 MB, 1900 s/7 MB, 1800 s/8 MB, 1400 s/7 MB, 2300 s/10 MB, 900 s/4 MB, 900 s/4 MB (+22 GB JPEG images), 4400 s/17 MB, 2100 s/11 MB (dataset 9 has occluding barriers); 17 text files per dataset; FTP ftp://asrl3.utias.utoronto.ca/MRCLAM/ ; MATLAB tools; browsers may need wget for FTP; no licence stated, citation requested (Leung, Halpern, Barfoot, Liu, IJRR 30(8) 2011, DOI 10.1177/0278364911398404) — [MR.CLAM page](https://asrl.utias.utoronto.ca/datasets/mrclam/)

### Inferences
- Not relevant to UWB/VIO validation; only useful for sanity-checking a multi-agent relative-pose graph back-end with ideal range-bearing inputs.

### Gaps
- FTP liveness not tested (curl only tested the HTTPS page).

## MCD (NTU/KTH/TUHH, CVPR 2024) and GRACO/GrAco (SYSU, RA-L 2023)

### Takeaway
MCD is single-platform (ATV and handheld), with Ouster OS1-128/64, Livox Mid-70, D435i/D455, VN100/VN200 and a UWB bag per sequence (`ltpb`), continuous-time GT from survey-grade prior maps, 18 bz2 rosbags of 3.5-51 GB on Google Drive, CC BY-NC-SA 4.0 — no multi-agent data. GrAco is a ground+aerial dataset (LiDAR, stereo, IMU, GPS, RTK GT, ROS1 and ROS2 bags, 20-37 GB per sequence on OneDrive/Google Drive) with no UWB and a 2.2 GB "Sample-Multi" bag as the only simultaneous multi-robot sample. Hilti SLAM Challenge sets contain no UWB.

### Cited Findings
- MCD sensors: 3D spinning lidar, non-repetitive lidar, stereo cameras, IMUs, "UWB ranging sensors"; continuous-time GT with B-spline wrapper github.com/mcdviral/ceva; licence CC BY-NC-SA 4.0 — [MCD landing page](https://mcdviral.github.io/); 18 sequences, >200k lidar scans, 1500k frames, GT by registering lidar-inertial data onto survey-grade prior maps — [MCD arXiv 2403.11496](https://arxiv.org/pdf/2403.11496)
- MCD download page: bags are bz2-compressed rosbags split per sensor (d435i, d455b, d455t, mid70, os1_128/os1_64, ltpb (UWB), vn100, vn200), GT in a separate folder, calibration YAMLs for ATV (ntu_) and handheld (kth_, tuhh_); hosting Google Drive; e.g. ntu_day_01 10m02s 41.5 GB, kth_day_06 14m51s 43.0 GB, tuhh_day_03 13m59s 51.3 GB, tuhh_night_09 3m05s 3.5 GB — [MCD Download (HTTP 200)](https://mcdviral.github.io/Download.html)
- GrAco: Sun Yat-sen University RAPID Lab, RA-L 8(2) 2023; sensors LiDAR, stereo cameras, IMU, GPS; self-made trigger module with ms-level sync; cm-level RTK GNSS GT; UWB not mentioned — [GrAco site](https://sites.google.com/view/graco-dataset); download page: 6 ground sequences (21.3-37.3 GB) + 8 aerial sequences (19.9-29.3 GB, suffix = altitude 20-40 m) as ROS1 and ROS2 bags with GT, Sample-Multi 2.2 GB ROS1 bag, OneDrive/Google Drive links, GT in local ENU frame at RTK base, calibration folders on Google Drive, no licence stated — [GrAco Download (HTTP 200)](https://sites.google.com/view/graco-dataset/download)
- GrAco used by Swarm-SLAM — [Swarm-SLAM arXiv 2301.06230](https://arxiv.org/pdf/2301.06230); CoPeD taxonomy lists GrAco as "Aerial/Ground Robot Camera, LiDAR, IMU, GPS Outdoor" — [CoPeD arXiv 2405.14731](https://arxiv.org/html/2405.14731v1)
- Hilti 2021: 5 cameras (1 stereo pair), 2 lidars, 3 IMUs, mm-accurate mocap or total-station GT; no UWB in sensor description — [Hilti arXiv 2109.11316](https://arxiv.org/abs/2109.11316v3); Hilti 2023 focuses on platform-agnostic multi-session SLAM, no UWB mentioned — [arXiv 2404.09765](https://arxiv.org/abs/2404.09765v1)

### Inferences
- MCD's `ltpb` bag label is plausibly "LinkTrack P-B" (Nooploop), which would make MCD the only dataset with LinkTrack messages recorded alongside a D435i — but this is an inference from a topic label; the vendor is not named on the page and must be confirmed from the MCD user manual before relying on it.
- Neither MCD nor GrAco supports inter-agent evaluation (single platform; GrAco ground and aerial runs are separate sequences apart from one small sample).

### Gaps
- MCD UWB vendor/model, anchor positions, and rosbag version not stated on the download page.
- GrAco sequence durations/lengths are only in an image; sensor models not named; licence absent.

## Other UWB / multi-robot datasets found (TIERS Turku, UTIL, Kimera-Multi, CoPeD, INSANE)

### Takeaway
TIERS (Univ. Turku) publishes two UWB-mocap datasets: an 8-TurtleBot4 DWM1001 all-to-all relative-localisation benchmark (with one 5-robot case including a VIO camera; rosbags on SharePoint, MIT repo) and a 2020 single-UAV UWB-anchor flight set; UTIL (UTIAS, IJRR 2024) is single-quadrotor DWM1000 TDOA with mm GT, text format; Kimera-Multi (MIT, 6-8 Jackals, D455 + LiDAR, GPS/total-station-aided LiDAR SLAM GT) is request-only via Google Form; CoPeD (NYU, 3 UGV + 2 UAV, D435i) has no UWB. None combine drones + inter-drone UWB + stereo except MILUV.

### Cited Findings
- TIERS benchmark: Qorvo DWM1001 with custom ToF firmware on TurtleBot4s, a Husky-based platform, or a UAV; eight-camera OptiTrack in an 8 m x 9 m arena (Case I 8 m x 16 m); TurtleBot data logged at 15 Hz via ROS 2; five cases incl. eight UWB TurtleBot4s all-to-all and five TurtleBots with a VIO camera; authors say all data and recording code are public on GitHub — [arXiv 2305.08532](https://arxiv.org/pdf/2305.08532); repo github.com/TIERS/uwb-relative-localization-dataset exists (MIT licence, 10 commits, 5 stars), cases 1-5, Case 5 rosbags on an external SharePoint folder, no README description of robots/format — [TIERS repo](https://github.com/TIERS/uwb-relative-localization-dataset); companion anomaly-detection paper used eight TurtleBot4 Lite with DWM1001 and OptiTrack — [arXiv 2303.17207](https://arxiv.org/pdf/2303.17207)
- TIERS drone dataset (IROS 2020): single F450 quadrotor, Pixhawk 2.4/PX4, Up Board, TF Mini lidar height, Decawave DWM1001 tags/anchors in multiple configurations, mocap GT (system unnamed), rosbags; github.com/TIERS/UWB_DRONE_DATASET redirects to github.com/TIERS/uwb-drone-dataset (HTTP 200) — [TIERS uwb-drone-dataset](https://github.com/TIERS/uwb-drone-dataset); [arXiv 2003.04380](https://arxiv.org/pdf/2003.04380)
- UTIL: UTIAS DSL (Zhao, Goudar, Qiao, Schoellig), IJRR 2024; Decawave DWM1000 TDOA; ~150 min of flights at ~0.45 m/s avg in obstacle-free and cluttered rooms with four anchor constellations; raw UWB TDOA, IMU, optical flow, ToF altitude, mm-accurate GT; plain text + MATLAB/Python scripts; site https://utiasdsl.github.io/util-uwb-dataset/ (HTTP 200) — [UTIL arXiv 2203.14471](https://arxiv.org/pdf/2203.14471); [UTIL IJRR](https://journals.sagepub.com/doi/full/10.1177/02783649241230640)
- Kimera-Multi: Campus-Outdoor 6 Jackals 6044 m 19 min; Campus-Tunnels 8 robots 6753 m 28 min; Campus-Hybrid 8 robots 7785 m 27 min; D455 (RGB, depth, infra1/infra2 stereo, IMU), VLP-16 or OS1-64 LiDAR (mixed per robot in 12_07/12_08), wheel odometry; compressed rosbags; GT "GPS and total-station assisted LiDAR SLAM based on LOCUS and LAMP"; downloads via request form https://forms.gle/L35NSrQcfbjqq2w56 ; extrinsics "not perfect"; repo MIT — [Kimera-Multi-Data GitHub](https://github.com/MIT-SPARK/Kimera-Multi-Data); dataset paper — [arXiv 2304.04362](https://arxiv.org/pdf/2304.04362)
- CoPeD (NYU, RA-L 2024): three ground robots + two aerial robots; Jackal with Ouster OS1-64, Microstrain 3DM-GX5-25, u-blox GNSS, D435i/D455; aerial robots with forward D435i, downward IMX219, PX4, GPS; AprilTag-based UAV-UGV relative pose; NTP sync; no UWB in results — [CoPeD arXiv 2405.14731](https://arxiv.org/pdf/2405.14731)
- INSANE (2024, IJRR): single-UAV multi-sensor set including UWB for Mars-analog/outdoor/transition flights — [INSANE IJRR](https://journals.sagepub.com/doi/10.1177/02783649241227245)
- A 2024 single-tag UWB dataset with mocap 6-DoF of tag and anchors plus stereo and inertial data studies relative-pose effects on UWB — [arXiv 2407.03890](https://arxiv.org/html/2407.03890v1)
- Multi-LiDAR multi-UAV tracking dataset (2023) has mocap indoor / GNSS outdoor GT but no UWB focus — [arXiv 2310.09165](https://arxiv.org/pdf/2310.09165)

### Inferences
- TIERS Case 5 (five TurtleBots with VIO camera + DWM1001 all-to-all + OptiTrack) is the closest ground-robot analogue to task (a); but the repo README is sparse and the rosbags live on a university SharePoint, so availability should be re-verified before committing.
- Kimera-Multi is the strongest C-SLAM benchmark (6-8 agents, D455 stereo+IMU) but request-only access and GT derived from LiDAR SLAM (not mocap) make it slower to obtain and less precise for cm-level relative error.

### Gaps
- TIERS Case 5 SharePoint link was not opened; format/size unknown. UTIL quadrotor model not confirmed (described as "customized quadrotor platform"). Kimera-Multi sizes and GT accuracy not stated on the repo page. INSANE access/format not checked.

## Cross-cutting: time sync, calibration and licence issues to plan around

### Takeaway
Known problems reported by maintainers: NTU VIRAL Ouster/IMU jitter (restamp script) and 0.4 m prism offset; EuRoC auto-exposure mismatch and weak sensor-to-GT sync; Kimera-Multi imperfect extrinsics; MILUV biased rangefinder and unsynced UWB clocks; S3E endpoint-only indoor GT. Licences range from CC BY 4.0 (MILUV, S3E) to NC-only (NTU VIRAL, MCD, EuRoC) to unstated (GrAco, UTIAS).

### Cited Findings
- NTU VIRAL: Ouster cloud/IMU jitter from sync problems, restamp.py provided; 0.4 m IMU-prism offset — [NTU VIRAL site](https://ntu-aris.github.io/ntu_viral_dataset/); 20 ms cam-IMU offset found by Kalibr but not applied; GT alignment within 0.1 s — [NTU VIRAL paper](https://ar5iv.labs.arxiv.org/html/2202.00379)
- EuRoC: brightness differences between stereo pair from per-camera auto-exposure; limited sensor-to-GT sync; Vicon lacks device timestamps — [EuRoC page](https://projects.asl.ethz.ch/datasets/euroc-mav/)
- Kimera-Multi: "these extrinsics are not perfect"; mixed LiDAR hardware across robots — [Kimera-Multi-Data](https://github.com/MIT-SPARK/Kimera-Multi-Data)
- MILUV: rangefinder bias, no GT for UWB clock states, CIR only ~5 Hz — [MILUV arXiv HTML](https://arxiv.org/html/2504.14376)
- S3E: indoor Vicon only at start/end — [HF S3E](https://huggingface.co/datasets/PengYu-Team/S3E)
- Licences: MILUV CC BY 4.0 — [figshare API](https://api.figshare.com/v2/articles/28386041); S3E cc-by-4.0 — [HF S3E](https://huggingface.co/datasets/PengYu-Team/S3E); NTU VIRAL CC BY-NC-SA 4.0 — [NTU VIRAL site](https://ntu-aris.github.io/ntu_viral_dataset/); MCD CC BY-NC-SA 4.0 — [MCD](https://mcdviral.github.io/); EuRoC InC-NC — [ETH Research Collection](https://www.research-collection.ethz.ch/handle/20.500.11850/690084); Omni-swarm repo GPLv3 / D²SLAM repo LGPL-3 with no dataset licence stated — [Omni-swarm README](https://raw.githubusercontent.com/HKUST-Aerial-Robotics/Omni-swarm/master/README.md), [D²SLAM GitHub](https://github.com/HKUST-Aerial-Robotics/D2SLAM)

### Inferences
- Recommended download order for this week: (1) MILUV three-drone runs + uwb_calib/cam_calib zips (~40-60 GB), (2) Omni-swarm Dropbox folder (inspect contents first), (3) EuRoC MH + V1 ZIPs (~18 GB) for C-SLAM baselines, (4) NTU VIRAL via SharePoint mirror once a few sequences are needed, (5) S3E outdoor sequences if ground-robot C-SLAM comparisons are wanted.

### Gaps
- GitHub issues for MILUV (10 open), Omni-swarm, S3E and MCD were not read individually; no sync-problem reports could be confirmed or ruled out for them.
