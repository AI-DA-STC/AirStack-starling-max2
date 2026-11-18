"""Phase 5 pilot glue (plan docs/plans/2026-11-18-nus-phase5-retraining.md section 9, Tasks P-T2 to P-T5), CPU, marker local files:
fresh training starts (``nus/train_game.py``), the stand-in trainer's ``--game nus_hangar`` path for both teams (``nus/pilot.py``), the hard
wall-clock cap, the GPU-hours ledger, the pilot videos, and the pilot tables. No numeric literal (G2): constants live in the fixture."""
from __future__ import annotations

import ast
import json
import math
import sys
import tomllib

import pytest
import torch

import _nus_markers  # noqa: F401  (puts source/ and scripts/ on the path)
from _nus_markers import ROOT
from _nus_phase4_fixture import (BEARING_TOL, CAP_LEFT_H, EVAL_TICKS, MOMENT_REL, P4_GAMES, PILOT_GAMES, PILOT_TIMESTEPS, START_DRAWS,
                                 build)
from svg_training.nus import hangar as hangar_mod, ladder
from svg_training.nus import pilot
from svg_training.nus.replica import NusReplica
from svg_training.nus.train_game import NusHangarTrainGame, draw_train_starts

sys.path.insert(0, str(ROOT / "scripts"))
import train_standin  # noqa: E402

PHASE5 = ROOT / "configs" / "nus_phase5.toml"


@pytest.fixture
def world(tmp_path, monkeypatch):
    w = build(tmp_path, monkeypatch)
    monkeypatch.setattr(hangar_mod, "LOCAL_HANGAR", w.folder / "nus_hangar.toml")
    monkeypatch.setattr(ladder, "load_starts", lambda path=None: w.starts)
    monkeypatch.setattr(pilot, "GPU_HOURS_LOG", tmp_path / "gpu_hours.log")
    return w


def _train_game(w, seed=1, n=P4_GAMES, **kw):
    row = w.rows["5"]
    return NusHangarTrainGame(w.cfg("5"), w.geo, row, w.rules, w.guards, w.strikes, num_games=n, device="cpu", seed=seed,
                              jitter_m=w.settings["ladder"]["jitter_m"], **kw)


# ------------------------------------------------------------------------------------------------ P-T2 training starts
def test_two_resets_give_different_starts_and_a_seed_reproduces_them(world):
    g = _train_game(world)
    first = g.pos_m.clone()
    g.reset()
    assert not torch.equal(first, g.pos_m)
    again = _train_game(world)
    assert torch.equal(first, again.pos_m)                                    # same seed: same first starts
    other = _train_game(world, seed=2)
    assert not torch.equal(first, other.pos_m)
    assert g._video is None                                                    # recording off by default


def test_finished_games_restart_from_fresh_starts(world):
    g = _train_game(world)
    before = g.pos_m.clone()
    done = torch.zeros(g.num_games, dtype=torch.bool)
    done[0] = True
    g._new_games(done)
    assert not torch.equal(before[0], g.pos_m[0]) and torch.equal(before[1:], g.pos_m[1:])


def test_start_distribution_matches_the_replica(world):
    w = world
    gen = torch.Generator().manual_seed(1)
    ours = draw_train_starts(NusReplica(w.rules), START_DRAWS, gen, w.geo.scale_m_per_unit, w.geo.height_m,
                             w.settings["ladder"]["jitter_m"])
    units = ours[..., :2] / w.geo.scale_m_per_unit
    ref = NusReplica(w.rules).reset(START_DRAWS, generator=torch.Generator().manual_seed(2), random_start=True).pos
    for team in (slice(0, w.guards), slice(w.guards, None)):
        r_ours, r_ref = units[:, team].norm(dim=-1), ref[:, team].norm(dim=-1)
        for stat in (torch.mean, torch.std):
            assert float(stat(r_ours)) == pytest.approx(float(stat(r_ref)), rel=MOMENT_REL, abs=MOMENT_REL * float(r_ref.mean()))
        bearing = torch.atan2(units[:, team, 1], units[:, team, 0])
        assert abs(float(bearing.cos().mean())) < BEARING_TOL and abs(float(bearing.sin().mean())) < BEARING_TOL
    z = ours[..., 2] - w.geo.height_m
    assert float(z.abs().max()) <= w.settings["ladder"]["jitter_m"] and float(z.std()) > 0


def test_train_game_refuses_the_phase4_starts_seed(world):
    with pytest.raises(ValueError, match="Phase 4"):
        _train_game(world, seed=world.settings["ladder"]["seed"])


def test_no_python_loop_in_the_train_game():
    tree = ast.parse((ROOT / "source/svg_training/nus/train_game.py").read_text())
    loops = [n for n in ast.walk(tree) if isinstance(n, (ast.For, ast.While, ast.comprehension))]
    assert not loops


# ------------------------------------------------------------------------------------------------ P-T5 tables
def test_pilot_tables_load_and_the_caps_fit_the_pilots_budget():
    d = tomllib.loads(PHASE5.read_text())
    total = d["pilots"]["total_gpu_hours"]
    caps = d["probe"]["gpu_cap_hours"] + d["pilot_p1"]["gpu_cap_hours"] + d["pilot_p2"]["gpu_cap_hours"] + \
        2 * (d["pilot_p3_guard"]["gpu_cap_hours"] + d["pilot_p3_strike"]["gpu_cap_hours"])
    assert caps <= total
    for name in pilot.PILOT_TABLES:
        t = d[name]
        assert t["preset"] == "nus_hangar" and t["algorithm"] == "IPPO" and t["train_team"] in ("guard", "strike")
        assert math.isclose(sum(t["opponent_mix"].values()), 1) and t["num_games"] == d["probe"]["pilot_max_games"]
        assert t["frozen_log_std_axes"]["starling"] == ["yaw"] and t["eval_games_early"] <= t["eval_games"]
    assert set(pilot.PILOT_TABLES) <= set(train_standin.SETTINGS_TABLES)


# ------------------------------------------------------------------------------------------------ GPU-hours ledger and the cap
def test_gpu_hours_log_appends_and_sums(tmp_path):
    log = tmp_path / "pilots" / "gpu_hours.log"
    assert pilot.logged_hours(log) == 0
    pilot.append_gpu_hours(log, "a", 0.0, pilot.HOUR_S / 2)
    pilot.append_gpu_hours(log, "b", pilot.HOUR_S, pilot.HOUR_S * 2)
    assert pilot.logged_hours(log) == pytest.approx(1 + 1 / 2)
    assert len([ln for ln in log.read_text().splitlines() if not ln.startswith("#")]) == 2


def test_cap_rules():
    d = tomllib.loads(PHASE5.read_text())
    h, cap, total = pilot.HOUR_S, d["pilot_p1"]["gpu_cap_hours"], d["pilots"]["total_gpu_hours"]
    assert pilot.effective_cap_s(cap, total, 0) == pytest.approx(cap * h)
    assert pilot.effective_cap_s(cap, total, total - cap / 2) == pytest.approx(cap / 2 * h)      # the pilots' budget binds
    assert pilot.must_stop(elapsed_s=h, reserve_s=cap * h - h, cap_s=cap * h) is False
    assert pilot.must_stop(elapsed_s=h, reserve_s=cap * h - h + 1, cap_s=cap * h) is True


# ------------------------------------------------------------------------------------------------ P-T3/P-T4: the trainer, both teams
def _pilot_args(tmp_path, table, *extra):
    return ["--game", "nus_hangar", "--settings", table, "--seed", "1", "--name", f"p_{table}", "--device", "cpu",
            "--num-games-override", str(PILOT_GAMES), "--timesteps-override", str(PILOT_TIMESTEPS), "--eval-games", str(P4_GAMES),
            "--eval-max-steps", str(EVAL_TICKS), "--runs-dir", str(tmp_path / "runs"), *extra]


def _in_process(argv):
    threads = torch.get_num_threads()
    try:
        return train_standin.main(argv)
    finally:
        torch.set_num_threads(threads)


@pytest.mark.parametrize("table", ["pilot_p1", "pilot_p3_strike"])
def test_pilot_runs_for_both_teams_with_videos_and_a_gpu_hours_line(world, tmp_path, table):
    before = {p for p in tmp_path.rglob("*")}
    assert _in_process(_pilot_args(tmp_path, table)) == 0
    run = tmp_path / "runs" / f"p_{table}"
    meta = tomllib.loads((run / "interface.toml").read_text())
    team = tomllib.loads(PHASE5.read_text())[table]["train_team"]
    assert meta["team"] == team and meta["preset"] == "nus_hangar" and meta["game"] == "nus_hangar"
    assert meta["guards"] == world.guards and meta["strikes"] == world.strikes and meta["local_file"].startswith("sha256")
    res = json.loads((run / "train_result.json").read_text())
    assert res["status"] == "FINISHED" and res["timesteps_done"] == PILOT_TIMESTEPS and res["train_team"] == team
    curve = json.loads((run / "curve.json").read_text())
    evaluations = [c["kind"] for c in curve]
    assert evaluations[-1] == "final" and ("start" in evaluations) == tomllib.loads(PHASE5.read_text())[table]["eval_at_start"]
    videos = sorted((run / "videos").glob("*.mp4"))
    assert videos and any("final" in v.name for v in videos) and any("best" in v.name for v in videos)
    assert (run / "agent_best.pt").exists() and (run / "agent.pt").exists()
    lines = [ln for ln in pilot.GPU_HOURS_LOG.read_text().splitlines() if not ln.startswith("#")]
    assert len(lines) == 1 and lines[0].split()[0] == f"p_{table}"
    new = {p for p in tmp_path.rglob("*")} - before
    outside = [p for p in new if p.is_file() and (tmp_path / "runs") not in p.parents and p != pilot.GPU_HOURS_LOG]
    assert not outside, outside                                                 # videos and outputs only under runs/


def test_warm_start_and_no_eval_at_start(world, tmp_path):
    assert _in_process(_pilot_args(tmp_path, "pilot_p1")) == 0
    first = tmp_path / "runs" / "p_pilot_p1"
    args = _pilot_args(tmp_path, "pilot_p2", "--warm-start", str(first), "--no-eval-at-start")
    assert _in_process(args) == 0
    run = tmp_path / "runs" / "p_pilot_p2"
    curve = json.loads((run / "curve.json").read_text())
    assert [c["kind"] for c in curve] == ["final"]
    assert tomllib.loads((run / "interface.toml").read_text())["training"]["warm_start"] == str(first)
    bad = _pilot_args(tmp_path, "pilot_p3_strike", "--warm-start", str(first))
    bad[bad.index("--name") + 1] = "wrong_team"
    assert _in_process(bad) == 2                                               # a Guard run cannot warm-start a Strike learner


def test_half_way_evaluation_and_the_hard_cap_stop(world, tmp_path, monkeypatch):
    monkeypatch.setattr(train_standin, "estimate_eval_s", lambda *a, **k: 0.0)
    monkeypatch.setattr(pilot, "mid_point_s", lambda *a, **k: 0.0)          # the half-way point at the first update
    two = _pilot_args(tmp_path, "pilot_p1")
    two[two.index("--timesteps-override") + 1] = str(PILOT_TIMESTEPS * 2)
    assert _in_process(two) == 0
    run = tmp_path / "runs" / "p_pilot_p1"
    assert [c["kind"] for c in json.loads((run / "curve.json").read_text())] == ["start", "mid", "final"]
    capped = two + ["--cap-min-override", str(CAP_LEFT_H)]                     # 0.0006 s: passed at the first update
    capped[capped.index("--name") + 1] = "capped"
    assert _in_process(capped) == 0
    res = json.loads((tmp_path / "runs" / "capped" / "train_result.json").read_text())
    assert res["stopped_by_wall_clock_cap"] and res["timesteps_done"] == PILOT_TIMESTEPS and "dropped" in res["mid_note"]
    assert [c["kind"] for c in json.loads((tmp_path / "runs" / "capped" / "curve.json").read_text())] == ["start", "final"]


def test_a_crash_still_writes_the_gpu_hours_line(world, tmp_path, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("injected by the test")
    monkeypatch.setattr(pilot, "eval_clips", boom)
    with pytest.raises(RuntimeError, match="injected"):
        _in_process(_pilot_args(tmp_path, "pilot_p1"))
    lines = [ln for ln in pilot.GPU_HOURS_LOG.read_text().splitlines() if not ln.startswith("#")]
    assert len(lines) == 1 and "CRASHED: RuntimeError" in lines[0]


def test_refusals(world, tmp_path):
    assert _in_process(_pilot_args(tmp_path, "pilot_p1", "--motion", "physics")) == 2
    s2_table = _pilot_args(tmp_path, "standin_v2")
    assert _in_process(s2_table) == 2                                          # an S2 table on the NUS game
    on_s2 = _pilot_args(tmp_path, "pilot_p1")
    on_s2[on_s2.index("nus_hangar")] = "s2"
    assert _in_process(on_s2) == 2                                             # a pilot table on the S2 game
    seeded = _pilot_args(tmp_path, "pilot_p1")
    seeded[seeded.index("--seed") + 1] = str(world.settings["ladder"]["seed"])
    assert _in_process(seeded) == 2                                            # never the Phase 4 starts seed
    total = tomllib.loads(PHASE5.read_text())["pilots"]["total_gpu_hours"]
    pilot.append_gpu_hours(pilot.GPU_HOURS_LOG, "earlier", 0.0, (total - CAP_LEFT_H) * pilot.HOUR_S)
    assert _in_process(_pilot_args(tmp_path, "pilot_p1")) == 2                 # less than one evaluation left
    assert not (tmp_path / "runs" / "p_pilot_p1").exists()


# ------------------------------------------------------------------------------------------------ P1b: zero-mean start and decision hold
from _nus_phase4_fixture import FAKE_DONE_TICK, FAKE_GAMES, HOLD_TEST  # noqa: E402


def test_zero_mean_head_gives_the_zero_action_and_still_learns():
    from svg_training.core.observations import OBS_DIM
    from svg_training.opponents.learned import make_models
    hidden = tomllib.loads(PHASE5.read_text())["pilot_p1b"]["hidden"]
    pol = make_models(["guard_0"], hidden, "cpu")["guard_0"]["policy"]
    before = pol.log_std.detach().clone()
    pilot.zero_mean_head(pol)
    obs = torch.randn(PILOT_GAMES, OBS_DIM, generator=torch.Generator().manual_seed(1))
    out = pol.net(obs)
    assert torch.equal(out, torch.zeros_like(out)) and torch.equal(pol.log_std.detach(), before)
    out.sum().backward()                                                        # the zeroed layer still gets a gradient
    last = [m for m in pol.net if isinstance(m, torch.nn.Linear)][-1]
    assert float(last.weight.grad.abs().sum()) > 0


class _FakeEnv:
    """Two agents, FAKE_GAMES games; reward 1 per tick per game; game 0 ends at tick FAKE_DONE_TICK (then a new game starts)."""
    possible_agents = ["guard_0", "guard_1"]

    def __init__(self):
        self.tick = 0
        self.seen = []

    def step(self, actions):
        self.tick += 1
        self.seen.append(actions["guard_0"].clone())
        done = torch.zeros(FAKE_GAMES, 1, dtype=torch.bool)
        done[0] = self.tick == FAKE_DONE_TICK
        ones = torch.ones(FAKE_GAMES, 1)
        obs = {a: torch.full((FAKE_GAMES, 1), float(self.tick)) for a in self.possible_agents}
        info = {"nonfinite_actions": torch.ones(FAKE_GAMES, dtype=torch.long), "upset": done[:, 0].clone()}
        return obs, {a: ones for a in self.possible_agents}, {a: done for a in self.possible_agents}, \
            {a: torch.zeros_like(done) for a in self.possible_agents}, info

    def reset(self):
        return {a: torch.zeros(FAKE_GAMES, 1) for a in self.possible_agents}, {}


def test_decision_hold_repeats_the_action_sums_rewards_until_the_end_and_flags_it():
    env = pilot.DecisionHoldEnv(_FakeEnv(), HOLD_TEST)
    act = {a: torch.full((FAKE_GAMES, 1), float(k + 1)) for k, a in enumerate(env.possible_agents)}
    obs, rew, term, trunc, info = env.step(act)
    inner = env.env
    assert inner.tick == HOLD_TEST and all(torch.equal(x, act["guard_0"]) for x in inner.seen)   # the same action every tick
    assert float(obs["guard_0"][0]) == HOLD_TEST                                # the observation after the last tick
    assert float(rew["guard_0"][0]) == FAKE_DONE_TICK and float(rew["guard_0"][1]) == HOLD_TEST   # game 0: rewards until its end only
    assert bool(term["guard_0"][0]) and not bool(term["guard_0"][1:].any()) and not bool(trunc["guard_0"].any())
    assert int(info["nonfinite_actions"][0]) == HOLD_TEST and bool(info["upset"][0])           # summed and or-ed over the hold
    assert env.possible_agents == inner.possible_agents                         # everything else is the inner environment's


def test_held_strategy_acts_every_hold_ticks_and_repeats_in_between():
    class Count:
        team, name = "guard", "count"

        def __init__(self):
            self.calls = 0

        def reset(self, games):
            pass

        def act(self, obs):
            self.calls += 1
            return torch.full((obs.shape[0], 1, 1), float(self.calls))
    held = pilot.HeldStrategy(Count(), HOLD_TEST)
    obs = torch.zeros(FAKE_GAMES, 1, 1)
    got = [float(held.act(obs)[0, 0, 0]) for _ in range(HOLD_TEST * 2)]
    assert got == [1.0] * HOLD_TEST + [2.0] * HOLD_TEST and held.team == "guard"     # asked on decision ticks only, repeated between


def test_no_loop_over_games_in_the_hold_code():
    tree = ast.parse((ROOT / "source/svg_training/nus/pilot.py").read_text())
    for cls in [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name in ("DecisionHoldEnv", "HeldStrategy")]:
        for loop in [n for n in ast.walk(cls) if isinstance(n, (ast.For, ast.While, ast.comprehension))]:
            text = ast.unparse(loop.iter if not isinstance(loop, ast.While) else loop.test)
            assert "hold" in text or "agents" in text or "items()" in text, text     # ticks of the hold or agent names, never games


def test_p1b_start_evaluation_equals_the_zero_action_arm(world, tmp_path):
    from svg_training.core.metrics import summarise
    from svg_training.core.play import play_match
    from svg_training.opponents.scripted import make_strategy
    args = ["--game", "nus_hangar", "--settings", "pilot_p1b", "--seed", "1", "--name", "p1b", "--device", "cpu",
            "--num-games-override", str(PILOT_GAMES), "--timesteps-override", "1", "--eval-games", str(P4_GAMES),
            "--runs-dir", str(tmp_path / "runs")]
    assert _in_process(args) == 0
    run = tmp_path / "runs" / "p1b"
    start = json.loads((run / "curve.json").read_text())[0]
    assert start["kind"] == "start"
    meta = tomllib.loads((run / "interface.toml").read_text())["training"]
    assert meta["decision_ticks"] == world.geo.hold_ticks and meta["zero_mean_init"] is True
    st = tomllib.loads(PHASE5.read_text())["pilot_p1b"]
    pw = pilot.pilot_world(st["shaping_weight"])
    seed, eval_seed = 1, 1 + train_standin.EVAL_SEED_OFFSET
    _, evals = pilot.pilot_games(pw, PILOT_GAMES, [P4_GAMES], "cpu", seed, eval_seed)
    game = evals[P4_GAMES]
    opp = pilot.mix_strategy(train_standin.mix_slices(st["opponent_mix"], P4_GAMES), "strike", pw.cfg, "cpu", eval_seed + train_standin.OPPONENT_SEED_OFFSET)
    game.gen.manual_seed(eval_seed)
    res = play_match(game, make_strategy("zero", "guard", pw.cfg, P4_GAMES, "cpu", 0), opp)
    zero = summarise(res, by=())
    ours = start["overall"]
    if not zero:
        assert ours is None
    else:
        assert ours["guard_wins"] == zero[0]["guard_wins"] and ours["games"] == zero[0]["games"]
        assert ours["mean_end_step"] == pytest.approx(zero[0]["mean_end_step"])
