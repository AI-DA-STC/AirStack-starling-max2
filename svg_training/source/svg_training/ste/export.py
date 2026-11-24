"""STE L3-L6 pipeline check, task L6.2: the export and reload check of both routes (spec
ste_learning/drafts/L3_L6_PIPELINE_SPEC.md section 5; lead's answer 3: schemas ``ste-check-velocity-0`` and
``ste-check-skills-0``; ARCHITECTURE section 3's ``ste-policy-1`` is for observation v0.3 and is not used here).

* :func:`export_policy`: a trained team (``Learner.saved()``: velocity or the two-level skills route) -> a folder of one
  ONNX file per drone slot (input ``obs [B, 71]`` raw, the observation scaler folded into the graph; output
  ``action_mean [B, 4]`` or ``logits [B, T+1+K_d]``) and ``interface.toml`` (STANDARDS section 3 rule 1's fields, the
  schema, the status, the files' sha256, the skills route's lists and rules, golden rows on real observations).
* :func:`reload_check`: in a fresh process, the folder read back WITHOUT torch's modules: onnxruntime (the primary
  runtime) and ``onnx.reference.ReferenceEvaluator`` (an independent second check). Refuses (ValueError) a missing or
  changed status, an unknown schema, a changed file. Outputs within ``GOLDEN_TOL`` of the golden rows; for the skills
  route each head's argmax, the flown skills and the skill lists exactly and the final commands (the pinned
  ``opponents/scripted.py``) within ``GOLDEN_TOL``.

Every file carries ``status = "pipeline check, not for flight"`` (in ``interface.toml`` and in each ONNX file's
metadata). This does not settle whether onnxruntime or torch runs in the AirStack ground container (ARCHITECTURE
section 3, UNVERIFIED there). Requires the ``export`` extra (onnx, onnxruntime)."""
from __future__ import annotations

import hashlib
import io
import subprocess
import tomllib
from pathlib import Path

import numpy as np
import torch
from torch import nn

from ..core.game_config import TICK_S
from ..core.observations import INTERFACE_VERSION, OBS_DIM
from . import exploit, skills, sweep

STATUS = "pipeline check, not for flight"
SCHEMAS = {"velocity": "ste-check-velocity-0", "skills": "ste-check-skills-0"}
GOLDEN_TOL = 1e-6                 # absolute: the ONNX runtimes round differently from torch (not bit for bit)
OPSET = 17
GOLDEN_GAMES = 8
GOLDEN_SEED = 5                   # the scripted game's seed of the golden observations
GOLDEN_TICKS = 30                 # ticks of scripted play before the golden observations are taken (some drones out)
SCRIPTED = exploit.ROOT / "source" / "svg_training" / "opponents" / "scripted.py"


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


def golden_observations(gates, side: str, games: int = GOLDEN_GAMES, seed: int = GOLDEN_SEED) -> torch.Tensor:
    """Real observations of ``side`` [games, M, 71] after ``GOLDEN_TICKS`` ticks of scripted play in the gate file's
    game (CPU), where some drones may be out."""
    from ..opponents.scripted import make_strategy
    from .exploit_train import TrainGame
    cfg = exploit.variant_cfg(gates, "base")
    guards, strikes = sweep.parse_size(gates.run["size"])
    game = TrainGame(cfg, games, guards, strikes, device="cpu", seed=seed)
    obs = game.reset()
    g = make_strategy("guard_mark_edge", "guard", cfg, games, "cpu", 0)
    s = make_strategy("strike_straight", "strike", cfg, games, "cpu", 0)
    for _ in range(GOLDEN_TICKS):
        obs = game.step({"guard": g.act(obs["guard"]), "strike": s.act(obs["strike"])}).obs
    return obs[side].clone()


def _dispatch(gates, side: str, games: int):
    return skills.two_level_dispatch(gates.learner, gates.players, side, exploit.variant_cfg(gates, "base"), games,
                                     "cpu", 0)


def export_policy(saved: dict, gates, side: str, out_dir, obs: torch.Tensor) -> Path:
    """Export ``saved`` (``Learner.saved()`` of ``gates``' route, team ``side``) to ``out_dir``; golden rows on ``obs``
    [G, M, 71]. Returns the folder."""
    import onnx
    from skrl.resources.preprocessors.torch import RunningStandardScaler

    from ..opponents.learned import OBS_SPACE, StandinPolicy, TwoLevelPolicy
    route = "skills" if gates.learner.skills else "velocity"
    if (route == "skills") != (set(saved) == {"skills", "modules"}):
        raise ValueError(f"the checkpoint does not match the gate file's route ({route})")
    modules = saved["modules"] if route == "skills" else saved
    names = sorted(modules, key=lambda a: int(a.rsplit("_", 1)[1]))
    hidden = list(gates.trainer["hidden"])
    probe = RunningStandardScaler(OBS_SPACE, device="cpu")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    d = _dispatch(gates, side, obs.shape[0]) if route == "skills" else None
    files, outputs = [], []
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
    (out / "interface.toml").write_text(_interface(gates, side, route, files, golden, d))
    return out


def _interface(gates, side: str, route: str, files: list, golden: list, d) -> str:
    cfg = exploit.variant_cfg(gates, "base")
    game = gates.games[gates.variants["base"]["game"]]
    params = exploit.ROOT / cfg.starling.params
    try:
        commit = subprocess.run(["git", "-C", str(exploit.ROOT), "rev-parse", "HEAD"], capture_output=True,
                                text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        commit = "unknown"
    hold = int(gates.trainer["decision_ticks"])
    guards, strikes = sweep.parse_size(gates.run["size"])
    lines = [f'# Exported by ste/export.py: {STATUS}. Observed in the training simulator; nothing here authorises '
             'a flight.',
             f'policy_schema = "{SCHEMAS[route]}"', f'status = "{STATUS}"',
             f'interface_version = "{INTERFACE_VERSION}"', f"obs_dim = {OBS_DIM}",
             'obs_layout = "own position 3, own velocity 3, sin/cos yaw 2, zone radius, arena half, time left, team, '
             'alive, 8 slots x 7 (rel position 3, rel velocity 3, present 1; Guard slots first), zone centre 2"',
             'frames = "positions relative to the zone centre, world ENU; slots relative to the own drone"',
             ('action = "vx, vy, vz, yaw rate in [-1, 1]; velocity part capped at length 1 then times the team speed"'
              if route == "velocity" else
              'action = "logits over [free, team strategies] then [drone skills]; the leader\'s team head, else each '
              'drone\'s drone skill (skills below)"'),
             f"decision_s = {hold * TICK_S:g}", f"tick_s = {TICK_S:g}", f"hold_ticks = {hold}",
             f'team = "{side}"', f"slots = {len(files)}", f"tag_radius_m = {float(cfg.tag.radius_m)}",
             f'filter_share = "{cfg.filter.share}"', f'game_file = "{game.file}"', f'game_sha256 = "{game.sha256}"',
             f'drone_model_file = "{cfg.starling.params}"', f'drone_model_sha256 = "{sha256_file(params)}"',
             f'git_commit = "{commit}"', f"seed = {int(gates.variants['base']['train_seed'][side])}",
             f'gates_sha256 = "{gates.sha256}"']
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
    route = {v: k for k, v in SCHEMAS.items()}.get(meta.get("policy_schema"))
    if route is None:
        raise ValueError(f"unknown policy_schema {meta.get('policy_schema')!r} (known: {sorted(SCHEMAS.values())})")
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
        sess = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
        ref = ReferenceEvaluator(m)
        runners.append((sess, ref))
    obs = np.asarray([row["obs"] for row in meta["golden"]], dtype=np.float32)          # [G, M, 71]
    want = np.asarray([row["outputs"] for row in meta["golden"]], dtype=np.float32)     # [G, M, W]
    got = {"onnxruntime": [], "onnx.reference": []}
    for slot, (sess, ref) in enumerate(runners):
        got["onnxruntime"].append(sess.run(None, {"obs": obs[:, slot]})[0])
        got["onnx.reference"].append(ref.run(None, {"obs": obs[:, slot]})[0])
    worst = 0.0
    for name, outs in got.items():
        arr = np.stack(outs, axis=1)
        diff = float(np.abs(arr - want).max())
        worst = max(worst, diff)
        if diff > GOLDEN_TOL:
            raise ValueError(f"golden rows: {name} differs by {diff:.2e} (> {GOLDEN_TOL:g})")
    out = {"ok": True, "runtimes": list(got), "max_abs_diff": worst, "golden_rows": int(obs.shape[0] * obs.shape[1]),
           "route": route, "status": STATUS}
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
    cmd_diff = float((command - want_cmd).abs().max())
    if not (lists_equal and choices_equal and cmd_diff <= GOLDEN_TOL):
        raise ValueError(f"skills golden rows: lists equal {lists_equal}, choices equal {choices_equal}, commands "
                         f"differ by {cmd_diff:.2e}")
    return {"choices_equal": choices_equal, "skill_lists_equal": lists_equal, "commands_max_abs_diff": cmd_diff}
