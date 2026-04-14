import json
import unittest
from urllib.parse import parse_qs
from unittest.mock import patch

from app.notifier import send_telegram_notification


class TelegramNotifierTests(unittest.TestCase):
    def test_send_notification_includes_inline_buttons_for_actions(self) -> None:
        incident = {
            "incident_id": "incident-123",
            "kind": "pod",
            "namespace": "ai-sre-demo",
            "name": "crashy",
            "answer": "summary",
            "proposed_actions": [
                {"action_id": "abc12345", "action_type": "delete-pod", "namespace": "ai-sre-demo", "name": "crashy"}
            ],
        }

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b'{"ok": true}'

        with patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "token", "TELEGRAM_CHAT_ID": "123"}, clear=False):
            with patch("app.notifier.urllib.request.urlopen", return_value=FakeResponse()) as urlopen:
                result = send_telegram_notification(incident)

        self.assertEqual("Telegram notification sent.", result)
        request = urlopen.call_args.args[0]
        parsed = parse_qs(request.data.decode("utf-8"))
        self.assertEqual("123", parsed["chat_id"][0])
        self.assertIn("Incident incident-123", parsed["text"][0])
        self.assertIn("Target: pod ai-sre-demo/crashy", parsed["text"][0])
        reply_markup = json.loads(parsed["reply_markup"][0])
        self.assertEqual("Approve abc12345", reply_markup["inline_keyboard"][0][0]["text"])
        self.assertEqual("approve:abc12345", reply_markup["inline_keyboard"][0][0]["callback_data"])

    def test_send_notification_omits_inline_buttons_when_no_actions(self) -> None:
        incident = {
            "incident_id": "incident-456",
            "kind": "deployment",
            "namespace": "ai-sre-demo",
            "name": "bad-deploy",
            "answer": "summary",
            "proposed_actions": [],
        }

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b'{"ok": true}'

        with patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "token", "TELEGRAM_CHAT_ID": "123"}, clear=False):
            with patch("app.notifier.urllib.request.urlopen", return_value=FakeResponse()) as urlopen:
                result = send_telegram_notification(incident)

        self.assertEqual("Telegram notification sent.", result)
        request = urlopen.call_args.args[0]
        parsed = parse_qs(request.data.decode("utf-8"))
        self.assertNotIn("reply_markup", parsed)

    def test_send_notification_includes_cluster_line(self) -> None:
        incident = {
            "incident_id": "incident-789",
            "kind": "deployment",
            "namespace": "ai-sre-demo",
            "name": "bad-deploy",
            "answer": "<think>internal chain of thought</think>\nSummary: image pull failure",
            "proposed_actions": [],
        }

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b'{"ok": true}'

        env = {"TELEGRAM_BOT_TOKEN": "token", "TELEGRAM_CHAT_ID": "123", "K8S_CLUSTER_NAME": "kind-local"}
        with patch.dict("os.environ", env, clear=False):
            with patch("app.notifier.urllib.request.urlopen", return_value=FakeResponse()) as urlopen:
                result = send_telegram_notification(incident)

        self.assertEqual("Telegram notification sent.", result)
        request = urlopen.call_args.args[0]
        parsed = parse_qs(request.data.decode("utf-8"))
        self.assertIn("Cluster: kind-local", parsed["text"][0])
        self.assertIn("<think>internal chain of thought</think>", parsed["text"][0])
