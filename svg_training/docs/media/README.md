# Replay animations of the training simulator

Training simulator (PyTorch, point drones), scripted strategies, committed neutral game settings; not a real flight.
Blue circles are Guard drones, orange triangles are Strike drones, the green disc is the zone, a faint x is a drone
that is out. Drones on top of each other show as nested markers; marker size only tells the drones of a team apart. Clips play at 2x real time (the game step is 0.05 s). MP4: 1280 x 960 px, 20 frames/s. GIF: 800 x 600 px, 10 frames/s (fewer frames to stay small; same 2x speed). Regenerate any clip with
`PYTHONPATH=source ~/miniconda3/envs/env_isaaclab/bin/python scripts/make_replay.py --only <name>` from `svg_training/`
(CPU only; the Starling-layer clip took about 75 s on this laptop on 16 November 2026). Each name gives `<name>.gif` and `<name>.mp4`.

| Name | Caption | Command (`--only`) |
|---|---|---|
| `2v1_pure` | 2 Guard drones v 1 Strike drone, pure rules. Guards mark inside, the Strike drone flanks. The Guard team holds the zone for the full 60 s. Middle-size arena, seed 0. | `2v1_pure` |
| `5v3_pure` | 5 Guard drones v 3 Strike drones, pure rules. Guards use the field tactic, Strike drones go straight. The Guard team holds the zone for the full 60 s. Middle-size arena, seed 0. | `5v3_pure` |
| `5v3_starling` | 5 v 3 with the Starling layer on (commander, safety filter, fitted drone model; exploratory), after the wall fix. Guards mark inside, Strike drones flank. The Guard team holds the zone for the full 60 s. Middle-size arena, seed 0. | `5v3_starling` |
| `strike_wins` | 5 v 3, pure rules, random Guards against straight-flying Strike drones: the Strike team reaches the zone after 7.1 s. Middle-size arena, seed 0. | `strike_wins` |

`5v3_starling` was made again on 16 November 2026 on the fixed Starling layer (wall fix, commit `17197a7`; filter check every 8). In the 8 games played for it, the closest Guard–Strike approach was 1.03–1.12 m (keep-out 1.10 m); the game shown comes to 1.03 m, the shallow open-space loss of the exploratory drone model. The earlier clip's 0.81 m dip came from the wall bug, not from the drone model.
