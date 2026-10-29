# tools/tests/test_plot_metrics.py
import json, pathlib, sys, tempfile, unittest
import matplotlib.pyplot as plt
import numpy as np
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / "live"))
import synth_crossing as S
import plot_metrics as P

SERIES = ["d_12", "d_13", "d_23", "min_pair_distance_running"]
SPEC = {"id": "dist", "title": "pairwise distance [m]", "series": SERIES, "refs": ["ref_2r", "ref_r"]}


def drawn(spec=SPEC, rows=None, cols=None, meta=None):
    c, r = S.frames()
    fig, ax = P.plot(cols or c, r if rows is None else rows, meta or S.default_meta(), spec)
    return fig, ax


class PlotMetrics(unittest.TestCase):
    def tearDown(self):
        plt.close("all")

    def test_renders_png_with_refs_and_phase(self):
        with tempfile.TemporaryDirectory() as d:
            d = pathlib.Path(d)
            cols, rows = S.frames()
            csv = d / "metrics.csv"; S.write_csv(csv, cols, rows)
            plots_json = d / "plots.json"
            plots_json.write_text(json.dumps({"plots": [SPEC, {"id": "speed", "series": ["speed_drone_1"], "refs": ["ref_speed_cap"]}]}))
            png = d / "fig-1.png"
            self.assertEqual(P.main([str(csv), "--plots", str(plots_json), "-o", str(png)]), 0)
            self.assertGreater(png.stat().st_size, 15_000)
            png2 = d / "fig-2.png"
            self.assertEqual(P.main([str(csv), "--plots", str(plots_json), "--plot", "speed", "-o", str(png2)]), 0)
            self.assertTrue(png2.is_file())

    def test_unknown_series_raises(self):
        cols, rows = S.frames(n=20)
        with self.assertRaises(ValueError):
            P.plot(cols, rows, {}, {"id": "x", "series": ["nope"]})

    def test_one_line_per_series_with_the_csv_data(self):
        cols, rows = S.frames()
        _, ax = drawn(cols=cols, rows=rows)
        lines = {l.get_label(): l for l in ax.lines}
        for name in SERIES:
            self.assertIn(name, lines)
            self.assertEqual(len(lines[name].get_xdata()), len(rows))
            np.testing.assert_allclose(lines[name].get_ydata(), rows[:, cols.index(name)])

    def test_reference_lines_at_the_values_from_the_csv_header(self):
        meta = S.default_meta()
        _, ax = drawn()
        refs = {l.get_label().split(" = ")[0]: l.get_ydata()[0] for l in ax.lines if " = " in l.get_label()}
        self.assertEqual(set(refs), {"ref_2r", "ref_r"})
        self.assertAlmostEqual(refs["ref_2r"], float(meta["ref_2r"])); self.assertAlmostEqual(refs["ref_r"], float(meta["ref_r"]))
        self.assertTrue(all(l.get_linestyle() == "--" for l in ax.lines if " = " in l.get_label()))

    def test_refs_from_a_meta_refs_dict(self):
        _, ax = drawn(meta={**S.default_meta(), "refs": {"ref_2r": 9.0}})
        ys = [l.get_ydata()[0] for l in ax.lines if l.get_label().startswith("ref_2r")]
        self.assertEqual(ys, [9.0])

    def test_legend_lists_every_series_and_ref(self):
        _, ax = drawn()
        labels = [t.get_text() for t in ax.get_legend().get_texts()]
        for name in SERIES:
            self.assertIn(name, labels)
        self.assertTrue(any(l.startswith("ref_2r") for l in labels))

    def test_footer_and_axis_labels(self):
        fig, ax = drawn()
        self.assertIn(P.FOOTER, [t.get_text() for t in fig.texts])
        self.assertEqual(ax.get_xlabel(), "t [s, wall]")
        self.assertEqual(ax.get_ylabel(), "pairwise distance [m]")
        self.assertNotEqual(ax.get_title("left"), ax.get_ylabel()); self.assertTrue(ax.get_title("left"))

    def test_phase_1_and_3_spans_are_shaded(self):
        cols, rows = S.frames()
        rows = rows.copy(); ph = cols.index("phase"); rows[:, ph] = 2
        rows[:10, ph] = 1; rows[-10:, ph] = 3
        _, ax = drawn(cols=cols, rows=rows)
        self.assertEqual(len(ax.patches), 2)
        labels = [t.get_text() for t in ax.get_legend().get_texts()]
        self.assertIn("phase 1 (takeoff)", labels); self.assertIn("phase 3 (land)", labels)

    def test_no_phase_spans_without_phase_1_or_3(self):
        cols, rows = S.frames()
        rows = rows.copy(); rows[:, cols.index("phase")] = 2
        _, ax = drawn(cols=cols, rows=rows)
        self.assertEqual(len(ax.patches), 0)

    def test_coinciding_series_get_separate_direct_labels(self):
        cols = ["t_s", "phase", "a", "b", "c"]
        rows = np.array([[t, 2, 1.0, 1.0, 1.0] for t in np.linspace(0, 5, 20)])
        _, ax = P.plot(cols, rows, {}, {"id": "x", "series": ["a", "b", "c"]})
        ys = sorted(t.xy[1] for t in ax.texts if t.get_text() in ("a", "b", "c"))
        self.assertEqual(len(ys), 3)
        self.assertGreaterEqual(min(np.diff(ys)), ax.label_gap - 1e-9)



class RefHeaderForm(unittest.TestCase):
    def test_refs_string_from_the_csv_header_is_parsed(self):
        import plot_metrics as P
        meta = {"refs": "ref_2r:1.1;ref_r:0.55;ref_speed_cap:4.0"}
        self.assertEqual(P._ref_value(meta, "ref_2r"), 1.1)
        self.assertEqual(P._ref_value(meta, "ref_speed_cap"), 4.0)
        self.assertIsNone(P._ref_value(meta, "nope"))

if __name__ == "__main__":
    unittest.main()
