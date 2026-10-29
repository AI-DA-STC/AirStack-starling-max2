# tools/tests/test_keymap.py — keyboard teleop: keys -> a gamepad's /joy axes (NEAR-789, sim)
import pathlib, re, sys, unittest
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "teleop"))
import keymap as K

CONTROLLERS = HERE.parents[1] / "AirStack/robot/ros_ws/src/svg_ground_control/svg_ground_control/safe_teleop/controllers.py"


def axes(state, t=1.05):
    return state.axes(t)


def cmu_deadzone(value, width=0.15):
    """CMU's safe_teleop/velocity.py deadzone(), copied: what the drone gets from a stick value."""
    if abs(value) < width:
        return 0.0
    return (abs(value) - width) / (1.0 - width) * (1.0 if value > 0 else -1.0)


class Layout(unittest.TestCase):
    def test_profiles_use_cmus_axis_numbers(self):
        src = CONTROLLERS.read_text()
        for name, prof in K.PROFILES.items():
            block = src[src.index("name='%s'" % name):]
            for field in ("forward_axis", "left_axis", "climb_axis", "yaw_axis", "lock_button"):
                cmu = int(re.search(field + r"=(\d+)", block).group(1))
                self.assertEqual(getattr(prof, field), cmu, (name, field))

    def test_nothing_held_is_all_zero_and_wide_enough(self):
        s = K.KeyState("dragonrise_usb")
        a = axes(s)
        self.assertEqual(set(a), {0.0}); self.assertGreaterEqual(len(a), 8)
        self.assertEqual(set(s.buttons()), {0}); self.assertGreaterEqual(len(s.buttons()), 15)


class Keys(unittest.TestCase):
    def setUp(self):
        self.s = K.KeyState("dragonrise_usb", scale=1.0)
        self.p = K.PROFILES["dragonrise_usb"]

    def held(self, *keys):
        for k in keys:
            self.s.press(k, 1.0)
        return axes(self.s)

    def test_mode2_layout_follows_the_stick_conventions(self):
        cases = {"Up": (self.p.forward_axis, 1.0), "Down": (self.p.forward_axis, -1.0),
                 "Left": (self.p.left_axis, 1.0), "Right": (self.p.left_axis, -1.0),
                 "w": (self.p.climb_axis, 1.0), "s": (self.p.climb_axis, -1.0),
                 "a": (self.p.yaw_axis, 1.0), "d": (self.p.yaw_axis, -1.0),
                 "Shift_L": (self.p.climb_axis, 1.0), "Control_L": (self.p.climb_axis, -1.0),
                 "Shift_R": (self.p.climb_axis, 1.0), "Control_R": (self.p.climb_axis, -1.0),
                 "q": (self.p.yaw_axis, 1.0), "e": (self.p.yaw_axis, -1.0)}
        for key, (idx, val) in cases.items():
            s = K.KeyState("dragonrise_usb", scale=1.0); s.press(key, 1.0)
            a = s.axes(1.05)
            self.assertEqual(a[idx], val, key)
            self.assertEqual(sum(1 for v in a if v), 1, key)

    def test_alias_and_main_key_together_never_exceed_full_stick(self):
        self.assertEqual(self.held("w", "Shift_L")[self.p.climb_axis], 1.0)
        s = K.KeyState("dragonrise_usb", scale=1.0); s.press("a", 1.0); s.press("e", 1.0)
        self.assertEqual(s.axes(1.05)[self.p.yaw_axis], 0.0)                  # opposite directions cancel

    def test_uppercase_from_a_held_shift_is_the_same_key(self):
        a = self.held("Shift_L", "A")                       # Shift held turns "a" into "A": still turn left
        self.assertEqual(a[self.p.yaw_axis], 1.0); self.assertEqual(a[self.p.climb_axis], 1.0)
        self.s.release("A", 2.0)
        self.assertEqual(axes(self.s, 3.0)[self.p.yaw_axis], 0.0)

    def test_opposite_keys_cancel(self):
        self.assertEqual(self.held("Up", "Down")[self.p.forward_axis], 0.0)

    def test_scale_keys_set_the_stick_amount(self):
        s = K.KeyState("dragonrise_usb")
        f = self.p.forward_axis
        s.press("Up", 1.0); self.assertAlmostEqual(cmu_deadzone(s.axes(1.05)[f]), 0.5)        # default 50 % of top speed
        s.press("1", 1.0); self.assertAlmostEqual(cmu_deadzone(s.axes(1.05)[f]), 0.25)
        s.press("3", 1.0); self.assertAlmostEqual(cmu_deadzone(s.axes(1.05)[f]), 1.0)
        self.assertEqual(s.scale, 1.0)

    def test_unknown_keys_do_nothing(self):
        self.assertEqual(set(self.held("x", "F5", "space")), {0.0})


class Speed(unittest.TestCase):
    def test_compensates_safe_teleops_dead_zone_on_every_axis(self):
        for key in ("Up", "Left", "w", "a"):
            for width in (0.15, 0.3):
                s = K.KeyState("dragonrise_usb", scale=0.25, deadzone=width); s.press(key, 1.0)
                v = [x for x in s.axes(1.05) if x][0]
                self.assertAlmostEqual(abs(cmu_deadzone(v, width)), 0.25, msg=(key, width))

    def test_diagonal_is_no_faster_than_straight(self):
        s = K.KeyState("dragonrise_usb", scale=1.0); s.press("Up", 1.0); s.press("Left", 1.0)
        p = K.PROFILES["dragonrise_usb"]; a = s.axes(1.05)
        speed = (cmu_deadzone(a[p.forward_axis]) ** 2 + cmu_deadzone(a[p.left_axis]) ** 2) ** 0.5
        self.assertAlmostEqual(speed, 1.0, places=6)


class Safety(unittest.TestCase):
    def test_autorepeat_release_press_pair_does_not_drop_the_key(self):
        s = K.KeyState("dragonrise_usb", scale=1.0); f = K.PROFILES["dragonrise_usb"].forward_axis
        s.press("Up", 1.000); s.release("Up", 1.500); s.press("Up", 1.505)        # X11 autorepeat: release+press 5 ms apart
        self.assertEqual(s.axes(1.6)[f], 1.0)

    def test_a_real_release_takes_effect_after_the_debounce(self):
        s = K.KeyState("dragonrise_usb", scale=1.0); f = K.PROFILES["dragonrise_usb"].forward_axis
        s.press("Up", 1.0); s.release("Up", 2.0)
        self.assertEqual(s.axes(2.0 + K.DEBOUNCE_S / 2)[f], 1.0)                 # might still be autorepeat
        self.assertEqual(s.axes(2.0 + K.DEBOUNCE_S * 1.5)[f], 0.0)               # it was a real release

    def test_a_key_with_no_event_for_a_second_counts_as_released(self):
        # Alt-Tab or a grab can swallow both the release and FocusOut; a held key always auto-repeats (500 ms delay)
        s = K.KeyState("dragonrise_usb", scale=1.0); f = K.PROFILES["dragonrise_usb"].forward_axis
        s.press("Up", 1.0)
        self.assertNotEqual(s.axes(1.0 + K.HOLD_SILENCE_S * 0.9)[f], 0.0)
        self.assertEqual(s.axes(1.0 + K.HOLD_SILENCE_S + 0.01)[f], 0.0)

    def test_auto_repeat_keeps_a_held_key_alive_past_the_silence_limit(self):
        s = K.KeyState("dragonrise_usb", scale=1.0); f = K.PROFILES["dragonrise_usb"].forward_axis
        s.press("Up", 1.0); t = 1.5
        while t < 4.0:                                       # X11 repeat: release+press every 30 ms after 500 ms
            s.release("Up", t); s.press("Up", t + 0.001); t += 0.03
        self.assertNotEqual(s.axes(4.0)[f], 0.0)

    def test_focus_loss_releases_every_key_at_once(self):
        s = K.KeyState("dragonrise_usb", scale=1.0)
        for k in ("w", "a", "q", "Shift_L"):
            s.press(k, 1.0)
        s.all_up()
        self.assertEqual(set(s.axes(1.0)), {0.0})

    def test_status_line_names_held_keys_and_scale(self):
        s = K.KeyState("dragonrise_usb"); s.press("Up", 1.0); s.press("w", 1.0)
        line = s.status(1.1)
        self.assertIn("forward", line); self.assertIn("up", line); self.assertIn("50 %", line); self.assertIn("top speed", line)


if __name__ == "__main__":
    unittest.main()


class WindowSource(unittest.TestCase):
    """key_teleop.py needs rclpy + Tk (container only), so its safety wiring is pinned by source checks."""
    SRC = (HERE.parent / "teleop" / "key_teleop.py").read_text()

    def test_rclpy_does_not_install_its_own_signal_handlers(self):
        # rclpy's handler invalidated the publisher under an open window on SIGTERM (found 2026-10-30)
        self.assertIn("rclpy.init(signal_handler_options=SignalHandlerOptions.NO)", self.SRC)
        self.assertIn("signal.signal(signal.SIGTERM", self.SRC); self.assertIn("signal.signal(signal.SIGINT", self.SRC)

    def test_focus_loss_and_close_release_every_key_and_publish_zeros(self):
        self.assertIn('root.bind("<FocusOut>", lambda e: state.all_up())', self.SRC)
        close = self.SRC[self.SRC.index("def close():"):self.SRC.index("root.protocol(")]
        self.assertIn("state.all_up()", close); self.assertIn("publish([0.0] * K.N_AXES)", close)

    def test_publishes_faster_than_safe_teleops_half_second_timeout(self):
        rate = float(re.search(r"RATE_HZ = ([0-9.]+)", self.SRC).group(1))
        self.assertGreaterEqual(rate, 10.0)


class WindowReviewFixes(unittest.TestCase):
    """Safety review 2026-10-30 of key_teleop.py (container-only, so source checks)."""
    SRC = (HERE.parent / "teleop" / "key_teleop.py").read_text()

    def test_reads_the_live_safe_teleop_profile_and_dead_zone_and_refuses_a_mismatch(self):
        self.assertIn("/safe_teleop/get_parameters", self.SRC)
        self.assertIn('"teleop_controller"', self.SRC); self.assertIn('"deadzone"', self.SRC)
        self.assertRegex(self.SRC, r"controller != a\.profile[\s\S]{0,400}return 2")

    def test_counts_other_publishers_after_discovery_and_every_second(self):
        disc = self.SRC.index("time.monotonic() + DISCOVERY_S")
        self.assertIn("rclpy.spin_once(node", self.SRC[disc:disc + 200])               # discovery spins first
        tick = self.SRC[self.SRC.index("def tick():"):self.SRC.index("def close():")]
        self.assertIn("count_publishers", tick)                                      # then counts every second
        self.assertLess(disc, self.SRC.index("root.after(0, tick)"))

    def test_minimising_releases_every_key(self):
        self.assertIn('root.bind("<Unmap>", lambda e: state.all_up())', self.SRC)

    def test_an_error_in_the_loop_publishes_zeros_and_closes(self):
        tick = self.SRC[self.SRC.index("def tick():"):self.SRC.index("def close():")]
        self.assertRegex(tick, r"except Exception[\s\S]{0,300}close\(\)")
