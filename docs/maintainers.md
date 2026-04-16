# Maintainers Guide

This docs site is intentionally small and should track shipped behavior only.

## Source-of-truth mapping

- `README.md`: public product behavior, quick-start snippets, guardrails
- `TESTING.md`: current validation runbook and verification checks
- Paperclip issues: active priorities and known limits

If any of these files change, update corresponding docs pages in the same PR.

## PR Routing

Use this review path for code and docs updates:

1. FoundingEngineer or the implementation owner opens the PR.
2. QA validates the branch and records evidence on the PR.
3. FoundingEngineer responds to QA findings, updates the branch, and refreshes evidence when needed.
4. A human reviewer merges after QA and required checks are complete.

QA evidence belongs on the PR itself:

- automated evidence in GitHub checks
- manual validation notes, screenshots, and kind or cluster artifacts in the PR description or comments
- short summaries with links or artifact paths instead of pasted logs

## Local docs build

```bash
uv tool run --with mkdocs mkdocs build --strict
```

The built site is generated into `site/`.

## GitHub Pages publishing

The workflow `.github/workflows/docs-pages.yml` handles docs CI and publishing:

- on pull requests: build docs to catch nav/render errors
- on pushes to `main`: build then deploy to GitHub Pages

Repository settings should use GitHub Actions as the Pages source.
