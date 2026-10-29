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

class PageBudgets(unittest.TestCase):
    def setUp(self):
        self._root = C.ROOT
        self.addCleanup(setattr, C, "ROOT", self._root)

    def test_caption_over_400_chars_fails(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d); (root / "docs" / "projects").mkdir(parents=True)
            (root / "docs" / "MILESTONES.md").write_text("# top\n")
            page = "### S1 x — SIM ONLY\n![f](../record/figures/x.png)\n*" + "caption word " * 40 + "*\n"
            (root / "docs" / "projects" / "HTX-R1.md").write_text(page)
            C.ROOT = root
            r = C.check_page_budgets()
            self.assertEqual(r.status, "FAIL")
            self.assertTrue(any("caption is" in x and "(max 400)" in x for x in r.details), r.details)

    def test_caption_under_400_chars_passes(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d); (root / "docs" / "projects").mkdir(parents=True)
            (root / "docs" / "MILESTONES.md").write_text("# top\n")
            page = "### S1 x — SIM ONLY\n![f](../record/figures/x.png)\n*Figure 1. Short caption.*\n"
            (root / "docs" / "projects" / "HTX-R1.md").write_text(page)
            C.ROOT = root
            self.assertEqual(C.check_page_budgets().status, "PASS")

    def test_top_page_61_lines_fails(self):
        with tempfile.TemporaryDirectory() as d:
            fixture(d, "", milestones_lines=61)
            r = C.check_page_budgets(); self.assertEqual(r.status, "FAIL"); self.assertTrue(any("MILESTONES.md: 61/60 lines" in x for x in r.details))

    def test_top_page_60_lines_passes(self):
        with tempfile.TemporaryDirectory() as d:
            fixture(d, "", milestones_lines=60); self.assertEqual(C.check_page_budgets().status, "PASS")

    def test_project_page_251_lines_fails(self):
        with tempfile.TemporaryDirectory() as d:
            root = fixture(d, "")
            (root / "docs/projects/HTX-R2.md").write_text("\n".join(f"l{i}" for i in range(251)) + "\n")
            r = C.check_page_budgets(); self.assertEqual(r.status, "FAIL"); self.assertTrue(any("HTX-R2.md: 251/250 lines" in x for x in r.details))
        with tempfile.TemporaryDirectory() as d:
            root = fixture(d, "")
            (root / "docs/projects/HTX-R2.md").write_text("\n".join(f"l{i}" for i in range(250)) + "\n")
            self.assertEqual(C.check_page_budgets().status, "PASS")

    def test_milestone_section_counts_exclude_figures(self):
        body = "\n".join(f"line {i}" for i in range(37)) + "\n![fig](x.png)\n*caption*\n"
        with tempfile.TemporaryDirectory() as d:
            fixture(d, "", extra=body); self.assertEqual(C.check_page_budgets().status, "PASS")
        with tempfile.TemporaryDirectory() as d:
            fixture(d, "", extra=body + "one more\n")
            r = C.check_page_budgets(); self.assertEqual(r.status, "FAIL"); self.assertTrue(any("41/40 lines (figures excluded)" in x for x in r.details))

    def test_long_cell_fails_except_title_column(self):
        long = "x" * 121
        with tempfile.TemporaryDirectory() as d:
            fixture(d, f"| NEAR-786 | {long} | — | — |\n"); self.assertEqual(C.check_page_budgets().status, "PASS")
        with tempfile.TemporaryDirectory() as d:
            fixture(d, f"| NEAR-786 | t | {long} | — |\n"); r = C.check_page_budgets(); self.assertEqual(r.status, "FAIL"); self.assertIn("cell 3", r.details[0])
        with tempfile.TemporaryDirectory() as d:
            fixture(d, f"| [NEAR-786](x) | {long} | — | — |\n"); self.assertEqual(C.check_page_budgets().status, "PASS")

    def test_ledger_cells_not_budgeted(self):
        with tempfile.TemporaryDirectory() as d:
            fixture(d, "", ledger="| # |\n|---|\n| " + "y" * 200 + " |\n"); self.assertEqual(C.check_page_budgets().status, "PASS")


class FigureRefs(unittest.TestCase):
    """Figures are numbered in page order, anchored, and every mention in text links to its figure."""
    GOOD = ('<a id="fig-1"></a>\n![a](x.png)\n*Figure 1. A.*\n\nSee [Figure 1](#fig-1).\n\n'
            '<a id="fig-2"></a>\n![b](y.png)\n*Figure 2. B.*\n')

    def setUp(self):
        self._root = C.ROOT
        self.addCleanup(setattr, C, "ROOT", self._root)

    def test_good_page_passes(self):
        with tempfile.TemporaryDirectory() as d:
            fixture(d, "", extra=self.GOOD); self.assertEqual(C.check_figure_refs().status, "PASS")

    def test_out_of_order_numbering_fails(self):
        with tempfile.TemporaryDirectory() as d:
            fixture(d, "", extra=self.GOOD.replace("Figure 1. A", "Figure 2. A").replace("Figure 2. B", "Figure 1. B"))
            r = C.check_figure_refs(); self.assertEqual(r.status, "FAIL"); self.assertTrue(any("expected Figure 1" in x for x in r.details), r.details)

    def test_missing_anchor_fails(self):
        with tempfile.TemporaryDirectory() as d:
            fixture(d, "", extra=self.GOOD.replace('<a id="fig-2"></a>\n', ""))
            r = C.check_figure_refs(); self.assertEqual(r.status, "FAIL"); self.assertTrue(any('<a id="fig-2">' in x for x in r.details), r.details)

    def test_unlinked_mention_fails(self):
        with tempfile.TemporaryDirectory() as d:
            fixture(d, "", extra=self.GOOD.replace("See [Figure 1](#fig-1).", "See Figure 1."))
            r = C.check_figure_refs(); self.assertEqual(r.status, "FAIL"); self.assertTrue(any("not linked" in x for x in r.details), r.details)


class PurposeLines(unittest.TestCase):
    def setUp(self):
        self._root = C.ROOT
        self.addCleanup(setattr, C, "ROOT", self._root)

    def test_section_without_purpose_fails(self):
        with tempfile.TemporaryDirectory() as d:
            fixture(d, "")                       # the fixture's S5 section has no **Purpose:** line
            r = C.check_purpose_lines(); self.assertEqual(r.status, "FAIL"); self.assertTrue(any("S5" in x and "Purpose" in x for x in r.details), r.details)

    def test_section_with_purpose_passes(self):
        with tempfile.TemporaryDirectory() as d:
            root = fixture(d, "")
            f = root / "docs/projects/HTX-R1.md"; f.write_text(f.read_text().replace("### S5 x — SIM ONLY\n", "### S5 x — SIM ONLY\n**Purpose:** because.\n"))
            self.assertEqual(C.check_purpose_lines().status, "PASS")
