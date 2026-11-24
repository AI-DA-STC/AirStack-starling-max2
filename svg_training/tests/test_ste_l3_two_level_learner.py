"""STE phase L3, slice 2, step 2: the two-level learner (design note ste_learning/drafts/L3_SLICE2_DESIGN.md §2, tests
4-7 and 12-17; test 18's loader half). Written before the code.

The learner: ``opponents/learned.TwoLevelPolicy`` (one network output split into the team head, index 0 = "free", and
the drone head) and ``ste/two_level.TwoLevelIPPO`` (skrl 2.1.0's IPPO with ``act``, ``record_transition`` and
``update`` replaced: per-head ratios each clipped and weighted by its own mask, per-head entropy with its own scale,
per-head approx KL; ``head_mask`` and ``head_log_prob`` in memory). The start: p(free) = 0.5. The checkpoint carries the
skill lists and is refused at load when they differ.

CPU only, small batches."""
import hashlib
import inspect
import math
import subprocess
import textwrap

import gymnasium
import numpy as np
import pytest
import torch

from _proc import child_env, child_python
from _torch_threads import default_torch_threads  # noqa: F401  (autouse: goldens at the default thread count)
from svg_training.core.observations import OBS_DIM, ObsView
from svg_training.opponents.scripted import make_strategy
from svg_training.ste import exploit, exploit_train, skills

V = ObsView()
HOLD = 12
SIDES = ("strike", "guard")
SCALES = {"team": 0.01, "drone": 0.03}                 # s_team != s_drone on purpose (design test 5)
LIST_A = {"team_strategies": {"strike": ["strike_sacrifice", "strike_converge"],
                              "guard": ["guard_parked_ring", "guard_field"]},
          "drone_skills": {"strike": ["strike_straight", "strike_flank", "strike_high", "strike_low"],
                           "guard": ["guard_parked_centre", "guard_mark_edge", "guard_mirror"]}}
WIDTHS = {"strike": (3, 4), "guard": (3, 3)}
# skrl 2.1.0's IPPO.update, read when TwoLevelIPPO.update was copied from it (24 Nov 2026)
SKRL_VERSION = "2.1.0"


def spec(scales=None, lists=LIST_A):
    return skills.learner_spec({"action": "skills", "choice": "two_level",
                                "team_strategies": {k: list(v) for k, v in lists["team_strategies"].items()},
                                "drone_skills": {k: list(v) for k, v in lists["drone_skills"].items()},
                                "entropy_scale": dict(scales or SCALES)})


@pytest.fixture(scope="module")
def gates():
    g = exploit.load_gates()
    assert g.trainer["decision_ticks"] == HOLD
    return g


def tiny(gates, **over):
    return {**gates.trainer, "num_games": 6, "rollouts": 2, "learning_epochs": 1, "mini_batches": 1, **over}


def other(side):
    return "guard" if side == "strike" else "strike"


def tl_env(gates, side, n=6, seed=7, sp=None):
    cfg = exploit.variant_cfg(gates, "base")
    game = exploit_train.TrainGame(cfg, n, 3, 3, device="cpu", seed=seed)
    opp = make_strategy(exploit.opponent_of(gates, "base", side), other(side), cfg, n, "cpu", seed + 1)
    return exploit_train.decision_env(game, HOLD, side, opp, sp or spec(), gates.players, seed)


def tl_learner(gates, side, n=6, **over):
    return exploit_train.Learner(tiny(gates, num_games=n, **over), tl_env(gates, side, n), "cpu", seed=11)


# --------------------------------------------------------------------------------------------- a learner without a game
def synth_agent(gates, widths, n=8, rollouts=4, seed=0, scales=None, **cfg_over):
    """A one-agent ``TwoLevelIPPO`` with the recipe's settings (cut down), no game: transitions are injected."""
    from svg_training.opponents.learned import OBS_SPACE, make_two_level_models
    from svg_training.ste.two_level import TwoLevelIPPO
    from skrl.memories.torch import RandomMemory
    torch.manual_seed(seed)
    names = ["guard_0"]
    settings = dict(gates.trainer, rollouts=rollouts, learning_epochs=1, mini_batches=2)
    models = make_two_level_models(names, [16, 16], widths, "cpu")
    cfg = exploit_train.ippo_cfg(settings, names, "cpu", **cfg_over)
    agent = TwoLevelIPPO(possible_agents=names, models=models,
                         memories={a: RandomMemory(memory_size=rollouts, num_envs=n, device="cpu") for a in names},
                         observation_spaces={a: OBS_SPACE for a in names},
                         state_spaces={a: gymnasium.spaces.Box(-1.0, 1.0, (1,)) for a in names},
                         action_spaces={a: gymnasium.spaces.MultiDiscrete(list(widths)) for a in names},
                         device="cpu", cfg=cfg, entropy_scale=dict(scales or SCALES))
    agent.init()
    return agent


def fake_batch(widths, n, rollouts, seed, mask=None):
    """rollouts x n injected transitions: observations, actions [team, drone], rewards, ends, values, per-head masks."""
    g = torch.Generator().manual_seed(seed)
    rows = []
    for _ in range(rollouts):
        act = torch.stack((torch.randint(0, widths[0], (n,), generator=g),
                           torch.randint(0, widths[1], (n,), generator=g)), dim=-1)
        m = mask if mask is not None else (torch.rand(n, 2, generator=g) < 0.5).float()
        rows.append({"observations": torch.randn(n, OBS_DIM, generator=g), "states": torch.zeros(n, 1),
                     "actions": act.float(), "rewards": torch.randn(n, 1, generator=g),
                     "terminated": torch.rand(n, 1, generator=g) < 0.2,
                     "truncated": torch.zeros(n, 1, dtype=torch.bool),
                     "values": torch.randn(n, 1, generator=g), "head_mask": m.expand(n, 2).clone()})
    return rows


def inject(agent, rows, uid="guard_0", heads=True):
    """Write ``rows`` into the agent's memory as ``record_transition`` would (the log-probabilities from the agent's own
    policy, with the observation scaler in eval mode, as ``act`` scores them); set the bootstrap observation."""
    pol = agent.policies[uid]
    for r in rows:
        act = r["actions"] if heads else r["actions"][:, :1]
        with torch.no_grad():
            obs = agent._observation_preprocessor[uid](r["observations"])
            _, out = pol.act({"observations": obs, "taken_actions": act}, role="policy")
        if heads:
            hlp = out["head_log_prob"]
            extra = {"head_mask": r["head_mask"], "head_log_prob": hlp,
                     "log_prob": (hlp * r["head_mask"]).sum(-1, keepdim=True)}
        else:
            extra = {"log_prob": out["log_prob"]}
        agent.memories[uid].add_samples(observations=r["observations"], states=r["states"], actions=act,
                                        rewards=r["rewards"], terminated=r["terminated"], truncated=r["truncated"],
                                        values=r["values"], **extra)
    agent._current_next_observations = {uid: rows[-1]["observations"]}
    agent._current_next_states = {uid: rows[-1]["states"]}


def run_update(agent, uid="guard_0", seed=5):
    torch.manual_seed(seed)
    agent.enable_models_training_mode(True)
    agent.update(timestep=0, timesteps=1, uid=uid)
    agent.enable_models_training_mode(False)


# ============================================================================================= test 4: masks, gradients
def _terms(pol, obs, act, old, mask, adv, scales=(0.01, 0.03), clip=0.2):
    from svg_training.ste.two_level import two_level_policy_terms
    _, out = pol.act({"observations": obs, "taken_actions": act}, role="policy")
    return two_level_policy_terms(out["head_log_prob"], old, pol.get_entropy(role="policy"), mask, adv, clip, scales)


def _grads(pol, terms):
    pol.zero_grad()
    (terms["policy_loss"] + terms["entropy_loss"]).backward()
    return [p.grad.clone() for p in pol.parameters()]


@pytest.mark.parametrize("head", [0, 1])
def test_a_masked_out_sample_stays_out_of_the_loss_and_its_gradient(head):
    """A sample whose head mask is 0 (a non-leader's team sample; a drone sample when a strategy flies): changing its
    stored action or old log-probability leaves the loss and every gradient bit for bit unchanged."""
    from svg_training.opponents.learned import TwoLevelPolicy
    torch.manual_seed(0)
    pol = TwoLevelPolicy([16, 16], (3, 4), "cpu")
    n = 40
    obs = torch.randn(n, OBS_DIM)
    act = torch.stack((torch.randint(0, 3, (n,)), torch.randint(0, 4, (n,))), -1).float()
    old = -torch.rand(n, 2) * 2
    mask = (torch.rand(n, 2) < 0.5).float()
    adv = torch.randn(n, 1)
    base = _terms(pol, obs, act, old, mask, adv)
    g0 = _grads(pol, base)
    off = mask[:, head] == 0
    assert 0 < int(off.sum()) < n
    act2, old2 = act.clone(), old.clone()
    act2[off, head] = (act2[off, head] + 1) % (3 if head == 0 else 4)
    old2[off, head] = old2[off, head] - 5.0
    again = _terms(pol, obs, act2, old2, mask, adv)
    for k in ("policy_loss", "entropy_loss", "kl"):
        assert torch.equal(base[k], again[k]), k
    for a, b in zip(g0, _grads(pol, again)):
        assert torch.equal(a, b)


@pytest.mark.parametrize("head", [0, 1])
def test_a_head_masked_out_everywhere_gets_no_gradient(head):
    """All samples with head ``head``'s mask 0: that head's rows of the output layer get exactly zero gradient."""
    from svg_training.opponents.learned import TwoLevelPolicy
    torch.manual_seed(1)
    pol = TwoLevelPolicy([16, 16], (3, 4), "cpu")
    n = 30
    mask = torch.ones(n, 2)
    mask[:, head] = 0.0
    t = _terms(pol, torch.randn(n, OBS_DIM), torch.stack((torch.randint(0, 3, (n,)), torch.randint(0, 4, (n,))),
                                                        -1).float(), -torch.rand(n, 2), mask, torch.randn(n, 1))
    _grads(pol, t)
    last = [m for m in pol.net if isinstance(m, torch.nn.Linear)][-1]
    rows = slice(0, 3) if head == 0 else slice(3, 7)
    keep = slice(3, 7) if head == 0 else slice(0, 3)
    assert bool((last.weight.grad[rows] == 0).all()) and bool((last.bias.grad[rows] == 0).all())
    assert bool((last.weight.grad[keep] != 0).any())
    assert float(t["kl"][head]) == 0.0                            # no sample with the mask on: KL 0, not NaN


def test_stored_and_recomputed_head_log_probabilities_agree_with_the_scaler_in_eval_mode(gates):
    """The memory's old per-head log-probabilities (from ``act``) equal the policy's on the stored observations and
    actions with the observation scaler in eval mode (skrl updates it in epoch 0, ippo.py:428-430), per decision."""
    learner = tl_learner(gates, "strike")
    agent, env = learner.agent, learner.env
    obs, states = learner.obs, learner.states
    agent.enable_training_mode(True)
    for t in range(2):
        with torch.no_grad():
            actions, _ = agent.act(obs, states, timestep=t, timesteps=2)
            nxt, rew, term, trunc, info = env.step(actions)
            agent.record_transition(observations=obs, states=states, actions=actions, rewards=rew,
                                    next_observations=nxt, next_states=env.state(), terminated=term, truncated=trunc,
                                    infos=info, timestep=t, timesteps=2)
        obs, states = nxt, env.state()
    for a in learner.names:
        mem = agent.memories[a]
        for t in range(2):
            o = mem.get_tensor_by_name("observations")[t]
            with torch.no_grad():
                _, out = agent.policies[a].act({"observations": agent._observation_preprocessor[a](o),
                                                "taken_actions": mem.get_tensor_by_name("actions")[t]},
                                               role="policy")
            assert torch.equal(out["head_log_prob"], mem.get_tensor_by_name("head_log_prob")[t]), (a, t)


# =============================================================================================== test 5: hand reference
def test_the_masked_loss_equals_a_hand_written_reference():
    """Random masks, s_team != s_drone, random advantages: policy loss, entropy loss and per-head KLs equal the design's
    formulas written here sample by sample in plain Python floats."""
    from svg_training.ste.two_level import two_level_policy_terms
    g = torch.Generator().manual_seed(3)
    n, clip, s = 25, 0.2, (0.01, 0.03)
    new = -torch.rand(n, 2, generator=g, dtype=torch.float64) * 2
    old = new + (torch.rand(n, 2, generator=g, dtype=torch.float64) - 0.5) * 0.8      # ratios in and out of the clip
    ent = torch.rand(n, 2, generator=g, dtype=torch.float64)
    mask = (torch.rand(n, 2, generator=g) < 0.6).double()
    adv = torch.randn(n, 1, generator=g, dtype=torch.float64)
    got = two_level_policy_terms(new, old, ent, mask, adv, clip, s)
    pol = ent_l = 0.0
    kl, cnt = [0.0, 0.0], [0, 0]
    for i in range(n):
        a = float(adv[i, 0])
        for h in range(2):
            if mask[i, h] == 0:
                continue
            r = math.exp(float(new[i, h] - old[i, h]))
            pol -= min(a * r, a * min(max(r, 1 - clip), 1 + clip)) / n
            ent_l -= s[h] * float(ent[i, h]) / n
            kl[h] += (r - 1) - math.log(r)
            cnt[h] += 1
    assert float(got["policy_loss"]) == pytest.approx(pol, rel=1e-12, abs=1e-12)
    assert float(got["entropy_loss"]) == pytest.approx(ent_l, rel=1e-12, abs=1e-12)
    for h in range(2):
        assert float(got["kl"][h]) == pytest.approx(kl[h] / cnt[h], rel=1e-12, abs=1e-12)
    clipped = ((new - old).exp() - 1).abs() > clip
    assert bool((clipped & (mask > 0)).any()) and bool((~clipped & (mask > 0)).any())


# =================================================================================================== test 6: copy guard
def test_the_update_equals_stock_ippo_where_the_two_coincide(gates):
    """A one-skill drone head (K_d = 1: log-probability 0, ratio 1, entropy 0) with every mask 1: two updates of
    ``TwoLevelIPPO`` equal stock IPPO with a categorical policy over the team head (its network from ours, the team
    rows), ``entropy_loss_scale = s_team``, on the same injected transitions and the same shuffle."""
    from skrl.memories.torch import RandomMemory
    from skrl.multi_agents.torch.ippo import IPPO
    from svg_training.opponents.learned import OBS_SPACE, SkillPolicy, StandinValue
    widths, n, rollouts = (3, 1), 8, 4
    ours = synth_agent(gates, widths, n, rollouts, seed=2, scales={"team": 0.02, "drone": 0.05})
    names = ["guard_0"]
    pol = SkillPolicy([16, 16], 3, "cpu")
    val = StandinValue([16, 16], "cpu")
    with torch.no_grad():
        src = list(ours.policies["guard_0"].net)
        for a, b in zip(pol.net, src):
            if isinstance(a, torch.nn.Linear):
                a.weight.copy_(b.weight[:a.weight.shape[0]])
                a.bias.copy_(b.bias[:a.bias.shape[0]])
        val.load_state_dict(ours.values["guard_0"].state_dict())
    settings = dict(gates.trainer, rollouts=rollouts, learning_epochs=1, mini_batches=2, entropy_loss_scale=0.02)
    stock = IPPO(possible_agents=names, models={"guard_0": {"policy": pol, "value": val}},
                 memories={a: RandomMemory(memory_size=rollouts, num_envs=n, device="cpu") for a in names},
                 observation_spaces={a: OBS_SPACE for a in names},
                 state_spaces={a: gymnasium.spaces.Box(-1.0, 1.0, (1,)) for a in names},
                 action_spaces={a: gymnasium.spaces.Discrete(3) for a in names}, device="cpu",
                 cfg=exploit_train.ippo_cfg(settings, names, "cpu"))
    stock.init()
    for k in range(2):
        rows = fake_batch(widths, n, rollouts, seed=10 + k, mask=torch.ones(1, 2))
        inject(ours, rows)
        inject(stock, rows, heads=False)
        run_update(ours, seed=20 + k)
        run_update(stock, seed=20 + k)
    for (na, a), (nb, b) in zip(ours.policies["guard_0"].net.named_parameters(), pol.net.named_parameters()):
        assert torch.allclose(a[:b.shape[0]], b, rtol=1e-6, atol=1e-7), na
    for (na, a), (_, b) in zip(ours.values["guard_0"].named_parameters(), val.named_parameters()):
        assert torch.allclose(a, b, rtol=1e-6, atol=1e-7), na
    for k in ("running_mean", "running_variance"):
        assert torch.equal(getattr(ours._observation_preprocessor["guard_0"], k),
                           getattr(stock._observation_preprocessor["guard_0"], k)), k
    moved = [m for m in ours.policies["guard_0"].net if isinstance(m, torch.nn.Linear)][-1].weight
    assert bool((moved[:3] != 0).any())


def test_two_level_act_draws_team_then_drone_as_skrls_multicategorical_mixin():
    """The sample order: under the same seed, ``TwoLevelPolicy.act`` gives the samples of skrl's
    ``MultiCategoricalMixin`` on the same logits (team head first)."""
    from skrl.models.torch import Model, MultiCategoricalMixin
    from svg_training.opponents.learned import OBS_SPACE, TwoLevelPolicy
    torch.manual_seed(4)
    ours = TwoLevelPolicy([16, 16], (3, 4), "cpu")
    with torch.no_grad():
        for p in ours.parameters():
            p.normal_(0.0, 1.0)

    class Ref(MultiCategoricalMixin, Model):
        def __init__(self):
            Model.__init__(self, observation_space=OBS_SPACE, action_space=gymnasium.spaces.MultiDiscrete([3, 4]),
                           device="cpu")
            MultiCategoricalMixin.__init__(self, unnormalized_log_prob=True)

        def compute(self, inputs, role=""):
            return ours.net(inputs["observations"]), {}
    obs = torch.randn(64, OBS_DIM)
    torch.manual_seed(9)
    a, _ = ours.act({"observations": obs}, role="policy")
    torch.manual_seed(9)
    b, _ = Ref().act({"observations": obs}, role="policy")
    assert torch.equal(a.long(), b.long())
    assert a[:, 0].unique().numel() > 1 and a[:, 1].unique().numel() > 1


# ================================================================================================= test 7: save, reload
CHILD = textwrap.dedent("""
    import sys, torch
    from svg_training.ste import exploit, exploit_train, skills
    saved = torch.load(sys.argv[1], weights_only=False)
    gates = exploit.load_gates()
    cfg = exploit.variant_cfg(gates, "base")
    obs = saved["obs"]
    sp = skills.learner_spec(saved["table"])
    d = skills.two_level_dispatch(sp, gates.players, saved["team"], cfg, obs.shape[0], "cpu", 0)
    team = exploit_train.skill_team_from_modules(saved["team"], saved["learner"], saved["hidden"], d, "cpu")
    logits = team.logits(obs)
    heads = d.greedy(logits)
    skill = team.choose(obs)
    torch.save({"logits": logits, "heads": heads, "skill": skill, "command": team.command(obs, skill)}, sys.argv[2])
""")


def _table(lists=LIST_A):
    return {"action": "skills", "choice": "two_level",
            "team_strategies": {k: list(v) for k, v in lists["team_strategies"].items()},
            "drone_skills": {k: list(v) for k, v in lists["drone_skills"].items()}, "entropy_scale": dict(SCALES)}


@pytest.mark.parametrize("side", SIDES)
def test_two_updates_then_save_and_reload_in_a_fresh_process_give_the_golden_rows(gates, tmp_path, side):
    learner = tl_learner(gates, side)
    env = learner.env
    for _ in range(2):
        stats = learner.update()
        assert stats["losses"] and all(np.isfinite(v) for v in stats["losses"].values())
    obs = env._game_obs[side].clone()
    team = learner.team()
    rows = {"logits": team.logits(obs)}
    rows["heads"] = env.skills.greedy(rows["logits"])
    rows["skill"] = team.choose(obs)
    rows["command"] = team.command(obs, rows["skill"])
    assert rows["logits"].shape == (6, 3, sum(WIDTHS[side]))
    saved = learner.saved()
    assert set(saved) == {"skills", "modules"}
    assert saved["skills"] == skills.skills_meta(env.skills)
    assert saved["skills"]["team_strategies"] == LIST_A["team_strategies"][side]
    path = tmp_path / "saved.pt"
    torch.save({"learner": saved, "hidden": list(gates.trainer["hidden"]), "team": side, "table": _table(),
                "obs": obs}, path)
    out = tmp_path / "rows.pt"
    r = subprocess.run([child_python(), "-c", CHILD, str(path), str(out)],
                       env={**child_env(), "CUDA_VISIBLE_DEVICES": ""}, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr[-2000:]
    got = torch.load(out, weights_only=False)
    for k, v in rows.items():
        assert torch.equal(got[k], v), k


def test_a_reload_with_other_skill_lists_is_refused(gates):
    learner = tl_learner(gates, "guard")
    saved = learner.saved()
    cfg = exploit.variant_cfg(gates, "base")
    hidden = list(gates.trainer["hidden"])
    swapped = dict(gates.players, guards=list(reversed(gates.players["guards"])))
    d = skills.TwoLevelDispatch("guard", swapped["guards"], LIST_A["team_strategies"]["guard"],
                                LIST_A["drone_skills"]["guard"], cfg, 4, "cpu", 0)
    with pytest.raises(ValueError, match="skill lists"):
        exploit_train.skill_team_from_modules("guard", saved, hidden, d, "cpu")
    moved = {"team_strategies": {**LIST_A["team_strategies"], "guard": ["guard_parked_ring", "guard_mark_edge",
                                                                       "guard_field"]},
             "drone_skills": {**LIST_A["drone_skills"], "guard": ["guard_parked_centre", "guard_mirror"]}}
    d2 = skills.two_level_dispatch(spec(lists=moved), gates.players, "guard", cfg, 4, "cpu", 0)
    with pytest.raises(ValueError, match="skill lists"):
        exploit_train.skill_team_from_modules("guard", saved, hidden, d2, "cpu")
    with pytest.raises(ValueError, match="skill lists"):
        learner.load_state({**learner.state(), "skills": {**learner.state()["skills"], "players": swapped["guards"]}})
    d3 = skills.two_level_dispatch(spec(), gates.players, "guard", cfg, 4, "cpu", 0)
    exploit_train.skill_team_from_modules("guard", saved, hidden, d3, "cpu")          # the same lists load
    learner.load_state(learner.state())


# =================================================================================================== test 12: the start
@pytest.mark.parametrize("side", SIDES)
def test_the_start_has_p_free_one_half_and_plays_free_with_the_first_drone_skill(gates, side):
    learner = tl_learner(gates, side)
    obs = torch.randn(5, 3, OBS_DIM, generator=torch.Generator().manual_seed(1))
    team = learner.team()
    logits = team.logits(obs)
    t, k = WIDTHS[side]
    p = torch.softmax(logits[..., :t].double(), -1)
    assert torch.allclose(p[..., 0], torch.full_like(p[..., 0], 0.5), atol=1e-6)
    assert torch.allclose(p[..., 1:], torch.full_like(p[..., 1:], 0.25), atol=1e-6)
    q = torch.softmax(logits[..., t:].double(), -1)
    assert torch.allclose(q, torch.full_like(q, 1.0 / k), atol=1e-6)
    assert team.dispatch.greedy(logits).tolist() == [[[skills.FREE, 0]] * 3] * 5
    stats = learner.update()                                          # runs with the per-head scales
    assert {f"Loss / Entropy team ({a})" for a in learner.names} <= set(stats["losses"])
    assert all(np.isfinite(v) for v in stats["losses"].values())


def test_the_two_level_learner_needs_its_entropy_scales_and_the_zero_start(gates):
    env = tl_env(gates, "strike")
    env.entropy_scale = None
    with pytest.raises(ValueError, match="entropy"):
        exploit_train.Learner(tiny(gates), env, "cpu", seed=3)
    with pytest.raises(ValueError, match="zero_mean_init"):
        exploit_train.Learner(tiny(gates, zero_mean_init=False), tl_env(gates, "strike"), "cpu", seed=3)


# ============================================================================================= test 13: the pinned copy
def test_the_update_copy_is_pinned_to_skrl_2_1_0():
    import skrl
    from skrl.multi_agents.torch.ippo import IPPO
    from svg_training.ste import two_level
    assert skrl.__version__ == SKRL_VERSION == two_level.SKRL_VERSION
    assert hashlib.sha256(inspect.getsource(IPPO.update).encode()).hexdigest() == two_level.IPPO_UPDATE_SHA256
    assert two_level.update_source_sha256() == two_level.IPPO_UPDATE_SHA256


# ==================================================================================================== test 14: KL paths
def _steps_and_kls(gates, threshold):
    widths = (3, 4)
    agent = synth_agent(gates, widths, seed=6, kl_threshold=threshold)
    inject(agent, fake_batch(widths, 8, 4, seed=7))
    count = [0]
    step = agent.optimizers["guard_0"].step

    def counted(*a, **k):
        count[0] += 1
        return step(*a, **k)
    agent.optimizers["guard_0"].step = counted
    run_update(agent)
    return count[0], [k.clone() for k in agent.last_kls]


def test_the_kl_early_stop_uses_the_summed_per_head_kl(gates):
    """Off: both minibatches step. On, with the threshold between the larger per-head KL of the first minibatch and the
    sum of the two: the first minibatch stops (a rule on either head alone would not)."""
    steps, kls = _steps_and_kls(gates, 0.0)
    assert steps == 2 and len(kls) == 2
    kt, kd = (float(x) for x in kls[0])
    assert kt > 0 and kd > 0
    steps_on, kls_on = _steps_and_kls(gates, max(kt, kd) + 0.5 * min(kt, kd))
    assert steps_on == 0 and len(kls_on) == 1
    assert torch.equal(kls_on[0], kls[0])


def test_kl_adaptive_lr_is_stepped_with_the_mean_summed_kl(gates):
    from skrl.resources.schedulers.torch import KLAdaptiveLR
    widths = (3, 4)
    agent = synth_agent(gates, widths, seed=8, learning_rate_scheduler={"guard_0": KLAdaptiveLR},
                        learning_rate_scheduler_kwargs={"guard_0": {"kl_threshold": 1e-9}})
    inject(agent, fake_batch(widths, 8, 4, seed=9))
    seen = []
    sched = agent.schedulers["guard_0"]
    step = sched.step
    sched.step = lambda kl=None, *a, **k: (seen.append(kl), step(kl, *a, **k))[1]
    lr0 = agent.optimizers["guard_0"].param_groups[0]["lr"]
    run_update(agent)
    td = agent.tracking_data
    kl = td["Policy / KL team (guard_0)"][-1] + td["Policy / KL drone (guard_0)"][-1]
    assert len(seen) == 1 and seen[0] == pytest.approx(kl, rel=1e-6)
    assert agent.optimizers["guard_0"].param_groups[0]["lr"] < lr0        # far above 2 x 1e-9: the rate falls


# =============================================================================================== test 15: gradient clip
def test_grad_norm_clip_holds_under_masking(gates):
    widths = (3, 4)
    agent = synth_agent(gates, widths, seed=10, grad_norm_clip=1e-3)
    rows = fake_batch(widths, 8, 4, seed=11)
    assert any(bool((r["head_mask"] == 0).any()) for r in rows)
    inject(agent, rows)
    norms = []
    opt = agent.optimizers["guard_0"]
    step = opt.step

    def measured(*a, **k):
        ps = [p for g in opt.param_groups for p in g["params"] if p.grad is not None]
        norms.append(float(torch.linalg.vector_norm(torch.stack([torch.linalg.vector_norm(p.grad) for p in ps]))))
        return step(*a, **k)
    opt.step = measured
    run_update(agent)
    assert norms and all(x <= 1e-3 * (1 + 1e-5) for x in norms)


# ====================================================================================================== test 16: memory
def test_head_mask_and_head_log_prob_are_in_memory_as_recorded(gates):
    learner = tl_learner(gates, "guard")
    agent, env = learner.agent, learner.env
    for a in learner.names:
        for name in ("head_mask", "head_log_prob"):
            t = agent.memories[a].get_tensor_by_name(name)
            assert t.dtype == torch.float32 and t.shape[-1] == 2, (a, name)
    agent.enable_training_mode(True)
    with torch.no_grad():
        actions, outputs = agent.act(learner.obs, learner.states, timestep=0, timesteps=1)
        nxt, rew, term, trunc, info = env.step(actions)
        agent.record_transition(observations=learner.obs, states=learner.states, actions=actions, rewards=rew,
                                next_observations=nxt, next_states=env.state(), terminated=term, truncated=trunc,
                                infos=info, timestep=0, timesteps=1)
    for i, a in enumerate(learner.names):
        mem = agent.memories[a]
        assert torch.equal(mem.get_tensor_by_name("head_mask")[0], info["head_mask"][:, i].float())
        assert torch.equal(mem.get_tensor_by_name("head_log_prob")[0], outputs[a]["head_log_prob"])
        want = (outputs[a]["head_log_prob"] * info["head_mask"][:, i]).sum(-1, keepdim=True)
        assert torch.equal(mem.get_tensor_by_name("log_prob")[0], want)
        assert torch.equal(mem.get_tensor_by_name("actions")[0], actions[a].float())
    assert float(info["head_mask"][..., 0].sum()) == env.game.num_games          # one leader per game


# ================================================================================================ test 17: absent slots
def test_an_absent_slot_under_free_still_trains_until_slice_3(gates):
    """Parity with the velocity route until slice 3's absent-drone mask: a slot absent at the decision's start has drone
    mask 1 when its leader chose "free" (it trains on its zeroed observation and the team reward). Slice 3 flips
    this."""
    cfg = exploit.variant_cfg(gates, "base")
    d = skills.two_level_dispatch(spec(), gates.players, "guard", cfg, 2, "cpu", 0)
    obs = torch.zeros(2, 3, OBS_DIM)
    obs[..., V.alive] = torch.tensor([[1.0, 1.0, 0.0], [0.0, 0.0, 0.0]])   # game 2: no live Guard (the game goes on)
    _, mask = d.resolve_two_level(torch.zeros(2, 3, 2, dtype=torch.long), obs)
    assert mask[0, 2].tolist() == [0.0, 1.0]
    assert mask[1].tolist() == [[0.0, 1.0], [0.0, 1.0], [1.0, 1.0]]


# ===================================================================================================== test 18: loaders
def test_a_velocity_checkpoint_still_loads_and_a_two_level_one_is_refused_by_the_velocity_loader(gates):
    hidden = list(gates.trainer["hidden"])
    cfg = exploit.variant_cfg(gates, "base")
    game = exploit_train.TrainGame(cfg, 4, 3, 3, device="cpu", seed=7)
    env = exploit_train.DecisionEnv(game, HOLD, "guard", make_strategy("strike_straight", "strike", cfg, 4, "cpu", 1))
    vel = exploit_train.Learner(tiny(gates, num_games=4), env, "cpu", seed=3)
    assert vel.saved().keys() == vel.modules().keys()                     # the velocity layout is unchanged
    team = exploit_train.team_from_modules("guard", vel.saved(), hidden, "cpu")
    assert isinstance(team, exploit.LearnerTeam)
    two = tl_learner(gates, "guard", n=4)
    with pytest.raises(ValueError, match="skill_team_from_modules"):
        exploit_train.team_from_modules("guard", two.saved(), hidden, "cpu")
