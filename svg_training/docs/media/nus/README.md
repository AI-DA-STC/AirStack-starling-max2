# Videos of the NUS port

Training simulator only; nothing here is a flight. Published with NUS's agreement (owner, 18 November 2026; STANDARDS
§2). The story behind each clip: [NUS_PORT](../../NUS_PORT.md).

**Two kinds of clip.**

- `nus_*`: **NUS's own 2-D game and NUS's JAX policies**, drawn by NUS's renderer (their `eval.py`, `save_eval_gif=True`),
  on the hangar geometry (0.40 m per unit, 0.60 s per step; [NUS_PORT §3](../../NUS_PORT.md#3-phase-0-answers-and-the-hangar-geometry)).
  Blue discs D0–D2 are Guard drones (NUS: "defender"), red discs A0–A2 are Strike drones (NUS: "attacker"), the green
  disc is the zone. The title bar shows NUS's environment name and the step (200 per game). NUS's game keeps the
  "reached" flag once a Strike drone has been inside the zone, and the game runs on to step 200, so a Strike drone
  may leave the zone again: the outcome is the first entry, not the last frame. Converted from NUS's 640 × 640 GIFs
  to H.264 MP4, 12.5 frames/s (2 steps a second; about 6× real time at 0.6 s per step), all 201 frames.
- Phase 4 clips (`p4_*`) are not published yet: their title shows the hangar's size, which the owner keeps local (18 Nov 2026). They stay on the 5090 under `runs/nus_port/phase4/row_*/videos/`.

| File | Caption | Source (5090 only) | Size |
|---|---|---|---|
| `nus_fixed_guard_vs_scripted_strike.mp4` | Fixed-opponent Guard policy (3,000 updates, the run converted as P3G) against NUS's scripted Strike controller. No Strike drone enters the zone in 200 steps (last evaluation: 19 of 20 held). | NUS outputs `hangar/2026-11-17_fixed_apf_3v3_defender/replays/defender_vs_apf_00003000_env0.gif` | 58 kB |
| `nus_fixed_strike_vs_scripted_guard.mp4`, `.gif` | Fixed-opponent Strike policy (the run converted as P3S) against NUS's scripted Guard controller. A Strike drone reaches the zone at about step 7 (last evaluation: 20 of 20 reached). | `hangar/2026-11-17_fixed_apf_3v3_attacker/replays/attacker_vs_apf_00003000_env0.gif` | 76 kB, 161 kB |
| `nus_selfplay_s1_g7_vs_s1_s8.mp4` | Self-play seed 1: Guard generation 7 against Strike generation 8. The Guard team holds (that pair: 0.005 Strike wins over 200 games). | `_probes/selfplay_eval/videos/s1_guard7_vs_strike8/` | 49 kB |
| `nus_selfplay_s2_g7_vs_s2_s8.mp4` | Self-play seed 2: Guard generation 7 against Strike generation 8. A Strike drone reaches the zone at about step 25 (that pair: 1.000 over 200 games), the "last mover wins" pattern of generations 1–12. | `_probes/selfplay_eval/videos/s2_guard7_vs_strike8/` | 73 kB |
| `nus_selfplay_s2_g19_vs_s2_s20.mp4`, `.gif` | The reference pair: seed 2 Guard generation 19 (G19) against Strike generation 20 (S20). The Guard team holds for 200 steps (that pair: 0.025 over 200 games). | `_probes/selfplay_eval/videos/s2_guard19_vs_strike20/` | 58 kB, 168 kB |
| `nus_selfplay_s2_g19_vs_s3_s8.mp4` | G19 against a policy it never met: seed 3 Strike generation 8. The Guard team holds (that pair: 0.120 over 200 games). | `_probes/selfplay_eval/videos/s2_guard19_vs_s3strike8/` | 62 kB |
| Isaac Lab camera clips (row 6) | results pending (running since 18 Nov 05:52): the converted policies on rigid-body Starlings in Isaac Lab come with Phase 6 pass 2. | — | — |

**Size budget.** 13 files, 1.25 MB in total (budget 20 MB; the repository already carries about 45 MB of clips and
figures). The GIFs (360 or 480 px, 5–6 frames/s) are there because GitHub shows GIFs inline on a page and MP4 files
only as downloads.

**How they were made** (home RTX 5090, 18 November 2026, the `ffmpeg` in `~/miniconda3/bin`):

```bash
# NUS GIF -> MP4 (all frames) and a small inline GIF
ffmpeg -i <nus.gif> -movflags +faststart -pix_fmt yuv420p -c:v libx264 -crf 28 -preset slow -vf "scale=640:-2" <name>.mp4
ffmpeg -i <nus.gif> -vf "fps=6.25,scale=360:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=48[p];[b][p]paletteuse=dither=none" <name>.gif
# Phase 4 MP4 -> smaller MP4
ffmpeg -i <row clip.mp4> -movflags +faststart -pix_fmt yuv420p -c:v libx264 -crf 28 -preset slow -vf "scale=800:-2" -an <name>.mp4
```

NUS's GIFs come from NUS's `eval.py` with `save_eval_gif=True`; for self-play policies the evaluation config was edited
so the opponent pool holds one archive entry (the self-play runner writes no GIFs itself). The Phase 4 clips come from
`scripts/nus_phase4.py` (`--render <row folder>` makes them again).
