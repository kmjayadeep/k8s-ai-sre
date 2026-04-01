import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.actions import attach_actions_to_incident
from app.investigate import investigate_target
from app.log import log_event
from app.notifier import send_telegram_notification
from app.stores import create_incident, get_incident, list_incidents, update_incident
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


app = FastAPI()

INCIDENT_INSPECTOR_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>k8s-ai-sre Incident Inspector</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f3f4f6;
      --panel: #ffffff;
      --ink: #0f172a;
      --muted: #4b5563;
      --accent: #0f766e;
      --line: #d1d5db;
    }
    body {
      margin: 0;
      background: linear-gradient(130deg, #ecfeff 0%, #f8fafc 40%, #fef9c3 100%);
      color: var(--ink);
      font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
    }
    .shell {
      max-width: 1100px;
      margin: 0 auto;
      padding: 1.25rem;
      display: grid;
      grid-template-columns: 340px 1fr;
      gap: 1rem;
    }
    .panel {
      background: color-mix(in oklab, var(--panel), #ffffff 10%);
      border: 1px solid var(--line);
      border-radius: 0.85rem;
      box-shadow: 0 0.5rem 2rem rgba(2, 6, 23, 0.07);
      overflow: hidden;
    }
    .panel h1, .panel h2 {
      margin: 0;
      padding: 1rem 1rem 0.5rem;
      letter-spacing: 0.02em;
    }
    .subline {
      margin: 0;
      padding: 0 1rem 1rem;
      color: var(--muted);
      font-size: 0.9rem;
    }
    #incident-list {
      max-height: 70vh;
      overflow: auto;
      padding: 0.35rem 0.65rem 1rem;
    }
    .incident-btn {
      width: 100%;
      margin: 0.35rem 0;
      border: 1px solid var(--line);
      border-radius: 0.6rem;
      text-align: left;
      background: #fff;
      padding: 0.65rem 0.75rem;
      color: var(--ink);
      cursor: pointer;
    }
    .incident-btn:hover {
      border-color: var(--accent);
      transform: translateY(-1px);
      transition: 120ms ease;
    }
    .incident-btn.selected {
      border-color: var(--accent);
      box-shadow: inset 0 0 0 1px var(--accent);
      background: #ecfeff;
    }
    .incident-btn .meta {
      margin-top: 0.2rem;
      color: var(--muted);
      font-size: 0.82rem;
    }
    #incident-detail {
      margin: 0;
      padding: 0 1rem 1rem;
      white-space: pre-wrap;
      font-family: "IBM Plex Mono", "SFMono-Regular", monospace;
      font-size: 0.85rem;
      color: #1f2937;
    }
    .empty {
      padding: 1rem;
      color: var(--muted);
    }
    @media (max-width: 850px) {
      .shell {
        grid-template-columns: 1fr;
      }
    }
  </style>
</head>
<body>
  <div class="shell">
    <section class="panel">
      <h1>Incident Feed</h1>
      <p class="subline">Select an incident to inspect.</p>
      <div id="incident-list"></div>
    </section>
    <section class="panel">
      <h2>Incident Detail</h2>
      <p class="subline" id="detail-hint">Choose an incident from the feed.</p>
      <pre id="incident-detail"></pre>
    </section>
  </div>
  <script>
    const listEl = document.getElementById("incident-list");
    const detailEl = document.getElementById("incident-detail");
    const hintEl = document.getElementById("detail-hint");
    let selectedId = null;

    async function loadIncidents() {
      const response = await fetch("/incidents");
      if (!response.ok) {
        listEl.innerHTML = '<div class="empty">Failed to load incidents.</div>';
        return;
      }
      const payload = await response.json();
      const incidents = payload.incidents || [];
      if (!incidents.length) {
        listEl.innerHTML = '<div class="empty">No incidents recorded yet.</div>';
        detailEl.textContent = "";
        hintEl.textContent = "Trigger /investigate or /webhooks/alertmanager to populate this view.";
        return;
      }

      listEl.innerHTML = "";
      for (const incident of incidents) {
        const button = document.createElement("button");
        button.className = "incident-btn";
        button.type = "button";
        button.innerHTML =
          `<strong>${incident.incident_id}</strong>` +
          `<div class="meta">${incident.kind}/${incident.namespace}/${incident.name}</div>`;
        button.addEventListener("click", () => inspectIncident(incident.incident_id));
        if (incident.incident_id === selectedId) {
          button.classList.add("selected");
        }
        listEl.appendChild(button);
      }

      if (!selectedId) {
        await inspectIncident(incidents[0].incident_id);
      }
    }

    async function inspectIncident(incidentId) {
      selectedId = incidentId;
      for (const element of listEl.querySelectorAll(".incident-btn")) {
        const active = element.firstChild && element.firstChild.textContent === incidentId;
        element.classList.toggle("selected", active);
      }
      const response = await fetch(`/incidents/${incidentId}`);
      if (!response.ok) {
        hintEl.textContent = "Incident not found.";
        detailEl.textContent = "";
        return;
      }
      const incident = await response.json();
      hintEl.textContent = `${incident.source} incident for ${incident.kind}/${incident.namespace}/${incident.name}`;
      detailEl.textContent = JSON.stringify(incident, null, 2);
    }

    loadIncidents();
  </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def incident_inspector() -> HTMLResponse:
    return HTMLResponse(content=INCIDENT_INSPECTOR_HTML)


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


def run_server(port: int = 8080) -> None:
    log_event("server_starting", port=port)
    start_telegram_polling_thread()
    uvicorn.run(app, host="0.0.0.0", port=port)
