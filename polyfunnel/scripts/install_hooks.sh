#!/usr/bin/env bash
# Install POLYFUNNEL git hooks into the enclosing repo's .git/hooks.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
GIT_DIR="$(git rev-parse --git-dir)"
install -m 0755 "$HERE/hooks/pre-commit" "$GIT_DIR/hooks/pre-commit"
echo "Installed pre-commit secret scan -> $GIT_DIR/hooks/pre-commit"
