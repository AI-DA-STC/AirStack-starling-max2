"""Route 3, stage LS1, task LS1-M4-T1: the gate loader takes the LS1.4 reading rule and lists the new fills
(``ste/exploit.py``; plan ste_learning/drafts/LS1_TASK_PLAN.md section 5, with the design check's corrections).

* ``[reading]`` (``margin_pooled``, ``margin_cell``, ``last_reads``, ``strike_read``) is REQUIRED in a net gate file
  (``[learner] skill_source = "net"``) and refused in every other one, so the reader never sees ``reading = None`` for a
  net; every committed gate file (none is net) loads as before.
* Every key is required, with no default. The two margins are a float in (0, 1) or a ``FILL_`` mark (R38: the owner
  sets them); ``last_reads`` is an int >= 1 and ``strike_read`` is ``"run0"``, both written filled (the design check's
  recommendation for the M4-T1 / M4-T4 contradiction: neither takes a ``FILL_`` mark).
* ``unfilled()`` also lists ``[run0] skills_reach_min``, ``[learner.skill_net] <side>.sha256`` and the ``[reading]``
  margins while they hold ``FILL_``; the loader accepts a ``FILL_`` ``skills_reach_min`` (and still checks it when
  filled); the driver's preflight refuses such a file ("not filled yet").

Task LS1-M4-T1b (owner R46: option B of OQ-1, a run 0 for each Strike seed on both arms): an optional
``variants.<v>.run0_seed``, read only under ``[run0] per_variant = true``; run 0 of that variant trains it and records
it in learner_control.json; every run0_seed is a seed of its own (the tests after the LS1-M4-T1b banner).

Every net gate file is written by ``tests/_ste_ls1.net_gates_text``; the ``[reading]`` values come from ``STAND_IN``
(synthetic, constraint 5), never typed. CPU only, no network is built."""
import json
import re
import sys
import tomllib

import pytest

import _ste_ls1 as H
from _ste_ls1 import ROOT, SKILLS_GATES, STAND_IN, net_gates_text
from svg_training.ste import exploit, skills

sys.path.insert(0, str(ROOT / "scripts"))
import ste_exploit_l012 as driver  # noqa: E402

CONFIGS = ROOT / "configs"
# The 13 committed gate files that exploit.load_gates loads at d70b4e01 (configs/ste_ls1/ excluded: none of its files
# is an exploit gate file).
COMMITTED = ("ste_l012/gates.toml", "ste_l012/smoke_gates.toml", "ste_l012b/gates.toml", "ste_l012c/guard_gates.toml",
             "ste_l012c/strike_gates.toml", "ste_l1/l110_gates.toml", "ste_l1/l111_strike_gates.toml",
             "ste_l1/l113_gates.toml", "ste_l1/l19_gates.toml", "ste_l3/skills_gates.toml",
             "ste_l3/skills_poolonly_gates.toml", "ste_l3/velocity_gates.toml", "ste_l3/velocity_poolonly_gates.toml")
L19_FILLS = ["[reference] sha256", "[reference] start_sha256", "[reference] t44_gates_sha256", "[reference] t44_record",
             "[reference] t44_run"]
MARGINS = ("margin_pooled", "margin_cell")
SHA = "0" * 64                                   # a well-formed sha256 (no network is loaded here)
FILL_SHA = "FILL_after_LS1.2"
FILL_MARGIN = "FILL_the_owner_sets_it"
FILL_REACH = "FILL_from_the_ceiling"
REACH_LINE = re.compile(r"(?m)^skills_reach_min = .*$")


def nets(sha: str = SHA) -> dict:
    return {side: (f"ste_provisional/skill_nets/x/skill_net_{side}.pt", sha) for side in skills.SIDE_KEYS}


def reading_text(**over) -> str:
    """A ``[reading]`` block: ``STAND_IN["reading"]`` with ``over`` on top (a value None drops the key)."""
    table = {**STAND_IN["reading"], **over}
    return "\n[reading]\n" + "".join(f"{k} = {H.toml_value(v)}\n" for k, v in table.items() if v is not None)


def write(tmp_path, text: str, name: str = "gates.toml"):
    path = tmp_path / name
    path.write_text(text)
    return path


def net_text(sha: str = SHA, reading: str | None = None, base: str | None = None) -> str:
    """A net gate file's text on the skills gate file: ``[reading]`` from ``STAND_IN`` (``reading`` None) or the given
    block."""
    base = SKILLS_GATES.read_text() if base is None else base
    if reading is None:
        return net_gates_text(base, nets(sha), reading=True)
    return net_gates_text(base, nets(sha), reading=False) + reading


# ================================================================================================ 1. off = as before
@pytest.mark.parametrize("name", COMMITTED)
def test_every_committed_gate_file_loads_as_before(name):
    g = exploit.load_gates(CONFIGS / name)
    assert g.reading is None and g.learner.skill_source == skills.SCRIPTS_SOURCE
    assert exploit.unfilled(g) == (L19_FILLS if name == "ste_l1/l19_gates.toml" else [])


# ================================================================================================ 2. required keys
def test_reading_keys_are_required_without_defaults(tmp_path):
    assert set(exploit.READING_KEYS) == set(STAND_IN["reading"])
    g = exploit.load_gates(write(tmp_path, net_text()))
    assert g.reading == STAND_IN["reading"]
    for key in exploit.READING_KEYS:                                    # each one missing
        with pytest.raises(ValueError, match=rf"missing key\(s\) in \[reading\]: \['{key}'\]"):
            exploit.load_gates(write(tmp_path, net_text(reading=reading_text(**{key: None})), f"no_{key}.toml"))
    with pytest.raises(ValueError, match=r"unknown key\(s\) in \[reading\]"):
        exploit.load_gates(write(tmp_path, net_text(reading=reading_text(extra=STAND_IN["reading"]["last_reads"])),
                                 "extra.toml"))
    bad = [(m, v) for m in MARGINS for v in (0, 0.0, 1, 1.0, 1.5, -0.5, True, "high", "fill_lower", [0.5])]
    bad += [("last_reads", v) for v in (0, -1, 1.5, True, "3", FILL_MARGIN)]
    bad += [("strike_read", v) for v in ("final", "", 0, FILL_MARGIN)]
    for i, (key, value) in enumerate(bad):
        with pytest.raises(ValueError, match=rf"\[reading\] {key}"):
            exploit.load_gates(write(tmp_path, net_text(reading=reading_text(**{key: value})), f"bad_{i}.toml"))


# ================================================================================================ 3. net only
def test_a_net_gate_file_needs_reading_and_a_scripts_one_refuses_it(tmp_path):
    with pytest.raises(ValueError, match=r"\[reading\]"):              # a net file without [reading]
        exploit.load_gates(write(tmp_path, net_gates_text(SKILLS_GATES.read_text(), nets(), reading=False), "n.toml"))
    for name in ("ste_l3/skills_gates.toml", "ste_l3/velocity_gates.toml", "ste_l012/smoke_gates.toml"):
        text = (CONFIGS / name).read_text() + "\n" + H.reading_block()     # a scripts (or velocity) file with it
        with pytest.raises(ValueError, match=r"\[reading\]"):
            exploit.load_gates(write(tmp_path, text, name.replace("/", "_")))
    assert H.READING_IN_NET_FILES is True and "[reading]" in net_gates_text(SKILLS_GATES.read_text(), nets())


# ================================================================================================ 4. the fills
def test_a_fill_placeholder_loads_and_is_listed(tmp_path):
    base = REACH_LINE.sub(f'skills_reach_min = "{FILL_REACH}"', SKILLS_GATES.read_text())
    assert base != SKILLS_GATES.read_text()
    text = net_text(FILL_SHA, reading_text(margin_pooled=FILL_MARGIN, margin_cell=FILL_MARGIN), base=base)
    g = exploit.load_gates(write(tmp_path, text))
    assert g.run0["skills_reach_min"] == FILL_REACH and g.reading["margin_cell"] == FILL_MARGIN
    todo = ["[run0] skills_reach_min", "[learner.skill_net] strike.sha256", "[learner.skill_net] guard.sha256",
            "[reading] margin_pooled", "[reading] margin_cell"]
    assert exploit.unfilled(g) == todo
    args = driver.parse(["--gates", str(tmp_path / "gates.toml"), "--variant", "base", "--side", "guard", "--run-dir",
                         str(tmp_path / "r"), "--cap-h", "1", "--pilot-json", str(tmp_path / "pilot.json")])
    why = driver.preflight(args, g)
    assert why is not None and "not filled yet" in why and all(t in why for t in todo)
    # each fill alone is listed alone; a filled file lists nothing
    assert exploit.unfilled(exploit.load_gates(write(tmp_path, net_text(), "filled.toml"))) == []
    one = exploit.load_gates(write(tmp_path, net_text(reading=reading_text(margin_cell=FILL_MARGIN)), "one.toml"))
    assert exploit.unfilled(one) == ["[reading] margin_cell"]
    scripts = exploit.load_gates(write(tmp_path, base, "scripts.toml"))     # the scripts route takes the mark too
    assert scripts.reading is None and exploit.unfilled(scripts) == ["[run0] skills_reach_min"]
    with pytest.raises(ValueError, match="skills_reach_min"):              # a string that is not the mark: refused
        exploit.load_gates(write(tmp_path, REACH_LINE.sub('skills_reach_min = "fill_later"', base), "lower.toml"))


# ================================================================================================ 5. from the file
def test_reading_values_come_from_the_file(tmp_path):
    for i, block in enumerate((reading_text(), reading_text(margin_pooled=FILL_MARGIN),
                               reading_text(last_reads=STAND_IN["reading"]["last_reads"] + 1))):
        text = net_text(reading=block)
        g = exploit.load_gates(write(tmp_path, text, f"g{i}.toml"))
        assert g.reading == tomllib.loads(text)["reading"]


# ================================================================================================ LS1-M4-T1b
# A run 0 seed per variant (owner R46: option B of OQ-1): ``variants.<v>.run0_seed``, optional, read only under
# ``[run0] per_variant = true`` (refused otherwise); absent, run 0 trains ``[run0] train_seed`` as today. Every
# ``run0_seed`` is a seed of its own: not a variant's ``train_seed``, ``[run0] train_seed``, another variant's
# ``run0_seed``, ``curve_seed``, ``clip_seed`` or ``[pool] seed`` (the loader), nor the scoring starts' seed (the
# driver's preflight, which loads the reference). The tests use the committed smoke gate file (CPU-sized); every seed
# is read from the file, and a fresh one is one above the file's largest.
SMOKE = CONFIGS / "ste_l012" / "smoke_gates.toml"
RUN0_HEADER = re.compile(r"(?m)^\[run0\]\n")


@pytest.fixture
def scratch_shared(tmp_path, monkeypatch):
    from svg_training.ste import shared
    monkeypatch.setenv(shared.SHARED_ENV, str(tmp_path / "shared"))
    monkeypatch.setenv(shared.LEGACY_LOGS_ENV, "")


def smoke_seeds() -> dict:
    """Every seed of the smoke gate file, by where it sits (read from the file)."""
    g = exploit.load_gates(SMOKE)
    out = {f"variants.{v}.train_seed.{side}": s for v, t in g.variants.items() for side, s in t["train_seed"].items()}
    return {**out, "[run0] train_seed": g.run0["train_seed"], "[run] curve_seed": g.run["curve_seed"],
            "[run] clip_seed": g.run["clip_seed"]}


FRESH = max(smoke_seeds().values()) + 1          # a seed the smoke file does not hold


def run0_seed_text(seeds: dict, per_variant: bool = True, pool_seed: int | None = None, base: str | None = None) -> str:
    """The smoke gate file's text with ``run0_seed`` written into the named ``[variants]`` lines (variant -> seed),
    ``[run0] per_variant`` set (or left absent) and an optional ``[pool]`` table (off) holding ``pool_seed``."""
    text = SMOKE.read_text() if base is None else base
    for variant, seed in seeds.items():
        line = f"{variant} = {{ run0_seed = {H.toml_value(seed)}, "
        text, k = re.subn(rf"(?m)^{variant} = \{{ (?=game = )", line, text, count=1)     # the [variants] line only
        assert k == 1, variant
    if per_variant:
        text, k = RUN0_HEADER.subn("[run0]\nper_variant = true\n", text, count=1)
        assert k == 1
    if pool_seed is not None:
        text += f"\n[pool]\nenabled = false\nseed = {pool_seed}\n"
    return text


def test_without_the_key_run0_trains_the_run0_seed_of_every_committed_file():
    for name in COMMITTED:
        g = exploit.load_gates(CONFIGS / name)
        assert all("run0_seed" not in v for v in g.variants.values())
        assert {exploit.run0_seed(g, v) for v in g.variants} == {g.run0["train_seed"]}, name


def test_beside_a_variant_with_the_key_the_others_keep_run0_train_seed(tmp_path):
    """The heads gate file's shape under R46: per_variant, the first variant without the key, the second with it."""
    g = exploit.load_gates(write(tmp_path, run0_seed_text({"tag_1p2": FRESH})))
    assert exploit.run0_seed(g, "tag_1p2") == FRESH
    assert exploit.run0_seed(g, "base") == exploit.run0_seed(g, "tag_1p4") == smoke_seeds()["[run0] train_seed"]


@pytest.mark.usefixtures("scratch_shared")
def test_per_variant_run0_trains_its_own_seed(tmp_path, monkeypatch):
    seeds = []
    real = driver.build_learner

    def spy(gates, variant, side, num_games, seed, *a, **k):
        seeds.append(seed)
        return real(gates, variant, side, num_games, seed, *a, **k)

    monkeypatch.setattr(driver, "build_learner", spy)
    pj = tmp_path / "pilot.json"
    pj.write_text(json.dumps({"strike_recipe": {"recipe": exploit.RECIPE_BARE, "side_overrides_strike": {}}}))
    own = write(tmp_path, run0_seed_text({"base": FRESH}), "own.toml")
    assert exploit.run0_seed(exploit.load_gates(own), "base") == FRESH
    for gates, rd, want in ((own, tmp_path / "r0_own", FRESH),                   # the variant's own run 0 seed
                            (SMOKE, tmp_path / "r0_plain", smoke_seeds()["[run0] train_seed"])):   # no key: as today
        before = len(seeds)
        assert driver.main(["--run0", "--gates", str(gates), "--variant", "base", "--run-dir", str(rd), "--cap-h", "1",
                            "--no-videos", "--pilot-json", str(pj)]) == 0
        assert seeds[before:] == [want]
        assert json.loads((rd / driver.RUN0_FILE).read_text())["train_seed"] == want


REPEATS = [*smoke_seeds(), "variants.tag_1p2.run0_seed", "[pool] seed"]


@pytest.mark.parametrize("where", REPEATS)
def test_a_run0_seed_that_repeats_a_seed_is_refused(tmp_path, where):
    assert exploit.load_gates(write(tmp_path, run0_seed_text({"base": FRESH}, pool_seed=FRESH + 1), "ok.toml"))
    if where == "variants.tag_1p2.run0_seed":
        text = run0_seed_text({"base": FRESH, "tag_1p2": FRESH})
    elif where == "[pool] seed":
        text = run0_seed_text({"base": FRESH}, pool_seed=FRESH)
    else:
        text = run0_seed_text({"base": smoke_seeds()[where]})
    with pytest.raises(ValueError, match=r"run0_seed .* is another seed of the gate file"):
        exploit.load_gates(write(tmp_path, text))


def test_a_run0_seed_that_is_the_scoring_starts_seed_is_refused_by_preflight(tmp_path):
    ref = exploit.load_reference(exploit.ROOT / exploit.load_gates(SMOKE).reference["file"])
    start = int(ref.meta["seed"])
    for i, variant in enumerate(("base", "tag_1p2")):          # the run's own variant, and another one of the file
        g = exploit.load_gates(write(tmp_path, run0_seed_text({variant: start}), f"g{i}.toml"))
        args = driver.parse(["--run0", "--gates", g.path, "--variant", "base", "--run-dir", str(tmp_path / f"r{i}"),
                             "--cap-h", "1", "--pilot-json", str(tmp_path / "pilot.json")])
        why = driver.preflight(args, g)
        assert why is not None and "run0_seed" in why and "scoring starts' seed" in why


@pytest.mark.parametrize("value", [True, "1", 1.5, [1]])
def test_a_run0_seed_is_an_int(tmp_path, value):
    with pytest.raises(ValueError, match="run0_seed"):
        exploit.load_gates(write(tmp_path, run0_seed_text({"base": value})))


def test_run0_seed_without_per_variant_is_refused(tmp_path):
    for i, text in enumerate((run0_seed_text({"base": FRESH}, per_variant=False),
                              RUN0_HEADER.sub("[run0]\nper_variant = false\n",
                                              run0_seed_text({"base": FRESH}, per_variant=False), count=1))):
        with pytest.raises(ValueError, match=r"run0_seed .*per_variant"):
            exploit.load_gates(write(tmp_path, text, f"g{i}.toml"))
