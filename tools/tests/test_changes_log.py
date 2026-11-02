# tools/tests/test_changes_log.py
"""The one change-log line format (owner rule 2026-11-02): `time · name · old → new · who · readback v`. Sim-only tooling."""
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib"))
import changes_log as C  # noqa: E402


class FormatChange(unittest.TestCase):
    def test_line_has_the_five_fields_in_order(self):
        s = C.format_change("2026-11-02T14:03:05+08:00", "MC_YAW_P", 2.8, 2.0, "yaw_step fly.sh sweep set 1", readback=2.0)
        self.assertEqual(s, "2026-11-02T14:03:05+08:00 · MC_YAW_P · 2.8 → 2 · yaw_step fly.sh sweep set 1 · readback 2")

    def test_unix_time_becomes_iso_with_offset(self):
        s = C.format_change(1_800_000_000.0, "MC_YAW_P", 2.8, 2.0, "x")
        self.assertRegex(s.split(" · ")[0], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d[+-]\d\d:\d\d$")

    def test_missing_values_are_explicit(self):
        s = C.format_change("t", "MC_YAW_P", None, 2.0, "x")
        self.assertIn("? → 2", s)
        self.assertTrue(s.endswith("readback n/a"), s)

    def test_one_line_even_with_a_newline_in_who(self):
        self.assertNotIn("\n", C.format_change("t", "P", 1, 2, "a\nb", readback=2))

    def test_parse_round_trips(self):
        s = C.format_change("2026-11-02T14:03:05+08:00", "MC_YAWRATE_D", 0.0, 0.002, "w", readback=0.002)
        d = C.parse_change(s)
        self.assertEqual((d["time"], d["name"], d["old"], d["new"], d["who"], d["readback"]),
                         ("2026-11-02T14:03:05+08:00", "MC_YAWRATE_D", 0.0, 0.002, "w", 0.002))
        self.assertIsNone(C.parse_change("not a change line"))
        self.assertIsNone(C.parse_change(C.format_change("t", "P", None, 2, "w"))["readback"])

    def test_append_writes_one_line_per_change(self):
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d) / "changes.log"
            C.append_change(p, "t1", "MC_YAW_P", 2.8, 2.0, "w", readback=2.0)
            C.append_change(p, "t2", "MC_YAW_P", 2.0, 1.4, "w", readback=1.4)
            lines = p.read_text().splitlines()
        self.assertEqual(len(lines), 2)
        self.assertEqual([C.parse_change(l)["new"] for l in lines], [2.0, 1.4])


if __name__ == "__main__":
    unittest.main()
