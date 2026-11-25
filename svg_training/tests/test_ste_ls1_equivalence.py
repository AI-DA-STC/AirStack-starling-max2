"""Route 3, stage LS1, task LS1-M2-T5: the equivalence read's players and its verdict functions (the importable part of
``scripts/ste_ls1_equivalence.py``; plan ste_learning/drafts/LS1_TASK_PLAN.md, section 3, and the design check of M2).

* The players (CPU, T44's starts, 24 games, hold 1, one game batch per team): the recorder keeps each slot's first game
  only, its positions at tick 0 are the side's columns of ``play_cells``' ``start_pos_m`` (the observation is
  zone-relative in xy, which is the world frame only because the base game's zone is centred); the oracle-flown net
  arm (``ScriptOracle`` through ``NetTwoLevelDispatch``) flies the scripts' games exactly, every fixed cell and two
  mixed combinations per side, with a command error of exactly 0 against the scripts' labels; a near-miss bias arm's
  error table comes from its own cells' recorders; the net arms carry no autograd graph; one player object per cell.
* The permuted scripts read from T44 alone (no play): cell (k, opp) is T44's cell (perm[k], opp).
* The verdict arithmetic, always on a synthetic gate file written under ``tmp_path`` from ``STAND_IN`` (constraint 5):
  each limit just crossed fails naming its key, just met passes; a ``FILL_`` value never reaches a comparison; the
  controls are read first; a cell inside the margin at plain alpha but outside at the adjusted z is NOT DISTILLED.
* ``test_the_committed_limits_run_through_the_rule`` is the one designed skip of M2 until the lead fills the file (R38).
"""
import contextlib
import io
import json
import math
import sys

import numpy as np
import pytest
import torch

from svg_training.core.game_config import TICK_S
from svg_training.core.observations import OBS_DIM
from svg_training.core.rewards import GUARD_WIN, STRIKE_WIN
from svg_training.opponents import perturbed
from svg_training.opponents.scripted import REGISTRY
from svg_training.ste import cells, distil, exploit, scoring, skill_net, skills
from svg_training.ste.run_contract import EXIT_CONTROL_FAILED, EXIT_DONE, EXIT_INTERRUPTED, EXIT_REFUSED
from svg_training.viz import replay3d

import _ste_ls1 as h
from _ste_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import ste_ls1_equivalence as eq  # noqa: E402

ROOT = exploit.ROOT
SIDES = ("guard", "strike")
GAMES = 24
MIXED_PER_SIDE = 2
TIMES_S = (0.0, 1.0, 10.0, 30.0, 90.0)         # the recorder test's marks (tick 0 included; the gate file's start at 1 s)
EPS = 1e-3                                     # "just crossed": a limit times (1 + EPS)


@pytest.fixture(scope="module")
def g():
    return distil.load_distil_gates(h.DISTIL_GATES)


@pytest.fixture(scope="module")
def stand_in(tmp_path_factory):
    """The distillation gate file with the owner's keys filled from STAND_IN (synthetic, constraint 5)."""
    return distil.load_distil_gates(h.write_distil_gates(tmp_path_factory.mktemp("stand_in")))


@pytest.fixture(scope="module")
def ref(g):
    return exploit.load_reference(ROOT / g.skills_gates.reference["file"])


def _cfg(g):
    return exploit.variant_cfg(g.skills_gates, distil.VARIANT)


def _side_cells(g, side):
    return cells.side_cells(g.specs[side], g.cells, g.skills_gates)


def _play_plan(g, side):
    """The side's fixed cells (each against one opponent, the other team's list taken in turn) and its first two
    cells.toml combinations."""
    every = [c for c in _side_cells(g, side) if c.kind != cells.INFO]
    opps = cells.gated_opponents(g.skills_gates, side)
    fixed = [next(c for c in every if c.kind == cells.FIXED and c.choice["script"] == code
                  and c.opponent == opps[i % len(opps)]) for i, code in enumerate(g.specs[side].players)]
    combos = [list(x) for x in g.cells["mixed"][side][:MIXED_PER_SIDE]]
    mixed = [next(c for c in every if c.kind == cells.MIXED and c.choice["flies"] == combo and c.opponent == opps[0])
             for combo in combos]
    return fixed + mixed


@pytest.fixture(scope="module")
def played(g, stand_in, ref):
    """Per side one game batch of GAMES games per cell: the scripts arm and the oracle arm on the play plan, and the
    STAND_IN bias arm on the first fixed cell. Returns {side: {"cells", "arms" {kind: players}, "pairs", "pg"}}."""
    out = {}
    cfg, seed = _cfg(g), int(ref.meta["seed"])
    for side in SIDES:
        among = _play_plan(g, side)
        spec = g.specs[side]
        oracle = cells.ScriptOracle(cfg, side, list(spec.players), spec.drones)
        arms = {kind: eq.arms(side, kind, g=g, among=among, cfg=cfg, n=GAMES, device="cpu", seed=seed,
                              net=oracle if kind == eq.ORACLE else None, path_times_s=TIMES_S)
                for kind in (eq.SCRIPTS, eq.ORACLE)}
        arms[eq.BIAS] = eq.arms(side, eq.BIAS, g=stand_in, among=among[:1], cfg=cfg, n=GAMES, device="cpu", seed=seed,
                                path_times_s=TIMES_S)
        players, pairs, order = {}, [], []
        for kind, group in arms.items():
            cell_list = eq.arm_cells(kind, among if kind != eq.BIAS else among[:1], side)
            for cell, (name, player) in zip(cell_list, group.items()):
                assert name not in players
                players[name] = player
                pairs.append(cells.cell_of(side, name, cell.opponent))
                order.append((kind, cell, name))
        pg = exploit.play_cells(cfg, g.skills_gates.run["size"], ref, pairs, GAMES, "cpu", seed,
                                int(g.skills_gates.run["ticks_cap"]), hold_ticks=eq.HOLD_TICKS, players=players)
        out[side] = {"cells": among, "arms": arms, "order": order, "pg": pg, "players": players}
    return out


def _slice(played_side, kind, cell):
    k = next(i for i, (a, c, _) in enumerate(played_side["order"]) if a == kind and c.index == cell.index)
    return exploit.slice_cell(played_side["pg"], k, GAMES), played_side["order"][k][2]


# ================================================================================================ the players
@pytest.mark.parametrize("side", SIDES)
def test_the_recorder_keeps_first_games_only(g, played, side):
    """Positions at tick 0 are the side's columns of ``start_pos_m`` (Guard drones first, then Strike drones; the
    observation is zone-relative in xy, the world frame here because the base game's zone is centred); at a mark at or
    after a game's end no drone of that game is recorded (the slot's later games are not counted)."""
    p = played[side]
    guards = g.specs["guard"].drones
    cols = slice(0, guards) if side == "guard" else slice(guards, None)
    ticks = [round(t / TICK_S) for t in TIMES_S]
    bit = 0
    for kind in (eq.SCRIPTS, eq.ORACLE):
        for cell in p["cells"]:
            mine, name = _slice(p, kind, cell)
            pos, alive = p["players"][name].paths()
            assert pos.shape == (GAMES, g.specs[side].drones, len(TIMES_S), 3) and pos.dtype == np.float32
            assert alive.shape == (GAMES, g.specs[side].drones, len(TIMES_S)) and alive.dtype == bool
            assert alive[:, :, 0].all()
            assert np.array_equal(pos[:, :, 0], mine["start_pos_m"][:, cols])
            for j, tick in enumerate(ticks):
                ended = np.asarray(mine["end_step"]) <= tick
                assert not alive[ended, :, j].any(), (kind, cell.index, tick)
                assert (pos[~alive[:, :, j], j] == 0).all()
                bit += int(ended.sum())
    assert bit > 0                      # some games end before the last mark: the check bites


@pytest.mark.parametrize("side", SIDES)
def test_the_oracle_net_flies_the_scripts_through_the_new_path(g, played, side):
    """Positive control 2 in miniature: fixed cells and two mixed combinations, differ 0 game for game against the
    scripts' arm, and the recorded command error against the scripts' labels is exactly 0 on every code flown."""
    p = played[side]
    assert sum(c.kind == cells.MIXED for c in p["cells"]) == MIXED_PER_SIDE
    for cell in p["cells"]:
        scr, _ = _slice(p, eq.SCRIPTS, cell)
        orc, name = _slice(p, eq.ORACLE, cell)
        assert exploit.agreement(orc, scr)["differ"] == 0, (side, cell.choice["name"], cell.opponent)
        acc = p["players"][name].errors()
        flown = set(cell.choice["flies"])
        assert {s for s, a in acc.items() if a["count"]} == flown
        for s in flown:
            assert acc[s]["sum_sq"] == [0.0] * 4 and acc[s]["max_abs"] == [0.0] * 4, (cell.choice["name"], s)
    table = eq.error_table(eq.sum_accumulators(g.specs[side].players,
                                               [p["players"][n].errors() for k, _, n in p["order"] if k == eq.ORACLE]))
    assert set(table["skills"]) == set(g.specs[side].players)
    for s, e in table["skills"].items():
        assert e["rows"] > 0 and e["rmse"] == [0.0] * 4 and e["max_abs"] == [0.0] * 4
        assert set(e["rmse_by_n_live"]) == {"1", "2", "3"}
        assert all(v in (None, 0.0) for v in e["rmse_by_n_live"].values())
    assert table["zero_skill"] == ("guard_parked_centre" if side == "guard" else None)
    active = eq.active_of(table)
    if side == "strike":
        assert all(active[s][2] for s in ("strike_high", "strike_low"))


@pytest.mark.parametrize("side", SIDES)
def test_a_near_miss_arm_reads_its_own_cells_errors(g, stand_in, played, side):
    """C6's errors argument: ``cells.command_errors`` over the bias arm's own recorders (perturbed's per-slot
    accumulators, each slot to the skill it flies): the xy error is the bias (or less, where the clamp at 1 bites), the
    other channels 0."""
    p = played[side]
    cell = p["cells"][0]
    _, name = _slice(p, eq.BIAS, cell)
    acc = eq.player_accumulators(p["players"][name], g.specs[side].players)
    table = eq.error_table(acc)
    code = cell.choice["script"]
    e = table["skills"][code]
    bias = stand_in.controls["near_miss"]["bias"]
    assert e["rows"] > 0 and "rmse_by_n_live" not in e
    assert 0 < e["rmse"][0] <= bias * (1 + 1e-6) and 0 < e["rmse"][1] <= bias * (1 + 1e-6)
    assert e["max_abs"][2] == 0.0 and e["max_abs"][3] == 0.0
    assert all(table["skills"][s]["rows"] == 0 for s in g.specs[side].players if s != code)


@pytest.mark.parametrize("side", SIDES)
def test_the_net_arm_command_carries_no_graph(g, side):
    """The unfitted, permuted and oracle networks fly under ``no_grad`` (``skill_net.one_code``)."""
    cfg, obs = h.team_obs(g.skills_gates, side, n=8, ticks=20)
    spec = g.specs[side]
    among = _side_cells(g, side)[:2]
    nets = {eq.UNFITTED: None, eq.PERMUTED: eq.unfitted_net(spec, g),
            eq.ORACLE: cells.ScriptOracle(cfg, side, list(spec.players), spec.drones)}
    for kind, net in nets.items():
        for player in eq.arms(side, kind, g=g, among=among, cfg=cfg, n=8, device="cpu", seed=0, net=net).values():
            player.reset(torch.ones(8, dtype=torch.bool))
            out = player.command(obs, player.choose(obs))
            assert out.shape == (8, spec.drones, 4) and not out.requires_grad and out.grad_fn is None, kind


@pytest.mark.parametrize("side", SIDES)
def test_the_error_accumulators_match_a_direct_recomputation(g, side):
    """R1's command-error accumulators (the numbers cmd_rmse_max reads), no play: an unfitted net with the scripts as
    labeller on real observations with out drones, a random code per drone; per code the sums of squares, max |error|,
    rows and label max equal a direct recomputation on the live rows of first games, and the live-drone bins add up to
    the totals. A game marked ended by ``reset`` is not counted afterwards."""
    cfg, obs = h.team_obs(g.skills_gates, side, n=64, ticks=40)
    spec = g.specs[side]
    n, m = obs.shape[:2]
    live = obs[..., skills._V.alive] > skills.ALIVE_FLAG_MIN
    assert live.any() and (~live).any()
    lists = (list(spec.players), list(spec.team_strategies), list(spec.drone_skills))
    net = eq.unfitted_net(spec, g)
    team = eq.recording_team(spec, cells.fixed_choices(spec)[0],
                             skills.NetTwoLevelDispatch(side, *lists, cfg, n, "cpu", 0, net, None), "net:x",
                             path_times_s=(0.0,), labeller=skills.TwoLevelDispatch(side, *lists, cfg, n, "cpu", 0))
    scripts = skills.TwoLevelDispatch(side, *lists, cfg, n, "cpu", 0)
    gen = torch.Generator().manual_seed(9)
    team.reset(torch.ones(n, dtype=torch.bool))
    ended = torch.zeros(n, dtype=torch.bool)
    ended[: n // 4] = True
    want = {s: {"sum_sq": torch.zeros(4, dtype=torch.float64), "max_abs": torch.zeros(4), "label": torch.zeros(4),
                "count": 0, "nl_sq": torch.zeros(m, 4, dtype=torch.float64), "nl_n": torch.zeros(m, dtype=torch.long)}
            for s in spec.players}
    for step in range(2):
        choice = torch.randint(len(spec.players), (n, m), generator=gen)
        out = team.command(obs, choice)
        flown = skill_net.one_code(net, obs, choice)
        assert torch.equal(out, flown)
        label = scripts.act(obs, choice)
        rows = live & (~ended[:, None] if step else torch.ones_like(live))
        n_live = live.sum(1).clamp(min=1)
        for k, s in enumerate(spec.players):
            mask = rows & (choice == k)
            d = (flown - label)[mask]
            w = want[s]
            w["sum_sq"] += (d.double() ** 2).sum(0)
            if mask.any():
                w["max_abs"] = torch.maximum(w["max_abs"], d.abs().amax(0))
                w["label"] = torch.maximum(w["label"], label[mask].abs().amax(0))
            w["count"] += int(mask.sum())
            for j in range(m):
                sel = mask & (n_live == j + 1)[:, None]
                w["nl_sq"][j] += ((flown - label)[sel].double() ** 2).sum(0)
                w["nl_n"][j] += int(sel.sum())
        team.reset(ended)                         # those games end now: their later rows are not counted
    got = team.errors()
    assert list(got) == list(spec.players)
    for s in spec.players:
        e, w = got[s], want[s]
        assert e["count"] == w["count"] > 0 and sum(e["count_by_n_live"]) == e["count"]
        assert torch.allclose(torch.tensor(e["sum_sq"], dtype=torch.float64), w["sum_sq"], rtol=1e-12, atol=0)
        assert torch.equal(torch.tensor(e["max_abs"], dtype=torch.float32), w["max_abs"])
        assert torch.equal(torch.tensor(e["label_max_abs"], dtype=torch.float32), w["label"])
        assert e["count_by_n_live"] == w["nl_n"].tolist()
        assert torch.allclose(torch.tensor(e["sum_sq_by_n_live"], dtype=torch.float64), w["nl_sq"], rtol=1e-12,
                              atol=0)
        assert torch.allclose(torch.tensor(e["sum_sq_by_n_live"], dtype=torch.float64).sum(0),
                              torch.tensor(e["sum_sq"], dtype=torch.float64), rtol=1e-12, atol=0)
    table = eq.error_table(got)
    for s in spec.players:
        t = table["skills"][s]
        on = t["active"]
        if any(on) and t["rows"]:
            num = sum(v for row in got[s]["sum_sq_by_n_live"] for v, a in zip(row, on) if a)
            pooled = math.sqrt(num / (t["rows"] * sum(on)))
            parts = [(v, c) for v, c in zip(t["rmse_by_n_live"].values(), got[s]["count_by_n_live"]) if c]
            assert math.isclose(math.sqrt(sum(v * v * c for v, c in parts) / t["rows"]), pooled, rel_tol=1e-9)


def test_the_unfitted_net_is_the_fit_start(g):
    """C4's network is the same initialisation the fit starts from ([fit] seed under fork_rng), the global RNG kept."""
    spec = g.specs["strike"]
    before = torch.random.get_rng_state()
    a, b = eq.unfitted_net(spec, g), distil.initial_net(spec, _cfg(g), g.net, g.fit["seed"])
    assert torch.equal(torch.random.get_rng_state(), before)
    for (ka, va), (kb, vb) in zip(a.state_dict().items(), b.state_dict().items()):
        assert ka == kb and torch.equal(va, vb)
    assert a.hidden == list(g.net["hidden"]) and a.zeroed_inputs == list(g.net["zeroed_inputs"])


def test_the_permuted_net_flies_code_perm_k_and_keeps_the_codes(g):
    side = "guard"
    spec = g.specs[side]
    cfg, obs = h.team_obs(g.skills_gates, side, n=6, ticks=20)
    net = eq.unfitted_net(spec, g)
    perm = list(g.cells["permutation"][side])
    pnet = eq.PermutedNet(net, perm)
    assert pnet.skills == net.skills and pnet.k == net.k and pnet.team == side and pnet.team_size == net.team_size
    rows = obs.reshape(-1, OBS_DIM)
    slot = torch.arange(spec.drones).repeat(6)
    for k in range(net.k):
        z = torch.full((rows.shape[0],), k)
        with torch.no_grad():
            assert torch.equal(pnet(rows, slot, z), net(rows, slot, torch.full_like(z, perm[k])))
    with pytest.raises(ValueError):
        eq.PermutedNet(net, [0] + perm[1:])                    # not a permutation of the codes


@pytest.mark.parametrize("side", SIDES)
def test_one_player_object_per_cell(g, stand_in, side):
    """C6: every arm gives each cell its own object under its own prefixed name; no name shadows a script."""
    cfg, spec = _cfg(g), g.specs[side]
    among = eq.near_miss_cells(stand_in, side) + [c for c in _side_cells(g, side) if c.kind == cells.MIXED][:3]
    net = eq.unfitted_net(spec, g)
    active = {s: [True, True, False, False] for s in spec.players}
    seen_names, seen_ids, kept = set(), set(), []          # kept: no object freed, so no id is reused
    for kind in eq.read_kinds(side):
        group = eq.arms(side, kind, g=stand_in, among=among, cfg=cfg, n=4, device="cpu", seed=0,
                        net=net if kind in (eq.PERMUTED, eq.NET) else None, active=active)
        assert len(group) == len(eq.arm_cells(kind, among, side)) > 0, kind
        for name, player in group.items():
            assert name.startswith(cells.PREFIXES) and player.name == name and player.team == side
            assert name not in seen_names and id(player) not in seen_ids
            seen_names.add(name)
            seen_ids.add(id(player))
            kept.append(player)
    assert not seen_names & set(REGISTRY)


# ================================================================================================ the near-miss arms
def _members(player, drones):
    """The changed player of each drone slot of a RecordingPlayer (one object for a uniform cell)."""
    inner = player.inner
    return [inner.members[m] for m in range(drones)] if isinstance(inner, cells.Composite) else [inner] * drones


@pytest.mark.parametrize("side", SIDES)
def test_each_near_miss_kind_maps_to_its_player(stand_in, side):
    """bias -> CommandPerturbation(kind="bias") on xy, rotate_deg -> kind="turn", noise -> kind="noise" on each skill's
    active channels (none for the zero-command skill: the identity, still recorded), seeded noise_seed + the cell's
    index x team size + the slot; each switch key -> its own moved player at its own value, on only the near-miss cells
    where its code flies (Strike three, Guard one)."""
    g = stand_in
    cfg, spec = _cfg(g), g.specs[side]
    nm = h.STAND_IN["controls"]["near_miss"]
    among = eq.near_miss_cells(g, side)
    assert [(c.choice["flies"] if c.kind == cells.MIXED else [c.choice["script"]], c.opponent) for c in among] == \
        [(e["codes"], e["opponent"]) for e in g.read["near_miss_cells"][side]]
    zero = "guard_parked_centre" if side == "guard" else None
    active = {s: ([False] * 4 if s == zero else [True, True, s in ("strike_high", "strike_low"), False])
              for s in spec.players}
    switches = {k: v for k, v in perturbed.SWITCHES.items() if v[0] == side}
    assert len(switches) == (1 if side == "guard" else 3)
    assert eq.systematic_kinds(side) == [eq.BIAS, eq.ROTATE] + list(switches) and eq.RANDOM_KINDS == [eq.NOISE]
    for kind in eq.systematic_kinds(side) + eq.RANDOM_KINDS:
        group = eq.arms(side, kind, g=g, among=among, cfg=cfg, n=4, device="cpu", seed=0, active=active)
        mine = eq.arm_cells(kind, among, side)
        assert len(group) == len(mine)
        for cell, player in zip(mine, group.values()):
            assert isinstance(player, eq.RecordingPlayer)
            for slot, (skill, member) in enumerate(zip(cell.choice["flies"], _members(player, spec.drones))):
                if kind in switches:
                    _, code, moved, keyword = switches[kind]
                    if skill != code:
                        assert type(member) is REGISTRY[skill]      # an unmoved slot flies its script
                        continue
                    assert isinstance(member, perturbed.SwitchRecorder) and type(member.moved) is moved
                    assert getattr(member.moved, keyword if keyword != "margin_m" else "MARGIN_M") == \
                        nm["switch"][kind]
                    continue
                assert isinstance(member, perturbed.CommandPerturbation) and type(member.inner) is REGISTRY[skill]
                if kind == eq.BIAS:
                    assert (member.kind, member.size, member.channels) == ("bias", nm["bias"], perturbed.XY)
                elif kind == eq.ROTATE:
                    assert (member.kind, member.size, member.channels) == ("turn", nm["rotate_deg"], perturbed.XY)
                else:
                    ch = tuple(i for i, a in enumerate(active[skill]) if a)
                    want = ("noise", nm["noise"], ch) if ch else ("scale", 1.0, eq.ALL_CHANNELS)
                    assert (member.kind, member.size, member.channels) == want
                    first = 0 if len(set(cell.choice["flies"])) == 1 else slot
                    assert member.seed == g.read["noise_seed"] + cell.index * spec.drones + first
        if kind in switches:
            assert mine and all(switches[kind][1] in c.choice["flies"] for c in mine)
            assert len(mine) == sum(switches[kind][1] in c.choice["flies"] for c in among)
        else:
            assert mine == among


# ================================================================================================ the permuted scripts
@pytest.mark.parametrize("side", SIDES)
def test_the_permuted_scripts_miss_from_t44_alone(g, stand_in, ref, side):
    """C3 from T44 alone: cell (k, opp) of the permuted scripts is T44's cell (perm[k], opp), its reference T44's cell
    (k, opp); on the STAND_IN limits at least the STAND_IN count of cells miss."""
    spec, perm = g.specs[side], list(g.cells["permutation"][side])
    opps = cells.gated_opponents(g.skills_gates, side)
    rows = eq.permuted_from_t44(ref, distil.VARIANT, spec, perm, ref.games, opps)
    assert [(r["code"], r["opponent"]) for r in rows] == [(c, o) for o in opps for c in spec.players]
    for r in rows:
        k = spec.players.index(r["code"])
        assert r["flies"] == spec.players[perm[k]]
        want = ref.cell(distil.VARIANT, *cells.cell_of(side, spec.players[perm[k]], r["opponent"]))
        base = ref.cell(distil.VARIANT, *cells.cell_of(side, r["code"], r["opponent"]))
        for key in ("outcome", "end_step"):
            assert np.array_equal(r["arm"][key], np.asarray(want[key])[:ref.games])
            assert np.array_equal(r["ref"][key], np.asarray(base[key])[:ref.games])
    m = cells.gated_m(spec, g.cells, g.skills_gates)
    read = eq.interval_step({i: r["arm"] for i, r in enumerate(rows)}, {i: r["ref"] for i, r in enumerate(rows)},
                            {i: cells.FIXED for i in range(len(rows))}, side, stand_in.read["alpha"], m)
    ctl = eq.gross_control(list(read["cells"].values()), stand_in.limits, stand_in.controls, "permuted_min_miss_cells")
    assert ctl["status"] == eq.PASS, ctl


# ================================================================================================ path distance
def test_path_distance_excludes_ended_games_and_absent_drones():
    times = (1, 3, 10)
    n, m = 4, 3
    pos_a = np.zeros((n, m, len(times), 3), dtype=np.float32)
    pos_b = np.zeros_like(pos_a)
    alive = np.ones((n, m, len(times)), dtype=bool)
    pos_b[0, 0, 0, 0] = 3.0                         # game 0: one drone 3 m apart at 1 s
    pos_b[1, 1, 0, 1] = 4.0                         # game 1: 4 m apart at 1 s
    pos_b[2, 2, 0, 2] = 100.0                       # game 2: 100 m apart, but that drone is out in arm b
    alive_b = alive.copy()
    alive_b[2, 2, 0] = False
    alive_a = alive.copy()
    alive_a[:, :, 2] = False                        # every game ended before 10 s in arm a
    alive_a[3, :, 1] = False                        # game 3 ended before 3 s
    pos_b[3, 0, 1, 0] = 50.0                        # ignored: game 3 has ended
    out = eq.path_distance(pos_a, pos_b, alive_a, alive_b, path_times_s=times)
    assert set(out) == {"1", "3", "10"}
    assert out["10"] is None
    assert out["3"] == {"games": 3, "median_m": 0.0, "p90_m": 0.0, "max_m": 0.0}
    one = out["1"]
    assert one["games"] == 4 and one["max_m"] == 4.0 and one["median_m"] == 1.5
    assert math.isclose(one["p90_m"], float(np.percentile([3.0, 4.0, 0.0, 0.0], eq.PATH_PCT)))


# ================================================================================================ the verdict
def test_verdict_reads_controls_first():
    good = {"ctl_a": {"status": eq.PASS, "detail": ""}, "ctl_b": {"status": eq.PASS, "detail": ""}}
    assert eq.verdict(good, [], []) == eq.DISTILLED
    assert eq.verdict(good, ["cell_margin: x"], []) == eq.NOT_DISTILLED
    for status in (eq.FAIL, eq.NOT_RUN, eq.NONFINITE):
        bad = {**good, "ctl_b": {"status": status, "detail": "", "phase": "controls"}}
        assert eq.verdict(bad, [], []) == eq.INCONCLUSIVE
        assert eq.verdict(bad, ["cell_margin: x"], []) == eq.INCONCLUSIVE        # controls first
    with pytest.raises(ValueError):
        eq.verdict({"ctl_a": {"status": "MAYBE", "detail": ""}}, [], [])
    with pytest.raises(ValueError):
        eq.verdict({}, [], [])
    with pytest.raises(ValueError):
        eq.verdict(good, eq.NOT_RUN, [])          # a run of record never has failures NOT_RUN


def _pass_case(limits: dict) -> dict:
    """A synthetic result that meets every limit of ``limits`` with room (each value a limit times 1 - EPS)."""
    lo = 1 - EPS
    cell = {"codes": ["a", "a", "a"], "opponent": "o", "flips": 0, "ci": [-limits["cell_margin"] * lo,
                                                                         limits["cell_margin"] * lo],
            "end_time": {"mean_abs_ticks": limits["end_time_max_ticks"] * lo}}
    pooled = {"ci": [-limits["pooled_margin"] * lo, limits["pooled_margin"] * lo]}
    errors = {"skills": {"a": {"rmse": [limits["cmd_rmse_max"] * lo] * 2 + [0.0, 0.0], "active": [True, True, False,
                                                                                                    False],
                               "max_abs": [limits["cmd_rmse_max"], limits["cmd_rmse_max"],
                                           limits["cmd_unused_max_abs"] * lo, 0.0], "rows": 10},
                         "z": {"rmse": [0.0] * 4, "active": [False] * 4,
                               "max_abs": [limits["cmd_zero_skill_max_abs"] * lo, 0.0, 0.0, 0.0], "rows": 10}},
              "zero_skill": "z"}
    return {"cells": [cell], "pooled": pooled, "errors": errors}


def _edits(limits: dict, factor: float) -> dict:
    """Per limit key, an edit of the pass case that puts its value at limit x ``factor`` (counts: + 1 or exactly)."""
    def set_rmse(c, v):
        c["errors"]["skills"]["a"]["rmse"][0] = v

    def set_unused(c, v):
        c["errors"]["skills"]["a"]["max_abs"][2] = v

    def set_zero(c, v):
        c["errors"]["skills"]["z"]["max_abs"][0] = v

    def set_flips(c, v):
        c["cells"][0]["flips"] = v

    def set_cell(c, v):
        c["cells"][0]["ci"] = [-v, 0.0]

    def set_pooled(c, v):
        c["pooled"]["ci"] = [0.0, v]

    def set_end(c, v):
        c["cells"][0]["end_time"]["mean_abs_ticks"] = v

    flips = limits["flips_max_games"] + (1 if factor > 1 else 0)
    return {"cmd_rmse_max": (set_rmse, limits["cmd_rmse_max"] * factor),
            "cmd_unused_max_abs": (set_unused, limits["cmd_unused_max_abs"] * factor),
            "cmd_zero_skill_max_abs": (set_zero, limits["cmd_zero_skill_max_abs"] * factor),
            "flips_max_games": (set_flips, flips),
            "cell_margin": (set_cell, limits["cell_margin"] * factor),
            "pooled_margin": (set_pooled, limits["pooled_margin"] * factor),
            "end_time_max_ticks": (set_end, limits["end_time_max_ticks"] * factor)}


def _run(case: dict, limits: dict) -> list[str]:
    return eq.limit_failures(case["cells"], case["pooled"], case["errors"], limits)


def _the_rule_reaches_every_key(gates) -> None:
    """Every limit and control-size key of ``gates`` (loaded, filled), read from it, just crossed in a synthetic result
    gives a failure naming it, just met gives none; no number typed (constraint 5)."""
    import copy
    limits = gates.limits
    assert _run(_pass_case(limits), limits) == []
    keys = [k for k in distil.LIMIT_KEYS if k != distil.LIMIT_BOOL]
    for factor, fails in ((1 + EPS, True), (1.0, False)):
        edits = _edits(limits, factor)
        assert set(edits) == set(keys)
        for key, (edit, value) in edits.items():
            case = copy.deepcopy(_pass_case(limits))
            edit(case, value)
            got = _run(case, limits)
            named = [f for f in got if key in f]
            if key == "end_time_max_ticks" and not limits["end_time_gated"]:
                assert got == [], (key, got)
                continue
            assert (named != [] and len(got) == len(named)) if fails else got == [], (key, factor, got)
            if fails:
                assert eq.verdict({"c": {"status": eq.PASS, "detail": ""}}, got, []) == eq.NOT_DISTILLED
    # end_time_gated off: the end time is reported, never gated
    off = {**limits, "end_time_gated": False}
    case = _pass_case(off)
    case["cells"][0]["end_time"]["mean_abs_ticks"] = off["end_time_max_ticks"] * (1 + EPS)
    assert _run(case, off) == []
    # the control sizes: C3 to C5 need at least the count of missing cells
    miss = _pass_case(limits)["cells"][0] | {"flips": limits["flips_max_games"] + 1}
    for key in distil.COUNT_KEYS:
        need = int(gates.controls[key])
        assert eq.gross_control([miss] * need, limits, gates.controls, key)["status"] == eq.PASS
        assert eq.gross_control([miss] * (need - 1) + [_pass_case(limits)["cells"][0]], limits, gates.controls,
                                key)["status"] == eq.FAIL
    # the near-miss sizes are the arms' own values
    for kind in eq.NEAR_MISS_KEYS:
        assert eq.near_miss_value(gates, kind) == distil._owner_value(gates.controls, eq.NEAR_MISS_KEYS[kind])


def test_each_limit_just_crossed_gives_not_distilled(stand_in):
    """Constraint 5: the STAND_IN values, through a synthetic gate file under tmp_path, never the committed file."""
    assert stand_in.limits == h.STAND_IN["limits"] and distil.unfilled_limits(stand_in) == []
    _the_rule_reaches_every_key(stand_in)


def test_a_missing_value_is_a_failure_not_a_pass(stand_in):
    limits = stand_in.limits
    case = _pass_case(limits)
    case["cells"][0]["ci"] = None
    assert [f for f in _run(case, limits) if "cell_margin" in f]
    case = _pass_case(limits)
    case["pooled"] = None
    assert [f for f in _run(case, limits) if "pooled_margin" in f]
    case = _pass_case(limits)
    case["errors"]["skills"]["a"]["rmse"] = None
    assert [f for f in _run(case, limits) if "cmd_rmse_max" in f]
    case = _pass_case(limits)
    case["cells"][0]["end_time"] = None
    assert [f for f in _run(case, limits) if "end_time_max_ticks" in f]


def test_a_fill_limit_never_reaches_a_comparison(g, stand_in):
    """A FILL_ limit or control size raises before any comparison; the verdict of a smoke with FILL_ values is NOT_RUN,
    never DISTILLED or NOT DISTILLED."""
    assert g.limits["end_time_gated"].startswith("FILL_")          # the committed file today
    case = _pass_case(stand_in.limits)
    for key in distil.LIMIT_KEYS:
        limits = {**stand_in.limits, key: "FILL_OWNER_R38"}
        with pytest.raises(ValueError, match=key):
            _run(case, limits)
        with pytest.raises(ValueError, match=key):
            eq.gross_control(case["cells"], limits, stand_in.controls, "permuted_min_miss_cells")
        for kind in eq.systematic_kinds("strike") + eq.RANDOM_KINDS:
            with pytest.raises(ValueError, match=key):
                eq.near_miss_control(kind, case["cells"], case["pooled"], case["errors"], limits)
    for key in distil.COUNT_KEYS:
        controls = {**stand_in.controls, key: "FILL_OWNER_R38"}
        with pytest.raises(ValueError, match=key):
            eq.gross_control(case["cells"], stand_in.limits, controls, key)
    with pytest.raises(ValueError, match="near_miss"):
        eq.near_miss_value(g, eq.BIAS)
    with pytest.raises(ValueError, match="near_miss"):
        eq.arms("strike", "flank_margin_m", g=g, among=eq.near_miss_cells(g, "strike"), cfg=_cfg(g), n=4,
                device="cpu", seed=0)
    good = {"c": {"status": eq.PASS, "detail": ""}}
    unfilled = distil.unfilled_limits(g)
    assert unfilled
    for failures in ([], ["cell_margin: x"], eq.NOT_RUN):
        assert eq.verdict(good, failures, unfilled) == eq.NOT_RUN


def test_the_near_miss_judgments(stand_in):
    """C6 PASSES when the systematic arm fails the limits; C7 PASSES when the random arm meets them."""
    limits = stand_in.limits
    ok = _pass_case(limits)
    bad = _pass_case(limits)
    bad["cells"][0]["flips"] = limits["flips_max_games"] + 1
    for kind in eq.systematic_kinds("strike"):
        assert eq.near_miss_control(kind, bad["cells"], bad["pooled"], bad["errors"], limits)["status"] == eq.PASS
        assert eq.near_miss_control(kind, ok["cells"], ok["pooled"], ok["errors"], limits)["status"] == eq.FAIL
    assert eq.near_miss_control(eq.NOISE, ok["cells"], ok["pooled"], ok["errors"], limits)["status"] == eq.PASS
    assert eq.near_miss_control(eq.NOISE, bad["cells"], bad["pooled"], bad["errors"], limits)["status"] == eq.FAIL


def test_stand_in_mirrors_no_limit(g):
    """Constraint 5, R2 B8: no typed PROPOSED value; every float of STAND_IN is off the 0.001 grid, they differ from each
    other and from every filled number of the committed [limits] and [controls]."""
    def floats(node):
        if isinstance(node, dict):
            return [x for v in node.values() for x in floats(v)]
        return [node] if isinstance(node, float) else []

    def numbers(node):
        if isinstance(node, dict):
            return [x for v in node.values() for x in numbers(v)]
        return [node] if isinstance(node, (int, float)) and not isinstance(node, bool) else []

    mine = floats(h.STAND_IN)
    assert mine and len(set(mine)) == len(mine)
    for v in mine:
        assert not math.isclose(v * 1000, round(v * 1000), abs_tol=1e-9), v
    committed = numbers(g.limits) + numbers(g.controls)
    assert not set(mine) & set(committed)


def test_the_committed_limits_run_through_the_rule(g):
    """Constraint 5, R2 RC-2, OA-4: the owner's own numbers, once filled, each reach the rule (the body runs un-skipped
    on the STAND_IN file in test_each_limit_just_crossed_gives_not_distilled)."""
    unfilled = distil.unfilled_limits(g)
    if unfilled:
        pytest.skip(f"R38: the owner's keys of configs/ste_ls1/distil_gates.toml are still FILL_ ({', '.join(unfilled)}); "
                    f"the one designed skip of M2 until lead step 3 fills the file")
    _the_rule_reaches_every_key(g)


# ================================================================================================ the interval step
def _games(side, both, b, c, neither):
    w, lo = (GUARD_WIN, STRIKE_WIN) if side == "guard" else (STRIKE_WIN, GUARD_WIN)
    arm = np.array([w] * both + [lo] * b + [w] * c + [lo] * neither, dtype=np.int8)
    ref = np.array([w] * both + [w] * b + [lo] * c + [lo] * neither, dtype=np.int8)
    end = np.arange(arm.size, dtype=np.int16) + 1
    return {"outcome": arm, "end_step": end}, {"outcome": ref, "end_step": end}


@pytest.mark.parametrize("side", SIDES)
def test_a_cell_inside_the_margin_at_plain_alpha_but_outside_at_the_adjusted_z_is_not_distilled(g, stand_in, side):
    """R2 RC-1: per-cell intervals at adjusted_z(alpha, m), m the side's gated cells of the committed layout; the pooled
    row at plain alpha. b = c, n chosen (searched, not typed) so the plain-alpha interval lies inside +-cell_margin
    and the adjusted one does not."""
    limits, alpha = stand_in.limits, stand_in.read["alpha"]
    margin = limits["cell_margin"]
    m = cells.gated_m(g.specs[side], g.cells, g.skills_gates)
    z_plain, z_cell = cells.adjusted_z(alpha, 1), cells.adjusted_z(alpha, m)
    n = 4000
    found = []
    for k in range(1, n // 4):
        both = n // 2 - k
        plain, _ = cells.newcombe_interval(both, k, k, n - both - 2 * k, z_plain)
        adj, _ = cells.newcombe_interval(both, k, k, n - both - 2 * k, z_cell)
        if -margin <= plain[0] and plain[1] <= margin and (adj[0] < -margin or adj[1] > margin):
            found.append(k)
    assert found
    k = found[len(found) // 2]
    arm, ref = _games(side, n // 2 - k, k, k, n // 2 - k)
    read = eq.interval_step({"x": arm}, {"x": ref}, {"x": cells.FIXED}, side, alpha, m)
    entry = read["cells"]["x"]
    assert read["intervals"]["z_cell"] == z_cell and read["intervals"]["z_pooled"] == z_plain
    assert read["intervals"]["m"] == {side: m} and read["intervals"]["alpha"] == alpha
    assert entry["ci"] == cells.paired_cell(arm, ref, side, z_cell)["ci"]
    assert entry["b"] == entry["c"] == k and entry["n"] == n and entry["end_time"]["differ_games"] == 0
    assert -margin <= cells.paired_cell(arm, ref, side, z_plain)["ci"][0]          # inside at plain alpha
    assert read["pooled"]["all"]["ci"] == cells.pooled_difference(
        {"x": arm["outcome"] == (GUARD_WIN if side == "guard" else STRIKE_WIN)},
        {"x": ref["outcome"] == (GUARD_WIN if side == "guard" else STRIKE_WIN)}, z_plain)["ci"]
    assert read["pooled"]["mixed"] is None
    clean = _pass_case(limits)
    lenient = {**limits, "flips_max_games": 2 * k}                 # isolate the margin (flips just met)
    failures = eq.limit_failures([entry], {"ci": [0.0, 0.0]}, clean["errors"], lenient)
    assert failures and all("cell_margin" in f for f in failures)
    assert eq.verdict({"c": {"status": eq.PASS, "detail": ""}}, failures, []) == eq.NOT_DISTILLED
    plain_read = eq.interval_step({"x": arm}, {"x": ref}, {"x": cells.FIXED}, side, alpha, 1)
    assert eq.limit_failures([plain_read["cells"]["x"]], {"ci": [0.0, 0.0]}, clean["errors"], lenient) == []


# ================================================================================================ the read (task LS1-M2-T6)
# Tiny reads on the CPU: the Guard team, one or two opponents (the first is the side's near-miss opponent, so the
# near-miss cells are played), no mixed combination of the gated cells (the near-miss mixed cell is still played: the
# scripted arms always hold the near-miss cells), [smoke] read_games starts (24) unless --games says fewer. The network
# is a tiny one whose meta and fit_report.json name the gate file read (tests/_ste_ls1.read_net): the read's checks,
# controls and files are under test, not a fit.
READ_SIDE = "guard"
READ_OPPONENT = "strike_straight"          # the Guard team's near-miss opponent (distil_gates.toml [read])
READ_MIXED = 1                             # the FILL_ read plays one gated mixed combination (R1 on a mixed cell)
STRIKE_GATED_OPPONENT = "guard_field"      # the Strike team's read test: an opponent whose games end soon (T44: <= 81 ticks)
VERDICT_WORDS = (eq.DISTILLED, eq.NOT_DISTILLED, eq.INCONCLUSIVE)


def _read_argv(gates_file, net, run_dir, side=READ_SIDE, opponents=(READ_OPPONENT,), mixed=0, games=None, smoke=True,
               extra=()):
    argv = ["--gates", str(gates_file), "--side", side, "--skill-net", str(net), "--run-dir", str(run_dir),
            "--cap-h", "1", "--opponents", *opponents, "--mixed", str(mixed)]
    if games is not None:
        argv += ["--games", str(games)]
    if smoke:
        argv.append("--smoke")
    return argv + list(extra)


def _launch(argv) -> tuple[int, list[str]]:
    """eq.main in this process (the hidden stop flag signals this process; RunGuard's handler takes it); stdout lines."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = eq.main(argv)
    return code, buf.getvalue().splitlines()


def _files(run_dir):
    return {p.name: p.stat().st_mtime_ns for p in sorted((run_dir / eq.GAMES_DIR).glob("*.npz"))}


def _json(path):
    return json.loads(path.read_text())


@pytest.fixture(scope="module")
def fill_read(tmp_path_factory):
    """The committed gate file (the owner's keys FILL_) under --smoke: a first launch stopped (hidden flag) after the
    last control batch, then the same command to the end. Returns the snapshot between the two and the end state."""
    tmp = tmp_path_factory.mktemp("fill_read")
    net, net_sha = h.read_net(tmp / "net", READ_SIDE, h.DISTIL_GATES)
    run_dir = tmp / "run"
    last_control = eq.batch_name(eq.STAGE_C5, f"{READ_OPPONENT}_00")
    first, first_lines = _launch(_read_argv(h.DISTIL_GATES, net, run_dir, mixed=READ_MIXED,
                                            extra=("--stop-after-batch", last_control)))
    snap = {"code": first, "lines": first_lines, "files": _files(run_dir),
            "controls": _json(run_dir / eq.CONTROLS_FILE), "results": (run_dir / eq.RESULTS).exists()}
    code, lines = _launch(_read_argv(h.DISTIL_GATES, net, run_dir, mixed=READ_MIXED))
    return {"snap": snap, "code": code, "lines": lines, "run_dir": run_dir, "net": net, "net_sha": net_sha,
            "last_control": last_control}


def test_controls_are_written_before_any_result_batch(g, fill_read):
    """Every control (C1 to C7) is in controls.json before the first R1 batch is played; a stop after the last control
    batch is the contract's own stop (exit 4) and writes no results.json."""
    snap = fill_read["snap"]
    assert snap["code"] == EXIT_INTERRUPTED and not snap["results"]
    assert set(eq.control_names(READ_SIDE)) <= set(snap["controls"])
    assert f"{fill_read['last_control']}.npz" in snap["files"]
    assert not [f for f in snap["files"] if f.startswith(eq.STAGE_R1)]
    for name in eq.control_names(READ_SIDE):
        assert snap["controls"][name]["status"] in eq.STATUSES


def test_resume_skips_done_batches(fill_read):
    """The same command resumes at the first batch not done: every batch file of the first launch is untouched (mtime),
    and the result batches are played."""
    assert fill_read["code"] == EXIT_DONE
    now = _files(fill_read["run_dir"])
    for name, mtime in fill_read["snap"]["files"].items():
        assert now[name] == mtime, name
    assert [f for f in now if f.startswith(eq.STAGE_R1)]


def test_a_resumed_read_writes_the_uninterrupted_reads_results(tmp_path, fill_read):
    """results.json is built from the batch files only: the stopped and resumed read gives the very file of a read run
    through in one launch (same network, same command)."""
    net, _ = h.read_net(tmp_path / "net", READ_SIDE, h.DISTIL_GATES)
    whole = tmp_path / "whole"
    assert _launch(_read_argv(h.DISTIL_GATES, net, whole, mixed=READ_MIXED))[0] == EXIT_DONE
    assert (whole / eq.RESULTS).read_bytes() == (fill_read["run_dir"] / eq.RESULTS).read_bytes()


def test_the_strike_read_plays_the_info_cells_beside_the_scripts(g, tmp_path):
    """R2 (INFO): the Strike team's cells against cells.toml [info_opponents] (guard_mark_inside, no T44 cell) are
    played by the scripted arm and then the network, paired with each other; they are in results' cells as kind info,
    not in the pooled rows or m, and no limit reads them."""
    net, _ = h.read_net(tmp_path / "net", "strike", h.DISTIL_GATES)
    info = g.cells["info_opponents"]["strike"]
    run_dir = tmp_path / "run"
    code, lines = _launch(_read_argv(h.DISTIL_GATES, net, run_dir, side="strike", games=2,
                                     opponents=(STRIKE_GATED_OPPONENT, *info)))
    assert code == EXIT_DONE and lines[-1] == eq.NOT_RUN
    res = _json(run_dir / eq.RESULTS)
    stages = {eq.stage_of(b["name"]) for b in _json(run_dir / eq.LAYOUT_FILE)["batches"]}
    assert {eq.STAGE_R2S, eq.STAGE_R2N} <= stages
    rows = [c for c in res["cells"] if c["kind"] == cells.INFO]
    assert rows and {c["arm"] for c in rows} == {eq.NET} and {c["opponent"] for c in rows} == set(info)
    gated = [c for c in res["cells"] if c["arm"] == eq.NET and c["kind"] != cells.INFO]
    assert res["pooled"]["all"]["cells"] == len(gated)
    assert res["intervals"]["m"] == {"strike": cells.gated_m(g.specs["strike"], g.cells, g.skills_gates)}


def test_a_filled_read_past_its_controls_reads_the_network_through_the_rule(tmp_path, monkeypatch):
    """The R1 path with the owner's keys filled (STAND_IN, synthetic): with C3 to C7 forced to PASS (24 starts cannot
    meet the STAND_IN margins; the controls' own arithmetic is tested above), the network's gated cells, the pooled row
    and R1's command-error table go through limit_failures; each failure names a [limits] key and the verdict is the
    rule's (verdict(controls, failures, [])), exit 0."""
    gates = h.write_distil_gates(tmp_path)
    net, _ = h.read_net(tmp_path / "net", READ_SIDE, gates)
    forced = {"status": eq.PASS, "detail": "forced by the test"}
    monkeypatch.setattr(eq, "gross_control", lambda *a, **k: dict(forced))
    monkeypatch.setattr(eq, "near_miss_control", lambda *a, **k: dict(forced))
    run_dir = tmp_path / "run"
    code, lines = _launch(_read_argv(gates, net, run_dir, games=8))
    res = _json(run_dir / eq.RESULTS)
    assert code == EXIT_DONE and lines[-1] == res["verdict"] in (eq.DISTILLED, eq.NOT_DISTILLED)
    assert isinstance(res["failures"], list)
    assert all(f.split(":")[0] in distil.LIMIT_KEYS for f in res["failures"])
    gated = [c for c in res["cells"] if c["arm"] == eq.NET and c["kind"] != cells.INFO]
    limits = distil.load_distil_gates(gates).limits
    assert res["failures"] == eq.limit_failures(gated, res["pooled"]["all"], res["errors"], limits)
    assert res["verdict"] == eq.verdict(res["controls"], res["failures"], [])
    skills_seen = {s for s, e in res["errors"]["skills"].items() if e["rows"]}
    assert skills_seen == set(distil.load_distil_gates(gates).specs[READ_SIDE].players)
    assert all(set(e["rmse_by_n_live"]) == {"1", "2", "3"} for e in res["errors"]["skills"].values())


def test_a_smoke_on_24_starts_ends_with_not_run_and_per_game_arrays(g, fill_read):
    """F1: with the owner's keys FILL_, C3 to C7, the failures and the verdict are NOT_RUN; C1, C1m and C2 PASS; no
    DISTILLED or NOT DISTILLED anywhere; results.json has exactly the file table's keys (complete last); each batch file
    holds the per-game arrays (save_batch's, pos_at, alive_at, and pair_class on an arm batch)."""
    run_dir = fill_read["run_dir"]
    assert fill_read["lines"][-1] == eq.NOT_RUN
    res = _json(run_dir / eq.RESULTS)
    assert list(res) == list(eq.RESULT_KEYS) and res["complete"] is True
    assert res["verdict"] == eq.NOT_RUN and res["failures"] == eq.NOT_RUN and res["of_record"] is False
    assert res["net_sha256"] == fill_read["net_sha"] and res["gates_sha256"] == g.sha256
    named = eq.control_names(READ_SIDE)
    for name in named:
        want = eq.PASS if name in (eq.CTL_C1, eq.CTL_C1M, eq.CTL_C2) else eq.NOT_RUN
        assert res["controls"][name]["status"] == want, (name, res["controls"][name])
    assert res["controls"] == _json(run_dir / eq.CONTROLS_FILE)
    text = "\n".join([(run_dir / eq.RESULTS).read_text(), (run_dir / eq.RESULTS_MD).read_text(),
                      (run_dir / eq.CONTROLS_FILE).read_text()] + fill_read["lines"] + fill_read["snap"]["lines"])
    assert eq.DISTILLED not in text                              # NOT DISTILLED contains it too
    drones, marks = g.specs[READ_SIDE].drones, len(g.read["path_times_s"])
    assert res["cells"] and all(set(c) == set(eq.CELL_KEYS) for c in res["cells"])
    assert {c["n"] for c in res["cells"]} == {g.smoke["read_games"]}
    for batch in _json(run_dir / eq.LAYOUT_FILE)["batches"]:
        pg = scoring.load_batch(run_dir / eq.GAMES_DIR / f"{batch['name']}.npz")
        games = len(batch["cells"]) * batch["n"]
        assert pg["pos_at"].shape == (games, drones, marks, 3) and pg["pos_at"].dtype == np.float32
        assert pg["alive_at"].shape == (games, drones, marks) and pg["alive_at"].dtype == bool
        assert set(exploit.PER_GAME) <= set(pg) and pg["outcome"].shape == (games,)
        if batch["arm"] == eq.SCRIPTS:
            assert "pair_class" not in pg
        else:
            assert pg["pair_class"].shape == (games,) and pg["pair_class"].dtype == np.int8
            assert set(np.unique(pg["pair_class"])) <= {eq.PAIR_SAME, eq.PAIR_B, eq.PAIR_C}


def test_layout_names_every_batch_and_cell(g, ref, fill_read):
    """layout.json lists every batch in play order with its cells (index, arm, codes, opponent, player) and how it was
    played (device, seed, tick cap, hold, n, the gate file's and, for the network's own arms, the network's sha256)."""
    run_dir = fill_read["run_dir"]
    layout = _json(run_dir / eq.LAYOUT_FILE)
    assert list(layout) == ["batches"]
    names = [b["name"] for b in layout["batches"]]
    assert sorted(f"{n}.npz" for n in names) == sorted(_files(run_dir)) and len(set(names)) == len(names)
    stages = [eq.stage_of(n) for n in names]
    assert stages == sorted(stages, key=eq.STAGES.index)          # play order
    sg = g.skills_gates
    for b in layout["batches"]:
        assert set(b) == set(eq.LAYOUT_BATCH_KEYS), b
        assert (b["side"], b["device"], b["seed"], b["ticks_cap"], b["hold_ticks"], b["n"], b["gates_sha256"]) == (
            READ_SIDE, g.read["device"], int(ref.meta["seed"]), int(sg.run["ticks_cap"]), eq.HOLD_TICKS,
            g.smoke["read_games"], g.sha256)
        assert b["net_sha256"] == (fill_read["net_sha"] if b["arm"] in (eq.NET, eq.PERMUTED) else None)
        assert isinstance(b["seconds"], float) and b["seconds"] > 0
        assert b["cells"] and all(set(c) == set(eq.LAYOUT_CELL_KEYS) for c in b["cells"])
        assert {c["arm"] for c in b["cells"]} == {b["arm"]}
        assert {c["opponent"] for c in b["cells"]} == {READ_OPPONENT}
        assert all(c["player"].startswith(cells.PREFIXES) for c in b["cells"])


def test_the_batch_file_serves_the_replay_check(g, fill_read):
    """R2 CA-4: a batch file holds start_pos_m [G, M, 3] (both teams) and every replay3d.EXACT_KEYS key, and the replay
    check of the batch against itself passes."""
    run_dir = fill_read["run_dir"]
    guards, strikes = g.specs["guard"].drones, g.specs["strike"].drones
    for path in sorted((run_dir / eq.GAMES_DIR).glob("*.npz")):
        pg = scoring.load_batch(path)
        assert pg["start_pos_m"].shape == (len(pg["outcome"]), guards + strikes, 3)
        assert set(replay3d.EXACT_KEYS) <= set(pg)
        assert replay3d.check_against_record(pg, pg)["equal"]


def _reference_slices(run_dir):
    """{(codes, opponent): the scripted arm's per-game record of that cell} from layout.json and the batch files."""
    out = {}
    for b in _json(run_dir / eq.LAYOUT_FILE)["batches"]:
        if b["arm"] != eq.SCRIPTS:
            continue
        pg = scoring.load_batch(run_dir / eq.GAMES_DIR / f"{b['name']}.npz")
        for i, c in enumerate(b["cells"]):
            out[(tuple(c["codes"]), c["opponent"])] = exploit.slice_cell(pg, i, b["n"])
    return out


def test_the_intervals_use_the_adjusted_z(g, fill_read):
    """R2 RC-1: every stored cell ci is paired_cell at results' z_cell, z_cell = adjusted_z(alpha, m) with m the side's
    gated cells of the committed layout; the pooled ci at z_pooled = adjusted_z(alpha, 1)."""
    run_dir = fill_read["run_dir"]
    res = _json(run_dir / eq.RESULTS)
    iv = res["intervals"]
    m = cells.gated_m(g.specs[READ_SIDE], g.cells, g.skills_gates)
    alpha = g.read["alpha"]
    assert iv["m"] == {READ_SIDE: m} and iv["alpha"] == alpha
    assert iv["z_cell"] == cells.adjusted_z(alpha, m) and iv["z_pooled"] == cells.adjusted_z(alpha, 1)
    assert (iv["interval"], iv["correction"]) == (g.read["interval"], g.read["correction"])
    refs = _reference_slices(run_dir)
    arm_wins, ref_wins = {}, {}
    for c in res["cells"]:
        with np.load(run_dir / c["games"]["file"]) as z:
            mine = {k: z[k][c["games"]["start"]:c["games"]["stop"]] for k in ("outcome", "end_step")}
        base = refs[(tuple(c["codes"]), c["opponent"])]
        want = cells.paired_cell(mine, base, READ_SIDE, iv["z_cell"])
        assert (c["b"], c["c"], c["n"], c["ci"]) == (want["b"], want["c"], want["n"], want["ci"]), c
        if c["arm"] == eq.NET and c["kind"] in (cells.FIXED, cells.MIXED):
            key = (tuple(c["codes"]), c["opponent"])
            arm_wins[key], ref_wins[key] = eq._wins(mine, READ_SIDE), eq._wins(base, READ_SIDE)
    assert arm_wins
    assert res["pooled"]["all"] == cells.pooled_difference(arm_wins, ref_wins, iv["z_pooled"])
    assert res["pooled"]["mixed"] is not None and res["pooled"]["mixed"]["cells"] == READ_MIXED


def test_a_smoke_with_stand_in_limits_ends_with_a_verdict_word(tmp_path):
    """Constraint 5 (design check of M2): a smoke on a gate file filled from STAND_IN judges the controls and writes a
    verdict word (which one depends on 24 starts and a tiny network, so it is not asserted): the last line, results'
    verdict and the exit agree, no control is NOT_RUN, the failures are a list."""
    gates = h.write_distil_gates(tmp_path)
    net, _ = h.read_net(tmp_path / "net", READ_SIDE, gates)
    opps = cells.gated_opponents(distil.load_distil_gates(gates).skills_gates, READ_SIDE)
    second = next(o for o in opps if o != READ_OPPONENT)
    run_dir = tmp_path / "run"
    code, lines = _launch(_read_argv(gates, net, run_dir, opponents=(READ_OPPONENT, second)))
    res = _json(run_dir / eq.RESULTS)
    assert lines[-1] in VERDICT_WORDS and lines[-1] == res["verdict"]
    assert code == (EXIT_CONTROL_FAILED if res["verdict"] == eq.INCONCLUSIVE else EXIT_DONE)
    assert isinstance(res["failures"], list) and res["of_record"] is False
    assert eq.NOT_RUN not in {v["status"] for v in res["controls"].values()}


class _ChangedOracle(cells.ScriptOracle):
    """The oracle with one command changed: vx moved on every live drone (C2 must catch it)."""

    def forward(self, obs, slot, z, clip=True):
        out = super().forward(obs, slot, z, clip=clip).clone()
        alive = obs[:, skills._V.alive]
        out[:, 0] = (out[:, 0] + 0.5 * alive).clamp(-1, 1)
        return out


def test_a_failed_control_exits_6_and_again_6_on_the_same_folder(tmp_path, monkeypatch):
    """OP-19: a control not PASS writes INCONCLUSIVE (exit 6) and plays no result batch; the same command on the folder
    exits 6 again (terminal)."""
    net, _ = h.read_net(tmp_path / "net", READ_SIDE, h.DISTIL_GATES)
    run_dir = tmp_path / "run"
    argv = _read_argv(h.DISTIL_GATES, net, run_dir, games=4)
    monkeypatch.setattr(cells, "ScriptOracle", _ChangedOracle)
    code, lines = _launch(argv)
    assert code == EXIT_CONTROL_FAILED and lines[-1] == eq.INCONCLUSIVE
    controls = _json(run_dir / eq.CONTROLS_FILE)
    assert controls[eq.CTL_C2]["status"] == eq.FAIL
    res = _json(run_dir / eq.RESULTS)
    assert res["verdict"] == eq.INCONCLUSIVE and res["complete"] is True and eq.CTL_C2 in " ".join(res["reasons"])
    assert not [f for f in _files(run_dir) if f.startswith(eq.STAGE_R1)]
    monkeypatch.undo()
    assert _launch(argv)[0] == EXIT_CONTROL_FAILED


def test_a_net_from_another_gate_file_or_side_is_refused(tmp_path):
    """Exit 2 before anything is written: a network distilled from another gate file, the other side's network, no
    complete fit_report.json beside it or one naming another network or gate file, a smoke network outside --smoke, the
    owner's keys FILL_ outside --smoke, a GPU job."""
    filled = h.write_distil_gates(tmp_path)

    def refused(argv, run_dir):
        assert _launch(argv)[0] == EXIT_REFUSED
        assert not run_dir.exists()

    other, _ = h.read_net(tmp_path / "other", READ_SIDE, filled)
    refused(_read_argv(h.DISTIL_GATES, other, tmp_path / "r1"), tmp_path / "r1")
    strike, _ = h.read_net(tmp_path / "strike", "strike", h.DISTIL_GATES)
    refused(_read_argv(h.DISTIL_GATES, strike, tmp_path / "r2"), tmp_path / "r2")
    good, sha = h.read_net(tmp_path / "good", READ_SIDE, h.DISTIL_GATES)
    h.write_fit_report(good, sha, g_sha := exploit.sha256_file(h.DISTIL_GATES), complete=False)
    refused(_read_argv(h.DISTIL_GATES, good, tmp_path / "r3"), tmp_path / "r3")
    h.write_fit_report(good, "0" * 64, g_sha)
    refused(_read_argv(h.DISTIL_GATES, good, tmp_path / "r4"), tmp_path / "r4")
    h.write_fit_report(good, sha, exploit.sha256_file(filled))
    refused(_read_argv(h.DISTIL_GATES, good, tmp_path / "r5"), tmp_path / "r5")
    (good.parent / "fit_report.json").unlink()
    refused(_read_argv(h.DISTIL_GATES, good, tmp_path / "r6"), tmp_path / "r6")
    mixed_up, mixed_sha = h.read_net(tmp_path / "mixed_up", READ_SIDE, filled)
    h.write_fit_report(mixed_up, mixed_sha, g_sha)                   # the report names this file, the network does not
    refused(_read_argv(h.DISTIL_GATES, mixed_up, tmp_path / "r6b"), tmp_path / "r6b")
    smoke_net, _ = h.read_net(tmp_path / "smoke_net", READ_SIDE, filled, of_record=False)
    refused(_read_argv(filled, smoke_net, tmp_path / "r7", smoke=False), tmp_path / "r7")
    fill_net, _ = h.read_net(tmp_path / "fill_net", READ_SIDE, h.DISTIL_GATES, of_record=True)
    refused(_read_argv(h.DISTIL_GATES, fill_net, tmp_path / "r8", smoke=False), tmp_path / "r8")
    record_net, _ = h.read_net(tmp_path / "record_net", READ_SIDE, filled, of_record=True)
    full = ["--gates", str(filled), "--side", READ_SIDE, "--skill-net", str(record_net), "--run-dir",
            str(tmp_path / "r10"), "--cap-h", "1"]
    ctx, why = eq.prepare(eq.parse(full))                            # the positive case: a read of record would start
    assert why is None and ctx.of_record and ctx.n == ctx.g.cells["read"]["games_per_cell"]
    assert ctx.m == len(ctx.gated) and not (tmp_path / "r10").exists()
    job_dir = tmp_path / "r9"
    job_dir.mkdir()
    (job_dir / "job.json").write_text(json.dumps({"gpu_h": 0.5}))
    assert _launch(_read_argv(h.DISTIL_GATES, fill_net, job_dir))[0] == EXIT_REFUSED
    assert sorted(p.name for p in job_dir.iterdir()) == ["job.json"]
