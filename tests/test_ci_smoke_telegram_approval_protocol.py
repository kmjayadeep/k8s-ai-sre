import json
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs
from unittest.mock import patch

import app.actions as action_service
import app.notifier as notifier
import app.stores.actions as action_store
import app.stores.incidents as incident_store
import app.telegram as telegram


class _FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return b'{"ok": true}'


class TelegramApprovalProtocolSmokeTests(unittest.TestCase):
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

    def _create_incident_with_action(self) -> tuple[dict[str, object], str]:
        action = action_service.propose_action("delete-pod", "ai-sre-demo", "crashy")
        incident = {
            "incident_id": "incident-telegram-protocol",
            "kind": "pod",
            "namespace": "ai-sre-demo",
            "name": "crashy",
            "answer": "Summary: CrashLoopBackOff due to bad sidecar config.",
            "proposed_actions": [action_service.action_metadata(action)],
            "action_ids": [action["id"]],
        }
        action_service.attach_actions_to_incident([action["id"]], incident["incident_id"])
        return incident, action["id"]

    def _render_notification_payload(self, incident: dict[str, object]) -> dict[str, list[str]]:
        with patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "token", "TELEGRAM_CHAT_ID": "123"}, clear=False):
            with patch("app.notifier.urllib.request.urlopen", return_value=_FakeResponse()) as urlopen:
                status = notifier.send_telegram_notification(incident)
        self.assertEqual("Telegram notification sent.", status)
        request = urlopen.call_args.args[0]
        return parse_qs(request.data.decode("utf-8"))

    def test_notifier_uses_protocol_callback_payloads(self) -> None:
        incident, action_id = self._create_incident_with_action()

        payload = self._render_notification_payload(incident)
        reply_markup = json.loads(payload["reply_markup"][0])
        buttons = reply_markup["inline_keyboard"][0]
        self.assertEqual(f"approve:{action_id}", buttons[0]["callback_data"])
        self.assertEqual(f"reject:{action_id}", buttons[1]["callback_data"])

    def test_callback_executes_action_and_acknowledges_operator(self) -> None:
        incident, action_id = self._create_incident_with_action()
        payload = self._render_notification_payload(incident)
        callback_data = json.loads(payload["reply_markup"][0])["inline_keyboard"][0][0]["callback_data"]
        update = {
            "ok": True,
            "result": [
                {
                    "update_id": 41,
                    "callback_query": {
                        "id": "cb-approve-1",
                        "data": callback_data,
                        "message": {"chat": {"id": "123"}},
                    },
                }
            ],
        }

        with patch("app.actions.delete_pod", return_value='pod "crashy" deleted'):
            with patch("app.telegram._telegram_token", return_value="token"):
                with patch("app.telegram._telegram_api", return_value=update):
                    with patch("app.telegram._allowed_chat_ids", return_value=set()):
                        with patch("app.telegram._save_offset"):
                            with patch("app.telegram._send_message", return_value="Telegram reply sent.") as send_message:
                                with patch(
                                    "app.telegram._answer_callback_query",
                                    return_value="Telegram callback acknowledged.",
                                ) as ack:
                                    result = telegram.poll_telegram_updates_once()

        self.assertEqual("Processed 1 Telegram command(s).", result)
        send_message.assert_called_once_with("123", f'Incident incident-telegram-protocol\npod "crashy" deleted')
        ack.assert_called_once_with("cb-approve-1", f'Incident incident-telegram-protocol\npod "crashy" deleted')
        stored = action_store.get_action(action_id)
        self.assertEqual("approved", stored["status"])

    def test_callback_marks_expired_actions_and_still_acks(self) -> None:
        incident, action_id = self._create_incident_with_action()
        action_store.update_action(action_id, {"expires_at": (datetime.now(UTC) - timedelta(minutes=1)).isoformat()})
        payload = self._render_notification_payload(incident)
        callback_data = json.loads(payload["reply_markup"][0])["inline_keyboard"][0][0]["callback_data"]
        update = {
            "ok": True,
            "result": [
                {
                    "update_id": 42,
                    "callback_query": {
                        "id": "cb-expired-1",
                        "data": callback_data,
                        "message": {"chat": {"id": "123"}},
                    },
                }
            ],
        }

        with patch("app.telegram._telegram_token", return_value="token"):
            with patch("app.telegram._telegram_api", return_value=update):
                with patch("app.telegram._allowed_chat_ids", return_value=set()):
                    with patch("app.telegram._save_offset"):
                        with patch("app.telegram._send_message", return_value="Telegram reply sent.") as send_message:
                            with patch(
                                "app.telegram._answer_callback_query",
                                return_value="Telegram callback acknowledged.",
                            ) as ack:
                                result = telegram.poll_telegram_updates_once()

        expected_reply = f"Incident incident-telegram-protocol\nAction {action_id} has expired."
        self.assertEqual("Processed 1 Telegram command(s).", result)
        send_message.assert_called_once_with("123", expected_reply)
        ack.assert_called_once_with("cb-expired-1", expected_reply)
        stored = action_store.get_action(action_id)
        self.assertEqual("expired", stored["status"])


if __name__ == "__main__":
    unittest.main()
