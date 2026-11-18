"""Phase 5 task M2: the replica as a training environment (nus/replica_train.py). Unit tests on marker files: fresh starts and the
spawn centres, the central-state layout, the reward formula and its zero-sum split, the first-reach flag, the APF block, no loop over
games. Parity: the partner's own critic states and rewards recorded by scripts/nus_record_fixtures.py --train-fields (skipped where the
fixture or the local files are absent: a skip is not a pass)."""
import ast
import json

import numpy as np
import pytest
import torch

from _nus_markers import BATCH, POS_TOL, ROOT
from _nus_phase5_method_fixture import SEEDS, GAMMA_SHAPING, REWARD_TOL, STATE_TOL, TRAIN_GAMES, TRAIN_TAG, marker_env
from svg_training.nus import replica_train as RT
from svg_training.nus.replica import ReplicaState


@pytest.fixture()
def env(tmp_path):
    return marker_env(tmp_path)


def test_fresh_starts_and_spawn_centres(env):
    a = env.reset(TRAIN_GAMES, torch.Generator().manual_seed(1))
    b = env.reset(TRAIN_GAMES, torch.Generator().manual_seed(2))
    c = env.reset(TRAIN_GAMES, torch.Generator().manual_seed(1))
    assert not torch.equal(a.game.pos, b.game.pos) and torch.equal(a.game.pos, c.game.pos)
    torch.testing.assert_close(a.strike_spawn, a.game.pos[:, env.guard_count:].mean(dim=1))
    assert torch.count_nonzero(a.guard_spawn) == 0
    fixed = env.reset(TRAIN_GAMES, random_start=False)
    assert torch.all(fixed.strike_spawn[:, 0] == env.rules.spawn_distance) and torch.all(fixed.strike_spawn[:, 1] == 0)


def test_central_state_layout(env):
    s = env.reset(TRAIN_GAMES, torch.Generator().manual_seed(0))
    s, _ = env.step(s, env.apf_actions(s, "guard"), env.apf_actions(s, "strike"), GAMMA_SHAPING)
    slots = torch.arange(TRAIN_GAMES) % env.slots
    x = env.central_state(s, slots)
    m, n = env.num_actors, TRAIN_GAMES
    assert x.shape == (n, (2 * 2 + 1) * m + 2 * 2 * 2 + env.slots) and env.state_dim == x.shape[1]
    cursor = 0

    def take(width):
        nonlocal cursor
        cursor += width
        return x[:, cursor - width: cursor]

    torch.testing.assert_close(take(2 * m), s.game.pos.reshape(n, -1))
    assert torch.count_nonzero(take(m)) == 0                            # done flags: every stored state is before the last step
    assert torch.all(take(1)[:, 0] == 1)                                 # step count
    assert torch.count_nonzero(take(2)) == 0                             # zone at the origin
    torch.testing.assert_close(take(2 * m), s.game.prev_pos.reshape(n, -1))
    assert torch.count_nonzero(take(2)) == 0                             # Guard spawn centre = zone
    torch.testing.assert_close(take(2), s.strike_spawn)
    torch.testing.assert_close(take(1)[:, 0], s.game.reached)
    hot = take(env.slots)
    assert torch.equal(hot.argmax(dim=1), slots) and torch.all(hot.sum(dim=1) == 1) and cursor == x.shape[1]


def test_reward_formula_and_zero_sum(env):
    method, g = env.method, env.guard_count
    s = env.reset(BATCH, torch.Generator().manual_seed(SEEDS[0]))
    nxt, out = env.step(s, torch.zeros(BATCH, g, 2), env.apf_actions(s, "strike"), GAMMA_SHAPING)
    before = torch.linalg.norm(s.game.pos[:, g:], dim=-1).sum(-1)
    after = torch.linalg.norm(nxt.game.pos[:, g:], dim=-1).sum(-1)
    inside = (torch.linalg.norm(nxt.game.pos[:, g:], dim=-1) <= env.rules.area_radius).sum(-1)
    expected = method.shaping_scale * (GAMMA_SHAPING * after - before) - method.inside_penalty * inside / env.strike_count
    expected = expected - method.first_reach_penalty * out.first_reach.float()
    torch.testing.assert_close(out.guard_reward, expected)
    assert torch.equal(out.inside_count, inside)


def test_first_reach_fires_once_and_clean_timeout_on_the_last_step(env):
    g, k = env.guard_count, env.strike_count
    s = env.reset(BATCH, torch.Generator().manual_seed(SEEDS[1]))
    inside = torch.zeros_like(s.game.pos)                         # every drone at the zone centre: the Strike team is inside at once
    state = RT.TrainState(ReplicaState(inside, inside.clone(), torch.zeros(BATCH), torch.zeros(BATCH, dtype=torch.long)),
                          s.guard_spawn, s.strike_spawn)
    zero_g, zero_s = torch.zeros(BATCH, g, 2), torch.zeros(BATCH, k, 2)
    firsts = []
    for _ in range(env.episode_steps):
        state, out = env.step(state, zero_g, zero_s, GAMMA_SHAPING)
        firsts.append(out.first_reach)
    firsts = torch.stack(firsts)
    assert torch.all(firsts.sum(dim=0) == 1) and torch.all(firsts[0]) and torch.all(out.time_limit) and torch.all(out.reached)
    # a game the Strike team never reached gets the clean time-out reward on its last step only
    far = s.game.pos.clone()
    far[:, g:] = far[:, g:] * (env.rules.spawn_distance * 2 / torch.linalg.norm(far[:, g:], dim=-1, keepdim=True))
    last = RT.TrainState(ReplicaState(far, far.clone(), torch.zeros(BATCH), torch.full((BATCH,), env.episode_steps - 1)),
                         s.guard_spawn, s.strike_spawn)
    _, out = env.step(last, zero_g, zero_s, GAMMA_SHAPING)
    shaping = env.method.shaping_scale * (GAMMA_SHAPING - 1) * torch.linalg.norm(far[:, g:], dim=-1).sum(-1)
    torch.testing.assert_close(out.guard_reward, shaping + env.method.clean_timeout_reward)


def test_apf_block_shapes(env):
    s = env.reset(BATCH, torch.Generator().manual_seed(SEEDS[2]))
    assert env.apf_actions(s, "guard").shape == (BATCH, env.guard_count, 2)
    assert env.apf_actions(s, "strike").shape == (BATCH, env.strike_count, 2)
    obs_g, obs_s = env.observe(s)
    assert obs_g.shape == (BATCH, env.guard_count, env.obs_dim) and obs_s.shape == (BATCH, env.strike_count, env.obs_dim)


def test_no_python_loop_in_the_environment():
    tree = ast.parse((ROOT / "source/svg_training/nus/replica_train.py").read_text())
    loops = [n for n in ast.walk(tree) if isinstance(n, (ast.For, ast.While, ast.comprehension))]
    assert not loops


# ---------------------------------------------------------------- parity with the partner's own critic state and reward
def _local():
    from svg_training.nus import deploy as deploy_mod, method_cfg, rules as rules_mod
    paths = (rules_mod.LOCAL_RULES, deploy_mod.LOCAL_DEPLOY, method_cfg.LOCAL_METHOD)
    npz = rules_mod.FIXTURE_DIR / f"{TRAIN_TAG}.npz"
    if not all(p.exists() for p in (*paths, npz)):
        pytest.skip("fixture or local files absent (scripts/nus_record_fixtures.py --train-fields, nus_make_local_*.py): not a pass")
    deploy = deploy_mod.load_deploy()
    rules = deploy_mod.apply_overrides(rules_mod.load_rules(), deploy)
    return RT.NusTrainEnv(rules, deploy, method_cfg.load_method()), np.load(npz), json.loads(npz.with_suffix(".json").read_text())


def test_parity_with_the_partners_critic_state_and_reward():
    env, d, cov = _local()
    assert cov["train_fields"] and cov["steps_with_flag_flip"] > 0 and cov["steps_with_push"] > 0
    e, t1, m = d["pos"].shape[:2 + 1]
    steps = t1 - 1
    g = env.guard_count

    def flat(a):
        return torch.from_numpy(np.ascontiguousarray(a)).reshape(e * steps, *a.shape[2:])

    spawn = torch.from_numpy(d["pos"][:, 0, g:].mean(axis=1)).repeat_interleave(steps, dim=0)
    state = RT.NusTrainEnv.from_positions(flat(d["pos"][:, :-1]), flat(d["prev_pos"][:, :-1]), flat(d["breach"][:, :-1]),
                                          flat(d["step"][:, :-1]).long(), spawn)
    slots = torch.from_numpy(d["slot"]).repeat_interleave(steps)
    central = env.central_state(state, slots)
    recorded = flat(d["central"])
    state_err = (central - recorded).abs().max().item()
    # the reward formula on the recorded positions before and after each step
    pos, nxt = flat(d["pos"][:, :-1]), flat(d["pos"][:, 1:])
    inside = env.replica.inside_zone(nxt[:, g:]).sum(dim=1)
    reached_after = flat(d["breach"][:, 1:]) > 0
    first = reached_after & ~(flat(d["breach"][:, :-1]) > 0)
    time_limit = flat(d["step"][:, 1:]).long() >= env.episode_steps
    reward = RT.guard_reward(pos, nxt, inside, time_limit, reached_after, first, guard_count=g, method=env.method,
                             shaping_gamma=env.method.guard_gamma)
    reward_err = (reward - flat(d["guard_reward"])).abs().max().item()
    # the environment's own step from each recorded state (positions within the Phase 2 tolerance)
    stepped, out = env.step(state, flat(d["actions"])[:, :g], flat(d["actions"])[:, g:], env.method.guard_gamma)
    step_err = (stepped.game.pos - nxt).abs().max().item()
    stepped_reward_err = (out.guard_reward - flat(d["guard_reward"])).abs().max().item()
    counts_equal = torch.equal(out.inside_count, flat(d["inside_count"]).long()) and torch.equal(out.first_reach, flat(d["first_reach"]))
    summary = {"episodes": e, "steps": steps, "central_state_max_abs_err": state_err, "reward_max_abs_err": reward_err,
               "step_position_max_abs_err": step_err, "reward_from_own_step_max_abs_err_info": stepped_reward_err,
               "inside_and_first_reach_equal": counts_equal}
    print(f"\n[M2 parity {TRAIN_TAG}] {json.dumps(summary)}")
    out_dir = ROOT / "runs" / "nus_port" / "phase5" / "method_port"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "m2_parity.json").write_text(json.dumps(summary, indent=2) + "\n")
    assert state_err <= STATE_TOL and reward_err <= REWARD_TOL and step_err <= POS_TOL and counts_equal
