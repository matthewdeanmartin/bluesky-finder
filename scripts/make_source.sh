#!/usr/bin/env bash
set -euo pipefail

git2md . \
  --ignore .idea __init__.py __pycache__ \
  .venv .markdownlintrc \
  dead_code data docs scripts \
  __about__.py logging_config.py py.typed utils \
  .gitignore  .pre-commit-config.yaml .ruff_cache README* \
  LICENSE SOURCE.md \
  .cache \
  uv.lock \
  --output SOURCE.md