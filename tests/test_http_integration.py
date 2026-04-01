import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import app.stores.actions as action_store
import app.stores.incidents as incident_store
from app.http import app
from fastapi.testclient import TestClient


class HttpIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
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

    def _make_client(self) -> TestClient:
        return TestClient(app)

    def test_healthz_endpoint_returns_typed_payload(self) -> None:
        with self._make_client() as client:
            response = client.get("/healthz")

        self.assertEqual(200, response.status_code)
        self.assertEqual({"status": "ok"}, response.json())

    def test_investigate_endpoint_creates_incident_with_notification_status(self) -> None:
        result = {
            "kind": "deployment",
            "namespace": "ai-sre-demo",
            "name": "bad-deploy",
            "answer": "Summary: image pull failure",
            "proposed_actions": [{"action_id": "abc12345", "action_type": "rollout-restart", "namespace": "ai-sre-demo", "name": "bad-deploy"}],
            "action_ids": ["abc12345"],
        }
        with patch("app.http.investigate_target", new=AsyncMock(return_value=result)):
            with patch("app.http.send_telegram_notification", return_value="Telegram notification sent."):
                with self._make_client() as client:
                    response = client.post(
                        "/investigate",
                        json={"kind": "deployment", "namespace": "ai-sre-demo", "name": "bad-deploy"},
                    )

        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertEqual("Telegram notification sent.", body["notification_status"])
        with self._make_client() as client:
            stored_response = client.get(f"/incidents/{body['incident_id']}")
        self.assertEqual(200, stored_response.status_code)
        stored = stored_response.json()
        self.assertEqual(["abc12345"], stored["action_ids"])
        self.assertEqual("Telegram notification sent.", stored["notification_status"])

    def test_alertmanager_webhook_endpoint_resolves_target_and_persists_source(self) -> None:
        result = {
            "kind": "deployment",
            "namespace": "ai-sre-demo",
            "name": "bad-deploy",
            "answer": "Summary: image pull failure",
            "proposed_actions": [],
            "action_ids": [],
        }
        with patch("app.http.investigate_target", new=AsyncMock(return_value=result)):
            with patch("app.http.send_telegram_notification", return_value="Telegram notification sent."):
                with self._make_client() as client:
                    response = client.post(
                        "/webhooks/alertmanager",
                        json={"commonLabels": {"namespace": "ai-sre-demo", "deployment": "bad-deploy"}, "alerts": []},
                    )

        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertEqual("alertmanager", body["source"])
        with self._make_client() as client:
            stored_response = client.get(f"/incidents/{body['incident_id']}")
        self.assertEqual(200, stored_response.status_code)
        stored = stored_response.json()
        self.assertEqual("alertmanager", stored["source"])

    def test_read_incident_endpoint_normalizes_legacy_payload_shape(self) -> None:
        incident = incident_store.create_incident(
            {
                "kind": "pod",
                "namespace": "ai-sre-demo",
                "name": "crashy",
                "proposed_actions": [{"action_id": "f314980d", "action_type": "delete-pod"}],
            }
        )

        with self._make_client() as client:
            response = client.get(f"/incidents/{incident['incident_id']}")

        self.assertEqual(200, response.status_code)
        stored = response.json()
        self.assertEqual("manual", stored["source"])
        self.assertEqual(["f314980d"], stored["action_ids"])
        self.assertEqual("/approve f314980d", stored["proposed_actions"][0]["approve_command"])
