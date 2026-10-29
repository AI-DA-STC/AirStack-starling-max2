#!/usr/bin/env bash
# Regenerates the committed figures under docs/record/figures/ from the run folders named HERE.
# Run BY HAND when a figure should change — a new run never alters a figure silently. Sim only (iron rule 9).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
mkdir -p docs/record/figures
python3 tools/hover_step_plot.py --overlay docs/record/sim_hover_step_run1 docs/record/sim_hover_step_run2 docs/record/sim_hover_step_run3 \
  --time-scale sim_hover_step_run1=1.336 \
  --label sim_hover_step_run1='#17' --label sim_hover_step_run2='#18' --label sim_hover_step_run3='#19' \
  -o docs/record/figures/s5_hover_step_overlay.png
python3 tools/live/plot_metrics.py docs/record/sim_crossing_dry1/metrics.csv --plots tools/sim_tests/crossing/plots.json -o docs/record/figures/s5_crossing_distances.png
