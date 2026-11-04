# tools/tests/test_sync_layout.py — sync_layout.py puts the shipped Foxglove layout into Studio's store as `working` (sim only)
import contextlib, io, json, os, pathlib, subprocess, sys, tempfile, unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "tools/teleop/foxglove"))
import sync_layout as S

UP = (ROOT / "localisation/scripts/slam_up.sh").read_text()


def shipped(tag="v1"):
    return {"configById": {"3D!cuvslam": {"cameraState": {"d": 1}, "tag": tag}}, "layout": "L"}


def layout(lid, name="teleop-cuvslam", base=None, work=None, viewed=None):
    d = {"id": lid, "name": name, "permission": "CREATOR_WRITE",
         "baseline": {"data": base or shipped("old"), "savedAt": "2026-01-01T00:00:00.000Z"},
         "syncInfo": {"status": "tracked", "lastRemoteSavedAt": "x"}}
    if work is not None:
        d["working"] = {"data": work, "savedAt": "2026-01-02T00:00:00.000Z"}
    if viewed:
        d["lastViewedAt"] = viewed
    return d


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        t = pathlib.Path(self.tmp.name)
        self.store = t / "store"; self.dir = self.store / "layouts-remote-x"; self.dir.mkdir(parents=True)
        self.ship = t / "ship.json"; self.ship.write_text(json.dumps(shipped()))
        self.marker = t / "out" / "marker"; self.bk = t / "out" / "backups"
        self.marker.parent.mkdir()

    def put(self, lid, **kw):
        p = self.dir / lid; p.write_text(json.dumps(layout(lid, **kw))); return p

    def run_sync(self, extra=None):
        out, err = io.StringIO(), io.StringIO()
        argv = ["--store", str(self.store), "--layout", str(self.ship), "--name", "teleop-cuvslam",
                "--marker", str(self.marker), "--backup-dir", str(self.bk)] + (extra or [])
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = S.main(argv)
        return rc, out.getvalue(), err.getvalue()

    def load(self, p):
        return json.loads(p.read_text())

    def tree(self):
        return sorted(str(p.relative_to(self.store)) for p in self.store.rglob("*"))


class Sync(Base):
    def test_first_run_updates_working_only(self):
        p = self.put("lay_a"); before = self.load(p)
        rc, out, _ = self.run_sync()
        self.assertEqual((rc, out), (0, "LAYOUT_ID=lay_a\n"))
        after = self.load(p)
        for k in ("baseline", "syncInfo", "id", "name", "permission"):
            self.assertEqual(after[k], before[k])
        self.assertEqual(after["working"]["data"]["configById"]["3D!cuvslam"]["tag"], "v1")
        self.assertRegex(after["working"]["savedAt"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z$")
        self.assertTrue(self.marker.exists())
        bks = list(self.bk.iterdir()); self.assertEqual(len(bks), 1)
        self.assertTrue(bks[0].name.startswith("lay_a.")); self.assertEqual(json.loads(bks[0].read_text()), before)
        self.assertNotIn(str(self.store), str(bks[0]))

    def test_baseline_bytes_equal(self):
        p = self.put("lay_a"); raw = json.loads(p.read_text())
        self.run_sync()
        self.assertEqual(json.dumps(self.load(p)["baseline"], sort_keys=True), json.dumps(raw["baseline"], sort_keys=True))

    def test_second_run_changes_nothing_even_after_owner_edit(self):
        p = self.put("lay_a"); self.run_sync()
        d = self.load(p); d["working"]["data"]["configById"]["3D!cuvslam"]["tag"] = "mine"
        p.write_text(json.dumps(d)); os.utime(p, (1000, 1000))
        content = p.read_text()
        rc, out, _ = self.run_sync()
        self.assertEqual((rc, out), (0, "LAYOUT_ID=lay_a\n"))
        self.assertEqual(p.read_text(), content); self.assertEqual(p.stat().st_mtime, 1000)
        self.assertEqual(len(list(self.bk.iterdir())), 1)

    def test_changed_shipped_file_updates_again(self):
        p = self.put("lay_a"); self.run_sync()
        self.ship.write_text(json.dumps(shipped("v2")))
        rc, out, _ = self.run_sync()
        self.assertEqual(out, "LAYOUT_ID=lay_a\n")
        self.assertEqual(self.load(p)["working"]["data"]["configById"]["3D!cuvslam"]["tag"], "v2")

    def test_marker_for_another_layout_id_syncs_again(self):
        self.put("lay_a"); self.run_sync()
        (self.dir / "lay_a").rename(self.dir / "lay_b")
        d = self.load(self.dir / "lay_b"); d["id"] = "lay_b"; (self.dir / "lay_b").write_text(json.dumps(d))
        self.run_sync()
        self.assertEqual(self.load(self.dir / "lay_b")["working"]["data"]["configById"]["3D!cuvslam"]["tag"], "v1")
        self.assertEqual(len(list(self.bk.iterdir())), 2)

    def test_mode_preserved(self):
        p = self.put("lay_a"); os.chmod(p, 0o644)
        self.run_sync()
        self.assertEqual(p.stat().st_mode & 0o777, 0o644)

    def _status(self, status, working):
        a = self.put("lay_a", work=shipped("w") if working else None)
        d = self.load(a); d["syncInfo"]["status"] = status; a.write_text(json.dumps(d)); return a

    def test_locally_deleted_skipped(self):
        a = self._status("locally-deleted", True); raw = a.read_text()
        rc, out, err = self.run_sync()
        self.assertEqual((rc, out), (0, "")); self.assertEqual(a.read_text(), raw)

    def test_remotely_deleted_without_working_skipped(self):
        a = self._status("remotely-deleted", False)
        self.assertEqual(self.run_sync()[1], "")

    def test_remotely_deleted_with_working_used(self):
        self._status("remotely-deleted", True)
        self.assertEqual(self.run_sync()[1], "LAYOUT_ID=lay_a\n")

    def test_tombstone_loses_to_live_duplicate(self):
        self._status("locally-deleted", True)
        b = self.put("lay_b", viewed="2020-01-01T00:00:00.000Z")
        self.assertEqual(self.run_sync()[1], "LAYOUT_ID=lay_b\n")

    def test_camera_state_from_working(self):
        w = shipped("mine"); w["configById"]["3D!cuvslam"]["cameraState"] = {"d": 99}
        b = shipped("b"); b["configById"]["3D!cuvslam"]["cameraState"] = {"d": 5}
        p = self.put("lay_a", base=b, work=w); self.run_sync()
        self.assertEqual(self.load(p)["working"]["data"]["configById"]["3D!cuvslam"]["cameraState"], {"d": 99})

    def test_camera_state_from_baseline(self):
        b = shipped("b"); b["configById"]["3D!cuvslam"]["cameraState"] = {"d": 5}
        p = self.put("lay_a", base=b); self.run_sync()
        self.assertEqual(self.load(p)["working"]["data"]["configById"]["3D!cuvslam"]["cameraState"], {"d": 5})

    def test_no_3d_panel_in_old_data_keeps_shipped_view(self):
        p = self.put("lay_a", base={"configById": {}}); self.run_sync()
        self.assertEqual(self.load(p)["working"]["data"]["configById"]["3D!cuvslam"]["cameraState"], {"d": 1})

    def test_newest_viewed_wins(self):
        a = self.put("lay_a", viewed="2026-11-01T00:00:00.000Z"); b = self.put("lay_b", viewed="2026-11-03T00:00:00.000Z")
        ra = a.read_text()
        rc, out, _ = self.run_sync()
        self.assertEqual(out, "LAYOUT_ID=lay_b\n"); self.assertEqual(a.read_text(), ra)
        self.assertIn("working", self.load(b))

    def test_other_names_untouched(self):
        o = self.put("lay_o"); d = self.load(o); d["name"] = "other"; o.write_text(json.dumps(d)); raw = o.read_text()
        self.put("lay_a"); self.run_sync()
        self.assertEqual(o.read_text(), raw)

    def test_matches_in_layouts_local(self):
        loc = self.store / "layouts-local"; loc.mkdir()
        (loc / "lay_l").write_text(json.dumps(layout("lay_l")))
        rc, out, _ = self.run_sync()
        self.assertEqual(out, "LAYOUT_ID=lay_l\n")

    def test_no_match(self):
        o = self.put("lay_o"); d = self.load(o); d["name"] = "other"; o.write_text(json.dumps(d))
        before = self.tree()
        rc, out, err = self.run_sync()
        self.assertEqual((rc, out), (0, "")); self.assertIn("Import from file", err)
        self.assertEqual(self.tree(), before); self.assertFalse(self.marker.exists()); self.assertFalse(self.bk.exists())

    def test_malformed_and_directory_skipped(self):
        bad = self.dir / "lay_bad"; bad.write_text("{nope"); (self.dir / "subdir").mkdir()
        self.put("lay_a")
        rc, out, _ = self.run_sync()
        self.assertEqual((rc, out), (0, "LAYOUT_ID=lay_a\n")); self.assertEqual(bad.read_text(), "{nope")

    def test_missing_store(self):
        self.store = self.store / "nope"
        rc, out, _ = self.run_sync()
        self.assertEqual((rc, out), (0, ""))

    def test_missing_shipped_file(self):
        self.put("lay_a"); self.ship.unlink()
        rc, out, _ = self.run_sync()
        self.assertEqual(rc, 0)

    def test_failed_replace_leaves_original(self):
        p = self.put("lay_a"); raw = p.read_text()
        with mock.patch.object(S.os, "replace", side_effect=OSError("boom")):
            rc, out, err = self.run_sync()
        self.assertEqual(rc, 0); self.assertEqual(p.read_text(), raw); self.assertFalse(self.marker.exists())
        self.assertNotIn("working", self.load(p))

    def test_read_only_target_dir(self):
        if os.geteuid() == 0:
            self.skipTest("root ignores modes")
        p = self.put("lay_a"); raw = p.read_text(); os.chmod(self.store, 0o555)
        self.addCleanup(os.chmod, self.store, 0o755)
        rc, out, _ = self.run_sync()
        self.assertEqual(rc, 0); self.assertEqual(p.read_text(), raw)

    def test_only_expected_files_in_layout_dirs(self):
        self.put("lay_a"); self.run_sync(); self.ship.write_text(json.dumps(shipped("v2"))); self.run_sync()
        self.assertEqual(sorted(x.name for x in self.dir.iterdir()), ["lay_a"])
        self.assertEqual(sorted(x.name for x in self.store.iterdir()), ["layouts-remote-x"])


class SlamUpSource(unittest.TestCase):
    def branch(self):
        i = UP.index('if ! ex \'pgrep -f "[f]oxglove-studio'); return UP[i:UP.index("\nelse echo \"Foxglove Studio (SLAM instance) already open", i)]

    def test_sync_only_in_not_running_branch_before_studio(self):
        self.assertEqual(UP.count("/teleop-foxglove/sync_layout.py"), 1)
        b = self.branch()
        self.assertLess(b.index("sync_layout.py"), b.index('exd "foxglove-studio'))

    def test_arguments(self):
        b = self.branch()
        for a in ("--store /exploration/foxglove/studio-data/studio-datastores", "--layout /teleop-foxglove/teleop-cuvslam.json",
                  "--marker /exploration/results/teleop_layout.marker", "--backup-dir /exploration/results/layout_backups",
                  "/teleop-foxglove/sync_layout.py"):
            self.assertIn(a, b)

    def test_id_reaches_deep_link_and_is_validated(self):
        b = self.branch()
        self.assertIn("&layoutId=", b); self.assertIn("^[A-Za-z0-9_-]+$", b)
        self.assertIn("Foxglove layout: teleop-cuvslam", b)
        self.assertIn("results/sync_layout.log", b); self.assertIn("LAYOUT_ID=", b)
        self.assertIn("panel and the layout", UP)

    def snippet(self):
        b = self.branch().splitlines()
        a = next(i for i, l in enumerate(b) if l.lstrip().startswith("LAYOUT_ID=$(")); z = next(i for i, l in enumerate(b) if "LAYOUT_ARG=" in l and "echo" in l)
        return "\n".join(b[a:z + 1])

    def run_snippet(self, ex_body):
        script = "set -euo pipefail\nex() { %s; }\n%s\necho \"AFTER id=[$LAYOUT_ID] arg=[$LAYOUT_ARG]\"\n" % (ex_body, self.snippet())
        return subprocess.run(["bash", "-c", script], capture_output=True, text=True)

    def test_sync_cannot_abort_script(self):
        r = self.run_snippet("echo boom; return 3")
        self.assertEqual(r.returncode, 0); self.assertIn("AFTER id=[] arg=[]", r.stdout)

    def test_only_tagged_line_gives_an_id(self):
        r = self.run_snippet("echo ready")
        self.assertIn("AFTER id=[] arg=[]", r.stdout)
        r = self.run_snippet("echo noise; echo LAYOUT_ID=lay_x; echo trailing")
        self.assertIn("AFTER id=[lay_x] arg=[&layoutId=lay_x]", r.stdout)
        r = self.run_snippet("echo 'LAYOUT_ID=bad id;x'")
        self.assertIn("AFTER id=[] arg=[]", r.stdout)


if __name__ == "__main__":
    unittest.main()
