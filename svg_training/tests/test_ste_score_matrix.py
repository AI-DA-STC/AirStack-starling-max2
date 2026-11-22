"""STE L1 side track: the scoring tool scripts/ste_score_matrix.py on the CPU with small fake players (a few games, a
short cap; no Isaac). The players are run folders made here: a gate file at a test size (CPU, N games, TICKS ticks; the
real reference files, whose script cells a CPU replay reproduces game for game, cut at TICKS), random networks and the
eval_final.npz they play. Also: the committed settings files pin the real files."""
from __future__ import annotations

import json
import re
import sys
import tomllib
from pathlib import Path

import numpy as np
import pytest
import torch

from svg_training.core.rewards import GUARD_WIN, STRIKE_WIN
from svg_training.ste import exploit, exploit_train, scoring, shared

ROOT = exploit.ROOT
sys.path.insert(0, str(ROOT / "scripts"))
import ste_score_matrix as tool  # noqa: E402

N, TICKS = 2, 160
L1 = ROOT / "configs" / "ste_l1"


@pytest.fixture(autouse=True)
def scratch_shared(tmp_path, monkeypatch):
    monkeypatch.setenv(shared.SHARED_ENV, str(tmp_path / "shared"))
    monkeypatch.setenv(shared.LEGACY_LOGS_ENV, "")


def _small(text: str) -> str:
    for key, value in {"device": '"cpu"', "eval_games": str(N), "ticks_cap": str(TICKS)}.items():
        text, k = re.subn(rf"(?m)^{key} = .*$", f"{key} = {value}", text, count=1)
        assert k == 1, key
    return text


def _modules(hidden, seed: int) -> dict:
    """agent_final.pt's layout (Learner.modules): per drone the policy and its observation scaler."""
    from skrl.resources.preprocessors.torch import RunningStandardScaler

    from svg_training.opponents.learned import OBS_SPACE, StandinPolicy
    torch.manual_seed(seed)
    return {f"exploiter_{k}": {"policy": StandinPolicy(hidden, "cpu").state_dict(),
                               "observation_preprocessor": RunningStandardScaler(OBS_SPACE, device="cpu").state_dict()}
            for k in range(3)}


def make_player(folder: Path, gates_src: Path, variant: str, side: str, seed: int) -> dict:
    """A run folder as the L0.12 driver leaves it (gates.toml, agent_final.pt, eval_final.npz); returns the [player]
    table that pins it."""
    folder.mkdir(parents=True)
    (folder / "gates.toml").write_text(_small(gates_src.read_text()))
    gates = exploit.load_gates(folder / "gates.toml")
    hidden = list(gates.trainer["hidden"])
    mods = _modules(hidden, seed)
    torch.save(mods, folder / "agent_final.pt")
    team = exploit_train.team_from_modules(side, mods, hidden, "cpu")
    ref = exploit.load_reference(ROOT / gates.reference["file"])
    pg = exploit.play_cells(exploit.variant_cfg(gates, variant), "3v3", ref, exploit.eval_cells(gates, variant, side), N,
                            "cpu", int(ref.meta["seed"]), TICKS, learner=team, hold_ticks=int(gates.trainer["decision_ticks"]))
    np.savez(folder / "eval_final.npz", **{k: v for k, v in pg.items() if isinstance(v, np.ndarray)})
    won = GUARD_WIN if side == "guard" else STRIKE_WIN
    return {"label": f"test {side} player", "dir": str(folder), "side": side, "variant": variant,
            "gates_sha256": exploit.sha256_file(folder / "gates.toml"),
            "agent_sha256": exploit.sha256_file(folder / "agent_final.pt"),
            "eval_sha256": exploit.sha256_file(folder / "eval_final.npz"),
            "own_wins": int(np.sum(pg["outcome"][:N] == won)), "own_source": "made by the test"}


def _value(v) -> str:
    return json.dumps(v) if isinstance(v, str) else repr(v)


def write_settings(path: Path, job: dict, player: dict, games: list[dict]) -> Path:
    lines = ["[job]", *[f"{k} = {_value(v)}" for k, v in job.items()], "", "[player]",
             *[f"{k} = {_value(v)}" for k, v in player.items()]]
    for g in games:
        lines += ["", "[[games]]", *[f"{k} = {_value(v)}" for k, v in g.items()]]
    path.write_text("\n".join(lines) + "\n")
    return path


def real_games(name: str) -> list[dict]:
    return tomllib.loads((L1 / name).read_text())["games"]


JOB = {"task": "L1.12", "what": "test scoring", "kind": "INFO"}


@pytest.fixture(scope="module")
def guard_case(tmp_path_factory):
    """A Guard player trained (randomly) on base, scored at base (the L1.12 shape), and its finished run."""
    tmp = tmp_path_factory.mktemp("score_guard")
    mp = pytest.MonkeyPatch()
    mp.setenv(shared.SHARED_ENV, str(tmp / "shared"))
    mp.setenv(shared.LEGACY_LOGS_ENV, "")
    player = make_player(tmp / "player", ROOT / "configs" / "ste_l012" / "gates.toml", "base", "guard", 3)
    settings = write_settings(tmp / "s.toml", JOB, player, real_games("score_matrix_l112.toml"))
    rd = tmp / "run"
    code = tool.main(["--settings", str(settings), "--run-dir", str(rd), "--cap-h", "1"])
    mp.undo()
    return code, rd, settings, player


def test_a_guard_player_is_scored_against_every_strike_script(guard_case):
    code, rd, _, player = guard_case
    assert code == 0
    controls = json.loads((rd / "controls.json").read_text())
    strikes = exploit.load_gates(Path(player["dir"]) / "gates.toml").players["strikes"]
    assert set(controls) == {"own_replay", *[f"scripts_base_120s__{x}" for x in strikes]}
    assert {v["status"] for v in controls.values()} == {"PASS"}
    assert controls["own_replay"]["trained"]["k"] == player["own_wins"]
    res = json.loads((rd / "results.json").read_text())
    assert res["complete"] is True and res["controls_pass"] is True
    rows = res["games"]["base_120s"]["rows"]
    assert sorted(r["opponent"] for r in rows) == sorted(strikes)
    assert [r["k"] for r in rows] == sorted(r["k"] for r in rows)                    # worst cell first
    for r in rows:
        assert r["n"] + r["unfinished"] == N and len(r["ci"]) == 2
        assert sum(r["end_reasons"].values()) == N
        assert r["best_script"]["cell"][1] == r["opponent"] and r["best_script"]["name"].startswith("guard_")
        assert r["cell"] == [tool.PLAYER, r["opponent"]]
    for x in strikes:
        assert (rd / "games" / f"base_120s__{x}.npz").is_file()
    assert (rd / "games" / "own_replay.npz").is_file()
    md = (rd / "results.md").read_text()
    assert md.startswith("Simulator: training simulator, tier 1") and "worst cell first" in md
    assert res["games"]["base_120s"]["readings"][0].startswith("test guard player holds ")


def test_the_best_script_and_paired_counts_come_from_the_same_batch(guard_case):
    _, rd, _, player = guard_case
    res = json.loads((rd / "results.json").read_text())
    for r in res["games"]["base_120s"]["rows"]:
        pg = scoring.load_batch(rd / "games" / f"base_120s__{r['opponent']}.npz")
        cells = tool.matrix_cells(exploit.load_gates(Path(player["dir"]) / "gates.toml"), "guard", r["opponent"])
        holds = [scoring.win_count(exploit.slice_cell(pg, i, N), "guard")[0] for i in range(1, len(cells))]
        assert r["best_script"]["k"] == max(holds)
        assert r["k"] == scoring.win_count(exploit.slice_cell(pg, 0, N), "guard")[0]


def test_the_same_command_on_a_finished_run_does_nothing_new(guard_case, tmp_path, monkeypatch):
    _, rd, settings, _ = guard_case
    before = (rd / "results.json").read_text()
    assert tool.main(["--settings", str(settings), "--run-dir", str(rd), "--cap-h", "1"]) == 0
    assert (rd / "results.json").read_text() == before


def test_a_failed_control_is_terminal_and_reports_no_number(guard_case, tmp_path):
    _, _, _, player = guard_case
    settings = write_settings(tmp_path / "s.toml", JOB, {**player, "own_wins": player["own_wins"] + 1},
                              real_games("score_matrix_l112.toml"))
    rd = tmp_path / "run"
    assert tool.main(["--settings", str(settings), "--run-dir", str(rd), "--cap-h", "1"]) == 6
    assert json.loads((rd / "controls.json").read_text())["own_replay"]["status"] == "FAIL"
    assert not (rd / "results.json").exists() and (rd / "games" / "own_replay.npz").is_file()
    assert tool.main(["--settings", str(settings), "--run-dir", str(rd), "--cap-h", "1"]) == 6


def test_a_script_cell_off_the_reference_fails_its_control(guard_case, tmp_path, monkeypatch):
    _, _, settings, _ = guard_case
    real = exploit.replay_ok
    monkeypatch.setattr(exploit, "replay_ok", lambda *a, **k: (False, "forced by the test") if a[2] == "cpu" and
                        k.get("ticks_cap") else real(*a, **k))
    rd = tmp_path / "run"
    assert tool.main(["--settings", str(settings), "--run-dir", str(rd), "--cap-h", "1"]) == 6
    controls = json.loads((rd / "controls.json").read_text())
    assert controls["own_replay"]["status"] == "PASS"
    assert [k for k, v in controls.items() if v["status"] == "FAIL"][0].startswith("scripts_base_120s__")
    assert not (rd / "results.json").exists()


def test_refusals_exit_2(guard_case, tmp_path):
    _, rd, settings, player = guard_case
    bad = write_settings(tmp_path / "bad.toml", JOB, {**player, "eval_sha256": "0" * 64},
                         real_games("score_matrix_l112.toml"))
    assert tool.main(["--settings", str(bad), "--run-dir", str(tmp_path / "a"), "--cap-h", "1"]) == 2
    fill = write_settings(tmp_path / "fill.toml", JOB, {**player, "dir": "FILL_FROM_THE_RUN"},
                          real_games("score_matrix_l112.toml"))
    assert tool.main(["--settings", str(fill), "--run-dir", str(tmp_path / "b"), "--cap-h", "1"]) == 2
    wrong_game = [{**real_games("score_matrix_l112.toml")[0], "sha256": "1" * 64}]
    g = write_settings(tmp_path / "g.toml", JOB, player, wrong_game)
    assert tool.main(["--settings", str(g), "--run-dir", str(tmp_path / "c"), "--cap-h", "1"]) == 2
    other = write_settings(tmp_path / "other.toml", {**JOB, "what": "changed"}, player, real_games("score_matrix_l112.toml"))
    assert tool.main(["--settings", str(other), "--run-dir", str(rd), "--cap-h", "1"]) == 2   # pinned settings
    (tmp_path / "d").mkdir()
    (tmp_path / "d" / "job.json").write_text(json.dumps({"gpu_h": 2.0}))
    assert tool.main(["--settings", str(settings), "--run-dir", str(tmp_path / "d"), "--cap-h", "1"]) == 2


def test_an_l113_arm_is_scored_at_both_clocks(tmp_path):
    """An arm A player (trained on the 30 s game, its own replay at 30 s) scored at 120 s and 30 s against every Guard
    script on the screen reference: the clock30 replay of every script cell equals the 120 s screen."""
    player = make_player(tmp_path / "arm_a", L1 / "l113_gates.toml", "arm_a_clock30", "strike", 4)
    gates = exploit.load_gates(Path(player["dir"]) / "gates.toml")
    assert exploit.eval_cells(gates, "arm_a_clock30", "strike")[0] == ("guard_field", exploit.EXPLOITER)
    settings = write_settings(tmp_path / "s.toml", {**JOB, "task": "L1.13"}, player,
                              real_games("score_matrix_t52.toml"))
    rd = tmp_path / "run"
    assert tool.main(["--settings", str(settings), "--run-dir", str(rd), "--cap-h", "1"]) == 0
    res = json.loads((rd / "results.json").read_text())
    assert set(res["games"]) == {"tag_1p15_120s", "tag_1p15_30s"}
    assert res["games"]["tag_1p15_30s"]["game_ticks"] == 600 and res["games"]["tag_1p15_120s"]["game_ticks"] == 2400
    for g in res["games"].values():
        assert sorted(r["opponent"] for r in g["rows"]) == sorted(gates.players["guards"])
        assert all(r["best_script"]["name"].startswith("strike_") for r in g["rows"])
    assert res["player"]["opponent"] == "guard_field"


# ================================================================================================ the committed settings
@pytest.mark.parametrize("name", ["score_matrix_l112.toml", "score_matrix_t52.toml"])
def test_the_filled_settings_pin_the_real_files(name):
    s = tool.load_settings(L1 / name)
    p = s["player"]
    d = tool._path(p["dir"])
    for f, key in (("gates.toml", "gates_sha256"), ("agent_final.pt", "agent_sha256"), ("eval_final.npz", "eval_sha256")):
        assert scoring.sha_problem(d / f, p[key], f) is None, f
    gates = exploit.load_gates(d / "gates.toml")
    assert p["variant"] in gates.variants
    res = json.loads((d / "results.json").read_text())
    assert res["exploiter"]["k"] == p["own_wins"] and res["side"] == p["side"]           # 913 (T46), 103 (T52)
    cells = exploit.eval_cells(gates, p["variant"], p["side"])                         # the batch own_replay plays
    n = int(gates.run["eval_games"])
    with np.load(d / "eval_final.npz") as z:
        assert set(tool.r3.EXACT_KEYS) <= set(z.files)
        assert len(z["outcome"]) == len(cells) * n == len(cells) * 1000
        won = GUARD_WIN if p["side"] == "guard" else STRIKE_WIN
        assert int(np.sum(z["outcome"][:n] == won)) == p["own_wins"]
    for g in s["games"]:
        assert scoring.sha_problem(tool._path(g["file"]), g["sha256"], "game") is None
        assert scoring.sha_problem(tool._path(g["reference"]), g["reference_sha256"], "reference") is None
        ref = exploit.load_reference(tool._path(g["reference"]))
        assert ref.start_sha256 == gates.reference["start_sha256"]


def test_the_l112_and_t52_numbers_are_the_spec_controls():
    assert tool.load_settings(L1 / "score_matrix_l112.toml")["player"]["own_wins"] == 913
    t52 = tool.load_settings(L1 / "score_matrix_t52.toml")
    assert t52["player"]["own_wins"] == 103 and [g["name"] for g in t52["games"]] == ["tag_1p15_120s", "tag_1p15_30s"]


@pytest.mark.parametrize("name", ["score_matrix_l111.toml", "score_matrix_l113_arm_a.toml", "score_matrix_l113_arm_b.toml"])
def test_the_unfilled_settings_are_refused_until_filled(name):
    with pytest.raises(ValueError, match="not filled yet"):
        tool.load_settings(L1 / name)
    raw = tomllib.loads((L1 / name).read_text())
    assert raw["job"]["task"] in ("L1.11", "L1.13")


def test_the_own_opponent_cell_must_equal_own_replay_game_for_game(guard_case, tmp_path, monkeypatch):
    """Fix round 1: on the player's own game, the matrix cell against its own training opponent is the same games as
    own_replay's trained cell: checked game for game (control scripts_<game>_<x>, key own_cell); a mismatch fails."""
    _, rd, settings, player = guard_case
    controls = json.loads((rd / "controls.json").read_text())
    gates = exploit.load_gates(Path(player["dir"]) / "gates.toml")
    opp = exploit.opponent_of(gates, "base", "guard")
    own = controls[f"scripts_base_120s__{opp}"]
    assert own["own_cell"]["equal"] is True and own["status"] == "PASS"
    assert all("own_cell" not in v for k, v in controls.items() if k.startswith("scripts_") and not k.endswith(opp))
    real = tool.play_matrix_batch
    def shifted(*a, **k):                       # the matrix cell of the own opponent differs in one game's end step
        pg = real(*a, **k)
        if k.get("x") == opp:
            pg["end_step"] = pg["end_step"].copy()
            pg["end_step"][0] += 1
        return pg
    monkeypatch.setattr(tool, "play_matrix_batch", shifted)
    rd2 = tmp_path / "run"
    assert tool.main(["--settings", str(settings), "--run-dir", str(rd2), "--cap-h", "1"]) == 6
    c2 = json.loads((rd2 / "controls.json").read_text())
    assert c2[f"scripts_base_120s__{opp}"]["status"] == "FAIL" and not (rd2 / "results.json").exists()
