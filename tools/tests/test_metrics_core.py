# tools/tests/test_metrics_core.py
import math
import pathlib
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "live"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import metrics_core as M
import synth_crossing as synth


def const_series(kind="continuous", tol=0.25):
    return [M.Series("x", lambda f: 0.0, tol, "", kind)]


def pair_arrays(live_vals, bag_vals, bag_dt_shift=0.0):
    """Two (t_s, phase, x) arrays one second apart in time; the bag's time stamps are shifted."""
    n = len(live_vals)
    t = np.arange(n, dtype=float)
    live = np.column_stack([t, np.full(n, 2.0), live_vals])
    bag = np.column_stack([t + bag_dt_shift, np.full(n, 2.0), bag_vals])
    return ["t_s", "phase", "x"], live, bag


def check(live_vals, bag_vals, kind="continuous", tol=0.25, shift=0.0, t_tol=0.05):
    cols, live, bag = pair_arrays(live_vals, bag_vals, shift)
    return M.crosscheck(cols, live, cols, bag, const_series(kind, tol), t_tol=t_tol)[0]


def seen_tracker(t_seen, status_phase2=True):
    """Tracker with all drones odometry-fed at the given times (None = never seen)."""
    tr = synth.make_tracker()
    tr.update_status(synth.straight_status(2.0 if status_phase2 else 0.0))
    pos, vel = synth.straight_world(2.0)
    for d in synth.DRONES:
        if t_seen[d] is not None:
            tr.update_odom(d, t_seen[d], pos[d] - tr.offsets[d], vel[d])
    return tr


class Geometry(unittest.TestCase):
    def test_world_position_adds_offset(self):
        np.testing.assert_allclose(M.world_position([1, 2, 3], [-2, 0, 0]), [-1, 2, 3])

    def test_pairwise_distances_three_drones(self):
        pos = {"drone_1": np.array([0., 0, 1]), "drone_2": np.array([3., 4, 1]), "drone_3": np.array([0., 0, 2])}
        d = M.pairwise_distances(pos)
        self.assertEqual(set(d), {"d_12", "d_13", "d_23"})
        self.assertAlmostEqual(d["d_12"], 5.0)
        self.assertAlmostEqual(d["d_13"], 1.0)

    def test_pair_key_is_sorted_by_name(self):
        self.assertEqual(M.pair_key("drone_2", "drone_1"), "d_12")
        self.assertEqual(M.pair_key("drone_3", "drone_1"), "d_13")

    def test_stale_drone_gives_nan_distance(self):
        f = synth.frame_at(5.0)
        f.stale = frozenset({"drone_3"})
        self.assertTrue(math.isnan(M.pair_distance(f, "drone_1", "drone_3")))
        self.assertFalse(math.isnan(M.pair_distance(f, "drone_1", "drone_2")))

    def test_stale_drone_makes_pairwise_distances_nan_for_its_pairs(self):
        f = synth.frame_at(5.0)
        d = M.pairwise_distances(f.pos, frozenset({"drone_3"}))
        self.assertTrue(math.isnan(d["d_13"]) and math.isnan(d["d_23"]))
        self.assertFalse(math.isnan(d["d_12"]))

    def test_stale_drone_makes_min_pair_distance_nan_not_min_of_the_rest(self):
        f = synth.frame_at(5.0)
        self.assertFalse(math.isnan(M.min_pair_distance(f)))
        f.stale = frozenset({"drone_3"})
        self.assertTrue(math.isnan(M.min_pair_distance(f)))

    def test_speed_is_norm_of_twist_and_nan_when_stale(self):
        f = synth.frame_at(5.0)
        f.vel = {"drone_1": np.array([3.0, 4.0, 0.0])}
        self.assertAlmostEqual(M.speed_of(f, "drone_1"), 5.0)
        f.stale = frozenset({"drone_1"})
        self.assertTrue(math.isnan(M.speed_of(f, "drone_1")))

    def _fence(self, p):
        f = synth.frame_at(0.0)
        f.pos = {"drone_1": np.array(p, dtype=float)}
        f.params = {"fence_min": [-3, -6, 0], "fence_max": [5, 5, 3]}
        return M.fence_margin(f)

    def test_fence_margin_upper_face_nearest(self):
        self.assertAlmostEqual(self._fence([4.5, 0, 1.0]), 0.5)

    def test_fence_margin_lower_face_nearest(self):
        self.assertAlmostEqual(self._fence([-2.9, 0, 1.0]), 0.1)
        self.assertAlmostEqual(self._fence([0, 0, 0.2]), 0.2)

    def test_fence_margin_negative_outside(self):
        self.assertAlmostEqual(self._fence([5.3, 0, 1.0]), -0.3)

    def test_fence_margin_ignores_stale_drones(self):
        f = synth.frame_at(0.0)
        f.pos = {"drone_1": np.array([4.9, 0, 1.0]), "drone_2": np.array([0.0, 0, 1.5])}
        f.params = {"fence_min": [-3, -6, 0], "fence_max": [5, 5, 3]}
        f.stale = frozenset({"drone_1"})
        self.assertAlmostEqual(M.fence_margin(f), 1.5)

    def test_antipode_is_point_reflection_about_center(self):
        np.testing.assert_allclose(M.antipode(np.array([0.9, 0, 1.5]), np.array([0, 0, 1.5])), [-0.9, 0, 1.5])

    def test_arena_center_is_midpoint(self):
        np.testing.assert_allclose(M.arena_center({"arena_low": [-3, -1, 0.5], "arena_high": [1, 3, 2.5]}), [-1, 1, 1.5])

    def test_goal_distance_is_nan_before_phase_2(self):
        self.assertTrue(math.isnan(M.goal_distance(synth.frame_at(0.5), "drone_1")))

    def test_goal_distance_is_distance_to_antipode_of_start(self):
        f = synth.frame_at(5.0)
        f.start_pos = {"drone_1": np.array([0.9, 0.0, 1.5])}
        f.pos = {"drone_1": np.array([-0.9, 0.5, 1.5])}
        self.assertAlmostEqual(M.goal_distance(f, "drone_1"), 0.5)


class Phase(unittest.TestCase):
    def test_idle_is_phase_0(self):
        self.assertEqual(M.phase_from_status(["IDLE"] * 3, False, 0), 0)

    def test_arming_is_phase_1(self):
        self.assertEqual(M.phase_from_status(["ARMING", "IDLE", "IDLE"], False, 0), 1)

    def test_ascend_is_phase_1(self):
        self.assertEqual(M.phase_from_status(["ASCEND"] * 3, False, 0), 1)

    def test_mission_active_is_phase_2(self):
        self.assertEqual(M.phase_from_status(["ACTIVE"] * 3, True, 1), 2)

    def test_landing_after_mission_is_phase_3(self):
        self.assertEqual(M.phase_from_status(["LANDING", "ACTIVE", "ACTIVE"], False, 2), 3)

    def test_all_idle_after_landing_is_phase_0(self):
        self.assertEqual(M.phase_from_status(["IDLE"] * 3, False, 3), 0)

    def test_unknown_states_keep_previous_phase(self):
        self.assertEqual(M.phase_from_status(["HOVER"] * 3, False, 2), 2)


class Params(unittest.TestCase):
    def test_parse_param_array_ros2_format(self):
        txt = "Double array value is: array('d', [-2.0, 0.0, 0.0, 0.0, 0.0, 0.0, 2.0, 0.0, 0.0])"
        self.assertEqual(M.parse_param_array(txt), [-2.0, 0, 0, 0, 0, 0, 2.0, 0, 0])

    def test_parse_param_array_plain_brackets(self):
        self.assertEqual(M.parse_param_array("[-2.0, 0.5e1]"), [-2.0, 5.0])

    def test_parse_param_scalar_real_ros2_line(self):
        self.assertEqual(M.parse_param_scalar("Double value is: 6.0"), 6.0)
        self.assertEqual(M.parse_param_scalar("Double value is: 0.55"), 0.55)

    def test_parse_param_scalar_negative_and_integer(self):
        self.assertEqual(M.parse_param_scalar("Integer value is: -3"), -3.0)

    def test_parse_param_scalar_on_vector_line_takes_last_number(self):
        self.assertEqual(M.parse_param_scalar("Double array value is: array('d', [1.0, 2.0, 3.5])"), 3.5)

    def test_offsets_by_drone_keeps_drone_order(self):
        o = M.offsets_by_drone([1, 2, 3, 4, 5, 6, 7, 8, 9], ["drone_1", "drone_2", "drone_3"])
        np.testing.assert_allclose(o["drone_1"], [1, 2, 3])
        np.testing.assert_allclose(o["drone_2"], [4, 5, 6])
        np.testing.assert_allclose(o["drone_3"], [7, 8, 9])

    def test_offsets_by_drone_wrong_length_is_error(self):
        with self.assertRaises(ValueError):
            M.offsets_by_drone([1, 2, 3], ["drone_1", "drone_2"])

    def test_offset_sanity_accepts_matching_offset(self):
        r = M.offset_sanity({"drone_1": [-1.0, 0, 0.1]}, {"drone_1": [1.0, 0, 0.1]}, {"drone_1": np.array([-2.0, 0, 0])})
        self.assertEqual(r, [])

    def test_offset_sanity_detects_wrong_offset(self):
        bad = M.offset_sanity({"drone_1": [1.0, 0, 0.1]}, {"drone_1": [1.0, 0, 0.1]}, {"drone_1": np.array([-2.0, 0, 0])})
        self.assertEqual(len(bad), 1)
        self.assertIn("drone_1", bad[0])

    def test_offset_sanity_tolerance_boundary(self):
        off = {"drone_1": np.array([0.0, 0, 0])}
        self.assertEqual(M.offset_sanity({"drone_1": [0.04, 0, 0]}, {"drone_1": [0, 0, 0]}, off), [])
        self.assertEqual(len(M.offset_sanity({"drone_1": [0.06, 0, 0]}, {"drone_1": [0, 0, 0]}, off)), 1)


class TrackerStatusAndStale(unittest.TestCase):
    def test_never_seen_drone_makes_min_pair_distance_and_running_nan(self):
        tr = seen_tracker({"drone_1": 2.0, "drone_2": 2.0, "drone_3": None})
        r = tr.row(2.0)
        self.assertTrue(math.isnan(r["min_pair_distance"]))
        self.assertTrue(math.isnan(r["min_pair_distance_running"]))
        self.assertTrue(math.isnan(r["d_13"]) and math.isnan(r["d_23"]))
        self.assertFalse(math.isnan(r["d_12"]))
        self.assertTrue(math.isnan(r["speed_drone_3"]))

    def test_old_stamp_makes_row_nan_and_boundary_is_half_a_second(self):
        tr = seen_tracker({"drone_1": 2.0, "drone_2": 2.0, "drone_3": 1.4})
        self.assertTrue(math.isnan(tr.row(2.0)["min_pair_distance"]))        # 0.6 s old
        tr = seen_tracker({"drone_1": 2.0, "drone_2": 2.0, "drone_3": 1.5})
        self.assertFalse(math.isnan(tr.row(2.0)["min_pair_distance"]))       # exactly 0.5 s old

    def test_running_min_survives_a_stale_row(self):
        tr = seen_tracker({"drone_1": 2.0, "drone_2": 2.0, "drone_3": 2.0})
        good = tr.row(2.0)["min_pair_distance"]
        self.assertTrue(math.isnan(tr.row(3.0)["min_pair_distance_running"]))
        pos, vel = synth.straight_world(2.0)
        for d in synth.DRONES:
            tr.update_odom(d, 3.0, pos[d] - tr.offsets[d], vel[d])
        self.assertAlmostEqual(tr.row(3.0)["min_pair_distance_running"], good)

    def test_running_min_counts_phase_2_only(self):
        tr = seen_tracker({d: 2.0 for d in synth.DRONES}, status_phase2=False)
        pos, vel = synth.straight_world(2.0)
        close = {d: pos["drone_1"] - tr.offsets[d] + np.array([0.1 * i, 0.0, 0.0]) for i, d in enumerate(synth.DRONES)}
        for d in synth.DRONES:                                   # phase 0, drones 0.1 m apart (on the pads)
            tr.update_odom(d, 2.0, close[d], vel[d])
        r = tr.row(2.0)
        self.assertEqual(r["phase"], 0.0); self.assertTrue(math.isnan(r["min_pair_distance_running"]))      # before
        tr.update_status(synth.straight_status(2.0))
        for d in synth.DRONES:
            tr.update_odom(d, 3.0, pos[d] - tr.offsets[d], vel[d])
        r = tr.row(3.0); during = r["min_pair_distance_running"]
        self.assertEqual(r["phase"], 2.0); self.assertAlmostEqual(during, r["min_pair_distance"])           # during
        tr.update_status({"drones": [{"state": "LANDING"}], "mission_active": False, "cbf": {"emergency": False}, "fence_breached": False})
        for d in synth.DRONES:
            tr.update_odom(d, 4.0, close[d], vel[d])
        r = tr.row(4.0)
        self.assertEqual(r["phase"], 3.0); self.assertLess(r["min_pair_distance"], 0.5)
        self.assertAlmostEqual(r["min_pair_distance_running"], during)                                      # after: frozen

    def test_update_status_reads_emergency_and_fence_breached(self):
        tr = synth.make_tracker()
        tr.update_status({"drones": [{"state": "ACTIVE"}], "mission_active": True, "cbf": {"emergency": True}, "fence_breached": True})
        f = tr.frame(0.0)
        self.assertTrue(f.emergency and f.fence_breached)
        tr.update_status({"drones": [{"state": "ACTIVE"}], "mission_active": True, "cbf": {"emergency": False}, "fence_breached": False})
        f = tr.frame(0.0)
        self.assertFalse(f.emergency or f.fence_breached)

    def test_update_cbf_strips_whitespace_and_empty(self):
        tr = synth.make_tracker()
        tr.update_cbf(" drone_1 , drone_3 ,")
        self.assertEqual(tr.frame(0.0).cbf_active, frozenset({"drone_1", "drone_3"}))
        tr.update_cbf("")
        self.assertEqual(tr.frame(0.0).cbf_active, frozenset())

    def test_start_pos_captured_on_transition_into_phase_2_only(self):
        tr = synth.make_tracker()
        tr.update_status(synth.straight_status(0.5))                          # ASCEND, phase 1
        p_early, v = synth.straight_world(0.5)
        for d in synth.DRONES:
            tr.update_odom(d, 0.5, np.array([9.0, 9.0, 9.0]), v[d])          # junk positions, must not be captured
        self.assertEqual(tr.frame(0.5).start_pos, {})
        p_start, v = synth.straight_world(1.0)
        for d in synth.DRONES:
            tr.update_odom(d, 1.0, p_start[d] - tr.offsets[d], v[d])
        tr.update_status(synth.straight_status(1.0))                          # mission_active, phase 2
        f = tr.frame(1.0)
        self.assertEqual(f.phase, 2)
        for d in synth.DRONES:
            np.testing.assert_allclose(f.start_pos[d], p_start[d])
        p_later, v = synth.straight_world(3.0)
        for d in synth.DRONES:
            tr.update_odom(d, 3.0, p_later[d] - tr.offsets[d], v[d])
        np.testing.assert_allclose(tr.frame(3.0).start_pos["drone_1"], p_start["drone_1"])


class AsymmetricRun(unittest.TestCase):
    """Three straight lines through the arena centre; drone_1/drone_2 pass closest at t = 6.05 s."""

    @classmethod
    def setUpClass(cls):
        cls.cols, cls.rows = synth.straight_frames()
        cls.t = cls.rows[:, cls.cols.index("t_s")]

    def col(self, name):
        return self.rows[:, self.cols.index(name)]

    def at(self, name, t):
        return self.col(name)[int(round(t / 0.025))]

    def test_closest_approach_pair_time_and_value(self):
        pairs = {k: self.col(k) for k in ("d_12", "d_13", "d_23")}
        closest = {k: v.min() for k, v in pairs.items()}
        self.assertEqual(min(closest, key=closest.get), "d_12")
        self.assertAlmostEqual(self.t[np.argmin(pairs["d_12"])], 6.05, places=3)
        self.assertAlmostEqual(closest["d_12"], 0.2987, places=3)

    def test_min_pair_distance_is_min_and_differs_from_max_at_that_instant(self):
        i = int(round(6.05 / 0.025))
        trio = [self.col(k)[i] for k in ("d_12", "d_13", "d_23")]
        self.assertAlmostEqual(self.col("min_pair_distance")[i], min(trio))
        self.assertGreater(max(trio) - min(trio), 0.5)

    def test_running_min_is_final_closest_and_above_current_afterwards(self):
        run = self.col("min_pair_distance_running")
        self.assertAlmostEqual(run[-1], 0.2987, places=3)
        self.assertTrue(np.all(np.diff(run[~np.isnan(run)]) <= 1e-9))
        self.assertGreater(self.col("min_pair_distance")[-1], run[-1] + 0.3)

    def test_speed_from_twist_at_two_instants(self):
        self.assertAlmostEqual(self.at("speed_drone_1", 4.0), 0.225, places=3)
        self.assertAlmostEqual(self.at("speed_drone_2", 4.0), 0.16875, places=3)
        self.assertAlmostEqual(self.at("speed_drone_2", 8.0), 0.39375, places=3)
        self.assertAlmostEqual(self.at("speed_drone_3", 8.0), 0.0105, places=3)

    def test_goal_distance_positive_at_start_and_zero_at_end(self):
        i = int(round(1.0 / 0.025))
        for d in synth.DRONES:
            self.assertGreater(self.col("goal_dist_" + d)[i], 1.0)
            self.assertLess(self.col("goal_dist_" + d)[-1], 1e-6)
        self.assertAlmostEqual(self.col("goal_dist_drone_1")[i], 1.8, places=3)
        self.assertTrue(math.isnan(self.col("goal_dist_drone_1")[0]))

    def test_phase_column_follows_status(self):
        ph = self.col("phase")
        self.assertEqual((ph[0], ph[int(0.5 / 0.025)], ph[-1]), (0.0, 1.0, 2.0))

    def test_fence_margin_is_distance_to_nearest_face(self):
        # drone_3 starts at z = 2.4 (0.6 below the z = 3 fence); the lowest drone is at z >= 0.6 above z = 0.
        self.assertAlmostEqual(self.col("fence_margin").min(), 0.6, places=2)


class TrackerAndCsv(unittest.TestCase):
    def test_running_min_matches_symmetric_run_final_value(self):
        cols, rows = synth.frames()
        i = cols.index("min_pair_distance_running")
        self.assertAlmostEqual(rows[-1, i], 1.25, places=2)
        self.assertTrue(np.all(np.diff(rows[~np.isnan(rows[:, i]), i]) <= 1e-9))

    def test_csv_roundtrip_keeps_meta_and_columns(self):
        cols, rows = synth.frames()
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d) / "metrics.csv"
            synth.write_csv(p, cols, rows, {"offsets": "-2,0,0,0,0,0,2,0,0", "t0_unix": "1.5"})
            meta, cols2, rows2 = M.read_metrics_csv(p)
        self.assertEqual(cols2, cols)
        self.assertEqual(meta["offsets"], "-2,0,0,0,0,0,2,0,0")
        np.testing.assert_allclose(rows2, rows, atol=1e-6)

    def test_csv_header_roundtrip_keeps_every_meta_key_exactly(self):
        meta = {"offsets": [-2, 0, 0, 0, 0, 0, 2, 0, 0], "t0_unix": 1761700000.123456, "r": 0.55,
                "fence_min": [-3.0, -6.0, 0.0], "ref_2r": 1.1, "run": "sim_crossing_run1"}
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d) / "m.csv"
            p.write_text(M.csv_header(synth.SERIES, meta))
            got, cols, rows = M.read_metrics_csv(p)
        self.assertEqual(set(got), set(meta))
        self.assertEqual(cols, M.csv_columns(synth.SERIES))
        self.assertEqual(rows.shape, (0, len(cols)))
        self.assertEqual(got["run"], "sim_crossing_run1")
        np.testing.assert_allclose([float(x) for x in got["offsets"].split(",")], meta["offsets"], atol=1e-6)
        np.testing.assert_allclose([float(x) for x in got["fence_min"].split(",")], meta["fence_min"], atol=1e-6)
        for k in ("t0_unix", "r", "ref_2r"):
            self.assertAlmostEqual(float(got[k]), meta[k], delta=1e-6)

    def test_csv_header_meta_keys_are_sorted(self):
        lines = M.csv_header(synth.SERIES, {"b": 1, "a": 2, "c": 3}).splitlines()
        self.assertEqual(lines[:3], ["# a=2", "# b=1", "# c=3"])

    def test_format_row_roundtrip_to_1e_6(self):
        cols = ["t_s", "phase", "x"]
        line = M.format_row(1.2345678, 2, {"x": 3.1415926}, cols)
        t, ph, x = [float(c) for c in line.split(",")]
        self.assertAlmostEqual(t, 1.2345678, delta=1e-6)
        self.assertEqual(ph, 2.0)
        self.assertAlmostEqual(x, 3.1415926, delta=1e-6)
        self.assertEqual(M.format_row(0, 0, {"x": math.nan}, cols).split(",")[2], "nan")

    def test_meta_offsets_parses_per_drone(self):
        o = M.meta_offsets({"offsets": "-2,0,0,0,0,0,2,0,0"}, synth.DRONES)
        np.testing.assert_allclose(o["drone_1"], [-2, 0, 0])
        np.testing.assert_allclose(o["drone_3"], [2, 0, 0])

    def test_read_metrics_csv_without_offsets_is_error(self):
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d) / "m.csv"
            p.write_text("t_s,phase,d_12\n0,0,1\n")
            with self.assertRaises(M.MetricsCsvError):
                M.read_metrics_csv(p)

    def test_read_metrics_csv_ragged_row_is_error(self):
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d) / "m.csv"
            p.write_text("# offsets=0,0,0\nt_s,phase,d_12\n0,0,1\n1,0\n")
            with self.assertRaises(M.MetricsCsvError):
                M.read_metrics_csv(p)

    def test_read_metrics_csv_without_column_line_is_error(self):
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d) / "m.csv"
            p.write_text("# offsets=0,0,0\n")
            with self.assertRaises(M.MetricsCsvError):
                M.read_metrics_csv(p)


class CrossCheck(unittest.TestCase):
    def test_identical_runs_agree_on_every_column(self):
        cols, rows = synth.frames()
        cr = M.crosscheck(cols, rows, cols, rows.copy(), synth.SERIES)
        self.assertTrue(all(r.ok for r in cr))
        self.assertEqual({r.name for r in cr}, {s.name for s in synth.SERIES} | {"min_pair_distance_running"})

    def test_min_distance_off_by_3cm_fails(self):
        cols, rows = synth.frames()
        bag = rows.copy()
        bag[:, cols.index("min_pair_distance")] -= 0.03
        bad = [r.name for r in M.crosscheck(cols, rows, cols, bag, synth.SERIES) if not r.ok]
        self.assertIn("min_pair_distance", bad)

    def test_running_min_column_is_checked_with_series_tolerance(self):
        cols, rows = synth.frames()
        bag = rows.copy()
        bag[:, cols.index("min_pair_distance_running")] -= 0.03
        bad = [r.name for r in M.crosscheck(cols, rows, cols, bag, synth.SERIES) if not r.ok]
        self.assertEqual(bad, ["min_pair_distance_running"])

    def test_flag_column_one_sample_skew_is_ok(self):
        cols, rows = synth.frames()
        bag = rows.copy()
        j = cols.index("cbf_drone_1")
        k = int(np.argmax(bag[:, j]))
        bag[k, j] = 0
        bag[k - 1, j] = 1
        self.assertTrue(next(r for r in M.crosscheck(cols, rows, cols, bag, synth.SERIES) if r.name == "cbf_drone_1").ok)

    def test_unpaired_rows_flagged(self):
        cols, rows = synth.frames()
        cr = M.crosscheck(cols, rows, cols, rows[::2], synth.SERIES)
        self.assertTrue(all(r.unpaired_frac > 0.05 for r in cr))
        self.assertFalse(any(r.ok for r in cr))

    def test_flag_count_tolerance_is_two_for_few_rows(self):
        live = np.zeros(100)
        self.assertTrue(check(live, np.r_[np.ones(2), np.zeros(98)], kind="flag").ok)       # diff 2
        self.assertFalse(check(live, np.r_[np.ones(3), np.zeros(97)], kind="flag").ok)      # diff 3

    def test_flag_count_tolerance_is_one_percent_for_many_rows(self):
        live = np.zeros(500)
        self.assertTrue(check(live, np.r_[np.ones(5), np.zeros(495)], kind="flag").ok)      # diff 5 = 1 %
        self.assertFalse(check(live, np.r_[np.ones(6), np.zeros(494)], kind="flag").ok)     # one over

    def test_continuous_tolerance_exactly_tol_is_ok_and_just_over_is_not(self):
        live = np.ones(10)
        self.assertTrue(check(live, live + 0.25, tol=0.25).ok)
        self.assertFalse(check(live, live + 0.2501, tol=0.25).ok)

    def test_nan_versus_value_is_not_ok(self):
        live = np.ones(10)
        bag = live.copy()
        bag[3] = np.nan
        self.assertFalse(check(live, bag).ok)

    def test_nan_in_both_is_ok(self):
        live = np.ones(10)
        live[3] = np.nan
        self.assertTrue(check(live, live.copy()).ok)

    def test_timestamp_within_t_tol_pairs_and_beyond_does_not(self):
        v = np.ones(20)
        self.assertEqual(check(v, v, shift=0.04).paired, 20)
        r = check(v, v, shift=0.06)
        self.assertEqual(r.paired, 0)
        self.assertFalse(r.ok)

    def test_t_tol_argument_is_honoured(self):
        v = np.ones(20)
        self.assertEqual(check(v, v, shift=0.0625, t_tol=0.0625).paired, 20)
        self.assertEqual(check(v, v, shift=0.125, t_tol=0.0625).paired, 0)

    def test_unpaired_exactly_five_percent_is_ok_and_more_is_not(self):
        v = np.ones(20)
        cols, live, bag = pair_arrays(v, v)
        self.assertTrue(M.crosscheck(cols, live, cols, bag[:19], const_series())[0].ok)      # 1/20 unpaired = 5 %
        self.assertFalse(M.crosscheck(cols, live, cols, bag[:18], const_series())[0].ok)     # 10 %


class CrossCheckBagSide(unittest.TestCase):
    def test_bag_extra_rows_counted_as_unpaired_bag_frac(self):
        cols, rows = synth.frames(n=40)
        cr = M.crosscheck(cols, rows[:-1], cols, rows, synth.SERIES)          # 1 extra bag row of 40 = 2.5 %
        self.assertTrue(all(r.unpaired_bag_frac > 0 for r in cr))
        self.assertTrue(all(r.ok for r in cr))

    def test_bag_unpaired_over_five_percent_is_not_ok(self):
        cols, rows = synth.frames()
        cr = M.crosscheck(cols, rows[::2], cols, rows, synth.SERIES)         # live is half the bag
        self.assertTrue(all(r.unpaired_frac == 0 for r in cr))
        self.assertTrue(all(r.unpaired_bag_frac > 0.05 for r in cr))
        self.assertFalse(any(r.ok for r in cr))

    def test_empty_live_is_not_ok(self):
        cols, rows = synth.frames()
        cr = M.crosscheck(cols, rows[:0], cols, rows, synth.SERIES)
        self.assertTrue(cr)
        self.assertFalse(any(r.ok for r in cr))

    def test_empty_both_is_not_ok(self):
        cols, rows = synth.frames()
        self.assertFalse(any(r.ok for r in M.crosscheck(cols, rows[:0], cols, rows[:0], synth.SERIES)))


def _drop(cols, rows, t_lo, t_hi):
    t = rows[:, cols.index("t_s")]
    return rows[~((t > t_lo + 1e-9) & (t < t_hi - 1e-9))]


class Coverage(unittest.TestCase):
    def test_clean_synthetic_run_has_small_gap_and_counts_rows(self):
        cols, rows = synth.frames()
        c = M.coverage(cols, rows)
        self.assertAlmostEqual(c["max_gap_s"], 0.025, places=6)
        self.assertEqual(c["phase2_rows"], int(np.sum(rows[:, cols.index("phase")] == 2)))
        self.assertEqual(c["phase3_rows"], 0)                                 # synth.frames never lands

    def test_one_second_gap_inside_phase_2(self):
        cols, rows = synth.frames()
        c = M.coverage(cols, _drop(cols, rows, 4.0, 5.0))
        self.assertAlmostEqual(c["max_gap_s"], 1.0, places=6)
        self.assertAlmostEqual(c["gap_at_s"], 4.0, places=6)

    def test_gap_across_the_start_of_phase_2_is_seen(self):
        cols, rows = synth.frames()                                          # phase 2 from t = 1.0
        c = M.coverage(cols, _drop(cols, rows, 0.5, 1.5))
        self.assertAlmostEqual(c["max_gap_s"], 1.0, places=6)

    def test_landing_rows_counted(self):
        cols, rows = synth.frames(land_at=9.5)
        c = M.coverage(cols, rows)
        self.assertGreater(c["phase3_rows"], 0)
        self.assertEqual(c["phase3_rows"], int(np.sum(rows[:, cols.index("phase")] == 3)))

    def test_gap_across_the_end_of_phase_2_is_seen(self):
        cols, rows = synth.frames(land_at=9.5)
        c = M.coverage(cols, _drop(cols, rows, 9.0, 9.8))
        self.assertAlmostEqual(c["max_gap_s"], 0.8, places=6)

    def test_no_phase_2_rows_is_infinite_gap(self):
        cols, rows = synth.frames(n=30)                                      # t < 0.75: phases 0 and 1 only
        c = M.coverage(cols, rows)
        self.assertEqual(c["phase2_rows"], 0)
        self.assertTrue(math.isinf(c["max_gap_s"]))


class NanFraction(unittest.TestCase):
    COLS = ["t_s", "phase", "x"]

    def test_only_phase_2_rows_count(self):
        rows = np.array([[0, 1, np.nan], [1, 1, np.nan], [2, 2, 1.0], [3, 2, np.nan], [4, 2, 1.0], [5, 2, 1.0], [6, 3, np.nan]])
        self.assertAlmostEqual(M.nan_fraction(rows, self.COLS, "x"), 0.25)

    def test_no_phase_2_rows_fails_closed(self):
        rows = np.array([[0, 1, 1.0], [1, 3, 1.0]])
        self.assertEqual(M.nan_fraction(rows, self.COLS, "x"), 1.0)

    def test_other_phase_can_be_selected(self):
        rows = np.array([[0, 1, np.nan], [1, 1, 1.0]])
        self.assertAlmostEqual(M.nan_fraction(rows, self.COLS, "x", phase=1), 0.5)


if __name__ == "__main__":
    unittest.main()
