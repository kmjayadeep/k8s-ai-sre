import json
from pathlib import Path
from uuid import uuid4


INCIDENT_STORE_PATH = Path("/tmp/k8s-ai-sre-incidents.json")


def _load_incidents() -> dict[str, dict[str, object]]:
    if not INCIDENT_STORE_PATH.exists():
        return {}
    return json.loads(INCIDENT_STORE_PATH.read_text(encoding="utf-8"))


def _save_incidents(incidents: dict[str, dict[str, object]]) -> None:
    INCIDENT_STORE_PATH.write_text(json.dumps(incidents, indent=2, sort_keys=True), encoding="utf-8")


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
