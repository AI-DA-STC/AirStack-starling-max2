"""Partner (NUS) privacy rails, as rewritten after the owner's decision of 18 November 2026 (STANDARDS section 2).

NUS agreed that their code details, game settings and our results on their code may be published in this public repository.
So documents, records, the ledger, commit messages and the slide deck may now state NUS's values. What stays out, and what this
file checks:

1. **NUS's source code** (it stays in NUS's own repository): no tracked path that looks like a copy of it, no tracked file equal
   to one of its files, and no tracked file sharing a block of its long source lines. The line and file scans need a NUS clone on
   this machine (``SVG_NUS_CLONE``, else the home RTX 5090's private workspace); without one they skip (a skip is not a pass). The
   path scan always runs.
2. **The ``configs/local/`` mechanism**: code and committed configs read partner values from the git-ignored local files and never
   hard-code them. The value scans below therefore cover code, configs and scripts only (``.py``, ``.toml``, ``.sh``), no longer the
   documents (``.md``), commit messages or the deck.

What the value scan looks for, when the local file is on this machine (it is read here at test time only):

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
  used for something else, even next to its key (tests set keys to made-up numbers), so it is not searched for. The rule relies on
  never typing the partner's values into committed code or configs; this test catches the recognisable slips only.
- Yes/no and text options (``teammates_pass``, ``push_rule``) are not searched for: each has two or three possible
  values that the code itself names.
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


CODE_SUFFIXES = (".py", ".toml", ".sh")


def _tracked_files() -> list[str]:
    """Files git tracks or would add (tracked, plus untracked files that are not ignored), so a copy is caught before it is staged."""
    return [f for f in subprocess.run(["git", "ls-files", "-z", "-co", "--exclude-standard", "--", "."], cwd=ROOT,
                                      capture_output=True, text=True).stdout.split("\0") if f]


def _tracked_texts() -> dict[str, str]:
    """Tracked code, configs and scripts (owner, 18 Nov 2026: documents may state NUS's values; code must read them locally)."""
    return {f: _text(ROOT / f) for f in _tracked_files() if f.endswith(CODE_SUFFIXES)}


def _sources() -> dict[str, str]:
    """Everything searched for local values: tracked code, configs and scripts."""
    return _tracked_texts()


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


def test_value_scan_covers_code_not_documents():
    """Owner, 18 Nov 2026 (STANDARDS section 2): documents may state NUS's values; code and configs still may not hold them."""
    names = set(_sources())
    assert any(n.endswith(".py") for n in names) and any(n.endswith(".toml") for n in names)
    assert not any(n.endswith(".md") for n in names)


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


# --- NUS's source code stays out (owner, 18 Nov 2026: settings and results may be published, the code may not) ---

import hashlib  # noqa: E402
import os  # noqa: E402

NUS_CLONE_DEFAULT = pathlib.Path.home() / "ma_skills-self-play" / "area-denial-continuous-space-self-play"
NUS_SOURCE_SUFFIXES = (".py", ".yaml", ".yml", ".sh", ".toml")
# Paths that would mean a copy of NUS's package or its vendored environment sits in this repository.
NUS_SOURCE_PATHS = re.compile(r"(^|/)(ma_skills|skill_learning_mpe|third_party)/|\.msgpack$|(^|/)simple_area_denial\.py$")
LONG_LINE = 50          # characters: shorter lines (imports, argparse boilerplate) are too common to mean a copy
SHARED_LINES_MAX = 4    # a file sharing more distinct long lines than this with NUS's code counts as a copy
SMALL_FILE = 200        # bytes: empty or tiny files (``__init__.py``) match by chance


def _nus_clone() -> pathlib.Path | None:
    p = pathlib.Path(os.environ.get("SVG_NUS_CLONE", NUS_CLONE_DEFAULT)).expanduser()
    return p if (p / "ma_skills").is_dir() else None


def _nus_source_files(clone: pathlib.Path) -> list[pathlib.Path]:
    skip = {".git", "outputs", "wandb", ".venv", "__pycache__"}
    return [p for p in clone.rglob("*") if p.is_file() and p.suffix in NUS_SOURCE_SUFFIXES and not skip & set(p.parts)]


def _shared_long_lines(text: str, nus_lines: set[str]) -> set[str]:
    return {s for s in (line.strip() for line in text.splitlines()) if len(s) >= LONG_LINE and s in nus_lines}


def test_source_path_rule_on_made_up_names():
    assert NUS_SOURCE_PATHS.search("svg_training/third_party/x/env.py")
    assert NUS_SOURCE_PATHS.search("svg_training/ma_skills/jax/policy.py")
    assert NUS_SOURCE_PATHS.search("runs/w/actor.msgpack")
    assert not NUS_SOURCE_PATHS.search("svg_training/source/svg_training/nus/replica.py")
    assert _shared_long_lines("  a_rather_long_line_of_code = compute(this, that, and_the_other_thing)\nx = 1\n",
                              {"a_rather_long_line_of_code = compute(this, that, and_the_other_thing)"})


def test_no_nus_source_path_is_tracked():
    """Always runs: no tracked path looks like NUS's package, its vendored environment or a checkpoint file."""
    hits = [f for f in _tracked_files() if NUS_SOURCE_PATHS.search(f)]
    assert not hits, f"tracked paths that look like NUS's code or checkpoints: {hits}"


def test_no_nus_source_file_or_block_is_tracked():
    """With a NUS clone on this machine: no tracked file equals one of NUS's source files, and none shares more than a few of its
    long source lines (a pasted block). A few shared lines are generic (argparse, hashing, numpy idioms)."""
    clone = _nus_clone()
    if clone is None:
        pytest.skip("no NUS clone on this machine (set SVG_NUS_CLONE): the file and line scans cannot run (a skip is not a pass)")
    hashes, lines = set(), set()
    for p in _nus_source_files(clone):
        data = p.read_bytes()
        if len(data) >= SMALL_FILE:
            hashes.add(hashlib.sha256(data).hexdigest())
        if p.suffix == ".py":
            lines |= {s for s in (line.strip() for line in data.decode(errors="ignore").splitlines()) if len(s) >= LONG_LINE}
    assert lines, "the NUS clone has no long source lines: wrong folder?"
    hits = []
    for f in _tracked_files():
        data = (ROOT / f).read_bytes() if (ROOT / f).is_file() else b""
        if len(data) >= SMALL_FILE and hashlib.sha256(data).hexdigest() in hashes:
            hits.append(f"{f}: equal to a NUS file")
        shared = _shared_long_lines(data.decode(errors="ignore"), lines)
        if len(shared) > SHARED_LINES_MAX:
            hits.append(f"{f}: {len(shared)} long lines of NUS's code")
    assert not hits, "NUS source code in tracked files:\n" + "\n".join(hits)
