#!/usr/bin/env bash
# Build the training-simulator image on top of NVIDIA's Isaac Lab image. Context = docker/ (nothing is copied in).
# Another base image: ISAACLAB_IMAGE=nvcr.io/nvidia/isaac-lab:<tag> docker/build.sh (the tag below stays the same).
set -euo pipefail
cd "$(dirname "$0")"
TAG=svg-training:isaaclab-2.3.2
docker build --build-arg "ISAACLAB_IMAGE=${ISAACLAB_IMAGE:-nvcr.io/nvidia/isaac-lab:2.3.2}" -t "$TAG" .
echo "built $TAG"
