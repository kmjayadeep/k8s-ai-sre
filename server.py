import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from investigate import investigate_target


class InvestigateRequest(BaseModel):
    kind: str
    namespace: str
    name: str


class AlertmanagerAlert(BaseModel):
    labels: dict[str, str] = {}


class AlertmanagerWebhook(BaseModel):
    commonLabels: dict[str, str] = {}
    alerts: list[AlertmanagerAlert] = []


app = FastAPI()


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/investigate")
async def investigate(request: InvestigateRequest) -> dict[str, str]:
    if not all([request.kind, request.namespace, request.name]):
        raise HTTPException(status_code=400, detail="kind, namespace, and name are required")
    return await investigate_target(request.kind, request.namespace, request.name, emit_progress=False)


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


@app.post("/webhooks/alertmanager")
async def alertmanager_webhook(payload: AlertmanagerWebhook) -> dict[str, str]:
    kind, namespace, name = _resolve_alert_target(payload)
    result = await investigate_target(kind, namespace, name, emit_progress=False)
    result["source"] = "alertmanager"
    return result


def run_server(port: int = 8080) -> None:
    uvicorn.run(app, host="0.0.0.0", port=port)
