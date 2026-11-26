"""LS1-M4-T5: ``scripts/ste_ls1_read.py``, the read of LS1.4 (plan ste_learning/drafts/LS1_TASK_PLAN.md, section 5;
option B, owner R46: a run 0 per training pair on both arms, so the Strike read is two pairs against two).

Synthetic folders with known answers (no training, no game played): route 2 on its two committed gate files
(``configs/ste_l3/skills_gates.toml``, ``configs/ste_ls1/skills_seed2_gates.toml``), route 3 on a ``tmp_path`` copy of
``configs/ste_ls1/heads_gates.toml`` whose ``FILL_`` marks are filled with synthetic values: the two margins from
``STAND_IN`` (constraint 5; never a typed PROPOSED value), a synthetic run 0 mark and synthetic network shas. The rule's
edges are tested twice: on exact fractions in the pure rule (exactly at the margin), and through ``main`` on the count
grid of 1,000 games (just met, one count past). Every refusal exits 2 and names what it refused. The fake-folder
helpers live here: no other test uses them. CPU only."""
import json
import re
import sys
import tomllib
from fractions import Fraction
from math import ceil
from pathlib import Path

import numpy as np
import pytest

from _ste_ls1 import STAND_IN
from _ste_tools import SCRIPTS
from svg_training.core.rewards import GUARD_WIN, STRIKE_WIN
from svg_training.ste import compare, exploit, jobs, pool, skills

sys.path.insert(0, str(SCRIPTS))
import ste_ls1_read as reader  # noqa: E402

ROOT = exploit.ROOT
HEADS = ROOT / "configs" / "ste_ls1" / "heads_gates.toml"
N = 1000                                   # the gate files' eval_games: the count grid of the read
ARMS, PAIRS = ("route2", "route3"), ("s1", "s2")
REACH_MIN = 0.0613                         # a synthetic run 0 mark (off the 0.001 grid), not the ceiling's
NET_SHAS = {"guard": "c" * 64, "strike": "d" * 64}       # synthetic network shas
LEVEL = re.compile(r"(?i)\blevel\b")
PLANTED = "trained two-level Strike (synthetic free text)"   # a fake folder's free text: the scan is not vacuous
READS = 5                                  # reads per run 0 (checkpoints 10, 20, ..., 50)
CURVE = [100, 180, 150, 220, 210]          # Guard curve.json reads (k of 256)
STRIKE = {("route2", "s1"): 640, ("route2", "s2"): 600, ("route3", "s1"): 640, ("route3", "s2"): 600}
GUARD = {("route2", "s1"): 800, ("route2", "s2"): 780, ("route3", "s1"): 800, ("route3", "s2"): 780}


# ------------------------------------------------------------------------------------------------ the gate files
def _once(text: str, old: str, new: str) -> str:
    assert text.count(old) == 1, f"{old!r} occurs {text.count(old)} times, not once"
    return text.replace(old, new, 1)


def heads_text(reading: bool = True, fill: str | None = None, edits=()) -> str:
    """The committed heads gate file with its ``[reading]`` section replaced, always, by ``STAND_IN``'s four keys (read
    at call time, so a monkeypatched value reaches the file; the committed margins never reach the arithmetic,
    constraint 5), and its other ``FILL_`` marks filled (a value already filled is kept): ``REACH_MIN``, ``NET_SHAS``
    and a dated net folder. ``fill``: that margin written as a ``FILL_`` mark. ``reading`` False leaves the section out.
    ``edits``: (old, new) replacements, each of a text found once."""
    text = HEADS.read_text()
    data = tomllib.loads(text)

    def is_fill(v) -> bool:
        return isinstance(v, str) and v.startswith(exploit.FILL_MARK)

    if is_fill(data["run0"]["skills_reach_min"]):
        text = _once(text, f'skills_reach_min = "{data["run0"]["skills_reach_min"]}"',
                     f"skills_reach_min = {REACH_MIN!r}")
    for side in skills.SIDE_KEYS:
        entry = data["learner"]["skill_net"][side]
        old = f'file = "{entry["file"]}", sha256 = "{entry["sha256"]}"'
        file = entry["file"].replace(exploit.FILL_MARK + "DATE", "2026-12-01")
        sha = NET_SHAS[side] if is_fill(entry["sha256"]) else entry["sha256"]
        text = _once(text, old, f'file = "{file}", sha256 = "{sha}"')
    text = text[:text.index("\n[reading]")] + "\n"          # [reading] is the file's last section
    if reading:
        values = {k: (f"{exploit.FILL_MARK}TEST" if k == fill else v) for k, v in STAND_IN["reading"].items()}
        text += "\n[reading]\n" + "".join(f"{k} = {json.dumps(v)}\n" for k, v in values.items())
    for old, new in edits:
        text = _once(text, old, new)
    return text


def use_heads(monkeypatch, path: Path) -> None:
    for pair in PAIRS:
        monkeypatch.setitem(reader.GATE_FILES["route3"], pair, path)


def gates_of(arm: str, pair: str):
    return exploit.load_gates(reader.GATE_FILES[arm][pair])


# ------------------------------------------------------------------------------------------------ the fake folders
def write(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj))


def edit(path: Path, fn) -> None:
    """Load the JSON file at ``path``, let ``fn`` change it in place, write it back."""
    data = json.loads(path.read_text())
    fn(data)
    path.write_text(json.dumps(data))


def make_pilot(folder: Path, gates) -> Path:
    if folder.exists():                    # route 2's two pairs share the L3.3 pilot
        return folder
    ctl = {"ctl_reference_replay_pilot": {"status": "PASS"}}
    recipe = {"side_overrides_strike": gates.trainer["side_overrides"]["strike"]}
    write(folder / "pilot.json", {"gates_sha256": gates.sha256, "learner": skills.learner_table(gates.learner),
                                  "eval": {"per_side": {"guard": {"controls": ctl}, "strike": {"controls": ctl}}},
                                  "strike_recipe": recipe})
    (folder / "pilot.md").write_text("pilot\n")
    (folder / jobs.EXIT_FILE).write_text("0\n")
    return folder


def make_run0(folder: Path, gates, variant: str, ks: list[int]) -> Path:
    marks = [10 * (i + 1) for i in range(len(ks))]
    reads = [{"update": u, "game_steps": u * 1000, "trained": {"k": k, "n": N, "rate": k / N, "ci": [0.0, 1.0]},
              "threshold": REACH_MIN, "pass": True} for u, k in zip(marks, ks)]
    write(folder / "learner_control.json", {
        "what": "run 0", "status": "PASS", "rule": PLANTED, "reads": reads, "variant": variant,
        "opponent": gates.run0["opponent"], "recipe": exploit.recipe_label(gates, "strike", variant),
        "train_seed": exploit.run0_seed(gates, variant), "checkpoints": marks, "updates": marks[-1],
        "budget_reached": True, "gates_sha256": gates.sha256, "cap_h": 0.6,
        "learner": skills.learner_table(gates.learner), "complete": True})
    write(folder / "controls.json", {"ctl_reference_replay": {"status": "PASS"}})
    (folder / jobs.EXIT_FILE).write_text("0\n")
    return folder


def cell_wins(side: str, ks: dict, seed: int) -> dict:
    """{opponent: bool [N]} with exactly ``ks[opponent]`` wins, at starts drawn from ``seed``."""
    rng = np.random.default_rng(seed)
    out = {}
    for o, k in ks.items():
        w = np.zeros(N, dtype=bool)
        w[rng.permutation(N)[:k]] = True
        out[o] = w
    return out


def opponents(gates, side: str) -> list:
    return list(gates.players["strikes" if side == "guard" else "guards"])


def make_main(folder: Path, gates, variant: str, side: str, ks: dict, seed: int) -> Path:
    """A run of record of ``side``: results.json, eval_info.npz (the INFO batch: one cell per script of the other
    team, ``ks`` {opponent: wins}), curve.json, controls.json, exit_code."""
    opps = opponents(gates, side)
    wins = cell_wins(side, ks, seed)
    won, lost = (GUARD_WIN, STRIKE_WIN) if side == "guard" else (STRIKE_WIN, GUARD_WIN)
    folder.mkdir(parents=True)
    np.savez_compressed(folder / "eval_info.npz",
                        outcome=np.concatenate([np.where(wins[o], won, lost) for o in opps]).astype(np.int64))
    key = (lambda o: f"{o} v {exploit.EXPLOITER}") if side == "strike" else (lambda o: f"{exploit.EXPLOITER} v {o}")
    members = pool.pool_members(gates.players, "strike" if side == "guard" else "guard")
    names = skills.team_skills(gates.players, side)
    game = gates.games[gates.variants[variant]["game"]]
    write(folder / "results.json", {
        "what": PLANTED, "complete": True, "side": side, "variant": variant, "gates_sha256": gates.sha256,
        "eval_games": N, "budget_reached": True, "train_seed": int(gates.variants[variant]["train_seed"][side]),
        "recipe": exploit.recipe_label(gates, side, variant), "learner": skills.learner_table(gates.learner),
        "reference": {k: gates.reference[k] for k in ("file", "sha256", "start_sha256", "t44_gates_sha256")},
        "game_file": {"file": str(game.file), "sha256": game.sha256},
        "info": {key(o): {"games": N} for o in opps},
        "pooled": {"rate": float(np.mean([wins[o].mean() for o in members]))},
        "best_single_choice": {"best": names[0], "per_choice": {nm: {"rate": 0.5} for nm in names}},
        "choice_by_decision": {o: {"bins": ["0", "1+"], "counts": [10, 30],
                                   "share": {nm: [1.0 if j == 0 else 0.0, 1.0 if j == 1 else 0.0]
                                             for j, nm in enumerate(names)}} for o in opps}})
    write(folder / "curve.json", [{"update": 10 * (i + 1), "k": k, "n": 256, "rate": k / 256}
                                  for i, k in enumerate(CURVE)])
    write(folder / "controls.json", {"ctl_reference_replay_final": {"status": "PASS"},
                                     "ctl_paired_starts_info": {"status": "PASS"}})
    (folder / jobs.EXIT_FILE).write_text("0\n")
    return folder


def even(total: int, cells: list) -> dict:
    """``total`` wins spread over ``cells`` as evenly as possible."""
    base, extra = divmod(total, len(cells))
    return {o: base + (1 if i < extra else 0) for i, o in enumerate(cells)}


def build(tmp_path, monkeypatch, strike=None, guard=None, heads=None, strike_runs=()) -> tuple[Path, dict]:
    """Every folder of the read and its manifest. ``strike`` {(arm, pair): k or [k per read]} (default ``STRIKE``,
    every read the same); ``guard`` {(arm, pair): k per cell or {opponent: k}} (default ``GUARD``); ``heads`` the
    route 3 gate file's text (default ``heads_text()``); ``strike_runs`` the (arm, pair) given a Strike run of record.
    Returns (manifest, {(arm, pair): {key: folder}})."""
    path = tmp_path / "gates" / "heads_gates.toml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(heads if heads is not None else heads_text())
    use_heads(monkeypatch, path)
    strike, guard = {**STRIKE, **(strike or {})}, {**GUARD, **(guard or {})}
    folders, lines = {}, []
    for a, arm in enumerate(ARMS):
        for p, pair in enumerate(PAIRS):
            gates, variant = gates_of(arm, pair), reader.VARIANTS[arm][pair]
            base = tmp_path / arm / pair
            ks = strike[(arm, pair)]
            g = guard[(arm, pair)]
            f = {"pilot": make_pilot(tmp_path / arm / "pilot", gates_of(*reader.PILOT_RAN_UNDER.get((arm, pair),
                                                                                                  (arm, pair)))),
                 "run0": make_run0(base / "run0", gates, variant, ks if isinstance(ks, list) else [ks] * READS),
                 "guard": make_main(base / "guard", gates, variant, "guard",
                                    g if isinstance(g, dict) else {o: g for o in opponents(gates, "guard")},
                                    seed=10 * a + p)}
            if (arm, pair) in strike_runs:
                f["strike"] = make_main(base / "strike", gates, variant, "strike",
                                        {o: 500 for o in opponents(gates, "strike")}, seed=20 + 10 * a + p)
            folders[(arm, pair)] = f
            lines += [f"[{arm}.{pair}]"] + [f'{k} = "{v}"' for k, v in f.items()] + [""]
    manifest = tmp_path / "read.toml"
    manifest.write_text("\n".join(lines))
    return manifest, folders


def run(manifest: Path, out: Path, capsys) -> tuple[int, str]:
    code = reader.main(["--manifest", str(manifest), "--out", str(out)])
    return code, capsys.readouterr().err


def read_json(out: Path) -> dict:
    return json.loads((out / "read.json").read_text())


# ------------------------------------------------------------------------------------------------ the rule, exactly
def _delta(key="margin_cell") -> Fraction:
    return Fraction(str(STAND_IN["reading"][key]))


def test_the_rule_at_the_margin_exactly_and_one_count_lower():
    """Exact fractions: route 3's mean exactly at route 2's mean less the margin, each pair at least route 2's lowest
    less the margin -> no drop; one count (1/1,000) lower on one pair -> not (INCONCLUSIVE: 2x the margin is far)."""
    d = _delta()
    r2 = [Fraction(640, N), Fraction(600, N)]
    r3 = [r2[0] - d, r2[1] - d]
    assert reader.rule(r3, r2, d) == reader.NO_DROP
    assert reader.rule([r3[0] - Fraction(1, N), r3[1]], r2, d) == reader.INCONCLUSIVE


def test_one_pair_below_the_lowest_less_the_margin_is_inconclusive():
    d = _delta()
    r2 = [Fraction(640, N), Fraction(600, N)]
    low = min(r2) - d
    assert reader.rule([low, Fraction(700, N)], r2, d) == reader.NO_DROP          # at the edge, mean well above
    assert reader.rule([low - Fraction(1, N), Fraction(700, N)], r2, d) == reader.INCONCLUSIVE


def test_below_is_strictly_past_twice_the_margin():
    d = _delta()
    r2 = [Fraction(640, N), Fraction(600, N)]
    at = [r2[0] - 2 * d, r2[1] - 2 * d]
    assert reader.rule(at, r2, d) == reader.INCONCLUSIVE                         # exactly 2x: not below
    assert reader.rule([at[0] - Fraction(1, N), at[1]], r2, d) == reader.BELOW   # one count past


# ------------------------------------------------------------------------------------------------ the whole read
def test_the_baseline_reads_no_drop_on_both_sides(tmp_path, monkeypatch, capsys):
    manifest, _ = build(tmp_path, monkeypatch)
    code, err = run(manifest, tmp_path / "out", capsys)
    assert code == reader.EXIT_DONE, err
    r = read_json(tmp_path / "out")
    assert r["strike"]["word"] == r["guard"]["word"] == reader.NO_DROP
    assert r["strike"]["margin_key"] == "margin_cell" and r["guard"]["margin_key"] == "margin_pooled"
    assert r["reading"] == STAND_IN["reading"]
    assert (tmp_path / "out" / "read.md").is_file()


def _grid_case(side: str, which: str) -> dict:
    """Route 3's total count on the side's grid (two pairs; Strike: N per pair, Guard: N x the pool's cells): just met
    ("met"), one count past the no-drop edge ("crossed"), one count past twice the margin ("below"), at the first
    count that is not below ("not_below"). Returns {"total": int, "denominator": int}."""
    gates = gates_of("route2", "s1")
    cells = len(pool.pool_members(gates.players, "strike")) if side == "guard" else 1
    den = 2 * N * cells
    base = STRIKE if side == "strike" else GUARD
    mean2 = Fraction(base[("route2", "s1")] + base[("route2", "s2")], 2 * N)
    d = _delta("margin_cell" if side == "strike" else "margin_pooled")
    met = ceil((mean2 - d) * den)
    not_below = ceil((mean2 - 2 * d) * den)
    total = {"met": met, "crossed": met - 1, "below": not_below - 1, "not_below": not_below}[which]
    return {"total": total, "cells": cells}


def _route3_from_total(side: str, total: int, cells: int, gates) -> dict:
    """Route 3's per-pair inputs for ``build`` from a total count over both pairs."""
    first, second = total - total // 2, total // 2
    if side == "strike":
        return {"strike": {("route3", "s1"): first, ("route3", "s2"): second}}
    opps = opponents(gates, "guard")
    return {"guard": {("route3", "s1"): even(first, opps), ("route3", "s2"): even(second, opps)}}


@pytest.mark.parametrize("side", ["strike", "guard"])
@pytest.mark.parametrize("which,word", [("met", "NO_DROP"), ("crossed", "INCONCLUSIVE"), ("below", "BELOW"),
                                        ("not_below", "INCONCLUSIVE")])
def test_each_margin_on_the_count_grid(tmp_path, monkeypatch, capsys, side, which, word):
    """Through ``main`` on the count grid (STAND_IN margins through the tmp_path gate file): just met -> no drop, one
    count lower -> not; one count past twice the margin -> below, the next count up -> INCONCLUSIVE."""
    _margins_reach_the_rule(tmp_path, monkeypatch, capsys, side, which, word)


def _margins_reach_the_rule(tmp_path, monkeypatch, capsys, side, which, word, heads=None):
    case = _grid_case(side, which)
    kw = _route3_from_total(side, case["total"], case["cells"], gates_of("route2", "s1"))
    manifest, _ = build(tmp_path, monkeypatch, heads=heads if heads is not None else heads_text(), **kw)
    code, err = run(manifest, tmp_path / "out", capsys)
    assert code == reader.EXIT_DONE, err
    assert read_json(tmp_path / "out")[side]["word"] == getattr(reader, word)


def test_the_committed_margins_run_through_the_rule(tmp_path, monkeypatch, capsys):
    """Constraint 5, R2 RC-2, OA-4: once the owner fills heads_gates.toml's [reading], its own margins and last_reads
    reach the rule (each margin just met and just crossed on the count grid); skipped while a ``FILL_`` is left (the
    one designed skip of this file; the same body runs on the STAND_IN file in test_each_margin_on_the_count_grid)."""
    left = [k for k in exploit.unfilled(exploit.load_gates(HEADS)) if k.startswith("[reading]")]
    if left:
        pytest.skip(f"R38: configs/ste_ls1/heads_gates.toml [reading] still holds FILL_ ({', '.join(left)}); the "
                    f"owner sets the margins (lead step 5)")
    committed = tomllib.loads(HEADS.read_text())["reading"]
    monkeypatch.setitem(STAND_IN, "reading", dict(committed))      # the committed values are the ones the file holds
    for side in ("strike", "guard"):
        for which, word in (("met", "NO_DROP"), ("crossed", "INCONCLUSIVE"), ("below", "BELOW")):
            sub = tmp_path / f"{side}_{which}"
            sub.mkdir()
            _margins_reach_the_rule(sub, monkeypatch, capsys, side, which, word)


def test_each_side_takes_its_own_margin(tmp_path, monkeypatch, capsys):
    """Strike is judged with margin_cell (OP-34), Guard with margin_pooled (OP-30 (a)): a gap of 19/2,000 (Strike) and
    114/12,000 (Guard), both 0.0095, lies between STAND_IN's margin_pooled 0.0091 and margin_cell 0.0097."""
    lo, hi = sorted([_delta("margin_pooled"), _delta("margin_cell")])
    assert lo < Fraction(95, 10000) <= hi and _delta("margin_pooled") < _delta("margin_cell")
    gates = gates_of("route2", "s1")
    opps = opponents(gates, "guard")
    manifest, _ = build(tmp_path, monkeypatch,
                        strike={("route3", "s1"): 640 - 10, ("route3", "s2"): 600 - 9},
                        guard={("route2", "s2"): 800, ("route3", "s1"): even(6 * 800 - 57, opps),
                               ("route3", "s2"): even(6 * 800 - 57, opps)})
    code, err = run(manifest, tmp_path / "out", capsys)
    assert code == reader.EXIT_DONE, err
    r = read_json(tmp_path / "out")
    assert r["strike"]["word"] == reader.NO_DROP          # 0.0095 <= margin_cell
    assert r["guard"]["word"] == reader.INCONCLUSIVE      # 0.0095 > margin_pooled
    assert "third" in r["guard"]["next"]


def test_a_monkeypatched_margin_moves_the_verdict(tmp_path, monkeypatch, capsys):
    """The margin is the gate file's, never typed: the same folders read INCONCLUSIVE at STAND_IN's margin_cell and no
    drop at twice it (written into the gate file)."""
    strike = {("route3", "s1"): 640 - 15, ("route3", "s2"): 600 - 15}     # a gap of 0.015 (> 0.0097, < 0.0194)
    manifest, _ = build(tmp_path, monkeypatch, strike=strike)
    code, err = run(manifest, tmp_path / "out1", capsys)
    assert code == reader.EXIT_DONE, err
    assert read_json(tmp_path / "out1")["strike"]["word"] == reader.INCONCLUSIVE
    doubled = 2 * STAND_IN["reading"]["margin_cell"]
    monkeypatch.setitem(STAND_IN, "reading", {**STAND_IN["reading"], "margin_cell": doubled})
    (tmp_path / "gates" / "heads_gates.toml").write_text(heads_text())
    edit_all = list(tmp_path.glob("route3/*/*/*.json")) + list(tmp_path.glob("route3/pilot/pilot.json"))
    sha = exploit.sha256_file(tmp_path / "gates" / "heads_gates.toml")
    for p in edit_all:
        edit(p, lambda d: d.__setitem__("gates_sha256", sha) if "gates_sha256" in d else None)
    code, err = run(manifest, tmp_path / "out2", capsys)
    assert code == reader.EXIT_DONE, err
    assert read_json(tmp_path / "out2")["strike"]["word"] == reader.NO_DROP


def test_the_strike_read_is_two_pairs_by_seed(tmp_path, monkeypatch, capsys):
    """Option B (R46): each pair's route 3 run 0 is read against route 2's run 0 of the same training seed (140203 for
    variant base, 140213 for base_s2 and route 2 seed 2), with the two-pair rule and margin_cell; route 2 seed 2's run
    0 is read, not INFO."""
    manifest, _ = build(tmp_path, monkeypatch)
    code, err = run(manifest, tmp_path / "out", capsys)
    assert code == reader.EXIT_DONE, err
    seeds = read_json(tmp_path / "out")["strike"]["pairs"]
    for pair, want in (("s1", 140203), ("s2", 140213)):
        assert seeds[pair]["route2"]["train_seed"] == seeds[pair]["route3"]["train_seed"] == want
        assert "score" in seeds[pair]["route2"] and "score" in seeds[pair]["route3"]
    assert seeds["s2"]["route3"]["variant"] == "base_s2" and seeds["s2"]["route2"]["variant"] == "base"


def test_a_route3_run0_of_an_unpaired_seed_exits_2(tmp_path, monkeypatch, capsys):
    """A route 3 gate file whose base_s2 run 0 trains another seed than route 2 seed 2's: its run 0 (made under it)
    pairs with nothing."""
    heads = heads_text(edits=[("run0_seed = 140213", "run0_seed = 140223")])
    manifest, _ = build(tmp_path, monkeypatch, heads=heads)
    code, err = run(manifest, tmp_path / "out", capsys)
    assert code == reader.EXIT_REFUSED and "run 0" in err and "140223" in err
    assert not (tmp_path / "out" / "read.json").exists()


def test_the_strike_score_ignores_an_earlier_dip(tmp_path, monkeypatch, capsys):
    manifest, _ = build(tmp_path, monkeypatch, strike={("route3", "s1"): [0, 3, 640, 640, 640]})
    code, err = run(manifest, tmp_path / "out", capsys)
    assert code == reader.EXIT_DONE, err
    r = read_json(tmp_path / "out")
    assert r["strike"]["pairs"]["s1"]["route3"]["score"] == pytest.approx(0.64)
    assert r["strike"]["word"] == reader.NO_DROP
    assert [x["update"] for x in r["strike"]["pairs"]["s1"]["route3"]["reads_used"]] == [30, 40, 50]


def test_min_last_reads_is_the_minimum_for_every_pair_and_arm(tmp_path, monkeypatch, capsys):
    manifest, _ = build(tmp_path, monkeypatch, strike={("route3", "s1"): [700, 0, 650, 610, 690]})
    code, err = run(manifest, tmp_path / "out", capsys)
    assert code == reader.EXIT_DONE, err
    r = read_json(tmp_path / "out")
    s = r["strike"]["pairs"]["s1"]["route3"]
    assert s["min_last_reads"] == pytest.approx(0.61) and s["score"] == pytest.approx(0.65)
    for side in ("strike", "guard"):
        for pair in PAIRS:
            for arm in ARMS:
                assert "min_last_reads" in r[side]["pairs"][pair][arm], (side, pair, arm)
    assert r["guard"]["pairs"]["s2"]["route3"]["min_last_reads"] == pytest.approx(min(CURVE[-3:]) / 256)


def test_a_guard_cell_miss_never_changes_the_verdict(tmp_path, monkeypatch, capsys):
    """One Guard cell 300 games worse on route 3, another 300 better: the pooled row is route 2's (no drop); the
    cell's gap is written beyond margin_cell as INFO."""
    opps = opponents(gates_of("route2", "s1"), "guard")
    ks = {o: 800 for o in opps}
    ks[opps[0]], ks[opps[1]], ks[opps[2]] = 500, 1000, 900     # 500 + 1000 + 900 = 3 x 800
    manifest, _ = build(tmp_path, monkeypatch, guard={("route3", "s1"): ks})
    code, err = run(manifest, tmp_path / "out", capsys)
    assert code == reader.EXIT_DONE, err
    r = read_json(tmp_path / "out")
    assert r["guard"]["word"] == reader.NO_DROP
    cells = {c["opponent"]: c for c in r["guard"]["pairs"]["s1"]["cells"]}
    assert cells[opps[0]]["beyond_margin_cell"] is True and cells[opps[0]]["label"].startswith("INFO")
    assert cells[opps[3]]["beyond_margin_cell"] is False


def test_the_paired_difference_uses_same_starts(tmp_path, monkeypatch, capsys):
    """The per-start pooled difference of each pair goes through ste_l6_read.same_starts, and equals
    compare.paired_difference of the two per-start means."""
    calls = []
    real = reader.l6.same_starts

    def spy(a, b, what):
        calls.append(what)
        return real(a, b, what)

    monkeypatch.setattr(reader.l6, "same_starts", spy)
    manifest, folders = build(tmp_path, monkeypatch)
    code, err = run(manifest, tmp_path / "out", capsys)
    assert code == reader.EXIT_DONE, err
    assert sum("guard" in c and "s1" in c for c in calls) >= 1 and sum("guard" in c and "s2" in c for c in calls) >= 1
    gates = gates_of("route2", "s1")
    members = pool.pool_members(gates.players, "strike")
    opps = opponents(gates, "guard")

    def y(folder):
        out = np.load(folder / "eval_info.npz")["outcome"]
        return compare.per_start_mean(compare.wins_by_cell(out, opps, N, "guard"), members)

    want = compare.paired_difference(y(folders[("route3", "s1")]["guard"]), y(folders[("route2", "s1")]["guard"]))
    got = read_json(tmp_path / "out")["guard"]["pairs"]["s1"]["paired_difference"]
    assert got["diff"] == pytest.approx(want["diff"]) and got["ci"] == pytest.approx(want["ci"])


MUTATIONS = {
    # name: (heads edits, (arm, pair, folder key, file) to edit or None, edit fn, words stderr must name)
    "train seed": ([("train_seed = { strike = 140211, guard = 140212 }, extra_eval_opponents = { strike = [], guard = "
                     "[] }, reference_variant", "train_seed = { strike = 140211, guard = 140222 }, extra_eval_opponents"
                     " = { strike = [], guard = [] }, reference_variant")], None, None, ["train_seed", "140222"]),
    "run 0 seed in the folder": ([], ("route3", "s1", "run0", "learner_control.json"),
                                 lambda d: d.__setitem__("train_seed", 140299), ["train_seed", "140299"]),
    "run 0 variant": ([], ("route3", "s2", "run0", "learner_control.json"), lambda d: d.__setitem__("variant", "base"),
                      ["variant"]),
    "pool seed": ([("enabled = true\nseed = 140001", "enabled = true\nseed = 140009")], None, None, ["pool"]),
    "recipe": ([("side_overrides = { strike = {}, guard = {} }",
                 "side_overrides = { strike = { shaping_weight = 1.0 }, guard = {} }")], None, None, ["recipe"]),
    "game steps": ([("game_steps_per_run = 550_000_000", "game_steps_per_run = 560_000_000")], None, None,
                   ["game_steps_per_run"]),
    "game file": ([], ("route3", "s1", "guard", "results.json"),
                  lambda d: d["game_file"].__setitem__("sha256", "e" * 64), ["game_file"]),
    "starts": ([], ("route3", "s2", "guard", "results.json"),
               lambda d: d["reference"].__setitem__("start_sha256", "e" * 64), ["starts"]),
    "route 3 without the net": ([], ("route3", "s1", "run0", "learner_control.json"),
                                lambda d: [d["learner"].pop(k) for k in ("skill_source", "skill_net_sha256")],
                                ["skill network"]),
    "another net sha": ([], ("route3", "s2", "guard", "results.json"),
                        lambda d: d["learner"]["skill_net_sha256"].__setitem__("strike", "e" * 64),
                        ["skill network", "sha256"]),
    "route 2 pilot's table": ([], ("route2", "s2", "pilot", "pilot.json"),
                              lambda d: d["learner"]["entropy_scale"].__setitem__("team", 0.5), ["pilot", "[learner]"]),
    "run 0 short of budget": ([], ("route3", "s2", "run0", "learner_control.json"),
                              lambda d: d.__setitem__("budget_reached", False), ["budget"]),
    "run 0 checkpoints": ([], ("route3", "s1", "run0", "learner_control.json"),
                          lambda d: (d.__setitem__("checkpoints", [11, 21, 31, 41, 50])), ["checkpoints"]),
    "run 0 read size": ([], ("route3", "s1", "run0", "learner_control.json"),
                        lambda d: d["reads"][-1]["trained"].__setitem__("n", 999), ["games"]),
    "guard short of budget": ([], ("route2", "s1", "guard", "results.json"),
                              lambda d: d.__setitem__("budget_reached", False), ["budget"]),
    "a stop at the cap": ([], ("route3", "s2", "guard", jobs.EXIT_FILE), None, ["cap"]),
}


@pytest.mark.parametrize("name", list(MUTATIONS))
def test_any_pairing_mismatch_exits_2(tmp_path, monkeypatch, capsys, name):
    """One mutation per refusal, against a baseline that exits 0: exit 2, the message names what it refused, and no
    read.json is written."""
    edits, target, fn, words = MUTATIONS[name]
    manifest, folders = build(tmp_path, monkeypatch, heads=heads_text(edits=edits))
    if target is not None:
        arm, pair, key, file = target
        path = folders[(arm, pair)][key] / file
        if fn is None:
            path.write_text("3\n")
        else:
            edit(path, fn)
    code, err = run(manifest, tmp_path / "out", capsys)
    assert code == reader.EXIT_REFUSED, err
    for w in words:
        assert w in err, (w, err)
    assert not (tmp_path / "out" / "read.json").exists()


def test_the_route2_seed2_pilot_is_route2s_l33_pilot(tmp_path, monkeypatch, capsys):
    """Route 2 seed 2 runs on the L3.3 pilot, made under configs/ste_l3/skills_gates.toml: accepted for
    skills_seed2_gates.toml by the file it ran under plus learner-table equality."""
    manifest, folders = build(tmp_path, monkeypatch)
    assert folders[("route2", "s1")]["pilot"] == folders[("route2", "s2")]["pilot"]
    pilot = json.loads((folders[("route2", "s2")]["pilot"] / "pilot.json").read_text())
    assert pilot["gates_sha256"] == gates_of("route2", "s1").sha256 != gates_of("route2", "s2").sha256
    code, err = run(manifest, tmp_path / "out", capsys)
    assert code == reader.EXIT_DONE, err


def test_a_gate_file_without_reading_or_with_a_fill_margin_exits_2(tmp_path, monkeypatch, capsys):
    """F8: a net gate file without [reading] is refused by the loader, a FILL_ margin by the reader; both exit 2. The
    committed heads gate file is refused while it holds a FILL_ mark (until lead steps 4 and 5)."""
    manifest, _ = build(tmp_path, monkeypatch)
    for i, (text, words) in enumerate(((heads_text(reading=False), ["[reading]"]),
                                       (heads_text(fill="margin_pooled"), ["margin_pooled", "FILL_"]))):
        path = tmp_path / f"variant{i}.toml"
        path.write_text(text)
        use_heads(monkeypatch, path)
        code, err = run(manifest, tmp_path / f"out{i}", capsys)
        assert code == reader.EXIT_REFUSED, err
        for w in words:
            assert w in err, (w, err)
    if exploit.unfilled(exploit.load_gates(HEADS)):          # until lead steps 4 and 5 fill it
        use_heads(monkeypatch, HEADS)
        code, err = run(manifest, tmp_path / "out_committed", capsys)
        assert code == reader.EXIT_REFUSED and "FILL_" in err


def test_stand_in_mirrors_no_limit(tmp_path):
    """Constraint 5, R2 B8: no typed PROPOSED value. STAND_IN's [reading] floats are off the 0.001 grid, differ from
    each other and from every filled number of the committed [reading] (read from the file); and the read's synthetic
    margins come from STAND_IN through a tmp_path gate file."""
    mine = [v for v in STAND_IN["reading"].values() if isinstance(v, float)]
    assert sorted(mine) == sorted(STAND_IN["reading"][k] for k in exploit.READING_MARGINS)
    assert len(set(mine)) == len(mine)
    for v in mine:
        assert Fraction(str(v)) * 1000 != int(Fraction(str(v)) * 1000), v
    committed = [v for v in tomllib.loads(HEADS.read_text())["reading"].values()
                 if isinstance(v, (int, float)) and not isinstance(v, bool)]
    assert not set(mine) & set(committed)
    path = tmp_path / "heads_gates.toml"
    path.write_text(heads_text())
    assert exploit.load_gates(path).reading == STAND_IN["reading"]


def test_the_word_level_never_appears(tmp_path, monkeypatch, capsys):
    """Scans read.md, read.json and scripts/ste_ls1_read.py for the word "level" (``\\blevel\\b``, any case, so also
    "two-level"); the fake folders carry it in their free text, so the scan is not vacuous. The learner table and choice
    string are never copied (they hold "two_level"): the read writes a check result only."""
    manifest, folders = build(tmp_path, monkeypatch)
    assert LEVEL.search((folders[("route3", "s1")]["run0"] / "learner_control.json").read_text())
    assert LEVEL.search((folders[("route3", "s1")]["guard"] / "results.json").read_text())
    code, err = run(manifest, tmp_path / "out", capsys)
    assert code == reader.EXIT_DONE, err
    for path in (tmp_path / "out" / "read.md", tmp_path / "out" / "read.json", SCRIPTS / "ste_ls1_read.py"):
        text = path.read_text()
        assert not LEVEL.search(text), (path, LEVEL.search(text))
        assert path.suffix == ".py" or "two_level" not in text, path
    r = read_json(tmp_path / "out")
    assert r["strike"]["pairs"]["s1"]["route3"]["learner"].startswith("net")


def test_the_read_writes_no_machine_path(tmp_path, monkeypatch, capsys):
    """Folders outside the repository are written by name only; no home directory reaches read.json or read.md."""
    manifest, _ = build(tmp_path, monkeypatch)
    code, err = run(manifest, tmp_path / "out", capsys)
    assert code == reader.EXIT_DONE, err
    for name in ("read.json", "read.md"):
        text = (tmp_path / "out" / name).read_text()
        assert str(tmp_path) not in text and str(Path.home()) not in text


def test_strike_runs_of_record_are_info(tmp_path, monkeypatch, capsys):
    """A Strike run of record on both arms of a pair: its paired per-start pooled difference and choice shares are
    INFO; the verdict is the run 0 cell's."""
    manifest, _ = build(tmp_path, monkeypatch, strike_runs={("route2", "s1"), ("route3", "s1")})
    code, err = run(manifest, tmp_path / "out", capsys)
    assert code == reader.EXIT_DONE, err
    r = read_json(tmp_path / "out")
    info = r["info"]["strike_runs_of_record"]["s1"]
    assert info["paired_difference"]["label"].startswith("INFO") and set(info["arms"]) == set(ARMS)
    assert r["strike"]["word"] == reader.NO_DROP
    assert set(r["info"]["choice_shares"]["guard"]["s1"]) == set(ARMS)
    best = r["info"]["best_single_choice"]["guard"]["s1"]["route3"]
    assert "scripts" in best["label"]


def test_a_second_read_needs_a_new_folder(tmp_path, monkeypatch, capsys):
    manifest, _ = build(tmp_path, monkeypatch)
    assert run(manifest, tmp_path / "out", capsys)[0] == reader.EXIT_DONE
    code, err = run(manifest, tmp_path / "out", capsys)
    assert code == reader.EXIT_REFUSED and "new folder" in err
