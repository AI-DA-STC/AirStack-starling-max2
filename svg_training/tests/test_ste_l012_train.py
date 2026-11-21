"""STE task L0.12 Best-response test, the exploiter trainer (source/svg_training/ste/exploit_train.py): the committed
L0.11 game files with the study tag on, either side trained against a fixed scripted opponent, one learner decision per
12 ticks with ended games restarted at the decision boundary, what a tagged drone looks like to the learner, one IPPO
update on each side (the loss moves), and the checkpoint the run contract resumes from. CPU only, tiny batches."""
import numpy as np
import pytest
import torch

from svg_training.core.game import PARK_M
from svg_training.core.observations import ObsView
from svg_training.core.rewards import GUARD_WIN
from svg_training.envs.skrl_adapter import SvgSkrlEnv
from svg_training.opponents.scripted import make_strategy
from svg_training.ste import exploit, exploit_train

V = ObsView()


@pytest.fixture(scope="module")
def gates():
    return exploit.load_gates()


def tiny(gates, **over):
    """The gate file's trainer settings cut to a CPU test size."""
    return dict(gates.trainer, num_games=6, rollouts=2, learning_epochs=1, mini_batches=1, **over)


def env_for(gates, variant, side, n, seed=7, hold=None):
    cfg = exploit.variant_cfg(gates, variant)
    game = exploit_train.TrainGame(cfg, n, 3, 3, device="cpu", seed=seed)
    opp = exploit.opponent_of(gates, variant, side)
    other = "guard" if side == "strike" else "strike"
    return exploit_train.DecisionEnv(game, hold or gates.trainer["decision_ticks"], side,
                                     make_strategy(opp, other, cfg, n, "cpu", seed + 1)), cfg


# ------------------------------------------------------------------------------------------------ the decision hold
def test_with_no_game_ending_a_decision_is_twelve_ticks_of_the_same_command(gates):
    env, cfg = env_for(gates, "base", "guard", 4, hold=3)
    ref = SvgSkrlEnv(exploit_train.TrainGame(cfg, 4, 3, 3, device="cpu", seed=7), train_teams=("guard",),
                     opponents={"strike": make_strategy("strike_straight", "strike", cfg, 4, "cpu", 8)})
    o1, _ = env.reset()
    o2, _ = ref.reset()
    act = {a: torch.full((4, 4), 0.1) for a in env.possible_agents}
    out = env.step(act)
    for _ in range(3):
        out2 = ref.step(act)
    for a in env.possible_agents:
        assert torch.equal(out[0][a], out2[0][a])
    assert not bool(out[2]["guard_0"].any())
    assert int(out[4]["stale_ticks"].sum()) == 0


def test_a_game_that_ends_inside_a_decision_restarts_at_the_decision_boundary(gates):
    """tag_10m-like end at tick 1: the 10 m tag is wider than the arena, so every game ends at its first tick with a
    hold; the remaining 11 ticks of the decision are not trained on, the reward is the end's alone, and the next decision
    starts on a fresh game at its first tick (so training phase = evaluation phase)."""
    cfg = exploit.variant_cfg(exploit.load_gates(), "base").replace(**{"tag.radius_m": 10.0})
    game = exploit_train.TrainGame(cfg, 3, 3, 3, device="cpu", seed=3)
    env = exploit_train.DecisionEnv(game, 12, "strike", make_strategy("zero", "guard", cfg, 3, "cpu", 4))
    env.reset()
    obs, rew, term, _, info = env.step({a: torch.zeros(3, 4) for a in env.possible_agents})
    assert bool(term["strike_0"].all())
    assert torch.equal(rew["strike_0"], -torch.ones(3, 1))                # one end, one -1: nothing after it summed
    assert torch.equal(info["decision_outcome"], torch.full((3,), GUARD_WIN, dtype=torch.int8))
    assert torch.equal(info["stale_ticks"], torch.full((3,), 11))
    assert torch.equal(game.steps, torch.zeros(3, dtype=torch.long))     # a fresh game, not yet stepped
    assert torch.equal(obs["strike_0"], env._split(game._obs())["strike_0"])


# ------------------------------------------------------------------------------------------------ tagged drones
def test_a_tagged_drone_is_absent_to_the_learner_and_no_parked_position_leaks(gates):
    """Base rules, 3v3: Guard 0 and Strike 0 start 1.2 m apart (inside the 1.6 m tag), the rest far apart. After one
    tick both are out and the game goes on. Strike 0's own row is zero except its team; every other drone's slot for a
    removed drone reads absent (all zeros); no observation holds the parked position."""
    cfg = exploit.variant_cfg(gates, "base")
    starts = torch.tensor([[[0.0, 0.0, 1.2], [-0.8, 0.0, 1.2], [0.0, -0.8, 1.2],
                            [1.2, 0.0, 1.2], [-2.75, 0.0, 1.2], [0.0, 2.75, 1.2]]])
    game = exploit.FixedStartsGame(cfg, 1, starts, torch.zeros(1, dtype=torch.bool), 3, 3, "cpu", 0)
    env = SvgSkrlEnv(game, train_teams=("strike",), opponents={"guard": make_strategy("zero", "guard", cfg, 1, "cpu", 0)})
    env.reset()
    obs, _, term, _, info = env.step({a: torch.zeros(1, 4) for a in env.possible_agents})
    assert not bool(term["strike_0"].any())
    assert info["final_alive"].tolist() == [[False, True, True, False, True, True]]
    s0 = obs["strike_0"][0]
    assert float(s0[V.alive]) == 0.0 and float(s0[V.team]) == 1.0
    assert float(s0.abs().sum()) == 1.0                                    # only the team flag is left
    for a in ("strike_1", "strike_2"):
        o = obs[a][0]
        assert float(o[V.slot(0)].abs().sum()) == 0.0                       # Guard 0: absent
        assert float(o[V.slot(cfg.pad_guards)].abs().sum()) == 0.0          # Strike 0: absent
        assert float(o[V.slot(1)][6]) == 1.0                                # Guard 1: present
    every = torch.cat([obs[a] for a in env.possible_agents])
    every[:, V.time_left] = 0.0                                          # 119.95 s left: the one large legitimate number
    assert float(every.abs().max()) < PARK_M / 100                       # no parked position or jump-to-park speed


# ------------------------------------------------------------------------------------------------ training
@pytest.mark.parametrize("variant,side", [("base", "strike"), ("base", "guard"), ("tag_1p2", "strike")])
def test_one_update_moves_the_loss_and_the_weights_on_either_side(gates, variant, side):
    env, _ = env_for(gates, variant, side, 6)
    learner = exploit_train.Learner(tiny(gates), env, "cpu", seed=11)
    names = env.possible_agents
    assert names == [f"{side}_{k}" for k in range(3)]
    before = {a: [p.clone() for p in learner.agent.policies[a].parameters()] for a in names}
    team = learner.team()
    assert torch.equal(team.act(torch.randn(4, 3, 71)), torch.zeros(4, 3, 4))   # zero-mean start
    stats = learner.update()
    assert stats["decisions"] == 2 and stats["game_steps"] == 2 * 12 * 6
    assert all(np.isfinite(v) for k, v in stats["losses"].items())
    assert stats["losses"], "skrl tracked no loss"
    moved = any(not torch.equal(p, q) for a in names for p, q in zip(before[a], learner.agent.policies[a].parameters()))
    assert moved
    yaw = exploit_train.ACTION_AXES["yaw"]
    for a in names:                                                      # yaw's noise is frozen, the others train
        assert float(learner.agent.policies[a].log_std[yaw]) == float(torch.tensor(gates.trainer["init_log_std"]))


def test_the_checkpoint_restores_networks_optimisers_scalers_and_the_update_count(gates):
    env, _ = env_for(gates, "base", "guard", 6)
    a = exploit_train.Learner(tiny(gates), env, "cpu", seed=11)
    a.update()
    state = a.state()
    env2, _ = env_for(gates, "base", "guard", 6)
    b = exploit_train.Learner(tiny(gates), env2, "cpu", seed=99)
    b.load_state(state)
    assert b.updates == a.updates == 1 and b.game_steps == a.game_steps
    for name in env.possible_agents:
        for p, q in zip(a.agent.policies[name].parameters(), b.agent.policies[name].parameters()):
            assert torch.equal(p, q)
        sa, sb = a.agent._observation_preprocessor[name].state_dict(), b.agent._observation_preprocessor[name].state_dict()
        assert all(torch.equal(sa[k], sb[k]) for k in sa)
        oa, ob = a.agent.optimizers[name].state_dict(), b.agent.optimizers[name].state_dict()
        assert oa["state"].keys() == ob["state"].keys()
    obs = torch.randn(5, 3, 71)
    assert torch.equal(a.team().act(obs), b.team().act(obs))
    b.update()                                                           # and it trains on from there
    assert b.updates == 2


def test_a_non_finite_weight_is_caught(gates):
    env, _ = env_for(gates, "base", "strike", 6)
    learner = exploit_train.Learner(tiny(gates), env, "cpu", seed=1)
    with torch.no_grad():
        next(learner.agent.policies["strike_0"].parameters()).fill_(float("nan"))
    with pytest.raises(exploit_train.NonFinite):
        learner.check_finite()


# ------------------------------------------------------------------------------------------------ QC fix round 1 (I-1)
PARITY_TICKS = 360                 # 30 decisions: games of T44's kind end in 36-78 ticks; the cap only bounds the test


class FixedTrainGame(exploit.FixedStartsGame):
    """T44's starts (or any) with the training game's restart: the training path on fixed starts."""
    restart = exploit_train.TrainGame.restart


def _scramble(learner, seed):
    """Non-trivial weights and observation scalers (a known, large, different network per drone)."""
    torch.manual_seed(seed)
    with torch.no_grad():
        for a in learner.names:
            for p in learner.agent.policies[a].net.parameters():
                p.normal_(0.0, 0.5)
            learner.agent._observation_preprocessor[a](torch.randn(64, 71) * 2.0 + 0.5, train=True)


@pytest.mark.parametrize("side", ["guard", "strike"])
def test_the_training_path_and_the_evaluation_path_play_the_same_games(gates, side):
    """QC I-1(a): the same weights from the same starts, (1) through the trainer's DecisionEnv with skrl's own mean
    actions (``agent.act``: its scaler, its network per agent name, one decision per 12 ticks) and (2) through the
    evaluation (``play_cells`` with ``HeldPlayer`` + ``Learner.team()``), give the same outcome and end step in every
    game. Catches a scaler, a drone order or a decision phase that differs between the two paths. Both paths are cut
    at the same PARITY_TICKS (random-weight Strike drones may wander to the time-out); unfinished games must agree too."""
    n, seed = 12, 7
    env, cfg = env_for(gates, "base", side, 4)
    learner = exploit_train.Learner(tiny(gates), env, "cpu", seed=3)
    _scramble(learner, 5)
    ref = exploit.load_reference(exploit.ROOT / gates.reference["file"])
    opp_name = exploit.opponent_of(gates, "base", side)
    other = "guard" if side == "strike" else "strike"
    offset = exploit.GUARD_SEED_OFFSET if other == "guard" else exploit.STRIKE_SEED_OFFSET
    game = FixedTrainGame(cfg, 1, torch.as_tensor(ref.starts_m[:n]), torch.as_tensor(ref.start_miss[:n]), 3, 3, "cpu",
                          seed)
    denv = exploit_train.DecisionEnv(game, 12, side, make_strategy(opp_name, other, cfg, n, "cpu", seed + offset))
    obs, _ = denv.reset()
    learner.agent.enable_training_mode(False)
    outcome = torch.zeros(n, dtype=torch.int8)
    end = torch.zeros(n, dtype=torch.long)
    done = torch.zeros(n, dtype=torch.bool)
    for d in range(PARITY_TICKS // 12):
        with torch.no_grad():
            _, out = learner.agent.act(obs, denv.state(), timestep=0, timesteps=1)
        obs, _, _, _, info = denv.step({a: out[a]["mean_actions"].clamp(-1.0, 1.0) for a in learner.names})
        new = info["decision_ended"] & ~done
        outcome = torch.where(new, info["decision_outcome"], outcome)
        end = torch.where(new, d * 12 + info["decision_end_tick"], end)
        done |= info["decision_ended"]
        if bool(done.all()):
            break
    cell = (opp_name, exploit.EXPLOITER) if side == "strike" else (exploit.EXPLOITER, opp_name)
    pg = exploit.play_cells(cfg, "3v3", ref, [cell], n, "cpu", seed, PARITY_TICKS, learner=learner.team(),
                            hold_ticks=12)
    assert int(done.sum()) >= n // 4, f"only {int(done.sum())} of {n} games ended: the test has no power"
    assert outcome.tolist() == pg["outcome"].tolist()
    assert end.tolist() == pg["end_step"].tolist()


def test_a_tagged_drone_reads_absent_in_the_decision_envs_observations(gates):
    """QC I-1(c), mutation T3: the observation the learner trains on (DecisionEnv's, after the boundary restart) shows a
    tagged drone as out (own alive 0) and absent to its team-mates."""
    cfg = exploit.variant_cfg(gates, "base")
    starts = torch.tensor([[[0.0, 0.0, 1.2], [-0.8, 0.0, 1.2], [0.0, -0.8, 1.2],
                            [1.2, 0.0, 1.2], [-2.75, 0.0, 1.2], [0.0, 2.75, 1.2]]])
    game = FixedTrainGame(cfg, 1, starts, torch.zeros(1, dtype=torch.bool), 3, 3, "cpu", 0)
    env = exploit_train.DecisionEnv(game, 12, "strike", make_strategy("zero", "guard", cfg, 1, "cpu", 0))
    env.reset()
    obs, _, term, _, _ = env.step({a: torch.zeros(1, 4) for a in env.possible_agents})
    assert not bool(term["strike_0"].any())
    assert float(obs["strike_0"][0, V.alive]) == 0.0 and float(obs["strike_1"][0, V.alive]) == 1.0
    assert float(obs["strike_1"][0][V.slot(cfg.pad_guards)].abs().sum()) == 0.0


def test_a_game_that_ends_mid_decision_restarts_fresh_and_the_new_game_is_not_kept(gates):
    """QC I-1(c), mutation T6: a Strike drone 0.02 m outside the zone flies in and reaches at tick k = 7 (1 < k < 12, measured);
    the core's own new game then plays the rest of the decision without ending; at the boundary that game is replaced by
    a fresh one (steps 0), so its stale ticks never reach training. (The 10 m test cannot see this: there every game
    ends on every tick.)"""
    cfg = exploit.variant_cfg(gates, "base").replace(**{"tag.mode": "off"})
    starts = torch.tensor([[[-2.8, -2.8, 1.2], [2.8, -2.8, 1.2], [-2.8, 2.8, 1.2],
                            [1.62, 0.0, 1.2], [0.0, 2.75, 1.2], [-2.75, 0.0, 1.2]]])
    game = FixedTrainGame(cfg, 1, starts, torch.zeros(1, dtype=torch.bool), 3, 3, "cpu", 0)
    env = exploit_train.DecisionEnv(game, 12, "strike", make_strategy("zero", "guard", cfg, 1, "cpu", 0))
    env.reset()
    act = {a: torch.zeros(1, 4) for a in env.possible_agents}
    act["strike_0"] = torch.tensor([[-1.0, 0.0, 0.0, 0.0]])
    _, rew, term, _, info = env.step(act)
    k = int(info["decision_end_tick"][0])
    assert bool(term["strike_0"][0]) and 1 < k < 12, k
    assert int(info["stale_ticks"][0]) == 12 - k
    assert float(rew["strike_0"][0]) == 1.0
    assert int(game.steps[0]) == 0                                      # the boundary's fresh game, not the core's
