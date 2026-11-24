"""STE phase L3, slice 3, step 3: the absent-drone mask, as library pieces (``ste/masking.py``; design note
ste_learning/drafts/L3_SLICE3_DESIGN.md §1 and "Revision after the review" B1, A1-A3, B-S). Wiring into the learners
is step 4; here every piece is checked on its own, against stock skrl where the mask is all live (bit for bit) and
against hand-built references (the live rows only) at the gradient level otherwise. CPU only."""
import copy
import hashlib
import inspect
import math

import pytest
import torch
import torch.nn.functional as F

from skrl.multi_agents.torch.ippo import ippo as skrl_ippo
from skrl.resources.preprocessors.torch import RunningStandardScaler
from svg_training.ste import masking

G, LAM = 0.99, 0.95


def gae_inputs(t=6, n=4, seed=0):
    g = torch.Generator().manual_seed(seed)
    return {"rewards": torch.randn(t, n, 1, generator=g), "terminated": torch.rand(t, n, 1, generator=g) < 0.2,
            "values": torch.randn(t, n, 1, generator=g), "last_values": torch.randn(n, 1, generator=g)}


# ================================================================================================ masked GAE
def test_all_live_gae_is_skrls_bit_for_bit():
    x = gae_inputs()
    t, n = x["rewards"].shape[:2]
    want_r, want_a = skrl_ippo.compute_gae(rewards=x["rewards"], terminated=x["terminated"],
                                           truncated=torch.zeros_like(x["terminated"]), values=x["values"],
                                           last_values=x["last_values"], discount_factor=G, lambda_coefficient=LAM)
    got = masking.masked_gae(x["rewards"], x["terminated"], x["values"], x["last_values"],
                             torch.ones(t, n, 1, dtype=torch.bool), torch.ones(n, 1, dtype=torch.bool),
                             torch.zeros(n, 1), G, LAM)
    assert torch.equal(got["returns"], want_r) and torch.equal(got["advantages"], want_a)


def hand_gae(r, term, v, last_v, alive, alive_next, tail, g=G, lam=LAM):
    """The design's rule for one slot in Python floats: live steps as GAE; an absent step's effective value is its
    reward-to-go (V_eff = r + g * not_done * next), its advantage 0; a cut absent tail ends on ``tail``."""
    t = len(r)
    nv = [0.0] * t
    veff = [0.0] * t
    adv = [0.0] * t
    for i in reversed(range(t)):
        if term[i]:
            nxt = 0.0
        elif i + 1 < t:
            nxt = v[i + 1] if alive[i + 1] else veff[i + 1]
        else:
            nxt = last_v if alive_next else tail
        nv[i] = nxt
        if alive[i]:
            a_next = adv[i + 1] if (i + 1 < t and alive[i + 1] and not term[i]) else 0.0
            adv[i] = r[i] - v[i] + g * (0.0 if term[i] else 1.0) * (nxt + lam * a_next)
        else:
            veff[i] = r[i] + g * (0.0 if term[i] else 1.0) * nxt
    return adv


def test_an_absent_tail_passes_its_teams_rewards_through_and_normalises_over_live_rows():
    torch.manual_seed(1)
    t, n = 7, 3
    r = torch.randn(t, n, 1, dtype=torch.float64)
    v = torch.randn(t, n, 1, dtype=torch.float64)
    last_v = torch.randn(n, 1, dtype=torch.float64)
    term = torch.zeros(t, n, 1, dtype=torch.bool)
    alive = torch.ones(t, n, 1, dtype=torch.bool)
    alive[3:, 0] = False                         # slot 0: tagged after step 2, absent to the rollout's end (cut tail)
    alive[2:5, 1] = False                        # slot 1: absent 2..4, its game ends at 4, a fresh game from 5
    term[4, 1] = True
    alive_next = alive[-1].clone()
    tail = torch.tensor([[0.7], [0.0], [0.0]], dtype=torch.float64)
    got = masking.masked_gae(r, term, v, last_v, alive, alive_next, tail, G, LAM)
    raw = torch.zeros(t, n, dtype=torch.float64)
    for s in range(n):
        raw[:, s] = torch.tensor(hand_gae(r[:, s, 0].tolist(), term[:, s, 0].tolist(), v[:, s, 0].tolist(),
                                          float(last_v[s]), alive[:, s, 0].tolist(), bool(alive_next[s]),
                                          float(tail[s])), dtype=torch.float64)
    live = alive[..., 0]
    mean, std = raw[live].mean(), raw[live].std()
    want = torch.where(live, (raw - mean) / (std + 1e-8), torch.zeros_like(raw))
    assert torch.allclose(got["advantages"][..., 0], want, rtol=1e-10, atol=1e-12)
    assert bool((got["advantages"][~alive] == 0).all())
    assert torch.allclose(got["returns"][alive], raw[live] + v[alive], rtol=1e-12, atol=1e-12)


def test_the_values_of_absent_rows_change_no_live_advantage():
    x = gae_inputs(t=8, n=3, seed=4)
    alive = torch.ones(8, 3, 1, dtype=torch.bool)
    alive[5:, 2] = False
    alive[2:, 0] = False
    args = (x["rewards"], x["terminated"], x["values"], x["last_values"], alive, alive[-1].clone(), torch.zeros(3, 1))
    a = masking.masked_gae(*args, G, LAM)
    v2 = x["values"].clone()
    v2[~alive] = 123.0                               # the critic's output on all-zero observations: never read
    b = masking.masked_gae(x["rewards"], x["terminated"], v2, x["last_values"], alive, alive[-1].clone(),
                           torch.zeros(3, 1), G, LAM)
    assert torch.equal(a["advantages"], b["advantages"])


def test_live_counts_zero_and_one_are_guarded():
    x = gae_inputs(t=3, n=2, seed=5)
    none = torch.zeros(3, 2, 1, dtype=torch.bool)
    out = masking.masked_gae(x["rewards"], x["terminated"], x["values"], x["last_values"], none,
                             torch.zeros(2, 1, dtype=torch.bool), torch.zeros(2, 1), G, LAM)
    assert bool((out["advantages"] == 0).all()) and bool(torch.isfinite(out["returns"]).all())
    one = none.clone()
    one[1, 0] = True
    out = masking.masked_gae(x["rewards"], x["terminated"], x["values"], x["last_values"], one,
                             torch.zeros(2, 1, dtype=torch.bool), torch.zeros(2, 1), G, LAM)
    assert bool((out["advantages"] == 0).all())                 # one live row: mean subtracted, std 1
    assert bool(torch.isfinite(out["advantages"]).all())


# ================================================================================================ the bootstrap
def test_own_last_live_value_and_its_gap():
    v = torch.arange(12, dtype=torch.float32).reshape(4, 3, 1)
    alive = torch.tensor([[1, 1, 0], [1, 0, 0], [0, 0, 0], [0, 0, 0]], dtype=torch.bool)[..., None]
    val, gap, has = masking.own_last_live(v, alive)
    assert val[:, 0].tolist() == [3.0, 1.0, 0.0] and gap.tolist() == [3, 4, 0] and has.tolist() == [True, True, False]


def test_the_team_bootstrap_is_the_raw_mean_of_live_mates_else_the_discounted_own_value():
    last = {"guard_0": torch.tensor([[1.0], [10.0]]), "guard_1": torch.tensor([[3.0], [20.0]]),
            "guard_2": torch.tensor([[5.0], [40.0]])}
    alive_next = {"guard_0": torch.tensor([False, False]), "guard_1": torch.tensor([True, False]),
                  "guard_2": torch.tensor([True, False])}
    own = {a: (torch.tensor([[7.0], [8.0]]), torch.tensor([2, 3]), torch.tensor([True, False])) for a in last}
    out = masking.team_bootstrap(last, alive_next, own, G)
    b0, c0 = out["guard_0"]
    assert b0[0, 0] == pytest.approx(4.0)                       # mates 1 and 2 live: mean of 3 and 5 (raw units)
    assert b0[1, 0] == pytest.approx(0.0) and c0 == {"mates": 1, "own": 0, "none": 1}     # no mate, no own value
    b1, c1 = out["guard_1"]
    assert b1[0, 0] == pytest.approx(5.0)                       # its only live mate is guard_2 (itself excluded)
    own2 = {a: (torch.tensor([[7.0], [8.0]]), torch.tensor([2, 3]), torch.tensor([True, True])) for a in last}
    b, c = masking.team_bootstrap(last, alive_next, own2, G)["guard_0"]
    assert b[1, 0] == pytest.approx(8.0 * G ** 3) and c == {"mates": 1, "own": 1, "none": 0}


def _tiny_agent(n=4, rollouts=3):
    import gymnasium
    from skrl.memories.torch import RandomMemory
    from skrl.multi_agents.torch.ippo import IPPO, IPPO_CFG
    from svg_training.envs.skrl_adapter import skrl_kwargs_defaults
    from svg_training.opponents.learned import OBS_SPACE, make_models
    torch.manual_seed(3)
    names = ["guard_0", "guard_1"]
    kw = skrl_kwargs_defaults(names)
    kw["observation_preprocessor_kwargs"] = {a: {"size": OBS_SPACE, "device": "cpu"} for a in names}
    kw["value_preprocessor_kwargs"] = {a: {"size": 1, "device": "cpu"} for a in names}
    cfg = IPPO_CFG(rollouts=rollouts, learning_epochs=1, mini_batches=1, learning_rate=1e-3,
                   observation_preprocessor={a: RunningStandardScaler for a in names},
                   value_preprocessor={a: RunningStandardScaler for a in names},
                   experiment={"write_interval": 0, "checkpoint_interval": 0}, **kw)
    agent = IPPO(possible_agents=names, models=make_models(names, [16, 16], "cpu"),
                 memories={a: RandomMemory(memory_size=rollouts, num_envs=n, device="cpu") for a in names},
                 observation_spaces={a: OBS_SPACE for a in names},
                 state_spaces={a: gymnasium.spaces.Box(-1.0, 1.0, (1,)) for a in names},
                 action_spaces={a: gymnasium.spaces.Box(-1.0, 1.0, (4,)) for a in names}, device="cpu", cfg=cfg)
    agent.init()
    gen = torch.Generator().manual_seed(5)
    for a in names:
        agent._value_preprocessor[a](torch.randn(20, 1, generator=gen) * 3 + 1, train=True)     # a non-trivial scaler
        agent._observation_preprocessor[a](torch.randn(20, 71, generator=gen), train=True)
    for _ in range(rollouts):
        for a in names:
            agent.memories[a].add_samples(observations=torch.randn(n, 71, generator=gen), states=torch.zeros(n, 1),
                                          actions=torch.rand(n, 4, generator=gen) * 2 - 1,
                                          rewards=torch.randn(n, 1, generator=gen),
                                          terminated=torch.zeros(n, 1, dtype=torch.bool),
                                          truncated=torch.zeros(n, 1, dtype=torch.bool),
                                          log_prob=torch.randn(n, 1, generator=gen),
                                          values=torch.randn(n, 1, generator=gen))
    agent._current_next_observations = {a: torch.randn(n, 71, generator=gen) for a in names}
    agent._current_next_states = {a: torch.zeros(n, 1) for a in names}
    return agent


def test_the_pre_pass_gives_the_last_values_the_stock_update_computes():
    """B1: the pre-pass (before any update, every agent, the update's own order, no_grad and autocast) gives, in raw
    units, exactly the last values skrl's update passes to compute_gae."""
    agent = _tiny_agent()
    pre = masking.last_values_prepass(agent)
    seen = {}
    real = skrl_ippo.compute_gae

    def spy(**kw):
        seen[len(seen)] = kw["last_values"].clone()
        return real(**kw)
    stock = copy.deepcopy(agent)
    skrl_ippo.compute_gae = spy
    try:
        stock.enable_models_training_mode(True)
        for a in stock.possible_agents:
            stock.update(timestep=0, timesteps=1, uid=a)
    finally:
        skrl_ippo.compute_gae = real
    for i, a in enumerate(agent.possible_agents):
        assert torch.equal(pre[a], seen[i]), a


# ================================================================================================ scalers
def _scaler(seed=0):
    s = RunningStandardScaler(5, device="cpu")
    s(torch.randn(30, 5, generator=torch.Generator().manual_seed(seed)) * 2 + 1, train=True)
    return s


def _stats(s):
    return [s.running_mean.clone(), s.running_variance.clone(), s.current_count.clone()]


def test_a_live_scaler_update_is_skrls_on_the_live_rows_bit_for_bit():
    x = torch.randn(12, 5, generator=torch.Generator().manual_seed(1))
    live = torch.tensor([True, False] * 6)
    a, b, c = _scaler(), _scaler(), _scaler()
    masking.masked_scaler_update(a, x, torch.ones(12, dtype=torch.bool))
    b(x, train=True)
    assert all(torch.equal(p, q) for p, q in zip(_stats(a), _stats(b)))
    masking.masked_scaler_update(c, x, live)
    d = _scaler()
    d(x[live], train=True)
    assert all(torch.equal(p, q) for p, q in zip(_stats(c), _stats(d)))


@pytest.mark.parametrize("count", [0, 1])
def test_a_scaler_update_with_fewer_than_two_live_rows_is_skipped(count):
    x = torch.randn(6, 5)
    live = torch.zeros(6, dtype=torch.bool)
    live[:count] = True
    s = _scaler()
    before = _stats(s)
    masking.masked_scaler_update(s, x, live)
    assert all(torch.equal(p, q) for p, q in zip(before, _stats(s)))


def test_the_pins_hold_for_the_installed_skrl():
    from skrl.resources.preprocessors.torch import running_standard_scaler
    masking.check_pins()
    src = inspect.getsource(running_standard_scaler.RunningStandardScaler._parallel_variance)
    assert hashlib.sha256(src.encode()).hexdigest() == masking.PARALLEL_VARIANCE_SHA256


# ================================================================================================ the optimiser step
def test_no_optimiser_step_with_no_live_sample():
    net = torch.nn.Linear(3, 1)
    opt = torch.optim.Adam(net.parameters(), lr=0.1)
    scaler = torch.amp.GradScaler(device="cpu", enabled=False)
    (net(torch.randn(4, 3)).sum() * 0.0).backward()
    before = [p.clone() for p in net.parameters()]
    assert masking.masked_optimizer_step(scaler, opt, 0) is False
    assert all(torch.equal(p, q) for p, q in zip(before, net.parameters())) and not opt.state
    net(torch.randn(4, 3)).sum().backward()
    assert masking.masked_optimizer_step(scaler, opt, 3) is True
    assert opt.state and any(not torch.equal(p, q) for p, q in zip(before, net.parameters()))


# ================================================================================================ time-limit bootstrap
def test_the_time_limit_bootstrap_skips_absent_slots():
    r = torch.tensor([[1.0], [1.0], [1.0]])
    trunc = torch.tensor([[True], [True], [False]])
    nv = torch.tensor([[2.0], [2.0], [2.0]])
    alive = torch.tensor([True, False, True])
    out = masking.time_limit_rewards(r, trunc, nv, G, alive)
    assert out[:, 0].tolist() == pytest.approx([1.0 + G * 2.0, 1.0, 1.0])


# ======================================================================================= losses, gradient level
def _ppo_batch(b=20, seed=2):
    g = torch.Generator().manual_seed(seed)
    w = torch.randn(3, 1, generator=g, requires_grad=True)
    x = torch.randn(b, 3, generator=g)
    old = torch.randn(b, 1, generator=g) * 0.1
    adv = torch.randn(b, 1, generator=g)
    live = torch.rand(b, generator=g) < 0.6
    return w, x, old, adv, live


def _grad(loss, w):
    (gw,) = torch.autograd.grad(loss, w, retain_graph=True)
    return gw


def test_the_masked_policy_and_entropy_terms_equal_the_stock_terms_on_the_live_rows():
    w, x, old, adv, live = _ppo_batch()
    lp = x @ w * 0.1
    ent = (x @ w).abs()
    got = masking.masked_policy_terms(lp, old, ent, adv, live, 0.2, 0.01)
    ratio = torch.exp(lp[live] - old[live])
    want_pol = -torch.min(adv[live] * ratio, adv[live] * torch.clip(ratio, 0.8, 1.2)).mean()
    want_ent = -0.01 * ent[live].mean()
    assert torch.allclose(_grad(got["policy_loss"], w), _grad(want_pol, w), rtol=1e-6, atol=1e-8)
    assert torch.allclose(_grad(got["entropy_loss"], w), _grad(want_ent, w), rtol=1e-6, atol=1e-8)
    old2, adv2 = old.clone(), adv.clone()
    old2[~live], adv2[~live] = 9.0, -9.0                         # absent rows: nothing they hold reaches the loss
    again = masking.masked_policy_terms(x @ w * 0.1, old2, (x @ w).abs(), adv2, live, 0.2, 0.01)
    assert torch.equal(_grad(again["policy_loss"], w), _grad(masking.masked_policy_terms(
        x @ w * 0.1, old, (x @ w).abs(), adv, live, 0.2, 0.01)["policy_loss"], w))


def test_all_live_policy_terms_are_the_stock_expressions_bit_for_bit():
    w, x, old, adv, _ = _ppo_batch()
    lp, ent = x @ w * 0.1, (x @ w).abs()
    got = masking.masked_policy_terms(lp, old, ent, adv, torch.ones(len(x), dtype=torch.bool), 0.2, 0.01)
    ratio = torch.exp(lp - old)
    assert torch.equal(got["policy_loss"], -torch.min(adv * ratio, adv * torch.clip(ratio, 0.8, 1.2)).mean())
    assert torch.equal(got["entropy_loss"], -0.01 * ent.mean())


@pytest.mark.parametrize("clip", [0.0, 0.3])
def test_the_masked_value_loss_equals_the_stock_loss_on_the_live_rows(clip):
    w, x, old, adv, live = _ppo_batch(seed=7)
    pred = x @ w
    got = masking.masked_value_loss(adv, pred, old, live, clip, 2.0)
    p = pred[live]
    if clip > 0:
        p = old[live] + torch.clip(p - old[live], -clip, clip)
    want = 2.0 * F.mse_loss(adv[live], p)
    assert torch.allclose(_grad(got, w), _grad(want, w), rtol=1e-6, atol=1e-8)
    all_live = masking.masked_value_loss(adv, x @ w, old, torch.ones(len(x), dtype=torch.bool), clip, 2.0)
    p = x @ w
    if clip > 0:
        p = old + torch.clip(p - old, -clip, clip)
    assert torch.equal(all_live, 2.0 * F.mse_loss(adv, p))


def test_the_two_level_terms_take_alive_into_the_head_masks_and_live_counts():
    """h' = h * alive, means over the live samples: equal (gradient level) to slice 2's terms on the live rows only."""
    from svg_training.ste.two_level import two_level_policy_terms
    g = torch.Generator().manual_seed(9)
    w = torch.randn(3, 2, generator=g, requires_grad=True)
    x = torch.randn(30, 3, generator=g)
    old = torch.randn(30, 2, generator=g) * 0.1
    mask = (torch.rand(30, 2, generator=g) < 0.6).float()
    adv = torch.randn(30, 1, generator=g)
    live = torch.rand(30, generator=g) < 0.7
    lp, ent = x @ w * 0.1, (x @ w).abs()
    got = two_level_policy_terms(lp, old, ent, mask, adv, 0.2, (0.01, 0.03), live=live)
    want = two_level_policy_terms(lp[live], old[live], ent[live], mask[live], adv[live], 0.2, (0.01, 0.03))
    for k in ("policy_loss", "entropy_loss"):
        assert torch.allclose(_grad(got[k], w), _grad(want[k], w), rtol=1e-6, atol=1e-8), k
    assert torch.allclose(got["kl"], want["kl"], rtol=1e-6) and torch.allclose(got["entropy"], want["entropy"])
    off = two_level_policy_terms(lp, old, ent, mask, adv, 0.2, (0.01, 0.03))
    same = two_level_policy_terms(lp, old, ent, mask, adv, 0.2, (0.01, 0.03), live=None)
    assert all(torch.equal(off[k], same[k]) for k in off)
    assert not math.isnan(float(got["policy_loss"]))
