"""Route 3, stage LS1, tasks LS1-M2-T2 and T3: the collection of the distillation (``ste/distil.py``: ``CodeSchedule``,
``collect``, ``Rows``, ``keep``, ``round_seed``, ``mix_combos``), then the fit, the relabelling rounds and the report
(``initial_net``, ``fit``, ``round_rows``, ``refit``, ``dagger``, ``report``, ``summarise``); plan
ste_learning/drafts/LS1_TASK_PLAN.md, section 3.

* Labels are every script's command on the state (the scripts are row-wise, so a row alone in a zero team tensor gives
  the same command); rows come from live drones of the side only.
* The code schedule: a uniform game flies one code on every drone all game, a mix game one combination of
  ``cells.mixed_pool`` all game, a random game changes its two-level choice only on hold boundaries counted from each
  game's own start (per-game tick: ``SvgGame.step`` restarts ended games itself).
* Same seed, same rows; another round, other rows; round seeds come from a mixing function and meet no other seed of
  the committed gate file (design check of M2: ``seed + round`` would hit ``[report] seed``).
* The near-switch flag follows the label jumps (same game, live both ticks, held ``switch_window_ticks``), never on a
  game's first tick; the opponent pool is redrawn after each game.
* ``keep``: exactly min(keep_rows, R) distinct rows, the absent quota met (at most the absent rows there are), uniform
  without weights, weighted by the keys log(1 - u) / w in float64, zero-weight rows filled at random when needed.

* The fit (T3) lowers every skill's error below half that of the same net unfitted; it is seeded, asks the stop
  before each epoch and reports each epoch's loss. The net starts from the [fit] seed without touching the global
  generator. Round 0 needs no net, later rounds do; each round refits a fresh net on every round's kept rows.
* The report (T3) has exactly the fit report's final keys, None for an empty stratum, the zero-command skill (Guard
  ``guard_parked_centre``), the active channels of the Strike skills, and numbers that match a direct recomputation
  with plain loops (per skill, by n_live, by hold bin, tick-to-tick change); it flies the net on its own seed.

Sizes from the plan: 16 games, 24 to 120 ticks, the skills gate file's ``[players]``/``[learner]``; the data-mix
values (shares, hold, switch jump and window) are read from the committed distil_gates.toml, never typed. CPU only."""
import dataclasses
import itertools
import json
import math

import pytest
import torch

from svg_training.core.observations import OBS_DIM
from svg_training.opponents.scripted import make_strategy
from svg_training.ste import cells, distil, exploit, pool, skills, sweep

import _ste_ls1 as h

ROOT = exploit.ROOT
DISTIL_GATES = ROOT / "configs" / "ste_ls1" / "distil_gates.toml"
GAMES = 16
LONG_TICKS = 120                     # the Strike fixture: games end and restart inside it (first ends near tick 30)
SHORT_TICKS = 24
SEED, POOL_SEED = 7, 8               # test seeds (not the gate file's)
ALIVE = skills._V.alive


# ================================================================================================ fixtures, helpers
@pytest.fixture(scope="module")
def dg():
    return distil.load_distil_gates(DISTIL_GATES)


@pytest.fixture(scope="module")
def cfg(dg):
    return exploit.variant_cfg(dg.skills_gates, distil.VARIANT)


def _collect(dg, cfg, side, ticks, *, script_share=1.0, net=None, round_index=0, seed=SEED, pool_seed=POOL_SEED,
             games=GAMES, should_stop=None):
    d = dg.data
    return distil.collect(cfg, dg.specs[side], dg.skills_gates.players, side, net, script_share, games, ticks,
                          d["hold"], seed, pool_seed, "cpu", should_stop, size=dg.skills_gates.run["size"],
                          shares=(d["uniform_share"], d["mix_share"], d["random_share"]),
                          switch_jump=d["switch_jump"], switch_window_ticks=d["switch_window_ticks"],
                          round_index=round_index)


@pytest.fixture(scope="module")
def strike_rows(dg, cfg):
    return _collect(dg, cfg, "strike", LONG_TICKS)


@pytest.fixture(scope="module")
def guard_rows(dg, cfg):
    return _collect(dg, cfg, "guard", SHORT_TICKS)


def isolated(obs_rows: torch.Tensor, slot: torch.Tensor, m: int) -> torch.Tensor:
    """obs_rows [R, OBS_DIM], slot [R] -> [R, M, OBS_DIM]: each row alone at its slot of a zero team tensor."""
    r = obs_rows.shape[0]
    team = obs_rows.new_zeros(r, m, OBS_DIM)
    team[torch.arange(r), slot] = obs_rows
    return team


def jumps(labels_t: torch.Tensor, labels_prev: torch.Tensor, same_game: torch.Tensor, jump: float) -> torch.Tensor:
    """labels [R, K, 4] at a tick and the tick before, same_game [R] bool (same game, live both ticks) -> [R] bool: any
    code's max-channel |change| above ``jump``."""
    return same_game & ((labels_t - labels_prev).abs().amax(dim=(-1, -2)) > jump)


def _sequences(rows):
    """Row indices grouped per (game slot, episode, drone slot), in tick order: {key: [index, ...]}."""
    order = sorted(range(rows.obs.shape[0]), key=lambda i: (int(rows.game[i]), int(rows.episode[i]),
                                                             int(rows.slot[i]), int(rows.tick[i])))
    out = {}
    for i in order:
        out.setdefault((int(rows.game[i]), int(rows.episode[i]), int(rows.slot[i])), []).append(i)
    return out


def _synthetic_rows(n: int, absent: torch.Tensor | None = None, near: torch.Tensor | None = None,
                    team_size: int = 3) -> distil.Rows:
    """``n`` synthetic rows: a mate absent where ``absent`` (n_live = team_size - 1), near_switch where ``near``."""
    absent = torch.zeros(n, dtype=torch.bool) if absent is None else absent
    near = torch.zeros(n, dtype=torch.bool) if near is None else near
    zl = torch.zeros(n, dtype=torch.long)
    return distil.Rows(obs=torch.zeros(n, OBS_DIM), slot=zl.clone(), label=torch.zeros(n, 1, 4), flown=zl.clone(),
                       n_live=torch.where(absent, team_size - 1, team_size).to(torch.int8),
                       held=torch.zeros(n, dtype=torch.int16), mode=torch.zeros(n, dtype=torch.int8),
                       net_flown=torch.zeros(n, dtype=torch.bool), near_switch=near,
                       round=torch.zeros(n, dtype=torch.int8), game=torch.arange(n, dtype=torch.int32),
                       episode=torch.zeros(n, dtype=torch.int32), tick=torch.zeros(n, dtype=torch.int16),
                       opponent=torch.zeros(n, dtype=torch.int8), team_size=team_size)


def _gen(seed: int) -> torch.Generator:
    g = torch.Generator()
    g.manual_seed(seed)
    return g


# ================================================================================================ labels and rows
@pytest.mark.parametrize("side", ["strike", "guard"])
def test_labels_are_every_scripts_command_on_that_state(side, dg, cfg, strike_rows, guard_rows):
    rows = strike_rows if side == "strike" else guard_rows
    spec = dg.specs[side]
    r = rows.obs.shape[0]
    assert rows.label.shape == (r, len(spec.players), 4) and rows.label.dtype == torch.float32
    team = isolated(rows.obs, rows.slot, spec.drones)
    for k, name in enumerate(spec.players):
        want = make_strategy(name, side, cfg, r, "cpu", 0).act(team)[torch.arange(r), rows.slot]
        assert torch.equal(rows.label[:, k], want), name


@pytest.mark.parametrize("side", ["strike", "guard"])
def test_only_live_drones_give_rows(side, dg, strike_rows, guard_rows):
    rows = strike_rows if side == "strike" else guard_rows
    m = dg.specs[side].drones
    assert rows.obs.shape[0] > 0 and rows.obs.dtype == torch.float32 and rows.obs.shape[1] == OBS_DIM
    assert bool((rows.obs[:, ALIVE] > skills.ALIVE_FLAG_MIN).all())
    assert bool(((rows.slot >= 0) & (rows.slot < m)).all()) and rows.slot.dtype == torch.long
    assert rows.team_size == m
    # n_live is the count of the side's live drones at that tick of that game: the rows of that (game, episode, tick)
    key = (rows.game.long() * (1 << 20) + rows.episode.long() * (1 << 10) + rows.tick.long())
    _, inverse, counts = torch.unique(key, return_inverse=True, return_counts=True)
    assert torch.equal(rows.n_live.long(), counts[inverse])
    assert bool((rows.round == 0).all())
    for name, dtype in (("n_live", torch.int8), ("held", torch.int16), ("mode", torch.int8), ("net_flown", torch.bool),
                        ("near_switch", torch.bool), ("round", torch.int8), ("flown", torch.long)):
        assert getattr(rows, name).dtype == dtype, name


def test_uniform_and_mix_games_fly_one_code_per_drone_all_game(dg, strike_rows):
    rows, spec = strike_rows, dg.specs["strike"]
    pool_codes = [tuple(spec.players.index(s) for s in c) for c in cells.mixed_pool(spec)]
    seen = set()
    per_game = {}
    for i in range(rows.obs.shape[0]):
        key = (int(rows.game[i]), int(rows.episode[i]))
        per_game.setdefault(key, []).append(i)
    for key, idx in per_game.items():
        idx = torch.tensor(idx)
        mode = rows.mode[idx]
        assert bool((mode == mode[0]).all()), f"game {key}: the mode changed inside a game"
        mode = int(mode[0])
        seen.add(mode)
        if mode == distil.UNIFORM:
            assert rows.flown[idx].unique().numel() == 1, f"game {key}: a uniform game flew more than one code"
        elif mode == distil.MIX:
            by_slot = {}
            for i in idx.tolist():
                by_slot.setdefault(int(rows.slot[i]), set()).add(int(rows.flown[i]))
            assert all(len(v) == 1 for v in by_slot.values()), f"game {key}: a mix game changed a drone's code"
            flies = {s: next(iter(v)) for s, v in by_slot.items()}
            assert any(all(c[s] == z for s, z in flies.items()) for c in pool_codes), f"game {key}: not a combination"
    assert {distil.UNIFORM, distil.MIX, distil.RANDOM} <= seen, "every mode must be played (the test is vacuous)"


def test_mix_combos_are_the_free_combinations(dg):
    for side in ("guard", "strike"):
        spec = dg.specs[side]
        combos = distil.mix_combos(spec, "cpu")
        want = [[spec.players.index(s) for s in c] for c in cells.mixed_pool(spec)]
        assert combos.dtype == torch.long and combos.tolist() == want


def test_random_games_change_choice_only_on_hold_boundaries_from_each_games_start(dg, strike_rows):
    rows, spec = strike_rows, dg.specs["strike"]
    hold = dg.data["hold"]
    team_codes = {spec.players.index(s) for s in spec.team_strategies}
    changes_inside = 0
    for key, idx in _sequences(rows).items():
        mode = int(rows.mode[idx[0]])
        for a, b in zip(idx, idx[1:]):
            assert int(rows.tick[b]) == int(rows.tick[a]) + 1, f"{key}: a live drone's rows skip a tick"
            changed = int(rows.flown[b]) != int(rows.flown[a])
            if changed:
                assert mode == distil.RANDOM, f"{key}: a {distil.MODES[mode]} game changed code"
                assert int(rows.tick[b]) % hold == 0, f"{key}: code changed at tick {int(rows.tick[b])}"
                changes_inside += 1
            assert int(rows.held[b]) == (0 if changed else int(rows.held[a]) + 1), f"{key}: held"
        first = idx[0]
        if int(rows.tick[first]) == 0:
            assert int(rows.held[first]) == 0
        if mode != distil.RANDOM:
            assert all(int(rows.held[i]) == int(rows.tick[i]) for i in idx), f"{key}: held counts from the start"
        else:
            assert all((int(rows.tick[i]) - int(rows.held[i])) % hold == 0 for i in idx), f"{key}: phase"
    assert changes_inside > 0, "no random game changed its choice (the test is vacuous)"
    # the two-level resolution: a team strategy flies on every live drone of the game at once
    random = rows.mode == distil.RANDOM
    for g, e, t in {(int(rows.game[i]), int(rows.episode[i]), int(rows.tick[i])) for i in random.nonzero()[:, 0]}:
        sel = (rows.game == g) & (rows.episode == e) & (rows.tick == t)
        codes = set(rows.flown[sel].tolist())
        if codes & team_codes:
            assert len(codes) == 1, f"game {g} tick {t}: a team strategy is not flown by the whole team {codes}"


def test_same_seed_same_rows(dg, cfg, guard_rows):
    again = _collect(dg, cfg, "guard", SHORT_TICKS)
    for name in distil.ROW_FIELDS:
        assert torch.equal(getattr(guard_rows, name), getattr(again, name)), name
    other = _collect(dg, cfg, "guard", SHORT_TICKS, round_index=1)
    assert bool((other.round == 1).all())
    n = min(other.obs.shape[0], guard_rows.obs.shape[0])
    assert not torch.equal(other.obs[:n], guard_rows.obs[:n]), "another round must play other starts"


def test_net_none_needs_script_share_1(dg, cfg):
    with pytest.raises(ValueError, match="script_share"):
        _collect(dg, cfg, "guard", 2, script_share=0.5, net=None)


def test_net_flown_games_fly_the_net_on_the_same_schedule(dg, cfg, guard_rows):
    """A stand-in net that equals the scripts (cells.ScriptOracle, exact) flies every game (script share 0): the rows
    are the scripts' rows, only net_flown differs; so a net-flown game flies ``one_code`` on the schedule's codes."""
    spec = dg.specs["guard"]
    oracle = cells.ScriptOracle(cfg, "guard", list(spec.players), spec.drones)
    flown = _collect(dg, cfg, "guard", SHORT_TICKS, script_share=0.0, net=oracle)
    assert bool(flown.net_flown.all()) and not bool(guard_rows.net_flown.any())
    for name in distil.ROW_FIELDS:
        if name != "net_flown":
            assert torch.equal(getattr(flown, name), getattr(guard_rows, name)), name
    wrong = cells.ScriptOracle(cfg, "strike", list(dg.specs["strike"].players), spec.drones)
    with pytest.raises(ValueError, match="strike"):
        _collect(dg, cfg, "guard", 2, script_share=0.0, net=wrong)


def test_should_stop_stops_before_a_tick(dg, cfg):
    with pytest.raises(sweep.SweepStopped):
        _collect(dg, cfg, "guard", 2, should_stop=lambda: True)


# ================================================================================================ switch flag, opponent
def test_near_switch_flag_follows_label_jumps(dg, strike_rows):
    rows = strike_rows
    jump, window = dg.data["switch_jump"], dg.data["switch_window_ticks"]
    want = torch.zeros(rows.obs.shape[0], dtype=torch.bool)
    for idx in _sequences(rows).values():
        idx_t = torch.tensor(idx)
        prev = torch.cat((idx_t[:1], idx_t[:-1]))
        same = torch.ones(len(idx), dtype=torch.bool)
        same[0] = False                                       # a game's first row of this drone has no tick before
        same &= rows.tick[idx_t].long() == rows.tick[prev].long() + 1
        j = jumps(rows.label[idx_t], rows.label[prev], same, jump)
        countdown = 0
        for pos, i in enumerate(idx):
            countdown = window if bool(j[pos]) else max(countdown - 1, 0)
            want[i] = countdown > 0
    assert torch.equal(rows.near_switch, want)
    assert bool(want.any()), "no label jump in the data (the test is vacuous)"
    assert not bool(rows.near_switch[rows.tick == 0].any()), "a game's first tick is never near a switch"


def test_the_opponent_is_redrawn_after_each_game(dg, strike_rows):
    rows = strike_rows
    names = pool.pool_members(dg.skills_gates.players, "guard")
    seed = distil.round_seed(POOL_SEED, 0, "pool")
    want = pool.pool_draw(seed, rows.game.long(), rows.episode.long(), len(names))
    assert torch.equal(rows.opponent.long(), want)
    later = rows.episode > 0
    assert bool(later.any()), "no game ended (the test is vacuous)"
    # a later game of a slot starts at tick 0: the restart was the game's own (SvgGame.step), the counter followed it
    firsts = {(int(rows.game[i]), int(rows.episode[i])): int(rows.tick[i]) for i in reversed(range(len(rows.tick)))}
    assert all(t == 0 for (g, e), t in firsts.items() if e > 0)
    changed = {g for g in rows.game[later].tolist()
               if len(set(rows.opponent[rows.game == g].tolist())) > 1}
    assert changed, "no redraw changed an opponent (the test is vacuous)"


# ================================================================================================ seeds
def test_round_seeds_are_new_and_the_report_starts_differ(dg, cfg):
    data, script_share = dg.data, dg.dagger["script_share"]
    others = {dg.fit["seed"], dg.report["seed"], dg.clips["seed"], data["pool_seed"], data["seed"]}
    derived = [distil.round_seed(data["seed"], r, p) for r in range(len(script_share)) for p in distil.SEED_PURPOSES]
    derived += [distil.round_seed(data["pool_seed"], r, p) for r in range(len(script_share))
                for p in distil.SEED_PURPOSES]
    assert len(set(derived)) == len(derived), "two rounds or purposes share a seed"
    assert not set(derived) & others, "a round seed equals another seed of the gate file"
    assert all(0 <= s < (1 << 63) for s in derived)
    # the report (task LS1-M2-T3) collects with seed = [report] seed, round 0: its starts are none of the rounds'
    report = _collect(dg, cfg, "guard", 1, seed=dg.report["seed"], pool_seed=data["pool_seed"])
    for r in range(len(script_share)):
        rows = _collect(dg, cfg, "guard", 1, seed=data["seed"], pool_seed=data["pool_seed"], round_index=r)
        assert rows.obs.shape == report.obs.shape and not torch.equal(rows.obs, report.obs), r


# ================================================================================================ keep
def test_keep_is_exact_meets_the_absent_quota_and_is_uniform_without_weights():
    n, k = 1000, 100
    # the quota: max(absent_min_share, natural share) x keep_rows, +-1 row
    for n_absent, min_share in ((300, 0.2), (100, 0.2), (50, 0.0)):
        absent = torch.zeros(n, dtype=torch.bool)
        absent[torch.randperm(n, generator=_gen(3))[:n_absent]] = True
        rows = _synthetic_rows(n, absent)
        err = torch.rand(n, generator=_gen(4)) + 0.01
        idx = distil.keep(rows, err, k, min_share, 1.0, _gen(5))
        assert idx.dtype == torch.long and idx.numel() == k and idx.unique().numel() == k
        want = max(min_share, n_absent / n) * k
        assert abs(int(absent[idx].sum()) - want) <= 1, (n_absent, min_share)
    # uniform without weights: R = 1,000, no absent mate, no near_switch, err None, 400 draws
    rows = _synthetic_rows(n)
    counts = torch.zeros(n)
    for s in range(400):
        idx = distil.keep(rows, None, k, 0.0, 1.0, _gen(s))
        assert idx.numel() == k and idx.unique().numel() == k
        counts[idx] += 1
    share = counts / 400
    assert bool(((share - 0.1).abs() <= 0.075).all()), (float(share.min()), float(share.max()))


def test_keep_takes_what_there_is_when_rows_are_few():
    """The smoke rule (distil.SMOKE_RULE): k = min(keep_rows, R); the absent quota is at most the absent rows."""
    rows = _synthetic_rows(50)
    idx = distil.keep(rows, None, 100, 0.2, 1.0, _gen(0))
    assert torch.equal(idx, torch.arange(50))
    absent = torch.zeros(50, dtype=torch.bool)
    absent[:5] = True
    idx = distil.keep(_synthetic_rows(50, absent), None, 40, 0.5, 1.0, _gen(1))
    assert idx.numel() == 40 and idx.unique().numel() == 40 and int(absent[idx].sum()) == 5
    # mostly absent rows: the quota is the natural share (rounded up), the other rows fill the rest, still exact
    absent = torch.ones(50, dtype=torch.bool)
    absent[:3] = False
    idx = distil.keep(_synthetic_rows(50, absent), None, 45, 0.2, 1.0, _gen(2))
    assert idx.numel() == 45 and idx.unique().numel() == 45
    assert int(absent[idx].sum()) == -(-47 * 45 // 50) and int((~absent[idx]).sum()) <= 3
    # every row kept: all of both strata
    idx = distil.keep(_synthetic_rows(50, absent), None, 50, 0.2, 1.0, _gen(3))
    assert torch.equal(idx, torch.arange(50))


def test_keep_weights_switch_floor_and_zero_weights():
    n, k = 1000, 100
    # near-switch rows raised to the floor are kept more often
    near = torch.zeros(n, dtype=torch.bool)
    near[:100] = True
    rows = _synthetic_rows(n, near=near)
    hits = sum(int(near[distil.keep(rows, None, k, 0.0, 8.0, _gen(s))].sum()) for s in range(20))
    assert hits / 20 > 2 * (k * 100 / n)
    # heavier rows are kept more often
    err = torch.ones(n)
    err[:100] = 10.0
    rows = _synthetic_rows(n)
    hits = sum(int((distil.keep(rows, err, k, 0.0, 1.0, _gen(s)) < 100).sum()) for s in range(20))
    assert hits / 20 > 2 * (k * 100 / n)
    # zero-weight rows: never kept while enough positive-weight rows exist; else filled at random, not by index
    err = torch.zeros(n)
    err[500:] = 1.0
    assert bool((distil.keep(rows, err, k, 0.0, 1.0, _gen(1)) >= 500).all())
    err = torch.zeros(n)
    err[:10] = 1.0
    picks = [distil.keep(rows, err, k, 0.0, 1.0, _gen(s)) for s in range(5)]
    for idx in picks:
        assert idx.numel() == k and idx.unique().numel() == k and bool((idx[:10] == torch.arange(10)).all())
    assert len({tuple(p.tolist()) for p in picks}) > 1, "the zero-weight fill follows the index order"
    assert not all(bool((p[10:] == torch.arange(10, k)).all()) for p in picks)
    # a perfect stand-in (every error 0): uniform, still exact
    idx = distil.keep(rows, torch.zeros(n), k, 0.0, 1.0, _gen(2))
    assert idx.numel() == k and idx.unique().numel() == k


def test_keep_refuses_bad_errors():
    rows = _synthetic_rows(10)
    for bad in (torch.full((10,), -1.0), torch.full((10,), float("nan")), torch.ones(9)):
        with pytest.raises(ValueError, match="err"):
            distil.keep(rows, bad, 5, 0.0, 1.0, _gen(0))


# ================================================================================================ the schedule alone
def test_the_schedule_ticks_per_game_and_restarts_with_the_game(dg, cfg):
    """Driven by hand: a game restarted by ``new_games`` counts its ticks from 0 again, the others go on."""
    spec = dg.specs["strike"]
    _, obs = h.team_obs(dg.skills_gates, "strike", n=8, ticks=4)
    disp = skills.TwoLevelDispatch("strike", list(spec.players), list(spec.team_strategies), list(spec.drone_skills),
                                   cfg, 8, "cpu", 0)
    sched = distil.CodeSchedule(spec, disp, (0.0, 0.0, 1.0), distil.mix_combos(spec, "cpu"), dg.data["hold"], 1.0,
                                "cpu", 3)
    sched.new_games(torch.ones(8, dtype=torch.bool))
    for _ in range(5):
        sched.flown(obs)
    assert torch.equal(sched.tick, torch.full((8,), 5))
    mask = torch.zeros(8, dtype=torch.bool)
    mask[2] = True
    sched.new_games(mask)
    assert sched.tick.tolist() == [5, 5, 0, 5, 5, 5, 5, 5]
    assert bool((sched.mode == distil.RANDOM).all()) and not bool(sched.net_flown.any())
    with pytest.raises(ValueError, match="hold"):
        distil.CodeSchedule(spec, disp, (1.0, 0.0, 0.0), distil.mix_combos(spec, "cpu"), 0, 1.0, "cpu", 3)
    with pytest.raises(ValueError, match="shares"):
        distil.CodeSchedule(spec, disp, (0.5, 0.0, 0.0), distil.mix_combos(spec, "cpu"), 1, 1.0, "cpu", 3)
    assert list(itertools.islice(distil.MODES, 3)) == ["uniform", "mix", "random"]


# ================================================================================================ T3: the fit
# Task LS1-M2-T3 (the fit, the relabelling rounds, the report). The plan's fit test: Guard rows of one round-0
# collection on 16 games x 120 ticks, seed 7; hidden [64, 64]; fit seed 11; CPU; every skill's RMSE below 0.5 x the
# unfitted net's. The plan's epochs 20, lr 1e-3, batch 512 do not reach 0.5 x (measured 25 Nov 2026, after / before per
# skill: 1.36, 0.83, 0.48, 0.57, 0.74; the zero-command skill's unfitted error is already small), so the builder's
# fixture fits longer (epochs 100, lr 3e-3, batch 256: 0.40, 0.30, 0.13, 0.14, 0.19, about 6 s); the factor is the plan's.
FIT_TICKS = 120
TINY_HIDDEN = [64, 64]
FIT_EPOCHS, FIT_LR, FIT_BATCH, FIT_SEED = 100, 3e-3, 256, 11
SMOKE_NET = {"hidden": [32, 32]}     # the dagger test's net and epochs: the committed [net] and [fit] take a minute
SMOKE_EPOCHS = 3
# the report's final keys and a round's summary keys (plan section 3, "The files M2 writes", fit_report.json)
FINAL_KEYS = {"per_skill", "unused_max_abs", "zero_skill", "rmse_by_n_live", "rmse_by_hold_bin", "delta_cmd",
              "game_steps_per_s"}
ROUND_KEYS = ["round", "rows", "kept", "shares_by_mode", "absent_share", "near_switch_share", "prev_net_rmse", "loss",
              "seconds"]


def _tiny(dg, cfg, side, seed=FIT_SEED):
    return distil.initial_net(dg.specs[side], cfg, {**dg.net, "hidden": TINY_HIDDEN}, seed)


def _skill_rmse(net, rows) -> torch.Tensor:
    """[K]: each skill's RMSE over its 4 channels on every row (every code, as the loss)."""
    out = distil.code_outputs(net, rows, "cpu")
    return ((out - rows.label) ** 2).mean(dim=(0, 2)).sqrt()


def _report(dg, cfg, side, net, ticks, games=GAMES, seed=None):
    d = dg.data
    return distil.report(net, cfg, dg.specs[side], dg.skills_gates.players, side, games, ticks,
                         dg.report["seed"] if seed is None else seed, dg.report["hold_bins_ticks"], "cpu",
                         size=dg.skills_gates.run["size"], shares=(d["uniform_share"], d["mix_share"], d["random_share"]),
                         hold=d["hold"], switch_jump=d["switch_jump"], switch_window_ticks=d["switch_window_ticks"])


@pytest.fixture(scope="module")
def guard_fit_rows(dg, cfg):
    return _collect(dg, cfg, "guard", FIT_TICKS)


def test_the_initial_net_is_seeded_and_leaves_the_global_rng_alone(dg, cfg):
    before = torch.random.get_rng_state()
    a, b = _tiny(dg, cfg, "guard"), _tiny(dg, cfg, "guard")
    assert torch.equal(torch.random.get_rng_state(), before), "the initial net drew from the global generator"
    for (ka, va), (kb, vb) in zip(a.state_dict().items(), b.state_dict().items()):
        assert ka == kb and torch.equal(va, vb), ka
    c = _tiny(dg, cfg, "guard", seed=FIT_SEED + 1)
    assert not torch.equal(a.state_dict()["mlp.0.weight"], c.state_dict()["mlp.0.weight"])
    spec = dg.specs["guard"]
    assert (a.team, a.skills, a.team_size, a.slot_width, a.hidden, a.zeroed_inputs) == \
        ("guard", tuple(spec.players), spec.drones, cfg.pad_guards, TINY_HIDDEN, dg.net["zeroed_inputs"])
    s = distil.initial_net(dg.specs["strike"], cfg, dg.net, FIT_SEED)
    assert s.slot_width == cfg.pad_strikes and s.hidden == dg.net["hidden"]


def test_code_outputs_are_the_nets_every_code_on_each_row(dg, cfg, guard_rows):
    net = _tiny(dg, cfg, "guard")
    out = distil.code_outputs(net, guard_rows, "cpu")
    r, k = guard_rows.obs.shape[0], net.k
    assert out.shape == (r, k, 4) and out.dtype == torch.float32 and not out.requires_grad
    sel = torch.arange(0, r, 7)
    with torch.no_grad():
        for z in range(k):
            want = net(guard_rows.obs[sel], guard_rows.slot[sel], torch.full((sel.numel(),), z))
            assert torch.allclose(out[sel, z], want, atol=1e-6), z          # another batch shape (constraint 8)
    err = distil.row_error(net, guard_rows, "cpu")
    want = ((out - guard_rows.label) ** 2).mean(dim=(1, 2)).sqrt()
    assert err.shape == (r,) and torch.allclose(err, want)


def test_fit_lowers_the_error_of_every_skill(dg, cfg, guard_fit_rows):
    rows = guard_fit_rows
    before = _skill_rmse(_tiny(dg, cfg, "guard"), rows)
    net = _tiny(dg, cfg, "guard")
    seen = []
    out = distil.fit(net, rows, FIT_EPOCHS, FIT_LR, FIT_BATCH, FIT_SEED, "cpu", check=lambda **kw: seen.append(kw),
                     std_floor=dg.net["std_floor"])
    after = _skill_rmse(net, rows)
    assert bool((after < 0.5 * before).all()), (before.tolist(), after.tolist())
    assert list(out) == ["loss"] and len(out["loss"]) == FIT_EPOCHS and all(isinstance(x, float) for x in out["loss"])
    assert out["loss"][-1] < out["loss"][0]
    assert [list(kw) for kw in seen] == [["loss"]] * FIT_EPOCHS and [kw["loss"] for kw in seen] == out["loss"]
    # the normaliser: the rows' mean and std, the std floored at the gate file's floor
    std, mean = torch.std_mean(rows.obs.double(), dim=0, correction=0)
    assert torch.allclose(net.in_mean, mean.float()) and torch.allclose(net.in_std, std.float().clamp(
        min=dg.net["std_floor"]))
    assert bool((net.in_std >= dg.net["std_floor"]).all())
    # a fitted net flies without a graph
    assert not any(p.requires_grad for p in net.parameters())


def test_fit_is_seeded_and_stops_between_epochs(dg, cfg, guard_rows):
    nets = [_tiny(dg, cfg, "guard") for _ in range(2)]
    outs = [distil.fit(n, guard_rows, 2, FIT_LR, FIT_BATCH, FIT_SEED, "cpu", std_floor=dg.net["std_floor"])
            for n in nets]
    assert outs[0] == outs[1]
    for (k, a), (_, b) in zip(nets[0].state_dict().items(), nets[1].state_dict().items()):
        assert torch.equal(a, b), k
    calls = []

    def stop():
        calls.append(1)
        return len(calls) > 1

    with pytest.raises(sweep.SweepStopped):
        distil.fit(_tiny(dg, cfg, "guard"), guard_rows, 5, FIT_LR, FIT_BATCH, FIT_SEED, "cpu", should_stop=stop,
                   std_floor=dg.net["std_floor"])
    assert len(calls) == 2, "the stop is asked once before each epoch"
    with pytest.raises(ValueError, match="rows"):
        distil.fit(_tiny(dg, cfg, "guard"), distil.take_rows(guard_rows, torch.zeros(0, dtype=torch.long)), 1, FIT_LR,
                   FIT_BATCH, FIT_SEED, "cpu", std_floor=dg.net["std_floor"])


# ================================================================================================ T3: the rounds
def test_net_flown_games_reach_other_states_and_stay_script_labelled(dg, cfg, guard_rows):
    spec = dg.specs["guard"]
    rows = _collect(dg, cfg, "guard", SHORT_TICKS, script_share=0.0, net=_tiny(dg, cfg, "guard"))
    assert bool(rows.net_flown.all())
    first, ref_first = (rows.tick == 0) & (rows.episode == 0), (guard_rows.tick == 0) & (guard_rows.episode == 0)
    assert torch.equal(rows.obs[first], guard_rows.obs[ref_first]), "the same starts"
    n = min(rows.obs.shape[0], guard_rows.obs.shape[0])
    assert rows.obs.shape != guard_rows.obs.shape or not torch.equal(rows.obs[:n], guard_rows.obs[:n]), \
        "the net-flown games must reach other states"
    r = rows.obs.shape[0]
    team = isolated(rows.obs, rows.slot, spec.drones)
    for k, name in enumerate(spec.players):
        want = make_strategy(name, "guard", cfg, r, "cpu", 0).act(team)[torch.arange(r), rows.slot]
        assert torch.equal(rows.label[:, k], want), name


@pytest.fixture(scope="module")
def round0(dg):
    """Round 0 of the smoke sizes, Guard team (no net: the scripts fly every game)."""
    return distil.round_rows(dg, "guard", 0, None, "cpu", smoke=True)


def test_round_zero_needs_no_net_and_later_rounds_do(dg, cfg, round0):
    sizes = distil.run_sizes(dg, smoke=True)
    kept, stats = round0
    assert stats["round"] == 0 and stats["prev_net_rmse"] is None and bool((kept.round == 0).all())
    assert stats["rows"] >= stats["kept"] == kept.obs.shape[0] > 0
    assert stats["kept"] == min(dg.data["keep_rows"], stats["rows"])
    with pytest.raises(ValueError, match="net"):
        distil.round_rows(dg, "guard", 1, None, "cpu", smoke=True)
    with pytest.raises(ValueError, match="round"):
        distil.round_rows(dg, "guard", len(sizes["script_share"]), _tiny(dg, cfg, "guard"), "cpu", smoke=True)
    # the same round, the same kept rows (seeded: the round's collection and its keep)
    again, _ = distil.round_rows(dg, "guard", 0, None, "cpu", smoke=True)
    for name in distil.ROW_FIELDS:
        assert torch.equal(getattr(kept, name), getattr(again, name)), name


def test_run_sizes_follow_the_smoke_rule(dg):
    full, smoke = distil.run_sizes(dg, smoke=False), distil.run_sizes(dg, smoke=True)
    assert full == {"games": dg.data["games"], "ticks": dg.data["ticks_per_round"],
                    "script_share": dg.dagger["script_share"], "report_games": dg.report["games"],
                    "report_ticks": dg.report["ticks"]}
    assert smoke == {"games": dg.smoke["games"], "ticks": dg.smoke["ticks"],
                     "script_share": dg.dagger["script_share"][:dg.smoke["rounds"]], "report_games": dg.smoke["games"],
                     "report_ticks": dg.smoke["ticks"]}


def test_the_keep_and_fit_seeds_are_new(dg):
    data, script_share = dg.data, dg.dagger["script_share"]
    others = {dg.fit["seed"], dg.report["seed"], dg.clips["seed"], data["pool_seed"], data["seed"]}
    assert {"keep", "shuffle"} <= set(distil.SEED_PURPOSES)
    derived = [distil.round_seed(s, r, p) for s in (data["seed"], data["pool_seed"], dg.fit["seed"], dg.report["seed"])
               for r in range(len(script_share)) for p in distil.SEED_PURPOSES]
    assert len(set(derived)) == len(derived) and not set(derived) & others
    # T2's purposes keep their seeds (appended, not reordered)
    assert distil.SEED_PURPOSES[:3] == ("game", "schedule", "pool")


@pytest.fixture(scope="module")
def small(dg):
    """The committed gate file with a small [net] and few [fit] epochs (the rounds' logic, not the sizes, is tested)."""
    return dataclasses.replace(dg, net={**dg.net, **SMOKE_NET}, fit={**dg.fit, "epochs": SMOKE_EPOCHS})


@pytest.fixture(scope="module")
def smoke_dagger(small):
    return distil.dagger(small, "guard", "cpu", smoke=True)


def test_dagger_refits_from_the_fit_seed_on_every_round_so_far(small, smoke_dagger, round0):
    dg = small
    net, rounds = smoke_dagger
    sizes = distil.run_sizes(dg, smoke=True)
    assert [s["round"] for s in rounds] == list(range(len(sizes["script_share"])))
    for s in rounds:
        assert list(s) == ROUND_KEYS
        assert set(s["shares_by_mode"]) == set(distil.MODES) and math.isclose(sum(s["shares_by_mode"].values()), 1.0)
        assert 0 <= s["absent_share"] <= 1 and 0 <= s["near_switch_share"] <= 1
        assert len(s["loss"]) == dg.fit["epochs"] and s["seconds"] > 0 and s["kept"] <= s["rows"]
    assert rounds[0]["prev_net_rmse"] is None and isinstance(rounds[1]["prev_net_rmse"], float)
    json.dumps(rounds, allow_nan=False)
    # the last net is the fit of a fresh [fit] seed net on every round's kept rows (OP-17), seeded
    kept = [round0[0]]                                 # round 0 does not read [net] or [fit]
    first, _ = distil.refit(dg, "guard", kept, "cpu")
    kept.append(distil.round_rows(dg, "guard", 1, first, "cpu", smoke=True)[0])
    again, fit_out = distil.refit(dg, "guard", kept, "cpu")
    assert fit_out["loss"] == rounds[1]["loss"]
    for (k, a), (_, b) in zip(net.state_dict().items(), again.state_dict().items()):
        assert torch.equal(a, b), k
    assert net.hidden == dg.net["hidden"] and net.zeroed_inputs == dg.net["zeroed_inputs"]


# ================================================================================================ T3: the report
@pytest.fixture(scope="module")
def strike_report_rows(dg, cfg):
    """A net-flown Strike collection on the report's seeds, long enough for games to end and restart."""
    d = dg.data
    rows, seconds = distil.report_collect(_tiny(dg, cfg, "strike"), cfg, dg.specs["strike"], dg.skills_gates.players,
                                          "strike", GAMES, LONG_TICKS, dg.report["seed"], "cpu",
                                          size=dg.skills_gates.run["size"],
                                          shares=(d["uniform_share"], d["mix_share"], d["random_share"]),
                                          hold=d["hold"], switch_jump=d["switch_jump"],
                                          switch_window_ticks=d["switch_window_ticks"])
    return rows, seconds


def test_report_has_every_read_and_none_for_empty_strata(dg, cfg):
    guard = _report(dg, cfg, "guard", _tiny(dg, cfg, "guard"), SHORT_TICKS)
    strike = _report(dg, cfg, "strike", _tiny(dg, cfg, "strike"), SHORT_TICKS)
    edges = dg.report["hold_bins_ticks"]
    bins = [f"{lo}-{hi}" for lo, hi in zip(edges, edges[1:])]
    for side, rep in (("guard", guard), ("strike", strike)):
        players = dg.specs[side].players
        assert set(rep) == FINAL_KEYS
        json.dumps(rep, allow_nan=False)
        assert list(rep["per_skill"]) == list(players) and list(rep["unused_max_abs"]) == list(players)
        for name, s in rep["per_skill"].items():
            assert set(s) == {"rmse", "p99_abs", "active", "rows"} and s["rows"] > 0
            assert len(s["rmse"]) == len(s["p99_abs"]) == len(s["active"]) == 4
            assert all(isinstance(a, bool) for a in s["active"])
            assert all(0 <= p for p in s["p99_abs"])
        assert set(rep["rmse_by_n_live"]) == {"1", "2", "3"}
        assert list(rep["rmse_by_hold_bin"]) == bins
        # ticks 24 < the upper bins' lower edges: those strata are empty, written None
        assert all(rep["rmse_by_hold_bin"][b] is None for b, lo in zip(bins, edges) if lo >= SHORT_TICKS)
        assert any(v is not None for v in rep["rmse_by_hold_bin"].values())
        assert rep["rmse_by_n_live"]["3"] is not None
        assert set(rep["delta_cmd"]) == {"net", "scripts"} and all(isinstance(v, float) for v in
                                                                    rep["delta_cmd"].values())
        assert isinstance(rep["game_steps_per_s"], float) and rep["game_steps_per_s"] > 0
    assert guard["zero_skill"]["name"] == "guard_parked_centre" and set(guard["zero_skill"]) == {"name", "max_abs"}
    assert guard["per_skill"]["guard_parked_centre"]["active"] == [False] * 4
    assert guard["unused_max_abs"]["guard_parked_centre"] is None, "the zero-command skill is read in zero_skill"
    for name, s in strike["per_skill"].items():
        if name in ("strike_high", "strike_low"):
            assert s["active"][2], name                   # vz (channel 2) active
        else:
            assert s["active"] == [True, True, False, False], name     # channels 0 and 1 only
        assert isinstance(strike["unused_max_abs"][name], float)
    assert strike["zero_skill"] is None


def test_the_report_numbers_match_a_direct_recomputation(dg, cfg, strike_report_rows):
    """Per skill, by n_live and by hold bin, from the rows and the net with plain loops (not the module's code)."""
    rows, _ = strike_report_rows
    net = _tiny(dg, cfg, "strike")
    rep = distil.summarise(net, rows, dg.report["hold_bins_ticks"], "cpu")
    out = distil.code_outputs(net, rows, "cpu").double()
    err = out - rows.label.double()
    players = dg.specs["strike"].players
    active = {}
    for k, name in enumerate(players):
        a = [bool((rows.label[:, k, c] != 0).any()) for c in range(4)]
        active[k] = a
        s = rep["per_skill"][name]
        assert s["active"] == a and s["rows"] == rows.obs.shape[0]
        for c in range(4):
            assert math.isclose(s["rmse"][c], float((err[:, k, c] ** 2).mean().sqrt()), rel_tol=1e-6)
            col = err[:, k, c].abs().sort().values
            assert math.isclose(s["p99_abs"][c], float(col[math.ceil(0.99 * col.numel()) - 1]), rel_tol=1e-6)
    for j in ("1", "2", "3"):
        sq = [float(err[i, k, c]) ** 2 for i in range(rows.obs.shape[0]) if int(rows.n_live[i]) == int(j)
              for k in range(len(players)) for c in range(4) if active[k][c]]
        want = math.sqrt(sum(sq) / len(sq)) if sq else None
        got = rep["rmse_by_n_live"][j]
        assert (got is None) == (want is None) and (want is None or math.isclose(got, want, rel_tol=1e-6)), j
    edges = dg.report["hold_bins_ticks"]
    for lo, hi in zip(edges, edges[1:]):
        sq = [float(err[i, int(rows.flown[i]), c]) ** 2 for i in range(rows.obs.shape[0])
              if lo <= int(rows.held[i]) < hi for c in range(4) if active[int(rows.flown[i])][c]]
        want = math.sqrt(sum(sq) / len(sq)) if sq else None
        got = rep["rmse_by_hold_bin"][f"{lo}-{hi}"]
        assert (got is None) == (want is None) and (want is None or math.isclose(got, want, rel_tol=1e-6)), (lo, hi)
    assert rep["rmse_by_n_live"]["3"] is not None and rep["rmse_by_hold_bin"][f"{edges[0]}-{edges[1]}"] is not None


def test_scripts_tick_to_tick_change_matches_a_direct_recomputation(dg, cfg, strike_report_rows):
    rows, _ = strike_report_rows
    assert bool((rows.episode > 0).any()), "no game restarted (the same-game rule is not exercised)"
    net = _tiny(dg, cfg, "strike")
    rep = distil.summarise(net, rows, dg.report["hold_bins_ticks"], "cpu")
    flown_net = distil.code_outputs(net, rows, "cpu")[torch.arange(rows.obs.shape[0]), rows.flown]
    flown_scr = rows.label[torch.arange(rows.obs.shape[0]), rows.flown]
    d_net, d_scr, pairs = 0.0, 0.0, 0
    for idx in _sequences(rows).values():                 # one live drone of one game, in tick order
        for a, b in zip(idx, idx[1:]):
            if int(rows.tick[b]) != int(rows.tick[a]) + 1:
                continue                                  # not live both ticks
            d_net += float((flown_net[b] - flown_net[a]).abs().sum())
            d_scr += float((flown_scr[b] - flown_scr[a]).abs().sum())
            pairs += 1
    assert pairs > 0
    assert math.isclose(rep["delta_cmd"]["scripts"], d_scr / (4 * pairs), rel_tol=1e-6)
    assert math.isclose(rep["delta_cmd"]["net"], d_net / (4 * pairs), rel_tol=1e-5)


def test_the_report_plays_its_own_seed_net_flown(dg, cfg, strike_report_rows):
    rows, seconds = strike_report_rows
    assert bool(rows.net_flown.all()) and seconds > 0
    # its starts are none of the rounds' (the report's seed, its own pool stream: design check of M2)
    for r in range(len(dg.dagger["script_share"])):
        other = _collect(dg, cfg, "strike", 1, seed=dg.data["seed"], pool_seed=dg.data["pool_seed"], round_index=r)
        assert not torch.equal(other.obs, rows.obs[rows.tick == 0]), r
    want = pool.pool_draw(distil.round_seed(dg.report["seed"], 0, "pool"), rows.game.long(), rows.episode.long(),
                          len(pool.pool_members(dg.skills_gates.players, "guard")))
    assert torch.equal(rows.opponent.long(), want), "the report's opponents come from [report] seed"
