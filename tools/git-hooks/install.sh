#!/usr/bin/env bash
# Activates the versioned pre-commit guard in THIS clone: git runs tools/git-hooks/pre-commit directly (core.hooksPath),
# so there is no copy to go stale. tools/sim.sh setup runs this; tools/sim.sh doctor fails when it has not run.
set -eu
root=$(git rev-parse --show-toplevel); cd "$root"
old="$(git rev-parse --git-common-dir)/hooks/pre-commit"          # computed BEFORE hooksPath is set (git-path would follow it)
git config core.hooksPath tools/git-hooks
if [ -f "$old" ] && head -3 "$old" | grep -q 'pre-commit guard'; then rm -f "$old"; fi   # the pre-2026-11 copy
echo "pre-commit guard active: core.hooksPath = tools/git-hooks ($root)"
