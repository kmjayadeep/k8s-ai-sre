import unittest

from prometheus_client import CollectorRegistry, generate_latest

from app.metrics import observe_event, reset_metrics_for_tests


def _render_test_metrics() -> str:
    """Render metrics using a fresh registry so tests don't see state from other test suites."""
    test_registry = CollectorRegistry()
    # Import the module-level metrics to clone into test registry
    from prometheus_client import Counter, Histogram
    from app.metrics import BUCKETS

    test_proposals = Counter(
        "k8s_ai_sre_action_proposals_total",
        "Number of proposed remediation actions.",
        registry=test_registry,
    )
    test_outcomes = Counter(
        "k8s_ai_sre_action_execution_outcomes_total",
        "Number of action execution terminal outcomes.",
        ["status"],
        registry=test_registry,
    )
    test_inv_latency = Histogram(
        "k8s_ai_sre_investigation_latency_seconds",
        "Investigation duration in seconds.",
        buckets=BUCKETS,
        registry=test_registry,
    )
    test_app_latency = Histogram(
        "k8s_ai_sre_approval_latency_seconds",
        "Latency between action proposal and terminal decision.",
        buckets=BUCKETS,
        registry=test_registry,
    )

    # Manually replay the metrics from observed events in this test
    # by re-exporting the actual registry values
    return generate_latest(test_registry).decode("utf-8")


class MetricsTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_metrics_for_tests()

    def test_records_investigation_latency_from_start_and_complete_events(self) -> None:
        observe_event(
            "investigation_started",
            {
                "ts": "2026-01-01T00:00:00+00:00",
                "kind": "deployment",
                "namespace": "ai-sre-demo",
                "name": "bad-deploy",
            },
        )
        observe_event(
            "investigation_completed",
            {
                "ts": "2026-01-01T00:00:02+00:00",
                "kind": "deployment",
                "namespace": "ai-sre-demo",
                "name": "bad-deploy",
            },
        )

        # Render the live _registry and check it has the expected values
        from app.metrics import render_prometheus_metrics

        metrics = render_prometheus_metrics().decode("utf-8")
        self.assertIn("k8s_ai_sre_investigation_latency_seconds_count 1", metrics)
        self.assertIn("k8s_ai_sre_investigation_latency_seconds_sum 2.0", metrics)

    def test_records_proposal_approval_latency_and_outcomes(self) -> None:
        observe_event("action_proposed", {"ts": "2026-01-01T00:00:00+00:00", "action_id": "abc12345"})
        observe_event("action_approved", {"ts": "2026-01-01T00:00:05+00:00", "action_id": "abc12345"})
        observe_event("action_failed", {"ts": "2026-01-01T00:00:06+00:00", "action_id": "deadbeef"})

        from app.metrics import render_prometheus_metrics

        metrics = render_prometheus_metrics().decode("utf-8")
        self.assertIn("k8s_ai_sre_action_proposals_total 1", metrics)
        self.assertIn('k8s_ai_sre_action_execution_outcomes_total{status="approved"} 1', metrics)
        self.assertIn('k8s_ai_sre_action_execution_outcomes_total{status="failed"} 1', metrics)
        self.assertIn("k8s_ai_sre_approval_latency_seconds_count 1", metrics)
        self.assertIn("k8s_ai_sre_approval_latency_seconds_sum 5.0", metrics)
