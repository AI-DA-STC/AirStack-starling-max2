# tools/tests/test_changes.py — change-logging standard: path map, pre-commit rule, git-log audit (docs/CODING_STANDARD.md)
import os, pathlib, shutil, subprocess, sys, tempfile, unittest
from unittest import mock
TOOLS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS / "docs_check"))
import changes as CH


def clean_env(**extra):
    e = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}     # a hook's GIT_DIR / GIT_INDEX_FILE must not reach the fixtures
    e.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1", GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t",
             GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
    e.update(extra)
    return e


def git(root, *args, check=True):
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, env=clean_env(), check=check)


HEAD_MD = "RECORD\n\n| ID | Date | Scope | What | Commit |\n|---|---|---|---|---|\n"
LEDGER = "| # | Date | SIM/REAL | Result | Evidence | NEAR |\n|---|---|---|---|---|---|\n| 3 | 2026-10-19 | SIM | r | e | n |\n"
def row(n, commit="this", what="x"): return f"| CHG-{n:04d} | 2026-11-02 | sim-only | {what} | {commit} |\n"
def block(n, verified="unit test", drop=None):
    lines = [f"Change: CHG-{n:04d}", "What: a -> b", "Scope: sim-only", "Why: w", "Could affect: c", "Watch for: s",
             f"Verified by: {verified}", "Revert: git revert"]
    return "\n".join(l for l in lines if not (drop and l.startswith(drop))) + "\n"


def make_repo(tmp, standard=True):
    root = pathlib.Path(tmp); git(root, "init", "-q", "-b", "main")
    (root / "docs/record").mkdir(parents=True); (root / "docs/record/LEDGER.md").write_text(LEDGER)
    paths = ["docs/record/LEDGER.md"]
    if standard:
        (root / "docs/CODING_STANDARD.md").write_text("KNOW\n"); (root / "docs/record/CHANGES.md").write_text(HEAD_MD + row(1))
        paths += ["docs/CODING_STANDARD.md", "docs/record/CHANGES.md"]
    git(root, "add", *paths); git(root, "commit", "-q", "--no-verify", "-m", "start", "-m", block(1) if standard else "x")
    return root


def commit(root, files, msg, body=""):
    for p, text in files.items():
        f = root / p; f.parent.mkdir(parents=True, exist_ok=True); f.write_text(text)
    git(root, "add", *files); git(root, "commit", "-q", "--no-verify", "-m", msg, *(["-m", body] if body else []))
    return git(root, "rev-parse", "HEAD").stdout.strip()


class PathMap(unittest.TestCase):
    CASES = {"AirStack/robot/ros_ws/src/svg_ground_control/svg_ground_control/swarm_commander.py": True,
             "AirStack/simulation/isaac-sim/px4/airframes/10090_pegasus_starling2max": True,
             "AirStack/robot/ros_ws/src/svg_ground_control/config/cbf_sim.yaml": True,
             "AirStack/robot/ros_ws/src/svg_ground_control/test/test_sim_teleop_release.py": False,
             "AirStack/docs/index.md": False, "patches/0007-mavros-interface-sim-velocity-room-frame.patch": True,
             "starling_1_indoor_params.params": True, "mocap.sh": True, "mocap/motion_capture.yaml": True,
             "tools/sim.sh": True, "tools/sim_hover_step_run.sh": True, "tools/hover_step_report.py": True,
             "tools/lib/report.py": True, "tools/live/metrics_core.py": True, "tools/teleop/keymap.py": True,
             "tools/sim_tests/crossing/gates.py": True, "tools/sim_tests/crossing/fly.sh": True, "tools/sim_tests/crossing/test.env": True,
             "tools/sim_tests/crossing/plots.json": False, "tools/sim_tests/_template/gates.py": False,
             "tools/tests/test_report.py": False, "tools/docs_check/check_docs.py": False, "tools/git-hooks/pre-commit": False,
             "tools/make_figures.sh": False, "localisation/nodes/cuvslam_stereo_node.py": True, "localisation/docker/Dockerfile": True,
             "localisation/README.md": False, "docs/record/CHANGES.md": False, "README.md": False, "CLAUDE.md": False,
             # fix round 2026-11-02: yaw_step + changes_log (yaw Task 4), the S5 hover/step tools, pattern mutants
             "tools/sim_tests/yaw_step/fly.sh": True, "tools/sim_tests/yaw_step/gates.py": True,
             "tools/sim_tests/yaw_step/metrics.py": True, "tools/sim_tests/yaw_step/test.env": True,
             "tools/sim_tests/yaw_step/layout.json": False, "tools/sim_tests/yaw_step/plots.json": False,
             "tools/lib/changes_log.py": True, "tools/sim_hover_step_test.sh": True, "tools/hover_step_analysis.py": True,
             "tools/hover_step_bag.py": True, "tools/hover_step_timescale.py": True, "tools/analyze_step.py": True,
             "tools/hover_step_plot.py": False, "tools/sim_tests/crossing/x.yaml": True, "mocap/cfg.yml": True,
             "notes.yamlx": False, "localisation/launch/vo.launch.py": True, "relaunch/x.py": False}

    def test_behaviour_paths(self):
        for p, want in self.CASES.items():
            self.assertEqual(CH.is_behaviour(p), want, p)


class Staged(unittest.TestCase):
    AF = "AirStack/simulation/isaac-sim/px4/airframes/10090_pegasus_starling2max"

    def test_airframe_without_a_changes_line_fails(self):                          # Review Focus 1
        errs, new = CH.staged_problems(HEAD_MD + row(1), HEAD_MD + row(1), [self.AF], True)
        self.assertTrue(any("without a new docs/record/CHANGES.md line" in e and "10090_pegasus_starling2max" in e for e in errs), errs)
        self.assertEqual(new, [])

    def test_new_line_passes_and_names_the_id(self):
        self.assertEqual(CH.staged_problems(HEAD_MD + row(1), HEAD_MD + row(1) + row(2), ["tools/sim.sh"], True), ([], ["CHG-0002"]))

    def test_edit_of_an_old_line_fails(self):
        errs, _ = CH.staged_problems(HEAD_MD + row(1), HEAD_MD + row(1, what="y") + row(2), ["tools/sim.sh"], True)
        self.assertTrue(any("append-only" in e for e in errs), errs)

    def test_reused_id_fails(self):                                                 # Review Focus 2
        errs, _ = CH.staged_problems(HEAD_MD + row(1), HEAD_MD + row(1) + row(1, what="other"), ["tools/sim.sh"], True)
        self.assertTrue(any("duplicate ID CHG-0001" in e for e in errs), errs)

    def test_malformed_line_fails(self):
        errs, _ = CH.staged_problems(HEAD_MD, HEAD_MD + "| CHG-12 | 2026-11-02 | sim-only | x | this |\n", ["tools/sim.sh"], True)
        self.assertTrue(any("malformed" in e for e in errs), errs)

    def test_docs_and_tests_need_nothing(self):
        self.assertEqual(CH.staged_problems(HEAD_MD + row(1), HEAD_MD + row(1), ["docs/RUNBOOK.md", "tools/tests/test_x.py"], True), ([], []))

    def test_before_the_standard_lands_nothing_is_enforced(self):
        self.assertEqual(CH.staged_problems("", "", ["tools/sim.sh"], False), ([], []))


class HookEndToEnd(unittest.TestCase):                                              # Review Focus 1 + 5, through core.hooksPath
    def _repo(self, tmp, standard=True):
        root = make_repo(tmp, standard=standard)
        for d in ("tools/git-hooks", "tools/docs_check"): (root / d).mkdir(parents=True)
        for f in ("git-hooks/pre-commit", "git-hooks/install.sh", "docs_check/changes.py"): shutil.copy(TOOLS / f, root / "tools" / f)
        stub = root / "tools/docs_check/check_docs.sh"; stub.write_text("#!/bin/sh\necho '0 PASS · 0 WARN · 0 FAIL · 0 SKIP'\n"); stub.chmod(0o755)
        git(root, "add", "tools"); git(root, "commit", "-q", "--no-verify", "-m", "tools")
        (root / ".git/hooks").mkdir(exist_ok=True)                                 # the pre-2026-11 copied hook
        (root / ".git/hooks/pre-commit").write_text("#!/usr/bin/env bash\n# pre-commit guard for the live clone (install: tools/git-hooks/install.sh).\nexit 0\n")
        r = subprocess.run(["bash", "tools/git-hooks/install.sh"], cwd=root, capture_output=True, text=True, env=clean_env())
        self.assertEqual(r.returncode, 0, r.stderr)
        return root

    def test_install_sets_hooks_path(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(git(self._repo(d), "config", "--get", "core.hooksPath").stdout.strip(), "tools/git-hooks")

    def test_behaviour_commit_without_entry_is_blocked_then_passes_with_one(self):
        with tempfile.TemporaryDirectory() as d:
            root = self._repo(d)
            (root / "AirStack").mkdir(); (root / "AirStack/x.py").write_text("print(1)\n"); git(root, "add", "AirStack/x.py")
            r = subprocess.run(["git", "commit", "-q", "-m", "x"], cwd=root, capture_output=True, text=True, env=clean_env())
            self.assertNotEqual(r.returncode, 0); self.assertIn("CHANGES.md", r.stdout + r.stderr)
            (root / "docs/record/CHANGES.md").write_text(HEAD_MD + row(1) + row(2)); git(root, "add", "docs/record/CHANGES.md")
            r = subprocess.run(["git", "commit", "-q", "-m", "x", "-m", block(2)], cwd=root, capture_output=True, text=True, env=clean_env())
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_inactive_until_the_standard_exists(self):
        # The rule switches on once a commit in HEAD's history added docs/CODING_STANDARD.md, or the index holds it
        # (Task 2's start commit adds it together with CHANGES.md). Before that, a behaviour commit without a line goes through.
        with tempfile.TemporaryDirectory() as d:
            root = self._repo(d, standard=False)
            (root / "AirStack").mkdir(); (root / "AirStack/x.py").write_text("print(1)\n"); git(root, "add", "AirStack/x.py")
            r = subprocess.run(["git", "commit", "-q", "-m", "x"], cwd=root, capture_output=True, text=True, env=clean_env())
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            # staging the standard itself (the start commit) switches the rule on for that same commit
            (root / "docs/CODING_STANDARD.md").write_text("KNOW\n"); (root / "AirStack/y.py").write_text("print(2)\n")
            git(root, "add", "docs/CODING_STANDARD.md", "AirStack/y.py")
            r = subprocess.run(["git", "commit", "-q", "-m", "y"], cwd=root, capture_output=True, text=True, env=clean_env())
            self.assertNotEqual(r.returncode, 0); self.assertIn("without a new docs/record/CHANGES.md line", r.stdout + r.stderr)

    def test_install_removes_the_old_copied_hook_only(self):
        with tempfile.TemporaryDirectory() as d:
            root = self._repo(d)
            self.assertFalse((root / ".git/hooks/pre-commit").exists())
            (root / ".git/hooks/pre-commit").write_text("#!/bin/sh\n# someone else's hook\nexit 0\n")
            r = subprocess.run(["bash", "tools/git-hooks/install.sh"], cwd=root, capture_output=True, text=True, env=clean_env())
            self.assertEqual(r.returncode, 0, r.stderr); self.assertTrue((root / ".git/hooks/pre-commit").exists())

    # fix round 2026-11-02 (Opus review)
    def _commit(self, root, *args):
        r = subprocess.run(["git", "commit", "-q", *args], cwd=root, capture_output=True, text=True, env=clean_env())
        return r.returncode, r.stdout + r.stderr

    def test_renamed_standard_keeps_the_rule_on(self):                             # Important 1
        with tempfile.TemporaryDirectory() as d:
            root = self._repo(d)
            git(root, "mv", "docs/CODING_STANDARD.md", "docs/OLD_STANDARD.md")
            rc, out = self._commit(root, "-m", "rename")
            self.assertNotEqual(rc, 0, out); self.assertIn("docs/CODING_STANDARD.md", out); self.assertIn("missing", out)
            git(root, "commit", "-q", "--no-verify", "-m", "rename anyway")
            (root / "AirStack").mkdir(); (root / "AirStack/x.py").write_text("print(1)\n"); git(root, "add", "AirStack/x.py")
            rc, out = self._commit(root, "-m", "x")
            self.assertNotEqual(rc, 0, out); self.assertIn("without a new docs/record/CHANGES.md line", out)

    def test_rename_out_of_a_behaviour_path_is_blocked(self):                      # --no-renames mutant
        with tempfile.TemporaryDirectory() as d:
            root = self._repo(d)
            (root / "AirStack").mkdir(); (root / "AirStack/x.py").write_text("print(1)\n" * 20)
            (root / "docs/record/CHANGES.md").write_text(HEAD_MD + row(1) + row(2)); git(root, "add", "-A")
            rc, out = self._commit(root, "-m", "x", "-m", block(2)); self.assertEqual(rc, 0, out)
            git(root, "mv", "AirStack/x.py", "docs/x.py")
            rc, out = self._commit(root, "-m", "move")
            self.assertNotEqual(rc, 0, out); self.assertIn("AirStack/x.py", out)

    def test_non_ascii_behaviour_path_is_seen(self):                               # git diff -z
        with tempfile.TemporaryDirectory() as d:
            root = self._repo(d)
            (root / "mocap").mkdir(); (root / "mocap/café.yaml").write_text("a: 1\n"); git(root, "add", "mocap/café.yaml")
            rc, out = self._commit(root, "-m", "x")
            self.assertNotEqual(rc, 0, out); self.assertIn("café.yaml", out)

    def test_amend_is_told_to_make_a_new_commit(self):
        with tempfile.TemporaryDirectory() as d:
            root = self._repo(d)
            (root / "AirStack").mkdir(); (root / "AirStack/a.py").write_text("print(1)\n")
            (root / "docs/record/CHANGES.md").write_text(HEAD_MD + row(1) + row(2)); git(root, "add", "-A")
            rc, out = self._commit(root, "-m", "x", "-m", block(2)); self.assertEqual(rc, 0, out)
            (root / "AirStack/a.py").write_text("print(2)\n"); git(root, "add", "AirStack/a.py")
            rc, out = self._commit(root, "--amend", "--no-edit")
            self.assertNotEqual(rc, 0, out); self.assertIn("make a new commit instead of --amend", out)


class Audit(unittest.TestCase):
    def setUp(self):
        self._d = tempfile.TemporaryDirectory(); self.addCleanup(self._d.cleanup); self.root = make_repo(self._d.name)

    def fails(self): return CH.audit(self.root)[0]

    def test_no_standard_skips(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertTrue(CH.audit(make_repo(d, standard=False))[2])

    def test_clean_history_passes(self):
        self.assertEqual(CH.audit(self.root)[:2], ([], []))

    def test_no_verify_behaviour_commit_is_caught_after_the_fact(self):            # Review Focus 4
        sha = commit(self.root, {"tools/sim.sh": "echo\n"}, "sneaky")
        self.assertTrue(any(sha[:7] in f and "without a Change: line" in f for f in self.fails()), self.fails())
        commit(self.root, {"docs/record/CHANGES.md": HEAD_MD + row(1) + row(2, commit=sha[:7], what="late entry")}, "late", block(2))
        self.assertEqual(self.fails(), [])

    def test_id_carried_by_two_commits_fails(self):                                 # Review Focus 2
        commit(self.root, {"docs/record/CHANGES.md": HEAD_MD + row(1) + row(2), "tools/sim.sh": "a\n"}, "a", block(2))
        commit(self.root, {"tools/lib/x.sh": "b\n"}, "b", block(2))
        self.assertTrue(any("CHG-0002" in f and "ID reuse" in f for f in self.fails()), self.fails())

    def test_duplicate_rows_fail(self):
        commit(self.root, {"docs/record/CHANGES.md": HEAD_MD + row(1) + row(2) + row(2, what="other")}, "dup", block(2))
        self.assertTrue(any("duplicate ID CHG-0002" in f for f in self.fails()), self.fails())

    def test_unknown_id_in_a_body_fails(self):
        commit(self.root, {"tools/sim.sh": "a\n"}, "a", block(7))
        self.assertTrue(any("unknown CHG-0007" in f for f in self.fails()), self.fails())

    def test_row_without_a_commit_fails_but_a_row_being_committed_does_not(self):
        commit(self.root, {"docs/record/CHANGES.md": HEAD_MD + row(1) + row(2)}, "row only")
        (self.root / "docs/record/CHANGES.md").write_text(HEAD_MD + row(1) + row(2) + row(3))       # working tree only
        f = self.fails()
        self.assertTrue(any("CHG-0002: no commit carries" in x for x in f), f); self.assertFalse(any("CHG-0003" in x for x in f), f)

    def test_dead_ledger_citation_fails(self):
        commit(self.root, {"docs/record/CHANGES.md": HEAD_MD + row(1) + row(2), "tools/sim.sh": "a\n"}, "a", block(2, verified="run, ledger #99"))
        self.assertTrue(any("LEDGER #99" in f for f in self.fails()), self.fails())
        commit(self.root, {"docs/record/CHANGES.md": HEAD_MD + row(1) + row(2) + row(3), "tools/sim.sh": "b\n"}, "b", block(3, verified="ledger #3"))
        self.assertFalse(any("LEDGER #3, not in" in f for f in self.fails()))

    def test_commit_cell_must_name_a_commit(self):
        commit(self.root, {"docs/record/CHANGES.md": HEAD_MD + row(1) + row(2, commit="deadbee")}, "x", block(2))
        self.assertTrue(any("deadbee" in f and "not a commit" in f for f in self.fails()), self.fails())

    def test_missing_field_is_a_warning(self):
        commit(self.root, {"docs/record/CHANGES.md": HEAD_MD + row(1) + row(2), "tools/sim.sh": "a\n"}, "a", block(2, drop="Watch for:"))
        fails, warns, _ = CH.audit(self.root)
        self.assertEqual(fails, []); self.assertTrue(any("Watch for:" in w for w in warns), warns)

    def test_show_prints_the_row_and_the_entry(self):
        r = subprocess.run([sys.executable, str(TOOLS / "docs_check/changes.py"), "show", "CHG-0001"], cwd=self.root,
                           capture_output=True, text=True, env=clean_env())
        self.assertEqual(r.returncode, 0, r.stderr); self.assertIn("| CHG-0001 |", r.stdout); self.assertIn("Watch for: s", r.stdout)
        self.assertLessEqual(len(r.stdout.splitlines()), 12)

    def test_candidates_lists_uncovered_behaviour_commits(self):
        sha = commit(self.root, {"tools/live/m.py": "x\n"}, "metrics change")
        commit(self.root, {"docs/RUNBOOK.md": "x\n"}, "docs only")
        r = subprocess.run([sys.executable, str(TOOLS / "docs_check/changes.py"), "candidates", "--since", "2000-01-01 00:00"],
                           cwd=self.root, capture_output=True, text=True, env=clean_env())
        self.assertEqual(r.stdout.split(), [sha[:7], "metrics", "change"])


    # fix round 2026-11-02 (Opus review)
    def test_rewriting_an_old_line_is_not_an_entry(self):                          # Important 2: the --no-verify dodge
        sha = commit(self.root, {"tools/sim.sh": "a\n", "docs/record/CHANGES.md": HEAD_MD + row(1, what="rewritten")}, "dodge")
        f = self.fails()
        self.assertTrue(any(sha[:7] in x and "without a Change: line" in x for x in f), f)
        self.assertTrue(any(sha[:7] in x and "append-only" in x for x in f), f)

    def test_rewriting_an_old_line_fails_even_with_a_change_line(self):
        commit(self.root, {"docs/record/CHANGES.md": HEAD_MD + row(1, what="rewritten") + row(2), "tools/sim.sh": "a\n"}, "a", block(2))
        self.assertTrue(any("append-only" in x for x in self.fails()), self.fails())

    def test_renamed_standard_fails(self):                                         # Important 1
        git(self.root, "mv", "docs/CODING_STANDARD.md", "docs/OLD.md"); git(self.root, "commit", "-q", "--no-verify", "-m", "mv")
        fails, _, skip = CH.audit(self.root)
        self.assertIsNone(skip); self.assertTrue(any("docs/CODING_STANDARD.md" in x and "missing" in x for x in fails), fails)

    def test_rename_out_of_a_behaviour_path_is_caught(self):                       # --no-renames mutant (R6)
        commit(self.root, {"docs/record/CHANGES.md": HEAD_MD + row(1) + row(2), "AirStack/x.py": "print(1)\n" * 20}, "a", block(2))
        git(self.root, "mv", "AirStack/x.py", "docs/x.py"); git(self.root, "commit", "-q", "--no-verify", "-m", "move")
        self.assertTrue(any("AirStack/x.py" in x and "without a Change: line" in x for x in self.fails()), self.fails())

    def test_non_ascii_path_is_caught(self):                                       # git show -z (R6)
        commit(self.root, {"mocap/café.yaml": "a: 1\n"}, "x")
        self.assertTrue(any("café.yaml" in x for x in self.fails()), self.fails())

    def test_merge_commits_are_not_judged_their_parents_are(self):                 # merge-skip mutant (plan R6: non-merge)
        git(self.root, "checkout", "-q", "-b", "side")
        side = commit(self.root, {"tools/lib/s.sh": "s\n"}, "side, no entry")
        git(self.root, "checkout", "-q", "main"); commit(self.root, {"docs/RUNBOOK.md": "x\n"}, "main side")
        git(self.root, "merge", "-q", "--no-ff", "--no-commit", "side")
        (self.root / "tools/sim.sh").write_text("evil\n"); git(self.root, "add", "tools/sim.sh")   # content only the merge has
        git(self.root, "commit", "-q", "--no-verify", "-m", "merge")
        merge = git(self.root, "rev-parse", "HEAD").stdout.strip()
        f = self.fails()
        self.assertTrue(any(side[:7] in x for x in f), f); self.assertFalse(any(merge[:7] in x for x in f), f)

    def test_inherited_git_env_is_ignored(self):                                   # env-scrub mutant: a hook exports these
        sha = commit(self.root, {"tools/sim.sh": "echo\n"}, "sneaky")
        with tempfile.TemporaryDirectory() as d:
            other = make_repo(d)
            with mock.patch.dict(os.environ, {"GIT_DIR": str(other / ".git"), "GIT_INDEX_FILE": str(other / ".git/index"),
                                              "GIT_WORK_TREE": str(other)}):
                f = self.fails()
        self.assertTrue(any(sha[:7] in x for x in f), f)

    def test_shallow_clone_skips(self):
        with tempfile.TemporaryDirectory() as d:
            dst = pathlib.Path(d) / "shallow"
            subprocess.run(["git", "clone", "-q", "--depth", "1", f"file://{self.root}", str(dst)], capture_output=True,
                           env=clean_env(), check=True)
            skip = CH.audit(dst)[2]
        self.assertTrue(skip and "shallow" in skip, skip)


class HookSource(unittest.TestCase):
    def test_change_rule_runs_first_and_the_marker_test_runs_on_airframe_edits(self):
        src = (TOOLS / "git-hooks/pre-commit").read_text()
        self.assertIn('changes.py" hook', src); self.assertLess(src.index('changes.py" hook'), src.index("check_docs.sh"))
        self.assertIn("AirStack/simulation/isaac-sim/px4/airframes/", src); self.assertIn("starling_1_indoor_params", src)
