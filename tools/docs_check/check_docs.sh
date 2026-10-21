#!/usr/bin/env bash
# Thin wrapper: run the documentation checker from the repo root.
# Usage: tools/docs_check/check_docs.sh [--warn-only] [--json] [--selftest]
# Exit 0 = no FAIL, 1 = at least one FAIL (or --selftest failed).
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"
exec python3 -I tools/docs_check/check_docs.py "$@"
