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

from dataclasses import dataclass

import torch
from torch import Tensor

from ..core.game_config import GameCfg
from ..core.observations import ObsView
from ..opponents.scripted import make_strategy

VELOCITY, SKILLS = "velocity", "skills"
ACTIONS = (VELOCITY, SKILLS)                    # [learner] action
TEAM, DRONE = "team", "drone"
CHOICES = (TEAM, DRONE)                         # [learner] choice (skills route only)
TEAM_PLAYERS = {"guard": "guards", "strike": "strikes"}    # the gate file's [players] list of each team = its skills
_V = ObsView()
ALIVE_FLAG_MIN = 0.5                            # the observation's own-alive flag is 0 or 1 (scripted.py reads it so)


@dataclass(frozen=True)
class LearnerSpec:
    """The ``[learner]`` table as loaded: action (ACTIONS), choice (CHOICES for the skills route, None for velocity)."""
    action: str
    choice: str | None

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
    unknown = sorted(set(table) - {"action", "choice"})
    if unknown:
        raise ValueError(f"unknown key(s) in [learner]: {unknown}")
    action = table.get("action", VELOCITY)
    if action not in ACTIONS:
        raise ValueError(f"[learner] action must be one of {ACTIONS}, got {action!r}")
    if action == VELOCITY:
        if "choice" in table:
            raise ValueError("[learner] choice belongs to the skills route only (action = \"skills\")")
        return LearnerSpec(VELOCITY, None)
    choice = table.get("choice")
    if choice not in CHOICES:
        raise ValueError(f"[learner] action = \"skills\" needs choice one of {CHOICES}, got {choice!r}")
    return LearnerSpec(SKILLS, choice)


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
