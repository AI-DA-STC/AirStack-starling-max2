"""Tests for the S0 record builder: fail closed, exact wording, CLI refusals."""

import copy
import importlib.util
import json
import tomllib
from pathlib import Path

import pytest

from svg_training.bench import record

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "s0_benchmark.toml"
HEADER = "| # | Date | Simulator | Run | What | Result | Record |\n|---|---|---|---|---|---|---|\n"


@pytest.fixture
def cfg():
    with open(CONFIG, "rb") as f:
        return tomllib.load(f)


def _row(tier, case, n, repeat, m, **over):
    r = {
        "tier": tier, "case": case, "num_games": n, "drones_per_game": m, "repeat": repeat,
        "status": "ok", "env_steps_per_s": 1000.0 * n, "drone_steps_per_s": 1000.0 * n * m,
        "peak_mem_mb": 512.0, "nan_count": 0, "mean_reset_fraction": 0.01,
        "device": "cuda:0", "gpu_name": "RTX 5070 Ti", "commit": "abc1234", "date": "2026-11-15",
    }
    if tier == 2:
        r["airframe"] = "ARL Robot 1"
    r.update(over)
    return r


@pytest.fixture
def rows(cfg):
    out = []
    for c in cfg["tier1"]:
        for n in c["num_games"]:
            for rep in range(cfg["timing"]["repeats"]):
                out.append(_row(1, c["name"], n, rep, c["guards"] + c["strikes"]))
    for c in cfg["tier2"]:
        for n in c["num_games"]:
            for rep in range(cfg["timing"]["repeats"]):
                out.append(_row(2, c["name"], n, rep, c["drones_per_game"]))
    return out


META = {"machine": "laptop", "gpu": "RTX 5070 Ti", "commit": "abc1234", "date": "2026-11-15",
        "name": "2026-11-15_s0_laptop", "config_path": "configs/s0_benchmark.toml"}


def test_complete_sweep_passes(rows, cfg):
    v = record.evaluate(rows, cfg, tests_passed=True)
    assert v["overall"] == "PASS" and v["missing"] == [] and all(g["pass"] for g in v["gates"].values())


def test_missing_point_fails(rows, cfg):
    v = record.evaluate([r for r in rows if not (r["case"] == "t1_5v3_full" and r["num_games"] == 4096)], cfg, True)
    assert v["overall"] == "FAIL" and ("t1_5v3_full", 4096) in v["missing"] and not v["gates"]["sweep_complete"]["pass"]


def test_oom_row_counts_as_present(rows, cfg):
    kept = [r for r in rows if not (r["case"] == "t1_5v3_full" and r["num_games"] == 65536)]
    kept.append(_row(1, "t1_5v3_full", 65536, 0, 8, status="oom", env_steps_per_s=None,
                     drone_steps_per_s=None, peak_mem_mb=None, nan_count=None, mean_reset_fraction=None))
    v = record.evaluate(kept, cfg, True)
    assert v["overall"] == "PASS" and v["missing"] == []


def test_repeat_spread_and_nan_fail(rows, cfg):
    bad = copy.deepcopy(rows)
    first = next(r for r in bad if r["case"] == "t1_1v1_open" and r["num_games"] == 256)
    first["env_steps_per_s"] *= 1.35  # about 30 % apart
    v = record.evaluate(bad, cfg, True)
    assert not v["gates"]["repeat_spread_max"]["pass"] and v["overall"] == "FAIL"
    assert v["gates"]["repeat_spread_max"]["observed"] > 0.10
    bad = copy.deepcopy(rows)
    bad[0]["nan_count"] = 1
    v = record.evaluate(bad, cfg, True)
    assert not v["gates"]["nan_count_max"]["pass"] and v["gates"]["nan_count_max"]["observed"] == 1
    assert v["overall"] == "FAIL"


def test_tests_failed_fails(rows, cfg):
    v = record.evaluate(rows, cfg, tests_passed=False)
    assert v["overall"] == "FAIL" and not v["gates"]["tests_pass"]["pass"]


def test_crash_only_and_empty_fail_closed(rows, cfg):
    crash = [r for r in rows if not (r["case"] == "t2_k2" and r["num_games"] == 64)]
    crash.append(_row(2, "t2_k2", 64, 0, 2, status="crash", env_steps_per_s=None, drone_steps_per_s=None,
                      peak_mem_mb=None, nan_count=None, mean_reset_fraction=None))
    v = record.evaluate(crash, cfg, True)
    assert ("t2_k2", 64) in v["missing"] and v["overall"] == "FAIL"
    v = record.evaluate([], cfg, True)
    assert v["overall"] == "FAIL" and not v["gates"]["repeat_spread_max"]["pass"]
    assert len(v["missing"]) > 0 and v["decisions"]["budget_gpu_hours"] is None


def test_decisions(rows, cfg):
    d = record.evaluate(rows, cfg, True)["decisions"]
    assert d["tier1_bulk"]["at_num_games"] == 65536 and d["tier1_bulk"]["meets"]
    assert d["tier2_train"]["case"] in {c["name"] for c in cfg["tier2"]}
    assert d["budget_gpu_hours"] == pytest.approx(2.0e9 / d["tier1_bulk"]["observed"] / 3600)


def test_record_text(rows, cfg):
    txt = record.render_record(rows, cfg, record.evaluate(rows, cfg, True), META)
    assert txt.splitlines()[0] == ("Simulator: training simulator, tiers 1 and 2 "
                                   "(stand-in drone models, no safety filter)")
    assert "observed in the training simulator" in txt and "validated" not in txt
    for word in ("stand-in", "no safety filter", "GPU-hours", "PASS", "t1_5v3_full", "RTX 5070 Ti",
                 "placeholder", "24 steps", "nothing here is a flight result"):
        assert word in txt


def test_ledger_row(rows, cfg):
    v = record.evaluate(rows, cfg, True)
    assert record.ledger_row(3, META, v) == (
        "| T3 | 2026-11-15 | training simulator, tiers 1 and 2 | 2026-11-15_s0_laptop | "
        "S0 throughput sweep | PASS | records/2026-11-15_s0_laptop_record.md |")


def _load_cli():
    spec = importlib.util.spec_from_file_location("make_record", ROOT / "scripts" / "make_record.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_cli_writes_and_refuses_overwrite(rows, tmp_path):
    res = tmp_path / "results.jsonl"
    res.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    ledger = tmp_path / "LEDGER.md"
    ledger.write_text(HEADER + "| T1 | 2026-11-01 | x | y | z | PASS | records/y_record.md |\n")
    out = tmp_path / "records"
    args = ["--results", str(res), "--config", str(CONFIG), "--tests-passed", "yes",
            "--name", "2026-11-15_s0_laptop", "--out-dir", str(out), "--ledger", str(ledger),
            "--seeds", "0"]
    cli = _load_cli()
    assert cli.main(args) == 0
    rec = out / "2026-11-15_s0_laptop_record.md"
    assert rec.exists() and "sha256" in rec.read_text()
    assert "| T2 | " in ledger.read_text() and ledger.read_text().count("| T") == 2
    before = (rec.read_text(), ledger.read_text())
    assert cli.main(args) == 1
    assert (rec.read_text(), ledger.read_text()) == before
    assert cli.main(args[:1] + [str(tmp_path / "nope.jsonl")] + args[2:6] + ["--name", "other"] + args[8:]) == 1


def _nan_row(rows, case, n):
    out = copy.deepcopy(rows)
    for r in out:
        if r["case"] == case and r["num_games"] == n:
            r["env_steps_per_s"] = float("nan")
            return out


@pytest.mark.parametrize("reverse", [False, True])
def test_nan_rate_fails_any_order(rows, cfg, reverse):
    bad = _nan_row(rows, "t2_k1", 4096)
    if reverse:
        bad = bad[::-1]
    v = record.evaluate(bad, cfg, True)
    assert v["overall"] == "FAIL" and any(x[:2] == ("t2_k1", 4096) for x in v["invalid_rows"])
    assert ("t2_k1", 4096) in v["missing"]


def test_none_nan_count_fails(rows, cfg):
    bad = copy.deepcopy(rows)
    bad[5]["nan_count"] = None
    v = record.evaluate(bad, cfg, True)
    assert v["overall"] == "FAIL" and v["invalid_rows"] and v["invalid_rows"][0][3] == "nan_count"
    record.render_record(bad, cfg, v, META)  # must not crash


def test_third_repeat_spread_fails(rows, cfg):
    more = rows + [_row(1, "t1_1v1_open", 256, 2, 2, env_steps_per_s=5000.0)]
    v = record.evaluate(more, cfg, True)
    assert not v["gates"]["repeat_spread_max"]["pass"]
    assert ("t1_1v1_open", 256) in v["extra_repeats"]
    assert "Extra repeats" in record.render_record(more, cfg, v, META)


def test_ok_plus_oom_present(rows, cfg):
    mixed = copy.deepcopy(rows)
    idx = next(i for i, r in enumerate(mixed) if r["case"] == "t1_5v3_full" and r["num_games"] == 65536 and r["repeat"] == 1)
    mixed[idx].update(status="oom", env_steps_per_s=None, drone_steps_per_s=None, peak_mem_mb=None,
                      nan_count=None, mean_reset_fraction=None)
    v = record.evaluate(mixed, cfg, True)
    assert v["missing"] == [] and v["overall"] == "PASS"
    record.render_record(mixed, cfg, v, META)


def test_two_gpus_warn(rows, cfg):
    two = copy.deepcopy(rows)
    two[0]["gpu_name"] = "Other GPU"
    txt = record.render_record(two, cfg, record.evaluate(two, cfg, True), META)
    assert "WARNING: rows from more than one GPU" in txt and "Other GPU" in txt


def _cli_args(tmp_path, results, extra=()):
    ledger = tmp_path / "LEDGER.md"
    if not ledger.exists():
        ledger.write_text(HEADER)
    return ["--results", str(results), "--config", str(CONFIG), "--tests-passed", "yes",
            "--name", "2026-11-15_s0_laptop", "--out-dir", str(tmp_path / "records"),
            "--ledger", str(ledger), *extra]


def test_cli_empty_results_writes_fail(tmp_path):
    res = tmp_path / "r.jsonl"
    res.write_text("")
    assert _load_cli().main(_cli_args(tmp_path, res, ["--seeds", "0 for all"])) == 0
    assert "| FAIL |" in (tmp_path / "LEDGER.md").read_text()
    assert (tmp_path / "records" / "2026-11-15_s0_laptop_record.md").exists()


def test_cli_malformed_line_writes_nothing(tmp_path):
    res = tmp_path / "r.jsonl"
    res.write_text("[1, 2]\n")
    args = _cli_args(tmp_path, res, ["--seeds", "0"])
    assert _load_cli().main(args) == 1
    assert not (tmp_path / "records").exists() and (tmp_path / "LEDGER.md").read_text() == HEADER
    res.write_text(json.dumps({"tier": 1, "case": "x"}) + "\n")
    assert _load_cli().main(args) == 1 and not (tmp_path / "records").exists()


def test_cli_requires_seeds(tmp_path):
    res = tmp_path / "r.jsonl"
    res.write_text("")
    with pytest.raises(SystemExit) as e:
        _load_cli().main(_cli_args(tmp_path, res))
    assert e.value.code == 2


def test_seeds_verbatim_in_record(tmp_path, rows):
    res = tmp_path / "r.jsonl"
    res.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    text = "0 for every case and repeat (Tier1BenchCfg.seed default)"
    assert _load_cli().main(_cli_args(tmp_path, res, ["--seeds", text])) == 0
    rec = (tmp_path / "records" / "2026-11-15_s0_laptop_record.md").read_text()
    assert text in rec and "not recorded" not in rec


def _set(rows, case, n, **kw):
    out = copy.deepcopy(rows)
    for r in out:
        if r["case"] == case and r["num_games"] == n:
            r.update(kw)
    return out


def test_negative_rates_fail(rows, cfg):
    v = record.evaluate(_set(rows, "t1_1v1_open", 256, env_steps_per_s=-1000.0), cfg, True)
    assert v["overall"] == "FAIL" and v["invalid_rows"]
    bad = copy.deepcopy(rows)
    pts = [r for r in bad if r["case"] == "t1_1v1_open" and r["num_games"] == 256]
    pts[0]["env_steps_per_s"], pts[1]["env_steps_per_s"] = -1000.0, -5000.0
    v = record.evaluate(bad, cfg, True)
    assert v["overall"] == "FAIL" and {x[3] for x in v["invalid_rows"]} == {"env_steps_per_s"}


def test_nan_count_opposite_signs_fail(rows, cfg):
    bad = copy.deepcopy(rows)
    bad[0]["nan_count"], bad[1]["nan_count"] = -5, 5
    v = record.evaluate(bad, cfg, True)
    assert v["overall"] == "FAIL" and v["invalid_rows"][0][3] == "nan_count"


@pytest.mark.parametrize("field,value", [("nan_count", 2.5), ("mean_reset_fraction", 1.5),
                                         ("peak_mem_mb", -1.0), ("env_steps_per_s", 10 ** 400)])
def test_out_of_range_invalid(rows, cfg, field, value):
    bad = copy.deepcopy(rows)
    bad[0][field] = value
    v = record.evaluate(bad, cfg, True)
    assert v["overall"] == "FAIL" and v["invalid_rows"][0][3] == field


def test_duplicate_repeat_fails(rows, cfg):
    bad = copy.deepcopy(rows)
    victim = next(i for i, r in enumerate(bad) if r["case"] == "t2_k1" and r["num_games"] == 64 and r["repeat"] == 1)
    dup = copy.deepcopy(bad[victim - 1])
    bad[victim] = dup  # repeat 0 twice instead of repeats 0 and 1
    v = record.evaluate(bad, cfg, True)
    assert v["overall"] == "FAIL" and ("t2_k1", 64, 0) in v["duplicate_rows"] and ("t2_k1", 64) in v["missing"]
    assert "Duplicate rows" in record.render_record(bad, cfg, v, META)


def test_cli_string_num_games_refused(tmp_path, rows):
    bad = copy.deepcopy(rows)
    bad[3]["num_games"] = "256"
    res = tmp_path / "r.jsonl"
    res.write_text("\n".join(json.dumps(r) for r in bad) + "\n")
    assert _load_cli().main(_cli_args(tmp_path, res, ["--seeds", "0"])) == 1
    assert not (tmp_path / "records").exists()


def test_cli_blank_seeds_exit_2(tmp_path):
    res = tmp_path / "r.jsonl"
    res.write_text("")
    with pytest.raises(SystemExit) as e:
        _load_cli().main(_cli_args(tmp_path, res, ["--seeds", "  "]))
    assert e.value.code == 2


def test_two_commits_warn(rows, cfg):
    two = copy.deepcopy(rows)
    two[0]["commit"] = "def5678"
    txt = record.render_record(two, cfg, record.evaluate(two, cfg, True), META)
    assert "WARNING: rows from more than one commit" in txt


def _txt(rows, cfg, meta=META):
    return record.render_record(rows, cfg, record.evaluate(rows, cfg, True), meta)


def test_two_code_versions_warn(rows, cfg):
    same = [dict(r, code_sha="aaaaaaaaaaaa") for r in rows]
    t = _txt(same, cfg)
    assert "WARNING: rows from more than one code version" not in t and "aaaaaaaaaaaa" in t
    two = copy.deepcopy(same)
    two[0]["code_sha"] = "bbbbbbbbbbbb"
    t = _txt(two, cfg)
    assert "WARNING: rows from more than one code version" in t and "bbbbbbbbbbbb" in t and "aaaaaaaaaaaa" in t


def test_commit_is_labelled(rows, cfg):
    assert "Parent repository HEAD (does not contain this folder while it is untracked)" in _txt(rows, cfg)


def test_unexpected_oom_order_listed(rows, cfg):
    bad = [r for r in rows if not (r["case"] == "t1_5v3_full" and r["num_games"] == 4096)]
    bad.append(_row(1, "t1_5v3_full", 4096, 0, 8, status="oom", env_steps_per_s=None, drone_steps_per_s=None,
                    peak_mem_mb=None, nan_count=None, mean_reset_fraction=None))
    v = record.evaluate(bad, cfg, True)
    assert v["oom_order"] == [("t1_5v3_full", 4096)]
    assert "Unexpected out-of-memory order" in _txt(bad, cfg)
    assert "Unexpected out-of-memory order" not in _txt(rows, cfg)
    # an oom at the largest size is the expected order
    top = [r for r in rows if not (r["case"] == "t1_5v3_full" and r["num_games"] == 65536)]
    top.append(_row(1, "t1_5v3_full", 65536, 0, 8, status="oom", env_steps_per_s=None, drone_steps_per_s=None,
                    peak_mem_mb=None, nan_count=None, mean_reset_fraction=None))
    assert record.evaluate(top, cfg, True)["oom_order"] == []


def test_not_measured_instead_of_does_not_meet(rows, cfg):
    none = [r for r in rows if r["tier"] == 2]  # no t1_5v3_full row at all
    t = _txt(none, cfg)
    assert "not measured" in t
    low = copy.deepcopy(rows)
    for r in low:
        if r["case"] == "t1_5v3_full":
            r["drone_steps_per_s"] = 1.0
    t = _txt(low, cfg)
    assert "does not meet" in t and "Tier 1 bulk training (case t1_5v3_full): best 1 drone-steps per second" in t


def test_new_limits_lines(rows, cfg):
    t = _txt(rows, cfg)
    for line in ("Warm-up is at least 50 steps and at least 2 s per repeat.",
                 "No policy network and no learning update are inside the timed step: the compute budget covers "
                 "simulator stepping only and is a lower bound on training time.",
                 "The budget assumes the published 2 billion samples are drone-steps; if they are environment steps, "
                 "multiply it by the number of drones per game (8 for 5 against 3).",
                 "Tier 2 rewrites every drone's root state on every policy step and has no flight controller.",
                 "Case t2_k8_250hz runs a 20.8 Hz policy (12 steps of 4 ms), not 20 Hz.",
                 "Tier 1 computes respawn candidates for every drone on every step, whether or not a drone is respawned."):
        assert f"- {line}" in t


def test_tier2_table_columns_and_worst_spread(rows, cfg):
    two = copy.deepcopy(rows)
    for r in two:
        if r["tier"] == 2:
            r["gpu_mem_used_mb"] = 7777.0
            r["peak_mem_mb"] = 11.0
        r["mean_reset_fraction"] = 0.0123
    first = next(r for r in two if r["case"] == "t1_1v1_open" and r["num_games"] == 256)
    first["env_steps_per_s"] *= 1.35
    t = _txt(two, cfg)
    t2 = t.split("### Tier 2")[1].split("## Gates")[0]
    assert "GPU memory used (device-wide)" in t2 and "7,777" in t2 and "| 11 |" not in t2
    assert "Resets per step (%)" in t and "| 1.2 |" in t
    assert "(worst: t1_1v1_open at 256 games)" in t


def test_note_and_flags_in_record(rows, cfg):
    t = _txt(rows, cfg, {**META, "note": "tier 2 stopped: first point exited 2",
                         "overflow_points": [("t2_k2", 64)]})
    g = t.split("## Gates")[1]
    assert g.lstrip().startswith("Note: tier 2 stopped: first point exited 2")
    assert "PhysX buffer overflow logged: numbers for these points are not trustworthy: t2_k2 at 64 games" in g


def test_cli_note_and_flags_file(tmp_path, rows):
    res = tmp_path / "r.jsonl"
    res.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    flags = tmp_path / "overflow_points.txt"
    flags.write_text("t2_k2 64\nt2_k2 64\n")
    assert _load_cli().main(_cli_args(tmp_path, res, ["--seeds", "0", "--note", "why it stopped",
                                                      "--flags-file", str(flags)])) == 0
    rec = (tmp_path / "records" / "2026-11-15_s0_laptop_record.md").read_text()
    assert "Note: why it stopped" in rec and rec.count("t2_k2 at 64 games") >= 1
    assert "t2_k2 at 64 games, t2_k2" not in rec  # duplicates collapsed


def test_cli_missing_flags_file_is_no_flags(tmp_path, rows):
    res = tmp_path / "r.jsonl"
    res.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    assert _load_cli().main(_cli_args(tmp_path, res, ["--seeds", "0", "--flags-file", str(tmp_path / "none.txt")])) == 0
    assert "PhysX buffer overflow" not in (tmp_path / "records" / "2026-11-15_s0_laptop_record.md").read_text()
