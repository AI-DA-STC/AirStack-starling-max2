#!/usr/bin/env bash
# Check a training workstation before anything is installed on it (docs/WORKSTATION_SETUP.md step 1).
# UNTESTED ON THE 5090: written and checked on the laptop with `bash -n` and --dry-run only (2026-11-17).
#
#   scripts/workstation/check_machine.sh [--dry-run] [--skip-docker] [--help]
#
# Read-only: it changes nothing on the machine. It prints the GPU and driver, the OS, free disk and memory,
# whether Docker can see the GPU, whether conda and the two conda environments exist, and the helper programs
# (git, rsync, tmux, tailscale). The Docker check runs `docker run --rm --gpus all ubuntu nvidia-smi -L`, which
# downloads the small `ubuntu` image the first time; --skip-docker leaves it out.
#
# Exit codes:
#   0  every required check passed (warnings may be printed)
#   1  a required check failed: no NVIDIA driver, driver older than 580, or less than 60 GB free in $HOME
#   2  unknown argument
set -uo pipefail

DRIVER_MIN=580          # the laptop runs 580.178; Isaac Sim 5.1 and JAX with CUDA 13 need a recent driver
DISK_MIN_GB=60          # about 26 GB for NVIDIA's Isaac Lab image, the rest for run folders

usage() { awk 'NR > 1 && /^#/ { sub(/^# ?/, ""); print; next } NR > 1 { exit }' "$0"; }

DRY=0
SKIP_DOCKER=0
for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY=1 ;;
        --skip-docker) SKIP_DOCKER=1 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "unknown argument: $arg (see --help)" >&2; exit 2 ;;
    esac
done

if [ "$DRY" -eq 1 ]; then
    echo "DRY RUN: the checks this script would run (nothing is run):"
    echo "  nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader   (driver >= $DRIVER_MIN)"
    echo "  nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader"
    echo "  lsb_release -ds   (expect Ubuntu 24.04)"
    echo "  df -BG --output=avail \$HOME   (at least $DISK_MIN_GB GB)"
    echo "  free -g; nproc"
    if [ "$SKIP_DOCKER" -eq 0 ]; then
        echo "  docker run --rm --gpus all ubuntu nvidia-smi -L"
    fi
    echo "  conda info --base; conda env list   (env_isaaclab, nus_jax)"
    echo "  command -v git rsync tmux tailscale"
    exit 0
fi

FAILS=0
WARNS=0
ok()   { echo "  OK    $*"; }
warn() { echo "  WARN  $*"; WARNS=$((WARNS + 1)); }
fail() { echo "  FAIL  $*"; FAILS=$((FAILS + 1)); }

echo "== GPU and driver"
if command -v nvidia-smi > /dev/null 2>&1; then
    GPU_LINE="$(nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader 2>/dev/null | head -n 1)"
    if [ -z "$GPU_LINE" ]; then
        fail "nvidia-smi is installed but lists no GPU"
    else
        echo "  $GPU_LINE"
        DRIVER="$(printf '%s' "$GPU_LINE" | awk -F', ' '{print $2}')"
        MAJOR="${DRIVER%%.*}"
        if [[ "$MAJOR" =~ ^[0-9]+$ ]] && [ "$MAJOR" -ge "$DRIVER_MIN" ]; then
            ok "driver $DRIVER (>= $DRIVER_MIN)"
        else
            fail "driver '$DRIVER' is older than $DRIVER_MIN: update the NVIDIA driver first"
        fi
        case "$GPU_LINE" in
            *5090*) ok "RTX 5090 found" ;;
            *) warn "this is not an RTX 5090; the workstation docs assume one" ;;
        esac
    fi
    echo "== GPU users now (pid, program, MiB)"
    APPS="$(nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader 2>/dev/null)"
    if [ -n "$APPS" ]; then
        printf '%s\n' "$APPS" | sed 's/^/  /'
        warn "the GPU has users: check them before starting a run"
    else
        ok "no compute process on the GPU"
    fi
else
    fail "nvidia-smi not found: install the NVIDIA driver ($DRIVER_MIN or newer)"
fi

echo "== Operating system"
OS="$(lsb_release -ds 2>/dev/null || (. /etc/os-release 2>/dev/null && echo "$PRETTY_NAME"))"
echo "  ${OS:-unknown}"
case "$OS" in
    *24.04*) ok "Ubuntu 24.04" ;;
    *) warn "not Ubuntu 24.04: the setup scripts were written for it" ;;
esac

echo "== Disk, memory, processors"
AVAIL_GB="$(df -BG --output=avail "$HOME" 2>/dev/null | tail -n 1 | tr -dc '0-9')"
if [ -n "$AVAIL_GB" ] && [ "$AVAIL_GB" -ge "$DISK_MIN_GB" ]; then
    ok "${AVAIL_GB} GB free in $HOME (>= $DISK_MIN_GB)"
else
    fail "${AVAIL_GB:-?} GB free in $HOME: need at least $DISK_MIN_GB GB"
fi
echo "  memory: $(free -g 2>/dev/null | awk '/^Mem:/ {print $2 " GB total, " $7 " GB available"}')"
echo "  processors: $(nproc 2>/dev/null || echo '?')"

echo "== Docker with the GPU"
if [ "$SKIP_DOCKER" -eq 1 ]; then
    echo "  skipped (--skip-docker)"
elif ! command -v docker > /dev/null 2>&1; then
    warn "docker not found: needed for the container route (GETTING_STARTED part A), not for the host route"
elif docker run --rm --gpus all ubuntu nvidia-smi -L 2>&1 | sed 's/^/  /'; then
    ok "containers can see the GPU"
else
    warn "docker could not reach the GPU: install the NVIDIA Container Toolkit, or add your user to the docker group"
fi

echo "== conda"
CONDA="$(command -v conda 2>/dev/null || true)"
[ -z "$CONDA" ] && [ -x "$HOME/miniconda3/bin/conda" ] && CONDA="$HOME/miniconda3/bin/conda"
if [ -n "$CONDA" ]; then
    ok "conda at $CONDA (base $("$CONDA" info --base 2>/dev/null))"
    ENVS="$("$CONDA" env list 2>/dev/null)"
    for env in env_isaaclab nus_jax; do
        if printf '%s\n' "$ENVS" | awk '{print $1}' | grep -qx "$env"; then
            echo "  env $env: present"
        else
            echo "  env $env: not yet created"
        fi
    done
else
    warn "conda not found: install Miniconda before setup_isaaclab_host.sh or setup_nus_jax.sh"
fi

echo "== Helper programs"
for prog in git rsync tmux tailscale; do
    if command -v "$prog" > /dev/null 2>&1; then
        ok "$prog"
    else
        warn "$prog not found"
    fi
done

echo "== Summary: $FAILS failed, $WARNS warnings"
[ "$FAILS" -eq 0 ] || exit 1
exit 0
