# tools/tests/test_report.py
import pathlib, shutil, sys, tempfile, unittest
HERE = pathlib.Path(__file__).resolve().parent
for p in (HERE, HERE.parent, HERE.parent / "live", HERE.parent / "lib"):
    sys.path.insert(0, str(p))
import report as R
import metrics_core as M
FX = HERE / "fixtures" / "run1"

TEST_ENV = '''TITLE="Fake crossing"
PURPOSE="Check the renderer."
SCOPE="Isaac Sim, flat world, no motion-capture positioning (mocap); the drone is not in the loop."
SIM_ONLY_LINE="none of these values is ported to the drone."
ISSUE=NEAR-787
MILESTONE=S5
CONFIG=cbf_sim.yaml
SCENARIO=antipodal
BAG_PREFIX=fake
DURATION_S=45
BASELINE="#4 1.02 m"
'''
GATES = '''
import report as R
def build_rows(out, heavy, env):
    rows = []
    R.isaac_rows(rows, out); R.landing_rows(rows, out)
    R.evidence_rows(rows, out, heavy, env["BAG_PREFIX"], extra_files=("metrics.csv",))
    R.row(rows, "fake gate", "x >= 1", "2", "-", True)
    return rows, {"headline": "min 1.25 m", "crosscheck": None, "node_log_tail": "t=1 d=1.25", "test_stdout": "[07:42:52] go\\n[07:43:30] done",
                  "caveats": ["one fake caveat"], "tuning": {"v": 4.0}}
def ledger_sentence(rows, ctx, verdict):
    return "Fake crossing: " + verdict
def figure_caption(ctx):
    return "Pairwise distance against time. Made by `tools/sim.sh figures fake` from metrics.csv, rows d_12 to d_23."
'''


def make(tmp, **over):
    tmp = pathlib.Path(tmp)
    td = tmp / "fake"; td.mkdir()
    (td / "test.env").write_text(TEST_ENV); (td / "gates.py").write_text(GATES)
    out = tmp / "sim_fake_run1"; out.mkdir()
    for f in ("isaac_evidence.txt", "landing_evidence.txt", "ulog_sysid_map.txt", "res_watch.log"):
        shutil.copy(FX / f, out / f)
    (out / "armed_post.txt").write_text("drone_1 armed: false\ndrone_2 armed: false\ndrone_3 armed: false\n")
    (out / "isaac_evidence.txt").write_text("model_line=3 starling_cfg=3 autostart=3 unknown_model=0 cooking=0 ready=3\n")
    (out / "run_meta.txt").write_text("head=0123456789abcdef\nhead_short=0123456\ndirty_tools=0\nstarted=2026-10-29T12:00:00+08:00\ntz=+08\n")
    (out / "metrics.csv").write_text("x\n")
    heavy = tmp / "heavy"; (heavy / "fake_20261029").mkdir(parents=True)
    (heavy / "fake_20261029" / "metadata.yaml").write_text("x: 1\n")
    for k, v in over.items():
        (out / k).unlink(missing_ok=True) if v is None else (out / k).write_text(v)
    return td, out, heavy


class Report(unittest.TestCase):
    def setUp(self):
        self._d = tempfile.TemporaryDirectory(); self.addCleanup(self._d.cleanup)
        self.td, self.out, self.heavy = make(self._d.name)
        self.env = R.parse_env(self.td / "test.env"); self.G = R.load_gates(self.td)

    def test_clean_run_renders_pass_record_in_docs_standard_shape(self):
        rows, ctx = self.G.build_rows(self.out, self.heavy, self.env)
        self.assertEqual(R.overall_verdict(rows), "PASS")
        md = R.render(self.env, rows, ctx, self.out, self.heavy, "PASS", [], 20, "NEAR-787")
        head = md.splitlines()
        self.assertTrue(head[0].startswith("RECORD · SIM — ")); self.assertIn("Sim-only", head[0])
        self.assertIn("**Verdict: PASS.**", md); self.assertIn("**Scope:**", md)
        self.assertIn("| Check | Criterion | Measured | Baseline | Verdict |", md)
        self.assertIn("| 20 | ", md.splitlines()[-2]); self.assertIn("NEAR-787", md.splitlines()[-2])

    def test_figure_block_only_when_png_exists_and_caption_within_400(self):
        rows, ctx = self.G.build_rows(self.out, self.heavy, self.env)
        self.assertNotIn('<a id="fig-1"></a>', R.render(self.env, rows, ctx, self.out, self.heavy, "PASS", [], 20, "NEAR-787"))
        (self.out / "fig-1.png").write_bytes(b"x")
        md = R.render(self.env, rows, ctx, self.out, self.heavy, "PASS", [], 20, "NEAR-787")
        i = md.index('<a id="fig-1"></a>'); self.assertTrue(md[i:].splitlines()[1].startswith("!["))
        cap = next(l for l in md.splitlines() if l.startswith("*Figure 1.")); self.assertLessEqual(len(cap), 400); self.assertTrue(cap.endswith("*"))

    def test_aborted_marker_forces_aborted_verdict(self):
        (self.out / "aborted.txt").write_text("aborted=2026-10-29T12:00:00+08:00\n")
        rc = R.main([str(self.td), str(self.out), "--heavy", str(self.heavy), "--no-verdict-log"]); self.assertEqual(rc, 3)
        self.assertIn("**Verdict: ABORTED.**", (self.out.parent / f"{self.out.name}_record.md").read_text())

    def test_missing_armed_post_is_unverified_and_incomplete(self):
        (self.out / "armed_post.txt").unlink()
        rows, _ = self.G.build_rows(self.out, self.heavy, self.env); self.assertEqual(R.overall_verdict(rows), "INCOMPLETE")

    def test_fill_ctx_loads_tuning_stdout_and_node_log_from_the_run_dir(self):
        for f in ("status_pre.json", "test_stdout.log"):
            shutil.copy(FX / f, self.out / f)
        (self.out / "metrics_node.log").write_text("\n".join("line %d" % i for i in range(30)) + "\n")
        ctx = R.fill_ctx({}, self.out)
        self.assertTrue(ctx["tuning"]); self.assertEqual(ctx["node_log_tail"].splitlines()[-1], "line 29")
        self.assertEqual(len(ctx["node_log_tail"].splitlines()), 12)
        self.assertRegex(ctx["test_stdout"], r"\[\d\d:\d\d:\d\d\]")
        md = R.render(self.env, [], ctx, self.out, self.heavy, "INCOMPLETE", [], 20, "NEAR-787")
        self.assertNotIn("flight span n/a", md); self.assertNotIn("tuning n/a", md)
        keep = R.fill_ctx({"tuning": {"v": 1}, "test_stdout": "[01:02:03] x"}, self.out)       # gates.py values win
        self.assertEqual(keep["tuning"], {"v": 1}); self.assertEqual(keep["test_stdout"], "[01:02:03] x")

    def test_headline_text_reads_the_named_row(self):
        rows = []
        R.row(rows, "min pairwise distance >= 1.10 m", "c", "0.98 m (margin -0.12 m)", "-", False)
        self.assertEqual(R.headline_text(rows, {"headline_row": "min pairwise distance"}), "0.98 m (margin -0.12 m)")
        self.assertEqual(R.headline_text(rows, {}), "n/a")

    def test_cli_pass_exit_0_and_verdict_log(self):
        rc = R.main([str(self.td), str(self.out), "--heavy", str(self.heavy), "--ledger", "20", "--issue", "NEAR-787"])
        self.assertEqual(rc, 0)
        self.assertIn("verdict=PASS", (self.out / "verdicts.log").read_text())

    def test_crosscheck_rows_verdicts(self):
        rows = []; R.crosscheck_rows(rows, None, "min_pair_distance"); self.assertEqual(rows[0].verdict, "UNVERIFIED")
        rows = []; R.crosscheck_rows(rows, [M.CrossRow("min_pair_distance", 0.02, "continuous", 0.03, 0, 0, 100, 0.0, False)], "min_pair_distance"); self.assertEqual(rows[0].verdict, "FAIL")
        rows = []; R.crosscheck_rows(rows, [M.CrossRow("min_pair_distance", 0.02, "continuous", 0.001, 0, 0, 100, 0.0, True),
                                            M.CrossRow("emergency", 0.0, "flag", 0, 3, 3, 100, 0.01, True)], "min_pair_distance")
        self.assertEqual(rows[0].verdict, "PASS"); self.assertIn("Σ 3 vs 3", rows[0].measured); self.assertIn("Δmax 0.001", rows[0].measured)

    def test_cli_exit_codes_and_bad_issue(self):
        with self.assertRaises(SystemExit): R.main([str(self.td), str(self.out), "--issue", "NEAR787"])

    def test_ledger_row_and_append_verdict(self):
        self.assertEqual(R.ledger_row(None, "2026-10-29", "S", "r", None), "| ? | 2026-10-29 | SIM | S | [r_record.md](r_record.md) | ? |")
        line = R.append_verdict(self.out, "PASS", [], "abc"); self.assertIn("head=abc verdict=PASS fail=0 unverified=0", line)

    def test_reading_sits_directly_above_the_figure_anchor_and_links_it(self):
        rows, ctx = self.G.build_rows(self.out, self.heavy, self.env)
        (self.out / "fig-1.png").write_bytes(b"x")
        ctx["reading"] = "[Figure 1](#fig-1) shows the minimum distance stayed at 1.25 m."
        L = R.render(self.env, rows, ctx, self.out, self.heavy, "PASS", [], 20, None).splitlines()
        i = L.index('<a id="fig-1"></a>'); self.assertEqual(L[i - 2], ctx["reading"]); self.assertEqual(L[i - 1], "")
        del ctx["reading"]; ctx["headline"] = "min 1.25 m"
        L = R.render(self.env, rows, ctx, self.out, self.heavy, "PASS", [], 20, None).splitlines()
        i = L.index('<a id="fig-1"></a>'); self.assertIn("[Figure 1](#fig-1)", L[i - 2]); self.assertIn("min 1.25 m", L[i - 2])

    def test_long_caption_is_trimmed_with_a_warning(self):
        rows, ctx = self.G.build_rows(self.out, self.heavy, self.env)
        (self.out / "fig-1.png").write_bytes(b"x"); ctx["figure_caption"] = "word " * 200
        import contextlib, io
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            md = R.render(self.env, rows, ctx, self.out, self.heavy, "PASS", [], 20, None)
        cap = next(l for l in md.splitlines() if l.startswith("*Figure 1."))
        self.assertLessEqual(len(cap), 400); self.assertTrue(cap.endswith("*")); self.assertIn("warning", err.getvalue())

    def test_issue_flag_beats_test_env_everywhere(self):
        rows, ctx = self.G.build_rows(self.out, self.heavy, self.env)
        md = R.render(self.env, rows, ctx, self.out, self.heavy, "PASS", [], 20, "NEAR-800")
        self.assertNotIn("NEAR-787", md)
        self.assertIn("For Linear NEAR-800 (milestone", md); self.assertIn("NEAR-800 |", md.splitlines()[-2])
        R.main([str(self.td), str(self.out), "--heavy", str(self.heavy), "--issue", "NEAR-800", "--no-verdict-log"])
        self.assertNotIn("NEAR-787", (self.out.parent / f"{self.out.name}_record.md").read_text())
        md = R.render(self.env, rows, ctx, self.out, self.heavy, "PASS", [], 20, None)   # no flag: test.env
        self.assertIn("For Linear NEAR-787 (milestone", md)

    def test_ledger_sentence_pipe_is_escaped(self):
        self.assertIn("a \\| b", R.ledger_row(1, "d", "a | b", "r", "NEAR-1"))

    def test_history_and_landing_log_appear_once(self):
        rows, ctx = self.G.build_rows(self.out, self.heavy, self.env)
        md = R.render(self.env, rows, ctx, self.out, self.heavy, "PASS", ["2026 head=x verdict=PASS fail=0 unverified=0"], 20, None)
        self.assertEqual(md.count("verdict=PASS fail=0"), 1)
        self.assertEqual(md.count("landed, disarmed (attempt 1)"), 3)   # the three lines of the one log block

    def test_broken_gates_still_leaves_an_incomplete_record(self):
        (self.td / "gates.py").write_text("def build_rows(out, heavy, env):\n    raise RuntimeError('boom')\ndef ledger_sentence(r, c, v):\n    return 'x'\ndef figure_caption(c):\n    return 'y'\n")
        rc = R.main([str(self.td), str(self.out), "--heavy", str(self.heavy), "--no-verdict-log"])
        self.assertEqual(rc, 2)
        md = (self.out.parent / f"{self.out.name}_record.md").read_text()
        self.assertIn("**Verdict: INCOMPLETE.**", md); self.assertIn("RuntimeError: boom", md)

    def test_parse_env_strips_quotes_and_comments(self):
        e = self.env; self.assertEqual(e["TITLE"], "Fake crossing"); self.assertEqual(e["ISSUE"], "NEAR-787")


class FinalFixes(unittest.TestCase):
    def setUp(self):
        self._d = tempfile.TemporaryDirectory(); self.addCleanup(self._d.cleanup)
        self.td, self.out, self.heavy = make(self._d.name)
        self.env = R.parse_env(self.td / "test.env"); self.G = R.load_gates(self.td)

    def test_no_gate_rows_is_incomplete_not_pass(self):
        self.assertEqual(R.overall_verdict([]), "INCOMPLETE")
        rows = []; R.row(rows, "note", "informational", "x", "-", None, gate=False)
        self.assertEqual(R.overall_verdict(rows), "INCOMPLETE")
        self.assertEqual(R.overall_verdict([], aborted=True), "ABORTED")
        rows = []; R.row(rows, "g", "c", "m", "-", True)
        self.assertEqual(R.overall_verdict(rows), "PASS")

    def test_newest_bag_dir_is_used(self):
        import os
        new = self.heavy / "fake_20261030"; new.mkdir(); (new / "metadata.yaml").write_text("x: 1\n")
        os.utime(self.heavy / "fake_20261029", (1_000_000_000, 1_000_000_000))                 # older, sorts first by name
        old = self.heavy / "fake_20261031"; old.mkdir(); (old / "metadata.yaml").write_text("x: 1\n")
        os.utime(old, (1_000_000_100, 1_000_000_100))                                         # older, sorts last by name
        rows = []; R.evidence_rows(rows, self.out, self.heavy, "fake")
        self.assertTrue(rows[0].measured.startswith("fake_20261030:"), rows[0].measured)

    def test_caveats_txt_lines_join_the_record_after_the_gates_caveats(self):
        (self.out / "caveats.txt").write_text("landing timed out; stack left up; bag left in the container\none fake caveat\n\nsecond run caveat\n")
        R.main([str(self.td), str(self.out), "--heavy", str(self.heavy), "--no-verdict-log"])
        md = (self.out.parent / f"{self.out.name}_record.md").read_text()
        cav = md.split("## Caveats", 1)[1].split("## Ledger", 1)[0]
        lines = [l for l in cav.splitlines() if l.startswith("- ")]
        self.assertEqual(lines, ["- one fake caveat", "- landing timed out; stack left up; bag left in the container", "- second run caveat"])


class ArmedUnknown(unittest.TestCase):
    def test_unknown_lines_are_unreadable_never_disarmed(self):
        self.assertIsNone(R.parse_armed_post("drone_1 armed: false\ndrone_2 armed: UNKNOWN\ndrone_3 armed: UNKNOWN\n"))


if __name__ == "__main__":
    unittest.main()
