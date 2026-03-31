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


def _normalize_action_summary(action: dict[str, object]) -> dict[str, object]:
    action_id = str(action.get("action_id", action.get("id", "unknown")))
    action_type = str(action.get("action_type", action.get("type", "unknown")))
    return {
        "action_id": action_id,
        "action_type": action_type,
        "namespace": str(action.get("namespace", "unknown")),
        "name": str(action.get("name", "unknown")),
        "params": action.get("params", {}) if isinstance(action.get("params", {}), dict) else {},
        "status": str(action.get("status", "pending")),
        "expires_at": action.get("expires_at"),
    }


def _normalize_proposed_action(action: dict[str, object]) -> dict[str, object]:
    action_id = str(action.get("action_id", action.get("id", "unknown")))
    action_type = str(action.get("action_type", action.get("type", "unknown")))
    normalized = {
        "action_id": action_id,
        "action_type": action_type,
        "namespace": str(action.get("namespace", "unknown")),
        "name": str(action.get("name", "unknown")),
        "params": action.get("params", {}) if isinstance(action.get("params", {}), dict) else {},
        "expires_at": action.get("expires_at"),
    }
    approve_command = action.get("approve_command")
    reject_command = action.get("reject_command")
    if isinstance(approve_command, str):
        normalized["approve_command"] = approve_command
    if isinstance(reject_command, str):
        normalized["reject_command"] = reject_command
    return normalized


def _derive_proposed_actions(actions: list[dict[str, object]]) -> list[dict[str, object]]:
    return [
        {
            "action_id": action["action_id"],
            "action_type": action["action_type"],
            "namespace": action["namespace"],
            "name": action["name"],
            "params": action.get("params", {}),
            "expires_at": action.get("expires_at"),
        }
        for action in actions
    ]


def _normalize_incident_payload(payload: dict[str, object]) -> dict[str, object]:
    record = dict(payload)

    raw_actions = record.get("actions")
    normalized_actions: list[dict[str, object]] = []
    if isinstance(raw_actions, list):
        for action in raw_actions:
            if isinstance(action, dict):
                normalized_actions.append(_normalize_action_summary(action))
    if not normalized_actions:
        normalized_actions = _initial_actions(record)
    record["actions"] = normalized_actions

    raw_proposed_actions = record.get("proposed_actions")
    normalized_proposed_actions: list[dict[str, object]] = []
    if isinstance(raw_proposed_actions, list):
        for action in raw_proposed_actions:
            if isinstance(action, dict):
                normalized_proposed_actions.append(_normalize_proposed_action(action))
    if not normalized_proposed_actions and normalized_actions:
        normalized_proposed_actions = _derive_proposed_actions(normalized_actions)
    record["proposed_actions"] = normalized_proposed_actions

    action_ids = [action["action_id"] for action in normalized_actions]
    if not action_ids and normalized_proposed_actions:
        action_ids = [str(action["action_id"]) for action in normalized_proposed_actions]
    record["action_ids"] = action_ids
    return record


def _load_incidents() -> dict[str, dict[str, object]]:
    if not INCIDENT_STORE_PATH.exists():
        return {}
    return json.loads(INCIDENT_STORE_PATH.read_text(encoding="utf-8"))


def _save_incidents(incidents: dict[str, dict[str, object]]) -> None:
    INCIDENT_STORE_PATH.write_text(json.dumps(incidents, indent=2, sort_keys=True), encoding="utf-8")


def create_incident(payload: dict[str, object]) -> dict[str, object]:
    incidents = _load_incidents()
    incident_id = uuid4().hex[:10]
    record = _normalize_incident_payload({"incident_id": incident_id, **payload})
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
    incident = _normalize_incident_payload(incident)
    incidents[incident_id] = incident
    _save_incidents(incidents)
    return incident
