<section class="hero">
  <div class="eyebrow">Kubernetes incident response docs</div>
  <h1>Investigate first. Approve before anything mutates.</h1>
  <p><code>k8s-ai-sre</code> helps operators inspect Kubernetes incidents, propose remediations, and execute only after an explicit approval step.</p>
  <div class="hero-actions">
    <a class="cta" href="quickstart/">Run the quick start</a>
    <a class="cta secondary" href="deployment/">Plan a cluster deployment</a>
    <a class="cta secondary" href="architecture/">Review the architecture</a>
  </div>
  <div class="pill-row">
    <span class="pill">Pods and deployments</span>
    <span class="pill">HTTP and Telegram workflow</span>
    <span class="pill">Guarded write actions</span>
  </div>
</section>

<div class="page-intro">
  <p>This site is the human-facing guide for operators and contributors. Start with the path that matches your goal, then use the deeper runbooks for deployment, validation, and maintenance details.</p>
</div>

## Choose Your Path

<div class="card-grid">
  <article class="doc-card">
    <h3>Operator path</h3>
    <p>Get from first run to a validated incident loop quickly.</p>
    <p><strong>Start with:</strong> <a href="quickstart/">Quick Start</a></p>
    <p>Then move to <a href="deployment/">Deployment</a> and <a href="architecture/">Architecture</a> when you need production context.</p>
  </article>
  <article class="doc-card">
    <h3>Contributor path</h3>
    <p>Use the docs site as the entry point for local setup, validation, and PR handoff.</p>
    <p><strong>Start with:</strong> <a href="contributing/">Contributing</a></p>
    <p>Then use <a href="developer/">Developer Guide</a> and <a href="testing/">Validation</a> for exact execution lanes.</p>
  </article>
</div>

## Current Product Scope

The repository currently implements:

- investigation for pods and deployments with real Kubernetes reads
- evidence collection from resource state, events, logs, and optional Prometheus queries
- API-triggered investigations (`/investigate`) and Alertmanager webhook handling (`/webhooks/alertmanager`)
- SQLite-backed persistence for incidents and pending actions (default path `/tmp/k8s-ai-sre-store.sqlite3`)
- Telegram notifications and approval commands (`/incident`, `/status`, `/approve`, `/reject`)
- guarded remediation actions that require explicit approval before execution

## Operator Loop

<ol class="steps">
  <li><strong>Ingest:</strong> an alert or manual request targets a Kubernetes object through HTTP or Alertmanager.</li>
  <li><strong>Investigate:</strong> the agent gathers real resource state, events, logs, and optional Prometheus evidence.</li>
  <li><strong>Propose:</strong> the service returns concrete remediation actions with approval and rejection paths.</li>
  <li><strong>Decide:</strong> an operator approves or rejects from Telegram or the HTTP operator API.</li>
  <li><strong>Execute safely:</strong> approved actions run only inside the configured namespace guardrails.</li>
</ol>

## Start Here By Goal

<div class="card-grid compact">
  <article class="doc-card">
    <h3>Local trial run</h3>
    <p>Install dependencies, configure a model provider, and trigger a sample investigation.</p>
    <p><a href="quickstart/">Open Quick Start</a></p>
  </article>
  <article class="doc-card">
    <h3>Cluster rollout</h3>
    <p>Use the Helm-first deployment path, startup contract, and rollback guidance.</p>
    <p><a href="deployment/">Open Deployment</a></p>
  </article>
  <article class="doc-card">
    <h3>Contributor workflow</h3>
    <p>Follow setup, validation lanes, QA handoff, and merge ownership in one sequence.</p>
    <p><a href="contributing/">Open Contributing</a></p>
  </article>
  <article class="doc-card">
    <h3>System internals</h3>
    <p>Review the service components, orchestration flow, and enforced write-action guardrails.</p>
    <p><a href="architecture/">Open Architecture</a></p>
  </article>
</div>

## Source Of Truth

This docs site must stay aligned with repository sources:

- product behavior: `README.md`
- validation runbook: `TESTING.md`
- deploy/rollback and startup contract: `docs/deployment.md`
- near-term priorities and constraints: `PLAN.md`

When these sources change, update matching docs pages in the same pull request.

## Trusted References

<ul class="link-list">
  <li><a href="https://github.com/kmjayadeep/k8s-ai-sre/blob/main/README.md">Product behavior in README.md</a></li>
  <li><a href="https://github.com/kmjayadeep/k8s-ai-sre/blob/main/TESTING.md">Exact validation commands in TESTING.md</a></li>
  <li><a href="deployment/">Deploy and rollback contract</a></li>
  <li><a href="contributing/">Contributor workflow entry page</a></li>
</ul>
