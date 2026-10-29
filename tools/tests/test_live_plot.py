# tools/tests/test_live_plot.py — the live distance window opened by `sim.sh test` (design 2026-10-30)
import json, math, pathlib, sys, tempfile, unittest
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / "live"))
import synth_crossing as S
import live_plot as L
import plot_style as PS

SPEC = {"id": "distances", "title": "Pairwise distances", "series": ["d_12", "d_13", "d_23", "min_pair_distance_running"],
        "refs": ["ref_2r", "ref_r"], "y_range": [0, 4], "unit": "m"}


def csv_lines(n=200, meta=None):
    cols, rows = S.frames(n=n)
    with tempfile.TemporaryDirectory() as d:
        p = pathlib.Path(d) / "m.csv"; S.write_csv(p, cols, rows, meta)
        return p.read_text().splitlines(), cols, rows


def fed(lines, spec=SPEC):
    m = L.LiveModel(spec)
    for ln in lines:
        m.feed(ln)
    return m


class Model(unittest.TestCase):
    def test_collects_every_row_of_each_series(self):
        lines, cols, rows = csv_lines()
        t, ys, phase = fed(lines).arrays()
        self.assertEqual(len(t), len(rows))
        np.testing.assert_allclose(ys["d_12"], rows[:, cols.index("d_12")], atol=1e-6)
        np.testing.assert_allclose(phase, rows[:, cols.index("phase")])

    def test_headline_names_the_latest_closest_pair_and_the_running_minimum(self):
        lines, cols, rows = csv_lines()
        last = rows[-1]
        now = min(last[cols.index(c)] for c in ("d_12", "d_13", "d_23"))
        run = last[cols.index("min_pair_distance_running")]
        h = fed(lines).headline()
        self.assertIn("now %.2f m" % now, h)
        self.assertIn("running min %s" % ("%.2f m" % run if not math.isnan(run) else "—"), h)

    def test_headline_before_any_row_is_waiting(self):
        self.assertIn("waiting", fed(["# offsets=0", "t_s,phase,d_12"], {"series": ["d_12"]}).headline())

    def test_refs_come_from_the_real_header_string(self):
        m = fed(["# refs=ref_2r:1.1;ref_r:0.55", "t_s,phase,d_12,d_13,d_23,min_pair_distance_running"])
        self.assertEqual(m.refs(), [("ref_2r", 1.1), ("ref_r", 0.55)])

    def test_a_torn_row_from_a_live_tail_is_skipped_not_fatal(self):
        lines, cols, rows = csv_lines(n=20)
        m = fed(lines[:-1] + ["0.9,2,1.0"] + lines[-1:])
        self.assertEqual(len(m.arrays()[0]), len(rows))
        self.assertEqual(m.skipped, 1)


class Window(unittest.TestCase):
    def tearDown(self):
        plt.close("all")

    def test_drawn_lines_match_the_data_refs_and_record_colours(self):
        lines, cols, rows = csv_lines()
        m = fed(lines + ["# refs=ref_2r:1.1;ref_r:0.55"])
        w = L.Window(SPEC, "crossing · run9")
        w.update(m)
        by_label = {ln.get_label(): ln for ln in w.ax.get_lines()}
        np.testing.assert_allclose(by_label["d_12"].get_ydata(), rows[:, cols.index("d_12")], atol=1e-6)
        self.assertEqual(by_label["min_pair_distance_running"].get_color(), PS.MIN_COLOUR)
        self.assertEqual(by_label["d_12"].get_color(), PS.COLOURS[0])
        ref_y = sorted(round(ln.get_ydata()[0], 3) for lbl, ln in by_label.items() if lbl.startswith("ref_"))
        self.assertEqual(ref_y, [0.55, 1.1])
        self.assertIn(m.headline(), w.ax.get_title(loc="left"))
        self.assertEqual(w.ax.get_ylim(), (0.0, 4.0))

    def test_update_twice_does_not_duplicate_reference_lines(self):
        lines, _, _ = csv_lines(n=20)
        m = fed(lines + ["# refs=ref_2r:1.1;ref_r:0.55"])
        w = L.Window(SPEC, "x")
        w.update(m); w.update(m)
        self.assertEqual(sum(1 for ln in w.ax.get_lines() if ln.get_label().startswith("ref_")), 2)


class Main(unittest.TestCase):
    def test_file_mode_once_saves_a_png(self):
        lines, _, _ = csv_lines()
        with tempfile.TemporaryDirectory() as d:
            d = pathlib.Path(d)
            (d / "m.csv").write_text("\n".join(lines) + "\n")
            (d / "plots.json").write_text(json.dumps({"plots": [SPEC]}))
            rc = L.main(["--plots", str(d / "plots.json"), "--file", str(d / "m.csv"), "--once", "--save", str(d / "f.png")])
            self.assertEqual(rc, 0)
            self.assertGreater((d / "f.png").stat().st_size, 10_000)

    def test_missing_plots_json_is_a_usage_error(self):
        self.assertEqual(L.main(["--plots", "/nonexistent/plots.json", "--file", "/dev/null", "--once"]), 2)

    def test_docker_source_follows_the_csv_until_the_metrics_node_exits(self):
        cmd = L.source_cmd(docker="robot", path="/tmp/svg_test/metrics.csv")
        self.assertEqual(cmd[:3], ["docker", "exec", "robot"])
        script = cmd[-1]
        for frag in ("tail -n +1 -F", "--pid=", "/tmp/svg_test/metrics.csv", "metrics_node"):
            self.assertIn(frag, script)

    def test_file_source_is_a_plain_tail(self):
        self.assertEqual(L.source_cmd(path="/x/m.csv"), ["tail", "-n", "+1", "-F", "/x/m.csv"])


if __name__ == "__main__":
    unittest.main()


class ReviewFixes(unittest.TestCase):
    def test_headline_of_a_plot_without_a_running_series_lists_the_latest_values_with_its_unit(self):
        spec = {"id": "speeds", "title": "Speed per drone", "series": ["speed_drone_1", "speed_drone_2"], "unit": "m/s"}
        m = fed(["# offsets=0", "t_s,phase,speed_drone_1,speed_drone_2", "0.0,2,1.0,0.5"], spec)
        self.assertEqual(m.headline(), "latest speed_drone_1 1.00 m/s, speed_drone_2 0.50 m/s")

    def test_missing_time_column_does_not_crash_the_window(self):
        m = fed(["# offsets=0", "phase,d_12", "2,1.0"], {"series": ["d_12"]})
        L.Window({"series": ["d_12"]}, "x").update(m)

    def test_arrays_built_incrementally_equal_a_fresh_build(self):
        lines, _, rows = csv_lines(n=120)
        m = L.LiveModel(SPEC)
        for k, ln in enumerate(lines):
            m.feed(ln)
            if k % 17 == 0:
                m.arrays()
        t, ys, _ = m.arrays()
        f = fed(lines)
        np.testing.assert_array_equal(t, f.arrays()[0]); np.testing.assert_array_equal(ys["d_13"], f.arrays()[1]["d_13"])

    def test_rows_that_arrive_inside_the_throttle_are_drawn_on_a_later_pass(self):
        r = L.Redraw(period=0.5)
        r.mark(); self.assertTrue(r.due(10.0)); r.drawn(10.0)
        r.mark(); self.assertFalse(r.due(10.2))           # inside the throttle: not yet
        self.assertTrue(r.due(10.6))                      # no new line arrived, still drawn later
        r.drawn(10.6); self.assertFalse(r.due(20.0))      # nothing new: no redraw

    def test_container_source_exits_when_no_metrics_node_runs(self):
        import subprocess
        script = L.source_cmd(docker="robot", path="/nonexistent/metrics.csv")[-1]
        self.assertIn("pgrep -of '^python3 metrics_node", script)
        r = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=10)   # no node here
        self.assertNotEqual(r.returncode, 0)

    def test_sim_sh_cleanup_pattern_matches_the_real_container_tail_and_nothing_else(self):
        import re, subprocess
        src = (HERE.parent / "sim.sh").read_text()
        fn = src[src.index("stop_live_plot() {"):src.index("# stop_fly")]
        pat = re.search(r'pkill -f "([^"]+)"', fn).group(1).replace("$S", "/tmp/svg_test")
        real = "tail -n +1 -F --pid=4242 /tmp/svg_test/metrics.csv"
        other = "tail -n0 -f /tmp/svg_test/metrics_node.log"
        g = lambda line: subprocess.run(["grep", "-qE", pat], input=line, text=True).returncode == 0
        self.assertTrue(g(real), pat); self.assertFalse(g(other), pat)
