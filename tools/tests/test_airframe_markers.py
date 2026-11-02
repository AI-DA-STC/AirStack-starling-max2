# tools/tests/test_airframe_markers.py — every sim-airframe line is labelled = real / SIM-ONLY and the label is true (CODING_STANDARD §4)
import pathlib, sys, unittest
TOOLS = pathlib.Path(__file__).resolve().parents[1]; REPO = TOOLS.parent
sys.path.insert(0, str(TOOLS / "lib"))
import airframe_params as A

REAL = "# Onboard parameters\n1\t1\tMC_ROLLRATE_P\t0.064\t9\n1\t1\tLNDMC_ROT_MAX\t3e+01\t9\n1\t1\tMC_YAW_P\t2.8\t9\n"
def check(*lines): return A.check_markers("\n".join(lines) + "\n", A.parse_real(REAL), {"CHG-0003"})

class Markers(unittest.TestCase):
    def test_the_repo_airframe_is_fully_marked_and_true(self):
        errs = A.check_markers((REPO / A.AIRFRAME).read_text(), A.parse_real((REPO / A.REAL_PARAMS).read_text()),
                               A.changes_ids((REPO / "docs/record/CHANGES.md").read_text()))
        self.assertEqual(errs, [])
    def test_all_48_lines_carry_a_marker(self):
        lines = A.parse_airframe((REPO / A.AIRFRAME).read_text())
        self.assertEqual(len(lines), 48); self.assertTrue(all(l.marker for l in lines), [l.name for l in lines if not l.marker])
    def test_real_values_parse_as_floats(self):
        self.assertEqual(A.parse_real(REAL)["LNDMC_ROT_MAX"], 30.0)
    def test_unmarked_line_fails(self):
        self.assertTrue(any("MC_YAW_P" in e and "no marker" in e for e in check("param set-default MC_YAW_P 2.8")))
    def test_equal_real_passes_and_differing_real_fails(self):
        self.assertEqual(check("param set-default MC_YAW_P 2.8   # = real"), [])
        self.assertTrue(any("MC_YAW_P" in e and "2.8" in e for e in check("param set-default MC_YAW_P 2.0 # = real")))
    def test_sim_only_with_the_wrong_real_value_fails(self):                        # Review Focus 3
        self.assertEqual(check("param set-default LNDMC_ROT_MAX 300.0 # SIM-ONLY (real 30) CHG-0003"), [])
        e = check("param set-default LNDMC_ROT_MAX 300.0 # SIM-ONLY (real 20) CHG-0003")
        self.assertTrue(any("LNDMC_ROT_MAX" in x and "20" in x and "30" in x for x in e), e)
    def test_sim_only_on_an_equal_value_must_say_real(self):
        self.assertTrue(any("= real" in e for e in check("param set-default MC_YAW_P 2.8 # SIM-ONLY (real 2.8) CHG-0003")))
    def test_no_real_value_only_for_names_the_drone_lacks(self):
        self.assertEqual(check("param set-default PWM_MAIN_FUNC1 101 # SIM-ONLY (no real value) CHG-0003"), [])
        self.assertTrue(check("param set-default MC_YAW_P 9 # SIM-ONLY (no real value) CHG-0003"))
        self.assertTrue(check("param set-default PWM_MAIN_FUNC1 101 # = real"))
    def test_unknown_change_id_fails(self):
        self.assertTrue(any("CHG-0999" in e for e in check("param set-default LNDMC_ROT_MAX 300.0 # SIM-ONLY (real 30) CHG-0999")))
    def test_marker_must_end_the_line(self):
        self.assertTrue(check("param set-default MC_YAW_P 2.8 # = real, as on the drone"))
