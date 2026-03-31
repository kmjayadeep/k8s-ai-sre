import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import app.actions as action_service
import app.stores.actions as action_store
import app.stores.incidents as incident_store


class ActionServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.store_path = Path(self.tempdir.name) / "actions.json"
        self.incident_path = Path(self.tempdir.name) / "incidents.json"
        self.path_patch = patch.object(action_store, "ACTION_STORE_PATH", self.store_path)
        self.incident_patch = patch.object(incident_store, "INCIDENT_STORE_PATH", self.incident_path)
        self.path_patch.start()
        self.incident_patch.start()
        self.addCleanup(self.path_patch.stop)
        self.addCleanup(self.incident_patch.stop)

    def test_proposal_capture_records_action_metadata(self) -> None:
        token = action_service.begin_proposal_capture()
        action = action_service.propose_action("delete-pod", "ai-sre-demo", "crashy")
        proposals = action_service.finish_proposal_capture(token)

        self.assertEqual([action["id"]], [item["action_id"] for item in proposals])
        self.assertEqual("delete-pod", proposals[0]["action_type"])

    def test_attach_actions_to_incident_updates_store(self) -> None:
        action = action_service.propose_action("rollout-restart", "ai-sre-demo", "bad-deploy")
        incident = incident_store.create_incident({"kind": "deployment", "namespace": "ai-sre-demo", "name": "bad-deploy"})

        action_service.attach_actions_to_incident([action["id"]], incident["incident_id"])

        stored = action_store.get_action(action["id"])
        self.assertEqual(incident["incident_id"], stored["incident_id"])
        synced_incident = incident_store.get_incident(incident["incident_id"])
        self.assertEqual([action["id"]], [item["action_id"] for item in synced_incident["actions"]])

    def test_approve_action_marks_failed_when_execution_fails(self) -> None:
        action = action_service.propose_action("delete-pod", "ai-sre-demo", "crashy")
        incident = incident_store.create_incident({"kind": "pod", "namespace": "ai-sre-demo", "name": "crashy"})
        action_service.attach_actions_to_incident([action["id"]], incident["incident_id"])

        with patch("app.actions.delete_pod", return_value="Failed to delete pod crashy in namespace ai-sre-demo: boom"):
            result = action_service.approve_action(action["id"])

        self.assertIn("Failed to delete pod", result)
        stored = action_store.get_action(action["id"])
        self.assertEqual("failed", stored["status"])
        synced_incident = incident_store.get_incident(incident["incident_id"])
        self.assertEqual("failed", synced_incident["actions"][0]["status"])

    def test_approve_action_marks_approved_when_execution_succeeds(self) -> None:
        action = action_service.propose_action("delete-pod", "ai-sre-demo", "crashy")
        incident = incident_store.create_incident({"kind": "pod", "namespace": "ai-sre-demo", "name": "crashy"})
        action_service.attach_actions_to_incident([action["id"]], incident["incident_id"])

        with patch("app.actions.delete_pod", return_value='pod "crashy" deleted'):
            result = action_service.approve_action(action["id"])

        self.assertIn('pod "crashy" deleted', result)
        stored = action_store.get_action(action["id"])
        self.assertEqual("approved", stored["status"])
        synced_incident = incident_store.get_incident(incident["incident_id"])
        self.assertEqual("approved", synced_incident["actions"][0]["status"])

    def test_reject_action_updates_incident_action_status(self) -> None:
        action = action_service.propose_action("delete-pod", "ai-sre-demo", "crashy")
        incident = incident_store.create_incident({"kind": "pod", "namespace": "ai-sre-demo", "name": "crashy"})
        action_service.attach_actions_to_incident([action["id"]], incident["incident_id"])

        result = action_service.reject_action(action["id"])

        self.assertIn("Rejected action", result)
        synced_incident = incident_store.get_incident(incident["incident_id"])
        self.assertEqual("rejected", synced_incident["actions"][0]["status"])

    def test_reject_action_does_not_override_approved_status(self) -> None:
        action = action_service.propose_action("delete-pod", "ai-sre-demo", "crashy")
        incident = incident_store.create_incident({"kind": "pod", "namespace": "ai-sre-demo", "name": "crashy"})
        action_service.attach_actions_to_incident([action["id"]], incident["incident_id"])
        with patch("app.actions.delete_pod", return_value='pod "crashy" deleted'):
            action_service.approve_action(action["id"])

        result = action_service.reject_action(action["id"])

        self.assertIn("already approved", result)
        stored = action_store.get_action(action["id"])
        self.assertEqual("approved", stored["status"])
        synced_incident = incident_store.get_incident(incident["incident_id"])
        self.assertEqual("approved", synced_incident["actions"][0]["status"])

    def test_reject_action_marks_expired_when_action_expired(self) -> None:
        action = action_service.propose_action("delete-pod", "ai-sre-demo", "crashy")
        incident = incident_store.create_incident({"kind": "pod", "namespace": "ai-sre-demo", "name": "crashy"})
        action_service.attach_actions_to_incident([action["id"]], incident["incident_id"])
        action_store.update_action(action["id"], {"expires_at": (datetime.now(UTC) - timedelta(minutes=1)).isoformat()})

        result = action_service.reject_action(action["id"])

        self.assertIn("has expired", result)
        stored = action_store.get_action(action["id"])
        self.assertEqual("expired", stored["status"])
        synced_incident = incident_store.get_incident(incident["incident_id"])
        self.assertEqual("expired", synced_incident["actions"][0]["status"])
