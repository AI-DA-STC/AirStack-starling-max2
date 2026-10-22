# HKUST Omni-swarm (T-RO 2022) and D²SLAM (T-RO 2024): facts for reuse on a Starling 2 Max swarm

Research date: 2026-10-22. Target platform assumed: ModalAI Starling 2 Max, Jetson Orin NX 16 GB, Intel RealSense D435i, Nooploop LinkTrack UWB, ROS 2 Jazzy, WiFi between drones. Lab plan: own VIO per drone + continuous 4-DoF frame alignment from shared positions + UWB ranges.

Primary sources used throughout:
- Omni-swarm paper: [arXiv 2103.04131 (v5, Sep 2022; T-RO DOI 10.1109/TRO.2022.3182503)](https://arxiv.org/abs/2103.04131); full text read via [ar5iv HTML](https://ar5iv.labs.arxiv.org/html/2103.04131)
- Omni-swarm code: [github.com/HKUST-Aerial-Robotics/Omni-swarm](https://github.com/HKUST-Aerial-Robotics/Omni-swarm)
- D²SLAM paper: [arXiv 2211.01538 (v4, Jun 2024; T-RO vol. 40 pp. 3445-3464, DOI 10.1109/TRO.2024.3422003)](https://arxiv.org/abs/2211.01538); full text read via [arXiv HTML v4](https://arxiv.org/html/2211.01538v4)
- D²SLAM code: [github.com/HKUST-Aerial-Robotics/D2SLAM](https://github.com/HKUST-Aerial-Robotics/D2SLAM)
- Repo statistics were pulled from the GitHub REST API on 2026-10-22 (star/fork/issue counts, commit dates, branch list); Docker tags from the Docker Hub v2 API; dataset links verified with HTTP HEAD/GET.

Note on authorship/lineage: both systems share first author Hao Xu (HKUST, Shaojie Shen's group); D²SLAM lists Omni-swarm as its own predecessor and cites it ([D²SLAM Sec. I/II](https://arxiv.org/html/2211.01538v4)). D²SLAM uses NO UWB; Omni-swarm does.

## Q1. Was it flown on real drones? Robots, hardware, flight length, environment

### Takeaway
Both were flown for real. Omni-swarm: 2-4 custom drones (DJI N3 + TX2 + dual 235° fisheye + Nooploop UWB), indoor mocap datasets 45-131 m per run plus one 235 m outdoor run without ground truth. D²SLAM: 3.5-inch FPV drones with Xavier NX; the real-flight table used RealSense D435i stereo (not the quad-fisheye rig), two flights of 51 m and 73 m; number of UAVs in the real flights is not stated explicitly (labels say "UAV2").

### Cited Findings
Omni-swarm
- Per-drone hardware (Sec. VI-A, Fig. 8): DJI N3 flight controller; two PointGrey cameras with fisheye lenses (Sec. IV-A: "two 235-degree FoV fisheye cameras", mounted facing up and down); "NoopLoop UWB module"; DJI Manifold 2-G with Nvidia TX2; WiFi module — [ar5iv 2103.04131](https://ar5iv.labs.arxiv.org/html/2103.04131)
- Drones per experiment: indoor/outdoor datasets of Table V use 2 drones; plug-and-play test (Sec. VII-B1) 4 drones; non-line-of-sight test (Sec. VII-B2) 2 drones; collision-avoidance (Sec. VII-E) 3 and 4 drones; simulations 2-20 drones (Sec. VII-A) — [ar5iv 2103.04131](https://ar5iv.labs.arxiv.org/html/2103.04131)
- Average trajectory lengths (Table V): Parallel1 93.0 m, Parallel2 106.4 m, Parallel3 130.7 m, RandFlight 45.5 m, Outdoor1 237.2 m; collision-avoidance runs (Table IX) 27.8 m (3 drones) and 19.9 m (4 drones) — [ar5iv 2103.04131](https://ar5iv.labs.arxiv.org/html/2103.04131)
- Ground truth: motion-capture system in the indoor lab (vendor not named); the outdoor dataset has no ground truth; Table VII outdoor numbers come from simulated variants (Parallel1Out, RandFlightOut) — [ar5iv 2103.04131](https://ar5iv.labs.arxiv.org/html/2103.04131)
- Fig. 1 shows "Indoor aerial swarm formation flight with four drones" — [ar5iv 2103.04131](https://ar5iv.labs.arxiv.org/html/2103.04131)
- Maintainer confirmed UWB brand in an issue: "Hi it's infinity uwb." (the driver repo is named inf_uwb_ros) — [Omni-swarm issue #7](https://github.com/HKUST-Aerial-Robotics/Omni-swarm/issues/7)

D²SLAM
- Platform (Sec. VIII, Fig. 10): modified 3.5-inch cinewhoop FPV UAV; quad-fisheye rig giving 360° horizontal visibility (camera model not given); optional Intel RealSense D435i; custom flight controller with four integrated ESCs running customised PX4; NVIDIA Xavier NX; take-off weight about 623 g; 22.8 V 1550 mAh battery, about 10 min endurance (Fig. 10 caption says "6s 18650", inconsistent with text) — [arXiv HTML 2211.01538v4](https://arxiv.org/html/2211.01538v4)
- Quad-fisheye geometry (Sec. V-A, Fig. 7): about 200° lateral FoV per camera with about 110° overlap between neighbours — [arXiv HTML 2211.01538v4](https://arxiv.org/html/2211.01538v4)
- Real-world flights (Sec. IX-G, Table IX): two flights, "UAV2 NoYaw" (51.0 m average trajectory) and "UAV2 Yaw" (73.3 m), with UAVs "equipped with Realsense d435i cameras" running the stereo version; number of UAVs, indoor/outdoor and ground-truth source are not stated in the section — [arXiv HTML 2211.01538v4](https://arxiv.org/html/2211.01538v4)
- Datasets "partly used a motion capture system to capture ground truth data" (Sec. IX-A) — [arXiv HTML 2211.01538v4](https://arxiv.org/html/2211.01538v4)
- Maintainer (Peize Liu, 2023-07-07): "we are now running a new project on D2SLAM with newly designed hardware and software platform" — [D2SLAM issue #10](https://github.com/HKUST-Aerial-Robotics/D2SLAM/issues/10); that platform is OmniNxt (IROS 2024): Jetson Orin NX 16 GB, four 210° fisheye cameras at 20 Hz, 500 Hz IMU — [arXiv 2403.20085](https://arxiv.org/abs/2403.20085), [OmniNxt GitHub](https://github.com/HKUST-Aerial-Robotics/OmniNxt)

### Inferences
- The D²SLAM real-flight ATE values require ground truth, so the flights were almost certainly in the group's indoor mocap room; "UAV2" most plausibly means a two-UAV flight. Both points are inferred, not stated.
- Omni-swarm's real flights were all short (under 2.5 min of trajectory at typical indoor speeds) and in one lab plus one outdoor campus run; there is no multi-hour or multi-building evidence.

### Gaps
- Omni-swarm: exact PointGrey camera model, fisheye lens model, Nooploop module model, mocap vendor, and clock-time flight durations are not given in the paper.
- D²SLAM: UAV count, venue and ground truth of the real flights are not stated; the quad-fisheye camera model is only referenced to an issue comment ([D2SLAM issue #2](https://github.com/HKUST-Aerial-Robotics/D2SLAM/issues/2), content not read).

## Q2. What is shared between agents and what bandwidth was reported

### Takeaway
Omni-swarm broadcasts odometry + UWB ranges (49 B at 100 Hz), full keyframes (SuperPoint landmarks PCA-compressed to 64-D + NetVLAD global descriptor, 180 kB at 0.3 Hz) and PCM inlier sets, totalling 59.4 kB/s per drone over 802.11 ad-hoc WiFi with LCM. D²SLAM broadcasts complete keyframes (20.1 kB stereo / 56.3 kB omni) in near mode, compact NetVLAD-only keyframes (1.2 / 4.8 kB) in far mode, plus D²VINS and D²PGO dual-state updates; keyframes at 5 Hz, PGO updates at 1 Hz; measured mean comm delay 23.89 ms in real flight.

### Cited Findings
Omni-swarm
- Shared content (Sec. IV-C): keyframes carrying a global descriptor, landmarks, odometry and extrinsics; only landmarks with successfully triangulated 3D positions are sent "to reduce the amount of communication" — [ar5iv 2103.04131](https://ar5iv.labs.arxiv.org/html/2103.04131)
- Per-drone broadcast budget (Table III): odometry + UWB distances 49 bytes at 100 Hz = 4.90 kB/s; keyframes 180 kB at 0.3 Hz = 54.0 kB/s; PCM inliers 552 bytes at 1 Hz = 0.47 kB/s; total 59.4 kB/s — [ar5iv 2103.04131](https://ar5iv.labs.arxiv.org/html/2103.04131)
- Descriptor compression: SuperPoint 256-D -> 64-D by PCA, saving 534.5 kB per keyframe (about 3x); keyframes average 696 landmarks — [ar5iv 2103.04131](https://ar5iv.labs.arxiv.org/html/2103.04131)
- Network: 5.2 GHz IEEE 802.11 IBSS ad-hoc WiFi, measured 4.9 MB/s at 22.4 m; messages via LCM; packet loss 3.5 % (2 drones), 4.7 % (3), 3.9 % (4) (Table IV); bandwidth-limited ideal swarm size 83 — [ar5iv 2103.04131](https://ar5iv.labs.arxiv.org/html/2103.04131)
- Fig. 2 caption states "All the communications between the devices are through UWB broadcast" — [ar5iv 2103.04131](https://ar5iv.labs.arxiv.org/html/2103.04131); the UWB driver limits broadcast payload to "no more than 250 byte data one time" — [inf_uwb_ros README](https://github.com/HKUST-Swarm/inf_uwb_ros)
- Conclusion (Sec. VIII): communication range limited to 22.4 m; mesh routing (Batman-adv) listed as future work — [ar5iv 2103.04131](https://ar5iv.labs.arxiv.org/html/2103.04131)

D²SLAM
- Shared content: complete keyframes (SuperPoint features + global descriptor) in discover/near modes; compact keyframes (NetVLAD descriptor only) in far mode; D²VINS and D²PGO state/dual updates (Sec. IV-B, V-A, VI-D1, VII-A). Map merging occurs "without exchanging landmarks" (Sec. IV-C) but distributed loop closure returns landmark info from a complete keyframe (Fig. 8, Sec. V-E) — [arXiv HTML 2211.01538v4](https://arxiv.org/html/2211.01538v4)
- Message sizes (Sec. IX-F, Tables VII/VIII): complete keyframe 20.1 kB (stereo) / 56.3 kB (omni); compact keyframe 1.2 kB / 4.8 kB; D²VINS update 0.188 + 0.036·p kB (about 3.5 kB per step for 5 UAVs, p = 51 poses); D²PGO update 0.056 + 0.064·e kB (about 81 kB for TUM Corr 5, e = 1262); keyframes and D²VINS updates at 5 Hz, D²PGO at 1 Hz — [arXiv HTML 2211.01538v4](https://arxiv.org/html/2211.01538v4)
- Total traffic on OmniLongYaw 5 (baseline -> D²SLAM, MB): front-end 1546.7 -> 984.2; D²VINS 75.9 -> 70.8; D²PGO 2340.9 -> 2179.4 — [arXiv HTML 2211.01538v4](https://arxiv.org/html/2211.01538v4)
- Real flight average communication delay 23.89 ms; D²PGO tests used an emulated 50 ms delay; near mode triggers at predicted 3-5 m separation and "needs a robust, low-latency network"; loss of comms falls back to single-robot SLAM (Sec. IV-B, IV-D1, IX-G) — [arXiv HTML 2211.01538v4](https://arxiv.org/html/2211.01538v4)
- Transport in code: d2comm package (d2comm.cpp, d2comm_node.cpp) and LCM listed in the Docker dependency set — [D2SLAM repo tree](https://github.com/HKUST-Aerial-Robotics/D2SLAM), [docker/README.md](https://github.com/HKUST-Aerial-Robotics/D2SLAM/blob/main/docker/README.md)
- A user running two Jetson NX + D435i over a WiFi router reported stuttering and that PGO trajectories of the other drone were only partly visible; maintainer attributed it to network configuration (multicast IP had to be changed) — [D2SLAM issue #39](https://github.com/HKUST-Aerial-Robotics/D2SLAM/issues/39)

### Inferences
- In Omni-swarm the 49-byte odometry+range packet fits the 250-byte UWB payload, so the low-rate state/range channel plausibly rides on the Nooploop broadcast while 180 kB keyframes must go over WiFi; the paper's Fig. 2 caption and Table III are otherwise in tension.
- D²SLAM stereo near-mode keyframe traffic is roughly 5 Hz x 20.1 kB = about 100 kB/s per drone (derived, not stated), i.e. an order of magnitude above Omni-swarm's 59.4 kB/s but still small for WiFi.

### Gaps
- D²SLAM gives totals in MB per dataset, not kB/s; no WiFi hardware is named.
- No report from either paper of behaviour under WiFi dropouts beyond the stated fallback to single-robot mode.

## Q3. Relative localisation error and drift, with/without UWB and inter-agent loop closures

### Takeaway
Omni-swarm (2 drones, indoor mocap, Table VI): relative error 0.062-0.072 m / 1.3-4.3° with everything on; removing UWB barely changes it (0.063-0.083 m), removing map-based loop closure moves relative error only to 0.062-0.075 m but doubles ATE on some runs (0.086 -> 0.225 m); VIO-only relative error 0.16-0.26 m. Outdoor 235 m: 1.9 m (0.8 %) drift vs 6.35 m for VIO. D²SLAM real D435i flights: relative position error 0.05-0.07 m per axis without yaw motion, 0.10-0.14 m with yaw; ATE 0.09-0.15 m after PGO.

### Cited Findings
Omni-swarm (all from Table VI unless noted; units m / degrees; ATE = absolute trajectory error of the swarm estimate, RE = relative error between drones)
- Proposed (UWB + map-based loop + detection) ATE: Parallel1 0.127 / 2.2°, Parallel2 0.086 / 3.0°, Parallel3 0.119 / 1.8°, RandFlight 0.088 / 2.7° — [ar5iv 2103.04131](https://ar5iv.labs.arxiv.org/html/2103.04131)
- Proposed RE: Parallel1 0.062 / 2.3°, Parallel2 0.063 / 4.3°, Parallel3 0.072 / 1.8°, RandFlight 0.069 / 1.3° — [ar5iv 2103.04131](https://ar5iv.labs.arxiv.org/html/2103.04131)
- Without UWB: ATE 0.126 / 0.094 / 0.128 / 0.092 m; RE 0.063 / 0.083 / 0.082 / 0.071 m (same dataset order) — [ar5iv 2103.04131](https://ar5iv.labs.arxiv.org/html/2103.04131)
- Without map-based (inter-drone loop) measurements: ATE 0.160 / 0.225 / 0.242 / 0.079 m; RE 0.062 / 0.069 / 0.075 / 0.074 m — [ar5iv 2103.04131](https://ar5iv.labs.arxiv.org/html/2103.04131)
- Without visual drone tracking: ATE 0.149 / 0.103 / 0.134 / 0.101 m; RE 0.100 / 0.096 / 0.081 / 0.078 m — [ar5iv 2103.04131](https://ar5iv.labs.arxiv.org/html/2103.04131)
- Without outlier rejection: RE up to 0.143 m / 9.8° (RandFlight rot) and ATE up to 0.535 m / 5.1° (Parallel3) — [ar5iv 2103.04131](https://ar5iv.labs.arxiv.org/html/2103.04131)
- VIO-only RE: 0.261 / 0.230 / 0.225 / 0.160 m; PGO baseline RE 0.114-0.130 m; "Xu2020" (the authors' earlier UWB+VIO+detection fusion) RE 0.959 / 0.241 / 0.566 / 0.191 m — [ar5iv 2103.04131](https://ar5iv.labs.arxiv.org/html/2103.04131)
- Outdoor (Sec. VII-D): 235 m run, estimated drift 1.9 m (0.8 %) vs 6.35 m for VIO; no ground truth — [ar5iv 2103.04131](https://ar5iv.labs.arxiv.org/html/2103.04131)
- Collision avoidance (Table IX): 3 drones RE x/y/z 0.076 / 0.074 / 0.083 m (VIO 0.064 / 0.061 / 0.030 m); 4 drones 0.065 / 0.056 / 0.088 m (VIO 0.070 / 0.131 / 0.064 m) — [ar5iv 2103.04131](https://ar5iv.labs.arxiv.org/html/2103.04131)
- Keyframe deletion strategy (Table VIII): RandDel (proposed) ATE Parallel1 0.086 m / 3.0°, NoDel 0.091 m, sliding window 0.153 m; solve time 14 ms vs 21 ms vs 12 ms — [ar5iv 2103.04131](https://ar5iv.labs.arxiv.org/html/2103.04131)
- Headline claims: "centimeter-level relative state estimation accuracy"; prior UWB-odometry methods "generally around 20 cm–50 cm" (Sec. I) — [arXiv abstract 2103.04131](https://arxiv.org/abs/2103.04131)

D²SLAM
- Near-field D²VINS, TUM-VI ROOM stereo handheld (Table II): ROOM 5 ATE 0.090 m / 1.85°, RE 0.073 m / 1.57° vs VINS-Mono 0.164 m / 1.62°, RE 0.209 m / 2.28°; ROOM 3 ATE 0.128 m / 2.40°, RE 0.119 m / 2.95° — [arXiv HTML 2211.01538v4](https://arxiv.org/html/2211.01538v4)
- Near-field, own quad-fisheye flights (Table III): Omni 2 ATE 0.069 m / 0.85°, RE 0.075 m / 0.32°; Omni 5 ATE 0.075 m / 0.71°, RE 0.076 m / 0.37°; OmniLongNoYaw 5 ATE 0.122 m, RE 0.043 m / 0.53°; OmniLongYaw 5 ATE 2.322 m / 11.09° but RE 0.028 m / 0.65° (VINS-Mono ATE 4.865 m, RE 1.466 m) — [arXiv HTML 2211.01538v4](https://arxiv.org/html/2211.01538v4)
- Far-field D²SLAM vs DOOR-SLAM (Table V): OmniLongYaw 5 ATE 0.168 m / 3.33°, RE 0.037 m / 0.91° (DOOR-SLAM 0.149 m, RE 0.085 m); TUM ROOM 5 ATE 0.032 m, RE 0.079 m; TUM Corr 5 ATE 0.275 m / 3.93°, RE 0.206 m / 1.77° (DOOR-SLAM ATE 0.068 m, RE 0.145 m) — [arXiv HTML 2211.01538v4](https://arxiv.org/html/2211.01538v4)
- Real D435i flights (Table IX, D²VINS -> D²PGO): NoYaw 51.0 m: ATE 0.103 -> 0.090 m, 2.24° -> 1.95°, RE x/y/z 0.047 / 0.067 / 0.056 m, RE rot 3.36°; Yaw 73.3 m: ATE 0.219 -> 0.147 m, 5.69° -> 4.17°, RE 0.124 / 0.144 / 0.100 m, RE rot 8.88° — [arXiv HTML 2211.01538v4](https://arxiv.org/html/2211.01538v4)
- Authors' stated limitation: limited stereo FoV overlap reduces relative accuracy during yaw rotation; accuracy decreases slightly with inter-UAV distance (Sec. IX, X) — [arXiv HTML 2211.01538v4](https://arxiv.org/html/2211.01538v4)
- A user running TUM corridor4_512 single-drone reported results better than the mocap-tagged GT topic visually, before loop closure crashed — [D2SLAM issue #1](https://github.com/HKUST-Aerial-Robotics/D2SLAM/issues/1)

### Inferences
- In Omni-swarm the ablations show that once inter-drone visual loop closures exist, UWB contributes almost nothing to relative accuracy (0.062 vs 0.063 m on Parallel1); UWB's value is in initialisation and in holding ATE when visual matches are sparse (Parallel2/3 ATE 0.086 -> 0.225 m without map). For the lab's plan (UWB + shared positions, no shared visual features) the closest Omni-swarm proxy is the "PGO"/"Xu2020" columns, i.e. 0.11-0.13 m RE at best, 0.2-0.96 m in parallel flight.
- D²SLAM with the lab's own D435i produces 5-14 cm relative error only in near mode (3-5 m) with substantial co-visibility; the yaw-motion case roughly doubles error.

### Gaps
- Neither paper reports drift as a function of time (only per-run ATE/RE and one outdoor end-point drift).
- Omni-swarm has no UWB-only (no vision) accuracy row; a user asked exactly this and got no answer — [Omni-swarm issue #12](https://github.com/HKUST-Aerial-Robotics/Omni-swarm/issues/12)
- D²SLAM Table IX does not separate near/far mode contributions; no comparison against Omni-swarm, COVINS or Kimera-Multi is in the results tables.

## Q4. How yaw becomes observable in Omni-swarm; anchors and initialisation

### Takeaway
Omni-swarm estimates 4-DoF relative poses (roll/pitch from gravity via VIO) and gets yaw from map-based inter-drone visual localisation (one match suffices) or CNN 6-DoF drone detection; UWB-odometry alone needs excited motion (box 1.5 x 1.5 x 0.8 m), cannot give the yaw of a hovering drone and is unobservable in parallel flight. No external anchors are required; initialisation took 1.29-1.43 s with 100 % success.

### Cited Findings
- 4-DoF formulation (Sec. III-B): roll and pitch come from VIO with gravity "consistent among drones", so relative states are 4-DoF; yaw drift removed via the yaw-difference term in Eq. (1) — [ar5iv 2103.04131](https://ar5iv.labs.arxiv.org/html/2103.04131)
- Map-based measurements between drones i ≠ j give "sufficient observability of the relative pose" and are validated with a gravity-consistency check (G_CHECK) (Sec. IV-C2); one map-based measurement suffices for initialisation (Sec. V-E, Table I) — [ar5iv 2103.04131](https://ar5iv.labs.arxiv.org/html/2103.04131)
- Visual detection: YOLOv4-tiny detector at about 1 Hz, MOSSE tracker at 10 Hz on the upward camera only, CNN 6-DoF pose estimator; anonymous detections associated by DFS (Sec. IV-B, V-E) — [ar5iv 2103.04131](https://ar5iv.labs.arxiv.org/html/2103.04131)
- UWB-odometry initialisation: requires at least 3-DoF observability and a motion box of 1.5 x 1.5 x 0.8 m; three random starts with x/y in [-5, 5] m, z in [-1, 1] m, yaw from VIO; 15 ms on PC, 100 ms onboard; "one moving drone and one fixed drone gives position but not yaw of the fixed drone"; parallel flight is unobservable and "can yield wrong results" (Sec. V-E, Table I, Fig. 7) — [ar5iv 2103.04131](https://ar5iv.labs.arxiv.org/html/2103.04131)
- Related-work statement: UWB-odometry relative localisation "can become unobservable in some cases, e.g., parallel flight tasks" (Sec. II-B) — [ar5iv 2103.04131](https://ar5iv.labs.arxiv.org/html/2103.04131)
- Initialisation performance (Table VII): proposed 1.29-1.43 s, one trial, 100 % success indoors and outdoors; Xu2020 needed 52-84 s and 0 % success on Parallel1 — [ar5iv 2103.04131](https://ar5iv.labs.arxiv.org/html/2103.04131)
- UWB outlier rejection thresholds: elevation 37°, distance 0.3 m; UWB distances sampled at 100 Hz — [ar5iv 2103.04131](https://ar5iv.labs.arxiv.org/html/2103.04131)
- No fixed anchors: the system claims no external infrastructure; earlier VIR methods needed a fixed UWB anchor (Sec. II-D) — [ar5iv 2103.04131](https://ar5iv.labs.arxiv.org/html/2103.04131)
- Back-end keeps at most m_max = 100 swarm keyframes (Sec. V-A); complexity O(n²) in drones (Sec. VIII) — [ar5iv 2103.04131](https://ar5iv.labs.arxiv.org/html/2103.04131)
- D²SLAM, for contrast, has no UWB or mutual detection; the conclusion lists integrating "relative measurements such as UWB or mutual visual detection" as future work — [arXiv HTML 2211.01538v4](https://arxiv.org/html/2211.01538v4)

### Inferences
- The lab's plan (positions + UWB ranges, no shared visual features) is exactly the Omni-swarm "UWB-odometry" sub-problem; Omni-swarm's own analysis says yaw is observable only with relative motion excitation, which fails in formation/parallel flight and for a hovering peer. Any 4-DoF alignment scheme without a visual or bearing cue will inherit these degeneracies.

### Gaps
- The paper does not publish a numerical yaw error for the UWB-odometry-only configuration.

## Q5. ROS version, licence, hardware/software assumptions

### Takeaway
Both are ROS 1, catkin, GPU-mandatory. Omni-swarm: ROS 1 (Melodic implied by TX2/Ubuntu 18.04), GPLv3 per README, TensorRT 7.1.3.4 + libtorch paths hard-coded, officially TX2 only, Docker image needs an RTX 3080-class GPU, VINS-Fisheye front-end (pinhole mode exists), Nooploop UWB via serial driver. D²SLAM: ROS 1 Noetic in Docker, LGPL-3 per README, CUDA required (no-CUDA build is VIO only), onnxruntime-gpu 1.12.1 + TensorRT INT8, tested on Xavier NX JetPack 5.0.2, Jetson Orin Docker image (L4T 35.3.1) exists, supports STEREO_PINHOLE (D435i config shipped), FOURCORNER_FISHEYE and PINHOLE_DEPTH (VIO only); STEREO_FISHEYE unsupported.

### Cited Findings
Omni-swarm
- Licence: README says GPLv3; GitHub API reports no detected licence file and the top-level tree has no LICENSE file (.gitignore, README.md, doc, localization_proxy, swarm_localization, swarm_loop) — [Omni-swarm README](https://github.com/HKUST-Aerial-Robotics/Omni-swarm)
- ROS: all packages use `<buildtool_depend>catkin</buildtool_depend>` and `roslaunch` commands (ROS 1); distribution not named; "officially supported on NVIDIA TX2 with Ubuntu 18.04" — [swarm_loop/package.xml](https://github.com/HKUST-Aerial-Robotics/Omni-swarm/blob/pinhole_compatiable/swarm_loop/package.xml), [README](https://github.com/HKUST-Aerial-Robotics/Omni-swarm)
- Build assumptions in CMake: `set(TENSORRT_ROOT $ENV{HOME}/source/TensorRT-7.1.3.4)`, `Torch_DIR "$ENV{HOME}/source/libtorch/..."`, `yolo-tensorrt` include path — [swarm_loop/CMakeLists.txt](https://github.com/HKUST-Aerial-Robotics/Omni-swarm/blob/pinhole_compatiable/swarm_loop/CMakeLists.txt)
- Docker image `xuhao1/swarm2020:pc` "only works with RTX 3080-class GPUs because the front-end uses a TensorRT engine"; ONNX Runtime port and buildable Dockerfile "in progress" with no date — [README](https://github.com/HKUST-Aerial-Robotics/Omni-swarm); Docker Hub tags: pc (2022-06-14, 15.93 GB), master (2020-07-01), latest (2020-07-16) — [Docker Hub xuhao1/swarm2020](https://hub.docker.com/r/xuhao1/swarm2020/tags)
- Cameras: stereo fisheye front-end via VINS-Fisheye (required dependency, "works in pinhole or fisheye mode"); pinhole path via `roslaunch swarm_loop realsense.launch`; default branch is literally `pinhole_compatiable` — [README](https://github.com/HKUST-Aerial-Robotics/Omni-swarm), [VINS-Fisheye](https://github.com/HKUST-Aerial-Robotics/VINS-Fisheye)
- UWB: "Only the NoopLoop UWB module is supported"; can run with `enable_uwb:=false` and manual `self_id` — [README](https://github.com/HKUST-Aerial-Robotics/Omni-swarm); driver is a serial-port node (open_port/baudrate) that also publishes/broadcasts up to 250-byte strings to all nodes — [inf_uwb_ros](https://github.com/HKUST-Swarm/inf_uwb_ros)
- Required sibling repos: swarm_msgs, inf_uwb_ros; optional swarm_detector; ground station swarm_gcs with "custom mavlink protocol" — [README](https://github.com/HKUST-Aerial-Robotics/Omni-swarm), [swarm_gcs](https://github.com/HKUST-Swarm/swarm_gcs) (via search snippet)
- Paper: VINS-Fisheye front-end CUDA-accelerated; CNNs via TensorRT, about 2x faster than TensorFlow/PyTorch on TX2; onboard rates (Table II): VINS front-end 16 Hz, back-end 8 Hz, detection 1 Hz, tracking 10 Hz, descriptors 0.3 Hz, optimisation 1 Hz; per-module onboard times (Table X, ms): VINS front-end 12.1-19.5, back-end 43.8-82.1, detection+tracking 32.8-41.4, descriptors 262.6-273.7, loop detection 28.1-48.9, PCM 0.8-110.5, optimisation 6.2-155.5 — [ar5iv 2103.04131](https://ar5iv.labs.arxiv.org/html/2103.04131)

D²SLAM
- Licence: README says LGPL-3; GitHub API reports no detected licence; top-level tree has no LICENSE file — [D2SLAM README](https://github.com/HKUST-Aerial-Robotics/D2SLAM)
- ROS/Docker stack: ROS Noetic, Ceres 2.1.0, onnxruntime-gpu 1.12.1, libtorch, LCM, faiss, OpenCV 4 with CUDA, OpenGV, Backward; tested on Jetson Xavier NX JetPack 5.0.2 / L4T 35.1.0; "building on Jetson takes hours"; no-CUDA Dockerfiles exist but without CUDA SuperPoint/NetVLAD, loop closure, pose graph, multi-robot localisation and depth generation are unavailable (VIO only) — [docker/README.md](https://github.com/HKUST-Aerial-Robotics/D2SLAM/blob/main/docker/README.md)
- Main-branch Jetson Dockerfile: `FROM hkustswarm/d2slam:jetson_orin_base_35.3.1`, `ARG ROS_VERSION=noetic` — [docker/Dockerfile.jetson](https://github.com/HKUST-Aerial-Robotics/D2SLAM/blob/main/docker/Dockerfile.jetson); Docker Hub tags: jetson_orin (2024-08-14, 10.7 GB), jetson_orin_base_35.3.1 (2024-08-14, 9.83 GB), OmniNxt (2024-07-04), x86 (2024-06-25, 6.21 GB), jetson_base_35.1.0 (2023-10-14) — [Docker Hub hkustswarm/d2slam](https://hub.docker.com/r/hkustswarm/d2slam/tags)
- Maintainer on Jetson Orin: `make jetson` built the Xavier NX image; Orin users must switch to the develop branch; user confirmed it then ran on Orin with a D435i but saw "obvious delay" in output — [D2SLAM issue #21](https://github.com/HKUST-Aerial-Robotics/D2SLAM/issues/21)
- Camera modes: STEREO_PINHOLE = 0, STEREO_FISHEYE = 1 (unsupported), PINHOLE_DEPTH = 2 (VIO only), FOURCORNER_FISHEYE = 3; shipped D435 config uses `/camera/infra1/image_rect_raw`, `/camera/infra2/image_rect_raw`, 640x480, IMU 400 Hz from a DJI SDK topic, `estimate_extrinsic: 1`, `is_compressed_images: 1` (README warns not to enable compression in real experiments and not to estimate extrinsics with multiple robots) — [config/realsense_d435/d435_single.yaml](https://github.com/HKUST-Aerial-Robotics/D2SLAM/blob/main/config/realsense_d435/d435_single.yaml), [README](https://github.com/HKUST-Aerial-Robotics/D2SLAM)
- Config directory also has GRACO, MIT_datasets, NTU_VIRAL, gopro, quadcam, quadcam_drone_nxt_tmp, tum, visensor_f9p — [config/](https://github.com/HKUST-Aerial-Robotics/D2SLAM/tree/main/config)
- Branches: main, develop (last commit 2023-09-03), feat_jeston_orin_drone (last 2023-08-23, "docker image for jetpack 35.3.1", INT8 HITNet depth), non-cuda, 3DGS, graco, CXX17, shared_ptr, track_sp_use_lk, chuhao_semantic — [D2SLAM branches](https://github.com/HKUST-Aerial-Robotics/D2SLAM/branches)
- Paper compute (Table VI, Xavier NX, ONNX Runtime + TensorRT INT8): image preprocessing 41.7 ms at 15 Hz, local feature tracking 2.67 ms, remote tracking 1.64 ms at 5 Hz, optimisation 56.23 ms at 5 Hz, marginalisation 16.88 ms — [arXiv HTML 2211.01538v4](https://arxiv.org/html/2211.01538v4)
- Third-party Xavier NX timings: SuperPoint 62.0 ms (no TRT) / 33.9 ms (fp16) / 28.0 ms (INT8); NetVLAD 15.5 / 5.9 ms; SuperGlue 83.1 / 80.1 ms; another user measured about 15 ms per SuperPoint image on Jetson Orin; README calls SuperGlue "EXTREME SLOW" — [D2SLAM issue #33](https://github.com/HKUST-Aerial-Robotics/D2SLAM/issues/33), [README](https://github.com/HKUST-Aerial-Robotics/D2SLAM)
- UWB: none in D²SLAM; README only excludes `/uwb_node/incoming_broadcast_data` from bag playback — [README](https://github.com/HKUST-Aerial-Robotics/D2SLAM)

### Inferences
- Omni-swarm = ROS Melodic era (TX2, Ubuntu 18.04, TensorRT 7.1); porting to ROS 2 Jazzy on Orin NX means re-exporting all CNN engines and rewriting message/transport layers; the realistic reuse is the formulation, not the code.
- D²SLAM in its Noetic Docker container can run on an Orin NX today (image exists), but integrating with a ROS 2 Jazzy stack would require a ros1_bridge or re-publishing camera/IMU topics into the container; no ROS 2 port exists in any branch.

### Gaps
- Exact Nooploop model (LinkTrack vs other) and serial protocol compatibility with current Nooploop firmware: UNVERIFIED (driver source only shows a generic serial parser; author called it "infinity uwb").
- No published GPU-memory figures for either system.

## Q6. Validation evidence: repo activity, issues, stars/forks, third-party reuse, build failures

### Takeaway
Omni-swarm is effectively abandoned: last push 2022-07-03, 291 stars / 46 forks, 13 open vs 3 closed issues, no maintainer reply visible after 2022-10-28, and no third-party report of it running. D²SLAM is semi-maintained: last push 2024-12-13, 474 stars / 70 forks, 42 open vs 24 closed issues, a steady stream of crash/build reports through 2026, a few users confirming it runs on Jetson NX/Orin with D435i, and HKUST's own OmniNxt platform as its main downstream user. No independent group was found that reproduced either system's multi-drone accuracy.

### Cited Findings
Omni-swarm
- GitHub API (2026-10-22): 291 stars, 46 forks, 13 open issues, created 2021-06-16, last push 2022-07-03 ("Update README.md"; previous: "Update dataset path", "Fix bug on desc size"), default branch `pinhole_compatiable`, not archived — [Omni-swarm](https://github.com/HKUST-Aerial-Robotics/Omni-swarm)
- Issues: 13 open / 3 closed (16 total). Open items include missing PCA files `components_.csv`/`mean_.csv` (#16, 2024-05), "Can I run with a normal (non-omnidirectional) camera?" (#15, no reply), Docker image usage and source compilation issues (#13), "only use uwb distance and vio" (#12, no reply), HFNet model missing (#10), SuperPoint TensorRT tensor size mismatch (#9), Docker pull "unexpected EOF" (#6), non-Docker config (#5: maintainer promised "full instruction at Nov [2022]", user replied "Still waiting!" 2022-12-07), Dependencies (#3) — [Omni-swarm issues](https://github.com/HKUST-Aerial-Robotics/Omni-swarm/issues)
- Latest visible maintainer replies are dated 2022-10-28 (#5, #7) — [issue #5](https://github.com/HKUST-Aerial-Robotics/Omni-swarm/issues/5), [issue #7](https://github.com/HKUST-Aerial-Robotics/Omni-swarm/issues/7)
- Issue #5 author reports having built all packages from source without Docker, but no one in the tracker reports a successful end-to-end run on the datasets or hardware — [issue #5](https://github.com/HKUST-Aerial-Robotics/Omni-swarm/issues/5)
- Semantic Scholar "influential" citers of Omni-swarm include: RACER (T-RO 2022), MURP: Multi-Agent UWB Relative Pose Estimation (RA-L 2023), Swarm-LIO2 (2024), Robust and Scalable Multi-Robot Localization Using Stereo UWB Arrays (T-RO 2025), Flying Co-Stereo (T-RO 2025), Agile Formation Control (RA-L 2021), D²SLAM — [Semantic Scholar citations API](https://api.semanticscholar.org/graph/v1/paper/arXiv:2103.04131/citations?fields=title,year,venue,isInfluential); none of these was verified to run Omni-swarm code or use its dataset.
- Web searches for tutorials/blogs on building Omni-swarm (swarm_loop / swarm_localization) returned nothing relevant — search performed 2026-10-22, no source.

D²SLAM
- GitHub API (2026-10-22): 474 stars, 70 forks, 44 open issues+PRs (42 open issues, 24 closed issues), created 2023-03-11, last push 2024-12-13 ("Update models path"; preceding commits are a shared_ptr refactor of D2VINS/D2PGO, one labelled "In progress. modified half way through the commit process"), not archived — [D2SLAM](https://github.com/HKUST-Aerial-Robotics/D2SLAM)
- Issue activity continues after last commit: #71 "Unable to read model and csv params from the config files" (2025-10-27), #72 inter-swarm timestamp problem (2025-12), #73 non-cuda vs main (2026-01), #74 Orin Docker image point cloud z-axis downward with an OAK quad camera (2026-04) — all open, unanswered — [D2SLAM issues](https://github.com/HKUST-Aerial-Robotics/D2SLAM/issues)
- Build/run failures reported: Docker build fail on Ubuntu 20.04 (#68, 2025-05), TRT engine deserialisation errors (#59 closed, #52 closed), "[d2vins-2] process has died" (#53 open, #58 closed), double free (#67), macro redefinition (#69), enable_loop crash (#1 2023 — fixed via faiss version lock on 2023-08-05; #51 2024-11 same symptom, open), segfaults (#30, #34), Realsense config failing (#48 — maintainer: "wrong path settings, fixed in latest main", 2024-12-13) — [D2SLAM issues](https://github.com/HKUST-Aerial-Robotics/D2SLAM/issues), [issue #1](https://github.com/HKUST-Aerial-Robotics/D2SLAM/issues/1), [issue #48](https://github.com/HKUST-Aerial-Robotics/D2SLAM/issues/48)
- Third-party "it runs" reports: user ported to Jetson NX "and it works" (not yet flown) — [issue #1](https://github.com/HKUST-Aerial-Robotics/D2SLAM/issues/1); user ran develop-branch Docker on Jetson Orin with D435i, noted obvious output latency — [issue #21](https://github.com/HKUST-Aerial-Robotics/D2SLAM/issues/21); user ran two Jetson NX + D435i multi-robot, saw each other's VINS/PGO trajectories only after fixing multicast IP, PGO of the other drone shown inconsistently and not smooth — [issue #39](https://github.com/HKUST-Aerial-Robotics/D2SLAM/issues/39); user ran it in AirSim with problems (#11, open) — [issue #11](https://github.com/HKUST-Aerial-Robotics/D2SLAM/issues/11)
- Downstream by the same group: OmniNxt (IROS 2024, Orin NX 16 GB, quad 210° fisheye, Omni-VINS/Omni-Depth, "docker images for each main module") — [arXiv 2403.20085](https://arxiv.org/abs/2403.20085), [OmniNxt GitHub](https://github.com/HKUST-Aerial-Robotics/OmniNxt); Docker Hub carries an `OmniNxt` tag of d2slam (2024-07-04) — [Docker Hub hkustswarm/d2slam](https://hub.docker.com/r/hkustswarm/d2slam/tags); develop branch merged PR #18 from an org named "D2SLAM-Fusion" (2023-09-03) — [D2SLAM commits develop](https://github.com/HKUST-Aerial-Robotics/D2SLAM/commits/develop)
- Third-party papers found citing D²SLAM in 2025-2026 (Flying Co-Stereo, arXiv 2506.00546; FLOCC-SLAM, arXiv 2602.02430 which benchmarks against Swarm-SLAM instead) do not use it as a baseline — [arXiv 2506.00546](https://arxiv.org/abs/2506.00546), [arXiv 2602.02430](https://arxiv.org/abs/2602.02430)

### Inferences
- D²SLAM's open-issue-to-closed ratio (42:24) and unanswered 2025-2026 issues indicate maintenance has stopped since the Dec 2024 refactor, which itself was left mid-stream ("modified half way through").
- Nobody outside HKUST has published a multi-drone accuracy reproduction of either system; the only external validation is anecdotal GitHub issues.

### Gaps
- Citation counts could not be retrieved (Semantic Scholar API returned HTTP 429 rate-limit on every attempt; Google Scholar not accessible). UNVERIFIED.
- ROS Discourse / forum threads: none found by search.
- Fork activity (whether any fork is ahead of upstream) not checked.

## Q7. Datasets released with the papers

### Takeaway
Both groups host datasets on Dropbox and the links resolve (HTTP 200 on 2026-10-22). Omni-swarm: one shared folder "omniswarm-opensource-datasets" (31.5 GB zip) with raw and preprocessed omnidirectional + pinhole data from the 2-drone indoor runs (UWB included by construction, mocap GT indoors). D²SLAM: quad-camera folder "D2SLAM_sharing" (171.5 GB zip) and an aligned TUM-VI multi-robot set tum_corr.7z (1.40 GB), plus a Baidu mirror; no UWB. Folder contents could not be listed (Dropbox page is JavaScript-only).

### Cited Findings
Omni-swarm
- README: "raw and preprocessed official omni-directional and pinhole dataset" at https://www.dropbox.com/sh/w5yagas06a9r14d/AACdKgMfCCg07M6jr6Ipmus1a?dl=0 ; CNN models at https://www.dropbox.com/s/skq1vgfeawiw151/models.zip?dl=0 — [Omni-swarm README](https://github.com/HKUST-Aerial-Robotics/Omni-swarm)
- Link check 2026-10-22: dataset folder HTTP 200 (redirects to https://www.dropbox.com/scl/fo/8n2ia0i76usy0mlxf21ml/AFxbbUX7-bdc265KcNfuikg?rlkey=r3sa6jo5b3r71dunyfb7jq264&dl=0); `dl=1` returns `omniswarm-opensource-datasets.zip`, Content-Length 31,474,341,037 bytes (31.5 GB); models.zip HTTP 200 — verified by HTTP HEAD (this note).
- Dataset content per paper (Table V): 2-drone indoor runs Parallel1/2/3, RandFlight (93.0 / 106.4 / 130.7 / 45.5 m) with mocap GT, and Outdoor1 (237.2 m, no GT); sensors on each drone: dual 235° fisheye, IMU (DJI N3), Nooploop UWB — [ar5iv 2103.04131](https://ar5iv.labs.arxiv.org/html/2103.04131)
- Replay requires `bag_replay:=true` and the HKUST-Swarm `sync_bag_player` tool — [README](https://github.com/HKUST-Aerial-Robotics/Omni-swarm), [sync_bag_player](https://github.com/HKUST-Swarm/sync_bag_player)
- A closed issue asked about dataset access (#2 "数据集 dataset", 2022-04) — [Omni-swarm issue #2](https://github.com/HKUST-Aerial-Robotics/Omni-swarm/issues/2)

D²SLAM
- README: quad-camera omnidirectional datasets https://www.dropbox.com/scl/fo/jtiwfx98ms7cty946nmug/h?dl=0&rlkey=n03gf3jqmthzy655ku0ycbny0 ; aligned TUM Corr https://www.dropbox.com/s/ic0yuxr2xym1m0c/tum_corr.7z?dl=0 ; Baidu mirror https://pan.baidu.com/s/1qyRUHUeVCvORXM4CrIZCxg?pwd=D2SL (code D2SL); "More datasets will be released very soon" (no date) — [D2SLAM README](https://github.com/HKUST-Aerial-Robotics/D2SLAM)
- Link check 2026-10-22: quad-cam folder HTTP 200, `dl=1` returns `D2SLAM_sharing.zip`, Content-Length 171,548,106,398 bytes (171.5 GB); tum_corr.7z HTTP 200, 1,402,927,165 bytes (1.40 GB); models.zip HTTP 200 — verified by HTTP HEAD (this note). Baidu link not tested.
- Dataset definitions (Sec. IX-A, Table I): Omni 2 / Omni 5: quad fisheye + IMU, "Flight", GT "Yes"; OmniLongNoYaw 5 / OmniLongYaw 5: five-robot flights with fixed vs moving yaw, GT status not listed; TUM Corr 5 built from TUM-VI corridor sequences ("TUM Corr 2 ... combination of TUM VI corridor datasets 1, 2"), GT "Partial"; TUM ROOM 5: stereo + IMU handheld, GT "Yes"; multi-robot sets were made by "align[ing] multiple segments of data into a single multi-robot dataset" and "partly used a motion capture system" — [arXiv HTML 2211.01538v4](https://arxiv.org/html/2211.01538v4)
- A user from mainland China could not download from Dropbox; the Baidu mirror was added in response (#6, closed) — [D2SLAM issue #6](https://github.com/HKUST-Aerial-Robotics/D2SLAM/issues/6)

### Inferences
- The D²SLAM "5-robot" datasets are stitched from separate single-robot recordings, so they exercise map merging but not simultaneous multi-drone dynamics or inter-drone interference; they contain no UWB. The Omni-swarm dataset is the only one of the two with real UWB ranges between drones, and it is 2-drone only.

### Gaps
- File-level contents (bag names, topics, formats, whether the pinhole subset includes UWB) could not be listed because Dropbox renders the folder via JavaScript; UNVERIFIED beyond the archive sizes above.
- The Baidu mirror was not verified.

## Q8. Verdict for the lab (Starling 2 Max, Orin NX 16 GB, D435i, Nooploop LinkTrack, ROS 2 Jazzy, WiFi)

### Takeaway
Omni-swarm: NO as code, YES as the reference design. D²SLAM: PARTLY — it can run on Orin NX with a D435i in its ROS 1 Noetic container today, but it has no UWB, is not ROS 2, is unmaintained since Dec 2024 and has many open crash reports; treat as an experiment-only alternative, not a dependency.

### Cited Findings
- Omni-swarm blockers: ROS 1/catkin, TX2 + Ubuntu 18.04 official target, TensorRT 7.1.3.4/libtorch hard-coded paths, Docker image bound to RTX 3080-class GPUs, ONNX port never shipped, last commit 2022-07-03, missing PCA files (#16), no maintainer replies since 2022-10 — [README](https://github.com/HKUST-Aerial-Robotics/Omni-swarm), [CMakeLists](https://github.com/HKUST-Aerial-Robotics/Omni-swarm/blob/pinhole_compatiable/swarm_loop/CMakeLists.txt), [issues](https://github.com/HKUST-Aerial-Robotics/Omni-swarm/issues)
- Omni-swarm fit points: Nooploop UWB is the only supported UWB (brand match with the lab's LinkTrack; exact model UNVERIFIED); a pinhole/RealSense launch path exists; the 4-DoF relative-pose formulation, UWB outlier thresholds (37°, 0.3 m), init motion box (1.5 x 1.5 x 0.8 m) and bandwidth budget (59.4 kB/s per drone) are directly reusable design numbers — [README](https://github.com/HKUST-Aerial-Robotics/Omni-swarm), [ar5iv 2103.04131](https://ar5iv.labs.arxiv.org/html/2103.04131)
- D²SLAM fit points: STEREO_PINHOLE mode with shipped D435 config; real flights were done with D435i; Jetson Orin Docker image published 2024-08-14; near-field relative error 0.05-0.07 m per axis (no yaw) / 0.10-0.14 m (yaw) in real flight; mean comm delay 23.89 ms over WiFi — [config d435_single.yaml](https://github.com/HKUST-Aerial-Robotics/D2SLAM/blob/main/config/realsense_d435/d435_single.yaml), [Docker Hub](https://hub.docker.com/r/hkustswarm/d2slam/tags), [arXiv HTML 2211.01538v4](https://arxiv.org/html/2211.01538v4)
- D²SLAM blockers: ROS 1 Noetic only; CUDA mandatory (no-CUDA = VIO only); no UWB at all (future work); SuperPoint about 15 ms/image on Orin per user report, SuperGlue "EXTREME SLOW"; 42 open issues including unanswered 2025-2026 crash/config reports; last commit is a half-finished refactor — [docker/README.md](https://github.com/HKUST-Aerial-Robotics/D2SLAM/blob/main/docker/README.md), [issue #33](https://github.com/HKUST-Aerial-Robotics/D2SLAM/issues/33), [issues](https://github.com/HKUST-Aerial-Robotics/D2SLAM/issues)
- Key evidence for the lab's own plan: Omni-swarm Table VI shows UWB adds little once inter-drone visual loop closures exist (RE 0.062 vs 0.063 m), while UWB+odometry without vision (Xu2020/PGO columns) sits at 0.11-0.96 m RE and fails to initialise in parallel flight (0 % success, 52-84 s) — [ar5iv 2103.04131](https://ar5iv.labs.arxiv.org/html/2103.04131)

### Inferences
- For the lab's "own VIO + 4-DoF alignment from shared positions + UWB ranges" plan, Omni-swarm's results predict roughly decimetre relative accuracy and yaw ambiguity in formation flight unless a bearing/visual cue (drone detection, shared keyframe matching, or at least rich relative motion) is added. Budget ~5 kB/s per drone for the position+range channel (Omni-swarm Table III) — comfortably within UWB broadcast payloads or WiFi.
- If the lab wants collaborative visual loop closures, porting D²SLAM's d2frontend (SuperPoint + NetVLAD via ONNX Runtime/TensorRT) is more realistic than reviving Omni-swarm's swarm_loop, because Orin-era Docker images and a D435i config already exist; but a ROS 2 Jazzy port and UWB factor would both be new engineering.

### Gaps
- No evidence that anyone has run either system under ROS 2 or with ros1_bridge.
- Nooploop LinkTrack protocol compatibility with inf_uwb_ros (built 2019-2022 for an unnamed Nooploop module) is UNVERIFIED; the driver repo was last pushed 2024-12-20 but its README names no model — [inf_uwb_ros](https://github.com/HKUST-Swarm/inf_uwb_ros)
