"""STE phase L3, slice 3: the opponent pool (design note ste_learning/drafts/L3_SLICE3_DESIGN.md §2 and its "Revision
after the review"). Step 1: :func:`pool_draw`, the draw.

Both routes train against a pool of the other team's scripts, one drawn per game, uniform. Which games end, and when,
differ between the routes, so the draw is a function of the game's identity, not of a generator's state: the k-th game
of slot g plays opponent ``pool_draw(seed, g, k, K)``. Both routes therefore see the same opponent for the same
(slot, k), whatever their timing.

The mixing is splitmix64's finaliser (Steele, Lea and Flood 2014; the constants of Java's ``SplittableRandom``) applied
three times, to the seed, then with the slot, then with the game counter, in int64 tensor ops: the 64-bit constants
are wrapped to signed int64 (int64 multiplication and addition wrap modulo 2^64 on the CPU and on CUDA), a logical
right shift is an arithmetic shift with the sign-extended bits masked off, and the choice is ``torch.remainder`` (non-
negative for a negative mixed value). Batched: no per-game Python loop.

Shapes: ``slot`` and ``k`` long tensors of one shape (any), non-negative; the result has that shape, long, on their
device."""
from __future__ import annotations

import torch
from torch import Tensor

_INT64_BITS = 64
_MASK64 = (1 << _INT64_BITS) - 1
_SIGN64 = 1 << (_INT64_BITS - 1)


def _signed64(x: int) -> int:
    """An integer's low 64 bits read as a signed int64 (two's complement)."""
    x &= _MASK64
    return x - (1 << _INT64_BITS) if x >= _SIGN64 else x


# splitmix64's increment and finaliser multipliers, as signed int64
_GOLDEN_U64 = 0x9E3779B97F4A7C15
_MUL1_U64 = 0xBF58476D1CE4E5B9
_MUL2_U64 = 0x94D049BB133111EB
_GOLDEN = _signed64(_GOLDEN_U64)
_MUL1 = _signed64(_MUL1_U64)
_MUL2 = _signed64(_MUL2_U64)
_SHIFTS = (30, 27, 31)


def _shr(z: Tensor, s: int) -> Tensor:
    """Logical right shift of int64 ``z`` by ``s`` (1..63): the arithmetic shift with its sign-extended top bits
    cleared."""
    return (z >> s) & ((1 << (_INT64_BITS - s)) - 1)


def _mix(z: Tensor) -> Tensor:
    """splitmix64's step (increment, then finaliser) on int64 ``z``, wrapping modulo 2^64."""
    z = z + _GOLDEN
    z = (z ^ _shr(z, _SHIFTS[0])) * _MUL1
    z = (z ^ _shr(z, _SHIFTS[1])) * _MUL2
    return z ^ _shr(z, _SHIFTS[2])


def pool_draw(seed: int, slot: Tensor, k: Tensor, choices: int) -> Tensor:
    """The opponent index (0..choices-1) of game number ``k`` of slot ``slot`` under pool seed ``seed``.

    seed: a Python int (its low 64 bits are used); slot, k: long tensors of one shape, non-negative; choices: K >= 1.
    ValueError names the first bad argument."""
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError(f"seed must be an int, got {seed!r}")
    if isinstance(choices, bool) or not isinstance(choices, int) or choices < 1:
        raise ValueError(f"choices must be an int >= 1, got {choices!r}")
    for name, t in (("slot", slot), ("k", k)):
        if not isinstance(t, Tensor) or t.dtype != torch.long:
            raise ValueError(f"{name} must be a long tensor")
    if slot.shape != k.shape:
        raise ValueError(f"slot and k must have one shape, got {tuple(slot.shape)} and {tuple(k.shape)}")
    if bool((slot < 0).any()) or bool((k < 0).any()):
        raise ValueError("slot and k must be non-negative")
    x = _mix(torch.full_like(slot, _signed64(seed)))
    x = _mix(x ^ slot)
    x = _mix(x ^ k)
    return torch.remainder(x, choices)


# ------------------------------------------------------------------ step 2: the pool itself
EXCLUDED = ("random",)        # RandomActions draws from its own stateful generator (lead's answer 2, 24 Nov 2026)
TEAM_PLAYERS = {"guard": "guards", "strike": "strikes"}


def pool_members(players: dict, team: str) -> list[str]:
    """The pool of ``team``: the gate file's ``[players]`` list of that team, in order, without ``random``."""
    return [p for p in players[TEAM_PLAYERS[team]] if p not in EXCLUDED]


class OpponentPool:
    """The other team as a pool of its scripts (design §2): game slot g plays script ``names[draw[g]]``, ``draw[g] =
    pool_draw(seed, g, k[g], K)``, k[g] its game counter. k = 0 is drawn at construction; ``redraw(games)`` (called by
    ``exploit_train.DecisionEnv`` after its decision-boundary restart) advances the counter of those games and draws
    again; ``reset(games)`` (the core's tick-level reset of a stale game, the scoring helpers) keeps the draw. ``act``
    runs every script on the batch and gathers each game's (no per-game loop). ``name`` is
    ``OpponentPool(<names>)``, what the train log and ``trained_against`` report.

    team: the pool's team; names: K scripted-player names (``opponents/scripted.REGISTRY``), not ``random``; cfg,
    num_games, device: as ``make_strategy``; seed: the pool seed (``[pool] seed``)."""

    def __init__(self, team: str, names: list[str], cfg, num_games: int, device, seed: int):
        from ..opponents.scripted import make_strategy
        if not names:
            raise ValueError("an opponent pool needs at least one script (empty list)")
        bad = [n for n in names if n in EXCLUDED]
        if bad:
            raise ValueError(f"{bad} cannot be in an opponent pool: random draws from its own stateful generator")
        self.team, self.names, self.seed = team, list(names), int(seed)
        self.name = "OpponentPool(" + ",".join(self.names) + ")"
        self.scripts = [make_strategy(n, team, cfg, num_games, device, seed) for n in self.names]
        dev = torch.device(device)
        self._slot = torch.arange(int(num_games), dtype=torch.long, device=dev)
        self.k = torch.zeros(int(num_games), dtype=torch.long, device=dev)
        self.draw = pool_draw(self.seed, self._slot, self.k, len(self.names))

    def reset(self, games: Tensor) -> None:
        """games [N] bool: the scripts are stateless; the draw is kept (a stale game, not trained)."""
        for s in self.scripts:
            s.reset(games)

    def redraw(self, games: Tensor) -> None:
        """games [N] bool: a new game starts in these slots (the decision-boundary restart): k + 1, a new draw."""
        self.k = self.k + games.to(torch.long)
        self.draw = torch.where(games, pool_draw(self.seed, self._slot, self.k, len(self.names)), self.draw)

    def act(self, obs: Tensor) -> Tensor:
        """obs [N, M, D] -> each game's own script's command [N, M, 4] (every script runs; gathered by ``draw``)."""
        every = torch.stack([s.act(obs) for s in self.scripts], dim=2)                 # [N, M, K, 4]
        idx = self.draw[:, None, None, None].expand(-1, every.shape[1], 1, every.shape[-1])
        return torch.gather(every, 2, idx)[:, :, 0]

    def state(self) -> dict:
        """What a checkpoint keeps: the game counters (the draws follow from them)."""
        return {"names": list(self.names), "seed": self.seed, "k": self.k.clone()}

    def load_state(self, state: dict) -> None:
        if state["names"] != self.names or int(state["seed"]) != self.seed:
            raise ValueError(f"the checkpoint's pool {state['names']} (seed {state['seed']}) is not this pool "
                             f"{self.names} (seed {self.seed})")
        self.k = state["k"].to(self.k.device)
        self.draw = pool_draw(self.seed, self._slot, self.k, len(self.names))
