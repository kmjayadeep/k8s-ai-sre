# k8s-ai-sre Documentation

<section class="hero">
  <span class="eyebrow">Investigate, propose, approve, execute</span>
  <h2>Start the product, trigger an incident, and review the approval loop without digging through the whole repo.</h2>
  <p>`k8s-ai-sre` is an AI-assisted Kubernetes incident investigator with guarded remediation. Use this page to choose the fastest path for your role.</p>
  <div class="hero-actions">
    <a class="card" href="quickstart/">
      <strong>Quick Start</strong>
      <span>Run a local demo, trigger an investigation, and see the response shape in minutes.</span>
    </a>
    <a class="card" href="deployment/">
      <strong>Deploy to Kubernetes</strong>
      <span>Install with Helm or manifests, verify readiness, and keep rollback steps nearby.</span>
    </a>
    <a class="card" href="testing/">
      <strong>Validate the Full Loop</strong>
      <span>Follow the test runbook for investigate, notify, approve, and execute flows.</span>
    </a>
  </div>
  <div class="signal-grid">
    <div class="signal">
      <strong>Input channels</strong>
      <span>HTTP API, Alertmanager webhooks, and Telegram approvals.</span>
    </div>
    <div class="signal">
      <strong>Guardrails</strong>
      <span>Explicit approval, namespace allow-lists, and `kubectl auth can-i` checks.</span>
    </div>
    <div class="signal">
      <strong>Operator view</strong>
      <span>Readable incident summary, action proposals, and audit-friendly status flows.</span>
    </div>
  </div>
</section>

<section class="section-block">
  <h2>Choose the right path</h2>
  <div class="path-grid">
    <a class="card" href="quickstart/">
      <strong>I want to try it locally</strong>
      <span>Install dependencies, configure model access, create the demo scenario, and hit `/investigate`.</span>
    </a>
    <a class="card" href="deployment/">
      <strong>I need the cluster runbook</strong>
      <span>Use the canonical deploy, preflight, validation, and rollback instructions.</span>
    </a>
    <a class="card" href="contributing/">
      <strong>I’m changing the product</strong>
      <span>Start with the contributor path, then drop into setup and validation docs only where needed.</span>
    </a>
    <a class="card" href="architecture/">
      <strong>I need the system model</strong>
      <span>Review the architecture, evidence flow, and core moving parts before deeper changes.</span>
    </a>
  </div>
</section>

<section class="section-block">
  <h2>Current product scope</h2>
  <ul class="checklist">
    <li>Investigates pods and deployments with real Kubernetes reads.</li>
    <li>Collects evidence from object state, events, logs, and optional Prometheus queries.</li>
    <li>Accepts manual investigations at <code>/investigate</code> and Alertmanager webhooks at <code>/webhooks/alertmanager</code>.</li>
    <li>Stores incidents and pending actions in SQLite by default at <code>/tmp/k8s-ai-sre-store.sqlite3</code>.</li>
    <li>Sends Telegram notifications and supports <code>/incident</code>, <code>/status</code>, <code>/approve</code>, and <code>/reject</code>.</li>
    <li>Requires explicit approval before any remediation action executes.</li>
  </ul>
</section>

<section class="section-block">
  <h2>Operator loop</h2>
  <ol class="checklist">
    <li>An alert or manual request targets a Kubernetes object.</li>
    <li>The agent gathers evidence and explains the likely cause.</li>
    <li>The system proposes one or more remediation actions.</li>
    <li>An operator approves or rejects the proposal.</li>
    <li>Approved actions execute through the configured guardrails.</li>
  </ol>
  <p class="callout">If you only need one next step, start with <a href="quickstart/">Quick Start</a>. It is now the first path on this site and the fastest way to validate the product.</p>
</section>

## Source Of Truth

This docs site must stay aligned with repository sources:

- product behavior: `README.md`
- validation runbook: `TESTING.md`
- deploy/rollback and startup contract: `docs/deployment.md`
- active backlog and priorities: Paperclip issues for this project

When these sources change, update matching docs pages in the same pull request.
