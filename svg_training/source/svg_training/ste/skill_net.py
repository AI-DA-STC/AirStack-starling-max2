"""Route 3, stage LS1: the skill network (task LS1-M1-T3; plan ste_learning/drafts/LS1_TASK_PLAN.md, contracts C2, C3).

One small network per team stands in for that team's K scripted skills: it reads one drone's observation
[OBS_DIM], the drone's slot in its team (one-hot over the team's pad) and a skill code z (one-hot over K) and returns
that drone's command [COMMAND_DIM] in [-1, 1], times the drone's own alive flag (the rule of ``opponents/scripted._pack``,
inside ``forward`` so every path and the exported graph get it once).

Two batched paths fly it: ``one_code`` (each drone its own code, [N, M, 4]) and ``all_codes`` (every code for every
drone, [N, M, K, 4], as ``SkillDispatch.commands`` stacks the scripts). Neither builds an autograd graph.

The file (C3) is a ``torch.save`` payload of plain types and tensors (loads with ``weights_only=True``), written
atomically; ``load_skill_net`` refuses a file that does not match what the caller plays (file sha256, format, team,
skills, team size, the scripts' sha256, the game file's sha256, the game constants, the observation width and
interface), and ``net_problems`` lists the same faults as strings, for a driver's preflight.

No import from ``skills``, ``exploit`` or ``export`` (they import this module, or will). No tuned number: sizes,
the floor and the tolerance are arguments (tests/test_ste_literals.py)."""
from __future__ import annotations

import hashlib
import io
from pathlib import Path

import torch
from torch import Tensor, nn
from torch.nn import functional as F

from ..core.game_config import GameCfg
from ..core.observations import INTERFACE_VERSION, OBS_DIM, ObsView
from . import atomic, shared

COMMAND_DIM = 4                                   # vx, vy, vz, yaw rate: the policy interface's action (STANDARDS §3)
FORMAT = "ste-ls1-skill-net-1"
FILL_MARK = "FILL_"                               # the gate files' placeholder (= ste/exploit.FILL_MARK, pinned by a test)
TEAMS = ("guard", "strike")
ROOT = shared.PACKAGE_DIR.parents[2]              # svg_training/ (PACKAGE_DIR is source/svg_training/ste)
SCRIPTED_FILE = shared.PACKAGE_DIR.parent / "opponents" / "scripted.py"
# The caller's part of a saved file's meta (C3); the rest (format, team, skills, team_size, slot_width, obs_dim,
# interface_version, hidden, zeroed_inputs, state_dict) comes from the network and this module.
META_KEYS = ("guards", "strikes", "std_floor", "scripted_sha256", "game_file", "game_sha256", "game_constants",
             "provenance")
GAME_CONSTANT_KEYS = ("pad_guards", "pad_strikes", "keepout_strike_m", "keepout_guard_m", "wall_margin_m",
                      "height_band_m", "starling_enabled", "guard_speed_mps", "strike_speed_mps")
_V = ObsView()


class SkillNet(nn.Module):
    """The skill network of one team (C2).

    team: "guard" or "strike"; skills: the K skill names in code order (the gate file's ``[players]`` list of the team);
    team_size: drones per team in the games it flies (M); slot_width: the one-hot width of the slot input (the team's
    pad, ``cfg.pad_guards`` or ``cfg.pad_strikes``; OP-6); hidden: the hidden widths (Linear + ELU each); zeroed_inputs:
    observation indices multiplied by 0 after normalising (``keep``), so no value there can change a command.
    Buffers ``in_mean``, ``in_std``, ``keep`` [OBS_DIM] float32 (mean 0, std 1 until ``set_normaliser``)."""

    def __init__(self, team: str, skills: list[str], team_size: int, slot_width: int, hidden: list[int],
                 zeroed_inputs: list[int]):
        super().__init__()
        if team not in TEAMS:
            raise ValueError(f"team must be one of {TEAMS}, got {team!r}")
        if not skills:
            raise ValueError("skills: at least one skill")
        if not 1 <= team_size <= slot_width:
            raise ValueError(f"team size {team_size} must be between 1 and the slot width {slot_width}")
        bad = [i for i in zeroed_inputs if not 0 <= i < OBS_DIM]
        if bad:
            raise ValueError(f"zeroed_inputs {bad} are not observation indices 0..{OBS_DIM - 1}")
        self.team = team
        self.skills = tuple(skills)
        self.k = len(self.skills)
        self.team_size = int(team_size)
        self.slot_width = int(slot_width)
        self.hidden = [int(h) for h in hidden]
        self.zeroed_inputs = [int(i) for i in zeroed_inputs]
        keep = torch.ones(OBS_DIM)
        keep[self.zeroed_inputs] = 0.0
        self.register_buffer("in_mean", torch.zeros(OBS_DIM))
        self.register_buffer("in_std", torch.ones(OBS_DIM))
        self.register_buffer("keep", keep)
        layers: list[nn.Module] = []
        width = OBS_DIM + self.slot_width + self.k
        for h in self.hidden:
            layers += [nn.Linear(width, h), nn.ELU()]
            width = h
        layers.append(nn.Linear(width, COMMAND_DIM))
        self.mlp = nn.Sequential(*layers)

    def set_normaliser(self, mean: Tensor, std: Tensor, floor: float) -> None:
        """Store the input normaliser: mean, std [OBS_DIM]; the std is clamped below at ``floor`` (a constant input
        would otherwise divide by zero)."""
        if mean.shape != (OBS_DIM,) or std.shape != (OBS_DIM,):
            raise ValueError(f"mean and std must be [{OBS_DIM}], got {tuple(mean.shape)} and {tuple(std.shape)}")
        with torch.no_grad():
            self.in_mean.copy_(mean)
            self.in_std.copy_(std.clamp(min=floor))

    def forward(self, obs: Tensor, slot: Tensor, z: Tensor, clip: bool = True) -> Tensor:
        """obs [B, OBS_DIM] float32, slot [B] int64 (0..slot_width-1), z [B] int64 (0..K-1) -> command [B, COMMAND_DIM]:
        ``clamp(-1, 1)`` when ``clip``, then times the drone's own alive flag (a drone that is out gets zeros)."""
        x = (obs - self.in_mean) / self.in_std * self.keep
        h = torch.cat((x, F.one_hot(slot, self.slot_width).to(x.dtype), F.one_hot(z, self.k).to(x.dtype)), dim=-1)
        out = self.mlp(h)
        if clip:
            out = out.clamp(-1, 1)
        return out * obs[:, _V.alive:_V.alive + 1]


def _check_team_size(net: SkillNet, obs: Tensor) -> None:
    if obs.shape[1] != net.team_size:
        raise ValueError(f"team size: the {net.team} skill network was built for {net.team_size} drones per team, "
                         f"the observation has {obs.shape[1]}")


def one_code(net: SkillNet, obs: Tensor, z: Tensor) -> Tensor:
    """obs [N, M, OBS_DIM], z [N, M] int64 (each drone's code) -> commands [N, M, COMMAND_DIM]; no graph. Row
    n * M + m is game n, drone m (slot m)."""
    _check_team_size(net, obs)
    n, m = obs.shape[:2]
    slot = torch.arange(m, device=obs.device).repeat(n)
    with torch.no_grad():
        out = net(obs.reshape(n * m, OBS_DIM), slot, z.reshape(n * m))
    return out.reshape(n, m, COMMAND_DIM)


def all_codes(net: SkillNet, obs: Tensor) -> Tensor:
    """obs [N, M, OBS_DIM] -> commands [N, M, K, COMMAND_DIM] (every code for every drone); no graph. Row
    (n * M + m) * K + k is game n, drone m, code k."""
    _check_team_size(net, obs)
    n, m = obs.shape[:2]
    rows = obs.reshape(n * m, OBS_DIM).repeat_interleave(net.k, dim=0)
    slot = torch.arange(m, device=obs.device).repeat(n).repeat_interleave(net.k)
    z = torch.arange(net.k, device=obs.device).repeat(n * m)
    with torch.no_grad():
        out = net(rows, slot, z)
    return out.reshape(n, m, net.k, COMMAND_DIM)


def game_constants(cfg: GameCfg) -> dict:
    """What the scripts read from the game config (``opponents/scripted.py``), as plain types: a network distilled
    from them is only valid where these are the same."""
    return {"pad_guards": int(cfg.pad_guards), "pad_strikes": int(cfg.pad_strikes),
            "keepout_strike_m": float(cfg.rules.keepout_strike_m), "keepout_guard_m": float(cfg.rules.keepout_guard_m),
            "wall_margin_m": float(cfg.arena.wall_margin_m),
            "height_band_m": [float(v) for v in cfg.arena.height_band_m],
            "starling_enabled": bool(cfg.starling.enabled),
            "guard_speed_mps": float(cfg.team_speed_mps("guard")),
            "strike_speed_mps": float(cfg.team_speed_mps("strike"))}


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def scripted_sha256() -> str:
    """sha256 of ``opponents/scripted.py`` today (the skills a network stands in for)."""
    return _sha256(SCRIPTED_FILE.read_bytes())


def save_skill_net(path: Path | str, net: SkillNet, meta: dict) -> str:
    """Write ``net`` and ``meta`` (exactly the keys ``META_KEYS``) to ``path`` atomically (C3); returns the sha256
    of the bytes written."""
    missing = [k for k in META_KEYS if k not in meta]
    extra = sorted(k for k in meta if k not in META_KEYS)
    if missing or extra:
        raise ValueError(f"skill network meta: missing keys {missing}, extra keys {extra}")
    payload = {"format": FORMAT, "team": net.team, "skills": list(net.skills), "team_size": net.team_size,
               "slot_width": net.slot_width, "obs_dim": OBS_DIM, "interface_version": INTERFACE_VERSION,
               "hidden": list(net.hidden), "zeroed_inputs": list(net.zeroed_inputs), **meta,
               "state_dict": {k: v.detach().cpu().clone() for k, v in net.state_dict().items()}}
    buffer = io.BytesIO()
    torch.save(payload, buffer)
    raw = buffer.getvalue()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = atomic.temporary_path(path)
    try:
        temporary.write_bytes(raw)
        atomic.commit(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return _sha256(raw)


def _payload(raw: bytes, device="cpu") -> dict:
    return torch.load(io.BytesIO(raw), map_location=device, weights_only=True)


def read_skill_net_meta(path: Path | str) -> dict:
    """The saved payload without ``state_dict``; no checks (for the export, M3)."""
    payload = _payload(Path(path).read_bytes())
    return {k: v for k, v in payload.items() if k != "state_dict"}


def _problems(payload, raw_sha: str, *, file_sha256: str | None, team: str, skills: list[str], team_size: int | None,
              cfg: GameCfg, game_sha256: str | None, game_file: str | None) -> list[str]:
    """Every fault of a loaded payload, in the order of the plan: file sha, format, team, skills, team size, scripts
    sha, game file and sha, game constants, observation width and interface. A wrong format stops the list."""
    out = []
    if file_sha256 is not None and raw_sha != file_sha256:
        out.append(f"file sha256: the file is {raw_sha}, expected {file_sha256}")
    fmt = payload.get("format") if isinstance(payload, dict) else None
    if fmt != FORMAT:
        return out + [f"format: the file is {fmt!r}, expected {FORMAT!r}"]
    if payload["team"] != team:
        out.append(f"team: the file is {payload['team']!r}, expected {team!r}")
    if list(payload["skills"]) != list(skills):
        out.append(f"skills: the file is {list(payload['skills'])}, expected {list(skills)}")
    if team_size is not None and payload["team_size"] != team_size:
        out.append(f"team size: the file is {payload['team_size']}, expected {team_size}")
    now = scripted_sha256()
    if payload["scripted_sha256"] != now:
        out.append(f"scripted_sha256: the file is {payload['scripted_sha256']}, opponents/scripted.py is {now}")
    if game_file is not None and payload["game_file"] != str(game_file):
        out.append(f"game_file: the file is {payload['game_file']!r}, expected {str(game_file)!r}")
    if game_sha256 is not None and payload["game_sha256"] != game_sha256:
        out.append(f"game_sha256: the file is {payload['game_sha256']}, expected {game_sha256}")
    want = game_constants(cfg)
    have = payload["game_constants"]
    differ = [f"{k} {have.get(k)!r} != {want[k]!r}" for k in GAME_CONSTANT_KEYS if have.get(k) != want[k]]
    differ += [f"{k} (not a game constant)" for k in sorted(have) if k not in want]
    if differ:
        out.append(f"game constants (file != config): {', '.join(differ)}")
    if payload["obs_dim"] != OBS_DIM or payload["interface_version"] != INTERFACE_VERSION:
        out.append(f"obs width/interface: the file is {payload['obs_dim']} / {payload['interface_version']!r}, "
                   f"expected {OBS_DIM} / {INTERFACE_VERSION!r}")
    return out


def load_skill_net(path: Path | str, *, team: str, skills: list[str], cfg: GameCfg, device, team_size: int | None = None,
                   file_sha256: str | None = None, game_sha256: str | None = None) -> tuple[SkillNet, dict]:
    """Load a skill network for flying (``eval()``, no gradients) and its meta (the payload without ``state_dict``).
    Refuses (``ValueError`` naming the field and both values) the first fault in the order of ``_problems``;
    ``team_size=None`` skips that check (the dispatch makes it at the first call)."""
    raw = Path(path).read_bytes()
    payload = _payload(raw, device)
    problems = _problems(payload, _sha256(raw), file_sha256=file_sha256, team=team, skills=skills, team_size=team_size,
                         cfg=cfg, game_sha256=game_sha256, game_file=None)
    if problems:
        raise ValueError(f"skill network {path}: {problems[0]}")
    net = SkillNet(payload["team"], list(payload["skills"]), payload["team_size"], payload["slot_width"],
                   list(payload["hidden"]), list(payload["zeroed_inputs"]))
    net.load_state_dict(payload["state_dict"])
    net.to(device).eval().requires_grad_(False)
    return net, {k: v for k, v in payload.items() if k != "state_dict"}


def net_problems(path: Path | str, *, sha256: str, team: str, skills: list[str], team_size: int, cfg: GameCfg,
                 game_file: str | None = None, game_sha256: str | None = None) -> list[str]:
    """The faults ``load_skill_net`` refuses, as strings (``[]`` = good), plus a missing file and a ``FILL_`` sha256;
    for a driver's preflight. ``game_file`` (repository-relative) and ``game_sha256`` are checked against the file's
    meta when given."""
    path = Path(path)
    if not path.is_file():
        return [f"skill network {path}: missing file"]
    raw = path.read_bytes()
    out = []
    if str(sha256).startswith(FILL_MARK):
        out.append(f"skill network {path}: sha256 not filled yet ({sha256!r})")
        sha256 = None
    try:
        payload = _payload(raw)
    except Exception as err:            # noqa: BLE001 (any unreadable file is one fault for the preflight to list)
        return out + [f"skill network {path}: cannot be read ({type(err).__name__}: {err})"]
    return out + [f"skill network {path}: {p}" for p in
                  _problems(payload, _sha256(raw), file_sha256=sha256, team=team, skills=skills, team_size=team_size,
                            cfg=cfg, game_sha256=game_sha256, game_file=game_file)]
