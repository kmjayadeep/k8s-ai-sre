import os
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel, Field

from app.actions import approve_action, attach_actions_to_incident, reject_action
from app.error_taxonomy import raise_http_error
from app.investigate import investigate_target
from app.log import log_event
from app.metrics import render_prometheus_metrics
from app.notifier import send_telegram_notification
from app.stores import create_incident, get_action, get_incident, list_incidents, update_incident
from app.telegram import start_telegram_polling_thread


class InvestigateRequest(BaseModel):
    kind: str
    namespace: str
    name: str


class AlertmanagerAlert(BaseModel):
    labels: dict[str, str] = Field(default_factory=dict)


class AlertmanagerWebhook(BaseModel):
    commonLabels: dict[str, str] = Field(default_factory=dict)
    alerts: list[AlertmanagerAlert] = Field(default_factory=list)


class HealthzResponse(BaseModel):
    status: str


class ProposedActionResponse(BaseModel):
    action_id: str
    action_type: str
    namespace: str
    name: str
    params: dict[str, object] = Field(default_factory=dict)
    expires_at: str | None = None
    approve_command: str
    reject_command: str


class IncidentResponse(BaseModel):
    incident_id: str
    kind: str
    namespace: str
    name: str
    answer: str = ""
    evidence: str = ""
    source: str = "manual"
    action_ids: list[str] = Field(default_factory=list)
    proposed_actions: list[ProposedActionResponse] = Field(default_factory=list)
    notification_status: str | None = None


class IncidentsResponse(BaseModel):
    incidents: list[IncidentResponse] = Field(default_factory=list)


class ActionDecisionResponse(BaseModel):
    action_id: str
    status: str
    message: str


app = FastAPI()

_UI_TEMPLATE_PATH = Path(__file__).resolve().parent / "ui" / "incident_inspector.html"


def _load_incident_inspector_html() -> str:
    return _UI_TEMPLATE_PATH.read_text(encoding="utf-8")


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


@app.get("/metrics", response_class=PlainTextResponse)
async def metrics() -> PlainTextResponse:
    return PlainTextResponse(content=render_prometheus_metrics(), media_type="text/plain; version=0.0.4")


@app.post("/investigate", response_model=IncidentResponse)
async def investigate(request: InvestigateRequest) -> IncidentResponse:
    if not all([request.kind, request.namespace, request.name]):
        raise HTTPException(status_code=400, detail="kind, namespace, and name are required")
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


@app.post("/webhooks/alertmanager", response_model=IncidentResponse)
async def alertmanager_webhook(payload: AlertmanagerWebhook) -> IncidentResponse:
    kind, namespace, name = _resolve_alert_target(payload)
    log_event("alertmanager_webhook_received", kind=kind, namespace=namespace, name=name)
    result = await investigate_target(kind, namespace, name, emit_progress=False)
    result["source"] = "alertmanager"
    incident = create_incident(result)
    attach_actions_to_incident(incident.get("action_ids", []), incident["incident_id"])
    incident["notification_status"] = send_telegram_notification(incident)
    update_incident(incident["incident_id"], {"source": "alertmanager", "notification_status": incident["notification_status"]})
    log_event("alertmanager_webhook_completed", incident_id=incident["incident_id"], kind=kind, namespace=namespace, name=name)
    return IncidentResponse.model_validate(incident)


@app.get("/incidents", response_model=IncidentsResponse)
async def read_incidents() -> IncidentsResponse:
    incidents = [IncidentResponse.model_validate(incident) for incident in list_incidents()]
    return IncidentsResponse(incidents=incidents)


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
    start_telegram_polling_thread()
    uvicorn.run(app, host="0.0.0.0", port=port)
