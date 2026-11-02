#!/usr/bin/env python3
"""Change-logging standard (docs/CODING_STANDARD.md): path map, CHANGES.md parser, staged-commit rule, git-log audit.

Stdlib only. Used by tools/git-hooks/pre-commit (`changes.py hook`, first) and by check_docs.py (the change-log pass).
The rule is inactive until docs/CODING_STANDARD.md exists: the hook checks HEAD and the index, the audit the working tree.

CLI (run from anywhere inside the repo):
  hook                          the staged rule (uses the hook's inherited GIT_INDEX_FILE); exit 1 on any error
  audit                         FAIL/WARN lines for CHANGES.md ids vs git log; exit 1 on any FAIL
  show CHG-nnnn                 the CHANGES.md line, a blank line, then the entry block from its commit
  candidates --since '<d> 00:00' behaviour commits with no Change: line and not named by a CHANGES.md line, oldest first
  is-behaviour <path>...        '<path>: yes|no' per path
"""
import argparse, collections, os, pathlib, re, subprocess, sys

CHANGES_FILE = "docs/record/CHANGES.md"
STANDARD_FILE = "docs/CODING_STANDARD.md"
LEDGER_FILE = "docs/record/LEDGER.md"
FIELDS = ("Change:", "What:", "Scope:", "Why:", "Could affect:", "Watch for:", "Verified by:", "Revert:")
SCOPES = ("sim-only", "real-drone", "sim+real", "tooling")

ROW_RE = re.compile(r"^\| (CHG-\d{4}) \| (\d{4}-\d\d-\d\d) \| (sim-only|real-drone|sim\+real|tooling) \| ([^|]+?) \| "
                    r"(this|[0-9a-f]{7,40}(?:, [0-9a-f]{7,40})*) \|\s*$")
CHANGE_RE = re.compile(r"^Change: (CHG-\d{4})\b", re.M)
LEDGER_ROW_RE = re.compile(r"^\|\s*(\d+)\s*\|\s*20\d\d-\d\d-\d\d\s*\|", re.M)

# A path is behaviour if it matches a BEHAVIOUR pattern and no NOT_BEHAVIOUR pattern (NOT_BEHAVIOUR wins).
BEHAVIOUR = tuple(re.compile(p) for p in (
    r"^AirStack/", r"^patches/", r"^starling_1_indoor_params\.params$", r"^mocap(\.sh$|/)",
    r"^tools/(sim|sim_tab|sim_terminals|sim_hover_step_run)\.sh$", r"^tools/hover_step_report\.py$",
    r"^tools/(lib|live|teleop)/", r"^tools/sim_tests/(?!_template/)[^/]+/(fly\.sh|gates\.py|metrics\.py|test\.env)$",
    r"^localisation/(nodes|scripts|docker|scenes)/", r"\.ya?ml$", r"(^|/)launch/", r"(^|/)Dockerfile",
    r"(^|/)docker-compose", r"fastdds\.xml$"))
NOT_BEHAVIOUR = tuple(re.compile(p) for p in (
    r"\.md$", r"(^|/)docs/", r"(^|/)tests?/", r"\.(png|jpe?g|gif|svg|pdf|mkv|mp4|ulg)$", r"^\.github/", r"^\.claude/"))

GIT_SCRUB = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR", "GIT_OBJECT_DIRECTORY", "GIT_PREFIX")

Row = collections.namedtuple("Row", "id date scope what commits lineno raw")


def is_behaviour(path):
    return any(p.search(path) for p in BEHAVIOUR) and not any(p.search(path) for p in NOT_BEHAVIOUR)


def parse_rows(text):
    """CHANGES.md text -> (rows, bad). Any line starting '| CHG-' that does not match ROW_RE is malformed."""
    rows, bad = [], []
    for n, line in enumerate((text or "").splitlines(), 1):
        if not line.startswith("| CHG-"):
            continue
        m = ROW_RE.match(line)
        if not m:
            bad.append(f"malformed line {n}: {line.strip()[:100]}")
            continue
        cell = m.group(5)
        commits = () if cell == "this" else tuple(cell.split(", "))
        rows.append(Row(m.group(1), m.group(2), m.group(3), m.group(4), commits, n, line.rstrip()))
    return rows, bad


def _dups(rows):
    return [i for i, c in collections.Counter(r.id for r in rows).items() if c > 1]


def staged_problems(old_text, new_text, staged_paths, standard_present):
    """The pre-commit rule, pure. old = HEAD's CHANGES.md, new = the index's. Returns (errors, new_ids)."""
    if not standard_present:
        return [], []
    old_rows, _ = parse_rows(old_text)
    new_rows, bad = parse_rows(new_text)
    errors = [f"{CHANGES_FILE}: {b}" for b in bad]
    new_raw = collections.Counter(r.raw for r in new_rows)
    for r in old_rows:
        if new_raw[r.raw] > 0:
            new_raw[r.raw] -= 1
        else:
            errors.append(f"{CHANGES_FILE} is append-only: {r.id} (line {r.lineno}) was edited or removed")
    errors += [f"{CHANGES_FILE}: duplicate ID {i}" for i in _dups(new_rows)]
    old_ids = {r.id for r in old_rows}
    new_ids = []
    for r in new_rows:
        if r.id not in old_ids and r.id not in new_ids:
            new_ids.append(r.id)
    beh = [p for p in staged_paths if is_behaviour(p)]
    if beh and not new_ids:
        more = f" (+{len(beh) - 5} more)" if len(beh) > 5 else ""
        errors.append(f"behaviour path(s) staged without a new {CHANGES_FILE} line: {', '.join(beh[:5])}{more}")
    return errors, new_ids


def entry_block(body, cid):
    """Lines from 'Change: <cid>' through the first line starting 'Revert:' (or up to the next 'Change:' line)."""
    lines = (body or "").splitlines()
    for i, line in enumerate(lines):
        m = CHANGE_RE.match(line)
        if m and m.group(1) == cid:
            out = [line]
            for nxt in lines[i + 1:]:
                if CHANGE_RE.match(nxt):
                    break
                out.append(nxt)
                if nxt.startswith("Revert:"):
                    break
            return out
    return None


# ----------------------------------------------------------------------- git
def _env(scrub):
    if not scrub:
        return None
    return {k: v for k, v in os.environ.items() if k not in GIT_SCRUB}


def _git(root, *args, scrub=True):
    """(returncode, stdout). Never raises."""
    try:
        r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, env=_env(scrub))
        return r.returncode, r.stdout
    except OSError:
        return 127, ""


def _log(root, rng, *extra):
    """[(sha, parents, body)] for rng, newest first."""
    rc, out = _git(root, "log", rng, "--format=%H%x1f%P%x1f%B%x1e", *extra)
    if rc != 0:
        return None
    commits = []
    for rec in out.split("\x1e"):
        rec = rec.strip("\n")
        if not rec:
            continue
        sha, parents, body = (rec.split("\x1f") + ["", ""])[:3]
        commits.append((sha.strip(), parents.split(), body))
    return commits


def _files(root, sha):
    rc, out = _git(root, "show", "--no-renames", "--format=", "--name-only", sha)
    return [l for l in out.splitlines() if l.strip()] if rc == 0 else []


def _added_a_row(root, sha):
    rc, out = _git(root, "show", "--format=", "--unified=0", sha, "--", CHANGES_FILE)
    return rc == 0 and any(l.startswith("+| CHG-") for l in out.splitlines())


def _resolve(root, sha):
    rc, out = _git(root, "rev-parse", "--verify", "--quiet", f"{sha}^{{commit}}")
    return out.strip() if rc == 0 and out.strip() else None


def _described(root, rows):
    """Full shas named in Commit cells -> {sha: row id}; plus FAIL lines for cells naming no commit."""
    described, fails = {}, []
    for r in rows:
        for s in r.commits:
            full = _resolve(root, s)
            if full:
                described[full] = r.id
            else:
                fails.append(f"{r.id}: commit cell names {s}, which is not a commit")
    return described, fails


def _carriers(commits, described):
    carriers = collections.defaultdict(list)
    for sha, _, body in commits:
        if sha in described:
            continue
        for cid in dict.fromkeys(CHANGE_RE.findall(body)):
            carriers[cid].append((sha, body))
    return carriers


def audit(root):
    """(fails, warns, skip). skip is a reason string while docs/CODING_STANDARD.md is absent (rules R1-R8)."""
    root = pathlib.Path(root)
    if not (root / STANDARD_FILE).exists():
        return [], [], f"{STANDARD_FILE} not in the working tree yet (the standard has not landed)"
    cf = root / CHANGES_FILE
    if not cf.exists():
        return [f"{CHANGES_FILE} missing while {STANDARD_FILE} exists"], [], None
    rc, _ = _git(root, "rev-parse", "--verify", "--quiet", "HEAD")
    if rc != 0:
        return [], [], "no git history (HEAD unresolvable); change-log audit skipped"
    fails, warns = [], []
    rows, bad = parse_rows(cf.read_text(encoding="utf-8", errors="replace"))           # R2
    fails += [f"{CHANGES_FILE}: {b}" for b in bad]
    fails += [f"{CHANGES_FILE}: duplicate ID {i}" for i in _dups(rows)]
    wt_ids = {r.id for r in rows}
    described, cell_fails = _described(root, rows)                                     # R3
    fails += cell_fails
    commits = _log(root, "HEAD")
    if commits is None:
        return fails + ["git log failed"], warns, None
    carriers = _carriers(commits, described)
    _, head_text = _git(root, "show", f"HEAD:{CHANGES_FILE}")
    head_ids = list(dict.fromkeys(r.id for r in parse_rows(head_text)[0]))
    for cid in head_ids:                                                               # R4
        c = carriers.get(cid, [])
        if not c:
            fails.append(f"{cid}: no commit carries 'Change: {cid}'")
        elif len(c) > 1:
            fails.append(f"{cid}: carried by {len(c)} commits ({', '.join(s[:7] for s, _ in c)}) — ID reuse")
    for cid, c in carriers.items():                                                    # R5
        if cid not in wt_ids:
            fails += [f"commit {s[:7]} names unknown {cid}" for s, _ in c]
    _, starts = _git(root, "log", "--diff-filter=A", "--format=%H", "HEAD", "--", STANDARD_FILE)
    start = starts.split()[-1] if starts.split() else None
    if start:                                                                          # R6
        for sha, parents, body in _log(root, f"{start}..HEAD") or []:
            if len(parents) > 1 or CHANGE_RE.search(body) or sha in described:
                continue
            beh = [f for f in _files(root, sha) if is_behaviour(f)]
            if beh and not _added_a_row(root, sha):
                fails.append(f"commit {sha[:7]} touches behaviour paths ({', '.join(beh[:3])}) without a Change: line")
    lt = root / LEDGER_FILE
    ledger = set(LEDGER_ROW_RE.findall(lt.read_text(encoding="utf-8", errors="replace"))) if lt.exists() else set()
    for cid, c in carriers.items():
        for sha, body in c:
            blk = entry_block(body, cid) or []
            for line in blk:                                                           # R7
                if line.startswith("Verified by:"):
                    for n in re.findall(r"#(\d+)", line):
                        if n not in ledger:
                            fails.append(f"{cid}: Verified by cites LEDGER #{n}, not in {LEDGER_FILE} table 1")
            idx = []                                                                   # R8
            for fld in FIELDS:
                at = next((i for i, l in enumerate(blk) if l.startswith(fld)), None)
                if at is None:
                    warns.append(f"{cid}: entry lacks {fld} (commit {sha[:7]})")
                else:
                    idx.append(at)
            if idx != sorted(idx):
                warns.append(f"{cid}: entry fields out of order (commit {sha[:7]}); order is {' '.join(FIELDS)}")
    return fails, warns, None


# ----------------------------------------------------------------------- CLI
def _toplevel(scrub=True):
    try:
        r = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, env=_env(scrub))
    except OSError:
        return None
    return pathlib.Path(r.stdout.strip()) if r.returncode == 0 and r.stdout.strip() else None


def cmd_hook():
    root = _toplevel(scrub=False)
    if root is None:
        print("change log: not inside a git work tree"); return 1
    rc, out = _git(root, "diff", "--cached", "--name-only", "--no-renames", scrub=False)
    if rc != 0:
        print("change log: git diff --cached failed"); return 1
    staged = [l for l in out.splitlines() if l.strip()]
    present = any(_git(root, "cat-file", "-e", spec, scrub=False)[0] == 0 for spec in (f"HEAD:{STANDARD_FILE}", f":{STANDARD_FILE}"))
    new_text = _git(root, "show", f":{CHANGES_FILE}", scrub=False)
    old_text = _git(root, "show", f"HEAD:{CHANGES_FILE}", scrub=False)
    errors, new_ids = staged_problems(old_text[1] if old_text[0] == 0 else "", new_text[1] if new_text[0] == 0 else "",
                                      staged, present)
    for e in errors:
        print(f"change log: {e}")
    if errors:
        return 1
    for cid in new_ids:
        print(f"change log: {cid} staged — start the commit body with 'Change: {cid}'")
    return 0


def cmd_audit():
    root = _toplevel()
    fails, warns, skip = audit(root or pathlib.Path.cwd())
    if skip:
        print(f"SKIP {skip}"); return 0
    for f in fails:
        print(f"FAIL {f}")
    for w in warns:
        print(f"WARN {w}")
    if not fails and not warns:
        print("PASS change log")
    return 1 if fails else 0


def cmd_show(cid):
    root = _toplevel() or pathlib.Path.cwd()
    cf = root / CHANGES_FILE
    rows, _ = parse_rows(cf.read_text(encoding="utf-8", errors="replace") if cf.exists() else "")
    row = next((r for r in rows if r.id == cid), None)
    commits = _log(root, "HEAD") or []
    described, _ = _described(root, rows)
    carrier = _carriers(commits, described).get(cid, [])
    blk = entry_block(carrier[-1][1], cid) if carrier else None                         # oldest carrier
    if row:
        print(row.raw)
    else:
        print(f"{cid}: no line in {CHANGES_FILE}")
    print()
    if blk:
        print(f"(commit {carrier[-1][0][:7]})")
        print("\n".join(blk))
    else:
        print(f"{cid}: no commit carries 'Change: {cid}'")
    return 0 if row and blk else 1


def cmd_candidates(since):
    root = _toplevel() or pathlib.Path.cwd()
    cf = root / CHANGES_FILE
    rows, _ = parse_rows(cf.read_text(encoding="utf-8", errors="replace") if cf.exists() else "")
    described, _ = _described(root, rows)
    for sha, parents, body in reversed(_log(root, "HEAD", f"--since={since}") or []):
        if len(parents) > 1 or CHANGE_RE.search(body) or sha in described:
            continue
        if any(is_behaviour(f) for f in _files(root, sha)):
            print(f"{sha[:7]} {body.splitlines()[0] if body.strip() else ''}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("hook"); sub.add_parser("audit")
    sp = sub.add_parser("show"); sp.add_argument("id")
    sp = sub.add_parser("candidates"); sp.add_argument("--since", required=True)
    sp = sub.add_parser("is-behaviour"); sp.add_argument("paths", nargs="+")
    a = ap.parse_args(argv)
    if a.cmd == "hook":
        return cmd_hook()
    if a.cmd == "audit":
        return cmd_audit()
    if a.cmd == "show":
        return cmd_show(a.id)
    if a.cmd == "candidates":
        return cmd_candidates(a.since)
    for p in a.paths:
        print(f"{p}: {'yes' if is_behaviour(p) else 'no'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
