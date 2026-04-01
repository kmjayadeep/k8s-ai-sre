import tempfile
import unittest
from asyncio import run
from pathlib import Path
from unittest.mock import AsyncMock, patch

import app.actions as action_service
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
    def test_alertmanager_to_approval_executes_linked_action(self) -> None:
        action = action_service.propose_action("delete-pod", "ai-sre-demo", "crashy")
        result = {
            "kind": "pod",
            "namespace": "ai-sre-demo",
            "name": "crashy",
            "answer": "Summary: CrashLoopBackOff from bad sidecar config",
            "proposed_actions": [action_service.action_metadata(action)],
            "action_ids": [action["id"]],
        }
        with patch("app.http.investigate_target", new=AsyncMock(return_value=result)):
            with patch("app.http.send_telegram_notification", return_value="Telegram notification sent."):
                body = run(
                    alertmanager_webhook(
                        AlertmanagerWebhook(commonLabels={"namespace": "ai-sre-demo", "pod": "crashy"}, alerts=[])
                    )
                )

        stored_incident = run(read_incident(body["incident_id"]))
        self.assertEqual([action["id"]], stored_incident["action_ids"])
        self.assertEqual("alertmanager", stored_incident["source"])

        stored_action = action_store.get_action(action["id"])
        self.assertEqual(body["incident_id"], stored_action["incident_id"])
        self.assertEqual("pending", stored_action["status"])

        with patch("app.actions.delete_pod", return_value='pod "crashy" deleted'):
            approval_reply = action_service.approve_action(action["id"])

        self.assertIn(f"Incident {body['incident_id']}", approval_reply)
        self.assertIn('pod "crashy" deleted', approval_reply)
        self.assertEqual("approved", action_store.get_action(action["id"])["status"])

    def test_read_incident_normalizes_legacy_payload_shape(self) -> None:
        incident = incident_store.create_incident(
            {
                "kind": "pod",
                "namespace": "ai-sre-demo",
                "name": "crashy",
                "proposed_actions": [{"action_id": "f314980d", "action_type": "delete-pod"}],
            }
        )

        stored = run(read_incident(incident["incident_id"]))
        self.assertEqual("manual", stored["source"])
        self.assertEqual(["f314980d"], stored["action_ids"])
        self.assertEqual("/approve f314980d", stored["proposed_actions"][0]["approve_command"])
