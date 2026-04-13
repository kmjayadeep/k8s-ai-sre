import base64
import hmac
import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


_INSPECTOR_AUTH_CONFIG: str | None = None


def load_inspector_auth() -> None:
    global _INSPECTOR_AUTH_CONFIG
    _INSPECTOR_AUTH_CONFIG = os.getenv("INSPECTOR_BASIC_AUTH", "").strip() or None


def _parse_basic(token: str) -> tuple[str, str] | None:
    try:
        decoded = base64.b64decode(token).decode("ascii")
        if ":" not in decoded:
            return None
        username, password = decoded.split(":", 1)
        return username, password
    except Exception:
        return None


def _parse_configured_auth(raw: str | None) -> tuple[str, str] | None:
    if raw is None or ":" not in raw:
        return None
    username, password = raw.split(":", 1)
    return username, password


class InspectorAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if _INSPECTOR_AUTH_CONFIG is None:
            return await call_next(request)

        # Only protect the UI and incident/action API routes
        path = request.url.path
        is_protected = (
            path == "/"
            or path.startswith("/incidents")
            or path.startswith("/actions")
        )
        if not is_protected:
            return await call_next(request)

        configured = _parse_configured_auth(_INSPECTOR_AUTH_CONFIG)
        if configured is None:
            return _login_challenge()

        token = None
        authorization = request.headers.get("Authorization", "")
        if authorization.startswith("Basic "):
            token = authorization[6:].strip()
        else:
            token = (request.cookies.get("inspector_auth") or "").strip() or None

        if token is None:
            return _login_challenge()

        parsed = _parse_basic(token)
        if parsed is None:
            return _login_challenge()

        expected_username, expected_password = configured
        actual_username, actual_password = parsed
        if not (
            hmac.compare_digest(actual_username, expected_username)
            and hmac.compare_digest(actual_password, expected_password)
        ):
            return _login_challenge()

        return await call_next(request)


def _login_challenge() -> Response:
    from starlette.responses import Response

    body = b"<!doctype html><html><head><title>k8s-ai-sre</title></head><body style='font-family:Manrope,sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;background:#f8fafc'><div style='text-align:center;padding:2rem;border:1px solid #e5e7eb;border-radius:16px;background:#fff;max-width:360px'><h2 style='margin:0 0 0.5rem'>k8s-ai-sre</h2><p style='color:#6b7280;margin:0 0 1.5rem'>Authentication required</p><form id='f' style='display:grid;gap:0.75rem'><input id='u' type='text' placeholder='Username' autocomplete='username' style='padding:0.55rem 0.75rem;border:1px solid #d1d5db;border-radius:8px;font-size:0.95rem' required/><input id='p' type='password' placeholder='Password' style='padding:0.55rem 0.75rem;border:1px solid #d1d5db;border-radius:8px;font-size:0.95rem' required/><button type='submit' style='padding:0.55rem;border-radius:8px;border:none;background:#0f766e;color:#fff;font-weight:600;cursor:pointer'>Sign In</button></form><p id='e' style='color:#dc2626;font-size:0.85rem;margin:0.5rem 0 0;display:none'>Invalid credentials</p><script>document.getElementById('f').addEventListener('submit',function(e){e.preventDefault();var btoa=btoa(document.getElementById('u').value+':'+document.getElementById('p').value);document.cookie='inspector_auth='+btoa+';path=/;max-age=3600';location.reload();});</script></div></body></html>"
    return Response(
        content=body,
        media_type="text/html",
        headers={"WWW-Authenticate": "Basic realm=\"k8s-ai-sre\"", "Cache-Control": "no-store"},
        status_code=401,
    )
