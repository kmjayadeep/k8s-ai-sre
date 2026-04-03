import tempfile
import unittest
from asyncio import run
from pathlib import Path
from unittest.mock import AsyncMock, patch

import app.actions as action_service
import app.stores.actions as action_store
import app.stores.incidents as incident_store
from fastapi import HTTPException

from app.http import (
    AlertmanagerWebhook,
    InvestigateRequest,
    alertmanager_webhook,
    approve_action_http,
    incident_inspector,
    investigate,
    metrics,
    read_incident,
    read_incidents,
    reject_action_http,
)
from app.metrics import reset_metrics_for_tests

INCIDENT_RESPONSE_KEYS = {
    "incident_id",
    "kind",
    "namespace",
    "name",
    "answer",
    "evidence",
    "source",
    "action_ids",
    "proposed_actions",
    "notification_status",
}

PROPOSED_ACTION_RESPONSE_KEYS = {
    "action_id",
    "action_type",
    "namespace",
    "name",
    "params",
    "expires_at",
    "approve_command",
    "reject_command",
}


class HttpIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_metrics_for_tests()
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.incident_path = Path(self.tempdir.name) / "incidents.json"
        self.action_path = Path(self.tempdir.name) / "actions.json"
        self.incident_patch = patch.object(incident_store, "INCIDENT_STORE_PATH", self.incident_path)
        self.action_patch = patch.object(action_store, "ACTION_STORE_PATH", self.action_path)
        self.incident_patch.start()
        self.action_patch.start()
        self.addCleanup(self.incident_patch.stop)
        self.addCleanup(self.action_patch.stop)

    def test_investigate_creates_incident_with_notification_status(self) -> None:
        result = {
            "kind": "deployment",
            "namespace": "ai-sre-demo",
            "name": "bad-deploy",
            "answer": "Summary: image pull failure",
            "proposed_actions": [{"action_id": "abc12345", "action_type": "rollout-restart", "namespace": "ai-sre-demo", "name": "bad-deploy"}],
            "action_ids": ["abc12345"],
        }
        with patch("app.http.investigate_target", new=AsyncMock(return_value=result)):
            with patch("app.http.send_telegram_notification", return_value="Telegram notification sent."):
                body = run(investigate(InvestigateRequest(kind="deployment", namespace="ai-sre-demo", name="bad-deploy"))).model_dump()

        self.assertEqual("Telegram notification sent.", body["notification_status"])
        self.assertEqual(INCIDENT_RESPONSE_KEYS, set(body.keys()))
        self.assertEqual(PROPOSED_ACTION_RESPONSE_KEYS, set(body["proposed_actions"][0].keys()))
        stored = run(read_incident(body["incident_id"])).model_dump()
        self.assertEqual(["abc12345"], stored["action_ids"])
        self.assertEqual("Telegram notification sent.", stored["notification_status"])
        self.assertEqual(INCIDENT_RESPONSE_KEYS, set(stored.keys()))
        self.assertEqual(PROPOSED_ACTION_RESPONSE_KEYS, set(stored["proposed_actions"][0].keys()))

    def test_alertmanager_webhook_resolves_target_and_persists_source(self) -> None:
        result = {
            "kind": "deployment",
            "namespace": "ai-sre-demo",
            "name": "bad-deploy",
            "answer": "Summary: image pull failure",
            "proposed_actions": [],
            "action_ids": [],
        }
        with patch("app.http.investigate_target", new=AsyncMock(return_value=result)):
            with patch("app.http.send_telegram_notification", return_value="Telegram notification sent."):
                body = run(
                    alertmanager_webhook(
                        AlertmanagerWebhook(commonLabels={"namespace": "ai-sre-demo", "deployment": "bad-deploy"}, alerts=[])
                    )
                ).model_dump()

        self.assertEqual("alertmanager", body["source"])
        self.assertEqual(INCIDENT_RESPONSE_KEYS, set(body.keys()))
        stored = run(read_incident(body["incident_id"])).model_dump()
        self.assertEqual("alertmanager", stored["source"])
        self.assertEqual(INCIDENT_RESPONSE_KEYS, set(stored.keys()))
    def test_alertmanager_to_approval_executes_linked_action(self) -> None:
        action = action_service.propose_action("delete-pod", "ai-sre-demo", "crashy")
        result = {
            "kind": "pod",
            "namespace": "ai-sre-demo",
            "name": "crashy",
            "answer": "Summary: CrashLoopBackOff from bad sidecar config",
            "proposed_actions": [action_service.action_metadata(action)],
            "action_ids": [action["id"]],
        }
        with patch("app.http.investigate_target", new=AsyncMock(return_value=result)):
            with patch("app.http.send_telegram_notification", return_value="Telegram notification sent."):
                body = run(
                    alertmanager_webhook(
                        AlertmanagerWebhook(commonLabels={"namespace": "ai-sre-demo", "pod": "crashy"}, alerts=[])
                    )
                ).model_dump()

        stored_incident = run(read_incident(body["incident_id"])).model_dump()
        self.assertEqual([action["id"]], stored_incident["action_ids"])
        self.assertEqual("alertmanager", stored_incident["source"])

        stored_action = action_store.get_action(action["id"])
        self.assertEqual(body["incident_id"], stored_action["incident_id"])
        self.assertEqual("pending", stored_action["status"])

        with patch("app.actions.delete_pod", return_value='pod "crashy" deleted'):
            approval_reply = action_service.approve_action(action["id"])

        self.assertIn(f"Incident {body['incident_id']}", approval_reply)
        self.assertIn('pod "crashy" deleted', approval_reply)
        self.assertEqual("approved", action_store.get_action(action["id"])["status"])

    def test_read_incident_normalizes_legacy_payload_shape(self) -> None:
        incident = incident_store.create_incident(
            {
                "kind": "pod",
                "namespace": "ai-sre-demo",
                "name": "crashy",
                "proposed_actions": [{"action_id": "f314980d", "action_type": "delete-pod"}],
            }
        )

        stored = run(read_incident(incident["incident_id"])).model_dump()
        self.assertEqual("manual", stored["source"])
        self.assertEqual(["f314980d"], stored["action_ids"])
        self.assertEqual("/approve f314980d", stored["proposed_actions"][0]["approve_command"])

    def test_read_incidents_returns_incidents_sorted_by_id_desc(self) -> None:
        first = incident_store.create_incident({"kind": "pod", "namespace": "ai-sre-demo", "name": "first"})
        second = incident_store.create_incident({"kind": "deployment", "namespace": "ai-sre-demo", "name": "second"})

        payload = run(read_incidents()).model_dump()
        returned_ids = [item["incident_id"] for item in payload["incidents"]]
        expected_ids = sorted([first["incident_id"], second["incident_id"]], reverse=True)

        self.assertEqual({"incidents"}, set(payload.keys()))
        self.assertEqual(2, len(payload["incidents"]))
        self.assertEqual(expected_ids, returned_ids)
        self.assertTrue(all(set(item.keys()) == INCIDENT_RESPONSE_KEYS for item in payload["incidents"]))

    def test_incident_inspector_returns_html(self) -> None:
        response = run(incident_inspector())

        self.assertIn("text/html", response.media_type)
        self.assertIn("Incident Feed", response.body.decode("utf-8"))

    def test_metrics_endpoint_includes_investigation_and_approval_signals(self) -> None:
        result = {
            "kind": "deployment",
            "namespace": "ai-sre-demo",
            "name": "bad-deploy",
            "answer": "Summary: image pull failure",
            "proposed_actions": [{"action_id": "abc12345", "action_type": "rollout-restart", "namespace": "ai-sre-demo", "name": "bad-deploy"}],
            "action_ids": ["abc12345"],
        }
        with patch("app.http.investigate_target", new=AsyncMock(return_value=result)):
            with patch("app.http.send_telegram_notification", return_value="Telegram notification sent."):
                run(investigate(InvestigateRequest(kind="deployment", namespace="ai-sre-demo", name="bad-deploy")))

        action = action_service.propose_action("delete-pod", "ai-sre-demo", "crashy")
        with patch.dict("os.environ", {"OPERATOR_API_TOKEN": "test-token"}, clear=False):
            with patch("app.actions.delete_pod", return_value='pod "crashy" deleted'):
                run(approve_action_http(action["id"], authorization="Bearer test-token", operator_id="operator-1"))

        body = run(metrics()).body.decode("utf-8")
        self.assertIn("k8s_ai_sre_investigation_latency_seconds_count", body)
        self.assertIn("k8s_ai_sre_action_proposals_total", body)
        self.assertIn('k8s_ai_sre_action_execution_outcomes_total{status="approved"}', body)
        self.assertIn("k8s_ai_sre_approval_latency_seconds_count", body)

    def test_operator_http_approve_executes_action_when_token_valid(self) -> None:
        action = action_service.propose_action("delete-pod", "ai-sre-demo", "crashy")

        with patch.dict("os.environ", {"OPERATOR_API_TOKEN": "test-token"}, clear=False):
            with patch("app.actions.delete_pod", return_value='pod "crashy" deleted'):
                body = run(
                    approve_action_http(
                        action["id"],
                        authorization="Bearer test-token",
                        operator_id="automation-kind",
                    )
                ).model_dump()

        self.assertEqual(action["id"], body["action_id"])
        self.assertEqual("approved", body["status"])
        self.assertIn('pod "crashy" deleted', body["message"])
        stored = action_store.get_action(action["id"])
        self.assertEqual("automation-kind", stored["approved_by"])
        self.assertEqual("http_api", stored["approval_source"])

    def test_operator_http_reject_updates_status_when_token_valid(self) -> None:
        action = action_service.propose_action("delete-pod", "ai-sre-demo", "crashy")

        with patch.dict("os.environ", {"OPERATOR_API_TOKEN": "test-token"}, clear=False):
            body = run(
                reject_action_http(
                    action["id"],
                    authorization="Bearer test-token",
                    operator_id="operator-42",
                )
            ).model_dump()

        self.assertEqual(action["id"], body["action_id"])
        self.assertEqual("rejected", body["status"])
        self.assertIn(f"Rejected action {action['id']}.", body["message"])

    def test_operator_http_approve_requires_token(self) -> None:
        action = action_service.propose_action("delete-pod", "ai-sre-demo", "crashy")

        with patch.dict("os.environ", {"OPERATOR_API_TOKEN": "test-token"}, clear=False):
            with self.assertRaises(HTTPException) as raised:
                run(approve_action_http(action["id"], authorization=None))

        self.assertEqual(401, raised.exception.status_code)
        self.assertEqual(
            {"code": "operator_token_missing", "message": "missing operator token"},
            raised.exception.detail,
        )

    def test_operator_http_approve_rejects_invalid_token(self) -> None:
        action = action_service.propose_action("delete-pod", "ai-sre-demo", "crashy")

        with patch.dict("os.environ", {"OPERATOR_API_TOKEN": "test-token"}, clear=False):
            with self.assertRaises(HTTPException) as raised:
                run(approve_action_http(action["id"], authorization="Bearer wrong", operator_id="operator-1"))

        self.assertEqual(403, raised.exception.status_code)
        self.assertEqual(
            {"code": "operator_token_invalid", "message": "invalid operator token"},
            raised.exception.detail,
        )

    def test_operator_http_approve_requires_operator_identity_header(self) -> None:
        action = action_service.propose_action("delete-pod", "ai-sre-demo", "crashy")

        with patch.dict("os.environ", {"OPERATOR_API_TOKEN": "test-token"}, clear=False):
            with self.assertRaises(HTTPException) as raised:
                run(approve_action_http(action["id"], authorization="Bearer test-token", operator_id=None))

        self.assertEqual(400, raised.exception.status_code)
        self.assertEqual(
            {
                "code": "operator_identity_missing",
                "message": "missing operator identity header (X-Operator-Id)",
            },
            raised.exception.detail,
        )

    def test_operator_http_approve_requires_configured_operator_token(self) -> None:
        action = action_service.propose_action("delete-pod", "ai-sre-demo", "crashy")

        with patch.dict("os.environ", {"OPERATOR_API_TOKEN": ""}, clear=False):
            with self.assertRaises(HTTPException) as raised:
                run(approve_action_http(action["id"], authorization="Bearer test-token", operator_id="operator-1"))

        self.assertEqual(503, raised.exception.status_code)
        self.assertEqual(
            {
                "code": "operator_api_not_configured",
                "message": "operator API approval endpoint is not configured",
            },
            raised.exception.detail,
        )

    def test_operator_http_approve_returns_action_not_found_error_shape(self) -> None:
        with patch.dict("os.environ", {"OPERATOR_API_TOKEN": "test-token"}, clear=False):
            with self.assertRaises(HTTPException) as raised:
                run(
                    approve_action_http(
                        "missing-action-id",
                        authorization="Bearer test-token",
                        operator_id="operator-1",
                    )
                )

        self.assertEqual(404, raised.exception.status_code)
        self.assertEqual(
            {"code": "action_not_found", "message": "action not found"},
            raised.exception.detail,
        )
