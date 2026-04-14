#!/usr/bin/env bash
set -euo pipefail

# Always run from repository root so relative paths remain stable.
cd "$(dirname "${BASH_SOURCE[0]}")/.."

uv sync --locked
uv run python -m unittest \
  tests.test_ci_smoke_api_contract \
  tests.test_ci_smoke_alert_approval_loop
