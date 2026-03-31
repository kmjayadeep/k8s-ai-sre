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


def _string(value: object, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def _normalize_action_ids(payload: dict[str, object]) -> list[str]:
    raw_action_ids = payload.get("action_ids", [])
    if not isinstance(raw_action_ids, list):
        return []
    normalized: list[str] = []
    for action_id in raw_action_ids:
        action_id_str = _string(action_id).strip()
        if action_id_str and action_id_str not in normalized:
            normalized.append(action_id_str)
    return normalized


def _normalize_proposed_actions(payload: dict[str, object]) -> list[dict[str, object]]:
    raw_actions = payload.get("proposed_actions", [])
    if not isinstance(raw_actions, list):
        return []

    normalized: list[dict[str, object]] = []
    default_namespace = _string(payload.get("namespace"))
    default_name = _string(payload.get("name"))
    for item in raw_actions:
        if not isinstance(item, dict):
            continue
        action_id = _string(item.get("action_id")).strip()
        if not action_id:
            continue
        action_type = _string(item.get("action_type"), "unknown").strip() or "unknown"
        namespace = _string(item.get("namespace"), default_namespace)
        name = _string(item.get("name"), default_name)
        params = item.get("params", {})
        if not isinstance(params, dict):
            params = {}
        record: dict[str, object] = {
            "action_id": action_id,
            "action_type": action_type,
            "namespace": namespace,
            "name": name,
            "params": params,
            "approve_command": _string(item.get("approve_command"), f"/approve {action_id}"),
            "reject_command": _string(item.get("reject_command"), f"/reject {action_id}"),
        }
        expires_at = item.get("expires_at")
        if expires_at is not None:
            record["expires_at"] = _string(expires_at)
        normalized.append(record)
    return normalized


def normalize_incident_payload(payload: dict[str, object], incident_id: str | None = None) -> dict[str, object]:
    normalized = dict(payload)
    if incident_id is not None:
        normalized["incident_id"] = incident_id
    normalized["kind"] = _string(normalized.get("kind"))
    normalized["namespace"] = _string(normalized.get("namespace"))
    normalized["name"] = _string(normalized.get("name"))
    normalized["answer"] = _string(normalized.get("answer"))
    normalized["evidence"] = _string(normalized.get("evidence"))
    normalized["source"] = _string(normalized.get("source"), "manual")
    normalized["proposed_actions"] = _normalize_proposed_actions(normalized)
    action_ids = _normalize_action_ids(normalized)
    if not action_ids:
        action_ids = [item["action_id"] for item in normalized["proposed_actions"]]
    normalized["action_ids"] = action_ids
    notification_status = normalized.get("notification_status")
    if notification_status is not None:
        normalized["notification_status"] = _string(notification_status)
    return normalized


def create_incident(payload: dict[str, object]) -> dict[str, object]:
    incidents = _load_incidents()
    incident_id = uuid4().hex[:10]
    record = normalize_incident_payload(payload, incident_id=incident_id)
    incidents[incident_id] = record
    _save_incidents(incidents)
    return record


def get_incident(incident_id: str) -> dict[str, object] | None:
    incidents = _load_incidents()
    incident = incidents.get(incident_id)
    if incident is None:
        return None
    normalized = normalize_incident_payload(incident, incident_id=incident_id)
    if normalized != incident:
        incidents[incident_id] = normalized
        _save_incidents(incidents)
    return normalized


def update_incident(incident_id: str, updates: dict[str, object]) -> dict[str, object] | None:
    incidents = _load_incidents()
    incident = incidents.get(incident_id)
    if incident is None:
        return None
    incident.update(updates)
    normalized = normalize_incident_payload(incident, incident_id=incident_id)
    incidents[incident_id] = normalized
    _save_incidents(incidents)
    return normalized
