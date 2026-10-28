# tools/tests/test_hover_step_plot.py
import contextlib, io, json, pathlib, shutil, sys, tempfile, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import hover_step_plot as P
import hover_step_analysis as A
FX = pathlib.Path(__file__).resolve().parent / "fixtures" / "run1"
REC = pathlib.Path(__file__).resolve().parents[2] / "docs" / "record"

class Plot(unittest.TestCase):
    def test_panel_order_handles_n_steps(self):
        ev = [{"name": n} for n in ["takeoff_lateral_x", "takeoff", "step_x_1", "step_x_2", "step_z_1", "landing"]]
        self.assertEqual([n for n, _ in P.panel_order(ev)], ["takeoff", "step_x_1", "step_x_2", "step_z_1", "landing"])

    def test_panel_order_sorts_by_step_index_not_lexically(self):
        ev = [{"name": n} for n in ["step_x_10", "step_z_2", "step_x_2", "landing", "takeoff", "step_z_1", "step_x_1"]]
        self.assertEqual([n for n, _ in P.panel_order(ev)],
                         ["takeoff", "step_x_1", "step_x_2", "step_x_10", "step_z_1", "step_z_2", "landing"])

    def test_renders_png_from_fixture(self):
        with tempfile.TemporaryDirectory() as d:
            out = pathlib.Path(d)
            for f in ("drone_1_odom.csv", "drone_1_cmd.csv", "drone_1_state.csv", "px4_arm_times.txt"): shutil.copy(FX / f, out / f)
            odom, cmd, state = A.load_xyz_csv(out / "drone_1_odom.csv"), A.load_xyz_csv(out / "drone_1_cmd.csv"), A.load_state_csv(out / "drone_1_state.csv")
            (out / "bag_analysis.json").write_text(json.dumps(A.analyse(odom, cmd, state, px4_arm_times=A.load_px4_arm_times(out / "px4_arm_times.txt"))))
            P.main([str(out)])
            self.assertGreater((out / "step_response.png").stat().st_size, 20_000)


class Overlay(unittest.TestCase):
    def test_step_events_accepts_old_and_new_names(self):
        ev = [{"name": n} for n in ["takeoff", "step_x", "step_z_2", "step_z_1", "step_x_1", "landing"]]
        self.assertEqual([(a, e["name"]) for a, e in P.step_events(ev)],
                         [("x", "step_x"), ("x", "step_x_1"), ("z", "step_z_1"), ("z", "step_z_2")])

    def test_run_time_scale_prefers_override_and_marks_estimated(self):
        self.assertEqual(P.run_time_scale({"time_scale": 1.3329, "time_scale_source": "px4_arm_times.txt (sysid 2)"}, None), (1.3329, False))
        self.assertEqual(P.run_time_scale({"time_scale": 1.3329, "time_scale_source": "px4_arm_times.txt (sysid 2)"}, 1.336), (1.336, True))
        with self.assertRaises(ValueError): P.run_time_scale({"time_scale": 1.0, "time_scale_source": "assumed 1.0 (no px4_arm_times)"}, None)
        with self.assertRaises(ValueError): P.run_time_scale({}, None)

    def test_relative_trace_is_goal_relative_and_vehicle_time(self):
        run = REC / "sim_hover_step_run2"
        j = json.loads((run / "bag_analysis.json").read_text())
        odom = P._load_xyz(run / "drone_1_odom.csv")
        ev = next(e for e in j["events"] if e["name"] == "step_x_2")      # a -1 m step: must read as +1
        t, y = P.relative_trace(odom, ev, 1.3237)
        self.assertAlmostEqual(y[0], 0.0, places=1)
        self.assertAlmostEqual(y[-1], 1.0, delta=0.1)
        # the trace stops where the analysis stops the step (ev["window_s"] = 7.486 wall s: the next step's command starts there),
        # not at the full 8 s: past it the position leaves the goal (0.84 m at 8 s)
        self.assertGreater(t[-1], (ev["window_s"] - 0.3) * 1.3237); self.assertLessEqual(t[-1], ev["window_s"] * 1.3237 + 0.1)

    def test_overlay_renders_three_runs(self):
        with tempfile.TemporaryDirectory() as d:
            out = pathlib.Path(d) / "overlay.png"
            rc = P.main(["--overlay", str(REC / "sim_hover_step_run1"), str(REC / "sim_hover_step_run2"), str(REC / "sim_hover_step_run3"),
                         "--time-scale", "sim_hover_step_run1=1.336", "--label", "sim_hover_step_run1=#17",
                         "--label", "sim_hover_step_run2=#18", "--label", "sim_hover_step_run3=#19", "-o", str(out)])
            self.assertEqual(rc, 0); self.assertGreater(out.stat().st_size, 20_000)

    def test_overlay_refuses_run_without_time_scale(self):            # Review Focus 1
        with tempfile.TemporaryDirectory() as d:
            out = pathlib.Path(d) / "overlay.png"
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                rc = P.main(["--overlay", str(REC / "sim_hover_step_run1"), str(REC / "sim_hover_step_run2"), "-o", str(out)])
            self.assertEqual(rc, 2); self.assertIn("sim_hover_step_run1", err.getvalue()); self.assertFalse(out.exists())

    def test_spread_labels_enforces_min_gap_and_keeps_order(self):
        out = P.spread_labels([100.0, 101.0, 100.5, 40.0], 10.0)
        self.assertEqual(len(out), 4)
        order = sorted(range(4), key=lambda i: [100.0, 101.0, 100.5, 40.0][i])
        s = [out[i] for i in order]
        self.assertTrue(all(b - a >= 10.0 - 1e-9 for a, b in zip(s, s[1:])), out)
        self.assertEqual(P.spread_labels([5.0, 50.0], 10.0), [5.0, 50.0])          # already apart: untouched

    def test_overlay_unknown_keys_exit_2_naming_the_key(self):
        for flag, key in (("--time-scale", "sim_hover_step_run9=1.2"), ("--label", "nope=#1")):
            with tempfile.TemporaryDirectory() as d:
                out = pathlib.Path(d) / "overlay.png"
                err = io.StringIO()
                with contextlib.redirect_stderr(err):
                    rc = P.main(["--overlay", str(REC / "sim_hover_step_run2"), str(REC / "sim_hover_step_run3"), flag, key, "-o", str(out)])
                self.assertEqual(rc, 2); self.assertIn(key.split("=")[0], err.getvalue()); self.assertFalse(out.exists())

    def test_single_run_mode_unchanged(self):
        with tempfile.TemporaryDirectory() as d:
            out = pathlib.Path(d)
            for f in ("drone_1_odom.csv", "drone_1_cmd.csv", "drone_1_state.csv", "px4_arm_times.txt"): shutil.copy(FX / f, out / f)
            odom, cmd, state = A.load_xyz_csv(out / "drone_1_odom.csv"), A.load_xyz_csv(out / "drone_1_cmd.csv"), A.load_state_csv(out / "drone_1_state.csv")
            (out / "bag_analysis.json").write_text(json.dumps(A.analyse(odom, cmd, state, px4_arm_times=A.load_px4_arm_times(out / "px4_arm_times.txt"))))
            self.assertEqual(P.main([str(out)]), 0); self.assertTrue((out / "step_response.png").exists())
