import unittest

from app.metrics import observe_event, render_prometheus_metrics, reset_metrics_for_tests


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

        metrics = render_prometheus_metrics()
        self.assertIn("k8s_ai_sre_investigation_latency_seconds_count 1", metrics)
        self.assertIn("k8s_ai_sre_investigation_latency_seconds_sum 2.0", metrics)

    def test_records_proposal_approval_latency_and_outcomes(self) -> None:
        observe_event("action_proposed", {"ts": "2026-01-01T00:00:00+00:00", "action_id": "abc12345"})
        observe_event("action_approved", {"ts": "2026-01-01T00:00:05+00:00", "action_id": "abc12345"})
        observe_event("action_failed", {"ts": "2026-01-01T00:00:06+00:00", "action_id": "deadbeef"})

        metrics = render_prometheus_metrics()
        self.assertIn("k8s_ai_sre_action_proposals_total 1", metrics)
        self.assertIn('k8s_ai_sre_action_execution_outcomes_total{status="approved"} 1', metrics)
        self.assertIn('k8s_ai_sre_action_execution_outcomes_total{status="failed"} 1', metrics)
        self.assertIn("k8s_ai_sre_approval_latency_seconds_count 1", metrics)
        self.assertIn("k8s_ai_sre_approval_latency_seconds_sum 5.0", metrics)
