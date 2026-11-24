"""STE phase L3, first slice (B8): the mixed route's skills (design note ste_learning/drafts/L3_TWO_ROUTES_DESIGN.md,
section "v2 after the design review"; owner ruling R26).

The mixed route's learner does not output a velocity command: each 0.6 s decision it picks one of K hand-written skills,
the team's scripted players of ``opponents/scripted.py`` (R26: Strike K = 6, Guard K = 5, the gate file's ``[players]``
lists in that order). What flies is the chosen skill's own command.

* :func:`learner_spec`: the one config switch, ``[learner] action = "velocity" | "skills"`` (absent: "velocity", today's
  learner unchanged), and for the skills route ``choice = "team" | "drone"``.
* :class:`SkillDispatch`: runs all K skills on the batch every tick and gathers the chosen one per drone.
* :func:`require_velocity_learner`: what every driver that builds a ``DecisionEnv`` or a team directly calls on its gate
  file, so that a skills gate file is refused (exit 2) until that driver is wired, never trained as velocity silently.

**Hold rule (v2, A1 / B1).** A choice is made every decision (12 ticks = 0.6 s); the chosen skill runs closed loop every
tick in between (it reads the current observation and decides every 0.05 s, as a script does). Training
(``exploit_train.DecisionEnv.step``) and scoring (``exploit.HeldPlayer``) both hold the CHOICE, never the command, and
both go through :meth:`SkillDispatch.act`.

**Choice modes.** ``drone``: each drone flies the skill its own network chose. ``team``: one choice for the whole team,
every skill as written. With today's one network per drone slot (v2 correction 2) v2 does not say whose choice is the
team's; built here (lead's call, 24 Nov 2026): the choice of the lowest-index LIVE drone at the decision tick, held for the
decision. If slot 0 is tagged, the next live slot leads; a tagged slot never leads (its observation is zeroed, so it
would choose blind), except in a game with no live drone of the team, which has ended and is restarted. The other slots' networks still
sample, and their actions are ignored by the game; skrl trains each on its own log-probability, so the update stays
valid PPO with a noisier signal for those slots.

Shapes: N games, M drones of the team, K skills, D observation width; choices are long tensors of skill indices.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import torch
from torch import Tensor

from ..core.game_config import GameCfg
from ..core.observations import ObsView
from ..opponents.scripted import make_strategy

VELOCITY, SKILLS = "velocity", "skills"
ACTIONS = (VELOCITY, SKILLS)                    # [learner] action
TEAM, DRONE = "team", "drone"
CHOICES = (TEAM, DRONE)                         # SkillDispatch's own modes (slice 1)
TWO_LEVEL = "two_level"                         # L3 slice 2 (owner ruling R30): a team head and a drone head per drone
LEARNER_CHOICES = CHOICES + (TWO_LEVEL,)        # [learner] choice (skills route only)
TWO_LEVEL_KEYS = ("team_strategies", "drone_skills", "entropy_scale")   # [learner] keys of choice = "two_level" only
SIDE_KEYS = ("strike", "guard")
HEADS = ("team", "drone")
FREE = 0                                        # the team head's index of "free" (each drone flies its drone skill)
TEAM_PLAYERS = {"guard": "guards", "strike": "strikes"}    # the gate file's [players] list of each team = its skills
_V = ObsView()
ALIVE_FLAG_MIN = 0.5                            # the observation's own-alive flag is 0 or 1 (scripted.py reads it so)


@dataclass(frozen=True)
class LearnerSpec:
    """The ``[learner]`` table as loaded: action (ACTIONS), choice (LEARNER_CHOICES for the skills route, None for
    velocity). Choice "two_level" only (L3 slice 2): team_strategies and drone_skills {side: tuple of player names},
    entropy_scale {"team": float, "drone": float}."""
    action: str
    choice: str | None
    team_strategies: dict | None = None
    drone_skills: dict | None = None
    entropy_scale: dict | None = None

    @property
    def skills(self) -> bool:
        return self.action == SKILLS


def learner_spec(table: dict | None) -> LearnerSpec:
    """The ``[learner]`` table (None or absent: the velocity route, today's learner). ValueError names the first
    problem: an unknown key, an unknown action, a skills route without a known ``choice``, a velocity route with one."""
    if table is None:
        return LearnerSpec(VELOCITY, None)
    if not isinstance(table, dict):
        raise ValueError("[learner] must be a table")
    unknown = sorted(set(table) - {"action", "choice", *TWO_LEVEL_KEYS})
    if unknown:
        raise ValueError(f"unknown key(s) in [learner]: {unknown}")
    action = table.get("action", VELOCITY)
    if action not in ACTIONS:
        raise ValueError(f"[learner] action must be one of {ACTIONS}, got {action!r}")
    if action == VELOCITY:
        if "choice" in table:
            raise ValueError("[learner] choice belongs to the skills route only (action = \"skills\")")
        if any(k in table for k in TWO_LEVEL_KEYS):
            raise ValueError(f"[learner] {list(TWO_LEVEL_KEYS)} belong to choice = \"{TWO_LEVEL}\" only")
        return LearnerSpec(VELOCITY, None)
    choice = table.get("choice")
    if choice not in LEARNER_CHOICES:
        raise ValueError(f"[learner] action = \"skills\" needs choice one of {LEARNER_CHOICES}, got {choice!r}")
    if choice != TWO_LEVEL:
        if any(k in table for k in TWO_LEVEL_KEYS):
            raise ValueError(f"[learner] {list(TWO_LEVEL_KEYS)} belong to choice = \"{TWO_LEVEL}\" only")
        return LearnerSpec(SKILLS, choice)
    return _two_level_spec(table)


class LearnerNotWired(ValueError):
    """A gate file asks for the skills route in a driver that only knows the velocity route (STE L3 first slice)."""


def require_velocity_learner(gates, who: str) -> None:
    """Refuse (:class:`LearnerNotWired`, a ValueError: the drivers' refusal path, exit 2) a gate file whose
    ``[learner] action = "skills"``: ``who`` (the driver) builds a ``DecisionEnv`` or a velocity team directly and is not
    wired to the skills route yet. ``gates``: a loaded gate file (its ``learner``; absent = the velocity route) or a
    :class:`LearnerSpec`."""
    spec = gates if isinstance(gates, LearnerSpec) else getattr(gates, "learner", None)
    if spec is not None and spec.skills:
        raise LearnerNotWired(f"[learner] action = \"skills\" (choice {spec.choice!r}) is not wired into {who} yet "
                              f"(STE L3 first slice: only the velocity route runs there); refused, nothing trained or "
                              f"played")


def team_skills(players: dict, team: str) -> list[str]:
    """The skills of ``team`` in order: the gate file's ``[players]`` list of that team (R26)."""
    return list(players[TEAM_PLAYERS[team]])


class SkillDispatch:
    """The K skills of one team over the batch.

    team: "guard" or "strike"; skills: K scripted-player names (``opponents/scripted.REGISTRY``) in the choice order;
    cfg, num_games, device, seed: as ``make_strategy``; choice: "team" or "drone". The skills are stateless scripts that
    read only the observation, so running all K every tick and keeping one equals running that one alone."""

    def __init__(self, team: str, skills: list[str], cfg: GameCfg, num_games: int, device, seed: int, choice: str):
        if choice not in CHOICES:
            raise ValueError(f"choice must be one of {CHOICES}, got {choice!r}")
        if not skills:
            raise ValueError("a skill dispatch needs at least one skill")
        self.team, self.names, self.choice = team, list(skills), choice
        self.players = [make_strategy(s, team, cfg, num_games, device, seed) for s in self.names]

    @property
    def k(self) -> int:
        return len(self.players)

    def reset(self, games: Tensor) -> None:
        """games [N] bool (the scripts are stateless; passed on all the same)."""
        for p in self.players:
            p.reset(games)

    def commands(self, obs: Tensor) -> Tensor:
        """obs [N, M, D] -> every skill's command [N, M, K, 4]."""
        return torch.stack([p.act(obs) for p in self.players], dim=2)

    def act(self, obs: Tensor, choice: Tensor) -> Tensor:
        """obs [N, M, D], choice [N, M] long (already resolved) -> the chosen skill's command [N, M, 4], by index (a
        gather, not a weighted sum: an unchosen skill's value never enters the result)."""
        every = self.commands(obs)
        idx = choice.to(torch.long)[:, :, None, None].expand(-1, -1, 1, every.shape[-1])
        return torch.gather(every, 2, idx)[:, :, 0]

    def greedy(self, logits: Tensor) -> Tensor:
        """logits [..., K] -> the argmax [...] long (first skill on a tie): the scoring play."""
        return logits.argmax(dim=-1)

    def resolve(self, choice: Tensor, obs: Tensor) -> Tensor:
        """Each drone's network choice [N, M] -> the choice that flies [N, M] long: unchanged per drone; per team, the
        choice of the lowest-index live drone in ``obs`` [N, M, D], given to every drone of the team."""
        choice = choice.to(torch.long)
        if self.choice == DRONE:
            return choice
        m = obs.shape[1]
        live = obs[..., _V.alive] > ALIVE_FLAG_MIN
        idx = torch.arange(m, device=obs.device)
        lead = torch.where(live, idx, m).amin(-1).clamp(max=m - 1)                  # [N]; drone 0 if none is live
        return torch.gather(choice, 1, lead[:, None]).expand(-1, m)


# ------------------------------------------------------------------ STE phase L3, slice 2: the two-level choice (R30)
# Design: ste_learning/drafts/L3_SLICE2_DESIGN.md. Per side, a team head (index 0 = "free", then the team strategies)
# and, per drone, a drone head over the skills that do not read their team-mates; a team strategy flies as written for
# every drone of the team, "free" lets each drone fly its own drone skill.

def _two_level_spec(table: dict) -> LearnerSpec:
    """The checks of choice = "two_level" that need no [players] list (``check_two_level`` does the rest)."""
    missing = [k for k in TWO_LEVEL_KEYS if k not in table]
    if missing:
        raise ValueError(f"[learner] choice = \"{TWO_LEVEL}\" needs {missing}")
    lists = {}
    for key in ("team_strategies", "drone_skills"):
        sub = table[key]
        if not isinstance(sub, dict) or sorted(sub) != sorted(SIDE_KEYS):
            raise ValueError(f"[learner.{key}] must have exactly the keys {list(SIDE_KEYS)}")
        for side, names in sub.items():
            if not isinstance(names, list) or not all(isinstance(n, str) for n in names):
                raise ValueError(f"[learner.{key}] {side} must be a list of player names")
        lists[key] = {side: tuple(sub[side]) for side in SIDE_KEYS}
    scale = table["entropy_scale"]
    if not isinstance(scale, dict) or sorted(scale) != sorted(HEADS):
        raise ValueError(f"[learner.entropy_scale] must have exactly the keys {list(HEADS)}")
    for head, v in scale.items():
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0:
            raise ValueError(f"[learner.entropy_scale] {head} must be a number > 0, got {v!r} (0 switches the entropy "
                             f"term off and a zero-initialised categorical head can collapse onto one skill)")
    return LearnerSpec(SKILLS, TWO_LEVEL, lists["team_strategies"], lists["drone_skills"],
                       {h: float(scale[h]) for h in HEADS})


def check_two_level(spec: LearnerSpec, players: dict) -> None:
    """A two-level spec against the gate file's ``[players]`` (ValueError names the first problem): per side, every
    name a player of that team; the two lists disjoint, without repeats, together the whole ``[players]`` list; neither
    empty; each in ``[players]`` order. Nothing to check for another spec."""
    if spec.choice != TWO_LEVEL:
        return
    for side in SIDE_KEYS:
        plist = team_skills(players, side)
        ts, ds = list(spec.team_strategies[side]), list(spec.drone_skills[side])
        where = f"[learner] {side}"
        bad = [n for n in ts + ds if n not in plist]
        if bad:
            raise ValueError(f"{where}: {bad} are not players of the {side} team {plist}")
        if len(set(ts)) != len(ts) or len(set(ds)) != len(ds):
            raise ValueError(f"{where}: a name is repeated inside a list")
        both = sorted(set(ts) & set(ds))
        if both:
            raise ValueError(f"{where}: {both} are in both team_strategies and drone_skills")
        left = [n for n in plist if n not in ts and n not in ds]
        if left:
            raise ValueError(f"{where}: {left} are in neither list (every [players] name must be in one)")
        if not ts or not ds:
            raise ValueError(f"{where}: team_strategies and drone_skills must both be non-empty")
        for key, names in (("team_strategies", ts), ("drone_skills", ds)):
            if names != [n for n in plist if n in names]:
                raise ValueError(f"{where}: {key} must follow the [players] order {plist}")


class TwoLevelDispatch(SkillDispatch):
    """The team's skills for the two-level choice: every player of ``players`` (the gate file's list of the team, in
    order) runs every tick, as in slice 1, and each drone flies the one its two heads resolve to (``resolve_two_level``).

    Network action per drone: [team index, drone index] (the action space ``MultiDiscrete([T+1, K_d])``); team index 0
    = "free", t >= 1 = ``team_strategies[t - 1]``; drone index d = ``drone_skills[d]``."""

    two_level = True

    def __init__(self, team: str, players: list[str], team_strategies: list[str], drone_skills: list[str], cfg: GameCfg,
                 num_games: int, device, seed: int):
        super().__init__(team, players, cfg, num_games, device, seed, DRONE)   # the gather is per drone
        self.choice = TWO_LEVEL
        bad = [n for n in list(team_strategies) + list(drone_skills) if n not in self.names]
        if bad or not team_strategies or not drone_skills:
            raise ValueError(f"two-level lists must be non-empty and name players of {self.names}; got {bad}")
        self.team_strategies, self.drone_skills = list(team_strategies), list(drone_skills)
        dev = torch.device(device)
        # index 0 of the team map is a placeholder: "free" never reads it (the drone map is used instead)
        self._team_map = torch.tensor([0] + [self.names.index(n) for n in self.team_strategies], device=dev)
        self._drone_map = torch.tensor([self.names.index(n) for n in self.drone_skills], device=dev)

    @property
    def widths(self) -> tuple[int, int]:
        """(T + 1, K_d): the team head's and the drone head's number of choices."""
        return len(self.team_strategies) + 1, len(self.drone_skills)

    def greedy(self, logits: Tensor) -> Tensor:
        """logits [..., T + 1 + K_d] -> each head's argmax [..., 2] long (first index on a tie)."""
        t, _ = self.widths
        return torch.stack((logits[..., :t].argmax(-1), logits[..., t:].argmax(-1)), dim=-1)

    def resolve_two_level(self, action: Tensor, obs: Tensor) -> tuple[Tensor, Tensor]:
        """action [N, M, 2] (each drone's [team, drone] sample), obs [N, M, D] -> (flown [N, M] long: the player index
        each drone flies, head_mask [N, M, 2] float 0/1). The leader is the lowest-index live drone in ``obs`` (with no
        live drone, the last one: the rule of slice 1's ``resolve``, whose comment says drone 0; such a game has ended
        and restarts); its team index is the team's. head_mask[..., 0] = 1 for the leader only (its team
        sample counts), head_mask[..., 1] = 1 for every drone when the leader chose "free" (its drone sample counts)."""
        a = action.to(torch.long)
        team_a, drone_a = a[..., 0], a[..., 1]
        m = obs.shape[1]
        live = obs[..., _V.alive] > ALIVE_FLAG_MIN
        idx = torch.arange(m, device=obs.device)
        lead = torch.where(live, idx, m).amin(-1).clamp(max=m - 1)                   # [N]
        t = torch.gather(team_a, 1, lead[:, None])[:, 0]                             # [N]
        free = t == FREE
        team_player = self._team_map.to(obs.device)[t]                               # [N]
        drone_player = self._drone_map.to(obs.device)[drone_a]                       # [N, M]
        flown = torch.where(free[:, None], drone_player, team_player[:, None].expand(-1, m))
        leader = idx[None, :] == lead[:, None]                                       # [N, M]
        mask = torch.stack((leader, free[:, None].expand(-1, m)), dim=-1).to(obs.dtype)
        return flown, mask

    def resolve(self, choice: Tensor, obs: Tensor) -> Tensor:
        """choice [N, M, 2] -> flown [N, M] (``resolve_two_level`` without the masks)."""
        return self.resolve_two_level(choice, obs)[0]


def two_level_dispatch(spec: LearnerSpec, players: dict, team: str, cfg: GameCfg, num_games: int, device,
                       seed: int) -> TwoLevelDispatch:
    """The ``TwoLevelDispatch`` of ``team`` from a two-level spec and the gate file's ``[players]``."""
    return TwoLevelDispatch(team, team_skills(players, team), list(spec.team_strategies[team]),
                            list(spec.drone_skills[team]), cfg, num_games, device, seed)
