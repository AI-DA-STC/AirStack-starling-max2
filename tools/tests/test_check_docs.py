# tools/tests/test_check_docs.py
import pathlib, sys, tempfile, textwrap, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "docs_check"))
import check_docs as C

PLAN = textwrap.dedent("""\
    # plan
    | Issue | Exact Linear title | Status |
    |---|---|---|
    | [NEAR-786](https://linear.app/x) | Re-run hover and 1 m step test on the updated sim drone | Backlog |
    | [NEAR-808](https://linear.app/x) | Feed drone_1’s IMU into cuVSLAM (camera-only → camera + IMU) and compare the scores | Backlog |
    """)

def fixture(tmp, page_rows, records=(), ledger="| # |\n|---|\n", milestones_lines=10, extra=""):
    root = pathlib.Path(tmp)
    (root / "docs/plans").mkdir(parents=True); (root / "docs/projects").mkdir(); (root / "docs/record").mkdir(); (root / "localisation/results").mkdir(parents=True)
    (root / "docs/plans/2026-10-26-project-plan-linear.md").write_text(PLAN)
    (root / "docs/projects/HTX-R1.md").write_text("# HTX-R1\nLinear snapshot: 2026-10-26\n\n### S5 x — SIM ONLY\n| Issue | Title | Result | Evidence |\n|---|---|---|---|\n" + page_rows + extra)
    for name, head in records: (root / name).write_text(head)
    (root / "docs/record/LEDGER.md").write_text(ledger)
    (root / "docs/MILESTONES.md").write_text("\n".join(f"line {i}" for i in range(milestones_lines)) + "\n")
    (root / "README.md").write_text("# r\n"); (root / "CLAUDE.md").write_text("# c\n")
    C.ROOT = root
    return root

class LinearParity(unittest.TestCase):
    def setUp(self):
        self._root = C.ROOT
        self.addCleanup(setattr, C, "ROOT", self._root)

    def test_wrong_title_is_fail_and_names_the_id(self):
        with tempfile.TemporaryDirectory() as d:
            fixture(d, "| NEAR-786 | Re-run hover and 1m step test | PASS, 2026-10-29 | #19 |\n")
            r = C.check_linear_parity()
            self.assertEqual(r.status, "FAIL"); self.assertTrue(any("NEAR-786" in x and "title differs" in x for x in r.details))

    def test_unknown_id_is_fail(self):
        with tempfile.TemporaryDirectory() as d:
            fixture(d, "| NEAR-999 | Anything | — | — |\n")
            self.assertEqual(C.check_linear_parity().status, "FAIL")

    def test_parity_title_apostrophe_and_whitespace(self):          # Review Focus 2
        with tempfile.TemporaryDirectory() as d:
            fixture(d, "| NEAR-808 | Feed drone_1's IMU into cuVSLAM (camera-only → camera + IMU) and compare the scores | — | — |\n")
            self.assertEqual(C.check_linear_parity().status, "FAIL")
        with tempfile.TemporaryDirectory() as d:
            fixture(d, "| NEAR-808 | Feed  drone_1’s IMU into cuVSLAM (camera-only → camera + IMU)  and compare the scores | — | — |\n")
            self.assertEqual(C.check_linear_parity().status, "PASS")

    def test_uncited_pass_record_is_warn_naming_it(self):
        with tempfile.TemporaryDirectory() as d:
            fixture(d, "| NEAR-786 | Re-run hover and 1 m step test on the updated sim drone | — | — |\n",
                    records=[("docs/record/a_record.md", "RECORD\n# a\n**Verdict: PASS.** x\n")])
            r = C.check_linear_parity()
            self.assertEqual(r.status, "WARN"); self.assertTrue(any("a_record.md" in x for x in r.details))

    def test_pass_but_backlog_is_warn(self):
        with tempfile.TemporaryDirectory() as d:
            fixture(d, "| NEAR-786 | Re-run hover and 1 m step test on the updated sim drone | PASS ×2, 2026-10-28/29 | [a](../record/a_record.md) |\n",
                    records=[("docs/record/a_record.md", "**Verdict: PASS.**\n")], ledger="| 19 | [a_record.md](a_record.md) |\n")
            r = C.check_linear_parity()
            self.assertEqual(r.status, "WARN"); self.assertTrue(any("Backlog" in x and "NEAR-786" in x for x in r.details))

    def test_parity_only_pass_records_count(self):                   # Review Focus 3
        with tempfile.TemporaryDirectory() as d:
            fixture(d, "| NEAR-786 | Re-run hover and 1 m step test on the updated sim drone | FAIL ×3, 2026-10-28 | — |\n",
                    records=[("docs/record/b_record.md", "**Verdict: FAIL.**\n"), ("localisation/results/c_record.md", "**Status: pipeline works**\n")])
            self.assertEqual(C.check_linear_parity().status, "PASS")

    def test_no_project_pages_passes_vacuously(self):
        with tempfile.TemporaryDirectory() as d:
            root = fixture(d, ""); (root / "docs/projects/HTX-R1.md").unlink()
            self.assertEqual(C.check_linear_parity().status, "PASS")

class Images(unittest.TestCase):
    def setUp(self):
        self._root = C.ROOT
        self.addCleanup(setattr, C, "ROOT", self._root)

    def test_images_relative_only(self):                             # Review Focus 5
        with tempfile.TemporaryDirectory() as d:
            root = fixture(d, "", extra="![a](../record/figures/nope.png)\n![b](https://x/y.png)\n<img src=\"../record/figures/ok.png#x\">\n")
            (root / "docs/record/figures").mkdir(); (root / "docs/record/figures/ok.png").write_bytes(b"x")
            r = C.check_images([root / "docs/projects/HTX-R1.md"])
            self.assertEqual(r.status, "FAIL"); self.assertEqual(len(r.details), 1); self.assertIn("nope.png", r.details[0])
