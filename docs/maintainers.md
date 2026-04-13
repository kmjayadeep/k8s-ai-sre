# Maintainers Guide

This docs site is intentionally small and should track shipped behavior only.

## Source-of-truth mapping

- `README.md`: public product behavior, quick-start snippets, guardrails
- `TESTING.md`: current validation runbook and verification checks
- `PLAN.md`: active priorities and known limits

If any of these files change, update corresponding docs pages in the same PR.

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
