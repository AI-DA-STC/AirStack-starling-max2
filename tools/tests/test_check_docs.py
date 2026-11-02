# tools/tests/test_check_docs.py
import pathlib, sys, tempfile, textwrap, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "docs_check"))
import check_docs as C

PLAN = textwrap.dedent("""\
    # plan
    ## Project 1 · HTX-R1 Swarm Sim Validation (Isaac)
    ### S5 x
    | Issue | Exact Linear title | Status |
    |---|---|---|
    | [NEAR-786](https://linear.app/x) | Re-run hover and 1 m step test on the updated sim drone | Backlog |
    | [NEAR-808](https://linear.app/x) | Feed drone_1’s IMU into cuVSLAM (camera-only → camera + IMU) and compare the scores | Backlog |
    """)

def fixture(tmp, page_rows, records=(), ledger="| # |\n|---|\n", milestones_lines=10, extra="", plan_extra=""):
    root = pathlib.Path(tmp)
    (root / "docs/plans").mkdir(parents=True); (root / "docs/projects").mkdir(); (root / "docs/record").mkdir(); (root / "localisation/results").mkdir(parents=True)
    (root / C.PLAN_FILE).write_text(PLAN + plan_extra)
    (root / "docs/projects/HTX-R1.md").write_text("# HTX-R1\nLinear snapshot: 2026-10-26\n\n### S5 x — SIM ONLY\n| Issue | Title | Linear status | Result | Evidence |\n|---|---|---|---|---|\n" + page_rows + extra)
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
            fixture(d, "| NEAR-786 | Re-run hover and 1m step test | Backlog | PASS, 2026-10-29 | #19 |\n")
            r = C.check_linear_parity()
            self.assertEqual(r.status, "FAIL"); self.assertTrue(any("NEAR-786" in x and "title differs" in x for x in r.details))

    def test_unknown_id_is_fail(self):
        with tempfile.TemporaryDirectory() as d:
            fixture(d, "| NEAR-999 | Anything | Backlog | — | — |\n")
            self.assertEqual(C.check_linear_parity().status, "FAIL")

    def test_parity_title_apostrophe_and_whitespace(self):          # Review Focus 2
        with tempfile.TemporaryDirectory() as d:
            fixture(d, "| NEAR-808 | Feed drone_1's IMU into cuVSLAM (camera-only → camera + IMU) and compare the scores | Backlog | — | — |\n")
            self.assertEqual(C.check_linear_parity().status, "FAIL")
        with tempfile.TemporaryDirectory() as d:
            fixture(d, "| NEAR-808 | Feed  drone_1’s IMU into cuVSLAM (camera-only → camera + IMU)  and compare the scores | Backlog | — | — |\n")
            self.assertEqual(C.check_linear_parity().status, "PASS")

    def test_uncited_pass_record_is_warn_naming_it(self):
        with tempfile.TemporaryDirectory() as d:
            fixture(d, "| NEAR-786 | Re-run hover and 1 m step test on the updated sim drone | Backlog | — | — |\n",
                    records=[("docs/record/a_record.md", "RECORD\n# a\n**Verdict: PASS.** x\n")])
            r = C.check_linear_parity()
            self.assertEqual(r.status, "WARN"); self.assertTrue(any("a_record.md" in x for x in r.details))

    def test_pass_but_backlog_is_warn(self):
        with tempfile.TemporaryDirectory() as d:
            fixture(d, "| NEAR-786 | Re-run hover and 1 m step test on the updated sim drone | Backlog | PASS ×2, 2026-10-28/29 | [a](../record/a_record.md) |\n",
                    records=[("docs/record/a_record.md", "**Verdict: PASS.**\n")], ledger="| 19 | [a_record.md](a_record.md) |\n")
            r = C.check_linear_parity()
            self.assertEqual(r.status, "WARN"); self.assertTrue(any("Backlog" in x and "NEAR-786" in x for x in r.details))

    def test_parity_only_pass_records_count(self):                   # Review Focus 3
        with tempfile.TemporaryDirectory() as d:
            fixture(d, "| NEAR-786 | Re-run hover and 1 m step test on the updated sim drone | Backlog | FAIL ×3, 2026-10-28 | — |\n",
                    records=[("docs/record/b_record.md", "**Verdict: FAIL.**\n"), ("localisation/results/c_record.md", "**Status: pipeline works**\n")])
            self.assertEqual(C.check_linear_parity().status, "PASS")

    def test_status_cell_must_equal_the_named_snapshot(self):           # owner 2026-10-30: Linear status column
        with tempfile.TemporaryDirectory() as d:
            fixture(d, "| NEAR-786 | Re-run hover and 1 m step test on the updated sim drone | Done | — | — |\n")
            r = C.check_linear_parity()
            self.assertEqual(r.status, "FAIL"); self.assertTrue(any("NEAR-786" in x and "status" in x and "Backlog" in x for x in r.details))

    def test_status_cell_matching_the_snapshot_passes(self):
        with tempfile.TemporaryDirectory() as d:
            fixture(d, "| NEAR-786 | Re-run hover and 1 m step test on the updated sim drone | Backlog | — | — |\n")
            self.assertEqual(C.check_linear_parity().status, "PASS")

    def test_issue_row_without_a_status_column_fails(self):
        with tempfile.TemporaryDirectory() as d:
            fixture(d, "| NEAR-786 | Re-run hover and 1 m step test on the updated sim drone | — | — |\n")
            r = C.check_linear_parity()
            self.assertEqual(r.status, "FAIL"); self.assertTrue(any("Linear status" in x for x in r.details))

    def test_no_project_pages_passes_vacuously(self):
        with tempfile.TemporaryDirectory() as d:
            root = fixture(d, ""); (root / "docs/projects/HTX-R1.md").unlink()
            self.assertEqual(C.check_linear_parity().status, "PASS")


CANCELED_PLAN = "| [NEAR-802](https://linear.app/x) | Decide the camera (built-in mono / built-in stereo / added stereo) and write down why | Canceled |\n"


class RescopeParity(unittest.TestCase):                              # rescope 2026-10-30, Review focus 1–3
    def setUp(self):
        self._root = C.ROOT
        self.addCleanup(setattr, C, "ROOT", self._root)

    def test_canceled_row_matching_the_snapshot_passes(self):
        with tempfile.TemporaryDirectory() as d:
            fixture(d, "| NEAR-802 | Decide the camera (built-in mono / built-in stereo / added stereo) and write down why | Canceled | — | — |\n",
                    plan_extra=CANCELED_PLAN)
            r = C.check_linear_parity()
            self.assertEqual(r.status, "PASS", r.details)

    def test_page_milestone_name_must_match_the_snapshot(self):
        with tempfile.TemporaryDirectory() as d:
            fixture(d, "", extra="\n### S5c · Choose the camera for cuVSLAM — DESK (decision)\n",
                    plan_extra="### S5c · Compare the two camera setups for cuVSLAM and OpenVINS\n")
            r = C.check_linear_parity()
            self.assertEqual(r.status, "FAIL")
            self.assertTrue(any("S5c" in x and "Compare the two camera setups" in x for x in r.details), r.details)

    def test_snapshot_milestone_missing_from_every_page_fails(self):
        with tempfile.TemporaryDirectory() as d:
            fixture(d, "", plan_extra="### S5d · Sim flies the real command route (px4_interface)\n")
            r = C.check_linear_parity()
            self.assertEqual(r.status, "FAIL")
            self.assertTrue(any("S5d" in x and "no section" in x for x in r.details), r.details)

    def test_matching_milestone_heading_with_tag_passes(self):
        with tempfile.TemporaryDirectory() as d:
            fixture(d, "", extra="\n### S5c · Compare the two camera setups for cuVSLAM and OpenVINS — SIM ONLY (Isaac)\n",
                    plan_extra="### S5c · Compare the two camera setups for cuVSLAM and OpenVINS\n")
            self.assertEqual(C.check_linear_parity().status, "PASS", C.check_linear_parity().details)


TWO_MS_PLAN = """## Project 1 · HTX-R1 Swarm Sim Validation (Isaac)
### S5c · Cams
| [NEAR-809](https://linear.app/x) | Model the Starling built-in tracking_front camera (AR0144) in sim | Backlog |
### S8 Payload
| [NEAR-798](https://linear.app/x) | Add the Jetson and ZED-style camera weight to the Starling sim model | Backlog |
"""
ROW809 = "| NEAR-809 | Model the Starling built-in tracking_front camera (AR0144) in sim | Backlog | — | — |\n"
ROW798 = "| NEAR-798 | Add the Jetson and ZED-style camera weight to the Starling sim model | Backlog | — | — |\n"
TBL = "| Issue | Title | Linear status | Result | Evidence |\n|---|---|---|---|---|\n"


class MilestoneMembership(unittest.TestCase):                      # final review 2026-10-30, items 3, 4, 6
    def setUp(self):
        self._root = C.ROOT
        self.addCleanup(setattr, C, "ROOT", self._root)

    def run_with(self, d, extra, plan_extra=TWO_MS_PLAN):
        fixture(d, "", extra=extra, plan_extra=plan_extra)
        return C.check_linear_parity()

    def test_issue_under_its_snapshot_milestone_passes(self):
        with tempfile.TemporaryDirectory() as d:
            r = self.run_with(d, "\n### S5c · Cams — SIM ONLY\n" + TBL + ROW809 + "\n### S8 Payload — SIM ONLY\n" + TBL + ROW798)
            self.assertEqual(r.status, "PASS", r.details)

    def test_issue_under_the_wrong_milestone_fails(self):
        with tempfile.TemporaryDirectory() as d:
            r = self.run_with(d, "\n### S5c · Cams — SIM ONLY\n" + TBL + "\n### S8 Payload — SIM ONLY\n" + TBL + ROW798 + ROW809)
            self.assertEqual(r.status, "FAIL")
            self.assertTrue(any("NEAR-809" in x and "S5c" in x and "S8" in x for x in r.details), r.details)

    def test_issue_row_twice_fails(self):
        with tempfile.TemporaryDirectory() as d:
            r = self.run_with(d, "\n### S5c · Cams — SIM ONLY\n" + TBL + ROW809 + ROW809 + "\n### S8 Payload — SIM ONLY\n" + TBL + ROW798)
            self.assertEqual(r.status, "FAIL"); self.assertTrue(any("NEAR-809" in x and "twice" in x for x in r.details), r.details)

    def test_milestone_heading_twice_fails(self):
        with tempfile.TemporaryDirectory() as d:
            r = self.run_with(d, "\n### S5c · Cams — SIM ONLY\n" + TBL + ROW809 + "\n### S8 Payload — SIM ONLY\n" + TBL + ROW798 + "\n### S8 Payload — SIM ONLY\n")
            self.assertEqual(r.status, "FAIL"); self.assertTrue(any("S8" in x and "twice" in x for x in r.details), r.details)

    def test_milestones_out_of_snapshot_order_fail(self):
        with tempfile.TemporaryDirectory() as d:
            r = self.run_with(d, "\n### S8 Payload — SIM ONLY\n" + TBL + ROW798 + "\n### S5c · Cams — SIM ONLY\n" + TBL + ROW809)
            self.assertEqual(r.status, "FAIL"); self.assertTrue(any("order" in x for x in r.details), r.details)

    def test_milestone_on_the_wrong_project_page_fails(self):
        with tempfile.TemporaryDirectory() as d:
            root = fixture(d, "", extra="\n### S8 Payload — SIM ONLY\n" + TBL + ROW798, plan_extra=TWO_MS_PLAN)
            (root / "docs/projects/HTX-R3.md").write_text("# HTX-R3\nLinear snapshot: 2026-10-30\n\n### S5c · Cams — SIM ONLY\n" + TBL + ROW809)
            r = C.check_linear_parity()
            self.assertEqual(r.status, "FAIL"); self.assertTrue(any("S5c" in x and "HTX-R3" in x for x in r.details), r.details)

    def test_page_milestone_code_not_in_plan_fails(self):
        with tempfile.TemporaryDirectory() as d:
            r = self.run_with(d, "\n### S99 Nowhere — SIM ONLY\n", plan_extra="")
            self.assertEqual(r.status, "FAIL"); self.assertTrue(any("S99" in x and "not in" in x for x in r.details), r.details)

    def test_terms_heading_outside_project_sections_is_not_a_milestone(self):
        with tempfile.TemporaryDirectory() as d:
            r = self.run_with(d, "", plan_extra="## How the work is split\n### Terms\n")
            self.assertEqual(r.status, "PASS", r.details)

    def test_empty_heading_fails_with_a_clear_message(self):
        with tempfile.TemporaryDirectory() as d:
            r = self.run_with(d, "\n### \n", plan_extra="")
            self.assertEqual(r.status, "FAIL"); self.assertTrue(any("empty" in x for x in r.details), r.details)


CHANGE_LIST = """# Linear change list (APPLIED)
{applied}
| op | id | milestone | exact title | state | note |
|---|---|---|---|---|---|
| NEW | NEW-1 | S5 | {title} | Backlog | x |

| placeholder | NEAR id |
|---|---|
{map}
"""


class ChangeLists(unittest.TestCase):
    def setUp(self):
        self._root = C.ROOT
        self.addCleanup(setattr, C, "ROOT", self._root)

    def write(self, d, applied=True, title="Re-run hover and 1 m step test on the updated sim drone", mapping="| NEW-1 | NEAR-786 |"):
        root = fixture(d, "")
        (root / "docs/plans/2026-10-30-linear-change-list.md").write_text(CHANGE_LIST.format(
            applied="**Applied:** 2026-10-30" if applied else "", title=title, map=mapping))

    def test_applied_list_with_unmapped_placeholder_fails(self):
        with tempfile.TemporaryDirectory() as d:
            self.write(d, mapping="| NEW-1 … NEW-27 | (filled from the new snapshot) |")
            r = C.check_change_lists()
            self.assertEqual(r.status, "FAIL"); self.assertTrue(any("NEW-1" in x for x in r.details), r.details)

    def test_applied_list_with_a_title_differing_from_the_snapshot_fails(self):
        with tempfile.TemporaryDirectory() as d:
            self.write(d, title="Re-run hover and step test")
            r = C.check_change_lists()
            self.assertEqual(r.status, "FAIL"); self.assertTrue(any("NEAR-786" in x for x in r.details), r.details)

    def test_applied_list_fully_mapped_passes(self):
        with tempfile.TemporaryDirectory() as d:
            self.write(d)
            self.assertEqual(C.check_change_lists().status, "PASS", C.check_change_lists().details)

    def test_placeholder_in_a_mistyped_op_row_fails(self):
        with tempfile.TemporaryDirectory() as d:
            root = fixture(d, "")
            (root / "docs/plans/2026-10-30-linear-change-list.md").write_text(
                CHANGE_LIST.format(applied="**Applied:** x", title="Re-run hover and 1 m step test on the updated sim drone",
                                   map="| NEW-1 | NEAR-786 |").replace("| NEW | NEW-1 |", "| ADD | NEW-1 |"))
            r = C.check_change_lists()
            self.assertEqual(r.status, "FAIL"); self.assertTrue(any("NEW-1" in x and "ADD" in x for x in r.details), r.details)

    def test_two_placeholders_mapped_to_one_id_fail(self):
        with tempfile.TemporaryDirectory() as d:
            self.write(d, mapping="| NEW-1 | NEAR-786 |\n| NEW-2 | NEAR-786 |")
            r = C.check_change_lists()
            self.assertEqual(r.status, "FAIL"); self.assertTrue(any("NEAR-786" in x and "twice" in x for x in r.details), r.details)

    def test_draft_list_is_ignored(self):
        with tempfile.TemporaryDirectory() as d:
            self.write(d, applied=False, mapping="| NEW-1 | (later) |")
            self.assertEqual(C.check_change_lists().status, "PASS")


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


class ChangeLogCheck(unittest.TestCase):
    def setUp(self):
        self._root = C.ROOT; self.addCleanup(setattr, C, "ROOT", self._root)

    def test_skips_before_the_standard_and_fails_on_a_slipped_commit(self):
        from test_changes import make_repo, commit
        with tempfile.TemporaryDirectory() as d:
            C.ROOT = make_repo(d, standard=False); self.assertEqual(C.check_change_log().status, "SKIP")
        with tempfile.TemporaryDirectory() as d:
            C.ROOT = make_repo(d); self.assertEqual(C.check_change_log().status, "PASS")
            commit(C.ROOT, {"tools/sim.sh": "x\n"}, "slipped"); self.assertEqual(C.check_change_log().status, "FAIL")
