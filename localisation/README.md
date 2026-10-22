# localisation-exploration

Exploration phase (Oct–Nov 2026) for multi-drone localisation: cuVSLAM in the Isaac sim, a
ground-truth degrader, a UWB emulator, an option-C aligner and the scorer. Lives OUTSIDE the
AirStack clones on purpose; nothing here is in CMU's tree.

- `reports/`, `research_notes/` — day-1 literature review (every number sourced; nothing is our result).
- `docker/` — exploration image = CMU robot image + cuVSLAM 17.0.1 (cu12 wheel) + GTSAM. `build.sh`, `run.sh`.
- `data/downloads/` — wheels/tarballs with SHA256SUMS; `data/cuVSLAM-src/` — SDK v17.0.1 source (examples, tests).
- `nodes/` — ROS 2 (Jazzy) nodes written here. `scripts/` — helpers. `results/` — bags, evo output, effort log.

Licence note: cuVSLAM is under the NVIDIA Community License (use on NVIDIA platforms); flag to the lead like YOLO's AGPL.
