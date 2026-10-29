# tools/tests/test_make_layout.py
import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "live"))
import make_layout as L

METRICS = '''import metrics_core as M
SERIES = [
    M.Series("d_12", lambda f: 0.0, 0.02, "m"),
    M.Series("d_13", lambda f: 0.0, 0.02, "m"),
    M.Series("d_23", lambda f: 0.0, 0.02, "m"),
    M.Series("min_pair_distance", lambda f: 0.0, 0.02, "m", "continuous", True),
]
REFERENCES = {"ref_2r": 1.1, "ref_r": 0.55}
'''
PLOTS_JSON = {
    "plots": [
        {"id": "distances", "title": "Pairwise distances",
         "series": ["d_12", "d_13", "d_23", "min_pair_distance_running"],
         "refs": ["ref_2r", "ref_r"], "y_range": [0, 4]},
        {"id": "fence", "title": "Fence", "series": ["d_12"], "refs": [], "y_range": None},
    ],
    "phase_series": "phase", "panel_width_pct": 50,
}


def make_test_dir(d):
    p = pathlib.Path(d)
    (p / "metrics.py").write_text(METRICS)
    (p / "plots.json").write_text(json.dumps(PLOTS_JSON))
    return str(p)


BASE = json.loads(L.BASE_LAYOUT.read_text())
PLOTS = json.loads(json.dumps(PLOTS_JSON))
_tmp = tempfile.TemporaryDirectory()
KNOWN = L.load_series_names(make_test_dir(_tmp.name))


class MakeLayout(unittest.TestCase):
    def test_render_keeps_base_panels_and_adds_plots(self):
        out = L.render(BASE, PLOTS, KNOWN)
        for k in ("svg-basestation.SVG Basestation!sbmain", "svg-basestation.SVG Basestation!sbpower", "3D!sbview"):
            self.assertIn(k, out["configById"])
        self.assertIn("Plot!svgtest_distances", out["configById"])
        self.assertIn("StateTransitions!svgtest_phase", out["configById"])
        self.assertEqual(out["layout"]["first"], BASE["layout"])
        self.assertEqual(out["layout"]["splitPercentage"], 50)
        paths = [p["value"] for p in out["configById"]["Plot!svgtest_distances"]["paths"]]
        self.assertEqual(paths, ["/svg/test/d_12.data", "/svg/test/d_13.data", "/svg/test/d_23.data",
                                 "/svg/test/min_pair_distance_running.data", "/svg/test/ref_2r.data",
                                 "/svg/test/ref_r.data"])

    def test_make_layout_rejects_unknown_series(self):
        bad = json.loads(json.dumps(PLOTS))
        bad["plots"][0]["series"].append("d_99")
        with self.assertRaisesRegex(L.LayoutError, "distances.*d_99"):
            L.render(BASE, bad, KNOWN)

    def test_rejects_duplicate_ids(self):
        bad = json.loads(json.dumps(PLOTS))
        bad["plots"][1]["id"] = "distances"
        with self.assertRaises(L.LayoutError):
            L.render(BASE, bad, KNOWN)

    def test_known_names(self):
        self.assertEqual(KNOWN, {"d_12", "d_13", "d_23", "min_pair_distance", "min_pair_distance_running",
                                 "ref_2r", "ref_r", "phase"})

    def test_base_not_mutated(self):
        before = json.dumps(BASE, sort_keys=True)
        L.render(BASE, PLOTS, KNOWN)
        self.assertEqual(json.dumps(BASE, sort_keys=True), before)

    def test_dumps_is_deterministic_and_check_detects_staleness(self):
        with tempfile.TemporaryDirectory() as d:
            td = make_test_dir(d)
            self.assertEqual(L.main([td, "--check"]), 1)  # no layout.json yet
            self.assertEqual(L.main([td]), 0)
            self.assertEqual(L.main([td, "--check"]), 0)
            p = pathlib.Path(td) / "plots.json"
            j = json.loads(p.read_text())
            j["plots"][0]["title"] = "changed"
            p.write_text(json.dumps(j))
            self.assertEqual(L.main([td, "--check"]), 1)

    def test_check_error_is_2(self):
        with tempfile.TemporaryDirectory() as d:
            td = make_test_dir(d)
            p = pathlib.Path(td) / "plots.json"
            j = json.loads(p.read_text())
            j["plots"][0]["series"].append("nope")
            p.write_text(json.dumps(j))
            self.assertEqual(L.main([td, "--check"]), 2)
            self.assertEqual(L.main([td]), 2)

    def test_column_tree_balanced(self):
        self.assertEqual(L.column_tree(["a"]), "a")
        t = L.column_tree(["a", "b", "c"])
        self.assertEqual(t["direction"], "column")
        self.assertEqual(t["splitPercentage"], 67)  # 2 of 3 leaves: equal-height panels


if __name__ == "__main__":
    unittest.main()
