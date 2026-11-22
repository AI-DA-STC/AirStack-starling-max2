"""STE task L0.11 Screening sweep (INFO): the variant game files, the gate file, the sweep's game (paired starts tiled
over the cells of a batch, per-game counts), the controls with known answers, and the shortlist rule.

CPU only. Every number compared comes from the sheet (``configs/ste_game.toml``), the gate file or a game file; the
games played here are a few ticks long (the Starling layer costs tens of ms per tick on a CPU)."""
import hashlib
import math
from pathlib import Path

import numpy as np
import pytest
import torch

from svg_training.core.game import SvgGame
from svg_training.core.game_config import TICK_S, load_game_cfg
from svg_training.core.play import play_match
from svg_training.core.rewards import GUARD_WIN, STRIKE_WIN
from svg_training.core.starling_layer import StarlingLayer
from svg_training.models.fitted import load_params
from svg_training.core.starling_layer import resolve_params
from svg_training.opponents import scripted
from svg_training.opponents.scripted import make_strategy
from svg_training.ste import sweep
from svg_training.ste.game_spec import SCHEMA, load_game_spec

ROOT = Path(__file__).resolve().parents[1]
SPEC = load_game_spec()[0]
GATES = sweep.load_gates()
TOL_M = 1e-5


def built(name: str, guards: int = 3, strikes: int = 3, games: int = 64) -> SvgGame:
    return SvgGame(sweep.variant_cfg(GATES, name), games, guards, strikes, device="cpu", seed=GATES.run["seed"], band=0)


# ================================================================================================ game files
def test_every_game_file_is_pinned_by_its_sha256_and_loads_without_the_local_file():
    assert sweep.game_file_problems(GATES) == []
    for name, ref in GATES.games.items():
        path = ROOT / ref.file
        assert hashlib.sha256(path.read_bytes()).hexdigest() == ref.sha256, name
        cfg, prov = load_game_cfg(path, local_dir=None, use_local=False)
        assert prov.local_file is None
        assert sweep.variant_cfg(GATES, name) == cfg


def test_every_game_file_is_complete_it_names_every_setting_of_every_section():
    """A complete game file: no value comes from a code default (a default added later, as starts.team_spacing_margin_m
    by L0.10's QC fix, must be written into the files, with their pinned sha256 updated)."""
    import dataclasses
    import tomllib

    from svg_training.core import game_config as gc
    sections = {"arena": gc.ArenaCfg, "partner_rules": gc.PartnerRulesCfg, "contact_rules": gc.ContactRulesCfg,
                "starling_layer": gc.StarlingLayerCfg, "starts": gc.StartsCfg, "rewards": gc.RewardsCfg, "tag": gc.TagCfg}
    for name, ref in GATES.games.items():
        data = tomllib.loads((ROOT / ref.file).read_text())
        for sec, cls in sections.items():
            missing = {f.name for f in dataclasses.fields(cls)} - set(data[sec])
            assert not missing, (name, sec, missing)


def test_an_edited_game_file_is_reported(tmp_path):
    ref = GATES.games["base"]
    copy = tmp_path / "base.toml"
    copy.write_text((ROOT / ref.file).read_text() + "\n# edited\n")
    changed = GATES.with_game("base", str(copy))
    problems = sweep.game_file_problems(changed)            # an absolute path wins over the root
    assert len(problems) == 1 and "base" in problems[0] and "sha256" in problems[0]


# Sheet rows and how the base game, as built, is checked against each. A row is either CHECKED on the built game,
# a property of the engine that no setting changes (ENGINE, with the code that fixes it), set differently ON PURPOSE for
# the study, a row about the study design checked on the gate file (DESIGN), or NOT APPLIED by this engine path.
NOT_APPLIED = {"timing.decision_s": "the scripted players act every tick (0.05 s), see the decision-period test"}
ON_PURPOSE = {"tag.mode": "nearest_pair_1for1"}       # the switch's default is off; the track's game files set it on
ENGINE = {"zone.shape": "core/game.py:314-315 tests a distance to one centre",
          "zone.scored_in": "core/game.py:314-315 tests the horizontal distance only",
          "arena.environment": "tier 1 has no obstacles", "filter.share": "safety filter: equal split, its only mode"}
DESIGN = {"teams.of_interest", "teams.target_sizes", "teams.base_case", "players.guard_park_ring_m"}


def realised_base() -> dict:
    """What the base game, as built, plays: read from the built game, not from the TOML."""
    g = built("base", games=256)
    cfg = g.cfg
    rho = (g.pos_m[..., :2] - g.arenas.zone_centre_m[:, None, :]).norm(dim=-1)
    params = load_params(resolve_params(cfg.starling.params))
    gap = (g.pos_m[:, :, None, :2] - g.pos_m[:, None, :, :2]).norm(dim=-1)
    team = torch.zeros(6, 6, dtype=torch.bool)
    team[:3, :3] = team[3:, 3:] = True
    team &= ~torch.eye(6, dtype=torch.bool)
    keepout = max(cfg.rules.keepout_guard_m, cfg.rules.keepout_strike_m)
    return {
        "starts.team_spacing_margin_m": gap[:, team].min().item() - keepout,     # closest team-mates at the start
        "zone.radius_m": float(g.arenas.zone_radius_m.unique()), "zone.centre": g.arenas.zone_centre_m.abs().max().item(),
        "zone.win_ticks_inside": cfg.rules.win_steps_in_zone, "height.band_m": tuple(cfg.arena.height_band_m),
        "height.mode": g.motion, "height.start_m": float(g.pos_m[..., 2].unique()),
        "arena.side_m": float(g.arenas.side_m.unique()), "arena.wall_margin_m": cfg.arena.wall_margin_m,
        "arena.walls": cfg.arena.walls, "starts.guard_disc_m": rho[:, :3].max().item(),
        "starts.strike_ring_m": rho[:, 3:], "timing.game_s": g.ticks * TICK_S,
        "speeds.strike_mps": cfg.team_speed_mps("strike"),
        "speeds.strike_to_guard_ratio": cfg.team_speed_mps("strike") / cfg.team_speed_mps("guard"),
        "tag_rule.main_game_has_tag": cfg.tag.mode != "off",                        # G0, 22 Nov 2026 (P1)
        "tag_rule.radius_m": cfg.tag.radius_m, "tag.radius_m": cfg.tag.radius_m, "tag_rule.pairing": cfg.tag.mode,
        "tag_rule.guard_survives_tag_prob": cfg.tag.guard_survives_tag_prob,
        "tag.guard_survives_tag_prob": cfg.tag.guard_survives_tag_prob,
        "filter.pairs": isinstance(g._starling, StarlingLayer),
        "filter.keepout_m": (cfg.rules.keepout_guard_m, cfg.rules.keepout_strike_m, 2 * params["filter"]["safety_radius_m"]),
    }


def cfg_margin(name: str) -> float:
    return sweep.variant_cfg(GATES, name).starts.team_spacing_margin_m


def test_the_base_game_as_built_equals_the_sheet_rows_it_claims():
    got = realised_base()
    checked = set(got)
    assert checked | set(NOT_APPLIED) | set(ON_PURPOSE) | set(ENGINE) | DESIGN == set(SCHEMA)      # every row placed
    for key, value in got.items():
        want = SPEC.value(key)
        if key == "starts.team_spacing_margin_m":
            assert value >= want - TOL_M and cfg_margin("base") == want
        elif key == "starts.guard_disc_m":
            assert value <= want + TOL_M
        elif key == "starts.strike_ring_m":
            assert torch.allclose(value, torch.full_like(value, want), atol=TOL_M)
        elif key == "height.mode":
            assert want == "free" and value == "starling"           # 3-D motion through the commander copy
        elif key == "filter.pairs":
            assert want == "every_pair" and value                    # the Starling layer's filter takes every pair
        elif key == "filter.keepout_m":
            assert all(math.isclose(v, want) for v in value)
        elif key == "zone.centre":
            assert want == "arena_centre" and value == 0
        elif key == "tag_rule.pairing":
            assert value == want
        elif isinstance(want, (tuple, str, bool)) or isinstance(value, str):
            assert value == want, key
        else:
            assert math.isclose(value, want, rel_tol=1e-6), (key, value, want)
    assert scripted.PARK_RING_M == SPEC.value("players.guard_park_ring_m")
    base = GATES.group("base")
    assert base.size == SPEC.value("teams.base_case")
    sizes = {g.size for g in GATES.groups if g.role == "sweep"}
    assert sizes == set(SPEC.value("teams.target_sizes")) and set(SPEC.value("teams.of_interest")) <= sizes
    for key, value in ON_PURPOSE.items():
        assert SPEC.value(key) != value                          # the study differs from the sheet here, on purpose
    assert built("base").cfg.tag.mode == ON_PURPOSE["tag.mode"]


class Counting:
    """Wraps a player and counts its decisions (calls of act)."""

    def __init__(self, inner):
        self.inner, self.team, self.name, self.calls = inner, inner.team, inner.name, 0

    def reset(self, games):
        self.inner.reset(games)

    def act(self, obs):
        self.calls += 1
        return self.inner.act(obs)


def test_the_decision_period_actually_used_is_one_tick_not_the_sheets_0_6_s():
    cfg = sweep.variant_cfg(GATES, "base")
    g = SvgGame(cfg, 4, 3, 3, device="cpu", seed=1, band=0)
    guard = Counting(make_strategy("guard_field", "guard", cfg, 4, "cpu", 1))
    strike = Counting(make_strategy("strike_straight", "strike", cfg, 4, "cpu", 2))
    ticks = 6
    play_match(g, guard, strike, max_steps=ticks)
    assert guard.calls == strike.calls == ticks                   # one new command per 0.05 s tick
    assert TICK_S != SPEC.value("timing.decision_s")


VARIANT_CHANGES = {      # dotted settings that differ from base.toml, per variant game file
    "tag_1p2": {"tag.radius_m"}, "tag_1p4": {"tag.radius_m"}, "tag_1p8": {"tag.radius_m"},
    "survive_1": {"tag.guard_survives_tag_prob"}, "zone_2p4": {"arena.zone_radius_frac"},
    "arena_7p5": {"arena.bands_m", "arena.zone_radius_frac", "arena.zone_wall_margin_m", "starts.strike_ring_m"},
    "tag_off": {"tag.mode"}, "tag_0p05": {"tag.radius_m"}, "tag_10m": {"tag.radius_m"},
    "zone_2p4_tag_off": {"arena.zone_radius_frac", "tag.mode"},
}


def flat(cfg) -> dict:
    out = {}
    for sec in ("arena", "rules", "contact", "starling", "starts", "rewards", "tag"):
        for k, v in vars(getattr(cfg, sec)).items():
            out[f"{sec}.{k}"] = v
    return out


@pytest.mark.parametrize("name", sorted(VARIANT_CHANGES))
def test_each_variant_changes_only_what_it_says(name):
    base, other = flat(sweep.variant_cfg(GATES, "base")), flat(sweep.variant_cfg(GATES, name))
    assert {k for k in base if base[k] != other[k]} == VARIANT_CHANGES[name]


@pytest.mark.parametrize("name", ["base", "tag_1p2", "tag_1p4", "tag_1p8", "survive_1", "zone_2p4", "arena_7p5"])
def test_every_variant_starts_on_its_ring_inside_the_keep_in_box_with_no_tag_at_the_first_step(name):
    g = built(name, games=512)
    cfg = g.cfg
    lim = float(g.arenas.half_m.unique()) - cfg.arena.wall_margin_m
    rho = (g.pos_m[..., :2] - g.arenas.zone_centre_m[:, None, :]).norm(dim=-1)
    assert torch.allclose(rho[:, 3:], torch.full_like(rho[:, 3:], cfg.starts.strike_ring_m), atol=TOL_M)
    assert g.pos_m[..., :2].abs().max() <= lim + TOL_M
    assert cfg.starts.strike_ring_m - cfg.starts.guard_disc_m > cfg.tag.radius_m          # no tag at the first step
    assert cfg.starts.strike_ring_m >= float(g.arenas.zone_radius_m.unique()) + GATES.ring_margin_m - TOL_M
    out = g.step({"guard": torch.zeros(512, 3, 4), "strike": torch.zeros(512, 3, 4)})
    assert not out.info["tagged"].any() and not g.start_miss.any()


def test_the_lead_rulings_on_the_two_confounds_hold():
    """Zone 2.4 m: the ring stays 2.75 m because 2.75 >= 2.4 + 0.3; 3.55 m would not fit the keep-in limit. 7.5 m arena:
    the hangar ring 3.2 m (the sheet's hangar value)."""
    z = sweep.variant_cfg(GATES, "zone_2p4")
    side = SPEC.value("arena.side_m")
    zone = z.arena.zone_radius_frac[0] * side
    assert math.isclose(zone, 2.4) and z.starts.strike_ring_m == SPEC.value("starts.strike_ring_m")
    assert z.starts.strike_ring_m >= zone + GATES.ring_margin_m
    other_ring = zone + (SPEC.value("starts.strike_ring_m") - SPEC.value("zone.radius_m"))
    assert other_ring > side / 2 - SPEC.value("arena.wall_margin_m")                  # 3.55 m would not fit
    a = sweep.variant_cfg(GATES, "arena_7p5")
    assert a.starts.strike_ring_m == 3.2 and a.arena.bands_m["lab"] == (7.5, 7.5)


# ================================================================================================ the gate file
def cells_of(plan, name):
    return [len(p.cells) for p in plan if p.spec.name == name][0]


def test_the_gate_file_lists_the_cells_in_the_stated_cut_order():
    plan = sweep.build_plan(GATES)
    names = [p.spec.name for p in plan]
    first_sweep = names.index("base")
    assert all(GATES.group(n).control in (sweep.TAG_FIRES, sweep.REACH_FIRES) for n in names[:first_sweep])
    sweeps = [n for n in names if GATES.group(n).role in ("sweep", "sensitivity")]
    assert sweeps[:5] == ["base", "sens_strike_dz_1mm", "size_1v1", "size_2v1", "size_5v3"]
    assert set(GATES.cut["protected"]) == {"base"} | {n for n in names if GATES.group(n).role == "control"}
    assert cells_of(plan, "sens_strike_dz_1mm") == len(GATES.players["guards"])
    sens = GATES.group("sens_strike_dz_1mm")
    assert sens.strikes == ("strike_straight",) and sens.game == "base" and sens.strike_start_dz_m == 0.001
    cells = {p.spec.name: len(p.cells) for p in plan}
    g, s = len(GATES.players["guards"]), len(GATES.players["strikes"])
    dup = len(GATES.players["one_strike_duplicates"])
    assert cells["base"] == g * s == 30
    assert cells["size_1v1"] == cells["size_2v1"] == g * (s - dup) == 20
    assert cells["ctl_same_seed"] == min(GATES.run["cells_per_batch"], g * s)
    assert sum(n for k, n in cells.items() if GATES.group(k).role == "sweep") == 280
    # 3 tag-fires + 2 reach-fires + same seed (one base batch: cells_per_batch cells) + 5 stand-still + 4 still-both
    # + 10 tiny tag + 30 tag off
    assert sum(n for k, n in cells.items() if GATES.group(k).role == "control") == 54 + cells["ctl_same_seed"]
    fires = {g.name: g for g in GATES.groups if g.control in (sweep.TAG_FIRES, sweep.REACH_FIRES)}
    assert {(g.control, g.size) for g in fires.values()} == {(sweep.TAG_FIRES, "2v1"), (sweep.TAG_FIRES, "3v3"),
                                                            (sweep.TAG_FIRES, "5v3"), (sweep.REACH_FIRES, "1v1"),
                                                            (sweep.REACH_FIRES, "3v3")}
    for g in fires.values():
        cfg = sweep.variant_cfg(GATES, g.game)
        if g.control == sweep.TAG_FIRES:
            assert g.guards == g.strikes == ("zero",) and cfg.tag.radius_m > math.hypot(*cfg.arena.bands_m["lab"])
        else:
            assert g.guards == ("zero",) and g.strikes == ("strike_straight",) and cfg.tag.mode == "off"
    still = [g for g in GATES.groups if g.control == sweep.STILL_ZERO_TAGS]
    assert {g.size for g in still} == {"1v1", "2v1", "3v3", "5v3"} and all(g.guards == g.strikes == ("zero",) for g in still)
    assert all(g.ticks_cap(GATES.run) * TICK_S == 10.0 for g in still)                   # the lead's "first 10 s"
    for p in plan:                                    # batches: fixed, in cell order, at most cells_per_batch each
        assert tuple(c for b in p.batches for c in b) == p.cells
        assert all(len(b) <= GATES.run["cells_per_batch"] for b in p.batches)


def test_the_one_strike_duplicates_play_exactly_as_strike_straight():
    cfg = sweep.variant_cfg(GATES, "base")
    for guards in (1, 2):
        g = SvgGame(cfg, 32, guards, 1, device="cpu", seed=3, band=0)
        obs = g.reset()["strike"]
        ref = make_strategy("strike_straight", "strike", cfg, 32, "cpu", 0).act(obs)
        for name in GATES.players["one_strike_duplicates"]:
            p = make_strategy(name, "strike", cfg, 32, "cpu", 0)
            p.reset(torch.ones(32, dtype=torch.bool))
            assert torch.equal(p.act(obs), ref), name


def test_the_shortlist_rule_and_controls_are_written_down():
    sl = GATES.shortlist
    assert sl["max_variants"] == 3 and 0 < sl["trivial_at"] < 1 and sl["tie_window_games"] == 50
    assert set(sl["candidates"]) <= {g.name for g in GATES.groups if g.role == "sweep"}
    assert not set(sl["report_only"]) & set(sl["candidates"])
    assert set(GATES.controls["global_checks"]) == set(sweep.GLOBAL_CHECKS)
    assert {g.control for g in GATES.groups if g.role == "control"} <= set(sweep.CONTROL_KINDS)


def test_the_loader_refuses_unknown_keys(tmp_path):
    bad = tmp_path / "gates.toml"
    bad.write_text(sweep.GATES_FILE.read_text().replace("[run]\n", "[run]\nnonsense = 1\n", 1))
    with pytest.raises(ValueError, match="nonsense"):
        sweep.load_gates(bad)


# ================================================================================================ the sweep's game
def small_run(**changes) -> dict:
    run = dict(GATES.run, games_per_cell=6, ticks_cap=4, device="cpu")
    run.update(changes)
    return run


def test_tiled_starts_pair_every_cell_and_every_batch_size():
    cfg = sweep.variant_cfg(GATES, "base")
    one = sweep.SweepGame(cfg, 1, 7, 3, 3, device="cpu", seed=5)
    three = sweep.SweepGame(cfg, 3, 7, 3, 3, device="cpu", seed=5)
    ref = one.pos_m
    for k in range(3):
        assert torch.equal(three.pos_m[k * 7:(k + 1) * 7], ref)
    assert torch.equal(three.start_miss, one.start_miss.repeat(3))
    assert not torch.equal(ref[0], ref[1])                       # games inside a cell still differ


def test_the_batch_counts_tags_and_ends_per_first_game(monkeypatch):
    """Pure path (fast): a reference loop over the same game counts per first game what the batch reports."""
    cfg = sweep.variant_cfg(GATES, "tag_1p8").replace(**{"starling.enabled": False, "rules.game_steps": 200})
    cells = [("guard_mark_edge", "strike_straight"), ("guard_parked_centre", "strike_sacrifice")]
    run = small_run(games_per_cell=16, ticks_cap=200)
    res = sweep.play_batch(cfg, "3v3", cells, run)
    pg = res.per_game
    assert pg["tags"].max() <= 3 and pg["tags"].sum() > 0
    ended = pg["outcome"] != 0
    assert np.all(pg["strikes_left"][ended & (pg["outcome"] == GUARD_WIN) & (pg["end_step"] < 200)] == 0)
    assert np.all(pg["tags"] + pg["strikes_left"] <= 3)
    # reference: the same game and players stepped by hand
    g = sweep.SweepGame(cfg, 2, 16, 3, 3, device="cpu", seed=run["seed"])
    gs = sweep.split_players(cells, "guard", cfg, 16, "cpu", run["seed"])
    ss = sweep.split_players(cells, "strike", cfg, 16, "cpu", run["seed"])
    obs = g.reset()
    gs.reset(torch.ones(32, dtype=torch.bool))
    ss.reset(torch.ones(32, dtype=torch.bool))
    tags = torch.zeros(32, dtype=torch.long)
    done = torch.zeros(32, dtype=torch.bool)
    for _ in range(200):
        out = g.step({"guard": gs.act(obs["guard"]), "strike": ss.act(obs["strike"])})
        tags += (~done) * out.info["tagged"][:, 3:].sum(1)
        done |= out.done
        gs.reset(out.done)
        ss.reset(out.done)
        obs = out.obs
    assert np.array_equal(tags.numpy(), pg["tags"])
    assert len(res.rows) == 2 and res.rows[0]["games"] + res.rows[0]["unfinished"] == 16


def test_a_stop_request_ends_the_batch_at_once():
    cfg = sweep.variant_cfg(GATES, "base")
    calls = []

    def stop():
        calls.append(1)
        return len(calls) >= 3

    with pytest.raises(sweep.SweepStopped):
        sweep.play_batch(cfg, "3v3", [("guard_field", "strike_straight")], small_run(ticks_cap=50), should_stop=stop)
    assert len(calls) == 3


def test_same_seed_twice_gives_identical_outputs_on_the_cpu():
    cfg = sweep.variant_cfg(GATES, "base")
    cells = [("guard_field", "strike_converge"), ("guard_parked_ring", "strike_high")]
    a = sweep.play_batch(cfg, "3v3", cells, small_run())
    b = sweep.play_batch(cfg, "3v3", cells, small_run())
    ok, _ = sweep.check_same_seed(a.per_game, b.per_game, tol_m=0.0)
    assert ok and a.start_sha256 == b.start_sha256
    assert a.start_sha256[0] == a.start_sha256[1]                  # paired across the cells of the batch


# ================================================================================================ the controls (known answers)
def per_game(**arrays):
    n = len(next(iter(arrays.values())))
    base = {k: np.zeros(n, dtype=np.int64) for k in ("outcome", "end_step", "tags", "strikes_left", "guards_tagged",
                                                     "guards_removed")}
    base["closest_3d_m"] = np.ones(n)
    base["start_pos_m"] = np.zeros((n, 2, 3))
    base.update({k: np.asarray(v) for k, v in arrays.items()})
    return base


def test_same_seed_control_fails_on_any_count_difference_and_on_closest_beyond_the_tolerance():
    a = per_game(outcome=[1, 2], closest_3d_m=[1.2, 1.3])
    assert sweep.check_same_seed(a, per_game(outcome=[1, 2], closest_3d_m=[1.2, 1.3]), 0.0)[0]
    assert not sweep.check_same_seed(a, per_game(outcome=[2, 2], closest_3d_m=[1.2, 1.3]), 1.0)[0]
    assert sweep.check_same_seed(a, per_game(outcome=[1, 2], closest_3d_m=[1.2, 1.3 + 1e-7]), 1e-6)[0]
    assert not sweep.check_same_seed(a, per_game(outcome=[1, 2], closest_3d_m=[1.2, 1.3 + 1e-5]), 1e-6)[0]


def test_zero_tags_and_never_reaches_controls():
    assert sweep.check_zero_tags(per_game(tags=[0, 0]))[0]
    assert not sweep.check_zero_tags(per_game(tags=[0, 1]))[0]
    assert sweep.check_never_reaches(per_game(outcome=[GUARD_WIN, GUARD_WIN]))[0]
    assert not sweep.check_never_reaches(per_game(outcome=[GUARD_WIN, STRIKE_WIN]))[0]


def test_one_for_one_guards_tagged_equal_strikes_tagged_and_removed_at_survive_0():
    """QC I1: the invariant that can fail (the old tags <= min(G, S) could not at G >= S)."""
    ok = per_game(tags=[3, 1], guards_tagged=[3, 1], guards_removed=[3, 1])
    assert sweep.check_one_for_one(ok, 0.0)[0]
    assert not sweep.check_one_for_one(per_game(tags=[3], guards_tagged=[1], guards_removed=[1]), 0.0)[0]   # hit.any
    assert not sweep.check_one_for_one(per_game(tags=[2], guards_tagged=[2], guards_removed=[0]), 0.0)[0]   # survive
    assert sweep.check_one_for_one(per_game(tags=[2], guards_tagged=[2], guards_removed=[0]), 1.0)[0]
    assert not sweep.check_one_for_one(per_game(tags=[0], guards_tagged=[2], guards_removed=[0]), 1.0)[0]   # counter dead


def test_tag_fires_and_reach_fires_known_answers():
    good = per_game(tags=[3, 3], guards_tagged=[3, 3], guards_removed=[3, 3], end_step=[1, 1],
                    outcome=[GUARD_WIN, GUARD_WIN])
    assert sweep.check_tag_fires(good, 5, 3)[0]
    for broken in (dict(tags=[0, 0]), dict(guards_removed=[5, 5]), dict(guards_removed=[0, 0]), dict(end_step=[1, 2]),
                   dict(outcome=[GUARD_WIN, 0])):
        assert not sweep.check_tag_fires({**good, **{k: np.asarray(v) for k, v in broken.items()}}, 5, 3)[0], broken
    assert sweep.check_reach_fires(per_game(outcome=[STRIKE_WIN, STRIKE_WIN]))[0]
    assert not sweep.check_reach_fires(per_game(outcome=[STRIKE_WIN, 0]))[0]
    assert not sweep.check_reach_fires(per_game(outcome=[STRIKE_WIN, GUARD_WIN]))[0]


@pytest.mark.parametrize("size", ["2v1", "3v3", "5v3"])
def test_the_tag_fires_game_ends_every_game_at_step_1_with_min_g_s_tags(size):
    cfg = sweep.variant_cfg(GATES, "tag_10m")
    res = sweep.play_batch(cfg, size, (("zero", "zero"),), small_run(games_per_cell=32, ticks_cap=5))
    g, s = sweep.parse_size(size)
    assert sweep.check_tag_fires(res.per_game, g, s) == (True, sweep.check_tag_fires(res.per_game, g, s)[1])
    assert np.all(res.per_game["tags"] == min(g, s))


def test_paired_starts_control():
    assert sweep.check_paired_starts({("3v3", 6.5): {"a"}, ("5v3", 6.5): {"b"}})[0]
    assert not sweep.check_paired_starts({("3v3", 6.5): {"a", "c"}})[0]


# ================================================================================================ the shortlist rule
def matrix(group: str, holds: list[list[float]]) -> list[dict]:
    rows = []
    for gi, line in enumerate(holds):
        for si, h in enumerate(line):
            k = round(h * 1000)
            rows.append({"group": group, "guard": f"g{gi}", "strike": f"s{si}", "games": 1000, "holds": k,
                         "reaches": 1000 - k, "hold_rate": k / 1000, "reach_rate": (1000 - k) / 1000,
                         "hold_ci": [h - 0.03, h + 0.03], "reach_ci": [1 - h - 0.03, 1 - h + 0.03]})
    return rows


def meta(name, side=6.5, zone=1.6, tag=1.6, survive=0.0):
    return {"name": name, "arena_side_m": side, "zone_radius_m": zone, "tag_radius_m": tag, "survive": survive}


RULE = {"info_reference": {}, "always": [], "candidates": ["base", "a", "b", "c", "d"], "report_only": ["size"], "max_variants": 3, "trivial_at": 0.8,
        "tie_window_games": 50, "tie_breaks": ["lab_arena_first", "larger_zone_tag_margin", "lower_guard_survives",
                                           "run_order"]}


def test_maximin_values_and_the_exclusion_of_trivial_variants():
    rows = {"base": matrix("base", [[0.9, 0.85], [0.2, 0.1]]),    # g0 holds >= 0.85 against both: H = 0.85, trivial
            "a": matrix("a", [[0.6, 0.3], [0.4, 0.5]]),           # H = max(0.3, 0.4) = 0.4; R = max(min(.4,.6), min(.7,.5)) = 0.5
            "b": matrix("b", [[0.1, 0.05], [0.15, 0.1]]),         # R = max(min(.9,.85), min(.95,.9)) = 0.9: trivial for Strike
            "size": matrix("size", [[0.5, 0.5], [0.5, 0.5]])}
    out = sweep.shortlist(rows, {k: meta(k) for k in rows}, RULE, ["base", "a", "b", "size"])
    by = {v["variant"]: v for v in out["variants"]}
    assert math.isclose(by["base"]["H"], 0.85) and not by["base"]["eligible"]
    assert math.isclose(by["a"]["H"], 0.4) and math.isclose(by["a"]["R"], 0.5) and by["a"]["eligible"]
    assert by["a"]["g_star"] == "g1" and by["a"]["s_star"] == "s1" and math.isclose(by["a"]["d"], 0.5)
    assert not by["b"]["eligible"]
    assert out["shortlist"] == ["a"] and "size" not in by and out["report_only"][0]["variant"] == "size"


def test_ties_inside_the_window_follow_the_written_tie_breaks_and_at_most_three_are_kept():
    rows = {k: matrix(k, [[0.5, 0.5], [0.5, 0.5]]) for k in RULE["candidates"]}
    metas = {"base": meta("base"), "a": meta("a", side=7.5), "b": meta("b", zone=2.4), "c": meta("c", survive=1.0),
             "d": meta("d", tag=1.2)}
    out = sweep.shortlist(rows, metas, RULE, RULE["candidates"])
    # all d = 0.5: lab arena first (a last), then larger |zone - tag| (b 0.8, d 0.4, then base and c 0.0), then survive
    assert out["shortlist"] == ["b", "d", "base"]


def test_a_variant_with_missing_cells_is_not_a_candidate():
    rows = {"base": matrix("base", [[0.5, 0.5], [0.5, 0.5]]), "a": matrix("a", [[0.5, 0.5], [0.5, 0.5]])[:3]}
    out = sweep.shortlist(rows, {k: meta(k) for k in rows}, RULE, ["base", "a"], expected_cells={"base": 4, "a": 4})
    assert out["shortlist"] == ["base"]
    assert [v for v in out["variants"] if v["variant"] == "a"][0]["eligible"] is False


def test_every_group_of_the_real_plan_with_one_start_setting_draws_the_same_starts():
    """The paired_starts control of the real gate file, before any GPU time: per group, the first games' starts as the
    driver hashes them (construction draws once, play_match's reset draws again), at the real games per cell. Read
    through the game: no start geometry is typed here. Rerun after any change to the start draw (L0.10 fix)."""
    import hashlib
    by_setting = {}
    for p in sweep.build_plan(GATES):
        game, size = sweep.group_game(GATES, p.spec)
        cfg = sweep.variant_cfg(GATES, game)
        g, s = sweep.parse_size(size)
        dz = p.spec.strike_start_dz_m or 0
        sg = sweep.SweepGame(cfg, 1, GATES.run["games_per_cell"], g, s, device="cpu", seed=GATES.run["seed"],
                             strike_start_dz_m=dz)
        sg.reset()
        sha = hashlib.sha256(np.ascontiguousarray(sg.pos_m.numpy()).tobytes()).hexdigest()
        key = (size, cfg.arena.bands_m["lab"][0], cfg.starts.guard_disc_m, cfg.starts.strike_ring_m, dz)
        by_setting.setdefault(key, set()).add(sha)
    ok, detail = sweep.check_paired_starts(by_setting)
    assert ok, detail
    assert len(by_setting) == 6          # 1v1, 2v1, 3v3, 5v3 at 6.5 m, 3v3 in the 7.5 m arena, 3v3 with Strikes 1 mm up


def test_the_base_case_always_goes_to_l012_and_the_rule_adds_at_most_two():
    """LEAD CALL 21 Nov 2026: base is the reference for the proposed 1.6 m rules even when the rule rules it out."""
    rule = dict(RULE, always=["base"])
    rows = {"base": matrix("base", [[0.9, 0.85], [0.2, 0.1]]),           # H = 0.85: ruled out by the rule
            **{k: matrix(k, [[0.5, 0.5], [0.5, 0.5]]) for k in ("a", "b", "c", "d")}}
    metas = {"base": meta("base"), "a": meta("a", side=7.5), "b": meta("b", zone=2.4), "c": meta("c", survive=1.0),
             "d": meta("d", tag=1.2)}
    out = sweep.shortlist(rows, metas, rule, RULE["candidates"])
    assert out["shortlist"] == ["base", "b", "d"]
    base = [v for v in out["variants"] if v["variant"] == "base"][0]
    assert base["reference"] and base["reason"].startswith("reference, ruled out because Guard-trivial looking")
    good = dict(rows, base=matrix("base", [[0.5, 0.5], [0.5, 0.5]]))
    out = sweep.shortlist(good, metas, rule, RULE["candidates"])
    assert out["shortlist"] == ["base", "b", "d"]                    # base never counts against the two added
    assert [v for v in out["variants"] if v["variant"] == "base"][0]["reason"] == "reference (eligible)"
    assert GATES.shortlist["always"] == ["base"] and GATES.shortlist["max_variants"] == 3


def test_the_strike_start_offset_is_off_by_default_bit_for_bit_and_moves_only_strike_heights():
    cfg = sweep.variant_cfg(GATES, "base")
    plain = sweep.SweepGame(cfg, 2, 8, 3, 3, device="cpu", seed=4)
    zero = sweep.SweepGame(cfg, 2, 8, 3, 3, device="cpu", seed=4, strike_start_dz_m=0.0)
    up = sweep.SweepGame(cfg, 2, 8, 3, 3, device="cpu", seed=4, strike_start_dz_m=GATES.group("sens_strike_dz_1mm").strike_start_dz_m)
    assert torch.equal(plain.pos_m, zero.pos_m) and torch.equal(plain.start_miss, zero.start_miss)
    assert torch.equal(up.pos_m[..., :2], plain.pos_m[..., :2]) and torch.equal(up.pos_m[:, :3], plain.pos_m[:, :3])
    dz = (up.pos_m[:, 3:, 2] - plain.pos_m[:, 3:, 2])
    assert torch.allclose(dz, torch.full_like(dz, 0.001), atol=1e-6)
    cells = (("guard_field", "strike_straight"),)
    run = small_run(ticks_cap=3)
    a = sweep.play_batch(cfg, "3v3", cells, run)
    b = sweep.play_batch(cfg, "3v3", cells, run, strike_start_dz_m=0.0)
    assert sweep.check_same_seed(a.per_game, b.per_game, 0.0)[0]


def test_ties_compare_whole_games_anchored_on_the_highest_d_with_less_or_equal():
    """QC I5 (LEAD CALL 21 Nov 2026): window 50 games of 1,000, compared on integer counts with <=, clusters anchored on
    the highest d left. QC's float edge (gaps of exactly 20 games) cannot occur with counts; 50 games exactly is a tie."""
    def flat_matrix(name, hold):
        return matrix(name, [[hold, hold], [hold, hold]])
    metas = {"a": meta("a", side=7.5), "b": meta("b", zone=2.4), "c": meta("c", tag=1.2)}
    rule = dict(RULE, candidates=["a", "b", "c"])
    # d = min(1 - H, 1 - R) with H = hold, R = 1 - hold: hold 0.45 -> d 0.45 (450 games), 0.40 -> 400
    rows = {"a": flat_matrix("a", 0.45), "b": flat_matrix("b", 0.40), "c": flat_matrix("c", 0.399)}
    out = sweep.shortlist(rows, metas, rule, ["a", "b", "c"])
    by = {v["variant"]: v for v in out["variants"]}
    assert by["a"]["d_games"] == 450 and by["b"]["d_games"] == 400 and by["c"]["d_games"] == 399
    assert out["shortlist"] == ["b", "a", "c"]      # 450 - 400 = 50: tied, lab arena first; c is 51 below a: next cluster
    rows["b"] = flat_matrix("b", 0.399)                                                     # 51 games: not tied any more
    assert sweep.shortlist(rows, metas, rule, ["a", "b", "c"])["shortlist"][0] == "a"


def test_the_cuda_smoke_gate_keeps_the_sweeps_settings_and_qcs_minimums():
    """QC I6 / section 5 B: the smoke plays the sweep's own settings and game files, every control kind, at least 2 cells
    per batch, 256 games per cell and 600 ticks on its short groups, and replays one whole base batch at full length."""
    smoke = sweep.load_gates(sweep.ROOT / "configs" / "ste_l011" / "cuda_smoke_gates.toml")
    for part in ("run", "players", "controls", "projection", "games", "confounds"):
        assert getattr(smoke, part) == getattr(GATES, part), part
    assert smoke.run["device"] == "cuda" and smoke.run["cells_per_batch"] >= 2 and smoke.run["games_per_cell"] >= 256
    assert {g.control for g in smoke.groups if g.role == "control"} == set(sweep.CONTROL_KINDS)
    plan = {p.spec.name: p for p in sweep.build_plan(smoke)}
    base, replay = plan["base"], plan["ctl_same_seed"]
    assert base.spec.ticks is None and replay.batches[0] == base.batches[0]
    assert len(base.batches[0]) == smoke.run["cells_per_batch"] and smoke.run["ticks_cap"] == 2400
    short = [p for p in plan.values() if p.spec.ticks is not None and p.spec.control not in (
        sweep.TAG_FIRES, sweep.REACH_FIRES, sweep.STILL_ZERO_TAGS)]
    assert short and all(p.spec.ticks >= 600 for p in short)
    assert {p.spec.role for p in plan.values()} == {"sweep", "control", "sensitivity"}


def test_the_tag_off_cells_are_an_info_reference_never_shortlisted():
    """LEAD CALL 21 Nov 2026 (QC M-8): the 30 tag-off base cells are reported as the INFO reference "no proximity tag"
    with H, R and d, and never shortlisted (the tag rule, P1, is the owner's at G0)."""
    assert GATES.shortlist["info_reference"] == {"ctl_tag_off": "no proximity tag"}
    assert "ctl_tag_off" not in GATES.shortlist["candidates"] + GATES.shortlist["report_only"]
    rule = dict(RULE, info_reference={"off": "no proximity tag"})
    rows = {"a": matrix("a", [[0.6, 0.3], [0.4, 0.5]]), "off": matrix("off", [[0.5, 0.5], [0.5, 0.5]])}
    out = sweep.shortlist(rows, {"a": meta("a"), "off": meta("off", tag=math.inf)}, dict(rule, candidates=["a"]), ["a", "off"])
    assert out["shortlist"] == ["a"]                                   # off has the larger d, but is never shortlisted
    ref = out["info_reference"][0]
    assert ref["variant"] == "off" and ref["label"] == "no proximity tag" and ref["d_games"] == 500
    assert ref["reason"].startswith("INFO reference") and "rank" not in ref


# ================================================================================================ follow-ups (T44 QC read)
def test_hold_composition_counts_guards_left_and_game_length():
    """QC check 2: Guards left = G - Guards removed by tags (drop-outs are off in every L0.11 game); game length over the
    finished games, in seconds."""
    pg = per_game(outcome=[GUARD_WIN, GUARD_WIN, STRIKE_WIN, GUARD_WIN, 0], guards_removed=[3, 2, 1, 3, 0],
                  end_step=[20, 40, 60, 2400, 7])
    hc = sweep.hold_composition({**pg, "game_ticks": 2400}, guards=3)
    assert hc["holds_no_guard_left"] == 2 and math.isclose(hc["guards_left_mean_in_holds"], 1 / 3)
    assert hc["timeouts_by_length"] == 1                                # the 2,400-tick game ran to the time-out
    assert math.isclose(hc["length_median_s"], 50 * TICK_S) and hc["length_p90_s"] > hc["length_median_s"]
    none = sweep.hold_composition(per_game(outcome=[STRIKE_WIN], guards_removed=[0], end_step=[30]), guards=3)
    assert none["holds_no_guard_left"] == 0 and none["guards_left_mean_in_holds"] is None
    empty = sweep.hold_composition(per_game(outcome=[0], guards_removed=[0], end_step=[0]), guards=3)
    assert empty["length_median_s"] is None


def test_play_batch_rows_carry_the_hold_composition():
    cfg = sweep.variant_cfg(GATES, "tag_10m")
    res = sweep.play_batch(cfg, "3v3", (("zero", "zero"),), small_run(games_per_cell=8, ticks_cap=3))
    row = res.rows[0]
    assert row["holds_no_guard_left"] == 8 and row["guards_left_mean_in_holds"] == 0.0    # 3-for-3 trades at step 1
    assert row["length_median_s"] == TICK_S
