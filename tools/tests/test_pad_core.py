# tools/tests/test_pad_core.py — the F310 pad check's decisions (tools/teleop/pad_core.py), no ROS.
import pathlib, re, sys, unittest
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "teleop"))
import pad_core as P

FIX = HERE / "fixtures" / "pad"
CONTROLLERS = HERE.parents[1] / "AirStack/robot/ros_ws/src/svg_ground_control/svg_ground_control/safe_teleop/controllers.py"
REST = [0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 0.0, 0.0]


def devs(name):
    return P.parse_input_devices((FIX / name).read_text())


def sample(t=0.0, **axes_and_buttons):
    """An F310 X-mode /joy sample at rest, with a<i>=value and b<i>=1 overrides."""
    a, b = list(REST), [0] * 11
    for k, v in axes_and_buttons.items():
        (a if k[0] == "a" else b)[int(k[1:])] = v
    return {"t": t, "axes": a, "buttons": b}


def cmu_xbox_mapping():
    """CMU's xbox_usb profile read from controllers.py by regex (as tools/tests/test_keymap.py does)."""
    src = CONTROLLERS.read_text()
    block = src[src.index("name='xbox_usb'"):]
    block = block[:block.index("\n)")]
    m = {}
    for f in ("forward_axis", "left_axis", "climb_axis", "yaw_axis", "lock_button"):
        m[f] = int(re.search(f + r"=(\d+)", block).group(1))
    for f in ("forward_sign", "left_sign", "climb_sign", "yaw_sign"):
        m[f] = float(re.search(f + r"=(-?[0-9.]+)", block).group(1))
    return m


STEPS = {s.name: s for s in P.steps_for(P.F310, cmu_xbox_mapping())}


class Spec(unittest.TestCase):
    def test_f310_constant(self):
        s = P.F310
        self.assertEqual((s.name, s.profile, s.usb, s.driver, s.sdl_name), ("f310", "xbox_usb", ("046d", "c21d"), "xpad", "Logitech Gamepad F310"))
        self.assertEqual((s.n_axes, s.n_buttons, s.trigger_axes, s.hat_axes), (8, 11, (2, 5), (6, 7)))
        self.assertIn("flip the switch on the back of the pad to X", s.wrong_modes[("046d", "c216")])


class InputDevices(unittest.TestCase):
    def test_parses_the_real_capture(self):
        d = devs("proc_x_mode.txt")
        self.assertEqual(len(d), 6)                                         # comment line ignored
        f = [x for x in d if x["vendor"] == "046d"][0]
        self.assertEqual((f["product"], f["name"], f["handlers"]), ("c21d", "Logitech Gamepad F310", ["event27", "js1"]))
        k = [x for x in d if "js0" in x["handlers"]][0]
        self.assertEqual((k["vendor"], k["product"], k["name"]), ("3434", "0e40", "Keychron Keychron K4 HE"))

    def test_x_mode_passes_and_names_the_keyboard_as_ignored(self):
        v, js = P.judge_usb(devs("proc_x_mode.txt"), P.F310)
        self.assertTrue(all(x.ok for x in v), [x.line() for x in v]); self.assertEqual(js, "js1")
        self.assertEqual(v[0].line(), 'PASS usb 046d:c21d "Logitech Gamepad F310" js1 (X mode)')
        self.assertEqual(v[1].line(), 'PASS others js0 "Keychron Keychron K4 HE" ignored — not the pinned name')

    def test_d_mode_fails_with_the_switch_fix(self):
        v, js = P.judge_usb(devs("proc_d_mode.txt"), P.F310)
        self.assertFalse(v[0].ok); self.assertIsNone(js)
        self.assertEqual(v[0].text, "046d:c216 = D mode — flip the switch on the back of the pad to X")

    def test_keyboard_only_never_picks_js0(self):
        v, js = P.judge_usb(devs("proc_keyboard_only.txt"), P.F310)
        self.assertFalse(v[0].ok); self.assertIsNone(js); self.assertEqual(v[0].text, "F310 not found — plug it in")

    def test_two_f310_is_ambiguous(self):
        v, js = P.judge_usb(devs("proc_two_f310.txt"), P.F310)
        self.assertFalse(v[0].ok); self.assertIsNone(js); self.assertEqual(v[0].text, "ambiguous — two F310 pads, unplug one")

    def test_an_x_pad_and_a_d_pad_together_are_ambiguous(self):
        both = devs("proc_x_mode.txt") + [x for x in devs("proc_d_mode.txt") if x["product"] == "c216"]
        v, js = P.judge_usb(both, P.F310)
        self.assertFalse(v[0].ok); self.assertIn("ambiguous", v[0].text)

    def test_another_joystick_with_the_pinned_name_fails_closed(self):
        d = devs("proc_x_mode.txt")
        k = [x for x in d if "js0" in x["handlers"]][0]; k["name"] = "Logitech Gamepad F310"
        v, _ = P.judge_usb(d, P.F310)
        self.assertFalse(all(x.ok for x in v)); self.assertIn("js0", [x for x in v if not x.ok][0].text)

    def test_f310_without_a_joystick_handler_fails(self):
        d = devs("proc_x_mode.txt")
        [x for x in d if x["vendor"] == "046d"][0]["handlers"] = ["event27"]
        v, js = P.judge_usb(d, P.F310)
        self.assertFalse(v[0].ok); self.assertIsNone(js)

    def test_empty_or_garbage_is_not_found(self):
        for text in ("", "garbage\nlines\n"):
            v, js = P.judge_usb(P.parse_input_devices(text), P.F310)
            self.assertFalse(v[0].ok); self.assertIsNone(js)


class Driver(unittest.TestCase):
    def test_xpad_passes(self):
        self.assertEqual(P.judge_driver("xpad", P.F310).line(), "PASS driver xpad")

    def test_hid_generic_fails(self):
        v = P.judge_driver("hid-generic", P.F310)
        self.assertFalse(v.ok); self.assertEqual(v.text, "driver hid-generic — cannot confirm X mode")

    def test_missing_driver_fails_closed(self):
        for n in (None, ""):
            v = P.judge_driver(n, P.F310)
            self.assertFalse(v.ok); self.assertEqual(v.text, "driver unreadable — cannot confirm X mode")


class Opened(unittest.TestCase):
    LOG = "[INFO] [1763012345.1] [svg_pad_check_joy]: Opened joystick: Logitech Gamepad F310.  deadzone: 0.050000\n"

    def test_parses_the_measured_log_line(self):
        self.assertEqual(P.parse_opened_name(self.LOG), "Logitech Gamepad F310")
        self.assertEqual(P.parse_opened_name("noise\n" + self.LOG + "more\n"), "Logitech Gamepad F310")

    def test_none_when_nothing_opened(self):
        self.assertIsNone(P.parse_opened_name("[ERROR] Could not get joystick with name Logitech Gamepad F310\n"))
        self.assertIsNone(P.parse_opened_name(""))

    def test_exact_name_passes(self):
        self.assertEqual(P.judge_opened("Logitech Gamepad F310", P.F310).line(), 'PASS joy_node opened "Logitech Gamepad F310"')

    def test_none_fails_with_the_pin(self):
        v = P.judge_opened(None, P.F310)
        self.assertFalse(v.ok); self.assertEqual(v.text, 'joy_node opened nothing within 5 s (name pin "Logitech Gamepad F310")')

    def test_another_name_fails(self):
        self.assertFalse(P.judge_opened("Logitech Logitech Dual Action", P.F310).ok)


class Shape(unittest.TestCase):
    def test_8_11_passes(self):
        self.assertEqual(P.judge_shape(8, 11, P.F310).line(), "PASS 8 axes 11 buttons")

    def test_others_fail(self):
        for a, b in ((6, 12), (8, 12), (6, 16), (0, 0)):
            v = P.judge_shape(a, b, P.F310)
            self.assertFalse(v.ok, (a, b)); self.assertEqual(v.text, "%d axes/%d buttons — not the X-mode layout (8/11)" % (a, b))


class Rest(unittest.TestCase):
    def test_rest_fixture_passes_and_returns_the_baseline(self):
        v = P.judge_rest(P.load_jsonl((FIX / "joy_rest.jsonl").read_text()), P.F310)
        self.assertTrue(v.ok, v.text); self.assertTrue(v.line().startswith("PASS rest ")); self.assertEqual(v.data, REST)

    def test_small_stick_noise_is_rest(self):
        self.assertTrue(P.judge_rest([sample(a4=0.12, a0=-0.1)], P.F310).ok)

    def test_trigger_pressed(self):
        v = P.judge_rest([sample(), sample(a2=0.5)], P.F310)
        self.assertFalse(v.ok); self.assertIn("trigger", v.text); self.assertIn("axis 2", v.text)

    def test_stick_held(self):
        v = P.judge_rest([sample(a4=0.6)], P.F310)
        self.assertFalse(v.ok); self.assertIn("stick", v.text); self.assertIn("axis 4", v.text)

    def test_dpad_held(self):
        v = P.judge_rest([sample(a6=-1.0)], P.F310)
        self.assertFalse(v.ok); self.assertIn("D-pad", v.text); self.assertIn("axis 6", v.text)

    def test_button_held(self):
        v = P.judge_rest([sample(b4=1)], P.F310)
        self.assertFalse(v.ok); self.assertIn("button 4", v.text)

    def test_no_samples_or_wrong_length_fail_closed(self):
        self.assertFalse(P.judge_rest([], P.F310).ok)
        self.assertFalse(P.judge_rest([{"t": 0, "axes": [0.0] * 6, "buttons": [0] * 16}], P.F310).ok)


class Steps(unittest.TestCase):
    def test_steps_follow_cmus_xbox_usb_profile(self):
        m = cmu_xbox_mapping()
        s = P.steps_for(P.F310, m)
        self.assertEqual([x.name for x in s], ["right stick UP", "right stick LEFT", "left stick UP", "left stick LEFT", "press LB"])
        self.assertEqual([(x.kind, x.index) for x in s],
                         [("axis", m["forward_axis"]), ("axis", m["left_axis"]), ("axis", m["climb_axis"]), ("axis", m["yaw_axis"]),
                          ("button", m["lock_button"])])
        self.assertEqual([(x.kind, x.index) for x in s], [("axis", 4), ("axis", 3), ("axis", 1), ("axis", 0), ("button", 4)])
        self.assertEqual([x.sign for x in s[:4]], [m["forward_sign"], m["left_sign"], m["climb_sign"], m["yaw_sign"]])
        self.assertEqual([x.stick for x in s], ["right", "right", "left", "left", None])

    def test_a_flipped_profile_sign_flips_the_expectation(self):
        m = dict(cmu_xbox_mapping(), forward_sign=-1.0)
        st = P.steps_for(P.F310, m)[0]
        self.assertTrue(P.judge_step(st, [sample(a4=-1.0)], REST, P.F310).ok)
        self.assertIn("INVERTED", P.judge_step(st, [sample(a4=1.0)], REST, P.F310).text)


class Step(unittest.TestCase):
    def j(self, name, *samples):
        return P.judge_step(STEPS[name], list(samples), REST, P.F310)

    def test_right_up_fixture_passes(self):
        v = P.judge_step(STEPS["right stick UP"], P.load_jsonl((FIX / "joy_right_up.jsonl").read_text()), REST, P.F310)
        self.assertTrue(v.ok, v.text); self.assertEqual(v.line(), "PASS right stick UP: axis 4 +1.00")

    def test_every_stick_step_passes_on_its_own_axis(self):
        for name, ax in (("right stick UP", 4), ("right stick LEFT", 3), ("left stick UP", 1), ("left stick LEFT", 0)):
            self.assertTrue(self.j(name, sample(**{"a%d" % ax: 0.95})).ok, name)

    def test_inverted(self):
        v = self.j("right stick UP", sample(a4=-1.0))
        self.assertFalse(v.ok); self.assertTrue(v.text.startswith("INVERTED"), v.text)

    def test_not_full(self):
        v = self.j("left stick LEFT", sample(a0=0.6))
        self.assertFalse(v.ok); self.assertTrue(v.text.startswith("NOT FULL"), v.text)

    def test_wrong_axis_same_stick(self):
        v = self.j("right stick UP", sample(a3=1.0))
        self.assertFalse(v.ok); self.assertTrue(v.text.startswith("WRONG AXIS"), v.text)

    def test_swapped_stick(self):
        v = self.j("right stick UP", sample(a1=1.0))
        self.assertFalse(v.ok); self.assertTrue(v.text.startswith("SWAPPED STICK"), v.text)
        self.assertTrue(self.j("left stick UP", sample(a4=1.0)).text.startswith("SWAPPED STICK"))

    def test_mode_on(self):
        v = P.judge_step(STEPS["left stick UP"], P.load_jsonl((FIX / "joy_mode_on_left_up.jsonl").read_text()), REST, P.F310)
        self.assertFalse(v.ok); self.assertEqual(v.text, "MODE ON — press MODE (light off) and run again")
        self.assertEqual(self.j("left stick LEFT", sample(a6=1.0)).text, "MODE ON — press MODE (light off) and run again")

    def test_dpad_on_a_right_stick_step(self):
        v = self.j("right stick UP", sample(a7=1.0))
        self.assertFalse(v.ok); self.assertIn("D-pad", v.text); self.assertNotIn("MODE ON", v.text)

    def test_trigger(self):
        v = self.j("right stick LEFT", sample(a5=-1.0))
        self.assertFalse(v.ok); self.assertIn("trigger", v.text.lower())

    def test_no_movement(self):
        v = self.j("left stick UP", sample(), sample(a1=0.3))
        self.assertFalse(v.ok); self.assertEqual(v.text, "NO MOVEMENT on left stick UP")
        self.assertEqual(self.j("press LB").text, "NO MOVEMENT on press LB")

    def test_lb_passes(self):
        v = self.j("press LB", sample(), sample(b4=1))
        self.assertTrue(v.ok, v.text); self.assertEqual(v.line(), "PASS press LB: button 4")

    def test_wrong_button(self):
        v = self.j("press LB", sample(b5=1))
        self.assertFalse(v.ok); self.assertTrue(v.text.startswith("WRONG BUTTON"), v.text)
        self.assertTrue(self.j("press LB", sample(b4=1, b5=1)).text.startswith("WRONG BUTTON"))      # two buttons: fail closed
        self.assertTrue(self.j("press LB", sample(a2=-1.0)).text.startswith("WRONG BUTTON"))         # LT instead of LB

    def test_keyboard_never_moves(self):
        kb = P.load_jsonl((FIX / "joy_keyboard.jsonl").read_text())
        for name in STEPS:
            v = P.judge_step(STEPS[name], kb, REST, P.F310)
            self.assertFalse(v.ok, name)

    def test_movement_needs_half_a_stick_or_a_button(self):
        self.assertFalse(P.movement(sample(a4=0.4), REST)); self.assertTrue(P.movement(sample(a4=0.6), REST))
        self.assertTrue(P.movement(sample(b0=1), REST)); self.assertTrue(P.movement(sample(a2=0.4), REST))   # trigger 1.0 -> 0.4


class Environment(unittest.TestCase):
    def test_clean_passes(self):
        self.assertTrue(P.judge_environment([], ["/svg_pad_check"], []).ok)

    def test_a_joy_publisher_refuses(self):
        v = P.judge_environment(["/joy_node"], ["/joy_node"], [])
        self.assertFalse(v.ok)
        self.assertEqual(v.text, "1 publisher(s) on /joy (/joy_node) — stop the teleop pane / close the sim keyboard window (tools/sim.sh relay stop)")

    def test_safe_teleop_refuses(self):
        for nodes, procs in ((["/safe_teleop"], []), ([], ["/usr/bin/python3 /root/AirStack/.../safe_teleop --ros-args"])):
            v = P.judge_environment([], nodes, procs)
            self.assertFalse(v.ok); self.assertEqual(v.text, "safe_teleop running — stick tests would reach the commander")

    def test_isaac_refuses(self):
        v = P.judge_environment([], [], ["python3 svg_multi_drone_single_domain.py"])
        self.assertFalse(v.ok); self.assertEqual(v.text, "Isaac Sim running — real teleop refused")


class Lines(unittest.TestCase):
    def test_final_lines(self):
        self.assertEqual(P.fail_line("F310 not found — plug it in"), "PAD CHECK: FAIL — do not fly: F310 not found — plug it in")
        self.assertEqual(P.PASS_LINE, "PAD CHECK: PASS — do not press MODE from now on")

    def test_load_jsonl_skips_comments_and_blanks(self):
        self.assertEqual(P.load_jsonl('# x\n\n{"t": 1, "axes": [], "buttons": []}\n'), [{"t": 1, "axes": [], "buttons": []}])


class Purity(unittest.TestCase):
    def test_stdlib_only_no_ros(self):
        src = (HERE.parent / "teleop" / "pad_core.py").read_text()
        for bad in ("rclpy", "import yaml", "subprocess", "sensor_msgs"):
            self.assertNotIn(bad, src)


if __name__ == "__main__":
    unittest.main()
