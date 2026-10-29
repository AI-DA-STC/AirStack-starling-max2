#!/usr/bin/env python3
"""contract_check — verify every tools/sim_tests/<dir> carries the test contract. SIM ONLY tooling.

    contract_check.py [--tests-root tools/sim_tests]

Per directory (including _template): fly.sh, gates.py, metrics.py, plots.json, test.env, layout.json present;
gates.py mentions metrics_core; metrics.py and gates.py compile; fly.sh passes bash -n; test.env defines
TITLE ISSUE SCOPE SIM_ONLY_LINE CONFIG SCENARIO BAG_PREFIX; layout.json is current (make_layout --check).
Prints one "OK <dir>" or "FAIL <dir>: <reason>" line per directory; exit 0 only when all are OK.
"""
import argparse
import pathlib
import py_compile
import re
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
TOOLS = HERE.parent
FILES = ("fly.sh", "gates.py", "metrics.py", "plots.json", "test.env", "layout.json")
ENV_KEYS = ("TITLE", "ISSUE", "SCOPE", "SIM_ONLY_LINE", "CONFIG", "SCENARIO", "BAG_PREFIX")

if str(TOOLS / "live") not in sys.path:
    sys.path.insert(0, str(TOOLS / "live"))


def _compiles(path):
    with tempfile.TemporaryDirectory() as d:
        try:
            py_compile.compile(str(path), cfile=str(pathlib.Path(d) / "x.pyc"), doraise=True)
        except py_compile.PyCompileError as e:
            return str(e).strip().splitlines()[-1]
    return None


def check(test_dir):
    """Problems found in one test directory (empty list = contract met)."""
    td = pathlib.Path(test_dir)
    probs = []
    for f in FILES:
        if not (td / f).is_file():
            probs.append("missing %s" % f)
    if (td / "gates.py").is_file() and "metrics_core" not in (td / "gates.py").read_text():
        probs.append("gates.py does not use metrics_core")
    for f in ("metrics.py", "gates.py"):
        if (td / f).is_file():
            err = _compiles(td / f)
            if err:
                probs.append("%s does not compile: %s" % (f, err))
    if (td / "fly.sh").is_file():
        r = subprocess.run(["bash", "-n", str(td / "fly.sh")], capture_output=True, text=True)
        if r.returncode != 0:
            probs.append("fly.sh bash -n: %s" % r.stderr.strip().splitlines()[0] if r.stderr.strip() else "fly.sh bash -n failed")
    if (td / "test.env").is_file():
        keys = set(re.findall(r"^\s*([A-Z_][A-Z0-9_]*)=", (td / "test.env").read_text(), re.M))
        for k in ENV_KEYS:
            if k not in keys:
                probs.append("test.env lacks %s" % k)
    if (td / "plots.json").is_file() and (td / "metrics.py").is_file():
        import io
        import contextlib
        import make_layout
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            rc = make_layout.main([str(td), "--check"])
        if rc == 1:
            probs.append("layout.json is stale (python3 tools/live/make_layout.py %s)" % td)
        elif rc != 0:
            probs.append("make_layout --check rc=%d: %s" % (rc, buf.getvalue().strip()))
    return probs


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tests-root", default=str(TOOLS / "sim_tests"))
    a = ap.parse_args(argv)
    root = pathlib.Path(a.tests_root)
    dirs = sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith("__")) if root.is_dir() else []
    if not dirs:
        print("FAIL %s: no test directories" % root)
        return 1
    bad = 0
    for d in dirs:
        probs = check(d)
        if probs:
            bad += 1
            print("FAIL %s: %s" % (d.name, "; ".join(probs)))
        else:
            print("OK %s" % d.name)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
