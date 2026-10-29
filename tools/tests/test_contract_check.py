# tools/tests/test_contract_check.py
import json, pathlib, shutil, sys, tempfile, unittest
TOOLS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS / "lib")); sys.path.insert(0, str(TOOLS / "live"))
import contract_check as C
CROSSING = TOOLS / "sim_tests" / "crossing"

class ContractCheck(unittest.TestCase):
    def test_repo_test_dirs_pass(self):
        self.assertEqual(C.main([]), 0)
    def test_missing_gates_file_fails_with_name(self):
        with tempfile.TemporaryDirectory() as d:
            shutil.copytree(CROSSING, pathlib.Path(d) / "x"); (pathlib.Path(d) / "x" / "gates.py").unlink()
            probs = C.check(pathlib.Path(d) / "x"); self.assertTrue(any("gates.py" in p for p in probs))
    def test_stale_layout_fails(self):
        with tempfile.TemporaryDirectory() as d:
            td = pathlib.Path(d) / "x"; shutil.copytree(CROSSING, td); p = td / "plots.json"; j = json.loads(p.read_text()); j["plots"][0]["title"] = "changed"; p.write_text(json.dumps(j))
            self.assertTrue(any("stale" in m for m in C.check(td)))
