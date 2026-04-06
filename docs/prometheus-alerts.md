# Prometheus Alerting Rules for k8s-ai-sre

These rules target the `k8s-ai-sre` metrics endpoint (`GET /metrics`) and assume
a Prometheus scrape job configured to pull from the service.

## Prometheus scrape config

```yaml
scrape_configs:
  - job_name: k8s-ai-sre
    static_configs:
      - targets: ["k8s-ai-sre.ai-sre-system.svc.cluster.local:8080"]
    metrics_path: /metrics
```

## Alert rules

```yaml
groups:
  - name: k8s-ai-sre.approval-loop
    rules:

      # ─── Investigation health ───────────────────────────────────────────

      - alert: K8sAISREInvestigationsFailing
        expr: |
          sum(rate(k8s_ai_sre_investigation_latency_seconds_count[5m])) == 0
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "No k8s-ai-sre investigations completed in 5 minutes"
          description: |
            Prometheus has not observed any investigation latency observations
            in the last 5 minutes. Either no traffic is arriving or the
            investigation loop is silently failing before completing.

      - alert: K8sAISREInvestigationLatencyHigh
        expr: |
          histogram_quantile(0.95,
            sum(rate(k8s_ai_sre_investigation_latency_seconds_bucket[5m])) by (le)
          ) > 60
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "k8s-ai-sre investigation P95 latency exceeds 60s"
          description: |
            The 95th-percentile investigation duration is above 60 seconds.
            Check model API latency and cluster connectivity.

      # ─── Action proposal health ──────────────────────────────────────────

      - alert: K8sAISREActionProposalRateZero
        expr: |
          sum(rate(k8s_ai_sre_action_proposals_total[10m])) == 0
        for: 10m
        labels:
          severity: info
        annotations:
          summary: "No action proposals in 10 minutes"
          description: |
            No remediation actions have been proposed in the last 10 minutes.
            This is informational if the cluster is healthy.

      # ─── Approval loop health ────────────────────────────────────────────

      - alert: K8sAISREApprovalLatencyHigh
        expr: |
          histogram_quantile(0.95,
            sum(rate(k8s_ai_sre_approval_latency_seconds_bucket[5m])) by (le)
          ) > 300
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "k8s-ai-sre approval P95 latency exceeds 5 minutes"
          description: |
            The 95th-percentile time between action proposal and operator
            decision (approve/reject) is above 5 minutes. Verify Telegram
            connectivity or that the HTTP operator token path is not blocked.

      - alert: K8sAISREApprovalDecisionRateZero
        expr: |
          sum(rate(k8s_ai_sre_action_execution_outcomes_total[30m])) == 0
        for: 30m
        labels:
          severity: info
        annotations:
          summary: "No approval decisions in 30 minutes"
          description: |
            No terminal action decisions (approved/rejected/failed) have been
            recorded in 30 minutes. Informational — cluster may be healthy.

      # ─── Execution outcomes ──────────────────────────────────────────────

      - alert: K8sAISREActionFailureRateHigh
        expr: |
          (
            sum(rate(k8s_ai_sre_action_execution_outcomes_total{status="failed"}[5m]))
            /
            sum(rate(k8s_ai_sre_action_execution_outcomes_total[5m]))
          ) > 0.5
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Over 50% of k8s-ai-sre action executions are failing"
          description: |
            More than half of action executions are returning failed status.
            Inspect k8s-ai-sre logs for RBAC failures, network errors,
            or target object not found errors.

      - alert: K8sAISREActionRejectionRateHigh
        expr: |
          (
            sum(rate(k8s_ai_sre_action_execution_outcomes_total{status="rejected"}[5m]))
            /
            sum(rate(k8s_ai_sre_action_execution_outcomes_total[5m]))
          ) > 0.3
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Over 30% of k8s-ai-sre action executions are operator-rejected"
          description: |
            More than 30% of proposed actions are being rejected by operators.
            Review whether proposals are too aggressive or targeting wrong resources.

      # ─── Service availability ───────────────────────────────────────────

      - alert: K8sAISREServiceDown
        expr: |
          up{job="k8s-ai-sre"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "k8s-ai-sre is unreachable"
          description: |
            Prometheus cannot scrape k8s-ai-sre. The service may be down
            or the /metrics endpoint may be returning errors.
```

## Grafana dashboard

A minimal dashboard JSON is available at `docs/grafana-dashboard.json`.
Import it into your Grafana instance pointing at the Prometheus datasource.

### Dashboard panels

| Panel | Query | Description |
|---|---|---|
| Investigation throughput | `sum(rate(k8s_ai_sre_investigation_latency_seconds_count[5m]))` | Investigations/min |
| Investigation P95 latency | `histogram_quantile(0.95, rate(...investigation_latency_seconds_bucket[5m]))` | Seconds |
| Action proposal rate | `sum(rate(k8s_ai_sre_action_proposals_total[5m]))` | Proposals/min |
| Approval P95 latency | `histogram_quantile(0.95, rate(...approval_latency_seconds_bucket[5m]))` | Seconds |
| Execution outcome split | `sum(rate(k8s_ai_sre_action_execution_outcomes_total[5m])) by (status)` | approved/failed/rejected/min |
| Failure rate | `failed / total` from above | % |
