import unittest

import app.stores.actions as action_store
import app.stores.incidents as incident_store
from app.stores.backend import KeyValueStore


class InMemoryStore(KeyValueStore):
    def __init__(self) -> None:
        self.records: dict[str, dict[str, object]] = {}

    def load(self) -> dict[str, dict[str, object]]:
        return dict(self.records)

    def save(self, records: dict[str, dict[str, object]]) -> None:
        self.records = dict(records)


class StoreAbstractionTests(unittest.TestCase):
    def test_action_store_backend_can_be_swapped(self) -> None:
        backend = InMemoryStore()
        original = action_store._action_store
        self.addCleanup(action_store.set_action_store, original)
        action_store.set_action_store(backend)

        created = action_store.create_action("delete-pod", "ai-sre-demo", "crashy")
        fetched = action_store.get_action(str(created["id"]))

        self.assertIsNotNone(fetched)
        self.assertEqual(created["id"], fetched["id"])

    def test_incident_store_backend_can_be_swapped(self) -> None:
        backend = InMemoryStore()
        original = incident_store._incident_store
        self.addCleanup(incident_store.set_incident_store, original)
        incident_store.set_incident_store(backend)

        created = incident_store.create_incident({"kind": "pod", "namespace": "ai-sre-demo", "name": "crashy"})
        fetched = incident_store.get_incident(str(created["incident_id"]))

        self.assertIsNotNone(fetched)
        self.assertEqual(created["incident_id"], fetched["incident_id"])
