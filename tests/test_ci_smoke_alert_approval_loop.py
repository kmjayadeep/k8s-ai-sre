import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import app.actions as action_service
import app.stores.actions as action_store
import app.stores.incidents as incident_store
from fastapi.testclient import TestClient

from app.http import app
from app.metrics import reset_metrics_for_tests


REQUIRED_INCIDENT_KEYS = {
    "incident_id",
    "kind",
    "namespace",
    "name",
    "answer",
    "evidence",
    "source",
    "action_ids",
    "proposed_actions",
    "notification_status",
}

REQUIRED_DECISION_KEYS = {"action_id", "status", "message"}


class AlertApprovalSmokeTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_metrics_for_tests()
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.incident_path = Path(self.tempdir.name) / "incidents.json"
        self.action_path = Path(self.tempdir.name) / "actions.json"
        self.incident_patch = patch.object(incident_store, "INCIDENT_STORE_PATH", self.incident_path)
        self.action_patch = patch.object(action_store, "ACTION_STORE_PATH", self.action_path)
        self.incident_patch.start()
        self.action_patch.start()
        self.addCleanup(self.incident_patch.stop)
        self.addCleanup(self.action_patch.stop)
        self.client = TestClient(app)

    def _create_incident_from_webhook(self) -> tuple[str, str]:
        action = action_service.propose_action("delete-pod", "ai-sre-demo", "crashy")
        result = {
            "kind": "pod",
            "namespace": "ai-sre-demo",
            "name": "crashy",
            "answer": "Summary: CrashLoopBackOff from bad sidecar config",
            "proposed_actions": [action_service.action_metadata(action)],
            "action_ids": [action["id"]],
        }
        with patch("app.http.investigate_target", new=AsyncMock(return_value=result)) as investigate_mock:
            with patch("app.http.send_telegram_notification", return_value="Telegram notification sent."):
                response = self.client.post(
                    "/webhooks/alertmanager",
                    json={"commonLabels": {"namespace": "ai-sre-demo", "pod": "crashy"}, "alerts": []},
                )

        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertEqual(REQUIRED_INCIDENT_KEYS, set(body.keys()))
        self.assertEqual("alertmanager", body["source"])
        self.assertEqual([action["id"]], body["action_ids"])
        investigate_mock.assert_awaited_once_with("pod", "ai-sre-demo", "crashy", emit_progress=False)

        incident_id = body["incident_id"]
        stored_incident = incident_store.get_incident(incident_id)
        self.assertIsNotNone(stored_incident)
        self.assertEqual("alertmanager", stored_incident["source"])
        self.assertEqual([action["id"]], stored_incident["action_ids"])
        self.assertEqual(incident_id, action_store.get_action(action["id"])["incident_id"])
        self.assertEqual("pending", action_store.get_action(action["id"])["status"])
        return incident_id, action["id"]

    def test_webhook_to_token_guarded_approve_executes_action(self) -> None:
        _, action_id = self._create_incident_from_webhook()

        with patch.dict(os.environ, {"OPERATOR_API_TOKEN": "test-token"}, clear=False):
            with patch("app.actions.delete_pod", return_value='pod "crashy" deleted'):
                decision = self.client.post(
                    f"/actions/{action_id}/approve",
                    headers={"Authorization": "Bearer test-token", "X-Operator-Id": "ci-smoke"},
                )

        self.assertEqual(200, decision.status_code)
        body = decision.json()
        self.assertEqual(REQUIRED_DECISION_KEYS, set(body.keys()))
        self.assertEqual(action_id, body["action_id"])
        self.assertEqual("approved", body["status"])
        self.assertIn('pod "crashy" deleted', body["message"])
        self.assertEqual("approved", action_store.get_action(action_id)["status"])
        self.assertEqual("ci-smoke", action_store.get_action(action_id)["approved_by"])

    def test_webhook_to_token_guarded_reject_updates_state(self) -> None:
        _, action_id = self._create_incident_from_webhook()

        with patch.dict(os.environ, {"OPERATOR_API_TOKEN": "test-token"}, clear=False):
            decision = self.client.post(
                f"/actions/{action_id}/reject",
                headers={"Authorization": "Bearer test-token", "X-Operator-Id": "ci-smoke"},
            )

        self.assertEqual(200, decision.status_code)
        body = decision.json()
        self.assertEqual(REQUIRED_DECISION_KEYS, set(body.keys()))
        self.assertEqual(action_id, body["action_id"])
        self.assertEqual("rejected", body["status"])
        self.assertIn(f"Rejected action {action_id}.", body["message"])
        self.assertEqual("rejected", action_store.get_action(action_id)["status"])
        self.assertEqual("ci-smoke", action_store.get_action(action_id)["approved_by"])

    def test_approve_rejects_invalid_token(self) -> None:
        _, action_id = self._create_incident_from_webhook()

        with patch.dict(os.environ, {"OPERATOR_API_TOKEN": "test-token"}, clear=False):
            decision = self.client.post(
                f"/actions/{action_id}/approve",
                headers={"Authorization": "Bearer wrong", "X-Operator-Id": "ci-smoke"},
            )

        self.assertEqual(403, decision.status_code)
        self.assertEqual({"detail": {"code": "operator_token_invalid", "message": "invalid operator token"}}, decision.json())
