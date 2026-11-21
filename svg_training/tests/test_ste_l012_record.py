"""The L0.12 record writer on small hand-made run folders (no training): the ledger row has LEDGER.md's seven columns,
numbers are rounded, a missing side prints "-" (never "nan"), and the probe note points at run 0 where it is."""
import datetime
import json
import sys
from pathlib import Path

from _ste_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import make_ste_l012_record as record  # noqa: E402

T0 = 1795225886.4097764          # a launch time; the row's date is the earliest launch of the runs it covers
SIM = "training simulator, tier 1 (test)"
GPU = "TEST GPU"


def ci(k, n=1000):
    return {"k": k, "n": n, "rate": k / n, "ci": [max(0.0, k / n - 0.03), min(1.0, k / n + 0.03)]}


def run_folder(root: Path, name: str, t: float, complete=True, budget=True) -> Path:
    d = root / name
    (d / "videos").mkdir(parents=True)
    (d / "launches.jsonl").write_text(json.dumps({"event": "launch", "launch": 1, "time": t}) + "\n"
                                      + json.dumps({"event": "end", "launch": 1, "time": t + 100, "exit_code": 0}) + "\n")
    (d / "exit_code").write_text("0\n")
    (d / "run.json").write_text(json.dumps({"variant": "tag_1p2", "side": "strike"}))
    (d / "train_log.jsonl").write_text(json.dumps({"update": 1, "game_steps_total": 1000}) + "\n")
    (d / "eval_before.npz").write_bytes(b"")
    (d / "eval_final.npz").write_bytes(b"")
    (d / "controls.json").write_text(json.dumps({"ctl": {"status": "PASS"}}))
    res = {"complete": complete, "budget_reached": budget, "train_stop": "cap reserve at update 1",
           "machine": {"host": "h", "gpu": GPU, "torch": "t"}, "simulator": SIM,
           "reference": {"file": "ref.npz", "sha256": "a", "start_sha256": "b", "t44_gates_sha256": "c"},
           "game_file": {"file": "g.toml", "sha256": "d"}, "settings": {}, "train_seed": 1,
           "parameter_set": {"file": "p.toml", "sha256": "e", "filter": "every pair"},
           "code": {"first": {"commit": "f" * 40, "diff_sha256": "0" * 64}}, "effective_s": 10.0, "cap_h": 0.75,
           "num_games": 4, "game_steps_per_s_median": 5.0, "trained_updates": 1, "game_steps": 1000,
           "eval_games": 1000, "videos": []}
    (d / "results.json").write_text(json.dumps(res))
    return d


def side(trained, script, guards_left, length, untrained=0):
    return {"untrained": ci(untrained), "gain": {"trained": ci(trained), "script": ci(script),
                                                 "gain": (trained - script) / 1000, "real": trained > script},
            "status": "gain", "exploiter_composition": {"guards_left_mean_in_holds": guards_left,
                                                        "length_median_s": length},
            "script_cell": ["guard_field", "strike_straight"], "paired": {"exploiter_only": 1, "script_only": 2},
            "recipe": "T41 recipe", "run0": {"learner_control_accepted": None}}


def verdict_folder(tmp_path: Path) -> tuple[Path, Path]:
    g = run_folder(tmp_path, "guard", T0 + 50)
    s = run_folder(tmp_path, "strike", T0 + 10)
    r0 = run_folder(tmp_path, "run0", T0)
    (r0 / "learner_control.json").write_text("{}")
    v = {"simulator": SIM, "gates_sha256": "x" * 64, "band": 0.2, "controls_pass": True,
         "run0": {"status": "PASS", "file": str(r0 / "learner_control.json"), "sha256": "y" * 64, "reads": [],
                  "script": ci(466), "train_stop": "PASS"},
         "variants": {
             "base": {"role": "reference", "category": "worth learning", "strike_upper": 0.6652488751252258,
                      "guard_upper": 0.9289258437501923,
                      "sides": {"strike": side(636, 192, 0.1043956043956044, 7.5),
                                "guard": side(913, 808, 0.0, 2.9000000000000004)}},
             "tag_1p2": {"role": "shortlisted", "category": "incomplete: one side only",
                         "sides": {"guard": side(503, 645, 0.0, 6.550000000000001)}}},
         "runs": {"base guard": str(g), "base strike": str(s), "tag_1p2 guard": str(g)},
         "machine": {"host": "h", "gpu": GPU, "torch": "t", "python": "3"}}
    vf = tmp_path / "verdict.json"
    vf.write_text(json.dumps(v))
    pilot = tmp_path / "pilot.json"
    pilot.write_text(json.dumps({"probes": [], "strike_recipe": {"recipe": "shaped Strike recipe"}}))
    return vf, pilot


def ledger_cells(text: str) -> list[str]:
    row = text.split("Ledger row: ", 1)[1].splitlines()[0]
    assert row.startswith("| ") and row.endswith(" |"), row
    return [c.strip() for c in row[1:-1].split(" | ")]


def date_of(t: float) -> str:
    return datetime.datetime.fromtimestamp(t).astimezone().isoformat(timespec="seconds")


def test_the_verdict_ledger_row_has_the_ledgers_seven_columns(tmp_path):
    vf, pilot = verdict_folder(tmp_path)
    out = tmp_path / "rec.md"
    assert record.main(["--verdict", str(vf), "--out", str(out), "--name", "n", "--number", "T46",
                        "--pilot", str(pilot)]) == 0
    cells = ledger_cells(out.read_text())
    assert len(cells) == 7, cells                       # | # | Date | Simulator | Run | What | Result | Record |
    assert cells[0] == "T46" and cells[1] == date_of(T0)             # the earliest launch, run 0's
    assert SIM in cells[2] and GPU in cells[2]
    assert cells[3] == "n" and cells[4].startswith("STE L0.12 Best-response test: ")
    assert cells[5] == "INFO" and cells[6] == "records/n_record.md"


def test_numbers_are_rounded_and_a_missing_side_prints_a_dash(tmp_path):
    vf, pilot = verdict_folder(tmp_path)
    out = tmp_path / "rec.md"
    assert record.main(["--verdict", str(vf), "--out", str(out), "--name", "n", "--pilot", str(pilot)]) == 0
    text = out.read_text()
    for raw in ("0.1043956043956044", "2.9000000000000004", "6.550000000000001", "nan"):
        assert raw not in text, raw
    assert "| 0.104 | 7.50 |" in text and "| 0.000 | 2.90 |" in text
    assert "| tag_1p2 | shortlisted | - | gain | - | - | **incomplete: one side only** |" in text


def test_the_probe_note_points_at_run_0_above_it(tmp_path):
    vf, pilot = verdict_folder(tmp_path)
    out = tmp_path / "rec.md"
    assert record.main(["--verdict", str(vf), "--out", str(out), "--name", "n", "--pilot", str(pilot)]) == 0
    text = out.read_text()
    assert text.index("## Run 0 (learner positive control)") < text.index("recipe picked")
    assert "run 0, above" in text and "run 0, below" not in text


def test_the_aborted_ledger_row_has_the_ledgers_seven_columns(tmp_path):
    d = run_folder(tmp_path, "cut", T0 + 7, budget=False)
    out = tmp_path / "rec.md"
    assert record.main(["--aborted", "--runs", str(d), "--out", str(out), "--name", "n", "--number", "T47"]) == 0
    text = out.read_text()
    cells = ledger_cells(text)
    assert len(cells) == 7, cells
    assert cells[0] == "T47" and cells[1] == date_of(T0 + 7) and GPU in cells[2]
    assert cells[5] == "ABORTED" and cells[6] == "records/n_record.md"
    assert "before its game-step budget" in cells[4]
    # a run cut before its budget is not called "finished" (QC N-2); a run that reached it still is (QC N-4)
    assert "finished, controls PASS" not in text
