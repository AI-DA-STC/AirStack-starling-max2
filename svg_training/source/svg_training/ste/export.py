"""STE L3-L6 pipeline check, task L6.2: the export and reload check of both routes (spec
ste_learning/drafts/L3_L6_PIPELINE_SPEC.md section 5; lead's answer 3: schemas ``ste-check-velocity-0`` and
``ste-check-skills-0``; ARCHITECTURE section 3's ``ste-policy-1`` is for observation v0.3 and is not used here).

* :func:`export_policy`: a trained team (``Learner.saved()``: velocity or the two-level skills route) -> a folder of one
  ONNX file per drone slot (input ``obs [B, 71]`` raw, the observation scaler folded into the graph; output
  ``action_mean [B, 4]`` or ``logits [B, T+1+K_d]``) and ``interface.toml`` (STANDARDS section 3 rule 1's fields, the
  schema, the status, the files' sha256, the skills route's lists and rules, golden rows on real observations).
  ``variant`` (route 3, task LS1-M3-T1; default "base"): the gate file's variant whose game and ``train_seed`` the
  export records; ``interface.toml`` names it (``variant = "<name>"``) only when it is not "base", so a base export is
  the same bytes as before.
* :func:`reload_check`: in a fresh process, the folder read back WITHOUT torch's modules: onnxruntime (the primary
  runtime) and ``onnx.reference.ReferenceEvaluator`` (an independent second check). Refuses (ValueError) a missing or
  changed status, an unknown schema, a changed file, skill lists unlike the ONNX files' own. Outputs within
  :func:`within` (``GOLDEN_ATOL + GOLDEN_RTOL * max |golden row|``) of the golden rows; for the skills
  route each head's argmax, the flown skills and the skill lists exactly and the final commands (the pinned
  ``opponents/scripted.py``) within :func:`within`.
* Route 3 (stage LS1), task LS1-M3-T2: :func:`skill_net_onnx` exports a skill network (``ste/skill_net.SkillNet``) as
  one ONNX graph (inputs ``obs`` f32 [B, OBS_DIM], ``slot`` and ``z`` i64 [B]; output ``command`` [B, 4]; the input
  scale, the one-hots, the clamp and the alive multiply inside the graph); :func:`export_skill_net` writes a stand-alone
  folder (schema ``ste-check-skillnet-0``: ``skill_net_<side>.onnx`` and ``interface.toml`` with a ``[skill_net]``
  section and ``[[skill_net_golden]]`` rows, every code for every drone); :func:`reload_check` reads it back on both
  runtimes (:func:`_skill_net_check`). :func:`run_skill_net` is the one door to the runtimes for a skill network: it
  refuses a slot outside [0, slot_width) or a code outside [0, k) before any runtime runs (onnxruntime's OneHot runs
  them without an error).

Every file carries ``status = "pipeline check, not for flight"`` (in ``interface.toml`` and in each ONNX file's
metadata). This does not settle whether onnxruntime or torch runs in the AirStack ground container (ARCHITECTURE
section 3, UNVERIFIED there). Requires the ``export`` extra (onnx, onnxruntime)."""
from __future__ import annotations

import hashlib
import io
import json
import subprocess
import tomllib
from pathlib import Path

import numpy as np
import torch
from torch import nn

from ..core.game_config import TICK_S
from ..core.observations import INTERFACE_VERSION, OBS_DIM, ObsView
from . import exploit, skill_net, skills, sweep

STATUS = "pipeline check, not for flight"
SCHEMAS = {"velocity": "ste-check-velocity-0", "skills": "ste-check-skills-0"}
SKILL_NET_SCHEMA = "ste-check-skillnet-0"         # a stand-alone skill network folder (route 3, LS1-M3-T2; OP-23)
# Every schema the reload reads -> (route, skill source): the two pipeline-check routes, and the skill network
ROUTE_OF_SCHEMA: dict[str, tuple[str, str | None]] = {**{schema: (route, None) for route, schema in SCHEMAS.items()},
                                                      SKILL_NET_SCHEMA: ("skill_net", None)}
GOLDEN_ATOL = 1e-6                # the ONNX runtimes round differently from torch (not bit for bit): absolute part
GOLDEN_RTOL = 1e-6                # and relative part (float32 rounding grows with the logit scale)
OPSET = 17
GOLDEN_GAMES = 8
GOLDEN_SEED = 5                   # the scripted game's seed of the golden observations
GOLDEN_TICKS = 30                 # ticks of scripted play before the golden observations are taken (some drones out)
SCRIPTED = exploit.ROOT / "source" / "svg_training" / "opponents" / "scripted.py"


def within(got, want) -> tuple[bool, float, float]:
    """|got - want| <= GOLDEN_ATOL + GOLDEN_RTOL * max |want row| everywhere (a row: one output vector, the last axis;
    float32 rounding in a layer's sums grows with the row's scale, not with the one element) -> (ok, max |got -
    want|, max |want|)."""
    got, want = np.asarray(got, dtype=np.float64), np.asarray(want, dtype=np.float64)
    diff = np.abs(got - want)
    row = np.abs(want).max(axis=-1, keepdims=True) if want.ndim else np.abs(want)
    ok = bool(np.all(diff <= GOLDEN_ATOL + GOLDEN_RTOL * row))
    return ok, float(diff.max()) if diff.size else 0.0, float(np.abs(want).max()) if want.size else 0.0


def repo_relative(path) -> str:
    """``path`` relative to the ``svg_training/`` root when it lies inside it (a net of record, C9); otherwise the
    resolved path as given (a test's temporary folder)."""
    p = Path(path).resolve()
    try:
        return str(p.relative_to(exploit.ROOT.resolve()))
    except ValueError:
        return str(p)


def _git_commit() -> str:
    try:
        return subprocess.run(["git", "-C", str(exploit.ROOT), "rev-parse", "HEAD"], capture_output=True, text=True,
                              check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def tolerance_text() -> str:
    return f"{GOLDEN_ATOL:g} + {GOLDEN_RTOL:g} * max |golden row|"


def sha256_file(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class FoldedPolicy(nn.Module):
    """skrl's RunningStandardScaler (its standardising branch) then the policy network: raw obs [B, 71] -> output."""

    def __init__(self, net: nn.Module, scaler_state: dict, epsilon: float, clip: float):
        super().__init__()
        self.net = net
        self.register_buffer("mean", scaler_state["running_mean"].float().clone())
        self.register_buffer("var", scaler_state["running_variance"].float().clone())
        self.epsilon, self.clip = float(epsilon), float(clip)

    def forward(self, obs):
        x = torch.clamp((obs - self.mean) / (torch.sqrt(self.var) + self.epsilon), min=-self.clip, max=self.clip)
        return self.net(x)


def check_variant(gates, variant: str) -> None:
    """ValueError unless ``variant`` is a name of the gate file's ``[variants]`` (``exploit.variant_cfg`` alone would
    take a ``[games]`` key too)."""
    if variant not in gates.variants:
        raise ValueError(f"variant {variant!r} not in the gate file (its variants: {sorted(gates.variants)})")


def golden_observations(gates, side: str, games: int = GOLDEN_GAMES, seed: int = GOLDEN_SEED,
                        variant: str = "base") -> torch.Tensor:
    """Real observations of ``side`` [games, M, 71] after ``GOLDEN_TICKS`` ticks of scripted play in the game of the
    gate file's ``variant`` (CPU), where some drones may be out. The scripted players stay fixed."""
    from ..opponents.scripted import make_strategy
    from .exploit_train import TrainGame
    check_variant(gates, variant)
    cfg = exploit.variant_cfg(gates, variant)
    guards, strikes = sweep.parse_size(gates.run["size"])
    game = TrainGame(cfg, games, guards, strikes, device="cpu", seed=seed)
    obs = game.reset()
    g = make_strategy("guard_mark_edge", "guard", cfg, games, "cpu", 0)
    s = make_strategy("strike_straight", "strike", cfg, games, "cpu", 0)
    for _ in range(GOLDEN_TICKS):
        obs = game.step({"guard": g.act(obs["guard"]), "strike": s.act(obs["strike"])}).obs
    return obs[side].clone()


def _dispatch(gates, side: str, games: int, variant: str = "base"):
    check_variant(gates, variant)
    return skills.two_level_dispatch(gates.learner, gates.players, side, exploit.variant_cfg(gates, variant), games,
                                     "cpu", 0)


def export_policy(saved: dict, gates, side: str, out_dir, obs: torch.Tensor, source: dict | None = None,
                  variant: str = "base") -> Path:
    """Export ``saved`` (``Learner.saved()`` of ``gates``' route, team ``side``) to ``out_dir``; golden rows on ``obs``
    [G, M, 71]. ``source``: {"run", "checkpoint", "checkpoint_sha256"} of the run it came from (written as
    ``source_run``, ``source_checkpoint``, ``source_checkpoint_sha256``; ``scripts/ste_l6_export.py``). ``variant``:
    the gate file's variant the run played (its game and ``train_seed`` go into ``interface.toml``, which names it as
    ``variant`` when it is not "base"); a name not in ``[variants]`` is refused before anything is written. Returns
    the folder."""
    import onnx
    from skrl.resources.preprocessors.torch import RunningStandardScaler

    from ..opponents.learned import OBS_SPACE, StandinPolicy, TwoLevelPolicy
    check_variant(gates, variant)
    route = "skills" if gates.learner.skills else "velocity"
    if (route == "skills") != (set(saved) == {"skills", "modules"}):
        raise ValueError(f"the checkpoint does not match the gate file's route ({route})")
    modules = saved["modules"] if route == "skills" else saved
    names = sorted(modules, key=lambda a: int(a.rsplit("_", 1)[1]))
    hidden = list(gates.trainer["hidden"])
    probe = RunningStandardScaler(OBS_SPACE, device="cpu")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    d = _dispatch(gates, side, obs.shape[0], variant=variant) if route == "skills" else None
    files, outputs = [], []
    skills_json = json.dumps(skills.skills_meta(d), sort_keys=True) if route == "skills" else None
    for slot, a in enumerate(names):
        pol = TwoLevelPolicy(hidden, d.widths, "cpu") if route == "skills" else StandinPolicy(hidden, "cpu")
        pol.load_state_dict(modules[a]["policy"])
        model = FoldedPolicy(pol.net, modules[a]["observation_preprocessor"], probe.epsilon, probe.clip_threshold)
        model.eval()
        out_name = "logits" if route == "skills" else "action_mean"
        buf = io.BytesIO()
        torch.onnx.export(model, torch.zeros(1, OBS_DIM), buf, input_names=["obs"], output_names=[out_name],
                          dynamic_axes={"obs": {0: "B"}, out_name: {0: "B"}}, opset_version=OPSET)
        m = onnx.load_from_string(buf.getvalue())
        for key, value in (("status", STATUS), ("policy_schema", SCHEMAS[route]), ("team", side), ("slot", str(slot))):
            entry = m.metadata_props.add()
            entry.key, entry.value = key, value
        if skills_json is not None:                     # the skill lists in every file too (the reload compares them)
            entry = m.metadata_props.add()
            entry.key, entry.value = "skills", skills_json
        onnx.checker.check_model(m)
        path = out / f"policy_{side}_{slot}.onnx"
        onnx.save(m, str(path))
        files.append({"slot": slot, "file": path.name, "sha256": sha256_file(path)})
        with torch.no_grad():
            outputs.append(model(obs[:, slot]))
    outs = torch.stack(outputs, dim=1)                                           # [G, M, W]
    golden = []
    for gi in range(obs.shape[0]):
        row = {"game": gi, "obs": obs[gi].tolist(), "outputs": outs[gi].tolist()}
        golden.append(row)
    if route == "skills":
        heads = d.greedy(outs)                                                   # [G, M, 2]
        flown = d.resolve(heads, obs)                                            # [G, M]
        command = d.act(obs, flown)                                              # [G, M, 4]
        for gi, row in enumerate(golden):
            row.update(heads=heads[gi].tolist(), flown=flown[gi].tolist(), command=command[gi].tolist())
    (out / "interface.toml").write_text(_interface(gates, side, route, files, golden, d, source,
                                                       variant=variant))
    return out


def _interface(gates, side: str, route: str, files: list, golden: list, d, source: dict | None = None,
               variant: str = "base") -> str:
    check_variant(gates, variant)
    cfg = exploit.variant_cfg(gates, variant)
    game = gates.games[gates.variants[variant]["game"]]
    params = exploit.ROOT / cfg.starling.params
    commit = _git_commit()
    hold = int(gates.trainer["decision_ticks"])
    guards, strikes = sweep.parse_size(gates.run["size"])
    lines = [f'# Exported by ste/export.py: {STATUS}. Observed in the training simulator; nothing here authorises '
             'a flight.',
             f'policy_schema = "{SCHEMAS[route]}"', f'status = "{STATUS}"',
             f'interface_version = "{INTERFACE_VERSION}"', f"obs_dim = {OBS_DIM}",
             f'obs_layout = "{_obs_layout(cfg)}"',
             'frames = "own x, y relative to the zone centre, own z the world height (m); own velocity world (m/s); '
             'yaw world (rad, sin and cos); slot k: the other drone minus this one in world axes (position m, velocity '
             'm/s), all zeros when that drone is out or padding; zone centre relative to the arena centre (m); a drone '
             'that is out sees zeros except team"',
             f"team_speed_mps = {float(cfg.team_speed_mps(side))!r}",
             f"yaw_rate_max_rad_s = {float(cfg.yaw_rate_max_rad_s)!r}",
             ('action = "vx, vy, vz, yaw rate, clamped to [-1, 1] (non-finite: zero); the velocity part divided by '
              'max(its length, 1) times team_speed_mps; the yaw rate times yaw_rate_max_rad_s"'
              if route == "velocity" else
              'action = "logits over [free, team strategies] then [drone skills]; the leader\'s team head, else each '
              'drone\'s drone skill (skills below)"'),
             f"decision_s = {hold * TICK_S:g}", f"tick_s = {TICK_S:g}", f"hold_ticks = {hold}",
             f'team = "{side}"', f"slots = {len(files)}", f"tag_radius_m = {float(cfg.tag.radius_m)}",
             f'filter_share = "{cfg.filter.share}"', f'game_file = "{game.file}"', f'game_sha256 = "{game.sha256}"',
             f'drone_model_file = "{cfg.starling.params}"', f'drone_model_sha256 = "{sha256_file(params)}"',
             f'git_commit = "{commit}"', f"seed = {int(gates.variants[variant]['train_seed'][side])}"]
    if variant != "base":                       # written only for another variant: a base export is unchanged (OP-24)
        lines.append(f'variant = "{variant}"')
    lines += [f'gates_sha256 = "{gates.sha256}"',
              f"golden_output_scale = {float(np.abs(np.asarray([r['outputs'] for r in golden])).max())!r}",
              f'golden_tolerance = "{tolerance_text()}"']
    for key in ("run", "checkpoint", "checkpoint_sha256"):
        if source is not None:
            lines.append(f'source_{key} = "{source[key]}"')
    if route == "skills":
        meta = skills.skills_meta(d)
        lines += [f'scripted_sha256 = "{sha256_file(SCRIPTED)}"', "", "[skills]",
                  f"players = {_arr(meta['players'])}", f"team_strategies = {_arr(meta['team_strategies'])}",
                  f"drone_skills = {_arr(meta['drone_skills'])}", f"free_index = {meta['free_index']}",
                  'leader_rule = "the lowest-index live drone at the decision tick chooses the team head (the last '
                  'slot when none is live)"',
                  f'hold_rule = "one choice every {hold} ticks ({hold * TICK_S:g} s), held; the chosen skills run '
                  'closed loop every tick"', "", "[team_size]", f"guards = {guards}", f"strikes = {strikes}"]
    for f in files:
        lines += ["", "[[files]]", f"slot = {f['slot']}", f'file = "{f["file"]}"', f'sha256 = "{f["sha256"]}"']
    for row in golden:
        lines += ["", "[[golden]]"] + [f"{k} = {_arr(v) if isinstance(v, list) else v}" for k, v in row.items()]
    return "\n".join(lines) + "\n"


def skill_net_onnx(net: skill_net.SkillNet, side: str, skills_list: list[str]):
    """``net`` (team ``side``, skills ``skills_list`` in code order, both checked against the network) as an ONNX
    graph: inputs ``obs`` f32 [B, OBS_DIM], ``slot`` i64 [B], ``z`` i64 [B]; output ``command`` f32 [B, COMMAND_DIM];
    dynamic B; the input scale, the one-hots, the clamp and the alive multiply inside the graph (C2); metadata status,
    schema, team, skills (JSON), slot_width, k; checked by ``onnx.checker``. Returns the ``onnx.ModelProto``."""
    import warnings

    import onnx
    if side != net.team:
        raise ValueError(f"team: the skill network is the {net.team} team's, not {side!r}")
    if list(skills_list) != list(net.skills):
        raise ValueError(f"skills: the network's {list(net.skills)} are not {list(skills_list)}")
    args = (torch.zeros(1, OBS_DIM), torch.zeros(1, dtype=torch.int64), torch.zeros(1, dtype=torch.int64))
    names = ["obs", "slot", "z"]
    buf = io.BytesIO()
    with warnings.catch_warnings():     # forward's "if clip": the default clip=True is traced in as a constant
        warnings.simplefilter("ignore", torch.jit.TracerWarning)
        torch.onnx.export(net.eval(), args, buf, input_names=names, output_names=["command"],
                          dynamic_axes={**{n: {0: "B"} for n in names}, "command": {0: "B"}}, opset_version=OPSET)
    m = onnx.load_from_string(buf.getvalue())
    for key, value in (("status", STATUS), ("policy_schema", SKILL_NET_SCHEMA), ("team", side),
                       ("skills", json.dumps(list(net.skills))), ("slot_width", str(net.slot_width)),
                       ("k", str(net.k))):
        entry = m.metadata_props.add()
        entry.key, entry.value = key, value
    onnx.checker.check_model(m)
    return m


def skill_net_golden(net: skill_net.SkillNet, obs: torch.Tensor) -> list[dict]:
    """Golden rows of ``net`` on ``obs`` [G, M, OBS_DIM]: one batched forward over every code for every drone
    (``skill_net.all_codes``) -> per game {"game", "obs" [M, OBS_DIM], "commands" [M, K, COMMAND_DIM]}; the rows of a
    drone that is out are zero (C2)."""
    commands = skill_net.all_codes(net, obs)
    return [{"game": gi, "obs": obs[gi].tolist(), "commands": commands[gi].tolist()} for gi in range(obs.shape[0])]


def export_skill_net(net: skill_net.SkillNet, meta: dict, side: str, out_dir, obs: torch.Tensor,
                     source: dict | None = None, *, net_file) -> Path:
    """A stand-alone skill network folder in ``out_dir``: ``skill_net_<side>.onnx`` (:func:`skill_net_onnx`) and
    ``interface.toml`` (schema ``SKILL_NET_SCHEMA``, status, interface, observation layout, team, tick, game file and
    sha256, ``scripted_sha256`` as provenance, commit, tolerance, ``source_*`` from ``source``, a ``[skill_net]``
    section and ``[[skill_net_golden]]`` rows on ``obs`` [G, M, OBS_DIM]). ``meta``: the network file's meta
    (``skill_net.load_skill_net``); ``net_file``: that file (written repository-relative when inside ``svg_training/``,
    with its sha256; it is not copied into the folder). The game file named in ``meta`` must have the meta's sha256.
    Returns the folder."""
    import onnx
    if meta["team"] != net.team or list(meta["skills"]) != list(net.skills):
        raise ValueError(f"the meta (team {meta['team']!r}, skills {list(meta['skills'])}) is not the network's "
                         f"({net.team!r}, {list(net.skills)})")
    game_path = exploit.ROOT / meta["game_file"]
    if sha256_file(game_path) != meta["game_sha256"]:
        raise ValueError(f"{meta['game_file']}: sha256 {sha256_file(game_path)} is not the network's "
                         f"{meta['game_sha256']}")
    cfg = exploit.load_game_cfg_file(game_path)
    model = skill_net_onnx(net, side, list(net.skills))
    golden = skill_net_golden(net, obs)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"skill_net_{side}.onnx"
    onnx.save(model, str(path))
    alive = ObsView().alive
    lines = [f'# Exported by ste/export.py: {STATUS}. Observed in the training simulator; nothing here authorises '
             'a flight.',
             f'policy_schema = "{SKILL_NET_SCHEMA}"', f'status = "{STATUS}"',
             f'interface_version = "{INTERFACE_VERSION}"', f"obs_dim = {OBS_DIM}",
             f'obs_layout = "{_obs_layout(cfg)}"', f'team = "{side}"', f"tick_s = {TICK_S:g}",
             f'game_file = "{meta["game_file"]}"', f'game_sha256 = "{meta["game_sha256"]}"',
             f'scripted_sha256 = "{meta["scripted_sha256"]}"', f'git_commit = "{_git_commit()}"',
             f'golden_tolerance = "{tolerance_text()}"']
    for key, value in (source or {}).items():
        lines.append(f'source_{key} = "{value}"')
    lines += ["", "[skill_net]", f'file = "{path.name}"', f'sha256 = "{sha256_file(path)}"',
              f'net_file = "{repo_relative(net_file)}"', f'net_sha256 = "{sha256_file(net_file)}"',
              f"skills = {_arr(list(net.skills))}", f"slot_width = {net.slot_width}", f"k = {net.k}",
              f"team_size = {net.team_size}", f"zeroed_inputs = {_arr(list(net.zeroed_inputs))}",
              f'alive_rule = "inside the graph: command times obs[{alive}]"',
              'code_rule = "z = index in skills; a two-level team\'s flown index is z"',
              'input_check = "the consumer refuses slot outside [0, slot_width) and z outside [0, k)"']
    for row in golden:
        lines += ["", "[[skill_net_golden]]"] + [f"{k} = {_arr(v) if isinstance(v, list) else v}"
                                                 for k, v in row.items()]
    (out / "interface.toml").write_text("\n".join(lines) + "\n")
    return out


def inputs_problem(slot: np.ndarray, z: np.ndarray, slot_width: int, k: int) -> str | None:
    """Why the skill network must not run on ``slot`` [B] and ``z`` [B] (int64, slot in [0, slot_width), z in
    [0, k)), or None when they are good. onnxruntime refuses int32 but runs a code out of range without an error."""
    slot, z = np.asarray(slot), np.asarray(z)
    out = [f"{name} must be int64, is {a.dtype}" for name, a in (("slot", slot), ("z", z)) if a.dtype != np.int64]
    for name, a, top in (("slot", slot, slot_width), ("z", z, k)):
        bad = (a < 0) | (a >= top)
        if bad.any():
            out.append(f"{name} outside [0, {top}) in {int(bad.sum())} rows (first {a[bad][0]})")
    return "; ".join(out) or None


def run_skill_net(onnx_file, obs: np.ndarray, slot: np.ndarray, z: np.ndarray, slot_width: int, k: int) -> dict:
    """The skill network's graph in ``onnx_file`` on rows ``obs`` [B, OBS_DIM] f32, ``slot`` [B], ``z`` [B] (int64) on
    onnxruntime and ``onnx.reference.ReferenceEvaluator`` -> {runtime name: command [B, COMMAND_DIM]}. The inputs are
    checked (:func:`inputs_problem`, ValueError) before any runtime is built."""
    problem = inputs_problem(slot, z, slot_width, k)
    if problem is not None:
        raise ValueError(f"skill network inputs: {problem}")
    import onnx
    import onnxruntime as ort
    from onnx.reference import ReferenceEvaluator
    feed = {"obs": np.asarray(obs, dtype=np.float32), "slot": slot, "z": z}
    sess = ort.InferenceSession(str(onnx_file), providers=["CPUExecutionProvider"])
    ref = ReferenceEvaluator(onnx.load(str(onnx_file)))
    return {"onnxruntime": sess.run(None, feed)[0], "onnx.reference": ref.run(None, feed)[0]}


def _skill_net_check(folder, meta: dict) -> dict:
    """The skill network of a folder (its ``[skill_net]`` section and ``[[skill_net_golden]]`` rows; a stand-alone
    folder's, and later a route 3 team folder's): the file's sha256; its ONNX metadata (status, ``SKILL_NET_SCHEMA``,
    team, slot_width, k); its skill list equal to ``[skill_net].skills``; the golden rows (every code for every drone,
    range-checked before any runtime) within :func:`within` on both runtimes. Returns {"skill_net_max_abs_diff",
    "skill_net_golden_rows"}; ValueError on a refusal."""
    import onnx
    sn = meta["skill_net"]
    path = Path(folder) / sn["file"]
    if sha256_file(path) != sn["sha256"]:
        raise ValueError(f"{sn['file']}: sha256 {sha256_file(path)} is not the interface's {sn['sha256']}")
    props = {p.key: p.value for p in onnx.load(str(path)).metadata_props}
    want = {"status": STATUS, "policy_schema": SKILL_NET_SCHEMA, "team": meta["team"],
            "slot_width": str(sn["slot_width"]), "k": str(sn["k"])}
    differ = {key: (props.get(key), value) for key, value in want.items() if props.get(key) != value}
    if differ:
        raise ValueError(f"{sn['file']}: ONNX metadata (file, interface) differs: {differ}")
    if json.loads(props.get("skills", "null")) != list(sn["skills"]) or len(sn["skills"]) != sn["k"]:
        raise ValueError(f"{sn['file']}: the skills of interface.toml [skill_net] {list(sn['skills'])} (k {sn['k']}) "
                         f"are not the file's own {props.get('skills')}")
    obs = np.asarray([row["obs"] for row in meta["skill_net_golden"]], dtype=np.float32)        # [G, M, OBS_DIM]
    want_cmd = np.asarray([row["commands"] for row in meta["skill_net_golden"]], dtype=np.float32)  # [G, M, K, 4]
    g, m = obs.shape[:2]
    k = int(sn["k"])
    if want_cmd.shape != (g, m, k, skill_net.COMMAND_DIM):
        raise ValueError(f"golden rows: commands of shape {want_cmd.shape}, expected "
                         f"{(g, m, k, skill_net.COMMAND_DIM)}")
    rows = np.repeat(obs.reshape(g * m, OBS_DIM), k, axis=0)                     # the row order of all_codes
    slot = np.repeat(np.tile(np.arange(m, dtype=np.int64), g), k)
    z = np.tile(np.arange(k, dtype=np.int64), g * m)
    got = run_skill_net(path, rows, slot, z, int(sn["slot_width"]), k)
    worst = 0.0
    for name, commands in got.items():
        ok, diff, scale = within(commands, want_cmd.reshape(g * m * k, skill_net.COMMAND_DIM))
        worst = max(worst, diff)
        if not ok:
            raise ValueError(f"skill network golden rows: {name} differs by up to {diff:.2e} (tolerance "
                             f"{tolerance_text()}, commands up to {scale:.3g})")
    return {"skill_net_max_abs_diff": worst, "skill_net_golden_rows": int(g * m * k)}


def _obs_layout(cfg) -> str:
    """The observation's index layout, from ``core.observations.ObsView`` (interface v0.1)."""
    from ..core.observations import SLOT, ObsView

    def span(s) -> str:
        return f"{s.start}-{s.stop - 1}"
    slots = cfg.pad_guards + cfg.pad_strikes
    last = ObsView.SLOTS_FROM + SLOT * slots - 1
    return (f"own position {span(ObsView.own_pos)}, own velocity {span(ObsView.own_vel)}, sin and cos of yaw "
            f"{span(ObsView.sin_cos_yaw)}, zone radius {ObsView.zone_radius}, arena half width {ObsView.arena_half}, "
            f"time left (s) {ObsView.time_left}, team {ObsView.team} (-1 Guard, +1 Strike), alive {ObsView.alive}, "
            f"{slots} slots of {SLOT} at {ObsView.SLOTS_FROM}-{last} (Guard drones first, padded to {cfg.pad_guards}, "
            f"then Strike drones, padded to {cfg.pad_strikes}; each relative position 3, relative velocity 3, present "
            f"1), zone centre {span(ObsView.zone_centre)}")


def _arr(v) -> str:
    if isinstance(v, list):
        return "[" + ", ".join(_arr(x) for x in v) + "]"
    if isinstance(v, str):
        return f'"{v}"'
    return repr(float(v)) if isinstance(v, float) else str(v)


def reload_check(folder) -> dict:
    """The reload check (module docstring), for a fresh process. Returns the numbers; raises ValueError on a refusal or
    a golden mismatch."""
    import onnx
    import onnxruntime as ort
    from onnx.reference import ReferenceEvaluator
    folder = Path(folder)
    meta = tomllib.loads((folder / "interface.toml").read_text())
    if meta.get("status") != STATUS:
        raise ValueError(f"interface.toml status {meta.get('status')!r}: must be {STATUS!r}")
    route = ROUTE_OF_SCHEMA.get(meta.get("policy_schema"), (None, None))[0]
    if route is None:
        raise ValueError(f"unknown policy_schema {meta.get('policy_schema')!r} (known: {sorted(ROUTE_OF_SCHEMA)})")
    if route == "skill_net":                    # a stand-alone skill network folder: no [[files]], no heads
        return {"ok": True, "runtimes": ["onnxruntime", "onnx.reference"], "route": route, "status": STATUS,
                "tolerance": tolerance_text(), **_skill_net_check(folder, meta)}
    runners = []
    for f in meta["files"]:
        path = folder / f["file"]
        if sha256_file(path) != f["sha256"]:
            raise ValueError(f"{f['file']}: sha256 {sha256_file(path)} is not the interface's {f['sha256']}")
        m = onnx.load(str(path))
        props = {p.key: p.value for p in m.metadata_props}
        if props.get("status") != STATUS or props.get("policy_schema") != meta["policy_schema"]:
            raise ValueError(f"{f['file']}: ONNX metadata status {props.get('status')!r} / schema "
                             f"{props.get('policy_schema')!r}, must be {STATUS!r} / {meta['policy_schema']!r}")
        if route == "skills":
            sk = meta["skills"]
            mine = {"team": meta["team"], "players": list(sk["players"]), "choice": skills.TWO_LEVEL,
                    "team_strategies": list(sk["team_strategies"]), "drone_skills": list(sk["drone_skills"]),
                    "free_index": sk["free_index"]}
            if json.loads(props.get("skills", "null")) != mine:
                raise ValueError(f"{f['file']}: the skill lists in interface.toml {mine} are not the file's own "
                                 f"{props.get('skills')}")
        sess = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
        ref = ReferenceEvaluator(m)
        runners.append((sess, ref))
    obs = np.asarray([row["obs"] for row in meta["golden"]], dtype=np.float32)          # [G, M, 71]
    want = np.asarray([row["outputs"] for row in meta["golden"]], dtype=np.float32)     # [G, M, W]
    got = {"onnxruntime": [], "onnx.reference": []}
    for slot, (sess, ref) in enumerate(runners):
        got["onnxruntime"].append(sess.run(None, {"obs": obs[:, slot]})[0])
        got["onnx.reference"].append(ref.run(None, {"obs": obs[:, slot]})[0])
    worst, scale = 0.0, 0.0
    for name, outs in got.items():
        ok, diff, scale = within(np.stack(outs, axis=1), want)
        worst = max(worst, diff)
        if not ok:
            raise ValueError(f"golden rows: {name} differs by up to {diff:.2e} (tolerance {tolerance_text()}, "
                             f"outputs up to {scale:.3g})")
    out = {"ok": True, "runtimes": list(got), "max_abs_diff": worst, "golden_rows": int(obs.shape[0] * obs.shape[1]),
           "route": route, "status": STATUS, "output_scale": scale, "tolerance": tolerance_text()}
    if route == "skills":
        out.update(_skills_reload(meta, obs, np.stack(got["onnxruntime"], axis=1)))
    return out


def _skills_reload(meta: dict, obs: np.ndarray, logits: np.ndarray) -> dict:
    """The skills route's golden choices and commands, the scripts loaded from the pinned scripted.py."""
    if sha256_file(SCRIPTED) != meta["scripted_sha256"]:
        raise ValueError(f"opponents/scripted.py sha256 {sha256_file(SCRIPTED)} is not the exported "
                         f"{meta['scripted_sha256']}: the skills changed")
    game_path = exploit.ROOT / meta["game_file"]
    if sha256_file(game_path) != meta["game_sha256"]:
        raise ValueError(f"{meta['game_file']}: sha256 differs from the exported game's")
    cfg = exploit.load_game_cfg_file(game_path)
    sk, side = meta["skills"], meta["team"]
    d = skills.TwoLevelDispatch(side, list(sk["players"]), list(sk["team_strategies"]), list(sk["drone_skills"]), cfg,
                                obs.shape[0], "cpu", 0)
    lists_equal = skills.skills_meta(d) == {"team": side, "players": list(sk["players"]), "choice": skills.TWO_LEVEL,
                                            "team_strategies": list(sk["team_strategies"]),
                                            "drone_skills": list(sk["drone_skills"]), "free_index": sk["free_index"]}
    o = torch.from_numpy(obs)
    heads = d.greedy(torch.from_numpy(logits))
    flown = d.resolve(heads, o)
    command = d.act(o, flown)
    want_heads = torch.tensor([row["heads"] for row in meta["golden"]])
    want_flown = torch.tensor([row["flown"] for row in meta["golden"]])
    want_cmd = torch.tensor([row["command"] for row in meta["golden"]], dtype=command.dtype)
    choices_equal = bool(torch.equal(heads, want_heads) and torch.equal(flown, want_flown))
    cmd_ok, cmd_diff, _ = within(command.numpy(), want_cmd.numpy())
    if not (lists_equal and choices_equal and cmd_ok):
        raise ValueError(f"skills golden rows: lists equal {lists_equal}, choices equal {choices_equal}, commands "
                         f"differ by {cmd_diff:.2e}")
    return {"choices_equal": choices_equal, "skill_lists_equal": lists_equal, "commands_max_abs_diff": cmd_diff}
