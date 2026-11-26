#!/bin/bash
# usage: run.sh <script.py> [args...]; runs from the pilots folder, cwd for paths is svg_training via chdir in python
set -u
export OMP_NUM_THREADS=6 MKL_NUM_THREADS=6 CUDA_VISIBLE_DEVICES=""
unset PYTHONPATH
P=$(cd "$(dirname "$0")" && pwd)
cd ~/AirStack-starling-max2-dev/svg_training
exec env PYTHONPATH=source:$P ~/miniconda3/envs/env_isaaclab/bin/python -u "$P/$1" "${@:2}"
