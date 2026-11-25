"""Route 3, stage LS1, task LS1-M1-T6: changed scripts for the calibration, in their own file
(``opponents/perturbed.py``; plan ste_learning/drafts/LS1_TASK_PLAN.md, M1-T6; ``opponents/scripted.py`` untouched).

* At today's values every changed player is its script bit for bit (``torch.equal``), both teams, live and out rows:
  each wrapper at noise 0, bias 0, scale 1, turn 0, and each moved-switch player at the value ``scripted.py`` holds.
* Each kind does what it says: scale is exactly the factor on the chosen channels; bias adds exactly ``+size`` on the
  chosen channels of live drones (it moves ``guard_parked_centre``'s zero command, a scale or a turn does not); turn
  keeps the norm and turns xy by the angle; noise lies in [-s, s], is zero on out drones, repeats for a seed, changes
  with the seed, and does not depend on the other cells of a batch.
* Each moved value changes the command where it should (hand-built observations), and only there for the sacrifice.
* The command error (wrappers and the switch recorder): per drone slot and channel, live drones of each slot's first
  game only, as tensors read once; zero at today's values.
* One short played cell: an identity wrapper plays its script's games exactly (``exploit.play_cells``, T44's starts).

CPU only."""
import math
import re
from pathlib import Path

import pytest
import torch

from svg_training.core.observations import OBS_DIM, ObsView
from svg_training.core.strategy import SplitStrategy
from svg_training.opponents import perturbed, scripted
from svg_training.opponents.scripted import REGISTRY, make_strategy
from svg_training.ste import exploit, skills

import _ste_ls1 as h

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "source" / "svg_training" / "opponents" / "perturbed.py"
SCRIPTED = ROOT / "source" / "svg_training" / "opponents" / "scripted.py"
SCRIPTED_SHA_PREFIX = "b7ccafdeaa4b01c7"
V = ObsView()
SIDES = ("guard", "strike")
XY = (0, 1)
ALL = (0, 1, 2, 3)
SCALE = 0.95                  # the calibration's PROPOSED scale (plan section 1 table)
TURN_DEG = 3.0                # the calibration's PROPOSED turn
BIAS = 0.05                   # a bias size of the PROPOSED xy ladder
NOISE = 0.1                   # a noise size of the PROPOSED ladder
SEED = 7
TOL = 1e-6


@pytest.fixture(scope="module")
def gates():
    return exploit.load_gates(h.SKILLS_GATES)


@pytest.fixture(scope="module")
def obs_of(gates):
    """{side: (cfg, obs [64, 3, OBS_DIM])}: 40 ticks of scripted play, some drones tagged (``_ste_ls1.team_obs``)."""
    return {side: h.team_obs(gates, side) for side in SIDES}


def _live(obs):
    return obs[..., V.alive] > perturbed.ALIVE_MIN


def _scripts(gates, side, cfg, n):
    return {name: make_strategy(name, side, cfg, n, "cpu", 0) for name in skills.team_skills(gates.players, side)}


def _wrap(inner, kind, size, channels=XY, seed=SEED):
    return perturbed.CommandPerturbation(inner, kind, size, seed, channels)


def _moved(side, cfg, n):
    """[(moved player at today's value, its script's name)] of ``side`` (R2 OA-3: all four are in ``[players]``)."""
    if side == "guard":
        return [(perturbed.FieldMovedRange(side, cfg, n, "cpu", 0, range_m=scripted.FIELD_RANGE_M), "guard_field")]
    return [(perturbed.SacrificeMovedEntry(side, cfg, n, "cpu", 0, entry_half_angle_rad=scripted.ENTRY_HALF_ANGLE_RAD),
             "strike_sacrifice"),
            (perturbed.ConvergeMovedGather(side, cfg, n, "cpu", 0, gather_angle_rad=scripted.GATHER_ANGLE_RAD),
             "strike_converge"),
            (perturbed.FlankMoved(side, cfg, n, "cpu", 0, margin_m=scripted.StrikeFlank.MARGIN_M), "strike_flank")]


# ================================================================================================ identity
@pytest.mark.parametrize("side", SIDES)
def test_at_identity_each_wrapper_is_its_script(gates, obs_of, side):
    """Noise 0, bias 0, scale 1 and turn 0 on every script of the team's ``[players]``: ``torch.equal`` to the
    script on live and out rows; the recorded error is zero, counted on the live drones of each slot."""
    cfg, obs = obs_of[side]
    live = _live(obs)
    assert live.any() and (~live).any()                       # both kinds of row are in the batch
    for name, script in _scripts(gates, side, cfg, obs.shape[0]).items():
        want = script.act(obs)
        for kind, size, ch in (("noise", 0.0, ALL), ("bias", 0.0, ALL), ("scale", 1.0, ALL), ("turn", 0.0, XY)):
            w = _wrap(make_strategy(name, side, cfg, obs.shape[0], "cpu", 0), kind, size, ch)
            assert torch.equal(w.act(obs), want), (name, kind)
            e = w.errors()
            assert torch.equal(e["count"], live.sum(0)), (name, kind)
            assert e["sum_sq"].abs().sum() == 0 and e["max_abs"].abs().sum() == 0, (name, kind)


@pytest.mark.parametrize("side", SIDES)
def test_at_todays_values_each_moved_player_is_its_script(gates, obs_of, side):
    """Each moved-switch player at the value scripted.py holds is its script bit for bit, and the switch recorder
    (moved against the original script) records zero error."""
    cfg, obs = obs_of[side]
    n = obs.shape[0]
    for moved, name in _moved(side, cfg, n):
        want = make_strategy(name, side, cfg, n, "cpu", 0).act(obs)
        assert torch.equal(moved.act(obs), want), name
        assert isinstance(moved, type(make_strategy(name, side, cfg, n, "cpu", 0))), name     # subclasses its script
        rec = perturbed.SwitchRecorder(moved, make_strategy(name, side, cfg, n, "cpu", 0))
        assert torch.equal(rec.act(obs), want) and rec.team == side
        e = rec.errors()
        assert e["sum_sq"].abs().sum() == 0 and e["max_abs"].abs().sum() == 0
        assert torch.equal(e["count"], _live(obs).sum(0))


def test_the_moved_players_refuse_the_other_team(gates, obs_of):
    cfg, _ = obs_of["guard"]
    with pytest.raises(ValueError):
        perturbed.FieldMovedRange("strike", cfg, 4, "cpu", 0, range_m=scripted.FIELD_RANGE_M)
    with pytest.raises(ValueError):
        perturbed.SacrificeMovedEntry("guard", cfg, 4, "cpu", 0, entry_half_angle_rad=scripted.ENTRY_HALF_ANGLE_RAD)
    with pytest.raises(ValueError):
        perturbed.SwitchRecorder(make_strategy("guard_field", "guard", cfg, 4, "cpu", 0),
                                 make_strategy("strike_flank", "strike", cfg, 4, "cpu", 0))


# ================================================================================================ each kind
@pytest.mark.parametrize("side", SIDES)
def test_scale_is_exactly_the_factor_on_the_chosen_channels(gates, obs_of, side):
    cfg, obs = obs_of[side]
    for name, script in _scripts(gates, side, cfg, obs.shape[0]).items():
        want = script.act(obs)
        got = _wrap(script, "scale", SCALE, XY).act(obs)
        assert torch.equal(got[..., :2], want[..., :2] * SCALE), name
        assert torch.equal(got[..., 2:], want[..., 2:]), name


@pytest.mark.parametrize("side", SIDES)
def test_bias_adds_the_size_on_live_drones_only(gates, obs_of, side):
    """Bias adds exactly ``+size`` (then the clamp) on the chosen channel of every live drone; the other channels and
    the out drones are unchanged. The recorded error is that change, per slot, on live drones."""
    cfg, obs = obs_of[side]
    live = _live(obs)
    for name, script in _scripts(gates, side, cfg, obs.shape[0]).items():
        want = script.act(obs)
        w = _wrap(script, "bias", BIAS, (0,))
        got = w.act(obs)
        moved = (want[..., 0] + BIAS).clamp(-1, 1)
        assert torch.equal(got[..., 0], torch.where(live, moved, want[..., 0])), name
        assert torch.equal(got[..., 1:], want[..., 1:]), name
        assert torch.all(got[~live] == 0), name
        d = (got - want) * live[..., None]
        e = w.errors()
        assert torch.allclose(e["sum_sq"], (d.double() ** 2).sum(0), rtol=0, atol=TOL), name
        assert torch.equal(e["max_abs"], d.abs().amax(0)), name
        assert torch.equal(e["ref_max_abs"], (want * live[..., None]).abs().amax(0)), name


def test_bias_moves_the_zero_command_skill(obs_of):
    """C1: ``guard_parked_centre`` commands zero in a 3-Guard team; bias moves it to ``size`` on every live drone, a
    scale or a turn leaves it zero (review round 1, C1)."""
    cfg, obs = obs_of["guard"]
    live = _live(obs)
    script = make_strategy("guard_parked_centre", "guard", cfg, obs.shape[0], "cpu", 0)
    assert obs.shape[1] == 3 and torch.all(script.act(obs) == 0)
    got = _wrap(script, "bias", BIAS, XY).act(obs)
    assert torch.all(got[live][:, :2] == BIAS) and torch.all(got[live][:, 2:] == 0) and torch.all(got[~live] == 0)
    assert torch.all(_wrap(script, "scale", SCALE).act(obs) == 0)
    assert torch.all(_wrap(script, "turn", TURN_DEG).act(obs) == 0)


@pytest.mark.parametrize("side", SIDES)
def test_turn_keeps_the_norm_and_turns_by_the_angle(gates, obs_of, side):
    """Turn rotates xy anticlockwise by the angle (degrees): the xy norm is kept and the angle between the two
    commands is the angle (``allclose``); vz and yaw rate are unchanged."""
    cfg, obs = obs_of[side]
    turned = 0
    for name, script in _scripts(gates, side, cfg, obs.shape[0]).items():
        want = script.act(obs)
        got = _wrap(script, "turn", TURN_DEG).act(obs)
        assert torch.equal(got[..., 2:], want[..., 2:]), name
        a, b = want[..., :2], got[..., :2]
        assert torch.allclose(a.norm(dim=-1), b.norm(dim=-1), atol=TOL), name
        moving = a.norm(dim=-1) > TOL                      # none for a zero xy command (parked centre, strike_high)
        assert torch.all(b[~moving].abs() <= TOL), name
        ang = torch.atan2(a[..., 0] * b[..., 1] - a[..., 1] * b[..., 0], (a * b).sum(-1))
        assert torch.allclose(ang[moving], torch.full_like(ang[moving], math.radians(TURN_DEG)), atol=1e-5), name
        turned += int(moving.sum())
    assert turned > 0


def _zero(obs_of, side="strike"):
    cfg, obs = obs_of[side]
    return cfg, obs, make_strategy("zero", side, cfg, obs.shape[0], "cpu", 0)


def test_noise_lies_in_its_range_and_is_zero_on_out_drones(obs_of):
    """On a zero script the flown command is the noise itself: within [-s, s] on the chosen channels of live drones,
    zero on the others and on out drones."""
    cfg, obs, zero = _zero(obs_of)
    live = _live(obs)
    got = _wrap(zero, "noise", NOISE, XY).act(obs)
    assert torch.all(got[..., :2].abs() <= NOISE) and torch.all(got[..., 2:] == 0) and torch.all(got[~live] == 0)
    assert torch.all(got[live][:, :2] != 0)                  # drawn on every live drone and chosen channel
    assert got[live][:, :2].abs().max() > NOISE / 2          # the whole range is used


def test_noise_repeats_for_a_seed_and_changes_with_it(obs_of):
    cfg, obs, zero = _zero(obs_of)
    a, b, c = (_wrap(zero, "noise", NOISE, XY, seed=s) for s in (SEED, SEED, SEED + 1))
    for _ in range(3):                                         # a few ticks: the stream goes on, the same for a seed
        x, y, z = a.act(obs), b.act(obs), c.act(obs)
        assert torch.equal(x, y) and not torch.equal(x, z)
    assert not torch.equal(a.act(obs), x)                      # a new draw every tick


def test_noise_does_not_depend_on_the_other_cells_of_a_batch(obs_of):
    """One object per cell (C6): a cell's noise is the same played alone or beside another cell in one batch
    (``SplitStrategy``, as ``exploit._team_split`` builds it), so chunking the cells changes no game."""
    cfg, obs, _ = _zero(obs_of)
    n = obs.shape[0] // 2
    mine, other = obs[:n], obs[n:]
    alone = _wrap(make_strategy("strike_straight", "strike", cfg, n, "cpu", 0), "noise", NOISE)
    a = perturbed.CommandPerturbation(make_strategy("strike_straight", "strike", cfg, n, "cpu", 0), "noise", NOISE,
                                      SEED, XY)
    b = perturbed.CommandPerturbation(make_strategy("strike_flank", "strike", cfg, n, "cpu", 0), "noise", NOISE,
                                      SEED + 1, XY)
    split = SplitStrategy("strike", [(a, slice(0, n)), (b, slice(n, 2 * n))])
    every = torch.ones(n, dtype=torch.bool)
    alone.reset(every)
    split.reset(torch.ones(2 * n, dtype=torch.bool))
    for _ in range(3):
        assert torch.equal(alone.act(mine), split.act(torch.cat((mine, other)))[:n])


# ================================================================================================ the recorded error
def test_the_error_counts_each_slots_first_game_only(obs_of):
    """After a game ends (``reset`` with its mask) its later games add nothing: as ``HeldPlayer`` and ``play_match``
    count only each slot's first game, so the error does not depend on how long the other cells of a batch play."""
    cfg, obs = obs_of["strike"]
    live = _live(obs)
    w = _wrap(make_strategy("strike_straight", "strike", cfg, obs.shape[0], "cpu", 0), "bias", BIAS)
    w.reset(torch.ones(obs.shape[0], dtype=torch.bool))
    w.act(obs)
    done = torch.zeros(obs.shape[0], dtype=torch.bool)
    done[:5] = True
    w.reset(done)
    w.act(obs)
    w.reset(done)                                              # a later game of the same slots ends: still not counted
    w.act(obs)
    assert torch.equal(w.errors()["count"], live.sum(0) + 2 * live[5:].sum(0))


def test_the_error_is_kept_per_slot(obs_of):
    """A ``Composite`` flies column m of member m, so the error is kept per drone slot: a bias on one slot's script
    shows in every slot here, and the reader takes the slot it flies."""
    cfg, obs = obs_of["strike"]
    w = _wrap(make_strategy("strike_straight", "strike", cfg, obs.shape[0], "cpu", 0), "bias", BIAS, (0,))
    w.act(obs)
    e = w.errors()
    m = obs.shape[1]
    assert e["sum_sq"].shape == (m, 4) and e["max_abs"].shape == (m, 4) and e["count"].shape == (m,)
    assert e["ref_max_abs"].shape == (m, 4) and e["sum_sq"].dtype == torch.float64
    assert e["count"].dtype == torch.long
    assert perturbed.CommandPerturbation(make_strategy("zero", "strike", cfg, 2, "cpu", 0), "bias", BIAS, SEED,
                                         XY).errors() is None                       # nothing flown yet


# ================================================================================================ moved values
def _drone(team, pos, r=1.6, z=1.2, half=3.25):
    """One drone's observation: pos (x, y) relative to the zone centre (the recipe of tests/test_scripted_study.py
    ``drone``, copied: test modules are not imported)."""
    o = torch.zeros(OBS_DIM)
    o[0:2], o[2] = torch.tensor(pos), z
    o[V.zone_radius], o[V.arena_half], o[V.time_left] = r, half, 30.0
    o[V.team] = -1.0 if team == "guard" else 1.0
    o[V.alive] = 1.0
    return o


def _put(o, slot, rel_pos):
    s = V.slot(slot)
    o[s.start:s.start + 2] = torch.tensor(rel_pos)
    o[s.start + 6] = 1.0


def _hand_obs(cfg, team, positions, others=()):
    """A whole team's observation [1, k, OBS_DIM] (tests/test_scripted_study.py ``team_obs``, copied)."""
    pg = cfg.pad_guards
    rows = [_drone(team, p) for p in positions]
    mate0, other0 = (0, pg) if team == "guard" else (pg, 0)
    for i, o in enumerate(rows):
        for j, q in enumerate(positions):
            if j != i:
                _put(o, mate0 + j, (q[0] - positions[i][0], q[1] - positions[i][1]))
        for j, q in enumerate(others):
            _put(o, other0 + j, (q[0] - positions[i][0], q[1] - positions[i][1]))
    return torch.stack(rows)[None]


def test_the_moved_sacrifice_differs_only_between_the_two_half_angles(gates):
    """Strike 1 at offsets 0.5, 1.5, ... 89.5 degrees from the entry bearing (the drawn Guard at +x: entry at 180
    degrees), one game each: with the half-angle moved from today's 30 degrees to 40 degrees, the command differs on
    exactly the games whose offset lies between the two, and the switch recorder sees it."""
    cfg = exploit.variant_cfg(gates, "base")
    moved_rad = math.radians(40.0)
    offsets = [k + 0.5 for k in range(90)]
    obs = torch.cat([_hand_obs(cfg, "strike", [(2.75, 0.0), (2.6 * math.cos(math.radians(180.0 + d)),
                                                             2.6 * math.sin(math.radians(180.0 + d)))],
                               [(0.6, 0.0), (-0.5, -0.5)]) for d in offsets])
    n = obs.shape[0]
    script = make_strategy("strike_sacrifice", "strike", cfg, n, "cpu", 0)
    moved = perturbed.SacrificeMovedEntry("strike", cfg, n, "cpu", 0, entry_half_angle_rad=moved_rad)
    differ = (moved.act(obs) != script.act(obs)).any(-1).any(-1)
    between = torch.tensor([scripted.ENTRY_HALF_ANGLE_RAD < math.radians(d) <= moved_rad for d in offsets])
    assert between.sum() == 10 and torch.equal(differ, between)
    rec = perturbed.SwitchRecorder(moved, script)
    rec.act(obs)
    assert rec.errors()["max_abs"][1].max() > 0 and rec.errors()["max_abs"][0].max() == 0     # Strike 0 is the decoy


@pytest.mark.parametrize("off_rad,differs", [(0.05, False), (0.15, True), (0.25, False)])
def test_the_moved_gather_angle_changes_the_run_in(gates, off_rad, differs):
    """Two Strike drones on the stand-off circle, Strike 1 ``off_rad`` short of its bearing (opposite Strike 0): with
    the gather angle moved from today's 0.1 rad to 0.2 rad the run-in starts at 0.15 rad off, not at 0.05 or 0.25."""
    cfg = exploit.variant_cfg(gates, "base")
    b = math.pi + off_rad
    obs = _hand_obs(cfg, "strike", [(2.6, 0.0), (2.6 * math.cos(b), 2.6 * math.sin(b))])
    script = make_strategy("strike_converge", "strike", cfg, 1, "cpu", 0)
    moved = perturbed.ConvergeMovedGather("strike", cfg, 1, "cpu", 0, gather_angle_rad=0.2)
    assert bool((moved.act(obs) != script.act(obs)).any()) is differs


@pytest.mark.parametrize("mate_m,differs", [(1.3, True), (2.0, False)])
def test_the_moved_field_range_changes_the_push(gates, mate_m, differs):
    """A Guard on the zone edge facing the Strike drone (no pull) with a team-mate ``mate_m`` away: with the range
    moved from today's 1.1 m to 1.5 m the mate at 1.3 m pushes, the one at 2.0 m does not."""
    cfg = exploit.variant_cfg(gates, "base")
    obs = _hand_obs(cfg, "guard", [(1.6, 0.0), (1.6, mate_m)], [(3.0, 0.0)])
    script = make_strategy("guard_field", "guard", cfg, 1, "cpu", 0)
    moved = perturbed.FieldMovedRange("guard", cfg, 1, "cpu", 0, range_m=1.5)
    assert bool((moved.act(obs)[0, 0] != script.act(obs)[0, 0]).any()) is differs


@pytest.mark.parametrize("extra_m,differs", [(0.45, True), (0.9, False)])
def test_the_moved_flank_margin_changes_the_detour(gates, extra_m, differs):
    """A Strike drone flying in along +x with a Guard drone ahead, ``keepout + extra_m`` off the line: with the margin
    moved from today's 0.3 m to 0.6 m the Guard at keepout + 0.45 m is in the way, the one at keepout + 0.9 m is not."""
    cfg = exploit.variant_cfg(gates, "base")
    off = cfg.rules.keepout_strike_m + extra_m
    obs = _hand_obs(cfg, "strike", [(-2.6, 0.0)], [(-1.0, off)])
    script = make_strategy("strike_flank", "strike", cfg, 1, "cpu", 0)
    moved = perturbed.FlankMoved("strike", cfg, 1, "cpu", 0, margin_m=0.6)
    assert moved.MARGIN_M == 0.6 and scripted.StrikeFlank.MARGIN_M == 0.3       # an instance value, the class untouched
    assert bool((moved.act(obs) != script.act(obs)).any()) is differs


# ================================================================================================ the wrapper's interface
class _Inner:
    team, name = "strike", "inner"

    def __init__(self):
        self.resets = []

    def reset(self, games):
        self.resets.append(games.clone())

    def act(self, obs):
        return obs.new_zeros(*obs.shape[:2], 4)


def test_the_wrapper_exposes_team_name_and_forwards_reset():
    inner = _Inner()
    w = perturbed.CommandPerturbation(inner, "noise", NOISE, SEED, XY)
    assert w.team == "strike" and isinstance(w.name, str) and w.inner is inner
    assert perturbed.CommandPerturbation(inner, "bias", BIAS, SEED, XY, name="cal:x").name == "cal:x"
    games = torch.tensor([True, False, True])
    w.reset(games)
    assert len(inner.resets) == 1 and torch.equal(inner.resets[0], games)


@pytest.mark.parametrize("kind,size,channels", [
    ("shift", BIAS, XY), ("bias", BIAS, ()), ("bias", BIAS, (4,)), ("bias", BIAS, (-1,)), ("bias", BIAS, (0, 0)),
    ("turn", TURN_DEG, (0,)), ("turn", TURN_DEG, (2, 3)), ("noise", -NOISE, XY), ("bias", float("nan"), XY),
    ("scale", float("inf"), XY)])
def test_bad_arguments_are_refused(kind, size, channels):
    with pytest.raises(ValueError):
        perturbed.CommandPerturbation(_Inner(), kind, size, SEED, channels)


# ================================================================================================ boundaries
def test_scripted_is_untouched_and_the_changed_players_stay_out_of_the_registry():
    import hashlib
    assert hashlib.sha256(SCRIPTED.read_bytes()).hexdigest().startswith(SCRIPTED_SHA_PREFIX)
    ours = {perturbed.CommandPerturbation, perturbed.SwitchRecorder, perturbed.SacrificeMovedEntry,
            perturbed.ConvergeMovedGather, perturbed.FieldMovedRange, perturbed.FlankMoved}
    assert not ours & set(REGISTRY.values())
    init = (ROOT / "source" / "svg_training" / "opponents" / "__init__.py").read_text()
    assert "perturbed" not in init


def test_no_host_read_in_the_changed_players():
    """Played during scoring: no host read (as tests/test_game_core.py's scan of the step files)."""
    text = MODULE.read_text()
    assert not re.search(r"\.(item|cpu|numpy|tolist)\(|import numpy|nonzero\(", text)


# ================================================================================================ one played cell
def test_an_identity_wrapper_plays_its_scripts_games(gates):
    """``exploit.play_cells`` on T44's starts, hold 1, the gate file's tick cap, 8 games: a ``cal:`` cell flown by an
    identity bias wrapper of ``strike_flank`` equals the plain script's cell game for game; its error is zero over a
    positive count."""
    ref = exploit.load_reference(exploit.ROOT / gates.reference["file"])
    cfg = exploit.variant_cfg(gates, "base")
    n, opp = 8, "guard_mark_edge"
    w = perturbed.CommandPerturbation(make_strategy("strike_flank", "strike", cfg, n, "cpu", 0), "bias", 0.0, SEED,
                                      XY, name="cal:bias0:strike_flank")
    pg = exploit.play_cells(cfg, gates.run["size"], ref, [(opp, w.name), (opp, "strike_flank")], n, "cpu",
                            int(ref.meta["seed"]), int(gates.run["ticks_cap"]), hold_ticks=1, players={w.name: w})
    for key in ("outcome", "end_step", "tags", "strikes_left"):
        assert (pg[key][:n] == pg[key][n:]).all(), key
    e = w.errors()
    assert e["count"].sum() > 0 and e["sum_sq"].abs().sum() == 0
