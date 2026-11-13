#!/usr/bin/env python3
"""Documentation guard for AirStack-starling-max2 (plan 2026-10-21 §4 Phase 0b).

Stdlib only. Every check returns a Result and never raises on missing markers,
registries or files: a missing input is reported as FAIL/WARN, not a crash.
Run via tools/docs_check/check_docs.sh (which cd's to the repo root).
"""
import argparse, difflib, json, os, re, subprocess, sys, tempfile
from urllib.parse import unquote
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))                  # check_docs.sh runs python3 -I: the script's own directory is not on sys.path
import changes as CH                           # noqa: E402  (change-log pass, docs/CODING_STANDARD.md)
EXCLUDE_DIRS = ("docs/superpowers/",)          # planning notes, not the doc corpus
IRON_BEGIN, IRON_END = "<!-- IRON_RULES:BEGIN -->", "<!-- IRON_RULES:END -->"
WARN_RE = re.compile(r"^\s*(?:[-*>]|\d+\.)*\s*⚠️")       # ⚠️ after list/quote markers
MAX_DETAILS = 25

# Prose budgets (words, excl. fenced code and ⚠️ lines) from plan §2. MILESTONES is RECORD tier.
BUDGETS = {"README": 450, "CLAUDE": 1000, "START_HERE": 1500, "SETUP": 1200, "RUNBOOK": 2500,
           "PREFLIGHT": 1100, "DRONE_SETUP": 1800, "ARCHITECTURE": 1500, "CONFIG": 2500,
           "SCENARIOS": 2500, "TELEOP": 2000, "BASESTATION": 2500, "MOCAP": 2000,
           "GLOSSARY": 3000, "AI_ASSIST": 800, "MILESTONES": 1200}
PLAN_FILE = "docs/plans/2026-11-13-project-plan-linear.md"
PROJECT_DIR = "docs/projects"
LEDGER_FILE = "docs/record/LEDGER.md"
ID_PAGES = ("docs/MILESTONES.md", "docs/record/LEDGER.md", "docs/PX4_MSGS_AUDIT.md")   # plus docs/projects/*.md
NEAR_RE = re.compile(r"\bNEAR-\d+\b")
RECORD_FILES = {"MILESTONES", "MIGRATION"}  # plus docs/record/*, docs/reference/*


class Result:
    def __init__(self, name, status, summary, details=None):
        self.name, self.status, self.summary, self.details = name, status, summary, list(details or [])

    def as_dict(self):
        return {"check": self.name, "status": self.status, "summary": self.summary, "details": self.details}


def verdict(name, fails, warns, ok_msg, fail_msg=None, warn_msg=None):
    """Build a Result from a list of FAIL details and a list of WARN details."""
    if fails:
        return Result(name, "FAIL", fail_msg or f"{len(fails)} problem(s)", fails + warns)
    if warns:
        return Result(name, "WARN", warn_msg or f"{len(warns)} warning(s)", warns)
    return Result(name, "PASS", ok_msg)


# ----------------------------------------------------------------- file helpers
def rel(p):
    try:
        return str(Path(p).resolve().relative_to(ROOT))
    except ValueError:
        return str(p)


def read(p):
    try:
        return Path(p).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def excluded(p):
    r = rel(p).replace(os.sep, "/")
    return any(r.startswith(d) for d in EXCLUDE_DIRS)


def corpus():
    """README.md, CLAUDE.md, docs/**/*.md (the prose corpus)."""
    files = [ROOT / "README.md", ROOT / "CLAUDE.md"] + sorted((ROOT / "docs").rglob("*.md"))
    return [f for f in files if f.is_file() and not excluded(f)]


def top_docs():
    """docs/*.md + README.md (the pages that carry banners / ⚠️ lines)."""
    return [f for f in [ROOT / "README.md"] + sorted((ROOT / "docs").glob("*.md")) if f.is_file()]


def prose_lines(text):
    """(lineno, line) pairs outside ``` / ~~~ fences."""
    out, fence = [], None
    for i, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        if fence:
            if s.startswith(fence):
                fence = None
            continue
        if s.startswith("```") or s.startswith("~~~"):
            fence = s[:3]
            continue
        out.append((i, line))
    return out


def slugify(h):
    """GitHub heading → anchor. Lowercase, drop punctuation except -, space, _; spaces → -."""
    h = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", h)       # keep link text only
    h = re.sub(r"[^\w\- ]", "", h.strip().lower())          # \w is unicode-aware
    return h.replace(" ", "-").strip("-")                   # each space → '-' (GitHub keeps doubles)


def anchors(text):
    seen, out = {}, set()
    for _, line in prose_lines(text):
        m = re.match(r"^#{1,6}\s+(.*?)\s*#*\s*$", line)
        if m:
            s = slugify(m.group(1))
            n = seen.get(s, 0)
            seen[s] = n + 1
            out.add(s if n == 0 else f"{s}-{n}")        # GitHub de-dupes with -1, -2 …
            out.add(re.sub(r"-{2,}", "-", s))           # tolerate hand-collapsed hyphens too
    out.update(re.findall(r'<a\s+(?:id|name)="([^"]+)"', text))
    return out


def registry(fname):
    """Tab-separated registry lines → list of (flag, fields). flag ∈ {'', '?', '!'}."""
    text = read(HERE / fname)
    if text is None:
        return None
    rows = []
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        flag = line[0] if line[0] in "?!" else ""
        rows.append((flag, line[len(flag):].split("\t")))
    return rows


# ----------------------------------------------------------------- 1. links
LINK_RE = re.compile(r"\[[^\]]*\]\(<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\)")


def check_links(files):
    """Every relative .md link (with optional #fragment) must resolve; fragment must match a heading slug."""
    dead, cache, n = [], {}, 0
    for f in files:
        text = read(f)
        if text is None:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            for m in LINK_RE.finditer(line):
                tgt = m.group(1)
                if re.match(r"^[a-z][a-z0-9+.-]*:", tgt):      # http:, mailto:, file: …
                    continue
                path, _, frag = tgt.partition("#")
                if path and not path.endswith(".md"):
                    continue
                n += 1
                target = (f.parent / path).resolve() if path else f.resolve()
                if not target.is_file():
                    dead.append(f"{rel(f)}:{i}: missing file → {tgt}")
                    continue
                if frag:
                    if target not in cache:
                        cache[target] = anchors(read(target) or "")
                    if frag.lower() not in cache[target]:
                        dead.append(f"{rel(f)}:{i}: no heading for #{frag} in {rel(target)}")
    return verdict("links", dead, [], f"all {n} relative .md links in {len(files)} files resolve",
                   f"{len(dead)} dead link(s)/fragment(s)")


def link_files():
    files = corpus() + [ROOT / "AirStack" / "README.md"] + sorted((ROOT / "tools").glob("*.sh"))
    return [f for f in dict.fromkeys(files) if f.is_file()]


# ----------------------------------------------------------------- 2. section refs
def check_section_refs():
    """Plain-text § refs and bare 'ledger #N' outside docs/record and MIGRATION → WARN (MOVE phase turns them into links)."""
    sec, ledger = {}, []
    for f in link_files():
        r = rel(f)
        if r.startswith("docs/record/") or r == "docs/MIGRATION.md":
            continue
        for i, line in enumerate((read(f) or "").splitlines(), 1):
            n = line.count("§")
            if n:
                sec[r] = sec.get(r, 0) + n
            bare = re.sub(r"\[[^\]]*\]\([^)]*\)", "", line)      # drop links, then look for ledger refs
            for m in re.finditer(r"ledger\s*#\d+", bare, re.I):
                ledger.append(f"{r}:{i}: {m.group(0)}")
    total = sum(sec.values())
    warns = [f"§ refs: {total} across {len(sec)} files; top: " + ", ".join(
        f"{k} ({v})" for k, v in sorted(sec.items(), key=lambda kv: -kv[1])[:5])] if total else []
    if ledger:
        warns.append(f"bare 'ledger #N' refs not inside a link: {len(ledger)}")
        warns += ledger[:10]
    return verdict("section-refs", [], warns, "no plain-text § or bare ledger refs",
                   warn_msg=f"{total} § refs, {len(ledger)} bare ledger refs (become links in MOVE phase)")


# ----------------------------------------------------------------- 3. iron rules
def iron_block(text):
    if text is None or IRON_BEGIN not in text or IRON_END not in text:
        return None
    return text.split(IRON_BEGIN, 1)[1].split(IRON_END, 1)[0]


def iron_line_range(text):
    """1-based (start, end) line numbers of the IRON_RULES block, or None."""
    lines = text.splitlines()
    b = [i for i, l in enumerate(lines, 1) if IRON_BEGIN in l]
    e = [i for i, l in enumerate(lines, 1) if IRON_END in l]
    return (b[0], e[0]) if b and e and e[0] >= b[0] else None


def check_iron_rules():
    """IRON_RULES block must exist in PREFLIGHT.md and CLAUDE.md and be byte-identical; AI_ASSIST must quote the rule count."""
    pf, cl = iron_block(read(ROOT / "docs/PREFLIGHT.md")), iron_block(read(ROOT / "CLAUDE.md"))
    fails, warns = [], []
    if pf is None:
        fails.append("docs/PREFLIGHT.md: IRON_RULES markers missing")
    if cl is None:
        fails.append("CLAUDE.md: IRON_RULES markers missing")
    if pf is not None and cl is not None and pf != cl:
        fails.append("blocks differ (PREFLIGHT = canonical, CLAUDE.md = copy):")
        fails += list(difflib.unified_diff(pf.splitlines(), cl.splitlines(), "docs/PREFLIGHT.md",
                                           "CLAUDE.md", lineterm="", n=1))[:20]
    src = pf if pf is not None else cl
    if src is not None:
        n = len(re.findall(r"^\s*\d+\.\s", src, re.M))
        ai = read(ROOT / "docs/AI_ASSIST.md") or ""
        table_nums = {int(x) for x in re.findall(r"^\|\s*(\d+)\s*\|", ai, re.M)}
        if not (re.search(rf"\b{n}\s+iron\s+rules?\b", ai, re.I) or len(table_nums) == n):
            warns.append(f"docs/AI_ASSIST.md does not mention '{n} iron rules' nor a table with {n} rule numbers")
        ok = f"blocks identical, {n} numbered rules, AI_ASSIST count matches"
    else:
        ok = "blocks identical"
    return verdict("iron-rules", fails, warns, ok, "IRON_RULES blocks missing or divergent")


# ----------------------------------------------------------------- 4. safety registry
def check_safety_registry():
    """Each registry phrase must appear byte-identically in each listed file and ≥ min times across the corpus."""
    rows = registry("safety_registry.txt")
    if rows is None:
        return Result("safety-registry", "FAIL", "tools/docs_check/safety_registry.txt missing")
    texts = {rel(f): read(f) or "" for f in corpus()}
    fails, warns, n = [], [], 0
    for flag, fields in rows:
        if flag == "!" or len(fields) < 3:
            continue                                       # '!' rows only whitelist ⚠️ lines (check 8)
        phrase, want, files = fields[0], fields[1].strip(), [x.strip() for x in fields[2].split(",") if x.strip()]
        n += 1
        bucket = warns if flag == "?" else fails
        cap = phrase[0].upper() + phrase[1:]   # sentence-initial form counts too
        total = sum(t.count(phrase) + (t.count(cap) if cap != phrase else 0) for t in texts.values())
        if want.isdigit() and total < int(want):
            bucket.append(f"'{phrase}': {total} occurrence(s) in corpus, need ≥{want}")
        for fn in files:
            t = texts.get(fn, read(ROOT / fn))
            if t is None:
                bucket.append(f"'{phrase}': listed file {fn} does not exist")
            elif phrase not in t and cap not in t:
                bucket.append(f"'{phrase}': missing in {fn}")
    return verdict("safety-registry", fails, warns, f"{n} phrases present at every listed location",
                   f"{len(fails)} registry violation(s)")


# ----------------------------------------------------------------- 5. values registry
def source_value(path, key):
    """Current value of key in a yaml ('key: value', any indent) or PX4 params export (tab-separated, col 4)."""
    text = read(ROOT / path)
    if text is None:
        return None, "file missing"
    if path.endswith(".params"):
        for line in text.splitlines():
            cols = line.split("\t")
            if len(cols) >= 4 and cols[2].strip() == key:
                return cols[3].strip(), None
        return None, "key not found"
    m = re.search(rf"^\s*{re.escape(key)}\s*:\s*([^#\n]*)", text, re.M)
    return (m.group(1).strip().strip("'\""), None) if m else (None, "key not found")


def same_number(a, b):
    try:
        return abs(float(a) - float(b)) < 1e-9
    except (TypeError, ValueError):
        return str(a).strip() == str(b).strip()


def check_values_registry():
    """(a) source yaml/params must equal the registry value; (b) doc prose 'key … number' must not disagree."""
    rows = registry("values_registry.txt")
    if rows is None:
        return Result("values-registry", "FAIL", "tools/docs_check/values_registry.txt missing")
    fails, warns, keys = [], [], {}
    for flag, fields in rows:
        if len(fields) < 3:
            warns.append(f"malformed registry row: {fields}")
            continue
        key, src, expect = (x.strip() for x in fields[:3])
        cur, err = source_value(src, key)
        if err:
            fails.append(f"{key}: {src}: {err}")
        elif not same_number(cur, expect):
            fails.append(f"{key}: registry says {expect}, {src} has {cur} (registry drift)")
        keys.setdefault(key, set()).add(expect)
    for f in corpus():                                     # (b) prose claims
        for i, line in prose_lines(read(f) or ""):
            line = re.sub(r"20\d\d-\d\d-\d\d", "", line)              # dates are not values
            for key, expects in keys.items():
                for m in re.finditer(r"(?<![\w])" + re.escape(key) + r"(?![\w])(.{0,40}?)(-?\d+(?:\.\d+)?)", line):
                    if not any(same_number(m.group(2), e) for e in expects):
                        warns.append(f"{rel(f)}:{i}: {key} … {m.group(2)} (expected {'/'.join(sorted(expects))})")
    return verdict("values-registry", fails, warns, f"{len(rows)} values match their sources; no stale prose numbers",
                   f"{len(fails)} source/registry mismatch(es)", f"{len(warns)} prose number(s) differ from registry")


# ----------------------------------------------------------------- 6. banners
def check_banners():
    """docs/*.md + README.md: a DO|KNOW|RECORD tier tag within the first 5 non-empty lines."""
    missing = []
    for f in top_docs():
        head = [l for l in (read(f) or "").splitlines() if l.strip()][:5]
        if not any(re.search(r"(?<![A-Za-z])(DO|KNOW|RECORD)(?![A-Za-z])", l) for l in head):
            missing.append(rel(f))
    return verdict("banners", [], missing, f"all {len(top_docs())} pages carry a tier tag",
                   warn_msg=f"{len(missing)} page(s) without a DO/KNOW/RECORD banner")


# ----------------------------------------------------------------- 7. real-page hygiene
FORBIDDEN_RE = re.compile(r"cbf_sim|swarm_sim|teleop_single|squeeze_3drone|teleop_real\.yaml")


def check_real_page_hygiene():
    """REAL pages must not name sim configs outside the IRON_RULES block, ⚠️/[SIM] lines or RUNBOOK §A."""
    fails = []
    for name in ("docs/RUNBOOK.md", "docs/PREFLIGHT.md"):
        text = read(ROOT / name)
        if text is None:
            fails.append(f"{name}: file missing")
            continue
        lines = text.splitlines()
        iron = iron_line_range(text) or (0, -1)
        sec_a = (0, -1)
        if name.endswith("RUNBOOK.md"):
            starts = [i for i, l in enumerate(lines, 1) if re.match(r"^## A\b", l)]
            if starts:
                nxt = [i for i, l in enumerate(lines, 1) if i > starts[0] and l.startswith("## ")]
                sec_a = (starts[0], nxt[0] - 1 if nxt else len(lines))
        for i, line in enumerate(lines, 1):
            if iron[0] <= i <= iron[1] or sec_a[0] <= i <= sec_a[1]:
                continue
            if WARN_RE.match(line) or "[SIM]" in line:
                continue
            m = FORBIDDEN_RE.search(line)
            if m:
                fails.append(f"{name}:{i}: '{m.group(0)}' on a REAL page")
    return verdict("real-page-hygiene", fails, [], "RUNBOOK/PREFLIGHT free of sim config names",
                   f"{len(fails)} sim config name(s) on REAL pages")


# ----------------------------------------------------------------- 8. warnings registered
def check_warnings_registered():
    """Every ⚠️ line must contain a safety-registry phrase or a '!' free entry → else WARN."""
    rows = registry("safety_registry.txt") or []
    phrases = [fields[0] for _, fields in rows if fields and fields[0]]
    if not phrases:
        return Result("warnings-registered", "WARN", "safety registry missing/empty; cannot match ⚠️ lines")
    unreg, total = [], 0
    for f in top_docs():
        for i, line in enumerate((read(f) or "").splitlines(), 1):
            if WARN_RE.match(line):
                total += 1
                if not any(p in line for p in phrases):
                    unreg.append(f"{rel(f)}:{i}: {line.strip()[:90]}")
    return verdict("warnings-registered", [], unreg, f"all {total} ⚠️ lines match the registry",
                   warn_msg=f"{len(unreg)}/{total} ⚠️ lines not in safety_registry.txt")


# ----------------------------------------------------------------- 9. budget
def is_record(f):
    r = rel(f)
    return f.stem in RECORD_FILES or r.startswith("docs/record/") or r.startswith("docs/reference/") \
        or r.startswith("docs/projects/")


def check_budget():
    """Prose words (no fenced code, no ⚠️ lines) per page vs plan §2 budgets; TROUBLESHOOTING rows ≤40 words."""
    warns, total = [], 0
    for f in corpus():
        lines = [l for _, l in prose_lines(read(f) or "") if not WARN_RE.match(l)]
        words = sum(len(l.split()) for l in lines)
        if not is_record(f):
            total += words
        if f.stem == "TROUBLESHOOTING":
            long = [(i, len(l.split())) for i, l in prose_lines(read(f) or "") if l.startswith("|") and len(l.split()) > 40]
            if long:
                warns.append(f"{rel(f)}: {len(long)} table row(s) > 40 words (first at line {long[0][0]}, {long[0][1]} w)")
        elif f.stem in BUDGETS and words > BUDGETS[f.stem]:
            warns.append(f"{rel(f)}: {words}/{BUDGETS[f.stem]} words (+{words - BUDGETS[f.stem]})")
    msg = f"non-RECORD prose total {total} words (target 30–32k)"
    return verdict("budget", [], warns, f"all pages within budget; {msg}", warn_msg=f"{len(warns)} page(s) over budget; {msg}")


# ----------------------------------------------------------------- 10. preflight date
DATE_TOKEN = re.compile(r"v20\d\d-\d\d-\d\d")


def check_preflight_date():
    """PREFLIGHT line 1 carries vYYYY-MM-DD; an uncommitted edit must also bump that token."""
    name = "docs/PREFLIGHT.md"
    text = read(ROOT / name)
    if text is None:
        return Result("preflight-date", "FAIL", f"{name} missing")
    first = next((l for l in text.splitlines() if l.strip()), "")
    tok = DATE_TOKEN.search(first)
    if not tok:
        return Result("preflight-date", "WARN", f"{name}: no vYYYY-MM-DD token on its first line")
    try:
        dirty = subprocess.run(["git", "diff", "--quiet", "HEAD", "--", name], cwd=ROOT, capture_output=True).returncode == 1
        if dirty:
            head = subprocess.run(["git", "show", f"HEAD:{name}"], cwd=ROOT, capture_output=True, text=True).stdout
            old = DATE_TOKEN.search(next((l for l in head.splitlines() if l.strip()), ""))
            if old and old.group(0) == tok.group(0):
                return Result("preflight-date", "FAIL", f"PREFLIGHT edited without bumping its date ({tok.group(0)})")
    except OSError:
        return Result("preflight-date", "PASS", f"token {tok.group(0)} (git unavailable; edit check skipped)")
    return Result("preflight-date", "PASS", f"token {tok.group(0)}")


# ----------------------------------------------------------------- 11. headings stable
def check_headings_stable():
    """Headings must not carry dates or status glyphs (they churn GitHub anchors)."""
    bad = []
    for f in top_docs():
        if f.name == "README.md":
            continue
        for i, line in prose_lines(read(f) or ""):
            if line.startswith("#") and re.search(r"(?<!v)20\d\d-\d\d-\d\d|⏳|✅|\(STE", line):
                bad.append(f"{rel(f)}:{i}: {line.strip()[:90]}")
    return verdict("headings-stable", [], bad, "no dates/status tokens in headings",
                   warn_msg=f"{len(bad)} heading(s) with date/status tokens")


# ----------------------------------------------------------------- 12. hashes (hook)
def check_hashes():
    """MOVE-phase hook: corpus_hashes.txt / retired.txt coverage. Skips silently when no snapshot exists."""
    snap = HERE / "corpus_hashes.txt"
    if not snap.is_file():
        return Result("hashes", "SKIP", "hash coverage (no snapshot)")
    n = len([l for l in (read(snap) or "").splitlines() if l.strip() and not l.startswith("#")])
    return Result("hashes", "WARN", f"snapshot has {n} entries; coverage check not implemented yet (MOVE phase)")


# ----------------------------------------------------------------- 13/14. linear parity, images
def norm(s):
    """Whitespace normalisation: the only change allowed before comparing Linear titles."""
    return " ".join(s.split())


def _table_cells(line):
    """Cells of a markdown table row; None for non-rows and |---| separators."""
    s = line.strip()
    if not s.startswith("|"):
        return None
    cells = [c.strip() for c in s.strip("|").split("|")] if s.endswith("|") else [c.strip() for c in s[1:].split("|")]
    if all(re.fullmatch(r":?-{3,}:?", c) for c in cells if c) and any(cells):
        return None
    return cells


def plan_issues(text):
    """{id: (title, status)} from plan rows '| [NEAR-nnn](url) | title | Done|In Progress|Backlog|Canceled |'."""
    out = {}
    for line in text.splitlines():
        c = _table_cells(line)
        if c and len(c) >= 3 and c[-1] in ("Done", "In Progress", "Backlog", "Canceled"):
            m = re.fullmatch(r"\[(NEAR-\d+)\]\(.*\)", c[0])
            if m:
                out[m.group(1)] = (c[1], c[-1])
    return out


def plan_structure(text):
    """Milestones and issue membership from the plan's '## Project … · HTX-Rn …' sections (rescope 2026-10-30):
    ({code: (project, 'code name', order)}, {NEAR id: milestone code}). Headings outside project sections
    (e.g. '### Terms') are not milestones."""
    ms, member, project, cur = {}, {}, None, None
    for line in text.splitlines():
        if line.startswith("## "):
            m = re.search(r"\b(HTX-R\d+)\b", line) if line.startswith("## Project") else None
            project, cur = (m.group(1) if m else None), None
        elif project and line.startswith("### ") and norm(line[4:]):
            name = norm(line[4:])
            cur = name.split()[0]
            ms[cur] = (project, name, len(ms))
        elif project and cur:
            c = _table_cells(line)
            m = re.fullmatch(r"\[(NEAR-\d+)\]\(.*\)", c[0]) if c else None
            if m:
                member[m.group(1)] = cur
    return ms, member


def plan_milestones(text):
    """{code: 'code name'} — the milestone names in the plan."""
    return {code: v[1] for code, v in plan_structure(text)[0].items()}


def page_milestones(text):
    """[(lineno, code, 'code name')] from a project page's '### code name — TAG' headings; code '' = empty heading."""
    out = []
    for i, line in enumerate(text.splitlines(), 1):
        if line.startswith("### "):
            name = norm(line[4:].split(" — ")[0])
            out.append((i, name.split()[0] if name else "", name))
    return out


def page_issue_rows(text):
    """(lineno, id, title, status_cell, result_cell) for table rows whose first cell is a NEAR id (plain or linked).
    Issue tables are | Issue | Title | Linear status | Result | Evidence | (owner, 2026-10-30); a shorter row has
    status None, and check_linear_parity fails it."""
    out = []
    for i, line in enumerate(text.splitlines(), 1):
        c = _table_cells(line)
        if c and len(c) >= 2:
            m = re.match(r"^\[?(NEAR-\d+)\]?(\(.*\))?$", c[0])
            if m:
                if len(c) >= 5:
                    out.append((i, m.group(1), c[1], c[2], c[3]))
                else:
                    out.append((i, m.group(1), c[1], None, c[2] if len(c) > 2 else ""))
    return out


def pass_records(root):
    """docs/record/*_record.md + localisation/results/*_record.md whose first 10 lines carry 'Verdict: PASS'."""
    out = []
    for d in ("docs/record", "localisation/results"):
        for f in sorted((Path(root) / d).glob("*_record.md")):
            head = "\n".join((read(f) or "").splitlines()[:10])
            if re.search(r"Verdict:\**\s*PASS\b", head):
                out.append(f)
    return out


def check_linear_parity():
    """NEAR ids on project pages/ID pages exist in the plan file with identical titles; PASS records cited."""
    plan_text = read(ROOT / PLAN_FILE)
    if plan_text is None:
        return Result("linear-parity", "FAIL", f"{PLAN_FILE} missing")
    plan = plan_issues(plan_text)
    plan_ms, member = plan_structure(plan_text)
    projects = sorted((ROOT / PROJECT_DIR).glob("*.md"))
    fails, warns, nrows, page_text, seen_ms, seen_ids = [], [], 0, "", set(), {}
    for f in projects:
        text = read(f) or ""
        page_text += text + "\n"
        heads = page_milestones(text)
        on_page = []
        for i, code, name in heads:
            if not code:
                fails.append(f"{rel(f)}:{i}: empty ### heading")
                continue
            if code in on_page:
                fails.append(f"{rel(f)}:{i}: milestone {code} appears twice on the page")
                continue
            on_page.append(code)
            seen_ms.add(code)
            if code not in plan_ms:
                fails.append(f"{rel(f)}:{i}: milestone '{name}' not in {PLAN_FILE}")
                continue
            proj, pname, _ = plan_ms[code]
            if name != pname:
                fails.append(f"{rel(f)}:{i}: milestone {code} name differs — page: '{name}' / plan: '{pname}'")
            if proj != f.stem:
                fails.append(f"{rel(f)}:{i}: milestone {code} belongs to {proj} in the plan but sits on {f.name}")
        known = [c for c in on_page if c in plan_ms]
        if known != sorted(known, key=lambda c: plan_ms[c][2]):
            fails.append(f"{rel(f)}: milestones out of the plan's order — page: {' '.join(known)} / plan: "
                         f"{' '.join(sorted(known, key=lambda c: plan_ms[c][2]))}")
        def under(line_no, _heads=heads):
            cur = None
            for i, code, _ in _heads:
                if i < line_no:
                    cur = code
            return cur
        snap = re.search(r"Linear snapshot:\s*(\d{4}-\d\d-\d\d)", text)
        date = snap.group(1) if snap else "(no snapshot line)"
        row_lines = set()
        for i, nid, title, status, result in page_issue_rows(text):
            nrows += 1
            row_lines.add(i)
            if nid in seen_ids:
                fails.append(f"{rel(f)}:{i}: {nid} appears twice (first at {seen_ids[nid]})")
                continue
            seen_ids[nid] = f"{rel(f)}:{i}"
            if nid not in plan:
                fails.append(f"{rel(f)}:{i}: {nid} not in {PLAN_FILE}")
                continue
            if member.get(nid) and under(i) != member[nid]:
                fails.append(f"{rel(f)}:{i}: {nid} sits under {under(i)} on the page but under {member[nid]} in the plan")
            if norm(title) != norm(plan[nid][0]):
                fails.append(f"{rel(f)}:{i}: {nid} title differs — page: '{norm(title)}' / plan: '{norm(plan[nid][0])}'")
            if status is None:
                fails.append(f"{rel(f)}:{i}: {nid} row has no Linear status column (Issue | Title | Linear status | Result | Evidence)")
            elif status != plan[nid][1]:
                fails.append(f"{rel(f)}:{i}: {nid} Linear status '{status}' differs from the snapshot {date}: '{plan[nid][1]}' — copy it from {PLAN_FILE}")
            if re.match(r"PASS\b", result) and plan[nid][1] == "Backlog":
                warns.append(f"{rel(f)}:{i}: {nid} Result says PASS but the snapshot {date} lists it Backlog — tick it in Linear")
        for i, line in enumerate(text.splitlines(), 1):
            if i not in row_lines:
                for nid in NEAR_RE.findall(line):
                    if nid not in plan:
                        fails.append(f"{rel(f)}:{i}: {nid} not in the plan file")
    for code, (_, name, _) in plan_ms.items():
        if projects and code not in seen_ms:
            fails.append(f"{PLAN_FILE}: milestone '{name}' has no section on any {PROJECT_DIR} page")
    for name in ID_PAGES:
        text = read(ROOT / name)
        for i, line in enumerate((text or "").splitlines(), 1):
            for nid in dict.fromkeys(NEAR_RE.findall(line)):
                if nid not in plan:
                    fails.append(f"{name}:{i}: {nid} not in the plan file")
    ledger = read(ROOT / LEDGER_FILE) or ""
    recs = pass_records(ROOT)
    for r in recs:
        if r.name not in ledger:
            warns.append(f"{rel(r)}: Verdict PASS but not cited in {LEDGER_FILE}")
        if projects and r.name not in page_text:
            warns.append(f"{rel(r)}: Verdict PASS but not cited on any docs/projects page")
    return verdict("linear-parity", fails, warns,
                   f"{nrows} issue rows on {len(projects)} project pages match the plan file; {len(recs)} PASS records cited",
                   f"{len(fails)} Linear id/title mismatch(es)", f"{len(warns)} parity warning(s)")


CHANGE_LIST_GLOB = "docs/plans/*-linear-change-list.md"


def check_change_lists():
    """An applied Linear change list (has an '**Applied:**' line) maps every NEW-n to a NEAR id, and each
    NEW row's title equals the snapshot's title for that id (rescope 2026-10-30). Draft lists are skipped."""
    plan = plan_issues(read(ROOT / PLAN_FILE) or "")
    fails, n = [], 0
    for f in sorted(ROOT.glob(CHANGE_LIST_GLOB)):
        text = read(f) or ""
        if "**Applied:**" not in text:
            continue
        n += 1
        mapping, titles = {}, {}
        for line in text.splitlines():
            c = _table_cells(line)
            if not c:
                continue
            if len(c) == 2 and re.fullmatch(r"NEW-\d+", c[0]):
                mapping[c[0]] = c[1] if re.fullmatch(r"NEAR-\d+", c[1]) else None
            elif len(c) >= 4 and re.fullmatch(r"NEW-\d+", c[1]):
                if c[0] != "NEW":
                    fails.append(f"{rel(f)}: {c[1]} sits in a '{c[0]}' row; placeholders belong to NEW rows")
                titles[c[1]] = c[3]
        used = {}
        for ph, nid in mapping.items():
            if nid and nid in used:
                fails.append(f"{rel(f)}: {nid} is mapped twice ({used[nid]}, {ph})")
            elif nid:
                used[nid] = ph
        for ph, title in titles.items():
            nid = mapping.get(ph)
            if nid is None:
                fails.append(f"{rel(f)}: {ph} has no NEAR id in the placeholder map")
            elif nid not in plan:
                fails.append(f"{rel(f)}: {ph} → {nid} not in {PLAN_FILE}")
            elif norm(title) != norm(plan[nid][0]):
                fails.append(f"{rel(f)}: {ph} → {nid} title differs — list: '{norm(title)}' / plan: '{norm(plan[nid][0])}'")
    return verdict("change-lists", fails, [], f"{n} applied Linear change list(s) match {PLAN_FILE}",
                   f"{len(fails)} change-list mismatch(es)")


IMG_MD_RE = re.compile(r"!\[[^\]]*\]\(<?([^)\s>]+)")
IMG_HTML_RE = re.compile(r"<img\b[^>]*?\bsrc\s*=\s*[\"']([^\"']+)[\"']", re.I)


def check_images(files):
    """Every relative ![..](path) / <img src> must point at an existing file."""
    missing, n = [], 0
    for f in files:
        text = read(f)
        if text is None:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            for m in list(IMG_MD_RE.finditer(line)) + list(IMG_HTML_RE.finditer(line)):
                tgt = m.group(1)
                if re.match(r"^[a-z][a-z0-9+.-]*:", tgt):
                    continue
                path = re.split(r"[#?]", tgt, maxsplit=1)[0]
                if not path:
                    continue
                n += 1
                if not (Path(f).parent / unquote(path)).is_file():
                    missing.append(f"{rel(f)}:{i}: missing image → {tgt}")
    return verdict("images", missing, [], f"all {n} relative image references in {len(files)} files exist",
                   f"{len(missing)} missing image(s)")


TOP_PAGE_LINES, PROJECT_PAGE_LINES, MILESTONE_SECTION_LINES, CELL_CHARS = 60, 250, 40, 120
CAPTION_CHARS = 400   # a caption is 2–4 sentences; the interpretation goes in the results text


def long_captions(text):
    """(lineno, length) for the italic caption line right under an image when it exceeds CAPTION_CHARS."""
    out, prev_img = [], False
    for i, line in enumerate(text.splitlines(), 1):
        if prev_img and line.startswith("*") and len(line) > CAPTION_CHARS:
            out.append((i, len(line)))
        prev_img = line.startswith("![")
    return out
TOP_PAGE = "docs/MILESTONES.md"


def section_lines(text):
    """(heading, n) per '### ' section; image lines and an italic caption right after one are not counted."""
    out, cur, n, prev_img = [], None, 0, False
    for line in text.splitlines():
        if line.startswith("### ") or line.startswith("## ") or line.startswith("# "):
            if cur is not None:
                out.append((cur, n))
            cur, n, prev_img = (line if line.startswith("### ") else None), 1, False
            continue
        if cur is None:
            continue
        if line.startswith("!["):
            prev_img = True
            continue
        if prev_img and line.startswith("*"):
            prev_img = False
            continue
        prev_img = False
        n += 1
    if cur is not None:
        out.append((cur, n))
    return out


def long_cells(text):
    """(lineno, cell_index, length) for table cells > CELL_CHARS; the Linear title cell of a NEAR row is exempt."""
    out = []
    for i, line in enumerate(text.splitlines(), 1):
        cells = _table_cells(line)
        if cells is None:
            continue
        for j, c in enumerate(cells):
            if j == 1 and re.match(r"\[?NEAR-\d+", cells[0]):
                continue
            if len(c) > CELL_CHARS:
                out.append((i, j, len(c)))
    return out


def check_page_budgets():
    """Line budgets for the top page and project pages; cell budget on those pages only (never LEDGER)."""
    fails = []
    pages = [(ROOT / TOP_PAGE, read(ROOT / TOP_PAGE), TOP_PAGE_LINES)]
    pages += [(f, read(f), PROJECT_PAGE_LINES) for f in sorted((ROOT / PROJECT_DIR).glob("*.md"))]
    for f, text, limit in pages:
        if text is None:
            continue
        n = len(text.splitlines())
        if n > limit:
            fails.append(f"{rel(f)}: {n}/{limit} lines")
        if limit == PROJECT_PAGE_LINES:
            for h, k in section_lines(text):
                if k > MILESTONE_SECTION_LINES:
                    fails.append(f"{rel(f)}: '{h}': {k}/{MILESTONE_SECTION_LINES} lines (figures excluded)")
        for ln, ci, length in long_cells(text):
            fails.append(f"{rel(f)}:{ln}: cell {ci + 1} is {length} chars (max {CELL_CHARS})")
        for ln, length in long_captions(text):
            fails.append(f"{rel(f)}:{ln}: caption is {length} chars (max {CAPTION_CHARS})")
    return verdict("page-budgets", fails, [],
                   f"{TOP_PAGE} ≤ {TOP_PAGE_LINES} lines; {len(pages) - 1} project page(s) ≤ {PROJECT_PAGE_LINES} lines, sections ≤ {MILESTONE_SECTION_LINES}, cells ≤ {CELL_CHARS} chars, captions ≤ {CAPTION_CHARS} chars",
                   f"{len(fails)} budget breach(es)")


FIG_CAPTION_RE = re.compile(r"^\*Figure (\d+)\.")
FIG_MENTION_RE = re.compile(r"Figure (\d+)")
FIG_LINK_RE = re.compile(r"\[Figure (\d+)\]\(#fig-\1\)")


def figure_problems(text):
    """Captions `*Figure N.` numbered 1..n in page order, each with `<a id=\"fig-N\"></a>` within the 3 lines above its
    image; every other `Figure N` in the text must be the link `[Figure N](#fig-N)`. Returns FAIL detail strings."""
    out, expected, lines = [], 1, text.splitlines()
    for i, line in enumerate(lines, 1):
        m = FIG_CAPTION_RE.match(line)
        if m:
            n = int(m.group(1))
            if n != expected:
                out.append(f"line {i}: caption says Figure {n}, expected Figure {expected} (number figures in page order)")
            window = "\n".join(lines[max(0, i - 5):i - 1])
            if f'<a id="fig-{n}"></a>' not in window:
                out.append(f'line {i}: Figure {n} has no <a id="fig-{n}"></a> on the line before its image')
            expected = max(expected, n) + 1
            continue
        stripped = FIG_LINK_RE.sub("", line)
        for mm in FIG_MENTION_RE.finditer(stripped):
            out.append(f"line {i}: 'Figure {mm.group(1)}' not linked — write [Figure {mm.group(1)}](#fig-{mm.group(1)})")
    return out


def check_figure_refs():
    """Numbered, anchored, linked figures on the top page and the project pages."""
    fails = []
    pages = [ROOT / TOP_PAGE] + sorted((ROOT / PROJECT_DIR).glob("*.md"))
    for f in pages:
        text = read(f)
        if text is None:
            continue
        fails += [f"{rel(f)}:{p}" for p in figure_problems(text)]
    return verdict("figure-refs", fails, [], "figures numbered in page order, anchored, every mention a link", f"{len(fails)} figure problem(s)")


def check_purpose_lines():
    """Every ### milestone section on a project page opens with a `**Purpose:**` line a newcomer can follow."""
    fails = []
    for f in sorted((ROOT / PROJECT_DIR).glob("*.md")):
        text = read(f)
        if text is None:
            continue
        cur, has = None, True
        for i, line in enumerate(text.splitlines(), 1):
            if line.startswith("### "):
                if cur and not has:
                    fails.append(f"{rel(f)}: '{cur}' has no **Purpose:** line")
                cur, has = line[4:].strip(), False
            elif line.startswith("## "):
                if cur and not has:
                    fails.append(f"{rel(f)}: '{cur}' has no **Purpose:** line")
                cur, has = None, True
            elif line.startswith("**Purpose:**"):
                has = True
        if cur and not has:
            fails.append(f"{rel(f)}: '{cur}' has no **Purpose:** line")
    return verdict("purpose-lines", fails, [], "every milestone section says why it exists", f"{len(fails)} section(s) without a Purpose line")


def check_change_log():
    """docs/CODING_STANDARD.md: CHANGES.md IDs ↔ commits, behaviour commits carry Change:, Verified cites real LEDGER rows."""
    fails, warns, skip = CH.audit(ROOT)
    if skip:
        return Result("change-log", "SKIP", skip)
    return verdict("change-log", fails, warns, "every CHG id has one commit; behaviour commits since the standard carry Change:",
                   f"{len(fails)} change-log problem(s)")


# ----------------------------------------------------------------- 21. single home
SINGLE_HOME_EXEMPT = ("docs/plans/", "docs/superpowers/", "docs/record/", ".claude/")
SINGLE_HOME_GLOBS = ("localisation/*.md", "localisation/scenes/**/*.md", "tools/*.md", "tools/*/README.md")   # never localisation/** (unreadable studio-data dirs)
NEAR_LINES = 3


def flat_line(s):
    """Backticks removed, whitespace runs collapsed to one space, stripped."""
    return " ".join(s.replace("`", "").split())


def single_home_files():
    """corpus() plus the live localisation/tools pages, de-duplicated, minus dated history."""
    seen, out = set(), []
    for f in corpus() + [g for pat in SINGLE_HOME_GLOBS for g in sorted(ROOT.glob(pat))]:
        r = rel(f).replace(os.sep, "/")
        if f.is_file() and r not in seen and not r.startswith(SINGLE_HOME_EXEMPT):
            seen.add(r); out.append(f)
    return out


def check_single_home(rows=None):
    """single_home.txt: `only` phrases sit solely in their listed files (and are in the first); `require` phrases are present. WARN only, even on an error."""
    try:
        return _single_home(rows)
    except Exception as e:                                          # main() turns an exception into FAIL; this check never fails the run
        return Result("single-home", "WARN", f"single-home check error: {type(e).__name__}: {e}")


def _single_home(rows):
    rows = registry("single_home.txt") if rows is None else rows
    if rows is None:
        return Result("single-home", "WARN", "tools/docs_check/single_home.txt missing")
    warns, n = [], 0
    for _, f in rows:
        f = [x.strip() for x in f]
        if len(f) < 3 or f[0] not in ("only", "require") or not f[1]:
            warns.append(f"malformed registry row: {f}"); continue
        n += 1
        kind, phrase, homes = f[0], f[1], [h.strip() for h in f[2].split(",")]
        near = f[3] if len(f) > 3 and f[3] else None
        for fn in homes:
            text = read(ROOT / fn)
            if text is None:
                warns.append(f"{fn}: listed file does not exist ('{phrase}')")
            elif kind == "require" and flat_line(phrase) not in flat_line(text):
                warns.append(f"{fn}: required phrase '{phrase}' missing")
        if kind == "only":
            def hits(text):
                lines = [flat_line(x) for x in text.splitlines()]
                return [i for i, ln in enumerate(lines, 1) if flat_line(phrase) in ln and (not near or any(flat_line(near) in x for x in lines[max(0, i - 1 - NEAR_LINES):i]))]
            first = read(ROOT / homes[0])
            if first is not None and not hits(first):
                warns.append(f"{homes[0]}: '{phrase}' missing from its home")
            for p in single_home_files():
                r, text = rel(p).replace(os.sep, "/"), read(p)
                if r in homes or text is None:
                    continue
                warns += [f"{r}:{i}: '{phrase}' outside its home ({', '.join(homes)})" for i in hits(text)]
    return verdict("single-home", [], warns, f"{n} phrase(s) in their single homes", warn_msg=f"{len(warns)} single-home warning(s)")


# ----------------------------------------------------------------- selftest / main
def selftest():
    """Prove the dead-link check works on a temp corpus: one good link, one dead file, one dead fragment."""
    with tempfile.TemporaryDirectory() as d:
        a, b = Path(d) / "a.md", Path(d) / "b.md"
        b.write_text("# Real Heading · here\ntext\n", encoding="utf-8")
        a.write_text("[ok](b.md)\n[ok2](b.md#real-heading--here)\n[dead](nope.md)\n[frag](b.md#missing)\n", encoding="utf-8")
        r = check_links([a])
        print_result(r)
        ok = r.status == "FAIL" and len(r.details) == 2 and "nope.md" in r.details[0] and "#missing" in r.details[1]
        print("SELFTEST", "PASS" if ok else "FAIL", "(expected exactly 2 dead links: missing file + missing fragment)")
        return 0 if ok else 1


def print_result(r):
    print(f"[{r.status}] {r.name}: {r.summary}")
    for line in r.details[:MAX_DETAILS]:
        print(f"    {line}")
    if len(r.details) > MAX_DETAILS:
        print(f"    … {len(r.details) - MAX_DETAILS} more")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--warn-only", action="store_true", help="downgrade FAIL to WARN, exit 0")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--selftest", action="store_true", help="verify dead-link detection on a temp corpus")
    args = ap.parse_args()
    if args.selftest:
        sys.exit(selftest())
    checks = [lambda: check_links(link_files()), check_section_refs, check_iron_rules, check_safety_registry,
              check_values_registry, check_banners, check_real_page_hygiene, check_warnings_registered,
              check_budget, check_preflight_date, check_headings_stable, check_hashes,
              check_linear_parity, check_change_lists, lambda: check_images(corpus()), check_page_budgets, check_figure_refs, check_purpose_lines,
              check_single_home, check_change_log]
    results = []
    for fn in checks:
        try:
            r = fn()
        except Exception as e:                            # a check bug must never hide the other checks
            r = Result(("check_images" if fn.__name__ == "<lambda>" and "images" in repr(fn.__code__.co_names) else getattr(fn, "__name__", "check")).replace("check_", "").replace("_", "-"), "FAIL", f"checker crashed: {e!r}")
        if args.warn_only and r.status == "FAIL":
            r.status = "WARN"
        results.append(r)
    counts = {s: sum(1 for r in results if r.status == s) for s in ("PASS", "WARN", "FAIL", "SKIP")}
    if args.json:
        print(json.dumps({"results": [r.as_dict() for r in results], "counts": counts}, indent=1, ensure_ascii=False))
    else:
        for r in results:
            print_result(r)
        print(f"\n{counts['PASS']} PASS · {counts['WARN']} WARN · {counts['FAIL']} FAIL · {counts['SKIP']} SKIP")
    sys.exit(1 if counts["FAIL"] else 0)


if __name__ == "__main__":
    main()
