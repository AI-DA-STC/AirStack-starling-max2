"""STE task L0.2 Tier 2 speed in contested play: the gate file, the point plan, one point on the CPU (tier 2 on the
PyTorch reference world, the oracle for Isaac Lab), and the driver's run contract with fake children.

CPU only, tiny games; no Isaac (the driver's Isaac path is the lead's smoke). Observed in the training simulator."""
import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
sys.path.insert(0, str(ROOT / "scripts"))

from svg_training.ste import speed  # noqa: E402

PY = sys.executable


def toml_text(data: dict) -> str:
    """A minimal TOML writer for the gate tables (numbers, texts, booleans, lists; [[point]] arrays)."""
    def val(v):
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, str):
            return json.dumps(v)
        if isinstance(v, list):
            return "[" + ", ".join(val(x) for x in v) + "]"
        return repr(v)
    out = []
    for name, table in data.items():
        if name == "point":
            for p in table:
                out.append("[[point]]")
                out += [f"{k} = {val(v)}" for k, v in p.items()]
            continue
        out.append(f"[{name}]")
        out += [f"{k} = {val(v)}" for k, v in table.items()]
    return "\n".join(out) + "\n"


def committed() -> dict:
    return tomllib.loads(speed.GATES_FILE.read_text())


def tiny(tmp_path: Path, points=None, **over) -> Path:
    """The committed gate file made small enough for the CPU: 4 games, 1v1, 2-tick decisions, 2-decision updates."""
    d = committed()
    d["timing"].update(warmup_decisions=1, reference_decisions=2, updates=1, isaac_start_s=1, process_start_s=1)
    d["trainer"].update(decision_ticks=2, rollouts=2, learning_epochs=1, mini_batches=1, hidden=[8, 8])
    d["controls"].update(agree_point="t2", agree_games=2, agree_ticks=3, learner_update_point="t1")
    d["clips"].update(points=[], games=2, max_ticks=40)
    d["run"].update(threads=2)
    d["point"] = points or [{"id": "t2", "tier": 2, "size": "1v1", "games": 4, "protected": True},
                            {"id": "t1", "tier": 1, "size": "1v1", "games": 4, "protected": True}]
    for k, v in over.items():
        sec, key = k.split("__")
        d[sec][key] = v
    path = tmp_path / "gates.toml"
    path.write_text(toml_text(d))
    return path


# ------------------------------------------------------------------------------------------------ the gate file
def test_committed_gate_file_loads_and_pins_the_l011_base_game():
    g = speed.load_gates()
    assert speed.game_problem(g) is None
    l011 = tomllib.loads((ROOT / "configs" / "ste_l011" / "gates.toml").read_text())
    assert g.run["game_sha256"] == l011["games"]["base"]["sha256"]
    core = [p for p in g.points if p.protected]
    assert {(p.tier, p.size, p.games) for p in core} >= {(t, "3v3", n) for t in (1, 2) for n in (1024, 2048, 4096, 8192)}
    assert {p.size for p in g.points} >= {"1v1", "2v1", "3v3", "5v3"}
    assert g.point(g.controls["agree_point"]).tier == 2


def test_gate_trainer_is_the_t41_recipe():
    p1b = tomllib.loads((ROOT / "configs" / "nus_phase5.toml").read_text())["pilot_p1b"]
    tr = speed.load_gates().trainer
    for k in ("rollouts", "learning_epochs", "mini_batches", "learning_rate", "hidden", "init_log_std",
              "discount_factor", "gae_lambda", "value_loss_scale", "zero_mean_init"):
        assert tr[k] == p1b[k], k


@pytest.mark.parametrize("edit", ["unknown", "missing", "bad_condition", "dup", "tier", "control_point"])
def test_gate_file_refuses(tmp_path, edit):
    d = committed()
    if edit == "unknown":
        d["run"]["surprise"] = 1
    elif edit == "missing":
        del d["timing"]["updates"]
    elif edit == "bad_condition":
        d["point"][0]["only_if_fit"] = "later_point"
    elif edit == "dup":
        d["point"].append(dict(d["point"][0]))
    elif edit == "control_point":                            # QC L02-9: the controls' points must always run
        d["controls"]["learner_update_point"] = "t1_3v3_2048"
    else:
        d["point"][0]["tier"] = 3
    path = tmp_path / "g.toml"
    path.write_text(toml_text(d))
    with pytest.raises(ValueError):
        speed.load_gates(path)


def test_tier_1_is_the_base_file_as_committed_and_tier_2_differs_only_in_the_backend():
    from svg_training.core.game_config import load_game_cfg
    g = speed.load_gates()
    base, _ = load_game_cfg(ROOT / g.run["game_file"], use_local=False)
    t1, t2 = speed.tier_cfg(g, 1), speed.tier_cfg(g, 2)
    assert t1 == base                                               # off means identical: tier 1 is the L0.11 base game
    assert speed.cfg_differences(t1, t2) == ["starling.backend"]
    assert t2.starling.backend == "physics" and t1.starling.backend == "fitted"


# ------------------------------------------------------------------------------------------------ planning
def test_conditions_and_cuts(tmp_path):
    pts = [{"id": "z", "tier": 2, "size": "1v1", "games": 4, "protected": True},
           {"id": "a", "tier": 1, "size": "1v1", "games": 4, "protected": True},
           {"id": "b", "tier": 1, "size": "1v1", "games": 8, "protected": False},
           {"id": "c", "tier": 1, "size": "1v1", "games": 8, "protected": False, "only_if_did_not_fit": "a"},
           {"id": "d", "tier": 1, "size": "1v1", "games": 8, "protected": False, "only_if_fit": "a"}]
    g = speed.load_gates(tiny(tmp_path, points=pts, controls__agree_point="z", controls__learner_update_point="a"))
    assert speed.runnable(g.point("c"), {}) is None
    rows = {"a": fit_row("a", 1, games=4, seconds=8.0)}              # 24 s over 8 ticks: 3 s per tick at 4 games
    assert speed.runnable(g.point("c"), rows) is False and speed.runnable(g.point("d"), rows) is True
    assert speed.runnable(g.point("c"), {"a": {"status": "crashed"}}) is True
    assert speed.timed_s_per_tick(g, rows["a"]) == pytest.approx(3.0)
    ticks = speed.point_game_steps(g, g.point("b")) // g.point("b").games
    assert speed.projected_s(g, g.point("b"), rows) == pytest.approx(1 + 3.0 * ticks * 2)    # 8 games: scaled up x2
    assert speed.projected_s(g, g.point("z"), rows) == 1                                      # no tier 2 row: start only
    todo = [g.point(i) for i in "bd"]
    each = [speed.projected_s(g, p, rows) for p in todo]
    assert each[0] > 1.0                                           # measured rate used, plus the start
    assert speed.plan_cuts(g, todo, rows, sum(each) + 1) == []
    assert speed.plan_cuts(g, todo, rows, each[0] + 0.5) == ["d"]  # from the end of the run order
    assert speed.plan_cuts(g, [g.point("a")], rows, 0.0) == []      # protected: never cut


# ------------------------------------------------------------------------------------------------ one point, CPU
@pytest.fixture(scope="module")
def cpu_rows(tmp_path_factory):
    torch.set_num_threads(2)
    path = tiny(tmp_path_factory.mktemp("g"))
    g = speed.load_gates(path)
    from ste_speed_l02 import torch_world_factory
    return g, {p.id: speed.run_point(g, p, "cpu", world_factory=torch_world_factory) for p in g.points}


def test_point_rows_on_the_cpu(cpu_rows):
    g, rows = cpu_rows
    tr, tm = g.trainer, g.timing
    for pid, row in rows.items():
        assert row["status"] == speed.FIT
        lr = row["learner"]
        assert lr["updates"] == tm["updates"]
        assert lr["game_steps"] == tm["updates"] * tr["rollouts"] * tr["decision_ticks"] * row["games"]
        assert lr["rollout_s"] > 0 and lr["update_s"] > 0
        assert lr["train_game_steps_per_s"] < lr["rollout_game_steps_per_s"]
        rf = row["reference"]
        assert rf["ticks"] == tm["reference_decisions"] * tr["decision_ticks"]
        assert rf["game_steps"] == rf["ticks"] * row["games"]                      # kills M2 (an inflated rate)
        assert rf["game_steps_per_s"] == pytest.approx(rf["game_steps"] / rf["seconds"])
        assert rf["nonfinite"] == 0
        assert lr["nonfinite"] == 0
    assert rows["t2"]["motion"].startswith("physics/") and rows["t1"]["motion"] == "starling"


def test_controls_on_the_cpu(cpu_rows):
    _, rows = cpu_rows
    a = rows["t2"]["controls"]["physics_agreement"]                 # C-1a: bare worlds, the same recorded inputs
    assert a["pass"] and a["max_gap_m"] == 0.0 and a["ticks"] > 0  # the reference world against a fresh copy of itself
    b = rows["t2"]["info"]["game_agreement"]                         # C-1b: INFO, never a control
    assert b["first_divergence_tick"] is None and b["differing_alive_drone_ticks"] == 0
    assert set(b["world"]) == set(b["reference"]) >= {"ended", "reaches", "tags"}
    assert "game_agreement" not in rows["t2"]["controls"]
    assert rows["t1"]["controls"]["learner_update"]["pass"]
    assert speed.failed_controls(rows["t1"]) == [] and speed.failed_controls(rows["t2"]) == []


def heavy_factory(n, m, params, device):
    import dataclasses

    from svg_training.models.rigid_body import TorchRigidBodyWorld
    a = dataclasses.replace(params.airframe, mass_kg=params.airframe.mass_kg * 1.5)
    return TorchRigidBodyWorld(n, m, a, params.physics_dt_s, device)


def bad_partial_factory(n, m, params, device):
    """QC re-check probe R1: a world that is right on whole-world writes and wrong on partial ones (every partial write,
    which the game makes each tick for out drones, restarts and wall clamps, halves the speed of every other drone)."""
    from svg_training.models.rigid_body import TorchRigidBodyWorld

    class BadPartial(TorchRigidBodyWorld):
        def write_state(self, mask, pos_m, quat, lin, ang):
            super().write_state(mask, pos_m, quat, lin, ang)
            if not bool(mask.all()):
                self.lin_vel_w = torch.where(mask[..., None], self.lin_vel_w, self.lin_vel_w * 0.5)
    return BadPartial(n, m, params.airframe, params.physics_dt_s, device)


def test_physics_agreement_compares_the_world_with_the_reference(tmp_path):
    """C-1a (LEAD CALL QC L02-R1): the replay applies the game's own per-drone world writes (restarts, parking, wall and
    height clamps) and setpoints in the game's order. On a reference world it reproduces the game's drone positions
    exactly for EVERY drone and tick, parked ones included; a heavier drone fails; a world wrong only on partial writes
    fails; every game is compared (N4); a world compared with itself would pass all (M11)."""
    from ste_speed_l02 import torch_world_factory
    from svg_training.core.physics_layer import load_game_physics_params
    pts = [{"id": "t2", "tier": 2, "size": "3v3", "games": 8, "protected": True},     # 3v3, 3 s: drones go out
           {"id": "t1", "tier": 1, "size": "3v3", "games": 4, "protected": True}]
    g = speed.load_gates(tiny(tmp_path, points=pts, controls__agree_ticks=60))
    p = g.point("t2")
    cfg = speed.tier_cfg(g, 2)
    params = load_game_physics_params(cfg)
    rec = speed.record_physics_inputs(g, cfg, p, "cpu", 7, torch_world_factory)
    kinds = [op[0] for op in rec["ops"]]
    assert kinds.count("setpoint") == 60 and kinds.count("reset") >= 60 and rec["drone_pos"].shape == (60, 8, 6, 3)
    assert bool((rec["drone_pos"].abs() > 100).any())          # drones went out: the parking spot is in the game
    replay = speed.replay_positions(torch_world_factory(p.games, p.drones, params, "cpu"), params, "cpu", rec)
    assert torch.equal(replay, rec["drone_pos"])               # every drone, every tick, parked ones too
    same = speed.physics_agreement(g, rec, torch_world_factory(p.games, p.drones, params, "cpu"), params, "cpu",
                                   torch_world_factory)
    assert same["pass"] and same["max_gap_m"] == 0.0
    assert (same["games"], same["drones"], same["ticks"]) == (p.games, p.drones, 60)
    for factory in (heavy_factory, bad_partial_factory):
        bad = speed.physics_agreement(g, rec, factory(p.games, p.drones, params, "cpu"), params, "cpu",
                                      torch_world_factory)
        assert not bad["pass"] and bad["max_gap_m"] > bad["limit_m"], factory.__name__


def test_c1a_compares_every_game_not_only_the_first(tmp_path):
    """N4: a fault in the last game only must fail C-1a."""
    from ste_speed_l02 import torch_world_factory
    from svg_training.core.physics_layer import load_game_physics_params
    from svg_training.models.rigid_body import TorchRigidBodyWorld
    g = speed.load_gates(tiny(tmp_path, controls__agree_ticks=20))
    p = g.point("t2")
    cfg = speed.tier_cfg(g, 2)
    params = load_game_physics_params(cfg)
    rec = speed.record_physics_inputs(g, cfg, p, "cpu", 7, torch_world_factory)

    class LastGameHeavy(TorchRigidBodyWorld):
        def step(self):
            super().step()
            self.lin_vel_w = torch.cat((self.lin_vel_w[:-1], self.lin_vel_w[-1:] * 0.9))
    w = LastGameHeavy(p.games, p.drones, params.airframe, params.physics_dt_s, "cpu")
    r = speed.physics_agreement(g, rec, w, params, "cpu", torch_world_factory)
    assert not r["pass"] and r["games"] == p.games


def test_game_traces_are_compared_only_while_alive_in_both():
    """C-1b: a drone parked (out) in one world and flying in the other is a divergence, never a 1.7 km gap."""
    t, n, m = 4, 2, 2
    pos_a = torch.zeros(t, n, m, 3)
    pos_b = pos_a.clone()
    pos_b[:, 0, 0, 0] = 0.003                                         # a 3 mm gap while both fly
    alive_a = torch.ones(t, n, m, dtype=torch.bool)
    alive_b = alive_a.clone()
    alive_b[2:, 1, 1] = False                                         # out in one world from the third tick
    pos_b[2:, 1, 1] = 1000.0                                          # the parking spot
    r = speed.compare_game_traces(pos_a, alive_a, pos_b, alive_b)
    assert r["first_divergence_tick"] == 3 and r["differing_alive_drone_ticks"] == 2
    assert r["max_gap_alive_before_divergence_m"] == pytest.approx(0.003)
    same = speed.compare_game_traces(pos_a, alive_a, pos_a, alive_a)
    assert same["first_divergence_tick"] is None and same["max_gap_alive_before_divergence_m"] == 0.0


def test_clips_record_the_points_own_game(tmp_path):
    from ste_speed_l02 import torch_world_factory
    from svg_training.core.physics_layer import load_game_physics_params
    g = speed.load_gates(tiny(tmp_path))
    p = g.point("t2")
    cfg = speed.tier_cfg(g, 2)
    game = speed.make_game(cfg, p, "cpu", 3, torch_world_factory(p.games, p.drones, load_game_physics_params(cfg), "cpu"))
    recs = speed.record_clips(g, game, cfg, p, "cpu", 3)
    assert recs, "no clip game ended within max_ticks"
    for r in recs:
        assert r.pos_m.shape[0] == r.end_step + 1 and r.pos_m.shape[1:] == (p.drones, 3)
        assert "physics" in r.rules


# ------------------------------------------------------------------------------------------------ the driver
def fake_launch(rows_by_id: dict, logs: dict | None = None, codes: dict | None = None):
    """A launch() that writes the given rows (or nothing, with a log) instead of starting a child."""
    def launch(args, point, guard):
        folder = args.run_dir / "points"
        folder.mkdir(parents=True, exist_ok=True)
        if point.id in rows_by_id:
            (folder / f"{point.id}.json").write_text(json.dumps(rows_by_id[point.id]))
        if logs and point.id in logs:
            import ste_speed_l02 as D
            D.attempt_log(args.run_dir, point.id).write_text(logs[point.id])     # this attempt's own log
        return (codes or {}).get(point.id, 0), ""
    return launch


REQUIRED = {"t2": {"physics_agreement": {"pass": True}}, "t1": {"learner_update": {"pass": True}}}


def fit_row(pid, tier, games=4, drones=2, size="1v1", seconds=1.0):
    return {"id": pid, "tier": tier, "size": size, "games": games, "drones": drones, "status": "fit",
            "controls": dict(REQUIRED.get(pid, {})),
            "wall_s": 1.0, "game_steps_total": 1000,
            "learner": {"train_game_steps_per_s": 10.0, "rollout_game_steps_per_s": 20.0, "update_s_each": 1.0,
                        "nonfinite": 0, "decisions": 2, "rollout_s": seconds, "update_s": seconds},
            "reference": {"game_steps_per_s": 30.0, "ticks": 4, "seconds": seconds, "nonfinite": 0}}


@pytest.fixture
def run_dir(tmp_path):
    """Run folders under runs/ (the driver refuses any other place), removed after the test."""
    import shutil
    made = []

    def make(name="r"):
        d = ROOT / "runs" / "pytest_l02" / f"{tmp_path.name}_{name}"
        d.parent.mkdir(parents=True, exist_ok=True)
        made.append(d)
        return d
    yield make
    for d in made:
        shutil.rmtree(d, ignore_errors=True)
    if made and made[0].parent.is_dir() and not any(made[0].parent.iterdir()):
        made[0].parent.rmdir()


def test_driver_refuses(tmp_path, run_dir):
    import ste_speed_l02 as D
    gates = tiny(tmp_path)
    rd = run_dir()
    assert D.main(["--run-dir", str(rd), "--gates", str(gates), "--cap-h", "0.1"], launch=fake_launch({})) == 2  # no --headless
    assert D.main(["--run-dir", str(rd), "--gates", str(gates), "--cap-h", "0", "--dry-cpu"]) == 2
    assert D.main(["--run-dir", str(tmp_path / "x"), "--gates", str(gates), "--cap-h", "0.1", "--dry-cpu"]) == 2


def test_driver_rows_oom_crash_and_resume(tmp_path, run_dir):
    import ste_speed_l02 as D
    pts = [{"id": "t2", "tier": 2, "size": "1v1", "games": 4, "protected": True},
           {"id": "t1", "tier": 1, "size": "1v1", "games": 4, "protected": True},
           {"id": "big", "tier": 2, "size": "1v1", "games": 64, "protected": True},
           {"id": "mid", "tier": 2, "size": "1v1", "games": 32, "protected": False, "only_if_did_not_fit": "big"},
           {"id": "huge", "tier": 2, "size": "1v1", "games": 128, "protected": False, "only_if_fit": "big"},
           {"id": "odd", "tier": 1, "size": "1v1", "games": 16, "protected": False}]
    gates = tiny(tmp_path, points=pts)
    rd = run_dir()
    rows = {"t2": fit_row("t2", 2), "t1": fit_row("t1", 1), "mid": fit_row("mid", 2, 32)}
    logs = {"big": "boom\nRuntimeError: CUDA out of memory. Tried to allocate\n", "odd": "segfault\n"}
    code = D.main(["--run-dir", str(rd), "--gates", str(gates), "--cap-h", "1", "--dry-cpu"],
                  launch=fake_launch(rows, logs, {"big": 1, "odd": 139}))
    assert code == 0
    res = json.loads((rd / "results.json").read_text())
    status = {r["id"]: r["status"] for r in res["rows"]}
    assert status == {"t2": "fit", "t1": "fit", "big": "did_not_fit", "mid": "fit", "odd": "crashed"}
    assert "huge" in res["cuts"]["cuts"] and res["controls_all_pass"]
    assert "did not fit" in (rd / "results.md").read_text()
    # the same command resumes: every point has a row or a cut, nothing runs again
    called = []
    code = D.main(["--run-dir", str(rd), "--gates", str(gates), "--cap-h", "1", "--dry-cpu"],
                  launch=lambda a, p, g: called.append(p.id) or (0, ""))
    assert code == 0 and called == []


def test_driver_control_failed_is_terminal(tmp_path, run_dir):
    import ste_speed_l02 as D
    gates = tiny(tmp_path)
    rd = run_dir()
    logs = {"t2": "Isaac failed to start\n"}                       # the smallest protected tier 2 point crashed: C-3
    args = ["--run-dir", str(rd), "--gates", str(gates), "--cap-h", "1", "--dry-cpu"]
    assert D.main(args, launch=fake_launch({}, logs, {"t2": 1})) == 6
    assert D.main(args, launch=fake_launch({"t2": fit_row("t2", 2)})) == 6        # a relaunch ends with 6 again
    bad = fit_row("t1", 1)
    bad["controls"] = {"learner_update": {"pass": False}}
    rd2 = run_dir("b")
    assert D.main(["--run-dir", str(rd2), "--gates", str(gates), "--cap-h", "1", "--dry-cpu"],
                  launch=fake_launch({"t2": fit_row("t2", 2), "t1": bad})) == 6


def test_tier_2_child_refuses_without_headless(tmp_path, run_dir):
    rd = run_dir()
    rd.mkdir(parents=True, exist_ok=True)
    (rd / "gates.toml").write_text(tiny(tmp_path).read_text())
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    r = subprocess.run([PY, str(ROOT / "scripts" / "ste_speed_l02.py"), "--run-dir", str(rd), "--child", "t2"],
                       capture_output=True, text=True, env=env, timeout=60)
    assert r.returncode == 2 and "--headless" in r.stderr


def test_dry_cpu_run_end_to_end(tmp_path, run_dir):
    """The real children (subprocesses) on the CPU: both points written, the controls pass, results written."""
    import ste_speed_l02 as D
    gates = tiny(tmp_path)
    rd = run_dir()
    assert D.main(["--run-dir", str(rd), "--gates", str(gates), "--cap-h", "1", "--dry-cpu"]) == 0
    res = json.loads((rd / "results.json").read_text())
    assert [r["status"] for r in res["rows"]] == ["fit", "fit"] and res["controls_all_pass"] and res["dry_cpu"]
    assert (rd / "gates.sha256").read_text().strip() == speed.sha256_file(gates)
    import make_ste_l02_record as R
    text, row = R.record_text(rd, res, "pytest_l02", "T0")
    for head in ("## Purpose", "## Games at once and steps per second", "## Gates", "## Videos", "Verdict: **ABORTED**"):
        assert head in text                                  # no exit_code file: never INFO
    assert row.startswith("| T0 |") and row.count("|") >= 8
    assert R.main(["--run-dir", str(rd), "--number", "T0", "--out-dir", str(tmp_path)]) == 1   # a dry run: no record


def test_committed_protects_the_g0_sizes_and_smoke_gates_match():
    g = speed.load_gates()
    prot = {(p.tier, p.size, p.games) for p in g.points if p.protected}
    assert {(t, s, 4096) for t in (1, 2) for s in ("1v1", "2v1", "5v3")} <= prot
    s = speed.load_gates(speed.GATES_FILE.parent / "smoke_gates.toml")
    assert (s.run | {"cap_h": g.run["cap_h"]}) == g.run and (s.timing, s.trainer, s.controls, s.clips) == (
        g.timing, g.trainer, g.controls, g.clips)
    assert s.run["cap_h"] < g.run["cap_h"] and any(not p.protected and p.games > 8192 for p in s.points)


def test_a_stop_that_reached_the_child_first_is_a_stop(tmp_path, run_dir):
    """gpu_pause.sh or Ctrl-C reaches the child too: it may die before the parent's poll; no crashed row, exit 4."""
    import signal

    import ste_speed_l02 as D
    gates = tiny(tmp_path)
    rd = run_dir()

    def launch(args, point, guard):
        guard.stop_signal = signal.SIGINT                     # the parent got the signal while the child died with 1
        return 1, ""
    assert D.main(["--run-dir", str(rd), "--gates", str(gates), "--cap-h", "1", "--dry-cpu"], launch=launch) == 4
    assert not (rd / "points" / "t2.json").exists()
    assert D.main(["--run-dir", str(rd), "--gates", str(gates), "--cap-h", "1", "--dry-cpu"],
                  launch=fake_launch({"t2": fit_row("t2", 2), "t1": fit_row("t1", 1)})) == 0    # resumes, runs it


def test_isaac_parsers_leave_headless_to_the_launcher():
    import argparse

    import ste_speed_l02 as D
    import ste_transfer_l03 as L3
    for make in (D.parser, L3.parser):
        p = make(isaac=True)
        p.add_argument("--headless", action="store_true")        # what Isaac Lab's launcher adds (with --device)
        p.add_argument("--device")
        assert "--headless" in make().format_usage() and isinstance(p, argparse.ArgumentParser)


# ------------------------------------------------------------------------------------------------ QC fix round (21 Nov)
class _FakeAgent:
    """skrl's interaction calls; the PPO update (the post_interaction closing a block of ``rollouts``) sleeps."""
    def __init__(self, rollouts, nap):
        self.rollouts, self.nap = rollouts, nap

    def enable_training_mode(self, on):
        pass

    def pre_interaction(self, timestep, timesteps):
        pass

    def act(self, obs, states, timestep, timesteps):
        return {"a": torch.zeros(2, 4)}, None

    def record_transition(self, **kw):
        pass

    def post_interaction(self, timestep, timesteps):
        if (timestep + 1) % self.rollouts == 0:              # as skrl 2.1.0: its own counter over every interaction
            import time
            time.sleep(self.nap)


class _FakeEnv:
    def reset(self):
        return {"a": torch.zeros(2, 3)}, {}

    def state(self):
        return None

    def step(self, actions):
        z = torch.zeros(2, dtype=torch.bool)
        return ({"a": torch.zeros(2, 3)}, {"a": torch.zeros(2, 1)}, {"a": z[:, None]}, {"a": z[:, None]},
                {"outcome": torch.zeros(2, dtype=torch.int8), "nonfinite_actions": torch.zeros(2, dtype=torch.long),
                 "upset": z})


def test_update_time_is_the_update_after_a_warm_up():
    """The block-closing call after a warm-up offset is timed as the update, the rest as rollout (kills M4)."""
    nap = 0.2
    r = speed.learner_phase(_FakeAgent(4, nap), _FakeEnv(), 4, 4, "cpu", timestep0=1, planned=5)
    assert r["updates"] == 1 and r["update_s"] >= nap and r["rollout_s"] < nap   # timesteps 1..4: the block closes at 3
    r = speed.learner_phase(_FakeAgent(4, nap), _FakeEnv(), 8, 4, "cpu", timestep0=1, planned=9)
    assert r["updates"] == 2 and r["update_s"] >= 2 * nap and r["rollout_s"] < nap


def _child_args(rd):
    import ste_speed_l02 as D
    return D.parser().parse_args(["--run-dir", str(rd), "--child", "t1", "--dry-cpu"])


@pytest.mark.parametrize("where", ["learner", "reference"])
def test_child_exits_5_on_any_non_finite_count(tmp_path, run_dir, monkeypatch, where):
    """Kills M6; the scripted reference's count counts too (QC L02-3)."""
    import ste_speed_l02 as D
    rd = run_dir()
    rd.mkdir(parents=True)
    (rd / "gates.toml").write_text(tiny(tmp_path).read_text())
    row = fit_row("t1", 1)
    row[where]["nonfinite"] = 1
    monkeypatch.setattr(speed, "run_point", lambda *a, **k: json.loads(json.dumps(row)))
    assert D.run_child(_child_args(rd)) == 5


def test_exit_5_is_terminal(tmp_path, run_dir):
    """Kills M7: the child's exit 5 ends the run with 5; a relaunch refuses (exit 2), never carries on to exit 0; a row
    with a non-finite count ends it with 5 even if the child said 0."""
    import ste_speed_l02 as D
    gates = tiny(tmp_path)
    args = ["--run-dir", None, "--gates", str(gates), "--cap-h", "1", "--dry-cpu"]
    rd = run_dir("a")
    args[1] = str(rd)
    assert D.main(args, launch=fake_launch({"t2": fit_row("t2", 2)}, codes={"t2": 5})) == 5
    assert (rd / D.TERMINAL_FILE).is_file()
    assert D.main(args, launch=fake_launch({"t1": fit_row("t1", 1)})) == 2
    bad = fit_row("t2", 2)
    bad["reference"]["nonfinite"] = 3
    rd2 = run_dir("b")
    args[1] = str(rd2)
    assert D.main(args, launch=fake_launch({"t2": bad})) == 5


def test_oom_reads_only_this_attempts_log_and_only_real_messages(tmp_path, run_dir):
    """QC L02-4: an out-of-memory line from an EARLIER attempt, or a loose word, never makes a crash "did not fit"; an
    allocation failure printed by a child that wrote its row makes the row "suspect", not "fit"."""
    import ste_speed_l02 as D
    pts = [{"id": "t2", "tier": 2, "size": "1v1", "games": 4, "protected": True},
           {"id": "t1", "tier": 1, "size": "1v1", "games": 4, "protected": True},
           {"id": "x", "tier": 2, "size": "1v1", "games": 64, "protected": False},
           {"id": "y", "tier": 2, "size": "1v1", "games": 64, "protected": False},
           {"id": "z", "tier": 2, "size": "1v1", "games": 64, "protected": False}]
    gates = tiny(tmp_path, points=pts)
    rd = run_dir()
    (rd / "points").mkdir(parents=True)
    (rd / "points" / "x.attempt1.log").write_text("RuntimeError: CUDA out of memory. Tried to allocate 2 GiB\n")

    def launch(args, point, guard):
        log = D.attempt_log(args.run_dir, point.id)
        log.write_text({"x": "Segmentation fault\n", "y": "warning: failed to allocate a texture; not enough memory\n",
                        "z": "PhysX error: PxgCudaMemoryAllocator fail to allocate memory 1073741824 bytes!\n"}.get(
                           point.id, ""))
        rows = {"t2": fit_row("t2", 2), "t1": fit_row("t1", 1), "z": fit_row("z", 2, 64)}
        if point.id in rows:
            (args.run_dir / "points" / f"{point.id}.json").write_text(json.dumps(rows[point.id]))
        return (0 if point.id in rows else 139), ""
    assert D.main(["--run-dir", str(rd), "--gates", str(gates), "--cap-h", "1", "--dry-cpu"], launch=launch) == 0
    st = {r["id"]: r["status"] for r in json.loads((rd / "results.json").read_text())["rows"]}
    assert st == {"t2": "fit", "t1": "fit", "x": "crashed", "y": "crashed", "z": "suspect"}


def test_a_crash_at_any_protected_point_is_control_failed(tmp_path, run_dir):
    """QC L02-5: a protected point that crashed (not out of memory) ends the run with 6."""
    import ste_speed_l02 as D
    pts = [{"id": "t2", "tier": 2, "size": "1v1", "games": 4, "protected": True},
           {"id": "t1", "tier": 1, "size": "1v1", "games": 4, "protected": True},
           {"id": "big", "tier": 2, "size": "1v1", "games": 64, "protected": True}]
    gates = tiny(tmp_path, points=pts)
    rd = run_dir()
    code = D.main(["--run-dir", str(rd), "--gates", str(gates), "--cap-h", "1", "--dry-cpu"],
                  launch=fake_launch({"t2": fit_row("t2", 2), "t1": fit_row("t1", 1)}, {"big": "Segmentation fault\n"},
                                     {"big": 139}))
    assert code == 6
    md = (rd / "results.md").read_text()
    assert "CONTROLS FAILED — rates void" in md.split("| Point |")[0] and "VOID" in md


def test_largest_fit_stops_at_the_first_protected_size_that_did_not_fit():
    import ste_speed_l02 as D
    rows = {f"p{n}": {"tier": 2, "size": "3v3", "games": n, "status": s, "protected": pr}
            for n, s, pr in ((1024, "fit", True), (4096, "fit", True), (6144, "fit", False), (8192, "did_not_fit", True),
                             (16384, "fit", False))}
    prot = {r_id for r_id, r in rows.items() if r["protected"]}
    assert D.largest_fit(rows, 2, prot) == 6144


def test_required_controls_missing_is_a_failure(tmp_path, run_dir):
    """QC L02-6: the agreement point's row without C-1a (or the learner point's without C-2) fails the run."""
    import ste_speed_l02 as D
    gates = tiny(tmp_path)
    rd = run_dir()
    bare = fit_row("t2", 2)
    bare["controls"] = {}
    assert D.main(["--run-dir", str(rd), "--gates", str(gates), "--cap-h", "1", "--dry-cpu"],
                  launch=fake_launch({"t2": bare, "t1": fit_row("t1", 1)})) == 6


def test_l02_record_aborted_on_any_failed_or_missing_control(tmp_path):
    """Kills M10; an ABORTED ledger row leads with ABORTED and no rate (QC L02-7)."""
    import ste_speed_l02 as D
    import make_ste_l02_record as R
    gates = tiny(tmp_path)
    rd = tmp_path / "run"
    rd.mkdir()
    (rd / "gates.toml").write_text(gates.read_text())
    (rd / "exit_code").write_text("0\n")
    g = speed.load_gates(gates)
    for rows, want in (({"t2": fit_row("t2", 2), "t1": fit_row("t1", 1)}, "INFO"),
                       ({"t2": {**fit_row("t2", 2), "controls": {"physics_agreement": {"pass": False}}},
                         "t1": fit_row("t1", 1)}, "ABORTED"),
                       ({"t2": {**fit_row("t2", 2), "controls": {}}, "t1": fit_row("t1", 1)}, "ABORTED")):
        (rd / "points").mkdir(exist_ok=True)
        for k, v in rows.items():
            (rd / "points" / f"{k}.json").write_text(json.dumps(v))
        res = D.write_results(rd, g, stopped=None)
        text, row = R.record_text(rd, res, "x", "T0")
        assert f"Verdict: **{want}" in text
        if want == "ABORTED":
            assert "rates void" in row and "game-steps/s" not in row


def test_record_only_keeps_the_runs_own_ending(tmp_path, run_dir):
    import ste_speed_l02 as D
    gates = tiny(tmp_path)
    rd = run_dir()
    args = ["--run-dir", str(rd), "--gates", str(gates), "--cap-h", "1", "--dry-cpu"]
    assert D.main(args, launch=fake_launch({"t2": fit_row("t2", 2), "t1": fit_row("t1", 1)})) == 0
    assert D.main(["--run-dir", str(rd), "--record-only"]) == 0
    assert json.loads((rd / "results.json").read_text())["stopped"] is None


def test_ctrl_c_during_isaac_start_exits_4(monkeypatch):
    """QC L02-10: Ctrl-C while Isaac Sim starts exits 4 (both drivers); Isaac Lab's launcher is a fake here."""
    import types

    class Launcher:
        def __init__(self, args):
            raise KeyboardInterrupt

        @staticmethod
        def add_app_launcher_args(parser):
            parser.add_argument("--headless", action="store_true")
            parser.add_argument("--device")
    mod = types.ModuleType("isaaclab.app")
    mod.AppLauncher = Launcher
    monkeypatch.setitem(sys.modules, "isaaclab", types.ModuleType("isaaclab"))
    monkeypatch.setitem(sys.modules, "isaaclab.app", mod)
    sys.modules.pop("_isaac_app", None)

    def fake_exit(code):
        raise SystemExit(code)
    import ste_speed_l02 as D
    import ste_transfer_l03 as L3
    monkeypatch.setattr(D.os, "_exit", fake_exit)
    for argv, fn in ((["x", "--run-dir", "runs/x", "--child", "t2", "--headless"], D._child_isaac),
                     (["x", "--part", "isaac", "--run-dir", "runs/x", "--headless"], L3._isaac_cli)):
        monkeypatch.setattr(sys, "argv", argv)
        with pytest.raises(SystemExit) as e:
            fn()
        assert e.value.code == 4


def test_smallest_protected_point_out_of_memory_is_control_failed(tmp_path, run_dir):
    """C-3: a tier that cannot hold its smallest protected games is a broken path, even when it is out of memory and not
    a crash (kills M9 now that a crash at any protected point also fails)."""
    import ste_speed_l02 as D
    gates = tiny(tmp_path)
    rd = run_dir()
    assert D.main(["--run-dir", str(rd), "--gates", str(gates), "--cap-h", "1", "--dry-cpu"],
                  launch=fake_launch({"t1": fit_row("t1", 1)}, {"t2": "torch.OutOfMemoryError: CUDA out of memory\n"},
                                     {"t2": 1})) == 6
    assert json.loads((rd / "points" / "t2.json").read_text())["status"] == "did_not_fit"


def test_each_attempt_gets_a_fresh_log(tmp_path):
    """N11: a second attempt never reads the first attempt's lines."""
    import ste_speed_l02 as D
    first = D.new_attempt_log(tmp_path, "p")
    first.write_text("CUDA out of memory\n")
    second = D.new_attempt_log(tmp_path, "p")
    assert second != first and second.read_text() == "" and D.attempt_log(tmp_path, "p") == second


def test_end_of_run_required_control_check_exits_6(tmp_path, run_dir):
    """N13: the agree point never ran (its condition failed), so its required control is missing at the end: exit 6."""
    import ste_speed_l02 as D
    pts = [{"id": "t1", "tier": 1, "size": "1v1", "games": 4, "protected": True},
           {"id": "x", "tier": 1, "size": "1v1", "games": 8, "protected": False},
           {"id": "t2", "tier": 2, "size": "1v1", "games": 4, "protected": True, "only_if_fit": "x"}]
    gates = tiny(tmp_path, points=pts)
    rd = run_dir()
    assert D.main(["--run-dir", str(rd), "--gates", str(gates), "--cap-h", "1", "--dry-cpu"],
                  launch=fake_launch({"t1": fit_row("t1", 1)}, {"x": "Segmentation fault\n"}, {"x": 139})) == 6
    assert any(k.startswith("t2:") for k in json.loads((rd / "controls.json").read_text())["failed"])


def test_nonfinite_counts_are_read_on_suspect_rows_too():
    """R3: a "suspect" row (an allocation failure in its log) still carries its non-finite counts."""
    import ste_speed_l02 as D
    row = fit_row("t2", 2)
    row["status"] = D.SUSPECT
    row["learner"]["nonfinite"] = 2
    assert D.nonfinite_in(row) == 2
