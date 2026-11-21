"""A Recording survives save_recording / load_recording (scripts/nus_selfplay_train.py), with and without the height band
the L0.12 height panel added (None must not become an object array that np.load refuses)."""
import dataclasses
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
spec = importlib.util.spec_from_file_location("nus_selfplay_train", ROOT / "scripts" / "nus_selfplay_train.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
from svg_training.viz.replay import Recording  # noqa: E402


def _rec(band):
    t, m = 5, 3
    return Recording(np.zeros((t, m, 3), np.float32), np.ones((t, m), bool), np.zeros(2), 1.6, 3.25, 1, 4, 2, 1,
                     "flat", "nus", "g", "s", 7, 0, 1.5, band)


@pytest.mark.parametrize("band", [None, (0.5, 1.8)])
def test_recording_round_trip(tmp_path, band):
    rec = _rec(band)
    back = mod.load_recording(mod.save_recording(rec, tmp_path / "r.npz"))
    assert back.height_band_m == band
    for f in dataclasses.fields(Recording):
        if f.name != "height_band_m":
            assert np.array_equal(np.asarray(getattr(back, f.name)), np.asarray(getattr(rec, f.name)))
