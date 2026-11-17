"""Tests of the ported scripted controllers (the partner's APF). Marker values only; the parity test against the partner's own
scripted actions on recorded states runs only where the reference file and the local files exist (scripts/nus_export_reference.py)."""
import numpy as np
import pytest
import torch

from _nus_markers import TIE_SHARE_MAX, BATCH, POS_TOL, TOL_LOOSE, TOL_TIGHT, SEED_B, load_marker_files
from svg_training.nus import deploy as deploy_mod, rules as rules_mod
from svg_training.nus.apf import NusApf

F32 = torch.float32


@pytest.fixture(scope="module")
def files(tmp_path_factory):
    return load_marker_files(tmp_path_factory.mktemp("apf"))


@pytest.fixture(scope="module")
def apf(files):
    rules, deploy, _, _ = files
    return NusApf(rules, deploy)


def reference_strike(rules, deploy, strikes, guards):
    """Plain per-drone NumPy restatement of the Strike controller, written separately from the batched code."""
    out = []
    radius = 2 * rules.agent_size + rules.guard_safety_distance
    for s in strikes:
        dist = np.linalg.norm(s)
        total = deploy.apf_attraction_gain * (-s / dist if dist > deploy.apf_floor else np.zeros(2))
        for g in guards:
            away = s - g
            d = np.linalg.norm(away)
            direction = away / max(d, deploy.apf_floor) if d > deploy.apf_floor else np.zeros(2)
            strength = max(1 / max(d, deploy.apf_floor) - 1 / radius, 0) / max(d, deploy.apf_floor) ** 2
            total = total + deploy.apf_repulsion_gain * direction * strength
        n = np.linalg.norm(total)
        out.append(total * min(1, rules.strike_max_speed / max(n, deploy.apf_floor)))
    return np.array(out)


def layout(rules, guard_xy, strike_xy):
    return torch.tensor([[*guard_xy, *strike_xy]], dtype=F32).reshape(1, -1, 2)


def test_strike_far_from_guards_is_pulled_to_the_zone_at_most_the_team_speed(apf, files):
    rules, deploy, _, _ = files
    guards = [[0.0, 0.0]] * rules.guard_count
    strikes = [[rules.spawn_distance, 0.0]] * rules.strike_count
    act = apf.strike_actions(layout(rules, guards, strikes))
    assert act.shape == (1, rules.strike_count, 2)
    expect = torch.tensor([-min(deploy.apf_attraction_gain, rules.strike_max_speed), 0.0])
    assert torch.allclose(act[0, 0], expect, atol=TOL_TIGHT)


def test_strike_next_to_a_guard_is_pushed_away_and_matches_the_plain_restatement(apf, files):
    rules, deploy, _, _ = files
    radius = 2 * rules.agent_size + rules.guard_safety_distance
    gen = torch.Generator().manual_seed(SEED_B)
    guards = torch.rand(BATCH, rules.guard_count, 2, generator=gen) * radius
    strikes = torch.rand(BATCH, rules.strike_count, 2, generator=gen) * radius
    pos = torch.cat((guards, strikes), dim=1)
    got = apf.strike_actions(pos).numpy()
    for game in range(BATCH):
        want = reference_strike(rules, deploy, strikes[game].numpy(), guards[game].numpy())
        np.testing.assert_allclose(got[game], want, atol=TOL_LOOSE)
    assert float(np.linalg.norm(got, axis=-1).max()) <= rules.strike_max_speed + TOL_TIGHT


def test_strike_exactly_on_a_guard_and_on_the_zone_centre_gives_finite_actions(apf, files):
    rules, _, _, _ = files
    guards = [[rules.spawn_distance, 0.0]] * rules.guard_count
    strikes = [[rules.spawn_distance, 0.0]] + [[0.0, 0.0]] * (rules.strike_count - 1)
    act = apf.strike_actions(layout(rules, guards, strikes))
    assert torch.isfinite(act).all()
    assert act[0, 1].abs().max() == 0  # on the zone centre and far from the Guards: nothing pulls or pushes


def test_guard_runs_at_the_nearest_strike_capped_at_the_team_speed(apf, files):
    rules, _, _, _ = files
    guards = [[0.0, 0.0]] * rules.guard_count
    strikes = [[rules.spawn_distance, 0.0]] + [[0.0, 2 * rules.spawn_distance]] * (rules.strike_count - 1)
    act = apf.guard_actions(layout(rules, guards, strikes))
    assert act.shape == (1, rules.guard_count, 2)
    near = torch.tensor([[rules.guard_max_speed / 2, 0.0]])
    close = layout(rules, [[0.0, 0.0]] * rules.guard_count, [[rules.guard_max_speed / 2, 0.0]] * rules.strike_count)
    assert torch.allclose(apf.guard_actions(close)[0, 0], near[0], atol=TOL_TIGHT)  # a short offset is not scaled up
    assert torch.allclose(act[0].norm(dim=-1), torch.full((rules.guard_count,), rules.guard_max_speed), atol=TOL_TIGHT)


def test_games_in_a_batch_do_not_affect_each_other(apf, files):
    rules, _, _, _ = files
    gen = torch.Generator().manual_seed(SEED_B)
    pos = torch.randn(BATCH, rules.guard_count + rules.strike_count, 2, generator=gen) * rules.area_radius
    both = apf.strike_actions(pos)
    for i in range(BATCH):
        assert torch.allclose(apf.strike_actions(pos[i:i + 1]), both[i:i + 1], atol=TOL_TIGHT)


def test_actions_by_team_name(apf, files):
    rules, _, _, _ = files
    pos = torch.randn(BATCH, rules.guard_count + rules.strike_count, 2)
    assert torch.equal(apf.actions("strike", pos), apf.strike_actions(pos)) and torch.equal(apf.actions("guard", pos), apf.guard_actions(pos))
    with pytest.raises(ValueError):
        apf.actions("referee", pos)


REFERENCE = deploy_mod.REFERENCE_DIR / "apf_states.npz"


def test_parity_with_the_partners_scripted_actions_on_recorded_states():
    local_rules, local_deploy = rules_mod.LOCAL_RULES, deploy_mod.LOCAL_DEPLOY
    if not (REFERENCE.exists() and local_rules.exists() and local_deploy.exists()):
        pytest.skip("reference file or local files absent (scripts/nus_export_reference.py)")
    deploy = deploy_mod.load_deploy(local_deploy)
    rules = deploy_mod.apply_overrides(rules_mod.load_rules(local_rules), deploy)
    data = np.load(REFERENCE)
    pos = torch.from_numpy(data["pos"])
    apf = NusApf(rules, deploy)
    strike_err = (apf.strike_actions(pos) - torch.from_numpy(data["strike_actions"])).abs().max().item()
    # The Guard controller picks the nearest Strike drone. Where two different drones are within float32 resolution of equally near,
    # either choice is a correct answer, so a state may differ only if it is such a near-tie, and only a few states may.
    guards, strikes = pos[:, : rules.guard_count], pos[:, rules.guard_count:]
    offsets = strikes[:, None, :, :] - guards[:, :, None, :]  # (states, guard, strike, 2)
    nearest_two = torch.linalg.norm(offsets, dim=-1).sort(dim=-1)
    gap = nearest_two.values[..., 1] - nearest_two.values[..., 0]
    first, second = (torch.gather(offsets, 2, nearest_two.indices[..., k, None, None].expand(-1, -1, 1, 2))[:, :, 0] for k in range(2))
    tie = ((gap <= TOL_LOOSE) & ((first - second).abs().amax(dim=-1) > POS_TOL)).any(dim=-1)  # equally near AND not the same place
    err = (apf.guard_actions(pos) - torch.from_numpy(data["guard_actions"])).abs().amax(dim=(1, 2))
    differ = err > POS_TOL
    guard_err = err[~tie].max().item()
    print(f"\n[apf parity] states={pos.shape[0]}  max |strike action err|={strike_err:.3e}  max |guard action err| outside near-ties={guard_err:.3e}  "
          f"near-tie states={int(tie.sum())}, of which the two controllers chose differently={int((differ & tie).sum())}")
    assert strike_err <= POS_TOL and guard_err <= POS_TOL and not (differ & ~tie).any()
    assert differ.float().mean().item() <= TIE_SHARE_MAX
