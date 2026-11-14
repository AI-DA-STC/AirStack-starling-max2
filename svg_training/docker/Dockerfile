# Training simulator for the Strike/Guard training pipeline: Isaac Lab in a container.
# NVIDIA's image (Isaac Sim 5.1 + Isaac Lab 2.3.2) is used unmodified underneath; this adds only pytest and a
# few environment variables that scripts/run_s0.sh reads to find Python and isaaclab.sh.
#
# Build:  docker/build.sh          Run:  docker/run.sh [command...]
# The project folder is MOUNTED at /workspace/svg_training at run time, not copied in,
# so a code change needs no rebuild.
ARG ISAACLAB_IMAGE=nvcr.io/nvidia/isaac-lab:2.3.2
FROM ${ISAACLAB_IMAGE}

# The tests run under Isaac Sim's own Python; harmless if pytest is already there.
RUN /workspace/isaaclab/isaaclab.sh -p -m pip install --no-cache-dir "pytest>=8"

# Two launchers that keep the child's exit code. Isaac Sim's python.sh (and so `isaaclab.sh -p`) turns every
# non-zero exit into 1, and scripts/run_s0.sh tells exit 1 (a crash row was written), 2 (asset not loadable)
# and 3 (nothing to run) apart. They set up the same environment as python.sh and isaaclab.sh -p, then exec.
RUN printf '%s\n' '#!/bin/bash' \
      '# Isaac Sim python.sh without its exit-code flattening (see docker/Dockerfile).' \
      'export CARB_APP_PATH=/isaac-sim/kit ISAAC_PATH=/isaac-sim EXP_PATH=/isaac-sim/apps' \
      'source /isaac-sim/setup_python_env.sh' \
      'export RESOURCE_NAME=IsaacSim LD_PRELOAD=/isaac-sim/kit/libcarb.so' \
      'exec /isaac-sim/kit/python/bin/python3 "$@"' > /usr/local/bin/svg-python \
 && printf '%s\n' '#!/bin/bash' \
      '# `isaaclab.sh -p <script> ...` without the exit-code flattening (see docker/Dockerfile).' \
      'if [ "${1:-}" = "-p" ]; then shift; fi' \
      'export ISAACLAB_PATH=/workspace/isaaclab' \
      'exec /usr/local/bin/svg-python "$@"' > /usr/local/bin/svg-isaaclab \
 && chmod +x /usr/local/bin/svg-python /usr/local/bin/svg-isaaclab

# SVG_*: read by scripts/run_s0.sh (container mode: no conda, the launchers above).
ENV SVG_IN_CONTAINER=1 \
    SVG_PY=/usr/local/bin/svg-python \
    SVG_ISAACLAB=/usr/local/bin/svg-isaaclab \
    ACCEPT_EULA=Y \
    PRIVACY_CONSENT=Y \
    TERM=xterm

# Build-time check that starts no simulator. find_spec only: importing isaaclab would start Kit, which needs a GPU.
RUN ${SVG_PY} -c "import torch, tomllib, pytest, importlib.util as u; assert u.find_spec('isaaclab_contrib') and u.find_spec('isaaclab'); print('torch', torch.__version__)"
# The launchers pass exit codes through.
RUN ${SVG_PY} -c "raise SystemExit(3)"; test $? -eq 3
RUN ${SVG_ISAACLAB} -p -c "raise SystemExit(2)"; test $? -eq 2

WORKDIR /workspace/svg_training
