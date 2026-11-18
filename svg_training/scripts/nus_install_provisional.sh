#!/usr/bin/env bash
# Install the lab's PROVISIONAL NUS-port files (nus_provisional/, owner decision 6, 18 Nov 2026) where the code reads them:
#   nus_provisional/configs/*   -> configs/local/
#   nus_provisional/nus_port/*  -> runs/nus_port/
# Both targets are git-ignored. Every file's sha256 is checked against nus_provisional/SHA256SUMS before anything is copied.
#
#   scripts/nus_install_provisional.sh [--dry-run] [--force] [--dest <svg_training folder>]
#
#   --dry-run  print what would be copied, copy nothing
#   --force    replace a target file whose content differs (default: refuse, so the lab's own local files are never overwritten)
#   --dest     install into another svg_training folder (default: the one holding this script; tests use a temporary folder)
#
# Exit codes: 0 installed (or already installed, or dry run); 1 refused (a checksum mismatch, a file missing from the bundle, or a
#             different target file without --force; nothing is copied); 2 bad argument.
set -euo pipefail

usage() { awk 'NR > 1 && /^#/ { sub(/^# ?/, ""); print; next } NR > 1 { exit }' "$0"; }

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$HERE/nus_provisional"
DEST="$HERE"
DRY=0
FORCE=0
while [ $# -gt 0 ]; do
    case "$1" in
        --dry-run) DRY=1 ;;
        --force) FORCE=1 ;;
        --dest) DEST="${2:?--dest needs a folder}"; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "unknown argument: $1 (see --help)" >&2; exit 2 ;;
    esac
    shift
done
[ -d "$DEST" ] || { echo "no such folder: $DEST" >&2; exit 2; }
DEST="$(cd "$DEST" && pwd)"
[ -f "$SRC/SHA256SUMS" ] || { echo "refusing: $SRC/SHA256SUMS not found" >&2; exit 1; }

# 1. the bundle is intact: every listed file present with its sha256, and no unlisted file under configs/ or nus_port/
if ! (cd "$SRC" && sha256sum --check --quiet --strict SHA256SUMS); then
    echo "refusing: nus_provisional/ does not match its SHA256SUMS (nothing copied)" >&2
    exit 1
fi
unlisted="$(cd "$SRC" && comm -23 <(find configs nus_port -type f | LC_ALL=C sort) <(awk '{print $2}' SHA256SUMS | LC_ALL=C sort))"
if [ -n "$unlisted" ]; then
    echo "refusing: files in nus_provisional/ not listed in SHA256SUMS: $unlisted" >&2
    exit 1
fi

target_of() {   # bundle path -> installed path
    case "$1" in
        configs/*) echo "$DEST/configs/local/${1#configs/}" ;;
        nus_port/*) echo "$DEST/runs/nus_port/${1#nus_port/}" ;;
    esac
}

# 2. conflicts: a target that exists with other content is refused unless --force
conflicts=()
while read -r sum rel; do
    t="$(target_of "$rel")"
    if [ -e "$t" ] && [ "$(sha256sum "$t" | cut -d' ' -f1)" != "$sum" ]; then
        conflicts+=("$t")
    fi
done < "$SRC/SHA256SUMS"
if [ "${#conflicts[@]}" -gt 0 ] && [ "$FORCE" -eq 0 ]; then
    echo "refusing: ${#conflicts[@]} target file(s) exist with other content (nothing copied; --force replaces them):" >&2
    printf '  %s\n' "${conflicts[@]}" >&2
    exit 1
fi

# 3. copy
copied=0; same=0
while read -r sum rel; do
    t="$(target_of "$rel")"
    if [ -e "$t" ] && [ "$(sha256sum "$t" | cut -d' ' -f1)" = "$sum" ]; then
        same=$((same + 1)); continue
    fi
    echo "+ $rel -> ${t#"$DEST"/}"
    if [ "$DRY" -eq 0 ]; then
        mkdir -p "$(dirname "$t")"
        cp "$SRC/$rel" "$t"
    fi
    copied=$((copied + 1))
done < "$SRC/SHA256SUMS"
if [ "$DRY" -eq 1 ]; then
    echo "dry run: $copied file(s) would be copied, $same already in place"
else
    echo "installed: $copied file(s) copied, $same already in place (PROVISIONAL: see nus_provisional/README.md)"
fi
