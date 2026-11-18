"""make_nus_phase4_figures.py refuses (exit 2, naming the missing rows) when a ladder row's scores.json is absent, and leaves the
committed figure alone (docs panel C7, owner 18 Nov 2026: on a fresh clone it used to overwrite docs/figures/nus_phase4_ladder.png
with empty axes and exit 0)."""
import importlib.util
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _script():
    spec = importlib.util.spec_from_file_location("_phase4_fig", ROOT / "scripts" / "make_nus_phase4_figures.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_refuses_on_missing_rows_and_keeps_the_figure(tmp_path, monkeypatch, capsys):
    fig = _script()
    out = tmp_path / "figure.png"
    out.write_bytes(b"committed figure")
    monkeypatch.setattr(fig, "OUT", out)
    monkeypatch.setattr(fig.L, "PHASE4_DIR", tmp_path / "phase4")
    order = fig.H.load_phase4()["figure"]["row_order"]
    (tmp_path / "phase4" / f"row_{order[0]}").mkdir(parents=True)
    (tmp_path / "phase4" / f"row_{order[0]}" / "scores.json").write_text(json.dumps({"pairs": []}))
    assert fig.main() == 2
    assert out.read_bytes() == b"committed figure"
    err = capsys.readouterr().err
    assert f"row_{order[-1]}/scores.json" in err and f"row_{order[0]}/scores.json" not in err
    assert "refus" in err
