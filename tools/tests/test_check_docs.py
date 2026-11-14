# tools/tests/test_check_docs.py
import json, pathlib, subprocess, sys, tempfile, textwrap, unittest
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


class SingleHome(unittest.TestCase):                                  # design 2026-11-06: one home per moved fact, WARN only
    ONLY = ("", ["only", "Import from file → /x/layout.json", "localisation/README.md"])
    NEAR = ("", ["only", "teleop.launch.py config:=$CFG", "localisation/README.md,docs/TELEOP.md", "teleop_single_ours.yaml"])
    REQ = ("", ["require", "never go on the real drone", "docs/TELEOP.md"])

    def setUp(self):
        self._root, self._here = C.ROOT, C.HERE
        self.addCleanup(setattr, C, "ROOT", self._root); self.addCleanup(setattr, C, "HERE", self._here)

    def tree(self, d, pages):
        root = pathlib.Path(d)
        pages = {"README.md": "# r\n", "CLAUDE.md": "# c\n", "localisation/README.md": "# l\n", "docs/TELEOP.md": "# t\n", **pages}
        for name, text in pages.items():
            (root / name).parent.mkdir(parents=True, exist_ok=True); (root / name).write_text(text)
        C.ROOT = root
        return root

    def test_copy_outside_its_home_warns_with_file_and_line(self):
        with tempfile.TemporaryDirectory() as d:
            self.tree(d, {"localisation/README.md": "Layouts → Import from file → `/x/layout.json`\n",
                          "docs/RUNBOOK.md": "# r\nLayouts → Import from file → `/x/layout.json`\n"})
            r = C.check_single_home([self.ONLY])
            self.assertEqual(r.status, "WARN"); self.assertTrue(any(x.startswith("docs/RUNBOOK.md:2:") for x in r.details), r.details)

    def test_phrase_only_in_its_home_passes(self):
        with tempfile.TemporaryDirectory() as d:
            self.tree(d, {"localisation/README.md": "Layouts → Import from file → `/x/layout.json`\n"})
            self.assertEqual(C.check_single_home([self.ONLY]).status, "PASS")

    def test_copies_in_tools_and_localisation_pages_are_found(self):
        with tempfile.TemporaryDirectory() as d:
            self.tree(d, {"tools/README.md": "Import from file → /x/layout.json\n",
                          "localisation/scenes/construction_site/README.md": "Import from file → /x/layout.json\n"})
            r = C.check_single_home([self.ONLY])
            self.assertTrue(any(x.startswith("tools/README.md:1:") for x in r.details), r.details)
            self.assertTrue(any(x.startswith("localisation/scenes/construction_site/README.md:1:") for x in r.details), r.details)

    def test_dated_history_is_exempt(self):
        with tempfile.TemporaryDirectory() as d:
            self.tree(d, {"localisation/README.md": "Import from file → /x/layout.json\n",     # the phrase is in its home, so only the exempt copies are in play
                          **{n: "Import from file → /x/layout.json\n" for n in
                             ("docs/plans/p.md", "docs/superpowers/specs/s.md", "docs/record/r_record.md", ".claude/worktrees/a/docs/TELEOP.md")}})
            self.assertEqual(C.check_single_home([self.ONLY]).status, "PASS")

    def test_backticks_and_spacing_are_ignored(self):
        with tempfile.TemporaryDirectory() as d:
            self.tree(d, {"docs/GLOSSARY.md": "Import  from file →\t`/x/layout.json`\n"})
            self.assertEqual(C.check_single_home([self.ONLY]).status, "WARN")

    def test_near_phrase_on_the_line_or_three_above_warns_inside_a_fence(self):
        with tempfile.TemporaryDirectory() as d:
            self.tree(d, {"docs/RUNBOOK.md": "```bash\nCFG=/c/teleop_single_ours.yaml\n# a\n# b\nros2 launch p teleop.launch.py config:=$CFG\n```\n"})
            r = C.check_single_home([self.NEAR])
            self.assertEqual(r.status, "WARN"); self.assertTrue(any(x.startswith("docs/RUNBOOK.md:5:") for x in r.details), r.details)

    def test_near_phrase_four_lines_above_or_below_passes(self):
        with tempfile.TemporaryDirectory() as d:
            self.tree(d, {"localisation/README.md": "CFG=/c/teleop_single_ours.yaml\nros2 launch p teleop.launch.py config:=$CFG\n",     # the home has it
                          "docs/RUNBOOK.md": "CFG=/c/teleop_single_ours.yaml\n# a\n# b\n# c\nros2 launch p teleop.launch.py config:=$CFG\n",
                          "docs/SCENARIOS.md": "CFG=/c/teleop_real_ours.yaml\nros2 launch p teleop.launch.py config:=$CFG\nin sim use teleop_single_ours.yaml\n"})
            self.assertEqual(C.check_single_home([self.NEAR]).status, "PASS")

    def test_require_missing_warns_and_a_wrapped_phrase_passes(self):
        with tempfile.TemporaryDirectory() as d:
            self.tree(d, {})
            r = C.check_single_home([self.REQ])
            self.assertEqual(r.status, "WARN"); self.assertTrue(any("docs/TELEOP.md" in x and "never go on the real drone" in x for x in r.details), r.details)
        with tempfile.TemporaryDirectory() as d:
            self.tree(d, {"docs/TELEOP.md": "**Sim only.** These never go on the\nreal drone.\n"})
            self.assertEqual(C.check_single_home([self.REQ]).status, "PASS")

    def test_listed_home_that_does_not_exist_warns(self):
        with tempfile.TemporaryDirectory() as d:
            self.tree(d, {})
            r = C.check_single_home([("", ["only", "x y", "localisation/GONE.md"])])
            self.assertEqual(r.status, "WARN"); self.assertTrue(any("localisation/GONE.md" in x and "does not exist" in x for x in r.details), r.details)

    def test_only_phrase_missing_from_its_first_home_warns(self):
        with tempfile.TemporaryDirectory() as d:
            self.tree(d, {})
            r = C.check_single_home([self.ONLY])
            self.assertEqual(r.status, "WARN"); self.assertTrue(any(x.startswith("localisation/README.md:") and "missing from its home" in x for x in r.details), r.details)
        with tempfile.TemporaryDirectory() as d:
            self.tree(d, {"localisation/README.md": "CFG=/c/teleop_single_ours.yaml\nros2 launch p teleop.launch.py config:=$CFG\n"})
            self.assertEqual(C.check_single_home([self.NEAR]).status, "PASS")

    def test_an_exception_inside_the_check_is_a_warn_not_a_fail(self):
        with tempfile.TemporaryDirectory() as d:
            self.tree(d, {})
            r = C.check_single_home([("", ["only", "x y", None])])       # a row that makes the check raise
            self.assertEqual(r.status, "WARN"); self.assertIn("single-home check error", r.summary)

    def test_bad_rows_and_a_missing_registry_warn_never_fail(self):
        with tempfile.TemporaryDirectory() as d:
            self.tree(d, {})
            r = C.check_single_home([("", ["maybe", "x", "a.md"]), ("", ["only", "x"])])
            self.assertEqual(r.status, "WARN"); self.assertEqual(sum("malformed" in x for x in r.details), 2, r.details)
            C.HERE = pathlib.Path(d)                                    # no single_home.txt here
            r = C.check_single_home()
            self.assertEqual(r.status, "WARN"); self.assertIn("single_home.txt", r.summary)

    def test_shipped_registry_has_the_designs_rows(self):
        rows = C.registry("single_home.txt")
        self.assertEqual([(f[0].strip(), f[1].strip()) for _, f in rows],
                         [("only", "Import from file → /teleop-foxglove/teleop-cuvslam.json"), ("only", "teleop.launch.py config:=$CFG"),
                          ("only", "sim_keyboard_teleop_2026-11-04.mp4"), ("only", "cd ~/AirStack-starling-max2 && tools/sim.sh relay"),
                          ("only", "drive mode ⇄ room mode"), ("require", "never go on the real drone")])
        self.assertEqual(rows[1][1][3].strip(), "teleop_single_ours.yaml")
        for _, f in rows:
            for fn in f[2].split(","):
                self.assertTrue((self._root / fn.strip()).is_file(), fn)

    def test_registered_in_the_checker_run(self):
        out = subprocess.run([sys.executable, "-I", str(pathlib.Path(C.__file__)), "--json"], capture_output=True, text=True, cwd=self._root).stdout
        self.assertIn("single-home", [r["check"] for r in json.loads(out)["results"]])


class RunbookProcedure(unittest.TestCase):                            # design 2026-11-14 D11: procedure-page rules for RUNBOOK
    CHOOSER = "| Session | SIM or REAL | Go to |"
    HEADS = {"B": "## B · REAL DRONE session (mocap room)", "B9": "### B9 — Fly one real drone with the gamepad",
             "B10": "### B10 — Two real drones, one flown by hand", "C": "## C · GOAL FLIGHTS (fly to commanded waypoints)",
             "C9": "### C9 — Two real drones with the collision filter (CBF)"}
    IP, SYS = {"drone_1": "10.40.2.11", "drone_2": "10.40.2.10"}, {"drone_1": "1", "drone_2": "2"}
    TAKEOFF, START, LAND = (f"ros2 service call /swarm_commander/{c} std_srvs/srv/Trigger" for c in ("takeoff", "start", "land"))

    def setUp(self):
        self._root = C.ROOT; self.addCleanup(setattr, C, "ROOT", self._root)

    def opening(self, drones=("drone_2",), bodies=True, rate="a steady rate"):
        """The shared opening for one or two drones; bodies=False is the bare `./mocap.sh` + no target_systems form."""
        mocap = (f'MOCAP_BODIES="{" ".join(drones)}" ' if bodies else "") + "./mocap.sh"
        launch = "drones:=" + ",".join(drones) + (" target_systems:=" + ",".join(self.SYS[d] for d in drones) if bodies else "")
        out = ["<!-- shared-opening -->", "**1 · Laptop · ping every drone**", "```bash", *[f"ping -c2 {self.IP[d]}" for d in drones], "```", "",
               "**2 · Laptop · mocap**", "```bash", f"cd ~/AirStack-starling-max2 && {mocap}", "```", "", "**3 · Pane 1 · link alive**"]
        for d in drones:
            out += ["```bash", f"ros2 topic hz /{d}/fmu/out/vehicle_status", "```"]
        out += [f"Must see: {rate}. Ctrl-C after each reading.", "", "**4 · Pane 3 · interfaces**", "```bash",
                f"ros2 launch svg_ground_control real_interfaces.launch.py {launch}", "```"]
        out += [f"Must see: the startup line of `{d}` says `target_system={self.SYS[d]}`." for d in drones]
        return out + ["<!-- /shared-opening -->", ""]

    def seq(self, name, opening=None, stop=True, gap=6, body=()):
        """One real sequence: heading, world blockquote (dated: exempt), opening, body, stop table, takeoff/start/land blocks.
        gap = line of `takeoff` minus line of the stop table's last row."""
        out = [self.HEADS[name], "", "> **WORLD: REAL DRONE.** First flown 2026-11-12 ([#34](record/LEDGER.md)).", ""]
        out += self.opening() if opening is None else opening
        out += list(body)
        if stop:
            out += ["**Stop table.** The PREFLIGHT.md emergency table comes first.", "", "| What you see | Do this |", "|---|---|",
                    "| Anything scary | KILL, then `land` once |"]
            out += [""] * (gap - 2)
        out += ["```bash", self.TAKEOFF, "```", "", "```bash", self.START, "```", "", "```bash", self.LAND, "```", ""]
        return out

    def page(self, top=0, a=(), seqs=None):
        """A whole RUNBOOK: chooser header on line 2 + top; section A (sim, no stop table); the five real sequences; tail."""
        seqs = seqs or {}
        out = ["# RUNBOOK", *[""] * top, self.CHOOSER, "|---|---|---|", "| Fly in simulation | SIM | [A](#a) |", "",
               "## A · Fly in SIMULATION", "", *a, "```bash", self.TAKEOFF, "```", "", "```bash", self.START, "```", ""]
        for name in self.HEADS:
            out += seqs.get(name) or self.seq(name)
        return "\n".join(out + ["## D · POST-FLIGHT — pull & review the PX4 logs", "", "## Pocket reference", "", "### Sim launch variants", ""]) + "\n"

    def run_check(self, text):
        return C.check_runbook_procedure(text)

    def test_chooser_on_line_15_passes_on_16_fails(self):
        self.assertEqual(self.run_check(self.page(top=13)).status, "PASS")
        r = self.run_check(self.page(top=14))
        self.assertEqual(r.status, "FAIL"); self.assertTrue(any("chooser" in x and "16" in x for x in r.details), r.details)
        r = self.run_check(self.page().replace(self.CHOOSER, "| Session | Go to |"))
        self.assertEqual(r.status, "FAIL"); self.assertTrue(any("chooser" in x for x in r.details), r.details)

    def test_block_mixing_mocap_sh_and_ros2_fails(self):
        for laptop in ("cd ~/AirStack-starling-max2 && ./mocap.sh", "cd ~/AirStack-starling-max2/AirStack && ./airstack.sh up",
                       "~/QGroundControl-x86_64.AppImage"):
            r = self.run_check(self.page(a=["```bash", laptop, "ros2 topic list", "```", ""]))
            self.assertEqual(r.status, "FAIL", laptop)
            self.assertTrue(any("laptop" in x and "ros2" in x and ":9" in x for x in r.details), r.details)

    def test_connect_not_last_fails_last_passes(self):
        r = self.run_check(self.page(a=["```bash", "cd ~/AirStack-starling-max2/AirStack && ./airstack.sh connect robot", "tmux attach -t bringup", "```", ""]))
        self.assertEqual(r.status, "FAIL"); self.assertTrue(any("connect" in x and ":9" in x for x in r.details), r.details)
        ok = self.page(a=["```bash", "cd ~/AirStack-starling-max2/AirStack", "./airstack.sh connect robot   # a new shell opens", "```", ""])
        self.assertEqual(self.run_check(ok).status, "PASS")

    def test_takeoff_and_start_in_one_block_fails(self):
        a = ["```bash", self.TAKEOFF, "# then", self.START, "```", ""]
        r = self.run_check(self.page(a=a))
        self.assertEqual(r.status, "FAIL"); self.assertTrue(any("takeoff" in x and "start" in x for x in r.details), r.details)
        self.assertEqual(self.run_check(self.page(a=["```bash", self.LAND, self.LAND, "```", ""])).status, "PASS")    # the same call twice is one call

    def test_stop_table_gap_16_fails_15_passes(self):
        self.assertEqual(self.run_check(self.page(seqs={"B10": self.seq("B10", gap=15)})).status, "PASS")
        r = self.run_check(self.page(seqs={"B10": self.seq("B10", gap=16)}))
        self.assertEqual(r.status, "FAIL"); self.assertTrue(any("B10" in x and "16" in x for x in r.details), r.details)

    def test_real_sequence_without_stop_table_fails_section_A_needs_none(self):
        self.assertEqual(self.run_check(self.page()).status, "PASS")                    # section A takes off with no stop table
        r = self.run_check(self.page(seqs={"C9": self.seq("C9", stop=False)}))
        self.assertEqual(r.status, "FAIL"); self.assertTrue(any("C9" in x and "Stop table" in x for x in r.details), r.details)

    def test_openings_differing_only_in_names_ips_and_counts_pass(self):
        two = self.opening(drones=("drone_1", "drone_2"))
        seqs = {"B": self.seq("B", opening=self.opening(drones=("drone_1",), bodies=False)), "B9": self.seq("B9"),
                "B10": self.seq("B10", opening=two), "C": self.seq("C", opening=self.opening(drones=("drone_1",), bodies=False)),
                "C9": self.seq("C9", opening=two)}
        r = self.run_check(self.page(seqs=seqs))
        self.assertEqual(r.status, "PASS", r.details)
        self.assertEqual(C.normalise_opening(['ping -c2 10.40.2.11', 'ping -c2 10.40.2.10', '```bash',
                                              'cd ~/AirStack-starling-max2 && MOCAP_BODIES="drone_1 drone_2" ./mocap.sh',
                                              'x drones:=drone_1,drone_2 target_systems:=1,2', '**17 · Pane 3 · `drone_1` and `drone_2`**']),
                         ['ping -c2 IP', 'cd ~/AirStack-starling-max2 && ./mocap.sh', 'x drones:=drone_N', '**N · Pane 3 · `drone_N` and `drone_N`**'])

    def test_opening_word_change_fails_with_the_line(self):
        r = self.run_check(self.page(seqs={"C9": self.seq("C9", opening=self.opening(rate="about 30 Hz"))}))
        self.assertEqual(r.status, "FAIL")
        self.assertTrue(any("C9" in x and "about 30 Hz" in x and "a steady rate" in x for x in r.details), r.details)
        self.assertFalse(any(x.startswith(("B:", "B9:", "B10:", "C:")) for x in r.details), r.details)

    def test_unpaired_or_missing_markers_fail(self):
        unclosed = [x for x in self.opening() if x != "<!-- /shared-opening -->"]
        stray = ["<!-- /shared-opening -->"] + self.opening()
        for name, op, word in (("B10", unclosed, "never closed"), ("B9", stray, "closing marker"),
                               ("C", [x for x in self.opening() if "shared-opening" not in x], "no shared-opening")):
            r = self.run_check(self.page(seqs={name: self.seq(name, opening=op)}))
            self.assertEqual(r.status, "FAIL", name); self.assertTrue(any(x.startswith(name + ":") and word in x for x in r.details), r.details)

    def test_date_or_ledger_number_in_a_step_warns_not_in_world_line_table_row_or_not_flown_line(self):
        body = ["**5 · Pane 4 · check** as flown on 2026-11-13.", "Seen in [#41](record/LEDGER.md).",
                "| 2026-11-12 | a table row, [#34](record/LEDGER.md) |", "Not flown since 2026-11-12; not re-derived for #34; not set.",
                "Re-provision ([DRONE_SETUP.md](DRONE_SETUP.md#4--point-px4-at-the-laptop-uxrce-dds-provisioning) §4).", ""]
        r = self.run_check(self.page(seqs={"B9": self.seq("B9", body=body)}))
        self.assertEqual(r.status, "WARN", r.details)
        self.assertEqual(len(r.details), 2, r.details)
        self.assertTrue(r.details[0].startswith("B9:") and "2026-11-13" in r.details[0], r.details)
        self.assertTrue(r.details[1].startswith("B9:") and "#41" in r.details[1], r.details)

    def test_sequence_of_181_lines_warns_not_fails(self):
        base = len(self.seq("B9"))
        self.assertEqual(self.run_check(self.page(seqs={"B9": self.seq("B9", body=["text"] * (180 - base))})).status, "PASS")
        r = self.run_check(self.page(seqs={"B9": self.seq("B9", body=["text"] * (181 - base))}))
        self.assertEqual(r.status, "WARN"); self.assertTrue(any(x.startswith("B9:") and "181" in x for x in r.details), r.details)
        r = self.run_check(self.page(a=["text"] * 181))
        self.assertEqual(r.status, "WARN"); self.assertTrue(any(x.startswith("A:") for x in r.details), r.details)

    def test_registered_in_the_checker_run(self):
        out = subprocess.run([sys.executable, "-I", str(pathlib.Path(C.__file__)), "--json"], capture_output=True, text=True, cwd=self._root).stdout
        self.assertIn("runbook-procedure", [r["check"] for r in json.loads(out)["results"]])

    def test_shipped_runbook_has_no_fail(self):
        r = C.check_runbook_procedure()
        self.assertEqual(r.name, "runbook-procedure")
        self.assertNotEqual(r.status, "FAIL", r.details)
