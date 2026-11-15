"""Tests for the batched safety-filter port (core/safety_filter.py) against CMU's cbf_filter.py."""
import ast
import importlib.util
import pathlib
import re
import sys
import tomllib

import numpy as np
import pytest
import torch

ROOT = pathlib.Path(__file__).resolve().parents[1]
CMU_PKG = ROOT.parent / "AirStack/robot/ros_ws/src/svg_ground_control"
sys.path.insert(0, str(CMU_PKG))
from svg_ground_control.cbf_filter import filter_velocities as cmu_filter  # noqa: E402

from svg_training.core import safety_filter as sf  # noqa: E402
from svg_training.core.safety_filter import FilterResult, filter_velocities, team_pair_mask  # noqa: E402

GATES = tomllib.loads((ROOT / "configs/s1.toml").read_text())["filter_gates"]
R_M = 0.55
ALPHA = 2.5


def _port(nominal, pos, vmax, mask=None, iterations=200, dtype=torch.float64):
    """One scene through the port; numpy (M, 3) in, numpy (M, 3) out plus the result."""
    m = len(pos)
    mask = team_pair_mask(m, 0) if mask is None else mask
    res = filter_velocities(torch.tensor(nominal, dtype=dtype)[None], torch.tensor(pos, dtype=dtype)[None],
                            mask, R_M, vmax, alpha=ALPHA, iterations=iterations)
    return res.velocities[0].numpy(), res


def _cmu(nominal, pos, vmax):
    return cmu_filter(np.asarray(nominal, float), np.asarray(pos, float), safety_radius=R_M, max_speed=vmax,
                      alpha=ALPHA)


# --- team mask -----------------------------------------------------------------------------------

def test_team_pair_mask_is_within_team_only():
    m = team_pair_mask(2, 3)
    assert m.shape == (5, 5) and m.dtype == torch.bool
    expect = torch.zeros(5, 5, dtype=torch.bool)
    expect[:2, :2] = True
    expect[2:, 2:] = True
    expect.fill_diagonal_(False)
    assert torch.equal(m, expect)
    assert torch.equal(team_pair_mask(3, 0), ~torch.eye(3, dtype=torch.bool))


# --- basic behaviour -----------------------------------------------------------------------------

def test_no_conflict_leaves_nominal_unchanged():
    pos = [[0.0, 0.0, 1.0], [5.0, 0.0, 1.0], [0.0, 5.0, 1.0]]
    nom = [[0.3, 0.0, 0.0], [0.0, 0.5, 0.0], [0.0, 0.0, -0.2]]
    v, res = _port(nom, pos, 2.0)
    assert isinstance(res, FilterResult)
    assert np.array_equal(v, np.array(nom))
    assert not res.corrected.any() and not res.emergency.any() and float(res.residual[0]) == 0.0


def test_speed_cap_respected_scalar_and_per_drone():
    gen = torch.Generator().manual_seed(3)
    pos = torch.rand(64, 6, 3, generator=gen, dtype=torch.float64) * 4.0
    nom = (torch.rand(64, 6, 3, generator=gen, dtype=torch.float64) - 0.5) * 12.0
    res = filter_velocities(nom, pos, team_pair_mask(3, 3), R_M, 2.0)
    assert (res.velocities.norm(dim=-1) <= 2.0 + 1e-9).all()
    cap = 1.0 + 3.0 * torch.rand(64, 6, 1, generator=gen, dtype=torch.float64)
    res = filter_velocities(nom, pos, team_pair_mask(6, 0), R_M, cap)
    assert (res.velocities.norm(dim=-1, keepdim=True) <= cap + 1e-9).all()


def test_fixed_rows_not_supported():
    pos = torch.zeros(1, 2, 3)
    pos[0, 1, 0] = 3.0
    with pytest.raises(ValueError, match="fixed"):
        filter_velocities(torch.zeros(1, 2, 3), pos, team_pair_mask(2, 0), R_M, 1.0, fixed=torch.tensor([True, False]))


# --- parity with CMU's filter on hand-made scenes ------------------------------------------------

HAND_SCENES = {
    # name: (positions, nominal, vmax, original uses emergency)
    "head_on_outside_keep_out": ([[0.0, 0, 1], [2.0, 0, 1]], [[2.0, 0, 0], [-2.0, 0, 0]], 2.0, False),
    "head_on_inside_keep_out": ([[0.0, 0, 1], [1.0, 0, 1]], [[1.0, 0, 0], [-1.0, 0, 0]], 2.0, False),
    "head_on_offset": ([[0.0, 0, 1], [1.6, 0.3, 1.1]], [[1.5, 0, 0], [-1.5, 0, 0]], 1.5, False),
    "three_way": ([[0.0, 0, 1], [1.5, 0, 1], [0.75, 1.299, 1]],
                  [[1.3, 0.75, 0], [-1.3, 0.75, 0], [0, -1.5, 0]], 2.0, False),
    "deep_penetration": ([[0.0, 0, 1], [0.1, 0, 1]], [[0.5, 0, 0], [-0.5, 0, 0]], 1.0, True),
    "coincident": ([[0.0, 0, 1], [0.0, 0, 1]], [[0.2, 0, 0], [0.0, 0.3, 0]], 1.0, True),
}


@pytest.mark.parametrize("name", sorted(HAND_SCENES))
def test_parity_with_cmu_on_hand_made_scenes(name):
    pos, nom, vmax, emergency = HAND_SCENES[name]
    ref = _cmu(nom, pos, vmax)
    assert ref.used_emergency_stop is emergency  # the scene is what its name says
    v, res = _port(nom, pos, vmax)
    assert bool(res.emergency[0]) is emergency
    assert np.abs(v - ref.velocities).max() <= GATES["max_abs_dv_mps"]
    assert np.array_equal(res.corrected[0].numpy(), ref.corrected)


def test_inside_keep_out_cluster_triggers_emergency_like_cmu():
    rng = np.random.default_rng(0)
    pos = rng.uniform(-0.3, 0.3, size=(6, 3)) + np.array([0.0, 0.0, 1.0])
    nom = rng.uniform(-1.0, 1.0, size=(6, 3))
    ref = _cmu(nom, pos, 1.0)
    v, res = _port(nom, pos, 1.0)
    assert ref.used_emergency_stop and bool(res.emergency[0])
    assert (np.linalg.norm(v, axis=-1) <= 1.0 + 1e-9).all()


def test_feasible_scene_constraints_hold_within_tolerance():
    pos, nom, vmax, _ = HAND_SCENES["three_way"]
    v, res = _port(nom, pos, vmax)
    p = np.array(pos)
    for i, j in [(0, 1), (0, 2), (1, 2)]:
        d = p[i] - p[j]
        lhs = 2 * d @ (v[i] - v[j]) + ALPHA * (d @ d - (2 * R_M) ** 2)
        assert lhs >= -GATES["constraint_residual_max"]
    assert float(res.residual[0]) <= GATES["constraint_residual_max"]


# --- team mask: Guard-Strike pairs are never filtered --------------------------------------------

def test_guard_strike_collision_course_gets_zero_correction():
    pos = [[0.0, 0, 1], [1.0, 0, 1]]  # inside each other's keep-out, closing at 4 m/s
    nom = [[2.0, 0, 0], [-2.0, 0, 0]]
    v, res = _port(nom, pos, 2.0, mask=team_pair_mask(1, 1))
    assert np.array_equal(v, np.array(nom))
    assert not res.corrected.any() and not res.emergency.any()


def test_two_teams_filtered_separately_like_cmu_per_team():
    # Guards 0, 1 head-on; Strikes 2, 3 head-on; every Guard also close to a Strike.
    pos = np.array([[0.0, 0, 1], [1.4, 0, 1], [0.0, 0.8, 1], [1.4, 0.8, 1]])
    nom = np.array([[1.5, 0, 0], [-1.5, 0, 0], [1.5, -0.5, 0], [-1.5, -0.5, 0]])
    v, res = _port(nom, pos, 2.0, mask=team_pair_mask(2, 2))
    for team in ([0, 1], [2, 3]):
        ref = _cmu(nom[team], pos[team], 2.0)
        assert np.abs(v[team] - ref.velocities).max() <= GATES["max_abs_dv_mps"]
    # The same Strike pair alone in its game gives bit-identical velocities: the Guards had no effect.
    alone, _ = _port(nom[2:], pos[2:], 2.0)
    assert np.array_equal(v[2:], alone)


def test_per_game_mask_matches_shared_mask():
    gen = torch.Generator().manual_seed(5)
    pos = torch.rand(8, 5, 3, generator=gen, dtype=torch.float64) * 3.0
    nom = (torch.rand(8, 5, 3, generator=gen, dtype=torch.float64) - 0.5) * 4.0
    mask = team_pair_mask(2, 3)
    a = filter_velocities(nom, pos, mask, R_M, 2.0)
    b = filter_velocities(nom, pos, mask.expand(8, 5, 5), R_M, 2.0)
    assert torch.equal(a.velocities, b.velocities) and torch.equal(a.emergency, b.emergency)


# --- batching ------------------------------------------------------------------------------------

def test_games_do_not_interact():
    gen = torch.Generator().manual_seed(7)
    pos = torch.rand(16, 6, 3, generator=gen, dtype=torch.float64) * 3.0
    nom = (torch.rand(16, 6, 3, generator=gen, dtype=torch.float64) - 0.5) * 4.0
    mask = team_pair_mask(4, 2)
    batch = filter_velocities(nom, pos, mask, R_M, 2.0)
    for k in range(16):
        one = filter_velocities(nom[k:k + 1], pos[k:k + 1], mask, R_M, 2.0)
        assert torch.allclose(batch.velocities[k], one.velocities[0], atol=1e-12, rtol=0)
        assert bool(batch.emergency[k]) == bool(one.emergency[0])


def _shapes_ok(res, n, m, device):
    assert res.velocities.shape == (n, m, 3) and res.corrected.shape == (n, m)
    assert res.residual.shape == (n,) and res.emergency.shape == (n,)
    assert res.corrected.dtype == torch.bool and res.emergency.dtype == torch.bool
    for t in (res.velocities, res.corrected, res.residual, res.emergency):
        assert t.device.type == device
    assert torch.isfinite(res.velocities).all()


def test_shapes_for_4096_games_cpu():
    gen = torch.Generator().manual_seed(11)
    pos = torch.rand(4096, 8, 3, generator=gen) * 4.0
    nom = (torch.rand(4096, 8, 3, generator=gen) - 0.5) * 4.0
    res = filter_velocities(nom, pos, team_pair_mask(5, 3), R_M, 2.0, iterations=10)
    _shapes_ok(res, 4096, 8, "cpu")
    assert res.velocities.dtype == torch.float32


@pytest.mark.skipif(not torch.cuda.is_available(), reason="no CUDA device")
def test_device_follows_inputs_cuda():
    gen = torch.Generator().manual_seed(13)
    pos = (torch.rand(4096, 8, 3, generator=gen) * 4.0).cuda()
    nom = ((torch.rand(4096, 8, 3, generator=gen) - 0.5) * 4.0).cuda()
    res = filter_velocities(nom, pos, team_pair_mask(5, 3), R_M, 2.0, iterations=10)  # mask on CPU
    _shapes_ok(res, 4096, 8, "cuda")
    cpu = filter_velocities(nom.cpu(), pos.cpu(), team_pair_mask(5, 3), R_M, 2.0, iterations=10)
    assert torch.allclose(res.velocities.cpu(), cpu.velocities, atol=1e-4)


# --- `iterations` is the only loop ---------------------------------------------------------------

def test_iterations_is_the_only_loop():
    tree = ast.parse(pathlib.Path(sf.__file__).read_text())
    loops = [n for n in ast.walk(tree) if isinstance(n, (ast.For, ast.AsyncFor, ast.While, ast.comprehension))]
    assert len(loops) == 1, [ast.dump(n)[:80] for n in loops]
    it = loops[0].iter
    assert isinstance(it, ast.Call) and it.func.id == "range" and [a.id for a in it.args] == ["iterations"]


def test_iterations_sets_the_work():
    """With 1 sweep a dense scene is not solved; with 200 it is (the loop count is the budget)."""
    pos, nom, vmax, _ = HAND_SCENES["three_way"]
    _, one = _port(nom, pos, vmax, iterations=1)
    _, many = _port(nom, pos, vmax, iterations=200)
    assert float(one.residual[0]) > GATES["constraint_residual_max"] or bool(one.emergency[0])
    assert float(many.residual[0]) <= GATES["constraint_residual_max"] and not bool(many.emergency[0])


def test_non_finite_nominal_takes_emergency_and_returns_finite():
    pos = [[0.0, 0, 1], [1.5, 0, 1], [6.0, 0, 1]]
    nom = [[float("nan"), 0, 0], [-1.0, 0, 0], [0.5, 0, 0]]
    v, res = _port(nom, pos, 2.0)
    assert bool(res.emergency[0]) and np.isfinite(v).all()
    ref = _cmu(np.array(nom), np.array(pos), 2.0)
    assert ref.used_emergency_stop


# --- a non-finite value in one team never reaches the other team (review I1) ---------------------

# Guards 0, 1 head-on; Strikes 2, 3 head-on nearby, so the Strike result is a real correction.
NF_POS = np.array([[0.0, 0, 1], [1.4, 0, 1], [0.0, 0.8, 1], [1.4, 0.8, 1]])
NF_NOM = np.array([[1.5, 0, 0], [-1.5, 0, 0], [1.5, -0.5, 0], [-1.5, -0.5, 0]])


def _nf_run(nom, pos):
    res = filter_velocities(torch.tensor(nom)[None], torch.tensor(pos)[None], team_pair_mask(2, 2), R_M, 2.0,
                            iterations=200)
    return res.velocities[0].numpy(), res


@pytest.mark.parametrize("where", ["command", "position"])
@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_non_finite_guard_leaves_strike_team_unchanged(where, bad):
    clean, clean_res = _nf_run(NF_NOM, NF_POS)
    assert clean_res.corrected[0, 2:].all()  # the Strikes really are filtered
    nom, pos = NF_NOM.copy(), NF_POS.copy()
    (nom if where == "command" else pos)[0, 1] = bad
    v, res = _nf_run(nom, pos)
    assert np.array_equal(v[2:], clean[2:])  # bit-identical Strike output
    assert np.array_equal(res.corrected[0, 2:].numpy(), clean_res.corrected[0, 2:].numpy())
    assert np.isfinite(v).all() and np.array_equal(v[0], np.zeros(3))  # the bad Guard is commanded zero
    assert bool(res.emergency[0])  # flagged for the game (the Guard team)


def test_non_finite_guard_in_batch_leaves_other_games_unchanged():
    nom = np.stack([NF_NOM, NF_NOM])
    pos = np.stack([NF_POS, NF_POS])
    nom[0, 0, 0] = float("nan")
    res = filter_velocities(torch.tensor(nom), torch.tensor(pos), team_pair_mask(2, 2), R_M, 2.0, iterations=200)
    clean, _ = _nf_run(NF_NOM, NF_POS)
    assert np.array_equal(res.velocities[1].numpy(), clean) and not bool(res.emergency[1])


# --- the parity script ---------------------------------------------------------------------------

def _load_script():
    spec = importlib.util.spec_from_file_location("filter_parity", ROOT / "scripts/filter_parity.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_scene_generator_is_seeded_and_near_collision_heavy():
    fp = _load_script()
    a = fp.make_scenes(200, seed=1)
    b = fp.make_scenes(200, seed=1)
    assert all(np.array_equal(x.pos_m, y.pos_m) and np.array_equal(x.nominal_mps, y.nominal_mps) for x, y in zip(a, b))
    stats = fp.scene_stats(a)
    assert stats["near_scene_fraction"] >= 0.5
    assert stats["penetration_scenes"] > 0 and stats["two_team_scenes"] > 0 and stats["one_team_scenes"] > 0
    assert {s.pos_m.shape[0] for s in a} == set(range(2, 9))
    assert all(1.0 <= s.max_speed_mps <= 4.0 for s in a)
    assert all((np.linalg.norm(s.nominal_mps, axis=-1) <= s.max_speed_mps + 1e-12).all() for s in a)


def test_parity_script_writes_record_and_ledger_row_and_refuses_overwrite(tmp_path):
    fp = _load_script()
    gates = tmp_path / "g.toml"
    text = (ROOT / "configs/s1.toml").read_text().replace("scenes = 2000", "scenes = 30")
    gates.write_text(text)
    ledger = tmp_path / "LEDGER.md"
    ledger.write_text((ROOT / "records/LEDGER.md").read_text())
    before = [int(n) for n in re.findall(r"^\| T(\d+) \|", ledger.read_text(), flags=re.M)]
    expect = max(before, default=0) + 1  # the next T-number, whatever the real ledger holds today
    args =["--gates", str(gates), "--name", "x_s1_filter_parity", "--out-dir", str(tmp_path), "--ledger", str(ledger)]
    assert fp.main(args) == 0
    rec = (tmp_path / "x_s1_filter_parity_record.md").read_text()
    assert rec.splitlines()[0] == "Simulator: training simulator (safety-filter port vs CMU cbf_filter.py, CPU)"
    for gate in GATES:
        if gate != "scenes":
            assert gate in rec
    rows = [ln for ln in ledger.read_text().splitlines() if ln.startswith("| T")]
    assert rows[-1].startswith(f"| T{expect} | ") and "x_s1_filter_parity" in rows[-1]
    assert len(rows) == len(before) + 1
    assert fp.main(args) == 1  # refuses to overwrite
    assert len([ln for ln in ledger.read_text().splitlines() if ln.startswith("| T")]) == len(rows)


# --- `check_every`: early stop with a shrinking working batch (S2 Task 7) -------------------------

def _scene_batch(count, seed):
    fp = _load_script()
    return fp._batch(fp.make_scenes(count, seed))


def test_check_every_matches_fixed_loop():
    nom, pos, mask, cap = _scene_batch(200, 7)
    a = filter_velocities(nom, pos, mask, 0.55, cap, iterations=300)
    b = filter_velocities(nom, pos, mask, 0.55, cap, iterations=300, check_every=8)
    assert (a.velocities - b.velocities).abs().max() <= 1e-5
    assert torch.equal(a.emergency, b.emergency) and torch.equal(a.corrected, b.corrected)


def test_check_every_zero_is_bit_identical():
    nom, pos, mask, cap = _scene_batch(200, 7)
    a = filter_velocities(nom, pos, mask, 0.55, cap, iterations=300)
    b = filter_velocities(nom, pos, mask, 0.55, cap, iterations=300, check_every=0)
    for x, y in ((a.velocities, b.velocities), (a.corrected, b.corrected), (a.residual, b.residual),
                 (a.emergency, b.emergency)):
        assert torch.equal(x, y)


def test_inactive_games_return_clamped_nominal():
    """Drones 10 m apart: no pair can be violated, the game skips the sweeps; the answer is the speed clamp."""
    gen = torch.Generator().manual_seed(17)
    pos = torch.tensor([[0.0, 0, 1], [10.0, 0, 1], [0.0, 10.0, 1], [10.0, 10.0, 1]]).expand(32, 4, 3).clone()
    nom = (torch.rand(32, 4, 3, generator=gen) - 0.5) * 8.0  # many over the 2 m/s cap
    res = filter_velocities(nom, pos, team_pair_mask(2, 2), R_M, 2.0, iterations=300, check_every=8)
    norms = nom.norm(dim=-1, keepdim=True)
    clamped = torch.where(norms > 2.0, nom * (2.0 / norms), nom)
    assert (res.velocities - clamped).abs().max() <= 1e-6
    assert not res.emergency.any()
    fixed = filter_velocities(nom, pos, team_pair_mask(2, 2), R_M, 2.0, iterations=300)
    assert torch.equal(res.corrected, fixed.corrected)


def test_check_every_with_per_game_mask():
    """[N, M, M] masks with drop-outs (a dropped drone pairs with nobody) give the fixed loop's answer."""
    gen = torch.Generator().manual_seed(19)
    pos = torch.rand(64, 8, 3, generator=gen) * 3.0
    nom = (torch.rand(64, 8, 3, generator=gen) - 0.5) * 4.0
    live = torch.rand(64, 8, generator=gen) > 0.25  # about a quarter of the drones dropped out
    mask = ~torch.eye(8, dtype=torch.bool).expand(64, 8, 8) & live[:, :, None] & live[:, None, :]
    a = filter_velocities(nom, pos, mask, R_M, 2.0, iterations=300)
    b = filter_velocities(nom, pos, mask, R_M, 2.0, iterations=300, check_every=8)
    assert (a.velocities - b.velocities).abs().max() <= 1e-5
    assert torch.equal(a.emergency, b.emergency) and torch.equal(a.corrected, b.corrected)


def test_check_every_stops_early(monkeypatch):
    """Solvable games converge in tens of sweeps; with check_every the loop ends soon after, not at `iterations`;
    a game that never converges (coincident drones) keeps sweeping alone in a one-game working batch."""
    calls = []
    real = sf._drone_residual
    monkeypatch.setattr(sf, "_drone_residual", lambda *a: calls.append(a[0].shape[0]) or real(*a))
    names = ["head_on_outside_keep_out", "head_on_offset", "three_way"]
    m = 3
    pos = torch.full((len(names), m, 3), 50.0, dtype=torch.float64)
    nom = torch.zeros(len(names), m, 3, dtype=torch.float64)
    pos[:, :, 0] += 10.0 * torch.arange(m)  # padding drones far apart
    for k, name in enumerate(names):
        p_, n_, _, _ = HAND_SCENES[name]
        pos[k, : len(p_)], nom[k, : len(n_)] = torch.tensor(p_), torch.tensor(n_)
    mask = team_pair_mask(m, 0)
    fixed = filter_velocities(nom, pos, mask, R_M, 2.0, iterations=5000)
    calls.clear()
    early = filter_velocities(nom, pos, mask, R_M, 2.0, iterations=5000, check_every=8)
    assert len(calls) - 2 < 1000  # one residual per sweep, plus two after the loop
    assert (early.velocities - fixed.velocities).abs().max() <= 1e-9
    calls.clear()  # add a coincident game: it never converges, so the loop runs on, on that game alone
    pos2, nom2 = torch.cat([pos, pos[:1]]), torch.cat([nom, nom[:1]])
    pos2[-1, 1] = pos2[-1, 0]
    filter_velocities(nom2, pos2, mask, R_M, 2.0, iterations=400, check_every=8)
    assert len(calls) - 2 == 400 and calls[-3] == 1


def test_check_every_must_not_be_negative():
    nom, pos, mask, cap = _scene_batch(4, 7)
    with pytest.raises(ValueError, match="check_every"):
        filter_velocities(nom, pos, mask, 0.55, cap, iterations=10, check_every=-1)


def test_t2_numbers_reproduced_at_1000_sweeps_check_every_0():
    """T2's 2,000 scenes (seed 20261115) at 1,000 sweeps, check_every 0: the four T2 numbers of its record."""
    fp = _load_script()
    threads = torch.get_num_threads()
    torch.set_num_threads(min(8, threads))  # T2's setting
    try:
        scenes = fp.make_scenes(2000, 20261115)
        ref = fp.run_original(scenes)
        port = fp.run_port(scenes, 1000, torch.float32, check_every=0)
        ev = fp.evaluate(scenes, ref, port)
        cross = fp.cross_team_check(scenes, port, 1000, torch.float32, check_every=0)
    finally:
        torch.set_num_threads(threads)
    assert fp._fmt(ev["max_abs_dv_mps"]) == "1.6666"
    assert fp._fmt(ev["constraint_residual_max"]) == "2.08973"
    assert fp._fmt(ev["emergency_agreement_min"]) == "0.999"
    assert cross["cross_team_corrections"] == 0
    assert f"{ev['max_dv_subset_no_gs']:.3g}" == "6.18e-05"
    assert len(ev["subset"]) == 1779 and int(port["emergency"].sum()) == 223


# --- host syncs on CUDA (D10: one per check, none otherwise) --------------------------------------

def _cuda_batch():
    gen = torch.Generator().manual_seed(23)
    pos = (torch.rand(256, 8, 3, generator=gen) * 4.0).cuda()
    nom = ((torch.rand(256, 8, 3, generator=gen) - 0.5) * 4.0).cuda()
    mask = torch.ones(8, 8, dtype=torch.bool).fill_diagonal_(False).cuda()  # every pair, as the Starling layer
    cap = torch.tensor(2.0, device="cuda")
    return nom, pos, mask, cap


@pytest.mark.skipif(not torch.cuda.is_available(), reason="no CUDA device")
def test_tensor_cap_makes_no_host_sync_cuda():
    nom, pos, mask, cap = _cuda_batch()
    filter_velocities(nom, pos, mask, R_M, cap, iterations=20)  # warm-up (lazy CUDA init)
    torch.cuda.synchronize()
    torch.cuda.set_sync_debug_mode("error")
    try:
        filter_velocities(nom, pos, mask, R_M, cap, iterations=20)
        filter_velocities(nom, pos, mask, R_M, cap, iterations=20, check_every=0)
    finally:
        torch.cuda.set_sync_debug_mode("default")


@pytest.mark.skipif(not torch.cuda.is_available(), reason="no CUDA device")
def test_check_every_one_host_sync_per_check_cuda():
    import warnings
    nom, pos, mask, cap = _cuda_batch()
    filter_velocities(nom, pos, mask, R_M, cap, iterations=40, check_every=8)  # warm-up
    torch.cuda.synchronize()
    torch.cuda.set_sync_debug_mode("warn")
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            filter_velocities(nom, pos, mask, R_M, cap, iterations=40, check_every=8)
    finally:
        torch.cuda.set_sync_debug_mode("default")
    syncs = [w for w in caught if "synchroniz" in str(w.message)]
    assert 1 <= len(syncs) <= 40 // 8  # checks at sweeps 0, 8, 16, 24, 32 at most; it may stop sooner
