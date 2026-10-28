#!/usr/bin/env bash
# Installs the pre-commit guard into THIS clone's .git/hooks (run once per clone; hooks are not versioned).
set -eu
root=$(git rev-parse --show-toplevel)
cp "$root/tools/git-hooks/pre-commit" "$root/.git/hooks/pre-commit" && chmod +x "$root/.git/hooks/pre-commit"
echo "installed: $root/.git/hooks/pre-commit"
