import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app.actions as action_service
import app.stores.actions as action_store
import app.stores.incidents as incident_store
import app.telegram as telegram


class TelegramIntegrationTests(unittest.TestCase):
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

    def test_incident_command_includes_action_ids(self) -> None:
        action = action_service.propose_action("rollout-restart", "ai-sre-demo", "bad-deploy")
        incident = incident_store.create_incident(
            {
                "kind": "deployment",
                "namespace": "ai-sre-demo",
                "name": "bad-deploy",
                "answer": "Summary: image pull failure",
                "proposed_actions": [{"action_id": action["id"], "action_type": "rollout-restart", "namespace": "ai-sre-demo", "name": "bad-deploy"}],
                "action_ids": [action["id"]],
            }
        )
        action_service.attach_actions_to_incident([action["id"]], incident["incident_id"])

        reply = telegram._handle_command(f"/incident {incident['incident_id']}")

        self.assertIn("Actions:", reply)
        self.assertIn(action["id"], reply)
        self.assertIn("[pending]", reply)

    def test_approve_command_executes_pending_action(self) -> None:
        action = action_service.propose_action("delete-pod", "ai-sre-demo", "crashy")
        action_service.attach_actions_to_incident([action["id"]], "incident-123")

        with patch("app.actions.delete_pod", return_value='pod "crashy" deleted'):
            reply = telegram._handle_command(f"/approve {action['id']}")

        self.assertIn("Incident incident-123", reply)
        self.assertIn('pod "crashy" deleted', reply)
        stored = action_store.get_action(action["id"])
        self.assertEqual("approved", stored["status"])

    def test_status_command_shows_live_action_statuses_for_incident(self) -> None:
        action = action_service.propose_action("delete-pod", "ai-sre-demo", "crashy")
        incident = incident_store.create_incident(
            {
                "kind": "pod",
                "namespace": "ai-sre-demo",
                "name": "crashy",
                "answer": "Summary: CrashLoopBackOff",
                "proposed_actions": [{"action_id": action["id"], "action_type": "delete-pod", "namespace": "ai-sre-demo", "name": "crashy"}],
                "action_ids": [action["id"]],
            }
        )
        action_service.attach_actions_to_incident([action["id"]], incident["incident_id"])
        action_store.update_action_status(action["id"], "rejected")

        reply = telegram._handle_command(f"/status {incident['incident_id']}")

        self.assertIn(action["id"], reply)
        self.assertIn("[rejected]", reply)

    def test_incident_command_falls_back_to_incident_actions_when_store_is_empty(self) -> None:
        incident = incident_store.create_incident(
            {
                "kind": "deployment",
                "namespace": "ai-sre-demo",
                "name": "bad-deploy",
                "answer": "Summary: image pull failure",
                "actions": [
                    {
                        "action_id": "abc12345",
                        "action_type": "rollout-restart",
                        "namespace": "ai-sre-demo",
                        "name": "bad-deploy",
                        "status": "approved",
                    }
                ],
                "proposed_actions": [],
            }
        )

        reply = telegram._handle_command(f"/incident {incident['incident_id']}")

        self.assertIn("abc12345", reply)
        self.assertIn("[approved]", reply)
