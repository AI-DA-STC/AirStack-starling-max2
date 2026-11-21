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
    """(folder of T46 runs, settings file, the modules by side, {"screen", "base"}: the fake references' paths)."""
    tmp = tmp_path_factory.mktemp("l012d")
    runs = tmp / "runs"
    real = tomllib.loads(REAL_CONFIG.read_text())
    cfg = json.loads(json.dumps(real))
    real_t46 = exploit.load_gates(ROOT / "configs" / "ste_l012" / "gates.toml")
    real_screen = exploit.load_gates(ROOT / real["screen"]["gates"])
    hidden, hold = list(real_t46.trainer["hidden"]), int(real_t46.trainer["decision_ticks"])
    t46_ref = exploit.load_reference(ROOT / real_t46.reference["file"])
    screen_ref = exploit.load_reference(ROOT / real_screen.reference["file"])
    mods = {side: _modules(hidden, seed) for side, seed in (("guard", 3), ("strike", 4))}
    teams = {side: exploit_train.team_from_modules(side, mods[side], hidden, "cpu") for side in mods}
    players = {drv.T46_GUARD: teams["guard"], drv.T46_STRIKE: teams["strike"]}

    def fake_reference(cfg_, ref, cells, variant, path):
        """The driver's own batch played on the CPU, its script cells kept as the reference (real starts, real meta)."""
        pg = exploit.play_cells(cfg_, "3v3", ref, cells, N, "cpu", int(ref.meta["seed"]), TICKS, hold_ticks=hold,
                                players=players)
        kept = {(variant, g, s): exploit.slice_cell(pg, i, N) for i, (g, s) in enumerate(cells)
                if drv.is_script_cell((g, s))}
        exploit.write_reference(path, ref.starts_m, ref.start_miss, kept, ref.meta)
        return kept

    # X4's base-game batch -> the fake T44 reference the T46 gate file copy points at (C4)
    base_ref = tmp / "t44_reference.npz"
    x4 = drv.x4_cells(real_screen, "tag_1p15", real_t46, "base")
    base_cells = fake_reference(exploit.variant_cfg(real_t46, "base"), t46_ref, x4, "base", base_ref)
    gates_text = _small((ROOT / "configs" / "ste_l012" / "gates.toml").read_text())
    gates_text = re.sub(r'(?m)^file = "configs/ste_l012/t44_reference.npz"', f'file = "{base_ref}"', gates_text)
    gates_text = re.sub(r'(?m)^sha256 = "4bc5e011[0-9a-f]*"', f'sha256 = "{_sha(base_ref)}"', gates_text)
    for side in ("guard", "strike"):
        rd = runs / real["t46"][f"{side}_run"]
        rd.mkdir(parents=True)
        (rd / "gates.toml").write_text(gates_text)
        gates = exploit.load_gates(rd / "gates.toml")
        assert gates.reference["file"] == str(base_ref)
        (rd / "run.json").write_text(json.dumps({"variant": "base", "side": side}))
        torch.save(mods[side], rd / "agent_final.pt")
        pg = exploit.play_cells(exploit.variant_cfg(gates, "base"), "3v3", t46_ref,
                                exploit.eval_cells(gates, "base", side), N, "cpu", int(t46_ref.meta["seed"]), TICKS,
                                learner=teams[side], hold_ticks=hold)
        np.savez(rd / "eval_final.npz", **{k: v for k, v in pg.items() if isinstance(v, np.ndarray)})
        won = GUARD_WIN if side == "guard" else STRIKE_WIN
        cfg["t46"][f"{side}_agent_sha256"] = _sha(rd / "agent_final.pt")
        cfg["t46"][f"{side}_eval_sha256"] = _sha(rd / "eval_final.npz")
        cfg["t46"]["guard_holds" if side == "guard" else "strike_reaches"] = int(np.sum(pg["outcome"][:N] == won))
    cfg["t46"]["gates_sha256"] = _sha(runs / real["t46"]["guard_run"] / "gates.toml")
    cfg["t46"]["reference_sha256"] = _sha(base_ref)
    g15, s15 = real_screen.variants["tag_1p15"]["g_star"], real_screen.variants["tag_1p15"]["s_star"]
    cfg["t46"]["x4_script_holds"] = int(np.sum(base_cells[("base", g15, s15)]["outcome"] == GUARD_WIN))

    # the 1.15 m batch -> the fake screen reference (C3)
    ref_path = tmp / "screen_reference.npz"
    cells = drv.x_cells(real_screen, "tag_1p15", real_t46, "base")
    ref_cells = fake_reference(exploit.variant_cfg(real_screen, "tag_1p15"), screen_ref, cells, "tag_1p15", ref_path)
    screen_text = _small((ROOT / real["screen"]["gates"]).read_text())
    screen_text = re.sub(r'(?m)^file = "configs/ste_l012b/screen_reference.npz"', f'file = "{ref_path}"', screen_text)
    screen_text = re.sub(r'(?m)^sha256 = "49014000[0-9a-f]*"', f'sha256 = "{_sha(ref_path)}"', screen_text)
    screen_gates = tmp / "screen_gates.toml"
    screen_gates.write_text(screen_text)
    assert exploit.load_gates(screen_gates).reference["file"] == str(ref_path)
    cfg["screen"].update(gates=str(screen_gates), gates_sha256=_sha(screen_gates), reference_sha256=_sha(ref_path),
                         screen_holds=int(np.sum(ref_cells[("tag_1p15", g15, s15)]["outcome"] == GUARD_WIN)))
    cfg["clips"]["games"] = 2
    settings = write_config(tmp / "cross_tag.toml", cfg)
    return runs, settings, mods, {"screen": ref_path, "base": base_ref}


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
    return re.search(r"\bX[1-4]\b", text) is not None             # word match: "PX4" is not an X cell


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
    assert {k: v["status"] for k, v in res["controls"].items()} == {"C1": "PASS", "C2": "PASS", "C3": "PASS",
                                                                     "C4": "PASS"}
    for key in ("X1", "X2", "X3", "X4"):
        x = res["cells"][key]
        assert x["n"] + x["unfinished"] == N and 0 <= x["k"] <= x["n"] and len(x["ci"]) == 2
    assert res["cells"]["X1"]["cell"] == [drv.T46_GUARD, "strike_straight"]
    assert res["cells"]["X2"]["cell"] == ["guard_field", drv.T46_STRIKE]
    assert res["cells"]["X3"]["cell"] == ["guard_mark_edge", drv.T46_STRIKE]
    assert set(res["cells"]["X1"]["paired"]) >= {"trained_only", "script_only", "both", "neither", "sign_test_p"}
    assert res["cells"]["X4"]["cell"] == ["guard_field", drv.T46_STRIKE] and res["cells"]["X4"]["game"] == "base"
    assert res["cells"]["X4"]["script"]["cell"] == ["guard_field", "strike_straight"] and "paired" in res["cells"]["X4"]
    assert "against guard_field, an opponent the T46 Strike team never trained against" in res["cells"]["X4"]["reading"]
    assert "X3" in res["cells"] and "paired" not in res["cells"]["X3"]
    assert res["closest_tol"]["source"] == "configs/ste_l011/gates.toml" and len(res["closest_tol"]["sha256"]) == 64
    assert res["closest_tol"]["tol_m"] == 0.0 and "gpu" in res and res["clip_seed"] == 120950
    for name in ("c1_base_guard", "c2_base_strike", "c4_base_field", "x_tag_1p15"):
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
    assert (out / "games" / "c1_base_guard.npz").is_file()                 # the failed batch kept for diagnosis
    assert not (out / "games" / "x_tag_1p15.npz").is_file()                # later batches never played
    assert not _x_keys((out / "results.md").read_text())
    assert _main(drv, runs, settings, out) == drv.EXIT_CONTROL_FAILED       # terminal: the same folder ends with 6 again


def test_a_mismatching_screen_reference_refuses(fixture, drv, tmp_path):
    """C3: the 1.15 m script cell differs from the screen reference in one game: exit 6, no X number."""
    runs, settings, _, refs = fixture
    ref_path = refs["screen"]
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
    assert not (out / "results.json").is_file()
    assert (out / "games" / "x_tag_1p15.npz").is_file()                    # kept for diagnosis, never summarised
    assert not _x_keys((out / "results.md").read_text())


def test_a_mismatching_t44_reference_refuses(fixture, drv, tmp_path):
    """C4: X4's base-game script cell differs from T44's reference in one game: exit 6, no X number (X4's batch is its
    own, never appended to C2's)."""
    runs, cfg = _copy(fixture, tmp_path)
    base = fixture[3]["base"]
    ref = exploit.load_reference(base)
    cells = {k: {f: np.array(v, copy=True) for f, v in c.items()} for k, c in ref.cells.items()}
    cells[("base", "guard_field", "strike_straight")]["tags"][0] += 1
    bad = tmp_path / "t44_reference.npz"
    exploit.write_reference(bad, ref.starts_m, ref.start_miss, cells, ref.meta)
    for side in ("guard", "strike"):
        g = runs / cfg["t46"][f"{side}_run"] / "gates.toml"
        g.write_text(g.read_text().replace(str(base), str(bad)).replace(_sha(base), _sha(bad)))
    cfg["t46"].update(gates_sha256=_sha(g), reference_sha256=_sha(bad))
    out = tmp_path / "run"
    assert _main(drv, runs, write_config(tmp_path / "s.toml", cfg), out) == drv.EXIT_CONTROL_FAILED
    controls = json.loads((out / "controls.json").read_text())
    assert controls["C1"]["status"] == "PASS" and controls["C2"]["status"] == "PASS"
    assert controls["C4"]["status"] == "FAIL" and "C3" not in controls
    assert not (out / "results.json").is_file() and (out / "games" / "c4_base_field.npz").is_file()
    assert not _x_keys((out / "results.md").read_text())


def test_roles_are_found_by_cell_not_by_position(drv):
    """x_roles looks every X cell and script cell up by name: a reordered batch still maps each role to its cell."""
    screen = exploit.load_gates(ROOT / "configs" / "ste_l012b" / "gates.toml")
    t46 = exploit.load_gates(ROOT / "configs" / "ste_l012" / "gates.toml")
    roles = drv.x_roles(screen, "tag_1p15", t46, "base")
    assert set(roles) == {"X1", "X2", "X3", "X4"} and roles["X4"]["batch"] == drv.X4_BATCH
    cells = {drv.X_BATCH: list(reversed(drv.x_cells(screen, "tag_1p15", t46, "base"))),
             drv.X4_BATCH: list(reversed(drv.x4_cells(screen, "tag_1p15", t46, "base")))}
    for name, r in roles.items():
        i, j = drv.role_index(r, cells)
        assert tuple(cells[r["batch"]][i]) == r["cell"]
        assert (j is None) == (r["script"] is None) and (j is None or tuple(cells[r["batch"]][j]) == r["script"])


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
    assert [round(c["radius"], 2) for c in calls] == [1.6, 1.6, 1.6, 1.15]
    assert all(c["hold"] == 12 for c in calls)
    assert calls[2]["cells"] == [("guard_field", drv.T46_STRIKE), ("guard_field", "strike_straight")]
    assert calls[1]["cells"][0] == ("guard_mark_edge", "exploiter")        # C2's batch replayed whole, nothing appended
    x = calls[3]
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


def test_clips_render_for_real_on_the_cpu(fixture, drv, tmp_path):
    """Unmocked: make_clips through the L0.12 make_videos and render_replay writes GIFs under clips/X1/videos/ (2
    games, a short clip length)."""
    import dataclasses
    from types import SimpleNamespace
    runs, settings, _, _ = fixture
    s = drv.load_settings(settings)
    screen = exploit.load_gates(s["screen"]["gates"])
    screen = dataclasses.replace(screen, videos={**screen.videos, "max_ticks": TICKS})
    ctx = SimpleNamespace(screen=screen, v15="tag_1p15", cfg15=exploit.variant_cfg(screen, "tag_1p15"),
                          dirs={side: runs / s["t46"][f"{side}_run"] for side in ("guard", "strike")})
    out = drv.make_clips(ctx, s, tmp_path)
    assert out["X1"]["files"], out
    for f in out["X1"]["files"]:
        assert f.startswith("clips/X1/videos/") and (tmp_path / f.split(":")[0]).is_file()


def test_a_clip_crash_still_leaves_complete_results(fixture, drv, tmp_path, monkeypatch):
    """The clips run last: an error there is caught, results.json is complete and the clips are marked missing."""
    runs, settings, _, _ = fixture

    def boom(*a, **k):
        raise RuntimeError("renderer fell over")
    monkeypatch.setattr(drv, "make_clips", boom)
    out = tmp_path / "run"
    assert drv.main(["--t46-runs-dir", str(runs), "--settings", str(settings), "--run-dir", str(out),
                     "--cap-h", "1"]) == 0
    res = json.loads((out / "results.json").read_text())
    assert res["complete"] is True and "renderer fell over" in res["clips"]["missing"]


def test_no_clips_when_the_cap_is_reached_or_a_stop_was_asked(drv):
    from types import SimpleNamespace
    made = []
    capped = SimpleNamespace(stop_requested=False, cap_reached=lambda: True)
    stopped = SimpleNamespace(stop_requested=True, cap_reached=lambda: False)
    free = SimpleNamespace(stop_requested=False, cap_reached=lambda: False)
    assert "cap" in drv.clips_or_missing(capped, lambda: made.append(1))["missing"]
    assert "stop" in drv.clips_or_missing(stopped, lambda: made.append(1))["missing"]
    assert not made
    assert drv.clips_or_missing(free, lambda: {"X1": {"files": []}}) == {"X1": {"files": []}}


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
    x4 = res["cells"]["X4"]
    assert re.search(rf"1\.6 m strategy at 1\.6 m against guard_field, an opponent the T46 Strike team never trained "
                     rf"against: {x4['k']:,} of {x4['n']:,} ", text)
    clip_line = f"Clips: the clip seed's own starts (clip_seed 120950), CPU, not the {res['eval_games']:,} scoring starts"
    seeds = text.split("## Seeds", 1)[1].split("##", 1)[0]
    figures = text.split("## Figures and videos", 1)[1].split("##", 1)[0]
    assert clip_line in seeds and clip_line in figures
    assert "X4" in (tmp_path / "LEDGER.md").read_text()
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
