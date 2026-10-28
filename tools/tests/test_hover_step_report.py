# tools/tests/test_hover_step_report.py
import json, pathlib, shutil, sys, tempfile, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import hover_step_report as R
import hover_step_analysis as A
FX = pathlib.Path(__file__).resolve().parent / "fixtures" / "run1"

def make_run(tmp, **overrides):
    """Fixture run dir: real #17 artefacts + a fresh bag_analysis.json from the Task 3 module + run_meta + clock + armed."""
    out = pathlib.Path(tmp) / "sim_hover_step_runX"; out.mkdir()
    for f in FX.iterdir():
        if f.name != "bag_analysis.json": shutil.copy(f, out / f.name)
    odom, cmd, state = (A.load_xyz_csv(out / "drone_1_odom.csv"), A.load_xyz_csv(out / "drone_1_cmd.csv"), A.load_state_csv(out / "drone_1_state.csv"))
    (out / "bag_analysis.json").write_text(json.dumps(A.analyse(odom, cmd, state, px4_arm_times=A.load_px4_arm_times(out / "px4_arm_times.txt"))))
    (out / "run_meta.txt").write_text("head=0123456789abcdef\nhead_short=0123456\ndirty_tools=0\nstarted=2026-10-28T15:39:01+08:00\ntz=+08\nrun=sim_hover_step_runX\n")
    (out / "clock_check.txt").write_text("clock_rc=1\n")
    (out / "armed_post.txt").write_text("drone_1 armed: false\ndrone_2 armed: false\ndrone_3 armed: false\n")
    (out / "isaac_evidence.txt").write_text("model_line=3 starling_cfg=3 autostart=3 unknown_model=0 cooking=0 ready=3\n")
    heavy = pathlib.Path(tmp) / "heavy"; (heavy / "hover_step_20261028_074116").mkdir(parents=True)
    (heavy / "hover_step_20261028_074116" / "metadata.yaml").write_text("rosbag2_bagfile_information: {}\n")
    for k, v in overrides.items():
        if v is None: (out / k).unlink(missing_ok=True)
        else: (out / k).write_text(v)
    return out, heavy

def verdict_of(rows, prefix):
    return next(r.verdict for r in rows if r.check.startswith(prefix))

class Rows(unittest.TestCase):
    def test_clean_fixture_is_pass(self):
        with tempfile.TemporaryDirectory() as d:
            out, heavy = make_run(d)
            rows, ctx = R.build_rows(out, heavy)
            self.assertEqual(R.overall_verdict(rows), "PASS", [(r.check, r.verdict, r.measured) for r in rows if r.verdict not in ("PASS", "info")])
            self.assertTrue(all(r.verdict == "info" for r in rows if not r.gate))
            self.assertNotIn("PASS", [r.verdict for r in rows if not r.gate])

    def test_vehicle_time_is_gated_with_wall_in_brackets(self):
        with tempfile.TemporaryDirectory() as d:
            out, heavy = make_run(d)
            rows, _ = R.build_rows(out, heavy)
            r = next(r for r in rows if r.check.startswith("x step") and "settle ±0.1" in r.check)
            self.assertRegex(r.measured, r"^2\.4\d s \[1\.8\d s wall\]")

    def test_starling_cfg_zero_is_unverified(self):            # Review Focus 3
        with tempfile.TemporaryDirectory() as d:
            out, heavy = make_run(d, **{"isaac_evidence.txt": "model_line=0 starling_cfg=0 autostart=3 unknown_model=0 cooking=0 ready=3\n"})
            rows, _ = R.build_rows(out, heavy)
            self.assertEqual(verdict_of(rows, "Isaac launch: Starling2MaxConfig"), "UNVERIFIED")
            self.assertEqual(R.overall_verdict(rows), "INCOMPLETE")

    def test_armed_post_garbage_is_unverified(self):           # Review Focus 4
        with tempfile.TemporaryDirectory() as d:
            out, heavy = make_run(d, **{"armed_post.txt": "drone_1 armed: groups: cannot find name for group ID 992\n" * 3})
            rows, _ = R.build_rows(out, heavy)
            self.assertEqual(verdict_of(rows, "post-flight armed=false x3"), "UNVERIFIED")

    def test_armed_post_two_values_is_unverified(self):
        with tempfile.TemporaryDirectory() as d:
            out, heavy = make_run(d, **{"armed_post.txt": "drone_1 armed: false\ndrone_2 armed: false\n"})
            rows, _ = R.build_rows(out, heavy)
            self.assertEqual(verdict_of(rows, "post-flight armed=false x3"), "UNVERIFIED")

    def test_armed_true_fails(self):
        with tempfile.TemporaryDirectory() as d:
            out, heavy = make_run(d, **{"armed_post.txt": "drone_1 armed: true\ndrone_2 armed: false\ndrone_3 armed: false\n"})
            rows, _ = R.build_rows(out, heavy)
            self.assertEqual(verdict_of(rows, "post-flight armed=false x3"), "FAIL")

    def test_thrust_parser_fail_closed(self):
        self.assertIsNone(R.parse_thrust_line("--- hover thrust samples ---\nulog thrust_setpoint median(mid-third) 0.001\n"))
        self.assertIsNone(R.parse_thrust_line("--- hover thrust samples ---\n0.15 0.15 0.15\n"))
        self.assertEqual(len(R.parse_thrust_line((FX / "test_stdout.log").read_text())), 10)
        with tempfile.TemporaryDirectory() as d:
            out, heavy = make_run(d, **{"test_stdout.log": (FX / "test_stdout.log").read_text().replace("--- hover thrust samples", "--- nothing")})
            rows, _ = R.build_rows(out, heavy)
            self.assertEqual(verdict_of(rows, "hover thrust setpoint"), "UNVERIFIED")

    def test_missing_px4_times_is_unverified(self):           # Review Focus 5
        with tempfile.TemporaryDirectory() as d:
            out, heavy = make_run(d)
            odom, cmd, state = (A.load_xyz_csv(out / "drone_1_odom.csv"), A.load_xyz_csv(out / "drone_1_cmd.csv"), A.load_state_csv(out / "drone_1_state.csv"))
            (out / "bag_analysis.json").write_text(json.dumps(A.analyse(odom, cmd, state, px4_arm_times=None)))
            rows, _ = R.build_rows(out, heavy)
            self.assertEqual(verdict_of(rows, "time scale"), "UNVERIFIED")
            self.assertEqual(R.overall_verdict(rows), "INCOMPLETE")

    def test_axis_mismatch_fails_step_row(self):               # Review Focus 2
        with tempfile.TemporaryDirectory() as d:
            out, heavy = make_run(d)
            j = json.loads((out / "bag_analysis.json").read_text()); j["steps"]["x"]["any_axis_mismatch"] = True
            (out / "bag_analysis.json").write_text(json.dumps(j))
            rows, _ = R.build_rows(out, heavy)
            self.assertEqual(verdict_of(rows, "x step: commanded axis moved most"), "FAIL")

    def test_ringing_gate_is_zero_reentries(self):
        with tempfile.TemporaryDirectory() as d:
            out, heavy = make_run(d)
            j = json.loads((out / "bag_analysis.json").read_text()); j["steps"]["z"]["reentries_0p1_max"] = 1
            (out / "bag_analysis.json").write_text(json.dumps(j))
            rows, _ = R.build_rows(out, heavy)
            self.assertEqual(verdict_of(rows, "z step: ringing"), "FAIL")

    def test_missing_bag_and_ulogs_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            out, heavy = make_run(d, **{"ulog_sysid_map.txt": "3 /tmp/a.ulg 1\n4 /tmp/b.ulg 1\n"})
            rows, _ = R.build_rows(out, pathlib.Path(d) / "nowhere")
            self.assertEqual(verdict_of(rows, "rosbag"), "UNVERIFIED")
            self.assertEqual(verdict_of(rows, "PX4 ulogs"), "FAIL")

class VerdictLog(unittest.TestCase):
    def test_history_row_and_append(self):
        with tempfile.TemporaryDirectory() as d:
            out, heavy = make_run(d, **{"verdicts.log": "2026-10-28T15:45:58+08:00 head=76cd405 verdict=FAIL fail=3 unverified=0\n"})
            rec = pathlib.Path(d) / "rec.md"
            rc = R.main([str(out), "--heavy", str(heavy), "--record", str(rec)])
            self.assertEqual(rc, 0)
            lines = (out / "verdicts.log").read_text().splitlines()
            self.assertEqual(len(lines), 2); self.assertIn("verdict=PASS", lines[1])
            md = rec.read_text()
            self.assertIn("verdict=FAIL fail=3", md)            # the earlier generation is visible in the record
            self.assertIn("UTC (container clock)", md); self.assertIn("+08", md)
            self.assertIn("tools/README.md", md); self.assertNotIn("MILESTONES", md)

    def test_exit_codes(self):
        with tempfile.TemporaryDirectory() as d:
            out, heavy = make_run(d, **{"isaac_evidence.txt": "starling_cfg=0 autostart=3 unknown_model=0 cooking=0 ready=3\n"})
            self.assertEqual(R.main([str(out), "--heavy", str(heavy), "--record", str(pathlib.Path(d) / "r.md"), "--no-verdict-log"]), 2)

class LedgerNumber(unittest.TestCase):
    def test_ledger_option_numbers_the_draft_row(self):
        with tempfile.TemporaryDirectory() as d:
            out, heavy = make_run(d)
            rec = pathlib.Path(d) / "rec.md"
            self.assertEqual(R.main([str(out), "--heavy", str(heavy), "--record", str(rec), "--no-verdict-log", "--ledger", "19", "--issue", "NEAR-786"]), 0)
            md = rec.read_text()
            self.assertIn("## Ledger row draft (docs/record/LEDGER.md table 1, #19, NEAR-786)", md)
            line = next(l for l in md.splitlines() if l.startswith("| 19 |"))
            self.assertRegex(line, r"^\| 19 \| \d{4}-\d\d-\d\d \| SIM \| Hover \+ 1 m steps, 1 per axis, PX4 vehicle time: PASS — x 0\.\d{3} m / \d\.\d\d s, z 0\.\d{3} m / \d\.\d\d s, thrust 0\.\d{3}, scale 1\.\d{3} \| \[sim_hover_step_runX_record\.md\]\(sim_hover_step_runX_record\.md\) \| NEAR-786 \|$")
            self.assertEqual(line.count("|"), 7)                 # one line, six cells
            self.assertNotIn("| 18 |", md)

    def test_no_ledger_or_issue_leaves_placeholders(self):
        with tempfile.TemporaryDirectory() as d:
            out, heavy = make_run(d)
            rec = pathlib.Path(d) / "rec.md"
            R.main([str(out), "--heavy", str(heavy), "--record", str(rec), "--no-verdict-log"])
            md = rec.read_text()
            self.assertIn("## Ledger row draft (docs/record/LEDGER.md table 1, next free number, issue ?)", md)
            self.assertTrue(any(l.startswith("| ? |") and l.endswith("| ? |") for l in md.splitlines()))

    def test_issue_option_rejects_malformed_id(self):           # Review Focus 4
        with tempfile.TemporaryDirectory() as d:
            out, heavy = make_run(d)
            for bad in ("786", "near-786", "NEAR-786x"):
                with self.assertRaises(SystemExit):
                    R.main([str(out), "--heavy", str(heavy), "--record", str(pathlib.Path(d) / "r.md"), "--no-verdict-log", "--issue", bad])
