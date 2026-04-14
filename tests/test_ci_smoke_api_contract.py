import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

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
    "brief",
    "action_ids",
    "proposed_actions",
    "notification_status",
}


class ApiSmokeContractTests(unittest.TestCase):
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

    def test_investigate_endpoint_contract_smoke(self) -> None:
        result = {
            "kind": "deployment",
            "namespace": "ai-sre-demo",
            "name": "bad-deploy",
            "answer": "Summary: image pull failure",
            "proposed_actions": [],
            "action_ids": [],
        }
        mock_investigate = AsyncMock(return_value=result)
        with patch("app.http.investigate_target", new=mock_investigate):
            with patch("app.http.send_telegram_notification", return_value="Telegram notification sent."):
                response = TestClient(app).post(
                    "/investigate",
                    json={"kind": "deployment", "namespace": "ai-sre-demo", "name": "bad-deploy"},
                )

        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertEqual(REQUIRED_INCIDENT_KEYS, set(body.keys()))
        self.assertTrue(isinstance(body["incident_id"], str) and body["incident_id"])
        self.assertEqual("manual", body["source"])
        self.assertIsInstance(body["action_ids"], list)
        mock_investigate.assert_awaited_once_with("deployment", "ai-sre-demo", "bad-deploy", emit_progress=False)

    def test_alertmanager_endpoint_contract_smoke(self) -> None:
        result = {
            "kind": "deployment",
            "namespace": "ai-sre-demo",
            "name": "bad-deploy",
            "answer": "Summary: image pull failure",
            "proposed_actions": [],
            "action_ids": [],
        }
        mock_investigate = AsyncMock(return_value=result)
        with patch("app.http.investigate_target", new=mock_investigate):
            with patch("app.http.send_telegram_notification", return_value="Telegram notification sent."):
                response = TestClient(app).post(
                    "/webhooks/alertmanager",
                    json={"commonLabels": {"namespace": "ai-sre-demo", "deployment": "bad-deploy"}, "alerts": []},
                )

        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertEqual(REQUIRED_INCIDENT_KEYS, set(body.keys()))
        self.assertTrue(isinstance(body["incident_id"], str) and body["incident_id"])
        self.assertEqual("alertmanager", body["source"])
        self.assertIsInstance(body["action_ids"], list)
        mock_investigate.assert_awaited_once_with("deployment", "ai-sre-demo", "bad-deploy", emit_progress=False)
