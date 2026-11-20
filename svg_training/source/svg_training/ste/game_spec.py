"""The game spec sheet of STE's learning track as settings: ``configs/ste_game.toml`` (task L0.8).

Every value of the game the track trains, each with its status label (FIXED, MEASURED, PROPOSED or OPEN, as defined at
the top of ``STANDARDS.md``) and its source. The labels live in the file's comments, one value per line, in the form
``key = value   # LABEL (source): text`` (the convention of ``configs/ste_learning.toml``). The sheet for readers is
``ste_learning/GAME_SPEC.md``; a test keeps its table and this file equal.

The sheet lists, it does not decide: the game does not read this file. The ``tag_rule`` section records the proposal;
the ``tag`` section (task L0.9) lists the game's own switch for the study tag with the defaults of
``core/game_config.TagCfg``, which a game file sets in its own ``[tag]`` table (a test keeps the two equal).

The loader fails closed: an unknown or missing section or key, a value of the wrong type, a value spread over more than
one line, or a value line without exactly one label and a source raises ``ValueError``. Lists load as tuples, so nothing can be
changed after loading. Standard library only: no PyTorch, no Isaac.
"""
from __future__ import annotations

import hashlib
import math
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Union

from ..core.game_config import CONFIGS
from .config import Provenance

GAME_FILE = CONFIGS / "ste_game.toml"

LABELS: tuple[str, ...] = ("FIXED", "MEASURED", "PROPOSED", "OPEN")

# The kind of each value: "decimal" (a finite float, written 1.0 not 1), "whole" (an int), "yes_no" (a bool), "text" (a
# string), "decimals" and "texts" (lists of those). Keys in the order of the sheet's table; SI units in the names.
SCHEMA: dict[str, str] = {
    "zone.shape": "text",
    "zone.scored_in": "text",
    "zone.radius_m": "decimal",
    "zone.centre": "text",
    "zone.win_ticks_inside": "whole",
    "height.band_m": "decimals",
    "height.mode": "text",
    "height.start_m": "decimal",
    "arena.side_m": "decimal",
    "arena.wall_margin_m": "decimal",
    "arena.walls": "text",
    "arena.environment": "text",
    "starts.guard_disc_m": "decimal",
    "starts.strike_ring_m": "decimal",
    "starts.team_spacing_margin_m": "decimal",
    "timing.game_s": "decimal",
    "timing.decision_s": "decimal",
    "speeds.strike_mps": "decimal",
    "speeds.strike_to_guard_ratio": "decimal",
    "teams.of_interest": "texts",
    "teams.target_sizes": "texts",
    "teams.base_case": "text",
    "tag_rule.main_game_has_tag": "yes_no",
    "tag_rule.radius_m": "decimal",
    "tag_rule.pairing": "text",
    "tag_rule.guard_survives_tag_prob": "decimal",
    "tag.mode": "text",
    "tag.radius_m": "decimal",
    "tag.guard_survives_tag_prob": "decimal",
    "filter.pairs": "text",
    "filter.share": "text",
    "filter.keepout_m": "decimal",
    "players.guard_park_ring_m": "decimal",
}

_KIND_WORDS = {"decimal": "a decimal number (write 2.0, not 2)", "whole": "a whole number", "yes_no": "true or false",
               "text": "text in quotes", "decimals": "a list of decimal numbers", "texts": "a list of texts in quotes"}
_LABELLED = re.compile(rf"({'|'.join(LABELS)})\b\s*([(:]\s*\S.*)$")
_SECOND_LABEL = re.compile(rf"(^\(\s*({'|'.join(LABELS)})\b)|\b({'|'.join(LABELS)})\s*[(:]")
_HEADER = re.compile(r"\[(\w+)\]$")
_VALUE_LINE = re.compile(r"(\w+)\s*=\s*\S")

Value = Union[float, int, bool, str, tuple]


@dataclass(frozen=True)
class SpecEntry:
    """One value of the game: ``key`` "section.name", the value, its status label and its source (the comment after
    the label)."""
    key: str
    value: Value
    status: str
    source: str


@dataclass(frozen=True)
class GameSpec:
    """Every value of the sheet, in the order of ``SCHEMA``."""
    entries: tuple[SpecEntry, ...]

    def entry(self, key: str) -> SpecEntry:
        """The entry of ``key`` ("section.name"); ``KeyError`` for a key the sheet does not hold."""
        for entry in self.entries:
            if entry.key == key:
                return entry
        raise KeyError(f"no setting {key!r} in the game spec (known: {list(SCHEMA)})")

    def value(self, key: str) -> Value:
        return self.entry(key).value

    def status(self, key: str) -> str:
        return self.entry(key).status


def _split_comment(line: str) -> tuple[str, str]:
    """(code, comment) of one TOML line: the comment starts at the first # outside a "basic string"."""
    in_string = False
    for i, char in enumerate(line):
        if char == '"' and (i == 0 or line[i - 1] != "\\"):
            in_string = not in_string
        elif char == "#" and not in_string:
            return line[:i].strip(), line[i + 1:].strip()
    return line.strip(), ""


def _labels(text: str, name: str) -> dict[str, tuple[str, str]]:
    """{"section.key": (label, source)} of every value line; raises for a line that is not one plain ``key = value``,
    or whose comment does not start with a label and a source."""
    out: dict[str, tuple[str, str]] = {}
    section = None
    for number, line in enumerate(text.splitlines(), start=1):
        code, comment = _split_comment(line)
        if not code:
            continue
        header = _HEADER.match(code)
        if header:
            section = header.group(1)
            continue
        found = _VALUE_LINE.match(code)
        if not found or section is None:
            raise ValueError(f"{name} line {number}: one value per line, as 'key = value   # LABEL (source): text'; "
                             f"found {line!r}")
        key = f"{section}.{found.group(1)}"
        labelled = _LABELLED.match(comment)
        source = labelled.group(2).strip() if labelled else ""
        bracket = re.match(r"\(([^)]*)\)", source)        # "(source): text": the brackets must hold words
        if (not labelled or not re.search(r"\w", source) or _SECOND_LABEL.search(source)
                or (bracket is not None and not re.search(r"\w", bracket.group(1)))):
            raise ValueError(f"{name} line {number}, {key}: the comment must start with one status label "
                             f"{list(LABELS)} and its source (some words; no second label), as '# PROPOSED (P1): ...'; "
                             f"found {comment!r}")
        out[key] = (labelled.group(1), source)
    return out


def _typed(value: Any, kind: str, key: str) -> Value:
    """``value`` as the kind the schema names (lists as tuples). Exact on purpose: a yes/no is not a number, 2 is not
    2.0."""
    def decimal(v: Any) -> bool:
        return type(v) is float and math.isfinite(v)

    ok = {"decimal": decimal(value), "whole": type(value) is int, "yes_no": type(value) is bool,
          "text": type(value) is str,
          "decimals": type(value) is list and bool(value) and all(decimal(v) for v in value),
          "texts": type(value) is list and bool(value) and all(type(v) is str for v in value)}[kind]
    if not ok:
        raise ValueError(f"{key} must be {_KIND_WORDS[kind]}, got {value!r}")
    return tuple(value) if type(value) is list else value


def load_game_spec(path: str | Path = GAME_FILE) -> tuple[GameSpec, Provenance]:
    """Load the game spec file. Returns the spec and where it came from (path, sha256 of the bytes read).

    Raises ``ValueError`` for a file that is not valid TOML (the message names the file), an unknown or missing
    section or key, a value of the wrong type, a value not on a line of its own, or a value line without a status label
    and a source; ``FileNotFoundError`` for a missing file.
    """
    path = Path(path)
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
        data = tomllib.loads(text)
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as err:
        raise ValueError(f"{path}: not valid TOML in UTF-8 ({err})") from err
    labels = _labels(text, path.name)

    sections = list(dict.fromkeys(key.split(".")[0] for key in SCHEMA))
    unknown = sorted(set(data) - set(sections))
    if unknown:
        raise ValueError(f"unknown section(s) in {path.name}: {unknown} (known: {sections})")
    missing = [name for name in sections if name not in data]
    if missing:
        raise ValueError(f"missing section(s) in {path.name}: {missing}")
    for name in sections:
        table, keys = data[name], [key.split(".")[1] for key in SCHEMA if key.startswith(f"{name}.")]
        if not isinstance(table, dict):
            raise ValueError(f"[{name}] must be a table, got {table!r}")
        unknown = sorted(set(table) - set(keys))
        if unknown:
            raise ValueError(f"unknown key(s) in [{name}]: {unknown} (known: {keys})")
        absent = [key for key in keys if key not in table]
        if absent:
            raise ValueError(f"missing key(s) in [{name}]: {absent}")

    if list(labels) != list(SCHEMA):     # a dotted key or a value over several lines would leave the two lists unequal
        raise ValueError(f"{path.name}: one value per line, in the order of the sheet; the lines set {list(labels)}, "
                         f"expected {list(SCHEMA)}")
    entries = tuple(SpecEntry(key=key, value=_typed(data[key.split(".")[0]][key.split(".")[1]], kind, key),
                              status=labels[key][0], source=labels[key][1]) for key, kind in SCHEMA.items())
    return GameSpec(entries=entries), Provenance(str(path), hashlib.sha256(raw).hexdigest())
