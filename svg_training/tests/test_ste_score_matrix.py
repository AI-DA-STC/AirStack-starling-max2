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
    if isinstance(v, dict):                                         # a TOML inline table ([player] time_left)
        return "{ " + ", ".join(f"{k} = {_value(x)}" for k, x in v.items()) + " }"
    if isinstance(v, list):
        return "[" + ", ".join(_value(x) for x in v) + "]"
    if isinstance(v, bool):                                         # TOML booleans ([[games]] reference = false)
        return "true" if v else "false"
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
@pytest.mark.parametrize("name", ["score_matrix_l112.toml", "score_matrix_t52.toml", "score_matrix_l114_t52_offset.toml",
                                  "score_matrix_l114_t52_clamp.toml"])
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
def test_the_unfilled_settings_are_refused_until_filled(name, tmp_path):
    """These three files were filled from their finished runs on 22 Nov 2026 (commit aa8cdeb7); a copy with the
    player's run-derived values put back to FILL_FROM_THE_RUN must still be refused."""
    import re
    text = (L1 / name).read_text()
    raw = tomllib.loads(text)
    assert raw["job"]["task"] in ("L1.11", "L1.13")
    tool.load_settings(L1 / name)                                   # the filled file loads
    for key in ("dir", "gates_sha256", "agent_sha256", "eval_sha256"):
        text = re.sub(rf'^{key} = "[^"]*"', f'{key} = "FILL_FROM_THE_RUN"', text, count=1, flags=re.M)
    text = re.sub(r"^own_wins = \d+", 'own_wins = "FILL_FROM_THE_RUN"', text, count=1, flags=re.M)
    unfilled = tmp_path / name
    unfilled.write_text(text)
    with pytest.raises(ValueError, match="not filled yet"):
        tool.load_settings(unfilled)


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


# ================================================================================================ L1.14: the time-left test
# Spec ste_learning/drafts/L1_SIDE_TRACK_SPEC.md, addendum 2: a per-player override of the time-left input
# (ObsView.time_left) of in-game drones, before the network; own_replay plays without it; control c_offset.
from svg_training.core.game import TICK_S  # noqa: E402
from svg_training.core.observations import OBS_DIM, ObsView  # noqa: E402
from svg_training.core.rewards import RUNNING  # noqa: E402

T52_GATES = ROOT / "ste_provisional" / "players" / "2026-11-21_ste_l012b_tag_1p15_strike" / "gates.toml"
TL = ObsView.time_left


class _Spy:
    """A team that records the observation it is given and answers zeros."""
    team, name = "strike", "spy"

    def __init__(self):
        self.seen = []

    def reset(self, games):
        pass

    def act(self, obs):
        self.seen.append(obs.clone())
        return torch.zeros(*obs.shape[:2], 4)


def _obs(time_left_s: torch.Tensor, alive: torch.Tensor) -> torch.Tensor:
    """[N, K, OBS_DIM] observations as build_obs leaves them: random fields, time left, alive; a drone that is out all
    zeros but team."""
    gen = torch.Generator().manual_seed(7)
    obs = torch.rand(*alive.shape, OBS_DIM, generator=gen)
    obs[..., TL] = time_left_s[:, None]
    obs[..., ObsView.alive] = alive.float()
    obs[..., ObsView.team] = 1.0
    out = torch.where(alive[..., None], obs, torch.zeros_like(obs))
    out[..., ObsView.team] = 1.0
    return out


def test_the_offset_is_the_time_left_a_longer_game_shows_bit_for_bit():
    """offset_s = 90 on the 30 s game (600 ticks) gives, at every step 0..600, exactly the float the 120 s game (2,400
    ticks) computes (core/game._time_left_s); a plain float add would differ in the last bit at about 1 step in 5."""
    steps = torch.arange(0, 601)
    short = (600 - steps).to(torch.float32) * TICK_S
    long_ = (2400 - steps).to(torch.float32) * TICK_S
    assert bool((short + 90.0 != long_).any())                      # why the override goes through whole ticks
    spy = _Spy()
    team = scoring.TimeLeftOverride(spy, scoring.parse_time_left({"offset_s": 90.0}))
    alive = torch.ones(len(steps), 3, dtype=torch.bool)
    team.act(_obs(short, alive))
    got = spy.seen[0]
    assert torch.equal(got[..., TL], long_[:, None].expand(-1, 3))
    rest = torch.ones(OBS_DIM, dtype=torch.bool)
    rest[TL] = False
    assert torch.equal(got[..., rest], _obs(short, alive)[..., rest])          # every other input untouched
    assert team.team == "strike" and team.name == "spy"


def test_the_clamp_caps_the_time_left_and_out_of_game_drones_keep_zeros():
    spy = _Spy()
    team = scoring.TimeLeftOverride(spy, scoring.parse_time_left({"clamp_max_s": 30.0}))
    tl = torch.tensor([120.0, 45.5, 30.0, 12.25])
    alive = torch.tensor([[True, False, True], [True, True, False], [False, True, True], [True, True, True]])
    obs = _obs(tl, alive)
    team.act(obs)
    got = spy.seen[0]
    want = torch.where(alive, torch.clamp(tl, max=30.0)[:, None], torch.zeros(()))
    assert torch.equal(got[..., TL], want)
    assert torch.equal(got[~alive], obs[~alive])                    # out of game: zeros (team kept), unchanged
    assert torch.equal(obs[..., TL], torch.where(alive, tl[:, None], torch.zeros(())))   # the input is not modified
    off = scoring.TimeLeftOverride(_Spy(), scoring.parse_time_left({"offset_s": 90.0}))
    off.act(obs)
    assert torch.equal(off.inner.seen[0][~alive], obs[~alive])     # out-of-game rows do not become 90


@pytest.mark.parametrize("bad,match", [
    ({}, "exactly one"), ({"offset_s": 90.0, "clamp_max_s": 30.0}, "exactly one"), ({"shift_s": 1.0}, "exactly one"),
    ({"offset_s": -0.05}, "offset_s"), ({"clamp_max_s": 0.0}, "clamp_max_s"), ({"clamp_max_s": -1.0}, "clamp_max_s"),
    ({"offset_s": float("nan")}, "finite"), ({"clamp_max_s": float("inf")}, "finite"), ({"offset_s": True}, "number"),
    ({"offset_s": "90"}, "number"), ({"offset_s": 0.01}, "whole number of ticks"), (90.0, "table")])
def test_a_bad_time_left_override_is_refused(bad, match):
    with pytest.raises(ValueError, match=match):
        scoring.parse_time_left(bad)


def test_parse_time_left_keeps_the_value_and_says_it_in_words():
    off = scoring.parse_time_left({"offset_s": 90})
    assert off == {"offset_s": 90.0, "offset_ticks": 1800}
    assert scoring.time_left_text(off) == "time-left input + 90 s"
    cl = scoring.parse_time_left({"clamp_max_s": 30.0})
    assert cl == {"clamp_max_s": 30.0} and scoring.time_left_text(cl) == "time-left input clamped to at most 30 s"


def _cell(outcome, end_step):
    return {"outcome": np.array(outcome, dtype=np.int8), "end_step": np.array(end_step, dtype=np.int64)}


S, G = STRIKE_WIN, GUARD_WIN
OWN_120 = _cell([S, S, G, S, G, S], [300, 600, 450, 900, 2400, 601])      # reaches by tick 600: games 0 and 1


@pytest.mark.parametrize("offset_games,ok,what", [
    (_cell([S, S, G, G, G, G], [300, 600, 450, 600, 600, 600]), True, "the same"),
    (_cell([S, S, G, G, G, G], [301, 600, 450, 600, 600, 600]), False, "a reach at another tick"),
    (_cell([S, G, G, G, G, G], [300, 600, 450, 600, 600, 600]), False, "a missing reach"),
    (_cell([S, S, S, G, G, G], [300, 600, 450, 600, 600, 600]), False, "an extra reach"),
    (_cell([S, S, G, G, G, S], [300, 600, 450, 600, 600, 600]), False, "a reach at tick 600 the long game made at 601"),
    (_cell([S, S, G, G, RUNNING, G], [300, 600, 450, 600, 0, 600]), False, "an unfinished game"),
])
def test_the_c_offset_rule(offset_games, ok, what):
    """Every game the player's own 120 s evaluation reached by the scoring game's last tick reaches in the offset games
    at the same tick, and no other game reaches; every offset game finished."""
    ctl = scoring.check_offset_prefix(offset_games, OWN_120, 600, 2400)
    assert (ctl["status"] == scoring.PASS) is ok, what
    assert ctl["reaches_expected"] == 2 and ctl["game_ticks"] == 600
    if ok:
        assert ctl["reaches"] == 2 and ctl["same_tick"] == 2 and ctl["extra"] == ctl["missing"] == ctl["shifted"] == 0
        assert "2 reaches by tick 600" in ctl["detail"]


def test_c_offset_under_a_play_cap_below_the_game_length():
    """A test-size play cap (below the 30 s game's 600 ticks): compared up to the cap; unfinished games allowed only
    there."""
    own = _cell([S, S, RUNNING], [100, 300, 0])
    ok = scoring.check_offset_prefix(_cell([S, RUNNING, RUNNING], [100, 0, 0]), own, 600, 160)
    assert ok["status"] == scoring.PASS and ok["reaches_expected"] == 1 and "by tick 160" in ok["detail"]
    assert scoring.check_offset_prefix(_cell([S, S, RUNNING], [100, 150, 0]), own, 600, 160)["status"] == scoring.FAIL
    assert scoring.check_offset_prefix(_cell([S, RUNNING, RUNNING], [100, 0, 0]), own, 600, 600)["status"] == scoring.FAIL


def _t52_player(folder: Path, seed: int = 5) -> dict:
    return make_player(folder, T52_GATES, "tag_1p15", "strike", seed)


def _spy_inputs(monkeypatch) -> list:
    """Records, per network call, (matrix batch?, the time-left column of in-game drones, of out-of-game drones) as the
    trained team's networks receive it (exploit.LearnerTeam.act)."""
    seen, phase = [], {"matrix": False}
    real_act, real_batch = exploit.LearnerTeam.act, tool.play_matrix_batch

    def act(self, obs):
        alive = obs[..., ObsView.alive] != 0
        seen.append((phase["matrix"], obs[..., TL][alive].clone(), obs[..., TL][~alive].clone()))
        return real_act(self, obs)

    def batch(*a, **k):
        phase["matrix"] = True
        try:
            return real_batch(*a, **k)
        finally:
            phase["matrix"] = False
    monkeypatch.setattr(exploit.LearnerTeam, "act", act)
    monkeypatch.setattr(tool, "play_matrix_batch", batch)
    return seen


JOB14 = {"task": "L1.14", "what": "test time-left", "kind": "INFO", "opponents": ["guard_field"]}


def test_an_offset_player_passes_c_offset_and_own_replay_plays_without_the_override(tmp_path, monkeypatch):
    player = _t52_player(tmp_path / "t52")
    games = [g for g in real_games("score_matrix_t52.toml") if g["name"] == "tag_1p15_30s"]
    settings = write_settings(tmp_path / "s.toml", JOB14, {**player, "time_left": {"offset_s": 90.0}}, games)
    seen = _spy_inputs(monkeypatch)
    rd = tmp_path / "run"
    assert tool.main(["--settings", str(settings), "--run-dir", str(rd), "--cap-h", "1"]) == 0
    own = torch.cat([tl for m, tl, _ in seen if not m])
    matrix = torch.cat([tl for m, tl, _ in seen if m])
    assert float(own.max()) == 120.0 and float(own.min()) >= 120.0 - TICKS * TICK_S - 1e-3       # own_replay: raw
    assert float(matrix.max()) == 120.0 and float(matrix.min()) >= 90.0                         # 30 s game + 90 s
    assert all(o.numel() == 0 or float(o.abs().max()) == 0.0 for _, _, o in seen)             # out: zeros kept
    controls = json.loads((rd / "controls.json").read_text())
    assert set(controls) == {"own_replay", "scripts_tag_1p15_30s__guard_field", "c_offset_tag_1p15_30s"}
    assert {v["status"] for v in controls.values()} == {"PASS"}
    res = json.loads((rd / "results.json").read_text())
    assert res["player"]["time_left"] == {"offset_s": 90.0}
    assert res["player"]["time_left_override"] == "time-left input + 90 s"
    assert res["opponents"] == {"names": ["guard_field"], "choice": tool.SUBSET_CHOICE}
    assert [r["opponent"] for r in res["games"]["tag_1p15_30s"]["rows"]] == ["guard_field"]
    md = (rd / "results.md").read_text()
    assert "time-left input + 90 s" in md and "against guard_field only" in md
    assert "time-left input + 90 s" in res["games"]["tag_1p15_30s"]["readings"][0]


def test_c_offset_fails_closed_on_a_reach_the_long_games_did_not_make(tmp_path, monkeypatch):
    player = _t52_player(tmp_path / "t52")
    games = [g for g in real_games("score_matrix_t52.toml") if g["name"] == "tag_1p15_30s"]
    settings = write_settings(tmp_path / "s.toml", JOB14, {**player, "time_left": {"offset_s": 90.0}}, games)
    real = tool.play_matrix_batch

    def extra(*a, **k):                         # the trained cell's game 0 reaches at tick 5 (the record has no such)
        pg = real(*a, **k)
        pg["outcome"], pg["end_step"] = pg["outcome"].copy(), pg["end_step"].copy()
        pg["outcome"][0], pg["end_step"][0] = STRIKE_WIN, 5
        return pg
    monkeypatch.setattr(tool, "play_matrix_batch", extra)
    rd = tmp_path / "run"
    assert tool.main(["--settings", str(settings), "--run-dir", str(rd), "--cap-h", "1"]) == 6
    controls = json.loads((rd / "controls.json").read_text())
    assert controls["c_offset_tag_1p15_30s"]["status"] == "FAIL" and controls["c_offset_tag_1p15_30s"]["extra"] == 1
    assert not (rd / "results.json").exists()


def test_a_clamp_player_skips_own_cell_and_its_network_sees_at_most_the_clamp(tmp_path, monkeypatch):
    """T52-like player on its own 120 s game, clamped to 30 s: own_replay raw (and PASS); the matrix cell against its
    own training opponent is not held to own_replay (the override changes it by design; recorded)."""
    player = _t52_player(tmp_path / "t52")
    games = [g for g in real_games("score_matrix_t52.toml") if g["name"] == "tag_1p15_120s"]
    settings = write_settings(tmp_path / "s.toml", JOB14, {**player, "time_left": {"clamp_max_s": 30.0}}, games)
    seen = _spy_inputs(monkeypatch)
    rd = tmp_path / "run"
    assert tool.main(["--settings", str(settings), "--run-dir", str(rd), "--cap-h", "1"]) == 0
    assert float(torch.cat([tl for m, tl, _ in seen if not m]).max()) == 120.0
    assert float(torch.cat([tl for m, tl, _ in seen if m]).max()) == 30.0
    controls = json.loads((rd / "controls.json").read_text())
    assert set(controls) == {"own_replay", "scripts_tag_1p15_120s__guard_field"}
    assert controls["scripts_tag_1p15_120s__guard_field"]["own_cell"]["skipped"].startswith("time-left override")
    res = json.loads((rd / "results.json").read_text())
    assert res["player"]["time_left_override"] == "time-left input clamped to at most 30 s"


def test_without_an_override_the_player_is_not_wrapped_and_the_results_carry_no_new_key(guard_case):
    _, rd, settings, _ = guard_case
    res = json.loads((rd / "results.json").read_text())
    assert "time_left" not in res["player"] and "time_left_override" not in res["player"] and "opponents" not in res
    md = (rd / "results.md").read_text()
    assert "time-left input" not in md and " only; " not in md


def test_offset_and_subset_refusals_exit_2(tmp_path):
    player = _t52_player(tmp_path / "t52")
    g30 = [g for g in real_games("score_matrix_t52.toml") if g["name"] == "tag_1p15_30s"]
    g120 = [g for g in real_games("score_matrix_t52.toml") if g["name"] == "tag_1p15_120s"]
    cases = {
        "a": (JOB14, {**player, "time_left": {"offset_s": 60.0}}, g30),            # 600 + 1200 ticks is not 2400
        "b": (JOB14, {**player, "time_left": {"offset_s": 90.0}}, g120),           # 2400 + 1800 is not 2400
        "c": ({**JOB14, "opponents": ["guard_mirror"]}, {**player, "time_left": {"offset_s": 90.0}}, g30),  # no own opp
        "d": ({**JOB14, "opponents": ["guard_nobody"]}, player, g30),              # not a script of the other team
    }
    for name, (job, pl, games) in cases.items():
        s = write_settings(tmp_path / f"{name}.toml", job, pl, games)
        assert tool.main(["--settings", str(s), "--run-dir", str(tmp_path / name), "--cap-h", "1"]) == 2, name
        assert not (tmp_path / name / "controls.json").exists(), name


@pytest.mark.parametrize("job_extra,player_extra,match", [
    ({"opponents": []}, {}, "opponents"), ({"opponents": ["guard_field", "guard_field"]}, {}, "opponents"),
    ({"opponents": "guard_field"}, {}, "opponents"), ({"opponents": [1]}, {}, "opponents"),
    ({}, {"time_left": {"offset_s": 90.0, "clamp_max_s": 30.0}}, "exactly one"),
    ({}, {"time_left": {"clamp_max_s": 0.0}}, "clamp_max_s")])
def test_bad_optional_keys_are_refused_by_the_settings_loader(tmp_path, job_extra, player_extra, match):
    s = tomllib.loads((L1 / "score_matrix_t52.toml").read_text())
    path = write_settings(tmp_path / "s.toml", {**s["job"], **job_extra}, {**s["player"], **player_extra}, s["games"])
    with pytest.raises(ValueError, match=match):
        tool.load_settings(path)


L114 = {"score_matrix_l114_t52_offset.toml": ("tag_1p15_30s", 600, {"offset_s": 90.0}),
        "score_matrix_l114_t52_clamp.toml": ("tag_1p15_120s", 2400, {"clamp_max_s": 30.0}),
        "score_matrix_l114_arm_a_clamp.toml": ("tag_1p15_120s", 2400, {"clamp_max_s": 30.0})}


@pytest.mark.parametrize("name", sorted(L114))
def test_the_l114_settings(name):
    """Spec addendum 2: T52 at 30 s with time-left + 90 s (control C-offset), T52 at 120 s clamped to 30 s (test
    T-clamp), arm A at 120 s clamped to 30 s (INFO); guard_field only; task L1.14."""
    s = tool.load_settings(L1 / name)
    game, ticks, override = L114[name]
    assert s["job"]["task"] == "L1.14" and s["job"]["kind"] == "INFO" and s["job"]["opponents"] == ["guard_field"]
    assert s["player"]["time_left"] == override and s["player"]["side"] == "strike"
    (g,) = s["games"]
    t52 = {x["name"]: x for x in real_games("score_matrix_t52.toml")}
    assert g == t52[game]                                          # the same pinned game file and reference as L1.13
    assert exploit.load_game_cfg_file(tool._path(g["file"])).game_ticks() == ticks
    source = "score_matrix_l113_arm_a.toml" if "arm_a" in name else "score_matrix_t52.toml"
    want = tomllib.loads((L1 / source).read_text())["player"]
    assert {k: v for k, v in s["player"].items() if k != "time_left"} == want     # the player exactly as pinned before


def test_the_offset_keeps_an_out_of_game_drones_zeros():
    """Review fix (L1.14): one drone out of the game (alive 0, all zeros but team) keeps exactly its zeros under the
    offset; its team-mates get the offset."""
    spy = _Spy()
    team = scoring.TimeLeftOverride(spy, scoring.parse_time_left({"offset_s": 90.0}))
    alive = torch.tensor([[True, False, True]])
    obs = _obs(torch.tensor([20.0]), alive)
    team.act(obs)
    got = spy.seen[0]
    assert torch.equal(got[0, 1], obs[0, 1]) and float(got[0, 1, TL]) == 0.0
    assert float(got[0, 1].abs().sum()) == float(obs[0, 1, ObsView.team])          # zeros but team
    assert torch.equal(got[0, [0, 2], TL], torch.full((2,), 110.0))


def test_c_offset_fails_on_a_reach_one_tick_late():
    """Review fix (L1.14): a reach the own evaluation made at tick 300 and the offset game at tick 301 fails."""
    ctl = scoring.check_offset_prefix(_cell([S, S, G, G, G, G], [301, 600, 450, 600, 600, 600]), OWN_120, 600, 2400)
    assert ctl["status"] == scoring.FAIL and ctl["shifted"] == 1 and ctl["first_games"]["shifted"] == [0]


# ================================================================================================ L1.15: the delay check
# Spec ste_learning/drafts/L1_SIDE_TRACK_SPEC.md, addendum 3: games without a screen reference (script cells reported,
# INFO), the distance at each tag and the closest approach per cell.
DELAY_GAMES = {"tag_1p15_delay0": "tag_1p15_delay0.toml", "tag_1p15_delay0p30": "tag_1p15_delay0p30.toml"}


def _noref_game(name: str) -> dict:
    f = L1 / DELAY_GAMES[name]
    params = tomllib.loads(f.read_text())["starling_layer"]["params"]
    return {"name": name, "file": f"configs/ste_l1/{f.name}", "sha256": exploit.sha256_file(f), "reference": False,
            "params_sha256": exploit.sha256_file(ROOT / params), "clock_label": f"test {name}"}


def test_tag_stats_of_a_cell():
    inf = float("inf")
    pg = {"outcome": np.array([G, S, G, RUNNING], dtype=np.int8),
          "tag_pair_m": np.array([[1.10, inf, 1.30], [1.12, inf, inf], [inf, inf, inf], [1.00, inf, inf]]),
          "closest_3d_m": np.array([1.05, 1.11, inf, 0.9])}
    st = scoring.tag_stats(pg)
    assert st["tags"] == 3 and st["tag_distance_min_m"] == pytest.approx(1.10)
    assert st["tag_distance_median_m"] == pytest.approx(1.12)            # finished games only; skewed (1.30) so a mean would fail
    # closest_3d_m is measured after the study tag removes the pair (core/game.py): pairs never tagged, renamed so
    assert st["closest_never_tagged_min_m"] == pytest.approx(1.05)
    assert st["closest_never_tagged_median_m"] == pytest.approx(1.08)
    # closest approach, any pair, per finished game = min(its tag distances, closest_3d_m): 1.05, 1.11 (game 3: none)
    assert st["closest_any_pair_min_m"] == pytest.approx(1.05) and st["closest_any_pair_median_m"] == pytest.approx(1.08)
    assert "closest_3d_min_m" not in st and "closest_3d_median_m" not in st
    none = scoring.tag_stats({"outcome": np.array([S], dtype=np.int8), "tag_pair_m": np.array([[inf]]),
                              "closest_3d_m": np.array([inf])})
    assert none["tags"] == 0 and none["tag_distance_min_m"] is None and none["closest_any_pair_median_m"] is None


def test_the_closest_approach_of_any_pair_counts_the_tag():
    """Correctness review (L1.15): a game whose only near approach is a tag at 1.12 m (the pair is removed on that tick,
    so closest_3d_m never sees it; here 2.5 m) reports 1.12 m as its closest approach of any pair."""
    inf = float("inf")
    st = scoring.tag_stats({"outcome": np.array([G], dtype=np.int8), "tag_pair_m": np.array([[1.12, inf, inf]]),
                            "closest_3d_m": np.array([2.5])})
    assert st["closest_any_pair_min_m"] == pytest.approx(1.12) and st["closest_any_pair_median_m"] == pytest.approx(1.12)
    assert st["closest_never_tagged_min_m"] == pytest.approx(2.5)


def test_a_game_without_a_screen_reference_is_scored_info_with_tag_distances(tmp_path):
    """A no-reference game (the delay files): played on the player's own starts, every cell reported, no reference
    control (control plumbing_<batch>: paired starts, one for one, finite), labelled INFO; own_replay still on the
    player's own game; every row carries the tag distances and closest approach, every script cell its own row."""
    player = _t52_player(tmp_path / "t52")
    games = [g for g in real_games("score_matrix_t52.toml") if g["name"] == "tag_1p15_120s"] + \
        [_noref_game("tag_1p15_delay0")]
    settings = write_settings(tmp_path / "s.toml", {**JOB14, "task": "L1.15"}, player, games)
    rd = tmp_path / "run"
    assert tool.main(["--settings", str(settings), "--run-dir", str(rd), "--cap-h", "1"]) == 0
    controls = json.loads((rd / "controls.json").read_text())
    assert set(controls) == {"own_replay", "scripts_tag_1p15_120s__guard_field", "plumbing_tag_1p15_delay0__guard_field"}
    assert {v["status"] for v in controls.values()} == {"PASS"}
    assert "no screen reference" in controls["plumbing_tag_1p15_delay0__guard_field"]["detail"]
    assert controls["scripts_tag_1p15_120s__guard_field"]["own_cell"]["equal"] is True   # own game: own_cell applies
    res = json.loads((rd / "results.json").read_text())
    g = res["games"]["tag_1p15_delay0"]
    assert g["reference"] is None and "INFO" in g["reference_note"]
    resp = g["response"]                                     # the response parameter file the game reads, and its delay
    assert resp["params"] == "configs/ste_l1/study_params_delay0.toml" and resp["delay_s"] == 0.0
    assert resp["params_sha256"] == exploit.sha256_file(L1 / "study_params_delay0.toml")
    assert res["games"]["tag_1p15_120s"]["response"]["delay_s"] == 0.1482
    md = (rd / "results.md").read_text()
    assert "response delay 0.0 s" in md
    side = json.loads((rd / "games" / "tag_1p15_delay0__guard_field.json").read_text())   # recorded when played
    assert side["response"] == resp
    (row,) = g["rows"]
    for key in ("tags", "tag_distance_min_m", "tag_distance_median_m", "closest_any_pair_min_m",
                "closest_any_pair_median_m", "closest_never_tagged_min_m", "closest_never_tagged_median_m"):
        assert key in row["tag_stats"] and key in row["best_script"]["tag_stats"]
    gates = exploit.load_gates(Path(player["dir"]) / "gates.toml")
    names = [c["name"] for c in row["script_cells"]]
    assert names == list(gates.players["strikes"]) and "strike_straight" in names       # guard_field v strike_straight
    straight = row["script_cells"][names.index("strike_straight")]
    assert straight["cell"] == ["guard_field", "strike_straight"] and len(straight["ci"]) == 2
    assert sum(straight["end_reasons"].values()) == N and "tag_stats" in straight
    pg = scoring.load_batch(rd / "games" / "tag_1p15_delay0__guard_field.npz")
    assert straight["k"] == scoring.win_count(exploit.slice_cell(pg, names.index("strike_straight") + 1, N), "strike")[0]
    md = (rd / "results.md").read_text()
    assert "no screen reference" in md and "Tag distance" in md


def test_reference_false_refuses_the_reference_keys_and_true(tmp_path):
    s = tomllib.loads((L1 / "score_matrix_t52.toml").read_text())
    for bad, match in (({**_noref_game("tag_1p15_delay0"), "reference_sha256": "0" * 64}, "reference"),
                       ({**_noref_game("tag_1p15_delay0"), "reference": True}, "reference"),
                       ({k: v for k, v in s["games"][0].items() if k != "reference_variant"}, "reference_variant")):
        path = write_settings(tmp_path / "s.toml", s["job"], s["player"], [bad])
        with pytest.raises(ValueError, match=match):
            tool.load_settings(path)


L115 = {"score_matrix_l115_t55.toml": ("strike", "guard_field", 134, "2026-11-22_ste_l012c_tag_1p15_strike"),
        "score_matrix_l115_t54.toml": ("guard", "strike_straight", 572, "2026-11-22_ste_l012c_tag_1p15_guard")}


@pytest.mark.parametrize("name", sorted(L115))
def test_the_l115_settings_pin_the_real_files(name):
    """Spec addendum 3: T55 (Strike, 134 of 1,000) and T54 (Guard, 572) against their training opponents at the fitted
    delay 0.148 s (the existing game, screen reference) and at 0 and 0.30 s (no reference, INFO)."""
    side, opp, wins, folder = L115[name]
    s = tool.load_settings(L1 / name)
    p = s["player"]
    assert s["job"]["task"] == "L1.15" and s["job"]["opponents"] == [opp] and "time_left" not in p
    assert p["side"] == side and p["own_wins"] == wins and p["dir"] == f"ste_provisional/players/{folder}"
    d = tool._path(p["dir"])
    for f, key in (("gates.toml", "gates_sha256"), ("agent_final.pt", "agent_sha256"), ("eval_final.npz", "eval_sha256")):
        assert scoring.sha_problem(d / f, p[key], f) is None, f
    res = json.loads((d / "results.json").read_text())
    assert res["exploiter"]["k"] == wins and res["side"] == side and res["opponent"] == opp
    assert [g["name"] for g in s["games"]] == ["tag_1p15_120s", "tag_1p15_delay0", "tag_1p15_delay0p30"]
    t52 = {x["name"]: x for x in real_games("score_matrix_t52.toml")}
    assert {k: v for k, v in s["games"][0].items() if k != "params_sha256"} == t52["tag_1p15_120s"]
    for g in s["games"][1:]:
        assert g["reference"] is False and scoring.sha_problem(tool._path(g["file"]), g["sha256"], "game") is None
    want = {"tag_1p15_120s": "params/real_exploratory_v0.toml", "tag_1p15_delay0": "configs/ste_l1/study_params_delay0.toml",
            "tag_1p15_delay0p30": "configs/ste_l1/study_params_delay0p30.toml"}
    for g in s["games"]:                                 # every game pins the parameter file its game file names
        named = tomllib.loads(tool._path(g["file"]).read_text())["starling_layer"]["params"]
        assert named == want[g["name"]]
        assert scoring.sha_problem(ROOT / named, g["params_sha256"], "params") is None
    head = (L1 / name).read_text().split("[job]")[0]
    assert "T55 run's" in head and "games/*.npz" in head


def test_the_params_file_is_pinned_and_checked(tmp_path):
    """Correctness review (L1.15): a no-reference game must pin the sha256 of the parameter file its game file names
    (params_sha256; optional on a game with a screen reference); a mismatch is refused before anything plays."""
    s = tomllib.loads((L1 / "score_matrix_t52.toml").read_text())
    unpinned = {k: v for k, v in _noref_game("tag_1p15_delay0").items() if k != "params_sha256"}
    path = write_settings(tmp_path / "u.toml", s["job"], s["player"], [unpinned])
    with pytest.raises(ValueError, match="params_sha256"):
        tool.load_settings(path)
    player = _t52_player(tmp_path / "t52")
    for name, game in (("a", {**_noref_game("tag_1p15_delay0"), "params_sha256": "0" * 64}),
                       ("b", {**real_games("score_matrix_t52.toml")[0], "params_sha256": "0" * 64})):
        bad = write_settings(tmp_path / f"{name}.toml", {**JOB14, "task": "L1.15"}, player, [game])
        assert tool.main(["--settings", str(bad), "--run-dir", str(tmp_path / name), "--cap-h", "1"]) == 2, name
        assert not (tmp_path / name / "controls.json").exists()


def test_a_resume_with_another_response_file_is_refused(tmp_path, monkeypatch):
    """The response (parameter file, sha256, delay) is recorded per batch when it is played; a later batch of the same
    game that would play another one is refused (exit 2)."""
    player = _t52_player(tmp_path / "t52")
    settings = write_settings(tmp_path / "s.toml", {**JOB14, "task": "L1.15"}, player, [_noref_game("tag_1p15_delay0")])
    rd = tmp_path / "run"
    assert tool.main(["--settings", str(settings), "--run-dir", str(rd), "--cap-h", "1"]) == 0
    key = "plumbing_tag_1p15_delay0__guard_field"
    controls = json.loads((rd / "controls.json").read_text())
    controls.pop(key)
    (rd / "controls.json").write_text(json.dumps(controls))
    (rd / "results.json").unlink()                              # as if the run had stopped before this batch's check
    real = tool.response_of
    monkeypatch.setattr(tool, "response_of", lambda cfg: {**real(cfg), "params_sha256": "f" * 64})
    assert tool.main(["--settings", str(settings), "--run-dir", str(rd), "--cap-h", "1"]) == 2
    assert key not in json.loads((rd / "controls.json").read_text())
