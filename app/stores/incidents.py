from pathlib import Path
from uuid import uuid4

from app.stores.backend import JsonFileKeyValueStore, KeyValueStore


INCIDENT_STORE_PATH = Path("/tmp/k8s-ai-sre-incidents.json")
_incident_store: KeyValueStore = JsonFileKeyValueStore(lambda: INCIDENT_STORE_PATH)


def _load_incidents() -> dict[str, dict[str, object]]:
    return _incident_store.load()


def _save_incidents(incidents: dict[str, dict[str, object]]) -> None:
    _incident_store.save(incidents)


def set_incident_store(store: KeyValueStore) -> None:
    global _incident_store
    _incident_store = store


def create_incident(payload: dict[str, object]) -> dict[str, object]:
    incidents = _load_incidents()
    incident_id = uuid4().hex[:10]
    record = {"incident_id": incident_id, **payload}
    incidents[incident_id] = record
    _save_incidents(incidents)
    return record


def get_incident(incident_id: str) -> dict[str, object] | None:
    return _load_incidents().get(incident_id)


def update_incident(incident_id: str, updates: dict[str, object]) -> dict[str, object] | None:
    incidents = _load_incidents()
    incident = incidents.get(incident_id)
    if incident is None:
        return None
    incident.update(updates)
    incidents[incident_id] = incident
    _save_incidents(incidents)
    return incident
