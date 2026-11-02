# tools/tests/test_teleop_frame_gates.py
"""tools/sim_tests/teleop_frame: gates on a synthetic run folder (live metrics.csv in wall time + fly.sh's push stamps +
odom_hz.txt), fly.sh --check, static fly.sh checks, the five-file contract. Sim-only (iron rule 9). No docker, no ROS.

Heading convention, used the same way in fly.sh, gates.py and here:
  operator heading h (fly.sh's stamps `heading=<deg>`, the relay's status line): 0 = +X, CLOCKWISE positive, [0, 360)
  ENU yaw psi (metrics.csv `heading_deg`, odometry):                             0 = +X, counter-clockwise positive
  psi = -h, so the nose at heading h points along (cos(-h), sin(-h)) in ENU:
    h 0 -> +X, h 90 -> -Y, h 180 -> -X, h 270 -> +Y.
A Drive-mode (BODY) forward push at heading 90 therefore moves the drone along -Y; +Y at heading 90 is a sign error."""
import contextlib
import importlib.util
import io
import math
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
TOOLS = HERE.parent
for p in (HERE, TOOLS, TOOLS / "live", TOOLS / "lib"):
    sys.path.insert(0, str(p))
import contract_check  # noqa: E402
import metrics_core as M  # noqa: E402
import report as R  # noqa: E402

TF = TOOLS / "sim_tests" / "teleop_frame"
FIX = HERE / "fixtures" / "run1"
T0_UNIX = 1_800_000_000.0
HZ = 40.0
MOVE_M = 0.9                       # 0.25 x 2.0 m/s for 2 s, a little short of 1.0 m (lag)


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def nose(h_deg):
    """ENU unit vector of the nose at operator heading h (clockwise from +X)."""
    psi = math.radians(-h_deg)
    return (math.cos(psi), math.sin(psi))


def pushes(moves=None, drift=None, skip=()):
    """[(label, heading h, (dx, dy) during the push, (dx, dy) after the release)]: the good flight unless overridden.
    Drive-mode pushes move along the nose; the Room-mode push at heading 180 moves along +X (not the nose, -X)."""
    out = []
    for lab, h in (("0", 0), ("90", 90), ("180", 180), ("270", 270), ("world", 180)):
        if lab in skip:
            continue
        u = (1.0, 0.0) if lab == "world" else nose(h)
        d = (moves or {}).get(lab, (MOVE_M * u[0], MOVE_M * u[1]))
        out.append((lab, h, d, (drift or {}).get(lab, (0.0, 0.0))))
    return out


def make_run(tmp, moves=None, drift=None, skip=(), relay_line="relay: stick_frame=body", odom_hz="average rate: 40.012",
             unreleased=None):
    tmp = pathlib.Path(tmp)
    out, heavy = tmp / "run", tmp / "heavy"
    out.mkdir()
    (heavy / "teleop_frame_2026_11_03-12_00_00").mkdir(parents=True)
    (heavy / "teleop_frame_2026_11_03-12_00_00" / "metadata.yaml").write_text("rosbag2_bagfile_information: {}\n")
    TM = _load("tf_metrics_t", TF / "metrics.py")
    cols = M.csv_columns(TM.SERIES)
    meta = {"offsets": [0.0, 0.0, 0.0], "t0_unix": repr(T0_UNIX), "trigger": "drone_1", "drones": "drone_1",
            "teleop_max_speed_mps": 2.0}
    # timeline (t_s from t0): phase 1 from 2 s, phase 2 from 5 s, push k onset at 10 + 15 k, 2 s long, phase 3 last 5 s
    plan = pushes(moves, drift, skip)
    segs, lines = [], ["[12:00:00] takeoff: success=True, message='ok'"]
    if relay_line:
        lines.append("[12:00:01] " + relay_line)
    for k, (lab, h, d, dr) in enumerate(plan):
        on = 10.0 + 15.0 * k
        segs.append((on, on + 2.0, h, d, dr))
        lines.append("[%.6f] push %s onset heading=%.1f" % (T0_UNIX + on, lab, h))
        if lab != unreleased:
            lines.append("[%.6f] push %s release heading=%.1f" % (T0_UNIX + on + 2.0, lab, h))
    t_end = 10.0 + 15.0 * len(plan) + 5.0
    lines.append("[12:02:00] landed: drone_1 IDLE")
    (out / "test_stdout.log").write_text("\n".join(lines) + "\n")

    def state(t):
        x = y = 0.0
        h = 0.0
        for on, rel, hh, d, dr in segs:
            if t < on - 6.0:                        # the yaw to this push's heading happens in the gap before it
                break
            h = hh
            f = min(max((t - on) / (rel - on), 0.0), 1.0)
            g = min(max((t - rel) / 1.5, 0.0), 1.0)          # post-release drift over 1.5 s
            x += d[0] * f + dr[0] * g
            y += d[1] * f + dr[1] * g
        return x, y, h

    rows = []
    n = int(round((t_end + 5.0) * HZ))
    for i in range(n + 1):
        t = i / HZ
        ph = 0 if t < 2 else 1 if t < 5 else 2 if t < t_end else 3
        x, y, h = state(t)
        psi = -h
        vals = {"heading_deg": (psi + 180.0) % 360.0 - 180.0, "x_m": x, "y_m": y,
                "xy_drift_m": math.hypot(x, y) if ph >= 2 else math.nan, "speed_drone_1": 0.0,
                "fence_breached": 0.0, "emergency": 0.0}
        rows.append(M.format_row(t, ph, vals, cols))
    (out / "metrics.csv").write_text(M.csv_header(TM.SERIES, meta) + "\n".join(rows) + "\n")
    shutil.copy(out / "metrics.csv", out / "metrics_bag.csv")
    if odom_hz is not None:
        (out / "odom_hz.txt").write_text(odom_hz + "\n")
    shutil.copy(FIX / "res_watch.log", out / "res_watch.log")
    (out / "armed_post.txt").write_text("drone_1 armed: false\n")
    (out / "landing_evidence.txt").write_text("[swarm_commander-2] drone_1: landed, disarmed (attempt 1)\n")
    (out / "isaac_evidence.txt").write_text("model_line=1 starling_cfg=1 autostart=1 unknown_model=0 cooking=0 ready=1\n")
    (out / "ulog_sysid_map.txt").write_text("2 /x.ulg 100\n")
    (out / "run_meta.txt").write_text("head_short=abc1234\ndirty_tools=0\nstarted=2026-11-03T12:00:00\ntz=+08\nnum_robots=1\nfly_args=0.25 2.0\n")
    env = R.parse_env(TF / "test.env")
    return out, heavy, env


def build(**kw):
    with tempfile.TemporaryDirectory() as d:
        out, heavy, env = make_run(d, **kw)
        G = _load("tf_gates_t", TF / "gates.py")
        rows, ctx = G.build_rows(out, heavy, env)
        return G, rows, ctx


def v(rows, prefix):
    return next(r.verdict for r in rows if r.check.startswith(prefix))


def m(rows, prefix):
    return next(r.measured for r in rows if r.check.startswith(prefix))


def failing(rows):
    return [(r.check, r.verdict, r.measured) for r in rows if r.gate and r.verdict != "PASS"]


class TeleopFrameGates(unittest.TestCase):
    def test_good_flight_passes(self):
        _, rows, ctx = build()
        self.assertEqual(R.overall_verdict(rows), "PASS", failing(rows))
        for lab in ("0", "90", "180", "270"):
            self.assertEqual(v(rows, "push %s: direction" % lab), "PASS")
            self.assertEqual(v(rows, "push %s: moved" % lab), "PASS")
            self.assertEqual(v(rows, "push %s: parked" % lab), "PASS")
        self.assertEqual(v(rows, "push world: direction"), "PASS")
        self.assertEqual(v(rows, "relay stick_frame recorded"), "PASS")
        self.assertEqual(v(rows, "odometry rate"), "PASS")
        self.assertIn("°", R.headline_text(rows, ctx))

    def test_push_at_90_along_minus_y_is_the_nose(self):
        # heading 90 (operator, clockwise) = ENU yaw -90 deg: the nose points along -Y
        _, rows, _ = build(moves={"90": (0.0, -0.25)})
        self.assertEqual(v(rows, "push 90: direction"), "PASS")
        self.assertEqual(v(rows, "push 90: moved"), "PASS")

    def test_push_at_90_along_plus_x_fails_direction(self):          # Room-mode behaviour in Drive mode
        _, rows, _ = build(moves={"90": (0.9, 0.0)})
        self.assertEqual(v(rows, "push 90: direction"), "FAIL")
        self.assertEqual(R.overall_verdict(rows), "FAIL")
        self.assertIn("90", m(rows, "push 90: direction"))

    def test_push_at_90_along_plus_y_fails_direction(self):          # the yaw-sign error (ENU yaw taken as +h)
        _, rows, _ = build(moves={"90": (0.0, 0.9)})
        self.assertEqual(v(rows, "push 90: direction"), "FAIL")

    def test_world_push_along_the_nose_fails(self):                  # the relay ignored the flip to Room mode
        _, rows, _ = build(moves={"world": (-0.9, 0.0)})
        self.assertEqual(v(rows, "push world: direction"), "FAIL")

    def test_short_push_fails_moved_and_leaves_direction_unverified(self):
        _, rows, _ = build(moves={"180": (-0.05, 0.0)})
        self.assertEqual(v(rows, "push 180: moved"), "FAIL")
        self.assertEqual(v(rows, "push 180: direction"), "UNVERIFIED")

    def test_drift_after_release_fails_parked(self):
        _, rows, _ = build(drift={"270": (0.0, 0.5)})
        self.assertEqual(v(rows, "push 270: parked"), "FAIL")
        self.assertEqual(v(rows, "push 270: direction"), "PASS")

    def test_missing_relay_line_is_incomplete(self):
        _, rows, _ = build(relay_line=None)
        self.assertEqual(v(rows, "relay stick_frame recorded"), "UNVERIFIED")
        self.assertEqual(R.overall_verdict(rows), "INCOMPLETE", failing(rows))

    def test_relay_started_in_world_fails(self):
        _, rows, _ = build(relay_line="relay: stick_frame=world")
        self.assertEqual(v(rows, "relay stick_frame recorded"), "FAIL")

    def test_slow_odometry_is_incomplete(self):
        _, rows, _ = build(odom_hz="average rate: 8.000")
        self.assertEqual(v(rows, "odometry rate"), "UNVERIFIED")
        self.assertEqual(R.overall_verdict(rows), "INCOMPLETE", failing(rows))

    def test_missing_odom_hz_is_incomplete(self):
        _, rows, _ = build(odom_hz=None)
        self.assertEqual(v(rows, "odometry rate"), "UNVERIFIED")

    def test_missing_push_is_incomplete_not_pass(self):
        _, rows, _ = build(skip=("270",))
        self.assertEqual(v(rows, "push 270: direction"), "UNVERIFIED")
        self.assertEqual(v(rows, "pushes flown"), "UNVERIFIED")
        self.assertEqual(R.overall_verdict(rows), "INCOMPLETE", failing(rows))

    def test_unreleased_push_never_passes(self):
        _, rows, _ = build(unreleased="world")
        self.assertEqual(v(rows, "push world: direction"), "UNVERIFIED")
        self.assertNotEqual(R.overall_verdict(rows), "PASS")

    def test_missing_metrics_is_unverified_not_a_crash(self):
        with tempfile.TemporaryDirectory() as d:
            out, heavy, env = make_run(d)
            (out / "metrics.csv").unlink()
            G = _load("tf_gates_t2", TF / "gates.py")
            rows, _ = G.build_rows(out, heavy, env)
        self.assertEqual(v(rows, "push 0: direction"), "UNVERIFIED")
        self.assertEqual(R.overall_verdict(rows), "INCOMPLETE")

    def test_caption_and_ledger_sentence(self):
        G, rows, ctx = build()
        s = G.ledger_sentence(rows, ctx, R.overall_verdict(rows))
        self.assertIn("PASS", s); self.assertIn("teleop_single_ours.yaml", s)
        cap = G.figure_caption(ctx)
        self.assertTrue(0 < len(cap) <= 380, len(cap))
        self.assertIn("Figure 1", ctx["reading"])

    def test_report_renders_a_record(self):
        with tempfile.TemporaryDirectory() as d:
            out, heavy, env = make_run(d)
            with contextlib.redirect_stdout(io.StringIO()):
                rc = R.main([str(TF), str(out), "--heavy", str(heavy), "--no-verdict-log", "--ledger", "32", "--issue", "NEAR-789"])
            text = (out.parent / "run_record.md").read_text()
        self.assertEqual(rc, 0)
        self.assertIn("| push 90: direction", text); self.assertIn("NEAR-789", text)


class FlyScript(unittest.TestCase):
    def check(self, *args):
        return subprocess.run(["bash", str(TF / "fly.sh"), "--check", *args], capture_output=True, text=True)

    def test_check_accepts_the_test_env_args(self):
        r = self.check("4", "0.25", "2.0")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("arguments ok", r.stdout)

    def test_check_rejects_bad_args(self):
        for args in (("4", "1.5", "2.0"), ("4", "0", "2.0"), ("4", "0.25", "0"), ("4", "0.25", "-1"), ("x", "0.25", "2.0"),
                     ("4", "0.25", "2.0", "9")):
            r = self.check(*args)
            self.assertEqual(r.returncode, 2, args)
            self.assertIn("fly.sh:", r.stderr)

    def test_static_flow(self):                                          # no ROS on the host: read the script
        src = (TF / "fly.sh").read_text()
        for n in ("# fly-check: yes", "/svg/drone_1/teleop_command_stick", "TwistStamped", "finally", "SIGTERM",
                  "SignalHandlerOptions.NO", '"$HERE/teleop_frame.py" --drone drone_1 --stick-frame body', "trap ",
                  "relay: stick_frame=", "/teleop_frame/status", "SetParameters", "stick_frame", "teleop_max_speed_mps",
                  "heading_deg_from_yaw", "push world", "onset", "release", "landed:", 'frame_id = "map"', "kill "):
            self.assertIn(n, src, n)
        self.assertRegex(src, r'python3 - [^\n]*fly\.sh')                # sim.sh's stop_fly (pkill -f fly\.sh) stops it too
        self.assertEqual(subprocess.run(["bash", "-n", str(TF / "fly.sh")]).returncode, 0)

    def test_the_embedded_program_compiles(self):
        src = (TF / "fly.sh").read_text()
        py = src.split("<<'PY'\n", 1)[1].split("\nPY\n", 1)[0]
        compile(py, "fly.sh<<PY", "exec")


class Contract(unittest.TestCase):
    def test_contract(self):
        self.assertEqual(contract_check.check(TF), [])

    def test_env_values(self):
        env = R.parse_env(TF / "test.env")
        want = {"ISSUE": "NEAR-789", "MILESTONE": "S5", "CONFIG": "teleop_single_ours.yaml", "SCENARIO": "hover",
                "BAG_PREFIX": "teleop_frame", "NUM_ROBOTS": "1", "USE_STUDIO": "false", "DURATION_S": "4",
                "FLY_ARGS": "0.25 2.0", "FLY_TIMEOUT_S": "600", "BASELINE": "none (first run sets it)",
                "TITLE": "one-drone teleop frame: a forward push follows the nose (Drive mode) and +X (Room mode)"}
        for k, val in want.items():
            self.assertEqual(env.get(k), val, k)
        self.assertIn("iron rule 9", (TF / "test.env").read_text())
        self.assertIn("safe_teleop", env["SCOPE"])


if __name__ == "__main__":
    unittest.main()
