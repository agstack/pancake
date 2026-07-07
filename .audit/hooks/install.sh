#!/bin/sh
# Symlink FATFD hooks into .git/hooks
HOOKS_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(git -C "$HOOKS_DIR" rev-parse --show-toplevel)"
ln -sf "$HOOKS_DIR/pre-commit" "$REPO_ROOT/.git/hooks/pre-commit"
chmod +x "$HOOKS_DIR/pre-commit"
echo "FATFD pre-commit hook installed."
