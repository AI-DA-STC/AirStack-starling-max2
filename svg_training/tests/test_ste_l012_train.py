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
