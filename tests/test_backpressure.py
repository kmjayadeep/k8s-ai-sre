import unittest

from app.backpressure import (
    enqueue_investigation,
    get_queue_depth,
    get_queue_status,
    get_active_investigation_count,
    record_processing_heartbeat,
    MAX_QUEUE_SIZE,
    _reset_queue,
)


class BackpressureTests(unittest.TestCase):
    """Tests for investigation queueing and backpressure."""

    def setUp(self) -> None:
        # Reset queue before each test to ensure clean state
        _reset_queue()

    def test_enqueue_investigation_returns_queued_on_success(self) -> None:
        success, reason = enqueue_investigation("deployment", "ai-sre-demo", "test-queued-success")
        self.assertTrue(success)
        self.assertEqual("queued", reason)

    def test_enqueue_investigation_returns_queue_full_when_full(self) -> None:
        # Fill the queue with unique names
        for i in range(MAX_QUEUE_SIZE):
            enqueue_investigation("deployment", "ai-sre-demo", f"test-deploy-{i}")
        # This should fail due to queue being full
        success, reason = enqueue_investigation("deployment", "ai-sre-demo", "test-deploy-overflow")
        self.assertFalse(success)
        self.assertEqual("queue_full", reason)

    def test_get_queue_depth_increments_on_enqueue(self) -> None:
        initial_depth = get_queue_depth()
        enqueue_investigation("pod", "ai-sre-demo", "test-pod")
        self.assertEqual(initial_depth + 1, get_queue_depth())

    def test_get_queue_status_returns_correct_structure(self) -> None:
        status = get_queue_status()
        self.assertIn("queue_depth", status)
        self.assertIn("max_queue_size", status)
        self.assertIn("active_investigations", status)
        self.assertIn("max_concurrent_investigations", status)
        self.assertIn("queue_utilization", status)
        self.assertIn("last_processing_heartbeat_at", status)
        self.assertIn("last_processing_heartbeat_age_seconds", status)
        self.assertIn("last_processing_target", status)
        self.assertIn("last_processing_state", status)
        self.assertEqual(MAX_QUEUE_SIZE, status["max_queue_size"])
        self.assertIsNone(status["last_processing_heartbeat_at"])
        self.assertIsNone(status["last_processing_heartbeat_age_seconds"])
        self.assertIsNone(status["last_processing_target"])
        self.assertIsNone(status["last_processing_state"])

    def test_get_active_investigation_count_returns_zero_initially(self) -> None:
        count = get_active_investigation_count()
        self.assertIsInstance(count, int)
        self.assertGreaterEqual(count, 0)

    def test_queue_status_includes_last_processing_heartbeat_details(self) -> None:
        record_processing_heartbeat("deployment", "ai-sre-demo", "api", state="started")

        status = get_queue_status()

        self.assertEqual("deployment/ai-sre-demo/api", status["last_processing_target"])
        self.assertEqual("started", status["last_processing_state"])
        self.assertIsNotNone(status["last_processing_heartbeat_at"])
        self.assertIsInstance(status["last_processing_heartbeat_age_seconds"], float)
        self.assertGreaterEqual(status["last_processing_heartbeat_age_seconds"], 0.0)
