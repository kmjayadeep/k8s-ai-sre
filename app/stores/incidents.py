import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from app.stores.backend import KeyValueStore, SqliteKeyValueStore


INCIDENT_STORE_PATH = Path(os.getenv("K8S_AI_SRE_STORE_PATH", "/tmp/k8s-ai-sre-store.sqlite3"))
_incident_store: KeyValueStore = SqliteKeyValueStore(lambda: INCIDENT_STORE_PATH, table_name="incidents")


def _load_incidents() -> dict[str, dict[str, object]]:
    return _incident_store.load()


def _save_incidents(incidents: dict[str, dict[str, object]]) -> None:
    _incident_store.save(incidents)


def set_incident_store(store: KeyValueStore) -> None:
    global _incident_store
    _incident_store = store


def _string(value: object, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


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


def _normalize_brief(payload: dict[str, object]) -> dict[str, object]:
    raw_brief = payload.get("brief")
    if not isinstance(raw_brief, dict):
        return {}
    summary = _string(raw_brief.get("summary")).strip()
    root_cause = _string(raw_brief.get("root_cause")).strip()
    confidence = _string(raw_brief.get("confidence")).strip()
    action_items_raw = raw_brief.get("action_items", [])
    action_items: list[str] = []
    if isinstance(action_items_raw, list):
        for item in action_items_raw:
            text = _string(item).strip()
            if text:
                action_items.append(text)
    if not summary and not root_cause and not confidence and not action_items:
        return {}
    return {
        "summary": summary,
        "root_cause": root_cause,
        "confidence": confidence,
        "action_items": action_items,
    }


def _normalize_event_history(payload: dict[str, object]) -> list[dict[str, object]]:
    raw_history = payload.get("event_history", [])
    if not isinstance(raw_history, list):
        return []

    normalized: list[dict[str, object]] = []
    for item in raw_history:
        if not isinstance(item, dict):
            continue
        event_name = _string(item.get("event")).strip()
        if not event_name:
            continue
        source = _string(item.get("source"), "unknown").strip() or "unknown"
        occurred_at = _string(item.get("occurred_at")).strip() or _utc_now()
        event: dict[str, object] = {"event": event_name, "source": source, "occurred_at": occurred_at}
        details = item.get("details")
        if isinstance(details, dict) and details:
            event["details"] = details
        normalized.append(event)
    return normalized


def _normalize_related_incident_ids(payload: dict[str, object], incident_id: str) -> list[str]:
    raw_related = payload.get("related_incident_ids", [])
    if not isinstance(raw_related, list):
        return []
    normalized: list[str] = []
    for item in raw_related:
        candidate = _string(item).strip()
        if not candidate or candidate == incident_id or candidate in normalized:
            continue
        normalized.append(candidate)
    return normalized


def _normalize_supersedes_incident_id(payload: dict[str, object], incident_id: str) -> str | None:
    candidate = _string(payload.get("supersedes_incident_id")).strip()
    if not candidate or candidate == incident_id:
        return None
    return candidate


def _target_dedup_key(kind: str, namespace: str, name: str) -> str:
    return f"{kind.strip().lower()}:{namespace.strip().lower()}:{name.strip().lower()}"


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
    normalized["dedup_key"] = _target_dedup_key(normalized["kind"], normalized["namespace"], normalized["name"])
    lifecycle_status = _string(normalized.get("lifecycle_status"), "active").strip().lower() or "active"
    normalized["lifecycle_status"] = "resolved" if lifecycle_status == "resolved" else "active"
    normalized["brief"] = _normalize_brief(normalized)
    normalized["proposed_actions"] = _normalize_proposed_actions(normalized)
    normalized["event_history"] = _normalize_event_history(normalized)
    dedup_count = normalized.get("dedup_count", 0)
    try:
        normalized["dedup_count"] = max(int(dedup_count), 0)
    except (TypeError, ValueError):
        normalized["dedup_count"] = 0
    action_ids = _normalize_action_ids(normalized)
    if not action_ids:
        action_ids = [item["action_id"] for item in normalized["proposed_actions"]]
    normalized["action_ids"] = action_ids
    current_incident_id = _string(normalized.get("incident_id")).strip()
    normalized["related_incident_ids"] = _normalize_related_incident_ids(normalized, current_incident_id)
    normalized["supersedes_incident_id"] = _normalize_supersedes_incident_id(normalized, current_incident_id)
    created_at = _string(normalized.get("created_at")).strip()
    updated_at = _string(normalized.get("updated_at")).strip()
    if not created_at:
        created_at = _utc_now()
    if not updated_at:
        updated_at = created_at
    normalized["created_at"] = created_at
    normalized["updated_at"] = updated_at
    last_event_at = _string(normalized.get("last_event_at")).strip()
    if not last_event_at and normalized["event_history"]:
        tail = normalized["event_history"][-1]
        if isinstance(tail, dict):
            last_event_at = _string(tail.get("occurred_at")).strip()
    if not last_event_at:
        last_event_at = updated_at
    normalized["last_event_at"] = last_event_at
    notification_status = normalized.get("notification_status")
    if notification_status is not None:
        normalized["notification_status"] = _string(notification_status)
    return normalized


def _incident_sort_key(incident: dict[str, object]) -> tuple[str, str, str]:
    return (
        _string(incident.get("created_at")),
        _string(incident.get("updated_at")),
        _string(incident.get("incident_id")),
    )


def _normalize_and_backfill_incidents(incidents: dict[str, dict[str, object]]) -> dict[str, dict[str, object]]:
    normalized_records: dict[str, dict[str, object]] = {}
    dirty = False
    grouped_by_target: dict[str, list[dict[str, object]]] = {}

    for incident_id, incident in incidents.items():
        normalized = normalize_incident_payload(incident, incident_id=incident_id)
        if normalized != incident:
            dirty = True
        normalized_records[incident_id] = normalized
        grouped_by_target.setdefault(_string(normalized.get("dedup_key")), []).append(normalized)

    for group in grouped_by_target.values():
        group.sort(key=_incident_sort_key)
        ordered_ids = [_string(item.get("incident_id")) for item in group]
        for index, incident in enumerate(group):
            incident_id = _string(incident.get("incident_id"))
            expected_supersedes = ordered_ids[index - 1] if index > 0 else None
            expected_related = [candidate for candidate in ordered_ids if candidate != incident_id]
            if incident.get("supersedes_incident_id") != expected_supersedes:
                incident["supersedes_incident_id"] = expected_supersedes
                dirty = True
            if incident.get("related_incident_ids") != expected_related:
                incident["related_incident_ids"] = expected_related
                dirty = True

    if dirty:
        _save_incidents(normalized_records)
    return normalized_records


def create_incident(payload: dict[str, object]) -> dict[str, object]:
    incidents = _load_incidents()
    incident_id = uuid4().hex[:10]
    record = normalize_incident_payload(payload, incident_id=incident_id)
    now = _utc_now()
    record["created_at"] = now
    record["updated_at"] = now
    record["last_event_at"] = now
    record["event_history"] = list(record["event_history"])
    record["event_history"].append({"event": "incident_created", "source": record["source"], "occurred_at": now})
    incidents[incident_id] = record
    _save_incidents(incidents)
    incidents = _normalize_and_backfill_incidents(incidents)
    return incidents[incident_id]


def get_incident(incident_id: str) -> dict[str, object] | None:
    incidents = _normalize_and_backfill_incidents(_load_incidents())
    return incidents.get(incident_id)


def list_incidents() -> list[dict[str, object]]:
    normalized_records = _normalize_and_backfill_incidents(_load_incidents())
    return [normalized_records[incident_id] for incident_id in sorted(normalized_records.keys(), reverse=True)]


def update_incident(incident_id: str, updates: dict[str, object]) -> dict[str, object] | None:
    incidents = _load_incidents()
    incident = incidents.get(incident_id)
    if incident is None:
        return None
    incident.update(updates)
    incident["updated_at"] = _utc_now()
    normalized = normalize_incident_payload(incident, incident_id=incident_id)
    incidents[incident_id] = normalized
    _save_incidents(incidents)
    incidents = _normalize_and_backfill_incidents(incidents)
    return incidents[incident_id]


def find_active_incident_by_target(kind: str, namespace: str, name: str) -> dict[str, object] | None:
    incidents = _normalize_and_backfill_incidents(_load_incidents())
    dedup_key = _target_dedup_key(kind, namespace, name)
    matches: list[dict[str, object]] = []

    for incident in incidents.values():
        if incident["dedup_key"] == dedup_key and incident["lifecycle_status"] == "active":
            matches.append(incident)
    if not matches:
        return None
    matches.sort(key=lambda item: (_string(item.get("updated_at")), _string(item.get("created_at")), _string(item.get("incident_id"))))
    return matches[-1]


def append_incident_event(
    incident_id: str,
    *,
    event_name: str,
    source: str,
    details: dict[str, object] | None = None,
    lifecycle_status: str | None = None,
) -> dict[str, object] | None:
    incidents = _load_incidents()
    incident = incidents.get(incident_id)
    if incident is None:
        return None

    normalized = normalize_incident_payload(incident, incident_id=incident_id)
    now = _utc_now()
    history = list(normalized["event_history"])
    entry: dict[str, object] = {"event": event_name, "source": source, "occurred_at": now}
    if details:
        entry["details"] = details
    history.append(entry)
    normalized["event_history"] = history
    normalized["dedup_count"] = int(normalized["dedup_count"]) + 1
    normalized["updated_at"] = now
    normalized["last_event_at"] = now
    if lifecycle_status is not None:
        lifecycle = _string(lifecycle_status).strip().lower()
        normalized["lifecycle_status"] = "resolved" if lifecycle == "resolved" else "active"

    incidents[incident_id] = normalize_incident_payload(normalized, incident_id=incident_id)
    _save_incidents(incidents)
    incidents = _normalize_and_backfill_incidents(incidents)
    return incidents[incident_id]
