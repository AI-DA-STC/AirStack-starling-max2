"""Route 3 (stage LS1), merge M3: the export of a team and of the skill network (``ste/export.py``,
``scripts/ste_l6_export.py``; plan ste_learning/drafts/LS1_TASK_PLAN.md section 4, tasks LS1-M3-T1 to LS1-M3-T4).

LS1-M3-T1, the export's variant is no longer fixed to "base": ``golden_observations``, ``_dispatch``,
``export_policy``, ``_interface`` and ``ste_l6_export.team_outputs`` take a trailing keyword ``variant`` (default
"base"). Without it the export is the same bytes as before (ONNX files and ``interface.toml``); with another variant
the golden observations, the dispatch and ``interface.toml`` use that variant's game and its ``train_seed`` of the
side, and ``interface.toml`` names the variant (``variant = "<name>"``, written only for a variant other than base,
OP-24). A variant the gate file does not hold is refused before anything is written; the export command takes the
run's own variant from ``results.json`` (default "base") and refuses (exit 2) one its gate file copy does not hold.

LS1-M3-T2, the skill network as an ONNX graph, its stand-alone folder and reload: ``skill_net_onnx`` exports a
``SkillNet`` with three inputs (``obs`` f32 [B, OBS_DIM], ``slot`` and ``z`` i64 [B]) and the one-hot, the input scale
and the alive rule inside the graph; ``export_skill_net`` writes ``skill_net_<side>.onnx`` and ``interface.toml``
(schema ``ste-check-skillnet-0``, a ``[skill_net]`` section and ``[[skill_net_golden]]`` rows of every code for every
drone); ``reload_check`` reads such a folder in a fresh process on onnxruntime and onnx's ReferenceEvaluator and
refuses damage. Codes and slots out of range are refused before any runtime runs (``run_skill_net``), because
onnxruntime's OneHot runs z = k and z = -1 without an error.

LS1-M3-T3, a route 3 team's folder: a two-level team flown by its skill network (``skill_source = "net"``) exports its
heads files (schema ``ste-check-skills-net-0`` in ``interface.toml`` and in every heads file, the skill lists with
``skill_source`` and ``skill_net_sha256``), its skill network's graph (``skill_net_<side>.onnx``, ``[skill_net]``,
``[[skill_net_golden]]``) and golden commands that are the network's. The reload checks the heads as for the scripts
route (its skill lists with the two keys more), then ``_skills_net_reload``: the network's own golden rows, the lists,
the team size, the game, the heads and flown codes exactly (scripts dispatch for ``greedy`` and ``resolve`` only) and
the commands from the ONNX skill network on the flown codes (range-checked first), on both runtimes. A scripts team's
export and reload are as before.

LS1-M3-T4, ``ste_l6_export.py --skill-net`` (job LS1.3): ``export.golden_observations_cfg`` (no gate file; equal to
``golden_observations``) and the command's stand-alone branch: the network's own game file and team sizes, its
preflight (``--side`` given and the network's team, the game file's sha256, ``skill_net.net_problems``), the folder and
its two controls (``ctl_net_equals_export``, ``ctl_reload_fresh_process``); refusals exit 2 (the parser's mutually
exclusive group exits through SystemExit 2), a failed control exits 6.

CPU only; needs onnxruntime (the file skips itself without it, as tests/test_ste_l3_export.py does)."""
import json
import sys
import tomllib
from pathlib import Path

import numpy as np
import pytest
import torch

pytest.importorskip("onnxruntime")

import _ste_ls1  # noqa: E402
import test_ste_l3_export as tx  # noqa: E402
from _ste_tools import SCRIPTS  # noqa: E402
from svg_training.core.observations import OBS_DIM, ObsView  # noqa: E402
from svg_training.ste import exploit, export, skill_net  # noqa: E402
from test_ste_l3_pool import POOL, SMOKE, TWO_LEVEL  # noqa: E402

sys.path.insert(0, str(SCRIPTS))
import ste_l6_export as cli  # noqa: E402

OTHER = "tag_1p2"                  # a second variant of configs/ste_l012/smoke_gates.toml (its own game and seeds)
SIDE = "strike"


@pytest.fixture(scope="module")
def two_level(tmp_path_factory):
    """(gates file, gates, saved): the smoke gate file with the pool and the two-level skills route, and a tiny
    learner's ``saved()`` on it (trained on base: the variant does not change the checkpoint's shape)."""
    path = tmp_path_factory.mktemp("ls1_export_gates") / "gates.toml"
    path.write_text(SMOKE.read_text() + POOL + TWO_LEVEL)
    gates = exploit.load_gates(path)
    return path, gates, _ste_ls1.tiny_learner_saved(gates, SIDE)


@pytest.fixture
def asked_variants(monkeypatch):
    """Every game name ``exploit.variant_cfg`` is asked for from now on (the export's call sites included)."""
    asked = []
    real = exploit.variant_cfg

    def recording(gates, variant, *args, **kwargs):
        asked.append(variant)
        return real(gates, variant, *args, **kwargs)
    monkeypatch.setattr(exploit, "variant_cfg", recording)
    return asked


@pytest.mark.parametrize(("route", "side"), [("velocity", "guard"), ("skills", "strike")], ids=["velocity", "skills"])
def test_export_without_variant_equals_variant_base_bit_for_bit(route, side, tmp_path):
    gates, learner = tx.tiny_learner(route, side)
    saved = learner.saved()
    obs = export.golden_observations(gates, side, games=4, seed=5)
    assert torch.equal(obs, export.golden_observations(gates, side, games=4, seed=5, variant="base"))
    plain = export.export_policy(saved, gates, side, tmp_path / "plain", obs)
    named = export.export_policy(saved, gates, side, tmp_path / "named", obs, variant="base")
    text = (plain / "interface.toml").read_text()
    assert text == (named / "interface.toml").read_text()
    meta = tomllib.loads(text)
    assert "variant" not in meta and meta["seed"] == int(gates.variants["base"]["train_seed"][side])
    for f in meta["files"]:
        assert (plain / f["file"]).read_bytes() == (named / f["file"]).read_bytes(), f["file"]


def test_a_second_variant_exports_with_its_own_seed_and_game(two_level, asked_variants, tmp_path):
    _, gates, saved = two_level
    base_cfg, other_cfg = exploit.variant_cfg(gates, "base"), exploit.variant_cfg(gates, OTHER)
    asked_variants.clear()
    obs = export.golden_observations(gates, SIDE, games=4, variant=OTHER)
    folder = export.export_policy(saved, gates, SIDE, tmp_path / "e", obs, variant=OTHER)
    assert asked_variants and set(asked_variants) == {OTHER}, asked_variants       # no call site left on base
    meta = tomllib.loads((folder / "interface.toml").read_text())
    game = gates.games[gates.variants[OTHER]["game"]]
    seed = int(gates.variants[OTHER]["train_seed"][SIDE])
    assert meta["variant"] == OTHER
    assert meta["seed"] == seed != int(gates.variants["base"]["train_seed"][SIDE])
    assert meta["game_file"] == str(game.file) and meta["game_sha256"] == game.sha256
    assert meta["game_sha256"] != gates.games[gates.variants["base"]["game"]].sha256
    assert meta["tag_radius_m"] == float(other_cfg.tag.radius_m) != float(base_cfg.tag.radius_m)
    assert meta["gates_sha256"] == gates.sha256 and meta["policy_schema"] == export.SCHEMAS["skills"]
    r = tx.reload_in_a_fresh_process(folder)        # the reload plays the skills on the exported (variant's) game
    assert r.returncode == 0, r.stderr[-2000:]
    assert json.loads(r.stdout.strip().splitlines()[-1])["ok"]


def test_an_unknown_variant_is_refused(two_level, tmp_path):
    _, gates, saved = two_level
    unknown = "base_typo"
    with pytest.raises(ValueError, match="not in the gate file"):
        export.golden_observations(gates, SIDE, games=2, variant=unknown)
    with pytest.raises(ValueError, match="not in the gate file"):
        export._dispatch(gates, SIDE, 2, variant=unknown)
    obs = export.golden_observations(gates, SIDE, games=2)
    with pytest.raises(ValueError, match="not in the gate file"):
        export.export_policy(saved, gates, SIDE, tmp_path / "never", obs, variant=unknown)
    assert not (tmp_path / "never").exists()                                     # refused before anything is written
    game_key = next(iter(gates.games))           # a [games] key that is not a variant name is refused too
    if game_key not in gates.variants:
        with pytest.raises(ValueError, match="not in the gate file"):
            export.golden_observations(gates, SIDE, games=2, variant=game_key)
    with pytest.raises(ValueError, match="not in the gate file"):
        cli.team_outputs(saved, gates, SIDE, obs, variant=unknown)


def _run_folder(where, gates_file, gates, saved, **res) -> Path:
    """A finished run folder as scripts/ste_exploit_l012.py leaves it, for the export command: the gate file copy,
    its pin, ``results.json`` (complete, the side, the gate sha, plus ``res``) and ``agent_final.pt``."""
    where.mkdir(parents=True)
    (where / cli.GATES_COPY).write_text(gates_file.read_text())
    (where / cli.PINNED_SHA).write_text(gates.sha256 + "\n")
    (where / cli.RESULTS).write_text(json.dumps({"complete": True, "side": SIDE, "gates_sha256": gates.sha256, **res}))
    torch.save(saved, where / cli.AGENT)
    return where


def test_the_export_command_takes_the_runs_variant(two_level, asked_variants, tmp_path):
    gates_file, gates, saved = two_level
    run = _run_folder(tmp_path / "run_other", gates_file, gates, saved, variant=OTHER)
    asked_variants.clear()
    assert cli.main(["--run-dir", str(run), "--out", str(tmp_path / "out_other"), "--games", "2"]) == 0
    assert asked_variants and set(asked_variants) == {OTHER}, asked_variants
    meta = tomllib.loads((tmp_path / "out_other" / "interface.toml").read_text())
    assert meta["variant"] == OTHER and meta["seed"] == int(gates.variants[OTHER]["train_seed"][SIDE])
    assert meta["game_sha256"] == gates.games[gates.variants[OTHER]["game"]].sha256
    controls = json.loads((tmp_path / "out_other" / "controls.json").read_text())
    assert controls["ctl_team_equals_export"]["status"] == cli.PASS

    plain = _run_folder(tmp_path / "run_plain", gates_file, gates, saved)        # no "variant" key: base
    assert cli.main(["--run-dir", str(plain), "--out", str(tmp_path / "out_plain"), "--games", "2"]) == 0
    meta = tomllib.loads((tmp_path / "out_plain" / "interface.toml").read_text())
    assert "variant" not in meta and meta["seed"] == int(gates.variants["base"]["train_seed"][SIDE])

    bad = _run_folder(tmp_path / "run_bad", gates_file, gates, saved, variant="base_typo")
    assert cli.main(["--run-dir", str(bad), "--out", str(tmp_path / "out_bad"), "--games", "2"]) == 2
    assert not (tmp_path / "out_bad" / "interface.toml").exists()



# ------------------------------------------------------------------ LS1-M3-T2: the skill network as an ONNX graph
ALIVE = ObsView().alive
SKILLS_GATES = exploit.load_gates(_ste_ls1.SKILLS_GATES)


def _rows(net, obs):
    """Every code for every drone of ``obs`` [G, M, OBS_DIM], in the row order of ``skill_net.all_codes``: (obs rows
    [G*M*K, OBS_DIM] f32, slot [G*M*K] i64, z [G*M*K] i64) as numpy."""
    g, m = obs.shape[:2]
    rows = obs.reshape(g * m, OBS_DIM).repeat_interleave(net.k, dim=0).numpy()
    slot = np.repeat(np.tile(np.arange(m, dtype=np.int64), g), net.k)
    z = np.tile(np.arange(net.k, dtype=np.int64), g * m)
    return rows, slot, z


def _runtimes(model):
    """(onnxruntime session, ReferenceEvaluator) of an in-memory ONNX model."""
    import onnxruntime as ort
    from onnx.reference import ReferenceEvaluator
    sess = ort.InferenceSession(model.SerializeToString(), providers=["CPUExecutionProvider"])
    return sess, ReferenceEvaluator(model)


def _with_an_out_drone(obs):
    """``obs`` with drone 1 of game 0 marked out (alive 0), its other values left as they were (a hand-made row)."""
    obs = obs.clone()
    obs[0, 1, ALIVE] = 0.0
    return obs


@pytest.fixture(scope="module", params=["guard", "strike"])
def tiny_skill_net(request, tmp_path_factory):
    """(side, net, meta, net path, net sha256, golden obs [4, 3, OBS_DIM]) for a tiny skill network of each side."""
    side = request.param
    net, meta, path, sha = _ste_ls1.tiny_skill_net(tmp_path_factory.mktemp(f"skill_net_{side}"), side, SKILLS_GATES)
    _, obs = _ste_ls1.team_obs(SKILLS_GATES, side, n=4, ticks=30)
    return side, net, meta, path, sha, _with_an_out_drone(obs)


@pytest.fixture(scope="module")
def skill_net_folder(tiny_skill_net, tmp_path_factory):
    side, net, meta, path, sha, obs = tiny_skill_net
    out = tmp_path_factory.mktemp(f"skill_net_export_{side}") / "skill_net"
    return export.export_skill_net(net, meta, side, out, obs, net_file=path)


def test_the_skill_net_graph_takes_obs_slot_z_and_computes_the_network(tiny_skill_net):
    side, net, _, _, _, obs = tiny_skill_net
    m = export.skill_net_onnx(net, side, list(net.skills))
    import onnx
    elem = onnx.TensorProto
    inputs = [(i.name, i.type.tensor_type.elem_type) for i in m.graph.input]
    assert inputs == [("obs", elem.FLOAT), ("slot", elem.INT64), ("z", elem.INT64)]
    assert [o.name for o in m.graph.output] == ["command"]
    assert m.graph.input[0].type.tensor_type.shape.dim[1].dim_value == OBS_DIM
    ops = {n.op_type for n in m.graph.node}
    assert "OneHot" in ops and "Clip" in ops and "Mul" in ops, ops
    props = {p.key: p.value for p in m.metadata_props}
    assert props["status"] == export.STATUS and props["policy_schema"] == export.SKILL_NET_SCHEMA
    assert props["team"] == side and json.loads(props["skills"]) == list(net.skills)
    assert int(props["slot_width"]) == net.slot_width and int(props["k"]) == net.k
    rows, slot, z = _rows(net, obs)                                  # G x M x K rows, a batch far from 1
    want = skill_net.all_codes(net, obs).reshape(-1, skill_net.COMMAND_DIM).numpy()
    sess, ref = _runtimes(m)
    for got in (sess.run(None, {"obs": rows, "slot": slot, "z": z})[0],
                ref.run(None, {"obs": rows, "slot": slot, "z": z})[0]):
        ok, diff, _ = export.within(got, want)
        assert ok, diff
    with pytest.raises(ValueError, match="team"):
        export.skill_net_onnx(net, "guard" if side == "strike" else "strike", list(net.skills))
    with pytest.raises(ValueError, match="skills"):
        export.skill_net_onnx(net, side, list(net.skills)[::-1])


def test_the_input_scale_and_alive_rule_are_in_the_graph(tiny_skill_net):
    import copy
    side, net, _, _, _, obs = tiny_skill_net
    rows, slot, z = _rows(net, obs)
    feed = {"obs": rows, "slot": slot, "z": z}
    before = _runtimes(export.skill_net_onnx(net, side, list(net.skills)))[0].run(None, feed)[0]
    scaled = copy.deepcopy(net)
    kept = [i for i in range(OBS_DIM) if i not in net.zeroed_inputs and i != ALIVE]
    with torch.no_grad():
        scaled.in_std[kept] *= 3.0
        scaled.in_mean[kept] += 0.25
    model = export.skill_net_onnx(scaled, side, list(scaled.skills))
    sess, ref = _runtimes(model)
    after = sess.run(None, feed)[0]
    assert not np.allclose(after, before)                          # the scale buffers are inside the graph
    want = skill_net.all_codes(scaled, obs).reshape(-1, skill_net.COMMAND_DIM).numpy()
    assert export.within(after, want)[0]
    out_rows = rows[:, ALIVE] == 0                                  # the hand-made out drone, K rows (and any other)
    assert out_rows.sum() >= net.k
    for got in (after, ref.run(None, feed)[0]):
        assert np.all(got[out_rows] == 0.0)                         # exactly zero: the alive multiply is in the graph
        assert np.any(got[~out_rows] != 0.0)


def test_a_skill_net_folder_reloads_in_a_fresh_process(tiny_skill_net, skill_net_folder):
    side, net, meta, path, sha, obs = tiny_skill_net
    folder = skill_net_folder
    r = tx.reload_in_a_fresh_process(folder)
    assert r.returncode == 0, r.stderr[-2000:]
    out = json.loads(r.stdout.strip().splitlines()[-1])
    g, m = obs.shape[:2]
    assert out["ok"] and out["route"] == "skill_net" and out["status"] == export.STATUS
    assert out["skill_net_golden_rows"] == g * m * net.k
    assert out["skill_net_max_abs_diff"] <= export.GOLDEN_ATOL + export.GOLDEN_RTOL
    assert sorted(out["runtimes"]) == ["onnx.reference", "onnxruntime"]


def test_the_skill_net_folder_holds_the_graph_and_its_interface(tiny_skill_net, skill_net_folder):
    side, net, meta, path, sha, obs = tiny_skill_net
    folder = skill_net_folder
    assert sorted(p.name for p in folder.iterdir()) == ["interface.toml", f"skill_net_{side}.onnx"]
    data = tomllib.loads((folder / "interface.toml").read_text())
    assert data["policy_schema"] == export.SKILL_NET_SCHEMA == "ste-check-skillnet-0"
    assert data["status"] == export.STATUS and data["team"] == side and data["obs_dim"] == OBS_DIM
    assert data["game_file"] == meta["game_file"] and data["game_sha256"] == meta["game_sha256"]
    assert data["scripted_sha256"] == meta["scripted_sha256"]
    assert "files" not in data and "golden" not in data                # no heads files: the net is the folder
    sn = data["skill_net"]
    assert sn["file"] == f"skill_net_{side}.onnx" and sn["sha256"] == export.sha256_file(folder / sn["file"])
    assert sn["net_file"] == str(path) and sn["net_sha256"] == sha    # outside svg_training/: the path as given
    assert sn["skills"] == list(net.skills) and sn["k"] == net.k and sn["slot_width"] == net.slot_width
    assert sn["team_size"] == net.team_size and sn["zeroed_inputs"] == net.zeroed_inputs
    assert sn["alive_rule"] == f"inside the graph: command times obs[{ALIVE}]"
    assert "z = index in skills" in sn["code_rule"] and "refuses" in sn["input_check"]
    golden = data["skill_net_golden"]
    assert len(golden) == obs.shape[0]
    want = skill_net.all_codes(net, obs)
    assert np.asarray([row["commands"] for row in golden], dtype=np.float32).tobytes() == want.numpy().tobytes()
    assert np.asarray([row["obs"] for row in golden], dtype=np.float32).tobytes() == obs.numpy().tobytes()
    assert export.ROUTE_OF_SCHEMA == {**{v: (k, None) for k, v in export.SCHEMAS.items()},
                                      export.SKILL_NET_SCHEMA: ("skill_net", None),
                                      export.SKILLS_NET_SCHEMA: ("skills", "net")}         # + LS1-M3-T3's entry
    assert export.SCHEMAS == {"velocity": "ste-check-velocity-0", "skills": "ste-check-skills-0"}


def test_the_net_file_is_written_repository_relative(tmp_path):
    inside = exploit.ROOT / "ste_provisional" / "skill_nets" / "2026-11-26_ls1_guard" / "skill_net_guard.pt"
    assert export.repo_relative(inside) == "ste_provisional/skill_nets/2026-11-26_ls1_guard/skill_net_guard.pt"
    assert export.repo_relative(tmp_path / "n.pt") == str((tmp_path / "n.pt").resolve())


def _damage(folder, how):
    import onnx
    data = tomllib.loads((folder / "interface.toml").read_text())
    if how == "bytes":
        f = folder / data["skill_net"]["file"]
        m = onnx.load(str(f))
        m.doc_string = "changed"
        onnx.save(m, str(f))
    elif how == "status":
        path = folder / "interface.toml"
        path.write_text(path.read_text().replace(f'status = "{export.STATUS}"\n', ""))
    elif how == "skills":
        tx.tamper(folder, "skills", lambda v: v[::-1])
    else:
        tx.tamper(folder, "commands", lambda v: tx._bump(v, 1e-3))


@pytest.mark.parametrize("how,why", [("bytes", "sha256"), ("status", "status"), ("skills", "skills"),
                                     ("golden", "golden")])
def test_the_skill_net_reload_refuses_damage(skill_net_folder, tmp_path, how, why):
    import shutil
    copy = tmp_path / "copy"
    shutil.copytree(skill_net_folder, copy)
    export.reload_check(copy)                                           # the undamaged copy passes
    _damage(copy, how)
    with pytest.raises(ValueError, match=why):
        export.reload_check(copy)


def test_codes_out_of_range_are_refused_before_the_runtime(tiny_skill_net, skill_net_folder, monkeypatch):
    side, net, _, _, _, obs = tiny_skill_net
    rows, slot, z = _rows(net, obs)
    k, width = net.k, net.slot_width
    assert export.inputs_problem(slot, z, width, k) is None
    for bad_z in (k, -1):
        zz = z.copy()
        zz[3] = bad_z
        assert "z" in export.inputs_problem(slot, zz, width, k)
    for bad_slot in (width, -1):
        ss = slot.copy()
        ss[5] = bad_slot
        assert "slot" in export.inputs_problem(ss, z, width, k)
    assert "int64" in export.inputs_problem(slot.astype(np.int32), z, width, k)
    assert "int64" in export.inputs_problem(slot, z.astype(np.int32), width, k)
    # run_skill_net, the one door to the runtimes (the reload, and a team folder's flown codes in LS1-M3-T3): the
    # range check comes first, so no runtime is built or run for a refused input
    import onnx.reference
    import onnxruntime

    def no_runtime(*args, **kwargs):
        raise AssertionError("a runtime was started for an input out of range")
    onnx_file = skill_net_folder / f"skill_net_{side}.onnx"
    good = export.run_skill_net(onnx_file, rows, slot, z, width, k)
    assert sorted(good) == ["onnx.reference", "onnxruntime"]
    monkeypatch.setattr(onnxruntime, "InferenceSession", no_runtime)
    monkeypatch.setattr(onnx.reference, "ReferenceEvaluator", no_runtime)
    for bad_z in (k, -1):
        zz = z.copy()
        zz[0] = bad_z
        with pytest.raises(ValueError, match="z outside"):
            export.run_skill_net(onnx_file, rows, slot, zz, width, k)


# ------------------------------------------------------------------ LS1-M3-T3: a route 3 team's folder and its reload
SIX_KEYS = {"team", "players", "choice", "team_strategies", "drone_skills", "free_index"}      # the scripts route's JSON
SCRIPTS_RELOAD_KEYS = {"ok", "runtimes", "max_abs_diff", "golden_rows", "route", "status", "output_scale", "tolerance",
                       "choices_equal", "skill_lists_equal", "commands_max_abs_diff"}             # reload_check today
EVIDENCE = exploit.ROOT / "records" / "evidence" / "2026-11-25_ste_l3_l6_pipeline" / "exports"
NET_MESSAGE = r"skills golden rows \(skill network\)"          # the net branch's own refusal of the golden rows


def _props(path) -> dict:
    import onnx
    return {p.key: p.value for p in onnx.load(str(path)).metadata_props}


@pytest.fixture(scope="module")
def net_gates(tmp_path_factory):
    """(gates, nets {side: (file, sha256)}): the skills gate file flown by a tiny skill network of each side (OP-35)."""
    path, nets = _ste_ls1.net_gates_file(tmp_path_factory.mktemp("ls1_net_gates"))
    return exploit.load_gates(path), nets


@pytest.fixture(scope="module", params=["guard", "strike"])
def route3_folder(request, net_gates, tmp_path_factory):
    """(side, gates, nets, folder, obs [4, 3, OBS_DIM]): a route 3 team's export (a tiny learner on the net gate file;
    golden observations with a hand-made out drone)."""
    side = request.param
    gates, nets = net_gates
    obs = _with_an_out_drone(export.golden_observations(gates, side, games=4))
    folder = export.export_policy(_ste_ls1.tiny_learner_saved(gates, side), gates, side,
                                  tmp_path_factory.mktemp(f"route3_{side}") / "team", obs)
    return side, gates, nets, folder, obs


@pytest.fixture(scope="module")
def route3_reload(route3_folder):
    r = tx.reload_in_a_fresh_process(route3_folder[3])
    assert r.returncode == 0, r.stderr[-2000:]
    return json.loads(r.stdout.strip().splitlines()[-1])


def _net_of(gates, side):
    """The side's network as the export flew it (the net dispatch's own)."""
    return export._dispatch(gates, side, 1).net


def test_a_route3_team_folder_holds_heads_and_its_skill_net(route3_folder):
    side, gates, nets, folder, obs = route3_folder
    g, m = obs.shape[:2]
    heads = [f"policy_{side}_{slot}.onnx" for slot in range(m)]
    assert sorted(p.name for p in folder.iterdir()) == sorted(heads + [f"skill_net_{side}.onnx", "interface.toml"])
    data = tomllib.loads((folder / "interface.toml").read_text())
    assert data["policy_schema"] == export.SKILLS_NET_SCHEMA == "ste-check-skills-net-0"
    d = export._dispatch(gates, side, g)
    want_json = export.skills.skills_meta(d)
    assert want_json["skill_source"] == "net" and want_json["skill_net_sha256"] == nets[side][1]
    assert [f["file"] for f in data["files"]] == heads                      # the net file is not a heads file
    for name in heads:
        props = _props(folder / name)
        assert json.loads(props["skills"]) == want_json, name
        assert props["policy_schema"] == export.SKILLS_NET_SCHEMA
    sk = data["skills"]
    assert sk["skill_source"] == "net" and sk["skill_net_sha256"] == nets[side][1]
    assert sk["players"] == list(d.names)
    net = d.net
    sn = data["skill_net"]
    assert sn["file"] == f"skill_net_{side}.onnx" and sn["sha256"] == export.sha256_file(folder / sn["file"])
    assert sn["net_file"] == str(Path(nets[side][0]).resolve()) and sn["net_sha256"] == nets[side][1]
    assert sn["skills"] == sk["players"] and sn["k"] == net.k and sn["slot_width"] == net.slot_width
    assert sn["team_size"] == net.team_size == data["slots"] == m
    assert sn["alive_rule"] == f"inside the graph: command times obs[{ALIVE}]"
    assert _props(folder / sn["file"])["policy_schema"] == export.SKILL_NET_SCHEMA    # the graph's own schema
    golden = data["skill_net_golden"]
    assert np.asarray([r["commands"] for r in golden], dtype=np.float32).tobytes() == \
        skill_net.all_codes(net, obs).numpy().tobytes()
    flown = torch.tensor([r["flown"] for r in data["golden"]])
    command = torch.tensor([r["command"] for r in data["golden"]], dtype=torch.float32)
    assert torch.equal(command, skill_net.one_code(net, obs, flown))       # the golden commands are the network's


def test_the_route3_reload_passes_in_a_fresh_process(route3_folder, route3_reload):
    side, gates, nets, folder, obs = route3_folder
    out = route3_reload
    g, m = obs.shape[:2]
    assert out["ok"] and out["choices_equal"] and out["skill_lists_equal"] and out["scripted_sha256_now_equal"]
    assert out["golden_rows"] == g * m and out["skill_net_golden_rows"] == g * m * _net_of(gates, side).k
    for key in ("max_abs_diff", "commands_max_abs_diff", "skill_net_max_abs_diff"):
        assert out[key] <= export.GOLDEN_ATOL + export.GOLDEN_RTOL * max(out["output_scale"], 1.0), key


def test_the_route3_reload_returns_route_skills_and_source_net(route3_folder, route3_reload):
    side, gates, nets, folder, obs = route3_folder
    assert route3_reload["route"] == "skills" and route3_reload["skill_source"] == "net"
    data = tomllib.loads((folder / "interface.toml").read_text())
    assert data["policy_schema"] == "ste-check-skills-net-0"
    for f in data["files"]:
        assert _props(folder / f["file"])["policy_schema"] == "ste-check-skills-net-0", f["file"]
    assert export.schema_of("skills", True) == "ste-check-skills-net-0"
    assert export.schema_of("skills", False) == "ste-check-skills-0"
    assert export.schema_of("velocity", False) == "ste-check-velocity-0"


def test_the_route3_reload_flies_the_onnx_net_not_the_scripts(route3_folder, monkeypatch):
    side, gates, nets, folder, obs = route3_folder

    def no(*args, **kwargs):
        raise AssertionError("the reload flew the scripts or the torch network")
    for owner, name in ((export.skills.SkillDispatch, "commands"), (export.skills.SkillDispatch, "act"),
                        (export.skills.NetTwoLevelDispatch, "commands"), (export.skills.NetTwoLevelDispatch, "act"),
                        (skill_net, "one_code"), (skill_net, "all_codes")):
        monkeypatch.setattr(owner, name, no)
    out = export.reload_check(folder)
    assert out["ok"] and out["skill_source"] == "net" and out["choices_equal"]


def test_a_scripts_team_export_is_unchanged_by_the_net_branch(tmp_path):
    gates = SKILLS_GATES
    side = SIDE
    obs = export.golden_observations(gates, side, games=4)
    folder = export.export_policy(_ste_ls1.tiny_learner_saved(gates, side), gates, side, tmp_path / "scripts", obs)
    data = tomllib.loads((folder / "interface.toml").read_text())
    evidence = tomllib.loads((EVIDENCE / f"skills_{side}_interface.toml").read_text())
    source_keys = {"source_run", "source_checkpoint", "source_checkpoint_sha256"}    # the evidence came from a run
    assert set(data) == set(evidence) - source_keys
    assert set(data["skills"]) == set(evidence["skills"]) and "skill_source" not in data["skills"]
    assert "skill_net" not in data and "skill_net_golden" not in data
    assert set(data["golden"][0]) == set(evidence["golden"][0])
    assert data["policy_schema"] == evidence["policy_schema"] == "ste-check-skills-0"
    assert sorted(p.name for p in folder.iterdir()) == sorted([f["file"] for f in data["files"]] + ["interface.toml"])
    for f in data["files"]:
        props = _props(folder / f["file"])
        assert set(json.loads(props["skills"])) == SIX_KEYS and props["policy_schema"] == "ste-check-skills-0"
    out = export.reload_check(folder)
    assert set(out) == SCRIPTS_RELOAD_KEYS and out["route"] == "skills"
    assert not any(k.startswith("skill_net") or k == "skill_source" for k in out)


def _set_first(folder, key, value):
    """The first ``key = [...]`` line of interface.toml (golden row 0) with its first element set to ``value``."""
    tx.tamper(folder, key, lambda v: [value] + v[1:])


def _copy(folder, tmp_path):
    import shutil
    copy = tmp_path / "copy"
    shutil.copytree(folder, copy)
    return copy


@pytest.mark.parametrize("how", ["command", "flown_other", "flown_k", "flown_minus_1", "skills", "team_size",
                                 "no_skill_net_section"])
def test_the_route3_reload_refuses_tampering(route3_folder, tmp_path, how):
    side, gates, nets, folder, obs = route3_folder
    copy = _copy(folder, tmp_path)
    data = tomllib.loads((copy / "interface.toml").read_text())
    k = data["skill_net"]["k"]
    first = data["golden"][0]["flown"][0]
    if how == "command":                       # the heads pass; the net branch's golden commands refuse it
        tx.tamper(copy, "command", lambda v: tx._bump(v, 1e-3))
        why = NET_MESSAGE + ".*commands"
    elif how == "flown_other":                 # another code in range: the choices differ
        _set_first(copy, "flown", (first + 1) % k)
        why = NET_MESSAGE + ".*choices equal False"
    elif how == "flown_k":                     # flown feeds z: out of range, refused before any runtime
        _set_first(copy, "flown", k)
        why = "z outside"
    elif how == "flown_minus_1":
        _set_first(copy, "flown", -1)
        why = "z outside"
    elif how == "skills":                      # [skill_net].skills reversed (the first "skills = " line)
        tx.tamper(copy, "skills", lambda v: v[::-1])
        why = "skills"
    elif how == "team_size":                   # [skill_net].team_size = 2
        tx.tamper(copy, "team_size", lambda v: 2)
        why = "team size"
    else:                                      # the [skill_net] section left out: a refusal, not a KeyError
        path = copy / "interface.toml"
        text = path.read_text()
        start, stop = text.index("\n[skill_net]\n"), text.index("\n[[files]]\n")
        path.write_text(text[:start] + text[stop:])
        why = "has no"
    with pytest.raises(ValueError, match=why):
        export.reload_check(copy)


@pytest.mark.parametrize("where", ["heads_file", "interface"])
def test_a_route3_heads_file_with_tampered_skills_json_is_refused_by_the_heads_loop(route3_folder, tmp_path,
                                                                                   monkeypatch, where):
    import onnx
    side, gates, nets, folder, obs = route3_folder
    copy = _copy(folder, tmp_path)
    interface = copy / "interface.toml"
    if where == "heads_file":                  # a heads file carrying the scripts route's six keys, its sha rewritten
        data = tomllib.loads(interface.read_text())
        f = data["files"][1]
        m = onnx.load(str(copy / f["file"]))
        for p in m.metadata_props:
            if p.key == "skills":
                p.value = json.dumps({k: v for k, v in json.loads(p.value).items() if k in SIX_KEYS}, sort_keys=True)
        onnx.save(m, str(copy / f["file"]))
        interface.write_text(interface.read_text().replace(f["sha256"], export.sha256_file(copy / f["file"])))
    else:                                      # interface.toml's [skills] names another network
        tx.tamper(copy, "skill_net_sha256", lambda v: "0" * len(v))

    def not_reached(*args, **kwargs):
        raise AssertionError("_skills_net_reload ran")
    monkeypatch.setattr(export, "_skills_net_reload", not_reached)
    with pytest.raises(ValueError, match="skill lists in interface.toml"):
        export.reload_check(copy)


def test_a_drone_that_is_out_has_a_zero_command(route3_folder):
    side, gates, nets, folder, obs = route3_folder
    data = tomllib.loads((folder / "interface.toml").read_text())
    alive = np.asarray([r["obs"] for r in data["golden"]])[..., ALIVE]                       # [G, M]
    out = alive == 0
    assert out[0, 1] and out.sum() >= 1                                    # the hand-made out drone (and any other)
    command = np.asarray([r["command"] for r in data["golden"]])                             # [G, M, 4]
    commands = np.asarray([r["commands"] for r in data["skill_net_golden"]])                 # [G, M, K, 4]
    assert np.all(command[out] == 0.0) and np.all(commands[out] == 0.0)
    assert np.any(command[~out] != 0.0)


# ------------------------------------------------------------------ LS1-M3-T4: ste_l6_export.py --skill-net (LS1.3)
import ste_l6_read as reader  # noqa: E402  (its reload_in_a_fresh_process is the command's second control)

CLI_GAMES = 3


def _export_net(path, side, out, games=CLI_GAMES) -> int:
    argv = ["--skill-net", str(path), "--out", str(out), "--games", str(games)]
    return cli.main(argv + (["--side", side] if side is not None else []))


def _resaved(net, meta, where, **changed) -> Path:
    """``net`` saved again under ``where`` with its C3 meta (``skill_net.META_KEYS`` only) and ``changed`` values."""
    path = Path(where) / f"skill_net_{net.team}.pt"
    skill_net.save_skill_net(path, net, {**{k: meta[k] for k in skill_net.META_KEYS}, **changed})
    return path


def test_golden_observations_cfg_equals_golden_observations(two_level):
    from svg_training.ste import sweep
    _, gates, _ = two_level
    guards, strikes = sweep.parse_size(gates.run["size"])
    for variant in ("base", OTHER):
        cfg = exploit.variant_cfg(gates, variant)
        for side in ("guard", "strike"):
            want = export.golden_observations(gates, side, games=3, seed=7, variant=variant)
            assert torch.equal(export.golden_observations_cfg(cfg, guards, strikes, side, 3, 7), want), (variant, side)


def test_the_skill_net_export_command_writes_a_reloading_folder(tiny_skill_net, tmp_path):
    side, net, meta, path, sha, _ = tiny_skill_net
    out = tmp_path / "export"
    out.mkdir()
    (out / "job.json").write_text("{}")                          # ste_job.py's own files do not count as an export
    assert _export_net(path, side, out) == 0
    controls = json.loads((out / "controls.json").read_text())
    assert sorted(controls) == ["ctl_net_equals_export", "ctl_reload_fresh_process"]
    assert all(c["status"] == "PASS" for c in controls.values()), controls
    assert sorted(p.name for p in out.iterdir()) == ["controls.json", "interface.toml", "job.json",
                                                     f"skill_net_{side}.onnx"]
    data = tomllib.loads((out / "interface.toml").read_text())
    assert data["policy_schema"] == export.SKILL_NET_SCHEMA and data["team"] == side
    assert data["skill_net"]["net_sha256"] == sha == data["source_checkpoint_sha256"]
    assert data["skill_net"]["net_file"] == export.repo_relative(path) == data["source_checkpoint"]
    assert data["game_file"] == meta["game_file"] and data["game_sha256"] == meta["game_sha256"]
    # the game file and the team sizes are the network's own (OP-26): the golden observations of its game
    cfg = exploit.load_game_cfg_file(exploit.ROOT / meta["game_file"])
    obs = export.golden_observations_cfg(cfg, meta["guards"], meta["strikes"], side, CLI_GAMES, export.GOLDEN_SEED)
    golden = data["skill_net_golden"]
    assert len(golden) == CLI_GAMES
    assert np.asarray([r["obs"] for r in golden], dtype=np.float32).tobytes() == obs.numpy().tobytes()
    assert export.reload_check(out)["ok"]


def test_the_skill_net_export_refuses_exit_2(tiny_skill_net, tmp_path, capsys, monkeypatch):
    side, net, meta, path, sha, _ = tiny_skill_net
    other = "guard" if side == "strike" else "strike"

    def refused(code, why, out):
        assert code == 2
        assert why in capsys.readouterr().err
        assert not (out / "interface.toml").exists() and not (out / "controls.json").exists()

    done = tmp_path / "done"
    done.mkdir()
    (done / "interface.toml").write_text("")
    assert _export_net(path, side, done) == 2                                      # a finished --out
    assert "holds an export already" in capsys.readouterr().err
    refused(_export_net(path, None, tmp_path / "o1"), "--side", tmp_path / "o1")     # --skill-net without --side
    refused(_export_net(path, other, tmp_path / "o2"), "team", tmp_path / "o2")      # the other team's side
    refused(_export_net(tmp_path / "none.pt", side, tmp_path / "o3"), "no skill network file", tmp_path / "o3")
    off_game = _resaved(net, meta, tmp_path / "off_game", game_sha256="0" * 64)      # the meta's game sha is off
    refused(_export_net(off_game, side, tmp_path / "o4"), "game_sha256", tmp_path / "o4")
    off_scripts = _resaved(net, meta, tmp_path / "off_scripts", scripted_sha256="0" * 64)   # skill_net.net_problems
    refused(_export_net(off_scripts, side, tmp_path / "o5"), "scripted_sha256", tmp_path / "o5")
    refused(cli.main(["--skill-net", str(path), "--side", side, "--out", str(tmp_path / "o6"), "--games", "0"]),
            "--games", tmp_path / "o6")
    for argv, why in (([  # both modes given, and neither: the parser's mutually exclusive, required group
            "--skill-net", str(path), "--side", side, "--run-dir", str(tmp_path), "--out", str(tmp_path / "o7")],
            "not allowed with"), (["--out", str(tmp_path / "o7")], "one of the arguments")):
        with pytest.raises(SystemExit) as exc:
            cli.main(argv)
        assert exc.value.code == 2
        assert why in capsys.readouterr().err
    assert not (tmp_path / "o7").exists()

    def no_runtime(folder):
        raise reader.Refused("the reload check cannot run in this environment (no onnxruntime)")
    monkeypatch.setattr(reader, "reload_in_a_fresh_process", no_runtime)    # the environment, not a failed control
    assert _export_net(path, side, tmp_path / "o8") == 2
    assert "cannot run in this environment" in capsys.readouterr().err
    assert not (tmp_path / "o8" / "controls.json").exists()


def test_a_failed_skill_net_control_exits_6(tiny_skill_net, tmp_path, monkeypatch):
    side, net, meta, path, sha, _ = tiny_skill_net
    monkeypatch.setattr(reader, "reload_in_a_fresh_process", lambda folder: {"ok": False, "error": "golden rows"})
    assert _export_net(path, side, tmp_path / "out") == 6
    controls = json.loads((tmp_path / "out" / "controls.json").read_text())
    assert controls["ctl_reload_fresh_process"]["status"] == "FAIL"
    assert controls["ctl_net_equals_export"]["status"] == "PASS"
    assert "golden rows" in controls["ctl_reload_fresh_process"]["detail"]
