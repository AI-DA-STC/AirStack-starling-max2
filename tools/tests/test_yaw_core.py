# tools/tests/test_yaw_core.py
import glob, math, os, pathlib, subprocess, sys, tempfile, unittest
import numpy as np
HERE = pathlib.Path(__file__).resolve().parent
for p in (HERE, HERE.parent / "live"): sys.path.insert(0, str(p))
import yaw_core as Y
import synth_yaw as S

DUMP = HERE.parent / "live" / "ulog_yaw_dump.py"


class Frames(unittest.TestCase):
    def test_ned_to_enu(self):
        self.assertAlmostEqual(Y.ned_to_enu_deg(90.0), 0.0); self.assertAlmostEqual(Y.ned_to_enu_deg(0.0), 90.0)

    def test_unwrap_no_jump_at_seam(self):
        a = Y.unwrap_deg(np.array([170.0, 179.0, -179.0, -170.0])); self.assertTrue(np.all(np.diff(a) > 0)); self.assertAlmostEqual(a[-1], 190.0)

    def test_unwrap_keeps_leading_nan(self):
        a = Y.unwrap_deg(np.array([np.nan, 170.0, -179.0]))
        self.assertTrue(np.isnan(a[0])); self.assertAlmostEqual(a[2], 181.0)


class Pulses(unittest.TestCase):
    def test_finds_both_directions_and_release(self):
        with tempfile.TemporaryDirectory() as d:
            csv = S.px4_csv(pathlib.Path(d) / "p.csv", [dict(onset=20.0, dur=1.0, sign=+1), dict(onset=40.0, dur=1.0, sign=-1)])
            r = Y.analyse(csv)
        self.assertEqual([p["sign"] for p in r["pulses"]], [1, -1]); self.assertTrue(all(p["released"] for p in r["pulses"]))
        self.assertAlmostEqual(r["pulses"][0]["release_s"] - r["pulses"][0]["onset_s"], 1.0, delta=0.06)   # 20 Hz ff -> 50 ms
        self.assertAlmostEqual(r["pulses"][0]["plateau_dps"], 57.3, delta=0.5)
        self.assertAlmostEqual(r["pulses"][0]["plateau_meas_dps"], 57.3, delta=2.0)
        self.assertEqual(r["marker"], "ff_dps")

    def test_underdamped_ring_is_measured(self):
        with tempfile.TemporaryDirectory() as d:
            csv = S.px4_csv(pathlib.Path(d) / "p.csv", [dict(onset=20.0, dur=1.0, sign=+1, zeta=0.1, f_hz=0.8)])
            p = Y.analyse(csv)["pulses"][0]
        self.assertGreater(p["overshoot_deg"], 8.0); self.assertGreaterEqual(p["ring_crossings"], 3)
        self.assertAlmostEqual(p["ring_hz"], 0.8, delta=0.15); self.assertGreater(p["settle_s"], 2.0)
        self.assertGreater(p["peak_rate_dps"], 30.0)                          # it swings back hard
        self.assertGreater(p["peak_rate_abs_dps"], 50.0)                      # includes the turn still under way at release

    def test_well_damped_pulse_settles_fast(self):
        with tempfile.TemporaryDirectory() as d:
            csv = S.px4_csv(pathlib.Path(d) / "p.csv", [dict(onset=20.0, dur=1.0, sign=+1, zeta=0.9, f_hz=1.5)])
            p = Y.analyse(csv)["pulses"][0]
        self.assertLess(p["overshoot_deg"], 3.0); self.assertLessEqual(p["ring_crossings"], 1); self.assertLess(p["settle_s"], 2.0)
        self.assertTrue(math.isnan(p["ring_hz"]))
        self.assertLess(p["peak_rate_dps"], 15.0)     # Ruling: bounce-back rate (2.4 deg back at ~9 deg/s), not the stop itself
        self.assertLess(p["xy_drift_m"], 1e-9)

    def test_negative_pulse_overshoot_is_along_its_own_turn(self):
        with tempfile.TemporaryDirectory() as d:
            csv = S.px4_csv(pathlib.Path(d) / "p.csv", [dict(onset=20.0, dur=1.0, sign=-1, zeta=0.1, f_hz=0.8)])
            p = Y.analyse(csv)["pulses"][0]
        self.assertGreater(p["overshoot_deg"], 8.0); self.assertLess(p["turn_deg"], -40.0)
        self.assertGreater(p["peak_rate_dps"], 30.0)

    def test_pulse_across_the_seam_has_small_overshoot(self):              # Review Focus 1
        # 211.5 + 57.3 = 268.8 deg ENU at release; the 2.4 deg overshoot passes ENU 270 = NED +-180, where the ulog
        # heading wraps. Without the unwrap the overshoot samples read ~-89 deg ENU: a ~358 deg "undershoot".
        with tempfile.TemporaryDirectory() as d:
            csv = S.px4_csv(pathlib.Path(d) / "p.csv", [dict(onset=20.0, dur=1.0, sign=+1, zeta=0.9, f_hz=1.5)], seam=True)
            _, cols, data = Y.read_px4_csv(csv)
            h = data[:, cols.index("heading_ned_deg")]
            self.assertGreater(np.nanmax(np.abs(np.diff(h))), 300.0)          # the fixture really wraps in NED
            p = Y.analyse(csv)["pulses"][0]
        self.assertLess(p["overshoot_deg"], 3.0); self.assertGreater(p["overshoot_deg"], 1.5)
        self.assertLess(abs(p["undershoot_deg"]), 3.0)
        self.assertAlmostEqual(p["turn_deg"], 57.3, delta=4.0); self.assertEqual(p["post_status"], "ok")

    def test_small_second_swing_pins_the_ring_hysteresis(self):
        # zeta 0.5 at 0.8 Hz: 6.2 deg overshoot, then one ~1.0 deg swing back, then 0.17 deg (below the 0.5 deg
        # hysteresis). Exactly one crossing; a 3.0 deg hysteresis would hide the swing (0 crossings).
        with tempfile.TemporaryDirectory() as d:
            csv = S.px4_csv(pathlib.Path(d) / "p.csv", [dict(onset=20.0, dur=1.0, sign=+1, zeta=0.5, f_hz=0.8)])
            p = Y.analyse(csv)["pulses"][0]
        self.assertAlmostEqual(p["undershoot_deg"], 1.0, delta=0.3)
        self.assertEqual(p["ring_crossings"], 1)
        self.assertEqual(Y.RING_HYST_DEG, 0.5)

    def test_xy_drift_is_measured_from_the_onset_position(self):
        with tempfile.TemporaryDirectory() as d:
            csv = S.px4_csv(pathlib.Path(d) / "p.csv", [dict(onset=20.0, dur=1.0, sign=+1, zeta=0.9, f_hz=1.5)], xy_ramp_mps=(0.006, 0.008))
            p = Y.analyse(csv)["pulses"][0]
        self.assertAlmostEqual(p["xy_drift_m"], 0.010 * (p["t_end_s"] - p["onset_s"]), delta=0.002)
        self.assertGreater(p["xy_drift_m"], 0.1)

    def test_nan_in_the_post_release_window_is_unverified_not_zero(self):   # fail closed: no data is never "settled"
        for gap in ((21.2, 22.0), (21.0, 40.0)):                             # a gap after release; everything after release
            with tempfile.TemporaryDirectory() as d:
                csv = S.px4_csv(pathlib.Path(d) / "p.csv", [dict(onset=20.0, dur=1.0, sign=+1, zeta=0.1, f_hz=0.8)], nan_window=gap)
                p = Y.analyse(csv)["pulses"][0]
            self.assertTrue(p["released"], gap); self.assertEqual(p["post_status"], "nan_in_window", gap)
            for k in Y.POST_KEYS:
                self.assertIsNone(p[k], (gap, k))

    def test_short_post_release_window_is_unverified(self):
        # data ends 1.24 s after release on a ringing drone: settle would read ~1.1 s and pass a 2 s gate
        with tempfile.TemporaryDirectory() as d:
            csv = S.px4_csv(pathlib.Path(d) / "p.csv", [dict(onset=20.0, dur=1.0, sign=+1, zeta=0.1, f_hz=0.8)], tail_s=1.24)
            p = Y.analyse(csv)["pulses"][0]
        self.assertEqual(p["post_status"], "short_window"); self.assertLess(p["window_s"], Y.MIN_POST_WINDOW_S)
        for k in Y.POST_KEYS:
            self.assertIsNone(p[k], k)
        self.assertEqual(Y.MIN_POST_WINDOW_S, 3.0)
        with tempfile.TemporaryDirectory() as d:                             # just long enough -> measured
            csv = S.px4_csv(pathlib.Path(d) / "p.csv", [dict(onset=20.0, dur=1.0, sign=+1, zeta=0.9, f_hz=1.5)], tail_s=3.2)
            p = Y.analyse(csv)["pulses"][0]
        self.assertEqual(p["post_status"], "ok"); self.assertIsNotNone(p["settle_s"])

    def test_settle_time_is_in_vehicle_time_not_wall(self):                 # Review Focus 2
        with tempfile.TemporaryDirectory() as d:
            csv = S.px4_csv(pathlib.Path(d) / "p.csv", [dict(onset=20.0, dur=1.0, sign=+1, zeta=0.3, f_hz=0.8)])
            a = Y.analyse(csv); b = Y.analyse(csv, wall_stamps=S.wall_stamps(a["pulses"], scale=0.36))
        self.assertEqual(a["pulses"][0]["settle_s"], b["pulses"][0]["settle_s"])
        self.assertAlmostEqual(b["time_scale"][0], 0.36, delta=0.03)
        self.assertTrue(math.isnan(a["time_scale"][0]))                     # no wall stamps -> no scale, never 1.0

    def test_unreleased_pulse_is_unverified(self):                           # Review Focus 3
        with tempfile.TemporaryDirectory() as d:
            csv = S.px4_csv(pathlib.Path(d) / "p.csv", [dict(onset=20.0, dur=1.0, sign=+1), dict(onset=40.0, dur=None, sign=-1)])
            r = Y.analyse(csv)
        self.assertEqual(len(r["pulses"]), 2)                                # named, not silently skipped
        self.assertFalse(r["pulses"][1]["released"]); self.assertIsNone(r["pulses"][1]["settle_s"])
        self.assertIsNone(r["pulses"][1]["release_s"]); self.assertEqual(r["pulses"][1]["post_status"], "unreleased")
        for k in ("overshoot_deg", "peak_rate_dps", "ring_crossings"):
            self.assertIsNone(r["pulses"][1][k], k)
        self.assertTrue(r["pulses"][0]["released"])

    def test_sign_follows_enu(self):                                         # Review Focus 5
        with tempfile.TemporaryDirectory() as d:
            csv = S.px4_csv(pathlib.Path(d) / "p.csv", [dict(onset=20.0, dur=1.0, sign=+1)])
            p = Y.analyse(csv)["pulses"][0]
        self.assertEqual(p["sign"], 1); self.assertGreater(p["turn_deg"], 40.0)    # ENU heading rose
        with tempfile.TemporaryDirectory() as d:
            csv = S.px4_csv(pathlib.Path(d) / "p.csv", [dict(onset=20.0, dur=1.0, sign=+1)], sign_flip=True)
            p = Y.analyse(csv)["pulses"][0]
        self.assertEqual(p["sign"], 1)            # the command's sign comes from the setpoint, not the heading
        self.assertLess(p["turn_deg"], -40.0)     # a flipped frame shows as a negative turn for a + command

    def test_falls_back_to_trajectory_yawspeed_when_ff_is_zero(self):       # U3
        with tempfile.TemporaryDirectory() as d:
            csv = S.px4_csv(pathlib.Path(d) / "p.csv", [dict(onset=20.0, dur=1.0, sign=-1)], ff_zero=True)
            r = Y.analyse(csv)
        self.assertEqual(r["marker"], "yawspeed_sp_dps"); self.assertEqual([p["sign"] for p in r["pulses"]], [-1])
        self.assertAlmostEqual(r["pulses"][0]["release_s"] - r["pulses"][0]["onset_s"], 1.0, delta=0.21)   # 5 Hz

    def test_no_pulses_is_empty_not_error(self):
        with tempfile.TemporaryDirectory() as d:
            csv = S.px4_csv(pathlib.Path(d) / "p.csv", [])
            r = Y.analyse(csv)
        self.assertEqual(r["pulses"], []); self.assertEqual(r["groups"], []); self.assertEqual(r["time_scale"], [])

    def test_missing_csv_raises_not_empty(self):                             # Review Focus 4: never "no pulses = fine"
        with self.assertRaises(FileNotFoundError):
            Y.analyse("/nonexistent/px4_drone_1.csv")

    def test_gains_in_force_and_groups(self):
        changes = [(30.0, "MC_YAW_P", 2.0)]
        hdr = {"MC_YAW_P": 2.8, "MC_YAWRATE_P": 0.07, "MC_YAWRATE_I": 0.5, "MC_YAWRATE_D": 0.0, "MC_YAWRATE_K": 1.0}
        self.assertEqual(Y.gains_in_force(changes, 20.0, hdr)["MC_YAW_P"], 2.8); self.assertEqual(Y.gains_in_force(changes, 40.0, hdr)["MC_YAW_P"], 2.0)
        self.assertEqual(Y.gains_in_force(changes, 40.0, hdr)["MC_YAWRATE_I"], 0.5)
        ps = [dict(onset_s=1, gains=dict(hdr)), dict(onset_s=2, gains=dict(hdr, MC_YAW_P=2.0)), dict(onset_s=3, gains=dict(hdr))]
        g = Y.group_by_gains(ps)
        self.assertEqual([len(x[1]) for x in g], [2, 1]); self.assertEqual(dict(g[0][0])["MC_YAW_P"], 2.8)

    def test_analyse_reads_param_changes_in_vehicle_time(self):
        with tempfile.TemporaryDirectory() as d:
            csv = S.px4_csv(pathlib.Path(d) / "p.csv", [dict(onset=20.0, dur=1.0, sign=+1), dict(onset=40.0, dur=1.0, sign=-1)])
            ch = pathlib.Path(d) / "px4_param_changes.txt"
            ch.write_text("# MC_YAW* changes, vehicle time\n101.0 MC_YAW_P 2.8\n130.0 MC_YAW_P 2.0\n")   # synth clock starts at 100 s
            r = Y.analyse(csv, changes_path=ch)
        self.assertEqual([p["gains"]["MC_YAW_P"] for p in r["pulses"]], [2.8, 2.0])
        self.assertEqual(len(r["groups"]), 2); self.assertEqual(r["header_gains"]["MC_YAWRATE_P"], 0.07)

    def test_tap_direction(self):
        t = np.linspace(0, 2, 200); x_ned = np.zeros_like(t); y_ned = 0.5 * t      # +east in ENU = +y NED
        r = Y.tap_check(t, x_ned, y_ned, np.full_like(t, 90.0), 0.0, 2.0)
        self.assertAlmostEqual(r["direction_err_deg"], 0.0, delta=1.0); self.assertAlmostEqual(r["heading_change_deg"], 0.0, delta=0.1)
        r = Y.tap_check(t, 0.5 * t, np.zeros_like(t), np.full_like(t, 90.0), 0.0, 2.0)  # +north = 90 deg off room +x (orbit symptom)
        self.assertAlmostEqual(r["direction_err_deg"], 90.0, delta=1.0)


class Dumper(unittest.TestCase):
    def test_hold_onto_clock_and_yaw_of_qd(self):
        import ulog_yaw_dump as D
        held = D.hold_onto(np.array([0.0, 1.0, 2.0]), np.array([0.5, 1.5]), np.array([10.0, 20.0]))
        self.assertTrue(np.isnan(held[0])); self.assertEqual(list(held[1:]), [10.0, 20.0])
        self.assertAlmostEqual(D.yaw_of_qd(math.cos(math.pi / 4), 0, 0, math.sin(math.pi / 4)), 90.0, places=6)   # PX4 q = (w, x, y, z)
        self.assertAlmostEqual(float(D.to_deg(math.pi)), 180.0)

    def test_unreadable_ulog_exit_2(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertTrue(DUMP.exists())
            bad = pathlib.Path(d) / "x.ulg"; bad.write_bytes(b"not a ulog")
            r = subprocess.run([sys.executable, str(DUMP), str(bad), "-o", str(pathlib.Path(d) / "o.csv")], capture_output=True, text=True, timeout=60)
        self.assertIn(r.returncode, (2, 4), r.stderr)          # 4 = pyulog not installed on this python (sim.sh retries in isaac-sim)
        self.assertFalse((pathlib.Path(d) / "o.csv").exists())

    @unittest.skipUnless(glob.glob(os.path.expanduser("~/flight_logs/sim/*/drone_1_sysid2_*.ulg")), "no sim ulog on this machine")
    def test_real_sim_ulog_dumps_and_analyses_without_pulses(self):
        try:
            import pyulog  # noqa: F401
        except ImportError:
            self.skipTest("pyulog not installed")
        ulg = sorted(glob.glob(os.path.expanduser("~/flight_logs/sim/sim_crossing_run2/drone_1_sysid2_*.ulg"))
                     or glob.glob(os.path.expanduser("~/flight_logs/sim/*/drone_1_sysid2_*.ulg")))[0]
        with tempfile.TemporaryDirectory() as d:
            out, par = pathlib.Path(d) / "px4.csv", pathlib.Path(d) / "par.txt"
            r = subprocess.run([sys.executable, str(DUMP), ulg, "-o", str(out), "--params-out", str(par)], capture_output=True, text=True, timeout=300)
            self.assertEqual(r.returncode, 0, r.stderr)
            meta, cols, data = Y.read_px4_csv(out)
            self.assertEqual(",".join(cols), S.COLUMNS); self.assertGreater(len(data), 1000)
            for k in ("source", "sysid", "MC_YAW_P", "MC_YAWRATE_P", "MC_YAWRATE_I", "MC_YAWRATE_D", "MC_YAWRATE_K", "arm_s", "disarm_s"):
                self.assertIn(k, meta, k)
            self.assertTrue(np.all(np.diff(data[:, 0]) >= 0))
            h = data[:, 1]; self.assertTrue(np.nanmax(np.abs(h)) <= 180.0 + 1e-6)
            Y.analyse(out, changes_path=par)                      # no crash; a crossing flight may or may not have pulses


if __name__ == "__main__":
    unittest.main()
