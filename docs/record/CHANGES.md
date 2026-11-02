RECORD · SIM + REAL — append-only change log ([CODING_STANDARD.md](../CODING_STANDARD.md)). One line per change. The full entry (eight fields) is in the body of the commit that carries `Change: CHG-nnnn`; read it with `python3 tools/docs_check/changes.py show CHG-nnnn`. Never edit or delete a line; correct with a new one.

Open (owner, 2026-11-02): which MPC limits the drone flies is unknown until the owner supplies the drone's parameter files. The QGC check (NEAR-914) was canceled. Until then the reference is `starling_1_indoor_params.params`.

# Changes

The last cell is `this` (the commit that carries the entry) or the sha(s) of older commits that the entry describes (backfilled, or a late entry for a commit that slipped through).

| ID | Date | Scope | What | Commit |
|---|---|---|---|---|
| CHG-0001 | 2026-10-30 | sim-only | patch 0006: sim teleop, released sticks park the drone (commander velocity output only); backfilled | bdc58d6 |
| CHG-0002 | 2026-10-30 | sim-only | patch 0007: sim MAVROS interface sends room-frame velocities as FRAME_LOCAL_NED (velocity_frame local); backfilled | 02cce03 |
| CHG-0003 | 2026-10-20 | sim-only | sim airframe 10090_pegasus_starling2max baseline: CMU rotor geometry, rate gains x0.5, LNDMC_ROT_MAX 300, MPC limits above the drone's; backfilled | 803385a, 15100b6, 6d40f95, 5bb4e04, 2a70731, 7032af4, d739a73 |
| CHG-0004 | 2026-10-30 | sim-only | NEAR-860: cuvslam_stereo_node.py tracker split into make_tracker()/track_frame() for the offline replay; backfilled | 1790264 |
| CHG-0005 | 2026-11-02 | sim-only | sim stack takes NUM_ROBOTS and FLY_ARGS from test.env (default 3); yaw gains in the ulog header dump; backfilled | 777b0c3 |
| CHG-0006 | 2026-11-02 | tooling | collect dumps drone_1's ulog to px4_drone_1.csv (vehicle-time yaw): ulog_yaw_dump.py, yaw_core.py; backfilled | a9f38d3 |
| CHG-0007 | 2026-11-02 | tooling | live metrics carry heading (quaternion to ENU yaw, unwrapped), yaw rate and xy drift; backfilled | 923fbad |
| CHG-0008 | 2026-11-02 | tooling | heading reads NaN on an unfilled quaternion (norm² < 0.5); backfilled | 1c45625 |
| CHG-0009 | 2026-11-02 | tooling | sim.sh: NUM_ROBOTS and FLY_ARGS no longer leak from the caller's shell (only test.env sets them); stack texts and say line fixed; backfilled | 5ec0a04 |
| CHG-0010 | 2026-11-02 | tooling | yaw_core: NaN or short post-release windows read UNVERIFIED, not 0; new post_status key; yaw_dump caveat reworded; backfilled | 84c990f |
| CHG-0011 | 2026-11-02 | sim-only | new yaw_step test (one sim drone, yaw pulses, PX4-vehicle-time gates, live gain sweep) + tools/lib/changes_log.py; sim.sh quotes FLY_ARGS, FLY_TIMEOUT_S watchdog, changes.log copy-out; backfilled | 285fdbe |
| CHG-0012 | 2026-11-02 | sim-only | yaw_step review fixes: interrupted sets logged, booted gains restored before the patch-0007 check, sweep gates, fly.sh --check before Isaac, fly.sh CAVEAT lines become record caveats; backfilled | 5b7e6e1 |
| CHG-0014 | 2026-11-02 | sim-only | sim.sh down saves uncopied PX4 ulogs to ~/flight_logs/sim/uncollected_<date>/ before Isaac stops (--force skips); doctor fails without core.hooksPath | this |
| CHG-0013 | 2026-11-02 | sim-only | sim airframe: every param set-default line marked = real / SIM-ONLY (real value) with its CHG id; outer-loop comment corrected; no value changed | this |
| CHG-0015 | 2026-11-02 | tooling | correction of CHG-0003, CHG-0006, CHG-0011: 0003 drops "MPC limits above the drone's" (sim limits = the 2026-08-20 drone backup; which set flies is open) and adds cbf_sim.yaml + ROMFS mount; 0006 Verified by and Why; 0011 "(static)" restored; changes.py show prints corrections | this |
| CHG-0016 | 2026-11-02 | sim-only | tools/sim.sh param set NAME VALUE [--drone N]: one PX4 parameter of a sim drone live via MAVROS (tools/lib/px4_param_set.sh), read back, logged by the one formatter changes_log.py (+ drone_N/ prefix, MISMATCH mark, append CLI) | this |
| CHG-0017 | 2026-11-02 | tooling | every sim.sh test: start/end parameter snapshots (PX4 via MAVROS per drone, commander), PX4 ulog changed-parameter list, the run's changes.log on every path and a "Changes in this run" record block (unknown / UNLOGGED CHANGE / CONFLICT) | this |
| CHG-0018 | 2026-11-02 | sim-only | param set fix round: LOCALHOST discovery + refuse unless the MAVROS fcu_url is the sim PX4 (REFUSED line); no read-back / failed pull / no set mechanism = UNVERIFIED, exit 1; Ctrl-C logs an interrupted line on the host; yaw_step gates match drone_1 lines only | this |
| CHG-0019 | 2026-11-02 | tooling | run capture fix round: end snapshot forces the MAVROS param pull (after landing), partial/empty snapshots are notes without rows, "Changes in this run" names every unknown source and drone without a ulog, CONFLICT when the end snapshot differs from the last logged value, one record caveat when anything is flagged or unknown | this |
| CHG-0020 | 2026-11-02 | sim-only | yaw_step fly.sh sweep and restore set PX4 gains through px4_param_set.sh (drone_1/ lines, read-back, UNVERIFIED/REFUSED stop the sweep); gates count drone_1 lines only and judge PARAM REFUSED/UNVERIFIED stops | this |
| CHG-0021 | 2026-11-02 | sim-only | legacy hover/step driver unsets NUM_ROBOTS/FLY_ARGS/FLY_TIMEOUT_S before sourcing stack.sh, so an exported value can no longer make it a one-drone run | this |
| CHG-0022 | 2026-11-02 | sim-only | yaw_step fly.sh: spin runs on a stoppable SingleThreadedExecutor; exit order is executor.shutdown, join (5 s), destroy_node, rclpy.try_shutdown (was: bare rclpy.spin thread left running -> `terminate called without an active exception`, core dump); bash prints a CAVEAT when the python exits with a code other than 0/1 | this |
| CHG-0023 | 2026-11-02 | sim-only | sim airframe: MC_YAW_TQ_CUTOFF 2 Hz (PX4 v1.16 default) -> 15 Hz, the real drone's MC_YAW_CUTOFF under its v1.16 name; suspected cause of the sim yaw ring | this |
| CHG-0024 | 2026-11-02 | sim-only | sim airframe: MC_YAWRATE_P 0.07 -> 0.25, MC_YAWRATE_I 0.5 -> 0.2 (with the 15 Hz yaw filter of CHG-0023); real drone keeps 0.07 / 0.5 | this |
| CHG-0025 | 2026-11-02 | tooling | yaw_step fly.sh waits for swarm_commander to subscribe to the teleop topic, plus 2 s, before the first pulse; no pulses after 30 s without it | this |
| CHG-0026 | 2026-11-03 | sim-only | tools/teleop/frame.py: BODY/WORLD rotation, pending flip, heading guard — pure logic for the relay | this |
| CHG-0027 | 2026-11-03 | sim-only | tools/teleop/frame.py: a stale heading now stays latched (like a jump) until the keys are centred and the heading is fresh and steady, so odometry returning mid-push no longer resumes the full horizontal command | this |
