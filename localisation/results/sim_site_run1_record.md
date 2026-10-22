# sim_site_run1 — cuVSLAM in the construction-site arena (2026-10-22, 22:49–22:53)

First flight in a textured world. Validation ladder `scenes/construction_site/VALIDATION.md` steps 1–6, all passed,
one change per step, Isaac headless, logs in `results/site_ladder/`.

## Setup
- World: `scenes/construction_site/build/construction_site_r40.usdc` — the user's UE4 construction site cropped to 40 m around
  site point (−29, −12.5), flattened, 68 unique materials, one sun, no Meerkat/person/extra lights. Launched with
  `ENV_USD=/isaac-sim/.local/share/ov/data/scenes/construction_site/construction_site_r40.usdc`.
- 3 Starling 2 Max SITL drones, ZED stereo on drone_1 at 640×480 (fx 245.3, baseline 0.120 m), `NUM_ROBOTS=3`.
- Commander `cbf_sim.yaml scenario:=random_goals`: takeoff 22:49:32, hover ×3 at 22:49:55, start, 3 min, hold, land, disarmed ×3 at 22:53:19.
- Node: `nodes/cuvslam_stereo_node.py` (stereo only, no IMU). Bag `results/bags/sim_site_run1/`.

## Result (reference = PX4 EKF2 on simulated GPS, NOT ground truth)
| metric | sim_site_run1 | runs 2–4 in the flat default world |
|---|---|---|
| path | 162.0 m | 25–197 m |
| APE SE(3)-aligned RMSE | **0.081 m** (0.05 % of path), max 0.29 m | 0.88–5.3 m |
| APE rotation RMSE | 2.6° | 17–159° |
| RPE per 1 m | 0.047 m | 0.27–1.7 m |
| frames lost | 0 of 6,167 poses | 0 (teleports were not flagged) |
| jumps > 1 m between poses | none (see diag plot) | 2 per run |

Clock offset −0.575 s (refined). Node at ~25 Hz wall, track p50 2.4 ms. Resources at 3 drones + camera + node: GPU ≤ 4.0 GB,
RTF 1.4 headless, load1 ~6–12, RAM 20 GB free. WiFi: 0 firmware alerts across 7 Isaac starts/stops.

## Caveats
- Same reference caveat as before (EKF2, not Isaac ground truth); lever arm uncompensated.
- Surfaces carry the export's 128×128 textures; the ground is a baked 1024² sand tint with bump shading. Features come from
  structure (containers, scaffolding, crane, fence, floodlight towers) 4–20 m away.
- Headless; a GUI viewport will cost more GPU.

## Interpretation
The 5–10 m teleports of runs 2–4 were an input problem (empty grid world: sky + horizon + repeating grid), not a tracker
problem. With structure in view, stereo-only cuVSLAM holds 5 cm/m relative error over 162 m in a ±2 m box with three drones.
