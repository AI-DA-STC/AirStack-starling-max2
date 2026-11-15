"""The partner's numbers stay in the git-ignored local file (configs/local/partner_rules.toml); none may appear in a
tracked file under svg_training/, in a commit message that touched it, or in the text of the slide deck.

What the scan looks for, when the local file is on this machine (it is read here at test time only):

1. A key of the local file written next to the local value, e.g. ``keepout_strike_m = <local value>`` or
   ``"rules.keepout_strike_m": <local value>``, for every numeric key whose local value differs from the committed
   default and has three or more significant digits (any element, for a list). Tests and examples set these keys
   to made-up small numbers, which may equal a partner value by chance, so smaller values are not searched for.
2. Any local value as a bare number, as written in the local file, and the forms the code computes from it (team
   speed in m/s = units/step x metres/unit / seconds/step, game ticks = steps x seconds/step / 0.05, game length
   in s), rounded as a document would round them; only values with three or more significant digits that are not
   also committed defaults.

Limits (read these before trusting a pass):

- A small common number (one or two significant digits, say 0.8 or 40) cannot be told apart from the same number
  used for something else, even next to its key (tests set keys to made-up numbers), so it is not searched for. The rule relies on never typing the partner's values into a committed
  file; this test catches the recognisable slips only.
- Yes/no and text options (``teammates_pass``, ``push_rule``) are not searched for: each has two or three possible
  values that the code itself names.
- The PDF copy of the deck is not read (compressed); it is built from the .pptx, which is.
- With no local file, or nothing distinctive in it, the scans skip and say why: a skip is not a pass.
"""
import html
import math
import pathlib
import re
import subprocess
import sys
import tomllib
import zipfile

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
from svg_training.core.game_config import TICK_S, load_game_cfg  # noqa: E402

LOCAL = ROOT / "configs/local/partner_rules.toml"
DECK = ROOT / "docs/pipeline/training-pipeline.pptx"
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


def _committed_text() -> str:
    return (ROOT / "configs/s2_game.toml").read_text() + (ROOT / "configs/partner_rules.example.toml").read_text()


def _distinctive_values(text: str) -> set[str]:
    """Number tokens as written with >= 3 significant digits, minus any value equal to a committed default."""
    body = "\n".join(line.split("#", 1)[0] for line in text.splitlines())
    committed = _committed_text()
    out = set()
    for tok in _NUM.findall(body):
        if _sig_digits(tok) >= 3 and not _has_token(committed, tok):
            out.add(tok)
    return out


def _written_forms(x: float) -> set[str]:
    """How a computed number may be written in a document: 2-4 decimals and 3-4 significant digits."""
    forms = {f"{x:.{d}f}" for d in (2, 3, 4)} | {f"{x:.{s}g}" for s in (3, 4)}
    if float(x).is_integer():
        forms.add(str(int(x)))
    return {f for f in forms if _NUM.fullmatch(f)}


def _converted(cfg) -> dict[str, float]:
    """The numbers the code computes from the partner rules (game_config.GameCfg)."""
    return {"strike speed m/s": cfg.team_speed_mps("strike"), "guard speed m/s": cfg.team_speed_mps("guard"),
            "game ticks": float(cfg.game_ticks()),
            "game length s": cfg.rules.game_steps * cfg.rules.seconds_per_step}


def _converted_distinctive(local_cfg, neutral_cfg) -> set[str]:
    """Written forms of the converted local numbers with >= 3 significant digits that are neither a form of the
    neutral number nor a token of the committed config files."""
    committed, out = _committed_text(), set()
    neutral = _converted(neutral_cfg)
    for name, x in _converted(local_cfg).items():
        if math.isclose(x, neutral[name], rel_tol=1e-9):
            continue
        for f in _written_forms(x) - _written_forms(neutral[name]):
            if _sig_digits(f) >= 3 and not _has_token(committed, f):
                out.add(f)
    return out


def _numbers(v) -> tuple[float, ...] | None:
    """A TOML value as a tuple of numbers (a list gives its elements), or None for yes/no and text values."""
    if isinstance(v, bool) or isinstance(v, str):
        return None
    if isinstance(v, (int, float)):
        return (float(v),)
    if isinstance(v, (list, tuple)) and all(isinstance(e, (int, float)) and not isinstance(e, bool) for e in v):
        return tuple(float(e) for e in v)
    return None


def _sig_of(x: float) -> int:
    """Significant digits of a number in its shortest written form (repr: 0.025 -> 2, 1200 -> 2, 0.0237 -> 3)."""
    return _sig_digits(str(int(x)) if float(x).is_integer() else repr(float(x)).lstrip("-"))


def _key_checks(local: dict, neutral: dict) -> dict[str, tuple[float, ...]]:
    """{key: local numbers} for every numeric local key whose value differs from the committed (neutral) one and has
    >= 3 significant digits (in any element)."""
    out = {}
    for sec, table in local.items():
        for key, val in table.items():
            lv, nv = _numbers(val), _numbers(neutral.get(sec, {}).get(key))
            if lv is None or max(_sig_of(x) for x in lv) < 3:
                continue
            if nv is not None and len(nv) == len(lv) and all(math.isclose(a, b, rel_tol=1e-9) for a, b in zip(lv, nv)):
                continue
            out[key] = lv
    return out


def _key_hit(text: str, key: str, value: tuple[float, ...]) -> bool:
    """True if text writes `key` (possibly dotted or quoted) assigned `value` with = or :, e.g. key = 0.7, "a.key": 0.7,
    key = [0.1, 0.2]."""
    pat = re.compile(rf"(?<![\w]){re.escape(key)}[\"'`]?\s*[=:]\s*[\"'`]?(\[[^\]]*\]|\([^)]*\)|[-+0-9.eE_]+)")
    for m in pat.finditer(text):
        try:
            got = tuple(float(t.replace("_", "")) for t in re.findall(r"[-+]?[0-9][0-9._]*(?:[eE][-+]?\d+)?",
                                                                       m.group(1)))
        except ValueError:
            continue
        if len(got) == len(value) and all(math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12) for a, b in zip(got, value)):
            return True
    return False


def _deck_text(path: pathlib.Path) -> str:
    """Visible text of a .pptx: every XML part, one line per paragraph, tags removed."""
    parts = []
    with zipfile.ZipFile(path) as z:
        for name in z.namelist():
            if name.endswith(".xml"):
                x = z.read(name).decode("utf-8", "replace")
                x = re.sub(r"</a:p>", "\n", x)
                parts.append(html.unescape(re.sub(r"<[^>]+>", "", x)))
    return "\n".join(parts)


def _tracked_texts() -> dict[str, str]:
    files = subprocess.run(["git", "ls-files", "-z", "--", "."], cwd=ROOT, capture_output=True,
                           text=True).stdout.split("\0")
    return {f: _text(ROOT / f) for f in files if f}


def _commit_messages() -> str:
    return subprocess.run(["git", "log", "--format=%B", "--", "."], cwd=ROOT, capture_output=True, text=True).stdout


def _sources() -> dict[str, str]:
    """Everything committed that is searched: tracked files, the commit messages, the deck's text."""
    out = _tracked_texts()
    out["<commit messages touching svg_training>"] = _commit_messages()
    out["<text inside docs/pipeline/training-pipeline.pptx>"] = _deck_text(DECK)
    return out


def _find_hits(checks: dict[str, tuple[float, ...]], values: list[str], sources: dict[str, str]) -> list[tuple]:
    """(where, what) for every key written with its local value and every distinctive value found; `what` names
    the key or the value's index, never the value itself (test output must not print partner numbers)."""
    hits = [(w, key) for w, text in sources.items() for key, v in checks.items() if _key_hit(text, key, v)]
    hits += [(w, f"value #{i}") for w, text in sources.items() for i, v in enumerate(values) if _has_token(text, v)]
    return hits


@pytest.fixture(scope="module")
def local():
    """(local TOML dict, neutral TOML dict, local GameCfg, neutral GameCfg), or skip when there is no local file."""
    if not LOCAL.exists():
        pytest.skip("no local partner file on this machine: nothing to search for (not a pass)")
    neutral_toml = tomllib.loads((ROOT / "configs/s2_game.toml").read_text())
    neutral_toml = {"partner_rules": neutral_toml.get("partner_rules", {}), "arena": neutral_toml.get("arena", {})}
    return (tomllib.loads(LOCAL.read_text()), neutral_toml, load_game_cfg(use_local=True)[0],
            load_game_cfg(use_local=False)[0])


# --- the helpers, on made-up numbers ---

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


def test_key_hit_forms():
    v = (0.83,)
    assert _key_hit("keepout_strike_m = 0.83\n", "keepout_strike_m", v)
    assert _key_hit('cfg.replace(**{"rules.keepout_strike_m": 0.830})', "keepout_strike_m", v)
    assert _key_hit("`keepout_strike_m = 0.83`", "keepout_strike_m", v)
    assert not _key_hit("keepout_strike_m = 0.831", "keepout_strike_m", v)
    assert not _key_hit("keepout_guard_m = 0.83", "keepout_strike_m", v)
    assert not _key_hit("the gap was 0.83 m", "keepout_strike_m", v)
    assert _key_hit("zone_radius_frac = [0.13, 0.27]", "zone_radius_frac", (0.13, 0.27))
    assert not _key_hit("zone_radius_frac = [0.13, 0.28]", "zone_radius_frac", (0.13, 0.27))
    assert _key_hit("game_steps = 1_234", "game_steps", (1234.0,))


def test_key_checks_skip_defaults_and_options():
    local = {"partner_rules": {"keepout_strike_m": 1.10, "game_steps": 977, "push_rule": "shove",
                               "teammates_pass": True, "keepout_guard_m": 0.9, "strike_units_per_step": 0.0237},
             "arena": {"zone_radius_frac": [0.10, 0.25]}}
    neutral = {"partner_rules": {"keepout_strike_m": 1.10, "game_steps": 1200, "push_rule": "block",
                                 "teammates_pass": True, "keepout_guard_m": 1.10, "strike_units_per_step": 0.025},
               "arena": {"zone_radius_frac": [0.10, 0.25]}}
    # 0.9 differs from the default but has one significant digit: generic, not searched for
    assert _key_checks(local, neutral) == {"game_steps": (977.0,), "strike_units_per_step": (0.0237,)}
    assert _sig_of(0.025) == 2 and _sig_of(1200) == 2 and _sig_of(0.0237) == 3 and _sig_of(977) == 3


def test_converted_forms():
    cfg = load_game_cfg(use_local=False)[0]
    made_up = cfg.replace(**{"rules.strike_units_per_step": 0.0237, "rules.seconds_per_step": 0.07})
    forms = _converted_distinctive(made_up, cfg)
    assert "0.339" in forms and "0.3386" in forms       # strike: 0.0237 x 1 / 0.07 m/s
    assert _converted_distinctive(cfg, cfg) == set()


def test_find_hits_on_made_up_sources():
    sources = {"a.md": "the gap was 0.7731 m", "b.py": '{"rules.game_steps": 977}', "c.md": "nothing here 0.77",
               "<commit messages>": "tune keepout_guard_m = 0.833"}
    hits = _find_hits({"game_steps": (977.0,), "keepout_guard_m": (0.833,)}, ["0.7731"], sources)
    assert sorted(hits) == [("<commit messages>", "keepout_guard_m"), ("a.md", "value #0"), ("b.py", "game_steps")]


def test_deck_text_is_read():
    t = _deck_text(DECK)
    assert "Guard" in t and "<a:t>" not in t


# --- the scans ---

def test_local_keys_not_written_with_local_values(local):
    ltoml, ntoml, _, _ = local
    checks = _key_checks(ltoml, ntoml)
    if not checks:
        pytest.skip("no numeric key of the local file both differs from the committed default and has 3 or more "
                    "significant digits: nothing distinctive to search for (see the module docstring)")
    hits = _find_hits(checks, [], _sources())
    assert hits == [], f"local key written with its local value in: {hits}"


def test_local_values_not_in_committed_text(local):
    ltoml_text = LOCAL.read_text()
    _, _, lcfg, ncfg = local
    values = sorted(_distinctive_values(ltoml_text) | _converted_distinctive(lcfg, ncfg))
    if not values:
        pytest.skip("no local value or converted value has 3 or more significant digits: small numbers cannot be "
                    "told apart from ordinary ones (see the module docstring)")
    hits = _find_hits({}, values, _sources())
    assert hits == [], f"a distinctive local value (index into the sorted list) appears in: {hits}"
