"""STE phase L3, slice 3, step 1: ``ste/pool.pool_draw``, the opponent pool's draw (design note
ste_learning/drafts/L3_SLICE3_DESIGN.md §2 and "Revision after the review").

The k-th game of slot g plays opponent ``pool_draw(seed, g, k, K)``: a pure function of (seed, slot, game counter), so
both routes see the same opponent for the same (slot, k) whatever their game-end timing. splitmix64-style mixing in
int64 tensor ops (constants wrapped to signed int64, logical shifts emulated by a mask, ``torch.remainder``).

Checked against an independent pure-Python reference on unsigned 64-bit integers, against literal values (made by that
reference, 24 Nov 2026), on the CPU and, when a GPU is visible, on CUDA with the same literals; uniform; the same
result for any batch shape or order."""
import pytest
import torch

from svg_training.ste import pool

MASK = (1 << 64) - 1


def ref_mix(z: int) -> int:
    z = (z + 0x9E3779B97F4A7C15) & MASK
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK
    return z ^ (z >> 31)


def ref_draw(seed: int, slot: int, k: int, choices: int) -> int:
    """The reference: unsigned 64-bit arithmetic in Python integers; the mixed value read as signed, then Python's %
    (non-negative for a positive modulus, as torch.remainder)."""
    x = ref_mix(seed & MASK)
    x = ref_mix(x ^ (slot & MASK))
    x = ref_mix(x ^ (k & MASK))
    signed = x - (1 << 64) if x >= (1 << 63) else x
    return signed % choices


# literal values (from ref_draw, 24 Nov 2026): (seed, choices) -> draws over the listed (slot, k)
GRID_A = [(g, k) for g in range(4) for k in range(3)]
GRID_B = [(g, k) for g in (0, 7, 4095) for k in (0, 1, 1000)]
LITERALS = {
    (0, 5, "A"): [3, 4, 3, 2, 3, 4, 3, 0, 0, 2, 2, 0],
    (0, 6, "B"): [3, 4, 1, 0, 2, 0, 0, 0, 2],
    (130001, 5, "A"): [3, 1, 1, 4, 4, 1, 4, 1, 4, 4, 1, 4],
    (130001, 6, "B"): [2, 3, 3, 5, 2, 2, 0, 3, 2],
}
DEVICES = ["cpu"] + (["cuda"] if torch.cuda.is_available() else [])


def draws(seed, grid, choices, device):
    slot = torch.tensor([g for g, _ in grid], dtype=torch.long, device=device)
    k = torch.tensor([k for _, k in grid], dtype=torch.long, device=device)
    return pool.pool_draw(seed, slot, k, choices)


@pytest.mark.parametrize("device", DEVICES)
@pytest.mark.parametrize("key", sorted(LITERALS))
def test_the_draws_equal_the_literal_values(key, device):
    seed, choices, grid = key
    got = draws(seed, GRID_A if grid == "A" else GRID_B, choices, device)
    assert got.dtype == torch.long and got.device.type == device
    assert got.tolist() == LITERALS[key]


def test_the_literals_are_the_references():
    for (seed, choices, grid), want in LITERALS.items():
        assert [ref_draw(seed, g, k, choices) for g, k in (GRID_A if grid == "A" else GRID_B)] == want


@pytest.mark.parametrize("device", DEVICES)
def test_the_draws_equal_the_pure_python_reference_on_many_inputs(device):
    gen = torch.Generator().manual_seed(1)
    slot = torch.randint(0, 1 << 20, (4000,), generator=gen)
    k = torch.randint(0, 1 << 30, (4000,), generator=gen)
    for seed, choices in ((0, 5), (130001, 6), (2**62 + 12345, 7), (-3, 5)):
        got = pool.pool_draw(seed, slot.to(device), k.to(device), choices).cpu().tolist()
        assert got == [ref_draw(seed, int(g), int(n), choices) for g, n in zip(slot, k)], (seed, choices)


def test_the_draw_is_uniform_over_the_choices():
    """Chi-square over 10^5 draws (slots x game counters), K = 5 and 6: below the 0.999 quantile (18.47 for 4 degrees
    of freedom, 20.52 for 5)."""
    slot = torch.arange(1000).repeat_interleave(100)
    k = torch.arange(100).repeat(1000)
    for choices, limit in ((5, 18.47), (6, 20.52)):
        counts = torch.bincount(pool.pool_draw(130001, slot, k, choices), minlength=choices).double()
        expected = slot.numel() / choices
        assert float(((counts - expected) ** 2 / expected).sum()) < limit, (choices, counts.tolist())


def test_a_draw_depends_only_on_its_own_seed_slot_and_counter():
    """Route independence: the same (slot, k) gives the same opponent in any batch, shape or order."""
    slot = torch.tensor([5, 1, 5, 9, 1])
    k = torch.tensor([2, 0, 2, 7, 3])
    full = pool.pool_draw(7, slot, k, 6)
    assert full[0] == full[2]
    perm = torch.tensor([4, 2, 0, 3, 1])
    assert torch.equal(pool.pool_draw(7, slot[perm], k[perm], 6), full[perm])
    assert torch.equal(pool.pool_draw(7, slot.reshape(5, 1), k.reshape(5, 1), 6), full.reshape(5, 1))
    other = pool.pool_draw(8, torch.arange(200), torch.zeros(200, dtype=torch.long), 6)
    same = pool.pool_draw(7, torch.arange(200), torch.zeros(200, dtype=torch.long), 6)
    assert not torch.equal(other, same)


@pytest.mark.parametrize("bad,why", [
    ({"choices": 0}, "choices"),
    ({"seed": 1.5}, "seed"),
    ({"seed": True}, "seed"),
    ({"slot": torch.tensor([1.0])}, "long"),
    ({"slot": torch.tensor([0, 1]), "k": torch.tensor([0])}, "shape"),
    ({"slot": torch.tensor([-1])}, "non-negative"),
])
def test_bad_arguments_are_refused(bad, why):
    args = {"seed": 1, "slot": torch.tensor([0]), "k": torch.tensor([0]), "choices": 5, **bad}
    with pytest.raises(ValueError, match=why):
        pool.pool_draw(args["seed"], args["slot"], args["k"], args["choices"])
