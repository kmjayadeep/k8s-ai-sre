import os
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel, Field

from app.alert_ingestion import ingestion_status_snapshot, record_ingestion_event
from app.actions import approve_action, attach_actions_to_incident, reject_action
from app.backpressure import get_queue_status
from app.error_taxonomy import raise_http_error
from app.ui.auth_middleware import InspectorAuthMiddleware, load_inspector_auth
from app.investigate import investigate_target
from app.log import log_event
from app.metrics import record_alertmanager_reconciliation_run, render_prometheus_metrics
from app.notifier import send_telegram_notification
from app.stores.actions import list_pending_actions
from app.stores import (
    append_incident_event,
    create_incident,
    find_active_incident_by_target,
    get_action,
    get_incident,
    list_incidents,
    update_incident,
)
from app.telegram import start_telegram_polling_thread


class InvestigateRequest(BaseModel):
    kind: str
    namespace: str
    name: str


class AlertmanagerAlert(BaseModel):
    status: str | None = None
    labels: dict[str, str] = Field(default_factory=dict)


class AlertmanagerWebhook(BaseModel):
    status: str | None = None
    receiver: str | None = None
    commonLabels: dict[str, str] = Field(default_factory=dict)
    alerts: list[AlertmanagerAlert] = Field(default_factory=list)


class HealthzResponse(BaseModel):
    status: str


class QueueStatusResponse(BaseModel):
    queue_depth: int
    max_queue_size: int
    active_investigations: int
    max_concurrent_investigations: int
    queue_utilization: float
    last_processing_heartbeat_at: str | None = None
    last_processing_heartbeat_age_seconds: float | None = None
    last_processing_target: str | None = None
    last_processing_state: str | None = None


class ProposedActionResponse(BaseModel):
    action_id: str
    action_type: str
    namespace: str
    name: str
    params: dict[str, object] = Field(default_factory=dict)
    expires_at: str | None = None
    approve_command: str
    reject_command: str


class InvestigationBriefResponse(BaseModel):
    summary: str = ""
    root_cause: str = ""
    confidence: str = ""
    action_items: list[str] = Field(default_factory=list)


class IncidentEventResponse(BaseModel):
    event: str
    source: str
    occurred_at: str
    details: dict[str, object] = Field(default_factory=dict)


class IncidentResponse(BaseModel):
    incident_id: str
    kind: str
    namespace: str
    name: str
    lifecycle_status: str = "active"
    created_at: str = ""
    updated_at: str = ""
    last_event_at: str = ""
    answer: str = ""
    evidence: str = ""
    source: str = "manual"
    brief: InvestigationBriefResponse = Field(default_factory=InvestigationBriefResponse)
    action_ids: list[str] = Field(default_factory=list)
    proposed_actions: list[ProposedActionResponse] = Field(default_factory=list)
    notification_status: str | None = None
    dedup_key: str = ""
    lifecycle_status: str = "active"
    dedup_count: int = 0
    event_history: list[IncidentEventResponse] = Field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    supersedes_incident_id: str | None = None
    related_incident_ids: list[str] = Field(default_factory=list)


class IncidentsResponse(BaseModel):
    incidents: list[IncidentResponse] = Field(default_factory=list)


class ActionDecisionResponse(BaseModel):
    action_id: str
    status: str
    message: str


class PendingActionsResponse(BaseModel):
    pending_actions: list[dict] = Field(default_factory=list)


class IngestionStatusResponse(BaseModel):
    status: str
    window_size: int
    failed_deliveries: int
    failure_rate: float
    degrade_threshold: float
    min_samples: int
    failed_by_receiver: dict[str, int] = Field(default_factory=dict)
    failed_by_target: dict[str, int] = Field(default_factory=dict)
    last_failure_at: str | None = None
    last_failure_detail: str | None = None


class AlertmanagerReconcileRequest(BaseModel):
    receiver: str | None = None
    alerts: list[AlertmanagerAlert] = Field(default_factory=list)


class AlertmanagerReconcileResponse(BaseModel):
    receiver: str
    active_alerts_seen: int
    recovered_incidents: int
    skipped_existing_incidents: int
    failed_alerts: int
    recovered_incident_ids: list[str] = Field(default_factory=list)


app = FastAPI()
app.add_middleware(InspectorAuthMiddleware)

_UI_TEMPLATE_PATH = Path(__file__).resolve().parent / "ui" / "incident_inspector.html"


def _load_incident_inspector_html() -> str:
    return _UI_TEMPLATE_PATH.read_text(encoding="utf-8")


_ALERTMANAGER_API_KEY: str | None = None


def _load_alertmanager_api_key() -> None:
    global _ALERTMANAGER_API_KEY
    _ALERTMANAGER_API_KEY = os.getenv("ALERTMANAGER_API_KEY", "").strip() or None


def _require_alertmanager_api_key(api_key: str | None) -> None:
    if _ALERTMANAGER_API_KEY is None:
        return  # auth disabled
    provided_key = (api_key or "").strip()
    if not provided_key:
        raise_http_error(401, "alertmanager_api_key_missing", "missing Alertmanager API key")
    if provided_key != _ALERTMANAGER_API_KEY:
        raise_http_error(403, "alertmanager_api_key_invalid", "invalid Alertmanager API key")


def _require_operator_api_token(authorization: str | None) -> None:
    configured_token = os.getenv("OPERATOR_API_TOKEN", "").strip()
    if not configured_token:
        raise_http_error(503, "operator_api_not_configured", "operator API approval endpoint is not configured")
    if not authorization or not authorization.startswith("Bearer "):
        raise_http_error(401, "operator_token_missing", "missing operator token")
    provided_token = authorization.split(" ", 1)[1].strip()
    if provided_token != configured_token:
        raise_http_error(403, "operator_token_invalid", "invalid operator token")


def _require_operator_identity(operator_id: str | None) -> str:
    candidate = (operator_id or "").strip()
    if not candidate:
        raise_http_error(400, "operator_identity_missing", "missing operator identity header (X-Operator-Id)")
    return candidate


def _action_status_or_not_found(action_id: str) -> str:
    action = get_action(action_id)
    if action is None:
        raise_http_error(404, "action_not_found", "action not found")
    return str(action.get("status", "unknown"))


@app.get("/", response_class=HTMLResponse)
async def incident_inspector() -> HTMLResponse:
    return HTMLResponse(content=_load_incident_inspector_html())


@app.get("/healthz", response_model=HealthzResponse)
async def healthz() -> HealthzResponse:
    return HealthzResponse(status="ok")



@app.get("/queue-status", response_model=QueueStatusResponse)
async def queue_status() -> QueueStatusResponse:
    status = get_queue_status()
    return QueueStatusResponse.model_validate(status)


@app.get("/metrics", response_class=PlainTextResponse)
async def metrics() -> PlainTextResponse:
    return PlainTextResponse(content=render_prometheus_metrics(), media_type="text/plain; version=0.0.4")


@app.get("/ingestion-status", response_model=IngestionStatusResponse)
async def ingestion_status() -> IngestionStatusResponse:
    threshold_raw = os.getenv("ALERTMANAGER_INGESTION_FAILURE_THRESHOLD", "").strip()
    min_samples_raw = os.getenv("ALERTMANAGER_INGESTION_MIN_SAMPLES", "").strip()
    try:
        threshold = float(threshold_raw) if threshold_raw else 0.2
    except ValueError:
        threshold = 0.2
    try:
        min_samples = int(min_samples_raw) if min_samples_raw else 5
    except ValueError:
        min_samples = 5
    snapshot = ingestion_status_snapshot(degrade_threshold=max(0.0, threshold), min_samples=max(1, min_samples))
    return IngestionStatusResponse.model_validate(snapshot)


@app.post("/investigate", response_model=IncidentResponse)
async def investigate(request: InvestigateRequest) -> IncidentResponse:
    if not all([request.kind, request.namespace, request.name]):
        raise HTTPException(status_code=400, detail="kind, namespace, and name are required")
    existing = find_active_incident_by_target(request.kind, request.namespace, request.name)
    if existing is not None:
        merged = append_incident_event(
            existing["incident_id"],
            event_name="duplicate_investigate_request",
            source="manual",
            details={"kind": request.kind, "namespace": request.namespace, "name": request.name},
        )
        log_event(
            "http_investigate_deduplicated",
            incident_id=existing["incident_id"],
            kind=request.kind,
            namespace=request.namespace,
            name=request.name,
        )
        return IncidentResponse.model_validate(merged or existing)
    log_event("http_investigate_received", kind=request.kind, namespace=request.namespace, name=request.name)
    result = await investigate_target(request.kind, request.namespace, request.name, emit_progress=False)
    incident = create_incident(result)
    attach_actions_to_incident(incident.get("action_ids", []), incident["incident_id"])
    incident["notification_status"] = send_telegram_notification(incident)
    update_incident(incident["incident_id"], {"notification_status": incident["notification_status"]})
    log_event(
        "http_investigate_completed",
        incident_id=incident["incident_id"],
        kind=request.kind,
        namespace=request.namespace,
        name=request.name,
    )
    return IncidentResponse.model_validate(incident)


@app.post("/reconcile/alertmanager", response_model=AlertmanagerReconcileResponse)
async def reconcile_alertmanager(
    payload: AlertmanagerReconcileRequest,
    authorization: str | None = Header(default=None, alias="X-API-Key"),
) -> AlertmanagerReconcileResponse:
    _require_alertmanager_api_key(authorization)
    receiver = _receiver_name(payload.receiver)
    active_alerts = [alert for alert in payload.alerts if (alert.status or "").strip().lower() == "firing"]
    recovered = 0
    skipped_existing = 0
    failed = 0
    recovered_ids: list[str] = []

    log_event(
        "alertmanager_reconcile_started",
        receiver=receiver,
        active_alerts_seen=len(active_alerts),
    )
    for alert in active_alerts:
        nested_payload = AlertmanagerWebhook(status=alert.status, receiver=receiver, commonLabels=alert.labels, alerts=[alert])
        try:
            kind, namespace, name = _resolve_alert_target(nested_payload)
        except HTTPException as exc:
            failed += 1
            record_ingestion_event(receiver, "unknown", "failed", detail=str(exc.detail))
            continue
        target = _target_key(kind, namespace, name)
        existing = find_active_incident_by_target(kind, namespace, name)
        if existing is not None:
            skipped_existing += 1
            record_ingestion_event(receiver, target, "reconcile_skipped")
            continue
        try:
            incident = await _ingest_alert_target(
                kind=kind,
                namespace=namespace,
                name=name,
                statuses=["firing"],
                receiver=receiver,
                success_outcome="recovered",
            )
            recovered += 1
            recovered_ids.append(incident.incident_id)
        except Exception as exc:
            failed += 1
            record_ingestion_event(receiver, target, "failed", detail=str(exc))

    run_status = "failed" if failed else "ok"
    record_alertmanager_reconciliation_run(run_status)
    log_event(
        "alertmanager_reconcile_completed",
        receiver=receiver,
        active_alerts_seen=len(active_alerts),
        recovered_incidents=recovered,
        skipped_existing_incidents=skipped_existing,
        failed_alerts=failed,
    )
    return AlertmanagerReconcileResponse(
        receiver=receiver,
        active_alerts_seen=len(active_alerts),
        recovered_incidents=recovered,
        skipped_existing_incidents=skipped_existing,
        failed_alerts=failed,
        recovered_incident_ids=recovered_ids,
    )


def _resolve_alert_target(payload: AlertmanagerWebhook) -> tuple[str, str, str]:
    labels = dict(payload.commonLabels)
    if payload.alerts:
        labels = {**labels, **payload.alerts[0].labels}

    namespace = labels.get("namespace", "default")
    if "deployment" in labels:
        return "deployment", namespace, labels["deployment"]
    if "pod" in labels:
        return "pod", namespace, labels["pod"]
    if "statefulset" in labels:
        return "statefulset", namespace, labels["statefulset"]
    raise HTTPException(status_code=400, detail="could not resolve alert target from labels")


def _alert_statuses(payload: AlertmanagerWebhook) -> list[str]:
    statuses: list[str] = []
    if payload.status:
        statuses.append(payload.status.strip().lower())
    for alert in payload.alerts:
        if alert.status:
            statuses.append(alert.status.strip().lower())
    return [status for status in statuses if status]


def _is_resolved_alert(payload: AlertmanagerWebhook) -> bool:
    statuses = _alert_statuses(payload)
    if not statuses:
        return False
    if "firing" in statuses:
        return False
    return all(status == "resolved" for status in statuses)


def _receiver_name(receiver: str | None) -> str:
    return (receiver or "").strip() or "unknown"


def _target_key(kind: str, namespace: str, name: str) -> str:
    return f"{kind}/{namespace}/{name}"


async def _ingest_alert_target(
    *,
    kind: str,
    namespace: str,
    name: str,
    statuses: list[str],
    receiver: str,
    success_outcome: str = "success",
) -> IncidentResponse:
    target = _target_key(kind, namespace, name)
    existing = find_active_incident_by_target(kind, namespace, name)
    if existing is not None:
        merged = append_incident_event(
            existing["incident_id"],
            event_name="alertmanager_duplicate_firing",
            source="alertmanager",
            details={"alert_statuses": statuses, "receiver": receiver},
        )
        record_ingestion_event(receiver, target, "deduplicated")
        log_event(
            "alertmanager_webhook_deduplicated",
            incident_id=existing["incident_id"],
            receiver=receiver,
            kind=kind,
            namespace=namespace,
            name=name,
        )
        return IncidentResponse.model_validate(merged or existing)

    result = await investigate_target(kind, namespace, name, emit_progress=False)
    result["source"] = "alertmanager"
    incident = create_incident(result)
    attach_actions_to_incident(incident.get("action_ids", []), incident["incident_id"])
    incident["notification_status"] = send_telegram_notification(incident)
    update_incident(incident["incident_id"], {"source": "alertmanager", "notification_status": incident["notification_status"]})
    record_ingestion_event(receiver, target, success_outcome)
    log_event(
        "alertmanager_webhook_completed",
        incident_id=incident["incident_id"],
        receiver=receiver,
        kind=kind,
        namespace=namespace,
        name=name,
    )
    return IncidentResponse.model_validate(incident)


@app.post("/webhooks/alertmanager", response_model=IncidentResponse)
async def alertmanager_webhook(
    payload: AlertmanagerWebhook,
    authorization: str | None = Header(default=None, alias="X-API-Key"),
) -> IncidentResponse:
    _require_alertmanager_api_key(authorization)
    receiver = _receiver_name(payload.receiver)
    kind, namespace, name = _resolve_alert_target(payload)
    target = _target_key(kind, namespace, name)
    statuses = _alert_statuses(payload)
    log_event(
        "alertmanager_webhook_received",
        receiver=receiver,
        kind=kind,
        namespace=namespace,
        name=name,
        alert_statuses=",".join(statuses) if statuses else "unknown",
    )
    try:
        existing = find_active_incident_by_target(kind, namespace, name)
        if _is_resolved_alert(payload):
            if existing is not None:
                append_incident_event(
                    existing["incident_id"],
                    event_name="alertmanager_resolved",
                    source="alertmanager",
                    details={"alert_statuses": statuses, "receiver": receiver},
                    lifecycle_status="resolved",
                )
                merged = update_incident(existing["incident_id"], {"notification_status": "Skipped notification for resolved alert."})
                record_ingestion_event(receiver, target, "resolved")
                log_event(
                    "alertmanager_webhook_deduplicated_resolved",
                    incident_id=existing["incident_id"],
                    receiver=receiver,
                    kind=kind,
                    namespace=namespace,
                    name=name,
                )
                return IncidentResponse.model_validate(merged or existing)
            incident = create_incident(
                {
                    "kind": kind,
                    "namespace": namespace,
                    "name": name,
                    "source": "alertmanager",
                    "lifecycle_status": "resolved",
                    "answer": "Alertmanager reported this alert as resolved; investigation and remediation were skipped.",
                    "evidence": f"Alert statuses: {', '.join(statuses)}",
                    "action_ids": [],
                    "proposed_actions": [],
                    "notification_status": "Skipped notification for resolved alert.",
                }
            )
            record_ingestion_event(receiver, target, "resolved")
            log_event(
                "alertmanager_webhook_skipped_resolved",
                incident_id=incident["incident_id"],
                receiver=receiver,
                kind=kind,
                namespace=namespace,
                name=name,
            )
            return IncidentResponse.model_validate(incident)

        return await _ingest_alert_target(kind=kind, namespace=namespace, name=name, statuses=statuses, receiver=receiver)
    except Exception as exc:
        record_ingestion_event(receiver, target, "failed", detail=str(exc))
        log_event(
            "alertmanager_webhook_failed",
            receiver=receiver,
            kind=kind,
            namespace=namespace,
            name=name,
            error=str(exc),
        )
        raise


@app.get("/incidents", response_model=IncidentsResponse)
async def read_incidents() -> IncidentsResponse:
    incidents = [IncidentResponse.model_validate(incident) for incident in list_incidents()]
    return IncidentsResponse(incidents=incidents)



@app.get("/actions", response_model=PendingActionsResponse)
async def read_pending_actions(namespace: str | None = None) -> PendingActionsResponse:
    pending = list_pending_actions(namespace)
    return PendingActionsResponse(pending_actions=pending)


@app.get("/incidents/{incident_id}", response_model=IncidentResponse)
async def read_incident(incident_id: str) -> IncidentResponse:
    incident = get_incident(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="incident not found")
    return IncidentResponse.model_validate(incident)


@app.post("/actions/{action_id}/approve", response_model=ActionDecisionResponse)
async def approve_action_http(
    action_id: str,
    authorization: str | None = Header(default=None),
    operator_id: str | None = Header(default=None, alias="X-Operator-Id"),
) -> ActionDecisionResponse:
    _require_operator_api_token(authorization)
    approver_id = _require_operator_identity(operator_id)
    message = approve_action(action_id, approver_id=approver_id, approval_source="http_api")
    return ActionDecisionResponse(action_id=action_id, status=_action_status_or_not_found(action_id), message=message)


@app.post("/actions/{action_id}/reject", response_model=ActionDecisionResponse)
async def reject_action_http(
    action_id: str,
    authorization: str | None = Header(default=None),
    operator_id: str | None = Header(default=None, alias="X-Operator-Id"),
) -> ActionDecisionResponse:
    _require_operator_api_token(authorization)
    approver_id = _require_operator_identity(operator_id)
    message = reject_action(action_id, approver_id=approver_id, approval_source="http_api")
    return ActionDecisionResponse(action_id=action_id, status=_action_status_or_not_found(action_id), message=message)


def run_server(port: int = 8080) -> None:
    log_event("server_starting", port=port)
    load_inspector_auth()
    _load_alertmanager_api_key()
    start_telegram_polling_thread()
    uvicorn.run(app, host="0.0.0.0", port=port)
