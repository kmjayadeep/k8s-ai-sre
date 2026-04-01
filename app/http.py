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


app = FastAPI()


@app.get("/healthz", response_model=HealthzResponse)
async def healthz() -> HealthzResponse:
    return HealthzResponse(status="ok")


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


@app.get("/incidents/{incident_id}", response_model=IncidentResponse)
async def read_incident(incident_id: str) -> IncidentResponse:
    incident = get_incident(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="incident not found")
    return IncidentResponse.model_validate(incident)


def run_server(port: int = 8080) -> None:
    log_event("server_starting", port=port)
    start_telegram_polling_thread()
    uvicorn.run(app, host="0.0.0.0", port=port)
