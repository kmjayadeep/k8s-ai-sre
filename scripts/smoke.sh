#!/usr/bin/env bash
set -euo pipefail

# Always run from repository root so relative paths remain stable.
cd "$(dirname "${BASH_SOURCE[0]}")/.."

uv sync --locked
uv run python -m unittest \
  tests.test_startup \
  tests.test_investigate \
  tests.test_http_integration \
  tests.test_tool_actions
