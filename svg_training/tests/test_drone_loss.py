"""STE task L2.4: drone loss and random team size (WORK_BREAKDOWN L2.4; STANDARDS section 4, team sizes FIXED, drop-out
PROPOSED; P7, not ruled, decides whether this is part of the flown game).

``[team_size] mode = "drawn"`` (PROPOSED; the default "fixed" is today's game bit for bit): the game's ``guards`` and
``strikes`` are slot counts; every game draws its own team sizes, uniform whole numbers in ``guards_range`` and
``strikes_range``, from a generator of its own seeded from the game seed. The first g Guard slots and the first s Strike
slots are present; the other slots are absent: never alive (out from the start, parked), so they never act, never tag,
are never tagged, never score, take part in no filter pair and show present = 0 in every observation. The starts
(``zone_disc_ring`` only) are drawn for the game's own sizes by the same rules as a fixed game of that size. A drop-out
(``dropout_fraction``) picks a present drone; it lands when ``[landing]`` is on and is out at once when it is off.

CPU, made-up games; observed in the training simulator, not a flight result.
"""
import math
import pathlib
import tomllib

import pytest
import torch

from svg_training.core.game import PARK_M, SvgGame
from svg_training.core.game_config import CONFIGS, GameCfg, TeamSizeCfg, load_game_cfg
from svg_training.core.observations import SLOT, ObsView
from svg_training.core.physics_layer import load_game_physics_params
from svg_training.models.rigid_body import TorchRigidBodyWorld

BASE = load_game_cfg(use_local=False)[0]
STUDY = CONFIGS / "ste_l2" / "drone_loss_drawn.toml"
V = ObsView()
G_PAD, S_PAD = BASE.pad_guards, BASE.pad_strikes          # 5 + 3 slots


def lab_cfg(**changes) -> GameCfg:
    """The committed s2 game with the track's 6.5 m lab arena (zone at the centre) and the zone_disc_ring starts (the
    values of configs/ste_l1/base_1v1_1p15.toml); pure partner rules unless changed."""
    side, frac = 6.5, 1.6 / 6.5
    cfg = BASE.replace(**{
        "arena.bands_m": {"lab": (side, side), "middle": (side, side), "large": (side, side)},
        "arena.zone_radius_frac": (frac, frac), "arena.zone_wall_margin_m": side / 2,
        "starts.mode": "zone_disc_ring", "starts.strike_ring_m": 2.75, "starts.guard_disc_m": 0.8})
    return cfg.replace(**changes) if changes else cfg


def drawn(lo_hi_g=(1, 5), lo_hi_s=(1, 3), **changes) -> GameCfg:
    return lab_cfg(**{"team_size.mode": "drawn", "team_size.guards_range": lo_hi_g,
                      "team_size.strikes_range": lo_hi_s, **changes})


def starling(cfg: GameCfg, backend="fitted", **changes) -> GameCfg:
    kw = {"starling.enabled": True, "starling.filter_iterations": 50, **changes}
    if backend == "physics":
        kw["starling.backend"] = "physics"
    return cfg.replace(**kw)


def make(cfg, n=64, guards=G_PAD, strikes=S_PAD, seed=0):
    world = None
    if cfg.starling.enabled and cfg.starling.backend == "physics":
        p = load_game_physics_params(cfg)
        world = TorchRigidBodyWorld(n, guards + strikes, p.airframe, p.physics_dt_s, "cpu")
    return SvgGame(cfg, n, guards, strikes, device="cpu", seed=seed, world=world)


def actions(g, gen, scale=1.0):
    return {"guard": (torch.rand(g.num_games, g.guards, 4, generator=gen) * 2 - 1) * scale,
            "strike": (torch.rand(g.num_games, g.strikes, 4, generator=gen) * 2 - 1) * scale}


def expected_present(g_n, s_n, guards=G_PAD, strikes=S_PAD):
    slot = torch.arange(guards + strikes)
    return torch.where(slot < guards, slot[None] < g_n[:, None], (slot - guards)[None] < s_n[:, None])


def sizes(g):
    p = g.present
    return p[:, :g.guards].sum(1), p[:, g.guards:].sum(1)


def run_outputs(g, steps, seed=7):
    """Every tensor of ``steps`` steps of random commands, in order."""
    gen = torch.Generator().manual_seed(seed)
    out = [g.pos_m.clone(), g.alive.clone(), g.dropout_step.clone(), g.state()]
    for _ in range(steps):
        s = g.step(actions(g, gen))
        out += [g.pos_m, g.vel_mps, g.yaw, g.alive, g.steps, g.dropout_step, s.done, s.outcome, s.end_step,
                *s.obs.values(), *s.reward.values(), *[v for k, v in sorted(s.info.items()) if k != "present"]]
    return out


def same(a, b):
    assert len(a) == len(b)
    for x, y in zip(a, b):
        assert x.dtype == y.dtype and x.shape == y.shape
        assert torch.equal(x, y) or (x.is_floating_point() and torch.equal(x.isnan(), y.isnan())
                                     and torch.equal(x[~x.isnan()], y[~y.isnan()]))


# ---------------------------------------------------------------------------------------------- settings
def test_default_is_fixed_and_the_ranges_are_the_proposed_sizes():
    ts = TeamSizeCfg()
    assert ts.mode == "fixed"
    assert ts.guards_range == (1, 5) and ts.strikes_range == (1, 3)       # STANDARDS section 4: 1-5 v 1-3 (PROPOSED)
    assert BASE.team_size == ts


@pytest.mark.parametrize("bad", [
    {"mode": "random"}, {"guards_range": (0, 3)}, {"guards_range": (3, 2)}, {"strikes_range": (1,)},
    {"strikes_range": (1.5, 3)}, {"guards_range": (True, 2)}, {"mode": "drawn", "guards_range": (1, 6)},
    {"mode": "drawn", "strikes_range": (1, 4)}])
def test_bad_team_size_settings_raise(bad):
    with pytest.raises(ValueError):
        lab_cfg(**{f"team_size.{k}": v for k, v in bad.items()})


def test_drawn_sizes_refuse_other_start_modes_and_the_contact_preset():
    with pytest.raises(ValueError, match="zone_disc_ring"):
        drawn(**{"starts.mode": "rings"})
    with pytest.raises(ValueError, match="partner"):
        drawn(preset="contact")


def test_drawn_sizes_need_slots_for_the_largest_size():
    with pytest.raises(ValueError, match="slots"):
        SvgGame(drawn(), 4, 3, 3, device="cpu")


def test_the_toml_section_loads(tmp_path):
    text = STUDY.read_text() if STUDY.is_file() else ""
    assert "[team_size]" in text
    cfg, _ = load_game_cfg(STUDY, use_local=False)
    assert cfg.team_size.mode == "drawn"
    bad = tmp_path / "bad.toml"
    bad.write_text(text.replace("\n[team_size]\n", "\n[team_size]\nsize_weights = [1.0]\n"))
    with pytest.raises(ValueError, match="unknown key"):
        load_game_cfg(bad, use_local=False)


def test_study_file_is_proposed_and_every_committed_game_file_stays_fixed():
    """The only file with drawn sizes or drop-outs on is the new study file (PROPOSED, P7 not ruled); ste_game.toml and
    every other committed game file keep their values (no [team_size], dropout_fraction as before)."""
    data = tomllib.loads(STUDY.read_text())
    assert data["team_size"]["mode"] == "drawn" and data["game"]["dropout_fraction"] > 0
    text = STUDY.read_text()
    table = text.split("\n[team_size]\n", 1)[1].split("\n[", 1)[0]
    lines = [ln for ln in table.splitlines() if "=" in ln] + \
        [ln for ln in text.splitlines() if ln.startswith("dropout_fraction")]
    assert len(lines) == 4 and all("PROPOSED" in ln for ln in lines)
    for path in CONFIGS.rglob("*.toml"):
        if path == STUDY or "local" in path.parts:
            continue
        data_other = tomllib.loads(path.read_text())
        assert "team_size" not in data_other, path
        assert data_other.get("game", {}).get("dropout_fraction", 0.0) == 0.0, path      # drop-outs stay off (P7)
    assert tomllib.loads((CONFIGS / "ste_game.toml").read_text()).get("team_size") is None


# ---------------------------------------------------------------------------------------------- off = today
def test_fixed_mode_written_out_is_the_same_game():
    """``[team_size] mode = "fixed"`` with other ranges plays as no section: nothing else is read, nothing drawn."""
    for cfg in (lab_cfg(dropout_fraction=0.5), starling(lab_cfg(dropout_fraction=0.5))):
        a = make(cfg, n=8, guards=3, strikes=3, seed=3)
        b = make(cfg.replace(**{"team_size.guards_range": (2, 2), "team_size.strikes_range": (1, 1)}), n=8, guards=3,
                 strikes=3, seed=3)
        same(run_outputs(a, 30), run_outputs(b, 30))
        assert "present" not in a.step(actions(a, torch.Generator())).info


@pytest.mark.parametrize("size", [(1, 1), (3, 3), (5, 3), (2, 1)])
def test_drawn_with_one_size_is_the_fixed_game_of_that_size(size):
    """A range of one size plays the fixed game of that size bit for bit (starts, drop-outs, every output): the drawn
    starts follow the fixed starts' rules and draw order; only info["present"] is new."""
    gs, ss = size
    for base in (lab_cfg(dropout_fraction=0.5), starling(lab_cfg(dropout_fraction=0.5))):
        fixed = make(base, n=16, guards=gs, strikes=ss, seed=5)
        one = make(base.replace(**{"team_size.mode": "drawn", "team_size.guards_range": (gs, gs),
                                   "team_size.strikes_range": (ss, ss)}), n=16, guards=gs, strikes=ss, seed=5)
        same(run_outputs(fixed, 60), run_outputs(one, 60))


# ---------------------------------------------------------------------------------------------- masks
def test_every_size_occurs_and_the_masks_are_right():
    g = make(drawn(), n=1500)
    g_n, s_n = sizes(g)
    combos = set(zip(g_n.tolist(), s_n.tolist()))
    assert combos == {(a, b) for a in range(1, 6) for b in range(1, 4)}            # all 15 sizes
    assert torch.equal(g.present, expected_present(g_n, s_n))
    assert torch.equal(g.alive, g.present)                                          # absent drones start out
    assert (g.pos_m[~g.present] == PARK_M).all()                                     # parked, as an out drone
    assert not g.start_miss.any() and not g.start_team_close.any()


def test_masks_right_for_every_size_one_by_one():
    for gs in range(1, 6):
        for ss in range(1, 4):
            g = make(drawn((gs, gs), (ss, ss)), n=4)
            assert torch.equal(g.present, expected_present(torch.full((4,), gs), torch.full((4,), ss)))


def test_absent_drones_show_present_zero_in_every_observation():
    g = make(drawn(), n=400)
    obs = g._obs()
    o = torch.cat((obs["guard"], obs["strike"]), dim=1)                             # [N, 8, D] in slot order
    p = g.present
    team = torch.where(torch.arange(8) < G_PAD, -1.0, 1.0)
    # an absent drone's own row: zeros but its team
    own = o[~p]
    assert (own[:, V.team] == team.expand(p.shape)[~p]).all()
    rest = torch.cat((own[:, :V.team], own[:, V.team + 1:]), dim=1)
    assert (rest == 0).all()
    # in a present drone's slots: an absent drone is all zeros with present 0; a present other drone has present 1
    slots = o[..., V.SLOTS_FROM:V.SLOTS_FROM + SLOT * 8].reshape(*o.shape[:2], 8, SLOT)   # [N, self, other, 7]
    other_present = p[:, None, :] & p[:, :, None] & ~torch.eye(8, dtype=torch.bool)
    assert torch.equal(slots[..., SLOT - 1] == 1, other_present)
    assert (slots[~other_present] == 0).all()
    # the critic's state: absent slots all zeros, present flag 0
    st = g.state()[:, 3:3 + SLOT * 8].reshape(-1, 8, SLOT)
    assert torch.equal(st[..., SLOT - 1] == 1, p) and (st[~p] == 0).all()


def test_starts_keep_the_rules_at_every_size():
    """Team-mates at least the filter distance + margin apart, opposite drones at least the keep-out apart, no Strike
    drone in the zone, Guards inside max(disc, chord radius), Strikes on the ring."""
    cfg = drawn()
    g = make(cfg, n=1500)
    spacing = max(cfg.rules.keepout_guard_m, cfg.rules.keepout_strike_m) + cfg.starts.team_spacing_margin_m
    p, xy = g.present, g.pos_m[..., :2] - g.arenas.zone_centre_m[:, None]
    d = (xy[:, :, None] - xy[:, None, :]).norm(dim=-1)
    both = p[:, :, None] & p[:, None, :] & ~torch.eye(8, dtype=torch.bool)
    is_s = torch.arange(8) >= G_PAD
    mates = both & (is_s[:, None] == is_s[None, :])
    assert (d[mates] >= spacing - 1e-5).all()
    assert (d[both & ~mates] >= cfg.rules.keepout_guard_m).all()
    r = xy.norm(dim=-1)
    g_n = sizes(g)[0]
    chord = torch.where(g_n > 1, spacing / (2 * torch.sin(math.pi / g_n.clamp(min=2))), torch.zeros(g_n.shape))
    assert (r[:, :G_PAD][p[:, :G_PAD]] <= torch.maximum(chord, torch.tensor(0.8))[:, None].expand(-1, G_PAD)[
        p[:, :G_PAD]] + 1e-5).all()
    assert torch.allclose(r[:, G_PAD:][p[:, G_PAD:]], torch.tensor(2.75), atol=1e-5)


# ---------------------------------------------------------------------------------------------- draws
def test_same_seed_same_sizes_and_reset_repeats_them():
    a, b, c = make(drawn(), seed=11), make(drawn(), seed=11), make(drawn(), seed=12)
    assert torch.equal(a.present, b.present) and not torch.equal(a.present, c.present)
    first = a.present.clone()
    a._new_games(torch.ones(a.num_games, dtype=torch.bool))
    assert not torch.equal(a.present, first)                                          # a new game redraws
    a.reset(seed=11)
    assert torch.equal(a.present, first)


def test_a_running_game_keeps_its_size_when_others_restart():
    g = make(drawn(), n=200, seed=2)
    before = g.present.clone()
    mask = torch.arange(200) % 2 == 0
    g._new_games(mask)
    assert torch.equal(g.present[~mask], before[~mask])
    assert not torch.equal(g.present[mask], before[mask])


def test_the_size_draw_leaves_the_games_own_stream_alone():
    """The sizes come from their own generator: the arenas drawn next by the game's generator are the same as in a fixed
    game with the same seed."""
    fixed, dr = make(lab_cfg(**{"arena.zone_radius_frac": (0.2, 0.25)}), seed=4), \
        make(drawn(**{"arena.zone_radius_frac": (0.2, 0.25)}), seed=4)
    for g in (fixed, dr):                                   # starts and drop-outs drawn, then the next arenas
        g._new_games(torch.ones(g.num_games, dtype=torch.bool))
    assert torch.equal(fixed.arenas.zone_radius_m, dr.arenas.zone_radius_m)


# ---------------------------------------------------------------------------------------------- playing
@pytest.mark.parametrize("backend", ["pure", "fitted", "physics"])
def test_absent_drones_never_act_count_or_pair(backend):
    cfg = drawn(**{"tag.mode": "nearest_pair_1for1"})
    if backend != "pure":
        cfg = starling(cfg, backend)
    g = make(cfg, n=24, seed=1)
    gen = torch.Generator().manual_seed(0)
    for _ in range(15):
        p = g.present.clone()
        a = actions(g, gen)
        a["guard"][~p[:, :G_PAD]] = float("nan")                                     # absent slots send garbage
        s = g.step(a)
        assert torch.equal(s.info["present"], p)
        assert not (s.info["final_alive"] & ~p).any()
        assert not (s.info["tagged"] & ~p).any()
        assert (s.info["nonfinite_actions"] == 0).all()                              # absent drones never act
        assert (g.pos_m[~g.present] == PARK_M).all()
        if backend != "pure":
            chain = g._starling.chain if backend == "physics" else g._starling.model.chain
            pm = chain.pair_mask
            absent = ~g.present
            assert not (pm & (absent[:, :, None] | absent[:, None, :])).any()


def test_absent_drones_never_land():
    g = make(starling(drawn(**{"tag.mode": "nearest_pair_1for1"}), **{"landing.enabled": True}), n=24, seed=1)
    gen = torch.Generator().manual_seed(0)
    for _ in range(15):
        p = g.present.clone()
        s = g.step(actions(g, gen))
        assert not (s.info["landing"] & ~p).any()


def test_dropout_picks_a_present_drone_at_a_drawn_step():
    g = make(drawn(dropout_fraction=1.0), n=600, seed=3)
    picked = g.dropout_step >= 0
    assert (picked.sum(1) == 1).all()                                                # every game, one drone
    assert not (picked & ~g.present).any()                                           # never an absent slot
    steps = g.dropout_step[picked]
    assert steps.min() >= 1 and steps.max() <= g.ticks
    # every present drone can be picked: all slots occur
    assert picked.any(0).all()


def test_dropout_happens_at_the_drawn_step():
    cfg = drawn(dropout_fraction=1.0, **{"rules.game_steps": 40})                   # 40 ticks: drop-outs in reach
    g = make(cfg, n=64, seed=6)
    when, who = g.dropout_step.clone(), (g.dropout_step >= 0).long().argmax(1)
    zero = {"guard": torch.zeros(64, G_PAD, 4), "strike": torch.zeros(64, S_PAD, 4)}  # nobody moves: no reach
    ended = torch.zeros(64, dtype=torch.bool)
    rows = torch.arange(64)
    for t in range(1, 41):
        s = g.step(zero)
        fa = s.info["final_alive"][rows, who]
        live = ~ended
        assert torch.equal(fa[live], (when[rows, who] > t)[live])                      # out exactly at its step
        ended |= s.done
    assert ended.all()


@pytest.mark.parametrize("backend", ["fitted", "physics"])
def test_a_dropped_drone_lands_with_landing_on_and_is_out_at_once_with_it_off(backend):
    for landing in (True, False):
        cfg = starling(drawn((2, 2), (2, 2)), backend, **{"landing.enabled": landing})
        g = make(cfg, n=4, guards=G_PAD, strikes=S_PAD, seed=0)
        g.schedule_dropout(torch.zeros(4, dtype=torch.long), torch.ones(4, dtype=torch.long))
        zero = {"guard": torch.zeros(4, G_PAD, 4), "strike": torch.zeros(4, S_PAD, 4)}
        z0 = g.pos_m[:, 0, 2].clone()
        s = g.step(zero)
        assert not s.info["final_alive"][:, 0].any()
        if landing:
            assert s.info["landing"][:, 0].all()
            assert (g.pos_m[:, 0, 2] < z0 + 1e-3).all() and (g.pos_m[:, 0, 2] < PARK_M).all()
        else:
            assert "landing" not in s.info and (g.pos_m[:, 0] == PARK_M).all()


def test_the_study_file_plays():
    cfg = load_game_cfg(STUDY, use_local=False)[0].replace(**{"starling.filter_iterations": 50})
    g = make(cfg, n=16, seed=0)
    gen = torch.Generator().manual_seed(1)
    for _ in range(5):
        s = g.step(actions(g, gen))
        assert torch.isfinite(s.obs["guard"]).all()
