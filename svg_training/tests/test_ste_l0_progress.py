"""The phase-L0 progress figure: its state file (ste_learning/status/l0_progress.toml) and the drawing script."""
import importlib.util
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "ste_learning" / "PLAN.md"
SCRIPT = ROOT / "scripts" / "make_ste_learning_figures.py"

spec = importlib.util.spec_from_file_location("make_ste_learning_figures", SCRIPT)
figs = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = figs
spec.loader.exec_module(figs)


def plan_l0_ids() -> list[str]:
    """Task IDs of the table in PLAN.md section 4 (rows starting '| L0.<n> |')."""
    text = PLAN.read_text()
    start, end = text.find("\n## 4. "), text.find("\n## 5. ")
    assert 0 < start < end, "PLAN.md: expected headings '## 4. ' and '## 5. '"
    return re.findall(r"^\| (L0\.\d+) \|", text[start:end], flags=re.M)


def good_text() -> str:
    return figs.PROGRESS_FILE.read_text()


def write(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "l0_progress.toml"
    p.write_text(text)
    return p


def test_committed_file_parses_with_numbers():
    data = figs.load_l0_progress()
    assert data["gpu_h_cap"] == 19.0 and 0 <= data["gpu_h_used"] <= data["gpu_h_cap"]
    assert all(t["state"] in figs.STATES for t in data["tasks"].values())


def test_every_plan_task_has_exactly_one_state():
    ids = plan_l0_ids()
    assert len(ids) == 14 and len(set(ids)) == 14, ids
    assert sorted(figs.load_l0_progress()["tasks"]) == sorted(ids)
    assert sorted(figs.L0_IDS) == sorted(ids)


def test_unknown_state_is_refused(tmp_path):
    with pytest.raises(ValueError, match="unknown state 'finished'"):
        figs.load_l0_progress(write(tmp_path, good_text().replace('"running"', '"finished"', 1)))


def test_unknown_task_id_is_refused(tmp_path):
    with pytest.raises(ValueError, match="unknown task ID 'L0.99'"):
        figs.load_l0_progress(write(tmp_path, good_text() + '[tasks."L0.99"]\nstate = "done"\n'))


def test_missing_task_is_refused(tmp_path):
    text, n = re.subn(r'\[tasks\."L0\.5"\]\nstate = "[a-z_]+"\n', "", good_text())
    assert n == 1   # the block is removed whatever L0.5's live state is
    with pytest.raises(ValueError, match="no state for L0.5"):
        figs.load_l0_progress(write(tmp_path, text))


def test_figure_renders_to_a_temp_path(tmp_path, monkeypatch):
    monkeypatch.setattr(figs, "OUT", tmp_path)
    path = figs.l0_progress()
    assert path == tmp_path / "l0_progress.png" and path.stat().st_size > 10_000
