"""Route 3, stage LS1, task LS1-M3-T6: ``scripts/ste_ls1_clips.py``, the 3-D clips of the copy beside the scripts (job
LS1.6; plan ste_learning/drafts/LS1_TASK_PLAN.md, section 4, and the design check of M3).

Tiny equivalence reads on the CPU, written by the read's own script (``scripts/ste_ls1_equivalence.py``) at N = 2
starts per cell, one opponent, one mixed combination, ``--smoke`` (the owner's keys stay FILL_): a Guard and a Strike
read with ``cells.ScriptOracle`` flown as the network (``eq.net_check`` patched for the read and for the replay, as the
design check says: the read loads its network from a file), and a Guard read with a tiny network
(``tests/_ste_ls1.read_net``). The Isaac render is the VID-1 renderer with the stand-in Isaac of
``tests/test_make_ste_3d.py`` (``l5.render_stage`` patched, as tests/test_ste_l5_clips3d.py does); the encode is real
(ffmpeg), on a small frame.

Checked: both arms of each pick are replayed on the read's own batches and drawn (with the oracle as the network the
two trajectories are equal frame for frame); a replay that differs from the read's record is not drawn, nor its pair
(exit 1); the picks of one batch share one replay; the pick rule (``RULE``, hand-made ``pair_class`` arrays); the plan
only writes nothing and every refusal exits 2. CPU only."""
import argparse
import contextlib
import hashlib
import io
import json
import shutil
import sys

import numpy as np
import pytest

from svg_training.ste import cells, exploit, scoring
from svg_training.ste.run_contract import EXIT_DONE
from svg_training.viz import replay3d as r3
from svg_training.viz.starling_look import SETTINGS_FILE

import _ste_ls1 as h
from _ste_tools import SCRIPTS
from test_make_ste_3d import FakeIsaac, m3

sys.path.insert(0, str(SCRIPTS))
import ste_l5_clips3d as l5  # noqa: E402
import ste_ls1_clips as cli  # noqa: E402
import ste_ls1_equivalence as eq  # noqa: E402

GAMES = 2                                                    # starts per cell of the tiny reads (the design check: N = 2)
OPPONENT = {"guard": "strike_straight", "strike": "guard_field"}    # one gated opponent per side, games that end soon
MIXED = 1                                                    # one gated mixed combination (R1 holds a mixed cell)
B, C, S = eq.PAIR_B, eq.PAIR_C, eq.PAIR_SAME


# ================================================================================================ helpers
def _oracle_net_check(args, g, cfg):
    """``eq.net_check`` with ``cells.ScriptOracle`` flown as the network (the network file's sha256 kept, so the read's
    layout names the file it was given)."""
    spec = g.specs[args.side]
    return (cells.ScriptOracle(cfg, args.side, list(spec.players), spec.drones),
            exploit.sha256_file(args.skill_net)), None


def tiny_equivalence_read(tmp, side, net) -> dict:
    """A finished equivalence read of ``side`` under ``tmp`` (``--smoke --games 2``, one opponent, ``--mixed 1``) by the
    read's own script, its network a tiny one (``_ste_ls1.read_net``) flown as such (``net="tiny"``) or with
    ``cells.ScriptOracle`` in its place (``net="oracle"``). Returns {"folder", "net", "sha"}."""
    assert net in ("tiny", "oracle")
    path, sha = h.read_net(tmp / f"net_{side}", side, h.DISTIL_GATES)
    folder = tmp / f"read_{side}_{net}"
    argv = ["--gates", str(h.DISTIL_GATES), "--side", side, "--skill-net", str(path), "--run-dir", str(folder),
            "--cap-h", "1", "--opponents", OPPONENT[side], "--mixed", str(MIXED), "--games", str(GAMES), "--smoke"]
    with pytest.MonkeyPatch.context() as mp, contextlib.redirect_stdout(io.StringIO()):
        if net == "oracle":
            mp.setattr(eq, "net_check", _oracle_net_check)
        assert eq.main(argv) == EXIT_DONE
    return {"folder": folder, "net": path, "sha": sha}


def _tree(folder):
    return {str(p.relative_to(folder)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(folder.rglob("*")) if p.is_file()}


def _fake_render(calls):
    def render(out, work, trajectories, settings):
        calls.append([str(p) for p in trajectories])
        a = argparse.Namespace(work=str(work), settings=settings, stills=False, replay=[str(p) for p in trajectories],
                               arena_frame=None, encode=False, smoke=False)
        return m3.render(a, FakeIsaac())
    return render


def _argv(reads, out, settings=None, extra=()):
    argv = []
    for r in reads:
        argv += ["--equivalence", str(r["folder"]), "--skill-net", str(r["net"])]
    argv += ["--out", str(out)]
    if settings:
        argv += ["--settings", settings]
    return argv + list(extra)


def _main(argv) -> tuple[int, list[str]]:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = cli.main(argv)
    return code, buf.getvalue().splitlines()


def _copy(read, tmp_path, name):
    dst = tmp_path / name
    shutil.copytree(read["folder"], dst)
    return {**read, "folder": dst}


# ================================================================================================ fixtures
@pytest.fixture(scope="module")
def small_settings(tmp_path_factory):
    """configs/ste_video.toml at 320 x 180 (the recipe of tests/test_ste_l5_clips3d.py ``small_settings``)."""
    p = tmp_path_factory.mktemp("video") / "ste_video.toml"
    text = SETTINGS_FILE.read_text()
    assert "resolution = [1280, 720]" in text
    p.write_text(text.replace("resolution = [1280, 720]", "resolution = [320, 180]"))
    return str(p)


@pytest.fixture(scope="module")
def oracle_reads(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("oracle_reads")
    return {side: tiny_equivalence_read(tmp, side, "oracle") for side in ("guard", "strike")}


@pytest.fixture(scope="module")
def tiny_read(tmp_path_factory):
    return tiny_equivalence_read(tmp_path_factory.mktemp("tiny_read"), "guard", "tiny")


@pytest.fixture
def oracle(monkeypatch):
    monkeypatch.setattr(eq, "net_check", _oracle_net_check)


@pytest.fixture(scope="module")
def drawn(oracle_reads, small_settings, tmp_path_factory):
    """Both oracle reads drawn in one launch (default picks per side), the render on the stand-in Isaac."""
    out = tmp_path_factory.mktemp("drawn") / "clips"
    reads = [oracle_reads["guard"], oracle_reads["strike"]]
    before = {r["folder"]: _tree(r["folder"]) for r in reads}
    calls = []
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(eq, "net_check", _oracle_net_check)
        mp.setattr(l5, "render_stage", _fake_render(calls))
        code, lines = _main(_argv(reads, out, small_settings))
    return {"code": code, "lines": lines, "out": out, "reads": reads, "before": before, "calls": calls,
            "report": json.loads((out / cli.CLIPS_JSON).read_text())}


# ================================================================================================ the tests
def test_both_arms_are_replayed_on_the_same_start_and_drawn(drawn):
    """Per pick both arms (the copy: the network's R1 batch; the scripts: the cell's C1 or C1m batch) are replayed on
    the read's own batches, each equals the read's per-game record, and both are drawn (MP4 and GIF per camera); with
    ScriptOracle as the network the two trajectories are equal frame for frame. One render launch for both sides;
    nothing is written in a read folder; clips_ls1.json is complete, last."""
    assert drawn["code"] == cli.EXIT_DONE, drawn["lines"][-20:]
    rep, out = drawn["report"], drawn["out"]
    assert list(rep)[-1] == "complete" and rep["complete"] is True and rep["rule"] == cli.RULE
    assert {r["folder"]: _tree(r["folder"]) for r in drawn["reads"]} == drawn["before"]
    assert rep["picks_per_side"] == {"guard": cli.DEFAULT_PICKS_PER_SIDE, "strike": cli.DEFAULT_PICKS_PER_SIDE}
    assert len(drawn["calls"]) == 1 and len(drawn["calls"][0]) == 2 * len(rep["picks"])
    assert {p["side"] for p in rep["picks"]} == {"guard", "strike"}
    for p in rep["picks"]:
        assert p["drawn"] is True, p
        copy, scripts = (r3.load_trajectory(out / p["arms"][arm]["trajectory"]) for arm in (cli.COPY, cli.SCRIPTS))
        assert p["arms"][cli.COPY]["batch"].startswith(eq.STAGE_R1)
        assert eq.stage_of(p["arms"][cli.SCRIPTS]["batch"]) in (eq.STAGE_C1, eq.STAGE_C1M)
        for arm, t in ((cli.COPY, copy), (cli.SCRIPTS, scripts)):
            a = p["arms"][arm]
            assert a["check"]["equal"], a
            assert (t.outcome, t.end_step) == (a["recorded"]["outcome"], a["recorded"]["end_step"])
            assert t.meta["arm"] == arm and t.meta["side"] == p["side"] and t.meta["cell"] == p["cell"]
            assert t.meta["game_index"] == p["game"] and t.meta["net_sha256"] == p["net_sha256"]
            for cam in ("top", "3d"):
                assert (out / a["files"][cam]["mp4"]).stat().st_size > 0
                assert (out / a["files"][cam]["gif"]["file"]).stat().st_size > 0
            assert len(a["caption"]) <= 400 and "not a flight" in a["caption"]
        assert np.array_equal(copy.pos_m, scripts.pos_m) and np.array_equal(copy.yaw_rad, scripts.yaw_rad)
        assert np.array_equal(copy.alive, scripts.alive) and copy.end_step == scripts.end_step
    assert rep["games_drawn"] == {"guard": cli.DEFAULT_PICKS_PER_SIDE, "strike": cli.DEFAULT_PICKS_PER_SIDE}
    assert drawn["lines"][-1].startswith(cli.TAG)


def test_a_replay_that_differs_from_the_read_is_not_drawn(oracle_reads, tmp_path, small_settings, oracle, monkeypatch):
    """One end step of a picked game of the copy's batch tampered in a copy of the read folder: that pick's copy check
    fails, neither of its two trajectories is drawn, the other picks are drawn, exit 1."""
    read = _copy(oracle_reads["guard"], tmp_path, "tampered")
    plan = cli.plan([cli.load_read(read["folder"], [read["net"]])], cli.MIN_PICKS_PER_SIDE)
    first = plan["picks"][0]
    batch_file = read["folder"] / eq.GAMES_DIR / f"{first['arms'][cli.COPY]['batch']}.npz"
    pg = scoring.load_batch(batch_file)
    pg["end_step"][first["arms"][cli.COPY]["global_index"]] += 1
    scoring.save_batch(batch_file, pg)
    calls = []
    monkeypatch.setattr(l5, "render_stage", _fake_render(calls))
    out = tmp_path / "out"
    code, _ = _main(_argv([read], out, small_settings, ("--picks-per-side", str(cli.MIN_PICKS_PER_SIDE))))
    assert code == cli.EXIT_MISMATCH
    rep = json.loads((out / cli.CLIPS_JSON).read_text())
    bad = rep["picks"][0]
    assert (bad["cell"], bad["game"]) == (first["cell"], first["game"])
    assert not bad["arms"][cli.COPY]["check"]["equal"] and bad["arms"][cli.SCRIPTS]["check"]["equal"]
    assert bad["drawn"] is False and all("trajectory" not in a for a in bad["arms"].values())
    assert not list((out / "trajectories").glob(f"*_cell{bad['cell']}_game{bad['game']}_*"))
    others = rep["picks"][1:]
    assert others and all(p["drawn"] for p in others)
    assert len(calls) == 1 and len(calls[0]) == 2 * len(others) and rep["complete"] is True


def test_picks_of_one_batch_share_one_replay(tiny_read, tmp_path, small_settings, monkeypatch):
    """B-11: one replay per batch for every pick in it (a counter on capture_trained): the calls are the distinct
    batches of the picks' two arms, each replayed once, fewer than 2 x picks; with a tiny network (no stand-in) every
    replay equals the read."""
    calls, renders = [], []
    real = r3.capture_trained

    def counted(*a, **k):
        calls.append(sorted(a[10] if len(a) > 10 else k["keep"]))
        return real(*a, **k)
    monkeypatch.setattr(r3, "capture_trained", counted)
    monkeypatch.setattr(l5, "render_stage", _fake_render(renders))
    out = tmp_path / "out"
    code, _ = _main(_argv([tiny_read], out, small_settings))
    assert code == cli.EXIT_DONE
    rep = json.loads((out / cli.CLIPS_JSON).read_text())
    batches = {p["arms"][arm]["batch"] for p in rep["picks"] for arm in (cli.COPY, cli.SCRIPTS)}
    assert len(calls) == len(batches) == len(rep["replays"]) < 2 * len(rep["picks"])
    assert sorted(r["batch"] for r in rep["replays"]) == sorted(batches)
    for r in rep["replays"]:
        want = sorted({p["arms"][arm]["global_index"] for p in rep["picks"] for arm in (cli.COPY, cli.SCRIPTS)
                       if p["arms"][arm]["batch"] == r["batch"]})
        assert r["keep"] == want and want in calls
        assert r["check"]["equal"], r
    assert all(p["drawn"] for p in rep["picks"])


def _cell(index, kind, flips, classes, arm=eq.NET):
    return {"index": index, "kind": kind, "arm": arm, "flips": flips, "classes": np.asarray(classes, np.int8)}


def test_the_pick_rule():
    """RULE (OP-27 as settled by the lead; design check of M3): per side, from the network's gated cells only (arm net,
    kind fixed or mixed; info cells and other arms left out), the fixed cell with the most flips and the mixed cell
    with the most flips (a tie to the lowest cell index); in order: the fixed cell's lowest b game, the mixed cell's
    lowest changed game (b or c), the fixed cell's lowest c game, then agreeing games (the fixed cell's, then the mixed
    cell's, lowest first); a slot with no such game takes the cell's lowest agreeing game not picked, else its lowest
    game not picked; no game twice; --picks-per-side N keeps the first N. No mixed cell: refused. Above the cap: the
    picks per side fall one at a time (the fill first, then the fixed cell's c game), never below
    MIN_PICKS_PER_SIDE."""
    rows = [_cell(0, cells.FIXED, 2, [S, B, S, C]),
            _cell(1, cells.FIXED, 3, [S, S, C, B, B]),
            _cell(2, cells.FIXED, 3, [B, C, C, S, S]),             # ties with cell 1: the lower index (1) wins
            _cell(3, cells.MIXED, 1, [S, S, C, S]),
            _cell(4, cells.MIXED, 2, [S, B, S, C]),
            _cell(5, cells.INFO, 9, [B, B, C, C]),                 # info: never picked
            _cell(6, cells.FIXED, 9, [B, B, C, C], arm=eq.SCRIPTS)]  # not the network's arm: never picked
    picks = cli.side_picks(rows, 5)
    assert [(p["pick"], p["cell"], p["game"], p["class"]) for p in picks] == [
        (cli.PICK_FIXED_B, 1, 3, B), (cli.PICK_MIXED, 4, 1, B), (cli.PICK_FIXED_C, 1, 2, C),
        (cli.PICK_FILL, 1, 0, S), (cli.PICK_FILL, 1, 1, S)]
    assert [p["pick"] for p in cli.side_picks(rows, 2)] == [cli.PICK_FIXED_B, cli.PICK_MIXED]
    assert cli.side_picks(rows, 7)[-2:] == [
        {"pick": cli.PICK_FILL, "cell": 4, "game": 0, "class": S}, {"pick": cli.PICK_FILL, "cell": 4, "game": 2,
                                                                     "class": S}]
    # no flips at all (the oracle read): every slot takes an agreeing game, none twice
    flat = [_cell(0, cells.FIXED, 0, [S, S]), _cell(1, cells.FIXED, 0, [S, S]), _cell(2, cells.MIXED, 0, [S, S])]
    assert [(p["pick"], p["cell"], p["game"]) for p in cli.side_picks(flat, 4)] == [
        (cli.PICK_FIXED_B, 0, 0), (cli.PICK_MIXED, 2, 0), (cli.PICK_FIXED_C, 0, 1), (cli.PICK_FILL, 2, 1)]
    # only b and c games left: the fallback takes the lowest game not picked
    worn = [_cell(0, cells.FIXED, 2, [C, C]), _cell(1, cells.MIXED, 1, [B])]
    assert [(p["pick"], p["game"], p["class"]) for p in cli.side_picks(worn, 3)] == [
        (cli.PICK_FIXED_B, 0, C), (cli.PICK_MIXED, 0, B), (cli.PICK_FIXED_C, 1, C)]
    with pytest.raises(cli.Refused, match="mixed"):
        cli.side_picks([r for r in rows if r["kind"] != cells.MIXED], 3)
    with pytest.raises(cli.Refused, match="fixed"):
        cli.side_picks([r for r in rows if r["kind"] != cells.FIXED or r["arm"] != eq.NET], 3)
    # the cut: one pick per side at a time while the ask is above the cap, never below the minimum
    ask = {2: 0.21, 3: 0.29, 4: 0.37, 5: 0.45}
    assert cli.fit_to_cap(5, 0.3, lambda k: {"ask_gpu_h": ask[k]})[:2] == (3, {"ask_gpu_h": 0.29})
    assert cli.fit_to_cap(5, 0.5, lambda k: {"ask_gpu_h": ask[k]})[0] == 5
    count, est, fits = cli.fit_to_cap(4, 0.2, lambda k: {"ask_gpu_h": ask[k]})
    assert (count, est["ask_gpu_h"], fits) == (cli.MIN_PICKS_PER_SIDE, 0.21, False)
    assert cli.MIN_PICKS_PER_SIDE == 2 and "MIN_PICKS_PER_SIDE" in cli.RULE and "info" in cli.RULE


def test_plan_only_writes_nothing_and_refusals_exit_2(oracle_reads, drawn, tmp_path, small_settings, oracle,
                                                      monkeypatch):
    """--plan-only prints the picks, the GPU-h ask, the number of batch replays and their CPU estimate (the read's own
    layout seconds of those batches, a line of its own and inside the ask) and writes nothing. Exit 2, nothing written:
    --picks-per-side below MIN_PICKS_PER_SIDE; two reads of one side; a read whose results are not complete; a read
    with no mixed cell of the network; --out inside a read folder; no network file found (--skill-net left out for a
    network outside svg_training); an ask above the LS1.6 cap even at the minimum (plan only and run); a finished
    --out; a CUDA-recorded read on a machine without CUDA."""
    guard, strike = oracle_reads["guard"], oracle_reads["strike"]
    before = {r["folder"]: _tree(r["folder"]) for r in (guard, strike)}
    out = tmp_path / "out"
    code, lines = _main(_argv([guard, strike], out, extra=("--plan-only",)))
    assert code == cli.EXIT_DONE and not out.exists()
    assert {r["folder"]: _tree(r["folder"]) for r in (guard, strike)} == before
    plan = cli.plan([cli.load_read(r["folder"], [r["net"]]) for r in (guard, strike)], cli.DEFAULT_PICKS_PER_SIDE)
    est = plan["estimate"]
    layout = {}
    for side, r in (("guard", guard), ("strike", strike)):
        for b in json.loads((r["folder"] / eq.LAYOUT_FILE).read_text())["batches"]:
            layout[(side, b["name"])] = b["seconds"]
    assert est["batch_replays"] == len(plan["replays"]) < 2 * len(plan["picks"])
    assert est["replay_cpu_s"] == pytest.approx(sum(layout[(x["side"], x["batch"])] for x in plan["replays"]))
    assert est["expected_s"] > est["replay_cpu_s"] > 0
    text = "\n".join(lines)
    assert f"batch replays: {est['batch_replays']}" in text and f"ask --gpu-h {est['ask_gpu_h']:.2f}" in text
    assert "CPU" in text and f"cap {cli.task_cap_gpu_h():g}" in text
    ask_line = next(x for x in lines if "ask by picks per side:" in x)
    for k in range(cli.MIN_PICKS_PER_SIDE, cli.DEFAULT_PICKS_PER_SIDE + 1):
        assert f"{k}: {cli.plan([cli.load_read(r['folder'], [r['net']]) for r in (guard, strike)], k)['estimate']['ask_gpu_h']:.2f}" in ask_line

    def refused(argv, where=None):
        code, _ = _main(argv)
        assert code == cli.EXIT_REFUSED, argv
        if where is not None:
            assert not where.exists()
    refused(_argv([guard], tmp_path / "o1", extra=("--picks-per-side", str(cli.MIN_PICKS_PER_SIDE - 1))),
            tmp_path / "o1")
    refused(_argv([guard, guard], tmp_path / "o2"), tmp_path / "o2")
    unfinished = _copy(guard, tmp_path, "unfinished")
    res = json.loads((unfinished["folder"] / eq.RESULTS).read_text())
    res["complete"] = False
    (unfinished["folder"] / eq.RESULTS).write_text(json.dumps(res))
    refused(_argv([unfinished], tmp_path / "o3"), tmp_path / "o3")
    no_mixed = _copy(guard, tmp_path, "no_mixed")
    res = json.loads((no_mixed["folder"] / eq.RESULTS).read_text())
    res["cells"] = [c for c in res["cells"] if not (c["arm"] == eq.NET and c["kind"] == cells.MIXED)]
    (no_mixed["folder"] / eq.RESULTS).write_text(json.dumps(res))
    refused(_argv([no_mixed], tmp_path / "o4"), tmp_path / "o4")
    refused(_argv([guard], guard["folder"] / "clips"), guard["folder"] / "clips")
    code, _ = _main(["--equivalence", str(guard["folder"]), "--out", str(tmp_path / "o5"), "--plan-only"])
    assert code == cli.EXIT_REFUSED
    monkeypatch.setattr(cli, "task_cap_gpu_h", lambda: 0.0)
    refused(_argv([guard], tmp_path / "o6", extra=("--plan-only",)))
    refused(_argv([guard], tmp_path / "o7", small_settings), tmp_path / "o7")
    monkeypatch.undo()
    monkeypatch.setattr(eq, "net_check", _oracle_net_check)
    refused(_argv(drawn["reads"], drawn["out"], small_settings))                 # a finished folder
    assert json.loads((drawn["out"] / cli.CLIPS_JSON).read_text()) == drawn["report"]
    monkeypatch.setattr(cli.torch.cuda, "is_available", lambda: False)
    with pytest.raises(cli.Refused, match="CUDA"):
        cli.device_check("cuda:0")
    assert cli.device_check("cpu") is None
    assert {r["folder"]: _tree(r["folder"]) for r in (guard, strike)} == before
