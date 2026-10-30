# tools/tests/test_compare_replay.py — NEAR-860: compare a replayed cuVSLAM path with the live one
import json, pathlib, subprocess, sys, tempfile, unittest

import numpy as np

SCRIPT = pathlib.Path(__file__).resolve().parents[2] / "localisation/scripts/compare_replay.py"
sys.path.insert(0, str(SCRIPT.parent))
import compare_replay as CR  # noqa: E402


def tum(path, rows):
    path.write_text("".join(f"{t:.6f} {x:.6f} {y:.6f} {z:.6f} 0 0 0 1\n" for t, x, y, z in rows))


class Compare(unittest.TestCase):
    def test_identical_paths_have_zero_error_and_full_coverage(self):
        t = np.arange(0, 10, 0.04)
        live = np.c_[t, np.sin(t), np.cos(t), 0.1 * t]
        r = CR.compare(live, live.copy())
        self.assertEqual(r["matched"], len(t)); self.assertAlmostEqual(r["coverage"], 1.0)
        self.assertAlmostEqual(r["rmse_m"], 0.0); self.assertAlmostEqual(r["max_m"], 0.0)

    def test_constant_offset_shows_as_error(self):
        t = np.arange(0, 10, 0.04)
        live = np.c_[t, t, 0 * t, 0 * t]
        rep = live.copy(); rep[:, 2] += 0.03
        r = CR.compare(live, rep)
        self.assertAlmostEqual(r["rmse_m"], 0.03, places=6); self.assertAlmostEqual(r["final_m"], 0.03, places=6)

    def test_missing_replay_poses_lower_the_coverage(self):
        t = np.arange(0, 10, 0.04)
        live = np.c_[t, t, 0 * t, 0 * t]
        r = CR.compare(live, live[: len(t) // 2])
        self.assertAlmostEqual(r["coverage"], 0.5, places=2)

    def test_poses_further_apart_in_time_than_the_tolerance_do_not_match(self):
        live = np.array([[0.0, 0, 0, 0], [1.0, 1, 0, 0]])
        rep = np.array([[0.5, 0, 0, 0]])
        self.assertEqual(CR.compare(live, rep, tol_s=0.01)["matched"], 0)

    def test_no_match_reports_none_not_a_crash(self):
        r = CR.compare(np.array([[0.0, 0, 0, 0]]), np.array([[9.0, 0, 0, 0]]))
        self.assertEqual(r["matched"], 0); self.assertIsNone(r["rmse_m"])

    def test_cli_writes_json_and_one_line(self):
        with tempfile.TemporaryDirectory() as d:
            d = pathlib.Path(d)
            t = np.arange(0, 2, 0.04)
            tum(d / "live.tum", [(x, x, 0, 0) for x in t]); tum(d / "rep.tum", [(x, x, 0.01, 0) for x in t])
            out = subprocess.run([sys.executable, str(SCRIPT), str(d / "live.tum"), str(d / "rep.tum"), "--json", str(d / "c.json")],
                                 capture_output=True, text=True, check=True).stdout
            self.assertIn("coverage 100.0 %", out); self.assertIn("RMSE 0.010 m", out)
            self.assertAlmostEqual(json.loads((d / "c.json").read_text())["rmse_m"], 0.01, places=6)


if __name__ == "__main__":
    unittest.main()
