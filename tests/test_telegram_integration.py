import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import app.actions as action_service
import app.stores.actions as action_store
import app.stores.incidents as incident_store
import app.telegram as telegram


class TelegramIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
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

    def test_incident_command_includes_action_ids(self) -> None:
        incident = incident_store.create_incident(
            {
                "kind": "deployment",
                "namespace": "ai-sre-demo",
                "name": "bad-deploy",
                "answer": (
                    "<thinking>verbose internal reasoning should be hidden</thinking>\n"
                    "Summary: image pull failure blocks deployment rollout.\n"
                    "Most likely cause: deployment references an image tag that does not exist.\n"
                    "Confidence: high"
                ),
                "proposed_actions": [{"action_id": "abc12345", "action_type": "rollout-restart", "namespace": "ai-sre-demo", "name": "bad-deploy"}],
                "action_ids": ["abc12345"],
            }
        )

        reply = telegram._handle_command(f"/incident {incident['incident_id']}")

        self.assertIn("Quick summary: image pull failure blocks deployment rollout.", reply)
        self.assertIn("Root cause: deployment references an image tag that does not exist.", reply)
        self.assertIn("Action items:", reply)
        self.assertIn("abc12345", reply)
        self.assertNotIn("<thinking>", reply)

    def test_status_command_includes_quick_summary_line(self) -> None:
        incident = incident_store.create_incident(
            {
                "kind": "pod",
                "namespace": "ai-sre-demo",
                "name": "crashy",
                "answer": "Summary: pod is crash-looping due to startup probe failures.",
                "action_ids": ["abc12345"],
            }
        )

        reply = telegram._handle_command(f"/status {incident['incident_id']}")
        self.assertIn("Quick summary: pod is crash-looping due to startup probe failures.", reply)

    def test_incident_command_includes_cluster_when_configured(self) -> None:
        incident = incident_store.create_incident(
            {
                "kind": "deployment",
                "namespace": "ai-sre-demo",
                "name": "bad-deploy",
                "answer": "<thinking>scratch pad</thinking>\nFinal summary",
                "proposed_actions": [],
                "action_ids": [],
            }
        )

        with patch.dict("os.environ", {"K8S_CLUSTER_NAME": "kind-dev"}, clear=False):
            reply = telegram._handle_command(f"/incident {incident['incident_id']}")

        self.assertIn("Cluster: kind-dev", reply)
        self.assertIn("Quick summary: Final summary", reply)
        self.assertNotIn("<thinking>scratch pad</thinking>", reply)

    def test_approve_command_executes_pending_action(self) -> None:
        action = action_service.propose_action("delete-pod", "ai-sre-demo", "crashy")
        action_service.attach_actions_to_incident([action["id"]], "incident-123")

        with patch("app.actions.delete_pod", return_value='pod "crashy" deleted'):
            reply = telegram._handle_command(f"/approve {action['id']}")

        self.assertIn("Incident incident-123", reply)
        self.assertIn('pod "crashy" deleted', reply)
        stored = action_store.get_action(action["id"])
        self.assertEqual("approved", stored["status"])

    def test_poll_replies_with_operator_friendly_error_on_command_failure(self) -> None:
        update_body = {
            "ok": True,
            "result": [
                {
                    "update_id": 123,
                    "message": {
                        "chat": {"id": "777"},
                        "text": "/incident abc123",
                    },
                }
            ],
        }

        with patch("app.telegram._telegram_token", return_value="token"):
            with patch("app.telegram._telegram_api", return_value=update_body):
                with patch("app.telegram._allowed_chat_ids", return_value=set()):
                    with patch("app.telegram._handle_command", side_effect=RuntimeError("boom")):
                        with patch("app.telegram._send_message", return_value="Telegram reply sent.") as send_message:
                            result = telegram.poll_telegram_updates_once()

        self.assertEqual("Processed 1 Telegram command(s).", result)
        send_message.assert_called_once_with(
            "777",
            "[telegram_command_execution_failed] Command failed due to an internal error. Please retry and check service logs.",
        )

    def test_approve_command_marks_expired_action_in_service_path(self) -> None:
        action = action_service.propose_action("delete-pod", "ai-sre-demo", "crashy")
        action_store.update_action(
            action["id"],
            {"expires_at": (datetime.now(UTC) - timedelta(minutes=1)).isoformat()},
        )

        reply = telegram._handle_command(f"/approve {action['id']}")

        self.assertIn(f"Action {action['id']} has expired.", reply)
        stored = action_store.get_action(action["id"])
        self.assertEqual("expired", stored["status"])

    def test_poll_updates_ignores_unauthorized_chat_commands(self) -> None:
        body = {
            "ok": True,
            "result": [{"update_id": 10, "message": {"chat": {"id": 222}, "text": "/status incident-123"}}],
        }
        with patch("app.telegram._telegram_token", return_value="token"):
            with patch("app.telegram._telegram_api", return_value=body):
                with patch("app.telegram._allowed_chat_ids", return_value={"111"}):
                    with patch("app.telegram._send_message") as send_message:
                        result = telegram.poll_telegram_updates_once()

        self.assertEqual("Processed 0 Telegram command(s).", result)
        send_message.assert_not_called()

    def test_callback_approval_persists_operator_attribution_and_source(self) -> None:
        action = action_service.propose_action("delete-pod", "ai-sre-demo", "crashy")
        body = {
            "ok": True,
            "result": [
                {
                    "update_id": 42,
                    "callback_query": {
                        "id": "cb-42",
                        "from": {"id": 555, "username": "alice"},
                        "data": f"approve:{action['id']}",
                        "message": {"chat": {"id": 123}},
                    },
                }
            ],
        }

        with patch("app.telegram._telegram_token", return_value="token"):
            with patch("app.telegram._telegram_api", return_value=body):
                with patch("app.telegram._allowed_chat_ids", return_value=set()):
                    with patch("app.telegram._save_offset"):
                        with patch("app.actions.delete_pod", return_value='pod "crashy" deleted'):
                            with patch("app.telegram._send_message", return_value="Telegram reply sent."):
                                with patch(
                                    "app.telegram._answer_callback_query",
                                    return_value="Telegram callback acknowledged.",
                                ):
                                    result = telegram.poll_telegram_updates_once()

        self.assertEqual("Processed 1 Telegram command(s).", result)
        stored = action_store.get_action(action["id"])
        self.assertEqual("approved", stored["status"])
        self.assertEqual("telegram:alice", stored["approved_by"])
        self.assertEqual("telegram_callback", stored["approval_source"])
