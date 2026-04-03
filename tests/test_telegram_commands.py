import unittest
from os import environ
from unittest.mock import MagicMock
from unittest.mock import patch

import app.telegram as telegram


class TelegramCommandParsingTests(unittest.TestCase):
    def test_approve_command_strips_bot_mention(self) -> None:
        with patch("app.telegram.approve_action", return_value="ok") as approve_action:
            reply = telegram._handle_command("/approve@k8s_ai_sre_bot f314980d")

        self.assertEqual("ok", reply)
        approve_action.assert_called_once_with("f314980d", approver_id="unknown", approval_source="telegram")

    def test_reject_command_strips_bot_mention(self) -> None:
        with patch("app.telegram.reject_action", return_value="rejected") as reject_action:
            reply = telegram._handle_command("/reject@k8s_ai_sre_bot f314980d")

        self.assertEqual("rejected", reply)
        reject_action.assert_called_once_with("f314980d", approver_id="unknown", approval_source="telegram")

    def test_incident_command_without_argument_returns_usage(self) -> None:
        reply = telegram._handle_command("/incident")
        self.assertEqual("Usage: /incident <incident-id>", reply)

    def test_approve_command_without_argument_returns_usage(self) -> None:
        reply = telegram._handle_command("/approve")
        self.assertEqual("Usage: /approve <action-id>", reply)

    def test_handle_callback_dispatches_approve(self) -> None:
        with patch("app.telegram.approve_action", return_value="ok") as approve_action:
            reply = telegram._handle_callback("approve:f314980d")

        self.assertEqual("ok", reply)
        approve_action.assert_called_once_with("f314980d")

    def test_handle_callback_rejects_unknown_payload(self) -> None:
        reply = telegram._handle_callback("bogus")
        self.assertEqual("[telegram_callback_payload_invalid] Unsupported action button payload.", reply)

    def test_unknown_command_returns_help(self) -> None:
        reply = telegram._handle_command("/help")
        self.assertIn("/incident <incident-id>", reply)
        self.assertIn("/approve <action-id>", reply)

    def test_start_telegram_polling_thread_skips_when_token_missing(self) -> None:
        with patch("app.telegram._telegram_token", return_value=None):
            thread = telegram.start_telegram_polling_thread()

        self.assertIsNone(thread)

    def test_start_telegram_polling_thread_starts_when_enabled(self) -> None:
        fake_thread = MagicMock()
        with patch("app.telegram._telegram_token", return_value="token"):
            with patch("app.telegram.threading.Thread", return_value=fake_thread) as thread_cls:
                thread = telegram.start_telegram_polling_thread()

        self.assertIs(thread, fake_thread)
        thread_cls.assert_called_once()
        fake_thread.start.assert_called_once()

    def test_poll_updates_ignores_unauthorized_chat(self) -> None:
        body = {
            "ok": True,
            "result": [{"update_id": 7, "message": {"chat": {"id": 123}, "text": "/approve deadbeef"}}],
        }
        with patch("app.telegram._telegram_token", return_value="token"):
            with patch("app.telegram._telegram_api", return_value=body):
                with patch("app.telegram._allowed_chat_ids", return_value={"999"}):
                    with patch("app.telegram._save_offset"):
                        with patch("app.telegram._send_message") as send_message:
                            with patch("app.telegram.log_event") as log_event:
                                result = telegram.poll_telegram_updates_once()

        self.assertEqual("Processed 0 Telegram command(s).", result)
        send_message.assert_not_called()
        log_event.assert_any_call("telegram_command_ignored_unauthorized", chat_id="123", text="/approve deadbeef")

    def test_poll_updates_sends_actionable_failure_reply(self) -> None:
        body = {
            "ok": True,
            "result": [{"update_id": 11, "message": {"chat": {"id": 123}, "text": "/approve deadbeef"}}],
        }
        with patch("app.telegram._telegram_token", return_value="token"):
            with patch("app.telegram._telegram_api", return_value=body):
                with patch("app.telegram._allowed_chat_ids", return_value=set()):
                    with patch("app.telegram._save_offset"):
                        with patch("app.telegram._handle_command", side_effect=RuntimeError("boom")):
                            with patch("app.telegram._send_message", return_value="Telegram reply sent.") as send_message:
                                telegram.poll_telegram_updates_once()

        send_message.assert_called_once_with(
            "123",
            "[telegram_command_execution_failed] Command failed due to an internal error. Please retry and check service logs.",
        )

    def test_poll_updates_sends_taxonomy_failure_reply_for_callback_errors(self) -> None:
        body = {
            "ok": True,
            "result": [
                {
                    "update_id": 14,
                    "callback_query": {
                        "id": "cb-3",
                        "data": "approve:deadbeef",
                        "message": {"chat": {"id": 123}},
                    },
                }
            ],
        }
        with patch("app.telegram._telegram_token", return_value="token"):
            with patch("app.telegram._telegram_api", return_value=body):
                with patch("app.telegram._allowed_chat_ids", return_value=set()):
                    with patch("app.telegram._save_offset"):
                        with patch("app.telegram._handle_callback", side_effect=RuntimeError("boom")):
                            with patch("app.telegram._send_message", return_value="Telegram reply sent.") as send_message:
                                with patch(
                                    "app.telegram._answer_callback_query",
                                    return_value="Telegram callback acknowledged.",
                                ) as ack:
                                    telegram.poll_telegram_updates_once()

        send_message.assert_called_once_with(
            "123",
            "[telegram_callback_execution_failed] Action failed due to an internal error. Please retry and check service logs.",
        )
        ack.assert_called_once_with(
            "cb-3",
            "[telegram_callback_execution_failed] Action failed due to an internal error. Please retry and check service logs.",
        )

    def test_poll_updates_processes_callback_query(self) -> None:
        body = {
            "ok": True,
            "result": [
                {
                    "update_id": 12,
                    "callback_query": {
                        "id": "cb-1",
                        "data": "approve:deadbeef",
                        "message": {"chat": {"id": 123}},
                    },
                }
            ],
        }
        with patch("app.telegram._telegram_token", return_value="token"):
            with patch("app.telegram._telegram_api", return_value=body):
                with patch("app.telegram._allowed_chat_ids", return_value=set()):
                    with patch("app.telegram._save_offset"):
                        with patch("app.telegram._handle_callback", return_value="approved") as handle_callback:
                            with patch("app.telegram._send_message", return_value="Telegram reply sent.") as send_message:
                                with patch("app.telegram._answer_callback_query", return_value="Telegram callback acknowledged.") as ack:
                                    result = telegram.poll_telegram_updates_once()

        self.assertEqual("Processed 1 Telegram command(s).", result)
        handle_callback.assert_called_once_with("approve:deadbeef")
        send_message.assert_called_once_with("123", "approved")
        ack.assert_called_once_with("cb-1", "approved")

    def test_poll_updates_ignores_unauthorized_callback_query(self) -> None:
        body = {
            "ok": True,
            "result": [
                {
                    "update_id": 13,
                    "callback_query": {
                        "id": "cb-2",
                        "data": "reject:deadbeef",
                        "message": {"chat": {"id": 123}},
                    },
                }
            ],
        }
        with patch("app.telegram._telegram_token", return_value="token"):
            with patch("app.telegram._telegram_api", return_value=body):
                with patch("app.telegram._allowed_chat_ids", return_value={"999"}):
                    with patch("app.telegram._save_offset"):
                        with patch("app.telegram._send_message") as send_message:
                            result = telegram.poll_telegram_updates_once()

        self.assertEqual("Processed 0 Telegram command(s).", result)
        send_message.assert_not_called()

    def test_poll_updates_uses_numeric_poll_timeout_override(self) -> None:
        with patch.dict(environ, {"TELEGRAM_POLL_TIMEOUT_SECONDS": "42"}, clear=False):
            with patch("app.telegram._telegram_token", return_value="token"):
                with patch("app.telegram._load_offset", return_value=None):
                    with patch("app.telegram._telegram_api", return_value={"ok": True, "result": []}) as telegram_api:
                        result = telegram.poll_telegram_updates_once()

        self.assertEqual("No new Telegram updates.", result)
        telegram_api.assert_called_once_with("getUpdates?timeout=42")

    def test_telegram_api_raises_http_timeout_when_configured_below_poll_timeout(self) -> None:
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b'{"ok": true, "result": []}'

        with patch.dict(
            environ,
            {
                "TELEGRAM_BOT_TOKEN": "token",
                "TELEGRAM_POLL_TIMEOUT_SECONDS": "30",
                "TELEGRAM_HTTP_TIMEOUT_SECONDS": "20",
            },
            clear=False,
        ):
            with patch("app.telegram.urllib.request.urlopen", return_value=FakeResponse()) as urlopen:
                telegram._telegram_api("getUpdates")

        self.assertEqual(35.0, urlopen.call_args.kwargs["timeout"])

    def test_timeout_parsing_falls_back_to_defaults_on_invalid_values(self) -> None:
        with patch.dict(
            environ,
            {
                "TELEGRAM_POLL_TIMEOUT_SECONDS": "abc",
                "TELEGRAM_HTTP_TIMEOUT_SECONDS": "-1",
            },
            clear=False,
        ):
            self.assertEqual(30.0, telegram._poll_timeout_seconds())
            self.assertEqual(35.0, telegram._http_timeout_seconds())
