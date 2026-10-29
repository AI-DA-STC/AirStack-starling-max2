"""Five-file test contract: tools/sim_tests/_template and crossing (gates on synthetic frames, fly.sh flow). Sim-only."""
import importlib.util
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
TOOLS = HERE.parent
for p in (HERE, TOOLS, TOOLS / "live", TOOLS / "lib"):
    sys.path.insert(0, str(p))
import make_layout as L  # noqa: E402
import report as R  # noqa: E402
import synth_crossing as synth  # noqa: E402

CROSSING = TOOLS / "sim_tests" / "crossing"
TEMPLATE = TOOLS / "sim_tests" / "_template"
FIX = HERE / "fixtures" / "run1"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CM = _load("crossing_metrics_t", CROSSING / "metrics.py")
G = _load("crossing_gates_t", CROSSING / "gates.py")


def make_run(tmp, **frames_kw):
    tmp = pathlib.Path(tmp)
    out, heavy = tmp / "run", tmp / "heavy"
    out.mkdir()
    (heavy / "crossing_2026_10_29-12_00_00").mkdir(parents=True)
    (heavy / "crossing_2026_10_29-12_00_00" / "metadata.yaml").write_text("rosbag2_bagfile_information: {}\n")
    for f in ("res_watch.log", "ulog_sysid_map.txt"):
        shutil.copy(FIX / f, out / f)
    (out / "isaac_evidence.txt").write_text("model_line=0 starling_cfg=3 autostart=3 unknown_model=0 cooking=0 ready=3\n")   # run1's print was not captured
    (out / "armed_post.txt").write_text("".join("drone_%d armed: false\n" % i for i in (1, 2, 3)))
    (out / "landing_evidence.txt").write_text("".join("[swarm_commander-2] drone_%d: landed, disarmed (attempt 1)\n" % i for i in (1, 2, 3)))
    (out / "run_meta.txt").write_text("head_short=abc1234 dirty_tools=0 started=2026-10-29T12:00:00 tz=+08\n")
    frames_kw.setdefault("land_at", 9.5)                 # 20 landing (phase-3) rows after the window
    cols, rows = synth.frames(**frames_kw)
    synth.write_csv(out / "metrics.csv", cols, rows)
    shutil.copy(out / "metrics.csv", out / "metrics_bag.csv")
    env = R.parse_env(CROSSING / "test.env")
    return out, heavy, env


def nan_out_rows(csv_path, columns, frac):
    lines = pathlib.Path(csv_path).read_text().splitlines()
    i0 = next(i for i, l in enumerate(lines) if not l.startswith("#"))
    cols = lines[i0].split(",")
    ph = cols.index("phase")
    idx = [i for i in range(i0 + 1, len(lines)) if lines[i].split(",")[ph] == "2"]
    k = max(1, round(1 / frac))
    for n, i in enumerate(idx):
        if n % k == 0:
            cells = lines[i].split(",")
            for c in columns:
                cells[cols.index(c)] = "nan"
            lines[i] = ",".join(cells)
    pathlib.Path(csv_path).write_text("\n".join(lines) + "\n")


def verdict_of(rows, prefix):
    return next(r.verdict for r in rows if r.check.startswith(prefix))


class Crossing(unittest.TestCase):
    def test_series_match_synth(self):
        self.assertEqual([(s.name, s.kind, s.tol, s.running_min) for s in CM.SERIES], [(s.name, s.kind, s.tol, s.running_min) for s in synth.SERIES])

    def test_clean_synthetic_run_passes(self):
        with tempfile.TemporaryDirectory() as d:
            out, heavy, env = make_run(d)
            rows, ctx = G.build_rows(out, heavy, env)
            self.assertEqual(R.overall_verdict(rows), "PASS", [(r.check, r.measured) for r in rows if r.gate and r.verdict != "PASS"])
            self.assertIn("1.25", next(r.measured for r in rows if r.check.startswith("min pairwise distance")))
            self.assertEqual(next(r.verdict for r in rows if r.check.startswith("vs ledger #4")), "info")

    def test_banner_headline_is_fed_by_the_real_gates(self):
        with tempfile.TemporaryDirectory() as d:
            out, heavy, env = make_run(d)
            rows, ctx = G.build_rows(out, heavy, env)
            self.assertIn("1.25", R.headline_text(rows, ctx))                                    # a missing ctx["headline_row"] gives "n/a" and fails here
        self.assertIn('"headline_row": "min pairwise distance"', (TOOLS / "sim_tests" / "_template" / "gates.py").read_text())

    def test_distance_below_2r_fails(self):
        with tempfile.TemporaryDirectory() as d:
            out, heavy, env = make_run(d, closest_m=1.05)
            rows, _ = G.build_rows(out, heavy, env)
            self.assertEqual(verdict_of(rows, "min pairwise distance"), "FAIL")

    def test_one_emergency_sample_fails(self):
        with tempfile.TemporaryDirectory() as d:
            out, heavy, env = make_run(d, emergency_at=5.0)
            rows, _ = G.build_rows(out, heavy, env)
            self.assertEqual(verdict_of(rows, "emergency samples"), "FAIL")

    def test_speed_4_3_fails_and_4_1_passes(self):
        for peak, want in ((4.3, "FAIL"), (4.1, "PASS")):
            with tempfile.TemporaryDirectory() as d:
                out, heavy, env = make_run(d, peak_speed=peak)
                rows, _ = G.build_rows(out, heavy, env)
                self.assertEqual(verdict_of(rows, "peak speed"), want, peak)

    def test_far_goal_0_45_fails(self):
        with tempfile.TemporaryDirectory() as d:
            out, heavy, env = make_run(d, far_goal_miss_m=0.45)
            rows, _ = G.build_rows(out, heavy, env)
            self.assertEqual(verdict_of(rows, "far goal reached"), "FAIL")

    def test_no_cbf_activity_fails(self):
        with tempfile.TemporaryDirectory() as d:
            out, heavy, env = make_run(d, cbf=False)
            rows, _ = G.build_rows(out, heavy, env)
            self.assertEqual(verdict_of(rows, "CBF active on"), "FAIL")

    def test_nan_fraction_makes_gate_unverified(self):
        with tempfile.TemporaryDirectory() as d:
            out, heavy, env = make_run(d)
            nan_out_rows(out / "metrics.csv", ("d_13", "min_pair_distance"), frac=0.05)
            rows, _ = G.build_rows(out, heavy, env)
            self.assertEqual(verdict_of(rows, "min pairwise distance"), "UNVERIFIED")
            self.assertEqual(R.overall_verdict(rows), "INCOMPLETE")

    def test_missing_csv_is_incomplete(self):
        with tempfile.TemporaryDirectory() as d:
            out, heavy, env = make_run(d)
            (out / "metrics.csv").unlink()
            rows, _ = G.build_rows(out, heavy, env)
            self.assertEqual(R.overall_verdict(rows), "INCOMPLETE")
            self.assertIn("metrics.csv", next(r.measured for r in rows if r.check.startswith("min pairwise distance")))

    def test_missing_bag_csv_makes_crosscheck_unverified(self):
        with tempfile.TemporaryDirectory() as d:
            out, heavy, env = make_run(d)
            (out / "metrics_bag.csv").unlink()
            rows, _ = G.build_rows(out, heavy, env)
            self.assertEqual(verdict_of(rows, "live vs bag recompute"), "UNVERIFIED")

    def test_ledger_sentence_and_caption(self):
        with tempfile.TemporaryDirectory() as d:
            out, heavy, env = make_run(d)
            rows, ctx = G.build_rows(out, heavy, env)
            self.assertLessEqual(len("*Figure 1. " + G.figure_caption(ctx) + "*"), 400)
            self.assertIn("NEAR", R.ledger_row(20, "2026-10-29", G.ledger_sentence(rows, ctx, "PASS"), "r", "NEAR-787"))
            self.assertIn("min pairwise distance 1.25 m", G.ledger_sentence(rows, ctx, "PASS"))
            self.assertIn("[Figure 1](#fig-1)", ctx["reading"])


def rewrite_csvs(out, live_rows=None, bag_rows=None, **frames_kw):
    """Rewrite metrics.csv / metrics_bag.csv from synthetic frames; live_rows / bag_rows = fn(cols, rows) -> rows."""
    frames_kw.setdefault("land_at", 9.5)
    cols, rows = synth.frames(**frames_kw)
    synth.write_csv(out / "metrics.csv", cols, live_rows(cols, rows) if live_rows else rows)
    synth.write_csv(out / "metrics_bag.csv", cols, bag_rows(cols, rows) if bag_rows else rows)


def drop_t(lo, hi):
    def fn(cols, rows):
        t = rows[:, cols.index("t_s")]
        return rows[~((t > lo + 1e-9) & (t < hi - 1e-9))]
    return fn


class Coverage(unittest.TestCase):
    def test_clean_run_coverage_row_passes(self):
        with tempfile.TemporaryDirectory() as d:
            out, heavy, env = make_run(d)
            rows, _ = G.build_rows(out, heavy, env)
            self.assertEqual(verdict_of(rows, "coverage"), "PASS")
            self.assertEqual(R.overall_verdict(rows), "PASS")

    def test_gap_in_phase_2_is_incomplete(self):
        with tempfile.TemporaryDirectory() as d:
            out, heavy, env = make_run(d)
            rewrite_csvs(out, live_rows=drop_t(4.0, 5.0), bag_rows=drop_t(4.0, 5.0))   # the bag has the same hole: cross-check passes
            rows, _ = G.build_rows(out, heavy, env)
            self.assertEqual(verdict_of(rows, "live vs bag recompute"), "PASS")
            self.assertEqual(verdict_of(rows, "coverage"), "UNVERIFIED")
            self.assertIn("largest phase-2 gap 1.00 s", next(r.measured for r in rows if r.check.startswith("coverage")))
            self.assertEqual(R.overall_verdict(rows), "INCOMPLETE")

    def test_no_landing_rows_is_incomplete(self):
        with tempfile.TemporaryDirectory() as d:
            out, heavy, env = make_run(d, land_at=None)
            rows, _ = G.build_rows(out, heavy, env)
            self.assertEqual(verdict_of(rows, "coverage"), "UNVERIFIED")
            self.assertIn("no landing rows", next(r.measured for r in rows if r.check.startswith("coverage")))
            self.assertEqual(R.overall_verdict(rows), "INCOMPLETE")

    def test_node_died_is_incomplete(self):
        with tempfile.TemporaryDirectory() as d:
            out, heavy, env = make_run(d)
            (out / "node_died.txt").write_text("found_dead=2026-10-29T22:55:00+08:00\nTraceback (most recent call last):\n")
            rows, _ = G.build_rows(out, heavy, env)
            self.assertEqual(verdict_of(rows, "coverage"), "UNVERIFIED")
            self.assertIn("metrics node died", next(r.measured for r in rows if r.check.startswith("coverage")))
            self.assertEqual(R.overall_verdict(rows), "INCOMPLETE")

    def test_bag_unpaired_rows_make_crosscheck_unverified(self):
        with tempfile.TemporaryDirectory() as d:
            out, heavy, env = make_run(d)
            rewrite_csvs(out, live_rows=lambda c, r: r[::2])          # bag has twice the rows; live gap 0.05 s stays covered
            rows, _ = G.build_rows(out, heavy, env)
            self.assertEqual(verdict_of(rows, "coverage"), "PASS")
            self.assertEqual(verdict_of(rows, "live vs bag recompute"), "UNVERIFIED")
            self.assertIn("bag unpaired 50.", next(r.measured for r in rows if r.check.startswith("live vs bag")))
            self.assertEqual(R.overall_verdict(rows), "INCOMPLETE")

    def test_template_has_the_coverage_row(self):
        TG = _load("template_gates_t", TEMPLATE / "gates.py")
        with tempfile.TemporaryDirectory() as d:
            out, heavy, env = make_run(d)
            env["BAG_PREFIX"] = "crossing"
            rows, _ = TG.build_rows(out, heavy, env)
            self.assertEqual(verdict_of(rows, "coverage"), "PASS")
            (out / "node_died.txt").write_text("found_dead=2026-10-29T22:55:00+08:00\n")
            rows, _ = TG.build_rows(out, heavy, env)
            self.assertEqual(verdict_of(rows, "coverage"), "UNVERIFIED")
            self.assertEqual(R.overall_verdict(rows), "INCOMPLETE")


class MeasuredNamesColumns(unittest.TestCase):
    def test_every_csv_gate_cell_names_its_columns(self):
        with tempfile.TemporaryDirectory() as d:
            out, heavy, env = make_run(d)
            rows, _ = G.build_rows(out, heavy, env)
            m = {r.check: r.measured for r in rows}
            self.assertRegex(m["min pairwise distance ≥ 1.10 m (2r)"], r"^`min_pair_distance`: 1\.25 m \(margin \+0\.15 m to the gate; pair `d_\d\d` at t=")
            self.assertTrue(m["vs ledger #4"].startswith("`min_pair_distance` − 1.02 m: +0.23 m"), m["vs ledger #4"])
            self.assertTrue(m["far goal reached per drone"].startswith("`goal_dist_drone_1..3`: drone_1 "), m["far goal reached per drone"])
            self.assertTrue(m["peak speed ≤ 4.2 m/s"].startswith("`speed_drone_1..3`: "), m["peak speed ≤ 4.2 m/s"])
            self.assertTrue(m["emergency samples"].startswith("`emergency`: 0 CSV rows flagged"), m["emergency samples"])
            self.assertTrue(m["fence-breach samples"].startswith("`fence_breached`: 0 CSV rows flagged"), m["fence-breach samples"])
            self.assertTrue(m["CBF active on ≥ 1 drone at least once"].startswith("`cbf_drone_1..3`: drone_1, drone_3 seen"), m["CBF active on ≥ 1 drone at least once"])
            self.assertIn("`t_s`", next(r.criterion for r in rows if r.check.startswith("coverage")))

    def test_caption_says_wall_clock(self):
        self.assertIn("against wall-clock time", G.figure_caption({}))
        self.assertLessEqual(len("*Figure 1. " + G.figure_caption({}) + "*"), 400)


class AllPhaseMin(unittest.TestCase):
    def test_info_row_finds_the_minimum_outside_the_window(self):
        def dip(cols, rows):
            rows = rows.copy()
            k = int(np.flatnonzero(rows[:, cols.index("phase")] == 3)[5])
            rows[k, cols.index("d_13")] = 0.76
            rows[k, cols.index("min_pair_distance")] = 0.76
            return rows
        with tempfile.TemporaryDirectory() as d:
            out, heavy, env = make_run(d)
            rewrite_csvs(out, live_rows=dip, bag_rows=dip)
            rows, _ = G.build_rows(out, heavy, env)
            r = next(r for r in rows if r.check == "min pairwise distance, all phases")
            self.assertFalse(r.gate); self.assertEqual(r.verdict, "info")
            self.assertIn("0.76 m", r.measured); self.assertIn("d_13", r.measured); self.assertIn("landing", r.measured)
            self.assertIn("1.25", R.headline_text(rows, {"headline_row": "min pairwise distance"}))   # headline stays the phase-2 gate
            self.assertEqual(verdict_of(rows, "min pairwise distance"), "PASS")                      # the window gate is unchanged

    def test_info_row_in_the_window_says_so(self):
        with tempfile.TemporaryDirectory() as d:
            out, heavy, env = make_run(d)
            rows, _ = G.build_rows(out, heavy, env)
            r = next(r for r in rows if r.check == "min pairwise distance, all phases")
            self.assertIn("1.25 m", r.measured); self.assertIn("test window", r.measured)


class Landing(unittest.TestCase):
    def test_ack_log_is_info_only_mavros_decides(self):
        with tempfile.TemporaryDirectory() as d:
            out, heavy, env = make_run(d)
            (out / "landing_evidence.txt").write_text("drone_1: landed, disarmed (attempt 1)\n")   # fewer than three ACKs
            rows, ctx = G.build_rows(out, heavy, env)
            self.assertEqual(R.overall_verdict(rows), "PASS")
            self.assertEqual(verdict_of(rows, "landed, disarmed"), "info")
            self.assertIn("landed + DISARMED ×3 yes", G.ledger_sentence(rows, ctx, "PASS"))
            (out / "landing_evidence.txt").unlink()
            rows, ctx = G.build_rows(out, heavy, env)
            self.assertEqual(R.overall_verdict(rows), "PASS")

    def test_mavros_armed_true_fails_despite_three_acks(self):
        with tempfile.TemporaryDirectory() as d:
            out, heavy, env = make_run(d)
            (out / "armed_post.txt").write_text("drone_1 armed: false\ndrone_2 armed: true\ndrone_3 armed: false\n")
            rows, ctx = G.build_rows(out, heavy, env)
            self.assertEqual(R.overall_verdict(rows), "FAIL")
            self.assertIn("landed + DISARMED ×3 NOT shown", G.ledger_sentence(rows, ctx, "FAIL"))

    def test_window_caveat_present(self):
        with tempfile.TemporaryDirectory() as d:
            out, heavy, env = make_run(d)
            self.assertIn("vehicle time", G.build_rows(out, heavy, env)[1]["caveats"][0])


class FlySh(unittest.TestCase):
    def test_fly_parses_sleeps_and_keeps_cmu_flow(self):
        src = (CROSSING / "fly.sh").read_text()
        self.assertEqual(subprocess.run(["bash", "-n", str(CROSSING / "fly.sh")]).returncode, 0)
        for n in ('wait_s(){ sleep "$1"; }', "svc takeoff", "svc start", "svc land", "DURATION", "landed:"):
            self.assertIn(n, src)
        self.assertNotIn("ros2 topic echo /clock", src)
        self.assertNotIn("python3", src)


class Template(unittest.TestCase):
    def test_template_and_crossing_have_the_five_files_and_fresh_layout(self):
        for d in (TEMPLATE, CROSSING):
            for f in ("test.env", "fly.sh", "metrics.py", "gates.py", "plots.json", "layout.json"):
                self.assertTrue((d / f).exists(), d / f)
            self.assertEqual(L.main([str(d), "--check"]), 0, d)
            self.assertIn("metrics_core", (d / "gates.py").read_text())

    def test_template_marks_placeholders(self):
        env = (TEMPLATE / "test.env").read_text()
        for k in ("TITLE", "ISSUE", "PURPOSE", "SCOPE"):
            self.assertRegex(env, k + r'=.*CHANGE_ME')


if __name__ == "__main__":
    unittest.main()
