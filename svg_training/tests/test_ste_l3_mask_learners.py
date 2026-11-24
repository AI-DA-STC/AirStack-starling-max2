"""STE phase L3, slice 3, step 4: the absent-drone mask wired into the learners behind ``[learner] mask_absent``
(design note ste_learning/drafts/L3_SLICE3_DESIGN.md §1 and its "Revision after the review").

* ``learner_spec`` accepts ``mask_absent`` for the velocity route and ``choice = "two_level"``, refuses it for slice
  1's flat modes (B2); default off.
* Off: today's learners bit for bit (both routes).
* On, velocity route: ``ste/masked_ippo.MaskedIPPO`` (built only when on; its own masked GAE; the pins). With every
  row live it equals stock skrl IPPO bit for bit; with absent rows, an update equals a hand-built masked update
  (gradient level), and nothing an absent row stores (action, old log-probability, value) reaches a weight or a
  scaler statistic.
* On, two-level route: ``TwoLevelIPPO`` with ``live``; the same invariance; all live = off bit for bit.
* The pre-pass bootstrap counts and the live share in the stats; time_limit_bootstrap with the mask is refused.
* A tiny CPU training run on each route with the mask on and a forced tag (absent slots occur).
CPU only."""
import pytest
import torch

from svg_training.core.observations import OBS_DIM, ObsView
from svg_training.opponents.scripted import make_strategy
from svg_training.ste import exploit, exploit_train, masking, skills

V = ObsView()
HOLD = 12
TWO = {"action": "skills", "choice": "two_level",
       "team_strategies": {"strike": ["strike_sacrifice", "strike_converge"],
                           "guard": ["guard_parked_ring", "guard_field"]},
       "drone_skills": {"strike": ["strike_straight", "strike_flank", "strike_high", "strike_low"],
                        "guard": ["guard_parked_centre", "guard_mark_edge", "guard_mirror"]},
       "entropy_scale": {"team": 0.01, "drone": 0.01}}


@pytest.fixture(scope="module")
def gates():
    return exploit.load_gates()


def tiny(gates, **over):
    return {**gates.trainer, "num_games": 6, "rollouts": 3, "learning_epochs": 1, "mini_batches": 1, **over}


def learner(gates, table, side="guard", n=6, seed=7, tag_off=False, **over):
    cfg = exploit.variant_cfg(gates, "base")
    if tag_off:                                  # no tag: no drone leaves, every row live
        cfg = cfg.replace(**{"tag.mode": "off"})
    game = exploit_train.TrainGame(cfg, n, 3, 3, device="cpu", seed=seed)
    opp = make_strategy(exploit.opponent_of(gates, "base", side), "strike" if side == "guard" else "guard", cfg, n,
                        "cpu", seed + 1)
    env = exploit_train.decision_env(game, HOLD, side, opp, skills.learner_spec(table), gates.players, seed)
    return exploit_train.Learner(tiny(gates, num_games=n, **over), env, "cpu", seed=11)


def force_tag(lrn, slot: int, games) -> None:
    """Take drone ``slot`` of the trained team out in ``games`` (a forced tag): the game's alive flag, then the
    observations the next decision starts from. The Guard team: its game goes on without the drone."""
    g = lrn.env.game
    off = 0 if lrn.env.team == "guard" else g.guards
    g.alive[games, off + slot] = False
    obs = g._obs()
    lrn.env._game_obs = obs
    lrn.env._obs = lrn.env._split(obs)
    lrn.obs = lrn.env._obs


def trained(gates, table, updates=2, tag_off=False):
    """A learner built and updated on its own (Learner seeds the global generator at construction, so two learners
    are compared one after the other, never interleaved)."""
    lrn = learner(gates, table, tag_off=tag_off)
    for _ in range(updates):
        st = lrn.update()
        if tag_off and "mask" in st:
            assert st["mask"]["live_share"] == 1.0, "a row was absent: the comparison is not all live"
    return lrn


def same_modules(a, b) -> bool:
    return all(torch.equal(a[ag][mod][k], b[ag][mod][k]) for ag in a for mod in ("policy", "value")
               for k in a[ag][mod] if torch.is_tensor(a[ag][mod][k]))


# ================================================================================================ the setting
def test_mask_absent_is_accepted_on_velocity_and_two_level_and_refused_on_the_flat_modes():
    assert skills.learner_spec(None).mask_absent is False
    assert skills.learner_spec({"action": "velocity", "mask_absent": True}).mask_absent is True
    assert skills.learner_spec({**TWO, "mask_absent": True}).mask_absent is True
    assert skills.learner_spec({"action": "skills", "choice": "team"}) == skills.LearnerSpec("skills", "team")
    for choice in ("team", "drone"):
        with pytest.raises(ValueError, match="mask_absent"):
            skills.learner_spec({"action": "skills", "choice": choice, "mask_absent": True})
    with pytest.raises(ValueError, match="mask_absent"):
        skills.learner_spec({"action": "velocity", "mask_absent": 1})


# ================================================================================================ off = bit for bit
@pytest.mark.parametrize("table,off", [(None, {"action": "velocity", "mask_absent": False}),
                                       (TWO, {**TWO, "mask_absent": False})])
def test_mask_off_trains_as_before_bit_for_bit(gates, table, off):
    a, b = trained(gates, table), trained(gates, off)
    assert same_modules(a.modules(), b.modules())
    assert type(a.agent) is type(b.agent)
    assert "mask" not in a.update() and "mask" not in b.update()


# ================================================================================================ velocity, on
def test_velocity_with_the_mask_and_every_row_live_equals_stock_ippo_bit_for_bit(gates):
    from svg_training.ste.masked_ippo import MaskedIPPO
    a = trained(gates, None, tag_off=True)
    b = trained(gates, {"action": "velocity", "mask_absent": True}, tag_off=True)
    assert isinstance(b.agent, MaskedIPPO) and not isinstance(a.agent, MaskedIPPO)
    assert same_modules(a.modules(), b.modules())
    for ag in a.names:
        for k in ("running_mean", "running_variance"):
            assert torch.equal(getattr(a.agent._observation_preprocessor[ag], k),
                               getattr(b.agent._observation_preprocessor[ag], k))


def _fill_rollout(lrn):
    """One rollout of decisions recorded in memory (no update), with slot 2 out in half the games from the start."""
    force_tag(lrn, 2, torch.tensor([True, False] * (lrn.env.game.num_games // 2)))
    agent, env = lrn.agent, lrn.env
    agent.enable_training_mode(True)
    for t in range(int(lrn.settings["rollouts"])):
        with torch.no_grad():
            actions, _ = agent.act(lrn.obs, lrn.states, timestep=t, timesteps=10)
            nxt, rew, term, trunc, info = env.step(actions)
            agent.record_transition(observations=lrn.obs, states=lrn.states, actions=actions, rewards=rew,
                                    next_observations=nxt, next_states=env.state(), terminated=term, truncated=trunc,
                                    infos=info, timestep=t, timesteps=10)
        lrn.obs, lrn.states = nxt, env.state()


def _update_all(lrn, seed=5):
    agent = lrn.agent
    torch.manual_seed(seed)
    agent.enable_models_training_mode(True)
    agent._rollout = int(lrn.settings["rollouts"]) - 1
    agent.post_interaction(timestep=int(lrn.settings["rollouts"]) - 1, timesteps=10)


@pytest.mark.parametrize("table", [{"action": "velocity", "mask_absent": True}, {**TWO, "mask_absent": True}])
def test_nothing_an_absent_row_stores_reaches_a_weight_or_a_scaler(gates, table):
    base = learner(gates, table)
    _fill_rollout(base)
    other = learner(gates, table)                       # the same learner and rollout (built after: same seeds)
    _fill_rollout(other)
    seen = 0
    for ag in base.names:
        mem = other.agent.memories[ag]
        obs = mem.get_tensor_by_name("observations")
        absent = obs[..., V.alive] <= 0.5
        seen += int(absent.sum())
        act = mem.get_tensor_by_name("actions")
        act[absent] = act[absent].flip(-1) if act.shape[-1] > 1 else (act[absent] + 1) % 3
        lp = mem.get_tensor_by_name("log_prob")
        lp[absent] = lp[absent] - 4.0
        val = mem.get_tensor_by_name("values")
        val[absent] = 77.0
        if "head_log_prob" in mem.get_tensor_names():
            hlp = mem.get_tensor_by_name("head_log_prob")
            hlp[absent] = hlp[absent] - 4.0
    assert seen > 0, "no absent row: the test has no power"
    _update_all(base)
    _update_all(other)
    assert same_modules(base.modules(), other.modules())
    for ag in base.names:
        for sc in ("_observation_preprocessor", "_value_preprocessor"):
            for k in ("running_mean", "running_variance", "current_count"):
                assert torch.equal(getattr(getattr(base.agent, sc)[ag], k), getattr(getattr(other.agent, sc)[ag], k))


def test_a_velocity_update_with_absent_rows_equals_a_hand_built_masked_update(gates):
    """One epoch, one minibatch: the masked update rebuilt by hand from the library pieces (step 3, each checked
    against hand references there) and plain torch (Adam, gradient clip): the same weights."""
    lrn = learner(gates, {"action": "velocity", "mask_absent": True})
    _fill_rollout(lrn)
    _update_all(lrn)
    twin = learner(gates, {"action": "velocity", "mask_absent": True})        # the same learner and rollout
    _fill_rollout(twin)
    hand = twin.agent
    s = lrn.settings
    g, lam = float(s["discount_factor"]), float(s["gae_lambda"])
    last = masking.last_values_prepass(hand)
    alive_next, own, alive = {}, {}, {}
    for ag in hand.possible_agents:
        mem = hand.memories[ag]
        alive[ag] = mem.get_tensor_by_name("observations")[..., V.alive:V.alive + 1] > 0.5
        alive_next[ag] = hand._current_next_observations[ag][:, V.alive] > 0.5
        own[ag] = masking.own_last_live(mem.get_tensor_by_name("values"), alive[ag])
    boot = masking.team_bootstrap(last, alive_next, own, g)
    torch.manual_seed(5)
    for ag in hand.possible_agents:
        mem, pol, val = hand.memories[ag], hand.policies[ag], hand.values[ag]
        values = mem.get_tensor_by_name("values")
        out = masking.masked_gae(mem.get_tensor_by_name("rewards"), mem.get_tensor_by_name("terminated"), values,
                                 last[ag], alive[ag], alive_next[ag][:, None], boot[ag][0], g, lam)
        vp, op = hand._value_preprocessor[ag], hand._observation_preprocessor[ag]
        masking.masked_scaler_update(vp, values, alive[ag][..., 0])
        v_s = vp(values)
        masking.masked_scaler_update(vp, out["returns"], alive[ag][..., 0])
        r_s = vp(out["returns"])
        idx = torch.randperm(len(mem))                                       # the memory's own shuffle
        flat = lambda x: x.reshape(-1, x.shape[-1])[idx]                              # noqa: E731
        obs = flat(mem.get_tensor_by_name("observations"))
        live = flat(alive[ag].float())[:, 0] > 0
        masking.masked_scaler_update(op, obs, live)
        inputs = {"observations": op(obs), "states": flat(mem.get_tensor_by_name("states"))}
        pol.train(), val.train()
        _, o = pol.act({**inputs, "taken_actions": flat(mem.get_tensor_by_name("actions"))}, role="policy")
        terms = masking.masked_policy_terms(o["log_prob"], flat(mem.get_tensor_by_name("log_prob")),
                                            pol.get_entropy(role="policy"), flat(out["advantages"]), live,
                                            float(s["ratio_clip"]), float(s["entropy_loss_scale"]))
        ent = terms["entropy_loss"] if float(s["entropy_loss_scale"]) else 0
        pred, _ = val.act(inputs, role="value")
        vl = masking.masked_value_loss(flat(r_s), pred, flat(v_s), live, float(s["value_clip"]),
                                       float(s["value_loss_scale"]))
        opt = hand.optimizers[ag]
        opt.zero_grad()
        (terms["policy_loss"] + ent + vl).backward()
        torch.nn.utils.clip_grad_norm_(list(pol.parameters()) + list(val.parameters()), float(s["grad_norm_clip"]))
        opt.step()
    for ag in hand.possible_agents:
        for p, q in zip(list(hand.policies[ag].parameters()) + list(hand.values[ag].parameters()),
                        list(lrn.agent.policies[ag].parameters()) + list(lrn.agent.values[ag].parameters())):
            assert torch.allclose(p, q, rtol=1e-5, atol=1e-7)


def test_two_level_with_the_mask_and_every_row_live_equals_off_bit_for_bit(gates):
    a, b = trained(gates, TWO, tag_off=True), trained(gates, {**TWO, "mask_absent": True}, tag_off=True)
    assert same_modules(a.modules(), b.modules())


# ================================================================================================ stats, refusals
def test_the_mask_stats_carry_the_live_share_and_the_bootstrap_counts(gates):
    lrn = learner(gates, {"action": "velocity", "mask_absent": True})
    force_tag(lrn, 2, torch.tensor([True, False] * 3))
    st = lrn.update()["mask"]
    assert 0 < st["live_share"] < 1
    assert set(st["bootstrap"]) == {"mates", "own", "none"} and sum(st["bootstrap"].values()) > 0
    assert st["time_limit_bootstrap"] is False


def test_the_mask_refuses_the_time_limit_bootstrap(gates):
    from svg_training.ste.masked_ippo import MaskedIPPO
    with pytest.raises(ValueError, match="time_limit_bootstrap"):
        MaskedIPPO.refuse_time_limit({"guard_0": True})


# ================================================================================================ tiny runs
@pytest.mark.parametrize("table", [{"action": "velocity", "mask_absent": True}, {**TWO, "mask_absent": True}])
def test_a_tiny_training_run_with_the_mask_and_a_forced_tag(gates, table):
    lrn = learner(gates, table, n=8)
    shares = []
    for u in range(3):
        force_tag(lrn, u % 3, torch.tensor([True, True, False, False] * 2))
        st = lrn.update()
        assert all(torch.isfinite(torch.tensor(v)) for v in st["losses"].values())
        shares.append(st["mask"]["live_share"])
    assert min(shares) < 1.0


def test_a_driver_run_with_the_mask_logs_it_and_records_the_setting(tmp_path, monkeypatch):
    import json
    import sys
    from _ste_tools import SCRIPTS
    from svg_training.ste import shared
    sys.path.insert(0, str(SCRIPTS))
    import ste_exploit_l012 as driver
    monkeypatch.setenv(shared.SHARED_ENV, str(tmp_path / "shared"))
    monkeypatch.setenv(shared.LEGACY_LOGS_ENV, "")
    g = tmp_path / "gates.toml"
    g.write_text((exploit.ROOT / "configs" / "ste_l012" / "smoke_gates.toml").read_text()
                 + '\n[learner]\naction = "velocity"\nmask_absent = true\n')
    pj = tmp_path / "pilot.json"
    pj.write_text(json.dumps({"strike_recipe": {"recipe": exploit.RECIPE_BARE, "side_overrides_strike": {}}}))
    r = tmp_path / "run"
    assert driver.main(["--gates", str(g), "--variant", "base", "--side", "guard", "--run-dir", str(r), "--cap-h", "1",
                        "--no-videos", "--pilot-json", str(pj)]) == 0
    log = [json.loads(x) for x in (r / "train_log.jsonl").read_text().splitlines()]
    assert log and all("mask" in x and 0 < x["mask"]["live_share"] <= 1 for x in log)
    res = json.loads((r / "results.json").read_text())
    assert res["mask"] == {"mask_absent": True, "time_limit_bootstrap": False}
