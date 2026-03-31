import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app.stores.incidents as incident_store


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
        self.assertEqual("pending", stored["actions"][0]["status"])

    def test_update_incident_persists_action_summaries(self) -> None:
        incident = incident_store.create_incident({"kind": "pod", "namespace": "ai-sre-demo", "name": "crashy"})

        incident_store.update_incident(
            incident["incident_id"],
            {
                "actions": [
                    {
                        "action_id": "abc12345",
                        "action_type": "delete-pod",
                        "namespace": "ai-sre-demo",
                        "name": "crashy",
                        "status": "approved",
                    }
                ]
            },
        )

        stored = incident_store.get_incident(incident["incident_id"])
        self.assertEqual("approved", stored["actions"][0]["status"])

    def test_update_incident_persists_notification_status(self) -> None:
        incident = incident_store.create_incident({"kind": "pod", "namespace": "ai-sre-demo", "name": "crashy"})

        incident_store.update_incident(incident["incident_id"], {"notification_status": "Telegram notification sent."})

        stored = incident_store.get_incident(incident["incident_id"])
        self.assertEqual("Telegram notification sent.", stored["notification_status"])
