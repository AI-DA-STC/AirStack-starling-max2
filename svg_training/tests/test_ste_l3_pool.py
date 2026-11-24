"""STE phase L3, slice 3, step 2: the opponent pool in training and the pooled scoring row (design note
ste_learning/drafts/L3_SLICE3_DESIGN.md §2 and "Revision after the review"; lead's answers 2 and 3).

* ``ste/pool.OpponentPool``: every script of the other team except ``random``, one per game, uniform, drawn by
  ``pool_draw(seed, slot, k)``; k = 0 drawn at construction; a batched gather (every script runs, each game takes its
  own); the counter advances at the decision-boundary restart only; its name is what ``trained_against`` reports.
* Off (no ``[pool]``, or ``enabled = false``): today's fixed opponent, bit for bit.
* The train log carries the per-opponent sample share of every update.
* The pooled row: the exact mean of the K cell rates on the shared starts with a stratified interval, trivial cells
  flagged, the worst cell the headline; the best single fixed choice over the pool; for the skills route, the choice
  share by decision index.
CPU only."""
import json
import math
import sys
from pathlib import Path

import numpy as np
import pytest
import torch

from svg_training.core.observations import ObsView
from svg_training.opponents.scripted import make_strategy
from svg_training.ste import exploit, exploit_train, pool, scoring, shared, skills

from _ste_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import ste_exploit_l012 as driver  # noqa: E402

V = ObsView()
HOLD = 12
SMOKE = exploit.ROOT / "configs" / "ste_l012" / "smoke_gates.toml"
POOL = "\n[pool]\nenabled = true\nseed = 140001\n"
TWO_LEVEL = """
[learner]
action = "skills"
choice = "two_level"

[learner.team_strategies]
strike = ["strike_sacrifice", "strike_converge"]
guard = ["guard_parked_ring", "guard_field"]

[learner.drone_skills]
strike = ["strike_straight", "strike_flank", "strike_high", "strike_low"]
guard = ["guard_parked_centre", "guard_mark_edge", "guard_mirror"]

[learner.entropy_scale]
team = 0.01
drone = 0.01
"""


@pytest.fixture(scope="module")
def gates():
    return exploit.load_gates()


def other(side):
    return "guard" if side == "strike" else "strike"


def team_obs(gates, side, n=12, ticks=20, seed=5):
    cfg = exploit.variant_cfg(gates, "base")
    game = exploit_train.TrainGame(cfg, n, 3, 3, device="cpu", seed=seed)
    obs = game.reset()
    g = make_strategy("guard_mark_edge", "guard", cfg, n, "cpu", 0)
    s = make_strategy("strike_straight", "strike", cfg, n, "cpu", 0)
    for _ in range(ticks):
        obs = game.step({"guard": g.act(obs["guard"]), "strike": s.act(obs["strike"])}).obs
    return cfg, obs[side]


# ================================================================================================ OpponentPool
@pytest.mark.parametrize("team", ["guard", "strike"])
def test_the_pool_gathers_each_games_own_script(gates, team):
    cfg, obs = team_obs(gates, team)
    names = pool.pool_members(gates.players, team)
    p = pool.OpponentPool(team, names, cfg, obs.shape[0], "cpu", 140001)
    assert p.team == team and p.name == "OpponentPool(" + ",".join(names) + ")"
    want_draw = pool.pool_draw(140001, torch.arange(obs.shape[0]), torch.zeros(obs.shape[0], dtype=torch.long),
                               len(names))
    assert torch.equal(p.draw, want_draw) and bool((p.k == 0).all())         # k = 0 drawn at construction
    assert p.draw.unique().numel() > 1, "one opponent only: the test cannot see a mix-up"
    own = [make_strategy(nm, team, cfg, obs.shape[0], "cpu", 0).act(obs) for nm in names]
    got = p.act(obs)
    for i in range(obs.shape[0]):
        assert torch.equal(got[i], own[int(p.draw[i])][i])


def test_redraw_advances_the_counter_of_the_restarted_games_only_and_reset_keeps_the_draw(gates):
    cfg, _ = team_obs(gates, "guard")
    names = pool.pool_members(gates.players, "guard")
    p = pool.OpponentPool("guard", names, cfg, 8, "cpu", 7)
    before = p.draw.clone()
    p.reset(torch.ones(8, dtype=torch.bool))                                   # tick-level: no new draw
    assert torch.equal(p.draw, before) and bool((p.k == 0).all())
    mask = torch.tensor([True, False, True, False, False, False, False, True])
    p.redraw(mask)
    p.redraw(torch.tensor([True] + [False] * 7))
    assert p.k.tolist() == [2, 0, 1, 0, 0, 0, 0, 1]
    assert torch.equal(p.draw, pool.pool_draw(7, torch.arange(8), p.k, len(names)))
    saved = p.state()
    q = pool.OpponentPool("guard", names, cfg, 8, "cpu", 7)
    q.load_state(saved)
    assert torch.equal(q.k, p.k) and torch.equal(q.draw, p.draw)


@pytest.mark.parametrize("bad,why", [(["random", "guard_field"], "random"), ([], "empty"),
                                     (["guard_field", "nope"], "nope")])
def test_the_pool_refuses_random_an_empty_list_and_unknown_names(gates, bad, why):
    cfg, _ = team_obs(gates, "guard")
    with pytest.raises((ValueError, KeyError), match=why):
        pool.OpponentPool("guard", bad, cfg, 4, "cpu", 1)


def test_pool_members_are_the_other_teams_players_without_random(gates):
    players = dict(gates.players, guards=list(gates.players["guards"]) + ["random"])
    assert pool.pool_members(players, "guard") == list(gates.players["guards"])
    assert pool.pool_members(gates.players, "strike") == list(gates.players["strikes"])


# ================================================================================================ in DecisionEnv
def _env(gates, side, opponent, n=6, seed=7, spec=None):
    cfg = exploit.variant_cfg(gates, "base")
    game = exploit_train.TrainGame(cfg, n, 3, 3, device="cpu", seed=seed)
    return exploit_train.decision_env(game, HOLD, side, opponent, spec or skills.learner_spec(None), gates.players,
                                      seed)


def test_a_one_script_pool_trains_as_the_fixed_opponent_bit_for_bit(gates):
    cfg = exploit.variant_cfg(gates, "base")
    opp = exploit.opponent_of(gates, "base", "strike")

    def run(pooled):
        o = pool.OpponentPool("guard", [opp], cfg, 6, "cpu", 3) if pooled else make_strategy(opp, "guard", cfg, 6,
                                                                                               "cpu", 8)
        learner = exploit_train.Learner({**gates.trainer, "num_games": 6, "rollouts": 2, "learning_epochs": 1,
                                         "mini_batches": 1}, _env(gates, "strike", o), "cpu", seed=11)
        stats = [learner.update() for _ in range(2)]
        return learner.modules(), stats
    (a, sa), (b, sb) = run(False), run(True)
    for agent in a:
        for mod in ("policy", "value", "observation_preprocessor"):
            for k in a[agent][mod]:
                assert torch.equal(a[agent][mod][k], b[agent][mod][k]), (agent, mod, k)
    assert "opponent_share" not in sa[0] and sb[0]["opponent_share"] == {opp: 1.0}


def test_the_counter_advances_at_the_decision_boundary_only_and_the_share_is_logged(gates):
    cfg = exploit.variant_cfg(gates, "base")
    names = pool.pool_members(gates.players, "guard")
    p = pool.OpponentPool("guard", names, cfg, 8, "cpu", 9)
    env = _env(gates, "strike", p, n=8)
    env.reset()
    restarts = torch.zeros(8, dtype=torch.long)
    seen = 0
    for _ in range(12):
        draw_before = p.draw.clone()
        _, _, _, _, info = env.step({a: torch.zeros(8, 4) for a in env.possible_agents})
        assert torch.equal(info["opponent_draw"], draw_before)                  # the decision's own opponent
        restarts += info["decision_ended"].long()
        seen += int(info["decision_ended"].sum())
    assert seen > 0, "no game ended: the test has no power"
    assert torch.equal(p.k, restarts)                                          # not the tick-level (stale) resets
    learner = exploit_train.Learner({**gates.trainer, "num_games": 8, "rollouts": 3, "learning_epochs": 1,
                                     "mini_batches": 1}, _env(gates, "strike", pool.OpponentPool(
                                         "guard", names, cfg, 8, "cpu", 9), n=8), "cpu", seed=2)
    share = learner.update()["opponent_share"]
    assert set(share) == set(names) and math.isclose(sum(share.values()), 1.0)
    state = learner.state()
    assert torch.equal(state["opponent_pool"]["k"], learner.env.opponents["guard"].k)


def test_both_routes_see_the_same_opponent_for_the_same_slot_and_game_number(gates):
    """Different end patterns (the velocity route standing still, the two-level route flying its skills): per slot,
    the sequence of opponents by game number is the same prefix."""
    cfg = exploit.variant_cfg(gates, "base")
    names = pool.pool_members(gates.players, "guard")
    spec = skills.learner_spec({"action": "skills", "choice": "two_level",
                                "team_strategies": {"strike": ["strike_sacrifice", "strike_converge"],
                                                    "guard": ["guard_parked_ring", "guard_field"]},
                                "drone_skills": {"strike": ["strike_straight", "strike_flank", "strike_high",
                                                            "strike_low"],
                                                 "guard": ["guard_parked_centre", "guard_mark_edge", "guard_mirror"]},
                                "entropy_scale": {"team": 0.01, "drone": 0.01}})
    seqs = []
    for route in ("velocity", "two_level"):
        p = pool.OpponentPool("guard", names, cfg, 8, "cpu", 21)
        env = _env(gates, "strike", p, n=8, spec=spec if route == "two_level" else None)
        env.reset()
        per_slot = [[int(p.draw[g])] for g in range(8)]
        for _ in range(15):
            act = (torch.zeros(8, 4) if route == "velocity" else torch.zeros(8, 2, dtype=torch.long))
            _, _, _, _, info = env.step({a: act for a in env.possible_agents})
            for g in torch.nonzero(info["decision_ended"]).flatten().tolist():
                per_slot[g].append(int(p.draw[g]))
        seqs.append(per_slot)
    differ = 0
    for a, b in zip(*seqs):
        m = min(len(a), len(b))
        assert a[:m] == b[:m]
        differ += len(a) != len(b)
    assert differ > 0, "the two routes ended games at the same times: the test cannot see a timing dependence"


# ================================================================================================ the gate file
def test_the_pool_table_loads_and_is_off_by_default(gates, tmp_path):
    assert gates.pool == {"enabled": False}
    p = tmp_path / "g.toml"
    p.write_text(SMOKE.read_text() + POOL)
    assert exploit.load_gates(p).pool == {"enabled": True, "seed": 140001}
    for bad, why in (("\n[pool]\nenabled = true\n", "seed"), ("\n[pool]\nenabled = 1\nseed = 3\n", "enabled"),
                     ("\n[pool]\nenabled = true\nseed = 140001\nplayers = []\n", "unknown"),
                     (f"\n[pool]\nenabled = true\nseed = {exploit.load_gates(SMOKE).run['curve_seed']}\n", "seed")):
        p.write_text(SMOKE.read_text() + bad)
        with pytest.raises(ValueError, match=why):
            exploit.load_gates(p)


def test_build_learner_trains_on_the_pool_and_run0_keeps_its_fixed_opponent(tmp_path):
    p = tmp_path / "g.toml"
    p.write_text(SMOKE.read_text() + POOL)
    g = exploit.load_gates(p)
    learner = driver.build_learner(g, "base", "strike", 4, 1)
    opp = learner.env.opponents["guard"]
    assert isinstance(opp, pool.OpponentPool) and opp.names == pool.pool_members(g.players, "guard")
    assert driver.trained_against(learner) == opp.name
    fixed = driver.build_learner(g, "base", "strike", 4, 1, opponent=g.run0["opponent"])
    assert driver.trained_against(fixed) == "GuardParkedCentre"
    plain = driver.build_learner(exploit.load_gates(SMOKE), "base", "strike", 4, 1)
    assert not isinstance(plain.env.opponents["guard"], pool.OpponentPool)


# ================================================================================================ the pooled row
def test_the_pooled_row_is_the_exact_mean_with_an_interval_over_the_shared_starts():
    """QC S1 of step 2: the cells share their starts and the scoring is deterministic, so the cells are correlated;
    the interval comes from the per-start mean of the K win indicators (sd / sqrt(n) over the starts), not from
    independent cells. Hand computation on correlated cells (b repeats a on every start)."""
    a = np.array([1, 1, 0, 1, 0, 0, 1, 1, 0, 1], dtype=bool)
    cells = {"a": a, "b": a.copy(), "c": np.zeros(10, dtype=bool), "d": np.ones(10, dtype=bool)}
    row = scoring.pooled_row(cells)
    y = np.mean([cells[o].astype(float) for o in cells], axis=0)             # the per-start mean of the 4 indicators
    assert row["rate"] == pytest.approx(float(np.mean([v.mean() for v in cells.values()])))
    assert row["rate"] == pytest.approx(float(y.mean()))
    se = float(np.std(y, ddof=1) / math.sqrt(10))
    assert row["se"] == pytest.approx(se)
    assert row["ci"] == pytest.approx([max(0.0, y.mean() - 1.96 * se), min(1.0, y.mean() + 1.96 * se)])
    indep = math.sqrt(sum(v.mean() * (1 - v.mean()) / 10 for v in cells.values())) / 4
    assert row["se"] > indep                                     # the correlation the independent formula misses
    assert row["worst"] == {"opponent": "c", "k": 0, "n": 10, "rate": 0.0}
    assert row["headline"] == "worst cell" and sorted(row["trivial_cells"]) == ["c", "d"]
    assert row["members"] == ["a", "b", "c", "d"] and row["cells"]["a"]["k"] == 6
    with pytest.raises(ValueError, match="starts"):
        scoring.pooled_row({"a": a, "b": a[:5]})
    assert "unfinished game counts as no win" in row["interval"]          # QC S of step 3
    with pytest.raises(ValueError, match="no start"):
        scoring.pooled_row({"a": np.zeros(0, dtype=bool)})
    flat = scoring.pooled_row({"a": np.ones(6, dtype=bool), "b": np.zeros(6, dtype=bool)})
    assert flat["se"] == 0.0 and flat["ci"] == [0.5, 0.5] and "zero width" in flat["interval_note"]


def test_the_best_single_fixed_choice_over_the_pool_is_read_from_the_reference(gates):
    ref = exploit.load_reference(exploit.ROOT / gates.reference["file"])
    out = scoring.best_single_choice(ref, "base", "strike", skills.team_skills(gates.players, "strike") + ["random"],
                                     pool.pool_members(gates.players, "guard"), 50)
    assert "random" not in out["per_choice"]                           # QC NIT: never a choice of the pool
    assert "closed loop" in out["source"]
    for s, row in out["per_choice"].items():
        want = []
        for g in pool.pool_members(gates.players, "guard"):
            o = np.asarray(ref.cell("base", g, s)["outcome"][:50])
            want.append(float(np.sum(o == exploit.STRIKE_WIN)) / 50)
        assert row["rate"] == pytest.approx(sum(want) / len(want)), s
    assert out["best"] == max(out["per_choice"], key=lambda s: out["per_choice"][s]["rate"])


# ================================================================================================ the choice log
def test_held_player_logs_the_flown_choice_by_decision_index_for_live_drones_of_first_games(gates):
    cfg, obs = team_obs(gates, "strike", n=4)
    d = skills.two_level_dispatch(
        skills.learner_spec({"action": "skills", "choice": "two_level",
                             "team_strategies": {"strike": ["strike_sacrifice", "strike_converge"],
                                                 "guard": ["guard_parked_ring", "guard_field"]},
                             "drone_skills": {"strike": ["strike_straight", "strike_flank", "strike_high",
                                                         "strike_low"],
                                              "guard": ["guard_parked_centre", "guard_mark_edge", "guard_mirror"]},
                             "entropy_scale": {"team": 0.01, "drone": 0.01}}),
        gates.players, "strike", cfg, 4, "cpu", 0)
    team = exploit_train.untrained_skill_team("strike", d, 3, [16, 16], "cpu")
    held = exploit.HeldPlayer(team, HOLD)
    held.reset(torch.ones(4, dtype=torch.bool))
    obs = obs.clone()
    obs[0, 2] = 0.0                                                             # one drone out in game 0
    obs[0, 2, V.team] = 1.0
    for tick in range(2 * HOLD):
        if tick == HOLD - 1:
            held.reset(torch.tensor([False, True, False, False]))              # game 1's first game ended
        held.act(obs)
    log = held.choice_log
    first = d.names.index("strike_straight")                                     # free + the first drone skill
    assert log[0].tolist() == [11 if j == first else 0 for j in range(d.k)]     # 4 games x 3 drones, one out
    assert int(log[1].sum()) == 2 + 3 + 3 and int(log[2:].sum()) == 0          # game 1 no longer counted


def test_play_cells_keys_the_choice_logs_by_team_and_cell(gates):
    """QC NIT: a log is keyed (team, cell index), so a cell with a skills team on each side cannot collide."""
    ref = exploit.load_reference(exploit.ROOT / gates.reference["file"])
    cfg = exploit.variant_cfg(gates, "base")
    spec = skills.learner_spec({"action": "skills", "choice": "two_level",
                                "team_strategies": {"strike": ["strike_sacrifice", "strike_converge"],
                                                    "guard": ["guard_parked_ring", "guard_field"]},
                                "drone_skills": {"strike": ["strike_straight", "strike_flank", "strike_high",
                                                            "strike_low"],
                                                 "guard": ["guard_parked_centre", "guard_mark_edge", "guard_mirror"]},
                                "entropy_scale": {"team": 0.01, "drone": 0.01}})
    d = skills.two_level_dispatch(spec, gates.players, "strike", cfg, 2, "cpu", 0)
    team = exploit_train.untrained_skill_team("strike", d, 3, [16, 16], "cpu")
    cells = [("guard_parked_centre", exploit.EXPLOITER), ("guard_field", exploit.EXPLOITER)]
    pg = exploit.play_cells(cfg, "3v3", ref, cells, 2, "cpu", ref.meta["seed"], 300, learner=team, hold_ticks=HOLD)
    assert sorted(pg["choice_log"]) == [("strike", 0), ("strike", 1)]


def test_the_velocity_held_player_keeps_no_log(gates):
    team = exploit.LearnerTeam.untrained("guard", 3, [16, 16], "cpu")
    held = exploit.HeldPlayer(team, HOLD)
    held.reset(torch.ones(2, dtype=torch.bool))
    held.act(torch.zeros(2, 3, 71))
    assert held.choice_log is None


def test_choice_share_bins_the_decisions():
    log = np.zeros((256, 3), dtype=np.int64)
    log[0] = [3, 0, 0]
    log[1] = [1, 1, 1]
    log[4] = [0, 2, 0]
    out = scoring.choice_share(log, ["a", "b", "c"])
    assert "survivor" in out["note"]                                    # QC NIT: late bins hold the long games only
    assert out["bins"][0] == "0" and out["share"]["a"][0] == 1.0
    assert out["share"]["b"][1] == pytest.approx(1 / 3)
    assert out["share"]["b"][out["bins"].index("3-5")] == 1.0
    assert out["counts"][out["bins"].index("12+")] == 0


# ========================================================================================= the driver, end to end
@pytest.fixture(scope="module")
def pooled_runs(tmp_path_factory):
    """A velocity Guard run and a two-level Strike run, both on the pool (tiny, CPU)."""
    tmp = tmp_path_factory.mktemp("l3_pool")
    mp = pytest.MonkeyPatch()
    mp.setenv(shared.SHARED_ENV, str(tmp / "shared"))
    mp.setenv(shared.LEGACY_LOGS_ENV, "")
    out = {}
    vel = tmp / "v" / "gates.toml"
    vel.parent.mkdir()
    vel.write_text(SMOKE.read_text() + POOL)
    pj = tmp / "pilot_v.json"
    pj.write_text(json.dumps({"strike_recipe": {"recipe": exploit.RECIPE_BARE, "side_overrides_strike": {}}}))
    assert driver.main(["--gates", str(vel), "--variant", "base", "--side", "guard", "--run-dir", str(tmp / "guard"),
                        "--cap-h", "1", "--no-videos", "--pilot-json", str(pj)]) == 0
    out["guard"] = (vel, tmp / "guard")
    sk = tmp / "s" / "gates.toml"
    sk.parent.mkdir()
    sk.write_text(SMOKE.read_text() + POOL + TWO_LEVEL)
    g = exploit.load_gates(sk)
    pj = tmp / "pilot_s.json"
    pj.write_text(json.dumps({"strike_recipe": {"recipe": exploit.RECIPE_BARE, "side_overrides_strike": {}},
                              "learner": skills.learner_table(g.learner)}))
    r0 = tmp / "run0.json"
    r0.write_text(json.dumps({"status": "PASS", "complete": True, "cap_h": 1.0, "gates_sha256": g.sha256,
                              "learner": skills.learner_table(g.learner)}))
    assert driver.main(["--gates", str(sk), "--variant", "base", "--side", "strike", "--run-dir",
                        str(tmp / "strike"), "--cap-h", "1", "--no-videos", "--pilot-json", str(pj), "--run0-json",
                        str(r0)]) == 0
    out["strike"] = (sk, tmp / "strike")
    mp.undo()
    return out


def test_a_pool_run_logs_the_mix_and_reports_the_pooled_row(pooled_runs):
    for side, (g, r) in pooled_runs.items():
        gates = exploit.load_gates(g)
        members = pool.pool_members(gates.players, other(side))
        log = [json.loads(x) for x in (r / "train_log.jsonl").read_text().splitlines()]
        assert log and all(set(x["opponent_share"]) == set(members) for x in log)
        assert all(x["opponent"] == "OpponentPool(" + ",".join(members) + ")" for x in log)
        res = json.loads((r / "results.json").read_text())
        pooled = res["pooled"]
        assert pooled["members"] == members and pooled["headline"] == "worst cell"
        ev = np.load(r / "eval_info.npz")
        n = res["eval_games"]
        cells = driver.info_cells(gates, side)
        won = exploit.STRIKE_WIN if side == "strike" else exploit.GUARD_WIN
        rates = []
        for o in members:
            k = [c[0] if side == "strike" else c[1] for c in cells].index(o)
            rates.append(float(np.mean(ev["outcome"][k * n:(k + 1) * n] == won)))   # all games (unfinished: no win)
        assert pooled["rate"] == pytest.approx(sum(rates) / len(rates))
        assert any("g*" in x for x in res["pool_notes"]) and any("run 0" in x for x in res["pool_notes"])
        assert res["best_single_choice"]["best"] in skills.team_skills(gates.players, side)
        assert ("choice_by_decision" in res) == (side == "strike")          # the skills route only
    cbd = json.loads((pooled_runs["strike"][1] / "results.json").read_text())["choice_by_decision"]
    assert set(cbd) == set(pool.pool_members(exploit.load_gates(pooled_runs["strike"][0]).players, "guard"))
