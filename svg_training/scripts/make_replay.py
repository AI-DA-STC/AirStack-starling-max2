#!/usr/bin/env python
"""Make the top-down replay animations of Strike vs Guard games (GIF and MP4) into docs/media/.

  make_replay.py [--out docs/media] [--only 2v1_pure,5v3_pure,5v3_starling,strike_wins] [--formats gif,mp4]
                 [--games 8] [--seed 0]

Plays a few games on the CPU with the committed neutral game settings (never the partner's local file), picks one
game per clip and renders it. Each clip is a fixed (matchup, seed) so the same command gives the same clip.
Training simulator, point drones, scripted strategies: not a real flight."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "source"))
from svg_training.core.game_config import load_game_cfg  # noqa: E402
from svg_training.core.rewards import GUARD_WIN, STRIKE_WIN  # noqa: E402
from svg_training.viz.replay import Recording, record_games, render_replay  # noqa: E402

# name -> (guards, strikes, guard strategy, strike strategy, starling layer, seed, wanted outcome)
CLIPS = {
    "2v1_pure": (2, 1, "guard_mark_inside", "strike_flank", False, 0, GUARD_WIN),
    "5v3_pure": (5, 3, "guard_field", "strike_straight", False, 0, GUARD_WIN),
    "5v3_starling": (5, 3, "guard_mark_inside", "strike_flank", True, 0, GUARD_WIN),
    "strike_wins": (5, 3, "random", "strike_straight", False, 0, STRIKE_WIN),
}
# Both formats play at 2 x real time (the game step is 0.05 s): MP4 = 1280 x 960 px, 20 frames/s, 2 steps per frame;
# GIF = 800 x 600 px, 10 frames/s, 4 steps per frame (fewer frames keep it under 5 MB).
FORMATS = {"mp4": dict(speed=2, fps=20, dpi=120), "gif": dict(speed=4, fps=10, dpi=75)}


def pick(recs: list[Recording], want: int) -> Recording:
    """The game with the wanted result that is most worth watching: a Guard hold with the closest approach of the
    two teams (smallest closest_cross_m), a Strike win that takes the longest."""
    ok = [r for r in recs if r.outcome == want]
    if not ok:
        raise RuntimeError(f"none of the {len(recs)} games ended with the wanted result; try another --seed")
    if want == STRIKE_WIN:
        return max(ok, key=lambda r: r.end_step)
    return min(ok, key=lambda r: r.closest_cross_m)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", default=str(ROOT / "docs" / "media"))
    ap.add_argument("--only", default=",".join(CLIPS))
    ap.add_argument("--formats", default="gif,mp4")
    ap.add_argument("--games", type=int, default=8)
    ap.add_argument("--seed", type=int, default=None, help="override every clip's seed")
    a = ap.parse_args(argv)
    cfg, _ = load_game_cfg(use_local=False)
    for name in [s.strip() for s in a.only.split(",") if s.strip()]:
        g, s, gs, ss, starling, seed, want = CLIPS[name]
        seed = seed if a.seed is None else a.seed
        recs = record_games(cfg.replace(**{"starling.enabled": starling}), g, s, gs, ss, a.games, seed=seed)
        rec = pick(recs, want)
        print(f"{name}: seed {seed}, game {rec.game_index} of {a.games}, {rec.band} arena, outcome {rec.outcome}, "
              f"{rec.end_step} steps ({rec.end_time_s:.1f} s)", flush=True)
        for fmt in [f.strip() for f in a.formats.split(",") if f.strip()]:
            p = render_replay(rec, Path(a.out) / f"{name}.{fmt}", playback_label="2x real time", **FORMATS[fmt])
            print(f"  wrote {p} ({p.stat().st_size / 1e6:.2f} MB)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
