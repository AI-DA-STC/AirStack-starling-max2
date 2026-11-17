"""The ``SvgGame._draw_starts`` hook (NUS port Phase 4, owner-approved, 18 November 2026): the default body is the same call as before,
so the random stream, the starts, the arenas and a short game are bit-identical. The hashes below were taken from the game BEFORE the
hook existed (pure partner rules and the Starling layer, 6 games of 2 Guard drones and 1 Strike drone, seed 5, 25 random-action steps,
then a reset with seed 7). They hold no partner value."""
import hashlib

import torch

from svg_training.core.arena import draw_starts
from svg_training.core.game import SvgGame
from svg_training.core.game_config import load_game_cfg

GOLDEN = {  # name -> (start hash, hash after the steps, hash after the reset)
    "pure": ("686fe3d18a86b09b", "657b109265d8b8b4", "2a697df91009bb5f"),
    "starling": ("686fe3d18a86b09b", "5873c7afbc0e401f", "2a697df91009bb5f"),
}
GAMES, GUARDS, STRIKES, STEPS, SEED, RESET_SEED, ACTION_SEED = 6, 2, 1, 25, 5, 7, 1


def _hash(*tensors) -> str:
    digest = hashlib.sha256()
    for t in tensors:
        digest.update(t.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest()[:16]


def _cfg(name):
    cfg, _ = load_game_cfg(use_local=False)
    return cfg if name == "pure" else cfg.replace(**{"starling.enabled": True})


def test_default_stream_is_bit_identical_to_the_game_before_the_hook():
    for name, (start, after, reset) in GOLDEN.items():
        game = SvgGame(_cfg(name), GAMES, GUARDS, STRIKES, device="cpu", seed=SEED)
        a = game.arenas
        assert _hash(game.pos_m, a.side_m, a.zone_centre_m, a.zone_radius_m, game.start_miss) == start, name
        gen = torch.Generator().manual_seed(ACTION_SEED)
        for _ in range(STEPS):
            game.step({"guard": torch.rand(GAMES, GUARDS, 4, generator=gen) * 2 - 1, "strike": torch.rand(GAMES, STRIKES, 4, generator=gen) * 2 - 1})
        assert _hash(game.pos_m, game.vel_mps, game.steps) == after, name
        game.reset(seed=RESET_SEED)
        a = game.arenas      # the reset hash was taken without the zone radius
        assert _hash(game.pos_m, a.side_m, a.zone_centre_m, game.start_miss) == reset, name


def test_the_hook_is_the_old_call():
    game = SvgGame(_cfg("pure"), GAMES, GUARDS, STRIKES, device="cpu", seed=SEED)
    ar = game._draw_arenas()
    state = game.gen.get_state()
    starts, miss = game._draw_starts(ar)
    game.gen.set_state(state)
    again, again_miss = draw_starts(game.cfg, ar, GUARDS, STRIKES, game.gen, return_miss=True)
    assert torch.equal(starts, again) and torch.equal(miss, again_miss)


def test_a_subclass_can_replace_the_starts():
    class Fixed(SvgGame):
        def _draw_starts(self, arenas):
            return torch.full((self.num_games, self.M, 3), 0.25), torch.ones(self.num_games, dtype=torch.bool)

    game = Fixed(_cfg("pure"), GAMES, GUARDS, STRIKES, device="cpu", seed=SEED)
    assert torch.all(game.pos_m == 0.25) and bool(game.start_miss.all())
