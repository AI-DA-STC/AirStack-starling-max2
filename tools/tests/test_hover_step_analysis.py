# tools/tests/test_hover_step_analysis.py
import json, math, pathlib, sys, tempfile, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import hover_step_analysis as A
FX = pathlib.Path(__file__).resolve().parent / "fixtures" / "run1"

def load():
    return (A.load_xyz_csv(FX / "drone_1_odom.csv"), A.load_xyz_csv(FX / "drone_1_cmd.csv"),
            A.load_state_csv(FX / "drone_1_state.csv"))

class Detector(unittest.TestCase):
    def test_detect_gentle_ramp_single_event(self):          # Review Focus 1
        cmd = [(i / 20, 0.0, 0.0, 0.0) for i in range(40)]  # 2 s quiet
        cmd += [(2 + i / 20, min(0.5 * i / 20, 0.6), 0.0, 0.0) for i in range(80)]   # 0.5 m/s² ramp to 0.6 m/s
        cmd += [(6 + i / 20, 0.0, 0.0, 0.0) for i in range(40)]
        ev = A.detect_events(cmd)
        self.assertEqual(len(ev), 1)
        self.assertEqual(ev[0]["axis"], 1)
        self.assertAlmostEqual(ev[0]["onset"], 2.2, places=6)   # first sample with v >= 0.10
        self.assertAlmostEqual(ev[0]["ramp_end"], 6.0, places=6)

    def test_fixture_events_axes_and_onsets(self):
        _, cmd, _ = load()
        ev = A.detect_events(cmd)
        self.assertEqual([e["axis"] for e in ev], [1, 2, 3, 1, 3, 3])
        self.assertAlmostEqual(ev[3]["onset"], 149.54, places=2)
        self.assertAlmostEqual(ev[4]["onset"], 158.59, places=2)
        self.assertAlmostEqual(ev[5]["onset"], 170.64, places=2)
        self.assertAlmostEqual(ev[3]["peak_v"], 0.917, places=2)

class Naming(unittest.TestCase):
    def test_fixture_names(self):
        odom, cmd, state = load()
        arm, _, _ = A.arming_events(state)
        names = [e["name"] for e in A.name_events(A.detect_events(cmd), arm[0], odom)]
        self.assertEqual(names, ["takeoff_lateral_x", "takeoff_lateral_y", "takeoff", "step_x_1", "step_z_1", "landing"])

    def test_three_alternating_z_steps_then_landing(self):
        # synthetic: arm at 0, takeoff z-up at 1 s, then z +1/−1/+1 at 30/40/50 s, landing (z-down to the floor) at 60 s
        def pulse(t0, ax, sgn):
            return [(t0 + i / 20, *(sgn * 0.9 if a == ax else 0.0 for a in (1, 2, 3))) for i in range(30)]
        quiet = lambda t0, n: [(t0 + i / 20, 0.0, 0.0, 0.0) for i in range(n)]
        cmd = quiet(0, 20) + pulse(1, 3, +1) + quiet(2.5, 550) + pulse(30, 3, +1) + quiet(31.5, 170) \
              + pulse(40, 3, -1) + quiet(41.5, 170) + pulse(50, 3, +1) + quiet(51.5, 170) + pulse(60, 3, -1) + quiet(61.5, 100)
        z = lambda t: 1.2 if t < 30 else (2.2 if t < 40 else (1.2 if t < 50 else (2.2 if t < 60 else 0.05)))
        odom = [(t, 0.0, 0.0, 0.0 if t < 1.5 else z(t)) for t in (i / 40 for i in range(70 * 40))]
        names = [e["name"] for e in A.name_events(A.detect_events(cmd), 0.0, odom)]
        self.assertEqual(names, ["takeoff", "step_z_1", "step_z_2", "step_z_3", "landing"])

class Measurement(unittest.TestCase):
    def test_step_x_metrics_on_fixture(self):
        odom, cmd, state = load()
        res = A.analyse(odom, cmd, state, px4_arm_times=A.load_px4_arm_times(FX / "px4_arm_times.txt"))
        sx = next(e for e in res["events"] if e["name"] == "step_x_1")
        self.assertEqual(sx["axis"], "x"); self.assertFalse(sx["axis_mismatch"])
        self.assertAlmostEqual(sx["start_m"], 2.006, delta=0.002)
        self.assertAlmostEqual(sx["final_m"], 3.003, delta=0.002)
        self.assertAlmostEqual(sx["tail"]["overshoot_m"], 0.054, delta=0.003)
        self.assertAlmostEqual(sx["tail"]["settle_s"], 1.84, delta=0.03)      # first in-band sample after the last excursion
        self.assertEqual(sx["tail"]["band_reentries"], 0)
        self.assertAlmostEqual(sx["goal"]["goal_m"], 3.006, delta=0.002)
        self.assertAlmostEqual(sx["goal"]["overshoot_m"], 0.052, delta=0.003)
        self.assertAlmostEqual(sx["goal"]["steady_state_error_m"], -0.002, delta=0.003)
        self.assertAlmostEqual(sx["goal"]["settle_0p05_s"], 3.29, delta=0.05)
        self.assertEqual(sx["goal"]["reentries_0p05"], 1)
        self.assertAlmostEqual(sx["commander_ramp_s"], 2.10, delta=0.03)
        self.assertAlmostEqual(sx["vehicle_time"]["settle_s"], 1.84 * res["time_scale"], delta=0.05)

    def test_time_scale_from_fixture(self):
        odom, cmd, state = load()
        res = A.analyse(odom, cmd, state, px4_arm_times=A.load_px4_arm_times(FX / "px4_arm_times.txt"))
        self.assertAlmostEqual(res["bag_arm_interval_s"], 76.32, delta=0.02)
        self.assertAlmostEqual(res["px4_arm_interval_s"], 100.87, delta=0.01)
        self.assertAlmostEqual(res["time_scale"], 1.3217, delta=0.002)
        self.assertIn("sysid 3", res["time_scale_source"])

    def test_velocity_tracking_gain_is_in_vehicle_time(self):
        odom, cmd, state = load()
        res = A.analyse(odom, cmd, state, px4_arm_times=A.load_px4_arm_times(FX / "px4_arm_times.txt"))
        sz = next(e for e in res["events"] if e["name"] == "step_z_1")
        self.assertAlmostEqual(sz["velocity_tracking"]["gain"], 1.01, delta=0.05)   # 1.336 if the ÷ time_scale is missing
        self.assertTrue(0.0 <= sz["velocity_tracking"]["lag_s"] <= 0.6)
        self.assertLess(sz["velocity_tracking"]["residual_rms_mps"], 0.15)

    def test_analyse_without_px4_times_assumes_scale_1(self):   # Review Focus 5
        odom, cmd, state = load()
        res = A.analyse(odom, cmd, state, px4_arm_times=None)
        self.assertEqual(res["time_scale"], 1.0)
        self.assertTrue(res["time_scale_source"].startswith("assumed 1.0"))
        sx = next(e for e in res["events"] if e["name"] == "step_x_1")
        self.assertEqual(sx["vehicle_time"]["settle_s"], sx["tail"]["settle_s"])

    def test_measure_flags_axis_mismatch(self):                  # Review Focus 2
        odom, cmd, state = load()
        swapped = [(t, y, x, z) for t, x, y, z in odom]          # the drone "moved" on y while x was commanded
        res = A.analyse(swapped, cmd, state)
        sx = next(e for e in res["events"] if e["name"] == "step_x_1")
        self.assertTrue(sx["axis_mismatch"]); self.assertEqual(sx["moved_most_axis"], "y")
        self.assertTrue(res["steps"]["x"]["any_axis_mismatch"])

    def test_settle_first_in_band_sample(self):
        seg = [(0.0, 0.0), (0.1, 0.5), (0.2, 0.95), (0.3, 1.12), (0.4, 1.05), (0.5, 1.0), (0.6, 1.0)]
        settle, reent, sat = A.settle_after_last_excursion(seg, 1.0, 0.1)
        self.assertAlmostEqual(settle, 0.4); self.assertEqual(reent, 1); self.assertFalse(sat)

    def test_steps_summary_gates_on_max(self):
        odom, cmd, state = load()
        res = A.analyse(odom, cmd, state, px4_arm_times=A.load_px4_arm_times(FX / "px4_arm_times.txt"))
        self.assertEqual(res["steps"]["x"]["n"], 1); self.assertEqual(res["steps"]["z"]["n"], 1)
        self.assertAlmostEqual(res["steps"]["x"]["settle_0p1_max_veh_s"], 1.84 * 1.3217, delta=0.06)
        self.assertEqual(res["steps"]["z"]["reentries_0p1_max"], 0)

class Cli(unittest.TestCase):
    def test_main_writes_json(self):
        with tempfile.TemporaryDirectory() as d:
            out = pathlib.Path(d) / "bag_analysis.json"
            rc = A.main(["--odom", str(FX / "drone_1_odom.csv"), "--cmd", str(FX / "drone_1_cmd.csv"),
                         "--state", str(FX / "drone_1_state.csv"), "--px4-arm-times", str(FX / "px4_arm_times.txt"), "-o", str(out)])
            self.assertEqual(rc, 0)
            j = json.loads(out.read_text())
            self.assertEqual(j["odom_msgs"], 8858); self.assertIn("steps", j)
