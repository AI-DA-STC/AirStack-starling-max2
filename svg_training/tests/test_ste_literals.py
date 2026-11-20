"""STE learning track: the code of ``source/svg_training/ste/`` holds no tuned number (ste_learning/CODING_PRACTICES.md
section 4: values that could change a result live in TOML; named physical or structural constants are fine).

The rule, as the lead defined it for task L0.1: in every ``.py`` file under ``source/svg_training/ste/`` a numeric
literal (int, float, complex; not a yes/no) other than 0, 1, -1, 2 is allowed only as the whole right-hand side, or
inside the tuple, list or dict literal on the right-hand side, of a MODULE-LEVEL assignment to an UPPER_CASE name
(``G_MPS2 = 9.81``). Anywhere else it is reported as ``file:line: value``.

Negative numbers are read as ``tests/test_nus_rules_privacy.py`` (rule G2) reads them: the scan looks at the digits,
and the minus sign in front is an operator, not part of the literal. So ``-1`` passes because 1 does, ``-0.5`` fails
because 0.5 does, and ``-2`` passes because 2 does. Also as in G2, ``0.0``, ``1.0`` and ``2.0`` pass: they equal the
allowed numbers.
"""
import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "source" / "svg_training" / "ste"
REQUIRED = ("__init__.py", "config.py")          # the scan must reach at least these: an empty scan is not a pass

ALLOWED = {0, 1, -1, 2}                          # the structural numbers of rule G2
CONSTANT_NAME = re.compile(r"_*[A-Z][A-Z0-9_]*")  # UPPER_CASE, as G_MPS2 or _SLOT


def is_number(node: ast.AST) -> bool:
    return (isinstance(node, ast.Constant) and isinstance(node.value, (int, float, complex))
            and not isinstance(node.value, bool))


def literal_numbers(value: ast.expr) -> list[ast.Constant]:
    """The number nodes of a right-hand side that is a number, or a tuple, list or dict literal of such (nested too).
    Anything else on the way (a sum, a call, a name) ends the search: its numbers are not part of a plain literal."""
    if is_number(value):
        return [value]
    if isinstance(value, ast.UnaryOp) and isinstance(value.op, (ast.USub, ast.UAdd)) and is_number(value.operand):
        return [value.operand]
    if isinstance(value, (ast.Tuple, ast.List)):
        return [number for item in value.elts for number in literal_numbers(item)]
    if isinstance(value, ast.Dict):
        return [number for item in (*value.keys, *value.values) if item is not None for number in literal_numbers(item)]
    return []


def named_constant_value(statement: ast.stmt) -> ast.expr | None:
    """The right-hand side if ``statement`` assigns to UPPER_CASE names only (``A = ...``, ``A: float = ...``)."""
    if isinstance(statement, ast.Assign):
        targets = statement.targets
    elif isinstance(statement, ast.AnnAssign) and statement.value is not None:
        targets = [statement.target]
    else:
        return None
    if all(isinstance(target, ast.Name) and CONSTANT_NAME.fullmatch(target.id) for target in targets):
        return statement.value
    return None


def tuned_numbers(source: str, name: str = "<source>") -> list[str]:
    """``name:line: value`` for every numeric literal of ``source`` that the rule does not allow, in line order."""
    tree = ast.parse(source)
    named = set()
    for statement in tree.body:                                      # module level only: not inside a def or a class
        value = named_constant_value(statement)
        if value is not None:
            named |= {id(number) for number in literal_numbers(value)}
    negated = {id(node.operand) for node in ast.walk(tree)
               if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub)}
    bad = [(node.lineno, node.col_offset, f"{'-' if id(node) in negated else ''}{node.value!r}")
           for node in ast.walk(tree) if is_number(node) and node.value not in ALLOWED and id(node) not in named]
    return [f"{name}:{line}: {text}" for line, _, text in sorted(bad)]


def package_files(folder: Path) -> list[Path]:
    """Every ``.py`` file under ``folder``; fails if the required files are not among them (a moved or empty folder)."""
    files = sorted(folder.rglob("*.py"))
    names = {path.relative_to(folder).as_posix() for path in files}
    assert len(files) >= len(REQUIRED) and set(REQUIRED) <= names, (
        f"the literal scan found {len(files)} .py file(s) under {folder}: {sorted(names)}; it must reach at least "
        f"{list(REQUIRED)}. Has the package moved? Then change PACKAGE in this test")
    return files


def scan(folder: Path) -> list[str]:
    return [hit for path in package_files(folder)
            for hit in tuned_numbers(path.read_text(), path.relative_to(folder).as_posix())]


# ------------------------------------------------------------------------------------------------ the package
def test_the_ste_package_holds_no_tuned_number():
    files = package_files(PACKAGE)
    assert {"__init__.py", "config.py"} <= {path.name for path in files}
    bad = scan(PACKAGE)
    assert not bad, f"numeric literals outside a named module-level constant (move them to a TOML file): {bad}"


# ------------------------------------------------------------------------------------------------ the scanner has teeth
@pytest.mark.parametrize("source, expected", [
    ("def f():\n    return 0.3\n", ["<source>:2: 0.3"]),                                  # a tuned number in a function
    ("def f(x=0.5):\n    return x\n", ["<source>:1: 0.5"]),                               # a default argument
    ("def f(x: float = 3) -> float:\n    return x\n", ["<source>:1: 3"]),
    ("rate = 0.3\n", ["<source>:1: 0.3"]),                                                # lower case at module level
    ("Rate = 0.3\n", ["<source>:1: 0.3"]),
    ("RATE = rate = 0.3\n", ["<source>:1: 0.3"]),                                         # one name is not a constant's
    ("A, B = 3, 4\n", ["<source>:1: 3", "<source>:1: 4"]),                                # not an assignment to a name
    ("class A:\n    RATE = 0.3\n", ["<source>:2: 0.3"]),                                  # not at module level
    ("def f():\n    RATE = 0.3\n    return RATE\n", ["<source>:2: 0.3"]),
    ("if True:\n    RATE = 0.3\n", ["<source>:2: 0.3"]),
    ("RATE = 0.3 * 2\n", ["<source>:1: 0.3"]),                                            # a sum is not a plain literal
    ("RATE = float(3)\n", ["<source>:1: 3"]),
    ("RATES = frozenset({0.25})\n", ["<source>:1: 0.25"]),
    ("RATE = 1\nRATE += 3\n", ["<source>:2: 3"]),
    ("x = [0, 1, 2]\ny = x[3]\n", ["<source>:2: 3"]),
    ("def f(x):\n    return x * 1e-6 + 3j\n", ["<source>:2: 1e-06", "<source>:2: 3j"]),   # float and complex
    ("def f(x):\n    return -0.5 * x\n", ["<source>:2: -0.5"]),                           # the sign is shown
    ("def f():\n    a = 7\n\n\n    return a + 19\n", ["<source>:2: 7", "<source>:5: 19"]),  # every line, in order
])
def test_scanner_reports_a_tuned_number_with_its_line(source, expected):
    assert tuned_numbers(source) == expected


@pytest.mark.parametrize("source", [
    "def f(x):\n    return -1 * x + 2 - 0 + 1\n",                                         # the structural numbers
    "def f(x):\n    return x[0], x[-1], x[1:2], -2\n",                                    # -2: read as rule G2 reads it
    "def f(x=True, y=False):\n    return x is True and y is not False\n",                 # a yes/no is not a number
    "def f(x):\n    return x * 0.0 + 1.0 - 2.0\n",                                        # equal to 0, 1, 2: as rule G2
    "G_MPS2 = 9.81\n",                                                                    # a named constant
    "G_MPS2: float = 9.81\n",
    "_SLOT = 7\n",
    "NEGATIVE = -9.81\n",
    "SLOTS = (3, 7)\nSIZES = [4, 8, 16]\nLIMITS = {'a': 5, 'b': [6, -7], 3: (0.5,)}\n",   # inside a plain literal
    "A = B = 6.5\n",
    '"""Module docstring: 19 GPU-h, 0.5 m/s."""\n\n\ndef f():\n    """Returns 3.5."""\n    return 1  # 42, not 43\n',
    "NAME = 'L0.11'\nTEXT = f'{NAME}: 3.0 and {1:>7}'\n",                                 # digits in text
    "",
])
def test_scanner_allows_structural_numbers_named_constants_and_text(source):
    assert tuned_numbers(source) == []


def test_scan_names_the_file_and_refuses_an_empty_or_moved_folder(tmp_path):
    with pytest.raises(AssertionError, match=r"found 0 \.py file"):
        scan(tmp_path)                                                # an empty folder is not a pass
    with pytest.raises(AssertionError, match=r"found 0 \.py file"):
        scan(tmp_path / "moved_away")
    (tmp_path / "__init__.py").write_text('"""A package."""\n')
    with pytest.raises(AssertionError, match=r"found 1 \.py file.*config\.py"):
        scan(tmp_path)                                                # one file of the two
    (tmp_path / "config.py").write_text("LIMIT = 0.5\n\n\ndef f():\n    return 1\n")
    assert scan(tmp_path) == []
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "learner.py").write_text("def step(x):\n    return x * 0.99\n")   # a sub-package is scanned too
    (tmp_path / "config.py").write_text("LIMIT = 0.5\n\n\ndef f():\n    return 3e-4\n")
    assert scan(tmp_path) == ["config.py:5: 0.0003", "sub/learner.py:2: 0.99"]
