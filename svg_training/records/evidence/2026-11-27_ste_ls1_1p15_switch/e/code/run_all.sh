#!/bin/bash
# step E dispatcher: jobs.txt lines, 2 at a time, from svg_training/ (scratch)
E=$(dirname "$(readlink -f "$0")")
cd ~/AirStack-starling-max2-dev/svg_training
run1() { set -- $1; n=$1; env -u PYTHONPATH CUDA_VISIBLE_DEVICES= PYTHONPATH=source:$E ~/miniconda3/envs/env_isaaclab/bin/python -u $E/e_run.py "$@" > $E/logs/$n.log 2>&1; echo "$(date +%H:%M) end $n $?" >> $E/dispatch.log; }
export -f run1; export E
echo "$(date +%H:%M) start" >> $E/dispatch.log
xargs -P 2 -I{} bash -c 'run1 "{}"' < $E/jobs.txt
echo "$(date +%H:%M) all done" >> $E/dispatch.log
