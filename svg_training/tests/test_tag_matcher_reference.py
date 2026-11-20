"""STE task L0.9, fix round 1 (QC item I3): ``core/pair_rules.proximity_tags`` against a plain greedy reference.

The reference below is written for reading, not speed: list every live Guard-Strike pair strictly closer than the radius,
then repeatedly take the closest pair whose two drones are both free (ties to the lower Guard index, then the lower
Strike index), until none is left. The batched matcher must give the same tagged drones, the same drones left in the
game and the same partners, on random games of many team sizes (with dead drones, Guards that survive, and grid
positions that make many exact ties). Two explicit cases pin an off-diagonal pair at 2v2 and 3v3, which every earlier
fixture missed (an index encoded as s*G+g but decoded as g*S+s passed them all). CPU, made-up positions.
"""
import pathlib
import random
import sys

import pytest
import torch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
from svg_training.core.pair_rules import proximity_tags  # noqa: E402

RADIUS_M = 1.6
SIZES = [(1, 1), (2, 1), (1, 2), (2, 2), (3, 3), (5, 3), (3, 5), (4, 2)]


def reference(points: torch.Tensor, alive: list[bool], guards: int, radius_m: float, survives: bool):
    """Plain greedy matcher for ONE game. points [M, 3] float32 (Guard drones first). Returns (tagged, alive_after,
    partner) as lists."""
    m = len(alive)
    strikes = m - guards
    pairs = {}
    for g in range(guards):
        for s in range(strikes):
            if alive[g] and alive[guards + s]:
                d = (points[g] - points[guards + s]).norm().item()      # the same float32 maths as the matcher
                if d < radius_m:
                    pairs[(g, s)] = d
    used_g, used_s, partner = set(), set(), [-1] * m
    while True:
        open_pairs = [(d, g, s) for (g, s), d in pairs.items() if g not in used_g and s not in used_s]
        if not open_pairs:
            break
        _, g, s = min(open_pairs)                                       # closest, then lower g, then lower s
        used_g.add(g)
        used_s.add(s)
        partner[g], partner[guards + s] = guards + s, g
    tagged = [i in used_g for i in range(guards)] + [s in used_s for s in range(strikes)]
    after = [alive[i] and not (tagged[i] and (i >= guards or not survives)) for i in range(m)]
    return tagged, after, partner


def random_games(rng: random.Random, guards: int, strikes: int, n: int):
    """n random games: half on a 0.5 m grid (many exact ties), half uniform; about 1 drone in 5 out; survive 50 %."""
    grid = rng.random() < 0.5
    pts = [[(rng.randint(-2, 2) * 0.5, rng.randint(-2, 2) * 0.5, 1.0 + rng.randint(0, 1) * 0.5) if grid else
            (rng.uniform(-1.5, 1.5), rng.uniform(-1.5, 1.5), rng.uniform(0.5, 1.8)) for _ in range(guards + strikes)]
           for _ in range(n)]
    alive = [[rng.random() > 0.2 for _ in range(guards + strikes)] for _ in range(n)]
    survives = [rng.random() < 0.5 for _ in range(n)]
    return torch.tensor(pts, dtype=torch.float32), alive, survives


@pytest.mark.parametrize("guards, strikes", SIZES)
def test_the_matcher_equals_the_plain_greedy_reference(guards, strikes):
    rng = random.Random(1000 * guards + strikes)
    checked = tagged_pairs = 0
    for _ in range(150):
        pos, alive, survives = random_games(rng, guards, strikes, 4)
        tagged, after, partner = proximity_tags(pos, torch.tensor(alive), guards, RADIUS_M, torch.tensor(survives))
        for i in range(len(alive)):
            want = reference(pos[i], alive[i], guards, RADIUS_M, survives[i])
            assert (tagged[i].tolist(), after[i].tolist(), partner[i].tolist()) == want, (
                guards, strikes, pos[i].tolist(), alive[i], survives[i])
            checked += 1
            tagged_pairs += sum(want[0][:guards])
    assert checked == 600 and tagged_pairs > 100                        # the cases do tag, often


def test_2v2_only_g0_s1_in_range():
    """Only G0-S1 is within 1.6 m: G0 and S1 are tagged, G1 and S0 stay in."""
    pos = torch.tensor([[(0.0, 0.0, 1.2), (5.0, 0.0, 1.2), (0.0, 5.0, 1.2), (1.0, 0.0, 1.2)]])
    tagged, after, partner = proximity_tags(pos, torch.ones(1, 4, dtype=torch.bool), 2, RADIUS_M,
                                            torch.zeros(1, dtype=torch.bool))
    assert tagged[0].tolist() == [True, False, False, True]
    assert after[0].tolist() == [False, True, True, False]
    assert partner[0].tolist() == [3, -1, -1, 0]


def test_3v3_off_diagonal_pairs():
    """3v3, the base case: G0-S2 and G2-S0 in range (and G1 alone): the off-diagonal pairs are tagged as such."""
    pos = torch.tensor([[(0.0, 0.0, 1.2), (10.0, 0.0, 1.2), (20.0, 0.0, 1.2),
                         (20.5, 0.0, 1.2), (-10.0, 5.0, 1.2), (1.2, 0.0, 1.2)]])
    tagged, _, partner = proximity_tags(pos, torch.ones(1, 6, dtype=torch.bool), 3, RADIUS_M,
                                        torch.zeros(1, dtype=torch.bool))
    assert tagged[0].tolist() == [True, False, True, True, False, True]
    assert partner[0].tolist() == [5, -1, 3, 2, -1, 0]
