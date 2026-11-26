"""Route 3, stage LS1, task LS1-M4-T7: a route 3 run's post-run clips and run export (plan
ste_learning/drafts/LS1_TASK_PLAN.md section 5; B-4, C6). Tests only: the paths below already build the team through
the dispatch factory ``skills.two_level_dispatch``, which gives a ``NetTwoLevelDispatch`` under ``[learner]
skill_source = "net"``.

* The 2-D clips the driver draws inside a run of record (``scripts/ste_exploit_l012.py`` ``make_videos``, its dispatch
  at :930) fly the trained heads on the run's skill network.
* The 3-D clips (``scripts/ste_l5_clips3d.py``): ``build_team`` builds the net team (factory at :338) and ``capture``
  replays the run's INFO batch on the run's device (the CPU here: tolerance 0) equal to ``eval_info.npz`` game for game
  (``viz/replay3d.check_against_record``); a scripts-flown team on the same heads does not replay the record (the
  check is about the network). A replay that differs leaves that game undrawn, the clips job exits 1
  (``EXIT_MISMATCH``) and the post-run hook's marker says ``failed``, while the run folder (results, the training job's
  exit code) stands: the rule of the LS1.4 job table (plan section 6).
* The export of a route 3 run folder (``scripts/ste_l6_export.py --run-dir``, the run's own variant) exits 0 and its
  folder reloads in a fresh process on the exported skill network.

The runs: the training driver on the LS1.4 heads gate file's shape (``tests/_ste_ls1.net_gate_file(heads_shape=True)``:
tiny networks, pool on, a second variant ``base_s2`` on the base reference cells), a Guard run on ``base`` and a Strike
run on ``base_s2``, both with their 2-D clips, after a hand-made net pilot (``tests/test_ste_ls1_driver.hand_pilot``;
the driver-run fixture pattern of ``tests/test_ste_l3_pool.pooled_runs``). The 3-D render is the VID-1 renderer with
the stand-in Isaac (``FakeIsaac`` of tests/test_make_ste_3d.py, ``small_settings`` and ``fake_render`` of
tests/test_ste_l5_clips3d.py). Where the scripts must not fly, ``SkillDispatch.commands`` and ``act`` raise (the net
dispatch overrides both). CPU only; no GPU job."""
import hashlib
import json
import shutil
import sys
import types

import numpy as np
import pytest
import torch

import _ste_ls1 as H
from _ste_ls1 import ROOT, net_gate_file
from _torch_threads import DEFAULT_THREADS, default_torch_threads  # noqa: F401  (autouse: CPU numerics)
from svg_training.ste import exploit, export, post_run, shared, skills
from svg_training.viz import replay3d as r3
from test_ste_l5_clips3d import fake_render, small_settings  # noqa: F401  (fixtures)
from test_ste_ls1_driver import hand_pilot

sys.path.insert(0, str(ROOT / "scripts"))
import ste_exploit_l012 as driver  # noqa: E402
import ste_l5_clips3d as clips  # noqa: E402
import ste_l6_export as export_cli  # noqa: E402

RUNS = {"guard": "base", "strike": H.SECOND_VARIANT}     # (side: variant) of the two runs of record
CAP_H = "1"                                              # hand_pilot's projection: 1,440 game-steps in a 1 h cap


def _tree(folder, skip: str | None = None) -> dict:
    return {str(p.relative_to(folder)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(folder.rglob("*")) if p.is_file() and not (skip and p.relative_to(folder).parts[0] == skip)}


def _copy(run, tmp_path, name="run"):
    dst = tmp_path / name
    shutil.copytree(run, dst)
    return dst


@pytest.fixture
def no_scripts(monkeypatch):
    """The scripts' dispatch may not fly: ``SkillDispatch.commands`` and ``act`` raise (``NetTwoLevelDispatch``
    overrides both; ``TwoLevelDispatch`` inherits them)."""
    def no(*args, **kwargs):
        raise AssertionError("the scripts' skill dispatch flew a route 3 team")
    for name in ("commands", "act"):
        monkeypatch.setattr(skills.SkillDispatch, name, no)


@pytest.fixture(scope="module")
def route3_runs(tmp_path_factory):
    """The heads gate file's shape under tiny networks; a Guard run on base and a Strike run on base_s2 (its own run 0
    stand-in, per_variant), both drawing their 2-D clips. Records every dispatch the factory built during each run and
    each ``make_videos`` call (its config and the learner's saved dict)."""
    tmp = tmp_path_factory.mktemp("ls1_post_run")
    mp = pytest.MonkeyPatch()
    mp.setenv(shared.SHARED_ENV, str(tmp / "shared"))
    mp.setenv(shared.LEGACY_LOGS_ENV, "")
    threads = torch.get_num_threads()
    torch.set_num_threads(DEFAULT_THREADS)                   # the replays run at the default count (autouse fixture)
    dispatches, videos = [], []
    factory, draw = skills.two_level_dispatch, driver.make_videos

    def spy_factory(spec, players, team, cfg, num_games, device, seed):
        d = factory(spec, players, team, cfg, num_games, device, seed)
        dispatches.append({"team": team, "num_games": int(num_games), "device": str(device), "seed": int(seed),
                           "dispatch": d})
        return d

    def spy_videos(gates, variant, side, cfg, learner, run_dir, opponent=None):
        out = draw(gates, variant, side, cfg, learner, run_dir, opponent)
        videos.append({"variant": variant, "side": side, "cfg": cfg, "saved": learner.saved(), "lines": out})
        return out
    mp.setattr(skills, "two_level_dispatch", spy_factory)
    mp.setattr(driver, "make_videos", spy_videos)
    try:
        g_file, nets = net_gate_file(tmp / "gates", heads_shape=True)
        g = exploit.load_gates(g_file)
        pilot = tmp / "pilot.json"
        pilot.write_text(json.dumps(hand_pilot(g_file, recipe=g.trainer["side_overrides"]["strike"])))
        out = {"gates_file": g_file, "nets": nets, "pilot": pilot, "codes": {}, "dispatches": {}, "videos": {}}
        for side, variant in RUNS.items():
            run, r0 = tmp / side, []
            if side == "strike":                             # run 0 of the run's own variant ([run0] per_variant)
                r0_json = tmp / "run0.json"
                r0_json.write_text(json.dumps({"status": "PASS", "complete": True, "cap_h": float(CAP_H),
                                               "gates_sha256": g.sha256, "learner": skills.learner_table(g.learner),
                                               "variant": variant}))
                r0 = ["--run0-json", str(r0_json)]
            dispatches.clear()
            videos.clear()
            out["codes"][side] = driver.main(["--gates", str(g_file), "--variant", variant, "--side", side,
                                              "--run-dir", str(run), "--cap-h", CAP_H, "--pilot-json", str(pilot),
                                              *r0])
            out[side], out["dispatches"][side], out["videos"][side] = run, list(dispatches), list(videos)
    finally:
        mp.undo()
        torch.set_num_threads(threads)
    return out


def test_the_runs_are_route3_runs_of_record_on_the_heads_shape(route3_runs):
    assert route3_runs["codes"] == {"guard": 0, "strike": 0}
    g = exploit.load_gates(route3_runs["gates_file"])
    assert g.learner.skill_source == "net" and g.pool["enabled"] and g.run0["per_variant"]
    assert exploit.ref_variant(g, H.SECOND_VARIANT) == "base"
    for side, variant in RUNS.items():
        res = json.loads((route3_runs[side] / "results.json").read_text())
        assert res["complete"] is True and res["side"] == side and res["variant"] == variant
        assert res["learner"]["skill_source"] == "net"
        assert res["learner"]["skill_net_sha256"] == {s: route3_runs["nets"][s][1] for s in ("guard", "strike")}


# ================================================================================ the 2-D clips inside the driver
def test_make_videos_draws_a_net_team_clip(route3_runs, tmp_path, no_scripts):
    """Each run of record drew its 2-D clip (STANDARDS section 8) with a team built by the factory on the run's own
    skill network (the clip's dispatch: the videos' game count, the CPU, ``clip_seed``); drawn again with the scripts'
    dispatch forbidden, the clip is the same game, outcome and time."""
    g = exploit.load_gates(route3_runs["gates_file"])
    n, seed = int(g.videos["games"]), int(g.run["clip_seed"])
    for side, variant in RUNS.items():
        run = route3_runs[side]
        lines = json.loads((run / "results.json").read_text())["videos"]
        assert lines and lines[0].startswith("videos/"), lines
        gif = run / lines[0].split(":")[0]
        assert gif.suffix == ".gif" and gif.stat().st_size > 0 and gif.name.startswith(f"{variant}_{side}_game")
        clip = [c for c in route3_runs["dispatches"][side]
                if (c["team"], c["num_games"], c["device"], c["seed"]) == (side, n, "cpu", seed)]
        assert len(clip) == 1, [(c["team"], c["num_games"], c["device"], c["seed"])
                                for c in route3_runs["dispatches"][side]]
        d = clip[0]["dispatch"]
        assert isinstance(d, skills.NetTwoLevelDispatch)
        assert d.skill_net_sha256 == route3_runs["nets"][side][1]
        (call,) = route3_runs["videos"][side]
        assert (call["variant"], call["side"], call["lines"]) == (variant, side, lines)
        learner = types.SimpleNamespace(skills=d, saved=lambda saved=call["saved"]: saved)
        again = driver.make_videos(g, variant, side, call["cfg"], learner, tmp_path / side)
        assert [x.split(" (")[0] for x in again] == [x.split(" (")[0] for x in lines]


# ================================================================================ the 3-D clips (post-run job)
def test_build_team_builds_the_net_team_and_its_replay_equals_the_record(route3_runs, tmp_path, no_scripts):
    """``build_team`` builds the trained heads on the run's network (the run's variant: its game and train seed), and
    ``capture`` replays the whole INFO batch on the CPU equal to the record at tolerance 0, every picked game too."""
    g = exploit.load_gates(route3_runs["gates_file"])
    for side, variant in RUNS.items():
        d = clips.load_run(route3_runs[side])
        assert (d["side"], d["variant"]) == (side, variant)
        team = clips.build_team(d, "cpu")
        assert isinstance(team.dispatch, skills.NetTwoLevelDispatch)
        assert team.dispatch.skill_net_sha256 == route3_runs["nets"][side][1] and team.dispatch.team == side
        picks = clips.plan(d)["picks"]
        assert picks, side
        picks, batch = clips.capture(d, picks, tmp_path / side, "test")
        cells = driver.info_cells(g, side)
        assert batch["equal"] is True and batch["tol_m"] == 0.0, batch
        assert batch["games_compared"] == len(cells) * int(g.run["eval_games"]) == len(d["info"]["outcome"])
        assert not any(batch["mismatches"].values()), batch
        for p in picks:
            assert p["check"]["equal"] and p["recorded"] == p["replayed"], p
            t = r3.load_trajectory(tmp_path / side / p["trajectory"])
            assert t.meta["variant"] == variant and t.meta["side"] == side
            assert (t.outcome, t.end_step) == (p["recorded"]["outcome"], p["recorded"]["end_step"])


def test_the_replay_check_is_about_the_network(route3_runs, tmp_path, monkeypatch):
    """The same trained heads flown on the scripts' dispatch do not replay the record: the equality above holds
    because the replay flew the run's network."""
    build = clips.build_team
    for side in RUNS:
        d = clips.load_run(route3_runs[side])
        net_team = build(d, "cpu")
        nd = net_team.dispatch
        sd = skills.TwoLevelDispatch(side, list(nd.names), list(nd.team_strategies), list(nd.drone_skills),
                                     exploit.train_cfg(d["gates"], d["variant"]), int(d["gates"].trainer["num_games"]),
                                     "cpu", int(d["gates"].variants[d["variant"]]["train_seed"][side]))
        assert not isinstance(sd, skills.NetTwoLevelDispatch)
        scripts_team = exploit.SkillTeam(side, net_team.nets, net_team.scalers, sd)
        monkeypatch.setattr(clips, "build_team", lambda d_, device: scripts_team)
        _, batch = clips.capture(d, clips.plan(d)["picks"], tmp_path / side, "test")
        assert batch["equal"] is False and any(batch["mismatches"].values()), (side, batch)


def test_the_3d_clips_of_a_route3_run_are_drawn_into_videos3d_only(route3_runs, tmp_path, fake_render,  # noqa: F811
                                                                   small_settings, no_scripts):
    for side in RUNS:
        run = _copy(route3_runs[side], tmp_path, side)
        before = _tree(run)
        assert clips.main(["--run-dir", str(run), "--settings", small_settings]) == clips.EXIT_DONE
        assert _tree(run, skip=clips.DEFAULT_OUT) == before                       # nothing else written
        rep = json.loads((run / clips.DEFAULT_OUT / clips.CLIPS_JSON).read_text())
        assert rep["complete"] is True and rep["side"] == side and rep["batch_check"]["equal"]
        assert rep["picks"] and all(p["check"]["equal"] and "files" in p for p in rep["picks"])
        for p in rep["picks"]:
            for cam in ("top", "3d"):
                assert (run / clips.DEFAULT_OUT / f"{p['stem']}_{cam}.mp4").stat().st_size > 0
    assert len(fake_render) == len(RUNS)


@pytest.mark.parametrize("side", list(RUNS))
def test_a_net_replay_that_differs_is_not_drawn_and_exits_1(route3_runs, tmp_path, fake_render,  # noqa: F811
                                                           small_settings, side):
    """One ``end_step`` of ``eval_info.npz`` tampered: that game is not drawn, the clips job exits 1 and the hook's
    marker says ``failed`` (not ``pending``); the run folder outside ``videos3d/`` (its results, the training job's
    exit code) is left as it was. The hook is on for a route 3 run of record by command."""
    run = _copy(route3_runs[side], tmp_path)
    d = clips.load_run(run)
    picks = clips.plan(d)["picks"]
    g = picks[0]["global_index"]
    info = dict(np.load(run / "eval_info.npz"))
    info["end_step"][g] += 1                                   # the record now differs from any replay of that game
    np.savez(run / "eval_info.npz", **info)
    (run / "exit_code").write_text("0\n")                      # the training job's exit code (ste/jobs.py writes it)
    before = _tree(run)
    assert clips.main(["--run-dir", str(run), "--settings", small_settings]) == clips.EXIT_MISMATCH == 1
    out = run / clips.DEFAULT_OUT
    rep = json.loads((out / clips.CLIPS_JSON).read_text())
    bad = next(p for p in rep["picks"] if p["global_index"] == g)
    assert not bad["check"]["equal"] and bad["check"]["mismatches"]["end_step"] == 1
    assert "trajectory" not in bad and "files" not in bad
    assert not list(out.glob(f"*{bad['pick']}*")) and not list((out / "trajectories").glob(f"*{bad['pick']}*"))
    assert not rep["batch_check"]["equal"] and rep["batch_check"]["mismatches"]["end_step"] == 1
    assert rep["complete"] is True
    drawn = [p for p in rep["picks"] if p["global_index"] != g]
    assert all("files" in p for p in drawn) and len(fake_render) == (1 if drawn else 0)
    said = []
    record = {"name": f"clips3d_{side}", "run_dir": str(out), "clips3d_for": str(run)}
    assert post_run.clips_ended(run, record, clips.EXIT_MISMATCH, said.append) == post_run.FAILED
    assert post_run.hook_state(run, {}) == post_run.FAILED
    assert (out / post_run.HOOK_STATUS).read_text().startswith(f"{post_run.FAILED}: job clips3d_{side} exit 1")
    assert _tree(run, skip=clips.DEFAULT_OUT) == before        # the run stands
    variant = RUNS[side]
    cmd = [sys.executable, str(ROOT / "scripts" / "ste_exploit_l012.py"), "--gates", str(route3_runs["gates_file"]),
           "--variant", variant, "--side", side, "--run-dir", str(run), "--cap-h", CAP_H]
    assert post_run.drives_training(cmd)
    assert not post_run.drives_training(cmd + ["--run0"]) and not post_run.drives_training(cmd + ["--pilot"])


# ================================================================================ the run export
def test_the_export_of_a_route3_run_folder_exits_0_and_reloads(route3_runs, tmp_path, no_scripts):
    """``ste_l6_export.py --run-dir`` on each route 3 run: exit 0, the heads and the skill network's graph in one
    folder of the net schema, the run's variant and its train seed recorded, the control PASS; the folder reloads in a
    fresh process flying the exported network."""
    pytest.importorskip("onnxruntime")
    import ste_l6_read as reader
    import tomllib
    g = exploit.load_gates(route3_runs["gates_file"])
    for side, variant in RUNS.items():
        run, out = route3_runs[side], tmp_path / side
        assert export_cli.main(["--run-dir", str(run), "--out", str(out)]) == export_cli.EXIT_DONE
        controls = json.loads((out / "controls.json").read_text())
        assert controls["ctl_team_equals_export"]["status"] == "PASS", controls
        data = tomllib.loads((out / "interface.toml").read_text())
        assert data["policy_schema"] == export.SKILLS_NET_SCHEMA and data["team"] == side
        assert data["skills"]["skill_source"] == "net"
        assert data["skills"]["skill_net_sha256"] == data["skill_net"]["net_sha256"] == route3_runs["nets"][side][1]
        assert (out / data["skill_net"]["file"]).is_file()
        assert data["source_checkpoint_sha256"] == exploit.sha256_file(run / "agent_final.pt")
        assert data["gates_sha256"] == g.sha256 and data["seed"] == int(g.variants[variant]["train_seed"][side])
        assert data.get("variant", "base") == variant
        back = reader.reload_in_a_fresh_process(out)
        assert back["ok"] and back["route"] == "skills" and back["skill_source"] == "net", back
        assert back["choices_equal"] and back["skill_lists_equal"]
