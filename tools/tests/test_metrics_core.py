# tools/tests/test_metrics_core.py
import math, pathlib, sys, tempfile, unittest
import numpy as np
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "live"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import metrics_core as M
import synth_crossing as synth
class Geometry(unittest.TestCase):
    def test_world_position_adds_offset(self):
        np.testing.assert_allclose(M.world_position([1, 2, 3], [-2, 0, 0]), [-1, 2, 3])
    def test_pairwise_distances_three_drones(self):
        pos = {"drone_1": np.array([0., 0, 1]), "drone_2": np.array([3., 4, 1]), "drone_3": np.array([0., 0, 2])}
        d = M.pairwise_distances(pos); self.assertEqual(set(d), {"d_12", "d_13", "d_23"}); self.assertAlmostEqual(d["d_12"], 5.0); self.assertAlmostEqual(d["d_13"], 1.0)
    def test_stale_drone_gives_nan_distance(self):                       # Review Focus 1
        f = synth.frame_at(5.0); f.stale = frozenset({"drone_3"})
        self.assertTrue(math.isnan(M.pair_distance(f, "drone_1", "drone_3"))); self.assertFalse(math.isnan(M.pair_distance(f, "drone_1", "drone_2")))
    def test_fence_margin_is_distance_to_nearest_face(self):
        f = synth.frame_at(0.0); f.pos = {"drone_1": np.array([4.5, 0, 1.0])}; f.params = {"fence_min": [-3, -6, 0], "fence_max": [5, 5, 3]}
        self.assertAlmostEqual(M.fence_margin(f), 0.5)
    def test_antipode_and_goal_distance(self):
        np.testing.assert_allclose(M.antipode(np.array([0.9, 0, 1.5]), np.array([0, 0, 1.5])), [-0.9, 0, 1.5])
        self.assertTrue(math.isnan(M.goal_distance(synth.frame_at(0.5), "drone_1")))   # before phase 2
class Phase(unittest.TestCase):
    def test_phase_transitions(self):
        self.assertEqual(M.phase_from_status(["IDLE"] * 3, False, 0), 0)
        self.assertEqual(M.phase_from_status(["ARMING", "IDLE", "IDLE"], False, 0), 1)
        self.assertEqual(M.phase_from_status(["ACTIVE"] * 3, True, 1), 2)
        self.assertEqual(M.phase_from_status(["LANDING", "ACTIVE", "ACTIVE"], False, 2), 3)
        self.assertEqual(M.phase_from_status(["IDLE"] * 3, False, 3), 0)
class Params(unittest.TestCase):
    def test_parse_param_array_ros2_format(self):
        self.assertEqual(M.parse_param_array("Double array value is: array('d', [-2.0, 0.0, 0.0, 0.0, 0.0, 0.0, 2.0, 0.0, 0.0])"), [-2.0, 0, 0, 0, 0, 0, 2.0, 0, 0])
    def test_offset_sanity_detects_wrong_offset(self):
        ok = M.offset_sanity({"drone_1": [-1.0, 0, 0.1]}, {"drone_1": [1.0, 0, 0.1]}, {"drone_1": np.array([-2.0, 0, 0])}); self.assertEqual(ok, [])
        bad = M.offset_sanity({"drone_1": [1.0, 0, 0.1]}, {"drone_1": [1.0, 0, 0.1]}, {"drone_1": np.array([-2.0, 0, 0])}); self.assertEqual(len(bad), 1); self.assertIn("drone_1", bad[0])
class TrackerAndCsv(unittest.TestCase):
    def test_running_min_and_min_distance_on_synthetic_run(self):
        cols, rows = synth.frames(); i = cols.index("min_pair_distance_running")
        self.assertAlmostEqual(rows[-1, i], 1.25, places=2); self.assertTrue(np.all(np.diff(rows[:, i]) <= 1e-9))
    def test_csv_roundtrip_keeps_meta_and_columns(self):
        cols, rows = synth.frames()
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d) / "metrics.csv"; synth.write_csv(p, cols, rows, {"offsets": "-2,0,0,0,0,0,2,0,0", "t0_unix": "1.5"})
            meta, cols2, rows2 = M.read_metrics_csv(p); self.assertEqual(cols2, cols); self.assertEqual(meta["offsets"], "-2,0,0,0,0,0,2,0,0"); np.testing.assert_allclose(rows2, rows, atol=1e-4)
    def test_read_metrics_csv_without_offsets_is_error(self):
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d) / "m.csv"; p.write_text("t_s,phase,d_12\n0,0,1\n")
            with self.assertRaises(M.MetricsCsvError): M.read_metrics_csv(p)
class CrossCheck(unittest.TestCase):
    def test_identical_runs_agree(self):
        cols, rows = synth.frames(); cr = M.crosscheck(cols, rows, cols, rows.copy(), synth.SERIES)
        self.assertTrue(all(r.ok for r in cr)); self.assertEqual({r.name for r in cr}, {s.name for s in synth.SERIES} | {"min_pair_distance_running"})
    def test_min_distance_off_by_3cm_fails(self):
        cols, rows = synth.frames(); bag = rows.copy(); bag[:, cols.index("min_pair_distance")] -= 0.03
        bad = [r for r in M.crosscheck(cols, rows, cols, bag, synth.SERIES) if not r.ok]; self.assertIn("min_pair_distance", [r.name for r in bad])
    def test_flag_column_one_sample_skew_is_ok(self):
        cols, rows = synth.frames(); bag = rows.copy(); j = cols.index("cbf_drone_1"); k = int(np.argmax(bag[:, j])); bag[k, j] = 0; bag[k - 1, j] = 1
        self.assertTrue(next(r for r in M.crosscheck(cols, rows, cols, bag, synth.SERIES) if r.name == "cbf_drone_1").ok)
    def test_crosscheck_unpaired_rows_flagged(self):                     # Review Focus 5
        cols, rows = synth.frames(); bag = rows[::2]                        # bag lost every other row → half the live rows unpaired
        cr = M.crosscheck(cols, rows, cols, bag, synth.SERIES); self.assertTrue(all(r.unpaired_frac > 0.05 for r in cr)); self.assertFalse(any(r.ok for r in cr))

if __name__ == "__main__":
    unittest.main()
