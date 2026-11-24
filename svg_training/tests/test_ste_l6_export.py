"""STE L3-L6 pipeline check, task L6.2: the export command (``scripts/ste_l6_export.py``) on folders the real driver
wrote (a velocity Guard run and a skills Strike run on the pool, tiny, CPU: ``tests/test_ste_l3_pool.py``'s fixture).
The run's own gate file copy and ``agent_final.pt`` through the route's loader; interface.toml records the
checkpoint's sha256 and the run's gate sha; the export reloads in a fresh process; the refusals exit 2."""
import json
import shutil
import sys
import tomllib

import pytest

from svg_training.ste import exploit

from _ste_tools import SCRIPTS
from test_ste_l3_pool import pooled_runs  # noqa: F401  (module fixture)

pytest.importorskip("onnxruntime")
sys.path.insert(0, str(SCRIPTS))
import ste_l6_export as cli  # noqa: E402
import ste_l6_read as reader  # noqa: E402


@pytest.fixture(scope="module")
def exported(pooled_runs, tmp_path_factory):  # noqa: F811
    tmp = tmp_path_factory.mktemp("l6_export")
    out = {}
    for side, (_, run) in pooled_runs.items():
        assert cli.main(["--run-dir", str(run), "--out", str(tmp / side), "--games", "4"]) == 0, side
        out[side] = (run, tmp / side)
    return out


def test_the_export_records_its_checkpoint_and_gate_file_and_reloads(exported):
    for side, (run, folder) in exported.items():
        meta = tomllib.loads((folder / "interface.toml").read_text())
        assert meta["source_checkpoint_sha256"] == exploit.sha256_file(run / "agent_final.pt")
        assert meta["gates_sha256"] == (run / "gates.sha256").read_text().strip()
        assert meta["source_run"] == str(run) and meta["team"] == side and len(meta["golden"]) == 4
        assert meta["policy_schema"] == ("ste-check-skills-0" if side == "strike" else "ste-check-velocity-0")
        r = reader.reload_in_a_fresh_process(folder)
        assert r["ok"], r


def test_the_reader_reads_the_real_export_and_refuses_another_checkpoint(exported, tmp_path):
    run, folder = exported["guard"]
    gates = exploit.load_gates(run / "gates.toml")
    (folder / "exit_code").write_text("0\n")                     # as scripts/ste_job.py writes it
    why, rel = reader.read_export(folder, "velocity", "guard", gates, run, "export")
    assert why is None and rel["ok"]
    other = tmp_path / "run"
    shutil.copytree(run, other)
    (other / "agent_final.pt").write_bytes(b"another checkpoint")
    with pytest.raises(reader.Refused, match="checkpoint"):
        reader.read_export(folder, "velocity", "guard", gates, other, "export")


def test_refusals_exit_2(exported, tmp_path):
    run, folder = exported["guard"]
    assert cli.main(["--run-dir", str(run), "--out", str(folder)]) == 2                 # a finished export folder
    bad = tmp_path / "bad"
    shutil.copytree(run, bad)
    (bad / "gates.sha256").write_text("0" * 64 + "\n")
    assert cli.main(["--run-dir", str(bad), "--out", str(tmp_path / "o1")]) == 2        # the copy is not the pin
    unfinished = tmp_path / "unfinished"
    shutil.copytree(run, unfinished)
    res = json.loads((unfinished / "results.json").read_text())
    res["complete"] = False
    (unfinished / "results.json").write_text(json.dumps(res))
    assert cli.main(["--run-dir", str(unfinished), "--out", str(tmp_path / "o2")]) == 2
    (tmp_path / "o3").mkdir()
    (tmp_path / "o3" / "job.json").write_text("{}")                                       # ste_job.py's own files
    assert cli.main(["--run-dir", str(run), "--out", str(tmp_path / "o3"), "--games", "2"]) == 0
