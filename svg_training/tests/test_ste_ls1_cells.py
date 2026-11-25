"""Route 3, stage LS1, task LS1-M1-T5: the cells of the reads, either team (``ste/cells.py``; plan
ste_learning/drafts/LS1_TASK_PLAN.md, contract C6).

The cells: fixed-choice cell k = every drone flies code k (code = index in the team's ``[players]`` list), mixed cells =
"free" combinations with at least two distinct drone skills. Checked here, CPU only:

* the choices: ``all_choices`` is the run 0 ceiling's list for the Strike team (field for field), ``fixed_choices`` has
  one entry per code, ``mixed_pool`` has 24 (Guard) and 60 (Strike) entries, disjoint from the fixed ones;
  ``draw_mixed`` is deterministic and draws distinct members;
* the oracle's premise (review A F5): the scripts are row-wise, so ``ScriptOracle`` (each row alone in a zero team
  tensor at its slot, every script once, gather) equals the scripts' team commands bit for bit, live and out rows;
* play on T44's starts (24 games, ``hold_ticks`` = 1, both teams, one game batch per team): every fixed choice through
  ``fixed_team`` over the real two-level dispatch equals its T44 cell (``exploit.replay_ok``, every game); a
  ``Composite`` of one script equals T44 too; 4 mixed combinations through ``fixed_team`` equal their ``Composite``;
  the same choices flown by ``NetTwoLevelDispatch(net=ScriptOracle(...))`` equal the scripts' cells game for game
  (positive control 2 in miniature, review A F4.1).

Each choice plays one opponent, the other team's ``[players]`` list taken in turn over the fixed then the mixed
choices (so every opponent is played), not every opponent: the batch stays one per team (about 20 s for the file)."""
import random
import sys

import pytest
import torch

from svg_training.core.observations import OBS_DIM
from svg_training.opponents.scripted import REGISTRY, make_strategy
from svg_training.ste import cells, exploit, skill_net, skills

import _ste_ls1 as h
from _ste_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import ste_l3_run0_ceiling as ceiling  # noqa: E402

SIDES = ("guard", "strike")
GAMES = 24
MIXED_PER_SIDE = 4
DRAW_SEED = 31                    # any seed: the test only needs the draw to repeat
POOL_SIZES = {"guard": 24, "strike": 60}


@pytest.fixture(scope="module")
def gates():
    return exploit.load_gates(h.SKILLS_GATES)


@pytest.fixture(scope="module")
def ref(gates):
    return exploit.load_reference(exploit.ROOT / gates.reference["file"])


@pytest.fixture(scope="module")
def specs(gates):
    return {side: cells.cell_spec(gates, side) for side in SIDES}


# ================================================================================================ the choices
def test_the_cell_spec_reads_the_gate_file(gates, specs):
    for side in SIDES:
        sp = specs[side]
        assert sp.side == side and sp.players == tuple(skills.team_skills(gates.players, side))
        assert sp.team_strategies == tuple(gates.learner.team_strategies[side])
        assert sp.drone_skills == tuple(gates.learner.drone_skills[side])
        assert sp.drones == 3
    assert cells.other("guard") == "strike" and cells.other("strike") == "guard"
    assert cells.cell_of("guard", "g", "s") == ("g", "s") and cells.cell_of("strike", "s", "g") == ("g", "s")
    with pytest.raises(ValueError):
        cells.other("zone")


def test_a_gate_file_that_is_not_two_level_is_refused():
    velocity = exploit.load_gates(exploit.ROOT / "configs" / "ste_l3" / "velocity_gates.toml")
    with pytest.raises(ValueError, match="two_level"):
        cells.cell_spec(velocity, "strike")


def test_all_choices_are_the_ceilings_for_the_strike_team(gates, specs):
    assert cells.all_choices(specs["strike"]) == ceiling.choices(gates)
    guard = cells.all_choices(specs["guard"])
    sp = specs["guard"]
    assert len(guard) == len(sp.team_strategies) + len(sp.drone_skills) ** sp.drones
    assert len({c["name"] for c in guard}) == len(guard)


@pytest.mark.parametrize("side", SIDES)
def test_one_fixed_choice_per_code_in_players_order(specs, side):
    sp = specs[side]
    fixed = cells.fixed_choices(sp)
    assert [c["script"] for c in fixed] == list(sp.players)
    every = {c["name"]: c for c in cells.all_choices(sp)}
    for code, c in enumerate(fixed):
        assert set(c) == {"name", "kind", "heads", "flies", "script"}
        assert c["flies"] == [sp.players[code]] * 3
        assert every[c["name"]] == c                         # a fixed choice is one of the ceiling's choices
        if sp.players[code] in sp.team_strategies:
            t = sp.team_strategies.index(sp.players[code]) + 1
            assert c["kind"] == "team" and c["heads"] == [(t, 0)] * 3
        else:
            d = sp.drone_skills.index(sp.players[code])
            assert c["kind"] == "free" and c["heads"] == [(skills.FREE, d)] * 3


@pytest.mark.parametrize("side", SIDES)
def test_the_mixed_pool_is_every_free_combination_of_two_or_more_skills(specs, side):
    sp = specs[side]
    pool = cells.mixed_pool(sp)
    assert len(pool) == POOL_SIZES[side] and len(set(pool)) == len(pool)
    assert all(len(c) == sp.drones and len(set(c)) >= 2 and set(c) <= set(sp.drone_skills) for c in pool)
    fixed = {tuple(c["flies"]) for c in cells.fixed_choices(sp)}
    assert not fixed & set(pool)
    mixed = cells.mixed_choices(sp, pool)
    every = {c["name"]: c for c in cells.all_choices(sp)}
    for combo, c in zip(pool, mixed):
        assert c["flies"] == list(combo) and c["kind"] == "free" and c["script"] is None
        assert c["heads"] == [(skills.FREE, sp.drone_skills.index(s)) for s in combo]
        assert every[c["name"]] == c
    with pytest.raises(ValueError):
        cells.mixed_choices(sp, [(sp.drone_skills[0],) * sp.drones])      # one skill on every drone: not mixed


@pytest.mark.parametrize("side", SIDES)
def test_draw_mixed_is_deterministic_and_distinct(specs, side):
    sp = specs[side]
    a = cells.draw_mixed(sp, MIXED_PER_SIDE, DRAW_SEED)
    assert a == cells.draw_mixed(sp, MIXED_PER_SIDE, DRAW_SEED)
    assert len(a) == MIXED_PER_SIDE and len(set(a)) == MIXED_PER_SIDE and set(a) <= set(cells.mixed_pool(sp))
    assert a == random.Random(DRAW_SEED).sample(cells.mixed_pool(sp), MIXED_PER_SIDE)   # the stdlib stream only
    assert a != cells.draw_mixed(sp, MIXED_PER_SIDE, DRAW_SEED + 1)
    assert len(set(cells.draw_mixed(sp, POOL_SIZES[side], DRAW_SEED))) == POOL_SIZES[side]


def test_the_name_prefixes_never_shadow_a_script():
    assert len(set(cells.PREFIXES)) == len(cells.PREFIXES) == 6
    assert set(cells.PREFIXES) == {cells.NET_PREFIX, cells.SCR_PREFIX, cells.ORC_PREFIX, cells.UNF_PREFIX,
                                   cells.PERM_PREFIX, cells.CAL_PREFIX}
    assert all(p.endswith(":") for p in cells.PREFIXES)
    assert not [name for name in REGISTRY for p in cells.PREFIXES if name.startswith(p)]


def test_a_composite_refuses_a_member_of_the_other_team(gates):
    cfg = exploit.variant_cfg(gates, "base")
    with pytest.raises(ValueError):
        cells.Composite("strike", ["strike_straight", "guard_field", "strike_low"], cfg, 4)
    with pytest.raises(ValueError):
        cells.Composite("guard", ["guard_field", "guard_field", "strike_low"], cfg, 4)
    guard_player = make_strategy("guard_field", "guard", cfg, 4, "cpu", 0)
    with pytest.raises(ValueError):
        cells.Composite("strike", ["strike_straight", guard_player, "strike_low"], cfg, 4)


# ================================================================================================ the oracle's premise
@pytest.mark.parametrize("side", SIDES)
def test_the_scripts_are_row_wise(gates, specs, side):
    """Review A F5: each script's command for a drone depends on that drone's observation row only, so the oracle
    (each row alone at its slot in a zero team tensor) equals the scripts' team commands bit for bit, every code, on
    live and out rows (``team_obs``: 40 ticks of play, some drones tagged)."""
    sp = specs[side]
    cfg, obs = h.team_obs(gates, side)
    n, m = obs.shape[:2]
    live = obs[..., skills._V.alive] > skills.ALIVE_FLAG_MIN
    assert live.any() and (~live).any()                      # both kinds of row are in the batch
    oracle = cells.ScriptOracle(cfg, side, list(sp.players), m)
    assert oracle.team == side and oracle.skills == sp.players and oracle.k == len(sp.players)
    assert oracle.team_size == m and isinstance(oracle, torch.nn.Module)
    rows = obs.reshape(n * m, OBS_DIM)
    slot = torch.arange(m).repeat(n)
    scripts = [make_strategy(name, side, cfg, n, "cpu", 0) for name in sp.players]
    want = torch.stack([s.act(obs) for s in scripts], dim=2)                       # [N, M, K, 4]
    for code in range(len(sp.players)):
        got = oracle(rows, slot, torch.full((n * m,), code)).reshape(n, m, skill_net.COMMAND_DIM)
        assert torch.equal(got, want[:, :, code]), sp.players[code]
    z = torch.randint(len(sp.players), (n, m), generator=torch.Generator().manual_seed(3))
    got = oracle(rows, slot, z.reshape(-1)).reshape(n, m, skill_net.COMMAND_DIM)
    assert torch.equal(got, torch.gather(want, 2, z[:, :, None, None].expand(-1, -1, 1, 4))[:, :, 0])
    # through the dispatch's two paths: the oracle-flown dispatch equals the scripts' dispatch
    lists = (list(sp.players), list(sp.team_strategies), list(sp.drone_skills))
    scr = skills.TwoLevelDispatch(side, *lists, cfg, n, "cpu", 0)
    net = skills.NetTwoLevelDispatch(side, *lists, cfg, n, "cpu", 0, oracle, None)
    assert torch.equal(net.commands(obs), scr.commands(obs))
    assert torch.equal(net.act(obs, z), scr.act(obs, z))


# ================================================================================================ play on T44's starts
def _opponents(gates, side):
    return skills.team_skills(gates.players, cells.other(side))


@pytest.fixture(scope="module")
def played(gates, ref, specs):
    """Per team one game batch of GAMES games per cell, hold 1, T44's starts and seed: every fixed choice through the
    scripts' dispatch (``scr:``), through a one-script ``Composite`` (``orc:``) and through the oracle-flown dispatch
    (``net:``); 4 drawn mixed choices through the same three. Each choice plays one opponent, the other team's list
    in turn over the fixed then the mixed choices (so every opponent is played). Returns {side: (rows, pg)}, rows =
    [(arm, choice, opponent)] in cell order."""
    out = {}
    cfg = exploit.variant_cfg(gates, "base")
    seed = int(ref.meta["seed"])
    for side in SIDES:
        sp = specs[side]
        off = exploit.GUARD_SEED_OFFSET if side == "guard" else exploit.STRIKE_SEED_OFFSET
        opps = _opponents(gates, side)
        fixed = cells.fixed_choices(sp)
        mixed = cells.mixed_choices(sp, cells.draw_mixed(sp, MIXED_PER_SIDE, DRAW_SEED))
        plan = [(c, opps[i % len(opps)]) for i, c in enumerate(fixed + mixed)]
        rows, players, cell_list = [], {}, []
        for arm in ("scr", "orc", "net"):
            for c, opp in plan:
                name = f"{arm}:{c['name']}@{opp}"
                if arm == "orc":
                    player = cells.Composite(side, c["flies"], cfg, GAMES, seed=seed + off, name=name)
                elif arm == "scr":
                    d = skills.two_level_dispatch(gates.learner, gates.players, side, cfg, GAMES, "cpu", seed + off)
                    player = cells.fixed_team(sp, c, d, name)
                else:
                    oracle = cells.ScriptOracle(cfg, side, list(sp.players), sp.drones)
                    d = skills.NetTwoLevelDispatch(side, list(sp.players), list(sp.team_strategies),
                                                   list(sp.drone_skills), cfg, GAMES, "cpu", seed + off, oracle, None)
                    player = cells.fixed_team(sp, c, d, name)
                assert name not in players and player.name == name
                players[name] = player
                rows.append((arm, c, opp))
                cell_list.append(cells.cell_of(side, name, opp))
        pg = exploit.play_cells(cfg, gates.run["size"], ref, cell_list, GAMES, "cpu", seed,
                                int(gates.run["ticks_cap"]), hold_ticks=1, players=players)
        out[side] = (rows, pg)
    return out


def specs_players(rows):
    """The fixed choices among the scripts' dispatch rows (one per code)."""
    return [c for a, c, _ in rows if a == "scr" and c["script"] is not None]


def _cell(played_side, arm, name, opp):
    rows, pg = played_side
    k = next(i for i, (a, c, o) in enumerate(rows) if a == arm and c["name"] == name and o == opp)
    return exploit.slice_cell(pg, k, GAMES)


@pytest.mark.parametrize("side", SIDES)
def test_every_fixed_choice_through_the_dispatch_replays_its_t44_cell(gates, ref, specs, played, side):
    """C6: fixed-choice cell k (every drone flies code k, through ``fixed_team`` over the real two-level dispatch) is
    T44's cell of that script, every game on the CPU; a ``Composite`` of the one script is too."""
    rows, _ = played[side]
    fixed = [(c, o) for a, c, o in rows if a == "scr" and c["script"] is not None]
    assert [c["script"] for c, _ in fixed] == list(specs[side].players)
    assert {o for a, _, o in rows if a == "scr"} == set(_opponents(gates, side))    # every opponent is played
    cap = int(gates.run["ticks_cap"])
    for c, opp in fixed:
        t44 = {k: v[:GAMES] for k, v in ref.cell("base", *cells.cell_of(side, c["script"], opp)).items()}
        for arm in ("scr", "orc"):
            good, text = exploit.replay_ok(_cell(played[side], arm, c["name"], opp), t44, "cpu", gates.controls,
                                           ticks_cap=cap)
            assert good, (side, arm, c["name"], opp, text)


@pytest.mark.parametrize("side", SIDES)
def test_a_mixed_choice_through_the_dispatch_equals_its_composite(played, side):
    rows, _ = played[side]
    mixed = [(c, o) for a, c, o in rows if a == "scr" and c["script"] is None]
    assert len(mixed) == MIXED_PER_SIDE
    for c, opp in mixed:
        ag = exploit.agreement(_cell(played[side], "scr", c["name"], opp), _cell(played[side], "orc", c["name"], opp))
        assert ag["differ"] == 0, (side, c["name"], ag)


@pytest.mark.parametrize("side", SIDES)
def test_the_oracle_flown_dispatch_equals_the_scripts_cells(played, side):
    """Positive control 2 in miniature (review A F4.1): ``NetTwoLevelDispatch(net=ScriptOracle(...))`` through
    ``fixed_team`` equals the scripts' cells game for game, every fixed choice and the 4 mixed ones."""
    rows, _ = played[side]
    chosen = [(c, o) for a, c, o in rows if a == "net"]
    assert [(c["name"], o) for c, o in chosen] == [(c["name"], o) for a, c, o in rows if a == "scr"]
    assert len(chosen) == len(specs_players(rows)) + MIXED_PER_SIDE
    for c, opp in chosen:
        mine = _cell(played[side], "net", c["name"], opp)
        for key in exploit.EXACT:
            assert (mine[key] == _cell(played[side], "scr", c["name"], opp)[key]).all(), (side, c["name"], key)


def test_the_played_batches_are_plumbed(ref, played):
    for side in SIDES:
        rows, pg = played[side]
        assert len(pg["start_sha256"]) == len(rows)
        assert set(pg["start_sha256"]) == {exploit.starts_sha(ref.starts_m[:GAMES])}
        assert int(pg["nonfinite_actions"].sum()) == 0
        names = [f"{a}:{c['name']}@{o}" for a, c, o in rows]
        assert len(set(names)) == len(names)                 # one object per cell (C6)


def test_fixed_team_takes_any_dispatch_and_keeps_its_name(gates, specs):
    cfg = exploit.variant_cfg(gates, "base")
    sp = specs["guard"]
    c = cells.fixed_choices(sp)[0]
    d = skills.two_level_dispatch(gates.learner, gates.players, "guard", cfg, 5, "cpu", 0)
    team = cells.fixed_team(sp, c, d, "scr:x")
    assert isinstance(team, exploit.SkillTeam) and team.name == "scr:x" and team.team == "guard"
    obs = torch.zeros(5, sp.drones, OBS_DIM)
    obs[..., skills._V.alive] = 1.0
    assert [sp.players[int(i)] for i in team.choose(obs)[0]] == c["flies"]
    with pytest.raises(ValueError):
        strike_d = skills.two_level_dispatch(gates.learner, gates.players, "strike", cfg, 5, "cpu", 0)
        cells.fixed_team(sp, c, strike_d, "scr:y")
