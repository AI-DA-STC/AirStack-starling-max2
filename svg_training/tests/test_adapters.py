"""Training-library adapters (skrl multi-agent, Gymnasium single-team vector) and the partner guide (S2 Task 9).

CPU only, small N. The worked example in docs/PLUG_IN.md is executed here too, so the guide cannot rot."""
import math
import os
import pathlib
import re
import subprocess
import sys

import pytest
import torch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
sys.path.insert(0, str(ROOT / "tests"))
from _proc import child_env, child_python  # noqa: E402
from svg_training.core.game import SCENARIOS, SvgGame  # noqa: E402
from svg_training.core.game_config import TICK_S, load_game_cfg  # noqa: E402
from svg_training.core.observations import OBS_DIM, STATE_DIM, ObsView  # noqa: E402
from svg_training.envs.gym_adapter import SvgTeamVectorEnv  # noqa: E402
from svg_training.envs.skrl_adapter import SvgSkrlEnv, skrl_kwargs_defaults  # noqa: E402
from svg_training.opponents.scripted import make_strategy  # noqa: E402

CFG = load_game_cfg(use_local=False)[0]
N = 16
V = ObsView()


def game_2v1(band=None, seed=0):
    return SvgGame(CFG, N, 2, 1, device="cpu", seed=seed, band=band)


def straight(n=N):
    return make_strategy("strike_straight", "strike", CFG, n, "cpu", seed=0)


# ------------------------------------------------------------------ skrl
def test_skrl_env_shapes_and_spaces():
    env = SvgSkrlEnv(game_2v1(), ("guard",), {"strike": straight()})
    assert env.possible_agents == ["guard_0", "guard_1"] and env.agents == env.possible_agents
    assert env.num_envs == N and env.num_agents == 2
    for a in env.possible_agents:
        assert env.observation_space(a).shape == (OBS_DIM,)
        box = env.action_space(a)
        assert box.shape == (4,) and float(box.low.min()) == -1.0 and float(box.high.max()) == 1.0
        assert env.state_space(a).shape == (STATE_DIM,)
    assert env.central_state_space.shape == (STATE_DIM,)
    obs, info = env.reset()
    assert info["opponents"] == {"strike": "StrikeStraight"}
    assert set(obs) == {"guard_0", "guard_1"} and obs["guard_0"].shape == (N, OBS_DIM)
    st = env.state()
    assert set(st) == set(env.possible_agents) and st["guard_0"].shape == (N, STATE_DIM)
    acts = {a: torch.zeros(N, 4) for a in env.possible_agents}
    obs, rew, term, trunc, info = env.step(acts)
    for a in env.possible_agents:
        assert obs[a].shape == (N, OBS_DIM)
        assert rew[a].shape == (N, 1) and rew[a].is_floating_point()
        assert term[a].shape == (N, 1) and term[a].dtype == torch.bool
        assert trunc[a].shape == (N, 1) and trunc[a].dtype == torch.bool and not bool(trunc[a].any())
    assert info["outcome"].shape == (N,) and info["opponents"] == {"strike": "StrikeStraight"}
    # both teams trained: names Guard first, no opponent needed
    both = SvgSkrlEnv(game_2v1(), ("strike", "guard"))
    assert both.possible_agents == ["guard_0", "guard_1", "strike_0"]


def test_skrl_env_checks_opponents():
    with pytest.raises(ValueError, match="needs an opponent"):
        SvgSkrlEnv(game_2v1(), ("guard",))
    with pytest.raises(ValueError, match="plays"):
        SvgSkrlEnv(game_2v1(), ("guard",), {"strike": make_strategy("guard_field", "guard", CFG, N, "cpu", 0)})
    with pytest.raises(ValueError, match="cannot also have"):
        SvgSkrlEnv(game_2v1(), ("guard", "strike"), {"strike": straight()})


def test_skrl_reward_and_done_follow_the_game():
    """Lab games, Strike straight, Guard standing: on every step the adapter's reward/terminated equal the game's
    own, read from a twin game driven directly with the same seed."""
    env = SvgSkrlEnv(game_2v1(band=0, seed=5), ("guard",), {"strike": straight()})
    twin, opp = game_2v1(band=0, seed=5), straight()
    env.reset()
    o = twin.reset()
    opp.reset(torch.ones(N, dtype=torch.bool))
    zero = torch.zeros(N, 4)
    seen_done = False
    for _ in range(400):
        _, rew, term, _, info = env.step({"guard_0": zero, "guard_1": zero})
        out = twin.step({"guard": torch.zeros(N, 2, 4), "strike": opp.act(o["strike"])})
        opp.reset(out.done)
        o = out.obs
        assert torch.equal(term["guard_1"][:, 0], out.done)
        assert torch.equal(rew["guard_0"][:, 0], out.reward["guard"][:, 0])
        assert torch.equal(info["outcome"], out.outcome)
        seen_done |= bool(out.done.any())
    assert seen_done


def _ippo(env, memory_size=16):
    from skrl.memories.torch import RandomMemory
    from skrl.models.torch import DeterministicMixin, GaussianMixin, Model
    from skrl.multi_agents.torch.ippo import IPPO, IPPO_CFG

    class Policy(GaussianMixin, Model):
        def __init__(self, obs_space, act_space, device):
            Model.__init__(self, observation_space=obs_space, action_space=act_space, device=device)
            GaussianMixin.__init__(self, clip_actions=True)
            self.net = torch.nn.Sequential(torch.nn.Linear(OBS_DIM, 16), torch.nn.Tanh(), torch.nn.Linear(16, 4))
            self.log_std = torch.nn.Parameter(torch.zeros(4))

        def compute(self, inputs, role=""):
            return self.net(inputs["observations"]), {"log_std": self.log_std}

    class Value(DeterministicMixin, Model):
        def __init__(self, obs_space, act_space, device):
            Model.__init__(self, observation_space=obs_space, action_space=act_space, device=device)
            DeterministicMixin.__init__(self)
            self.net = torch.nn.Sequential(torch.nn.Linear(OBS_DIM, 16), torch.nn.Tanh(), torch.nn.Linear(16, 1))

        def compute(self, inputs, role=""):
            return self.net(inputs["observations"]), {}

    dev = env.device
    models = {a: {"policy": Policy(env.observation_space(a), env.action_space(a), dev),
                  "value": Value(env.observation_space(a), env.action_space(a), dev)} for a in env.possible_agents}
    memories = {a: RandomMemory(memory_size=memory_size, num_envs=env.num_envs, device=dev)
                for a in env.possible_agents}
    cfg = IPPO_CFG(rollouts=memory_size, learning_epochs=2, mini_batches=2,
                   experiment={"write_interval": 0, "checkpoint_interval": 0},
                   **skrl_kwargs_defaults(env.possible_agents))
    return IPPO(possible_agents=env.possible_agents, models=models, memories=memories,
                observation_spaces=env.observation_spaces, state_spaces=env.state_spaces,
                action_spaces=env.action_spaces, device=dev, cfg=cfg)


def test_skrl_ippo_runs_64_timesteps():
    from skrl.trainers.torch import SequentialTrainer

    torch.manual_seed(0)
    env = SvgSkrlEnv(game_2v1(), ("guard",), {"strike": straight()})
    agent = _ippo(env)
    before = {a: [p.detach().clone() for p in agent.policies[a].parameters()] for a in env.possible_agents}
    trainer = SequentialTrainer(env=env, agents=agent, cfg={"timesteps": 64, "headless": True,
                                                            "disable_progressbar": True,
                                                            "close_environment_at_exit": False})
    trainer.train()
    for a in env.possible_agents:
        for tag in (f"Loss / Policy loss ({a})", f"Loss / Value loss ({a})"):
            losses = agent.tracking_data[tag]
            assert len(losses) == 64 // 16, (tag, losses)
            assert all(math.isfinite(x) for x in losses), (tag, losses)
        after = list(agent.policies[a].parameters())
        assert any(not torch.equal(b, c) for b, c in zip(before[a], after)), f"{a}: network never changed"
    assert agent.policies["guard_0"] is not agent.policies["guard_1"]      # one network per Guard name


# ------------------------------------------------------------------ Gymnasium
def test_gym_vector_env_api():
    import gymnasium

    game = game_2v1()
    env = SvgTeamVectorEnv(game, "guard", straight())
    assert isinstance(env, gymnasium.vector.VectorEnv)
    assert env.metadata["autoreset_mode"] == gymnasium.vector.AutoresetMode.SAME_STEP
    assert env.num_envs == N
    obs, info = env.reset(seed=3)
    obs2, _ = env.reset(seed=3)
    assert torch.equal(obs, obs2)
    assert info["opponent"] == "StrikeStraight"
    assert env.single_action_space.shape == (8,) and obs.shape == (16, 2 * OBS_DIM)
    assert env.single_observation_space.shape == (2 * OBS_DIM,)
    assert env.action_space.shape == (N, 8) and env.observation_space.shape == (N, 2 * OBS_DIM)
    assert float(env.single_action_space.low.min()) == -1.0 and float(env.single_action_space.high.max()) == 1.0
    # observation = drone 0's OBS_DIM (71) floats then drone 1's
    assert torch.equal(obs.reshape(N, 2, OBS_DIM), game._obs()["guard"])
    o, r, term, trunc, info = env.step(torch.zeros(N, 8))
    assert o.shape == (N, 2 * OBS_DIM) and r.shape == (N,) and term.shape == (N,) and trunc.shape == (N,)
    assert term.dtype == torch.bool and trunc.dtype == torch.bool and not bool(trunc.any())
    assert info["outcome"].shape == (N,) and info["opponent"] == "StrikeStraight"
    assert o.device == r.device == term.device == torch.device("cpu")
    # the Strike team's view: one drone, OBS_DIM (71) floats
    s_env = SvgTeamVectorEnv(game_2v1(), "strike", make_strategy("guard_field", "guard", CFG, N, "cpu", 0))
    so, _ = s_env.reset(seed=1)
    assert so.shape == (N, OBS_DIM) and s_env.single_action_space.shape == (4,)
    with pytest.raises(ValueError, match="must play"):
        SvgTeamVectorEnv(game_2v1(), "guard", make_strategy("guard_field", "guard", CFG, N, "cpu", 0))


def test_gym_autoreset_same_step():
    """Lab-sized games, Strike straight, Guard zero: on the step a game ends, the returned observation is
    already the new game's (full time left, the game's fresh state), and the outcome is the ended game's."""
    game = game_2v1(band=0, seed=7)
    env = SvgTeamVectorEnv(game, "guard", straight())
    env.reset(seed=7)
    full_s = game.ticks * TICK_S
    zero = torch.zeros(N, 8)
    for k in range(game.ticks + 5):
        obs, rew, term, _, info = env.step(zero)
        if bool(term.any()):
            break
    assert bool(term.any()), "no lab game ended"
    o = obs.reshape(N, 2, OBS_DIM)
    t_left = o[..., V.time_left]
    assert torch.allclose(t_left[term], torch.full_like(t_left[term], full_s))          # new games
    if k + 1 < game.ticks:
        assert bool((t_left[~term] < full_s).all())                                      # still running
    assert torch.equal(o, game._obs()["guard"].reshape(N, 2, OBS_DIM))                   # = the game's current state
    assert bool((info["outcome"][term] > 0).all()) and bool((info["outcome"][~term] == 0).all())
    assert bool((info["end_step"][term] == k + 1).all())
    assert bool((rew[term] != 0).all()) and bool((rew[~term] == 0).all())               # terminal +-1, no shaping


# ------------------------------------------------------------------ rules shared by both
def test_adapters_refuse_scenarios():
    sc = SvgGame(CFG, 4, 1, 1, device="cpu", scenario=SCENARIOS["lab4_open"])
    opp = make_strategy("strike_straight", "strike", CFG, 4, "cpu", 0)
    with pytest.raises(ValueError, match="scenario"):
        SvgSkrlEnv(sc, ("guard",), {"strike": opp})
    with pytest.raises(ValueError, match="scenario"):
        SvgTeamVectorEnv(sc, "guard", opp)


def test_core_imports_no_training_library():
    """Re-run of Task 5's test now that the adapters import skrl and gymnasium: the core, the strategy contract
    and the scripted opponents still import neither."""
    code = ("import svg_training.core.game, svg_training.core.strategy, svg_training.core.play, "
            "svg_training.core.metrics, svg_training.opponents, svg_training.envs, sys; "
            "assert not {'skrl', 'gymnasium', 'isaaclab'} & set(sys.modules), "
            "sorted({'skrl', 'gymnasium', 'isaaclab'} & set(sys.modules))")
    r = subprocess.run([child_python(), "-c", code], env=child_env(str(ROOT / "source")), capture_output=True,
                       text=True)
    assert r.returncode == 0, r.stderr
    # and the adapters do bring their library in (so the test above means something)
    code2 = ("import svg_training.envs.gym_adapter, sys; assert 'gymnasium' in sys.modules; "
             "assert 'skrl' not in sys.modules")
    r = subprocess.run([child_python(), "-c", code2], env=child_env(str(ROOT / "source")), capture_output=True,
                       text=True)
    assert r.returncode == 0, r.stderr


# ------------------------------------------------------------------ the partner guide runs
GUIDE = ROOT / "docs" / "PLUG_IN.md"
_BLOCK = re.compile(r"```(python|bash)\n(.*?)```", re.S)


def _guide_blocks():
    """[(lang, code)] of the guide's fenced blocks marked to run (first line '# file: <name>' or '# run')."""
    out = []
    for lang, code in _BLOCK.findall(GUIDE.read_text()):
        first = code.splitlines()[0] if code.strip() else ""
        if first.startswith("# file:") or first.startswith("# run"):
            out.append((lang, code))
    return out


def test_plug_in_guide_example_runs(tmp_path):
    """Writes the guide's '# file:' blocks into a tmp folder, runs its '# run' Python blocks there (CPU), and
    runs its score.py commands there with tiny settings (CPU, 8 games, lab band, pure rules). The repo's
    configs/local/ is never read: the guide's code uses use_local=False and score.py gets --no-local. The second
    score.py command loads the networks the skrl block saved (my_ippo:TrainedGuard, from the checkpoint)."""
    blocks = _guide_blocks()
    files = [c for _, c in blocks if c.startswith("# file:")]
    runs = [(lang, c) for lang, c in blocks if c.startswith("# run")]
    assert files and any(lang == "python" for lang, _ in runs) and any(lang == "bash" for lang, _ in runs)
    for code in files:
        name = code.splitlines()[0].split(":", 1)[1].strip()
        (tmp_path / name).write_text(code)
    env = child_env(f"{ROOT / 'source'}{os.pathsep}{tmp_path}")
    env["CUDA_VISIBLE_DEVICES"] = ""          # the guide's examples pick the CPU when no GPU is visible
    scored = []
    for b, (lang, code) in enumerate(runs):
        if lang == "python":
            script = tmp_path / "block.py"
            script.write_text(code)
            r = subprocess.run([child_python(), str(script)], cwd=tmp_path, env=env, capture_output=True, text=True,
                               timeout=600)
            assert r.returncode == 0, f"guide block failed:\n{code}\n--- stderr\n{r.stderr[-3000:]}"
        else:
            cmd = " ".join(line.rstrip("\\").strip() for line in code.splitlines()[1:] if line.strip())
            assert cmd.startswith("PYTHONPATH=source:. python scripts/score.py"), cmd
            args = cmd.split()[3:]
            args = [a for a in args if not a.startswith("runs/")]
            i = args.index("--out")
            del args[i:i + 1]
            out = tmp_path / f"score_out_{b}"
            # later options win: CPU, 8 games, lab band, pure rules only (the Starling layer is tested in
            # test_score.py on a shortened game file)
            args += ["--device", "cpu", "--games-per-band", "8", "--bands", "lab", "--presets", "pure",
                     "--no-local", "--out", str(out)]
            r = subprocess.run([child_python(), str(ROOT / "scripts" / "score.py"), *args], cwd=tmp_path, env=env,
                               capture_output=True, text=True, timeout=600)
            assert r.returncode == 0, r.stderr[-3000:]
            scored.append((out / "scores.md").read_text())
    assert (tmp_path / "my_ippo_guard.pt").is_file()                       # the skrl block saved its networks
    assert any("my_guard:MyGuard" in t for t in scored)
    assert any("my_ippo:TrainedGuard" in t for t in scored)                # scored from the saved checkpoint


def test_plug_in_guide_obs_table_matches_obsview():
    """The guide's observation table names the same index ranges as ObsView."""
    text = GUIDE.read_text()
    for idx in ("0–2", "3–5", "6–7", "8", "9", "10", "11", "12", "13–19", "48–54", "62–68", "69–70"):
        assert f"| {idx} |" in text, idx
    assert V.own_pos == slice(0, 3) and V.own_vel == slice(3, 6) and V.sin_cos_yaw == slice(6, 8)
    assert (V.zone_radius, V.arena_half, V.time_left, V.team, V.alive) == (8, 9, 10, 11, 12)
    assert V.slot(0) == slice(13, 20) and V.slot(5) == slice(48, 55) and V.slot(7) == slice(62, 69)
    assert V.zone_centre == slice(69, 71) and OBS_DIM == 71 and STATE_DIM == 61
    assert "| 69–70 | zone centre x, y from the arena centre (m)" in text and "[N, 61]" in text
    assert "71 numbers" in text and "69 floats" not in text


def test_plug_in_flowchart_script_runs(tmp_path):
    out = tmp_path / "flow.png"
    r = subprocess.run([child_python(), str(ROOT / "scripts" / "make_s2_plug_in_flowchart.py"), str(out)],
                       env=child_env(str(ROOT / "source")), capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert out.stat().st_size > 10_000


def test_s2b_flowchart_script_runs(tmp_path):
    """docs/S2B_RESULTS.md figure 1 is made by a committed script (STANDARDS §11)."""
    out = tmp_path / "s2b_flow.png"
    r = subprocess.run([child_python(), str(ROOT / "scripts" / "make_s2b_flowchart.py"), str(out)],
                       env=child_env(str(ROOT / "source")), capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert out.stat().st_size > 10_000
    assert "figures/s2b_flow.png" in (ROOT / "docs" / "S2B_RESULTS.md").read_text()


def test_adapter_modules_have_no_host_calls():
    """Static scan, as tests/test_game_core.py does for the game: no host reads or NumPy in the adapters."""
    for f in ("skrl_adapter", "gym_adapter"):
        src = (ROOT / "source" / "svg_training" / "envs" / f"{f}.py").read_text()
        assert not re.search(r"\.(item|cpu|numpy|tolist)\(|import numpy|nonzero\(", src), f


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA only")
def test_adapter_steps_run_under_sync_debug_error():
    """Both adapters' step (with a scripted opponent inside) make no host sync; short games so the auto-reset
    runs often."""
    cfg = CFG.replace(**{"dropout_fraction": 0.2, "rules.game_steps": 40})
    n = 256
    opp = make_strategy("strike_flank", "strike", cfg, n, "cuda", 0)
    skrl_env = SvgSkrlEnv(SvgGame(cfg, n, 3, 2, device="cuda", seed=1), ("guard",), {"strike": opp})
    gym_env = SvgTeamVectorEnv(SvgGame(cfg, n, 3, 2, device="cuda", seed=2), "guard",
                               make_strategy("strike_straight", "strike", cfg, n, "cuda", 0))
    skrl_env.reset()
    gym_env.reset(seed=2)
    acts = {a: torch.rand(n, 4, device="cuda") * 2 - 1 for a in skrl_env.possible_agents}
    flat = torch.rand(n, 12, device="cuda") * 2 - 1
    skrl_env.step(acts)
    gym_env.step(flat)
    torch.cuda.set_sync_debug_mode("error")
    try:
        d1 = torch.zeros(n, dtype=torch.bool, device="cuda")
        d2 = torch.zeros_like(d1)
        for _ in range(100):
            _, _, term, _, _ = skrl_env.step(acts)
            skrl_env.state()
            d1 |= term["guard_0"][:, 0]
            _, _, t2, _, _ = gym_env.step(flat)
            d2 |= t2
    finally:
        torch.cuda.set_sync_debug_mode(0)
    assert bool(d1.all()) and bool(d2.all())                     # every game auto-reset at least once


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA only")
@pytest.mark.parametrize("starling", [False, True])
def test_strike_team_against_scripted_guards_under_sync_debug_error(starling):
    """A Strike team trained through either adapter against each scripted Guard strategy (opponents/scripted.py)
    makes no host sync in the step; short games so the auto-reset runs often."""
    cfg = CFG.replace(**{"dropout_fraction": 0.2, "rules.game_steps": 40})
    if starling:
        cfg = cfg.replace(**{"starling.enabled": True, "starling.filter_iterations": 20,
                             "starling.filter_check_every": 0})
    n, steps = 128, (60 if starling else 100)
    for k, gs in enumerate(("guard_mark_edge", "guard_mark_inside", "guard_field", "guard_mirror")):
        skrl_env = SvgSkrlEnv(SvgGame(cfg, n, 5, 3, device="cuda", seed=k), ("strike",),
                              {"guard": make_strategy(gs, "guard", cfg, n, "cuda", 101)})
        gym_env = SvgTeamVectorEnv(SvgGame(cfg, n, 5, 3, device="cuda", seed=10 + k), "strike",
                                   make_strategy(gs, "guard", cfg, n, "cuda", 101))
        skrl_env.reset()
        gym_env.reset(seed=10 + k)
        acts = {a: torch.rand(n, 4, device="cuda") * 2 - 1 for a in skrl_env.possible_agents}
        flat = torch.rand(n, 12, device="cuda") * 2 - 1
        skrl_env.step(acts)
        gym_env.step(flat)
        torch.cuda.set_sync_debug_mode("error")
        try:
            d1 = torch.zeros(n, dtype=torch.bool, device="cuda")
            d2 = torch.zeros_like(d1)
            for _ in range(steps):
                _, _, term, _, _ = skrl_env.step(acts)
                d1 |= term["strike_0"][:, 0]
                _, _, t2, _, _ = gym_env.step(flat)
                d2 |= t2
        finally:
            torch.cuda.set_sync_debug_mode(0)
        assert bool(d1.all()) and bool(d2.all()), gs              # every game auto-reset at least once
