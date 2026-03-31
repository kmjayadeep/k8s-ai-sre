import json
from pathlib import Path
from uuid import uuid4


INCIDENT_STORE_PATH = Path("/tmp/k8s-ai-sre-incidents.json")


def _initial_actions(payload: dict[str, object]) -> list[dict[str, object]]:
    proposed_actions = payload.get("proposed_actions", [])
    if not isinstance(proposed_actions, list):
        return []

    actions: list[dict[str, object]] = []
    for action in proposed_actions:
        if not isinstance(action, dict):
            continue
        actions.append(
            {
                "action_id": action.get("action_id", "unknown"),
                "action_type": action.get("action_type", "unknown"),
                "namespace": action.get("namespace", "unknown"),
                "name": action.get("name", "unknown"),
                "params": action.get("params", {}),
                "status": "pending",
                "expires_at": action.get("expires_at"),
            }
        )
    return actions


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
    if "actions" not in record:
        record["actions"] = _initial_actions(record)
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
