#!/usr/bin/env python3
"""Step responses from the commander's rosbag, with real timestamps (S5 / NEAR-786).

Runs INSIDE the robot container (needs rosbag2_py + the message packages):
    docker cp tools/hover_step_bag.py airstack-robot-desktop-1:/tmp/
    docker exec airstack-robot-desktop-1 bash -ic 'python3 /tmp/hover_step_bag.py <bag dir> drone_1'

Why: `ros2 topic echo` traces (analyze_step.py) have no timestamps and drop messages, so their time axis is only as
good as the assumed rate. The bag records /drone_1/odometry_conversion/odometry and the commander's own setpoint
(/drone_1/interface/mavros/setpoint_raw/local) with the receive time, so a step's onset, the commanded ramp and the
drone's settle are all measured on one clock.

Definitions (same shape as analyze_step.py so the numbers compare): a step starts when the commanded velocity on the
axis rises above 0.05 m/s after a quiet second; final = mean of the last 0.5 s before the next step (or before landing);
overshoot = peak − final (signed by the step direction); settle = time from onset to the last sample outside ±0.1 m of
final; ringing = re-entries into the band after the first entry; ramp = time for the COMMANDED velocity to return to
its final value (the commander's own velocity profile), so settle − ramp is the drone's lag behind the command."""
import json, sys
import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message

bag, drone = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else "drone_1")
csv_prefix = sys.argv[3] if len(sys.argv) > 3 else None      # optional: write <prefix>_odom.csv and <prefix>_cmd.csv for plotting
T_ODOM, T_SP, T_STATE = f"/{drone}/odometry_conversion/odometry", f"/{drone}/interface/mavros/setpoint_raw/local", f"/{drone}/interface/mavros/state"
BAND, MIN_STEP = 0.1, 0.5

r = rosbag2_py.SequentialReader()
r.open(rosbag2_py.StorageOptions(uri=bag, storage_id="mcap"), rosbag2_py.ConverterOptions("", ""))
types = {t.name: get_message(t.type) for t in r.get_all_topics_and_types()}
odom, sp, state = [], [], []
while r.has_next():
    topic, data, t = r.read_next()
    if topic == T_ODOM:
        m = deserialize_message(data, types[topic]); p = m.pose.pose.position; odom.append((t / 1e9, p.x, p.y, p.z))
    elif topic == T_SP:
        m = deserialize_message(data, types[topic]); sp.append((t / 1e9, m.position.x, m.position.y, m.position.z, m.velocity.x, m.velocity.y, m.velocity.z))
    elif topic == T_STATE:
        m = deserialize_message(data, types[topic]); state.append((t / 1e9, bool(m.armed), m.mode))
t0 = odom[0][0] if odom else 0.0
out = {"bag": bag, "drone": drone, "odom_msgs": len(odom), "setpoint_msgs": len(sp), "duration_s": round(odom[-1][0] - odom[0][0], 1) if len(odom) > 1 else None,
       "odom_rate_hz": round(len(odom) / (odom[-1][0] - odom[0][0]), 1) if len(odom) > 1 else None}

# arming windows from MAVROS state
arm_on = [t for i, (t, a, _) in enumerate(state) if a and (i == 0 or not state[i - 1][1])]
arm_off = [t for i, (t, a, _) in enumerate(state) if not a and i > 0 and state[i - 1][1]]
out["armed_at_s"] = [round(t - t0, 2) for t in arm_on]; out["disarmed_at_s"] = [round(t - t0, 2) for t in arm_off]
out["armed_at_end"] = state[-1][1] if state else None

# events: the commander publishes a VELOCITY setpoint (type_mask ignores position; frame 8 = body, but the drone
# does not yaw in this test so body x/y/z = world). An event starts when the commanded speed on an axis rises above
# 0.10 m/s after >= 0.8 s below 0.05 m/s (hover drift sits at ~0.02); the commander's ramp ends when the commanded
# speed falls back below 0.02 m/s. Events are then classified by order: first z-up after arming = takeoff, the
# horizontal one = step_x, the next z-up = step_z, the final z-down = landing. The drone's response is measured on
# the world axis that moved most.
QUIET, ONSET, DONE = 0.05, 0.10, 0.02
events = []
for ax in (1, 2, 3):
    v = [(s[0], s[3 + ax]) for s in sp]
    quiet_since = v[0][0] if v else 0.0
    i = 0
    while i < len(v):
        t, val = v[i]
        if abs(val) < QUIET:
            i += 1; continue
        if abs(val) >= ONSET and t - quiet_since >= 0.8:
            onset = v[i - 1][0] if i else t
            j = i
            while j < len(v) and (abs(v[j][1]) >= DONE or v[j][0] - onset < 0.3): j += 1
            ramp_end = v[min(j, len(v) - 1)][0]
            peak_v = max((x[1] for x in v[i:max(j, i + 1)]), key=abs)
            if ramp_end - onset > 0.3:
                events.append({"axis": ax, "onset": onset, "ramp_end": ramp_end, "peak_v": peak_v})
            i = j; quiet_since = v[min(j, len(v) - 1)][0]
        else:
            quiet_since = t; i += 1
events.sort(key=lambda e: e["onset"])
t_arm = arm_on[0] if arm_on else -1
named = []
seen_takeoff = seen_x = seen_z = False
TAKEOFF_PHASE_S = 15.0     # after arming: the climb plus the lateral leg from the pad to the hover point (2 m here)
for e in events:
    if t_arm >= 0 and 0 <= e["onset"] - t_arm < TAKEOFF_PHASE_S:
        if e["axis"] == 3 and e["peak_v"] > 0 and not seen_takeoff:
            e["name"] = "takeoff"; seen_takeoff = True
        else:
            e["name"] = f"takeoff_lateral_axis{e['axis']}"
    elif e["axis"] in (1, 2) and not seen_x:
        e["name"] = "step_x"; seen_x = True
    elif e["axis"] == 3 and e["peak_v"] > 0 and seen_takeoff and not seen_z:
        e["name"] = "step_z"; seen_z = True
    elif e["axis"] == 3 and e["peak_v"] < 0:
        e["name"] = "landing"
    else:
        e["name"] = f"other_axis{e['axis']}"
    named.append(e)

results = []
for k, e in enumerate(named):
    onset = e["onset"]
    later = [n["onset"] for n in named[k + 1:] if n["onset"] - onset >= 2.0]   # concurrent events don't end the window
    end = min(later[0] if later else onset + 8.0, onset + 8.0)
    win = [(t, x, y, z) for t, x, y, z in odom if onset <= t <= end]
    if len(win) < 20:
        continue
    if e["axis"] == 3:
        ax = 3                                      # vertical command: measure z
    else:
        deltas = [abs(win[-1][i] - win[0][i]) for i in (1, 2)]
        ax = deltas.index(max(deltas)) + 1          # horizontal command: the world axis that moved most
    seg = [(t - onset, w[ax - 1]) for t, *w in win]
    tail = [v for tt, v in seg if tt >= seg[-1][0] - 0.5]
    final = sum(tail) / len(tail); delta = final - seg[0][1]; sign = 1 if delta >= 0 else -1
    peak = max(v for _, v in seg) if sign > 0 else min(v for _, v in seg)
    overshoot = (peak - final) * sign
    inband = [abs(v - final) <= BAND for _, v in seg]
    last_out = max((i for i, b in enumerate(inband) if not b), default=-1)
    settle = seg[last_out][0] if last_out >= 0 else 0.0
    first_in = next((i for i, b in enumerate(inband) if b), None)
    reentries = sum(1 for i in range(1, len(inband)) if inband[i] and not inband[i - 1]) - (1 if first_in not in (None, 0) else 0)
    ramp = e["ramp_end"] - onset
    results.append({"name": e["name"], "axis": "xyz"[ax - 1], "onset_s_from_bag_start": round(onset - t0, 2),
                    "onset_s_after_arming": round(onset - t_arm, 2) if t_arm >= 0 else None,
                    "commanded_peak_speed_mps": round(abs(e["peak_v"]), 2), "moved_m": round(delta, 3), "final_m": round(final, 3),
                    "peak_m": round(peak, 3), "overshoot_m": round(overshoot, 3), "settle_s": round(settle, 2),
                    "commander_ramp_s": round(ramp, 2), "lag_after_ramp_s": round(settle - ramp, 2),
                    "band_reentries": max(reentries, 0), "samples": len(seg), "window_s": round(seg[-1][0], 2),
                    "saturated": settle >= seg[-1][0] - 0.3})
out["events"] = results
if csv_prefix:
    with open(csv_prefix + "_odom.csv", "w") as f:
        f.write("t_s,x,y,z\n"); f.writelines(f"{t - t0:.3f},{x:.4f},{y:.4f},{z:.4f}\n" for t, x, y, z in odom)
    with open(csv_prefix + "_cmd.csv", "w") as f:
        f.write("t_s,vx,vy,vz\n"); f.writelines(f"{s[0] - t0:.3f},{s[4]:.4f},{s[5]:.4f},{s[6]:.4f}\n" for s in sp)
    out["csv"] = [csv_prefix + "_odom.csv", csv_prefix + "_cmd.csv"]
print(json.dumps(out, indent=1))
