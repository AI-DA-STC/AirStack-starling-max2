"""The partner's numbers stay in the git-ignored local file; none may appear in a tracked file."""
import pathlib
import re
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))

_NUM = re.compile(r"(?<![\w.])\d+(?:\.\d+)?(?![\w.])")


def _text(p: pathlib.Path) -> str:
    try:
        return p.read_text()
    except (UnicodeDecodeError, OSError):
        return ""


def _sig_digits(tok: str) -> int:
    """Significant digits of a number token as written: leading and trailing zeros do not count."""
    return len(tok.replace(".", "").strip("0"))


def _has_token(text: str, tok: str) -> bool:
    """True if tok appears in text as a whole number token, not inside a longer one."""
    return re.search(rf"(?<![\w.]){re.escape(tok)}(?![\w.])", text) is not None


def _distinctive_values(text: str) -> set[str]:
    """Number tokens as written with >= 3 significant digits, minus any value equal to a committed default."""
    body = "\n".join(line.split("#", 1)[0] for line in text.splitlines())
    committed = (ROOT / "configs/s2_game.toml").read_text() + (ROOT / "configs/partner_rules.example.toml").read_text()
    out = set()
    for tok in _NUM.findall(body):
        if _sig_digits(tok) >= 3 and not _has_token(committed, tok):
            out.add(tok)
    return out


def test_gitignore_covers_local():
    assert "configs/local/" in (ROOT / ".gitignore").read_text().splitlines()
    r = subprocess.run(["git", "check-ignore", "-q", "configs/local/partner_rules.toml"], cwd=ROOT)
    assert r.returncode == 0


def test_whole_token_and_significant_digits():
    assert _sig_digits("200") == 1 and _sig_digits("3.0") == 1 and _sig_digits("0.7731") == 4
    assert _distinctive_values("a = 200\nb = 1200\nc = 3.0\n") == set()
    assert _has_token("x = 0.7731 m", "0.7731") and not _has_token("x = 10.77315", "0.7731")
    assert not _has_token("2000 scenes", "200")


def test_distinctive_values_helper():
    assert "0.7731" in _distinctive_values("a = 0.7731\nb = 7\n")
    assert "1200" not in _distinctive_values("b = 1200\n")


def test_local_values_not_in_tracked_files():
    local = ROOT / "configs/local/partner_rules.toml"
    if not local.exists():
        pytest.skip("no local partner file on this machine")
    values = _distinctive_values(local.read_text())
    tracked = subprocess.run(["git", "ls-files", "-z", "--", "."], cwd=ROOT, capture_output=True,
                             text=True).stdout.split("\0")
    hits = [(f, v) for f in tracked if f for v in values if _has_token(_text(ROOT / f), v)]
    assert hits == []
