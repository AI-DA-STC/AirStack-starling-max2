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

_MASK64 = (1 << 64) - 1
_SIGN64 = 1 << 63


def _signed64(x: int) -> int:
    """An integer's low 64 bits read as a signed int64 (two's complement)."""
    x &= _MASK64
    return x - (1 << 64) if x >= _SIGN64 else x


# splitmix64's increment and finaliser multipliers, as signed int64
_GOLDEN = _signed64(0x9E3779B97F4A7C15)
_MUL1 = _signed64(0xBF58476D1CE4E5B9)
_MUL2 = _signed64(0x94D049BB133111EB)
_SHIFTS = (30, 27, 31)


def _shr(z: Tensor, s: int) -> Tensor:
    """Logical right shift of int64 ``z`` by ``s`` (1..63): the arithmetic shift with its sign-extended top bits
    cleared."""
    return (z >> s) & ((1 << (64 - s)) - 1)


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
