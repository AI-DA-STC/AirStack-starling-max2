"""STE phase L3, slice 2, first build step: the two-level choice of owner ruling R30 (design note
ste_learning/drafts/L3_SLICE2_DESIGN.md, tests 1-3). No learning here: the networks are fixed.

1. The ``[learner] choice = "two_level"`` table: list A and list B load; every refusal names its reason.
2. The non-coordinating rule: a drone skill's command does not read the drone's own team-mates (perturbing only the
   own-team slots of the observation leaves it bit for bit unchanged); a team strategy's does.
3. Fixed-choice replay, on both paths (training: ``DecisionEnv`` on T44's starts; scoring: ``play_cells`` with
   ``HeldPlayer``): (a) each team strategy flown by the whole team = that script's T44 cell, game for game, against
   every script of the other team; (b) "free" with every drone on one drone skill = that script's T44 cell; (c) "free"
   with every mixed combination (Strike 4^3 = 64, Guard 3^3 = 27) = a composite player written here without the
   dispatch, against g* / s*, 4 games each, fixed seed; (d) the leader rule and its hold.

CPU only."""
import itertools

import numpy as np
import pytest
import torch

from svg_training.core.observations import OBS_DIM, SLOT, ObsView
from svg_training.core.strategy import SplitStrategy
from svg_training.opponents.scripted import make_strategy
from svg_training.ste import exploit, exploit_train, skills

V = ObsView()
HOLD = 12
GAMES = 24                           # T44's first starts per cell (slice 1's size)
MIX_GAMES = 4                        # per mixed combination (design test 3c: small n)
SIDES = ("strike", "guard")
LIST_A = {"team_strategies": {"strike": ["strike_sacrifice", "strike_converge"],
                              "guard": ["guard_parked_ring", "guard_field"]},
          "drone_skills": {"strike": ["strike_straight", "strike_flank", "strike_high", "strike_low"],
                           "guard": ["guard_parked_centre", "guard_mark_edge", "guard_mirror"]}}
LIST_B_GUARD = {"team_strategies": ["guard_parked_ring", "guard_mark_edge", "guard_mirror", "guard_field"],
                "drone_skills": ["guard_parked_centre"]}
TOML_A = """
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


def table(**over) -> dict:
    t = {"action": "skills", "choice": "two_level",
         "team_strategies": {k: list(v) for k, v in LIST_A["team_strategies"].items()},
         "drone_skills": {k: list(v) for k, v in LIST_A["drone_skills"].items()},
         "entropy_scale": {"team": 0.01, "drone": 0.01}}
    t.update(over)
    return t


SPEC_A = skills.learner_spec(table())


@pytest.fixture(scope="module")
def gates():
    g = exploit.load_gates()
    assert g.trainer["decision_ticks"] == HOLD
    return g


@pytest.fixture(scope="module")
def ref(gates):
    return exploit.load_reference(exploit.ROOT / gates.reference["file"])


def other(side):
    return "guard" if side == "strike" else "strike"


def cell_of(side, mine, opp):
    return (opp, mine) if side == "strike" else (mine, opp)


# ================================================================================================ test 1: the config
def test_list_a_loads_from_a_gate_file_and_list_b_is_accepted(gates, tmp_path):
    path = tmp_path / "gates.toml"
    path.write_text(exploit.GATES_FILE.read_text() + TOML_A)
    g = exploit.load_gates(path)
    assert g.learner.skills and g.learner.choice == skills.TWO_LEVEL
    for side in SIDES:
        assert list(g.learner.team_strategies[side]) == LIST_A["team_strategies"][side]
        assert list(g.learner.drone_skills[side]) == LIST_A["drone_skills"][side]
    assert g.learner.entropy_scale == {"team": 0.01, "drone": 0.01}
    assert g.learner == SPEC_A
    b = table(team_strategies={"strike": LIST_A["team_strategies"]["strike"], "guard": LIST_B_GUARD["team_strategies"]},
              drone_skills={"strike": LIST_A["drone_skills"]["strike"], "guard": LIST_B_GUARD["drone_skills"]})
    skills.check_two_level(skills.learner_spec(b), gates.players)
    # the pinned gate file and slice 1's modes are unchanged
    assert gates.learner == skills.learner_spec(None)
    assert skills.learner_spec({"action": "skills", "choice": "team"}) == skills.LearnerSpec("skills", "team")


def _moved(key, side, names):
    t = table()
    t[key] = {**t[key], side: names}
    return t


@pytest.mark.parametrize("bad,why", [
    (table(choice="pair"), "needs choice"),
    ({**table(), "hold": 3}, "unknown key"),
    ({k: v for k, v in table().items() if k != "entropy_scale"}, "needs"),
    ({k: v for k, v in table().items() if k != "drone_skills"}, "needs"),
    (table(entropy_scale={"team": 0.01}), "exactly the keys"),
    (table(entropy_scale={"team": 0.0, "drone": 0.01}), "must be a number > 0"),
    (table(entropy_scale={"team": 0.01, "drone": -0.01}), "must be a number > 0"),
    (table(entropy_scale={"team": True, "drone": 0.01}), "must be a number > 0"),
    (table(entropy_scale={"team": float("nan"), "drone": 0.01}), "must be a number > 0"),
    (table(team_strategies={"strike": ["strike_sacrifice"]}), "exactly the keys"),
    (_moved("drone_skills", "guard", "guard_mirror"), "list of player names"),
    ({"action": "skills", "choice": "team", "team_strategies": LIST_A["team_strategies"]}, "belong to choice"),
    ({"action": "velocity", "drone_skills": LIST_A["drone_skills"]}, "belong to choice"),
])
def test_the_two_level_table_refuses_a_bad_shape(bad, why):
    with pytest.raises(ValueError, match=why):
        skills.learner_spec(bad)


@pytest.mark.parametrize("bad,why", [
    (_moved("team_strategies", "strike", ["strike_sacrifice", "strike_zigzag"]), "not players"),
    (_moved("team_strategies", "guard", ["guard_parked_ring", "guard_field", "guard_mirror"]), "in both"),
    (_moved("drone_skills", "strike", ["strike_straight", "strike_flank", "strike_high"]), "in neither"),
    (_moved("drone_skills", "guard", ["guard_parked_centre", "guard_mark_edge", "guard_mark_edge", "guard_mirror"]),
     "repeated"),
    (table(team_strategies={"strike": [], "guard": LIST_A["team_strategies"]["guard"]},
           drone_skills={"strike": ["strike_straight", "strike_flank", "strike_high", "strike_low", "strike_sacrifice",
                                    "strike_converge"], "guard": LIST_A["drone_skills"]["guard"]}), "non-empty"),
    (table(team_strategies={"strike": LIST_A["team_strategies"]["strike"],
                            "guard": ["guard_parked_centre", "guard_parked_ring", "guard_mark_edge", "guard_mirror",
                                      "guard_field"]},
           drone_skills={"strike": LIST_A["drone_skills"]["strike"], "guard": []}), "non-empty"),
    (_moved("drone_skills", "strike", ["strike_flank", "strike_straight", "strike_high", "strike_low"]),
     "follow the \\[players\\] order"),
])
def test_the_two_level_lists_are_checked_against_players(gates, bad, why, tmp_path):
    spec = skills.learner_spec(bad)
    with pytest.raises(ValueError, match=why):
        skills.check_two_level(spec, gates.players)
    path = tmp_path / "gates.toml"                     # and the gate file loader runs the same check
    path.write_text(exploit.GATES_FILE.read_text() + "\n[learner]\n" + "\n".join(
        f"{k} = {_toml(v)}" for k, v in bad.items()) + "\n")
    with pytest.raises(ValueError, match=why):
        exploit.load_gates(path)


def _toml(v):
    if isinstance(v, dict):
        return "{ " + ", ".join(f"{k} = {_toml(x)}" for k, x in v.items()) + " }"
    if isinstance(v, list):
        return "[" + ", ".join(_toml(x) for x in v) + "]"
    return f'"{v}"' if isinstance(v, str) else repr(v)


def test_the_two_level_learner_is_refused_until_it_is_built(gates):
    cfg = exploit.variant_cfg(gates, "base")
    env = exploit_train.decision_env(exploit_train.TrainGame(cfg, 4, 3, 3, device="cpu", seed=7), HOLD, "strike",
                                     make_strategy("guard_mark_edge", "guard", cfg, 4, "cpu", 1), SPEC_A,
                                     gates.players, 7)
    with pytest.raises(ValueError, match="not built yet"):
        exploit_train.Learner(dict(gates.trainer, num_games=4, rollouts=2), env, "cpu", seed=3)


# ================================================================================================ test 2: the rule
def _team_obs(gates, side, n=16, ticks=20, seed=5):
    """Real observations of ``side`` after ``ticks`` ticks of scripted play (slice 1's helper)."""
    cfg = exploit.variant_cfg(gates, "base")
    game = exploit_train.TrainGame(cfg, n, 3, 3, device="cpu", seed=seed)
    obs = game.reset()
    g = make_strategy("guard_mark_edge", "guard", cfg, n, "cpu", 0)
    s = make_strategy("strike_straight", "strike", cfg, n, "cpu", 0)
    for _ in range(ticks):
        obs = game.step({"guard": g.act(obs["guard"]), "strike": s.act(obs["strike"])}).obs
    return cfg, obs[side]


def _perturbed_mates(cfg, side, obs, seed, drop=False):
    """obs with only the own-team slots changed: each present team-mate's relative position and velocity redrawn
    within 0.5 m (inside the field's 1.1 m), or (``drop``) every team-mate made absent."""
    first = 0 if side == "guard" else cfg.pad_guards
    count = cfg.pad_guards if side == "guard" else cfg.pad_strikes
    out = obs.clone()
    gen = torch.Generator().manual_seed(seed)
    for k in range(first, first + count):
        sl = V.slot(k)
        present = out[..., sl.start + 6] > 0.5
        if drop:
            out[..., sl] = 0.0
            continue
        noise = (torch.rand(*out.shape[:2], 6, generator=gen) - 0.5)
        out[..., sl.start:sl.start + 6] = torch.where(present[..., None], noise, out[..., sl.start:sl.start + 6])
    return out


@pytest.mark.parametrize("side", SIDES)
def test_a_drone_skill_reads_no_team_mate_and_a_team_strategy_does(gates, side):
    cfg, obs = _team_obs(gates, side)
    assert int((obs[..., V.alive] > 0.5).sum(-1).ge(2).sum()) >= obs.shape[0] // 2, "too few live mates: no power"
    for name in LIST_A["drone_skills"][side]:
        p = make_strategy(name, side, cfg, obs.shape[0], "cpu", 0)
        base = p.act(obs)
        for seed, drop in ((1, False), (2, False), (3, True)):
            assert torch.equal(p.act(_perturbed_mates(cfg, side, obs, seed, drop)), base), (name, seed, drop)
    for name in LIST_A["team_strategies"][side]:
        p = make_strategy(name, side, cfg, obs.shape[0], "cpu", 0)
        assert not torch.equal(p.act(_perturbed_mates(cfg, side, obs, 1)), p.act(obs)), name


# ================================================================================================ test 3: replay
class HeadLogits(torch.nn.Module):
    """A fixed two-level network: logits [B, T + 1 + K_d], 1 at team index t and at drone index d, 0 elsewhere."""

    def __init__(self, t, d, widths):
        super().__init__()
        self.t, self.d, self.widths = t, d, widths

    def forward(self, obs):
        out = obs.new_zeros(obs.shape[0], sum(self.widths))
        out[:, self.t] = 1.0
        out[:, self.widths[0] + self.d] = 1.0
        return out


def dispatch_of(side, cfg, n, gates):
    return skills.two_level_dispatch(SPEC_A, gates.players, side, cfg, n, "cpu", 0)


def two_level_team(side, heads, cfg, n, gates, name):
    """heads: per slot (team index, drone index)."""
    d = dispatch_of(side, cfg, n, gates)
    return exploit.SkillTeam(side, [HeadLogits(t, k, d.widths) for t, k in heads],
                             [lambda o, train=False: o] * len(heads), d, name=name)


class Composite:
    """The oracle of test 3c, written without the dispatch: drone m flies script ``names[m]`` (its own column of that
    script's command on the whole team's observation)."""

    def __init__(self, side, names, cfg, n):
        self.team, self.name = side, "composite(" + ",".join(names) + ")"
        self.scripts = [make_strategy(nm, side, cfg, n, "cpu", 0) for nm in names]

    def reset(self, games):
        for s in self.scripts:
            s.reset(games)

    def act(self, obs):
        return torch.stack([s.act(obs)[:, m] for m, s in enumerate(self.scripts)], dim=1)


class FixedTrainGame(exploit.FixedStartsGame):
    restart = exploit_train.TrainGame.restart


def train_path(gates, ref, side, cells, n):
    """The training path on T44's first ``n`` starts: ``DecisionEnv`` (two-level, list A) with fixed actions.
    cells: per cell (opponent script, heads per slot [(t, d)] * 3). Returns {cell index: (outcome [n], end_step [n])}
    of each slot's first game, as slice 1's parity test reads them."""
    cfg = exploit.variant_cfg(gates, "base")
    seed = int(ref.meta["seed"])
    k = len(cells)
    game = FixedTrainGame(cfg, k, torch.as_tensor(ref.starts_m[:n]), torch.as_tensor(ref.start_miss[:n]), 3, 3, "cpu",
                          seed)
    off = exploit.GUARD_SEED_OFFSET if other(side) == "guard" else exploit.STRIKE_SEED_OFFSET
    opp = SplitStrategy(other(side), [(make_strategy(o, other(side), cfg, n, "cpu", seed + off),
                                       slice(i * n, (i + 1) * n)) for i, (o, _) in enumerate(cells)])
    env = exploit_train.decision_env(game, HOLD, side, opp, SPEC_A, gates.players, seed)
    widths = env.skills.widths
    assert all(list(s.nvec) == list(widths) for s in env.action_spaces.values())
    act = torch.tensor([h for _, h in cells], dtype=torch.float32).repeat_interleave(n, dim=0)   # [k n, 3, 2]
    env.reset()
    total = k * n
    outcome = torch.zeros(total, dtype=torch.int8)
    end = torch.zeros(total, dtype=torch.long)
    done = torch.zeros(total, dtype=torch.bool)
    for d in range(int(gates.run["ticks_cap"]) // HOLD):
        _, _, _, _, info = env.step({a: act[:, i] for i, a in enumerate(env.possible_agents)})
        assert info["head_mask"].shape == (total, 3, 2)
        new = info["decision_ended"] & ~done
        outcome = torch.where(new, info["decision_outcome"], outcome)
        end = torch.where(new, d * HOLD + info["decision_end_tick"], end)
        done |= info["decision_ended"]
        if bool(done.all()):
            break
    assert bool(done.all()), "a game did not end inside the cap"
    return {i: (outcome[i * n:(i + 1) * n].numpy(), end[i * n:(i + 1) * n].numpy()) for i in range(k)}


def _same(path_cell, other_cell):
    """(outcome, end_step) of one path against another cell's arrays (first games)."""
    o, e = path_cell
    return (np.array_equal(o, np.asarray(other_cell["outcome"]))
            and np.array_equal(e, np.asarray(other_cell["end_step"])))


@pytest.mark.parametrize("side", SIDES)
def test_each_team_strategy_and_each_uniform_drone_skill_replays_its_t44_cell_on_both_paths(gates, ref, side):
    """3a and 3b: the team head at strategy t (the drone heads anything) and "free" with every drone on drone skill d,
    against every script of the other team, equal that script's T44 cell game for game."""
    cfg = exploit.variant_cfg(gates, "base")
    ts, ds = LIST_A["team_strategies"][side], LIST_A["drone_skills"][side]
    flown = [(nm, [(t + 1, (t + j) % len(ds)) for j in range(3)]) for t, nm in enumerate(ts)]   # drone heads differ
    flown += [(nm, [(skills.FREE, d)] * 3) for d, nm in enumerate(ds)]
    opps = skills.team_skills(gates.players, other(side))
    # the scoring path
    players = {f"tl:{nm}": two_level_team(side, heads, cfg, GAMES, gates, f"tl:{nm}") for nm, heads in flown}
    cells = [cell_of(side, f"tl:{nm}", o) for o in opps for nm, _ in flown]
    pg = exploit.play_cells(cfg, "3v3", ref, cells, GAMES, "cpu", ref.meta["seed"], gates.run["ticks_cap"],
                            hold_ticks=HOLD, players=players)
    k = 0
    for o in opps:
        for nm, _ in flown:
            t44 = {key: v[:GAMES] for key, v in ref.cell("base", *cell_of(side, nm, o)).items()}
            assert exploit.agreement(exploit.slice_cell(pg, k, GAMES), t44)["differ"] == 0, ("scoring", nm, o)
            k += 1
    # the training path
    tp = train_path(gates, ref, side, [(o, heads) for o in opps for _, heads in flown], GAMES)
    k = 0
    for o in opps:
        for nm, _ in flown:
            t44 = {key: v[:GAMES] for key, v in ref.cell("base", *cell_of(side, nm, o)).items()}
            assert _same(tp[k], t44), ("training", nm, o)
            k += 1


@pytest.mark.parametrize("side", SIDES)
def test_every_mixed_free_combination_equals_the_composite_player_on_both_paths(gates, ref, side):
    """3c: "free" with drone m on drone skill c[m], every combination, against g* (Strike side) / s* (Guard side): the
    two-level team (both paths) equals the composite player game for game; 4 games per combination, T44's starts."""
    cfg = exploit.variant_cfg(gates, "base")
    ds = LIST_A["drone_skills"][side]
    combos = list(itertools.product(range(len(ds)), repeat=3))
    assert len(combos) == {"strike": 64, "guard": 27}[side]
    opp = exploit.opponent_of(gates, "base", side)
    n = MIX_GAMES
    mine = {f"tl:{c}": two_level_team(side, [(skills.FREE, d) for d in c], cfg, n, gates, f"tl:{c}") for c in combos}
    comp = {f"comp:{c}": Composite(side, [ds[d] for d in c], cfg, n) for c in combos}
    seed = ref.meta["seed"]
    pg = exploit.play_cells(cfg, "3v3", ref, [cell_of(side, nm, opp) for nm in mine], n, "cpu", seed,
                            gates.run["ticks_cap"], hold_ticks=HOLD, players=mine)
    oracle = exploit.play_cells(cfg, "3v3", ref, [cell_of(side, nm, opp) for nm in comp], n, "cpu", seed,
                                gates.run["ticks_cap"], hold_ticks=1, players=comp)
    tp = train_path(gates, ref, side, [(opp, [(skills.FREE, d) for d in c]) for c in combos], n)
    mixed = 0
    for k, c in enumerate(combos):
        want = exploit.slice_cell(oracle, k, n)
        assert exploit.agreement(exploit.slice_cell(pg, k, n), want)["differ"] == 0, ("scoring", c)
        assert _same(tp[k], want), ("training", c)
        mixed += len(set(c)) > 1
    assert mixed == len(combos) - len(ds)


# ------------------------------------------------------------------------------------------------ 3d: the leader
def test_the_leader_is_the_lowest_index_live_drone_and_only_it_and_free_count_in_the_masks(gates):
    cfg = exploit.variant_cfg(gates, "base")
    d = dispatch_of("strike", cfg, 4, gates)
    obs = torch.zeros(4, 3, OBS_DIM)
    obs[..., V.alive] = torch.tensor([[1.0, 1.0, 1.0], [0.0, 1.0, 1.0], [0.0, 0.0, 1.0], [0.0, 0.0, 0.0]])
    action = torch.tensor([[1, 0], [2, 1], [0, 3]]).expand(4, 3, 2)          # slot 0: sacrifice, 1: converge, 2: free
    flown, mask = d.resolve_two_level(action, obs)
    names = d.names
    sac, conv = names.index("strike_sacrifice"), names.index("strike_converge")
    drone = [names.index(n) for n in ("strike_straight", "strike_flank", "strike_high", "strike_low")]
    free = [drone[0], drone[1], drone[3]]
    assert flown.tolist() == [[sac] * 3, [conv] * 3, free, free]        # no live drone: the last slot (slice 1's rule)
    assert mask[..., 0].tolist() == [[1, 0, 0], [0, 1, 0], [0, 0, 1], [0, 0, 1]]
    assert mask[..., 1].tolist() == [[0, 0, 0], [0, 0, 0], [1, 1, 1], [1, 1, 1]]
    assert torch.equal(d.resolve(action, obs), flown)
    assert d.greedy(torch.tensor([[0.0, 2.0, 1.0, 0.0, 0.0, 5.0, 0.0]])).tolist() == [[1, 2]]


def test_a_tagged_leader_keeps_its_choice_to_the_end_of_the_decision(gates):
    """Scoring (HeldPlayer): slot 0 leads with sacrifice, slot 1 would choose converge. Slot 0 is tagged at tick 5:
    sacrifice is held to the end of the decision; from tick 12 slot 1 leads and converge flies."""
    cfg = exploit.variant_cfg(gates, "base")
    team = two_level_team("strike", [(1, 0), (2, 0), (skills.FREE, 0)], cfg, 2, gates, "lead")
    held = exploit.HeldPlayer(team, HOLD)
    held.reset(torch.ones(2, dtype=torch.bool))
    names = team.dispatch.names
    obs = torch.zeros(2, 3, OBS_DIM)
    obs[..., V.alive] = 1.0
    obs[..., V.zone_radius] = 1.0
    obs[..., V.arena_half] = 6.0
    seen = []
    for tick in range(2 * HOLD):
        if tick == 5:
            obs[:, 0] = 0.0                                                      # slot 0 out: an all-zero observation
            obs[:, 0, V.team] = 1.0
        held.act(obs)
        seen.append(held.held[0, 1].item())
    assert seen[:HOLD] == [names.index("strike_sacrifice")] * HOLD
    assert seen[HOLD:] == [names.index("strike_converge")] * HOLD
