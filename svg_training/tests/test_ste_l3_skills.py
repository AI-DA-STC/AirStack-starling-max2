"""STE phase L3, first slice (B8), tier 1: the mixed route (design note ste_learning/drafts/L3_TWO_ROUTES_DESIGN.md, "v2
after the design review"; owner ruling R26).

The four tests v2 asks for, written before the code:

1. A fixed choice j for every drone reproduces script j's T44 cell game for game (CPU replay), every skill of both
   teams, both choice modes (per team, per drone).
2. Training (``DecisionEnv.step``) and scoring (``HeldPlayer``) use the same hold rule: the choice is made every 12
   ticks and the chosen skill runs closed loop every tick in between; the two paths play the same games.
3. Two PPO updates, then the networks saved, reloaded in a fresh Python process, and golden rows (logits, skill, final
   command) on real team observations match bit for bit.
4. The velocity route is unchanged: the switch's default is the velocity route, the pinned gate files load as before, and
   the golden of tests/test_ste_l3_velocity_golden.py (recorded before this slice) still holds.

Plus the config switch's refusals and the dispatch's gather. CPU only, small batches."""
import subprocess
import textwrap

import numpy as np
import pytest
import torch

from _torch_threads import default_torch_threads  # noqa: F401  (autouse: goldens at the default thread count)

from _proc import child_env, child_python
from svg_training.core.observations import OBS_DIM, ObsView
from svg_training.envs.skrl_adapter import SvgSkrlEnv
from svg_training.opponents.scripted import make_strategy
from svg_training.ste import exploit, exploit_train, skills

V = ObsView()
HOLD = 12                         # the gate file's decision_ticks (checked below)
GAMES = 24                        # first games of T44's starts per cell (tests/test_ste_l012.py's size)
PARITY_TICKS = 360                # 30 decisions; bounds the parity test as in tests/test_ste_l012_train.py
SIDES = ("strike", "guard")


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


def tiny(gates, **over):
    return dict(gates.trainer, num_games=6, rollouts=2, learning_epochs=1, mini_batches=1, **over)


def spec(choice):
    return skills.learner_spec({"action": "skills", "choice": choice})


def skill_env(gates, side, n, choice, seed=7, game=None):
    cfg = exploit.variant_cfg(gates, "base")
    game = game or exploit_train.TrainGame(cfg, n, 3, 3, device="cpu", seed=seed)
    opp = make_strategy(exploit.opponent_of(gates, "base", side), other(side), cfg, n, "cpu", seed + 1)
    return exploit_train.decision_env(game, HOLD, side, opp, spec(choice), gates.players, seed), cfg


class FixedLogits(torch.nn.Module):
    """A network that always prefers skill j: logits [B, K] with 1 at j, 0 elsewhere."""

    def __init__(self, j, k):
        super().__init__()
        self.j, self.k = j, k

    def forward(self, obs):
        return torch.nn.functional.one_hot(torch.full(obs.shape[:1], self.j), self.k).to(obs.dtype)


def fixed_team(side, j, cfg, n, choice, gates):
    names = skills.team_skills(gates.players, side)
    dispatch = skills.SkillDispatch(side, names, cfg, n, "cpu", 0, choice)
    return exploit.SkillTeam(side, [FixedLogits(j, len(names))] * 3, [lambda o, train=False: o] * 3, dispatch,
                             name=f"skill {names[j]}")


# ------------------------------------------------------------------------------------------------ the config switch
def test_no_learner_table_is_the_velocity_route_and_the_pinned_gate_files_load_as_before(gates):
    assert skills.learner_spec(None) == skills.learner_spec({}) == skills.learner_spec({"action": "velocity"})
    assert skills.learner_spec(None).action == "velocity" and not skills.learner_spec(None).skills
    assert gates.learner == skills.learner_spec(None)                     # configs/ste_l012/gates.toml has no [learner]


@pytest.mark.parametrize("table,why", [
    ({"action": "skill"}, "action must be one of"),
    ({"action": "skills"}, "needs choice"),
    ({"action": "skills", "choice": "pair"}, "needs choice"),
    ({"action": "velocity", "choice": "team"}, "skills route only"),
    ({"action": "skills", "choice": "team", "hold": 3}, "unknown key"),
])
def test_the_learner_table_refuses_a_bad_value(table, why):
    with pytest.raises(ValueError, match=why):
        skills.learner_spec(table)


def test_a_gate_file_with_a_learner_table_loads_the_skills_route(tmp_path):
    text = exploit.GATES_FILE.read_text() + '\n[learner]\naction = "skills"\nchoice = "team"\n'
    path = tmp_path / "gates.toml"
    path.write_text(text)
    g = exploit.load_gates(path)
    assert g.learner == skills.LearnerSpec("skills", "team")
    path.write_text(exploit.GATES_FILE.read_text() + '\n[learner]\naction = "skills"\n')
    with pytest.raises(ValueError, match="needs choice"):
        exploit.load_gates(path)


def test_the_skill_lists_are_r26s(gates):
    assert skills.team_skills(gates.players, "strike") == ["strike_straight", "strike_flank", "strike_high",
                                                          "strike_low", "strike_sacrifice", "strike_converge"]
    assert skills.team_skills(gates.players, "guard") == ["guard_parked_centre", "guard_parked_ring",
                                                         "guard_mark_edge", "guard_mirror", "guard_field"]


# ------------------------------------------------------------------------------------------------ the dispatch
def _team_obs(gates, side, n=8, ticks=20, seed=5):
    """Real observations of ``side`` after ``ticks`` ticks of scripted play (some drones tagged)."""
    cfg = exploit.variant_cfg(gates, "base")
    game = exploit_train.TrainGame(cfg, n, 3, 3, device="cpu", seed=seed)
    obs = game.reset()
    g = make_strategy("guard_mark_edge", "guard", cfg, n, "cpu", 0)
    s = make_strategy("strike_straight", "strike", cfg, n, "cpu", 0)
    for _ in range(ticks):
        obs = game.step({"guard": g.act(obs["guard"]), "strike": s.act(obs["strike"])}).obs
    return cfg, obs[side]


@pytest.mark.parametrize("side", SIDES)
def test_the_dispatch_gives_each_drone_exactly_its_chosen_scripts_command(gates, side):
    cfg, obs = _team_obs(gates, side)
    names = skills.team_skills(gates.players, side)
    d = skills.SkillDispatch(side, names, cfg, obs.shape[0], "cpu", 0, "drone")
    own = [make_strategy(nm, side, cfg, obs.shape[0], "cpu", 0).act(obs) for nm in names]
    for j in range(d.k):
        assert torch.equal(d.act(obs, torch.full(obs.shape[:2], j)), own[j])
    mixed = torch.arange(obs.shape[0] * 3).reshape(-1, 3) % d.k                  # a different skill per drone
    want = torch.stack([own[int(mixed[i, m])][i, m] for i in range(obs.shape[0]) for m in range(3)])
    assert torch.equal(d.act(obs, mixed).reshape(-1, 4), want)


def test_an_unchosen_skills_non_finite_command_never_reaches_the_drone(gates):
    cfg, obs = _team_obs(gates, "strike")
    d = skills.SkillDispatch("strike", ["strike_straight", "strike_flank"], cfg, obs.shape[0], "cpu", 0, "drone")
    d.players[1].act = lambda o: torch.full((*o.shape[:2], 4), float("nan"))
    assert bool(torch.isfinite(d.act(obs, torch.zeros(obs.shape[:2], dtype=torch.long))).all())


def test_per_team_the_lowest_index_live_drone_chooses_for_the_team():
    obs = torch.zeros(3, 3, OBS_DIM)
    obs[..., V.alive] = torch.tensor([[1.0, 1.0, 1.0], [0.0, 1.0, 1.0], [0.0, 0.0, 1.0]])
    choice = torch.tensor([[4, 1, 2], [4, 1, 2], [4, 1, 2]])
    team = skills.SkillDispatch.__new__(skills.SkillDispatch)
    team.choice = "team"
    assert team.resolve(choice, obs).tolist() == [[4, 4, 4], [1, 1, 1], [2, 2, 2]]
    team.choice = "drone"
    assert team.resolve(choice, obs).tolist() == choice.tolist()


# ------------------------------------------------------------------------------------------------ test 1: T44 replay
@pytest.mark.parametrize("choice", skills.CHOICES)
@pytest.mark.parametrize("side", SIDES)
def test_a_fixed_choice_j_replays_script_js_t44_cell_game_for_game(gates, ref, side, choice):
    """Every skill j of the team, chosen by every drone (held 12 ticks, run closed loop), against the run's opponent
    (g* for the Strike side, s* for the Guard side) from T44's starts: outcome, end step, tags and Strike drones left
    equal T44's cell of script j in every game (the scoring path: ``play_cells`` with ``HeldPlayer``)."""
    cfg = exploit.variant_cfg(gates, "base")
    opp = exploit.opponent_of(gates, "base", side)
    names = skills.team_skills(gates.players, side)
    players = {f"skill_{j}": fixed_team(side, j, cfg, GAMES, choice, gates) for j in range(len(names))}
    cells = [(opp, nm) if side == "strike" else (nm, opp) for nm in players]
    pg = exploit.play_cells(cfg, "3v3", ref, cells, GAMES, "cpu", ref.meta["seed"], gates.run["ticks_cap"],
                            hold_ticks=HOLD, players=players)
    for k, nm in enumerate(names):
        mine = exploit.slice_cell(pg, k, GAMES)
        t44 = {key: v[:GAMES] for key, v in ref.cell("base", *((opp, nm) if side == "strike" else (nm, opp))).items()}
        assert exploit.agreement(mine, t44)["differ"] == 0, (side, choice, nm)


# ------------------------------------------------------------------------------------------------ test 2: the hold rule
def test_held_player_holds_the_choice_and_runs_the_skill_every_tick(gates):
    """Scoring: the choice counts only on the decision ticks (every 3rd here, phased from each game's start, a reset
    restarting the phase); the command is the held skill's command on the CURRENT observation, every tick."""
    cfg, obs = _team_obs(gates, "strike", n=2)
    names = skills.team_skills(gates.players, "strike")
    k = len(names)
    d = skills.SkillDispatch("strike", names, cfg, 2, "cpu", 0, "drone")
    team = exploit.SkillTeam("strike", [FixedLogits(0, k)] * 3, [lambda o, train=False: o] * 3, d)
    wishes = iter([torch.full((2, 3), t % k) for t in range(7)])           # a new wish every tick
    team.choose = lambda o: next(wishes)
    p = exploit.HeldPlayer(team, 3)
    p.reset(torch.ones(2, dtype=torch.bool))
    followed = False
    for t in range(7):
        o = obs.clone()
        o[..., V.own_pos] += 0.05 * t                                       # a moving observation
        if t == 4:
            p.reset(torch.tensor([False, True]))
        out = p.act(o)
        decided = [3 * (t // 3), 3 * (t // 3) if t < 4 else 4 + 3 * ((t - 4) // 3)]
        assert p.held.tolist() == [[decided[g] % k] * 3 for g in range(2)], t
        assert torch.equal(out, d.act(o, p.held))
        followed |= not torch.equal(out, d.act(obs, p.held))
    assert followed, "the command never depended on the current observation: the test has no power"


def test_one_decision_flies_the_chosen_skill_closed_loop_not_its_first_command(gates):
    """Training: one DecisionEnv decision with every drone choosing skill j equals 12 ticks of the plain adapter driven
    by script j's command on each tick's own observation, and differs from 12 ticks of script j's first command held
    (the test can tell the two rules apart)."""
    cfg = exploit.variant_cfg(gates, "base")
    names = skills.team_skills(gates.players, "strike")
    j = names.index("strike_converge")
    env, _ = skill_env(gates, "strike", 4, "drone")
    env.reset()
    obs, rew, term, _, info = env.step({a: torch.full((4, 1), j) for a in env.possible_agents})
    script = make_strategy("strike_converge", "strike", cfg, 4, "cpu", 0)

    def plain(closed):
        ref_env = SvgSkrlEnv(exploit_train.TrainGame(cfg, 4, 3, 3, device="cpu", seed=7), train_teams=("strike",),
                             opponents={"guard": make_strategy(exploit.opponent_of(gates, "base", "strike"), "guard",
                                                               cfg, 4, "cpu", 8)})
        ref_env.reset()
        first = script.act(ref_env._game_obs["strike"])
        for _ in range(HOLD):
            cmd = script.act(ref_env._game_obs["strike"]) if closed else first
            out = ref_env.step({f"strike_{m}": cmd[:, m] for m in range(3)})
        return out
    closed, held = plain(True), plain(False)
    assert not bool(info["decision_ended"].any()), "a game ended: pick other starts"
    for a in env.possible_agents:
        assert torch.equal(obs[a], closed[0][a])
    assert any(not torch.equal(obs[a], held[0][a]) for a in env.possible_agents)
    assert torch.equal(info["skill_choice"], torch.full((4, 3), j))


def _scramble(learner, seed):
    torch.manual_seed(seed)
    with torch.no_grad():
        for a in learner.names:
            for p in learner.agent.policies[a].net.parameters():
                p.normal_(0.0, 0.5)
            learner.agent._observation_preprocessor[a](torch.randn(64, OBS_DIM) * 2.0 + 0.5, train=True)


class FixedTrainGame(exploit.FixedStartsGame):
    restart = exploit_train.TrainGame.restart


@pytest.mark.parametrize("choice", skills.CHOICES)
@pytest.mark.parametrize("side", SIDES)
def test_the_training_path_and_the_scoring_path_play_the_same_games(gates, ref, side, choice):
    """The same categorical networks from T44's starts, (1) through DecisionEnv with skrl's own logits (argmax, one
    choice per 12 ticks, the skill closed loop) and (2) through play_cells with HeldPlayer + Learner.team(): the same
    outcome and end step in every game. The choices must change during games, or the test has no power."""
    n, seed = 12, 7
    env, cfg = skill_env(gates, side, 4, choice)
    learner = exploit_train.Learner(tiny(gates), env, "cpu", seed=3)
    _scramble(learner, 5)
    opp = exploit.opponent_of(gates, "base", side)
    offset = exploit.GUARD_SEED_OFFSET if other(side) == "guard" else exploit.STRIKE_SEED_OFFSET
    game = FixedTrainGame(cfg, 1, torch.as_tensor(ref.starts_m[:n]), torch.as_tensor(ref.start_miss[:n]), 3, 3, "cpu",
                          seed)
    denv = exploit_train.decision_env(game, HOLD, side, make_strategy(opp, other(side), cfg, n, "cpu", seed + offset),
                                      spec(choice), gates.players, seed)
    obs, _ = denv.reset()
    learner.agent.enable_training_mode(False)
    outcome = torch.zeros(n, dtype=torch.int8)
    end = torch.zeros(n, dtype=torch.long)
    done = torch.zeros(n, dtype=torch.bool)
    switches, prev = 0, None
    for d in range(PARITY_TICKS // HOLD):
        with torch.no_grad():
            _, out = learner.agent.act(obs, denv.state(), timestep=0, timesteps=1)
        obs, _, _, _, info = denv.step({a: out[a]["net_output"].argmax(-1, keepdim=True) for a in learner.names})
        c = info["skill_choice"]
        if choice == "team":
            assert bool((c == c[:, :1]).all())
        if prev is not None:
            switches += int(((c != prev).any(-1) & ~done).sum())
        prev = c
        new = info["decision_ended"] & ~done
        outcome = torch.where(new, info["decision_outcome"], outcome)
        end = torch.where(new, d * HOLD + info["decision_end_tick"], end)
        done |= info["decision_ended"]
        if bool(done.all()):
            break
    cell = (opp, exploit.EXPLOITER) if side == "strike" else (exploit.EXPLOITER, opp)
    pg = exploit.play_cells(cfg, "3v3", ref, [cell], n, "cpu", seed, PARITY_TICKS, learner=learner.team(),
                            hold_ticks=HOLD)
    assert int(done.sum()) >= n // 4, f"only {int(done.sum())} of {n} games ended: the test has no power"
    assert switches > 0, "no choice changed inside a game: the test cannot see the hold rule"
    assert outcome.tolist() == pg["outcome"].tolist()
    assert end.tolist() == pg["end_step"].tolist()


def test_a_skill_index_stored_as_float_scores_the_same_log_probability():
    """skrl's memory stores actions as float32; the PPO step scores the stored index again (``taken_actions``): a
    scrambled categorical policy must give the same log-probability for the float copy as for the sampled long index."""
    from svg_training.opponents.learned import SkillPolicy
    torch.manual_seed(0)
    pol = SkillPolicy([16, 16], 6, "cpu")
    with torch.no_grad():
        for p in pol.parameters():
            p.normal_(0.0, 1.0)
    obs = torch.randn(50, OBS_DIM)
    act, out = pol.act({"observations": obs}, role="policy")
    _, again = pol.act({"observations": obs, "taken_actions": act.float()}, role="policy")
    assert act.unique().numel() > 1, "one index only: the test cannot see a mix-up"
    assert torch.equal(out["log_prob"], again["log_prob"])


# ------------------------------------------------------------------------------------------------ test 3: save, reload
CHILD = textwrap.dedent("""
    import sys, torch
    from svg_training.ste import exploit, exploit_train, skills
    saved = torch.load(sys.argv[1], weights_only=False)
    gates = exploit.load_gates()
    cfg = exploit.variant_cfg(gates, "base")
    obs = saved["obs"]
    d = skills.SkillDispatch(saved["team"], saved["skills"], cfg, obs.shape[0], "cpu", 0, saved["choice"])
    team = exploit_train.skill_team_from_modules(saved["team"], saved["learner"], saved["hidden"], d, "cpu")
    logits = team.logits(obs)
    skill = team.choose(obs)
    torch.save({"logits": logits, "skill": skill, "command": team.command(obs, skill)}, sys.argv[2])
""")


@pytest.mark.parametrize("side,choice", [("strike", "drone"), ("guard", "team")])
def test_two_updates_then_save_and_reload_in_a_fresh_process_give_the_golden_rows(gates, tmp_path, side, choice):
    env, _ = skill_env(gates, side, 6, choice)
    learner = exploit_train.Learner(tiny(gates), env, "cpu", seed=11)
    names = env.possible_agents
    assert env.action_spaces[names[0]].n == len(skills.team_skills(gates.players, side))
    obs0 = torch.randn(5, 3, OBS_DIM, generator=torch.Generator().manual_seed(1))
    assert bool((learner.team().logits(obs0) == 0).all())                  # uniform start: zero logits
    before = {a: [p.clone() for p in learner.agent.policies[a].parameters()] for a in names}
    for _ in range(2):
        stats = learner.update()
        assert stats["losses"] and all(np.isfinite(v) for v in stats["losses"].values())
        assert stats["std"] == {}                                          # a categorical head has no standard deviation
    assert any(not torch.equal(p, q) for a in names for p, q in zip(before[a], learner.agent.policies[a].parameters()))
    obs = env._game_obs[side].clone()                                     # real team observations [N, M, D]
    team = learner.team()
    rows = {"logits": team.logits(obs)}
    rows["skill"] = team.choose(obs)
    rows["command"] = team.command(obs, rows["skill"])
    assert rows["logits"].shape == (6, 3, env.skills.k) and rows["skill"].dtype == torch.long
    saved = tmp_path / "saved.pt"
    assert set(learner.saved()) == {"skills", "modules"}               # L3 slice 2: the skill lists travel along
    torch.save({"learner": learner.saved(), "hidden": list(gates.trainer["hidden"]), "team": side,
                "skills": env.skills.names, "choice": choice, "obs": obs}, saved)
    out = tmp_path / "rows.pt"
    r = subprocess.run([child_python(), "-c", CHILD, str(saved), str(out)], env={**child_env(), "CUDA_VISIBLE_DEVICES": ""},
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr[-2000:]
    got = torch.load(out, weights_only=False)
    for k, v in rows.items():
        assert torch.equal(got[k], v), k


# ------------------------------------------------------------------------------------------------ test 4: velocity route
def test_the_velocity_switch_builds_todays_decision_env_and_learner_bit_for_bit(gates):
    """``[learner] action = "velocity"`` (or no table) builds the same DecisionEnv as before (no dispatch, the Box action
    space) and two updates give the same weights bit for bit as the env built the old way."""
    cfg = exploit.variant_cfg(gates, "base")
    opp = exploit.opponent_of(gates, "base", "guard")

    def run(new):
        game = exploit_train.TrainGame(cfg, 6, 3, 3, device="cpu", seed=7)
        o = make_strategy(opp, "strike", cfg, 6, "cpu", 8)
        env = (exploit_train.decision_env(game, HOLD, "guard", o, skills.learner_spec(None), gates.players, 7) if new
               else exploit_train.DecisionEnv(game, HOLD, "guard", o))
        assert env.skills is None and env.action_spaces["guard_0"].shape == (4,)
        learner = exploit_train.Learner(tiny(gates), env, "cpu", seed=11)
        learner.update()
        learner.update()
        return learner.modules()
    a, b = run(False), run(True)
    for agent in a:
        for mod in ("policy", "value"):
            for k in a[agent][mod]:
                assert torch.equal(a[agent][mod][k], b[agent][mod][k]), (agent, mod, k)
