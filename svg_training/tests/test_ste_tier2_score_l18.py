"""STE task L1.8: T46's base players re-scored on tier 2 under the estimate error (scripts/ste_tier2_score_l18.py).

CPU only, no Isaac: the parameter files of the two error conditions (they differ from v1 in the error keys only), the
settings file's pins, the effective error each condition flies (configs/s2b.toml [physics] laid over the file), and the
driver end to end on the PyTorch reference world (--dry-cpu) with small made-up players (a few games, a short clock).
"""
from __future__ import annotations

import json
import re
import sys
import tomllib
from pathlib import Path

import numpy as np
import pytest
import torch

from svg_training.core.physics_layer import load_game_physics_params
from svg_training.models.physics_params import ERROR_KEYS
from svg_training.ste import exploit, exploit_train, shared

ROOT = exploit.ROOT
sys.path.insert(0, str(ROOT / "scripts"))
import ste_tier2_score_l18 as tool  # noqa: E402

V1 = ROOT / "params" / "starling_physics_v1.toml"
NOMINAL = ROOT / "params" / "starling_physics_v1_nominal.toml"
CONSERVATIVE = ROOT / "params" / "starling_physics_v1_conservative.toml"
SETTINGS = ROOT / "configs" / "ste_l1" / "tier2_score_l18.toml"
# T63 (records/2026-11-23_ste_l13_fit_record.md): the L1.3 EXPLORATORY proposal, (sigma, tau) per quantity
T63 = {"pos": (0.0099, 1.2), "vel": (0.022, 1.3), "att": (0.0027, 2.0)}
UNIT = {"pos": "m", "vel": "mps", "att": "rad"}
N, TICKS = 2, 160


@pytest.fixture(autouse=True)
def scratch_shared(tmp_path, monkeypatch):
    monkeypatch.setenv(shared.SHARED_ENV, str(tmp_path / "shared"))
    monkeypatch.setenv(shared.LEGACY_LOGS_ENV, "")


# ================================================================================================ parameter files
def _flat(path: Path) -> dict:
    data = tomllib.loads(path.read_text())
    return {f"{sec}.{k}": v for sec, table in data.items() for k, v in table.items()}


@pytest.mark.parametrize("path,factor", [(NOMINAL, 1.0), (CONSERVATIVE, 2.0)])
def test_error_files_differ_from_v1_in_the_error_keys_only(path, factor):
    v1, new = _flat(V1), _flat(path)
    assert set(v1) == set(new)
    changed = {k for k in v1 if v1[k] != new[k]}
    assert changed == {f"model.{k}" for k in ERROR_KEYS}
    for q, (sigma, tau) in T63.items():
        assert new[f"model.state_error_{q}_{UNIT[q]}"] == pytest.approx(factor * sigma, abs=1e-12)
        assert new[f"model.state_error_{q}_tau_s"] == tau         # the nominal taus in both files
    assert all(v1[f"model.{k}"] == 0.0 for k in ERROR_KEYS)       # v1 itself stays at 0


@pytest.mark.parametrize("path", [NOMINAL, CONSERVATIVE])
def test_error_files_are_labelled_exploratory_from_t63(path):
    head = path.read_text().split("[source]")[0]
    assert "EXPLORATORY" in head and "T63" in head and "L1.8" in head
    for line in path.read_text().splitlines():
        if line.startswith("state_error_"):
            assert "EXPLORATORY" in line and "T63" in line, line


def test_each_condition_flies_its_own_error_after_the_s2b_overrides():
    """configs/s2b.toml [physics] is laid over every physics file: it must not touch the error keys."""
    s = tool.load_settings(SETTINGS)
    base = exploit.load_game_cfg_file(ROOT / s["game"]["file"])
    for cond in s["conditions"]:
        p = load_game_physics_params(tool.condition_cfg(base, cond))
        want = tomllib.loads((ROOT / cond["params"]).read_text())["model"]
        assert {k: getattr(p, k) for k in ERROR_KEYS} == {k: float(want[k]) for k in ERROR_KEYS}, cond["name"]
    names = [c["name"] for c in s["conditions"]]
    assert names == ["off", "nominal", "conservative"]           # "off" first: its gated controls fail fast


def test_condition_cfg_changes_the_backend_and_the_physics_file_only():
    from svg_training.ste import tier2_train as T
    s = tool.load_settings(SETTINGS)
    base = exploit.load_game_cfg_file(ROOT / s["game"]["file"])
    for cond in s["conditions"]:
        assert T.cfg_differences(base, tool.condition_cfg(base, cond)) == ["starling.backend", "starling.physics_params"]
    assert list(s["controls"]["condition_difference"]) == ["starling.backend", "starling.physics_params"]


def _flight(params_path: Path, seed: int, ticks: int = 40):
    """A few ticks of the physics drone on the PyTorch world under fixed setpoints; positions after each tick."""
    from svg_training.models.physics_drone import PhysicsDrone
    from svg_training.models.physics_params import load_physics_drone_params
    from svg_training.models.rigid_body import TorchRigidBodyWorld
    p = load_physics_drone_params(params_path)
    n, m = 4, 2
    drone = PhysicsDrone(TorchRigidBodyWorld(n, m, p.airframe, p.physics_dt_s, "cpu"), p, "cpu", noise_seed=seed)
    start = torch.zeros(n, m, 3)
    start[..., 0] = torch.arange(m, dtype=torch.float32)
    start[..., 2] = 1.2
    drone.reset(torch.ones(n, m, dtype=torch.bool), start, torch.zeros(n, m))
    out = []
    for t in range(ticks):
        goal = start + torch.tensor([0.02 * t, 0.0, 0.0])
        drone.step_setpoint(goal, torch.zeros(n, m, 3), torch.zeros(n, m, 3), torch.zeros(n, m), torch.zeros(n, m))
        out.append(drone.pos_m.clone())
    return torch.stack(out)


def test_the_error_moves_the_drone_and_the_same_seed_repeats():
    off, nom, nom_again, cons = (_flight(V1, 7), _flight(NOMINAL, 7), _flight(NOMINAL, 7), _flight(CONSERVATIVE, 7))
    assert torch.equal(nom, nom_again)                            # same seed, same flight
    assert (nom - off).abs().max() > 1e-4                         # the nominal error moves the drone
    assert (cons - off).abs().max() > (nom - off).abs().max()     # twice the sigma moves it more (same draws)


# ================================================================================================ the settings file
def test_settings_pin_the_real_files():
    s = tool.load_settings(SETTINGS)
    problems = tool.pin_problems(s)
    assert problems == [], problems
    assert s["job"]["task"] == "L1.8" and s["job"]["kind"] == "INFO"
    assert s["guard_player"]["own_wins"] == 913 and s["strike_player"]["own_wins"] == 636
    cross = tomllib.loads((ROOT / "configs" / "ste_l012d" / "cross_tag.toml").read_text())["t46"]
    assert s["guard_player"]["agent_sha256"] == cross["guard_agent_sha256"]
    assert s["strike_player"]["agent_sha256"] == cross["strike_agent_sha256"]
    sums = dict(reversed(line.split()) for line in (ROOT / "ste_provisional" / "SHA256SUMS").read_text().splitlines())
    for side in ("guard", "strike"):
        p = s[f"{side}_player"]
        rel = Path(p["dir"]).relative_to("ste_provisional").as_posix()
        for name, key in tool.PLAYER_FILES:
            assert sums[f"{rel}/{name}"] == p[key], (side, name)


def test_the_batch_layout_and_its_size():
    s = tool.load_settings(SETTINGS)
    lay = tool.layout(s)
    g, st = lay.guards, lay.strikes
    assert [c for c in lay.cells if c[0] == tool.PLAYER["guard"]] == [(tool.PLAYER["guard"], x) for x in st]
    assert [c for c in lay.cells if c[1] == tool.PLAYER["strike"]] == [(x, tool.PLAYER["strike"]) for x in g]
    assert ("guard_mark_edge", "strike_straight") in lay.cells and ("guard_parked_centre", "strike_straight") in lay.cells
    assert len(lay.cells) == len(st) + len(g) + 2 * len(s["cells"]["repeat"]) == 15
    for c in s["cells"]["repeat"]:
        assert lay.cells.count(tuple(c)) == 2                     # played twice, same starts, same seed
    assert int(s["job"]["games"]) == 1000 and int(s["job"]["ticks_cap"]) == 2400


def test_the_cap_fits_the_task_cap():
    s = tool.load_settings(SETTINGS)
    task_cap = float(re.search(r'(?m)^"L1\.8" = ([0-9.]+)', (ROOT / "configs" / "ste_learning.toml").read_text())[1])
    assert 0 < float(s["job"]["cap_h"]) <= task_cap


def test_known_check_band():
    s = tool.load_settings(SETTINGS)
    c = s["controls"]
    assert (c["known_holds_min"], c["known_holds_max"], c["known_games"]) == (507, 569, 1000)
    from svg_training.core.rewards import GUARD_WIN, STRIKE_WIN
    for holds, want in ((506, "FAIL"), (507, "PASS"), (538, "PASS"), (569, "PASS"), (570, "FAIL")):
        out = np.array([GUARD_WIN] * holds + [STRIKE_WIN] * (1000 - holds))
        assert tool.known_check({"outcome": out}, c, GUARD_WIN)["status"] == want, holds


def test_settings_refuse_a_gated_condition_that_is_not_first(tmp_path):
    text = SETTINGS.read_text().replace('gated_repeat_condition = "off"', 'gated_repeat_condition = "nominal"')
    (tmp_path / "s.toml").write_text(text)
    with pytest.raises(ValueError, match="first condition"):
        tool.load_settings(tmp_path / "s.toml")


# ================================================================================================ the driver (dry CPU)
def _small(text: str) -> str:
    for key, value in {"device": '"cpu"', "eval_games": str(N), "ticks_cap": str(TICKS)}.items():
        text, k = re.subn(rf"(?m)^{key} = .*$", f"{key} = {value}", text, count=1)
        assert k == 1, key
    return text


def _modules(hidden, seed: int) -> dict:
    from skrl.resources.preprocessors.torch import RunningStandardScaler

    from svg_training.opponents.learned import OBS_SPACE, StandinPolicy
    torch.manual_seed(seed)
    return {f"exploiter_{k}": {"policy": StandinPolicy(hidden, "cpu").state_dict(),
                               "observation_preprocessor": RunningStandardScaler(OBS_SPACE, device="cpu").state_dict()}
            for k in range(3)}


def make_player(folder: Path, side: str, seed: int) -> dict:
    """A run folder as the L0.12 driver leaves it (gates.toml, agent_final.pt, eval_final.npz, eval_info.npz,
    results.json), at the test size; returns the settings table that pins it."""
    folder.mkdir(parents=True)
    (folder / "gates.toml").write_text(_small((ROOT / "configs" / "ste_l012" / "gates.toml").read_text()))
    gates = exploit.load_gates(folder / "gates.toml")
    hidden = list(gates.trainer["hidden"])
    mods = _modules(hidden, seed)
    torch.save(mods, folder / "agent_final.pt")
    team = exploit_train.team_from_modules(side, mods, hidden, "cpu")
    ref = exploit.load_reference(ROOT / gates.reference["file"])
    cfg, hold = exploit.variant_cfg(gates, "base"), int(gates.trainer["decision_ticks"])
    pg = exploit.play_cells(cfg, "3v3", ref, exploit.eval_cells(gates, "base", side), N, "cpu", int(ref.meta["seed"]),
                            TICKS, learner=team, hold_ticks=hold)
    np.savez(folder / "eval_final.npz", **{k: v for k, v in pg.items() if isinstance(v, np.ndarray)})
    others = gates.players["guards" if side == "strike" else "strikes"]
    info_cells = [(x, exploit.EXPLOITER) if side == "strike" else (exploit.EXPLOITER, x) for x in others]
    info = exploit.play_cells(cfg, "3v3", ref, info_cells, N, "cpu", int(ref.meta["seed"]), TICKS, learner=team,
                              hold_ticks=hold)
    np.savez(folder / "eval_info.npz", **{k: v for k, v in info.items() if isinstance(v, np.ndarray)})
    from svg_training.core.rewards import GUARD_WIN, STRIKE_WIN
    won = GUARD_WIN if side == "guard" else STRIKE_WIN
    cells = {f"{c[0]} v {c[1]}": {"games": N, "holds": int(np.sum(info["outcome"][i * N:(i + 1) * N] == GUARD_WIN)),
                                  "reaches": int(np.sum(info["outcome"][i * N:(i + 1) * N] == STRIKE_WIN))}
             for i, c in enumerate(info_cells)}
    (folder / "results.json").write_text(json.dumps({"info": cells, "complete": True}))
    table = {"label": f"test {side} player", "dir": str(folder), "variant": "base",
             "own_wins": int(np.sum(pg["outcome"][:N] == won)), "own_source": "made by the test"}
    table.update({key: exploit.sha256_file(folder / name) for name, key in tool.PLAYER_FILES})
    return table


def _value(v) -> str:
    if isinstance(v, list):
        return "[" + ", ".join(_value(x) for x in v) + "]"
    if isinstance(v, bool):
        return "true" if v else "false"
    return json.dumps(v) if isinstance(v, str) else repr(v)


def write_settings(path: Path, guard: dict, strike: dict, **controls) -> Path:
    """The committed settings at the test size; the known-answer band opened to the test's N games (the real band is for
    1,000 games: tests/test_ste_tier2_score_l18.py test_known_check_band checks the rule itself)."""
    s = tomllib.loads(SETTINGS.read_text())
    s["job"].update({"device": "cpu", "games": N, "ticks_cap": TICKS})
    s["controls"].update({"known_games": N, "known_holds_min": 0, "known_holds_max": N, **controls})
    s["guard_player"], s["strike_player"] = guard, strike
    lines = []
    for sec in ("job", "game", "guard_player", "strike_player", "cells", "controls", "tier1"):
        lines += [f"[{sec}]", *[f"{k} = {_value(v)}" for k, v in s[sec].items()], ""]
    for c in s["conditions"]:
        lines += ["[[conditions]]", *[f"{k} = {_value(v)}" for k, v in c.items()], ""]
    path.write_text("\n".join(lines))
    return path


@pytest.fixture(scope="module")
def dry_case(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("l18")
    mp = pytest.MonkeyPatch()
    mp.setenv(shared.SHARED_ENV, str(tmp / "shared"))
    mp.setenv(shared.LEGACY_LOGS_ENV, "")
    guard, strike = make_player(tmp / "guard", "guard", 3), make_player(tmp / "strike", "strike", 4)
    settings = write_settings(tmp / "s.toml", guard, strike)
    rd = tmp / "run"
    args = ["--settings", str(settings), "--run-dir", str(rd), "--cap-h", "0.9", "--dry-cpu"]
    code = tool.main(args)
    again = tool.main(args)                                        # a finished folder: nothing to do
    mp.undo()
    return code, again, rd, settings


def test_dry_run_scores_every_condition_with_every_control_pass(dry_case):
    code, again, rd, _ = dry_case
    assert code == 0 and again == 0
    controls = json.loads((rd / "controls.json").read_text())
    assert {v["status"] for k, v in controls.items() if not v.get("info")} == {"PASS"}
    for name in ("tier1_replay", "tier2_off", "tier2_nominal", "tier2_conservative", "condition_off",
                 "repeat_off", "known_off"):
        assert name in controls, name
    assert any(k.startswith("physics_agreement_off_launch") for k in controls)
    assert controls["repeat_nominal"]["info"] is True                # the error draws differ per slot: INFO there
    res = json.loads((rd / "results.json").read_text())
    assert res["complete"] is True and res["dry_cpu"] is True and res["smoke"] is False
    assert [c["name"] for c in res["conditions"]] == ["off", "nominal", "conservative"]
    rows = res["rows"]
    assert len(rows) == 13                                          # 11 player cells + 2 script cells (repeats folded)
    for r in rows:
        assert set(r["tier2"]) == {"off", "nominal", "conservative"}
        assert r["tier1"]["source"] and r["tier1"]["n"] + r["tier1"]["unfinished"] == N
        for name in ("off", "nominal", "conservative"):              # n = finished games (a short test clock cuts some)
            assert r["tier2"][name]["n"] + r["tier2"][name]["end_reasons"]["unfinished"] == N
    md = (rd / "results.md").read_text()
    assert "observed in the training simulator" in md.lower() and "tier 2" in md
    assert "EXPLORATORY" in md


def test_dry_run_tier1_condition_is_the_players_own_record(dry_case):
    _, _, rd, settings = dry_case
    res = json.loads((rd / "results.json").read_text())
    s = tomllib.loads(Path(settings).read_text())
    for side, opp in (("guard", "strike_straight"), ("strike", "guard_mark_edge")):
        cell = [tool.PLAYER["guard"], opp] if side == "guard" else [opp, tool.PLAYER["strike"]]
        row = next(r for r in res["rows"] if r["cell"] == cell)
        assert row["training_opponent"] is True
        assert row["tier1"]["k"] == s[f"{side}_player"]["own_wins"]


def test_a_changed_pin_is_refused(tmp_path):
    guard, strike = make_player(tmp_path / "guard", "guard", 3), make_player(tmp_path / "strike", "strike", 4)
    guard["agent_sha256"] = "0" * 64
    settings = write_settings(tmp_path / "s.toml", guard, strike)
    code = tool.main(["--settings", str(settings), "--run-dir", str(tmp_path / "run"), "--cap-h", "0.9", "--dry-cpu"])
    assert code == 2 and not (tmp_path / "run" / "controls.json").exists()


def test_cap_must_equal_the_settings(tmp_path):
    code = tool.main(["--settings", str(SETTINGS), "--run-dir", str(ROOT / "runs" / "never_l18"), "--cap-h", "0.5",
                      "--dry-cpu"])
    assert code == 2


def test_isaac_launch_needs_headless():
    assert tool.pre_isaac_problem(["--settings", str(SETTINGS), "--run-dir", "runs/x", "--cap-h", "0.9"])[0] == 2
    assert tool.pre_isaac_problem(["--settings", str(SETTINGS), "--run-dir", "runs/x", "--cap-h", "0.9",
                                   "--headless"]) is None


def test_smoke_flags_are_stamped_and_skip_the_known_answers(tmp_path):
    guard, strike = make_player(tmp_path / "guard", "guard", 3), make_player(tmp_path / "strike", "strike", 4)
    settings = write_settings(tmp_path / "s.toml", guard, strike)
    rd = tmp_path / "run"
    code = tool.main(["--settings", str(settings), "--run-dir", str(rd), "--cap-h", "0.9", "--dry-cpu",
                      "--games", "1", "--max-ticks", "20"])
    assert code == 0
    res = json.loads((rd / "results.json").read_text())
    assert res["smoke"] is True and res["games"] == 1 and res["ticks_cap"] == 20
    controls = json.loads((rd / "controls.json").read_text())
    assert controls["tier1_replay"]["status"] == "NOT_CHECKED" and controls["known_off"]["status"] == "NOT_CHECKED"


def test_results_need_every_required_control():
    """Fail closed: a stop between two controls must not publish (the required set, as ste_score_matrix's ``want``)."""
    s = tool.load_settings(SETTINGS)
    names = [c["name"] for c in s["conditions"]]
    full = {"tier1_replay": {"status": "PASS"}, "known_off": {"status": "PASS"}}
    for n in names:
        full.update({f"condition_{n}": {"status": "PASS"}, f"tier2_{n}": {"status": "PASS"},
                     f"physics_agreement_{n}_launch1": {"status": "PASS"},
                     f"repeat_{n}": {"status": "PASS"} if n == "off" else {"status": "INFO", "info": True}})
    assert tool.required_problems(full, s, smoke=False) == ([], {})
    gone = {k: v for k, v in full.items() if k != "repeat_nominal"}
    assert tool.required_problems(gone, s, smoke=False)[0] == ["repeat_nominal"]
    no_agree = {k: v for k, v in full.items() if k != "physics_agreement_off_launch1"}
    assert tool.required_problems(no_agree, s, smoke=False)[0] == ["physics_agreement_off_launch<k>"]
    skipped = {**full, "tier1_replay": {"status": "NOT_CHECKED"}}
    assert tool.required_problems(skipped, s, smoke=False)[1] == {"tier1_replay": "NOT_CHECKED"}
    assert tool.required_problems(skipped, s, smoke=True) == ([], {})
    sneaky = {**full, "repeat_off": {"status": "INFO"}}                 # INFO only where the control says it is INFO
    assert tool.required_problems(sneaky, s, smoke=False)[1] == {"repeat_off": "INFO"}
