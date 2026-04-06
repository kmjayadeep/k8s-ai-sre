import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import app.actions as action_service
import app.stores.actions as action_store
from app.stores.backend import SqliteKeyValueStore


class ActionServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.store_path = Path(self.tempdir.name) / "actions.json"
        self.path_patch = patch.object(action_store, "ACTION_STORE_PATH", self.store_path)
        self.path_patch.start()
        self.addCleanup(self.path_patch.stop)

    def test_proposal_capture_records_action_metadata(self) -> None:
        token = action_service.begin_proposal_capture()
        action = action_service.propose_action("delete-pod", "ai-sre-demo", "crashy")
        proposals = action_service.finish_proposal_capture(token)

        self.assertEqual([action["id"]], [item["action_id"] for item in proposals])
        self.assertEqual("delete-pod", proposals[0]["action_type"])

    def test_attach_actions_to_incident_updates_store(self) -> None:
        action = action_service.propose_action("rollout-restart", "ai-sre-demo", "bad-deploy")

        action_service.attach_actions_to_incident([action["id"]], "incident-123")

        stored = action_store.get_action(action["id"])
        self.assertEqual("incident-123", stored["incident_id"])

    def test_approve_action_marks_failed_when_execution_fails(self) -> None:
        action = action_service.propose_action("delete-pod", "ai-sre-demo", "crashy")

        with patch("app.actions.delete_pod", return_value="Failed to delete pod crashy in namespace ai-sre-demo: boom"):
            result = action_service.approve_action(action["id"])

        self.assertIn("Failed to delete pod", result)
        stored = action_store.get_action(action["id"])
        self.assertEqual("failed", stored["status"])

    def test_approve_action_marks_approved_when_execution_succeeds(self) -> None:
        action = action_service.propose_action("delete-pod", "ai-sre-demo", "crashy")

        with patch("app.actions.delete_pod", return_value='pod "crashy" deleted'):
            result = action_service.approve_action(action["id"], approver_id="operator-1", approval_source="http_api")

        self.assertIn('pod "crashy" deleted', result)
        stored = action_store.get_action(action["id"])
        self.assertEqual("approved", stored["status"])
        self.assertEqual("operator-1", stored["approved_by"])
        self.assertEqual("http_api", stored["approval_source"])
        self.assertIn("action_type", stored["executed_action"])
        self.assertIn('pod "crashy" deleted', stored["execution_result"])
        self.assertIn("execution_finished_at", stored)

    def test_approve_action_fails_closed_when_execution_raises(self) -> None:
        action = action_service.propose_action("delete-pod", "ai-sre-demo", "crashy")

        with patch("app.actions.delete_pod", side_effect=RuntimeError("kaboom")):
            result = action_service.approve_action(action["id"])

        self.assertIn(f"Failed to execute action {action['id']}: kaboom", result)
        stored = action_store.get_action(action["id"])
        self.assertEqual("failed", stored["status"])

    def test_approve_action_is_retry_safe_after_success(self) -> None:
        action = action_service.propose_action("delete-pod", "ai-sre-demo", "crashy")

        with patch("app.actions.delete_pod", return_value='pod "crashy" deleted') as delete_pod:
            first_result = action_service.approve_action(action["id"])
            second_result = action_service.approve_action(action["id"])

        self.assertIn('pod "crashy" deleted', first_result)
        self.assertIn(f"Action {action['id']} is already approved.", second_result)
        delete_pod.assert_called_once()

    def test_approve_action_is_retry_safe_after_failure(self) -> None:
        action = action_service.propose_action("delete-pod", "ai-sre-demo", "crashy")

        with patch("app.actions.delete_pod", return_value="Failed to delete pod crashy in namespace ai-sre-demo: boom") as delete_pod:
            first_result = action_service.approve_action(action["id"])
            second_result = action_service.approve_action(action["id"])

        self.assertIn("Failed to delete pod", first_result)
        self.assertIn(f"Action {action['id']} is already failed.", second_result)
        delete_pod.assert_called_once()

    def test_reject_action_does_not_override_non_pending_state(self) -> None:
        action = action_service.propose_action("delete-pod", "ai-sre-demo", "crashy")
        action_store.update_action_status(action["id"], "approved")

        result = action_service.reject_action(action["id"])

        self.assertIn(f"Action {action['id']} is already approved.", result)
        stored = action_store.get_action(action["id"])
        self.assertEqual("approved", stored["status"])

    def test_reject_action_writes_audit_fields(self) -> None:
        action = action_service.propose_action("delete-pod", "ai-sre-demo", "crashy")

        result = action_service.reject_action(action["id"], approver_id="telegram:alice", approval_source="telegram")

        self.assertIn(f"Rejected action {action['id']}.", result)
        stored = action_store.get_action(action["id"])
        self.assertEqual("rejected", stored["status"])
        self.assertEqual("telegram:alice", stored["approved_by"])
        self.assertEqual("telegram", stored["approval_source"])
        self.assertIn("Rejected by operator", stored["execution_result"])
        self.assertIn("approval_decided_at", stored)
        self.assertIn("execution_finished_at", stored)

    def test_reject_action_marks_expired_when_action_is_expired(self) -> None:
        action = action_service.propose_action("delete-pod", "ai-sre-demo", "crashy")
        action_store.update_action(
            action["id"],
            {"expires_at": (datetime.now(UTC) - timedelta(minutes=1)).isoformat()},
        )

        result = action_service.reject_action(action["id"])

        self.assertIn(f"Action {action['id']} has expired.", result)
        stored = action_store.get_action(action["id"])
        self.assertEqual("expired", stored["status"])

    def test_pending_action_survives_store_rebind_restart(self) -> None:
        original_store = action_store._action_store
        self.addCleanup(action_store.set_action_store, original_store)

        first_backend = SqliteKeyValueStore(lambda: self.store_path, table_name="actions")
        action_store.set_action_store(first_backend)
        action = action_service.propose_action("delete-pod", "ai-sre-demo", "crashy")

        restarted_backend = SqliteKeyValueStore(lambda: self.store_path, table_name="actions")
        action_store.set_action_store(restarted_backend)
        reloaded = action_store.get_action(action["id"])

        self.assertIsNotNone(reloaded)
        self.assertEqual("pending", reloaded["status"])

    def test_approved_action_remains_retry_safe_after_store_rebind_restart(self) -> None:
        original_store = action_store._action_store
        self.addCleanup(action_store.set_action_store, original_store)

        first_backend = SqliteKeyValueStore(lambda: self.store_path, table_name="actions")
        action_store.set_action_store(first_backend)
        action = action_service.propose_action("delete-pod", "ai-sre-demo", "crashy")

        with patch("app.actions.delete_pod", return_value='pod "crashy" deleted') as delete_pod:
            first_result = action_service.approve_action(action["id"])
            self.assertIn('pod "crashy" deleted', first_result)
            delete_pod.assert_called_once()

        restarted_backend = SqliteKeyValueStore(lambda: self.store_path, table_name="actions")
        action_store.set_action_store(restarted_backend)
        with patch("app.actions.delete_pod") as delete_pod:
            second_result = action_service.approve_action(action["id"])

        self.assertIn(f"Action {action['id']} is already approved.", second_result)
        delete_pod.assert_not_called()
