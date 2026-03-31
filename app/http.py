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
    action_id: str = "unknown"
    action_type: str = "unknown"
    namespace: str = "unknown"
    name: str = "unknown"
    params: dict[str, object] = Field(default_factory=dict)
    expires_at: str | None = None
    approve_command: str | None = None
    reject_command: str | None = None


class IncidentResponse(BaseModel):
    incident_id: str = "unknown"
    kind: str = "unknown"
    namespace: str = "unknown"
    name: str = "unknown"
    evidence: str = ""
    answer: str = ""
    source: str = "manual"
    notification_status: str = ""
    proposed_actions: list[ProposedActionResponse] = Field(default_factory=list)
    action_ids: list[str] = Field(default_factory=list)


app = FastAPI()


def _normalize_incident_payload(payload: dict[str, object], default_source: str = "manual") -> IncidentResponse:
    raw_actions = payload.get("proposed_actions")
    normalized_actions = []
    if isinstance(raw_actions, list):
        for action in raw_actions:
            if not isinstance(action, dict):
                continue
            normalized_actions.append(
                {
                    "action_id": str(action.get("action_id", "unknown")),
                    "action_type": str(action.get("action_type", "unknown")),
                    "namespace": str(action.get("namespace", "unknown")),
                    "name": str(action.get("name", "unknown")),
                    "params": action.get("params", {}),
                    "expires_at": action.get("expires_at"),
                    "approve_command": action.get("approve_command"),
                    "reject_command": action.get("reject_command"),
                }
            )

    raw_action_ids = payload.get("action_ids")
    normalized_action_ids = []
    if isinstance(raw_action_ids, list):
        normalized_action_ids = [str(action_id) for action_id in raw_action_ids]

    source = str(payload.get("source") or default_source)
    return IncidentResponse.model_validate(
        {
            "incident_id": str(payload.get("incident_id", "unknown")),
            "kind": str(payload.get("kind", "unknown")),
            "namespace": str(payload.get("namespace", "unknown")),
            "name": str(payload.get("name", "unknown")),
            "evidence": str(payload.get("evidence", "")),
            "answer": str(payload.get("answer", "")),
            "source": source,
            "notification_status": str(payload.get("notification_status", "")),
            "proposed_actions": normalized_actions,
            "action_ids": normalized_action_ids,
        }
    )


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
    return _normalize_incident_payload(incident)


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
    return _normalize_incident_payload(incident, default_source="alertmanager")


@app.get("/incidents/{incident_id}", response_model=IncidentResponse)
async def read_incident(incident_id: str) -> IncidentResponse:
    incident = get_incident(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="incident not found")
    return _normalize_incident_payload(incident)


def run_server(port: int = 8080) -> None:
    log_event("server_starting", port=port)
    start_telegram_polling_thread()
    uvicorn.run(app, host="0.0.0.0", port=port)
