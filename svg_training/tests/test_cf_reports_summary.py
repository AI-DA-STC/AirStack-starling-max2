"""scripts/cf_reports_summary.py on a synthetic report.json fixture written here (STE track, Crazyflie route).

No real flight data is read; the fixture mimics the fields the script uses."""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import cf_reports_summary as cf  # noqa: E402


def _drone(err, lag, air=60.0, flags=None, batt=(3.9, 3.4, 3.7)):
    return {
        "mocap": {"hz": 50.0, "dropouts": 3},
        "envelope": {"airborne_s": air, "top_speed": 0.8},
        "commands": {"hz": 17.0, "stalls": 1, "longest_stall_s": 0.3},
        "tracking": {"error": {"mean": err, "p95": 2 * err, "max": 3 * err}, "lag_s": lag,
                     "residual": {"mean": err, "p95": err, "max": err}, "samples": 100},
        "status": {"battery_start": batt[0], "battery_min": batt[1], "battery_end": batt[2], "flags": flags or []},
    }


def _write(root, name, drones, closest, returncode=0, controller="mellinger", cmdline_extra=""):
    d = root / name
    d.mkdir()
    rep = {"drones": drones, "fleet": {"closest_pair": closest, "close_pairs": [closest] if closest else [],
                                       "downwash": {"events": []}, "show_alarms": ["2026-11-24T14:49:22.842 ATTACK WINS -- 1 strike(s)"]}}
    # json.dumps writes NaN as the bare word NaN, as the real reports do
    (d / "report.json").write_text(json.dumps(rep))
    cmd = ("ros2 run crazyflie_shows guard_show --ros-args -p rules:=pressure -p defense:=shell -p attack:=coordinated "
           "-p defenders:=cf1,cf2 -p attackers:=cf10 -p seed:=7 -p paced:=true" + cmdline_extra)
    (d / "meta.json").write_text(json.dumps({"cmdline": cmd, "returncode": returncode, "state": "done",
                                             "started_iso": "2026-11-24T14:47:32.1", "git": {"head": "abc1234"}}))
    (d / "output.log").write_text(f"2026-11-24T14:47:32.1 $ x\n2026-11-24T14:47:33.0   controller    {controller}\n"
                                  "2026-11-24T14:47:33.0   speeds        defence 1.00, attack 0.80, safety cap 1.20 m/s\n")
    (d / "config").mkdir()
    (d / "config" / "crazyflies.yaml").write_text("all:\n  firmware_params:\n    stabilizer:\n      controller: 1 # 1: PID\n"
                                                  "    # estimator: 9\n")


def _fixture(tmp_path):
    root = tmp_path / "flight_logs"
    root.mkdir()
    pair = {"pair": "cf1/cf2", "gap": 0.40, "t": 12.0, "dz": 0.0, "cmd_gap": 0.45, "mocap_jump_nearby": False}
    _write(root, "20261124_144732_guard_show",
           {"cf1": _drone(0.02, 0.10), "cf2": _drone(0.04, 0.12, flags=["crashed"]), "cf10": _drone(0.03, 0.08)}, pair)
    nanpair = dict(pair, pair="cf2/cf10", cmd_gap=float("nan"))
    _write(root, "20261123_135734_guard_show",
           {"cf1": _drone(0.20, 0.58), "cf2": _drone(0.22, 0.56), "cf10": _drone(0.25, 0.60)}, nanpair, controller="pid")
    _write(root, "20261123_133817_guard_show",
           {"cf1": _drone(0.0, 0.0, air=0.0), "cf2": _drone(0.0, 0.0, air=0.0), "cf10": _drone(0.0, 0.0, air=0.0)}, None, returncode=1)
    (root / "20261119_103551_guard_show").mkdir()  # trace only, no report.json
    return root


def test_load_and_rows(tmp_path):
    root = _fixture(tmp_path)
    flights, missing = cf.load_flights(root)
    assert [f["name"][:8] for f in flights] == ["20261123", "20261123", "20261124"]
    assert missing == ["20261119_103551_guard_show"]
    rows = {r["name"][:15]: r for r in map(cf.flight_row, flights)}
    r = rows["20261124_144732"]
    assert (r["rules"], r["defense"], r["attack"], r["seed"], r["paced"]) == ("pressure", "shell", "coordinated", "7", "true")
    assert (r["n_guard"], r["n_strike"], r["flown"], r["controller"], r["speeds"]) == (2, 1, True, "mellinger", "1.00/0.80")
    assert r["flags"] == {"cf2": ["crashed"]} and r["config"] == {"controller": "1"}
    assert rows["20261123_133817"]["flown"] is False and rows["20261123_133817"]["exit"] == 1
    assert rows["20261123_135734"]["controller"] == "pid"


def test_role_stats_split_by_controller(tmp_path):
    flights, _ = cf.load_flights(_fixture(tmp_path))
    st = cf.role_stats(flights)
    assert set(st) == {("guard", "mellinger"), ("strike", "mellinger"), ("guard", "pid"), ("strike", "pid")}
    g = st[("guard", "mellinger")]
    assert g["n_drone_flights"] == 2 and g["lag"]["median"] == 0.11 and g["lag_low"] == 2
    assert abs(g["err_mean_weighted"] - 0.03) < 1e-9 and abs(g["err_p95"]["max"] - 0.08) < 1e-9
    assert st[("guard", "pid")]["lag_high"] == 2  # the unflown flight adds nothing
    assert cf.role_stats(flights, skip_flagged=True)[("guard", "mellinger")]["n_drone_flights"] == 1


def test_pair_labels_nan_is_unknown(tmp_path):
    flights, _ = cf.load_flights(_fixture(tmp_path))
    labels = sorted((e["pair"], e["label"]) for e in cf.pair_events(flights))
    assert labels == [("cf1/cf2", "plan"), ("cf2/cf10", "unknown")]
    far = {"pair": "cf1/cf2", "gap": 0.4, "cmd_gap": 1.0}
    assert cf.classify_pair(far, {"cf1": {"tracking": {"error": {"p95": 0.05}}}, "cf2": {}}) == "aircraft"


def test_cli_prints_and_writes_nothing(tmp_path, capsys):
    root = _fixture(tmp_path)
    before = sorted(str(p) for p in root.rglob("*"))
    assert cf.main([str(root)]) == 0
    out = capsys.readouterr().out
    assert "## Per flight" in out and "guard / mellinger" in out and "1 folders without report.json" in out
    assert sorted(str(p) for p in root.rglob("*")) == before
