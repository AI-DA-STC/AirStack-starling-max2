"""scripts/nus_phase5_probe.py (Phase 5 pilot P0, plan section 7, Task P-T1) without a GPU: the settings, the pilots' game-count rule, a CPU
probe on tiny counts with the marker local files (both arms, probe.json, the profile tick), the out-of-memory stop, the budget stop, the
refusal to overwrite, and the profiler counts (one ``aten::einsum`` per filter sweep). Marker values only; no numeric literal (G2)."""
from __future__ import annotations

import importlib.util
import json
import shutil
import tomllib

import pytest
import torch

import _nus_markers  # noqa: F401  (puts source/ and scripts/ on the path)
from _nus_markers import ROOT
from _nus_phase4_fixture import PROBE_COUNTS, PROBE_SWEEPS, PROBE_TIMED, PROBE_WARMUP, build
from svg_training.core.safety_filter import filter_velocities, team_pair_mask
from svg_training.nus import hangar as hangar_mod, ladder

spec = importlib.util.spec_from_file_location("nus_phase5_probe", ROOT / "scripts" / "nus_phase5_probe.py")
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)

WORK = ladder.RUNS_DIR / "nus_port" / "_test_phase5_probe"


@pytest.fixture
def world(tmp_path, monkeypatch):
    w = build(tmp_path, monkeypatch)
    monkeypatch.setattr(hangar_mod, "LOCAL_HANGAR", w.folder / "nus_hangar.toml")
    shutil.rmtree(WORK, ignore_errors=True)
    yield w
    shutil.rmtree(WORK, ignore_errors=True)


def _args(*extra: str, counts=PROBE_COUNTS) -> list[str]:
    return ["--games", ",".join(str(c) for c in counts), "--out", str(WORK), "--device", "cpu", "--warmup-ticks", str(PROBE_WARMUP),
            "--timed-ticks", str(PROBE_TIMED), *extra]


def _read() -> dict:
    return json.loads((WORK / "probe.json").read_text())


# ------------------------------------------------------------------------------------------------ settings
def test_probe_settings_match_the_plan_and_stay_under_the_cap():
    st = probe.load_probe()
    raw = tomllib.loads(probe.PHASE5_CONFIG.read_text())["probe"]
    assert st == raw
    assert st["games"] == sorted(st["games"]) and st["pilot_max_games"] in st["games"]
    assert {st["side_by_side_games"], st["side_by_side_ref_games"]} <= set(st["games"]) and st["side_by_side_ratio"] > 1
    assert st["games"][0] == st["profile_games"]
    assert st["warmup_ticks"] == hangar_mod.load_phase4()["ladder"]["warmup_ticks"]
    assert st["timed_ticks"] > st["warmup_ticks"]
    assert st["arms"][0] == "parked_s20" and set(st["arms"]) == set(probe.ARMS)
    assert st["pilot_ratio"] > 1 and st["budget_hours"] < st["gpu_cap_hours"]
    rows = {r["id"]: r for r in hangar_mod.load_phase4()["row"]}
    row = rows[st["row"]]
    assert row["separation"] == "filter" and row["height"] == "free_jitter" and row["drone"] == "fitted"


# ------------------------------------------------------------------------------------------------ the pilots' game-count rule
def _entry(games, spt, status="ok"):
    return {"games": games, "status": status, "seconds_per_tick": spt if status == "ok" else None}


def test_pilot_rule_takes_the_largest_count_within_the_ratio():
    st = probe.load_probe()
    g, r = st["games"], st["pilot_ratio"]
    base = 1.0
    entries = [_entry(g[0], base), _entry(g[1], base * r), _entry(g[2], base * r * 2), _entry(g[-1], base)]
    entries.append(_entry(g[-1] * 2, base))                                     # above the maximum: never chosen
    out = probe.pilot_rule(entries, r, g[-1])
    assert out["games"] == g[-1] and out["base_games"] == g[0] and out["base_seconds_per_tick"] == base   # the largest qualifying count
    entries = entries[:-1]
    entries[-1] = _entry(g[-1], None, "oom")
    assert probe.pilot_rule(entries, r, st["pilot_max_games"])["games"] == g[1]                          # equal to the limit qualifies
    assert probe.pilot_rule(entries, r, g[0])["games"] == g[0]                                            # the maximum caps it
    assert probe.pilot_rule([_entry(g[0], None, "oom")], r, st["pilot_max_games"])["games"] is None       # no base: no count
    assert probe.pilot_rule([], r, st["pilot_max_games"])["games"] is None


def test_pilot_count_is_the_pilot_arms_and_the_random_arm_is_info():
    st = probe.load_probe()
    g, arm = st["games"], st["pilot_arm"]
    assert arm == "parked_s20"
    assert probe.pilot_choice({"parked_s20": {"games": g[-2]}, "random": {"games": g[0]}}, arm) == g[-2]   # random's smaller count is ignored
    assert probe.pilot_choice({"parked_s20": {"games": None}, "random": {"games": g[1]}}, arm) is None
    assert probe.pilot_choice({"random": {"games": g[1]}}, arm) is None


# ------------------------------------------------------------------------------------------------ the CPU probe
def test_cpu_probe_writes_probe_json_for_both_arms_and_refuses_a_rerun(world):
    w = world
    assert probe.main(_args("--profile-games", str(PROBE_COUNTS[0]))) == 0
    data = _read()
    assert (WORK / "gates.toml").read_text().startswith("#") and "gates = []" in (WORK / "gates.toml").read_text()
    m = w.guards + w.strikes
    for arm in probe.ARMS:
        entries = data["arms"][arm]
        assert [e["games"] for e in entries] == list(PROBE_COUNTS)
        for e in entries:
            assert e["status"] == "ok" and e["ticks_timed"] == PROBE_TIMED and e["warmup_ticks"] == PROBE_WARMUP
            assert e["seconds_per_tick"] > 0 and e["seconds_per_tick"] == pytest.approx(e["seconds_timed"] / PROBE_TIMED)
            assert e["game_steps_per_s"] == pytest.approx(e["games"] * PROBE_TIMED / e["seconds_timed"])
            assert e["drone_steps_per_s"] == pytest.approx(e["game_steps_per_s"] * m)
            assert 0 <= e["filter_share"] <= 1 and e["filter_calls"] == PROBE_TIMED
            assert e["peak_gpu_bytes"] is None                                       # CPU: no GPU memory
        assert data["pilot"]["per_arm"][arm]["games"] in PROBE_COUNTS
    assert data["pilot"]["games"] == data["pilot"]["per_arm"]["parked_s20"]["games"] and data["pilot"]["arm"] == "parked_s20"
    assert "random arm is INFO" in data["pilot"]["decision"]
    meta = data["meta"]
    assert meta["drones_per_game"] == m and meta["device"] == "cpu" and meta["row"] == probe.load_probe()["row"]
    assert "synchronize" in meta["filter_timing_method"] and set(meta["sha256"]) >= {"rules", "deploy_ref", "hangar", "settings", "phase4"}
    prof = data["profile"]
    assert prof["games"] == PROBE_COUNTS[0] and prof["filter_calls"] == 1
    assert prof["sweeps"] >= 0 and prof["early_stop_checks"] >= 1 and prof["kernel_launches_tick"] == 0   # CPU: no CUDA launches
    assert prof["sweeps"] <= prof["filter_iterations"]
    assert probe.main(_args()) == probe.EXIT_REFUSED                                  # a finished probe is never overwritten


def test_out_of_memory_stops_the_arm_at_the_first_count_that_fails(world, monkeypatch):
    original = probe._measure
    failing = PROBE_COUNTS[1]

    def measure(ctx, n, *args, **kw):
        if n == failing:
            raise torch.cuda.OutOfMemoryError("CUDA out of memory (injected by the test)")
        return original(ctx, n, *args, **kw)
    monkeypatch.setattr(probe, "_measure", measure)
    assert probe.main(_args("--profile-games", "0")) == 0
    data = _read()
    for arm in probe.ARMS:
        entries = data["arms"][arm]
        assert [e["games"] for e in entries] == list(PROBE_COUNTS[:2])                # stopped: the last count is never tried
        assert entries[0]["status"] == "ok" and entries[1]["status"] == "oom" and "out of memory" in entries[1]["error"]
        assert data["pilot"]["per_arm"][arm]["games"] == PROBE_COUNTS[0]
    assert data["profile"] is None


def test_budget_stop_records_the_skip_and_sets_no_pilot_count(world):
    assert probe.main(_args("--budget-hours", "0", "--profile-games", "0")) == probe.EXIT_STOP
    data = _read()
    first = data["arms"]["parked_s20"]
    assert first and all(e["status"] == "budget" for e in first)
    assert data["pilot"]["games"] is None


def test_side_by_side_rule_compares_the_two_counts():
    st = probe.load_probe()
    ref, big, r = st["side_by_side_ref_games"], st["side_by_side_games"], st["side_by_side_ratio"]
    base = 1.0
    ok = probe.side_by_side_rule([_entry(ref, base), _entry(big, base * r)], ref, big, r)
    assert ok["passes"] is True and ok["seconds_per_tick_ratio"] == pytest.approx(r)
    assert probe.side_by_side_rule([_entry(ref, base), _entry(big, base * r * 2)], ref, big, r)["passes"] is False
    assert probe.side_by_side_rule([_entry(ref, base), _entry(big, None, "oom")], ref, big, r)["passes"] is None


def test_extend_adds_a_larger_count_keeps_the_earlier_entries_and_refuses_a_smaller_one(world):
    first = PROBE_COUNTS[:2]
    assert probe.main(_args("--profile-games", "0", counts=first)) == 0
    before = _read()
    assert probe.main(_args("--extend", counts=PROBE_COUNTS[2:])) == 0
    after = _read()
    for arm in probe.ARMS:
        assert after["arms"][arm][:len(first)] == before["arms"][arm]
        assert [e["games"] for e in after["arms"][arm]] == list(PROBE_COUNTS)
    assert len(after["meta"]["extensions"]) == 1 and set(after["side_by_side"]) == set(probe.ARMS)
    assert after["meta"]["wall_seconds"] >= before["meta"]["wall_seconds"]
    assert probe.main(_args("--extend", counts=PROBE_COUNTS[2:])) == probe.EXIT_REFUSED       # not larger than what is there
    shutil.rmtree(WORK)
    assert probe.main(_args("--extend", counts=PROBE_COUNTS[2:])) == probe.EXIT_REFUSED       # nothing to extend


def test_out_folder_must_be_under_runs(world, tmp_path):
    with pytest.raises(ValueError):
        probe.main(["--out", str(tmp_path / "elsewhere"), "--device", "cpu"])


# ------------------------------------------------------------------------------------------------ profiler counts
def test_profiler_counts_one_einsum_per_sweep_and_one_nonzero_per_check():
    m = len(PROBE_COUNTS) * 2
    guards = m // 2
    gen = torch.Generator().manual_seed(0)
    pos = torch.rand(PROBE_COUNTS[0], m, len(PROBE_COUNTS), generator=gen) * PROBE_WARMUP   # crowded: every pair active
    nominal = torch.rand(pos.shape, generator=gen) * 2 - 1
    mask = team_pair_mask(guards, m - guards)
    cap = torch.tensor(float(PROBE_TIMED))
    with torch.profiler.profile(activities=[torch.profiler.ProfilerActivity.CPU]) as prof:
        with torch.profiler.record_function(probe.FILTER_SCOPE):
            filter_velocities(nominal, pos, mask, float(PROBE_WARMUP), cap, iterations=PROBE_SWEEPS, tolerance=0.0)
    counts = probe.profile_counts(prof.events())
    assert counts["filter_calls"] == 1 and counts["sweeps"] == PROBE_SWEEPS and counts["early_stop_checks"] == 0
    with torch.profiler.profile(activities=[torch.profiler.ProfilerActivity.CPU]) as prof:
        with torch.profiler.record_function(probe.FILTER_SCOPE):
            filter_velocities(nominal, pos, mask, float(PROBE_WARMUP), cap, iterations=PROBE_SWEEPS, tolerance=0.0, check_every=2)
    counts = probe.profile_counts(prof.events())
    assert counts["sweeps"] == PROBE_SWEEPS and counts["early_stop_checks"] == -(-PROBE_SWEEPS // 2)
