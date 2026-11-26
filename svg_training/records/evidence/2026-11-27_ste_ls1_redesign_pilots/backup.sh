#!/bin/bash
while [ ! -f "$(dirname "$0")/STOP" ]; do
  rsync -a --exclude __pycache__ "$(cd "$(dirname "$0")" && pwd)/" ~/AirStack-starling-max2-dev/svg_training/runs/2026-11-27_ste_ls1r_pilots_scratch/
  sleep 600
done
