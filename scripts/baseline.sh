#!/usr/bin/env bash
set -euo pipefail

# Always run from repository root so relative paths remain stable.
cd "$(dirname "${BASH_SOURCE[0]}")/.."

uv sync --locked
uv run python -m unittest discover -s tests
