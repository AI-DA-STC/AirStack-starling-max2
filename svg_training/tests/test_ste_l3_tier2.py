"""STE phase L3, slice 3, step 5: the skills route in tier 2 (design note ste_learning/drafts/L3_SLICE3_DESIGN.md §3 and
its revision; lead's answer 4: the Guard-side L0.13 arms and the dispatch-equality tests only).

* ``ste/tier2_train.load_gates`` accepts optional ``[players]``, ``[learner]`` and ``[pool]`` (None / velocity / off by
  default); the L0.13 gate file of record loads unchanged (its sha256); slice 1's flat modes are still refused.
* On the CPU reference world (tier 2 in the CPU tests): the dispatch gives each script's own command on tier-2
  observations; a fixed two-level team replays the tier-2 script cells game for game; training = scoring on tier 2.
* The L0.13 driver, ``--dry-cpu``, both arms with a two-level gate file: every control passes (the untrained team =
  the first Guard drone skill = the parked Guard), snapshots carry the skill lists, t2 reads t1's networks.
No Isaac run. CPU only."""
import hashlib
import json
import sys

import numpy as np
import pytest
import torch

from svg_training.core.physics_layer import load_game_physics_params
from svg_training.opponents.scripted import make_strategy
from svg_training.ste import exploit, exploit_train, shared, skills, tier2_train as T

from _ste_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import ste_tier2_l013 as driver  # noqa: E402

HOLD = 12
# sha256 of configs/ste_l013/gates.toml as committed (development cef8d0ee, 24 Nov 2026): the file of record
L013_GATES_SHA256 = hashlib.sha256(T.GATES_FILE.read_bytes()).hexdigest()
PLAYERS = """
[players]
guards = ["guard_parked_centre", "guard_parked_ring", "guard_mark_edge", "guard_mirror", "guard_field"]
strikes = ["strike_straight", "strike_flank", "strike_high", "strike_low", "strike_sacrifice", "strike_converge"]
"""
TWO_LEVEL = """
[learner]
action = "skills"
choice = "two_level"

[learner.team_strategies]
strike = ["strike_sacrifice", "strike_converge"]
guard = ["guard_parked_ring", "guard_field"]

[learner.drone_skills]
strike = ["strike_straight", "strike_flank", "strike_high", "strike_low"]
guard = ["guard_parked_centre", "guard_mark_edge", "guard_mirror"]

[learner.entropy_scale]
team = 0.01
drone = 0.01
"""
SPEC = skills.learner_spec({"action": "skills", "choice": "two_level",
                            "team_strategies": {"strike": ["strike_sacrifice", "strike_converge"],
                                                "guard": ["guard_parked_ring", "guard_field"]},
                            "drone_skills": {"strike": ["strike_straight", "strike_flank", "strike_high",
                                                        "strike_low"],
                                             "guard": ["guard_parked_centre", "guard_mark_edge", "guard_mirror"]},
                            "entropy_scale": {"team": 0.01, "drone": 0.01}})


@pytest.fixture(scope="module")
def gates():
    return T.load_gates()


@pytest.fixture(scope="module")
def ref(gates):
    return exploit.load_reference(exploit.ROOT / gates.reference["file"])


def write(tmp_path, text, name="g.toml"):
    p = tmp_path / name
    p.write_text(text)
    return p


# ================================================================================================ the gate file
def test_the_l013_gate_file_of_record_loads_unchanged(gates):
    import subprocess
    committed = subprocess.run(["git", "-C", str(T.ROOT), "show", "cef8d0ee:svg_training/configs/ste_l013/gates.toml"],
                               capture_output=True, check=True).stdout
    assert hashlib.sha256(committed).hexdigest() == L013_GATES_SHA256 == gates.sha256
    assert gates.players is None and gates.learner == skills.learner_spec(None) and gates.pool == {"enabled": False}


def test_a_two_level_tier2_gate_file_loads(tmp_path):
    g = T.load_gates(write(tmp_path, T.GATES_FILE.read_text() + PLAYERS + TWO_LEVEL))
    assert g.learner == SPEC and g.players["guards"][0] == "guard_parked_centre"
    assert g.learner.drone_skills["guard"][0] == g.run["parked"]


@pytest.mark.parametrize("extra,why", [
    (TWO_LEVEL, "players"),                                                         # two-level without [players]
    (PLAYERS + '\n[learner]\naction = "skills"\nchoice = "team"\n', "not wired"),     # slice 1's flat modes
    (PLAYERS + TWO_LEVEL + "\n[pool]\nenabled = true\nseed = 150001\n", "pool"),    # the pool: not in the L0.13 arms
    (PLAYERS + TWO_LEVEL.replace('guard = ["guard_parked_ring", "guard_field"]',
                                 'guard = ["guard_parked_centre", "guard_parked_ring"]')
     .replace('guard = ["guard_parked_centre", "guard_mark_edge", "guard_mirror"]',
              'guard = ["guard_mark_edge", "guard_mirror", "guard_field"]'), "parked"),
    (PLAYERS.replace('"guard_field"]', '"guard_field", "guard_mark_inside"]') + TWO_LEVEL, "tier 1"),
])
def test_bad_tier2_tables_are_refused(tmp_path, extra, why):
    with pytest.raises(ValueError, match=why):
        T.load_gates(write(tmp_path, T.GATES_FILE.read_text() + extra))


def test_a_disabled_pool_table_loads(tmp_path):
    g = T.load_gates(write(tmp_path, T.GATES_FILE.read_text() + "\n[pool]\nenabled = false\nseed = 150001\n"))
    assert g.pool == {"enabled": False, "seed": 150001}


# ================================================================================================ tier 2, reference world
def _world(cfg, n):
    return T.torch_world_factory(n, 6, load_game_physics_params(cfg), "cpu")


def test_the_dispatch_gives_each_scripts_own_command_on_tier2_observations(gates):
    cfg = T.tier_cfg(gates, 2)
    n = 6
    game = exploit_train.TrainGame(cfg, n, 3, 3, device="cpu", seed=5, world=_world(cfg, n))
    obs = game.reset()
    g = make_strategy("guard_mark_edge", "guard", cfg, n, "cpu", 0)
    s = make_strategy("strike_straight", "strike", cfg, n, "cpu", 0)
    for _ in range(20):
        obs = game.step({"guard": g.act(obs["guard"]), "strike": s.act(obs["strike"])}).obs
    for side in ("guard", "strike"):
        d = skills.two_level_dispatch(SPEC, exploit.load_gates().players, side, cfg, n, "cpu", 0)
        for j, name in enumerate(d.names):
            own = make_strategy(name, side, cfg, n, "cpu", 0).act(obs[side])
            assert torch.equal(d.act(obs[side], torch.full(obs[side].shape[:2], j)), own), (side, name)


class HeadLogits(torch.nn.Module):
    def __init__(self, t, d, widths):
        super().__init__()
        self.t, self.d, self.widths = t, d, widths

    def forward(self, obs):
        out = obs.new_zeros(obs.shape[0], sum(self.widths))
        out[:, self.t] = 1.0
        out[:, self.widths[0] + self.d] = 1.0
        return out


class Composite:
    def __init__(self, side, names, cfg, n):
        self.team, self.name = side, "composite(" + ",".join(names) + ")"
        self.scripts = [make_strategy(nm, side, cfg, n, "cpu", 0) for nm in names]

    def reset(self, games):
        for s in self.scripts:
            s.reset(games)

    def act(self, obs):
        return torch.stack([s.act(obs)[:, m] for m, s in enumerate(self.scripts)], dim=1)


def test_a_fixed_two_level_guard_team_replays_the_tier2_script_cells(gates, ref):
    """Each team strategy and each uniform drone skill, and a sample of mixed "free" combinations, played as a fixed
    two-level Guard team on tier 2, equal the scripts (or the composite player) played on tier 2, game for game."""
    cfg = T.tier_cfg(gates, 2)
    n, ticks, opp = 4, 90, gates.run["opponent"]
    d = skills.two_level_dispatch(SPEC, {"guards": ["guard_parked_centre", "guard_parked_ring", "guard_mark_edge",
                                                    "guard_mirror", "guard_field"],
                                         "strikes": ["strike_straight"]}, "guard", cfg, n, "cpu", 0)
    ts, ds = SPEC.team_strategies["guard"], SPEC.drone_skills["guard"]
    heads = [(nm, [(t + 1, 0)] * 3) for t, nm in enumerate(ts)] + [(nm, [(0, k)] * 3) for k, nm in enumerate(ds)]
    mixed = [(0, 1, 2), (2, 2, 0), (1, 0, 1)]
    mine = {f"tl:{nm}": exploit.SkillTeam("guard", [HeadLogits(t, k, d.widths) for t, k in hh],
                                          [lambda o, train=False: o] * 3, d) for nm, hh in heads}
    mine.update({f"tl:{c}": exploit.SkillTeam("guard", [HeadLogits(0, k, d.widths) for k in c],
                                              [lambda o, train=False: o] * 3, d) for c in mixed})
    oracle = {f"comp:{c}": Composite("guard", [ds[k] for k in c], cfg, n) for c in mixed}
    cells = [(nm, opp) for nm in mine]
    pg = exploit.play_cells(cfg, "3v3", ref, cells, n, "cpu", ref.meta["seed"], ticks, hold_ticks=HOLD, players=mine,
                            world=_world(cfg, len(cells) * n))
    want_cells = [(nm, opp) for nm, _ in heads]
    want = exploit.play_cells(cfg, "3v3", ref, want_cells, n, "cpu", ref.meta["seed"], ticks,
                              world=_world(cfg, len(want_cells) * n))
    comp = exploit.play_cells(cfg, "3v3", ref, [(nm, opp) for nm in oracle], n, "cpu", ref.meta["seed"], ticks,
                              hold_ticks=1, players=oracle, world=_world(cfg, len(oracle) * n))
    for k in range(len(heads)):
        assert exploit.agreement(exploit.slice_cell(pg, k, n), exploit.slice_cell(want, k, n))["differ"] == 0, heads[k][0]
    for k in range(len(mixed)):
        got = exploit.slice_cell(pg, len(heads) + k, n)
        assert exploit.agreement(got, exploit.slice_cell(comp, k, n))["differ"] == 0, mixed[k]
    assert len({tuple(exploit.slice_cell(want, k, n)["end_step"]) for k in range(len(heads))}) > 1, "no power"


class _FixedTrainGame(exploit.FixedStartsGame):
    restart = exploit_train.TrainGame.restart


def test_training_equals_scoring_on_tier2(gates, ref):
    """The same scrambled two-level Guard networks from T44's starts on tier 2: (1) ``decision_env`` with skrl's
    logits (each head's argmax) and (2) ``play_cells`` with ``HeldPlayer`` + ``Learner.team()``: the same games."""
    cfg = T.tier_cfg(gates, 2)
    n, ticks, seed = 6, 120, 7
    players = {"guards": ["guard_parked_centre", "guard_parked_ring", "guard_mark_edge", "guard_mirror", "guard_field"],
               "strikes": ["strike_straight"]}
    small = exploit_train.TrainGame(cfg, 4, 3, 3, device="cpu", seed=seed, world=_world(cfg, 4))
    env = exploit_train.decision_env(small, HOLD, "guard", make_strategy(gates.run["opponent"], "strike", cfg, 4, "cpu",
                                                                         seed + 1), SPEC, players, seed)
    learner = exploit_train.Learner({**exploit.load_gates().trainer, "num_games": 4, "rollouts": 2,
                                     "learning_epochs": 1, "mini_batches": 1}, env, "cpu", seed=3)
    torch.manual_seed(5)
    with torch.no_grad():
        for a in learner.names:
            for p in learner.agent.policies[a].net.parameters():
                p.normal_(0.0, 0.5)
    game = _FixedTrainGame(cfg, 1, torch.as_tensor(ref.starts_m[:n]), torch.as_tensor(ref.start_miss[:n]), 3, 3, "cpu",
                           seed, world=_world(cfg, n))
    denv = exploit_train.decision_env(game, HOLD, "guard", make_strategy(gates.run["opponent"], "strike", cfg, n,
                                                                         "cpu", seed + 1), SPEC, players, seed)
    obs, _ = denv.reset()
    learner.agent.enable_training_mode(False)
    outcome = torch.zeros(n, dtype=torch.int8)
    end = torch.zeros(n, dtype=torch.long)
    done = torch.zeros(n, dtype=torch.bool)
    for d in range(ticks // HOLD):
        with torch.no_grad():
            _, out = learner.agent.act(obs, denv.state(), timestep=0, timesteps=1)
        obs, _, _, _, info = denv.step({a: denv.skills.greedy(out[a]["net_output"]) for a in learner.names})
        new = info["decision_ended"] & ~done
        outcome = torch.where(new, info["decision_outcome"], outcome)
        end = torch.where(new, d * HOLD + info["decision_end_tick"], end)
        done |= info["decision_ended"]
        if bool(done.all()):
            break
    cell = (exploit.EXPLOITER, gates.run["opponent"])
    pg = exploit.play_cells(cfg, "3v3", ref, [cell], n, "cpu", seed, ticks, learner=learner.team(), hold_ticks=HOLD,
                            world=_world(cfg, n))
    assert int(done.sum()) >= 1, "no game ended: no power"
    assert outcome.tolist() == pg["outcome"].tolist()
    assert end[done].tolist() == np.asarray(pg["end_step"])[done.numpy()].tolist()


# ================================================================================================ the L0.13 driver
TINY = {"num_games = 16384 ": "num_games = 16 ", "eval_games = 1000 ": "eval_games = 4 ",
        "curve_games = 256 ": "curve_games = 4 ", "ticks_cap = 2400 ": "ticks_cap = 120 ", "rollouts = 32": "rollouts = 2",
        "learning_epochs = 5": "learning_epochs = 1", "mini_batches = 4": "mini_batches = 1",
        "game_steps_per_run = 6_291_456 ": "game_steps_per_run = 576 ", "games = 4\n": "games = 2\n",
        "max_ticks = 600 ": "max_ticks = 120 "}


@pytest.fixture(scope="module")
def skills_arms(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("l3_tier2")
    mp = pytest.MonkeyPatch()
    mp.setenv(shared.SHARED_ENV, str(tmp / "shared"))
    mp.setenv(shared.LEGACY_LOGS_ENV, "")
    text = T.SMOKE_GATES_FILE.read_text()
    for old, new in TINY.items():
        assert old in text, old
        text = text.replace(old, new, 1)
    g = write(tmp, text + PLAYERS + TWO_LEVEL, "tiny_gates.toml")

    def arm(which, *extra):
        cap = str(T.load_gates(g).arms[which]["cap_h"])
        return driver.main(["--arm", which, "--gates", str(g), "--run-dir", str(tmp / which), "--cap-h", cap,
                            "--dry-cpu", *extra])
    assert arm("t1", "--no-videos") == 0
    assert arm("t2", "--t1-run", str(tmp / "t1")) == 0              # t2 makes its clips (the skills team)
    mp.undo()
    return {"gates": g, "t1": tmp / "t1", "t2": tmp / "t2"}


def test_both_arms_with_a_two_level_gate_file_pass_every_control(skills_arms):
    for a in ("t1", "t2"):
        controls = json.loads((skills_arms[a] / "controls.json").read_text())
        assert controls and all(v["status"] == "PASS" for v in controls.values()), (a, controls)
        tiers = (1,) if a == "t1" else (1, 2)
        for tier in tiers:
            assert f"ctl_untrained_is_first_skill_t{tier}" in controls
            assert f"ctl_untrained_is_still_t{tier}" not in controls
        res = json.loads((skills_arms[a] / "results.json").read_text())
        assert res["learner"]["choice"] == "two_level"


def test_the_snapshots_carry_the_skill_lists_and_t2_reads_t1s_networks(skills_arms):
    snaps = sorted((skills_arms["t1"] / "snapshots").glob("u*.pt"))
    assert snaps
    s = torch.load(snaps[-1], weights_only=False)
    assert set(s) == {"skills", "modules"} and s["skills"]["team_strategies"] == ["guard_parked_ring", "guard_field"]
    res = json.loads((skills_arms["t2"] / "results.json").read_text())
    assert res["videos"] and str(res["videos"][0]).startswith("videos/")
