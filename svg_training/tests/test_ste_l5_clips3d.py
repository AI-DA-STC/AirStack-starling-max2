"""STE L5 3-D clips (``scripts/ste_l5_clips3d.py``) on run folders the real driver wrote (a velocity Guard run and a
two-level skills Strike run on the pool, tiny, CPU: ``tests/test_ste_l3_pool.py``'s fixture). The Isaac render is the
VID-1 renderer with the stand-in Isaac of ``tests/test_make_ste_3d.py``; the encode is real (ffmpeg), on a small frame.

Checked: the key-game rule (worst cell without z_up_info, a won and a lost game, the opponent met most in training
from the pool counters), the replay equals the record before a game is drawn (both routes), a game that differs is
recorded and not drawn (exit 1), MP4 + GIF per camera, clips3d.json complete last, nothing written in the run folder
but videos3d/, the refusals (exit 2). CPU only."""
import argparse
import hashlib
import json
import shutil
import sys

import numpy as np
import pytest

from svg_training.ste import exploit
from svg_training.viz import replay3d as r3
from svg_training.viz.starling_look import SETTINGS_FILE

from _ste_tools import SCRIPTS
from test_make_ste_3d import FakeIsaac, m3
from test_ste_l3_pool import pooled_runs  # noqa: F401  (module fixture)

sys.path.insert(0, str(SCRIPTS))
import ste_l5_clips3d as cli  # noqa: E402


@pytest.fixture(scope="module")
def small_settings(tmp_path_factory):
    """configs/ste_video.toml at 320 x 180 (the encode's speed in tests; every other value as it is)."""
    p = tmp_path_factory.mktemp("video") / "ste_video.toml"
    text = SETTINGS_FILE.read_text()
    assert "resolution = [1280, 720]" in text
    p.write_text(text.replace("resolution = [1280, 720]", "resolution = [320, 180]"))
    return str(p)


@pytest.fixture
def fake_render(monkeypatch):
    """The render stage on the VID-1 renderer with the stand-in Isaac (no preflight, no child process)."""
    calls = []

    def render(out, work, trajectories, settings):
        calls.append([str(p) for p in trajectories])
        a = argparse.Namespace(work=str(work), settings=settings, stills=False, replay=[str(p) for p in trajectories],
                               arena_frame=None, encode=False, smoke=False)
        return m3.render(a, FakeIsaac())
    monkeypatch.setattr(cli, "render_stage", render)
    return calls


def _tree(folder):
    return {str(p.relative_to(folder)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(folder.rglob("*")) if p.is_file()}


def _copy(run, tmp_path, name="run"):
    dst = tmp_path / name
    shutil.copytree(run, dst)
    return dst


@pytest.mark.parametrize("side", ["guard", "strike"])
def test_both_routes_draw_the_recorded_key_games_into_videos3d_only(pooled_runs, side, tmp_path, fake_render,  # noqa: F811
                                                                    small_settings):
    run = _copy(pooled_runs[side][1], tmp_path)
    before = _tree(run)
    assert cli.main(["--run-dir", str(run), "--settings", small_settings]) == 0
    after = _tree(run)
    assert {k: v for k, v in after.items() if not k.startswith("videos3d/")} == before     # nothing else written
    out = run / "videos3d"
    rep = json.loads((out / "clips3d.json").read_text())
    assert rep["complete"] is True and rep["side"] == side and rep["rule"] == cli.RULE
    assert rep["route"] == ("skills (two-level)" if side == "strike" else "velocity")
    assert rep["batch_check"]["equal"] and len(rep["picks"]) >= 1
    info = np.load(run / "eval_info.npz")
    for p in rep["picks"]:
        assert p["check"]["equal"], p
        g = p["global_index"]
        t = r3.load_trajectory(out / p["trajectory"])
        assert (t.outcome, t.end_step) == (int(info["outcome"][g]), int(info["end_step"][g]))
        assert t.meta["kind"] == "l5_trained" and t.meta["side"] == side
        for cam in ("top", "3d"):
            assert (out / f"{p['stem']}_{cam}.mp4").stat().st_size > 0
            assert (out / f"{p['stem']}_{cam}.gif").stat().st_size > 0
            assert p["files"][cam]["gif"]["file"] == f"{p['stem']}_{cam}.gif"
        assert "not a flight" in p["caption"] and f"the {rep['task']} run's evaluation" in p["caption"]
    assert len(fake_render) == 1 and len(fake_render[0]) == len(rep["picks"])


def test_the_rule_on_the_driver_runs(pooled_runs):  # noqa: F811
    for side in ("guard", "strike"):
        d = cli.load_run(pooled_runs[side][1])
        rows = cli.info_table(d)
        worst = cli.worst_cell(rows)
        eligible = [r for r in rows if not r["z_up_info"]] or rows
        assert worst["rate"] == min(r["rate"] for r in eligible) and not worst["z_up_info"]
        meet = cli.training_meetings(d)
        assert meet["agrees_with_train_log"] and sum(meet["counts"].values()) == meet["games_total"] > 0
        assert meet["counts"][meet["most"]] == max(meet["counts"].values())
        picks = cli.pick_games(d, rows, worst, meet["most"])
        n = int(d["gates"].run["eval_games"])
        out = d["info"]["outcome"]
        for p in picks:
            k, g = p["cell_index"], p["game_index"]
            assert p["global_index"] == k * n + g and out[k * n + g] != cli.UNFINISHED
            cell = out[k * n:(k + 1) * n]
            if p["pick"] == "worst_won":
                assert k == worst["cell_index"] and g == int(np.flatnonzero(cell == cli.won_code(side))[0])
            elif p["pick"] == "worst_lost":
                assert k == worst["cell_index"] and g == int(np.flatnonzero(cell == cli.lost_code(side))[0])
            elif p["pick"] == "most_met":
                assert p["opponent"] == meet["most"] != worst["opponent"]
            else:
                assert p["pick"].startswith("next_worst_") and k != worst["cell_index"] and len(picks) <= 2
        assert len({p["global_index"] for p in picks}) == len(picks)
        assert not [p for p in cli.pick_games(d, rows, worst, worst["opponent"]) if p["pick"] == "most_met"]


def test_worst_cell_leaves_out_z_up_info_and_breaks_ties_in_players_order():
    rows = [{"cell_index": 0, "opponent": "a", "rate": 0.5, "z_up_info": False},
            {"cell_index": 1, "opponent": "b", "rate": 0.1, "z_up_info": True},
            {"cell_index": 2, "opponent": "c", "rate": 0.5, "z_up_info": False}]
    assert cli.worst_cell(rows)["opponent"] == "a"
    assert cli.worst_cell([dict(r, z_up_info=True) for r in rows])["opponent"] == "b"


def test_a_game_that_differs_from_the_record_is_not_drawn(pooled_runs, tmp_path, fake_render, small_settings):  # noqa: F811
    run = _copy(pooled_runs["guard"][1], tmp_path)
    d = cli.load_run(run)
    picks = cli.plan(d)["picks"]
    g = picks[0]["global_index"]
    info = dict(np.load(run / "eval_info.npz"))
    info["end_step"][g] += 1                                   # the record now differs from any replay of that game
    np.savez(run / "eval_info.npz", **info)
    out = tmp_path / "out"
    assert cli.main(["--run-dir", str(run), "--out", str(out), "--settings", small_settings]) == 1
    rep = json.loads((out / "clips3d.json").read_text())
    bad = next(p for p in rep["picks"] if p["global_index"] == g)
    assert not bad["check"]["equal"] and "trajectory" not in bad and "files" not in bad
    assert not list(out.glob(f"*{bad['pick']}*"))
    assert not list((out / "trajectories").glob(f"*{bad['pick']}*"))
    assert not rep["batch_check"]["equal"] and rep["complete"] is True
    drawn = [p for p in rep["picks"] if p["global_index"] != g]
    assert all("files" in p for p in drawn) and len(fake_render[0]) == len(drawn)


def test_refusals_exit_2_and_plan_only_writes_nothing(pooled_runs, tmp_path, fake_render, small_settings):  # noqa: F811
    src = pooled_runs["guard"][1]
    run = _copy(src, tmp_path)
    before = _tree(run)
    assert cli.main(["--run-dir", str(run), "--plan-only"]) == 0 and _tree(run) == before
    bad = _copy(src, tmp_path, "pin")
    (bad / "gates.sha256").write_text("0" * 64 + "\n")
    assert cli.main(["--run-dir", str(bad), "--plan-only"]) == 2
    bad = _copy(src, tmp_path, "unfinished")
    res = json.loads((bad / "results.json").read_text())
    res["complete"] = False
    (bad / "results.json").write_text(json.dumps(res))
    assert cli.main(["--run-dir", str(bad), "--plan-only"]) == 2
    bad = _copy(src, tmp_path, "counts")                       # results.json's INFO block is not eval_info.npz
    res = json.loads((bad / "results.json").read_text())
    first = next(iter(res["info"]))
    res["info"][first]["holds"] += 1
    (bad / "results.json").write_text(json.dumps(res))
    assert cli.main(["--run-dir", str(bad), "--plan-only"]) == 2
    bad = _copy(src, tmp_path, "nopool")
    (bad / "checkpoint.latest").unlink()
    assert cli.main(["--run-dir", str(bad), "--plan-only"]) == 2
    assert cli.main(["--run-dir", str(run), "--out", str(run / "elsewhere")]) == 2     # inside the run, not videos3d
    out = tmp_path / "done"
    assert cli.main(["--run-dir", str(run), "--out", str(out), "--settings", small_settings]) == 0
    assert cli.main(["--run-dir", str(run), "--out", str(out), "--settings", small_settings]) == 2   # finished folder


def test_a_cuda_record_is_not_replayed_on_the_cpu(pooled_runs, tmp_path, monkeypatch, fake_render):  # noqa: F811
    import torch
    run = _copy(pooled_runs["guard"][1], tmp_path)
    d = cli.load_run(run)
    d["gates"].run["device"] = "cuda"
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    with pytest.raises(cli.Refused, match="CUDA"):
        cli.capture(d, cli.plan(d)["picks"], tmp_path / "o", "test")


# ========================================================================================= fix round (lead, 25 Nov)
def test_gif_ticks_compress_a_long_game_and_keep_its_first_and_last_tick():
    for frames in (52, 149, 130, 131, 2401, 1777):
        step, keep = cli.gif_ticks(frames, 20, 150)
        assert keep[0] == 0 and keep[-1] == frames - 1 and len(keep) + 20 <= 150
        assert keep == sorted(set(keep)) and all(b - a <= step for a, b in zip(keep, keep[1:]))
        assert (step == 1) == (frames <= 130)
    assert cli.gif_ticks(2401, 20, 150)[0] >= 19


def _fake_d(outcomes_by_cell, side="guard"):
    n = len(outcomes_by_cell[0])
    gates = argparse.Namespace(run={"eval_games": n})
    return {"side": side, "info": {"outcome": np.concatenate([np.asarray(c, np.int8) for c in outcomes_by_cell])},
            "gates": gates}


def test_fewer_than_two_games_take_the_next_worst_cell():
    won, lost = cli.won_code("guard"), cli.lost_code("guard")
    d = _fake_d([[lost, lost, lost], [won, lost, won], [lost, won, won]])
    rows = [{"cell_index": k, "opponent": f"o{k}", "rate": r, "z_up_info": False}
            for k, r in enumerate((0.0, 2 / 3, 2 / 3))]
    worst = cli.worst_cell(rows)
    picks = cli.pick_games(d, rows, worst, worst["opponent"])          # most met = the worst cell's opponent
    assert [p["pick"] for p in picks] == ["worst_lost", "next_worst_won"]
    assert (picks[1]["cell_index"], picks[1]["game_index"]) == (1, 0)    # next worst by rate, then cell order
    d = _fake_d([[won, won, won], [won, lost, won], [lost, lost, won]])  # only wins in the worst cell: a loss next
    rows = [{"cell_index": k, "opponent": f"o{k}", "rate": r, "z_up_info": z}
            for k, (r, z) in enumerate(((1.0, False), (2 / 3, True), (1 / 3, False)))]
    worst = cli.worst_cell(rows)
    assert worst["cell_index"] == 2
    d = _fake_d([[won, won, won], [won, lost, won], [won, won, won]])
    rows = [{"cell_index": k, "opponent": f"o{k}", "rate": r, "z_up_info": z}
            for k, (r, z) in enumerate(((1.0, False), (2 / 3, True), (1.0, False)))]
    worst = cli.worst_cell(rows)                                          # cell 0 (z_up_info cell 1 left out)
    picks = cli.pick_games(d, rows, worst, worst["opponent"])
    assert [p["pick"] for p in picks] == ["worst_won", "next_worst_lost"] and picks[1]["cell_index"] == 1
    assert "(3) Fewer than two games" in cli.RULE


def test_the_ask_scales_with_the_ticks_to_render(pooled_runs):  # noqa: F811
    d = cli.load_run(pooled_runs["guard"][1])
    p = cli.plan(d)
    e = p["estimate"]
    assert e["ticks_to_render"] == sum(int(d["info"]["end_step"][x["global_index"]]) + 1 for x in p["picks"])
    longer = [dict(x) for x in p["picks"]]
    d["info"] = dict(d["info"], end_step=d["info"]["end_step"] + 2000)
    e2 = cli.estimate(d, longer)
    assert e2["ticks_to_render"] == e["ticks_to_render"] + 2000 * len(longer) and e2["ask_gpu_h"] > e["ask_gpu_h"]


def _long_traj(tmp_path, end=400):
    from svg_training.core.rewards import STRIKE_WIN
    t = end + 1
    pos = np.zeros((t, 6, 3), np.float32)
    pos[:, :, 2] = 1.2
    pos[:, :, 0] = np.linspace(-2, 2, 6)[None]
    pos[:, 3:, 1] = np.linspace(2.5, 0.0, t)[:, None]
    alive = np.ones((t, 6), bool)
    alive[200:, 0] = False
    tr = r3.Trajectory(pos, np.zeros((t, 6), np.float32), alive, 3, 3, 3.25, 0.25, (0.5, 1.8), np.zeros(2), 1.6, 1.6,
                       STRIKE_WIN, end,
                       {"kind": "l5_trained", "task": "L5.1", "route": "velocity", "side": "strike", "variant": "base",
                        "pick": "worst_won", "guard": "guard_field", "strike": "trained Strike team",
                        "game_index": 8, "tags": 1})
    return r3.save_trajectory(tmp_path / "trajectories" / "long", tr)


def test_a_long_game_keeps_every_tick_in_the_mp4_and_a_time_compressed_gif(tmp_path, small_settings):
    import imageio.v2 as imageio
    p = _long_traj(tmp_path)
    work = tmp_path / "work"
    a = argparse.Namespace(work=str(work), settings=small_settings, stills=False, replay=[str(p)], arena_frame=None,
                           encode=False, smoke=False)
    assert m3.render(a, FakeIsaac()) == 0
    out = tmp_path / "out"
    out.mkdir()
    enc = cli.encode_clips(out, work, small_settings)["long"]
    hold = 20
    for cam in ("top", "3d"):
        f = enc["files"][cam]
        assert "mp4_error" not in f and "gif_error" not in f, f
        assert sum(1 for _ in imageio.get_reader(str(out / f["mp4"]))) == 401 + hold == f["mp4_frames"]
        g = f["gif"]
        step, keep = cli.gif_ticks(401, hold, cli.GIF_FRAME_CAPS[0])
        assert g["tick_step"] == step > 1 and g["frames"] == len(keep) + hold <= cli.GIF_FRAME_CAPS[0]
        assert g["speed_x"] == 0.5 * step and f"{0.5 * step:g}x real time" in g["caption"]
        assert sum(1 for _ in imageio.get_reader(str(out / g["file"]))) == g["frames"]
        assert g["mb"] <= 5.0


def test_a_gif_that_fails_keeps_the_mp4_and_the_other_clips(pooled_runs, tmp_path, fake_render, small_settings,  # noqa: F811
                                                            monkeypatch):
    run = _copy(pooled_runs["guard"][1], tmp_path)
    calls = []

    def no_fit(frames, path, fps, max_mb):
        calls.append(path.name)
        return None if path.name == calls[0] else real(frames, path, fps, max_mb)
    real = cli.fit_gif
    monkeypatch.setattr(cli, "fit_gif", no_fit)
    out = tmp_path / "out"
    assert cli.main(["--run-dir", str(run), "--out", str(out), "--settings", small_settings]) == 0
    rep = json.loads((out / "clips3d.json").read_text())
    assert rep["complete"] and len(rep["clip_failures"]) == 1 and "gif_error" in rep["clip_failures"][0]
    first = rep["picks"][0]["files"]["top"]
    assert "gif_error" in first and (out / first["mp4"]).is_file()
    assert rep["clips_made"] == 4 * len(rep["picks"]) - 1

    def boom(*a, **k):
        raise RuntimeError("encoder down")
    monkeypatch.setattr(cli, "fit_gif", lambda *a, **k: None)
    monkeypatch.setattr(cli, "stream_mp4", boom)
    out2 = tmp_path / "out2"
    assert cli.main(["--run-dir", str(run), "--out", str(out2), "--settings", small_settings]) == 3
    rep = json.loads((out2 / "clips3d.json").read_text())
    assert rep["clips_made"] == 0 and rep["clip_failures"]
