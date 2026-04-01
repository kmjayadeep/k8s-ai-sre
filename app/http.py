import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.actions import attach_actions_to_incident
from app.investigate import investigate_target
from app.log import log_event
from app.notifier import send_telegram_notification
from app.stores import create_incident, get_incident, update_incident
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
    approve_command: str | None = None
    reject_command: str | None = None


class IncidentResponse(BaseModel):
    incident_id: str
    kind: str
    namespace: str
    name: str
    source: str = "manual"
    evidence: str = ""
    answer: str = ""
    action_ids: list[str] = Field(default_factory=list)
    proposed_actions: list[ProposedActionResponse] = Field(default_factory=list)
    notification_status: str = "notification_not_attempted"


app = FastAPI()


def _normalize_incident_payload(
    payload: dict[str, object],
    *,
    source: str = "manual",
    notification_status: str = "notification_not_attempted",
) -> dict[str, object]:
    action_ids = payload.get("action_ids", [])
    if not isinstance(action_ids, list):
        action_ids = []
    proposed_actions = payload.get("proposed_actions", [])
    if not isinstance(proposed_actions, list):
        proposed_actions = []

    return {
        "kind": str(payload.get("kind", "")),
        "namespace": str(payload.get("namespace", "")),
        "name": str(payload.get("name", "")),
        "source": str(payload.get("source", source)),
        "evidence": str(payload.get("evidence", "")),
        "answer": str(payload.get("answer", "")),
        "action_ids": [str(item) for item in action_ids if item is not None],
        "proposed_actions": [item for item in proposed_actions if isinstance(item, dict)],
        "notification_status": str(payload.get("notification_status", notification_status)),
    }


def _normalize_stored_incident(incident: dict[str, object]) -> dict[str, object]:
    return {"incident_id": str(incident["incident_id"]), **_normalize_incident_payload(incident)}


@app.get("/healthz", response_model=HealthzResponse)
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/investigate", response_model=IncidentResponse)
async def investigate(request: InvestigateRequest) -> dict[str, object]:
    if not all([request.kind, request.namespace, request.name]):
        raise HTTPException(status_code=400, detail="kind, namespace, and name are required")
    log_event("http_investigate_received", kind=request.kind, namespace=request.namespace, name=request.name)
    result = await investigate_target(request.kind, request.namespace, request.name, emit_progress=False)
    incident = create_incident(_normalize_incident_payload(result, source="manual"))
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
    return IncidentResponse(**_normalize_stored_incident(incident)).model_dump()


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
async def alertmanager_webhook(payload: AlertmanagerWebhook) -> dict[str, object]:
    kind, namespace, name = _resolve_alert_target(payload)
    log_event("alertmanager_webhook_received", kind=kind, namespace=namespace, name=name)
    result = await investigate_target(kind, namespace, name, emit_progress=False)
    incident = create_incident(_normalize_incident_payload(result, source="alertmanager"))
    attach_actions_to_incident(incident.get("action_ids", []), incident["incident_id"])
    incident["notification_status"] = send_telegram_notification(incident)
    update_incident(incident["incident_id"], {"source": "alertmanager", "notification_status": incident["notification_status"]})
    log_event("alertmanager_webhook_completed", incident_id=incident["incident_id"], kind=kind, namespace=namespace, name=name)
    return IncidentResponse(**_normalize_stored_incident(incident)).model_dump()


@app.get("/incidents/{incident_id}", response_model=IncidentResponse)
async def read_incident(incident_id: str) -> dict[str, object]:
    incident = get_incident(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="incident not found")
    return IncidentResponse(**_normalize_stored_incident(incident)).model_dump()


def run_server(port: int = 8080) -> None:
    log_event("server_starting", port=port)
    start_telegram_polling_thread()
    uvicorn.run(app, host="0.0.0.0", port=port)
