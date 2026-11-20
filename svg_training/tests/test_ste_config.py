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
from pathlib import Path

import pytest

from svg_training.ste.config import (
    SETTINGS_FILE, TASK_IDS, BudgetCfg, Provenance, SteLearningCfg, TrackCfg, load_ste_learning)

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "ste_learning" / "PLAN.md"

# The numbers of ste_learning/PLAN.md section 4 (version 2), typed here once more: a change to the file is then seen.
L0_PHASE_CAP_GPU_H = 19.0          # the owner's approval of 20 Nov 2026
L0_TASK_CAP_GPU_H = {"L0.1": 0.0, "L0.7": 0.0, "L0.8": 0.0, "L0.9": 0.0, "L0.10": 0.0, "L0.11": 3.0, "L0.12": 6.0,
                     "L0.2": 1.5, "L0.13": 6.0, "L0.3": 1.5, "L0.4": 0.2, "L0.5": 0.3, "L0.6": 0.0}

GOOD = SETTINGS_FILE.read_text()


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "ste_learning.toml"
    path.write_text(text)
    return path


def changed(tmp_path: Path, old: str, new: str) -> Path:
    """A copy of the committed file with one piece of text replaced (the piece must be there exactly once)."""
    assert GOOD.count(old) == 1, old
    return write(tmp_path, GOOD.replace(old, new))


# ------------------------------------------------------------------------------------------------ the committed file
def test_committed_file_loads_with_the_plans_numbers():
    cfg, provenance = load_ste_learning()
    assert isinstance(cfg, SteLearningCfg) and isinstance(provenance, Provenance)
    assert cfg.track == TrackCfg(plan_version=2, phase="L0")
    assert cfg.budget.phase_cap_gpu_h == L0_PHASE_CAP_GPU_H and type(cfg.budget.phase_cap_gpu_h) is float
    assert cfg.budget.task_cap_gpu_h == tuple(L0_TASK_CAP_GPU_H.items())          # same tasks, same order, same caps
    assert all(type(cap) is float for _, cap in cfg.budget.task_cap_gpu_h)
    assert cfg.budget.cap_gpu_h("L0.11") == 3.0 and cfg.budget.cap_gpu_h("L0.4") == 0.2
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
    assert math.fsum(caps) <= budget.phase_cap_gpu_h
    assert budget.task_caps_total_gpu_h() == math.fsum(L0_TASK_CAP_GPU_H.values()) < L0_PHASE_CAP_GPU_H


# ------------------------------------------------------------------------------------------------ against PLAN.md
def plan_l0_rows() -> list[tuple[str, float]]:
    """(task ID, GPU-h cap) of every row of the table in PLAN.md section 4, in the table's order."""
    text = PLAN.read_text()
    section = text[text.index("\n## 4. "):text.index("\n## 5. ")]
    rows = []
    for line in section.splitlines():
        if re.match(r"\| L\d+\.\d+ \|", line):
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            assert len(cells) == 5, line          # ID | Plain name | What it delivers | GPU-h cap | Gate
            rows.append((cells[0], float(cells[3])))
    return rows


def test_task_ids_and_caps_are_those_of_plan_section_4():
    rows = plan_l0_rows()
    assert len(rows) == len(L0_TASK_CAP_GPU_H)                       # the parser found the table
    cfg, _ = load_ste_learning()
    assert [task for task, _ in cfg.budget.task_cap_gpu_h] == [task for task, _ in rows]
    assert TASK_IDS[cfg.track.phase] == tuple(task for task, _ in rows)
    assert list(tomllib.loads(GOOD)["budget"]["task_cap_gpu_h"]) == [task for task, _ in rows]   # the file's own order
    assert dict(cfg.budget.task_cap_gpu_h) == dict(rows)


def test_plan_version_is_the_one_in_the_plans_header():
    header = PLAN.read_text().splitlines()[0]
    found = re.search(r"\bversion (\d+)\b", header)
    assert found, header
    assert load_ste_learning()[0].track.plan_version == int(found.group(1))


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
    # without the quotes TOML reads L0.6 as a table "L0" holding a key "6"
    with pytest.raises(ValueError, match=r"unknown task ID.*L0"):
        load_ste_learning(changed(tmp_path, '"L0.6" =', "L0.6 ="))


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
    ('"L0.11" = 3.0', '"L0.11" = 3', r"budget.task_cap_gpu_h.*L0\.11"),
    ('"L0.11" = 3.0', '"L0.11" = "3.0"', r"budget.task_cap_gpu_h.*L0\.11"),
    ('"L0.11" = 3.0', '"L0.11" = false', r"budget.task_cap_gpu_h.*L0\.11"),
    ('"L0.11" = 3.0', '"L0.11" = [3.0]', r"budget.task_cap_gpu_h.*L0\.11"),
    ('"L0.11" = 3.0', '"L0.11" = nan', r"budget.task_cap_gpu_h.*L0\.11"),
    ('"L0.11" = 3.0', '"L0.11" = inf', r"budget.task_cap_gpu_h.*L0\.11"),
    ('"L0.11" = 3.0', '"L0.11" = -0.5', r"budget.task_cap_gpu_h.*L0\.11"),
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
        load_ste_learning(changed(tmp_path, '"L0.11" = 3.0', '"L0.11" = 3.6'))    # one tenth of a GPU-hour over
    load_ste_learning(changed(tmp_path, '"L0.11" = 3.0', '"L0.11" = 3.5'))        # exactly the phase cap is allowed


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
    run = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                         env={"PYTHONPATH": str(ROOT / "source"), "CUDA_VISIBLE_DEVICES": ""})
    assert run.returncode == 0, run.stderr
    assert run.stdout.strip() == "[]"
