"""The L0.12c figure script reads curve.json and verdict.json as the driver writes them, and writes the PNG and CSV."""
import csv
import json
import sys

from _ste_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import make_ste_l012c_figure as fig  # noqa: E402


def run_dir(tmp_path, name, reads):
    d = tmp_path / name
    d.mkdir()
    (d / "curve.json").write_text(json.dumps([{"update": 10 * (i + 1), "game_steps": 62_914_560 * (i + 1), "k": k,
                                               "n": 256} for i, k in enumerate(reads)]))
    (d / "results.json").write_text(json.dumps({"game_steps": 62_914_560 * (len(reads) + 1)}))
    return d


def verdict(tmp_path, side, trained, script):
    p = tmp_path / f"{side}.json"
    gain = {"trained": {"k": trained, "n": 1000, "rate": trained / 1000, "ci": [trained / 1000 - 0.03, trained / 1000 + 0.03]},
            "script": {"k": script, "n": 1000, "rate": script / 1000, "ci": [script / 1000 - 0.03, script / 1000 + 0.03]}}
    p.write_text(json.dumps({"variants": {"tag_1p15": {"sides": {side: {"gain": gain}}}}}))
    return p


def test_curve_and_result_are_read_as_the_driver_writes_them(tmp_path):
    d = run_dir(tmp_path, "g", [38, 46])
    assert fig.curve(d) == [(62_914_560 / 1e9, 38 / 256), (2 * 62_914_560 / 1e9, 46 / 256)]
    r = fig.side_result(verdict(tmp_path, "guard", 572, 645), "guard")
    assert r["trained"][0] == 0.572 and r["script"][0] == 0.645
    assert fig.final_steps(d) == 3 * 62_914_560 / 1e9                  # the final point sits where training ended


def test_main_writes_the_png_and_every_curve_read_to_the_csv(tmp_path):
    out, table = tmp_path / "f.png", tmp_path / "c.csv"
    code = fig.main(["--guard-short", str(run_dir(tmp_path, "gs", [38, 46])),
                     "--guard-long", str(run_dir(tmp_path, "gl", [37, 46, 52])),
                     "--strike-short", str(run_dir(tmp_path, "ss", [17])),
                     "--strike-long", str(run_dir(tmp_path, "sl", [7, 17])),
                     "--guard-verdict", str(verdict(tmp_path, "guard", 572, 645)),
                     "--strike-verdict", str(verdict(tmp_path, "strike", 134, 355)),
                     "--out", str(out), "--csv", str(table)])
    assert code == 0 and out.stat().st_size > 10_000
    rows = list(csv.DictReader(table.open()))
    assert len(rows) == 2 + 3 + 1 + 2 and {r["run"] for r in rows} == {"T51", "T54", "T52, ABORTED", "T55"}
