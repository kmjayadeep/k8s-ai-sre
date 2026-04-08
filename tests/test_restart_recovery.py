import os
import tempfile
import unittest
from pathlib import Path

from app.stores.actions import (
    create_action,
    get_action,
    set_action_store,
    update_action,
    update_action_status,
)
from app.stores.backend import SqliteKeyValueStore


class RestartRecoveryTests(unittest.TestCase):
    """Tests for restart recovery semantics during in-flight pending/approved actions."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.mkdtemp()
        self._tmpdb = Path(self._tmpdir) / "test-actions.db"
        self._backend = SqliteKeyValueStore(lambda: self._tmpdb, "actions")

    def tearDown(self) -> None:
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_pending_action_survives_restart(self) -> None:
        """Verify pending actions remain in pending state after store reload."""
        set_action_store(self._backend)
        original = create_action("delete-pod", "ai-sre-demo", "crashy")
        action_id = str(original["id"])

        # Simulate restart: create new backend pointing to same DB
        new_backend = SqliteKeyValueStore(lambda: self._tmpdb, "actions")
        set_action_store(new_backend)

        fetched = get_action(action_id)
        self.assertIsNotNone(fetched)
        self.assertEqual(action_id, fetched["id"])
        self.assertEqual("pending", fetched["status"])

    def test_approved_action_survives_restart(self) -> None:
        """Verify approved actions remain in approved state after store reload."""
        set_action_store(self._backend)
        original = create_action("delete-pod", "ai-sre-demo", "crashy")
        action_id = str(original["id"])

        # Approve the action
        update_action(action_id, {"status": "approved", "approved_by": "test-operator"})

        # Simulate restart: create new backend pointing to same DB
        new_backend = SqliteKeyValueStore(lambda: self._tmpdb, "actions")
        set_action_store(new_backend)

        fetched = get_action(action_id)
        self.assertIsNotNone(fetched)
        self.assertEqual(action_id, fetched["id"])
        self.assertEqual("approved", fetched["status"])
        self.assertEqual("test-operator", fetched.get("approved_by"))

    def test_rejected_action_survives_restart(self) -> None:
        """Verify rejected actions remain in rejected state after store reload."""
        set_action_store(self._backend)
        original = create_action("delete-pod", "ai-sre-demo", "crashy")
        action_id = str(original["id"])

        # Reject the action
        update_action(action_id, {"status": "rejected", "approved_by": "test-operator"})

        # Simulate restart: create new backend pointing to same DB
        new_backend = SqliteKeyValueStore(lambda: self._tmpdb, "actions")
        set_action_store(new_backend)

        fetched = get_action(action_id)
        self.assertIsNotNone(fetched)
        self.assertEqual(action_id, fetched["id"])
        self.assertEqual("rejected", fetched["status"])
        self.assertEqual("test-operator", fetched.get("approved_by"))

    def test_executed_action_survives_restart(self) -> None:
        """Verify executed actions remain in executed state after store reload."""
        set_action_store(self._backend)
        original = create_action("rollout-restart", "ai-sre-demo", "bad-deploy")
        action_id = str(original["id"])

        # Execute the action (approved -> executed)
        update_action(action_id, {"status": "approved", "approved_by": "test-operator"})
        update_action(action_id, {"status": "executed"})

        # Simulate restart: create new backend pointing to same DB
        new_backend = SqliteKeyValueStore(lambda: self._tmpdb, "actions")
        set_action_store(new_backend)

        fetched = get_action(action_id)
        self.assertIsNotNone(fetched)
        self.assertEqual(action_id, fetched["id"])
        self.assertEqual("executed", fetched["status"])

    def test_no_duplicate_actions_on_restart(self) -> None:
        """Verify no duplicate actions are created when re-loading from DB."""
        set_action_store(self._backend)

        # Create multiple actions
        actions = [
            create_action("delete-pod", "ai-sre-demo", "pod-1"),
            create_action("rollout-restart", "ai-sre-demo", "deploy-1"),
            create_action("scale", "ai-sre-demo", "deploy-2"),
        ]
        action_ids = [str(a["id"]) for a in actions]

        # Simulate restart: create new backend pointing to same DB
        new_backend = SqliteKeyValueStore(lambda: self._tmpdb, "actions")
        set_action_store(new_backend)

        # Verify all actions still exist and no duplicates
        for action_id in action_ids:
            fetched = get_action(action_id)
            self.assertIsNotNone(fetched)

        # Verify only 3 actions exist
        from app.stores.actions import _action_store
        loaded = _action_store.load()
        self.assertEqual(3, len(loaded))

    def test_failed_action_survives_restart(self) -> None:
        """Verify failed actions remain in failed state after store reload."""
        set_action_store(self._backend)
        original = create_action("delete-pod", "ai-sre-demo", "crashy")
        action_id = str(original["id"])

        # Approve then fail the action
        update_action(action_id, {"status": "approved", "approved_by": "test-operator"})
        update_action(action_id, {"status": "failed", "error_message": "Kubectl execution failed"})

        # Simulate restart: create new backend pointing to same DB
        new_backend = SqliteKeyValueStore(lambda: self._tmpdb, "actions")
        set_action_store(new_backend)

        fetched = get_action(action_id)
        self.assertIsNotNone(fetched)
        self.assertEqual(action_id, fetched["id"])
        self.assertEqual("failed", fetched["status"])
        self.assertEqual("Kubectl execution failed", fetched.get("error_message"))

    def test_action_expired_status_survives_restart(self) -> None:
        """Verify expired actions remain in expired state after store reload."""
        set_action_store(self._backend)
        original = create_action("delete-pod", "ai-sre-demo", "crashy")
        action_id = str(original["id"])

        # Mark as expired
        update_action_status(action_id, "expired")

        # Simulate restart: create new backend pointing to same DB
        new_backend = SqliteKeyValueStore(lambda: self._tmpdb, "actions")
        set_action_store(new_backend)

        fetched = get_action(action_id)
        self.assertIsNotNone(fetched)
        self.assertEqual(action_id, fetched["id"])
        self.assertEqual("expired", fetched["status"])

    def test_multiple_restarts_preserve_state(self) -> None:
        """Verify state is preserved across multiple restart cycles."""
        set_action_store(self._backend)

        action1 = create_action("delete-pod", "ai-sre-demo", "pod-1")
        action2 = create_action("rollout-restart", "ai-sre-demo", "deploy-1")

        # Approve first, reject second
        update_action(str(action1["id"]), {"status": "approved", "approved_by": "op-1"})
        update_action(str(action2["id"]), {"status": "rejected", "approved_by": "op-2"})

        # Simulate multiple restarts
        for _ in range(3):
            new_backend = SqliteKeyValueStore(lambda: self._tmpdb, "actions")
            set_action_store(new_backend)

        # Verify state is correct
        fetched1 = get_action(str(action1["id"]))
        fetched2 = get_action(str(action2["id"]))

        self.assertEqual("approved", fetched1["status"])
        self.assertEqual("rejected", fetched2["status"])
        self.assertEqual("op-1", fetched1.get("approved_by"))
        self.assertEqual("op-2", fetched2.get("approved_by"))
