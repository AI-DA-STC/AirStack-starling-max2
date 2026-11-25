"""Route 3, stage LS1, task LS1-M1-T3: the skill network (``ste/skill_net.py``; plan
ste_learning/drafts/LS1_TASK_PLAN.md, contracts C2 and C3).

1. The output is clipped and linear inside [-1, 1].      6. The slot and the code change the command.
2. The zeroed inputs cannot change a command.            7. Flying builds no autograd graph.
3. The normaliser clamps a constant input's std.         8. Save, load and every refusal; the preflight's list.
4. A drone that is out gets zero on every path.          9. The game constants are read from the config.
5. One code = the gathered all codes (batch numerics).

No training: the networks are fixed (``tests/_ste_ls1.tiny_net``). CPU only."""
import ast
import dataclasses
import hashlib
from pathlib import Path

import pytest
import torch

from _ste_ls1 import ROOT, SKILLS_GATES, save_tiny_net, team_obs, tiny_net
from _torch_threads import default_torch_threads  # noqa: F401  (autouse: CPU numerics at the default thread count)
from svg_training.core.observations import INTERFACE_VERSION, OBS_DIM, ObsView
from svg_training.ste import exploit, skill_net, skills

V = ObsView()
TOL = 1e-6                    # one code against all codes: rows run in batches of different size (plan constraint 8)
ZEROED = (6, 7, 10, 11)       # tiny_net's default zeroed inputs
FLOOR = 0.0029                # a made-up std floor
SIDES = ("strike", "guard")
MODULE = ROOT / "source" / "svg_training" / "ste" / "skill_net.py"


@pytest.fixture(scope="module")
def gates():
    return exploit.load_gates(SKILLS_GATES)


@pytest.fixture(scope="module")
def cfg(gates):
    return exploit.variant_cfg(gates, "base")


@pytest.fixture(scope="module")
def obs_of(gates):
    """side -> obs [64, 3, OBS_DIM] float32 after 40 ticks of scripted play."""
    return {side: team_obs(gates, side)[1] for side in SIDES}


def live_rows(obs, count=64):
    rows = obs.reshape(-1, OBS_DIM)
    rows = rows[rows[:, V.alive] > 0.5]
    assert rows.shape[0] >= count, f"only {rows.shape[0]} live rows"
    return rows[:count]


def inputs(rows, slot=0, z=0):
    b = rows.shape[0]
    return rows, torch.full((b,), slot, dtype=torch.long), torch.full((b,), z, dtype=torch.long)


def test_the_observations_are_float32(obs_of):
    for side in SIDES:
        assert obs_of[side].dtype == torch.float32 and obs_of[side].shape == (64, 3, OBS_DIM)


# ------------------------------------------------------------------------------------------------ 1
@pytest.mark.parametrize("side", SIDES)
def test_output_is_clipped_linear(side, gates, obs_of):
    net = tiny_net(side, gates)
    with torch.no_grad():
        net.mlp[-1].weight.mul_(100)
        net.mlp[-1].bias.mul_(100)
        rows, slot, z = inputs(live_rows(obs_of[side]))
        out = net(rows, slot, z)
        raw = net(rows, slot, z, clip=False)
    assert out.abs().max() <= 1 and (out.abs() == 1).any()
    assert raw.abs().max() > 1
    assert torch.equal(out, raw.clamp(-1, 1))             # inside [-1, 1] the command is the linear output


# ------------------------------------------------------------------------------------------------ 2
@pytest.mark.parametrize("side", SIDES)
def test_zeroed_inputs_do_not_change_the_command(side, gates, obs_of):
    net = tiny_net(side, gates)
    rows, slot, z = inputs(live_rows(obs_of[side]))
    other = rows.clone()
    gen = torch.Generator().manual_seed(11)
    other[:, list(ZEROED)] = torch.randn(rows.shape[0], len(ZEROED), generator=gen) * 50
    with torch.no_grad():
        assert torch.equal(net(rows, slot, z), net(other, slot, z))
        moved = rows.clone()
        moved[:, 0] += 1.0                                # a kept input (own x) does move it
        assert not torch.equal(net(rows, slot, z), net(moved, slot, z))
    with torch.no_grad():                                 # a stale normaliser cannot leak a zeroed input either
        net.set_normaliser(torch.randn(OBS_DIM, generator=gen), torch.rand(OBS_DIM, generator=gen), FLOOR)
        assert torch.equal(net(rows, slot, z), net(other, slot, z))


# ------------------------------------------------------------------------------------------------ 3
def test_normaliser_clamps_a_constant_input(gates, obs_of):
    net = tiny_net("strike", gates)
    rows, slot, z = inputs(live_rows(obs_of["strike"]))
    std = rows.std(dim=0)
    std[[V.zone_radius, V.arena_half, 0]] = 0.0
    net.set_normaliser(rows.mean(dim=0), std, FLOOR)
    assert net.in_std.min() == torch.tensor(FLOOR)
    assert net.in_std.dtype == torch.float32
    with torch.no_grad():
        assert torch.isfinite(net(rows, slot, z)).all()
    with pytest.raises(ValueError, match="mean and std"):
        net.set_normaliser(torch.zeros(OBS_DIM - 1), std, FLOOR)


# ------------------------------------------------------------------------------------------------ 4
@pytest.mark.parametrize("side", SIDES)
def test_a_drone_that_is_out_gets_zero_on_every_path(side, gates, obs_of):
    net = tiny_net(side, gates)
    assert all((layer.bias != 0).any() for layer in net.mlp if isinstance(layer, torch.nn.Linear))
    obs = obs_of[side].clone()
    out = torch.zeros(obs.shape[:2], dtype=torch.bool)
    out[::2, 1] = True                                    # drone 1 of every other game is out
    out[1::4, 0] = True
    team = obs[..., V.team].clone()
    obs[out] = 0.0                                        # an out drone's row is zero but its team flag (observations.py)
    obs[..., V.team] = team
    live = obs[..., V.alive] > 0.5
    assert out.any() and live.any()
    gen = torch.Generator().manual_seed(3)
    z = torch.randint(0, net.k, obs.shape[:2], generator=gen)
    with torch.no_grad():
        slot = torch.arange(obs.shape[1]).repeat(obs.shape[0])
        fwd = net(obs.reshape(-1, OBS_DIM), slot, z.reshape(-1)).reshape(*obs.shape[:2], skill_net.COMMAND_DIM)
    one = skill_net.one_code(net, obs, z)
    every = skill_net.all_codes(net, obs)
    dead = ~live
    for result in (fwd, one, every):
        assert torch.all(result[dead] == 0)
        assert (result[live] != 0).any()


# ------------------------------------------------------------------------------------------------ 5
@pytest.mark.parametrize("side", SIDES)
def test_one_code_is_the_gathered_all_codes(side, gates, obs_of):
    net = tiny_net(side, gates)
    obs = obs_of[side]
    n, m = obs.shape[:2]
    z = torch.randint(0, net.k, (n, m), generator=torch.Generator().manual_seed(9))
    one = skill_net.one_code(net, obs, z)
    every = skill_net.all_codes(net, obs)
    assert one.shape == (n, m, skill_net.COMMAND_DIM)
    assert every.shape == (n, m, net.k, skill_net.COMMAND_DIM)
    gathered = every.gather(2, z[:, :, None, None].expand(n, m, 1, skill_net.COMMAND_DIM)).squeeze(2)
    torch.testing.assert_close(one, gathered, rtol=0, atol=TOL)
    for k in range(net.k):                                # every code, every drone
        torch.testing.assert_close(skill_net.one_code(net, obs, torch.full((n, m), k)), every[:, :, k], rtol=0, atol=TOL)
    with pytest.raises(ValueError, match="team size"):
        skill_net.one_code(net, obs[:, :2], z[:, :2])
    with pytest.raises(ValueError, match="team size"):
        skill_net.all_codes(net, obs[:, :2])


# ------------------------------------------------------------------------------------------------ 6
@pytest.mark.parametrize("side", SIDES)
def test_slot_and_code_change_the_command(side, gates, obs_of):
    net = tiny_net(side, gates)
    rows = live_rows(obs_of[side])
    with torch.no_grad():
        base = net(*inputs(rows, slot=0, z=0))
        assert not torch.equal(base, net(*inputs(rows, slot=1, z=0)))
        assert not torch.equal(base, net(*inputs(rows, slot=0, z=1)))
        assert torch.equal(base, net(*inputs(rows, slot=0, z=0)))
    assert torch.equal(base, tiny_net(side, gates)(*inputs(rows)).detach())   # the seed fixes the weights


# ------------------------------------------------------------------------------------------------ 7
def test_flying_builds_no_graph(gates, obs_of):
    net = tiny_net("guard", gates)
    obs = obs_of["guard"]
    assert all(p.requires_grad for p in net.parameters())
    assert net(*inputs(live_rows(obs))).requires_grad       # the fit's path does build one
    z = torch.zeros(obs.shape[:2], dtype=torch.long)
    assert not skill_net.one_code(net, obs, z).requires_grad
    assert not skill_net.all_codes(net, obs).requires_grad


# ------------------------------------------------------------------------------------------------ 8
def _rewrite(path: Path, out: Path, **changes) -> tuple[Path, str]:
    """A copy of the saved file ``path`` with payload keys changed; (path, sha256 of the new bytes)."""
    payload = torch.load(path, weights_only=True)
    payload.update(changes)
    torch.save(payload, out)
    return out, hashlib.sha256(out.read_bytes()).hexdigest()


def test_round_trip_and_refusals(tmp_path, gates, cfg, obs_of):
    side = "strike"
    names = skills.team_skills(gates.players, side)
    path, sha = save_tiny_net(tmp_path, side, cfg, gates)
    assert path.is_absolute() and sha == hashlib.sha256(path.read_bytes()).hexdigest()
    payload = torch.load(path, weights_only=True)
    assert set(payload) == {"format", "team", "skills", "team_size", "guards", "strikes", "slot_width", "obs_dim",
                            "interface_version", "hidden", "zeroed_inputs", "std_floor", "scripted_sha256",
                            "game_file", "game_sha256", "game_constants", "provenance", "state_dict"}
    assert payload["format"] == skill_net.FORMAT and payload["obs_dim"] == OBS_DIM
    assert payload["interface_version"] == INTERFACE_VERSION and payload["skills"] == names
    assert not Path(payload["game_file"]).is_absolute()
    game_sha = payload["game_sha256"]
    assert game_sha == gates.games["base"].sha256

    net, meta = skill_net.load_skill_net(path, team=side, skills=names, cfg=cfg, device="cpu", team_size=3,
                                         file_sha256=sha, game_sha256=game_sha)
    assert meta == skill_net.read_skill_net_meta(path) == {k: v for k, v in payload.items() if k != "state_dict"}
    assert not net.training and not any(p.requires_grad for p in net.parameters())
    rows = live_rows(obs_of[side])
    b = rows.shape[0]
    args = (rows, torch.arange(b) % 3, torch.arange(b) % net.k)
    assert torch.equal(net(*args), tiny_net(side, gates)(*args).detach())
    obs = obs_of[side]
    assert torch.equal(skill_net.all_codes(net, obs), skill_net.all_codes(tiny_net(side, gates), obs))

    def load(p=path, **over):
        kw = dict(team=side, skills=names, cfg=cfg, device="cpu", team_size=3, file_sha256=None, game_sha256=None)
        kw.update(over)
        return skill_net.load_skill_net(p, **kw)

    moved = dataclasses.replace(cfg, rules=dataclasses.replace(cfg.rules, keepout_strike_m=1.5))
    assert moved.rules.keepout_strike_m != cfg.rules.keepout_strike_m
    other_format, other_format_sha = _rewrite(path, tmp_path / "format.pt", format="ste-ls1-skill-net-0")
    other_scripts, other_scripts_sha = _rewrite(path, tmp_path / "scripts.pt", scripted_sha256="f" * len(sha))
    other_width, other_width_sha = _rewrite(path, tmp_path / "width.pt", obs_dim=OBS_DIM + 2)
    with pytest.raises(ValueError, match="file sha256"):
        load(file_sha256="0" * len(sha))
    with pytest.raises(ValueError, match="format"):
        load(other_format)
    with pytest.raises(ValueError, match="team: the file is 'strike', expected 'guard'"):
        load(team="guard")
    with pytest.raises(ValueError, match="skills"):
        load(skills=names[::-1])
    with pytest.raises(ValueError, match="team size: the file is 3, expected 2"):
        load(team_size=2)
    with pytest.raises(ValueError, match="scripted_sha256"):
        load(other_scripts)
    with pytest.raises(ValueError, match="game_sha256"):
        load(game_sha256="0" * len(sha))
    with pytest.raises(ValueError, match="game constants.*keepout_strike_m"):
        load(cfg=moved)
    with pytest.raises(ValueError, match="obs width/interface"):
        load(other_width)
    load(team_size=None)                                  # the dispatch checks the team size at the first call

    good_meta = {k: payload[k] for k in skill_net.META_KEYS}
    with pytest.raises(ValueError, match="missing keys \\['provenance'\\]"):
        skill_net.save_skill_net(tmp_path / "bad.pt", net, {k: v for k, v in good_meta.items() if k != "provenance"})
    with pytest.raises(ValueError, match="extra keys \\['note'\\]"):
        skill_net.save_skill_net(tmp_path / "bad.pt", net, dict(good_meta, note="x"))
    assert not (tmp_path / "bad.pt").exists()
    assert list(tmp_path.glob("*.tmp.*")) == []

    def problems(p=path, **over):
        kw = dict(sha256=sha, team=side, skills=names, team_size=3, cfg=cfg, game_file=payload["game_file"],
                  game_sha256=game_sha)
        kw.update(over)
        return skill_net.net_problems(p, **kw)

    assert problems() == []
    faults = {"missing file": problems(tmp_path / "nope.pt"),
              "not filled": problems(sha256="FILL_after the distillation"),
              "file sha256": problems(sha256="0" * len(sha)),
              "format": problems(other_format, sha256=other_format_sha),
              "team": problems(team="guard"),
              "skills": problems(skills=names[::-1]),
              "team size": problems(team_size=2),
              "scripted_sha256": problems(other_scripts, sha256=other_scripts_sha),
              "game_file": problems(game_file="configs/ste_l011/other.toml"),
              "game_sha256": problems(game_sha256="0" * len(sha)),
              "game constants": problems(cfg=moved),
              "obs width/interface": problems(other_width, sha256=other_width_sha)}
    for word, found in faults.items():
        assert len(found) == 1 and word in found[0], (word, found)


def test_the_fill_mark_is_the_gate_files_one():
    assert skill_net.FILL_MARK == exploit.FILL_MARK


def test_no_import_from_skills_exploit_or_export():
    """Import direction (plan LS1-M1-T3): exploit imports skills, export imports exploit; skill_net imports none."""
    tree = ast.parse(MODULE.read_text())
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            names |= {node.module or ""} | {a.name for a in node.names}
        elif isinstance(node, ast.Import):
            names |= {a.name for a in node.names}
    assert not {n for n in names if n.split(".")[-1] in ("skills", "exploit", "export")}, names


# ------------------------------------------------------------------------------------------------ 9
def test_game_constants_are_read_from_the_config(cfg):
    want = {"pad_guards": cfg.pad_guards, "pad_strikes": cfg.pad_strikes,
            "keepout_strike_m": cfg.rules.keepout_strike_m, "keepout_guard_m": cfg.rules.keepout_guard_m,
            "wall_margin_m": cfg.arena.wall_margin_m, "height_band_m": list(cfg.arena.height_band_m),
            "starling_enabled": cfg.starling.enabled, "guard_speed_mps": cfg.team_speed_mps("guard"),
            "strike_speed_mps": cfg.team_speed_mps("strike")}
    got = skill_net.game_constants(cfg)
    assert got == want and set(got) == set(want) and len(got) == 9
    moved = dataclasses.replace(cfg, rules=dataclasses.replace(cfg.rules, keepout_strike_m=1.5))
    after = skill_net.game_constants(moved)
    assert {k for k in got if after[k] != got[k]} == {"keepout_strike_m"} and after["keepout_strike_m"] == 1.5
