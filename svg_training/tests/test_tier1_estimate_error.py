"""STE task L1.7: tier 1 (the fitted Starling layer) gets tier 2's estimate error (L1.1b), so quick experiments stay
comparable.

What is checked (CPU, small batches, made-up commands; parameter file real_exploratory_v0, exploratory):

- off (no ``[estimate_error]`` table, or the table with ``enabled = false``) builds nothing and plays the same game
  (the golden files ``tests/test_game_tag_off_golden.py`` and ``tests/test_command_chain.py`` cover "as before");
- the error is a first-order Gauss-Markov process per quantity and axis: stationary sigma, lag-1 autocorrelation
  exp(-dt / tau), drawn afresh from the stationary distribution at a reset;
- the PX4 model's feedback reads the estimate: a frozen position error e moves the hovering drone by -e when the
  commander reads the true position, and not at all when it reads the estimate (the switch);
- the game, the tags, the walls and the scoring read the true positions; the safety filter reads what the switch says;
- the game seed reaches the error (same seed same error, another seed another; ``reset(seed)`` = a fresh game);
- replay determinism: the same seed and the same commands play the same game, tick for tick;
- the study game files ``configs/ste_l1/base_err_{nominal,conservative}.toml`` differ from ``configs/ste_l011/base.toml``
  by the table only, and from each other by the two sigmas only.
"""
from __future__ import annotations

import math
import pathlib
import sys
import tomllib

import pytest
import torch
from torch import Tensor

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
from svg_training.core.game import SvgGame  # noqa: E402
from svg_training.core.game_config import EstimateErrorCfg, load_game_cfg  # noqa: E402
from svg_training.models import fitted  # noqa: E402
from svg_training.models.fitted import FittedResponse, load_params  # noqa: E402

PARAMS = ROOT / "params" / "real_exploratory_v0.toml"
BASE = ROOT / "configs" / "ste_l011" / "base.toml"
NOMINAL = ROOT / "configs" / "ste_l1" / "base_err_nominal.toml"
CONSERVATIVE = ROOT / "configs" / "ste_l1" / "base_err_conservative.toml"
SUB_DT = 0.01                     # the fitted model's sub-step (params [px4] model_dt_s)
TICK = 0.05


def base_cfg(**extra):
    cfg = load_game_cfg(BASE, local_dir=None, use_local=False)[0]
    return cfg.replace(**{"starling.filter_iterations": 50, **extra})      # 50 sweeps: fast CPU tests


def err_cfg(commander_reads="true", pos=(0.02, 0.5), vel=(0.03, 0.3), **extra):
    return base_cfg(**{"estimate_error.enabled": True, "estimate_error.pos_sigma_m": pos[0],
                       "estimate_error.pos_tau_s": pos[1], "estimate_error.vel_sigma_mps": vel[0],
                       "estimate_error.vel_tau_s": vel[1], "estimate_error.commander_reads": commander_reads,
                       **extra})


class Jiggle:
    """Seeded random commands from their own generator (never the game's)."""
    def __init__(self, n, k, seed):
        self.n, self.k, self.gen = n, k, torch.Generator().manual_seed(seed)

    def __call__(self):
        return torch.rand(self.n, self.k, 4, generator=self.gen) * 2 - 1


def play(game, ticks, seed=1):
    """Every output of ``ticks`` steps under seeded random commands, stacked."""
    g, s = Jiggle(game.num_games, game.guards, seed), Jiggle(game.num_games, game.strikes, seed + 100)
    rows = []
    for _ in range(ticks):
        out = game.step({"guard": g(), "strike": s()})
        rows.append(torch.cat((game.pos_m.flatten(1), game.vel_mps.flatten(1), game.alive.flatten(1).float(),
                               out.outcome[:, None].float(), out.reward["guard"].reshape(game.num_games, -1),
                               out.info["closest_cross_3d_m"][:, None], out.info["tagged"].flatten(1).float()),
                              dim=1))
    return torch.stack(rows)


def layer_error(game):
    """(position error, velocity error) the fitted model's feedback reads now, [N, M, 3] each."""
    m = game._starling.model
    return m.est_pos_m - m.pos_m, m.est_vel_mps - m.vel_mps


# ------------------------------------------------------------------------------------------------ off
def test_absent_table_is_off_and_builds_nothing():
    cfg = load_game_cfg(BASE, local_dir=None, use_local=False)[0]
    assert cfg.estimate_error == EstimateErrorCfg() and not cfg.estimate_error.enabled
    game = SvgGame(base_cfg(), 2, 3, 3, device="cpu", seed=3)
    assert game._starling.model.estimator is None
    assert torch.equal(game._starling.model.est_pos_m, game._starling.model.pos_m)


def test_table_present_but_disabled_is_the_same_game():
    """``enabled = false`` with other values: nothing else is read, the game is the same bit for bit."""
    off = SvgGame(base_cfg(), 3, 3, 3, device="cpu", seed=4)
    present = SvgGame(err_cfg(**{"estimate_error.enabled": False, "estimate_error.commander_reads": "estimate"}),
                      3, 3, 3, device="cpu", seed=4)
    assert present._starling.model.estimator is None
    assert torch.equal(play(off, 60), play(present, 60))


def test_on_changes_the_game():
    a = play(SvgGame(base_cfg(), 2, 1, 1, device="cpu", seed=4), 40)
    b = play(SvgGame(err_cfg(), 2, 1, 1, device="cpu", seed=4), 40)
    assert not torch.equal(a, b)


# ------------------------------------------------------------------------------------------------ refusals
@pytest.mark.parametrize("extra, match", [
    ({"starling.enabled": False}, "Starling layer"),
    ({"starling.backend": "physics"}, "physics"),
    ({"estimate_error.commander_reads": "mocap"}, "commander_reads"),
    ({"estimate_error.pos_tau_s": 0.0}, "tau"),
    ({"estimate_error.vel_sigma_mps": -0.1}, "sigma"),
])
def test_refused_settings(extra, match):
    with pytest.raises(ValueError, match=match):
        cfg = err_cfg(**extra)
        SvgGame(cfg, 1, 1, 1, device="cpu")


def test_attitude_key_is_refused(tmp_path):
    """Tier 1 has no attitude state (the fitted lag1 model is translational only): an attitude error key is unknown."""
    path = tmp_path / "g.toml"
    path.write_text(BASE.read_text() + "\n[estimate_error]\nenabled = true\natt_sigma_rad = 0.003\n")
    with pytest.raises(ValueError, match="att_sigma_rad"):
        load_game_cfg(path, local_dir=None, use_local=False)
    with pytest.raises(ValueError, match="att"):
        FittedResponse(1, 1, PARAMS, device="cpu", estimate_error={"att": (0.003, 2.0)})


# ------------------------------------------------------------------------------------------------ statistics
def test_gauss_markov_statistics():
    """Hover of 4000 drones (float64): the error starts stationary (sigma), keeps sigma, decays per tick as
    exp(-0.05 / tau) and over 2.5 s as exp(-2.5 / tau); position and velocity independent."""
    n, sig_p, tau_p, sig_v, tau_v = 4000, 0.0099, 1.2, 0.022, 1.3
    model = FittedResponse(n, 1, PARAMS, device="cpu", dtype=torch.float64, hover_seed=True,
                           estimate_error={"pos": (sig_p, tau_p), "vel": (sig_v, tau_v)}, estimate_seed=11)
    start = torch.zeros(n, 1, 3, dtype=torch.float64) + torch.tensor([0.0, 0.0, 1.2], dtype=torch.float64)
    model.reset(torch.ones(n, 1, dtype=torch.bool), start)
    zero = torch.zeros(n, 1, 3, dtype=torch.float64)

    def err():
        return (model.est_pos_m - model.pos_m).flatten(), (model.est_vel_mps - model.vel_mps).flatten()

    p0, v0 = err()
    model.step(zero)
    p1, v1 = err()
    for _ in range(49):
        model.step(zero)
    p50, v50 = err()
    corr = lambda a, b: float((a * b).mean() / (a.std() * b.std()))      # noqa: E731  (zero-mean process)
    for e, s in ((p0, sig_p), (p1, sig_p), (p50, sig_p), (v0, sig_v), (v50, sig_v)):
        assert abs(float(e.std()) / s - 1) < 0.03 and abs(float(e.mean())) < 4 * s / math.sqrt(e.numel())
    assert abs(corr(p0, p1) - math.exp(-TICK / tau_p)) < 0.01
    assert abs(corr(v0, v1) - math.exp(-TICK / tau_v)) < 0.01
    assert abs(corr(p0, p50) - math.exp(-50 * TICK / tau_p)) < 0.03
    assert abs(corr(v0, v50) - math.exp(-50 * TICK / tau_v)) < 0.03
    assert abs(corr(p0, v0)) < 0.03                                       # drawn independently
    # a reset redraws from the stationary distribution (no warm-up), only where the mask says
    keep = torch.arange(n) % 2 == 0
    before, _ = err()
    model.reset(~keep[:, None])
    after, _ = err()
    b3, a3 = before.view(n, 3), after.view(n, 3)
    assert torch.equal(a3[keep], b3[keep])
    fresh = a3[~keep].flatten()
    assert abs(float(fresh.std()) / sig_p - 1) < 0.05 and abs(corr(fresh, b3[~keep].flatten())) < 0.05


def test_error_steps_on_the_px4_sub_step_grid():
    """The error is stepped once per 0.01 s PX4 sub-step (five per tick), as tier 2 steps it per physics step."""
    model = FittedResponse(1, 1, PARAMS, device="cpu", estimate_error={"pos": (0.01, 1.2)})
    assert model.estimator.error_a["pos"] == pytest.approx(math.exp(-SUB_DT / 1.2), rel=1e-12)
    assert model.estimator.delay_steps == 0 and not model.estimator.noisy           # no delay, no white noise


# ------------------------------------------------------------------------------------------------ what reads what
def _hover_offset(commander_reads_estimate: bool) -> tuple[Tensor, Tensor]:
    """A frozen position error (tau 1e6 s) on a hovering drone for 40 s: (true displacement, the error)."""
    model = FittedResponse(4, 1, PARAMS, device="cpu", dtype=torch.float64, hover_seed=True,
                           estimate_error={"pos": (0.05, 1.0e6)}, estimate_seed=2,
                           commander_reads_estimate=commander_reads_estimate)
    start = torch.tensor([1.0, -1.0, 1.2], dtype=torch.float64).expand(4, 1, 3).clone()
    model.reset(torch.ones(4, 1, dtype=torch.bool), start)
    e = model.est_pos_m - model.pos_m
    for _ in range(800):
        model.step(torch.zeros(4, 1, 3, dtype=torch.float64))
    return model.pos_m - start, e


def test_px4_feedback_reads_the_estimate_and_the_switch_moves_the_commander():
    """Commander on the true position: its hold point is the true start, PX4 flies its estimate there, so the drone
    settles at start - e. Commander on the estimate: hold point start + e, PX4's estimate reaches it at the true start."""
    moved, e = _hover_offset(False)
    assert float(e.abs().max()) > 0.02
    assert torch.allclose(moved, -e, atol=2e-3)
    still, _ = _hover_offset(True)
    assert float(still.abs().max()) < 2e-3


@pytest.mark.parametrize("reads", ["true", "estimate"])
def test_filter_reads_what_the_switch_says_and_the_game_reads_true(monkeypatch, reads):
    seen = []
    real = fitted.filter_velocities

    def spy(nominal, pos_m, *a, **k):
        seen.append(pos_m.clone())
        return real(nominal, pos_m, *a, **k)

    monkeypatch.setattr(fitted, "filter_velocities", spy)
    tagged_on = []

    class Probe(SvgGame):
        def _study_tags(self, pos_m, alive, corrected):
            tagged_on.append(pos_m.clone())
            return super()._study_tags(pos_m, alive, corrected)

    game = Probe(err_cfg(reads), 3, 3, 3, device="cpu", seed=8)
    g, s = Jiggle(3, 3, 5), Jiggle(3, 3, 6)
    model = game._starling.model
    for _ in range(30):
        true_before, est_before = model.pos_m.clone(), model.est_pos_m.clone()
        alive_before = game.alive.clone()
        n_seen = len(seen)
        game.step({"guard": g(), "strike": s()})
        assert len(seen) == n_seen + 1
        want = est_before if reads == "estimate" else true_before
        live = alive_before[..., None].expand_as(want)
        assert torch.equal(seen[-1][live], want[live])                 # the filter's positions at the tick start
        # the tags and the scoring see the true positions (live drones; out drones are parked by the game)
        alive = game.alive[..., None].expand_as(game.pos_m)
        assert torch.equal(tagged_on[-1][alive], model.pos_m[alive])
        assert torch.equal(game.pos_m[alive], model.pos_m[alive])
        assert not torch.equal(model.est_pos_m[alive], model.pos_m[alive])


# ------------------------------------------------------------------------------------------------ seed, replay
def _err_state(game):
    """The error's state (position, velocity) [N, M, 3] each, exactly (EstimatorEffect.state_dict)."""
    err = game._starling.model.estimator.state_dict()["err"]
    return err["pos"], err["vel"]


def test_game_seed_reaches_the_error():
    a, b, c = (SvgGame(err_cfg(), 4, 1, 1, device="cpu", seed=s) for s in (5, 5, 6))
    ea, eb, ec = layer_error(a)[0], layer_error(b)[0], layer_error(c)[0]
    assert torch.equal(ea, eb) and not torch.allclose(ea, ec)
    assert not torch.allclose(ea[0], ea[1])                              # each game slot its own error
    play(a, 10)
    play(c, 23)
    a.reset(seed=9)
    c.reset(seed=9)
    fresh = SvgGame(err_cfg(), 4, 1, 1, device="cpu", seed=9)
    for x, y in zip(_err_state(a), _err_state(fresh)):                   # reset(seed) draws as a fresh game would
        assert torch.equal(x, y)
    for x, y in zip(_err_state(c), _err_state(fresh)):
        assert torch.equal(x, y)


def test_replay_same_seed_same_game():
    """Same seed and same commands: the same game, tick for tick (auto-resets and out drones included); two used games
    with different histories play the same game after reset(seed). (A fresh game's own start draws differ from
    reset(seed)'s, as before L1.7: __init__ draws arenas once more; the error itself restarts alike, test above.)"""
    cfg = err_cfg(**{"rules.game_steps": 60})                            # 3 s games: many auto-resets
    one = play(SvgGame(cfg, 3, 3, 3, device="cpu", seed=12), 150)
    two = play(SvgGame(cfg, 3, 3, 3, device="cpu", seed=12), 150)
    assert torch.equal(one, two)
    used = []
    for seed, ticks in ((1, 37), (2, 81)):
        g = SvgGame(cfg, 3, 3, 3, device="cpu", seed=seed)
        play(g, ticks, seed=7)
        g.reset(seed=12)
        used.append(play(g, 150))
    assert torch.equal(used[0], used[1])
    off = err_cfg(**{"rules.game_steps": 60, "estimate_error.enabled": False})
    assert not torch.equal(play(SvgGame(off, 3, 3, 3, device="cpu", seed=12), 150), one)   # the error is in play


# ------------------------------------------------------------------------------------------------ study files
def _toml(path):
    return tomllib.loads(path.read_text())


def test_study_files_are_base_plus_the_table():
    base, nom, con = _toml(BASE), _toml(NOMINAL), _toml(CONSERVATIVE)
    t_nom, t_con = nom.pop("estimate_error"), con.pop("estimate_error")
    assert nom == base and con == base                                   # every other value as base.toml
    assert t_nom == {"enabled": True, "pos_sigma_m": 0.0099, "pos_tau_s": 1.2, "vel_sigma_mps": 0.022,
                     "vel_tau_s": 1.3, "commander_reads": "true"}
    assert t_con == {**t_nom, "pos_sigma_m": 2 * 0.0099, "vel_sigma_mps": 2 * 0.022}   # sigmas doubled, nothing else
    # and the text: base.toml's value lines byte for byte, then the table
    values = lambda p: [x for x in p.read_text().split("\n[estimate_error]")[0].splitlines()   # noqa: E731
                        if x.strip() and not x.lstrip().startswith("#")]
    assert values(NOMINAL) == values(BASE) == values(CONSERVATIVE)
    for p in (NOMINAL, CONSERVATIVE):
        cfg = load_game_cfg(p, local_dir=None, use_local=False)[0]
        assert cfg.estimate_error.enabled and cfg.starling.backend == "fitted"
        assert "EXPLORATORY" in p.read_text() and "PROPOSED" in p.read_text()
