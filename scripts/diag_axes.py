#!/usr/bin/env python3
"""Diagnose axis/sign/scale mismatch between a cuVSLAM TUM trajectory and the ulog reference."""
import sys, numpy as np
sys.path.insert(0, '/exploration/scripts')
from score_vs_ulog import ulog_to_traj, takeoff_time
from evo.tools import file_interface
from evo.core import sync
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
est = file_interface.read_tum_trajectory_file(sys.argv[1]); ref, _ = ulog_to_traj(sys.argv[2])
off = takeoff_time(ref, 0.15) - takeoff_time(est, 0.15); est.timestamps = est.timestamps + off
r, e = sync.associate_trajectories(ref, est, max_diff=0.02)
P = r.positions_xyz - r.positions_xyz[0]; Q = e.positions_xyz - e.positions_xyz[0]
print("path length ref %.1f m, est %.1f m, ratio est/ref %.3f" % (r.path_length, e.path_length, e.path_length / r.path_length))
dP = np.diff(P, axis=0); dQ = np.diff(Q, axis=0)
C = np.array([[np.corrcoef(dQ[:, i], dP[:, j])[0, 1] for j in range(3)] for i in range(3)])
print("corr of velocity components: rows = est x,y,z ; cols = ref x,y,z (ENU)"); print(np.round(C, 2))
print("per-axis std ref", np.round(P.std(0), 2), " est", np.round(Q.std(0), 2))
print("ref z range %.2f..%.2f  est z range %.2f..%.2f" % (P[:, 2].min(), P[:, 2].max(), Q[:, 2].min(), Q[:, 2].max()))
fig, ax = plt.subplots(1, 3, figsize=(15, 5))
ax[0].plot(P[:, 0], P[:, 1], label="ref (ulog ENU)"); ax[0].plot(Q[:, 0], Q[:, 1], label="est (cuvslam FLU)"); ax[0].set_title("top-down x-y"); ax[0].axis("equal"); ax[0].legend()
t = r.timestamps - r.timestamps[0]
for i, n in enumerate("xyz"): ax[1].plot(t, P[:, i], label=f"ref {n}"); ax[2].plot(t, Q[:, i], label=f"est {n}")
ax[1].set_title("ref xyz vs t"); ax[2].set_title("est xyz vs t"); ax[1].legend(); ax[2].legend()
out = sys.argv[1].replace(".tum", "_diag.png"); plt.tight_layout(); plt.savefig(out, dpi=90); print("saved", out)
