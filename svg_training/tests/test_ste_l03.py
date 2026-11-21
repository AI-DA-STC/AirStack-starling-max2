"""STE task L0.3 STE Guard policy in tier 2 without retraining: the gate file, T41's two games (row 5 and row 6), the
held strategy, the checks with known answers, and the driver's two parts on the CPU (tier 2 on the PyTorch reference
world, the oracle for Isaac Lab). No Isaac. Needs the PROVISIONAL bundle (T41's run folder, the paired starts, the local
NUS files: scripts/nus_install_provisional.sh); skipped without it. Observed in the training simulator."""
import json
import shutil
import sys
import tomllib
from pathlib import Path

import numpy as np
import pytest
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
sys.path.insert(0, str(ROOT / "scripts"))

from svg_training.core.rewards import GUARD_WIN, STRIKE_WIN  # noqa: E402
from svg_training.ste import transfer as T  # noqa: E402

GATES = T.load_gates()
PROBLEMS = T.pin_problems(GATES)
BUNDLE = not [p for p in PROBLEMS if not p.startswith("t45")]          # T41, starts, local files
HAS_T45 = not [p for p in PROBLEMS if p.startswith("t45")]             # T45's per-game file (runs/, copied by hand)
needs_bundle = pytest.mark.skipif(not BUNDLE, reason="the PROVISIONAL bundle is not installed (T41, starts, local files)")
needs_t45 = pytest.mark.skipif(not (BUNDLE and HAS_T45), reason="the bundle or T45's per-game file is missing")


@pytest.fixture(scope="module")
def worlds():
    if not BUNDLE:
        pytest.skip("no bundle")
    torch.set_num_threads(2)
    return T.worlds(GATES)


def torch_world(n, m, params, device):
    from svg_training.models.rigid_body import TorchRigidBodyWorld
    return TorchRigidBodyWorld(n, m, params.airframe, params.physics_dt_s, device)


# ------------------------------------------------------------------------------------------------ the gate file
def test_gate_file_matches_t41_and_t45():
    r, c = GATES["run"], GATES["controls"]
    l014 = ROOT / "configs" / "ste_l014.toml"
    if l014.is_file():                                     # on development after the L0.14 merge
        resp = tomllib.loads(l014.read_text())["response"]
        assert (r["eval_seed"], r["opponent_seed_offset"], r["games"], r["opponent"]) == (
            resp["eval_seed"], resp["opponent_seed_offset"], resp["games"], resp["opponent"])
    assert r["guard_agent_sha256"].startswith("c91bea51d7ec4032")          # T45's record
    assert c["parked_reach_min"] <= GATES["references"]["t24_parked_reaches"] <= c["parked_reach_max"]
    assert not c["parked_reach_min"] <= GATES["references"]["row5_parked_reaches"] <= c["parked_reach_max"]


@pytest.mark.parametrize("edit", ["unknown", "band"])
def test_gate_file_refuses(tmp_path, edit):
    text = GATES["path"].read_text()
    if edit == "unknown":
        text = text.replace("[clips]", "[clips]\nsurprise = 1")
    else:
        text = text.replace("parked_reach_min = 493", "parked_reach_min = 600")
    (tmp_path / "g.toml").write_text(text)
    with pytest.raises(ValueError):
        T.load_gates(tmp_path / "g.toml")


@needs_t45
def test_pins_hold_on_this_machine():
    assert T.pin_problems(GATES) == []


# ------------------------------------------------------------------------------------------------ the games
def test_row_6_differs_from_row_5_in_the_drone_only(worlds):
    w5, w6 = worlds
    assert T.check_rows(GATES, w5, w6)["pass"]
    assert w5.row["drone"] == "fitted" and w6.row["drone"] == "physics"
    bad = w6.__class__(**{**w6.__dict__, "cfg": w6.cfg.replace(**{"starling.filter_iterations": 7})})
    assert not T.check_rows(GATES, w5, bad)["pass"]         # negative control


def test_direct_game_equals_pilot_games(worlds):
    """The game this task builds is T41's evaluation game (nus/pilot.pilot_games, the path T45 reproduced)."""
    from svg_training.core.play import play_match
    from svg_training.nus import pilot as P
    w5, _ = worlds
    n, seed = 3, int(GATES["run"]["eval_seed"])
    _, evals = P.pilot_games(w5, 1, [n], "cpu", seed, seed)
    outs = []
    for game in (evals[n], T.t41_game(w5, n, "cpu", seed)):
        guard, opp = T.t41_players(GATES, w5, n, "cpu")
        game.gen.manual_seed(seed)
        res = play_match(game, guard, opp, max_steps=40)
        outs.append((res, game.pos_m.clone()))
    assert torch.equal(outs[0][1], outs[1][1])
    assert torch.equal(outs[0][0].closest_cross_m, outs[1][0].closest_cross_m)


def test_held_strategy_asks_once_per_decision(worlds):
    from svg_training.nus import pilot as P
    w5, _ = worlds
    hold = P.decision_ticks(GATES["run"]["decision_ticks"], w5)
    assert hold == 12

    class Count:
        team, name = "guard", "count"
        calls = 0

        def reset(self, games):
            pass

        def act(self, obs):
            Count.calls += 1
            return torch.full((1, 3, 4), float(Count.calls))
    h = P.HeldStrategy(Count(), hold)
    acts = [float(h.act(None)[0, 0, 0]) for _ in range(3 * hold)]
    assert acts == [1.0] * hold + [2.0] * hold + [3.0] * hold


def test_tier_2_game_on_the_reference_world(worlds):
    from svg_training.core.physics_layer import load_game_physics_params
    _, w6 = worlds
    n = 2
    phys = torch_world(n, w6.guards + w6.strikes, load_game_physics_params(w6.cfg), "cpu")
    game = T.t41_game(w6, n, "cpu", 1, phys)
    assert game.motion.startswith("physics/")
    res, extras = T.play_t41(GATES, w6, "cpu", phys, games=n, max_steps=30)
    assert res.steps_played == 30 and int(res.nonfinite_actions.sum()) == 0 and "video" in extras


def heavy_world(n, m, params, device):
    import dataclasses
    a = dataclasses.replace(params.airframe, mass_kg=params.airframe.mass_kg * 1.5)
    return torch_world(n, m, dataclasses.replace(params, airframe=a), device)


def test_c3_compares_the_physics_world_with_the_reference(worlds):
    """C-3 (LEAD CALL QC L02-2): bare replays of T41's game inputs. A heavier drone in the world under test must fail
    (a world compared with itself would pass: mutation M18); a reference-kind world passes with no gap. C-3b (INFO)
    reports the in-game comparison."""
    from svg_training.core.physics_layer import load_game_physics_params
    _, w6 = worlds
    n = 3
    params = load_game_physics_params(w6.cfg)
    m = w6.guards + w6.strikes
    good, info = T.agreement(GATES, w6, "cpu", torch_world(n, m, params, "cpu"), torch_world, games=n)
    assert good["pass"] and good["max_gap_m"] == 0.0 and good["games"] == n and good["ticks"] == GATES["controls"]["agree_ticks"]
    assert info["first_divergence_tick"] is None and {"ended", "reaches", "tags"} <= set(info["world"])
    bad, _ = T.agreement(GATES, w6, "cpu", heavy_world(n, m, params, "cpu"), torch_world, games=n)
    assert not bad["pass"] and bad["max_gap_m"] > bad["limit_m"]
    from test_ste_l02 import bad_partial_factory                     # QC R1: wrong only on per-drone writes
    worse, _ = T.agreement(GATES, w6, "cpu", bad_partial_factory(n, m, params, "cpu"), torch_world, games=n)
    assert not worse["pass"] and worse["max_gap_m"] > worse["limit_m"]


def test_stop_between_ticks(worlds):
    w5, _ = worlds
    calls = []
    with pytest.raises(T.Stopped):
        T.play_t41(GATES, w5, "cpu", games=2, max_steps=50, should_stop=lambda: calls.append(1) or len(calls) > 5)


# ------------------------------------------------------------------------------------------------ the checks
def test_known_answer_checks(tmp_path):
    ref = np.full(10, GUARD_WIN, dtype=np.int8)
    ref[:3] = STRIKE_WIN
    f = tmp_path / "pg.npz"
    np.savez(f, **{"delay_0.1482__outcome": ref})
    g = {**GATES, "controls": {**GATES["controls"], "t45_per_game": str(f), "t45_per_game_sha256": T.sha256_file(f),
                               "t45_holds": 7}}
    assert T.check_t45(g, {"outcome": ref.copy()}, root=Path("/"))["pass"]
    other = ref.copy()
    other[[3, 0]] = other[[0, 3]]                          # same count, two games swapped: must fail
    r = T.check_t45(g, {"outcome": other}, root=Path("/"))
    assert not r["pass"] and r["games_differing_from_t45"] == 2
    assert not T.check_t45({**g, "controls": {**g["controls"], "t45_per_game_sha256": "0" * 64}}, {"outcome": ref},
                           root=Path("/"))["pass"]
    reach = lambda k: {"outcome": np.array([STRIKE_WIN] * k + [GUARD_WIN] * (1000 - k), dtype=np.int8)}  # noqa: E731
    assert T.check_parked(GATES, reach(524))["pass"] and not T.check_parked(GATES, reach(571))["pass"]
    assert T.sign_test_p(0, 5) == pytest.approx(0.0625) and T.sign_test_p(3, 3) == 1.0
    p = T.paired(np.array([GUARD_WIN, GUARD_WIN, STRIKE_WIN, STRIKE_WIN]), np.array([GUARD_WIN, STRIKE_WIN, GUARD_WIN,
                                                                                      STRIKE_WIN]))
    assert (p["both_hold"], p["lost_here"], p["gained_here"], p["both_lost"]) == (1, 1, 1, 1)


# ------------------------------------------------------------------------------------------------ the driver
@pytest.fixture
def run_dirs(tmp_path):
    base = ROOT / "runs" / "pytest_l03" / tmp_path.name
    yield base / "cpu", base / "gpu"
    shutil.rmtree(base, ignore_errors=True)
    if base.parent.is_dir() and not any(base.parent.iterdir()):
        base.parent.rmdir()


@needs_t45
def test_driver_parts_on_the_cpu(run_dirs):
    import ste_transfer_l03 as D
    cpu, gpu = run_dirs
    small = ["--games", "3", "--max-steps", "30"]
    # part isaac refuses before part cpu has passed C-1, and without --headless
    assert D.main(["--part", "isaac", "--run-dir", str(gpu), "--cpu-run", str(cpu), "--cap-h", "1", "--headless",
                   *small]) == 2
    assert D.main(["--part", "cpu", "--run-dir", str(cpu), "--cap-h", "1", *small]) == 0
    assert D.main(["--part", "isaac", "--run-dir", str(gpu), "--cpu-run", str(cpu), "--cap-h", "1", *small]) == 2
    assert D.main(["--part", "isaac", "--run-dir", str(gpu), "--cpu-run", str(cpu), "--cap-h", "1", "--dry-cpu",
                   *small]) == 0
    res = json.loads((gpu / "results.json").read_text())
    assert set(res["arms"]) == {"t1_cpu_t41", "t2_parked", "t2_t41", "t1_cuda_t41"} and res["smoke"]
    assert res["controls"]["C-0"]["pass"] and res["controls"]["C-3"]["pass"] and res["controls_all_pass"]
    assert "C-2" in res["controls"] and "C-3b" in res["info"] and "C-3b" not in res["controls"]
    assert res["t1_cuda_v_t1_cpu"]["outcomes_differ"] == 0            # the same tier 1 game twice on the CPU
    assert "SMOKE" in (gpu / "results.md").read_text()
    import make_ste_l03_record as R
    res_full = {**res, "smoke": False}
    for arm in res_full["arms"].values():                   # unfinished smoke games have no rates: fill for the writer
        arm["summary"].update({k: 0.0 for k, v in arm["summary"].items() if v is None and k != "ci"})
        arm["summary"]["ci"] = [0.0, 0.0]
    text, row = R.record_text(gpu, cpu, res_full, "pytest_l03", "T0")
    for head in ("## Purpose", "## Results", "## Gates", "## Videos", "Verdict: **ABORTED**"):
        assert head in text
    assert row.startswith("| T0 |")
    assert R.main(["--run-dir", str(gpu), "--cpu-run", str(cpu), "--number", "T0", "--out-dir", str(gpu)]) == 1   # smoke
    # the same command resumes: every arm done, nothing plays again
    assert D.main(["--part", "isaac", "--run-dir", str(gpu), "--cpu-run", str(cpu), "--cap-h", "1", "--dry-cpu",
                   *small]) == 0


@needs_t45
def test_failed_control_is_terminal(run_dirs):
    import ste_transfer_l03 as D
    cpu, _ = run_dirs
    cpu.mkdir(parents=True)
    (cpu / D.CONTROLS_FILE).write_text(json.dumps({"C-1": {"pass": False}}))
    assert D.main(["--part", "cpu", "--run-dir", str(cpu), "--cap-h", "1", "--games", "2", "--max-steps", "5"]) == 6


def test_part_isaac_refuses_before_isaac_starts(tmp_path):
    import ste_transfer_l03 as D
    cpu = tmp_path / "cpu"
    cpu.mkdir()
    base = ["--part", "isaac", "--run-dir", str(tmp_path / "gpu"), "--cpu-run", str(cpu)]
    assert "headless" in D.pre_isaac_problem(base)
    assert "cpu-run" in D.pre_isaac_problem([*base, "--headless"])
    (cpu / D.CONTROLS_FILE).write_text(json.dumps({"C-1": {"pass": False}}))
    assert "C-1" in D.pre_isaac_problem([*base, "--headless"])
    (cpu / D.CONTROLS_FILE).write_text(json.dumps({"C-1": {"pass": True, "not_checked": "smoke run"}}))
    assert "C-1" in D.pre_isaac_problem([*base, "--headless"])                        # a smoke C-1 is not of record
    assert D.pre_isaac_problem([*base, "--headless", "--games", "4"]) is None
    (cpu / D.CONTROLS_FILE).write_text(json.dumps({"C-1": {"pass": True}}))
    assert D.pre_isaac_problem([*base, "--headless"]) is None


# ------------------------------------------------------------------------------------------------ QC fix round (21 Nov)
def test_t41_plays_one_mean_action_per_decision(worlds):
    """T41 as scored: one decision per 12 ticks, the network's mean action (kills mutants M12, M13)."""
    w5, _ = worlds
    guard, _ = T.t41_players(GATES, w5, 2, "cpu")
    assert guard.hold == 12 and guard.inner.deterministic is True


def small_args(cpu, gpu):
    return ["--part", "isaac", "--run-dir", str(gpu), "--cpu-run", str(cpu), "--cap-h", "1", "--dry-cpu",
            "--games", "2", "--max-steps", "5"]


@needs_t45
def test_nonfinite_parked_arm_is_terminal_and_c2_checked_first(run_dirs, monkeypatch):
    """QC L02-3: C-2 is saved before exit 5; a relaunch after exit 5 refuses (exit 2), never skips to INFO (M15, M16)."""
    import ste_transfer_l03 as D
    cpu, gpu = run_dirs
    assert D.main(["--part", "cpu", "--run-dir", str(cpu), "--cap-h", "1", "--games", "2", "--max-steps", "5"]) == 0
    real = T.play_parked

    def bad(*a, **k):
        res, extras = real(*a, **k)
        res.nonfinite_actions[0] = 1
        return res, extras
    monkeypatch.setattr(T, "play_parked", bad)
    assert D.main(small_args(cpu, gpu)) == 5
    assert "C-2" in D.read_controls(gpu) and (gpu / D.TERMINAL_FILE).is_file()
    monkeypatch.setattr(T, "play_parked", real)
    assert D.main(small_args(cpu, gpu)) == 2
    assert D.pre_isaac_problem([*small_args(cpu, gpu)[:6], "--headless", "--games", "2"]) is not None


@needs_t45
def test_c2_is_checked_on_resume_when_the_arm_was_saved_without_it(run_dirs):
    """A process that died between saving the parked arm and C-2: the relaunch checks C-2 from the arm file."""
    import ste_transfer_l03 as D
    cpu, gpu = run_dirs
    assert D.main(["--part", "cpu", "--run-dir", str(cpu), "--cap-h", "1", "--games", "2", "--max-steps", "5"]) == 0
    assert D.main(small_args(cpu, gpu)) == 0
    c = D.read_controls(gpu)
    del c["C-2"]
    (gpu / D.CONTROLS_FILE).write_text(json.dumps(c))
    assert D.main(small_args(cpu, gpu)) == 0
    assert "C-2" in D.read_controls(gpu)


def test_record_requires_every_named_control(tmp_path):
    """QC L02-6/7: a missing or failed control makes the record ABORTED and its ledger row leads with ABORTED, not a
    rate (kills M17)."""
    import make_ste_l03_record as R
    import ste_transfer_l03 as D
    summary = {"games": 1000, "count": 800, "rate": 0.8, "ci": [0.77, 0.82], "counted": "holds",
               "closest_3d_min_m": 0.9, "closest_3d_median_m": 1.5, "rule_breach_share": 0.0, "filter_share": 0.3,
               "mean_end_step": 2000.0, "nonfinite_actions": 0, "upset_games": 0}
    arm = {"tier": 2, "row": "6", "device": "cuda", "gpu": "GPU", "summary": summary, "game_steps_per_s": 1.0}
    good = {c: {"pass": True} for c in D.REQUIRED_CONTROLS}
    base = {"stopped": None, "gates_sha256": "x", "smoke": False, "references": GATES["references"], "info": {},
            "arms": {"t1_cpu_t41": {**arm, "tier": 1, "row": "5"}, "t2_t41": arm, "t2_parked": {**arm, "summary": {
                **summary, "counted": "reaches", "count": 520}}}}
    (tmp_path / "exit_code").write_text("0\n")
    for controls, want in ((good, "INFO"), ({**good, "C-2": {"pass": False}}, "ABORTED"),
                           ({k: v for k, v in good.items() if k != "C-2"}, "ABORTED")):
        res = {**base, "controls": controls, **D.control_summary(controls)}
        text, row = R.record_text(tmp_path, tmp_path, res, "x", "T0")
        assert f"Verdict: **{want}" in text, controls
        assert (" | ABORTED |" in row) == (want == "ABORTED")
        if want == "ABORTED":
            assert "rates void" in row and "800 / 1000" not in row


def test_t45_file_is_checked_before_the_cpu_part_plays(tmp_path, run_dirs):
    """QC L02-8: a missing or wrong T45 per-game file refuses at the start (exit 2), not after a 1,000-game arm."""
    import ste_transfer_l03 as D
    cpu, _ = run_dirs
    g = tmp_path / "g.toml"
    g.write_text(GATES["path"].read_text().replace('t45_per_game = "runs/2026-11-21_ste_l014/response/per_game.npz"',
                                                    't45_per_game = "runs/no_such/per_game.npz"'))
    assert any("t45" in p for p in T.pin_problems(T.load_gates(g)))
    assert D.main(["--part", "cpu", "--run-dir", str(cpu), "--gates", str(g), "--cap-h", "1", "--games", "2"]) == 2
    assert not (cpu / D.ARMS).exists()


@needs_t45
def test_record_only_keeps_the_runs_own_ending(run_dirs):
    import ste_transfer_l03 as D
    cpu, gpu = run_dirs
    assert D.main(["--part", "cpu", "--run-dir", str(cpu), "--cap-h", "1", "--games", "2", "--max-steps", "5"]) == 0
    assert D.main(small_args(cpu, gpu)) == 0
    assert D.main(["--part", "record", "--run-dir", str(gpu), "--cpu-run", str(cpu)]) == 0
    assert json.loads((gpu / "results.json").read_text())["stopped"] is None


def test_missing_controls_read_as_failed_in_results_md():
    """N14: control_summary counts a missing required control as a failure, and results.md says so."""
    import ste_transfer_l03 as D
    s = D.control_summary({"C-0": {"pass": True}, "C-1": {"pass": True}, "C-3": {"pass": True}})
    assert not s["controls_all_pass"] and s["controls_missing"] == ["C-2"]
    md = D.render_md({"controls": {}, "arms": {}, "references": GATES["references"], "smoke": False, "stopped": None,
                      "info": {}, **s})
    assert "CONTROLS FAILED" in md and "C-2" in md
