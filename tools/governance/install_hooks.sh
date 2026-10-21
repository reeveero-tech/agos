#!/usr/bin/env bash
# Install the AGOS governance git hooks for this clone (run once after cloning).
set -e
cd "$(git rev-parse --show-toplevel)"
git config core.hooksPath .githooks
chmod +x .githooks/*
echo "✓ AGOS governance hooks installed (core.hooksPath=.githooks)"
