#!/usr/bin/env python3
"""Parse `ros2 topic echo --field pose.pose.position` output (x:/y:/z:/--- blocks, ~40 Hz) and
report a step response on one axis. Measured against the SETTLED value (mean of the last 0.5 s),
because the odometry frame (PX4 local) and the commander's goal frame differ by the configured
position offset, so "distance to target" would be frame-dependent.
Usage: analyze_step.py <trace.txt> <axis x|y|z> <commanded delta m> [hz=40]"""
import sys, re
path, axis, delta = sys.argv[1], sys.argv[2], float(sys.argv[3])
hz = float(sys.argv[4]) if len(sys.argv) > 4 else 40.0
vals = [float(m.group(1)) for m in re.finditer(rf"^{axis}:\s*([-\d.eE+]+)", open(path).read(), re.M)]
if len(vals) < 40:
    print(f"{path}: only {len(vals)} samples"); sys.exit(1)
start, final = vals[0], sum(vals[-20:]) / 20
moved = final - start
peak = max(vals) if delta > 0 else min(vals)
overshoot = (peak - final) if delta > 0 else (final - peak)
band = 0.1
last_out = max((i for i, v in enumerate(vals) if abs(v - final) > band), default=-1)
settle = (last_out + 1) / hz
print(f"{path} axis={axis}: {len(vals)} samples ({len(vals)/hz:.1f} s) | moved {moved:+.3f} m of {delta:+.1f} commanded "
      f"(trace starts after the command, so this is a lower bound) | peak {peak:+.3f} | "
      f"overshoot past settled {overshoot:+.3f} m | settled (±{band} m) after {settle:.2f} s")
