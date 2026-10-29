# tools/tests/test_plot_metrics.py
import json, pathlib, sys, tempfile, unittest
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / "live"))
import synth_crossing as S
import plot_metrics as P


class PlotMetrics(unittest.TestCase):
    def test_renders_png_with_refs_and_phase(self):
        with tempfile.TemporaryDirectory() as d:
            d = pathlib.Path(d)
            cols, rows = S.frames()
            csv = d / "metrics.csv"; S.write_csv(csv, cols, rows)
            plots_json = d / "plots.json"
            plots_json.write_text(json.dumps({"plots": [
                {"id": "dist", "title": "pairwise distance [m]", "series": ["d_12", "d_13", "d_23", "min_pair_distance_running"], "refs": ["ref_2r"]},
                {"id": "speed", "series": ["speed_drone_1"], "refs": ["ref_speed_cap"]}]}))
            png = d / "fig-1.png"
            self.assertEqual(P.main([str(csv), "--plots", str(plots_json), "-o", str(png)]), 0)
            self.assertGreater(png.stat().st_size, 15_000)
            png2 = d / "fig-2.png"
            self.assertEqual(P.main([str(csv), "--plots", str(plots_json), "--plot", "speed", "-o", str(png2)]), 0)
            self.assertTrue(png2.is_file())

    def test_unknown_series_raises(self):
        with tempfile.TemporaryDirectory() as d:
            cols, rows = S.frames(n=20)
            with self.assertRaises(ValueError):
                P.plot(cols, rows, {}, {"id": "x", "series": ["nope"]}, pathlib.Path(d) / "x.png")


if __name__ == "__main__":
    unittest.main()
