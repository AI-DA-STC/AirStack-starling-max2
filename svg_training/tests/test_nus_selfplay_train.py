"""Phase 5 task M7: the trainer (scripts/nus_selfplay_train.py) and the 5.1-b pool builder, on the CPU with marker files and tiny
counts: the batch shapes of 5.1 / 5.1b / 5.1c, the GPU-hours log (overlapping jobs counted once, CPU jobs not counted), the probe and
the cap refusal, the hard wall-clock stop, a whole tiny run with its videos (one per selection evaluation, two per archived entry) and
record draft, and nothing written outside runs/."""
import importlib.util
import json
import time
from pathlib import Path

import pytest

from _nus_markers import ROOT, load_marker_files
from _nus_phase5_method_fixture import (HOUR, LOG_ROWS, LOG_S51_HOURS, PROBE_UPDATES, RUN_SEED, TINY_CAP, TINY_VARIANTS, TRAIN_GENERATIONS,
                                        marker_env, marker_method, write_method_toml)


@pytest.fixture()
def trainer(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("nus_selfplay_train", ROOT / "scripts" / "nus_selfplay_train.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "RUNS_ROOT", tmp_path / "runs")
    monkeypatch.setattr(mod, "STAGE_DIR", tmp_path / "runs" / "phase5")
    gates = tmp_path / "gates.toml"
    gates.write_text(TINY_VARIANTS)
    monkeypatch.setattr(mod, "GATES", gates)
    return mod


def _args(tmp_path, *extra):
    _, _, rules, deploy = load_marker_files(tmp_path / "inputs")
    method = tmp_path / "inputs" / "nus_method.toml"
    write_method_toml(method, marker_method())
    return ["--seed", str(RUN_SEED), "--rules", str(rules), "--deploy", str(deploy), "--method", str(method), "--generations",
            str(TRAIN_GENERATIONS), "--probe-updates", str(PROBE_UPDATES), *extra]


def test_batch_shapes(tmp_path, trainer):
    import tomllib
    env = marker_env(tmp_path)
    gates = tomllib.loads(TINY_VARIANTS)["gates"]
    assert trainer.batch_shape("nus", env.method, env.episode_steps, gates) == {}
    table = gates["phase5_method_variants"]
    for variant, key in (("5.1b", "s51b"), ("5.1c", "s51c")):
        shape = trainer.batch_shape(variant, env.method, env.episode_steps, gates)
        assert shape["games_per_update"] == table["games_per_update"]
        assert shape["updates_per_generation"] == table["updates_per_generation"][key]
        assert list(shape["selection_after"]) == table["selection_evaluations_after_update"][key]
        m = env.method
        assert shape["minibatch_samples"] == m.minimum_rollout_batch * env.episode_steps // m.ppo_minibatches
        samples = shape["games_per_update"] * env.episode_steps
        assert abs(shape["minibatches"] * shape["minibatch_samples"] - samples) <= shape["minibatch_samples"]


def test_gpu_hours_log_counts_overlap_once(tmp_path, trainer):
    log = tmp_path / "runs" / "gpu_hours.log"
    for group, device, start, end in LOG_ROWS:
        trainer.append_log(log, {"group": group, "device": device, "start": start, "end": end})
    assert trainer.logged_hours(log, "s51") == pytest.approx(LOG_S51_HOURS)
    assert trainer.logged_hours(tmp_path / "absent.log", "s51") == 0
    assert trainer.HOUR_S == HOUR


def test_tiny_run_with_probe_videos_and_record(tmp_path, trainer):
    out = tmp_path / "runs" / "phase5" / "s51" / "seed"
    assert trainer.main(_args(tmp_path, "--variant", "nus", "--out", str(out), "--video-format", "gif", "--log-note", "smoke")) == 0
    probe = json.loads((out / "probe.json").read_text())
    assert probe["updates_timed"] == PROBE_UPDATES and probe["estimate_hours"] > 0 and probe["within_cap"]
    assert probe["peak_allocated_gib"] is None and probe["peak_reserved_gib"] is None      # CUDA only
    assert probe["estimate_hours_three_seeds_one_after_another"] == pytest.approx(probe["estimate_hours"] * (2 + 1))
    state = json.loads((out / "self_play_state.json").read_text())
    assert [e["team"] for e in state["archive"]] == ["guard", "strike"][:TRAIN_GENERATIONS]
    selections = sum(len(json.loads((Path(e["path"]) / "metadata.json").read_text())["evaluations"]) for e in state["archive"])
    videos = sorted((out / "videos").glob("*.gif"))
    assert len(videos) == selections + 2 * len(state["archive"])
    draft = (out / "record_draft.md").read_text()
    assert "training simulator" in draft and "complete" in draft and all(v.name in draft for v in videos)
    log = [json.loads(line) for line in (tmp_path / "runs" / "phase5" / "s51" / "gpu_hours.log").read_text().splitlines()]
    assert [r["what"] for r in log] == ["probe", "train"] and all(r["device"] == "cpu" for r in log)
    assert all(r["note"] == "smoke" for r in log)
    assert all("runs" in p.relative_to(tmp_path).parts or p.relative_to(tmp_path).parts[0] in ("inputs", "gates.toml")
               for p in tmp_path.rglob("*") if p.is_file())


def test_variant_shape_reaches_the_run(tmp_path, trainer):
    out = tmp_path / "runs" / "phase5" / "s51c" / "seed"
    assert trainer.main(_args(tmp_path, "--variant", "5.1c", "--out", str(out), "--video-format", "none")) == 0
    state = json.loads((out / "self_play_state.json").read_text())
    import tomllib
    table = tomllib.loads(TINY_VARIANTS)["gates"]["phase5_method_variants"]
    for e in state["archive"]:
        meta = json.loads((Path(e["path"]) / "metadata.json").read_text())
        slots = len(meta["opponent_generations"]) + 1
        assert meta["games_per_update"] % slots == 0 and meta["games_per_update"] >= table["games_per_update"]
        assert [ev["update"] for ev in meta["evaluations"]] == table["selection_evaluations_after_update"]["s51c"]


def test_cap_refusal_and_hard_stop(tmp_path, trainer, monkeypatch):
    config = tmp_path / "config.toml"
    config.write_text((ROOT / "configs" / "nus_phase5_method.toml").read_text().replace("s51 = 36", f"s51 = {TINY_CAP}"))
    monkeypatch.setattr(trainer, "CONFIG", config)
    out = tmp_path / "runs" / "phase5" / "s51" / "refused"
    assert trainer.main(_args(tmp_path, "--variant", "nus", "--out", str(out), "--video-format", "none")) == trainer.EXIT_REFUSED
    assert not (out / "self_play_state.json").exists() and (out / "probe.json").exists()
    # the hard limit: a deadline already past stops at the first update boundary, with a checkpoint
    from svg_training.nus.selfplay import SelfPlay
    env = marker_env(tmp_path)
    sp = SelfPlay(env.method, env, RUN_SEED, tmp_path / "runs" / "deadline")
    sp.run(deadline=time.monotonic())
    state = json.loads((tmp_path / "runs" / "deadline" / "self_play_state.json").read_text())
    assert sp.stopped_by_deadline and state["active"]["update"] == 0 and state["active"]["checkpoint"]


def test_selection_pools(tmp_path):
    from svg_training.nus import crossplay as X
    entries = [X.Entry("o", g, "guard" if g % 2 else "strike") for g in range(1, 2 ** 2 * 2 + 1)]
    pools = X.selection_pools(entries, RUN_SEED, maximum=len(entries), recent=1)
    for e in entries:
        assert pools[e] == [o for o in entries if o.generation < e.generation and o.team != e.team]
    small = X.selection_pools(entries, RUN_SEED, maximum=2, recent=1)
    last = entries[-1]
    assert len(small[last]) == 2 and small[last][-1] == pools[last][-1]       # the latest entry is always kept
    with pytest.raises(ValueError):
        X.selection_pools(entries + [X.Entry("other", 1, "guard")], RUN_SEED, maximum=2, recent=1)


def test_stop_request_checkpoints_at_the_next_update_boundary(tmp_path):
    """gpu_pause.sh stop sends SIGINT: the trainer's handler sets a flag, and the run checkpoints and returns at the next update
    boundary (the same command resumes it)."""
    import os
    import signal

    from svg_training.nus.selfplay import SelfPlay
    env = marker_env(tmp_path)
    sp = SelfPlay(env.method, env, RUN_SEED, tmp_path / "runs" / "stop")
    previous = signal.getsignal(signal.SIGINT)
    try:
        from nus_selfplay_train import install_stop_handler
        install_stop_handler(sp)
        sp.on_selection = lambda s, result: os.kill(os.getpid(), signal.SIGINT)
        sp.run()
    finally:
        signal.signal(signal.SIGINT, previous)
    state = json.loads((tmp_path / "runs" / "stop" / "self_play_state.json").read_text())
    assert sp.stopped == "interrupted" and not sp.stopped_by_deadline
    assert state["active"]["update"] == min(sp.selection_after) and state["active"]["checkpoint"] and state["archive"] == []
    resumed = SelfPlay(env.method, env, RUN_SEED, tmp_path / "runs" / "stop").run()
    assert len(resumed) == env.method.generations


def test_caps_subtract_paused_time(tmp_path, trainer):
    from _nus_phase5_method_fixture import GPU_HOURS_AFTER_PAUSES, GPU_PAUSES, GPU_ROWS
    log, pauses = tmp_path / "runs" / "gpu_hours.log", tmp_path / "runs" / "pauses.log"
    for group, device, start, end in GPU_ROWS:
        trainer.append_log(log, {"group": group, "device": device, "start": start, "end": end})
    for event, t in GPU_PAUSES:
        trainer.append_log(pauses, {"event": event, "time": t})
    assert trainer.logged_hours(log, "s51", pauses) == pytest.approx(GPU_HOURS_AFTER_PAUSES)
    pause_start, pause_end = GPU_PAUSES[0][1], GPU_PAUSES[1][1]
    start = pause_start - HOUR / 2
    # one hour of budget: without the pause it would be reached at start + 1 h; with it, the paused time later
    assert trainer.cap_reached(start, 1.0, pauses, now=start + HOUR) is False
    assert trainer.cap_reached(start, 1.0, pauses, now=start + HOUR + (pause_end - pause_start) / 2) is False
    assert trainer.cap_reached(start, 1.0, pauses, now=start + HOUR + (pause_end - pause_start)) is True


def test_memory_fraction_is_cuda_only(tmp_path, trainer):
    """Separate side-by-side processes cap their share of GPU memory (plan section 10); on the CPU the option is refused."""
    out = tmp_path / "runs" / "phase5" / "s51" / "frac"
    with pytest.raises(SystemExit, match="memory-fraction"):
        trainer.main(_args(tmp_path, "--variant", "nus", "--out", str(out), "--memory-fraction", "0.3"))
