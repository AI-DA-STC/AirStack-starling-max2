# tools/tests/test_real_config.py — the per-drone real teleop config rendered from teleop_real_ours.yaml (tools/teleop/real_config.py).
import dataclasses, datetime, os, pathlib, subprocess, sys, tempfile, unittest
import yaml
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "teleop"))
import pad_core as P
import real_config as C

SRC_PATH = HERE.parents[1] / "AirStack/robot/ros_ws/src/svg_ground_control/config/teleop_real_ours.yaml"
SRC = SRC_PATH.read_text()
NOW = datetime.datetime(2026, 11, 13, 15, 0, 0, tzinfo=datetime.timezone(datetime.timedelta(hours=8)))
SHA = "ab" * 32
SL = SRC.splitlines()
LINE_NAMES = [i + 1 for i, l in enumerate(SL) if l == '    drone_names: ["drone_1"]']
LINE_TELEOP = [i + 1 for i, l in enumerate(SL) if l == '    teleop_drones: "drone_1"']
LINE_CTRL = [i + 1 for i, l in enumerate(SL) if l == '    teleop_controller: "dragonrise_usb"']


def render(drone="drone_2", src=SRC, spec=P.F310):
    return C.render(src, drone, spec, NOW, SHA)


def body_diff(out, src=SRC):
    """{source line number: (old, new)} over the rendered body (header and appended tail dropped)."""
    o = out.splitlines()[2:]
    s = src.splitlines()
    body = o[:len(s)]
    return {i + 1: (a, b) for i, (a, b) in enumerate(zip(s, body)) if a != b}


class Anchors(unittest.TestCase):
    def test_the_source_has_the_anchors_the_spec_measured(self):
        self.assertEqual((len(LINE_NAMES), len(LINE_TELEOP), len(LINE_CTRL)), (2, 1, 1))


class Render(unittest.TestCase):
    def test_drone_2_changes_only_the_listed_lines(self):
        d = body_diff(render("drone_2"))
        self.assertEqual(sorted(d), sorted(LINE_NAMES + LINE_TELEOP + LINE_CTRL))
        for n in LINE_NAMES:
            self.assertEqual(d[n][1], '    drone_names: ["drone_2"]')
        self.assertEqual(d[LINE_TELEOP[0]][1], '    teleop_drones: "drone_2"')
        self.assertEqual(d[LINE_CTRL[0]][1], '    teleop_controller: "xbox_usb"')

    def test_drone_1_changes_only_the_controller_line(self):
        d = body_diff(render("drone_1"))
        self.assertEqual(sorted(d), LINE_CTRL)
        self.assertEqual(d[LINE_CTRL[0]][1], '    teleop_controller: "xbox_usb"')

    def test_semantically_equal_except_the_listed_keys(self):
        for drone in C.KNOWN_DRONES:
            s, o = yaml.safe_load(SRC), yaml.safe_load(render(drone))
            self.assertEqual(set(o), set(s) | {"led_controller", "joy_node"})
            self.assertEqual(o["swarm_commander"]["ros__parameters"].pop("drone_names"), [drone])
            self.assertEqual(o["swarm_commander"]["ros__parameters"].pop("teleop_drones"), drone)
            self.assertEqual(o["mocap_bridge"]["ros__parameters"].pop("drone_names"), [drone])
            self.assertEqual(o["safe_teleop"]["ros__parameters"].pop("teleop_controller"), "xbox_usb")
            self.assertEqual(o.pop("led_controller"), {"ros__parameters": {"drone_names": [drone]}})
            self.assertEqual(o.pop("joy_node"), {"ros__parameters": {"device_name": "Logitech Gamepad F310"}})
            for k, path in (("swarm_commander", ("drone_names", "teleop_drones")), ("mocap_bridge", ("drone_names",)),
                            ("safe_teleop", ("teleop_controller",))):
                for p in path:
                    s[k]["ros__parameters"].pop(p)
            self.assertEqual(o, s, drone)

    def test_blocks_appended_exactly(self):
        out = render("drone_2")
        self.assertTrue(out.endswith('led_controller:\n  ros__parameters:\n    drone_names: ["drone_2"]\n'
                                     'joy_node:\n  ros__parameters:\n    device_name: "Logitech Gamepad F310"\n'), out[-300:])

    def test_the_pin_is_the_pad_specs_sdl_name(self):
        self.assertIn('    device_name: "%s"\n' % P.F310.sdl_name, render())
        other = dataclasses.replace(P.F310, sdl_name="Some Other Pad")
        self.assertIn('    device_name: "Some Other Pad"\n', render(spec=other))

    def test_header_names_sha_drone_pad_and_time(self):
        h = render("drone_2").splitlines()[:2]
        self.assertTrue(all(l.startswith("# ") for l in h), h)
        text = "\n".join(h)
        for n in (SHA, "drone_2", "f310", "2026-11-13T15:00:00+08:00", "tools/real.sh teleop drone_2", "teleop_real_ours.yaml"):
            self.assertIn(n, text)
        self.assertEqual(SRC.splitlines()[0], render().splitlines()[2])

    def test_rendering_is_a_pure_function(self):
        self.assertEqual(render("drone_2"), render("drone_2"))


class Refusals(unittest.TestCase):
    def test_unknown_drones_refused(self):
        for d in ("drone_3", "drone_N", "2", "drone_02", "", "drone_1 ", "<drone>"):
            with self.assertRaises(C.RenderError, msg=repr(d)):
                render(d)
            with self.assertRaises(C.RenderError, msg=repr(d)):
                C.check_drone(d)

    def test_anchor_count_drift_refused(self):
        cases = [SRC.replace('    drone_names: ["drone_1"]\n', "    drone_names: [\"drone_1\", \"drone_2\"]\n", 1),
                 SRC.replace('    teleop_drones: "drone_1"\n', '    teleop_drones: "drone_1"\n    teleop_drones: "drone_1"\n'),
                 SRC.replace('    teleop_controller: "dragonrise_usb"', '    teleop_controller: "xbox_usb"'),
                 SRC.replace('    drone_names: ["drone_1"]\n', '    drone_names: ["drone_1"]\n', 1) + 'x:\n  ros__parameters:\n    drone_names: ["drone_1"]\n']
        for i, src in enumerate(cases):
            for drone in C.KNOWN_DRONES:
                with self.assertRaises(C.RenderError, msg=(i, drone)):
                    render(drone, src)

    def test_stray_drone_1_refused_for_drone_2(self):
        src = SRC.replace("    external_drones: \"\"\n", "    external_drones: \"drone_1\"\n")
        with self.assertRaises(C.RenderError):
            render("drone_2", src)
        render("drone_1", src)                                       # drone_1 itself may say drone_1

    def test_comments_naming_drone_1_are_fine(self):
        self.assertIn("Motive body named drone_1", render("drone_2"))

    def test_existing_top_level_blocks_refused(self):
        for extra in ('led_controller:\n  ros__parameters:\n    drone_names: ["drone_1"]\n',
                      'joy_node:\n  ros__parameters:\n    device_id: 1\n',
                      '/joy_node:\n  ros__parameters:\n    device_id: 1\n',
                      '"/joy_node":\n  ros__parameters:\n    device_id: 1\n',
                      '/led_controller:\n  ros__parameters:\n    drone_names: ["drone_1"]\n',
                      '/**:\n  ros__parameters:\n    use_sim_time: false\n',
                      '"/**":\n  ros__parameters:\n    use_sim_time: false\n'):
            with self.assertRaises(C.RenderError, msg=extra):
                render("drone_1", SRC + extra)

    def test_verify_render_catches_a_tampered_output(self):
        good = render("drone_2")
        C.verify_render(SRC, good, "drone_2", P.F310)
        bad = [good.replace("    land_speed_mps: 0.6", "    land_speed_mps: 0.3"),          # another value changed
               good.replace('    teleop_drones: "drone_2"', '    teleop_drones: "drone_1"'),   # an anchor left behind
               good + "extra_key:\n  ros__parameters: {}\n",                                   # an extra top-level key
               good.replace('device_name: "Logitech Gamepad F310"', 'device_name: "x"')]
        for i, out in enumerate(bad):
            with self.assertRaises(C.RenderError, msg=i):
                C.verify_render(SRC, out, "drone_2", P.F310)

    def test_pyyaml_missing_is_a_refusal(self):
        keep = C.yaml
        try:
            C.yaml = None
            with self.assertRaises(C.RenderError) as e:
                render("drone_2")
            self.assertIn("PyYAML", str(e.exception))
            self.assertIsInstance(e.exception, C.CannotCheck)                    # exit 2, not a refusal (CHG-0066)
        finally:
            C.yaml = keep


class MappingOverrides(unittest.TestCase):
    """CHG-0066: safe_teleop takes its axis map from the config's block when one is set; the pad check tests the
    profile's own map, so a source that overrides it must not render (it would fly inverted after a PASS)."""
    KEYS = ("forward_axis", "left_axis", "climb_axis", "yaw_axis", "lock_button",
            "forward_sign", "left_sign", "climb_sign", "yaw_sign", "joy_topic")
    VALUES = {"forward_axis": "3", "forward_sign": "-1.0", "lock_button": "5", "joy_topic": '"/joy2"'}

    def with_override(self, key, value, block="safe_teleop"):
        anchor = "    max_climb_speed_mps: 0.5"
        if block == "safe_teleop":
            self.assertIn(anchor, SRC)
            return SRC.replace(anchor, anchor + "\n    %s: %s" % (key, value), 1)
        return SRC + "%s:\n  ros__parameters:\n    %s: %s\n" % (block, key, value)

    def assert_refused(self, src, key):
        for drone in C.KNOWN_DRONES:
            with self.assertRaises(C.RenderError) as e:
                render(drone, src)
            msg = str(e.exception)
            self.assertIn(key, msg)
            self.assertIn("the pad check tests the profile's own mapping; remove the override from teleop_real_ours.yaml", msg)

    def test_an_axis_override_is_refused(self):
        self.assert_refused(self.with_override("forward_axis", "3"), "forward_axis")

    def test_a_sign_override_is_refused(self):
        self.assert_refused(self.with_override("forward_sign", "-1.0"), "forward_sign")

    def test_a_lock_button_override_is_refused(self):
        self.assert_refused(self.with_override("lock_button", "5"), "lock_button")

    def test_a_joy_topic_override_is_refused(self):
        self.assert_refused(self.with_override("joy_topic", '"/joy2"'), "joy_topic")

    def test_every_key_in_every_spelling_is_refused(self):
        for key in self.KEYS:
            v = self.VALUES.get(key, "1")
            for block in ("safe_teleop", "/safe_teleop", '"/safe_teleop"', "/**", '"/**"'):
                with self.assertRaises(C.RenderError, msg=(key, block)) as e:
                    render("drone_2", self.with_override(key, v, block))
                self.assertIn(key, str(e.exception), (key, block))

    def test_verify_render_refuses_an_override_too(self):
        src = self.with_override("yaw_sign", "-1.0")
        out = render("drone_2").replace("    max_climb_speed_mps: 0.5", "    max_climb_speed_mps: 0.5\n    yaw_sign: -1.0", 1)
        with self.assertRaises(C.RenderError) as e:
            C.verify_render(src, out, "drone_2", P.F310)
        self.assertIn("yaw_sign", str(e.exception))

    def test_the_real_source_still_renders(self):
        for drone in C.KNOWN_DRONES:
            C.verify_render(SRC, render(drone), drone, P.F310)


class Operator(unittest.TestCase):
    PANES_2 = ['laptop : cd ~/AirStack-starling-max2 && MOCAP_BODIES="drone_2" ./mocap.sh',      # start order (CHG-0066)
               'pane 1 : MicroXRCEAgent udp4 -p 8888 -v4',
               'pane 2 : ros2 launch svg_ground_control real_interfaces.launch.py drones:=drone_2 target_systems:=2',
               'pane 5 : ros2 launch svg_ground_control teleop.launch.py config:=/tmp/svg_real/teleop_real_drone_2.yaml',
               'pane 3 : ros2 launch svg_ground_control ground_control.launch.py config:=/tmp/svg_real/teleop_real_drone_2.yaml use_mocap:=true use_foxglove_studio:=true']
    START_HEADER = "Start them in this order. Prove the sticks on the ground (pane 5) before you start the commander (pane 3):"

    def test_pane_lines_drone_2_literal(self):
        self.assertEqual(C.pane_lines("drone_2", "/tmp/svg_real/teleop_real_drone_2.yaml"), self.PANES_2)

    def test_pane_lines_drone_1_literal(self):
        want = [l.replace("drone_2", "drone_1").replace("target_systems:=2", "target_systems:=1") for l in self.PANES_2]
        self.assertEqual(C.pane_lines("drone_1", "/tmp/svg_real/teleop_real_drone_1.yaml"), want)

    def test_no_placeholders_anywhere_the_operator_reads(self):
        for d in C.KNOWN_DRONES:
            out = render(d)
            text = "\n".join(C.operator_block(SRC, out, d, C.container_path(d)))
            self.assertNotIn("drone_N", text); self.assertNotIn("<", text)
            for l in C.pane_lines(d, C.container_path(d)):
                self.assertNotIn("drone_N", l); self.assertNotIn("<", l)

    def test_unknown_drone_has_no_pane_lines(self):
        with self.assertRaises(C.RenderError):
            C.pane_lines("drone_3", "/tmp/x.yaml")

    def test_container_path(self):
        self.assertEqual(C.container_path("drone_2"), "/tmp/svg_real/teleop_real_drone_2.yaml")

    def test_takeoff_point_from_hover_positions(self):
        for d in C.KNOWN_DRONES:
            self.assertEqual(C.takeoff_point(SRC, d), (-0.5, 0.0, 0.5))
        self.assertEqual(C.takeoff_sentence("drone_2", (-0.5, 0.0, 0.5)),
                         "Stand drone_2 on x -0.5, y 0.0, nose toward +x. Takeoff flies a straight line to that point.")

    def test_diff_summary_lists_only_the_changed_lines_and_the_blocks(self):
        lines = C.diff_summary(SRC, render("drone_2"))
        changed = [l for l in lines if l.lstrip().startswith("line ")]
        self.assertEqual(len(changed), 4, lines)
        self.assertTrue(any('drone_names: ["drone_2"]' in l and "line %d " % LINE_NAMES[0] in l for l in changed), lines)
        self.assertTrue(any('teleop_controller: "xbox_usb"' in l for l in changed))
        added = [l for l in lines if l.lstrip().startswith("added")]
        self.assertEqual(len(added), 2, lines)
        self.assertEqual(len([l for l in C.diff_summary(SRC, render("drone_1")) if l.lstrip().startswith("line ")]), 1)

    def test_operator_block_order(self):
        out = render("drone_2")
        b = C.operator_block(SRC, out, "drone_2", C.container_path("drone_2"))
        i_diff = next(i for i, l in enumerate(b) if "line %d " % LINE_CTRL[0] in l)
        i_take = b.index("Stand drone_2 on x -0.5, y 0.0, nose toward +x. Takeoff flies a straight line to that point.")
        i_pane = b.index(self.PANES_2[0])
        self.assertLess(i_diff, i_take); self.assertLess(i_take, i_pane)
        self.assertEqual(b[i_pane:i_pane + 5], self.PANES_2)
        self.assertEqual(b[i_pane - 1], self.START_HEADER)
        self.assertEqual(b[-1], "Do not press MODE. Re-run this command after any container restart or pad replug.")


class Cli(unittest.TestCase):
    PY = HERE.parent / "teleop" / "real_config.py"

    def cli(self, *args):
        return subprocess.run([sys.executable, str(self.PY), *args], capture_output=True, text=True, timeout=20)

    def test_check_drone(self):
        self.assertEqual(self.cli("check-drone", "drone_2").returncode, 0)
        r = self.cli("check-drone", "drone_3")
        self.assertEqual(r.returncode, 2); self.assertIn("drone_1 or drone_2", r.stderr)

    def test_render_writes_and_prints(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "o.yaml")
            r = self.cli("render", "--drone", "drone_2", "--source", str(SRC_PATH), "--out", out)
            self.assertEqual(r.returncode, 0, r.stderr)
            text = pathlib.Path(out).read_text()
            C.verify_render(SRC, text, "drone_2", P.F310)
            self.assertIn(C.sha256_text(SRC), text.splitlines()[0])
            self.assertIn(Operator.PANES_2[4], r.stdout)

    def test_render_without_pyyaml_is_cannot_check_exit_2(self):
        with tempfile.TemporaryDirectory() as shim, tempfile.TemporaryDirectory() as tmp:
            pathlib.Path(shim, "yaml.py").write_text("raise ImportError('no PyYAML in this test')\n")
            r = subprocess.run([sys.executable, str(self.PY), "render", "--drone", "drone_2", "--source", str(SRC_PATH),
                                "--out", os.path.join(tmp, "o.yaml")], capture_output=True, text=True, timeout=20,
                               env=dict(os.environ, PYTHONPATH=shim))
            self.assertEqual(r.returncode, 2, r.stderr); self.assertIn("PyYAML", r.stderr)
            self.assertFalse(os.path.exists(os.path.join(tmp, "o.yaml")))

    def test_render_refuses_a_drifted_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "s.yaml"); pathlib.Path(src).write_text(SRC + 'joy_node:\n  ros__parameters:\n    device_id: 1\n')
            out = os.path.join(tmp, "o.yaml")
            r = self.cli("render", "--drone", "drone_2", "--source", src, "--out", out)
            self.assertEqual(r.returncode, 1); self.assertIn("refused", r.stderr); self.assertFalse(os.path.exists(out))


if __name__ == "__main__":
    unittest.main()
