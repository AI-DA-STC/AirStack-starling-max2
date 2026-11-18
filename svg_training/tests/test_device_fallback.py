"""--device auto (the default of score.py and train_standin.py): CUDA when PyTorch sees a GPU, else the CPU with a printed note.
A plain laptop without an NVIDIA GPU runs both scripts without editing the command line (docs panel C1/C2, owner 18 Nov 2026)."""
import importlib.util
import pathlib
import sys

import pytest
import torch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
from svg_training.devices import resolve_device  # noqa: E402


def _script(name):
    spec = importlib.util.spec_from_file_location(f"_dev_{name}", ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_auto_falls_back_to_cpu_with_a_note(monkeypatch, capsys):
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    assert resolve_device("auto") == "cpu"
    err = capsys.readouterr().err
    assert "no CUDA GPU" in err and "cpu" in err


def test_auto_picks_cuda_when_available(monkeypatch, capsys):
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    assert resolve_device("auto") == "cuda"
    assert capsys.readouterr().err == ""


def test_explicit_device_is_kept(monkeypatch):
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    assert resolve_device("cpu") == "cpu"
    assert resolve_device("cuda:1") == "cuda:1"       # an explicit choice is never changed; torch refuses it later if absent


@pytest.mark.parametrize("name", ["score", "train_standin"])
def test_default_is_auto(name):
    ap = _script(name).make_parser()
    assert ap.get_default("device") == "auto"
    assert "auto" in ap.format_help()


def test_score_physics_treats_auto_as_cuda():
    """--presets physics with the default device is not refused for the device (auto means the GPU there); cpu still is."""
    score = _script("score")
    base = ["--presets", "physics", "--sizes", "2v1", "--headless", "--batch-per-pair"]
    assert score.physics_problem(base) is None
    assert "cuda" in score.physics_problem(base + ["--device", "cpu"])


def test_score_auto_runs_on_cpu_without_gpu(monkeypatch, tmp_path):
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    score = _script("score")
    out = tmp_path / "o"
    assert score.main(["--guard", "zero", "--strike", "zero", "--sizes", "2v1", "--presets", "pure", "--bands", "lab",
                       "--no-local", "--games-per-band", "2", "--out", str(out)]) == 0
    import json
    assert json.loads((out / "scores.json").read_text())["meta"]["device"] == "cpu"
