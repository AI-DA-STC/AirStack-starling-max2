# Docker: the training simulator in a container

A *container* is a sealed copy of the software that runs the same way on every machine. Ours starts from NVIDIA's
image `nvcr.io/nvidia/isaac-lab:2.3.2` (Isaac Sim 5.1, Isaac Lab 2.3.2), unchanged, and adds `pytest` and a few
variables. The project folder is mounted when the container starts, so a code change needs no rebuild. It runs
without a display (*headless*). Step by step, with what to expect: [GETTING_STARTED](../docs/GETTING_STARTED.md).
Versions: [GLOSSARY](../docs/GLOSSARY.md#versions).

The table shows how the same job is started on the host and in the container.

| Job | On the host | In the container |
|---|---|---|
| Python | `~/miniconda3/envs/env_isaaclab/bin/python` | `svg-python` (Isaac Sim's `python.sh`, but the exit code is kept) |
| Isaac Lab | `~/IsaacLab/isaaclab.sh` | `/workspace/isaaclab` (NVIDIA's image, unmodified), started by `svg-isaaclab` |
| Tier 2 start | `conda run -n env_isaaclab ... isaaclab.sh -p` | `svg-isaaclab -p` |

`scripts/run_s0.sh` reads `SVG_IN_CONTAINER`, `SVG_PY` and `SVG_ISAACLAB`. The image sets them. On the host they are unset.

## Commands

```
docker/build.sh                                        # once; downloads NVIDIA's base image (about 26 GB)
docker/run.sh '$SVG_PY -m pytest -q'                   # the tests
docker/run.sh                                          # an interactive shell in /workspace/svg_training
docker/run.sh bash scripts/run_s0.sh <name> <approved sha256>
```

The approved sha256 is a fingerprint of the config the owner approved (its *hash*). How to check it:
[GETTING_STARTED](../docs/GETTING_STARTED.md#approved-sha256). A mismatch stops the run (exit 65).

`docker/run.sh --print ...` shows the `docker run` line and starts nothing. Arguments are joined with spaces and
run by `bash -lc`, so quote a compound command as one argument.

## What is stored where

- `runs/` and `records/` are on the host (the mounted folder). After each command they are handed back to your user.
- Isaac's caches and logs are named docker volumes, prefixed `svg-training-isaac-`. List them with `docker volume ls`.
- Nothing else in the container survives it (`--rm`).

## Cautions

- The first tier 2 run downloads NVIDIA's drone asset. The machine needs internet access.
- The script's "is the GPU busy" check sees only processes inside its own container. Run `nvidia-smi` on the host first.
