"""S2b Task 9 (S2 Task 10, moved): the stand-in trainer (pipe test), its loader, TensorBoard logging and gate rule.

CPU only. The pure-rules runs go through a child process (the trainer sets one CPU thread for itself); the physics
run uses the in-process test hook (a TorchRigidBodyWorld instead of IsaacWorld), which only tests may use."""
import hashlib
import json
import pathlib
import subprocess
import sys
import tomllib

import pytest
import torch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "scripts"))
from _proc import child_env, child_python  # noqa: E402
from svg_training.core.game import SvgGame  # noqa: E402
from svg_training.core.game_config import CONFIGS, load_game_cfg  # noqa: E402
from svg_training.core.observations import INTERFACE_VERSION, OBS_DIM  # noqa: E402
from svg_training.core.strategy import check_strategy  # noqa: E402
from svg_training.opponents.learned import SkrlPolicyStrategy  # noqa: E402
from svg_training.opponents.scripted import make_strategy  # noqa: E402

import train_standin  # noqa: E402
from test_s2b_config import STANDIN_SHA256  # noqa: E402   (pinned in S2b Task 1)

CFG, _ = load_game_cfg(use_local=False)
SCRIPT = ROOT / "scripts" / "train_standin.py"
TB = tomllib.loads((CONFIGS / "s2b.toml").read_text())["tensorboard"]


def _run_cli(*args: str, timeout: int = 600) -> subprocess.CompletedProcess:
    return subprocess.run([child_python(), str(SCRIPT), *args], cwd=ROOT, env=child_env(str(ROOT / "source")),
                          capture_output=True, text=True, timeout=timeout)


def _in_process(argv: list[str], **kw) -> int:
    threads = torch.get_num_threads()          # the trainer sets one CPU thread; give the suite its own back
    try:
        return train_standin.main(argv, **kw)
    finally:
        torch.set_num_threads(threads)


@pytest.fixture(scope="module")
def smoke_run(tmp_path_factory) -> pathlib.Path:
    """The S2 smoke run: CPU, 32 games, --timesteps-override 200 (about 6 s on the laptop; the owner's
    1-minute TensorBoard smoke)."""
    runs = tmp_path_factory.mktemp("runs")
    r = _run_cli("--config", "configs/s2.toml", "--seed", "1", "--name", "smoke", "--device", "cpu",
                 "--num-games-override", "32", "--timesteps-override", "200", "--eval-games", "16",
                 "--runs-dir", str(runs))
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-4000:]
    return runs / "smoke"


def test_standin_smoke(smoke_run):
    assert (smoke_run / "agent.pt").exists()
    meta = tomllib.loads((smoke_run / "interface.toml").read_text())
    # S2's text said interface_version == 0; the observation is now version 0.1 (71 numbers)
    assert meta["pipe_test"] is True and meta["interface_version"] == INTERFACE_VERSION and meta["preset"] == "pure"
    assert meta["motion"] == "pure" and meta["world"] == "none" and meta["parameter_set"] == "none (pure rules)"
    assert meta["observation"]["dim"] == OBS_DIM and meta["seed"] == 1 and meta["tick_s"] == 0.05
    assert meta["game_config_sha256"] == hashlib.sha256((CONFIGS / "s2_game.toml").read_bytes()).hexdigest()
    res = json.loads((smoke_run / "train_result.json").read_text())
    assert res["timesteps_done"] == 200 and res["game_steps_done"] == 6400 and not res["stopped_by_wall_clock_cap"]
    assert res["evaluations"] == 2                              # at the start and at the end
    check_strategy(SkrlPolicyStrategy(smoke_run, 32, "cpu"), SvgGame(CFG, 32, 2, 1, device="cpu"))


def test_tensorboard_event_file_has_game_scalars(smoke_run):   # the owner's TensorBoard addition
    from make_s2b_figures import read_scalars
    from tensorboard.backend.event_processing.event_accumulator import EventAccumulator

    scalars = read_scalars(smoke_run)
    for tag in TB["game_scalars"]:
        assert tag in scalars, (tag, sorted(scalars))
    assert "game/hold_rate" in scalars
    for b in ("strike_straight", "strike_flank"):
        assert f"game/hold_rate/{b}" in scalars
    assert any(t.startswith("Loss / Policy loss") for t in scalars)     # skrl's own curves, same folder
    assert "Reward / Total reward (mean)" in scalars
    texts = set()
    for f in smoke_run.glob("events.out.tfevents.*"):
        ea = EventAccumulator(str(f), size_guidance={"tensors": 0})
        ea.Reload()
        texts |= set(ea.Tags()["tensors"])
    for key in TB["settings_text"]:
        assert f"settings/{key}/text_summary" in texts, (key, texts)


def test_standin_figure_from_event_files(smoke_run, tmp_path):
    import make_s2b_figures
    out = tmp_path / "curves.png"
    make_s2b_figures.standin(str(out), str(smoke_run))
    assert out.stat().st_size > 10_000


def test_learned_refuses_other_team_size(smoke_run):
    s = SkrlPolicyStrategy(smoke_run, 8, "cpu")
    assert s.act(torch.zeros(8, 2, OBS_DIM)).shape == (8, 2, 4)
    for g in (1, 3):
        with pytest.raises(ValueError, match="trained for 2 Guard drones"):
            s.act(torch.zeros(8, g, OBS_DIM))


def test_learned_refuses_other_interface(smoke_run, tmp_path):
    other = tmp_path / "old"
    other.mkdir()
    (other / "agent.pt").write_bytes((smoke_run / "agent.pt").read_bytes())
    text = (smoke_run / "interface.toml").read_text().replace(f'interface_version = "{INTERFACE_VERSION}"',
                                                               'interface_version = "0"')
    (other / "interface.toml").write_text(text)
    with pytest.raises(ValueError, match="interface"):
        SkrlPolicyStrategy(other, 8, "cpu")


def test_make_strategy_loads_run_folder(smoke_run):
    s = make_strategy(str(smoke_run), "guard", CFG, 16, "cpu", 0)
    assert isinstance(s, SkrlPolicyStrategy) and s.team == "guard" and s.deterministic
    with pytest.raises(ValueError, match="Guard stand-in"):
        make_strategy(str(smoke_run), "strike", CFG, 16, "cpu", 0)
    assert make_strategy("guard_mark_edge", "guard", CFG, 16, "cpu", 0).name != s.name   # scripted names unchanged


def test_learned_matches_the_trained_agent(smoke_run):
    """The loader applies the saved observation scaler: its actions equal skrl's own mean actions of the same agent
    (rebuilt and loaded by skrl), and differ from the network on unscaled observations."""
    from skrl.multi_agents.torch.ippo import IPPO, IPPO_CFG
    from skrl.resources.preprocessors.torch import RunningStandardScaler
    from svg_training.envs.skrl_adapter import skrl_kwargs_defaults
    from svg_training.opponents.learned import ACT_SPACE, OBS_SPACE, make_models

    names = ["guard_0", "guard_1"]
    kw = skrl_kwargs_defaults(names)
    kw["observation_preprocessor_kwargs"] = {a: {"size": OBS_SPACE, "device": "cpu"} for a in names}
    kw["value_preprocessor_kwargs"] = {a: {"size": 1, "device": "cpu"} for a in names}
    agent = IPPO(possible_agents=names, models=make_models(names, [128, 128], "cpu"),
                 observation_spaces={a: OBS_SPACE for a in names}, action_spaces={a: ACT_SPACE for a in names},
                 device="cpu", cfg=IPPO_CFG(observation_preprocessor={a: RunningStandardScaler for a in names},
                                            value_preprocessor={a: RunningStandardScaler for a in names},
                                            experiment={"write_interval": 0, "checkpoint_interval": 0}, **kw))
    agent.load(str(smoke_run / "agent.pt"))
    game = SvgGame(CFG, 16, 2, 1, device="cpu", seed=5)
    obs = game.reset()["guard"]
    for _ in range(30):
        obs = game.step({"guard": torch.rand(16, 2, 4) * 2 - 1, "strike": torch.zeros(16, 1, 4)}).obs["guard"]
    got = SkrlPolicyStrategy(smoke_run, 16, "cpu").act(obs)
    for k, a in enumerate(names):
        with torch.no_grad():
            _, out = agent.policies[a].act({"observations": agent._observation_preprocessor[a](obs[:, k])},
                                           role="policy")
        torch.testing.assert_close(got[:, k], out["mean_actions"].clamp(-1, 1))
        with torch.no_grad():
            raw = agent.policies[a].net(obs[:, k]).clamp(-1, 1)
        assert not torch.allclose(raw, got[:, k])          # so the scaler is really applied


def test_standin_ignores_local_file(tmp_path, monkeypatch):
    local = tmp_path / "local"
    local.mkdir()
    (local / "partner_rules.toml").write_text("[partner_rules]\nguard_units_per_step = 0.02\n")   # made up
    loaded, prov = load_game_cfg(local_dir=local)                 # it would change the Guard speed if read
    assert prov.local_file and loaded.team_speed_mps("guard") != CFG.team_speed_mps("guard")
    monkeypatch.setattr(train_standin, "LOCAL_DIR", local)
    rc = _in_process(["--seed", "3", "--name", "nolocal", "--device", "cpu", "--num-games-override", "8",
                      "--timesteps-override", "32", "--eval-games", "4", "--eval-max-steps", "40",
                      "--runs-dir", str(tmp_path / "runs")])
    assert rc == 0
    meta = tomllib.loads((tmp_path / "runs" / "nolocal" / "interface.toml").read_text())
    assert meta["local_file"] == "none"
    assert meta["action"]["guard_speed_mps"] == CFG.team_speed_mps("guard")


def _table(seed: int, trained: dict[str, tuple[int, int]], random: dict[str, tuple[int, int]],
           bands: int = 3, run: str | None = None, preset: str = "pure") -> dict:
    """A fake score.py table: per behaviour (guard_wins, games) per band for the trained Guard and random."""
    rows = []
    for guard, counts in ((run or f"runs/x_seed{seed}", trained), ("random", random)):
        for b, (k, n) in counts.items():
            for band in ("lab", "middle", "large")[:bands]:
                rows.append({"preset": preset, "size": "2v1", "guard": guard, "strike": b, "band": band,
                             "games": n, "guard_wins": k})
    return {"seed": seed, "preset": preset, "rows": rows}


def test_standin_gate_rule():
    gates = tomllib.loads((CONFIGS / "s2.toml").read_text())["standin_gates"]
    good = {"strike_straight": (700, 1000), "strike_flank": (650, 1000)}
    rand = {"strike_straight": (300, 1000), "strike_flank": (300, 1000)}
    res = train_standin.standin_verdict([_table(s, good, rand) for s in (1, 2, 3)], gates)
    assert res["verdict"] == "PASS" and res["seeds_passed"] == [1, 2, 3]
    assert res["cells"][0]["trained"]["games"] == 3000              # 1,000 per band, summed
    # one seed short of 0.20 on one behaviour -> FAIL
    short = {"strike_straight": (490, 1000), "strike_flank": (650, 1000)}         # 0.19 above random
    res = train_standin.standin_verdict([_table(1, good, rand), _table(2, short, rand), _table(3, good, rand)],
                                        gates)
    assert res["verdict"] == "FAIL" and res["seeds_passed"] == [1, 3]
    assert not next(c for c in res["cells"] if c["seed"] == 2 and c["behaviour"] == "strike_straight")["gain_ok"]
    # a gain >= 0.20 with overlapping intervals (few games) -> FAIL
    few_t = {"strike_straight": (8, 15), "strike_flank": (8, 15)}                  # 24 / 45 = 0.53
    few_r = {"strike_straight": (5, 15), "strike_flank": (5, 15)}                  # 15 / 45 = 0.33
    res = train_standin.standin_verdict([_table(s, few_t, few_r) for s in (1, 2, 3)], gates)
    c = res["cells"][0]
    assert c["gain"] >= 0.20 and c["gain_ok"] and not c["intervals_disjoint"] and res["verdict"] == "FAIL"
    # fewer seeds than required -> FAIL
    assert train_standin.standin_verdict([_table(s, good, rand) for s in (1, 2)], gates)["verdict"] == "FAIL"
    # a table that also holds another preset (scored as information): only the trained preset's rows count
    mixed = []
    for s_ in (1, 2, 3):
        t = _table(s_, good, rand)
        t["rows"] += _table(s_, {"strike_straight": (0, 1000), "strike_flank": (0, 1000)}, rand,
                            preset="starling")["rows"]
        mixed.append(t)
    res = train_standin.standin_verdict(mixed, gates, strict=True)
    assert res["verdict"] == "PASS" and res["cells"][0]["trained"]["games"] == 3000
    with pytest.raises(ValueError, match="3 bands of 1000"):                     # runs of record: full counts only
        train_standin.standin_verdict([_table(s, few_t, few_r) for s in (1, 2, 3)], gates, strict=True)


def test_verdict_cli(smoke_run, tmp_path):
    gates = tmp_path / "gates.toml"
    gates.write_text(train_standin.table_text((CONFIGS / "s2.toml").read_text(), "standin_gates"))   # the copy

    def score_dir(name: str, seed: int, per_band: int = 1000, local=None) -> str:
        d = tmp_path / name
        d.mkdir()
        k = per_band * 7 // 10
        t = _table(1, {"strike_straight": (k, per_band), "strike_flank": (k, per_band)},
                   {"strike_straight": (per_band // 5, per_band), "strike_flank": (per_band // 5, per_band)},
                   run=str(smoke_run))
        meta = {"seed": seed, "local_file": local, "guards": [str(smoke_run), "random"]}
        (d / "scores.json").write_text(json.dumps({"meta": meta, "rows": t["rows"]}))
        return str(d)

    def verdict(scores: str, out: str, *extra: str) -> int:
        return _in_process(["verdict", "--gates", str(gates), "--scores", scores, "--out", str(tmp_path / out),
                            *extra])

    assert verdict(score_dir("ok", 1001), "g") == 0                             # smoke run: seed 1 -> 1001
    v = json.loads((tmp_path / "g" / "verdict.json").read_text())
    assert v["seeds"] == [1] and v["seeds_passed"] == [1] and v["verdict"] == "FAIL"   # 1 of the 3 seeds required
    assert verdict(score_dir("local", 1001, local="partner_rules.toml"), "h") == 2
    assert verdict(score_dir("wrongseed", 1002), "i") == 2                      # scored with another seed
    short = score_dir("short", 1001, per_band=100)
    assert verdict(short, "j") == 2                                             # 100 games per band: refused
    assert verdict(short, "k", "--allow-short") == 0                            # sanity checks only


def test_standin_config_unchanged():                      # D14: [standin], [standin_gates] as pinned in Task 1
    text = (CONFIGS / "s2.toml").read_text()
    for name, sha in STANDIN_SHA256.items():
        assert hashlib.sha256(train_standin.table_text(text, name).encode()).hexdigest() == sha, name


def test_cap_stops_at_the_first_update(tmp_path):
    rc = _in_process(["--seed", "2", "--name", "capped", "--device", "cpu", "--num-games-override", "8",
                      "--timesteps-override", "200", "--cap-min-override", "0", "--eval-games", "4",
                      "--eval-max-steps", "40", "--runs-dir", str(tmp_path)])
    assert rc == 0
    res = json.loads((tmp_path / "capped" / "train_result.json").read_text())
    assert res["stopped_by_wall_clock_cap"] is True and res["timesteps_done"] == 32       # one update (rollouts 32)
    assert (tmp_path / "capped" / "agent.pt").exists() and res["evaluations"] == 2


def test_refuses_an_existing_run_folder(tmp_path):
    (tmp_path / "taken").mkdir()
    (tmp_path / "taken" / "interface.toml").write_text("x = 1\n")
    assert _in_process(["--seed", "1", "--name", "taken", "--device", "cpu", "--runs-dir", str(tmp_path)]) == 2


def _torch_world(n, m, params, device):
    from svg_training.models.rigid_body import TorchRigidBodyWorld
    return TorchRigidBodyWorld(n, m, params.airframe, params.physics_dt_s, device)


def test_standin_physics_smoke_torch_world(tmp_path):
    from svg_training.models.rigid_body import TORCH_WORLD_LABEL
    rc = _in_process(["--seed", "1", "--name", "phys", "--motion", "physics", "--device", "cpu",
                      "--num-games-override", "16", "--timesteps-override", "100", "--eval-games", "8",
                      "--eval-max-steps", "40", "--runs-dir", str(tmp_path)], world_factory=_torch_world)
    assert rc == 0
    run = tmp_path / "phys"
    assert (run / "agent.pt").exists()
    meta = tomllib.loads((run / "interface.toml").read_text())
    assert meta["motion"] == f"physics/{TORCH_WORLD_LABEL}" and meta["motion"].startswith("physics/torch-reference")
    assert meta["preset"] == "physics" and meta["world"] == TORCH_WORLD_LABEL
    ph = meta["physics"]
    assert "SIM-ONLY" in ph["yaw_rate_gains"]                     # the owner's ruling, named in the interface file
    assert ph["physics_params_sha256"] == hashlib.sha256(
        (ROOT / "params" / "starling_physics_v0.toml").read_bytes()).hexdigest()
    res = json.loads((run / "train_result.json").read_text())
    assert res["timesteps_done"] == 100 and res["nonfinite_count"] == 0 and res["upset_training_games"] == 0
    check_strategy(SkrlPolicyStrategy(run, 8, "cpu"), SvgGame(CFG, 8, 2, 1, device="cpu"))


def test_standin_physics_refuses_torch_world_for_runs(tmp_path):
    # without the test hook: no world -> refused in-process; from the command line it needs --headless (IsaacWorld)
    assert _in_process(["--seed", "1", "--name", "p", "--motion", "physics", "--device", "cpu",
                        "--runs-dir", str(tmp_path)]) == 2
    r = _run_cli("--seed", "1", "--name", "p", "--motion", "physics", "--runs-dir", str(tmp_path), timeout=120)
    assert r.returncode == 2 and "--headless" in r.stderr, r.stderr[-2000:]
    assert not (tmp_path / "p").exists()


def test_evaluation_leaves_the_training_world_unchanged():
    """Physics: the evaluation game flies on a slice of the training world; with the world's state saved and
    written back, the training game continues bit for bit as if no evaluation had run (torch reference world)."""
    from svg_training.core.physics_layer import load_game_physics_params

    cfg = CFG.replace(**{"starling.enabled": True, "starling.backend": "physics", "starling.filter_iterations": 50})
    p = load_game_physics_params(cfg)

    def setup():
        world = _torch_world(6, 3, p, "cpu")
        sl = train_standin.WorldSlice(world, 3)
        ev = SvgGame(cfg, 3, 2, 1, device="cpu", seed=9, world=sl)
        tr = SvgGame(cfg, 6, 2, 1, device="cpu", seed=4, world=world)
        return world, sl, ev, tr

    gen = torch.Generator().manual_seed(0)
    acts = [{"guard": torch.rand(6, 2, 4, generator=gen) * 2 - 1, "strike": torch.rand(6, 1, 4, generator=gen) * 2 - 1}
            for _ in range(8)]
    out = []
    for with_eval in (False, True):
        world, sl, ev, tr = setup()
        for a in acts[:4]:
            tr.step(a)
        if with_eval:
            snap = sl.snapshot()
            ev.reset()
            for _ in range(5):
                ev.step({"guard": torch.ones(3, 2, 4) * 0.7, "strike": -torch.ones(3, 1, 4) * 0.7})
            assert not torch.equal(world.state()[0], snap[0])        # the evaluation did move the bodies
            sl.restore(snap)
        for a in acts[4:]:
            tr.step(a)
        out.append([t.clone() for t in world.state()] + [tr.pos_m.clone()])
    for x, y in zip(*out):
        assert torch.equal(x, y)


def test_parked_games_stay_put_during_evaluation():
    """While the evaluation flies on the slice, the other games are parked level, at rest, held by a hover wrench."""
    from svg_training.core.physics_layer import load_game_physics_params

    cfg = CFG.replace(**{"starling.enabled": True, "starling.backend": "physics", "starling.filter_iterations": 50})
    p = load_game_physics_params(cfg)
    world = _torch_world(6, 3, p, "cpu")
    sl = train_standin.WorldSlice(world, 2)
    ev = SvgGame(cfg, 2, 2, 1, device="cpu", seed=9, world=sl)
    tr = SvgGame(cfg, 6, 2, 1, device="cpu", seed=4, world=world)
    for _ in range(5):
        tr.step({"guard": torch.ones(6, 2, 4) * 0.5, "strike": torch.ones(6, 1, 4) * 0.5})
    snap = sl.snapshot()
    ev.reset()
    for _ in range(200):                                                     # 10 s of game time
        ev.step({"guard": torch.zeros(2, 2, 4), "strike": torch.ones(2, 1, 4)})
    pos = world.state()[0]
    assert (pos[2:] - snap[0][2:]).abs().max() < 1e-3                        # parked: they did not fall
    sl.restore(snap)
    assert all(torch.equal(a, b) for a, b in zip(world.state(), snap))


def test_mix_slices():
    assert train_standin.mix_slices({"a": 0.5, "b": 0.5}, 4096) == [("a", slice(0, 2048)), ("b", slice(2048, 4096))]
    with pytest.raises(ValueError):
        train_standin.mix_slices({"a": 0.7, "b": 0.5}, 10)


def test_refuses_another_skrl_major_version(tmp_path, monkeypatch):
    import importlib.metadata
    monkeypatch.setattr(importlib.metadata, "version", lambda name: "1.4.3")     # the container image's skrl
    assert "1.4.3" in train_standin.skrl_version_problem()
    assert _in_process(["--seed", "1", "--name", "old", "--device", "cpu", "--runs-dir", str(tmp_path)]) == 2
    assert not (tmp_path / "old").exists()


@pytest.mark.isaac
@pytest.mark.skipif(train_standin.skrl_version_problem() is not None,
                    reason="needs skrl 2.x: run on the host (conda env_isaaclab), not in the container")
def test_standin_physics_isaac_smoke(tmp_path):
    """HOST, after scripts/isaac_preflight.sh: SVG_ISAAC_TESTS=1 PYTHONPATH=source
    ~/miniconda3/envs/env_isaaclab/bin/python -m pytest -q -m isaac tests/test_train_standin.py"""
    r = _run_cli("--headless", "--seed", "1", "--name", "isaac", "--motion", "physics", "--num-games-override", "16",
                 "--timesteps-override", "64", "--eval-games", "8", "--runs-dir", str(tmp_path), timeout=1800)
    # full-length evaluations: the parked training games are held for up to 60 s of game time
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-3000:]
    meta = tomllib.loads((tmp_path / "isaac" / "interface.toml").read_text())
    assert meta["motion"] == "physics/isaaclab-2.3.2" and "SIM-ONLY" in meta["physics"]["yaw_rate_gains"]
    res = json.loads((tmp_path / "isaac" / "train_result.json").read_text())
    assert res["timesteps_done"] == 64 and res["nonfinite_count"] == 0
