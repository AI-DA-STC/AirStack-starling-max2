"""STE task L0.12 Best-response test, the library (source/svg_training/ste/exploit.py): the gate file, the script
baselines by code, the evaluation batch on T44's own starts (positive control: game for game on the CPU), the held
command of the learner, the untrained exploiter's known answer, and the verdict arithmetic. CPU only, small."""
import math
import sys

import numpy as np
import pytest
import torch

from _ste_tools import SCRIPTS
from svg_training.core.metrics import wilson_interval
from svg_training.core.rewards import GUARD_WIN, STRIKE_WIN
from svg_training.ste import exploit, sweep

sys.path.insert(0, str(SCRIPTS))
import ste_l011_followups as fu  # noqa: E402

GAMES = 24          # first games of T44's 1,000 starts: enough to see play, seconds on the CPU


@pytest.fixture(scope="module")
def gates():
    return exploit.load_gates()


@pytest.fixture(scope="module")
def ref(gates):
    return exploit.load_reference(exploit.ROOT / gates.reference["file"])


# ------------------------------------------------------------------------------------------------ the gate file
def test_the_gate_file_loads_and_pins_the_l011_game_files(gates):
    assert gates.run["task"] == "L0.12"
    assert set(gates.variants) == {"base", "tag_1p2", "tag_1p4"}
    assert not exploit.game_file_problems(gates)
    l011 = sweep.load_gates()
    for name, ref_ in gates.games.items():
        assert ref_ == l011.games[name], name                        # the very files T44 played, same sha256


def test_the_gate_file_refuses_unknown_and_missing_keys(tmp_path):
    text = exploit.GATES_FILE.read_text()
    bad = tmp_path / "g.toml"
    bad.write_text(text.replace("\n[verdict]\n", "\n[verdict]\nsurprise = 1\n", 1))
    with pytest.raises(ValueError, match="surprise"):
        exploit.load_gates(bad)
    bad.write_text(text.replace("band = ", "bend = ", 1))
    with pytest.raises(ValueError, match="bend"):          # unknown bend, missing band: refused
        exploit.load_gates(bad)


def test_the_decision_period_is_the_sheets_twelve_ticks(gates):
    assert gates.trainer["decision_ticks"] == fu.decision_ticks() == 12


def test_the_trainer_settings_are_t41s_recipe(gates):
    import tomllib
    p1b = tomllib.loads((exploit.ROOT / "configs" / "nus_phase5.toml").read_text())["pilot_p1b"]
    for key in ("rollouts", "learning_epochs", "mini_batches", "learning_rate", "hidden", "init_log_std",
                "discount_factor", "gae_lambda", "entropy_loss_scale", "value_loss_scale", "ratio_clip", "value_clip",
                "grad_norm_clip", "zero_mean_init", "shaping_weight"):
        assert gates.trainer[key] == p1b[key], key
    assert gates.trainer["frozen_log_std_axes"] == p1b["frozen_log_std_axes"]["starling"]


def test_the_training_seeds_never_draw_the_scoring_starts(gates, ref):
    seeds = [s for v in gates.variants.values() for s in v["train_seed"].values()]
    assert len(set(seeds)) == len(seeds) == 2 * len(gates.variants)
    assert ref.meta["seed"] not in seeds and gates.run["curve_seed"] not in seeds


# ------------------------------------------------------------------------------------------------ cells and baselines
def test_the_evaluation_batch_layout(gates):
    s_cells = exploit.eval_cells(gates, "base", "strike")
    assert s_cells[0] == ("guard_mark_edge", exploit.EXPLOITER) and s_cells[1] == ("guard_mark_edge", "zero")
    assert s_cells[2:] == [("guard_mark_edge", s) for s in gates.players["strikes"]]
    g_cells = exploit.eval_cells(gates, "tag_1p4", "guard")
    assert g_cells[0] == (exploit.EXPLOITER, "strike_low") and g_cells[1] == ("zero", "strike_low")
    assert g_cells[2:] == [(g, "strike_low") for g in gates.players["guards"]]


def test_the_script_baseline_is_the_best_script_on_the_same_starts(gates, ref):
    b = exploit.script_baseline(gates, ref, "base", "strike")
    assert b["cell"] == ("guard_mark_edge", "strike_straight") and (b["k"], b["n"]) == (192, 1000)
    b = exploit.script_baseline(gates, ref, "base", "guard")
    assert b["cell"] == ("guard_mark_edge", "strike_straight") and (b["k"], b["n"]) == (808, 1000)
    b = exploit.script_baseline(gates, ref, "tag_1p4", "guard")
    assert b["cell"] == ("guard_mirror", "strike_low") and b["k"] == 672
    b = exploit.script_baseline(gates, ref, "tag_1p2", "strike")
    assert b["cell"] == ("guard_field", "strike_straight") and b["k"] == 355


# ------------------------------------------------------------------------------------------------ the evaluation game
def test_the_replay_of_t44s_starts_is_t44_game_for_game_on_the_cpu(gates, ref):
    """Positive control at small size: the evaluation path replays the base maximin cell and a parked cell from T44's
    starts; outcome, end step, tags and Strike drones left equal T44's in every game."""
    cfg = exploit.variant_cfg(gates, "base")
    cells = [("guard_mark_edge", "strike_straight"), ("guard_parked_centre", "strike_flank")]
    pg = exploit.play_cells(cfg, "3v3", ref, cells, GAMES, device="cpu", seed=ref.meta["seed"],
                            ticks_cap=gates.run["ticks_cap"])
    for k, cell in enumerate(cells):
        mine = exploit.slice_cell(pg, k, GAMES)
        t44 = {key: v[:GAMES] for key, v in ref.cell("base", *cell).items()}
        assert exploit.agreement(mine, t44)["differ"] == 0, cell
    assert pg["start_sha256"][0] == exploit.starts_sha(ref.starts_m[:GAMES])


def test_the_learners_held_command_is_the_follow_ups_hold_bit_for_bit():
    class Counter:
        team, name = "guard", "counter"

        def __init__(self):
            self.k = 0

        def reset(self, games):
            pass

        def act(self, obs):
            self.k += 1
            return torch.full((obs.shape[0], 1, 4), float(self.k))
    a, b = exploit.HeldPlayer(Counter(), 3), fu.HoldPlayer(Counter(), 3)
    for p in (a, b):
        p.reset(torch.ones(2, dtype=torch.bool))
    for k in range(7):
        if k == 4:
            for p in (a, b):
                p.reset(torch.tensor([False, True]))
        assert torch.equal(a.act(torch.zeros(2, 1, 1)), b.act(torch.zeros(2, 1, 1)))


def test_hold_1_is_the_player_itself():
    from svg_training.opponents.scripted import make_strategy
    cfg = exploit.variant_cfg(exploit.load_gates(), "base")
    p = make_strategy("guard_mark_edge", "guard", cfg, 3, "cpu", 0)
    h = exploit.HeldPlayer(make_strategy("guard_mark_edge", "guard", cfg, 3, "cpu", 0), 1)
    h.reset(torch.ones(3, dtype=torch.bool))
    obs = torch.randn(3, 3, 71)
    assert torch.equal(h.act(obs), p.act(obs))


def test_a_zero_mean_learner_commands_exactly_zero_and_plays_as_the_zero_script(gates, ref):
    """The untrained exploiter's known answer (negative control): zero-mean start -> mean action exactly 0 for every
    observation, so it plays game for game as the ``zero`` script, on either side."""
    torch.manual_seed(0)
    team = exploit.LearnerTeam.untrained("strike", 3, list(gates.trainer["hidden"]), "cpu")
    assert torch.equal(team.act(torch.randn(5, 3, 71)), torch.zeros(5, 3, 4))
    cfg = exploit.variant_cfg(gates, "base")
    cells = exploit.eval_cells(gates, "base", "strike")[:2]           # exploiter, zero
    pg = exploit.play_cells(cfg, "3v3", ref, cells, GAMES, device="cpu", seed=ref.meta["seed"],
                            ticks_cap=gates.run["ticks_cap"], learner=team, hold_ticks=12)
    a, b = exploit.slice_cell(pg, 0, GAMES), exploit.slice_cell(pg, 1, GAMES)
    assert exploit.agreement(a, b)["differ"] == 0
    assert int(np.sum(a["outcome"] == STRIKE_WIN)) == 0               # still Strike drones never reach (ctl_stand_still)


def test_one_for_one_holds_in_an_evaluation(gates, ref):
    cfg = exploit.variant_cfg(gates, "tag_1p2")
    pg = exploit.play_cells(cfg, "3v3", ref, [("guard_field", "strike_straight")], 8, device="cpu",
                            seed=ref.meta["seed"], ticks_cap=gates.run["ticks_cap"])
    assert np.array_equal(pg["guards_removed"], pg["tags"])
    assert int(pg["nonfinite_actions"].sum()) == 0


# ------------------------------------------------------------------------------------------------ the verdict arithmetic
def test_a_gain_is_real_only_when_the_wilson_intervals_do_not_overlap():
    g = exploit.gain((300, 1000), (192, 1000))
    lo, hi = wilson_interval(192, 1000)
    assert g["script"]["ci"] == [lo, hi] and g["gain"] == pytest.approx(0.108)
    assert g["real"] is True
    assert exploit.gain((215, 1000), (192, 1000))["real"] is False      # 0.215 lies inside 192's interval
    assert exploit.gain((100, 1000), (192, 1000))["real"] is False


def test_a_side_that_did_not_learn_is_inconclusive_and_falls_back_to_the_script():
    side = exploit.side_result("strike", trained=(5, 1000), untrained=(0, 1000), script=(192, 1000))
    assert side["learned"] is False and side["status"] == exploit.SIDE_INCONCLUSIVE
    assert side["better"]["who"] == "script" and side["better"]["k"] == 192
    side = exploit.side_result("strike", trained=(400, 1000), untrained=(0, 1000), script=(192, 1000))
    assert side["learned"] is True and side["status"] == exploit.SIDE_GAIN and side["better"]["who"] == "exploiter"
    side = exploit.side_result("guard", trained=(700, 1000), untrained=(534, 1000), script=(808, 1000))
    assert side["learned"] is True and side["status"] == exploit.SIDE_WEAK_BELOW and side["better"]["who"] == "script"


def test_the_variant_band_is_read_on_the_better_of_script_and_exploiter(gates):
    band = gates.verdict["band"]
    assert band == 0.2
    strike = exploit.side_result("strike", trained=(150, 1000), untrained=(0, 1000), script=(170, 1000))
    guard = exploit.side_result("guard", trained=(700, 1000), untrained=(500, 1000), script=(830, 1000))
    assert exploit.variant_verdict(strike, guard, band)["category"] == exploit.GUARD_TRIVIAL    # 0.170 upper 0.195
    strike = exploit.side_result("strike", trained=(150, 1000), untrained=(0, 1000), script=(192, 1000))
    assert exploit.variant_verdict(strike, guard, band)["category"] == exploit.WORTH_LEARNING   # 192 upper 0.218
    guard = exploit.side_result("guard", trained=(150, 1000), untrained=(100, 1000), script=(160, 1000))
    strike = exploit.side_result("strike", trained=(800, 1000), untrained=(0, 1000), script=(840, 1000))
    assert exploit.variant_verdict(strike, guard, band)["category"] == exploit.STRIKE_TRIVIAL
    assert math.isclose(exploit.variant_verdict(strike, guard, band)["guard_upper"], wilson_interval(160, 1000)[1])


def test_controls_compare_counts_with_the_device_tolerance(gates):
    a = {"outcome": np.array([1, 2, 2, 2], dtype=np.int8), "end_step": np.array([5, 6, 7, 8]),
         "tags": np.array([0, 3, 3, 3]), "strikes_left": np.array([3, 0, 0, 0])}
    b = {k: v.copy() for k, v in a.items()}
    assert exploit.replay_ok(a, b, "cpu", gates.controls)[0]
    b["end_step"][0] = 9
    assert not exploit.replay_ok(a, b, "cpu", gates.controls)[0]          # CPU: game for game, nothing may differ
    assert exploit.replay_ok(a, b, "cuda", gates.controls)[0]             # CUDA: counts within the stated tolerance
    b["outcome"][:] = GUARD_WIN
    assert exploit.replay_ok(a, b, "cuda", dict(gates.controls, replay_count_tol_cuda_games=0))[0] is False


def test_side_overrides_default_to_the_t41_recipe_and_only_take_known_keys(gates, tmp_path):
    assert gates.trainer["side_overrides"] == {"strike": {}, "guard": {}}
    text = exploit.GATES_FILE.read_text().replace("side_overrides = { strike = {}, guard = {} }",
                                                   "side_overrides = { strike = { learning_rate = 1.0 }, guard = {} }")
    bad = tmp_path / "g.toml"
    bad.write_text(text)
    with pytest.raises(ValueError, match="learning_rate"):
        exploit.load_gates(bad)
    assert exploit.side_settings(gates, "strike") == {k: v for k, v in gates.trainer.items() if k != "side_overrides"}


def test_the_pilot_probes_name_known_settings(gates):
    for probe in gates.pilot["probes"]:
        assert probe["side"] in exploit.SIDES
        assert set(probe) - {"side", "opponent"} <= set(exploit.OVERRIDE_KEYS)
    assert {"side": "strike", "opponent": "guard_parked_centre"} in gates.pilot["probes"]   # the Strike learner's positive control


def test_the_zero_mean_head_is_the_phase_5_pilots_rule():
    from svg_training.nus import pilot as nus_pilot
    from svg_training.opponents.learned import StandinPolicy
    torch.manual_seed(3)
    a = StandinPolicy([16, 16], "cpu")
    b = StandinPolicy([16, 16], "cpu")
    b.load_state_dict(a.state_dict())
    exploit.zero_mean_head(a)
    nus_pilot.zero_mean_head(b)
    assert all(torch.equal(x, y) for x, y in zip(a.state_dict().values(), b.state_dict().values()))


def test_the_smoke_gate_file_differs_from_the_real_one_only_in_sizes():
    import tomllib
    real = tomllib.loads(exploit.GATES_FILE.read_text())
    smoke = tomllib.loads((exploit.ROOT / "configs" / "ste_l012" / "smoke_gates.toml").read_text())
    sizes = {("run", "device"), ("run", "eval_games"), ("run", "ticks_cap"), ("run", "curve_games"),
             ("trainer", "num_games"), ("trainer", "game_steps_per_run"), ("trainer", "rollouts"),
             ("trainer", "learning_epochs"), ("trainer", "mini_batches"), ("trainer", "curve_every_updates"),
             ("trainer", "final_reserve_s"), ("videos", "games"), ("videos", "keep"), ("videos", "max_ticks"),
             ("pilot", "num_games"), ("pilot", "updates"), ("pilot", "probes"), ("pilot", "probe_num_games"),
             ("pilot", "probe_updates")}
    assert real.keys() == smoke.keys()
    for section in real:
        assert real[section].keys() == smoke[section].keys(), section
        for key in real[section]:
            if (section, key) not in sizes:
                assert real[section][key] == smoke[section][key], (section, key)


# ------------------------------------------------------------------------------------------------ the lead's rulings (21 Nov)
def test_the_strike_fallback_is_pre_registered_and_is_the_only_recipe_change(gates):
    assert gates.trainer["strike_fallback"] == {"shaping_weight": 1.0}
    assert gates.trainer["strike_fallback_label"] == "shaped Strike recipe"
    assert gates.verdict["strike_no_signal"] == "the T41 recipe gives the Strike no learning signal in this game"
    probes = [{k: v for k, v in p.items()} for p in gates.pilot["probes"]]
    assert probes == [{"side": "strike"}, {"side": "strike", "opponent": "guard_parked_centre"},
                      {"side": "strike", "shaping_weight": 1.0},
                      {"side": "strike", "shaping_weight": 1.0, "opponent": "guard_parked_centre"}]
    assert gates.trainer["side_overrides"] == {"strike": {}, "guard": {}}


def test_the_strike_recipe_decision_follows_the_pilot_probes_against_g_star_only(gates):
    """LEAD CALL 21 Nov 2026: the probe against g* (the Strike's training opponent) decides; the parked-Guard probes are
    information only."""
    def probe(shaped, reaches, parked=False):
        p = {"side": "strike", **({"shaping_weight": 1.0} if shaped else {}),
             **({"opponent": "guard_parked_centre"} if parked else {})}
        return {**p, "updates": [{"reaches": r, "ended": 100} for r in reaches]}

    def probes(bare_g, bare_parked, shaped_g, shaped_parked):
        return [probe(False, bare_g), probe(False, bare_parked, True), probe(True, shaped_g),
                probe(True, shaped_parked, True)]
    assert exploit.strike_recipe(gates, probes([0, 1], [0, 0], [0, 0], [0, 0]))["recipe"] == exploit.RECIPE_BARE
    d = exploit.strike_recipe(gates, probes([0, 0], [5, 9], [0, 3], [0, 0]))      # a parked reach does not decide
    assert d["recipe"] == exploit.RECIPE_SHAPED and d["side_overrides_strike"] == {"shaping_weight": 1.0}
    assert d["bare_reaches"] == 0 and d["bare_reaches_parked_info"] == 14
    d = exploit.strike_recipe(gates, probes([0, 0], [4, 4], [0, 0], [7, 7]))
    assert d["recipe"] == exploit.RECIPE_NOT_LAUNCHED and d["side_overrides_strike"] is None
    with pytest.raises(ValueError, match="against g"):
        exploit.strike_recipe(gates, [probe(False, [1], True), probe(True, [1])])


def test_tag_1p4_scores_strike_straight_as_an_evaluation_only_opponent(gates):
    assert gates.variants["tag_1p4"]["extra_eval_opponents"] == {"strike": [], "guard": ["strike_straight"]}
    for v in ("base", "tag_1p2"):
        assert gates.variants[v]["extra_eval_opponents"] == {"strike": [], "guard": []}
    assert "strike_low" in gates.players["z_up_info"]
    assert gates.players["z_up_label"] == "tier 1 vertical response not fitted (s2b.toml z_up_info)"


# ------------------------------------------------------------------------------------------------ QC fix round 1
def test_a_learned_exploiter_without_a_real_gain_reads_weak(gates):
    """QC I-2 (wording, no rule change): learned but no real gain over the script reads "weak (learned, below the
    script)" when the exploiter's rate is below the script's, "weak (learned, not clearly above the script)" otherwise."""
    below = exploit.side_result("strike", trained=(10, 1000), untrained=(0, 1000), script=(192, 1000))
    assert below["status"] == exploit.SIDE_WEAK_BELOW == "weak (learned, below the script)"
    above = exploit.side_result("strike", trained=(200, 1000), untrained=(0, 1000), script=(192, 1000))
    assert above["status"] == exploit.SIDE_WEAK_NOT_ABOVE
    assert exploit.side_result("strike", trained=(400, 1000), untrained=(0, 1000), script=(192, 1000))["status"] == \
        exploit.SIDE_GAIN


def test_the_learner_positive_control_rule(gates):
    """QC I-1(b), LEAD CALL 21 Nov 2026: the parked-Guard probe's trained Strike reaches at least the scripted
    strike_straight's rate against the parked Guard on the same starts minus 0.05 (point estimates)."""
    lc = gates.pilot["learner_control"]
    assert lc == {"opponent": "guard_parked_centre", "script": "strike_straight", "margin": 0.05,
                  "game_steps_fraction": 0.1, "game_steps_if_unfilled": 25_000_000, "cap_gpu_h": 0.15}
    assert exploit.learner_control((417, 1000), (466, 1000), lc["margin"])["pass"] is True
    assert exploit.learner_control((415, 1000), (466, 1000), lc["margin"])["pass"] is False
    assert exploit.learner_control((0, 0), (466, 1000), lc["margin"])["pass"] is False


def test_the_gate_states_no_follow_up_seeds_and_the_category_is_set_by_t44s_scripts(gates, ref):
    """QC I-7 and I-8: no follow-up seeds; every best script's Wilson upper bound is already above the band, so the
    category reads "worth learning" whatever training does (the gain is the measure); the gate says so."""
    assert gates.verdict["follow_up_seeds"] == []
    for v in gates.variants:
        for side in exploit.SIDES:
            b = exploit.script_baseline(gates, ref, v, side)
            assert wilson_interval(b["k"], b["n"])[1] > gates.verdict["band"], (v, side)
    text = exploit.GATES_FILE.read_text()
    assert "INCONCLUSIVE is final for L0.12" in text and "the category alone is uninformative" in text


def test_the_final_reserve_is_measured_and_floored(gates):
    """QC I-3: training stops while the cap left still holds final_reserve_factor x (the main and INFO batches, each
    timed as this run's own controls batch, plus clip_reserve_s), and never less than final_reserve_s."""
    assert gates.trainer["final_reserve_factor"] == 2.0 and gates.trainer["clip_reserve_s"] > 0
    assert exploit.final_reserve_s(gates.trainer, 0.0) == gates.trainer["final_reserve_s"]
    assert exploit.final_reserve_s(gates.trainer, 1000.0) == 2.0 * (2 * 1000.0 + gates.trainer["clip_reserve_s"])



# ------------------------------------------------------------------------------------------------ lead's items after round 1
def test_the_learner_control_probe_budget_is_pre_registered(gates):
    """LEAD CALL: ONE longer probe after the recipe is chosen: 10 % of game_steps_per_run as filled, else a fixed 25 M
    game-steps, capped at 0.15 GPU-h of effective time."""
    unfilled = exploit.learner_control_budget(gates)
    assert gates.trainer["game_steps_per_run"] == 0
    assert unfilled["game_steps"] == 25_000_000 and unfilled["cap_s"] == 0.15 * 3600
    filled = exploit.learner_control_budget(gates.__class__(**{**gates.__dict__,
                                                               "trainer": dict(gates.trainer, game_steps_per_run=300_000_000)}))
    assert filled["game_steps"] == 30_000_000


def test_the_learner_control_reads_only_on_the_long_probe_and_a_capped_probe_is_inconclusive():
    ok = exploit.learner_control((430, 1000), (466, 1000), 0.05)
    assert exploit.learner_control_status(ok, reached_budget=True) == "PASS"
    assert exploit.learner_control_status(ok, reached_budget=False) == "INCONCLUSIVE"
    bad = exploit.learner_control((100, 1000), (466, 1000), 0.05)
    assert exploit.learner_control_status(bad, reached_budget=True) == "FAIL"


def _pilot(recipe, overrides, status):
    return {"strike_recipe": {"recipe": recipe, "side_overrides_strike": overrides},
            "learner_control": {"status": status}}


def test_runs_and_the_verdict_are_tied_to_the_pilot(gates):
    """M-4 (LEAD CALL): a run of record names the pilot it follows. Refused when the learner control is not PASS (unless
    the lead's decision is given), when the Strike recipe of the gate differs from the pilot's, or for a Strike run the
    pilot said not to launch; --strike-not-launched only when the pilot said so."""
    ok = _pilot(exploit.RECIPE_BARE, {}, "PASS")
    assert exploit.pilot_problem(gates, ok, "strike") is None and exploit.pilot_problem(gates, ok, "guard") is None
    assert "learner control" in exploit.pilot_problem(gates, _pilot(exploit.RECIPE_BARE, {}, "FAIL"), "guard")
    assert exploit.pilot_problem(gates, _pilot(exploit.RECIPE_BARE, {}, "INCONCLUSIVE"), "guard",
                                 accepted="lead decided 21 Nov: probe too short, go") is None
    shaped = _pilot(exploit.RECIPE_SHAPED, {"shaping_weight": 1.0}, "PASS")
    assert "side_overrides" in exploit.pilot_problem(gates, shaped, "strike")       # the gate still says {}
    assert exploit.pilot_problem(gates, shaped, "guard") is None                    # the Guard recipe does not depend on it
    gone = _pilot(exploit.RECIPE_NOT_LAUNCHED, None, "PASS")
    assert "not launched" in exploit.pilot_problem(gates, gone, "strike")
    assert exploit.strike_not_launched_problem(gone) is None
    assert "not" in exploit.strike_not_launched_problem(ok)
