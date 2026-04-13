import base64
import unittest
from asyncio import run

from starlette.requests import Request
from starlette.responses import Response

import app.ui.auth_middleware as auth_middleware
from app.ui.auth_middleware import InspectorAuthMiddleware


class InspectorAuthMiddlewareTests(unittest.TestCase):
    def setUp(self) -> None:
        self._original_config = auth_middleware._INSPECTOR_AUTH_CONFIG
        auth_middleware._INSPECTOR_AUTH_CONFIG = "operator:secret"

    def tearDown(self) -> None:
        auth_middleware._INSPECTOR_AUTH_CONFIG = self._original_config

    def _request(self, path: str, headers: list[tuple[bytes, bytes]] | None = None) -> Request:
        scope = {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": path,
            "raw_path": path.encode("ascii"),
            "query_string": b"",
            "headers": headers or [],
            "client": ("127.0.0.1", 12345),
            "server": ("testserver", 80),
        }
        return Request(scope)

    def _middleware(self) -> InspectorAuthMiddleware:
        return InspectorAuthMiddleware(app=lambda scope, receive, send: None)

    def test_unprotected_route_passes_without_auth(self) -> None:
        request = self._request("/healthz")

        async def call_next(_: Request) -> Response:
            return Response(content=b"ok", status_code=200)

        response = run(self._middleware().dispatch(request, call_next))
        self.assertEqual(200, response.status_code)

    def test_protected_route_requires_credentials(self) -> None:
        request = self._request("/incidents")

        async def call_next(_: Request) -> Response:
            return Response(content=b"ok", status_code=200)

        response = run(self._middleware().dispatch(request, call_next))
        self.assertEqual(401, response.status_code)
        self.assertIn("Basic realm=", response.headers.get("WWW-Authenticate", ""))

    def test_protected_route_accepts_valid_authorization_header(self) -> None:
        token = base64.b64encode(b"operator:secret")
        request = self._request("/actions", headers=[(b"authorization", b"Basic " + token)])

        async def call_next(_: Request) -> Response:
            return Response(content=b"ok", status_code=200)

        response = run(self._middleware().dispatch(request, call_next))
        self.assertEqual(200, response.status_code)

    def test_protected_route_accepts_valid_cookie(self) -> None:
        token = base64.b64encode(b"operator:secret")
        request = self._request("/incidents", headers=[(b"cookie", b"inspector_auth=" + token)])

        async def call_next(_: Request) -> Response:
            return Response(content=b"ok", status_code=200)

        response = run(self._middleware().dispatch(request, call_next))
        self.assertEqual(200, response.status_code)


if __name__ == "__main__":
    unittest.main()
