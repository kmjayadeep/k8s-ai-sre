import tempfile
import unittest
from asyncio import run
from pathlib import Path
from unittest.mock import AsyncMock, patch

import app.stores.actions as action_store
import app.stores.incidents as incident_store
from app.http import AlertmanagerWebhook, InvestigateRequest, alertmanager_webhook, investigate, read_incident


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

    def test_investigate_creates_incident_with_notification_status(self) -> None:
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
                body = run(investigate(InvestigateRequest(kind="deployment", namespace="ai-sre-demo", name="bad-deploy")))

        self.assertEqual("Telegram notification sent.", body["notification_status"])
        stored = run(read_incident(body["incident_id"]))
        self.assertEqual(["abc12345"], stored["action_ids"])
        self.assertEqual("Telegram notification sent.", stored["notification_status"])

    def test_alertmanager_webhook_resolves_target_and_persists_source(self) -> None:
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
                body = run(
                    alertmanager_webhook(
                        AlertmanagerWebhook(commonLabels={"namespace": "ai-sre-demo", "deployment": "bad-deploy"}, alerts=[])
                    )
                )

        self.assertEqual("alertmanager", body["source"])
        stored = run(read_incident(body["incident_id"]))
        self.assertEqual("alertmanager", stored["source"])

    def test_read_incident_normalizes_legacy_payload_shape(self) -> None:
        incident = incident_store.create_incident(
            {
                "kind": "pod",
                "namespace": "ai-sre-demo",
                "name": "crashy",
            }
        )

        stored = run(read_incident(incident["incident_id"]))

        self.assertEqual("manual", stored["source"])
        self.assertEqual("", stored["answer"])
        self.assertEqual("", stored["evidence"])
        self.assertEqual([], stored["action_ids"])
        self.assertEqual([], stored["proposed_actions"])
        self.assertEqual("notification_not_attempted", stored["notification_status"])
