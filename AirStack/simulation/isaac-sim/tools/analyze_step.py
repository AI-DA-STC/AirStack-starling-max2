#!/usr/bin/env python3
"""Parse `ros2 topic echo --field pose.pose.position` output (x:/y:/z:/--- blocks, ~40 Hz)
and report the step response on the given axis: start, final, target, overshoot, settle time."""
import sys, re
path, axis, target_delta = sys.argv[1], sys.argv[2], float(sys.argv[3])
vals = [float(m.group(1)) for m in re.finditer(rf"^{axis}:\s*([-\d.eE+]+)", open(path).read(), re.M)]
if len(vals) < 10:
    print(f"{path}: only {len(vals)} samples"); sys.exit(1)
hz = 40.0
start = vals[0]; target = start + target_delta
final = sum(vals[-20:]) / 20
overshoot = (max(vals) - target) if target_delta > 0 else (target - min(vals))
band = 0.1
settle_idx = next((i for i in range(len(vals)) if all(abs(v - target) < band for v in vals[i:])), None)
print(f"{path} axis={axis}: samples={len(vals)} ({len(vals)/hz:.1f} s)  start={start:+.3f}  target={target:+.3f}  "
      f"final={final:+.3f}  err={final-target:+.3f}  overshoot={overshoot:+.3f} m  "
      f"settle(<0.1 m)={'%.2f s' % (settle_idx/hz) if settle_idx is not None else 'NOT within window'}")
