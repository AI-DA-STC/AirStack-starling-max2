"""STE learning track, task L0.1: the track's settings file (configs/ste_learning.toml) and its loader (ste/config.py).

L0.1 holds process settings only: which plan and phase, and the GPU-hour caps of phase L0. Game settings arrive with the
tasks that build them (L0.8 onwards), so there is no "defaults reproduce today's game" test here yet.
"""
import dataclasses
import hashlib
import math
import re
import subprocess
import sys
import tomllib
from fractions import Fraction
from pathlib import Path

import pytest

from svg_training.ste.config import (
    SETTINGS_FILE, TASK_IDS, BudgetCfg, Provenance, SteLearningCfg, TrackCfg, load_ste_learning)

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "ste_learning" / "PLAN.md"

# The numbers of ste_learning/PLAN.md section 4 (version 2), typed here once more: a change to the file is then seen.
L0_PHASE_CAP_GPU_H = 19.0          # the owner's approval of 20 Nov 2026
L0_TASK_CAP_GPU_H = {"L0.1": 0.0, "L0.7": 0.0, "L0.8": 0.0, "L0.9": 0.0, "L0.10": 0.0, "L0.11": 0.5, "L0.12": 13.0,
                     "L0.2": 0.4, "L0.13": 1.6, "L0.3": 1.3, "L0.4": 0.2, "L0.5": 0.3, "L0.14": 0.0, "L0.6": 0.0}

GOOD = SETTINGS_FILE.read_text()


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "ste_learning.toml"
    path.write_text(text)
    return path


def changed(tmp_path: Path, old: str, new: str) -> Path:
    """A copy of the committed file with one piece of text replaced (the piece must be there exactly once)."""
    assert GOOD.count(old) == 1, old
    return write(tmp_path, GOOD.replace(old, new))


def settings_text(phase_cap: str, caps: dict[str, str]) -> str:
    """A settings file for phase L0 with the given phase cap; a task not in ``caps`` gets 0.0 GPU-hours."""
    lines = ["[track]", "plan_version = 2", 'phase = "L0"', "[budget]", f"phase_cap_gpu_h = {phase_cap}",
             "[budget.task_cap_gpu_h]"]
    return "\n".join(lines + [f'"{task}" = {caps.get(task, "0.0")}' for task in TASK_IDS["L0"]]) + "\n"


# ------------------------------------------------------------------------------------------------ the committed file
def test_committed_file_loads_with_the_plans_numbers():
    cfg, provenance = load_ste_learning()
    assert isinstance(cfg, SteLearningCfg) and isinstance(provenance, Provenance)
    assert cfg.track == TrackCfg(plan_version=2, phase="L0")
    assert cfg.budget.phase_cap_gpu_h == L0_PHASE_CAP_GPU_H and type(cfg.budget.phase_cap_gpu_h) is float
    assert cfg.budget.task_cap_gpu_h == tuple(L0_TASK_CAP_GPU_H.items())          # same tasks, same order, same caps
    assert all(type(cap) is float for _, cap in cfg.budget.task_cap_gpu_h)
    assert cfg.budget.cap_gpu_h("L0.11") == 0.5 and cfg.budget.cap_gpu_h("L0.4") == 0.2
    with pytest.raises(KeyError, match="L0.99"):
        cfg.budget.cap_gpu_h("L0.99")
    assert load_ste_learning(SETTINGS_FILE) == (cfg, provenance)
    assert SETTINGS_FILE == ROOT / "configs" / "ste_learning.toml"


def test_l01_holds_process_settings_only():
    """No game section before the task that builds it (L0.8 creates configs/ste_game.toml; L0.9 adds [tag])."""
    assert set(tomllib.loads(GOOD)) == {"track", "budget"}
    assert [f.name for f in dataclasses.fields(SteLearningCfg)] == ["track", "budget"]


def test_task_caps_fit_the_phase_cap_and_none_is_negative():
    budget = load_ste_learning()[0].budget
    caps = [cap for _, cap in budget.task_cap_gpu_h]
    assert all(cap >= 0.0 for cap in caps)
    assert budget.task_caps_total_gpu_h() <= budget.phase_cap_gpu_h              # the loader compares in decimal
    assert budget.task_caps_total_gpu_h() == math.fsum(L0_TASK_CAP_GPU_H.values()) < L0_PHASE_CAP_GPU_H


# ------------------------------------------------------------------------------------------------ against PLAN.md
# Each helper takes PLAN.md's text, so the checks can be tried on a made-up plan too. Every assertion says what was
# expected and where in PLAN.md it looked: the parsing is strict on purpose, and a failure must be readable.
SETTINGS = "configs/ste_learning.toml"


def plan_section(text: str, number: int) -> str:
    """Section ``number`` of PLAN.md: from its heading line "## <number>. " up to the next section's heading line."""
    start, end = text.find(f"\n## {number}. "), text.find(f"\n## {number + 1}. ")
    assert start != -1 and end > start, (
        f"PLAN.md: expected a heading line starting '## {number}. ' and, after it, one starting '## {number + 1}. ' "
        f"(section {number} holds the phase's task table and its budget sentence); found '## {number}. ': "
        f"{'yes' if start != -1 else 'no'}, '## {number + 1}. ' after it: {'yes' if end > start else 'no'}")
    return text[start:end]


def plan_task_rows(text: str) -> list[tuple[str, float]]:
    """(task ID, GPU-h cap) of every row of the task table in PLAN.md section 4, in the table's order."""
    rows = []
    for line in plan_section(text, 4).splitlines():
        if re.match(r"\| L\d+\.\d+ \|", line):
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            assert len(cells) == 5, (
                f"PLAN.md section 4, task table, row {cells[0]}: expected 5 cells (ID | Plain name | What it "
                f"delivers | GPU-h cap | Gate), found {len(cells)}; the row starts {line[:80]!r}")
            assert re.fullmatch(r"\d+(\.\d+)?", cells[3]), (
                f"PLAN.md section 4, task table, row {cells[0]}: expected a plain number of GPU-hours in the 4th cell "
                f"(GPU-h cap), found {cells[3]!r}")
            rows.append((cells[0], float(cells[3])))
    return rows


def check_plan_tasks(text: str, task_cap_gpu_h: tuple[tuple[str, float], ...]) -> None:
    """The task table of PLAN.md section 4 lists the same task IDs, in the same order, with the same caps."""
    rows = plan_task_rows(text)
    plan_ids, file_ids = [task for task, _ in rows], [task for task, _ in task_cap_gpu_h]
    assert plan_ids == file_ids, (
        f"PLAN.md section 4, task table (lines starting '| L<phase>.<n> |'): expected the {len(file_ids)} task IDs of "
        f"{SETTINGS} [budget.task_cap_gpu_h] in the same order, {file_ids}; found {len(plan_ids)}: {plan_ids}")
    differ = {task: {"file": cap, "PLAN.md": plan_cap} for (task, cap), (_, plan_cap) in zip(task_cap_gpu_h, rows)
              if cap != plan_cap}
    assert not differ, (f"PLAN.md section 4, task table, 4th cell (GPU-h cap): expected the caps of {SETTINGS} "
                        f"[budget.task_cap_gpu_h]; these differ: {differ}")


def plan_header_version(text: str) -> str:
    """The version written in PLAN.md's first line, as text ("2", or "2.1" if someone writes that)."""
    header = text.splitlines()[0] if text else ""
    found = re.search(r"\bversion (\d+(?:\.\d+)*)", header)
    assert found, f"PLAN.md line 1: expected the words 'version <number>' (the plan's version), found {header[:120]!r}"
    return found.group(1)


def check_plan_version(text: str, plan_version: int) -> None:
    version = plan_header_version(text)
    assert version == str(plan_version), (
        f"PLAN.md line 1 says 'version {version}'; expected 'version {plan_version}', the whole number of "
        f"{SETTINGS} [track] plan_version = {plan_version}")


def plan_budget_sentence(text: str, phase: str) -> tuple[str, str | None]:
    """(phase cap, sum of the task caps or None) as written in the budget sentence of PLAN.md section 4:
    "**L0 budget: at most 19 GPU-h** (the task caps above sum to <number>), ..."; the sum is looked for in the same
    paragraph, after the words "sum to"."""
    found = re.search(rf"\*\*{re.escape(phase)} budget: at most (\d+(?:\.\d+)?) GPU-h\*\*((?:[^\n]|\n(?!\n))*)",
                      plan_section(text, 4))
    assert found, (f"PLAN.md section 4: expected the budget sentence '**{phase} budget: at most <number> GPU-h**' "
                   f"(the phase cap, with the two asterisks on each side); found no such sentence")
    total = re.search(r"\bsum to (\d+(?:\.\d+)?)", found.group(2))
    return found.group(1), total.group(1) if total else None


def check_plan_budget(text: str, phase: str, phase_cap_gpu_h: float, task_caps_total_gpu_h: float) -> None:
    cap, total = plan_budget_sentence(text, phase)
    assert float(cap) == phase_cap_gpu_h, (
        f"PLAN.md section 4, budget sentence, says '{phase} budget: at most {cap} GPU-h'; expected "
        f"{phase_cap_gpu_h!r}, the value of {SETTINGS} [budget] phase_cap_gpu_h")
    assert total is None or float(total) == task_caps_total_gpu_h, (
        f"PLAN.md section 4, budget sentence, says the task caps 'sum to {total}'; expected {task_caps_total_gpu_h!r}, "
        f"the sum of {SETTINGS} [budget.task_cap_gpu_h]")


def test_task_ids_and_caps_are_those_of_plan_section_4():
    cfg, _ = load_ste_learning()
    check_plan_tasks(PLAN.read_text(), cfg.budget.task_cap_gpu_h)
    file_order = list(tomllib.loads(GOOD)["budget"]["task_cap_gpu_h"])
    assert file_order == list(TASK_IDS[cfg.track.phase]) == [task for task, _ in cfg.budget.task_cap_gpu_h], (
        f"the task IDs are written in three places that must agree in order: the lines of {SETTINGS} {file_order}, "
        f"TASK_IDS in ste/config.py {list(TASK_IDS[cfg.track.phase])}, and PLAN.md section 4 (checked just above)")


def test_plan_version_is_the_one_in_the_plans_header():
    check_plan_version(PLAN.read_text(), load_ste_learning()[0].track.plan_version)


def test_phase_cap_and_task_cap_sum_are_those_of_the_plans_budget_sentence():
    cfg, _ = load_ste_learning()
    text = PLAN.read_text()
    check_plan_budget(text, cfg.track.phase, cfg.budget.phase_cap_gpu_h, cfg.budget.task_caps_total_gpu_h())
    cap, total = plan_budget_sentence(text, cfg.track.phase)
    assert float(cap) == L0_PHASE_CAP_GPU_H, (
        f"PLAN.md section 4, budget sentence, says 'at most {cap} GPU-h'; expected {L0_PHASE_CAP_GPU_H!r}, the owner's "
        f"cap typed as L0_PHASE_CAP_GPU_H at the top of this test file")


def made_up_plan(task_cap_gpu_h: tuple[tuple[str, float], ...], version: str = "2", cap: str = "19",
                 total: str | None = "") -> str:
    """A small text with the parts of PLAN.md the checks read: line 1, the section 4 table and budget sentence.
    ``total``: the sum the sentence states; "" = the sum of the given caps, None = the sentence states no sum."""
    rows = [f"| {task} | a name | what it delivers | {task_cap:g} | none |" for task, task_cap in task_cap_gpu_h]
    total = f"{float(sum(Fraction(repr(task_cap)) for _, task_cap in task_cap_gpu_h)):g}" if total == "" else total
    budget = f"**L0 budget: at most {cap} GPU-h**" + (f" (the task caps above sum to {total})," if total else ",")
    return "\n".join([f"INTERNAL · the master plan, version {version} (20 Nov 2026).", "", "# PLAN", "",
                      "## 4. Phase L0 in detail", "", "| ID | Plain name | What it delivers | GPU-h cap | Gate |",
                      "|---|---|---|---|---|", *rows, "", budget, "alone on the GPU.", "", "## 5. Gate G0", ""])


def test_the_plan_checks_refuse_a_plan_that_differs_and_say_where():
    cfg, _ = load_ste_learning()
    caps, phase = cfg.budget.task_cap_gpu_h, cfg.track.phase
    cap, total = cfg.budget.phase_cap_gpu_h, cfg.budget.task_caps_total_gpu_h()
    good = made_up_plan(caps)
    check_plan_tasks(good, caps), check_plan_version(good, 2), check_plan_budget(good, phase, cap, total)
    check_plan_budget(made_up_plan(caps, total=None), phase, cap, total)        # the sum is compared only if written

    def refused(match, check, text, *args):
        with pytest.raises(AssertionError, match=match):
            check(text, *args)

    # line 1: the version
    refused(r"line 1 says 'version 2\.1'; expected 'version 2'", check_plan_version, made_up_plan(caps, "2.1"), 2)
    refused(r"line 1 says 'version 3'; expected 'version 2'", check_plan_version, made_up_plan(caps, "3"), 2)
    refused(r"line 1 says 'version 12'; expected 'version 1'", check_plan_version, made_up_plan(caps, "12"), 1)
    refused(r"line 1: expected the words 'version <number>'", check_plan_version, good.replace("version 2", "v2"), 2)
    # section 4: the budget sentence
    refused(r"at most 20 GPU-h'; expected 19\.0", check_plan_budget, made_up_plan(caps, cap="20"), phase, cap, total)
    refused(rf"'sum to 77'; expected {re.escape(repr(total))}", check_plan_budget, made_up_plan(caps, total="77"),
            phase, cap, total)
    refused(r"section 4: expected the budget sentence '\*\*L0 budget: at most <number> GPU-h\*\*'", check_plan_budget,
            good.replace("**L0 budget: at most", "L0 budget: about"), phase, cap, total)
    # section 4: the task table
    without_a_row = "\n".join(line for line in good.splitlines() if not line.startswith("| L0.13 |"))
    refused(r"section 4, task table.*expected the 14 task IDs.*found 13", check_plan_tasks, without_a_row, caps)
    swapped = good.replace("| L0.1 |", "| L0.x |").replace("| L0.7 |", "| L0.1 |").replace("| L0.x |", "| L0.7 |")
    refused(r"in the same order", check_plan_tasks, swapped, caps)
    refused(r"4th cell \(GPU-h cap\).*these differ: \{'L0\.4': \{'file': 0\.2, 'PLAN\.md': 0\.25\}\}", check_plan_tasks,
            good.replace("| 0.2 | none |", "| 0.25 | none |"), caps)
    refused(r"row L0\.4: expected 5 cells .*found 4", check_plan_tasks,
            good.replace("| L0.4 | a name | what it delivers |", "| L0.4 | a name and what it delivers |"), caps)
    refused(r"row L0\.4: expected a plain number of GPU-hours in the 4th cell \(GPU-h cap\), found 'none'",
            check_plan_tasks, good.replace("| 0.2 | none |", "| none | none |"), caps)
    refused(r"expected a heading line starting '## 4\. '.*found '## 4\. ': no", check_plan_tasks,
            good.replace("## 4. Phase", "## Phase"), caps)
    refused(r"'## 5\. ' after it: no", check_plan_budget, good.replace("## 5. Gate", "## Gate"), phase, cap, total)


# ------------------------------------------------------------------------------------------------ unknown keys raise
def test_unknown_top_level_section_raises(tmp_path):
    with pytest.raises(ValueError, match=r"unknown section.*tag"):
        load_ste_learning(write(tmp_path, GOOD + "\n[tag]\nradius_m = 1.6\n"))
    with pytest.raises(ValueError, match=r"unknown section.*stray"):
        load_ste_learning(write(tmp_path, "stray = 1\n" + GOOD))           # a bare key above the first table


def test_unknown_key_in_a_section_raises(tmp_path):
    with pytest.raises(ValueError, match=r"unknown key.*\[track\].*owner"):
        load_ste_learning(changed(tmp_path, "[budget]\n", 'owner = "x"\n\n[budget]\n'))
    with pytest.raises(ValueError, match=r"unknown key.*\[budget\].*phase_cap_gpu_hours"):
        load_ste_learning(changed(tmp_path, "phase_cap_gpu_h = 19.0",
                                  "phase_cap_gpu_h = 19.0\nphase_cap_gpu_hours = 19.0"))


def test_unknown_task_id_raises(tmp_path):
    with pytest.raises(ValueError, match=r"unknown task ID.*L0\.99"):
        load_ste_learning(write(tmp_path, GOOD + '"L0.99" = 0.0\n'))
    with pytest.raises(ValueError, match=r"unknown task ID.*L1\.1"):
        load_ste_learning(changed(tmp_path, '"L0.6" =', '"L1.1" = 0.0\n"L0.6" ='))
    # without the quotes TOML reads L0.6 as a table "L0" holding a key "6": the message says to quote task IDs
    with pytest.raises(ValueError, match=r"unknown task ID.*\['L0'\].*in quotes") as unquoted:
        load_ste_learning(changed(tmp_path, '"L0.6" =', "L0.6 ="))
    assert '"L0.1" = 0.0' in str(unquoted.value)                                 # with an example line
    with pytest.raises(ValueError, match=r"unknown task ID.*\['L0'\].*in quotes"):
        load_ste_learning(write(tmp_path, GOOD.replace('"L0.', "L0.").replace('" = ', " = ")))   # every ID unquoted
    with pytest.raises(ValueError, match=r"unknown task ID.*L0\.99") as quoted:
        load_ste_learning(write(tmp_path, GOOD + '"L0.99" = 0.0\n'))
    assert "quotes" not in str(quoted.value)                                     # no hint where it does not apply


def test_a_file_that_cannot_be_read_as_toml_raises_naming_the_file(tmp_path):
    path = write(tmp_path, GOOD.replace("[budget]\n", "[budget\n"))             # a TOML syntax error
    with pytest.raises(ValueError, match=r"not valid TOML") as syntax:
        load_ste_learning(path)
    assert str(path) in str(syntax.value)
    path.write_bytes(GOOD.encode() + "# café\n".encode("latin-1"))               # not UTF-8
    with pytest.raises(ValueError, match=r"not UTF-8") as encoding:
        load_ste_learning(path)
    assert str(path) in str(encoding.value)


def test_missing_section_key_or_task_raises(tmp_path):
    track_only = GOOD[:GOOD.index("[budget]")]
    with pytest.raises(ValueError, match=r"missing section.*budget"):
        load_ste_learning(write(tmp_path, track_only))
    with pytest.raises(ValueError, match=r"missing key.*\[track\].*phase"):
        load_ste_learning(changed(tmp_path, 'phase = "L0"', "# phase removed"))
    with pytest.raises(ValueError, match=r"missing key.*\[budget\].*phase_cap_gpu_h"):
        load_ste_learning(changed(tmp_path, "phase_cap_gpu_h = 19.0", "# cap removed"))
    with pytest.raises(ValueError, match=r"missing task ID.*L0\.13"):
        load_ste_learning(changed(tmp_path, '"L0.13" =', '# "L0.13" ='))
    with pytest.raises(FileNotFoundError):
        load_ste_learning(tmp_path / "absent.toml")


def test_unknown_phase_raises(tmp_path):
    with pytest.raises(ValueError, match=r"track\.phase.*L1"):
        load_ste_learning(changed(tmp_path, 'phase = "L0"', 'phase = "L1"'))


# ------------------------------------------------------------------------------------------------ wrong types raise
@pytest.mark.parametrize("old, new, names", [
    ("plan_version = 2", 'plan_version = "2"', "track.plan_version"),
    ("plan_version = 2", "plan_version = 2.0", "track.plan_version"),
    ("plan_version = 2", "plan_version = true", "track.plan_version"),            # a TOML boolean is not a whole number
    ("plan_version = 2", "plan_version = 0", "track.plan_version"),
    ('phase = "L0"', "phase = 0", "track.phase"),
    ("phase_cap_gpu_h = 19.0", "phase_cap_gpu_h = 19", "budget.phase_cap_gpu_h"),  # caps are written as decimals
    ("phase_cap_gpu_h = 19.0", 'phase_cap_gpu_h = "19.0"', "budget.phase_cap_gpu_h"),
    ("phase_cap_gpu_h = 19.0", "phase_cap_gpu_h = true", "budget.phase_cap_gpu_h"),
    ("phase_cap_gpu_h = 19.0", "phase_cap_gpu_h = inf", "budget.phase_cap_gpu_h"),
    ("phase_cap_gpu_h = 19.0", "phase_cap_gpu_h = -19.0", "budget.phase_cap_gpu_h"),
    ('"L0.11" = 0.5', '"L0.11" = 3', r"budget.task_cap_gpu_h.*L0\.11"),
    ('"L0.11" = 0.5', '"L0.11" = "3.0"', r"budget.task_cap_gpu_h.*L0\.11"),
    ('"L0.11" = 0.5', '"L0.11" = false', r"budget.task_cap_gpu_h.*L0\.11"),
    ('"L0.11" = 0.5', '"L0.11" = [3.0]', r"budget.task_cap_gpu_h.*L0\.11"),
    ('"L0.11" = 0.5', '"L0.11" = nan', r"budget.task_cap_gpu_h.*L0\.11"),
    ('"L0.11" = 0.5', '"L0.11" = inf', r"budget.task_cap_gpu_h.*L0\.11"),
    ('"L0.11" = 0.5', '"L0.11" = -0.5', r"budget.task_cap_gpu_h.*L0\.11"),
])
def test_wrong_type_or_impossible_value_raises(tmp_path, old, new, names):
    with pytest.raises(ValueError, match=names):
        load_ste_learning(changed(tmp_path, old, new))


def test_a_section_that_is_not_a_table_raises(tmp_path):
    with pytest.raises(ValueError, match=r"\[track\].*table"):
        load_ste_learning(write(tmp_path, "track = 2\n" + GOOD[GOOD.index("[budget]"):]))
    head = GOOD[:GOOD.index("[budget.task_cap_gpu_h]")]
    with pytest.raises(ValueError, match=r"\[budget.task_cap_gpu_h\].*table"):
        load_ste_learning(write(tmp_path, head.replace("phase_cap_gpu_h = 19.0",
                                                       "phase_cap_gpu_h = 19.0\ntask_cap_gpu_h = 1.5")))


def test_task_caps_above_the_phase_cap_raise(tmp_path):
    with pytest.raises(ValueError, match=r"task caps.*phase cap"):
        load_ste_learning(changed(tmp_path, '"L0.11" = 0.5', '"L0.11" = 2.3'))    # one tenth of a GPU-hour over
    load_ste_learning(changed(tmp_path, '"L0.11" = 0.5', '"L0.11" = 2.2'))        # exactly the phase cap is allowed


def test_task_caps_are_added_and_compared_exactly_in_decimal(tmp_path):
    """0.1 + 0.2 is 0.3 in a settings file, though not in binary floating point (0.30000000000000004)."""
    def load(phase_cap, caps):
        return load_ste_learning(write(tmp_path, settings_text(phase_cap, caps)))[0].budget

    budget = load("0.3", {"L0.11": "0.1", "L0.12": "0.2"})                       # equal to the phase cap: allowed
    assert budget.phase_cap_gpu_h == 0.3 and budget.task_caps_total_gpu_h() == 0.3
    assert load("0.3", {"L0.11": "0.1", "L0.12": "0.1", "L0.13": "0.1"}).task_caps_total_gpu_h() == 0.3
    assert load("3.3", {"L0.11": "1.1", "L0.12": "2.2"}).task_caps_total_gpu_h() == 3.3
    with pytest.raises(ValueError, match=r"task caps add up to 0\.31 GPU-hours.*phase cap.*0\.3\b"):
        load("0.3", {"L0.11": "0.11", "L0.12": "0.2"})
    # the other direction: in decimal 0.1 + 0.7 = 0.8 is more than this cap; the binary sum equals the cap exactly
    assert math.fsum([0.1, 0.7]) == 0.7999999999999999
    with pytest.raises(ValueError, match=r"task caps add up to 0\.8 GPU-hours"):
        load("0.7999999999999999", {"L0.11": "0.1", "L0.12": "0.7"})
    assert load("1e-07", {"L0.11": "3e-08", "L0.12": "7e-08"}).task_caps_total_gpu_h() == 1e-07   # small values too


# ------------------------------------------------------------------------------------------------ status labels
LABELS = ("FIXED", "MEASURED", "PROPOSED", "OPEN")       # ../STANDARDS.md (the table under the title)


def split_comment(line: str) -> tuple[str, str]:
    """(code, comment) of one TOML line: the comment starts at the first # outside a "basic string"."""
    in_string = False
    for i, char in enumerate(line):
        if char == '"' and (i == 0 or line[i - 1] != "\\"):
            in_string = not in_string
        elif char == "#" and not in_string:
            return line[:i].strip(), line[i + 1:].strip()
    return line.strip(), ""


def value_lines(text: str) -> list[tuple[int, str, str]]:
    """(line number, code, comment) of every line that sets a value: not blank, not a comment, not a [table] header."""
    out = []
    for number, line in enumerate(text.splitlines(), start=1):
        code, comment = split_comment(line)
        if code and not code.startswith("["):
            assert re.match(r'("[^"]+"|[A-Za-z0-9_-]+)\s*=\s*\S', code), f"line {number} is not 'key = value': {line!r}"
            out.append((number, code, comment))
    return out


def unlabelled(text: str) -> list[int]:
    """Line numbers of value lines whose comment does not start with a status label followed by its source."""
    labelled = re.compile(rf"({'|'.join(LABELS)})\b\s*[(:]\s*\S")
    return [number for number, _, comment in value_lines(text) if not labelled.match(comment)]


def leaves(table: dict) -> int:
    return sum(leaves(v) if isinstance(v, dict) else 1 for v in table.values())


def test_every_value_line_carries_a_status_label_and_source():
    lines = value_lines(GOOD)
    assert len(lines) == leaves(tomllib.loads(GOOD)) == 3 + len(L0_TASK_CAP_GPU_H)   # one value per line, none skipped
    assert unlabelled(GOOD) == []


def test_the_label_check_fails_a_line_without_a_label():
    sample = "\n".join([
        "# a comment line and a header are not value lines",
        "[budget]",
        "a = 1.0   # FIXED (owner, 20 Nov 2026): labelled",
        "b = 1.0",                                             # line 4: no comment
        "c = 1.0   # the cap of the phase",                    # line 5: a comment without a label
        'd = "FIXED (owner)"',                                 # line 6: the label is in the value, not in a comment
        'e = "#"   # PROPOSED: a hash inside the value does not start the comment',
        "f = 1.0   # see PROPOSED (lead) below",               # line 8: the label does not lead the comment
        "g = 1.0   # OPEN",                                    # line 9: a label without a source
        "h = 1.0   # FIXEDISH (owner)",                        # line 10: not one of the four labels
        "i = 1.0   # MEASURED: records/x.md",
        "j = 1.0   # OPEN (owner + NUS): no value yet",
    ])
    assert unlabelled(sample) == [4, 5, 6, 8, 9, 10]
    for number, code, _ in value_lines(GOOD):                  # the committed file with one line's comment taken away
        lines = GOOD.splitlines()
        lines[number - 1] = code
        assert unlabelled("\n".join(lines)) == [number]


# ------------------------------------------------------------------------------------------------ frozen
def test_dataclasses_are_frozen():
    cfg, provenance = load_ste_learning()
    for obj, name, value in ((cfg, "track", cfg.track), (cfg.track, "phase", "L1"), (cfg.track, "plan_version", 3),
                             (cfg.budget, "phase_cap_gpu_h", 100.0), (cfg.budget, "task_cap_gpu_h", ()),
                             (provenance, "settings_sha256", "0")):
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(obj, name, value)
    with pytest.raises(TypeError):                              # the caps are a tuple of pairs: no item can be set
        cfg.budget.task_cap_gpu_h[0] = ("L0.1", 100.0)
    with pytest.raises(TypeError):
        cfg.budget.task_cap_gpu_h[0][1] = 100.0
    assert hash(cfg) == hash(load_ste_learning()[0])            # nothing mutable inside
    for cls in (TrackCfg, BudgetCfg, SteLearningCfg, Provenance):
        assert cls.__dataclass_params__.frozen
        assert all(f.default is dataclasses.MISSING and f.default_factory is dataclasses.MISSING
                   for f in dataclasses.fields(cls)), cls      # no number lives in the code: the file is the one source


# ------------------------------------------------------------------------------------------------ content hash
def test_hash_is_the_files_sha256_stable_and_changes_with_the_content(tmp_path):
    cfg, provenance = load_ste_learning()
    assert provenance.settings_sha256 == hashlib.sha256(SETTINGS_FILE.read_bytes()).hexdigest()
    assert provenance.settings_file == str(SETTINGS_FILE)
    assert load_ste_learning()[1] == provenance                                 # stable from load to load
    copy_cfg, copy_provenance = load_ste_learning(write(tmp_path, GOOD))
    assert copy_provenance.settings_sha256 == provenance.settings_sha256        # same bytes elsewhere, same hash
    assert copy_provenance.settings_file == str(tmp_path / "ste_learning.toml")
    note_cfg, note_provenance = load_ste_learning(write(tmp_path, GOOD + "# a note\n"))
    assert note_provenance.settings_sha256 != provenance.settings_sha256        # any change of the bytes changes it
    assert note_cfg == cfg == copy_cfg                                          # though the values are the same
    value_cfg, value_provenance = load_ste_learning(changed(tmp_path, '"L0.4" = 0.2', '"L0.4" = 0.1'))
    assert value_provenance.settings_sha256 != provenance.settings_sha256 and value_cfg != cfg


# ------------------------------------------------------------------------------------------------ the package
def test_package_imports_on_the_cpu_without_torch_or_isaac():
    code = ("import sys; before = set(sys.modules); import svg_training.ste, svg_training.ste.config as c; "
            "c.load_ste_learning(); new = {m.split('.')[0] for m in set(sys.modules) - before}; "
            "print(sorted(new & {'torch', 'numpy', 'isaaclab', 'isaacsim', 'omni', 'pxr'}))")
    run = subprocess.run([sys.executable, "-B", "-c", code], capture_output=True, text=True,   # -B: no __pycache__
                         env={"PYTHONPATH": str(ROOT / "source"), "CUDA_VISIBLE_DEVICES": ""})
    assert run.returncode == 0, run.stderr
    assert run.stdout.strip() == "[]"
