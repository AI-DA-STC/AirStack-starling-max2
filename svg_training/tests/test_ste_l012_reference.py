"""STE task L0.12 Best-response test: the T44 reference file (configs/ste_l012/t44_reference.npz), made by
scripts/ste_l012_reference.py from T44's run folder. It holds T44's 1,000 starts of the 3v3 6.5 m start setting and the
per-game results of every cell of the shortlisted variants, so L0.12 can replay T44's own starts (a CPU generator does
not reproduce the CUDA draw) and compute its script baselines by code. The extraction is tested on a synthetic run
folder; the committed file is checked against T44's published numbers (record T44, follow-up note)."""
import hashlib
import json
import sys

import numpy as np
import pytest

from _ste_tools import SCRIPTS
from svg_training.ste import exploit

sys.path.insert(0, str(SCRIPTS))
import ste_l012_reference as ref_script  # noqa: E402

G = ["guard_parked_centre", "guard_mark_edge"]
S = ["strike_straight", "strike_low"]


def fake_t44(tmp_path, games=5, variants=("base", "tag_1p2"), break_start=False):
    """A T44-like run folder: one batch per variant, cells G x S, per-game arrays as ste/sweep.py writes them."""
    run = tmp_path / "t44"
    (run / "cells").mkdir(parents=True)
    rng = np.random.default_rng(0)
    starts = rng.normal(size=(games, 6, 3)).astype(np.float32)
    sha = hashlib.sha256(np.ascontiguousarray(starts).tobytes()).hexdigest()
    (run / "gates.sha256").write_text("ab" * 32 + "\n")
    (run / "exit_code").write_text("0\n")                        # a finished job, every control PASS (L0.12b QC 1)
    (run / "controls.json").write_text(json.dumps({"paired_starts": {"status": "PASS", "detail": ""}}))
    for v_i, v in enumerate(variants):
        cells = [[g, s] for g in G for s in S]
        n = games * len(cells)
        outcome = rng.integers(1, 3, size=n).astype(np.int8)
        st = np.tile(starts, (len(cells), 1, 1))
        if break_start and v_i == 1:
            st = st.copy()
            st[0, 0, 0] += 1.0
        arrays = dict(outcome=outcome, end_step=rng.integers(1, 99, size=n), tags=rng.integers(0, 4, size=n),
                      guards_tagged=np.zeros(n, dtype=np.int64), guards_removed=rng.integers(0, 4, size=n),
                      strikes_left=rng.integers(0, 4, size=n), closest_3d_m=np.zeros(n, dtype=np.float32),
                      start_miss=np.zeros(n, dtype=bool), start_pos_m=st)
        np.savez_compressed(run / "cells" / f"{v}__b00.npz", **arrays)
        shas = [hashlib.sha256(np.ascontiguousarray(st[k * games:(k + 1) * games]).tobytes()).hexdigest()
                for k in range(len(cells))]
        (run / "cells" / f"{v}__b00.json").write_text(json.dumps(
            {"batch": f"{v}/b00", "group": v, "game": v, "size": "3v3", "cells": cells, "games": n,
             "start_sha256": shas}))
    return run, starts, sha


def test_extraction_keeps_the_starts_and_every_cell_game_for_game(tmp_path):
    run, starts, sha = fake_t44(tmp_path)
    out = tmp_path / "ref.npz"
    assert ref_script.main(["--t44", str(run), "--out", str(out), "--variants", "base,tag_1p2"]) == 0
    ref = exploit.load_reference(out)
    assert ref.start_sha256 == sha
    assert np.array_equal(ref.starts_m, starts)
    assert ref.games == 5 and ref.meta["t44_gates_sha256"] == "ab" * 32
    z = np.load(run / "cells" / "tag_1p2__b00.npz")
    k = [list(c) for c in json.loads((run / "cells" / "tag_1p2__b00.json").read_text())["cells"]].index(
        ["guard_mark_edge", "strike_low"])
    pg = ref.cell("tag_1p2", "guard_mark_edge", "strike_low")
    for key in exploit.PER_GAME:
        assert np.array_equal(pg[key], z[key][k * 5:(k + 1) * 5]), key
    assert set(ref.cells) == {(v, g, s) for v in ("base", "tag_1p2") for g in G for s in S}


def test_extraction_refuses_a_variant_whose_starts_differ(tmp_path):
    run, _, _ = fake_t44(tmp_path, break_start=True)
    assert ref_script.main(["--t44", str(run), "--out", str(tmp_path / "r.npz"), "--variants", "base,tag_1p2"]) == 2
    assert not (tmp_path / "r.npz").exists()


def test_extraction_refuses_a_missing_variant(tmp_path):
    run, _, _ = fake_t44(tmp_path)
    assert ref_script.main(["--t44", str(run), "--out", str(tmp_path / "r.npz"), "--variants", "base,tag_1p4"]) == 2


# ------------------------------------------------------------------------------------------------ the committed file
@pytest.fixture(scope="module")
def committed():
    g = exploit.load_gates()
    return g, exploit.load_reference(exploit.ROOT / g.reference["file"])


def test_the_committed_file_is_the_one_the_gate_file_pins(committed):
    g, ref = committed
    assert exploit.sha256_file(exploit.ROOT / g.reference["file"]) == g.reference["sha256"]
    assert ref.start_sha256 == g.reference["start_sha256"]
    assert ref.start_sha256.startswith("5aeba7ab2b582f29")          # the follow-up note's 3v3 start set
    assert ref.meta["t44_gates_sha256"] == g.reference["t44_gates_sha256"]
    assert ref.games == 1000 and ref.starts_m.shape == (1000, 6, 3)


def test_the_committed_file_reproduces_t44s_published_numbers(committed):
    _, ref = committed
    count = lambda v, g, s, what: int(np.sum(ref.cell(v, g, s)["outcome"] == what))   # noqa: E731
    assert count("base", "guard_mark_edge", "strike_straight", exploit.GUARD_WIN) == 808     # T44 base maximin
    assert count("base", "guard_mark_edge", "strike_straight", exploit.STRIKE_WIN) == 192
    assert count("tag_1p2", "guard_field", "strike_straight", exploit.GUARD_WIN) == 645
    assert count("tag_1p4", "guard_mirror", "strike_low", exploit.GUARD_WIN) == 672
    assert count("base", "guard_parked_centre", "strike_straight", exploit.GUARD_WIN) == 534


def test_g_star_and_s_star_by_code_equal_the_gate_file_and_t44(committed):
    g, ref = committed
    for name, v in g.variants.items():
        assert exploit.star_players(ref, name, g.players) == (v["g_star"], v["s_star"]), name
    assert (g.variants["base"]["g_star"], g.variants["base"]["s_star"]) == ("guard_mark_edge", "strike_straight")
    assert (g.variants["tag_1p2"]["g_star"], g.variants["tag_1p2"]["s_star"]) == ("guard_field", "strike_straight")
    assert (g.variants["tag_1p4"]["g_star"], g.variants["tag_1p4"]["s_star"]) == ("guard_mirror", "strike_low")
