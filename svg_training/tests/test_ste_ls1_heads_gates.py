"""Route 3, stage LS1, task LS1-M4-T4 (plan ste_learning/drafts/LS1_TASK_PLAN.md, section 5): the two gate files of
LS1.4. Nothing is played.

* ``configs/ste_ls1/heads_gates.toml``: head training on the skill network (route 3), a template whose fills
  (``FILL_``) are set after LS1.2 (the two network shas), M4-T3 (the run 0 mark) and the owner (the two margins of
  ``[reading]``, R38). Option B of OQ-1 (owner R46): a run 0 per variant (``[run0] per_variant``), ``base_s2``'s own
  ``run0_seed``.
* ``configs/ste_ls1/skills_seed2_gates.toml``: route 2's second seed (the scripts), complete at M4.

Both are ``configs/ste_l3/skills_gates.toml`` with only the named keys changed, so the two arms share the recipe, the
game-step budget, the pool draws and the scoring starts, and pair seed by seed. The fill assertions hold before and
after the fills (the pattern of tests/test_ste_ls1_distil_gates.py ``test_limits_are_numbers_or_fill``): a value is a
``FILL_`` mark or a valid value, and ``unfilled`` lists exactly the marks. CPU only."""
import json
import tomllib

from svg_training.ste import exploit, skills
from svg_training.ste.config import load_ste_learning

ROOT = exploit.ROOT
SKILLS = ROOT / "configs" / "ste_l3" / "skills_gates.toml"
HEADS = ROOT / "configs" / "ste_ls1" / "heads_gates.toml"
SEED2 = ROOT / "configs" / "ste_ls1" / "skills_seed2_gates.toml"
ROUTE2_LEARNER = ROOT / "records" / "evidence" / "2026-11-25_ste_l3_l6_pipeline" / "l3_run0_skills_learner_control.json"
SECOND = "base_s2"                                     # heads' second variant: the base game, route 2 seed 2's seeds
NAMED_FILLS = {"[run0] skills_reach_min", "[learner.skill_net] strike.sha256", "[learner.skill_net] guard.sha256",
               *(f"[reading] {k}" for k in exploit.READING_MARGINS)}
ROUTE2_SEED1_RUN0 = 140203                             # route 2 seed 1's run 0 (configs/ste_l3/skills_gates.toml)
SECOND_RUN0 = 140213                                   # C8: the second seed's run 0, both arms (R46, option B)


def _data(path) -> dict:
    return tomllib.loads(path.read_text())


def _is_fill(v) -> bool:
    return isinstance(v, str) and v.startswith(exploit.FILL_MARK)


def _seeds(g: exploit.ExploitGates) -> list[int]:
    out = [int(s) for v in g.variants.values() for s in v["train_seed"].values()]
    out += [exploit.run0_seed(g, v) for v in g.variants]
    out += [int(g.run["curve_seed"]), int(g.run["clip_seed"]), int(g.pool["seed"])]
    return out


def test_heads_differs_from_skills_gates_in_the_named_keys_only():
    """Pop the named keys (plan M4-T4 and the design check under option B): [run] task, the two route 3 learner keys,
    variant base_s2, [verdict] order, [run0] skills_reach_min and per_variant, [reading]; the rest is route 2's file key
    for key, so route 2's recipe is pinned as filled (the pilot is a check, M4-T2) and the budget, pool, controls and
    pilot are the same."""
    heads, route2 = _data(HEADS), _data(SKILLS)
    for d in (heads, route2):
        d["run"].pop("task")
        d["verdict"].pop("order")
        d["run0"].pop("skills_reach_min")
    assert heads["learner"].pop("skill_source") == skills.NET_SOURCE
    assert sorted(heads["learner"].pop("skill_net")) == sorted(skills.SIDE_KEYS)
    second = heads["variants"].pop(SECOND)
    assert heads["run0"].pop("per_variant") is True
    assert sorted(heads.pop("reading")) == sorted(exploit.READING_KEYS)
    assert heads == route2
    assert heads["trainer"]["side_overrides"]["strike"] == {}
    for key in ("game_steps_per_run", "num_games", "decision_ticks"):
        assert heads["trainer"][key] == route2["trainer"][key]
    for section in ("pool", "controls", "pilot", "reference", "games", "players"):
        assert heads[section] == route2[section], section
    # base_s2 is the base variant with route 2 seed 2's seeds, read on the base reference cells, its own run 0
    base = heads["variants"]["base"]
    own = {"train_seed", "role", "reference_variant", "run0_seed"}
    assert {k: v for k, v in second.items() if k not in own} == {k: v for k, v in base.items() if k not in own}
    assert second["reference_variant"] == "base" and "run0_seed" not in base


def test_seed2_differs_in_task_and_seeds_only():
    seed2, route2 = _data(SEED2), _data(SKILLS)
    assert seed2["run"]["task"] == "LS1.4"
    for d in (seed2, route2):
        d["run"].pop("task")
        d["variants"]["base"].pop("train_seed")
        d["run0"].pop("train_seed")
    assert seed2 == route2
    assert list(seed2["variants"]) == ["base"]


def test_seeds_pair_across_arms():
    """Both arms train on the same seeds, the same pool draws and the same curve and clip starts: heads' base is route
    2 seed 1 (skills_gates.toml), heads' base_s2 is route 2 seed 2 (skills_seed2_gates.toml)."""
    heads, route2, seed2 = (exploit.load_gates(p) for p in (HEADS, SKILLS, SEED2))
    assert heads.variants["base"]["train_seed"] == route2.variants["base"]["train_seed"]
    assert heads.variants[SECOND]["train_seed"] == seed2.variants["base"]["train_seed"]
    assert heads.variants[SECOND]["train_seed"] != heads.variants["base"]["train_seed"]
    for g in (route2, seed2):
        assert g.pool == heads.pool
        assert (g.run["curve_seed"], g.run["clip_seed"]) == (heads.run["curve_seed"], heads.run["clip_seed"])
    for g in (heads, seed2):
        assert len(set(_seeds(g))) == len(_seeds(g))                    # within a file, every seed its own
    assert not set(seed2.variants["base"]["train_seed"].values()) & set(route2.variants["base"]["train_seed"].values())


def test_each_run0_seed_pairs_across_arms():
    """Option B (owner R46): a run 0 per Strike seed on both arms. Heads' base run 0 = route 2 seed 1's (140203);
    heads' base_s2 run 0 = skills_seed2's run 0 (140213), distinct from every other heads seed."""
    heads, route2, seed2 = (exploit.load_gates(p) for p in (HEADS, SKILLS, SEED2))
    assert heads.run0["per_variant"] is True and heads.run0["variant"] == "base"
    assert exploit.run0_seed(heads, "base") == exploit.run0_seed(route2, "base") == ROUTE2_SEED1_RUN0
    assert exploit.run0_seed(heads, SECOND) == exploit.run0_seed(seed2, "base") == SECOND_RUN0
    others = [s for s in _seeds(heads)]
    others.remove(SECOND_RUN0)
    assert SECOND_RUN0 not in others
    assert exploit.ref_variant(heads, SECOND) == "base"


def test_both_load_and_name_only_the_fills():
    heads, seed2 = exploit.load_gates(HEADS), exploit.load_gates(SEED2)
    assert exploit.unfilled(seed2) == []
    assert set(exploit.unfilled(heads)) <= NAMED_FILLS
    for g in (heads, seed2):
        assert exploit.game_file_problems(g) == []
        assert g.run["task"] == "LS1.4"
    assert heads.learner.skill_source == skills.NET_SOURCE and seed2.learner.skill_source == skills.SCRIPTS_SOURCE
    assert seed2.reading is None
    # the run 0 mark: a share in (0, 1] or the mark of M4-T3's net ceiling, listed while it is one
    mark = heads.run0["skills_reach_min"]
    assert _is_fill(mark) == ("[run0] skills_reach_min" in exploit.unfilled(heads))
    for side, entry in heads.learner.skill_net.items():
        assert _is_fill(entry["sha256"]) == (f"[learner.skill_net] {side}.sha256" in exploit.unfilled(heads))


def test_the_task_is_in_the_route_budget():
    cfg, _ = load_ste_learning()
    for path in (HEADS, SEED2):
        g = exploit.load_gates(path)
        assert cfg.budget_of(g.run["task"]).section == "budget_ls"
        assert cfg.cap_gpu_h(g.run["task"]) > 0


def test_route2_pilot_table_equals_seed2_table():
    """Route 2's L3.3 [learner] table (the committed evidence copy of its run 0's learner_control.json; the pilot's
    table equals it, ``pilot_problem``) is skills_seed2's, so that pilot is accepted for the second seed; heads'
    table carries the network, so the same pilot is refused there (``skills_pilot_problem``). The pilot.json itself
    is not in this worktree (runs/ is not in git), so the evidence copy stands in for it, with no skip."""
    route2 = json.loads(ROUTE2_LEARNER.read_text())["learner"]
    seed2, heads = exploit.load_gates(SEED2), exploit.load_gates(HEADS)
    assert route2 == skills.learner_table(seed2.learner)
    assert route2 == skills.learner_table(exploit.load_gates(SKILLS).learner)
    assert skills.learner_table(heads.learner) != route2
    assert skills.learner_table(heads.learner)["skill_source"] == skills.NET_SOURCE


def test_heads_has_reading_with_every_key():
    """F8: the four keys present. The two margins are the owner's (R38): a ``FILL_`` mark until the owner sets them,
    then a float in (0, 1); ``last_reads`` and ``strike_read`` are written filled (never a mark). ``unfilled`` lists
    exactly the margins that still hold a mark."""
    heads = exploit.load_gates(HEADS)
    reading = heads.reading
    assert reading == _data(HEADS)["reading"]
    assert sorted(reading) == sorted(exploit.READING_KEYS)
    for key in exploit.READING_MARGINS:
        v = reading[key]
        assert _is_fill(v) or (isinstance(v, float) and 0.0 < v < 1.0), key
    assert not _is_fill(reading["last_reads"]) and not _is_fill(reading["strike_read"])
    assert isinstance(reading["last_reads"], int) and reading["last_reads"] >= 1
    assert reading["strike_read"] in exploit.STRIKE_READS
    listed = [u for u in exploit.unfilled(heads) if u.startswith("[reading]")]
    assert listed == [f"[reading] {k}" for k in exploit.READING_KEYS if _is_fill(reading[k])]
    assert set(listed) <= {f"[reading] {k}" for k in exploit.READING_MARGINS}
    text = HEADS.read_text()
    assert "W3" in text and "OP-30" in text and "curve.json" in text      # the departure from workflow section 6


def test_a_filled_copy_of_heads_has_no_fill_left(tmp_path):
    """The template's marks are its only gaps: with every mark of the named fills replaced (synthetic values, not the
    owner's) the file loads and ``unfilled`` is empty, so nothing else waits for a fill."""
    text = HEADS.read_text()
    filled = _data(HEADS)
    synthetic = {("run0", "skills_reach_min"): 0.5, ("reading", "margin_pooled"): 0.25,
                 ("reading", "margin_cell"): 0.25}
    for (section, key), value in synthetic.items():
        old = filled[section][key]
        if _is_fill(old):
            text = text.replace(f'{key} = "{old}"', f"{key} = {value}", 1)
            filled[section][key] = value
    for side in skills.SIDE_KEYS:
        old = filled["learner"]["skill_net"][side]["sha256"]
        if _is_fill(old):
            text = text.replace(f'"{old}"', f'"{"0" * 64}"', 1)
            filled["learner"]["skill_net"][side]["sha256"] = "0" * 64
    out = tmp_path / "heads_gates.toml"
    out.write_text(text)
    assert tomllib.loads(text) == filled
    assert exploit.unfilled(exploit.load_gates(out)) == []
