import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from investigate import investigate_target


class InvestigateRequest(BaseModel):
    kind: str
    namespace: str
    name: str


app = FastAPI()


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/investigate")
async def investigate(request: InvestigateRequest) -> dict[str, str]:
    if not all([request.kind, request.namespace, request.name]):
        raise HTTPException(status_code=400, detail="kind, namespace, and name are required")
    return await investigate_target(request.kind, request.namespace, request.name, emit_progress=False)


def run_server(port: int = 8080) -> None:
    uvicorn.run(app, host="0.0.0.0", port=port)
