# tools/tests/test_teleop_frame.py
import math, pathlib, sys, unittest
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "teleop"))
import frame as F

class Rotation(unittest.TestCase):
    def test_four_headings(self):
        for yaw, want in ((0.0, (1.0, 0.0)), (math.pi/2, (0.0, 1.0)), (math.pi, (-1.0, 0.0)), (-math.pi/2, (0.0, -1.0))):
            vx, vy = F.rotate_body_to_world(1.0, 0.0, yaw)
            self.assertAlmostEqual(vx, want[0], 6, yaw); self.assertAlmostEqual(vy, want[1], 6, yaw)
    def test_left_key_at_heading_180_slides_to_room_right(self):
        vx, vy = F.rotate_body_to_world(0.0, 1.0, math.pi)
        self.assertAlmostEqual(vx, 0.0, 6); self.assertAlmostEqual(vy, -1.0, 6)
    def test_unfilled_quaternion_is_no_heading(self):
        self.assertTrue(math.isnan(F.yaw_from_quat(0, 0, 0, 0)))
        self.assertAlmostEqual(F.yaw_from_quat(0, 0, math.sin(0.25), math.cos(0.25)), 0.5, 6)
    def test_heading_deg_is_operator_convention(self):
        self.assertAlmostEqual(F.heading_deg_from_yaw(0.0), 0.0, 6)
        self.assertAlmostEqual(F.heading_deg_from_yaw(math.pi/2), 270.0, 6)   # nose on +Y (ENU) = 270 clockwise from +X
        self.assertTrue(math.isnan(F.heading_deg_from_yaw(math.nan)))

class Modes(unittest.TestCase):
    def fresh(self, mode="body"):
        s = F.FrameState(mode=mode); s.update_heading(math.pi, 10.0); return s
    def test_body_rotates_world_passes_through(self):
        s = self.fresh()
        vx, vy, vz, yr = s.command(1.0, 0.0, 0.3, 0.7, 10.05)
        self.assertAlmostEqual(vx, -1.0, 6); self.assertAlmostEqual(vy, 0.0, 6); self.assertEqual((vz, yr), (0.3, 0.7))
        w = self.fresh("world"); self.assertEqual(w.command(1.0, 0.0, 0.3, 0.7, 10.05), (1.0, 0.0, 0.3, 0.7))
    def test_flip_waits_until_centred(self):
        s = self.fresh(); s.command(1.0, 0.0, 0, 0, 10.05); s.request_mode("world")
        self.assertEqual(s.status(10.06)["pending"], "world")
        vx, _, _, _ = s.command(1.0, 0.0, 0, 0, 10.1); self.assertAlmostEqual(vx, -1.0, 6)      # still body
        s.command(0.0, 0.0, 0, 0, 10.15)                                                         # centred: flip applies
        self.assertEqual(s.status(10.16)["frame"], "world"); self.assertEqual(s.status(10.16)["pending"], "none")
        self.assertEqual(s.command(1.0, 0.0, 0, 0, 10.2)[0], 1.0)
    def test_two_f_presses_while_held_cancel(self):
        s = self.fresh(); s.command(1.0, 0, 0, 0, 10.05); s.request_mode("world"); s.request_mode("body")
        self.assertEqual(s.status(10.06)["pending"], "none"); s.command(0, 0, 0, 0, 10.1)
        self.assertEqual(s.status(10.11)["frame"], "body")
    def test_unknown_mode_rejected(self):
        with self.assertRaises(ValueError): F.FrameState().request_mode("nose")

class Guard(unittest.TestCase):
    def test_stale_heading_zeroes_horizontal_keeps_vz_and_yaw(self):
        s = F.FrameState(); s.update_heading(0.0, 10.0)
        self.assertEqual(s.command(1.0, 0.5, 0.3, 0.7, 10.5), (0.0, 0.0, 0.3, 0.7)); self.assertEqual(s.status(10.5)["guard"], "stale")
    def test_stale_trip_stays_latched_until_centred(self):
        s = F.FrameState(); s.update_heading(0.0, 10.0)
        self.assertEqual(s.command(1.0, 0, 0, 0, 10.5)[:2], (0.0, 0.0))
        s.update_heading(0.0, 10.6)                                                       # fresh again, key still held
        self.assertEqual(s.command(1.0, 0, 0, 0, 10.61)[:2], (0.0, 0.0)); self.assertEqual(s.status(10.61)["guard"], "stale")
        s.command(0.0, 0.0, 0, 0, 10.65); s.update_heading(0.0, 10.7)
        self.assertEqual(s.status(10.71)["guard"], "ok"); self.assertEqual(s.command(1.0, 0, 0, 0, 10.72)[0], 1.0)

    def test_normal_sample_gap_does_not_trip(self):
        s = F.FrameState(); s.update_heading(0.0, 10.0); s.update_heading(0.03, 10.1)
        self.assertEqual(s.command(1.0, 0.0, 0, 0, 10.15)[0], 1.0 * math.cos(0.03)); self.assertEqual(s.status(10.15)["guard"], "ok")
    def test_jump_trips_and_rearms_only_when_centred_and_steady(self):
        s = F.FrameState(); s.update_heading(0.0, 10.0); s.update_heading(3.1, 10.05)
        self.assertEqual(s.command(1.0, 0, 0, 0, 10.06)[:2], (0.0, 0.0)); self.assertEqual(s.status(10.06)["guard"], "jump")
        s.update_heading(3.1, 10.1); s.update_heading(3.1, 10.15)
        self.assertEqual(s.command(1.0, 0, 0, 0, 10.16)[:2], (0.0, 0.0))                  # steady but not centred: still tripped
        s.command(0.0, 0.0, 0, 0, 10.2); s.update_heading(3.1, 10.25); s.command(0.0, 0.0, 0, 0, 10.26)
        self.assertEqual(s.status(10.27)["guard"], "ok"); self.assertNotEqual(s.command(1.0, 0, 0, 0, 10.3)[0], 0.0)
    def test_wraparound_is_not_a_jump(self):
        s = F.FrameState(); s.update_heading(math.pi - 0.01, 10.0); s.update_heading(-math.pi + 0.01, 10.05)
        self.assertEqual(s.status(10.06)["guard"], "ok")
    def test_world_mode_never_trips(self):
        s = F.FrameState(mode="world"); s.update_heading(0.0, 10.0); s.update_heading(3.1, 10.05)
        self.assertEqual(s.command(1.0, 0, 0, 0, 12.0), (1.0, 0.0, 0.0, 0.0)); self.assertEqual(s.status(12.0)["guard"], "ok")

class Status(unittest.TestCase):
    def test_status_line_format_and_input_silence(self):
        s = F.FrameState(); s.update_heading(0.0, 10.0); s.command(0, 0, 0, 0, 10.0)
        self.assertEqual(s.status_line(10.1), "frame=body pending=none heading_deg=0.0 heading_age_s=0.10 guard=ok input=ok")
        self.assertEqual(s.status(11.5)["input"], "none")
        n = F.FrameState(); self.assertEqual(n.status(0.0)["input"], "none"); self.assertTrue(math.isnan(n.status(0.0)["heading_deg"]))
