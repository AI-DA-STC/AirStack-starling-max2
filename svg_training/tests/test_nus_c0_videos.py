"""scripts/nus_c0_videos.py (plan section 4.3, C0 videos: NUS's eval.py, two games per archived entry): an eval-ready folder per archived
entry (its best checkpoint linked, its config copied with the pool set to the entry's strongest opponent from its archive evaluation, or
APF alone) and one eval.py call each, in NUS's environment. Tested with a fake NUS layout and a fake eval.py that only writes two GIFs."""
import json
import sys
import textwrap

from _nus_markers import ROOT


def _fake_nus(tmp_path, run):
    clone = tmp_path / "clone"
    (clone / "ma_skills" / "scripts").mkdir(parents=True)
    (clone / "ma_skills" / "scripts" / "eval.py").write_text(textwrap.dedent("""
        import sys
        from pathlib import Path
        args = dict(a.split("=", 1) for a in sys.argv[1:])
        out = Path(args["hydra.run.dir"]) / "replays"
        out.mkdir(parents=True, exist_ok=True)
        for k in range(int(args["deployment_eval_episodes"])):
            (out / f"game{k}.gif").write_bytes(b"GIF89a")
        (Path(args["hydra.run.dir"]) / "seen.json").write_text(__import__("json").dumps(args))
        """))
    outputs = tmp_path / "outputs"
    # entry 2 does worst against generation 1 (its strongest opponent), entry 1 has only APF
    for generation, team, rows in ((1, "defender", [("APF", 1)]), (2, "attacker", [("generation_1", 1 / 2), ("APF", 1)])):
        name = f"{generation:04d}_{team}"
        entry = outputs / run / "archive" / name
        entry.mkdir(parents=True)
        (entry / "metadata.json").write_text(json.dumps({"evaluation": {"rows": [{"opponent": o, "win_rate": w} for o, w in rows]}}))
        best = outputs / run / "generations" / name / "checkpoints" / "best"
        best.mkdir(parents=True)
        (best / "state.msgpack").write_bytes(b"weights")
        (best / "config.json").write_text(json.dumps({"train_team": team, "opponent_pool_paths": ["x"], "include_apf_in_pool": True,
                                                     "environment": {"runner": {"_target_": "ensemble"}}}))
    return clone, outputs


def test_c0_videos_two_games_per_archived_entry(tmp_path, monkeypatch):
    import importlib.util
    spec = importlib.util.spec_from_file_location("nus_c0_videos", ROOT / "scripts" / "nus_c0_videos.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "RUNS_ROOT", tmp_path / "runs")
    run = "2026-11-18_c0_selfplay_3v3_seed101"
    clone, outputs = _fake_nus(tmp_path, run)
    out = tmp_path / "runs" / "c0" / "videos"
    assert mod.main(["--clone", str(clone), "--outputs-dir", str(outputs), "--runs", run, "--out", str(out),
                     "--python", sys.executable]) == 0
    for name, pool, apf in (("0001_defender", [], True), ("0002_attacker", [str(outputs / run / "archive" / "0001_defender")], False)):
        folder = out / run / name
        cfg = json.loads((folder / "ckpt" / "config.json").read_text())
        assert cfg["opponent_pool_paths"] == pool and cfg["include_apf_in_pool"] is apf and cfg["opponent_checkpoint_path"] is None
        assert cfg["environment"]["runner"]["_target_"].endswith("FixedOpponentRunner") and cfg["opponent_action_mode"] == "deterministic"
        assert (folder / "ckpt" / "state.msgpack").resolve() == (outputs / run / "generations" / name / "checkpoints" / "best" / "state.msgpack")
        assert len(list((folder / "eval" / "replays").glob("*.gif"))) == 2
        seen = json.loads((folder / "eval" / "seen.json").read_text())
        assert seen["checkpoint_path"] == str(folder / "ckpt") and seen["save_eval_gif"] == "True"
    summary = json.loads((out / "videos.json").read_text())
    assert len(summary["entries"]) == 2 and all(len(e["gifs"]) == 2 for e in summary["entries"])
