# Contributing

<div class="page-intro">
  <p>Use this page as the contributor landing page. It shows the shortest route from local setup to PR handoff, with the deeper validation and maintainer runbooks linked only where they become necessary.</p>
</div>

Use this page as the contributor entry point. It shows where to set up locally, how much validation to run, what to include in a PR, and who owns the merge.

## 1. Set up locally

Start with the [Developer Guide](developer.md) for dependency install, model configuration, local startup, and the main local commands.

Keep the validation references nearby:

- choose a validation lane in the [Validation guide](testing.md)
- run exact commands from [the repository `TESTING.md` runbook](https://github.com/kmjayadeep/k8s-ai-sre/blob/main/TESTING.md)

## 2. Pick the right validation lane

Run the lightest checks that still cover your change:

| Change type | Start here | Then run |
|---|---|---|
| docs-only copy or nav | this page | `uv tool run --with mkdocs mkdocs build --strict` |
| Python or runtime behavior | [Developer Guide](developer.md) | [Validation guide](testing.md), then [the repository `TESTING.md` runbook](https://github.com/kmjayadeep/k8s-ai-sre/blob/main/TESTING.md) if you need deeper coverage |
| Helm, Kustomize, or deploy manifests | [Validation guide](testing.md) | manifest checks from [the repository `TESTING.md` runbook](https://github.com/kmjayadeep/k8s-ai-sre/blob/main/TESTING.md) |
| end-to-end or alert flow changes | [Validation guide](testing.md) | kind or full alert-pipeline flows from [the repository `TESTING.md` runbook](https://github.com/kmjayadeep/k8s-ai-sre/blob/main/TESTING.md) |

## 3. Open or update a PR

Make the PR easy to validate:

- summarize the user-visible change
- list the commands already run
- link the docs or product pages you changed
- note where QA should look for evidence

## 4. Handoff to QA

QA validates the current PR head after contributor checks are complete.

Your handoff should call out:

- which validation lane you chose
- any artifact paths, screenshots, or logs worth checking
- the exact PR head commit if QA may need to re-run after later fixes
- whether commits changed after any earlier QA sign-off

## 5. Merge ownership

Contributors do not merge by default. The expected route is:

1. contributor opens or updates the PR
2. QA validates the current revision
3. contributor addresses feedback and requests re-validation if commits changed
4. a human reviewer or repo owner performs the final merge

You should not need the [Maintainers Guide](maintainers.md) for the normal contributor route. Use it only when you are handling release or repository-owner responsibilities.

## Related pages

- [Developer Guide](developer.md)
- [Validation guide](testing.md)
- [Repository `TESTING.md` runbook](https://github.com/kmjayadeep/k8s-ai-sre/blob/main/TESTING.md)
- [Maintainers Guide](maintainers.md)
