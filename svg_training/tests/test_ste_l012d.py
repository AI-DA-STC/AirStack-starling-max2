"""STE L0.12d Cross-tag check: the driver (scripts/ste_cross_tag_l012d.py) and the record writer
(scripts/make_ste_l012d_record.py) on small fake run folders (CPU only, a few games, a short cap; no Isaac).

The fixture is self-consistent by construction: fake T46 run folders (the L0.12 gate file at a CPU size, random
networks, eval_final.npz played on the CPU) and a fake screen reference made by playing the driver's own 1.15 m batch on
the CPU; a fixture settings file pins their sha256."""
from __future__ import annotations

import importlib.util
import json
import re
import shutil
import tomllib
from pathlib import Path

import numpy as np
import pytest
import torch

from svg_training.core.rewards import GUARD_WIN, RUNNING, STRIKE_WIN
from svg_training.ste import exploit, exploit_train

ROOT = Path(__file__).resolve().parents[1]
N, TICKS = 2, 160
REAL_CONFIG = ROOT / "configs" / "ste_l012d" / "cross_tag.toml"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def drv():
    return _load("ste_cross_tag_l012d")


def _small(text: str, extra: dict | None = None) -> str:
    """A gate file's text at the test size: CPU, N games, TICKS ticks (and any other line replaced)."""
    subs = {"device": '"cpu"', "eval_games": str(N), "ticks_cap": str(TICKS), **(extra or {})}
    for key, value in subs.items():
        text, k = re.subn(rf"(?m)^{key} = .*$", f"{key} = {value}", text, count=1)
        assert k == 1, key
    return text


def _modules(hidden, seed: int) -> dict:
    """agent_final.pt's layout (Learner.modules): per drone the policy and its observation scaler."""
    from skrl.resources.preprocessors.torch import RunningStandardScaler

    from svg_training.opponents.learned import OBS_SPACE, StandinPolicy
    torch.manual_seed(seed)
    out = {}
    for k in range(3):
        pol = StandinPolicy(hidden, "cpu")
        sc = RunningStandardScaler(OBS_SPACE, device="cpu")
        out[f"exploiter_{k}"] = {"policy": pol.state_dict(), "observation_preprocessor": sc.state_dict()}
    return out


def _sha(p: Path) -> str:
    return exploit.sha256_file(p)


def _toml_value(v) -> str:
    return json.dumps(v) if isinstance(v, str) else repr(v)


def write_config(path: Path, cfg: dict) -> Path:
    lines = []
    for section, table in cfg.items():
        lines.append(f"[{section}]")
        lines += [f"{k} = {_toml_value(v)}" for k, v in table.items()]
    path.write_text("\n".join(lines) + "\n")
    return path


@pytest.fixture(scope="module")
def fixture(tmp_path_factory, drv):
    """(folder of T46 runs, settings file, the modules by side, the fake screen reference's path)."""
    tmp = tmp_path_factory.mktemp("l012d")
    runs = tmp / "runs"
    gates_text = _small((ROOT / "configs" / "ste_l012" / "gates.toml").read_text())
    real = tomllib.loads(REAL_CONFIG.read_text())
    cfg = json.loads(json.dumps(real))
    t46_ref = exploit.load_reference(ROOT / "configs" / "ste_l012" / "t44_reference.npz")
    mods = {}
    for side, seed in (("guard", 3), ("strike", 4)):
        rd = runs / real["t46"][f"{side}_run"]
        rd.mkdir(parents=True)
        (rd / "gates.toml").write_text(gates_text)
        gates = exploit.load_gates(rd / "gates.toml")
        (rd / "run.json").write_text(json.dumps({"variant": "base", "side": side}))
        mods[side] = _modules(list(gates.trainer["hidden"]), seed)
        torch.save(mods[side], rd / "agent_final.pt")
        team = exploit_train.team_from_modules(side, mods[side], list(gates.trainer["hidden"]), "cpu")
        pg = exploit.play_cells(exploit.variant_cfg(gates, "base"), "3v3", t46_ref,
                                exploit.eval_cells(gates, "base", side), N, "cpu", int(t46_ref.meta["seed"]), TICKS,
                                learner=team, hold_ticks=int(gates.trainer["decision_ticks"]))
        np.savez(rd / "eval_final.npz", **{k: v for k, v in pg.items() if isinstance(v, np.ndarray)})
        won = GUARD_WIN if side == "guard" else STRIKE_WIN
        cfg["t46"][f"{side}_agent_sha256"] = _sha(rd / "agent_final.pt")
        cfg["t46"][f"{side}_eval_sha256"] = _sha(rd / "eval_final.npz")
        cfg["t46"]["guard_holds" if side == "guard" else "strike_reaches"] = int(np.sum(pg["outcome"][:N] == won))
    cfg["t46"]["gates_sha256"] = _sha(runs / real["t46"]["guard_run"] / "gates.toml")

    # the fake screen reference: the driver's own 1.15 m batch played on the CPU, its script cells kept
    real_screen = exploit.load_gates(ROOT / real["screen"]["gates"])
    screen_ref = exploit.load_reference(ROOT / real_screen.reference["file"])
    t46_gates = exploit.load_gates(runs / real["t46"]["guard_run"] / "gates.toml")
    teams = {side: exploit_train.team_from_modules(side, mods[side], list(t46_gates.trainer["hidden"]), "cpu")
             for side in mods}
    cells = drv.x_cells(real_screen, "tag_1p15", t46_gates, real["t46"]["variant"])
    pg = exploit.play_cells(exploit.variant_cfg(real_screen, "tag_1p15"), "3v3", screen_ref, cells, N, "cpu",
                            int(screen_ref.meta["seed"]), TICKS, hold_ticks=int(t46_gates.trainer["decision_ticks"]),
                            players={drv.T46_GUARD: teams["guard"], drv.T46_STRIKE: teams["strike"]})
    ref_cells = {("tag_1p15", g, s): exploit.slice_cell(pg, i, N) for i, (g, s) in enumerate(cells)
                 if drv.is_script_cell((g, s))}
    ref_path = tmp / "screen_reference.npz"
    exploit.write_reference(ref_path, screen_ref.starts_m, screen_ref.start_miss, ref_cells, screen_ref.meta)
    screen_text = _small((ROOT / real["screen"]["gates"]).read_text())
    screen_text = re.sub(r'(?m)^file = "configs/ste_l012b/screen_reference.npz"', f'file = "{ref_path}"', screen_text)
    screen_text = re.sub(r'(?m)^sha256 = "49014000[0-9a-f]*"', f'sha256 = "{_sha(ref_path)}"', screen_text)
    screen_gates = tmp / "screen_gates.toml"
    screen_gates.write_text(screen_text)
    assert exploit.load_gates(screen_gates).reference["file"] == str(ref_path)
    g_star, s_star = real_screen.variants["tag_1p15"]["g_star"], real_screen.variants["tag_1p15"]["s_star"]
    cfg["screen"].update(gates=str(screen_gates), gates_sha256=_sha(screen_gates), reference_sha256=_sha(ref_path),
                         screen_holds=int(np.sum(ref_cells[("tag_1p15", g_star, s_star)]["outcome"] == GUARD_WIN)))
    cfg["clips"]["games"] = 2
    settings = write_config(tmp / "cross_tag.toml", cfg)
    return runs, settings, mods, ref_path


def _main(drv, runs, settings, run_dir, *extra):
    return drv.main(["--t46-runs-dir", str(runs), "--settings", str(settings), "--run-dir", str(run_dir),
                     "--cap-h", "1", "--no-videos", *extra])


def _copy(fixture, tmp_path):
    runs, settings, mods, ref = fixture
    new = tmp_path / "runs"
    shutil.copytree(runs, new)
    cfg = tomllib.loads(settings.read_text())
    return new, cfg


def _x_keys(text: str) -> bool:
    return any(k in text for k in ("X1", "X2", "X3"))


# ================================================================================================ the driver
@pytest.fixture(scope="module")
def good_run(fixture, drv, tmp_path_factory):
    runs, settings, _, _ = fixture
    rd = tmp_path_factory.mktemp("good") / "run"
    code = _main(drv, runs, settings, rd)
    return code, rd


def test_the_settings_file_loads_and_pins_t46(drv):
    s = drv.load_settings(REAL_CONFIG)
    assert s["t46"]["guard_holds"] == 913 and s["t46"]["strike_reaches"] == 636 and s["screen"]["screen_holds"] == 645
    assert s["compare"]["trained_guard_holds"] == 572 and s["compare"]["trained_strike_reaches"] == 134
    assert s["t46"]["gates_sha256"] == _sha(ROOT / "configs" / "ste_l012" / "gates.toml")


def test_the_settings_file_refuses_an_unknown_key(drv, tmp_path):
    cfg = tomllib.loads(REAL_CONFIG.read_text())
    cfg["t46"]["typo_key"] = 1
    with pytest.raises(ValueError, match="typo_key"):
        drv.load_settings(write_config(tmp_path / "s.toml", cfg))


def test_controls_pass_on_a_self_consistent_fixture(good_run, drv):
    code, rd = good_run
    assert code == 0
    res = json.loads((rd / "results.json").read_text())
    assert res["complete"] is True and res["controls_pass"] is True
    assert {k: v["status"] for k, v in res["controls"].items()} == {"C1": "PASS", "C2": "PASS", "C3": "PASS"}
    for key in ("X1", "X2", "X3"):
        x = res["cells"][key]
        assert x["n"] + x["unfinished"] == N and 0 <= x["k"] <= x["n"] and len(x["ci"]) == 2
    assert res["cells"]["X1"]["cell"] == [drv.T46_GUARD, "strike_straight"]
    assert res["cells"]["X2"]["cell"] == ["guard_field", drv.T46_STRIKE]
    assert res["cells"]["X3"]["cell"] == ["guard_mark_edge", drv.T46_STRIKE]
    assert set(res["cells"]["X1"]["paired"]) >= {"trained_only", "script_only", "both", "neither", "sign_test_p"}
    assert "X3" in res["cells"] and "paired" not in res["cells"]["X3"]
    for name in ("c1_base_guard", "c2_base_strike", "x_tag_1p15"):
        assert (rd / "games" / f"{name}.npz").is_file()
    md = (rd / "results.md").read_text()
    assert "1.6 m strategy at 1.15 m:" in md and "observed in the training simulator" in md.lower()


def test_a_rerun_of_a_done_folder_changes_nothing(fixture, drv, good_run):
    runs, settings, _, _ = fixture
    code, rd = good_run
    before = (rd / "results.json").read_text()
    assert _main(drv, runs, settings, rd) == 0
    assert (rd / "results.json").read_text() == before


def test_a_mismatching_record_refuses_with_no_x_numbers(fixture, drv, tmp_path):
    """T46's eval_final.npz differs from the replay in one game (its pin updated, so only the control can catch it)."""
    runs, cfg = _copy(fixture, tmp_path)
    rd = runs / cfg["t46"]["guard_run"]
    d = dict(np.load(rd / "eval_final.npz"))
    d["end_step"][-1] += 1                                  # a script cell's game
    np.savez(rd / "eval_final.npz", **d)
    cfg["t46"]["guard_eval_sha256"] = _sha(rd / "eval_final.npz")
    settings = write_config(tmp_path / "s.toml", cfg)
    out = tmp_path / "run"
    assert _main(drv, runs, settings, out) == drv.EXIT_CONTROL_FAILED
    controls = json.loads((out / "controls.json").read_text())
    assert controls["C1"]["status"] == "FAIL"
    assert not (out / "results.json").is_file()
    assert not (out / "games" / "x_tag_1p15.npz").is_file()
    assert not _x_keys((out / "results.md").read_text())
    assert _main(drv, runs, settings, out) == drv.EXIT_CONTROL_FAILED       # terminal: the same folder ends with 6 again


def test_a_mismatching_screen_reference_refuses(fixture, drv, tmp_path):
    """C3: the 1.15 m script cell differs from the screen reference in one game: exit 6, no X number."""
    runs, settings, _, ref_path = fixture
    cfg = tomllib.loads(settings.read_text())
    ref = exploit.load_reference(ref_path)
    cells = {k: {f: np.array(v, copy=True) for f, v in c.items()} for k, c in ref.cells.items()}
    key = ("tag_1p15", "guard_field", "strike_straight")
    cells[key]["end_step"][0] += 1
    bad_ref = tmp_path / "screen_reference.npz"
    exploit.write_reference(bad_ref, ref.starts_m, ref.start_miss, cells, ref.meta)
    text = Path(cfg["screen"]["gates"]).read_text()
    text = text.replace(str(ref_path), str(bad_ref)).replace(_sha(ref_path), _sha(bad_ref))
    gates = tmp_path / "screen_gates.toml"
    gates.write_text(text)
    cfg["screen"].update(gates=str(gates), gates_sha256=_sha(gates), reference_sha256=_sha(bad_ref))
    out = tmp_path / "run"
    assert _main(drv, runs, write_config(tmp_path / "s.toml", cfg), out) == drv.EXIT_CONTROL_FAILED
    controls = json.loads((out / "controls.json").read_text())
    assert controls["C1"]["status"] == "PASS" and controls["C2"]["status"] == "PASS"
    assert controls["C3"]["status"] == "FAIL"
    assert not (out / "results.json").is_file() and not (out / "games" / "x_tag_1p15.npz").is_file()
    assert not _x_keys((out / "results.md").read_text())


@pytest.mark.parametrize("key", ["guard_agent_sha256", "strike_agent_sha256", "gates_sha256", "guard_eval_sha256",
                                 "reference_sha256", "game_sha256"])
def test_a_t46_pin_mismatch_refuses_before_any_game(fixture, drv, tmp_path, monkeypatch, key):
    runs, settings, _, _ = fixture
    cfg = tomllib.loads(settings.read_text())
    cfg["t46"][key] = "0" * 64
    played = []
    monkeypatch.setattr(exploit, "play_cells", lambda *a, **k: played.append(1))
    out = tmp_path / "run"
    assert _main(drv, runs, write_config(tmp_path / "s.toml", cfg), out) == drv.EXIT_REFUSED
    assert not played and not (out / "results.json").is_file()


@pytest.mark.parametrize("key", ["gates_sha256", "reference_sha256", "game_sha256"])
def test_a_screen_pin_mismatch_refuses_before_any_game(fixture, drv, tmp_path, monkeypatch, key):
    runs, settings, _, _ = fixture
    cfg = tomllib.loads(settings.read_text())
    cfg["screen"][key] = "0" * 64
    played = []
    monkeypatch.setattr(exploit, "play_cells", lambda *a, **k: played.append(1))
    assert _main(drv, runs, write_config(tmp_path / "s.toml", cfg), tmp_path / "run") == drv.EXIT_REFUSED
    assert not played


def test_a_changed_network_file_refuses(fixture, drv, tmp_path):
    """agent_final.pt changed after the pin: refused on its sha256 before it is loaded."""
    runs, cfg = _copy(fixture, tmp_path)
    rd = runs / cfg["t46"]["strike_run"]
    mods = torch.load(rd / "agent_final.pt", weights_only=False)
    mods["exploiter_0"]["policy"] = {k: v + 0.5 if v.dtype.is_floating_point else v
                                     for k, v in mods["exploiter_0"]["policy"].items()}
    torch.save(mods, rd / "agent_final.pt")
    assert _main(drv, runs, write_config(tmp_path / "s.toml", cfg), tmp_path / "run") == drv.EXIT_REFUSED


def test_x_cells_play_the_1p15_game_with_the_base_run_networks(fixture, drv, tmp_path, monkeypatch):
    """Spy on play_cells: C1 and C2 play the base game (tag 1.6 m) with T46's learner; the X batch plays the 1.15 m game
    with networks whose weights are T46's base runs' agent_final.pt."""
    runs, settings, mods, _ = fixture
    real, calls = exploit.play_cells, []

    def spy(cfg, size, ref, cells, n, device, seed, ticks_cap, learner=None, hold_ticks=1, should_stop=None, world=None,
            players=None):
        calls.append({"radius": cfg.tag.radius_m, "cells": list(cells), "learner": learner, "players": players,
                      "hold": hold_ticks})
        return real(cfg, size, ref, cells, n, device, seed, ticks_cap, learner=learner, hold_ticks=hold_ticks,
                    should_stop=should_stop, world=world, players=players)

    monkeypatch.setattr(exploit, "play_cells", spy)
    assert _main(drv, runs, settings, tmp_path / "run") == 0
    assert [round(c["radius"], 2) for c in calls] == [1.6, 1.6, 1.15]
    assert all(c["hold"] == 12 for c in calls)
    x = calls[2]
    assert x["learner"] is None and set(x["players"]) == {drv.T46_GUARD, drv.T46_STRIKE}

    def same(team, side):
        want = mods[side]["exploiter_0"]["policy"]
        got = team.nets[0].state_dict()
        return all(torch.equal(got[k.split("net.", 1)[1]], v) for k, v in want.items() if k.startswith("net."))
    assert same(x["players"][drv.T46_GUARD], "guard") and same(x["players"][drv.T46_STRIKE], "strike")
    assert same(calls[0]["learner"], "guard") and same(calls[1]["learner"], "strike")
    assert x["players"][drv.T46_GUARD].team == "guard" and x["players"][drv.T46_STRIKE].team == "strike"
    res = json.loads((tmp_path / "run" / "results.json").read_text())
    assert res["games"]["x"]["file"] == "configs/ste_l011/tag_1p15.toml"
    assert res["networks"]["guard"]["run"] == tomllib.loads(settings.read_text())["t46"]["guard_run"]


def test_paired_counts_read_wins_of_the_trained_side(drv):
    """Hand-made outcomes: the Guard side wins on holds, the Strike side on reaches (transfer.paired relabelled)."""
    H, R = GUARD_WIN, STRIKE_WIN
    script = np.array([H, H, R, R, H])
    trained = np.array([H, R, H, R, R])
    g = drv.paired_wins(trained, script, "guard")
    assert (g["both"], g["trained_only"], g["script_only"], g["neither"]) == (1, 1, 2, 1)
    s = drv.paired_wins(trained, script, "strike")
    assert (s["both"], s["trained_only"], s["script_only"], s["neither"]) == (1, 2, 1, 1)
    with pytest.raises(ValueError):
        drv.paired_wins(np.array([H, RUNNING]), np.array([H, H]), "guard")


def test_clips_use_the_l012_drawing_with_one_win_and_one_loss_asked(fixture, drv, monkeypatch, tmp_path):
    """X1 and X2 clips go through the L0.12 driver's make_videos (the 1.15 m game, the run's side and its 1.15 m
    opponent, [clips] games recorded, keep 2); a clip set without both outcomes says so."""
    from types import SimpleNamespace
    runs, settings, mods, _ = fixture
    s = drv.load_settings(settings)
    screen = exploit.load_gates(s["screen"]["gates"])
    seen = []

    def fake(gates, variant, side, cfg, learner, run_dir, opponent=None):
        seen.append({"games": gates.videos["games"], "keep": gates.videos["keep"], "variant": variant, "side": side,
                     "radius": cfg.tag.radius_m, "modules": learner.modules(), "run_dir": run_dir})
        kind = "hold" if side == "guard" else "reach"
        return [f"videos/{variant}_{side}_game0_{kind}.gif: game 0", f"videos/{variant}_{side}_game1_hold.gif: game 1"]

    monkeypatch.setattr(drv.l012, "make_videos", fake)
    ctx = SimpleNamespace(screen=screen, v15="tag_1p15", cfg15=exploit.variant_cfg(screen, "tag_1p15"),
                          dirs={side: runs / s["t46"][f"{side}_run"] for side in ("guard", "strike")})
    out = drv.make_clips(ctx, s, tmp_path)
    assert [x["side"] for x in seen] == ["guard", "strike"] and all(x["variant"] == "tag_1p15" for x in seen)
    assert all(round(x["radius"], 2) == 1.15 and x["games"] == s["clips"]["games"] and x["keep"] == 2 for x in seen)
    assert torch.equal(seen[0]["modules"]["exploiter_0"]["policy"]["net.0.weight"],
                       mods["guard"]["exploiter_0"]["policy"]["net.0.weight"])
    assert seen[0]["run_dir"] == tmp_path / "clips" / "X1"
    assert out["X1"]["note"] is not None and "hold" in out["X1"]["note"]      # two holds: no Guard loss recorded
    assert out["X2"]["note"] is None and out["X2"]["files"][0].startswith("clips/X2/videos/")


# ================================================================================================ the record writer
@pytest.fixture(scope="module")
def rec():
    return _load("make_ste_l012d_record")


def test_the_record_carries_the_reading_words(good_run, rec, tmp_path):
    _, rd = good_run
    assert rec.main(["--run-dir", str(rd), "--number", "T56", "--out-dir", str(tmp_path), "--name", "l012d_test",
                     "--ledger", str(tmp_path / "LEDGER.md"), "--append-ledger"]) == 0
    text = (tmp_path / "l012d_test_record.md").read_text()
    res = json.loads((rd / "results.json").read_text())
    x1, x2 = res["cells"]["X1"], res["cells"]["X2"]
    assert re.search(rf"1\.6 m strategy at 1\.15 m: {x1['k']:,} of {x1['n']:,} \([0-9.na]+–[0-9.na]+\) against the "
                     rf"1\.15 m-trained team's 572 and the script's {x1['script']['k']}", text)
    assert re.search(rf"1\.6 m strategy at 1\.15 m: {x2['k']:,} of {x2['n']:,} \([0-9.na]+–[0-9.na]+\) against the "
                     rf"1\.15 m-trained team's 134 and the script's {x2['script']['k']}", text)
    assert "one seed per side, one opponent, one start set" in text.lower()
    assert "observed in the training simulator" in text.lower() and "INFO" in text
    assert "validated" not in text.lower() and "category" not in text.lower()
    row = (tmp_path / "LEDGER.md").read_text().strip()
    assert row.startswith("| T56 |") and "STE L0.12d" in row and "| INFO |" in row
    assert row.endswith("| records/l012d_test_record.md |")


def test_the_record_writer_refuses_without_passing_controls(good_run, rec, tmp_path):
    _, rd = good_run
    bad = tmp_path / "run"
    shutil.copytree(rd, bad)
    res = json.loads((bad / "results.json").read_text())
    res["controls_pass"] = False
    (bad / "results.json").write_text(json.dumps(res))
    assert rec.main(["--run-dir", str(bad), "--number", "T56", "--out-dir", str(tmp_path)]) == 1
    (bad / "results.json").unlink()
    assert rec.main(["--run-dir", str(bad), "--number", "T56", "--out-dir", str(tmp_path)]) == 1
    assert not list(tmp_path.glob("*_record.md"))


def test_the_record_writer_never_overwrites(good_run, rec, tmp_path):
    _, rd = good_run
    args = ["--run-dir", str(rd), "--number", "T56", "--out-dir", str(tmp_path), "--name", "x"]
    assert rec.main(args) == 0
    assert rec.main(args) == 1
