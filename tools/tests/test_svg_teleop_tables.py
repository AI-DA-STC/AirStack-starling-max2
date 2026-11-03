# tools/tests/test_svg_teleop_tables.py — the Foxglove strip's generated tables and fixtures follow keymap.py (NEAR-789, sim)
import json, pathlib, shutil, subprocess, sys, tempfile, unittest
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "teleop"))
import keymap as K

GEN = ROOT / "teleop/foxglove/gen_keymap.py"
EXT = ROOT / "teleop/foxglove/svg-teleop/dist/extension.js"
FIX = ROOT / "teleop/foxglove/svg-teleop/test/fixtures.json"


def visible_strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from visible_strings(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from visible_strings(v)


class Tables(unittest.TestCase):
    def test_generated_files_match_keymap_py(self):
        r = subprocess.run([sys.executable, str(GEN), "--check"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_removed_aliases_stay_removed(self):
        self.assertFalse({"q", "e", "shift_l", "shift_r", "control_l", "control_r"} & set(K.export_tables()["keys"]))

    def test_a_changed_word_fails_the_check(self):
        with tempfile.TemporaryDirectory() as d:
            ext = pathlib.Path(d) / "extension.js"
            shutil.copy(EXT, ext)
            ext.write_text(ext.read_text(encoding="utf-8").replace("pitch: forward", "pitch: ahead"), encoding="utf-8")
            r = subprocess.run([sys.executable, str(GEN), "--check", "--extension", str(ext), "--fixtures", str(FIX)],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)

    def test_regeneration_keeps_code_outside_the_block(self):
        with tempfile.TemporaryDirectory() as d:
            ext = pathlib.Path(d) / "extension.js"
            ext.write_text(EXT.read_text(encoding="utf-8") + "// later task code\n", encoding="utf-8")
            fx = pathlib.Path(d) / "fixtures.json"
            subprocess.run([sys.executable, str(GEN), "--extension", str(ext), "--fixtures", str(fx)], check=True,
                           capture_output=True)
            self.assertIn("// later task code", ext.read_text(encoding="utf-8"))
            self.assertEqual(fx.read_text(encoding="utf-8"), FIX.read_text(encoding="utf-8"))

    def test_fixtures_cover_all_header_states(self):
        bold = {c["header"][0] for c in json.loads(FIX.read_text(encoding="utf-8"))["status"]}
        for name, line in K.export_tables()["lines"].items():
            self.assertIn(line[0], bold, name)
        self.assertGreaterEqual(len(bold), 6)

    def test_fixtures_cover_profiles_diagonals_and_space(self):
        axes = json.loads(FIX.read_text(encoding="utf-8"))["axes"]
        self.assertEqual({c["profile"] for c in axes}, set(K.PROFILES))
        self.assertTrue(any(set(c["held"]) >= {"up", "right"} for c in axes))
        self.assertTrue(any(c.get("space") and c["held"] and not any(c["axes"]) for c in axes))

    def test_fixtures_include_nan_and_garbled_lines(self):
        lines = {c["line"] for c in json.loads(FIX.read_text(encoding="utf-8"))["status"]}
        self.assertIn(None, lines)
        self.assertTrue(any(l and "nan" in l for l in lines))
        self.assertIn("garbage", lines)

    def test_no_jargon_in_visible_strings(self):
        t = K.export_tables()
        for s in visible_strings([t["lines"], t["footer"], t["words"]]):
            for w in ("BODY", "WORLD", "CMU"):
                self.assertNotIn(w, s)

    def test_dump_json_prints_the_tables(self):
        r = subprocess.run([sys.executable, str(ROOT / "teleop/keymap.py"), "--dump-json"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout), K.export_tables())

    def test_words_keys_are_stick_colon_sign(self):
        self.assertIn("forward:1", K.export_tables()["words"])
        self.assertIn("forward:-1", K.export_tables()["words"])

    def test_skeleton_registers_the_panel(self):
        src = EXT.read_text(encoding="utf-8")
        self.assertIn('name: "SVG Teleop"', src)
        self.assertIn("module.exports", src)
        pkg = json.loads((EXT.parents[1] / "package.json").read_text())
        self.assertEqual((pkg["publisher"], pkg["name"], pkg["displayName"], pkg["version"], pkg["main"]),
                         ("nearlab", "svg-teleop", "SVG Teleop", "1.0.0", "./dist/extension.js"))


if __name__ == "__main__":
    unittest.main()
