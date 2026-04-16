import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app.stores.incidents as incident_store
from app.stores.backend import JsonFileKeyValueStore


class IncidentStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.store_path = Path(self.tempdir.name) / "incidents.json"
        self.path_patch = patch.object(incident_store, "INCIDENT_STORE_PATH", self.store_path)
        self.path_patch.start()
        self.addCleanup(self.path_patch.stop)

    def test_create_incident_persists_proposed_actions(self) -> None:
        incident = incident_store.create_incident(
            {
                "kind": "deployment",
                "namespace": "ai-sre-demo",
                "name": "bad-deploy",
                "answer": "Summary: broken image",
                "action_ids": ["abc12345"],
                "proposed_actions": [{"action_id": "abc12345", "action_type": "rollout-restart"}],
            }
        )

        stored = incident_store.get_incident(incident["incident_id"])
        self.assertEqual(["abc12345"], stored["action_ids"])
        self.assertEqual("rollout-restart", stored["proposed_actions"][0]["action_type"])

    def test_update_incident_persists_notification_status(self) -> None:
        incident = incident_store.create_incident({"kind": "pod", "namespace": "ai-sre-demo", "name": "crashy"})

        incident_store.update_incident(incident["incident_id"], {"notification_status": "Telegram notification sent."})

        stored = incident_store.get_incident(incident["incident_id"])
        self.assertEqual("Telegram notification sent.", stored["notification_status"])

    def test_create_incident_backfills_action_ids_from_proposed_actions(self) -> None:
        incident = incident_store.create_incident(
            {
                "kind": "deployment",
                "namespace": "ai-sre-demo",
                "name": "bad-deploy",
                "proposed_actions": [{"action_id": "abc12345", "action_type": "rollout-restart"}],
            }
        )

        self.assertEqual(["abc12345"], incident["action_ids"])
        self.assertEqual("/approve abc12345", incident["proposed_actions"][0]["approve_command"])

    def test_get_incident_normalizes_legacy_payload_from_disk(self) -> None:
        original_store = incident_store._incident_store
        self.addCleanup(incident_store.set_incident_store, original_store)
        incident_store.set_incident_store(JsonFileKeyValueStore(lambda: self.store_path))
        self.store_path.write_text(
            '{"legacy12345": {"incident_id": "legacy12345", "kind": "pod", "namespace": "default", "name": "x"}}',
            encoding="utf-8",
        )

        stored = incident_store.get_incident("legacy12345")

        self.assertEqual("", stored["answer"])
        self.assertEqual("manual", stored["source"])
        self.assertEqual([], stored["action_ids"])

    def test_find_active_incident_by_target_ignores_resolved_incidents(self) -> None:
        active = incident_store.create_incident({"kind": "pod", "namespace": "ai-sre-demo", "name": "crashy"})
        resolved = incident_store.create_incident(
            {"kind": "pod", "namespace": "ai-sre-demo", "name": "crashy", "lifecycle_status": "resolved"}
        )

        found = incident_store.find_active_incident_by_target("pod", "ai-sre-demo", "crashy")

        self.assertEqual(active["incident_id"], found["incident_id"])
        self.assertNotEqual(resolved["incident_id"], found["incident_id"])

    def test_append_incident_event_updates_history_and_dedup_count(self) -> None:
        incident = incident_store.create_incident({"kind": "pod", "namespace": "ai-sre-demo", "name": "crashy"})

        updated = incident_store.append_incident_event(
            incident["incident_id"],
            event_name="duplicate_investigate_request",
            source="manual",
            details={"reason": "same target retriggered"},
        )

        self.assertEqual(1, updated["dedup_count"])
        self.assertEqual(2, len(updated["event_history"]))
        self.assertEqual("duplicate_investigate_request", updated["event_history"][-1]["event"])
