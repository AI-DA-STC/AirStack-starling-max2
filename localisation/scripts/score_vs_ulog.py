#!/usr/bin/env python3
"""Score a cuVSLAM trajectory (TUM file from the bag) against the PX4 ulog of the same drone.

Reference = PX4 EKF2 local position from the ulog (sim: EKF2 on simulated GPS). It is a REFERENCE,
NOT ground truth, until the Isaac ground-truth publisher exists. Both clocks are sim time in lockstep
(PX4 boot time vs Isaac timeline), offset by a constant that we estimate from the takeoff event
(first time z rises > 0.15 m in each stream). Result files go next to the estimate.

Usage (inside the exploration container, pyulog + evo installed):
  python3 scripts/score_vs_ulog.py <estimate.tum> <drone.ulg> [--takeoff-thresh 0.15]
"""
import argparse, json, os, sys
import numpy as np
from scipy.spatial.transform import Rotation as R

from pyulog import ULog
from evo.core import metrics, sync
from evo.core.trajectory import PoseTrajectory3D
from evo.tools import file_interface

# NED -> ENU: x_enu = y_ned, y_enu = x_ned, z_enu = -z_ned (proper rotation, det +1)
R_ENU_FROM_NED = np.array([[0.0, 1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, -1.0]])
# body FRD -> FLU: x same, y and z flipped (proper rotation)
R_FLU_FROM_FRD = np.diag([1.0, -1.0, -1.0])


def ulog_to_traj(path):
    u = ULog(path, message_name_filter_list=["vehicle_local_position", "vehicle_attitude"])
    lp = next(d for d in u.data_list if d.name == "vehicle_local_position")
    att = next(d for d in u.data_list if d.name == "vehicle_attitude")
    t = lp.data["timestamp"] * 1e-6
    p_ned = np.stack([lp.data["x"], lp.data["y"], lp.data["z"]], axis=1)
    # attitude: interpolate quaternion by nearest sample (rates differ)
    ta = att.data["timestamp"] * 1e-6
    q_ned = np.stack([att.data["q[1]"], att.data["q[2]"], att.data["q[3]"], att.data["q[0]"]], axis=1)  # xyzw
    idx = np.clip(np.searchsorted(ta, t), 0, len(ta) - 1)
    q_ned = q_ned[idx]
    p_enu = p_ned @ R_ENU_FROM_NED.T
    R_wb_ned = R.from_quat(q_ned).as_matrix()                      # NED world <- FRD body
    R_wb_enu = R_ENU_FROM_NED @ R_wb_ned @ R_FLU_FROM_FRD.T         # ENU world <- FLU body
    q_enu = R.from_matrix(R_wb_enu).as_quat()                       # xyzw
    q_wxyz = np.column_stack([q_enu[:, 3], q_enu[:, 0], q_enu[:, 1], q_enu[:, 2]])
    sysid = None
    try:
        sysid = u.initial_parameters.get("MAV_SYS_ID")
    except Exception:
        pass
    return PoseTrajectory3D(positions_xyz=p_enu, orientations_quat_wxyz=q_wxyz, timestamps=t), sysid


def _aligned_rmse(ref, est, offset, max_diff):
    e = PoseTrajectory3D(est.positions_xyz.copy(), est.orientations_quat_wxyz.copy(), est.timestamps + offset)
    try:
        r_s, e_s = sync.associate_trajectories(ref, e, max_diff=max_diff)
    except Exception:
        return np.inf, 0
    if e_s.num_poses < 50:
        return np.inf, e_s.num_poses
    e_s.align(r_s, correct_scale=False)
    d = np.linalg.norm(e_s.positions_xyz - r_s.positions_xyz, axis=1)
    return float(np.sqrt(np.mean(d ** 2))), e_s.num_poses


def refine_offset(ref, est, offset0, max_diff):
    best = (np.inf, offset0)
    for step, span in ((0.25, 5.0), (0.05, 0.5), (0.01, 0.1)):
        centre = best[1]
        for o in np.arange(centre - span, centre + span + 1e-9, step):
            rmse, n = _aligned_rmse(ref, est, o, max_diff)
            if rmse < best[0]:
                best = (rmse, float(o))
    return best[1]


def takeoff_time(traj, thresh):
    z = traj.positions_xyz[:, 2] - traj.positions_xyz[0, 2]
    k = np.argmax(z > thresh)
    if z[k] <= thresh:
        raise RuntimeError("no takeoff found (z never rose above threshold)")
    return float(traj.timestamps[k])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("estimate_tum")
    ap.add_argument("ulog")
    ap.add_argument("--takeoff-thresh", type=float, default=0.15)
    ap.add_argument("--max-diff", type=float, default=0.02, help="association window [s]")
    a = ap.parse_args()

    est = file_interface.read_tum_trajectory_file(a.estimate_tum)
    ref, sysid = ulog_to_traj(a.ulog)
    print(f"estimate: {est.num_poses} poses, {est.timestamps[0]:.2f}..{est.timestamps[-1]:.2f} s")
    print(f"reference (ulog MAV_SYS_ID={sysid}): {ref.num_poses} poses, {ref.timestamps[0]:.2f}..{ref.timestamps[-1]:.2f} s")

    t_est = takeoff_time(est, a.takeoff_thresh)
    t_ref = takeoff_time(ref, a.takeoff_thresh)
    offset0 = t_ref - t_est
    print(f"takeoff: estimate {t_est:.2f} s, reference {t_ref:.2f} s -> initial clock offset {offset0:+.3f} s (ref = est + offset)")
    # refine: the takeoff edge is a coarse cue; search the offset that minimises the SE(3)-aligned APE
    offset = refine_offset(ref, est, offset0, a.max_diff)
    print(f"refined clock offset {offset:+.3f} s (searched ±5 s around the takeoff estimate)")
    est.timestamps = est.timestamps + offset

    ref_s, est_s = sync.associate_trajectories(ref, est, max_diff=a.max_diff)
    print(f"associated {est_s.num_poses} pose pairs (max_diff {a.max_diff} s)")
    path_len = float(ref_s.path_length)

    out = {"reference": "PX4 EKF2 local position from ulog (sim GPS) — NOT ground truth",
           "estimate": os.path.basename(a.estimate_tum), "ulog": os.path.basename(a.ulog),
           "mav_sys_id": sysid, "pairs": int(est_s.num_poses), "path_length_m": path_len,
           "clock_offset_s": offset}

    # APE translation, SE(3) aligned (Umeyama, no scale)
    est_al = est_s.copy() if hasattr(est_s, "copy") else PoseTrajectory3D(est_s.positions_xyz.copy(), est_s.orientations_quat_wxyz.copy(), est_s.timestamps.copy())
    est_al.align(ref_s, correct_scale=False)
    ape = metrics.APE(metrics.PoseRelation.translation_part)
    ape.process_data((ref_s, est_al))
    s = ape.get_all_statistics()
    out["ape_se3_m"] = {k: float(v) for k, v in s.items()}
    print(f"APE (SE3-aligned) rmse {s['rmse']:.3f} m, mean {s['mean']:.3f}, max {s['max']:.3f} m over {path_len:.1f} m path -> {100*s['rmse']/max(path_len,1e-9):.2f}% of path (rmse/len)")

    # APE rotation (aligned)
    ape_r = metrics.APE(metrics.PoseRelation.rotation_angle_deg)
    ape_r.process_data((ref_s, est_al))
    sr = ape_r.get_all_statistics()
    out["ape_rot_deg"] = {k: float(v) for k, v in sr.items()}
    print(f"APE rotation (aligned) rmse {sr['rmse']:.2f} deg, max {sr['max']:.2f} deg")

    # RPE per 1 m (drift), on the aligned pair
    rpe = metrics.RPE(metrics.PoseRelation.translation_part, delta=1.0, delta_unit=metrics.Unit.meters, all_pairs=False)
    rpe.process_data((ref_s, est_al))
    sp = rpe.get_all_statistics()
    out["rpe_1m_m"] = {k: float(v) for k, v in sp.items()}
    print(f"RPE per 1 m: rmse {sp['rmse']:.3f} m ({100*sp['rmse']:.1f}% per metre), mean {sp['mean']:.3f} m")

    # unaligned APE (frame offset included) for completeness
    ape_u = metrics.APE(metrics.PoseRelation.translation_part)
    ape_u.process_data((ref_s, est_s))
    su = ape_u.get_all_statistics()
    out["ape_unaligned_m"] = {k: float(v) for k, v in su.items()}
    print(f"APE unaligned rmse {su['rmse']:.3f} m (includes camera->body offset and frame yaw)")

    res = os.path.splitext(a.estimate_tum)[0] + "_vs_ulog.json"
    with open(res, "w") as f:
        json.dump(out, f, indent=2)
    print("saved", res)


if __name__ == "__main__":
    main()
